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
    write("09_the-green-card-step.html", f"""<!-- ref:perm -->
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
    write("08_the-route-that-shrank.html", f"""<!-- ref:j1 -->
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
    write("10_who-the-sponsors-are.html", f"""<!-- ref:sponsors -->
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
    write("11_the-partner-universities.html", f"""<!-- ref:partners -->
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
    write("09_who-sponsors-under-the-exemption.html", f"""<!-- ref:sponsors_ranked -->
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
    write("12_two-petitions-at-once.html", f"""<!-- ref:concurrent -->
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
    write("04_what-the-degrees-pay.html", f"""<!-- ref:earnings -->
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
    f, l = yrs[0], yrs[-1]
    chart = line([("Temporary visa", [(y, ra[y]["visa"]) for y in yrs], ORANGE, False),
                  ("Citizen / PR", [(y, ra[y]["citizen"]) for y in yrs], BLUE, False)],
                 height=196, ymax=60, ymin=20, ylines=4,
                 yfmt=lambda v: f"{v:.0f}%", xticks=yrs)
    rows = "".join(
        f"<tr><td>{y}</td><td class='n'>{ra[y]['citizen']:.1f}%</td>"
        f"<td class='n'>{ra[y]['visa']:.1f}%</td>"
        f"<td class='n'>{gap[str(y)]:.1f}</td>"
        f"<td class='n'>{head[str(y)]['visa']:,}</td></tr>" for y in yrs)
    growth = 100 * (head[str(l)]["visa"] / head[str(f)]["visa"] - 1)
    write("07_how-long-this-has-been-true.html", f"""<!-- ref:supporttrend -->
<div class="page">
  <p class="eyebrow">5. How long this has been true</p>
  <h2>The funding gap on page {{{{page:whopays}}}} is not new, and it has not widened.
  It has held for seven straight years</h2>
  <hr class="rule">

  <p>A single year cannot say whether a gap is recent or entrenched. The Survey of
  Earned Doctorates publishes the same question with every release, so the series
  below is assembled from seven of them, {f} through {l}.</p>

  <div class="stats">
    <div class="stat"><div class="v">{gap[str(f)]:.0f} &rarr; {gap[str(l)]:.0f} pts</div>
      <div class="l">the gap in {f} and in {l}. It has not moved</div></div>
    <div class="stat"><div class="v">{min(gap.values()):.1f}&ndash;{max(gap.values()):.1f}</div>
      <div class="l">the full range across all seven years</div></div>
    <div class="stat"><div class="v">+{growth:.0f}%</div>
      <div class="l">growth in visa holders funded principally by a research
      assistantship, {f} to {l}</div></div>
  </div>

  <div class="legend"><span class="lg"><span class="sw" style="border-top:2px solid {ORANGE}"></span>Temporary-visa holders</span><span class="lg"><span class="sw" style="border-top:2px solid {BLUE}"></span>U.S. citizens and permanent residents</span></div>
  <div class="fig">{chart}</div>
  <p class="cap"><b>Share of doctorate recipients funded principally by a research
  assistantship, by citizenship at graduation.</b> All fields. Source: NSF Survey of
  Earned Doctorates, primary-source-of-support table, seven releases.</p>

  <table>
    <tr><th>Year</th><th class="n">Citizens &amp; PR</th><th class="n">Visa holders</th>
        <th class="n">Gap (pts)</th><th class="n">Visa holders on an RA</th></tr>
    {rows}
  </table>

  <div class="note">Two things the chart does not say. First, the SED records that a
  student was funded by a research assistantship, not which award paid for it; the
  federal link comes from the Survey of Graduate Students and Postdoctorates, which
  shows federal support reaching doctoral students overwhelmingly through research
  assistantships &mdash; 52,428 federally supported RAs against 1,041 federally
  supported teaching assistantships. Second, both lines rise together: the citizen
  share is up {ra[l]['citizen'] - ra[f]['citizen']:.1f} points over the period and the
  visa share {ra[l]['visa'] - ra[f]['visa']:.1f}. The finding here is duration and
  scale, not deterioration. The series runs on all fields because NCSES revised the
  field taxonomy in {l - 1}, which would otherwise split a science-and-engineering
  series across two definitions.</div>
</div>
""")


BUILDERS = {"perm": page_perm, "j1": page_j1,
            "nonprofits": page_nonprofits, "partners": page_partners,
            "sponsors_ranked": page_sponsors_ranked, "concurrent": page_concurrent,
            "earnings": page_earnings,
            "support_trend": page_support_trend}

if __name__ == "__main__":
    want = sys.argv[1:] or list(BUILDERS)
    for k in want:
        if k not in BUILDERS:
            print(f"  unknown page: {k}")
            sys.exit(1)
        BUILDERS[k]()
