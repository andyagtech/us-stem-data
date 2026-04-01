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
    "mit": {
        "Computer Science": {"home": "https://www.eecs.mit.edu/", "students": "https://www.eecs.mit.edu/people/"},
        "Electrical & Computer Engineering": {"home": "https://www.eecs.mit.edu/", "students": "https://www.eecs.mit.edu/people/"},
        "Mathematics & Statistics": {"home": "https://math.mit.edu/", "students": "https://math.mit.edu/directory/graduate.html"},
        "Physics": {"home": "https://physics.mit.edu/", "students": "https://physics.mit.edu/academic-programs/graduate-students/"},
        "Chemistry": {"home": "https://chemistry.mit.edu/", "students": "https://chemistry.mit.edu/academic-programs/graduate-programs/"},
        "Mechanical Engineering": {"home": "https://meche.mit.edu/", "students": "https://meche.mit.edu/academics/graduate"},
        "Chemical Engineering": {"home": "https://cheme.mit.edu/", "students": "https://cheme.mit.edu/academics/graduate-students/"},
        "Materials Science & Engineering": {"home": "https://dmse.mit.edu/", "students": "https://dmse.mit.edu/education/graduate-program/"},
        "Biology": {"home": "https://biology.mit.edu/", "students": "https://biology.mit.edu/graduate/"},
        "Civil & Environmental Engineering": {"home": "https://cee.mit.edu/", "students": "https://cee.mit.edu/graduate/"},
        "Nuclear Engineering": {"home": "https://nse.mit.edu/", "students": "https://nse.mit.edu/education/graduate/"},
        "Aerospace Engineering": {"home": "https://aeroastro.mit.edu/", "students": "https://aeroastro.mit.edu/education/graduate/"},
    },
    "purdue": {
        "Electrical & Computer Engineering": {"home": "https://engineering.purdue.edu/ECE", "students": "https://engineering.purdue.edu/ECE/People/GraduateStudents"},
        "Computer Science": {"home": "https://www.cs.purdue.edu/", "students": "https://www.cs.purdue.edu/people/graduate-students.html"},
        "Mechanical Engineering": {"home": "https://engineering.purdue.edu/ME", "students": "https://engineering.purdue.edu/ME/Graduate"},
        "Aerospace Engineering": {"home": "https://engineering.purdue.edu/AAE", "students": "https://engineering.purdue.edu/AAE/academics/graduate"},
        "Chemical Engineering": {"home": "https://engineering.purdue.edu/ChE", "students": "https://engineering.purdue.edu/ChE/Graduate"},
        "Physics": {"home": "https://www.physics.purdue.edu/", "students": "https://www.physics.purdue.edu/"},
        "Chemistry": {"home": "https://www.chem.purdue.edu/", "students": "https://www.chem.purdue.edu/"},
        "Mathematics & Statistics": {"home": "https://www.math.purdue.edu/", "students": "https://www.math.purdue.edu/academic/grad/"},
        "Civil & Environmental Engineering": {"home": "https://engineering.purdue.edu/CE", "students": "https://engineering.purdue.edu/CE/Graduate"},
        "Materials Science & Engineering": {"home": "https://engineering.purdue.edu/MSE", "students": "https://engineering.purdue.edu/MSE/Graduate"},
        "Biomedical Engineering": {"home": "https://engineering.purdue.edu/BME", "students": "https://engineering.purdue.edu/BME/Graduate"},
    },
    "gatech": {
        "Electrical & Computer Engineering": {"home": "https://ece.gatech.edu/", "students": "https://ece.gatech.edu/academics/graduate-students"},
        "Computer Science": {"home": "https://scs.gatech.edu/", "students": "https://scs.gatech.edu/people/phd"},
        "Mechanical Engineering": {"home": "https://www.me.gatech.edu/", "students": "https://www.me.gatech.edu/"},
        "Aerospace Engineering": {"home": "https://ae.gatech.edu/", "students": "https://ae.gatech.edu/prospective-students/prospective-phd"},
        "Physics": {"home": "https://www.physics.gatech.edu/", "students": "https://www.physics.gatech.edu/"},
        "Chemistry": {"home": "https://www.chemistry.gatech.edu/", "students": "https://www.chemistry.gatech.edu/"},
        "Mathematics & Statistics": {"home": "https://www.math.gatech.edu/", "students": "https://www.math.gatech.edu/"},
        "Materials Science & Engineering": {"home": "https://www.mse.gatech.edu/", "students": "https://www.mse.gatech.edu/"},
        "Civil & Environmental Engineering": {"home": "https://ce.gatech.edu/", "students": "https://ce.gatech.edu/"},
        "Chemical Engineering": {"home": "https://chbe.gatech.edu/", "students": "https://chbe.gatech.edu/"},
        "Biomedical Engineering": {"home": "https://bme.gatech.edu/", "students": "https://bme.gatech.edu/"},
    },
    "stanford": {
        "Computer Science": {"home": "https://cs.stanford.edu/", "students": "https://cs.stanford.edu/directory/phd-students"},
        "Electrical Engineering": {"home": "https://ee.stanford.edu/", "students": "https://ee.stanford.edu/current-grads"},
        "Mechanical Engineering": {"home": "https://me.stanford.edu/", "students": "https://me.stanford.edu/academics-admissions/graduate-programs"},
        "Physics": {"home": "https://physics.stanford.edu/", "students": "https://physics.stanford.edu/graduate/graduate-students-overview"},
        "Chemistry": {"home": "https://chemistry.stanford.edu/", "students": "https://chemistry.stanford.edu/people/graduate-students"},
        "Mathematics & Statistics": {"home": "https://mathematics.stanford.edu/", "students": "https://mathematics.stanford.edu/academics/graduate-admissions"},
        "Materials Science & Engineering": {"home": "https://mse.stanford.edu/", "students": "https://mse.stanford.edu/academics-admissions/doctoral-program"},
        "Chemical Engineering": {"home": "https://cheme.stanford.edu/", "students": "https://cheme.stanford.edu/"},
        "Biology": {"home": "https://biology.stanford.edu/", "students": "https://biology.stanford.edu/"},
    },
    "vt": {
        "Electrical & Computer Engineering": {"home": "https://ece.vt.edu/", "students": "https://ece.vt.edu/grad.html"},
        "Mechanical Engineering": {"home": "https://me.vt.edu/", "students": "https://me.vt.edu/for-students/graduate.html"},
        "Computer Science": {"home": "https://cs.vt.edu/", "students": "https://cs.vt.edu/Graduate.html"},
        "Physics": {"home": "https://www.phys.vt.edu/", "students": "https://www.phys.vt.edu/"},
        "Chemistry": {"home": "https://www.chem.vt.edu/", "students": "https://www.chem.vt.edu/"},
        "Mathematics & Statistics": {"home": "https://math.vt.edu/", "students": "https://math.vt.edu/"},
        "Aerospace Engineering": {"home": "https://www.aoe.vt.edu/", "students": "https://www.aoe.vt.edu/"},
        "Civil & Environmental Engineering": {"home": "https://www.cee.vt.edu/", "students": "https://www.cee.vt.edu/"},
        "Materials Science & Engineering": {"home": "https://www.mse.vt.edu/", "students": "https://www.mse.vt.edu/"},
    },
    "iowa_state": {
        "Electrical & Computer Engineering": {"home": "https://www.ece.iastate.edu/", "students": "https://www.ece.iastate.edu/graduate-degree-programs/"},
        "Mechanical Engineering": {"home": "https://www.me.iastate.edu/", "students": "https://www.me.iastate.edu/graduate-programs/"},
        "Computer Science": {"home": "https://www.cs.iastate.edu/", "students": "https://www.cs.iastate.edu/"},
        "Physics": {"home": "https://www.physastro.iastate.edu/", "students": "https://www.physastro.iastate.edu/"},
        "Chemistry": {"home": "https://www.chem.iastate.edu/", "students": "https://www.chem.iastate.edu/"},
        "Mathematics & Statistics": {"home": "https://math.iastate.edu/", "students": "https://math.iastate.edu/academics/graduate/"},
        "Agriculture & Life Sciences": {"home": "https://www.cals.iastate.edu/", "students": "https://www.cals.iastate.edu/"},
    },
    "ucberkeley": {
        "Electrical & Computer Engineering": {"home": "https://eecs.berkeley.edu/", "students": "https://eecs.berkeley.edu/academics/graduate/"},
        "Computer Science": {"home": "https://eecs.berkeley.edu/", "students": "https://eecs.berkeley.edu/academics/graduate/"},
        "Mechanical Engineering": {"home": "https://me.berkeley.edu/", "students": "https://me.berkeley.edu/graduate/"},
        "Physics": {"home": "https://physics.berkeley.edu/", "students": "https://physics.berkeley.edu/directory"},
        "Chemistry": {"home": "https://chemistry.berkeley.edu/", "students": "https://chemistry.berkeley.edu/"},
        "Mathematics & Statistics": {"home": "https://math.berkeley.edu/", "students": "https://math.berkeley.edu/graduate"},
        "Civil & Environmental Engineering": {"home": "https://ce.berkeley.edu/", "students": "https://ce.berkeley.edu/"},
        "Materials Science & Engineering": {"home": "https://mse.berkeley.edu/", "students": "https://mse.berkeley.edu/"},
        "Chemical Engineering": {"home": "https://cheme.berkeley.edu/", "students": "https://cheme.berkeley.edu/"},
        "Biomedical Engineering": {"home": "https://bioeng.berkeley.edu/", "students": "https://bioeng.berkeley.edu/"},
    },
    "ucla": {
        "Electrical & Computer Engineering": {"home": "https://www.ee.ucla.edu/", "students": "https://www.ee.ucla.edu/"},
        "Computer Science": {"home": "https://www.cs.ucla.edu/", "students": "https://www.cs.ucla.edu/graduate-admissions/"},
        "Mechanical Engineering": {"home": "https://www.mae.ucla.edu/", "students": "https://www.mae.ucla.edu/"},
        "Physics": {"home": "https://www.pa.ucla.edu/", "students": "https://www.pa.ucla.edu/current-graduate-students.html"},
        "Chemistry": {"home": "https://www.chemistry.ucla.edu/", "students": "https://www.chemistry.ucla.edu/current-graduate-students"},
        "Mathematics & Statistics": {"home": "https://ww3.math.ucla.edu/", "students": "https://ww3.math.ucla.edu/"},
    },
    "cmu": {
        "Computer Science": {"home": "https://www.cs.cmu.edu/", "students": "https://www.cs.cmu.edu/directory/all"},
        "Electrical & Computer Engineering": {"home": "https://www.ece.cmu.edu/", "students": "https://www.ece.cmu.edu/directory/"},
        "Mechanical Engineering": {"home": "https://www.meche.engineering.cmu.edu/", "students": "https://www.meche.engineering.cmu.edu/education/graduate-programs/"},
        "Physics": {"home": "https://www.cmu.edu/physics/", "students": "https://www.cmu.edu/physics/"},
        "Chemistry": {"home": "https://www.cmu.edu/chemistry/", "students": "https://www.cmu.edu/chemistry/"},
        "Materials Science & Engineering": {"home": "https://www.cmu.edu/engineering/materials/", "students": "https://www.cmu.edu/engineering/materials/"},
    },
    "cornell": {
        "Electrical & Computer Engineering": {"home": "https://www.ece.cornell.edu/", "students": "https://www.ece.cornell.edu/ece/programs/graduate-programs"},
        "Computer Science": {"home": "https://www.cs.cornell.edu/", "students": "https://www.cs.cornell.edu/phd"},
        "Mechanical Engineering": {"home": "https://www.mae.cornell.edu/", "students": "https://www.mae.cornell.edu/"},
        "Physics": {"home": "https://physics.cornell.edu/", "students": "https://physics.cornell.edu/prospective-graduate-students"},
        "Chemistry": {"home": "https://chemistry.cornell.edu/", "students": "https://chemistry.cornell.edu/graduate"},
        "Mathematics & Statistics": {"home": "https://math.cornell.edu/", "students": "https://math.cornell.edu/graduate"},
        "Materials Science & Engineering": {"home": "https://www.mse.cornell.edu/", "students": "https://www.mse.cornell.edu/"},
        "Chemical Engineering": {"home": "https://www.cheme.cornell.edu/", "students": "https://www.cheme.cornell.edu/"},
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
