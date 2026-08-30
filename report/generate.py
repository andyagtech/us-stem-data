#!/usr/bin/env python3
"""Assemble the briefing from page fragments and render the PDF.

THE POINT OF THIS FILE. An earlier version of the generator lived in a
scratch directory and was destroyed when that directory was cleared. Every
page now lives under report/pages/ in the repository, numbered in render
order, and this script assembles them. Nothing about the report exists
outside version control any more.

Pages are ordinary HTML fragments. New ones can be written by hand or
generated from data by a builder in report/builders.py; either way they land
in report/pages/ and are committed.

Numbering is derived, never typed. Inserting a page shifts every footer,
section heading and in-text cross-reference after it, and doing that by hand
is how a document ends up with two page 9s and a reference pointing at the
wrong one. This script renumbers all three from render order on every build.

Usage:
  python3 report/generate.py            # rebuild HTML and PDF
  python3 report/generate.py --html     # skip the PDF
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "report" / "pages"
OUT_HTML = ROOT / "report" / "briefing.html"
OUT_PDF = Path.home() / "usds_china_reports" / "STEM_Pipeline_Briefing.pdf"
SITE = "https://phd-demographics.andy-barr.com"

FOOT = ('<div class="pagefoot"><span><a href="{site}">{host}</a></span>'
        '<span>Page {n} of {total}</span></div>')


def renumber_files() -> int:
    """Rewrite page filenames into a clean 01..NN sequence.

    Inserting a page means picking a filename, and picking one that sorts
    correctly next to its neighbours is fiddly -- "12_the-route" sorts before
    "12_two-petitions" when the intent was the reverse. This normalises the
    prefixes to the current sort order so the next insertion only has to land
    in roughly the right place. Renames go through temporary names, or a
    rename can clobber a file not yet moved.
    """
    files = page_files()
    staged = []
    for i, src in enumerate(files, start=1):
        stem = re.sub(r"^\d+[a-z]?_", "", src.name)
        tmp = src.with_name(f"tmp_{i:03d}.html")
        src.rename(tmp)
        staged.append((tmp, src.with_name(f"{i:02d}_{stem}")))
    renamed = {}
    for tmp, dst in staged:
        tmp.rename(dst)
    for (src, _t), (_tmp, dst) in zip(zip(files, staged), staged):
        if src.name != dst.name:
            renamed[src.name] = dst.name
    # A builder still writing the pre-renumber filename recreates the page
    # under its old name, and the document silently gains a duplicate. Point
    # the builders at where their pages actually live.
    b = ROOT / "report" / "builders.py"
    if renamed and b.exists():
        text = orig = b.read_text()
        for old_name, new_name in renamed.items():
            text = text.replace(f'write("{old_name}"', f'write("{new_name}"')
        if text != orig:
            b.write_text(text)
            print(f"  repointed {sum(1 for o, n in renamed.items() if o != n)} "
                  f"builder path(s) in report/builders.py")
    print(f"  renumbered {len(staged)} pages")
    return 0


def page_files() -> list[Path]:
    files = sorted(p for p in PAGES.glob("*.html") if not p.name.startswith("_"))
    # Two files with the same slug means one page is in the document twice --
    # normally a builder that kept writing its pre-renumber filename.
    seen = {}
    for f in files:
        slug = re.sub(r"^\d+[a-z]?_", "", f.name)
        if slug in seen:
            raise SystemExit(f"  duplicate page: {seen[slug]} and {f.name} "
                             f"are both '{slug}' -- delete one")
        seen[slug] = f.name
    return files


def renumber(fragments: list[str]) -> list[str]:
    """Footers and section numbers follow render order, not what was typed."""
    total = len(fragments)
    out, section = [], 0
    for n, frag in enumerate(fragments, start=1):
        foot = FOOT.format(site=SITE, host=SITE.split("//")[1], n=n, total=total)
        if 'class="pagefoot"' in frag:
            # Rewrite the number in place. Replacing the whole footer element
            # depended on it being the last thing in the fragment, and two
            # pages that had a stray newline after it silently kept their old
            # numbers -- "2 of 15" in a nineteen-page document.
            frag, count = re.subn(r"Page \d+ of \d+", f"Page {n} of {total}", frag)
            assert count == 1, f"page {n}: expected one footer, found {count}"
        else:
            frag = frag.rstrip()
            assert frag.endswith("</div>"), f"page {n} is not a closed div"
            frag = frag[: -len("</div>")] + foot + "</div>"
        m = re.search(r'class="eyebrow">(\d+)\.\s*([^<]*)', frag)
        if m:
            if "continued" not in m.group(2).lower():
                section += 1
            frag = re.sub(r'(class="eyebrow">)\d+\.', rf"\g<1>{section}.", frag, count=1)
        out.append(frag)
    return out


def resolve_crossrefs(html: str, fragments: list[str]) -> str:
    """Rewrite "on page N" using anchors, so references cannot rot.

    A fragment may carry <!-- ref:name --> to claim a name, and prose may
    write {{page:name}} to point at it. Literal "page 7" survives untouched
    for anything not yet converted, which is most of the original text.
    """
    index = {}
    for n, frag in enumerate(fragments, start=1):
        for name in re.findall(r"<!--\s*ref:([a-z0-9_-]+)\s*-->", frag):
            index[name] = n
    def sub(m):
        name = m.group(1)
        if name not in index:
            raise SystemExit(f"  unknown page reference: {{{{page:{name}}}}}")
        return str(index[name])
    return re.sub(r"\{\{page:([a-z0-9_-]+)\}\}", sub, html)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", action="store_true", help="skip the PDF")
    ap.add_argument("--renumber", action="store_true",
                    help="normalise page filenames to 01..NN, then build")
    args = ap.parse_args()

    if args.renumber:
        renumber_files()
    files = page_files()
    if not files:
        print(f"  no page fragments in {PAGES.relative_to(ROOT)}")
        return 1
    fragments = renumber([f.read_text() for f in files])
    css = (PAGES / "_style.css").read_text()
    title = (PAGES / "_title.txt").read_text().strip()
    body = "\n".join(fragments)
    # Without a viewport tag iOS assumes a 980px desktop page and scales the
    # whole thing down, so every sheet arrives shrunk and unreadable. The
    # print layout is unaffected: @page governs the PDF.
    html = (f'<!doctype html><html><head><meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{title}</title>\n<style>{css}</style></head><body>\n"
            f"{body}\n</body></html>\n")
    html = resolve_crossrefs(html, fragments)
    OUT_HTML.write_text(html)
    print(f"  {len(files)} pages -> {OUT_HTML.relative_to(ROOT)}")

    if args.html:
        return 0
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        pg.goto(OUT_HTML.as_uri(), wait_until="networkidle", timeout=90000)
        OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
        pg.pdf(path=str(OUT_PDF), format="Letter", print_background=False,
               prefer_css_page_size=True)
        b.close()
    raw = OUT_PDF.read_bytes()
    rendered = raw.count(b"/Type /Page") - raw.count(b"/Type /Pages")
    print(f"  PDF: {rendered} pages, {len(raw)/1024:.0f} KB -> {OUT_PDF}")
    if rendered != len(files):
        print(f"  WARNING: {len(files)} fragments produced {rendered} PDF pages; "
              "a page is overflowing")
        for name in _find_overflowing(html, files, fragments):
            print(f"    overflows: {name}")
        return 1
    return 0


def _find_overflowing(html: str, files, fragments) -> list[str]:
    """Name the fragments that need more than one sheet.

    The count alone says a page overflows but not which, which means trimming
    by guesswork. Each fragment is re-rendered on its own -- the page box is
    fixed by @page, so a fragment that needs two sheets alone needs two in the
    document. Cross-references are already resolved in `fragments`.
    """
    from playwright.sync_api import sync_playwright
    probe = PAGES / "_overflow_probe.html"
    head = html[:html.index("<body>") + 6]
    over = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            for f, frag in zip(files, fragments):
                probe.write_text(f"{head}\n{frag}\n</body></html>\n")
                pg.goto(probe.resolve().as_uri(), wait_until="networkidle",
                        timeout=60000)
                pdf = pg.pdf(format="Letter", print_background=False,
                             prefer_css_page_size=True)
                if pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages") != 1:
                    over.append(f.name)
            b.close()
    except Exception as e:                      # diagnostic only, never fatal
        print(f"    (could not isolate: {e})")
    finally:
        probe.unlink(missing_ok=True)
    return over


if __name__ == "__main__":
    sys.exit(main())
