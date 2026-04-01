#!/usr/bin/env python3
"""
Generic OAI-PMH ETD harvester for DSpace and bepress repositories.

Supports harvesting dissertations/theses from multiple Western US universities.
Each repository is configured with its OAI endpoint, ETD set(s), and field mappings.

Usage:
    python scripts/scrape_oai_etds.py --repo uarizona          # single repo
    python scripts/scrape_oai_etds.py --repo unm               # UNM (bepress, multiple sets)
    python scripts/scrape_oai_etds.py --repo mines              # CO School of Mines
    python scripts/scrape_oai_etds.py --repo montana_state      # Montana State
    python scripts/scrape_oai_etds.py --repo umt                # U Montana
    python scripts/scrape_oai_etds.py --repo nmtech             # NM Tech
    python scripts/scrape_oai_etds.py --list                    # list available repos
    python scripts/scrape_oai_etds.py --repo uarizona --resume  # resume interrupted harvest
"""

import argparse
import csv
import json
import logging
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "western_us_dissertations"

# OAI-PMH XML namespaces
NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}

REQUEST_DELAY = 1.0
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": "Western-US-PhD-Research/1.0 (academic research)",
}

CSV_FIELDS = [
    "repo", "university", "identifier", "title", "creator",
    "contributor", "date", "subject", "description", "type",
    "format", "language", "source", "relation",
    "oai_set", "url",
]

# ──────────────────────────────────────────────────────────────
# Repository configurations
# ──────────────────────────────────────────────────────────────
REPOS = {
    "uarizona": {
        "name": "University of Arizona",
        "state": "AZ",
        "oai_base": "https://repository.arizona.edu/oai/request",
        "platform": "dspace5",
        "sets": ["com_10150_129649"],  # UA Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "unm": {
        "name": "University of New Mexico",
        "state": "NM",
        "oai_base": "https://digitalrepository.unm.edu/do/oai/",
        "platform": "bepress",
        # Use the umbrella set plus all department ETD sets
        "sets": ["publication:etds"],
        "metadata_prefix": "oai_dc",
    },
    "mines": {
        "name": "Colorado School of Mines",
        "state": "CO",
        "oai_base": "https://repository.mines.edu/oai/request",
        "platform": "dspace",
        "sets": ["com_11124_7"],  # Theses & Dissertations
        "metadata_prefix": "oai_dc",
    },
    "montana_state": {
        "name": "Montana State University",
        "state": "MT",
        "oai_base": "https://scholarworks.montana.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_1_732"],  # Theses and Dissertations at MSU
        "metadata_prefix": "oai_dc",
    },
    "umt": {
        "name": "University of Montana",
        "state": "MT",
        "oai_base": "https://scholarworks.umt.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],  # Graduate Student Theses, Dissertations & Professional Papers
        "metadata_prefix": "oai_dc",
    },
    "nmtech": {
        "name": "New Mexico Institute of Mining and Technology",
        "state": "NM",
        "oai_base": "https://nmt.edu/oai",  # needs verification
        "platform": "unknown",
        "sets": [],
        "metadata_prefix": "oai_dc",
    },
    "nmsu": {
        "name": "New Mexico State University",
        "state": "NM",
        "oai_base": "https://scholarworks.nmsu.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertations"],  # needs verification — DNS down
        "metadata_prefix": "oai_dc",
    },
    "boise_state": {
        "name": "Boise State University",
        "state": "ID",
        "oai_base": "https://scholarworks.boisestate.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:td"],  # Boise State Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "unlv": {
        "name": "University of Nevada, Las Vegas",
        "state": "NV",
        "oai_base": "https://digitalscholarship.unlv.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:thesesdissertations"],  # main ETD set
        "metadata_prefix": "oai_dc",
    },
    "byu": {
        "name": "Brigham Young University",
        "state": "UT",
        "oai_base": "https://scholarsarchive.byu.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],  # main ETD umbrella set
        "metadata_prefix": "oai_dc",
    },
    "utah_state": {
        "name": "Utah State University",
        "state": "UT",
        "oai_base": "https://digitalcommons.usu.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],
        "metadata_prefix": "oai_dc",
    },
    "udenver": {
        "name": "University of Denver",
        "state": "CO",
        "oai_base": "https://digitalcommons.du.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],  # Electronic Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "northern_colorado": {
        "name": "University of Northern Colorado",
        "state": "CO",
        "oai_base": "https://digscholarship.unco.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertations"],
        "metadata_prefix": "oai_dc",
    },
    "nau": {
        "name": "Northern Arizona University",
        "state": "AZ",
        "oai_base": "https://openknowledge.nau.edu/cgi/oai2",
        "platform": "eprints",
        "sets": [],  # will harvest all, filter by type
        "metadata_prefix": "oai_dc",
    },
    "oregon_state": {
        "name": "Oregon State University",
        "state": "OR",
        "oai_base": "https://ir.library.oregonstate.edu/catalog/oai",
        "platform": "hyrax",
        "sets": ["2b88qc16g"],  # Graduate Thesis or Dissertation
        "metadata_prefix": "oai_dc",
    },
    "uwyoming": {
        "name": "University of Wyoming",
        "state": "WY",
        "oai_base": "https://wyoscholar.uwyo.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_internal_109"],  # Graduate Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "cu_boulder": {
        "name": "University of Colorado Boulder",
        "state": "CO",
        "oai_base": "https://scholar.colorado.edu/catalog/oai",
        "platform": "hyrax",
        "sets": [],  # harvest all, filter by type
        "metadata_prefix": "oai_dc",
    },
    # ──── Great Plains & Upper Midwest ────
    "iowa_state": {
        "name": "Iowa State University",
        "state": "IA",
        "oai_base": "https://dr.lib.iastate.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["col_20.500.12876_5"],  # Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "washu": {
        "name": "Washington University in St Louis",
        "state": "MO",
        "oai_base": "https://openscholarship.wustl.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],  # All Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "missouri_st": {
        "name": "Missouri University of Science and Technology",
        "state": "MO",
        "oai_base": "https://scholarsmine.mst.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:doctoral_dissertations"],
        "metadata_prefix": "oai_dc",
    },
    "umissouri": {
        "name": "University of Missouri-Columbia",
        "state": "MO",
        "oai_base": "https://mospace.umsystem.edu/server/oai/request",
        "platform": "dspace",
        "sets": [  # All 50 dissertation sets (MU + UMKC)
            "com_10355_14639", "com_10355_14641", "com_10355_14642",  # 1890s-1910s MU
            "com_10355_79521", "com_10355_99261", "com_10355_66000",  # 1920s-1940s MU
            "com_10355_67570", "com_10355_70549", "com_10355_70185",  # 1950s-1970s MU
            "com_10355_44061", "com_10355_43684",                     # 1980s-1990s MU
            "com_10355_43483", "com_10355_98862", "com_10355_3992",   # 2001-2004 MU
            "com_10355_4054", "com_10355_4058", "com_10355_4073",     # 2005-2007 MU
            "com_10355_4193", "com_10355_4202", "com_10355_8038",     # 2008-2010 MU
            "com_10355_11257", "com_10355_14971", "com_10355_37574",  # 2011-2013 MU
            "com_10355_44141", "com_10355_46814", "com_10355_55724",  # 2014-2016 MU
            "com_10355_61873", "com_10355_66033", "com_10355_69918",  # 2017-2019 MU
            "com_10355_77941", "com_10355_85701", "com_10355_91543",  # 2020-2022 MU
            "com_10355_96061", "com_10355_104642",                    # 2023-2024 MU
            "com_10355_11739",                                        # 1929-2009 UMKC
            "com_10355_8988", "com_10355_10599", "com_10355_13615",   # 2010-2012 UMKC
            "com_10355_33226", "com_10355_43255", "com_10355_44868",  # 2013-2015 UMKC
            "com_10355_48314", "com_10355_60014", "com_10355_63230",  # 2016-2018 UMKC
            "com_10355_67999", "com_10355_72981", "com_10355_81181",  # 2019-2021 UMKC
            "com_10355_89681", "com_10355_94821", "com_10355_98126",  # 2022-2024 UMKC
        ],
        "metadata_prefix": "oai_dc",
    },
    "ukansas": {
        "name": "University of Kansas",
        "state": "KS",
        "oai_base": "https://kuscholarworks.ku.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_1808_1260"],  # Dissertations and Theses
        "metadata_prefix": "oai_dc",
    },
    "kstate": {
        "name": "Kansas State University",
        "state": "KS",
        "oai_base": "https://krex.k-state.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_2097_1"],  # Electronic Theses, Dissertations, and Reports
        "metadata_prefix": "oai_dc",
    },
    "shareok": {
        "name": "University of Oklahoma / Oklahoma State (ShareOK)",
        "state": "OK",
        "oai_base": "https://shareok.org/server/oai/request",
        "platform": "dspace",
        "sets": ["col_11244_340716"],  # PQETD collection
        "metadata_prefix": "oai_dc",
    },
    "unl": {
        "name": "University of Nebraska-Lincoln",
        "state": "NE",
        "oai_base": "https://digitalcommons.unl.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertations"],  # ETD Collection
        "metadata_prefix": "oai_dc",
    },
    "und": {
        "name": "University of North Dakota",
        "state": "ND",
        "oai_base": "https://commons.und.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etds"],  # Theses, Dissertations, and Senior Projects
        "metadata_prefix": "oai_dc",
    },
    "ndsu": {
        "name": "North Dakota State University",
        "state": "ND",
        "oai_base": "",  # OAI 404 — needs investigation
        "platform": "unknown",
        "sets": [],
        "metadata_prefix": "oai_dc",
    },
    "sdsu": {
        "name": "South Dakota State University",
        "state": "SD",
        "oai_base": "https://openprairie.sdstate.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],  # Electronic Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "usd": {
        "name": "University of South Dakota",
        "state": "SD",
        "oai_base": "https://red.library.usd.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:diss-thesis"],  # Dissertations and Theses
        "metadata_prefix": "oai_dc",
    },
    "uarkansas": {
        "name": "University of Arkansas",
        "state": "AR",
        "oai_base": "https://scholarworks.uark.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],  # Graduate Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "lsu": {
        "name": "Louisiana State University",
        "state": "LA",
        "oai_base": "https://digitalcommons.lsu.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:gradschool_dissertations", "publication:gradschool_theses"],
        "metadata_prefix": "oai_dc",
    },
    "la_tech": {
        "name": "Louisiana Tech University",
        "state": "LA",
        "oai_base": "https://digitalcommons.latech.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertations"],  # Doctoral Dissertations
        "metadata_prefix": "oai_dc",
    },
    # ──── East Midwest & Upper South ────
    "marquette": {
        "name": "Marquette University",
        "state": "WI",
        "oai_base": "https://epublications.marquette.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertations_mu"],  # Dissertations (1934-)
        "metadata_prefix": "oai_dc",
    },
    "siu": {
        "name": "Southern Illinois University Carbondale",
        "state": "IL",
        "oai_base": "https://opensiuc.lib.siu.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertations"],  # Dissertations
        "metadata_prefix": "oai_dc",
    },
    "niu": {
        "name": "Northern Illinois University",
        "state": "IL",
        "oai_base": "https://huskiecommons.lib.niu.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:allgraduate-thesesdissertations"],
        "metadata_prefix": "oai_dc",
    },
    "purdue": {
        "name": "Purdue University",
        "state": "IN",
        "oai_base": "https://docs.lib.purdue.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:open_access_dissertations", "publication:etd"],
        "metadata_prefix": "oai_dc",
    },
    "uky": {
        "name": "University of Kentucky",
        "state": "KY",
        "oai_base": "https://uknowledge.uky.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:gradschool_diss"],  # Doctoral Dissertations
        "metadata_prefix": "oai_dc",
    },
    "ulouisville": {
        "name": "University of Louisville",
        "state": "KY",
        "oai_base": "https://ir.library.louisville.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],
        "metadata_prefix": "oai_dc",
    },
    "umemphis": {
        "name": "University of Memphis",
        "state": "TN",
        "oai_base": "https://digitalcommons.memphis.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],
        "metadata_prefix": "oai_dc",
    },
    "msstate": {
        "name": "Mississippi State University",
        "state": "MS",
        "oai_base": "https://scholarsjunction.msstate.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:td"],  # Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "olemiss": {
        "name": "University of Mississippi",
        "state": "MS",
        "oai_base": "https://egrove.olemiss.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],  # will try umbrella; if empty, harvest dept sets
        "metadata_prefix": "oai_dc",
    },
    "usm": {
        "name": "University of Southern Mississippi",
        "state": "MS",
        "oai_base": "https://aquila.usm.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertations"],
        "metadata_prefix": "oai_dc",
    },
    # ──── Batch 4: Mid-Atlantic & Great Lakes ────
    "wayne_state": {
        "name": "Wayne State University",
        "state": "MI",
        "oai_base": "https://digitalcommons.wayne.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:oa_dissertations"],
        "metadata_prefix": "oai_dc",
    },
    "wmich": {
        "name": "Western Michigan University",
        "state": "MI",
        "oai_base": "https://scholarworks.wmich.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertations"],
        "metadata_prefix": "oai_dc",
    },
    "mtu": {
        "name": "Michigan Technological University",
        "state": "MI",
        "oai_base": "https://digitalcommons.mtu.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],
        "metadata_prefix": "oai_dc",
    },
    "bgsu": {
        "name": "Bowling Green State University",
        "state": "OH",
        "oai_base": "https://scholarworks.bgsu.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:odc_diss"],
        "metadata_prefix": "oai_dc",
    },
    "upenn": {
        "name": "University of Pennsylvania",
        "state": "PA",
        "oai_base": "https://repository.upenn.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["col_20.500.14332_2"],
        "metadata_prefix": "oai_dc",
    },
    "njit": {
        "name": "New Jersey Institute of Technology",
        "state": "NJ",
        "oai_base": "https://digitalcommons.njit.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertations"],
        "metadata_prefix": "oai_dc",
    },
    "wvu": {
        "name": "West Virginia University",
        "state": "WV",
        "oai_base": "https://researchrepository.wvu.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],
        "metadata_prefix": "oai_dc",
    },
    # ──── Batch 5: Southeast ────
    "ncstate": {
        "name": "North Carolina State University",
        "state": "NC",
        "oai_base": "https://repository.lib.ncsu.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_1840.20_23"],  # NC State Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "duke": {
        "name": "Duke University",
        "state": "NC",
        "oai_base": "https://dukespace.lib.duke.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["col_10161_4"],  # Dissertations
        "metadata_prefix": "oai_dc",
    },
    "clemson": {
        "name": "Clemson University",
        "state": "SC",
        "oai_base": "https://tigerprints.clemson.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:all_dissertations"],
        "metadata_prefix": "oai_dc",
    },
    "usc_columbia": {
        "name": "University of South Carolina",
        "state": "SC",
        "oai_base": "https://scholarcommons.sc.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],
        "metadata_prefix": "oai_dc",
    },
    "usf": {
        "name": "University of South Florida",
        "state": "FL",
        "oai_base": "https://digitalcommons.usf.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],
        "metadata_prefix": "oai_dc",
    },
    "ucf": {
        "name": "University of Central Florida",
        "state": "FL",
        "oai_base": "https://stars.library.ucf.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],
        "metadata_prefix": "oai_dc",
    },
    "fau": {
        "name": "Florida Atlantic University",
        "state": "FL",
        "oai_base": "https://digitalcommons.fau.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],
        "metadata_prefix": "oai_dc",
    },
    # ──── Batch 6: Northeast ────
    "harvard": {
        "name": "Harvard University",
        "state": "MA",
        "oai_base": "https://dash.harvard.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["col_1_4927603"],  # FAS Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "bu": {
        "name": "Boston University",
        "state": "MA",
        "oai_base": "https://open.bu.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_2144_898"],  # Theses & Dissertations
        "metadata_prefix": "oai_dc",
    },
    "syracuse": {
        "name": "Syracuse University",
        "state": "NY",
        "oai_base": "https://surface.syr.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],
        "metadata_prefix": "oai_dc",
    },
    "cuny": {
        "name": "City University of New York",
        "state": "NY",
        "oai_base": "https://academicworks.cuny.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:gc_etds"],  # Graduate Center ETDs — 6,533 records
        "metadata_prefix": "oai_dc",
    },
    "yale": {
        "name": "Yale University",
        "state": "CT",
        "oai_base": "https://elischolar.library.yale.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:gsas_dissertations"],
        "metadata_prefix": "oai_dc",
    },
    "uconn": {
        "name": "University of Connecticut",
        "state": "CT",
        "oai_base": "https://opencommons.uconn.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertations"],
        "metadata_prefix": "oai_dc",
    },
    "dartmouth": {
        "name": "Dartmouth College",
        "state": "NH",
        "oai_base": "https://digitalcommons.dartmouth.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertations"],
        "metadata_prefix": "oai_dc",
    },
    "unh": {
        "name": "University of New Hampshire",
        "state": "NH",
        "oai_base": "https://scholars.unh.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertation"],
        "metadata_prefix": "oai_dc",
    },
    "umaine": {
        "name": "University of Maine",
        "state": "ME",
        "oai_base": "https://digitalcommons.library.umaine.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd"],
        "metadata_prefix": "oai_dc",
    },
    "uri": {
        "name": "University of Rhode Island",
        "state": "RI",
        "oai_base": "https://digitalcommons.uri.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:bio_etd", "publication:bps_etd", "publication:cba_etd",
                 "publication:che_etd", "publication:chm_etd", "publication:cmb_etd",
                 "publication:cmd_etd", "publication:com_etd", "publication:cpl_etd",
                 "publication:csc_etd", "publication:cve_etd", "publication:ecn_etd",
                 "publication:education_etd", "publication:ele_etd", "publication:eng_etd",
                 "publication:enre_etd", "publication:favs_etd", "publication:geo_etd",
                 "publication:gso_etd", "publication:hdf_etd", "publication:his_etd",
                 "publication:inp_etd", "publication:kinesiology_etd",
                 "publication:maf_etd", "publication:mcise_etd", "publication:ml_etd",
                 "publication:mth_etd", "publication:nfs_etd", "publication:nrs_etd",
                 "publication:nursing_etd", "publication:oa_diss",
                 "publication:oce_etd", "publication:phl_etd", "publication:php_etd",
                 "publication:phys_etd", "publication:pls_etd", "publication:psc_etd",
                 "publication:psy_etd", "publication:soc_etd", "publication:theses",
                 "publication:tmd_etd"],  # all dept ETD sets + umbrella
        "metadata_prefix": "oai_dc",
    },
    # ──── Batch 7: Texas & Territories ────
    "unt": {
        "name": "University of North Texas",
        "state": "TX",
        "oai_base": "https://digital.library.unt.edu/oai/",
        "platform": "dspace",
        "sets": ["collection:UNTETD"],
        "metadata_prefix": "oai_dc",
    },
    "smu": {
        "name": "Southern Methodist University",
        "state": "TX",
        "oai_base": "https://scholar.smu.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:theses-and-dissertations"],  # umbrella ETD set — 845 records
        "metadata_prefix": "oai_dc",
    },
    "uhawaii": {
        "name": "University of Hawaii at Manoa",
        "state": "HI",
        "oai_base": "https://scholarspace.manoa.hawaii.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_10125_8002"],
        "metadata_prefix": "oai_dc",
    },
    # ──── Priority Targets: Top NRA+Asian STEM PhD producers ────
    "mit": {
        "name": "Massachusetts Institute of Technology",
        "state": "MA",
        "oai_base": "https://dspace.mit.edu/oai/request",
        "platform": "dspace",
        "sets": ["com_1721.1_7582"],  # 3. Theses (main community)
        "metadata_prefix": "oai_dc",
    },
    "utaustin": {
        "name": "University of Texas at Austin",
        "state": "TX",
        "oai_base": "https://repositories.lib.utexas.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_2152_4"],  # UT Electronic Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "osu": {
        "name": "Ohio State University",
        "state": "OH",
        "oai_base": "https://kb.osu.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_1811_133"],  # Undergraduate + Graduate Research Theses
        "metadata_prefix": "oai_dc",
    },
    "vt": {
        "name": "Virginia Tech",
        "state": "VA",
        "oai_base": "https://vtechworks.lib.vt.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_10919_5534"],  # VT Electronic Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "umn": {
        "name": "University of Minnesota",
        "state": "MN",
        "oai_base": "https://conservancy.umn.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_11299_45272"],  # Dissertations and Theses
        "metadata_prefix": "oai_dc",
    },
    "uwmadison": {
        "name": "University of Wisconsin-Madison",
        "state": "WI",
        "oai_base": "https://minds.wisconsin.edu/oai/request",
        "platform": "dspace",
        "sets": ["com_1793_82418"],  # Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "umass": {
        "name": "University of Massachusetts Amherst",
        "state": "MA",
        "oai_base": "https://scholarworks.umass.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_20.500.14394_54495"],  # 15,872 records
        "metadata_prefix": "oai_dc",
    },
    "udel": {
        "name": "University of Delaware",
        "state": "DE",
        "oai_base": "https://udspace.udel.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["col_19716_12883", "col_19716_20898"],  # Doctoral Dissertations (2014+ and pre-2014)
        "metadata_prefix": "oai_dc",
    },
    "gatech": {
        "name": "Georgia Institute of Technology",
        "state": "GA",
        "oai_base": "https://repository.gatech.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["col_1853_67552"],  # Theses and Dissertations (new repo, small)
        "metadata_prefix": "oai_dc",
    },
    # ── Batch 4: High-NRA institutions (Mar 10 2026) ──
    "binghamton": {
        "name": "Binghamton University",
        "state": "NY",
        "oai_base": "https://orb.binghamton.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertation_and_theses", "publication:etds"],
        "metadata_prefix": "oai_dc",
    },
    "rit": {
        "name": "Rochester Institute of Technology",
        "state": "NY",
        "oai_base": "https://repository.rit.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:theses"],
        "metadata_prefix": "oai_dc",
    },
    "utdallas": {
        "name": "University of Texas at Dallas",
        "state": "TX",
        "oai_base": "https://utd-ir.tdl.org/server/oai/request",
        "platform": "dspace",
        "sets": [],  # harvest all, filter to Thesis type post-hoc
        "metadata_prefix": "oai_dc",
    },
    # cornell: SKIPPED — no thesis/dissertation set in DSpace OAI, 106K mixed records
    # uakron: SKIPPED — no dissertation sets found in bepress OAI
    "stony_brook": {
        "name": "Stony Brook University",
        "state": "NY",
        "oai_base": "https://commons.library.stonybrook.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:electronic-disserations-theses", "publication:open-dissertations",
                 "publication:stony-brook-theses-and-dissertations-collection"],
        "metadata_prefix": "oai_dc",
    },
    "rpi": {
        "name": "Rensselaer Polytechnic Institute",
        "state": "NY",
        "oai_base": "https://dspace.rpi.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["col_20.500.13015_4"],  # RPI Theses Online (Complete) — 4,106 records
        "metadata_prefix": "oai_dc",
    },
    "erau": {
        "name": "Embry-Riddle Aeronautical University",
        "state": "FL",
        "oai_base": "https://commons.erau.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:db-dissertations"],  # Doctoral Dissertations - Daytona Beach — 247 records
        "metadata_prefix": "oai_dc",
    },
    # ── Phase 2: High-NRA new harvests (Mar 11 2026) ──
    "utarlington": {
        "name": "University of Texas at Arlington",
        "state": "TX",
        "oai_base": "https://mavmatrix.uta.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:etd_home"],  # umbrella ETD set (29 dept dissertation sets available)
        "metadata_prefix": "oai_dc",
    },
    "ubuffalo": {
        "name": "University at Buffalo",
        "state": "NY",
        "oai_base": "https://ubir.buffalo.edu/oai/request",
        "platform": "dspace",
        "sets": ["com_10477_77914"],  # Theses and Dissertations (ETDs)
        "metadata_prefix": "oai_dc",
    },
    "uhouston": {
        "name": "University of Houston",
        "state": "TX",
        "oai_base": "https://uh-ir.tdl.org/server/oai/request",
        "platform": "dspace",
        "sets": ["com_10657_1"],  # UH Electronic Theses and Dissertations (2010-Present) — 6,854 records
        "metadata_prefix": "oai_dc",
    },
    "ttu": {
        "name": "Texas Tech University",
        "state": "TX",
        "oai_base": "https://ttu-ir.tdl.org/server/oai/request",
        "platform": "dspace",
        "sets": ["com_2346_468"],  # ThinkTech — 12,958 records (mixed types, filter to Thesis post-hoc)
        "metadata_prefix": "oai_dc",
    },
    "uoregon": {
        "name": "University of Oregon",
        "state": "OR",
        "oai_base": "https://scholarsbank.uoregon.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_1794_7556"],  # Graduate Theses & Dissertations
        "metadata_prefix": "oai_dc",
    },
    "uw_seattle": {
        "name": "University of Washington",
        "state": "WA",
        "oai_base": "https://digital.lib.washington.edu/researchworks/server/oai/request",
        "platform": "dspace",
        "sets": [],
        "metadata_prefix": "oai_dc",
        "disabled": True,  # General repository, no thesis-specific collection
    },
    # ── Tier 7: More R1 universities ──
    "auburn": {
        "name": "Auburn University",
        "state": "AL",
        "oai_base": "https://aurora.auburn.edu/oai/request",
        "platform": "dspace",
        "sets": [],  # Harvest all — set filtering doesn't work on this repo
        "metadata_prefix": "oai_dc",
    },
    # ── Tier 6: Remaining R1 universities ──
    "temple": {
        "name": "Temple University",
        "state": "PA",
        "oai_base": "https://scholarshare.temple.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_20.500.12613_10"],  # Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "gmu": {
        "name": "George Mason University",
        "state": "VA",
        "oai_base": "https://mars.gmu.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_1920_2811"],  # etd @ Mason
        "metadata_prefix": "oai_dc",
    },
    "utk": {
        "name": "University of Tennessee Knoxville",
        "state": "TN",
        "oai_base": "https://trace.tennessee.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_20.500.14382_utk-grad"],  # Graduate School
        "metadata_prefix": "oai_dc",
    },
    # ── Tier 5: More missing R1 universities ──
    "uga": {
        "name": "University of Georgia",
        "state": "GA",
        "oai_base": "https://openscholar.uga.edu/oai2d",
        "platform": "invenio",
        "sets": ["ETD-D", "ETD-G"],  # Doctoral + Graduate (master's)
        "metadata_prefix": "oai_dc",
    },
    # ── Tier 4: Missing top-tier research universities ──
    "msu": {
        "name": "Michigan State University",
        "state": "MI",
        "oai_base": "https://d.lib.msu.edu/oai",
        "platform": "dspace",
        "sets": ["etd"],  # Electronic Theses & Dissertations (PhD + MS mixed)
        "metadata_prefix": "oai_dc",
    },
    "uutah": {
        "name": "University of Utah",
        "state": "UT",
        "oai_base": "https://collections.lib.utah.edu/oai",
        "platform": "dspace",
        "sets": ["ir_etd"],  # Theses & Dissertations
        "metadata_prefix": "oai_dc",
    },
    # ── Tier 3: Major R1 research universities ──
    "cornell": {
        "name": "Cornell University",
        "state": "NY",
        "oai_base": "https://ecommons.cornell.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_1813_35"],  # Cornell University Graduate School
        "metadata_prefix": "oai_dc",
    },
    "penn_state": {
        "name": "Penn State University",
        "state": "PA",
        "oai_base": "https://etda.libraries.psu.edu/catalog/oai",
        "platform": "blacklight",
        "sets": [],  # Entire repo is ETDs - harvest all
        "metadata_prefix": "oai_dc",
    },
    "columbia": {
        "name": "Columbia University",
        "state": "NY",
        "oai_base": "https://academiccommons.columbia.edu/oai",
        "platform": "blacklight",
        "sets": ["degree_level:Doctoral", "degree_level:Master's"],
        "metadata_prefix": "oai_dc",
    },
    # ── Tier 2: High-NRA universities ──
    "rice": {
        "name": "Rice University",
        "state": "TX",
        "oai_base": "https://repository.rice.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_1911_8299"],  # Graduate Theses and Dissertations
        "metadata_prefix": "oai_dc",
    },
    "uiuc": {
        "name": "University of Illinois Urbana-Champaign",
        "state": "IL",
        "oai_base": "https://www.ideals.illinois.edu/oai-pmh",
        "platform": "dspace",
        "sets": ["com_2142_5130"],  # Graduate Dissertations and Theses at Illinois
        "metadata_prefix": "oai_dc",
    },
    "umd": {
        "name": "University of Maryland",
        "state": "MD",
        "oai_base": "https://api.drum.lib.umd.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_1903_1654", "com_1903_12"],  # Engineering + CMNS (biggest STEM colleges)
        "metadata_prefix": "oai_dc",
    },
    "cmu": {
        "name": "Carnegie Mellon University",
        "state": "PA",
        "oai_base": "https://api.figshare.com/v2/oai",
        "platform": "figshare",
        "sets": ["portal_231"],  # KiltHub portal
        "metadata_prefix": "oai_dc",
    },
}


def fetch_oai_page(url, retries=3):
    """Fetch a single OAI-PMH page with retries."""
    for attempt in range(retries):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return resp.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as e:
            log.warning("  Attempt %d failed: %s", attempt + 1, e)
            if attempt < retries - 1:
                time.sleep(REQUEST_DELAY * (attempt + 2))
    return None


def parse_records(xml_content, repo_key, university):
    """Parse OAI-PMH XML and extract DC metadata records."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        log.error("  XML parse error: %s", e)
        return [], None, None

    records = []
    for record in root.findall(".//oai:record", NS):
        header = record.find("oai:header", NS)
        if header is not None and header.get("status") == "deleted":
            continue

        metadata = record.find("oai:metadata/oai_dc:dc", NS)
        if metadata is None:
            continue

        # Get OAI identifier
        oai_id_elem = header.find("oai:identifier", NS) if header is not None else None
        oai_id = oai_id_elem.text.strip() if oai_id_elem is not None and oai_id_elem.text else ""

        # Get set memberships
        set_specs = []
        if header is not None:
            for ss in header.findall("oai:setSpec", NS):
                if ss.text:
                    set_specs.append(ss.text.strip())

        def get_text(tag):
            elem = metadata.find(f"dc:{tag}", NS)
            return elem.text.strip() if elem is not None and elem.text else ""

        def get_all_text(tag):
            elems = metadata.findall(f"dc:{tag}", NS)
            return "; ".join(e.text.strip() for e in elems if e.text)

        # Extract URL from identifiers
        identifiers = [e.text.strip() for e in metadata.findall("dc:identifier", NS) if e.text]
        url = ""
        for ident in identifiers:
            if ident.startswith("http"):
                url = ident
                break

        row = {
            "repo": repo_key,
            "university": university,
            "identifier": oai_id,
            "title": get_text("title"),
            "creator": get_all_text("creator"),
            "contributor": get_all_text("contributor"),
            "date": get_text("date"),
            "subject": get_all_text("subject"),
            "description": (get_text("description") or "")[:500],
            "type": get_all_text("type"),
            "format": get_text("format"),
            "language": get_text("language"),
            "source": get_text("source"),
            "relation": get_all_text("relation"),
            "oai_set": "; ".join(set_specs),
            "url": url or (identifiers[0] if identifiers else ""),
        }
        records.append(row)

    # Get resumptionToken
    token_elem = root.find(".//oai:resumptionToken", NS)
    resumption_token = None
    total_size = None
    if token_elem is not None:
        resumption_token = token_elem.text.strip() if token_elem.text else None
        total_size = token_elem.get("completeListSize")

    return records, resumption_token, total_size


def harvest_set(repo_key, config, oai_set, writer, checkpoint, delay=1.0):
    """Harvest all records for a single OAI set."""
    oai_base = config["oai_base"]
    university = config["name"]
    prefix = config["metadata_prefix"]

    log.info("Harvesting set '%s' from %s", oai_set, university)

    # Check for resumption token
    ck_key = f"{repo_key}:{oai_set}"
    token = checkpoint.get("tokens", {}).get(ck_key)
    if token:
        # For bepress, resumptionToken is URL-encoded differently
        url = f"{oai_base}?verb=ListRecords&resumptionToken={token}"
        log.info("  Resuming from checkpoint")
    else:
        if oai_set:
            url = f"{oai_base}?verb=ListRecords&metadataPrefix={prefix}&set={oai_set}"
        else:
            url = f"{oai_base}?verb=ListRecords&metadataPrefix={prefix}"

    total_records = 0
    page = 0

    while url:
        page += 1
        content = fetch_oai_page(url)
        if content is None:
            log.error("  Failed to fetch page %d, stopping set %s", page, oai_set)
            break

        if "noRecordsMatch" in content:
            log.info("  No records found for set %s", oai_set)
            break

        if "<error" in content and "badResumptionToken" in content:
            log.warning("  Bad resumption token, restarting set %s", oai_set)
            url = f"{oai_base}?verb=ListRecords&metadataPrefix={prefix}&set={oai_set}"
            checkpoint.get("tokens", {})[ck_key] = None
            continue

        records, resumption_token, total_size = parse_records(content, repo_key, university)

        for row in records:
            writer.writerow(row)
        total_records += len(records)

        if page == 1 and total_size:
            log.info("  Total available: %s", total_size)

        log.info("  Page %d: %d records (total: %d)", page, len(records), total_records)

        if resumption_token:
            checkpoint.setdefault("tokens", {})[ck_key] = resumption_token
            save_checkpoint(checkpoint, repo_key)
            url = f"{oai_base}?verb=ListRecords&resumptionToken={resumption_token}"
        else:
            checkpoint.setdefault("tokens", {})[ck_key] = None
            checkpoint.setdefault("completed_sets", [])
            if ck_key not in checkpoint["completed_sets"]:
                checkpoint["completed_sets"].append(ck_key)
            save_checkpoint(checkpoint, repo_key)
            url = None

        time.sleep(delay)

    log.info("  Set '%s' done: %d records", oai_set, total_records)
    return total_records


def checkpoint_path(repo_key):
    return DATA_DIR / f"{repo_key}_checkpoint.json"


def output_csv_path(repo_key):
    return DATA_DIR / f"{repo_key}_etds.csv"


def load_checkpoint(repo_key):
    cp = checkpoint_path(repo_key)
    if cp.exists():
        with open(cp) as f:
            return json.load(f)
    return {"completed_sets": [], "tokens": {}}


def save_checkpoint(checkpoint, repo_key):
    with open(checkpoint_path(repo_key), "w") as f:
        json.dump(checkpoint, f, indent=2)


def discover_bepress_etd_sets(oai_base):
    """For bepress repos, discover all ETD-related sets."""
    url = f"{oai_base}?verb=ListSets"
    content = fetch_oai_page(url)
    if not content:
        return []

    root = ET.fromstring(content)
    sets = []
    for s in root.findall(".//oai:set", NS):
        spec = s.find("oai:setSpec", NS)
        name = s.find("oai:setName", NS)
        if spec is not None and spec.text:
            spec_t = spec.text.strip()
            name_t = name.text.strip() if name is not None and name.text else ""
            combined = (spec_t + name_t).lower()
            if any(k in combined for k in ['etd', 'thesis', 'dissert']):
                sets.append(spec_t)
                log.info("  Found ETD set: %s (%s)", spec_t, name_t)

    return sets


def main():
    parser = argparse.ArgumentParser(description="Generic OAI-PMH ETD harvester")
    parser.add_argument("--repo", type=str, help="Repository key (e.g., uarizona)")
    parser.add_argument("--list", action="store_true", help="List available repositories")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--discover-sets", action="store_true", help="Discover ETD sets (bepress)")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list:
        print(f"\n{'Key':<18} {'University':<45} {'State':<5} {'Platform':<10} {'Sets'}")
        print("─" * 100)
        for key, cfg in sorted(REPOS.items()):
            sets_str = ", ".join(cfg["sets"][:3])
            if len(cfg["sets"]) > 3:
                sets_str += f" (+{len(cfg['sets'])-3} more)"
            print(f"{key:<18} {cfg['name']:<45} {cfg['state']:<5} {cfg['platform']:<10} {sets_str}")
        return

    if not args.repo:
        parser.error("--repo is required (or use --list)")

    if args.repo not in REPOS:
        log.error("Unknown repo: %s. Use --list to see available repos.", args.repo)
        sys.exit(1)

    config = REPOS[args.repo]
    repo_key = args.repo

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Optionally discover sets
    if args.discover_sets:
        log.info("Discovering ETD sets for %s ...", config["name"])
        sets = discover_bepress_etd_sets(config["oai_base"])
        log.info("Found %d ETD sets", len(sets))
        return

    checkpoint = load_checkpoint(repo_key) if args.resume else {"completed_sets": [], "tokens": {}}

    # Open CSV
    out_csv = output_csv_path(repo_key)
    file_exists = out_csv.exists() and args.resume
    csvfile = open(out_csv, "a" if file_exists else "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
    if not file_exists:
        writer.writeheader()

    grand_total = 0
    sets_to_harvest = config["sets"] if config["sets"] else [None]  # None = no set filter
    for oai_set in sets_to_harvest:
        ck_key = f"{repo_key}:{oai_set or '__all__'}"
        if ck_key in checkpoint.get("completed_sets", []) and args.resume:
            log.info("Skipping set %s — already completed", oai_set or '(all)')
            continue

        try:
            count = harvest_set(repo_key, config, oai_set, writer, checkpoint, delay=args.delay)
            grand_total += count
            csvfile.flush()
        except Exception as e:
            log.error("Error harvesting set %s: %s", oai_set or '(all)', e, exc_info=True)
            continue

    csvfile.close()
    save_checkpoint(checkpoint, repo_key)

    log.info("=" * 60)
    log.info("Done! %s: %d records harvested", config["name"], grand_total)
    log.info("Output: %s", out_csv)


if __name__ == "__main__":
    main()
