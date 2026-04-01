#!/usr/bin/env python3
"""
Concurrent DSpace metadata enrichment using ThreadPoolExecutor.

Fetches dc.degree.discipline, dc.degree.department, dc.degree.level
from DSpace REST APIs with 15 concurrent connections.

Usage:
    python scripts/enrich_concurrent.py --repo ncstate
    python scripts/enrich_concurrent.py --repo rice
    python scripts/enrich_concurrent.py --repo umd
    python scripts/enrich_concurrent.py --repo uw_seattle
"""

import argparse
import csv
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

log = logging.getLogger(__name__)

CONCURRENCY = 15
TIMEOUT = 12

REPOS = {
    "ncstate": {
        "name": "NC State",
        "csv": "data/western_us_dissertations/ncstate_etds.csv",
        "api_base": "https://repository.lib.ncsu.edu/server/api",
        "handle_prefix": "1840",
        "degree_fields": {
            "dept": "dc.degree.discipline",
            "level": "dc.degree.level",
            "name": "dc.degree.name",
        },
    },
    "rice": {
        "name": "Rice",
        "csv": "data/western_us_dissertations/rice_etds.csv",
        "api_base": "https://repository.rice.edu/server/api",
        "handle_prefix": "1911",
        "degree_fields": {
            "dept": "thesis.degree.department",
            "disc": "thesis.degree.discipline",
            "level": "thesis.degree.level",
            "name": "thesis.degree.name",
        },
    },
    "umd": {
        "name": "UMD",
        "csv": "data/western_us_dissertations/umd_etds.csv",
        "api_base": "https://api.drum.lib.umd.edu/server/api",
        "handle_prefix": "1903",
        "degree_fields": {
            "dept": "dc.contributor.department",
        },
    },
    "uw_seattle": {
        "name": "UW Seattle",
        "csv": "data/uw_dissertations/uw_etd_metadata.csv",
        "mode": "uw_scrape",  # Special: SSR scrape, not REST API
    },
}

# UW Seattle collection scrape config
UW_BASE = "https://digital.lib.washington.edu/researchworks"
UW_DELAY = 0.3


def fetch_json(url):
    """Fetch JSON from a URL."""
    try:
        req = Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "ETD-Research/1.0 (academic research)",
        })
        with urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def fetch_html(url):
    """Fetch HTML from a URL."""
    try:
        req = Request(url, headers={"User-Agent": "UW-ETD-Research/1.0 (academic research)"})
        with urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def enrich_one_dspace(args):
    """Enrich a single DSpace record. Returns (row_index, field_updates) or None."""
    row_idx, handle, api_base, degree_fields = args

    # Resolve handle → UUID
    data = fetch_json(f"{api_base}/pid/find?id={handle}")
    if not data or not data.get("uuid"):
        return None

    # Fetch item metadata
    item = fetch_json(f"{api_base}/core/items/{data['uuid']}")
    if not item or "metadata" not in item:
        return None

    meta = item["metadata"]
    updates = {}

    for key, field_name in degree_fields.items():
        vals = meta.get(field_name, [])
        if vals and isinstance(vals[0], dict):
            updates[key] = vals[0].get("value", "")

    if any(updates.values()):
        return (row_idx, updates)
    return None


def scrape_one_uw(args):
    """Scrape a single UW Seattle item page. Returns (uuid, metadata) or None."""
    uuid, dept = args
    url = f"{UW_BASE}/items/{uuid}"
    html = fetch_html(url)
    if not html:
        return None

    def meta(name):
        m = re.search(rf'<meta\s+name="{name}"\s+content="([^"]*)"', html)
        return m.group(1).strip() if m else ""

    author = meta("citation_author")
    if not author:
        return None

    return (uuid, {
        "uuid": uuid,
        "url": url,
        "collection_uuid": "",
        "department": dept,
        "title": meta("citation_title") or meta("title"),
        "author": author,
        "date": meta("citation_publication_date"),
        "keywords": meta("citation_keywords"),
        "description": meta("description"),
        "handle_url": meta("citation_abstract_html_url"),
        "pdf_url": meta("citation_pdf_url"),
    })


def enrich_dspace(config):
    """Enrich a DSpace CSV with concurrent REST API calls."""
    csv_path = config["csv"]
    api_base = config["api_base"]
    handle_prefix = config["handle_prefix"]
    degree_fields = config["degree_fields"]

    # Read CSV
    rows = []
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    # Add enrichment fields
    for field in ["degree_discipline", "degree_department", "degree_level", "degree_name"]:
        if field not in fieldnames:
            fieldnames.append(field)

    # Find records that need enrichment
    tasks = []
    for i, row in enumerate(rows):
        if row.get("degree_discipline") or row.get("degree_department"):
            continue
        # Extract handle from identifier or URL
        handle = None
        for field in ("identifier", "url"):
            m = re.search(rf"({handle_prefix}[\d.]+/\d+)", row.get(field, ""))
            if m:
                handle = m.group(1)
                break
        if handle:
            tasks.append((i, handle, api_base, degree_fields))

    log.info("Records to enrich: %d / %d (already done: %d)",
             len(tasks), len(rows), len(rows) - len(tasks))

    # Process concurrently
    enriched = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {executor.submit(enrich_one_dspace, t): t for t in tasks}
        done = 0
        for future in as_completed(futures):
            done += 1
            result = future.result()
            if result:
                row_idx, updates = result
                field_map = {"dept": "degree_discipline", "disc": "degree_discipline",
                             "level": "degree_level", "name": "degree_name"}
                # Special: Rice has both dept and disc
                if "dept" in updates and updates["dept"]:
                    rows[row_idx]["degree_department"] = updates["dept"]
                if "disc" in updates and updates["disc"]:
                    rows[row_idx]["degree_discipline"] = updates["disc"]
                if "level" in updates:
                    rows[row_idx]["degree_level"] = updates.get("level", "")
                if "name" in updates:
                    rows[row_idx]["degree_name"] = updates.get("name", "")
                enriched += 1

            if done % 500 == 0:
                log.info("  %d/%d done (enriched: %d)", done, len(tasks), enriched)
                # Checkpoint save
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)

    # Final save
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    log.info("Done! Enriched %d / %d records for %s", enriched, len(tasks), config["name"])


def enrich_uw_seattle(config):
    """Concurrent UW Seattle SSR scrape with checkpoint support."""
    csv_path = config["csv"]
    checkpoint_path = "data/uw_dissertations/uw_etd_checkpoint.json"

    # Load checkpoint
    checkpoint = json.loads(open(checkpoint_path).read())
    discovered = checkpoint.get("discovered_items", {})
    completed = set(checkpoint.get("completed_items", []))

    # Find items not yet scraped
    to_scrape = [(uuid, discovered[uuid]) for uuid in discovered if uuid not in completed]
    log.info("UW Seattle: %d items to scrape (%d already done)", len(to_scrape), len(completed))

    if not to_scrape:
        log.info("Nothing to do!")
        return

    # Load existing ETD collection mapping
    # Import from scraper
    import importlib.util
    spec = importlib.util.spec_from_file_location("uw", "scripts/scrape_uw_etd_collections.py")
    uw_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(uw_mod)
    coll_map = uw_mod.ETD_COLLECTIONS

    # Build tasks: (uuid, department_name)
    tasks = []
    for uuid, coll_uuid in to_scrape:
        dept = coll_map.get(coll_uuid, "Unknown")
        tasks.append((uuid, dept))

    # Read existing CSV rows
    csv_fields = ["uuid", "url", "collection_uuid", "department", "title", "author",
                   "date", "keywords", "description", "handle_url", "pdf_url"]
    existing_rows = []
    if os.path.exists(csv_path) and os.path.getsize(csv_path) > 50:
        with open(csv_path, encoding="utf-8") as f:
            existing_rows = list(csv.DictReader(f))

    # Process concurrently
    scraped = 0
    new_rows = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {executor.submit(scrape_one_uw, t): t for t in tasks}
        done = 0
        for future in as_completed(futures):
            done += 1
            result = future.result()
            if result:
                uuid, row_data = result
                new_rows.append(row_data)
                completed.add(uuid)
                scraped += 1
            else:
                # Still mark as completed to avoid retrying broken items
                uuid = tasks[list(futures.values()).index(futures.get(future, tasks[0]))][0] if future in futures else ""
                if uuid:
                    completed.add(uuid)

            if done % 500 == 0:
                log.info("  %d/%d done (scraped: %d)", done, len(tasks), scraped)
                # Checkpoint
                checkpoint["completed_items"] = list(completed)
                with open(checkpoint_path, "w") as f:
                    json.dump(checkpoint, f)
                # Append to CSV
                all_rows = existing_rows + new_rows
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=csv_fields)
                    writer.writeheader()
                    writer.writerows(all_rows)
                existing_rows = all_rows
                new_rows = []

    # Final save
    all_rows = existing_rows + new_rows
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(all_rows)
    checkpoint["completed_items"] = list(completed)
    with open(checkpoint_path, "w") as f:
        json.dump(checkpoint, f)

    log.info("Done! Scraped %d / %d items for UW Seattle", scraped, len(tasks))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, choices=REPOS.keys())
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        datefmt="%H:%M:%S")

    config = REPOS[args.repo]
    log.info("Enriching %s with %d concurrent connections...", config["name"], CONCURRENCY)

    if config.get("mode") == "uw_scrape":
        enrich_uw_seattle(config)
    else:
        enrich_dspace(config)


if __name__ == "__main__":
    main()
