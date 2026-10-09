#!/usr/bin/env python3
"""The postdoc page: who holds the appointments federal research money funds.

WHY THIS PAGE EXISTS. On 2026-10-08 the Department of Labor and the Department
of Justice opened a J-1 investigation into nine universities, and the figure
given in public was that about 61% of postdoctoral researchers and federally
funded workers at those institutions are foreign nationals, against a national
average of 38%. This site holds the NSF survey that measures exactly that
population, so the figure can be checked rather than repeated.

WHAT CHECKING IT FOUND, and the page says both halves:

  * The 61% is right. Computed from the NSF microdata, the nine come to 60.7%.
  * The national average is not 38%. It is 58.3% on the same measure.

The second half matters more than the first. If the nine were far above a low
national average they would be outliers and the story would be about nine
universities. They are not outliers. The national postdoctoral workforce is
58.3% foreign, so American citizens and permanent residents are a minority of
it everywhere, and the nine are about two points above a line that is already
over half. That is a bigger finding than the one announced, and it is the
author's thesis stated in federal data: an American is a minority in their own
field, in their own country.

NO LEGAL CLAIM. The page says what the survey counts. It does not say any
university broke a law, and the investigation's existence is reported as a
fact with its date, not as a finding.

Usage:
  python3 scripts/build_postdoc_page.py
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

SRC = ROOT / "site" / "data" / "postdoc_citizenship.json"
OUT = ROOT / "site" / "postdocs.html"

E = html.escape


def n(v) -> str:
    return f"{int(v):,}"


def head(title: str, desc: str) -> str:
    return f"""<!DOCTYPE html>
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
  .page-head h1 {{ font-size: 1.9rem; margin: 0 0 .7rem; line-height: 1.2; }}
  .page-head p {{ color: var(--text-muted); max-width: 72ch; line-height: 1.65;
    font-size: .95rem; margin: 0 0 .6rem; }}
  .kicker {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .08em;
    color: var(--text-muted); margin: 0 0 .6rem; }}
  .stats {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: .8rem; margin: 1.6rem 0 0; }}
  .stat {{ border: 1px solid var(--border); border-radius: 10px; padding: .9rem 1rem;
    background: var(--surface); }}
  .stat .n {{ font-size: 1.7rem; font-weight: 800; color: var(--hl); line-height: 1.1;
    font-variant-numeric: tabular-nums; }}
  .stat .l {{ font-size: .82rem; line-height: 1.45; margin: .3rem 0 0; }}
  .stat .s {{ font-size: .72rem; color: var(--text-muted); margin: .45rem 0 0; }}
  @media (max-width: 900px) {{ .stats {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} }}
  @media (max-width: 480px) {{ .stats {{ grid-template-columns: 1fr; }} }}
  section.block {{ margin-top: 2.8rem; border-top: 1px solid var(--border);
    padding-top: 1.6rem; }}
  section.block h2 {{ font-size: 1.2rem; margin: 0 0 .45rem; }}
  .lede {{ color: var(--text-muted); max-width: 74ch; line-height: 1.6;
    font-size: .92rem; margin: 0 0 1rem; }}
  section.block p {{ max-width: 74ch; line-height: 1.68; font-size: .92rem;
    margin: 0 0 .95rem; }}
  section.block ul.lede {{ padding-left: 1.1rem; }}
  section.block ul.lede li {{ margin: 0 0 .5rem; }}
  .note {{ color: var(--text-muted); font-size: .78rem; line-height: 1.55;
    max-width: 82ch; margin: .9rem 0 0; }}
  .table-wrap {{ overflow-x: auto; }}
  table.t {{ width: 100%; border-collapse: collapse; font-size: .84rem; margin: .6rem 0 0; }}
  table.t th {{ text-align: left; font-size: .71rem; text-transform: uppercase;
    letter-spacing: .06em; color: var(--text-muted); font-weight: 600;
    padding: .4rem .5rem; border-bottom: 1px solid var(--border); white-space: nowrap; }}
  table.t td {{ padding: .42rem .5rem; border-bottom: 1px solid var(--border); }}
  table.t td.num, table.t th.num {{ text-align: right;
    font-variant-numeric: tabular-nums; white-space: nowrap; }}
  table.t tr.named td {{ font-weight: 600; }}

  /* THE BAR IS THE WHOLE CHART. One series, drawn to a 100% scale, with the
     national line marked across it so every row is read against the same
     reference rather than against the row above. A block element, not a
     span: a span ignores width and the bars render as hairlines. */
  .barrow {{ display: grid; grid-template-columns: 17rem 1fr 4.2rem;
    gap: .6rem; align-items: center; margin: 0 0 .32rem; font-size: .83rem; }}
  .barrow .nm {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .track {{ position: relative; background: var(--border); border-radius: 3px;
    height: 1.1rem; overflow: hidden; }}
  .track .fill {{ display: block; height: 100%; background: var(--hl);
    border-radius: 3px 0 0 3px; }}
  .track .fill.us {{ background: var(--text-muted); opacity: .45; }}
  .barrow .pc {{ text-align: right; font-variant-numeric: tabular-nums;
    font-weight: 600; }}
  .natline {{ position: relative; height: 1.3rem; margin: .1rem 0 .7rem;
    grid-column: 2; }}
  .scale {{ display: grid; grid-template-columns: 17rem 1fr 4.2rem; gap: .6rem;
    font-size: .68rem; color: var(--text-muted); margin-top: .35rem; }}
  .scale .ticks {{ display: flex; justify-content: space-between; }}
  @media (max-width: 720px) {{
    .barrow, .scale {{ grid-template-columns: 9rem 1fr 3.4rem; }}
  }}
  .callout {{ border: 1px solid var(--border); border-left: 3px solid var(--hl);
    border-radius: 8px; background: var(--surface); padding: 1rem 1.1rem;
    margin: 1.2rem 0 0; }}
  .callout p {{ margin: 0 0 .55rem; font-size: .9rem; line-height: 1.6; }}
  .callout p:last-child {{ margin-bottom: 0; }}
  .cmp {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr));
    gap: .8rem; margin: 1.2rem 0 0; }}
  @media (max-width: 680px) {{ .cmp {{ grid-template-columns: 1fr; }} }}
</style>
  <script id="phd-theme-boot">(function(){{try{{var t=localStorage.getItem("phd-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
  <script defer src="/theme.js"></script>
</head>
<body data-page="postdocs">
"""


def bar(label: str, share: float, named: bool = False) -> str:
    cls = " named" if named else ""
    return (f'<div class="barrow{cls}"><span class="nm">{E(label)}</span>'
            f'<span class="track"><span class="fill" style="width:{share:.1f}%"></span></span>'
            f'<span class="pc">{share:.1f}%</span></div>')


def main() -> int:
    if not SRC.exists():
        print(f"  missing {SRC.relative_to(ROOT)}; run build_postdoc_citizenship.py")
        return 1
    d = json.loads(SRC.read_text())
    nat, named = d["national"], d["named_institutions"]
    year = d["year"]

    title = "Postdocs and Citizenship"
    desc = (f"Postdoctoral appointees by citizenship, {year}. "
            f"{nat['share']}% of the national postdoctoral workforce holds a "
            f"temporary visa.")

    p = [head(title, desc), f"""<main class="wrap">
<div class="page-head">
<p class="kicker">NSF Survey of Graduate Students and Postdoctorates, {E(year)}</p>
<h1>Who holds the postdoc jobs</h1>
<p>A postdoctoral appointment is the job an American doctorate leads to. It is
the step between the degree and a faculty position or a research career, and
roughly half of these posts are paid for with federal research money.</p>
<p>This page counts them by citizenship. A postdoc is counted as American here
if they are a citizen or a permanent resident. Everyone else holds a temporary
visa.</p>
</div>

<div class="stats">
  <div class="stat"><div class="n">{n(nat['postdocs'])}</div>
    <p class="l">postdoctoral appointees</p>
    <p class="s">at {n(nat['institutions'])} institutions, {E(year)}</p></div>
  <div class="stat"><div class="n">{nat['share']}%</div>
    <p class="l">hold a temporary visa</p>
    <p class="s">{n(nat['foreign'])} of {n(nat['postdocs'])}</p></div>
  <div class="stat"><div class="n">{n(nat['us'])}</div>
    <p class="l">are American</p>
    <p class="s">citizens and permanent residents, {100 - nat['share']:.1f}%</p></div>
  <div class="stat"><div class="n">{nat['federally_supported_share']}%</div>
    <p class="l">are federally supported</p>
    <p class="s">{n(nat['federally_supported'])} posts on federal money</p></div>
</div>

<section class="block" id="the-finding">
<h2>Americans are a minority of the postdoctoral workforce</h2>
<p class="lede">Not at nine universities. Nationally.</p>
<p>{nat['share']}% of postdoctoral appointees in the United States hold a
temporary visa. American citizens and permanent residents are
{100 - nat['share']:.1f}% &mdash; a minority of the people doing postdoctoral
research in their own country, in a workforce where about half the posts are
paid for by the federal government.</p>
<p>This is the measured finding. What follows is what it means for the nine
universities named in October.</p>
</section>

<section class="block" id="the-nine">
<h2>The nine named universities</h2>
<p class="lede">On 8 October 2026 the Department of Labor and the Department of
Justice announced an investigation into J-1 visa use at nine universities, and
said that about 61% of postdoctoral researchers and federally funded workers
at those institutions are foreign nationals, against a national average of
38%.</p>
<p>The first figure checks out. Computed from the NSF survey, the nine come to
<strong>{named['share']}%</strong>: {n(named['foreign'])} of
{n(named['postdocs'])} postdocs on a temporary visa.</p>
<p>The second figure does not match this survey. The national average on the
same measure is <strong>{nat['share']}%</strong>, not 38%. The two numbers
count different things, and the difference decides what the story is.</p>

<div class="cmp">
  <div class="stat"><div class="n">{named['share']}%</div>
    <p class="l">the nine named universities</p>
    <p class="s">{n(named['foreign'])} of {n(named['postdocs'])} postdocs on a temporary visa</p></div>
  <div class="stat"><div class="n">{nat['share']}%</div>
    <p class="l">every institution in the survey</p>
    <p class="s">{n(nat['foreign'])} of {n(nat['postdocs'])}</p></div>
</div>

<div class="callout">
<p><strong>The nine are not outliers. They are typical.</strong> They sit about
{named['share'] - nat['share']:.1f} points above a national figure that is
already over half.</p>
<p>That is the larger finding. If these nine were far above a low national
average, this would be a story about nine universities and an enforcement
action would address it. They are not. On this measure the American
postdoctoral workforce is a minority of itself everywhere, and the nine named
institutions look much like the rest of the country.</p>
</div>

<div class="table-wrap">
<table class="t">
<thead><tr><th>Institution</th><th class="num">Postdocs</th>
<th class="num">Temporary visa</th><th class="num">American</th>
<th class="num">Share foreign</th></tr></thead>
<tbody>
"""]
    for r in named["institutions"]:
        p.append(f'<tr class="named"><td>{E(r["named_as"])}</td>'
                 f'<td class="num">{n(r["postdocs"])}</td>'
                 f'<td class="num">{n(r["foreign"])}</td>'
                 f'<td class="num">{n(r["us"])}</td>'
                 f'<td class="num">{r["share"]}%</td></tr>')
    p.append(f"""</tbody>
<tfoot><tr><th>The nine together</th><th class="num">{n(named['postdocs'])}</th>
<th class="num">{n(named['foreign'])}</th>
<th class="num">{n(named['postdocs'] - named['foreign'])}</th>
<th class="num">{named['share']}%</th></tr>
<tr><th>Every institution surveyed</th><th class="num">{n(nat['postdocs'])}</th>
<th class="num">{n(nat['foreign'])}</th><th class="num">{n(nat['us'])}</th>
<th class="num">{nat['share']}%</th></tr></tfoot>
</table>
</div>
<p class="note">Institutions are matched on their federal UNITID, not on their
name. The investigation was announced on 8 October 2026. This page reports
that it was announced and what the survey counts. It makes no claim that any
institution broke a law.</p>
</section>

<section class="block" id="ranking">
<h2>The institutions with the highest shares</h2>
<p class="lede">Every institution reporting at least {d['ranking']['floor']}
postdocs, ranked by the share holding a temporary visa. The nine named
universities are shown in bold where they appear.</p>
""")
    named_ids = {r["unitid"] for r in named["institutions"]}
    for r in d["ranking"]["top"][:25]:
        p.append(bar(f"{r['institution']} ({n(r['postdocs'])})", r["share"],
                     r["unitid"] in named_ids))
    p.append(f"""<div class="scale"><span></span>
  <span class="ticks"><span>0%</span><span>25%</span><span>50%</span>
  <span>75%</span><span>100%</span></span><span></span></div>
<p class="note">{n(d['ranking']['ranked_institutions'])} institutions clear the
floor of {d['ranking']['floor']} postdocs. A unit with nine postdocs and six on
a visa is 67% and tells a reader nothing, which is why the floor exists.</p>
</section>

<section class="block" id="federal">
<h2>Who pays for the posts</h2>
<p class="lede">{nat['federally_supported_share']}% of postdoctoral
appointments are federally supported &mdash; {n(nat['federally_supported'])}
posts.</p>
<div class="table-wrap">
<table class="t">
<thead><tr><th>Federal source</th><th class="num">Postdocs supported</th></tr></thead>
<tbody>
""")
    for agency, v in sorted(d["federal_support_by_agency"].items(),
                            key=lambda kv: -kv[1]):
        p.append(f'<tr><td>{E(agency)}</td><td class="num">{n(v)}</td></tr>')
    p.append("""</tbody></table>
</div>
<p class="note">The survey reports how many postdocs are federally supported
and how many hold a temporary visa. It does not report how many are both, so
these two figures cannot be multiplied. A page that multiplied them would be
inventing a number the survey does not contain.</p>
</section>

<section class="block" id="method">
<h2>Method and limits</h2>
<p class="lede">What this counts, and what it cannot.</p>
<ul class="lede">
""")
    for c in d["caveats"]:
        p.append(f"<li>{E(c)}</li>")
    p.append(f"""</ul>
<p class="note">Source: {E(d['source'])}, {E(year)}.
<a href="{E(d['source_url'])}">{E(d['source_url'])}</a>. Built by
<code>scripts/build_postdoc_citizenship.py</code> from the institution
microdata, summed from organisational units to institutions.</p>
</section>
</main>
<script src="/analytics-beacon.js" defer></script>
<script src="/anchors.js" defer></script>
<script src="/sidebar.js"></script>
</body>
</html>
""")
    write_text(OUT, "".join(p))
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  national {nat['share']}% foreign, the nine {named['share']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
