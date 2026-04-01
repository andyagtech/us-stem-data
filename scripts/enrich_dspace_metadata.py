#!/usr/bin/env python3
"""
Enrich DSpace ETD metadata with department/degree info from the REST API.

Some DSpace 7 repositories expose their REST API even when OAI-PMH is restricted.
This script fetches dc.degree.discipline, dc.degree.level, dc.degree.name for
each record that lacks department info.

Usage:
    python scripts/enrich_dspace_metadata.py --repo ncstate
    python scripts/enrich_dspace_metadata.py --repo penn_state
"""

import argparse
import csv
import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

log = logging.getLogger(__name__)

REPOS = {
    "ncstate": {
        "name": "NC State",
        "csv": "data/western_us_dissertations/ncstate_etds.csv",
        "api_base": "https://repository.lib.ncsu.edu/server/api/core/items",
        "url_pattern": r"1840\.\d+/(\d+)",  # extract handle from URL
        "handle_to_uuid": True,  # need to resolve handle -> UUID first
        "handle_api": "https://repository.lib.ncsu.edu/server/api/pid/find?id=",
    },
    "penn_state": {
        "name": "Penn State",
        "csv": "data/western_us_dissertations/penn_state_etds.csv",
        "api_base": None,  # Penn State uses Blacklight, different approach
        "web_scrape": True,
        "url_field": "url",
    },
}

DELAY = 0.5
HEADERS = {"User-Agent": "ETD-Research/1.0 (academic research)", "Accept": "application/json"}


def fetch_json(url):
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.debug("Failed to fetch %s: %s", url, e)
        return None


def fetch_html(url):
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (academic research)"})
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        log.debug("Failed to fetch %s: %s", url, e)
        return None


def enrich_ncstate(config):
    csv_path = config["csv"]
    api_base = config["api_base"]

    # Read existing CSV
    rows = []
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Add new fields if not present
    for field in ["degree_discipline", "degree_level", "degree_name"]:
        if field not in fieldnames:
            fieldnames.append(field)

    # Track which ones already have data
    need_enrichment = []
    for i, row in enumerate(rows):
        if row.get("degree_discipline"):
            continue
        # Extract handle from URL
        url = row.get("url", "")
        handle_match = re.search(r"1840[.\d]+/(\d+)", url)
        if not handle_match:
            handle_match = re.search(r"resolver/(1840[.\d]+/\d+)", url)
        if handle_match:
            need_enrichment.append((i, handle_match.group(0) if "/" in handle_match.group(0) else f"1840.20/{handle_match.group(1)}"))

    log.info("Need enrichment: %d / %d records", len(need_enrichment), len(rows))

    # Also try extracting UUID from the OAI identifier
    for i, row in enumerate(rows):
        if row.get("degree_discipline"):
            continue
        ident = row.get("identifier", "")
        # oai:repository.lib.ncsu.edu:1840.16/8213
        handle_match = re.search(r"(1840\.\d+/\d+)", ident)
        if handle_match:
            handle = handle_match.group(1)
            found = False
            for j, h in need_enrichment:
                if j == i:
                    found = True
                    break
            if not found:
                need_enrichment.append((i, handle))

    need_enrichment = list(dict(need_enrichment).items())  # deduplicate by row index
    log.info("Total to enrich: %d", len(need_enrichment))

    enriched = 0
    for idx, (row_idx, handle) in enumerate(need_enrichment):
        # Resolve handle to UUID via API
        resolve_url = f"https://repository.lib.ncsu.edu/server/api/pid/find?id={handle}"
        data = fetch_json(resolve_url)

        if data and data.get("uuid"):
            uuid = data["uuid"]
            # Fetch full metadata
            item_url = f"{api_base}/{uuid}"
            item_data = fetch_json(item_url)

            if item_data and "metadata" in item_data:
                meta = item_data["metadata"]
                disc = meta.get("dc.degree.discipline", [{}])
                level = meta.get("dc.degree.level", [{}])
                name = meta.get("dc.degree.name", [{}])

                rows[row_idx]["degree_discipline"] = disc[0].get("value", "") if disc else ""
                rows[row_idx]["degree_level"] = level[0].get("value", "") if level else ""
                rows[row_idx]["degree_name"] = name[0].get("value", "") if name else ""

                if rows[row_idx]["degree_discipline"]:
                    enriched += 1

        if (idx + 1) % 100 == 0:
            log.info("  Processed %d/%d (enriched: %d)", idx + 1, len(need_enrichment), enriched)
            # Write progress
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

        time.sleep(DELAY)

    # Final write
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    log.info("Done! Enriched %d / %d records", enriched, len(need_enrichment))


def enrich_penn_state(config):
    """Penn State uses Blacklight — scrape the web page for Graduate Program field."""
    csv_path = config["csv"]

    rows = []
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    for field in ["degree_discipline", "degree_level"]:
        if field not in fieldnames:
            fieldnames.append(field)

    need_enrichment = [(i, row) for i, row in enumerate(rows) if not row.get("degree_discipline")]
    log.info("Need enrichment: %d / %d records", len(need_enrichment), len(rows))

    enriched = 0
    for idx, (row_idx, row) in enumerate(need_enrichment):
        url = row.get("url", "")
        if not url:
            continue

        html = fetch_html(url)
        if html:
            # Look for Graduate Program field
            program = re.search(r"Graduate Program[^<]*</[^>]+>\s*<[^>]+>([^<]+)", html)
            if not program:
                program = re.search(r"program[\":]([^\"<]+)", html, re.I)

            degree = re.search(r"Degree Type[^<]*</[^>]+>\s*<[^>]+>([^<]+)", html)

            if program:
                rows[row_idx]["degree_discipline"] = program.group(1).strip()
                enriched += 1
            if degree:
                rows[row_idx]["degree_level"] = degree.group(1).strip()

        if (idx + 1) % 100 == 0:
            log.info("  Processed %d/%d (enriched: %d)", idx + 1, len(need_enrichment), enriched)
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

        time.sleep(DELAY)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    log.info("Done! Enriched %d / %d records", enriched, len(need_enrichment))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, choices=REPOS.keys())
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    config = REPOS[args.repo]
    log.info("Enriching %s...", config["name"])

    if args.repo == "ncstate":
        enrich_ncstate(config)
    elif args.repo == "penn_state":
        enrich_penn_state(config)


if __name__ == "__main__":
    main()
