#!/usr/bin/env python3
"""Where to look, for the sectors that carry a federal access regime.

THE DEPARTMENT-NAME RANKING WAS BLIND HERE. rank_search_targets.py reads
the department strings the dissertation harvest recorded, and on those
strings nothing from aerospace, nuclear, semiconductors, petroleum or
mining reached its top thirty. Not because those fields are balanced --
petroleum is 85.3% non-resident at doctorate level -- but because the
harvest files them under names the matcher does not recognize, or the
departments fall under its size floor.

So this ranks from the CIP codes instead. critical_industries.json already
maps each sector to its IPEDS field codes and publishes the institutions
awarding those doctorates with their non-resident share. That is a census,
not a sample, and it does not depend on how a university chose to name its
department.

ORDERED BY WHAT THE WORK REQUIRES, NOT BY SIZE. A sector where the job
needs export-control eligibility or access authorization ranks above one
where it does not, because that is where the composition question has a
concrete federal consequence rather than a general one.

Usage:
  python3 scripts/rank_security_targets.py
  python3 scripts/rank_security_targets.py --sector aerospace
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

SRC = ROOT / "site" / "data" / "critical_industries.json"
OUT = ROOT / "data" / "labs" / "security_targets.json"

#: What the federal regime means for who can do the work. Taken from the
#: dataset's own restriction field, ranked.
REGIME_RANK = {"Access authorization": 3, "Export control": 2, None: 0}

#: Where a department of this kind keeps its people page. Tried in order
#: against the institution's domain; the harvester follows what responds.
PATH_HINTS = [
    "/people", "/people/", "/directory", "/faculty", "/people/faculty",
    "/people/graduate-students", "/grad-students", "/students",
    "/research/labs", "/labs", "/our-people",
]

MIN_DOCTORATES = 25


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sector")
    ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args()

    ci = json.loads(SRC.read_text())
    rows = []
    for ind in ci["industries"]:
        if a.sector and ind["slug"] != a.sector:
            continue
        regime = ind.get("restriction")
        for s in ind.get("top_schools") or []:
            if (s.get("doctorates") or 0) < MIN_DOCTORATES:
                continue
            rows.append({
                "sector": ind["slug"],
                "sector_name": ind["name"],
                "restriction": regime,
                "restriction_note": ind.get("restriction_note", "")[:200],
                "cips": ind.get("cips"),
                "institution": s["name"],
                "unitid": s.get("unitid"),
                "doctorates": s["doctorates"],
                "nra": s.get("nra"),
                "nra_share": s.get("share"),
                #: Regime first, then concentration, then volume. A
                #: nuclear program at 36% matters more for this question
                #: than a computing program at 65%, because the work
                #: itself is gated.
                "priority": round(
                    REGIME_RANK.get(regime, 0) * 40
                    + (s.get("share") or 0)
                    + min((s.get("doctorates") or 0) / 20, 12), 1),
                "path_hints": PATH_HINTS,
            })

    rows.sort(key=lambda r: -r["priority"])
    payload = {
        "built_from": "site/data/critical_industries.json (IPEDS CIP codes)",
        "why": ("Ranked from field codes rather than department names, "
                "because the name-based ranking could not see the sectors "
                "that carry an access regime."),
        "min_doctorates": MIN_DOCTORATES,
        "count": len(rows),
        "targets": rows,
    }
    write_text(OUT, json.dumps(payload, indent=2))

    print(f"  {len(rows)} sector-institution targets\n")
    print(f"  {'sector':<11}{'regime':<22}{'institution':<42}{'docs':>5}{'nra%':>7}")
    shown = 0
    for sec in sorted({r["sector"] for r in rows},
                      key=lambda s: -max(r["priority"] for r in rows
                                         if r["sector"] == s)):
        for r in [x for x in rows if x["sector"] == sec][:a.top]:
            print(f"  {r['sector']:<11}{(r['restriction'] or '-'):<22}"
                  f"{r['institution'][:41]:<42}{r['doctorates']:>5}"
                  f"{r['nra_share']:>7}")
            shown += 1
        print()
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
