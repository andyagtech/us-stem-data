#!/usr/bin/env python3
"""J-1 academic exchange categories: the other uncapped route into a lab.

Every other route this project tracks is growing. J-1 research scholar --
which needs no cap, no labour condition application and no wage floor -- is
not. It is the counter-example, and it belongs beside the others for that
reason.

THE PARTIAL YEAR IS THE TRAP. The source carries CY2025 as data through
approximately March. Comparing 2015 with 2025 puts a full year against a
quarter and returns a 51% fall in research scholars; the real fall to the
last COMPLETE year is 33%. This script refuses to compute a change into a
year marked partial, and publishes the partial figures separately.

2020 and 2021 are complete years but reflect the pandemic closure, so the
headline comparison runs to the latest complete year and the whole series is
published for anyone who wants to see the shape.

Source: BridgeUSA participants by calendar year of program begin date, via
data/h1b/national_visa_trends.json.

Usage:
  python3 scripts/build_j1_scholars.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "h1b" / "national_visa_trends.json"
OUT = ROOT / "data" / "h1b" / "j1_scholars.json"

ACADEMIC = ("research_scholar", "professor", "short_term_scholar", "specialist")
LABELS = {"research_scholar": "Research scholar", "professor": "Professor",
          "short_term_scholar": "Short-term scholar", "specialist": "Specialist",
          "total": "All J-1 participants"}


def main() -> int:
    if not SRC.exists():
        print(f"  {SRC.relative_to(ROOT)} not found")
        return 1
    cat = json.loads(SRC.read_text()).get("j1_participants_by_category")
    if not cat:
        print("  no j1_participants_by_category in the source")
        return 1

    years = sorted(y for y in cat if y.isdigit())
    partial = {y for y in years
               if "partial" in str(cat[y].get("_note", "")).lower()}
    complete = [y for y in years if y not in partial]
    if not complete:
        print("  no complete year in the series")
        return 1
    first, last = complete[0], complete[-1]

    series = {y: {k: cat[y].get(k, 0) for k in ACADEMIC + ("total",)}
              for y in years}
    change = {k: {"from_year": int(first), "to_year": int(last),
                  "from": cat[first].get(k, 0), "to": cat[last].get(k, 0),
                  "pct": (round(100 * (cat[last].get(k, 0) / cat[first][k] - 1), 1)
                          if cat[first].get(k) else None)}
              for k in ACADEMIC + ("total",)}

    OUT.write_text(json.dumps({
        "_comment": ("J-1 academic exchange categories. The J-1 research scholar "
                     "route is uncapped and carries no labour condition "
                     "application or wage floor, which makes its decline the "
                     "counter-example to every other route in this project. "
                     "Changes are computed only between COMPLETE calendar years; "
                     "years marked partial are published but excluded from any "
                     "comparison, because measuring into one turns a 33% fall "
                     "into a 51% fall."),
        "source": "BridgeUSA participants by calendar year of program begin date",
        "complete_years": [int(y) for y in complete],
        "partial_years": [int(y) for y in sorted(partial)],
        "labels": LABELS,
        "series": series,
        "change_between_complete_years": change,
    }, indent=1) + "\n")

    print(f"  complete years {first}-{last}; partial: "
          f"{', '.join(sorted(partial)) or 'none'}")
    for k in ACADEMIC + ("total",):
        c = change[k]
        print(f"  {LABELS[k]:22} {c['from']:>8,} -> {c['to']:>8,}"
              + (f"  ({c['pct']:+.0f}%)" if c["pct"] is not None else ""))
    for y in sorted(partial):
        print(f"  [{y} partial, excluded] research scholar "
              f"{cat[y].get('research_scholar', 0):,}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
