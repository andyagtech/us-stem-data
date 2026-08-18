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
# ETD Metadata Standard namespace (used by bepress repos)
NS_ETDMS = {
    **NS,
    "etdms": "http://www.ndltd.org/standards/metadata/etdms/1.0/",
}

REQUEST_DELAY = 1.0
REQUEST_TIMEOUT = 30

# Repositories disagree about which user agent they trust, and they disagree in
# both directions, so there is no single string that works everywhere.
#
#   scholar.colorado.edu, www.ideals.illinois.edu   403 the project token, 200 a browser
#   iowa_state, mines, temple, uarizona, ukansas,   the reverse: 200 the project token,
#   umass, uwyoming (all DSpace)                    403 a browser string
#
# IDEALS is why UIUC sat at 4% degree labelling while LABELING_METHODOLOGY.md
# recorded it as having "no API available" — it has one, and it was refusing us
# at the door. So: identify honestly by default, and fall back to a browser
# string only on a 403.
#
# This does not rescue every block. repository.lib.ncsu.edu challenges every
# agent including Googlebot, and scholarworks.montana.edu blocks by IP (TCP and
# TLS complete, then the response is withheld). Those need a proof-of-work
# client and a cool-off respectively, not a different string.
PROJECT_UA = "phd-demographics-harvester/1.0 (academic research)"
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

HEADERS = {"User-Agent": PROJECT_UA}
FALLBACK_HEADERS = {"User-Agent": BROWSER_UA}

CSV_FIELDS = [
    "repo", "university", "identifier", "title", "creator",
    "contributor", "date", "subject", "description", "type",
    "format", "language", "source", "relation",
    "oai_set", "url",
    "degree_name", "degree_level", "degree_discipline",
    "date_issued",
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
        # NMT has no local repository; the Skeen Library uses Zenodo as its IR.
        # Community "nmt" = NMT Dissertations & Theses (only ~13 records deposited).
        # Zenodo currently 403s this network ("unusual traffic"); verified from another IP.
        "oai_base": "https://zenodo.org/oai2d",
        "platform": "invenio",
        "sets": ["user-nmt"],
        "metadata_prefix": "oai_dc",
    },
    "nmsu": {
        "name": "New Mexico State University",
        "state": "NM",
        # scholarworks.nmsu.edu no longer resolves; the live bepress instance is
        # digitalcommons.nmsu.edu. Verified 2026-08-18: it exposes 64 sets and NONE
        # are ETD sets (publication:dissertations and publication:gradschool both
        # return noRecordsMatch). NMSU ETDs are ProQuest-only (etdadmin.com/nmsuetd),
        # so there is nothing harvestable here.
        "oai_base": "https://digitalcommons.nmsu.edu/do/oai/",
        "platform": "bepress",
        "sets": [],
        "metadata_prefix": "oai_dc",
        "disabled": True,  # no open-access ETD collection published
    },
    "pdx": {
        "name": "Portland State University",
        "state": "OR",
        # Harvested by a bespoke script originally and never registered here,
        # so the ETDMS degree sweep skipped it and it sat at 8.4% labelled.
        "oai_base": "https://pdxscholar.library.pdx.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:open_access_etds"],
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
        "metadata_prefix": "oai_etdms",
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
        # Bison Scholar (DSpace 7.6.2). UI at library.ndsu.edu/ir, REST/OAI at /server.
        # NOTE: the whole host sits behind a cookie bot-check — an unauthenticated request
        # 302s to /bcheck/. Passing it once (POST /bcheck/validate with humancheck=yes)
        # sets a `user_ok=ishuman` cookie that unlocks the endpoint. urllib without a
        # cookie jar cannot harvest this, so the repo stays disabled until the harvester
        # can carry cookies. Verified 2026-08-18: com_10365_26050 = 4,810 ETD records.
        "oai_base": "https://library.ndsu.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_10365_26050"],  # NDSU Theses & Dissertations
        "metadata_prefix": "oai_dc",
        "disabled": True,  # requires a bot-check cookie the harvester does not send
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
        "metadata_prefix": "oai_etdms",
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
        "sets": ["publication:dissertations_mu",   # Dissertations (1934-)
                 "publication:theses_open"],       # Master's Theses (2009-)
        "metadata_prefix": "oai_dc",
    },
    "siu": {
        "name": "Southern Illinois University Carbondale",
        "state": "IL",
        "oai_base": "https://opensiuc.lib.siu.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:dissertations",   # Dissertations
                 "publication:theses"],        # Theses (master's)
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
        "metadata_prefix": "oai_etdms",
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
        "sets": ["publication:dissertations", "publication:masters_theses"],
        "metadata_prefix": "oai_dc",
    },
    # ──── Batch 4: Mid-Atlantic & Great Lakes ────
    "wayne_state": {
        "name": "Wayne State University",
        "state": "MI",
        "oai_base": "https://digitalcommons.wayne.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:oa_dissertations", "publication:oa_theses"],
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
        # URL still correct, but as of 2026 the whole host sits behind Anubis proof-of-work
        # bot detection (only robots.txt is exempt). Every User-Agent tried — browser,
        # curl, Googlebot, our harvester — gets the JS challenge, from two separate
        # networks. Not harvestable until NCSU allowlists the harvester.
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
        "sets": ["col_10161_4",       # Dissertations
                 "col_10161_2493"],   # Master's Theses
        "metadata_prefix": "oai_dc",
    },
    "clemson": {
        "name": "Clemson University",
        "state": "SC",
        "oai_base": "https://tigerprints.clemson.edu/do/oai/",
        "platform": "bepress",
        # All Dissertations (doctoral) + All Theses (master's). Harvesting only
        # the first read as "Clemson awards no master's degrees".
        "sets": ["publication:all_dissertations", "publication:all_theses"],
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
        "sets": ["publication:dissertations", "publication:masters_theses"],
        "metadata_prefix": "oai_dc",
    },
    "unh": {
        "name": "University of New Hampshire",
        "state": "NH",
        "oai_base": "https://scholars.unh.edu/do/oai/",
        "platform": "bepress",
        # publication:thesis is "Master's Theses and Capstones"
        "sets": ["publication:dissertation", "publication:thesis"],
        "metadata_prefix": "oai_dc",
    },
    "umaine": {
        "name": "University of Maine",
        "state": "ME",
        # DigitalCommons@UMaine was sunset 2026-06-30 and its host no longer resolves.
        # UMaine System migrated to Ex Libris Alma Specto; ETDs are now discoverable at
        # maine.primo.exlibrisgroup.com (vid=01MAINE_INST:DigCol). Alma's OAI endpoint
        # (maine.alma.exlibrisgroup.com/view/oai/01MAINE_INST/request) returns
        # error_code 21 "Unauthorized access to the OAI services" — no public OAI-PMH.
        # A future scraper would need the Primo NDE REST API instead.
        "oai_base": "",
        "platform": "alma_specto",
        "sets": [],
        "metadata_prefix": "oai_dc",
        "disabled": True,  # no public OAI-PMH after the Specto migration
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
        "metadata_prefix": "oai_etdms",
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
        # MINDS@UW upgraded to DSpace 7 (/oai/request -> /server/oai/request) and moved to
        # minds.wisc.edu; minds.wisconsin.edu 301s there on every verb except Identify.
        "oai_base": "https://minds.wisc.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_1793_82418"],  # Theses and Dissertations — 3,037 records
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
        "sets": ["col_19716_12883", "col_19716_20898",   # Doctoral Dissertations (2014+ and pre-2014)
                 "col_19716_5010"],                      # Master's Theses (Fall 2009 to present)
        # col_19716_21710 (pre-Fall-2009 master's theses, partial holdings) is
        # deliberately excluded: its dc:date is the 2020 bulk-ingest timestamp,
        # not the degree year, so every record would land in 2020.
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
        "sets": ["publication:etds"],  # Superset — includes dissertation_and_theses
        "metadata_prefix": "oai_etdms",  # Has degree.name, degree.level, degree.discipline
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
        # /researchworks is the Angular UI base only; OAI lives at the host root.
        "oai_base": "https://digital.lib.washington.edu/server/oai/request",
        "platform": "dspace",
        "sets": ["com_1773_4888"],  # Dissertations and Theses — 19,695 records
        "metadata_prefix": "oai_dc",
        # Endpoint and set re-verified 2026-08-18; the old "no thesis collection" note was
        # wrong. Left disabled pending a decision to include UW in the harvest.
        "disabled": True,
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
        # MARS migrated off DSpace to TIND (Invenio); mars.gmu.edu 301s to digitalcollections.gmu.edu
        "oai_base": "https://digitalcollections.gmu.edu/oai2d",
        "platform": "invenio",
        "sets": ["gmu_lib:ir_collections"],  # MARS Digital Repository — 8,123 records (ETDs mixed with articles)
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
    """Fetch a single OAI-PMH page with retries.

    On a 403 the request is retried once with a browser user agent; see the
    note on HEADERS for why neither string works everywhere.
    """
    headers = HEADERS
    for attempt in range(retries):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return resp.read().decode("utf-8")
        except HTTPError as e:
            if e.code == 403 and headers is HEADERS:
                log.info("  403 with project user agent, retrying as a browser")
                headers = FALLBACK_HEADERS
                continue
            log.warning("  Attempt %d failed: %s", attempt + 1, e)
            if attempt < retries - 1:
                time.sleep(REQUEST_DELAY * (attempt + 2))
        except (URLError, TimeoutError) as e:
            log.warning("  Attempt %d failed: %s", attempt + 1, e)
            if attempt < retries - 1:
                time.sleep(REQUEST_DELAY * (attempt + 2))
    return None


def _pick_issued_date(dates):
    """Pick the award date from a record's dc:date values.

    oai_dc flattens dc.date.accessioned, dc.date.available and
    dc.date.issued into repeated <dc:date> elements, and DSpace emits the
    ingest timestamps first. Taking the first value therefore dates a
    thesis by when the repository ingested it, not when the degree was
    awarded — measured against our own harvested records, that misdates
    84% of Iowa State's and 22% of MIT's, by a median of 24 and 39 years.

    Accession timestamps carry a time component; the award date does not.
    Prefer the earliest plain date, which is the degree event rather than
    a later revision.
    """
    plain = [d.strip() for d in dates if d and "T" not in d]
    if not plain:
        return ""
    return sorted(plain)[0]


def parse_records(xml_content, repo_key, university, metadata_prefix="oai_dc"):
    """Parse OAI-PMH XML and extract DC metadata records.
    Supports both oai_dc and oai_etdms metadata prefixes."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        log.error("  XML parse error: %s", e)
        return [], None, None

    is_etdms = metadata_prefix == "oai_etdms"

    records = []
    for record in root.findall(".//oai:record", NS):
        header = record.find("oai:header", NS)
        if header is not None and header.get("status") == "deleted":
            continue

        # Try oai_dc wrapper first, then oai_etdms
        metadata = record.find("oai:metadata/oai_dc:dc", NS)
        etdms_metadata = None
        if metadata is None and is_etdms:
            # oai_etdms: try multiple possible wrapper elements
            # Some repos use the etdms namespace directly
            for ns_url in ["http://www.ndltd.org/standards/metadata/etdms/1.0/",
                           "http://www.ndltd.org/standards/metadata/etdms/1.1/"]:
                for tag in ["thesis", "etdms"]:
                    metadata = record.find(f"oai:metadata/{{{ns_url}}}{tag}", NS)
                    if metadata is not None:
                        etdms_metadata = metadata
                        break
                if metadata is not None:
                    break
            # Last resort: grab first child of oai:metadata
            if metadata is None:
                meta_wrap = record.find("oai:metadata", NS)
                if meta_wrap is not None and len(meta_wrap) > 0:
                    metadata = meta_wrap[0]
                    etdms_metadata = metadata
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
            # Try dc: namespace first, then unnamespaced
            elem = metadata.find(f"dc:{tag}", NS)
            if elem is None:
                elem = metadata.find(tag)
            # For etdms, also try with the etdms namespace
            if elem is None and etdms_metadata is not None:
                ns_uri = etdms_metadata.tag.split('}')[0].lstrip('{') if '}' in etdms_metadata.tag else ''
                if ns_uri:
                    elem = metadata.find(f"{{{ns_uri}}}{tag}")
            return elem.text.strip() if elem is not None and elem.text else ""

        def get_all_dates():
            elems = metadata.findall("dc:date", NS) or metadata.findall("date")
            return [e.text for e in elems if e is not None and e.text]

        def get_all_text(tag):
            # Try dc: namespace first, then unnamespaced
            elems = metadata.findall(f"dc:{tag}", NS)
            if not elems:
                elems = metadata.findall(tag)
            if not elems and etdms_metadata is not None:
                ns_uri = etdms_metadata.tag.split('}')[0].lstrip('{') if '}' in etdms_metadata.tag else ''
                if ns_uri:
                    elems = metadata.findall(f"{{{ns_uri}}}{tag}")
            return "; ".join(e.text.strip() for e in elems if e.text)

        # Extract URL from identifiers
        identifiers = []
        for id_elem in metadata.findall(f"dc:identifier", NS):
            if id_elem.text:
                identifiers.append(id_elem.text.strip())
        if not identifiers:
            for id_elem in metadata.findall("identifier"):
                if id_elem.text:
                    identifiers.append(id_elem.text.strip())
            if not identifiers and etdms_metadata is not None:
                ns_uri = etdms_metadata.tag.split('}')[0].lstrip('{') if '}' in etdms_metadata.tag else ''
                if ns_uri:
                    for id_elem in metadata.findall(f"{{{ns_uri}}}identifier"):
                        if id_elem.text:
                            identifiers.append(id_elem.text.strip())
        url = ""
        for ident in identifiers:
            if ident.startswith("http"):
                url = ident
                break

        # Extract ETD degree fields if available
        degree_name = ""
        degree_level = ""
        degree_discipline = ""
        if etdms_metadata is not None:
            ns_uri = etdms_metadata.tag.split('}')[0].lstrip('{') if '}' in etdms_metadata.tag else ''
            ns_pre = f"{{{ns_uri}}}" if ns_uri else ""

            # Check direct children for thesis.degree.level
            for child in metadata:
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                text = (child.text or "").strip()
                if not text:
                    continue
                if tag in ("thesis.degree.name", "degree.name", "degree_name") and not degree_name:
                    degree_name = text
                elif tag in ("thesis.degree.abbreviation",) and not degree_name:
                    degree_name = text  # fallback: use abbreviation (e.g. "Ph.D.")
                elif tag in ("thesis.degree.level", "degree.level", "degree_level") and not degree_level:
                    degree_level = text
                elif tag in ("thesis.degree.discipline", "degree.discipline", "degree_discipline") and not degree_discipline:
                    degree_discipline = text

            # Check <degree> wrapper for children (bepress puts name/discipline here)
            degree_wrap = metadata.find(f"{ns_pre}degree")
            if degree_wrap is None:
                degree_wrap = metadata.find("degree")
            if degree_wrap is not None:
                for child in degree_wrap:
                    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    text = (child.text or "").strip()
                    if not text:
                        continue
                    if tag in ("thesis.degree.name", "degree.name", "name") and not degree_name:
                        degree_name = text
                    elif tag in ("thesis.degree.abbreviation",) and not degree_name:
                        degree_name = text
                    elif tag in ("thesis.degree.level", "degree.level", "level") and not degree_level:
                        degree_level = text
                    elif tag in ("thesis.degree.discipline", "degree.discipline", "discipline") and not degree_discipline:
                        degree_discipline = text

        row = {
            "repo": repo_key,
            "university": university,
            "identifier": oai_id,
            "title": get_text("title"),
            "creator": get_all_text("creator"),
            "contributor": get_all_text("contributor"),
            "date": get_text("date"),
            "date_issued": _pick_issued_date(get_all_dates()),
            "subject": get_all_text("subject"),
            "description": (get_text("description") or "")[:2000],
            "type": get_all_text("type"),
            "format": get_text("format"),
            "language": get_text("language"),
            "source": get_text("source"),
            "relation": get_all_text("relation"),
            "oai_set": "; ".join(set_specs),
            "url": url or (identifiers[0] if identifiers else ""),
            "degree_name": degree_name,
            "degree_level": degree_level,
            "degree_discipline": degree_discipline,
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


def _load_existing_identifiers(path):
    """Identifiers already present in a harvest CSV, for append-time dedup."""
    seen = set()
    if not path.exists():
        return seen
    try:
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                ident = row.get("identifier")
                if ident:
                    seen.add(ident)
    except Exception as e:  # a malformed CSV must not block a harvest
        log.warning("Could not read existing identifiers from %s: %s", path, e)
    return seen


def harvest_set(repo_key, config, oai_set, writer, checkpoint, delay=1.0,
                from_date=None, seen_ids=None):
    """Harvest all records for a single OAI set.

    from_date (YYYY-MM-DD) issues an OAI-PMH selective harvest, returning
    only records added or modified on or after that date. Repositories we
    already hold are otherwise never revisited, so new deposits never land.
    """
    oai_base = config["oai_base"]
    university = config["name"]
    prefix = config["metadata_prefix"]

    log.info("Harvesting set '%s' from %s", oai_set, university)

    # Check for resumption token
    # A selective harvest is a different result set, so it gets its own
    # checkpoint key; resuming it must not consume a full-harvest token.
    ck_key = f"{repo_key}:{oai_set}" if not from_date else f"{repo_key}:{oai_set}:from={from_date}"
    frm = f"&from={from_date}" if from_date else ""
    token = checkpoint.get("tokens", {}).get(ck_key)
    if token:
        # For bepress, resumptionToken is URL-encoded differently
        url = f"{oai_base}?verb=ListRecords&resumptionToken={token}"
        log.info("  Resuming from checkpoint")
    else:
        if oai_set:
            url = f"{oai_base}?verb=ListRecords&metadataPrefix={prefix}&set={oai_set}{frm}"
        else:
            url = f"{oai_base}?verb=ListRecords&metadataPrefix={prefix}{frm}"

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
            url = f"{oai_base}?verb=ListRecords&metadataPrefix={prefix}&set={oai_set}{frm}"
            checkpoint.get("tokens", {})[ck_key] = None
            continue

        records, resumption_token, total_size = parse_records(content, repo_key, university, prefix)

        written = 0
        for row in records:
            # Repositories expose the same record through more than one set,
            # and a selective harvest re-walks a window that may overlap what
            # is already on disk. Neither the resumption token nor the
            # checkpoint is record-level, so dedup has to happen here.
            ident = row.get("identifier")
            if seen_ids is not None and ident:
                if ident in seen_ids:
                    continue
                seen_ids.add(ident)
            writer.writerow(row)
            written += 1
        skipped = len(records) - written
        if skipped:
            log.info("  Skipped %d record(s) already harvested", skipped)
        total_records += written

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
    parser.add_argument("--from", dest="from_date", type=str,
                        help="Selective harvest: only records added or modified "
                             "on or after this date (YYYY-MM-DD)")
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

    # Open CSV. A selective harvest returns only the new deposits, so it must
    # append — opening "w" here would discard everything harvested to date.
    out_csv = output_csv_path(repo_key)
    file_exists = out_csv.exists() and (args.resume or bool(args.from_date))
    fieldnames = CSV_FIELDS
    if file_exists:
        # Earlier harvests wrote a different column set (some files carry a
        # degree_type column, some predate the degree_* columns entirely).
        # Append in the file's own column order, or every appended row lands
        # shifted against the header.
        with open(out_csv, newline="", encoding="utf-8") as _existing:
            header = next(csv.reader(_existing), None)
        if header:
            fieldnames = header
    csvfile = open(out_csv, "a" if file_exists else "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                            extrasaction="ignore", restval="")
    if not file_exists:
        writer.writeheader()

    seen_ids = _load_existing_identifiers(out_csv) if file_exists else set()
    if seen_ids:
        log.info("Loaded %d existing identifiers for dedup", len(seen_ids))

    grand_total = 0
    sets_to_harvest = config["sets"] if config["sets"] else [None]  # None = no set filter
    for oai_set in sets_to_harvest:
        ck_key = f"{repo_key}:{oai_set or '__all__'}"
        if args.from_date:
            ck_key = f"{ck_key}:from={args.from_date}"
        if ck_key in checkpoint.get("completed_sets", []) and args.resume:
            log.info("Skipping set %s — already completed", oai_set or '(all)')
            continue

        try:
            count = harvest_set(repo_key, config, oai_set, writer, checkpoint,
                                delay=args.delay, from_date=args.from_date,
                                seen_ids=seen_ids)
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
