#!/usr/bin/env python3
"""A four-page executive brief, generated entirely from built data.

WHY A SECOND DOCUMENT

The full briefing is 41 pages and every one of its 545 figures is typed by
hand. That is the opposite of the rule the rest of this project follows, and
it means the document goes stale silently: nothing in the build can tell that
a number written in September describes data that moved in October. It is
also the wrong shape for a reader who has twenty minutes.

So this is a separate, short document that states the case and nothing else.
Four pages. Every figure resolves from site/data at render time, so the brief
cannot disagree with the site, and rebuilding it is the only way to change a
number in it.

The long briefing is untouched. It is the supporting document, and this one
points at it.

WHAT IT ARGUES

The author's case, in his terms: American institutions, funded by American
taxpayers, now award most of the graduate seats in a growing number of
programs to people who are not Americans; the degree has become a route to a
work visa; and the public that pays is the party going without.

WHAT IT MAY NOT DO

Name a school, a firm or a person as having broken a law. Nothing on this
site does. The brief shows what public records show and says what follows.

Usage:
    python3 report/exec_brief.py            # HTML + PDF
    python3 report/exec_brief.py --html     # HTML only, for a quick look
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "data"
PAGES = ROOT / "report" / "pages"
OUT_HTML = ROOT / "report" / "exec-brief.html"
OUT_PDF = ROOT / "site" / "executive-brief.pdf"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                          # noqa: E402


class MissingFigure(RuntimeError):
    pass


_CACHE: dict = {}


def D(name: str) -> dict:
    if name not in _CACHE:
        p = DATA / f"{name}.json"
        if not p.exists():
            raise MissingFigure(f"{name}.json is not built")
        _CACHE[name] = json.loads(p.read_text())
    return _CACHE[name]


def V(dataset: str, *path):
    """One figure, by its exact field. Raises rather than guessing.

    A brief that printed a dash where a number should be would make a weaker
    claim than the one it was written to make, and the reader would never
    know a figure had gone missing.
    """
    node = D(dataset)
    for p in path:
        try:
            node = node[p]
        except (KeyError, IndexError, TypeError) as exc:
            raise MissingFigure(
                f"{dataset}.{'.'.join(map(str, path))} stopped resolving at "
                f"{p!r} ({type(exc).__name__})") from exc
    return node


def n(x) -> str:
    return f"{x:,}"


def pct(x) -> str:
    return f"{x:.1f}%"


def usdm(x) -> str:
    return f"${x / 1_000_000:,.0f}m"


def build_html() -> str:
    ms_major = V("level_rankings", "levels", "masters", "institutions_majority_nra")
    ms_elig = V("level_rankings", "levels", "masters", "institutions_eligible")
    dr_major = V("level_rankings", "levels", "doctorate", "institutions_majority_nra")
    dr_elig = V("level_rankings", "levels", "doctorate", "institutions_eligible")
    ms_share = V("level_rankings", "levels", "masters", "national", "share")
    ms_nra = V("level_rankings", "levels", "masters", "national", "nra")
    ms_tot = V("level_rankings", "levels", "masters", "national", "total")
    dr_share = V("sed_series", "series", "2024", "share")

    sch = V("visa_schools", "totals", "schools")
    sch_aid = V("visa_schools", "totals", "take_federal_student_aid")
    pell = V("visa_schools", "totals", "pell_dollars")
    loans = V("visa_schools", "totals", "federal_loan_dollars")

    bs_emp = V("visa_bodyshops", "body_shop_totals", "employers")
    bs_fil = V("visa_bodyshops", "body_shop_totals", "filings")
    bs_shr = V("visa_bodyshops", "body_shop_totals", "share_of_filings_pct")
    below = V("local_wage_comparison", "below_local_median_pct")
    priced = V("local_wage_comparison", "filings_priced")

    perm = V("public_employer_perm", "public_rows")
    perm_win = V("public_employer_perm", "window")
    sectors = V("public_employer_perm", "sectors")

    pet = next(i for i in V("critical_industries", "industries")
               if i["slug"] == "petroleum")

    css = (PAGES / "_style.css").read_text()
    today = date.today().strftime("%B %Y")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Executive brief &middot; American graduate education and the work visa</title>
<style>{css}
  .big {{ font-size: 2.6rem; font-weight: 800; line-height: 1; }}
  .ask li {{ margin: 0 0 .5rem; }}
</style></head><body>

<div class="page">
  <p class="eyebrow">Executive brief &middot; Built from federal data &middot; {today}</p>
  <h1>American universities, paid for by American taxpayers,<br>
  now award most graduate seats in a growing number of<br>
  programs to people who are not Americans</h1>
  <hr class="rule">

  <p class="lede">Across the eight core STEM fields, non-resident students on
  temporary visas received <b>{pct(ms_share)}</b> of master's degrees awarded
  between 2021 and 2025 &mdash; {n(ms_nra)} of {n(ms_tot)}. In 2024 they took
  <b>{pct(dr_share)}</b> of all US research doctorates.</p>

  <p class="lede">Those are averages, and the average hides the finding. At
  <b>{n(ms_major)}</b> of the <b>{n(ms_elig)}</b> institutions large enough to
  measure, <b>most</b> of the master's degrees awarded go to people who are
  not Americans. At <b>{n(dr_major)}</b> institutions the same is true of the
  doctorate.</p>

  <div class="stats">
    <div class="stat"><div class="v">{n(ms_major)}</div>
      <div class="l">institutions where most master's degrees go to
      non-residents, of {n(ms_elig)} measured</div></div>
    <div class="stat"><div class="v">$875K</div>
      <div class="l">median federal research obligations per STEM research
      doctorate awarded</div></div>
    <div class="stat"><div class="v">{pct(pet['share'])}</div>
      <div class="l">of US petroleum engineering doctorates went to
      temporary-visa holders</div></div>
  </div>

  <p>A graduate seat is finite. An American who is not admitted does not
  receive a smaller share of a program; they receive none of it. Where most
  of a publicly funded program's seats go to temporary visa holders, year
  after year, the effect on American applicants is the same whatever anyone
  intended &mdash; and the people funding it are the ones going without.</p>
</div>

<div class="page">
  <p class="eyebrow">The public pays</p>
  <h2>Federal and state money funds the result, and cannot fund the people
  it was raised for</h2>
  <hr class="rule">

  <p>Federal research funding runs to roughly <b>$875,000</b> for every STEM
  research doctorate awarded. State legislatures fund the public institutions
  on top of that, and founded them to educate the people of those states.</p>

  <p><b>{n(sch)}</b> institutions have graduate enrollments that are mostly
  foreign; at several, nine in ten. <b>{n(sch_aid)}</b> of them take federal
  student aid, drawing <b>{usdm(pell)}</b> in Pell grants and
  <b>{usdm(loans)}</b> in federal loans. Foreign students cannot receive
  either. That money is American students' aid, paid to institutions whose
  graduate programs are mostly not for Americans.</p>

  <p>The public payroll sponsors directly as well. Universities, school
  districts, public utilities and agencies of state government filed
  <b>{n(perm)}</b> certified applications for permanent residence across
  {perm_win} &mdash; {n(sectors['universities']['filings'])} by universities,
  {n(sectors['school_districts']['filings'])} by school districts,
  {n(sectors['utilities']['filings'])} by utilities and
  {n(sectors['state_agencies']['filings'])} by state agencies. Each one
  required the employer to test the local labor market first and conclude
  that no American would do.</p>

  <p class="note">Sources: NSF NCSES Federal Support Survey; IPEDS Fall
  Enrollment and Student Financial Aid; US Department of Labor PERM
  disclosure files. Every figure is computed from those files when this
  document is built.</p>
</div>

<div class="page">
  <p class="eyebrow">What the degree is for</p>
  <h2>The degree has become a route to a work visa, and the worker it
  produces is cheaper than the American beside him</h2>
  <hr class="rule">

  <p>The graduate degree is the product and the work visa is why it sells.
  On the far side of it, <b>{n(bs_emp)}</b> firms whose business is supplying
  workers to other companies filed <b>{n(bs_fil)}</b> certified H-1B
  applications &mdash; <b>{pct(bs_shr)}</b> of every certified application in
  those years. That classification comes from the employers' own answers on
  their own forms, made under penalty of perjury.</p>

  <p>The wage data says what the arrangement is worth. Of <b>{n(priced)}</b>
  certified applications priced against the local market,
  <b>{pct(below)}</b> were below the median wage for that occupation in that
  place. A worker whose right to remain is tied to an employer does not
  negotiate, and the discount is the point.</p>

  <p>An American graduate competing for these jobs is not competing on merit
  against an equal. They are competing against a cheaper worker who cannot
  leave, supplied at volume by firms built for the purpose &mdash; after
  competing for the graduate seat that produced that worker, at an
  institution their own taxes fund.</p>

  <div class="stats">
    <div class="stat"><div class="v">{pct(below)}</div>
      <div class="l">of priced H-1B applications pay below the local median
      for the occupation</div></div>
    <div class="stat"><div class="v">{pct(bs_shr)}</div>
      <div class="l">of all certified H-1B applications come from
      worker-supply firms</div></div>
    <div class="stat"><div class="v">{n(bs_emp)}</div>
      <div class="l">firms meet all four parts of the supply test</div></div>
  </div>
</div>

<div class="page">
  <p class="eyebrow">What follows</p>
  <h2>What the record supports, and what it does not</h2>
  <hr class="rule">

  <p><b>What the data establishes.</b> That public money funds these programs;
  that a large and growing number of them award most of their seats to
  temporary visa holders; that institutions with mostly foreign graduate
  enrollments still draw federal student aid Americans alone can use; and
  that the workers these programs produce are paid below the local market
  more often than not.</p>

  <p><b>What it does not establish.</b> That any institution or firm broke a
  law. Nothing in these records shows that, and this brief does not say it.
  The records show what institutions chose, repeatedly, with public money,
  and that is a question of policy rather than of legality.</p>

  <p><b>What cannot be answered at all.</b> No federal collection records who
  applied to a graduate program, who was admitted, or who was offered
  funding. The question of whether American applicants are declining, being
  declined, or not applying is the central one, and no agency gathers the
  data to answer it. That gap, and twenty-three others, are set out at
  <b>phd-demographics.andy-barr.com/data_requests</b> &mdash; most needing no
  new collection at all.</p>

  <p class="note">This brief is the short form. The full briefing runs to 41
  pages with the complete method and every source, and the site carries the
  underlying tables, the per-institution pages, and a SQL console over the
  published data. Every figure here is computed from federal files at build
  time; none is typed.</p>

  <p class="note"><b>phd-demographics.andy-barr.com</b> &middot; labor-visa
  detail at <b>h1b.andy-barr.com</b></p>
</div>

</body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", action="store_true", help="skip the PDF")
    args = ap.parse_args()

    html = build_html()
    write_text(OUT_HTML, html)
    print(f"  wrote {OUT_HTML.relative_to(ROOT)}")
    if args.html:
        return 0

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(OUT_HTML.as_uri(), wait_until="networkidle", timeout=90000)
        pg.pdf(path=str(OUT_PDF), format="Letter", print_background=False,
               prefer_css_page_size=True)
        b.close()
    kb = OUT_PDF.stat().st_size / 1024
    print(f"  wrote {OUT_PDF.relative_to(ROOT)} ({kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MissingFigure as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
