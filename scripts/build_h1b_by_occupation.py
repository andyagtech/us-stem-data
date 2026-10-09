#!/usr/bin/env python3
"""H-1B by the job, not the industry.

WHY A SECOND VIEW

build_h1b_by_industry.py asks what the EMPLOYER does. This asks what the WORKER
was hired to do, which is a different question and sometimes a more revealing
one. A school district is one industry; the teachers, the psychologists, the
IT staff and the custodians inside it are four occupations with four different
stories.

THE SPECIALTY-OCCUPATION TEST IS THE POINT

An H-1B is for a "specialty occupation" -- one that normally requires at least
a bachelor's degree in a specific field. So the interesting question for a job
like cleaning or food service is not how many there are but whether there are
any at all, and what the employer called the role when it filed. A certified
application for a job that does not obviously need a degree is worth looking
at. It is NOT evidence of wrongdoing: DOL certifies the wage and the working
conditions, not the degree test, which USCIS applies later on the I-129. A
certified LCA for a custodian means an employer asked, not that anyone was
admitted.

Occupations are counted from the employer's own SOC code and title, and job
titles are kept as filed so a reader can see the words the employer chose.

Output: site/data/h1b_by_occupation.json

Usage:
    python3 scripts/build_h1b_by_occupation.py
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LCA = ROOT / "data" / "h1b" / "lca"
OUT = ROOT / "site" / "data" / "h1b_by_occupation.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402
from build_visa_bodyshops import drop_contained              # noqa: E402

#: SOC major groups and the specific codes worth naming. A code is matched on
#: its prefix, so 37-2 catches every cleaning occupation whatever the suffix.
GROUPS = {
    "teachers_k12": {
        "label": "Primary, secondary and special education teachers",
        "soc": ("25-2",),
    },
    "teachers_post": {
        "label": "Postsecondary teachers",
        "soc": ("25-1",),
    },
    "education_other": {
        "label": "Librarians, counsellors and other education roles",
        "soc": ("25-3", "25-4", "25-9", "21-1012"),
    },
    "custodial": {
        "label": "Building cleaning and maintenance",
        "soc": ("37-",),
    },
    "food_service": {
        "label": "Food preparation and serving",
        "soc": ("35-",),
    },
    "healthcare_practitioners": {
        "label": "Healthcare practitioners",
        "soc": ("29-",),
    },
    "healthcare_support": {
        "label": "Healthcare support",
        "soc": ("31-",),
    },
    "protective_service": {
        "label": "Protective service",
        "soc": ("33-",),
    },
    "transport_material": {
        "label": "Transport and material moving",
        "soc": ("53-",),
    },
    "construction": {
        "label": "Construction and extraction",
        "soc": ("47-",),
    },
    "personal_care": {
        "label": "Personal care and service",
        "soc": ("39-",),
    },
    "farming": {
        "label": "Farming, fishing and forestry",
        "soc": ("45-",),
    },
}

NEED = {
    "CASE_STATUS": ("CASE_STATUS", "STATUS", "APPROVAL_STATUS"),
    "EMPLOYER_NAME": ("EMPLOYER_NAME", "LCA_CASE_EMPLOYER_NAME", "NAME"),
    "SOC_CODE": ("SOC_CODE", "LCA_CASE_SOC_CODE"),
    "SOC_TITLE": ("SOC_TITLE", "LCA_CASE_SOC_NAME", "LCA_CASE_SOC_TITLE"),
    "JOB_TITLE": ("JOB_TITLE", "LCA_CASE_JOB_TITLE"),
    "NAICS_CODE": ("NAICS_CODE", "LCA_CASE_NAICS_CODE", "NAIC_CODE"),
    "WAGE_RATE_OF_PAY_FROM": ("WAGE_RATE_OF_PAY_FROM", "LCA_CASE_WAGE_RATE_FROM"),
    "WAGE_UNIT_OF_PAY": ("WAGE_UNIT_OF_PAY", "LCA_CASE_WAGE_RATE_UNIT"),
    "WORKSITE_STATE": ("WORKSITE_STATE", "LCA_CASE_WORKLOC1_STATE", "WORKSITE_STATE_1"),
}
REQUIRED = ("CASE_STATUS", "EMPLOYER_NAME", "SOC_CODE")
CASE_KEY = ("CASE_NUMBER", "LCA_CASE_NUMBER")


def clean(v) -> str:
    t = str(v or "").strip()
    if t.startswith('="') and t.endswith('"'):
        t = t[2:-1]
    return t.strip('="').strip()


def annual(wage, unit):
    try:
        w = float(str(wage).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None
    m = {"year": 1, "hour": 2080, "week": 52, "bi-weekly": 26,
         "month": 12}.get(str(unit or "").strip().lower())
    return w * m if m and w else None


def main() -> int:
    files = sorted(LCA.glob("*.xlsx"))
    if not files:
        raise SystemExit(f"FAIL: no LCA files in {LCA}.")
    files, _spans = drop_contained(files, strict=False)

    import openpyxl
    socs: dict[str, dict] = defaultdict(
        lambda: {"filings": 0, "wages": [], "titles": defaultdict(int),
                 "employers": defaultdict(int), "states": defaultdict(int),
                 "naics": defaultdict(int), "soc_title": ""})
    skipped, total, dupes = [], 0, 0
    seen: set = set()
    for path in files:
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
            skipped.append({"file": path.name,
                            "reason": f"no column for {', '.join(missing)}"})
            print(f"  SKIP {path.name}: {missing}", flush=True)
            continue
        ci = next((hdr.index(c) for c in CASE_KEY if c in hdr), None)
        for row in it:
            # See the note in build_h1b_by_industry: overlapping releases are
            # resolved by case number, which is exact.
            if ci is not None:
                cn = str(row[ci] or "").strip().upper()
                if cn:
                    if cn in seen:
                        dupes += 1
                        continue
                    seen.add(cn)
            if clean(row[idx["CASE_STATUS"]]).lower() != "certified":
                continue
            code = clean(row[idx["SOC_CODE"]]).upper().replace(".", "-")
            m = re.match(r"(\d{2})-?(\d{4})", code)
            if not m:
                continue
            code = f"{m.group(1)}-{m.group(2)}"
            total += 1
            e = socs[code]
            e["filings"] += 1
            if not e["soc_title"] and "SOC_TITLE" in idx:
                e["soc_title"] = clean(row[idx["SOC_TITLE"]]).title()
            if "JOB_TITLE" in idx:
                t = clean(row[idx["JOB_TITLE"]]).title()
                if t:
                    e["titles"][t] += 1
            n = clean(row[idx["EMPLOYER_NAME"]]).upper()
            if n:
                e["employers"][n] += 1
            if "WORKSITE_STATE" in idx:
                st = clean(row[idx["WORKSITE_STATE"]]).upper()
                if st:
                    e["states"][st] += 1
            if "NAICS_CODE" in idx:
                nc = re.sub(r"\D", "", clean(row[idx["NAICS_CODE"]]))[:6]
                if nc:
                    e["naics"][nc] += 1
            if "WAGE_RATE_OF_PAY_FROM" in idx:
                w = annual(row[idx["WAGE_RATE_OF_PAY_FROM"]],
                           row[idx["WAGE_UNIT_OF_PAY"]] if "WAGE_UNIT_OF_PAY" in idx else "year")
                if w and 5_000 < w < 1_000_000 and len(e["wages"]) < 40_000:
                    e["wages"].append(w)
        wb.close()
        print(f"  read {path.name}", flush=True)

    def pack(e):
        ws = sorted(e["wages"])
        return {"filings": e["filings"], "soc_title": e["soc_title"],
                "employers": len(e["employers"]),
                "median_wage": round(ws[len(ws) // 2]) if ws else None,
                "top_titles": sorted(e["titles"].items(), key=lambda kv: -kv[1])[:12],
                "top_employers": sorted(e["employers"].items(), key=lambda kv: -kv[1])[:15],
                "top_states": sorted(e["states"].items(), key=lambda kv: -kv[1])[:10],
                "top_naics": sorted(e["naics"].items(), key=lambda kv: -kv[1])[:8]}

    groups = {}
    for key, spec in GROUPS.items():
        merged = {"filings": 0, "wages": [], "titles": defaultdict(int),
                  "employers": defaultdict(int), "states": defaultdict(int),
                  "naics": defaultdict(int), "soc_title": spec["label"]}
        codes = []
        for code, e in socs.items():
            if not any(code.startswith(p) for p in spec["soc"]):
                continue
            codes.append(code)
            merged["filings"] += e["filings"]
            merged["wages"] += e["wages"]
            for f in ("titles", "employers", "states", "naics"):
                for k, v in e[f].items():
                    merged[f][k] += v
        groups[key] = {"label": spec["label"], "soc_prefixes": list(spec["soc"]),
                       "codes_present": sorted(codes), **pack(merged)}

    out = {
        "source": "US DOL OFLC, H-1B LCA disclosure files",
        "source_url": "https://www.dol.gov/agencies/eta/foreign-labor/performance",
        "files": [f.name for f in files],
        "files_skipped": skipped,
        "certified_filings": total,
        "duplicate_rows_skipped": dupes,
        "distinct_soc_codes": len(socs),
        "caveats": [
            "The occupation code is the employer's own answer on its own form.",
            "An H-1B is for a specialty occupation, one normally requiring a "
            "bachelor's degree in a specific field. DOL certifies the wage and "
            "the working conditions; USCIS applies the degree test later, on "
            "the petition. A certified application for a job that does not "
            "obviously need a degree means an employer ASKED. It is not proof "
            "that anyone was admitted, and it is not evidence of wrongdoing.",
            "Certified applications only, counted by application rather than "
            "by position.",
            "Job titles are kept as the employer wrote them.",
        ],
        "groups": groups,
        "by_soc": {c: pack(e) for c, e in
                   sorted(socs.items(), key=lambda kv: -kv[1]["filings"])},
    }
    write_json(OUT, out, indent=1)
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {total:,} certified applications across {len(socs):,} SOC codes")
    print(f"  {dupes:,} duplicate rows skipped by case number")
    for k, g in groups.items():
        print(f"    {g['label'][:46]:<48}{g['filings']:>9,} filings  "
              f"{g['employers']:>6,} employers  "
              f"{('$' + format(g['median_wage'], ',')) if g['median_wage'] else '-':>10}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
