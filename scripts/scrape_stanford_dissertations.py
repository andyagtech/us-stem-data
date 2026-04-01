#!/usr/bin/env python3
"""
Scrape Stanford Digital Repository dissertation metadata via PURL JSON API.

Uses the sitemap to discover all SDR items, fetches Cocina JSON metadata,
and filters for theses/dissertations based on the 'form' genre field.

Usage:
    python scripts/scrape_stanford_dissertations.py --max 100     # test with 100 items
    python scripts/scrape_stanford_dissertations.py --all          # scrape all ~31K items
    python scripts/scrape_stanford_dissertations.py --resume       # resume from checkpoint
"""

import argparse
import csv
import gzip
import json
import logging
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

log = logging.getLogger(__name__)

SITEMAP_URL = "https://purl.stanford.edu/system/sitemap/sitemap.xml.gz"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "stanford_dissertations"
OUTPUT_CSV = OUTPUT_DIR / "stanford_dissertations_metadata.csv"
CHECKPOINT_FILE = OUTPUT_DIR / "scrape_checkpoint.json"

REQUEST_DELAY = 0.3  # Stanford JSON API is fast
REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": "Stanford-Dissertation-Research/1.0 (academic research)",
    "Accept": "application/json",
}

CSV_FIELDS = [
    "druid", "purl", "title", "author", "advisor", "date",
    "genre", "subject", "department", "degree", "description",
]


def fetch_sitemap():
    """Download and parse the Stanford SDR sitemap."""
    log.info("Fetching sitemap from %s ...", SITEMAP_URL)
    req = Request(SITEMAP_URL, headers={"User-Agent": HEADERS["User-Agent"]})
    with urlopen(req, timeout=30) as resp:
        data = resp.read()

    # Decompress if gzipped
    try:
        data = gzip.decompress(data)
    except gzip.BadGzipFile:
        pass

    content = data.decode("utf-8")
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(content)

    druids = []
    for url_elem in root.findall(".//sm:url/sm:loc", ns):
        url = url_elem.text.strip()
        druid = url.rstrip("/").split("/")[-1]
        if druid and len(druid) == 11:  # Stanford druids are 11 chars
            druids.append(druid)

    log.info("Found %d PURL items in sitemap", len(druids))
    return druids


def extract_name(name_obj):
    """Extract a human-readable name from Cocina name structure."""
    if not name_obj:
        return ""

    if isinstance(name_obj, list):
        names = []
        for n in name_obj:
            names.append(extract_name(n))
        return "; ".join(filter(None, names))

    # Direct value
    if name_obj.get("value"):
        return name_obj["value"]

    # Structured value (forename + surname)
    structured = name_obj.get("structuredValue", [])
    if structured:
        parts = {}
        for part in structured:
            ptype = part.get("type", "")
            pval = part.get("value", "")
            if ptype and pval:
                parts[ptype] = pval
        if "surname" in parts:
            forename = parts.get("forename", "")
            return f"{parts['surname']}, {forename}".strip(", ")
        return " ".join(p.get("value", "") for p in structured if p.get("value"))

    return ""


def parse_cocina_json(data, druid):
    """Parse Cocina JSON and extract dissertation metadata."""
    desc = data.get("description", {})

    # Title
    titles = desc.get("title", [])
    title = titles[0].get("value", "") if titles else data.get("label", "")

    # Contributors — separate authors from advisors
    contributors = desc.get("contributor", [])
    authors = []
    advisors = []
    department = ""

    for contrib in contributors:
        name = extract_name(contrib.get("name", []))
        ctype = contrib.get("type", "")
        roles = contrib.get("role", [])
        role_values = [r.get("value", "") for r in roles]

        if ctype == "organization":
            if "department" in name.lower() or "program" in name.lower():
                department = name
            continue

        if "advisor" in role_values or "degree supervisor" in role_values:
            advisors.append(name)
        elif "author" in role_values or contrib.get("status") == "primary":
            authors.append(name)
        else:
            authors.append(name)

    # Genre/form — check if it's a thesis/dissertation
    forms = desc.get("form", [])
    genre = ""
    for form in forms:
        # Check structured forms
        for sv in form.get("structuredValue", []):
            if sv.get("type") == "subtype":
                genre = sv.get("value", "")
        # Check direct value
        if form.get("type") == "genre":
            genre = form.get("value", "")
        if not genre and form.get("value") and "thesis" in form.get("value", "").lower():
            genre = form.get("value", "")

    # Date
    events = desc.get("event", [])
    date = ""
    for event in events:
        for d in event.get("date", []):
            if d.get("value"):
                date = d["value"]
                break
        if date:
            break

    # Subject
    subjects = desc.get("subject", [])
    subject_list = []
    for s in subjects:
        if s.get("value"):
            subject_list.append(s["value"])
        for sv in s.get("structuredValue", []):
            if sv.get("value"):
                subject_list.append(sv["value"])

    # Notes (abstract)
    notes = desc.get("note", [])
    abstract = ""
    degree = ""
    for note in notes:
        if note.get("type") == "abstract":
            abstract = (note.get("value", "") or "")[:500]
        elif note.get("type") == "thesis" or "degree" in note.get("type", ""):
            degree = note.get("value", "")

    return {
        "druid": druid,
        "purl": f"https://purl.stanford.edu/{druid}",
        "title": title,
        "author": "; ".join(authors),
        "advisor": "; ".join(advisors),
        "date": date,
        "genre": genre,
        "subject": "; ".join(subject_list),
        "department": department,
        "degree": degree,
        "description": abstract,
    }


def fetch_item(druid, retries=2):
    """Fetch Cocina JSON for a single item."""
    url = f"https://purl.stanford.edu/{druid}.json"
    for attempt in range(retries):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                log.debug("Failed to fetch %s: %s", druid, e)
    return None


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"last_index": 0, "total_items": 0, "thesis_count": 0}


def save_checkpoint(checkpoint):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Scrape Stanford SDR dissertation metadata")
    parser.add_argument("--max", type=int, default=100, help="Max items to check (default: 100)")
    parser.add_argument("--all", action="store_true", help="Check all items")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY)
    parser.add_argument("--include-all", action="store_true",
                        help="Save all items, not just theses/dissertations")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    druids = fetch_sitemap()
    checkpoint = load_checkpoint() if args.resume else {"last_index": 0, "total_items": 0, "thesis_count": 0}

    start_idx = checkpoint["last_index"] if args.resume else 0
    max_items = len(druids) if args.all else min(args.max, len(druids))
    end_idx = min(start_idx + max_items, len(druids))

    log.info("Checking items %d to %d (of %d total)", start_idx, end_idx, len(druids))

    # Thesis detection keywords
    thesis_keywords = {"thesis", "dissertation", "theses"}

    file_exists = OUTPUT_CSV.exists() and args.resume
    csvfile = open(OUTPUT_CSV, "a" if file_exists else "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
    if not file_exists:
        writer.writeheader()

    checked = 0
    saved = 0
    errors = 0

    for i in range(start_idx, end_idx):
        druid = druids[i]
        data = fetch_item(druid)
        checked += 1

        if data is None:
            errors += 1
            if errors > 50:
                log.error("Too many errors, stopping.")
                break
            continue

        row = parse_cocina_json(data, druid)

        # Filter for theses/dissertations unless --include-all
        is_thesis = False
        genre_lower = row["genre"].lower()
        title_lower = row["title"].lower()
        degree_lower = row["degree"].lower()

        if any(kw in genre_lower for kw in thesis_keywords):
            is_thesis = True
        elif any(kw in degree_lower for kw in thesis_keywords):
            is_thesis = True
        elif "ph.d" in degree_lower or "ph.d" in title_lower:
            is_thesis = True

        if is_thesis or args.include_all:
            writer.writerow(row)
            saved += 1

        if checked % 50 == 0:
            log.info("  Checked %d/%d, saved %d theses (errors: %d)",
                     checked, end_idx - start_idx, saved, errors)
            csvfile.flush()
            checkpoint["last_index"] = i + 1
            checkpoint["total_items"] = checked
            checkpoint["thesis_count"] = saved
            save_checkpoint(checkpoint)

        time.sleep(args.delay)

    csvfile.close()
    checkpoint["last_index"] = end_idx
    checkpoint["total_items"] = checked
    checkpoint["thesis_count"] = saved
    save_checkpoint(checkpoint)

    log.info("Done! Checked %d items, saved %d theses (%d errors). Output: %s",
             checked, saved, errors, OUTPUT_CSV)


if __name__ == "__main__":
    main()
