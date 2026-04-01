#!/usr/bin/env python3
"""
Build an interactive HTML dashboard from IPEDS STEM PhD data.

Reads raw IPEDS completions files to extract demographic breakdowns,
aggregates data, and produces a self-contained HTML file with Chart.js.

Usage:
    python scripts/build_dashboard.py
    python scripts/build_dashboard.py --output dashboard.html
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd

from ipeds_config import (
    ALL_YEARS,
    AWLEVEL_TRANSITION_YEARS,
    CIP_FAMILIES,
    IPEDS_COMBINED_OUTPUT,
    IPEDS_DATA_DIR,
    YEAR_FILES,
    phd_awlevels,
)
from ipeds_filter import (
    _find_csv,
    _normalize_cipcode,
    _read_csv_robust,
    _filter_transition_year,
)

log = logging.getLogger("build_dashboard")

# ---------------------------------------------------------------------------
# Demographic column mapping across IPEDS eras
# ---------------------------------------------------------------------------

# 1995-2009 CRACE codes → canonical names
CRACE_MAP = {
    "CRACE15": "Total_Men",
    "CRACE16": "Total_Women",
    "CRACE01": "NonresAlien_Men",
    "CRACE02": "NonresAlien_Women",
    "CRACE03": "Black_Men",
    "CRACE04": "Black_Women",
    "CRACE05": "AmerIndian_Men",
    "CRACE06": "AmerIndian_Women",
    "CRACE07": "Asian_Men",
    "CRACE08": "Asian_Women",
    "CRACE09": "Hispanic_Men",
    "CRACE10": "Hispanic_Women",
    "CRACE11": "White_Men",
    "CRACE12": "White_Women",
    "CRACE13": "Unknown_Men",
    "CRACE14": "Unknown_Women",
}

# 2010+ named columns → canonical names
MODERN_MAP = {
    "CTOTALM": "Total_Men",
    "CTOTALW": "Total_Women",
    "CTOTALT": "Total",
    "CNRALM": "NonresAlien_Men",
    "CNRALW": "NonresAlien_Women",
    "CNRALT": "NonresAlien_Total",
    "CASIAM": "Asian_Men",
    "CASIAW": "Asian_Women",
    "CASIAT": "Asian_Total",
    "CBKAAM": "Black_Men",
    "CBKAAW": "Black_Women",
    "CBKAAT": "Black_Total",
    "CHISPM": "Hispanic_Men",
    "CHISPW": "Hispanic_Women",
    "CHISPT": "Hispanic_Total",
    "CAIANM": "AmerIndian_Men",
    "CAIANW": "AmerIndian_Women",
    "CAIANT": "AmerIndian_Total",
    "CNHPIM": "NHPI_Men",
    "CNHPIW": "NHPI_Women",
    "CNHPIT": "NHPI_Total",
    "CWHITM": "White_Men",
    "CWHITW": "White_Women",
    "CWHITT": "White_Total",
    "C2MORM": "TwoOrMore_Men",
    "C2MORW": "TwoOrMore_Women",
    "C2MORT": "TwoOrMore_Total",
    "CUNKNM": "Unknown_Men",
    "CUNKNW": "Unknown_Women",
    "CUNKNT": "Unknown_Total",
}

# Aggregate race groups for charts
RACE_GROUPS = [
    "White", "Asian", "NonresAlien", "Hispanic", "Black",
    "AmerIndian", "NHPI", "TwoOrMore", "Unknown",
]

RACE_LABELS = {
    "White": "White",
    "Asian": "Asian",
    "NonresAlien": "Nonresident Alien (International)",
    "Hispanic": "Hispanic/Latino",
    "Black": "Black/African American",
    "AmerIndian": "American Indian/Alaska Native",
    "NHPI": "Native Hawaiian/Pacific Islander",
    "TwoOrMore": "Two or More Races",
    "Unknown": "Unknown",
}


def _extract_demographics(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Extract and normalize demographic columns from raw completions."""
    cols = set(df.columns)

    result = df[["UNITID", "CIPCODE", "AWLEVEL"]].copy()

    if year >= 2010:
        for raw_col, canon in MODERN_MAP.items():
            if raw_col in cols:
                result[canon] = pd.to_numeric(df[raw_col], errors="coerce").fillna(0).clip(lower=0).astype(int)
    elif year >= 1995:
        for raw_col, canon in CRACE_MAP.items():
            if raw_col in cols:
                result[canon] = pd.to_numeric(df[raw_col], errors="coerce").fillna(0).clip(lower=0).astype(int)
        # Compute totals from men+women for race groups
        for group in RACE_GROUPS:
            m_col = f"{group}_Men"
            w_col = f"{group}_Women"
            t_col = f"{group}_Total"
            if m_col in result.columns and w_col in result.columns and t_col not in result.columns:
                result[t_col] = result[m_col] + result[w_col]
        if "Total_Men" in result.columns and "Total_Women" in result.columns and "Total" not in result.columns:
            result["Total"] = result["Total_Men"] + result["Total_Women"]
    else:
        # 1984-1994: only total men/women
        if "CRACE15" in cols:
            result["Total_Men"] = pd.to_numeric(df["CRACE15"], errors="coerce").fillna(0).clip(lower=0).astype(int)
            result["Total_Women"] = pd.to_numeric(df["CRACE16"], errors="coerce").fillna(0).clip(lower=0).astype(int)
            result["Total"] = result["Total_Men"] + result["Total_Women"]

    return result


def build_enriched_data() -> pd.DataFrame:
    """Build enriched dataset with demographics from raw IPEDS files."""
    all_rows = []

    for year in sorted(YEAR_FILES.keys()):
        yf = YEAR_FILES[year]
        path = _find_csv(yf.completions, IPEDS_DATA_DIR)
        if not path:
            continue

        log.info("[%d] Loading %s...", year, os.path.basename(path))
        df = _read_csv_robust(path)
        df.columns = df.columns.str.upper().str.strip()

        # Apply PhD filter
        if year in AWLEVEL_TRANSITION_YEARS:
            phd_df = _filter_transition_year(df)
        else:
            awl = phd_awlevels(year)
            phd_df = df[df["AWLEVEL"].isin(awl)].copy()

        if phd_df.empty:
            continue

        # Normalize CIP codes and filter for STEM
        phd_df["CIPCODE"] = _normalize_cipcode(phd_df["CIPCODE"])
        cip2 = phd_df["CIPCODE"].str.split(".").str[0].str.zfill(2)
        stem_mask = cip2.isin(set(CIP_FAMILIES.keys()))
        stem_df = phd_df[stem_mask].copy()
        stem_df["CIP2"] = cip2[stem_mask].values

        if stem_df.empty:
            continue

        # Extract demographics
        demo = _extract_demographics(stem_df, year)

        # Add metadata
        demo["Year"] = year
        demo["CIP2"] = stem_df["CIP2"].values
        demo["Discipline"] = demo["CIP2"].map(lambda x: CIP_FAMILIES.get(x, ("Unknown", "Unknown"))[0])
        demo["Category"] = demo["CIP2"].map(lambda x: CIP_FAMILIES.get(x, ("Unknown", "Unknown"))[1])

        all_rows.append(demo)
        log.info("  → %d STEM PhD rows", len(demo))

    enriched = pd.concat(all_rows, ignore_index=True)
    log.info("Total enriched rows: %s", f"{len(enriched):,}")
    return enriched


def aggregate_for_dashboard(enriched: pd.DataFrame) -> dict:
    """Pre-aggregate data into JSON-friendly structures for the dashboard."""
    data = {}

    # --- 1. National trends by discipline ---
    disc_year = enriched.groupby(["Year", "Discipline"]).agg(
        Total=("Total", "sum") if "Total" in enriched.columns else ("Total_Men", lambda x: 0),
        Institutions=("UNITID", "nunique"),
    ).reset_index()

    trends_by_disc = {}
    for disc in sorted(enriched["Discipline"].unique()):
        sub = disc_year[disc_year["Discipline"] == disc].sort_values("Year")
        trends_by_disc[disc] = {
            "years": sub["Year"].tolist(),
            "totals": sub["Total"].tolist(),
            "institutions": sub["Institutions"].tolist(),
        }
    data["trends_by_discipline"] = trends_by_disc

    # --- 2. National total trend ---
    nat = enriched.groupby("Year").agg(
        Total=("Total", "sum"),
        Institutions=("UNITID", "nunique"),
    ).reset_index().sort_values("Year")
    data["national_trend"] = {
        "years": nat["Year"].tolist(),
        "totals": nat["Total"].tolist(),
        "institutions": nat["Institutions"].tolist(),
    }

    # --- 3. Race/ethnicity trends (years where data is available) ---
    race_cols = [f"{g}_Total" for g in RACE_GROUPS]
    avail_race_cols = [c for c in race_cols if c in enriched.columns]

    if avail_race_cols:
        # Only include years that have race data
        race_data = enriched[enriched[avail_race_cols].sum(axis=1) > 0]
        race_year = race_data.groupby("Year")[avail_race_cols].sum().reset_index().sort_values("Year")

        data["race_trends"] = {
            "years": race_year["Year"].tolist(),
        }
        for col in avail_race_cols:
            group = col.replace("_Total", "")
            label = RACE_LABELS.get(group, group)
            data["race_trends"][group] = {
                "label": label,
                "values": race_year[col].tolist(),
            }

    # --- 4. Race by discipline (latest year with full data) ---
    if avail_race_cols:
        latest_year = enriched[enriched[avail_race_cols].sum(axis=1) > 0]["Year"].max()
        latest = enriched[enriched["Year"] == latest_year]
        race_disc = latest.groupby("Discipline")[avail_race_cols].sum().reset_index()
        data["race_by_discipline"] = {
            "year": int(latest_year),
            "disciplines": race_disc["Discipline"].tolist(),
        }
        for col in avail_race_cols:
            group = col.replace("_Total", "")
            data["race_by_discipline"][group] = race_disc[col].tolist()

    # --- 5. Gender trends ---
    gender_cols = ["Total_Men", "Total_Women"]
    if all(c in enriched.columns for c in gender_cols):
        gender_data = enriched[enriched[gender_cols].sum(axis=1) > 0]
        gender_year = gender_data.groupby("Year")[gender_cols].sum().reset_index().sort_values("Year")
        data["gender_trends"] = {
            "years": gender_year["Year"].tolist(),
            "men": gender_year["Total_Men"].tolist(),
            "women": gender_year["Total_Women"].tolist(),
        }

    # --- 6. Top institutions ---
    # Load university names from combined output
    combined = pd.read_csv(IPEDS_COMBINED_OUTPUT)
    name_map = combined.drop_duplicates("UNITID", keep="last").set_index("UNITID")[["University", "State"]].to_dict("index")

    # All-time top 25
    inst_totals = enriched.groupby("UNITID").agg(Total=("Total", "sum")).reset_index()
    inst_totals = inst_totals.nlargest(25, "Total")
    inst_list = []
    for _, row in inst_totals.iterrows():
        info = name_map.get(row["UNITID"], {"University": f"UNITID {row['UNITID']}", "State": "?"})
        inst_list.append({
            "unitid": int(row["UNITID"]),
            "name": str(info["University"]),
            "state": str(info["State"]),
            "total": int(row["Total"]),
        })
    data["top_institutions"] = inst_list

    # --- 7. Top institutions by discipline ---
    top_by_disc = {}
    for disc in sorted(enriched["Discipline"].unique()):
        sub = enriched[enriched["Discipline"] == disc]
        inst_disc = sub.groupby("UNITID").agg(Total=("Total", "sum")).reset_index()
        inst_disc = inst_disc.nlargest(15, "Total")
        entries = []
        for _, row in inst_disc.iterrows():
            info = name_map.get(row["UNITID"], {"University": f"UNITID {row['UNITID']}", "State": "?"})
            entries.append({
                "name": str(info["University"]),
                "state": str(info["State"]),
                "total": int(row["Total"]),
            })
        top_by_disc[disc] = entries
    data["top_by_discipline"] = top_by_disc

    # --- 8. State totals ---
    state_data = enriched.merge(
        combined[["UNITID", "State"]].drop_duplicates("UNITID", keep="last"),
        on="UNITID", how="left"
    )
    state_totals = state_data.groupby("State").agg(
        Total=("Total", "sum"),
        Institutions=("UNITID", "nunique"),
    ).reset_index().sort_values("Total", ascending=False)
    data["state_totals"] = {
        "states": state_totals["State"].tolist(),
        "totals": state_totals["Total"].tolist(),
        "institutions": state_totals["Institutions"].tolist(),
    }

    # --- 9. Institution detail for search (all institutions) ---
    inst_all = enriched.groupby("UNITID").agg(
        Total=("Total", "sum"),
        Years=("Year", "nunique"),
        FirstYear=("Year", "min"),
        LastYear=("Year", "max"),
    ).reset_index()
    inst_details = []
    for _, row in inst_all.iterrows():
        info = name_map.get(row["UNITID"], {"University": f"UNITID {row['UNITID']}", "State": "?"})
        inst_details.append({
            "unitid": int(row["UNITID"]),
            "name": str(info["University"]),
            "state": str(info["State"]),
            "total": int(row["Total"]),
            "years": int(row["Years"]),
            "first": int(row["FirstYear"]),
            "last": int(row["LastYear"]),
        })
    data["all_institutions"] = sorted(inst_details, key=lambda x: -x["total"])

    # --- 10. Per-institution yearly trend (top 10 only, to keep size manageable) ---
    top10_ids = [i["unitid"] for i in inst_list[:10]]
    inst_trends = {}
    for uid in top10_ids:
        sub = enriched[enriched["UNITID"] == uid].groupby("Year").agg(Total=("Total", "sum")).reset_index().sort_values("Year")
        info = name_map.get(uid, {"University": f"UNITID {uid}"})
        inst_trends[str(uid)] = {
            "name": str(info["University"]),
            "years": sub["Year"].tolist(),
            "totals": sub["Total"].tolist(),
        }
    data["institution_trends"] = inst_trends

    return data


def generate_html(dashboard_data: dict, output_path: str):
    """Generate self-contained HTML dashboard."""
    json_data = json.dumps(dashboard_data, indent=None)

    # Use string concatenation to avoid f-string/JS template literal conflicts.
    # The JS code is stored as a plain string — no Python interpolation.
    html_before_data = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IPEDS STEM PhD Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0f172a; --surface: #1e293b; --border: #334155;
    --text: #e2e8f0; --text-muted: #94a3b8; --accent: #38bdf8;
    --green: #4ade80; --red: #f87171; --yellow: #facc15;
    --purple: #a78bfa; --pink: #f472b6; --orange: #fb923c;
    --teal: #2dd4bf; --indigo: #818cf8;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
  .header { background: linear-gradient(135deg, #1e3a5f, #0f172a); padding: 2rem; text-align: center; border-bottom: 1px solid var(--border); }
  .header h1 { font-size: 1.8rem; font-weight: 700; margin-bottom: 0.3rem; }
  .header .subtitle { color: var(--text-muted); font-size: 0.95rem; }
  .stats-bar { display: flex; justify-content: center; gap: 2rem; padding: 1rem 2rem; background: var(--surface); border-bottom: 1px solid var(--border); flex-wrap: wrap; }
  .stat { text-align: center; }
  .stat .value { font-size: 1.5rem; font-weight: 700; color: var(--accent); }
  .stat .label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .tabs { display: flex; gap: 0; border-bottom: 2px solid var(--border); padding: 0 2rem; background: var(--surface); flex-wrap: wrap; }
  .tab { padding: 0.75rem 1.25rem; cursor: pointer; color: var(--text-muted); border-bottom: 2px solid transparent; margin-bottom: -2px; font-size: 0.9rem; transition: all 0.2s; }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
  .content { max-width: 1200px; margin: 0 auto; padding: 1.5rem; }
  .panel { display: none; }
  .panel.active { display: block; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }
  .card h2 { font-size: 1.1rem; margin-bottom: 1rem; color: var(--accent); }
  .card h3 { font-size: 0.95rem; margin-bottom: 0.75rem; color: var(--text-muted); }
  .chart-container { position: relative; width: 100%; }
  .chart-container.tall { height: 500px; }
  .chart-container.medium { height: 400px; }
  .chart-container.short { height: 300px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th, td { padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }
  th { color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
  tr:hover { background: rgba(56,189,248,0.05); }
  .rank { color: var(--text-muted); width: 2rem; }
  .search { width: 100%; padding: 0.6rem 1rem; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 0.9rem; margin-bottom: 1rem; }
  .search:focus { outline: none; border-color: var(--accent); }
  select { padding: 0.5rem; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 0.85rem; }
  .note { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem; font-style: italic; }
</style>
</head>
<body>

<div class="header">
  <h1>IPEDS STEM PhD Completions Dashboard</h1>
  <div class="subtitle">Research Doctorates in STEM &amp; Clinical Fields &bull; 1984&ndash;2024</div>
</div>

<div class="stats-bar" id="statsBar"></div>

<div class="tabs" id="tabBar">
  <div class="tab active" data-panel="trends">Trends by Discipline</div>
  <div class="tab" data-panel="demographics">Demographics</div>
  <div class="tab" data-panel="institutions">Institutions</div>
  <div class="tab" data-panel="states">States</div>
</div>

<div class="content">
  <div class="panel active" id="panel-trends">
    <div class="card">
      <h2>National STEM PhD Completions Over Time</h2>
      <div class="chart-container tall"><canvas id="chartNational"></canvas></div>
    </div>
    <div class="card">
      <h2>Trends by STEM Discipline</h2>
      <div class="chart-container tall"><canvas id="chartByDisc"></canvas></div>
    </div>
    <div class="card">
      <h2>Discipline Share Over Time</h2>
      <div class="chart-container tall"><canvas id="chartDiscShare"></canvas></div>
      <p class="note">Stacked area showing each discipline's share of total STEM PhD completions.</p>
    </div>
  </div>

  <div class="panel" id="panel-demographics">
    <div class="card">
      <h2>Race/Ethnicity Composition Over Time</h2>
      <div class="chart-container tall"><canvas id="chartRace"></canvas></div>
      <p class="note">Race/ethnicity data available from 1995 onward. Pre-1995 data only has total men/women.</p>
    </div>
    <div class="card">
      <h2>Race/Ethnicity Share (%) Over Time</h2>
      <div class="chart-container tall"><canvas id="chartRacePct"></canvas></div>
    </div>
    <div class="card">
      <h2>Gender Trends</h2>
      <div class="chart-container medium"><canvas id="chartGender"></canvas></div>
    </div>
    <div class="card">
      <h2 id="raceDiscTitle">Race/Ethnicity by Discipline</h2>
      <div class="chart-container medium"><canvas id="chartRaceDisc"></canvas></div>
    </div>
  </div>

  <div class="panel" id="panel-institutions">
    <div class="card">
      <h2>Top 10 Institutions &mdash; PhD Trend Over Time</h2>
      <div class="chart-container tall"><canvas id="chartInstTrend"></canvas></div>
    </div>
    <div class="card">
      <h2>Top 25 PhD-Producing Institutions (All-Time)</h2>
      <div class="chart-container tall"><canvas id="chartTop25"></canvas></div>
    </div>
    <div class="card">
      <h2>Top Institutions by Discipline</h2>
      <select id="discSelect" onchange="renderDiscInst()"></select>
      <div class="chart-container medium" style="margin-top:1rem;"><canvas id="chartDiscInst"></canvas></div>
    </div>
    <div class="card">
      <h2>All Institutions</h2>
      <input type="text" class="search" id="instSearch" placeholder="Search by name or state..." oninput="filterInstitutions()">
      <div style="max-height:500px;overflow-y:auto;">
        <table>
          <thead><tr><th>#</th><th>Institution</th><th>State</th><th>Total PhDs</th><th>Years</th><th>Span</th></tr></thead>
          <tbody id="instTable"></tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="panel" id="panel-states">
    <div class="card">
      <h2>STEM PhD Completions by State</h2>
      <div class="chart-container tall"><canvas id="chartStates"></canvas></div>
    </div>
  </div>
</div>

<script>
const D = """

    html_after_data = r""";

const COLORS = {
  'Biological and Biomedical Sciences': '#4ade80',
  'Computer and Information Sciences': '#38bdf8',
  'Engineering': '#f97316',
  'Engineering Technologies': '#a3e635',
  'Health Professions / Clinical': '#f472b6',
  'Mathematics and Statistics': '#a78bfa',
  'Multi/Interdisciplinary Studies': '#facc15',
  'Physical Sciences': '#2dd4bf',
  'Psychology': '#fb923c',
};

const RACE_COLORS = {
  'White': '#e2e8f0',
  'Asian': '#38bdf8',
  'NonresAlien': '#f97316',
  'Hispanic': '#facc15',
  'Black': '#a78bfa',
  'AmerIndian': '#4ade80',
  'NHPI': '#2dd4bf',
  'TwoOrMore': '#f472b6',
  'Unknown': '#64748b',
};

Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#334155';
Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

// --- Stats bar ---
const sb = document.getElementById('statsBar');
const nt = D.national_trend;
const totalPhDs = nt.totals.reduce((a,b) => a+b, 0);
const totalInst = D.all_institutions.length;
sb.innerHTML =
  '<div class="stat"><div class="value">' + totalPhDs.toLocaleString() + '</div><div class="label">Total STEM PhDs</div></div>' +
  '<div class="stat"><div class="value">' + totalInst + '</div><div class="label">Institutions</div></div>' +
  '<div class="stat"><div class="value">' + nt.years.length + '</div><div class="label">Years</div></div>' +
  '<div class="stat"><div class="value">' + nt.years[0] + '&ndash;' + nt.years[nt.years.length-1] + '</div><div class="label">Span</div></div>' +
  '<div class="stat"><div class="value">' + Object.keys(D.trends_by_discipline).length + '</div><div class="label">Disciplines</div></div>';

// --- Tabs ---
document.querySelectorAll('.tab').forEach(function(tab) {
  tab.addEventListener('click', function() {
    document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
    document.querySelectorAll('.panel').forEach(function(p) { p.classList.remove('active'); });
    tab.classList.add('active');
    document.getElementById('panel-' + tab.dataset.panel).classList.add('active');
  });
});

// --- National trend ---
new Chart(document.getElementById('chartNational'), {
  type: 'line',
  data: {
    labels: nt.years,
    datasets: [{
      label: 'Total STEM PhD Completions',
      data: nt.totals,
      borderColor: '#38bdf8',
      backgroundColor: 'rgba(56,189,248,0.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 3,
    }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: true, title: { display: true, text: 'Completions' } },
      x: { title: { display: true, text: 'Year' } }
    }
  }
});

// --- Trends by discipline ---
var discDatasets = Object.entries(D.trends_by_discipline).map(function(entry) {
  var disc = entry[0], d = entry[1];
  return {
    label: disc,
    data: d.years.map(function(y, i) { return { x: y, y: d.totals[i] }; }),
    borderColor: COLORS[disc] || '#888',
    backgroundColor: COLORS[disc] || '#888',
    tension: 0.3,
    pointRadius: 2,
    borderWidth: 2,
  };
});

new Chart(document.getElementById('chartByDisc'), {
  type: 'line',
  data: { datasets: discDatasets },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } } },
    scales: {
      y: { beginAtZero: true, title: { display: true, text: 'Completions' } },
      x: { type: 'linear', title: { display: true, text: 'Year' }, ticks: { stepSize: 5 } }
    }
  }
});

// --- Discipline share (stacked area) ---
var allYears = nt.years;
var discShareDatasets = Object.entries(D.trends_by_discipline).map(function(entry) {
  var disc = entry[0], d = entry[1];
  var yearMap = {};
  d.years.forEach(function(y, i) { yearMap[y] = d.totals[i]; });
  return {
    label: disc,
    data: allYears.map(function(y) { return yearMap[y] || 0; }),
    backgroundColor: (COLORS[disc] || '#888') + '99',
    borderColor: COLORS[disc] || '#888',
    borderWidth: 1,
    fill: true,
    pointRadius: 0,
  };
});

new Chart(document.getElementById('chartDiscShare'), {
  type: 'line',
  data: { labels: allYears, datasets: discShareDatasets },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } } },
    scales: {
      y: { stacked: true, title: { display: true, text: 'Completions' } },
      x: { stacked: true }
    }
  }
});

// --- Race/ethnicity trends ---
if (D.race_trends) {
  var raceGroups = ['White','Asian','NonresAlien','Hispanic','Black','AmerIndian','NHPI','TwoOrMore','Unknown'];
  var raceDatasets = raceGroups.filter(function(g) { return D.race_trends[g]; }).map(function(g) {
    return {
      label: D.race_trends[g].label,
      data: D.race_trends[g].values,
      borderColor: RACE_COLORS[g],
      backgroundColor: RACE_COLORS[g] + '20',
      fill: true,
      tension: 0.3,
      pointRadius: 2,
      borderWidth: 2,
    };
  });

  new Chart(document.getElementById('chartRace'), {
    type: 'line',
    data: { labels: D.race_trends.years, datasets: raceDatasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } } },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: 'Completions' } },
        x: { title: { display: true, text: 'Year' } }
      }
    }
  });

  // Race % stacked
  var racePctDatasets = raceGroups.filter(function(g) { return D.race_trends[g]; }).map(function(g) {
    var vals = D.race_trends[g].values;
    var totals = D.race_trends.years.map(function(_, i) {
      return raceGroups.filter(function(gg) { return D.race_trends[gg]; }).reduce(function(s, gg) { return s + D.race_trends[gg].values[i]; }, 0);
    });
    return {
      label: D.race_trends[g].label,
      data: vals.map(function(v, i) { return totals[i] > 0 ? (v / totals[i] * 100) : 0; }),
      backgroundColor: RACE_COLORS[g] + '99',
      borderColor: RACE_COLORS[g],
      borderWidth: 1,
      fill: true,
      pointRadius: 0,
    };
  });

  new Chart(document.getElementById('chartRacePct'), {
    type: 'line',
    data: { labels: D.race_trends.years, datasets: racePctDatasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } } },
      scales: {
        y: { stacked: true, max: 100, title: { display: true, text: '% of Completions' } },
        x: { stacked: true }
      }
    }
  });
}

// --- Gender trends ---
if (D.gender_trends) {
  new Chart(document.getElementById('chartGender'), {
    type: 'line',
    data: {
      labels: D.gender_trends.years,
      datasets: [
        { label: 'Men', data: D.gender_trends.men, borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.1)', fill: true, tension: 0.3 },
        { label: 'Women', data: D.gender_trends.women, borderColor: '#f472b6', backgroundColor: 'rgba(244,114,182,0.1)', fill: true, tension: 0.3 },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: { y: { beginAtZero: true } }
    }
  });
}

// --- Race by discipline ---
if (D.race_by_discipline) {
  document.getElementById('raceDiscTitle').textContent = 'Race/Ethnicity by Discipline (' + D.race_by_discipline.year + ')';
  var raceGroups2 = ['White','Asian','NonresAlien','Hispanic','Black','TwoOrMore','Unknown'];
  new Chart(document.getElementById('chartRaceDisc'), {
    type: 'bar',
    data: {
      labels: D.race_by_discipline.disciplines,
      datasets: raceGroups2.filter(function(g) { return D.race_by_discipline[g]; }).map(function(g) {
        return {
          label: (D.race_trends && D.race_trends[g]) ? D.race_trends[g].label : g,
          data: D.race_by_discipline[g],
          backgroundColor: RACE_COLORS[g] + 'cc',
        };
      })
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 } } } },
      scales: { x: { stacked: true }, y: { stacked: true } }
    }
  });
}

// --- Institution trend (top 10) ---
var instColors = ['#38bdf8','#4ade80','#f97316','#a78bfa','#f472b6','#facc15','#2dd4bf','#818cf8','#fb923c','#e2e8f0'];
var instTrendDatasets = Object.values(D.institution_trends).map(function(inst, i) {
  return {
    label: inst.name,
    data: inst.years.map(function(y, j) { return { x: y, y: inst.totals[j] }; }),
    borderColor: instColors[i % instColors.length],
    tension: 0.3,
    pointRadius: 2,
    borderWidth: 2,
  };
});

new Chart(document.getElementById('chartInstTrend'), {
  type: 'line',
  data: { datasets: instTrendDatasets },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 } } } },
    scales: {
      y: { beginAtZero: true },
      x: { type: 'linear', ticks: { stepSize: 5 } }
    }
  }
});

// --- Top 25 bar ---
new Chart(document.getElementById('chartTop25'), {
  type: 'bar',
  data: {
    labels: D.top_institutions.map(function(i) { return i.name; }),
    datasets: [{ data: D.top_institutions.map(function(i) { return i.total; }), backgroundColor: '#38bdf8cc' }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: { legend: { display: false } },
    scales: { x: { title: { display: true, text: 'Total PhD Completions' } } }
  }
});

// --- Top by discipline ---
var discSel = document.getElementById('discSelect');
Object.keys(D.top_by_discipline).forEach(function(d) {
  var opt = document.createElement('option');
  opt.value = d; opt.textContent = d;
  discSel.appendChild(opt);
});
var discInstChart = null;
function renderDiscInst() {
  var disc = discSel.value;
  var entries = D.top_by_discipline[disc];
  if (discInstChart) discInstChart.destroy();
  discInstChart = new Chart(document.getElementById('chartDiscInst'), {
    type: 'bar',
    data: {
      labels: entries.map(function(e) { return e.name; }),
      datasets: [{ data: entries.map(function(e) { return e.total; }), backgroundColor: (COLORS[disc] || '#38bdf8') + 'cc' }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: { legend: { display: false } },
    }
  });
}
renderDiscInst();

// --- All institutions table ---
function filterInstitutions() {
  var q = document.getElementById('instSearch').value.toLowerCase();
  var filtered = D.all_institutions.filter(function(i) { return i.name.toLowerCase().includes(q) || i.state.toLowerCase().includes(q); });
  var tbody = document.getElementById('instTable');
  tbody.innerHTML = filtered.slice(0, 100).map(function(inst, i) {
    return '<tr><td class="rank">' + (i+1) + '</td><td>' + inst.name + '</td><td>' + inst.state + '</td><td>' + inst.total.toLocaleString() + '</td><td>' + inst.years + '</td><td>' + inst.first + '&ndash;' + inst.last + '</td></tr>';
  }).join('');
}
filterInstitutions();

// --- States bar ---
new Chart(document.getElementById('chartStates'), {
  type: 'bar',
  data: {
    labels: D.state_totals.states.slice(0, 30),
    datasets: [{ data: D.state_totals.totals.slice(0, 30), backgroundColor: '#38bdf8cc' }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { y: { title: { display: true, text: 'Total PhD Completions' } } }
  }
});
</script>
</body>
</html>"""

    html = html_before_data + json_data + html_after_data

    with open(output_path, "w") as f:
        f.write(html)
    log.info("Dashboard written to %s", output_path)


def main():
    parser = argparse.ArgumentParser(description="Build IPEDS STEM PhD dashboard")
    parser.add_argument("--output", default="ipeds_dashboard.html", help="Output HTML file")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    log.info("Building enriched dataset with demographics...")
    enriched = build_enriched_data()

    log.info("\nAggregating for dashboard...")
    dashboard_data = aggregate_for_dashboard(enriched)

    base_dir = os.path.dirname(os.path.dirname(__file__))
    output_path = os.path.join(base_dir, args.output)
    generate_html(dashboard_data, output_path)

    # Also write to site/ for unified serving
    site_path = os.path.join(base_dir, "site", "ipeds_dashboard.html")
    os.makedirs(os.path.dirname(site_path), exist_ok=True)
    generate_html(dashboard_data, site_path)
    log.info("\nDone! Written to %s and %s", output_path, site_path)


if __name__ == "__main__":
    main()
