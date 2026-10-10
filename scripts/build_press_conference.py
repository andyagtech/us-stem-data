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


def main() -> int:
    blocks, used = [], 0
    for i, m in enumerate(MOMENTS):
        ev = []
        for label, stem, path, how in m.evidence:
            ev.append(f'<li><span class="v">{E(fmt(resolve(stem, path), how))}</span>'
                      f'<span class="l">{E(label)}</span></li>')
            used += 1
        links = "".join(
            f'<a class="go" href="{E(h)}">{E(t)} &rarr;</a>' for h, t in m.links)
        badge = ""
        if m.verdict == "confirms":
            badge = '<span class="vd ok">Our data agrees</span>'
        elif m.verdict == "differs":
            badge = '<span class="vd no">Partly differs</span>'
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
  {f'<p class="links">{links}</p>' if links else ''}
</section>""")

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
  .rail {{ position: sticky; top: 1rem; }}
  @media (max-width: 900px) {{
    .cols {{ grid-template-columns: 1fr; gap: 1.25rem; }}
    .rail {{ position: static; order: -1; }}
  }}
  .player {{ position: relative; aspect-ratio: 16/9; background: #000;
    border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }}
  .player iframe {{ width: 100%; height: 100%; border: 0; display: block; }}
  .poster {{ position: absolute; inset: 0; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: .6rem; cursor: pointer;
    background: var(--surface); color: var(--text); border: 0; width: 100%;
    font: inherit; }}
  .poster .play {{ font-size: 2.2rem; color: var(--hl); }}
  .poster .cap {{ font-size: .8rem; color: var(--text-muted); max-width: 30ch;
    text-align: center; line-height: 1.5; }}
  .rail .src {{ font-size: .75rem; color: var(--text-muted); margin: .6rem 0 0;
    line-height: 1.5; }}
  .jumps {{ display: flex; flex-direction: column; gap: .15rem; margin: 1rem 0 0;
    max-height: 42vh; overflow-y: auto; }}
  .jump {{ text-align: left; background: none; border: 0; cursor: pointer;
    font: inherit; font-size: .78rem; color: var(--text-muted);
    padding: .3rem .4rem; border-radius: 6px; border-left: 2px solid transparent; }}
  .jump:hover {{ color: var(--hl); background: var(--surface); }}
  .jump.on {{ color: var(--hl); border-left-color: var(--hl);
    background: var(--surface); }}

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
  <h1>The press conference, claim by claim</h1>
  <p>On {E(DATE)} the administration announced PERM suspensions for eight
  companies and a J-1 investigation into nine universities. Most of what was
  said is checkable against federal data, and this site holds much of it.</p>
  <p>Each moment below quotes the recording, says who said it, and sets out
  what this site's data can and cannot show. Press a timestamp to hear it.
  Where our figures agree, it says so. Where they differ, it says that
  too.</p>
</div>

<div class="cols">
  <div class="stream">{''.join(blocks)}

  <section class="method" id="method">
    <h2>How to read this page</h2>
    <p><strong>The quotations are verbatim</strong>, taken from the published
    captions with their timestamps, so any one of them can be heard in
    context by pressing the time.</p>
    <p><strong>Six people spoke</strong> and each quotation names its
    speaker. Attributing one person's words to another would be the worst
    error this page could make.</p>
    <p><strong>Every figure on this page resolves from a built dataset</strong>
    when the page is rendered. None is typed, and a figure that stops
    resolving fails the build rather than appearing as a dash.</p>
    <p><strong>An investigation was announced.</strong> That is a fact with a
    date. Nothing here says any institution or company broke a law, and a
    citizenship share is not evidence of wrongdoing by anyone.</p>
    <p>Source:
    <a href="{E(SOURCE_URL)}" target="_blank" rel="noopener">{E(TITLE)}</a>,
    {E(PUBLISHER)}, {E(DATE)}.</p>
  </section>
  </div>

  <aside class="rail">
    <div class="player" id="player">
      <button class="poster" id="poster" type="button"
              data-track="press.play"
              aria-label="Load and play the recording">
        <span class="play">&#9654;</span>
        <span class="cap">Play the recording. Nothing is requested from
        YouTube until you press this.</span>
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
          f"{sum(1 for m in MOMENTS if m.verdict)} with a verdict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
