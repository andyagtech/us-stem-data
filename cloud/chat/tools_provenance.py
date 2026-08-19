"""
Provenance tools for the chat assistant: coverage, caveats, citations.

These three tools exist so a figure this assistant quotes can be checked by
someone who does not trust it.  They are the accuracy floor of the whole tool
surface, so every assertion in this module was verified against the code or the
data before it was written down, and anything that could not be verified was
left out.  A caveat that turns out to be wrong is worse than a missing one.

  coverage_for(university)  what we hold and, more importantly, what we do NOT,
                            so a number can be quoted with its completeness
                            attached.
  caveats_for(topic)        the registry of known, VERIFIED limitations of a
                            metric, a dataset or a university.
  cite(metric, ...)         a citation a reader can paste into a footnote.

Conventions follow ``tools.py``: ``_fn`` builds the OpenAI function schema,
``_clamp`` bounds integers, results carry ``source`` and ``scope``, errors are
returned rather than raised, and anything containing harvested text carries the
``_untrusted`` banner.

Registry wiring (SCHEMAS / IMPL) is done by the caller; this module registers
nothing itself and does not modify ``tools.py``.

NOTE FOR DEPLOYMENT: ``infra/chat/deploy.sh`` copies an explicit list of .py
files into the Lambda bundle.  ``tools_provenance.py`` must be added to that
list or the module will be missing at runtime.
"""
from __future__ import annotations

try:                                            # package layout (repo)
    from .tools import _fn, _clamp, UNTRUSTED
except ImportError:                             # flat layout (Lambda zip)
    from tools import _fn, _clamp, UNTRUSTED

try:
    from . import data_store as ds
except ImportError:
    import data_store as ds


# ---------------------------------------------------------------------------
# COVERAGE SNAPSHOT
#
# pipeline/manifest.json is NOT bundled into the Lambda zip (infra/chat/
# deploy.sh copies only chat_data/*.{csv,csv.gz,json}), so the fields the
# manifest carries are embedded here as a dated snapshot rather than read at
# request time.  Refresh it by re-running the one-liner recorded in
# COVERAGE_SNAPSHOT["regenerate"] against a current pipeline/manifest.json.
#
# Tuple layout, per university key:
#   0 stem records total          5 non-STEM records
#   1 stem phd                    6 flags: h1b,opt,lca,perm,enrollment,
#   2 stem ms                       funding,dept_links  ('1'/'0')
#   3 stem unlabelled             7 h1b years
#   4 stem label_pct              8 opt years
#                                 9 lca certifications matched
# ---------------------------------------------------------------------------
COVERAGE_SNAPSHOT = {
    "built_from": "pipeline/manifest.json",
    "manifest_last_run": "2026-08-18T23:31 (process + process_nonstem, all 105 universities)",
    "universities": 105,
    "regenerate": (
        "python3 -c \"import json;m=json.load(open('pipeline/manifest.json'));"
        "print({k:(v['records']['total'],v['records']['phd'],v['records']['ms'],"
        "v['records']['unlabeled'],v['records']['label_pct'],"
        "v.get('process_nonstem',{}).get('records',0),"
        "''.join('1' if v['data_sources'].get(f) else '0' for f in "
        "('h1b','opt','lca','perm','enrollment','funding','dept_links')),"
        "v['data_sources'].get('h1b_years',0),v['data_sources'].get('opt_years',0),"
        "v['data_sources'].get('lca_total',0)) for k,v in sorted(m.items())})\""
    ),
}

_FLAG_ORDER = ("h1b", "opt", "lca", "perm", "enrollment", "funding", "dept_links")

_FLAG_LABEL = {
    "h1b": "USCIS H-1B Employer Data Hub petitions filed by the university",
    "opt": "ICE/SEVP OPT, STEM-OPT and CPT counts for this campus",
    "lca": "DOL Labor Condition Applications (job titles, SOC codes, wages)",
    "perm": "DOL PERM permanent-labour certifications (green-card sponsorship)",
    "enrollment": "IPEDS Fall Enrolment and NSF GSS graduate enrolment",
    "funding": "NSF HERD R&D expenditure series",
    "dept_links": "links from a department name to that department's own web page",
}

_FLAG_ABSENT_REASON = {
    "h1b": ("No employer name in entity_map.json resolved to this campus in the "
            "USCIS files. USCIS truncates employer names at 35 characters and "
            "reports at the employer (often system) level."),
    "opt": ("SEVP publishes only a Top-100 school list, so a campus outside the "
            "top 100 has no published OPT figure. The students exist; the "
            "publication does not cover them."),
    "lca": "No DOL LCA certification matched this employer name in FY2013-FY2026 Q1.",
    "perm": ("No PERM certification matched. Many universities sponsor few or no "
             "green cards directly, so an absence here is often real, not a gap."),
    "enrollment": "No IPEDS/GSS enrolment row joined on this UNITID.",
    "funding": ("Not in the NSF HERD table used. HERD covers institutions above a "
                "reporting threshold, so smaller research campuses are absent."),
    "dept_links": "No department link table has been built for this university yet.",
}

_COVERAGE_ROWS = {
    "binghamton":          (119, 31, 74, 14, 88.2, 50, '1110111', 1, 8, 506),
    "boise_state":         (846, 251, 550, 45, 94.7, 426, '1010111', 17, 0, 334),
    "bu":                  (11444, 1836, 1852, 7756, 32.2, 7361, '1111111', 17, 8, 1802),
    "byu":                 (2598, 662, 1935, 1, 100.0, 1611, '1011111', 15, 0, 284),
    "caltech":             (2435, 2435, 0, 0, 100.0, 0, '1011111', 16, 0, 2401),
    "clemson":             (3360, 1758, 1602, 0, 100.0, 1454, '1111111', 17, 5, 937),
    "cmu":                 (3312, 2894, 278, 140, 95.8, 801, '1111101', 17, 8, 1784),
    "columbia":            (4150, 3828, 322, 0, 100.0, 3984, '1111101', 17, 8, 5023),
    "cornell":             (6410, 683, 1996, 3731, 41.8, 812, '1111101', 17, 8, 2016),
    "cu_boulder":          (2477, 2477, 0, 0, 100.0, 638, '0000000', 0, 0, 0),
    "cuny":                (1817, 1474, 343, 0, 100.0, 3169, '1010111', 12, 0, 510),
    "dartmouth":           (635, 464, 171, 0, 100.0, 116, '1011111', 17, 0, 679),
    "duke":                (2934, 2260, 674, 0, 100.0, 1201, '1111111', 17, 8, 3345),
    "gatech":              (6960, 5346, 1614, 0, 100.0, 472, '1111111', 16, 8, 1696),
    "gmu":                 (7110, 1900, 806, 4404, 38.1, 3858, '1111101', 17, 8, 748),
    "harvard":             (4134, 4125, 3, 6, 99.9, 2187, '1111111', 17, 8, 4260),
    "iowa_state":          (8455, 2491, 5396, 568, 93.3, 2082, '1111111', 15, 8, 1863),
    "kstate":              (2941, 548, 1921, 472, 84.0, 2180, '1011111', 17, 0, 1022),
    "la_tech":             (231, 231, 0, 0, 100.0, 157, '1010101', 13, 0, 184),
    "lsu":                 (3335, 1905, 1430, 0, 100.0, 1908, '1011111', 14, 0, 1407),
    "marquette":           (767, 346, 421, 0, 100.0, 431, '1010111', 17, 0, 344),
    "mines":               (8250, 2702, 5427, 121, 98.5, 25, '1010111', 16, 0, 249),
    "missouri_st":         (1598, 928, 670, 0, 100.0, 24, '1111111', 17, 7, 104),
    "mit":                 (14203, 3409, 3374, 7420, 47.8, 2657, '1111111', 17, 8, 565883),
    "montana_state":       (1248, 310, 0, 938, 24.8, 777, '0000000', 0, 0, 0),
    "msstate":             (3419, 1645, 1774, 0, 100.0, 0, '1011111', 17, 0, 804),
    "msu":                 (4311, 3238, 1073, 0, 100.0, 2458, '1111101', 17, 7, 2954),
    "mtu":                 (1757, 749, 999, 9, 99.5, 132, '1111111', 17, 6, 368),
    "nau":                 (371, 0, 354, 17, 95.4, 382, '1010111', 15, 0, 253),
    "ncstate":             (7475, 4778, 2169, 528, 92.9, 760, '1110101', 4, 8, 2009),
    "niu":                 (1049, 353, 679, 17, 98.4, 1138, '1110111', 15, 6, 334),
    "njit":                (777, 572, 205, 0, 100.0, 23, '1110111', 13, 8, 384),
    "northern_colorado":   (163, 162, 1, 0, 100.0, 655, '1010111', 9, 0, 106),
    "northwestern":        (2540, 2529, 11, 0, 100.0, 1165, '1111101', 14, 8, 3733),
    "olemiss":             (1049, 459, 559, 31, 97.0, 1145, '1010111', 14, 0, 1743),
    "pdx":                 (1118, 500, 600, 18, 98.4, 914, '1010111', 17, 0, 186),
    "penn_state":          (10747, 7076, 3568, 103, 99.0, 0, '1111101', 17, 8, 2697),
    "purdue":              (8058, 6397, 1661, 0, 100.0, 1847, '1111111', 17, 8, 4254),
    "rice":                (4911, 1215, 1552, 2144, 56.3, 1368, '1111101', 17, 5, 1075),
    "rit":                 (2931, 469, 2462, 0, 100.0, 445, '1111111', 12, 8, 455),
    "rpi":                 (1580, 1184, 369, 27, 98.3, 1, '1010111', 14, 0, 901),
    "sdsu":                (1411, 432, 920, 59, 95.8, 174, '1010111', 16, 0, 358),
    "siu":                 (1797, 667, 1130, 0, 100.0, 1066, '1110111', 5, 1, 598),
    "smu":                 (510, 386, 124, 0, 100.0, 257, '1110111', 11, 5, 402),
    "stanford":            (8310, 8310, 0, 0, 100.0, 2186, '1110111', 17, 8, 707),
    "stony_brook":         (561, 397, 139, 25, 95.5, 167, '1111111', 3, 8, 793),
    "syracuse":            (1088, 1021, 48, 19, 98.3, 631, '1111111', 17, 8, 525),
    "temple":              (2775, 1761, 623, 391, 85.9, 684, '1011101', 17, 0, 2117),
    "ttu":                 (5274, 1637, 1265, 2372, 55.0, 2914, '1111111', 17, 8, 2528),
    "uarizona":            (7401, 3318, 3845, 238, 96.8, 4329, '1011111', 13, 0, 2032),
    "uarkansas":           (2523, 1114, 1409, 0, 100.0, 1421, '1011111', 17, 0, 2836),
    "ubuffalo":            (3083, 1786, 1173, 124, 96.0, 1160, '1110111', 9, 8, 1320),
    "ucberkeley":          (5963, 5963, 0, 0, 100.0, 2299, '1111111', 14, 8, 2375),
    "ucdavis":             (3147, 3147, 0, 0, 100.0, 861, '1111111', 11, 7, 2771),
    "ucf":                 (2814, 1011, 1154, 649, 76.9, 1973, '1110111', 12, 3, 641),
    "ucirvine":            (4552, 4552, 0, 0, 100.0, 1852, '1111111', 13, 8, 1266),
    "ucla":                (7108, 7108, 0, 0, 100.0, 3422, '1111111', 5, 8, 2896),
    "ucmerced":            (828, 828, 0, 0, 100.0, 279, '1010111', 14, 0, 230),
    "uconn":               (1103, 1103, 0, 0, 100.0, 530, '0000000', 0, 0, 0),
    "ucriverside":         (2763, 2763, 0, 0, 100.0, 1032, '1110111', 11, 3, 1035),
    "ucsb":                (2491, 2491, 0, 0, 100.0, 1202, '1011111', 1, 0, 1104),
    "ucsc":                (1849, 1849, 0, 0, 100.0, 814, '1011111', 5, 0, 530),
    "ucsd":                (7453, 7453, 0, 0, 100.0, 1843, '1111111', 13, 8, 3340),
    "ucsf":                (1475, 1475, 0, 0, 100.0, 229, '1011111', 3, 0, 3800),
    "udel":                (3977, 2667, 1310, 0, 100.0, 274, '1011111', 15, 0, 725),
    "udenver":             (607, 346, 244, 17, 97.2, 844, '1011111', 17, 0, 276),
    "uf":                  (9271, 6210, 2821, 240, 97.4, 1438, '1111101', 16, 8, 3557),
    "uhouston":            (3905, 2702, 1202, 1, 100.0, 1971, '1111111', 17, 8, 1629),
    "uiuc":                (5119, 3061, 2055, 3, 99.9, 1210, '1101101', 2, 8, 0),
    "ukansas":             (4245, 2241, 1457, 547, 87.1, 4970, '1011111', 14, 0, 2120),
    "uky":                 (1915, 1915, 0, 0, 100.0, 1418, '0000000', 0, 0, 0),
    "ulouisville":         (1281, 830, 450, 1, 99.9, 970, '1010111', 17, 0, 898),
    "umass":               (7708, 4280, 1433, 1995, 74.1, 8162, '1111111', 13, 6, 818),
    "umd":                 (4318, 3306, 1012, 0, 100.0, 15, '1111101', 16, 8, 2484),
    "umemphis":            (1427, 795, 607, 25, 98.2, 997, '1111111', 17, 1, 366),
    "umissouri":           (2627, 16, 2415, 196, 92.5, 1509, '1111111', 17, 7, 2871),
    "umn":                 (7496, 4749, 2084, 663, 91.2, 3045, '1111111', 16, 8, 3724),
    "umt":                 (943, 290, 528, 125, 86.7, 873, '1010111', 16, 0, 214),
    "und":                 (1018, 463, 555, 0, 100.0, 755, '1011111', 14, 0, 428),
    "unh":                 (1211, 506, 705, 0, 100.0, 475, '1011111', 17, 0, 381),
    "unl":                 (1349, 1348, 1, 0, 100.0, 1006, '1011111', 15, 0, 36),
    "unlv":                (1360, 688, 672, 0, 100.0, 1306, '1010111', 9, 0, 433),
    "unm":                 (2046, 1063, 526, 457, 77.7, 1386, '1010111', 17, 0, 865),
    "unt":                 (1817, 1105, 712, 0, 100.0, 2423, '1111111', 17, 7, 904),
    "uoregon":             (1866, 1224, 352, 290, 84.5, 1308, '1011101', 17, 0, 779),
    "upenn":               (5619, 5053, 222, 344, 93.9, 4098, '1111111', 13, 8, 5616),
    "usc_columbia":        (2392, 1493, 826, 73, 96.9, 2393, '1011111', 16, 0, 1775),
    "usd":                 (172, 81, 76, 15, 91.3, 197, '1010111', 11, 0, 258),
    "usf":                 (2898, 1649, 1246, 3, 99.9, 2102, '1111111', 16, 8, 1024),
    "usm":                 (832, 443, 389, 0, 100.0, 1132, '1010111', 16, 0, 206),
    "utah_state":          (1493, 530, 930, 33, 97.8, 595, '1011111', 17, 0, 502),
    "utarlington":         (2454, 1499, 955, 0, 100.0, 831, '1110111', 8, 8, 744),
    "utaustin":            (12771, 5888, 5578, 1305, 89.8, 3637, '1111111', 13, 8, 2730),
    "utdallas":            (2301, 1260, 1022, 19, 99.2, 858, '1111111', 14, 8, 932),
    "utk":                 (4627, 2300, 3, 2324, 49.8, 2338, '1011101', 11, 0, 2872),
    "uutah":               (1569, 1064, 490, 15, 99.0, 381, '1111101', 14, 8, 2561),
    "uva":                 (5372, 4001, 1368, 3, 99.9, 7, '1111101', 15, 7, 2959),
    "uw_seattle":          (5518, 2971, 2546, 1, 100.0, 1971, '1111101', 16, 8, 2669),
    "uwmadison":           (618, 6, 612, 0, 100.0, 250, '1111101', 5, 8, 1255),
    "vt":                  (13982, 6100, 7870, 12, 99.9, 3258, '1111111', 12, 7, 26),
    "washu":               (2231, 1607, 366, 258, 88.4, 1320, '1111111', 17, 7, 1863),
    "wayne_state":         (1454, 1138, 316, 0, 100.0, 955, '1111111', 17, 5, 1140),
    "wsu":                 (3171, 1773, 1398, 0, 100.0, 1130, '1010101', 5, 0, 1099),
    "wvu":                 (2800, 1304, 1331, 165, 94.1, 1452, '1011111', 17, 0, 1714),
    "yale":                (1235, 1235, 0, 0, 100.0, 668, '1111111', 17, 8, 4192),
}


# ---------------------------------------------------------------------------
# CAVEAT REGISTRY
#
# Every entry was checked against the code or the data named in "verified".
# Entries that a document asserted but the data did not support were dropped;
# where a documented claim was wrong in part, the entry states the correction
# rather than repeating the claim.
#
#   id           stable handle, quotable
#   title        one line a reader can act on
#   severity     "high"   = can invalidate the figure or the comparison
#                "medium" = changes how the figure must be described
#   scope        "metric" | "dataset" | "university" | "always"
#                "always" entries come back for any university topic.
#   applies_to   metric / dataset handles this entry attaches to
#   keywords     extra search terms
#   universities specific university keys, or None for all
#   detail       what is actually true
#   consequence  what a careful writer does about it
#   verified     the file, code path or measurement that establishes it
# ---------------------------------------------------------------------------
CAVEATS = [
    {
        "id": "ipeds_award_level_break",
        "title": ("IPEDS recoded doctoral award levels between 2008 and 2010; a series "
                  "filtered to award level 17 alone breaks across that boundary."),
        "severity": "high",
        "scope": "metric",
        "applies_to": ["nra_share", "phd_completions", "completions_trend",
                       "ipeds_completions", "nra_distribution"],
        "keywords": ["awlevel", "award level", "level 17", "level 9", "recode",
                     "2008", "2009", "2010", "long series", "since 1995", "trend"],
        "universities": None,
        "detail": (
            "IPEDS Completions carries two doctoral award-level schemes. Through 2007: "
            "AWLEVEL 9 'Doctor's degree' plus AWLEVEL 10 'First-professional degree'. "
            "From 2010: 17 research/scholarship, 18 professional practice, 19 other. "
            "BOTH schemes appear in the 2008 and 2009 files. Institutions converted "
            "individually and no institution reports under both blocks in the same year "
            "(zero overlap, checked on the raw files for 2006-2010). So an AWLEVEL-17 "
            "filter returns nothing before 2008 and only part of the field in 2008-2009: "
            "12,347 doctorates in 2008 against 57,661 in 2010. That is a coding artefact, "
            "not a collapse and not a boom."
        ),
        "consequence": (
            "This assistant's nra_lookup is already safe here: the index assigns each "
            "institution one basis per year (aw09 before the switch, aw17 after), so a "
            "1995-2025 series is continuous. Anyone pulling AWLEVEL 17 straight out of "
            "the raw IPEDS files must not splice it to a pre-2008 series."
        ),
        "verified": (
            "scripts/build_nra_index.py lines 165-211 (per-institution basis selection); "
            "data/ipeds/nra_index_meta.json awlevel_rule; "
            "data/ipeds/nra_ground_truth/_metadata.md 'Award-level scheme transition'; "
            "raw AWLEVEL tabulation of data/ipeds/c2006-c2010, 0 institutions in both "
            "blocks in any year."
        ),
        "correction": (
            "A note in this project's own git history says award level 9 'also counted "
            "MD and JD'. It did not, and the caveat's real reason is different. MD (CIP "
            "51.1201), JD (22.0101), DDS (51.0401), DVM and PharmD were AWLEVEL 10, "
            "'first-professional', before the change and AWLEVEL 18 after it - outside "
            "the research bucket in both schemes, zero of them under AWLEVEL 9 in any "
            "year. (CIP family 22 does carry 143 awards at level 9 in 2007, but those are "
            "SJD research doctorates in law, not JDs.) What actually makes level 9 "
            "broader than level 17 is that 9 was the undifferentiated 'Doctor's degree', "
            "split in 2010 into 17 research/scholarship and 18 professional practice, "
            "with PharmD, DPT, AuD and similar moving to 18. Health CIP family 51 shows "
            "it: 8,356 doctorates at level 9 in 2007 against 3,955 at level 17 in 2010, "
            "the balance now in 18. Across all fields, for the 398 institutions that "
            "switched between 2009 and 2010, that shrank the research bucket by about "
            "13% and raised measured NRA share by about 2.2 points (24.3% to 26.5%). "
            "National NRA share still runs fairly smoothly across the break - 28.2% in "
            "2007 on aw09, 27.3% in 2010 on aw17 - so the recoding distorts LEVELS and "
            "COUNTS much more than it distorts the SHARE."
        ),
    },
    {
        "id": "ipeds_cip_vintages",
        "title": "Six-digit CIP codes are not comparable across CIP vintages; two-digit families are.",
        "severity": "medium",
        "scope": "metric",
        "applies_to": ["nra_share", "phd_completions", "ipeds_completions", "cip"],
        "keywords": ["cip", "cip2020", "cip2010", "vintage", "field of study",
                     "subject", "code changed"],
        "universities": None,
        "detail": (
            "The index spans four CIP vintages: CIP1990 for 1995-1999, CIP2000 for "
            "2000-2009, CIP2010 for 2010-2019 and CIP2020 from 2020. Codes were added, "
            "retired and renumbered at each revision, so a six-digit series that crosses a "
            "vintage boundary can move because the code moved."
        ),
        "consequence": ("For any series before 2020, roll up to the two-digit family "
                        "(nra_lookup family:true) or say which vintage the code belongs to."),
        "verified": "data/ipeds/nra_index_meta.json cip_vintages; titles come from the CIP2020 list only.",
    },
    {
        "id": "nra_is_a_reporting_category",
        "title": "Non-resident alien is a federal reporting category for visa holders, not ethnicity or national origin.",
        "severity": "high",
        "scope": "always",
        "applies_to": ["nra_share", "nra_site_figure", "enrollment", "faculty",
                       "ipeds_completions", "phd_completions"],
        "keywords": ["nra", "non-resident", "nonresident", "international", "foreign",
                     "chinese", "ethnicity", "race", "citizenship", "definition"],
        "universities": None,
        "detail": (
            "IPEDS 'nonresident alien' (CNRALT / EFNRALT / HRNRALT) counts people in the "
            "United States on a temporary visa - F-1, J-1, H-1B and so on. It excludes "
            "permanent residents and naturalised citizens, who IPEDS puts in the "
            "race/ethnicity categories alongside native-born citizens. It says nothing "
            "about a person's race, ethnicity or country of origin, and there is no field "
            "in IPEDS that separates citizens from green-card holders."
        ),
        "consequence": (
            "Describe an NRA figure as a share on temporary visas. Never render it as a "
            "share who are foreign-born, Chinese, or of any nationality. NSF's SDR "
            "measures the other side of this: 28.1% of the doctoral workforce IPEDS calls "
            "domestic is foreign-born."
        ),
        "verified": ("data/ipeds/nra_index_meta.json 'measure'; data/DATA_DICTIONARY.md "
                     "Key Terminology and Citizenship Field Definitions by Source."),
    },
    {
        "id": "name_origin_is_not_visa_status",
        "title": "Name-origin classification is not a measure of visa status, and it is not IPEDS NRA.",
        "severity": "high",
        "scope": "always",
        "applies_to": ["foreign_name_pct", "name_origins", "departments",
                       "name_classification", "dissertation_records"],
        "keywords": ["name", "surname", "classification", "chinese names", "origin",
                     "foreign_name_pct", "r2", "predict"],
        "universities": None,
        "detail": (
            "The classifier reads a surname (and, for ambiguous surnames, a given name) "
            "against curated surname lists and returns one of chinese, korean, "
            "vietnamese, indian, iranian, turkish, arabic, excluded_ambiguous or other, "
            "with a confidence. It has no citizenship, visa or nationality input and no "
            "such output. A cohort's name composition does carry real signal about "
            "reported NRA share, but not enough to stand in for it. Held out by whole "
            "university across 5 folds on 1,153 university x CIP-family cells, name "
            "shares add 0.059 R2 over field of study alone (0.639 to 0.698) and 0.026 "
            "over field plus the institution's own published NRA share (0.713 to 0.739). "
            "Best-model RMSE is 0.112, about 11 percentage points."
        ),
        "consequence": (
            "Quote a name-origin percentage as what it is - a name-origin estimate for "
            "that department's dissertation authors - and never as a count of "
            "international students, Chinese nationals, or visa holders. An 11-point "
            "typical error means a department estimated at 40% is routinely 29% or 51% on "
            "the reported measure. RMSE is a typical error, not a bound."
        ),
        "verified": (
            "scripts/name_classifier.py classify() - no visa/citizenship field exists; "
            "scripts/name_signal_study.py, re-run read-only on its cached cells, "
            "reproducing 0.059 / 0.026 / RMSE 0.112 exactly. Two honest qualifiers: those "
            "are the POOLED-over-year panel; the by-year panel (n=6,950) gives +0.055 and "
            "+0.038 with RMSE 0.150. And on the current data/processed corpus the "
            "increments are +0.073 and +0.033 with RMSE 0.109 - the conclusion is "
            "unchanged, the exact decimals are snapshot-bound."
        ),
    },
    {
        "id": "harvest_year_is_often_a_deposit_date",
        "title": ("Harvested record YEARS are unreliable: for most universities the stored "
                  "year is when the repository ingested the file, not when the degree was "
                  "awarded."),
        "severity": "high",
        "scope": "always",
        "applies_to": ["dissertation_records", "records", "record_years", "departments",
                       "foreign_name_pct"],
        "keywords": ["year", "date", "accessioned", "issued", "deposit", "ingest",
                     "timestamp", "record_years", "harvest", "when", "trend over time"],
        "universities": None,
        "detail": (
            "The OAI harvester takes the FIRST dc:date element in an oai_dc record. "
            "oai_dc flattens accessioned, available and issued into repeated dc:date "
            "elements and DSpace emits the accession timestamp first, so the harvester "
            "stores the ingest moment. Confirmed live against both repositories: an Iowa "
            "State record stores 2018-08-22T18:45:17 for a 1934 degree; an MIT record "
            "stores 2005-08-18T12:00:00Z for a 1996 degree. Corpus-wide, 407,462 of "
            "1,035,726 in-window rows - 39.3% - carry a date with a clock time, which "
            "only an ingest timestamp has, and 72 of the 105 universities have more than "
            "90% of their in-window rows timestamped that way."
        ),
        "consequence": (
            "Do NOT read a record-year distribution as a graduation-year distribution, "
            "and do not build a trend over time out of these years. A per-university "
            "total and a name-origin composition are unaffected; anything with a year "
            "axis is not. Record counts by year are safe only where the repository "
            "publishes a real issued date."
        ),
        "verified": (
            "scripts/scrape_oai_etds.py line 1274 takes the first dc:date; "
            "scripts/generate_name_lists.py extract_year()/date_field apply the "
            "configured year window to it; live GetRecord calls to dr.lib.iastate.edu "
            "and dspace.mit.edu; clock-time census over all 105 configured CSVs."
        ),
        "correction": (
            "Two figures this project has written down do not reproduce, and the "
            "reproducible ones are these. Sampling 250 in-window records per university "
            "and re-fetching each from the source: Iowa State 59.9% awarded outside its "
            "[2019, 2026] window (63.6% if records with no plain date are counted as "
            "outside), NOT 84%; median lag 24 years, which does match. MIT 19.2% outside "
            "its [2016, 2026] window, consistent with the 22% on file; median lag of the "
            "outside-window records 49.5 years, NOT 39. Also worth knowing: the harvester "
            "fix that computes an issued date has never reached disk, because on a "
            "selective re-harvest the writer reuses the existing file header with "
            "extrasaction='ignore' and silently drops the new column. No CSV in the "
            "repository has a date_issued column."
        ),
    },
    {
        "id": "northwestern_years_were_deposit_dates",
        "title": "Northwestern's record years were deposit timestamps; the correction is not committed.",
        "severity": "high",
        "scope": "university",
        "applies_to": ["dissertation_records", "record_years"],
        "keywords": ["northwestern", "deposit", "arch", "date_uploaded", "2026"],
        "universities": ["northwestern"],
        "detail": (
            "The Northwestern refresher read date_uploaded_dtsi, the ARCH deposit "
            "timestamp. Joining the pre-fix and post-fix files on record id: deposit year "
            "equals degree year for only 25.1% of 4,902 records, median lag one year, "
            "with a spike of 717 records deposited 10-11 years after the degree in a 2018 "
            "bulk load of 2007-2008 degrees. 803 records that were inside the 2016-2026 "
            "window on deposit dates fall outside it on degree dates; the in-window count "
            "goes from 4,899 to 4,096."
        ),
        "consequence": (
            "Treat Northwestern's per-year record counts as unusable and its total as "
            "roughly 16% too high until the corrected file is committed and reprocessed. "
            "The claim that its 2025-2026 records were real graduation dates rather than "
            "bulk imports does not hold: the pre-fix file's newest rows are a repeated "
            "2026-03-25T00:00:00Z batch."
        ),
        "verified": ("scripts/refresh_frozen_etds.py date field, corrected only in the "
                     "uncommitted working tree; "
                     "data/western_us_dissertations/northwestern_etds.csv.bak_predatefix "
                     "(4,900 of 4,903 rows clock-timestamped) joined against the current "
                     "file on record id."),
    },
    {
        "id": "uva_2026_records_have_no_degree_date",
        "title": "UVA's post-2025 records carry a deposit-workflow timestamp and no degree date at all.",
        "severity": "high",
        "scope": "university",
        "applies_to": ["dissertation_records", "record_years"],
        "keywords": ["uva", "virginia", "publishedat", "2026", "workflow"],
        "universities": ["uva"],
        "detail": (
            "UVA's new-format API records expose createdAt, modifiedAt and publishedAt "
            "and no conferral field of any kind - only a degree string. The harvester "
            "stores publishedAt, which lands about a day after the PDF upload. In "
            "uva_etds.csv every row dated 1885-2024 is exactly T00:00:00 (a real "
            "conferral date), while 1,346 rows carry a real clock time, beginning "
            "2025-08-29 and running to the present. All 1,157 records the site counts as "
            "2026 are of that kind."
        ),
        "consequence": ("Do not quote a UVA 2025 or 2026 record count as graduates in "
                        "those years. The award date is not available upstream, so this "
                        "cannot be fixed by reharvesting."),
        "verified": ("scripts/refresh_frozen_etds.py stores publishedAt; direct API fetch "
                     "of a new-format UVA record returns createdAt/modifiedAt/publishedAt "
                     "only; timestamp census of data/western_us_dissertations/uva_etds.csv "
                     "(15,162 rows)."),
    },
    {
        "id": "opt_top_100_only",
        "title": "OPT covers only 59 of our 105 universities because SEVP publishes a Top-100 list.",
        "severity": "high",
        "scope": "dataset",
        "applies_to": ["opt", "stem_opt", "cpt"],
        "keywords": ["opt", "stem opt", "cpt", "sevp", "sevis", "top 100", "missing", "coverage"],
        "universities": None,
        "detail": (
            "ICE/SEVP publishes per-campus OPT and STEM-OPT figures only as annual "
            "'Top 100 school campuses' PDFs. A campus outside the top 100 in a given year "
            "simply does not appear. 59 of the 105 universities here have any OPT figure; "
            "46 have none. Coverage also varies within a university, because a campus can "
            "be inside the top 100 in one year and outside it in the next."
        ),
        "consequence": (
            "Absence of an OPT figure is absence of a PUBLICATION, not absence of "
            "students. Never rank universities by OPT without saying the list is drawn "
            "from a top-100 publication, and never read a missing year as a drop to zero."
        ),
        "verified": ("data/h1b/opt_by_university.json has 59 keys; source PDFs in data/h1b/ "
                     "are named ...top100-prepost-opt-schools.pdf and "
                     "...top100-stem-opt-schools.pdf; pipeline/manifest.json data_sources.opt "
                     "is true for 59 of 105."),
    },
    {
        "id": "labelling_rate_uncertainty",
        "title": "A low degree-labelling rate makes the PhD/master's split uncertain - it does not mean records are missing.",
        "severity": "high",
        "scope": "always",
        "applies_to": ["dissertation_records", "phd", "ms", "records", "label_pct"],
        "keywords": ["unlabelled", "unlabeled", "label", "phd vs masters", "degree",
                     "labelling rate", "split"],
        "universities": None,
        "detail": (
            "Every harvested record is a real thesis or dissertation. The degree LABEL is "
            "inferred by a nine-step chain over whatever the repository publishes, and "
            "some repositories publish nothing usable through the metadata format the "
            "harvester requests. Where the labelling rate is low the unlabelled records "
            "are still counted in the total and still name-classified; only the PhD/MS "
            "split is unknown for them. Corpus labelling is 88.8% (327,802 of 369,319 "
            "STEM records), ranging from 24.8% to 100% across the 105 universities."
        ),
        "consequence": (
            "Quote the total confidently. Quote a PhD count from a university with a low "
            "label_pct only with the labelling rate attached, and never compute a PhD "
            "share by dividing labelled PhDs by the total. Call coverage_for first."
        ),
        "verified": ("pipeline/LABELING_METHODOLOGY.md inference chain; pipeline/manifest.json "
                     "records.label_pct; 327,802 labelled of 369,319 STEM records; "
                     "min 24.8 (montana_state), max 100.0, over 105 universities; "
                     "unlabelled records are retained in records.total."),
    },
    {
        "id": "uscis_h1b_is_employer_level",
        "title": "USCIS reports H-1B at the employer, which for a multi-campus system is the whole system.",
        "severity": "medium",
        "scope": "dataset",
        "applies_to": ["h1b"],
        "keywords": ["h1b", "h-1b", "uscis", "system", "campus", "employer",
                     "entity map", "truncated"],
        "universities": None,
        "detail": (
            "The USCIS H-1B Employer Data Hub keys on employer name, truncated to 35 "
            "characters, and a university system files under one name. Campus-level "
            "attribution is therefore a name-matching exercise (entity_map.json, 292 "
            "mappings), and for some campuses the only available figure is the parent "
            "system's aggregate."
        ),
        "consequence": ("Where a system-level note is attached, say the number covers the "
                        "system rather than the campus. coverage_for returns that note."),
        "verified": ("pipeline/entity_map.json; pipeline/system_h1b_map.json; "
                     "pipeline/manifest.json h1b_system_note; "
                     "data/h1b/DOWNLOAD_LINKS.md field list."),
    },
    {
        "id": "sheeo_state_funding_is_a_state_proxy",
        "title": "State appropriations shown against a university are the STATE total, not that institution's.",
        "severity": "high",
        "scope": "dataset",
        "applies_to": ["state_funding"],
        "keywords": ["sheeo", "shef", "state funding", "appropriations", "state support"],
        "universities": None,
        "detail": (
            "SHEEO does not publish institution-level appropriations. Each public "
            "university is joined to its state's SHEF time series as a proxy; private "
            "universities carry private_no_state = true."
        ),
        "consequence": ("Never say 'this university received $X in state appropriations'. "
                        "Say the state appropriated $X across its public system."),
        "verified": "scripts/build_sheeo_json.py, sheeo_by_university _meta note.",
    },
    {
        "id": "awlevel17_is_not_the_sed_universe",
        "title": "IPEDS research doctorates and NSF SED research doctorates are different universes.",
        "severity": "medium",
        "scope": "metric",
        "applies_to": ["phd_completions", "nra_share", "sed", "ipeds_completions"],
        "keywords": ["sed", "survey of earned doctorates", "ncses", "cross-cite",
                     "doctorate count"],
        "universities": None,
        "detail": (
            "IPEDS award level 17 is broader than the NSF Survey of Earned Doctorates: "
            "82,438 in 2023 against roughly 57,900 SED research doctorates, because many "
            "institutions file EdD, DBA and PsyD degrees under 17."
        ),
        "consequence": "Do not put an IPEDS count and an SED count in the same sentence without reconciling them.",
        "verified": "data/ipeds/nra_ground_truth/_metadata.md, 'Known source problems'.",
    },
    {
        "id": "lca_year_buckets_are_calendar",
        "title": ("LCA year buckets are CALENDAR years from DECISION_DATE; the first "
                  "bucket is a stub, and from FY2026 DOL ships cumulative files that "
                  "double-count if two are held at once."),
        "severity": "high",
        "scope": "dataset",
        "applies_to": ["lca"],
        "keywords": ["lca", "fiscal year", "calendar year", "decision_date", "2014",
                     "2026", "dol", "quarter", "partial year", "cumulative",
                     "superseded", "double count", "csv_cache"],
        "universities": None,
        "detail": (
            "Three separate things about the year axis. (1) No DOL LCA layout in this "
            "project's files carries a FISCAL_YEAR column, so the parser falls through to "
            "DECISION_DATE and the buckets are CALENDAR years. (2) The earliest file with "
            "a decision date starts in October 2014, so calendar 2014 holds one quarter - "
            "13,909 certifications against 89,589 in 2015, a file-coverage artefact rather "
            "than a real trough; the one FY2013 file uses the old layout with no "
            "DECISION_DATE at all and contributes nothing. (3) From FY2026 DOL publishes "
            "CUMULATIVE year-to-date files: the FY2026 Q3 release contains every case in "
            "the FY2026 Q1 release. Holding both double-counts October to December 2025. "
            "FY2026 Q1 has been moved to data/h1b/lca/superseded/ for that reason. Note "
            "the consequence for the current year: with Q3 the newest file, calendar 2026 "
            "covers January to June only and will read as a collapse in volume if it is "
            "presented as an annual figure."
        ),
        "consequence": (
            "Start any LCA time series at 2015 and stop it at the last COMPLETE calendar "
            "year. Never describe these buckets as fiscal years, never present 2014 as a "
            "low year, and never present the current part-year as an annual total. Keep "
            "exactly one FY2026 file on disk."
        ),
        "verified": (
            "pipeline/step3_parse_federal.py fy_col = find_col('FISCAL_YEAR', "
            "'DECISION_DATE'); header scan of the LCA files finds no FISCAL column. "
            "Cumulativeness measured directly on the sheet XML of both releases, using "
            "each file's autoFilter ref for the true data extent: FY2026 Q1 = 83,120 "
            "records spanning 2025-10 to 2025-12, FY2026 Q3 = 437,496 records spanning "
            "2025-10 to 2026-06, and all 83,120 Q1 case numbers appear in Q3 with 0 "
            "absent. It is a CHANGE in DOL practice, not a standing one: FY2025 quarters "
            "are discrete, with FY2025 Q1 (2024-10 to 2024-12) and FY2025 Q4 (2025-07 to "
            "2025-09) sharing only 595 case numbers, 0.55%. So FY2013-FY2025 are "
            "unaffected."
        ),
        "correction": (
            "An earlier pass of this registry asserted that FY2026 files are NOT "
            "cumulative, on the evidence that the FY2026 Q1 file has more rows "
            "(1,042,437) than the FY2025 Q4 file (563,689). That reasoning was invalid "
            "twice over and the conclusion was wrong. A row count tests whether one file "
            "is larger, not whether a later file contains an earlier one - only "
            "case-number containment tests that, and it shows full containment. And the "
            "row counts themselves were wrong: 959,317 of the FY2026 Q1 file's rows are "
            "empty style-only padding emitted past the end of the data, so its real "
            "record count is 83,120, not 1,042,437. Any row-count comparison across these "
            "files must read the autoFilter ref rather than the sheet dimension."
        ),
        "operational_note": (
            "Moving or deleting the superseded .xlsx is NOT sufficient. "
            "_parse_lca_duckdb() builds its conversion list from the .xlsx files in "
            "data/h1b/lca/, but then aggregates csv_dir.glob('*.csv') independently, so a "
            "previously converted data/h1b/lca/csv_cache/lca_FY2026_Q1.csv would still be "
            "read and summed even though the workbook is gone. Delete the cached CSV too. "
            "The cache is keyed by filename, so it never notices the source moved."
        ),
    },
    {
        "id": "mit_lca_total_is_contaminated",
        "title": "MIT's shipped LCA total is wrong: a three-letter employer pattern swept in the national H-1B filers.",
        "severity": "high",
        "scope": "university",
        "applies_to": ["lca"],
        "keywords": ["mit", "lca", "565883", "565,883", "entity map", "substring"],
        "universities": ["mit"],
        "detail": (
            "pipeline/entity_map.json maps the bare pattern 'MIT' to the mit key. The "
            "employer matcher used to test that as a plain substring, so LIMITED, SMITH, "
            "SUMMIT and every employer containing those three letters was credited to "
            "MIT - INFOSYS LIMITED, WIPRO LIMITED, TATA CONSULTANCY SERVICES LIMITED "
            "among them. MIT's stored LCA total is 565,883 against 5,616 for the next "
            "highest university and a corpus median near 1,000, and its top job titles "
            "are 'Technology Lead - Us', 'Developer' and 'Consultant - Us'. The matcher "
            "has been fixed to require word boundaries, and a re-parse was under way "
            "when this entry was written. The check is the number itself: if MIT's LCA "
            "total still reads anywhere near 565,883, the artefact you are reading "
            "predates the fix. A plausible post-fix figure is in the low thousands, in "
            "line with comparable private research universities."
        ),
        "consequence": (
            "Do not quote MIT's LCA total, yearly LCA counts, wage percentiles or job "
            "titles while the total still reads 565,883. They are not MIT's. Every "
            "other university's LCA figures look "
            "unaffected: 'MIT' is the only one of the 296 patterns shorter than six "
            "characters, and the next highest total is upenn at 5,616."
        ),
        "verified": (
            "pipeline/step3_parse_federal.py _match_employer() docstring and word-boundary "
            "regex; pipeline/entity_map.json 'MIT'; data/h1b/lca_by_university.json mit "
            "total_lcas 565,883 with Infosys-style top titles, next highest upenn 5,616; "
            "cloud/chat/chat_data/universities_compact.json still carries 565,883."
        ),
    },
    {
        "id": "overstay_report_off_by_one",
        "title": "dhs_overstay_fy2025.pdf contains FY2024 data; the latest overstay data year is FY2024.",
        "severity": "medium",
        "scope": "dataset",
        "applies_to": ["overstay"],
        "keywords": ["overstay", "cbp", "entry exit", "fy2025", "off by one",
                     "reporting cycle"],
        "universities": None,
        "detail": (
            "data/vwp/dhs_overstay_fy2025.pdf is cover-titled 'Fiscal Year 2025 Report to "
            "Congress' but its opening message submits the Fiscal Year 2024 report, "
            "covering travellers expected to depart between 1 October 2023 and 30 "
            "September 2024, and its tables are FY2024. It shares a PDF creation "
            "timestamp with dhs_overstay_fy2024.pdf: they are two renderings of the same "
            "report. Its metadata is self-inconsistent, carrying both FY24 and FY25 "
            "title strings."
        ),
        "consequence": ("Cite any rate from that file as FY2024. There is no FY2025 "
                        "overstay data; that report is not due until 2026."),
        "verified": ("pdftotext of data/vwp/dhs_overstay_fy2025.pdf pages 1-6; its /Title "
                     "objects are both 'CBP - Entry Exit Overstay Report FY25' and "
                     "'... FY24'; identical CreationDate with dhs_overstay_fy2024.pdf."),
        "correction": (
            "data/vwp/DATA_SOURCES.md states this as a general CBP convention - that the "
            "filename follows a reporting cycle running a year ahead, so every file's "
            "data year is one less than its name. It is not general. "
            "dhs_overstay_fy2023.pdf is cover-titled FY2023 and carries FY2023 data "
            "(October 2022 to September 2023), and dhs_overstay_fy2024.pdf is FY2024 and "
            "carries FY2024 data. Only the FY2025 file is misnamed. Do NOT subtract one "
            "from the other two."
        ),
    },
    {
        "id": "lsu_federal_support_is_system_office",
        "title": "LSU's federal support figure is the Louisiana State University System office, not the Baton Rouge campus.",
        "severity": "high",
        "scope": "university",
        "applies_to": ["federal_support"],
        "keywords": ["lsu", "louisiana", "system", "system office", "ncses",
                     "federal support", "unh"],
        "universities": ["lsu"],
        "detail": (
            "The NCSES federal support survey table (NSF 25-339, Table 17) has no Baton "
            "Rouge LSU row at all - only 'Louisiana State U., system office'. The build "
            "hardcodes that override and marks the record system_level: true. LSU's "
            "$150,082,000 of federal obligations is therefore a system figure."
        ),
        "consequence": (
            "Say 'the LSU system' for that figure, never 'LSU Baton Rouge'. The "
            "system_level flag is written into the data but nothing on the site reads "
            "it, so the page shows no warning; this tool is where the caveat lives."
        ),
        "verified": ("scripts/build_federal_support_json.py NAME_OVERRIDES['lsu'] and "
                     "SYSTEM_LEVEL={'lsu'}; data/federal_support/nsf25339-tab017.xlsx "
                     "contains no Baton Rouge LSU row; site/data/stem/lsu.json "
                     "federal_support.system_level is true."),
        "correction": (
            "Two parts of the way this is usually stated do not hold. First, LSU's USCIS "
            "H-1B series is NOT a system aggregate: pipeline/system_h1b_map.json has no "
            "LSU entry, no system note is attached, and 85 of the 87 FY2025 approvals "
            "are Baton Rouge rows. What is wrong with that series is different and worth "
            "saying - the employer variant 'LOUISIANA STATE UNIV' matches no pattern, so "
            "2015, 2016 and 2018 read as 1-2 approvals when the real Baton Rouge filings "
            "were dozens. Those are matcher misses, not declines. Second, LSU is not the "
            "only university with this problem: UNH is matched to 'U. System New "
            "Hampshire' and is NOT flagged system_level, and Table 17 carries 15 system "
            "office rows in all."
        ),
    },
    {
        "id": "nra_site_figure_is_pinned",
        "title": ("The site's headline NRA figure per university is a pinned constant, "
                  "not a live IPEDS query."),
        "severity": "high",
        "scope": "metric",
        "applies_to": ["nra_site_figure", "list_universities"],
        "keywords": ["headline", "site figure", "43.8", "university nra",
                     "pinned", "nra_site_figure"],
        "universities": None,
        "detail": (
            "`nra` in pipeline/universities.json is a stored number with no recorded "
            "basis - no year window and no CIP list is stored alongside it. Where it "
            "does reproduce, the basis is the pooled non-resident share of research "
            "doctorates in the STEM CIP families 11, 14, 15, 26, 27, 30, 40 and 42 over "
            "a multi-year window: MIT 43.8% = 2,175/4,962 for 2015-2023, Colorado School "
            "of Mines 39.8% = 385/967 for 2015-2023, Binghamton 56.9% = 388/682 for "
            "2015-2022. The window is not uniform, and for 49 of the 105 universities "
            "the pinned figure does not reproduce under ANY of four CIP bases crossed "
            "with 35 year windows."
        ),
        "consequence": (
            "Present it as 'the figure this site prints', not as an IPEDS statistic for a "
            "stated year. For a number a reader can reproduce, call nra_lookup with the "
            "unitid, a stated year range and a stated CIP filter, and quote that instead."
        ),
        "verified": (
            "pipeline/universities.json carries `nra` and no basis fields; the three "
            "worked examples were recomputed from cloud/chat/chat_data/nra_index.csv.gz "
            "and match to the decimal; the 49 non-reproducing keys come from a sweep of "
            "CIP bases {core-8, DATA_DICTIONARY 15, enrichment 16, all fields} x windows "
            "starting 2013-2017 and ending 2019-2025."
        ),
    },
    {
        "id": "completions_trend_is_all_fields",
        "title": "completions_trend.phd_nra_share covers ALL research doctorates, not the STEM subset.",
        "severity": "medium",
        "scope": "metric",
        "applies_to": ["completions_trend", "phd_completions"],
        "keywords": ["completions trend", "phd_nra_share", "stem subset", "all fields"],
        "universities": None,
        "detail": (
            "In the per-university digest, phd_total / phd_nra / phd_nra_share are every "
            "CIP at award level 17. phd_stem_total and phd_stem_nra are the STEM subset "
            "and are carried separately. The site's headline nra figure is on the STEM "
            "basis, so the two will not agree."
        ),
        "consequence": "Say which basis a share is on whenever both are in play in the same answer.",
        "verified": ("scripts/build_chat_facts.py digest_university() computes phd_nra_share "
                     "from phd_nra/phd_total; scripts/enrich_university_json.py "
                     "load_ipeds_completions() keeps the STEM split in separate arrays."),
    },
    {
        "id": "ipeds_panels_are_dated_snapshots",
        "title": "Enrolment, faculty, tuition and aid panels are single-year snapshots, not current values.",
        "severity": "medium",
        "scope": "dataset",
        "applies_to": ["enrollment", "enrollment_ipeds", "faculty", "tuition",
                       "financial_aid"],
        "keywords": ["enrolment", "enrollment", "faculty", "tuition", "aid",
                     "snapshot", "out of date", "current"],
        "universities": None,
        "detail": (
            "enrollment_ipeds is IPEDS Fall 2022 (grad_enrollment_demographics_2022.csv). "
            "faculty is IPEDS Fall Staff 2022. tuition is AY2023. financial_aid is "
            "AY2022-23. Newer IPEDS releases sit unused in data/ipeds/ - Fall 2024 "
            "enrolment is on disk but the enrichment does not read it."
        ),
        "consequence": "Always attach the survey year. Never present these as 'today' or 'current'.",
        "verified": ("scripts/enrich_university_json.py load_ipeds_enrollment() line 257, "
                     "load_tuition() 433, load_financial_aid() 452, load_faculty() 475 - "
                     "each opens one fixed-year file."),
    },
    {
        "id": "usaspending_partial_coverage",
        "title": "USAspending figures exist for only 26 of the 105 universities.",
        "severity": "medium",
        "scope": "dataset",
        "applies_to": ["usaspending"],
        "keywords": ["usaspending", "federal grants", "coverage"],
        "universities": None,
        "detail": ("data/usaspending/usaspending_by_university.json holds 26 entries, drawn "
                   "from a top-recipients extract rather than a full pull."),
        "consequence": "Never rank or compare universities on this field; absence is not a low total.",
        "verified": "data/usaspending/usaspending_by_university.json has 26 keys against 105 universities.",
    },
]


# ---------------------------------------------------------------------------
# CITATION REGISTRY
#
# One entry per metric a reader might want to footnote.  Fields:
#   publication  what to name in the footnote
#   agency       who publishes it
#   file         the specific file, table or survey component in this repo
#   period       the survey / fiscal / calendar year the figure belongs to
#   retrieved    when this project pulled it (from the file on disk); "" if unknown
#   url          a stable public address, "" where none exists
#   derivation   what this project did to the source to get the published figure
#   caveats      ids into CAVEATS
#   years        (min, max) the source covers, or None
# ---------------------------------------------------------------------------
CITATIONS = {
    "nra_share": {
        "aliases": ["nra", "nra_lookup", "non-resident share", "nonresident share",
                    "ipeds_completions", "phd_completions", "completions", "doctorates"],
        "metric": "Non-resident-alien share of research doctorates",
        "publication": "IPEDS Completions survey, component C part A (awards by CIP x award level x race/ethnicity x sex)",
        "agency": "National Center for Education Statistics, U.S. Department of Education",
        "file": ("data/ipeds/c{year}_a.csv (exact release preferred, _rv revised as "
                 "fallback), aggregated into the bundled index nra_index.csv.gz "
                 "by scripts/build_nra_index.py"),
        "period": "Data years 1995-2025; the year is the end of the academic year, so 2025 is the provisional 2024-25 release",
        "retrieved": "2026-07-13 (data year 2025 added; earlier years 2026-03-08)",
        "url": "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx",
        "derivation": ("Research doctorates only: award level 17 from 2010, award level 9 "
                       "before the recoding, per-institution basis in 2008-2009. First "
                       "majors only. CIPCODE 99 institution-aggregate rows excluded. "
                       "nra_share = CNRALT / CTOTALT."),
        "caveats": ["ipeds_award_level_break", "ipeds_cip_vintages",
                    "nra_is_a_reporting_category", "awlevel17_is_not_the_sed_universe"],
        "years": (1995, 2025),
    },
    "nra_site_figure": {
        "aliases": ["site figure", "headline nra", "university nra"],
        "metric": "The headline non-resident share printed on a university page",
        "publication": "Derived by this project from IPEDS Completions",
        "agency": "This project (pinned value); underlying data NCES/IPEDS",
        "file": "pipeline/universities.json, field `nra`",
        "period": "Multi-year pooled window, not recorded in the file",
        "retrieved": "n/a - stored constant",
        "url": "",
        "derivation": ("Where it reproduces: pooled NRA share of research doctorates in "
                       "STEM CIP families 11, 14, 15, 26, 27, 30, 40, 42 over a "
                       "university-specific window (commonly 2015-2022 or 2015-2023)."),
        "caveats": ["nra_site_figure_is_pinned", "nra_is_a_reporting_category"],
        "years": None,
    },
    "completions_trend": {
        "aliases": ["phd trend", "doctorates by year", "phd_nra_share"],
        "metric": "Doctorates awarded and the non-resident subset, by year, per university",
        "publication": "IPEDS Completions survey, component C part A",
        "agency": "National Center for Education Statistics, U.S. Department of Education",
        "file": "data/ipeds/c{2010..2025}_a.csv via scripts/enrich_university_json.py load_ipeds_completions()",
        "period": "Data years 2010-2025",
        "retrieved": "2026-07-13 (data year 2025); earlier years 2026-03-08",
        "url": "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx",
        "derivation": ("Award level 17, CIPCODE 99 excluded, summed over all CIPs for "
                       "phd_total/phd_nra and over the STEM CIP families for "
                       "phd_stem_total/phd_stem_nra."),
        "caveats": ["completions_trend_is_all_fields", "ipeds_award_level_break",
                    "nra_is_a_reporting_category"],
        "years": (2010, 2025),
    },
    "enrollment_ipeds": {
        "aliases": ["enrollment", "enrolment", "grad enrollment", "graduate enrollment"],
        "metric": "Graduate enrolment by race/ethnicity and non-resident status",
        "publication": "IPEDS Fall Enrollment survey (EF component), Fall 2022",
        "agency": "National Center for Education Statistics, U.S. Department of Education",
        "file": "data/ipeds/enrollment/grad_enrollment_demographics_2022.csv (from ef2022a)",
        "period": "Fall 2022",
        "retrieved": "2026-03-30",
        "url": "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx",
        "derivation": "Graduate level rows; EFNRALT as the non-resident count.",
        "caveats": ["ipeds_panels_are_dated_snapshots", "nra_is_a_reporting_category"],
        "years": (2022, 2022),
    },
    "enrollment_gss": {
        "aliases": ["gss", "nsf gss", "graduate students survey", "foreign enrollment"],
        "metric": "Graduate enrolment by field with a foreign / domestic split",
        "publication": "Survey of Graduate Students and Postdoctorates in Science and Engineering (GSS)",
        "agency": "National Center for Science and Engineering Statistics, National Science Foundation",
        "file": "data/nsf_gss/parsed/gss_enrollment_by_institution.csv",
        "period": "Survey years 2023-2024",
        "retrieved": "2026-03-30",
        "url": "https://ncses.nsf.gov/surveys/graduate-students-postdoctorates-in-science-and-engineering/",
        "derivation": "Institution rows joined on UNITID; 'foreign' is temporary visa holders.",
        "caveats": ["nra_is_a_reporting_category"],
        "years": (2023, 2024),
    },
    "faculty": {
        "aliases": ["staff", "instructional staff", "faculty demographics"],
        "metric": "Instructional staff by race/ethnicity and non-resident status",
        "publication": "IPEDS Human Resources survey, Fall Staff component, 2022",
        "agency": "National Center for Education Statistics, U.S. Department of Education",
        "file": "data/ipeds/hr/faculty_demographics_2022.csv (from s2022_is)",
        "period": "Fall 2022",
        "retrieved": "2026-03-31",
        "url": "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx",
        "derivation": "HRNRALT as the non-resident count.",
        "caveats": ["ipeds_panels_are_dated_snapshots", "nra_is_a_reporting_category"],
        "years": (2022, 2022),
    },
    "tuition": {
        "aliases": ["fees", "graduate tuition"],
        "metric": "Graduate tuition, in-state and out-of-state",
        "publication": "IPEDS Institutional Characteristics survey, tuition component, AY2023",
        "agency": "National Center for Education Statistics, U.S. Department of Education",
        "file": "data/ipeds/ic_tuition/grad_tuition_2023.csv (from ic2023_ay)",
        "period": "Academic year 2023",
        "retrieved": "2026-03-31",
        "url": "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx",
        "derivation": "Published sticker tuition; not net of assistantship or fee waivers.",
        "caveats": ["ipeds_panels_are_dated_snapshots"],
        "years": (2023, 2023),
    },
    "financial_aid": {
        "aliases": ["aid", "grants", "graduate aid"],
        "metric": "Graduate grant aid",
        "publication": "IPEDS Student Financial Aid survey, AY2022-23",
        "agency": "National Center for Education Statistics, U.S. Department of Education",
        "file": "data/ipeds/sfa/grad_aid_2223.csv (from sfa2223)",
        "period": "Academic year 2022-23",
        "retrieved": "2026-03-31",
        "url": "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx",
        "derivation": "Graduate grant counts and dollars as reported.",
        "caveats": ["ipeds_panels_are_dated_snapshots"],
        "years": (2022, 2023),
    },
    "opt": {
        "aliases": ["stem_opt", "stem opt", "cpt", "practical training", "sevp", "sevis"],
        "metric": "Optional Practical Training, STEM-OPT and CPT participation",
        "publication": "SEVIS by the Numbers, Top 100 school campuses with OPT / STEM-OPT (annual PDFs)",
        "agency": "Student and Exchange Visitor Program, ICE, U.S. Department of Homeland Security",
        "file": ("data/h1b/*top100-prepost-opt-schools.pdf and *top100-stem-opt-schools.pdf, "
                 "parsed to data/h1b/opt_by_university.json"),
        "period": "Calendar years 2017-2024",
        "retrieved": "2026-04-02",
        "url": "https://studyinthestates.dhs.gov/sevis-by-the-numbers/sevis-by-the-numbers-data",
        "derivation": "Per-campus students-employed and authorisation counts, with SEVP's published rank.",
        "caveats": ["opt_top_100_only"],
        "years": (2017, 2024),
    },
    "h1b": {
        "aliases": ["h-1b", "petitions", "uscis", "data hub"],
        "metric": "H-1B petitions and approvals with the university as employer",
        "publication": "H-1B Employer Data Hub",
        "agency": "U.S. Citizenship and Immigration Services, Department of Homeland Security",
        "file": "data/h1b/h1b_datahub_fy{2010..2026}.csv, resolved to campuses via pipeline/entity_map.json",
        "period": "Federal fiscal years 2010-2026",
        "retrieved": "2026-04-03",
        "url": "https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub",
        "derivation": "Initial and continuing approvals and denials summed per matched employer name.",
        "caveats": ["uscis_h1b_is_employer_level"],
        "years": (2010, 2026),
    },
    "lca": {
        "aliases": ["labor condition application", "labour condition application",
                    "dol lca", "wages", "job titles", "oflc"],
        "metric": "Labor Condition Applications certified with the university as employer",
        "publication": "LCA Disclosure Data (quarterly and annual disclosure files)",
        "agency": "Office of Foreign Labor Certification, U.S. Department of Labor",
        "file": ("data/h1b/lca/*.xlsx (FY2013 through FY2026 Q3; FY2026 Q1 is superseded "
                 "by Q3 and held in lca/superseded/), parsed to "
                 "data/h1b/lca_by_university.json"),
        "period": ("Calendar-year buckets from DECISION_DATE. 2014 holds one quarter "
                   "(October to December 2014) and the FY2013 file has no DECISION_DATE "
                   "column at all, so the first complete year is 2015. The last complete "
                   "year is 2025; 2026 currently runs to June only."),
        "retrieved": "2026-04-02 (FY2013-FY2025 releases); 2026-08-07 (FY2026 Q3)",
        "url": "https://www.dol.gov/agencies/eta/foreign-labor/performance",
        "derivation": ("Certifications counted per matched employer name, bucketed by "
                       "the CALENDAR year of DECISION_DATE. No DOL layout in these 32 "
                       "files carries a fiscal-year column."),
        "caveats": ["lca_year_buckets_are_calendar", "mit_lca_total_is_contaminated",
                    "uscis_h1b_is_employer_level"],
        "years": (2014, 2026),
    },
    "perm": {
        "aliases": ["green card sponsorship", "labor certification", "permanent"],
        "metric": "PERM permanent labour certifications",
        "publication": "PERM Disclosure Data",
        "agency": "Office of Foreign Labor Certification, U.S. Department of Labor",
        "file": "data/h1b/perm_*.xlsx, parsed to data/h1b/perm_by_university.json (71 universities matched)",
        "period": "Through FY2025 Q1",
        "retrieved": "2026-04-02",
        "url": "https://www.dol.gov/agencies/eta/foreign-labor/performance",
        "derivation": "Certified / denied counts per matched employer name.",
        "caveats": ["uscis_h1b_is_employer_level"],
        "years": None,
    },
    "funding": {
        "aliases": ["herd", "r&d", "rd", "research expenditure", "research spending"],
        "metric": "University R&D expenditures",
        "publication": "Higher Education Research and Development Survey (HERD), FY2024, tables 13 and 14",
        "agency": "National Center for Science and Engineering Statistics, National Science Foundation",
        "file": "data/herd/herd_fy2024_table13.xlsx, herd_fy2024_table14.xlsx -> data/herd/funding_by_university.json",
        "period": "Fiscal year 2024 (series back to 2010)",
        "retrieved": "2026-03-24",
        "url": "https://ncses.nsf.gov/surveys/higher-education-research-development/",
        "derivation": "Institution totals by source of funds and by field, in thousands of dollars as published.",
        "caveats": [],
        "years": (2010, 2024),
    },
    "federal_support": {
        "aliases": ["ncses federal support", "federal obligations", "nsf25339",
                    "s&e support", "fellowships"],
        "metric": "Federal obligations to the institution for science and engineering",
        "publication": "Survey of Federal Science and Engineering Support to Universities, Colleges and Nonprofit Institutions, NSF 25-339, Table 17",
        "agency": "National Center for Science and Engineering Statistics, National Science Foundation",
        "file": "data/federal_support/nsf25339-tab017.xlsx -> data/federal_support/federal_support_by_university.json",
        "period": "Fiscal year 2023",
        "retrieved": "2026-08-18",
        "url": "https://ncses.nsf.gov/pubs/nsf25339",
        "derivation": ("All-agency obligations, R&D, and fellowships/traineeships/training, "
                       "converted from the published thousands to dollars. 101 of 105 "
                       "universities matched; some matched to a SYSTEM OFFICE row rather "
                       "than a campus row."),
        "caveats": ["lsu_federal_support_is_system_office"],
        "years": (2023, 2023),
    },
    "nsf_awards": {
        "aliases": ["nsf grants", "award search"],
        "metric": "NSF awards and obligated dollars",
        "publication": "NSF Award Search",
        "agency": "National Science Foundation",
        "file": "data/state_funding/nsf_awards/nsf_by_university.json via scripts/fetch_nsf_awards.py",
        "period": "Award years 2020-2025",
        "retrieved": "2026-08-18",
        "url": "https://api.nsf.gov/services/v1/awards.json",
        "derivation": "Awards matched on institution name; obligated amounts summed per year.",
        "caveats": [],
        "years": (2020, 2025),
    },
    "nih": {
        "aliases": ["nih grants", "reporter", "nih reporter"],
        "metric": "NIH grants and dollars",
        "publication": "NIH RePORTER",
        "agency": "National Institutes of Health",
        "file": "data/state_funding/nih_reporter/nih_by_university.json via data/state_funding/nih_reporter/fetch_nih.py",
        "period": "Fiscal years 2020-2025",
        "retrieved": "2026-08-18",
        "url": "https://reporter.nih.gov/",
        "derivation": "Grants matched on organisation-name variants; total dollars summed per fiscal year.",
        "caveats": [],
        "years": (2020, 2025),
    },
    "state_funding": {
        "aliases": ["sheeo", "shef", "appropriations", "state support"],
        "metric": "State higher-education appropriations",
        "publication": "State Higher Education Finance (SHEF), FY2025 report data",
        "agency": "State Higher Education Executive Officers Association (SHEEO)",
        "file": "data/state_funding/sheeo/SHEEO_SHEF_FY25_Report_Data.xlsx -> sheeo_by_university.json",
        "period": "Fiscal years 2010-2025; real dollars rebased to FY2025 via HECA",
        "retrieved": "2026-08-18",
        "url": "https://shef.sheeo.org/data-downloads/",
        "derivation": "State-level series joined to each public university on its IPEDS state.",
        "caveats": ["sheeo_state_funding_is_a_state_proxy"],
        "years": (2010, 2025),
    },
    "usaspending": {
        "aliases": ["federal grants", "treasury"],
        "metric": "Federal grant dollars awarded to the institution",
        "publication": "USAspending.gov award data",
        "agency": "U.S. Department of the Treasury",
        "file": "data/usaspending/usaspending_by_university.json (26 universities)",
        "period": "Not year-partitioned in the stored extract",
        "retrieved": "2026-04-08",
        "url": "https://www.usaspending.gov/",
        "derivation": "Grant totals by recipient name.",
        "caveats": ["usaspending_partial_coverage"],
        "years": None,
    },
    "dissertation_records": {
        "aliases": ["records", "theses", "dissertations", "harvest", "oai", "corpus"],
        "metric": "Thesis and dissertation records harvested from institutional repositories",
        "publication": "Institutional repository metadata, harvested over OAI-PMH (oai_dc, oai_etdms, dim, mods, untl, native) and two REST APIs",
        "agency": "The 105 universities themselves",
        "file": "data/western_us_dissertations/{key}_etds.csv -> data/processed/{stem,nonstem}/{key}.json",
        "period": "Varies by university; call coverage_for for the record-year range actually held",
        "retrieved": "2026-08-18 (latest process run)",
        "url": "",
        "derivation": ("Degree type inferred by a nine-step chain; department mapped to a "
                       "taxonomy; author name classified for name origin; deduplicated on "
                       "(name, year, department, title)."),
        "caveats": ["labelling_rate_uncertainty", "harvest_year_is_often_a_deposit_date",
                    "name_origin_is_not_visa_status"],
        "years": None,
    },
    "foreign_name_pct": {
        "aliases": ["name origin", "name_origins", "name classification", "surname",
                    "chinese names", "departments"],
        "metric": "Share of a department's dissertation authors whose surname is not American-typical",
        "publication": "Derived by this project from harvested author names",
        "agency": "This project",
        "file": "scripts/name_classifier.py, applied in pipeline/step2_process.py",
        "period": "Covers the record years held for that university; see coverage_for",
        "retrieved": "2026-08-18 (latest process run)",
        "url": "",
        "derivation": ("Surname matched against curated origin lists, with the given name "
                       "used only to resolve ambiguous surnames. Output is a name-origin "
                       "category and a confidence."),
        "caveats": ["name_origin_is_not_visa_status"],
        "years": None,
    },
    "visa_issuances": {
        "aliases": ["f1", "j1", "h1b visas", "visa statistics", "state department"],
        "metric": "Non-immigrant visa issuances by class",
        "publication": "Nonimmigrant Visa Statistics (annual issuances by classification)",
        "agency": "Bureau of Consular Affairs, U.S. Department of State",
        "file": "Series carried in site/stem.html national panel -> chat_data/national_series.json",
        "period": "Fiscal years 2007-2024",
        "retrieved": "",
        "url": "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-statistics/nonimmigrant-visa-statistics.html",
        "derivation": "Issuances, not admissions and not people: one person can be issued several visas over time.",
        "caveats": [],
        "years": (2007, 2024),
    },
    "eb_by_country": {
        "aliases": ["green cards", "employment based", "eb"],
        "metric": "Employment-based immigrant visas against US doctorates, by country",
        "publication": "Department of State FY2024 immigrant visa statistics with NSF Survey of Earned Doctorates",
        "agency": "U.S. Department of State; NCSES, National Science Foundation",
        "file": "Series carried in site/pipeline.html -> chat_data/national_series.json",
        "period": "Fiscal year 2024",
        "retrieved": "",
        "url": "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-statistics/annual-reports.html",
        "derivation": "Two independently published series put side by side; they are not a cohort and do not follow the same people.",
        "caveats": ["awlevel17_is_not_the_sed_universe"],
        "years": (2024, 2024),
    },
    "sed": {
        "aliases": ["survey of earned doctorates", "ncses sed", "stay rate"],
        "metric": "Research doctorates by field, citizenship and country",
        "publication": "Survey of Earned Doctorates, published tables",
        "agency": "National Center for Science and Engineering Statistics, National Science Foundation",
        "file": "data/nsf_sed/parsed/table_*.csv",
        "period": "1979-2024 depending on table",
        "retrieved": "2026-03-30",
        "url": "https://ncses.nsf.gov/surveys/earned-doctorates/",
        "derivation": "Published tables parsed as released; small cells are suppressed at source.",
        "caveats": ["awlevel17_is_not_the_sed_universe", "nra_is_a_reporting_category"],
        "years": (1979, 2024),
    },
    "overstay": {
        "aliases": ["overstay rate", "entry exit", "cbp"],
        "metric": "Suspected in-country overstay rates by country",
        "publication": "Entry/Exit Overstay Report",
        "agency": "U.S. Customs and Border Protection, Department of Homeland Security",
        "file": "data/vwp/dhs_overstay_fy{2023,2024,2025}.pdf",
        "period": ("dhs_overstay_fy2023.pdf carries FY2023 data and dhs_overstay_fy2024.pdf "
                   "carries FY2024 data - filename equals data year for both. "
                   "dhs_overstay_fy2025.pdf is cover-titled FY2025 but carries FY2024 data. "
                   "The latest available data year is FY2024."),
        "retrieved": "2026-04-06",
        "url": "https://www.dhs.gov/publication/entryexit-overstay-report",
        "derivation": "Rates as published; expected departures is the denominator.",
        "caveats": ["overstay_report_off_by_one"],
        "years": (2022, 2024),
    },
    "sevis_active_students": {
        "aliases": ["active students", "sevis mapping", "international students"],
        "metric": "Active F/M student records by country and state",
        "publication": "SEVIS by the Numbers data / SEVIS Data Mapping Tool monthly extracts",
        "agency": "Student and Exchange Visitor Program, ICE, U.S. Department of Homeland Security",
        "file": "data/sevp/sevis_data_mapping_{month}{year}.csv",
        "period": "Monthly snapshots, January 2024 to March 2026",
        "retrieved": "2026-03-31",
        "url": "https://studyinthestates.dhs.gov/sevis-data-mapping-tool",
        "derivation": "Point-in-time active record counts, not flows and not enrolments.",
        "caveats": [],
        "years": (2024, 2026),
    },
}


# ---------------------------------------------------------------------------
# lookup helpers
# ---------------------------------------------------------------------------
_CAVEAT_BY_ID = {c["id"]: c for c in CAVEATS}


def _norm(value, limit=60):
    """Lower-cased, control-stripped, length-capped.  Input is user text."""
    return ds.clean_text(value, limit).lower().strip()


def _uni_key(topic):
    """Resolve a topic to a site university key, or None."""
    t = _norm(topic, 40).replace(" ", "_").replace("-", "_")
    unis = ds.universities()
    if t in unis:
        return t
    if t in _COVERAGE_ROWS:
        return t
    for key, u in unis.items():
        if _norm(u.get("name", ""), 80) == _norm(topic, 80):
            return key
    return None


def _cite_key(metric):
    """Resolve a metric name or alias to a CITATIONS key, or None."""
    m = _norm(metric, 60)
    if m in CITATIONS:
        return m
    m2 = m.replace(" ", "_").replace("-", "_")
    if m2 in CITATIONS:
        return m2
    for key, rec in CITATIONS.items():
        if m in rec["aliases"] or m2 in rec["aliases"]:
            return key
    # last resort: substring against key, aliases and the metric label
    for key, rec in CITATIONS.items():
        hay = " ".join([key] + rec["aliases"] + [rec["metric"].lower()])
        if m and m in hay:
            return key
    return None


def _caveat_out(c):
    out = {"id": c["id"], "severity": c["severity"], "title": c["title"],
           "detail": c["detail"], "consequence": c["consequence"],
           "verified_against": c["verified"]}
    if c.get("correction"):
        out["correction"] = c["correction"]
    if c.get("operational_note"):
        out["operational_note"] = c["operational_note"]
    if c.get("universities"):
        out["specific_to"] = c["universities"]
    return out


def _match_caveats(topic):
    """Return (matching caveats, how the match was made)."""
    t = _norm(topic, 60)
    if not t:
        return [], "empty"

    key = _uni_key(topic)
    if key:
        row = _COVERAGE_ROWS.get(key)
        flags = row[6] if row else "0" * len(_FLAG_ORDER)
        held = {_FLAG_ORDER[i] for i, ch in enumerate(flags) if ch == "1"}
        hits = []
        for c in CAVEATS:
            if c.get("universities") and key in c["universities"]:
                hits.append(c)
            elif c["scope"] == "always" and not c.get("universities"):
                hits.append(c)
            elif (c["scope"] == "dataset" and not c.get("universities")
                    and held & set(c["applies_to"])):
                hits.append(c)
            elif c["scope"] == "metric" and not c.get("universities"):
                hits.append(c)
        # Caveats naming this university first, then by severity: a truncated
        # list must not drop the entry that is specifically about this campus.
        order = {"high": 0, "medium": 1}
        hits.sort(key=lambda c: (0 if c.get("universities") else 1,
                                 order.get(c["severity"], 2), c["id"]))
        return hits, f"university:{key}"

    t2 = t.replace(" ", "_").replace("-", "_")
    hits = []
    for c in CAVEATS:
        hay = [c["id"]] + list(c["applies_to"]) + list(c["keywords"])
        if t in hay or t2 in hay:
            hits.append(c)
            continue
        blob = " ".join(hay + [c["title"].lower()])
        if len(t) >= 3 and t in blob:
            hits.append(c)
    order = {"high": 0, "medium": 1}
    hits.sort(key=lambda c: (order.get(c["severity"], 2), c["id"]))
    return hits, "keyword"


# ---------------------------------------------------------------------------
# SCHEMAS
# ---------------------------------------------------------------------------
SCHEMAS = [
    _fn(
        "coverage_for",
        "What this project holds for one university and, more usefully, what it does "
        "NOT, so a figure can be quoted with its completeness attached. Returns the "
        "dissertation record count, the PhD / master's / unlabelled split and the "
        "labelling rate, plus a held / not-held list across H-1B, OPT, LCA, PERM, "
        "enrolment, funding and department links, each absence with its reason. Call "
        "this before quoting a university-level count, before ranking universities on a "
        "federal source, and whenever a reader asks how complete the data is. Two "
        "things it will tell you that are easy to get wrong: a missing OPT figure means "
        "SEVP's Top-100 publication did not cover that campus, not that no students "
        "were on OPT; and a low labelling rate means the PhD / master's split is "
        "uncertain, not that records are missing.",
        {"university": {"type": "string",
                        "description": "University key, e.g. mit, njit, iowa_state. "
                                       "Use list_universities to find one."}},
        ["university"],
    ),
    _fn(
        "caveats_for",
        "The registry of known, verified limitations, looked up by metric, dataset or "
        "university. Every entry names the code or data it was checked against, and a "
        "few carry a `correction` where a claim this project has written down elsewhere "
        "turned out not to hold. Call this before presenting a comparison across years, "
        "a federal-source figure, a name-origin percentage, or any number a sceptical "
        "reader would push back on, and put the relevant caveat in a show_notice rather "
        "than burying it. Topics that work: a metric (nra_share, completions_trend, "
        "foreign_name_pct, opt, h1b, lca, state_funding), a dataset (ipeds_completions, "
        "sevp, dol), a university key, or a phrase (award level, cip, name "
        "classification, labelling).",
        {"topic": {"type": "string",
                   "description": "A metric name, dataset name, university key or phrase."},
         "severity": {"type": "string", "enum": ["high", "medium", "all"],
                      "description": "Filter by severity. Default all. 'high' means the "
                                     "caveat can invalidate the figure or the comparison."},
         "limit": {"type": "integer", "description": "1-12, default 6."}},
        ["topic"],
    ),
    _fn(
        "cite",
        "A citation the reader can paste into a footnote: the publishing agency, the "
        "specific file or survey table, the survey / fiscal / calendar year, the "
        "retrieval date where this project recorded one, and a stable URL where one "
        "exists. Use it whenever someone asks where a number comes from, whether it can "
        "be checked, or how to find the source themselves, and pair it with show_link "
        "when the source has a public URL. It also returns the ids of the caveats that "
        "attach to that metric, which you can expand with caveats_for.",
        {"metric": {"type": "string",
                    "description": "What is being cited: nra_share, completions_trend, "
                                   "enrollment_ipeds, faculty, tuition, opt, h1b, lca, "
                                   "perm, funding, federal_support, nsf_awards, nih, "
                                   "state_funding, dissertation_records, "
                                   "foreign_name_pct, visa_issuances, sed, overstay. "
                                   "Aliases and near-misses resolve."},
         "university": {"type": "string",
                        "description": "Optional university key, to pin the citation to "
                                       "one institution and add its UNITID."},
         "year": {"type": "integer",
                  "description": "Optional survey / fiscal year, to name it in the "
                                 "citation and warn if it is outside coverage."}},
        ["metric"],
    ),
]


# ---------------------------------------------------------------------------
# IMPLEMENTATIONS
# ---------------------------------------------------------------------------
def _t_coverage_for(args):
    raw = args.get("university", "")
    key = _uni_key(raw)
    if not key:
        probe = _norm(raw, 40).replace(" ", "_")
        near = [k for k in _COVERAGE_ROWS if probe and (probe in k or k in probe)][:8]
        return {"error": f"No university with key '{ds.clean_text(raw, 40)}'.",
                "did_you_mean": near,
                "hint": "Call list_universities to find the right key."}

    row = _COVERAGE_ROWS[key]
    total, phd, ms, unlab, label_pct, nonstem, flags, h1b_years, opt_years, lca_total = row
    digest = ds.universities().get(key, {})

    held, not_held = [], []
    for i, flag in enumerate(_FLAG_ORDER):
        item = {"source": flag, "holds": _FLAG_LABEL[flag]}
        if flags[i] == "1":
            if flag == "h1b" and h1b_years:
                item["years_present"] = h1b_years
            if flag == "opt" and opt_years:
                item["years_present"] = opt_years
            if flag == "lca" and lca_total:
                item["certifications"] = lca_total
            held.append(item)
        else:
            item["why_absent"] = _FLAG_ABSENT_REASON[flag]
            not_held.append(item)

    labelled = phd + ms
    labelling = {
        "labelled": labelled,
        "unlabelled": unlab,
        "label_pct": label_pct,
        "reading": (
            f"{unlab:,} of {total:,} STEM records carry no degree label. Those records "
            f"are present and counted in the total; only their PhD/master's split is "
            f"unknown. Do NOT compute a PhD share as {phd:,}/{total:,}."
            if unlab else
            "Every STEM record carries a degree label."
        ),
    }
    if label_pct < 60:
        labelling["warning"] = (
            f"label_pct is {label_pct}%. Quote the {total:,} total confidently; quote "
            f"the {phd:,} PhD figure only as 'at least', with the labelling rate stated.")

    notes = []
    if "1" not in flags:
        notes.append("EVERY federal source is absent for this university, which almost "
                     "always means the enrichment step has not yet been run for it "
                     "rather than that seven separate matches failed. Treat the "
                     "per-source reasons below as provisional and quote only the "
                     "dissertation record counts.")
    if flags[_FLAG_ORDER.index("opt")] == "0":
        notes.append("No OPT figure: SEVP publishes only a Top-100 school list, and this "
                     "campus is not on it. 59 of the 105 universities here have any OPT "
                     "data. Absence is a gap in the PUBLICATION, not in the population.")
    else:
        notes.append(f"OPT covers {opt_years} year(s). SEVP's source is a Top-100 list, so "
                     f"a campus can drop out of a year without its students doing so; "
                     f"only 59 of the 105 universities here appear at all.")
    if label_pct < 90:
        notes.append(f"Degree labelling is {label_pct}% against a corpus rate of 88.8%.")
    if digest.get("record_years"):
        lo, hi = digest["record_years"]
        notes.append(f"record_years {lo}-{hi} is the range of the STORED year, which for "
                     f"most universities is the repository's ingest timestamp rather than "
                     f"the award date (caveats_for 'harvest_year_is_often_a_deposit_date'). "
                     f"Use it as the harvest window, not as a graduation-year range.")
    for c in CAVEATS:
        if c.get("universities") and key in c["universities"]:
            notes.append(f"{c['title']} (caveats_for '{c['id']}')")

    out = {
        "source": (f"pipeline/manifest.json snapshot, process run "
                   f"{COVERAGE_SNAPSHOT['manifest_last_run']}"),
        "university": {"key": key,
                       "name": digest.get("name", key),
                       "unitid": digest.get("unitid"),
                       "url": digest.get("url", f"/universities/{key}.html")},
        "records": {"stem_total": total, "phd": phd, "ms": ms,
                    "unlabelled": unlab, "nonstem_total": nonstem,
                    "record_years": digest.get("record_years")},
        "labelling": labelling,
        "held": held,
        "not_held": not_held,
        "coverage_notes": notes,
        "corpus_context": {
            "universities": 105,
            "stem_records": 369319,
            "corpus_label_pct": 88.8,
            "universities_with_opt": 59,
            "universities_with_h1b": 101,
            "universities_with_lca": 100,
            "universities_with_perm": 71,
            "universities_with_funding": 80,
        },
        "caveat_ids": sorted({c["id"] for c in _match_caveats(key)[0]}),
        "scope": ("Record counts are the STEM track of this project's harvested "
                  "dissertation corpus, not an IPEDS degree count and not an enrolment "
                  "count. The held/not-held flags describe whether a federal source "
                  "matched this campus, not whether the underlying activity happened."),
        "_untrusted": UNTRUSTED,
    }
    return out


def _t_caveats_for(args):
    topic = args.get("topic", "")
    if not _norm(topic, 60):
        return {"error": "caveats_for requires a topic.",
                "available_topics": sorted(_CAVEAT_BY_ID),
                "hint": "Try a metric (nra_share, opt, foreign_name_pct), a dataset "
                        "(ipeds_completions), or a university key."}

    hits, how = _match_caveats(topic)
    sev = args.get("severity") or "all"
    if sev in ("high", "medium"):
        hits = [c for c in hits if c["severity"] == sev]
    limit = _clamp(args.get("limit", 6), 1, 12, 6)
    shown = hits[:limit]

    out = {
        "source": "Provenance caveat registry (cloud/chat/tools_provenance.py)",
        "topic": ds.clean_text(topic, 60),
        "matched_by": how,
        "matched": len(hits),
        "returned": len(shown),
        "caveats": [_caveat_out(c) for c in shown],
        "scope": ("Every entry was checked against the code or data named in "
                  "`verified_against`. Entries a project document asserted but the data "
                  "did not support were dropped; where a written claim was wrong in "
                  "part, the entry carries a `correction` rather than repeating it."),
        "usage": ("Put a high-severity caveat in front of the reader with show_notice "
                  "rather than in a trailing sentence."),
    }
    if not hits:
        out["note"] = ("Nothing registered for that topic. That means no verified "
                       "limitation is on file - not that the figure is unqualified. "
                       "Registered ids: " + ", ".join(sorted(_CAVEAT_BY_ID)))
    return out


def _t_cite(args):
    metric = args.get("metric", "")
    key = _cite_key(metric)
    if not key:
        return {"error": f"No citation registered for '{ds.clean_text(metric, 60)}'.",
                "available": sorted(CITATIONS),
                "hint": "Pass one of the listed metric names, or an alias of one."}

    rec = CITATIONS[key]
    parts = [rec["agency"], rec["publication"]]

    year = args.get("year")
    year_note = None
    if year is not None:
        try:
            asked = int(year)
        except (TypeError, ValueError):
            asked = None
        year = _clamp(year, 1900, 2100, 0)
        if asked is not None and rec.get("years"):
            lo, hi = rec["years"]
            if not lo <= asked <= hi:
                year_note = (f"{asked} is outside the coverage of this source "
                             f"({lo}-{hi}). Do not cite it for that year.")
        elif asked is None:
            year = 0

    uni = None
    ukey = _uni_key(args.get("university", "")) if args.get("university") else None
    if args.get("university") and not ukey:
        uni = {"error": f"Unknown university key "
                        f"'{ds.clean_text(args.get('university'), 40)}'; citation "
                        f"returned without an institution."}
    elif ukey:
        d = ds.universities().get(ukey, {})
        uni = {"key": ukey, "name": d.get("name", ukey), "unitid": d.get("unitid"),
               "page": d.get("url", f"/universities/{ukey}.html")}
        if d.get("unitid"):
            parts.append(f"{d.get('name', ukey)} (IPEDS UNITID {d['unitid']})")
        else:
            parts.append(d.get("name", ukey))

    if year and not year_note:
        parts.append(f"Data year {year} (source coverage: {rec['period']})")
    else:
        parts.append(rec["period"])
    parts.append(f"File: {rec['file']}")
    if rec["retrieved"]:
        parts.append(f"Retrieved {rec['retrieved']}")
    if rec["url"]:
        parts.append(rec["url"])
    citation = ". ".join(p.rstrip(".") for p in parts if p) + "."

    out = {
        "source": "Provenance citation registry (cloud/chat/tools_provenance.py)",
        "metric": rec["metric"],
        "metric_key": key,
        "citation": citation,
        "publication": rec["publication"],
        "agency": rec["agency"],
        "file": rec["file"],
        "period": rec["period"],
        "retrieved": rec["retrieved"] or "not recorded",
        "url": rec["url"] or "no stable public URL for this file",
        "derivation": rec["derivation"],
        "caveat_ids": rec["caveats"],
        "coverage_years": list(rec["years"]) if rec.get("years") else None,
        "scope": ("The citation names the source this project actually read, and the "
                  "derivation says what was done to it. Where those differ from the "
                  "headline figure on the site, `caveat_ids` says so; expand them with "
                  "caveats_for."),
    }
    if uni:
        out["university"] = uni
    if year_note:
        out["warning"] = year_note
    elif year:
        out["year"] = year
    if rec["url"]:
        label = rec["publication"]
        if len(label) > 58:
            label = label[:58].rsplit(" ", 1)[0].rstrip(" ,(") + "\u2026"
        out["show_link_hint"] = {"kind": "external", "url": rec["url"], "label": label}
    return out


IMPL = {
    "coverage_for": _t_coverage_for,
    "caveats_for": _t_caveats_for,
    "cite": _t_cite,
}


def run(name, args):
    """Convenience runner mirroring tools.run_data_tool: errors returned, not raised."""
    fn = IMPL.get(name)
    if not fn:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(args if isinstance(args, dict) else {})
    except Exception as exc:                      # noqa: BLE001 - surfaced to the model
        return {"error": f"{name} failed: {type(exc).__name__}: {exc}"}
