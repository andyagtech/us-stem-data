#!/usr/bin/env python3
"""Federal research dollars per doctorate, set against non-resident share.

WHY THIS EXISTS

"Taxpayers fund these programs" is the strongest claim this project can make,
and it was being asserted rather than quantified. This attaches a number: how
much federal money flows to an institution, how many research doctorates it
produces, and what share of those go to students on temporary visas.

The result is concrete in a way a percentage is not. The median institution
here receives on the order of three quarters of a million dollars in annual
federal obligations for every research doctorate it awards.

DOCTORAL AND MASTER'S ARE DIFFERENT MECHANISMS -- kept separate here

  Doctoral students in STEM are overwhelmingly funded: research assistantships
  on federal grants, teaching assistantships, and fellowships. Tuition is
  typically waived and a stipend paid. The public subsidy per student is large
  and mostly federal.

  Master's students in STEM are usually self-funded through tuition, with a
  minority holding teaching assistantships. The public subsidy per student is
  much smaller, and where it exists it runs through institutional and state
  channels more than federal grants.

Collapsing the two overstates the federal subsidy attached to master's degrees,
which is where the enrolment growth actually happened. This script reports
doctorates only, and says so.

WHAT THE PER-DOCTORATE FIGURE IS AND IS NOT

It is federal obligations to the institution divided by its research doctorates
-- an intensity ratio, not a cost of production. Federal obligations fund
research whose outputs include papers, instruments, facilities and staff, not
only degrees. A university with a large national lab has a high ratio for
reasons unrelated to graduate training.

So: a legitimate way to show where public research money and non-resident
doctoral output coincide. Not a defensible claim that taxpayers "paid $X for
that specific degree." Anyone quoting it the second way will be corrected by
anyone who works in research administration.

Usage:
    python3 scripts/build_taxpayer_cost.py
    python3 scripts/build_taxpayer_cost.py --out site/data/taxpayer_cost.json
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from atomic_write import write_json

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW   # noqa: E402
FED = ROOT / "data" / "federal_support" / "federal_support_by_university.json"
INDEX = ROOT / "data" / "ipeds" / "nra_index.csv.gz"
REGISTRY = ROOT / "pipeline" / "universities.json"
DEFAULT_OUT = ROOT / "site" / "data" / "taxpayer_cost.json"

NARROW_STEM = STEM_NARROW   # single source: pipeline/models.py.
# Seven scripts each carried their own copy of this set. They all happened
# to agree, which is exactly why the drift would have been silent: change
# models.py and the copies keep the old definition without a word.
YEAR_LO, YEAR_HI = 2015, 2022
WINDOW = YEAR_HI - YEAR_LO + 1
MIN_DOCTORATES = 100      # over the window; below this the ratio is unstable


def doctorate_counts():
    tot, nra = defaultdict(int), defaultdict(int)
    with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            year = int(row["year"])
            if not (YEAR_LO <= year <= YEAR_HI) or row["basis"] != "aw17":
                continue
            if row["cipcode"].split(".")[0].zfill(2) not in NARROW_STEM:
                continue
            tot[row["unitid"]] += int(row["total"])
            nra[row["unitid"]] += int(row["nra"])
    return tot, nra


def build():
    if not FED.exists() or not INDEX.exists():
        sys.exit("Need both federal_support_by_university.json and nra_index.csv.gz")
    blob = json.loads(FED.read_text())
    fed, meta = blob["universities"], blob.get("_metadata", {})
    registry = json.loads(REGISTRY.read_text())
    key_to_unitid = {k: str(v["unitid"]) for k, v in registry.items()
                     if v.get("unitid")}

    tot, nra = doctorate_counts()
    rows = []
    for key, entry in fed.items():
        uid = key_to_unitid.get(key)
        if not uid or tot.get(uid, 0) < MIN_DOCTORATES:
            continue
        obligations = entry.get("all_federal_obligations") or 0
        if obligations <= 0:
            continue
        doctorates = tot[uid]
        per_year = doctorates / WINDOW
        rows.append({
            "key": key,
            "institution": entry.get("source_name", key),
            "federal_obligations": obligations,
            "fiscal_year": entry.get("fiscal_year"),
            "doctorates": doctorates,
            "doctorates_per_year": round(per_year, 1),
            "nra": nra[uid],
            "share": round(100 * nra[uid] / doctorates, 1),
            "federal_per_doctorate": round(obligations / per_year),
        })
    rows.sort(key=lambda r: -r["share"])
    return rows, meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    rows, meta = build()
    if not rows:
        sys.exit("No institutions matched.")
    median = statistics.median(r["federal_per_doctorate"] for r in rows)

    payload = {
        "basis": {
            "funding_source": meta.get("source"),
            "funding_fiscal_year": meta.get("fiscal_year"),
            "doctorate_years": [YEAR_LO, YEAR_HI],
            "award_level": 17,
            "cip_families": sorted(NARROW_STEM),
            "min_doctorates": MIN_DOCTORATES,
        },
        "median_federal_per_doctorate": median,
        "level_note": (
            "Research doctorates only. Doctoral students in STEM are largely "
            "funded through federal research assistantships, teaching "
            "assistantships and fellowships, with tuition waived and a stipend "
            "paid. Master's students are usually self-funded through tuition, "
            "so the federal subsidy per master's degree is far smaller. The two "
            "are not combined here."),
        "caveat": (
            "This is an intensity ratio, not a cost of production. Federal "
            "obligations fund research whose outputs include papers, "
            "instruments, facilities and staff, not only degrees. It shows "
            "where public research money and non-resident doctoral output "
            "coincide; it does not establish that taxpayers paid a given sum "
            "for a given degree."),
        "count": len(rows),
        "institutions": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, payload, separators=(",", ":"))

    print(f"Federal obligations ({meta.get('fiscal_year')}) per STEM research "
          f"doctorate ({YEAR_LO}-{YEAR_HI})\n")
    print(f"{'NRA%':>6}{'fed $/doctorate':>18}{'obligations':>14}{'PhDs':>8}  institution")
    print("-" * 82)
    for r in rows[:args.top]:
        print(f"{r['share']:>5.1f}%{r['federal_per_doctorate']:>17,}"
              f"{r['federal_obligations'] / 1e6:>13,.0f}M{r['doctorates']:>8,}  "
              f"{r['institution'][:32]}")
    print(f"\n{len(rows)} institutions. Median federal obligations per STEM "
          f"research doctorate: ${median:,.0f}")
    print(f"\nwrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
