#!/usr/bin/env python3
"""The H-1B explorer: the front page of h1b.andy-barr.com.

WHY A SEPARATE FRONT DOOR

h1b.andy-barr.com and phd-demographics.andy-barr.com serve the same files
from the same bucket, which is why the H-1B host used to show the STEM
sidebar and the STEM homepage. They are different subjects with different
readers. A congressional staffer looking at visa filings does not need the
doctorate pipeline in the left rail, and the pipeline reader does not need
gas stations.

So this page is the H-1B host's own front page, and sidebar.js serves a
different navigation tree when it sees that hostname. One bucket, two sites.

WHAT IT LEADS WITH

The cases that are not what the program is described as doing. H-1B is
understood as a visa for software engineers and professors, and most of it
is. The rest is in the same federal files and almost nobody reads it.

Every figure resolves from built data at render time. A case whose evidence
stops resolving fails the build rather than going stale.

Usage:
    python3 scripts/build_h1b_explorer.py
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = SITE / "data"
OUT = SITE / "h1b.html"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                          # noqa: E402
from employer_name import pretty as _pn                      # noqa: E402
from h1b_cases import CASES                                  # noqa: E402

E = html.escape


class EvidenceError(RuntimeError):
    pass


def resolve(file: str, path: str):
    p = DATA / file
    if not p.exists():
        raise EvidenceError(f"{file} is not built")
    node = json.loads(p.read_text())
    for part in path.split("."):
        try:
            node = node[int(part)] if part.lstrip("-").isdigit() else node[part]
        except (KeyError, IndexError, TypeError) as exc:
            raise EvidenceError(f"{file}:{path} stopped resolving at {part!r} "
                                f"({type(exc).__name__})") from exc
    return node


def fmt(v, how: str) -> str:
    if how == "n":
        return f"{v:,}"
    if how == "usd":
        return f"${v:,.0f}"
    if how == "pct1":
        return f"{v:.1f}%"
    if how == "raw":
        return str(v)
    raise EvidenceError(f"unknown format {how!r}")


REPORTS = [
    ("/public-sector-visas", "Who the public sector sponsors",
     "Universities, school districts and state agencies. Every state-agency "
     "filing published whole, with the worker's citizenship and the case "
     "number. Open any employer to see its roles and who filled them."),
    ("/state-agencies", "H-1B in state government",
     "The temporary work visas at agencies of state government, FY2009 "
     "onward. More numerous than the permanent filings, and it cannot name a "
     "nationality against an employer."),
    ("/bodyshops", "The visa body shops",
     "The firms whose business is supplying workers to other companies, "
     "separated from the firms that hire for their own work, using the "
     "employers' own answers on their own filings."),
    ("/filers", "Who files the visas",
     "The employers behind the volume."),
    ("/eor", "Hiring a foreigner with no visa",
     "Employer-of-record firms let an American company hire abroad with no "
     "visa at all. There is no federal count of this route and there cannot "
     "be, which makes every visa figure a floor."),
    ("/data_requests", "Data Asks",
     "What a federal office holds, or once published, that would answer a "
     "question these pages cannot. Most of it needs no new collection."),
]


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
  .wrap {{ max-width: 1060px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}
  .page-head h1 {{ font-size: 2.1rem; margin: 0 0 .7rem; line-height: 1.15; }}
  .page-head p {{ color: var(--text-muted); max-width: 70ch; line-height: 1.65; font-size: .97rem; margin: 0 0 .7rem; }}
  .kicker {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; color: var(--text-muted); margin: 0 0 .6rem; }}
  section.block {{ margin-top: 2.8rem; border-top: 1px solid var(--border); padding-top: 1.6rem; }}
  section.block h2 {{ font-size: 1.25rem; margin: 0 0 .45rem; }}
  .lede {{ color: var(--text-muted); max-width: 74ch; line-height: 1.6; font-size: .92rem; margin: 0 0 1rem; }}
  .note {{ color: var(--text-muted); font-size: .78rem; line-height: 1.55; max-width: 82ch; margin: .9rem 0 0; }}

  /* A case is a card. The figures are the point, so they lead. */
  .cases {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 1rem; margin: 1.2rem 0 0; }}
  @media (max-width: 820px) {{ .cases {{ grid-template-columns: 1fr; }} }}
  .case {{ border: 1px solid var(--border); border-radius: 12px; padding: 1.1rem 1.2rem;
    background: var(--surface); display: flex; flex-direction: column; }}
  .case h3 {{ margin: 0 0 .55rem; font-size: 1.04rem; line-height: 1.3; }}
  .case .nums {{ display: flex; flex-wrap: wrap; gap: 1.1rem; margin: 0 0 .7rem; }}
  .case .nums div {{ min-width: 0; }}
  .case .nums .v {{ font-size: 1.45rem; font-weight: 800; color: var(--hl);
    line-height: 1.1; font-variant-numeric: tabular-nums; }}
  .case .nums .k {{ font-size: .7rem; color: var(--text-muted); line-height: 1.35;
    margin-top: .2rem; max-width: 18ch; }}
  .case p {{ margin: 0 0 .5rem; font-size: .87rem; line-height: 1.6; }}
  .case .odd {{ color: var(--text-muted); }}
  .case .caveat {{ font-size: .76rem; color: var(--text-muted); border-top: 1px dashed var(--border);
    padding-top: .5rem; margin-top: auto; }}
  .case a.more {{ font-size: .82rem; font-weight: 600; margin-top: .35rem; display: inline-block; }}

  /* DRILL-DOWN. <details> rather than a script: it opens with no JavaScript,
     it is keyboard operable for free, and the browser's find-in-page can
     reach inside a closed one in current browsers. */
  details.drill {{ margin: .8rem 0 0; border-top: 1px dashed var(--border); padding-top: .6rem; }}
  details.drill > summary {{ cursor: pointer; font-size: .82rem; font-weight: 650;
    color: var(--hl); list-style: none; padding: .15rem 0; }}
  details.drill > summary::-webkit-details-marker {{ display: none; }}
  details.drill > summary::before {{ content: "▸"; display: inline-block;
    width: 1em; transition: transform .12s; }}
  details.drill[open] > summary::before {{ transform: rotate(90deg); }}
  .drillbody {{ padding: .6rem 0 .2rem; }}
  .drillbody h4 {{ font-size: .8rem; margin: 1rem 0 .2rem; text-transform: uppercase;
    letter-spacing: .05em; color: var(--text-muted); }}
  .drillbody h4:first-child {{ margin-top: .2rem; }}
  .dnote {{ font-size: .76rem; color: var(--text-muted); line-height: 1.5; margin: 0 0 .5rem; }}
  .two {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: .9rem; }}
  @media (max-width: 760px) {{ .two {{ grid-template-columns: 1fr; }} }}
  .drillbody table.t {{ width: 100%; border-collapse: collapse; font-size: .78rem; }}
  .drillbody table.t th {{ text-align: left; font-size: .64rem; text-transform: uppercase;
    letter-spacing: .05em; color: var(--text-muted); font-weight: 600;
    padding: .25rem .4rem; border-bottom: 1px solid var(--border); }}
  .drillbody table.t td {{ padding: .25rem .4rem; border-bottom: 1px solid var(--border);
    vertical-align: top; }}
  .drillbody table.t td.num, .drillbody table.t th.num {{ text-align: right;
    font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .table-wrap {{ overflow-x: auto; }}
  .chips {{ line-height: 2; margin: 0 0 .3rem; }}
  .cits {{ line-height: 1.95; }}
  .cit {{ display: inline-block; font-size: .7rem; padding: .05rem .4rem;
    margin: 0 .2rem .15rem 0; border: 1px solid var(--border); border-radius: 999px;
    white-space: nowrap; font-variant-numeric: tabular-nums; }}
  .cit b {{ font-weight: 600; }}
  .reports {{ display: grid; gap: .7rem; margin: 1rem 0 0; }}
  .report {{ border: 1px solid var(--border); border-left-width: 3px; border-radius: 10px;
    padding: .9rem 1.1rem; background: var(--surface); }}
  .report a {{ font-weight: 650; font-size: .97rem; }}
  .report p {{ margin: .25rem 0 0; font-size: .85rem; line-height: 1.55; color: var(--text-muted); }}

  .stats {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .8rem; margin: 1.6rem 0 0; }}
  .stat {{ border: 1px solid var(--border); border-radius: 10px; padding: .9rem 1rem; background: var(--surface); }}
  .stat .n {{ font-size: 1.7rem; font-weight: 800; color: var(--hl); line-height: 1.1; font-variant-numeric: tabular-nums; }}
  .stat .l {{ font-size: .82rem; line-height: 1.45; margin: .3rem 0 0; }}
  .stat .s {{ font-size: .72rem; color: var(--text-muted); margin: .45rem 0 0; }}
  @media (max-width: 900px) {{ .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
  @media (max-width: 480px) {{ .stats {{ grid-template-columns: 1fr; }} }}
</style>
  <script id="phd-theme-boot">(function(){{try{{var t=localStorage.getItem("phd-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
  <script defer src="/theme.js"></script>
</head>
<body data-page="h1b-explorer">
<a class="skip-link" href="#cases">Skip to the cases</a>
<main id="main">
<div class="wrap">
"""



def load(name: str) -> dict:
    f = DATA / name
    return json.loads(f.read_text()) if f.exists() else {}


def drill_html(c, h1b_ind: dict, h1b_occ: dict, perm: dict) -> str:
    """Who files, and where the people come from.

    The two halves come from different programs and they are NOT a subset of
    one another. H-1B names the employers and records no nationality at all
    below the national total. PERM is the green-card step, far smaller, and
    is the only public file that names a country against an employer. Showing
    them side by side is the only way to answer the question, and the panel
    says which is which so nobody reads the second as a share of the first.
    """
    if not c.group:
        return ""
    src = h1b_ind if c.h1b_source == "industry" else h1b_occ
    hg = (src.get("groups") or {}).get(c.group, {})
    pg = (perm.get("groups") or {}).get(c.group, {})
    if not hg and not pg:
        return ""

    who = "".join(
        f'<tr><td>{E(_pn(n))}</td><td class="num">{fmt(k, "n")}</td></tr>'
        for n, k in (hg.get("top_employers") or [])[:15])
    titles = "".join(
        f'<tr><td>{E(t)}</td><td class="num">{fmt(k, "n")}</td></tr>'
        for t, k in (hg.get("top_titles") or [])[:10])

    if pg:
        cits = pg.get("citizenship") or {}
        chips = " ".join(
            f'<span class="cit"><b>{E(n)}</b> {fmt(k, "n")}</span>'
            for n, k in list(cits.items())[:24])
        rows = "".join(
            f'<tr><td>{E(_pn(e))}</td><td class="cits">'
            #: ALWAYS PRINT THE COUNT, INCLUDING 1. Hiding it was meant
            #: to reduce clutter and instead made single filings look
            #: like categories: "North Korea" sat unnumbered next to
            #: "China 328" in the Defender Services row and read as a
            #: finding, when it is one person's paperwork. A bare chip
            #: in a list of counted chips is the most misleading thing
            #: on the row.
            + " ".join(f'<span class="cit"><b>{E(cn)}</b> {v}</span>'
                       for cn, v in (pg["employer_citizenship"].get(e) or {}).items())
            + "</td></tr>"
            for e, _ in (pg.get("top_employers") or [])[:12])
        nat = f"""
<h4>Where they came from</h4>
<p class="dnote">{fmt(pg['filings'], 'n')} permanent-residence filings in this
same group, {fmt(pg['citizenships'], 'n')} citizenships. This is the green-card
step and a different, much smaller program than the H-1B figures above. It is
not a subset of them and it is the only public record that puts a country
against an employer.</p>
<div class="chips">{chips}</div>
<h4>Which employer, which country</h4>
<div class="table-wrap"><table class="t"><thead><tr><th>Employer</th>
<th>Citizenship of the people sponsored</th></tr></thead>
<tbody>{rows}</tbody></table></div>
"""
    else:
        nat = ('<h4>Where they came from</h4><p class="dnote">No '
               'permanent-residence filings fall in this group, so no public '
               'record names a country for it. The H-1B files record no '
               'nationality at any level below the national total.</p>')

    return f"""
<details class="drill">
<summary>Who files these, and where the people come from</summary>
<div class="drillbody">
<h4>Who files</h4>
<p class="dnote">Employers by certified H-1B applications. Counted by
application, never by position, and every total is a floor because the files
carry the name as typed and nothing stable.</p>
<div class="two">
<div class="table-wrap"><table class="t"><thead><tr><th>Employer</th>
<th class="num">Applications</th></tr></thead><tbody>{who}</tbody></table></div>
<div class="table-wrap"><table class="t"><thead><tr><th>Job title</th>
<th class="num">Applications</th></tr></thead><tbody>{titles}</tbody></table></div>
</div>
{nat}
</div>
</details>
"""


def case_html(c, h1b_ind, h1b_occ, perm) -> str:
    nums = "".join(
        f'<div><div class="v">{E(fmt(resolve(f, p), how))}</div>'
        f'<div class="k">{E(label)}</div></div>'
        for label, f, p, how in c.evidence)
    more = (f'<a class="more" href="{E(c.href)}">See the filings &rarr;</a>'
            if c.href else "")
    caveat = f'<p class="caveat">{E(c.caveat)}</p>' if c.caveat else ""
    return f"""
<article class="case">
<h3>{E(c.title)}</h3>
<div class="nums">{nums}</div>
<p>{E(c.finding)}</p>
<p class="odd">{E(c.why_odd)}</p>
{more}
{drill_html(c, h1b_ind, h1b_occ, perm)}
{caveat}
</article>
"""


def build() -> int:
    h1b_ind = load("h1b_by_industry.json")
    h1b_occ = load("h1b_by_occupation.json")
    perm_ind = load("perm_by_industry.json")
    nat = resolve("h1b_by_industry.json", "certified_filings")
    codes = resolve("h1b_by_industry.json", "distinct_codes")
    perm = resolve("public_employer_perm.json", "public_rows")

    title = "The H-1B Explorer"
    desc = ("What the federal labor-visa record actually contains: gas "
            "stations, school districts, state agencies and the filings "
            "nobody expects, built from the Labor Department's own "
            "disclosure files.")

    parts = [head(title, desc), f"""
<div class="page-head">
<p class="kicker">Labor visas, from the federal disclosure files</p>
<h1>The H-1B Explorer</h1>
<p>H-1B is discussed as a visa for software engineers. Most of it is. This
site is about the rest.</p>
<p>Everything here is built from the Department of Labor's own disclosure
files and the USCIS employer data, at render time. No figure is typed onto a
page. Where the record stops, the pages say so rather than guessing.</p>
<p><strong>A certified application is permission to employ, not proof of
hiring.</strong> Nothing on this site says any employer or worker broke a
rule. These are public records of what employers asked for.</p>
</div>

<div class="stats">
  <div class="stat"><div class="n">{fmt(nat, 'n')}</div><p class="l">certified applications read</p>
    <p class="s">de-duplicated by case number across every quarterly release</p></div>
  <div class="stat"><div class="n">{fmt(codes, 'n')}</div><p class="l">industry codes</p>
    <p class="s">six digits, which separates a staffing firm from a law firm</p></div>
  <div class="stat"><div class="n">{fmt(perm, 'n')}</div><p class="l">public-sector green-card filings</p>
    <p class="s">with the worker's citizenship, FY2013&ndash;FY2024</p></div>
  <div class="stat"><div class="n">{len(CASES)}</div><p class="l">cases below</p>
    <p class="s">each one a figure you can check against the source</p></div>
</div>

<section class="block" id="cases">
<h2>The filings nobody expects</h2>
<p class="lede">Each of these is in the government's own files. Several are
perfectly ordinary things for a visa to cover; they are here because they are
the opposite of how the program is usually described. The figures resolve
from the data when this page is built, so none of them can go stale without
the page changing.</p>
<div class="cases">{"".join(case_html(c, h1b_ind, h1b_occ, perm_ind) for c in CASES)}</div>
</section>

<section class="block" id="reports">
<h2>The reports</h2>
<p class="lede">Each one stands alone and says what it cannot show.</p>
<div class="reports">
{"".join(f'<div class="report"><a href="{E(h)}">{E(t)}</a><p>{E(d)}</p></div>'
         for h, t, d in REPORTS)}
</div>
</section>

<section class="block" id="method">
<h2>How to read any of this</h2>
<ul class="note">
<li><strong>Count applications, never positions.</strong> One application can
cover forty workers. Weighting by positions hands every share to the bulk
filers.</li>
<li><strong>Positions are not people.</strong> A certified application is
permission to employ. Every figure here is a ceiling on intent, not a count
of arrivals.</li>
<li><strong>Never add initial and continuing approvals.</strong> A continuing
approval is the same person renewed; adding them counts one worker once a
year for as long as they stay.</li>
<li><strong>Industry and occupation are the employer's own answers</strong> on
its own form, made under penalty of perjury. They are not anyone's opinion
about a company, and they are also not audited.</li>
<li><strong>Every employer total is a floor.</strong> The files carry the name
as typed and nothing stable, so one company appears under many spellings.</li>
</ul>
<p class="note">This site shares its data and its builders with
<a href="https://phd-demographics.andy-barr.com/">the graduate-pipeline
site</a>, which covers degrees, enrolment and funding. The visa pages are
here; the pipeline pages are there.</p>
</section>
</div>
</main>
<script src="/analytics-beacon.js" defer></script>
<script src="/anchors.js" defer></script>
<script src="/sidebar.js"></script>
</body>
</html>
"""]
    write_text(OUT, "".join(parts))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(CASES)} cases, "
          f"{len(REPORTS)} reports")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(build())
    except EvidenceError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
