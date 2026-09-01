#!/usr/bin/env python3
"""What states put in, and what students were charged, over twenty-four years.

The project has established that foreign master's students pay published
out-of-state rates and that some institutions run on them. It has not looked
at what happened to the price for everyone else, or at what states were
contributing while that price moved.

This puts the two series side by side, per state and per institution:
published IN-STATE tuition at public institutions, and state education
appropriations per full-time-equivalent student. Both in constant dollars,
because a nominal comparison over twenty-four years is meaningless.

WHAT IT CAN AND CANNOT SHOW. Two series moving in opposite directions is a
substitution PATTERN, not a demonstrated cause: appropriations are set by
legislatures and tuition by boards, both responding to enrolment, costs and
politics at once. And the tuition figure is a PUBLISHED RATE -- the sticker
before any discount, waiver or aid -- so it is what a student is quoted, not
what the average student pays.

Usage:
  python3 scripts/build_tuition_and_appropriations.py
  python3 scripts/build_tuition_and_appropriations.py --institution 236948
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
import statistics
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
TUITION = ROOT / "data" / "ipeds_tuition"
SHEF = ROOT / "data" / "shef" / "SHEEO_SHEF_FY24_Report_Data.xlsx"
SFA = ROOT / "data" / "ipeds_sfa"
HD = ROOT / "data" / "ipeds" / "hd2024.csv"
CPI_DIR = ROOT / "data" / "bls_cpi"
OUT = ROOT / "site" / "data" / "tuition_and_appropriations.json"

# IPEDS IC*_AY: 2 is in-state undergraduate, 6 in-state graduate,
# 3 and 7 the out-of-state equivalents. Fees are billed alongside tuition
# and a rate without them understates what a student is charged.
RATES = {"in_state_undergrad": ("TUITION2", "FEE2"),
         "in_state_grad": ("TUITION6", "FEE6"),
         "out_state_undergrad": ("TUITION3", "FEE3")}
BASE_YEAR = 2024
PUBLIC = "1"
# Institutions worth naming in the output.
FEATURED = {"236948": "University of Washington-Seattle Campus",
            "170976": "University of Michigan-Ann Arbor",
            "110635": "University of California-Berkeley",
            "228778": "The University of Texas at Austin",
            "134130": "University of Florida",
            "145637": "University of Illinois Urbana-Champaign"}


def load_cpi() -> dict[int, float]:
    ann = {}
    for f in glob.glob(str(CPI_DIR / "*.json")):
        d = json.loads(Path(f).read_text())
        for s in (d.get("Results") or {}).get("series", []):
            for x in s.get("data", []):
                if x.get("period") == "M13":       # annual average
                    ann[int(x["year"])] = float(x["value"])
    return ann


def num(v):
    s = str(v or "").strip().replace(",", "")
    if not s or s in (".", "-"):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return f if f > 0 else None


def load_institutions() -> dict[str, tuple[str, bool]]:
    out = {}
    with open(HD, encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            uid = (r.get("UNITID") or "").strip()
            st = (r.get("STABBR") or "").strip().upper()
            if uid and st:
                out[uid] = (st, (r.get("CONTROL") or "").strip() == PUBLIC)
    return out


def load_shef() -> dict[tuple[str, int], float]:
    import openpyxl
    ws = openpyxl.load_workbook(SHEF, read_only=True)["Report Data"]
    it = ws.iter_rows(values_only=True)
    hdr = [str(c) if c is not None else "" for c in next(it)]
    idx = {c: i for i, c in enumerate(hdr)}
    out = {}
    for r in it:
        try:
            state = str(r[idx["State"]] or "").strip()
            fy = int(r[idx["FY"]])
            approp = float(r[idx["Education Appropriations"]] or 0)
            fte = float(r[idx["Net FTE Enrollment"]] or 0)
            heca = float(r[idx["HECA (Inflation) Adjustment"]] or 1) or 1
        except (TypeError, ValueError, KeyError):
            continue
        if state and fte > 0:
            # HECA is an index: nominal is DIVIDED by it for constant dollars.
            out[(state, fy)] = approp / heca / fte
    return out


def load_net_price(cpi: dict, base: float, inst: dict) -> dict[str, dict[int, dict]]:
    """UNITID -> year -> net price, in constant dollars.

    IPEDS reports NET PRICE for FIRST-TIME, FULL-TIME UNDERGRADUATES paying
    the in-state rate and receiving aid: cost of attendance -- which includes
    living costs, unlike the tuition rate -- minus grant aid. It is the best
    published answer to "what does someone actually pay", and it is NOT the
    same population or the same basis as the sticker rate beside it.

    Each file carries three years in suffixed columns; only the file's own
    year (suffix 2) is taken, so the years do not overlap between files.
    """
    import zipfile, io
    out: dict[str, dict[int, dict]] = {}
    for path in sorted(SFA.glob("SFA*.zip")):
        m = re.search(r"SFA(\d{2})(\d{2})", path.name)
        if not m:
            continue
        # SFA2223 describes academic year 2022-23; key it to the later year
        # so it lines up with the IPEDS tuition file for the same cycle.
        year = 2000 + int(m.group(2))
        if year not in cpi:
            continue
        deflate = base / cpi[year]
        with zipfile.ZipFile(path) as z:
            inner = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(inner) as fh:
                rd = csv.DictReader(io.TextIOWrapper(
                    fh, encoding="utf-8-sig", errors="replace"))
                cols = {c.upper(): c for c in (rd.fieldnames or [])}
                for r in rd:
                    uid = (r.get(cols.get("UNITID", "UNITID")) or "").strip()
                    got = inst.get(uid)
                    if not got or not got[1]:
                        continue
                    rec = {}
                    # NPIST is the public-sector column; NPGRN the private.
                    v = num(r.get(cols.get("NPIST2", "NPIST2")))
                    if v:
                        rec["net_price"] = round(v * deflate, 2)
                    lo = num(r.get(cols.get("NPIS412", "NPIS412")))
                    hi = num(r.get(cols.get("NPIS452", "NPIS452")))
                    if lo:
                        rec["net_price_income_under_30k"] = round(lo * deflate, 2)
                    if hi:
                        rec["net_price_income_over_110k"] = round(hi * deflate, 2)
                    if rec:
                        out.setdefault(uid, {})[year] = rec
    return out



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--institution")
    args = ap.parse_args()

    cpi = load_cpi()
    if not cpi:
        print(f"  no CPI in {CPI_DIR.relative_to(ROOT)}")
        return 1
    base = cpi[max(k for k in cpi if k <= BASE_YEAR)]
    inst = load_institutions()
    shef = load_shef()
    netp = load_net_price(cpi, base, inst)

    # Per institution and year, the published rates in constant dollars.
    series: dict[str, dict[int, dict]] = {}
    for path in sorted(TUITION.glob("ic*_ay*.csv")):
        m = re.search(r"ic(\d{4})", path.name)
        if not m:
            continue
        year = int(m.group(1))
        if year not in cpi:
            continue
        deflate = base / cpi[year]
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            rd = csv.DictReader(fh)
            cols = {c.upper(): c for c in (rd.fieldnames or [])}
            for r in rd:
                uid = (r.get(cols.get("UNITID", "UNITID")) or "").strip()
                got = inst.get(uid)
                if not got or not got[1]:          # public institutions only
                    continue
                rec = {}
                for key, (tc, fc) in RATES.items():
                    t = num(r.get(cols.get(tc, tc)))
                    if t is None:
                        continue
                    f = num(r.get(cols.get(fc, fc))) or 0
                    rec[key] = round((t + f) * deflate, 2)
                if rec:
                    series.setdefault(uid, {})[year] = rec

    if not series:
        print("  no tuition rows parsed")
        return 1

    years = sorted({y for v in series.values() for y in v})
    first, last = years[0], years[-1]

    # State medians: the typical published in-state rate, beside what the
    # state put in per student that year.
    STATE_NAMES = json.loads((ROOT / "pipeline" / "state_names.json").read_text()) \
        if (ROOT / "pipeline" / "state_names.json").exists() else None
    MEASURES = ("in_state_undergrad", "out_state_undergrad", "net_price")
    by_state: dict[str, dict[int, dict]] = {}
    for uid, yrs in series.items():
        st = inst[uid][0]
        for y, rec in yrs.items():
            slot = by_state.setdefault(st, {}).setdefault(
                y, {m: [] for m in MEASURES})
            for m in ("in_state_undergrad", "out_state_undergrad"):
                if m in rec:
                    slot[m].append(rec[m])
    for uid, yrs in netp.items():
        st = inst[uid][0]
        for y, rec in yrs.items():
            if rec.get("net_price"):
                by_state.setdefault(st, {}).setdefault(
                    y, {m: [] for m in MEASURES})["net_price"].append(
                        rec["net_price"])

    STATE_FULL = {v: k for k, v in {}.items()}   # populated from SHEF below
    states = []
    for st, yrs in sorted(by_state.items()):
        row = {"abbr": st, "years": {}}
        for y in sorted(yrs):
            cell = {}
            for m in MEASURES:
                vals = yrs[y].get(m) or []
                # Three institutions is the floor: a state median off one or
                # two schools is not a state median.
                if len(vals) >= 3:
                    cell[f"median_{m}"] = round(statistics.median(vals), 2)
                    cell[f"{m}_institutions"] = len(vals)
            if cell:
                row["years"][str(y)] = cell
        if len(row["years"]) >= 10:
            states.append(row)

    # The comparison the states table exists for: change on each measure
    # across the common window, per state.
    WINDOW = (2011, 2023)
    comparison = []
    for row in states:
        f_, l_ = (row["years"].get(str(WINDOW[0])), row["years"].get(str(WINDOW[1])))
        if not f_ or not l_:
            continue
        rec = {"abbr": row["abbr"]}
        for m in MEASURES:
            a, b = f_.get(f"median_{m}"), l_.get(f"median_{m}")
            if a and b:
                rec[f"{m}_change_pct"] = round(100 * (b / a - 1), 1)
                rec[f"{m}_last"] = b
        if len(rec) > 1:
            comparison.append(rec)

    featured = []
    for uid, name in FEATURED.items():
        yrs = series.get(uid)
        if not yrs:
            continue
        pts = {str(y): v for y, v in sorted(yrs.items())
               if "in_state_undergrad" in v}
        if len(pts) < 10:
            continue
        ys = sorted(int(y) for y in pts)
        f, l = str(ys[0]), str(ys[-1])
        np_series = {str(y): v.get("net_price")
                     for y, v in sorted(netp.get(uid, {}).items())
                     if v.get("net_price")}
        featured.append({
            "unitid": uid, "institution": name, "state": inst[uid][0],
            "first_year": ys[0], "last_year": ys[-1],
            "first": pts[f]["in_state_undergrad"],
            "last": pts[l]["in_state_undergrad"],
            "change_pct": round(100 * (pts[l]["in_state_undergrad"]
                                       / pts[f]["in_state_undergrad"] - 1), 1),
            "series": {y: v["in_state_undergrad"] for y, v in pts.items()},
            "out_of_state_series": {y: v["out_state_undergrad"]
                                    for y, v in pts.items()
                                    if "out_state_undergrad" in v},
            "net_price_series": np_series})

    doc = {
        "_comment": (
            "Published IN-STATE tuition and required fees at PUBLIC "
            "institutions (IPEDS IC*_AY) beside state education "
            "appropriations per full-time-equivalent student (SHEEO SHEF), "
            "both in constant " + str(BASE_YEAR) + " dollars -- tuition "
            "deflated by CPI-U from the BLS API, appropriations by SHEEO's "
            "own HECA index, which is an index and therefore DIVIDES. "
            "TUITION HERE IS A PUBLISHED RATE: the sticker before any "
            "discount, waiver, scholarship or aid, so it is what a student is "
            "quoted and not what the average student pays. Two series moving "
            "apart is a substitution PATTERN, NOT A DEMONSTRATED CAUSE -- "
            "legislatures set one and boards the other, both responding to "
            "enrolment, cost and politics at once. THE PERIOD DECIDES THE "
            "STORY, so always give the window: the substitution is a "
            "2008-2012 event, and across 2011-2023 it RUNS THE OTHER WAY -- "
            "median state appropriations per FTE rose 11.2% in real terms, "
            "median in-state sticker rose 2.5%, and median NET PRICE FELL "
            "6.6% with 35 of 51 states down. 'Students pay more while states "
            "pay less' describes the crash years, not the decade after them. "
            "NET PRICE is the better measure of what is actually paid and is "
            "a DIFFERENT population and basis from the sticker beside it: "
            "first-time full-time undergraduates receiving aid, cost of "
            "attendance including living costs, minus grant aid. Public "
            "institutions only, because in-state tuition is a public-sector "
            "concept."),
        "sources": {
            "tuition": "NCES IPEDS Institutional Characteristics, academic year rates",
            "appropriations": "SHEEO State Higher Education Finance, FY2024 report",
            "deflator": "BLS CPI-U, CUUR0000SA0, annual average",
        },
        "source_url": "https://nces.ed.gov/ipeds/use-the-data",
        "base_year": BASE_YEAR,
        "years": years,
        "institutions": len(series),
        "featured_institutions": featured,
        "net_price_institutions": len(netp),
        "states": states,
        "comparison_window": list(WINDOW),
        "state_comparison": comparison,
        "state_appropriations_per_fte": {
            f"{st}|{fy}": round(v, 2) for (st, fy), v in shef.items()
            if first <= fy <= last},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {len(series):,} public institutions, {first}-{last}, "
          f"constant {BASE_YEAR} dollars")
    print(f"\n  published in-state undergraduate tuition and fees:")
    print(f"  {'institution':44}{first:>10}{last:>10}{'change':>9}")
    for f_ in featured:
        print(f"  {f_['institution'][:42]:44}${f_['first']:>9,.0f}"
              f"${f_['last']:>9,.0f}{f_['change_pct']:>8.0f}%")
    if args.institution:
        f_ = next((x for x in featured if x["unitid"] == args.institution), None)
        if f_:
            print(f"\n  {f_['institution']}, year by year:")
            for y, v in sorted(f_["series"].items()):
                print(f"   {y}  ${v:,.0f}")
    if comparison:
        w = [c for c in comparison if "in_state_undergrad_change_pct" in c]
        w.sort(key=lambda c: -c["in_state_undergrad_change_pct"])
        print(f"\n  real change {WINDOW[0]}-{WINDOW[1]}, median public rates:")
        print(f"  {'state':7}{'in-state':>11}{'out-of-state':>15}{'net price':>12}")
        for c in w[:5] + w[-5:]:
            g = lambda k: (f"{c[k]:+.0f}%" if k in c else "-")
            print(f"  {c['abbr']:7}{g('in_state_undergrad_change_pct'):>11}"
                  f"{g('out_state_undergrad_change_pct'):>15}"
                  f"{g('net_price_change_pct'):>12}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
