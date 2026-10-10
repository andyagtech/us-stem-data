#!/usr/bin/env python3
"""The public-sector page: who the state, the schools and the colleges sponsor.

WHY THIS PAGE EXISTS SEPARATELY

The body-shop pages measure firms that file at volume. Public employers are the
opposite shape -- a long tail of single filings -- and the interesting thing
about them is not volume at all. It is that a state corrections department, a
school district and a land-grant university each sponsor permanent residence,
each for a different reason, and the records say which reason.

WHAT IT SHOWS AND WHY IT IS BUILT, NOT WRITTEN

Three sectors, and for each one a distribution rather than a league table. A
histogram answers a question a top-ten cannot: whether a sector's total comes
from a crowd of employers filing once or a handful filing hundreds. The wage
histogram answers what the posts pay, which is the only way to see that a
school district's filings and a university's filings are not the same kind of
job.

The anomaly lists are computed in the builder, not chosen here. That matters.
A hand-picked list of strange filings is an argument; a list produced by a test
applied to every row is a finding, and the reader can see the test.

NOTHING HERE IS AN ACCUSATION. A PERM filing is an employer asking the
Department of Labor for permission to sponsor permanent residence. It is a
public record of a request. It is not evidence that anyone broke a rule, and
the page says so where a reader might otherwise assume it.

Usage:
    python3 scripts/build_public_sector_page.py
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
PERM = SITE / "data" / "public_employer_perm.json"
OUT = SITE / "public-sector-visas.html"
ENTITY_MAP = ROOT / "pipeline" / "entity_map.json"

#: One file per state that the page gives a section to. The employer rows in
#: those sections open onto every filing the employer made, and those rows are
#: fetched rather than inlined. See `write_state_filings`.
FILINGS_DIR = SITE / "data" / "public_sector_filings"
FILINGS_URL = "/data/public_sector_filings"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                          # noqa: E402
from employer_name import pretty as _pn                      # noqa: E402

E = html.escape

SECTOR_TITLE = {
    "universities": "Universities and colleges",
    "school_districts": "School districts and K–12 schools",
    "state_agencies": "State agencies",
    "utilities": "Utilities: power, gas and water",
}
SECTOR_LEDE = {
    "universities": (
        "Public and private institutions alike. This is the largest of the "
        "three by an order of magnitude, and the least surprising: a research "
        "university recruits faculty and postdocs from a world labor market, "
        "and has done for as long as the records run."),
    "school_districts": (
        "Districts, boards of education and individual schools. The story here "
        "is different from the universities. The filings are teachers, and they "
        "are concentrated in subjects and regions where districts say they "
        "cannot hire."),
    "utilities": (
        "Electric generation and distribution, natural gas, water and "
        "sewage. This sector is found by industry code rather than by name, "
        "because 'Electric' in a company name usually means it makes "
        "equipment rather than power. Most of it is investor-owned, not "
        "public, and the page marks which is which rather than quietly "
        "dropping the private ones: they run the same grid."),
    "state_agencies": (
        "Departments of a state government. The smallest sector by far, and "
        "the one a reader is most likely to find unexpected, because these are "
        "posts inside the machinery of a state."),
}
#: The four jobs a colour can do, and only one of them is in use here: every
#: histogram is one series, so identity never rides on hue. One accent carries
#: magnitude and the text tokens carry everything that must be read.
ACCENT = "#3987e5"


def fmt(n) -> str:
    return "—" if n is None else f"{n:,}"


def usd(n) -> str:
    return "—" if n is None else f"${n:,.0f}"


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
  .page-head p {{ color: var(--text-muted); max-width: 72ch; line-height: 1.65; font-size: .95rem; margin: 0 0 .6rem; }}
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
  section.block h3 {{ font-size: .96rem; margin: 1.6rem 0 .3rem; }}
  .lede {{ color: var(--text-muted); max-width: 74ch; line-height: 1.6; font-size: .92rem; margin: 0 0 1rem; }}
  .note {{ color: var(--text-muted); font-size: .78rem; line-height: 1.55; max-width: 82ch; margin: .9rem 0 0; }}
  .table-wrap {{ overflow-x: auto; }}
  table.t {{ width: 100%; border-collapse: collapse; font-size: .84rem; margin: .6rem 0 0; }}
  table.t th {{ text-align: left; font-size: .71rem; text-transform: uppercase; letter-spacing: .06em;
    color: var(--text-muted); font-weight: 600; padding: .4rem .5rem; border-bottom: 1px solid var(--border); white-space: nowrap; }}
  table.t td {{ padding: .42rem .5rem; border-bottom: 1px solid var(--border); vertical-align: top; }}
  table.t td.num, table.t th.num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  table.t td.muted {{ color: var(--text-muted); }}
  table.t th.sortable {{ cursor: pointer; }}

  /* HISTOGRAM. Vertical columns, one series, drawn from the bin counts in the
     data. The column is a block element: a span would ignore height and every
     bar would render flat, which is the bug this site already shipped once on
     the state pages. */
  .hist {{ margin: 1rem 0 0; }}
  .hist .plot {{ display: grid; grid-auto-flow: column; grid-auto-columns: 1fr;
    align-items: end; gap: 2px; height: 160px; padding: 0 0 2px;
    border-bottom: 1px solid var(--border); }}
  .hist .col {{ display: flex; flex-direction: column; justify-content: flex-end;
    height: 100%; position: relative; }}
  .hist .bar {{ display: block; width: 100%; background: {ACCENT};
    border-radius: 4px 4px 0 0; min-height: 2px; }}
  .hist .bar[data-zero="1"] {{ background: rgba(148,163,184,0.3); }}
  .hist .cap {{ font-size: .66rem; color: var(--text-muted); text-align: center;
    font-variant-numeric: tabular-nums; padding-top: .3rem; line-height: 1.3;
    word-break: break-word; }}
  .hist .ticks {{ display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 2px; }}
  .hist .peak {{ font-size: .66rem; color: var(--text-muted); margin: 0 0 .25rem;
    font-variant-numeric: tabular-nums; }}
  .hist .col:hover .bar {{ background: var(--hl); }}
  .hist .col .tip {{ position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
    background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
    padding: .3rem .5rem; font-size: .72rem; white-space: nowrap; opacity: 0;
    pointer-events: none; transition: opacity .12s; z-index: 5; margin-bottom: 4px; }}
  .hist .col:hover .tip, .hist .col:focus-within .tip {{ opacity: 1; }}
  /* A tip is centred on its column, so the tip on the last column -- the
     widest label, "$250k+" -- hung half its width past the right edge of the
     page and made the whole page scroll sideways on every device. It is laid
     out even at opacity 0, so nobody saw the thing that was doing it. The
     edge columns anchor their tip inside the plot instead. */
  .hist .col:first-child .tip {{ left: 0; transform: none; }}
  .hist .col:last-child .tip {{ left: auto; right: 0; transform: none; }}
  /* On a phone the plot is about 330px wide and a tip can be 165px, so a tip
     centred on any column right of the middle still pushes the page. Below
     this width the tip is anchored to the plot rather than to its column:
     one is open at a time, so where it sits matters less than the page not
     scrolling sideways. */
  @media (max-width: 700px) {{
    .hist .plot {{ position: relative; }}
    .hist .col {{ position: static; }}
    .hist .col .tip {{ left: 0; right: auto; transform: none;
      white-space: normal; max-width: 100%; }}
  }}
  .pcts {{ display: flex; gap: 1.4rem; flex-wrap: wrap; margin: .7rem 0 0; font-size: .8rem; }}
  .pcts div span {{ color: var(--text-muted); }}
  .pcts div b {{ font-variant-numeric: tabular-nums; }}

  /* Country bars: horizontal, one series, sorted by magnitude. */
  .cbars {{ margin: .8rem 0 0; }}
  .cbars .row {{ display: grid; grid-template-columns: 11rem 1fr 3.6rem; gap: .6rem;
    align-items: center; padding: .22rem 0; font-size: .84rem; }}
  .cbars .lab {{ color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .cbars .track {{ display: block; background: rgba(148,163,184,0.14); border-radius: 3px;
    height: 14px; overflow: hidden; }}
  .cbars .fill {{ display: block; height: 100%; border-radius: 3px; background: {ACCENT}; min-width: 2px; }}
  .cbars .v {{ font-variant-numeric: tabular-nums; font-weight: 600; text-align: right; }}
  @media (max-width: 620px) {{ .cbars .row {{ grid-template-columns: 8rem 1fr 3rem; }} }}

  .sectortabs {{ display: flex; gap: .4rem; flex-wrap: wrap; margin: 1.2rem 0 0; }}
  .sectortabs button {{ font: inherit; font-size: .8rem; padding: .35rem .75rem;
    border: 1px solid var(--border); background: var(--surface); color: inherit;
    border-radius: 999px; cursor: pointer; }}
  .sectortabs button[aria-selected="true"] {{ border-color: var(--hl); color: var(--hl); font-weight: 600; }}
  .callout {{ border: 1px solid var(--border); border-left-width: 3px; border-radius: 10px;
    padding: 1rem 1.1rem; margin: 1rem 0 0; background: var(--surface); }}
  .callout h3 {{ margin: 0 0 .35rem; font-size: 1rem; }}
  .callout p {{ margin: 0 0 .5rem; font-size: .88rem; line-height: 1.55; color: var(--text-muted); }}
  /* The source file and case number are what a reader verifies against, so
     the cell wraps rather than clipping. A truncated filename is useless. */
  .why {{ font-size: .78rem; color: var(--text-muted); overflow-wrap: anywhere; }}
  table.t td.why {{ min-width: 11rem; }}
  /* DRILL-DOWN. An employer row opens onto the roles it filed for. The
     detail rows ship in the page and are hidden with the `hidden` attribute,
     so a reader with no JavaScript sees a closed table rather than a broken
     one, and print opens every row. */
  table.drill tr.emp {{ cursor: pointer; }}
  table.drill tr.emp:hover td {{ background: color-mix(in srgb, var(--hl) 6%, transparent); }}
  table.drill tr.emp:focus-visible {{ outline: 2px solid var(--hl); outline-offset: -2px; }}
  table.drill .twisty {{ display: inline-block; width: 1em; color: var(--text-muted);
    transition: transform .12s; }}
  table.drill tr.emp[aria-expanded="true"] .twisty {{ transform: rotate(90deg); }}
  table.drill tr.emp[aria-expanded="true"] td {{ font-weight: 600; }}
  table.drill tr.detail > td {{ padding: 0 0 .9rem 1.6rem;
    background: color-mix(in srgb, var(--hl) 3%, transparent); }}
  table.t.roles {{ margin: .2rem 0 0; font-size: .8rem; }}
  table.t.roles th {{ font-size: .66rem; }}
  table.t.roles td {{ padding: .3rem .5rem; }}
  .cits {{ line-height: 1.9; }}
  .cit {{ display: inline-block; font-size: .72rem; padding: .08rem .45rem;
    margin: 0 .25rem .2rem 0; border: 1px solid var(--border); border-radius: 999px;
    white-space: nowrap; }}
  .cit b {{ font-weight: 600; }}
  .cit.muted {{ color: var(--text-muted); font-style: italic; }}
  button.expand-all {{ font: inherit; font-size: .76rem; padding: .2rem .6rem;
    border: 1px solid var(--border); background: var(--surface); color: inherit;
    border-radius: 999px; cursor: pointer; margin-left: .3rem; }}
  button.expand-all:hover {{ border-color: var(--hl); color: var(--hl); }}
  @media print {{ table.drill tr.detail {{ display: table-row !important; }} }}
  .dept {{ margin: 0 0 1rem; }}
  .dept h5 {{ margin: .3rem 0 .2rem; font-size: .88rem; }}
  .dept h5 .why {{ font-weight: 400; }}
  table.drill tr.emp td.cits {{ max-width: 34rem; }}
  .grid2 {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 2rem; }}
  @media (max-width: 860px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}

  /* THE FILINGS INSIDE AN OPEN EMPLOYER ROW. Fetched, so the block has three
     states a reader can see: waiting, failed, and loaded. The buttons wrap,
     because this sits inside a table cell on a 360px phone. */
  .filings {{ margin: .2rem 0 0; }}
  .filings .showing {{ display: flex; align-items: baseline; gap: .5rem;
    flex-wrap: wrap; margin: .4rem 0 .2rem; font-size: .78rem;
    color: var(--text-muted); }}
  .filings .showing b {{ color: var(--text); font-variant-numeric: tabular-nums; }}
  .filings button {{ font: inherit; font-size: .76rem; padding: .18rem .6rem;
    border: 1px solid var(--border); background: var(--surface); color: inherit;
    border-radius: 999px; cursor: pointer; }}
  .filings button:hover {{ border-color: var(--hl); color: var(--hl); }}
  .filings button[aria-pressed="true"] {{ border-color: var(--hl);
    color: var(--hl); font-weight: 600; }}
  .filings .failed {{ color: var(--hl); }}
  /* A 27px pill is a hard thing to hit with a thumb. */
  @media (max-width: 700px) {{ .filings button {{ padding: .45rem .9rem; }} }}
  table.t.filed {{ font-size: .78rem; }}
  table.t.filed th {{ font-size: .66rem; }}
  table.t.filed td {{ padding: .3rem .5rem; }}
  table.t.filed td.deny {{ color: var(--text-muted); font-style: italic; }}
  table.t.filed td.who {{ font-weight: 600; }}
</style>
  <script id="phd-theme-boot">(function(){{try{{var t=localStorage.getItem("phd-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
  <script defer src="/theme.js"></script>
</head>
<body data-page="public-sector-visas">
<a class="skip-link" href="#sectors">Skip to the sectors</a>
<main id="main">
<div class="wrap">
"""


def histogram_html(h: dict, unit: str) -> str:
    """One series, drawn to one scale, every bar labelled with its own bin.

    The tallest bin sets the scale and is printed above the plot, so a reader
    can put a number on a bar without a y-axis.
    """
    peak = max((b["count"] for b in h["bins"]), default=0) or 1
    cols, ticks = [], []
    for b in h["bins"]:
        pct = 100 * b["count"] / peak
        zero = ' data-zero="1"' if b["count"] == 0 else ""
        cols.append(
            f'<div class="col" tabindex="0">'
            f'<span class="tip">{fmt(b["count"])} {unit} · {E(b["label"])}</span>'
            f'<span class="bar" style="height:{pct:.1f}%"{zero}></span></div>')
        ticks.append(f'<div class="cap">{E(b["label"])}</div>')
    return (f'<div class="hist"><p class="peak">tallest bin: {fmt(peak)} {unit}</p>'
            f'<div class="plot">{"".join(cols)}</div>'
            f'<div class="ticks">{"".join(ticks)}</div></div>')


def country_bars(counts: dict, limit: int = 12) -> str:
    items = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
    if not items:
        return ""
    top = items[0][1] or 1
    rows = []
    for name, n in items:
        rows.append(
            f'<div class="row"><div class="lab" title="{E(name)}">{E(name)}</div>'
            f'<span class="track"><span class="fill" style="width:{100*n/top:.1f}%"></span></span>'
            f'<div class="v">{fmt(n)}</div></div>')
    return f'<div class="cbars">{"".join(rows)}</div>'



#: The two state-agency pages answer different halves of one question and
#: neither linked to the other, so a reader who found one had no way to the
#: other. H-1B has the volume and cannot name a nationality against an
#: employer; PERM is far smaller and names one on every row. Saying which is
#: which matters more than the link itself.
COMPANION = {
    "state_agencies": (
        "/state-agencies",
        "H-1B workers in state government",
        "This page counts permanent-residence filings. The H-1B page counts "
        "the temporary work visas, which are far more numerous and run from "
        "FY2009. It can tell you how many and which agencies. It cannot tell "
        "you who: the H-1B files do not link a nationality to an employer. "
        "That is the one thing this page can do, and it is why the two belong "
        "side by side."),
    "universities": (
        "/universities",
        "the university pages",
        "Each institution has its own page with enrolment, degrees and "
        "funding. This page adds what its employer filings say."),
    "school_districts": (
        "/states",
        "the state pages",
        "Each state page carries its schools and institutions. This page adds "
        "what their employer filings say."),
}



DRILL_JS = """<script>
/* Drill-down on the employer tables.
 *
 * TWO KINDS OF OPEN ROW, ONE TOGGLE. In the sector tables the detail rows are
 * already in the document and this only unhides them. In the state sections
 * the detail row holds a placeholder, and the filings are fetched from that
 * state's file the first time any row in it opens -- once per state, cached
 * for every row after. Four states inlined would be 1.3 MB of markup for rows
 * almost nobody opens.
 *
 * A row that cannot load says so and leaves the link to the file in place, so
 * the reader is never left with an empty open row.
 */
(function () {
  'use strict';
  var FIRST = __FIRST__, MORE = __MORE__;
  var loading = {};

  function load(slug) {
    if (!loading[slug]) {
      loading[slug] = fetch('__URL__/' + slug + '.json')
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (j) {
          var at = {}, byKey = {};
          (j.fields || []).forEach(function (f, i) { at[f] = i; });
          (j.employers || []).forEach(function (e) { byKey[e.key] = e; });
          return { at: at, byKey: byKey };
        })
        .catch(function (err) {
          // A FAILED FETCH IS NOT CACHED. Caching the rejected promise would
          // make one dropped request break every row in the state until the
          // page was reloaded; closing and reopening a row should retry.
          delete loading[slug];
          throw err;
        });
    }
    return loading[slug];
  }

  function cell(tr, text, cls) {
    var td = document.createElement('td');
    if (cls) td.className = cls;
    var s = (text === null || text === undefined || text === '') ? '\\u2014' : text;
    td.textContent = s;
    tr.appendChild(td);
    return td;
  }

  function money(n) {
    return (n === null || n === undefined) ? '\\u2014'
      : '$' + Number(n).toLocaleString('en-US');
  }

  var COLS = [['num', 'FY'], ['', 'Outcome'], ['', 'Job title'], ['', 'City'],
              ['', 'Citizenship'], ['', 'Born in'], ['', 'Visa held'],
              ['num', 'Wage'], ['', 'Decided'], ['', 'Source']];

  function filingsTable(emp, at, limit) {
    var wrap = document.createElement('div');
    wrap.className = 'table-wrap';
    var t = document.createElement('table');
    t.className = 't filed';
    var thead = document.createElement('thead');
    var hr = document.createElement('tr');
    COLS.forEach(function (c) {
      var th = document.createElement('th');
      if (c[0]) th.className = c[0];
      th.textContent = c[1];
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    t.appendChild(thead);
    var tb = document.createElement('tbody');
    emp.rows.slice(0, limit).forEach(function (r) {
      var tr = document.createElement('tr');
      var status = r[at.status] || '';
      cell(tr, r[at.fiscal_year], 'num');
      cell(tr, status, status.indexOf('Certified') === 0 ? 'muted' : 'deny');
      cell(tr, r[at.job_title]);
      cell(tr, r[at.city], 'muted');
      cell(tr, r[at.citizenship], 'who');
      cell(tr, r[at.birth_country], 'muted');
      cell(tr, r[at.visa_held]);
      cell(tr, money(r[at.wage]), 'num');
      cell(tr, r[at.decided], 'muted');
      var src = cell(tr, r[at.source_file], 'why');
      if (r[at.case_number]) {
        src.appendChild(document.createElement('br'));
        src.appendChild(document.createTextNode(r[at.case_number]));
      }
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    wrap.appendChild(t);
    return wrap;
  }

  /* The count line and the two buttons the author asked for. "Show 50" is
     offered only when there are more than fifty to show; otherwise "Show All"
     already is the whole list and a second button saying the same thing would
     be furniture. */
  function controls(box, emp, at, shown) {
    var total = emp.rows.length;
    var p = document.createElement('p');
    p.className = 'showing';
    var a = document.createElement('b');
    a.textContent = shown.toLocaleString('en-US');
    var b = document.createElement('b');
    b.textContent = total.toLocaleString('en-US');
    // One flex item, not six. The row is a flex container with a gap, so
    // every text node left loose in it would be spaced like a button.
    var said = document.createElement('span');
    said.appendChild(document.createTextNode('Showing '));
    said.appendChild(a);
    said.appendChild(document.createTextNode(' of '));
    said.appendChild(b);
    said.appendChild(document.createTextNode(
      total === 1 ? ' filing.' : ' filings.'));
    p.appendChild(said);
    var opts = [];
    if (total > FIRST) {
      if (total > MORE) opts.push(['Show ' + MORE, MORE]);
      opts.push(['Show All', total]);
    }
    opts.forEach(function (o) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = o[0];
      btn.setAttribute('aria-pressed', shown === Math.min(o[1], total)
        ? 'true' : 'false');
      btn.addEventListener('click', function () {
        draw(box, emp, at, o[1]);
      });
      p.appendChild(btn);
    });
    return p;
  }

  function draw(box, emp, at, limit) {
    var shown = Math.min(limit, emp.rows.length);
    box.textContent = '';
    box.appendChild(controls(box, emp, at, shown));
    box.appendChild(filingsTable(emp, at, shown));
  }

  function detailOf(row) {
    // The sector tables name their detail row; the state tables do not, to
    // keep 372 rows of markup down, so it is the row's own id with a d- on it.
    return document.getElementById(
      row.getAttribute('data-target') || ('d-' + row.id));
  }

  function fill(row) {
    var d = detailOf(row);
    var box = d && d.querySelector('.filings');
    if (!box) return;
    var slug = row.getAttribute('data-state');
    var key = row.getAttribute('data-key');
    if (!slug || !key) return;
    box.setAttribute('aria-busy', 'true');
    if (!box.firstChild) box.textContent = 'Loading the filings\\u2026';
    load(slug).then(function (data) {
      box.removeAttribute('aria-busy');
      var emp = data.byKey[key];
      if (!emp) throw new Error('employer not in ' + slug + '.json');
      draw(box, emp, data.at, FIRST);
    }).catch(function (err) {
      box.removeAttribute('aria-busy');
      box.textContent = '';
      var p = document.createElement('p');
      p.className = 'note failed';
      p.textContent = 'These filings could not be loaded: ' + err.message
        + '. The file they come from is linked under this table.';
      box.appendChild(p);
    });
  }

  function setOpen(row, open) {
    var d = detailOf(row);
    if (!d) return;
    d.hidden = !open;
    row.setAttribute('aria-expanded', open ? 'true' : 'false');
    // Every open starts at the default ten, including a reopen.
    if (open && row.hasAttribute('data-key')) fill(row);
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('button.expand-all');
    if (btn) {
      var sec = document.getElementById(btn.getAttribute('data-expand'));
      if (!sec) return;
      var rows = sec.querySelectorAll('table.drill tr.emp');
      var opening = btn.textContent.indexOf('Open') === 0;
      Array.prototype.forEach.call(rows, function (r) { setOpen(r, opening); });
      btn.textContent = opening ? 'Close all' : 'Open all';
      return;
    }
    var row = e.target.closest('table.drill tr.emp');
    if (row) setOpen(row, row.getAttribute('aria-expanded') !== 'true');
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var row = e.target.closest && e.target.closest('table.drill tr.emp');
    if (!row) return;
    e.preventDefault();
    setOpen(row, row.getAttribute('aria-expanded') !== 'true');
  });

  /* An employer row is addressable. #emp-washington--university-of-washington
     opens that row and loads its filings, which is what a page of its own
     would have given a reader who wanted to send a link. anchors.js resolves
     the fragment on cold load and on hashchange and calls these hooks first. */
  window.ANCHOR_HOOKS = (window.ANCHOR_HOOKS || []).concat(function (id) {
    var row = document.getElementById(id);
    if (!row || !row.classList.contains('emp')) return false;
    setOpen(row, true);
    return true;
  });
}());
</script>
"""


def roles_html(roles: list, emp: str) -> str:
    """One employer's job titles, each with who filled it.

    Citizenship is printed whole, not topped. A reader opening a row is
    usually looking for the one filing from somewhere unexpected, and a
    "top 5" would hide exactly that.
    """
    rows = []
    for r in roles:
        cits = r["citizenship"]
        span = (str(r["first_year"]) if r["first_year"] == r["last_year"]
                else f'{r["first_year"]}\u2013{r["last_year"]}')
        chips = " ".join(
            f'<span class="cit"><b>{E(c)}</b> &times;{n}</span>'
            for c, n in cits.items()) or '<span class="cit muted">not stated</span>'
        rows.append(
            f'<tr><td class="num">{fmt(r["filings"])}</td>'
            f'<td>{E(r["title"])}</td>'
            f'<td class="muted num">{E(span)}</td>'
            f'<td class="num">{usd(r["median_wage"])}</td>'
            f'<td class="cits">{chips}</td></tr>')
    return (f'<table class="t roles"><thead><tr>'
            f'<th class="num">Filings</th><th>Role</th><th class="num">Years</th>'
            f'<th class="num">Median wage</th>'
            f'<th>Who filled it, by citizenship</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')



def state_rollup(sec: str, detail: dict, roles_by_emp: dict) -> str:
    """State agencies, folded by state and opening onto their departments.

    WHY BY STATE. A flat list of employers puts "California Department Of
    Corrections And Rehabilit" and "California Department Of Corrections
    Rehab" on separate rows, which are one department truncated two ways by
    the federal file. Folding by state makes that a detail inside California
    rather than two entries competing at the top of a national table, and it
    is the unit a reader with one state's remit actually wants.

    Three levels: the state, its departments, and every filing with the
    nationality of the person it was for.
    """
    rows = []
    states = sorted(
        ((st, d) for st, d in detail.items()
         if (d.get("sectors") or {}).get(sec, {}).get("filings")),
        key=lambda t: -t[1]["sectors"][sec]["filings"])
    for i, (st, d) in enumerate(states):
        meta = d["sectors"][sec]
        filings = [r for r in (d.get("agency_filings") or [])]
        cits = meta.get("citizenship") or {}
        chips = " ".join(
            f'<span class="cit"><b>{E(c)}</b>'
            + f" &times;{n}</span>"
            for c, n in list(cits.items())[:14])
        by_dept: dict = {}
        for r in filings:
            by_dept.setdefault(r["employer"], []).append(r)
        depts = []
        for name, rs in sorted(by_dept.items(), key=lambda kv: -len(kv[1])):
            inner = "".join(
                f'<tr><td class="num">{r["fiscal_year"]}</td>'
                f'<td>{E(r["job_title"]) or "&mdash;"}</td>'
                f'<td class="muted">{E(r["city"]) or "&mdash;"}</td>'
                f'<td><strong>{E(r["citizenship"]) or "&mdash;"}</strong></td>'
                f'<td class="muted">{E(r["birth_country"]) or "&mdash;"}</td>'
                f'<td>{E(r["visa_held"]) or "&mdash;"}</td>'
                f'<td class="num">{usd(r["wage"])}</td>'
                f'<td class="why">{E(r.get("source_file", ""))}'
                + (f'<br>{E(r["case_number"])}' if r.get("case_number") else "")
                + '</td></tr>'
                for r in sorted(rs, key=lambda r: -r["fiscal_year"]))
            depts.append(
                f'<div class="dept"><h5>{E(_pn(name))} '
                f'<span class="why">{len(rs)} filing'
                f'{"" if len(rs) == 1 else "s"}</span></h5>'
                f'<div class="table-wrap"><table class="t"><thead><tr>'
                f'<th class="num">FY</th><th>Job title</th><th>City</th>'
                f'<th>Citizenship</th><th>Born in</th><th>Visa held</th>'
                f'<th class="num">Wage</th><th>Source</th></tr></thead>'
                f'<tbody>{inner}</tbody></table></div></div>')
        rid = f"{sec}-st-{i}"
        rows.append(
            f'<tr class="emp" data-target="{rid}" tabindex="0" role="button" '
            f'aria-expanded="false" aria-controls="{rid}">'
            f'<td><span class="twisty" aria-hidden="true">&#9656;</span>'
            f'{E(st.title())}</td>'
            f'<td class="num">{fmt(meta["filings"])}</td>'
            f'<td class="num">{fmt(len(by_dept) or meta["employers"])}</td>'
            f'<td class="cits">{chips}</td></tr>')
        rows.append(
            f'<tr class="detail" id="{rid}" hidden><td colspan="4">'
            f'{"".join(depts)}</td></tr>')
    return (f'<div class="table-wrap"><table class="t drill" data-drill>'
            f'<thead><tr><th>State</th><th class="num">Filings</th>'
            f'<th class="num">Departments</th>'
            f'<th>Citizenship of the people sponsored</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def employer_table(sec: str, employers: list, roles_by_emp: dict) -> str:
    """The employers table, with each row opening onto its own roles.

    The detail rows ship in the page rather than being fetched, because the
    whole point is that a reader can open any of them without waiting, and
    because a page that still works as a saved file is worth more here than
    the bytes saved.
    """
    body = []
    for i, (name, count) in enumerate(employers):
        roles = roles_by_emp.get(name)
        rid = f"{sec}-emp-{i}"
        if roles:
            body.append(
                f'<tr class="emp" data-target="{rid}" tabindex="0" '
                f'role="button" aria-expanded="false" aria-controls="{rid}">'
                f'<td><span class="twisty" aria-hidden="true">&#9656;</span>'
                f'{E(name.title())}</td>'
                f'<td class="num">{fmt(count)}</td>'
                f'<td class="num muted">{len(roles)}</td></tr>')
            body.append(
                f'<tr class="detail" id="{rid}" hidden><td colspan="3">'
                f'{roles_html(roles, name)}</td></tr>')
        else:
            body.append(f'<tr><td>{E(name.title())}</td>'
                        f'<td class="num">{fmt(count)}</td>'
                        f'<td class="num muted">&mdash;</td></tr>')
    return (f'<div class="table-wrap"><table class="t drill" data-drill>'
            f'<thead><tr><th>Employer</th><th class="num">Filings</th>'
            f'<th class="num">Roles</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def companion(sec: str) -> str:
    link = COMPANION.get(sec)
    if not link:
        return ""
    href, label, why = link
    return (f'<div class="callout"><h3>The other half of this</h3>'
            f'<p>{E(why)}</p>'
            f'<p><a href="{E(href)}">{E(label)}</a></p></div>')


def sector_block(sec: str, s: dict, d: dict, roles_by_emp: dict,
                 detail: dict) -> str:
    wage, per = d["wage"], d["filings_per_employer"]
    top10 = per["top10_share"]
    #: The sentence is built from the shape, so it stays true whichever way the
    #: distribution comes out on a rebuild.
    if top10 is None:
        shape = ""
    elif top10 >= 50:
        shape = (f"The ten busiest employers account for <strong>{top10}%</strong> "
                 f"of this sector's filings. It is a handful of programs, not "
                 f"a general practice.")
    elif top10 >= 20:
        shape = (f"The ten busiest employers account for {top10}% of this "
                 f"sector's filings. Concentrated at the top, with a long tail "
                 f"underneath.")
    else:
        shape = (f"The ten busiest employers account for only {top10}% of this "
                 f"sector's filings. This is a crowd of employers filing a few "
                 f"each, not a program.")


    visa_rows = "".join(
        f'<tr><td>{E(v)}</td><td class="num">{fmt(c)}</td></tr>'
        for v, c in sorted(s["visa_held"].items(), key=lambda kv: -kv[1])[:10])

    return f"""
<section class="block" id="{E(sec)}" data-sector="{E(sec)}">
<h2>{E(SECTOR_TITLE[sec])}</h2>
<p class="lede">{SECTOR_LEDE[sec]}</p>

<div class="stats">
  <div class="stat"><div class="n">{fmt(s['filings'])}</div>
    <p class="l">filings</p><p class="s">one filing is one request, not one worker hired</p></div>
  <div class="stat"><div class="n">{fmt(per['employers'])}</div>
    <p class="l">distinct employers</p><p class="s">median {fmt(per['median'])} filings each, most {fmt(per['max'])}</p></div>
  <div class="stat"><div class="n">{usd(wage['median'])}</div>
    <p class="l">median wage offered</p><p class="s">annualised; {fmt(wage['n'])} of {fmt(s['filings'])} state one</p></div>
  <div class="stat"><div class="n">{fmt(len(s['citizenship']))}</div>
    <p class="l">citizenships</p><p class="s">largest: {E(max(s['citizenship'], key=s['citizenship'].get)) if s['citizenship'] else '&mdash;'}</p></div>
</div>

<div class="grid2">
<div>
<h3>What these posts pay</h3>
<p class="note">Wage offered on the filing, annualised. Hourly rates assume a
2,080-hour year, so a nine-month contract paid hourly reads high here.</p>
{histogram_html(wage, "filings")}
<div class="pcts">
  <div><span>10th percentile</span> <b>{usd(wage['p10'])}</b></div>
  <div><span>median</span> <b>{usd(wage['median'])}</b></div>
  <div><span>90th percentile</span> <b>{usd(wage['p90'])}</b></div>
  <div><span>highest</span> <b>{usd(wage['max'])}</b></div>
</div>
</div>
<div>
<h3>How the filings pile up</h3>
<p class="note">Employers by how many filings each made across the whole window.
A tall bar on the left is a sector of one-off filings.</p>
{histogram_html(per, "employers")}
<p class="note">{shape}</p>
</div>
</div>

<div class="grid2">
<div>
<h3>Where the workers hold citizenship</h3>
{country_bars(s['citizenship'])}
<p class="note">Citizenship as the filing states it. It is a separate field
from country of birth, and the two do not always agree.</p>
</div>
<div>
<h3>The visa held when the employer filed</h3>
<div class="table-wrap"><table class="t" data-sortable>
<thead><tr><th class="sortable">Class of admission</th><th class="sortable num">Filings</th></tr></thead>
<tbody>{visa_rows}</tbody></table></div>
<p class="note">The status the worker held at the time of filing, not the status
sought. PERM asks for permanent residence whatever the worker holds now.</p>
</div>
</div>

{companion(sec)}
<h3>{"By state" if sec == "state_agencies" else "The employers filing most"}</h3>
<p class="note">{"Open a state to see its departments, and every filing with the nationality of the person it was for." if sec == "state_agencies" else "Open a row to see the roles it filed for and the citizenship of the people who filled them."} <button type="button" class="expand-all"
data-expand="{E(sec)}">Open all</button></p>
{state_rollup(sec, detail, roles_by_emp) if sec == "state_agencies"
   else employer_table(sec, s["top_employers"][:25], roles_by_emp)}
<p class="note">Employer names come through as the filer typed them, and the
federal files truncate long ones. Two spellings of the same department appear
as two rows where the truncation differs. Citizenship is listed in full for
each role, not topped, because one filing from an unexpected country is the
thing worth finding.</p>
</section>
"""


#: How many flagged rows the page tables show. The lists in the JSON are
#: longer; the totals are longer still.
TABLE_ROWS = 120



#: The states named by the readers this page was extended for. They get a
#: block of their own ahead of the national table. Nothing about the test or
#: the data changes for them; they are simply surfaced first, because a reader
#: whose remit is one state should not have to sort a 50-row table to begin.
FEATURED = ("WASHINGTON", "MISSOURI", "FLORIDA", "MONTANA")

SECTOR_SHORT = {"universities": "Universities",
                "school_districts": "School districts",
                "state_agencies": "State agencies",
                "utilities": "Utilities"}


# ---------------------------------------------------------------------------
# ONE EMPLOYER, SEVERAL SPELLINGS
#
# The federal files do not spell an employer the same way twice. Three
# distinct failures are in the data and they need different handling:
#
#   punctuation   UNIVERSITY OF WISCONSIN-MADISON and UNIVERSITY OF
#                 WISCONSINMADISON. One file drops the hyphen, and dropping it
#                 closes up the words, so replacing punctuation with a space
#                 does NOT make the two match. The key therefore removes every
#                 non-alphanumeric character, spaces included.
#   legal form    GEORGIA CHRISTIAN UNIVERSITY, INC. / ,INC / , LLC. The
#                 trailing form is dropped before comparing.
#   truncation    THE UNIVERSITY OF TEXAS HEALTH SCIENCE CENTER AT H. Three of
#                 the twelve files cut the field at 50 characters, which is why
#                 477 names are exactly 50 long. A short name is folded into a
#                 longer one only when it is a prefix of it AND is itself at or
#                 near that 50-character cut -- the signature of a truncation.
#
# The last rule has to be that narrow. UNIVERSITY OF IOWA is a prefix of
# UNIVERSITY OF IOWA COMMUNITY MEDICAL SERVICES and they are not the same
# employer, so prefix alone would merge a university into a hospital company.
# Nationally the narrow rule folds 2 names and the broad one would fold 148.
#
# Grouping is inside one state and one sector, never across. Merging is shown,
# not assumed: every employer row that is more than one spelling says so and
# lists them.
# ---------------------------------------------------------------------------

#: Trailing tokens that name a legal form rather than an employer. Kept in
#: step with SUFFIXES in `employer_name.py`, which strips the same words for
#: display -- the same list has to decide identity and presentation or a row
#: can be labelled one thing and keyed as another.
LEGAL_FORMS = {"INC", "INCORPORATED", "LLC", "LLP", "LTD", "LIMITED", "LP",
               "CO", "COMPANY", "CORP", "CORPORATION", "PC", "PA", "PLLC"}

#: The character count at which three of the files cut the employer field.
#: A name this long that is a prefix of a longer one is a truncation.
TRUNCATED_AT = 48


def merge_key(name: str) -> str:
    """The comparison form of an employer name. Not shown to a reader.

    NEVER STRIPS TO NOTHING. A filer whose whole name is a legal form -- and
    the files do carry "ACADEMY, LTD." shapes -- would otherwise key on the
    empty string, and then every such filer in a sector would be one employer.
    The empty key is also a prefix of every other key, so the truncation fold
    below would pull the whole sector into it.
    """
    raw = (name or "").upper()
    toks = [x for x in re.split(r"[^A-Z0-9]+", raw) if x]
    while len(toks) > 1 and toks[-1] in LEGAL_FORMS:
        toks.pop()
    if len(toks) > 1 and toks[0] == "THE":
        toks = toks[1:]
    if not toks:
        #: A name with no letters or digits in it at all. Not a real employer,
        #: but it must still get a key of its own rather than the empty one.
        return re.sub(r"\s+", "", raw)
    #: AND IS DROPPED, NOT NORMALISED. Some files write the ampersand, some
    #: write "and", and some drop it altogether: TEXAS A&M UNIVERSITY has 105
    #: filings and TEXAS AM UNIVERSITY has 45, and they are one university.
    #: Mapping "&" onto "and" matches the first two spellings and misses the
    #: third, so the word goes. The ampersand itself is already gone: the
    #: split above keeps only letters and digits.
    toks = [x for x in toks if x != "AND"] or toks
    return "".join(toks)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60].strip("-")


def group_employers(records: list) -> list:
    """Fold one state's filings into one entry per employer.

    Returns a list of dicts, busiest first, each carrying every filing it
    merged and every spelling it merged them under.
    """
    buckets: dict = {}
    for r in records:
        buckets.setdefault((r["sector"], merge_key(r["employer"])), []).append(r)

    # Truncation fold, within a sector: a key that is a strict prefix of
    # another and whose longest spelling is at the file's cut.
    for (sec, key) in sorted(buckets, key=lambda k: len(k[1])):
        rows = buckets.get((sec, key))
        if not rows or not key:
            continue
        longest = max(len(r["employer"]) for r in rows)
        if longest < TRUNCATED_AT:
            continue
        hosts = [k for k in buckets
                 if k[0] == sec and k[1] != key and k[1].startswith(key)]
        if len(hosts) == 1:
            buckets[hosts[0]].extend(rows)
            del buckets[(sec, key)]

    out = []
    for (sec, key), rows in buckets.items():
        spellings = sorted({r["employer"] for r in rows},
                           key=lambda s: (-len(s), s))
        #: Newest first, and newest WITHIN a year first too. Two stable
        #: passes rather than one key, because the decision date sorts
        #: descending and the fiscal year cannot be negated into the same
        #: tuple as a string.
        rows.sort(key=lambda r: (r["decided"] or "", r["job_title"] or ""),
                  reverse=True)
        rows.sort(key=lambda r: -r["fiscal_year"])
        out.append({
            "key": f"{sec}|{key}",
            "name": _pn(spellings[0]),
            "sector": sec,
            "filings": len(rows),
            "spellings": spellings,
            "rows": rows,
        })
    out.sort(key=lambda e: (-e["filings"], e["name"]))
    return out


#: The fields a drilled-down filing row carries, in the order the JSON packs
#: them. Packed as arrays against one field list rather than as objects: it is
#: the same data a third smaller, and the state file is fetched by a reader on
#: a phone.
FILING_FIELDS = ("fiscal_year", "status", "job_title", "city", "citizenship",
                 "birth_country", "visa_held", "wage", "decided",
                 "source_file", "case_number")


def write_state_filings(st: str, window: str, employers: list) -> int:
    """One state's filings, as the page's drill-down fetches them.

    WHY A FETCH, WHEN THE SECTOR TABLES SHIP THEIR DETAIL ROWS INLINE.
    An employer row in a sector table opens onto its job titles -- tens of
    rows. A state section opens onto individual filings, and Florida alone has
    1,780 of them. Inlining four states would add about 1.3 MB of markup to a
    page that is already 1 MB, and a reader opens one row. So the state files
    are written next to the page and fetched on the first open, one per state,
    cached thereafter. The page says where the file is, so a reader with no
    JavaScript can still get the data.
    """
    FILINGS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": st,
        "slug": slugify(st),
        "window": window,
        "filings": sum(e["filings"] for e in employers),
        "fields": list(FILING_FIELDS),
        "built_from": "site/data/public_employer_perm.json",
        "employers": [
            {
                "key": e["key"],
                "name": e["name"],
                "sector": e["sector"],
                "filings": e["filings"],
                "spellings": e["spellings"],
                "rows": [[r.get(f) for f in FILING_FIELDS] for r in e["rows"]],
            }
            for e in employers
        ],
    }
    path = FILINGS_DIR / f"{slugify(st)}.json"
    write_text(path, json.dumps(payload, separators=(",", ":")))
    return path.stat().st_size


def load_entity_map() -> dict:
    """Employer name -> the slug of the institution page we already publish.

    Exact matches only, and only where the page exists on disk. The
    substring matcher in `pipeline/step3_parse_federal` is deliberately not
    reused: it matched MIT inside LIMITED once, and a wrong link here would
    send a reader to the wrong university.
    """
    try:
        raw = json.loads(ENTITY_MAP.read_text())
    except Exception:
        return {}
    out = {}
    for name, slug in raw.items():
        if (SITE / "universities" / f"{slug}.html").exists():
            out[merge_key(name)] = slug
    return out


#: An employer this busy gets its own line of furniture in the open row: a
#: link to the institution page where we publish one, and a note that the
#: filings run to several screens. The author asked whether each should get a
#: generated page of its own; see the note in `employer_drill` for why the
#: answer here is a deep link instead.
BIG_EMPLOYER = 100

#: What an open row shows before a reader asks for more, and the one step in
#: between. "All" is whatever the employer filed -- 251 for the University of
#: Washington, the largest in any featured state.
SHOW_DEFAULT, SHOW_MORE = 10, 50


def agency_rows_html(rows: list, show_state: bool = True) -> str:
    """Every state-agency filing, whole, with the file it came from.

    There are 87 in the country across twelve years. A sample would be a
    choice; the whole list is a record. The source file and case number are on
    each row so a reader can open the federal file and find the same line.
    """
    head = ("<th class='sortable num'>FY</th><th class='sortable'>Agency</th>"
            "<th class='sortable'>Job title</th>"
            + ("<th class='sortable'>State</th>" if show_state else "")
            + "<th class='sortable'>City</th>"
            "<th class='sortable'>Citizenship</th><th class='sortable'>Born in</th>"
            "<th class='sortable'>Visa held</th><th class='sortable num'>Wage</th>"
            "<th class='sortable'>Decided</th><th>Source file</th>")
    body = []
    for r in rows:
        body.append(
            f'<tr><td class="num">{r["fiscal_year"]}</td>'
            f'<td>{E(_pn(r["employer"]))}</td>'
            f'<td>{E(r["job_title"]) or "&mdash;"}</td>'
            + (f'<td class="muted">{E(r["state"].title())}</td>' if show_state else "")
            + f'<td class="muted">{E(r["city"]) or "&mdash;"}</td>'
            f'<td>{E(r["citizenship"]) or "&mdash;"}</td>'
            f'<td>{E(r["birth_country"]) or "&mdash;"}</td>'
            f'<td>{E(r["visa_held"]) or "&mdash;"}</td>'
            f'<td class="num">{usd(r["wage"])}</td>'
            f'<td class="muted">{E(r["decided"])}</td>'
            f'<td class="why">{E(r.get("source_file", ""))}'
            + (f'<br>{E(r["case_number"])}' if r.get("case_number") else "")
            + '</td></tr>')
    return (f'<div class="table-wrap"><table class="t" data-sortable>'
            f'<thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody>'
            f'</table></div>')


def employer_drill(st: str, employers: list, unis: dict) -> str:
    """Every public employer in one state, each row opening onto its filings.

    WHAT A ROW OPENS ONTO. The filings themselves: fiscal year, outcome, job
    title, city, citizenship, birth country, the visa held when the employer
    filed, the wage offered, the decision date, and the federal file and case
    number the row came from. Ten at a time, then fifty, then all of them.
    The rows are fetched from this state's file on the first open.

    WHY NOT A PAGE PER EMPLOYER. 82 employers in the country have 100 filings
    or more, 8 of them in the states this page features. A page each would
    duplicate what the open row already shows, and would put 82 new paths into
    the sitemap, the contents page and the assistant's copy of the site map.
    What a reader actually wants from a page is a link they can send, so every
    employer row carries its own id instead: the fragment opens the row and
    shows every filing, and the rows big enough to be worth sending print that
    link. Where we already publish an institution page, the open row links to
    it.

    PAGE WEIGHT. Every byte here is multiplied by 370 employer rows across the
    four states, so the row carries the state and the employer key once and
    the detail row carries nothing it can be told: the detail row's id is the
    employer row's id with a `d-` in front, and the script derives it. The
    link to the state's file is printed once under the table rather than once
    per row, which is also where a reader with no JavaScript will look for it.
    """
    slug = slugify(st)
    rows, seen = [], set()
    for e in employers:
        #: TWO EMPLOYERS CAN SLUG THE SAME WAY. The display name drops the
        #: legal form and the slug is cut at 60 characters, so two different
        #: employers can arrive at one id. Falling back to "-2" is not
        #: allowed: a numbered twin of an existing id is the signature of a
        #: bug this repo already has a test for. The sector disambiguates
        #: readably, and the employer key -- unique inside a state -- settles
        #: anything the sector cannot.
        base = f"emp-{slug}--{slugify(e['name'])}"
        rid = base
        if rid in seen:
            rid = f"{base}--{slugify(SECTOR_SHORT[e['sector']])}"
        if rid in seen:
            rid = f"{base}--x{hashlib.sha1(e['key'].encode()).hexdigest()[:8]}"
        assert rid not in seen, rid
        seen.add(rid)
        extra = []
        if e["filings"] >= BIG_EMPLOYER:
            #: The link a page of its own would have given the reader. Shown
            #: only on the employers big enough that someone will want to
            #: send one, because it is furniture on a row with two filings.
            extra.append(
                f'<p class="note">{fmt(e["filings"])} filings. This row has '
                f'its own address: <a href="#{rid}">#{rid}</a>. Opening that '
                f'link opens this row.</p>')
        #: Matched on the raw spelling, never on the display form. The
        #: prettifier drops "Inc" and re-cases initialisms, so two employers
        #: the federal files keep apart can prettify to one string, and a
        #: lookup on that string is a lookup on the wrong employer.
        page = unis.get(merge_key(e["spellings"][0]))
        if page:
            extra.append(
                f'<p class="note">We publish a page on this institution: '
                f'<a href="/universities/{E(page)}.html">'
                f'{E(e["name"])}</a>.</p>')
        if len(e["spellings"]) > 1:
            extra.append(
                f'<p class="note">{len(e["spellings"])} spellings merged: '
                + "; ".join(f"<q>{E(s)}</q>" for s in e["spellings"])
                + '.</p>')
        rows.append(
            f'<tr class="emp" id="{rid}" data-state="{slug}" '
            f'data-key="{E(e["key"])}" tabindex="0" role="button" '
            f'aria-expanded="false" aria-controls="d-{rid}">'
            f'<td><span class="twisty" aria-hidden="true">&#9656;</span>'
            f'{E(e["name"])}</td>'
            f'<td class="muted">{SECTOR_SHORT[e["sector"]]}</td>'
            f'<td class="num">{fmt(e["filings"])}</td></tr>')
        rows.append(
            f'<tr class="detail" id="d-{rid}" hidden><td colspan="3">'
            + "".join(extra) + '<div class="filings"></div></td></tr>')
    return (f'<div class="table-wrap"><table class="t drill" data-sortable>'
            f'<thead><tr><th class="sortable">Employer</th>'
            f'<th class="sortable">Sector</th>'
            f'<th class="sortable num">Filings</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def state_block(st: str, det: dict, employers: list, unis: dict) -> str:
    """One state, in the shape a reader with that state's remit needs."""
    secs = det["sectors"]
    cells = []
    for key in ("state_agencies", "utilities", "school_districts",
                "universities"):
        s = secs.get(key)
        if not s:
            cells.append(f'<div class="stat"><div class="n">0</div>'
                         f'<p class="l">{SECTOR_SHORT[key]}</p>'
                         f'<p class="s">no filings in this state</p></div>')
            continue
        top = max(s["citizenship"], key=s["citizenship"].get) if s["citizenship"] else None
        cells.append(
            f'<div class="stat"><div class="n">{fmt(s["filings"])}</div>'
            f'<p class="l">{SECTOR_SHORT[key]}</p>'
            f'<p class="s">{fmt(s["employers"])} employers'
            + (f' &middot; median {usd(s["median_wage"])}' if s["median_wage"] else '')
            + (f'<br>largest citizenship: {E(top)}' if top else '') + '</p></div>')

    agencies = det["agency_filings"]
    if agencies:
        detail = (f'<h3>Every state-agency filing in {E(st.title())}</h3>'
                  f'<p class="note">All {len(agencies)} of them, with the '
                  f'federal file each came from.</p>'
                  + agency_rows_html(agencies, show_state=False))
    else:
        #: An absence is a result. Saying nothing here would read as an
        #: oversight rather than as the finding it is.
        detail = (f'<p class="note">No agency of the {E(st.title())} state '
                  f'government filed a certified PERM case in this window. '
                  f'That is a finding, not a gap: the files were read and the '
                  f'state is not in them.</p>')

    #: The outcome breakdown. The page used to call every one of these a
    #: CERTIFIED filing. Most are, but the files also carry denied and
    #: withdrawn cases and they were inside the same total, so the label
    #: was wrong by about four per cent. The number is a count of
    #: FILINGS, which is what it has always been; the outcomes are a
    #: breakdown of it, stated here and named again on every row.
    outcomes: dict = {}
    for e in employers:
        for r in e["rows"]:
            outcomes[r["status"]] = outcomes.get(r["status"], 0) + 1
    certified = sum(n for s, n in outcomes.items() if s.startswith("Certified"))
    other = " ".join(
        f'{fmt(n)} {"was" if n == 1 else "were"} {E(s.lower())}.'
        for s, n in sorted(outcomes.items(), key=lambda kv: -kv[1])
        if not s.startswith("Certified"))
    merged = sum(1 for e in employers if len(e["spellings"]) > 1)

    return f"""
<section class="block" id="state-{E(st.replace(' ', '-'))}">
<h2>{E(st.title())}</h2>
<p class="lede">{fmt(det['filings'])} filings by public employers in
{E(st.title())} across the whole window.</p>
<div class="stats">{"".join(cells)}</div>
{detail}
<h3>The public employers filing most in {E(st.title())}</h3>
<p class="note">All {fmt(len(employers))} public employers that filed in
{E(st.title())} are here. Open a row to read an employer's filings one by one.
Ten show first. Then fifty. Then all of them.</p>
<p class="note">{fmt(certified)} of the {fmt(det['filings'])} were certified.
{other} Each row names its own outcome. A certified filing is permission to
sponsor, not proof of a hire.</p>
{employer_drill(st, employers, unis)}
<p class="note">The filings in these rows are fetched from
<a href="{FILINGS_URL}/{slugify(st)}.json">{slugify(st)}.json</a>, which holds
every {E(st.title())} filing with its outcome, citizenship, wage and the
federal file it came from. They are not in the page: four states of them would
add more than a megabyte to it.</p>
<p class="note">Employer names come through as the filer typed them.
{f"{fmt(merged)} employers here are more than one spelling of the same body, merged, and each row says which spellings it merged." if merged else "No two spellings in this state resolved to the same employer."}
Spellings are merged inside one sector and one state, never across either.</p>
</section>
"""


def all_states_table(detail: dict) -> str:
    rows = []
    for st, det in sorted(detail.items(), key=lambda kv: -kv[1]["filings"]):
        s = det["sectors"]
        g = lambda k: s.get(k, {}).get("filings", 0)       # noqa: E731
        rows.append(
            f'<tr><td>{E(st.title())}</td>'
            f'<td class="num">{fmt(det["filings"])}</td>'
            f'<td class="num">{fmt(g("universities"))}</td>'
            f'<td class="num">{fmt(g("school_districts"))}</td>'
            f'<td class="num">{fmt(g("state_agencies"))}</td></tr>')
    return (f'<div class="table-wrap"><table class="t" data-sortable>'
            f'<thead><tr><th class="sortable">State</th>'
            f'<th class="sortable num">All filings</th>'
            f'<th class="sortable num">Universities</th>'
            f'<th class="sortable num">School districts</th>'
            f'<th class="sortable num">State agencies</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def pairs_block(pairs: list, total: int) -> str:
    """What the citizenship/birth mismatch is actually made of.

    The mismatch count on its own invites the reader to imagine something
    irregular. The pairs say what it is: overwhelmingly people who naturalised
    somewhere else first, and mostly in one country. That is worth printing
    before the table of individual rows, because it is the context the table
    does not carry.
    """
    if not pairs:
        return ""
    by_cit = {}
    for p in pairs:
        by_cit[p["citizenship"]] = by_cit.get(p["citizenship"], 0) + p["filings"]
    lead, lead_n = max(by_cit.items(), key=lambda kv: kv[1])
    rows = "".join(
        f'<tr><td>{E(p["citizenship"])}</td><td>{E(p["birth_country"])}</td>'
        f'<td class="num">{fmt(p["filings"])}</td></tr>' for p in pairs[:20])
    return f"""
<div class="callout">
<h3>Most of the mismatch is one country</h3>
<p>Of the {fmt(total)} filings where citizenship and birth country differ, the
largest single citizenship is <strong>{E(lead)}</strong>, with {fmt(lead_n)} of
them. These are people who emigrated once already, took a second nationality,
and then moved again. The pattern is a staging post, not a discrepancy.</p>
</div>
<div class="table-wrap"><table class="t" data-sortable>
<thead><tr><th class="sortable">Citizenship</th><th class="sortable">Born in</th>
<th class="sortable num">Filings</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="note">The twenty most common pairs. Sortable.</p>
"""


def anomaly_block(key: str, rows: list, note: str, total: int) -> str:
    titles = {
        "sponsored_while_not_work_authorised":
            "Sponsored while holding something other than a work visa",
        "a_us_citizen_named_on_the_filing":
            "A US citizen named on the filing",
        "citizenship_differs_from_birth_country":
            "Citizenship is not the country of birth",
        "job_title_unique_in_its_sector":
            "A job title filed once in its whole sector",
    }
    body = "".join(
        f'<tr><td class="num">{r["fiscal_year"]}</td>'
        f'<td>{E(_pn(r["employer"]))}</td>'
        f'<td>{E(r["job_title"]) or "&mdash;"}</td>'
        f'<td class="muted">{E(r["state"].title())}</td>'
        f'<td class="why">{E(r["why"])}</td></tr>'
        for r in rows[:TABLE_ROWS])
    #: The count is the total the test flagged, not the length of this table.
    #: The JSON caps the list it ships, and reading the count off the capped
    #: list would print the cap against every test on the page.
    n_shown = min(len(rows), TABLE_ROWS)
    more = ("" if total <= n_shown else
            f" Showing the {n_shown:,} most recent of {total:,}.")
    return f"""
<h3>{E(titles.get(key, key))} <span class="why">({fmt(total)} filings)</span></h3>
<p class="note">{E(note)}{E(more)}</p>
<div class="table-wrap"><table class="t" data-sortable>
<thead><tr><th class="sortable num">FY</th><th class="sortable">Employer</th>
<th class="sortable">Job title</th><th class="sortable">State</th>
<th>What flagged it</th></tr></thead>
<tbody>{body}</tbody></table></div>
"""


def build() -> None:
    d = json.loads(PERM.read_text())
    secs, dists = d["sectors"], d["distributions"]
    roles = d.get("employer_roles", {})
    order = ["state_agencies", "utilities", "school_districts", "universities"]
    order = [s for s in order if s in secs]

    total = sum(secs[s]["filings"] for s in order)
    employers = sum(dists[s]["filings_per_employer"]["employers"] for s in order)
    countries = len(d["citizenship_overall"])
    anoms = d["anomalies"]
    notes = d["anomaly_notes"]

    title = "Who the public sector sponsors"
    desc = (f"{total:,} certified permanent-residence filings by universities, "
            f"school districts and state agencies, {d['window']}, from the "
            f"Department of Labor's own disclosure files.")

    parts = [head(title, desc), f"""
<div class="page-head">
<p class="kicker">PERM permanent labor certification &middot; {E(d['window'])}</p>
<h1>Who the public sector sponsors</h1>
<p>A university hiring a physicist from abroad surprises nobody. A state
corrections department sponsoring a psychiatrist for permanent residence is the
same legal instrument used for a different purpose, and almost nobody has
looked at it.</p>
<p>This page reads the Department of Labor's PERM disclosure files for
{E(d['window'])} and keeps every certified filing by an employer that is a
university, a school district or an agency of a state government. It shows the
distributions rather than a league table, because the shape of a sector says
more than its top ten.</p>
<p>A PERM filing is a request. The employer asks the Department of Labor for
permission to sponsor permanent residence, after testing the local labor
market as the regulation requires. A certified filing means the request was
granted. It does not mean a person was hired, and nothing on this page says
any employer or worker broke a rule.</p>
</div>

<div class="stats">
  <div class="stat"><div class="n">{fmt(total)}</div><p class="l">filings</p>
    <p class="s">across {len(order)} sectors, {E(d['window'])}</p></div>
  <div class="stat"><div class="n">{fmt(employers)}</div><p class="l">public employers filing</p>
    <p class="s">from single schools to flagship universities</p></div>
  <div class="stat"><div class="n">{fmt(countries)}</div><p class="l">citizenships represented</p>
    <p class="s">the filings name the worker's citizenship and birth country</p></div>
  <div class="stat"><div class="n">{fmt(d['rows_scanned'])}</div><p class="l">filings read to find them</p>
    <p class="s">{fmt(d['duplicate_rows_skipped'])} duplicate rows skipped by case number</p></div>
</div>
"""]

    parts.append("""
<section class="block" id="sectors">
<h2>The three sectors</h2>
<p class="lede">Each sector is classified from the employer's own name, by rule,
not by hand. A name that reads as a school is tested as a school before it is
tested as a university, so a university-run high school lands in the K&ndash;12
sector and not the other way round.</p>
</section>
""")
    for sec in order:
        parts.append(sector_block(sec, secs[sec], dists[sec],
                                  roles.get(sec, {}),
                                  d.get("by_state_detail", {})))

    detail = d.get("by_state_detail", {})
    sidecars = []
    if detail:
        featured = [st for st in FEATURED if st in detail]
        nav = " &middot; ".join(
            f'<a href="#state-{st.replace(" ", "-")}">{st.title()}</a>'
            for st in featured)
        parts.append(f"""
<section class="block" id="states">
<h2>By state</h2>
<p class="lede">The same filings, cut by the state the work is in. A national
total is the wrong unit for a reader whose remit is one state, so every state
is below and the whole national table is at the end of this section.</p>
<p class="note">Jump to: {nav}</p>
</section>
""")
        unis = load_entity_map()
        by_state: dict = {}
        for r in d["records"]:
            by_state.setdefault(r["state"], []).append(r)
        for st in featured:
            employers = group_employers(by_state.get(st, []))
            size = write_state_filings(st, d["window"], employers)
            sidecars.append((slugify(st), len(employers), size))
            parts.append(state_block(st, detail[st], employers, unis))

        parts.append(f"""
<section class="block" id="every-state">
<h2>Every state</h2>
<p class="lede">All {fmt(len(detail))} states and territories with a public-sector
filing in the window. Sortable by any column.</p>
{all_states_table(detail)}
</section>
""")

    #: Every state-agency filing in the country, whole. 87 rows across twelve
    #: years is a list, not a dataset, and publishing it whole is the only way
    #: a reader can check that the summary above describes it faithfully.
    all_agency = sorted(
        [r for r in d["records"] if r["sector"] == "state_agencies"],
        key=lambda r: (-r["fiscal_year"], r["state"], r["employer"]))
    parts.append(f"""
<section class="block" id="every-agency-filing">
<h2>Every state-agency filing in the country</h2>
<p class="lede">All {fmt(len(all_agency))} of them, {E(d['window'])}, with the
federal file and case number each came from. This is the complete list, not a
selection: a reader can check the summary above against the thing it
summarises.</p>
{agency_rows_html(all_agency)}
<p class="note">Wage is the offer on the filing, annualised. A blank wage means
the filing did not state one in a unit that could be read. Case numbers are as
published; no worker is named in the federal file and none is named here.</p>
</section>
""")

    parts.append("""
<section class="block" id="anomalies">
<h2>The filings that do not fit</h2>
<p class="lede">Three tests, applied to every row rather than to rows chosen in
advance. Each table shows what flagged the filing, so the reader can judge the
test and not just the result. None of these tests finds wrongdoing. They find
rows that depart from the ordinary pattern, which is a different and more
useful thing.</p>
""")
    for key in ("sponsored_while_not_work_authorised",
                "a_us_citizen_named_on_the_filing",
                "citizenship_differs_from_birth_country",
                "job_title_unique_in_its_sector"):
        if key == "citizenship_differs_from_birth_country":
            parts.append(pairs_block(d.get("citizenship_birth_pairs", []),
                                     d.get("citizenship_birth_pairs_total", 0)))
        if anoms.get(key):
            parts.append(anomaly_block(
                key, anoms[key], notes.get(key, ""),
                d["anomaly_totals"].get(key, len(anoms[key]))))
    parts.append("</section>")

    caveats = "".join(f"<li>{E(c)}</li>" for c in d["caveats"]) \
        if isinstance(d["caveats"], list) else ""
    parts.append(f"""
<section class="block" id="method">
<h2>Method and limits</h2>
<p class="lede">Built from {fmt(len(d['files_read']))} PERM disclosure files published
by the Office of Foreign Labor Certification. Every figure on this page is
computed at build time from those files.</p>
<ul class="note">{caveats}
<li>The window ends at FY2024 because the Department of Labor stopped
publishing the worker fields. The FY2025 and FY2026 files carry no citizenship,
no country of birth and no class of admission. That is why this page cannot be
brought up to date, and it is a change in what the government discloses, not a
change in what employers filed.</li>
<li>Filings are counted once each, de-duplicated by case number, because the
quarterly releases overlap and a case appears in more than one file.</li>
<li>A certified filing is permission to sponsor. It is not a hire, not a visa,
and not a green card. Counting filings as people would overstate every figure
here.</li>
<li>Sector membership is decided by the employer's name. A name that does not
say what the employer is will not be found, so all three counts are floors.</li>
</ul>
<p class="note">Source: <a href="{E(d['source_url'])}">{E(d['source'])}</a>.</p>
</section>
</div>
</main>
""")
    parts.append(DRILL_JS.replace("__FIRST__", str(SHOW_DEFAULT))
                 .replace("__MORE__", str(SHOW_MORE))
                 .replace("__URL__", FILINGS_URL))
    parts.append("""<script src="/analytics-beacon.js" defer></script>
<script src="/anchors.js" defer></script>
<script src="/sidebar.js"></script>
<script src="/states.js"></script>
</body>
</html>
""")
    write_text(OUT, "".join(parts))
    print(f"wrote {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size / 1024:,.0f} KB)")
    print(f"  {total:,} filings, {len(order)} sectors, "
          f"{sum(len(v) for v in anoms.values()):,} flagged rows")
    for slug, n_emp, size in sidecars:
        print(f"  {FILINGS_DIR.relative_to(ROOT)}/{slug}.json: "
              f"{n_emp:,} employers, {size / 1024:,.0f} KB, fetched on demand")


if __name__ == "__main__":
    build()
