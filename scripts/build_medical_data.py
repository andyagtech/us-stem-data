#!/usr/bin/env python3
"""
Extract AAMC medical-school enrollment + DACA + race data into a single
JSON for the medical immigration dashboard page.

Output: data/medical/medical_dashboard.json
"""
import json
import openpyxl
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MED = ROOT / "data" / "medical"
OUT = MED / "medical_dashboard.json"


def load_enrollment_history():
    """Chart 4: applicants/matriculants/enrollment 1980-2025."""
    wb = openpyxl.load_workbook(MED / "aamc_chart4_enrollment_history.xlsx", data_only=True)
    ws = wb["Data"]
    rows = list(ws.iter_rows(values_only=True))
    years, applicants, matriculants, enrollment = [], [], [], []
    for r in rows:
        if not r or not r[0] or not isinstance(r[0], str) or "-" not in r[0]:
            continue
        try:
            yr = int(r[0].split("-")[0])
            years.append(yr)
            applicants.append(int(r[1]) if r[1] else None)
            matriculants.append(int(r[2]) if r[2] else None)
            enrollment.append(int(r[3]) if r[3] else None)
        except (ValueError, TypeError):
            continue
    return {"years": years, "applicants": applicants, "matriculants": matriculants, "enrollment": enrollment}


def load_summary_table():
    """Table 1: 10-year summary 2016-2025."""
    wb = openpyxl.load_workbook(MED / "aamc_table1_summary_2016-2026.xlsx", data_only=True)
    ws = wb["FACTS Table 1"]
    rows = list(ws.iter_rows(values_only=True))
    out = {"years": [], "applicants": [], "matriculants": [], "enrollment": [], "graduates": []}
    for r in rows:
        if not r or not r[0]:
            continue
        label = str(r[0]).strip()
        # Header row contains year strings like "2016-2017"
        if "Applicants, Matriculants" in label:
            out["years"] = [str(c).strip() for c in r[3:] if c and isinstance(c, str)]
            continue
        if label == "Applicants":
            out["applicants"] = [int(c) for c in r[3:] if isinstance(c, (int, float))]
        elif label == "Matriculants":
            out["matriculants"] = [int(c) for c in r[3:] if isinstance(c, (int, float))]
        elif label == "Enrollment":
            out["enrollment"] = [int(c) for c in r[3:] if isinstance(c, (int, float))]
        elif label == "Graduates":
            out["graduates"] = [int(c) if isinstance(c, (int, float)) else None for c in r[3:]]
    return out


def load_daca():
    """Table A-25: DACA status 2018-2025."""
    wb = openpyxl.load_workbook(MED / "aamc_A25_daca_status_2018-2026.xlsx", data_only=True)
    ws = wb["FACTS Table A-25"]
    rows = list(ws.iter_rows(values_only=True))
    out = {"years": [], "applicants_daca": [], "applicants_total": [], "matriculants_daca": [], "matriculants_total": []}
    current_section = None
    for r in rows:
        if not r:
            continue
        if r[0] == "Applicants":
            current_section = "applicants"
        elif r[0] == "Acceptees":
            current_section = "acceptees"
        elif r[0] == "Matriculants":
            current_section = "matriculants"

        # Year rows have the year in column 1
        if r[1] and isinstance(r[1], str) and "-" in str(r[1]):
            year_str = str(r[1]).split("-")[0]
            try:
                year = int(year_str)
            except ValueError:
                continue
            if current_section == "applicants":
                if year not in out["years"]:
                    out["years"].append(year)
                out["applicants_daca"].append(int(r[2]) if r[2] is not None else None)
                out["applicants_total"].append(int(r[4]) if r[4] is not None else None)
            elif current_section == "matriculants":
                out["matriculants_daca"].append(int(r[2]) if r[2] is not None else None)
                out["matriculants_total"].append(int(r[4]) if r[4] is not None else None)
    return out


def load_race_2025():
    """Table A-12: race/ethnicity breakdown for 2025-2026 (totals only, not by gender)."""
    wb = openpyxl.load_workbook(MED / "aamc_A12_applicants_by_race_ethnicity.xlsx", data_only=True)
    ws = wb["FACTS Table A-12"]
    rows = list(ws.iter_rows(values_only=True))
    # Aggregate by top-level race category, summing across gender
    # Strategy: scan for rows where col 0 is "Men"/"Women"/"Total" and col 1 is the category name
    # Their Asian sub-rows (col 2 has detail) we want for the immigration story
    asian_origins = {}
    in_men_asian = False
    for r in rows:
        if not r:
            continue
        if r[0] == "Men":
            current_gender = "men"
            current_category = (r[1] or "").strip() if r[1] else None
            if current_category == "Asian":
                in_men_asian = True
            else:
                in_men_asian = False
        elif r[0] == "Women" or r[0] == "Total":
            in_men_asian = False
        elif r[0] is None and r[1] is not None and not r[2]:
            # New top-level category for current gender
            current_category = (r[1] or "").strip()
            if current_category == "Asian":
                in_men_asian = True
            else:
                in_men_asian = False
        elif in_men_asian and r[2]:
            origin = str(r[2]).strip()
            matriculants = r[6]
            if isinstance(matriculants, (int, float)) and origin and "More Than One" not in origin and "Some Other" not in origin:
                asian_origins[origin] = asian_origins.get(origin, 0) + int(matriculants)
    return {"asian_origins_men_matriculants_2025": asian_origins}


def main():
    out = {
        "source": "AAMC FACTS — applicants, matriculants, enrollment, graduates of US MD-granting medical schools",
        "url": "https://www.aamc.org/data-reports/students-residents/data/facts-applicants-and-matriculants-data",
        "history": load_enrollment_history(),
        "ten_year_summary": load_summary_table(),
        "daca": load_daca(),
        "race_2025": load_race_2025(),
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"Wrote {OUT}")
    print(f"  history years: {len(out['history']['years'])}")
    print(f"  DACA years: {len(out['daca']['years'])}")
    print(f"  Asian origins: {len(out['race_2025']['asian_origins_men_matriculants_2025'])}")


if __name__ == "__main__":
    main()
