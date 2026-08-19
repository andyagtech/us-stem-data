#!/usr/bin/env python3
"""The OpenGraph / Twitter meta block, and idempotent injection of it.

Shared by scripts/build_og_cards.py and by the page generators
(scripts/build_static_pages.py, scripts/generate_name_lists_html.py) so there
is exactly one definition of what the block looks like. A generated page that
is rebuilt keeps a correct block without having to re-run the card build.

The block is fenced by HTML comments. Injection removes any previous fenced
block *and* any loose og:/twitter: tags a page carried before, then writes one
canonical block — so running it twice produces identical bytes.

Absolute URLs throughout: Facebook, X and Slack all fetch og:image from their
own servers with no page context, so a relative path resolves to nothing.
"""
import re
from html import escape as _esc

DOMAIN = "https://phd-demographics.andy-barr.com"
CARD_W, CARD_H = 1200, 630

MARK_OPEN = "<!-- og:cards -->"
MARK_CLOSE = "<!-- /og:cards -->"

_STRIP = re.compile(
    r'[ \t]*<meta\s+(?:property|name)="(?:og:(?:title|description|image|image:width|'
    r'image:height|image:type|image:alt|image:secure_url|url|type|site_name)|'
    r'twitter:(?:card|title|description|image|image:alt|image:src|site|creator))"'
    r'[^>]*>[ \t]*\r?\n?', re.I)
_BLOCK = re.compile(re.escape(MARK_OPEN) + r".*?" + re.escape(MARK_CLOSE) + r"\r?\n?", re.S)


def card_url(rel_png: str) -> str:
    """'og/universities/mit.png' -> absolute URL."""
    return f"{DOMAIN}/{rel_png.lstrip('/')}"


def card_rel_for_page(rel_page: str) -> str:
    """Map a page path to its card path, mirroring the site's URL structure.

        index.html                     -> og/index.png
        universities/mit.html          -> og/universities/mit.png
        universities/nonstem/mit.html  -> og/universities/nonstem/mit.png

    Deterministic and reversible: strip .html, add .png, prefix og/. No hash,
    counter or timestamp is involved, so a rebuild yields identical names.
    """
    rel_page = rel_page.lstrip("/")
    if rel_page.endswith(".html"):
        rel_page = rel_page[:-len(".html")]
    return f"og/{rel_page}.png"


def meta_block(title, desc, img_url, page_url, alt, og_type="website"):
    t, d, a = (_esc(str(x), quote=True) for x in (title, desc, alt))
    lines = [
        MARK_OPEN,
        f'<meta property="og:title" content="{t}">',
        f'<meta property="og:description" content="{d}">',
        f'<meta property="og:url" content="{page_url}">',
        f'<meta property="og:type" content="{og_type}">',
        '<meta property="og:site_name" content="PhD Demographics">',
        f'<meta property="og:image" content="{img_url}">',
        f'<meta property="og:image:secure_url" content="{img_url}">',
        '<meta property="og:image:type" content="image/png">',
        f'<meta property="og:image:width" content="{CARD_W}">',
        f'<meta property="og:image:height" content="{CARD_H}">',
        f'<meta property="og:image:alt" content="{a}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{t}">',
        f'<meta name="twitter:description" content="{d}">',
        f'<meta name="twitter:image" content="{img_url}">',
        f'<meta name="twitter:image:alt" content="{a}">',
        MARK_CLOSE,
    ]
    return "\n".join(lines)


def wire_html(html, title, desc, img_url, page_url, alt, og_type="website"):
    """Return html with exactly one canonical OG block in <head>."""
    html = _BLOCK.sub("", html)
    html = _STRIP.sub("", html)
    block = meta_block(title, desc, img_url, page_url, alt, og_type) + "\n"
    if "</head>" in html:
        return html.replace("</head>", block + "</head>", 1)
    return re.sub(r"(<meta charset=[^>]*>\s*)", r"\1" + block, html, count=1)


def wire_file(path, title, desc, img_url, page_url, alt, og_type="website"):
    """Rewrite a file in place. Returns True if the bytes changed."""
    before = path.read_text()
    after = wire_html(before, title, desc, img_url, page_url, alt, og_type)
    if after != before:
        path.write_text(after)
        return True
    return False


# ---------------------------------------------------------------------------
# Meta for the pages that a generator owns.
#
# scripts/generate_name_lists_html.py writes stem.html and non_stem.html from
# scratch on every run, so it needs the same title/description strings that
# scripts/build_og_cards.py puts on their cards. Keeping the strings here means
# there is one definition and the two cannot drift.
# ---------------------------------------------------------------------------

GENERATED_PAGE_META = {
    "stem": (
        "Who Earns America's STEM Doctorates",
        "369,530 STEM thesis and dissertation records from 105 university "
        "repositories, each name linked back to its source.",
        "Who earns America’s STEM doctorates — non-resident STEM doctorates "
        "awarded, 2010–2024",
    ),
    "non_stem": (
        "Non-STEM Theses from 105 Universities",
        "148,185 education, humanities and social-science dissertation records, "
        "set against the national non-resident share of non-STEM doctorates.",
        "Non-STEM dissertations, school by school — NRA share of non-STEM "
        "research doctorates",
    ),
}


def generated_page_block(name):
    """The full fenced block for stem.html / non_stem.html."""
    title, desc, alt = GENERATED_PAGE_META[name]
    return meta_block(title, desc, card_url(card_rel_for_page(f"{name}.html")),
                      f"{DOMAIN}/{name}.html", alt)


def university_block(key, mode, title, desc, alt):
    """The full fenced block for a per-university page."""
    sub = "" if mode == "stem" else "nonstem/"
    rel_page = f"universities/{sub}{key}.html"
    return meta_block(title, desc, card_url(card_rel_for_page(rel_page)),
                      f"{DOMAIN}/{rel_page}", alt)
