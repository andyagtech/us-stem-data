#!/usr/bin/env python3
"""Do the foreign nationals trained here actually stay?

This project already held SED Table 2-8, which records what doctorate
recipients SAID they intended to do -- a survey answer given before
graduation. That is not retention. NCSES separately measures where those
people actually live years later, by matching them to administrative records,
and that is the number that closes the pipeline.

The distinction matters for the briefing: intentions can be quoted as though
they were outcomes, and they are not the same thing.

Source: NCSES, "Most U.S.-Trained Science and Engineering Doctorate
Recipients on Temporary Visas Remain in the United States" (NSF 25-325),
Table 1 -- residence of 2017-19 doctorate recipients as of 2023.

Usage:
  python3 scripts/build_stay_rates.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "stay_rates" / "nsf25325_tab001.xlsx"
OUT = ROOT / "site" / "data" / "stay_rates.json"


def main() -> int:
    if not SRC.exists():
        print(f"  {SRC.relative_to(ROOT)} not found")
        return 1
    import openpyxl
    ws = openpyxl.load_workbook(SRC).active
    rows = [[c for c in r] for r in ws.iter_rows(values_only=True)]

    title = next((str(r[0]) for r in rows if r[0] and "Residence" in str(r[0])), "")
    out = []
    for r in rows:
        if not r or not r[0] or not isinstance(r[0], str):
            continue
        vals = [v for v in r[1:] if isinstance(v, (int, float))]
        if len(vals) < 5:
            continue
        total, us_n, us_pct, non_n, non_pct = vals[:5]
        # The parts must account for the total, or a column has shifted.
        if abs((us_n + non_n) - total) > max(50, 0.01 * total):
            print(f"  skipped {r[0]!r}: {us_n:,.0f}+{non_n:,.0f} != {total:,.0f}")
            continue
        out.append({
            "origin": r[0].strip(),
            "doctorates": int(total),
            "in_us": int(us_n), "stay_rate_pct": round(float(us_pct), 1),
            "outside_us": int(non_n), "left_pct": round(float(non_pct), 1),
        })
    if not out:
        print("  no rows parsed")
        return 1

    total_row = next((r for r in out if r["origin"].lower() == "total"), None)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "_comment": ("Where temporary-visa doctorate recipients actually live "
                     "years after graduating -- measured, not intended. This "
                     "project separately holds SED Table 2-8, which records "
                     "what recipients SAID they planned to do before "
                     "graduating; the two must not be quoted "
                     "interchangeably."),
        "source": ("NCSES, Most U.S.-Trained Science and Engineering Doctorate "
                   "Recipients on Temporary Visas Remain in the United States "
                   "(NSF 25-325), Table 1"),
        "measure": title.strip(),
        "cohort": "2017-19 doctorate recipients, residence as of 2023",
        "overall": total_row,
        "by_origin": [r for r in out if r is not total_row],
    }, indent=1) + "\n")

    print(f"  {title.strip()[:70]}")
    if total_row:
        print(f"  overall: {total_row['in_us']:,} of {total_row['doctorates']:,} "
              f"still in the US ({total_row['stay_rate_pct']}%)")
    for r in out:
        if r is total_row:
            continue
        print(f"   {r['origin'][:28]:30} {r['doctorates']:>7,}  "
              f"{r['stay_rate_pct']:>5.1f}% stayed")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
