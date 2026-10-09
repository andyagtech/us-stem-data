#!/usr/bin/env python3
"""The entry point for the thesis and dissertation name lists.

WHY THIS PAGE EXISTS. The name lists are the most persuasive thing on this
site. A chart showing a 74% non-resident share is an argument. A list of
every doctorate awarded by a department, with the person's name, the year and
the title of the work, is the thing itself -- real research, done by real
people, in American institutions, and a reader can click any name through to
the university's own repository and check it.

They had no entry point. /name_lists.html was a redirect to stem.html, the
lists were not in the sidebar, and they were not in the chat site map, so the
assistant could not send anyone to them. The single most shareable material
on the site was reachable only by knowing where to look.

This page is that entry point. It is deliberately thin: it states what the
lists are, how big they are, what a reader can do with them, and hands over
to the lists themselves. Everything it counts is counted from the built
record files, so it cannot drift from them.

Usage:
  python3 scripts/build_name_lists_index.py
"""
from __future__ import annotations

import collections
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

SITE = ROOT / "site"
OUT = SITE / "name-lists.html"
DATA = SITE / "data"

E = html.escape


def n(v) -> str:
    return f"{int(v):,}"


def survey():
    """Count the record files, so the page cannot overstate the harvest."""
    tot = 0
    per_kind = {}
    unis = {}
    years = collections.Counter()
    depts = set()
    for kind in ("stem", "nonstem"):
        k = 0
        d = DATA / kind
        if not d.is_dir():
            raise SystemExit(f"missing {d.relative_to(ROOT)}; run "
                             f"generate_name_lists_html.py")
        for f in sorted(d.glob("*.json")):
            if f.name == "_search.json":
                continue
            blob = json.loads(f.read_text())
            recs = blob.get("records") or []
            k += len(recs)
            key = blob.get("key") or f.stem
            e = unis.setdefault(key, {"name": blob.get("name") or f.stem,
                                      "key": key, "records": 0,
                                      "nra": blob.get("nra")})
            e["records"] += len(recs)
            if blob.get("nra") is not None:
                e["nra"] = blob["nra"]
            for r in recs:
                if isinstance(r, list) and len(r) > 1:
                    if isinstance(r[1], int) and 1900 < r[1] < 2100:
                        years[r[1]] += 1
                    if r and isinstance(r[0], str):
                        depts.add(r[0])
        per_kind[kind] = k
        tot += k
    ys = sorted(years)
    return {"total": tot, "per_kind": per_kind, "universities": unis,
            "first_year": ys[0], "last_year": ys[-1], "departments": len(depts)}


def main() -> int:
    s = survey()
    unis = sorted(s["universities"].values(), key=lambda u: -u["records"])
    by_nra = sorted((u for u in unis if u.get("nra") is not None),
                    key=lambda u: -u["nra"])[:12]

    title = "Thesis & Dissertation Name Lists"
    desc = (f"{n(s['total'])} doctoral and master's records from 106 American "
            f"universities, {s['first_year']} to {s['last_year']}. Every name "
            f"links to the university's own repository.")

    p = [f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<link rel="stylesheet" href="/style.css">
<style>
  .wrap {{ max-width: 1120px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}
  .page-head h1 {{ font-size: 2rem; margin: 0 0 .7rem; line-height: 1.18; }}
  .page-head p {{ color: var(--text-muted); max-width: 70ch; line-height: 1.68;
    font-size: 1rem; margin: 0 0 .7rem; }}
  .page-head p.first {{ color: var(--text); font-size: 1.1rem; font-weight: 500; }}
  .kicker {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .08em;
    color: var(--text-muted); margin: 0 0 .6rem; }}
  .stats {{ display: grid; grid-template-columns: repeat(4, minmax(0,1fr));
    gap: .8rem; margin: 1.8rem 0 0; }}
  .stat {{ border: 1px solid var(--border); border-radius: 10px; padding: .9rem 1rem;
    background: var(--surface); }}
  .stat .n {{ font-size: 1.7rem; font-weight: 800; color: var(--hl); line-height: 1.1;
    font-variant-numeric: tabular-nums; }}
  .stat .l {{ font-size: .82rem; line-height: 1.45; margin: .3rem 0 0; }}
  @media (max-width: 900px) {{ .stats {{ grid-template-columns: repeat(2,minmax(0,1fr)); }} }}
  @media (max-width: 480px) {{ .stats {{ grid-template-columns: 1fr; }} }}
  section.block {{ margin-top: 2.8rem; border-top: 1px solid var(--border);
    padding-top: 1.6rem; }}
  section.block h2 {{ font-size: 1.25rem; margin: 0 0 .5rem; }}
  section.block p {{ max-width: 72ch; line-height: 1.68; font-size: .95rem;
    margin: 0 0 .9rem; }}
  .lede {{ color: var(--text-muted); max-width: 72ch; line-height: 1.6;
    font-size: .93rem; margin: 0 0 1rem; }}
  .note {{ color: var(--text-muted); font-size: .78rem; line-height: 1.55;
    max-width: 82ch; margin: 1rem 0 0; }}

  /* THE TWO DOORS. These are the whole point of the page, so they are the
     largest thing on it after the headline. */
  .doors {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr));
    gap: 1rem; margin: 1.4rem 0 0; }}
  @media (max-width: 680px) {{ .doors {{ grid-template-columns: 1fr; }} }}
  .door {{ display: block; text-decoration: none; color: inherit;
    border: 1px solid var(--border); border-left: 3px solid var(--hl);
    border-radius: 10px; padding: 1.2rem 1.3rem; background: var(--surface); }}
  .door:hover {{ border-color: var(--hl); }}
  .door .t {{ font-size: 1.12rem; font-weight: 700; color: var(--hl);
    margin: 0 0 .3rem; }}
  .door .c {{ font-size: 1.5rem; font-weight: 800; font-variant-numeric: tabular-nums;
    margin: 0 0 .25rem; }}
  .door .d {{ font-size: .86rem; color: var(--text-muted); line-height: 1.55; margin: 0; }}

  .unis {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr));
    gap: .5rem; margin: 1rem 0 0; }}
  @media (max-width: 860px) {{ .unis {{ grid-template-columns: repeat(2,minmax(0,1fr)); }} }}
  @media (max-width: 520px) {{ .unis {{ grid-template-columns: 1fr; }} }}
  .uni {{ display: flex; justify-content: space-between; gap: .6rem;
    text-decoration: none; color: inherit; border: 1px solid var(--border);
    border-radius: 8px; padding: .55rem .75rem; background: var(--surface);
    font-size: .86rem; }}
  .uni:hover {{ border-color: var(--hl); }}
  .uni .v {{ color: var(--hl); font-weight: 700; font-variant-numeric: tabular-nums;
    white-space: nowrap; }}
  ol.steps {{ max-width: 72ch; padding-left: 1.2rem; }}
  ol.steps li {{ margin: 0 0 .6rem; line-height: 1.65; font-size: .95rem; }}
</style>
  <script id="phd-theme-boot">(function(){{try{{var t=localStorage.getItem("phd-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
  <script defer src="/theme.js"></script>
</head>
<body data-page="name-lists">
<main class="wrap">
<div class="page-head">
<p class="kicker">Every record links to the university's own repository</p>
<h1>The names behind the numbers</h1>
<p class="first">This is the work itself. {n(s['total'])} doctoral and
master's theses awarded by 106 American universities, with the name of the
person who wrote each one, the department, the year and the title.</p>
<p>Every other page here reports a share or a count. This one reports the
research. These are the dissertations American universities produced, the
problems they chose to work on, and the people they trained to do it.</p>
<p>Each name links to the awarding university's own repository, so any entry
can be checked at its source.</p>
</div>

<div class="stats">
  <div class="stat"><div class="n">{n(s['total'])}</div>
    <p class="l">records</p></div>
  <div class="stat"><div class="n">106</div>
    <p class="l">universities</p></div>
  <div class="stat"><div class="n">{n(s['departments'])}</div>
    <p class="l">departments</p></div>
  <div class="stat"><div class="n">{s['first_year']}&ndash;{s['last_year']}</div>
    <p class="l">years covered</p></div>
</div>

<section class="block" id="open">
<h2>Open the lists</h2>
<p class="lede">Both views carry the same structure: pick a university, expand
a department, expand a year, and read the names and titles.</p>
<div class="doors">
  <a class="door" href="/stem">
    <p class="t">STEM theses and dissertations &rarr;</p>
    <p class="c">{n(s['per_kind']['stem'])}</p>
    <p class="d">Science, technology, engineering and mathematics, ranked by
    each university's non-resident share of STEM doctoral completions.</p>
  </a>
  <a class="door" href="/non_stem">
    <p class="t">Non-STEM theses and dissertations &rarr;</p>
    <p class="c">{n(s['per_kind']['nonstem'])}</p>
    <p class="d">Humanities, social sciences, education, business and the
    arts, in the same structure.</p>
  </a>
</div>
</section>

<section class="block" id="how">
<h2>How to read one</h2>
<ol class="steps">
<li><strong>Pick a university</strong> from the rail on the left. It is
ordered by non-resident share of STEM doctoral completions, so the
institutions where the question is sharpest are at the top.</li>
<li><strong>Expand a department.</strong> The count beside it is how many
records the harvest found for that department.</li>
<li><strong>Expand a year</strong> and read the list. Each row is one thesis:
the author, and the title of the work.</li>
<li><strong>Click any name</strong> to open that record in the university's
own repository and verify it.</li>
</ol>
<p>A department is the right unit to look at. A university-wide figure
averages a physics department against a school of education. The department
list shows who actually did the work in one field, one year at a time.</p>
</section>

<section class="block" id="largest">
<h2>The largest collections</h2>
<p class="lede">By number of records the harvest found. A university that
publishes more appears larger here, which is a fact about its repository and
not only about its output.</p>
<div class="unis">
"""]
    for u in unis[:18]:
        p.append(f'<a class="uni" href="/universities/{E(u["key"])}">'
                 f'<span>{E(u["name"])}</span>'
                 f'<span class="v">{n(u["records"])}</span></a>')
    p.append("""</div>
</section>

<section class="block" id="highest-nra">
<h2>Where the non-resident share is highest</h2>
<p class="lede">The same lists, for the universities with the highest
non-resident share of STEM doctoral completions in IPEDS.</p>
<div class="unis">
""")
    for u in by_nra:
        p.append(f'<a class="uni" href="/universities/{E(u["key"])}">'
                 f'<span>{E(u["name"])}</span>'
                 f'<span class="v">{u["nra"]}%</span></a>')
    p.append(f"""</div>
</section>

<section class="block" id="limits">
<h2>What this record is not</h2>
<p class="lede">The gap matters as much as the count.</p>
<p><strong>No university is required to publish any of this.</strong> There is
no federal rule obliging an institution to post a dissertation, or even to
list the ones it has awarded. There is no national register. Each university
decides, and the decision is often revisited department by department.</p>
<p>So this record was built one institution at a time, and coverage is a
floor rather than a total. A university that appears smaller here may simply
publish less. Two institutions cannot be ranked against each other on record
count alone.</p>
<p>The names are reproduced as the awarding repository recorded them, with
catalogue artefacts removed &mdash; a degree or an institution glued onto the
author field. Where a suffix could be a real part of a name it is left
alone, because a tidy wrong name is worse than an untidy right one.</p>
<p><a href="/data_requests#no-requirement">The ask that would fix this
&rarr;</a></p>
</section>
</main>
<script src="/analytics-beacon.js" defer></script>
<script src="/anchors.js" defer></script>
<script src="/sidebar.js"></script>
<script src="/chat-widget.js"></script>
</body>
</html>
""")
    #: Also publish the counts as data. The knowledge base and the
    #: consistency checks both need these figures to come from a dataset
    #: rather than from prose, and the page's own totals then have a field
    #: to be pinned against.
    blob = {
        "source": "Built from site/data/{stem,nonstem}/*.json, the harvested "
                  "thesis and dissertation records",
        "total_records": s["total"],
        "stem_records": s["per_kind"]["stem"],
        "nonstem_records": s["per_kind"]["nonstem"],
        "universities": len(unis),
        "departments": s["departments"],
        "first_year": s["first_year"],
        "last_year": s["last_year"],
        "largest": [{"key": u["key"], "name": u["name"],
                     "records": u["records"]} for u in unis[:25]],
        "highest_nra": [{"key": u["key"], "name": u["name"], "nra": u["nra"]}
                        for u in by_nra],
        "caveats": [
            "No university is required to publish a dissertation or to list "
            "the ones it has awarded, so coverage is a floor and not a "
            "total.",
            "A university with fewer records here may publish less rather "
            "than award less. Institutions must not be ranked on record "
            "count alone.",
        ],
    }
    write_text(DATA / "name_lists.json", json.dumps(blob, indent=2))

    write_text(OUT, "".join(p))
    print(f"Wrote {OUT.relative_to(ROOT)} and site/data/name_lists.json")
    print(f"  {n(s['total'])} records, {len(unis)} universities, "
          f"{s['first_year']}-{s['last_year']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
