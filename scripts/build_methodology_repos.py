#!/usr/bin/env python3
"""Put the repository list on the methodology page, idempotently.

Reads site/data/repository_index.json and writes a sortable table of every
institutional repository the harvest read, before "What the data cannot
answer". Running it twice changes nothing.

Usage:
    python3 scripts/build_methodology_repos.py
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "site" / "data" / "repository_index.json"
PAGE = ROOT / "site" / "methodology.html"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                          # noqa: E402

E = html.escape
OPEN, CLOSE = "<!-- repos:begin -->", "<!-- repos:end -->"
BLOCK = re.compile(re.escape(OPEN) + r".*?" + re.escape(CLOSE), re.S)


def main() -> int:
    d = json.loads(SRC.read_text())
    rows = []
    for r in sorted(d["repositories"], key=lambda r: r["name"].lower()):
        if r["url"]:
            link = (f'<a href="{E(r["url"])}" rel="noopener">'
                    f'{E(r["repository"])}</a>')
            if r["indirect"]:
                link += ' <span class="rp-note">resolver</span>'
        else:
            #: Saying so is the finding. A blank cell reads as an oversight.
            link = '<span class="rp-note">not recorded</span>'
        rows.append(f'<tr><td>{E(r["name"])}</td><td>{link}</td>'
                    f'<td class="num">{r["departments_searched"] or "&mdash;"}</td></tr>')

    block = f'''{OPEN}
<h2 id="institutional-repositories">Every institutional repository read</h2>
<p>Each dissertation on this site links to its record in the awarding
institution's own repository, so any single name can be checked at the
source. These are those repositories: {d["with_repository"]} of
{d["institutions"]} institutions, with the number of departments searched at
each.</p>
<p>A handful resolve through a handle or DOI service rather than a named
archive. Those are marked <span class="rp-note">resolver</span>, because the
host forwards to the institution's archive rather than being it.
{d["without_repository"]} institutions have no repository recorded here; their
records came from a route this file does not capture, and that is stated
rather than left blank.</p>
<div class="table-wrap"><table class="t" data-sortable>
<thead><tr><th class="sortable">Institution</th>
<th class="sortable">Repository</th>
<th class="sortable num">Departments searched</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
{CLOSE}'''

    s = PAGE.read_text()
    s = BLOCK.sub("", s)
    anchor = '<h2 id="what-the-data-cannot-answer">'
    if anchor not in s:
        print("ERROR: methodology.html has no 'what the data cannot answer' "
              "heading to insert before.")
        return 1
    s = s.replace(anchor, block + "\n\n" + anchor, 1)

    css = """<style id="repo-style">
  .rp-note { font-size: .78rem; color: var(--text-muted); font-style: italic; }
  table.t { width: 100%; border-collapse: collapse; font-size: .85rem; margin: .8rem 0 0; }
  table.t th { text-align: left; font-size: .7rem; text-transform: uppercase;
    letter-spacing: .05em; color: var(--text-muted); padding: .4rem .5rem;
    border-bottom: 1px solid var(--border); }
  table.t td { padding: .35rem .5rem; border-bottom: 1px solid var(--border); }
  table.t td.num, table.t th.num { text-align: right; font-variant-numeric: tabular-nums; }
  table.t th.sortable { cursor: pointer; }
  .table-wrap { overflow-x: auto; }
</style>"""
    if "repo-style" not in s:
        s = s.replace("</head>", css + "\n</head>", 1)
    if 'src="/states.js"' not in s:
        s = s.replace("</body>", '<script src="/states.js" defer></script>\n</body>', 1)
    write_text(PAGE, s)
    print(f"wrote {PAGE.relative_to(ROOT)}: {len(rows)} repositories listed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
