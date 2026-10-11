#!/usr/bin/env python3
"""Every figure in the knowledge base must be findable in the data behind it.

WHAT THIS CATCHES that nothing else does. The assistant answers from prose in
cloud/chat/knowledge/*.md, and a number typed into prose has no link back to
the dataset it came from. It can be mistyped, left over from an older build, or
invented. knowledge_figures.py pins 73 figures exactly, by re-deriving each one
-- but the knowledge base states about 1,300, and writing 1,300 resolvers by
hand would add 1,300 more things that can be wrong.

So this proves the cheaper, broader property: the number EXISTS in a dataset
the file draws on. It does not prove the number is current -- that is what
knowledge_figures.py is for -- but an untraceable figure is a different and
worse problem, and this is the only thing that looks for it. On its first run
it found a pair of enrolment counts quoted for 2008 that match no dataset in
the repo, and an arithmetic error stated as the point of its own file.

A RATCHET, NOT A GATE. Clearing 490 untraceable figures is a long job, and a
check that fails for weeks gets ignored or switched off. So this records a
baseline and fails only when the count goes UP. New prose must carry its
provenance from the day it is written; the backlog comes down when someone has
time. Lower the baseline whenever it drops -- the script prints the command.

Usage:
    python3 scripts/check_kb_provenance.py              # report and ratchet
    python3 scripts/check_kb_provenance.py --verbose    # name every figure
    python3 scripts/check_kb_provenance.py --accept     # pin a lower baseline
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "cloud" / "chat" / "knowledge"
DATA = ROOT / "site" / "data"
BASELINE = ROOT / "cloud" / "chat" / "kb_provenance_baseline.json"

sys.path.insert(0, str(ROOT / "cloud" / "chat"))
from knowledge_sources import EXTERNAL, sources_for          # noqa: E402

#: A figure: a thousands-separated number, a decimal, or a bare integer of two
#: digits or more. One-digit numbers are prose ("one in three") far more often
#: than they are data, and matching them buries the signal.
#: The trailing class must NOT exclude "%": excluding it made "32.7%" fail as a
#: decimal and match the bare "32" instead, so every percentage in the base was
#: checked against the wrong number and reported as untraceable.
#: Excluding "$" before the number was the same mistake in the other direction:
#: "$2,865,216" could not start at the "2", so it matched the fragment
#: "865,216" and reported a figure the data had never contained. A comma on
#: either side is the real boundary to refuse.
FIG = re.compile(r'(?<![\w.,-])(\d{1,3}(?:,\d{3})+|\d+\.\d+|\d{2,})(?![\w.,-])')
CITED = re.compile(r'/data/([a-z0-9_]+)\.json|`([a-z0-9_]+)\.json`')

#: Rounding slack. Prose rounds 123435007.03 to "$123,435,007" and may state a
#: share as 84.0 where the data holds 0.84 or 84.04.
REL_TOLERANCE = 0.0005
ABS_TOLERANCE = 0.051


def numbers(obj, out: set) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(float(obj))
        return
    if isinstance(obj, dict):
        for v in obj.values():
            numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            numbers(v, out)
    elif isinstance(obj, str):
        # Figures stored as strings ("85.3%", "1,234") still count as present.
        s = obj.replace(",", "").rstrip("%")
        try:
            out.add(float(s))
        except ValueError:
            pass


def dataset_values() -> dict[str, set]:
    """Every published dataset, plus the build inputs a file may declare.

    A figure can have real provenance without being published: the degree-label
    coverage table comes from pipeline/universities.json, which is an input to
    the build and never shipped. Treating that as "external" would be wrong --
    it is computed here, it is just not on the site -- so a file may declare it
    as "pipeline:universities" and the number is checked against it.
    """
    pools: dict[str, set] = {}
    #: The lab crawl is the same case as pipeline/: computed here, read
    #: by the directory builder at render time, and never shipped as a
    #: site dataset. Its figures are as traceable as any published one.
    for f in sorted((ROOT / "data" / "labs").glob("*.json")):
        try:
            vals: set = set()
            numbers(json.loads(f.read_text()), vals)
            pools[f"labs:{f.stem}"] = vals
        except Exception:                                     # noqa: BLE001
            continue
    for f in sorted((ROOT / "pipeline").glob("*.json")):
        try:
            vals: set = set()
            numbers(json.loads(f.read_text()), vals)
            pools[f"pipeline:{f.stem}"] = vals
        except Exception:                                     # noqa: BLE001
            continue
    for f in sorted(DATA.glob("*.json")):
        try:
            vals: set = set()
            numbers(json.loads(f.read_text()), vals)
            pools[f.stem] = vals
        except Exception:                                     # noqa: BLE001
            continue
    return pools


def strip_citations(text: str) -> str:
    """Remove the numbers that are legal citations, years and code blocks."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"\b\d+\s*(?:CFR|U\.?S\.?C\.?)\s*[\d.()a-z§-]*", " ", text)
    text = re.sub(r"\b(?:EO|SEAD|Executive Order|Proclamation|Pub\.? ?L\.?)\s*[\d.-]+",
                  " ", text, flags=re.I)
    text = re.sub(r"\b(?:19|20)\d{2}\b", " ", text)           # years
    text = re.sub(r"\bFY\d{2,4}\b", " ", text)
    text = re.sub(r"\b\d{1,2}-\d{1,2}\b", " ", text)          # ranges, dates
    text = re.sub(r"\b\d{2}-[a-z]", " ", text, flags=re.I)    # H-1B, H-2A, L-1
    return text


def present(value: float, pool: set) -> bool:
    for cand in (value, value / 100.0, value * 100.0):
        for p in pool:
            if abs(cand - p) <= max(ABS_TOLERANCE, abs(p) * REL_TOLERANCE):
                return True
    return False


def scan(verbose: bool = False):
    pools = dataset_values()
    report, total, orphans = [], 0, 0
    for path in sorted(KB.glob("*.md")):
        text = path.read_text()
        stems = {m.group(1) or m.group(2) for m in CITED.finditer(text)}
        stems |= set(sources_for(path.name))
        pool: set = set()
        for stem in stems:
            pool |= pools.get(stem, set())
        missing = []
        for m in FIG.finditer(strip_citations(text)):
            raw = m.group(1)
            if raw in EXTERNAL or raw.replace(",", "") in EXTERNAL:
                continue
            total += 1
            try:
                value = float(raw.replace(",", ""))
            except ValueError:
                continue
            if not pool or not present(value, pool):
                missing.append(raw)
        orphans += len(missing)
        if missing:
            report.append((path.name, len(missing), sorted(stems), missing))
    report.sort(key=lambda r: -r[1])
    return total, orphans, report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true", help="name every figure")
    ap.add_argument("--accept", action="store_true",
                    help="pin the current count as the new baseline")
    args = ap.parse_args()

    total, orphans, report = scan(args.verbose)
    base = 10**9
    if BASELINE.exists():
        base = json.loads(BASELINE.read_text()).get("untraceable", 10**9)

    print(f"  {total:,} figures in the knowledge base, "
          f"{total - orphans:,} traceable to a dataset the file draws on")
    for name, n, stems, missing in report[:12]:
        shown = ", ".join(missing[:6]) + ("…" if len(missing) > 6 else "")
        src = ", ".join(stems) if stems else "NO SOURCE DECLARED"
        print(f"    {n:>4}  {name:<42}{shown}")
        if args.verbose:
            print(f"          sources: {src}")

    if args.accept or not BASELINE.exists():
        BASELINE.write_text(json.dumps({"untraceable": orphans}, indent=1) + "\n")
        print(f"  baseline pinned at {orphans}")
        return 0

    if orphans > base:
        print(f"  FAIL: untraceable figures rose from {base} to {orphans}. "
              f"New prose must cite the dataset its numbers come from.")
        return 1
    if orphans < base:
        print(f"  {base - orphans} fewer than the baseline of {base}. "
              f"Lower it: python3 scripts/check_kb_provenance.py --accept")
    else:
        print(f"  at the baseline of {base}; none added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
