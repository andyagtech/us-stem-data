#!/usr/bin/env python3
"""Generate data-driven OpenGraph share cards for every page of the site, and
wire the meta tags that point at them.

Each card is a 1200x630 PNG carrying that page's own headline figure and its
own chart — not a generic logo. Cards are rendered as HTML + inline SVG in the
house style of site/concentration.html and screenshotted with headless Chrome.

Filenames mirror the site's URL structure exactly, so the card URL is
guessable from the page URL: strip .html, add .png, prefix /og/.

    /index.html                       ->  /og/index.png
    /stem.html                        ->  /og/stem.png
    /concentration.html               ->  /og/concentration.png
    /universities/mit.html            ->  /og/universities/mit.png
    /universities/nonstem/mit.html    ->  /og/universities/nonstem/mit.png

Names are derived from page identity alone — no hashes, counters, timestamps
or cache-busting suffixes — so re-running produces byte-identical names.
University keys are the project's canonical underscore spelling (the keys in
pipeline/universities.json, which are also the sidebar links and the
/data/<mode>/<key>.json filenames): missouri_st, never missouri-st.

Usage:
    python3 scripts/build_og_cards.py                # everything
    python3 scripts/build_og_cards.py --only mit,stem # a subset, by card name
    python3 scripts/build_og_cards.py --pages        # top-level pages only
    python3 scripts/build_og_cards.py --no-tags      # render PNGs, skip meta
    python3 scripts/build_og_cards.py --no-render    # rewrite meta tags only
"""
import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from og import card, data, fonts, shoot, tags  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OG_DIR = SITE / "og"
DOMAIN = "https://phd-demographics.andy-barr.com"
SOURCE_IPEDS = ("IPEDS Completions, award level 17. “Non-resident alien” is the "
                "federal reporting category for visa holders — not ethnicity or origin.")


# ---------------------------------------------------------------------------
# top-level page cards
#
# Every figure below is quoted from the page itself or from the JSON that page
# loads. PAGES maps <page>.html -> card spec + the og:title / og:description
# that should describe that page.
# ---------------------------------------------------------------------------

def _years(d):
    return {int(k): v for k, v in d.items()}


PAGES = {}


def page(name, **kw):
    PAGES[name] = kw


# --- built from data/ipeds/nra_index.csv.gz + concentration.html's own D -----

CONC_DEPTS = {2010: 82, 2011: 99, 2012: 104, 2013: 117, 2014: 118, 2015: 124,
              2016: 130, 2017: 119, 2018: 142, 2019: 147, 2020: 156, 2021: 155,
              2022: 198, 2023: 174, 2024: 181, 2025: 193}
CONC_SHARE = {2010: 4.24, 2011: 5.01, 2012: 5.14, 2013: 5.25, 2014: 5.58,
              2015: 5.48, 2016: 5.53, 2017: 5.22, 2018: 5.84, 2019: 5.98,
              2020: 6.31, 2021: 6.19, 2022: 7.34, 2023: 6.47, 2024: 6.45,
              2025: 7.06}


def build_page_specs(nat):
    """Return {page_name: spec}. nat is data.national_series()."""
    yrs = [y for y in sorted(nat["all"]) if y >= 2010]
    nat_all = {y: nat["all"][y] for y in yrs}
    nat_stem = {y: nat["stem"][y] for y in yrs}
    nat_ns = {y: nat["nonstem"][y] for y in yrs}

    def natline(points, tip, color=card.NRA, area=card.FILL):
        return {"points": points, "color": color, "tip": tip, "area": area}

    P = {}

    P["index"] = dict(
        title="Who Earns America's Advanced Degrees",
        desc="Dissertation and federal data for 107 US research universities: "
             "who receives American doctorates, and who funds them.",
        eyebrow="PhD Demographics", tag="IPEDS · NSF · DHS · DOL",
        headline="Who earns America’s advanced degrees",
        hero=dict(value="471K", label="dissertation and thesis records indexed "
                                      "across 107 US research universities"),
        stats=[dict(n="334,788", l="STEM records"),
               dict(n="136,383", l="non-STEM records")],
        figure=dict(title="NRA share of US research doctorates",
                    sub="All fields, all institutions · IPEDS Completions",
                    chart=("line", [natline(nat_all, f"{nat_all[yrs[-1]]}%")], dict(ymax=40)),
                    legend=[("All US research doctorates", card.NRA)]),
        footer="IPEDS Completions · NSF · DOL · DHS · State Department, "
               "plus 107 university institutional repositories.")

    P["overview"] = dict(
        title="National Overview: US Doctorate Output",
        desc="NSF Survey of Earned Doctorates trends, foreign share by field, "
             "PhD funding and the OPT work-authorization pipeline.",
        eyebrow="ICE/SEVP · SEVIS", tag="OPT authorizations",
        headline="OPT has grown sevenfold since 2007",
        hero=dict(value="173,939", label="OPT work authorizations with employment "
                                         "start dates in 2024"),
        stats=[dict(n="33.3%", acc=True, l="of 2024 doctorates went to temporary visa holders")],
        figure=dict(title="OPT work authorizations, 2007–2024",
                    sub="Annual authorizations with employment start dates",
                    chart=("bar", {2007: 24836, 2008: 45304, 2009: 46116, 2010: 50992,
                                   2011: 56300, 2012: 62427, 2013: 67502, 2014: 77369,
                                   2015: 99016, 2016: 129811, 2017: 140152, 2018: 130512,
                                   2019: 125215, 2020: 112930, 2021: 102985, 2022: 106791,
                                   2023: 152361, 2024: 173939}, dict())),
        footer="NSF Survey of Earned Doctorates · NSF GSS · IPEDS · "
               "ICE/SEVP SEVIS By the Numbers.")

    P["concentration"] = dict(
        title="The Concentration Effect",
        desc="The national non-resident share of US research doctorates is flat, "
             "but the number of majority-non-resident departments has more than doubled.",
        eyebrow="Finding", tag="The flat line hides it",
        headline="The national average hides where the change happened",
        hero=dict(value="82 → 193", label="departments awarding 20+ doctorates "
                                                        "that are majority non-resident, 2010–2025"),
        stats=[dict(n="27.2 → 25.5%", l="national NRA share over the same years")],
        figure=dict(title="Majority-non-resident departments",
                    sub="Departments of 20+ research doctorates per year",
                    chart=("bar", CONC_DEPTS, dict()),
                    legend=[("Departments where non-residents are the majority", card.NRA)]),
        footer=SOURCE_IPEDS)

    P["stem"] = dict(
        title=tags.GENERATED_PAGE_META["stem"][0],
        desc=tags.GENERATED_PAGE_META["stem"][1],
        eyebrow="Institutional repositories", tag="106 universities",
        headline="Who earns America’s STEM doctorates",
        hero=dict(value="15,814", label="STEM research doctorates awarded to "
                                        "non-resident students in 2024 — 32.3% of the total"),
        stats=[dict(n="369,530", l="thesis records across 105 schools")],
        figure=dict(title="Non-resident STEM doctorates awarded",
                    sub="IPEDS Completions, 2010–2024",
                    chart=("bar", {2010: 11120, 2011: 11580, 2012: 12043, 2013: 12785,
                                   2014: 13502, 2015: 13450, 2016: 13480, 2017: 13749,
                                   2018: 14369, 2019: 14655, 2020: 14984, 2021: 14673,
                                   2022: 16294, 2023: 15957, 2024: 15814}, dict())),
        footer="IPEDS Completions Survey (NCES); names harvested from university "
               "OAI-PMH thesis repositories.")

    P["non_stem"] = dict(
        title=tags.GENERATED_PAGE_META["non_stem"][0],
        desc=tags.GENERATED_PAGE_META["non_stem"][1],
        eyebrow="Institutional repositories", tag="Non-STEM fields",
        headline="Non-STEM dissertations, school by school",
        hero=dict(value="148,185", label="non-STEM thesis and dissertation records "
                                         "harvested from 105 university repositories"),
        stats=[dict(n=f"{nat_ns[yrs[-1]]}%", acc=True,
                    l="national NRA share of non-STEM doctorates")],
        figure=dict(title="NRA share of non-STEM research doctorates",
                    sub="All US institutions · IPEDS Completions",
                    chart=("line", [natline(nat_ns, f"{nat_ns[yrs[-1]]}%")], dict()),
                    legend=[("National non-STEM", card.NRA)]),
        footer=SOURCE_IPEDS)

    # --- country / pipeline pages -----------------------------------------
    # These carry <meta name="robots" content="noindex, nofollow">. That stops
    # search indexing; it does not stop a scraper fetching OG tags when someone
    # pastes the link, so they still need real cards.

    P["china"] = dict(
        title="China's Outbound Students Have Turned Down",
        desc="Chinese enrolment in the US peaked at 372,532 in 2020 and has "
             "fallen 28.6% since, as China diversifies its destinations.",
        eyebrow="IIE Open Doors", tag="China",
        headline="China’s US student boom has reversed",
        hero=dict(value="265,919", label="Chinese students in the United States, "
                                         "Open Doors 2025 — down 28.6% from the 2020 peak"),
        figure=dict(title="Chinese students in the US, 2010–2025",
                    sub="Peaked at 372,532 in 2020",
                    chart=("line", [{"points": {2010: 127628, 2011: 157558, 2012: 194029,
                                                2013: 235597, 2014: 274439, 2015: 304040,
                                                2016: 328547, 2017: 350755, 2018: 363341,
                                                2019: 369548, 2020: 372532, 2021: 317299,
                                                2022: 290086, 2023: 289526, 2024: 277398,
                                                2025: 265919},
                                     "color": card.NRA, "tip": "266K", "area": card.FILL}],
                           dict(pct=False)),
                    legend=[("Chinese students in the US", card.NRA)]),
        footer="IIE Open Doors · DHS SEVP · UNESCO UIS · China MOE · IRCC · HESA.")

    P["india"] = dict(
        title="India's Outbound Student Pipeline",
        desc="India sends 1.34M students abroad — 331,602 to the US alone, "
             "a figure that has more than tripled since 2013.",
        eyebrow="IIE Open Doors · India MEA", tag="India",
        headline="India now sends 1.34M students abroad",
        hero=dict(value="331,602", label="Indian students in the United States in 2024, "
                                         "more than triple the 2013 figure"),
        stats=[dict(n="1.34M", acc=True, l="Indians studying abroad, MEA 2024")],
        figure=dict(title="Indian students in the US, 2010–2024",
                    sub="IIE Open Doors annual enrolment",
                    chart=("line", [{"points": {2010: 104897, 2011: 103895, 2012: 100270,
                                                2013: 96754, 2014: 102673, 2015: 132888,
                                                2016: 165918, 2017: 186267, 2018: 196271,
                                                2019: 202014, 2020: 193124, 2021: 167582,
                                                2022: 199182, 2023: 268923, 2024: 331602},
                                     "color": card.NRA, "tip": "332K", "area": card.FILL}],
                           dict(pct=False)),
                    legend=[("Indian students in the US", card.NRA)]),
        footer="IIE Open Doors · IRCC · HESA · DHS SEVP · India MEA · NMC.")

    P["canada"] = dict(
        title="Canada's Million International Students",
        desc="Canada's study-permit stock reached 996,375 at the end of 2024 "
             "after peaking above a million in 2023.",
        eyebrow="IRCC Open Data", tag="Canada",
        headline="Canada hit a million international students",
        hero=dict(value="996,375", label="study-permit holders in Canada at the end "
                                         "of 2024, after peaking at 1.04M in 2023"),
        figure=dict(title="Study permit holders in Canada",
                    sub="Year-end stock, IRCC Open Data",
                    chart=("line", [{"points": {2010: 225260, 2011: 248445, 2012: 274680,
                                                2013: 301515, 2014: 330075, 2015: 352290,
                                                2016: 410540, 2017: 490735, 2018: 566915,
                                                2019: 637745, 2020: 527145, 2021: 616365,
                                                2022: 803580, 2023: 1037165, 2024: 996375},
                                     "color": card.NRA, "tip": "996K", "area": card.FILL}],
                           dict(pct=False)),
                    legend=[("Study permit holders", card.NRA)]),
        footer="IRCC / Statistics Canada Open Data — study permits, IMP work "
               "permits and Post-Graduation Work Permits.")

    P["uk"] = dict(
        title="The UK's International Student Peak",
        desc="UK international enrolment reached 732,285 in 2023/24, up 67% in "
             "eight years, with India and China supplying 43% of it.",
        eyebrow="HESA Student Statistics", tag="United Kingdom",
        headline="The UK’s 732K international student peak",
        hero=dict(value="732,285", label="international students enrolled in the UK "
                                         "in 2023/24, up 67% in eight years"),
        figure=dict(title="UK international enrolment, HESA",
                    sub="Academic years 2015/16 to 2023/24",
                    chart=("bar", {2016: 438000, 2017: 443320, 2018: 450480,
                                   2019: 469395, 2020: 496315, 2021: 554375,
                                   2022: 600180, 2023: 675200, 2024: 732285},
                           dict())),
        footer="HESA Student Statistics (enrolment) · UK Home Office Immigration "
               "System Statistics. Years shown are the ending year of each session.")

    P["eu"] = dict(
        title="Germany, Europe's Top Student Destination",
        desc="The EU hosts 1.76M international students and Germany leads with "
             "402,083, where India has now overtaken China as top source.",
        eyebrow="Destatis · DAAD", tag="EU & Germany",
        headline="Germany is Europe’s top student magnet",
        hero=dict(value="469,485", label="foreign students in Germany in 2023/24, "
                                         "up 55.7% over ten years"),
        stats=[dict(n="402,083", acc=True, l="international students, WS 2024/25")],
        figure=dict(title="Foreign students in Germany",
                    sub="Destatis via DAAD Wissenschaft weltoffen",
                    chart=("bar", {2014: 301350, 2016: 340305, 2017: 358895,
                                   2018: 374583, 2019: 394665, 2020: 411601,
                                   2021: 416437, 2022: 440564, 2023: 458210,
                                   2024: 469485}, dict())),
        footer="DAAD Wissenschaft weltoffen / Destatis · Eurostat learning mobility "
               "statistics · DHS SEVP. Years are the ending year of each winter semester.")

    P["mexico"] = dict(
        title="Mexico Barely Sends Students Abroad",
        desc="Only 36,922 Mexicans study abroad and 17,851 hold active US SEVIS "
             "records — flat mobility despite a doubled college-age population.",
        eyebrow="DHS SEVP · UNESCO UIS", tag="Mexico",
        headline="Mexico barely sends students abroad",
        hero=dict(value="17,851", label="active US SEVIS records held by Mexican "
                                        "students, March 2026"),
        figure=dict(title="Where Mexicans study abroad",
                    sub="Students by destination country",
                    chart=("hbar", [("Canada", 16980), ("United States", 15474),
                                    ("Spain", 5540), ("Australia", 3620)], dict())),
        footer="IIE Open Doors · DHS SEVP SEVIS (March 2026) · UNESCO UIS 2022.")

    P["vwp"] = dict(
        title="Visa Waiver Countries Overstay Five Times Less",
        desc="The 41 Visa Waiver Program countries overstay at 0.43% against "
             "2.22% for non-VWP countries, and take 69,200 naturalizations a year.",
        eyebrow="DHS OHSS", tag="Visa Waiver Program",
        headline="Visa waiver countries overstay 5x less",
        hero=dict(value="0.43", unit="%", label="VWP overstay rate, against 2.22% "
                                                "for non-VWP countries"),
        figure=dict(title="VWP naturalizations by year",
                    sub="All 41 Visa Waiver countries, FY2014–FY2023",
                    chart=("bar", {2014: 63510, 2015: 67550, 2016: 66860, 2017: 62530,
                                   2018: 69800, 2019: 75830, 2020: 54300, 2021: 73400,
                                   2022: 80680, 2023: 69200}, dict())),
        footer="DHS OHSS Yearbook 2023 (Table 21) · DHS Entry/Exit Overstay Reports "
               "· SEVP SEVIS.")

    P["immigration"] = dict(
        title="From Student Visa to Green Card, by School",
        desc="H-1B, OPT, LCA and PERM records for 101 US research universities, "
             "showing how each campus feeds the employment-immigration pipeline.",
        eyebrow="ICE/SEVP · USCIS · DOL", tag="101 universities",
        headline="From student visa to green card, by school",
        hero=dict(value="101", label="US research universities with H-1B, OPT, LCA "
                                     "and PERM records matched to them"),
        figure=dict(title="OPT students employed in 2024",
                    sub="Largest programmes among tracked universities",
                    chart=("hbar", [("Columbia", 6359), ("U North Texas", 5241),
                                    ("UT Dallas", 4483), ("UT Arlington", 3635)], dict())),
        footer="ICE/SEVP OPT (CY2017–2024) · USCIS H-1B Employer Data Hub "
               "(FY2010–2026) · DOL LCA and PERM disclosure data.")

    P["workforce"] = dict(
        title="The Foreign-Born US Doctoral STEM Workforce",
        desc="NSF Survey of Doctorate Recipients 2023: 38.1% of the 908,700-strong "
             "US doctoral workforce is foreign-born, rising to 70.5% in ECE.",
        eyebrow="NSF Survey of Doctorate Recipients", tag="2023",
        headline="38% of US PhD scientists are foreign-born",
        hero=dict(value="38.1", unit="%", label="of the 908,700-strong US doctoral "
                                                "workforce is foreign-born"),
        figure=dict(title="Foreign-born share by field",
                    sub="NSF SDR 2023, doctoral workforce",
                    chart=("hbar", [("Electrical & Computer Eng", 70.5),
                                    ("Computer Science", 65.1),
                                    ("Engineering (all)", 59.9),
                                    ("All fields", 38.1)], dict(unit="%"))),
        footer="NSF Survey of Doctorate Recipients 2023, Table 9 · NSB 2026 Science "
               "& Engineering Indicators, Table STAL-12.")

    # --- project / methodology pages ---------------------------------------

    P["about"] = dict(
        title="About PhD Demographics",
        desc="What this project tracks, where every figure comes from, and how to "
             "send a correction or a new source.",
        eyebrow="About the project", tag="Method and sources",
        headline="Who actually gets American PhDs",
        hero=dict(value="430,000", label="thesis and dissertation records scraped from "
                                         "101 university repositories, 2016–2024"),
        figure=dict(title="What the project holds",
                    sub="Records, institutions and years of federal data",
                    chart=("hbar", [("Thesis records", 430000),
                                    ("US universities", 101),
                                    ("Years of IPEDS completions", 41)], dict())),
        footer="University repositories, IPEDS, ICE/SEVP, USCIS, DOL, NSF HERD and "
               "NIH RePORTER — all official government open data.")

    P["data_sources"] = dict(
        title="Data Sources & Methodology",
        desc="Every federal and repository source behind the site, how citizenship "
             "categories differ between surveys, and the known limitations.",
        eyebrow="Methodology", tag="Seven federal datasets",
        headline="What “domestic” actually means in the data",
        hero=dict(value="63.5", unit="%", label="of US doctorate holders are native-born "
                                                "citizens — the rest of “domestic” is not"),
        figure=dict(title="Who “domestic” PhDs really are",
                    sub="NSF Survey of Doctorate Recipients 2023, 80,143 respondents",
                    chart=("hbar", [("Native-born citizens", 63.5),
                                    ("Naturalized citizens", 17.9),
                                    ("Permanent residents", 7.0),
                                    ("Temporary visa", 3.1)], dict(unit="%"))),
        footer="IPEDS/NCES · NSF NCSES (SED, GSS, SDR, NSCG, HERD) · ICE/SEVP SEVIS "
               "· DOL OFLC · USAspending · Census ACS.")

    P["implementation"] = dict(
        title="How the Pipeline Is Built",
        desc="The six-step functional pipeline that harvests, classifies, enriches "
             "and deploys thesis metadata from 101 university repositories.",
        eyebrow="Technical implementation", tag="6-step pipeline",
        headline="A six-step pipeline over 101 repositories",
        hero=dict(value="294K", label="thesis records harvested from 101 institutional "
                                      "repositories across 10 platforms"),
        figure=dict(title="Federal coverage by dataset",
                    sub="Universities matched in each federal source",
                    chart=("hbar", [("H-1B (USCIS)", 98), ("LCA (DOL)", 78),
                                    ("PERM (DOL)", 72), ("OPT (SEVIS)", 59)], dict())),
        footer="Pipeline steps 1–6: OAI-PMH harvest, USCIS H-1B Data Hub, DOL LCA and "
               "PERM, ICE SEVIS, IPEDS, NSF HERD and GSS.")

    P["query"] = dict(
        title="Query the Dissertation Data with SQL",
        desc="An in-browser SQL workspace over the project's STEM and non-STEM "
             "thesis Parquet exports — no server, no account.",
        eyebrow="In-browser SQL", tag="Parquet exports",
        headline="Run SQL on 427K dissertation records",
        hero=dict(value="427K", label="dissertation records queryable in the browser "
                                      "across two Parquet tables"),
        figure=dict(title="Queryable Parquet tables",
                    sub="Loaded and queried entirely in the browser",
                    chart=("hbar", [("STEM records", 291000),
                                    ("Non-STEM records", 136000)], dict())),
        footer="Pipeline Parquet exports queried in-browser with Squirreling and "
               "hyparquet. Nothing is uploaded — the query runs on your machine.")

    P["submit"] = dict(
        title="Tip Line: Send Links and Corrections",
        desc="Send missing department directories, data corrections, new federal "
             "sources or bug reports straight to the maintainer.",
        eyebrow="Tip line", tag="Corrections welcome",
        headline="Send a link, a correction, or a bug",
        hero=dict(value="5,000", label="characters per message, rate-limited to three "
                                       "submissions per ten minutes"),
        figure=dict(title="What is most useful",
                    sub="The kinds of tips the project acts on",
                    chart=("hbar", [("Department directory links", 1),
                                    ("Data corrections", 1),
                                    ("New datasets or sources", 1),
                                    ("Bugs and analysis ideas", 1)], dict())),
        footer="Messages go directly to the maintainer’s inbox. No tracking, no "
               "third-party services, rate-limited per IP.")

    P["webmcp"] = dict(
        title="WebMCP Tools for AI Agents",
        desc="The WebMCP tools and plain-HTTP endpoints that let AI agents query "
             "this site's university, thesis and taxonomy data as JSON.",
        eyebrow="WebMCP", tag="Agent interface",
        headline="Five WebMCP tools for AI agents",
        hero=dict(value="5", label="WebMCP tools registered for AI agents, alongside "
                                   "six plain-HTTP JSON endpoints"),
        figure=dict(title="Agent surface area",
                    sub="Tools, endpoints and schema exposed to agents",
                    chart=("hbar", [("Department taxonomy categories", 44),
                                    ("Record fields per row", 8),
                                    ("HTTP JSON endpoints", 6),
                                    ("WebMCP tools", 5)], dict())),
        footer="WebMCP via navigator.modelContext.registerTool(), W3C draft spec. "
               "Data v1.0.0.")

    # --- Caltech case-study pages ------------------------------------------

    P["caltech_dashboard"] = dict(
        title="Caltech PhD Demographics, 1911–2026",
        desc="Name-based classification of 10,732 Caltech doctoral dissertations, "
             "charting Chinese-origin share by year, era, degree type and field.",
        eyebrow="CaltechTHESIS", tag="Name classification",
        headline="One in three Caltech PhDs in 2024",
        hero=dict(value="32.7", unit="%", label="of Caltech PhDs in 2024 carried "
                                                "Chinese-origin names — the highest year on record"),
        stats=[dict(n="10,732", l="dissertations classified, 1911–2026")],
        figure=dict(title="Chinese share of Caltech PhDs",
                    sub="Name-based classification of CaltechTHESIS records",
                    chart=("line", [{"points": {2010: 12.4, 2011: 9.5, 2012: 18.7,
                                                2013: 14.5, 2014: 15.5, 2015: 15.4,
                                                2016: 18.4, 2017: 21.1, 2018: 17.3,
                                                2019: 20.8, 2020: 19.0, 2021: 25.1,
                                                2022: 21.6, 2023: 25.4, 2024: 32.7,
                                                2025: 23.5},
                                     "color": card.NRA, "tip": "23.5%", "area": card.FILL}],
                           dict())),
        footer="CaltechTHESIS dissertation records with name-based origin "
               "classification. Names indicate likely origin, not citizenship.")

    P["caltech_field_demographics"] = dict(
        title="STEM PhD Demographics by Field and University",
        desc="An IPEDS explorer comparing race, ethnicity and international share "
             "of STEM doctorates across 17 West Coast universities by field.",
        eyebrow="IPEDS Completions", tag="2015–2024",
        headline="Half of UC engineering PhDs are foreign",
        hero=dict(value="32.7", unit="%", label="of the University of California’s "
                                                "27,596 STEM doctorates went to non-residents"),
        figure=dict(title="NRA share by STEM field",
                    sub="University of California, all campuses, 2015–2024",
                    chart=("hbar", [("Computer Science", 57.2), ("Engineering", 51.4),
                                    ("Math / Statistics", 41.1),
                                    ("Physical Sciences", 25.6)], dict(unit="%"))),
        footer=SOURCE_IPEDS)

    P["caltech_ipeds_tables"] = dict(
        title="17 Universities Ranked by Foreign PhD Share",
        desc="Printable IPEDS tables giving the full race and ethnicity breakdown "
             "of STEM doctorates by field for 17 West Coast universities.",
        eyebrow="IPEDS Completions", tag="2015–2024",
        headline="17 universities, ranked by foreign PhD share",
        hero=dict(value="46.7", unit="%", label="of Washington State’s STEM doctorates "
                                                "went to non-residents — the highest of the 17"),
        figure=dict(title="Foreign share of STEM doctorates",
                    sub="Selected universities, IPEDS research doctorates 2015–2024",
                    chart=("hbar", [("Washington State", 46.7), ("Caltech", 41.7),
                                    ("UCLA", 37.6), ("U Oregon", 11.1)], dict(unit="%"))),
        footer=SOURCE_IPEDS)

    # --- dashboards and analysis pages -------------------------------------

    P["medical"] = dict(
        title="US Medicine's Hard Cap on Seats",
        desc="54,699 applicants chase 23,440 MD matriculant seats while J-1 foreign "
             "physicians in US residency training rose 76% in a decade.",
        eyebrow="AAMC FACTS", tag="Medical pipeline",
        headline="US medicine’s hard cap: 23,440 seats",
        hero=dict(value="100,723", label="students enrolled in US MD schools in 2025 — "
                                         "past 100,000 for the first time"),
        stats=[dict(n="23,440", acc=True, l="matriculant seats for 54,699 applicants")],
        figure=dict(title="US MD school enrollment, 2010–2025",
                    sub="Total enrollment crossed 100,000 in 2025",
                    chart=("line", [{"points": {2010: 78741, 2011: 80204, 2012: 81932,
                                                2013: 83351, 2014: 85122, 2015: 86584,
                                                2016: 88181, 2017: 89729, 2018: 91218,
                                                2019: 92621, 2020: 94064, 2021: 95334,
                                                2022: 96376, 2023: 97772, 2024: 99454,
                                                2025: 100723},
                                     "color": card.NRA, "tip": "101K", "area": card.FILL}],
                           dict(pct=False)),
                    legend=[("Total MD enrollment", card.NRA)]),
        footer="AAMC FACTS — applicants, matriculants, enrollment and graduates of US "
               "MD-granting medical schools · Intealth EVSP · NRMP.")

    P["usaid"] = dict(
        title="US Government Scholarships and Exchange Programs",
        desc="Of 1.18M international students in the US, roughly 2% receive US "
             "government funding; most are self- or family-funded.",
        eyebrow="State Dept ECA · USAID", tag="Exchange programmes",
        headline="Only about 2% of foreign students get US aid",
        hero=dict(value="~2", unit="%", label="of the 1.18M international students in "
                                              "the US receive US government funding"),
        figure=dict(title="Major US government exchange programmes",
                    sub="Annual participants or grants",
                    chart=("hbar", [("Fulbright", 8000), ("IVLP", 4000),
                                    ("USAID partnerships", 2000),
                                    ("Cochran", 500)], dict())),
        footer="IIE Open Doors funding-source data · State Dept ECA · USAID · USDA "
               "programme figures · ForeignAssistance.gov. Programme counts are approximate.")

    P["ipeds_dashboard"] = dict(
        title="41 Years of US STEM Doctorates",
        desc="Every STEM and clinical research doctorate reported to IPEDS from 1984 "
             "to 2024 — 849 institutions, by field, race, gender and state.",
        eyebrow="IPEDS Completions", tag="1984–2024",
        headline="41 years of US STEM doctorates",
        hero=dict(value="49,012", label="STEM research doctorates awarded in 2024, "
                                        "up 50% since 2010"),
        stats=[dict(n="849", l="institutions covered")],
        figure=dict(title="National STEM doctorate completions",
                    sub="IPEDS research doctorates in STEM and clinical fields",
                    chart=("bar", {2010: 32743, 2011: 34257, 2012: 35500, 2013: 37308,
                                   2014: 39272, 2015: 39507, 2016: 40148, 2017: 40866,
                                   2018: 42252, 2019: 42937, 2020: 43293, 2021: 42533,
                                   2022: 46400, 2023: 47779, 2024: 49012}, dict())),
        footer="IPEDS Completions Survey (NCES) — research doctorates in STEM and "
               "clinical fields, 1984–2024.")

    P["stem_dashboard"] = dict(
        title="Name Origins Across 438K STEM Records",
        desc="Surname-based origin classification of 438,353 STEM dissertation "
             "records: 52,149 Chinese-origin names and 14,236 Indian.",
        eyebrow="Name classification", tag="438,353 records",
        headline="Name origins across 438K STEM records",
        hero=dict(value="52,149", label="Chinese-origin surnames among 438,353 STEM "
                                        "dissertation records — 11.9% of the total"),
        figure=dict(title="Chinese-origin share of STEM records",
                    sub="By dissertation year, 2015–2025",
                    chart=("line", [{"points": {2015: 11.6, 2016: 13.9, 2017: 14.0,
                                                2018: 13.3, 2019: 14.7, 2020: 14.2,
                                                2021: 14.7, 2022: 14.1, 2023: 12.4,
                                                2024: 14.4, 2025: 13.8},
                                     "color": card.NRA, "tip": "13.8%", "area": card.FILL}],
                           dict())),
        footer="Name-origin classification of university dissertation repository "
               "records. Surnames indicate likely origin, not citizenship.")

    P["department_reports"] = dict(
        title="Name Origins, Department by Department",
        desc="46,514 dissertation records at nine high-NRA universities, broken out "
             "by department and surname origin.",
        eyebrow="Department-level classification", tag="9 universities",
        headline="Name origins, department by department",
        hero=dict(value="73.2", unit="%", label="non-resident share at Missouri S&T, the "
                                                "highest of the nine universities tracked"),
        figure=dict(title="Chinese-origin share of records",
                    sub="Across all departments at the nine tracked universities",
                    chart=("line", [{"points": {2010: 12.5, 2011: 13.2, 2012: 15.4,
                                                2013: 13.7, 2014: 15.6, 2015: 16.8,
                                                2016: 16.9, 2017: 17.1, 2018: 15.5,
                                                2019: 17.1, 2020: 12.6, 2021: 17.1,
                                                2022: 14.5, 2023: 13.4, 2024: 11.7,
                                                2025: 8.7},
                                     "color": card.NRA, "tip": "8.7%", "area": card.FILL}],
                           dict())),
        footer="Surname-origin classification of dissertation records; NRA share from "
               "IPEDS Completions 2015–2024. Surnames indicate likely origin, not citizenship.")

    P["pipeline"] = dict(
        title="F-1 to Green Card: Where the Funnel Narrows",
        desc="The cross-dataset funnel from student visa to doctorate to OPT to H-1B: "
             "India has 350K students in SEVIS but 2,649 PhDs a year.",
        eyebrow="SEVIS · NSF SED · USCIS", tag="Immigration funnel",
        headline="F-1 to green card: where the funnel narrows",
        hero=dict(value="350,237", label="Indian students in SEVIS, of whom 2,649 earn "
                                         "a US doctorate — China earns 6,756"),
        figure=dict(title="STEM-OPT growth, 2010 = 100",
                    sub="STEM-OPT is up tenfold while F-1 issuance is flat",
                    chart=("line", [{"points": {2010: 100, 2011: 144, 2012: 170,
                                                2013: 201, 2014: 229, 2015: 294,
                                                2016: 447, 2017: 689, 2018: 744,
                                                2019: 771, 2020: 683, 2021: 658,
                                                2022: 693, 2023: 663, 2024: 1020},
                                     "color": card.NRA, "tip": "1020", "area": card.FILL}],
                           dict(pct=False)),
                    legend=[("STEM-OPT, indexed to 2010", card.NRA)]),
        footer="SEVP SEVIS · State Dept visa statistics · NSF SED · USCIS H-1B data · "
               "State Dept Table V (EB visas, FY2024).")

    P["quality"] = dict(
        title="Data Quality Scorecard",
        desc="The per-university QA audit: 82.7% of 455,524 harvested records carry a "
             "degree label, and 60 of 101 universities have a flagged issue.",
        eyebrow="QA scorecard", tag="101 universities",
        headline="455,524 records, audited school by school",
        hero=dict(value="82.7", unit="%", label="of 455,524 harvested records carry a "
                                                "degree label; 78,666 do not"),
        figure=dict(title="Department link coverage by type",
                    sub="Share of 5,549 department entries with each link populated",
                    chart=("hbar", [("Repository search", 97.9),
                                    ("Department homepage", 27.2),
                                    ("Faculty directory", 21.7),
                                    ("Students directory", 12.1)], dict(unit="%"))),
        footer="Generated by scripts/qa_report.py over the 101 tracked university "
               "repositories.")

    return P


# ---------------------------------------------------------------------------
# university cards
# ---------------------------------------------------------------------------

MIN_COHORT = 40  # below this, a percentage is noise — use the records card


def top_departments(uni, n=4):
    counts = {}
    for r in uni.get("records", []):
        d = (r[0] or "").strip() if r else ""
        if d:
            counts[d] = counts.get(d, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])[:n]


def uni_spec(key, mode, uni, nat, stem_idx):
    """Card spec for one university page.

    STEM cards are built on the pinned basis from scripts/compute_nra_shares.py
    (CIP families 11/14/15/26/27/30/40/42, award level 17), so the hero figure
    IS the share published on the page — verified identical for 103 of the 105
    registered universities — and the school line and the national line in the
    chart are computed the same way as each other.

    Non-STEM cards stay on the complement of the broad 16-family set, which is
    what "non-STEM" means on this site.
    """
    name = uni.get("name", key)
    n_records = len(uni.get("records", []))
    label = "STEM" if mode == "stem" else "non-STEM"
    Label = "STEM" if mode == "stem" else "Non-STEM"

    if mode == "stem":
        e = stem_idx.get(key) or {}
        pooled, cohort = e.get("pooled"), e.get("cohort", 0)
        share = {y: v for y, v in (e.get("share") or {}).items() if y >= 2010}
        window = f"{data.PINNED_YEARS[0]}\u2013{data.PINNED_YEARS[1]}"
        natpoints = nat["stem"]
    else:
        share, pooled, cohort = data.uni_series(uni, mode)
        share = {y: v for y, v in share.items() if y >= 2010}
        yrs_all = sorted(share)
        window = f"{yrs_all[0]}\u2013{yrs_all[-1]}" if yrs_all else ""
        natpoints = nat["nonstem"]

    stats = [dict(n=f"{n_records:,}", l="thesis records tracked")]
    enr = (uni.get("enrollment_ipeds") or {}).get("nra_pct")
    if enr:
        stats.append(dict(n=f"{enr}%", acc=True, l="non-resident graduate enrollment"))

    if pooled is not None and cohort >= MIN_COHORT and len(share) >= 6:
        yrs = sorted(share)
        base = {y: natpoints[y] for y in yrs if y in natpoints}
        last = share[yrs[-1]]
        return dict(
            title=f"{name} \u2014 {Label} doctorate demographics",
            desc=(f"{name}: non-residents took {pooled}% of its {label} research "
                  f"doctorates over {window} ({cohort:,} doctorates), against "
                  f"{natpoints[yrs[-1]]}% nationally."),
            eyebrow="IPEDS Completions", tag=f"{Label} \u00b7 {name}",
            headline=name,
            hero=dict(value=f"{pooled}", unit="%",
                      label=f"of its {label} research doctorates went to "
                            f"non-resident students, {window}"),
            stats=stats,
            figure=dict(title=f"NRA share of {label} doctorates",
                        sub=f"{name} against the national {label} average, "
                            f"{yrs[0]}\u2013{yrs[-1]}",
                        chart=("line", [
                            {"points": base, "color": card.BASE, "dash": "6 5", "width": 2.6},
                            {"points": share, "color": card.NRA, "tip": f"{last}%",
                             "area": card.FILL},
                        ], dict(years=yrs)),
                        legend=[(name, card.NRA), (f"National {label}", card.BASE)]),
            footer=SOURCE_IPEDS)

    # Fallback: too few doctorates for a percentage to mean anything, or — for
    # the two institutions with no unitid in the registry (cuny, mines) — a
    # stored headline share that could not be recomputed and so cannot be
    # stood behind. Build the card on the repository records instead and print
    # no percentage at all.
    depts = top_departments(uni)
    return dict(
        title=f"{name} \u2014 {Label} theses and dissertations",
        desc=(f"{name}: {n_records:,} {label} thesis and dissertation records, "
              f"each linked to the university's own institutional repository."),
        eyebrow="Institutional repository", tag=f"{Label} \u00b7 {name}",
        headline=name,
        hero=dict(value=f"{n_records:,}",
                  label=f"{label} thesis and dissertation records, each "
                        f"linked to its source repository"),
        stats=[s for s in stats[1:]],
        figure=dict(title="Largest departments by records",
                    sub=f"{name} \u00b7 institutional repository",
                    chart=("hbar", depts, dict())) if depts else {},
        footer=f"{name} institutional repository, enriched with IPEDS, NSF, DOL, "
               f"DHS and State Department federal data.")


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def make_svg(figure):
    kind, payload, opts = figure["chart"]
    if kind == "line":
        return card.line_chart(payload, aria=figure.get("title", ""), **opts)
    if kind == "bar":
        return card.bar_chart(payload, aria=figure.get("title", ""), **opts)
    if kind == "hbar":
        return card.hbar_chart(payload, aria=figure.get("title", ""), **opts)
    raise ValueError(kind)


def spec_to_html(spec, font_css):
    fig = dict(spec.get("figure") or {})
    if fig.get("chart"):
        fig["svg"] = make_svg(fig)
    return card.render(dict(spec, figure=fig), font_css)


# ---------------------------------------------------------------------------
# meta tags
# ---------------------------------------------------------------------------

# The block itself lives in scripts/og/tags.py so that the page generators
# (build_static_pages.py, generate_name_lists_html.py) emit exactly the same
# markup without importing this script.
wire_tags = tags.wire_file


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def collect(args):
    """Return [(card_name, rel_png, page_path, page_url, spec)] for every card."""
    nat = data.national_series()
    stem_idx = data.uni_stem_index()
    jobs = []

    page_specs = build_page_specs(nat)
    for name, spec in page_specs.items():
        p = SITE / f"{name}.html"
        if not p.exists():
            print(f"  ! no page for {name}.html")
            continue
        rel = tags.card_rel_for_page(f"{name}.html")
        jobs.append((name, rel, p, f"{DOMAIN}/{name}.html", spec))

    if not args.pages:
        for mode in ("stem", "nonstem"):
            sub = "" if mode == "stem" else "nonstem/"
            for key in data.uni_keys(mode):
                uni = data.load_uni(key, mode)
                if not uni:
                    continue
                spec = uni_spec(key, mode, uni, nat, stem_idx)
                rel_page = f"universities/{sub}{key}.html"
                jobs.append((f"{sub}{key}", tags.card_rel_for_page(rel_page),
                             SITE / rel_page, f"{DOMAIN}/{rel_page}", spec))

    if args.only:
        want = {s.strip() for s in args.only.split(",")}
        jobs = [j for j in jobs if j[0] in want or Path(j[1]).stem in want]
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated card names to build")
    ap.add_argument("--pages", action="store_true", help="top-level pages only")
    ap.add_argument("--no-tags", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args()

    print("Collecting card specs...")
    jobs = collect(args)
    print(f"  {len(jobs)} cards")

    if not args.no_render:
        print("Loading fonts...")
        font_css = fonts.font_css()
        tmp = Path(tempfile.mkdtemp(prefix="ogcards-"))
        shots = []
        try:
            for name, rel, _page, _url, spec in jobs:
                html_path = tmp / (rel.replace("/", "__") + ".html")
                html_path.write_text(spec_to_html(spec, font_css))
                out = SITE / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shots.append((str(html_path), str(out)))
            print(f"Rendering {len(shots)} cards at {card.W}x{card.H}...")
            ok, fails = shoot.shoot_all(shots, workers=args.workers or None)
            print(f"  {ok} rendered, {len(fails)} failed")
            for png, err in fails[:5]:
                print(f"  FAIL {png}: {err[:200]}")
            if fails:
                sys.exit(1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if not args.no_tags:
        print("Wiring meta tags...")
        n = 0
        for name, rel, page_path, page_url, spec in jobs:
            if not page_path.exists():
                continue
            alt = f"{spec['headline']} — {spec.get('figure',{}).get('title','PhD Demographics')}"
            if wire_tags(page_path, spec["title"], spec["desc"],
                         tags.card_url(rel), page_url, alt,
                         spec.get("og_type", "website")):
                n += 1
        print(f"  {n} pages updated")

    total = sum(p.stat().st_size for p in OG_DIR.rglob("*.png")) if OG_DIR.exists() else 0
    print(f"site/og/ now holds {len(list(OG_DIR.rglob('*.png')))} PNGs, "
          f"{total/1_048_576:.1f} MiB")


if __name__ == "__main__":
    main()
