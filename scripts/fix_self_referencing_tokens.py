#!/usr/bin/env python3
"""Restore colour tokens that were rewritten to reference themselves.

WHAT HAPPENED. On 2026-08-28 a one-off pass replaced every hard-coded colour
on the site with its token -- #0f172a became var(--bg) -- so the light theme
could reach pages that carried their own inline palette. It also rewrote the
lines that DEFINE those tokens, so `--bg: #0f172a` became `--bg: var(--bg)`.

A custom property that refers to itself is a dependency cycle. The browser
discards it as invalid at computed-value time, `background: var(--bg)` falls
through to transparent, and the page shows the white canvas beneath. On 237
pages that meant, in dark mode, near-white text on a white page and a sidebar
with no background at all. Light mode survived by accident: the light
overrides sit in a more specific selector and win regardless.

WHAT THIS DOES. For each self-referencing declaration it recovers the literal
the file carried before that commit, from git, and writes it back. A file that
did not exist then, or whose old value cannot be found, gets the palette the
dark theme has always used, and is reported so the fallback is visible.

Idempotent. Pair with check_consistency.py, which now fails on any
self-referencing custom property anywhere under site/.

Usage:
  python3 scripts/fix_self_referencing_tokens.py --check   # report only
  python3 scripts/fix_self_referencing_tokens.py
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SITE_REPO = SITE.resolve().parent            # site/ is a symlink into the private repo
BAD_COMMIT = "41c033e"

# What the dark theme has always used; the generators still emit these.
DARK = {"bg": "#0f172a", "surface": "#1e293b", "border": "#334155"}

SELF_REF = re.compile(r"--([a-z0-9-]+)(\s*:\s*)var\(--\1\)")
LITERAL = r"--{name}\s*:\s*(#[0-9a-fA-F]{{3,8}}|rgba?\([^)]*\))"


def before_bad_commit(rel: str) -> str | None:
    r = subprocess.run(["git", "-C", str(SITE_REPO), "show",
                        f"{BAD_COMMIT}^:site/{rel}"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    fixed = fell_back = 0
    fallback_files = []
    for path in sorted(SITE.rglob("*")):
        if path.suffix not in (".html", ".css", ".js") or not path.is_file():
            continue
        src = path.read_text(errors="replace")
        if not SELF_REF.search(src):
            continue
        rel = path.relative_to(SITE).as_posix()
        old = before_bad_commit(rel)

        def restore(m: re.Match) -> str:
            nonlocal fixed, fell_back
            name = m.group(1)
            value = None
            if old:
                hit = re.search(LITERAL.format(name=re.escape(name)), old)
                value = hit.group(1) if hit else None
            if value is None:
                value = DARK.get(name)
                fell_back += 1
                fallback_files.append(f"{rel}:--{name}")
            if value is None:
                return m.group(0)          # nothing to restore it to; leave, report below
            fixed += 1
            return f"--{name}{m.group(2)}{value}"

        new = SELF_REF.sub(restore, src)
        if new != src and not args.check:
            path.write_text(new)

    remaining = [p.relative_to(SITE).as_posix() for p in SITE.rglob("*")
                 if p.suffix in (".html", ".css", ".js") and p.is_file()
                 and SELF_REF.search(p.read_text(errors="replace"))]
    verb = "would restore" if args.check else "restored"
    print(f"  {verb} {fixed} declaration(s); "
          f"{fell_back} from the dark palette rather than git history")
    for f in fallback_files[:10]:
        print(f"    fallback: {f}")
    if not args.check:
        print(f"  self-referencing declarations left: {len(remaining)}")
    return 1 if (not args.check and remaining) else 0


if __name__ == "__main__":
    raise SystemExit(main())
