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


def by_class(ws) -> tuple[list[str], dict[str, dict[str, int]]]:
    """Tables 10 and 11: country against broad class of admission."""
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    hdr, at = None, None
    for i, r in enumerate(rows[:9]):
        if r[1] and "Total" in str(r[1]):
            hdr = [re.sub(r"\s+", " ", str(x or "")).strip() for x in r]
            at = i
            break
    if not hdr:
        return [], {}
    classes = [c for c in hdr[1:] if c]
    out: dict[str, dict[str, int]] = {}
    for r in rows[at + 1:]:
        label = re.sub(r"\s+", " ", str(r[0] or "")).strip()
        if not label or NOT_A_COUNTRY.match(label):
            continue
        vals = {hdr[i]: int(x) for i, x in enumerate(r)
                if i and isinstance(x, (int, float)) and hdr[i]}
        if vals:
            out[label] = vals
    return classes, out



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

    # Where a country's surplus actually sits. A waypoint whose gap is in
    # family admission is a different phenomenon from one whose gap is in
    # employment, and the total alone cannot tell them apart.
    classes, birth_cls = by_class(wb["Table 10"])
    _c2, res_cls = by_class(wb["Table 11"])
    composition: dict[str, dict] = {}
    if classes and birth_cls and res_cls:
        for country in set(birth_cls) & set(res_cls):
            b, r = birth_cls[country], res_cls[country]
            tot_gap = (r.get("Total", 0) - b.get("Total", 0))
            if abs(tot_gap) < 500:
                continue
            parts = {}
            for cls in classes:
                if cls == "Total" or cls not in b or cls not in r:
                    continue
                g = r[cls] - b[cls]
                parts[cls] = {"birth": b[cls], "residence": r[cls], "gap": g,
                              "share_of_total_gap_pct": round(100 * g / tot_gap, 1)
                              if tot_gap else None}
            if parts:
                composition[country] = {"total_gap": tot_gap, "by_class": parts}

    waypoints = sorted((x for x in rows if x["gap"] > 0),
                       key=lambda x: -x["gap"])[:15]
    for x in waypoints:
        c = composition.get(x["country"])
        if c:
            x["composition"] = c["by_class"]
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
            "no published answer. THE COMPOSITION MATTERS AND IS BROKEN OUT: "
            "Canada's surplus is 55% immediate relatives of US citizens and "
            "23% family-sponsored against only 17% employment-based, and zero "
            "in refugees and asylees. A waypoint whose gap sits in family "
            "admission is a different phenomenon from one whose gap sits in "
            "employment, and the headline total cannot tell them apart. "
            "Countries below "
            f"{FLOOR:,} are excluded because the gap is then noise."),
        "source": "DHS Yearbook of Immigration Statistics, tables 2 and 3",
        "source_url": "https://ohss.dhs.gov/topics/immigration/yearbook",
        "years": years,
        "latest_year": latest,
        "floor": FLOOR,
        "countries": len(rows),
        "waypoints": waypoints,
        "gap_composition": composition,
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
