#!/usr/bin/env python3
"""Who public bodies sponsored for a green card, and where they were from.

WHAT THIS ANSWERS THAT NOTHING ELSE CAN

The H-1B record says what the job was. It never says who filled it: the LCA's
98 columns name the employer's country, its contact's and its attorney's, and
no one else's. The permanent-labor-certification file is different. Every row
carries the employer, the job title, the worksite, the wage -- and the
worker's COUNTRY OF CITIZENSHIP, their country of birth, and the visa class
they held at the time.

So this is the only end-to-end view there is: a named public employer, a named
job, and the nationality of the person it was filed for.

THE WINDOW IS TWELVE YEARS AND IT IS CLOSED. Citizenship appears in FY2013 and
is gone from FY2025, when the form was redesigned and every worker field was
removed at once -- 155 columns to 137. Birth country runs FY2015 to FY2024.
Nothing published after FY2024 will ever carry either. This is not a gap in
the data; it is a series that ended.

WHAT A ROW IS, AND IS NOT

A PERM certification is an employer asking to sponsor someone for permanent
residence, after testing the local labor market. It is not a hire, not an
admission, and not an H-1B petition. Many of these workers were already in the
job on another visa -- CLASS_OF_ADMISSION says which. A public body appearing
here sponsored somebody; it does not follow that the post could not be filled
by an American, only that the employer filed to say so.

No worker is named in this file and none is named here. Employer, job title,
worksite, citizenship: all of it is published disclosure.

THREE PUBLIC SECTORS, kept apart because they are different arguments:
state agencies, public universities and colleges, and school districts.

Output: site/data/public_employer_perm.json

Usage:
    python3 scripts/build_public_employer_perm.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERM = ROOT / "data" / "h1b" / "perm"
EXTRA = (ROOT / "data" / "h1b" / "perm_fy2024_q4.xlsx",)
OUT = ROOT / "site" / "data" / "public_employer_perm.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

#: Every spelling, across the 27 / 125 / 154-column eras.
NEED = {
    "CASE_STATUS": ("CASE_STATUS", "STATUS"),
    "DECISION_DATE": ("DECISION_DATE",),
    "EMPLOYER_NAME": ("EMPLOYER_NAME",),
    "CITIZENSHIP": ("COUNTRY_OF_CITIZENSHIP",),
    "BIRTH_COUNTRY": ("FOREIGN_WORKER_BIRTH_COUNTRY", "FW_INFO_BIRTH_COUNTRY"),
    "CLASS_OF_ADMISSION": ("CLASS_OF_ADMISSION",),
    "JOB_TITLE": ("JOB_TITLE", "JOB_INFO_JOB_TITLE", "PW_JOB_TITLE_9089"),
    "WORK_STATE": ("WORKSITE_STATE", "JOB_INFO_WORK_STATE"),
    "WORK_CITY": ("WORKSITE_CITY", "JOB_INFO_WORK_CITY"),
    "WAGE_FROM": ("WAGE_OFFER_FROM_9089", "WAGE_OFFERED_FROM_9089",
                  "OFFERED_WAGE", "WAGE_OFFER_FROM"),
    "WAGE_UNIT": ("WAGE_OFFER_UNIT_OF_PAY_9089", "WAGE_OFFERED_UNIT_OF_PAY_9089",
                  "OFFERED_WAGE_UNIT", "WAGE_OFFER_UNIT_OF_PAY"),
    "CASE_NUMBER": ("CASE_NUMBER",),
    #: Five spellings across the archive, as everywhere else in these files.
    "NAICS": ("EMP_NAICS", "NAICS_CODE", "NAICS_US_CODE",
              "2007_NAICS_US_CODE", "2007 NAICS US CODE"),
}
REQUIRED = ("CASE_STATUS", "EMPLOYER_NAME", "CITIZENSHIP")

STATES = {
    "ALABAMA", "ALASKA", "ARIZONA", "ARKANSAS", "CALIFORNIA", "COLORADO",
    "CONNECTICUT", "DELAWARE", "FLORIDA", "GEORGIA", "HAWAII", "IDAHO",
    "ILLINOIS", "INDIANA", "IOWA", "KANSAS", "KENTUCKY", "LOUISIANA", "MAINE",
    "MARYLAND", "MASSACHUSETTS", "MICHIGAN", "MINNESOTA", "MISSISSIPPI",
    "MISSOURI", "MONTANA", "NEBRASKA", "NEVADA", "NEW HAMPSHIRE", "NEW JERSEY",
    "NEW MEXICO", "NEW YORK", "NORTH CAROLINA", "NORTH DAKOTA", "OHIO",
    "OKLAHOMA", "OREGON", "PENNSYLVANIA", "RHODE ISLAND", "SOUTH CAROLINA",
    "SOUTH DAKOTA", "TENNESSEE", "TEXAS", "UTAH", "VERMONT", "VIRGINIA",
    "WASHINGTON", "WEST VIRGINIA", "WISCONSIN", "WYOMING",
}
GOV = (r"(?:DEPT|DEPARTMENT|OFFICE|DIVISION|BUREAU|COMMISSION|BOARD|AGENCY|"
       r"PATROL|POLICE|AUTHORITY|ADMINISTRATION)")
AGENCY = re.compile(r"^(?:STATE OF\s+|COMMONWEALTH OF\s+)?(" +
                    "|".join(sorted(STATES, key=len, reverse=True)) +
                    r")\s+(?:STATE\s+)?" + GOV + r"\b")
UNIVERSITY = re.compile(r"\b(UNIVERSITY|UNIV\b|COLLEGE|INSTITUTE OF TECHNOLOGY|"
                        r"POLYTECHNIC|COMMUNITY COLLEGE)\b")
#: "ACADEMY" is how a great many charter and private schools name themselves --
#: LISA ACADEMY, YINGHUA ACADEMY, SEJONG ACADEMY OF MINNESOTA are all real
#: schools filing real cases -- so the word stays in the school test.
#:
#: The first attempt at this inverted the burden of proof: it demanded that an
#: ACADEMY prove it was a school by also carrying CHARTER or PREPARATORY in its
#: name. That removed 1,224 filings by 567 employers to exclude the 23 filed by
#: ACADEMY, LTD. D/B/A ACADEMY SPORTS AND OUTDOORS, a sporting-goods retailer.
#: Fixing a handful of false positives by creating a thousand false negatives is
#: the worse trade, and a classifier that silently drops real rows is exactly
#: the failure this repo's rule about missing columns is written against.
#:
#: So the test is broad and the exclusions are named. Each entry below is a
#: business that uses the word "academy" for something that is not a school:
#: a retailer, a dojo, a salon, a driving range. The list is explicit because
#: an explicit list can be audited and a clever rule cannot.
#: The additions below came from scanning one year for employers that look
#: public and land in no sector. SAVANNAH-CHATHAM COUNTY PUBLIC SCHOOL SYSTEM
#: alone filed 108 times in FY2023 and was missed, because the pattern had
#: "PUBLIC SCHOOLS" and the district calls itself a PUBLIC SCHOOL SYSTEM.
#: New York City files as a DEPARTMENT OF EDUCATION, not a board.
SCHOOL = re.compile(r"\b(SCHOOL DISTRICT|PUBLIC SCHOOLS?\s+SYSTEM|"
                    r"PUBLIC SCHOOLS|UNIFIED SCHOOL|MUNICIPAL SCHOOLS?|"
                    r"BOARD OF EDUCATION|BOARD OF SCHOOL|"
                    r"DEPARTMENT OF EDUCATION|DEPT OF EDUCATION|"
                    r"COUNTY SCHOOLS?|CITY SCHOOLS?|COMMUNITY SCHOOLS?|"
                    r"INDEPENDENT SCHOOL|CHARTER SCHOOL|HIGH SCHOOL|"
                    r"MIDDLE SCHOOL|ELEMENTARY SCHOOL|PREPARATORY SCHOOL|"
                    r"ACADEMY|MONTESSORI)\b")

NOT_A_SCHOOL = re.compile(
    r"ACADEMY,?\s*(LTD|LLC|INC)\.?\s*D/?B/?A\s*ACADEMY SPORTS"
    r"|SPORTS AND OUTDOORS|SPORTS & OUTDOORS"
    r"|MARTIAL ART|TAEKWONDO|TAE KWON|KARATE|\bJUDO\b|JIU[\s-]?JITSU|BOXING"
    r"|\bTENNIS\b|\bGOLF\b|\bSOCCER\b|\bFUTSAL\b|\bBASEBALL\b"
    r"|\bBASKETBALL\b|\bHOCKEY\b|\bGYMNASTIC"
    r"|\bBEAUTY\b|COSMETOLOG|\bBARBER|\bMASSAGE\b|\bNAIL\b"
    r"|\bDRIVING\b|\bTRUCK|\bFLIGHT\b|\bAVIATION\b|\bAIR ACADEMY\b"
    r"|KHAN ACADEMY|\bDANCE\b|\bYOGA\b|\bFITNESS\b")


#: THE WORKSITE STATE IS SPELLED TWO WAYS AND BOTH ARE IN THE DATA.
#:
#: The older files write "MONTANA" and the newer ones write "MT". Left alone,
#: every state appears twice and each copy carries about half its filings --
#: Montana came out as 36 under one spelling and 36 under the other, and a
#: page built on that would have understated every state by roughly half.
#:
#: This is the same failure as the header drift this repo already guards
#: against, one level down: not a column that changed name, but a value. The
#: rule is the same. Read through a known list and FAIL on a value that is not
#: in it, because a silently unmatched state is a state missing from the
#: totals and nobody will notice.
STATE_NAMES = {
    "AL": "ALABAMA", "AK": "ALASKA", "AZ": "ARIZONA", "AR": "ARKANSAS",
    "CA": "CALIFORNIA", "CO": "COLORADO", "CT": "CONNECTICUT",
    "DE": "DELAWARE", "DC": "DISTRICT OF COLUMBIA", "FL": "FLORIDA",
    "GA": "GEORGIA", "HI": "HAWAII", "ID": "IDAHO", "IL": "ILLINOIS",
    "IN": "INDIANA", "IA": "IOWA", "KS": "KANSAS", "KY": "KENTUCKY",
    "LA": "LOUISIANA", "ME": "MAINE", "MD": "MARYLAND",
    "MA": "MASSACHUSETTS", "MI": "MICHIGAN", "MN": "MINNESOTA",
    "MS": "MISSISSIPPI", "MO": "MISSOURI", "MT": "MONTANA",
    "NE": "NEBRASKA", "NV": "NEVADA", "NH": "NEW HAMPSHIRE",
    "NJ": "NEW JERSEY", "NM": "NEW MEXICO", "NY": "NEW YORK",
    "NC": "NORTH CAROLINA", "ND": "NORTH DAKOTA", "OH": "OHIO",
    "OK": "OKLAHOMA", "OR": "OREGON", "PA": "PENNSYLVANIA",
    "RI": "RHODE ISLAND", "SC": "SOUTH CAROLINA", "SD": "SOUTH DAKOTA",
    "TN": "TENNESSEE", "TX": "TEXAS", "UT": "UTAH", "VT": "VERMONT",
    "VA": "VIRGINIA", "WA": "WASHINGTON", "WV": "WEST VIRGINIA",
    "WI": "WISCONSIN", "WY": "WYOMING",
    "PR": "PUERTO RICO", "GU": "GUAM", "VI": "VIRGIN ISLANDS",
    "MP": "NORTHERN MARIANA ISLANDS", "AS": "AMERICAN SAMOA",
    #: The freely associated states. A US employer can file from them and a
    #: handful do; without these the build stops dead, which is how they were
    #: found.
    "MH": "MARSHALL ISLANDS", "FM": "MICRONESIA", "PW": "PALAU",
}
#: Spellings the files use that are not simply the name or the code.
STATE_ALIASES = {
    "WASHINGTON DC": "DISTRICT OF COLUMBIA",
    "WASHINGTON, DC": "DISTRICT OF COLUMBIA",
    "D.C.": "DISTRICT OF COLUMBIA",
    "U.S. VIRGIN ISLANDS": "VIRGIN ISLANDS",
    "MARIANA ISLANDS": "NORTHERN MARIANA ISLANDS",
}
STATE_FULL = set(STATE_NAMES.values())


def normalise_state(raw: str) -> str:
    """One spelling per state, or a crash naming the one we could not place."""
    v = " ".join(str(raw).upper().split())
    if not v:
        return ""
    if v in STATE_FULL:
        return v
    if v in STATE_NAMES:
        return STATE_NAMES[v]
    if v in STATE_ALIASES:
        return STATE_ALIASES[v]
    raise SystemExit(
        f"unrecognised worksite state {raw!r}. Add it to STATE_NAMES or "
        f"STATE_ALIASES in {__file__}. Dropping it silently would remove its "
        f"filings from every state total on the page.")


#: Utilities cannot be found by name. "Electric" matches Schneider Electric
#: and Milwaukee Electric Tool, which make things, not power. NAICS 221 is
#: the industry itself -- electric generation and distribution, natural gas,
#: water and sewage -- and it is on the filing.
#: The phrases that make an education body look like a school district.
#: Matched against the state test before the school test, never after.
EDUCATION_BODY = re.compile(r"\b(DEPARTMENT|DEPT|BOARD|OFFICE) OF EDUCATION\b")

UTILITY_NAICS = ("221",)

#: Whether the body is publicly owned, as far as its own name says. This is a
#: flag on the row and NOT a filter: an investor-owned utility runs the same
#: grid and this page would be dishonest to imply otherwise. Most of NAICS
#: 221 is investor-owned, and the page says so.
PUBLICLY_OWNED = re.compile(
    r"\b(PUBLIC UTILITY DISTRICT|PUBLIC POWER|MUNICIPAL UTILIT|"
    r"POWER AUTHORITY|WATER AUTHORITY|UTILITY AUTHORITY|"
    r"ELECTRIC COOPERATIVE|ELECTRIC MEMBERSHIP|RURAL ELECTRIC|"
    r"WATER DISTRICT|SANITATION DISTRICT|IRRIGATION DISTRICT|"
    r"METROPOLITAN (WATER|UTILIT)|TENNESSEE VALLEY AUTHORITY|"
    r"BONNEVILLE POWER|CITY OF|TOWN OF|COUNTY OF|BOROUGH OF)\b")


def is_utility(naics: str) -> bool:
    code = "".join(ch for ch in str(naics or "") if ch.isdigit())
    return any(code.startswith(p) for p in UTILITY_NAICS)


def sector(name: str) -> str | None:
    """Which of the three public sectors, if any. Order matters: a district
    with 'college' in its name is still a school district.

    The exclusion is tested first and against every branch, not just the school
    branch. WEIL TENNIS ACADEMY & COLLEGE was excluded as a school and then
    picked straight back up as a university on the word 'college'. An exclusion
    that only guards one door guards nothing.
    """
    if NOT_A_SCHOOL.search(name):
        return None
    #: A STATE department or board of education runs a state agency; it does
    #: not run a school. New York CITY's department does. Widening the school
    #: pattern to catch New York City swept up Virginia, Nebraska and Arizona
    #: with it and cut the state-agency count from 87 to 74, so the state
    #: test runs first when the education phrase is the only school signal.
    if EDUCATION_BODY.search(name) and AGENCY.match(name):
        return "state_agencies"
    if SCHOOL.search(name):
        return "school_districts"
    if UNIVERSITY.search(name):
        return "universities"
    if AGENCY.match(name):
        return "state_agencies"
    return None



#: The wage offered, put on one scale. PERM states a wage and the unit it is
#: paid in, and the unit is not consistent even within one employer -- a school
#: district files hourly for a paraprofessional and yearly for a teacher. A
#: histogram of the raw numbers would bin an hourly rate against an annual
#: salary, so every wage is annualised before it is binned. Hours assume a
#: 2,080-hour year, which is an assumption and not a fact about any one post:
#: a nine-month teaching contract paid hourly annualises high.
WAGE_MULTIPLIER = {
    "YEAR": 1, "YR": 1, "ANNUAL": 1, "A": 1,
    "MONTH": 12, "MTH": 12, "MON": 12, "M": 12,
    "BIWEEKLY": 26, "BI-WEEKLY": 26, "BI": 26,
    "WEEK": 52, "WK": 52, "W": 52,
    "HOUR": 2080, "HR": 2080, "H": 2080,
}


def annual_wage(raw: str, unit: str):
    """None when it cannot be read, never a guess. A zero is not a wage."""
    txt = str(raw).replace("$", "").replace(",", "").strip()
    if not txt:
        return None
    try:
        amount = float(txt)
    except ValueError:
        return None
    mult = WAGE_MULTIPLIER.get(str(unit).upper().strip())
    if mult is None or amount <= 0:
        return None
    annual = amount * mult
    #: Guard both ends. A yearly figure mislabelled hourly annualises to tens
    #: of millions and would set the histogram's whole scale by itself.
    if annual < 5_000 or annual > 2_000_000:
        return None
    return round(annual)


#: Bin edges chosen once, here, so every sector is binned the same way and the
#: three histograms can be read against each other. Equal-width bins would put
#: almost every row in one bucket, because public-sector wages cluster hard
#: between 40k and 90k and then run a long thin tail to the chaired professor.
#:
#: The top edge is infinity, not a large number. With 10**9 as the last edge the
#: half-open test lo <= v < hi excluded anything at or above it, so the
#: "open-ended" bin was not open-ended and the bin counts silently stopped
#: summing to the number of rows.
WAGE_BINS = [0, 30_000, 40_000, 50_000, 60_000, 75_000, 90_000, 110_000,
             140_000, 180_000, 250_000, float("inf")]
COUNT_BINS = [1, 2, 3, 5, 10, 25, 50, 100, 250, float("inf")]


def bin_label(lo, hi, money: bool) -> str:
    #: No "$0k". Below a thousand the k suffix is wrong, not just ugly.
    def fmt(v):
        if not money:
            return str(int(v))
        return f"${int(v) // 1000}k" if v >= 1000 else f"${int(v)}"
    if hi == float("inf"):
        return f"{fmt(lo)}+"
    if not money and hi - lo == 1:
        return str(int(lo))
    return f"{fmt(lo)}–{fmt(hi - 1)}" if not money else f"{fmt(lo)}–{fmt(hi)}"


def histogram(values: list, edges: list, money: bool) -> list:
    """Counts per bin, with the bin's own range recorded beside the count.

    The label is built from the edges rather than written out, so a change to
    the edges cannot leave behind a label that describes the old bin.
    """
    out = []
    for lo, hi in zip(edges, edges[1:]):
        n = sum(1 for v in values if lo <= v < hi)
        out.append({"from": lo, "to": None if hi == float("inf") else hi,
                    "label": bin_label(lo, hi, money), "count": n})
    return out


def state_detail(rows: list) -> dict:
    """Per state: what each sector did there, and who it was.

    A national total is the wrong unit for anyone whose remit is one state.
    This is the same data cut the way a state's own reader needs it, so a
    question about Montana is answered with Montana's rows and not with
    Montana's share of a national figure.
    """
    out = {}
    for st in sorted({r["state"] for r in rows if r["state"]}):
        mine = [r for r in rows if r["state"] == st]
        per_sec = {}
        for sec in sorted({r["sector"] for r in mine}):
            sm = [r for r in mine if r["sector"] == sec]
            emp = defaultdict(int)
            cit = defaultdict(int)
            for r in sm:
                emp[r["employer"]] += 1
                if r["citizenship"]:
                    cit[r["citizenship"]] += 1
            wages = sorted(r["wage"] for r in sm if r["wage"])
            per_sec[sec] = {
                "filings": len(sm),
                "employers": len(emp),
                "top_employers": sorted(emp.items(), key=lambda kv: -kv[1])[:10],
                "citizenship": dict(sorted(cit.items(), key=lambda kv: -kv[1])),
                "median_wage": wages[len(wages) // 2] if wages else None,
            }
        out[st] = {
            "filings": len(mine),
            "sectors": per_sec,
            "years": {str(y): sum(1 for r in mine if r["fiscal_year"] == y)
                      for y in sorted({r["fiscal_year"] for r in mine})},
            #: Every state-agency filing in the state, whole. There are 87 in
            #: the country, so nothing is served by sampling them.
            "agency_filings": sorted(
                [r for r in mine if r["sector"] == "state_agencies"],
                key=lambda r: (-r["fiscal_year"], r["employer"])),
        }
    return out


#: How many employers per sector get a role breakdown. The table on the page
#: lists this many, and each one can be opened.
ROLE_EMPLOYERS = 25


def employer_roles(rows: list, sectors: dict) -> dict:
    """Per employer, the job titles filed and who filled them.

    WHY ROLES AND NOT FILINGS. Dallas Independent School District filed 549
    times. Listing 549 rows answers nothing; collapsing them to 16 job titles
    shows that 321 are Elementary Bilingual Teacher and 215 of those went to
    Mexican citizens. The aggregate is the finding, and it is also two orders
    of magnitude smaller to ship.

    Citizenship is kept whole per role rather than topped, because a single
    filing from an unexpected country is exactly what a reader drilling in is
    looking for, and truncating the tail would hide it.
    """
    out: dict = {}
    for sec, meta in sectors.items():
        wanted = {e for e, _ in meta["top_employers"][:ROLE_EMPLOYERS]}
        per: dict = {}
        for r in rows:
            if r["sector"] != sec or r["employer"] not in wanted:
                continue
            title = r["job_title"] or "(no title stated)"
            slot = per.setdefault(r["employer"], {}).setdefault(
                title, {"filings": 0, "citizenship": defaultdict(int),
                        "wages": [], "years": set()})
            slot["filings"] += 1
            slot["years"].add(r["fiscal_year"])
            if r["citizenship"]:
                slot["citizenship"][r["citizenship"]] += 1
            if r["wage"]:
                slot["wages"].append(r["wage"])
        out[sec] = {
            emp: sorted(
                ({"title": t,
                  "filings": v["filings"],
                  "first_year": min(v["years"]), "last_year": max(v["years"]),
                  "median_wage": (sorted(v["wages"])[len(v["wages"]) // 2]
                                  if v["wages"] else None),
                  "citizenship": dict(sorted(v["citizenship"].items(),
                                             key=lambda kv: -kv[1]))}
                 for t, v in titles.items()),
                key=lambda d: -d["filings"])
            for emp, titles in per.items()}
    return out


def distributions(rows: list) -> dict:
    """Per sector: what the wages look like, and how filings pile up per employer.

    Two different shapes, answering different questions. The wage histogram says
    what these posts pay. The filings-per-employer histogram says whether a
    sector is a long tail of employers filing once or a handful filing hundreds,
    which is the difference between a practice and a program.
    """
    out = {}
    for sec in sorted({r["sector"] for r in rows}):
        mine = [r for r in rows if r["sector"] == sec]
        wages = sorted(r["wage"] for r in mine if r["wage"])
        per_emp = defaultdict(int)
        for r in mine:
            per_emp[r["employer"]] += 1
        counts = sorted(per_emp.values())

        def pct(seq, q):
            return seq[min(len(seq) - 1, int(q * len(seq)))] if seq else None

        out[sec] = {
            "wage": {
                "bins": histogram(wages, WAGE_BINS, money=True),
                "n": len(wages),
                "unpriced": len(mine) - len(wages),
                "median": pct(wages, 0.5), "p10": pct(wages, 0.10),
                "p90": pct(wages, 0.90),
                "min": wages[0] if wages else None,
                "max": wages[-1] if wages else None,
            },
            "filings_per_employer": {
                "bins": histogram(counts, COUNT_BINS, money=False),
                "employers": len(counts),
                "median": pct(counts, 0.5),
                "max": counts[-1] if counts else None,
                #: The share the busiest ten employers account for. One number
                #: that says whether the sector's total is a crowd or a few.
                "top10_share": (round(100 * sum(sorted(counts, reverse=True)[:10])
                                      / sum(counts), 1) if counts else None),
            },
            "by_year": {str(y): sum(1 for r in mine if r["fiscal_year"] == y)
                        for y in sorted({r["fiscal_year"] for r in mine})},
        }
    return out


#: Visa classes that are NOT work authorisation. Being sponsored while holding
#: one is not unlawful and is not rare enough to be shocking -- a person can
#: be out of status, or in a category that permits an employer to petition --
#: but it is the opposite of the ordinary H-1B-to-green-card path, and it is
#: the kind of row a reader would want to find rather than have summarized.
#: EWI means entered without inspection; PAROLEE means admitted on parole.
#: Spellings of US citizenship as they appear in the files.
US_CITIZEN = {"UNITED STATES OF AMERICA", "UNITED STATES", "USA", "U.S.A.",
              "AMERICA"}

NON_WORK_VISA = {"B-1", "B-2", "F-2", "J-2", "M-1", "H-4", "TPS", "PAROLEE",
                 "EWI", "VISITOR", "NOT IN USA", "NONE"}


def anomalies(rows: list) -> dict:
    """Rows worth a second look, each with the reason that flagged it.

    Nothing here is an accusation. These are filings that depart from the
    ordinary pattern, computed rather than chosen, so a reader can see the test
    and not only its result.

    Returns the FULL lists. Truncation for display happens at the call site,
    and the count is taken here, before it. An earlier version truncated inside
    this function and the page then reported the cap -- "400 filings" against
    every test it ran -- because a count read off a capped list measures the
    cap.
    """
    title_counts = defaultdict(int)
    for r in rows:
        if r["job_title"]:
            title_counts[(r["sector"], r["job_title"])] += 1

    out = defaultdict(list)
    for r in rows:
        if r["visa_held"] in NON_WORK_VISA:
            out["sponsored_while_not_work_authorised"].append(
                {**r, "why": f"held {r['visa_held']}, which is not work authorisation"})
        cit, born = r["citizenship"], r["birth_country"]
        #: A US citizen cannot need a labor certification. The filing names
        #: one anyway. Almost certainly a mis-keyed field rather than anything
        #: else, but it is a defect in a federal disclosure file and the only
        #: way anyone finds it is by testing for it.
        if cit.upper() in US_CITIZEN:
            out["a_us_citizen_named_on_the_filing"].append(
                {**r, "why": f"citizenship recorded as {cit}"
                             + (f", born in {born}" if born else "")})
        elif cit and born and born.lower() not in ("", "not in usa") and cit.lower() != born.lower():
            out["citizenship_differs_from_birth_country"].append(
                {**r, "why": f"{cit} citizen, born in {born}"})
        if r["job_title"] and title_counts[(r["sector"], r["job_title"])] == 1:
            out["job_title_unique_in_its_sector"].append(
                {**r, "why": "this job title appears once in this sector"})
    return {k: sorted(v, key=lambda r: (-r["fiscal_year"], r["employer"]))
            for k, v in out.items()}


#: How many rows of each list ship in the JSON. The total is published beside
#: it so a reader of the file can tell a cap from a count.
ANOMALY_SHOWN = 400


def clean(v) -> str:
    t = str(v or "").strip()
    if t.startswith('="') and t.endswith('"'):
        t = t[2:-1]
    return t.strip('="').strip()


def fy_of(path: Path) -> int:
    m = re.search(r"FY_?(\d{2,4})", path.name, re.I)
    if not m:
        return 0
    y = int(m.group(1))
    return 2000 + y if y < 100 else y


def main() -> int:
    files = sorted(set(list(PERM.glob("*.xlsx")) + [p for p in EXTRA if p.exists()]),
                   key=fy_of)
    files = [f for f in files if "New_Form" not in f.name]
    if not files:
        raise SystemExit(f"FAIL: no PERM files in {PERM}. Nothing written.")

    import openpyxl
    rows: list[dict] = []
    seen: set = set()
    skipped, dupes, scanned = [], 0, 0
    for path in files:
        fy = fy_of(path)
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        hdr = [str(h).strip().upper() if h else "" for h in next(it)]
        idx = {}
        for field, spell in NEED.items():
            hit = next((s for s in spell if s in hdr), None)
            if hit is not None:
                idx[field] = hdr.index(hit)
        missing = [c for c in REQUIRED if c not in idx]
        if missing:
            wb.close()
            why = ("carries no citizenship field" if missing == ["CITIZENSHIP"]
                   else f"no column for {', '.join(missing)}")
            skipped.append({"file": path.name, "fiscal_year": fy, "reason": why})
            print(f"  SKIP FY{fy} {path.name}: {why}", flush=True)
            continue
        got = 0
        for row in it:
            scanned += 1
            if "CASE_NUMBER" in idx:
                cn = clean(row[idx["CASE_NUMBER"]]).upper()
                if cn:
                    if cn in seen:
                        dupes += 1
                        continue
                    seen.add(cn)
            name = clean(row[idx["EMPLOYER_NAME"]]).upper()
            if not name:
                continue
            sec = sector(name)
            if not sec and "NAICS" in idx and is_utility(row[idx["NAICS"]]):
                sec = "utilities"
            if not sec:
                continue
            g = lambda k: clean(row[idx[k]]) if k in idx else ""   # noqa: E731
            rows.append({
                "fiscal_year": fy, "sector": sec, "employer": name,
                "job_title": g("JOB_TITLE").title(),
                "citizenship": g("CITIZENSHIP").title(),
                "birth_country": g("BIRTH_COUNTRY").title(),
                "visa_held": g("CLASS_OF_ADMISSION").upper(),
                "state": normalise_state(g("WORK_STATE")),
                "city": g("WORK_CITY").title(),
                "status": g("CASE_STATUS").title(),
                "decided": g("DECISION_DATE")[:10],
                "wage": annual_wage(g("WAGE_FROM"), g("WAGE_UNIT")),
                #: The federal file this row came from, named on the row. A
                #: reader who wants to check a figure should not have to work
                #: out which of twelve files to open.
                "publicly_owned": bool(PUBLICLY_OWNED.search(name)),
                "source_file": path.name,
                "case_number": clean(row[idx["CASE_NUMBER"]]) if "CASE_NUMBER" in idx else "",
            })
            got += 1
        wb.close()
        print(f"  FY{fy} {path.name}: {got:,} public-employer rows", flush=True)

    years = sorted({r["fiscal_year"] for r in rows})
    def tally(key, within=None):
        c = defaultdict(int)
        for r in rows:
            if within and r["sector"] != within:
                continue
            v = r.get(key) or "(not stated)"
            c[v] += 1
        return dict(sorted(c.items(), key=lambda kv: -kv[1]))

    sectors = {}
    #: Derived from the rows, not a hardcoded list. The utilities sector was
    #: classified correctly, collected correctly, and then dropped on the
    #: floor here because this loop named three sectors and there were four.
    for sec in sorted({r["sector"] for r in rows}):
        mine = [r for r in rows if r["sector"] == sec]
        emp = defaultdict(int)
        for r in mine:
            emp[r["employer"]] += 1
        sectors[sec] = {
            "filings": len(mine),
            "employers": len(emp),
            "citizenship": dict(sorted(
                ((k, v) for k, v in tally("citizenship", sec).items()),
                key=lambda kv: -kv[1])),
            "visa_held": tally("visa_held", sec),
            "top_employers": sorted(emp.items(), key=lambda kv: -kv[1])[:25],
            "by_year": {str(y): sum(1 for r in mine if r["fiscal_year"] == y)
                        for y in years},
        }

    #: BY STATE *AND SECTOR*. by_state alone is every sector together, so
    #: Washington's 131 Indian filings are overwhelmingly its universities
    #: and say nothing about its state agencies. A reader looking at a
    #: state-agency page and reading a state total would draw exactly the
    #: wrong conclusion, so the two are kept apart.
    by_state_sector = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    by_state = defaultdict(lambda: defaultdict(int))
    for r in rows:
        by_state[r["state"]][r["citizenship"] or "(not stated)"] += 1
        by_state_sector[r["sector"]][r["state"]][
            r["citizenship"] or "(not stated)"] += 1

    anom = anomalies(rows)
    pairs = defaultdict(int)
    for r in rows:
        c, b = r["citizenship"], r["birth_country"]
        if (c and b and c.upper() not in US_CITIZEN
                and b.lower() not in ("", "not in usa") and c.lower() != b.lower()):
            pairs[(c, b)] += 1
    out = {
        "source": "US DOL OFLC, PERM permanent labor certification disclosure files",
        "source_url": "https://www.dol.gov/agencies/eta/foreign-labor/performance",
        "window": f"FY{years[0]}-FY{years[-1]}" if years else "",
        "files_read": [f.name for f in files if not any(
            s["file"] == f.name for s in skipped)],
        "files_skipped": skipped,
        "rows_scanned": scanned,
        "duplicate_rows_skipped": dupes,
        "public_rows": len(rows),
        "caveats": [
            "A PERM certification is an employer asking to sponsor someone for "
            "permanent residence after testing the local labor market. It is "
            "not a hire, not an admission, and not an H-1B petition.",
            "Many of these workers were already in the job on another visa. "
            "The visa_held field says which one.",
            "Citizenship is published for FY2013 onward and was removed from "
            "FY2025, when the form lost every worker field at once. Birth "
            "country runs FY2015 to FY2024. The series has ended.",
            "No worker is named in the federal file and none is named here. "
            "Employer, job title, worksite and citizenship are all published "
            "disclosure.",
            "Employers are matched on the name as filed, so one body can "
            "appear under several spellings and any single total is a floor.",
            "Sponsoring a worker is lawful. Nothing here says otherwise.",
        ],
        "sectors": sectors,
        "citizenship_overall": tally("citizenship"),
        "by_state": {k: dict(sorted(v.items(), key=lambda kv: -kv[1]))
                     for k, v in sorted(by_state.items())},
        "employer_roles": employer_roles(rows, sectors),
        "by_state_sector": {
            sector: {st: dict(sorted(c.items(), key=lambda kv: -kv[1]))
                     for st, c in sorted(states.items()) if st}
            for sector, states in sorted(by_state_sector.items())},
        "by_state_detail": state_detail(rows),
        "distributions": distributions(rows),
        #: Which citizenship-and-birth pairs recur. The mismatch test alone
        #: says only that the two fields disagree. The pairs say what the
        #: disagreement is made of, and it turns out to be mostly one country.
        "citizenship_birth_pairs": [
            {"citizenship": c, "birth_country": b, "filings": n}
            for (c, b), n in sorted(
                pairs.items(), key=lambda kv: -kv[1])[:40]],
        "citizenship_birth_pairs_total": sum(pairs.values()),
        "anomalies": {k: v[:ANOMALY_SHOWN] for k, v in anom.items()},
        "anomaly_totals": {k: len(v) for k, v in anom.items()},
        "anomaly_shown": ANOMALY_SHOWN,
        "anomaly_notes": {
            "sponsored_while_not_work_authorised":
                "The worker held a visa class that is not work authorisation "
                "when the employer filed. Lawful in itself; the opposite of "
                "the ordinary path.",
            "citizenship_differs_from_birth_country":
                "Citizenship and country of birth are different fields and "
                "they disagree on this row. Common and unremarkable for many "
                "people; it is here because the two are often assumed to be "
                "the same thing.",
            "a_us_citizen_named_on_the_filing":
                "The filing records the worker as a US citizen. A US citizen "
                "needs no labor certification, so the field is almost "
                "certainly wrong. It is published as filed.",
            "job_title_unique_in_its_sector":
                "A job title filed exactly once by any employer in this "
                "sector. Usually a local naming quirk rather than a strange "
                "job.",
        },
        "records": sorted(rows, key=lambda r: (-r["fiscal_year"], r["employer"])),
    }
    write_json(OUT, out, indent=1)
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(rows):,} public-employer filings, {out['window']}, "
          f"{dupes:,} duplicates skipped")
    for sec, v in sectors.items():
        top = list(v["citizenship"].items())[:3]
        print(f"    {sec:<18}{v['filings']:>7,} filings  {v['employers']:>5} employers  "
              f"top: {top}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
