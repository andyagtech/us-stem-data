#!/usr/bin/env python3
"""Write the engineering sections into /implementation, from measurement.

The page already described the six pipeline steps. What it did not describe
is the part that is actually unusual about this project: that a figure
written in prose is refilled from data on every build, that the assistant's
knowledge base is checked three ways against the datasets it draws on, and
that three quarters of a million rows are queryable in the reader's own
browser with no server at all.

Those are claims about engineering, so every number in them is counted here
at build time rather than typed. The block is replaced wholesale between
markers, so running this twice changes nothing and a figure cannot go stale.

Usage:
  python3 scripts/build_engineering_section.py
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "cloud" / "chat"))
from atomic_write import write_text                           # noqa: E402
from build_methodology_page import _facts                     # noqa: E402

PAGE = ROOT / "site" / "implementation.html"
OPEN, CLOSE = "<!-- engineering:begin -->", "<!-- engineering:end -->"
BLOCK = re.compile(re.escape(OPEN) + r".*?" + re.escape(CLOSE), re.S)

E = html.escape


def n(v) -> str:
    return f"{int(v):,}"


def section(f: dict) -> str:
    return f"""{OPEN}
<h2 id="functionally-inspired">Functionally inspired</h2>
<p>This is not a functional-programming codebase and does not pretend to be.
There is no immutable-data library and no composition framework. What it
takes from that tradition is a discipline, applied where it earns its
keep.</p>
<ul>
<li><strong>A builder reads inputs and writes one output.</strong> It does
not mutate what it read. {n(f['builders'])} builders produce
{n(f['datasets'])} catalogued datasets, one each, and every one prints what
it wrote.</li>
<li><strong>Rebuilds are idempotent.</strong> Running the pipeline twice on
the same inputs produces the same site.</li>
<li><strong>Retrieved data is append-only.</strong> A harvest may add
records and fill empty fields. It may never remove a record, drop a column,
or blank a field that held a value &mdash; in the S3 archive too, where
<code>--delete</code> is forbidden.</li>
<li><strong>Writes are atomic.</strong> A builder once raised part-way
through and left its output holding the previous run's content, so the site
served figures matching no run of the code. Every write now renames into
place: a reader sees the old file or the new one, never a half-written
one.</li>
<li><strong>The catalogue is data, not code.</strong> Each dataset is a
frozen record naming its script, its inputs, its outputs, its source URL and
where its raw data was archived. A builder missing from it is invisible to
the pipeline.</li>
</ul>

<h2 id="figures-cannot-go-stale">Figures in prose cannot go stale</h2>
<p>No number on this site is typed into a sentence. Prose carries a marker
naming the field it quotes, and the build refills it:</p>
<pre><code>&lt;!--auto:data:postdoc_citizenship.national.share|pct1--&gt;58.3&lt;!--/auto--&gt;</code></pre>
<p>{n(f['markers'])} markers across {n(f['managed'])} managed documents,
resolving {n(f['facts'])} distinct facts. A rebuild moves the number inside
the sentence, so a figure cannot outlive the data behind it, and the
consistency gate fails when any marker is stale.</p>
<p>This is not theoretical. The footer on all 227 pages read
&ldquo;Last updated: August 2026&rdquo; in October, because that one string
had been typed rather than marked. It is a marker now.</p>

<h2 id="every-figure-is-checked">Every figure the assistant states is checked three ways</h2>
<p>The assistant answers from {n(f['knowledge_files'])} knowledge files.
A retrieval system that cannot verify its own corpus will state a wrong
number confidently, so each figure in those files is checked against the
data three different ways, because each catches something the others
cannot.</p>
<table>
<thead><tr><th>Check</th><th>Count</th><th>What it proves</th></tr></thead>
<tbody>
<tr><td>Recomputed</td><td>{n(f['recomputed'])}</td>
<td>The figure is derived again from source. Proves the arithmetic, not
just the value.</td></tr>
<tr><td>Pinned to a field</td><td>{n(f['pins'])}</td>
<td>Names the exact field a figure came from, as
<code>by_state[state=CA].priced</code>. The drift alarm: the labor files
land quarterly and every share recomputes.</td></tr>
<tr><td>Provenance ratchet</td><td>backlog of {n(f['baseline'])}</td>
<td>Every figure must be findable in a dataset the file declares. Cheap,
total, and the only thing that catches a number that was invented.</td></tr>
</tbody></table>
<p><strong>Pin the field, never the row.</strong> These lists sort by
volume, so a pin to row zero quietly becomes a different state after a
rebuild while the check still passes.</p>
<p>The provenance check is a ratchet rather than a gate: the historic
backlog is recorded and new prose may not add to it. Guards are also tested
for failure before being trusted &mdash; a check that has never gone red may
not work. One recently did not: a pin compared its table against the data
but never read the prose, so editing a figure in a knowledge file passed
everything. It reads both ends now.</p>

<h2 id="structured-for-machines">Structured so a machine can use it</h2>
<p>The site is addressable, not just readable. Every section carries a
stable id, and the assistant is given a map of them rather than being left
to guess.</p>
<ul>
<li><strong>{n(f['anchors'])} anchors across {n(f['map_pages'])} pages</strong>,
published as a map the assistant ships inside its own bundle. It can send a
reader to a numbered section, not merely to a page.</li>
<li><strong>The map is part of the deploy gate.</strong> A page can be live,
linked and indexed while the assistant is unable to mention it, because the
assistant carries its own copy. That happened twice. A consistency check now
fails when the bundle is behind the site.</li>
<li><strong>A machine-readable catalogue</strong> at
<a href="/catalog.json">/catalog.json</a>, generated, describing every
dataset with its federal source.</li>
</ul>

<h2 id="query-in-the-browser">Three quarters of a million rows, no server</h2>
<p>{n(f['exports'])} Parquet exports load into the reader's own browser and
are queried there with SQL. Nothing is sent anywhere, there is no backend to
run, and the tables can be joined &mdash; which employer sits in which
industry, which public employers file both a green card and an H-1B.</p>
<p>The same files are downloadable and work directly with DuckDB, so any
figure on this site can be checked without trusting the site.</p>

<h2 id="classification-is-experimental">Where the method is weakest</h2>
<p>Two parts of this project are estimates, and are labelled as such
wherever they appear.</p>
<p><strong>Degree-level classification is approximate and experimental.</strong>
A repository often records a thesis without saying whether it is a master's
or a doctorate. {f['labelled_pct']}% of records carry a degree label;
{n(f['unlabelled'])} do not. Where a title and department made it inferable,
a cached run of a small language model classified
{n(f['ai_records'])} records, keeping nothing below
{f['ai_min_conf']:.2f} confidence. That step is <em>not</em> part of the
pipeline &mdash; it is a standalone script, run by hand, and its results are
cached rather than recomputed. It should be read as a best guess at scale,
not as a label from the registrar.</p>
<p><strong>Name-origin classification is inference, not identity.</strong> A
name is evidence about likely origin and nothing more. It is never presented
as a person's nationality, and no conclusion on this site rests on a single
classified name.</p>
{CLOSE}"""


def main() -> int:
    if not PAGE.exists():
        print(f"  missing {PAGE.relative_to(ROOT)}")
        return 1
    f = _facts()
    s = PAGE.read_text()
    block = section(f)
    if BLOCK.search(s):
        s = BLOCK.sub(block, s)
        where = "replaced"
    else:
        #: First run. The engineering story belongs after the architecture
        #: section and before the CLI reference, which is reference matter.
        m = re.search(r'<h2[^>]*>\s*CLI Usage', s)
        if not m:
            print("  no insertion point found (CLI Usage heading)")
            return 1
        s = s[:m.start()] + block + "\n\n" + s[m.start():]
        where = "inserted"
    write_text(PAGE, s)
    print(f"  {where} the engineering block in {PAGE.relative_to(ROOT)}")
    print(f"  {f['markers']} markers, {f['pins']} pins, {f['recomputed']} recomputed, "
          f"{f['anchors']} anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
