#!/usr/bin/env python3
"""Put each page's conclusion on it, idempotently.

The conclusions are declared in scripts/page_conclusions.py. This writes them
into the pages, replacing any block it wrote before, so running it twice
changes nothing and editing a declaration updates the page.

WHERE IT PUTS THEM. Before the page's "Method and limits" section where one
exists, because the conclusion belongs with the argument and the method
belongs after it. Otherwise before whatever element the declaration names,
otherwise at the end of <main>.

A page whose anchor cannot be found is REPORTED, never silently skipped: a
conclusion nobody can see is worse than no conclusion, because the author
believes it shipped.

Usage:
    python3 scripts/build_page_conclusions.py
    python3 scripts/build_page_conclusions.py --check    # report, write nothing
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                          # noqa: E402
from page_conclusions import CONCLUSIONS                     # noqa: E402

MARK_OPEN = "<!-- conclusion:begin -->"
MARK_CLOSE = "<!-- conclusion:end -->"
BLOCK = re.compile(re.escape(MARK_OPEN) + r".*?" + re.escape(MARK_CLOSE),
                   re.S)

CSS_ID = "conclusion-style"
CSS = f"""<style id="{CSS_ID}">
  /* The conclusion closes the page, so it is separated from the evidence
     above it and from whatever the template puts below. An earlier version
     had neither margin and collided with the next heading. */
  .conclusion {{ border-top: 3px solid var(--hl); margin: 3.5rem 0 2.5rem;
    padding: 1.6rem 0 0; clear: both; }}
  .conclusion h2 {{ font-size: 1.35rem; margin: 0 0 .5rem; }}
  .conclusion .cx-lede {{ font-size: 1.18rem; line-height: 1.55; font-weight: 600;
    max-width: 60ch; margin: 0 0 1.1rem; }}
  .conclusion .cx-body p {{ font-size: 1rem; line-height: 1.7; max-width: 68ch;
    margin: 0 0 .9rem; }}
  .conclusion .cx-body p:last-child {{ margin-bottom: 0; }}
  .cx-onward {{ margin: 1.8rem 0 0; padding: 1.1rem 0 0; border-top: 1px solid var(--border); }}
  .cx-onward-head {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .08em;
    color: var(--text-muted); margin: 0 0 .7rem; }}
  .cx-next-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: .7rem; }}
  .cx-next {{ display: block; text-decoration: none; color: inherit;
    border: 1px solid var(--border); border-radius: 10px; padding: .75rem .9rem;
    background: var(--surface); }}
  .cx-next:hover {{ border-color: var(--hl); }}
  .cx-label {{ display: block; font-weight: 650; font-size: .92rem; color: var(--hl); }}
  .cx-why {{ display: block; font-size: .8rem; line-height: 1.45; color: var(--text-muted);
    margin-top: .2rem; }}
</style>"""


def block_for(c) -> str:
    paras = "\n".join(f"    <p>{p}</p>" for p in c.paragraphs)
    nxt = ""
    if c.next:
        cards = "\n".join(
            f'    <a class="cx-next" href="{html.escape(h)}">'
            f'<span class="cx-label">{html.escape(l)}</span>'
            f'<span class="cx-why">{html.escape(w)}</span></a>'
            for h, l, w in c.next)
        nxt = (f'  <div class="cx-onward">\n'
               f'    <p class="cx-onward-head">Where to look next</p>\n'
               f'    <div class="cx-next-row">\n{cards}\n    </div>\n'
               f'  </div>\n')
    return (f'{MARK_OPEN}\n<section class="conclusion" id="what-this-means">\n'
            f'  <h2>{html.escape(c.heading)}</h2>\n'
            f'  <p class="cx-lede">{html.escape(c.lede)}</p>\n'
            f'  <div class="cx-body">\n{paras}\n  </div>\n'
            f'{nxt}</section>\n{MARK_CLOSE}')


def insertion_point(s: str, c) -> int | None:
    """Where the conclusion goes, in order of preference.

    A conclusion belongs AFTER the evidence. The first version fell back to
    whatever element the declaration named, which on a page with no method
    section put "What this adds up to" in the middle, above half the charts
    it was concluding from. So the fallbacks now all land at the end of the
    content: the last <script> block, or </main>, or </body>.
    """
    for pat in (r'<section[^>]*\sid="method"',
                r'<h2[^>]*\sid="method-and-limits"',
                rf'<[a-z]+[^>]*\sid="{re.escape(c.before)}"' if c.before else None,
                r'</main>',
                r'\n<script>',
                r'</body>'):
        if not pat:
            continue
        m = re.search(pat, s)
        if m:
            return m.start()
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    wrote, missing = 0, []
    for c in CONCLUSIONS:
        p = SITE / c.page
        if not p.exists():
            missing.append(f"{c.page} does not exist")
            continue
        s = p.read_text()
        s = BLOCK.sub("", s)            # replace any block written before
        at = insertion_point(s, c)
        if at is None:
            missing.append(f"{c.page}: nowhere to put it")
            continue
        s = s[:at] + block_for(c) + "\n\n" + s[at:]
        #: REPLACE, never skip. The first version only inserted the style
        #: block when it was absent, so editing the CSS here left every page
        #: carrying the first version's rules for ever -- the markup changed
        #: underneath and the styling silently did not follow.
        s = re.sub(rf'<style id="{CSS_ID}">.*?</style>\n?', "", s, flags=re.S)
        s = s.replace("</head>", CSS + "\n</head>", 1)
        if args.check:
            print(f"  would write {c.page}")
        else:
            write_text(p, s)
            print(f"  {c.page}: conclusion in place")
        wrote += 1

    for m in missing:
        print(f"  MISSING {m}")
    print(f"{wrote} conclusion(s), {len(missing)} unplaced")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
