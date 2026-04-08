#!/usr/bin/env python3
"""
Extract UK Home Office sponsored-study visa data into JSON for the
uk.html page.

Output: data/uk/uk_dashboard.json
"""
import json
import warnings
import openpyxl
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
UK = ROOT / "data" / "uk"
SRC = UK / "education-visas-datasets-sep-2025.xlsx"
OUT = UK / "uk_dashboard.json"


def load_grants():
    wb = openpyxl.load_workbook(SRC, data_only=True)
    ws = wb["Data_Edu_D02"]
    rows = list(ws.iter_rows(values_only=True))
    # Header row is row index 2
    header = rows[2]
    yr_idx = header.index("Year")
    nat_idx = header.index("Nationality")
    region_idx = header.index("Region")
    vt_idx = header.index("Visa type subgroup")
    level_idx = header.index("Course level")
    grants_idx = header.index("Grants")

    by_year = defaultdict(int)
    by_year_country = defaultdict(lambda: defaultdict(int))  # year → country → grants
    by_year_level = defaultdict(lambda: defaultdict(int))  # year → level → grants
    by_year_region = defaultdict(lambda: defaultdict(int))  # year → region → grants

    for r in rows[3:]:
        if not r or r[yr_idx] is None or r[grants_idx] is None:
            continue
        year = int(r[yr_idx])
        country = r[nat_idx] or "Unknown"
        region = r[region_idx] or "Unknown"
        level = r[level_idx] or "Unknown"
        grants = int(r[grants_idx]) if isinstance(r[grants_idx], (int, float)) else 0
        by_year[year] += grants
        by_year_country[year][country] += grants
        by_year_level[year][level] += grants
        by_year_region[year][region] += grants

    years = sorted(by_year.keys())

    # National total over time
    national_total = [by_year[y] for y in years]

    # Top 10 countries by total over the period
    country_totals = defaultdict(int)
    for y in years:
        for c, n in by_year_country[y].items():
            country_totals[c] += n
    top_countries = sorted(country_totals.items(), key=lambda kv: -kv[1])[:12]
    top_country_yearly = []
    for c, _ in top_countries:
        top_country_yearly.append({
            "country": c,
            "yearly": [by_year_country[y].get(c, 0) for y in years],
        })

    # By course level over time
    all_levels = sorted({lvl for d in by_year_level.values() for lvl in d.keys()})
    level_yearly = {}
    for lvl in all_levels:
        level_yearly[lvl] = [by_year_level[y].get(lvl, 0) for y in years]

    # By world region over time
    all_regions = sorted({r for d in by_year_region.values() for r in d.keys()})
    region_totals = defaultdict(int)
    for y in years:
        for r, n in by_year_region[y].items():
            region_totals[r] += n
    top_regions = [r for r, _ in sorted(region_totals.items(), key=lambda kv: -kv[1])[:8]]
    region_yearly = {}
    for r in top_regions:
        region_yearly[r] = [by_year_region[y].get(r, 0) for y in years]

    return {
        "years": years,
        "national_total": national_total,
        "top_countries": top_country_yearly,
        "by_level": level_yearly,
        "by_region": region_yearly,
    }


def main():
    out = {
        "source": "UK Home Office — Immigration System Statistics, sponsored study visa grants",
        "url": "https://www.gov.uk/government/statistical-data-sets/immigration-system-statistics-data-tables",
        "as_of": "year ending September 2025",
        "grants": load_grants(),
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"Wrote {OUT}")
    g = out["grants"]
    print(f"  years: {g['years']}")
    print(f"  national totals: {g['national_total']}")
    print(f"  top country: {g['top_countries'][0]['country']} = {sum(g['top_countries'][0]['yearly'])}")


if __name__ == "__main__":
    main()
