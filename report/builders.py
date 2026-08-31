#!/usr/bin/env python3
"""Generate data-driven page fragments into report/pages/.

Each builder reads a dataset and writes one numbered fragment. Numbering in
the filename fixes render order; generate.py derives footers, section numbers
and cross-references from that order, so a page can be inserted by choosing a
filename and nothing else has to be edited.

Usage:
  python3 report/builders.py            # write every page
  python3 report/builders.py perm       # just one
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "report" / "pages"
H1B = ROOT / "data" / "h1b"

BLUE, ORANGE, INK, MUTED, GRID = "#1d4ed8", "#c2410c", "#111827", "#4b5563", "#d4d4d8"


def J(path: Path):
    return json.loads(path.read_text())


def bars(rows, width=660, height=None, xmax=None, fmt=lambda v: f"{v:,.0f}"):
    """Horizontal bars: (label, value). One series, so no legend is needed."""
    height = height or 26 * len(rows) + 16
    xmax = xmax or max(v for _l, v in rows) * 1.12
    pad_l, pad_r = 232, 62
    plot = width - pad_l - pad_r
    out = [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
           f'xmlns="http://www.w3.org/2000/svg">']
    for i, (label, v) in enumerate(rows):
        y = 8 + i * 26
        out.append(f'<text x="{pad_l-12}" y="{y+13}" text-anchor="end" font-size="11" '
                   f'fill="{INK}">{label}</text>')
        w = max(plot * v / xmax, 1.5)
        out.append(f'<rect x="{pad_l}" y="{y+3}" width="{w:.1f}" height="15" rx="2" '
                   f'fill="{BLUE}"/>')
        out.append(f'<text x="{pad_l+w+7:.1f}" y="{y+15}" font-size="10.5" fill="{MUTED}" '
                   f'font-variant-numeric="tabular-nums">{fmt(v)}</text>')
    out.append("</svg>")
    return "".join(out)


def line(series, width=660, height=210, ymax=None, ymin=0, yfmt=None,
         xticks=(), pad=46, padr=126, top=16, bot=32, ylines=4):
    yfmt = yfmt or (lambda v: f"{v:,.0f}")
    xs = [p[0] for p in series[0][1]]
    x0, x1 = min(xs), max(xs)
    ymax = ymax or max(v for _l, pts, *_ in series for _x, v in pts) * 1.12
    def X(v): return pad + (v - x0) / max(x1 - x0, 1) * (width - pad - padr)
    def Y(v): return top + (ymax - v) / (ymax - ymin) * (height - top - bot)
    out = [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
           f'xmlns="http://www.w3.org/2000/svg">']
    for k in range(ylines + 1):
        v = ymin + (ymax - ymin) * k / ylines
        out.append(f'<line x1="{pad}" y1="{Y(v):.1f}" x2="{width-padr+6}" y2="{Y(v):.1f}" '
                   f'stroke="{GRID}" stroke-width="0.75"/>')
        out.append(f'<text x="{pad-8}" y="{Y(v)+3.5:.1f}" text-anchor="end" font-size="10.5" '
                   f'fill="{MUTED}" font-variant-numeric="tabular-nums">{yfmt(v)}</text>')
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


def write(name: str, html: str):
    (PAGES / name).write_text(html.rstrip() + "\n")
    print(f"  wrote report/pages/{name}")


# ---------------------------------------------------------------- pages

def page_perm():
    d = J(H1B / "perm_pipeline.json")
    adm = [r for r in d["class_of_admission"] if r["value"] != "(not stated)"][:7]
    rows = "".join(
        f"<tr><td>{r['value']}</td><td class='n'>{r['count']:,}</td>"
        f"<td class='n'>{r['share']}%</td></tr>" for r in adm)
    ctry = "".join(
        f"<tr><td>{r['value'].title()}</td><td class='n'>{r['count']:,}</td>"
        f"<td class='n'>{r['share']}%</td></tr>" for r in d["country_of_citizenship"][:6])
    top = adm[0]
    st = {r["value"]: r["count"] for r in d["case_status"]}
    write("25_the-green-card-step.html", f"""<!-- ref:perm -->
<div class="page">
  <p class="eyebrow">8. The green card step</p>
  <h2>Nearly six in ten permanent-residence filings begin on an H-1B</h2>
  <hr class="rule">

  <p>PERM is where an employer certifies to the Department of Labor that no
  U.S. worker was available for a job it intends to fill permanently. The
  disclosure file records the status the beneficiary already held.</p>

  <div class="stats">
    <div class="stat"><div class="v">{top['share']}%</div>
      <div class="l">of {d['applications']:,} FY2024 filings were made for someone
      already on an H-1B</div></div>
    <div class="stat"><div class="v">{d['country_of_citizenship'][0]['share']}%</div>
      <div class="l">were for citizens of {d['country_of_citizenship'][0]['value'].title()},
      the largest single origin</div></div>
    <div class="stat"><div class="v">{st.get('CERTIFIED-EXPIRED', 0):,}</div>
      <div class="l">certifications lapsed unused, against {st.get('CERTIFIED', 0):,}
      live</div></div>
  </div>

  <h3>Status held when the application was filed</h3>
  <table>
    <tr><th>Class of admission</th><th class="n">Applications</th><th class="n">Share</th></tr>
    {rows}
  </table>

  <h3>Country of citizenship</h3>
  <table>
    <tr><th>Country</th><th class="n">Applications</th><th class="n">Share</th></tr>
    {ctry}
  </table>
  <p class="cap" style="margin-top:4px">Source: US DOL Office of Foreign Labor
  Certification, PERM disclosure data, FY2024.</p>

  <div class="note">A certification is not a green card. USCIS must still approve an
  I-140 and a visa number must be available, which for the largest origin countries
  takes years. Counts are applications, not people.</div>
</div>
""")


def page_j1():
    d = J(H1B / "j1_scholars.json")
    ch = d["change_between_complete_years"]
    yrs = [y for y in d["complete_years"]]
    pts = lambda k: [(y, d["series"][str(y)][k]) for y in yrs]
    chart = line([("Research scholar", pts("research_scholar"), BLUE, False),
                  ("Short-term scholar", pts("short_term_scholar"), ORANGE, True)],
                 height=206, ymax=40000, yfmt=lambda v: f"{v/1000:.0f}k",
                 xticks=[2015, 2018, 2021, 2024])
    rows = "".join(
        f"<tr><td>{d['labels'][k]}</td><td class='n'>{ch[k]['from']:,}</td>"
        f"<td class='n'>{ch[k]['to']:,}</td><td class='n'>{ch[k]['pct']:+.0f}%</td></tr>"
        for k in ("research_scholar", "professor", "short_term_scholar", "total"))
    write("24_the-route-that-shrank.html", f"""<!-- ref:j1 -->
<div class="page">
  <p class="eyebrow">7. The route that shrank</p>
  <h2>One uncapped academic route is going the other way</h2>
  <hr class="rule">

  <p>The J-1 research scholar category needs no numerical cap, no labour condition
  application and no wage floor. It is the cheapest lawful way to place a foreign
  researcher in a university laboratory &mdash; and it has been falling for a decade.</p>

  <div class="legend">
    <span class="lg"><span class="sw" style="border-top:2px solid {BLUE}"></span>Research scholar</span>
    <span class="lg"><span class="sw" style="border-top:2px dashed {ORANGE}"></span>Short-term scholar</span>
  </div>
  <div class="fig">{chart}</div>
  <p class="cap"><b>J-1 academic participants by calendar year of program begin date,
  {yrs[0]}&ndash;{yrs[-1]}.</b> The 2020 and 2021 troughs are the pandemic closure.
  Source: BridgeUSA.</p>

  <table>
    <tr><th>Category</th><th class="n">{yrs[0]}</th><th class="n">{yrs[-1]}</th>
        <th class="n">Change</th></tr>
    {rows}
  </table>

  <div class="note">The academic categories fell several times harder than the exchange
  programme as a whole. CY2025 is excluded: the source publishes it as data through
  approximately March, and measuring into a partial year turns a 33% fall into a 51% one.</div>
</div>
""")


def page_nonprofits():
    d = J(H1B / "nonprofit_990s.json")["organizations"]
    filers = J(H1B / "h1b_nonprofit_filers.json")["watched_nonprofits"]
    rows = []
    for org in sorted(d.values(), key=lambda o: -(o["filings"][-1]["revenue"] or 0)):
        f = org["filings"]
        rows.append(f"<tr><td>{org['name']}</td><td class='n'>FY{f[0]['year']}</td>"
                    f"<td class='n'>${(f[0]['revenue'] or 0)/1e6:,.1f}M</td>"
                    f"<td class='n'>${(f[-1]['revenue'] or 0)/1e6:,.1f}M</td>"
                    f"<td class='n'>{org['revenue_growth_pct']:+.0f}%</td></tr>")
    oa = d["822344731"]
    oaf = {x["year"]: x["revenue"] for x in oa["filings"]}
    oh = filers.get("Open Avenues Foundation", {})
    hb = ", ".join(f"FY{y} {oh[y]['total']}" for y in sorted(oh) if oh[y]["total"])
    write("21_who-the-sponsors-are.html", f"""<!-- ref:sponsors -->
<div class="page">
  <p class="eyebrow">9. Who the sponsors are</p>
  <h2>The affiliated nonprofits, sized by their own tax filings</h2>
  <hr class="rule">

  <p>USCIS counts petitions from nonprofits affiliated with universities but names
  none of them. The Employer Data Hub names employers but records no cap status.
  Form 990 is the one public record that sizes a named filer.</p>

  <table>
    <tr><th>Organisation</th><th class="n">From</th><th class="n">Revenue then</th>
        <th class="n">FY2023</th><th class="n">Change</th></tr>
    {"".join(rows)}
  </table>
  <p class="cap" style="margin-top:4px">IRS Form 990 total revenue. Source: ProPublica
  Nonprofit Explorer.</p>

  <h3>Open Avenues Foundation</h3>
  <p>The organisation behind the Build Fellowship, and the clearest public example of
  the affiliated-nonprofit route. Revenue rose from
  <b>${oaf[min(oaf)]:,}</b> in FY{min(oaf)} to <b>${oaf[max(oaf)]:,}</b> in FY{max(oaf)}.
  Its H-1B approvals over a comparable period: {hb}.</p>

  <div class="note">Revenue is not a count of sponsorships, and a 990 records no cap
  status. The organisations above file H-1B petitions at volume and fall within the
  statutory cap-exempt employer types; no published source confirms cap status for any
  named employer.</div>
</div>
""")


def page_partners():
    d = J(H1B / "build_fellowship_partners.json")
    ps = d["partners"]
    top = sorted((p for p in ps if p["masters"]["share"] is not None),
                 key=lambda p: -p["masters"]["share"])[:10]
    rows = "".join(
        f"<tr><td>{p['ipeds_name'][:44]}</td><td class='n'>{p['state']}</td>"
        f"<td class='n'>{p['masters']['share']}%</td>"
        f"<td class='n'>{p['masters']['nra'] + p['doctorate']['nra']:,}</td></tr>"
        for p in top)
    tot = sum(p["masters"]["nra"] + p["doctorate"]["nra"] for p in ps)
    write("22_the-partner-universities.html", f"""<!-- ref:partners -->
<div class="page">
  <p class="eyebrow">10. The partner universities</p>
  <h2>Where the Build Fellowship says it operates</h2>
  <hr class="rule">

  <p>The organisation publishes {d['partners_published']} university partners across 20
  states. Joined to IPEDS, those institutions conferred <b>{tot:,}</b> non-resident
  graduate STEM degrees between {d['ipeds_window'][0]} and {d['ipeds_window'][1]}.</p>

  <h3>Partners with the highest non-resident master's share</h3>
  <table>
    <tr><th>Institution</th><th class="n">State</th>
        <th class="n">Non-resident master's</th><th class="n">Grad non-res degrees</th></tr>
    {rows}
  </table>
  <p class="cap" style="margin-top:4px">Partner list from buildfellowship.com/impact;
  degree figures from IPEDS Completions, {d['ipeds_window'][0]}&ndash;{d['ipeds_window'][1]}.</p>

  <div class="note">A partnership is the organisation&rsquo;s own claim that it trains
  students at that institution. It does not mean the university sponsors anyone, employs
  a fellow, or is party to any petition &mdash; the affiliation that confers cap exemption
  is the nonprofit&rsquo;s. By reported participants the list is led by Suffolk, Boston
  University and City College of San Francisco; Harvard and Northeastern are each shown at
  fewer than ten students.</div>
</div>
""")


def page_sponsors_ranked():
    """Replaces the NAICS-61 page: better candidates, and the proxy failure."""
    r = J(ROOT / "data" / "cap_exempt" / "sponsor_ranking.json")
    c = J(ROOT / "data" / "cap_exempt" / "proxy_comparison.json")
    top = r["sponsors"][:9]
    rows = "".join(
        f"<tr><td>{s['employer'].title()[:42]}</td><td class='n'>{s['state']}</td>"
        f"<td class='n'>{s['approvals']:,}</td></tr>" for s in top)
    miss = "".join(
        f"<tr><td>{m['employer'].title()[:40]}</td><td class='n'>{m['approvals']:,}</td>"
        f"<td>{(m['naics'] or '')[:30]}</td></tr>"
        for m in c["directory_only"]["largest"][:5])
    write("20_who-sponsors-under-the-exemption.html", f"""<!-- ref:sponsors_ranked -->
<div class="page">
  <p class="eyebrow">8. Who sponsors under the exemption</p>
  <h2>The largest filers among employers treated as cap-exempt</h2>
  <hr class="rule">

  <p>No government source records cap status against a named employer, so the
  employers below come from public directories that infer it. Every figure beside
  them is USCIS&rsquo;s own: <b>{r['matched_in_hub']:,}</b> of {r['candidates']:,}
  candidates appear in the Employer Data Hub, accounting for
  <b>{r['total_approvals']:,}</b> approvals over FY{r['years'][0]}&ndash;FY{r['years'][-1]}.</p>

  <table>
    <tr><th>Employer</th><th class="n">State</th><th class="n">Petitions approved</th></tr>
    {rows}
  </table>
  <p class="cap" style="margin-top:4px">Candidate list from public cap-exempt
  directories; approvals from the USCIS H-1B Employer Data Hub.</p>

  <h3>Why the industry code cannot be used instead</h3>
  <p>Counting employers filing under Educational Services fails: the codes are
  self-reported and often describe something other than the institution, so major
  research employers are absent from that category entirely.</p>
  <table>
    <tr><th>Employer</th><th class="n">Approvals</th><th>Files under</th></tr>
    {miss}
  </table>
  <p class="cap" style="margin-top:4px">Employers the directories identify and an
  industry-code filter misses. FY{c['years'][0]}&ndash;FY{c['years'][-1]}.</p>

  <div class="note">The two approaches disagree in both directions: the directories
  name {c['directory_only']['count']} employers the industry code misses, and the code
  captures {c['naics_61_only']['count']:,} the directories exclude &mdash; largely school
  districts and for-profit colleges, which are not cap-exempt. That two independent
  proxies disagree this sharply is why the exemption cannot be measured from published
  data.</div>
</div>
""")


def page_concurrent():
    d = J(ROOT / "data" / "buildfellowship" / "employer_h1b.json")
    b = d["concurrent_baseline"]
    top = [e for e in d["employers"] if e["concurrent"]][:10]
    rows = "".join(
        f"<tr><td>{e['employer'][:38]}</td><td class='n'>{e['fellowship_projects']}</td>"
        f"<td class='n'>{e['approvals']:,}</td><td class='n'>{e['concurrent']}</td></tr>"
        for e in top)
    write("23_two-petitions-at-once.html", f"""<!-- ref:concurrent -->
<div class="page">
  <p class="eyebrow">11. Two petitions at once</p>
  <h2>The employers hosting fellows file concurrent petitions at {b['ratio']:.0f} times the rate</h2>
  <hr class="rule">

  <p>The arrangement requires a worker to hold two H-1B petitions simultaneously:
  a cap-exempt one through the nonprofit, and one at the company where the work is
  done. USCIS reports concurrent petitions as their own category.</p>

  <div class="stats">
    <div class="stat"><div class="v">{b['fellowship_rate_pct']:.0f}%</div>
      <div class="l">of the {b['fellowship_employers']} fellowship employers filed a
      concurrent petition</div></div>
    <div class="stat"><div class="v">{b['all_rate_pct']}%</div>
      <div class="l">of all {b['all_employers_in_band']:,} employers of comparable size
      did</div></div>
    <div class="stat"><div class="v">{b['ratio']:.0f}&times;</div>
      <div class="l">the difference, FY{b['years'][0]}&ndash;FY{b['years'][-1]}</div></div>
  </div>

  <table>
    <tr><th>Employer</th><th class="n">Fellowship projects</th>
        <th class="n">Approvals</th><th class="n">Concurrent</th></tr>
    {rows}
  </table>
  <p class="cap" style="margin-top:4px">Employer names taken from fellows&rsquo; published
  biographies and matched to the USCIS H-1B Employer Data Hub. Approvals are all
  petition types.</p>

  <div class="note">This is an association, not a demonstration. These firms were
  identified <i>because</i> they host fellows, so some difference is expected &mdash;
  though not one of this size. No source links a named worker to a petition, and a
  concurrent approval at one of these employers is not evidence that a fellow holds it.
  Establishing that would need the cap status USCIS declines to publish.</div>
</div>
""")


def page_earnings():
    d = J(ROOT / "site" / "data" / "stem_earnings.json")
    fields = [f for f in d["fields"] if f["masters"]]
    show = sorted(fields, key=lambda f: -f["doctorate"])[:9]
    rows = "".join(
        f"<tr><td>{f['name'].rstrip('.')[:38]}</td>"
        f"<td class='n'>${f['bachelors']:,}</td>"
        f"<td class='n'>${f['masters']:,}</td>"
        f"<td class='n'>${f['doctorate']:,}</td>"
        f"<td class='n'>{f['doctorate_premium_pct']:+.0f}%</td></tr>" for f in show)
    below = d["fields_where_doctorate_pays_below_masters"]
    write("11_what-the-degrees-pay.html", f"""<!-- ref:earnings -->
<div class="page">
  <p class="eyebrow">3. What the degrees pay</p>
  <h2>The doctorate pays, but it takes six years to start collecting</h2>
  <hr class="rule">

  <p>Domestic doctorate conversion is falling. The most obvious explanation is
  price: a graduate with a STEM bachelor&rsquo;s can take an industry job now, or
  spend six years on a stipend first.</p>

  <div class="stats">
    <div class="stat"><div class="v">+{d['median_doctorate_premium_over_bachelors_pct']:.0f}%</div>
      <div class="l">median earnings premium of a doctorate over a bachelor&rsquo;s in the
      same field, one year after each finishes</div></div>
    <div class="stat"><div class="v">{len(below)} of {d['fields_with_both_masters_and_doctorate']}</div>
      <div class="l">fields where the doctorate pays <i>less</i> than the master&rsquo;s
      in that field</div></div>
    <div class="stat"><div class="v">{d['levels']['doctorate']['programmes']}</div>
      <div class="l">doctoral programmes with earnings published, against
      {d['levels']['bachelors']['programmes']:,} at bachelor&rsquo;s level</div></div>
  </div>

  <h3>Median earnings one year after completion</h3>
  <table>
    <tr><th>Field</th><th class="n">Bachelor&rsquo;s</th><th class="n">Master&rsquo;s</th>
        <th class="n">Doctorate</th><th class="n">Doctorate vs bachelor&rsquo;s</th></tr>
    {rows}
  </table>
  <p class="cap" style="margin-top:4px">Source: U.S. Department of Education, College
  Scorecard, field of study file. Highest-paying doctoral fields shown.</p>

  <div class="note">This is not the return to a doctorate. Each figure is measured one
  year after that credential finishes, so the bachelor&rsquo;s cohort is around 23 and the
  doctoral cohort around 29 &mdash; and the bachelor&rsquo;s holder has six years of
  earnings the comparison does not count. Read alongside page {{{{page:whopays}}}}: the
  doctorate is the funded route, and it is the one Americans take least.</div>
</div>
""")


def page_support_trend():
    d = J(ROOT / "site" / "data" / "support_trend.json")
    yrs = d["years"]
    ra = {y: d["series"][str(y)]["all_fields"]["sources"]["research"] for y in yrs}
    head = d["research_assistantship_headcount"]
    gap = d["research_assistantship_gap_pts"]
    vshare = d["visa_share_of_research_assistantships"]
    f, l = yrs[0], yrs[-1]
    chart = line([("Temporary visa", [(y, ra[y]["visa"]) for y in yrs], ORANGE, False),
                  ("Citizen / PR", [(y, ra[y]["citizen"]) for y in yrs], BLUE, False)],
                 height=164, ymax=60, ymin=20, ylines=3,
                 yfmt=lambda v: f"{v:.0f}%", xticks=yrs)
    rows = "".join(
        f"<tr><td>{y}</td><td class='n'>{ra[y]['citizen']:.1f}%</td>"
        f"<td class='n'>{ra[y]['visa']:.1f}%</td>"
        f"<td class='n'>{gap[str(y)]:.1f}</td>"
        f"<td class='n'>{head[str(y)]['visa']:,}</td></tr>" for y in yrs)
    growth = 100 * (head[str(l)]["visa"] / head[str(f)]["visa"] - 1)
    se = d["series"][str(l)]["science_and_engineering"]["sources"]["research"]
    write("14_how-long-this-has-been-true.html", f"""<!-- ref:supporttrend -->
<div class="page">
  <p class="eyebrow">5. How long this has been true</p>
  <h2>This is not a snapshot. The federally funded route through a doctorate has
  tilted toward visa holders in every year on record</h2>
  <hr class="rule">

  <p>The gap on page {{{{page:whopays}}}} is a single year. The Survey of Earned
  Doctorates asks the same question with every release, so the series below is built
  from seven of them, {f} through {l}: the pattern holds in all seven, and the visa
  share rises across them.</p>

  <div class="stats">
    <div class="stat"><div class="v">{ra[l]['visa']:.1f}%</div>
      <div class="l">of visa holders funded principally by a research
      assistantship in {l}, up from {ra[f]['visa']:.1f}% in {f}</div></div>
    <div class="stat"><div class="v">+{growth:.0f}%</div>
      <div class="l">growth in visa holders on a research assistantship,
      {head[str(f)]['visa']:,} to {head[str(l)]['visa']:,}</div></div>
    <div class="stat"><div class="v">{min(gap.values()):.0f}+ pts</div>
      <div class="l">the gap over citizens, in every one of the seven
      years &mdash; it never falls below {min(gap.values()):.1f}</div></div>
  </div>

  <div class="legend"><span class="lg"><span class="sw" style="border-top:2px solid {ORANGE}"></span>Temporary-visa holders</span><span class="lg"><span class="sw" style="border-top:2px solid {BLUE}"></span>U.S. citizens and permanent residents</span></div>
  <div class="fig">{chart}</div>
  <p class="cap"><b>Share of doctorate recipients funded principally by a research
  assistantship, by citizenship at graduation, {f}&ndash;{l}.</b> All fields. Research
  assistantships are the channel federal research money travels through. Source: NSF
  Survey of Earned Doctorates, primary-source-of-support table, seven releases.</p>

  <table>
    <tr><th>Year</th><th class="n">Citizens &amp; PR</th><th class="n">Visa holders</th>
        <th class="n">Gap (pts)</th><th class="n">Visa holders on an RA</th></tr>
    {rows}
  </table>

  <p style="margin-top:10px">Visa holders are now <b>{vshare[str(l)]}%</b> of everyone
  funded principally by a research assistantship, against {vshare[str(f)]}% in {f}
  &mdash; approaching half of the federally funded doctoral workforce.</p>

  <div class="note">The SED records that a student was funded by a research
  assistantship, not which award paid. The federal link comes from the Survey of
  Graduate Students and Postdoctorates: 52,428 federally supported research
  assistantships against 1,041 federally supported teaching assistantships. The series
  runs on all fields because NCSES revised the field taxonomy in {l - 1}, which would
  split a science-and-engineering series across two definitions; on the S&amp;E rollup
  the {l} gap is wider still, {se['citizen']:.1f}% against {se['visa']:.1f}%.</div>
</div>
""")



def page_fica():
    d = J(H1B / "fica_exposure.json")
    r = d["rates"]
    a = d["authorisations"]
    # The published series prices several wage levels; the middle one is used
    # in the text and all three are shown, because the wage is an assumption
    # and the page should not hide which one it rests on.
    wages = sorted({s["assumed_annual_wage"] for s in d["scenarios"]})
    mid = wages[len(wages) // 2]
    by = {(s["population"], s["assumed_annual_wage"]): s for s in d["scenarios"]}
    rows = "".join(
        f"<tr><td>${w:,} a year</td>"
        f"<td class='n'>${by[('OPT', w)]['employer_side_forgone'] / 1e9:.2f}bn</td>"
        f"<td class='n'>${by[('STEM OPT', w)]['employer_side_forgone'] / 1e9:.2f}bn</td>"
        f"<td class='n'>${(by[('OPT', w)]['combined_forgone'] + by[('STEM OPT', w)]['combined_forgone']) / 1e9:.2f}bn</td>"
        f"</tr>" for w in wages)
    # The salary half of the argument comes from the SDR. Compared within a
    # graduation cohort -- the only fair comparison, since the two groups are
    # not the same age -- pay is level, which is what makes the tax treatment
    # the operative difference rather than the wage.
    cite = d["statute"].split(";")[0].strip()   # the section, without the gloss
    o = J(ROOT / "site" / "data" / "doctorate_outcomes.json")
    cohort = o["median_salary_by_cohort"]
    recent = max(k.split(" \u2014 ")[1] for k in cohort)
    nat = cohort[f"US citizen at doctorate (native) \u2014 {recent}"]
    vis = cohort[f"Temporary visa at doctorate \u2014 {recent}"]
    write("16_the-discount.html", f"""<!-- ref:fica -->
<div class="page">
  <p class="eyebrow">6. The discount</p>
  <h2>Equal pay is not equal cost: an American graduate is the more expensive
  hire at the same salary</h2>
  <hr class="rule">

  <p>Compared within a graduation cohort, doctorate holders trained on a temporary visa
  earn about what their American classmates earn: among those who finished in
  {recent}, a median of <b>${vis:,}</b> against <b>${nat:,}</b> for citizens trained
  here. That is a statement about salary, and salary is not what an employer pays. Wages earned on Optional Practical Training are
  exempt from Social Security and Medicare tax under
  <span class="src">{cite}</span>. The graduate is cheaper to employ at the
  same salary.</p>

  <div class="stats">
    <div class="stat"><div class="v">{r['employer_side'] * 100:.2f}%</div>
      <div class="l">of payroll the employer does not pay on an OPT hire &mdash;
      ${d['per_100k_payroll']['employer_side']:,} on every $100,000 of wages</div></div>
    <div class="stat"><div class="v">{r['employer_plus_employee'] * 100:.1f}%</div>
      <div class="l">counting the employee side, which is also exempt</div></div>
    <div class="stat"><div class="v">{a['opt'] + a['stem_opt']:,}</div>
      <div class="l">OPT and STEM OPT authorisations in {d['year']} to which the
      exemption can apply</div></div>
  </div>

  <p>This is the mechanism behind the disadvantage. An American graduate competing for
  the same job carries {r['employer_side'] * 100:.2f}% in employer payroll tax that the
  OPT graduate does not, on identical work at an identical wage. The exemption is
  statutory and applies automatically &mdash; nobody has to seek it &mdash; which is
  what makes the cost comparison an employer faces different from the wage comparison
  the salary data shows.</p>

  <h3>Payroll tax not collected, {d['year']} authorisations</h3>
  <table>
    <tr><th>If wages average</th><th class="n">OPT, employer side</th>
        <th class="n">STEM OPT, employer side</th>
        <th class="n">Both, employer + employee</th></tr>
    {rows}
  </table>
  <p class="cap" style="margin-top:4px">The rates are statutory and the authorisation
  counts are published. <b>The wage is an assumption</b> &mdash; wages on OPT are not
  reported anywhere, which is why three levels are priced rather than one. Sources:
  {d['statute']}. Authorisation counts: DHS SEVP.</p>

  <div class="note">An authorisation is not a full-time year of employment, so applying
  an annual wage to a count overstates any single year. The exemption ends when the
  holder becomes a resident alien for tax purposes, generally after five calendar years
  in F or J status &mdash; so it is a discount on early-career employment, which is
  exactly the stage at which a new American graduate is competing.</div>
</div>
""")


LEVEL_LABEL = {"masters": "Master&rsquo;s", "doctorate": "Doctorate",
               "graduate": "Graduate, combined"}


def page_graduate_balance():
    d = J(ROOT / "site" / "data" / "graduate_balance.json")
    g = J(ROOT / "site" / "data" / "gss_citizenship_trend.json")
    gs, gp = g["shift"]["graduate_students"], g["shift"]["postdocs"]
    ser, yrs = d["series"], [str(y) for y in d["years"]]
    sh = d["shift"]
    f, l = yrs[0], yrs[-1]
    chart = line([("Master's", [(int(y), ser[y]["masters"]["share"]) for y in yrs],
                   ORANGE, False),
                  ("Doctorate", [(int(y), ser[y]["doctorate"]["share"]) for y in yrs],
                   BLUE, False)],
                 height=178, ymax=50, ymin=20, ylines=3,
                 yfmt=lambda v: f"{v:.0f}%",
                 xticks=[int(y) for y in yrs if int(y) % 5 == 0])
    rows = "".join(
        f"<tr><td>{LEVEL_LABEL[lv]}</td>"
        f"<td class='n'>{sh[lv]['first_share']:.1f}%</td>"
        f"<td class='n'>{sh[lv]['last_share']:.1f}%</td>"
        f"<td class='n'>{sh[lv]['change_pts']:+.1f}</td>"
        f"<td class='n'>{sh[lv]['nra_change_pct']:+,.0f}%</td>"
        f"<td class='n'>{sh[lv]['domestic_change_pct']:+,.0f}%</td></tr>"
        for lv in ("masters", "doctorate", "graduate"))
    write("04_where-the-balance-shifted.html", f"""<!-- ref:balance -->
<div class="page">
  <p class="eyebrow">3. Where the balance shifted</p>
  <h2>Across thirty years the shift is at master&rsquo;s level, and it is now
  approaching half of all core-STEM master&rsquo;s degrees</h2>
  <hr class="rule">

  <p>The doctorate is the smaller end of graduate education and the one most often
  measured. Taken across every year IPEDS supports, the master&rsquo;s degree moved
  more than four times as far.</p>

  <div class="stats">
    <div class="stat"><div class="v">{sh['masters']['last_share']:.1f}%</div>
      <div class="l">of core-STEM master&rsquo;s degrees went to non-residents in
      {l}, from {sh['masters']['first_share']:.1f}% in {f}</div></div>
    <div class="stat"><div class="v">+{sh['masters']['change_pts']:.1f} pts</div>
      <div class="l">the master&rsquo;s shift, against
      {sh['doctorate']['change_pts']:+.1f} points at doctorate level</div></div>
    <div class="stat"><div class="v">{sh['graduate']['last_share']:.1f}%</div>
      <div class="l">of all core-STEM graduate degrees combined, from
      {sh['graduate']['first_share']:.1f}%</div></div>
  </div>

  <div class="legend"><span class="lg"><span class="sw" style="border-top:2px solid {ORANGE}"></span>Master&rsquo;s</span><span class="lg"><span class="sw" style="border-top:2px solid {BLUE}"></span>Doctorate</span></div>
  <div class="fig">{chart}</div>
  <p class="cap"><b>Non-resident share of core-STEM degrees conferred,
  {f}&ndash;{l}.</b> First majors only. The doctorate peaked at
  {sh['doctorate']['peak_share']:.1f}% in {sh['doctorate']['peak_year']} and has
  fallen since; the master&rsquo;s has not turned. Source: NCES IPEDS Completions.</p>

  <table>
    <tr><th>Level</th><th class="n">{f}</th><th class="n">{l}</th>
        <th class="n">Change (pts)</th><th class="n">Non-resident</th>
        <th class="n">Domestic</th></tr>
    {rows}
  </table>

  <p style="margin-top:10px">A separate collection reaches further back and is
  restricted to science, engineering and health. On it, the temporary-visa share of
  graduate <i>enrolment</i> went from <b>{gs['first_share']}%</b> in
  {gs['first_year']} to <b>{gs['last_share']}%</b>, and among postdoctoral
  researchers from {gp['first_share']}% to <b>{gp['last_share']}%</b> &mdash; a
  majority of the people doing the country&rsquo;s postdoctoral science.</p>

  <div class="note">Domestic output rose at both levels over the period &mdash;
  master&rsquo;s {sh['masters']['domestic_change_pct']:+,.0f}%, doctorate
  {sh['doctorate']['domestic_change_pct']:+,.0f}% &mdash; so this is a change in
  share, not an American retreat. Non-resident is a <i>visa</i> category: a permanent
  resident is counted under their race and appears here as domestic, so these lines
  understate the foreign-born share and say nothing about where the visa holders end
  up. Page {{{{page:transition}}}} follows that.</div>
</div>
""")


def page_transition():
    d = J(ROOT / "site" / "data" / "doctorate_outcomes.json")
    g = J(ROOT / "site" / "data" / "graduate_balance.json")
    now = d["trained_on_a_visa_are_now_pct"]
    nat = now["US citizen at doctorate (naturalised)"]
    pr = now["Permanent resident at doctorate"]
    still = now["Temporary visa at doctorate"]
    abroad = now["Non-US, living abroad"]
    settled = nat + pr
    # Of those still in the country, the share that reached settled status.
    of_stayers = 100 * settled / (settled + still)
    bar = bars([("Naturalised U.S. citizen", nat),
                ("Permanent resident", pr),
                ("Still on a temporary visa", still),
                ("Living outside the U.S.", abroad)],
               height=118, xmax=42, fmt=lambda v: f"{v:.1f}%")
    write("09_from-non-immigrant-to-immigrant.html", f"""<!-- ref:transition -->
<div class="page">
  <p class="eyebrow">4. From non-immigrant to immigrant</p>
  <h2>The student visa is not a temporary category. For most who finish a doctorate
  on one, it is the first step to permanent residence</h2>
  <hr class="rule">

  <p>Every count on page {{{{page:balance}}}} is a <i>visa</i> count, which invites the
  assumption that these are visitors. The Survey of Doctorate Recipients follows the
  same people afterwards. Of those who earned a U.S. doctorate while on a temporary
  visa, <b>{settled:.1f}%</b> now hold citizenship or permanent residence &mdash; and
  only <b>{still:.1f}%</b> are still on a temporary visa.</p>

  <div class="stats">
    <div class="stat"><div class="v">{settled:.1f}%</div>
      <div class="l">are now U.S. citizens or permanent residents</div></div>
    <div class="stat"><div class="v">{nat:.1f}%</div>
      <div class="l">have naturalised &mdash; the single largest outcome</div></div>
    <div class="stat"><div class="v">{of_stayers:.0f}%</div>
      <div class="l">of those who stayed in the country reached citizenship or
      permanent residence</div></div>
  </div>

  <div class="fig">{bar}</div>
  <p class="cap"><b>Where doctorate recipients trained on a temporary visa are now.</b>
  {d['sample_rows']:,} respondents with a U.S.-earned doctorate, weighted to the
  population. Source: NSF Survey of Doctorate Recipients.</p>

  <p>Read the two pages together. A non-resident share of
  {g['shift']['graduate']['last_share']:.1f}% of graduate STEM degrees does not
  measure temporary visitors passing through. It measures the entry point of a route
  to settlement, and {of_stayers:.0f}% of those who stay complete it.</p>

  <div class="note">The survey covers every cohort from the 1970s on, so the balance
  between staying and leaving describes the whole period rather than any single year.
  Recent graduates have had less time to naturalise, which if anything understates the
  eventual rate. Status is recorded at the doctorate and again at survey; nothing here
  identifies which visa or which route was used, and the SED does not follow
  master&rsquo;s recipients at all &mdash; so the transition is measured at doctorate
  level and applied to the larger population only by inference.</div>
</div>
""")


def page_adjustments():
    d = J(ROOT / "site" / "data" / "lpr_adjustments.json")
    perm = J(H1B / "perm_pipeline.json")
    cls, yrs = d["classes"], [str(y) for y in d["years"]]
    f, l = yrs[0], yrs[-1]
    emp = cls["Employment-based"]
    share = d["employment_based_adjustment_share_pct"]
    order = ["Employment-based", "Immediate relatives", "Refugees",
             "Family-sponsored", "Diversity lottery"]
    rows = "".join(
        f"<tr><td>{name}</td>"
        f"<td class='n'>{cls[name]['total'][l]:,}</td>"
        f"<td class='n'>{100 * cls[name]['adjustment'][l] / cls[name]['total'][l]:.1f}%</td>"
        f"<td class='n'>{100 * cls[name]['new_arrival'][l] / cls[name]['total'][l]:.1f}%</td></tr>"
        for name in order if name in cls and cls[name]["total"].get(l))
    # PERM records the status held when permanent residence was sought.
    by_status = {r["value"]: r for r in perm["class_of_admission"]}
    h1b = by_status.get("H-1B", {})
    f1 = by_status.get("F-1", {})
    write("10_the-route-to-a-green-card.html", f"""<!-- ref:adjust -->
<div class="page">
  <p class="eyebrow">5. The route to a green card</p>
  <h2>The employment green card is not a way to bring someone in. It is
  overwhelmingly a way to convert someone already here</h2>
  <hr class="rule">

  <p>Page {{{{page:transition}}}} follows one population, doctorate recipients. DHS
  reports the same question for every permanent resident, splitting each class into
  people who arrived from abroad and people who were already in the United States on
  another status and adjusted without leaving.</p>

  <div class="stats">
    <div class="stat"><div class="v">{share[l]}%</div>
      <div class="l">of employment-based green cards in {l} went to people
      already in the country</div></div>
    <div class="stat"><div class="v">{emp['adjustment'][l]:,}</div>
      <div class="l">people, against {emp['new_arrival'][l]:,} who arrived from
      abroad</div></div>
    <div class="stat"><div class="v">{h1b.get('share', 0)}%</div>
      <div class="l">of labour certifications are filed for someone already on an
      H-1B, plus {f1.get('share', 0)}% on a student visa</div></div>
  </div>

  <h3>Adjusted from inside the U.S., or arrived from abroad &mdash; {l}</h3>
  <table>
    <tr><th>Class of admission</th><th class="n">Total</th>
        <th class="n">Adjusted status</th><th class="n">New arrival</th></tr>
    {rows}
  </table>
  <p class="cap" style="margin-top:4px">Source: DHS Yearbook of Immigration
  Statistics, table 6. Counts rounded by DHS to the nearest ten.</p>

  <p style="margin-top:10px">The contrast is the finding. Family-sponsored admission
  and the diversity lottery bring people in from outside; employment-based admission
  mostly changes the status of people already living and working here. It has run
  between {min(share.values())}% and {max(share.values())}% for the decade.</p>

  <div class="note">An adjustment shows the person was already in the country. It does
  <i>not</i> record which status they held before, so this table cannot say they
  studied here. The labour-certification figures beside it do carry that field, and
  they point the same way. Counts are persons, not degrees.</div>
</div>
""")


def page_leverage():
    perm = J(H1B / "perm_pipeline.json")
    lpr = J(ROOT / "site" / "data" / "lpr_adjustments.json")
    wc = J(ROOT / "site" / "data" / "working_conditions.json")
    by_status = {r["value"]: r for r in perm["class_of_admission"]}
    ctry = {r["value"]: r for r in perm["country_of_citizenship"]}
    h1b = by_status.get("H-1B", {})
    india = ctry.get("INDIA", {})
    l = str(lpr["years"][-1])
    sec = wc["dissatisfied_pct"]["job security"]
    sal = wc["dissatisfied_pct"]["salary"]
    vis, nat = "Temporary visa", "US citizen (native)"
    bar = bars([("Job security &mdash; temporary visa", sec[vis]),
                ("Job security &mdash; U.S. citizen", sec[nat]),
                ("Salary &mdash; temporary visa", sal[vis]),
                ("Salary &mdash; U.S. citizen", sal[nat])],
               height=118, xmax=34, fmt=lambda v: f"{v:.1f}%")
    write("17_who-holds-the-leverage.html", f"""<!-- ref:leverage -->
<div class="page">
  <p class="eyebrow">7. Who holds the leverage</p>
  <h2>The employer holds the visa. Losing the job means losing the right to
  remain in the country, and the worker knows it</h2>
  <hr class="rule">

  <p>The payroll-tax gap on page {{{{page:fica}}}} is a price difference. This is a
  bargaining difference, and it is larger. H-1B status is tied to one employer:
  the employer files the petition, and on termination the worker has
  <b>60 days</b> to find another sponsor or leave the country
  (<span class="src">8 CFR 214.1(l)(2)</span>). Permanent residence is filed by
  the employer too, for a named job. An American in the next chair can resign on
  two weeks&rsquo; notice and lose nothing but the job.</p>

  <div class="stats">
    <div class="stat"><div class="v">{h1b.get('share', 0)}%</div>
      <div class="l">of labour certifications are filed for someone already
      working for that employer on an H-1B</div></div>
    <div class="stat"><div class="v">{india.get('share', 0)}%</div>
      <div class="l">are for Indian nationals, who then wait years for a visa
      number &mdash; so the dependence runs for years, not months</div></div>
    <div class="stat"><div class="v">{lpr['employment_based_adjustment_share_pct'][l]}%</div>
      <div class="l">of employment-based green cards go to people already here
      on a temporary status &mdash; this is the normal condition of the route,
      not an edge case</div></div>
  </div>

  <h3>Dissatisfaction, doctorate holders working in the U.S.</h3>
  <div class="fig">{bar}</div>
  <p class="cap"><b>Share reporting dissatisfaction, by citizenship status now.</b>
  Workers on a temporary visa are <b>{sec[vis] / sec[nat]:.1f} times</b> as likely to
  be dissatisfied with their job security as citizens doing comparable work, and
  markedly more dissatisfied with pay. {wc['sample_rows']:,} employed respondents.
  Source: NSF Survey of Doctorate Recipients.</p>

  <div class="note">Two boundaries. This measures the <i>structure</i> of dependence
  and what workers report about it; no dataset records whether a visa holder
  accepted worse terms or declined to complain, and none is claimed here. And these
  respondents are <b>doctorate holders</b>, many of them academic postdocs &mdash;
  not the larger H-1B population, most of whom hold a bachelor&rsquo;s or
  master&rsquo;s and are not surveyed this way. On hours, this survey cannot settle
  the question either way: its top category is simply &ldquo;more than 40&rdquo;, so
  a forty-one-hour week and an eighty-hour week are the same answer, and both figures
  are self-reported to a federal survey by people whose right to remain depends on an
  employer.</div>
</div>
""")


def page_revenue():
    d = J(ROOT / "site" / "data" / "tuition.json")
    ser = d["series"]
    yrs = sorted(ser)
    f, l = yrs[0], yrs[-1]
    h = d["headline"]
    # "constant 2024 dollars, CPI-U (...)" -- take the year from the basis
    # rather than from the last series key, which is the data year, not the
    # deflator year.
    dollars = re.search(r"(\d{4})", d["basis"]["dollars"]).group(1)
    chart = line([("Non-resident", [(int(y), ser[y]["billed_nra_real"] / 1e9)
                                    for y in yrs], ORANGE, False),
                  ("Domestic", [(int(y), ser[y]["billed_domestic_real"] / 1e9)
                                for y in yrs], BLUE, False)],
                 height=170, ylines=3, yfmt=lambda v: f"${v:.1f}bn",
                 xticks=[int(y) for y in yrs if int(y) % 3 == 0])
    write("05_the-revenue.html", f"""<!-- ref:revenue -->
<div class="page">
  <p class="eyebrow">4. The revenue</p>
  <h2>The master&rsquo;s is the level that pays. Almost none of it is funded, and
  the billings have quadrupled</h2>
  <hr class="rule">

  <p>Page {{{{page:balance}}}} shows where the balance moved. This is why the level it
  moved at is the master&rsquo;s. A doctoral student is normally paid to be there
  &mdash; page {{{{page:whopays}}}}. A master&rsquo;s student normally is not: the
  Survey of Graduate Students puts master&rsquo;s assistantship rates at
  <b>7.0%</b> on a research assistantship and <b>6.9%</b> on a teaching one, so
  roughly <b>86%</b> hold neither and pay their own way.</p>

  <div class="stats">
    <div class="stat"><div class="v">${h['billed_nra_real_last'] / 1e9:.2f}bn</div>
      <div class="l">a year in published tuition billed to non-resident core-STEM
      master&rsquo;s graduates, from ${h['billed_nra_real_first'] / 1e9:.2f}bn in
      {f}</div></div>
    <div class="stat"><div class="v">+{h['growth_pct_real']:.0f}%</div>
      <div class="l">real growth over the period, after inflation</div></div>
    <div class="stat"><div class="v">86%</div>
      <div class="l">of master&rsquo;s students hold neither a research nor a
      teaching assistantship</div></div>
  </div>

  <div class="legend"><span class="lg"><span class="sw" style="border-top:2px solid {ORANGE}"></span>Non-resident</span><span class="lg"><span class="sw" style="border-top:2px solid {BLUE}"></span>Domestic</span></div>
  <div class="fig">{chart}</div>
  <p class="cap"><b>Published tuition and required fees billed to core-STEM
  master&rsquo;s graduates, constant {dollars} dollars.</b> Non-resident billings passed
  domestic in {l}, on {ser[l]['nra_degrees']:,} degrees against
  {ser[l]['domestic_degrees']:,}. Sources: IPEDS Institutional Characteristics and
  Completions, {ser[l]['institutions_matched']:,} institutions matched.</p>

  <div class="note">This is <b>sticker price, not receipts</b>: one year of published
  out-of-state graduate tuition multiplied by the degrees conferred, not net of
  discounts, waivers or aid, and not what any institution banked. A master&rsquo;s
  normally runs 1.5 to 2 years, so the figure for a whole programme is larger than
  the annual one shown. What the series establishes is the direction and the scale of
  the difference between the two levels, not an institution&rsquo;s revenue.</div>
</div>
""")


def page_where_it_is_the_model():
    d = J(ROOT / "site" / "data" / "gss_institution_ranking.json")
    nat = d["national"]
    ma = d["rankings"]["master's"]
    rows = "".join(
        f"<tr><td>{r['institution'][:44]}</td>"
        f"<td class='n'>{r['foreign']:,}</td><td class='n'>{r['total']:,}</td>"
        f"<td class='n'>{r['share']:.1f}%</td></tr>" for r in ma["by_share"][:10])
    big = "".join(
        f"<tr><td>{r['institution'][:44]}</td>"
        f"<td class='n'>{r['foreign']:,}</td><td class='n'>{r['total']:,}</td>"
        f"<td class='n'>{r['share']:.1f}%</td></tr>" for r in ma["by_count"][:5])
    write("06_where-it-is-the-model.html", f"""<!-- ref:model -->
<div class="page">
  <p class="eyebrow">5. Where it is the model</p>
  <h2>At some institutions the science and engineering master&rsquo;s is
  almost entirely a foreign-student programme</h2>
  <hr class="rule">

  <p>The national figures on page {{{{page:balance}}}} are averages, and averages
  hide the institutions that have built a programme around this. Of full-time
  science, engineering and health graduate enrolment, <b>{nat["master's"]['share']}%</b>
  at master&rsquo;s level and <b>{nat['doctoral']['share']}%</b> at doctoral level is
  held by temporary-visa holders. At the institutions below the master&rsquo;s figure
  is above ninety.</p>

  <h3>Highest temporary-visa share, full-time master&rsquo;s</h3>
  <table>
    <tr><th>Institution</th><th class="n">Visa holders</th>
        <th class="n">Enrolled</th><th class="n">Share</th></tr>
    {rows}
  </table>
  <p class="cap" style="margin-top:4px">Institutions with at least
  {ma['floor']} full-time master&rsquo;s students; {ma['eligible']} qualify.</p>

  <h3>Largest by number of visa holders</h3>
  <table>
    <tr><th>Institution</th><th class="n">Visa holders</th>
        <th class="n">Enrolled</th><th class="n">Share</th></tr>
    {big}
  </table>
  <p class="cap" style="margin-top:4px">Source: NSF Survey of Graduate Students and
  Postdoctorates, 2024. Enrolments in science, engineering and health units.</p>

  <div class="note">These are <b>enrolments, not degrees</b>, on a science,
  engineering and health basis &mdash; not comparable with the core-STEM degree
  counts elsewhere. Permanent residents are counted under their race and appear as
  domestic, so these shares are a floor on the foreign-born proportion. Single
  year, 2024.</div>
</div>
""")


def page_funding_and_enrolment():
    d = J(ROOT / "site" / "data" / "enrolment_and_funding.json")
    q = d["by_federal_rd_quartile"]
    dr, ma = q["doctoral"], q["master's"]
    mj = d["majority_foreign_doctoral"]
    rows = "".join(
        f"<tr><td>Q{a['quartile']}{' (least funded)' if a['quartile'] == 1 else ' (most funded)' if a['quartile'] == 4 else ''}</td>"
        f"<td class='n'>${a['federal_rd_median'] / 1e6:,.0f}m</td>"
        f"<td class='n'>{a['share']:.1f}%</td>"
        f"<td class='n'>{a['enrolled']:,}</td>"
        f"<td class='n'>{b['share']:.1f}%</td></tr>"
        for a, b in zip(dr, ma))
    mjrows = "".join(
        f"<tr><td>{r['institution'][:40]}</td>"
        f"<td class='n'>${r['federal_rd'] / 1e6:,.0f}m</td>"
        f"<td class='n'>{r['doctoral_share']:.1f}%</td>"
        f"<td class='n'>{r['doctoral_total']:,}</td></tr>" for r in mj["leading"][:7])
    write("07_where-the-money-is.html", f"""<!-- ref:funding -->
<div class="page">
  <p class="eyebrow">7. Where the money is</p>
  <h2>The federal research money and the foreign enrolment are in the same
  institutions</h2>
  <hr class="rule">

  <p>Page {{{{page:model}}}} shows where the visa share is highest. This asks whether
  those are also the institutions the taxpayer funds. Sorting every matched
  institution into quartiles by federal research and development expenditure gives a
  clear answer.</p>

  <table>
    <tr><th>Federal R&amp;D quartile</th><th class="n">Median federal R&amp;D</th>
        <th class="n">Doctoral visa share</th><th class="n">Doctoral students</th>
        <th class="n">Master&rsquo;s visa share</th></tr>
    {rows}
  </table>
  <p class="cap" style="margin-top:4px">{d['matched']} institutions matched between
  the enrolment survey and the R&amp;D survey; shares pooled within each quartile.
  Sources: NSF GSS 2024; NSF HERD FY2024 table 14.</p>

  <h3>Where the two meet</h3>
  <p>At <b>{mj['institutions']}</b> institutions a majority of doctoral students hold
  a temporary visa. Those institutions account for
  <b>${mj['federal_rd'] / 1e9:.1f}bn</b> of federal R&amp;D expenditure &mdash;
  <b>{mj['federal_rd_pct_of_matched']}%</b> of the matched total &mdash; and
  {mj['doctoral_students']:,} doctoral students.</p>
  <table>
    <tr><th>Institution</th><th class="n">Federal R&amp;D</th>
        <th class="n">Doctoral visa share</th><th class="n">Doctoral students</th></tr>
    {mjrows}
  </table>

  <div class="note">This page is about <b>doctoral</b> students, deliberately.
  Federal research money pays research assistantships and the graduate survey shows
  master&rsquo;s students are overwhelmingly unfunded, so a master&rsquo;s share says
  nothing about where grant money goes. HERD reports R&amp;D <b>expenditure</b>, not
  all federal money and not student support, and it is recorded at the institution
  &mdash; nothing here traces a dollar to a named student.
  {d['unmatched_count']} institutions could not be matched by name; unmatched does
  not mean unfunded.</div>
</div>
""")


def page_tuition_model():
    d = J(ROOT / "site" / "data" / "enrolment_and_funding.json")
    hi = [r for r in d["highest_masters_share"]
          if r.get("masters_foreign_tuition_billed")][:9]

    def money(v):
        return f"${v / 1e6:,.0f}m" if v >= 5e5 else f"${v / 1e3:,.0f}k"

    rows = "".join(
        f"<tr><td>{r['institution'][:38]}</td>"
        f"<td class='n'>{r['masters_share']:.1f}%</td>"
        f"<td class='n'>{r['masters_enrolled']:,}</td>"
        f"<td class='n'>{money(r['masters_foreign_tuition_billed'])}</td>"
        f"<td class='n'>{money(r['federal_rd'])}</td>"
        f"<td class='n'>{r['tuition_to_federal_rd']:.1f}&times;</td></tr>" for r in hi)
    write("08_the-other-model.html", f"""<!-- ref:tuitionmodel -->
<div class="page">
  <p class="eyebrow">8. The other model</p>
  <h2>Where the students fund the institution rather than the taxpayer funding
  the research</h2>
  <hr class="rule">

  <p>Page {{{{page:funding}}}} follows the federal money. The institutions with the
  very highest master&rsquo;s visa shares are somewhere else entirely: they receive
  little federal research money, and what they bill their foreign master&rsquo;s
  students dwarfs it.</p>

  <table>
    <tr><th>Institution</th><th class="n">Visa share</th>
        <th class="n">Enrolled</th><th class="n">Tuition billed</th>
        <th class="n">Federal R&amp;D</th><th class="n">Per $1 R&amp;D</th></tr>
    {rows}
  </table>
  <p class="cap" style="margin-top:4px">Tuition is one year of published out-of-state
  graduate tuition and required fees multiplied by the foreign master&rsquo;s head
  count. Institutions with at least {d['masters_floor']} full-time master&rsquo;s
  students. Sources: IPEDS {d['tuition_rate_source']}; NSF GSS 2024; NSF HERD
  FY2024.</p>

  <p>Harrisburg University of Science and Technology and the University of Central
  Missouri rank higher on share than anything listed above &mdash; 96.4% and 92.7%
  &mdash; and do not appear in the federal research survey at all.</p>

  <div class="note">Two different machines running on one visa. On page
  {{{{page:funding}}}} the taxpayer funds the research and the students work on it;
  here the students pay to be there. The tuition figure is <b>sticker price, not
  receipts</b>: gross of every waiver, remission and scholarship, and one year where
  a master&rsquo;s normally runs one and a half to two. It measures the scale of the
  difference between the two models, not any institution&rsquo;s income. The table is
  ordered by visa share rather than by the ratio, so institutions where tuition does
  <i>not</i> dominate appear too.</div>
</div>
""")


BUILDERS = {"perm": page_perm, "j1": page_j1,
            "nonprofits": page_nonprofits, "partners": page_partners,
            "sponsors_ranked": page_sponsors_ranked, "concurrent": page_concurrent,
            "earnings": page_earnings,
            "support_trend": page_support_trend,
            "fica": page_fica,
            "graduate_balance": page_graduate_balance,
            "transition": page_transition,
            "adjustments": page_adjustments,
            "leverage": page_leverage,
            "revenue": page_revenue,
            "model": page_where_it_is_the_model,
            "funding": page_funding_and_enrolment,
            "tuition_model": page_tuition_model}

if __name__ == "__main__":
    want = sys.argv[1:] or list(BUILDERS)
    for k in want:
        if k not in BUILDERS:
            print(f"  unknown page: {k}")
            sys.exit(1)
        BUILDERS[k]()
