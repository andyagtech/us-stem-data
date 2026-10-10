#!/usr/bin/env python3
"""Render the press-conference walkthrough.

The video is embedded once and stays put while the transcript scrolls
beside it; clicking a moment seeks the player to that second. Nothing is
sent to YouTube until the reader presses play, because an autoplaying
embed on a page about federal data is a nuisance and a privacy leak.

EVERY FIGURE RESOLVES OR THE BUILD FAILS. A page whose whole purpose is
checking someone else's numbers cannot carry an unresolved one of its own.

Usage:
  python3 scripts/build_press_conference.py
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402
from press_conference import (MOMENTS, VIDEO_ID, SOURCE_URL,   # noqa: E402
                              TITLE, PUBLISHER, DATE)

DATA = ROOT / "site" / "data"
OUT = ROOT / "site" / "press-conference.html"
E = html.escape


class MissingFigure(RuntimeError):
    pass


def resolve(stem: str, path: str):
    f = DATA / f"{stem}.json"
    if not f.exists():
        raise MissingFigure(f"{stem}.json does not exist")
    cur = json.loads(f.read_text())
    #: A dotted path where a step may carry a [key=value] selector:
    #:     industries[slug=petroleum].levels[level=Doctorate].share
    #: NAME THE ROW, NEVER ITS POSITION. These lists are ordered by volume,
    #: so industries.0 is petroleum today and something else after a
    #: rebuild, and this page would cite the wrong industry while every
    #: check still passed.
    for part in re.findall(r"[^.\[]+(?:\[[^\]]+\])?", path):
        m = re.fullmatch(r"([^\[]+)\[([^=]+)=([^\]]+)\]", part)
        if m:
            key, field, want = m.group(1), m.group(2), m.group(3)
            if not isinstance(cur, dict) or key not in cur:
                raise MissingFigure(f"{stem}.{path}: no {key!r}")
            rows = cur[key]
            if not isinstance(rows, list):
                raise MissingFigure(f"{stem}.{path}: {key!r} is not a list")
            hit = [r for r in rows
                   if isinstance(r, dict) and str(r.get(field)) == want]
            if len(hit) != 1:
                raise MissingFigure(
                    f"{stem}.{path}: {field}={want!r} matched {len(hit)} rows")
            cur = hit[0]
            continue
        if isinstance(cur, dict):
            if part not in cur:
                raise MissingFigure(f"{stem}.{path}: stopped at {part!r}")
            cur = cur[part]
            continue
        raise MissingFigure(f"{stem}.{path}: cannot descend into {part!r}")
    return cur


def fmt(v, how: str) -> str:
    if how == "n":
        return f"{int(v):,}"
    if how == "pct1":
        return f"{float(v):.1f}%"
    if how == "usd":
        return f"${float(v):,.0f}"
    return str(v)


def clock(t: int) -> str:
    return f"{t // 60}:{t % 60:02d}"




# ---------------------------------------------------------------- charts
# Inline SVG, no library. These sit inside a <details>, so the markup is in
# the page from the first byte and a reader with no JavaScript still gets
# the numbers; opening the panel costs nothing and loads nothing.

def bar_chart(rows, *, value_key="v", label_key="k", suffix="%",
              highlight=None, width=620, rowh=26) -> str:
    """Horizontal bars. rows: [{k, v}], already in the order to display."""
    if not rows:
        return ""
    top = max(r[value_key] for r in rows) or 1
    labw, numw, gap = 220, 56, 10
    plot = width - labw - numw - gap * 2
    h = len(rows) * rowh + 8
    out = [f'<svg class="chart" viewBox="0 0 {width} {h}" role="img" '
           f'preserveAspectRatio="xMinYMin meet">']
    for i, r in enumerate(rows):
        y = i * rowh + 4
        w = max(2, r[value_key] / top * plot)
        hot = highlight and highlight(r)
        cls = "bar hot" if hot else "bar"
        lab = str(r[label_key])
        lab = lab if len(lab) <= 34 else lab[:33] + "\u2026"
        out.append(
            f'<text class="lab" x="{labw}" y="{y + rowh * 0.66}" '
            f'text-anchor="end">{E(lab)}</text>'
            f'<rect class="{cls}" x="{labw + gap}" y="{y + 4}" '
            f'width="{w:.1f}" height="{rowh - 11}" rx="2"/>'
            f'<text class="val{" hot" if hot else ""}" '
            f'x="{labw + gap + w + 6}" y="{y + rowh * 0.66}">'
            f'{r[value_key]:,.1f}{suffix}</text>'
            if isinstance(r[value_key], float) else
            f'<text class="lab" x="{labw}" y="{y + rowh * 0.66}" '
            f'text-anchor="end">{E(lab)}</text>'
            f'<rect class="{cls}" x="{labw + gap}" y="{y + 4}" '
            f'width="{w:.1f}" height="{rowh - 11}" rx="2"/>'
            f'<text class="val{" hot" if hot else ""}" '
            f'x="{labw + gap + w + 6}" y="{y + rowh * 0.66}">'
            f'{r[value_key]:,}{suffix}</text>')
    out.append("</svg>")
    return "".join(out)


def panel(title: str, body: str, *, open_by_default=False) -> str:
    """A collapsible chart. Closed by default: the prose carries the point
    and the chart is for the reader who wants to see the shape."""
    op = " open" if open_by_default else ""
    return (f'<details class="panel"{op}><summary>{E(title)}</summary>'
            f'<div class="panel-body">{body}</div></details>')

def charts_for(moment_t: int) -> str:
    """The chart that belongs beside a given moment, if any."""
    pd = json.loads((DATA / "postdoc_citizenship.json").read_text())
    bs = json.loads((DATA / "visa_bodyshops.json").read_text())
    pe = json.loads((DATA / "public_employer_perm.json").read_text())

    if moment_t == 411:          # the nine universities
        rows = sorted(pd["named_institutions"]["institutions"],
                      key=lambda r: -r["share"])
        return panel(
            "Each of the nine, by share of postdocs on a temporary visa",
            bar_chart([{"k": r["named_as"], "v": r["share"]} for r in rows],
                      highlight=lambda r: r["v"] >= 65)
            + '<p class="cap">Combined they are '
            + f'{pd["named_institutions"]["share"]}%. Every one of the nine '
            + 'is above half.</p>')

    if moment_t == 434:          # the postdoc share
        d = pd["distribution"]
        rows = [{"k": f'{h["from"]}\u2013{h["to"]}%', "v": h["institutions"]}
                for h in d["histogram"]]
        return panel(
            "Where every institution falls, not just the nine",
            bar_chart(rows, suffix="", highlight=lambda r: "7" == r["k"][0]
                      or "8" == r["k"][0] or "9" == r["k"][0])
            + f'<p class="cap">{d["institutions"]} institutions reporting at '
              f'least {d["floor"]} postdocs. The bars right of 70% are the '
              f'ones no announcement has named.</p>')

    if moment_t == 322:          # the staffing firms
        lv = bs["national"]["levels"]
        order = ["I", "II", "III", "IV"]
        rows = [{"k": f"Level {k}", "v": lv[k]} for k in order if k in lv]
        return panel(
            "Certified filings by statutory wage level, nationally",
            bar_chart(rows, suffix="",
                      highlight=lambda r: r["k"] in ("Level I", "Level II"))
            + f'<p class="cap">Levels I and II are the two lowest the '
              f'statute defines. They carry '
              f'{bs["national"]["low_level_pct"]}% of all certified '
              f'filings.</p>')

    if moment_t == 656:          # the suspensions
        d = bs["threshold_distribution"]["dependent_pct"]
        rows = [{"k": k if k != "100" else "100%", "v": v}
                for k, v in d.items()]
        return panel(
            "Employers by share of their workforce that is H-1B dependent",
            bar_chart(rows, suffix="",
                      highlight=lambda r: r["k"] in ("90-99", "100%"))
            + f'<p class="cap">{d.get("100", 0):,} employers report a '
              f'workforce that is entirely H-1B dependent, and '
              f'{d.get("90-99", 0):,} more are above nine tenths. The '
              f'distribution is bimodal: most employers barely use the '
              f'program, and a cluster runs on almost nothing else.</p>')

    if moment_t == 141:          # PERM, the step this site can see
        sec = pe["sectors"]
        rows = sorted(
            [{"k": k.replace("_", " ").title(), "v": v["filings"]}
             for k, v in sec.items()],
            key=lambda r: -r["v"])
        return panel(
            "Public-employer permanent-residence filings by sector",
            bar_chart(rows, suffix="")
            + '<p class="cap">Certified PERM filings, FY2013\u2013FY2024. '
              'This is the only federal disclosure file that records the '
              'worker\u2019s citizenship.</p>')
    return ""


def distributions() -> str:
    """The shape behind the headline shares.

    A mean is the one statistic that cannot show an outlier, and every
    figure quoted from a podium is a mean. This section ships the
    distribution beside it, because at most institutions the share is
    HIGHER than the national average: the big universities pull the
    weighted mean down, so the typical institution is worse than the
    headline number suggests.
    """
    d = json.loads((DATA / "postdoc_citizenship.json").read_text())
    dist, nat = d["distribution"], d["national"]
    nine = d["named_institutions"]
    pc = dist["percentiles"]
    peak = max(h["institutions"] for h in dist["histogram"]) or 1

    bars = []
    for h in dist["histogram"]:
        w = h["institutions"] / peak * 100
        hot = " hot" if h["from"] >= 70 else ""
        bars.append(
            f'<div class="hrow"><span class="hb">{h["from"]}\u2013{h["to"]}%</span>'
            f'<span class="ht"><span class="hf{hot}" style="width:{w:.1f}%"></span></span>'
            f'<span class="hn">{h["institutions"]}</span></div>')

    out = []
    for r in dist["outliers"][:8]:
        out.append(f'<tr><td>{E(r["institution"])}</td>'
                   f'<td class="num">{r["postdocs"]:,}</td>'
                   f'<td class="num">{r["foreign"]:,}</td>'
                   f'<td class="num hi">{r["share"]}%</td></tr>')

    return f"""
<section class="mo dist" id="distributions">
  <div class="mo-head"><span class="who">Context</span>
    <span class="vd ok">Federal data on this</span></div>
  <h2>What the averages hide</h2>
  <p class="note">Every share quoted from a podium is an average, and an
  average is the one statistic that cannot show an outlier. The national
  postdoc figure is {nat['share']}%. The <strong>median institution</strong>
  is {pc['median']}% &mdash; higher &mdash; because the largest universities
  pull the weighted average down. At the typical American institution the
  position is worse than the national number suggests.</p>

  <ul class="ev">
    <li><span class="v">{dist['majority_foreign']}</span><span class="l">of
      {dist['institutions']} institutions have a MAJORITY of postdocs on a
      temporary visa, covering
      {dist['majority_foreign_postdocs']:,} posts</span></li>
    <li><span class="v">{dist['above_national']}</span><span class="l">sit
      above the national average of {nat['share']}%</span></li>
    <li><span class="v">{dist['at_or_above_80']}</span><span class="l">are at
      80% or higher</span></li>
    <li><span class="v">{dist['max']}%</span><span class="l">the highest
      single institution; the lowest is {dist['min']}%</span></li>
  </ul>

  <h3>Institutions by share of postdocs on a temporary visa</h3>
  <div class="hist">{''.join(bars)}</div>
  <p class="cap">Each bar is a count of institutions. The nine named sit at
  {nine['share']}% combined, inside the main body of this distribution
  rather than at its edge &mdash; which is the point: they are not unusual.
  The unusual institutions are further right.</p>

  <h3>Where the distribution runs out</h3>
  <div class="table-wrap">
  <table class="t">
  <thead><tr><th>Institution</th><th class="num">Postdocs</th>
  <th class="num">Temporary visa</th><th class="num">Share</th></tr></thead>
  <tbody>{''.join(out)}</tbody></table>
  </div>
  <p class="cap">Percentiles across the {dist['institutions']} institutions
  reporting at least {dist['floor']} postdocs:
  10th {pc['p10']}% &middot; 25th {pc['p25']}% &middot; median
  {pc['median']}% &middot; 75th {pc['p75']}% &middot; 90th {pc['p90']}%.</p>
  <p class="links"><a class="go" href="/postdocs#ranking">Every institution
  ranked &rarr;</a><a class="go" href="/distributions">Distributions across
  the rest of the data &rarr;</a></p>
</section>"""


def speaker_slug(who: str, start: int, seen: dict) -> str:
    """A stable, readable anchor for one speaker's run at the podium.

    Contiguous runs, not one section per speaker: the Vice President
    opens and then closes, and collapsing those into a single block
    would put the closing remarks before three other speakers who
    actually spoke first. The recording is the order of record.

    A SECOND RUN IS NAMED FOR WHEN IT STARTS, not "-2". A numeric
    suffix is the signature of a de-duplication counter -- the thing
    that quietly hides two different rows behind one anchor -- and
    test_anchor_slugs.py fails any page carrying one, correctly. The
    timestamp says which run it is and stays put as long as the
    recording does.
    """
    import re as _re
    last = who.split()[-1].lower()
    last = _re.sub(r"[^a-z0-9]", "", last) or "speaker"
    seen[last] = seen.get(last, 0) + 1
    if seen[last] == 1:
        return last
    return f"{last}-at-{start // 60}m{start % 60:02d}"


def group_by_speaker(blocks: list, speakers: list, moments) -> tuple:
    """(html, nav) -- one collapsible section per run at the podium."""
    runs, cur = [], None
    for html, who, m in zip(blocks, speakers, moments):
        if cur is None or cur["who"] != who:
            cur = {"who": who, "items": [], "first": m.t, "last": m.t}
            runs.append(cur)
        cur["items"].append(html)
        cur["last"] = m.t

    seen: dict = {}
    out, nav = [], []
    for r in runs:
        slug = speaker_slug(r["who"], r["first"], seen)
        span = (clock(r["first"]) if r["first"] == r["last"]
                else f"{clock(r['first'])}&ndash;{clock(r['last'])}")
        n = len(r["items"])
        #: OPEN BY DEFAULT. A reader arriving at a transcript should see
        #: the transcript, and a page of shut drawers reads as empty.
        #: The control is there for folding a speaker away, not for
        #: hiding the page until someone clicks.
        out.append(
            f'<details class="spk" id="speaker-{slug}" open>'
            f'<summary><span class="sp-name">{E(r["who"])}</span>'
            f'<span class="sp-meta">{span} &middot; '
            f'{n} passage{"" if n == 1 else "s"}</span></summary>'
            f'{"".join(r["items"])}</details>')
        nav.append(
            f'<a class="sp-jump" href="#speaker-{slug}">'
            f'{E(r["who"])}<span class="sp-when">{span}</span></a>')
    return "".join(out), "".join(nav)


def main() -> int:
    blocks, used = [], 0
    speakers = []
    for i, m in enumerate(MOMENTS):
        ev = []
        for label, stem, path, how in m.evidence:
            ev.append(f'<li><span class="v">{E(fmt(resolve(stem, path), how))}</span>'
                      f'<span class="l">{E(label)}</span></li>')
            used += 1
        links = "".join(
            #: A LINK OUT OF THIS PAGE OPENS A NEW TAB. A reader working
            #: through the transcript is following an argument in order.
            #: Sending them to the query tool in the same tab loses their
            #: place in a twenty-minute press conference, and the back
            #: button returns them to the top of the page rather than to
            #: the moment they left.
            f'<a class="go" href="{E(h)}" target="_blank" '
            f'rel="noopener">{E(t)} &rarr;</a>' for h, t in m.links)
        #: NOT A SCORECARD. An earlier version stamped each moment
        #: "Our data agrees" or "Partly differs", which turned an evidence
        #: base into a fact-check and made the page about the gap between a
        #: spoken figure and a decimal place. That is not the job. The job
        #: is to put the federal record behind the statement, because the
        #: record is hard to carry in a speech and this site holds it.
        badge = ('<span class="vd ok">Federal data on this</span>'
                 if m.evidence else '')
        speakers.append(m.who)
        blocks.append(f"""
<section class="mo" id="t{m.t}" data-t="{m.t}">
  <div class="mo-head">
    <button class="ts" type="button" data-seek="{m.t}"
            data-track="press.seek.{m.t}"
            aria-label="Play from {clock(m.t)}">&#9654; {clock(m.t)}</button>
    <span class="who">{E(m.who)}</span>{badge}
  </div>
  <blockquote>{E(m.quote)}</blockquote>
  <h2>{E(m.heading)}</h2>
  {f'<ul class="ev">{"".join(ev)}</ul>' if ev else ''}
  {f'<p class="note">{E(m.note)}</p>' if m.note else ''}
  {f'<ul class="pts">{"".join(f"<li>{E(x)}</li>" for x in m.bullets)}</ul>'
   if m.bullets else ''}
  {f'<p class="ask"><a href="{E(m.ask[1])}">'
   f'<span class="ask-tag">The ask</span>{E(m.ask[0])} &rarr;</a></p>'
   if m.ask else ''}
  {charts_for(m.t)}
  {f'<p class="links">{links}</p>' if links else ''}
</section>""")

    stream, speaker_nav = group_by_speaker(blocks, speakers, MOMENTS)

    nav = "".join(
        f'<button type="button" class="jump" data-seek="{m.t}" '
        f'data-track="press.jump.{m.t}">{clock(m.t)} &middot; '
        f'{E(m.heading)}</button>' for m in MOMENTS)

    desc = (f"The {DATE} White House press conference on visa fraud, moment "
            f"by moment, with the federal data behind each claim.")

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Press Conference</title>
<meta name="description" content="{E(desc)}">
<meta property="og:title" content="The Press Conference">
<meta property="og:description" content="{E(desc)}">
<link rel="stylesheet" href="/style.css">
<style>
  .wrap {{ max-width: 1240px; margin: 0 auto; padding: 1.75rem 1.25rem 4rem; }}
  .page-head h1 {{ font-size: 2rem; margin: 0 0 .6rem; line-height: 1.18; }}
  .page-head p {{ color: var(--text-muted); max-width: 70ch; line-height: 1.68;
    margin: 0 0 .6rem; }}
  .kicker {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .08em;
    color: var(--text-muted); margin: 0 0 .5rem; }}

  /* THE PLAYER STAYS, THE TRANSCRIPT MOVES. Sticky rather than fixed, so it
     scrolls away naturally at the foot of the page instead of covering the
     method note. Below 900px it sits at the top and un-sticks: a sticky
     16:9 video on a phone eats half the screen. */
  .cols {{ display: grid; grid-template-columns: minmax(0,1fr) 420px;
    gap: 2rem; align-items: start; margin-top: 1.5rem; }}
  /* A grid item defaults to min-width:auto, which means it refuses to
     shrink below its content. The jump labels are sentences, so the rail
     held itself at 363px inside a 360px screen and pushed the page
     sideways. Both columns get min-width:0 so the track can actually
     shrink to the one fraction it was given. */
  .cols > * {{ min-width: 0; }}
  .rail {{ position: sticky; top: 1rem; min-width: 0; }}
  .jumps {{ max-width: 100%; }}
  @media (max-width: 900px) {{
    .cols {{ grid-template-columns: 1fr; gap: 1.25rem; }}
    .rail {{ position: static; order: -1; }}
  }}
  .player {{ position: relative; aspect-ratio: 16/9; background: #000;
    border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }}
  .player iframe {{ width: 100%; height: 100%; border: 0; display: block; }}
  /* The thumbnail is served from this origin, so the recording looks like
     a recording and nothing is still requested from YouTube until the
     reader presses play. No apology required. */
  .poster {{ position: absolute; inset: 0; padding: 0; border: 0; width: 100%;
    cursor: pointer; background: #000; display: block; }}
  .poster img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .poster .play {{ position: absolute; inset: 0; display: grid;
    place-items: center; font-size: 3.2rem; color: #fff;
    text-shadow: 0 2px 18px rgba(0,0,0,.65); transition: transform .12s; }}
  .poster:hover .play {{ transform: scale(1.08); }}

  /* COLLAPSIBLE CHARTS. Closed by default -- the prose carries the point
     and the chart is for the reader who wants the shape. The markup ships
     in the page either way, so the numbers survive with JavaScript off. */
  .panel {{ margin: .9rem 0 .2rem; border: 1px solid var(--border);
    border-radius: 9px; background: var(--surface); }}
  .panel > summary {{ cursor: pointer; padding: .55rem .8rem; font-size: .82rem;
    font-weight: 600; color: var(--hl); list-style: none; }}
  .panel > summary::-webkit-details-marker {{ display: none; }}
  .panel > summary::before {{ content: "\25B8"; display: inline-block;
    margin-right: .5rem; transition: transform .12s; }}
  .panel[open] > summary::before {{ transform: rotate(90deg); }}
  .panel > summary:hover {{ filter: brightness(1.15); }}
  .panel-body {{ padding: .2rem .8rem .9rem; }}
  .chart {{ width: 100%; height: auto; display: block; max-width: 640px; }}
  .chart .lab {{ font-size: 11px; fill: var(--text-muted); }}
  .chart .val {{ font-size: 11px; fill: var(--text-muted);
    font-variant-numeric: tabular-nums; }}
  .chart .val.hot {{ fill: var(--hl); font-weight: 700; }}
  .chart .bar {{ fill: var(--text-muted); opacity: .45; }}
  .chart .bar.hot {{ fill: var(--hl); opacity: 1; }}
  .rail .src {{ font-size: .75rem; color: var(--text-muted); margin: .6rem 0 0;
    line-height: 1.5; }}
  .jumps {{ display: flex; flex-direction: column; gap: .15rem; margin: 1rem 0 0;
    max-height: 42vh; overflow-y: auto; }}
  /* The labels are headings, not captions, and one of them is a whole
     sentence. Without wrapping the longest pushed the rail 23px past a
     360px screen and took the page sideways with it. */
  .jump {{ text-align: left; background: none; border: 0; cursor: pointer;
    font: inherit; font-size: .78rem; color: var(--text-muted);
    padding: .3rem .4rem; border-radius: 6px; border-left: 2px solid transparent;
    white-space: normal; overflow-wrap: anywhere; line-height: 1.4;
    max-width: 100%; }}
  .jump:hover {{ color: var(--hl); background: var(--surface); }}
  .jump.on {{ color: var(--hl); border-left-color: var(--hl);
    background: var(--surface); }}

  /* One collapsible block per run at the podium. */
  .speakers {{ display: flex; flex-wrap: wrap; gap: .4rem;
    margin: 0 0 1.4rem; }}
  .sp-jump {{ display: inline-flex; flex-direction: column; gap: .1rem;
    border: 1px solid var(--border); border-radius: 8px;
    padding: .35rem .7rem; font-size: .8rem; text-decoration: none;
    color: var(--text); background: var(--surface); line-height: 1.3; }}
  .sp-jump:hover {{ border-color: var(--hl); color: var(--hl); }}
  .sp-when {{ font-size: .68rem; color: var(--text-muted);
    font-variant-numeric: tabular-nums; }}
  .spk {{ border-top: 2px solid var(--hl); margin: 1.6rem 0 0; }}
  .spk > summary {{ cursor: pointer; list-style: none; padding: .6rem 0;
    display: flex; flex-wrap: wrap; align-items: baseline; gap: .6rem; }}
  .spk > summary::-webkit-details-marker {{ display: none; }}
  .spk > summary::before {{ content: "\\25bc"; font-size: .6rem;
    color: var(--text-muted); transition: transform .15s; }}
  .spk:not([open]) > summary::before {{ transform: rotate(-90deg); }}
  .sp-name {{ font-weight: 700; font-size: 1rem; }}
  .sp-meta {{ font-size: .76rem; color: var(--text-muted);
    font-variant-numeric: tabular-nums; }}
  .spk > summary:hover .sp-name {{ color: var(--hl); }}
  .spk .mo:first-of-type {{ border-top: 0; padding-top: .4rem; }}
  .pts {{ margin: .4rem 0 0; padding-left: 1.1rem; font-size: .92rem;
    line-height: 1.7; color: var(--text); }}
  .pts li {{ margin: 0 0 .15rem; }}
  /* THE ASK IS THE POINT OF THE PAGE, not an aside. Each one names a
     specific federal request and links straight to it. */
  .ask {{ margin: .8rem 0 0; }}
  .ask a {{ display: block; color: var(--hl); text-decoration: none;
    font-size: .9rem; line-height: 1.6; border-left: 3px solid var(--hl);
    padding: .55rem .9rem; border-radius: 0 8px 8px 0;
    background: color-mix(in srgb, var(--hl) 7%, transparent); }}
  .ask a:hover {{ background: color-mix(in srgb, var(--hl) 13%, transparent); }}
  .ask-tag {{ display: block; font-size: .66rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: .09em; margin-bottom: .2rem; }}
  .mo {{ border-top: 1px solid var(--border); padding: 1.6rem 0 .4rem;
    scroll-margin-top: 1rem; }}
  .mo-head {{ display: flex; flex-wrap: wrap; align-items: center; gap: .6rem;
    margin: 0 0 .7rem; }}
  .ts {{ background: var(--hl); color: #fff; border: 0; border-radius: 999px;
    padding: .2rem .65rem; font: inherit; font-size: .76rem; font-weight: 600;
    cursor: pointer; font-variant-numeric: tabular-nums; }}
  .ts:hover {{ filter: brightness(1.1); }}
  .who {{ font-size: .76rem; text-transform: uppercase; letter-spacing: .06em;
    color: var(--text-muted); font-weight: 600; }}
  .vd {{ font-size: .68rem; text-transform: uppercase; letter-spacing: .05em;
    padding: .12rem .5rem; border-radius: 999px; font-weight: 700; }}
  .vd.ok {{ background: rgba(34,160,90,.14); color: #1a7f48; }}
  .vd.no {{ background: rgba(200,120,0,.15); color: #9a5b00; }}
  :root:not([data-theme="light"]) .vd.ok {{ color: #5fd99a; }}
  :root:not([data-theme="light"]) .vd.no {{ color: #ffb454; }}
  :root[data-theme="dark"] .vd.ok {{ color: #5fd99a; }}
  :root[data-theme="dark"] .vd.no {{ color: #ffb454; }}
  blockquote {{ margin: 0 0 1rem; padding: 0 0 0 1rem;
    border-left: 3px solid var(--border); font-size: 1.04rem; line-height: 1.6;
    max-width: 62ch; }}
  .mo h2 {{ font-size: 1.08rem; margin: 0 0 .6rem; }}
  .ev {{ list-style: none; padding: 0; margin: 0 0 .9rem; display: grid;
    gap: .35rem; }}
  .ev li {{ display: flex; flex-wrap: wrap; gap: .6rem; align-items: baseline; }}
  .ev .v {{ color: var(--hl); font-weight: 800; font-size: 1.05rem;
    font-variant-numeric: tabular-nums; min-width: 5.5rem; }}
  .ev .l {{ font-size: .86rem; color: var(--text-muted); flex: 1; min-width: 0;
    line-height: 1.5; }}
  .note {{ font-size: .9rem; line-height: 1.68; max-width: 66ch;
    margin: 0 0 .8rem; }}
  .links {{ display: flex; flex-wrap: wrap; gap: .9rem; margin: 0; }}
  .go {{ font-size: .84rem; font-weight: 600; color: var(--hl);
    text-decoration: none; }}
  .go:hover {{ text-decoration: underline; }}
  .dist h3 {{ font-size: .95rem; margin: 1.4rem 0 .5rem; }}
  .hist {{ display: grid; gap: .22rem; margin: .6rem 0 .5rem; max-width: 60ch; }}
  .hrow {{ display: grid; grid-template-columns: 4.6rem 1fr 2.2rem;
    gap: .55rem; align-items: center; font-size: .78rem; }}
  .hb {{ color: var(--text-muted); font-variant-numeric: tabular-nums;
    text-align: right; }}
  .ht {{ background: var(--border); border-radius: 3px; height: .95rem;
    overflow: hidden; }}
  .hf {{ display: block; height: 100%; background: var(--text-muted);
    opacity: .55; border-radius: 3px 0 0 3px; }}
  .hf.hot {{ background: var(--hl); opacity: 1; }}
  .hn {{ font-variant-numeric: tabular-nums; font-weight: 600;
    font-size: .76rem; }}
  .cap {{ font-size: .78rem; color: var(--text-muted); line-height: 1.6;
    max-width: 68ch; margin: .5rem 0 .4rem; }}
  .table-wrap {{ overflow-x: auto; }}
  table.t {{ width: 100%; border-collapse: collapse; font-size: .82rem;
    margin: .4rem 0 0; }}
  table.t th {{ text-align: left; font-size: .68rem; text-transform: uppercase;
    letter-spacing: .05em; color: var(--text-muted); font-weight: 700;
    padding: .35rem .5rem; border-bottom: 1px solid var(--border);
    white-space: nowrap; }}
  table.t td {{ padding: .34rem .5rem; border-bottom: 1px solid var(--border); }}
  table.t td.num, table.t th.num {{ text-align: right;
    font-variant-numeric: tabular-nums; white-space: nowrap; }}
  table.t td.hi {{ color: var(--hl); font-weight: 700; }}
  .method {{ margin-top: 2.6rem; border-top: 3px solid var(--hl);
    padding-top: 1.2rem; }}
  .method p {{ font-size: .88rem; line-height: 1.7; max-width: 70ch;
    margin: 0 0 .7rem; color: var(--text-muted); }}
</style>
  <script id="phd-theme-boot">(function(){{try{{var t=localStorage.getItem("phd-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
  <script defer src="/theme.js"></script>
</head>
<body data-page="press-conference">
<main class="wrap">
<div class="page-head">
  <p class="kicker">{E(PUBLISHER)} &middot; {E(DATE)}</p>
  <h1>The press conference, with the data behind it</h1>
  <p>On {E(DATE)} the administration announced PERM suspensions for eight
  companies and a J-1 investigation into nine universities. The case rests
  on federal records that are difficult to carry in a speech. This site
  holds those records.</p>
  <p>Each moment below quotes the recording and sets the measured evidence
  beside it. Press a timestamp to hear it said. Where the published record
  stops short, the page says what is missing and what would settle it &mdash;
  because the gaps are themselves part of the case.</p>
</div>

<div class="cols">
  <nav class="speakers" aria-label="Jump to a speaker">{speaker_nav}</nav>
  <div class="stream">{stream}
  {distributions()}

  <section class="method" id="method">
    <h2>How to read this page</h2>
    <p><strong>The quotations are verbatim</strong>, taken from the published
    captions with their timestamps, so any one of them can be heard in
    context by pressing the time.</p>
    <p><strong>Six people spoke</strong> and each quotation names its
    speaker.</p>
    <p><strong>Every figure resolves from a federal dataset</strong> when the
    page is rendered. None is typed, and a figure that stops resolving fails
    the build rather than appearing as a dash. Each one links to the page
    where it can be checked at source.</p>
    <p><strong>Where the record stops, the page says so.</strong> Several of
    these claims cannot be settled from published data &mdash; not because
    they are wrong, but because the agency does not release the field. Those
    are listed as data requests, and they are the most useful thing this
    site can offer anyone working on this.</p>
    <p><strong>An investigation was announced.</strong> That is a fact with a
    date. Nothing here states that any institution or company broke a law.</p>
    <p>Source:
    <a href="{E(SOURCE_URL)}" target="_blank" rel="noopener">{E(TITLE)}</a>,
    {E(PUBLISHER)}, {E(DATE)}.</p>
  </section>
  </div>

  <aside class="rail">
    <div class="player" id="player">
      <button class="poster" id="poster" type="button"
              data-track="press.play"
              aria-label="Play the recording">
        <img src="/img/press-conference-thumb.jpg" alt="" width="1280"
             height="720" loading="lazy" decoding="async">
        <span class="play" aria-hidden="true">&#9654;</span>
      </button>
    </div>
    <p class="src">{E(TITLE)}<br>{E(PUBLISHER)}, {E(DATE)}</p>
    <div class="jumps">{nav}</div>
  </aside>
</div>
</main>

<script>
/* The embed is created on demand. Until the reader presses play there is no
   iframe, so no request reaches YouTube and nothing is set in their browser
   by a third party on a page about federal data. */
(function () {{
  var VIDEO = {json.dumps(VIDEO_ID)};
  var frame = null;

  function mount(at) {{
    var box = document.getElementById('player');
    var poster = document.getElementById('poster');
    if (poster) poster.remove();
    frame = document.createElement('iframe');
    frame.allow = 'accelerometer; encrypted-media; picture-in-picture';
    frame.allowFullscreen = true;
    frame.title = {json.dumps(TITLE)};
    frame.src = 'https://www.youtube-nocookie.com/embed/' + VIDEO +
                '?start=' + (at || 0) + '&autoplay=1&rel=0&enablejsapi=1';
    box.appendChild(frame);
  }}

  function seek(at) {{
    if (!frame) {{ mount(at); return; }}
    // postMessage avoids rebuilding the iframe, which would restart the
    // download and lose the reader's place.
    try {{
      frame.contentWindow.postMessage(JSON.stringify(
        {{event: 'command', func: 'seekTo', args: [at, true]}}), '*');
      frame.contentWindow.postMessage(JSON.stringify(
        {{event: 'command', func: 'playVideo', args: []}}), '*');
    }} catch (e) {{
      frame.src = 'https://www.youtube-nocookie.com/embed/' + VIDEO +
                  '?start=' + at + '&autoplay=1&rel=0&enablejsapi=1';
    }}
    var r = document.querySelector('.rail');
    if (r && window.innerWidth < 900) r.scrollIntoView({{behavior: 'smooth', block: 'start'}});
  }}

  document.addEventListener('click', function (e) {{
    var b = e.target.closest('[data-seek]');
    if (b) {{ seek(parseInt(b.dataset.seek, 10) || 0); return; }}
    if (e.target.closest('#poster')) mount(0);
  }});

  // Mark the moment the reader is looking at, so the jump list tracks the
  // page rather than only driving it.
  var secs = [].slice.call(document.querySelectorAll('.mo'));
  var jumps = [].slice.call(document.querySelectorAll('.jump'));
  if ('IntersectionObserver' in window && secs.length) {{
    var io = new IntersectionObserver(function (entries) {{
      entries.forEach(function (en) {{
        if (!en.isIntersecting) return;
        var t = en.target.dataset.t;
        jumps.forEach(function (j) {{
          j.classList.toggle('on', j.dataset.seek === t);
        }});
      }});
    }}, {{rootMargin: '-20% 0px -70% 0px'}});
    secs.forEach(function (s) {{ io.observe(s); }});
  }}
}})();
</script>
<script src="/analytics-beacon.js" defer></script>
<script src="/anchors.js" defer></script>
<script src="/sidebar.js"></script>
<script src="/chat-widget.js"></script>
</body>
</html>
"""
    write_text(OUT, page)
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(MOMENTS)} moments, {used} figures resolved, "
          f"{sum(1 for m in MOMENTS if m.evidence)} backed by data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
