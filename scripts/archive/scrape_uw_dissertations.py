#!/usr/bin/env python3
"""
Scrape UW ResearchWorks dissertation metadata from the DSpace 7 repository.

Uses the sitemap to discover item URLs, then extracts citation metadata
from server-side rendered HTML meta tags.

Usage:
    python scripts/scrape_uw_dissertations.py --max 100     # test with 100 items
    python scripts/scrape_uw_dissertations.py --all          # scrape all ~36K items
    python scripts/scrape_uw_dissertations.py --resume       # resume from last checkpoint
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

log = logging.getLogger(__name__)

SITEMAP_URL = "https://digital.lib.washington.edu/researchworks/sitemap0.xml"
BASE_URL = "https://digital.lib.washington.edu/researchworks"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "uw_dissertations"
OUTPUT_CSV = OUTPUT_DIR / "uw_dissertations_metadata.csv"
CHECKPOINT_FILE = OUTPUT_DIR / "scrape_checkpoint.json"

# Fields to extract from HTML meta tags
CITATION_FIELDS = [
    "citation_title",
    "citation_author",
    "citation_publication_date",
    "citation_keywords",
    "citation_language",
    "citation_abstract_html_url",
    "citation_pdf_url",
    "citation_dissertation_institution",
]

# Also extract standard meta fields
META_FIELDS = ["title", "description"]

HEADERS = {
    "User-Agent": "UW-Dissertation-Research/1.0 (academic research)",
    "Accept": "text/html",
}

# Rate limiting
REQUEST_DELAY = 0.5  # seconds between requests


def fetch_sitemap_items():
    """Extract all item UUIDs from the sitemap."""
    log.info("Fetching sitemap from %s ...", SITEMAP_URL)
    req = Request(SITEMAP_URL, headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        content = resp.read().decode("utf-8")

    # Parse XML
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(content)
    urls = []
    for url_elem in root.findall("sm:url/sm:loc", ns):
        url = url_elem.text
        if "/items/" in url:
            uuid = url.split("/items/")[-1]
            urls.append({"uuid": uuid, "url": url})

    log.info("Found %d item URLs in sitemap", len(urls))
    return urls


def extract_metadata(html):
    """Extract citation and standard metadata from HTML meta tags."""
    meta = {}

    # Extract meta tags: <meta name="..." content="...">
    # Handle both orderings of name/content attributes
    patterns = [
        re.compile(r'<meta\s+name="([^"]+)"\s+content="([^"]*)"', re.IGNORECASE),
        re.compile(r'<meta\s+content="([^"]*)"\s+name="([^"]+)"', re.IGNORECASE),
    ]

    for pattern in patterns:
        for match in pattern.finditer(html):
            if pattern == patterns[0]:
                name, content = match.group(1), match.group(2)
            else:
                content, name = match.group(1), match.group(2)

            name_lower = name.lower()
            if name_lower.startswith("citation_") or name_lower in ("title", "description"):
                if name_lower in meta:
                    # Some fields like citation_author can appear multiple times
                    if isinstance(meta[name_lower], list):
                        meta[name_lower].append(content)
                    else:
                        meta[name_lower] = [meta[name_lower], content]
                else:
                    meta[name_lower] = content

    return meta


def scrape_item(url):
    """Fetch a single item page and extract metadata."""
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        return extract_metadata(html)
    except (HTTPError, URLError, TimeoutError) as e:
        log.warning("Failed to fetch %s: %s", url, e)
        return None


def load_checkpoint():
    """Load scraping checkpoint."""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"completed": [], "last_index": 0}


def save_checkpoint(checkpoint):
    """Save scraping checkpoint."""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f)


def main():
    parser = argparse.ArgumentParser(description="Scrape UW ResearchWorks dissertations")
    parser.add_argument("--max", type=int, default=50, help="Max items to scrape (default: 50)")
    parser.add_argument("--all", action="store_true", help="Scrape all items")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY, help="Delay between requests")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Get all item URLs
    items = fetch_sitemap_items()

    # Determine range
    checkpoint = load_checkpoint() if args.resume else {"completed": set(), "last_index": 0}
    if isinstance(checkpoint.get("completed"), list):
        checkpoint["completed"] = set(checkpoint["completed"])

    start_idx = checkpoint["last_index"] if args.resume else 0
    max_items = len(items) if args.all else min(args.max, len(items))
    end_idx = min(start_idx + max_items, len(items))

    log.info("Scraping items %d to %d (of %d total)", start_idx, end_idx, len(items))

    # Prepare CSV
    csv_fields = ["uuid", "url", "title", "author", "date", "keywords",
                  "language", "description", "handle_url", "pdf_url"]
    file_exists = OUTPUT_CSV.exists() and args.resume
    csvfile = open(OUTPUT_CSV, "a" if file_exists else "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(csvfile, fieldnames=csv_fields)
    if not file_exists:
        writer.writeheader()

    scraped = 0
    errors = 0
    consecutive_errors = 0
    for i in range(start_idx, end_idx):
        item = items[i]
        uuid = item["uuid"]

        if uuid in checkpoint.get("completed", set()):
            continue

        meta = scrape_item(item["url"])
        if meta is None:
            errors += 1
            consecutive_errors += 1
            if consecutive_errors > 50:
                log.error("Too many consecutive errors, stopping.")
                break
            time.sleep(args.delay * 2)
            continue

        consecutive_errors = 0

        # Flatten author list
        author = meta.get("citation_author", "")
        if isinstance(author, list):
            author = "; ".join(author)

        row = {
            "uuid": uuid,
            "url": item["url"],
            "title": meta.get("citation_title", meta.get("title", "")),
            "author": author,
            "date": meta.get("citation_publication_date", ""),
            "keywords": meta.get("citation_keywords", ""),
            "language": meta.get("citation_language", ""),
            "description": (meta.get("description", "") or "")[:500],
            "handle_url": meta.get("citation_abstract_html_url", ""),
            "pdf_url": meta.get("citation_pdf_url", ""),
        }
        writer.writerow(row)
        scraped += 1

        if scraped % 10 == 0:
            log.info("  Scraped %d/%d items (errors: %d)", scraped, end_idx - start_idx, errors)
            csvfile.flush()

        # Update checkpoint
        completed = checkpoint.get("completed", [])
        if isinstance(completed, set):
            completed = list(completed)
        if uuid not in completed:
            completed.append(uuid)
        checkpoint["completed"] = completed
        checkpoint["last_index"] = i + 1
        if scraped % 50 == 0:
            save_checkpoint(checkpoint)

        time.sleep(args.delay)

    csvfile.close()
    save_checkpoint(checkpoint)

    log.info("Done! Scraped %d items (%d errors). Output: %s", scraped, errors, OUTPUT_CSV)


if __name__ == "__main__":
    main()
