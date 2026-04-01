#!/usr/bin/env python3
"""
Scrape UW ResearchWorks ETD collections to identify thesis/dissertation items.

UW's DSpace 7 has no OAI-PMH and no REST API. But the SSR pages include citation
meta tags. This script:
1. Discovers item UUIDs from each ETD collection page
2. Scrapes citation metadata from each item's SSR page
3. Outputs a CSV with department labels from the collection name

The ETD community UUID is 6b84acce-b816-4d18-b41a-387c062aab76.
"""

import csv
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

log = logging.getLogger(__name__)

BASE_URL = "https://digital.lib.washington.edu/researchworks"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "uw_dissertations"
OUTPUT_CSV = OUTPUT_DIR / "uw_etd_metadata.csv"
CHECKPOINT_FILE = OUTPUT_DIR / "uw_etd_checkpoint.json"

ETD_COLLECTIONS = {
    # Original 20 (A-C alphabetically)
    "b69cccbc-23af-471f-bb90-f394a2a46922": "Aeronautics & Astronautics",
    "a7c444b9-f3b6-46cc-a3ba-b0fe460d80bd": "Anthropology",
    "8b99a49a-a389-45f1-a06b-1c0cdc619f89": "Applied Mathematics",
    "99a85652-974b-49be-987c-1e8277179545": "Architecture",
    "0ed3d308-3256-469a-8650-ae68cbf0708b": "Art History",
    "8ea9afeb-7aa8-4643-a8eb-f81391b421f8": "Asian Languages & Literature",
    "a4ac3a21-41aa-4f30-b5b8-3f464578b7d3": "Astronomy",
    "ec00c2bc-f7ba-4152-bc34-e3b9d6bb04f3": "Atmospheric Sciences",
    "e45e0204-49ea-4e9b-aed8-affbebf4fcb7": "Bioengineering",
    "c3bb5ff1-bda9-428e-9693-a6ccabff6666": "Biological Chemistry",
    "d51d317c-6232-45d0-becd-f29adfebac14": "Biological Structure",
    "cdf055fa-ef19-4049-b940-42102c04ce14": "Biology",
    "21e8e79e-1ef7-4208-b69a-10cd47a52b23": "Biomedical & Health Informatics",
    "f241a304-4fb0-423b-93a6-31c597c8784a": "Biostatistics",
    "b61940b2-3f75-4010-8e0d-8d6c569658be": "Built Environment",
    "5b0e0251-c746-45af-82af-0d5320e31aa2": "Business Administration",
    "2cf6ac6e-b765-455e-a71b-f1088158be6b": "Chemical Engineering",
    "ce6ff467-0efd-44c9-9661-e3fa89e077ab": "Chemistry",
    "a0d3f14f-68c7-44c6-b5f8-45e7826205b8": "Cinema & Media Studies",
    "db9ef52c-ea61-4870-b193-ddb025314ef1": "Civil Engineering",
    # Newly discovered 110 collections (C-W alphabetically)
    "46c03b9d-6688-4755-87cb-d73defd8de4e": "Classical Languages & Literature",
    "ea888303-9d7c-4d0c-bbe1-e742a0f2d779": "Communications",
    "c2eba5d4-6e7b-49a3-af85-8dc6d7414f43": "Comparative Literature",
    "8aa77bc8-2ebc-41df-bf8c-bf48856d1bad": "Comparative Medicine",
    "24db75a0-2e2f-4bd6-bf81-9ae52decdf3d": "Computer Science & Engineering",
    "8a07fcd7-2070-4c2a-9258-721be90fa75d": "Computer Science & Systems (Tacoma)",
    "2b196c58-a3e6-4f30-8427-a87d99302c16": "Computing & Software Systems (Bothell)",
    "a1e86818-2917-411b-bb4f-4ccd4c269012": "Construction Management",
    "a4c362b5-0c98-49af-bb3a-4b003bd576a6": "Dentistry",
    "7ef492e6-7391-4f23-a924-b8cd8fbc01af": "Design",
    "bc3de820-e425-4686-b1aa-003adc612b3b": "Digital Arts & Experimental Media",
    "75208926-0a00-4be2-9c1e-bf30bc239115": "Drama",
    "26d23815-ca95-4061-91f2-5036ecefc325": "Earth & Space Sciences",
    "e803923b-f580-423e-ae2e-e70026ee6a21": "East Asian Studies",
    "5eda2b1e-813e-4eaa-99fc-5eb5a77d4d30": "Economics",
    "6306a37b-4281-4d66-a805-0a169afd2288": "Education (Bothell)",
    "87869905-804d-48a9-9667-3407499ff721": "Education (Seattle)",
    "2f7e12e0-ffbe-45ea-871f-260bd1ab5ac1": "Education (Tacoma)",
    "109f1311-912a-43f7-b3ae-0182a0495354": "Electrical & Computer Engineering",
    "dde90d2a-08c3-43f0-99a5-bfb8b47f1597": "Electrical Engineering",
    "fc725099-1e70-4dc6-9f9e-2f3d4edca4c2": "Engineering",
    "7aa9abd2-f2be-4797-8aad-7a672ae38525": "English",
    "bcad9170-d865-4b47-a83d-60b824be1c0d": "Environmental Health",
    "c2553083-88f6-4c84-a869-70a46bf6d849": "Epidemiology",
    "35816c03-b0ee-4916-8d50-96562519e041": "Ethnomusicology",
    "77b9f447-e38c-4c2d-b2ed-918c1f46de61": "Fine Arts",
    "0b101821-a0c9-4638-998f-b84b9dd2ba50": "Fisheries",
    "30d18277-c139-4c86-84f8-2555829ed4df": "Forestry",
    "db17a73e-f2d6-4702-86b0-dc03ffbdce17": "French & Italian",
    "3bad2cf1-aea4-44e1-ad95-8ea72d842324": "Gender, Women & Sexuality",
    "5e8726b1-0830-49fc-a020-985cbee2e3b7": "Genetics",
    "4b60a0f3-12ea-490a-9982-74956e3965ce": "Geography",
    "364c069e-74e8-421f-ae69-da498d839647": "Geology",
    "24e08e5b-569c-4e03-9eb4-c7f395a24f02": "Geophysics",
    "3f4df462-3927-410b-95df-31ca5a2ce9bc": "German",
    "bdd8709e-1053-4b86-a7ba-226073413c29": "Global Health",
    "b970eb4f-fa7a-49b5-bc14-a776ad6b0135": "Health Services",
    "93aff68b-89d2-463a-aebe-3c3bd5289939": "International Studies",
    "4a03f0c9-7775-47f5-8dbf-2bcd20d0d04d": "Hispanic Studies",
    "de59d688-1251-4e74-8fc8-482d3ed5d0fe": "History",
    "e775938c-896d-49f6-92d1-b27030a26057": "Human Centered Design & Engineering",
    "a3b4851b-ca84-4150-8ab3-1f2cd998fbf6": "Immunology",
    "af85ad77-c525-4e6b-9453-20ee3ea9665b": "Individual Program",
    "91b8a9f5-bec7-4ad9-9942-b3913dae3965": "Industrial Engineering",
    "b9ac79fd-eb5e-4506-a334-b5d3258e9538": "Information Science",
    "905f2f23-725c-4d82-b11d-391a8583bf01": "Laboratory Medicine",
    "69a4e77d-8ae5-4283-9fe8-6137b702e757": "Landscape Architecture",
    "8ee179b3-c96f-413d-b4e9-b99eb16f032d": "Law",
    "9a648782-c3a5-49ec-ae00-7920af257e9f": "Linguistics",
    "e5e58c99-ef4f-45b2-b58b-e66452ddd967": "Marine Affairs",
    "71bfc742-3ef9-43f9-9efb-3f2f497fb38a": "Materials Science & Engineering",
    "9b20908e-d0b3-437b-acc6-4ac4c15ad821": "Mathematics",
    "a41a22bd-c323-4799-82ec-13dffb586f9a": "Mechanical Engineering",
    "d1ad311b-514e-4234-b124-d36855cebaff": "Medical History & Ethics",
    "7c458ce5-d413-4198-b9bb-04f16ad4f4c6": "Medicinal Chemistry",
    "72a194f6-f974-4836-87da-9deda75316ae": "Microbiology",
    "e108efda-c032-4340-8ec0-d7deb3e2114f": "Molecular & Cellular Biology",
    "3212b70a-4dbd-4c2a-9de9-3206360010b1": "Molecular Biotechnology",
    "b99cd724-50b8-45a8-9a25-7d30c09145c2": "Molecular Engineering",
    "1c414fa9-fb4a-4075-8876-3d706fb8214e": "Molecular Medicine",
    "ae3e678c-6d1c-4cad-8bfc-be2f4968e708": "Museology",
    "5ea168e9-ff40-4a58-bd42-6a49c1862690": "Music",
    "5ee458b7-aa1d-4b12-8bcd-d21f3c68838a": "Near Eastern Languages & Literature",
    "ce8ae92b-1c72-43da-b6f3-345ff3074652": "Near & Middle Eastern Studies",
    "2f9f26b9-7abc-4cb8-9f43-f338875a7df2": "Neuroscience",
    "777cb978-a645-405d-967e-2192f3c714ee": "Nuclear Engineering",
    "06fd875f-a061-42e6-97c6-4a53dff58f0e": "Nursing",
    "395e6730-747b-4e17-89b7-724abfba66a3": "Nutritional Sciences",
    "272b6eb1-9716-4e17-b4c3-febc5d9896ac": "Oceanography",
    "d4a57b58-a5d3-4450-97a0-43fde3523db6": "Pathobiology",
    "8a76476a-48cd-4a32-98de-6f87e32e16df": "Pathology",
    "af2675b4-b881-466b-ad34-b842eb9c4bec": "Pharmaceutical Sciences",
    "147d2cb3-b213-4b29-8468-beea448bfbf4": "Pharmaceutics",
    "7fd397e3-3c9b-4e39-abb7-31898622aca7": "Pharmacology",
    "f1cbf0fe-d2e3-4ae4-a1ab-43f9391107ef": "Philosophy",
    "aa5ac5a3-3314-4b8e-9362-8927c142dfc2": "Physics",
    "05a36875-e44e-4940-9d08-a8d23a21d197": "Physiology & Biophysics",
    "6024d2c6-5361-434b-854f-954fddecdd2f": "Political Science",
    "5cd51737-89b8-406f-8572-65df67459330": "Psychology",
    "e8fffe79-97ba-4181-9fce-2d0a86965032": "Public Administration",
    "a032aefb-323e-46f8-8881-72ad2759e0e9": "Public Affairs",
    "61f1ad86-90fb-422d-a735-4a3b0c00f360": "Public Health",
    "9487bf13-9a08-4a37-a3c9-69c5c029ede6": "Public Health Genetics",
    "abd7b586-0fa1-4b86-ab5b-8946ec0abde0": "Quantitative Ecology & Resource Management",
    "4a8468f6-8674-49e0-a7e1-c0967aa8e54b": "Rehabilitation Medicine",
    "73697cdd-d77c-4649-a055-d35b0ebaf414": "Romance Languages & Literature",
    "0b0e13d8-86ac-41dd-a483-ba0f677699c0": "Russian & East European Studies",
    "e4308c79-b27f-40d0-a8e3-2b2afacfd515": "Scandinavian Languages & Literature",
    "3a529d0c-c090-47fb-8aa9-c6a2c65c4048": "Scientific & Technical Communication",
    "a18150a1-e2a0-432c-a4e3-ea1ce855d53f": "Slavic Languages & Literature",
    "f287d79c-1b8c-4e5f-b7f9-7c86c14e7336": "Social Welfare",
    "6114d106-a4f0-4d2a-9f95-819ab5742347": "Social Work",
    "b9feb40b-d2e8-4ef3-86de-62ad730c7382": "Sociology",
    "e9834362-b1e0-4f85-b9b4-5ee6428e6a1d": "Speech & Hearing Sciences",
    "a96ad6ac-b9b8-4e83-ac36-906622b47581": "Statistics",
    "9093d1aa-db9c-404c-8bcd-f6a55d292c0c": "Urban Planning",
    "d2dc6bbe-d0c3-42f7-a395-66b8b720eb8e": "Women's Studies",
}

HEADERS = {"User-Agent": "UW-ETD-Research/1.0 (academic research)"}
DELAY = 0.5

CSV_FIELDS = [
    "uuid", "url", "collection_uuid", "department", "title", "author",
    "date", "keywords", "description", "handle_url", "pdf_url",
]


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text())
    return {"completed_items": [], "discovered_items": {}}


def save_checkpoint(data):
    CHECKPOINT_FILE.write_text(json.dumps(data, indent=2))


def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError) as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                log.warning("Failed to fetch %s: %s", url, e)
                return None


def discover_collection_items(coll_uuid):
    """Discover item UUIDs by browsing collection pages."""
    items = []
    page = 1
    while True:
        url = f"{BASE_URL}/collections/{coll_uuid}?cp.page={page}&cp.rpp=20"
        html = fetch(url)
        if not html:
            break
        # Find item UUIDs in the page
        uuids = re.findall(r'/items/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', html)
        new_uuids = list(dict.fromkeys(uuids))  # deduplicate preserving order
        if not new_uuids:
            break
        items.extend(new_uuids)
        log.info("  Collection page %d: %d items (total: %d)", page, len(new_uuids), len(items))
        # Check if we got any new items vs previous page
        if page > 1 and set(new_uuids) == set(prev_uuids):
            break
        prev_uuids = new_uuids
        page += 1
        time.sleep(DELAY)
    return list(dict.fromkeys(items))


def scrape_item(uuid):
    """Scrape metadata from an item's SSR page."""
    url = f"{BASE_URL}/items/{uuid}"
    html = fetch(url)
    if not html:
        return None

    def meta(name):
        m = re.search(rf'<meta\s+name="{name}"\s+content="([^"]*)"', html)
        return m.group(1).strip() if m else ""

    return {
        "uuid": uuid,
        "url": url,
        "title": meta("citation_title") or meta("title"),
        "author": meta("citation_author"),
        "date": meta("citation_publication_date"),
        "keywords": meta("citation_keywords"),
        "description": meta("description"),
        "handle_url": meta("citation_abstract_html_url"),
        "pdf_url": meta("citation_pdf_url"),
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    checkpoint = load_checkpoint()
    completed = set(checkpoint.get("completed_items", []))
    discovered = checkpoint.get("discovered_items", {})

    # Phase 1: Discover items from all ETD collections
    if not discovered:
        log.info("Phase 1: Discovering items from %d ETD collections...", len(ETD_COLLECTIONS))
        for coll_uuid, dept_name in ETD_COLLECTIONS.items():
            log.info("  %s (%s)...", dept_name, coll_uuid)
            items = discover_collection_items(coll_uuid)
            for item_uuid in items:
                if item_uuid not in discovered:
                    discovered[item_uuid] = coll_uuid
            log.info("    Found %d items", len(items))
        checkpoint["discovered_items"] = discovered
        save_checkpoint(checkpoint)
        log.info("Discovered %d unique items across all ETD collections", len(discovered))

    # Phase 2: Scrape metadata for each item
    to_scrape = [uuid for uuid in discovered if uuid not in completed]
    log.info("Phase 2: Scraping %d items (%d already done)", len(to_scrape), len(completed))

    # Open CSV for append
    csv_exists = OUTPUT_CSV.exists() and OUTPUT_CSV.stat().st_size > 0
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not csv_exists:
            writer.writeheader()

        for i, uuid in enumerate(to_scrape):
            coll_uuid = discovered[uuid]
            dept = ETD_COLLECTIONS.get(coll_uuid, "Unknown")

            meta = scrape_item(uuid)
            if meta:
                meta["collection_uuid"] = coll_uuid
                meta["department"] = dept
                writer.writerow(meta)

            completed.add(uuid)

            if (i + 1) % 50 == 0:
                log.info("  Scraped %d/%d items (errors: %d)", i + 1, len(to_scrape),
                         sum(1 for u in to_scrape[:i+1] if not scrape_item))
                checkpoint["completed_items"] = list(completed)
                save_checkpoint(checkpoint)
                f.flush()

            time.sleep(DELAY)

    checkpoint["completed_items"] = list(completed)
    save_checkpoint(checkpoint)
    log.info("Done! %d items scraped to %s", len(completed), OUTPUT_CSV)


if __name__ == "__main__":
    main()
