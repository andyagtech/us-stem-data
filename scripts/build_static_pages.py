#!/usr/bin/env python3
"""
Build static HTML pages for each university (server-side rendered).

For high traffic, we want each university to be its own static HTML file
that CloudFront can cache at the edge with high hit rate. This is a Python
rewrite of the JS `renderUni()` function in generate_name_lists_html.py.

Output: site/universities/{key}.html (for STEM)
        site/universities/nonstem/{key}.html (for non-STEM)

Run: python3 scripts/build_static_pages.py
"""
import json
import os
import re
import sys
from html import escape as _esc
from pathlib import Path

ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "site"
DATA_DIR = SITE_DIR / "data"
UNIVERSITIES_DIR = SITE_DIR / "universities"

# Origin classifications (for badges)
ORIGINS = {
    "chinese": ("🇨🇳", "Chinese", "chinese"),
    "indian": ("🇮🇳", "Indian", "indian"),
    "iranian": ("🇮🇷", "Iranian", "iranian"),
    "korean": ("🇰🇷", "Korean", "korean"),
    "vietnamese": ("🇻🇳", "Vietnamese", "vietnamese"),
    "turkish": ("🇹🇷", "Turkish", "turkish"),
    "arabic": ('<img src="/arabic_language_flag.svg" class="arabic-flag-img" alt="Arabic">', "Arabic", "arabic"),
}
ORIGIN_KEYS = list(ORIGINS.keys())


def esc(s):
    return _esc(str(s) if s is not None else "")


def slug(s):
    """Slugify for HTML id."""
    s = re.sub(r"[^a-zA-Z0-9-]+", "-", str(s)).strip("-").lower()
    return s or "x"


def badge(cls):
    """Origin badge HTML."""
    if cls in ORIGINS:
        flag, label, _ = ORIGINS[cls]
        return f'<span class="flag-badge" title="{label}">{flag}</span>'
    return ""


def degree_badge(d):
    """Degree badge HTML."""
    if d == "phd":
        return '<span class="degree-badge phd">PhD</span>'
    elif d == "ms":
        return '<span class="degree-badge ms">MS</span>'
    return ""


def is_general(dept):
    d = dept.lower()
    return d == "general" or d.endswith("(general)")


def build_name_rows(recs):
    """Build HTML for a list of name rows."""
    parts = []
    for r in recs:
        b = badge(r[3] if len(r) > 3 else "")
        db = degree_badge(r[7] if len(r) > 7 else "")
        title_e = esc(r[5] if len(r) > 5 else "")
        name = r[2] if len(r) > 2 else ""
        url = r[6] if len(r) > 6 else ""
        if url:
            name_el = f'<a href="{esc(url)}" target="_blank" class="name-link">{esc(name)}</a>'
        else:
            name_el = f'<span class="name-nolink">{esc(name)}</span>'
        parts.append(
            f'<div class="name-row"><div class="name-col">{db}{b}{name_el}</div>'
            f'<div class="title-col" title="{title_e}">{title_e}</div></div>'
        )
    return "".join(parts)


def get_repo_base(uni):
    """Extract base institutional repository URL from first record."""
    for r in uni.get("records", [])[:50]:
        if len(r) > 6 and r[6]:
            url = r[6]
            m = re.match(r"https?://[^/]+", url)
            if m:
                return m.group(0)
    return None


def render_university_content(uni):
    """
    Build the main content HTML for a single university.
    Mirrors renderUni() in generate_name_lists_html.py.
    """
    records = uni.get("records", [])
    uni_key = uni.get("key", "")
    uni_slug = slug(uni_key or uni.get("name", ""))

    # Group by department
    dept_map = {}
    for r in records:
        d = r[0] if len(r) > 0 else ""
        dept_map.setdefault(d, []).append(r)

    # Compute stats per dept
    depts = []
    for dept, recs in dept_map.items():
        stats = {"total": len(recs)}
        for o in ORIGIN_KEYS:
            stats[o] = 0
        for r in recs:
            cls = r[3] if len(r) > 3 else ""
            if cls in ORIGINS:
                stats[cls] += 1
        classified = sum(stats[o] for o in ORIGIN_KEYS)
        stats["classifiedPct"] = (classified / len(recs) * 100) if recs else 0
        depts.append({"dept": dept, "recs": recs, "stats": stats})

    # Filter: ≥5 records OR (≥5% classified AND ≥1 record)
    depts = [d for d in depts if d["stats"]["total"] >= 5 or (d["stats"]["classifiedPct"] >= 5 and d["stats"]["total"] >= 1)]

    # Sort: PhD-bearing first, MS-only next, General last
    def sort_key(d):
        gen = 2 if is_general(d["dept"]) else 0
        phds = sum(1 for r in d["recs"] if len(r) > 7 and r[7] == "phd")
        ms_only = 1 if (phds == 0 and d["stats"]["total"] > 0) else 0
        priority = max(gen, ms_only)
        return (priority, -d["stats"]["total"])

    depts.sort(key=sort_key)

    all_total = sum(d["stats"]["total"] for d in depts)
    origin_totals = {o: sum(d["stats"][o] for d in depts) for o in ORIGIN_KEYS}

    # Degree counts
    phd_count = ms_count = unknown_count = 0
    for d in depts:
        for r in d["recs"]:
            deg = r[7] if len(r) > 7 else ""
            if deg == "phd":
                phd_count += 1
            elif deg == "ms":
                ms_count += 1
            else:
                unknown_count += 1

    stats_parts = []
    if phd_count > 0:
        stats_parts.append(f'<span style="color:#4ade80">{phd_count} PhD</span>')
    if ms_count > 0:
        stats_parts.append(f'<span style="color:#fbbf24">{ms_count} MS</span>')
    if unknown_count > 0:
        stats_parts.append(f"{unknown_count} unlabeled")

    origin_parts = []
    for o in ORIGIN_KEYS:
        if origin_totals[o] > 0:
            flag, label, _ = ORIGINS[o]
            origin_parts.append(f"{flag} {origin_totals[o]} {label}")

    repo_base = get_repo_base(uni)
    repo_link = (
        f' &middot; <a href="{esc(repo_base)}" target="_blank" '
        'style="color:var(--accent);text-decoration:none;font-size:0.8rem;">Institutional Repository</a>'
        if repo_base else ""
    )

    name_e = esc(uni.get("name", ""))
    nra = uni.get("nra", 0)

    html = []
    html.append(f'<h2 id="{uni_slug}">{name_e} <span class="uni-nra">IPEDS NRA: {nra}%</span></h2>')

    stats_html = " &middot; ".join(stats_parts)
    html.append(f'<div class="uni-stats">{all_total:,} records across {len(depts)} departments &middot; {stats_html}')
    if origin_parts:
        html.append(f'<span class="uni-origin-stats"> &middot; {" &middot; ".join(origin_parts)}</span>')
    html.append(f"{repo_link}</div>")

    # Toolbar
    html.append('<div style="margin:8px 0 12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">')
    html.append('<button onclick="document.querySelectorAll(\'.dept-section\').forEach(d=>d.classList.remove(\'collapsed\'))" style="background:var(--surface);border:1px solid var(--surface2);color:var(--text-muted);font-size:0.72rem;padding:3px 10px;border-radius:5px;cursor:pointer;">Expand All Departments</button>')
    html.append('<button onclick="document.querySelectorAll(\'.dept-section\').forEach(d=>d.classList.add(\'collapsed\'))" style="background:var(--surface);border:1px solid var(--surface2);color:var(--text-muted);font-size:0.72rem;padding:3px 10px;border-radius:5px;cursor:pointer;">Collapse All</button>')
    html.append('<button onclick="navigator.clipboard.writeText(location.href);this.textContent=\'Copied!\';setTimeout(()=>this.textContent=\'🔗\',1500)" style="background:none;border:none;font-size:0.75rem;cursor:pointer;margin-left:auto;opacity:0.4;" title="Copy link">🔗</button>')
    html.append("</div>")

    # Department sections
    dept_links_data = uni.get("dept_links", {})
    for dept_idx, d in enumerate(depts):
        is_gen = is_general(d["dept"])
        # Group by year
        by_year = {}
        for r in d["recs"]:
            yr = r[1] if len(r) > 1 else 0
            by_year.setdefault(yr, []).append(r)

        year_html_parts = []
        for yr in sorted(by_year.keys(), reverse=True):
            yr_recs = sorted(by_year[yr], key=lambda r: (r[2] if len(r) > 2 else "").lower())
            phd_recs = [r for r in yr_recs if not (len(r) > 7 and r[7] == "ms")]
            ms_recs = [r for r in yr_recs if len(r) > 7 and r[7] == "ms"]

            yr_id = f"{uni_slug}--{slug(d['dept'])}--{yr}"
            old_class = " pre-2010" if isinstance(yr, int) and yr < 2010 else ""

            # MS-only year — only show when MS toggle is on
            if not phd_recs and ms_recs:
                ms_rows = build_name_rows(ms_recs)
                year_html_parts.append(
                    f'<div class="year-block ms-group{old_class}" id="{yr_id}">'
                    f'<div class="year-header" onclick="this.parentElement.classList.toggle(\'yr-collapsed\')">'
                    f'<span class="year-toggle">▼</span>'
                    f'<span style="color:var(--accent);font-weight:700">{yr}</span>'
                    f'&nbsp;&nbsp;{len(ms_recs)} master&apos;s {"theses" if len(ms_recs)!=1 else "thesis"}'
                    f'</div><div class="year-names">{ms_rows}</div></div>'
                )
                continue

            # Year stats for PhD/unlabeled
            yr_counts = {o: 0 for o in ORIGIN_KEYS}
            for r in phd_recs:
                cls = r[3] if len(r) > 3 else ""
                if cls in ORIGINS:
                    yr_counts[cls] += 1
            yr_classified = sum(yr_counts.values())
            yr_pct = (yr_classified / len(phd_recs) * 100) if phd_recs else 0

            yr_badge = []
            for o in ORIGIN_KEYS:
                if yr_counts[o] > 0:
                    flag, _, _ = ORIGINS[o]
                    yr_badge.append(f"{flag}{yr_counts[o]}")

            pct_class = "pct-high" if yr_pct >= 40 else "pct-med" if yr_pct >= 20 else ""

            header_label = f'{len(phd_recs)} dissertation{"s" if len(phd_recs) != 1 else ""}'
            if ms_recs:
                header_label += f'<span class="year-ms-note"> and {len(ms_recs)} master&apos;s {"theses" if len(ms_recs) != 1 else "thesis"}</span>'

            names_html = build_name_rows(phd_recs)

            if ms_recs:
                ms_counts = {o: 0 for o in ORIGIN_KEYS}
                for r in ms_recs:
                    cls = r[3] if len(r) > 3 else ""
                    if cls in ORIGINS:
                        ms_counts[cls] += 1
                ms_classified = sum(ms_counts.values())
                ms_badge = []
                for o in ORIGIN_KEYS:
                    if ms_counts[o] > 0:
                        flag, _, _ = ORIGINS[o]
                        ms_badge.append(f"{flag}{ms_counts[o]}")
                names_html += (
                    f'<div class="ms-group">'
                    f'<div class="ms-group-header" onclick="this.parentElement.classList.toggle(\'collapsed\')">'
                    f'<span class="dept-toggle">▼</span>'
                    f'<span style="color:#fbbf24;font-weight:600;font-size:0.82rem;">'
                    f'{len(ms_recs)} Master&apos;s {"Theses" if len(ms_recs) != 1 else "Thesis"}</span>'
                    f'<span class="year-pct" style="font-size:0.78rem;margin-left:8px;">'
                    f'{" ".join(ms_badge)} &mdash; {ms_classified}/{len(ms_recs)} classified</span>'
                    f'</div><div class="ms-group-body">{build_name_rows(ms_recs)}</div></div>'
                )

            year_html_parts.append(
                f'<div class="year-block{old_class}" id="{yr_id}">'
                f'<div class="year-header" onclick="this.parentElement.classList.toggle(\'yr-collapsed\')">'
                f'<span class="year-toggle">▼</span>'
                f'<span class="year-label">{yr}</span>'
                f'<span class="year-count">{header_label}</span>'
                f'<span class="year-pct {pct_class}">{" ".join(yr_badge)} &mdash; {yr_classified}/{len(phd_recs)} classified ({yr_pct:.0f}%)</span>'
                f'</div><div class="year-names">{names_html}</div></div>'
            )

        # Department badges
        dept_badge_parts = []
        for o in ORIGIN_KEYS:
            if d["stats"][o] > 0:
                flag, _, _ = ORIGINS[o]
                pct = d["stats"][o] / d["stats"]["total"] * 100
                dept_badge_parts.append(f"{flag}{d['stats'][o]} ({pct:.0f}%)")

        d_pct_class = "pct-high" if d["stats"]["classifiedPct"] >= 30 else "pct-med" if d["stats"]["classifiedPct"] >= 20 else ""

        # Collapse: General always, otherwise expand first 5
        collapsed_class = " collapsed" if (is_gen or dept_idx >= 5) else ""
        general_class = " dept-general" if is_gen else ""

        # Department links
        dept_link_html = ""
        dl = dept_links_data.get(d["dept"]) if dept_links_data else None
        if dl:
            if dl.get("home"):
                dept_link_html += f' <a href="{esc(dl["home"])}" target="_blank" onclick="event.stopPropagation()" style="color:var(--accent);font-size:0.75rem;text-decoration:none;" title="Department homepage">Dept</a>'
            if dl.get("faculty"):
                dept_link_html += f' <a href="{esc(dl["faculty"])}" target="_blank" onclick="event.stopPropagation()" style="color:var(--accent);font-size:0.75rem;text-decoration:none;" title="Faculty directory">Faculty</a>'
            if dl.get("students"):
                dept_link_html += f' <a href="{esc(dl["students"])}" target="_blank" onclick="event.stopPropagation()" style="color:var(--accent);font-size:0.75rem;text-decoration:none;" title="PhD student directory">Students</a>'
            if dl.get("repo_search"):
                dept_link_html += f' <a href="{esc(dl["repo_search"])}" target="_blank" onclick="event.stopPropagation()" style="color:var(--accent);font-size:0.75rem;text-decoration:none;" title="Search repository">Repo</a>'

        dept_slug_id = f"{uni_slug}--{slug(d['dept'])}"
        html.append(
            f'<div class="dept-section{collapsed_class}{general_class}" id="{dept_slug_id}" data-dept="{esc(d["dept"])}">'
            f'<div class="dept-header" onclick="this.parentElement.classList.toggle(\'collapsed\')">'
            f'<span class="dept-toggle">▼</span>'
            f'<span class="dept-name">{esc(d["dept"])}</span>'
            f'{dept_link_html}'
            f'<span class="dept-stats">{d["stats"]["total"]} records</span>'
            f'<span class="dept-flags">{"  ".join(dept_badge_parts)}</span>'
            f'<span class="dept-pct {d_pct_class}">{d["stats"]["classifiedPct"]:.0f}% classified</span>'
            f'</div>'
            f'<div class="dept-body">{"".join(year_html_parts)}</div></div>'
        )

    return "\n".join(html)


# ===========================================================================
# PAGE TEMPLATE
# ===========================================================================

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="{description}">
<meta property="og:title" content="{name} — PhD Demographics">
<meta property="og:description" content="{description}">
<meta property="og:type" content="website">
<meta property="og:url" content="https://phd-demographics.andy-barr.com/universities/{key}.html">
<link rel="canonical" href="https://phd-demographics.andy-barr.com/universities/{key}.html">
<link rel="icon" type="image/x-icon" href="/favicon.ico">
<title>{name} — PhD Demographics</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
:root {{
  --bg: #0f172a; --surface: #1e293b; --surface2: #334155;
  --text: #e2e8f0; --text-muted: #94a3b8; --accent: #38bdf8;
  --red: #f87171; --orange: #fb923c; --yellow: #fbbf24;
  --green: #4ade80; --blue: #60a5fa;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); }}
.page {{ max-width: 1200px; margin: 0 auto; padding: 24px 32px; }}
h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
h2 {{ font-size: 1.2rem; margin-bottom: 4px; }}
.uni-nra {{ font-size: 0.85rem; color: var(--accent); font-weight: 400; }}
.uni-stats {{ font-size: 0.85rem; color: var(--text-muted); margin-bottom: 16px; }}
.subtitle {{ font-size: 0.78rem; color: var(--text-muted); margin-bottom: 14px; }}
.back-link {{ font-size: 0.82rem; color: var(--accent); text-decoration: none; margin-bottom: 12px; display: inline-block; }}

.dept-section {{ background: var(--surface); border-radius: 8px; margin-bottom: 8px; border: 1px solid var(--surface2); }}
.dept-header {{ padding: 10px 16px; cursor: pointer; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
.dept-header:hover {{ background: var(--surface2); border-radius: 8px; }}
.dept-toggle {{ font-size: 0.7rem; color: var(--text-muted); transition: transform 0.15s; }}
.dept-section.collapsed .dept-toggle {{ transform: rotate(-90deg); }}
.dept-section.collapsed .dept-body {{ display: none; }}
.dept-name {{ font-weight: 600; font-size: 0.9rem; }}
.dept-stats {{ font-size: 0.8rem; color: var(--text-muted); }}
.dept-flags {{ font-size: 0.78rem; flex: 1; }}
.dept-pct {{ font-size: 0.8rem; font-weight: 600; min-width: 110px; text-align: right; }}
.pct-high {{ color: var(--red); }}
.pct-med {{ color: var(--orange); }}
.dept-body {{ padding: 0 16px 12px; }}

.year-block {{ margin-top: 8px; }}
.year-block .year-header {{ cursor: pointer; }}
.year-block.yr-collapsed .year-names {{ display: none; }}
.year-block.yr-collapsed .year-toggle {{ transform: rotate(-90deg); }}
.year-toggle {{ font-size: 0.6rem; color: var(--text-muted); transition: transform 0.15s; display: inline-block; margin-right: 4px; user-select: none; }}
.year-header {{ display: flex; align-items: center; gap: 10px; padding: 4px 0; border-bottom: 1px solid var(--surface2); margin-bottom: 4px; }}
.year-label {{ color: var(--accent); font-weight: 700; }}
.year-count {{ font-size: 0.78rem; color: var(--text-muted); }}
.year-pct {{ font-size: 0.78rem; margin-left: auto; color: var(--text-muted); }}
.year-names {{ padding: 4px 0; }}

.name-row {{ display: grid; grid-template-columns: 280px 1fr; gap: 16px; padding: 2px 0; font-size: 0.82rem; }}
.name-col {{ display: flex; align-items: baseline; gap: 4px; }}
.title-col {{ color: var(--text-muted); font-size: 0.78rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.name-link {{ color: var(--text); text-decoration: none; }}
.name-link:hover {{ color: var(--accent); text-decoration: underline; }}
.name-nolink {{ color: var(--text); }}
.degree-badge {{ font-size: 0.6rem; font-weight: 700; padding: 1px 5px; border-radius: 3px; margin-right: 4px; flex-shrink: 0; }}
.degree-badge.phd {{ background: rgba(74,222,128,0.15); color: var(--green); }}
.degree-badge.ms {{ background: rgba(251,191,36,0.15); color: var(--yellow); }}
.flag-badge {{ font-size: 0.85rem; margin-right: 3px; }}
.arabic-flag-img {{ width: 16px; height: 11px; vertical-align: -1px; }}

.ms-group {{ margin-top: 6px; padding: 4px 0; border-top: 1px solid rgba(251,191,36,0.15); }}
.ms-group.collapsed .ms-group-body {{ display: none; }}
.ms-group.collapsed .dept-toggle {{ transform: rotate(-90deg); }}
.ms-group-header {{ cursor: pointer; padding: 2px 0; }}
.ms-group-body {{ padding: 4px 0 0 16px; }}

.dept-general {{ opacity: 0.7; }}
.year-block.pre-2010 {{ opacity: 0.7; }}

@media (max-width: 700px) {{
  .page {{ padding: 16px; }}
  .name-row {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<div class="page">
  <a href="/stem.html" class="back-link">&larr; Back to All Universities</a>
  <h1>{name}</h1>
  <p class="subtitle">NRA = Non-Resident Alien. {nra}% share of STEM doctoral completions (IPEDS).</p>

  <div id="content">
{content_html}
  </div>
</div>
<script src="/sidebar.js"></script>
<script src="/chat-widget.js"></script>
</body>
</html>
"""


def build_university_page(key: str, mode: str = "stem"):
    """Build a static HTML page for one university."""
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
    description = (
        f"{name}: {record_count:,} thesis and dissertation records. "
        f"NRA share of STEM doctoral completions: {nra}%. "
        f"Tracked from institutional repository data, enriched with IPEDS, NSF, DOL, DHS, and State Department federal data."
    )

    content_html = render_university_content(uni)

    page_html = PAGE_TEMPLATE.format(
        name=esc(name),
        key=esc(key),
        nra=nra,
        description=esc(description),
        content_html=content_html,
    )

    out_dir = UNIVERSITIES_DIR if mode == "stem" else (UNIVERSITIES_DIR / "nonstem")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{key}.html"
    out_path.write_text(page_html)
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
    sitemap_path.write_text("\n".join(xml))
    print(f"  Sitemap: {len(urls)} URLs → {sitemap_path}")


def main():
    print("Building static university pages...")
    UNIVERSITIES_DIR.mkdir(parents=True, exist_ok=True)

    stem_keys = []
    nonstem_keys = []

    for mode in ("stem", "nonstem"):
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
                result = build_university_page(key, mode)
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
