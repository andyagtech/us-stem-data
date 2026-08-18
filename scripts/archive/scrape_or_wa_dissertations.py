#!/usr/bin/env python3
"""
Scrape dissertation metadata from Oregon and Washington university repositories.

Supports:
  - U. Oregon Scholars' Bank (DSpace 8.1, sitemap + SSR meta tags)
  - WSU Research Exchange (Esploro, sitemap + SSR meta tags with Googlebot UA)
  - Oregon State ScholarsArchive (blocked by bot detection — not currently supported)

Usage:
    python scripts/archive/scrape_or_wa_dissertations.py --repo uoregon --max 100
    python scripts/archive/scrape_or_wa_dissertations.py --repo wsu --all
    python scripts/archive/scrape_or_wa_dissertations.py --repo uoregon --all --resume

Append-only refresh (the mode to use against an existing snapshot). Walks the
whole sitemap but fetches only items whose id is not already in the CSV, and
appends without ever rewriting an existing row:

    python scripts/archive/scrape_or_wa_dissertations.py --repo wsu --all --append

--resume's index-based checkpoint is not safe for a refresh: the sitemap is
re-ordered between runs, so "carry on at item N" silently skips new items.
--append keys off the item id instead.
"""

import argparse
import csv
import gzip
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

# This script now lives in scripts/archive/, so the repo root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_BASE = REPO_ROOT / "data" / "or_wa_dissertations"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from scrape_checkpoint import CheckpointDB  # noqa: E402

# Repository configurations
REPOS = {
    "uoregon": {
        "name": "University of Oregon",
        "sitemap_url": "https://scholarsbank.uoregon.edu/sitemap0.xml",
        "user_agent": "UO-Dissertation-Research/1.0 (academic research)",
        "url_filter": lambda u: "/items/" in u,
        "url_id": lambda u: u.split("/items/")[-1],
        "delay": 0.5,
        "output_csv": "uoregon_dissertations.csv",
        "checkpoint": "uoregon_checkpoint.json",
    },
    "wsu": {
        "name": "Washington State University",
        "sitemap_urls": [
            f"https://rex.libraries.wsu.edu/view/google/ResearchAsset/sitemap?map={i}"
            for i in range(1, 6)
        ],
        "user_agent": "Googlebot/2.1 (+http://www.google.com/bot.html)",
        "url_filter": lambda u: "/outputs/doctoral/" in u or "/outputs/graduate/" in u,
        "url_id": lambda u: u.rstrip("/").split("/")[-1],
        "delay": 1.0,
        "output_csv": "wsu_dissertations.csv",
        "checkpoint": "wsu_checkpoint.json",
    },
}

CSV_FIELDS = [
    "id", "url", "repo", "title", "author", "date", "keywords",
    "language", "description", "institution", "doi", "pdf_url", "type",
]


def fetch_sitemap_urls(repo_config):
    """Fetch item URLs from sitemap(s)."""
    headers = {"User-Agent": repo_config["user_agent"]}
    all_items = []

    sitemap_urls = repo_config.get("sitemap_urls", [repo_config.get("sitemap_url")])

    for sitemap_url in sitemap_urls:
        log.info("Fetching sitemap: %s", sitemap_url)
        req = Request(sitemap_url, headers=headers)
        try:
            with urlopen(req, timeout=30) as resp:
                data = resp.read()
        except Exception as e:
            log.error("Failed to fetch sitemap %s: %s", sitemap_url, e)
            continue

        # Try gzip decompression
        try:
            data = gzip.decompress(data)
        except (gzip.BadGzipFile, OSError):
            pass

        content = data.decode("utf-8")
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        root = ET.fromstring(content)

        url_filter = repo_config["url_filter"]
        url_id = repo_config["url_id"]

        for url_elem in root.findall(".//sm:url/sm:loc", ns):
            url = url_elem.text.strip()
            if url_filter(url):
                all_items.append({"id": url_id(url), "url": url})

    log.info("Found %d item URLs across %d sitemap(s)", len(all_items), len(sitemap_urls))
    return all_items


def extract_metadata(html):
    """Extract citation and standard metadata from SSR HTML meta tags."""
    meta = {}

    patterns = [
        re.compile(r'<meta\s+name="([^"]+)"\s+content="([^"]*)"', re.IGNORECASE),
        re.compile(r'<meta\s+content="([^"]*)"\s+name="([^"]+)"', re.IGNORECASE),
        re.compile(r"<meta\s+name='([^']+)'\s+content='([^']*)'", re.IGNORECASE),
        re.compile(r'<meta\s+property="([^"]+)"\s+content="([^"]*)"', re.IGNORECASE),
    ]

    for pattern in patterns:
        for match in pattern.finditer(html):
            if pattern in (patterns[0], patterns[2], patterns[3]):
                name, content = match.group(1), match.group(2)
            else:
                content, name = match.group(1), match.group(2)

            name_lower = name.lower()
            if name_lower.startswith("citation_") or name_lower.startswith("dc.") or \
               name_lower.startswith("og:") or name_lower in ("title", "description"):
                if name_lower in meta:
                    if isinstance(meta[name_lower], list):
                        meta[name_lower].append(content)
                    else:
                        meta[name_lower] = [meta[name_lower], content]
                else:
                    meta[name_lower] = content

    return meta


def scrape_item(url, user_agent, timeout=15):
    """Fetch a single item page and extract metadata."""
    from urllib.parse import quote, urlparse, urlunparse
    # URL-encode non-ASCII characters in the path
    parsed = urlparse(url)
    safe_path = quote(parsed.path, safe="/:@!$&'()*+,;=")
    safe_url = urlunparse(parsed._replace(path=safe_path))
    headers = {"User-Agent": user_agent, "Accept": "text/html"}
    req = Request(safe_url, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        return extract_metadata(html)
    except (HTTPError, URLError, TimeoutError, UnicodeEncodeError) as e:
        log.warning("Failed to fetch %s: %s", safe_url, e)
        return None
    except Exception as e:
        log.warning("Unexpected error fetching %s: %s", safe_url, e)
        return None


def flatten(val):
    """Flatten a value that might be a list into a semicolon-separated string."""
    if isinstance(val, list):
        return "; ".join(str(v) for v in val)
    return str(val) if val else ""


def meta_to_row(item_id, url, repo_name, meta):
    """Convert extracted metadata dict to a CSV row."""
    return {
        "id": item_id,
        "url": url,
        "repo": repo_name,
        "title": meta.get("citation_title", meta.get("og:title", meta.get("title", ""))),
        "author": flatten(meta.get("citation_author", "")),
        "date": meta.get("citation_publication_date",
                         meta.get("citation_online_date",
                                  meta.get("citation_date", ""))),
        "keywords": flatten(meta.get("citation_keywords", "")),
        "language": meta.get("citation_language", ""),
        "description": (meta.get("description",
                                 meta.get("og:description", "")) or "")[:500],
        "institution": meta.get("citation_dissertation_institution", ""),
        "doi": meta.get("citation_doi", ""),
        "pdf_url": meta.get("citation_pdf_url", ""),
        "type": meta.get("citation_dissertation_name",
                         meta.get("dc.type", "")),
    }


def load_checkpoint(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"last_index": 0, "scraped": 0, "errors": 0}


def save_checkpoint(path, checkpoint):
    with open(path, "w") as f:
        json.dump(checkpoint, f, indent=2)


def refresh_append(args, config, items, output_csv, delay):
    """Append-only refresh keyed on item id."""
    if not output_csv.exists():
        log.error("--append requires an existing %s", output_csv)
        sys.exit(1)

    csv.field_size_limit(10_000_000)
    db_path = OUTPUT_BASE / f"{args.repo}_refresh.db"
    db = CheckpointDB(db_path)

    if not db.get_state("seeded_from_csv"):
        log.info("Seeding dedup checkpoint from %s ...", output_csv)
        batch = []
        with open(output_csv, encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                iid = (row.get("id") or "").strip()
                if iid:
                    batch.append(iid)
                if len(batch) >= 5000:
                    db.mark_done_batch(batch)
                    batch = []
        if batch:
            db.mark_done_batch(batch)
        db.set_state("seeded_from_csv", "1")
        log.info("  seeded %d existing ids", db.count_done())

    with open(output_csv, encoding="utf-8", errors="replace") as f:
        header = next(csv.reader(f), None)
    if header != CSV_FIELDS:
        log.error("Header mismatch\n  on disk: %s\n  expected: %s", header, CSV_FIELDS)
        sys.exit(1)

    todo = [it for it in items if not db.is_done(it["id"])]
    if not args.all:
        todo = todo[:args.max]
    log.info("%s: %d sitemap items, %d not yet harvested, fetching %d",
             config["name"], len(items), len(items) - (len(items) - len(todo)), len(todo))

    csvfile = open(output_csv, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
    written = errors = 0
    consecutive_errors = 0

    try:
        for i, item in enumerate(todo, 1):
            meta = scrape_item(item["url"], config["user_agent"])
            if meta is None:
                errors += 1
                consecutive_errors += 1
                if consecutive_errors > 20:
                    log.error("Too many consecutive errors, stopping.")
                    break
                time.sleep(delay * 2)
                continue
            consecutive_errors = 0

            title = meta.get("citation_title", meta.get("og:title", meta.get("title", "")))
            if not title:
                # Not a content page; remember it so we never refetch it.
                db.mark_done(item["id"])
                time.sleep(delay)
                continue

            writer.writerow(meta_to_row(item["id"], item["url"], config["name"], meta))
            csvfile.flush()
            db.mark_done(item["id"])
            written += 1

            if i % 100 == 0:
                log.info("  %d/%d checked — appended %d (errors %d)",
                         i, len(todo), written, errors)
            time.sleep(delay)
    except KeyboardInterrupt:
        log.warning("Interrupted — progress is checkpointed, re-run to continue")
    finally:
        csvfile.close()
        log.info("=" * 60)
        log.info("%s: appended %d new records (%d errors) -> %s",
                 config["name"], written, errors, output_csv)
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Scrape OR/WA university dissertations")
    parser.add_argument("--repo", required=True, choices=list(REPOS.keys()),
                        help="Repository to scrape")
    parser.add_argument("--max", type=int, default=100, help="Max items (default: 100)")
    parser.add_argument("--all", action="store_true", help="Scrape all items")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--append", action="store_true",
                        help="Append-only refresh: skip ids already in the CSV, never truncate")
    parser.add_argument("--delay", type=float, default=None, help="Override delay between requests")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    config = REPOS[args.repo]
    delay = args.delay if args.delay is not None else config["delay"]
    output_csv = OUTPUT_BASE / config["output_csv"]
    checkpoint_path = OUTPUT_BASE / config["checkpoint"]

    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    # Fetch sitemap
    items = fetch_sitemap_urls(config)

    if args.append:
        return refresh_append(args, config, items, output_csv, delay)

    # Checkpoint
    checkpoint = load_checkpoint(checkpoint_path) if args.resume else {"last_index": 0, "scraped": 0, "errors": 0}
    start_idx = checkpoint["last_index"] if args.resume else 0
    max_items = len(items) if args.all else min(args.max, len(items))
    end_idx = min(start_idx + (max_items - start_idx if args.resume else max_items), len(items))

    log.info("Repository: %s (%s)", config["name"], args.repo)
    log.info("Scraping items %d to %d (of %d total)", start_idx, end_idx, len(items))

    # CSV
    file_exists = output_csv.exists() and args.resume
    csvfile = open(output_csv, "a" if file_exists else "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
    if not file_exists:
        writer.writeheader()

    scraped = checkpoint.get("scraped", 0)
    errors = checkpoint.get("errors", 0)
    consecutive_errors = 0

    for i in range(start_idx, end_idx):
        item = items[i]
        meta = scrape_item(item["url"], config["user_agent"])

        if meta is None:
            errors += 1
            consecutive_errors += 1
            if consecutive_errors > 20:
                log.error("Too many consecutive errors, stopping.")
                break
            time.sleep(delay * 2)
            continue

        consecutive_errors = 0

        # Skip items with no title (likely non-content pages)
        title = meta.get("citation_title", meta.get("og:title", meta.get("title", "")))
        if not title:
            continue

        row = meta_to_row(item["id"], item["url"], config["name"], meta)
        writer.writerow(row)
        scraped += 1

        if scraped % 20 == 0:
            log.info("  Scraped %d items (checked %d/%d, errors: %d)",
                     scraped, i - start_idx + 1, end_idx - start_idx, errors)
            csvfile.flush()
            checkpoint.update({"last_index": i + 1, "scraped": scraped, "errors": errors})
            save_checkpoint(checkpoint_path, checkpoint)

        time.sleep(delay)

    csvfile.close()
    checkpoint.update({"last_index": end_idx, "scraped": scraped, "errors": errors})
    save_checkpoint(checkpoint_path, checkpoint)

    log.info("Done! %s: scraped %d items (%d errors). Output: %s",
             config["name"], scraped, errors, output_csv)


if __name__ == "__main__":
    main()
