#!/usr/bin/env python3
"""Generate the methodology page from the catalogue.

site/data_sources.html was maintained by hand and had fallen behind: it
covered none of the cap-exempt, Build Fellowship, J-1, EB-2, Form 990,
College Scorecard or stay-rate work. A hand-kept sources page always drifts,
and a document going to legislators cannot cite sources it does not list.

So the page is derived from pipeline.datasets, which is the same catalogue
check_consistency.py validates. Adding a dataset adds a row; a dataset with
no source URL fails the build there rather than quietly vanishing here.

Usage:
  python3 scripts/build_methodology_page.py
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.datasets import CATALOG  # noqa: E402
# Ids are stamped here rather than by add_section_anchors.py, which this page
# is excluded from: it is rewritten on every build, so an id added afterwards
# would survive exactly until the next one. The slugs follow that tool's
# convention so anchors.js resolves the same string at runtime.
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text as _atomic_write_text  # noqa: E402

OUT = ROOT / "site" / "methodology.html"

AGENCY = [
    ("nces.ed.gov", "NCES", "Dept of Education"),
    ("collegescorecard.ed.gov", "College Scorecard", "Dept of Education"),
    ("ncses.nsf.gov", "NCSES", "National Science Foundation"),
    ("uscis.gov", "USCIS", "Dept of Homeland Security"),
    ("ice.gov", "SEVP", "Dept of Homeland Security"),
    ("dol.gov", "OFLC", "Dept of Labor"),
    ("travel.state.gov", "State Dept", "Dept of State"),
    ("j1visa.state.gov", "BridgeUSA", "Dept of State"),
    ("irs.gov", "IRS", "Dept of the Treasury"),
    ("propublica.org", "ProPublica", "non-government"),
]


def classify(url: str) -> tuple[str, str]:
    for frag, short, dept in AGENCY:
        if frag in url:
            return short, dept
    return "other", "non-government"


def main() -> int:
    rows, gov, other = [], 0, 0
    for d in sorted(CATALOG, key=lambda x: x.key):
        if not d.source_url:
            continue
        short, dept = classify(d.source_url)
        is_gov = dept != "non-government"
        gov += is_gov
        other += not is_gov
        rows.append(
            f'<tr><td><code>{html.escape(d.key)}</code></td>'
            f'<td>{html.escape(d.summary)}</td>'
            f'<td>{html.escape(d.source)}</td>'
            f'<td><a href="{html.escape(d.source_url)}" rel="noopener">{short}</a></td>'
            f'<td>{"government" if is_gov else "third party"}</td></tr>')

    derived = [d.key for d in CATALOG if not d.source_url]
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Methodology and sources</title>
<meta name="description" content="Every dataset behind this site, with the
agency that publishes it and a link to obtain it.">
<link rel="stylesheet" href="/style.css">
</head><body>
<div class="wrap">
<h1 id="methodology-and-sources">Methodology and sources</h1>
<p class="lede">Every dataset behind this site, with the agency that publishes
it and a link to get it yourself. {gov} come from federal statistical
sources; {other} do not, and are marked.</p>

<p>This page is generated from the project's dataset catalogue, not written by
hand, so it cannot fall behind what the site actually uses. A dataset added
without a source URL fails the consistency checks.</p>

<h2 id="datasets">Datasets</h2>
<table>
<thead><tr><th>Key</th><th>What it is</th><th>Source</th><th>Link</th>
<th>Provenance</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table>

<h2 id="derived">Derived</h2>
<p>These are built from the datasets above and have no external source:
{", ".join(f"<code>{html.escape(k)}</code>" for k in derived)}.</p>

<h2 id="what-the-data-cannot-answer">What the data cannot answer</h2>
<p>Three limits recur and are stated wherever the figures appear.
<strong>Cap-exempt status is not published</strong>: USCIS records it on the
I-129 and releases only national totals by employer category, so every public
cap-exempt employer list, including this site's, is an inference from
employer type. <strong>IPEDS counts degrees, not people</strong>, so any
progression figure is a ratio between two populations rather than a tracked
cohort. And <strong>no federal source records graduate applications or
admissions</strong>, so whether domestic applicants are declining, being
declined, or not applying cannot be determined from published data.</p>
</div>
</body></html>
"""
    # Written atomically: a reader following a link from the briefing must
    # never land on a half-written page.
    _atomic_write_text(OUT, page)
    print(f"  {len(rows)} datasets ({gov} government, {other} third party)")
    print(f"  {len(derived)} derived with no external source")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
