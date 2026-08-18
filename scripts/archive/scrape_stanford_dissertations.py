#!/usr/bin/env python3
"""
Scrape Stanford Digital Repository dissertation metadata via PURL JSON API.

Uses the sitemap to discover all SDR items, fetches Cocina JSON metadata,
and filters for theses/dissertations based on the 'form' genre field.

Usage:
    python scripts/archive/scrape_stanford_dissertations.py --max 100   # test with 100 items
    python scripts/archive/scrape_stanford_dissertations.py --all        # all SDR items
    python scripts/archive/scrape_stanford_dissertations.py --resume     # resume

Append-only refresh (the only mode that should be used against the existing
snapshot). Skips every druid already checked in a previous run, appends only
newly discovered theses, and never rewrites an existing row:

    python scripts/archive/scrape_stanford_dissertations.py --all --append --workers 4

SDR exposes no usable date filter — the sitemap's <lastmod> is bulk-refreshed
(75k of 82k items were restamped in a single month), and there is no OAI-PMH
endpoint — so a refresh is a full sweep with druid-level dedup. --workers runs
that sweep with a small thread pool; writes stay serialised behind a lock.
"""

import argparse
import csv
import gzip
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

log = logging.getLogger(__name__)

SITEMAP_URL = "https://purl.stanford.edu/system/sitemap/sitemap.xml.gz"
# This script now lives in scripts/archive/, so the repo root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "data" / "stanford_dissertations"
OUTPUT_CSV = OUTPUT_DIR / "stanford_dissertations_metadata.csv"
CHECKPOINT_FILE = OUTPUT_DIR / "scrape_checkpoint.json"
# SQLite checkpoint for --append: records every druid we have *checked*, not
# just the theses we kept, so a re-run never re-fetches a known non-thesis.
APPEND_DB = OUTPUT_DIR / "refresh_checkpoint.db"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from scrape_checkpoint import CheckpointDB  # noqa: E402

REQUEST_DELAY = 0.3  # Stanford JSON API is fast
REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": "Stanford-Dissertation-Research/1.0 (academic research)",
    "Accept": "application/json",
}

# degree_type is a trailing column in the historical CSV, populated by later
# enrichment rather than by this harvester. It must stay in the field list so
# appended rows line up with the existing 12-column header.
CSV_FIELDS = [
    "druid", "purl", "title", "author", "advisor", "date",
    "genre", "subject", "department", "degree", "description", "degree_type",
]


def _get_sitemap(url):
    """Fetch one sitemap document, transparently gunzipping it."""
    req = Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
    with urlopen(req, timeout=60) as resp:
        data = resp.read()
    try:
        data = gzip.decompress(data)
    except (gzip.BadGzipFile, OSError):
        pass
    return data.decode("utf-8")


def fetch_sitemap():
    """Download and parse the Stanford SDR sitemap.

    As of 2026 the top-level document is a <sitemapindex> pointing at
    sitemap1.xml.gz / sitemap2.xml.gz, so the child sitemaps must be followed.
    Entries come back in descending <lastmod> order and that order is preserved,
    which puts the most recently touched items first.
    """
    log.info("Fetching sitemap from %s ...", SITEMAP_URL)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    content = _get_sitemap(SITEMAP_URL)
    root = ET.fromstring(content)

    children = [e.text.strip() for e in root.findall(".//sm:sitemap/sm:loc", ns) if e.text]
    docs = []
    if children:
        log.info("  sitemap index with %d child sitemaps", len(children))
        for child in children:
            log.info("  fetching %s", child)
            docs.append(_get_sitemap(child))
    else:
        docs.append(content)

    druids = []
    for doc in docs:
        child_root = ET.fromstring(doc)
        for url_elem in child_root.findall(".//sm:url/sm:loc", ns):
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
        "degree_type": "",
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
    parser.add_argument("--append", action="store_true",
                        help="Append-only refresh: never truncate the CSV, skip already-checked druids")
    parser.add_argument("--workers", type=int, default=1,
                        help="Concurrent fetches in --append mode (default 1)")
    parser.add_argument("--reverse", action="store_true",
                        help="Walk the sitemap from the end. Theses cluster in the tail "
                             "(2025-26 dissertations sit around index 78k-82k of 82.5k), "
                             "so this reaches the recent ETDs first")
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

    if args.append:
        return refresh_append(args)

    druids = fetch_sitemap()
    checkpoint = load_checkpoint() if args.resume else {"last_index": 0, "total_items": 0, "thesis_count": 0}

    start_idx = checkpoint["last_index"] if args.resume else 0
    max_items = len(druids) if args.all else min(args.max, len(druids))
    end_idx = min(start_idx + max_items, len(druids))

    log.info("Checking items %d to %d (of %d total)", start_idx, end_idx, len(druids))

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

        if is_thesis(row) or args.include_all:
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


def is_thesis(row):
    """Decide whether a parsed SDR row is a thesis/dissertation."""
    thesis_keywords = {"thesis", "dissertation", "theses"}
    genre_lower = row["genre"].lower()
    title_lower = row["title"].lower()
    degree_lower = row["degree"].lower()
    if any(kw in genre_lower for kw in thesis_keywords):
        return True
    if any(kw in degree_lower for kw in thesis_keywords):
        return True
    if "ph.d" in degree_lower or "ph.d" in title_lower:
        return True
    return False


def refresh_append(args):
    """Append-only refresh: sweep the sitemap, skip known druids, append theses."""
    if not OUTPUT_CSV.exists():
        log.error("--append requires an existing %s", OUTPUT_CSV)
        sys.exit(1)

    db = CheckpointDB(APPEND_DB)

    # Seed once from the druids already in the CSV. Those are theses only, so a
    # first --append run still has to look at every non-thesis SDR item once;
    # from then on every checked druid is remembered.
    if not db.get_state("seeded_from_csv"):
        log.info("Seeding dedup checkpoint from %s ...", OUTPUT_CSV)
        csv.field_size_limit(10_000_000)
        batch = []
        with open(OUTPUT_CSV, encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                d = (row.get("druid") or "").strip()
                if d:
                    batch.append(d)
                if len(batch) >= 5000:
                    db.mark_done_batch(batch)
                    batch = []
        if batch:
            db.mark_done_batch(batch)
        db.set_state("seeded_from_csv", "1")
        log.info("  seeded %d known druids", db.count_done())

    # Guard the header: appended rows must line up with what is on disk.
    with open(OUTPUT_CSV, encoding="utf-8", errors="replace") as f:
        header = next(csv.reader(f), None)
    if header != CSV_FIELDS:
        log.error("Header mismatch\n  on disk: %s\n  expected: %s", header, CSV_FIELDS)
        sys.exit(1)

    druids = fetch_sitemap()
    if args.reverse:
        druids = list(reversed(druids))
    todo = [d for d in druids if not db.is_done(d)]
    if not args.all:
        todo = todo[:args.max]
    log.info("%d druids not yet checked; fetching %d", len(druids) - db.count_done(), len(todo))

    csvfile = open(OUTPUT_CSV, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
    state = {"checked": 0, "saved": 0, "errors": 0}

    def fetch_one(druid):
        """Worker: network only. SQLite and the CSV are touched by the caller,
        since a sqlite3 connection may only be used from its creating thread."""
        data = fetch_item(druid)
        time.sleep(args.delay)
        return druid, data

    def consume(result):
        druid, data = result
        state["checked"] += 1
        if data is None:
            state["errors"] += 1
        else:
            row = parse_cocina_json(data, druid)
            if is_thesis(row) or args.include_all:
                writer.writerow(row)
                csvfile.flush()
                state["saved"] += 1
            # Marked only on a successful fetch, so transient failures are
            # retried by the next run.
            db.mark_done(druid)
        if state["checked"] % 500 == 0:
            log.info("  checked %d/%d — appended %d theses (%d fetch errors)",
                     state["checked"], len(todo), state["saved"], state["errors"])

    try:
        if args.workers > 1:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for result in pool.map(fetch_one, todo):
                    consume(result)
        else:
            for druid in todo:
                consume(fetch_one(druid))
    except KeyboardInterrupt:
        log.warning("Interrupted — progress is checkpointed, re-run to continue")
    finally:
        csvfile.close()
        log.info("=" * 60)
        log.info("Done! Checked %d items, appended %d theses (%d fetch errors). Output: %s",
                 state["checked"], state["saved"], state["errors"], OUTPUT_CSV)
        db.close()


if __name__ == "__main__":
    main()
