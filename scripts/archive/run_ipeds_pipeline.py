#!/usr/bin/env python3
"""
IPEDS Pipeline Orchestrator.

Runs the full pipeline: download → filter → combine across all years.
Each stage is idempotent — re-running skips already-completed work.

Usage:
    python scripts/run_ipeds_pipeline.py                       # full pipeline, all years
    python scripts/run_ipeds_pipeline.py --start 2000 --end 2024  # year range
    python scripts/run_ipeds_pipeline.py --year 2023           # single year
    python scripts/run_ipeds_pipeline.py --skip-download       # filter only (data already present)
    python scripts/run_ipeds_pipeline.py --force               # re-filter even if outputs exist
"""

import argparse
import logging
import os
import sys
import time

from ipeds_config import ALL_YEARS, IPEDS_COMBINED_OUTPUT, IPEDS_DATA_DIR, IPEDS_FILTERED_DIR

log = logging.getLogger("ipeds_pipeline")


def _parse_years(args) -> list[int]:
    if args.year:
        return [args.year]
    start = args.start or min(ALL_YEARS)
    end = args.end or max(ALL_YEARS)
    return [y for y in ALL_YEARS if start <= y <= end]


def run_download(years: list[int]) -> bool:
    """Stage 1: Download raw data."""
    from download_ipeds import download_years

    log.info("=" * 60)
    log.info("STAGE 1: DOWNLOAD (%d years)", len(years))
    log.info("=" * 60)

    results = download_years(years, IPEDS_DATA_DIR)
    failed = [r for r in results if r.status == "failed"]
    ok = [r for r in results if r.status == "ok"]
    skipped = [r for r in results if r.status == "skipped"]

    log.info("  Downloaded: %d  Skipped: %d  Failed: %d", len(ok), len(skipped), len(failed))

    if failed:
        log.warning("  Failed downloads:")
        for r in failed:
            log.warning("    %d %s: %s", r.year, r.file_stem, r.detail)

    return len(failed) == 0


def run_filter(years: list[int], force: bool = False) -> bool:
    """Stage 2: Filter each year."""
    from ipeds_filter import filter_year, print_summary

    log.info("")
    log.info("=" * 60)
    log.info("STAGE 2: FILTER (%d years)", len(years))
    log.info("=" * 60)

    if force:
        for y in years:
            p = os.path.join(IPEDS_FILTERED_DIR, f"ipeds_stem_phd_{y}.csv")
            if os.path.exists(p):
                os.remove(p)

    results = []
    for year in years:
        result = filter_year(year, IPEDS_DATA_DIR, IPEDS_FILTERED_DIR)
        results.append(result)

    print_summary(results)

    failed = [r for r in results if r.status == "failed"]
    return len(failed) == 0


def run_combine() -> bool:
    """Stage 3: Combine all per-year filtered outputs."""
    from ipeds_filter import combine_years

    log.info("")
    log.info("=" * 60)
    log.info("STAGE 3: COMBINE")
    log.info("=" * 60)

    df = combine_years(IPEDS_FILTERED_DIR, IPEDS_COMBINED_OUTPUT)
    if df.empty:
        log.error("Combined output is empty")
        return False

    # Print summary stats
    log.info("")
    log.info("=== Combined Dataset Summary ===")
    log.info("  Total rows:         %s", f"{len(df):,}")
    log.info("  Unique institutions: %s", f"{df['UNITID'].nunique():,}")
    log.info("  Years covered:      %d–%d (%d years)",
             df["Year"].min(), df["Year"].max(), df["Year"].nunique())
    log.info("  States covered:     %d", df["State"].nunique())

    log.info("\n  By Category:")
    for cat, count in df.groupby("Category").size().items():
        log.info("    %-25s %s", cat, f"{count:,}")

    log.info("\n  By Discipline:")
    for disc, count in df.groupby("STEM_Discipline").size().sort_values(ascending=False).items():
        log.info("    %-40s %s", disc, f"{count:,}")

    log.info("\n  By Decade:")
    df["Decade"] = (df["Year"] // 10) * 10
    for decade, count in df.groupby("Decade").size().items():
        institutions = df[df["Decade"] == decade]["UNITID"].nunique()
        log.info("    %ds: %5s rows, %s institutions", decade, f"{count:,}", f"{institutions:,}")

    return True


def main():
    parser = argparse.ArgumentParser(description="IPEDS Pipeline: download → filter → combine.")
    parser.add_argument("--year", type=int, help="Single year")
    parser.add_argument("--start", type=int, help="Start of year range")
    parser.add_argument("--end", type=int, help="End of year range")
    parser.add_argument("--skip-download", action="store_true", help="Skip download stage")
    parser.add_argument("--skip-filter", action="store_true", help="Skip filter stage (combine only)")
    parser.add_argument("--force", action="store_true", help="Re-filter even if outputs exist")
    parser.add_argument("--no-combine", action="store_true", help="Skip the combine stage")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    years = _parse_years(args)
    t0 = time.time()

    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║  IPEDS STEM PhD Pipeline — %d years (%d–%d)          ║",
             len(years), min(years), max(years))
    log.info("╚══════════════════════════════════════════════════════════╝")
    log.info("")

    ok = True

    if not args.skip_download:
        ok = run_download(years) and ok

    if not args.skip_filter:
        ok = run_filter(years, force=args.force) and ok

    if not args.no_combine:
        ok = run_combine() and ok

    elapsed = time.time() - t0
    log.info("\n" + "=" * 60)
    log.info("Pipeline %s in %.1f seconds.",
             "completed" if ok else "finished with errors", elapsed)
    log.info("=" * 60)

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
