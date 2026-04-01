#!/usr/bin/env python3
"""
Build department URL mappings for universities.

For each university, maps department names to:
1. Department home page URL (e.g., https://amath.washington.edu/)
2. PhD student directory URL (e.g., https://amath.washington.edu/people/graduate-student/phd)
3. Repository collection URL (e.g., the OAI set or DSpace collection)

Outputs a JSON file that gets merged into per-university JSON data.
"""

import csv
import json
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# Known department URL patterns for key universities
# Format: university_key -> {dept_name -> {home: url, students: url, repo: url}}

DEPT_LINKS = {
    "uw_seattle": {
        "_base": "https://www.washington.edu",
        "_repo_base": "https://digital.lib.washington.edu/researchworks/collections/",
        "Aeronautics & Astronautics": {"home": "https://www.aa.washington.edu/", "students": "https://www.aa.washington.edu/students/grad"},
        "Applied Mathematics": {"home": "https://amath.washington.edu/", "students": "https://amath.washington.edu/people/graduate-student/phd"},
        "Astronomy": {"home": "https://astro.washington.edu/", "students": "https://astro.washington.edu/people/graduate-students"},
        "Atmospheric Sciences": {"home": "https://atmos.washington.edu/", "students": "https://atmos.washington.edu/people/graduate-students"},
        "Bioengineering": {"home": "https://bioe.uw.edu/", "students": "https://bioe.uw.edu/people/"},
        "Biology": {"home": "https://www.biology.washington.edu/", "students": "https://www.biology.washington.edu/people/graduate-students"},
        "Chemical Engineering": {"home": "https://www.cheme.washington.edu/", "students": "https://www.cheme.washington.edu/people/grad"},
        "Chemistry": {"home": "https://chem.washington.edu/", "students": "https://chem.washington.edu/people/graduate-students"},
        "Civil Engineering": {"home": "https://www.ce.washington.edu/", "students": "https://www.ce.washington.edu/people/grad"},
        "Computer Science & Engineering": {"home": "https://www.cs.washington.edu/", "students": "https://www.cs.washington.edu/people/phd-students"},
        "Earth & Space Sciences": {"home": "https://ess.uw.edu/", "students": "https://ess.uw.edu/people/students/"},
        "Electrical & Computer Engineering": {"home": "https://www.ece.uw.edu/", "students": "https://www.ece.uw.edu/people/grad-students/"},
        "Electrical Engineering": {"home": "https://www.ee.washington.edu/", "students": "https://www.ee.washington.edu/people/grad"},
        "Epidemiology": {"home": "https://epi.washington.edu/", "students": "https://epi.washington.edu/students/"},
        "Genetics": {"home": "https://www.gs.washington.edu/", "students": "https://www.gs.washington.edu/academics/gradprogram/"},
        "Materials Science & Engineering": {"home": "https://mse.washington.edu/", "students": "https://mse.washington.edu/people/current-students"},
        "Mathematics": {"home": "https://math.washington.edu/", "students": "https://math.washington.edu/people/graduate-students"},
        "Mechanical Engineering": {"home": "https://www.me.washington.edu/", "students": "https://www.me.washington.edu/people/grad-students"},
        "Microbiology": {"home": "https://microbiology.washington.edu/", "students": "https://microbiology.washington.edu/people/graduate-students"},
        "Neuroscience": {"home": "https://depts.washington.edu/neurogrd/", "students": "https://depts.washington.edu/neurogrd/people/current-students/"},
        "Nuclear Engineering": {"home": "https://www.nuce.washington.edu/"},
        "Oceanography": {"home": "https://www.ocean.washington.edu/", "students": "https://www.ocean.washington.edu/story/Graduate_Students"},
        "Physics": {"home": "https://phys.washington.edu/", "students": "https://phys.washington.edu/people/graduate-students"},
        "Statistics": {"home": "https://stat.uw.edu/", "students": "https://stat.uw.edu/people/grad-students"},
    },
}

# For universities where we scraped from OAI-PMH, we can link to the repository search
# The OAI set names often map to repository collection pages
OAI_REPO_PATTERNS = {
    # bepress repos: department dissertations at {base}/department_dissertations/
    "bepress": lambda base, dept_slug: f"{base}/{dept_slug}/",
    # DSpace repos: search by department
    "dspace": lambda base, dept: f"{base}/search?query={dept.replace(' ', '+')}",
}


def build_repo_collection_url(uni_key, dept_name, records):
    """Build a repository collection URL from the first record's URL."""
    for r in records:
        url = r[6]  # URL field in the record array
        if url and url.startswith("http"):
            # Extract the repository base
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                base = f"{parsed.scheme}://{parsed.netloc}"
                # For bepress repos, construct a search URL
                return f"{base}/cgi/search.cgi?q={dept_name.replace(' ', '+')}"
            except:
                pass
    return None


def main():
    """Build department links for all universities and save to JSON."""
    stem_dir = BASE_DIR / "site" / "data" / "stem"

    all_links = {}

    for fname in sorted(os.listdir(stem_dir)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue

        key = fname.replace(".json", "")
        fpath = stem_dir / fname

        with open(fpath) as f:
            uni_data = json.load(f)

        records = uni_data.get("records", [])
        if not records:
            continue

        # Get unique departments
        depts = sorted(set(r[0] for r in records))

        # Check if we have manual links
        if key in DEPT_LINKS:
            dept_links = {}
            for dept in depts:
                if dept in DEPT_LINKS[key]:
                    dept_links[dept] = DEPT_LINKS[key][dept]
            if dept_links:
                all_links[key] = dept_links
                continue

        # For other universities, build repo search URLs from the records
        dept_links = {}
        for dept in depts:
            dept_records = [r for r in records if r[0] == dept]
            repo_url = build_repo_collection_url(key, dept, dept_records)
            if repo_url:
                dept_links[dept] = {"repo_search": repo_url}

        if dept_links:
            all_links[key] = dept_links

    # Save
    outfile = BASE_DIR / "data" / "dept_links.json"
    with open(outfile, "w") as f:
        json.dump(all_links, f, indent=2, ensure_ascii=False)

    print(f"Saved department links for {len(all_links)} universities to {outfile}")

    # Also merge into per-university JSONs
    for key, links in all_links.items():
        for mode in ["stem", "nonstem"]:
            fpath = stem_dir.parent / mode / f"{key}.json"
            if not fpath.exists():
                continue
            with open(fpath) as f:
                uni_data = json.load(f)
            uni_data["dept_links"] = links
            with open(fpath, "w") as f:
                json.dump(uni_data, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Merged into per-university JSON files")


if __name__ == "__main__":
    main()
