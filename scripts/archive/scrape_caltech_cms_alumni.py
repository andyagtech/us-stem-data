#!/usr/bin/env python3
"""
Scrape Caltech department graduate alumni lists.
Sources: CMS, MCE, EE, GALCIT/Aerospace, Medical Engineering

Extracts: year, first_name, last_name, degree_type, title, thesis_url, doi, advisors

Usage:
    /usr/bin/python3 scripts/archive/scrape_caltech_cms_alumni.py            # full rewrite
    /usr/bin/python3 scripts/archive/scrape_caltech_cms_alumni.py --append   # refresh

--append is the mode to use against the existing snapshot: the department pages
are complete listings, so it re-reads them, then appends only the rows whose key
is not already in caltech_dept_alumni_combined.csv. The combined CSV is never
rewritten and the per-department CSVs are left untouched.

Needs requests + beautifulsoup4, which on this machine are only present in
/usr/bin/python3 (the homebrew python3 does not have them).
"""

import argparse
import csv
import os
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "caltech_dissertations")

DEPARTMENTS = [
    {
        'key': 'cms',
        'name': 'Computing + Mathematical Sciences',
        'url': 'https://www.cms.caltech.edu/people/grads/alumni',
    },
    {
        'key': 'mce',
        'name': 'Mechanical & Civil Engineering',
        'url': 'https://mce.caltech.edu/people/graduate-students/alumni',
    },
    {
        'key': 'ee',
        'name': 'Electrical Engineering',
        'url': 'https://ee.caltech.edu/people/graduate-students/alumni',
    },
    {
        'key': 'galcit',
        'name': 'Aerospace (GALCIT)',
        'url': 'https://galcit.caltech.edu/people/graduate-students/alumni',
    },
    {
        'key': 'mede',
        'name': 'Medical Engineering',
        'url': 'https://mede.caltech.edu/people/graduate-students/graduate-alumni',
    },
]


def scrape_department(dept):
    """Scrape a single department alumni page."""
    url = dept['url']
    print(f"Fetching {dept['name']} ({url}) ...")
    r = requests.get(url, timeout=30, allow_redirects=True)
    r.raise_for_status()
    print(f"  {len(r.text):,} bytes")

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    if not table:
        print("  ERROR: No table found on page")
        return []

    rows = table.find_all("tr")
    print(f"  {len(rows)} rows (incl. header)")

    # Parse header
    header_row = rows[0]
    headers = [th.get_text(strip=True).lower().replace(" ", "_")
               for th in header_row.find_all(["td", "th"])]
    print(f"  Headers: {headers}")

    records = []
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        year = cells[0].get_text(strip=True)
        first_name = cells[1].get_text(strip=True)
        last_name = cells[2].get_text(strip=True)
        degree_type = cells[3].get_text(strip=True)
        title = cells[4].get_text(strip=True)
        institution = cells[5].get_text(strip=True) if len(cells) > 5 else ""
        doi = cells[6].get_text(strip=True) if len(cells) > 6 else ""
        advisors = cells[7].get_text(strip=True) if len(cells) > 7 else ""

        # Extract thesis URL from title cell link
        link = cells[4].find("a")
        thesis_url = link.get("href", "") if link else ""

        # Combine name as "Last, First" for consistency with other datasets
        name = f"{last_name}, {first_name}"

        records.append({
            "year": year,
            "name": name,
            "first_name": first_name,
            "last_name": last_name,
            "degree_type": degree_type,
            "title": title,
            "thesis_url": thesis_url,
            "doi": doi,
            "advisors": advisors,
            "institution": institution,
            "department": dept['name'],
            "dept_key": dept['key'],
        })

    return records


FIELDNAMES = ["year", "name", "first_name", "last_name", "degree_type",
              "title", "thesis_url", "doi", "advisors", "institution",
              "department", "dept_key"]


def record_key(r):
    """Stable identity for an alumni row (the pages carry no record id)."""
    if r.get("thesis_url"):
        return f"url:{r['thesis_url'].strip()}"
    return "|".join([r.get("dept_key", ""), r.get("year", ""),
                     r.get("name", ""), (r.get("title", "") or "")[:80]])


def scrape_all():
    """Scrape every department, returning (records, per_dept)."""
    all_records = []
    per_dept = {}
    for dept in DEPARTMENTS:
        try:
            records = scrape_department(dept)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue
        if not records:
            continue
        per_dept[dept["key"]] = records
        all_records.extend(records)
    return all_records, per_dept


def main():
    parser = argparse.ArgumentParser(description="Scrape Caltech department alumni lists")
    parser.add_argument("--append", action="store_true",
                        help="Append-only refresh of caltech_dept_alumni_combined.csv")
    args = parser.parse_args()

    os.makedirs(BASE_DIR, exist_ok=True)
    combined_file = os.path.join(BASE_DIR, "caltech_dept_alumni_combined.csv")

    if args.append:
        if not os.path.exists(combined_file):
            print(f"--append requires an existing {combined_file}")
            return
        csv.field_size_limit(10_000_000)
        with open(combined_file, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != FIELDNAMES:
                print(f"Header mismatch\n  on disk: {reader.fieldnames}\n  expected: {FIELDNAMES}")
                return
            known = {record_key(r) for r in reader}
        print(f"{len(known)} rows already in the combined CSV")

        all_records, _ = scrape_all()
        new = [r for r in all_records if record_key(r) not in known]
        print(f"\nScraped {len(all_records)} rows, {len(new)} are new")

        if new:
            with open(combined_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writerows(new)
        by_year = {}
        for r in new:
            by_year[r["year"]] = by_year.get(r["year"], 0) + 1
        for y in sorted(by_year):
            print(f"  {y}: {by_year[y]}")
        print(f"\n-> appended {len(new)} rows to {combined_file}")
        return

    all_records, per_dept = scrape_all()

    for dept in DEPARTMENTS:
        records = per_dept.get(dept["key"])
        if not records:
            continue
        dept_file = os.path.join(BASE_DIR, f"{dept['key']}_alumni.csv")
        with open(dept_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(records)

        phds = [r for r in records if r["degree_type"] == "phd"]
        masters = [r for r in records if r["degree_type"] != "phd"]
        years = sorted(set(r["year"] for r in records))
        print(f"  -> {dept_file}")
        print(f"    {len(records)} records ({len(phds)} PhD, {len(masters)} Masters) {years[0]}-{years[-1]}")

    if all_records:
        with open(combined_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(all_records)

        total_phds = len([r for r in all_records if r["degree_type"] == "phd"])
        print(f"\n-> {combined_file}")
        print(f"  {len(all_records)} total records ({total_phds} PhD)")
        print(f"  Departments: {len(set(r['dept_key'] for r in all_records))}")


if __name__ == "__main__":
    main()
