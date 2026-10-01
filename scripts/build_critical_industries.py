#!/usr/bin/env python3
"""Five industries the United States cannot import, and who it trains to run them.

WHY THESE FIVE. Mining, petroleum, aerospace, batteries and nuclear are
industries where the work is physically here and cannot be offshored: an ore
body, a well, an airframe, a cell plant, a reactor. If the people who hold the
doctorates in those fields are overwhelmingly here on temporary visas, the
country has a supply problem that no amount of hiring abroad fixes.

WHAT RESTRICTS THE WORK, SAID PRECISELY. Some of this work carries federal
access restrictions, and they are three different regimes that are routinely
run together. They are not the same thing and this file does not treat them as
the same thing.

  EXPORT CONTROL (ITAR, 22 CFR 120-130; EAR, 15 CFR 730-774) limits access to
  controlled technical data to a "U.S. person" -- 22 CFR 120.62 -- which means
  a citizen, a LAWFUL PERMANENT RESIDENT, or a protected individual under
  8 USC 1324b(a)(3). It is NOT a security clearance and it does NOT require
  citizenship. A green-card holder needs no authorisation to do ITAR work.

  ACCESS AUTHORISATION at a commercial reactor (10 CFR 73.56) is a background
  investigation and fitness-for-duty determination for unescorted access. It
  is NOT a security clearance either.

  A SECURITY CLEARANCE is eligibility for access to classified national
  security information, adjudicated under EO 12968 and SEAD 4, and DOE's L and
  Q access authorisations (10 CFR 710) are of this kind. These do require US
  citizenship. Very little of what a doctorate holder does in these five
  industries falls here.

WHY THE DISTINCTION MATTERS FOR THIS DATA, and it is the one place it bites:
IPEDS counts a permanent resident as domestic, so every "non-resident alien"
in these counts is on a temporary visa and is therefore NOT a U.S. person for
export-control purposes. The export-control line falls exactly on the
population this dataset measures. That is a statement about law, not about who
was hired: IPEDS records a degree awarded and nothing else.

THE MAP BELOW IS AN EDITORIAL CLAIM, not a federal category. IPEDS publishes
CIP codes, and a CIP code is a field of study, not an industry. Four of these
five map onto codes that plainly belong to the industry. BATTERIES DO NOT:
there is no battery CIP, so that entry is a declared proxy built from materials
programmes, and every page that shows it says so. A reader who disagrees with a
mapping can see exactly which codes produced every number.

THE 2010 RECODE is handled by bases_for(), as everywhere else here. Counting
award bases naively double-counts the transition years and inflates every
programme by roughly a fifth.

Usage:
    python3 scripts/build_critical_industries.py
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "ipeds" / "nra_index.csv.gz"
CIP_TITLES = ROOT / "data" / "ipeds" / "cip_titles.csv"
HD = ROOT / "data" / "ipeds" / "HD2024.csv"
IPEDS_DIR = ROOT / "data" / "ipeds"
OUT = ROOT / "site" / "data" / "critical_industries.json"
RECORD = ROOT / "data" / "policy" / "public_record.json"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from pipeline.models import bases_for                        # noqa: E402
from atomic_write import write_json                          # noqa: E402

#: The window the headline shares are pooled over. Matches programme_shares.py
#: so the two pages cannot disagree about the same programme.
YEAR_LO, YEAR_HI = 2015, 2022

#: One entry per industry. `cips` is the whole claim: change it and every
#: number on that industry's page changes with it.
INDUSTRIES = [
    {
        "slug": "petroleum",
        "name": "Petroleum",
        "cips": {"14.2501": "Petroleum Engineering"},
        "restriction": None,
        "restriction_note": "No export-control or access-authorisation regime "
                            "applies by default. Open to anyone with the right "
                            "to work in the United States.",
        "why": "Reservoir engineering, drilling and production. The degree is "
               "specific to the industry: there is no other career for a "
               "petroleum engineering doctorate.",
    },
    {
        "slug": "mining",
        "name": "Mining and metals",
        "cips": {"14.2101": "Mining and Mineral Engineering",
                 "14.2001": "Metallurgical Engineering"},
        "restriction": None,
        "restriction_note": "No export-control or access-authorisation regime "
                            "applies by default. Some critical-minerals work "
                            "carries federal funding conditions, which are "
                            "grant terms and not a personnel restriction.",
        "why": "The people who open mines and process ore. Geology is "
               "deliberately excluded: most geologists never work in mining, "
               "and including them would describe earth science instead.",
    },
    {
        "slug": "battery",
        "name": "Battery technology",
        "cips": {"14.1801": "Materials Engineering",
                 "40.1001": "Materials Science"},
        "restriction": None,
        "restriction_note": "No export-control or access-authorisation regime "
                            "applies by default, though specific DOE-funded "
                            "programmes may attach their own conditions.",
        # The honest caveat, carried in the data so no page can drop it.
        "proxy": ("IPEDS HAS NO BATTERY CATEGORY. This is the closest honest "
                  "proxy: the materials programmes that produce electrode, "
                  "electrolyte and cell researchers. It therefore counts people "
                  "who will never work on a battery, and misses battery work "
                  "done inside chemistry and chemical engineering. Treat it as "
                  "the materials pipeline, which is what it measures."),
        "why": "Cell chemistry, electrodes and electrolytes sit inside "
               "materials programmes. No federal category names the industry.",
    },
    {
        "slug": "ai",
        "name": "Artificial intelligence",
        "cips": {"11.0102": "Artificial Intelligence",
                 "11.0701": "Computer Science",
                 "30.7001": "Data Science"},
        "restriction": None,
        "restriction_note": "No export-control or access-authorisation regime "
                            "applies to the field as such. Specific defence or "
                            "intelligence work carries its own rules, and some "
                            "frontier model weights and semiconductor design "
                            "tools fall under export control, but a computer "
                            "science doctorate does not.",
        "why": "The models and the people who build them. Computer science "
               "carries the volume; the named AI and data science codes are "
               "newer and smaller, and are counted separately on this page so "
               "neither is hidden inside the other.",
    },
    {
        "slug": "aerospace",
        "name": "Aerospace",
        "cips": {"14.0201": "Aerospace, Aeronautical and Astronautical Engineering"},
        "restriction": "Export control",
        "restriction_note": "Much of this work is export-controlled. ITAR "
                            "(22 CFR 120-130) limits access to defence articles "
                            "and technical data to a 'U.S. person' as defined at "
                            "22 CFR 120.62: a citizen, a lawful permanent "
                            "resident, or a protected individual. This is not a "
                            "security clearance and it does not require "
                            "citizenship -- a permanent resident qualifies. It "
                            "does exclude someone on a temporary visa, which is "
                            "exactly who IPEDS counts as a non-resident alien.",
        "why": "Airframes, propulsion and spacecraft. The clearest case of a "
               "field trained one way and employed another.",
    },
    {
        "slug": "nuclear",
        "name": "Nuclear",
        "cips": {"14.2301": "Nuclear Engineering"},
        "restriction": "Access authorisation",
        "restriction_note": "Two different regimes, often confused. Unescorted "
                            "access to a commercial reactor requires NRC access "
                            "authorisation under 10 CFR 73.56 -- a background "
                            "investigation and fitness-for-duty determination, "
                            "not a security clearance, and not restricted by "
                            "citizenship on its face. DOE work on weapons-adjacent "
                            "programmes requires an L or Q access authorisation "
                            "under 10 CFR 710, which IS a clearance and does "
                            "require US citizenship. Most civil nuclear "
                            "engineering falls under the first, not the second.",
        "why": "Reactor physics, fuel cycle and radiological engineering.",
    },
]


#: IPEDS award levels, and the rollup rows that would double-count if read.
AWARD_LEVELS = {"5": "Bachelor's", "7": "Master's", "17": "Doctorate"}
ROLLUPS = {"20", "21", "99"}


def _completions_rows():
    """The newest IPEDS Completions release, whatever form it is in."""
    best, year = None, 0
    for p in sorted(IPEDS_DIR.iterdir()):
        m = re.match(r"^[cC](\d{4})_[aA](_rv|_RV)?\.(csv|zip)$", p.name)
        if not m or not 1990 <= int(m.group(1)) <= 2100:
            continue
        if int(m.group(1)) >= year:
            year, best = int(m.group(1)), p
    if best is None:
        return 0, []
    if best.suffix.lower() == ".zip":
        with zipfile.ZipFile(best) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(name) as fh:
                return year, list(csv.DictReader(
                    io.TextIOWrapper(fh, "utf-8-sig", errors="replace")))
    with open(best, newline="", encoding="utf-8-sig", errors="replace") as fh:
        return year, list(csv.DictReader(fh))


def by_award_level(wanted: set[str]) -> tuple[int, dict]:
    """Bachelor's, master's and doctorate shares for each CIP, newest year.

    This is the one comparison that answers "are Americans taking these
    degrees?" directly, because it holds the FIELD constant and varies only the
    level. Electrical engineering runs 9% non-resident at bachelor's and 71% at
    doctorate: the same subject, the same year, a different population.
    """
    year, rows = _completions_rows()
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for row in rows:
        code = (row.get("CIPCODE") or "").strip()
        if code not in wanted:
            continue
        if (row.get("MAJORNUM") or "1").strip() != "1":
            continue
        lvl = (row.get("AWLEVEL") or "").strip()
        if lvl in ROLLUPS or lvl not in AWARD_LEVELS:
            continue
        def num(key):
            v = row.get(key)
            try:
                return int(float(v)) if v not in (None, "", ".") else 0
            except ValueError:
                return 0
        acc[code][lvl][0] += num("CTOTALT")
        acc[code][lvl][1] += num("CNRALT")
    return year, acc


def public_record(rows, year: int) -> list[dict]:
    """Statements on the record, with the federal figure that sits beside each.

    The point is not to adjudicate anyone. It is that a site measuring this
    workforce should be able to put its own numbers next to what is being said
    about it, so a reader sees both at once. Each figure is recomputed from
    IPEDS here, so the pairing cannot go stale while the statement stays fixed.
    Where a statement concerns data this site does not hold -- graduate counts
    abroad -- that is recorded as a limit of this site.
    """
    if not RECORD.exists():
        return []
    statements = json.loads(RECORD.read_text()).get("statements", [])
    tot = defaultdict(int)
    inst = defaultdict(set)
    for row in rows:
        code = (row.get("CIPCODE") or "").strip()
        if (row.get("MAJORNUM") or "1").strip() != "1":
            continue
        if (row.get("AWLEVEL") or "").strip() in ROLLUPS:
            continue
        v = row.get("CTOTALT")
        try:
            n = int(float(v)) if v not in (None, "", ".") else 0
        except ValueError:
            n = 0
        tot[code] += n
        if n:
            inst[code].add((row.get("UNITID") or "").strip())
    out = []
    for c in statements:
        entry = {k: c[k] for k in ("id", "speaker", "venue", "date", "source_url",
                                   "source_note", "quote") if k in c}
        if c.get("outside_scope"):
            entry["outside_scope"] = c["outside_scope"]
            out.append(entry)
            continue
        checks = []
        for ch in c.get("checks", []):
            if ch["measure"] == "awards":
                found = sum(tot[code] for code in ch["cip"])
            else:
                found = len(set().union(*(inst[code] for code in ch["cip"])))
            checks.append({"label": ch["label"], "stated": ch["stated"],
                           "found": found, "cip": ch["cip"], "year": year})
        entry["checks"] = checks
        out.append(entry)
    return out


def cip_titles() -> dict[str, str]:
    out: dict[str, str] = {}
    if not CIP_TITLES.exists():
        return out
    with open(CIP_TITLES, newline="", encoding="utf-8-sig", errors="replace") as fh:
        for row in csv.DictReader(fh):
            code = (row.get("cipcode") or row.get("CIPCODE") or "").strip()
            title = (row.get("title") or row.get("TITLE") or "").strip()
            if code and title:
                out[code] = title
    return out


def institution_names() -> dict[str, str]:
    """unitid -> institution name, from the IPEDS directory."""
    out: dict[str, str] = {}
    if not HD.exists():
        return out
    with open(HD, newline="", encoding="utf-8-sig", errors="replace") as fh:
        for row in csv.DictReader(fh):
            uid = (row.get("UNITID") or row.get("unitid") or "").strip()
            name = (row.get("INSTNM") or row.get("instnm") or "").strip()
            if uid and name:
                out[uid] = name
    return out


def main() -> int:
    if not INDEX.exists():
        print(f"  missing {INDEX.relative_to(ROOT)}")
        return 1
    titles, names = cip_titles(), institution_names()
    wanted = {c: ind["slug"] for ind in INDUSTRIES for c in ind["cips"]}
    level_year, by_level = by_award_level(set(wanted))
    record_year, record_rows = _completions_rows()
    record = public_record(record_rows, record_year)

    # [total, nra] accumulators, each keyed the way one view needs it.
    per_cip = defaultdict(lambda: [0, 0])
    per_cip_year = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    per_inst = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    national_year = defaultdict(lambda: [0, 0])

    with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            year = int(row["year"])
            # The 2010 recode. Without this the transition years are counted
            # twice and every programme reads about a fifth too high.
            if row["basis"] not in bases_for(year):
                continue
            t, n = int(row["total"]), int(row["nra"])
            if YEAR_LO <= year <= YEAR_HI:
                national_year[year][0] += t
                national_year[year][1] += n
            code = row["cipcode"]
            if code not in wanted:
                continue
            y = per_cip_year[code][year]
            y[0] += t
            y[1] += n
            if YEAR_LO <= year <= YEAR_HI:
                c = per_cip[code]
                c[0] += t
                c[1] += n
                inst = per_inst[wanted[code]][row["unitid"]]
                inst[0] += t
                inst[1] += n

    def pct(n, t):
        return round(100 * n / t, 1) if t else None

    out_inds = []
    for ind in INDUSTRIES:
        tot = nra = 0
        progs = []
        for code, label in ind["cips"].items():
            t, n = per_cip[code]
            tot += t
            nra += n
            progs.append({"cip": code, "title": titles.get(code, label),
                          "label": label, "doctorates": t, "nra": n,
                          "share": pct(n, t),
                          # A programme's own line, so a composite industry can
                          # be taken apart by a reader who distrusts the map.
                          "series": {str(y): pct(v[1], v[0])
                                     for y, v in sorted(per_cip_year[code].items())
                                     if v[0] >= 20}})
        combined = defaultdict(lambda: [0, 0])
        for code in ind["cips"]:
            for y, v in per_cip_year[code].items():
                combined[y][0] += v[0]
                combined[y][1] += v[1]
        schools = sorted(
            ({"unitid": uid, "name": names.get(uid, uid), "doctorates": v[0],
              "nra": v[1], "share": pct(v[1], v[0])}
             for uid, v in per_inst[ind["slug"]].items() if v[0] >= 10),
            key=lambda s: -s["doctorates"])
        # The level gradient, pooled across the industry's codes.
        levels = []
        for lvl, label in AWARD_LEVELS.items():
            lt = sum(by_level[c][lvl][0] for c in ind["cips"])
            ln = sum(by_level[c][lvl][1] for c in ind["cips"])
            if lt:
                levels.append({"level": label, "awards": lt, "nra": ln,
                               "share": pct(ln, lt),
                               "domestic": lt - ln,
                               "domestic_share": pct(lt - ln, lt)})
        out_inds.append({
            "levels": levels,
            **{k: ind[k] for k in ("slug", "name", "restriction",
                                   "restriction_note", "why")},
            "proxy": ind.get("proxy"),
            "url": f"/industries/{ind['slug']}.html",
            "cips": list(ind["cips"]),
            "doctorates": tot, "nra": nra, "share": pct(nra, tot),
            "institutions": len(per_inst[ind["slug"]]),
            "programmes": sorted(progs, key=lambda p: -p["doctorates"]),
            "series": {str(y): pct(v[1], v[0]) for y, v in sorted(combined.items())
                       if v[0] >= 20},
            "top_schools": schools[:25],
        })

    out_inds.sort(key=lambda i: -(i["share"] or 0))
    nat_t = sum(v[0] for v in national_year.values())
    nat_n = sum(v[1] for v in national_year.values())
    out = {
        "_comment": __doc__.split("Usage:")[0].strip(),
        "source": "NCES IPEDS Completions, research doctorates, "
                  f"{YEAR_LO}-{YEAR_HI}",
        "source_url": "https://nces.ed.gov/ipeds/use-the-data",
        "window": {"from": YEAR_LO, "to": YEAR_HI},
        "level_year": level_year,
        "public_record": record,
        "national": {"doctorates": nat_t, "nra": nat_n, "share": pct(nat_n, nat_t),
                     "note": "All research doctorates in the same window, as the "
                             "baseline every industry share is read against."},
        "definitions": {
            "cip_is_not_an_industry":
                "IPEDS publishes a field of study, not an employer. Every "
                "mapping here is this site's, and each industry lists the codes "
                "it used.",
            "restriction":
                "The federal access regime that applies to the work, where one "
                "does. Export control and access authorisation are NOT security "
                "clearances, and only a DOE L or Q authorisation requires US "
                "citizenship. See each industry's note for the exact rule.",
            "us_person":
                "Export control turns on 'U.S. person' (22 CFR 120.62), which "
                "includes lawful permanent residents. IPEDS counts permanent "
                "residents as domestic, so every non-resident alien here is "
                "outside that definition.",
            "share": "Non-resident alien share of research doctorates awarded.",
            "levels":
                "The same field at bachelor's, master's and doctorate in the "
                "newest Completions year. It holds the subject constant and "
                "varies only the level, which is the most direct measure here "
                "of where the American pipeline stops.",
        },
        "industries": out_inds,
        "caveats": [
            "A CIP code is a field of study. Nobody in this data is observed "
            "working in the industry it is matched to.",
            "The battery entry is a proxy built from materials programmes, "
            "because IPEDS publishes no battery category.",
            "Shares are of degrees awarded, not of the current workforce. A "
            "doctorate awarded in 2016 may have left the country or the field.",
            "'Non-resident alien' is the IPEDS reporting category: a student on "
            "a temporary visa. Permanent residents are counted as domestic.",
            "The restriction note states the law as written. It is not an "
            "observed hiring outcome: this data cannot show who was employed, "
            "under what authorisation, or whether they stayed.",
            "Export control, access authorisation and a security clearance are "
            "three different things. Only a DOE L or Q access authorisation "
            "requires US citizenship.",
        ],
    }
    write_json(OUT, out, indent=1)
    print(f"  wrote {OUT.relative_to(ROOT)}: {len(out_inds)} industries, "
          f"{YEAR_LO}-{YEAR_HI}")
    for i in out_inds:
        print(f"    {i['share']:>5}%  {i['name']:<22}{i['doctorates']:>6,} doctorates"
              f"  {i['institutions']:>3} schools"
              f"  {i['restriction'] or ''}")
    print(f"    national baseline across all fields {out['national']['share']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
