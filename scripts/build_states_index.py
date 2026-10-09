#!/usr/bin/env python3
"""The state list the sidebar expands, from the pages that actually exist.

The rail offers "Show states" under All State Profiles. It needs the list,
and the list has to agree with the pages on disk: an entry for a state with
no page is a link to a 404, and a page with no entry is a page nobody can
reach from the rail.

So the index is built from the intersection -- a declared state that has a
rendered page -- rather than from the declaration alone.

Usage:
    python3 scripts/build_states_index.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data" / "states_index.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                          # noqa: E402
from build_state_pages import NAMES, PUBLISH                 # noqa: E402


def main() -> int:
    pages = ROOT / "site" / "states"
    rows = [{"key": a.lower(), "abbr": a, "name": NAMES[a]}
            for a in PUBLISH if (pages / f"{a.lower()}.html").exists()]
    rows.sort(key=lambda r: r["name"])
    if not rows:
        print("ERROR: no state pages found. Run build_state_pages.py first.")
        return 1
    missing = [a for a in PUBLISH if not (pages / f"{a.lower()}.html").exists()]
    write_text(OUT, json.dumps({"states": rows}, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} states")
    if missing:
        print(f"  {len(missing)} declared but not rendered: "
              f"{', '.join(missing[:8])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
