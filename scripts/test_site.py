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

    # Descriptive prose goes stale silently. These are the counts the copy
    # states; assert them against the artifacts that define them.
    import json as _json
    reg = _json.loads((ROOT / "pipeline" / "universities.json").read_text())
    n_uni = len(reg)
    # Any count introduced by "the", "all" or "from" is a claim about the WHOLE
    # set and must equal the registry. Counts phrased "across these N" or
    # "37 of N" are genuine subsets and are deliberately not matched -- the
    # previous version of this check looked for two hardcoded wrong values,
    # 101 and 107, so when the registry went to 106 the 18 places still saying
    # 105 sailed through.
    found = re.findall(r"\b(?:the|all|from)\s+(\d{2,3})\s+universities\b",
                       html, re.I)
    stale = sorted({v for v in found if v != str(n_uni)})
    check(not stale, f"prose university count matches the registry ({n_uni})",
          ", ".join(stale))

    try:
        import duckdb as _dd
        for name, path in (("STEM", "stem_records"), ("non-STEM", "nonstem_records")):
            pq = SITE / "data" / "exports" / f"{path}.parquet"
            if not pq.exists():
                continue
            n = _dd.sql(f"select count(*) from '{pq}'").fetchone()[0]
            # the copy quotes these with thousands separators
            quoted = f"{n:,}"
            # Scan prose only. A bare \d{3},\d{3} also matches the first two
            # channels of every rgba(148,163,184,...) in the stylesheets, so
            # the failure message used to name CSS colours as stale record
            # counts. Strip style blocks and colour functions first.
            prose = re.sub(r"<style\b.*?</style>", " ", html,
                           flags=re.S | re.I)
            prose = re.sub(r"\brgba?\([^)]*\)", " ", prose, flags=re.I)
            # Require a record context. Proximity alone flagged unrelated
            # six-digit figures -- "159,213 core-STEM master's places added"
            # is not a stale record count, it is a different statistic.
            older = [m for m in re.findall(
                         r"\b(\d{3},\d{3})\b(?=[^<]{0,30}?records?\b)", prose)
                     if m != quoted and abs(int(m.replace(",", "")) - n) < 120_000]
            check(quoted in html or not older,
                  f"{name} record count in prose matches the export ({quoted})",
                  ", ".join(older[:3]))
    except ImportError:
        pass

    check("April 2026" not in html, "no stale 'last updated' date in the page")

    # Provenance must stay on the page: it is what separates the federal
    # figures from the name-origin work elsewhere on the site.
    for phrase, label in (
            ("IPEDS Completions", "names IPEDS Completions as the source"),
            ("mandatory", "states that reporting is mandatory"),
            ("Reported, not inferred", "distinguishes reported from inferred"),
            ("Self-reported", "discloses that institutions self-report"),
            ("nces.ed.gov/ipeds", "links to the IPEDS download page")):
        check(phrase in html, f"provenance: {label}")

    # The headline must not make a cost-per-degree claim that the method
    # section disclaims. It said "Taxpayers spend $875,000 per STEM doctorate"
    # while the method list said "an intensity ratio, not a price tag" -- the
    # page arguing with itself, and the first thing a hostile reader quotes.
    import re as _re2
    h1 = _re2.search(r"<h1[^>]*>(.*?)</h1>", html, _re2.S)
    h1_text = _re2.sub(r"<[^>]+>", " ", h1.group(1)) if h1 else ""
    h1_text = _re2.sub(r"\s+", " ", h1_text)
    check(not _re2.search(r"(spend|cost|costs|pays?)\s+\$?875", h1_text, _re2.I),
          "headline does not claim $875K is a cost per degree", h1_text[:70])
    check("intensity ratio" in html,
          "the intensity-ratio caveat is still on the page")

    # The lead arguments must keep their own counter-evidence attached. The
    # displacement reading is the one that gets this refuted, and the page has
    # to state the domestic-growth figures before an opponent does.
    # The page states the domestic figures but does not volunteer a
    # displacement conclusion in either direction; the raw-counts chart plots
    # the domestic line, so the number is visible either way. Assert the
    # figures stay and that the editorialised conclusion does not come back.
    for phrase, label in (
            ("rose 68%", "seats section still states domestic master's growth"),
            ("rose about a third", "method limits still state domestic doctorate growth"),
            # The qualification moved from mid-punch into the method notes,
            # so assert the SUBSTANCE survives rather than one phrasing: the
            # page must still say the contrast is measured and its explanation
            # inferred. Losing that would be a real regression; rewording is not.
            ("contrast is measured; the explanation for it is inferred",
             "the clearance contrast is still qualified as a reading"),
            ("every one of the nineteen fields", "the funding gap states its breadth")):
        check(phrase in html, f"lead argument: {label}")
    for phrase in ("Nobody was pushed out", "Composition, not displacement",
                   "American numbers went up too"):
        check(phrase not in html,
              f"lead argument: does not volunteer '{phrase[:28]}'")

    # --- raw counts ------------------------------------------------------
    # The site was proportion-only until these two panels; shares alone hide
    # whether a rising percentage came from more non-residents or fewer
    # Americans. Both panels are asserted against their own sources.
    dist = (SITE / "distributions.html").read_text()
    for el in ("counts-chart", "masters-chart"):
        check(f'id="{el}"' in dist, f"raw counts: {el} section present")
    djs = (SITE / "distributions.js").read_text()
    check("long_series.json" in djs and "live_bundle.json" in djs,
          "raw counts: both panels are wired to a source")

    ls = json.loads((SITE / "data" / "long_series.json").read_text())["series"]
    first, last = min(ls, key=int), max(ls, key=int)
    check(ls[last]["domestic"] > ls[first]["domestic"],
          "raw counts: domestic doctorates rose over the series",
          f'{ls[first]["domestic"]:,} -> {ls[last]["domestic"]:,}')
    check(all(v["total"] == v["nra"] + v["domestic"] for v in ls.values()),
          "raw counts: total reconciles to nra + domestic in every year")
    # IPEDS never published 1999. The chart must break the line rather than
    # draw a fabricated point through the gap.
    check("1999" not in ls, "raw counts: 1999 absent, as upstream")
    check("stroke-dasharray" in djs and "gap" in djs,
          "raw counts: the missing year is drawn as a break, not interpolated")

    # Regression: build_live_bundle.py mapped only AWLEVEL 7 and 17, never 9,
    # so the doctorate series read 6,202 for 2008 against a true ~29,500 and
    # drew a fabricated five-fold ramp into 2010. Level 9 is the pre-2010
    # research-doctorate coding; both are summed across the 2008-09 migration.
    bundle = json.loads((SITE / "data" / "live_bundle.json").read_text())
    doc = bundle["degrees"]["doctorate"]
    doc_tot = {}
    for fam in doc.values():
        for y, pair in fam.items():
            doc_tot[y] = doc_tot.get(y, 0) + pair[0]
    for y in ("2008", "2009"):
        a, b = doc_tot.get(y, 0), ls[y]["total"]
        check(abs(a - b) / b < 0.02,
              f"raw counts: bundle doctorate {y} matches the long series",
              f"{a:,} vs {b:,}")

    # --- the majority claim does not depend on its baseline ----------------
    mas = bundle["degrees"]["masters"]
    m_tot, m_nra = {}, {}
    for fam in mas.values():
        for y, pair in fam.items():
            m_tot[y] = m_tot.get(y, 0) + pair[0]
            m_nra[y] = m_nra.get(y, 0) + pair[1]
    end = max(m_tot, key=int)
    shares = {}
    for a in range(2008, 2019):
        ya = str(a)
        if ya not in m_tot:
            continue
        nt = m_tot[end] - m_tot[ya]
        shares[a] = 100.0 * (m_nra[end] - m_nra[ya]) / nt
    check(len(shares) == 11, "robustness: eleven baselines measured",
          f"{len(shares)}")
    check(all(v > 50 for v in shares.values()),
          "robustness: non-residents take the majority from every baseline",
          f"min {min(shares.values()):.1f}% from {min(shares, key=shares.get)}")
    check("50.2% and 60.8%" in html,
          "robustness: the stated range matches the computed one",
          f"{min(shares.values()):.1f}%-{max(shares.values()):.1f}%")
    check("does not depend on where you start counting" in html,
          "robustness: the claim is stated on the page")

    # --- the master's expansion page -------------------------------------
    exp = (SITE / "expansion.html").read_text()
    ejs = (SITE / "expansion.js").read_text()
    tu = json.loads((SITE / "data" / "tuition.json").read_text())
    ts, th = tu["series"], tu["headline"]
    tys = sorted(ts, key=int)

    for el in ("vol-chart", "share-chart", "visa-chart", "rate-chart",
               "billed-chart", "index-chart"):
        check(f'id="{el}"' in exp, f"expansion: {el} present")
    check("/expansion.html" in (SITE / "sidebar.js").read_text(),
          "expansion: page is reachable from the sidebar")

    # Never two y-scales on one chart: the billings/sector comparison must be
    # indexed, because $3B and $174B cannot honestly share an axis.
    flat = re.sub(r"\s+", " ", exp)
    check("indexed" in flat.lower() and "cannot honestly share an axis" in flat,
          "expansion: the cross-scale comparison is indexed, not dual-axis")

    # The tuition figure is an estimate and the page must say so, in the same
    # breath as the number, not in a footnote somewhere else.
    for phrase, label in (
            ("sticker price, not receipts", "billings are labelled sticker price"),
            ("It is not federal money", "the estimate is separated from federal funding"),
            ("7.0%", "the assistantship rate that justifies sticker is given"),
            ("This is an estimate", "the estimate is labelled as one")):
        check(phrase in exp, f"expansion: {label}")

    # Every stated figure reconciles with the built data.
    first, last = ts[tys[0]], ts[tys[-1]]
    check(last["median_oos_rate_real"] < first["median_oos_rate_real"],
          "expansion: real sticker price fell, as the page states",
          f'${first["median_oos_rate_real"]:,} -> ${last["median_oos_rate_real"]:,}')
    check(last["median_oos_rate"] > first["median_oos_rate"],
          "expansion: nominal sticker price rose, as the page states")
    lo_b = th["billed_nra_real_last"] * 1.5 / 1e9
    hi_b = th["billed_nra_real_last"] * 2 / 1e9
    check(5.0 <= lo_b and hi_b <= 7.0,
          "expansion: the five-to-seven-billion cohort range holds",
          f"${lo_b:.2f}B-${hi_b:.2f}B")
    fin = [ts[y]["net_tuition_all_levels_real"] for y in tys
           if ts[y]["net_tuition_all_levels_real"]]
    check(fin and fin[-1] < fin[0],
          "expansion: sector net tuition fell in real terms, as the page states",
          f"${fin[0]/1e9:.1f}B -> ${fin[-1]/1e9:.1f}B" if fin else "")
    check(th["growth_pct_real"] > 0 and th["degree_growth_pct"] > 0,
          "expansion: billings and degree counts both rose",
          f'billings {th["growth_pct_real"]:+.1f}%, degrees {th["degree_growth_pct"]:+.1f}%')
    # Price fell while billings rose, so the growth is volume. The page says
    # exactly that; if it ever stops being true the sentence must change.
    check(last["median_oos_rate_real"] < first["median_oos_rate_real"]
          and th["growth_pct_real"] > 0,
          "expansion: 'all of this growth is volume' still holds")
    check("all of this growth is volume" in exp,
          "expansion: the volume-not-price reading is stated")

    # --- the rankings page -------------------------------------------------
    rk = (SITE / "rankings.html").read_text()
    lr = json.loads((SITE / "data" / "level_rankings.json").read_text())
    check("/rankings.html" in (SITE / "sidebar.js").read_text(),
          "rankings: page is reachable from the sidebar")
    for el in ("inst-table", "prog-table", "contrast-list", "biggest-table",
               "level-pick"):
        check(f'id="{el}"' in rk, f"rankings: {el} present")

    for level in ("masters", "doctorate"):
        L = lr["levels"][level]
        f = lr["floors"][level]
        # Every ranked unit must clear the floor the page advertises.
        for kind, floor in (("institutions", f["inst"]), ("programmes", f["prog"])):
            bad = [r for r in L[kind] if r["total"] < floor]
            check(not bad, f"rankings: every {level} {kind[:-1]} clears its floor",
                  f"{len(bad)} below {floor}" if bad else f"floor {floor}")
        # Shares must reconcile with their own numerator and denominator.
        bad = [r for r in L["institutions"]
               if abs(r["share"] - 100 * r["nra"] / r["total"]) > 0.1]
        check(not bad, f"rankings: {level} shares reconcile with their counts")
        check(L["national"]["nra"] < L["national"]["total"],
              f"rankings: {level} national share is a proper fraction",
              f'{L["national"]["share"]}%')
        # The contrast is the strongest claim, so hold it to the tightest test:
        # both sides must clear the floor and the gap must be what is printed.
        for c in L["contrasts"]:
            if (c["high"]["total"] < L["contrast_floor"]
                    or c["low"]["total"] < L["contrast_floor"]
                    or abs(c["gap"] - (c["high"]["share"] - c["low"]["share"])) > 0.15):
                check(False, f"rankings: {level} contrast rows are sound", c["name"])
                break
        else:
            check(True, f"rankings: {level} contrast rows are sound",
                  f'{L["contrasts_total"]} institutions, floor {L["contrast_floor"]}')

    # The OPT/H-1B explanation of the contrast is an inference and must stay
    # labelled as one, exactly like the information-security contrast.
    rkflat = re.sub(r"\s+", " ", rk)
    check("A reading, not a finding" in rkflat,
          "rankings: the contrast explanation is labelled a reading")
    check("does not record who applied" in rkflat,
          "rankings: the page states what IPEDS cannot show")
    check("cohort floor" in rkflat and "denominator on every row" in rkflat,
          "rankings: the page discloses its floors up front")

    # --- the twenty-year tuition arc ---------------------------------------
    rates = tu.get("rates") or {}
    rys = sorted(rates, key=int)
    check(len(rys) >= 18, "tuition arc: at least eighteen years of rates",
          f"{rys[0]}-{rys[-1]}" if rys else "none")
    if rys:
        a, b = rates[rys[0]], rates[rys[-1]]
        peak = max(rys, key=lambda y: rates[y]["ug_ins_real"])
        rise = 100 * (rates[peak]["ug_ins_real"] - a["ug_ins_real"]) / a["ug_ins_real"]
        # The page says undergraduate in-state rose 36% in real terms to its
        # peak. If that ever stops being true the sentence must change.
        check(34 <= rise <= 38,
              "tuition arc: the 36% undergraduate rise still holds",
              f"{rise:.1f}% to {peak}")
        check(rates[peak]["ug_ins_real"] > b["ug_ins_real"],
              "tuition arc: the peak is behind us, as the page states")
        check("36% in real" in re.sub(r"\s+", " ", exp),
              "tuition arc: the rise is stated on the page")
        check('id="arc-chart"' in exp, "tuition arc: the chart is present")

    # --- documentation and metadata consistency ----------------------------
    # Delegated to scripts/check_consistency.py so the checks live in one place
    # and can also gate a build directly. Reported as a single assertion here;
    # run that script for the breakdown.
    import subprocess as _sp
    _cc = _sp.run([sys.executable, str(ROOT / "scripts" / "check_consistency.py"),
                   "--quiet"], cwd=str(ROOT), capture_output=True, text=True)
    _tail = [l for l in _cc.stdout.strip().splitlines() if "consistency checks" in l]
    check(_cc.returncode == 0, "documentation and metadata are self-consistent",
          _tail[-1].strip() if _tail else _cc.stdout.strip()[-70:])

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
