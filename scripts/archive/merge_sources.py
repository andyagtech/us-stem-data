#!/usr/bin/env python3
"""
Merge IPEDS and NSF GSS filtered outputs into a unified master list.

Performs fuzzy institution name matching between the two sources,
cross-references against the Gemini-exported R1 university list,
and produces a single master CSV.

Usage:
    python scripts/merge_sources.py
"""

import os
import sys

import pandas as pd
from rapidfuzz import fuzz, process

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
IPEDS_PATH = os.path.join(PROJECT_ROOT, "data", "ipeds", "ipeds_stem_phd_programs.csv")
GSS_PATH = os.path.join(PROJECT_ROOT, "data", "nsf_gss", "nsf_gss_stem_phd_programs.csv")
GEMINI_PATH = os.path.join(PROJECT_ROOT, "data", "gemini_exported_sheet.csv")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "master_stem_phd_institutions.csv")

# Minimum fuzzy match score to consider two institution names the same
FUZZY_THRESHOLD = 85


def load_if_exists(path: str, label: str) -> pd.DataFrame | None:
    """Load a CSV if it exists, otherwise warn and return None."""
    if not os.path.exists(path):
        print(f"WARNING: {label} not found at {path}")
        return None
    df = pd.read_csv(path)
    print(f"Loaded {label}: {len(df):,} rows from {path}")
    return df


def normalize_name(name: str) -> str:
    """Normalize institution name for matching."""
    if not isinstance(name, str):
        return ""
    # Common abbreviations and variants
    replacements = {
        "university": "univ",
        "institute of technology": "inst tech",
        "the ": "",
        " - ": "-",
        "–": "-",
        "saint ": "st ",
        "saint. ": "st ",
        "&": "and",
    }
    name = name.strip().lower()
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name


def fuzzy_match_institutions(
    gss_names: list[str], ipeds_names: list[str]
) -> dict[str, str | None]:
    """
    For each GSS institution name, find the best IPEDS match.
    Returns dict mapping GSS name → IPEDS name (or None if no good match).
    """
    ipeds_normalized = {normalize_name(n): n for n in ipeds_names}
    ipeds_norm_list = list(ipeds_normalized.keys())

    matches = {}
    for gss_name in gss_names:
        gss_norm = normalize_name(gss_name)
        result = process.extractOne(
            gss_norm, ipeds_norm_list, scorer=fuzz.token_sort_ratio
        )
        if result and result[1] >= FUZZY_THRESHOLD:
            matches[gss_name] = ipeds_normalized[result[0]]
        else:
            matches[gss_name] = None

    return matches


def merge_datasets(ipeds: pd.DataFrame | None, gss: pd.DataFrame | None) -> pd.DataFrame:
    """Merge IPEDS and GSS data into a unified master list."""

    if ipeds is not None and gss is not None:
        return _merge_both(ipeds, gss)
    elif ipeds is not None:
        return _format_ipeds_only(ipeds)
    elif gss is not None:
        return _format_gss_only(gss)
    else:
        print("ERROR: No data to merge.")
        sys.exit(1)


def _format_ipeds_only(ipeds: pd.DataFrame) -> pd.DataFrame:
    """Format IPEDS-only output as master list."""
    ipeds["Source"] = "IPEDS"
    ipeds["GSS_Field_Code"] = ""
    col_order = [
        "State", "University", "STEM_Discipline", "Category",
        "Source", "UNITID", "CIP_2Digit", "CIP_Codes_Detail",
        "GSS_Field_Code", "Institution_URL",
    ]
    col_order = [c for c in col_order if c in ipeds.columns]
    return ipeds[col_order].copy()


def _format_gss_only(gss: pd.DataFrame) -> pd.DataFrame:
    """Format GSS-only output as master list."""
    result = gss.rename(columns={"Institution_Name": "University"}).copy()
    result["Source"] = "GSS"
    result["UNITID"] = ""
    result["CIP_2Digit"] = ""
    result["CIP_Codes_Detail"] = ""
    result["Institution_URL"] = ""
    col_order = [
        "State", "University", "STEM_Discipline", "Category",
        "Source", "UNITID", "CIP_2Digit", "CIP_Codes_Detail",
        "GSS_Field_Code", "Institution_URL",
    ]
    col_order = [c for c in col_order if c in result.columns]
    return result[col_order].copy()


def _build_institution_map(
    ipeds: pd.DataFrame, gss: pd.DataFrame
) -> dict[str, tuple[str, str]]:
    """
    Map each GSS institution to its IPEDS counterpart.
    Returns dict: GSS Institution_Name → (IPEDS University name, IPEDS State).

    Strategy:
      1. Match on UNITID (exact, reliable).
      2. For remaining unmatched, fall back to fuzzy name matching.
    """
    # --- Phase 1: UNITID matching ---
    # Build IPEDS lookup: UNITID → (University name, State)
    ipeds_by_unitid = {}
    if "UNITID" in ipeds.columns:
        for _, row in ipeds.drop_duplicates("UNITID").iterrows():
            uid = str(int(row["UNITID"])) if pd.notna(row["UNITID"]) else ""
            if uid:
                ipeds_by_unitid[uid] = (row["University"], row.get("State", ""))

    inst_map: dict[str, tuple[str, str]] = {}  # GSS name → (IPEDS name, state)
    unmatched_gss_names = []

    # Deduplicate GSS institutions
    gss_institutions = (
        gss[["Institution_Name", "State", "UNITID"]]
        .drop_duplicates("Institution_Name")
        .dropna(subset=["Institution_Name"])
    )

    for _, row in gss_institutions.iterrows():
        gss_name = row["Institution_Name"]
        gss_unitid = str(int(row["UNITID"])) if pd.notna(row["UNITID"]) else ""

        if gss_unitid and gss_unitid in ipeds_by_unitid:
            ipeds_name, ipeds_state = ipeds_by_unitid[gss_unitid]
            inst_map[gss_name] = (ipeds_name, ipeds_state)
        else:
            unmatched_gss_names.append(gss_name)

    unitid_matched = len(inst_map)
    print(f"  UNITID matches: {unitid_matched}")

    # --- Phase 2: Fuzzy name matching for the rest ---
    if unmatched_gss_names:
        ipeds_names = ipeds["University"].dropna().unique().tolist()
        name_map = fuzzy_match_institutions(unmatched_gss_names, ipeds_names)

        # For fuzzy-matched institutions, look up the IPEDS state
        ipeds_state_lookup = dict(
            ipeds.drop_duplicates("University")[["University", "State"]].values
        )

        fuzzy_matched = 0
        for gss_name, ipeds_name in name_map.items():
            if ipeds_name:
                inst_map[gss_name] = (ipeds_name, ipeds_state_lookup.get(ipeds_name, ""))
                fuzzy_matched += 1

        still_unmatched = len(unmatched_gss_names) - fuzzy_matched
        print(f"  Fuzzy name matches: {fuzzy_matched}")
        print(f"  Unmatched (GSS-only): {still_unmatched}")

        if still_unmatched > 0 and still_unmatched <= 30:
            print(f"  Unmatched GSS institutions:")
            for name in sorted(unmatched_gss_names):
                if name not in inst_map:
                    print(f"    - {name}")

    return inst_map


def _merge_both(ipeds: pd.DataFrame, gss: pd.DataFrame) -> pd.DataFrame:
    """Merge IPEDS and GSS using UNITID matching first, then fuzzy name fallback."""
    if "Institution_Name" not in gss.columns:
        print("WARNING: GSS has no Institution_Name column; treating as IPEDS-only.")
        return _format_ipeds_only(ipeds)

    gss_count = gss["Institution_Name"].nunique()
    ipeds_count = ipeds["University"].nunique()
    print(f"\nMatching {gss_count} GSS institutions against {ipeds_count} IPEDS institutions...")

    inst_map = _build_institution_map(ipeds, gss)

    # Start with IPEDS as the base (it has richer data)
    ipeds_out = _format_ipeds_only(ipeds)

    # Build a lookup for IPEDS state/URL by institution name for new rows
    ipeds_info = {}
    for _, row in ipeds.drop_duplicates("University").iterrows():
        ipeds_info[row["University"]] = {
            "State": row.get("State", ""),
            "UNITID": row.get("UNITID", ""),
            "Institution_URL": row.get("Institution_URL", ""),
        }

    # Add GSS-only institutions and disciplines
    gss_only_rows = []
    for _, row in gss.iterrows():
        gss_inst = row.get("Institution_Name", "")
        gss_discipline = row.get("STEM_Discipline", "")
        match = inst_map.get(gss_inst)  # (ipeds_name, ipeds_state) or None

        if match:
            ipeds_name, ipeds_state = match
            # Check if this discipline already exists in IPEDS for this institution
            existing = ipeds_out[
                (ipeds_out["University"] == ipeds_name) &
                (ipeds_out["STEM_Discipline"] == gss_discipline)
            ]
            if not existing.empty:
                # Update source to "Both"
                mask = (
                    (ipeds_out["University"] == ipeds_name) &
                    (ipeds_out["STEM_Discipline"] == gss_discipline)
                )
                ipeds_out.loc[mask, "Source"] = "Both"
                if "GSS_Field_Code" in row.index and "GSS_Field_Code" in ipeds_out.columns:
                    ipeds_out.loc[mask, "GSS_Field_Code"] = row.get("GSS_Field_Code", "")
            else:
                # New discipline from GSS for a matched institution — use IPEDS metadata
                info = ipeds_info.get(ipeds_name, {})
                new_row = {
                    "State": info.get("State", ipeds_state),
                    "University": ipeds_name,
                    "STEM_Discipline": gss_discipline,
                    "Category": row.get("Category", ""),
                    "Source": "GSS",
                    "UNITID": info.get("UNITID", ""),
                    "CIP_2Digit": "",
                    "CIP_Codes_Detail": "",
                    "GSS_Field_Code": row.get("GSS_Field_Code", ""),
                    "Institution_URL": info.get("Institution_URL", ""),
                }
                gss_only_rows.append(new_row)
        else:
            # Entirely new institution from GSS
            new_row = {
                "State": row.get("State", ""),
                "University": gss_inst,
                "STEM_Discipline": gss_discipline,
                "Category": row.get("Category", ""),
                "Source": "GSS",
                "UNITID": row.get("UNITID", ""),
                "CIP_2Digit": "",
                "CIP_Codes_Detail": "",
                "GSS_Field_Code": row.get("GSS_Field_Code", ""),
                "Institution_URL": "",
            }
            gss_only_rows.append(new_row)

    if gss_only_rows:
        gss_additions = pd.DataFrame(gss_only_rows)
        # Align columns
        for col in ipeds_out.columns:
            if col not in gss_additions.columns:
                gss_additions[col] = ""
        gss_additions = gss_additions[ipeds_out.columns]
        ipeds_out = pd.concat([ipeds_out, gss_additions], ignore_index=True)
        print(f"  Added {len(gss_only_rows)} GSS-only rows")

    return ipeds_out.sort_values(["State", "University", "STEM_Discipline"]).reset_index(drop=True)


def cross_reference_gemini(master: pd.DataFrame) -> None:
    """Cross-reference master list against Gemini R1 university list."""
    if not os.path.exists(GEMINI_PATH):
        print("\nSkipping Gemini cross-reference (file not found).")
        return

    gemini = pd.read_csv(GEMINI_PATH)
    gemini_unis = []
    for _, row in gemini.iterrows():
        state = row.iloc[0]
        unis = [u.strip() for u in str(row.iloc[1]).split(",")]
        for u in unis:
            gemini_unis.append({"State": state, "University": u})

    gemini_df = pd.DataFrame(gemini_unis)
    master_unis = master["University"].dropna().unique().tolist()

    print(f"\n=== Gemini R1 Cross-Reference ===")
    print(f"Gemini R1 entries: {len(gemini_df)}")
    print(f"Master list unique institutions: {master['University'].nunique()}")

    # Check each Gemini university against master list
    missing = []
    for _, row in gemini_df.iterrows():
        uni = row["University"]
        state = row["State"]
        result = process.extractOne(
            normalize_name(uni),
            [normalize_name(m) for m in master_unis],
            scorer=fuzz.token_sort_ratio,
        )
        if not result or result[1] < FUZZY_THRESHOLD:
            missing.append(f"  {state}: {uni}")

    if missing:
        print(f"\nGemini R1 universities NOT found in master list ({len(missing)}):")
        for m in sorted(missing):
            print(m)
    else:
        print("\nAll Gemini R1 universities are represented in the master list.")


def main():
    print("=== Merging IPEDS and NSF GSS Data ===\n")

    ipeds = load_if_exists(IPEDS_PATH, "IPEDS filtered data")
    gss = load_if_exists(GSS_PATH, "NSF GSS filtered data")

    master = merge_datasets(ipeds, gss)

    master.to_csv(OUTPUT_PATH, index=False)
    print(f"\nExported master list: {len(master):,} rows to {os.path.abspath(OUTPUT_PATH)}")

    # Summary
    print(f"\n=== Master List Summary ===")
    print(f"Total rows: {len(master):,}")
    print(f"Unique institutions: {master['University'].nunique()}")
    print(f"\nBy Source:")
    print(master["Source"].value_counts().to_string())
    print(f"\nBy Category:")
    print(master["Category"].value_counts().to_string())
    print(f"\nBy Discipline:")
    print(master["STEM_Discipline"].value_counts().to_string())
    print(f"\nStates covered: {master['State'].nunique()}")

    cross_reference_gemini(master)


if __name__ == "__main__":
    main()
