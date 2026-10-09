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
def _data_ask_count() -> int:
    """How many asks the Data Asks page actually carries.

    Read from the built data rather than written here. The description said
    "Eight requests" after the page had grown past eight, and because the
    assistant ships this site map in its bundle it repeated the eight to
    readers.
    """
    import json as _json
    p = os.path.join(SITE, "data", "data_asks.json")
    if not os.path.exists(p):
        return 0
    with open(p) as fh:
        return len(_json.load(fh)["asks"])


DESCRIPTIONS = {
    "index.html": "Landing page and navigation hub for the whole site.",
    "overview.html": "National overview: the headline picture in one page.",
    "stem.html": "National STEM landing page: charts plus the sidebar to every university page.",
    "non_stem.html": "Non-STEM dissertation records and the same per-university breakdown.",
    "pipeline.html": "Cross-dataset analysis: F-1 to PhD to H-1B to green card.",
    "immigration.html": "Per-university H-1B, OPT, LCA and PERM cards.",
    "presentation.html": "The presentation: a twelve-slide deck on the concentration of non-resident alien doctorates by field and department.",
    "industries.html": "Five industries the United States cannot offshore -- mining, petroleum, aerospace, battery technology and nuclear -- compared by the non-resident share of the research doctorates that staff them, and by whether the work itself requires US citizenship.",
    "industries/grid.html": "How many credentials the United States awards each year in the programmes that staff generation, transmission and the electrical trade. Counts rather than shares, because Americans earn essentially all of them and the question is the size of the pipeline. For the trades these counts are a floor: IPEDS covers Title IV institutions and misses union and employer apprenticeships.",
    "industries/ai.html": "Artificial intelligence, computer science and data science doctorates, with the American share at bachelors, masters and doctorate set side by side.",
    "industries/petroleum.html": "Petroleum engineering doctorates: the highest non-resident share of any field on this site, with the programmes and institutions behind it.",
    "industries/mining.html": "Mining, mineral and metallurgical engineering doctorates -- a very small national cohort, mostly non-resident.",
    "industries/battery.html": "The materials pipeline behind battery technology. IPEDS publishes no battery category, so this page is a declared proxy and says so.",
    "industries/aerospace.html": "Aerospace engineering doctorates. Much of the work is export-controlled under ITAR, which limits access to US persons -- a category that includes lawful permanent residents and is not a security clearance.",
    "industries/nuclear.html": "Nuclear engineering doctorates. Unescorted access at a commercial reactor needs NRC authorisation under 10 CFR 73.56, which is a background check rather than a clearance; DOE L and Q authorisations are clearances and do require citizenship.",
    "state-agencies.html": ("Which arms of state government sponsor H-1B "
                            "workers, and for what. Approvals by agency and "
                            "state from the USCIS Employer Data Hub, with the "
                            "job titles and wages from the employers' own "
                            "certified Labor Department applications. "
                            "Universities, counties and cities are excluded. "
                            "Sponsoring an H-1B is lawful and the page says "
                            "so."),
    "security.html": ("The Justice Department's own register of China-related "
                      "prosecutions, parsed from the page DOJ archived in 2021: "
                      "who each defendant was according to DOJ's own headline, "
                      "what each case was about, which entries were announced as "
                      "an accusation and nothing more, and the four entries that "
                      "are not prosecutions at all. Plus the cases charged since "
                      "the list stopped being updated, which no official list "
                      "covers. A charge is an allegation; this page never says "
                      "anyone is guilty."),
    "eor.html": ("Employer-of-record services: how an American company employs a "
                 "foreign worker with no visa, no petition and no cap, because "
                 "the worker never enters the United States. No LCA, no I-129 and "
                 "no SEVIS record exists for such a hire, so no federal file "
                 "counts it -- which makes every visa figure on this site a floor "
                 "rather than a total. Counts the vendors' own pages that name "
                 "the H-1B, and which vendors reference each other."),
    "bodyshops.html": "The firms that sponsor H-1B workers and place them at other companies, identified from their own certified Labor Department filings: six-digit industry, H-1B dependency, third-party placement, chosen wage tier, the same-occupation pay gap between placed and directly-hired workers, and every employer the Labor Department has debarred.",
    "name-lists.html": "The entry point for the thesis and dissertation name lists: 708,393 doctoral and master's records from 106 American universities, 1966-2026, with the author, department, year and title of each, every name linking to the awarding university's own repository. The most directly verifiable material on the site.",
    "postdocs.html": "Postdoctoral appointees by citizenship from the NSF survey: 58.3% of the national postdoctoral workforce holds a temporary visa, the nine universities named in the October 2026 J-1 investigation come to 60.7%, and who pays for the posts.",
    "visa-schools.html": "The 57 US colleges where foreign students are most of the graduate enrolment: growth since 2022, the federal student aid they take in, what the nonprofits report paying recruiting firms, and how visa programmes substitute for each other.",
    "live.html": "Live dashboard: degrees by field, level and residency status. Pick a field and the charts redraw, or press Start talking and ask out loud -- the voice session draws the same charts. Voice has its own daily budget and refuses politely when it is spent; the dashboard works either way.",
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
    #: Counted, not typed. The page grew from eight asks to 24 and this
    #: line still said eight, so the assistant told readers eight.
    "data_requests.html": f"{_data_ask_count()} asks for federal data that is collected or was once published, with the agency, the form and what each would settle.",
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
# The closing quote must be the SAME one that opened the attribute. Matching
# either quote ended the description at the first apostrophe, so every page
# whose description contained one was cut mid-word: the master's expansion was
# described to readers as "How US core-STEM master".
DESC_RE = re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=(["\'])(.*?)\1',
                     re.I | re.S)
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
        desc = _text(dm.group(2))[:200] if dm else title
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
        # Clean paths: the site serves /industries/mining, and this map is
        # what the assistant is told are the only valid link targets. Handing
        # it .html would make it the one place on the site still saying so.
        "path": "/" + (rel[:-5] if rel.endswith(".html") else rel),
        "title": title,
        "desc": desc,
        "widget": "chat-widget.js" in html,
        # Deliberately "open" for every page: the anchor scheme is in flight,
        # so fragments are carried opaquely and never rejected (contract 4.5.5).
        "anchors": "open",
        "sections": sections[:60],
    }


#: Subdirectories whose pages are real destinations and must be scanned like
#: top-level ones. universities/ is deliberately NOT here: its 106 pages are
#: carried separately as `university_paths` so they do not swamp the prompt.
#: states/ is out for the same reason and carried as `state_paths`: scanning
#: its 52 pages took this file from 57 entries to 104 and from 105 KB to
#: 164 KB, all of it near-identical boilerplate. /states, the hub, IS scanned
#: and is what the assistant should send a reader to first.
#: Without this, /industries/aerospace.html and its four siblings existed, were
#: linked from the sidebar and served fine -- and the assistant could not name
#: them, because this file only ever looked at the top level.
PAGE_DIRS = ("industries",)


def build() -> dict:
    pages = []
    for name in sorted(os.listdir(SITE)):
        if not name.endswith(".html") or name in EXCLUDE:
            continue
        pages.append(scan_page(os.path.join(SITE, name), name))

    for sub in PAGE_DIRS:
        d = os.path.join(SITE, sub)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(".html"):
                continue
            rel = f"{sub}/{name}"
            if rel in EXCLUDE:
                continue
            pages.append(scan_page(os.path.join(d, name), rel))

    unis = []
    idx_path = os.path.join(SITE, "data", "universities_index.json")
    if os.path.exists(idx_path):
        with open(idx_path, encoding="utf-8") as fh:
            idx = json.load(fh)
        for u in idx.get("universities", []):
            key = u.get("key")
            if not key:
                continue
            rel = f"universities/{key}"
            entry = {"key": key, "name": u.get("name", key), "path": "/" + rel}
            if u.get("nra") is not None:
                entry["nra"] = u["nra"]
            unis.append(entry)

    # Every university page is a valid path even though we do not scan all 105.
    uni_dir = os.path.join(SITE, "universities")
    uni_paths = sorted(
        "/universities/" + n[:-5] for n in os.listdir(uni_dir) if n.endswith(".html")
    ) if os.path.isdir(uni_dir) else []

    state_dir = os.path.join(SITE, "states")
    state_paths = sorted(
        "/states/" + n[:-5] for n in os.listdir(state_dir) if n.endswith(".html")
    ) if os.path.isdir(state_dir) else []

    return {
        "version": _dt.date.today().isoformat(),
        "pages": pages,
        "university_paths": uni_paths,
        "universities": unis,
        "state_paths": state_paths,
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
          f"{len(data['state_paths'])} state pages, "
          f"{sum(len(p['sections']) for p in data['pages'])} anchors, "
          f"{os.path.getsize(args.out)/1024:.0f} KB")


if __name__ == "__main__":
    main()
