#!/usr/bin/env python3
"""Real figures for the OG cards, derived from the project's own data.

Everything a card prints comes from here. Two rules held throughout:

  * Nothing is invented or rounded into a nicer story.
  * A card never shows two numbers that disagree. In particular the per-
    university cards do NOT use the `nra` field in site/data/{stem,nonstem}/
    <key>.json — for Caltech that field says 64.9% while the IPEDS completions
    series in the same file says 40.1% pooled / 42.5% latest. The IPEDS series
    is the one that reconciles exactly with data/ipeds/nra_index.csv.gz
    (national all-fields 27.2% in 2010 and 25.5% in 2025, reproduced below),
    so the cards are built on the IPEDS series alone.
"""
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
INDEX = ROOT / "data" / "ipeds" / "nra_index.csv.gz"

# The project's own STEM definition, copied from scripts/enrich_university_json.py
# so the national baseline on a university card uses the same rule as that
# university's phd_stem_* series.
# Two STEM definitions exist in this codebase and they disagree. The broad
# 16-family set below drives the per-university completions chart via
# enrich_university_json.py. The headline NRA share on every page uses the
# narrow 8-family set pinned in scripts/compute_nra_shares.py, which is what
# ipeds_nra_asian_ranking.py has always used.
#
# Cards must match the page they represent, so the narrow set wins here. The
# two differ by up to about 3 points (Michigan State 49.0 vs 46.1), which is
# small but is exactly the sort of unexplained gap this project cannot afford.
STEM_CIPS = {"11", "14", "15", "26", "27", "30", "40", "42"}

# The pinned window and award-level rule from scripts/compute_nra_shares.py.
# A STEM card's hero figure is the university's published headline share, so it
# has to be computed on exactly the same basis or the card contradicts its page.
PINNED_YEARS = (2015, 2022)


def basis_for(year):
    """One award-level basis per year; never both. 2008 and 2009 carry both
    codings across different institutions, so summing them double-counts."""
    return "aw17" if year >= 2010 else "aw09"

# Kept for reference: the broader set used by the completions chart.
STEM_CIPS_BROAD = {"01", "03", "04", "10", "11", "14", "15", "26", "27", "29",
                   "30", "40", "41", "42", "45", "51"}


def national_series():
    """National NRA share of research doctorates by year.

      all      every field
      stem     the narrow 8-family set — the basis the headline figures use,
               so the national line on a STEM card is comparable with both the
               school line and the page's own number
      nonstem  the complement of the BROAD 16-family set, not of the narrow
               one. "Non-STEM" on this site means education, humanities and the
               social sciences; the narrow complement would sweep health,
               agriculture and psychology in with them and misdescribe the page.
    """
    tot, nra = Counter(), Counter()
    stot, snra = Counter(), Counter()     # narrow STEM
    btot, bnra = Counter(), Counter()     # broad STEM, only to take a complement
    with gzip.open(INDEX, "rt") as f:
        for r in csv.DictReader(f):
            y = int(r["year"])
            if r["basis"] != basis_for(y):
                continue
            t, n = int(r["total"]), int(r["nra"])
            cip2 = r["cipcode"].split(".")[0].zfill(2)
            tot[y] += t
            nra[y] += n
            if cip2 in STEM_CIPS:
                stot[y] += t
                snra[y] += n
            if cip2 in STEM_CIPS_BROAD:
                btot[y] += t
                bnra[y] += n

    def pct(a, b):
        return {y: round(100 * a[y] / b[y], 1) for y in sorted(b) if b[y]}

    return {
        "all": pct(nra, tot),
        "stem": pct(snra, stot),
        "nonstem": pct(Counter({y: nra[y] - bnra[y] for y in tot}),
                       Counter({y: tot[y] - btot[y] for y in tot})),
        "totals": dict(tot),
    }


def registry():
    with open(ROOT / "pipeline" / "universities.json") as f:
        return json.load(f)


def uni_stem_index():
    """Per-university STEM series on the pinned basis, straight from the IPEDS
    index rather than from the pre-computed phd_stem_* arrays (which use the
    broad set and so disagree with the published headline by a median of 3.2
    points, up to 17.6).

    Returns {key: {"share": {year: pct}, "pooled": pct, "cohort": n}} where
    `pooled` is the pinned 2015-2022 figure — identical to the university's
    published NRA share for 103 of the 105 registered institutions.
    """
    reg = registry()
    u2k = {str(v["unitid"]): k for k, v in reg.items() if v.get("unitid")}
    tot = defaultdict(Counter)
    nra = defaultdict(Counter)
    with gzip.open(INDEX, "rt") as f:
        for r in csv.DictReader(f):
            k = u2k.get(r["unitid"])
            if k is None:
                continue
            y = int(r["year"])
            if r["basis"] != basis_for(y):
                continue
            if r["cipcode"].split(".")[0].zfill(2) not in STEM_CIPS:
                continue
            tot[k][y] += int(r["total"])
            nra[k][y] += int(r["nra"])

    lo, hi = PINNED_YEARS
    out = {}
    for k in tot:
        share = {y: round(100 * nra[k][y] / tot[k][y], 1)
                 for y in sorted(tot[k]) if tot[k][y]}
        T = sum(t for y, t in tot[k].items() if lo <= y <= hi)
        N = sum(n for y, n in nra[k].items() if lo <= y <= hi)
        out[k] = {"share": share,
                  "pooled": round(100 * N / T, 1) if T else None,
                  "cohort": T}
    return out


def uni_series(uni, mode):
    """(share_by_year, pooled_pct, total_doctorates) for one university.

    Used for the non-STEM cards only: the arithmetic complement of the broad
    STEM set, which is what the non-STEM pages cover. STEM cards go through
    uni_stem_index() instead, so that they sit on the same pinned basis as the
    headline share printed on the page.
    """
    ct = uni.get("completions_trend") or {}
    years = ct.get("years") or []
    if not years:
        return {}, None, 0
    if mode == "stem":
        tot = ct["phd_stem_total"]
        nra = ct["phd_stem_nra"]
    else:
        tot = [a - b for a, b in zip(ct["phd_total"], ct["phd_stem_total"])]
        nra = [a - b for a, b in zip(ct["phd_nra"], ct["phd_stem_nra"])]
    share = {y: round(100 * n / t, 1) for y, t, n in zip(years, tot, nra) if t > 0}
    T, N = sum(tot), sum(nra)
    pooled = round(100 * N / T, 1) if T else None
    return share, pooled, T


def load_uni(key, mode):
    p = SITE / "data" / ("stem" if mode == "stem" else "nonstem") / f"{key}.json"
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def uni_keys(mode):
    """Keys that actually have a published page, in the project's canonical
    spelling (the underscore form used by pipeline/universities.json, the
    sidebar links and the /data/<mode>/<key>.json filenames)."""
    d = SITE / "universities" if mode == "stem" else SITE / "universities" / "nonstem"
    return sorted(p.stem for p in d.glob("*.html"))
