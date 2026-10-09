#!/usr/bin/env python3
"""Who files for the unexpected jobs, and what countries they come from.

WHY THIS EXISTS, AND WHY IT CANNOT COME FROM THE H-1B FILES

The H-1B explorer can say that gas stations filed 1,675 certified
applications and name the companies. It cannot say where the workers came
from, because the Labor Condition Application does not record a nationality.
No H-1B file does, at any level below the national total.

PERM does. The permanent-residence file carries country of citizenship and,
from FY2015, country of birth -- and it also carries the employer's NAICS
code, which means it can be grouped by exactly the same industry definitions
the H-1B pages use. That makes it the only way to answer "who is filing for
gas station work, and where are those people from" from public records.

WHAT THIS IS NOT. PERM is a different and much smaller programme than H-1B:
it is the green-card step, and most H-1B workers never file one. The counts
here are NOT a subset of the H-1B counts and must never be presented as a
share of them. They answer a different question about the same industries.

THE COLUMN IS SPELLED FIVE WAYS. 2007_NAICS_US_CODE, "2007 NAICS US CODE"
with spaces, NAICS_US_CODE, NAICS_CODE and EMP_NAICS, depending on the year.
Reading one spelling returns a silent zero for most of the archive, which is
the failure this repo has hit three times now, so a file that matches none of
them is reported rather than skipped quietly.

Usage:
    python3 scripts/build_perm_by_industry.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
PERM = ROOT / "data" / "h1b" / "perm"
EXTRA = (ROOT / "data" / "h1b" / "perm_fy2024_q4.xlsx",)
OUT = ROOT / "site" / "data" / "perm_by_industry.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                          # noqa: E402
from build_h1b_by_industry import GROUPS as NAICS_GROUPS     # noqa: E402
from build_h1b_by_occupation import GROUPS as SOC_GROUPS      # noqa: E402
from build_public_employer_perm import (                     # noqa: E402
    annual_wage, clean, fy_of, normalise_state,
)

NEED = {
    "CASE_STATUS": ("CASE_STATUS", "STATUS"),
    "CASE_NUMBER": ("CASE_NUMBER",),
    "EMPLOYER_NAME": ("EMPLOYER_NAME",),
    "CITIZENSHIP": ("COUNTRY_OF_CITIZENSHIP",),
    "BIRTH_COUNTRY": ("FOREIGN_WORKER_BIRTH_COUNTRY", "FW_INFO_BIRTH_COUNTRY"),
    "JOB_TITLE": ("JOB_TITLE", "JOB_INFO_JOB_TITLE", "PW_JOB_TITLE_9089"),
    "CLASS_OF_ADMISSION": ("CLASS_OF_ADMISSION",),
    "WORK_STATE": ("WORKSITE_STATE", "JOB_INFO_WORK_STATE"),
    #: Five spellings, one column.
    "NAICS": ("EMP_NAICS", "NAICS_CODE", "NAICS_US_CODE",
              "2007_NAICS_US_CODE", "2007 NAICS US CODE"),
    #: PERM carries the prevailing-wage SOC code, which lets the same file
    #: answer the occupation questions as well as the industry ones. Without
    #: it the custodial, food-service and personal-care cases could name the
    #: employers and never the countries.
    "SOC": ("PW_SOC_CODE", "PW_SOC_CODE_9089", "OCCUPATION_CODE"),
    "WAGE_FROM": ("WAGE_OFFER_FROM_9089", "WAGE_OFFERED_FROM_9089",
                  "OFFERED_WAGE", "WAGE_OFFER_FROM"),
    "WAGE_UNIT": ("WAGE_OFFER_UNIT_OF_PAY_9089", "WAGE_OFFERED_UNIT_OF_PAY_9089",
                  "OFFERED_WAGE_UNIT", "WAGE_OFFER_UNIT_OF_PAY"),
}
REQUIRED = ("EMPLOYER_NAME", "CITIZENSHIP")

#: Inverted from the H-1B definitions so the two pages mean the same thing
#: by "gas stations" and by "custodial".
CODE_TO_GROUP = {c: k for k, spec in NAICS_GROUPS.items()
                 for c in spec["codes"]}
SOC_PREFIXES = [(p, k) for k, spec in SOC_GROUPS.items()
                for p in spec.get("soc", ())]
#: Longest prefix first, so 25-2 beats 25- when both are declared.
SOC_PREFIXES.sort(key=lambda t: -len(t[0]))

LABELS = {**{k: v["label"] for k, v in NAICS_GROUPS.items()},
          **{k: v["label"] for k, v in SOC_GROUPS.items()}}


def naics6(raw: str) -> str:
    v = "".join(ch for ch in str(raw) if ch.isdigit())
    return v[:6]


def soc_group(raw: str) -> str | None:
    v = str(raw or "").strip().upper()
    if not v:
        return None
    for prefix, key in SOC_PREFIXES:
        if v.startswith(prefix):
            return key
    return None


def main() -> int:
    files = sorted(set(list(PERM.glob("*.xlsx"))
                       + [p for p in EXTRA if p.exists()]))
    if not files:
        print(f"No PERM files in {PERM.relative_to(ROOT)}. Restore with:\n"
              f"  aws s3 sync s3://phd-demographics-raw-data/data/h1b/perm/ "
              f"{PERM.relative_to(ROOT)}/ --profile personal")
        return 1

    rows, seen, skipped = [], set(), []
    scanned = dupes = 0
    for path in files:
        fy = fy_of(path)
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        hdr = [str(c or "").strip().upper() for c in next(it)]
        idx = {}
        for field, names in NEED.items():
            hit = next((n for n in names if n.upper() in hdr), None)
            if hit:
                idx[field] = hdr.index(hit.upper())
        missing = [c for c in REQUIRED if c not in idx]
        if missing:
            wb.close()
            why = f"no column for {', '.join(missing)}"
            skipped.append({"file": path.name, "fiscal_year": fy, "reason": why})
            print(f"  SKIP FY{fy} {path.name}: {why}", flush=True)
            continue

        got = 0
        for row in it:
            scanned += 1
            cn = clean(row[idx["CASE_NUMBER"]]).upper() if "CASE_NUMBER" in idx else ""
            if cn:
                if cn in seen:
                    dupes += 1
                    continue
                seen.add(cn)
            status = (clean(row[idx["CASE_STATUS"]]).upper()
                      if "CASE_STATUS" in idx else "CERTIFIED")
            if not status.startswith("CERTIFIED"):
                continue
            #: A filing can land in an industry group and an occupation
            #: group at once -- a school custodian is both. They are counted
            #: in each, because the two groupings answer different questions
            #: and neither is a subset of the other. Summing across groups
            #: would double count and the page never does.
            hits = []
            if "NAICS" in idx:
                n = CODE_TO_GROUP.get(naics6(row[idx["NAICS"]]))
                if n:
                    hits.append(n)
            if "SOC" in idx:
                sgrp = soc_group(row[idx["SOC"]])
                if sgrp:
                    hits.append(sgrp)
            if not hits:
                continue
            g = lambda k: clean(row[idx[k]]) if k in idx else ""   # noqa: E731
            rows.append({
                "fiscal_year": fy, "groups": hits,
                "employer": g("EMPLOYER_NAME").upper(),
                "job_title": g("JOB_TITLE").title(),
                "citizenship": g("CITIZENSHIP").title(),
                "birth_country": g("BIRTH_COUNTRY").title(),
                "visa_held": g("CLASS_OF_ADMISSION").upper(),
                "state": normalise_state(g("WORK_STATE")),
                "wage": annual_wage(g("WAGE_FROM"), g("WAGE_UNIT")),
            })
            got += 1
        wb.close()
        print(f"  FY{fy} {path.name}: {got:,} rows in a tracked industry",
              flush=True)

    groups = {}
    for grp in sorted({g for r in rows for g in r["groups"]}):
        mine = [r for r in rows if grp in r["groups"]]
        emp = defaultdict(int)
        cit = defaultdict(int)
        title = defaultdict(int)
        by_emp_cit = defaultdict(lambda: defaultdict(int))
        for r in mine:
            emp[r["employer"]] += 1
            if r["citizenship"]:
                cit[r["citizenship"]] += 1
                by_emp_cit[r["employer"]][r["citizenship"]] += 1
            if r["job_title"]:
                title[r["job_title"]] += 1
        wages = sorted(r["wage"] for r in mine if r["wage"])
        top = sorted(emp.items(), key=lambda kv: -kv[1])[:25]
        groups[grp] = {
            "label": LABELS.get(grp, grp),
            "filings": len(mine),
            "employers": len(emp),
            "citizenships": len(cit),
            "median_wage": wages[len(wages) // 2] if wages else None,
            "citizenship": dict(sorted(cit.items(), key=lambda kv: -kv[1])),
            "top_titles": sorted(title.items(), key=lambda kv: -kv[1])[:20],
            "top_employers": top,
            #: The cross a reader actually wants: this employer, these
            #: countries. Published whole per employer, not topped, because
            #: one filing from somewhere unexpected is the point.
            "employer_citizenship": {
                e: dict(sorted(by_emp_cit[e].items(), key=lambda kv: -kv[1]))
                for e, _ in top},
            "years": {str(y): sum(1 for r in mine if r["fiscal_year"] == y)
                      for y in sorted({r["fiscal_year"] for r in mine})},
        }

    out = {
        "source": "US DOL OFLC, PERM permanent labor certification disclosure files",
        "source_url": "https://www.dol.gov/agencies/eta/foreign-labor/performance",
        "files_read": [p.name for p in files
                       if p.name not in {s["file"] for s in skipped}],
        "files_skipped": skipped,
        "rows_scanned": scanned,
        "duplicate_rows_skipped": dupes,
        "caveats": [
            "PERM is the permanent-residence step and is a different, much "
            "smaller program than H-1B. These counts are NOT a subset of the "
            "H-1B counts on the same industries and must not be shown as a "
            "share of them.",
            "Industry is the employer's own NAICS code on its own filing. A "
            "firm that owns gas stations and does something else too files "
            "everything under one code.",
            "Citizenship is published from FY2013 and country of birth from "
            "FY2015. Both were removed after FY2024, so this series has "
            "ended.",
            "Certified filings only. A certification is permission to "
            "sponsor, not a hire.",
            "No worker is named in the federal file and none is named here.",
        ],
        "groups": groups,
    }
    write_text(OUT, json.dumps(out, indent=1))
    print(f"\nWrote {OUT.relative_to(ROOT)}")
    for k, v in sorted(groups.items(), key=lambda kv: -kv[1]["filings"]):
        top = list(v["citizenship"].items())[:3]
        print(f"    {k:28} {v['filings']:6,} filings  "
              f"{v['employers']:5,} employers  top: {top}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
