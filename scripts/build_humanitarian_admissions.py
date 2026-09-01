#!/usr/bin/env python3
"""Refugee arrivals and asylum grants, alongside the rest of the pipeline.

This project is about the education and work routes. Humanitarian admission
is a different route with different law behind it, and it is included so the
work routes can be read against the whole rather than in isolation -- a
figure like "148,960 employment-based green cards" means something different
beside 60,000 refugees than beside 200,000.

REFUGEES AND ASYLEES ARE COUNTED AT DIFFERENT MOMENTS. A refugee is admitted
from abroad after being approved; an asylee is already in the country when
the grant is made. They are not two halves of one number and are never
summed here.

REFUGEE ADMISSION IS A POLICY CEILING, NOT A DEMAND SIGNAL. The annual number
is set by presidential determination, so the series tracks decisions in
Washington rather than anything about applicants.

Usage:
  python3 scripts/build_humanitarian_admissions.py
"""
from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
YB = ROOT / "data" / "dhs_yearbook"
OUT = ROOT / "site" / "data" / "humanitarian_admissions.json"
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

NOT_A_COUNTRY = re.compile(
    r"^(africa|asia|europe|north america|south america|oceania|"
    r"grand totals?|totals?\b.*|unknown|.*not (specified|reported).*|"
    r".*note.*)$", re.I)


def year_series(ws) -> tuple[list[str], dict[str, dict[str, int]]]:
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    years, at = [], None
    for i, r in enumerate(rows[:12]):
        cand = [str(x).strip() for x in r[1:] if x is not None]
        if len(cand) >= 4 and all(re.fullmatch(r"(19|20)\d\d", c) for c in cand):
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


def long_series(ws) -> dict[str, int]:
    """Table 13 style: one row per fiscal year."""
    out = {}
    for r in ws.iter_rows(values_only=True):
        try:
            y = int(str(r[0] or "").strip())
        except (TypeError, ValueError):
            continue
        if not 1950 <= y <= 2100:
            continue
        v = next((x for x in r[1:] if isinstance(x, (int, float))), None)
        if v is not None:
            out[str(y)] = int(v)
    return out


def main() -> int:
    import openpyxl
    ref_p, asy_p = YB / "refugees_fy2023.xlsx", YB / "asylees_fy2023.xlsx"
    for p in (ref_p, asy_p):
        if not p.exists():
            print(f"  missing {p.relative_to(ROOT)}")
            return 1

    refs = openpyxl.load_workbook(ref_p, read_only=True)
    asys = openpyxl.load_workbook(asy_p, read_only=True)

    annual = long_series(refs["Table 13"]) if "Table 13" in refs.sheetnames else {}
    _y, ref_country = (year_series(refs["Table 14"])
                       if "Table 14" in refs.sheetnames else ([], {}))
    # The asylee workbook numbers its tables differently; find the one that
    # breaks grants down by nationality rather than assuming a name.
    asy_country, asy_years = {}, []
    for name in asys.sheetnames:
        if name.upper() == "TOC":
            continue
        ys, got = year_series(asys[name])
        if got and len(got) > 20 and len(ys) >= 4:
            asy_years, asy_country = ys, got
            break

    if not annual and not ref_country:
        print("  nothing parsed from the refugee workbook")
        return 1

    warns = []
    latest = max(ref_country[k] for k in list(ref_country)[:1]) if ref_country else {}
    ref_last = max(_y) if _y else None
    asy_last = max(asy_years) if asy_years else None

    def top(d: dict, year: str, n: int = 12):
        rows = [{"country": k, "arrivals": v[year]}
                for k, v in d.items() if v.get(year)]
        rows.sort(key=lambda r: -r["arrivals"])
        return rows[:n]

    doc = {
        "_comment": (
            "Refugee arrivals and asylum grants, from the DHS Yearbook. "
            "REFUGEES AND ASYLEES ARE COUNTED AT DIFFERENT MOMENTS and are "
            "never summed here: a refugee is admitted from abroad after "
            "approval, an asylee is already in the country when the grant is "
            "made. REFUGEE ADMISSION IS A POLICY CEILING set each year by "
            "presidential determination, so the series tracks decisions in "
            "Washington rather than demand -- a fall is a policy choice and "
            "must not be read as fewer people seeking admission. Included so "
            "the employment and study routes elsewhere in this project can be "
            "read against the whole rather than in isolation; the legal "
            "basis, the caps and the process are entirely separate."),
        "source": "DHS Office of Homeland Security Statistics, Yearbook of "
                  "Immigration Statistics, refugee and asylee tables",
        "source_url": "https://ohss.dhs.gov/topics/immigration/yearbook",
        "refugee_arrivals_by_year": annual,
        "refugee_years_by_country": _y,
        "refugee_top_nationalities": top(ref_country, ref_last) if ref_last else [],
        "asylee_years": asy_years,
        "asylee_top_nationalities": top(asy_country, asy_last) if asy_last else [],
        "warnings": warns,
    }
    write_json(OUT, doc)

    if annual:
        ys = sorted(annual)
        print(f"  refugee arrivals {ys[0]}-{ys[-1]}")
        for y in ys:
            if int(y) % 5 == 0 or y == ys[-1]:
                print(f"   {y}  {annual[y]:>9,}")
        peak = max(annual, key=lambda k: annual[k])
        print(f"   peak {annual[peak]:,} in {peak}; "
              f"low {min(annual.values()):,}")
    if doc["refugee_top_nationalities"]:
        print(f"\n  leading refugee nationalities, {ref_last}:")
        for r in doc["refugee_top_nationalities"][:6]:
            print(f"   {r['country'][:28]:30}{r['arrivals']:>8,}")
    if doc["asylee_top_nationalities"]:
        print(f"\n  leading asylee nationalities, {asy_last}:")
        for r in doc["asylee_top_nationalities"][:6]:
            print(f"   {r['country'][:28]:30}{r['arrivals']:>8,}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
