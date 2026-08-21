#!/usr/bin/env python3
"""Single-source the numbers that appear in prose, so they cannot drift.

THE PROBLEM. Counts get written into documentation by hand and then rot. As of
2026-08-20, before this script existed:

    pipeline/PIPELINE.md  said 101 university configs   (really 105)
    pipeline/PIPELINE.md  said 292 employer mappings    (really 296)
    README.md             said BOTH 101 and 105 in the same file

Nothing was wrong with the data. The prose describing it was wrong, and nothing
checked. Meanwhile the machine-readable layer -- pipeline/datasets.py -- was
clean, because it is used rather than read.

THE FIX is not to check the prose but to generate it. A documented number is
wrapped in a marker:

    The registry holds <!--auto:universities_count-->105<!--/auto--> universities.

`--write` refills every marker from the real files. `--check` exits non-zero if
any is stale, and is wired into scripts/test_site.py. Markers are HTML comments,
so rendered Markdown is unaffected.

This deliberately does NOT try to find undocumented numbers or judge prose. It
guarantees one thing completely: any number inside a marker is current. Numbers
outside a marker are unprotected -- wrap them to protect them.

Usage:
    python3 scripts/sync_docs.py --list           # every fact and its value
    python3 scripts/sync_docs.py --check          # exit 1 if any marker is stale
    python3 scripts/sync_docs.py --write          # refill markers in place
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files whose markers are managed. Adding a file here is safe: a file with no
# markers is simply left alone.
MANAGED = (
    "README.md",
    "pipeline/PIPELINE.md",
    "data/DATA_DICTIONARY.md",
    "HANDOFF.md",
)

MARKER = re.compile(r"(<!--auto:([a-z0-9_]+)-->)(.*?)(<!--/auto-->)", re.S)


def _json(path: str):
    return json.loads((ROOT / path).read_text())


def _catalog():
    sys.path.insert(0, str(ROOT))
    from pipeline.datasets import CATALOG, uncatalogued
    return CATALOG, uncatalogued()


def fact_universities_count() -> str:
    return f"{len(_json('pipeline/universities.json')):,}"


def fact_entity_map_count() -> str:
    return f"{len(_json('pipeline/entity_map.json')):,}"


def fact_dataset_count() -> str:
    return f"{len(_catalog()[0]):,}"


def fact_uncatalogued_scripts() -> str:
    return f"{len(_catalog()[1]):,}"


def fact_script_count() -> str:
    return f"{len(list((ROOT / 'scripts').glob('*.py'))):,}"


def fact_knowledge_files() -> str:
    return f"{len(list((ROOT / 'cloud' / 'chat' / 'knowledge').glob('*.md'))):,}"


def fact_site_checks() -> str:
    """How many assertions scripts/test_site.py makes -- counted by running it."""
    import subprocess
    r = subprocess.run([sys.executable, "scripts/test_site.py", "--offline"],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    m = re.search(r"(\d+)/(\d+) checks pass", r.stdout)
    return m.group(2) if m else "unknown"


FACTS = {name[5:]: fn for name, fn in sorted(globals().items())
         if name.startswith("fact_")}


def resolve(keys: set[str]) -> dict[str, str]:
    out = {}
    for k in sorted(keys):
        fn = FACTS.get(k)
        if fn is None:
            out[k] = None
            continue
        try:
            out[k] = str(fn())
        except Exception as exc:                       # noqa: BLE001
            out[k] = f"<error: {type(exc).__name__}>"
    return out


def scan() -> dict[Path, list[tuple[str, str]]]:
    """{path: [(key, current_text), ...]} for every managed file."""
    found = {}
    for rel in MANAGED:
        p = ROOT / rel
        if not p.exists():
            continue
        hits = [(m.group(2), m.group(3)) for m in MARKER.finditer(p.read_text())]
        if hits:
            found[p] = hits
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if not any((args.check, args.write, args.list)):
        args.list = True

    if args.list:
        vals = resolve(set(FACTS))
        print(f"{'fact':<28}value")
        for k, v in vals.items():
            print(f"  {k:<26}{v}")
        used = {k for hits in scan().values() for k, _ in hits}
        unused = sorted(set(FACTS) - used)
        if unused:
            print(f"\n  defined but not referenced in any managed file: "
                  f"{', '.join(unused)}")
        return 0

    found = scan()
    if not found:
        print("No <!--auto:...--> markers in any managed file. Nothing to do.")
        print("Wrap a number to protect it, e.g.:")
        print("    <!--auto:universities_count-->105<!--/auto-->")
        return 0

    wanted = {k for hits in found.values() for k, _ in hits}
    vals = resolve(wanted)

    stale, unknown = [], []
    for path, hits in found.items():
        for key, cur in hits:
            if vals.get(key) is None:
                unknown.append((path, key))
            elif cur != vals[key]:
                stale.append((path, key, cur, vals[key]))

    rel = lambda p: p.relative_to(ROOT)                 # noqa: E731
    for path, key in unknown:
        print(f"  UNKNOWN  {rel(path)}: no fact named '{key}'")
    for path, key, cur, want in stale:
        print(f"  STALE    {rel(path)}: {key} says {cur!r}, should be {want!r}")

    if args.check:
        if stale or unknown:
            print(f"\n{len(stale)} stale, {len(unknown)} unknown. "
                  f"Run: python3 scripts/sync_docs.py --write")
            return 1
        n = sum(len(h) for h in found.values())
        print(f"  all {n} marker(s) across {len(found)} file(s) are current")
        return 0

    if unknown:
        print("\nRefusing to write while a marker names an unknown fact.")
        return 1
    for path, hits in found.items():
        text = path.read_text()
        text = MARKER.sub(lambda m: m.group(1) + vals[m.group(2)] + m.group(4), text)
        path.write_text(text)
    print(f"\n  wrote {len(found)} file(s), {len(stale)} marker(s) updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
