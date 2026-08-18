#!/usr/bin/env python3
"""
Harvest UC dissertation/thesis metadata from eScholarship via OAI-PMH.

Each UC campus has an ETD (Electronic Theses & Dissertations) set.
The OAI-PMH endpoint returns 500 records per page with resumptionToken pagination.

Usage:
    python scripts/archive/scrape_escholarship.py                       # all campuses (full harvest)
    python scripts/archive/scrape_escholarship.py --campus ucb_etd      # single campus
    python scripts/archive/scrape_escholarship.py --resume              # resume from checkpoint

Incremental refresh (append-only, deduped against the existing CSV):

    python scripts/archive/scrape_escholarship.py --from 2026-02-01 --append

--append never truncates the output CSV. Every identifier already present in
the CSV (or already written by a previous --append run) is skipped via the
shared SQLite checkpoint in scrape_checkpoint.py.
"""

import argparse
import csv
import json
import logging
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

log = logging.getLogger(__name__)

OAI_BASE = "https://escholarship.org/oai"
# This script now lives in scripts/archive/, so the repo root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "data" / "uc_dissertations"
OUTPUT_CSV = OUTPUT_DIR / "uc_dissertations_metadata.csv"
CHECKPOINT_FILE = OUTPUT_DIR / "scrape_checkpoint.json"
# SQLite checkpoint used by --append (identifier-level dedup, crash safe)
APPEND_DB = OUTPUT_DIR / "refresh_checkpoint.db"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from scrape_checkpoint import CheckpointDB  # noqa: E402

# UC campus ETD sets (verified working)
UC_CAMPUS_SETS = {
    "ucb_etd": "UC Berkeley",
    "ucd_etd": "UC Davis",
    "uci_etd": "UC Irvine",
    "ucla_etd": "UCLA",
    "ucm_etd": "UC Merced",
    "ucr_etd": "UC Riverside",
    "ucsb_etd": "UC Santa Barbara",
    "ucsc_etd": "UC Santa Cruz",
    "ucsd_etd": "UC San Diego",
    "ucsf_etd": "UC San Francisco",
}

# OAI-PMH XML namespaces
NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}

REQUEST_DELAY = 1.0  # seconds between OAI requests (be polite)
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": "UC-Dissertation-Research/1.0 (academic research)",
}

# NOTE: degree_type is a trailing column present in the historical CSV. It is
# populated by later enrichment, not by this harvester, but it must stay in the
# field list so appended rows line up with the existing header.
CSV_FIELDS = [
    "campus_set", "campus_name", "identifier", "title", "creator",
    "contributor", "date", "subject", "description", "type",
    "language", "rights", "escholarship_url", "pdf_url", "degree_type",
]


def fetch_oai_page(url, retries=3):
    """Fetch a single OAI-PMH page with retries."""
    for attempt in range(retries):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return resp.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as e:
            log.warning("Attempt %d failed for %s: %s", attempt + 1, url[:100], e)
            if attempt < retries - 1:
                time.sleep(REQUEST_DELAY * (attempt + 1))
    return None


def parse_records(xml_content, campus_set, campus_name):
    """Parse OAI-PMH XML and extract DC metadata records."""
    root = ET.fromstring(xml_content)

    records = []
    for record in root.findall(".//oai:record", NS):
        # Skip deleted records
        header = record.find("oai:header", NS)
        if header is not None and header.get("status") == "deleted":
            continue

        metadata = record.find("oai:metadata/oai_dc:dc", NS)
        if metadata is None:
            continue

        def get_text(tag):
            elem = metadata.find(f"dc:{tag}", NS)
            return elem.text.strip() if elem is not None and elem.text else ""

        def get_all_text(tag):
            elems = metadata.findall(f"dc:{tag}", NS)
            return "; ".join(e.text.strip() for e in elems if e.text)

        # Extract identifiers — find escholarship URL and PDF URL
        identifiers = [e.text.strip() for e in metadata.findall("dc:identifier", NS) if e.text]
        escholarship_url = ""
        pdf_url = ""
        item_id = ""
        for ident in identifiers:
            if "escholarship.org/uc/item/" in ident:
                escholarship_url = ident
            elif ident.endswith(".pdf"):
                pdf_url = ident
            elif len(ident) < 20 and not ident.startswith("http"):
                item_id = ident

        row = {
            "campus_set": campus_set,
            "campus_name": campus_name,
            "identifier": item_id or (identifiers[0] if identifiers else ""),
            "title": get_text("title"),
            "creator": get_all_text("creator"),
            "contributor": get_all_text("contributor"),
            "date": get_text("date"),
            "subject": get_all_text("subject"),
            "description": (get_text("description") or "")[:500],
            "type": get_text("type"),
            "language": get_text("language"),
            "rights": get_text("rights"),
            "escholarship_url": escholarship_url,
            "pdf_url": pdf_url,
            "degree_type": "",
        }
        records.append(row)

    # Get resumptionToken
    token_elem = root.find(".//oai:resumptionToken", NS)
    resumption_token = None
    total_size = None
    if token_elem is not None:
        resumption_token = token_elem.text.strip() if token_elem.text else None
        total_size = token_elem.get("completeListSize")

    return records, resumption_token, total_size


def harvest_campus(campus_set, campus_name, writer, checkpoint, delay=1.0,
                   from_date=None, seen=None):
    """Harvest records for a single campus ETD set.

    from_date — OAI-PMH selective harvesting: only records with a datestamp on
    or after this date (YYYY-MM-DD) are returned by the server.
    seen — optional CheckpointDB; identifiers already in it are skipped and
    newly written identifiers are recorded, making the run append-only and
    resumable without ever re-writing an existing row.
    """
    log.info("Starting harvest: %s (%s)%s", campus_name, campus_set,
             f" from {from_date}" if from_date else "")

    # Check if we have a resumption token from a previous run
    token = checkpoint.get("tokens", {}).get(campus_set)
    if token:
        url = f"{OAI_BASE}?verb=ListRecords&resumptionToken={token}"
        log.info("  Resuming from checkpoint token")
    else:
        url = f"{OAI_BASE}?verb=ListRecords&metadataPrefix=oai_dc&set={campus_set}"
        if from_date:
            url += f"&from={from_date}"

    total_records = 0
    skipped = 0
    page = 0

    while url:
        page += 1
        content = fetch_oai_page(url)
        if content is None:
            log.error("  Failed to fetch page %d, stopping campus %s", page, campus_set)
            break

        # Check for OAI errors
        if "noRecordsMatch" in content:
            log.info("  No records found for %s", campus_set)
            break

        records, resumption_token, total_size = parse_records(content, campus_set, campus_name)

        new_ids = []
        for row in records:
            ident = row["identifier"]
            if seen is not None and (not ident or seen.is_done(ident)):
                skipped += 1
                continue
            writer.writerow(row)
            total_records += 1
            if ident:
                new_ids.append(ident)
        if seen is not None and new_ids:
            seen.mark_done_batch(new_ids)

        if page == 1 and total_size:
            log.info("  Total records available: %s", total_size)

        log.info("  Page %d: %d fetched, %d new (total new: %d, skipped dupes: %d)",
                 page, len(records), len(records) - (len(records) - len(new_ids)) if seen is not None else len(records),
                 total_records, skipped)

        # Save checkpoint
        if resumption_token:
            checkpoint.setdefault("tokens", {})[campus_set] = resumption_token
            save_checkpoint(checkpoint)
            url = f"{OAI_BASE}?verb=ListRecords&resumptionToken={resumption_token}"
        else:
            # Done with this campus
            checkpoint.setdefault("tokens", {})[campus_set] = None
            checkpoint.setdefault("completed_campuses", [])
            if campus_set not in checkpoint["completed_campuses"]:
                checkpoint["completed_campuses"].append(campus_set)
            save_checkpoint(checkpoint)
            url = None

        time.sleep(delay)

    log.info("  Finished %s: %d new records appended (%d duplicates skipped)",
             campus_name, total_records, skipped)
    return total_records


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"completed_campuses": [], "tokens": {}}


def save_checkpoint(checkpoint):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Harvest UC eScholarship ETD metadata via OAI-PMH")
    parser.add_argument("--campus", type=str, help="Single campus set ID (e.g., ucb_etd)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY, help="Delay between requests (default: 1.0s)")
    parser.add_argument("--from", dest="from_date", type=str, default=None,
                        help="OAI selective harvest: only records with a datestamp >= this date (YYYY-MM-DD)")
    parser.add_argument("--append", action="store_true",
                        help="Append-only refresh: never truncate the CSV, skip identifiers already present")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    request_delay = args.delay

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    checkpoint = load_checkpoint() if args.resume else {"completed_campuses": [], "tokens": {}}

    # --append mode: identifier-level dedup via the shared SQLite checkpoint.
    # The DB is seeded once from the identifiers already in the CSV so that a
    # refresh can never duplicate a historical row.
    seen = None
    if args.append:
        seen = CheckpointDB(APPEND_DB)
        if not seen.get_state("seeded_from_csv") and OUTPUT_CSV.exists():
            log.info("Seeding dedup checkpoint from %s ...", OUTPUT_CSV)
            csv.field_size_limit(10_000_000)
            with open(OUTPUT_CSV, encoding="utf-8", errors="replace") as f:
                batch = []
                for row in csv.DictReader(f):
                    ident = (row.get("identifier") or "").strip()
                    if ident:
                        batch.append(ident)
                    if len(batch) >= 5000:
                        seen.mark_done_batch(batch)
                        batch = []
                if batch:
                    seen.mark_done_batch(batch)
            seen.set_state("seeded_from_csv", "1")
            log.info("  Seeded %d existing identifiers", seen.count_done())
        # A refresh must not reuse stale per-campus resumption tokens from an
        # unrelated full harvest.
        checkpoint = {"completed_campuses": [], "tokens": {}}

    # Determine which campuses to harvest
    if args.campus:
        if args.campus not in UC_CAMPUS_SETS:
            log.error("Unknown campus set: %s. Available: %s", args.campus, list(UC_CAMPUS_SETS.keys()))
            sys.exit(1)
        campuses = {args.campus: UC_CAMPUS_SETS[args.campus]}
    else:
        campuses = UC_CAMPUS_SETS

    # Open CSV — --append never truncates an existing snapshot
    file_exists = OUTPUT_CSV.exists() and (args.resume or args.append)
    if args.append and not OUTPUT_CSV.exists():
        log.error("--append requires an existing %s", OUTPUT_CSV)
        sys.exit(1)
    csvfile = open(OUTPUT_CSV, "a" if file_exists else "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
    if not file_exists:
        writer.writeheader()

    grand_total = 0
    for campus_set, campus_name in campuses.items():
        if campus_set in checkpoint.get("completed_campuses", []) and args.resume:
            log.info("Skipping %s (%s) — already completed", campus_name, campus_set)
            continue

        try:
            count = harvest_campus(campus_set, campus_name, writer, checkpoint,
                                   delay=request_delay, from_date=args.from_date,
                                   seen=seen)
            grand_total += count
            csvfile.flush()
        except Exception as e:
            log.error("Error harvesting %s: %s", campus_set, e)
            continue

    csvfile.close()
    if not args.append:
        save_checkpoint(checkpoint)
    if seen is not None:
        seen.close()

    log.info("=" * 60)
    log.info("Done! Total records harvested: %d", grand_total)
    log.info("Output: %s", OUTPUT_CSV)


if __name__ == "__main__":
    main()
