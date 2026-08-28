#!/usr/bin/env python3
"""Insert the domestic-pipeline page into the briefing, and re-render the PDF.

The report generator used to live in a scratch directory and was lost when
that directory was cleared. The rendered HTML survived because it had been
copied out, and it carries every page and every chart as inline SVG -- so it
is now the source, kept in the repository where it cannot vanish again.

This script adds one page from data/site JSON and writes the PDF. It is
idempotent: running it twice replaces the page rather than adding a second.

Usage:
  python3 report/render_pipeline_page.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "report" / "briefing.html"
DATA = ROOT / "site" / "data" / "domestic_pipeline.json"
OUT_PDF = Path.home() / "usds_china_reports" / "STEM_Pipeline_Briefing.pdf"
MARKER = "<!-- domestic-pipeline -->"

BLUE, ORANGE, INK, MUTED, GRID = "#1d4ed8", "#c2410c", "#111827", "#4b5563", "#d4d4d8"


def line_chart(series, width=660, height=200, ymax=30, pad=46, padr=132,
               top=16, bot=32, ylines=3, xticks=()):
    xs = [p[0] for p in series[0][1]]
    x0, x1 = min(xs), max(xs)
    def X(v): return pad + (v - x0) / max(x1 - x0, 1) * (width - pad - padr)
    def Y(v): return top + (ymax - v) / ymax * (height - top - bot)
    out = [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
           f'xmlns="http://www.w3.org/2000/svg">']
    for k in range(ylines + 1):
        v = ymax * k / ylines
        out.append(f'<line x1="{pad}" y1="{Y(v):.1f}" x2="{width-padr+6}" y2="{Y(v):.1f}" '
                   f'stroke="{GRID}" stroke-width="0.75"/>')
        out.append(f'<text x="{pad-8}" y="{Y(v)+3.5:.1f}" text-anchor="end" font-size="10.5" '
                   f'fill="{MUTED}" font-variant-numeric="tabular-nums">{v:.0f}%</text>')
    for xv in (xticks or xs):
        out.append(f'<text x="{X(xv):.1f}" y="{height-bot+18:.1f}" text-anchor="middle" '
                   f'font-size="10.5" fill="{MUTED}" font-variant-numeric="tabular-nums">{xv}</text>')
    for label, pts, color, dashed in series:
        d = " ".join(f"{'M' if i == 0 else 'L'}{X(a):.1f},{Y(b):.1f}"
                     for i, (a, b) in enumerate(pts))
        dash = ' stroke-dasharray="7 4"' if dashed else ""
        out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" '
                   f'stroke-linejoin="round" stroke-linecap="round"{dash}/>')
        lx, ly = X(pts[-1][0]), Y(pts[-1][1])
        out.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.4" fill="{color}"/>')
        out.append(f'<text x="{lx+8:.1f}" y="{ly+3.5:.1f}" font-size="11" font-weight="600" '
                   f'fill="{INK}">{label}</text>')
    out.append("</svg>")
    return "".join(out)


def build_page(d: dict) -> str:
    years = sorted(int(y) for y in d["series"])
    first, last = str(years[0]), str(years[-1])
    s0, s1 = d["series"][first], d["series"][last]
    cm, cd = d["conversion"]["masters"], d["conversion"]["doctorate"]
    chart = line_chart(
        [("To a master's", [(r["bachelors_year"], r["rate"]) for r in cm], BLUE, False),
         ("To a doctorate", [(r["bachelors_year"], r["rate"]) for r in cd], ORANGE, True)],
        xticks=[2011, 2014, 2017, 2019])

    def pct(a, b):
        return f"{100 * (b / a - 1):+.0f}%"

    rows = "".join(
        f"<tr><td>{r['name']}</td><td class='n'>{r['domestic_first']:,}</td>"
        f"<td class='n'>{r['domestic_last']:,}</td>"
        f"<td class='n'>{r['domestic_change_pct']:+.0f}%</td>"
        f"<td class='n'>{r['nra_change_pct']:+.0f}%</td></tr>"
        for r in d["doctorate_fields"]["rows"])
    fy0, fy1 = d["doctorate_fields"]["years"]

    return f"""{MARKER}
<div class="page">
  <p class="eyebrow">2. The domestic pipeline</p>
  <h2>Americans are not leaving STEM. They are stopping before the doctorate</h2>
  <hr class="rule">

  <p>Domestic core-STEM completions rose at every level between {first} and {last}.
  The shortfall is not in how many Americans earn STEM degrees.</p>

  <div class="stats">
    <div class="stat"><div class="v">{pct(s0['bachelors']['domestic'], s1['bachelors']['domestic'])}</div>
      <div class="l">domestic bachelor's degrees, {first}&ndash;{last}
      ({s0['bachelors']['domestic']:,} to {s1['bachelors']['domestic']:,})</div></div>
    <div class="stat"><div class="v">{pct(s0['masters']['domestic'], s1['masters']['domestic'])}</div>
      <div class="l">domestic master's degrees
      ({s0['masters']['domestic']:,} to {s1['masters']['domestic']:,})</div></div>
    <div class="stat"><div class="v">{pct(s0['doctorate']['domestic'], s1['doctorate']['domestic'])}</div>
      <div class="l">domestic research doctorates
      ({s0['doctorate']['domestic']:,} to {s1['doctorate']['domestic']:,})</div></div>
  </div>

  <p style="margin-top:14px">What changed is where they stop. Of a domestic bachelor's cohort,
  the share going on to a master's <b>rose</b> from {cm[0]['rate']}% to {cm[-1]['rate']}%. The share
  going on to a research doctorate <b>fell</b> from {cd[0]['rate']}% to {cd[-1]['rate']}% &mdash;
  a decline of about an eighth.</p>

  <div class="legend">
    <span class="lg"><span class="sw" style="border-top:2px solid {BLUE}"></span>Continuing to a master's</span>
    <span class="lg"><span class="sw" style="border-top:2px dashed {ORANGE}"></span>Continuing to a research doctorate</span>
  </div>
  <div class="fig">{chart}</div>
  <p class="cap"><b>Domestic bachelor's cohort continuing to a graduate degree.</b> Plotted by the
  year of the bachelor's cohort, against master's two years later and doctorates six. The lag is a
  modelling choice; IPEDS counts degrees, not people, so this is a ratio between two populations
  rather than a tracked cohort. Source: IPEDS Completions.</p>

  <h3>Doctorates by field, {fy0}&ndash;{fy1}</h3>
  <table>
    <tr><th>Field</th><th class="n">Domestic {fy0}</th><th class="n">Domestic {fy1}</th>
        <th class="n">Domestic</th><th class="n">Non-resident</th></tr>
    {rows}
  </table>
  <p class="cap" style="margin-top:4px">Research doctorates conferred. Source: IPEDS Completions.</p>

  <div class="note">Fields differ, and two here run against the pattern: mechanical engineering's
  domestic output grew faster than its non-resident output, and physics moved in step. The
  exception that matters is electrical engineering, where American doctorate production has not
  moved in fourteen years while non-resident production rose.</div>
</div>
"""


def main() -> int:
    if not (HTML.exists() and DATA.exists()):
        print("  missing briefing.html or domestic_pipeline.json")
        return 1
    html = HTML.read_text()
    page = build_page(json.loads(DATA.read_text()))

    # Idempotent: drop any previous copy before inserting.
    html = re.sub(re.escape(MARKER) + r".*?</div>\s*(?=<div class=\"page\")",
                  "", html, flags=re.S)
    anchor = '<div class="page">\n  <p class="eyebrow">2. Who the degrees go to</p>'
    if anchor not in html:
        anchor = [m.start() for m in re.finditer(r'<div class="page">', html)][2]
        html = html[:anchor] + page + html[anchor:]
    else:
        html = html.replace(anchor, page + anchor, 1)

    # Renumber footers and section headings by page order. Inserting a page
    # shifts every number after it; doing this by hand is how a document ends
    # up with two page 9s and a cross-reference pointing at the wrong page.
    pages = re.split(r'(?=<div class="page">)', html)
    n = sum(1 for pg in pages if pg.lstrip().startswith('<div class="page">'))
    seq, section = 0, 0
    rebuilt = []
    for pg in pages:
        if not pg.lstrip().startswith('<div class="page">'):
            rebuilt.append(pg)
            continue
        seq += 1
        # Every page carries a footer; the new one has none yet.
        if 'class="pagefoot"' in pg:
            pg = re.sub(r"Page \d+ of \d+", f"Page {seq} of {n}", pg)
        else:
            foot = ('<div class="pagefoot">'
                    '<span><a href="https://phd-demographics.andy-barr.com">'
                    'phd-demographics.andy-barr.com</a></span>'
                    f'<span>Page {seq} of {n}</span></div>')
            pg = pg.rstrip()
            assert pg.endswith("</div>")
            pg = pg[: -len("</div>")] + foot + "</div>\n"
        # A "(continued)" page shares its predecessor's section number.
        m = re.search(r'class="eyebrow">(\d+)\.\s*([^<]*)', pg)
        if m:
            if "continued" not in m.group(2).lower():
                section += 1
            pg = re.sub(r'(class="eyebrow">)\d+\.', rf"\g<1>{section}.", pg, count=1)
        rebuilt.append(pg)
    html = "".join(rebuilt)

    # In-text cross-references shift too. Everything referenced sits after
    # the inserted page, so each moves by one. Guarded by a marker so a
    # second run does not shift them again.
    if "<!-- xref-shifted -->" not in html:
        html = re.sub(r"\b(on|see) page (\d+)",
                      lambda m: f"{m.group(1)} page {int(m.group(2)) + 1}", html)
        html = re.sub(r"\bPage (\d+) states",
                      lambda m: f"Page {int(m.group(1)) + 1} states", html)
        html = html.replace("</body>", "<!-- xref-shifted --></body>") \
            if "</body>" in html else html + "<!-- xref-shifted -->"

    HTML.write_text(html)
    print(f"  page inserted; {n} pages total")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        pg.goto(HTML.as_uri(), wait_until="networkidle", timeout=60000)
        OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
        pg.pdf(path=str(OUT_PDF), format="Letter", print_background=False,
               prefer_css_page_size=True)
        b.close()
    raw = OUT_PDF.read_bytes()
    print(f"  PDF pages: {raw.count(b'/Type /Page') - raw.count(b'/Type /Pages')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
