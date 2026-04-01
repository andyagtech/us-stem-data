#!/usr/bin/env python3
"""
Classify dissertation authors by department for NRA >= 40% universities.
Extracts department from oai_set (bepress) or subject (DSpace) fields.
Outputs .txt reports and JSON for the web interface.
"""

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from name_classifier import classify

# ── Department mappings from OAI set specs ──

MISSOURI_ST_DEPTS = {
    "chem": "Chemistry",
    "chem_dissert": "Chemistry",
    "chem-tds": "Chemistry",
    "phys": "Physics",
    "phys_dissert": "Physics",
    "physics-tds": "Physics",
    "ele_comeng": "Electrical & Computer Eng",
    "ele_comeng_dissert": "Electrical & Computer Eng",
    "ece-tds": "Electrical & Computer Eng",
    "geosci_geo_peteng": "Geosciences & Geological/Petroleum Eng",
    "geosci_geo_peteng_dissert": "Geosciences & Geological/Petroleum Eng",
    "geo-tds": "Geosciences & Geological/Petroleum Eng",
    "civarc_enveng": "Civil, Architectural & Environmental Eng",
    "civarc_enveng_dissert": "Civil, Architectural & Environmental Eng",
    "care-tds": "Civil, Architectural & Environmental Eng",
    "engman_syseng": "Engineering Mgmt & Systems Eng",
    "engman_syseng_dissert": "Engineering Mgmt & Systems Eng",
    "emse-tds": "Engineering Mgmt & Systems Eng",
    "che_bioeng": "Chemical & Biochemical Eng",
    "che_bioeng_dissert": "Chemical & Biochemical Eng",
    "chembiochem-tds": "Chemical & Biochemical Eng",
    "math_stat": "Mathematics & Statistics",
    "math_stat_dissert": "Mathematics & Statistics",
    "mathstat-tds": "Mathematics & Statistics",
    "min_nuceng": "Mining & Nuclear Eng",
    "min_nuceng_dissert": "Mining & Nuclear Eng",
    "minnuc-tds": "Mining & Nuclear Eng",
    "comsci": "Computer Science",
    "comsci_dissert": "Computer Science",
    "compsci-tds": "Computer Science",
    "matsci_eng": "Materials Science & Eng",
    "matsci_eng_dissert": "Materials Science & Eng",
    "matsci-tds": "Materials Science & Eng",
    "mec_aereng": "Mechanical & Aerospace Eng",
    "mec_aereng_dissert": "Mechanical & Aerospace Eng",
    "mechaero-tds": "Mechanical & Aerospace Eng",
    "nuclear": "Nuclear Eng",
    "nuclear-dissert": "Nuclear Eng",
    "nuclear-tds": "Nuclear Eng",
    "biosci": "Biological Sciences",
    "biosci_dissert": "Biological Sciences",
    "biosci-tds": "Biological Sciences",
    "psych": "Psychology",
    "psych-tds": "Psychology",
    "english": "English",
    "english-tds": "English",
    "history": "History",
    "history-tds": "History",
    "business": "Business & Information Technology",
    "business-tds": "Business & Information Technology",
}

MTU_DEPTS = {
    "mechanical": "Mechanical Eng",
    "mechanical-etd": "Mechanical Eng",
    "cee": "Civil & Environmental Eng",
    "cee-etd": "Civil & Environmental Eng",
    "ece": "Electrical & Computer Eng",
    "ece-etd": "Electrical & Computer Eng",
    "geo": "Geological & Mining Eng",
    "geo-etd": "Geological & Mining Eng",
    "biological": "Biological Sciences",
    "biological-etd": "Biological Sciences",
    "forest": "College of Forest Resources",
    "forestry-etd": "College of Forest Resources",
    "materials": "Materials Science & Eng",
    "materials-etd": "Materials Science & Eng",
    "chemical": "Chemical Eng",
    "chemical-etd": "Chemical Eng",
    "social-sciences": "Social Sciences",
    "social-sciences-etd": "Social Sciences",
    "physics": "Physics",
    "physics-etd": "Physics",
    "chemistry": "Chemistry",
    "chemistry-etd": "Chemistry",
    "cs": "Computer Science",
    "cs-etd": "Computer Science",
    "math": "Mathematical Sciences",
    "math-etd": "Mathematical Sciences",
    "biomedical": "Biomedical Eng",
    "biomedical-etd": "Biomedical Eng",
    "humanities": "Humanities",
    "humanities-etd": "Humanities",
    "kinesiology": "Kinesiology",
    "kinesiology-etd": "Kinesiology",
    "business": "Business",
    "business-etd": "Business",
    "environmental": "Environmental Eng",
    "environmental-etd": "Environmental Eng",
}

SDSU_DEPTS = {
    "plant": "Plant Science",
    "plant_etd": "Plant Science",
    "nrm": "Natural Resource Management",
    "nrm_etd": "Natural Resource Management",
    "con": "Construction & Operations Mgmt",
    "con_etd": "Construction & Operations Mgmt",
    "cvlee": "Civil & Environmental Eng",
    "cvlee_etd": "Civil & Environmental Eng",
    "dairy": "Dairy & Food Science",
    "dairy_etd": "Dairy & Food Science",
    "dairy_pubdb": "Dairy & Food Science",
    "hns": "Health & Nutritional Sciences",
    "hns_etd": "Health & Nutritional Sciences",
    "abe": "Agricultural & Biosystems Eng",
    "abe_etd": "Agricultural & Biosystems Eng",
    "ans": "Animal Science",
    "ans_etd": "Animal Science",
    "sociology": "Sociology & Rural Studies",
    "sociology_etd": "Sociology & Rural Studies",
    "ee-cs": "Electrical Eng & Computer Science",
    "ee-cs_etd": "Electrical Eng & Computer Science",
    "econ": "Economics",
    "econ_etd": "Economics",
    "biomicro": "Biology & Microbiology",
    "biomicro_etd": "Biology & Microbiology",
    "chem": "Chemistry & Biochemistry",
    "chem_etd": "Chemistry & Biochemistry",
    "comm-theatre": "Communication & Theatre",
    "comm-theatre_etd": "Communication & Theatre",
    "math": "Mathematics & Statistics",
    "math_etd": "Mathematics & Statistics",
    "gse": "Teaching, Learning & Leadership",
    "gse_etd": "Teaching, Learning & Leadership",
    "english": "English",
    "english_etd": "English",
    "pharmacy": "Pharmacy & Allied Health",
    "pharmacy_etd": "Pharmacy & Allied Health",
    "nursing": "Nursing",
    "nursing_etd": "Nursing",
    "me": "Mechanical Eng",
    "me_etd": "Mechanical Eng",
    "vet": "Veterinary & Biomedical Sciences",
    "vet_etd": "Veterinary & Biomedical Sciences",
    "ps": "Political Science",
    "ps_etd": "Political Science",
    "phys": "Physics",
    "phys_etd": "Physics",
    "geo": "Geography & Geospatial Sciences",
    "geo_etd": "Geography & Geospatial Sciences",
    "wild": "Wildlife, Fisheries & Aquaculture",
    "wild_etd": "Wildlife, Fisheries & Aquaculture",
}

ERAU_DEPTS = {
    "db-coa-dissertation": "College of Aviation",
    "db-coe-phd-aerospace-engineering": "Aerospace Eng",
    "db-coas-phd-human-factors": "Human Factors Psychology",
    "db-coas-phd-engineering-physics": "Engineering Physics",
    "db-coe-phd-mechanical-engineering": "Mechanical Eng",
    "db-coe-phd-electrical-computer": "Electrical & Computer Eng",
    "db-cob-phd-aviation-business-administration": "Aviation Business Admin",
}

RIT_DEPTS = {
    "theses": "All Departments",
}

STONY_BROOK_DEPTS = {}

# RPI: use subject field directly (it contains clean dept names)
# UT Dallas: use subject field
# U Missouri: use subject field

# ── Datasets (NRA >= 40%) ──

DATASETS = [
    {
        "key": "missouri_st", "name": "Missouri S&T", "nra_pct": 73.2,
        "file": "data/western_us_dissertations/missouri_st_etds.csv",
        "dept_source": "oai_set", "dept_map": MISSOURI_ST_DEPTS,
    },
    {
        "key": "mtu", "name": "Michigan Tech", "nra_pct": 62.0,
        "file": "data/western_us_dissertations/mtu_etds.csv",
        "dept_source": "oai_set", "dept_map": MTU_DEPTS,
    },
    {
        "key": "sdsu", "name": "SD State", "nra_pct": 59.6,
        "file": "data/western_us_dissertations/sdsu_etds.csv",
        "dept_source": "oai_set", "dept_map": SDSU_DEPTS,
    },
    {
        "key": "utdallas", "name": "UT Dallas", "nra_pct": 59.3,
        "file": "data/western_us_dissertations/utdallas_etds.csv",
        "dept_source": "subject", "dept_map": {},
    },
    {
        "key": "rit", "name": "RIT", "nra_pct": 57.3,
        "file": "data/western_us_dissertations/rit_etds.csv",
        "dept_source": "subject", "dept_map": {},
    },
    {
        "key": "erau", "name": "Embry-Riddle", "nra_pct": 52.3,
        "file": "data/western_us_dissertations/erau_etds.csv",
        "dept_source": "oai_set", "dept_map": ERAU_DEPTS,
    },
    {
        "key": "umissouri", "name": "U Missouri", "nra_pct": 50.2,
        "file": "data/western_us_dissertations/umissouri_etds.csv",
        "dept_source": "subject", "dept_map": {},
    },
    {
        "key": "stony_brook", "name": "Stony Brook", "nra_pct": 49.6,
        "file": "data/western_us_dissertations/stony_brook_etds.csv",
        "dept_source": "subject", "dept_map": {},
    },
    {
        "key": "rpi", "name": "RPI", "nra_pct": 48.7,
        "file": "data/western_us_dissertations/rpi_etds.csv",
        "dept_source": "subject", "dept_map": {},
    },
]


def extract_year(date_str):
    if not date_str:
        return None
    m = re.search(r'(\d{4})', date_str)
    return int(m.group(1)) if m else None


def extract_dept_from_oai_set(oai_set_str, dept_map):
    """Extract department name from semicolon-separated oai_set specs."""
    if not oai_set_str:
        return "Unknown"
    parts = [p.strip() for p in oai_set_str.split(";")]
    # Strip 'publication:' prefix
    clean = []
    for p in parts:
        if p.startswith("publication:"):
            clean.append(p[len("publication:"):])
        else:
            clean.append(p)
    # Find first match in dept_map
    for c in clean:
        if c in dept_map:
            return dept_map[c]
    return "Other/Unknown"


def extract_dept_from_subject(subject_str, university_key):
    """Extract department from subject field. Strategy depends on university."""
    if not subject_str or subject_str.lower() in ('', 'none provided'):
        return "Unknown"

    # RPI: subject IS the department name (clean single values)
    if university_key == "rpi":
        # Take first subject if semicolon separated
        subj = subject_str.split(";")[0].strip()
        # Normalize some common variations
        subj_lower = subj.lower()
        dept_norm = {
            "mechanical engineering": "Mechanical Eng",
            "electrical engineering": "Electrical Eng",
            "computer science": "Computer Science",
            "chemistry": "Chemistry",
            "physics": "Physics",
            "mathematics": "Mathematics",
            "chemical and biological engineering": "Chemical & Biological Eng",
            "chemical engineering": "Chemical Eng",
            "materials science and engineering": "Materials Science & Eng",
            "materials engineering": "Materials Science & Eng",
            "civil engineering": "Civil Eng",
            "civil and environmental engineering": "Civil & Environmental Eng",
            "environmental engineering": "Environmental Eng",
            "aerospace engineering": "Aerospace Eng",
            "nuclear engineering and science": "Nuclear Eng",
            "nuclear engineering": "Nuclear Eng",
            "biomedical engineering": "Biomedical Eng",
            "biology": "Biology",
            "communication and rhetoric": "Communication & Rhetoric",
            "electronic arts": "Electronic Arts",
            "information technology": "Information Technology",
            "science and technology studies": "Science & Technology Studies",
            "decision sciences and engineering systems": "Decision Sciences & Eng Systems",
            "industrial and management engineering": "Industrial & Management Eng",
            "geology": "Geology",
            "cognitive science": "Cognitive Science",
            "economics": "Economics",
            "architectural sciences": "Architectural Sciences",
            "multidisciplinary science": "Multidisciplinary Science",
        }
        for k, v in dept_norm.items():
            if subj_lower.startswith(k):
                return v
        # If short enough, use as-is
        if len(subj) <= 60:
            return subj.title() if subj == subj.lower() else subj
        return "Other/Unknown"

    # UT Dallas: subject often contains department-like info at the end
    if university_key == "utdallas":
        subj = subject_str
        # Look for known department patterns
        dept_patterns = {
            r"Electrical Eng": "Electrical Eng",
            r"Computer Science": "Computer Science",
            r"Mechanical Eng": "Mechanical Eng",
            r"Physics": "Physics",
            r"Chemistry": "Chemistry",
            r"Biomedical Eng": "Biomedical Eng",
            r"Materials Science": "Materials Science",
            r"Mathematics": "Mathematics",
            r"Biology": "Biology",
            r"Geosciences": "Geosciences",
            r"Psychology": "Psychology",
            r"Economics": "Economics",
            r"Political Science": "Political Science",
            r"Sociology": "Sociology",
            r"History": "History",
            r"Literature": "Literature",
            r"Business": "Business",
            r"Engineering": "Engineering (General)",
        }
        for pat, dept in dept_patterns.items():
            if re.search(pat, subj, re.IGNORECASE):
                return dept
        # Try the last semicolon-separated chunk (often the department)
        parts = [p.strip() for p in subj.split(";")]
        last = parts[-1] if parts else subj
        if len(last) <= 60 and last[0].isupper():
            return last
        return "Other/Unknown"

    # U Missouri: Library of Congress subjects — extract broad field
    if university_key == "umissouri":
        subj_lower = subject_str.lower()
        field_patterns = [
            (r"engineering|mechanical|electrical|civil|chemical eng|biomedical eng", "Engineering"),
            (r"computer|software|data processing|machine learning|artificial intellig", "Computer Science"),
            (r"chemistr", "Chemistry"),
            (r"physic(?!al edu)", "Physics"),
            (r"mathematic|algebra|topology|geometry|calculus|stochastic", "Mathematics"),
            (r"biolog|molecular|cell|gene|genom|microbiol|biochem|bioinformat|neurosci", "Biological Sciences"),
            (r"geolog|earth science|paleontol|mineral|stratigraphy|geophys|geochemist", "Geology/Earth Science"),
            (r"agri|agron|crop|soil|plant|horticultur|entomolog|animal sci|veterinar|dairy|poultry|livestock", "Agriculture & Life Sciences"),
            (r"education|teach|curricul|school|learn|instruct|pedagog|literacy", "Education"),
            (r"nurs", "Nursing"),
            (r"pharmac|drug|medic(?!al imag)|patholog|epidemiolog|public health|clinic", "Health Sciences"),
            (r"psych", "Psychology"),
            (r"econom|financ", "Economics"),
            (r"politic|govern|public admin|public policy", "Political Science"),
            (r"sociolog|social work|anthropolog", "Sociology/Social Work"),
            (r"histor", "History"),
            (r"english|liter|rhetoric|writing|poet|fiction|novel|drama|shakespeare", "English/Literature"),
            (r"music|compos|symphony|opera|concert", "Music"),
            (r"communicat|journal|media", "Communication/Journalism"),
            (r"law|legal|jurispruden", "Law"),
            (r"statistics|statistic", "Statistics"),
            (r"forestry|wildlife|ecolog|conserv|environment|natural resource", "Natural Resources & Environment"),
            (r"library|information science|archiv", "Library & Information Science"),
            (r"philosoph", "Philosophy"),
            (r"linguist|language|translat", "Linguistics"),
            (r"art|museum|design|visual", "Art & Design"),
            (r"business|management|market|account|entrepreneur|organizational", "Business"),
        ]
        for pattern, dept in field_patterns:
            if re.search(pattern, subj_lower):
                return dept
        return "Other/Unknown"

    # Stony Brook: subject field is sparse/inconsistent
    if university_key == "stony_brook":
        subj_lower = subject_str.lower()
        # Same broad field approach
        field_patterns = [
            (r"engineering|mechanical|electrical|civil|materials|biomedical eng", "Engineering"),
            (r"computer science|computing|algorithm|software", "Computer Science"),
            (r"chemistr", "Chemistry"),
            (r"physic(?!al edu)|quantum|particle|condensed matter", "Physics"),
            (r"mathematic|algebra|topology|geometry", "Mathematics"),
            (r"biolog|molecular|cell|gene|genom|microbiol|biochem|neurosci|ecology", "Biological Sciences"),
            (r"geolog|earth|ocean|atmosph|climate|marine|geophys", "Geosciences"),
            (r"psych", "Psychology"),
            (r"econom", "Economics"),
            (r"politic", "Political Science"),
            (r"sociolog|social|anthropol", "Sociology"),
            (r"histor", "History"),
            (r"english|liter|writing|comparat", "English/Literature"),
            (r"music|compos", "Music"),
            (r"philosoph", "Philosophy"),
            (r"linguist|language", "Linguistics"),
            (r"education|teach|school", "Education"),
            (r"nurs|health|public health|epidemiol", "Health Sciences"),
            (r"art|theater|cinema|visual", "Arts"),
        ]
        for pattern, dept in field_patterns:
            if re.search(pattern, subj_lower):
                return dept
        return "Other/Unknown"

    return "Other/Unknown"


def load_and_classify(dataset):
    """Load CSV and classify all records with department info."""
    filepath = dataset["file"]
    dept_source = dataset["dept_source"]
    dept_map = dataset["dept_map"]
    uni_key = dataset["key"]
    records = []

    with open(filepath, encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            creator = row.get('creator', '').strip()
            if not creator:
                continue
            if ';' in creator:
                creator = creator.split(';')[0].strip()

            cat, conf = classify(creator)
            year = extract_year(row.get('date', ''))

            if dept_source == "oai_set":
                dept = extract_dept_from_oai_set(row.get('oai_set', ''), dept_map)
            else:
                dept = extract_dept_from_subject(row.get('subject', ''), uni_key)

            records.append({
                'name': creator,
                'classification': cat,
                'confidence': conf,
                'year': year,
                'department': dept,
                'title': row.get('title', ''),
                'subject': row.get('subject', ''),
            })

    return records


def generate_dept_stats(records, min_count=10):
    """Generate per-department statistics. Returns sorted list of dept dicts."""
    dept_records = defaultdict(list)
    for r in records:
        dept_records[r['department']].append(r)

    dept_stats = []
    for dept, recs in dept_records.items():
        total = len(recs)
        if total < min_count:
            continue

        chinese = len([r for r in recs if r['classification'] == 'chinese'])
        chinese_high = len([r for r in recs if r['classification'] == 'chinese' and r['confidence'] == 'high'])
        indian = len([r for r in recs if r['classification'] == 'indian'])
        korean = len([r for r in recs if r['classification'] == 'korean'])
        vietnamese = len([r for r in recs if r['classification'] == 'vietnamese'])
        other = total - chinese - indian - korean - vietnamese

        # Recent years (2015+) only
        recent = [r for r in recs if r['year'] and r['year'] >= 2015]
        recent_chinese = len([r for r in recent if r['classification'] == 'chinese'])
        recent_total = len(recent)

        dept_stats.append({
            'department': dept,
            'total': total,
            'chinese': chinese,
            'chinese_high': chinese_high,
            'chinese_pct': round(chinese / total * 100, 1) if total else 0,
            'indian': indian,
            'indian_pct': round(indian / total * 100, 1) if total else 0,
            'korean': korean,
            'vietnamese': vietnamese,
            'kv': korean + vietnamese,
            'kv_pct': round((korean + vietnamese) / total * 100, 1) if total else 0,
            'other': other,
            'asian_est': chinese + indian + korean + vietnamese,
            'asian_pct': round((chinese + indian + korean + vietnamese) / total * 100, 1) if total else 0,
            'recent_total': recent_total,
            'recent_chinese': recent_chinese,
            'recent_chinese_pct': round(recent_chinese / recent_total * 100, 1) if recent_total else 0,
        })

    return sorted(dept_stats, key=lambda x: -x['chinese_pct'])


def print_dept_report(dataset, records, f=None):
    """Print department breakdown report for one university."""
    import builtins
    _print = builtins.print
    def out(*args, **kwargs):
        if f:
            kwargs['file'] = f
        _print(*args, **kwargs)

    name = dataset["name"]
    nra_pct = dataset["nra_pct"]

    out(f"\n{'='*80}")
    out(f"  {name}  (IPEDS NRA: {nra_pct}%)")
    out(f"{'='*80}")
    out(f"  Total records: {len(records)}")

    dept_stats = generate_dept_stats(records, min_count=5)
    if not dept_stats:
        out(f"  No departments with >= 5 records found.")
        return dept_stats

    out(f"  Departments with >= 5 records: {len(dept_stats)}")
    out(f"")
    out(f"  {'Department':<45} {'Total':>6} {'Chinese':>8} {'%':>6} {'Indian':>7} {'%':>6} {'K+V':>5} {'Asian%':>7}")
    out(f"  {'-'*90}")

    for d in dept_stats:
        out(f"  {d['department']:<45} {d['total']:>6} {d['chinese']:>8} {d['chinese_pct']:>5.1f}% {d['indian']:>7} {d['indian_pct']:>5.1f}% {d['kv']:>5} {d['asian_pct']:>6.1f}%")

    # Recent years comparison
    recent_depts = [d for d in dept_stats if d['recent_total'] >= 5]
    if recent_depts:
        out(f"\n  ── Recent (2015+) Chinese % by department ──")
        out(f"  {'Department':<45} {'2015+ Total':>12} {'Chinese':>8} {'%':>6}")
        out(f"  {'-'*75}")
        for d in sorted(recent_depts, key=lambda x: -x['recent_chinese_pct']):
            out(f"  {d['department']:<45} {d['recent_total']:>12} {d['recent_chinese']:>8} {d['recent_chinese_pct']:>5.1f}%")

    # Year-by-year for top departments
    top_depts_by_chinese = [d['department'] for d in dept_stats if d['chinese'] >= 10][:5]
    if top_depts_by_chinese:
        out(f"\n  ── Year-by-year Chinese % for top departments ──")
        years = sorted(set(r['year'] for r in records if r['year'] and r['year'] >= 2015))
        if years:
            header = f"  {'Year':>6}"
            for dept in top_depts_by_chinese:
                short = dept[:18]
                header += f" {short:>20}"
            out(header)
            out(f"  {'-'*(8 + 20*len(top_depts_by_chinese))}")

            for yr in years:
                line = f"  {yr:>6}"
                for dept in top_depts_by_chinese:
                    yr_recs = [r for r in records if r['year'] == yr and r['department'] == dept]
                    ch = len([r for r in yr_recs if r['classification'] == 'chinese'])
                    t = len(yr_recs)
                    if t >= 3:
                        line += f" {ch:>3}/{t:<3} ({ch/t*100:>4.0f}%){' '*3}"
                    elif t > 0:
                        line += f" {ch:>3}/{t:<3}        "
                    else:
                        line += f" {'':>20}"
                out(line)

    # Sample names from highest-Chinese-% department
    if dept_stats and dept_stats[0]['chinese'] >= 5:
        top_dept = dept_stats[0]['department']
        chinese_in_top = [r for r in records
                          if r['department'] == top_dept
                          and r['classification'] == 'chinese'
                          and r['year'] and r['year'] >= 2018]
        if chinese_in_top:
            out(f"\n  Sample Chinese names in {top_dept} (2018+, first 10):")
            for r in chinese_in_top[:10]:
                out(f"    {r['year']}  {r['name']:<35} [{r['confidence']}]  {r['title'][:55]}")

    return dept_stats


def main():
    all_university_data = []
    report_lines = []

    print("DEPARTMENT-LEVEL NAME CLASSIFICATION REPORT")
    print("=" * 80)
    print("Universities with IPEDS NRA% >= 40% (plus select others)")
    print("Classifying dissertation authors by department using name_classifier.py\n")

    report_path = Path("data/department_classification_reports")
    report_path.mkdir(parents=True, exist_ok=True)

    for ds in DATASETS:
        if not Path(ds["file"]).exists():
            print(f"\n  SKIPPING {ds['name']}: {ds['file']} not found")
            continue

        print(f"Processing {ds['name']}...", flush=True)
        records = load_and_classify(ds)

        # Write individual .txt report
        txt_path = report_path / f"{ds['key']}_department_report.txt"
        with open(txt_path, 'w') as f:
            dept_stats = print_dept_report(ds, records, f=f)

        # Also print to stdout
        dept_stats = print_dept_report(ds, records)

        # Collect for JSON export
        all_university_data.append({
            'key': ds['key'],
            'name': ds['name'],
            'nra_pct': ds['nra_pct'],
            'total_records': len(records),
            'departments': dept_stats,
            'records': [{
                'name': r['name'],
                'classification': r['classification'],
                'confidence': r['confidence'],
                'year': r['year'],
                'department': r['department'],
                'title': r['title'][:100],
            } for r in records],
        })

        print(f"  → {txt_path}")

    # Write combined .txt report
    combined_path = report_path / "all_departments_report.txt"
    with open(combined_path, 'w') as f:
        f.write("DEPARTMENT-LEVEL NAME CLASSIFICATION REPORT\n")
        f.write("=" * 80 + "\n")
        f.write("Universities with IPEDS NRA% >= 40%\n\n")
        for ds in DATASETS:
            if not Path(ds["file"]).exists():
                continue
            records = load_and_classify(ds)
            print_dept_report(ds, records, f=f)

    # Write JSON for web interface
    json_path = report_path / "department_data.json"
    with open(json_path, 'w') as f:
        json.dump(all_university_data, f, indent=1)

    print(f"\n{'='*80}")
    print(f"Reports written to {report_path}/")
    print(f"  Individual: <key>_department_report.txt")
    print(f"  Combined:   all_departments_report.txt")
    print(f"  JSON:       department_data.json")


if __name__ == "__main__":
    main()
