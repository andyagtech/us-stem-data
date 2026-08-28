#!/usr/bin/env python3
"""What a STEM degree pays, by field and credential level.

The briefing shows domestic doctorate conversion falling and says nothing
about why. The obvious candidate is money: someone with a STEM bachelor's
can take an industry job now or spend six years on a stipend. College
Scorecard reports median earnings and median debt by 4-digit CIP AND
credential level, which is the only federal source that lets that comparison
be made.

READ THE COMPARISON CAREFULLY. Earnings are measured one year after
completion, so a bachelor's cohort is around 23 and a doctoral cohort around
29. This is NOT the return to a doctorate: the bachelor's holder would have
six years of experience and earnings by the time the doctorate holder starts.
It is the narrower thing a graduate actually faces -- what each credential
pays at its own starting line.

Values are suppressed by the Department where a cell is small, so field
coverage varies by level and the counts are reported alongside.

Usage:
  python3 scripts/build_stem_earnings.py
"""
from __future__ import annotations

import csv
import io
import json
import statistics
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW  # noqa: E402

SRC = ROOT / "data" / "scorecard" / "field_of_study.zip"
OUT = ROOT / "site" / "data" / "stem_earnings.json"

LEVELS = {"3": "bachelors", "5": "masters", "6": "doctorate"}
EARN, DEBT = "EARN_MDN_HI_1YR", "DEBT_ALL_STGP_EVAL_MDN"


def rows():
    with zipfile.ZipFile(SRC) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(name) as fh:
            yield from csv.DictReader(
                io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace"))


def num(v):
    v = (v or "").strip()
    if not v or v in ("NULL", "PrivacySuppressed"):
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def main() -> int:
    if not SRC.exists():
        print(f"  {SRC.relative_to(ROOT)} not found")
        return 1
    fam = set(STEM_NARROW)
    by_level = defaultdict(list)
    by_field = defaultdict(lambda: defaultdict(list))
    names = {}

    for r in rows():
        lvl = LEVELS.get((r.get("CREDLEV") or "").strip())
        if not lvl:
            continue
        cip = (r.get("CIPCODE") or "").strip().zfill(4)
        fam2 = cip[:2]
        if fam2 not in fam:
            continue
        e = num(r.get(EARN))
        if e is None:
            continue
        by_level[lvl].append(e)
        cip4 = f"{cip[:2]}.{cip[2:]}"
        by_field[cip4][lvl].append(e)
        names.setdefault(cip4, (r.get("CIPDESC") or "").strip().strip('"'))

    if not by_level:
        print("  no rows matched; check the CIP or credential coding")
        return 1

    # The pooled medians are NOT comparable across levels. Suppression leaves
    # 208 doctoral programmes against 7,121 bachelor's, and they are a
    # different mix of fields, so the pooled doctoral figure coming out below
    # the pooled master's is composition, not a pay gap: only 3 of 27 fields
    # show that within the same field. Same-field comparison is the honest one.
    levels = {k: {"programmes": len(v), "median_earnings": int(statistics.median(v)),
                  "caution": ("pooled across a different mix of fields at each "
                              "level; compare within a field, not between these")}
              for k, v in by_level.items()}

    fields = []
    for cip, per in by_field.items():
        if not all(k in per for k in ("bachelors", "doctorate")):
            continue
        b = int(statistics.median(per["bachelors"]))
        d = int(statistics.median(per["doctorate"]))
        m = int(statistics.median(per["masters"])) if per.get("masters") else None
        fields.append({
            "cip": cip, "name": names.get(cip, cip),
            "bachelors": b, "masters": m, "doctorate": d,
            "n_bachelors": len(per["bachelors"]), "n_doctorate": len(per["doctorate"]),
            "doctorate_premium_pct": round(100 * (d / b - 1), 1),
        })
    fields.sort(key=lambda f: f["doctorate_premium_pct"])
    same_field = [f for f in fields if f["masters"]]
    doc_below_masters = [f["name"] for f in same_field if f["doctorate"] < f["masters"]]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "_comment": ("Median earnings one year after completion, by field and "
                     "credential level. NOT a return to the degree: a "
                     "bachelor's cohort is measured at about 23 and a doctoral "
                     "cohort at about 29, and the bachelor's holder would have "
                     "six years of earnings by then. It is what each credential "
                     "pays at its own starting line. Cells are suppressed where "
                     "small, so coverage differs by level."),
        "source": "U.S. Department of Education, College Scorecard, field of study file",
        "measure": "EARN_MDN_HI_1YR, median earnings one year after completion",
        "levels": levels,
        "fields_compared": len(fields),
        "median_doctorate_premium_over_bachelors_pct":
            round(statistics.median([f["doctorate_premium_pct"] for f in fields]), 1),
        "fields_where_doctorate_pays_below_masters": doc_below_masters,
        "fields_with_both_masters_and_doctorate": len(same_field),
        "fields": fields,
    }, indent=1) + "\n")

    print("  median earnings one year out, core-STEM programmes")
    for k in ("bachelors", "masters", "doctorate"):
        if k in levels:
            v = levels[k]
            print(f"   {k:11} ${v['median_earnings']:>7,}   ({v['programmes']:,} programmes)")
    print(f"  fields with both bachelor's and doctorate: {len(fields)}")
    print(f"  {'field':42}{'bach':>9}{'doct':>9}{'premium':>9}")
    for f in fields[:6]:
        print(f"  {f['name'][:42]:42}${f['bachelors']:>8,}${f['doctorate']:>8,}"
              f"{f['doctorate_premium_pct']:>8.0f}%")
    print("   ...")
    for f in fields[-3:]:
        print(f"  {f['name'][:42]:42}${f['bachelors']:>8,}${f['doctorate']:>8,}"
              f"{f['doctorate_premium_pct']:>8.0f}%")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
