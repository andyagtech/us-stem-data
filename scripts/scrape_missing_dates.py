#!/usr/bin/env python3
"""
Scrape missing publication dates for universities whose OAI-PMH records
have no date fields (Binghamton, Mississippi State, SMU).

All three repositories use bepress, which embeds a
<meta name="bepress_citation_date" content="YYYY"> tag in the HTML.

Usage:
    python scripts/scrape_missing_dates.py                # all 3 universities
    python scripts/scrape_missing_dates.py --repo binghamton
    python scripts/scrape_missing_dates.py --repo msstate
    python scripts/scrape_missing_dates.py --repo smu
    python scripts/scrape_missing_dates.py --dry-run      # preview without writing
"""

import argparse
import csv
import json
import logging
import re
import sys
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "western_us_dissertations"

REQUEST_DELAY = 0.3          # seconds between requests (3x faster, ~33 min for 6739 records)
REQUEST_TIMEOUT = 30         # seconds per request
MAX_RETRIES = 3              # retry on transient errors
CHECKPOINT_INTERVAL = 50     # save progress every N records

HEADERS = {
    "User-Agent": "Western-US-PhD-Research/1.0 (academic research)",
}

REPOS = {
    "binghamton": {
        "file": DATA_DIR / "binghamton_etds.csv",
        "university": "Binghamton University",
    },
    "msstate": {
        "file": DATA_DIR / "msstate_etds.csv",
        "university": "Mississippi State University",
    },
    "smu": {
        "file": DATA_DIR / "smu_etds.csv",
        "university": "Southern Methodist University",
    },
}

# Checkpoint file for resuming interrupted scrapes
CHECKPOINT_FILE = DATA_DIR / "scrape_dates_checkpoint.json"


def fetch_date_from_page(url):
    """Fetch a bepress page and extract the citation date from meta tags.

    Returns the date string (typically a 4-digit year) or None.
    """
    for attempt in range(MAX_RETRIES):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Primary: <meta name="bepress_citation_date" content="2015">
            m = re.search(
                r'<meta\s+name=["\']bepress_citation_date["\']\s+content=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )
            if m:
                return m.group(1).strip()

            # Fallback: <meta name="DC.date" ...> or citation_publication_date
            for tag_name in ("DC.date", "citation_publication_date", "citation_date"):
                m = re.search(
                    rf'<meta\s+name=["\']{ re.escape(tag_name) }["\']\s+content=["\']([^"\']+)["\']',
                    html,
                    re.IGNORECASE,
                )
                if m:
                    return m.group(1).strip()

            # Fallback: look for "Date of Award/Degree" in visible text
            m = re.search(
                r'Date\s+of\s+(?:Award|Degree)[^<]*</h2>\s*<p>([^<]+)</p>',
                html,
                re.IGNORECASE,
            )
            if m:
                return m.group(1).strip()

            # Fallback: "Degree Date"
            m = re.search(
                r'Degree\s+Date[^<]*</h2>\s*<p>([^<]+)</p>',
                html,
                re.IGNORECASE,
            )
            if m:
                return m.group(1).strip()

            log.warning("No date found in HTML for %s", url)
            return None

        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                log.warning("Retry %d for %s: %s (waiting %ds)",
                            attempt + 1, url, exc, wait)
                time.sleep(wait)
            else:
                log.error("Failed after %d retries for %s: %s",
                          MAX_RETRIES, url, exc)
                return None

    return None


def extract_year(date_str):
    """Extract a 4-digit year from a date string."""
    if not date_str:
        return None
    m = re.search(r'\b(19|20)\d{2}\b', date_str)
    return int(m.group(0)) if m else None


def load_checkpoint():
    """Load checkpoint of already-scraped URLs."""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {}


def save_checkpoint(checkpoint):
    """Save checkpoint to disk."""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f)


def process_repo(repo_key, dry_run=False, resume=True):
    """Scrape dates for a single repository. Returns stats dict."""
    cfg = REPOS[repo_key]
    csv_path = cfg["file"]
    log.info("Processing %s (%s)", cfg["university"], csv_path.name)

    # Read all rows
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Load checkpoint for resume support
    checkpoint = load_checkpoint() if resume else {}
    repo_ckpt = checkpoint.get(repo_key, {})

    stats = {
        "total": len(rows),
        "already_have_date": 0,
        "scraped": 0,
        "recovered": 0,
        "failed": 0,
        "skipped_no_url": 0,
    }

    for i, row in enumerate(rows):
        # Skip rows that already have a date
        if row.get("date", "").strip():
            stats["already_have_date"] += 1
            continue

        url = row.get("url", "").strip()
        if not url:
            stats["skipped_no_url"] += 1
            continue

        # Check checkpoint
        if url in repo_ckpt:
            date_val = repo_ckpt[url]
            if date_val:
                row["date"] = date_val
                stats["recovered"] += 1
            else:
                stats["failed"] += 1
            stats["scraped"] += 1
            continue

        if dry_run:
            log.info("  [DRY-RUN] Would fetch: %s", url)
            continue

        # Rate limit
        time.sleep(REQUEST_DELAY)

        date_val = fetch_date_from_page(url)
        stats["scraped"] += 1

        if date_val:
            row["date"] = date_val
            stats["recovered"] += 1
            log.info("  [%d/%d] %s -> %s", i + 1, len(rows), url, date_val)
        else:
            stats["failed"] += 1
            log.info("  [%d/%d] %s -> NO DATE", i + 1, len(rows), url)

        # Save to checkpoint
        repo_ckpt[url] = date_val or ""
        checkpoint[repo_key] = repo_ckpt

        if stats["scraped"] % CHECKPOINT_INTERVAL == 0:
            save_checkpoint(checkpoint)
            log.info("  Checkpoint saved (%d scraped so far)", stats["scraped"])

    # Final checkpoint save
    if not dry_run:
        save_checkpoint(checkpoint)

    # Write updated CSV
    if not dry_run and stats["recovered"] > 0:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        log.info("  Wrote updated CSV: %s", csv_path)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Scrape missing dates for bepress ETD repositories"
    )
    parser.add_argument(
        "--repo",
        choices=list(REPOS.keys()),
        help="Process a single repository (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be fetched without making requests",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore checkpoint and re-scrape everything",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    repos_to_process = [args.repo] if args.repo else list(REPOS.keys())

    print(f"\n{'='*60}")
    print(f"Scraping missing dates for {len(repos_to_process)} repository(ies)")
    print(f"{'='*60}\n")

    all_stats = {}
    for repo_key in repos_to_process:
        stats = process_repo(repo_key, dry_run=args.dry_run,
                             resume=not args.no_resume)
        all_stats[repo_key] = stats

    # Summary report
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    total_recovered = 0
    total_records = 0
    for repo_key, stats in all_stats.items():
        cfg = REPOS[repo_key]
        total_recovered += stats["recovered"]
        total_records += stats["total"]
        print(f"\n  {cfg['university']} ({cfg['file'].name}):")
        print(f"    Total records:      {stats['total']}")
        print(f"    Already had dates:  {stats['already_have_date']}")
        print(f"    Scraped:            {stats['scraped']}")
        print(f"    Dates recovered:    {stats['recovered']}")
        print(f"    Failed:             {stats['failed']}")
        print(f"    No URL (skipped):   {stats['skipped_no_url']}")

    print(f"\n  TOTAL: {total_recovered} dates recovered across"
          f" {total_records} records")
    print()


if __name__ == "__main__":
    main()
