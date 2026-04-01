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

sys.path.insert(0, os.path.dirname(__file__))
from name_classifier import classify

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
        'key': 'missouri_st', 'name': 'Missouri S&T', 'nra': 73.2,
        'file': 'data/western_us_dissertations/missouri_st_etds.csv',
        'dept_source': 'oai_set', 'dept_map': MISSOURI_ST_DEPTS,
        'years': (2016, 2024),
        'degree_label': 'phd',  # OAI set is publication:doctoral_dissertations only
    },
    {
        'key': 'missouri_st', 'name': 'Missouri S&T', 'nra': 73.2,
        'file': 'data/western_us_dissertations/missouri_st_masters.csv',
        'dept_source': 'oai_set', 'dept_map': MISSOURI_ST_DEPTS,
        'years': (2016, 2024),
        'degree_label': 'ms',  # OAI set is publication:masters_theses only
        '_merge': True,  # merge into existing missouri_st entry
    },
    {
        'key': 'mtu', 'name': 'Michigan Tech', 'nra': 62.0,
        'file': 'data/western_us_dissertations/mtu_etds.csv',
        'dept_source': 'oai_set', 'dept_map': MTU_DEPTS,
        'years': (2016, 2024),
    },
    {
        'key': 'sdsu', 'name': 'SD State', 'nra': 59.6,
        'file': 'data/western_us_dissertations/sdsu_etds.csv',
        'dept_source': 'oai_set', 'dept_map': SDSU_DEPTS,
        'years': (2016, 2024),
    },
    {
        'key': 'utdallas', 'name': 'UT Dallas', 'nra': 59.3,
        'file': 'data/western_us_dissertations/utdallas_etds.csv',
        'dept_source': 'subject_utdallas', 'dept_map': {},
        'years': (2016, 2024),
        'type_filter': 'thesis',  # Filter out articles, photographs, etc.
    },
    {
        'key': 'stony_brook', 'name': 'Stony Brook', 'nra': 49.6,
        'file': 'data/western_us_dissertations/stony_brook_etds.csv',
        'dept_source': 'subject_stonybrook', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'rpi', 'name': 'RPI', 'nra': 48.7,
        'file': 'data/western_us_dissertations/rpi_etds.csv',
        'dept_source': 'subject_rpi', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'umissouri', 'name': 'U Missouri', 'nra': 50.2,
        'file': 'data/western_us_dissertations/umissouri_etds.csv',
        'dept_source': 'subject_umissouri', 'dept_map': {},
        'years': (2016, 2024),
    },
    # ── Phase 1 additions: high-NRA schools with existing data ──
    {
        'key': 'njit', 'name': 'NJIT', 'nra': 70.1,
        'file': 'data/western_us_dissertations/njit_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'degree_label': 'phd',  # OAI set is publication:dissertations; all URLs are /dissertations/
    },
    {
        'key': 'njit', 'name': 'NJIT', 'nra': 70.1,
        'file': 'data/western_us_dissertations/njit_theses.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'degree_label': 'ms',  # OAI set is publication:theses
        '_merge': True,
    },
    {
        'key': 'purdue', 'name': 'Purdue', 'nra': 60.3,
        'file': 'data/western_us_dissertations/purdue_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'kstate', 'name': 'Kansas State', 'nra': 58.3,
        'file': 'data/western_us_dissertations/kstate_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'rit', 'name': 'RIT', 'nra': 57.3,
        'file': 'data/western_us_dissertations/rit_etds.csv',
        'dept_source': 'oai_set', 'dept_map': RIT_DEPTS,
        'years': (2016, 2024),
    },
    {
        'key': 'binghamton', 'name': 'Binghamton', 'nra': 56.9,
        'file': 'data/western_us_dissertations/binghamton_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'iowa_state', 'name': 'Iowa State', 'nra': 55.5,
        'file': 'data/western_us_dissertations/iowa_state_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'clemson', 'name': 'Clemson', 'nra': 55.2,
        'file': 'data/western_us_dissertations/clemson_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'ucf', 'name': 'UCF', 'nra': 53.8,
        'file': 'data/western_us_dissertations/ucf_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'vt', 'name': 'Virginia Tech', 'nra': 53.6,
        'file': 'data/western_us_dissertations/vt_etds.csv',
        'dept_source': 'contributor_vt', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'lsu', 'name': 'LSU', 'nra': 52.3,
        'file': 'data/western_us_dissertations/lsu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'gatech', 'name': 'Georgia Tech', 'nra': 52.4,
        'file': 'data/western_us_dissertations/gatech_etds.csv',
        'dept_source': 'contributor_gatech', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'unl', 'name': 'U Nebraska-Lincoln', 'nra': 49.2,
        'file': 'data/western_us_dissertations/unl_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'umass', 'name': 'UMass Amherst', 'nra': 49.3,
        'file': 'data/western_us_dissertations/umass_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'osu', 'name': 'Ohio State', 'nra': 46.9,
        'file': 'data/western_us_dissertations/osu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    # ── Phase 2: newly harvested (Mar 11 2026) ──
    {
        'key': 'ubuffalo', 'name': 'U Buffalo', 'nra': 54.1,
        'file': 'data/western_us_dissertations/ubuffalo_etds.csv',
        'dept_source': 'contributor_ubuffalo', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'utarlington', 'name': 'UT Arlington', 'nra': 65.5,
        'file': 'data/western_us_dissertations/utarlington_etds.csv',
        'dept_source': 'oai_set', 'dept_map': UTARLINGTON_DEPTS,
        'years': (2016, 2024),
    },
    {
        'key': 'uhouston', 'name': 'U Houston', 'nra': 64.5,
        'file': 'data/western_us_dissertations/uhouston_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'ttu', 'name': 'Texas Tech', 'nra': 57.4,
        'file': 'data/western_us_dissertations/ttu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'type_filter': 'thesis',
    },
    # ── Phase 3: already-harvested schools with NRA data ──
    {
        'key': 'utaustin', 'name': 'UT Austin', 'nra': 46.4,
        'file': 'data/western_us_dissertations/utaustin_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'mit', 'name': 'MIT', 'nra': 43.8,
        'file': 'data/western_us_dissertations/mit_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'wvu', 'name': 'West Virginia U', 'nra': 42.8,
        'file': 'data/western_us_dissertations/wvu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'usf', 'name': 'U South Florida', 'nra': 41.5,
        'file': 'data/western_us_dissertations/usf_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'wayne_state', 'name': 'Wayne State', 'nra': 40.2,
        'file': 'data/western_us_dissertations/wayne_state_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'ukansas', 'name': 'U Kansas', 'nra': 39.2,
        'file': 'data/western_us_dissertations/ukansas_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'umn', 'name': 'U Minnesota', 'nra': 38.8,
        'file': 'data/western_us_dissertations/umn_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'washu', 'name': 'Wash U St Louis', 'nra': 37.7,
        'file': 'data/western_us_dissertations/washu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'duke', 'name': 'Duke', 'nra': 37.3,
        'file': 'data/western_us_dissertations/duke_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'uarizona', 'name': 'U Arizona', 'nra': 36.3,
        'file': 'data/western_us_dissertations/uarizona_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'bu', 'name': 'Boston U', 'nra': 34.2,
        'file': 'data/western_us_dissertations/bu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'yale', 'name': 'Yale', 'nra': 33.2,
        'file': 'data/western_us_dissertations/yale_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'harvard', 'name': 'Harvard', 'nra': 33.0,
        'file': 'data/western_us_dissertations/harvard_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'upenn', 'name': 'U Penn', 'nra': 31.6,
        'file': 'data/western_us_dissertations/upenn_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    # ── Additional large harvested datasets ──
    {
        'key': 'unt', 'name': 'U North Texas', 'nra': 45.0,
        'file': 'data/western_us_dissertations/unt_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'syracuse', 'name': 'Syracuse', 'nra': 47.5,
        'file': 'data/western_us_dissertations/syracuse_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'unlv', 'name': 'UNLV', 'nra': 38.5,
        'file': 'data/western_us_dissertations/unlv_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'usc_columbia', 'name': 'U South Carolina', 'nra': 47.0,
        'file': 'data/western_us_dissertations/usc_columbia_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'udel', 'name': 'U Delaware', 'nra': 46.3,
        'file': 'data/western_us_dissertations/udel_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    # ── Phase 4: more harvested datasets (NRA not in top ranking) ──
    {
        'key': 'mines', 'name': 'CO School of Mines', 'nra': 39.8,
        'file': 'data/western_us_dissertations/mines_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'cuny', 'name': 'CUNY Grad Center', 'nra': 38.5,
        'file': 'data/western_us_dissertations/cuny_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'byu', 'name': 'BYU', 'nra': 30.9,
        'file': 'data/western_us_dissertations/byu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'uarkansas', 'name': 'U Arkansas', 'nra': 54.3,
        'file': 'data/western_us_dissertations/uarkansas_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'msstate', 'name': 'Mississippi State', 'nra': 53.0,
        'file': 'data/western_us_dissertations/msstate_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'ulouisville', 'name': 'U Louisville', 'nra': 47.4,
        'file': 'data/western_us_dissertations/ulouisville_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'umemphis', 'name': 'U Memphis', 'nra': 47.9,
        'file': 'data/western_us_dissertations/umemphis_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'utah_state', 'name': 'Utah State', 'nra': 17.3,
        'file': 'data/western_us_dissertations/utah_state_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'olemiss', 'name': 'Ole Miss', 'nra': 39.2,
        'file': 'data/western_us_dissertations/olemiss_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'umt', 'name': 'U Montana', 'nra': 19.9,
        'file': 'data/western_us_dissertations/umt_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'und', 'name': 'U North Dakota', 'nra': 53.5,
        'file': 'data/western_us_dissertations/und_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'udenver', 'name': 'U Denver', 'nra': 45.2,
        'file': 'data/western_us_dissertations/udenver_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'boise_state', 'name': 'Boise State', 'nra': 29.7,
        'file': 'data/western_us_dissertations/boise_state_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'siu', 'name': 'Southern Illinois', 'nra': 71.3,
        'file': 'data/western_us_dissertations/siu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'northern_colorado', 'name': 'U Northern Colorado', 'nra': 11.9,
        'file': 'data/western_us_dissertations/northern_colorado_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    # ── Phase 4b: remaining small harvested datasets ──
    {
        'key': 'niu', 'name': 'Northern Illinois', 'nra': 34.4,
        'file': 'data/western_us_dissertations/niu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'usm', 'name': 'U Southern Miss', 'nra': 15.4,
        'file': 'data/western_us_dissertations/usm_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'smu', 'name': 'SMU', 'nra': 65.3,
        'file': 'data/western_us_dissertations/smu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'nau', 'name': 'Northern Arizona', 'nra': 22.8,
        'file': 'data/western_us_dissertations/nau_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'marquette', 'name': 'Marquette', 'nra': 48.6,
        'file': 'data/western_us_dissertations/marquette_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'unh', 'name': 'U New Hampshire', 'nra': 46.8,
        'file': 'data/western_us_dissertations/unh_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'unm', 'name': 'U New Mexico', 'nra': 38.7,
        'file': 'data/western_us_dissertations/unm_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'dartmouth', 'name': 'Dartmouth', 'nra': 34.9,
        'file': 'data/western_us_dissertations/dartmouth_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'usd', 'name': 'U South Dakota', 'nra': 48.9,
        'file': 'data/western_us_dissertations/usd_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'pdx', 'name': 'Portland State', 'nra': 41.2,
        'file': 'data/or_wa_dissertations/pdxscholar_dissertations.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    # ── Phase 5: UC system + Stanford (different CSV formats) ──
    {
        'key': 'ucla', 'name': 'UCLA', 'nra': 37.3,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'campus_filter': 'UCLA', 'degree_label': 'phd',
    },
    {
        'key': 'ucsd', 'name': 'UC San Diego', 'nra': 36.6,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'campus_filter': 'UC San Diego', 'degree_label': 'phd',
    },
    {
        'key': 'ucberkeley', 'name': 'UC Berkeley', 'nra': 29.3,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'campus_filter': 'UC Berkeley', 'degree_label': 'phd',
    },
    {
        'key': 'ucirvine', 'name': 'UC Irvine', 'nra': 35.0,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'campus_filter': 'UC Irvine', 'degree_label': 'phd',
    },
    {
        'key': 'ucriverside', 'name': 'UC Riverside', 'nra': 34.0,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'campus_filter': 'UC Riverside', 'degree_label': 'phd',
    },
    {
        'key': 'ucdavis', 'name': 'UC Davis', 'nra': 30.0,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'campus_filter': 'UC Davis', 'degree_label': 'phd',
    },
    {
        'key': 'ucsb', 'name': 'UC Santa Barbara', 'nra': 32.0,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'campus_filter': 'UC Santa Barbara', 'degree_label': 'phd',
    },
    {
        'key': 'ucsc', 'name': 'UC Santa Cruz', 'nra': 28.0,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'campus_filter': 'UC Santa Cruz', 'degree_label': 'phd',
    },
    {
        'key': 'ucsf', 'name': 'UCSF', 'nra': 25.0,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'campus_filter': 'UC San Francisco', 'degree_label': 'phd',
    },
    {
        'key': 'ucmerced', 'name': 'UC Merced', 'nra': 30.0,
        'file': 'data/uc_dissertations/uc_dissertations_metadata.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'campus_filter': 'UC Merced', 'degree_label': 'phd',
    },
    {
        'key': 'stanford', 'name': 'Stanford', 'nra': 35.5,
        'file': 'data/stanford_dissertations/stanford_dissertations_metadata.csv',
        'dept_source': 'department_stanford', 'dept_map': {},
        'years': (2016, 2024),
        'creator_field': 'author', 'degree_label': 'phd',
    },
    # ── Phase 6b: U Oregon (OAI from Graduate Theses & Dissertations set) ──
    {
        'key': 'uoregon', 'name': 'U Oregon', 'nra': 11.8,
        'file': 'data/western_us_dissertations/uoregon_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    # ── Phase 7: Tier 1 additions — already-harvested data ──
    {
        'key': 'ncstate', 'name': 'NC State', 'nra': 37.8,
        'file': 'data/western_us_dissertations/ncstate_etds.csv',
        'dept_source': 'oai_set', 'dept_map': {},
        'years': (2016, 2024),
    },
    # Oregon State: 98K records but OAI harvest has no dates — need re-harvest
    # UConn: data ends 2016 — need re-harvest for recent years
    {
        'key': 'uwmadison', 'name': 'UW Madison', 'nra': 19.7,
        'file': 'data/western_us_dissertations/uwmadison_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'la_tech', 'name': 'Louisiana Tech', 'nra': 22.5,
        'file': 'data/western_us_dissertations/la_tech_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    # U Kentucky: data ends 2012 — need re-harvest for recent years
    {
        'key': 'wsu', 'name': 'Washington State', 'nra': 18.0,
        'file': 'data/or_wa_dissertations/wsu_dissertations.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'creator_field': 'author',
    },
    # ── Phase 8: Tier 2 — newly harvested high-NRA universities ──
    {
        'key': 'rice', 'name': 'Rice', 'nra': 52.4,
        'file': 'data/western_us_dissertations/rice_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'type_filter': 'thesis',  # type field contains "Thesis" for all theses/dissertations
    },
    {
        'key': 'umd', 'name': 'U Maryland', 'nra': 34.8,
        'file': 'data/western_us_dissertations/umd_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'type_filter': 'dissertation',  # Filter to dissertations only (PhD)
        'degree_label': 'phd',
    },
    {   # UMD Master's theses (separate entry)
        'key': 'umd', 'name': 'U Maryland', 'nra': 34.8,
        'file': 'data/western_us_dissertations/umd_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'type_filter': 'thesis',
        'degree_label': 'ms',
        '_merge': True,
    },
    # ── Phase 8b: Tier 2 — UIUC, CMU, UW Seattle ──
    {
        'key': 'uiuc', 'name': 'UIUC', 'nra': 37.9,
        'file': 'data/western_us_dissertations/uiuc_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'type_filter': 'thesis',
    },
    {
        'key': 'cmu', 'name': 'Carnegie Mellon', 'nra': 56.8,
        'file': 'data/western_us_dissertations/cmu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
        'type_filter': 'thesis',
    },
    {
        'key': 'uw_seattle', 'name': 'UW Seattle', 'nra': 16.6,
        'file': 'data/uw_dissertations/uw_etd_metadata.csv',
        'dept_source': 'column_department', 'dept_map': {},
        'years': (2016, 2024),
        'creator_field': 'author',
    },
    # ── Phase 8c: Cornell, Columbia, Penn State ──
    {
        'key': 'cornell', 'name': 'Cornell', 'nra': 32.2,
        'file': 'data/western_us_dissertations/cornell_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'columbia', 'name': 'Columbia', 'nra': 19.7,
        'file': 'data/western_us_dissertations/columbia_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'penn_state', 'name': 'Penn State', 'nra': 32.5,
        'file': 'data/western_us_dissertations/penn_state_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    # ── Phase 8d: Tier A + UVA ──
    {
        'key': 'uutah', 'name': 'U Utah', 'nra': 15.9,
        'file': 'data/western_us_dissertations/uutah_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'uva', 'name': 'U Virginia', 'nra': 14.1,
        'file': 'data/western_us_dissertations/uva_etds.csv',
        'dept_source': 'column_department', 'dept_map': {},
        'years': (2016, 2024),
        'creator_field': 'author',
    },
    {
        'key': 'msu', 'name': 'Michigan State', 'nra': 16.7,
        'file': 'data/western_us_dissertations/msu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'uf', 'name': 'U Florida', 'nra': 18.4,
        'file': 'data/western_us_dissertations/uf_etds.csv',
        'dept_source': 'column_department', 'dept_map': {},
        'years': (2016, 2024),
        'creator_field': 'creator',
    },
    {
        'key': 'uga', 'name': 'U Georgia', 'nra': 20.2,
        'file': 'data/western_us_dissertations/uga_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'northwestern', 'name': 'Northwestern', 'nra': 20.4,
        'file': 'data/western_us_dissertations/northwestern_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    # ── Phase 8e: Remaining R1 OAI harvests ──
    {
        'key': 'temple', 'name': 'Temple', 'nra': 10.6,
        'file': 'data/western_us_dissertations/temple_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'gmu', 'name': 'George Mason', 'nra': 17.7,
        'file': 'data/western_us_dissertations/gmu_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    {
        'key': 'utk', 'name': 'U Tennessee', 'nra': 17.2,
        'file': 'data/western_us_dissertations/utk_etds.csv',
        'dept_source': 'subject_generic', 'dept_map': {},
        'years': (2016, 2024),
    },
    # Auburn removed — OAI data contains only journal articles/reports, no theses
    # ── Phase 9: Caltech department alumni (scraped from dept websites) ──
    {
        'key': 'caltech', 'name': 'Caltech', 'nra': 64.9,
        'file': 'data/caltech_dissertations/caltech_dept_alumni_combined.csv',
        'dept_source': 'column_department', 'dept_map': {},
        'years': (1966, 2026),
        'creator_field': 'name',
        'date_field': 'year',
        'url_field': 'thesis_url',
        'degree_filter': 'phd',
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


def infer_degree_type(row, config):
    """Infer PhD vs Masters from available metadata. Returns 'phd', 'ms', or ''."""
    # Config-level override (e.g. collection is known to be all-PhD)
    forced = config.get('degree_label')
    if forced:
        return forced

    # Explicit degree_type, degree, or degree_level column
    dt = (row.get('degree_type', '') or row.get('degree', '') or row.get('degree_level', '') or '').lower().strip()
    if dt in ('phd', 'doctoral', 'doctorate') or dt.startswith(('phd ', 'phd(', 'ph.d', 'edd', 'ed.d', 'sjd', 'dnp', 'dma', 'd.m')) or 'doctor' in dt:
        return 'phd'
    if dt in ('masters', 'master', 'ms', 'msc', 'ma', 'mfa', 'med', 'mla') or dt.startswith(('ms ', 'ms(', 'ma ', 'ma(', 'mfa', 'me ', 'me(', 'llm', 'mar ', 'march', 'muep', 'm.s', 'm.a', 'm.e')):
        return 'ms'
    # Skip bachelor's theses
    if dt.startswith(('bs ', 'bs(', 'ba ', 'ba(', 'bsc', 'b.s', 'b.a')):
        return 'bs'

    # Check OAI set membership (bepress repos like UTA have _dissertations vs _theses)
    oai_set = (row.get('oai_set', '') or '').lower()
    has_diss = 'dissertation' in oai_set
    has_thes = 'theses' in oai_set or 'thesis' in oai_set
    if has_diss and not has_thes:
        return 'phd'
    if has_thes and not has_diss:
        return 'ms'

    # Check type field
    t = (row.get('type', '') or '').lower()
    if 'doctoral' in t or ('dissertation' in t and 'thesis' not in t):
        return 'phd'
    if 'masters' in t or ('thesis' in t and 'dissertation' not in t
                          and 'text' not in t and 'reproduction' not in t):
        return 'ms'

    # Check relation field (Penn State stores PHD/MASTERS here)
    rel = (row.get('relation', '') or '').upper().strip()
    if rel == 'PHD' or rel == 'DOCTORAL':
        return 'phd'
    if rel in ('MASTERS', 'MASTER', 'MS', 'MA'):
        return 'ms'

    # Check description field
    desc = (row.get('description', '') or '').lower()
    if 'ph.d' in desc or 'doctor of philosophy' in desc or 'doctoral' in desc:
        return 'phd'
    if 'master of science' in desc or 'master of arts' in desc or 'm.s.' in desc or 'm.sc' in desc:
        return 'ms'

    return ''


def load_records(config):
    records = []
    date_field = config.get('date_field', 'date')
    url_field = config.get('url_field', None)
    degree_filter = config.get('degree_filter', None)
    with open(config['file'], encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            yr = extract_year(row.get(date_field, ''))
            if not yr or yr < config['years'][0] or yr > config['years'][1]:
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
