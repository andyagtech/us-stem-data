#!/usr/bin/env python3
"""
Filter NSF GSS data to extract STEM doctoral programs.

Reads the GSS public-use file (SAS7BDAT, Excel, or CSV) downloaded by
download_nsf_gss.py, filters for doctoral institutions and target STEM
fields using the official GSS code taxonomy, and exports a clean CSV.

Usage:
    python scripts/nsf_gss_filter.py [--year 2023]
"""

import argparse
import glob
import os
import sys

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "nsf_gss")

# ---------------------------------------------------------------------------
# GSS Code Taxonomy (from the GSS Public-Use File User Guide)
# Maps gss_code → (Field Name, Broad Field, Standardized Discipline, Category)
# ---------------------------------------------------------------------------

GSS_TAXONOMY = {
    # Engineering
    "101": ("Aerospace, Aeronautical, and Astronautical Engineering", "Engineering", "Engineering", "Core STEM"),
    "102": ("Agricultural Engineering", "Engineering", "Engineering", "Core STEM"),
    "104": ("Chemical Engineering", "Engineering", "Engineering", "Core STEM"),
    "105": ("Civil Engineering", "Engineering", "Engineering", "Core STEM"),
    "106": ("Electrical, Electronics, and Communications Engineering", "Engineering", "Engineering", "Core STEM"),
    "107": ("Engineering Mechanics, Physics, and Science", "Engineering", "Engineering", "Core STEM"),
    "108": ("Industrial and Manufacturing Engineering", "Engineering", "Engineering", "Core STEM"),
    "109": ("Mechanical Engineering", "Engineering", "Engineering", "Core STEM"),
    "112": ("Nuclear Engineering", "Engineering", "Engineering", "Core STEM"),
    "113": ("Petroleum Engineering", "Engineering", "Engineering", "Core STEM"),
    "117": ("Architectural, Environmental, Construction, and Surveying Engineering", "Engineering", "Engineering", "Core STEM"),
    "118": ("Computer Engineering", "Engineering", "Engineering", "Core STEM"),
    "119": ("Systems Engineering and Operations Research", "Engineering", "Engineering", "Core STEM"),
    "120": ("Biological, Biomedical, and Biosystems Engineering", "Engineering", "Engineering", "Core STEM"),
    "121": ("Metallurgical, Mining, Materials, and Related Engineering", "Engineering", "Engineering", "Core STEM"),
    "122": ("Engineering, other", "Engineering", "Engineering", "Core STEM"),
    # Physical Sciences
    "201": ("Astronomy and Astrophysics", "Physical Sciences", "Physical Sciences", "Core STEM"),
    "202": ("Chemistry", "Physical Sciences", "Physical Sciences", "Core STEM"),
    "203": ("Physics", "Physical Sciences", "Physical Sciences", "Core STEM"),
    "204": ("Physical Sciences, nec", "Physical Sciences", "Physical Sciences", "Core STEM"),
    "205": ("Materials Sciences", "Physical Sciences", "Physical Sciences", "Core STEM"),
    # Geosciences, Atmospheric, Ocean
    "301": ("Atmospheric Sciences and Meteorology", "Geosciences", "Physical Sciences", "Core STEM"),
    "302": ("Geological and Earth Sciences", "Geosciences", "Physical Sciences", "Core STEM"),
    "303": ("Ocean and Marine Sciences", "Geosciences", "Physical Sciences", "Core STEM"),
    "304": ("Geoscience, nec", "Geosciences", "Physical Sciences", "Core STEM"),
    # Mathematics and Statistics
    "403": ("Statistics", "Mathematics and Statistics", "Mathematics and Statistics", "Core STEM"),
    "404": ("Applied Mathematics", "Mathematics and Statistics", "Mathematics and Statistics", "Core STEM"),
    "405": ("Mathematics", "Mathematics and Statistics", "Mathematics and Statistics", "Core STEM"),
    # Computer and Information Sciences
    "410": ("Computer Science", "Computer and Information Sciences", "Computer and Information Sciences", "Core STEM"),
    "411": ("Computer and Information Sciences, general", "Computer and Information Sciences", "Computer and Information Sciences", "Core STEM"),
    "412": ("Computer and Information Sciences, nec", "Computer and Information Sciences", "Computer and Information Sciences", "Core STEM"),
    "413": ("Computer and Information Systems Security", "Computer and Information Sciences", "Computer and Information Sciences", "Core STEM"),
    "414": ("Information Technology", "Computer and Information Sciences", "Computer and Information Sciences", "Core STEM"),
    "415": ("Information Science and Studies", "Computer and Information Sciences", "Computer and Information Sciences", "Core STEM"),
    "416": ("Artificial Intelligence, Informatics, and CIS Topics", "Computer and Information Sciences", "Computer and Information Sciences", "Core STEM"),
    # Agricultural and Veterinary Sciences
    "501": ("Agricultural Sciences", "Agricultural Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "502": ("Veterinary Biomedical and Clinical Sciences", "Agricultural Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    # Natural Resources and Conservation
    "510": ("Environmental Science and Studies", "Natural Resources", "Multi/Interdisciplinary Studies", "Core STEM"),
    "511": ("Forestry, Natural Resources, and Conservation", "Natural Resources", "Multi/Interdisciplinary Studies", "Core STEM"),
    # Biological and Biomedical Sciences
    "602": ("Biochemistry", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "603": ("Biology", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "605": ("Biophysics", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "606": ("Botany and Plant Biology", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "610": ("Genetics", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "611": ("Microbiological Sciences and Immunology", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "612": ("Nutrition Science", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "613": ("Pathology and Experimental Pathology", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "614": ("Pharmacology and Toxicology", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "615": ("Physiology", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "616": ("Zoology and Animal Biology", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "617": ("Biological and Biomedical Sciences, nec", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "618": ("Biostatistics and Bioinformatics", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "619": ("Cell, Cellular Biology, and Anatomical Sciences", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "620": ("Ecology and Population Biology", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "621": ("Epidemiology", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "622": ("Molecular Biology", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "623": ("Biomedical Sciences", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "624": ("Biotechnology", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    "626": ("Neurobiology and Neuroscience", "Biological and Biomedical Sciences", "Biological and Biomedical Sciences", "Core STEM"),
    # Health – Clinical Medicine
    "701": ("Anesthesiology", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "702": ("Cardiology and Cardiovascular Disease", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "703": ("Oncology and Cancer Research", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "704": ("Endocrinology, Diabetes, and Metabolism", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "705": ("Gastroenterology", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "706": ("Hematology", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "707": ("Neurology and Neurosurgery", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "708": ("Obstetrics and Gynecology", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "709": ("Ophthalmology", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "710": ("Otorhinolaryngology", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "711": ("Pediatrics", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "712": ("Public Health", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "713": ("Psychiatry", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "714": ("Pulmonary Disease", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "715": ("Radiological Sciences", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "716": ("Surgery", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "717": ("Clinical Medicine, nec", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    "729": ("Medical Clinical Sciences and Lab Sciences", "Health - Clinical Medicine", "Health Professions / Clinical", "Clinical/Medical"),
    # Health – Other Health
    "718": ("Dental Sciences", "Health - Other", "Health Professions / Clinical", "Clinical/Medical"),
    "719": ("Nursing", "Health - Other", "Health Professions / Clinical", "Clinical/Medical"),
    "720": ("Pharmaceutical Sciences", "Health - Other", "Health Professions / Clinical", "Clinical/Medical"),
    "722": ("Health-Related, nec", "Health - Other", "Health Professions / Clinical", "Clinical/Medical"),
    "723": ("Communication Disorders Sciences", "Health - Other", "Health Professions / Clinical", "Clinical/Medical"),
    "724": ("Kinesiology and Exercise Science", "Health - Other", "Health Professions / Clinical", "Clinical/Medical"),
    # Psychology
    "801": ("Psychology, General", "Psychology", "Psychology", "Core STEM"),
    "803": ("Clinical Psychology", "Psychology", "Psychology", "Core STEM"),
    "804": ("Applied Psychology", "Psychology", "Psychology", "Core STEM"),
    "805": ("Research and Experimental Psychology", "Psychology", "Psychology", "Core STEM"),
    "806": ("Counseling Psychology", "Psychology", "Psychology", "Core STEM"),
    "815": ("Human Development", "Psychology", "Psychology", "Core STEM"),
    # Social Sciences (excluded from our target but kept for reference)
    # "901"-"919" → Social Sciences → not included
    # Multidisciplinary and Interdisciplinary Studies
    "980": ("Multidisciplinary and Interdisciplinary Studies", "Interdisciplinary", "Multi/Interdisciplinary Studies", "Core STEM"),
    "981": ("Computational Science", "Interdisciplinary", "Multi/Interdisciplinary Studies", "Core STEM"),
    "982": ("Biological and Physical Sciences", "Interdisciplinary", "Multi/Interdisciplinary Studies", "Core STEM"),
    "983": ("International and Global Studies", "Interdisciplinary", "Multi/Interdisciplinary Studies", "Core STEM"),
    "984": ("Data Science and Data Analytics", "Interdisciplinary", "Multi/Interdisciplinary Studies", "Core STEM"),
}

# Codes that are Social Sciences (not in our target set, but tracked for completeness)
SOCIAL_SCIENCE_CODES = {
    "901", "902", "903", "904", "906", "907", "908", "911", "912", "914", "916", "917", "918", "919",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def find_data_file() -> str | None:
    """Find the main GSS data file (SAS, Excel, or CSV)."""
    # Prefer SAS file (the main PUF data)
    for pattern in ["gss*_code.sas7bdat", "gss*_Code.sas7bdat", "gss*.sas7bdat"]:
        matches = glob.glob(os.path.join(DATA_DIR, pattern))
        matches = [m for m in matches if "institution" not in m.lower()]
        if matches:
            return matches[0]

    # Try Excel
    for pattern in ["gss*_Code.xlsx", "gss*_code.xlsx", "gss*.xlsx"]:
        matches = glob.glob(os.path.join(DATA_DIR, pattern))
        matches = [m for m in matches if "institution" not in m.lower() and "dict" not in m.lower()]
        if matches:
            return matches[0]

    # Try CSV
    for pattern in ["gss*.csv", "GSS*.csv"]:
        matches = glob.glob(os.path.join(DATA_DIR, pattern))
        matches = [m for m in matches if "stem_phd" not in m.lower()]
        if matches:
            return matches[0]

    return None


def load_data(path: str) -> pd.DataFrame:
    """Load GSS data from SAS, Excel, or CSV format."""
    ext = os.path.splitext(path)[1].lower()
    print(f"Loading: {path} (format: {ext})")

    if ext == ".sas7bdat":
        df = pd.read_sas(path, encoding="latin-1")
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    elif ext == ".csv":
        df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    else:
        print(f"ERROR: Unsupported file format: {ext}")
        sys.exit(1)

    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    return df


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_and_classify(df: pd.DataFrame) -> pd.DataFrame:
    """Filter for doctoral programs in target STEM/Clinical fields."""

    # --- Filter for doctoral-level programs ---
    # hdg_code: 1 = Doctorate-granting, 2 = Master's, 3 = No PhD/Master's
    if "hdg_code" in df.columns:
        print(f"\nFiltering for doctoral programs (hdg_code == '1')...")
        df["hdg_code"] = df["hdg_code"].astype(str).str.strip()
        doctoral = df[df["hdg_code"] == "1"].copy()
        print(f"  {len(doctoral):,} doctoral-level rows (from {len(df):,} total)")
    elif "hdg_inst" in df.columns:
        print(f"\nFiltering for doctoral institutions (hdg_inst == 1)...")
        doctoral = df[df["hdg_inst"] == 1.0].copy()
        print(f"  {len(doctoral):,} rows from doctoral institutions")
    else:
        print("\nWARNING: No hdg_code or hdg_inst column found; including all rows.")
        doctoral = df.copy()

    # --- Map gss_code to taxonomy ---
    if "gss_code" not in doctoral.columns:
        print("ERROR: No gss_code column found in data.")
        sys.exit(1)

    doctoral["gss_code"] = doctoral["gss_code"].astype(str).str.strip()

    # Look up each code in our taxonomy
    doctoral["GSS_Field"] = doctoral["gss_code"].map(
        lambda c: GSS_TAXONOMY.get(c, (None,))[0]
    )
    doctoral["Broad_Field"] = doctoral["gss_code"].map(
        lambda c: GSS_TAXONOMY.get(c, (None, None))[1]
    )
    doctoral["STEM_Discipline"] = doctoral["gss_code"].map(
        lambda c: GSS_TAXONOMY.get(c, (None, None, None))[2]
    )
    doctoral["Category"] = doctoral["gss_code"].map(
        lambda c: GSS_TAXONOMY.get(c, (None, None, None, None))[3]
    )

    # Report unmatched codes
    unmatched = doctoral[doctoral["Category"].isna()]["gss_code"].unique()
    social = [c for c in unmatched if c in SOCIAL_SCIENCE_CODES]
    other = [c for c in unmatched if c not in SOCIAL_SCIENCE_CODES]
    print(f"\n  Matched: {doctoral['Category'].notna().sum():,} rows")
    print(f"  Unmatched Social Sciences codes (excluded): {len(social)}")
    if other:
        print(f"  Unmatched other codes: {sorted(other)}")

    # Keep only rows with a matched category
    result = doctoral[doctoral["Category"].notna()].copy()
    print(f"  {len(result):,} rows after filtering to target fields")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Filter NSF GSS data for STEM doctoral programs.")
    parser.add_argument("--year", type=int, default=2023, help="GSS survey year (default: 2023)")
    args = parser.parse_args()
    year = args.year

    if not os.path.isdir(DATA_DIR):
        print(f"ERROR: Data directory not found: {DATA_DIR}")
        print("Run download_nsf_gss.py first.")
        sys.exit(1)

    data_file = find_data_file()
    if not data_file:
        print(f"ERROR: No GSS data file found in {DATA_DIR}")
        print("Run download_nsf_gss.py first, or place files manually.")
        sys.exit(1)

    print(f"=== NSF GSS Filter: Year {year} ===\n")

    df = load_data(data_file)
    filtered = filter_and_classify(df)

    # Build output DataFrame
    out_cols = {
        "Institution_Name": "Institution_Name",
        "State": "institution_state",
        "UNITID": "UNITID",
        "GSS_Code": "gss_code",
        "GSS_Field": "GSS_Field",
        "Broad_Field": "Broad_Field",
        "STEM_Discipline": "STEM_Discipline",
        "Category": "Category",
    }

    result_data = {}
    for out_name, src_col in out_cols.items():
        if src_col in filtered.columns:
            result_data[out_name] = filtered[src_col].values
    result = pd.DataFrame(result_data)

    # Deduplicate: one row per (Institution, STEM_Discipline)
    dedup_cols = ["Institution_Name", "STEM_Discipline"]
    dedup_cols = [c for c in dedup_cols if c in result.columns]
    if dedup_cols:
        before = len(result)
        result = result.drop_duplicates(subset=dedup_cols)
        print(f"\n  Deduplicated: {before:,} → {len(result):,} unique (institution, discipline) pairs")

    result = result.sort_values(
        [c for c in ["State", "Institution_Name", "STEM_Discipline"] if c in result.columns]
    ).reset_index(drop=True)

    # Export
    output_path = os.path.join(DATA_DIR, "nsf_gss_stem_phd_programs.csv")
    result.to_csv(output_path, index=False)
    print(f"\nExported {len(result):,} rows to {os.path.abspath(output_path)}")

    # Summary
    print(f"\n=== Summary ===")
    if "Institution_Name" in result.columns:
        print(f"Unique institutions: {result['Institution_Name'].nunique()}")
    if "State" in result.columns:
        print(f"States covered: {result['State'].nunique()}")
    print(f"Total (institution, discipline) pairs: {len(result)}")
    print(f"\nBy Category:")
    print(result["Category"].value_counts().to_string())
    print(f"\nBy Discipline:")
    print(result["STEM_Discipline"].value_counts().to_string())
    if "State" in result.columns:
        print(f"\nBy State (top 10):")
        print(result.groupby("State").size().sort_values(ascending=False).head(10).to_string())


if __name__ == "__main__":
    main()
