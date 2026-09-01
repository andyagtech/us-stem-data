#!/usr/bin/env python3
"""Who arrives from a country, against who was born there.

DHS publishes permanent residents twice over: once by country of birth and
once by country of last residence. Where the two disagree, people spent time
somewhere that was not their birthplace before entering the United States,
and the size of the disagreement measures how much a country functions as a
waypoint rather than a source.

WHAT THIS CANNOT DO. The two tables are separate totals, not a
cross-tabulation, so no individual is traced from a birthplace to a
residence. A surplus for one country cannot be attributed to any particular
origin, however suggestive the matching deficit elsewhere looks. Saying
"X of Canada's surplus were born in India" is not supported and is not said.

IT ALSO DOES NOT REACH TEMPORARY VISAS. Every nonimmigrant series -- TN,
H-1B, F-1 -- is published by CITIZENSHIP only. Country of birth is not
published for any of them, so a naturalised citizen is indistinguishable from
a native one in every visa table this project holds. The question of who
holds a given nonimmigrant status by origin has no published answer at all.

Usage:
  python3 scripts/build_origin_vs_residence.py
"""
from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "dhs_yearbook" / "lpr_fy2023.xlsx"
OUT = ROOT / "site" / "data" / "origin_vs_residence.json"
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

NOT_A_COUNTRY = re.compile(
    r"^(africa|asia|europe|north america|south america|oceania|"
    r"grand totals?|totals?\b.*|unknown|.*not (specified|reported).*|"
    r".*note.*)$", re.I)
FLOOR = 3000          # below this the gap is noise, not a pattern


def table(ws) -> tuple[list[str], dict[str, dict[str, int]]]:
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    years, at = [], None
    for i, r in enumerate(rows[:12]):
        cand = [str(x).strip() for x in r[1:] if x is not None]
        if len(cand) >= 5 and all(re.fullmatch(r"(19|20)\d\d", c) for c in cand):
            years, at = cand, i
            break
    if not years:
        return [], {}
    out: dict[str, dict[str, int]] = {}
    for r in rows[at + 1:]:
        label = re.sub(r"\s+", " ", str(r[0] or "")).strip()
        if not label or NOT_A_COUNTRY.match(label):
            continue
        vals = {y: int(v) for y, v in zip(years, r[1:])
                if isinstance(v, (int, float))}
        if vals:
            out[label] = vals
    return years, out


def main() -> int:
    if not SRC.exists():
        print(f"  missing {SRC.relative_to(ROOT)}")
        return 1
    import openpyxl
    wb = openpyxl.load_workbook(SRC, read_only=True)
    yr, residence = table(wb["Table 2"])
    yb, birth = table(wb["Table 3"])
    if not residence or not birth:
        print("  could not read both tables")
        return 1

    years = [y for y in yr if y in yb]
    latest = years[-1]
    warns = []

    rows = []
    for country in sorted(set(residence) & set(birth)):
        r, b = residence[country], birth[country]
        if r.get(latest) is None or b.get(latest) is None:
            continue
        if max(r[latest], b[latest]) < FLOOR:
            continue
        series = {y: {"residence": r[y], "birth": b[y],
                      "gap": r[y] - b[y],
                      "gap_pct_of_residence": round(100 * (r[y] - b[y]) / r[y], 1)
                      if r[y] else None}
                  for y in years if y in r and y in b}
        rows.append({"country": country,
                     "residence": r[latest], "birth": b[latest],
                     "gap": r[latest] - b[latest],
                     "gap_pct_of_residence": round(
                         100 * (r[latest] - b[latest]) / r[latest], 1)
                     if r[latest] else None,
                     "series": series})

    waypoints = sorted((x for x in rows if x["gap"] > 0),
                       key=lambda x: -x["gap"])[:15]
    sources = sorted((x for x in rows if x["gap"] < 0),
                     key=lambda x: x["gap"])[:15]

    doc = {
        "_comment": (
            "Persons obtaining lawful permanent residence counted by COUNTRY "
            "OF LAST RESIDENCE against the same people counted by COUNTRY OF "
            "BIRTH. A positive gap means more people arrived FROM a country "
            "than were BORN in it -- the country served as a waypoint. THE "
            "TWO TABLES ARE SEPARATE TOTALS, NOT A CROSS-TABULATION: no "
            "individual is traced from a birthplace to a residence, so a "
            "surplus in one country CANNOT BE ATTRIBUTED to any particular "
            "origin however well the deficits elsewhere seem to match. THIS "
            "DOES NOT REACH TEMPORARY VISAS. Every nonimmigrant series -- TN, "
            "H-1B, F-1, L-1 -- is published by CITIZENSHIP ONLY; country of "
            "birth is not published for any of them, so a naturalised citizen "
            "cannot be distinguished from a native-born one anywhere in the "
            "visa data. Who holds a given nonimmigrant status by origin has "
            "no published answer. Countries below "
            f"{FLOOR:,} are excluded because the gap is then noise."),
        "source": "DHS Yearbook of Immigration Statistics, tables 2 and 3",
        "source_url": "https://ohss.dhs.gov/topics/immigration/yearbook",
        "years": years,
        "latest_year": latest,
        "floor": FLOOR,
        "countries": len(rows),
        "waypoints": waypoints,
        "origin_countries": sources,
        "birth_not_published_for": ["TN", "H-1B", "F-1", "L-1", "O-1",
                                    "every nonimmigrant classification"],
        "warnings": warns,
    }
    write_json(OUT, doc)

    print(f"  {len(rows)} countries above the {FLOOR:,} floor, {years[0]}-{latest}")
    print(f"\n  arrived FROM more than were BORN there ({latest}):")
    print(f"  {'country':30}{'residence':>11}{'birth':>10}{'gap':>10}{'of arrivals':>13}")
    for x in waypoints[:8]:
        print(f"  {x['country'][:28]:30}{x['residence']:>11,}{x['birth']:>10,}"
              f"{x['gap']:>+10,}{x['gap_pct_of_residence']:>12.1f}%")
    print(f"\n  born there but last lived elsewhere ({latest}):")
    for x in sources[:6]:
        print(f"  {x['country'][:28]:30}{x['residence']:>11,}{x['birth']:>10,}"
              f"{x['gap']:>+10,}")
    ca = next((x for x in rows if x["country"] == "Canada"), None)
    if ca:
        print(f"\n  Canada over time:")
        for y in years:
            s = ca["series"].get(y)
            if s:
                print(f"   {y}  from {s['residence']:>7,}  born {s['birth']:>7,}"
                      f"  gap {s['gap']:>+7,} ({s['gap_pct_of_residence']:.0f}%)")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
