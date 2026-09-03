#!/usr/bin/env python3
"""Regenerate the derived-datasets list on the data sources page from the catalogue.

WHY. site/data_sources.html kept this list by hand, and by September 2026 it had
drifted to naming 34 of the 44 datasets the catalogue publishes -- missing the
level rankings, the graduate support tables, the stay rates, the earnings, the
per-institution profiles and five others. That is the same failure that produced
scripts/build_methodology_page.py: a hand-kept list of a growing thing always
falls behind, and it falls behind silently, because nothing about the page looks
wrong when an entry is simply absent.

So the list is derived from pipeline.datasets, the same catalogue
check_consistency.py validates, and check_consistency.py now fails the build if
the page and the catalogue disagree.

Only the list between the markers is touched; the rest of the page stays
hand-written, because the prose around each federal collection is judgement
about the source and not something a catalogue can hold.

Usage:
  python3 scripts/build_derived_datasets_list.py
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from pipeline.datasets import CATALOG            # noqa: E402
from atomic_write import write_text              # noqa: E402

PAGE = ROOT / "site" / "data_sources.html"
START = "<!-- derived:start -->"
END = "<!-- derived:end -->"

#: Longer than this and an entry stops being a one-line description.
LIMIT = 190


def published() -> list[tuple[str, str, str]]:
    """(filename, summary, script) for every dataset the catalogue publishes.

    A dataset can produce several files; only the ones served under /data are
    listed, because those are the ones a reader can actually download.
    """
    out = []
    for d in sorted(CATALOG, key=lambda x: x.key):
        for path in d.produces:
            m = re.fullmatch(r"site/data/([a-z0-9_]+\.json)", path)
            if m:
                out.append((m.group(1), d.summary, d.script))
    return sorted(out)


def sentence(summary: str) -> str:
    """The catalogue summary as one line, trimmed at a clause break if long.

    Cutting mid-clause reads as a truncation bug rather than a summary, so a
    long entry is cut back to the last semicolon, dash or comma before the
    limit and only falls back to a word boundary if there is none.
    """
    text = " ".join(summary.split())
    if len(text) <= LIMIT:
        return text
    for mark in ("; ", " -- ", ", "):
        cut = text.rfind(mark, 0, LIMIT)
        if cut > LIMIT // 3:
            return text[:cut].rstrip(" ,;-") + "\u2026"
    return text[:text.rfind(" ", 0, LIMIT)].rstrip(" ,;-") + "\u2026"


def main() -> int:
    if not PAGE.exists():
        print(f"  missing {PAGE}")
        return 1
    src = PAGE.read_text()
    if START not in src or END not in src:
        print(f"  markers {START} / {END} not found in {PAGE.name}")
        return 1

    rows = published()
    items = []
    for name, summary, script in rows:
        items.append(
            f"      <li><code>/data/{name}</code> &mdash; "
            f"{html.escape(sentence(summary), quote=False)}\n"
            f"        (<code>scripts/{script}.py</code>).</li>")
    body = (f"{START}\n    <ul>\n" + "\n".join(items)
            + f"\n    </ul>\n    {END}")

    head, rest = src.split(START, 1)
    _old, tail = rest.split(END, 1)
    write_text(PAGE, head + body + tail)
    print(f"  wrote {PAGE.relative_to(ROOT)}: {len(rows)} derived datasets listed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
