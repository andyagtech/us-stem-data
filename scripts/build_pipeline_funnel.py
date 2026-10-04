#!/usr/bin/env python3
"""The student-to-work funnel by country, for /pipeline.

WHY THIS EXISTS. /pipeline.html carried its whole funnel as hardcoded JS
arrays, and they had drifted. The OPT series, indexed to 2010, ended at 341
where the data gives 381 -- the page understated the growth it exists to show,
by a tenth, for however long the arrays had been stale. Two of its five bars,
SEVIS enrolment and employment-based green cards by country, matched no
published dataset at all.

So this builds what can be sourced and says nothing about what cannot:

  * F-1 issuances by country          visa_issuances.json (State Dept)
  * doctorate recipients by country   doctorate_origins.json (NSF SED)
  * H-1B issuances by country         visa_issuances.json (State Dept)
  * OPT, STEM OPT, CPT and issuance series, indexed   visa_substitution.json

SEVIS enrolment by country and employment-based green cards by country are NOT
included. No dataset here holds either, and inventing a bar is worse than
leaving the funnel with three stages. The absence is noted on the page.

A NOTE ON WHAT THE FUNNEL IS NOT. These are three different measures of three
different populations in one year, not a cohort followed through time. A
student who was issued an F-1 in 2016 and earned a doctorate in 2024 appears in
one column of one year and another column of another. The funnel shows relative
scale at a moment. It does not show a rate of progression, and must never be
read as one.

Usage:
    python3 scripts/build_pipeline_funnel.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_write import write_json              # noqa: E402
SITE = ROOT / "site" / "data"
OUT = ROOT / "data" / "pipeline" / "pipeline_funnel.json"

INDEX_BASE = 2010
SERIES = {
    "opt": ("student_work", "opt", "OPT"),
    "stem_opt": ("student_work", "stem_opt", "STEM OPT"),
    "cpt": ("student_work", "cpt", "CPT"),
    "f1": ("issuance", "F1", "F-1 issued"),
    "h1b": ("issuance", "H1B", "H-1B issued"),
}


#: NSF names a country one way and the State Department another. Without this
#: China and South Korea resolved to nothing and the funnel showed them with
#: zero F-1 issuances -- which would have read as a finding rather than a
#: join that silently failed.
ALIASES = {
    "China": "China - mainland",
    "South Korea": "Korea, South",
    "Taiwan": "China - Taiwan",
}


def _issued(table: dict, country: str, year: str):
    """Issuances for a country, through the name the issuance table uses."""
    key = ALIASES.get(country, country)
    if key not in table:
        raise KeyError(
            f"no issuance record for {country!r} (tried {key!r}). Add it to "
            f"ALIASES -- a missing join reads as a zero, which is a lie.")
    return (table[key] or {}).get(year)


def _load(name: str):
    return json.loads((SITE / f"{name}.json").read_text())


def main() -> int:
    origins = _load("doctorate_origins")
    issuance = _load("visa_issuances")
    subst = _load("visa_substitution")

    year = str(origins["year"])
    f1 = issuance["by_country"]["F-1 student"]
    h1b = issuance["by_country"]["H-1B specialty occupation"]

    # The ten largest doctorate origins, which is the ordering the page uses.
    rows = []
    for c in origins["countries"][:10]:
        name = c["country"]
        rows.append({
            "country": name,
            "doctorates": c["recipients"],
            "doctorate_share_of_visa_holders_pct": c["share_of_visa_holders_pct"],
            "f1_issued": _issued(f1, name, year),
            "h1b_issued": _issued(h1b, name, year),
        })

    # Indexed series, computed here rather than typed into the page.
    indexed = {"base_year": INDEX_BASE, "years": [], "series": {}}
    years = [y for y in subst["years"] if int(y) >= INDEX_BASE]
    indexed["years"] = [str(y) for y in years]
    for key, (block, field, label) in SERIES.items():
        raw = subst[block].get(field) or {}
        base = raw.get(str(INDEX_BASE))
        if not base:
            continue
        indexed["series"][key] = {
            "label": label,
            "values": [None if raw.get(str(y)) is None
                       else round(raw[str(y)] / base * 100) for y in years],
        }

    # The divergence chart needs the full F-1 series for the two largest
    # origins, which was also hardcoded in the page.
    diverge = {"years": [], "series": {}}
    dyears = [str(y) for y in range(INDEX_BASE, int(year) + 1)]
    diverge["years"] = dyears
    for country in ("China", "India"):
        diverge["series"][country] = [_issued(f1, country, y) for y in dyears]

    out = {
        "_comment": __doc__.split("Usage:")[0].strip(),
        "year": year,
        "sources": {
            "doctorates": origins["source"],
            "issuances": issuance["source"],
        },
        "not_published": [
            "SEVIS enrolment by country: no dataset here holds it.",
            "Employment-based green cards by country: no dataset here holds it.",
        ],
        "by_country": rows,
        "indexed": indexed,
        "f1_divergence": diverge,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_json(OUT, out, indent=2)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(rows)} countries for {year}")
    for r in rows[:4]:
        print(f"    {r['country']:<14}F-1 {r['f1_issued'] or 0:>7,}  "
              f"PhD {r['doctorates']:>6,}  H-1B {r['h1b_issued'] or 0:>7,}")
    for key, s in indexed["series"].items():
        print(f"  {s['label']:<12}{INDEX_BASE}=100 -> {s['values'][-1]} in {years[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
