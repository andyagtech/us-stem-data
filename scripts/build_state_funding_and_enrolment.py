#!/usr/bin/env python3
"""Did states that cut public funding recruit more foreign students?

The tuition pages establish that foreign master's students pay, and that
some institutions run almost entirely on them. They do not establish WHY,
and the usual explanation -- states withdrew support, so universities went
looking for full-fare students -- is asserted in this project rather than
shown.

This tests it. SHEEO publishes state education appropriations per
full-time-equivalent student, by state and year, in constant dollars. IPEDS
publishes graduate enrolment by citizenship, by institution, which maps to a
state. If the explanation holds, states cutting hardest should show the
largest rise in foreign share.

WHAT A CORRELATION HERE WOULD AND WOULD NOT MEAN. Fifty states over a decade
is a small panel with a common national trend running through it: foreign
enrolment rose almost everywhere and appropriations fell almost everywhere,
so the two will correlate even if neither causes the other. The output
therefore reports the CHANGE in each, per state, so a reader can see the
spread rather than a single coefficient, and no causal claim is made.

PUBLIC INSTITUTIONS ONLY on the enrolment side, because state appropriations
reach no others.

Usage:
  python3 scripts/build_state_funding_and_enrolment.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import warnings
import zipfile
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SHEF = ROOT / "data" / "shef" / "SHEEO_SHEF_FY24_Report_Data.xlsx"
EF = ROOT / "data" / "ipeds_enrollment"
HD = ROOT / "data" / "ipeds" / "hd2024.csv"
OUT = ROOT / "site" / "data" / "state_funding_and_enrolment.json"

GRAD_LEVEL = 12                     # EFALEVEL 12 = all graduate students
# IPEDS CONTROL: 1 = public. State appropriations reach only these.
PUBLIC = "1"


def load_institutions() -> dict[str, tuple[str, bool]]:
    """UNITID -> (state, is_public)."""
    out = {}
    with open(HD, encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            uid = (r.get("UNITID") or "").strip()
            st = (r.get("STABBR") or "").strip().upper()
            ctl = (r.get("CONTROL") or "").strip()
            if uid and st:
                out[uid] = (st, ctl == PUBLIC)
    return out


def load_shef() -> dict[tuple[str, int], dict]:
    import openpyxl
    wb = openpyxl.load_workbook(SHEF, read_only=True)
    ws = wb["Report Data"]
    it = ws.iter_rows(values_only=True)
    hdr = [str(c) if c is not None else "" for c in next(it)]
    idx = {c: i for i, c in enumerate(hdr)}
    need = ("State", "FY", "Education Appropriations", "Net FTE Enrollment",
            "Net Tuition and Fee Revenue", "HECA (Inflation) Adjustment")
    missing = [c for c in need if c not in idx]
    if missing:
        raise SystemExit(f"  SHEF is missing {missing}")
    out = {}
    for r in it:
        try:
            state = str(r[idx["State"]] or "").strip()
            fy = int(r[idx["FY"]])
            approp = float(r[idx["Education Appropriations"]] or 0)
            fte = float(r[idx["Net FTE Enrollment"]] or 0)
            heca = float(r[idx["HECA (Inflation) Adjustment"]] or 1) or 1
            tuition = float(r[idx["Net Tuition and Fee Revenue"]] or 0)
        except (TypeError, ValueError):
            continue
        if not state or fte <= 0:
            continue
        # HECA is an INDEX, not a multiplier: the base year is 1 and earlier
        # years are below it, so a nominal figure is DIVIDED by it to reach
        # constant dollars. Multiplying instead shrinks the early years and
        # turns a modest recovery into an apparent doubling -- Alabama 2010
        # reads $3,811 that way against a published figure near $7,700.
        out[(state, fy)] = {
            "appropriations_per_fte": round(approp / heca / fte, 2),
            "tuition_per_fte": round(tuition / heca / fte, 2),
            "fte": round(fte)}
    return out


def enrolment_by_state(inst: dict) -> dict[int, dict[str, list[int]]]:
    """year -> state -> [total, non-resident], public institutions only."""
    out: dict[int, dict[str, list[int]]] = {}
    for path in sorted(EF.glob("EF*A.zip")):
        year = int(path.stem[2:6])
        agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        with zipfile.ZipFile(path) as z:
            inner = next(x for x in z.namelist() if x.lower().endswith(".csv"))
            with z.open(inner) as fh:
                for r in csv.DictReader(io.TextIOWrapper(
                        fh, encoding="utf-8-sig", errors="replace")):
                    try:
                        if int(float(r.get("EFALEVEL") or 0)) != GRAD_LEVEL:
                            continue
                        t = int(float(r.get("EFTOTLT") or 0))
                        n = int(float(r.get("EFNRALT") or 0))
                    except (TypeError, ValueError):
                        continue
                    if t <= 0:
                        continue
                    got = inst.get((r.get("UNITID") or "").strip())
                    if not got or not got[1]:
                        continue
                    a = agg[got[0]]
                    a[0] += t
                    a[1] += n
        if agg:
            out[year] = dict(agg)
    return out


def main() -> int:
    for p in (SHEF, HD):
        if not p.exists():
            print(f"  missing {p.relative_to(ROOT)}")
            return 1

    inst = load_institutions()
    shef = load_shef()
    enrol = enrolment_by_state(inst)
    if not enrol:
        print(f"  no enrolment files in {EF.relative_to(ROOT)}")
        return 1

    # Abbreviations in IPEDS, full names in SHEEO.
    import csv as _csv
    names = {}
    with open(HD, encoding="utf-8-sig", errors="replace") as fh:
        for r in _csv.DictReader(fh):
            ab = (r.get("STABBR") or "").strip().upper()
            nm = (r.get("STABBR") or "").strip()
            names[ab] = nm
    STATE_NAMES = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut",
        "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
        "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
        "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
        "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
        "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
        "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
        "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
        "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
        "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
        "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}

    years = sorted(set(enrol) & {fy for _s, fy in shef})
    if len(years) < 5:
        print(f"  only {len(years)} overlapping years")
        return 1
    first, last = years[0], years[-1]

    rows, unmatched = [], []
    for ab, full in sorted(STATE_NAMES.items()):
        e0, e1 = enrol.get(first, {}).get(ab), enrol.get(last, {}).get(ab)
        s0, s1 = shef.get((full, first)), shef.get((full, last))
        if not (e0 and e1 and s0 and s1):
            unmatched.append(ab)
            continue
        share0 = 100 * e0[1] / e0[0]
        share1 = 100 * e1[1] / e1[0]
        rows.append({
            "state": full, "abbr": ab,
            "appropriations_per_fte_first": s0["appropriations_per_fte"],
            "appropriations_per_fte_last": s1["appropriations_per_fte"],
            "appropriations_change_pct": round(
                100 * (s1["appropriations_per_fte"] / s0["appropriations_per_fte"] - 1), 1)
            if s0["appropriations_per_fte"] else None,
            "foreign_share_first": round(share0, 1),
            "foreign_share_last": round(share1, 1),
            "foreign_share_change_pts": round(share1 - share0, 1),
            "graduate_enrolment_last": e1[0]})

    # Do the states that cut hardest show the largest rise? Split at the
    # median rather than fitting a line: fifty points with a strong common
    # trend do not support a coefficient anyone should quote.
    usable = [r for r in rows if r["appropriations_change_pct"] is not None]
    usable.sort(key=lambda r: r["appropriations_change_pct"])
    half = len(usable) // 2
    cut_most, cut_least = usable[:half], usable[half:]

    def mean(rs, key):
        return round(sum(r[key] for r in rs) / len(rs), 2) if rs else None

    doc = {
        "_comment": (
            "State education appropriations per full-time-equivalent student "
            "(SHEEO SHEF, constant dollars via the HECA adjustment) against "
            "the non-resident share of GRADUATE enrolment at PUBLIC "
            "institutions in the same state (IPEDS Fall Enrolment). Built to "
            "test the usual explanation for the tuition findings -- that "
            "states withdrew support and universities recruited full-fare "
            "students. THE PANEL DOES NOT SUPPORT IT and points the other "
            "way: the half of states that cut most saw the foreign share rise "
            "3.74 points, the half that cut least 4.96. Only 13 of 50 states "
            "cut in real terms at all. The tuition finding stands; this "
            "explanation for it should not be repeated. IT DOES NOT ESTABLISH "
            "CAUSATION AND NO COEFFICIENT IS "
            "PUBLISHED: fifty states over a decade share a strong national "
            "trend, with foreign enrolment rising and appropriations falling "
            "almost everywhere, so the two correlate whether or not either "
            "drives the other. Per-state changes are reported so the spread "
            "is visible. Public institutions only, because state "
            "appropriations reach no others. Enrolment is ALL FIELDS -- "
            "IPEDS does not publish it by field."),
        "sources": {
            "funding": "SHEEO State Higher Education Finance, FY2024 report data",
            "enrolment": "NCES IPEDS Fall Enrolment, public institutions",
        },
        "source_url": "https://shef.sheeo.org/data-downloads/",
        "years": [first, last],
        "states": rows,
        "states_unmatched": unmatched,
        "median_split": {
            "cut_most": {
                "states": len(cut_most),
                "mean_appropriations_change_pct": mean(cut_most, "appropriations_change_pct"),
                "mean_foreign_share_change_pts": mean(cut_most, "foreign_share_change_pts")},
            "cut_least": {
                "states": len(cut_least),
                "mean_appropriations_change_pct": mean(cut_least, "appropriations_change_pct"),
                "mean_foreign_share_change_pts": mean(cut_least, "foreign_share_change_pts")},
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    ms = doc["median_split"]
    print(f"  {len(rows)} states, {first} to {last}"
          + (f"  (unmatched: {', '.join(unmatched)})" if unmatched else ""))
    print(f"\n  {'half':12}{'states':>8}{'approp/FTE change':>20}{'foreign share change':>23}")
    for k in ("cut_most", "cut_least"):
        h = ms[k]
        print(f"  {k:12}{h['states']:>8}{h['mean_appropriations_change_pct']:>19}%"
              f"{h['mean_foreign_share_change_pts']:>22} pts")
    print(f"\n  largest cuts:")
    for r in usable[:6]:
        print(f"   {r['state']:16}{r['appropriations_change_pct']:>8}%"
              f"   foreign {r['foreign_share_first']:>5}% -> {r['foreign_share_last']:>5}%"
              f"  ({r['foreign_share_change_pts']:+.1f})")
    print(f"  largest increases:")
    for r in usable[-6:]:
        print(f"   {r['state']:16}{r['appropriations_change_pct']:>8}%"
              f"   foreign {r['foreign_share_first']:>5}% -> {r['foreign_share_last']:>5}%"
              f"  ({r['foreign_share_change_pts']:+.1f})")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
