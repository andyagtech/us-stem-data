#!/usr/bin/env python3
"""Build the "what you can ask" page from the curated question list.

A chat box with no prompt is a chat box nobody uses well: people ask one
vague question, get a hedged answer, and leave. The questions that work are
the ones the assistant has data for, and that list already exists -- it is
the curated set the cache is warmed from.

Generating the page from that list keeps three things in step that otherwise
drift apart: what a reader is invited to ask, what the cache is warmed with,
and what the assistant can actually answer. Add a question to the YAML and it
appears here and is warmed; it cannot appear here without being warmed.

Usage:
  python3 scripts/build_ask_guide.py
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text as _atomic_write_text  # noqa: E402
# The slug convention belongs to add_section_anchors.py and anchors.js has to
# agree with it at runtime. Importing it keeps one definition rather than a
# copy that drifts the first time an entity appears in a heading.
from add_section_anchors import slugify  # noqa: E402

SRC = ROOT / "cloud" / "chat" / "curated_answers.yaml"
OUT = ROOT / "site" / "ask.html"

GROUPS = {
    "finding": ("The central finding", "What the site argues, and how firmly."),
    "pipeline": ("The domestic pipeline",
                 "Whether America trains its own STEM talent, and what a degree pays."),
    "fields": ("Fields and programmes", "Where the concentration actually sits."),
    "schools": ("Institutions", "Individual universities and how they compare."),
    "work": ("Work visas", "OPT, the H-1B cap and the routes around it."),
    "outcomes": ("After the degree", "Green cards, and whether people stay."),
    "cost": ("Public money", "What federal funding buys, and for whom."),
    "visas": ("Visa mechanics", "How the categories work."),
    "hard": ("The hard questions", "Where the argument is weakest, asked plainly."),
    "method": ("Method and limits", "Sources, definitions, and what cannot be answered."),
    "compare": ("Comparing institutions",
                "Any two universities on the same measures, or a whole state."),
    "wages": ("What the work pays",
              "The wage promised on a visa filing, against the local market."),
}
ORDER = ["finding", "pipeline", "work", "wages", "outcomes", "fields",
         "schools", "compare", "cost", "visas", "hard", "method"]


def main() -> int:
    import yaml
    answers = yaml.safe_load(SRC.read_text())["answers"]
    by_group: dict[str, list[str]] = {}
    for e in answers:
        if e.get("skip"):
            continue
        by_group.setdefault(e["group"], []).append(e["question"])

    unknown = [g for g in by_group if g not in GROUPS]
    if unknown:
        print(f"  groups with no heading: {', '.join(unknown)}")

    blocks = []
    for g in ORDER + unknown:
        qs = by_group.get(g)
        if not qs:
            continue
        title, blurb = GROUPS.get(g, (g.title(), ""))
        items = "\n".join(
            f'      <li><button class="ask" data-q="{html.escape(q, quote=True)}">'
            f'{html.escape(q)}</button></li>' for q in qs)
        blocks.append(
            f'    <section class="ask-group">\n'
            f'      <h2 id="{slugify(title)}">{html.escape(title)}</h2>\n'
            f'      <p class="ask-blurb">{html.escape(blurb)}</p>\n'
            f'      <ul class="ask-list">\n{items}\n      </ul>\n'
            f'    </section>')

    total = sum(len(v) for v in by_group.values())
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>What you can ask</title>
<meta name="description" content="{total} questions this site's assistant can
answer from federal data, grouped by topic.">
<link rel="stylesheet" href="/style.css">
<script defer src="/chat-widget.js"></script>
<style>
.ask-list{{list-style:none;padding:0;margin:0 0 1.4rem}}
.ask-list li{{margin:0 0 .45rem}}
.ask{{font:inherit;text-align:left;background:none;border:0;padding:.35rem .5rem;
     margin:0 -.5rem;border-radius:6px;cursor:pointer;color:inherit;width:100%}}
.ask:hover,.ask:focus-visible{{background:rgba(127,127,127,.14)}}
.ask-blurb{{margin:.1rem 0 .7rem;opacity:.72;font-size:.94rem}}
.ask-group{{margin:0 0 1.9rem}}
</style>
</head><body>
<div class="wrap">
<h1 id="what-you-can-ask">What you can ask</h1>
<p class="lede">{total} questions the assistant answers from federal data.
Click one to ask it. Every figure it gives you comes from a tool call made in
that conversation, not from memory.</p>

<p>These are the questions the assistant is warmed for, so they return
immediately. Anything else works too &mdash; it just takes a moment longer while
the model does the work.</p>

{chr(10).join(blocks)}

<h2 id="what-it-will-not-do">What it will not do</h2>
<p>It will not give you a figure it cannot source, and it will say so rather
than estimate. Three limits come up often: cap-exempt status is not published
by USCIS, so no employer-level count of it exists; IPEDS counts degrees rather
than people, so progression figures are ratios between two populations; and no
federal source records graduate applications or admissions, so whether
domestic applicants are declining, being declined, or not applying cannot be
answered from published data.</p>

<p><a href="/methodology">Every dataset behind these answers, with a link
to its source &rarr;</a></p>
</div>
<script>
// The widget exposes window.__phdChat with open() and send(). An earlier
// version of this page called window.openChatWith and fell back to a ?q=
// parameter -- neither exists, so every button on the page did nothing.
document.addEventListener('click', function (e) {{
  var b = e.target.closest('.ask');
  if (!b) return;
  var q = b.dataset.q;
  var chat = window.__phdChat;
  if (chat && typeof chat.send === 'function') {{
    if (typeof chat.open === 'function') chat.open();
    chat.send(q);
    return;
  }}
  // The widget loads asynchronously; wait briefly rather than losing the click.
  var tries = 0;
  var t = setInterval(function () {{
    var c = window.__phdChat;
    if (c && typeof c.send === 'function') {{
      clearInterval(t);
      if (typeof c.open === 'function') c.open();
      c.send(q);
    }} else if (++tries > 40) {{
      clearInterval(t);
      b.textContent = q + ' \u2014 the assistant did not load';
    }}
  }}, 150);
}});
</script>
</body></html>
"""
    _atomic_write_text(OUT, page)
    print(f"  {total} questions across {len(by_group)} groups")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
