#!/usr/bin/env python3
"""
Build site/data/chat/site_map.json — the shared page/anchor registry used by
both the chat Lambda (path validation, prompt rendering) and chat-widget.js
(nav-token resolution, target re-validation).

Contract: chat_contract.md section 4.10.

  * Every page defaults to  "anchors": "open"  — the anchor scheme is being
    rationalised in a parallel workstream, so fragments stay opaque and are
    never validated.  `sections` is populated anyway (it is useful for
    labelling and for the prompt) but is advisory while anchors == "open".
  * Nothing here hard-codes a fragment format.

Usage:
    python3 scripts/build_site_map.py [--out site/data/chat/site_map.json]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
from atomic_write import write_json
from private_pages import PRIVATE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")

# Pages the assistant should never route a reader to.
# concentration.html is a redirect stub kept for links shared before the
# deck moved to presentation.html; the assistant must send people to the
# page itself, not the redirect.
# The private pages come from one shared declaration -- the assistant used to
# carry analytics.html in its navigation index and would happily send a reader
# to the owner's dashboard.
# name_lists.html and concentration.html are redirect stubs; the
# assistant must send people to the page itself, not the bounce.
EXCLUDE = {"webmcp.html", "submit.html", "concentration.html",
           "name_lists.html"} | set(PRIVATE)

# Hand-maintained one-line descriptions.  A page missing from this table falls
# back to its <meta name="description">, then to its <title>.
DESCRIPTIONS = {
    "index.html": "Landing page and navigation hub for the whole site.",
    "overview.html": "National overview: the headline picture in one page.",
    "stem.html": "National STEM landing page: charts plus the sidebar to every university page.",
    "non_stem.html": "Non-STEM dissertation records and the same per-university breakdown.",
    "pipeline.html": "Cross-dataset analysis: F-1 to PhD to H-1B to green card.",
    "immigration.html": "Per-university H-1B, OPT, LCA and PERM cards.",
    "presentation.html": "The presentation: a twelve-slide deck on the concentration of non-resident alien doctorates by field and department.",
    "bodyshops.html": "The firms that sponsor H-1B workers and place them at other companies, identified from their own certified Labor Department filings: six-digit industry, H-1B dependency, third-party placement, chosen wage tier, the same-occupation pay gap between placed and directly-hired workers, and every employer the Labor Department has debarred.",
    "visa-schools.html": "The 57 US colleges where foreign students are most of the graduate enrolment: growth since 2022, the federal student aid they take in, what the nonprofits report paying recruiting firms, and how visa programmes substitute for each other.",
    "live.html": "Live dashboard: degrees by field, level and residency status; pick a field and the charts redraw.",
    "distributions.html": "Distribution charts: departments by non-resident share nationally, by programme, and inside one university.",
    "china.html": "China outbound: US decline, global diversification, return rates.",
    "india.html": "India outbound: STEM and medical pipelines.",
    "canada.html": "Canada: IRCC study permits and the post-cap decline.",
    "uk.html": "UK: HESA enrolment and the Graduate Route.",
    "eu.html": "EU and Germany: DAAD international enrolment.",
    "mexico.html": "Mexico outbound mobility.",
    "vwp.html": "Visa Waiver Program: 41 countries and their overstay rates.",
    "workforce.html": "NSF Survey of Doctorate Recipients: foreign-born share of the US doctoral STEM workforce.",
    "medical.html": "Medical education pipeline: IMGs, residency match, FMGE.",
    "usaid.html": "USAID-funded higher education programmes.",
    "quality.html": "Data quality: coverage, classification confidence, known gaps.",
    "ipeds_dashboard.html": "IPEDS STEM PhD completions, 1984 to 2024.",
    "stem_dashboard.html": "Interactive STEM dashboard.",
    "query.html": "SQL query interface over the raw dissertation records (runs in the browser).",
    "data_sources.html": "Data sources and methodology.",
    "contents.html": "Table of contents: every page on the site in one list, including the university pages.",
    "briefing.html": "The briefing as a PDF, on white or dark paper: 41 pages built from federal data.",
    "data_requests.html": "Eight requests for federal data that is collected and not published, with the agency and form for each.",
    "implementation.html": "Pipeline architecture and the six-step build process.",
    "about.html": "About this site and its author.",
    "analytics.html": "Site analytics.",
    "name_lists.html": "Name-origin classification lists.",
    "department_reports.html": "Per-department classification reports.",
    "caltech_dashboard.html": "Caltech case-study dashboard.",
    "caltech_field_demographics.html": "Caltech field-level demographics.",
    "caltech_ipeds_tables.html": "Caltech IPEDS tables.",
}

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
DESC_RE = re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', re.I | re.S)
ID_RE = re.compile(r'\bid=["\']([A-Za-z0-9_:.\-]+)["\']')
H_RE = re.compile(r"<(h[1-4])\b[^>]*\bid=[\"']([A-Za-z0-9_:.\-]+)[\"'][^>]*>(.*?)</\1>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")

# ids that are plainly plumbing, never a navigation target
NOISE_PREFIXES = ("chat-", "cb-", "js-")
NOISE_EXACT = {"app", "root", "main", "content", "wrapper", "container", "sidebar",
               "header", "footer", "nav", "search", "modal", "overlay", "tooltip"}


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", s)).strip()


def _labels_for(html: str) -> dict:
    """id -> heading text, for ids that sit on a heading element."""
    out = {}
    for _tag, hid, inner in H_RE.findall(html):
        label = _text(inner)[:60]
        if label:
            out[hid] = label
    return out


def _kind_for(hid: str) -> str:
    low = hid.lower()
    if "chart" in low or "canvas" in low:
        return "chart"
    if "table" in low:
        return "table"
    if low.endswith("-section") or low.endswith("_section"):
        return "section"
    return "anchor"


def scan_page(path: str, rel: str) -> dict:
    with open(path, encoding="utf-8", errors="replace") as fh:
        html = fh.read()
    m = TITLE_RE.search(html)
    title = _text(m.group(1)) if m else rel
    title = re.sub(r"\s*[—|-]\s*(PhD Demographics|USDS China)\s*$", "", title).strip() or rel
    desc = DESCRIPTIONS.get(rel)
    if not desc:
        dm = DESC_RE.search(html)
        desc = _text(dm.group(1))[:200] if dm else title
    labels = _labels_for(html)
    seen, sections = set(), []
    for hid in ID_RE.findall(html):
        if hid in seen:
            continue
        seen.add(hid)
        low = hid.lower()
        if low in NOISE_EXACT or low.startswith(NOISE_PREFIXES):
            continue
        sections.append({
            "id": hid,
            "label": labels.get(hid, hid.replace("-", " ").replace("_", " ")),
            "kind": _kind_for(hid),
            "dynamic": False,
        })
    return {
        "path": "/" + rel,
        "title": title,
        "desc": desc,
        "widget": "chat-widget.js" in html,
        # Deliberately "open" for every page: the anchor scheme is in flight,
        # so fragments are carried opaquely and never rejected (contract 4.5.5).
        "anchors": "open",
        "sections": sections[:60],
    }


def build() -> dict:
    pages = []
    for name in sorted(os.listdir(SITE)):
        if not name.endswith(".html") or name in EXCLUDE:
            continue
        pages.append(scan_page(os.path.join(SITE, name), name))

    unis = []
    idx_path = os.path.join(SITE, "data", "universities_index.json")
    if os.path.exists(idx_path):
        with open(idx_path, encoding="utf-8") as fh:
            idx = json.load(fh)
        for u in idx.get("universities", []):
            key = u.get("key")
            if not key:
                continue
            rel = f"universities/{key}.html"
            entry = {"key": key, "name": u.get("name", key), "path": "/" + rel}
            if u.get("nra") is not None:
                entry["nra"] = u["nra"]
            unis.append(entry)

    # Every university page is a valid path even though we do not scan all 105.
    uni_dir = os.path.join(SITE, "universities")
    uni_paths = sorted(
        "/universities/" + n for n in os.listdir(uni_dir) if n.endswith(".html")
    ) if os.path.isdir(uni_dir) else []

    return {
        "version": _dt.date.today().isoformat(),
        "pages": pages,
        "university_paths": uni_paths,
        "universities": unis,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(SITE, "data", "chat", "site_map.json"))
    args = ap.parse_args()
    data = build()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    write_json(args.out, data, separators=(",", ":"), ensure_ascii=False)
    print(f"wrote {args.out}: {len(data['pages'])} pages, "
          f"{len(data['university_paths'])} university pages, "
          f"{sum(len(p['sections']) for p in data['pages'])} anchors, "
          f"{os.path.getsize(args.out)/1024:.0f} KB")


if __name__ == "__main__":
    main()
