#!/usr/bin/env python3
"""Add the theme boot script and toggle to every page that links style.css.

Two pieces, and the order between them is the whole trick. A tiny inline
script in <head> applies the stored preference BEFORE the first paint;
without it the page renders dark, then flips, and the toggle feels broken.
theme.js loads deferred afterwards and only draws the button.

Idempotent: a page already carrying the boot marker is left alone.

Usage:
  python3 scripts/add_theme_toggle.py
  python3 scripts/add_theme_toggle.py --check   # report, change nothing
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
MARKER = "phd-theme-boot"

BOOT = ('<script id="' + MARKER + '">(function(){try{var t=localStorage.getItem'
        '("phd-theme");if(t==="light"||t==="dark")document.documentElement'
        '.dataset.theme=t;}catch(e){}})();</script>')
LOADER = '<script defer src="/theme.js"></script>'

# The other 243 pages do not link style.css -- they carry the same tokens in
# an inline :root block. They need the light overrides injected too, or the
# button would appear and do nothing on almost every page of the site.
LIGHT_TOKENS = """
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){
--bg:#ffffff;--surface:#f6f7f9;--border:#d8dee6;--text:#111827;
--text-muted:#4b5563;--accent:#1d4ed8;color-scheme:light;}}
:root[data-theme="light"]{
--bg:#ffffff;--surface:#f6f7f9;--border:#d8dee6;--text:#111827;
--text-muted:#4b5563;--accent:#1d4ed8;color-scheme:light;}
.themebtn{position:fixed;right:20px;bottom:84px;z-index:60;display:inline-flex;
align-items:center;gap:7px;padding:7px 12px;border-radius:999px;
background:var(--surface);color:var(--text-muted);border:1px solid var(--border);
cursor:pointer;font:500 12px/1 -apple-system,BlinkMacSystemFont,'Segoe UI',
Roboto,sans-serif;letter-spacing:.02em;text-transform:lowercase;}
.themebtn:hover,.themebtn:focus-visible{color:var(--text);border-color:var(--accent);}
.themebtn .ic{font-size:13px;line-height:1;}
@media print{.themebtn{display:none;}}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    changed, already, skipped = [], [], []
    for p in sorted(SITE.rglob("*.html")):
        try:
            t = p.read_text(errors="replace")
        except Exception:
            continue
        rel = str(p.relative_to(SITE))
        if MARKER in t:
            already.append(rel)
            continue
        # Only pages that use the shared tokens; index.html carries its own
        # complete inline stylesheet and is deliberately left alone.
        if "</head>" not in t:
            skipped.append(rel)
            continue
        links_css = "/style.css" in t
        if not links_css and "--bg:" not in t:
            skipped.append(rel)          # neither shared nor inline tokens
            continue
        new = t
        if not links_css:
            # Inline-token page: append the light overrides to its own style
            # block rather than adding a second stylesheet.
            m = re.search(r"</style>", new)
            if not m:
                skipped.append(rel)
                continue
            new = new[:m.start()] + LIGHT_TOKENS + new[m.start():]
        new = new.replace("</head>", f"  {BOOT}\n  {LOADER}\n</head>", 1)
        if not args.check:
            p.write_text(new)
        changed.append(rel)

    print(f"  {len(changed)} pages given the toggle, {len(already)} already had it, "
          f"{len(skipped)} skipped (no tokens)")
    for r in changed[:12]:
        print(f"    + {r}")
    if len(changed) > 12:
        print(f"    ... and {len(changed)-12} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
