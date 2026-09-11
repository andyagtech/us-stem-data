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
"""



# ---------------------------------------------------------------------------
# Status colours in light mode
# ---------------------------------------------------------------------------
# LIGHT_TOKENS above re-colours the ground, text and accent. It left every
# status colour at its dark-theme value -- green #4ade80, amber #fbbf24, sky
# #38bdf8 -- which were chosen to glow on navy and all but vanish on white:
# the MS count on every university page, the progress warnings, the chart
# legends. Those are mapped here.
#
# BY VALUE, NOT BY NAME. The same token name means different hues on different
# pages: --accent2 is pink on seven pages and blue on another, --accent3 is
# violet on some and green on others. Re-colouring by name would turn a blue
# accent pink. So each page's own dark value is looked up, and only values in
# this table are overridden; anything else -- including every page that was
# designed light in the first place -- is left exactly as it is.
DARK_TO_LIGHT = {
    "#4ade80": "#15803d", "#22c55e": "#15803d", "#34d399": "#047857",
    "#fb923c": "#c2410c",
    "#f87171": "#b91c1c", "#ef4444": "#b91c1c",
    "#fbbf24": "#a16207", "#facc15": "#a16207", "#f59e0b": "#b45309",
    "#60a5fa": "#1d4ed8", "#3b82f6": "#1d4ed8",
    "#a78bfa": "#6d28d9", "#8b5cf6": "#6d28d9",
    "#f472b6": "#be185d",
    "#2dd4bf": "#0f766e", "#22d3ee": "#0e7490", "#818cf8": "#4338ca",
    "#f0a5ae": "#b3123c",
    "#94a3b8": "#4b5563", "#64748b": "#4b5563",
    "#334155": "#e5e7eb", "#232733": "#e5e7eb",
}
# Owned by LIGHT_TOKENS, which already gives them a light value.
HANDLED = {"bg", "surface", "border", "text", "text-muted", "accent"}
STATUS_START, STATUS_END = "/* phd-light-status */", "/* /phd-light-status */"


def status_block(html: str) -> str:
    """The light overrides for this page's own status colours, or ''."""
    m = re.search(r":root\s*\{([^}]*)\}", html)
    if not m:
        return ""
    decls = []
    for name, val in re.findall(r"--([a-z0-9-]+)\s*:\s*([^;]+);", m.group(1)):
        light = DARK_TO_LIGHT.get(val.strip().lower())
        if light and name not in HANDLED:
            decls.append(f"--{name}:{light};")
    if not decls:
        return ""
    body = "".join(decls)
    return (f"{STATUS_START}\n@media (prefers-color-scheme: light){{"
            f":root:not([data-theme=\"dark\"]){{{body}}}}}\n"
            f":root[data-theme=\"light\"]{{{body}}}\n{STATUS_END}")


def apply_status_colours(check: bool) -> tuple[int, int]:
    """Insert or refresh the status block on every inline-palette page."""
    pat = re.compile(re.escape(STATUS_START) + r".*?" + re.escape(STATUS_END), re.S)
    touched = unchanged = 0
    for p in sorted(SITE.rglob("*.html")):
        t = p.read_text(errors="replace")
        if "/style.css" in t or MARKER not in t:
            continue                      # shared-stylesheet page, or no toggle
        want = status_block(t)
        if pat.search(t):
            new = pat.sub(lambda _m: want, t, count=1)
        elif want and "</style>" in t:
            i = t.index("</style>")
            new = t[:i] + want + "\n" + t[i:]
        else:
            new = t
        if new == t:
            unchanged += 1
            continue
        touched += 1
        if not check:
            p.write_text(new)
    return touched, unchanged


# ---------------------------------------------------------------------------
# Hard-coded colours that should have been tokens
# ---------------------------------------------------------------------------
# The status block above can only re-colour what reads a token. About 3,200
# colours in style blocks and style="" attributes were still literals --
# `color: #fbbf24` on every university page's MS count -- so in light mode they
# kept their dark-theme value and all but vanished on white.
#
# Each literal is replaced by the page's own token for EXACTLY that value, so
# in dark mode the page renders identically by construction; in light mode it
# then picks up the status block's colour. Three rules keep this safe, and the
# first is the one the 2026-08-28 pass broke:
#
#   1. A declaration that DEFINES a custom property is never touched. Rewriting
#      `--bg: #0f172a` to `--bg: var(--bg)` is what blanked dark mode on 237
#      pages. Declarations are handled one at a time and any starting with --
#      is skipped whole.
#   2. Scripts are never touched. Most script colours feed Chart.js, which
#      draws on a canvas and cannot resolve var(); rewriting them would break
#      every chart on the site.
#   3. Only values the page's own :root defines are replaced, so a literal
#      with no matching token is left exactly as it is.
HEX = re.compile(r"#[0-9a-fA-F]{6}(?![0-9a-fA-F])|#[0-9a-fA-F]{3}(?![0-9a-fA-F])")


def _page_tokens(html: str) -> dict[str, str]:
    """lower-cased hex -> the first token this page defines with that value."""
    m = re.search(r":root\s*\{([^}]*)\}", html)
    out: dict[str, str] = {}
    if m:
        for name, val in re.findall(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,6})\s*;", m.group(1)):
            out.setdefault(val.lower(), name)
    return out


def _tokenise_css(css: str, tokens: dict[str, str]) -> tuple[str, int]:
    n = 0

    def decl(m: re.Match) -> str:
        nonlocal n
        d = m.group(0)
        if d.lstrip().startswith("--"):
            return d                                   # rule 1
        def sub(h: re.Match) -> str:
            nonlocal n
            name = tokens.get(h.group(0).lower())
            if not name:
                return h.group(0)                      # rule 3
            n += 1
            return f"var(--{name})"
        return HEX.sub(sub, d)

    return re.sub(r"[^;{}]+", decl, css), n


def tokenise_literals(html: str) -> tuple[str, int]:
    tokens = _page_tokens(html)
    if not tokens:
        return html, 0
    total = 0
    parts = re.split(r"(<script\b[^>]*>.*?</script>)", html, flags=re.S | re.I)
    for i, part in enumerate(parts):
        if i % 2 == 1:
            continue                                   # rule 2
        def style_block(m: re.Match) -> str:
            nonlocal total
            css, k = _tokenise_css(m.group(2), tokens)
            total += k
            return m.group(1) + css + m.group(3)
        part = re.sub(r"(<style\b[^>]*>)(.*?)(</style>)", style_block, part,
                      flags=re.S | re.I)
        def style_attr(m: re.Match) -> str:
            nonlocal total
            css, k = _tokenise_css(m.group(2), tokens)
            total += k
            return m.group(1) + css + m.group(3)
        part = re.sub(r'(\bstyle=")([^"]*)(")', style_attr, part)
        parts[i] = part
    return "".join(parts), total


def apply_tokenise(check: bool) -> tuple[int, int]:
    files = replaced = 0
    for p in sorted(SITE.rglob("*.html")):
        t = p.read_text(errors="replace")
        if "/style.css" in t or MARKER not in t:
            continue
        new, k = tokenise_literals(t)
        if k:
            files += 1
            replaced += k
            if not check:
                p.write_text(new)
    return files, replaced

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

    tok_files, tok_n = apply_tokenise(args.check)
    touched, unchanged = apply_status_colours(args.check)
    print(f"  {len(changed)} pages given the toggle, {len(already)} already had it, "
          f"{len(skipped)} skipped (no tokens)")
    print(f"  hard-coded colours tokenised: {tok_n} in {tok_files} page(s)")
    print(f"  status colours for light mode: {touched} page(s) updated, "
          f"{unchanged} already current")
    for r in changed[:12]:
        print(f"    + {r}")
    if len(changed) > 12:
        print(f"    ... and {len(changed)-12} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
