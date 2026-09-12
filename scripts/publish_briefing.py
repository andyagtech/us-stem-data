#!/usr/bin/env python3
"""Host the briefing: both PDFs, and the page that offers the right one.

report/generate.py renders the briefing twice -- once on white paper, once on
dark -- because a PDF cannot follow the reader's theme: its colours are fixed
when the file is written. This copies both into site/ and writes the page that
picks whichever matches the reader, with the other a click away.

The page count is read out of the PDFs rather than assumed, and compared
against the number of page fragments; a mismatch means the hosted PDF is older
than the document and is reported rather than published quietly.

Usage:
  python3 report/generate.py          # renders both PDFs first
  python3 scripts/publish_briefing.py
"""
from __future__ import annotations

import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from add_theme_toggle import BOOT, LOADER                    # noqa: E402
from atomic_write import write_text                          # noqa: E402

REPORTS = Path.home() / "usds_china_reports"
SRC = {"light": REPORTS / "STEM_Pipeline_Briefing.pdf",
       "dark": REPORTS / "STEM_Pipeline_Briefing_dark.pdf"}
DEST = {"light": ROOT / "site" / "briefing.pdf",
        "dark": ROOT / "site" / "briefing-dark.pdf"}
PAGE = ROOT / "site" / "briefing.html"
FRAGMENTS = ROOT / "report" / "pages"


def pdf_pages(raw: bytes) -> int:
    return raw.count(b"/Type /Page") - raw.count(b"/Type /Pages")


def main() -> int:
    missing = [str(p) for p in SRC.values() if not p.exists()]
    if missing:
        print("  missing: " + ", ".join(missing))
        print("  run: python3 report/generate.py")
        return 1

    fragments = len(list(FRAGMENTS.glob("[0-9]*.html")))
    sizes, pages = {}, {}
    for kind, src in SRC.items():
        raw = src.read_bytes()
        pages[kind], sizes[kind] = pdf_pages(raw), len(raw)
        shutil.copy2(src, DEST[kind])
    if pages["light"] != fragments:
        print(f"  the PDF has {pages['light']} pages against {fragments} fragments; "
              "re-run report/generate.py before publishing")
        return 1
    if pages["light"] != pages["dark"]:
        print(f"  light {pages['light']} pages, dark {pages['dark']}; they must match")
        return 1

    n = pages["light"]
    mb = sizes["light"] / 1024 ** 2
    built = date.fromtimestamp(SRC["light"].stat().st_mtime).strftime("%-d %B %Y")
    write_text(PAGE, _page(n, mb, built))
    print(f"  wrote {PAGE.relative_to(ROOT)} and both PDFs: {n} pages, {mb:.1f} MB")
    return 0


def _page(n: int, mb: float, built: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The briefing</title>
<meta name="description" content="The {n}-page congressional briefing on US graduate
STEM education and the immigration pipeline, as a PDF, on white paper or dark.">
<meta property="og:title" content="The briefing">
<meta property="og:description" content="{n} pages, built from federal data. Every
figure traceable to a published source.">
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
.wrap{{max-width:880px;margin:0 auto;padding-block:48px 72px}}
h1{{font:500 30px/1.2 Charter,Georgia,serif;margin:0 0 10px;letter-spacing:-.01em}}
.lede{{color:var(--ink2);font:400 17px/1.6 Charter,Georgia,serif;max-width:62ch;margin:0 0 6px}}
.meta{{color:var(--ink3);font-size:13px;font-variant-numeric:tabular-nums;margin:0 0 26px}}
.picks{{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 10px}}
.pick{{display:inline-flex;align-items:center;gap:9px;padding:11px 16px;border-radius:8px;
  border:1px solid var(--rule);background:var(--panel);color:var(--ink);
  text-decoration:none;font-weight:600;font-size:14px}}
.pick:hover{{border-color:var(--link)}}
.pick:focus-visible{{outline:2px solid var(--link);outline-offset:2px}}
.pick[data-match="yes"]{{background:var(--ink);color:var(--paper);border-color:var(--ink)}}
.pick .ic{{font-size:15px}}
.pick .tag{{font-weight:400;font-size:12px;opacity:.75}}
.note{{color:var(--ink3);font-size:13px;margin:0 0 26px;max-width:70ch}}
.frame{{border:1px solid var(--rule);border-radius:8px;overflow:hidden;background:var(--panel)}}
.frame iframe{{display:block;width:100%;height:min(78vh,900px);border:0}}
.after{{color:var(--ink3);font-size:13px;margin:14px 0 0}}
.after a{{color:var(--link)}}
@media (max-width:560px){{h1{{font-size:24px}} .frame iframe{{height:60vh}}}}
</style>
  {BOOT}
  {LOADER}
</head>
<body data-page="briefing">
<main id="main">
<div class="wrap">
  <h1 id="the-briefing">The briefing</h1>
  <p class="lede">{n} pages on US graduate STEM education and the immigration
  pipeline, built entirely from federal statistical sources. Every figure is
  traceable to a published collection, and the pages that cannot answer
  something say so.</p>
  <p class="meta">{n} pages &middot; {mb:.1f} MB &middot; built {built}</p>

  <div class="picks">
    <a class="pick" id="pick-light" href="/briefing.pdf" data-track="pdf.light">
      <span class="ic" aria-hidden="true">&#9788;</span>On white paper
      <span class="tag" id="tag-light"></span></a>
    <a class="pick" id="pick-dark" href="/briefing-dark.pdf" data-track="pdf.dark">
      <span class="ic" aria-hidden="true">&#9790;</span>On dark paper
      <span class="tag" id="tag-dark"></span></a>
  </div>
  <p class="note">A PDF's colours are fixed when the file is written, so it
  cannot follow your theme the way the rest of the site does. Both renderings
  hold the same {n} pages and the same figures.</p>

  <div class="frame">
    <iframe id="viewer" title="The briefing" src="/briefing.pdf"></iframe>
  </div>
  <p class="after">Prefer it as a web page? The same material is on this site,
  starting at <a href="/overview.html">the overview</a>, with the slides at
  <a href="/presentation.html">the presentation</a> and the data requests at
  <a href="/data_requests.html">federal data requests</a>.</p>
</div>
</main>
<script>
(function () {{
  var light = document.getElementById('pick-light'),
      dark = document.getElementById('pick-dark'),
      viewer = document.getElementById('viewer');
  function effective() {{
    if (window.__phdTheme) return window.__phdTheme.effective();
    return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }}
  function paint() {{
    var isDark = effective() === 'dark';
    light.dataset.match = isDark ? 'no' : 'yes';
    dark.dataset.match = isDark ? 'yes' : 'no';
    document.getElementById('tag-light').textContent = isDark ? '' : 'matches your theme';
    document.getElementById('tag-dark').textContent = isDark ? 'matches your theme' : '';
    var want = isDark ? '/briefing-dark.pdf' : '/briefing.pdf';
    // Only reload when it actually changes: re-setting src restarts the
    // viewer and throws the reader back to page one.
    if (viewer.getAttribute('src') !== want) viewer.setAttribute('src', want);
  }}
  paint();
  document.addEventListener('themechange', paint);
}})();
</script>
<script src="/sidebar.js"></script>
<script src="/anchors.js" defer></script>
<script src="/analytics-beacon.js" defer></script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
