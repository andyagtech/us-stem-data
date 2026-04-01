#!/usr/bin/env python3
"""
Download IPEDS Complete Data Files for one or many survey years.

Idempotent: skips files already present on disk.
Uses direct URL downloads from the NCES server.

Usage:
    python scripts/download_ipeds.py                     # download all known years
    python scripts/download_ipeds.py --year 2023         # single year
    python scripts/download_ipeds.py --start 2000 --end 2024  # year range
    python scripts/download_ipeds.py --dry-run            # show what would download
"""

import argparse
import io
import logging
import os
import sys
import zipfile
from dataclasses import dataclass

import requests

from ipeds_config import (
    ALL_YEARS,
    DIRECT_BASE_URL,
    IPEDS_DATA_DIR,
    YEAR_FILES,
)

log = logging.getLogger("download_ipeds")

# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

@dataclass
class DownloadResult:
    year: int
    file_stem: str
    status: str        # "ok", "skipped", "failed"
    detail: str = ""


def _csv_exists(file_stem: str, data_dir: str) -> bool:
    """Check if at least one CSV matching this stem already exists."""
    stem_lower = file_stem.lower()
    try:
        for f in os.listdir(data_dir):
            if f.lower().startswith(stem_lower) and f.lower().endswith(".csv"):
                return True
            # Also match lowercase with underscores (e.g. c9596_a.csv for C9596_A)
            if f.lower().replace("-", "_") == stem_lower.replace("-", "_") + ".csv":
                return True
    except FileNotFoundError:
        pass
    return False


def download_zip(file_stem: str, data_dir: str, timeout: int = 120) -> bool:
    """Download and extract a ZIP from the NCES server. Returns True on success."""
    url = f"{DIRECT_BASE_URL}/{file_stem}.zip"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        if len(resp.content) < 500:
            log.warning("  Response too small (%d bytes) — likely error page", len(resp.content))
            return False
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_files = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            zf.extractall(data_dir)
            log.info("  Extracted: %s (%.1f MB)", csv_files, len(resp.content) / 1024 / 1024)
        return True
    except (requests.RequestException, zipfile.BadZipFile) as exc:
        log.warning("  Download failed for %s: %s", file_stem, exc)
        return False


# ---------------------------------------------------------------------------
# Multi-year download
# ---------------------------------------------------------------------------

def download_year(year: int, data_dir: str, dry_run: bool = False) -> list[DownloadResult]:
    """Download completions + institutional files for a single year."""
    year_info = YEAR_FILES.get(year)
    if year_info is None:
        return [DownloadResult(year, "", "failed", f"No file mapping for year {year}")]

    results = []
    for label, stem in [("completions", year_info.completions), ("institutions", year_info.institutions)]:
        if not stem:
            results.append(DownloadResult(year, "", "skipped", f"No {label} file known"))
            continue

        if _csv_exists(stem, data_dir):
            results.append(DownloadResult(year, stem, "skipped", "already on disk"))
            continue

        if dry_run:
            results.append(DownloadResult(year, stem, "skipped", "dry-run"))
            continue

        log.info("  [%d] Downloading %s (%s)...", year, stem, label)
        ok = download_zip(stem, data_dir)
        results.append(DownloadResult(
            year, stem,
            "ok" if ok else "failed",
            "" if ok else "download/extract error",
        ))

    return results


def download_years(years: list[int], data_dir: str, dry_run: bool = False) -> list[DownloadResult]:
    """Download files for multiple years. Returns list of results."""
    os.makedirs(data_dir, exist_ok=True)
    all_results: list[DownloadResult] = []
    for year in years:
        results = download_year(year, data_dir, dry_run=dry_run)
        all_results.extend(results)
    return all_results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_years(args) -> list[int]:
    """Resolve CLI arguments into a list of years."""
    if args.year:
        return [args.year]
    start = args.start or min(ALL_YEARS)
    end = args.end or max(ALL_YEARS)
    return [y for y in ALL_YEARS if start <= y <= end]


def main():
    parser = argparse.ArgumentParser(description="Download IPEDS data files.")
    parser.add_argument("--year", type=int, help="Single year to download")
    parser.add_argument("--start", type=int, help="Start of year range (default: earliest)")
    parser.add_argument("--end", type=int, help="End of year range (default: latest)")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without downloading")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    years = _parse_years(args)
    log.info("=== IPEDS Download: %d years (%d–%d) ===", len(years), min(years), max(years))
    log.info("Output: %s\n", os.path.abspath(IPEDS_DATA_DIR))

    if args.dry_run:
        log.info("[DRY RUN] Would download:\n")
        for y in years:
            yf = YEAR_FILES.get(y)
            if yf:
                log.info("  %d: completions=%s  institutions=%s", y, yf.completions, yf.institutions or "(none)")
        return

    results = download_years(years, IPEDS_DATA_DIR)

    # Summary
    ok = [r for r in results if r.status == "ok"]
    skipped = [r for r in results if r.status == "skipped"]
    failed = [r for r in results if r.status == "failed"]

    log.info("\n=== Download Summary ===")
    log.info("  Downloaded: %d files", len(ok))
    log.info("  Skipped:    %d (already on disk or unavailable)", len(skipped))
    if failed:
        log.warning("  FAILED:     %d files", len(failed))
        for r in failed:
            log.warning("    %d %s: %s", r.year, r.file_stem, r.detail)
        sys.exit(1)
    else:
        log.info("  Failures:   0")


if __name__ == "__main__":
    main()
