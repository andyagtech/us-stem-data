#!/usr/bin/env python3
"""One site, one name in the browser tab.

An audit on 2026-10-13 found three conventions in 59 <title> tags: 20 ended
"— PhD Demographics", 29 ended with nothing, and site/data_sources.html still
ended "— USDS China", a brand the project had already renamed away from. A
reader with eight tabs open could not tell which belonged to this site.

WHY A PASS AND NOT AN EDIT. Most pages here are written by a builder --
build_static_pages, build_h1b_explorer, build_lab_directory, build_industry_pages
and a dozen more emit the whole file. A title typed into the HTML lasts until
the next rebuild. So this is a pass, idempotent, run at deploy beside
add_theme_toggle.py for the same reason that one exists: deploy is the single
step every page goes through.

WHAT IS LEFT ALONE.
  index.html     its <title> IS the site's name. "US Graduate Program
                 Demographics and Funding — PhD Demographics" says it twice.
  redirect stubs "Moved to /presentation" is the whole message and these
                 pages carry noindex; a brand on them is noise.
  private pages  not part of the public site (scripts/private_pages.py).

Usage:
  python3 scripts/normalise_titles.py --report
  python3 scripts/normalise_titles.py --write
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
from private_pages import PRIVATE                            # noqa: E402

SUFFIX = "PhD Demographics"
SEP = " — "                                             # em dash

#: Brands this project used before and must not keep showing a reader.
STALE = ("USDS China", "usds-china")

#: name -> why, so the report says which rule skipped a page.
SKIP = {"index.html": "the title is the site's own name"}
SKIP.update({n: "not part of the public site" for n in PRIVATE})

TITLE_RE = re.compile(r"(<title>)(.*?)(</title>)", re.S | re.I)


def is_stub(src: str) -> bool:
    """A redirect stub: it says so in a meta refresh and carries noindex."""
    return ('http-equiv="refresh"' in src.lower()
            and "noindex" in src.lower())


def normalise(title: str) -> str:
    """Strip any stale brand, then end with exactly one current one."""
    t = re.sub(r"\s+", " ", title).strip()
    for bad in STALE:
        # Both "X — USDS China" and a bare "USDS China" tail.
        t = re.sub(r"\s*[—–-]\s*" + re.escape(bad) + r"\s*$", "", t,
                   flags=re.I).strip()
    # Compared unescaped, returned escaped. An earlier draft returned the
    # unescaped form and rewrote "Scholarships &amp; NGOs" to a raw
    # ampersand: a pass that corrupts what it touches is worse than drift.
    if html.unescape(t).endswith(SUFFIX):
        # Already ends with the brand; only the separator may be wrong.
        head = t[: -len(SUFFIX)].rstrip().rstrip("—–-").rstrip()
        return (head + SEP + SUFFIX) if head else SUFFIX
    return t + SEP + SUFFIX


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    changed, skipped, already = [], [], 0
    for path in sorted(SITE.glob("*.html")):
        if path.name in SKIP:
            skipped.append((path.name, SKIP[path.name]))
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        if is_stub(src):
            skipped.append((path.name, "redirect stub"))
            continue
        m = TITLE_RE.search(src)
        if not m or not m.group(2).strip():
            skipped.append((path.name, "no title to normalise"))
            continue
        old = re.sub(r"\s+", " ", m.group(2)).strip()
        new = normalise(old)
        if new == old:
            already += 1
            continue
        changed.append((path.name, old, new))
        if args.write:
            path.write_text(TITLE_RE.sub(
                lambda mm: mm.group(1) + new + mm.group(3), src, count=1),
                encoding="utf-8")

    for name, old, new in changed:
        print(f"  {name}")
        print(f"      {old}")
        print(f"   -> {new}")
    for name, why in skipped:
        print(f"  skip {name:28} {why}")
    verb = "retitled" if args.write else "would retitle"
    print(f"  {verb} {len(changed)}; {already} already correct; "
          f"{len(skipped)} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
