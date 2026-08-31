#!/usr/bin/env python3
"""H-1B wage violations found by the Department of Labor.

Every survey in this project reaches doctorate holders. The H-1B population
the leverage argument is actually about mostly holds a bachelor's or master's
and works in industry, and no survey here reaches them. This does: the Wage
and Hour Division's enforcement database records one row per investigation,
with the employer named and, where the H-1B provisions were violated, the
back wages agreed and the employees affected.

READ IT AS A FLOOR, NEVER AS A RATE. These are violations that were FOUND,
which requires a complaint to be filed or an investigation opened. Nothing
here counts violations that occurred, and a low number in a year or an
industry is not evidence of compliance -- it is equally consistent with
nobody complaining, which is exactly what the dependence described elsewhere
in this project would predict. That tension cannot be resolved from this
data, and stating it is part of using the data honestly.

BACK WAGES ARE "AGREED TO PAY" (the ATP columns), which is a finding and an
agreement, not proof of money collected.

Usage:
  python3 scripts/build_h1b_enforcement.py
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "WHD_enforcement.zip"
OUT = ROOT / "site" / "data" / "h1b_enforcement.json"

FIRST_YEAR = 2000          # 1999 has four cases; the series starts when it is real


def num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def clean_name(s: str) -> str:
    """Collapse whitespace and case only. No fuzzy grouping.

    An earlier name-matching pass in this project turned a military college
    into a trading firm; employers here are reported as filed and two
    spellings of one company stay two rows rather than being guessed into
    one.
    """
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()


def main() -> int:
    if not SRC.exists():
        print(f"  missing {SRC.relative_to(ROOT)}")
        return 1

    by_year: dict[int, dict] = defaultdict(
        lambda: {"cases": 0, "violations": 0, "back_wages": 0.0,
                 "employees": 0, "penalties": 0.0})
    employers: dict[str, dict] = {}
    industries: dict[str, dict] = defaultdict(
        lambda: {"cases": 0, "back_wages": 0.0, "employees": 0})
    totals = {"cases": 0, "violations": 0, "back_wages": 0.0,
              "employees": 0, "penalties": 0.0}
    undated = 0

    with zipfile.ZipFile(SRC) as z:
        for name in sorted(z.namelist()):
            if not name.lower().endswith(".csv"):
                continue
            with z.open(name) as fh:
                for r in csv.DictReader(io.TextIOWrapper(
                        fh, encoding="utf-8-sig", errors="replace")):
                    v = num(r.get("H1B_VIOLTN_CNT"))
                    if v <= 0:
                        continue
                    bw = num(r.get("H1B_BW_ATP_AMT"))
                    ee = int(num(r.get("H1B_EE_ATP_CNT")))
                    cmp_ = num(r.get("H1B_CMP_ASSD_AMT"))

                    totals["cases"] += 1
                    totals["violations"] += int(v)
                    totals["back_wages"] += bw
                    totals["employees"] += ee
                    totals["penalties"] += cmp_

                    end = (r.get("FINDINGS_END_DATE") or "").strip()
                    m = re.match(r"(\d{4})", end)
                    if m:
                        y = int(m.group(1))
                        b = by_year[y]
                        b["cases"] += 1
                        b["violations"] += int(v)
                        b["back_wages"] += bw
                        b["employees"] += ee
                        b["penalties"] += cmp_
                    else:
                        undated += 1

                    key = clean_name(r.get("LEGAL_NAME") or r.get("TRADE_NM"))
                    if key:
                        e = employers.setdefault(key, {
                            "employer": key, "cases": 0, "back_wages": 0.0,
                            "employees": 0, "penalties": 0.0,
                            "state": (r.get("ST_CD") or "").strip(),
                            "industry": (r.get("NAICS_CODE_DESCRIPTION") or "").strip()})
                        e["cases"] += 1
                        e["back_wages"] += bw
                        e["employees"] += ee
                        e["penalties"] += cmp_

                    ind = (r.get("NAICS_CODE_DESCRIPTION") or "").strip() or "Not recorded"
                    i = industries[ind]
                    i["cases"] += 1
                    i["back_wages"] += bw
                    i["employees"] += ee

    if totals["cases"] < 100:
        print(f"  only {totals['cases']} H-1B cases found")
        return 1

    years = sorted(y for y in by_year if FIRST_YEAR <= y)
    series = {str(y): {k: (round(v, 2) if isinstance(v, float) else v)
                       for k, v in by_year[y].items()} for y in years}
    top_bw = sorted(employers.values(), key=lambda e: -e["back_wages"])[:25]
    top_ee = sorted(employers.values(), key=lambda e: -e["employees"])[:25]
    top_ind = sorted(industries.items(), key=lambda kv: -kv[1]["back_wages"])[:15]

    # Enforcement against the size of the programme. Cases alone fall over
    # the period while issuances rise, and the ratio is the honest way to
    # show that -- with the same caveat doubled: it is enforcement INTENSITY,
    # the rate at which violations are found per visa issued, and says
    # nothing about the rate at which they occur.
    intensity = []
    vi_path = ROOT / "site" / "data" / "visa_issuances.json"
    if vi_path.exists():
        vi = json.loads(vi_path.read_text())
        for y in years:
            issued = vi["totals"].get(str(y), {}).get("H1B")
            if not issued:
                continue
            intensity.append({
                "year": y,
                "cases": by_year[y]["cases"],
                "h1b_issuances": issued,
                "cases_per_10k_issuances": round(
                    10_000 * by_year[y]["cases"] / issued, 2),
                "back_wages": round(by_year[y]["back_wages"], 2)})

    doc = {
        "_comment": (
            "H-1B provisions of the INA, as enforced by the DOL Wage and Hour "
            "Division. THIS IS A FLOOR, NEVER A RATE: these are violations "
            "FOUND, which requires a complaint or an investigation, so "
            "nothing here counts violations that occurred and a low figure is "
            "NOT evidence of compliance -- it is equally consistent with "
            "nobody complaining, which is what employer dependence would "
            "predict. BACK WAGES ARE 'AGREED TO PAY', a finding and an "
            "agreement, not money proven collected. Cases are dated by "
            "FINDINGS_END_DATE and an investigation can cover several earlier "
            "years. Employers are grouped on the filed legal name with case "
            "and whitespace normalised only -- nothing is fuzzy-matched, so "
            "two spellings of one company remain two rows and totals per "
            "company are a floor."),
        "source": "US DOL Wage and Hour Division enforcement database (WHISARD)",
        "source_url": "https://enforcedata.dol.gov/views/data_catalogs.php",
        "source_file": SRC.name,
        "cases_in_file": totals["cases"],
        "undated_cases": undated,
        "totals": {k: (round(v, 2) if isinstance(v, float) else v)
                   for k, v in totals.items()},
        "back_wages_per_employee": round(
            totals["back_wages"] / totals["employees"], 2) if totals["employees"] else None,
        "years": years,
        "series": series,
        "enforcement_intensity": intensity,
        "top_employers_by_back_wages": top_bw,
        "top_employers_by_employees": top_ee,
        "industries": [{"industry": k, **{kk: (round(vv, 2) if isinstance(vv, float) else vv)
                                          for kk, vv in v.items()}}
                       for k, v in top_ind],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {totals['cases']:,} H-1B cases, {years[0]}-{years[-1]}"
          f" ({undated} undated)")
    print(f"  ${totals['back_wages']:,.0f} back wages agreed, "
          f"{totals['employees']:,} employees, "
          f"${totals['penalties']:,.0f} penalties")
    print(f"  ${doc['back_wages_per_employee']:,.0f} per affected employee")
    print(f"\n  {'year':6}{'cases':>8}{'back wages':>15}{'employees':>11}")
    for y in years:
        if y % 4 == 0 or y == years[-1]:
            s = series[str(y)]
            print(f"  {y:6}{s['cases']:>8}${s['back_wages']:>14,.0f}"
                  f"{s['employees']:>11,}")
    if intensity:
        f, l = intensity[0], intensity[-1]
        peak = max(intensity, key=lambda x: x["cases_per_10k_issuances"])
        print(f"\n  enforcement intensity (cases per 10,000 H-1B issuances):")
        for r in (f, peak, l):
            print(f"   {r['year']}: {r['cases']:>3} cases / "
                  f"{r['h1b_issuances']:>7,} issuances = "
                  f"{r['cases_per_10k_issuances']:>5}")
    print(f"\n  largest by back wages:")
    for e in top_bw[:8]:
        print(f"   {e['employer'][:44]:46}${e['back_wages']:>12,.0f}"
              f"{e['employees']:>7,} ee")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
