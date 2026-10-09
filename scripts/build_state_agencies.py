#!/usr/bin/env python3
"""H-1B workers employed by state governments.

WHY THIS IS A PAGE

The rest of this site asks who the universities admit and who the companies
hire. This asks a narrower question with a different weight: which arms of
state government sponsor H-1B workers, and for what. A state agency is not a
competitive employer bidding for scarce talent -- it is a public body, funded
by the taxpayers of that state, choosing to sponsor a foreign worker for a job
in its own department.

Nothing here says that is wrong. Agencies hire engineers, actuaries,
epidemiologists and statisticians, and the H-1B is a lawful way to do it. The
point is that it is countable, and until now nobody had counted it.

TWO SOURCES, TWO DIFFERENT THINGS

  USCIS Employer Data Hub   approvals, FY2009-FY2023. Closer to people.
  DOL LCA disclosure files  applications, with JOB TITLE and WAGE. Closer to
                            what the work actually was. A ceiling on intent.

HEADER SPELLINGS ARE READ THROUGH A LIST, AND A MISS IS FATAL.

The Data Hub names its columns "Initial Approvals" through FY2019 and "Initial
Approval" from FY2020. Reading only one spelling returns a silent zero for
eleven of the fifteen files and understates the total threefold -- which is
exactly what happened the first time this was measured by hand. So every
column is resolved through both spellings and a file matching neither stops
the build.

WHAT COUNTS AS A STATE AGENCY

The employer's own name on the form, matched as "State of X <gov word>",
"X State <gov word>" or "X <gov word>", where the gov word is department,
office, division, bureau, commission, board, agency, patrol, police or
authority -- AND the filing's own state matches the state in the name, so
Washington County in Utah and Washington University in St Louis do not creep
in. Universities, counties, cities and school districts are excluded: a public
university is a state institution too, and it is measured elsewhere on this
site, but it is not what this page is about.

NAMES ARE TRUNCATED, SO VARIANTS ARE GROUPED. The older Data Hub files cut the
employer name at about 34 characters, so one agency appears several ways --
Washington's Department of Ecology appears four. Two variants are grouped when
one's normalised name is a PREFIX of the other's. Both the group and the raw
names as filed are published, so the grouping can be checked rather than
trusted.

Output: site/data/state_agencies.json

Usage:
    python3 scripts/build_state_agencies.py
    python3 scripts/build_state_agencies.py --with-lca   # add job titles and wages
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "data" / "uscis_hub"
LCA = ROOT / "data" / "h1b" / "lca"
CACHE = ROOT / "data" / "h1b" / "state_agency_lca.json"
ISSUANCES = ROOT / "site" / "data" / "visa_issuances.json"
OUT = ROOT / "site" / "data" / "state_agencies.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

#: Both spellings of every column. A file matching neither is a crash.
FIELDS = {
    "initial_approval": ("Initial Approval", "Initial Approvals"),
    "initial_denial": ("Initial Denial", "Initial Denials"),
    "continuing_approval": ("Continuing Approval", "Continuing Approvals"),
    "continuing_denial": ("Continuing Denial", "Continuing Denials"),
}

ABBR = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
    "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE",
    "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR",
    "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
    "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
}
NAMES = sorted(ABBR, key=len, reverse=True)
GOV = (r"(?:DEPT|DEPARTMENT|OFFICE|DIVISION|BUREAU|COMMISSION|BOARD|AGENCY|"
       r"PATROL|POLICE|ADMIN|AUTHORITY|INSUR)")
PAT = re.compile(r"^(?:STATE OF\s+|COMMONWEALTH OF\s+)?(" + "|".join(NAMES) +
                 r")\s+(?:STATE\s+)?" + GOV + r"\b")
SKIP = re.compile(r"\b(UNIVERSITY|UNIV|COLLEGE|SCHOOL DISTRICT|COUNTY|"
                  r"CITY OF|NEW YORK CITY)\b")
STOP = re.compile(r"\b(STATE OF|COMMONWEALTH OF|STATE|THE|OF|AND|&|DEPT|"
                  r"DEPARTMENT|OFFICE|DIVISION|BUREAU)\b")


def value(row: dict, names: tuple) -> int:
    for n in names:
        if n in row:
            raw = (row[n] or "0").replace(",", "").strip()
            try:
                return int(raw)
            except ValueError:
                return 0
    raise SystemExit(
        f"FAIL: none of {names} is a column in this file. The Data Hub "
        f"renamed it again; add the new spelling. Nothing written.")


def agency_state(name: str) -> str | None:
    m = PAT.match(name)
    return ABBR[m.group(1)] if m else None


def normalise(name: str, state_word: str) -> str:
    """The agency's function, with the boilerplate stripped.

    "STATE OF WASHINGTON DEPT OF ECOLOG" and "WASHINGTON STATE DEPARTMENT OF
    ECOLOGY" both reduce to "ECOLOG"/"ECOLOGY", and the prefix rule in
    group_variants() then puts them together.
    """
    s = name.replace(state_word, " ")
    s = STOP.sub(" ", s)
    return re.sub(r"[^A-Z ]", " ", s).split() and " ".join(
        re.sub(r"[^A-Z ]", " ", s).split()) or ""


def group_variants(variants: list) -> list:
    """Fold truncated spellings together, longest name first.

    Two variants join when one normalised form is a prefix of the other and
    the shorter is at least five characters -- short enough to catch a cut
    name, long enough that "DEPT OF H..." does not swallow Health and Housing
    into one agency.
    """
    out: list = []
    for v in sorted(variants, key=lambda x: -len(x["normal"])):
        host = next((g for g in out
                     if len(v["normal"]) >= 5
                     and (g["normal"].startswith(v["normal"])
                          or v["normal"].startswith(g["normal"]))), None)
        if host:
            host["filed_as"].append(v["name"])
            for k in ("initial", "continuing", "denied"):
                host[k] += v[k]
            host["years"] |= v["years"]
            host["cities"] |= v["cities"]
        else:
            out.append({**v, "filed_as": [v["name"]]})
    return out


def read_hub() -> tuple[dict, dict]:
    """Approvals by agency, from every Data Hub file."""
    rows = defaultdict(lambda: {"initial": 0, "continuing": 0, "denied": 0,
                                "years": set(), "cities": set()})
    years = set()
    files = sorted(HUB.glob("h1b_datahubexport-*.csv"))
    if not files:
        raise SystemExit(f"FAIL: no Data Hub files in {HUB}. Nothing written.")
    for f in files:
        data = list(csv.DictReader(f.open(encoding="utf-8-sig")))
        if not data:
            continue
        value(data[0], FIELDS["initial_approval"])     # fail loudly, once per file
        for r in data:
            name = (r.get("Employer") or "").strip().upper()
            if not name or SKIP.search(name):
                continue
            st = agency_state(name)
            if not st or st != (r.get("State") or "").strip().upper():
                continue
            e = rows[(st, name)]
            e["initial"] += value(r, FIELDS["initial_approval"])
            e["continuing"] += value(r, FIELDS["continuing_approval"])
            e["denied"] += (value(r, FIELDS["initial_denial"])
                            + value(r, FIELDS["continuing_denial"]))
            fy = int(r.get("Fiscal Year") or 0)
            e["years"].add(fy)
            years.add(fy)
            city = (r.get("City") or "").strip().title()
            if city:
                e["cities"].add(city)
    return rows, {"first": min(years), "last": max(years), "files": len(files)}


def read_lca() -> dict:
    """Job titles and wages for state agencies, from the DOL disclosure files.

    Cached: the files are 1.6 GB and reading them takes minutes, while the
    handful of agency rows inside them changes only when a new quarter lands.
    """
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    if not list(LCA.glob("*.xlsx")):
        return {}
    import openpyxl
    #: EVERY COLUMN THROUGH A LIST OF KNOWN SPELLINGS. The FY2013-FY2016
    #: files prefix everything with LCA_CASE_ and call the occupation
    #: LCA_CASE_SOC_NAME. Demanding the modern name made this reader fail on
    #: the first old file and return nothing, and because the result is
    #: cached, the failure was invisible for as long as a cache built from a
    #: newer subset sat on disk. The job titles behind every state agency
    #: came from that partial cache.
    need = {
        "CASE_STATUS": ("CASE_STATUS", "STATUS", "APPROVAL_STATUS"),
        "EMPLOYER_NAME": ("EMPLOYER_NAME", "LCA_CASE_EMPLOYER_NAME", "NAME"),
        "JOB_TITLE": ("JOB_TITLE", "LCA_CASE_JOB_TITLE"),
        "SOC_TITLE": ("SOC_TITLE", "LCA_CASE_SOC_NAME", "SOC_NAME",
                      "OCCUPATIONAL_TITLE"),
        "WAGE_RATE_OF_PAY_FROM": ("WAGE_RATE_OF_PAY_FROM",
                                  "LCA_CASE_WAGE_RATE_FROM", "WAGE_RATE_FROM"),
        "WAGE_UNIT_OF_PAY": ("WAGE_UNIT_OF_PAY", "LCA_CASE_WAGE_RATE_UNIT",
                             "WAGE_RATE_UNIT"),
        "WORKSITE_STATE": ("WORKSITE_STATE", "LCA_CASE_WORKLOC1_STATE",
                           "WORKSITE_STATE_1", "STATE_1", "STATE"),
        "PW_WAGE_LEVEL": ("PW_WAGE_LEVEL", "PW_WAGE_LEVEL_1",
                          "PW_WAGE_SOURCE_1"),
    }
    #: Which columns the reader genuinely cannot work without. A missing
    #: wage level costs a detail; a missing employer name costs the row.
    essential = ("CASE_STATUS", "EMPLOYER_NAME", "WORKSITE_STATE")
    mult = {"year": 1, "hour": 2080, "week": 52, "bi-weekly": 26, "month": 12}
    missing_optional: dict = {}
    out = defaultdict(lambda: {"filings": 0, "titles": defaultdict(int),
                               "wages": [], "levels": defaultdict(int)})
    for path in sorted(LCA.glob("*.xlsx")):
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        hdr = [str(h).strip().upper() if h else "" for h in next(it)]
        idx = {}
        for field, spell in need.items():
            hit = next((s for s in spell if s in hdr), None)
            if hit is None:
                #: Fail loudly for a column the read cannot work without; a
                #: silently missing employer name is a whole file of rows
                #: that quietly never existed. An optional column that is
                #: genuinely absent in an older layout is recorded and the
                #: file is still read, because dropping fifteen years of
                #: filings to preserve one detail is the worse trade.
                if field in essential:
                    wb.close()
                    raise SystemExit(
                        f"FAIL: {path.name} has no column for {field}, which "
                        f"is required. Add its spelling to `need` rather than "
                        f"letting the file be skipped. Nothing written.")
                missing_optional.setdefault(field, []).append(path.name)
                continue
            idx[field] = hdr.index(hit)
        for row in it:
            st_raw = str(row[idx["CASE_STATUS"]] or "").strip().lower()
            #: FY2008 writes "CERTIFIED" as an approval status; later files
            #: use CASE_STATUS. Both mean the same thing and a prefix test
            #: also catches "certified-withdrawn", which is a certification
            #: that was later withdrawn and still happened.
            if not st_raw.startswith("certified"):
                continue
            name = str(row[idx["EMPLOYER_NAME"]] or "").strip().upper()
            if not name or SKIP.search(name):
                continue
            st = agency_state(name)
            if not st or st != str(row[idx["WORKSITE_STATE"]] or "").strip().upper():
                continue
            e = out[f"{st}|{name}"]
            e["filings"] += 1
            raw_title = str((row[idx["JOB_TITLE"]] if "JOB_TITLE" in idx else None) or "").strip()
            # Excel writes some text cells as a formula literal, so the title
            # arrives as ="Transportation Engineer (Civil)" rather than words.
            if raw_title.startswith('="') and raw_title.endswith('"'):
                raw_title = raw_title[2:-1]
            title = raw_title.strip('="').strip().title()
            if title:
                e["titles"][title] += 1
            lvl = re.sub(r"[^IV]", "", str((row[idx["PW_WAGE_LEVEL"]] if "PW_WAGE_LEVEL" in idx else None) or "").upper())
            if lvl:
                e["levels"][lvl] += 1
            try:
                w = float(str((row[idx["WAGE_RATE_OF_PAY_FROM"]] if "WAGE_RATE_OF_PAY_FROM" in idx else None) or "0")
                          .replace(",", "").replace("$", ""))
            except ValueError:
                w = 0
            m = mult.get(str((row[idx["WAGE_UNIT_OF_PAY"]] if "WAGE_UNIT_OF_PAY" in idx else None) or "").strip().lower())
            if w and m and 10_000 < w * m < 1_000_000:
                e["wages"].append(w * m)
        wb.close()
        print(f"  read {path.name}", flush=True)
    packed = {k: {"filings": v["filings"],
                  "titles": sorted(v["titles"].items(), key=lambda kv: -kv[1])[:8],
                  "levels": dict(v["levels"]),
                  "median_wage": (sorted(v["wages"])[len(v["wages"]) // 2]
                                  if v["wages"] else None)}
              for k, v in out.items()}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(packed, indent=1) + "\n")
    return packed



def national_countries() -> dict:
    """Where H-1B visa holders come from -- NATIONALLY, and only nationally.

    THIS CANNOT BE BROKEN DOWN BY EMPLOYER AND THE PAGE MUST NOT IMPLY THAT IT
    CAN. The LCA carries 98 columns and the only ones naming a country are the
    EMPLOYER's, its point of contact's and its attorney's. The Data Hub has
    none at all. An LCA is a filing about a JOB -- an occupation, a wage and a
    worksite -- and is often filed before a particular worker is identified.
    The document that names a beneficiary and their nationality is the I-129,
    and USCIS does not publish at beneficiary level.

    So this block is the State Department's visa issuances by nationality, for
    the whole country. It sits in its own section on the page, with the
    absence stated, because the national split is lopsided enough that a
    reader could easily carry 68% across to a state transport department and
    believe the data said so.
    """
    if not ISSUANCES.exists():
        return {}
    d = json.loads(ISSUANCES.read_text())
    by = (d.get("by_country") or {}).get("H-1B specialty occupation") or {}
    if not by:
        raise SystemExit("FAIL: visa_issuances.json has no H-1B country block. "
                         "Nothing written.")
    years = sorted({y for v in by.values() for y in v})
    latest = years[-1]
    rows = sorted(((c, v.get(latest, 0)) for c, v in by.items()),
                  key=lambda kv: -kv[1])
    rows = [(c, n) for c, n in rows if n > 0]
    total = sum(n for _, n in rows)
    return {
        "source": d.get("source", "US Department of State, NIV issuances"),
        "source_url": d.get("source_url", ""),
        "year": latest,
        "total_issuances": total,
        "countries": len(rows),
        "not_linkable": ("No public file connects a visa holder's nationality "
                         "to an employer. The LCA records the job, not the "
                         "person; the Data Hub records the employer, not the "
                         "person. These shares are national and say nothing "
                         "about any agency on this page."),
        "by_country": [{"country": c, "issuances": n,
                        "share_pct": round(100 * n / total, 2)}
                       for c, n in rows],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-lca", action="store_true",
                    help="add job titles and wages from the DOL files")
    args = ap.parse_args()

    raw, span = read_hub()
    per_state = defaultdict(list)
    for (st, name), e in raw.items():
        per_state[st].append({"name": name, "normal": normalise(name, st and
                              next(k for k, v in ABBR.items() if v == st)),
                              **e})
    lca = read_lca() if args.with_lca else {}
    # Each LCA record belongs to one agency. Claimed records are removed so a
    # second group with a near-identical name cannot report the same filings.
    unclaimed = set(lca)

    states = []
    for st, variants in per_state.items():
        agencies = group_variants(variants)
        for a in agencies:
            a["years"] = sorted(a["years"])
            a["cities"] = sorted(a["cities"])
            # THE DATA HUB TRUNCATES EMPLOYER NAMES AT ABOUT 34 CHARACTERS,
            # so "STATE OF WASHINGTON DEPARTMENT OF CORRECTIONS" arrives as
            # "STATE OF WASHINGTON DEPARTMENT OF" and is indistinguishable
            # from that state's departments of Ecology, Health and Revenue.
            #
            # The previous version scored every prefix match with
            # len(a["normal"]) -- the same value for all of them -- so the
            # ties were broken by dictionary order and a truncated name
            # silently claimed ONE arbitrary department, hiding the others.
            # Washington's Department of Corrections was invisible that way.
            #
            # Now: one candidate claims the name and lends its full spelling
            # to the display. Several candidates means the Hub row genuinely
            # cannot be resolved, which is recorded rather than guessed.
            cands = []
            for k in list(unclaimed):
                if not k.startswith(st + "|"):
                    continue
                raw = k.split("|", 1)[1]
                norm = normalise(raw, next(n for n, ab in ABBR.items()
                                           if ab == st))
                if len(a["normal"]) >= 5 and norm.startswith(a["normal"]):
                    cands.append((k, raw, len(norm)))
                elif len(norm) >= 5 and a["normal"].startswith(norm):
                    cands.append((k, raw, len(norm)))
            exact = [c for c in cands
                     if normalise(c[1], next(n for n, ab in ABBR.items()
                                             if ab == st)) == a["normal"]]
            chosen = exact or cands
            if len(chosen) == 1:
                k, raw, _ = chosen[0]
                a["lca"] = lca[k]
                unclaimed.discard(k)
                #: Adopt the fuller spelling. The Hub row said
                #: "STATE OF WASHINGTON DEPARTMENT OF"; the LCA says which
                #: department, and that is the whole point of the join.
                if len(raw) > len(a["name"]):
                    a["resolved_from"] = a["name"]
                    a["name"] = raw.upper()
            elif len(chosen) > 1:
                a["ambiguous"] = sorted({c[1].upper() for c in chosen})[:8]
            if len(a["normal"]) < 5:
                #: The Hub truncates at about 34 characters and the
                #: normaliser strips STATE OF, DEPARTMENT and OF, so
                #: "STATE OF WASHINGTON DEPARTMENT OF" reduces to nothing at
                #: all. The approvals are real; the department is simply not
                #: recoverable from this file. Saying that is the finding --
                #: leaving the row looking like a named agency is not.
                a["unidentified"] = True
            a.pop("normal", None)
        agencies.sort(key=lambda a: -(a["initial"] + a["continuing"]))
        #: Every certified LCA in this state that no Hub row claimed. These
        #: are agencies the Hub cannot show separately, usually because a
        #: longer name was truncated into an unidentifiable stub. Washington
        #: State Department of Corrections is one: it filed, and it appears
        #: in the approval data only inside "STATE OF WASHINGTON DEPARTMENT
        #: OF". Publishing the LCA name is the only way a reader sees it.
        leftover = []
        for k in sorted(unclaimed):
            if not k.startswith(st + "|"):
                continue
            leftover.append({"name": k.split("|", 1)[1].upper(), **lca[k]})
        leftover.sort(key=lambda d: -d.get("filings", 0))
        for k in [k for k in list(unclaimed) if k.startswith(st + "|")]:
            unclaimed.discard(k)
        states.append({
            "lca_only": leftover,
            "state": st,
            "initial": sum(a["initial"] for a in agencies),
            "continuing": sum(a["continuing"] for a in agencies),
            "denied": sum(a["denied"] for a in agencies),
            "agencies": len(agencies),
            "name_variants": len(variants),
            "detail": agencies,
        })
    states.sort(key=lambda s: -(s["initial"] + s["continuing"]))

    out = {
        "source": ("USCIS H-1B Employer Data Hub" +
                   (", plus US DOL OFLC LCA disclosure files" if lca else "")),
        "source_url": "https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub",
        "window": f"FY{span['first']}-FY{span['last']}",
        "files_read": span["files"],
        "totals": {
            "initial_approvals": sum(s["initial"] for s in states),
            "continuing_approvals": sum(s["continuing"] for s in states),
            "denials": sum(s["denied"] for s in states),
            "states": len(states),
            "agencies": sum(s["agencies"] for s in states),
            "name_variants": sum(s["name_variants"] for s in states),
        },
        "caveats": [
            "Initial and continuing approvals are never added. A continuing "
            "approval is the same person renewed; adding them counts one "
            "worker once a year for as long as they stay.",
            "Employer names are truncated at about 34 characters in the older "
            "files, so one agency can appear several ways. Variants are "
            "grouped when one name is a prefix of another, and every raw name "
            "as filed is published beside the group.",
            "An agency is identified from the employer name on the form. One "
            "that files under a name without its state in it is not counted, "
            "so these figures are a floor.",
            "Public universities, counties, cities and school districts are "
            "excluded. A public university is a state institution too; it is "
            "measured elsewhere on this site.",
            "Sponsoring an H-1B is lawful, and nothing here says otherwise.",
        ],
        "states": states,
        "national_origin": national_countries(),
    }
    write_json(OUT, out, indent=1)
    t = out["totals"]
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {t['initial_approvals']:,} initial and {t['continuing_approvals']:,} "
          f"continuing approvals, {out['window']}")
    no = out["national_origin"]
    if no:
        print(f"  national origin: {no['countries']} countries, "
              f"{no['total_issuances']:,} H-1B visas issued in {no['year']}")
    print(f"  {t['agencies']} agencies in {t['states']} states "
          f"({t['name_variants']} raw name variants)")
    for s in states[:6]:
        print(f"    {s['state']}  {s['initial']:>5} initial {s['continuing']:>5} "
              f"continuing  {s['agencies']} agencies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
