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
        + ('<span class="pill">Declared proxy</span>' if i.get("proxy") else "")
        + '</a>' for i in inds)
    rows = "".join(
        f'<tr><td><a href="{E(i["url"])}">{E(i["name"])}</a></td>'
        f'<td class="num share">{i["share"]}%</td>'
        f'<td class="num">{i["doctorates"]:,}</td>'
        f'<td class="num muted">{i["institutions"]}</td>'
        f'<td class="muted">{E(i["restriction"]) if i["restriction"] else "&mdash;"}'
        f'{" <span class=\'pill\'>proxy</span>" if i.get("proxy") else ""}</td>'
        f'<td class="muted">{E(", ".join(i["cips"]))}</td></tr>' for i in inds)
    notes = "".join(
        f'<tr><td>{E(i["name"])}</td>'
        f'<td class="muted">{E(i["restriction"] or "None by default")}</td>'
        f'<td>{P(i["restriction_note"])}</td></tr>' for i in inds)
    names = ", ".join(i["name"].lower() for i in inds[:-1]) + f' and {inds[-1]["name"].lower()}'
    return (head("Critical industries",
                 "Who the United States trains to run the industries it cannot offshore: "
                 f"{names}, by non-resident share of research doctorates.")
            + '<body data-page="industries">\n<main id="main">\n<div class="wrap">\n'
            f'''
  <header class="page-head">
    <p class="kicker">Federal records: NCES IPEDS Completions, {d["window"]["from"]}&ndash;{d["window"]["to"]}</p>
    <h1 id="critical-industries">The industries the country cannot offshore</h1>
    <p>An ore body is where it is. So is a well, an airframe line, a cell plant and a
      reactor. The work has to be done here, by people who are here. This page asks
      who the United States is training to do it.</p>
    <p>Each share below is the non-resident share of the research doctorates awarded
      in that field. The national figure across all fields is <strong>{nat["share"]}%</strong>.
      All {len(inds)} of them run above it.</p>
    <div class="cards">{cards}</div>
  </header>

  <section class="block" id="all">
    <h2>All {len(inds)}, side by side</h2>
    <div class="table-wrap"><table class="t">
      <thead><tr><th>Industry</th><th class="num">Non-resident share</th>
        <th class="num">Doctorates</th><th class="num">Institutions</th>
        <th>Federal access regime</th><th>CIP codes used</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    <p class="note">Pooled over {d["window"]["from"]}&ndash;{d["window"]["to"]}. Each industry
      page lists the programmes behind its number and the institutions that award them.</p>
  </section>

  <section class="block" id="grid">
    <h2>Who runs it, once it is built</h2>
    <p class="lede">These {len(inds)} fields are measured by who gets the doctorate. The
      grid itself is not. Electrician and lineworker credentials go almost entirely to
      Americans, so the question there is not who but how many.</p>
    <p><a href="/industries/grid">The grid workforce &rarr;</a></p>
  </section>

  <section class="block" id="restrictions">
    <h2>A note on federal access rules</h2>
    <p class="lede">Some of this work carries federal access restrictions, and they are
      often described loosely. Export control under ITAR turns on &ldquo;U.S. person&rdquo;
      status, which includes lawful permanent residents. Unescorted access at a commercial
      reactor is a background check. Neither is a security clearance, and only a DOE L or Q
      authorisation requires citizenship.</p>
    <p class="lede">It makes less difference than it sounds. These rules govern particular
      work, not a field of study, and they have not stopped the shares on this page from
      rising. They are recorded here for accuracy and are not the argument.</p>
    <div class="table-wrap"><table class="t">
      <thead><tr><th>Industry</th><th>Regime</th><th>What it says</th></tr></thead>
      <tbody>{notes}</tbody></table></div>
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
    # The newest published point, so the fourth card says something the other
    # three do not. It previously repeated the non-resident count from card two.
    pts = sorted((int(y), v) for y, v in i["series"].items() if v is not None)
    latest_year = pts[-1][0] if pts else d["window"]["to"]
    latest_share = f'{pts[-1][1]}%' if pts else "&mdash;"
    # Public statements about this workforce, checked against the same federal
    # file the rest of the page is built from. Mining only, because that is
    # what the statements are about.
    claims = ""
    if i["slug"] == "mining" and d.get("public_record"):
        blocks = []
        for c in d["public_record"]:
            rows = "".join(
                f'<tr><td>{E(ch["label"])}<div class="muted" style="font-size:.74rem">'
                f'CIP {E(", ".join(ch["cip"]))}, {ch["year"]}</div></td>'
                f'<td class="num muted">{E(str(ch["stated"]))}</td>'
                f'<td class="num share">{ch["found"]:,}</td></tr>'
                for ch in c.get("checks", []))
            table = (f'<div class="table-wrap" style="margin-top:.7rem"><table class="t">'
                     f'<thead><tr><th>What the federal data measures</th>'
                     f'<th class="num">On the record</th><th class="num">IPEDS</th></tr></thead>'
                     f'<tbody>{rows}</tbody></table></div>' if rows else "")
            un = (f'<p class="note">{P(c["outside_scope"])}</p>'
                  if c.get("outside_scope") else "")
            if c.get("scope_note"):
                un += f'<p class="note">{P(c["scope_note"])}</p>' 
            blocks.append(
                f'<div class="proxy" style="border-style:solid;margin-top:1rem">'
                f'<h3>{E(c["speaker"])} &middot; {E(c["date"])}</h3>'
                f'<p><em>&ldquo;{E(c["quote"])}&rdquo;</em></p>{table}{un}'
                f'<p class="note"><a href="{E(c["source_url"])}" target="_blank" '
                f'rel="noopener noreferrer">Source</a> &middot; {P(c["source_note"])}</p></div>')
        claims = (
            '<section class="block" id="current-state">'
            '<h2>The current state, on the record</h2>'
            '<p class="lede">What is being said about this workforce, with the federal figures '
            'that sit beside it. The statements are fixed. The figures are recomputed '
            'from IPEDS on every build, so the two cannot drift apart.</p>' + "".join(blocks) + '</section>')
    levels = "".join(
        f'<tr><td>{E(l["level"])}</td>'
        f'<td class="num">{l["domestic"]:,}</td>'
        f'<td class="num share">{l["domestic_share"]}%</td>'
        f'<td class="num muted">{l["nra"]:,}</td>'
        f'<td class="num muted">{l["awards"]:,}</td></tr>' for l in i["levels"])
    # The sentence the table is for, built from the table's own two ends.
    by_lvl = {l["level"]: l for l in i["levels"]}
    b, m = by_lvl.get("Bachelor's"), by_lvl.get("Master's")
    if b and m:
        drop = round(b["domestic_share"] - m["domestic_share"], 1)
        # Describe the gap this field actually has. The old wording asserted
        # that the graduate pipeline "is not American" regardless of the
        # numbers, which on nuclear sat directly under 86.7% American.
        if drop >= 20:
            shape = (f'The American share falls <strong>{drop} points</strong> between the '
                     f'two, and the graduate degree is the one these industries hire from.')
        elif drop > 0:
            shape = (f'The American share falls {drop} points between the two, a smaller '
                     f'gap than most fields on this site show.')
        else:
            shape = ('The American share does not fall between the two. This field is an '
                     'exception to the pattern the rest of the site finds.')
        level_note = (
            f'Americans take <strong>{b["domestic_share"]}%</strong> of the '
            f'{b["awards"]:,} bachelor&rsquo;s degrees in this field and '
            f'<strong>{m["domestic_share"]}%</strong> of the {m["awards"]:,} '
            f'master&rsquo;s degrees. {shape} '
            f'See <a href="/expansion">the master&rsquo;s expansion</a> for the '
            f'same comparison across every field. A row resting on a few dozen awards '
            f'moves on one student, so read the small ones with the award count beside '
            f'them.')
    else:
        level_note = ("Awards are from the newest IPEDS Completions release, first-major "
                      "rows only.")
    return (head(f'{i["name"]} — critical industries',
                 f'{i["name"]}: {i["share"]}% of US research doctorates in this field go to '
                 f'non-residents, against {nat["share"]}% across all fields. The programmes '
                 f'behind that number, the institutions awarding them, and the award level at '
                 f'which the American share falls away.')
            + f'<body data-page="industry-{E(i["slug"])}">\n<main id="main">\n<div class="wrap">\n'
            f'''
  <header class="page-head">
    <p class="kicker"><a href="/industries">Critical industries</a> &middot;
      NCES IPEDS, {d["window"]["from"]}&ndash;{d["window"]["to"]}</p>
    <h1 id="{E(i["slug"])}">{E(i["name"])}</h1>
    <p>{P(i["why"])}</p>
    <div class="stats">
      <div class="stat"><p class="n">{i["share"]}%</p><p class="l">of research doctorates in
        {"the programmes counted here" if i.get("proxy") else "this field"} go to
        non-residents</p>
        <p class="s">{"+" if diff > 0 else ""}{diff} points against the
          {nat["share"]}% national figure</p></div>
      <div class="stat"><p class="n">{i["doctorates"]:,}</p><p class="l">doctorates awarded in
        the window</p><p class="s">{i["nra"]:,} of them to non-residents</p></div>
      <div class="stat"><p class="n">{i["institutions"]}</p><p class="l">institutions award
        {"these doctorates" if i.get("proxy") else "this doctorate"} at all</p>
        <p class="s">{"the capacity of the proxy, not of battery work" if i.get("proxy") else "the whole national capacity"}</p></div>
      <div class="stat"><p class="n">{latest_share}</p>
        <p class="l">the share in {latest_year}, the most recent year published</p>
        <p class="s">{"federal access rules apply to some of this work; see the note below" if i["restriction"] else "no federal access regime applies by default"}</p></div>
    </div>
    {gate}
    {proxy}
  </header>

  {claims}

  <section class="block" id="levels">
    <h2>The American share, by award level</h2>
    <p class="lede">The same field at three levels, in {d["level_year"]}. The subject does not
      change. Only the level does.</p>
    <div class="table-wrap"><table class="t">
      <thead><tr><th>Level</th><th class="num">Awarded to Americans</th>
        <th class="num">Share American</th><th class="num">Awarded to non-residents</th>
        <th class="num">Total</th></tr></thead>
      <tbody>{levels}</tbody></table></div>
    <p class="note">{level_note}</p>
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

  <section class="block" id="trend">
    <h2>The share since {min(i["series"]) if i["series"] else ""}</h2>
    <p class="lede">Non-resident share of the doctorates awarded each year, against the
      national figure for all fields.</p>
    {line_chart(i["series"], nat["share"], i["name"])}
    <p class="note">The line runs the full published history. The headline
      <strong>{i["share"]}%</strong> above is pooled over
      {d["window"]["from"]}&ndash;{d["window"]["to"]}. That is the window this site uses
      everywhere. The two figures answer different questions and will not match. Years
      with fewer than 20 doctorates nationally are omitted: a share computed on a dozen
      degrees moves on one student.</p>
  </section>

  <section class="block" id="method">
    <h2>Method and limits</h2>
    <ul class="caveats">{"".join(f"<li>{P(c)}</li>" for c in d["caveats"])}</ul>
    <p class="note">Built by <code>scripts/build_critical_industries.py</code> from
      <a href="{E(d["source_url"])}" target="_blank" rel="noopener noreferrer">{E(d["source"])}</a>.
      Compare the others on <a href="/industries">the hub</a>.</p>
  </section>

</div>
</main>
''' + FOOT)


def grid(g: dict) -> str:
    """The capacity page. Counts, never shares -- see build_grid_capacity.py."""
    t = g["totals"]
    scarce = "".join(
        f'<tr><td>{E(p["title"])}<div class="muted" style="font-size:.74rem">'
        f'CIP {E(p["cip"])}</div></td>'
        f'<td class="num share">{p["latest_awards"]:,}</td>'
        f'<td class="num muted">{p["institutions"]}</td></tr>' for p in g["scarcest"])
    groups = ""
    for grp in g["groups"]:
        rows = "".join(
            f'<tr><td>{E(p["title"])}<div class="muted" style="font-size:.74rem">'
            f'CIP {E(p["cip"])}</div></td>'
            f'<td class="num">{p["latest_awards"]:,}</td>'
            f'<td class="num muted">{p["institutions"]}</td>'
            f'<td class="num">{"&mdash;" if p["change_10y"] is None else ("+" if p["change_10y"] > 0 else "") + str(p["change_10y"]) + "%"}</td>'
            f'<td class="num muted">{p["nra_share"]}%</td></tr>'
            for p in grp["programmes"] if p["latest_awards"])
        groups += (f'<h3 style="font-size:.95rem;margin:1.6rem 0 .5rem">{E(grp["group"])}'
                   f' <span class="muted" style="font-weight:400;font-size:.8rem">'
                   f'&middot; {grp["latest_awards"]:,} awards, '
                   f'{grp["nra_share"]}% non-resident</span></h3>'
                   f'<div class="table-wrap"><table class="t"><thead><tr>'
                   f'<th>Programme</th><th class="num">Awards, {g["latest_year"]}</th>'
                   f'<th class="num">Institutions</th><th class="num">10-year change</th>'
                   f'<th class="num">Non-resident</th></tr></thead>'
                   f'<tbody>{rows}</tbody></table></div>')
    # The two sentences this page exists to support, built from its own data.
    def prog(cip):
        return next((p for grp in g["groups"] for p in grp["programmes"]
                     if p["cip"] == cip), None)
    pp, nuc = prog("15.1702"), prog("41.0205")
    # Typed by hand first, and wrong: the group share (0.6%) was quoted as the
    # electrician figure and swapped with lineworker. Read them instead.
    elec, line = prog("46.0302"), prog("46.0303")
    return (head("The grid workforce",
                 "How many Americans the United States trains to run its energy "
                 "infrastructure: power plant, lineworker, electrician and HVAC "
                 "credentials awarded each year, and how few of them there are.")
            + '<body data-page="grid">\n<main id="main">\n<div class="wrap">\n'
            f'''
  <header class="page-head">
    <p class="kicker"><a href="/industries">Critical industries</a> &middot;
      NCES IPEDS Completions, {g["years"][0]}&ndash;{g["latest_year"]}</p>
    <h1 id="the-grid-workforce">Americans run the grid. Some of these pipelines are
      vanishingly small.</h1>
    <p>Every other page on this site asks who gets the degree. Ask that about the
      electrical grid and the answer is already settled. Electrician credentials are
      <strong>{elec["nra_share"] if elec else "&mdash;"}%</strong> non-resident.
      Lineworker credentials are <strong>{line["nra_share"] if line else "&mdash;"}%</strong>.
      Americans earn essentially all of these credentials.</p>
    <p>So the question worth asking here is not who. It is <strong>how many</strong>.</p>
    <p class="note" style="margin-top:.9rem">Two limits apply to every figure on this
      page, and they apply before the figures are read. This counts credentials awarded,
      not people working: a credential is not a job and not a career. And IPEDS covers
      institutions that take Title IV federal aid, so the trades are undercounted &mdash;
      much electrical and line work is learned in union or employer apprenticeships,
      IBEW and NECA among them, which award no IPEDS credential and appear nowhere here.
      <strong>For the trades these counts are a floor on the pipeline, not the
      pipeline.</strong> The power plant and engineering numbers do not have that
      problem, because colleges award those credentials.</p>
    <div class="stats">
      <div class="stat"><p class="n">{pp["latest_awards"] if pp else "&mdash;"}</p>
        <p class="l">power plant technology credentials awarded in {g["latest_year"]},
          <strong>in the entire country</strong></p>
        <p class="s">at {pp["institutions"] if pp else 0} institutions</p></div>
      <div class="stat"><p class="n">{nuc["latest_awards"] if nuc else "&mdash;"}</p>
        <p class="l">nuclear power technology credentials, every level combined</p>
        <p class="s">{("down " + str(abs(nuc["change_10y"])) + "% in ten years") if nuc and nuc["change_10y"] is not None else ""}</p></div>
      <div class="stat"><p class="n">{t["awards"]:,}</p>
        <p class="l">credentials across every programme on this page</p>
        <p class="s">generation, transmission, the trade and the engineering</p></div>
      <div class="stat"><p class="n">{round(100 - t["nra_share"], 1)}%</p>
        <p class="l">of those credentials went to Americans</p>
        <p class="s">this pipeline is domestic; the question is its size</p></div>
    </div>
  </header>

  <section class="block" id="scarcest">
    <h2>The programmes with the fewest graduates</h2>
    <p class="lede">These are national totals. Not per state, not per region &mdash; the
      whole United States, every award level from a short certificate upward.</p>
    <div class="table-wrap"><table class="t">
      <thead><tr><th>Programme</th><th class="num">Awards, {g["latest_year"]}</th>
        <th class="num">Institutions</th></tr></thead>
      <tbody>{scarce}</tbody></table></div>
    <p class="note">A programme that awarded nothing in {g["latest_year"]} is left out:
      that is a pipeline that has closed, not a small one.</p>
  </section>

  <section class="block" id="programmes">
    <h2>Every programme, by what it staffs</h2>
    <p class="lede">Awards in the latest year, how many institutions award them, the
      ten-year change, and the non-resident share &mdash; which is small everywhere except
      the engineering.</p>
    {groups}
  </section>

  <section class="block" id="method">
    <h2>Method and limits</h2>
    <p class="lede">This page counts credentials awarded. It does not count workers, and a
      credential is not a career.</p>
    <ul class="caveats">{"".join(f"<li>{P(c)}</li>" for c in g["caveats"])}</ul>
    <p class="note">Built by <code>scripts/build_grid_capacity.py</code> from
      <a href="{E(g["source_url"])}" target="_blank" rel="noopener noreferrer">{E(g["source"])}</a>.
      The composition question &mdash; who gets the degree &mdash; is on
      <a href="/industries">the industry pages</a>.</p>
  </section>

</div>
</main>
''' + FOOT)


def main() -> int:
    if not DATA.exists():
        print(f"  missing {DATA.relative_to(ROOT)}; run build_critical_industries.py")
        return 1
    d = json.loads(DATA.read_text())
    gridded = ROOT / "site" / "data" / "grid_capacity.json"
    SUBDIR.mkdir(parents=True, exist_ok=True)
    write_text(SITE / "industries.html", hub(d))
    for i in d["industries"]:
        write_text(SUBDIR / f'{i["slug"]}.html', page(i, d))
    if gridded.exists():
        write_text(SUBDIR / "grid.html", grid(json.loads(gridded.read_text())))
        print("    /industries/grid.html            the capacity page")
    print(f"  wrote site/industries.html and {len(d['industries'])} industry pages:")
    for i in d["industries"]:
        print(f"    {i['url']:<34}{i['share']}%  {i['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
