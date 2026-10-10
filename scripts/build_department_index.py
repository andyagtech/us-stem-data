#!/usr/bin/env python3
"""A complete university x department index for the dissertation record.

WHY. search_targets.json is a RANKING, cut at the top 400, so looking a
department up in it silently fails for everything below the cut --
University of Houston's industrial engineering programme is not in it,
and that is the programme with the highest non-resident share on the
whole site. Any link built from the ranking is therefore missing exactly
the cases worth linking to.

This is the whole list instead: every university slug, every department
name it awards under, and how many records this site holds. Small
enough to load in a builder, complete enough that a lookup which finds
nothing means the department genuinely is not in the corpus.

Usage:
  python3 scripts/build_department_index.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

OUT = ROOT / "data" / "labs" / "department_index.json"


def main() -> int:
    idx: dict = defaultdict(lambda: defaultdict(int))
    names: dict = {}
    for track in ("stem", "nonstem"):
        d = ROOT / "site" / "data" / track
        if not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            if f.name.startswith("_"):
                continue
            b = json.loads(f.read_text())
            slug = f.stem
            names[slug] = b.get("name") or slug
            for r in b.get("records") or []:
                if isinstance(r, list) and r and isinstance(r[0], str):
                    idx[slug][r[0].strip()] += 1

    payload = {
        "built_from": "site/data/stem/*.json and site/data/nonstem/*.json",
        "why": ("The complete university x department list. The ranked "
                "search targets are cut at 400 rows, so a lookup against "
                "them fails for most departments and gives no sign that "
                "it has."),
        "universities": len(idx),
        "departments": sum(len(v) for v in idx.values()),
        "names": names,
        "index": {k: dict(sorted(v.items(), key=lambda kv: -kv[1]))
                  for k, v in sorted(idx.items())},
    }
    write_text(OUT, json.dumps(payload, indent=1))
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {payload['universities']} universities, "
          f"{payload['departments']} university-department pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
