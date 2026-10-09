#!/usr/bin/env python3
"""The Data Asks page: what the federal government holds and does not publish.

WHY THIS PAGE EXISTS

Every other page here reports what the public record says. This one reports
where the public record stops, and names the office that could move it.

An absence is a finding on this site, and the discipline that applies to a
finding applies to an absence too. So an ask is not a wish. It names the
analysis it blocks, and the figures beside it resolve from the built data at
render time. If a dataset changes shape the ask changes with it, and an ask
whose evidence stops resolving fails the build rather than quietly becoming
untrue.

WHAT THIS PAGE DOES NOT ASK FOR

Anything that identifies a person. Nothing on this site names a worker, no
federal file used here names one, and no ask below would change that. Several
asks are deliberately for a tabulation rather than for microdata, because the
tabulation answers the question and the microdata would not be released.

Usage:
    python3 scripts/build_data_asks.py
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = SITE / "data"
OUT_HTML = SITE / "data_requests.html"
OUT_JSON = DATA / "data_asks.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                          # noqa: E402
from data_asks import ASKS, EFFORT                           # noqa: E402

E = html.escape

#: Agencies in the order a reader meets them, not alphabetically. Labor
#: certification first because it is where the series actually ended.
ORDER = ("USCIS", "Department of Labor", "DHS", "NSF",
         "National Center for Education Statistics",
         "State Department", "Bureau of Labor Statistics",
         "Department of Justice", "Internal Revenue Service",
         "No federal agency")

EFFORT_ORDER = ("restore", "collected", "aggregate", "new")


class EvidenceError(RuntimeError):
    pass


def resolve(file: str, path: str):
    """One figure, from the built data, by its exact field.

    Raises rather than returning a placeholder. A page that silently printed
    an em-dash where a figure should be would be making a weaker claim than
    the one it was written to make, and nobody would notice.
    """
    p = DATA / file
    if not p.exists():
        raise EvidenceError(f"{file} is not built; run its builder first")
    node = json.loads(p.read_text())
    for part in path.split("."):
        try:
            node = node[int(part)] if part.lstrip("-").isdigit() else node[part]
        except (KeyError, IndexError, TypeError) as exc:
            raise EvidenceError(f"{file}:{path} stopped resolving at "
                                f"{part!r} ({type(exc).__name__})") from exc
    return node


def fmt(value, how: str) -> str:
    if how == "raw":
        return str(value)
    if how == "n":
        return f"{value:,}"
    if how == "pct1":
        return f"{value:.1f}%"
    if how == "usd":
        return f"${value:,.0f}"
    raise EvidenceError(f"unknown format {how!r}")


def agency_group(name: str) -> str:
    """The office a reader would walk into, not the full attribution line."""
    for prefix in ORDER:
        if name.startswith(prefix):
            return prefix
    return name.split(",")[0].split(";")[0].strip()


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
  .wrap {{ max-width: 1020px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}
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

  .ask {{ border: 1px solid var(--border); border-radius: 10px; padding: 1.1rem 1.2rem;
    margin: 1rem 0 0; background: var(--surface); }}
  .ask h3 {{ margin: 0 0 .1rem; font-size: 1.02rem; line-height: 1.35; }}
  .ask .agency {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .06em;
    color: var(--text-muted); margin: 0 0 .5rem; }}
  .ask dl {{ margin: .7rem 0 0; display: grid; grid-template-columns: 9.5rem 1fr; gap: .35rem .9rem; }}
  .ask dt {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .05em;
    color: var(--text-muted); padding-top: .15rem; }}
  .ask dd {{ margin: 0; font-size: .89rem; line-height: 1.6; }}
  @media (max-width: 620px) {{ .ask dl {{ grid-template-columns: 1fr; gap: .1rem; }}
    .ask dd {{ margin-bottom: .6rem; }} }}

  /* The effort badge is the axis that decides the conversation, so it is the
     one piece of colour on the card. Status colour, not a series colour. */
  .badge {{ display: inline-block; font-size: .7rem; font-weight: 600; letter-spacing: .03em;
    padding: .18rem .55rem; border-radius: 999px; border: 1px solid; white-space: nowrap; }}
  .badge.restore   {{ color: #b4530a; border-color: #b4530a40; background: #b4530a14; }}
  .badge.collected {{ color: #1d7a4c; border-color: #1d7a4c40; background: #1d7a4c14; }}
  .badge.aggregate {{ color: #2f6ab5; border-color: #2f6ab540; background: #2f6ab514; }}
  .badge.new       {{ color: #8a3b6b; border-color: #8a3b6b40; background: #8a3b6b14; }}

  .ev {{ margin: .75rem 0 0; padding-top: .6rem; border-top: 1px dashed var(--border); }}
  .ev .row {{ display: flex; gap: .6rem; align-items: baseline; font-size: .82rem; padding: .12rem 0; }}
  .ev .v {{ font-weight: 700; font-variant-numeric: tabular-nums; color: var(--hl);
    min-width: 8.5rem; text-align: right; }}
  .ev .k {{ color: var(--text-muted); }}
  .ev .src {{ font-size: .7rem; color: var(--text-muted); margin: .4rem 0 0; }}

  .legend {{ display: grid; gap: .6rem; margin: 1rem 0 0; }}
  .legend .row {{ display: grid; grid-template-columns: 13rem 1fr; gap: .8rem; align-items: start; font-size: .86rem; }}
  .legend p {{ margin: 0; color: var(--text-muted); line-height: 1.55; }}
  @media (max-width: 620px) {{ .legend .row {{ grid-template-columns: 1fr; gap: .15rem; }} }}
</style>
  <script id="phd-theme-boot">(function(){{try{{var t=localStorage.getItem("phd-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
  <script defer src="/theme.js"></script>
</head>
<body data-page="data-asks">
<a class="skip-link" href="#asks">Skip to the asks</a>
<main id="main">
<div class="wrap">
"""


def evidence_html(ask) -> str:
    if not ask.evidence:
        return ""
    rows, srcs = [], []
    for label, file, path, how in ask.evidence:
        rows.append(f'<div class="row"><span class="v">'
                    f'{E(fmt(resolve(file, path), how))}</span>'
                    f'<span class="k">{E(label)}</span></div>')
        srcs.append(f"{file}:{path}")
    return (f'<div class="ev">{"".join(rows)}'
            f'<p class="src">Built at render time from {E(", ".join(srcs))}.</p>'
            f'</div>')


def ask_html(ask, n: int) -> str:
    label, _ = EFFORT[ask.effort]
    note = (f'<dt>Note</dt><dd>{E(ask.note)}</dd>' if ask.note else "")
    return f"""
<article class="ask" id="ask-{n}">
<p class="agency">{n}. {E(ask.held_by)}</p>
<h3>{E(ask.title)}</h3>
<p style="margin:.5rem 0 0"><span class="badge {E(ask.effort)}">{E(label)}</span></p>
<dl>
<dt>Collected on</dt><dd>{E(ask.collected_on)}</dd>
<dt>Published now</dt><dd>{E(ask.published_now)}</dd>
<dt>The request</dt><dd><strong>{E(ask.request)}</strong></dd>
<dt>Would settle</dt><dd>{E(ask.would_settle)}</dd>
{note}
</dl>
{evidence_html(ask)}
</article>
"""


def build() -> int:
    groups: dict[str, list] = {}
    for a in ASKS:
        groups.setdefault(agency_group(a.held_by), []).append(a)
    ordered = [g for g in ORDER if g in groups] + \
              [g for g in sorted(groups) if g not in ORDER]

    #: One running number across the page, assigned in the order the
    #: asks are declared, so an ask can be cited as "ask 9" and stay
    #: findable when another is added to a different agency.
    numbers = {id(a): i for i, a in enumerate(ASKS, 1)}

    counts = {k: sum(1 for a in ASKS if a.effort == k) for k in EFFORT_ORDER}
    held = counts["collected"] + counts["restore"]

    title = "Data Asks"
    desc = (f"{len(ASKS)} datasets the federal government holds or once "
            f"published that would answer a question this site cannot. "
            f"Each names the analysis it blocks.")

    parts = [head(title, desc), f"""
<div class="page-head">
<p class="kicker">What is collected, and what is released</p>
<h1>Data Asks</h1>
<p>Every other page on this site reports what the public record says. This one
reports where it stops.</p>
<p>Each ask below names something a federal office holds, or once published,
that would answer a question this site currently cannot. It says what is
missing, and it says which analysis is blocked. The figures beside each ask
are read from this site's own built data when the page is rendered, so an ask
cannot outlive the evidence for it.</p>
<p><strong>{held} of {len(ASKS)} are not requests for new collection.</strong>
The agency already has the field on a form it already processes, or published
it until recently and stopped. Those are disclosure decisions. The rest are
marked, because a release decision and a budget request are different
conversations.</p>
<p>Nothing here asks for anything that identifies a person. Several asks are
deliberately for a tabulation rather than for record-level data, because the
tabulation answers the question and the records would not be released.</p>
</div>

<div class="stats">
  <div class="stat"><div class="n">{len(ASKS)}</div><p class="l">asks</p>
    <p class="s">across {len(ordered)} departments and agencies</p></div>
  <div class="stat"><div class="n">{counts['collected']}</div><p class="l">already collected</p>
    <p class="s">on a form the agency already processes</p></div>
  <div class="stat"><div class="n">{counts['restore']}</div><p class="l">published, then stopped</p>
    <p class="s">the collection did not change; the release did</p></div>
  <div class="stat"><div class="n">{counts['new']}</div><p class="l">would need new collection</p>
    <p class="s">a cost, and a different conversation</p></div>
</div>

<section class="block" id="no-requirement">
<h2>Nobody is required to publish any of this</h2>
<p class="lede">The gap this page describes starts before any federal agency.
It starts with the fact that a university does not have to tell anyone what it
awarded, to whom, or on whose money.</p>
<p>There is no federal rule obliging a university to publish a dissertation or
a thesis. There is no rule obliging it to list the ones it has awarded. Each
institution decides for itself, and the decision is often revisited department
by department. There is no national register of awarded doctorates and no
federal index of where a dissertation can be read. The largest single
collection is held by ProQuest, which is a private subscription product.</p>
<p>So the record on this site was built one institution at a time, because
there is no list to work from. Of the
<strong><!--auto:data:repository_index.institutions|n-->106<!--/auto--></strong>
institutions searched,
<strong><!--auto:data:repository_index.without_repository|n-->7<!--/auto--></strong>
publish nothing the harvest could find, and
<strong><!--auto:data:repository_index.indirect_resolvers|n-->27<!--/auto--></strong>
more are reachable only through a handle or DOI resolver rather than a
browsable index. Several that do publish cover only recent years, or only some
departments.</p>
<p><strong>Coverage here is a floor, and the absence is not evenly spread.</strong>
A university that posts less is not a university that awards less. Every
institution-level figure on this site should be read as the smallest the true
number can be, and the ranking between two institutions is partly a ranking of
how much each chose to make public.</p>
<p>This is the first ask on the page, and it is the one the public most
obviously already paid for.</p>
</section>

<section class="block" id="how-to-read">
<h2>How to read an ask</h2>
<p class="lede">The badge is the part that decides who you are talking to.</p>
<div class="legend">
{"".join(f'<div class="row"><span><span class="badge {k}">{E(EFFORT[k][0])}</span></span>'
         f'<p>{E(EFFORT[k][1])}</p></div>' for k in EFFORT_ORDER)}
</div>
</section>

<section class="block" id="asks">
<h2>The asks</h2>
<p class="lede">Grouped by the office that holds the data.</p>
</section>
"""]

    for g in ordered:
        items = sorted(groups[g], key=lambda a: EFFORT_ORDER.index(a.effort))
        parts.append(f'<section class="block" id="{E(g.lower().replace(" ", "-").replace(",", ""))}">'
                     f'<h2>{E(g)}</h2>')
        parts.extend(ask_html(a, numbers[id(a)]) for a in items)
        parts.append("</section>")

    parts.append("""
<section class="block" id="method">
<h2>How this page is built</h2>
<p class="lede">The asks are declared once, in
<code>scripts/data_asks.py</code>. Each one names the dataset that demonstrates
the gap, and the builder reads the figure from that dataset when the page is
rendered.</p>
<ul class="note">
<li>No figure on this page is typed. An ask whose evidence stops resolving
fails the build, so the page cannot keep making a claim the data no longer
supports.</li>
<li>Every gap described here was met while building something else on this
site. None was looked for.</li>
<li>An ask is about publication, not about collection, unless it says
otherwise. Where a field is already on a federal form, the page says so.</li>
<li>Nothing here is a criticism of the staff who publish these files. Most of
these gaps are decisions taken years ago for reasons that were good at the
time, and several would cost almost nothing to revisit.</li>
</ul>
</section>
</div>
</main>
<script src="/analytics-beacon.js" defer></script>
<script src="/anchors.js" defer></script>
<script src="/sidebar.js"></script>
<script src="/states.js"></script>
</body>
</html>
""")

    payload = {
        "generated_from": "scripts/data_asks.py",
        "asks": [
            {"held_by": a.held_by, "title": a.title, "effort": a.effort,
             "effort_label": EFFORT[a.effort][0], "note": a.note,
             "number": numbers[id(a)],
             "collected_on": a.collected_on, "published_now": a.published_now,
             "request": a.request, "would_settle": a.would_settle,
             "evidence": [{"label": l, "dataset": f, "path": p,
                           "value": resolve(f, p)}
                          for l, f, p, _ in a.evidence]}
            for a in ASKS],
        "counts": counts,
        "agencies": ordered,
    }
    write_text(OUT_JSON, json.dumps(payload, indent=1))
    write_text(OUT_HTML, "".join(parts))
    print(f"wrote {OUT_HTML.relative_to(ROOT)} and {OUT_JSON.relative_to(ROOT)}")
    print(f"  {len(ASKS)} asks, {len(ordered)} agencies, "
          f"{held} needing no new collection")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(build())
    except EvidenceError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
