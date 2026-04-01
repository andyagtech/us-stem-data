G#!/usr/bin/env python3
"""
Scrape Caltech department graduate alumni lists.
Sources: CMS, MCE, EE, GALCIT/Aerospace, Medical Engineering

Extracts: year, first_name, last_name, degree_type, title, thesis_url, doi, advisors
"""

import csv
import os
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "data", "caltech_dissertations")

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


def main():
    os.makedirs(BASE_DIR, exist_ok=True)

    all_records = []
    fieldnames = ["year", "name", "first_name", "last_name", "degree_type",
                   "title", "thesis_url", "doi", "advisors", "institution",
                   "department", "dept_key"]

    for dept in DEPARTMENTS:
        try:
            records = scrape_department(dept)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue

        if not records:
            continue

        # Write per-department CSV
        dept_file = os.path.join(BASE_DIR, f"{dept['key']}_alumni.csv")
        with open(dept_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

        phds = [r for r in records if r["degree_type"] == "phd"]
        masters = [r for r in records if r["degree_type"] != "phd"]
        years = sorted(set(r["year"] for r in records))
        print(f"  → {dept_file}")
        print(f"    {len(records)} records ({len(phds)} PhD, {len(masters)} Masters) {years[0]}–{years[-1]}")

        all_records.extend(records)

    # Write combined CSV
    if all_records:
        combined_file = os.path.join(BASE_DIR, "caltech_dept_alumni_combined.csv")
        with open(combined_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_records)

        total_phds = len([r for r in all_records if r["degree_type"] == "phd"])
        print(f"\n→ {combined_file}")
        print(f"  {len(all_records)} total records ({total_phds} PhD)")
        print(f"  Departments: {len(set(r['dept_key'] for r in all_records))}")

        # Recent PhD counts by department
        print("\n  Recent PhDs by department (2015-2025):")
        for dept in DEPARTMENTS:
            n = len([r for r in all_records
                     if r['dept_key'] == dept['key']
                     and r['degree_type'] == 'phd'
                     and r['year'].isdigit() and 2015 <= int(r['year']) <= 2025])
            if n > 0:
                print(f"    {dept['name']:40s} {n:4d}")


if __name__ == "__main__":
    main()
