#!/usr/bin/env python3
"""Rank cap-exempt sponsors from the source data, not from a reseller.

The commercial directories that rank "cap-exempt sponsors" are built from
two public federal datasets: DOL LCA disclosure files and the USCIS H-1B
Employer Data Hub. This project holds both. Their added value is the
CANDIDATE LIST -- which employers to treat as exempt -- and that has already
been collected, so the ranking can be produced here with the government's own
figures rather than a third party's.

The result is better than a scrape in one specific way: every number comes
from USCIS, and the inference (which employers are exempt) is separated from
the measurement (how much they file), so a reader can accept one and reject
the other.

STILL NOT A CAP-EXEMPT COUNT. USCIS records cap status on the I-129 and does
not publish it. This ranks petitions by employers a directory treats as
exempt. Some are certainly wrong in both directions.

Usage:
  python3 scripts/build_cap_exempt_sponsors.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import join_fellowship_employers as J  # noqa: E402

MERGED = ROOT / "data" / "cap_exempt" / "merged_employers.json"
OUT = ROOT / "data" / "cap_exempt" / "sponsor_ranking.json"
YEARS = (2021, 2022, 2023, 2024, 2025)


def main() -> int:
    if not MERGED.exists():
        print("  no merged_employers.json; run the merge first")
        return 1
    candidates = {}
    for e in json.loads(MERGED.read_text())["employers"]:
        k = J.norm(e["name"])
        if k:
            candidates.setdefault(k, e)

    hub = defaultdict(lambda: {"new": 0, "cont": 0, "concurrent": 0,
                               "naics": None, "state": None, "name": None,
                               "years": set()})
    for y in YEARS:
        p = ROOT / "data" / "h1b" / f"h1b_datahub_fy{y}.csv"
        if not p.exists():
            continue
        for row, L in J.hub_rows(p):
            nm = row[L["name"]].strip().strip('"')
            k = J.norm(nm)
            if k not in candidates:
                continue
            a = hub[k]
            a["new"] += J.num(row[L["new"]])
            a["cont"] += J.num(row[L["cont"]])
            if "concurrent" in L:
                a["concurrent"] += J.num(row[L["concurrent"]])
            a["naics"] = a["naics"] or (row[L["naics"]] or "").strip().strip('"')
            a["state"] = a["state"] or row[L["state"]]
            a["name"] = a["name"] or nm
            a["years"].add(y)

    rows = [{
        "employer": v["name"], "state": v["state"], "naics": v["naics"],
        "new_employment": v["new"], "continuation": v["cont"],
        "approvals": v["new"] + v["cont"], "concurrent": v["concurrent"],
        "years_present": sorted(v["years"]),
        "directory_source": candidates[k].get("source"),
    } for k, v in hub.items()]
    rows.sort(key=lambda r: -r["approvals"])

    total = sum(r["approvals"] for r in rows)
    OUT.write_text(json.dumps({
        "_comment": ("H-1B petitions approved for employers a public directory "
                     "treats as cap-exempt. The CANDIDATE LIST is a third "
                     "party's inference; every FIGURE is USCIS's own. This is "
                     "not a count of cap-exempt petitions: USCIS records cap "
                     "status on the I-129 and does not publish it."),
        "figures_from": "USCIS H-1B Employer Data Hub",
        "candidates_from": "merged public cap-exempt directories",
        "years": list(YEARS),
        "candidates": len(candidates),
        "matched_in_hub": len(rows),
        "total_approvals": total,
        "sponsors": rows,
    }, indent=1) + "\n")

    print(f"  {len(candidates):,} candidate employers; {len(rows):,} found in the hub")
    print(f"  approvals FY{YEARS[0]}-FY{YEARS[-1]}: {total:,}")
    print(f"  {'employer':44}{'approvals':>10}{'concurrent':>12}  st")
    for r in rows[:18]:
        print(f"  {r['employer'][:44]:44}{r['approvals']:>10,}{r['concurrent']:>12,}  {r['state']}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
