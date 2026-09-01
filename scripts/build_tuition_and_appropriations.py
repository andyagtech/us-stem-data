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
    by_state: dict[str, dict[int, dict]] = {}
    for uid, yrs in series.items():
        st = inst[uid][0]
        for y, rec in yrs.items():
            if "in_state_undergrad" in rec:
                by_state.setdefault(st, {}).setdefault(y, {"rates": []})
                by_state[st][y]["rates"].append(rec["in_state_undergrad"])

    states = []
    for st, yrs in sorted(by_state.items()):
        row = {"abbr": st, "years": {}}
        for y in sorted(yrs):
            rates = yrs[y]["rates"]
            if len(rates) < 3:
                continue
            row["years"][str(y)] = {
                "median_in_state_undergrad": round(statistics.median(rates), 2),
                "institutions": len(rates)}
        if len(row["years"]) >= 10:
            states.append(row)

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
        featured.append({
            "unitid": uid, "institution": name, "state": inst[uid][0],
            "first_year": ys[0], "last_year": ys[-1],
            "first": pts[f]["in_state_undergrad"],
            "last": pts[l]["in_state_undergrad"],
            "change_pct": round(100 * (pts[l]["in_state_undergrad"]
                                       / pts[f]["in_state_undergrad"] - 1), 1),
            "series": {y: v["in_state_undergrad"] for y, v in pts.items()}})

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
            "enrolment, cost and politics at once. Public institutions only, "
            "because in-state tuition is a public-sector concept."),
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
        "states": states,
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
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
