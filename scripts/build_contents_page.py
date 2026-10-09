#!/usr/bin/env python3
"""Build site/contents.html: every page on the site, in one list.

WHY. The site had sitemap.xml for crawlers and no table of contents for
people. It also had twelve live pages that appeared in no navigation at all --
the national overview among them -- reachable only by typing the URL. Most are
now in the sidebar; this page is the complete list, including the ones that are
deliberately not in the sidebar.

It is GENERATED from the site's own navigation (site/sidebar.js) and its site
map, so it cannot drift from them: a page added to the sidebar appears here,
and a page in the site map that is in no section appears under "Also on the
site" rather than going unlisted. check_consistency.py fails the build if a
page is missing from it.

Usage:
  python3 scripts/build_contents_page.py
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from add_theme_toggle import BOOT, LOADER                    # noqa: E402
from atomic_write import write_text                          # noqa: E402
from private_pages import is_private                         # noqa: E402

SIDEBAR = ROOT / "site" / "sidebar.js"
SITE_MAP = ROOT / "site" / "data" / "chat" / "site_map.json"
OUT = ROOT / "site" / "contents.html"

ITEM = re.compile(r"""href:\s*'([^']+)'\s*,\s*label:\s*(?:'([^']*)'|"([^"]*)")""")
SECTION = re.compile(r"\{\s*title:\s*'([^']+)',\s*items:\s*\[(.*?)\]\s*\}\s*,\s*"
                     r"(?=\{\s*title:|\]\s*;)", re.S)

# Pages that belong on this list but not in the sidebar, with why.
# Private pages are NOT here -- see private_pages.PRIVATE. This page used to
# list analytics.html with a note explaining it was kept out of the
# navigation, which advertised the URL to every reader of the contents page.
UNLISTED_NOTE = {
    "/caltech_dashboard.html": "an early one-off, superseded by the IPEDS dashboard",
    "/caltech_field_demographics.html": "an early one-off, by field",
    "/caltech_ipeds_tables.html": "an early one-off, the IPEDS tables behind it",
    "/submit.html": "the tip line, linked from the footer",
    "/webmcp.html": "how a machine client talks to this site",
    "/index.html": "the front page",
    # Both are new and deliberately stand alone: they are not wired into the
    # sidebar, so no existing page changed to make room for them.

}
FILES = [("/executive-brief.pdf", "Executive brief, four pages"),
         ("/briefing.pdf", "The briefing, for printing"),
         ("/briefing-reader.pdf", "The briefing, for reading on screen"),
         ("/catalog.json", "Every dataset, machine-readable"),
         ("/sitemap.xml", "For crawlers"),
         ("/llms.txt", "For machine clients")]


def sections() -> list[tuple[str, list[tuple[str, str]]]]:
    #: sidebar.js now holds TWO navigation trees, because h1b.andy-barr.com
    #: and phd-demographics.andy-barr.com share one bucket and pick their rail
    #: by hostname. This page is the pipeline site's contents, so it reads the
    #: pipeline tree only. Scanning the whole file produced a second "Start
    #: here" and a second "Reference" group, and two blocks with one id means
    #: the browser resolves the first and the second is unreachable.
    src = SIDEBAR.read_text()
    start = src.find("const STEM_SECTIONS = [")
    if start == -1:
        raise SystemExit(
            "sidebar.js has no STEM_SECTIONS array. If the trees were renamed, "
            "fix this parser rather than letting it read both.")
    src = src[start:]
    out = []
    for m in SECTION.finditer(src):
        items = [(h, a or b) for h, a, b in ITEM.findall(m.group(2))]
        out.append((m.group(1), [(h, l) for h, l in items if h.startswith("/")]))
    return out


def _clean(href: str) -> str:
    """A page link without its extension, the way the site now serves them.

    The sidebar dropped .html from every href; the site map and this file's own
    notes still carry the file name. Comparing the two raw made 51 pages look
    absent from the navigation when they were all in it, so both sides are
    normalised before they meet.
    """
    return href[:-5] if href.endswith(".html") else href


def main() -> int:
    secs = sections()
    if not secs:
        print("  could not read any section from sidebar.js")
        return 1
    smap = json.loads(SITE_MAP.read_text()) if SITE_MAP.exists() else {"pages": [], "universities": []}
    titles = {_clean(p["path"]): p.get("title") or p["path"]
              for p in smap.get("pages", [])}
    listed = {_clean(h) for _t, items in secs for h, _l in items}
    unlisted = sorted(p for p in (set(titles) - listed
                                  | {_clean(p) for p in UNLISTED_NOTE
                                     if (ROOT / "site" / p.lstrip("/")).exists()})
                      if not is_private(p))
    unis = smap.get("universities", [])

    def row(href: str, label: str, note: str = "") -> str:
        note = f'<span class="note">{html.escape(note)}</span>' if note else ""
        return (f'    <li><a href="{href}">{html.escape(label)}</a>'
                f'<code>{href}</code>{note}</li>')

    blocks = []
    for title, items in secs:
        rows = "\n".join(row(h, l) for h, l in items)
        blocks.append(f'  <h2 id="{title.lower().replace(" ", "-")}">{html.escape(title)}</h2>\n'
                      f'  <ul class="pages">\n{rows}\n  </ul>')
    rows = "\n".join(row(p, titles.get(p, p.strip("/")), UNLISTED_NOTE.get(p, ""))
                     for p in unlisted)
    blocks.append('  <h2 id="also-on-the-site">Also on the site</h2>\n'
                  '  <p class="lede">Live pages that are not in the navigation, and why.</p>\n'
                  f'  <ul class="pages">\n{rows}\n  </ul>')
    rows = "\n".join(row(h, l) for h, l in FILES)
    blocks.append('  <h2 id="files">Files</h2>\n'
                  f'  <ul class="pages">\n{rows}\n  </ul>')
    uni_links = "\n".join(
        f'    <li><a href="{_clean(u["path"])}">{html.escape(u.get("name") or u["path"])}</a></li>'
        for u in unis if u.get("path"))
    blocks.append(
        f'  <h2 id="universities">Universities</h2>\n'
        f'  <p class="lede">{len(unis)} institutions, each with its dissertation records, '
        f'funding, OPT and H-1B. Every one also has a non-STEM counterpart under '
        f'<code>/universities/nonstem/</code>.</p>\n'
        f'  <ul class="unis">\n{uni_links}\n  </ul>')

    total = sum(len(i) for _t, i in secs) + len(unlisted) + len(unis)
    write_text(OUT, _page("\n\n".join(blocks), total, len(unis)))
    print(f"  wrote {OUT.relative_to(ROOT)}: {total} links "
          f"({sum(len(i) for _t, i in secs)} in the navigation, "
          f"{len(unlisted)} not, {len(unis)} universities)")
    return 0


def _page(body: str, total: int, unis: int) -> str:
    desc = (f"Every page on this site in one list: {total} links, including the "
            f"{unis} university pages and the pages that are not in the navigation.")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Table of contents</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="Table of contents">
<meta property="og:description" content="{desc}">
<link rel="icon" type="image/x-icon" href="/favicon.ico">
<style>
:root{{
  --paper:#ffffff; --panel:#f5f6f8; --ink:#111827; --ink2:#374151; --ink3:#5b6472;
  --rule:#dde1e6; --link:#1d4ed8;
  --bg:var(--paper); --surface:var(--panel); --border:var(--rule);
  --text:var(--ink); --text-muted:var(--ink3); --accent:var(--link);
  color-scheme:light;
}}
@media (prefers-color-scheme: dark){{
  :root:not([data-theme="light"]){{
    --paper:#121418; --panel:#1a1d23; --ink:#e8eaee; --ink2:#c3c8d0; --ink3:#949cab;
    --rule:#2b3038; --link:#93b4ff; color-scheme:dark;
  }}
}}
:root[data-theme="dark"]{{
  --paper:#121418; --panel:#1a1d23; --ink:#e8eaee; --ink2:#c3c8d0; --ink3:#949cab;
  --rule:#2b3038; --link:#93b4ff; color-scheme:dark;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);padding-inline:20px;
  font:400 15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:880px;margin:0 auto;padding-block:48px 80px}}
h1{{font:500 30px/1.2 Charter,Georgia,serif;margin:0 0 10px;letter-spacing:-.01em}}
h2{{font:600 12px/1.3 inherit;letter-spacing:.12em;text-transform:uppercase;
  color:var(--ink3);margin:38px 0 10px;padding-bottom:8px;border-bottom:1px solid var(--rule)}}
.intro{{color:var(--ink2);font:400 17px/1.6 Charter,Georgia,serif;max-width:64ch;margin:0 0 8px}}
.lede{{color:var(--ink3);font-size:13.5px;max-width:72ch;margin:0 0 12px}}
ul{{list-style:none;margin:0;padding:0}}
.pages li{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;
  padding:7px 0;border-bottom:1px solid var(--rule)}}
.pages li:last-child{{border-bottom:0}}
.pages a{{color:var(--link);text-decoration:none;font-weight:500}}
.pages a:hover{{text-decoration:underline}}
.pages code{{color:var(--ink3);font:400 12px/1 "SF Mono",Menlo,Consolas,monospace}}
.pages .note{{color:var(--ink3);font-size:12.5px;flex:1 1 100%}}
.unis{{columns:3;column-gap:26px}}
.unis li{{padding:3px 0;break-inside:avoid}}
.unis a{{color:var(--link);text-decoration:none;font-size:14px}}
a:focus-visible{{outline:2px solid var(--link);outline-offset:2px}}
@media (max-width:700px){{.unis{{columns:2}}}}
@media (max-width:460px){{.unis{{columns:1}} h1{{font-size:25px}}}}
</style>
  {BOOT}
  {LOADER}
<link rel="stylesheet" href="/style.css">
</head>
<body data-page="contents">
<main id="main">
<div class="wrap">
  <h1 id="table-of-contents">Table of contents</h1>
  <p class="intro">Every page on this site, grouped the way the navigation
  groups them, plus the pages that are not in the navigation and the files you
  can download. {total} links in all.</p>

{body}
</div>
</main>
<script src="/sidebar.js"></script>
<script src="/anchors.js" defer></script>
<script src="/analytics-beacon.js" defer></script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
