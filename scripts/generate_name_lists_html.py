#!/usr/bin/env python3
"""
Generate an HTML page with clickable name lists for all high-NRA universities.
Each name links directly to the institutional repository for verification.
Flag icons mark identified origins: Chinese, Indian, Iranian, Korean, Vietnamese, Turkish, Arabic.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from name_classifier import classify  # noqa: F401

from generate_name_lists import (
    CONFIGS, load_records,
)

# Origin config: key -> (flag_html, label, css_class)
# Arabic language flag uses the user's custom SVG file
ARABIC_FLAG_HTML = '<img src="arabic_language_flag.svg" class="arabic-flag-img" alt="Arabic">'

ORIGINS = {
    'chinese':    ('\U0001F1E8\U0001F1F3', 'Chinese',    'flag-cn'),
    'indian':     ('\U0001F1EE\U0001F1F3', 'Indian',     'flag-in'),
    'iranian':    ('\U0001F1EE\U0001F1F7', 'Iranian',    'flag-ir'),
    'korean':     ('\U0001F1F0\U0001F1F7', 'Korean',     'flag-kr'),
    'vietnamese': ('\U0001F1FB\U0001F1F3', 'Vietnamese', 'flag-vn'),
    'turkish':    ('\U0001F1F9\U0001F1F7', 'Turkish',    'flag-tr'),
    'arabic':     (ARABIC_FLAG_HTML,        'Arabic',     'flag-ar'),
}

def classification_badge(cat, conf):
    if cat not in ORIGINS:
        return ''
    flag, label, css_class = ORIGINS[cat]
    return f'<span class="flag-badge {css_class}" data-origin="{cat}" title="{label}">{flag}</span>'


def build_html(all_data, mode='stem'):
    """Build an HTML page with JSON data blob and client-side rendering.
    Only renders one university at a time for performance.
    mode: 'stem' or 'non-stem'"""
    import json
    is_nonstem = mode == 'non-stem'

    # Build lightweight index (no records — those are fetched on demand)
    all_data_sorted = sorted(all_data, key=lambda x: x[2], reverse=True)
    data_dir = 'data/nonstem' if is_nonstem else 'data/stem'

    index_unis = []
    nav_items = []
    for uni_key, uni_name, nra, records in all_data_sorted:
        index_unis.append({
            'key': uni_key, 'name': uni_name, 'nra': nra,
            'count': len(records),
        })
        nav_items.append(
            f'<a href="javascript:void(0)" class="nav-item" data-key="{uni_key}" onclick="showUni(\'{uni_key}\');">'
            f'{uni_name} <span class="nav-nra">{nra}%</span> '
            f'<span class="nav-count">{len(records):,}</span></a>'
        )

    data_json = json.dumps(index_unis, ensure_ascii=False, separators=(',', ':'))

    # Build legend key
    legend_key_items = []
    for o, (flag, label, css_class) in ORIGINS.items():
        legend_key_items.append(f'<span class="legend-key-item">{flag} {label}</span>')

    # Origin keys for JS
    origins_js = json.dumps({k: [v[0], v[1]] for k, v in ORIGINS.items()}, ensure_ascii=False)

    # Load funding data
    funding_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'herd', 'funding_by_university.json')
    funding_json = '{}'
    if os.path.exists(funding_path):
        with open(funding_path) as f:
            funding_json = f.read().strip()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{"Non-STEM " if is_nonstem else ""}Thesis &amp; Dissertation Lists — High NRA Universities</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f172a; --surface: #1e293b; --surface2: #334155;
    --text: #e2e8f0; --text-muted: #94a3b8; --accent: #38bdf8;
    --red: #f87171; --orange: #fb923c; --yellow: #fbbf24;
    --green: #4ade80; --blue: #60a5fa;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); display: flex; min-height: 100vh; }}

  .sidebar {{ width: 220px; background: var(--surface); border-right: 1px solid var(--surface2); padding: 16px 0; position: fixed; top: 0; left: 0; bottom: 0; overflow-y: auto; z-index: 20; }}
  /* Share anchor buttons */
  .share-anchor {{ font-size: 0.6rem; cursor: pointer; text-decoration: none; padding: 2px 4px; border-radius: 3px; opacity: 0.3; transition: opacity 0.15s; }}
  .share-anchor:hover {{ opacity: 1; }}
  .dept-header .share-anchor {{ margin-left: auto; }}
  /* Accessibility: focus indicators */
  a:focus-visible, button:focus-visible, select:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
  .nav-item:focus-visible {{ outline: 2px solid var(--accent); outline-offset: -2px; }}
  .sidebar h3 {{ padding: 0 16px 12px; font-size: 0.85rem; color: var(--accent); }}
  .nav-item {{ display: block; padding: 8px 16px; color: var(--text-muted); text-decoration: none; font-size: 0.85rem; border-left: 3px solid transparent; transition: all 0.1s; }}
  .nav-item:hover {{ background: var(--surface2); color: var(--text); }}
  .nav-item.active {{ border-left-color: var(--accent); color: var(--accent); background: rgba(56,189,248,0.08); }}
  .nav-nra {{ font-size: 0.7rem; color: var(--text-muted); }}
  .nav-count {{ font-size: 0.65rem; color: var(--text-muted); }}

  .main {{ margin-left: 220px; flex: 1; padding: 24px 32px; max-width: 1200px; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .subtitle {{ color: var(--text-muted); font-size: 0.85rem; margin-bottom: 12px; }}
  h2 {{ font-size: 1.2rem; margin-bottom: 4px; }}
  .uni-nra {{ font-size: 0.85rem; color: var(--accent); font-weight: 400; }}
  .uni-stats {{ font-size: 0.85rem; color: var(--text-muted); margin-bottom: 16px; }}

  .toggle-bar {{ display: flex; align-items: center; gap: 12px; padding: 10px 16px; background: var(--surface); border-radius: 10px; border: 1px solid var(--surface2); margin-bottom: 16px; flex-wrap: wrap; }}
  .toggle-wrap {{ display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; }}
  .toggle-label {{ font-size: 0.82rem; font-weight: 600; color: var(--text); }}
  .toggle-switch {{ position: relative; width: 40px; height: 22px; background: var(--surface2); border-radius: 11px; transition: background 0.2s; flex-shrink: 0; }}
  .toggle-switch::after {{ content: ''; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; background: var(--text-muted); border-radius: 50%; transition: all 0.2s; }}
  .toggle-wrap.active .toggle-switch {{ background: var(--accent); }}
  .toggle-wrap.active .toggle-switch::after {{ left: 21px; background: #fff; }}

  .legend-sep {{ width: 1px; height: 20px; background: var(--surface2); margin: 0 4px; }}
  .legend-key {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
  .legend-key-item {{ font-size: 0.78rem; color: var(--text-muted); white-space: nowrap; }}

  .flag-badge {{ font-size: 0.9rem; margin-right: 5px; display: inline; cursor: default; }}
  .arabic-flag-img {{ width: 18px; height: 13px; vertical-align: -1px; border-radius: 1px; }}
  .flags-hidden .flag-badge {{ display: none !important; }}
  .flags-hidden .dept-flags {{ display: none !important; }}
  .flags-hidden .year-pct {{ display: none !important; }}
  .flags-hidden .dept-pct {{ display: none !important; }}
  .flags-hidden .uni-origin-stats {{ display: none !important; }}
  .flags-hidden .flags-only-legend {{ display: none !important; }}
  .ms-hidden .ms-group {{ display: none !important; }}
  .ms-hidden .year-ms-note {{ display: none !important; }}
  .old-hidden .year-block.pre-2010 {{ display: none !important; }}

  .funding-chart-wrap {{ background: var(--surface); border: 1px solid var(--surface2); border-radius: 10px; padding: 16px; margin-bottom: 16px; display: none; }}
  .funding-chart-wrap.visible {{ display: block; }}
  .funding-chart-wrap h3 {{ font-size: 0.9rem; margin-bottom: 4px; }}
  .funding-chart-wrap .funding-source {{ font-size: 0.75rem; color: var(--text-muted); margin-bottom: 8px; }}
  .funding-chart-wrap .funding-source a {{ color: var(--accent); text-decoration: none; }}
  .funding-chart-wrap canvas {{ max-height: 220px; }}
  .funding-panels {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .funding-panels > div {{ flex: 1; min-width: 280px; }}
  .finance-breakdown {{ margin-top: 12px; }}
  .finance-bar {{ display: flex; height: 28px; border-radius: 6px; overflow: hidden; margin: 8px 0 6px; }}
  .finance-bar > div {{ transition: width 0.3s; }}
  .finance-legend {{ display: flex; flex-wrap: wrap; gap: 10px; font-size: 0.75rem; color: var(--text-muted); }}
  .finance-legend span {{ display: flex; align-items: center; gap: 4px; }}
  .finance-legend .dot {{ width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }}
  .finance-stat {{ font-size: 0.82rem; color: var(--text); margin-top: 6px; }}
  .finance-stat strong {{ color: var(--accent); }}

  .dept-section {{ background: var(--surface); border-radius: 8px; margin-bottom: 8px; border: 1px solid var(--surface2); }}
  .dept-header {{ padding: 10px 16px; cursor: pointer; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
  .dept-header .dept-toggle {{ user-select: none; }}
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
  .year-block .year-header:hover {{ opacity: 0.85; }}
  .year-block.yr-collapsed .year-names {{ display: none; }}
  .year-block.yr-collapsed .year-toggle {{ transform: rotate(-90deg); }}
  .year-toggle {{ font-size: 0.6rem; color: var(--text-muted); transition: transform 0.15s; display: inline-block; margin-right: 4px; user-select: none; }}
  .year-header {{ display: flex; align-items: center; gap: 10px; padding: 4px 0; border-bottom: 1px solid var(--surface2); margin-bottom: 4px; }}
  .year-header .share-anchor {{ margin-left: auto; }}
  .year-label {{ font-weight: 700; font-size: 0.9rem; color: var(--accent); min-width: 40px; }}
  .year-count {{ font-size: 0.8rem; color: var(--text-muted); }}
  .year-pct {{ font-size: 0.8rem; font-weight: 600; }}

  .name-row {{ display: flex; padding: 3px 0; font-size: 0.82rem; gap: 8px; align-items: baseline; }}
  .name-row:hover {{ background: rgba(56,189,248,0.04); }}
  .name-col {{ min-width: 280px; max-width: 340px; display: flex; align-items: baseline; }}
  .name-link {{ color: var(--accent); text-decoration: none; }}
  .name-link:hover {{ text-decoration: underline; }}
  .name-nolink {{ color: var(--text); }}
  .title-col {{ color: var(--text-muted); font-size: 0.78rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 600px; }}

  .toolbar {{ position: sticky; top: 0; z-index: 10; background: var(--bg); padding: 12px 0 8px; }}
  .search-input {{ width: 100%; padding: 8px 14px; background: var(--surface); border: 1px solid var(--surface2); border-radius: 8px; color: var(--text); font-size: 0.9rem; outline: none; margin-bottom: 8px; }}
  .search-input:focus {{ border-color: var(--accent); }}
  .search-input::placeholder {{ color: var(--text-muted); }}
  .search-results {{ font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; display: none; }}
  #content {{ min-height: 200px; }}
  .placeholder-msg {{ color: var(--text-muted); font-size: 0.95rem; padding: 40px 0; }}
  .degree-badge {{ font-size: 0.65rem; font-weight: 700; padding: 1px 4px; border-radius: 3px; margin-right: 4px; vertical-align: 1px; }}
  .degree-phd {{ background: rgba(74,222,128,0.15); color: #4ade80; }}
  .degree-ms {{ background: rgba(251,191,36,0.15); color: #fbbf24; }}

  .ms-group {{ margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--surface2); }}
  .ms-group-header {{ display: flex; align-items: center; gap: 8px; cursor: pointer; padding: 4px 0; }}
  .ms-group-header:hover {{ opacity: 0.85; }}
  .ms-group.collapsed .ms-group-body {{ display: none; }}
  .ms-group.collapsed .dept-toggle {{ transform: rotate(-90deg); }}

  .top-nav {{ position: absolute; top: 16px; right: 16px; display: flex; gap: 8px; z-index: 15; }}
  .top-nav-btn {{ background: var(--surface); border: 1px solid var(--surface2); color: var(--text-muted); font-size: 0.75rem; padding: 4px 10px; border-radius: 6px; cursor: pointer; text-decoration: none; white-space: nowrap; }}
  .top-nav-btn:hover {{ background: var(--surface2); color: var(--text); }}
  .main {{ position: relative; }}

  .info-box {{ background: var(--surface); border: 1px solid var(--surface2); border-radius: 10px; padding: 14px 18px; margin-bottom: 16px; font-size: 0.82rem; color: var(--text-muted); line-height: 1.5; }}
  .info-box a {{ color: var(--accent); text-decoration: none; }}
  .info-box a:hover {{ text-decoration: underline; }}
  .info-box strong {{ color: var(--text); }}
  .info-box summary {{ cursor: pointer; font-weight: 600; color: var(--text); font-size: 0.85rem; }}

  /* Tablet: 601-800px */
  @media (max-width: 800px) {{
    .sidebar {{ position: fixed; left: -260px; width: 260px; transition: left 0.25s; z-index: 100; }}
    .sidebar.open {{ left: 0; }}
    .sidebar-overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 99; }}
    .sidebar.open + .sidebar-overlay {{ display: block; }}
    .main {{ margin-left: 0; padding: 16px 20px; }}
    .mobile-menu-btn {{ display: flex !important; }}
    h1 {{ font-size: 1.1rem; }}
    .subtitle {{ font-size: 0.78rem; }}
    .name-col {{ min-width: 180px; max-width: 240px; }}
    .title-col {{ font-size: 0.75rem; max-width: 400px; }}
    .name-row {{ font-size: 0.8rem; }}
    .toggle-bar {{ padding: 8px 10px; gap: 8px; flex-wrap: wrap; }}
    .toggle-label {{ font-size: 0.75rem; }}
    .dept-header {{ padding: 8px 12px; font-size: 0.82rem; flex-wrap: wrap; }}
    .dept-name {{ font-size: 0.82rem; }}
    .dept-pct {{ min-width: unset; }}
    .dept-flags {{ display: none; }}
    .year-header {{ flex-wrap: wrap; }}
    .funding-panels {{ flex-direction: column; }}
    .funding-panels > div {{ min-width: unset; }}
    .funding-chart-wrap {{ padding: 12px; }}
    .top-nav {{ gap: 6px; }}
    .top-nav-btn {{ font-size: 0.68rem; padding: 3px 8px; }}
    .info-box {{ padding: 10px 14px; font-size: 0.78rem; }}
    .uni-stats {{ font-size: 0.78rem; }}
  }}

  /* Phone: <=600px */
  @media (max-width: 600px) {{
    .main {{ padding: 10px 10px; }}
    h1 {{ font-size: 1rem; }}
    h2 {{ font-size: 1.05rem; }}
    .subtitle {{ font-size: 0.72rem; }}
    .top-nav {{ flex-wrap: wrap; gap: 4px; top: 10px; right: 10px; }}
    .top-nav-btn {{ font-size: 0.62rem; padding: 2px 6px; }}
    .toggle-bar {{ padding: 6px 8px; gap: 6px; flex-wrap: wrap; }}
    .toggle-wrap {{ gap: 4px; }}
    .toggle-switch {{ width: 32px; height: 16px; }}
    .toggle-switch::after {{ width: 12px; height: 12px; top: 2px; left: 2px; }}
    .toggle-wrap.active .toggle-switch::after {{ left: 18px; }}
    .toggle-label {{ font-size: 0.7rem; }}
    .dept-filter-select {{ max-width: 140px; font-size: 0.75rem; }}
    .name-row {{ flex-direction: column; gap: 2px; padding: 3px 0; }}
    .name-col {{ min-width: unset; max-width: unset; width: 100%; }}
    .title-col {{ max-width: unset; width: 100%; white-space: normal; font-size: 0.7rem; line-height: 1.3; }}
    .dept-header {{ padding: 6px 10px; font-size: 0.78rem; gap: 6px; }}
    .dept-stats {{ font-size: 0.72rem; }}
    .dept-pct {{ font-size: 0.72rem; min-width: unset; text-align: left; }}
    .dept-flags {{ display: none; }}
    .dept-body {{ padding: 0 10px 8px; }}
    .year-header {{ gap: 6px; font-size: 0.78rem; }}
    .year-label {{ font-size: 0.82rem; }}
    .year-count {{ font-size: 0.72rem; }}
    .year-pct {{ font-size: 0.68rem; }}
    .uni-stats {{ font-size: 0.72rem; }}
    .uni-nra {{ font-size: 0.72rem; }}
    .funding-chart-wrap {{ padding: 8px; }}
    .funding-chart-wrap h3 {{ font-size: 0.82rem; }}
    .funding-source {{ font-size: 0.68rem; }}
    .share-anchor {{ font-size: 0.55rem; padding: 1px 3px; }}
    .degree-badge {{ font-size: 0.55rem; padding: 0 3px; }}
    .ms-group-header {{ font-size: 0.75rem; }}
    .info-box {{ padding: 8px 10px; font-size: 0.72rem; }}
    canvas {{ max-height: 180px !important; }}
  }}
  /* Coach marks */
  .coach-overlay {{ position: fixed; inset: 0; background: rgba(0,0,0,0.55); z-index: 200; transition: opacity 0.3s; }}
  .coach-highlight {{ position: absolute; z-index: 201; border-radius: 8px; box-shadow: 0 0 0 4px var(--accent), 0 0 20px rgba(56,189,248,0.4); transition: all 0.4s; }}
  .coach-tooltip {{ position: absolute; z-index: 202; background: var(--surface); border: 1px solid var(--accent); border-radius: 10px; padding: 14px 18px; max-width: 280px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); }}
  .coach-tooltip .coach-text {{ font-size: 0.88rem; color: var(--text); line-height: 1.4; }}
  .coach-tooltip .coach-step {{ font-size: 0.7rem; color: var(--text-muted); margin-bottom: 6px; }}
  .coach-tooltip .coach-arrow {{ position: absolute; width: 12px; height: 12px; background: var(--surface); border-left: 1px solid var(--accent); border-top: 1px solid var(--accent); }}
  .coach-tooltip .coach-arrow.left {{ left: -7px; top: 50%; transform: translateY(-50%) rotate(-45deg); }}
  .coach-tooltip .coach-arrow.top {{ top: -7px; left: 30px; transform: rotate(45deg); }}
  .coach-dismiss {{ display: inline-block; margin-top: 10px; background: var(--accent); color: #0f172a; border: none; padding: 5px 14px; border-radius: 5px; font-size: 0.78rem; font-weight: 600; cursor: pointer; }}
  @keyframes coach-pulse {{ 0%,100% {{ box-shadow: 0 0 0 4px var(--accent), 0 0 20px rgba(56,189,248,0.4); }} 50% {{ box-shadow: 0 0 0 8px var(--accent), 0 0 30px rgba(56,189,248,0.6); }} }}
  .coach-highlight {{ animation: coach-pulse 1.5s ease-in-out infinite; }}

  .mobile-menu-btn {{ display: none; position: fixed; bottom: 16px; left: 16px; z-index: 98; background: var(--accent); color: #0f172a; border: none; border-radius: 50%; width: 48px; height: 48px; font-size: 1.3rem; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.3); align-items: center; justify-content: center; }}

  /* General dept visual distinction */
  .dept-section.dept-general {{ border-style: dashed; opacity: 0.85; }}
  .dept-section.dept-general .dept-name {{ font-style: italic; }}
  .dept-section.dept-general .dept-name::after {{ content: ' (uncategorized)'; font-size: 0.75rem; color: var(--text-muted); font-weight: 400; }}

  /* Department filter */
  .dept-filter-select {{ background: var(--surface); border: 1px solid var(--surface2); border-radius: 8px; color: var(--text); font-size: 0.82rem; padding: 6px 10px; outline: none; max-width: 220px; cursor: pointer; }}
  .dept-filter-select:focus {{ border-color: var(--accent); }}

  .nav-item-wrap {{ display: flex; align-items: center; }}
  .nav-item-wrap .nav-item {{ flex: 1; }}
</style>
</head>
<body class="flags-hidden ms-hidden old-hidden">

<a href="#main-content" class="skip-link" style="position:absolute;left:-9999px;top:0;z-index:999;background:var(--accent);color:#0f172a;padding:8px 16px;font-size:0.85rem;text-decoration:none;" onfocus="this.style.left='0'" onblur="this.style.left='-9999px'">Skip to content</a>

<button class="mobile-menu-btn" onclick="toggleSidebar()" aria-label="Open navigation menu">\u2630</button>
<nav class="sidebar" id="sidebar" aria-label="University navigation">
  <h3>Universities ({len(all_data)})</h3>
  {"".join(nav_items)}
</nav>
<div class="sidebar-overlay" onclick="toggleSidebar()" role="presentation"></div>

<main class="main" id="main-content">
  <header class="top-nav" role="banner">
    <a href="index.html" class="top-nav-btn">Education Index</a>
    <a href="{"stem.html" if is_nonstem else "non_stem.html"}" class="top-nav-btn">{"STEM View" if is_nonstem else "Non-STEM View"}</a>
    <a href="data_sources.html" class="top-nav-btn">Data Sources</a>
  </header>
  <h1>{"Non-STEM " if is_nonstem else ""}Thesis &amp; Dissertation Lists — High <abbr title="Non-Resident Alien: a person who is not a citizen or national of the United States and who is in this country on a visa or temporary basis" style="text-decoration:underline dotted;cursor:help;">NRA</abbr> Universities</h1>
  <p class="subtitle">{"Non-STEM fields (Education, Humanities, Social Sciences, etc.). " if is_nonstem else ""}Every name links to the university's institutional repository for direct verification. {sum(u['count'] for u in index_unis):,} total records across {len(all_data_sorted)} schools.</p>
  <div style="background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.3);border-radius:8px;padding:8px 14px;margin:10px 0 4px;font-size:0.82rem;color:#fbbf24;">Data scraping still in progress. Record counts may change as new data is collected.</div>

  <div id="info-section">
    <div class="info-box">
      <details open>
        <summary>About this data</summary>
        <p style="margin-top:8px;">
          <strong>This page shows ALL graduates</strong> — every student who submitted a thesis or dissertation
          to the institutional repository in the 2016–2024 window, not only non-resident aliens. Americans,
          permanent residents, and international students are all included.
        </p>
        <p style="margin-top:8px;">
          <strong>Data source:</strong> Names were collected from each university's
          <a href="https://www.openarchives.org/pmh/" target="_blank">OAI-PMH</a>
          "Theses and Dissertations" collections. These typically include <strong>both doctoral dissertations
          and master's theses</strong>. Only Caltech has explicit PhD-only filtering.
          Where possible, records are labeled
          <span style="color:#4ade80;">PhD</span> or <span style="color:#fbbf24;">MS</span>
          based on available metadata, but many records cannot be distinguished.
          Each name links directly to the original record for verification.
        </p>
        <p style="margin-top:8px;">
          <strong>IPEDS <abbr title="Non-Resident Alien: a person who is not a citizen or national of the United States and who is in this country on a visa or temporary basis" style="text-decoration:underline dotted;cursor:help;">NRA</abbr> %</strong>
          refers to the percentage of STEM doctoral completions awarded to
          <a href="https://nces.ed.gov/ipeds/report-your-data/race-ethnicity-reporting-changes" target="_blank">Non-Resident Aliens</a>
          at each university, as reported in the
          <a href="https://nces.ed.gov/ipeds/" target="_blank">Integrated Postsecondary Education Data System (IPEDS)</a>
          maintained by the National Center for Education Statistics (NCES).
          Completions data is from the
          <a href="https://nces.ed.gov/ipeds/use-the-data/survey-components/9/completions" target="_blank">IPEDS Completions Survey</a>.
          Universities are ranked by <abbr title="Non-Resident Alien" style="text-decoration:underline dotted;cursor:help;">NRA</abbr> share of STEM PhDs.
        </p>
        <p style="margin-top:8px;">
          <strong>Origin estimates</strong> are produced by a name-classification model and should be treated as approximate.
          Toggle "Show estimated origin" above to display or hide these labels.
        </p>
      </details>
    </div>
  </div>

  <div class="toolbar">
    <!-- Search disabled — will be on dedicated cross-university page -->
    <input type="text" class="search-input" id="search" placeholder="Search by name across all universities..." oninput="debounceSearch(this.value)" style="display:none;">
    <div class="toggle-bar">
      <div class="toggle-wrap" onclick="toggleMs()" id="ms-toggle" role="switch" aria-checked="false" tabindex="0" onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();this.click();}}">
        <div class="toggle-switch"></div>
        <span class="toggle-label">Show Master's Theses</span>
      </div>
      <div class="legend-sep"></div>
      <div class="toggle-wrap" onclick="toggleFunding()" id="funding-toggle" role="switch" aria-checked="false" tabindex="0" onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();this.click();}}">
        <div class="toggle-switch"></div>
        <span class="toggle-label">R&amp;D Funding</span>
      </div>
      <div class="legend-sep"></div>
      <div class="toggle-wrap" onclick="toggleEnrollment()" id="enrollment-toggle" role="switch" aria-checked="false" tabindex="0" onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();this.click();}}">
        <div class="toggle-switch"></div>
        <span class="toggle-label">Enrollment</span>
      </div>
      <div class="legend-sep" id="old-toggle-sep" style="display:none;"></div>
      <div class="toggle-wrap" onclick="toggleOld()" id="old-toggle" style="display:none;">
        <div class="toggle-switch"></div>
        <span class="toggle-label">Show Pre-2010 Records</span>
      </div>
      <div class="legend-sep" style="display:none;"></div>
      <div class="legend-key flags-only-legend" style="display:none;">
        {"".join(legend_key_items)}
      </div>
      <div class="legend-sep"></div>
      <select id="dept-filter" class="dept-filter-select" onchange="applyDeptFilter(this.value)">
        <option value="">All departments</option>
      </select>
    </div>
    <div class="search-results" id="search-results"></div>
  </div>

  <div id="funding-chart-container" class="funding-chart-wrap" style="position:relative;">
    <a class="share-anchor" onclick="shareAnchor((currentKey||'')+'--funding',event)" title="Copy link to funding panel" style="position:absolute;top:12px;right:12px;">\U0001F517</a>
    <h3 id="funding-chart-title">R&amp;D Expenditures</h3>
    <div class="funding-source">Sources: <a href="https://ncses.nsf.gov/surveys/higher-education-research-development/2024" target="_blank">NSF HERD Survey</a> (R&amp;D, FY 2010–2024) · <a href="https://nces.ed.gov/ipeds/" target="_blank">IPEDS Finance Survey</a> (Revenue, FY 2022-23)</div>
    <div class="funding-panels">
      <div>
        <div style="font-weight:600;font-size:0.85rem;margin-bottom:6px;">R&amp;D Expenditures (<a href="https://ncses.nsf.gov/surveys/higher-education-research-development/2024" target="_blank" style="color:var(--accent);text-decoration:none;">NSF HERD</a>)</div>
        <canvas id="funding-chart"></canvas>
      </div>
      <div id="finance-breakdown" class="finance-breakdown" style="display:none;">
        <div style="font-weight:600;font-size:0.85rem;margin-bottom:6px;">Revenue by Source (<a href="https://nces.ed.gov/ipeds/" target="_blank" style="color:var(--accent);text-decoration:none;">IPEDS</a>)</div>
        <canvas id="finance-chart" style="max-height:220px;"></canvas>
        <div id="finance-details" style="margin-top:8px;font-size:0.78rem;color:var(--text-muted);line-height:1.6;"></div>
      </div>
    </div>
  </div>

  <div id="enrollment-container" class="funding-chart-wrap" style="position:relative;">
    <a class="share-anchor" onclick="shareAnchor((currentKey||'')+'--enrollment',event)" title="Copy link to enrollment panel" style="position:absolute;top:12px;right:12px;">\U0001F517</a>
    <h3 id="enrollment-title">Graduate Enrollment Demographics</h3>
    <div class="funding-source">Sources: <a href="https://ncses.nsf.gov/surveys/graduate-students-postdoctorates-in-science-and-engineering" target="_blank">NSF GSS</a> (Enrollment, 2024) · <a href="https://nces.ed.gov/ipeds/" target="_blank">IPEDS Completions</a> (PhD Trend, 2010–2024)</div>
    <div class="funding-panels">
      <div>
        <div style="font-weight:600;font-size:0.85rem;margin-bottom:6px;">Enrollment by Citizenship (<a href="https://ncses.nsf.gov/surveys/graduate-students-postdoctorates-in-science-and-engineering" target="_blank" style="color:var(--accent);text-decoration:none;">NSF GSS</a>)</div>
        <div id="enrollment-stats" style="margin-bottom:10px;"></div>
        <canvas id="enrollment-field-chart" style="max-height:220px;"></canvas>
      </div>
      <div>
        <div style="font-weight:600;font-size:0.85rem;margin-bottom:6px;">PhD Completions Trend (<a href="https://nces.ed.gov/ipeds/" target="_blank" style="color:var(--accent);text-decoration:none;">IPEDS</a>)</div>
        <canvas id="completions-trend-chart" style="max-height:220px;"></canvas>
      </div>
    </div>
  </div>

  <div id="content" role="region" aria-label="University data" aria-live="polite">
    <p class="placeholder-msg">\u2190 Select a university from the sidebar to view its name lists.</p>
  </div>
</main>

<script>
const DATA = {data_json};
const DATA_DIR = '{data_dir}';
const ORIGINS = {origins_js};
const ORIGIN_KEYS = Object.keys(ORIGINS);
let flagsVisible = false;
let msVisible = false;
let oldVisible = false;
let currentKey = null;
let searchTimer = null;
const FUNDING = {funding_json};
let fundingVisible = false;
let enrollmentVisible = false;
let enrollmentFieldChart = null;
let completionsTrendChart = null;
let fundingChart = null;
let financeChart = null;

// Build lookup by key (lightweight — no records yet)
const UNI_MAP = {{}};
DATA.forEach(u => UNI_MAP[u.key] = u);

// Cache for fetched university data
const UNI_CACHE = {{}};

function esc(s) {{ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'); }}

function slug(s) {{ return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''); }}

function expandAllDepts() {{
  document.querySelectorAll('#content .dept-section.collapsed').forEach(el => el.classList.remove('collapsed'));
}}
function collapseAllDepts() {{
  document.querySelectorAll('#content .dept-section:not(.collapsed)').forEach(el => el.classList.add('collapsed'));
}}
function expandAllYears(btn) {{
  const deptBody = btn.closest('.dept-body');
  if (deptBody) deptBody.querySelectorAll('.year-block.yr-collapsed').forEach(el => el.classList.remove('yr-collapsed'));
}}
function collapseAllYears(btn) {{
  const deptBody = btn.closest('.dept-body');
  if (deptBody) deptBody.querySelectorAll('.year-block:not(.yr-collapsed)').forEach(el => el.classList.add('yr-collapsed'));
}}

function badge(cat) {{
  if (!ORIGINS[cat]) return '';
  const [flag, label] = ORIGINS[cat];
  if (cat === 'arabic') return '<span class="flag-badge" data-origin="arabic" title="Arabic"><img src="arabic_language_flag.svg" class="arabic-flag-img" alt="Arabic"></span>';
  return `<span class="flag-badge" data-origin="${{cat}}" title="${{label}}">${{flag}}</span>`;
}}

function degreeBadge(deg) {{
  if (deg === 'phd') return '<span class="degree-badge degree-phd">PhD</span>';
  if (deg === 'ms') return '<span class="degree-badge degree-ms">MS</span>';
  return '';
}}

function renderUni(uni) {{
  // records: [dept, year, name, cat, conf, title, url, degree]
  // Group by dept
  const deptMap = {{}};
  uni.records.forEach(r => {{
    const d = r[0];
    if (!deptMap[d]) deptMap[d] = [];
    deptMap[d].push(r);
  }});

  // Compute stats per dept
  const depts = Object.entries(deptMap).map(([dept, recs]) => {{
    const stats = {{total: recs.length}};
    ORIGIN_KEYS.forEach(o => stats[o] = 0);
    recs.forEach(r => {{ if (ORIGINS[r[3]]) stats[r[3]]++; }});
    const classified = ORIGIN_KEYS.reduce((s, o) => s + stats[o], 0);
    stats.classifiedPct = recs.length ? classified / recs.length * 100 : 0;
    return {{dept, recs, stats}};
  }}).filter(d => d.stats.total >= 5 || (d.stats.classifiedPct >= 5 && d.stats.total >= 1))
    .sort((a, b) => {{
      // "General" always goes last
      const aGen = a.dept.toLowerCase() === 'general' ? 1 : 0;
      const bGen = b.dept.toLowerCase() === 'general' ? 1 : 0;
      if (aGen !== bGen) return aGen - bGen;
      return b.stats.total - a.stats.total;
    }});

  const allTotal = depts.reduce((s, d) => s + d.stats.total, 0);
  const originTotals = {{}};
  ORIGIN_KEYS.forEach(o => originTotals[o] = depts.reduce((s, d) => s + d.stats[o], 0));

  // Degree type counts
  let phdCount = 0, msCount = 0, unknownCount = 0;
  depts.forEach(d => d.recs.forEach(r => {{
    if (r[7] === 'phd') phdCount++;
    else if (r[7] === 'ms') msCount++;
    else unknownCount++;
  }}));

  let statsParts = [];
  if (phdCount > 0) statsParts.push(`<span style="color:#4ade80">${{phdCount}} PhD</span>`);
  if (msCount > 0) statsParts.push(`<span style="color:#fbbf24">${{msCount}} MS</span>`);
  if (unknownCount > 0) statsParts.push(`${{unknownCount}} unlabeled`);
  let originParts = [];
  ORIGIN_KEYS.forEach(o => {{
    if (originTotals[o] > 0) {{
      const [flag, label] = ORIGINS[o];
      originParts.push(`${{flag}} ${{originTotals[o]}} ${{label}}`);
    }}
  }});

  const repoBase = getRepoBase(uni);
  const repoLink = repoBase ? ` &middot; <a href="${{repoBase}}" target="_blank" style="color:var(--accent);text-decoration:none;font-size:0.8rem;">Institutional Repository \u2197</a>` : '';
  const uniSlug = slug(uni.key || uni.name);
  let html = `<h2 id="${{uniSlug}}">${{esc(uni.name)}} <span class="uni-nra">IPEDS <abbr title="Non-Resident Alien: a person who is not a citizen or national of the United States and who is in this country on a visa or temporary basis" style="text-decoration:underline dotted;cursor:help;">NRA</abbr>: ${{uni.nra}}%</span></h2>`;
  html += `<div class="uni-stats">${{allTotal.toLocaleString()}} records across ${{depts.length}} departments &middot; ${{statsParts.join(' &middot; ')}}`;
  if (originParts.length > 0) html += `<span class="uni-origin-stats"> &middot; ${{originParts.join(' &middot; ')}}</span>`;
  html += `${{repoLink}}</div>`;
  html += `<div style="margin:8px 0 12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;"><button onclick="expandAllDepts()" style="background:var(--surface);border:1px solid var(--surface2);color:var(--text-muted);font-size:0.72rem;padding:3px 10px;border-radius:5px;cursor:pointer;">Expand All Departments</button><button onclick="collapseAllDepts()" style="background:var(--surface);border:1px solid var(--surface2);color:var(--text-muted);font-size:0.72rem;padding:3px 10px;border-radius:5px;cursor:pointer;">Collapse All</button><button id="share-btn" onclick="shareLink()" style="background:none;border:none;font-size:0.75rem;cursor:pointer;margin-left:auto;opacity:0.4;transition:opacity 0.15s;" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.4'" title="Copy link to clipboard">\U0001F517</button></div>`;

  let deptIdx = 0;
  depts.forEach(d => {{
    const isGeneral = d.dept.toLowerCase() === 'general';
    // Group by year
    const byYear = {{}};
    d.recs.forEach(r => {{
      const yr = r[1];
      if (!byYear[yr]) byYear[yr] = [];
      byYear[yr].push(r);
    }});

    let yearHtml = '';
    Object.keys(byYear).sort((a, b) => b - a).forEach(yr => {{
      const yrRecs = byYear[yr].sort((a, b) => a[2].localeCompare(b[2]));

      // Split into PhD/unlabeled vs MS
      const phdRecs = yrRecs.filter(r => r[7] !== 'ms');
      const msRecs = yrRecs.filter(r => r[7] === 'ms');

      // Stats for PhD/unlabeled group
      const yrCounts = {{}};
      ORIGIN_KEYS.forEach(o => yrCounts[o] = 0);
      phdRecs.forEach(r => {{ if (ORIGINS[r[3]]) yrCounts[r[3]]++; }});
      const yrClassified = ORIGIN_KEYS.reduce((s, o) => s + yrCounts[o], 0);
      const yrPct = phdRecs.length ? yrClassified / phdRecs.length * 100 : 0;

      let yrBadge = [];
      ORIGIN_KEYS.forEach(o => {{
        if (yrCounts[o] > 0) {{ const [flag] = ORIGINS[o]; yrBadge.push(`${{flag}}${{yrCounts[o]}}`); }}
      }});
      const pctClass = yrPct >= 40 ? 'pct-high' : yrPct >= 20 ? 'pct-med' : '';

      // Build year header label
      let headerLabel = `${{phdRecs.length}} dissertation${{phdRecs.length !== 1 ? 's' : ''}}`;
      if (msRecs.length > 0) headerLabel += `<span class="year-ms-note"> and ${{msRecs.length}} master's thesis${{msRecs.length !== 1 ? 'es' : ''}}</span>`;

      function buildNameRows(recs) {{
        let rows = '';
        recs.forEach(r => {{
          const b = badge(r[3]);
          const db = degreeBadge(r[7]);
          const titleEsc = esc(r[5]);
          const nameEl = r[6]
            ? `<a href="${{r[6]}}" target="_blank" class="name-link">${{esc(r[2])}}</a>`
            : `<span class="name-nolink">${{esc(r[2])}}</span>`;
          rows += `<div class="name-row"><div class="name-col">${{db}}${{b}}${{nameEl}}</div><div class="title-col" title="${{titleEsc}}">${{titleEsc}}</div></div>`;
        }});
        return rows;
      }}

      let namesHtml = buildNameRows(phdRecs);

      if (msRecs.length > 0) {{
        const msCounts = {{}};
        ORIGIN_KEYS.forEach(o => msCounts[o] = 0);
        msRecs.forEach(r => {{ if (ORIGINS[r[3]]) msCounts[r[3]]++; }});
        const msClassified = ORIGIN_KEYS.reduce((s, o) => s + msCounts[o], 0);

        let msBadge = [];
        ORIGIN_KEYS.forEach(o => {{
          if (msCounts[o] > 0) {{ const [flag] = ORIGINS[o]; msBadge.push(`${{flag}}${{msCounts[o]}}`); }}
        }});

        namesHtml += `<div class="ms-group"><div class="ms-group-header" onclick="this.parentElement.classList.toggle('collapsed')"><span class="dept-toggle">\u25bc</span><span style="color:#fbbf24;font-weight:600;font-size:0.82rem;">${{msRecs.length}} Master's Thesis${{msRecs.length !== 1 ? 'es' : ''}}</span><span class="year-pct" style="font-size:0.78rem;margin-left:8px;">${{msBadge.join(' ')}} &mdash; ${{msClassified}}/${{msRecs.length}} classified</span></div><div class="ms-group-body">${{buildNameRows(msRecs)}}</div></div>`;
      }}

      const oldClass = parseInt(yr) < 2010 ? ' pre-2010' : '';
      const yrId = uniSlug + '--' + slug(d.dept) + '--' + yr;
      yearHtml += `<div class="year-block${{oldClass}}" id="${{yrId}}"><div class="year-header" onclick="this.parentElement.classList.toggle('yr-collapsed')"><span class="year-toggle">\u25bc</span><span class="year-label">${{yr}}</span><span class="year-count">${{headerLabel}}</span><a class="share-anchor" onclick="shareAnchor('${{yrId}}',event)" title="Copy link to ${{yr}}">\U0001F517</a><span class="year-pct ${{pctClass}}">${{yrBadge.join(' ')}} &mdash; ${{yrClassified}}/${{phdRecs.length}} classified (${{yrPct.toFixed(0)}}%)</span></div><div class="year-names">${{namesHtml}}</div></div>`;
    }});

    // Dept header flags
    let deptBadge = [];
    ORIGIN_KEYS.forEach(o => {{
      if (d.stats[o] > 0) {{
        const [flag] = ORIGINS[o];
        deptBadge.push(`${{flag}}${{d.stats[o]}} (${{(d.stats[o]/d.stats.total*100).toFixed(0)}}%)`);
      }}
    }});
    const pctClass = d.stats.classifiedPct >= 30 ? 'pct-high' : d.stats.classifiedPct >= 20 ? 'pct-med' : '';
    // Expand first 5 non-General departments; General always collapsed
    const collapsed = (isGeneral || deptIdx >= 5) ? ' collapsed' : '';
    const generalClass = isGeneral ? ' dept-general' : '';
    // Auto-expand if department filter is active
    const deptFilterVal = window._activeDeptFilter || '';
    const filterExpand = deptFilterVal && d.dept === deptFilterVal ? '' : collapsed;
    const finalCollapsed = deptFilterVal ? filterExpand : collapsed;

    // Build department links if available
    const deptLinks = uni.dept_links && uni.dept_links[d.dept];
    let deptLinkHtml = '';
    if (deptLinks) {{
      if (deptLinks.home) deptLinkHtml += ` <a href="${{deptLinks.home}}" target="_blank" onclick="event.stopPropagation()" style="color:var(--accent);font-size:0.75rem;text-decoration:none;" title="Department homepage">\u2197 Dept</a>`;
      if (deptLinks.students) deptLinkHtml += ` <a href="${{deptLinks.students}}" target="_blank" onclick="event.stopPropagation()" style="color:var(--accent);font-size:0.75rem;text-decoration:none;" title="PhD student directory">\u2197 Students</a>`;
      if (deptLinks.repo_search) deptLinkHtml += ` <a href="${{deptLinks.repo_search}}" target="_blank" onclick="event.stopPropagation()" style="color:var(--accent);font-size:0.75rem;text-decoration:none;" title="Search repository for this department">\u2197 Repo</a>`;
    }}

    const deptSlug = uniSlug + '--' + slug(d.dept);
    const yearControls = Object.keys(byYear).length > 2 ? `<div style="display:flex;gap:6px;margin-bottom:6px;"><button onclick="expandAllYears(this)" style="background:none;border:1px solid var(--surface2);color:var(--text-muted);font-size:0.68rem;padding:2px 8px;border-radius:4px;cursor:pointer;">Expand All Years</button><button onclick="collapseAllYears(this)" style="background:none;border:1px solid var(--surface2);color:var(--text-muted);font-size:0.68rem;padding:2px 8px;border-radius:4px;cursor:pointer;">Collapse Years</button></div>` : '';
    html += `<div class="dept-section${{finalCollapsed}}${{generalClass}}" id="${{deptSlug}}" data-dept="${{esc(d.dept)}}"><div class="dept-header" onclick="this.parentElement.classList.toggle('collapsed')"><span class="dept-toggle">\u25bc</span><span class="dept-name">${{esc(d.dept)}}</span>${{deptLinkHtml}}<span class="dept-stats">${{d.stats.total}} records</span><span class="dept-flags">${{deptBadge.join('  ')}}</span><span class="dept-pct ${{pctClass}}">${{d.stats.classifiedPct.toFixed(0)}}% classified</span><a class="share-anchor" onclick="shareAnchor('${{deptSlug}}',event)" title="Copy link to ${{esc(d.dept)}}">\U0001F517</a></div><div class="dept-body">${{yearControls}}${{yearHtml}}</div></div>`;
    deptIdx++;
  }});

  return html;
}}

function toggleSidebar() {{
  document.getElementById('sidebar').classList.toggle('open');
}}

function showUni(key, skipHash) {{
  // Close mobile sidebar if open
  document.getElementById('sidebar').classList.remove('open');
  currentKey = key;
  if (!skipHash) updateUrlState();
  document.getElementById('search').value = '';
  document.getElementById('search-results').style.display = 'none';

  document.querySelectorAll('.nav-item').forEach(a => {{
    a.classList.toggle('active', a.dataset.key === key);
  }});

  if (!UNI_MAP[key]) return;
  document.getElementById('info-section').style.display = 'none';

  // If already cached, render immediately
  if (UNI_CACHE[key]) {{
    document.getElementById('content').innerHTML = renderUni(UNI_CACHE[key]);
    updateOldToggle();
    updateFundingChart();
    updateEnrollmentPanel();
    return;
  }}

  // Show loading state, then fetch
  document.getElementById('content').innerHTML = '<p class="placeholder-msg">Loading...</p>';
  fetch(DATA_DIR + '/' + key + '.json')
    .then(r => r.json())
    .then(uni => {{
      UNI_CACHE[key] = uni;
      // Only render if still the current selection
      if (currentKey === key) {{
        document.getElementById('content').innerHTML = renderUni(uni);
        updateOldToggle();
        updateFundingChart();
        updateEnrollmentPanel();
      }}
    }})
    .catch(e => {{
      document.getElementById('content').innerHTML = '<p class="placeholder-msg">Error loading data: ' + e.message + '</p>';
    }});
}}

function toggleFlags() {{
  flagsVisible = !flagsVisible;
  document.getElementById('flag-toggle').classList.toggle('active', flagsVisible);
  document.body.classList.toggle('flags-hidden', !flagsVisible);
}}

function toggleMs() {{
  msVisible = !msVisible;
  const el = document.getElementById('ms-toggle');
  el.classList.toggle('active', msVisible);
  el.setAttribute('aria-checked', msVisible);
  document.body.classList.toggle('ms-hidden', !msVisible);
  updateUrlState();
}}

function toggleOld() {{
  oldVisible = !oldVisible;
  document.getElementById('old-toggle').classList.toggle('active', oldVisible);
  document.body.classList.toggle('old-hidden', !oldVisible);
}}

function toggleFunding() {{
  fundingVisible = !fundingVisible;
  const el = document.getElementById('funding-toggle');
  el.classList.toggle('active', fundingVisible);
  el.setAttribute('aria-checked', fundingVisible);
  updateFundingChart();
  updateUrlState();
}}

function toggleEnrollment() {{
  enrollmentVisible = !enrollmentVisible;
  const el = document.getElementById('enrollment-toggle');
  el.classList.toggle('active', enrollmentVisible);
  el.setAttribute('aria-checked', enrollmentVisible);
  updateEnrollmentPanel();
  updateUrlState();
}}

function updateEnrollmentPanel() {{
  const container = document.getElementById('enrollment-container');
  if (!enrollmentVisible || !currentKey) {{
    container.classList.remove('visible');
    return;
  }}

  const uni = UNI_CACHE[currentKey];
  if (!uni || !uni.enrollment) {{
    container.classList.remove('visible');
    return;
  }}
  container.classList.add('visible');

  const enr = uni.enrollment;
  const trend = uni.completions_trend;

  // Title
  document.getElementById('enrollment-title').textContent = uni.name + ' — Graduate Enrollment & PhD Trend';

  // Stats summary
  const statsEl = document.getElementById('enrollment-stats');
  const foreignPct = enr.foreign_pct || 0;
  const docForeignPct = enr.doctoral_total ? ((enr.doctoral_foreign / enr.doctoral_total) * 100).toFixed(0) : '?';
  const maForeignPct = enr.masters_total ? ((enr.masters_foreign / enr.masters_total) * 100).toFixed(0) : '?';

  const tuit = uni.tuition || {{}};
  const aid = uni.financial_aid || {{}};
  const fac = uni.faculty || {{}};

  let html = `<div style="display:flex;gap:20px;flex-wrap:wrap;font-size:0.82rem;margin-bottom:8px;">
    <div><span style="font-size:1.3rem;font-weight:700;color:var(--text);">${{enr.total_grad?.toLocaleString() || '?'}}</span><br><span style="color:var(--text-muted);">Total Grad Students</span></div>
    <div><span style="font-size:1.3rem;font-weight:700;color:#f87171;">${{foreignPct}}%</span><br><span style="color:var(--text-muted);">Temporary Visa Holders</span></div>
    <div><span style="font-size:1.3rem;font-weight:700;color:#4ade80;">${{enr.doctoral_total?.toLocaleString() || '?'}}</span><br><span style="color:var(--text-muted);">Doctoral (${{docForeignPct}}% foreign)</span></div>
    <div><span style="font-size:1.3rem;font-weight:700;color:#fbbf24;">${{enr.masters_total?.toLocaleString() || '?'}}</span><br><span style="color:var(--text-muted);">Master's (${{maForeignPct}}% foreign)</span></div>
  </div>`;

  // Second row: tuition, aid, faculty
  let row2 = [];
  if (tuit.outstate > 0) {{
    const instate = tuit.instate ? `$${{(tuit.instate/1000).toFixed(0)}}K in-state` : '';
    row2.push(`<div><span style="font-size:1rem;font-weight:600;color:var(--text);">$${{(tuit.outstate/1000).toFixed(0)}}K</span><br><span style="color:var(--text-muted);">Grad Tuition (out-of-state)${{instate ? '<br>' + instate : ''}}</span></div>`);
  }}
  if (aid.grant_total > 0) {{
    const pctAided = aid.grad_students > 0 ? ((aid.receiving_grants / aid.grad_students) * 100).toFixed(0) : '?';
    row2.push(`<div><span style="font-size:1rem;font-weight:600;color:var(--text);">$${{(aid.grant_total/1e6).toFixed(1)}}M</span><br><span style="color:var(--text-muted);">Grad Grants (${{pctAided}}% receive aid)</span></div>`);
  }}
  if (fac.total > 0) {{
    row2.push(`<div><span style="font-size:1rem;font-weight:600;color:var(--text);">${{fac.total.toLocaleString()}}</span><br><span style="color:var(--text-muted);">Faculty (${{fac.nra_pct}}% NRA)</span></div>`);
  }}
  if (row2.length > 0) {{
    html += `<div style="display:flex;gap:20px;flex-wrap:wrap;font-size:0.82rem;margin-top:6px;padding-top:6px;border-top:1px solid var(--surface2);">${{row2.join('')}}</div>`;
  }}

  statsEl.innerHTML = html;

  // Field bar chart — top fields by foreign enrollment
  const fields = enr.by_field || [];
  if (fields.length > 0 && document.getElementById('enrollment-field-chart')) {{
    if (enrollmentFieldChart) enrollmentFieldChart.destroy();
    const ctx = document.getElementById('enrollment-field-chart').getContext('2d');
    const topFields = fields.slice(0, 10);
    enrollmentFieldChart = new Chart(ctx, {{
      type: 'bar',
      data: {{
        labels: topFields.map(f => f.field.length > 30 ? f.field.substring(0, 28) + '...' : f.field),
        datasets: [
          {{ label: 'Foreign', data: topFields.map(f => f.foreign), backgroundColor: '#f87171' }},
          {{ label: 'US Domestic', data: topFields.map(f => f.total - f.foreign), backgroundColor: '#38bdf8' }},
        ]
      }},
      options: {{
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#94a3b8', font: {{ size: 10 }} }} }} }},
        scales: {{
          x: {{ stacked: true, ticks: {{ color: '#64748b', font: {{ size: 10 }} }}, grid: {{ color: '#1e293b' }} }},
          y: {{ stacked: true, ticks: {{ color: '#94a3b8', font: {{ size: 10 }} }}, grid: {{ display: false }} }}
        }}
      }}
    }});
  }}

  // Completions trend chart — show STEM if available, otherwise all fields
  if (trend && trend.years && trend.years.length > 0 && document.getElementById('completions-trend-chart')) {{
    if (completionsTrendChart) completionsTrendChart.destroy();
    const ctx2 = document.getElementById('completions-trend-chart').getContext('2d');

    // Prefer STEM-only data if available
    const hasStem = trend.phd_stem_total && trend.phd_stem_total.some(v => v > 0);
    const totals = hasStem ? trend.phd_stem_total : trend.phd_total;
    const nras = hasStem ? trend.phd_stem_nra : trend.phd_nra;
    const chartLabel = hasStem ? 'STEM PhD Completions (IPEDS)' : 'PhD Completions — All Fields (IPEDS)';

    // Update panel title
    document.querySelector('#enrollment-container .funding-panels > div:last-child > div:first-child').innerHTML =
      chartLabel + ' <a href="https://nces.ed.gov/ipeds/" target="_blank" style="color:var(--accent);text-decoration:none;font-weight:400;font-size:0.8rem;">source</a>';

    const domestic = totals.map((t, i) => t - (nras[i] || 0));
    completionsTrendChart = new Chart(ctx2, {{
      type: 'line',
      data: {{
        labels: trend.years,
        datasets: [
          {{ label: 'Temporary Visa (NRA)', data: nras, borderColor: '#f87171', backgroundColor: 'rgba(248,113,113,0.3)', fill: true, tension: 0.3, order: 1 }},
          {{ label: 'US Citizens + Perm Residents*', data: domestic, borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.3)', fill: true, tension: 0.3, order: 2 }},
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ position: 'bottom', labels: {{ color: '#94a3b8', font: {{ size: 10 }} }} }},
          tooltip: {{ callbacks: {{
            afterBody: function(items) {{
              const idx = items[0].dataIndex;
              const t = totals[idx], n = nras[idx];
              return `NRA: ${{n}} of ${{t}} (${{(n/t*100).toFixed(0)}}%)`;
            }}
          }} }}
        }},
        scales: {{
          x: {{ ticks: {{ color: '#64748b', font: {{ size: 10 }} }}, grid: {{ color: '#1e293b' }}, stacked: true }},
          y: {{ ticks: {{ color: '#64748b', font: {{ size: 10 }} }}, grid: {{ color: '#1e293b' }}, beginAtZero: true, stacked: true }}
        }}
      }}
    }});
  }}

  // Add footnote about green card holders
  const footnoteId = 'enrollment-footnote';
  let footnote = document.getElementById(footnoteId);
  if (!footnote) {{
    footnote = document.createElement('div');
    footnote.id = footnoteId;
    footnote.style.cssText = 'font-size:0.72rem;color:var(--text-muted);margin-top:10px;line-height:1.5;padding:0 4px;';
    document.getElementById('enrollment-container').appendChild(footnote);
  }}
  const unknownTotal = trend && trend.phd_unknown ? trend.phd_unknown[trend.phd_unknown.length - 1] : 0;
  footnote.innerHTML = `*"US Citizens + Perm Residents" includes <strong>permanent residents (green card holders)</strong>, naturalized citizens, and DACA recipients — not just US-born citizens. ` +
    `An unknown number of students in this category are foreign-born with green cards. ` +
    (unknownTotal > 0 ? `${{unknownTotal}} students had unknown/unreported citizenship status in the most recent year. ` : '') +
    `<br>Source: <a href="https://nces.ed.gov/ipeds/" style="color:var(--accent);text-decoration:none;">IPEDS Completions Survey</a>, doctoral research degrees (AWLEVEL=17).`;
}}

function fmtDollars(n) {{
  if (n >= 1e9) return `$${{(n/1e9).toFixed(1)}}B`;
  if (n >= 1e6) return `$${{(n/1e6).toFixed(0)}}M`;
  if (n >= 1e3) return `$${{(n/1e3).toFixed(0)}}K`;
  return `$${{n}}`;
}}

function updateFundingChart() {{
  try {{
  const container = document.getElementById('funding-chart-container');
  if (!fundingVisible || !currentKey || !FUNDING[currentKey]) {{
    container.classList.remove('visible');
    return;
  }}
  container.classList.add('visible');
  const fdata = FUNDING[currentKey];
  const yearly = fdata.yearly_rd_thousands || {{}};
  const years = Object.keys(yearly).sort();
  const values = years.map(y => yearly[y] / 1000);

  document.getElementById('funding-chart-title').textContent =
    `${{fdata.name}} — Funding & Revenue (HERD Rank #${{fdata.rank}})`;

  if (typeof Chart === 'undefined') return;
  if (fundingChart) fundingChart.destroy();
  const ctx = document.getElementById('funding-chart').getContext('2d');
  fundingChart = new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: years,
      datasets: [{{
        label: 'Total R&D ($M)',
        data: values,
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56,189,248,0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 4,
        pointBackgroundColor: '#38bdf8',
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            label: function(ctx) {{
              return `$${{ctx.parsed.y.toFixed(0)}}M`;
            }}
          }}
        }}
      }},
      scales: {{
        y: {{
          beginAtZero: true,
          ticks: {{ callback: v => `$${{v}}M`, color: '#94a3b8' }},
          grid: {{ color: 'rgba(51,65,85,0.5)' }},
        }},
        x: {{
          ticks: {{ color: '#94a3b8' }},
          grid: {{ display: false }},
        }}
      }}
    }}
  }});

  // IPEDS Finance breakdown - multi-year stacked chart
  const fb = document.getElementById('finance-breakdown');
  const series = fdata.ipeds_finance_series;
  if (!series || Object.keys(series).length === 0) {{
    fb.style.display = 'none';
    return;
  }}
  fb.style.display = '';

  const finYears = Object.keys(series).sort();
  const fedData = finYears.map(y => series[y].federal / 1e6);
  const stateData = finYears.map(y => series[y].state / 1e6);
  const tuitionData = finYears.map(y => series[y].tuition / 1e6);
  const otherData = finYears.map(y => Math.max(0, (series[y].total - series[y].federal - series[y].state - series[y].tuition)) / 1e6);
  const finLabels = finYears.map(y => `FY${{y}}`);

  if (typeof Chart === 'undefined') return;
  if (financeChart) financeChart.destroy();
  const ctx2 = document.getElementById('finance-chart').getContext('2d');
  financeChart = new Chart(ctx2, {{
    type: 'bar',
    data: {{
      labels: finLabels,
      datasets: [
        {{ label: 'Federal', data: fedData, backgroundColor: '#f87171', stack: 'rev' }},
        {{ label: 'State', data: stateData, backgroundColor: '#60a5fa', stack: 'rev' }},
        {{ label: 'Tuition', data: tuitionData, backgroundColor: '#4ade80', stack: 'rev' }},
        {{ label: 'Other (gifts, investment, hospitals, auxiliary, private grants)', data: otherData, backgroundColor: '#475569', stack: 'rev' }},
      ]
    }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{
          position: 'bottom',
          labels: {{ color: '#94a3b8', boxWidth: 12, padding: 10, font: {{ size: 11 }} }}
        }},
        tooltip: {{
          callbacks: {{
            label: function(ctx) {{
              const lbl = ctx.dataset.label.split(' (')[0];
              return `${{lbl}}: $${{ctx.parsed.y.toFixed(0)}}M`;
            }},
            afterBody: function(items) {{
              const idx = items[0].dataIndex;
              const yr = finYears[idx];
              const d = series[yr];
              let lines = [`\\nTotal: ${{fmtDollars(d.total)}}`, `Taxpayer (Federal+State): ${{fmtDollars(d.federal + d.state)}} (${{((d.federal+d.state)/d.total*100).toFixed(0)}}%)`];
              if (d.other > 0) {{
                lines.push(`\\nOther includes:`);
                if (d.other_gifts) lines.push(`  Gifts/Donations: ${{fmtDollars(d.other_gifts)}}`);
                if (d.other_investment) lines.push(`  Investment Income: ${{fmtDollars(d.other_investment)}}`);
                if (d.other_hospitals) lines.push(`  Hospitals: ${{fmtDollars(d.other_hospitals)}}`);
                if (d.other_auxiliary) lines.push(`  Auxiliary (housing, dining): ${{fmtDollars(d.other_auxiliary)}}`);
              }}
              return lines.join('\\n');
            }}
          }}
        }}
      }},
      scales: {{
        y: {{
          stacked: true,
          beginAtZero: true,
          ticks: {{ callback: v => `$${{v}}M`, color: '#94a3b8' }},
          grid: {{ color: 'rgba(51,65,85,0.5)' }},
        }},
        x: {{
          stacked: true,
          ticks: {{ color: '#94a3b8' }},
          grid: {{ display: false }},
        }}
      }}
    }}
  }});

  // Summary for most recent year
  const latestYr = finYears[finYears.length - 1];
  const latest = series[latestYr];
  const taxpayer = latest.federal + latest.state;
  const taxpayerPct = ((taxpayer / latest.total) * 100).toFixed(0);
  document.getElementById('finance-details').innerHTML =
    `In FY${{latestYr}}: <strong style="color:#f87171;">${{fmtDollars(taxpayer)}}</strong> of ${{fmtDollars(latest.total)}} total revenue (${{taxpayerPct}}%) came from <strong style="color:var(--text);">taxpayer funding</strong> (federal + state).`
    + `<br><span style="font-size:0.72rem;color:var(--text-muted);">"Other" includes gifts &amp; donations, investment income, hospital revenue, auxiliary enterprises (housing, dining), and private grants. Hover bars for details.</span>`;
  }} catch(e) {{ console.warn('Funding chart error:', e); }}
}}

function updateOldToggle() {{
  // Show the pre-2010 toggle only if the current view has pre-2010 year blocks
  const hasPre2010 = document.querySelectorAll('#content .pre-2010').length > 0;
  document.getElementById('old-toggle').style.display = hasPre2010 ? '' : 'none';
  document.getElementById('old-toggle-sep').style.display = hasPre2010 ? '' : 'none';
}}

function resetView() {{
  currentKey = null;
  history.replaceState(null, '', location.pathname);
  document.getElementById('search').value = '';
  document.getElementById('search-results').style.display = 'none';
  document.querySelectorAll('.nav-item').forEach(a => a.classList.remove('active'));
  document.getElementById('content').innerHTML = '<p class="placeholder-msg">\u2190 Select a university from the sidebar to view its name lists.</p>';
  document.getElementById('info-section').style.display = '';
  document.getElementById('old-toggle').style.display = 'none';
  document.getElementById('old-toggle-sep').style.display = 'none';
  document.getElementById('funding-chart-container').classList.remove('visible');
  document.getElementById('enrollment-container').classList.remove('visible');
}}

function getRepoBase(uni) {{
  // Extract the base repository URL from the first record with a URL
  if (!uni.records) return null;
  for (const r of uni.records) {{
    if (r[6]) {{
      try {{
        const u = new URL(r[6]);
        return u.origin;
      }} catch(e) {{}}
    }}
  }}
  return null;
}}

function debounceSearch(q) {{
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => doSearch(q), 250);
}}

let searchIndex = null;
let searchIndexLoading = false;

function loadSearchIndex() {{
  if (searchIndex || searchIndexLoading) return;
  searchIndexLoading = true;
  fetch(DATA_DIR + '/_search.json')
    .then(r => r.json())
    .then(data => {{ searchIndex = data; searchIndexLoading = false; }})
    .catch(() => {{ searchIndexLoading = false; }});
}}

function doSearch(query) {{
  const q = query.toLowerCase().trim();
  const results = document.getElementById('search-results');
  const content = document.getElementById('content');

  if (!q || q.length < 2) {{
    if (currentKey && UNI_CACHE[currentKey]) {{
      content.innerHTML = renderUni(UNI_CACHE[currentKey]);
    }} else if (currentKey) {{
      showUni(currentKey, true);
    }} else {{
      content.innerHTML = '<p class="placeholder-msg">\u2190 Select a university from the sidebar.</p>';
    }}
    results.style.display = 'none';
    return;
  }}

  // Load search index if not ready
  if (!searchIndex) {{
    loadSearchIndex();
    results.style.display = 'block';
    results.textContent = 'Loading search index...';
    setTimeout(() => doSearch(query), 300);
    return;
  }}

  // Search the index: entries are [uniKey, name, dept, year]
  let hits = [];
  for (const entry of searchIndex) {{
    const text = (entry[1] + ' ' + entry[2]).toLowerCase();
    if (text.includes(q)) {{
      hits.push(entry);
      if (hits.length >= 200) break;
    }}
  }}

  results.style.display = 'block';
  if (hits.length === 0) {{
    results.textContent = 'No results found';
    content.innerHTML = '';
    return;
  }}

  results.textContent = hits.length >= 200
    ? `Showing first 200 results`
    : `${{hits.length}} results found`;

  // Group hits by university for nav highlighting
  const uniKeys = new Set(hits.map(h => h[0]));
  document.querySelectorAll('.nav-item').forEach(a => {{
    a.classList.toggle('active', uniKeys.has(a.dataset.key));
  }});

  // Render search results (name + dept + year + university)
  let html = '';
  hits.forEach(h => {{
    // h: [uniKey, name, dept, year]
    const uniName = UNI_MAP[h[0]] ? UNI_MAP[h[0]].name : h[0];
    html += `<div class="name-row"><div class="name-col"><a href="javascript:void(0)" class="name-link" onclick="showUni('${{h[0]}}')">${{esc(h[1])}}</a></div><div class="title-col">${{esc(uniName)}} &middot; ${{esc(h[2])}} &middot; ${{h[3]}}</div></div>`;
  }});
  content.innerHTML = html;
}}

// URL state management — encode toggles in hash params
function updateUrlState() {{
  if (!currentKey) return;
  let hash = currentKey;
  const params = [];
  if (enrollmentVisible) params.push('enrollment=1');
  if (fundingVisible) params.push('funding=1');
  if (msVisible) params.push('ms=1');
  if (params.length) hash += '?' + params.join('&');
  history.replaceState(null, '', '#' + hash);
}}

function parseUrlState() {{
  const raw = location.hash.replace('#', '');
  if (!raw) return null;
  const [keyPart, paramStr] = raw.split('?');
  const key = keyPart.toLowerCase();
  const params = {{}};
  if (paramStr) {{
    paramStr.split('&').forEach(p => {{
      const [k, v] = p.split('=');
      params[k] = v;
    }});
  }}
  return {{ key, params }};
}}

function applyUrlState(state) {{
  if (!state) return;
  // Find matching university
  let uniKey = null;
  if (UNI_MAP[state.key]) {{ uniKey = state.key; }}
  else {{
    for (const u of DATA) {{
      if (u.name.toLowerCase().replace(/[^a-z0-9]/g, '').includes(state.key.replace(/[^a-z0-9]/g, ''))) {{
        uniKey = u.key; break;
      }}
    }}
  }}
  if (!uniKey) return;

  showUni(uniKey, true);

  // Apply toggle states from URL
  if (state.params.enrollment === '1' && !enrollmentVisible) toggleEnrollment();
  if (state.params.funding === '1' && !fundingVisible) toggleFunding();
  if (state.params.ms === '1' && !msVisible) toggleMs();
}}

// Share anchor — copy a specific anchor link
function shareAnchor(id, event) {{
  if (event) event.stopPropagation();
  const base = location.origin + location.pathname;
  const url = base + '#' + id;
  // Track in analytics
  if (typeof send === 'function') send({{type:'share',target:id,uni:currentKey||'',url:url}});
  navigator.clipboard.writeText(url).then(() => {{
    const el = event && event.target;
    if (el) {{
      const orig = el.textContent;
      el.textContent = '\u2713';
      el.style.opacity = '1';
      el.style.color = '#4ade80';
      setTimeout(() => {{ el.textContent = orig; el.style.color = ''; el.style.opacity = ''; }}, 1500);
    }}
  }}).catch(() => {{
    prompt('Copy this link:', url);
  }});
}}

// Share button — copy current URL to clipboard
function shareLink() {{
  updateUrlState();
  const url = location.href;
  if (typeof send === 'function') send({{type:'share',target:'main',uni:currentKey||'',url:url}});
  navigator.clipboard.writeText(url).then(() => {{
    const btn = document.getElementById('share-btn');
    const orig = btn.textContent;
    btn.textContent = '\u2713 Copied!';
    btn.style.color = '#4ade80';
    setTimeout(() => {{ btn.textContent = orig; btn.style.color = ''; }}, 2000);
  }}).catch(() => {{
    prompt('Copy this link:', location.href);
  }});
}}

// On page load: restore state from URL
(function() {{
  const state = parseUrlState();
  if (state) applyUrlState(state);
}})();

// Preload search index in background after page loads
setTimeout(loadSearchIndex, 2000);

// Handle back/forward navigation
window.addEventListener('hashchange', function() {{
  const state = parseUrlState();
  if (state) applyUrlState(state);
}});

// ===== Department Filter (item 4) =====
window._activeDeptFilter = '';
const ALL_DEPTS = new Set();

// Populate department dropdown from loaded data
function populateDeptFilter() {{
  // Scan all cached university data for departments
  Object.values(UNI_CACHE).forEach(uni => {{
    if (!uni.records) return;
    uni.records.forEach(r => ALL_DEPTS.add(r[0]));
  }});
  const sel = document.getElementById('dept-filter');
  const current = sel.value;
  // Clear existing options except first
  while (sel.options.length > 1) sel.remove(1);
  const sorted = Array.from(ALL_DEPTS).sort((a, b) => {{
    if (a.toLowerCase() === 'general') return 1;
    if (b.toLowerCase() === 'general') return -1;
    return a.localeCompare(b);
  }});
  sorted.forEach(d => {{
    const opt = document.createElement('option');
    opt.value = d;
    opt.textContent = d;
    sel.appendChild(opt);
  }});
  if (current) sel.value = current;
}}

// On first use, we need to fetch _all_ university data to know which unis have a dept.
// We'll do a lighter approach: scan the search index (already fetched for search).
function applyDeptFilter(dept) {{
  window._activeDeptFilter = dept;
  if (!dept) {{
    // Show all sidebar items
    document.querySelectorAll('.nav-item-wrap').forEach(w => w.style.display = '');
    // Re-render current uni without filter
    if (currentKey && UNI_CACHE[currentKey]) {{
      document.getElementById('content').innerHTML = renderUni(UNI_CACHE[currentKey]);
      updateOldToggle();
    }}
    return;
  }}
  // Use search index to find which unis have this dept
  if (!searchIndex) {{
    loadSearchIndex();
    setTimeout(() => applyDeptFilter(dept), 400);
    return;
  }}
  const unisWithDept = new Set();
  searchIndex.forEach(entry => {{
    if (entry[2] === dept) unisWithDept.add(entry[0]);
  }});
  // Filter sidebar
  document.querySelectorAll('.nav-item-wrap').forEach(w => {{
    const key = w.dataset.unikey;
    w.style.display = unisWithDept.has(key) ? '' : 'none';
  }});
  // Re-render current uni so the matching dept is auto-expanded
  if (currentKey && UNI_CACHE[currentKey]) {{
    document.getElementById('content').innerHTML = renderUni(UNI_CACHE[currentKey]);
    updateOldToggle();
  }}
}}

// Hook into showUni to populate dept filter with new data
const _origShowUni = showUni;
// We patch after fetch to populate departments
(function() {{
  const origFetch = window.fetch;
  // After each uni data load, update the dept filter options
  const observer = new MutationObserver(() => {{
    populateDeptFilter();
  }});
  observer.observe(document.getElementById('content'), {{ childList: true }});
}})();

// Also populate dept filter from the search index once it loads
(function() {{
  const origLoad = loadSearchIndex;
  const checkInterval = setInterval(() => {{
    if (searchIndex) {{
      clearInterval(checkInterval);
      const deptSet = new Set();
      searchIndex.forEach(entry => deptSet.add(entry[2]));
      const sel = document.getElementById('dept-filter');
      const sorted = Array.from(deptSet).sort((a, b) => {{
        if (a.toLowerCase() === 'general') return 1;
        if (b.toLowerCase() === 'general') return -1;
        return a.localeCompare(b);
      }});
      sorted.forEach(d => {{
        if (!ALL_DEPTS.has(d)) {{
          ALL_DEPTS.add(d);
          const opt = document.createElement('option');
          opt.value = d;
          opt.textContent = d;
          sel.appendChild(opt);
        }}
      }});
    }}
  }}, 500);
  // Stop checking after 30s
  setTimeout(() => clearInterval(checkInterval), 30000);
}})();
</script>
<script>
// Coach marks for first-time visitors
(function() {{
  if (localStorage.getItem('coach_done') || location.hash.length > 1) return;

  let step = 0;
  const overlay = document.createElement('div');
  overlay.className = 'coach-overlay';
  const highlight = document.createElement('div');
  highlight.className = 'coach-highlight';
  highlight.style.position = 'fixed';
  const tooltip = document.createElement('div');
  tooltip.className = 'coach-tooltip';
  tooltip.style.position = 'fixed';

  function positionAt(el, tipSide) {{
    const r = el.getBoundingClientRect();
    highlight.style.left = (r.left - 4) + 'px';
    highlight.style.top = (r.top - 4) + 'px';
    highlight.style.width = (r.width + 8) + 'px';
    highlight.style.height = (r.height + 8) + 'px';
    if (tipSide === 'right') {{
      tooltip.style.left = (r.right + 16) + 'px';
      tooltip.style.top = (r.top) + 'px';
      tooltip.querySelector('.coach-arrow').className = 'coach-arrow left';
    }} else if (tipSide === 'bottom') {{
      tooltip.style.left = (r.left) + 'px';
      tooltip.style.top = (r.bottom + 16) + 'px';
      tooltip.querySelector('.coach-arrow').className = 'coach-arrow top';
    }}
  }}

  function showStep1() {{
    step = 1;
    const firstNav = document.querySelector('.nav-item');
    if (!firstNav) return cleanup();
    tooltip.innerHTML = '<div class="coach-arrow left"></div><div class="coach-step">Step 1 of 2</div><div class="coach-text">Click a university to see its thesis and dissertation records.</div><button class="coach-dismiss" onclick="window._coachNext()">Got it</button>';
    document.body.appendChild(overlay);
    document.body.appendChild(highlight);
    document.body.appendChild(tooltip);
    positionAt(firstNav, 'right');
  }}

  function showStep2() {{
    step = 2;
    // Wait for content to load, then highlight first department
    const waitForDept = setInterval(() => {{
      const dept = document.querySelector('.dept-header');
      if (dept) {{
        clearInterval(waitForDept);
        tooltip.innerHTML = '<div class="coach-arrow top"></div><div class="coach-step">Step 2 of 2</div><div class="coach-text">Expand a field to see individual names, years, and links to the original thesis.</div><button class="coach-dismiss" onclick="window._coachNext()">Done</button>';
        positionAt(dept, 'bottom');
      }}
    }}, 200);
    // Timeout safety
    setTimeout(() => clearInterval(waitForDept), 5000);
  }}

  function cleanup() {{
    overlay.remove();
    highlight.remove();
    tooltip.remove();
    localStorage.setItem('coach_done', '1');
  }}

  window._coachNext = function() {{
    if (step === 1) {{
      // Click the first university to demo
      const firstNav = document.querySelector('.nav-item');
      if (firstNav) firstNav.click();
      showStep2();
    }} else {{
      cleanup();
    }}
  }};

  // Also dismiss if they click the overlay
  overlay.addEventListener('click', cleanup);

  // Start after a short delay
  setTimeout(showStep1, 600);
}})();

// Analytics beacon
(function(){{
  var API='https://analytics.andy-barr.com/collect';
  var sid=sessionStorage.getItem('_sid');
  if(!sid){{sid=Math.random().toString(36).substr(2,12);sessionStorage.setItem('_sid',sid);}}
  function send(data){{data.sid=sid;data.ua=navigator.userAgent;data.screen=screen.width+'x'+screen.height;navigator.sendBeacon?navigator.sendBeacon(API,JSON.stringify(data)):fetch(API,{{method:'POST',body:JSON.stringify(data),keepalive:true}});}}
  send({{type:'pageview',page:location.pathname+location.hash,referrer:document.referrer}});
  var clicks=0;
  document.addEventListener('click',function(e){{
    clicks++;
    var t=e.target.closest('.nav-item,.dept-header,.toggle-wrap,a.name-link');
    if(t){{var lbl=t.dataset.key||t.textContent.trim().substr(0,40);send({{type:'click',target:lbl,uni:currentKey||''}});}}
  }});
}})();
</script>
<script>
// WebMCP hooks — register tools for AI agent interaction
(function() {{
  if (!navigator.modelContext) return; // WebMCP not available

  const mc = navigator.modelContext;

  mc.registerTool({{
    name: 'list_universities',
    description: 'List all universities available on this site with their NRA percentage and record counts',
    inputSchema: {{ type: 'object', properties: {{}}, required: [] }},
    async execute() {{
      return {{ content: [{{ type: 'text', text: JSON.stringify(DATA.map(u => ({{ key: u.key, name: u.name, nra: u.nra, records: u.count }}))) }}] }};
    }}
  }});

  mc.registerTool({{
    name: 'get_university_data',
    description: 'Get thesis/dissertation records for a specific university. Returns records with department, year, author name, degree type, and title.',
    inputSchema: {{
      type: 'object',
      properties: {{
        university_key: {{ type: 'string', description: 'University key (e.g. purdue, mit, stanford). Use list_universities to find valid keys.' }}
      }},
      required: ['university_key']
    }},
    async execute(args) {{
      const key = args.university_key;
      if (UNI_CACHE[key]) return {{ content: [{{ type: 'text', text: JSON.stringify(UNI_CACHE[key]) }}] }};
      const resp = await fetch(DATA_DIR + '/' + key + '.json');
      if (!resp.ok) return {{ content: [{{ type: 'text', text: 'University not found: ' + key }}] }};
      const uni = await resp.json();
      UNI_CACHE[key] = uni;
      return {{ content: [{{ type: 'text', text: JSON.stringify(uni) }}] }};
    }}
  }});

  mc.registerTool({{
    name: 'get_data_catalog',
    description: 'Get the full data catalog with version info, schemas, and links to all datasets and government sources',
    inputSchema: {{ type: 'object', properties: {{}}, required: [] }},
    async execute() {{
      const resp = await fetch('/catalog.json');
      const catalog = await resp.json();
      return {{ content: [{{ type: 'text', text: JSON.stringify(catalog) }}] }};
    }}
  }});

  mc.registerTool({{
    name: 'get_taxonomy',
    description: 'Get the department taxonomy mapping variant department names to 44 canonical STEM and non-STEM categories',
    inputSchema: {{ type: 'object', properties: {{}}, required: [] }},
    async execute() {{
      const resp = await fetch('/data/taxonomy.json');
      const tax = await resp.json();
      return {{ content: [{{ type: 'text', text: JSON.stringify(tax) }}] }};
    }}
  }});

  mc.registerTool({{
    name: 'navigate_to_university',
    description: 'Navigate the page to show a specific university. Optionally expand a specific department.',
    inputSchema: {{
      type: 'object',
      properties: {{
        university_key: {{ type: 'string', description: 'University key (e.g. purdue, mit)' }},
        department: {{ type: 'string', description: 'Optional: department name to auto-expand' }}
      }},
      required: ['university_key']
    }},
    async execute(args) {{
      showUni(args.university_key);
      if (args.department) {{
        window._activeDeptFilter = args.department;
      }}
      return {{ content: [{{ type: 'text', text: 'Navigated to ' + args.university_key }}] }};
    }}
  }});

}})();
</script>
</body>
</html>"""


def load_all(stem_filter='stem'):
    """Load records for all CONFIGS with the given STEM filter."""
    data_by_key = {}

    for config in CONFIGS:
        if not os.path.exists(config['file']):
            continue

        # Inject the stem filter into each config
        cfg = dict(config)
        cfg['_stem_filter'] = stem_filter

        records = load_records(cfg)
        key = cfg['key']
        if cfg.get('_merge') and key in data_by_key:
            data_by_key[key][3].extend(records)
        else:
            entry = [cfg['key'], cfg['name'], cfg['nra'], records]
            data_by_key[key] = entry

    return [(e[0], e[1], e[2], e[3]) for e in data_by_key.values()]


def write_data_files(all_data, data_dir):
    """Write per-university JSON files and a search index."""
    import json
    os.makedirs(data_dir, exist_ok=True)

    search_entries = []  # lightweight search index

    for uni_key, uni_name, nra, records in all_data:
        compact = []
        for r in records:
            compact.append([
                r['dept'], r['year'], r['name'],
                r['classification'] or '', r['confidence'] or '',
                r['title'][:90], r['url'], r.get('degree', ''),
            ])
            # Add to search index: just name + dept, enough for matching
            search_entries.append([uni_key, r['name'], r['dept'], r['year']])

        uni_json = json.dumps({
            'key': uni_key, 'name': uni_name, 'nra': nra,
            'records': compact,
        }, ensure_ascii=False, separators=(',', ':'))

        with open(os.path.join(data_dir, f'{uni_key}.json'), 'w') as f:
            f.write(uni_json)

    # Write search index
    with open(os.path.join(data_dir, '_search.json'), 'w') as f:
        json.dump(search_entries, f, ensure_ascii=False, separators=(',', ':'))

    total_size = sum(os.path.getsize(os.path.join(data_dir, fn)) for fn in os.listdir(data_dir))
    print(f"  Data files: {data_dir}/ ({len(all_data)} universities, {total_size/1024/1024:.1f} MB total)")


def main():
    for label, stem_filter, html_file, data_subdir in [
        ("STEM", "stem", "site/stem.html", "site/data/stem"),
        ("NON-STEM", "non-stem", "site/non_stem.html", "site/data/nonstem"),
    ]:
        print(f"=== {label} ===", flush=True)
        data = load_all(stem_filter)
        total = sum(len(u[3]) for u in data)
        print(f"  {total:,} records across {len(data)} schools")

        write_data_files(data, data_subdir)
        html = build_html(data, mode=stem_filter)
        with open(html_file, 'w') as f:
            f.write(html)
        print(f"→ {html_file} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
