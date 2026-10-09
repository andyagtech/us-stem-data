#!/usr/bin/env python3
"""One page per state, from the national per-institution file.

WHY A GENERATOR AND NOT A PAGE

Fifty-odd states cannot be hand-written and kept true. Every figure here comes
from site/data/institution_profiles.json at build time, so a rebuild moves the
pages and a stale number cannot survive one. Nothing in this file decides
anything about a state: the prose is assembled from that state's own numbers,
which is why the same template reads correctly for a state at the top of the
national distribution and for one at the bottom.

THE TEMPLATE MUST NOT ASSUME THE SITE'S OWN THESIS. Montana's research
doctorates go to non-residents 17.4% of the time against 38.9% nationally. A
template that said "the graduate pipeline is not American" would be false on
the first page it generated. So every comparative sentence is built from the
comparison it is making -- above, below or level -- and the national figure is
always printed beside the state's.

WHAT A STATE PAGE HOLDS

  * the state's own totals and where they sit among the states
  * every institution in the state, including the ones awarding no graduate
    degrees at all, because leaving them out would make the state look like
    its flagship
  * the concentration: how few institutions award most of the doctorates
  * the institution with the highest foreign share of graduate students on the
    NSF survey, where the survey covers any institution in the state
  * what the state itself appropriates per student, and how its foreign share
    moved over the same window

Usage:
    python3 scripts/build_state_pages.py              # the declared states
    python3 scripts/build_state_pages.py --all        # every state with data
    python3 scripts/build_state_pages.py --state MT
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SUBDIR = SITE / "states"
PROFILES = SITE / "data" / "institution_profiles.json"
SHEEO = SITE / "data" / "state_funding_and_enrolment.json"
CORPUS = SITE / "data" / "university_distribution.json"
OPT = SITE / "data" / "opt_by_university.json"
MEDICAL = ROOT / "data" / "medical" / "medical_dashboard.json"
RESIDENCY = SITE / "data" / "state_residency.json"
FUNDING = SITE / "data" / "institution_funding.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                          # noqa: E402

E = html.escape

NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana",
    "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
    "GU": "Guam", "VI": "US Virgin Islands", "AS": "American Samoa",
    "MP": "Northern Mariana Islands",
}
#: The states this script publishes. Kept explicit rather than "everything",
#: so adding a state is a decision someone made and not a side effect of a
#: rebuild. --all overrides it.
PUBLISH: tuple[str, ...] = tuple(sorted(
    set(NAMES) - {"GU", "VI", "AS", "MP"}))




def n(x) -> str:
    return f"{int(x or 0):,}"


def money(x) -> str:
    """Dollars at the precision the figure deserves."""
    x = int(x or 0)
    if x >= 1_000_000_000:
        return f"${x / 1_000_000_000:.2f}bn"
    if x >= 1_000_000:
        return f"${x / 1_000_000:.1f}m"
    return f"${x:,}"


def pct(num, den) -> float | None:
    return round(100 * num / den, 1) if den else None


def g(row: dict, block: str, field: str):
    return (row.get(block) or {}).get(field) or 0



def levels(row: dict) -> dict:
    """Undergraduate and graduate enrolment for one institution.

    IPEDS reports total enrolment and graduate enrolment, each with its own
    non-resident count, so the undergraduate figures are the remainder. That
    subtraction is only safe where graduate enrolment is REPORTED: an
    institution missing that block may have graduate students the file does not
    carry, and treating its whole enrolment as undergraduate would invent a
    clean undergraduate count out of a gap. Those are marked `grad_known`
    False and counted in the open on the page.
    """
    tot = row.get("total_enrolment") or {}
    grad = row.get("graduate_enrolment")
    t, tn = tot.get("total") or 0, tot.get("non_resident") or 0
    if isinstance(grad, dict) and grad.get("total") is not None:
        gt, gn = grad.get("total") or 0, grad.get("non_resident") or 0
        known = True
    else:
        gt = gn = 0
        known = False
    return {"ug_total": max(t - gt, 0), "ug_nra": max(tn - gn, 0),
            "grad_total": gt, "grad_nra": gn, "grad_known": known,
            "total": t, "total_nra": tn}


def head(title: str, desc: str, body_attrs: str = "") -> str:
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
  .lede {{ color: var(--text-muted); max-width: 74ch; line-height: 1.6; font-size: .92rem; margin: 0 0 1rem; }}
  .note {{ color: var(--text-muted); font-size: .78rem; line-height: 1.55; max-width: 82ch; margin: .9rem 0 0; }}
  .table-wrap {{ overflow-x: auto; }}
  table.t {{ width: 100%; border-collapse: collapse; font-size: .84rem; margin: .6rem 0 0; }}
  table.t th {{ text-align: left; font-size: .71rem; text-transform: uppercase; letter-spacing: .06em;
    color: var(--text-muted); font-weight: 600; padding: .4rem .5rem; border-bottom: 1px solid var(--border); white-space: nowrap; }}
  table.t td {{ padding: .42rem .5rem; border-bottom: 1px solid var(--border); }}
  table.t td.num, table.t th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  table.t td.muted {{ color: var(--text-muted); }}
  table.t td.share {{ font-weight: 600; color: var(--hl); }}
  table.t th.share-col {{ color: var(--hl); }}
  table.t td.share, table.t th.share-col {{
    background: color-mix(in srgb, var(--hl) 7%, transparent); }}
  table.t th.sortable {{ cursor: pointer; }}
  .scale {{ display: flex; align-items: center; gap: .7rem; margin: 1rem 0 0; flex-wrap: wrap; }}
  .scale .seg {{ font-size: .8rem; }}
  .barpair {{ margin: 1rem 0 0; }}
  .barpair .row {{ display: grid; grid-template-columns: 11rem 1fr auto; gap: .6rem; align-items: center;
    padding: .3rem 0; font-size: .86rem; }}
  .barpair .lab {{ color: var(--text-muted); }}
  /* display:block on both. A <span> is inline by default, so width and
     height are ignored on it -- every fill rendered at zero width inside a
     full-width track, which made a 2.9% bar and a 47.4% bar look identical. */
  .barpair .track {{ display: block; background: rgba(148,163,184,0.14);
    border-radius: 3px; height: 16px; overflow: hidden; }}
  .barpair .fill {{ display: block; height: 100%; border-radius: 3px;
    background: #3987e5; min-width: 2px; }}
  .barpair .fill.nat {{ background: rgba(148,163,184,0.55); }}
  .barpair .v {{ font-variant-numeric: tabular-nums; font-weight: 600; }}
  /* The state bar sits directly above its national counterpart, so each pair
     is one comparison. A gap after the pair keeps the eye from reading all
     four as a single ranked list. */
  .barpair .row.pair-end {{ margin-bottom: .55rem; }}
  @media (max-width: 620px) {{ .barpair .row {{ grid-template-columns: 1fr auto; }} .barpair .track {{ display: none; }} }}
  .callout {{ border: 1px solid var(--border); border-left-width: 3px; border-radius: 10px;
    padding: 1rem 1.1rem; margin: 1rem 0 0; background: var(--surface); }}
  .callout h3 {{ margin: 0 0 .35rem; font-size: 1rem; }}
  .callout p {{ margin: 0 0 .5rem; font-size: .88rem; line-height: 1.55; color: var(--text-muted); }}
</style>
  <script id="phd-theme-boot">(function(){{try{{var t=localStorage.getItem("phd-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
  <script defer src="/theme.js"></script>
</head>
<body data-page="state"{body_attrs}>
<a class="skip-link" href="#institutions">Skip to the institutions</a>
<main id="main">
<div class="wrap">
"""


def rank_of(states: list[dict], abbr: str, key: str, reverse=True) -> tuple[int, int]:
    """Where a state sits on one measure, counting only states that have it.

    A state with no doctorates has no non-resident share, and sorting None to
    the bottom would silently award it a rank it did not earn.
    """
    have = [s for s in states if s.get(key) is not None]
    have.sort(key=lambda s: s[key], reverse=reverse)
    for i, s in enumerate(have):
        if s["state"] == abbr:
            return i + 1, len(have)
    return 0, len(have)


def comparison(state_share: float | None, national: float) -> str:
    """The sentence that places the state against the country.

    Built from the direction of the gap, so this template is honest on a state
    at either end. The first state generated sits well BELOW the national
    figure, and a template that assumed otherwise would have published a false
    sentence on its first run.
    """
    if state_share is None:
        return ("This state awards too few research doctorates for a share to "
                "mean anything.")
    gap = round(state_share - national, 1)
    if abs(gap) < 1.0:
        return (f"That is level with the national figure of {national}%.")
    if gap < 0:
        return (f"That is <strong>{abs(gap)} points below</strong> the national "
                f"figure of {national}%. The pattern this site measures "
                f"nationally is weaker here, not stronger.")
    return (f"That is <strong>{gap} points above</strong> the national figure "
            f"of {national}%.")


def page(abbr: str, prof: dict, sheeo: dict | None, corpus: list[dict],
         opt_by_unitid: dict, j1_states: list, j1_year: str,
         residency: dict, funding: dict) -> str:
    name = NAMES.get(abbr, abbr)
    states = prof["states"]
    rec = next(s for s in states if s["state"] == abbr)
    insts = sorted((r for r in prof["institutions"] if r.get("state") == abbr),
                   key=lambda r: -g(r, "total_enrolment", "total"))

    nat_doc = sum(s["doctorates_awarded"] for s in states)
    nat_nra = sum(s["doctorates_non_resident"] for s in states)
    nat_share = round(100 * nat_nra / nat_doc, 1) if nat_doc else 0.0
    doc_share = rec.get("doctorates_non_resident_share")
    r_share, n_share = rank_of(states, abbr, "doctorates_non_resident_share")
    r_count, n_count = rank_of(states, abbr, "doctorates_awarded")

    # Concentration: how few institutions award most of the state's doctorates.
    with_doc = sorted((r for r in insts if g(r, "all_research_doctorates", "awarded")),
                      key=lambda r: -g(r, "all_research_doctorates", "awarded"))
    total_doc = sum(g(r, "all_research_doctorates", "awarded") for r in with_doc)
    top2 = sum(g(r, "all_research_doctorates", "awarded") for r in with_doc[:2])
    top2_share = pct(top2, total_doc)
    none_grad = [r for r in insts if not g(r, "graduate_enrolment", "total")]

    lv = [levels(r) for r in insts]
    ug_t = sum(x["ug_total"] for x in lv)
    ug_n = sum(x["ug_nra"] for x in lv)
    gr_t = sum(x["grad_total"] for x in lv)
    gr_n = sum(x["grad_nra"] for x in lv)
    unknown = sum(1 for x in lv if not x["grad_known"])
    nat = [levels(r) for r in prof["institutions"]]
    nat_ug = pct(sum(x["ug_nra"] for x in nat), sum(x["ug_total"] for x in nat))
    nat_gr = pct(sum(x["grad_nra"] for x in nat), sum(x["grad_total"] for x in nat))
    ug_share, gr_share = pct(ug_n, ug_t), pct(gr_n, gr_t)

    def money_cell(value):
        """A dash, not a zero, when the institution does not report the line."""
        if not value:
            return '<td class="num muted" data-sort="-1">&mdash;</td>'
        return f'<td class="num" data-sort="{int(value)}">{money(value)}</td>'

    def share_cell(num, den):
        if not den:
            return '<td class="num share" data-sort="-1">&mdash;</td>'
        v = pct(num, den)
        return f'<td class="num share" data-sort="{v}">{v}%</td>'

    level_rows = ""
    for r, x in sorted(zip(insts, lv), key=lambda z: -z[1]["total"]):
        fund = funding.get(str(r.get("unitid")), {})
        has_grad = "1" if (x["grad_known"] and x["grad_total"]) else "0"
        level_rows += (
            f'<tr data-has-grad="{has_grad}">'
            f'<td data-sort="{E(r["institution"].lower())}">{E(r["institution"])}</td>'
            f'<td class="num" data-sort="{x["ug_total"]}">{n(x["ug_total"])}</td>'
            f'<td class="num" data-sort="{x["ug_nra"]}">{n(x["ug_nra"])}</td>'
            + share_cell(x["ug_nra"], x["ug_total"])
            + (f'<td class="num" data-sort="{x["grad_total"]}">{n(x["grad_total"])}</td>'
               if x["grad_known"] else '<td class="num muted" data-sort="-1">&mdash;</td>')
            + (f'<td class="num" data-sort="{x["grad_nra"]}">{n(x["grad_nra"])}</td>'
               if x["grad_known"] else '<td class="num muted" data-sort="-1">&mdash;</td>')
            + share_cell(x["grad_nra"], x["grad_total"])
            + money_cell(fund.get("state_appropriations"))
            + money_cell(g(r, "federal", "rd_total"))
            + "</tr>")

    gap = (round(gr_share - ug_share, 1)
           if ug_share is not None and gr_share is not None else None)
    # ONE SCALE FOR THE FOUR BARS, set by the largest of them. Scaling to the
    # national graduate share clipped anything above it: Missouri's 25.7% and
    # the national 17.1% both drew a full-width bar, which is the one thing a
    # bar chart must never do.
    lvl_max = max([v for v in (ug_share, gr_share, nat_ug, nat_gr)
                   if v is not None] or [1]) or 1

    # The two levels are not one phenomenon at two sizes. They are separate
    # admissions systems, and the institution where they diverge most says
    # more than the state average does. Computed, not asserted.
    widest, widest_gap = None, 0.0
    for r, x in zip(insts, lv):
        if x["ug_total"] < 200 or x["grad_total"] < 100:
            continue
        u, q = pct(x["ug_nra"], x["ug_total"]), pct(x["grad_nra"], x["grad_total"])
        if u is None or q is None:
            continue
        if abs(q - u) > abs(widest_gap):
            widest, widest_gap = (r, x, u, q), round(q - u, 1)
    divergence = ""
    if widest is not None and abs(widest_gap) >= 2.0:
        r, x, u, q = widest
        divergence = (
            f'<p class="lede">The two levels diverge most at '
            f'<strong>{E(r["institution"])}</strong>: <strong>{u}%</strong> of '
            f'its {n(x["ug_total"])} undergraduates and <strong>{q}%</strong> '
            f'of its {n(x["grad_total"])} graduate students. These are '
            f'different admissions systems with different applicant pools, '
            f'different money and different reasons to say yes, and a single '
            f'state figure hides both.</p>')
    levels_html = f"""
  <section class="block" id="levels">
    <h2>Undergraduate and graduate, side by side</h2>
    <p class="lede">The same institutions at two levels. Undergraduate is the
    remainder once graduate enrolment is taken out of the total, and both
    levels carry their own non-resident count.
    {'In ' + E(name) + ' the graduate share is <strong>' + str(gap) +
     ' points higher</strong> than the undergraduate share.' if gap and gap > 0
     else 'In ' + E(name) + ' the two levels are close.' if gap is not None and abs(gap) <= 1
     else 'In ' + E(name) + ' the undergraduate share is the higher of the two.'}</p>
    <div class="barpair">
      <div class="row"><span class="lab">Undergraduate</span>
        <span class="track"><span class="fill" style="width:{min(100, (ug_share or 0) / lvl_max * 100):.1f}%"></span></span>
        <span class="v">{ug_share}%</span></div>
      <div class="row pair-end"><span class="lab">US undergraduate</span>
        <span class="track"><span class="fill nat" style="width:{min(100, (nat_ug or 0) / lvl_max * 100):.1f}%"></span></span>
        <span class="v">{nat_ug}%</span></div>
      <div class="row"><span class="lab">Graduate</span>
        <span class="track"><span class="fill" style="width:{min(100, (gr_share or 0) / lvl_max * 100):.1f}%"></span></span>
        <span class="v">{gr_share}%</span></div>
      <div class="row"><span class="lab">US graduate</span>
        <span class="track"><span class="fill nat" style="width:{min(100, (nat_gr or 0) / lvl_max * 100):.1f}%"></span></span>
        <span class="v">{nat_gr}%</span></div>
    </div>
    <p class="note" style="margin:0 0 .4rem">Click any column heading to sort.
    Click it again to reverse. The panel under the table narrows what is shown
    &mdash; everything is shown until you ask for less.</p>
    <div class="table-wrap"><table class="t" data-sortable data-controls>
      <thead><tr><th>Institution</th>
        <th class="num">Undergraduates</th><th class="num">Non-res</th>
        <th class="num share-col">Share</th>
        <th class="num">Graduates</th><th class="num">Non-res</th>
        <th class="num share-col">Share</th>
        <th class="num">State funding</th><th class="num">Federal R&amp;D</th></tr></thead>
      <tbody>{level_rows}</tbody></table></div>
    {divergence}
    <p class="note">{n(ug_n)} of {n(ug_t)} undergraduates and {n(gr_n)} of
    {n(gr_t)} graduate students.
    {'IPEDS reports no graduate enrolment for ' + n(unknown) + ' of these institutions; their rows show a dash rather than a zero, because the file not carrying a number is not the same as the number being none.' if unknown else ''}</p>
  </section>

"""

    notpub_html = """
  <section class="block" id="not-published">
    <h2>What is not published for a state this size</h2>
    <p class="lede">Two of the measures this site uses elsewhere do not exist
    at this scale, and the reason is the same in both cases: the agency
    publishes a ranked extract rather than the whole file.</p>
    <ul class="lede">
      <li><strong>Practical training is not published here.</strong> SEVP
      releases the top 100 and top 200 schools for OPT and STEM OPT, not every
      school. An institution outside those lists has no published figure at
      all. Its absence is a fact about the list, not about the institution, and
      it must never be read as a zero.</li>
      <li><strong>Student visa counts are not published by state.</strong> DHS
      reports SEVIS records nationally and names a few states per region in its
      commentary. For most states it publishes a percentage change and no
      count, so the number of foreign students physically in a state cannot be
      read off the federal release.</li>
      <li><strong>Enrolment is the measure that does exist.</strong> IPEDS asks
      every institution directly, which is why this page is built from it. It
      counts students enrolled, not visas issued, and the two are different
      questions.</li>
    </ul>
  </section>
"""

    # WHY THIS SECTION EXISTS, and why it is on every state page.
    #
    # A state figure is a weighted average, and in several states one very
    # large institution decides it. Utah reads 3.4% non-resident at graduate
    # level. Western Governors University holds 70.8% of the state's graduate
    # enrolment at 0% non-resident; take that one institution out and the rest
    # of Utah is 11.7%. Arizona reads 8.6% with Grand Canyon at 29.3% of the
    # state and 0.8% non-resident; without it the rest is 11.8%.
    #
    # Dropping those institutions would be cherry-picking, so nothing is
    # dropped. The blend is shown instead, with the figure recomputed without
    # the single largest. That is mechanical, needs no judgement about what
    # kind of institution anything is, and therefore holds for all fifty.
    by_grad = sorted(insts, key=lambda r: -g(r, "graduate_enrolment", "total"))
    state_gt = sum(g(r, "graduate_enrolment", "total") for r in insts)
    state_gn = sum(g(r, "graduate_enrolment", "non_resident") for r in insts)
    biggest = by_grad[0] if by_grad and state_gt else None
    blend_html = ""
    if biggest is not None:
        b_t = g(biggest, "graduate_enrolment", "total")
        b_n = g(biggest, "graduate_enrolment", "non_resident")
        b_weight = pct(b_t, state_gt)
        rest_t, rest_n = state_gt - b_t, state_gn - b_n
        rest_share = pct(rest_n, rest_t)
        state_share = pct(state_gn, state_gt)
        rows = "".join(
            f'<tr><td>{E(r["institution"])}</td>'
            f'<td class="num">{n(g(r, "graduate_enrolment", "total"))}</td>'
            f'<td class="num muted">{pct(g(r, "graduate_enrolment", "total"), state_gt)}%</td>'
            f'<td class="num share">{pct(g(r, "graduate_enrolment", "non_resident"), g(r, "graduate_enrolment", "total"))}%</td></tr>'
            for r in by_grad[:6] if g(r, "graduate_enrolment", "total"))
        moved = (abs(rest_share - state_share)
                 if rest_share is not None and state_share is not None else 0)
        verdict = (
            f'<div class="callout"><h3>One institution is moving this figure</h3>'
            f'<p><strong>{E(biggest["institution"])}</strong> holds '
            f'<strong>{b_weight}%</strong> of the graduate enrolment in '
            f'{E(name)} and is <strong>{pct(b_n, b_t)}%</strong> non-resident. '
            f'Take it out and the rest of the state is '
            f'<strong>{rest_share}%</strong>, against {state_share}% with it '
            f'in. A state average is not a description of its universities '
            f'when one of them is most of the state.</p></div>'
            if b_weight and b_weight >= 20 and moved >= 1.0 else
            f'<p class="note">No single institution decides this figure. The '
            f'largest, {E(biggest["institution"])}, holds {b_weight}% of the '
            f'state&rsquo;s graduate enrolment, and removing it moves the '
            f'state share from {state_share}% to {rest_share}%.</p>')
        blend_html = f"""
  <section class="block" id="blend">
    <h2>What the state figure is an average of</h2>
    <p class="lede">The largest graduate enrolments in {E(name)}, each with its
    own non-resident share. Nothing here is excluded from the figures above.
    The point is to show what they are made of.</p>
    <div class="table-wrap"><table class="t" data-sortable>
      <thead><tr><th>Institution</th><th class="num">Graduate students</th>
        <th class="num">Share of the state</th>
        <th class="num">Non-resident</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    {verdict}
  </section>
"""

    # OPT AND THE OTHER STUDENT VISAS.
    #
    # Practical training is the bridge from a student visa to a job, and it
    # applies at both levels: a foreign undergraduate can take OPT as readily
    # as a doctoral graduate. SEVP publishes it only for the top 100 and top
    # 200 schools, so it exists for some states and not others, and a state
    # with no row here has no published figure rather than no OPT.
    #
    # NEVER ADD OPT TO STEM OPT. A graduate who holds post-completion OPT and
    # then a STEM extension inside the same year appears in both columns, and
    # the sum counts that person twice. This site made exactly that mistake on
    # the visa-schools levels table: the overstatement grew from 2 students in
    # 2007 to 20,615 in 2024 and tilted the trend. The columns stay apart.
    opt_rows, opt_year = "", ""
    for r in sorted(insts, key=lambda r: -g(r, "total_enrolment", "total")):
        entry = opt_by_unitid.get(str(r.get("unitid")))
        if not entry:
            continue
        year = max(entry)
        opt_year = max(opt_year, year)
        o, st = entry[year].get("opt") or {}, entry[year].get("stem_opt") or {}
        opt_rows += (
            f'<tr><td>{E(r["institution"])}</td>'
            f'<td class="num">{n(o.get("authorizations"))}</td>'
            f'<td class="num muted">{o.get("rank", "&mdash;")}</td>'
            f'<td class="num">{n(st.get("authorizations"))}</td>'
            f'<td class="num muted">{st.get("rank", "&mdash;")}</td>'
            f'<td class="num">{n(o.get("students_employed"))}</td></tr>')

    j1 = next((v for k, v in j1_states if k == name), None)
    j1_line = (
        f'<p class="note"><strong>J-1 physicians.</strong> {E(name)} hosted '
        f'<strong>{n(j1)}</strong> J-1 physicians in graduate medical education '
        f'in {j1_year}. That list is published for the top twelve states only, '
        f'so a state missing from it has no published figure.</p>'
        if j1 else
        f'<p class="note"><strong>J-1 physicians.</strong> {E(name)} is not in '
        f'the published top twelve states for J-1 physicians in graduate '
        f'medical education, which is the only state breakdown ECFMG '
        f'publishes. That is an absence from a short list, not a zero.</p>')

    if opt_rows:
        opt_html = f"""
  <section class="block" id="training">
    <h2>Practical training, and the other student visas</h2>
    <p class="lede">A student visa does not end at graduation. Optional
    Practical Training lets a graduate work on the same visa, and a STEM degree
    adds a further twenty-four months. It applies at both levels &mdash; a
    foreign undergraduate can take OPT as readily as a doctoral graduate
    &mdash; which is why the undergraduate share above is not the end of the
    story.</p>
    <div class="table-wrap"><table class="t" data-sortable>
      <thead><tr><th>Institution</th><th class="num">OPT authorisations</th>
        <th class="num">National rank</th>
        <th class="num">STEM OPT authorisations</th><th class="num">National rank</th>
        <th class="num">Students employed</th></tr></thead>
      <tbody>{opt_rows}</tbody></table></div>
    <p class="note"><strong>Do not add these two columns together.</strong> A
    graduate who holds post-completion OPT and then a STEM extension in the
    same year appears in both, and the sum counts that person twice. They are
    authorisations, not people. Figures are for {opt_year}, from SEVP&rsquo;s
    top-100 and top-200 school lists &mdash; an institution outside those lists
    has no published figure, which is a fact about the list and never a zero.</p>
    {j1_line}
  </section>
"""
    else:
        opt_html = f"""
  <section class="block" id="training">
    <h2>Practical training, and the other student visas</h2>
    <p class="lede">A student visa does not end at graduation. Optional
    Practical Training lets a graduate work on the same visa, and a STEM degree
    adds a further twenty-four months. It applies at both levels, so the
    undergraduate share above is not the end of the story.</p>
    <p class="lede"><strong>No institution in {E(name)} appears in
    SEVP&rsquo;s published lists</strong>, which cover the top 100 and top 200
    schools for OPT and STEM OPT. There is therefore no published practical
    training figure for this state. That is a fact about what the agency
    releases, not a statement that no one here is on OPT.</p>
    {j1_line}
  </section>
"""

    # IN-STATE AGAINST OUT-OF-STATE, in students and in dollars.
    #
    # OUT-OF-STATE IS NOT FOREIGN. SHEEO's own note is explicit: out-of-state
    # FTE "includes international students and students that do not meet
    # residency requirements", so a student from the next state and a student
    # from Shanghai sit in the same column. This section is about the PRICE a
    # non-resident pays and the SHARE of revenue non-residents carry. It is
    # never a count of foreign students, and the page says so where it is read.
    res_html = ""
    rec_res = residency.get(abbr)
    if rec_res:
        yr = rec_res["latest_year"]
        cur = rec_res["years"].get(yr, {})
        ins = cur.get("in_state_net_tuition_per_fte")
        oos = cur.get("out_of_state_net_tuition_per_fte")
        fte_in = cur.get("in_state_fte_share")
        fte_out = cur.get("out_of_state_fte_share")
        rev_out = cur.get("out_of_state_revenue_share")
        mult = rec_res.get("premium_multiple")
        warn = []
        if cur.get("fte_missing"):
            warn.append("could not provide a complete enrolment breakout")
        if cur.get("tuition_missing"):
            warn.append("could not provide a complete tuition breakout")
        if cur.get("fte_estimated") or cur.get("tuition_estimated"):
            warn.append("estimated part of this breakout")
        rows = ""
        if fte_in is not None and fte_out is not None:
            rows += (f'<tr><td>Share of students (FTE)</td>'
                     f'<td class="num">{round(fte_in * 100, 1)}%</td>'
                     f'<td class="num">{round(fte_out * 100, 1)}%</td></tr>')
        if ins and oos:
            rows += (f'<tr><td>Net tuition and fees collected per student</td>'
                     f'<td class="num">${ins:,.0f}</td>'
                     f'<td class="num share">${oos:,.0f}</td></tr>')
        if cur.get("in_state_revenue_share") is not None and rev_out is not None:
            rows += (f'<tr><td>Share of tuition revenue</td>'
                     f'<td class="num">{round(cur["in_state_revenue_share"] * 100, 1)}%</td>'
                     f'<td class="num share">{round(rev_out * 100, 1)}%</td></tr>')
        headline = ""
        if mult and fte_out is not None and rev_out is not None:
            headline = (
                f'<p class="lede">An out-of-state student in {E(name)} is worth '
                f'<strong>{mult}&times;</strong> an in-state one to the '
                f'institution. They are <strong>{round(fte_out * 100, 1)}%</strong> '
                f'of the students and <strong>{round(rev_out * 100, 1)}%</strong> '
                f'of the tuition revenue.</p>')
        elif mult:
            headline = (f'<p class="lede">An out-of-state student in {E(name)} '
                        f'is worth <strong>{mult}&times;</strong> an in-state '
                        f'one to the institution.</p>')
        if rows:
            res_html = f"""
  <section class="block" id="residency">
    <h2>In-state against out-of-state</h2>
    <p class="lede">Public four-year institutions, FY{yr}. Every foreign
    student pays the out-of-state rate, so this is the price attached to the
    non-resident column everywhere else on this page.</p>
    {headline}
    <div class="table-wrap"><table class="t">
      <thead><tr><th>Measure</th><th class="num">In-state</th>
        <th class="num">Out-of-state</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    <p class="note"><strong>Out-of-state is not the same as foreign.</strong>
    SHEEO counts international students and domestic students from other states
    in one column. This shows what a non-resident pays, never how many of them
    are foreign. Figures are <strong>net</strong> tuition and fee revenue per
    full-time-equivalent student &mdash; what the institution actually
    collected after its own aid, not the published price. Public four-year
    institutions only; medical FTE excluded.
    {'SHEEO records that ' + E(name) + ' ' + ' and '.join(warn) + ' for this year.' if warn else ''}</p>
  </section>
"""

    title = f"{name}: who the graduate programmes are for"
    desc = (f"Every degree-granting institution in {name}, the research "
            f"doctorates each awards, how many go to non-residents, and the "
            f"federal research money that arrives. Built from IPEDS, NSF and "
            f"NCSES.")

    out = [head(title, desc,
                f' data-state-name="{E(name)}" data-state-abbr="{E(abbr)}"')]
    out.append(f"""
  <div class="page-head">
    <p class="kicker">State profile &middot; {E(abbr)}</p>
    <h1 id="{abbr.lower()}-graduate-programmes">{E(name)}</h1>
    <p>{E(name)} has <strong>{n(rec['institutions'])}</strong> degree-granting
    institutions in this data. Between them they award
    <strong>{n(rec['doctorates_awarded'])}</strong> research doctorates and
    <strong>{n(rec['masters_awarded'])}</strong> master&rsquo;s degrees over the
    window, and take <strong>{money(rec['federal_rd'])}</strong> in federal
    research and development money.</p>
    <p>This page counts every institution in the state, including the ones that
    award no graduate degree at all. Leaving those out would make a state look
    like its flagship.</p>
  </div>

  <div class="stats">
    <div class="stat"><div class="n">{n(rec['institutions'])}</div>
      <p class="l">institutions in the state</p>
      <p class="s">{n(len(with_doc))} award a research doctorate.
        {n(len(none_grad))} enrol no graduate students at all.</p></div>
    <div class="stat"><div class="n">{str(doc_share) + '%' if doc_share is not None else 'n/a'}</div>
      <p class="l">of research doctorates go to
        <span data-term="nra">non-residents</span></p>
      <p class="s">{n(rec['doctorates_non_resident'])} of
        {n(rec['doctorates_awarded'])}. National figure: {nat_share}%.</p></div>
    <div class="stat"><div class="n">{rec.get('graduate_non_resident_share', 0)}%</div>
      <p class="l">of graduate enrolment is non-resident</p>
      <p class="s">{n(rec['graduate_non_resident'])} of
        {n(rec['graduate_enrolment'])} graduate students.</p></div>
    <div class="stat"><div class="n">{money(rec['federal_rd'])}</div>
      <p class="l">federal research and development money</p>
      <p class="s">Across {n(rec['institutions_with_federal'])} institutions.
        {money(rec['federal_obligations'])} in total federal obligations.</p></div>
  </div>

  <section class="block" id="against-the-country">
    <h2>Where {E(name)} sits</h2>
    <p class="lede">The non-resident share of research doctorates, against the
    same figure for the country. {comparison(doc_share, nat_share)}</p>
    <div class="barpair">
      <div class="row"><span class="lab">{E(name)}</span>
        <span class="track"><span class="fill" style="width:{min(100, (doc_share or 0) / max(nat_share, doc_share or 0, 1) * 100):.1f}%"></span></span>
        <span class="v">{str(doc_share) + '%' if doc_share is not None else 'n/a'}</span></div>
      <div class="row"><span class="lab">United States</span>
        <span class="track"><span class="fill nat" style="width:{min(100, nat_share / max(nat_share, doc_share or 0, 1) * 100):.1f}%"></span></span>
        <span class="v">{nat_share}%</span></div>
    </div>
    <p class="note">{E(name)} ranks <strong>{r_share}</strong> of {n_share}
    states on that share, and <strong>{r_count}</strong> of {n_count} on the
    number of research doctorates it awards. Rank 1 is the highest. Only states
    that award doctorates are ranked.</p>
  </section>

  {levels_html}

  {blend_html}

  {opt_html}

  {res_html}

  <section class="block" id="institutions">
    <h2>Every institution</h2>
    <p class="lede">Largest first by total enrolment. A dash means the
    institution awards none of that degree, or that no federal research money
    was matched to it.</p>
    <div class="table-wrap"><table class="t" data-sortable>
      <thead><tr><th>Institution</th><th>City</th><th>Control</th>
        <th class="num">Enrolled</th><th class="num">Graduate</th>
        <th class="num">Master&rsquo;s</th><th class="num">Non-res</th>
        <th class="num">Doctorates</th><th class="num">Non-res</th>
        <th class="num">Federal R&amp;D</th></tr></thead>
      <tbody>""")

    for r in insts:
        ma, mn = g(r, "masters", "awarded"), g(r, "masters", "non_resident")
        dc, dn = (g(r, "all_research_doctorates", "awarded"),
                  g(r, "all_research_doctorates", "non_resident"))
        fed = g(r, "federal", "rd_total")
        dash = '<td class="num muted" data-sort="-1">&mdash;</td>'
        out.append(
            f'<tr><td>{E(r["institution"])}</td><td class="muted">{E(r.get("city") or "")}</td>'
            f'<td class="muted">{E(r.get("control") or "")}</td>'
            f'<td class="num" data-sort="{g(r, "total_enrolment", "total")}">'
            f'{n(g(r, "total_enrolment", "total"))}</td>'
            f'<td class="num" data-sort="{g(r, "graduate_enrolment", "total") or -1}">'
            f'{n(g(r, "graduate_enrolment", "total")) if g(r, "graduate_enrolment", "total") else "&mdash;"}</td>'
            + (f'<td class="num">{n(ma)}</td><td class="num share">{n(mn)}</td>' if ma else dash + dash)
            + (f'<td class="num">{n(dc)}</td><td class="num share">{n(dn)}</td>' if dc else dash + dash)
            + (f'<td class="num" data-sort="{int(fed)}">{money(fed)}</td>'
               if fed else dash)
            + "</tr>")

    out.append(f"""</tbody></table></div>
    <p class="note">Degrees are pooled over
    {prof['windows']['late'][0]}&ndash;{prof['windows']['late'][1]}. Enrolment
    and federal money are the most recent year in the file. &ldquo;Non-res&rdquo;
    means a student here on a temporary visa, almost always F-1 or J-1. A green
    card holder is not counted in it.</p>
  </section>

  <section class="block" id="concentration">
    <h2>How few institutions this is</h2>
    <p class="lede">Of the {n(rec['institutions'])} institutions in
    {E(name)}, <strong>{n(len(with_doc))}</strong> award a research doctorate at
    all{', and the largest two award ' + str(top2_share) + '% of them' if top2_share is not None and len(with_doc) > 1 else ''}.
    A state&rsquo;s graduate pipeline is a much smaller thing than its list of
    colleges.</p>
    <div class="table-wrap"><table class="t" data-sortable>
      <thead><tr><th>Institution</th><th class="num">Research doctorates</th>
        <th class="num">Non-resident</th><th class="num share-col">Share</th>
        <th class="num">Share of the state&rsquo;s doctorates</th></tr></thead>
      <tbody>""")
    for r in with_doc:
        dc = g(r, "all_research_doctorates", "awarded")
        dn = g(r, "all_research_doctorates", "non_resident")
        out.append(
            f'<tr><td>{E(r["institution"])}</td><td class="num">{n(dc)}</td>'
            f'<td class="num">{n(dn)}</td>'
            f'<td class="num share">{pct(dn, dc)}%</td>'
            f'<td class="num muted">{pct(dc, total_doc)}%</td></tr>')
    out.append("""</tbody></table></div>
  </section>""")

    # The NSF survey reaches only a few institutions per state; where it does,
    # the highest foreign share is worth naming, because it is usually not the
    # flagship.
    gss = [r for r in insts if isinstance(r.get("gss_foreign_share"), dict)]
    if gss:
        def doctoral(r):
            return r["gss_foreign_share"].get("doctoral") or 0
        top = max(gss, key=doctoral)
        rows = "".join(
            f'<tr><td>{E(r["institution"])}</td>'
            f'<td class="num share">{r["gss_foreign_share"].get("doctoral", "&mdash;")}%</td>'
            f'<td class="num">{r["gss_foreign_share"].get("master’s", r["gss_foreign_share"].get("master\'s", "&mdash;"))}%</td></tr>'
            for r in sorted(gss, key=doctoral, reverse=True))
        out.append(f"""
  <section class="block" id="survey">
    <h2>The foreign share of graduate students, where the survey reaches</h2>
    <p class="lede">The NSF Survey of Graduate Students and Postdoctorates asks
    institutions directly, and it covers {n(len(gss))} of the
    {n(rec['institutions'])} institutions in {E(name)}. It is a different
    measure from the degree counts above: enrolled students rather than degrees
    awarded.</p>
    <div class="table-wrap"><table class="t" data-sortable>
      <thead><tr><th>Institution</th><th class="num">Doctoral students foreign</th>
        <th class="num">Master&rsquo;s students foreign</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    <div class="callout">
      <h3>{E(top["institution"])}</h3>
      <p>The highest foreign share of doctoral students in the state, at
      <strong>{doctoral(top)}%</strong>. It is not the largest institution here
      and it is not the one with the most federal money. Size and share are
      different questions, and a state page that ranked only by size would not
      show this.</p>
    </div>
  </section>""")

    if sheeo:
        out.append(f"""
  <section class="block" id="state-money">
    <h2>What the state itself puts in</h2>
    <p class="lede">State appropriations per full-time-equivalent student, from
    the SHEEO finance survey, against the change in the foreign share of
    graduate enrolment over the same window.</p>
    <div class="table-wrap"><table class="t" data-sortable>
      <thead><tr><th>Measure</th><th class="num">First year</th>
        <th class="num">Last year</th><th class="num">Change</th></tr></thead>
      <tbody>
        <tr><td>State appropriations per FTE student</td>
          <td class="num">${sheeo['appropriations_per_fte_first']:,.0f}</td>
          <td class="num">${sheeo['appropriations_per_fte_last']:,.0f}</td>
          <td class="num share">{sheeo['appropriations_change_pct']:+}%</td></tr>
        <tr><td>Foreign share of graduate enrolment</td>
          <td class="num">{sheeo['foreign_share_first']}%</td>
          <td class="num">{sheeo['foreign_share_last']}%</td>
          <td class="num share">{sheeo['foreign_share_change_pts']:+} pts</td></tr>
      </tbody></table></div>
    <p class="note">These two rows move for their own reasons. Nothing here
    shows that one caused the other, and the page does not say it did.</p>
  </section>""")

    if corpus:
        rows = ""
        for u in corpus:
            depts = "".join(
                f'<tr><td class="muted">{E(u["institution"])}</td>'
                f'<td>{E(dp["title"])}</td><td class="num">{n(dp["total"])}</td>'
                f'<td class="num">{n(dp["nra"])}</td>'
                f'<td class="num share">{dp["share"]}%</td></tr>'
                for dp in sorted(u.get("depts", []),
                                 key=lambda x: -x["share"]))
            rows += depts
        majority = sum(u.get("majority_non_resident", 0) for u in corpus)
        out.append(f"""
  <section class="block" id="departments">
    <h2>Department by department</h2>
    <p class="lede">The dissertation corpus reaches
    {n(len(corpus))} institution{'s' if len(corpus) != 1 else ''} in this state,
    covering {n(sum(u.get('departments', 0) for u in corpus))} departments.
    {'<strong>' + str(majority) + '</strong> of them are majority non-resident.'
     if majority else 'None of them is majority non-resident.'}</p>
    <div class="table-wrap"><table class="t" data-sortable>
      <thead><tr><th>Institution</th><th>Department</th>
        <th class="num">Doctorates</th><th class="num">Non-resident</th>
        <th class="num share-col">Share</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    <p class="note">From the dissertation corpus, which is built from what
    universities publish about their own graduates. It covers the institutions
    on this site, not every institution in the state, so it is a floor.</p>
  </section>""")

    out.append(notpub_html)
    out.append(f"""
  <section class="block" id="method">
    <h2>Method and limits</h2>
    <ul class="lede">
      <li><strong>Non-resident means here on a temporary visa.</strong> IPEDS
      defines it as a person &ldquo;who is not a citizen or national of the
      United States and who is in this country on a visa or temporary basis and
      does not have the right to remain indefinitely.&rdquo; A green card holder
      is therefore never counted here. Neither is a refugee or an asylee. Those
      students are reported in the race and ethnicity categories alongside
      citizens. For students the category is overwhelmingly F-1 and J-1.</li>
      <li><strong>It is not ethnicity and not country of origin.</strong> A
      US-born citizen of any background is never non-resident. The status is
      recorded when the student enrols, for the enrolment figures, and when the
      degree is awarded, for the degree counts. These files cannot be split any
      other way.</li>
      <li><strong>Degrees are pooled</strong> over
      {prof['windows']['late'][0]}&ndash;{prof['windows']['late'][1]}, because a
      single year at a small institution moves on one student.</li>
      <li><strong>Enrolment and awards are different measures</strong> and will
      not agree. One counts people on a given day; the other counts degrees
      conferred over five years.</li>
      <li><strong>Federal money is matched to a campus</strong>, and a system
      that reports centrally can carry money its branches spend.</li>
      <li><strong>This page shows composition, not displacement.</strong> It
      records who received the degrees. It does not show that anyone was kept
      out, and nothing here should be read that way.</li>
    </ul>
    <p class="note">Built by <code>scripts/build_state_pages.py</code> from
    <a href="/data/institution_profiles.json">institution_profiles.json</a>,
    <a href="/data/state_funding_and_enrolment.json">state_funding_and_enrolment.json</a>
    and <a href="/data/university_distribution.json">university_distribution.json</a>.
    Compare the country on <a href="/overview">the national overview</a>.</p>
  </section>

</div>
</main>
<script src="/analytics-beacon.js" defer></script>\n<script src="/states.js" defer></script>\n<script src="/anchors.js" defer></script>
<script src="/sidebar.js"></script>
</body>
</html>
""")
    return "".join(out)



def index(abbrs: list[str], prof: dict) -> str:
    """The hub at /states.

    One navigation entry, however many states are published. Without it every
    new state would need a sidebar edit, and fifty sidebar edits is fifty
    chances to publish a page nothing links to -- the failure this repo has
    already had twice.
    """
    states = prof["states"]
    nat_doc = sum(s["doctorates_awarded"] for s in states)
    nat_nra = sum(s["doctorates_non_resident"] for s in states)
    nat = round(100 * nat_nra / nat_doc, 1) if nat_doc else 0.0
    have = [s for s in states if s.get("doctorates_non_resident_share") is not None]
    have.sort(key=lambda s: -s["doctorates_non_resident_share"])
    rank = {s["state"]: i + 1 for i, s in enumerate(have)}

    rows = ""
    for abbr in sorted(abbrs, key=lambda a: NAMES.get(a, a)):
        rec = next(s for s in states if s["state"] == abbr)
        sh = rec.get("doctorates_non_resident_share")
        rows += (
            f'<tr><td data-sort="{E(NAMES.get(abbr, abbr).lower())}">'
            f'<a href="/states/{abbr.lower()}">{E(NAMES.get(abbr, abbr))}</a></td>'
            f'<td class="num" data-sort="{rec["institutions"]}">{n(rec["institutions"])}</td>'
            f'<td class="num" data-sort="{rec["doctorates_awarded"]}">{n(rec["doctorates_awarded"])}</td>'
            f'<td class="num share" data-sort="{sh if sh is not None else -1}">'
            f'{str(sh) + "%" if sh is not None else "n/a"}</td>'
            f'<td class="num muted" data-sort="{rank.get(abbr, 999)}">'
            f'{rank.get(abbr, "&mdash;")} of {len(have)}</td>'
            f'<td class="num" data-sort="{rec["federal_rd"]}">{money(rec["federal_rd"])}</td></tr>')

    title = "The states"
    desc = ("Per-state profiles: every degree-granting institution, the research "
            "doctorates it awards, how many go to non-residents, and the federal "
            "research money that arrives.")
    return head(title, desc) + f"""
  <div class="page-head">
    <p class="kicker">State profiles</p>
    <h1 id="the-states">The states</h1>
    <p>One page per state, built from the same national files as the rest of
    this site. Each counts every degree-granting institution in the state,
    including the ones awarding no graduate degree at all.</p>
    <p><strong>{n(len(abbrs))}</strong> of {len(have)} states are published so
    far. The national non-resident share of research doctorates is
    <strong>{nat}%</strong>; rank 1 is the highest.</p>
  </div>

  <section class="block" id="published">
    <h2>Published so far</h2>
    <p class="note" style="margin:0 0 .4rem">Click any column heading to sort.
    Click it again to reverse.</p>
    <div class="table-wrap"><table class="t" data-sortable>
      <thead><tr><th>State</th><th class="num">Institutions</th>
        <th class="num">Research doctorates</th>
        <th class="num share-col">Non-resident share</th><th class="num">Rank</th>
        <th class="num">Federal R&amp;D</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    <p class="note">Degrees pooled over
    {prof['windows']['late'][0]}&ndash;{prof['windows']['late'][1]}. A state
    page is published when someone decides to publish it, not as a side effect
    of a rebuild, so this list grows deliberately.</p>
  </section>

  <section class="block" id="reading">
    <h2>Reading these pages</h2>
    <ul class="lede">
      <li><strong>A state average is a weighted average.</strong> In several
      states one very large institution decides it. Every state page shows what
      its figure is made of, and recomputes it without the largest institution.</li>
      <li><strong>Enrolment and degrees are different measures</strong> and
      will not agree. One counts people on a day; the other counts degrees over
      five years.</li>
      <li><strong>Non-resident means here on a temporary visa</strong>,
      almost always F-1 or J-1. A green card holder is never counted in it, and
      nor is a refugee or an asylee. It is not ethnicity and not country of
      origin.</li>
      <li><strong>Composition, not displacement.</strong> These pages record
      who received the degrees. They do not show that anyone was kept out.</li>
    </ul>
  </section>

</div>
</main>
<script src="/states.js" defer></script>
<script src="/analytics-beacon.js" defer></script>\n<script src="/states.js" defer></script>\n<script src="/anchors.js" defer></script>
<script src="/sidebar.js"></script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="every state with data")
    ap.add_argument("--state", action="append", default=[],
                    help="a two-letter abbreviation; repeatable")
    args = ap.parse_args()

    prof = json.loads(PROFILES.read_text())
    sheeo_rows = {s["abbr"]: s for s in json.loads(SHEEO.read_text())["states"]
                  if s.get("abbr")}
    corpus_all = json.loads(CORPUS.read_text())
    corpus_rows = (list(corpus_all.values()) if isinstance(corpus_all, dict)
                   else corpus_all)
    by_unitid = {str(r.get("unitid")): r for r in prof["institutions"]}

    # OPT is keyed by this site's own short names, so it is joined to a state
    # through the corpus file's UNITID. Two keys ("cuny", "osu") name a system
    # or are ambiguous between universities in different states; they are left
    # unmapped and reported, because guessing which Ohio/Oregon/Oklahoma State
    # was meant would attach real numbers to the wrong state.
    opt_raw = json.loads(OPT.read_text()) if OPT.exists() else {}
    corpus_by_key = {u["key"]: u for u in corpus_rows
                     if isinstance(u, dict) and u.get("key")}
    opt_by_unitid, unmapped = {}, []
    for key, entry in opt_raw.items():
        u = corpus_by_key.get(key)
        if u and str(u.get("unitid")) in by_unitid:
            opt_by_unitid[str(u["unitid"])] = entry
        else:
            unmapped.append(key)
    if unmapped:
        print(f"  note: {len(unmapped)} OPT key(s) not mapped to a state "
              f"({', '.join(sorted(unmapped))}); left out rather than guessed")

    residency = (json.loads(RESIDENCY.read_text()).get("states", {})
                 if RESIDENCY.exists() else {})
    funding = (json.loads(FUNDING.read_text()).get("institutions", {})
               if FUNDING.exists() else {})
    med = json.loads(MEDICAL.read_text()) if MEDICAL.exists() else {}
    j1_states = (med.get("evsp_j1") or {}).get("top_states_2025") or []
    j1_year = str((med.get("evsp_j1") or {}).get("as_of") or "")[:4] or "2025"

    if args.all:
        wanted = [s["state"] for s in prof["states"] if s.get("institutions")]
    elif args.state:
        wanted = [a.upper() for a in args.state]
    else:
        wanted = list(PUBLISH)

    known = {s["state"] for s in prof["states"]}
    missing = [a for a in wanted if a not in known]
    if missing:
        raise SystemExit(f"FAIL: no data for {', '.join(missing)}. "
                         f"Nothing written.")

    SUBDIR.mkdir(parents=True, exist_ok=True)
    for abbr in wanted:
        # The corpus keys on its own institution names, so it is joined on
        # UNITID. Joining on a name would silently drop "The University of
        # Montana" against "U Montana", and a failed join that reads as an
        # empty section is worse than a crash.
        mine = [u for u in corpus_rows
                if isinstance(u, dict)
                and by_unitid.get(str(u.get("unitid")), {}).get("state") == abbr]
        write_text(SUBDIR / f"{abbr.lower()}.html",
                   page(abbr, prof, sheeo_rows.get(abbr), mine,
                        opt_by_unitid, j1_states, j1_year, residency,
                        funding))
        rec = next(s for s in prof["states"] if s["state"] == abbr)
        print(f"  /states/{abbr.lower()}.html  {NAMES.get(abbr, abbr):<22}"
              f"{rec['institutions']:>3} institutions, "
              f"{rec['doctorates_awarded']:>6} doctorates, "
              f"{rec.get('doctorates_non_resident_share')}% non-resident, "
              f"{len(mine)} in the corpus")
    # The hub always lists the DECLARED set, not whatever was built this run,
    # so a one-state rebuild cannot quietly shrink the index.
    write_text(SITE / "states.html", index(list(PUBLISH), prof))
    print(f"  /states.html         hub, {len(PUBLISH)} state(s) listed")
    print(f"Wrote {len(wanted)} state page(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
