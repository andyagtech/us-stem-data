#!/usr/bin/env python3
"""Render the faculty-mobility page.

Every figure comes from scripts/faculty_mobility.py, where each one is
tied to an award ID in the funding agency's own database. The page shows
the money, the appointments and the dates, and links every source
including an archive of the pages that no longer exist.

Usage:
  python3 scripts/build_faculty_mobility.py
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402
from faculty_mobility import CASES                             # noqa: E402

OUT = ROOT / "site" / "faculty-mobility.html"
E = html.escape


def case_html(c) -> str:
    us = "".join(
        f'<li><strong>{E(a.institution)}</strong>'
        f'<span class="mut"> &middot; {E(a.role)}'
        f'{" &middot; " + E(a.years) if a.years else ""}</span>'
        + (f' <a href="{E(a.archived)}" target="_blank" rel="noopener" '
           f'class="sm">archived page</a>' if a.archived else "")
        + "</li>" for a in c.us)

    grants = "".join(
        f'<tr><td class="mut">{E(g.start[:4])}</td>'
        f'<td><a href="https://www.nsf.gov/awardsearch/showAward?AWD_ID='
        f'{E(g.award_id)}" target="_blank" rel="noopener">{E(g.agency)} '
        f'{E(g.award_id)}</a></td>'
        f'<td>{E(g.institution)}</td>'
        f'<td>{E(g.title[:48])}</td>'
        f'<td class="num hi">${g.amount:,}</td></tr>' for g in c.grants)

    src = "".join(
        f'<li><a href="{E(u)}" target="_blank" rel="noopener">{E(t)}</a></li>'
        for t, u in c.sources)

    return f"""
<article class="case">
  <h2>{E(c.name)}</h2>
  <p class="field">{E(c.field)}</p>
  <div class="hero">
    <div class="big"><span class="n">${c.total:,}</span>
      <span class="l">in federal awards as principal investigator, at
      US institutions</span></div>
    <div class="big"><span class="n">{len(c.grants)}</span>
      <span class="l">NSF awards, {E(c.grants[-1].start[:4])}&ndash;{E(c.grants[0].start[:4])}</span></div>
  </div>
  <p class="sum">{E(c.summary)}</p>

  <h3>United States appointments</h3>
  <ul class="appts">{us}</ul>

  <h3>Current appointment</h3>
  <ul class="appts now">
    <li><strong>{E(c.now.institution)}</strong>
      <span class="mut"> &middot; {E(c.now.country)}</span><br>
      <span class="role">{E(c.now.role)}</span>
      {f'<a href="{E(c.now.url)}" target="_blank" rel="noopener" class="sm">faculty page</a>' if c.now.url else ''}
    </li>
  </ul>

  <h3>The federal awards</h3>
  <div class="tw"><table>
    <thead><tr><th>Year</th><th>Award</th><th>Awardee institution</th>
    <th>Title</th><th class="num">Obligated</th></tr></thead>
    <tbody>{grants}</tbody>
    <tfoot><tr><th colspan="4">Total</th>
    <th class="num hi">${c.total:,}</th></tr></tfoot>
  </table></div>

  <p class="note">{E(c.note)}</p>
  <h3>Sources</h3>
  <ul class="src">{src}</ul>
</article>"""


def main() -> int:
    total = sum(c.total for c in CASES)
    desc = ("Faculty who held federally funded US appointments and now work "
            "abroad, with the award record behind each.")
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Where the Expertise Went</title>
<meta name="description" content="{E(desc)}">
<link rel="stylesheet" href="/style.css">
<style>
  .wrap {{ max-width: 1060px; margin: 0 auto; padding: 1.75rem 1.25rem 4rem; }}
  h1 {{ font-size: 1.95rem; margin: 0 0 .5rem; }}
  .lede {{ color: var(--text-muted); max-width: 72ch; line-height: 1.68;
    font-size: .98rem; margin: 0 0 .7rem; }}
  .warn {{ border-left: 3px solid var(--hl); background: var(--surface);
    padding: .8rem 1rem; border-radius: 0 8px 8px 0; margin: 1.1rem 0 0;
    font-size: .88rem; line-height: 1.65; max-width: 78ch; }}
  .case {{ margin-top: 2.6rem; border-top: 1px solid var(--border);
    padding-top: 1.5rem; }}
  .case h2 {{ font-size: 1.5rem; margin: 0 0 .2rem; }}
  .field {{ color: var(--text-muted); font-size: .9rem; margin: 0 0 1rem; }}
  .hero {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px,1fr));
    gap: .8rem; margin: 0 0 1.1rem; }}
  .big {{ border: 1px solid var(--border); border-left: 3px solid var(--hl);
    border-radius: 0 9px 9px 0; padding: .8rem 1rem; background: var(--surface); }}
  .big .n {{ display: block; font-size: 1.9rem; font-weight: 800;
    color: var(--hl); line-height: 1.1; font-variant-numeric: tabular-nums; }}
  .big .l {{ display: block; font-size: .82rem; color: var(--text-muted);
    line-height: 1.5; margin-top: .25rem; }}
  .sum {{ font-size: .97rem; line-height: 1.7; max-width: 72ch;
    margin: 0 0 1.2rem; }}
  .case h3 {{ font-size: .76rem; text-transform: uppercase; letter-spacing: .07em;
    color: var(--text-muted); margin: 1.4rem 0 .5rem; }}
  ul.appts {{ list-style: none; padding: 0; margin: 0; }}
  ul.appts li {{ padding: .4rem 0; border-bottom: 1px solid var(--border);
    font-size: .92rem; line-height: 1.6; }}
  ul.appts.now li {{ border-bottom: 0; border-left: 3px solid var(--hl);
    padding-left: .8rem; background: var(--surface); border-radius: 0 8px 8px 0; }}
  .role {{ font-size: .86rem; color: var(--text-muted); }}
  .sm {{ font-size: .76rem; margin-left: .4rem; }}
  .tw {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .84rem; }}
  th {{ text-align: left; font-size: .68rem; text-transform: uppercase;
    letter-spacing: .05em; color: var(--text-muted); font-weight: 700;
    padding: .4rem .5rem; border-bottom: 1px solid var(--border); }}
  td {{ padding: .36rem .5rem; border-bottom: 1px solid var(--border); }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums;
    white-space: nowrap; }}
  td.hi, th.hi {{ color: var(--hl); font-weight: 700; }}
  td.mut {{ color: var(--text-muted); }}
  .note {{ font-size: .82rem; line-height: 1.65; color: var(--text-muted);
    max-width: 78ch; margin: 1rem 0 0; }}
  ul.src {{ font-size: .84rem; line-height: 1.7; padding-left: 1.1rem;
    margin: 0; }}
  a {{ color: var(--hl); }}
</style>
  <script id="phd-theme-boot">(function(){{try{{var t=localStorage.getItem("phd-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
  <script defer src="/theme.js"></script>
</head>
<body data-page="faculty-mobility">
<main class="wrap">
<h1>Where the expertise went</h1>
<p class="lede">Federal research money buys two things: the research, and
the researcher. The research is published. The researcher can leave, and
when they do the public has paid to create expertise it no longer has.</p>
<p class="lede">Each case below is a professor who held a federally funded
appointment at a US institution and now holds one abroad. Every figure is
an award in the funding agency's own database, with its identifier.</p>
<div class="warn"><strong>This is not an allegation.</strong> Changing
institutions is legal, ordinary and common, in both directions, and
nothing here states or implies that any person did anything improper,
broke any law, or failed any disclosure obligation. What the page shows is
the public record: who was funded, by how much, where, and where they
work now. Readers should draw conclusions about policy, not about
people.</div>
{''.join(case_html(c) for c in CASES)}
</main>
<script src="/analytics-beacon.js" defer></script>
<script src="/sidebar.js"></script>
</body>
</html>
"""
    write_text(OUT, page)
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(CASES)} case(s), ${total:,} in documented federal awards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
