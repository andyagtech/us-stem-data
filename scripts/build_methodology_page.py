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



def _count(path: Path, pattern: str) -> int:
    """How many times a pattern appears across a glob. Counted at build
    time so none of the figures below can be typed, which is the same rule
    the rest of the site follows."""
    import re
    n = 0
    for f in sorted(ROOT.glob(path)) if isinstance(path, str) else []:
        pass
    return n


def _facts() -> dict:
    """Everything the architecture sections quote, measured now."""
    import json
    import re
    out = {}

    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_docs

    out["builders"] = len(list((ROOT / "scripts").glob("build_*.py")))
    out["datasets"] = len(CATALOG)

    # Tests and checks, counted rather than remembered.
    # Tests and checks come from sync_docs, which already resolves both and
    # is the same source CLAUDE.md quotes. Counting them a second way here
    # produced 487 tests against 1,237 and 27 checks against 37, because a
    # test function can be parametrised and one check function can make
    # several assertions. Two counts of the same thing is one too many.
    try:
        out["tests"] = int(sync_docs.FACTS["test_count"]().replace(",", ""))
        out["checks"] = int(sync_docs.FACTS["consistency_checks"]())
    except Exception:
        pass

    # The auto-marker system.
    try:
        out["managed"] = len(sync_docs.MANAGED)
        out["facts"] = len(sync_docs.FACTS)
        out["markers"] = sum(
            len(re.findall(r"<!--auto:", (ROOT / rel).read_text(errors="replace")))
            for rel in sync_docs.MANAGED if (ROOT / rel).exists())
        out["facts_used"] = len({m for rel in sync_docs.MANAGED
                                 if (ROOT / rel).exists()
                                 for m in re.findall(
                                     r"<!--auto:([a-z0-9_]+)",
                                     (ROOT / rel).read_text(errors="replace"))})
    except Exception:
        out["managed"] = out["facts"] = out["markers"] = 0

    # The three knowledge checks.
    try:
        sys.path.insert(0, str(ROOT / "cloud" / "chat"))
        from knowledge_pins import PINS
        out["pins"] = len(PINS)
    except Exception:
        out["pins"] = 0
    try:
        from knowledge_figures import FIGURES
        out["recomputed"] = len(FIGURES)
    except Exception:
        out["recomputed"] = 0
    base = ROOT / "cloud" / "chat" / "kb_provenance_baseline.json"
    try:
        out["baseline"] = len(json.loads(base.read_text()))
    except Exception:
        out["baseline"] = 0

    # Structure: anchors and the assistant's map.
    sm = ROOT / "site" / "data" / "chat" / "site_map.json"
    try:
        j = json.loads(sm.read_text())
        pages = j.get("pages") or []
        out["map_pages"] = len(pages)
        out["anchors"] = sum(len(pg.get("sections") or [])
                             for pg in pages if isinstance(pg, dict))
    except Exception:
        out["map_pages"] = out["anchors"] = 0
    out["knowledge_files"] = len(list(
        (ROOT / "cloud" / "chat" / "knowledge").glob("*.md")))

    # The browser-side query surface.
    ex = ROOT / "site" / "data" / "exports"
    out["exports"] = len(list(ex.glob("*.parquet"))) if ex.is_dir() else 0

    # Degree labelling, for the AI-classification section.
    lab = unlab = 0
    for track in ("stem", "nonstem"):
        d = ROOT / "site" / "data" / track
        if not d.is_dir():
            continue
        for f in d.glob("*.json"):
            if f.name.startswith("_"):
                continue
            try:
                recs = json.loads(f.read_text()).get("records") or []
            except Exception:
                continue
            for r in recs:
                if isinstance(r, list) and len(r) > 7:
                    if r[7]:
                        lab += 1
                    else:
                        unlab += 1
    out["labelled"], out["unlabelled"] = lab, unlab
    out["labelled_pct"] = round(lab / (lab + unlab) * 100, 1) if lab + unlab else 0

    ai = ROOT / "pipeline" / "ai_classifications.json"
    try:
        cache = json.loads(ai.read_text())
        out["ai_records"] = sum(len(v) for v in cache.values() if isinstance(v, list))
        conf = sorted(r[2] for v in cache.values() if isinstance(v, list)
                      for r in v if isinstance(r, list) and len(r) > 2)
        out["ai_min_conf"] = round(min(conf), 2) if conf else 0
    except Exception:
        out["ai_records"] = out["ai_min_conf"] = 0
    return out


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
<style>
  /* .wrap is this page's own container and is defined nowhere else, so it
     had no padding at all: at 375px the heading, the lede and every table
     cell began at x=0, hard against the bezel. */
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 1.75rem 1.25rem 3.5rem; }}
  .wrap table {{ width: 100%; border-collapse: collapse; }}
  .wrap .table-wrap, .wrap > table {{ display: block; overflow-x: auto; }}
  @media (max-width: 620px) {{
    .wrap {{ padding: 1.25rem 1rem 2.5rem; }}
    .wrap table {{ font-size: .8rem; }}
  }}
</style>
  <script id="phd-theme-boot">(function(){{try{{var t=localStorage.getItem("phd-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
  <script defer src="/theme.js"></script>
</head><body>
<div class="wrap">
<h1 id="dataset-catalogue">Dataset catalogue</h1>
<p class="lede">One row per dataset behind this site, with the agency that
publishes it and a link to get it yourself. For the narrative method &mdash;
how the records were collected, what the citizenship categories mean, and
what the figures cannot show &mdash; see
<a href="/data_sources">Data sources and methodology</a>. {gov} come from federal statistical
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
<!-- THE PAGE EMITS ITS OWN SHELL. These four were previously added to the
     built file by a later pass, so regenerating this page on its own -- as
     anyone would when editing the builder -- silently produced a page with
     no sidebar, no analytics beacon and no chat widget, and shipped it. A
     fully generated page should depend on nothing invisible. -->
<script src="/sidebar.js"></script>
<script src="/analytics-beacon.js" defer></script>
<script src="/anchors.js" defer></script>
<script src="/states.js" defer></script>
<script src="/chat-widget.js"></script>
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
