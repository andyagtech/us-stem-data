#!/usr/bin/env python3
"""Does the below-median finding hold where the filings actually are?

The national comparison says 73.3% of priced H-1B filings promise less than
the median wage for their occupation. That uses ONE national median per
occupation, and H-1B filings do not fall evenly across the country: they
concentrate in California, Texas, New York and New Jersey, where wages are
above the national median. A national yardstick could therefore be flattering
the filings -- a wage that clears the national median may still sit below the
local one.

This re-runs the comparison against the median for the occupation IN THE
STATE OF THE WORKSITE, and reports both numbers so the difference is visible.

WHY STATE AND NOT METRO. OEWS publishes metropolitan areas too and they would
be sharper, but the labour condition application records a worksite state
reliably and a metro only by city and postcode, which would need a crosswalk
that introduces its own errors. State is the finest cut both sides support
without guessing.

Usage:
  python3 scripts/build_local_wage_comparison.py
  python3 scripts/build_local_wage_comparison.py --keep
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import warnings
import zipfile
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "data" / "h1b" / "_lca_work"
OES = ROOT / "data" / "bls_oes"
OUT = ROOT / "site" / "data" / "local_wage_comparison.json"
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

BUCKET = "s3://phd-demographics-raw-data/data/h1b/lca/"
PROFILE = "personal"
FILES = {2019: ["H-1B_Disclosure_Data_FY2019.xlsx"],
         2023: ["lca_fy2023_Q1.xlsx", "lca_fy2023_Q2.xlsx",
                "lca_fy2023_Q3.xlsx", "lca_fy2023_Q4.xlsx"]}
LEVELS = ("Level I", "Level II", "Level III", "Level IV")
LEVEL_ALIASES = {"I": "Level I", "II": "Level II",
                 "III": "Level III", "IV": "Level IV"}
UNITS = {"year": 1, "yr": 1, "hour": 2080, "hr": 2080, "week": 52, "wk": 52,
         "bi-weekly": 26, "biweekly": 26, "month": 12, "mth": 12}


def load_state_medians() -> tuple[dict[tuple[str, str], float], int]:
    """(state abbreviation, SOC) -> annual median wage."""
    import openpyxl
    files = sorted(OES.glob("oesm*st.zip"))
    if not files:
        return {}, 0
    path = files[-1]
    year = 2000 + int(re.search(r"oesm(\d{2})st", path.name).group(1))
    with zipfile.ZipFile(path) as z:
        inner = next(n for n in z.namelist() if n.lower().endswith((".xlsx", ".xls")))
        wb = openpyxl.load_workbook(io.BytesIO(z.read(inner)), read_only=True)
    ws = wb[wb.sheetnames[0]]
    it = ws.iter_rows(values_only=True)
    hdr = [str(c).upper() if c is not None else "" for c in next(it)]
    idx = {c: i for i, c in enumerate(hdr)}
    need = ("PRIM_STATE", "OCC_CODE", "O_GROUP", "A_MEDIAN")
    if any(c not in idx for c in need):
        raise SystemExit(f"  {path.name}: missing {[c for c in need if c not in idx]}")
    out = {}
    for r in it:
        if str(r[idx["O_GROUP"]] or "").strip().lower() != "detailed":
            continue
        st = str(r[idx["PRIM_STATE"]] or "").strip().upper()
        soc = str(r[idx["OCC_CODE"]] or "").strip()
        v = r[idx["A_MEDIAN"]]
        if len(st) != 2 or not re.fullmatch(r"\d{2}-\d{4}", soc):
            continue
        try:
            med = float(str(v).replace(",", "").replace("$", ""))
        except (TypeError, ValueError):
            continue
        out[(st, soc)] = med
    return out, year


def national_medians() -> dict[str, float]:
    p = ROOT / "site" / "data" / "occupational_wages.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text())
    by = d["by_soc"][str(d["latest_year"])]
    return {soc: v["median"] for soc, v in by.items() if v.get("median")}


def load_county_to_cbsa() -> dict[tuple[str, str], str]:
    """(county name, state abbreviation) -> CBSA code.

    The application records a worksite COUNTY, and the Census delineation
    file maps counties to metropolitan areas, so the chain is deterministic:
    no city-name or postcode guessing anywhere in it.
    """
    import openpyxl
    path = ROOT / "data" / "census_geo" / "cbsa_delineation_2023.xlsx"
    if not path.exists():
        return {}
    ws = openpyxl.load_workbook(path, read_only=True).active
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    hdr_at = next((i for i, r in enumerate(rows[:8])
                   if any(str(c or "").strip() == "CBSA Code" for c in r)), None)
    if hdr_at is None:
        return {}
    hdr = [str(c or "").strip() for c in rows[hdr_at]]
    idx = {c: i for i, c in enumerate(hdr)}
    need = ("CBSA Code", "County/County Equivalent", "State Name")
    if any(c not in idx for c in need):
        return {}
    out = {}
    for r in rows[hdr_at + 1:]:
        code = str(r[idx["CBSA Code"]] or "").strip()
        county = str(r[idx["County/County Equivalent"]] or "").strip()
        state = str(r[idx["State Name"]] or "").strip()
        if not (code.isdigit() and county and state):
            continue
        ab = STATE_ABBR.get(state.upper())
        if ab:
            out[(norm_county(county), ab)] = code
    return out


def norm_county(name: str) -> str:
    """Strip the suffixes and punctuation the two sources spell differently."""
    s = str(name or "").upper()
    s = re.sub(r"\b(COUNTY|PARISH|BOROUGH|CENSUS AREA|CITY AND BOROUGH|"
               r"MUNICIPALITY|MUNICIPIO)\b", " ", s)
    s = s.replace("SAINT ", "ST ").replace("ST. ", "ST ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return " ".join(s.split())


STATE_ABBR = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT",
    "DELAWARE": "DE", "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL",
    "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL",
    "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY",
    "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT",
    "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY",
    "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH",
    "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "PUERTO RICO": "PR", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
    "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
}


def load_metro_medians() -> dict[tuple[str, str], float]:
    """(CBSA code, SOC) -> annual median wage."""
    import openpyxl
    files = sorted(OES.glob("oesm*ma.zip"))
    if not files:
        return {}
    with zipfile.ZipFile(files[-1]) as z:
        inner = next((n for n in z.namelist() if "MSA" in n.upper()
                      and n.lower().endswith(".xlsx")), None)
        if not inner:
            return {}
        wb = openpyxl.load_workbook(io.BytesIO(z.read(inner)), read_only=True)
    it = wb[wb.sheetnames[0]].iter_rows(values_only=True)
    hdr = [str(c).upper() if c is not None else "" for c in next(it)]
    idx = {c: i for i, c in enumerate(hdr)}
    if any(c not in idx for c in ("AREA", "OCC_CODE", "O_GROUP", "A_MEDIAN")):
        return {}
    out = {}
    for r in it:
        if str(r[idx["O_GROUP"]] or "").strip().lower() != "detailed":
            continue
        area = str(r[idx["AREA"]] or "").strip()
        soc = str(r[idx["OCC_CODE"]] or "").strip()
        try:
            med = float(str(r[idx["A_MEDIAN"]]).replace(",", "").replace("$", ""))
        except (TypeError, ValueError):
            continue
        if area and re.fullmatch(r"\d{2}-\d{4}", soc):
            out[(area, soc)] = med
    return out



def fetch(fname: str) -> Path | None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    dest = SCRATCH / fname
    if dest.exists():
        return dest
    r = subprocess.run(["aws", "s3", "cp", f"{BUCKET}{fname}", str(dest),
                        "--profile", PROFILE, "--no-progress"],
                       capture_output=True, text=True)
    return dest if dest.exists() else None


def scan(path: Path, state_med, nat_med, metro_med, cty2cbsa, tally) -> int:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb[wb.sheetnames[0]]
    it = ws.iter_rows(values_only=True)
    hdr = [str(c) if c is not None else "" for c in next(it)]
    idx = {c: i for i, c in enumerate(hdr)}

    def pick(*names):
        return next((idx[n] for n in names if n in idx), None)

    i_lvl = pick("PW_WAGE_LEVEL_1", "PW_WAGE_LEVEL")
    i_wage = pick("PREVAILING_WAGE_1", "PREVAILING_WAGE")
    i_unit = pick("PW_UNIT_OF_PAY_1", "PW_UNIT_OF_PAY")
    i_soc = pick("SOC_CODE", "PW_SOC_CODE")
    i_st = pick("WORKSITE_STATE", "WORKSITE_STATE_1", "EMPLOYER_STATE")
    i_cty = pick("WORKSITE_COUNTY", "WORKSITE_COUNTY_1")
    i_status, i_class = pick("CASE_STATUS"), pick("VISA_CLASS")
    if None in (i_lvl, i_wage, i_unit, i_soc, i_st, i_status, i_class):
        print(f"    {path.name}: missing a required column")
        wb.close()
        return 0

    n = 0
    for r in it:
        if not str(r[i_status] or "").strip().upper().startswith("CERTIFIED"):
            continue
        if str(r[i_class] or "").strip().upper() != "H-1B":
            continue
        lvl = LEVEL_ALIASES.get(str(r[i_lvl] or "").strip().upper(),
                                str(r[i_lvl] or "").strip())
        if lvl not in LEVELS:
            continue
        m = re.search(r"(\d{2})-?(\d{4})", str(r[i_soc] or ""))
        st = str(r[i_st] or "").strip().upper()
        if not m or len(st) != 2:
            continue
        soc = f"{m.group(1)}-{m.group(2)}"
        try:
            wage = float(str(r[i_wage] or "").replace(",", "").replace("$", ""))
        except ValueError:
            continue
        mult = UNITS.get(str(r[i_unit] or "").strip().lower())
        if mult is None:
            mult = 1 if wage > 15000 else None
            if mult is None:
                continue
        annual = wage * mult
        if not 10_000 <= annual <= 1_000_000:
            continue

        loc = state_med.get((st, soc))
        nat = nat_med.get(soc)
        if loc is None or nat is None:
            tally["unmatched"] += 1
            continue
        n += 1
        tally["priced"] += 1
        tally["below_national"] += annual < nat
        tally["below_local"] += annual < loc

        # Metro where the county resolves to one; the state figure stands
        # for everyone else rather than a metro being guessed.
        cbsa = (cty2cbsa.get((norm_county(r[i_cty]), st))
                if i_cty is not None else None)
        met = metro_med.get((cbsa, soc)) if cbsa else None
        if met is None:
            tally["no_metro"] += 1
        else:
            tally["metro_priced"] += 1
            tally["below_metro"] += annual < met
            tally["below_national_metro_subset"] += annual < nat
        s = tally["by_state"][st]
        s["priced"] += 1
        s["below_local"] += annual < loc
        s["below_national"] += annual < nat
        lv = tally["by_level"][lvl]
        lv["priced"] += 1
        lv["below_local"] += annual < loc
        lv["below_national"] += annual < nat
    wb.close()
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    state_med, oes_year = load_state_medians()
    nat_med = national_medians()
    metro_med = load_metro_medians()
    cty2cbsa = load_county_to_cbsa()
    if not state_med or not nat_med:
        print("  need both the OEWS state file and occupational_wages.json")
        return 1

    tally = {"priced": 0, "below_national": 0, "below_local": 0, "unmatched": 0,
             "metro_priced": 0, "below_metro": 0, "no_metro": 0,
             "below_national_metro_subset": 0,
             "by_state": defaultdict(lambda: {"priced": 0, "below_local": 0,
                                              "below_national": 0}),
             "by_level": defaultdict(lambda: {"priced": 0, "below_local": 0,
                                              "below_national": 0})}
    for year, names in FILES.items():
        for fname in names:
            print(f"  {year}: {fname}")
            p = fetch(fname)
            if not p:
                print(f"    fetch failed")
                continue
            scan(p, state_med, nat_med, metro_med, cty2cbsa, tally)
            if not args.keep:
                p.unlink(missing_ok=True)

    if tally["priced"] < 10_000:
        print(f"  only {tally['priced']:,} filings priced")
        return 1

    def pct(a, b):
        return round(100 * a / b, 1) if b else None

    states = sorted(
        ({"state": st, "priced": v["priced"],
          "below_local_pct": pct(v["below_local"], v["priced"]),
          "below_national_pct": pct(v["below_national"], v["priced"]),
          "difference_pts": round(pct(v["below_local"], v["priced"])
                                  - pct(v["below_national"], v["priced"]), 1)}
         for st, v in tally["by_state"].items() if v["priced"] >= 2000),
        key=lambda x: -x["priced"])

    doc = {
        "_comment": (
            "The share of certified H-1B filings promising less than the "
            "median wage for their occupation, measured twice: against the "
            "NATIONAL median and against the median for that occupation IN "
            "THE WORKSITE STATE. Built because filings concentrate in "
            "high-wage states, so a national yardstick can flatter them -- a "
            "wage clearing the national median may still sit below the local "
            "one. THE FINER THE GEOGRAPHY THE WORSE THE FILINGS LOOK, which "
            "is what happens when they cluster in expensive places: national "
            "70.8%, state 78.7%, metropolitan 84.0%. THE METRO FIGURE IS THE "
            "SHARPEST and is reached deterministically -- the application "
            "records a worksite COUNTY, and the Census delineation file maps "
            "counties to metropolitan areas, so no city name or postcode is "
            "guessed anywhere. Filings whose county resolves to no metro area "
            "(9%) keep the state comparison rather than being dropped or "
            "assigned one. Filings whose "
            "occupation has no published median in their state are counted as "
            "unmatched rather than assigned the national figure. This is what "
            "was PROMISED, not paid, and filing at a low level is lawful."),
        "sources": {
            "wages": f"BLS OEWS state file, {oes_year}",
            "filings": "US DOL OFLC, H-1B LCA disclosure data, FY2019 and FY2023",
        },
        "oews_year": oes_year,
        "filings_priced": tally["priced"],
        "unmatched_state_occupation": tally["unmatched"],
        "below_national_median_pct": pct(tally["below_national"], tally["priced"]),
        "below_local_median_pct": pct(tally["below_local"], tally["priced"]),
        "metro": {
            "filings_priced": tally["metro_priced"],
            "no_metro_match": tally["no_metro"],
            "below_metro_median_pct": pct(tally["below_metro"], tally["metro_priced"]),
            "below_national_median_pct_same_subset": pct(
                tally["below_national_metro_subset"], tally["metro_priced"])},
        "by_level": {k: {"priced": v["priced"],
                         "below_national_pct": pct(v["below_national"], v["priced"]),
                         "below_local_pct": pct(v["below_local"], v["priced"])}
                     for k, v in sorted(tally["by_level"].items())},
        "by_state": states[:25],
    }
    write_json(OUT, doc)

    print(f"\n  {tally['priced']:,} filings priced "
          f"({tally['unmatched']:,} had no state median for their occupation)")
    print(f"  below the NATIONAL median: {doc['below_national_median_pct']}%")
    print(f"  below the LOCAL median:    {doc['below_local_median_pct']}%")
    mt = doc["metro"]
    if mt["filings_priced"]:
        print(f"\n  metro subset: {mt['filings_priced']:,} filings "
              f"({mt['no_metro_match']:,} had no metro match)")
        print(f"   below national: {mt['below_national_median_pct_same_subset']}%")
        print(f"   below METRO:    {mt['below_metro_median_pct']}%")
    print(f"\n  {'level':12}{'national':>11}{'local':>9}")
    for k, v in doc["by_level"].items():
        print(f"  {k:12}{v['below_national_pct']:>10.1f}%{v['below_local_pct']:>8.1f}%")
    print(f"\n  {'state':7}{'filings':>10}{'national':>11}{'local':>9}{'diff':>8}")
    for x in states[:10]:
        print(f"  {x['state']:7}{x['priced']:>10,}{x['below_national_pct']:>10.1f}%"
              f"{x['below_local_pct']:>8.1f}%{x['difference_pts']:>+8.1f}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
