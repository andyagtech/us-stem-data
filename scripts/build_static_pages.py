#!/usr/bin/env python3
"""
Build per-university SEO pages by cloning stem.html and injecting an
auto-load directive for each university.

Strategy:
- stem.html is the full SPA (272KB) with all toggles, panels, charts, JS.
- We make 101 copies, one per university, each with:
  - <title>, <meta description>, <link rel="canonical"> set for that uni
  - A small inline script that calls showUni('{key}') on page load
  - The pre-rendered department list inlined for SEO crawlers (so Google
    sees the content without running JS)
- This gives us:
  - SEO: each uni has its own URL with full <title>, og tags, indexable HTML
  - Functionality: full SPA with all toggles + panels works on each page
  - No JSON fetch round-trip: data preloaded into UNI_CACHE before showUni()

Output: site/universities/{key}.html for STEM
"""
import json
import os
import re
import sys
from html import escape as _esc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from og import tags as og_tags
from atomic_write import write_text

ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "site"
DATA_DIR = SITE_DIR / "data"
UNIVERSITIES_DIR = SITE_DIR / "universities"
STEM_HTML = SITE_DIR / "stem.html"
NONSTEM_HTML = SITE_DIR / "non_stem.html"


def esc(s):
    return _esc(str(s) if s is not None else "")


def render_seo_content(uni):
    """Render a minimal pre-rendered department/year list for crawlers.
    The SPA will replace this when JS runs (via showUni → renderUni).
    """
    records = uni.get("records", [])
    name = uni.get("name", "")
    nra = uni.get("nra", 0)
    record_count = len(records)

    # Group records by department
    dept_map = {}
    for r in records:
        d = r[0] if len(r) > 0 else ""
        dept_map.setdefault(d, []).append(r)

    # Pick top 5 departments by record count
    top_depts = sorted(dept_map.items(), key=lambda x: -len(x[1]))[:5]

    parts = [
        f'<noscript><h2>{esc(name)} — {record_count:,} records</h2>',
        f'<p>NRA = Non-Resident Alien. {nra}% share of STEM doctoral completions (IPEDS).</p>',
    ]

    for dept, recs in top_depts:
        parts.append(f'<h3>{esc(dept)} ({len(recs)} records)</h3><ul>')
        # Show first 20 names per dept for crawlers
        for r in recs[:20]:
            name_str = esc(r[2] if len(r) > 2 else "")
            year = r[1] if len(r) > 1 else ""
            title = esc(r[5] if len(r) > 5 else "")
            url = r[6] if len(r) > 6 else ""
            if url:
                parts.append(f'<li>{year}: <a href="{esc(url)}">{name_str}</a> — {title}</li>')
            else:
                parts.append(f'<li>{year}: {name_str} — {title}</li>')
        parts.append("</ul>")

    parts.append("</noscript>")
    return "\n".join(parts)


def build_university_page(key: str, mode: str, source_html: str):
    """Build a static page for one university by cloning the SPA HTML."""
    json_path = DATA_DIR / mode / f"{key}.json"
    if not json_path.exists():
        return None

    with open(json_path) as f:
        uni = json.load(f)

    if not uni.get("records"):
        return None

    name = uni.get("name", key)
    nra = uni.get("nra", 0)
    record_count = len(uni.get("records", []))
    field = "STEM" if mode == "stem" else "non-STEM"
    description = (
        f"{name}: {record_count:,} {field} thesis and dissertation records. "
        f"NRA share of {field} doctoral completions: {nra}%. "
        f"Tracked from institutional repository data, enriched with IPEDS, NSF, DOL, DHS, and State Department federal data."
    )

    # Non-STEM pages live under /universities/nonstem/, so their canonical and
    # og:url must say so — pointing them at the STEM URL told crawlers the two
    # were the same page.
    sub = "" if mode == "stem" else "nonstem/"
    page_url = f"https://phd-demographics.andy-barr.com/universities/{sub}{key}.html"

    # Clone the SPA HTML and modify
    html = source_html

    # Update <title>
    html = re.sub(
        r"<title>[^<]*</title>",
        lambda m: f"<title>{esc(name)} — PhD Demographics</title>",
        html,
        count=1,
    )

    # Update meta description
    html = re.sub(
        r'<meta name="description" content="[^"]*"',
        lambda m: f'<meta name="description" content="{esc(description)}"',
        html,
        count=1,
    )

    # Replace the source page's OpenGraph block (cloned from stem.html) with
    # this university's own: its title, its description, and its own share card
    # at /og/universities[/nonstem]/<key>.png. Previously every clone inherited
    # stem.html's tags and a single site-wide og-image.png.
    html = og_tags.wire_html(
        html,
        title=f"{name} — {'STEM' if mode == 'stem' else 'Non-STEM'} doctorate demographics",
        desc=description,
        img_url=og_tags.card_url(og_tags.card_rel_for_page(
            f"universities/{sub}{key}.html")),
        page_url=page_url,
        alt=f"{name} — NRA share of {'STEM' if mode == 'stem' else 'non-STEM'} "
            f"research doctorates against the national average",
    )

    # Add canonical link (insert before </head>)
    canonical = f'<link rel="canonical" href="{page_url}">'
    if "<link rel=\"canonical\"" not in html:
        html = html.replace("</head>", f"{canonical}\n</head>", 1)
    else:
        html = re.sub(
            r'<link rel="canonical" href="[^"]*">',
            canonical,
            html,
            count=1,
        )

    # Inline the university data into UNI_CACHE so showUni() doesn't need to fetch
    uni_json = json.dumps(uni, separators=(",", ":"))
    auto_load_script = (
        f'<script>'
        f'window._preloadedUniKey = "{key}";'
        f'window._preloadedUniData = {uni_json};'
        f'</script>'
    )

    # Inject the auto-load script + SEO content right before the main JS
    seo_html = render_seo_content(uni)
    injection = f"{auto_load_script}\n{seo_html}\n"

    # Insert SEO noscript content right after <body class="...">
    seo_replacement = seo_html  # avoid escape sequences in replacement
    html = re.sub(
        r"(<body[^>]*>)",
        lambda m: m.group(1) + "\n" + seo_replacement,
        html,
        count=1,
    )

    # Rewrite DATA_DIR from relative ('data/stem') to absolute ('/data/stem')
    # so fetches work from /universities/{key}.html
    html = html.replace(
        "const DATA_DIR = 'data/stem';",
        "const DATA_DIR = '/data/stem';",
    )
    html = html.replace(
        "const DATA_DIR = 'data/nonstem';",
        "const DATA_DIR = '/data/nonstem';",
    )

    # Rewrite sidebar links: javascript:void(0) onclick="showUni('mit')"
    # → href="/universities/mit.html" so users navigate cross-page
    html = re.sub(
        r"<a href=\"javascript:void\(0\)\" class=\"nav-item\" data-key=\"([a-z0-9_]+)\" onclick=\"showUni\('[a-z0-9_]+'\);\">",
        lambda m: f'<a href="/universities/{m.group(1)}.html" class="nav-item" data-key="{m.group(1)}">',
        html,
    )

    # Rewrite other sidebar nav links to absolute paths
    # immigration.html → /immigration.html, etc.
    for relpage in ["immigration.html", "pipeline.html", "data_sources.html",
                     "ipeds_dashboard.html", "india.html", "china.html",
                     "canada.html", "uk.html", "eu.html", "mexico.html",
                     "vwp.html", "query.html", "data_catalog.json", "llms.txt",
                     "stem.html", "non_stem.html", "index.html"]:
        html = html.replace(
            f'href="{relpage}"',
            f'href="/{relpage}"',
        )

    # Fix asset paths (favicon, arabic flag svg, og images) — only relative ones
    for asset in ["favicon.ico", "favicon-32x32.png", "favicon-16x16.png",
                  "apple-touch-icon.png", "arabic_language_flag.svg",
                  "og-image.png"]:
        html = html.replace(f'href="{asset}"', f'href="/{asset}"')
        html = html.replace(f'src="{asset}"', f'src="/{asset}"')

    # Inject the auto-load script right before the main <script> block
    # Find the first script block that contains showUni or DATA = and inject before it
    html = html.replace(
        '<script>\nconst DATA = ',
        f'{auto_load_script}\n<script>\nconst DATA = ',
        1,
    )

    # Add an auto-load IIFE at the end of the body
    auto_load_iife = """
<script>
// Auto-load preloaded university on page load
(function() {
  if (window._preloadedUniKey && window._preloadedUniData) {
    if (typeof UNI_CACHE !== 'undefined') {
      UNI_CACHE[window._preloadedUniKey] = window._preloadedUniData;
    }
    // Wait for DOMContentLoaded to ensure showUni is defined
    function load() {
      if (typeof showUni === 'function') {
        showUni(window._preloadedUniKey, true);
      } else {
        setTimeout(load, 50);
      }
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', load);
    } else {
      load();
    }
  }
})();
</script>
"""
    html = html.replace("</body>", auto_load_iife + "\n</body>", 1)

    out_dir = UNIVERSITIES_DIR if mode == "stem" else (UNIVERSITIES_DIR / "nonstem")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{key}.html"
    write_text(out_path, html)
    return out_path


def build_sitemap(stem_keys, nonstem_keys):
    """Build sitemap.xml with all university pages."""
    base = "https://phd-demographics.andy-barr.com"
    urls = [
        f"{base}/",
        f"{base}/stem.html",
        f"{base}/non_stem.html",
        f"{base}/immigration.html",
        f"{base}/pipeline.html",
        f"{base}/india.html",
        f"{base}/china.html",
        f"{base}/canada.html",
        f"{base}/uk.html",
        f"{base}/eu.html",
        f"{base}/mexico.html",
        f"{base}/vwp.html",
        f"{base}/ipeds_dashboard.html",
        f"{base}/data_sources.html",
        f"{base}/query.html",
    ]
    for key in stem_keys:
        urls.append(f"{base}/universities/{key}.html")
    for key in nonstem_keys:
        urls.append(f"{base}/universities/nonstem/{key}.html")

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for url in urls:
        xml.append(f"<url><loc>{url}</loc></url>")
    xml.append("</urlset>")

    sitemap_path = SITE_DIR / "sitemap.xml"
    write_text(sitemap_path, "\n".join(xml))
    print(f"  Sitemap: {len(urls)} URLs → {sitemap_path}")


def main():
    print("Building static university pages (full SPA clones)...")
    UNIVERSITIES_DIR.mkdir(parents=True, exist_ok=True)

    if not STEM_HTML.exists():
        print(f"  ERROR: {STEM_HTML} not found. Run generate step first.")
        return

    stem_html_source = STEM_HTML.read_text()
    nonstem_html_source = NONSTEM_HTML.read_text() if NONSTEM_HTML.exists() else stem_html_source

    stem_keys = []
    nonstem_keys = []

    for mode, source in (("stem", stem_html_source), ("nonstem", nonstem_html_source)):
        mode_dir = DATA_DIR / mode
        if not mode_dir.is_dir():
            continue

        built = 0
        skipped = 0
        for jf in sorted(mode_dir.glob("*.json")):
            if jf.name.startswith("_"):
                continue
            key = jf.stem
            try:
                result = build_university_page(key, mode, source)
                if result:
                    built += 1
                    if mode == "stem":
                        stem_keys.append(key)
                    else:
                        nonstem_keys.append(key)
                else:
                    skipped += 1
            except Exception as e:
                print(f"  ERROR {key}: {e}")
                skipped += 1

        out = UNIVERSITIES_DIR if mode == "stem" else (UNIVERSITIES_DIR / "nonstem")
        if out.exists():
            total_size = sum(f.stat().st_size for f in out.glob("*.html"))
            print(f"  {mode}: built {built}, skipped {skipped} ({total_size/1024/1024:.1f} MB)")

    build_sitemap(stem_keys, nonstem_keys)
    print("Done.")


if __name__ == "__main__":
    main()