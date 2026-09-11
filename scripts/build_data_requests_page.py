#!/usr/bin/env python3
"""Publish the data-requests memo as a page on the site.

report/data_requests.html is the one source. It is written in the artifact
convention -- a <title>, a <style> and the body, with no document shell -- so
this wraps it in the site's head (charset, viewport, description, the theme
boot that applies a stored light/dark choice before first paint) and appends
the site's scripts: the sidebar, section anchors and the analytics beacon.
Editing the memo means editing report/data_requests.html and re-running this;
the site page is never edited by hand, so the two cannot drift apart.

Usage:
  python3 scripts/build_data_requests_page.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from add_theme_toggle import BOOT, LOADER                    # noqa: E402
from atomic_write import write_text                          # noqa: E402
from add_section_anchors import slugify                      # noqa: E402

SRC = ROOT / "report" / "data_requests.html"
OUT = ROOT / "site" / "data_requests.html"
DESCRIPTION = ("Eight aggregate extracts of federal data -- seven of them already "
               "collected -- that would settle what the published record cannot: "
               "H-1B cap status, L-1 and O-1 by employer, F-1 students by school, "
               "and more.")


def main() -> int:
    src = SRC.read_text()
    m = re.search(r"<title>(.*?)</title>", src, re.S)
    title = m.group(1).strip() if m else "Federal data requests"
    body = re.sub(r"<title>.*?</title>\s*", "", src, count=1, flags=re.S)
    style = re.search(r"<style>.*?</style>", body, re.S)
    head_style = style.group(0) if style else ""
    content = body.replace(head_style, "", 1).strip()
    # Every heading gets an id so sections can be linked, using the anchor
    # tool's own slug so anchors.js resolves the same string. This page is
    # generated, so the anchor tool skips it and the ids are stamped here.
    seen: set[str] = set()
    def stamp(m: re.Match) -> str:
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        if "id=" in attrs:
            return m.group(0)
        slug = slugify(re.sub(r"<[^>]+>", "", inner)) or tag
        base, n = slug, 2
        while slug in seen:
            slug, n = f"{base}-{n}", n + 1
        seen.add(slug)
        return f'<{tag}{attrs} id="{slug}">{inner}</{tag}>'
    content = re.sub(r"<(h[1-3])([^>]*)>(.*?)</\1>", stamp, content, flags=re.S)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{DESCRIPTION}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{DESCRIPTION}">
<link rel="icon" type="image/x-icon" href="/favicon.ico">
{head_style}
  {BOOT}
  {LOADER}
</head>
<body data-page="data_requests">
<main id="main">
{content}
</main>
<script src="/sidebar.js"></script>
<script src="/anchors.js" defer></script>
<script src="/analytics-beacon.js" defer></script>
</body>
</html>
"""
    write_text(OUT, page)
    print(f"  wrote {OUT.relative_to(ROOT)} from {SRC.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
