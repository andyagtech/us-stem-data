#!/usr/bin/env python3
"""
Build all Chart.js-ready JSON analyses from joined datasets.
Outputs 6 JSON files into data/analyses/
"""
import csv
import json
import os

BASE = "/Users/andy/usds_china/data"
OUT = f"{BASE}/analyses"

# ─────────────────────────────────────────────
# Country name normalization mapping
# Key = name as it appears in any source dataset
# Value = canonical name used in output
# ─────────────────────────────────────────────
COUNTRY_MAP = {
    # SEVIS (UPPERCASE)
    "CHINA": "China",
    "INDIA": "India",
    "SOUTH KOREA": "South Korea",
    "KOREA, REPUBLIC OF": "South Korea",
    "BANGLADESH": "Bangladesh",
    "SAUDI ARABIA": "Saudi Arabia",
    "IRAN": "Iran",
    "TAIWAN": "Taiwan",
    "CANADA": "Canada",
    "TURKEY": "Turkey",
    "BRAZIL": "Brazil",
    "NEPAL": "Nepal",
    "NIGERIA": "Nigeria",
    "MEXICO": "Mexico",
    "SRI LANKA": "Sri Lanka",
    "COLOMBIA": "Colombia",
    "PAKISTAN": "Pakistan",
    "ITALY": "Italy",
    "VIETNAM": "Vietnam",
    "GERMANY": "Germany",
    "EGYPT": "Egypt",
    "GHANA": "Ghana",
    "UNITED KINGDOM": "United Kingdom",
    "JAPAN": "Japan",
    "SPAIN": "Spain",
    "RUSSIA": "Russia",
    "FRANCE": "France",
    "THAILAND": "Thailand",
    "PHILIPPINES": "Philippines",
    "INDONESIA": "Indonesia",
    # NSF SED
    "Chinaa": "China",  # footnote marker
    "India": "India",
    "South Korea": "South Korea",
    "Bangladesh": "Bangladesh",
    "Saudi Arabia": "Saudi Arabia",
    "Iran": "Iran",
    "Taiwan": "Taiwan",
    "Canada": "Canada",
    "Turkey": "Turkey",
    "Brazil": "Brazil",
    "Nepal": "Nepal",
    "Nigeria": "Nigeria",
    "Mexico": "Mexico",
    "Sri Lanka": "Sri Lanka",
    "Colombia": "Colombia",
    "Pakistan": "Pakistan",
    "Italy": "Italy",
    "Vietnam": "Vietnam",
    "Germany": "Germany",
    "Egypt": "Egypt",
    "Ghana": "Ghana",
    "United Kingdom": "United Kingdom",
    "Japan": "Japan",
    "Spain": "Spain",
    "Russia": "Russia",
    "France": "France",
    "Thailand": "Thailand",
    "Philippines": "Philippines",
    "Indonesia": "Indonesia",
    # State Dept NIV
    "China - mainland": "China",
    "Korea, South": "South Korea",
    "Great Britain and Northern Ireland": "United Kingdom",
    # State Dept EB
    "China - mainland born": "China",
    "Korea, South": "South Korea",
    # B-visa refusal (UPPERCASE like SEVIS)
    "KOREA, SOUTH": "South Korea",
    "GREAT BRITAIN AND NORTHERN IRELAND": "United Kingdom",
}


def normalize(name):
    """Normalize a country name to canonical form."""
    name = name.strip()
    if name in COUNTRY_MAP:
        return COUNTRY_MAP[name]
    # Try title case
    if name.upper() in COUNTRY_MAP:
        return COUNTRY_MAP[name.upper()]
    # Try as-is (already canonical)
    return name


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


# =============================================
# Load all datasets
# =============================================

# 1. SEVIS active students
sevis_rows = read_csv(f"{BASE}/sevp/sevis_data_mapping_mar2026.csv")
sevis = {}
for r in sevis_rows:
    cname = normalize(r["Country of Citizenship"])
    try:
        sevis[cname] = int(r["Active Students"].replace(",", ""))
    except (ValueError, KeyError):
        pass

# 2. NSF SED PhDs (table 7-8, 2024)
sed78 = read_csv(f"{BASE}/nsf_sed/parsed/table_7_8_top_countries_2024.csv")
phd_count = {}
for r in sed78:
    cname = normalize(r["country"])
    try:
        phd_count[cname] = int(r["se"])
    except ValueError:
        pass

# 3. NSF SED stay rates (table 2-8)
sed28 = read_csv(f"{BASE}/nsf_sed/parsed/table_2_8_temp_visa_intending_stay_by_country.csv")
stay_rate = {}
phd_total_2024 = {}
for r in sed28:
    raw = r["region_country"].strip()
    cname = normalize(raw)
    try:
        val = r["2024_pct_staying"]
        if val and val != "D":
            stay_rate[cname] = float(val)
    except (ValueError, KeyError):
        pass
    try:
        val = r["2024_number"]
        if val and val != "D":
            phd_total_2024[cname] = int(float(val))
    except (ValueError, KeyError):
        pass

# 4. State Dept F-1 / H-1B issuances (FY2024)
niv_rows = read_csv(f"{BASE}/h1b/state_dept/niv_by_country_fy2024.csv")
f1_visa = {}
h1b_visa = {}
for r in niv_rows:
    raw = r["country"].strip()
    if raw.startswith("Totals") or raw == "Grand Total" or raw == "No Nationality":
        continue
    cname = normalize(raw)
    try:
        f1 = r["F1"].replace(",", "")
        if f1:
            f1_visa[cname] = f1_visa.get(cname, 0) + int(f1)
    except (ValueError, KeyError):
        pass
    try:
        h1b = r["H1B"].replace(",", "")
        if h1b:
            h1b_visa[cname] = h1b_visa.get(cname, 0) + int(h1b)
    except (ValueError, KeyError):
        pass

# 5. EB green cards
eb_rows = read_csv(f"{BASE}/h1b/state_dept/eb_visas_by_country_fy2024.csv")
eb_total = {}
eb_detail = {}
for r in eb_rows:
    raw = r["country"].strip()
    if raw.startswith("Region Total") or raw == "Grand Total" or raw == "TOTAL" or not raw:
        continue
    cname = normalize(raw)
    try:
        eb1 = int(r["EB1"]) if r["EB1"] else 0
        eb2 = int(r["EB2"]) if r["EB2"] else 0
        eb3t = int(r["EB3_total"]) if r["EB3_total"] else 0
        eb4t = int(r["EB4_total"]) if r["EB4_total"] else 0
        total = eb1 + eb2 + eb3t + eb4t
        if cname in eb_total:
            eb_total[cname] += total
            eb_detail[cname] = {
                "EB1": eb_detail[cname]["EB1"] + eb1,
                "EB2": eb_detail[cname]["EB2"] + eb2,
                "EB3": eb_detail[cname]["EB3"] + eb3t,
                "EB4": eb_detail[cname]["EB4"] + eb4t,
            }
        else:
            eb_total[cname] = total
            eb_detail[cname] = {"EB1": eb1, "EB2": eb2, "EB3": eb3t, "EB4": eb4t}
    except (ValueError, KeyError):
        pass

# 6. B-visa refusal rates
bvisa_rows = read_csv(f"{BASE}/h1b/state_dept/b_visa_refusal_rates_fy25.csv")
refusal = {}
for r in bvisa_rows:
    cname = normalize(r["country"])
    try:
        refusal[cname] = float(r["refusal_rate_pct"])
    except (ValueError, KeyError):
        pass

# 7. Time series (country-level)
ts_rows = read_csv(f"{BASE}/h1b/state_dept/niv_timeseries_key_countries.csv")
timeseries_by_country = {}
for r in ts_rows:
    fy = int(r["fiscal_year"])
    raw = r["country"].strip()
    cname = normalize(raw)
    if cname not in timeseries_by_country:
        timeseries_by_country[cname] = {}
    timeseries_by_country[cname][fy] = {
        "F1": int(r["F1_issuances"]),
        "H1B": int(r["H1B_issuances"]),
        "J1": int(r["J1_issuances"]),
    }

# 8. NSF SED time series (table 7-7)
sed77 = read_csv(f"{BASE}/nsf_sed/parsed/table_7_7_top_countries_by_field.csv")
phd_timeseries = {}
for r in sed77:
    raw = r["country_and_field"].strip()
    # Only take the total rows (country names without "Science and engineering" etc.)
    if "engineering" in raw.lower() or raw == "":
        continue
    cname = normalize(raw)
    phd_timeseries[cname] = {}
    for yr in range(2014, 2025):
        val = r.get(str(yr), "")
        if val and val != "D":
            phd_timeseries[cname][yr] = int(float(val))

# 9. National trends
with open(f"{BASE}/h1b/national_visa_trends.json") as f:
    nat_visa = json.load(f)
with open(f"{BASE}/h1b/national_opt_trends.json") as f:
    nat_opt = json.load(f)

# 10. STEM by country x state
stem_rows = read_csv(f"{BASE}/sevp/sevis_data_mapping_mar2026_stem.csv")

# =============================================
# ANALYSIS A: Full Pipeline by Country (Top 20)
# =============================================

# Determine top 20 by SEVIS active students
top20_countries = sorted(sevis.items(), key=lambda x: -x[1])[:20]
top20_names = [c[0] for c in top20_countries]

pipeline_data = {
    "_metadata": {
        "description": "Full immigration pipeline by country - from enrollment to green card (top 20 by active student count)",
        "sources": {
            "sevis_active": "SEVP SEVIS Data Mapping, March 2026",
            "phds": "NSF Survey of Earned Doctorates 2024, Table 7-8",
            "f1_visas": "State Dept NIV Detail Table, FY2024",
            "h1b_visas": "State Dept NIV Detail Table, FY2024",
            "eb_green_cards": "State Dept EB Visas by Country, FY2024",
        },
        "note": "F-1 and H-1B are visa stamps issued at consulates (excludes in-US status changes). EB includes EB-1 through EB-4.",
    },
    "labels": top20_names,
    "datasets": [
        {
            "label": "SEVIS Active Students (Mar 2026)",
            "data": [sevis.get(c, 0) for c in top20_names],
            "yAxisID": "y",
        },
        {
            "label": "F-1 Visas Issued (FY2024)",
            "data": [f1_visa.get(c, 0) for c in top20_names],
            "yAxisID": "y",
        },
        {
            "label": "PhDs Awarded (2024)",
            "data": [phd_count.get(c, 0) for c in top20_names],
            "yAxisID": "y2",
        },
        {
            "label": "H-1B Visas Issued (FY2024)",
            "data": [h1b_visa.get(c, 0) for c in top20_names],
            "yAxisID": "y",
        },
        {
            "label": "EB Green Cards (FY2024)",
            "data": [eb_total.get(c, 0) for c in top20_names],
            "yAxisID": "y2",
        },
    ],
    "chartConfig": {
        "type": "bar",
        "options": {
            "responsive": True,
            "plugins": {"title": {"display": True, "text": "Immigration Pipeline: Enrollment → PhD → Work Visa → Green Card (Top 20 Countries)"}},
            "scales": {
                "y": {"type": "linear", "position": "left", "title": {"display": True, "text": "Count (Students / Visas)"}},
                "y2": {"type": "linear", "position": "right", "title": {"display": True, "text": "Count (PhDs / Green Cards)"}, "grid": {"drawOnChartArea": False}},
            },
        },
    },
}

with open(f"{OUT}/pipeline_by_country.json", "w") as f:
    json.dump(pipeline_data, f, indent=2)
print("✓ pipeline_by_country.json")


# =============================================
# ANALYSIS B: China vs India Time Series
# =============================================

years_ts = list(range(2010, 2025))

china_ts = timeseries_by_country.get("China", {})
india_ts = timeseries_by_country.get("India", {})
china_phd_ts = phd_timeseries.get("China", {})
india_phd_ts = phd_timeseries.get("India", {})

china_india_data = {
    "_metadata": {
        "description": "China vs India divergence: F-1 visas, H-1B visas, and PhD production (2010-2024)",
        "sources": {
            "f1_h1b": "State Dept NIV Detail Table, FY2010-2024 (niv_timeseries_key_countries.csv)",
            "phds": "NSF SED Table 7-7 (top countries by field, 2014-2024)",
        },
    },
    "labels": years_ts,
    "datasets": [
        {
            "label": "China F-1 Issuances",
            "data": [china_ts.get(y, {}).get("F1") if isinstance(china_ts.get(y), dict) else china_ts.get(y, {}).get("F1") for y in years_ts],
            "borderColor": "#e63946",
            "borderDash": [],
            "yAxisID": "y",
        },
        {
            "label": "India F-1 Issuances",
            "data": [india_ts.get(y, {}).get("F1") if isinstance(india_ts.get(y), dict) else None for y in years_ts],
            "borderColor": "#457b9d",
            "borderDash": [],
            "yAxisID": "y",
        },
        {
            "label": "China H-1B Issuances",
            "data": [china_ts.get(y, {}).get("H1B") if isinstance(china_ts.get(y), dict) else None for y in years_ts],
            "borderColor": "#e63946",
            "borderDash": [5, 5],
            "yAxisID": "y",
        },
        {
            "label": "India H-1B Issuances",
            "data": [india_ts.get(y, {}).get("H1B") if isinstance(india_ts.get(y), dict) else None for y in years_ts],
            "borderColor": "#457b9d",
            "borderDash": [5, 5],
            "yAxisID": "y",
        },
        {
            "label": "China PhDs Awarded",
            "data": [china_phd_ts.get(y) for y in years_ts],
            "borderColor": "#e63946",
            "borderDash": [2, 2],
            "yAxisID": "y2",
        },
        {
            "label": "India PhDs Awarded",
            "data": [india_phd_ts.get(y) for y in years_ts],
            "borderColor": "#457b9d",
            "borderDash": [2, 2],
            "yAxisID": "y2",
        },
    ],
    "chartConfig": {
        "type": "line",
        "options": {
            "responsive": True,
            "plugins": {"title": {"display": True, "text": "China vs India: F-1, H-1B, and PhD Trends (2010-2024)"}},
            "scales": {
                "y": {"type": "linear", "position": "left", "title": {"display": True, "text": "Visa Issuances"}},
                "y2": {"type": "linear", "position": "right", "title": {"display": True, "text": "PhDs Awarded"}, "grid": {"drawOnChartArea": False}},
            },
        },
    },
}

# Clean up None values for JSON (replace dict-based extraction)
for ds in china_india_data["datasets"]:
    ds["data"] = [
        (v if v is not None else None) for v in ds["data"]
    ]

with open(f"{OUT}/china_vs_india_timeseries.json", "w") as f:
    json.dump(china_india_data, f, indent=2)
print("✓ china_vs_india_timeseries.json")


# =============================================
# ANALYSIS C: Stay Rate vs Refusal Rate Scatter
# =============================================

# Map continents from SEVIS data
continent_map = {}
for r in sevis_rows:
    cname = normalize(r["Country of Citizenship"])
    continent_map[cname] = r.get("Continent", "Unknown")

scatter_countries = []
for cname in set(stay_rate.keys()) & set(refusal.keys()):
    phds = phd_total_2024.get(cname, phd_count.get(cname, 0))
    if phds and phds >= 20:  # only countries with meaningful PhD output
        scatter_countries.append({
            "country": cname,
            "x": refusal[cname],
            "y": stay_rate[cname],
            "r": max(3, min(40, phds / 100)),  # bubble radius scaled
            "phds": phds,
            "continent": continent_map.get(cname, "Unknown"),
        })

# Color by continent
continent_colors = {
    "Asia": "#e63946",
    "Europe": "#457b9d",
    "Africa": "#2a9d8f",
    "South America": "#e9c46a",
    "North America": "#f4a261",
    "Australia&Pacific Islands": "#264653",
    "Unknown": "#999999",
    "N/A": "#999999",
}

# Group by continent for separate datasets
by_continent = {}
for pt in scatter_countries:
    cont = pt["continent"]
    if cont not in by_continent:
        by_continent[cont] = []
    by_continent[cont].append(pt)

scatter_datasets = []
for cont, points in sorted(by_continent.items()):
    scatter_datasets.append({
        "label": cont,
        "data": [{"x": p["x"], "y": p["y"], "r": p["r"], "country": p["country"], "phds": p["phds"]} for p in points],
        "backgroundColor": continent_colors.get(cont, "#999") + "88",
        "borderColor": continent_colors.get(cont, "#999"),
    })

stay_refusal_data = {
    "_metadata": {
        "description": "PhD stay rate (% intending to remain in US) vs B-visa refusal rate, bubble size = PhD count",
        "sources": {
            "stay_rate": "NSF SED Table 2-8 (2024 % intending to stay)",
            "refusal_rate": "State Dept B-visa adjusted refusal rates, FY2025",
            "phd_count": "NSF SED Table 2-8 / Table 7-8 (2024)",
        },
        "note": "Only countries with 20+ PhDs in 2024 shown. Bubble radius = PhDs/100, clamped 3-40px.",
    },
    "datasets": scatter_datasets,
    "chartConfig": {
        "type": "bubble",
        "options": {
            "responsive": True,
            "plugins": {
                "title": {"display": True, "text": "PhD Stay Rate vs B-Visa Refusal Rate by Country"},
                "tooltip": {
                    "callbacks": {
                        "_note": "Use custom tooltip to show country name, exact values"
                    }
                },
            },
            "scales": {
                "x": {"title": {"display": True, "text": "B-Visa Refusal Rate (%, FY2025)"}},
                "y": {"title": {"display": True, "text": "% of PhD Recipients Intending to Stay in US (2024)"}},
            },
        },
    },
}

with open(f"{OUT}/stay_rate_vs_refusal.json", "w") as f:
    json.dump(stay_refusal_data, f, indent=2)
print("✓ stay_rate_vs_refusal.json")


# =============================================
# ANALYSIS D: EB Green Card Bottleneck
# =============================================

# Countries that appear in both PhD and EB data
eb_countries = []
for cname in set(phd_count.keys()) & set(eb_total.keys()):
    if phd_count[cname] >= 50:  # meaningful PhD count
        eb_countries.append(cname)

eb_countries.sort(key=lambda c: -phd_count.get(c, 0))
eb_countries = eb_countries[:20]

bottleneck_data = {
    "_metadata": {
        "description": "PhD production vs EB green card availability - pipeline bottleneck analysis",
        "sources": {
            "phds": "NSF SED Table 7-8, 2024",
            "eb_visas": "State Dept EB Visas by Country, FY2024 (EB-1 through EB-4)",
        },
        "note": "Ratio > 1 means more new PhDs than EB visas issued; indicates building backlog. EB visas serve all employment-based immigrants (not just PhDs).",
    },
    "labels": eb_countries,
    "datasets": [
        {
            "label": "PhDs Awarded (2024)",
            "data": [phd_count.get(c, 0) for c in eb_countries],
            "backgroundColor": "#e63946aa",
            "yAxisID": "y",
        },
        {
            "label": "EB Green Cards Issued (FY2024)",
            "data": [eb_total.get(c, 0) for c in eb_countries],
            "backgroundColor": "#457b9daa",
            "yAxisID": "y",
        },
    ],
    "ratios": {
        c: round(phd_count.get(c, 0) / eb_total[c], 2) if eb_total.get(c, 0) > 0 else None
        for c in eb_countries
    },
    "eb_breakdown": {
        c: eb_detail.get(c, {}) for c in eb_countries
    },
    "chartConfig": {
        "type": "bar",
        "options": {
            "responsive": True,
            "plugins": {"title": {"display": True, "text": "PhD Production vs EB Green Card Capacity by Country"}},
            "scales": {
                "y": {"title": {"display": True, "text": "Count"}},
            },
        },
    },
}

with open(f"{OUT}/eb_bottleneck.json", "w") as f:
    json.dump(bottleneck_data, f, indent=2)
print("✓ eb_bottleneck.json")


# =============================================
# ANALYSIS E: STEM by Country x State (Top 10 x Top 10)
# =============================================

# Aggregate STEM students by country and state
stem_agg = {}  # (country, state_abbr) -> count
country_totals = {}
state_totals = {}

for r in stem_rows:
    cname = normalize(r["CoC"])
    st = r["Abbrv"]
    try:
        cnt = int(r["Count of Active STEM Students"])
    except (ValueError, KeyError):
        continue
    key = (cname, st)
    stem_agg[key] = stem_agg.get(key, 0) + cnt
    country_totals[cname] = country_totals.get(cname, 0) + cnt
    state_totals[st] = state_totals.get(st, 0) + cnt

top10_countries_stem = sorted(country_totals.items(), key=lambda x: -x[1])[:10]
top10_states_stem = sorted(state_totals.items(), key=lambda x: -x[1])[:10]
top10_c_names = [c[0] for c in top10_countries_stem]
top10_s_names = [s[0] for s in top10_states_stem]

matrix = []
for cname in top10_c_names:
    row = [stem_agg.get((cname, st), 0) for st in top10_s_names]
    matrix.append(row)

stem_matrix_data = {
    "_metadata": {
        "description": "STEM student enrollment heatmap: Top 10 countries x Top 10 US states",
        "source": "SEVP SEVIS STEM Data Mapping, March 2026",
    },
    "countries": top10_c_names,
    "states": top10_s_names,
    "matrix": matrix,
    "country_totals": {c: country_totals[c] for c in top10_c_names},
    "state_totals": {s: state_totals[s] for s in top10_s_names},
    "chartConfig": {
        "type": "matrix",
        "_note": "Use chartjs-chart-matrix plugin or render as HTML table with color scaling",
        "options": {
            "responsive": True,
            "plugins": {"title": {"display": True, "text": "STEM Student Concentration: Top 10 Countries × Top 10 US States"}},
        },
    },
}

with open(f"{OUT}/stem_country_state_matrix.json", "w") as f:
    json.dump(stem_matrix_data, f, indent=2)
print("✓ stem_country_state_matrix.json")


# =============================================
# ANALYSIS G: National Pipeline Time Series (indexed to 2010=100)
# =============================================

BASE_YEAR = 2010
YEARS_NAT = list(range(2010, 2025))


def get_series(data_dict, years):
    """Extract numeric values from a dict, skipping metadata keys."""
    result = {}
    for y in years:
        val = data_dict.get(str(y))
        if val is not None and not isinstance(val, dict) and not isinstance(val, str):
            result[y] = val
    return result


def index_to_base(series, base_year):
    """Index a series so base_year = 100."""
    base_val = series.get(base_year)
    if not base_val or base_val == 0:
        return {y: None for y in series}
    return {y: round(v / base_val * 100, 1) for y, v in series.items()}


f1_series = get_series(nat_visa["f1_issuances"], YEARS_NAT)
h1b_iss_series = get_series(nat_visa["h1b_issuances"], YEARS_NAT)
h1b_pet_series = get_series(nat_visa["h1b_petitions_approved"], YEARS_NAT)
j1_series = get_series(nat_visa["j1_issuances"], YEARS_NAT)
o1_series = get_series(nat_visa["o1_issuances"], YEARS_NAT)

opt_series = {y: nat_opt[str(y)]["opt"] for y in YEARS_NAT if str(y) in nat_opt}
stem_opt_series = {y: nat_opt[str(y)]["stem_opt"] for y in YEARS_NAT if str(y) in nat_opt}
cpt_series = {y: nat_opt[str(y)]["cpt"] for y in YEARS_NAT if str(y) in nat_opt}

all_raw = {
    "F-1 Issuances": f1_series,
    "H-1B Issuances (consular)": h1b_iss_series,
    "H-1B Petitions Approved": h1b_pet_series,
    "J-1 Issuances": j1_series,
    "O-1 Issuances": o1_series,
    "OPT Authorizations": opt_series,
    "STEM-OPT Extensions": stem_opt_series,
    "CPT Authorizations": cpt_series,
}

all_indexed = {name: index_to_base(series, BASE_YEAR) for name, series in all_raw.items()}

colors_nat = {
    "F-1 Issuances": "#e63946",
    "H-1B Issuances (consular)": "#457b9d",
    "H-1B Petitions Approved": "#1d3557",
    "J-1 Issuances": "#2a9d8f",
    "O-1 Issuances": "#264653",
    "OPT Authorizations": "#e9c46a",
    "STEM-OPT Extensions": "#f4a261",
    "CPT Authorizations": "#a8dadc",
}

dash_nat = {
    "F-1 Issuances": [],
    "H-1B Issuances (consular)": [],
    "H-1B Petitions Approved": [5, 5],
    "J-1 Issuances": [],
    "O-1 Issuances": [2, 2],
    "OPT Authorizations": [],
    "STEM-OPT Extensions": [],
    "CPT Authorizations": [8, 4],
}

nat_datasets = []
for name in all_raw:
    indexed = all_indexed[name]
    nat_datasets.append({
        "label": name,
        "data": [indexed.get(y) for y in YEARS_NAT],
        "borderColor": colors_nat[name],
        "borderDash": dash_nat[name],
        "fill": False,
    })

national_data = {
    "_metadata": {
        "description": f"National immigration pipeline trends, indexed to {BASE_YEAR}=100",
        "sources": {
            "visa_issuances": "State Dept Annual Reports (F-1, H-1B, J-1, O-1 stamps issued at consulates)",
            "h1b_petitions": "USCIS H-1B trend tables and Annual Reports to Congress",
            "opt_cpt": "SEVP OPT/CPT authorization data (national_opt_trends.json)",
        },
        "note": f"All series indexed to {BASE_YEAR}=100. STEM-OPT was very small in {BASE_YEAR} (9,356) so its indexed growth appears extreme.",
    },
    "labels": YEARS_NAT,
    "raw_values": {name: {str(y): v for y, v in series.items()} for name, series in all_raw.items()},
    "datasets": nat_datasets,
    "chartConfig": {
        "type": "line",
        "options": {
            "responsive": True,
            "plugins": {"title": {"display": True, "text": f"National Immigration Pipeline Trends (Indexed: {BASE_YEAR}=100)"}},
            "scales": {
                "y": {"title": {"display": True, "text": f"Index ({BASE_YEAR}=100)"}},
                "x": {"title": {"display": True, "text": "Fiscal Year"}},
            },
        },
    },
}

with open(f"{OUT}/national_pipeline_indexed.json", "w") as f:
    json.dump(national_data, f, indent=2)
print("✓ national_pipeline_indexed.json")


print("\n=== All 6 analysis files written to data/analyses/ ===")
