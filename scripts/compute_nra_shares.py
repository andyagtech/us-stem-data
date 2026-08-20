#!/usr/bin/env python3
"""Recompute each university's headline NRA share from IPEDS completions.

The stored figures came from scripts/archive/ipeds_nra_asian_ranking.py and
then drifted: 37 of 103 checked universities were out by more than 5 points,
in both directions and by as much as 32. Michigan State was published at
16.7% against an IPEDS figure of 49.0%. MIT reproduced exactly and Missouri
S&T to within 1.1 points, so the method was never wrong — most of the values
simply did not come from it.

THE PINNED BASIS, all three parts of which matter:

  fields       CIP 2-digit families 11, 14, 15, 26, 27, 30, 40, 42.
               Note the codebase carries a SECOND, broader STEM set in
               scripts/enrich_university_json.py (16 families, including
               health, agriculture and social sciences) which drives the
               completions chart. The two disagree by about a point. This
               narrow set is the one the headline figure has always used.

  years        2015-2022 inclusive. The source script's header claims
               2015-2024, but C2023_A.csv and later carry a UTF-8 BOM on the
               UNITID column, so row.get("UNITID") returned None for those
               files and its range(2015, 2025) silently harvested 2015-2022.
               Two anchors confirm the window: Mines 39.76% against a stored
               39.8%, Binghamton 56.89% against 56.9%. No other window fits
               both.

  award level  17 (research/scholarship doctorate) from 2010, legacy 9 before
               it. Never both in one year: 2008 and 2009 carry both codings
               across different institutions, so summing double-counts. Level
               9 is not equivalent to 17 — it was split in 2010 into 17 and 18
               (professional practice) — but the window here starts in 2015,
               so only level 17 is ever read.

Usage:
    python3 scripts/compute_nra_shares.py --report     # show drift, change nothing
    python3 scripts/compute_nra_shares.py --write      # update the configs
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "ipeds" / "nra_index.csv.gz"
REGISTRY = ROOT / "pipeline" / "universities.json"
CONFIGS_PY = ROOT / "scripts" / "generate_name_lists.py"

STEM_CIP2 = {"11", "14", "15", "26", "27", "30", "40", "42"}
YEAR_LO, YEAR_HI = 2015, 2022


def basis_for(year: int) -> str:
    """One award-level basis per year; never both.

    Delegates to pipeline.models.award_level_basis so this rule lives in one
    place. It was previously re-derived in at least three files, which is how
    two STEM definitions came to coexist and disagree by up to 17 points.
    """
    try:
        import sys as _s
        _s.path.insert(0, str(ROOT))
        from pipeline.models import award_level_basis
        return award_level_basis(year)
    except Exception:
        return "aw17" if year >= 2010 else "aw09"


def compute() -> dict[str, tuple[int, int, float]]:
    """unitid -> (doctorates, nra, share_pct) on the pinned basis."""
    totals: dict[str, list[int]] = {}
    with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            year = int(row["year"])
            if year < YEAR_LO or year > YEAR_HI:
                continue
            if row["basis"] != basis_for(year):
                continue
            if row["cipcode"].split(".")[0].zfill(2) not in STEM_CIP2:
                continue
            slot = totals.setdefault(row["unitid"], [0, 0])
            slot[0] += int(row["total"])
            slot[1] += int(row["nra"])
    return {u: (t, n, (100.0 * n / t) if t else 0.0) for u, (t, n) in totals.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="Update the configs")
    ap.add_argument("--report", action="store_true", help="Show drift only")
    ap.add_argument("--threshold", type=float, default=5.0,
                    help="Report universities differing by more than this many points")
    args = ap.parse_args()
    if not (args.write or args.report):
        args.report = True

    by_unitid = compute()
    registry = json.loads(REGISTRY.read_text())

    changes, unresolved = [], []
    for key, entry in registry.items():
        uid = entry.get("unitid")
        if not uid or str(uid) not in by_unitid:
            unresolved.append(key)
            continue
        doctorates, nra, share = by_unitid[str(uid)]
        if doctorates == 0:
            unresolved.append(key)
            continue
        stored = entry.get("nra")
        changes.append((key, stored, round(share, 1), doctorates, nra))

    big = [c for c in changes if c[1] is None or abs(c[1] - c[2]) > args.threshold]
    big.sort(key=lambda c: -(abs((c[1] or 0) - c[2])))

    print(f"basis: CIP {sorted(STEM_CIP2)}, {YEAR_LO}-{YEAR_HI}, award level 17")
    print(f"{len(changes)} universities computed, {len(unresolved)} unresolved")
    print(f"{len(big)} differ from the stored value by more than {args.threshold} points\n")
    print(f"{'university':<18}{'stored':>9}{'computed':>10}{'delta':>8}{'doctorates':>12}")
    for key, stored, share, doctorates, _nra in big:
        s = f"{stored:.1f}%" if stored is not None else "none"
        d = f"{share - stored:+.1f}" if stored is not None else "n/a"
        print(f"{key:<18}{s:>9}{share:>9.1f}%{d:>8}{doctorates:>12,}")
    if unresolved:
        print(f"\nunresolved (kept as-is): {', '.join(sorted(unresolved))}")

    if not args.write:
        print("\nNo files written. Re-run with --write to apply.")
        return 0

    # 1. registry
    for key, _stored, share, doctorates, nra in changes:
        registry[key]["nra"] = share
        registry[key]["nra_basis"] = {
            "source": "IPEDS Completions via data/ipeds/nra_index.csv.gz",
            "cip2_families": sorted(STEM_CIP2),
            "years": [YEAR_LO, YEAR_HI],
            "award_level": 17,
            "doctorates": doctorates,
            "nra": nra,
        }
    REGISTRY.write_text(json.dumps(registry, indent=2, ensure_ascii=False))

    # 2. the CONFIGS literal, which is a separate copy of the same number
    src = CONFIGS_PY.read_text()
    applied = 0
    for key, _stored, share, _d, _n in changes:
        pattern = re.compile(
            r"(\'key\':\s*\'" + re.escape(key) + r"\',.*?\'nra\':\s*)([0-9.]+)",
            re.DOTALL)

        def _sub(m, v=share):
            return f"{m.group(1)}{v}"

        # count=0: several universities are assembled from more than one
        # CONFIGS entry (a PhD config plus an MS config sharing a key), and
        # every copy carries its own nra. Updating only the first leaves the
        # rest stale and the two files disagreeing.
        src, n = pattern.subn(_sub, src, count=0)
        applied += n
    CONFIGS_PY.write_text(src)
    print(f"\nWrote {REGISTRY.relative_to(ROOT)} ({len(changes)} entries)")
    print(f"Wrote {CONFIGS_PY.relative_to(ROOT)} ({applied} CONFIGS entries updated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
