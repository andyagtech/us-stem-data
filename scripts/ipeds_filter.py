#!/usr/bin/env python3
"""
Filter IPEDS data to extract STEM PhD programs.

Handles all IPEDS eras (1984-2024):
  - Different file naming conventions (C_CIP, C_A, academic-year)
  - AWLEVEL code changes (9 → 17 transition in 2008)
  - Institutional file format variations (IC vs HD)

Outputs per-year CSVs to data/ipeds/filtered/ and can combine all years.

Usage:
    python scripts/ipeds_filter.py --year 2023         # single year
    python scripts/ipeds_filter.py --start 2000 --end 2024  # year range
    python scripts/ipeds_filter.py --all                # all available years
    python scripts/ipeds_filter.py --all --combine      # all years + combined CSV
"""

import argparse
import logging
import os
import sys
from dataclasses import dataclass

import pandas as pd

from ipeds_config import (
    ALL_YEARS,
    AWLEVEL_TRANSITION_YEARS,
    CIP_FAMILIES,
    IPEDS_COMBINED_OUTPUT,
    IPEDS_DATA_DIR,
    IPEDS_FILTERED_DIR,
    IPEDS_SINGLE_YEAR_OUTPUT,
    YEAR_FILES,
    phd_awlevels,
    resolve_inst_columns,
)

log = logging.getLogger("ipeds_filter")

# Encoding fallback order for older IPEDS CSVs
_ENCODINGS = ["utf-8-sig", "latin-1", "cp1252"]


def _read_csv_robust(path: str) -> pd.DataFrame:
    """Read a CSV trying multiple encodings."""
    for enc in _ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except (UnicodeDecodeError, UnicodeError):
            log.debug("    Encoding %s failed for %s, trying next...", enc, os.path.basename(path))
    raise ValueError(f"Could not decode {path} with any of {_ENCODINGS}")


# ---------------------------------------------------------------------------
# File resolution
# ---------------------------------------------------------------------------

def _find_csv(stem: str, data_dir: str) -> str | None:
    """
    Find a CSV on disk matching a file stem, case-insensitive.
    E.g. stem="C2023_A" matches "C2023_a.csv" or "c2023_a.csv".
    """
    stem_lower = stem.lower()
    try:
        for f in os.listdir(data_dir):
            f_lower = f.lower()
            if not f_lower.endswith(".csv"):
                continue
            # Strip extension and compare
            f_stem = f_lower.rsplit(".", 1)[0]
            if f_stem == stem_lower:
                return os.path.join(data_dir, f)
            # Handle _rv (revised) variants — accept them too
            if f_stem == stem_lower + "_rv":
                return os.path.join(data_dir, f)
    except FileNotFoundError:
        pass
    return None


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_completions(year: int, data_dir: str) -> pd.DataFrame | None:
    """Load the Completions CSV for a given year."""
    year_info = YEAR_FILES.get(year)
    if not year_info:
        log.error("No file mapping for year %d", year)
        return None

    path = _find_csv(year_info.completions, data_dir)
    if not path:
        log.error("Completions file not found for %d (expected %s.csv in %s)",
                  year, year_info.completions, data_dir)
        return None

    log.info("  Completions: %s", os.path.basename(path))
    df = _read_csv_robust(path)
    df.columns = df.columns.str.upper()
    log.info("    %s rows loaded", f"{len(df):,}")
    return df


def load_institutions(year: int, data_dir: str) -> pd.DataFrame | None:
    """Load the Institutional Characteristics CSV for a given year."""
    year_info = YEAR_FILES.get(year)
    if not year_info or not year_info.institutions:
        log.warning("  No institutional file mapped for %d", year)
        return None

    path = _find_csv(year_info.institutions, data_dir)
    if not path:
        log.warning("  Institutional file not found for %d (expected %s.csv)", year, year_info.institutions)
        return None

    log.info("  Institutions: %s", os.path.basename(path))
    df = _read_csv_robust(path)
    df.columns = df.columns.str.upper()
    log.info("    %s institutions loaded", f"{len(df):,}")
    return df


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def _normalize_cipcode(raw: pd.Series) -> pd.Series:
    """
    Normalize CIP codes to standard XX.XXXX dotted format.

    Handles three IPEDS-era formats:
      - Integer (1984-1989):  110101  →  "11.0101"
      - Narrow float (1991):  6.0402  →  "06.0402"
      - Standard (1995+):    11.0101 →  "11.0101"
    """
    s = raw.astype(str).str.strip()

    # Case 1: No dot → integer format. Insert dot after first 2 digits.
    no_dot = ~s.str.contains(r"\.", regex=True)
    s = s.where(~no_dot, s.str.zfill(6).str[:2] + "." + s.str.zfill(6).str[2:])

    # Case 2: Has dot but prefix is < 2 digits (e.g. "6.0402" → "06.0402")
    parts = s.str.split(".", n=1)
    prefix = parts.str[0].str.zfill(2)
    suffix = parts.str[1].fillna("0000")
    s = prefix + "." + suffix

    return s


def _extract_cip2(cipcode_series: pd.Series) -> pd.Series:
    """Extract the 2-digit CIP family from a normalized CIP code series."""
    return cipcode_series.str.split(".").str[0].str.zfill(2)


def _filter_transition_year(completions: pd.DataFrame) -> pd.DataFrame:
    """
    Handle AWLEVEL transition logic for 2008-2009.

    Each institution uses EITHER old code 9 OR new codes 17/18/19 (never both).
    - Institutions with any code 17/18/19 rows → keep only AWLEVEL=17
    - Institutions with only code 9 → keep AWLEVEL=9 (best available)
    """
    new_codes = {17, 18, 19}
    doctoral = completions[completions["AWLEVEL"].isin({9} | new_codes)]

    # Identify which institutions have adopted new codes
    inst_codes = doctoral.groupby("UNITID")["AWLEVEL"].apply(set)
    transitioned = set(inst_codes[inst_codes.apply(lambda s: bool(s & new_codes))].index)

    # Transitioned institutions: use code 17 only
    mask_new = (completions["UNITID"].isin(transitioned)) & (completions["AWLEVEL"] == 17)
    # Non-transitioned: use code 9
    mask_old = (~completions["UNITID"].isin(transitioned)) & (completions["AWLEVEL"] == 9)

    result = completions[mask_new | mask_old].copy()
    log.info("    Transition: %d institutions on new codes (AW=17), %d on old (AW=9)",
             len(transitioned),
             len(set(completions[mask_old]["UNITID"].unique())))
    return result


def filter_stem_phds(completions: pd.DataFrame, year: int) -> pd.DataFrame:
    """Filter completions for PhD-level STEM programs."""
    if year in AWLEVEL_TRANSITION_YEARS:
        phd_df = _filter_transition_year(completions)
        log.info("    → %s PhD rows (transition-year logic)", f"{len(phd_df):,}")
    else:
        awlevels = phd_awlevels(year)
        phd_mask = completions["AWLEVEL"].isin(awlevels)
        phd_df = completions[phd_mask].copy()
        log.info("    AWLEVEL %s → %s PhD rows", awlevels, f"{len(phd_df):,}")

    if phd_df.empty:
        return phd_df

    # Normalize CIP codes across all eras
    phd_df["CIPCODE"] = _normalize_cipcode(phd_df["CIPCODE"])

    # Extract 2-digit CIP prefix and filter for target families
    cip_2digit = _extract_cip2(phd_df["CIPCODE"])
    cip_prefixes = set(CIP_FAMILIES.keys())
    stem_mask = cip_2digit.isin(cip_prefixes)
    stem_df = phd_df[stem_mask].copy()
    log.info("    STEM/Clinical CIP filter → %s rows", f"{len(stem_df):,}")

    # Add standardized fields
    cip_2 = _extract_cip2(stem_df["CIPCODE"])
    stem_df["STEM_Discipline"] = cip_2.map(lambda x: CIP_FAMILIES.get(x, ("Unknown", "Unknown"))[0])
    stem_df["Category"] = cip_2.map(lambda x: CIP_FAMILIES.get(x, ("Unknown", "Unknown"))[1])
    stem_df["CIP_2Digit"] = cip_2

    return stem_df


# ---------------------------------------------------------------------------
# Merge + deduplicate
# ---------------------------------------------------------------------------

def merge_and_deduplicate(
    filtered: pd.DataFrame,
    institutions: pd.DataFrame | None,
    year: int,
) -> pd.DataFrame:
    """Merge filtered completions with institution details and deduplicate."""
    if institutions is not None:
        col_map = resolve_inst_columns(list(institutions.columns))
        # Build subset with canonical column names
        rename_map = {}
        available = []
        for canonical, actual in col_map.items():
            if actual:
                rename_map[actual] = canonical
                available.append(actual)

        inst_subset = institutions[available].rename(columns=rename_map)
        inst_subset = inst_subset.drop_duplicates(subset=["UNITID"])

        merged = filtered.merge(inst_subset, on="UNITID", how="left")
    else:
        merged = filtered.copy()
        # Add empty columns for consistency
        for col in ["INSTNM", "STABBR", "CITY", "WEBADDR"]:
            if col not in merged.columns:
                merged[col] = ""

    log.info("    Merged → %s rows", f"{len(merged):,}")

    if merged.empty:
        return _empty_result(year)

    # Deduplicate: one row per (UNITID, CIP 2-digit family)
    agg_dict = {"STEM_Discipline": "first", "Category": "first"}
    for col in ["INSTNM", "STABBR", "CITY", "WEBADDR"]:
        if col in merged.columns:
            agg_dict[col] = "first"
    agg_dict["CIPCODE"] = lambda x: "; ".join(sorted(x.unique()))

    dedup = merged.groupby(["UNITID", "CIP_2Digit"]).agg(agg_dict).reset_index()

    # Rename to canonical output columns
    rename = {
        "INSTNM": "University",
        "STABBR": "State",
        "CITY": "City",
        "WEBADDR": "Institution_URL",
        "CIPCODE": "CIP_Codes_Detail",
    }
    dedup = dedup.rename(columns={k: v for k, v in rename.items() if k in dedup.columns})

    dedup["Year"] = year

    # Ensure all output columns exist
    output_cols = [
        "Year", "UNITID", "State", "University", "City",
        "STEM_Discipline", "Category", "CIP_2Digit",
        "CIP_Codes_Detail", "Institution_URL",
    ]
    for c in output_cols:
        if c not in dedup.columns:
            dedup[c] = ""
    dedup = dedup[output_cols].sort_values(["State", "University", "STEM_Discipline"])

    log.info("    Deduplicated → %s (institution, discipline) pairs", f"{len(dedup):,}")
    return dedup


def _empty_result(year: int) -> pd.DataFrame:
    """Return an empty DataFrame with the standard output schema."""
    return pd.DataFrame(columns=[
        "Year", "UNITID", "State", "University", "City",
        "STEM_Discipline", "Category", "CIP_2Digit",
        "CIP_Codes_Detail", "Institution_URL",
    ])


# ---------------------------------------------------------------------------
# Per-year processing
# ---------------------------------------------------------------------------

@dataclass
class FilterResult:
    year: int
    status: str       # "ok", "skipped", "failed"
    rows: int = 0
    institutions: int = 0
    output_path: str = ""


def filter_year(year: int, data_dir: str, output_dir: str) -> FilterResult:
    """Run the full filter pipeline for a single year."""
    output_path = os.path.join(output_dir, f"ipeds_stem_phd_{year}.csv")

    # Skip if output already exists
    if os.path.exists(output_path):
        existing = pd.read_csv(output_path)
        log.info("[%d] Already filtered (%d rows) — skipping", year, len(existing))
        return FilterResult(year, "skipped", len(existing), existing["UNITID"].nunique(), output_path)

    log.info("[%d] Filtering...", year)

    completions = load_completions(year, data_dir)
    if completions is None:
        return FilterResult(year, "failed")

    institutions = load_institutions(year, data_dir)

    filtered = filter_stem_phds(completions, year)
    if filtered.empty:
        log.warning("[%d] No PhD STEM rows found", year)
        return FilterResult(year, "ok", 0, 0, output_path)

    result = merge_and_deduplicate(filtered, institutions, year)

    os.makedirs(output_dir, exist_ok=True)
    result.to_csv(output_path, index=False)
    log.info("[%d] → %s rows, %s institutions → %s",
             year, f"{len(result):,}", f"{result['UNITID'].nunique():,}",
             os.path.basename(output_path))

    return FilterResult(year, "ok", len(result), result["UNITID"].nunique(), output_path)


# ---------------------------------------------------------------------------
# Combine all years
# ---------------------------------------------------------------------------

def combine_years(output_dir: str, combined_path: str) -> pd.DataFrame:
    """Concatenate all per-year filtered CSVs into one combined file."""
    import glob as _glob
    files = sorted(_glob.glob(os.path.join(output_dir, "ipeds_stem_phd_*.csv")))
    if not files:
        log.error("No filtered files found in %s", output_dir)
        return pd.DataFrame()

    frames = []
    for f in files:
        df = pd.read_csv(f)
        frames.append(df)
        log.debug("  Loaded %s (%d rows)", os.path.basename(f), len(df))

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["Year", "State", "University", "STEM_Discipline"])
    combined.to_csv(combined_path, index=False)
    log.info("Combined %d years → %s rows → %s",
             len(files), f"{len(combined):,}", os.path.basename(combined_path))
    return combined


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(results: list[FilterResult]) -> None:
    """Print a summary table of filter results."""
    ok = [r for r in results if r.status == "ok"]
    skipped = [r for r in results if r.status == "skipped"]
    failed = [r for r in results if r.status == "failed"]

    log.info("\n=== Filter Summary ===")
    log.info("  Processed:  %d years", len(ok))
    log.info("  Skipped:    %d years (already filtered)", len(skipped))
    if failed:
        log.warning("  FAILED:     %d years", len(failed))
        for r in failed:
            log.warning("    %d", r.year)

    all_done = [r for r in results if r.status in ("ok", "skipped")]
    if all_done:
        total_rows = sum(r.rows for r in all_done)
        year_range = f"{min(r.year for r in all_done)}-{max(r.year for r in all_done)}"
        log.info("  Total rows across %s: %s", year_range, f"{total_rows:,}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_years(args) -> list[int]:
    if args.all:
        return list(ALL_YEARS)
    if args.year:
        return [args.year]
    start = args.start or min(ALL_YEARS)
    end = args.end or max(ALL_YEARS)
    return [y for y in ALL_YEARS if start <= y <= end]


def main():
    parser = argparse.ArgumentParser(description="Filter IPEDS data for STEM PhD programs.")
    parser.add_argument("--year", type=int, help="Single year to filter")
    parser.add_argument("--start", type=int, help="Start of year range")
    parser.add_argument("--end", type=int, help="End of year range")
    parser.add_argument("--all", action="store_true", help="Process all available years")
    parser.add_argument("--combine", action="store_true", help="Combine all per-year outputs into one CSV")
    parser.add_argument("--force", action="store_true", help="Re-filter even if output exists")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    years = _parse_years(args)
    log.info("=== IPEDS Filter: %d years (%d–%d) ===\n", len(years), min(years), max(years))

    if args.force:
        # Remove existing per-year outputs so they get regenerated
        for y in years:
            p = os.path.join(IPEDS_FILTERED_DIR, f"ipeds_stem_phd_{y}.csv")
            if os.path.exists(p):
                os.remove(p)

    results = []
    for year in years:
        result = filter_year(year, IPEDS_DATA_DIR, IPEDS_FILTERED_DIR)
        results.append(result)

    print_summary(results)

    # Also write the single-year legacy output for the most recent year
    most_recent = max(years)
    latest_filtered = os.path.join(IPEDS_FILTERED_DIR, f"ipeds_stem_phd_{most_recent}.csv")
    if os.path.exists(latest_filtered):
        import shutil
        shutil.copy2(latest_filtered, IPEDS_SINGLE_YEAR_OUTPUT)
        log.info("\nCopied latest year (%d) → %s", most_recent, os.path.basename(IPEDS_SINGLE_YEAR_OUTPUT))

    if args.combine:
        log.info("")
        combine_years(IPEDS_FILTERED_DIR, IPEDS_COMBINED_OUTPUT)


if __name__ == "__main__":
    main()
