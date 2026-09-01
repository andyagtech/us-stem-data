#!/usr/bin/env python3
"""When each part of the pipeline expanded, and in what order.

The project holds the degree series, the visa series and the work-visa
series separately, each measured on its own basis. This puts them on one
axis and asks the question they were built to answer: what were the windows,
and did they move together or in sequence?

PHASE BOUNDARIES ARE A JUDGMENT, NOT A RESULT. They are set here from the
turning points visible in the series and from known external events -- the
post-9/11 visa contraction, the 2020 consular closure -- and are stated
explicitly so a reader can move them. Growth inside each window is computed,
not asserted.

THE LAG IS TESTED, NOT ASSUMED. Correlating two rising series proves
nothing, so the correlation is computed on YEAR-OVER-YEAR CHANGES, which
removes the shared trend, and 2020-21 are excluded as an exogenous shock. It
peaks at three years and is near zero at lag zero -- the shape a mechanical
lag produces, and not the shape a common trend produces.

Usage:
  python3 scripts/build_expansion_phases.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

SITE = ROOT / "site" / "data"
OUT = SITE / "expansion_phases.json"

# Each window is named for what happened in it, with the reason it starts
# and ends. Open-ended windows use the last year in the data.
PHASES = [
    (1998, 2003, "Post-9/11 contraction",
     "Student visa issuance falls after the 2001 attacks and the "
     "consular tightening that followed."),
    (2003, 2015, "The long student expansion",
     "F-1 issuance rises without interruption from its post-9/11 trough to "
     "an all-time peak."),
    (2007, 2017, "The master's expansion",
     "Non-resident master's degrees rise steeply, beginning about three "
     "years after the student expansion and ending about two after it."),
    (2015, 2019, "Student visas fall, degrees hold",
     "F-1 issuance drops sharply while conferrals stay near their peak -- "
     "the pipeline emptying from the front."),
    (2019, 2021, "Consular closure",
     "Posts close and an entry proclamation suspends H-1B admission. Anchored "
     "on 2019 so the window shows the collapse rather than growth off its own "
     "trough; an exogenous break, excluded from every trend computed here."),
    (2022, 2025, "The second surge",
     "Non-resident master's degrees and H-1B issuance both reach records, "
     "faster than the first expansion."),
]

SERIES = {
    "masters_nonresident_degrees": ("graduate_balance", "masters_nra"),
    "masters_nonresident_share": ("graduate_balance", "masters_share"),
    "doctorate_nonresident_degrees": ("graduate_balance", "doctorate_nra"),
    "f1_issuances": ("visa_issuances", "F1"),
    "h1b_issuances": ("visa_issuances", "H1B"),
    "o1_issuances": ("visa_issuances", "O1"),
    "j1_issuances": ("visa_issuances", "J1"),
}
SHOCK_YEARS = (2020, 2021)


def load() -> dict[str, dict[int, float]]:
    gb = json.loads((SITE / "graduate_balance.json").read_text())["series"]
    vi = json.loads((SITE / "visa_issuances.json").read_text())["totals"]
    out: dict[str, dict[int, float]] = {k: {} for k in SERIES}
    for y, s in gb.items():
        y = int(y)
        out["masters_nonresident_degrees"][y] = s["masters"]["nra"]
        out["masters_nonresident_share"][y] = s["masters"]["share"]
        out["doctorate_nonresident_degrees"][y] = s["doctorate"]["nra"]
    for y, t in vi.items():
        y = int(y)
        for key, (src, col) in SERIES.items():
            if src == "visa_issuances" and t.get(col):
                out[key][y] = t[col]
    return out


def growth(d: dict[int, float], a: int, b: int) -> dict | None:
    ks = sorted(k for k in d if a <= k <= b)
    if len(ks) < 2:
        return None
    f, l = ks[0], ks[-1]
    if not d[f]:
        return None
    yrs = l - f
    total = 100 * (d[l] / d[f] - 1)
    # A window that ends below its own peak understates what happened in it:
    # H-1B issuance peaked in 2023 and fell after, so first-to-last reads
    # +7% for a window containing a record.
    peak_y = max(ks, key=lambda k: d[k])
    return {"first_year": f, "last_year": l,
            "first": round(d[f], 1), "last": round(d[l], 1),
            "change_pct": round(total, 1),
            "peak_year": peak_y, "peak": round(d[peak_y], 1),
            "peak_change_pct": round(100 * (d[peak_y] / d[f] - 1), 1),
            "annualised_pct": round(100 * ((d[l] / d[f]) ** (1 / yrs) - 1), 1)
            if yrs else None}


def pct_changes(d: dict[int, float]) -> dict[int, float]:
    ks = sorted(d)
    return {ks[i]: d[ks[i]] / d[ks[i - 1]] - 1
            for i in range(1, len(ks))
            if ks[i] - ks[i - 1] == 1 and d[ks[i - 1]]
            and ks[i] not in SHOCK_YEARS and ks[i - 1] not in SHOCK_YEARS}


def pearson(a: dict[int, float], b: dict[int, float]) -> tuple[float | None, int]:
    ks = sorted(set(a) & set(b))
    if len(ks) < 8:
        return None, len(ks)
    x = [a[k] for k in ks]
    y = [b[k] for k in ks]
    mx, my = statistics.mean(x), statistics.mean(y)
    num = sum((i - mx) * (j - my) for i, j in zip(x, y))
    den = (sum((i - mx) ** 2 for i in x) * sum((j - my) ** 2 for j in y)) ** 0.5
    return (round(num / den, 2) if den else None), len(ks)


def main() -> int:
    data = load()
    if not data["f1_issuances"]:
        print("  no visa series; build visa_issuances first")
        return 1

    phases = []
    for a, b, name, why in PHASES:
        rec = {"start": a, "end": b, "name": name, "why": why, "series": {}}
        for key, d in data.items():
            g = growth(d, a, b)
            if g:
                rec["series"][key] = g
        phases.append(rec)

    # Does the student visa lead the degree, and by how long?
    dm = pct_changes(data["masters_nonresident_degrees"])
    df = pct_changes(data["f1_issuances"])
    lags = []
    for lag in range(0, 6):
        r, n = pearson(dm, {y + lag: v for y, v in df.items()})
        lags.append({"lag_years": lag, "r": r, "n": n})
    best = max((l for l in lags if l["r"] is not None),
               key=lambda l: l["r"], default=None)

    doc = {
        "_comment": (
            "Non-resident graduate degrees and nonimmigrant visa issuances on "
            "one time axis, divided into named windows. PHASE BOUNDARIES ARE "
            "A JUDGMENT, not a result: they are set from turning points in "
            "the series and from known external events, and are listed with "
            "the reason for each so a reader can move them. Growth inside "
            "each window is computed. THE LAG IS TESTED ON DIFFERENCED "
            "SERIES -- year-over-year changes, which removes the shared trend "
            "that would make any two rising series correlate -- with 2020-21 "
            "excluded as an exogenous consular shock. It peaks at three years "
            "and sits near zero at lag zero, which is the shape a mechanical "
            "lag produces and not the shape a common trend produces. IT IS "
            "STILL A CORRELATION on 16 observations and is consistent with "
            "the mechanics of a two-year degree rather than proof of them. "
            "DEGREES AND ISSUANCES ARE DIFFERENT UNITS: an issuance is a "
            "document and not a person, a degree is a conferral and not a "
            "person, and neither is a headcount of anyone."),
        "sources": {
            "degrees": "NCES IPEDS Completions, eight core-STEM CIP families",
            "visas": "US Department of State, nonimmigrant visa detail tables",
        },
        "shock_years_excluded_from_trends": list(SHOCK_YEARS),
        "phases": phases,
        "lag_test": {
            "description": "Correlation of year-over-year changes: F-1 "
                           "issuances leading non-resident master's degrees",
            "by_lag": lags,
            "best_lag_years": best["lag_years"] if best else None,
            "best_r": best["r"] if best else None,
        },
    }
    write_json(OUT, doc)

    print(f"  {len(phases)} phases\n")
    for p in phases:
        s = p["series"]
        print(f"  {p['start']}-{p['end']}  {p['name']}")
        for key in ("f1_issuances", "masters_nonresident_degrees",
                    "h1b_issuances", "o1_issuances"):
            g = s.get(key)
            if g:
                mark = (f"   peak {g['peak']:,.0f} in {g['peak_year']}"
                        if g["peak_year"] != g["last_year"] else "")
                print(f"     {key:32}{g['first']:>10,.0f} -> {g['last']:>10,.0f}"
                      f"{g['change_pct']:>9.0f}%{mark}")
        print()
    print("  lag test (F-1 leading master's degrees, differenced):")
    for l in lags:
        print(f"   {l['lag_years']} yr: r={l['r']}  n={l['n']}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
