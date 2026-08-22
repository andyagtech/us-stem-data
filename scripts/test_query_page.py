#!/usr/bin/env python3
"""Guard the browser query page: /query.html and the Parquet exports it reads.

This surface had no tests, and it is unusual in this project: the SQL runs in
the VISITOR'S BROWSER, not on a server. hyparquet fetches
site/data/exports/*.parquet from CloudFront and queries them locally. Nothing
server-side executes a query, so nothing server-side can notice when the page
and the data disagree.

Two disagreements were live when this file was written:

  * query.html advertises "291K STEM + 136K Non-STEM records". The exports hold
    371,145 and 149,170 -- the counts were regenerated on 2026-08-19 after the
    duckdb gap and the prose was never updated. scripts/test_site.py has a
    check for exactly this drift but only inspects index.html.
  * The assistant's suggest_query tool describes a nine-column schema to
    readers. Nothing verified that description against the files.

Also measures download size and time, because the page fetches whole files via
arrayBuffer() rather than HTTP Range requests: every query, however small,
pulls all 23 MB. That is fine on a laptop and painful on mobile, so a size
regression is worth catching.

Usage:
    python3 scripts/test_query_page.py            # against the live site
    python3 scripts/test_query_page.py --local    # against site/ on disk
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE = "https://phd-demographics.andy-barr.com"
EXPORTS = ("stem_records", "nonstem_records")

# The schema cloud/chat/tools.py advertises to readers via suggest_query.
ADVERTISED = ["university", "department", "year", "name", "classification",
              "confidence", "title", "url", "degree"]

# Whole-file fetch: a regression here is felt by every visitor on every query.
SIZE_CEILING_MB = {"stem_records": 25.0, "nonstem_records": 12.0}

_results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    _results.append((bool(ok), name, detail))
    return bool(ok)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local", action="store_true",
                    help="read site/ from disk instead of the live site")
    args = ap.parse_args()

    try:
        import duckdb
    except ModuleNotFoundError:
        sys.exit("duckdb required -- see requirements.txt")

    html = (SITE / "query.html").read_text()

    # --- the page loads the libraries it claims to ------------------------
    check("hyparquet" in html, "query page loads hyparquet")
    check("parquetRead" in html or "parquetMetadataAsync" in html,
          "query page calls the hyparquet reader")

    # --- schema matches what the assistant advertises ---------------------
    for name in EXPORTS:
        p = SITE / "data" / "exports" / f"{name}.parquet"
        if not check(p.exists(), f"{name}.parquet exists"):
            continue
        cols = [r[0] for r in duckdb.sql(
            f"describe select * from '{p}'").fetchall()]
        check(cols == ADVERTISED,
              f"{name} schema matches what suggest_query advertises",
              f"actual {cols}" if cols != ADVERTISED else f"{len(cols)} columns")

        rows = duckdb.sql(f"select count(*) from '{p}'").fetchone()[0]
        mb = p.stat().st_size / 1048576
        check(mb <= SIZE_CEILING_MB[name],
              f"{name} stays under its download ceiling",
              f"{mb:.1f} MB of {SIZE_CEILING_MB[name]} MB, {rows:,} rows")

        # The page prints a record count in its table picker. It must match.
        label = re.search(rf"file: '{name}\.parquet',\s*label: '([^']+)'", html)
        if label:
            claimed = re.search(r"\(([\d.]+)K\)", label.group(1))
            if claimed:
                claimed_n = float(claimed.group(1)) * 1000
                close = abs(claimed_n - rows) / rows < 0.05
                check(close,
                      f"{name} label matches the file",
                      f"page says {claimed.group(1)}K, file has {rows:,}")

    # --- SQL guardrails the page and the tool both promise ----------------
    flat = re.sub(r"\s+", " ", html)
    check("LIMIT" in html, "the page enforces or documents a LIMIT")
    # Flatten first: these promises are written across source lines, so a raw
    # substring match reports a missing guardrail that is actually present.
    tools_src = re.sub(r'"\s*\n\s*"', "", (ROOT / "cloud" / "chat" / "tools.py").read_text())
    if "suggest_query" in tools_src:
        for phrase, label in (("no semicolons", "no semicolons"),
                              ("LIMIT is mandatory", "mandatory LIMIT"),
                              ("Read-only SELECT", "read-only SELECT")):
            check(phrase in tools_src,
                  f"suggest_query still promises {label}")

    # --- third-party library pins -----------------------------------------
    # The page imports hyparquet, hyparquet-compressors and squirreling from
    # esm.sh at RUNTIME, so whatever those URLs resolve to is what every visitor
    # executes. A floating pin (@1, @0) means the page's behaviour can change
    # with no deploy and no commit of ours.
    #
    # That is not hypothetical here: hyparquet ships roughly weekly (138
    # releases; 1.29.1 landed 2026-08-21) and squirreling moved 0.15 -> 0.16 on
    # 2026-08-18. squirreling is pre-1.0, where semver permits a MINOR bump to
    # break the API outright. Under @0 that change reached production
    # untested.
    #
    # So: exact pins are required, and this check reports when a newer version
    # exists rather than failing on it -- being deliberately behind is fine,
    # being unknowingly adrift is not.
    imports = re.findall(r"https://esm\.sh/([a-z-]+)@([0-9][^\"'/]*)", html)
    check(bool(imports), "query page imports are discoverable",
          f"{len(imports)} found")
    for pkg, ver in imports:
        exact = re.fullmatch(r"\d+\.\d+\.\d+", ver) is not None
        check(exact, f"{pkg} is pinned to an exact version",
              f"pinned '{ver}'" + ("" if exact else " - floats to whatever is latest"))

    if not args.local:
        import urllib.error
        for pkg, ver in imports:
            try:
                with urllib.request.urlopen(
                        f"https://registry.npmjs.org/{pkg}/latest", timeout=20) as r:
                    latest = json.load(r).get("version")
            except Exception:                              # noqa: BLE001
                continue
            behind = latest and latest != ver
            # Report, do not fail: an intentional lag is a valid choice.
            check(True, f"{pkg} pin vs npm latest",
                  f"pinned {ver}, latest {latest}"
                  + ("  <-- UPDATE AVAILABLE" if behind else "  (current)"))

    # --- live reachability and timing -------------------------------------
    if not args.local:
        for name in EXPORTS:
            url = f"{BASE}/data/exports/{name}.parquet"
            t0 = time.time()
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=120) as r:
                    blob = r.read()
                dt = time.time() - t0
                check(len(blob) > 0, f"{name}.parquet served",
                      f"{len(blob)/1048576:.1f} MB in {dt:.2f}s "
                      f"({len(blob)/1048576/max(dt,0.001):.0f} MB/s)")
            except Exception as exc:                      # noqa: BLE001
                check(False, f"{name}.parquet served", f"{type(exc).__name__}")

    failed = [r for r in _results if not r[0]]
    for ok, name, detail in _results:
        print(f"  {'pass' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    print(f"\n{len(_results) - len(failed)}/{len(_results)} query-page checks pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
