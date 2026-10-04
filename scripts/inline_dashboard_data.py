#!/usr/bin/env python3
"""Inline dashboard JSONs into the corresponding HTML pages.

For each (json_path, html_path) pair, find the line `const D = {...};`
in the HTML and replace it with the freshly-loaded JSON. Idempotent —
re-run after changing any extractor.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_SITE = ROOT.parent / "usds_china_private" / "site"

# Each pair: (json_path, html_path, js_var_name)
# js_var_name lets us inject data under a custom variable so a page can have
# multiple data blocks (e.g. canada.html has its own legacy const D + a new const DCN).
PAIRS = [
    ("data/medical/medical_dashboard.json", "medical.html", "D"),
    ("data/nsf_workforce/workforce_dashboard.json", "workforce.html", "D"),
    ("data/canada/canada_dashboard.json", "canada.html", "DCN"),
    ("data/uk/uk_dashboard.json", "uk.html", "DUK"),
    ("data/pipeline/pipeline_funnel.json", "pipeline.html", "PF"),
]


def inline(json_rel, html_name, var_name):
    json_path = ROOT / json_rel
    html_path = PRIVATE_SITE / html_name
    if not json_path.exists():
        print(f"  SKIP {html_name}: {json_path} missing")
        return
    if not html_path.exists():
        print(f"  SKIP {html_name}: {html_path} missing")
        return
    data = json.loads(json_path.read_text())
    js_data = json.dumps(data, separators=(",", ":"))
    html = html_path.read_text()
    pattern = re.compile(
        r"const " + re.escape(var_name) + r" = \{.*?\};",
        flags=re.DOTALL,
    )
    new_html, n = pattern.subn(
        lambda m: f"const {var_name} = {js_data};",
        html,
        count=1,
    )
    if n == 0:
        print(f"  WARN {html_name}: no `const {var_name} = ...;` block found — inject one first")
        return
    html_path.write_text(new_html)
    print(f"  + {html_name} ({var_name}): inlined {len(js_data):,} bytes")


def main():
    print(f"Inlining dashboard data into {PRIVATE_SITE}")
    for json_rel, html_name, var_name in PAIRS:
        inline(json_rel, html_name, var_name)


if __name__ == "__main__":
    main()
