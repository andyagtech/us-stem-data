#!/usr/bin/env python3
"""Record, per university, how much of its corpus carries a degree level.

Degree level (phd / masters) is read from each repository's OAI feed. Only
seven repositories have a hand-picked metadata prefix that exposes it, so
coverage varies enormously between universities -- and nothing on the site said
so. Montana State labels 24.3% of its records; a reader comparing its
master's/doctoral split against a university at 99% would be comparing a
near-complete count with a quarter of one.

This is a SOURCE LIMITATION, not a defect: the feeds for the remainder do not
publish degree level at all. Three full repository walks of gmu, uoregon and
cmu returned zero additional records. So the fix is to label it, not to chase
it.

Writes `degree_label_coverage` into each university's site JSON and into
pipeline/universities.json, as a number rather than prose so a check can assert
on it and the front end can render it.

Usage:
    python3 scripts/label_degree_coverage.py --report
    python3 scripts/label_degree_coverage.py --write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_write import write_json                     # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "pipeline" / "universities.json"
LEVEL_IDX = 7
LABELS = {"phd", "masters", "master", "ms", "ma", "mfa", "med", "meng"}


def coverage(records: list) -> tuple[int, int]:
    labelled = sum(1 for r in records
                   if len(r) > LEVEL_IDX
                   and str(r[LEVEL_IDX] or "").strip().lower() in LABELS)
    return labelled, len(records)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--floor", type=float, default=50.0,
                    help="Flag universities below this percent. Default 50.")
    args = ap.parse_args()
    if not (args.write or args.report):
        args.report = True

    registry = json.loads(REGISTRY.read_text())
    rows = []
    for mode in ("stem", "nonstem"):
        for path in sorted((ROOT / "site" / "data" / mode).glob("*.json")):
            if path.name.startswith("_"):
                continue
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            labelled, total = coverage(data.get("records", []))
            if not total:
                continue
            pct = round(100.0 * labelled / total, 1)
            rows.append((path.stem, mode, labelled, total, pct, path, data))

    rows.sort(key=lambda r: r[4])
    low = [r for r in rows if r[4] < args.floor]

    print(f"{'university':<22}{'mode':<10}{'labelled':>10}{'of':>10}{'pct':>8}")
    for key, mode, lab, tot, pct, _p, _d in rows[:14]:
        print(f"  {key:<20}{mode:<10}{lab:>10,}{tot:>10,}{pct:>7.1f}%")
    print(f"\n  {len(rows)} corpora; {len(low)} below {args.floor:.0f}% "
          f"degree-level coverage")

    if not args.write:
        print("\nNo files written. Re-run with --write.")
        return 0

    for key, mode, lab, tot, pct, path, data in rows:
        data["degree_label_coverage"] = {
            "labelled": lab, "records": tot, "percent": pct,
            "note": ("Degree level comes from the institution's OAI feed. Where "
                     "coverage is low the feed does not publish it; this is a "
                     "source limitation, not a gap in processing. Master's and "
                     "doctoral splits for this institution cover only the "
                     "labelled share."),
        }
        write_json(path, data, separators=(",", ":"))
        if key in registry:
            # A university has up to two corpora (stem and nonstem) with
            # different coverage. Storing a single number let the last one
            # written win, which -- because rows are sorted ascending -- meant
            # the HIGHER figure survived and the registry flattered the
            # institution. Keep both, and a worst-case for anything that wants
            # one number.
            slot = registry[key].setdefault("degree_label_coverage", {})
            if not isinstance(slot, dict):
                slot = {}
                registry[key]["degree_label_coverage"] = slot
            slot[mode] = pct
            slot["worst"] = min(v for k, v in slot.items() if k != "worst")
    write_json(REGISTRY, registry, indent=2)
    print(f"\n  wrote {len(rows)} site JSONs and the registry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
