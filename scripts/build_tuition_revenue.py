#!/usr/bin/env python3
"""What the master's expansion is worth in tuition, and how that grew.

THE PROBLEM THIS SOLVES. IPEDS finance files give total tuition revenue with no
breakdown by degree level or residency (F1B01 for public/GASB, F2D01 for
private/FASB). So the finance files alone cannot say what non-resident master's
students are worth. IPEDS IC*_AY gives the published RATE by level and
residency (TUITION7 + FEE7 = out-of-state graduate), and Completions gives
non-resident master's degrees by institution and year. Multiplying those two
gives a defined, checkable quantity.

WHAT IS COMPUTED, stated exactly, because the wording is the honesty:

    "One year of published out-of-state graduate tuition and required fees,
     multiplied by the number of non-resident master's degrees that
     institution conferred that year."

That is billings for ONE academic year per degree conferred. A master's
normally runs 1.5-2 years, so the whole-programme figure is roughly 1.5-2x;
the output carries that range rather than picking a point inside it.

WHAT IT IS NOT, and must never be called:
  * Not revenue received. It is sticker price. Assistantship holders get
    waivers -- though NSF GSS 2024 puts master's assistantship rates at 7.0%
    (RA) and 6.9% (TA), so ~86% of master's students hold neither, which is
    why sticker is a defensible base here and would NOT be for undergraduates.
  * Not net of discounts and allowances. The finance-file series below IS net,
    and the two must not be added together or compared like for like.
  * Not attributable to any one student. Rates are institution-level.

The measured finance series is reported alongside it, unmodelled, so a reader
can see the estimate against an actual audited total.

Inflation: CPI-U annual averages, US city average, BLS series CUUR0000SA0.
Constant 2024 dollars.

Usage:
    python3 scripts/build_tuition_revenue.py            # writes site/data/tuition.json
    python3 scripts/build_tuition_revenue.py --report   # print, write nothing
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from atomic_write import write_json

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW   # noqa: E402
TUITION_DIR = ROOT / "data" / "ipeds_tuition"
FINANCE_DIR = ROOT / "data" / "ipeds_finance"
COMPLETIONS = ROOT / "data" / "ipeds"
OUT = ROOT / "site" / "data" / "tuition.json"

# Core-STEM, the same eight families the rest of the site uses.
STEM_CIP2 = STEM_NARROW   # single source: pipeline/models.py.
# Seven scripts each carried their own copy of this set. They all happened
# to agree, which is exactly why the drift would have been silent: change
# models.py and the copies keep the old definition without a word.
MASTERS_AWLEVEL = "7"

# CPI-U annual average, US city average (BLS CUUR0000SA0). 2024 = base.
CPI = {2000: 172.200, 2001: 177.100, 2002: 179.900, 2003: 184.000,
       2004: 188.900, 2005: 195.300, 2006: 201.600, 2007: 207.342,
       2008: 215.303, 2009: 214.537, 2010: 218.056, 2011: 224.939,
       2012: 229.594, 2013: 232.957, 2014: 236.736, 2015: 237.017,
       2016: 240.007, 2017: 245.120, 2018: 251.107, 2019: 255.657,
       2020: 258.811, 2021: 270.970, 2022: 292.655, 2023: 304.702,
       2024: 313.689}
BASE_YEAR = 2024


def real(dollars: float, year: int) -> float:
    """Nominal -> constant BASE_YEAR dollars."""
    if year not in CPI:
        return dollars
    return dollars * CPI[BASE_YEAR] / CPI[year]


# Published rate columns, all with their matching required-fee column.
# The undergraduate pair is carried because the graduate trend is meaningless
# without it: reading 2014-2023 alone suggests tuition simply fell, when the
# real shape is a steep rise to about 2012 and a real-terms decline after.
RATE_COLS = {
    "grad_oos": ("TUITION7", "FEE7"),   # out-of-state graduate
    "grad_ins": ("TUITION6", "FEE6"),   # in-state graduate
    "ug_oos": ("TUITION3", "FEE3"),     # out-of-state undergraduate
    "ug_ins": ("TUITION2", "FEE2"),     # in-state undergraduate
}


def load_rates() -> dict[int, dict[str, dict[str, float]]]:
    """{year: {unitid: {slot: rate}}} -- published tuition plus required fees."""
    out: dict[int, dict[str, dict[str, float]]] = {}
    for path in sorted(glob.glob(str(TUITION_DIR / "ic*_ay.csv"))):
        m = re.search(r"ic(\d{4})_ay", os.path.basename(path).lower())
        if not m:
            continue
        year = int(m.group(1))
        per: dict[str, dict[str, float]] = {}
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            for row in csv.DictReader(fh):
                def g(k):
                    try:
                        return float(row.get(k) or 0)
                    except (ValueError, TypeError):
                        return 0.0
                slots = {}
                for slot, (t, f) in RATE_COLS.items():
                    v = g(t) + g(f)
                    if v > 0:
                        slots[slot] = v
                # Keep every institution reporting ANY rate. Gating the whole
                # row on grad_oos would silently drop undergraduate-only
                # institutions from the undergraduate median, which shifts it
                # by thousands of dollars and answers a different question
                # from the one an undergraduate is asking.
                if slots:
                    per[row["UNITID"]] = slots
        if per:
            out[year] = per
    return out


def median(vals):
    vals = sorted(vals)
    return vals[len(vals) // 2] if vals else None


def load_masters() -> dict[int, dict[str, tuple[int, int]]]:
    """{year: {unitid: (nra_masters, total_masters)}} for core STEM."""
    files: dict[int, str] = {}
    for path in glob.glob(str(COMPLETIONS / "*_a*.csv")):
        m = re.search(r"c(\d{4})_a", os.path.basename(path).lower())
        if not m:
            continue
        y = int(m.group(1))
        if y not in files or "_rv" in path.lower():
            files[y] = path
    out: dict[int, dict[str, tuple[int, int]]] = {}
    for year, path in sorted(files.items()):
        per: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        try:
            with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
                for row in csv.DictReader(fh):
                    if (row.get("AWLEVEL") or "").lstrip("0") != MASTERS_AWLEVEL:
                        continue
                    if (row.get("CIPCODE") or "").split(".")[0].zfill(2) not in STEM_CIP2:
                        continue
                    try:
                        tot = int(row.get("CTOTALT") or 0)
                        nra = int(row.get("CNRALT") or 0)
                    except ValueError:
                        continue
                    if tot <= 0:
                        # Pre-2008 files have no CTOTALT/CNRALT, so every row
                        # parses to zero. Without this guard those years enter
                        # the series as real zeros and the billings window
                        # starts four years before any billings exist.
                        continue
                    slot = per[row["UNITID"]]
                    slot[0] += nra
                    slot[1] += tot
        except OSError:
            continue
        if per and any(v[1] > 0 for v in per.values()):
            out[year] = {u: (v[0], v[1]) for u, v in per.items() if v[1] > 0}
    return out


def load_finance() -> dict[int, tuple[float, int]]:
    """{year: (net_tuition_and_fees, institutions)} -- public + private.

    F1B01 (GASB/public) and F2D01 (FASB/private non-profit) are both 'tuition
    and fees, after deducting discounts and allowances'. Summing them gives a
    national net figure; for-profit (F3) is excluded, which is stated in the
    output so nobody assumes the total is every institution.
    """
    out: dict[int, list] = defaultdict(lambda: [0.0, 0])
    for path in glob.glob(str(FINANCE_DIR / "f*_f*.csv")):
        base = os.path.basename(path).lower()
        m = re.match(r"f(\d{2})(\d{2})_f(1a|2)\.csv", base)
        if not m:
            continue
        # f1415 -> academic year ending 2015; report on the ending year.
        year = 2000 + int(m.group(2))
        col = "F1B01" if m.group(3) == "1a" else "F2D01"
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            for row in csv.DictReader(fh):
                v = row.get(col)
                try:
                    val = float(v)
                except (TypeError, ValueError):
                    continue
                if val > 0:
                    out[year][0] += val
                    out[year][1] += 1
    return {y: (v[0], v[1]) for y, v in sorted(out.items())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    rates = load_rates()
    masters = load_masters()
    finance = load_finance()
    if not rates or not masters:
        sys.exit("missing inputs -- run scripts/download_ipeds_finance.py first")

    years = sorted(set(rates) & set(masters))
    series = {}
    for y in years:
        r, m = rates[y], masters[y]
        # Not every institution in the rate panel offers graduate study.
        _grad_med = median([v["grad_oos"] for v in r.values() if v.get("grad_oos")])
        billed_nra = billed_dom = 0.0
        nra_n = dom_n = 0
        matched = 0
        for uid, (nra, tot) in m.items():
            if uid not in r:
                continue
            oos = r[uid].get("grad_oos", 0)
            ins = r[uid].get("grad_ins", 0)
            if not oos:
                continue
            matched += 1
            billed_nra += nra * oos
            billed_dom += (tot - nra) * (ins or oos)
            nra_n += nra
            dom_n += tot - nra
        series[y] = {
            "nra_degrees": nra_n,
            "domestic_degrees": dom_n,
            "billed_nra_nominal": round(billed_nra),
            "billed_nra_real": round(real(billed_nra, y)),
            "billed_domestic_real": round(real(billed_dom, y)),
            "median_oos_rate": round(_grad_med),
            "median_oos_rate_real": round(real(_grad_med, y)),
            "institutions_matched": matched,
            "net_tuition_all_levels": round(finance[y][0]) if y in finance else None,
            "net_tuition_all_levels_real": round(real(finance[y][0], y)) if y in finance else None,
            "finance_institutions": finance[y][1] if y in finance else None,
        }

    # The rate series runs over EVERY year with an IC file, not just the years
    # where billings can be computed. Billings need the residency columns in
    # Completions (2008 onward); rates go back further, and the earlier years
    # are what show the rise that the recent decline sits on top of.
    rate_series = {}
    for y in sorted(rates):
        r = rates[y]
        row = {}
        for slot in RATE_COLS:
            vals = [v[slot] for v in r.values() if v.get(slot)]
            if len(vals) < 200:          # too thin a panel to take a median from
                continue
            med = median(vals)
            row[slot] = round(med)
            row[slot + "_real"] = round(real(med, y))
        if len(row) == 2 * len(RATE_COLS):
            row["institutions"] = len(r)
            rate_series[y] = row

    lo, hi = years[0], years[-1]
    a, b = series[lo], series[hi]
    payload = {
        "basis": {
            "quantity": ("one year of published out-of-state graduate tuition and "
                         "required fees (IPEDS IC*_AY TUITION7 + FEE7), multiplied by "
                         "non-resident core-STEM master's degrees conferred (IPEDS "
                         "Completions, award level 7)"),
            "programme_length_note": ("a master's normally runs 1.5-2 years, so the "
                                      "whole-programme figure is roughly 1.5-2x the "
                                      "annual figure shown"),
            "not_revenue": ("sticker price, not receipts, and not net of discounts. "
                            "NSF GSS 2024 puts master's assistantship rates at 7.0% RA "
                            "and 6.9% TA, so ~86% hold neither"),
            "cip_families": sorted(STEM_CIP2),
            "dollars": f"constant {BASE_YEAR} dollars, CPI-U (BLS CUUR0000SA0)",
            "finance_series": ("F1B01 public/GASB + F2D01 private non-profit/FASB, net "
                               "of discounts and allowances; for-profit institutions "
                               "excluded"),
        },
        "window": [lo, hi],
        "headline": {
            "billed_nra_real_first": a["billed_nra_real"],
            "billed_nra_real_last": b["billed_nra_real"],
            "growth_pct_real": round(100 * (b["billed_nra_real"] - a["billed_nra_real"])
                                     / a["billed_nra_real"], 1),
            "nra_degrees_first": a["nra_degrees"],
            "nra_degrees_last": b["nra_degrees"],
            "degree_growth_pct": round(100 * (b["nra_degrees"] - a["nra_degrees"])
                                       / a["nra_degrees"], 1),
        },
        "series": series,
        "rates": rate_series,
        "rates_note": ("median published tuition plus required fees across all "
                       "reporting institutions, by level and residency. Each "
                       "series is a median over the institutions reporting THAT "
                       "rate, so the undergraduate panel includes institutions "
                       "with no graduate programme. A median across "
                       "institutions, NOT weighted by enrolment: it describes "
                       "the typical sticker price at a typical institution, not "
                       "what the typical student pays."),
    }

    print(f"IPEDS tuition, core-STEM master's, {lo}-{hi}  (constant {BASE_YEAR} dollars)\n")
    print(f"  {'year':<6}{'NRA degrees':>13}{'billed (real)':>18}{'median OOS rate':>18}"
          f"{'net tuition, all levels':>26}")
    for y in years:
        s = series[y]
        nt = (f"${s['net_tuition_all_levels_real']/1e9:,.1f}B"
              if s["net_tuition_all_levels_real"] else "-")
        print(f"  {y:<6}{s['nra_degrees']:>13,}${s['billed_nra_real']/1e9:>16,.2f}B"
              f"${s['median_oos_rate_real']:>17,}{nt:>26}")
    h = payload["headline"]
    print(f"\n  non-resident core-STEM master's degrees: {h['nra_degrees_first']:,} -> "
          f"{h['nra_degrees_last']:,}  ({h['degree_growth_pct']:+.1f}%)")
    print(f"  annual tuition billed (real):  ${h['billed_nra_real_first']/1e9:,.2f}B -> "
          f"${h['billed_nra_real_last']/1e9:,.2f}B  ({h['growth_pct_real']:+.1f}%)")
    print(f"  whole-programme, at 1.5-2x:    "
          f"${h['billed_nra_real_last']*1.5/1e9:,.1f}B - "
          f"${h['billed_nra_real_last']*2/1e9:,.1f}B per graduating cohort")

    if not args.report:
        # Atomic: a crash midway through this script previously left the
        # PREVIOUS run's file in place while reporting nothing, so the site
        # served figures nobody had computed.
        write_json(OUT, payload, indent=1)
        print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())