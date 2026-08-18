#!/usr/bin/env python3
"""
Shared configuration for the IPEDS pipeline.

Single source of truth for file patterns, AWLEVEL codes, CIP families,
directory paths, and year-specific metadata across all pipeline stages.
"""

import os
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
IPEDS_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "ipeds")
IPEDS_FILTERED_DIR = os.path.join(IPEDS_DATA_DIR, "filtered")
IPEDS_COMBINED_OUTPUT = os.path.join(IPEDS_DATA_DIR, "ipeds_stem_phd_all_years.csv")
IPEDS_SINGLE_YEAR_OUTPUT = os.path.join(IPEDS_DATA_DIR, "ipeds_stem_phd_programs.csv")

# ---------------------------------------------------------------------------
# Download URLs
# ---------------------------------------------------------------------------

# NCES moved the Complete Data Files in 2026. The old datacenter/data path is
# now a frozen mirror that 404s for anything from the 2024-25 collection
# onward (C2025_A, HD2025, EF2024A all 404 there, 200 here), while the new
# path still serves every historical file, so this is a superset.
DIRECT_BASE_URL = "https://nces.ed.gov/ipeds/complete-data-files"

# ---------------------------------------------------------------------------
# CIP code families → (discipline name, category)
# ---------------------------------------------------------------------------

CIP_FAMILIES: dict[str, tuple[str, str]] = {
    "11": ("Computer and Information Sciences", "Core STEM"),
    "14": ("Engineering", "Core STEM"),
    "15": ("Engineering Technologies", "Core STEM"),
    "26": ("Biological and Biomedical Sciences", "Core STEM"),
    "27": ("Mathematics and Statistics", "Core STEM"),
    "30": ("Multi/Interdisciplinary Studies", "Core STEM"),
    "40": ("Physical Sciences", "Core STEM"),
    "42": ("Psychology", "Core STEM"),
    "51": ("Health Professions / Clinical", "Clinical/Medical"),
}

# ---------------------------------------------------------------------------
# Year metadata
# ---------------------------------------------------------------------------

# All years we know have completions data on the NCES server.
ALL_YEARS = (
    list(range(1984, 1990))       # 1984-1989
    + list(range(1991, 1995))     # 1991-1994  (1990 missing)
    + list(range(1995, 1999))     # 1995-1998  (1999 missing)
    + list(range(2000, 2026))     # 2000-2025
)

MISSING_YEARS = {1990, 1999}  # Known gaps in completions data


@dataclass(frozen=True)
class YearFiles:
    """File names for a given survey year (without extension)."""
    completions: str   # e.g. "C2023_A" or "C1984_CIP" or "C9596_A"
    institutions: str  # e.g. "HD2023" or "IC1984" or "" if unavailable


def _build_year_file_map() -> dict[int, YearFiles]:
    """
    Build a mapping of survey year → known file stems on the NCES server.

    Completions file naming conventions by era:
      1984-1994:  C{YEAR}_CIP
      1995-1998:  C{YY}{YY+1}_A   (academic-year format)
      2000-2024:  C{YEAR}_A

    Institutional file naming conventions:
      1980:       IC1980
      1984-1985:  IC{YEAR}
      1986-1989:  (not available — use nearest)
      1991:       IC1991_HDR
      1992-1996:  (not available — use nearest)
      1997:       IC9798_HDR
      1998-1999:  (not available — use nearest)
      2000-2001:  IC{YEAR}_AY
      2002-2024:  HD{YEAR}
    """
    m: dict[int, YearFiles] = {}

    # --- Completions ---
    for y in range(1984, 1995):
        if y == 1990:
            continue
        m[y] = YearFiles(completions=f"C{y}_CIP", institutions="")

    for y in range(1995, 1999):
        yy = str(y)[2:]
        yy1 = str(y + 1)[2:]
        m[y] = YearFiles(completions=f"C{yy}{yy1}_A", institutions="")

    for y in range(2000, 2026):
        m[y] = YearFiles(completions=f"C{y}_A", institutions="")

    # --- Institutions (overlay onto existing entries) ---
    inst_map: dict[int, str] = {
        1980: "IC1980",
        1984: "IC1984",
        1985: "IC1985",
        1991: "IC1991_HDR",
        1997: "IC9798_HDR",
        2000: "IC2000_AY",
        2001: "IC2001_AY",
    }
    for y in range(2002, 2026):
        inst_map[y] = f"HD{y}"

    for y, files in m.items():
        inst = inst_map.get(y, "")
        if not inst:
            inst = _nearest_inst_file(y, inst_map)
        m[y] = YearFiles(completions=files.completions, institutions=inst)

    return m


def _nearest_inst_file(year: int, inst_map: dict[int, str]) -> str:
    """Find the closest available institutional file for a year without one."""
    available = sorted(inst_map.keys())
    best = min(available, key=lambda y: abs(y - year))
    return inst_map[best]


YEAR_FILES: dict[int, YearFiles] = _build_year_file_map()

# ---------------------------------------------------------------------------
# AWLEVEL codes for PhD (research/scholarship)
# ---------------------------------------------------------------------------

# Pre-2008: AWLEVEL=9 is "Doctor's degree" (research only; professional
#   degrees were coded as AWLEVEL=10 "First-professional").
# 2008-2009: Transition period. NCES split doctorates into:
#   17 = Doctor's degree — research/scholarship
#   18 = Doctor's degree — professional practice
#   19 = Doctor's degree — other
#   During transition, each institution uses EITHER old code 9 OR new codes
#   17/18/19 (never both).  Institutions still on code 9 lumped professional
#   doctorates in, so naively using code 9 overcounts research PhDs ~70%.
# 2010+: AWLEVEL=17 is reliably "research/scholarship" only.
#
# Strategy for 2008-2009 (implemented in ipeds_filter.filter_stem_phds):
#   - Institutions that have ANY code 17/18/19 → use code 17 only
#   - Institutions with only code 9 → use code 9 (best available)
#   This is imperfect for code-9-only institutions but is the most
#   accurate approach without external validation data.

# Transition years where per-institution AWLEVEL logic is needed.
AWLEVEL_TRANSITION_YEARS = {2008, 2009}


def phd_awlevels(year: int) -> list[int]:
    """Return the AWLEVEL code(s) that represent research PhDs for a given year.

    For 2008-2009 transition years, this returns both codes.  The caller
    (filter_stem_phds) applies per-institution logic to pick the right one.
    """
    if year <= 2007:
        return [9]
    elif year in AWLEVEL_TRANSITION_YEARS:
        return [9, 17]
    else:
        return [17]


# ---------------------------------------------------------------------------
# Institutional file column mapping (varies by era)
# ---------------------------------------------------------------------------

# The key columns we need, mapped to canonical names.
# Listed in order of preference — first match wins.
INST_COLUMN_ALIASES = {
    "UNITID":  ["UNITID"],
    "INSTNM":  ["INSTNM"],
    "STABBR":  ["STABBR"],
    "CITY":    ["CITY"],
    "WEBADDR": ["WEBADDR", "INSTURL", "PBATEFX"],
}


def resolve_inst_columns(columns: list[str]) -> dict[str, str | None]:
    """
    Given a list of actual column names in an institutional CSV,
    return a mapping of canonical name → actual column name.
    """
    cols_upper = {c.upper(): c for c in columns}
    resolved = {}
    for canonical, aliases in INST_COLUMN_ALIASES.items():
        resolved[canonical] = None
        for alias in aliases:
            if alias in cols_upper:
                resolved[canonical] = cols_upper[alias]
                break
    return resolved
