#!/usr/bin/env python3
"""The five critical-industry pages, and the hub that compares them.

One template, six pages: /industries.html plus one per industry. Generated
rather than hand-written because five pages that drift apart are five pages
nobody trusts -- and because every figure has to come from
site/data/critical_industries.json at build time, so a rebuild moves the pages
and a stale number cannot survive one.

Nothing here decides anything. The industry list, the CIP map, the gating note
and the caveats all live in the builder; this file only lays them out.

Usage:
    python3 scripts/build_industry_pages.py
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data" / "critical_industries.json"
SITE = ROOT / "site"
SUBDIR = SITE / "industries"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                          # noqa: E402

E = html.escape


def P(text: str) -> str:
    """Escaped prose. The builders write ASCII, where a dash is "--"; set it
    properly for display rather than leaving "--" on the page."""
    return html.escape(str(text)).replace(" -- ", " &mdash; ")


def head(title: str, desc: str) -> str:
    """Everything a page on this site needs. sidebar.js pulls in the shared
    navigation and the chat widget; the deploy pass adds the theme tokens."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:image" content="https://phd-demographics.andy-barr.com/og/concentration.png">
<link rel="stylesheet" href="/style.css">
<style>
  .wrap {{ max-width: 1120px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}
  .page-head h1 {{ font-size: 1.9rem; margin: 0 0 .7rem; line-height: 1.2; max-width: 24ch; }}
  .page-head p {{ color: var(--text-muted); max-width: 70ch; line-height: 1.65; font-size: .95rem; margin: 0 0 .5rem; }}
  .kicker {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; color: var(--text-muted); margin: 0 0 .6rem; }}
  .stats {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .8rem; margin: 1.6rem 0 0; }}
  .stat {{ border: 1px solid var(--border); border-radius: 10px; padding: .9rem 1rem; background: var(--surface); }}
  .stat .n {{ font-size: 1.7rem; font-weight: 800; color: var(--hl); line-height: 1.1; font-variant-numeric: tabular-nums; }}
  .stat .l {{ font-size: .82rem; line-height: 1.45; margin: .3rem 0 0; }}
  .stat .s {{ font-size: .72rem; color: var(--text-muted); margin: .45rem 0 0; }}
  @media (max-width: 900px) {{ .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
  @media (max-width: 480px) {{ .stats {{ grid-template-columns: 1fr; }} }}
  section.block {{ margin-top: 2.8rem; border-top: 1px solid var(--border); padding-top: 1.6rem; }}
  section.block h2 {{ font-size: 1.2rem; margin: 0 0 .45rem; }}
  .lede {{ color: var(--text-muted); max-width: 72ch; line-height: 1.6; font-size: .92rem; margin: 0 0 1rem; }}
  .note {{ color: var(--text-muted); font-size: .78rem; line-height: 1.55; max-width: 80ch; margin: .8rem 0 0; overflow-wrap: anywhere; }}
  .table-wrap {{ overflow-x: auto; border: 1px solid var(--border); border-radius: 10px; }}
  table.t {{ width: 100%; border-collapse: collapse; font-size: .84rem; }}
  table.t th {{ text-align: left; padding: .6rem .7rem; font-size: .7rem; text-transform: uppercase;
    letter-spacing: .05em; color: var(--text-muted); font-weight: 600; border-bottom: 1px solid var(--border); white-space: nowrap; }}
  table.t td {{ padding: .55rem .7rem; border-bottom: 1px solid var(--border); }}
  table.t td.num, table.t th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  table.t tr:last-child td {{ border-bottom: none; }}
  .share {{ font-weight: 700; color: var(--hl); }}
  .muted {{ color: var(--text-muted); }}
  .pill {{ display: inline-block; font-size: .7rem; border: 1px solid var(--border); border-radius: 999px;
    padding: .05rem .5rem; color: var(--text-muted); white-space: nowrap; }}
  .pill.gated {{ border-color: var(--hl); color: var(--hl); font-weight: 600; }}
  .gate {{ border-left: 3px solid var(--hl); background: var(--surface); border-radius: 0 10px 10px 0;
    padding: .9rem 1.1rem; margin: 1.2rem 0 0; }}
  .gate h3 {{ font-size: .85rem; margin: 0 0 .4rem; }}
  .gate p {{ font-size: .85rem; line-height: 1.6; margin: 0; color: var(--text-muted); }}
  .proxy {{ border: 1px dashed var(--border); border-radius: 10px; padding: .9rem 1.1rem; margin: 1.2rem 0 0; }}
  .proxy h3 {{ font-size: .8rem; margin: 0 0 .4rem; text-transform: uppercase; letter-spacing: .05em; color: var(--text-muted); }}
  .proxy p {{ font-size: .85rem; line-height: 1.6; margin: 0; }}
  /* The industry cards on the hub. */
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: .8rem; margin: 1.4rem 0 0; }}
  .card {{ border: 1px solid var(--border); border-radius: 10px; padding: 1rem 1.1rem; background: var(--surface);
    display: flex; flex-direction: column; gap: .45rem; text-decoration: none; color: inherit; }}
  .card:hover {{ border-color: var(--hl); }}
  .card .pc {{ font-size: 2rem; font-weight: 800; color: var(--hl); line-height: 1; font-variant-numeric: tabular-nums; }}
  .card .nm {{ font-size: .95rem; font-weight: 700; }}
  .card .sub {{ font-size: .76rem; color: var(--text-muted); line-height: 1.45; }}
  /* Share by year. One axis, every line directly labelled. */
  .chart {{ margin: 1.2rem 0 0; }}
  .chart svg {{ width: 100%; height: auto; max-width: 100%; display: block; }}
  .chart .gl {{ stroke: var(--border); stroke-width: 1; }}
  .chart .ln {{ fill: none; stroke: var(--hl); stroke-width: 2; }}
  .chart .base {{ fill: none; stroke: var(--text-muted); stroke-width: 1.5; stroke-dasharray: 4 3; opacity: .7; }}
  .chart text {{ fill: var(--text-muted); font-size: 10px; }}
  .chart text.lab {{ fill: var(--text); font-size: 11px; font-weight: 600; }}
  .caveats {{ border-left: 2px solid var(--border); padding: .1rem 0 .1rem 1rem; margin: 1.2rem 0 0; }}
  .caveats li {{ color: var(--text-muted); font-size: .8rem; line-height: 1.6; max-width: 80ch; overflow-wrap: anywhere; }}
  a {{ color: var(--accent); }}
</style>
  <script id="phd-theme-boot">(function(){{try{{var t=localStorage.getItem("phd-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
  <script defer src="/theme.js"></script>
</head>
"""


FOOT = """<script src="/sidebar.js" defer></script>
</body>
</html>
"""


def line_chart(series: dict, baseline: float | None, label: str) -> str:
    """Share by year as an inline SVG. No library, no runtime fetch.

    Drawn against one scale, 0-100, with the last point labelled in place so
    the reader never has to match a colour to a legend.
    """
    pts = [(int(y), v) for y, v in sorted(series.items()) if v is not None]
    if len(pts) < 3:
        return ""
    # Right padding has to hold the baseline caption ("all fields 27.0%"),
    # which at 54px was clipped to "all fields 2". The last year label sits
    # inside the plot for the same reason.
    W, H, PL, PR, PT, PB = 760, 230, 34, 96, 14, 26
    x0, x1 = pts[0][0], pts[-1][0]
    span = max(1, x1 - x0)
    def X(y): return PL + (y - x0) / span * (W - PL - PR)
    def Y(v): return PT + (100 - v) / 100 * (H - PT - PB)
    grid = "".join(
        f'<line class="gl" x1="{PL}" y1="{Y(v):.1f}" x2="{W-PR}" y2="{Y(v):.1f}"/>'
        f'<text x="{PL-6}" y="{Y(v)+3:.1f}" text-anchor="end">{v}%</text>'
        for v in (0, 25, 50, 75, 100))
    path = "M" + " L".join(f"{X(y):.1f},{Y(v):.1f}" for y, v in pts)
    base = ""
    if baseline is not None:
        base = (f'<path class="base" d="M{PL},{Y(baseline):.1f} L{W-PR},{Y(baseline):.1f}"/>'
                f'<text x="{W-PR+4}" y="{Y(baseline)+3:.1f}">all fields {baseline}%</text>')
    last_y, last_v = pts[-1]
    years = "".join(
        f'<text x="{X(y):.1f}" y="{H-8}" text-anchor="{a}">{y}</text>'
        for y, a in ((x0, "start"), ((x0 + x1) // 2, "middle"), (x1, "end")))
    return (f'<div class="chart"><svg viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="{E(label)} non-resident share by year, {x0} to {x1}">'
            f'{grid}{base}<path class="ln" d="{path}"/>'
            f'<circle cx="{X(last_y):.1f}" cy="{Y(last_v):.1f}" r="4" fill="var(--hl)"/>'
            f'<text class="lab" x="{X(last_y)-8:.1f}" y="{Y(last_v)-14:.1f}" text-anchor="end">{last_v}%</text>'
            f'{years}</svg></div>')


def hub(d: dict) -> str:
    inds = d["industries"]
    nat = d["national"]
    cards = "".join(
        f'<a class="card" href="{E(i["url"])}" data-track="industry.{E(i["slug"])}">'
        f'<span class="pc">{i["share"]}%</span>'
        f'<span class="nm">{E(i["name"])}</span>'
        f'<span class="sub">{i["doctorates"]:,} doctorates at {i["institutions"]} '
        f'institutions</span>'
        + (f'<span class="pill">{E(i["restriction"])}</span>' if i["restriction"] else "")
        + '</a>' for i in inds)
    rows = "".join(
        f'<tr><td><a href="{E(i["url"])}">{E(i["name"])}</a></td>'
        f'<td class="num share">{i["share"]}%</td>'
        f'<td class="num">{i["doctorates"]:,}</td>'
        f'<td class="num muted">{i["institutions"]}</td>'
        f'<td class="muted">{E(i["restriction"] or "&mdash;")}</td>'
        f'<td class="muted">{E(", ".join(i["cips"]))}</td></tr>' for i in inds)
    notes = "".join(
        f'<tr><td>{E(i["name"])}</td>'
        f'<td class="muted">{E(i["restriction"] or "None by default")}</td>'
        f'<td>{P(i["restriction_note"])}</td></tr>' for i in inds)
    return (head("Critical industries",
                 "Who the United States trains to run the industries it cannot offshore: "
                 "mining, petroleum, aerospace, battery technology and nuclear, by "
                 "non-resident share of research doctorates.")
            + '<body data-page="industries">\n<main id="main">\n<div class="wrap">\n'
            f'''
  <header class="page-head">
    <p class="kicker">Federal records: NCES IPEDS Completions, {d["window"]["from"]}&ndash;{d["window"]["to"]}</p>
    <h1 id="critical-industries">Five industries the country cannot offshore</h1>
    <p>An ore body is where it is. So is a well, an airframe line, a cell plant and a
      reactor. The work has to be done here, by people who are here. This page asks
      who the United States is training to do it.</p>
    <p>Each share below is the non-resident share of the research doctorates awarded
      in that field. The national figure across all fields is <strong>{nat["share"]}%</strong>.
      Every one of these five runs above it, and petroleum runs higher than any other
      field on this site.</p>
    <div class="cards">{cards}</div>
  </header>

  <section class="block" id="all">
    <h2>All five, side by side</h2>
    <div class="table-wrap"><table class="t">
      <thead><tr><th>Industry</th><th class="num">Non-resident share</th>
        <th class="num">Doctorates</th><th class="num">Institutions</th>
        <th>Federal access regime</th><th>CIP codes used</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    <p class="note">Pooled over {d["window"]["from"]}&ndash;{d["window"]["to"]}. Each industry
      page lists the programmes behind its number and the institutions that award them.</p>
  </section>

  <section class="block" id="restrictions">
    <h2>What restricts this work, precisely</h2>
    <p class="lede">Some of this work carries federal access restrictions. Three different
      regimes get run together under the word &ldquo;clearance&rdquo;, and they are not the
      same thing. Export control turns on
      <strong>U.S. person</strong> status (22 CFR 120.62), which <strong>includes lawful
      permanent residents</strong> &mdash; it is not a clearance and does not require
      citizenship. Unescorted access at a commercial reactor (10 CFR 73.56) is a background
      and fitness-for-duty determination, also not a clearance. A <strong>security
      clearance</strong> is eligibility for access to classified information under EO 12968
      and SEAD 4; DOE&rsquo;s L and Q authorisations (10 CFR 710) are of that kind and do
      require citizenship.</p>
    <div class="table-wrap"><table class="t">
      <thead><tr><th>Industry</th><th>Regime</th><th>What it actually says</th></tr></thead>
      <tbody>{notes}</tbody></table></div>
    <p class="note">One consequence is worth stating because it is easy to get backwards.
      IPEDS counts a permanent resident as domestic, so every non-resident alien in these
      figures is on a temporary visa and is therefore outside the U.S.-person definition
      that export control uses. That is a statement about what the rules say, not about who
      was hired: this data records a degree awarded and nothing more.</p>
  </section>

  <section class="block" id="method">
    <h2>Method and limits</h2>
    <p class="lede">A CIP code is a field of study. It is not an industry, and nobody in this
      data is observed working anywhere. The mapping from field to industry is this
      site&rsquo;s, and every page shows the codes it used so the mapping can be argued with.</p>
    <ul class="caveats">{"".join(f"<li>{P(c)}</li>" for c in d["caveats"])}</ul>
    <p class="note">Built by <code>scripts/build_critical_industries.py</code> and
      <code>scripts/build_industry_pages.py</code> from
      <a href="{E(d["source_url"])}" target="_blank" rel="noopener noreferrer">{E(d["source"])}</a>.</p>
  </section>

</div>
</main>
''' + FOOT)


def page(i: dict, d: dict) -> str:
    nat = d["national"]
    progs = "".join(
        f'<tr><td>{E(p["title"])}<div class="muted" style="font-size:.74rem">CIP {E(p["cip"])}</div></td>'
        f'<td class="num share">{p["share"]}%</td><td class="num">{p["doctorates"]:,}</td>'
        f'<td class="num muted">{p["nra"]:,}</td></tr>' for p in i["programmes"])
    schools = "".join(
        f'<tr><td>{E(s["name"])}</td><td class="num share">{s["share"]}%</td>'
        f'<td class="num">{s["doctorates"]:,}</td><td class="num muted">{s["nra"]:,}</td></tr>'
        for s in i["top_schools"])
    # Named for the regime that actually applies. "Clearance" is a specific
    # thing -- eligibility for classified information under EO 12968 -- and
    # almost none of this work is that, so the word does not appear here.
    gate = (f'<div class="gate"'
            f'{"" if i["restriction"] else " style=\"border-left-color:var(--border)\""}>'
            f'<h3>{E(i["restriction"] or "No federal access restriction by default")}</h3>'
            f'<p>{P(i["restriction_note"])}</p></div>')
    proxy = (f'<div class="proxy"><h3>This category is ours, not the government&rsquo;s</h3>'
             f'<p>{P(i["proxy"])}</p></div>' if i.get("proxy") else "")
    diff = round(i["share"] - nat["share"], 1)
    return (head(f'{i["name"]} — critical industries',
                 f'{i["name"]}: {i["share"]}% of US research doctorates in this field go to '
                 f'non-residents, against {nat["share"]}% across all fields. The programmes, '
                 f'the institutions, and whether the work requires citizenship.')
            + f'<body data-page="industry-{E(i["slug"])}">\n<main id="main">\n<div class="wrap">\n'
            f'''
  <header class="page-head">
    <p class="kicker"><a href="/industries.html">Critical industries</a> &middot;
      NCES IPEDS, {d["window"]["from"]}&ndash;{d["window"]["to"]}</p>
    <h1 id="{E(i["slug"])}">{E(i["name"])}</h1>
    <p>{P(i["why"])}</p>
    <div class="stats">
      <div class="stat"><p class="n">{i["share"]}%</p><p class="l">of research doctorates in
        this field go to non-residents</p>
        <p class="s">{"+" if diff > 0 else ""}{diff} points against the
          {nat["share"]}% national figure</p></div>
      <div class="stat"><p class="n">{i["doctorates"]:,}</p><p class="l">doctorates awarded in
        the window</p><p class="s">{i["nra"]:,} of them to non-residents</p></div>
      <div class="stat"><p class="n">{i["institutions"]}</p><p class="l">institutions award
        this doctorate at all</p><p class="s">the whole national capacity</p></div>
      <div class="stat"><p class="n" style="font-size:1.1rem">{E(i["restriction"] or "None")}</p>
        <p class="l">federal access regime on the work itself</p>
        <p class="s">{"not a security clearance &mdash; see below" if i["restriction"] else "no export-control or access regime by default"}</p></div>
    </div>
    {gate}
    {proxy}
  </header>

  <section class="block" id="trend">
    <h2>The share since {min(i["series"]) if i["series"] else ""}</h2>
    <p class="lede">Non-resident share of the doctorates awarded each year, against the
      national figure for all fields.</p>
    {line_chart(i["series"], nat["share"], i["name"])}
    <p class="note">The line runs the full published history. The headline
      <strong>{i["share"]}%</strong> above is pooled over {d["window"]["from"]}&ndash;{d["window"]["to"]},
      the window this site uses everywhere, so the two figures answer different
      questions and will not match. Years with fewer than 20 doctorates nationally are
      omitted, because a share computed on a dozen degrees moves on one student.</p>
  </section>

  <section class="block" id="programmes">
    <h2>The programmes behind the number</h2>
    <p class="lede">Every CIP code this page counts, and what each contributes. Disagree with
      the mapping and you can see exactly which rows to drop.</p>
    <div class="table-wrap"><table class="t">
      <thead><tr><th>Programme</th><th class="num">Non-resident share</th>
        <th class="num">Doctorates</th><th class="num">Non-residents</th></tr></thead>
      <tbody>{progs}</tbody></table></div>
  </section>

  <section class="block" id="schools">
    <h2>Where it is taught</h2>
    <p class="lede">The institutions awarding these doctorates, largest first. Ten or more
      over the window.</p>
    <div class="table-wrap"><table class="t">
      <thead><tr><th>Institution</th><th class="num">Non-resident share</th>
        <th class="num">Doctorates</th><th class="num">Non-residents</th></tr></thead>
      <tbody>{schools}</tbody></table></div>
  </section>

  <section class="block" id="method">
    <h2>Method and limits</h2>
    <ul class="caveats">{"".join(f"<li>{P(c)}</li>" for c in d["caveats"])}</ul>
    <p class="note">Built by <code>scripts/build_critical_industries.py</code> from
      <a href="{E(d["source_url"])}" target="_blank" rel="noopener noreferrer">{E(d["source"])}</a>.
      Compare the other four on <a href="/industries.html">the hub</a>.</p>
  </section>

</div>
</main>
''' + FOOT)


def main() -> int:
    if not DATA.exists():
        print(f"  missing {DATA.relative_to(ROOT)}; run build_critical_industries.py")
        return 1
    d = json.loads(DATA.read_text())
    SUBDIR.mkdir(parents=True, exist_ok=True)
    write_text(SITE / "industries.html", hub(d))
    for i in d["industries"]:
        write_text(SUBDIR / f'{i["slug"]}.html', page(i, d))
    print(f"  wrote site/industries.html and {len(d['industries'])} industry pages:")
    for i in d["industries"]:
        print(f"    {i['url']:<34}{i['share']}%  {i['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
