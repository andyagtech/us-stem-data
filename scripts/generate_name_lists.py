#!/usr/bin/env python3
"""
Generate verifiable name lists for top departments at high-NRA universities.
For each university, lists all PhD recipients in the highest Chinese-% departments
with direct URLs to the institutional repository for manual verification.
"""

import csv
import os
import re
import sys
from collections import defaultdict

csv.field_size_limit(1_000_000)  # Handle long description fields

sys.path.insert(0, os.path.dirname(__file__))
try:
    from name_classifier import classify
except ImportError:
    # Name classifier is optional — returns empty classification when unavailable
    def classify(name):
        return ('', '')

# ── Department extraction from OAI set specs ──

MISSOURI_ST_DEPTS = {
    "Mechanical & Aerospace Eng": ["mec_aereng", "mec_aereng_dissert", "mechaero-tds"],
    "Electrical & Computer Eng": ["ele_comeng", "ele_comeng_dissert", "ece-tds"],
    "Civil, Arch & Environmental Eng": ["civarc_enveng", "civarc_enveng_dissert", "care-tds"],
    "Chemistry": ["chem", "chem_dissert", "chem-tds"],
    "Materials Science & Eng": ["matsci_eng", "matsci_eng_dissert", "matsci-tds"],
    "Chemical & Biochemical Eng": ["che_bioeng", "che_bioeng_dissert", "chembiochem-tds"],
    "Computer Science": ["comsci", "comsci_dissert", "compsci-tds"],
    "Geosciences & Geo/Petroleum Eng": ["geosci_geo_peteng", "geosci_geo_peteng_dissert", "geo-tds"],
    "Physics": ["phys", "phys_dissert", "physics-tds"],
    "Mathematics & Statistics": ["math_stat", "math_stat_dissert", "mathstat-tds"],
    "Mining & Nuclear Eng": ["min_nuceng", "min_nuceng_dissert", "minnuc-tds"],
    "Engineering Mgmt & Systems Eng": ["engman_syseng", "engman_syseng_dissert", "emse-tds"],
}

MTU_DEPTS = {
    "Mathematical Sciences": ["math", "math-etd"],
    "Computer Science": ["cs", "cs-etd"],
    "Materials Science & Eng": ["materials", "materials-etd"],
    "Electrical & Computer Eng": ["ece", "ece-etd"],
    "Civil & Environmental Eng": ["cee", "cee-etd"],
    "Chemical Eng": ["chemical", "chemical-etd"],
    "Mechanical Eng": ["mechanical", "mechanical-etd"],
    "Physics": ["physics", "physics-etd"],
    "Chemistry": ["chemistry", "chemistry-etd"],
    "Biological Sciences": ["biological", "biological-etd"],
    "Geological & Mining Eng": ["geo", "geo-etd"],
}

SDSU_DEPTS = {
    "Electrical Eng & Computer Science": ["ee-cs", "ee-cs_etd"],
    "Chemistry & Biochemistry": ["chem", "chem_etd"],
    "Plant Science": ["plant", "plant_etd"],
    "Dairy & Food Science": ["dairy", "dairy_etd", "dairy_pubdb"],
    "Civil & Environmental Eng": ["cvlee", "cvlee_etd"],
    "Biology & Microbiology": ["biomicro", "biomicro_etd"],
    "Mathematics & Statistics": ["math", "math_etd"],
    "Mechanical Eng": ["me", "me_etd"],
    "Agricultural & Biosystems Eng": ["abe", "abe_etd"],
    "Animal Science": ["ans", "ans_etd"],
    "Natural Resource Management": ["nrm", "nrm_etd"],
    "Economics": ["econ", "econ_etd"],
    "Health & Nutritional Sciences": ["hns", "hns_etd"],
    "Pharmacy & Allied Health": ["pharmacy", "pharmacy_etd"],
    "Construction & Operations Mgmt": ["con", "con_etd"],
}

ERAU_DEPTS = {
    "College of Aviation": ["db-coa-dissertation"],
    "Aerospace Eng": ["db-coe-phd-aerospace-engineering"],
    "Human Factors Psychology": ["db-coas-phd-human-factors"],
    "Engineering Physics": ["db-coas-phd-engineering-physics"],
    "Mechanical Eng": ["db-coe-phd-mechanical-engineering"],
    "Electrical & Computer Eng": ["db-coe-phd-electrical-computer"],
}

RIT_DEPTS = {
    "Kate Gleason College of Eng": ["KGCOE"],
    "Golisano College of Computing": ["GCCIS", "cs", "cis"],
    "College of Science": ["COS", "spas"],
    "College of Applied Science & Tech": ["CAST", "mmet"],
    "College of Imaging Arts & Sciences": ["CIAS", "art"],
    "School of Design": ["sd"],
}

NJIT_DEPTS = {
    "Computer Science": ["csit"],
    "Electrical & Computer Eng": ["ece"],
    "Chemical & Materials Eng": ["chem_bio_pharm"],
    "Civil & Environmental Eng": ["cee"],
    "Mechanical & Industrial Eng": ["mie"],
    "Mathematical Sciences": ["math"],
    "Physics": ["physics"],
    "Biomedical Eng": ["bme"],
    "Information Systems": ["is"],
}

# ── Subject-based department extraction ──


def extract_dept_from_contributor_ubuffalo(contributor):
    """U Buffalo: department name in contributor field after advisor name."""
    if not contributor:
        return None
    parts = [p.strip() for p in contributor.split(';')]
    norm = {
        'mechanical and aerospace engineering': 'Mechanical & Aerospace Eng',
        'computer science and engineering': 'Computer Science & Eng',
        'chemical and biological engineering': 'Chemical & Biological Eng',
        'electrical engineering': 'Electrical Eng',
        'civil, structural and environmental engineering': 'Civil & Environmental Eng',
        'industrial and systems engineering': 'Industrial & Systems Eng',
        'biomedical engineering': 'Biomedical Eng',
        'chemistry': 'Chemistry',
        'physics': 'Physics',
        'mathematics': 'Mathematics',
        'biological sciences': 'Biological Sciences',
        'pharmaceutical sciences': 'Pharmaceutical Sciences',
        'psychology': 'Psychology',
        'political science': 'Political Science',
        'sociology': 'Sociology',
        'economics': 'Economics',
        'philosophy': 'Philosophy',
        'history': 'History',
        'english': 'English',
        'linguistics': 'Linguistics',
        'communicative disorders and sciences': 'Communication Sciences',
        'counseling, school and educational psychology': 'Education',
        'learning and instruction': 'Education',
        'educational leadership and policy': 'Education',
        'global gender and sexuality studies': 'Gender Studies',
        'geography': 'Geography',
        'geology': 'Geology',
        'exercise and nutrition sciences': 'Exercise & Nutrition Sciences',
        'pathology and anatomical sciences': 'Pathology',
        'oral biology': 'Oral Biology',
        'oral sciences': 'Oral Sciences',
        'engineering science': 'Engineering Science',
        'computational and data enabled sciences': 'Data Science',
        'nuclear engineering': 'Nuclear Eng',
        'architecture': 'Architecture',
        'urban and regional planning': 'Urban Planning',
        'music': 'Music',
        'theatre and dance': 'Theatre & Dance',
    }
    for p in parts:
        pl = p.strip().lower()
        if pl in norm:
            return norm[pl]
    return None


UTARLINGTON_DEPTS = {
    "Bioengineering": ["bioengineering_dissertations"],
    "Biology": ["biology_dissertations"],
    "Chemistry": ["chemistry_dissertations"],
    "Civil Eng": ["civilengineering_dissertations"],
    "Computer Science & Eng": ["cse_dissertations"],
    "Earth & Environmental Sci": ["ees_dissertations"],
    "Electrical Eng": ["electricaleng_dissertations"],
    "Industrial & Manufacturing Eng": ["industrialmanusys_dissertations"],
    "Materials Science & Eng": ["materialscieng_dissertations"],
    "Mathematics": ["math_dissertations"],
    "Mechanical & Aerospace Eng": ["mechaerospace_dissertations"],
    "Physics": ["physics_dissertations"],
    "Psychology": ["psychology_dissertations"],
    "Kinesiology": ["kinesiology_dissertations"],
    "Nursing": ["nursing_dissertations"],
    "Education": ["edleadershippolicy_dissertations"],
    "English": ["english_dissertations"],
    "History": ["history_dissertations"],
    "Business Admin": ["businessadmin_dissertations"],
    "Info Systems & Ops Mgmt": ["infosystemsopmanage_dissertations"],
    "Linguistics & TESOL": ["linguistics_tesol_dissertations"],
    "Public Affairs": ["publicaffairs_dissertations"],
    "Social Work": ["socialwork_dissertations"],
    "Planning": ["planning_dissertations"],
}


def extract_dept_from_contributor_gatech(contributor):
    """Georgia Tech: department name is one of the semicolon-separated contributor entries."""
    if not contributor:
        return None
    parts = [p.strip() for p in contributor.split(';')]
    norm = {
        'electrical and computer engineering': 'Electrical & Computer Eng',
        'mechanical engineering': 'Mechanical Eng',
        'chemical engineering': 'Chemical Eng',
        'chemical and biomolecular engineering': 'Chemical & Biomolecular Eng',
        'civil and environmental engineering': 'Civil & Environmental Eng',
        'civil engineering': 'Civil & Environmental Eng',
        'aerospace engineering': 'Aerospace Eng',
        'aeronautical engineering': 'Aerospace Eng',
        'industrial and systems engineering': 'Industrial & Systems Eng',
        'industrial engineering': 'Industrial & Systems Eng',
        'biomedical engineering': 'Biomedical Eng',
        'biomedical engineering (joint gt/emory department)': 'Biomedical Eng',
        'materials science and engineering': 'Materials Science & Eng',
        'computer science': 'Computer Science',
        'chemistry and biochemistry': 'Chemistry',
        'chemistry': 'Chemistry',
        'physics': 'Physics',
        'mathematics': 'Mathematics',
        'biology': 'Biology',
        'earth and atmospheric sciences': 'Earth & Atmospheric Sciences',
        'psychology': 'Psychology',
        'public policy': 'Public Policy',
        'architecture': 'Architecture',
        'city and regional planning': 'City & Regional Planning',
        'nuclear and radiological engineering': 'Nuclear Eng',
        'institute of paper science and technology': 'Paper Science & Technology',
    }
    for p in parts:
        pl = p.strip().lower()
        if pl in norm:
            return norm[pl]
    return None


def extract_dept_from_contributor_vt(contributor):
    """Virginia Tech: department name appears in contributor, sometimes prefixed with 'Department of'."""
    if not contributor:
        return None
    parts = [p.strip() for p in contributor.split(';')]
    norm = {
        'mechanical engineering': 'Mechanical Eng',
        'electrical and computer engineering': 'Electrical & Computer Eng',
        'electrical engineering': 'Electrical & Computer Eng',
        'civil engineering': 'Civil Eng',
        'civil and environmental engineering': 'Civil & Environmental Eng',
        'chemical engineering': 'Chemical Eng',
        'aerospace and ocean engineering': 'Aerospace & Ocean Eng',
        'industrial and systems engineering': 'Industrial & Systems Eng',
        'biomedical engineering and mechanics': 'Biomedical Eng',
        'engineering mechanics': 'Engineering Mechanics',
        'engineering science and mechanics': 'Engineering Science & Mechanics',
        'materials science and engineering': 'Materials Science & Eng',
        'biological systems engineering': 'Biological Systems Eng',
        'mining and minerals engineering': 'Mining & Minerals Eng',
        'computer science': 'Computer Science',
        'computer science and applications': 'Computer Science',
        'chemistry': 'Chemistry',
        'physics': 'Physics',
        'mathematics': 'Mathematics',
        'statistics': 'Statistics',
        'biology': 'Biology',
        'biochemistry': 'Biochemistry',
        'geosciences': 'Geosciences',
        'psychology': 'Psychology',
        'economics': 'Economics',
        'political science': 'Political Science',
        'sociology': 'Sociology',
        'educational leadership and policy studies': 'Education',
        'teaching and learning': 'Education',
        'curriculum and instruction': 'Education',
        'food science and technology': 'Food Science & Technology',
        'animal and poultry sciences': 'Animal Sciences',
        'crop and soil environmental sciences': 'Crop & Soil Sciences',
        'fisheries and wildlife sciences': 'Fisheries & Wildlife',
        'forestry': 'Forestry',
        'entomology': 'Entomology',
        'horticulture': 'Horticulture',
        'plant pathology, physiology, and weed science': 'Plant Pathology',
        'environmental engineering': 'Environmental Eng',
        'human nutrition, foods, and exercise': 'Human Nutrition',
    }
    for p in parts:
        pl = p.strip().lower()
        # Strip "Department of " prefix
        if pl.startswith('department of '):
            pl = pl[len('department of '):]
        if pl in norm:
            return norm[pl]
    return None


def extract_dept_from_subject_generic(subject):
    """Generic department extractor using regex on the subject field.
    Works for most bepress/DSpace schools where subject contains discipline names."""
    if not subject:
        return None
    sl = subject.lower()
    # Order: more specific patterns first to avoid over-broad matches
    patterns = [
        # Engineering disciplines
        (r"mechanical eng", "Mechanical Eng"),
        (r"electrical and computer eng|electrical eng|electronics? eng|electrical and electronics", "Electrical & Computer Eng"),
        (r"civil and environmental eng|civil eng", "Civil & Environmental Eng"),
        (r"chemical and biochemical eng|chemical eng", "Chemical Eng"),
        (r"biomedical eng|bioengineering", "Biomedical Eng"),
        (r"materials sci|materials eng", "Materials Science & Eng"),
        (r"aerospace eng|aeronaut", "Aerospace Eng"),
        (r"industrial eng", "Industrial Eng"),
        (r"environmental eng|environmental sci", "Environmental Eng"),
        (r"nuclear eng", "Nuclear Eng"),
        (r"transportation eng|transportation sci", "Transportation Eng"),
        (r"mining eng|petroleum eng", "Mining/Petroleum Eng"),
        (r"(?:^|\W)engineering(?:\W|$)", "Engineering"),
        # Computing
        (r"computer science|computer engineering|computational science|computing", "Computer Science"),
        (r"data science|machine learning|artificial intelligence", "Data Science"),
        (r"management information|information system|information technol", "Information Systems"),
        (r"cybersecur|network secur", "Computer Science"),
        # Math & Stats
        (r"applied mathematic", "Applied Mathematics"),
        (r"mathematic|statistics|statistical|biostatistic", "Mathematics/Statistics"),
        (r"operations research", "Operations Research"),
        # Physical Sciences
        (r"organic chemistr|analytical chemistr|polymer chemistr|physical chemistr|inorganic chemistr", "Chemistry"),
        (r"biochemistr", "Biochemistry"),
        (r"chemistr", "Chemistry"),
        (r"condensed matter|atomic physic|nuclear physic|particle physic|plasma physic|quantum", "Physics"),
        (r"(?<!geop)(?<!biop)physic(?!al edu|s edu|al ther|olog|ian)", "Physics"),
        (r"pure sciences", "Physics"),
        (r"optics|photonics|laser", "Physics"),
        # Life Sciences
        (r"bioinformat", "Bioinformatics"),
        (r"molecular bio|cell bio|cellular bio", "Molecular/Cell Biology"),
        (r"microbiol", "Microbiology"),
        (r"neurosci|neurobio|neurolog", "Neuroscience"),
        (r"genetics|genomics|proteom", "Genetics"),
        (r"ecology|evolution(?!ary psych)|zoolog|entomol|wildlife|conservation bio", "Ecology/Evolution"),
        (r"biolog(?!ical eng)|biotech|life sci", "Biology"),
        (r"immunol|pathobiol|pathol(?!ogy of build)", "Biology"),
        # Earth & Atmospheric
        (r"geolog|geoscience|geophys|earth sci|geochemist|paleontol|mineral|seismol", "Geosciences"),
        (r"ocean|atmosph|climate|meteorol|hydrol", "Atmospheric/Ocean Sciences"),
        # Agriculture
        (r"agri|agron|crop|soil sci|horticultur|animal sci|veterinar|food sci|plant (?:sci|bio|path)|forest", "Agriculture & Life Sciences"),
        # Social Sciences
        (r"clinical psych|educational psych|cognitive psych|social psych|developmental psych", "Psychology"),
        (r"psych", "Psychology"),
        (r"econom|financ", "Economics"),
        (r"politic|govern|public admin|public policy", "Political Science"),
        (r"sociolog|social work|anthropolog|criminol", "Sociology"),
        (r"commun(?:ication|ications)\b", "Communication"),
        # Education & Humanities
        (r"educational leader|curriculum|teacher edu|higher edu|special edu", "Education"),
        (r"education(?!al psych)", "Education"),
        (r"histor", "History"),
        (r"english|liter|rhetoric|writing|linguist|compar.+liter", "English/Literature"),
        (r"philosoph", "Philosophy"),
        (r"music|compos", "Music"),
        (r"theolog|divinity|religio", "Religious Studies"),
        (r"art\b|fine arts|visual arts", "Art"),
        (r"theater|theat|drama|performing art", "Theater"),
        # Health
        (r"nurs", "Nursing"),
        (r"pharmac|public health|epidemiol|health sci|health and environ|rehabilitation", "Health Sciences"),
        (r"kinesiol|exercise sci|biomech|sport sci", "Kinesiology"),
        (r"dentist|oral", "Health Sciences"),
        # Business
        (r"business|management(?! info)|marketing|account|supply chain|logistics", "Business"),
        # Nanoscience
        (r"nanoscience|nanotech|nanopart", "Nanoscience"),
        # Broad categories (last resort)
        (r"applied sci", "Engineering"),
        (r"technology and innovation", "Engineering"),
        (r"natural resource|environ.*manage", "Agriculture & Life Sciences"),
    ]
    for pat, dept in patterns:
        if re.search(pat, sl):
            return dept
    return None

def extract_dept_from_subject_rpi(subject):
    if not subject or subject.lower() in ('', 'none provided'):
        return None
    subj = subject.split(";")[0].strip()
    norm = {
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
        "decision sciences and engineering systems": "Decision Sciences & Eng Systems",
        "industrial and management engineering": "Industrial & Management Eng",
        "geology": "Geology",
        "cognitive science": "Cognitive Science",
        "communication and rhetoric": "Communication & Rhetoric",
        "electronic arts": "Electronic Arts",
        "information technology": "Information Technology",
        "science and technology studies": "Science & Technology Studies",
        "architectural sciences": "Architectural Sciences",
        "computer and systems engineering": "Computer & Systems Eng",
        "computer": "Computer & Systems Eng",
    }
    sl = subj.lower()
    for k, v in norm.items():
        if sl.startswith(k):
            return v
    if len(subj) <= 50:
        return subj.title() if subj == subj.lower() else subj
    return None


def extract_dept_from_subject_utdallas(subject):
    if not subject:
        return None
    # UT Dallas subjects often end with field name after semicolons
    parts = [p.strip() for p in subject.split(";")]
    # Look for department-like entries
    dept_patterns = [
        (r"[Ee]lectrical [Ee]ng", "Electrical Eng"),
        (r"[Cc]omputer [Ss]cience", "Computer Science"),
        (r"[Mm]echanical [Ee]ng", "Mechanical Eng"),
        (r"[Pp]hysics", "Physics"),
        (r"[Cc]hemistry", "Chemistry"),
        (r"[Bb]iomedical [Ee]ng", "Biomedical Eng"),
        (r"[Mm]aterials [Ss]cience", "Materials Science"),
        (r"[Mm]athematics", "Mathematics"),
        (r"[Bb]iology|[Mm]olecular [Bb]iology", "Biology"),
        (r"[Gg]eosciences", "Geosciences"),
        (r"[Pp]sychology", "Psychology"),
        (r"[Ee]conomics", "Economics"),
        (r"[Pp]olitical [Ss]cience", "Political Science"),
        (r"[Ss]ociology", "Sociology"),
        (r"[Hh]istory", "History"),
        (r"[Ll]iterature|[Ll]iterary", "Literature"),
        (r"[Bb]usiness|[Mm]anagement|[Mm]arket", "Business"),
        (r"[Nn]euroscience", "Neuroscience"),
        (r"[Ss]tatistics|[Ss]tatistical", "Statistics"),
    ]
    subj = subject
    for pat, dept in dept_patterns:
        if re.search(pat, subj):
            return dept
    return None


def extract_dept_from_subject_umissouri(subject):
    if not subject:
        return None
    sl = subject.lower()
    patterns = [
        (r"engineering|mechanical|electrical|civil|chemical eng|biomedical eng|industrial eng", "Engineering"),
        (r"computer|software|data processing|machine learning|artificial intellig|informatics", "Computer Science"),
        (r"chemistr", "Chemistry"),
        (r"physic(?!al edu)|quantum|particle|optic", "Physics"),
        (r"mathematic|algebra|topology|geometry|calculus|stochastic|statistic", "Mathematics/Statistics"),
        (r"biolog|molecular|cell|gene|genom|microbiol|biochem|bioinformat|neurosci", "Biological Sciences"),
        (r"geolog|earth science|paleontol|mineral|geophys|geochemist", "Geology/Earth Science"),
        (r"agri|agron|crop|soil|plant|horticultur|entomolog|animal sci|veterinar|dairy|poultry", "Agriculture & Life Sciences"),
        (r"education|teach|curricul|school|learn|instruct|pedagog|literacy", "Education"),
        (r"nurs", "Nursing"),
        (r"pharmac|drug|medic|patholog|epidemiolog|public health|clinic", "Health Sciences"),
        (r"psych", "Psychology"),
        (r"econom|financ", "Economics"),
        (r"politic|govern|public admin|public policy", "Political Science"),
        (r"sociolog|social work|anthropolog", "Sociology/Social Work"),
        (r"histor", "History"),
        (r"english|liter|rhetoric|writing|poet|fiction|drama", "English/Literature"),
        (r"music|compos|symphony|opera|concert", "Music"),
        (r"communicat|journal|media", "Communication/Journalism"),
        (r"forestry|wildlife|ecolog|conserv|environment|natural resource", "Natural Resources & Environment"),
        (r"business|management|market|account|entrepreneur", "Business"),
    ]
    for pat, dept in patterns:
        if re.search(pat, sl):
            return dept
    return None


def extract_dept_from_subject_stonybrook(subject):
    if not subject:
        return None
    sl = subject.lower()
    patterns = [
        (r"mechanical eng|materials sci", "Mechanical/Materials Eng"),
        (r"electrical eng|electronics", "Electrical Eng"),
        (r"computer science|computing|algorithm|software", "Computer Science"),
        (r"biomedical eng", "Biomedical Eng"),
        (r"civil eng", "Civil Eng"),
        (r"chemical eng", "Chemical Eng"),
        (r"chemistr", "Chemistry"),
        (r"physic|quantum|particle|condensed matter|optic", "Physics"),
        (r"mathematic|algebra|topology|geometry", "Mathematics"),
        (r"biolog|molecular|cell|gene|genom|microbiol|biochem|neurosci|ecology|evolution", "Biological Sciences"),
        (r"geolog|earth|ocean|atmosph|climate|marine|geophys", "Geosciences"),
        (r"psych", "Psychology"),
        (r"econom", "Economics"),
        (r"politic", "Political Science"),
        (r"sociolog|social|anthropol", "Sociology/Anthropology"),
        (r"histor", "History"),
        (r"english|liter|writing|comparat", "English/Literature"),
        (r"music|compos|violin|piano|cello|viola|voice|clarinet|flute|bassoon|percussion|harpsichord|trumpet|guitar|saxophone|oboe|harp|organ|trombone|conducting", "Music"),
        (r"philosoph", "Philosophy"),
        (r"linguist|language", "Linguistics"),
        (r"education|teach|school", "Education"),
        (r"nurs|health|public health|epidemiol", "Health Sciences"),
        (r"art|theater|cinema|visual", "Arts"),
        (r"stony brook|test", None),  # junk
    ]
    for pat, dept in patterns:
        if re.search(pat, sl):
            return dept
    return None


# ── Main ──

def extract_year(date_str):
    m = re.search(r'(\d{4})', date_str or '')
    return int(m.group(1)) if m else None


def get_dept_from_oai(oai_set, dept_map):
    parts = [p.strip().replace('publication:', '') for p in oai_set.split(';')]
    for dept_name, keywords in dept_map.items():
        for kw in keywords:
            if kw in parts:
                return dept_name
    return None


def normalize_stanford_dept(dept):
    """Normalize Stanford department field to short department name."""
    if not dept:
        return None
    # Strip trailing period, "Stanford University" prefix, and "Department of"
    d = dept.strip().rstrip('.')
    d = re.sub(r'^Stanford University[,\s]*', '', d)
    d = re.sub(r'^Department of\s+', '', d)
    d = re.sub(r'\s+Department$', '', d)
    d = d.strip()
    if not d:
        return None
    # Normalize common names
    norm = {
        'electrical engineering': 'Electrical Eng',
        'mechanical engineering': 'Mechanical Eng',
        'computer science': 'Computer Science',
        'chemistry': 'Chemistry',
        'physics': 'Physics',
        'biology': 'Biology',
        'mathematics': 'Mathematics',
        'chemical engineering': 'Chemical Eng',
        'materials science and engineering': 'Materials Science & Eng',
        'applied physics': 'Applied Physics',
        'bioengineering': 'Bioengineering',
        'aeronautics and astronautics': 'Aero & Astro',
        'civil & environmental engineering': 'Civil & Environmental Eng',
        'civil and environmental engineering': 'Civil & Environmental Eng',
        'management science and engineering': 'Management Science & Eng',
        'petroleum engineering': 'Petroleum Eng',
        'energy resources engineering': 'Energy Resources Eng',
        'economics': 'Economics',
        'psychology': 'Psychology',
        'political science': 'Political Science',
        'sociology': 'Sociology',
        'history': 'History',
        'english': 'English',
        'philosophy': 'Philosophy',
        'linguistics': 'Linguistics',
        'music': 'Music',
        'education': 'Education',
        'communication': 'Communication',
        'statistics': 'Statistics',
        'genetics': 'Genetics',
        'neurosciences': 'Neurosciences',
        'immunology': 'Immunology',
        'biophysics': 'Biophysics',
        'biochemistry': 'Biochemistry',
        'structural biology': 'Structural Biology',
        'developmental biology': 'Developmental Biology',
        'microbiology and immunology': 'Microbiology & Immunology',
        'cancer biology': 'Cancer Biology',
    }
    dl = d.lower()
    if dl in norm:
        return norm[dl]
    # Program in X → X
    m = re.match(r'(?:Program in\s+)(.*)', d, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Return cleaned name if not in norm map
    return d


def get_url(row):
    url = row.get('url', '').strip()
    identifier = row.get('identifier', '').strip()
    eschol = row.get('escholarship_url', '').strip()
    purl = row.get('purl', '').strip()
    link = url or eschol or purl or identifier
    if not link:
        return ''
    if ';' in link:
        parts = [p.strip() for p in link.split(';')]
        http_parts = [p for p in parts if p.startswith('http')]
        link = http_parts[0] if http_parts else parts[0]
    return link


CONFIGS = [
    {
        'key': 'missouri_st', 'name': 'Missouri S&T', 'nra': 74.3,
        'file': 'data/western_us_dissertations/missouri_st_etds.csv',
        'dept_source': 'oai_set', 'dept_map': MISSOURI_ST_DEPTS,
        'years': (2010, 2026),
        'degree_label': 'phd',  # OAI set is publication:doctoral_dissertations only
    },
    {
        'key': 'missouri_st', 'name': 'Missouri S&T', 'nra': 74.3,
        'file': 'data/western_us_dissertations/missouri_st_masters.csv',
        'dept_source': 'oai_set', 'dept_map': MISSOURI_ST_DEPTS,
        'years': (2010, 2026),
        'degree_label': 'ms',  # OAI set is publication:masters_theses only
        '_merge': True,  # merge into existing missouri_st entry
    },
    {
        'key': 'mtu', 'name': 'Michigan Tech', 'nra': 66.7,
        'file': 'data/western_us_dissertations/mtu_etds.csv',
        'dept_source': 'oai_set', 'dept_map': MTU_DEPTS,
        'years': (2010, 2026),
    },
    {
        'key': 'sdsu', 'name': 'SD State', 'nra': 64.5,
        'file': 'data/western_us_dissertations/sdsu_etds.csv',
        'dept_source': 'oai_set', 'dept_map': SDSU_DEPTS,
        'years': (2010, 2026),
    },
    {
        'key': 'utdallas', 'name': 'UT Dallas', 'nra': 66.1,
        'file': 'data/western_us_dissertations/utdallas_etds.csv',
        'dept_source': 'subject_utdallas', 'dept_map': {},
        'years': (2010, 2026),
        'exclude_type': 'article|image|photograph|journal|newsletter',
    },
    {
        'key': 'utdallas', 'name': 'UT Dallas', 'nra': 66.1,
        'file': 'data/western_us_dissertations/utdallas_gradschool_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2020, 2025),
        'degree_label': 'phd',  # All records from grad school are PhDs
        '_merge': True,  # Merge with OAI data (don't overwrite)
    },
    {
        'key': 'stony_brook', 'name': 'Stony Brook', 'nra': 58.8,
        'file': 'data/western_us_dissertations/stony_brook_dspace_etds.csv',  # REST API harvest (bepress OAI was incomplete)
        'dept_source': 'subject_stonybrook', 'dept_map': {},
        # dc.type is the only degree signal; confirmed against the ProQuest file
        # naming on the item pages (…_0771E_… doctoral, …_0771M_… master's).
        'thesis_vocab_field': 'type',
        'years': (2010, 2026),
    },
    {
        # Added 2026-08-22. The corpus was harvested and re-harvested all along
        # (4,240 records, 100% with a real award date) but no config claimed it,
        # so 3,974 matched LCA filings and every one of those records reached no
        # page. enrich reported the orphan on every run.
        #
        # Its OAI feed types every record as "Thesis" with no degree level, so
        # the PhD/master's split is unknown here and the page will show a 0%
        # labelling rate. That is a real limitation of the source, disclosed by
        # the same mechanism that flags every other low-labelling university --
        # not a reason to keep the records invisible.
        'key': 'osu', 'name': 'Ohio State', 'nra': 46.9,
        'file': 'data/western_us_dissertations/osu_etds.csv',
        'dept_source': 'subject', 'years': (2010, 2026),
    },
    {
        'key': 'rpi', 'name': 'RPI', 'nra': 48.7,
        'file': 'data/western_us_dissertations/rpi_etds.csv',
        'dept_source': 'subject_rpi', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'umissouri', 'name': 'U Missouri', 'nra': 50.2,
        'file': 'data/western_us_dissertations/umissouri_etds.csv',
        'dept_source': 'subject_umissouri', 'dept_map': {},
        'years': (2010, 2026),
    },
    # ── Phase 1 additions: high-NRA schools with existing data ──
    {
        'key': 'njit', 'name': 'NJIT', 'nra': 70.7,
        'file': 'data/western_us_dissertations/njit_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'degree_label': 'phd',  # OAI set is publication:dissertations; all URLs are /dissertations/
    },
    {
        'key': 'njit', 'name': 'NJIT', 'nra': 70.7,
        'file': 'data/western_us_dissertations/njit_theses.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'degree_label': 'ms',  # OAI set is publication:theses
        '_merge': True,
    },
    {
        'key': 'purdue', 'name': 'Purdue', 'nra': 60.3,
        'file': 'data/western_us_dissertations/purdue_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'kstate', 'name': 'Kansas State', 'nra': 58.3,
        'file': 'data/western_us_dissertations/kstate_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'rit', 'name': 'RIT', 'nra': 57.1,
        'file': 'data/western_us_dissertations/rit_etds.csv',
        'dept_source': 'oai_set', 'dept_map': RIT_DEPTS,
        'years': (2010, 2026),
    },
    {
        'key': 'binghamton', 'name': 'Binghamton', 'nra': 56.9,
        'file': 'data/western_us_dissertations/binghamton_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026), 'allow_no_date': True,
    },
    {
        'key': 'iowa_state', 'name': 'Iowa State', 'nra': 56.0,
        'file': 'data/western_us_dissertations/iowa_state_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        # Was (2019, 2026) to dodge 23K bulk imports all stamped 2018.
        # date_issued spreads those 24,697 records across many years
        # (2018 itself holds 203), so the workaround now only discards
        # real 2016-2018 awards. Standard window.
        'years': (2010, 2026),
        'exclude_type': 'article',  # Exclude "article; dissertation" and "article; thesis" records
    },
    {
        'key': 'clemson', 'name': 'Clemson', 'nra': 55.2,
        'file': 'data/western_us_dissertations/clemson_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'phd_sets': ['publication:all_dissertations'],
        'ms_sets': ['publication:all_theses'],
        'years': (2010, 2026),
    },
    {
        'key': 'ucf', 'name': 'UCF', 'nra': 53.8,
        'file': 'data/western_us_dissertations/ucf_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'vt', 'name': 'Virginia Tech', 'nra': 53.6,
        'file': 'data/western_us_dissertations/vt_etds.csv',
        'dept_source': 'contributor_vt', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'lsu', 'name': 'LSU', 'nra': 52.3,
        'file': 'data/western_us_dissertations/lsu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'gatech', 'name': 'Georgia Tech', 'nra': 52.4,
        'file': 'data/western_us_dissertations/gatech_etds.csv',
        'dept_source': 'contributor_gatech', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'unl', 'name': 'U Nebraska-Lincoln', 'nra': 49.1,
        'file': 'data/western_us_dissertations/unl_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'phd_sets': ['publication:dissertations'],
        'years': (2010, 2026),
    },
    {
        'key': 'umass', 'name': 'UMass Amherst', 'nra': 49.3,
        'file': 'data/western_us_dissertations/umass_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    # Ohio State removed: OAI data is 99.9% undergraduate honors theses, not graduate work.
    # Need to find their graduate thesis/dissertation collection separately.
    # ── Phase 2: newly harvested (Mar 11 2026) ──
    {
        'key': 'ubuffalo', 'name': 'U Buffalo', 'nra': 54.4,
        'file': 'data/western_us_dissertations/ubuffalo_etds.csv',
        'dept_source': 'contributor_ubuffalo', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'utarlington', 'name': 'UT Arlington', 'nra': 65.5,
        'file': 'data/western_us_dissertations/utarlington_etds.csv',
        'dept_source': 'oai_set', 'dept_map': UTARLINGTON_DEPTS,
        'years': (2010, 2026),
    },
    {
        'key': 'uhouston', 'name': 'U Houston', 'nra': 64.5,
        'file': 'data/western_us_dissertations/uhouston_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'ttu', 'name': 'Texas Tech', 'nra': 57.4,
        'file': 'data/western_us_dissertations/ttu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'exclude_type': 'article|presentation|student paper|technical report|newsletter|poster|review|other',
    },
    # ── Phase 3: already-harvested schools with NRA data ──
    {
        'key': 'utaustin', 'name': 'UT Austin', 'nra': 46.4,
        'file': 'data/western_us_dissertations/utaustin_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'mit', 'name': 'MIT', 'nra': 43.8,
        'file': 'data/western_us_dissertations/mit_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'wvu', 'name': 'West Virginia U', 'nra': 42.8,
        'file': 'data/western_us_dissertations/wvu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'usf', 'name': 'U South Florida', 'nra': 41.5,
        'file': 'data/western_us_dissertations/usf_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'wayne_state', 'name': 'Wayne State', 'nra': 40.2,
        'file': 'data/western_us_dissertations/wayne_state_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'phd_sets': ['publication:oa_dissertations'],
        'ms_sets': ['publication:oa_theses'],
        'years': (2010, 2026),
    },
    {
        'key': 'ukansas', 'name': 'U Kansas', 'nra': 39.2,
        'file': 'data/western_us_dissertations/ukansas_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'umn', 'name': 'U Minnesota', 'nra': 38.8,
        'file': 'data/western_us_dissertations/umn_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'washu', 'name': 'Wash U St Louis', 'nra': 37.7,
        'file': 'data/western_us_dissertations/washu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'duke', 'name': 'Duke', 'nra': 37.3,
        'file': 'data/western_us_dissertations/duke_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'phd_sets': ['col_10161_4'],
        'ms_sets': ['col_10161_2493'],
        'years': (2010, 2026),
    },
    {
        'key': 'uarizona', 'name': 'U Arizona', 'nra': 36.3,
        'file': 'data/western_us_dissertations/uarizona_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'bu', 'name': 'Boston U', 'nra': 34.2,
        'file': 'data/western_us_dissertations/bu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'yale', 'name': 'Yale', 'nra': 33.2,
        'file': 'data/western_us_dissertations/yale_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'phd_sets': ['publication:gsas_dissertations'],
        'years': (2010, 2026),
    },
    {
        'key': 'harvard', 'name': 'Harvard', 'nra': 33.0,
        'file': 'data/western_us_dissertations/harvard_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'upenn', 'name': 'U Penn', 'nra': 31.6,
        'file': 'data/western_us_dissertations/upenn_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    # ── Additional large harvested datasets ──
    {
        'key': 'unt', 'name': 'U North Texas', 'nra': 41.4,
        'file': 'data/western_us_dissertations/unt_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'syracuse', 'name': 'Syracuse', 'nra': 51.6,
        'file': 'data/western_us_dissertations/syracuse_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'unlv', 'name': 'UNLV', 'nra': 32.3,
        'file': 'data/western_us_dissertations/unlv_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'usc_columbia', 'name': 'U South Carolina', 'nra': 47.0,
        'file': 'data/western_us_dissertations/usc_columbia_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'udel', 'name': 'U Delaware', 'nra': 46.3,
        'file': 'data/western_us_dissertations/udel_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'phd_sets': ['col_19716_12883', 'col_19716_20898'],
        'ms_sets': ['col_19716_5010'],
        'years': (2010, 2026),
    },
    # ── Phase 4: more harvested datasets (NRA not in top ranking) ──
    {
        'key': 'mines', 'name': 'CO School of Mines', 'nra': 39.8,
        'file': 'data/western_us_dissertations/mines_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'cuny', 'name': 'CUNY Grad Center', 'nra': 38.5,
        'file': 'data/western_us_dissertations/cuny_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'byu', 'name': 'BYU', 'nra': 26.4,
        'file': 'data/western_us_dissertations/byu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'uarkansas', 'name': 'U Arkansas', 'nra': 50.5,
        'file': 'data/western_us_dissertations/uarkansas_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'msstate', 'name': 'Mississippi State', 'nra': 49.2,
        'file': 'data/western_us_dissertations/msstate_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026), 'allow_no_date': True,
    },
    {
        'key': 'ulouisville', 'name': 'U Louisville', 'nra': 43.2,
        'file': 'data/western_us_dissertations/ulouisville_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'umemphis', 'name': 'U Memphis', 'nra': 31.6,
        'file': 'data/western_us_dissertations/umemphis_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'utah_state', 'name': 'Utah State', 'nra': 14.9,
        'file': 'data/western_us_dissertations/utah_state_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'olemiss', 'name': 'Ole Miss', 'nra': 32.6,
        'file': 'data/western_us_dissertations/olemiss_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        # NRA basis, pinned against two anchors rather than one: IPEDS
        # AWLEVEL 17 (or legacy 9), STEM CIP families 11/14/15/26/27/30/40/42,
        # completions 2015-2022 INCLUSIVE. Only that window reproduces both
        # stored figures — mines 39.76 against 39.8 and binghamton 56.89
        # against 56.9. 2015-2023 fits mines but misses binghamton (56.37),
        # and 2015-2024 fits neither. ipeds_nra_asian_ranking.py's header
        # claiming 2015-2024 is wrong by two years.
        'key': 'montana_state',
        'name': 'Montana State U',
        'nra': 15.3,
        'file': 'data/western_us_dissertations/montana_state_etds.csv',
        'dept_source': 'subject_generic',
        'dept_map': {},
        'years': [2010, 2026],
    },
    {
        'key': 'umt', 'name': 'U Montana', 'nra': 14.7,
        'file': 'data/western_us_dissertations/umt_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'und', 'name': 'U North Dakota', 'nra': 37.8,
        'file': 'data/western_us_dissertations/und_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'udenver', 'name': 'U Denver', 'nra': 27.0,
        'file': 'data/western_us_dissertations/udenver_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'boise_state', 'name': 'Boise State', 'nra': 29.7,
        'file': 'data/western_us_dissertations/boise_state_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'siu', 'name': 'Southern Illinois', 'nra': 57.1,
        'file': 'data/western_us_dissertations/siu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'phd_sets': ['publication:dissertations'],
        'ms_sets': ['publication:theses'],
        'years': (2010, 2026),
    },
    {
        'key': 'northern_colorado', 'name': 'U Northern Colorado', 'nra': 8.1,
        'file': 'data/western_us_dissertations/northern_colorado_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    # ── Phase 4b: remaining small harvested datasets ──
    {
        'key': 'niu', 'name': 'Northern Illinois', 'nra': 20.5,
        'file': 'data/western_us_dissertations/niu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'usm', 'name': 'U Southern Miss', 'nra': 10.2,
        'file': 'data/western_us_dissertations/usm_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'phd_sets': ['publication:dissertations'],
        'ms_sets': ['publication:masters_theses'],
        'years': (2010, 2026),
    },
    {
        'key': 'smu', 'name': 'SMU', 'nra': 61.3,
        'file': 'data/western_us_dissertations/smu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        # Umbrella ETD set; SMU's oai_etdms records carry no degree block, only
        # <type>Dissertation</type> / <type>Thesis</type>.
        'thesis_vocab_field': 'type',
        'years': (2010, 2026), 'allow_no_date': True,
    },
    {
        'key': 'nau', 'name': 'Northern Arizona', 'nra': 16.6,
        'file': 'data/western_us_dissertations/nau_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'marquette', 'name': 'Marquette', 'nra': 38.6,
        'file': 'data/western_us_dissertations/marquette_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'phd_sets': ['publication:dissertations_mu'],
        'ms_sets': ['publication:theses_open'],
        'years': (2010, 2026),
    },
    {
        'key': 'unh', 'name': 'U New Hampshire', 'nra': 42.6,
        'file': 'data/western_us_dissertations/unh_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'phd_sets': ['publication:dissertation'],
        'ms_sets': ['publication:thesis'],
        'years': (2010, 2026),
    },
    {
        'key': 'unm', 'name': 'U New Mexico', 'nra': 34.0,
        'file': 'data/western_us_dissertations/unm_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'dartmouth', 'name': 'Dartmouth', 'nra': 34.4,
        'file': 'data/western_us_dissertations/dartmouth_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'phd_sets': ['publication:dissertations'],
        'ms_sets': ['publication:masters_theses'],
        'years': (2010, 2026),
    },
    {
        'key': 'usd', 'name': 'U South Dakota', 'nra': 25.8,
        'file': 'data/western_us_dissertations/usd_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'pdx', 'name': 'Portland State', 'nra': 33.2,
        'file': 'data/or_wa_dissertations/pdxscholar_dissertations.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    # ── Phase 5: UC system + Stanford (different CSV formats) ──
    {
        'key': 'ucla', 'name': 'UCLA', 'nra': 37.3,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'campus_filter': 'UCLA', 'degree_label': 'phd',
    },
    {
        'key': 'ucsd', 'name': 'UC San Diego', 'nra': 36.6,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'campus_filter': 'UC San Diego', 'degree_label': 'phd',
    },
    {
        'key': 'ucberkeley', 'name': 'UC Berkeley', 'nra': 29.3,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'campus_filter': 'UC Berkeley', 'degree_label': 'phd',
    },
    {
        'key': 'ucirvine', 'name': 'UC Irvine', 'nra': 33.2,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'campus_filter': 'UC Irvine', 'degree_label': 'phd',
    },
    {
        'key': 'ucriverside', 'name': 'UC Riverside', 'nra': 38.6,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'campus_filter': 'UC Riverside', 'degree_label': 'phd',
    },
    {
        'key': 'ucdavis', 'name': 'UC Davis', 'nra': 29.4,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'campus_filter': 'UC Davis', 'degree_label': 'phd',
    },
    {
        'key': 'ucsb', 'name': 'UC Santa Barbara', 'nra': 29.8,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'campus_filter': 'UC Santa Barbara', 'degree_label': 'phd',
    },
    {
        'key': 'ucsc', 'name': 'UC Santa Cruz', 'nra': 19.7,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'campus_filter': 'UC Santa Cruz', 'degree_label': 'phd',
    },
    {
        'key': 'ucsf', 'name': 'UCSF', 'nra': 9.3,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'campus_filter': 'UC San Francisco', 'degree_label': 'phd',
    },
    {
        'key': 'ucmerced', 'name': 'UC Merced', 'nra': 37.4,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'campus_filter': 'UC Merced', 'degree_label': 'phd',
    },
    {
        'key': 'stanford', 'name': 'Stanford', 'nra': 35.5,
        'file': 'data/stanford_dissertations/stanford_dissertations_metadata.csv',
        'dept_source': 'department_stanford', 'dept_map': {},
        'years': (2010, 2026),
        'creator_field': 'author', 'degree_label': 'phd',
    },
    # ── Phase 6b: U Oregon (OAI from Graduate Theses & Dissertations set) ──
    {
        'key': 'uoregon', 'name': 'U Oregon', 'nra': 10.4,
        'file': 'data/western_us_dissertations/uoregon_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    # ── Phase 7: Tier 1 additions — already-harvested data ──
    {
        'key': 'ncstate', 'name': 'NC State', 'nra': 43.9,
        'file': 'data/western_us_dissertations/ncstate_etds.csv',
        'dept_source': 'oai_set', 'dept_map': {},
        'years': (2010, 2026),
    },
    # Oregon State: 98K records but OAI harvest has no dates — need re-harvest
    # UConn: data ends 2016 — need re-harvest for recent years
    {
        'key': 'uwmadison', 'name': 'UW Madison', 'nra': 36.6,
        'file': 'data/western_us_dissertations/uwmadison_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'la_tech', 'name': 'Louisiana Tech', 'nra': 54.3,
        'file': 'data/western_us_dissertations/la_tech_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    # U Kentucky: data ends 2012 — need re-harvest for recent years
    {
        'key': 'wsu', 'name': 'Washington State', 'nra': 47.2,
        'file': 'data/or_wa_dissertations/wsu_dissertations.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'creator_field': 'author',
    },
    # ── Phase 8: Tier 2 — newly harvested high-NRA universities ──
    {
        'key': 'rice', 'name': 'Rice', 'nra': 51.3,
        'file': 'data/western_us_dissertations/rice_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'type_filter': 'thesis',  # type field contains "Thesis" for all theses/dissertations
    },
    {
        'key': 'umd', 'name': 'U Maryland', 'nra': 45.2,
        'file': 'data/western_us_dissertations/umd_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'type_filter': 'dissertation',  # Filter to dissertations only (PhD)
        'degree_label': 'phd',
    },
    {   # UMD Master's theses (separate entry)
        'key': 'umd', 'name': 'U Maryland', 'nra': 45.2,
        'file': 'data/western_us_dissertations/umd_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'type_filter': 'thesis',
        'degree_label': 'ms',
        '_merge': True,
    },
    # ── Phase 8b: Tier 2 — UIUC, CMU, UW Seattle ──
    {
        'key': 'uiuc', 'name': 'UIUC', 'nra': 52.1,
        'file': 'data/western_us_dissertations/uiuc_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'type_filter': 'thesis',
    },
    {
        'key': 'cmu', 'name': 'Carnegie Mellon', 'nra': 55.9,
        'file': 'data/western_us_dissertations/cmu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'type_filter': 'thesis',
    },
    {
        'key': 'uw_seattle', 'name': 'UW Seattle', 'nra': 26.2,
        'file': 'data/uw_dissertations/uw_etd_metadata.csv',
        'dept_source': 'column_department', 'dept_map': {},
        'years': (2010, 2026),
        'creator_field': 'author',
    },
    # ── Phase 8c: Cornell, Columbia, Penn State ──
    {
        'key': 'cornell', 'name': 'Cornell', 'nra': 41.3,
        'file': 'data/western_us_dissertations/cornell_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'columbia', 'name': 'Columbia', 'nra': 42.5,
        'file': 'data/western_us_dissertations/columbia_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'penn_state', 'name': 'Penn State', 'nra': 50.8,
        'file': 'data/western_us_dissertations/penn_state_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    # ── Phase 8d: Tier A + UVA ──
    {
        'key': 'uutah', 'name': 'U Utah', 'nra': 37.1,
        'file': 'data/western_us_dissertations/uutah_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        # ir_etd holds theses and dissertations together; dc:description carries
        # the controlled type word ('dissertation' / 'thesis' / 'honors thesis').
        'thesis_vocab_field': 'description',
        'years': (2010, 2026),
    },
    {
        'key': 'uva', 'name': 'U Virginia', 'nra': 35.2,
        'file': 'data/western_us_dissertations/uva_etds.csv',
        'dept_source': 'column_department', 'dept_map': {},
        'years': (2010, 2026),
        'creator_field': 'author',
    },
    {
        'key': 'msu', 'name': 'Michigan State', 'nra': 49.0,
        'file': 'data/western_us_dissertations/msu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'uf', 'name': 'U Florida', 'nra': 45.2,
        'file': 'data/western_us_dissertations/uf_etds.csv',
        'dept_source': 'column_department', 'dept_map': {},
        'years': (2010, 2026),
        'creator_field': 'creator',
    },
    # U Georgia removed — Invenio OAI returns deposit date (2024-12-05) not graduation date
    # Re-harvested 2026-04: dates are now real graduation dates spanning 2017-2026.
    # 2024 has no records (gap in source), but 2025-2026 records are valid PhD conferrals.
    {
        'key': 'northwestern', 'name': 'Northwestern', 'nra': 37.9,
        'file': 'data/western_us_dissertations/northwestern_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    # ── Phase 8e: Remaining R1 OAI harvests ──
    {
        'key': 'temple', 'name': 'Temple', 'nra': 35.4,
        'file': 'data/western_us_dissertations/temple_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'gmu', 'name': 'George Mason', 'nra': 32.6,
        'file': 'data/western_us_dissertations/gmu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
    },
    {
        'key': 'utk', 'name': 'U Tennessee', 'nra': 37.3,
        'file': 'data/western_us_dissertations/utk_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        # STILL NEEDED. The re-harvest recovered almost no award dates
        # here: date_issued is filled for 285 records out of ~26,000, so
        # this repository falls back to `date`, which still carries the
        # bulk-deposit spike (7,295 in 2023, 4,657 in 2024).
        'years': (2016, 2022),
    },
    # Auburn removed — OAI data contains only journal articles/reports, no theses
    # ── Phase 9: Caltech department alumni (scraped from dept websites) ──
    {
        'key': 'caltech', 'name': 'Caltech', 'nra': 41.2,
        'file': 'data/caltech_dissertations/caltech_dept_alumni_combined.csv',
        'dept_source': 'column_department', 'dept_map': {},
        'years': (1966, 2026),
        'creator_field': 'name',
        'date_field': 'year',
        'url_field': 'thesis_url',
        'degree_filter': 'phd',
    },
    # ── Phase 10: previously-harvested repos that were configured in
    # scripts/scrape_oai_etds.py REPOS but never registered here, so their
    # records never reached the site.
    #
    # NRA basis for all three: IPEDS AWLEVEL=17, STEM CIP families
    # 11/14/15/26/27/30/40/42 (CIPCODE '99' excluded), CNRALT/CTOTALT summed
    # over data/ipeds/C{year}_A.csv. The reproducing window is 2015-2022, NOT
    # the 2015-2023 that scripts/archive/ipeds_nra_asian_ranking.py appears to
    # request: C2023_a.csv and later ship a UTF-8 BOM on the UNITID header, so
    # row.get('UNITID') returns None for every 2023+ row and that year silently
    # contributes nothing. Checked against both stored anchors — CO School of
    # Mines 39.8 and Binghamton 56.9 — and only 2015-2022 reproduces both
    # (a BOM-aware 2015-2023 read gives Binghamton 56.4).
    {
        'key': 'cu_boulder', 'name': 'CU Boulder', 'nra': 23.4,
        'file': 'data/western_us_dissertations/cu_boulder_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        # CU Scholar is a whole-repository Hyrax harvest (REPOS sets == []), so
        # the CSV also holds Articles, Data Sets, Masters Theses and
        # Undergraduate Honors Theses. 'Dissertation' is CU's doctoral type.
        'type_filter': 'dissertation',
        'degree_label': 'phd',
    },
    {
        'key': 'uky', 'name': 'U Kentucky', 'nra': 43.5,
        'file': 'data/western_us_dissertations/uky_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        'degree_label': 'phd',  # OAI set is publication:gradschool_diss (Doctoral Dissertations)
    },
    {
        'key': 'uconn', 'name': 'UConn', 'nra': 49.7,
        'file': 'data/western_us_dissertations/uconn_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2010, 2026),
        # OAI set is publication:dissertations ("Doctoral Dissertations").
        # The series is complete but stops at 2020 upstream, so the in-window
        # coverage is 2016-2020 only (1,633 records); nothing after 2020 is
        # published to this bepress series.
        'degree_label': 'phd',
    },
]


# Non-STEM departments to exclude from display
NON_STEM_DEPTS = {
    'Education', 'English/Literature', 'History', 'Music', 'Philosophy',
    'Political Science', 'Sociology', 'Business', 'Nursing', 'Kinesiology',
    'Psychology', 'Economics', 'Social Work', 'Communication',
    'Public Administration', 'Public Affairs', 'Art', 'Theater',
    'Foreign Languages', 'Religious Studies', 'Law', 'Journalism',
    'Library Science', 'Criminal Justice', 'Anthropology',
    # UW Seattle and other column_department sources
    'Art History', 'Business Administration', 'Asian Languages & Literature',
    'Cinema & Media Studies', 'Architecture', 'Built Environment',
    'Classical Languages & Literature', 'Communications', 'Comparative Literature',
    'Design', 'Digital Arts & Experimental Media', 'Drama', 'East Asian Studies',
    'Education (Bothell)', 'Education (Seattle)', 'Education (Tacoma)',
    'English', 'Ethnomusicology', 'Fine Arts', 'French & Italian',
    'Gender, Women & Sexuality', 'Geography', 'German',
    'Hispanic Studies', 'History', 'International Studies',
    'Landscape Architecture', 'Law', 'Linguistics',
    'Marine Affairs', 'Medical History & Ethics', 'Museology', 'Music',
    'Near Eastern Languages & Literature', 'Near & Middle Eastern Studies',
    'Philosophy', 'Political Science', 'Psychology',
    'Public Administration', 'Public Affairs',
    'Romance Languages & Literature', 'Russian & East European Studies',
    'Scandinavian Languages & Literature', 'Scientific & Technical Communication',
    'Slavic Languages & Literature', 'Social Welfare', 'Social Work',
    'Sociology', 'Urban Planning', "Women's Studies",
}


_ETDMS_CACHE: dict[str, dict] = {}


def _etdms_lookup(repo_key, identifier):
    """Return 'phd'/'ms'/'' from a degree enrichment mapping.

    Two directories share the same {identifier: {level, name}} format:
      data/etdms_degrees/     — bepress repos, from scripts/enrich_etdms_degrees.py
      data/degree_enrichment/ — non-bepress repos, from scripts/enrich_degree_metadata.py
    """
    if not repo_key or not identifier:
        return ''
    if repo_key not in _ETDMS_CACHE:
        import json as _json
        from pathlib import Path as _Path
        _data = _Path(__file__).resolve().parent.parent / 'data'
        merged = {}
        for _sub in ('etdms_degrees', 'degree_enrichment'):
            p = _data / _sub / f'{repo_key}.json'
            if p.exists():
                try:
                    merged.update(_json.loads(p.read_text()))
                except Exception:
                    pass
        _ETDMS_CACHE[repo_key] = merged
    m = _ETDMS_CACHE[repo_key].get(identifier)
    if not m:
        return ''
    level = (m.get('level') or '').lower()
    name = (m.get('name') or '').lower()
    # Check the degree NAME first — it's the most specific signal.
    # NIU and some others use a combined level like "Dissertation/Thesis"
    # for every record, so level alone doesn't distinguish.
    if 'doctor' in name or 'ph.d' in name or 'phd' in name or 'ed.d' in name or 'sc.d' in name or 'd.m' in name:
        return 'phd'
    if ('master' in name or 'm.s.' in name or 'm.a.' in name or 'm.f.a' in name or
            'm.b.a' in name or 'm.mus' in name or 'm.ed' in name or 'm.eng' in name or
            'm.arch' in name or 'llm' in name):
        return 'ms'
    # Some repos put the degree inside the level string ("Thesis (Ph.D.)" at
    # Dartmouth), which the bare-"Thesis" fallback below would read as an MS.
    if 'ph.d' in level or 'phd' in level or 'ed.d' in level or 'doctor' in level:
        return 'phd'
    # Fall back to level: unambiguous "Dissertation" alone -> PhD; "Thesis" alone -> MS
    if 'dissertation' in level and 'thesis' not in level:
        return 'phd'
    if 'thesis' in level and 'dissertation' not in level:
        return 'ms'
    # Undergraduate honours theses (some repos mix them in) — filtered downstream
    if 'bachelor' in level:
        return 'bs'
    return ''


def infer_degree_type(row, config):
    """Infer PhD vs Masters from available metadata. Returns 'phd', 'ms', or ''."""
    # Config-level override (e.g. collection is known to be all-PhD)
    forced = config.get('degree_label')
    if forced:
        return forced

    # ETDMS enrichment mapping (bepress repos) — fetched separately to get
    # thesis.degree.name/level that oai_dc drops.
    etdms = _etdms_lookup(config.get('key'), row.get('identifier'))
    if etdms:
        return etdms

    # Explicit degree_type, degree, degree_level, or degree_name column
    dt = (row.get('degree_type', '') or row.get('degree', '') or row.get('degree_name', '') or row.get('degree_level', '') or '').lower().strip()
    if dt in ('phd', 'doctoral', 'doctorate', 'dissertation') or dt.startswith(('phd ', 'phd(', 'ph.d', 'edd', 'ed.d', 'sjd', 'dnp', 'dma', 'd.m', 'd.ed', 'd.eng', 'd.n.p')) or 'doctor' in dt:
        return 'phd'
    if dt in ('masters', 'master', 'ms', 'msc', 'ma', 'mfa', 'med', 'mla', "master's thesis") or dt.startswith(('ms ', 'ms(', 'ma ', 'ma(', 'mfa', 'me ', 'me(', 'llm', 'mar ', 'march', 'muep', 'm.s', 'm.a', 'm.e', "master's")) or 'master of' in dt:
        return 'ms'
    # Skip bachelor's theses
    if dt.startswith(('bs ', 'bs(', 'ba ', 'ba(', 'bsc', 'b.s', 'b.a')):
        return 'bs'

    # Check degree_level field specifically (oai_etdms: "Thesis" = MS, "Dissertation" = PhD)
    dl = (row.get('degree_level', '') or '').lower().strip()
    # Undergraduate theses share the graduate ETD collections at some repos
    # (Harvard's FAS collection holds AB/SB theses); they are filtered downstream.
    if 'bachelor' in dl or 'undergraduate' in dl:
        return 'bs'
    if dl and 'dissertation' in dl:
        return 'phd'
    if dl and 'thesis' in dl and 'dissertation' not in dl:
        return 'ms'

    # Sets the repository itself curates by degree level, named explicitly in
    # the config. Repos that harvest both a dissertations set and a master's
    # set (and DSpace repos, whose set specs are opaque handles) get a
    # deterministic answer here instead of falling through to the heuristics
    # below. A record's own "Master's thesis" type outranks the collection it
    # was filed in, so it is checked first.
    oai_specs = [p.strip() for p in (row.get('oai_set', '') or '').split(';')]
    row_type = (row.get('type', '') or '').lower()
    for spec in config.get('ms_sets', ()):
        if spec in oai_specs:
            return 'ms'
    if 'master' not in row_type:
        for spec in config.get('phd_sets', ()):
            if spec in oai_specs:
                return 'phd'

    # A few repositories publish a controlled resource-type vocabulary in which
    # a bare "Thesis" means master's and "Dissertation" means doctoral. That is
    # not safe to assume generally — most repos call all graduate work a
    # "Thesis" — so the field carrying the vocabulary is named per config.
    vocab_field = config.get('thesis_vocab_field')
    if vocab_field:
        vocab = (row.get(vocab_field, '') or '').split(';')[0].strip().lower()
        if vocab == 'dissertation':
            return 'phd'
        if vocab in ('honors thesis', 'senior thesis'):
            return 'bs'
        if vocab in ('thesis', "master's thesis"):
            return 'ms'

    # Check OAI set membership — split into individual sets and check each
    oai_set = (row.get('oai_set', '') or '').lower()
    oai_parts = [p.strip() for p in oai_set.split(';')]
    # Check for dissertation-only or doctoral sets
    if 'degree_level:doctoral' in oai_set:
        return 'phd'
    if "degree_level:master" in oai_set:
        return 'ms'
    # Check individual set parts — a set like "publication:dissertations" (without "thesis") indicates PhD
    for part in oai_parts:
        if ('dissertation' in part and 'thes' not in part and
            part not in ('publication:theses-dissertations', 'publication:thesesdissertations',
                         'publication:allgraduate-thesesdissertations')):
            return 'phd'
    # Check for explicit master's thesis sets
    if ('masters_theses' in oai_set or 'master_theses' in oai_set or
        'gradschool_theses' in oai_set):
        return 'ms'
    # Check for explicit master's thesis sets (unambiguous)
    for part in oai_parts:
        if part in ('publication:masters-theses', 'publication:masters_theses'):
            return 'ms'

    # Check type field
    t = (row.get('type', '') or '').lower()
    if 'doctoral' in t or ('dissertation' in t and 'thesis' not in t):
        return 'phd'
    if 'masters' in t or "master's thesis" in t or 'master thesis' in t:
        return 'ms'
    # Note: generic "Thesis" alone does NOT mean master's — many universities use it for all grad work

    # Check relation field (Penn State stores PHD/MASTERS here)
    rel = (row.get('relation', '') or '').upper().strip()
    if rel == 'PHD' or rel == 'DOCTORAL':
        return 'phd'
    if rel in ('MASTERS', 'MASTER', 'MS', 'MA'):
        return 'ms'

    # Ex Libris Esploro (WSU) encodes the repository's own ETD asset type in the
    # item URL path: etd.doctoral -> /outputs/doctoral/, etd.graduate -> /outputs/graduate/
    item_url = (row.get('url', '') or '').lower()
    if '/outputs/doctoral/' in item_url:
        return 'phd'
    if '/outputs/graduate/' in item_url:
        return 'ms'

    # Check description field for degree indicators
    desc = (row.get('description', '') or '').lower()
    # Skip bachelor's theses first (MIT uses S.B., B.S.)
    if re.search(r'\b(s\.b\.|b\.s\.)(?!\s*and\s*m)', desc):
        return 'bs'
    # PhD patterns: Ph.D., Ph. D., Sc.D., Sc. D., doctoral, dissertation
    if re.search(r'ph\.\s*d', desc) or 'doctor of philosophy' in desc or 'doctoral' in desc or 'dissertation' in desc or re.search(r'sc\.\s*d', desc):
        return 'phd'
    # Master's patterns: S.M., M.S., M.Eng., M.C.P., M.Arch., M.B.A., etc.
    if re.search(r'\bs\.m\.', desc) or 'm.s.' in desc or 'm.eng' in desc or 'm.c.p' in desc or 'm.arch' in desc or 'm.b.a' in desc or 'master of science' in desc or 'master of arts' in desc or 'm.sc' in desc or 'master of engineering' in desc or 'master of city planning' in desc or 'master of architecture' in desc:
        return 'ms'

    # Late OAI set check — ambiguous sets like publication:theses
    # Only use this as fallback after description check (some repos use "theses" for all grad work)
    if 'publication:theses' in oai_parts and 'publication:dissertations' not in oai_parts:
        return 'ms'

    return ''


def load_records(config):
    """Load one university's records, filtered to the config's year window.

    The year comes from ``date_issued`` when the harvest captured a real award
    date, falling back to ``date`` otherwise. ``date`` is whatever the
    repository listed first, which for a DSpace instance is usually the
    accession stamp -- the moment a librarian uploaded the record. An explicit
    ``date_field`` in the config overrides both.
    """
    records = []
    # Prefer the real award date. The re-harvest writes it to `date_issued`;
    # `date` is whatever the repository happened to put first, which for a
    # DSpace instance is usually the accession stamp -- the moment a librarian
    # uploaded the record. Colorado School of Mines digitised its historical
    # collection in 2023-24, so "The Roscoe pegmatite dike", awarded in 1900,
    # carried date='2024-03-21T17:36:24Z'. 283,642 records across 26
    # repositories were misdated this way, every one of them too late.
    #
    # An explicit date_field in the config still wins. Where date_issued is
    # absent or blank the behaviour is exactly as before.
    date_field = config.get('date_field')
    url_field = config.get('url_field', None)
    degree_filter = config.get('degree_filter', None)
    allow_no_date = config.get('allow_no_date', False)
    with open(config['file'], encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if date_field:
                raw_date = row.get(date_field, '')
            else:
                raw_date = (row.get('date_issued') or '').strip() or row.get('date', '')
            yr = extract_year(raw_date)
            if not yr:
                if allow_no_date:
                    yr = 0  # Placeholder for records with no date
                else:
                    continue
            elif yr < config['years'][0] or yr > config['years'][1]:
                continue

            # Optional degree filter (e.g. Caltech has phd + masters)
            if degree_filter:
                if row.get('degree_type', '').lower() != degree_filter:
                    continue

            # Optional type filter (e.g. TTU ThinkTech has mixed types)
            type_filter = config.get('type_filter')
            if type_filter:
                row_type = row.get('type', '').lower()
                if type_filter not in row_type:
                    continue

            # Optional type exclusion (e.g. Iowa State has "article; dissertation" mixed in)
            exclude_type = config.get('exclude_type')
            if exclude_type:
                row_type = row.get('type', '').lower()
                if any(row_type.startswith(p) or p in row_type for p in exclude_type.split('|')):
                    continue

            # Optional campus filter (UC system)
            campus_filter = config.get('campus_filter')
            if campus_filter:
                campus = row.get('campus_name', '')
                if campus != campus_filter:
                    continue

            creator_field = config.get('creator_field', 'creator')
            creator = row.get(creator_field, '').strip()
            if not creator:
                continue
            if ';' in creator:
                creator = creator.split(';')[0].strip()
            # Strip birth dates appended to names (e.g. "Smith, John 1991-" or "Doe, Jane 12/07/1994-")
            creator = re.sub(r'\s+\d{1,2}/\d{1,2}/\d{4}-?\s*$', '', creator)
            creator = re.sub(r'\s+\d{4}-?\s*$', '', creator)

            # Determine department — try enriched fields first
            dept = None
            for enrich_field in ('degree_department', 'degree_discipline'):
                val = (row.get(enrich_field, '') or '').strip()
                if val and val.lower() not in ('', 'natural sciences', 'social sciences', 'engineering', 'humanities'):
                    dept = val
                    break
            src = config['dept_source']
            if dept:
                pass  # Already have dept from enriched fields
            elif src == 'oai_set':
                dept = get_dept_from_oai(row.get('oai_set', ''), config['dept_map'])
            elif src == 'subject_rpi':
                dept = extract_dept_from_subject_rpi(row.get('subject', ''))
            elif src == 'subject_utdallas':
                dept = extract_dept_from_subject_utdallas(row.get('subject', ''))
            elif src == 'subject_umissouri':
                dept = extract_dept_from_subject_umissouri(row.get('subject', ''))
            elif src == 'subject_stonybrook':
                dept = extract_dept_from_subject_stonybrook(row.get('subject', ''))
            elif src == 'subject_generic':
                dept = extract_dept_from_subject_generic(row.get('subject', ''))
            elif src == 'contributor_gatech':
                dept = extract_dept_from_contributor_gatech(row.get('contributor', ''))
            elif src == 'contributor_vt':
                dept = extract_dept_from_contributor_vt(row.get('contributor', ''))
            elif src == 'contributor_ubuffalo':
                dept = extract_dept_from_contributor_ubuffalo(row.get('contributor', ''))
            elif src == 'department_stanford':
                dept = normalize_stanford_dept(row.get('department', ''))
            elif src == 'column_department':
                val = row.get('department', '').strip()
                # Handle Python list strings like "['Dental Sciences', 'Dentistry']"
                if val and val.startswith('['):
                    import ast
                    try:
                        parsed = ast.literal_eval(val)
                        val = parsed[0] if parsed else ''
                    except:
                        val = val.strip("[]'\"")
                dept = val or None
            else:
                dept = None

            # Fallback 1: try title for department clues
            if not dept:
                dept = extract_dept_from_subject_generic(row.get('title', ''))
            # Fallback 2: try OAI set names for bepress-style department sets
            if not dept:
                oai = row.get('oai_set', '').lower()
                dept = extract_dept_from_subject_generic(oai.replace('_', ' ').replace(':', ' '))
            # Fallback 3: try description
            if not dept:
                desc = (row.get('description', '') or '')[:300]
                dept = extract_dept_from_subject_generic(desc)
            if not dept:
                dept = 'General'

            # Filter STEM vs non-STEM departments
            is_non_stem = dept in NON_STEM_DEPTS
            stem_filter = config.get('_stem_filter', 'stem')
            if stem_filter == 'stem' and is_non_stem:
                continue
            if stem_filter == 'non-stem' and not is_non_stem:
                continue

            cat, conf = classify(creator)
            if url_field:
                url = row.get(url_field, '').strip()
            else:
                url = get_url(row)
            title = row.get('title', '').strip()

            # Infer degree type from available metadata
            degree = infer_degree_type(row, config)

            # Skip bachelor's theses
            if degree == 'bs':
                continue

            records.append({
                'dept': dept, 'year': yr, 'name': creator,
                'classification': cat, 'confidence': conf,
                'title': title, 'url': url, 'degree': degree,
            })

    # Deduplicate by (name, year, dept, title)
    seen = set()
    deduped = []
    for r in records:
        key = (r['name'].lower(), r['year'], r['dept'].lower(), r['title'][:50].lower())
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    if len(deduped) < len(records):
        print(f"  Removed {len(records) - len(deduped)} duplicates")
    return deduped


def record_dedup_key(r):
    """Identity of a graduate record, matching load_records' own dedup key."""
    return (
        r['name'].lower(),
        r['year'],
        r['dept'].lower(),
        r['title'][:50].lower(),
    )


def merge_university_records(existing, incoming, authoritative=False):
    """Merge a second config's records into a university's list, in place.

    load_records() deduplicates within one config, but several universities
    are assembled from two configs — UT Dallas reads both its institutional
    repository and the graduate school's doctoral-degree conferral pages.
    Extending the list without a cross-config check counted those graduates
    twice, and with conflicting degrees: the repository record often carries
    no degree (or an inferred master's) while the conferral page is
    explicitly doctoral.

    `authoritative` marks an incoming config that states a degree outright
    (a `degree_label`), so its label wins a conflict.
    """
    index = {record_dedup_key(r): i for i, r in enumerate(existing)}
    for rec in incoming:
        key = record_dedup_key(rec)
        if key not in index:
            index[key] = len(existing)
            existing.append(rec)
            continue
        prev = existing[index[key]]
        if rec.get('degree') and (authoritative or not prev.get('degree')):
            existing[index[key]] = rec
    return existing


def write_university_report(config, records, outfile):
    """Write name lists for top departments at one university."""
    name = config['name']
    nra = config['nra']
    yr_range = config['years']

    # Find departments with highest Chinese %
    dept_stats = defaultdict(lambda: {'total': 0, 'chinese': 0})
    for r in records:
        dept_stats[r['dept']]['total'] += 1
        if r['classification'] == 'chinese':
            dept_stats[r['dept']]['chinese'] += 1

    # Sort by Chinese %, filter to >= 10 records
    ranked = [(d, s['chinese'] / s['total'] * 100, s['total'], s['chinese'])
              for d, s in dept_stats.items() if s['total'] >= 10]
    ranked.sort(key=lambda x: -x[1])

    # Take top departments (those with >= 15% Chinese or top 6)
    top = [r for r in ranked if r[1] >= 15]
    if len(top) < 4:
        top = ranked[:6]

    outfile.write(f"\n{'#'*100}\n")
    outfile.write(f"#  {name}  (IPEDS NRA: {nra}%)\n")
    outfile.write(f"#  {yr_range[0]}-{yr_range[1]} — All PhD recipients by department\n")
    outfile.write(f"#  Source: {config['file']}\n")
    outfile.write(f"{'#'*100}\n\n")

    # Summary table
    outfile.write(f"  Department summary (sorted by Chinese %):\n")
    outfile.write(f"  {'Department':<45} {'Total':>6} {'Chinese':>8} {'%':>6}\n")
    outfile.write(f"  {'-'*70}\n")
    for dept, pct, total, ch in ranked:
        marker = " <<<" if pct >= 20 else ""
        outfile.write(f"  {dept:<45} {total:>6} {ch:>8} {pct:>5.1f}%{marker}\n")
    outfile.write(f"\n")

    # Detailed name lists for top departments
    for dept, pct, total, ch in top:
        dept_recs = [r for r in records if r['dept'] == dept]

        outfile.write(f"\n{'='*100}\n")
        outfile.write(f"  {dept} — {name} ({yr_range[0]}-{yr_range[1]})\n")
        outfile.write(f"  Overall: {total} records, {ch} Chinese-classified ({pct:.1f}%)\n")
        outfile.write(f"{'='*100}\n")

        for yr in range(yr_range[0], yr_range[1] + 1):
            yr_recs = sorted([r for r in dept_recs if r['year'] == yr], key=lambda x: x['name'])
            if not yr_recs:
                continue

            yr_ch = len([r for r in yr_recs if r['classification'] == 'chinese'])
            yr_ind = len([r for r in yr_recs if r['classification'] == 'indian'])
            yr_tot = len(yr_recs)
            ch_pct = yr_ch / yr_tot * 100 if yr_tot else 0

            outfile.write(f"\n  {yr} ({yr_tot} dissertations, {yr_ch} Chinese = {ch_pct:.0f}%):\n")
            outfile.write(f"  {'─'*95}\n")
            for r in yr_recs:
                tag = ""
                if r['classification'] == 'chinese':
                    tag = f"  [CH-{r['confidence']}]"
                elif r['classification'] == 'indian':
                    tag = f"  [IN]"
                elif r['classification'] == 'korean':
                    tag = f"  [KR]"
                elif r['classification'] == 'vietnamese':
                    tag = f"  [VN]"

                outfile.write(f"    {r['name']:<42}{tag}\n")
                outfile.write(f"      {r['title'][:80]}\n")
                if r['url']:
                    outfile.write(f"      {r['url']}\n")


def main():
    outdir = "data/department_classification_reports"
    os.makedirs(outdir, exist_ok=True)

    for config in CONFIGS:
        if not os.path.exists(config['file']):
            print(f"SKIP {config['name']}: {config['file']} not found")
            continue

        print(f"Processing {config['name']}...", flush=True)
        records = load_records(config)
        print(f"  {len(records)} records loaded across {len(set(r['dept'] for r in records))} departments")

        outpath = os.path.join(outdir, f"{config['key']}_name_lists.txt")
        with open(outpath, 'w') as f:
            write_university_report(config, records, f)

        print(f"  → {outpath}")

    print("\nDone! Name lists written to data/department_classification_reports/")


if __name__ == "__main__":
    main()
