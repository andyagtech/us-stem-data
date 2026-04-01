#!/usr/bin/env python3
"""
Archive completed scrape data to data/finished_data/.

Copies finished CSVs to the archive directory with standardized names.
Files in finished_data/ are NEVER modified — they serve as immutable backups.

Usage:
    python scripts/archive_finished.py                # archive all completed datasets
    python scripts/archive_finished.py --check        # dry-run: show what would be archived
"""

import argparse
import hashlib
import shutil
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
ARCHIVE_DIR = DATA_DIR / "finished_data"

# Registry of completed datasets: (source_path, archive_name)
COMPLETED = [
    # UC eScholarship (OAI-PMH)
    ("uc_dissertations/uc_dissertations_metadata.csv", "oai_uc_all_campuses.csv"),
    ("uc_dissertations/uc_stem_dissertations.csv", "oai_uc_stem_filtered.csv"),
    # Stanford
    ("stanford_dissertations/stanford_dissertations_metadata.csv", "api_stanford.csv"),
    # Caltech
    ("caltech_dissertations/caltech_theses_metadata.csv", "html_caltech.csv"),
    # Portland State
    ("or_wa_dissertations/pdxscholar_dissertations.csv", "oai_portland_state.csv"),
    ("or_wa_dissertations/pdxscholar_enriched.csv", "oai_portland_state_enriched.csv"),
    # Western US OAI-PMH harvests
    ("western_us_dissertations/uarizona_etds.csv", "oai_uarizona.csv"),
    ("western_us_dissertations/unm_etds.csv", "oai_unm.csv"),
    ("western_us_dissertations/mines_etds.csv", "oai_co_mines.csv"),
    ("western_us_dissertations/umt_etds.csv", "oai_u_montana.csv"),
    ("western_us_dissertations/boise_state_etds.csv", "oai_boise_state.csv"),
    ("western_us_dissertations/unlv_etds.csv", "oai_unlv.csv"),
    ("western_us_dissertations/byu_etds.csv", "oai_byu.csv"),
    ("western_us_dissertations/utah_state_etds.csv", "oai_utah_state.csv"),
    ("western_us_dissertations/udenver_etds.csv", "oai_u_denver.csv"),
    ("western_us_dissertations/northern_colorado_etds.csv", "oai_northern_colorado.csv"),
]

# Datasets that are still in progress — add to COMPLETED when done
IN_PROGRESS = [
    ("uw_dissertations/uw_dissertations_metadata.csv", "sitemap_uw_seattle.csv"),
    ("or_wa_dissertations/wsu_dissertations.csv", "sitemap_wsu.csv"),
    ("or_wa_dissertations/uoregon_dissertations.csv", "sitemap_u_oregon.csv"),
]


def file_hash(path, chunk_size=8192):
    """SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()[:16]


def archive_file(src_path, archive_name, dry_run=False):
    """Copy a file to the archive. Skip if identical copy already exists."""
    src = DATA_DIR / src_path
    dst = ARCHIVE_DIR / archive_name

    if not src.exists():
        return "MISSING", 0

    src_size = src.stat().st_size
    row_count = sum(1 for _ in open(src, encoding="utf-8", errors="replace")) - 1

    if dst.exists():
        if file_hash(src) == file_hash(dst):
            return "UP-TO-DATE", row_count
        else:
            return "CHANGED", row_count

    if not dry_run:
        shutil.copy2(src, dst)
        # Make read-only
        dst.chmod(0o444)

    return "ARCHIVED", row_count


def main():
    parser = argparse.ArgumentParser(description="Archive completed scrape data")
    parser.add_argument("--check", action="store_true", help="Dry-run: show what would be archived")
    args = parser.parse_args()

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"{'Status':<14} {'Rows':>8}  {'Archive Name':<35} {'Source'}")
    print("─" * 100)

    total_archived = 0
    total_rows = 0

    for src, name in COMPLETED:
        status, rows = archive_file(src, name, dry_run=args.check)
        print(f"{status:<14} {rows:>8,}  {name:<35} {src}")
        if status == "ARCHIVED":
            total_archived += 1
        if rows > 0:
            total_rows += rows

    print()
    print(f"In progress (not archived yet):")
    for src, name in IN_PROGRESS:
        src_path = DATA_DIR / src
        if src_path.exists():
            rows = sum(1 for _ in open(src_path, encoding="utf-8", errors="replace")) - 1
            print(f"  {'PENDING':<14} {rows:>8,}  {name:<35} {src}")
        else:
            print(f"  {'MISSING':<14} {'':>8}  {name:<35} {src}")

    print()
    print(f"Total: {total_archived} files archived, {total_rows:,} total rows")

    # Update manifest
    if not args.check:
        manifest = ARCHIVE_DIR / "MANIFEST.txt"
        with open(manifest, "w") as f:
            f.write(f"# Finished Data Manifest — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"# {total_rows:,} total rows across {len(COMPLETED)} datasets\n\n")
            f.write(f"{'Archive Name':<35} {'Rows':>8}  {'SHA-256':>18}  {'Source'}\n")
            f.write("─" * 100 + "\n")
            for src, name in COMPLETED:
                dst = ARCHIVE_DIR / name
                if dst.exists():
                    rows = sum(1 for _ in open(dst, encoding="utf-8", errors="replace")) - 1
                    h = file_hash(dst)
                    f.write(f"{name:<35} {rows:>8,}  {h:>18}  {src}\n")
        print(f"Manifest written to {manifest}")


if __name__ == "__main__":
    main()
