#!/usr/bin/env python3
"""
Playwright-based ETD scraper for Cloudflare-protected university repositories.

Uses a real browser to bypass Cloudflare challenges, then extracts metadata from
DSpace SSR pages (citation meta tags) or REST APIs.

Supports:
  - U Michigan (Deep Blue) - DSpace, Cloudflare WAF
  - Texas A&M (OakTrust) - DSpace, Cloudflare WAF
  - U Pittsburgh (D-Scholarship) - EPrints, Cloudflare WAF
  - Johns Hopkins (JScholarship) - DSpace, blocked
  - UNC Chapel Hill (CDR) - Hyrax, rate-limited JSON API

Usage:
    python scripts/scrape_with_playwright.py --repo umich
    python scripts/scrape_with_playwright.py --repo tamu
    python scripts/scrape_with_playwright.py --repo unc --resume
"""

import argparse
import csv
import json
import logging
import os
import re
import time
from pathlib import Path

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "western_us_dissertations"

REPOS = {
    "umich": {
        "name": "University of Michigan",
        "base_url": "https://deepblue.lib.umich.edu",
        "platform": "dspace",
        "sitemap_url": "https://deepblue.lib.umich.edu/sitemap0.xml",
        "etd_community_uuid": None,  # Will discover
        "delay": 2.0,
        "csv": "umich_etds.csv",
        "checkpoint": "umich_checkpoint.json",
    },
    "tamu": {
        "name": "Texas A&M University",
        "base_url": "https://oaktrust.library.tamu.edu",
        "platform": "dspace",
        "sitemap_url": "https://oaktrust.library.tamu.edu/sitemap0.xml",
        "etd_community_uuid": None,
        "delay": 2.0,
        "csv": "tamu_etds.csv",
        "checkpoint": "tamu_checkpoint.json",
    },
    "unc": {
        "name": "UNC Chapel Hill",
        "base_url": "https://cdr.lib.unc.edu",
        "platform": "hyrax",
        "delay": 2.0,
        "csv": "unc_etds.csv",
        "checkpoint": "unc_checkpoint.json",
    },
    "upitt": {
        "name": "University of Pittsburgh",
        "base_url": "https://d-scholarship.pitt.edu",
        "platform": "eprints",
        "sitemap_url": "https://d-scholarship.pitt.edu/cgi/oai2?verb=Identify",  # EPrints - different approach
        "delay": 2.0,
        "csv": "upitt_etds.csv",
        "checkpoint": "upitt_checkpoint.json",
    },
    "jhu": {
        "name": "Johns Hopkins University",
        "base_url": "https://jscholarship.library.jhu.edu",
        "platform": "dspace",
        "delay": 2.0,
        "csv": "jhu_etds.csv",
        "checkpoint": "jhu_checkpoint.json",
    },
}

CSV_FIELDS = [
    "id", "url", "title", "creator", "date", "degree_type",
    "department", "subject", "description",
]


def load_checkpoint(path):
    if path.exists():
        return json.loads(path.read_text())
    return {"completed": [], "discovered": [], "phase": "discover"}


def save_checkpoint(path, data):
    path.write_text(json.dumps(data, indent=2))


def extract_meta(page, name):
    """Extract a meta tag value from the page."""
    el = page.query_selector(f'meta[name="{name}"]')
    return el.get_attribute("content").strip() if el else ""


def scrape_dspace_with_playwright(config):
    """Scrape a DSpace repository using Playwright to bypass Cloudflare."""
    from playwright.sync_api import sync_playwright

    base = config["base_url"]
    delay = config["delay"]
    csv_path = DATA_DIR / config["csv"]
    cp_path = DATA_DIR / config["checkpoint"]
    checkpoint = load_checkpoint(cp_path)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # Must be headed to bypass Cloudflare
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        page.add_init_script('Object.defineProperty(navigator, "webdriver", { get: () => false });')

        # Phase 1: Discover ETD items from sitemap
        if checkpoint["phase"] == "discover":
            log.info("Phase 1: Discovering ETD items...")

            # First, navigate to the site to pass Cloudflare challenge
            log.info("Passing Cloudflare challenge...")
            page.goto(base, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)  # Wait for challenge to complete

            # Now fetch the sitemap
            log.info(f"Fetching sitemap: {config['sitemap_url']}")
            page.goto(config["sitemap_url"], wait_until="domcontentloaded", timeout=30000)
            content = page.content()

            # Extract item URLs
            item_urls = re.findall(r"(https?://[^<]+/items/[a-f0-9-]{36})", content)
            comm_urls = re.findall(r"(https?://[^<]+/communities/[a-f0-9-]{36})", content)
            coll_urls = re.findall(r"(https?://[^<]+/collections/[a-f0-9-]{36})", content)

            log.info(f"Found {len(item_urls)} items, {len(comm_urls)} communities, {len(coll_urls)} collections")

            # Find ETD community by browsing communities
            etd_comm = None
            for comm_url in comm_urls:
                page.goto(comm_url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(delay)
                title = extract_meta(page, "title")
                if any(x in title.lower() for x in ["thesis", "dissert", "etd", "graduate", "rackham", "electronic thes"]):
                    etd_comm = comm_url
                    log.info(f"Found ETD community: {title} ({comm_url})")
                    break

            if not etd_comm:
                log.warning("No ETD community found. Trying to find ETD collections...")
                # Try collections instead
                for coll_url in coll_urls[:100]:
                    page.goto(coll_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(delay)
                    title = extract_meta(page, "title")
                    if any(x in title.lower() for x in ["thesis", "dissert", "etd"]):
                        log.info(f"Found ETD collection: {title} ({coll_url})")
                        # Get items from this collection
                        coll_items = re.findall(r"/items/([a-f0-9-]{36})", page.content())
                        checkpoint["discovered"].extend(coll_items)

            # If we found a community, browse its collections for items
            if etd_comm:
                page.goto(etd_comm, wait_until="domcontentloaded", timeout=20000)
                time.sleep(delay)
                # Find collection links
                etd_colls = re.findall(r"/collections/([a-f0-9-]{36})", page.content())
                log.info(f"ETD community has {len(set(etd_colls))} collections")

                for coll_uuid in set(etd_colls):
                    coll_url = f"{base}/collections/{coll_uuid}"
                    page_num = 1
                    while True:
                        url = f"{coll_url}?cp.page={page_num}&cp.rpp=20"
                        page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        time.sleep(delay)
                        items = re.findall(r"/items/([a-f0-9-]{36})", page.content())
                        new_items = [i for i in items if i not in checkpoint["discovered"]]
                        if not new_items:
                            break
                        checkpoint["discovered"].extend(new_items)
                        page_num += 1

                    coll_title = extract_meta(page, "title")
                    log.info(f"  Collection {coll_title}: {len(checkpoint['discovered'])} total items")
                    save_checkpoint(cp_path, checkpoint)

            checkpoint["discovered"] = list(set(checkpoint["discovered"]))
            checkpoint["phase"] = "scrape"
            save_checkpoint(cp_path, checkpoint)
            log.info(f"Discovered {len(checkpoint['discovered'])} unique items")

        # Phase 2: Scrape metadata for each item
        completed = set(checkpoint.get("completed", []))
        to_scrape = [uid for uid in checkpoint["discovered"] if uid not in completed]
        log.info(f"Phase 2: Scraping {len(to_scrape)} items ({len(completed)} already done)")

        # Open CSV for append
        csv_exists = csv_path.exists() and csv_path.stat().st_size > 0
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if not csv_exists:
                writer.writeheader()

            for i, uuid in enumerate(to_scrape):
                url = f"{base}/items/{uuid}"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(delay)

                    # Extract citation meta tags
                    title = extract_meta(page, "citation_title") or extract_meta(page, "title")
                    author = extract_meta(page, "citation_author")
                    date = extract_meta(page, "citation_publication_date")
                    keywords = extract_meta(page, "citation_keywords")
                    description = extract_meta(page, "description")
                    pdf_url = extract_meta(page, "citation_pdf_url")

                    # Try to find degree type in page content
                    content = page.content()
                    degree = ""
                    thesis_match = re.search(r"Thesis\s*\(([^)]+)\)", content)
                    if thesis_match:
                        deg = thesis_match.group(1)
                        if "Ph.D" in deg or "Doctor" in deg:
                            degree = "phd"
                        elif "Master" in deg:
                            degree = "ms"

                    # Try to find department
                    dept = ""
                    dept_match = re.search(r"(?:Department|Program|Discipline)[:\s]+([^<]{3,60})", content)
                    if dept_match:
                        dept = dept_match.group(1).strip()

                    if author:
                        writer.writerow({
                            "id": uuid, "url": url, "title": title,
                            "creator": author, "date": date, "degree_type": degree,
                            "department": dept,
                            "subject": keywords, "description": description[:300],
                        })

                    completed.add(uuid)

                except Exception as e:
                    log.debug(f"Failed {uuid}: {e}")
                    completed.add(uuid)  # Skip to avoid retrying forever

                if (i + 1) % 50 == 0:
                    log.info(f"  Scraped {i + 1}/{len(to_scrape)} items")
                    checkpoint["completed"] = list(completed)
                    save_checkpoint(cp_path, checkpoint)
                    f.flush()

        checkpoint["completed"] = list(completed)
        save_checkpoint(cp_path, checkpoint)

        browser.close()

    log.info(f"Done! Results in {csv_path}")


def scrape_hyrax_with_playwright(config):
    """Scrape a Hyrax/Samvera repository using Playwright for rate-limited JSON API."""
    from playwright.sync_api import sync_playwright

    base = config["base_url"]
    delay = config["delay"]
    csv_path = DATA_DIR / config["csv"]
    cp_path = DATA_DIR / config["checkpoint"]
    checkpoint = load_checkpoint(cp_path)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        # Phase 1: Discover items from sitemap
        if checkpoint["phase"] == "discover":
            log.info("Phase 1: Scanning sitemaps for ETD items...")
            diss_ids = set()
            ms_ids = set()

            for i in range(4096):
                try:
                    page.goto(f"{base}/sitemap/{i:03d}?locale=en",
                              wait_until="networkidle", timeout=10000)
                    content = page.content()
                    for m in re.finditer(r"/concern/dissertations/([a-z0-9]+)", content):
                        diss_ids.add(m.group(1))
                    for m in re.finditer(r"/concern/masters_papers/([a-z0-9]+)", content):
                        ms_ids.add(m.group(1))
                except:
                    pass

                if (i + 1) % 500 == 0:
                    log.info(f"  Scanned {i + 1}/4096: {len(diss_ids)} diss + {len(ms_ids)} masters")
                    # Stop early if no new ETDs for a while
                    if i > 1500 and len(diss_ids) > 3000:
                        break

            checkpoint["discovered"] = (
                [("dissertations", id, "phd") for id in diss_ids] +
                [("masters_papers", id, "ms") for id in ms_ids]
            )
            checkpoint["phase"] = "scrape"
            save_checkpoint(cp_path, checkpoint)
            log.info(f"Discovered {len(diss_ids)} dissertations + {len(ms_ids)} masters")

        # Phase 2: Fetch metadata via JSON API (using browser to avoid rate limits)
        completed = set(checkpoint.get("completed", []))
        to_scrape = [(t, id, d) for t, id, d in checkpoint["discovered"] if id not in completed]
        log.info(f"Phase 2: Fetching {len(to_scrape)} items ({len(completed)} already done)")

        csv_exists = csv_path.exists() and csv_path.stat().st_size > 0
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if not csv_exists:
                writer.writeheader()

            for i, (item_type, item_id, degree_label) in enumerate(to_scrape):
                url = f"{base}/concern/{item_type}/{item_id}.json?locale=en"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(delay)

                    # Parse JSON from page content
                    content = page.inner_text("body")
                    try:
                        d = json.loads(content)
                    except:
                        completed.add(item_id)
                        continue

                    creators = d.get("creators", [])
                    creator = ""
                    if creators and isinstance(creators[0], dict):
                        for field in ["name", "label", "display_name"]:
                            v = creators[0].get(field, "")
                            if isinstance(v, list) and v:
                                creator = v[0]
                                break
                            elif isinstance(v, str) and v:
                                creator = v
                                break

                    title_raw = d.get("title", [""])
                    title = title_raw[0] if isinstance(title_raw, list) else str(title_raw)
                    abstract = d.get("abstract", [""])
                    abstract = abstract[0] if isinstance(abstract, list) else str(abstract)
                    date = d.get("date_issued", "") or str(d.get("date_created", ""))[:10]

                    if title:
                        writer.writerow({
                            "id": item_id,
                            "url": f"{base}/concern/{item_type}/{item_id}",
                            "title": title, "creator": creator, "date": date,
                            "degree_type": degree_label,
                            "department": "",
                            "subject": "; ".join(d.get("subject", d.get("keyword", []))),
                            "description": abstract[:300] if abstract else "",
                        })

                    completed.add(item_id)

                except Exception as e:
                    log.debug(f"Failed {item_id}: {e}")
                    completed.add(item_id)

                if (i + 1) % 100 == 0:
                    log.info(f"  Fetched {i + 1}/{len(to_scrape)} items")
                    checkpoint["completed"] = list(completed)
                    save_checkpoint(cp_path, checkpoint)
                    f.flush()

        checkpoint["completed"] = list(completed)
        save_checkpoint(cp_path, checkpoint)
        browser.close()

    log.info(f"Done! Results in {csv_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, choices=REPOS.keys())
    parser.add_argument("--resume", action="store_true",
                        help="Resume from checkpoint (skip discovery phase)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        datefmt="%H:%M:%S")

    config = REPOS[args.repo]
    log.info("Scraping %s with Playwright...", config["name"])

    if config["platform"] == "hyrax":
        scrape_hyrax_with_playwright(config)
    else:
        scrape_dspace_with_playwright(config)


if __name__ == "__main__":
    main()
