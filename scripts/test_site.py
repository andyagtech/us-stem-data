#!/usr/bin/env python3
"""Exhaustive site tests: links, accessibility, performance budget, integrity.

WHY THIS EXISTS

The site was audited by hand and six accessibility failures, one site-wide
broken link and a render-blocking script turned up. A hand audit finds those
once; it does not stop them coming back. This runs the same checks on demand,
against local files or the live site.

The broken link is the instructive one. `/data_catalog.json` was referenced from
six places including sidebar.js -- which renders on EVERY page -- while the real
file is `catalog.json`. Nothing surfaced it because a 404 on a nav link looks
like nothing at all until someone clicks.

WHAT IT CHECKS

  links          every href and src on the page, plus sidebar-injected nav,
                 resolved against the live site. In-page #anchors are checked
                 against ids in the document.
  a11y           landmarks, skip link, heading order, focus styles, table
                 semantics, live regions, reduced motion, alt text, link text
  perf           render-blocking resources and a gzipped payload budget
  integrity      the JSON the page depends on parses, has the expected shape,
                 and its headline figures match what the HTML claims

Usage:
    python3 scripts/test_site.py                  # local files + live links
    python3 scripts/test_site.py --offline        # skip anything needing network
    python3 scripts/test_site.py --page live.html
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE = "https://phd-demographics.andy-barr.com"
PAYLOAD_BUDGET_KB = 80        # gzipped, first visit

_results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    _results.append((bool(ok), name, detail))
    return bool(ok)


def head(url: str, timeout: int = 20) -> int:
    req = urllib.request.Request(url, method="GET",
                                 headers={"User-Agent": "site-test/1.0",
                                          "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


# ---------------------------------------------------------------- links

def test_links(html: str, offline: bool):
    sidebar = (SITE / "sidebar.js")
    hrefs = set(re.findall(r'href="([^"]+)"', html))
    hrefs |= set(re.findall(r'src="([^"]+)"', html))
    if sidebar.exists():
        hrefs |= set(re.findall(r"href:\s*'([^']+)'", sidebar.read_text()))

    ids = set(re.findall(r'id="([^"]+)"', html))
    anchors = {h for h in hrefs if h.startswith("#")}
    for a in sorted(anchors):
        check(a[1:] in ids, f"anchor {a} resolves", "no matching id")

    if offline:
        return
    remote = sorted(h for h in hrefs
                    if not h.startswith("#") and not h.startswith("mailto:"))
    broken = []
    for h in remote:
        url = h if h.startswith("http") else BASE + ("" if h.startswith("/") else "/") + h
        code = head(url)
        if code != 200:
            broken.append(f"{code} {h}")
    check(not broken, f"all {len(remote)} links resolve", "; ".join(broken[:6]))


# ----------------------------------------------------------------- a11y

def test_a11y(html: str):
    check("<html lang=" in html, "html has lang")
    check('name="viewport"' in html, "viewport meta present")
    check(html.count("<h1") == 1, "exactly one h1", f"found {html.count('<h1')}")

    levels = [int(m) for m in re.findall(r"<h([1-6])\b", html)]
    skips = [f"h{a}->h{b}" for a, b in zip(levels, levels[1:]) if b - a > 1]
    check(not skips, "heading levels never skip", ", ".join(skips))

    check("<main" in html, "main landmark present")
    check("skip-link" in html, "skip link present")
    check(":focus-visible" in html or ":focus" in html,
          "focus styles defined", "keyboard users get no visible focus")
    check("prefers-reduced-motion" in html, "reduced motion honoured")

    imgs = re.findall(r"<img\b[^>]*>", html)
    check(all("alt=" in i for i in imgs), f"all {len(imgs)} images have alt")

    tables = re.findall(r"<table\b.*?</table>", html, re.S)
    for i, t in enumerate(tables):
        if "<th" in t:
            check("scope=" in t, f"table {i+1} th elements use scope")
        check("<caption" in t, f"table {i+1} has a caption")
        if 'id="' in t and ("Loading" in t or "loading" in t):
            check("aria-live" in t, f"table {i+1} JS-filled body is a live region")

    empties = re.findall(r"<a\b[^>]*>\s*</a>", html)
    check(not empties, "no empty links", f"{len(empties)} found")

    btns = re.findall(r"<button\b[^>]*>(.*?)</button>", html, re.S)
    unnamed = [b for b in btns if not re.sub(r"<[^>]+>", "", b).strip()]
    check(not unnamed, f"all {len(btns)} buttons have an accessible name")

    ext = re.findall(r'<a\b[^>]*target="_blank"[^>]*>', html)
    unsafe = [a for a in ext if "noopener" not in a]
    check(not unsafe, "external links carry rel=noopener",
          f"{len(unsafe)} without")


# ----------------------------------------------------------------- perf

def test_perf(html: str, page: str):
    blocking = re.findall(r"<script(?![^>]*(?:defer|async))[^>]*\ssrc=", html)
    check(not blocking, "no render-blocking scripts",
          f"{len(blocking)} blocking")

    total = 0
    parts = [SITE / page]
    parts += [SITE / m.lstrip("/") for m in re.findall(r'src="(/[^"]+\.js)"', html)]
    parts += [SITE / m.lstrip("/") for m in re.findall(r'href="(/data/[^"]+\.json)"', html)]
    missing = []
    for f in parts:
        if f.exists():
            total += len(gzip.compress(f.read_bytes(), 9))
        else:
            missing.append(f.name)
    kb = total / 1024
    check(kb <= PAYLOAD_BUDGET_KB,
          f"first-visit payload within {PAYLOAD_BUDGET_KB} KB budget",
          f"{kb:.0f} KB")
    check(not missing, "every referenced local asset exists", ", ".join(missing))


# ------------------------------------------------------------ integrity

def test_integrity(html: str):
    cases_f = SITE / "data" / "concentration_cases.json"
    cost_f = SITE / "data" / "taxpayer_cost.json"

    if check(cases_f.exists(), "concentration_cases.json present"):
        d = json.loads(cases_f.read_text())
        n = d.get("count", 0)
        check(n == len(d.get("cases", [])), "case count matches array length")
        check(str(n) in html, f"page states the real case count ({n})")
        # The criterion is per-YEAR, not pooled: 70%+ in at least six separate
        # years. A case can satisfy that and still pool below 70 if its two
        # off years were low enough -- Rutgers-Newark does exactly this at
        # 69.3% pooled with 6 of 8 years over the mark. Assert the criterion
        # the dataset actually claims, and surface the pooled spread so a
        # drift in either direction is visible.
        mark = d["criteria"]["high_mark_pct"]
        need = d["criteria"]["min_high_years"]
        check(all(c["years_at_or_above_mark"] >= need for c in d["cases"]),
              f"every case clears {mark:.0f}% in {need}+ separate years")
        pooled_below = [c for c in d["cases"] if c["share"] < mark]
        check(len(pooled_below) <= 1,
              "at most one case pools below the mark",
              ", ".join(f'{c["institution"]} {c["share"]}%' for c in pooled_below))
        check(all(c["doctorates"] >= d["criteria"]["min_cohort"] for c in d["cases"]),
              "every case clears the cohort floor")
        check("honest_reading" in d, "payload carries the honest-reading note")

    if check(cost_f.exists(), "taxpayer_cost.json present"):
        d = json.loads(cost_f.read_text())
        med = d.get("median_federal_per_doctorate", 0)
        check(med > 0, "median federal-per-doctorate is positive")
        # the hero rounds this to $875K; allow the rounding but catch drift
        check(abs(med - 875_000) < 25_000,
              "hero figure still matches the data", f"median is ${med:,.0f}")
        check("caveat" in d, "payload carries the intensity-ratio caveat")

    # The guided tour states the master's expansion split. It is derived from
    # IPEDS, so a rebuild can move it and leave the narration wrong.
    tour = SITE / "tour.js"
    if tour.exists():
        t = tour.read_text()
        if "159,000" in t or "96,000" in t:
            import csv as _csv, glob as _glob, os as _os, re as _re
            narrow = {"11", "14", "15", "26", "27", "30", "40", "42"}
            files = {}
            for path in _glob.glob(str(ROOT / "data" / "ipeds" / "*_a*.csv")):
                m = _re.search(r"c(\d{4})_a", _os.path.basename(path).lower())
                if m:
                    y = int(m.group(1))
                    if y not in files or "_rv" in path:
                        files[y] = path

            def _tally(year):
                tot = nra = 0
                if year not in files:
                    return None
                with open(files[year], newline="", encoding="utf-8-sig",
                          errors="replace") as fh:
                    for row in _csv.DictReader(fh):
                        if (row.get("AWLEVEL") or "").lstrip("0") != "7":
                            continue
                        if (row.get("CIPCODE") or "").split(".")[0].zfill(2) not in narrow:
                            continue
                        try:
                            tot += int(row.get("CTOTALT") or 0)
                            nra += int(row.get("CNRALT") or 0)
                        except ValueError:
                            continue
                return tot, nra

            a, b = _tally(2012), _tally(2025)
            if a and b:
                added = b[0] - a[0]
                to_nra = b[1] - a[1]
                check(abs(added - 159_000) < 6_000,
                      "tour's seats-added figure still matches IPEDS",
                      f"{added:,}")
                check(abs(to_nra - 96_000) < 6_000,
                      "tour's non-resident-share-of-growth still matches",
                      f"{to_nra:,}")

    check("andybarr@protonmail.com" in html, "contact email present")
    check("andybarr.25" in html, "Signal contact present")
    check("buymeacoffee.com/andybarr" in html or "buymeacoffee" in
          (SITE / "sidebar.js").read_text(), "support link reachable")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", default="index.html")
    ap.add_argument("--offline", action="store_true",
                    help="skip checks that need the network")
    args = ap.parse_args()

    path = SITE / args.page
    if not path.exists():
        sys.exit(f"No such page: {path}")
    html = path.read_text()

    print(f"Testing {args.page}"
          f"{' (offline)' if args.offline else f' against {BASE}'}\n")
    test_links(html, args.offline)
    test_a11y(html)
    test_perf(html, args.page)
    test_integrity(html)

    groups: dict[str, list] = {}
    for ok, name, detail in _results:
        groups.setdefault("PASS" if ok else "FAIL", []).append((name, detail))
    for name, detail in groups.get("PASS", []):
        print(f"  pass  {name}" + (f"  ({detail})" if detail else ""))
    for name, detail in groups.get("FAIL", []):
        print(f"  FAIL  {name}" + (f"  -- {detail}" if detail else ""))

    n_fail = len(groups.get("FAIL", []))
    print(f"\n{len(_results) - n_fail}/{len(_results)} checks pass")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
