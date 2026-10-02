#!/usr/bin/env python3
"""The URL rule exists twice and the two copies must agree.

/industries/mining is served by industries/mining.html. That rewrite happens in
a CloudFront function at the edge; scripts/clean_urls.py repeats it in Python
so the local servers the checks run against behave like the real site.

Two copies of one rule is a drift waiting to happen, so this executes both
against the same table of paths. It also pins the regression that hid behind
the migration: a link checker that decided "is this a page?" by looking for a
.html suffix stopped checking every page at once, and still reported success.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from clean_urls import to_path                                  # noqa: E402

EDGE = ROOT / "infra" / "cdn" / "clean-urls.js"

#: Every shape the live site actually serves, including the ones that must be
#: left alone.
PATHS = [
    "/", "/industries", "/industries/", "/industries/mining",
    "/industries/mining.html", "/industries/grid", "/universities/mit",
    "/index.html", "/catalog.json", "/llms.txt",
    "/data/critical_industries.json", "/og/concentration.png",
    "/data/exports/stem_records.parquet", "/briefing.pdf",
    "/expansion", "/rankings.html",
]


def test_python_mirror_matches_the_edge_function():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    if not EDGE.exists():
        pytest.skip("the private infra checkout is not present")
    # Run the real edge source, with the event shape CloudFront passes it.
    script = (EDGE.read_text() + "\nconst out = {};\n"
              + "for (const u of " + json.dumps(PATHS) + ") {\n"
              + "  out[u] = handler({request: {uri: u, headers: {}}}).uri;\n}\n"
              + "console.log(JSON.stringify(out));\n")
    r = subprocess.run([node, "--input-type=module", "-e", script],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[:400]
    edge = json.loads(r.stdout)
    mine = {u: to_path(u) for u in PATHS}
    assert edge == mine, (
        "the edge function and scripts/clean_urls.py disagree: "
        + ", ".join(f"{u}: edge={edge[u]} python={mine[u]}"
                    for u in PATHS if edge[u] != mine[u]))


def test_assets_are_never_rewritten():
    for p in ("/catalog.json", "/llms.txt", "/data/x.json", "/og/a.png",
              "/data/exports/stem_records.parquet", "/robots.txt"):
        assert to_path(p) == p, f"{p} must be served as-is"


def test_pages_resolve_with_and_without_the_extension():
    assert to_path("/industries/mining") == "/industries/mining.html"
    assert to_path("/industries/mining.html") == "/industries/mining.html"
    assert to_path("/industries") == "/industries.html"
    assert to_path("/industries/") == "/industries.html"
    assert to_path("/") == "/"


def test_the_link_checker_still_treats_clean_paths_as_pages():
    """It decided "is this a page?" by looking for .html. When links dropped
    the extension that skipped every page, and the suite went from 7,364
    checks to 98 while still printing success."""
    src = (ROOT / "scripts" / "check_sidebar_links.py").read_text()
    assert 'if not it["href"].endswith(".html"):\n            continue' not in src, \
        "a .html suffix test here skips every clean link on the site"
