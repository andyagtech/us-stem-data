#!/usr/bin/env python3
"""
Scrape thesis metadata from CaltechTHESIS (static EPrints mirror).

Phase 1: Scrape year browse pages for basic metadata (author, title, year, degree, ID).
Phase 2 (optional): Enrich with individual thesis pages (division, option, advisor, defense date).

Usage:
    python scripts/scrape_caltech_theses.py --all                 # Phase 1: all years
    python scripts/scrape_caltech_theses.py --start 2000 --end 2025  # Phase 1: year range
    python scripts/scrape_caltech_theses.py --enrich              # Phase 2: fetch individual pages
    python scripts/scrape_caltech_theses.py --enrich --max 100    # Phase 2: limit
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

BASE_URL = "https://thesis.caltech.edu"
OUTPUT_DIR = Path("data/caltech_dissertations")
OUTPUT_CSV = OUTPUT_DIR / "caltech_theses_metadata.csv"
CHECKPOINT = OUTPUT_DIR / "caltech_checkpoint.json"

CSV_FIELDS = [
    "id", "url", "title", "author", "year", "degree_type", "doi",
    "resolver_url", "division", "major_option", "advisor", "defense_date",
    "keywords", "thesis_availability",
]


def fetch(url, delay=1.0):
    """Fetch a URL with delay and error handling."""
    time.sleep(delay)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (research scraper)"})
    try:
        resp = urlopen(req, timeout=30)
        return resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as e:
        log.warning("Failed to fetch %s: %s", url, e)
        return None


def get_year_list():
    """Fetch the year index page and return list of available years."""
    html = fetch(f"{BASE_URL}/view/year/", delay=0.5)
    if not html:
        log.error("Cannot fetch year index")
        return []
    years = re.findall(r'/view/year/(\d{4})\.html', html)
    return sorted(set(int(y) for y in years))


def parse_year_page(html, year):
    """Parse a year browse page and extract thesis entries."""
    entries = []

    # Count from page header
    count_match = re.search(r'Number of items:\s*<strong>\s*(\d+)', html)
    expected = int(count_match.group(1)) if count_match else 0

    # Each thesis is in a <p> block with structured content:
    #   <span class="person_name">Author</span>
    #   (YYYY)
    #   <a href="/NNNNN/"><em>Title</em></a>
    #   Degree type text.
    #   doi:...
    #   <a href="resolver_url">...</a>

    # Split by <p> tags to get individual entries
    blocks = re.split(r'<p\b[^>]*>', html)

    for block in blocks:
        # Must contain a person_name span
        author_match = re.search(
            r'<span class="person_name">\s*(.*?)\s*</span>', block, re.DOTALL
        )
        if not author_match:
            continue

        author = re.sub(r'<[^>]+>', '', author_match.group(1)).strip()

        # Year
        year_match = re.search(r'\((\d{4})\)', block)
        entry_year = int(year_match.group(1)) if year_match else year

        # Thesis ID and title
        link_match = re.search(r'<a href="/(\d+)/">\s*<em>\s*(.*?)\s*</em>\s*</a>', block, re.DOTALL)
        if not link_match:
            continue
        thesis_id = link_match.group(1)
        title = re.sub(r'<[^>]+>', '', link_match.group(2)).strip()
        title = re.sub(r'\s+', ' ', title)

        # Degree type — text after the </a> closing the title link
        # e.g., "Dissertation (Ph.D.), California Institute of Technology."
        after_title = block[link_match.end():]
        degree_match = re.search(
            r'(Dissertation \(Ph\.D\.\)|Master\'s thesis|Engineer\'s thesis|'
            r'Bachelor\'s thesis|Senior thesis|Thesis \([^)]+\))',
            after_title, re.IGNORECASE
        )
        degree_type = degree_match.group(0) if degree_match else ""

        # DOI
        doi_match = re.search(r'doi:(10\.\d{4,}/[^\s<]+)', after_title)
        doi = doi_match.group(1).rstrip('.') if doi_match else ""

        # Resolver URL
        resolver_match = re.search(
            r'href="(https://resolver\.caltech\.edu/[^"]+)"', after_title
        )
        resolver_url = resolver_match.group(1) if resolver_match else ""

        entries.append({
            "id": thesis_id,
            "url": f"{BASE_URL}/{thesis_id}/",
            "title": title,
            "author": author,
            "year": str(entry_year),
            "degree_type": degree_type,
            "doi": doi,
            "resolver_url": resolver_url,
            "division": "",
            "major_option": "",
            "advisor": "",
            "defense_date": "",
            "keywords": "",
            "thesis_availability": "",
        })

    if expected and len(entries) != expected:
        log.warning("Year %d: expected %d, parsed %d", year, expected, len(entries))

    return entries


def parse_thesis_page(html):
    """Parse an individual thesis page for enriched metadata."""
    meta = {}

    # Extract table rows: <th>Label:</th><td>Value</td>
    rows = re.findall(
        r'<tr[^>]*>\s*<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>',
        html, re.DOTALL
    )
    for th, td in rows:
        label = re.sub(r'<[^>]+>', '', th).strip().rstrip(':')
        value = re.sub(r'<[^>]+>', ' ', td).strip()
        value = re.sub(r'\s+', ' ', value)

        if label == "Division":
            meta["division"] = value
        elif label == "Major Option":
            meta["major_option"] = value
        elif "Minor Option" in label and value:
            # Append minor to major
            if meta.get("major_option"):
                meta["major_option"] += f"; Minor: {value}"
            else:
                meta["major_option"] = f"Minor: {value}"
        elif "Research Advisor" in label:
            meta["advisor"] = value
        elif label == "Defense Date":
            meta["defense_date"] = value
        elif label == "Subject Keywords":
            meta["keywords"] = value
        elif label == "Thesis Availability":
            meta["thesis_availability"] = value

    return meta


def load_checkpoint():
    """Load checkpoint data."""
    if CHECKPOINT.exists():
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {"phase1_years_done": [], "phase2_ids_done": []}


def save_checkpoint(ckpt):
    """Save checkpoint data."""
    with open(CHECKPOINT, "w") as f:
        json.dump(ckpt, f)


def phase1(args):
    """Phase 1: Scrape year browse pages."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ckpt = load_checkpoint()
    years_done = set(ckpt.get("phase1_years_done", []))

    # Get available years
    all_years = get_year_list()
    if not all_years:
        log.error("No years found")
        return

    log.info("Available years: %d-%d (%d total)", min(all_years), max(all_years), len(all_years))

    # Filter to requested range
    if args.start or args.end:
        start = args.start or min(all_years)
        end = args.end or max(all_years)
        target_years = [y for y in all_years if start <= y <= end]
    else:
        target_years = all_years

    # Skip already-done years unless --force
    if not args.force:
        target_years = [y for y in target_years if y not in years_done]

    log.info("Scraping %d year pages (skipping %d already done)",
             len(target_years), len(years_done))

    # Open CSV
    file_exists = OUTPUT_CSV.exists() and not args.force
    csvfile = open(OUTPUT_CSV, "a" if file_exists else "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
    if not file_exists:
        writer.writeheader()

    total_entries = 0
    for i, year in enumerate(sorted(target_years)):
        url = f"{BASE_URL}/view/year/{year}.html"
        log.info("[%d/%d] Fetching year %d...", i + 1, len(target_years), year)

        html = fetch(url, delay=args.delay)
        if html is None:
            log.warning("Skipping year %d (fetch failed)", year)
            continue

        entries = parse_year_page(html, year)
        for entry in entries:
            writer.writerow(entry)
        csvfile.flush()

        total_entries += len(entries)
        years_done.add(year)
        ckpt["phase1_years_done"] = sorted(years_done)
        save_checkpoint(ckpt)

        log.info("  Year %d: %d theses (total so far: %d)", year, len(entries), total_entries)

    csvfile.close()
    log.info("Phase 1 complete: %d theses from %d years → %s", total_entries, len(target_years), OUTPUT_CSV)


def phase2(args):
    """Phase 2: Enrich with individual thesis page metadata."""
    if not OUTPUT_CSV.exists():
        log.error("Run phase 1 first: %s not found", OUTPUT_CSV)
        return

    ckpt = load_checkpoint()
    ids_done = set(ckpt.get("phase2_ids_done", []))

    # Read existing records
    with open(OUTPUT_CSV) as f:
        records = list(csv.DictReader(f))

    log.info("Loaded %d records, %d already enriched", len(records), len(ids_done))

    # Find records needing enrichment
    to_enrich = [r for r in records if r["id"] not in ids_done and not r.get("division")]
    if args.max:
        to_enrich = to_enrich[:args.max]

    log.info("Enriching %d records...", len(to_enrich))

    # Build lookup by ID
    record_map = {r["id"]: r for r in records}
    consecutive_errors = 0

    for i, rec in enumerate(to_enrich):
        url = rec["url"]
        log.info("[%d/%d] Enriching %s — %s", i + 1, len(to_enrich), rec["id"], rec["author"])

        html = fetch(url, delay=args.delay)
        if html is None:
            consecutive_errors += 1
            if consecutive_errors > 20:
                log.error("Too many consecutive errors, stopping.")
                break
            continue

        consecutive_errors = 0
        meta = parse_thesis_page(html)

        # Update record
        for key, value in meta.items():
            if value:
                record_map[rec["id"]][key] = value

        ids_done.add(rec["id"])
        ckpt["phase2_ids_done"] = sorted(ids_done)

        if (i + 1) % 50 == 0:
            # Periodic save
            save_checkpoint(ckpt)
            with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()
                writer.writerows(records)
            log.info("  Saved checkpoint (%d enriched)", len(ids_done))

    # Final save
    save_checkpoint(ckpt)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)

    log.info("Phase 2 complete: %d records enriched → %s", len(ids_done), OUTPUT_CSV)


def main():
    parser = argparse.ArgumentParser(description="Scrape CaltechTHESIS")
    parser.add_argument("--all", action="store_true", help="Scrape all years")
    parser.add_argument("--start", type=int, help="Start year")
    parser.add_argument("--end", type=int, help="End year")
    parser.add_argument("--enrich", action="store_true", help="Phase 2: enrich with individual pages")
    parser.add_argument("--max", type=int, default=0, help="Max items (phase 2)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests (seconds)")
    parser.add_argument("--force", action="store_true", help="Re-scrape even if already done")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.enrich:
        phase2(args)
    elif args.all or args.start or args.end:
        phase1(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
