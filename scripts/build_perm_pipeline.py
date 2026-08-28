#!/usr/bin/env python3
"""PERM labour certifications: the last published step before a green card.

PERM is where an employer certifies that no U.S. worker was available for a
job it wants to fill permanently. The disclosure file carries something no
other source in this project does: CLASS_OF_ADMISSION, the status the
beneficiary held when the application was filed.

That single column is a real piece of the pipeline linkage the briefing's
data-needs page asks for. It cannot follow a person across datasets, but it
does show what status people were in at the point of seeking permanent
residence -- how many arrived through F-1 and OPT, how many through H-1B,
how many through J-1.

WHAT IT IS NOT. A certification is not a green card: it is a Department of
Labor step, after which USCIS must approve an I-140 and a visa number must
be available, which for some countries takes years. Counts are applications,
not people, and one person may appear more than once.

Usage:
  python3 scripts/build_perm_pipeline.py
"""
from __future__ import annotations

import json
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "h1b"
OUT = SRC / "perm_pipeline.json"
ENTITY_MAP = ROOT / "pipeline" / "entity_map.json"

WANT = ("CASE_STATUS", "EMPLOYER_NAME", "COUNTRY_OF_CITIZENSHIP",
        "CLASS_OF_ADMISSION", "PW_SOC_TITLE", "JOB_TITLE", "MINIMUM_EDUCATION")


def main() -> int:
    import openpyxl
    files = sorted(SRC.glob("perm_*.xlsx"))
    if not files:
        print("  no perm_*.xlsx found")
        return 1

    emap = {k.upper(): v for k, v in json.loads(ENTITY_MAP.read_text()).items()} \
        if ENTITY_MAP.exists() else {}

    status = Counter()
    admission = Counter()
    admission_certified = Counter()
    country = Counter()
    soc = Counter()
    uni_rows = defaultdict(lambda: Counter())
    total = 0

    for path in files:
        ws = openpyxl.load_workbook(path, read_only=True).active
        rows = ws.iter_rows(values_only=True)
        hdr = [str(h) if h is not None else "" for h in next(rows)]
        idx = {name: hdr.index(name) for name in WANT if name in hdr}
        missing = [w for w in WANT if w not in idx]
        if missing:
            print(f"  {path.name}: missing columns {missing}")
        for row in rows:
            total += 1
            def g(col):
                i = idx.get(col)
                v = row[i] if i is not None and i < len(row) else None
                return str(v).strip() if v is not None else ""
            st = g("CASE_STATUS").upper()
            status[st] += 1
            adm = g("CLASS_OF_ADMISSION").upper() or "(not stated)"
            admission[adm] += 1
            if st.startswith("CERTIFIED"):
                admission_certified[adm] += 1
            if c := g("COUNTRY_OF_CITIZENSHIP").upper():
                country[c] += 1
            if s := g("PW_SOC_TITLE"):
                soc[s] += 1
            key = emap.get(g("EMPLOYER_NAME").upper())
            if key:
                uni_rows[key][st] += 1

    def top(counter, n=12):
        return [{"value": k, "count": v,
                 "share": round(100 * v / sum(counter.values()), 1)}
                for k, v in counter.most_common(n)]

    doc = {
        "_comment": ("PERM labour certifications. CLASS_OF_ADMISSION is the "
                     "status held when the application was filed -- the one "
                     "published field that shows which visa route people are on "
                     "when they seek permanent residence. A certification is NOT "
                     "a green card: USCIS must still approve an I-140 and a visa "
                     "number must be available. Counts are applications, not "
                     "people."),
        "source": "US DOL Office of Foreign Labor Certification, PERM disclosure data",
        "files": [f.name for f in files],
        "applications": total,
        "case_status": top(status, 8),
        "class_of_admission": top(admission),
        "class_of_admission_certified_only": top(admission_certified),
        "country_of_citizenship": top(country),
        "occupation": top(soc),
        "universities": {k: dict(v) for k, v in sorted(
            uni_rows.items(), key=lambda kv: -sum(kv[1].values()))},
    }
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {total:,} applications across {len(files)} file(s)")
    print("  status:", ", ".join(f"{r['value']} {r['count']:,}" for r in doc["case_status"][:3]))
    print("  class of admission when filed:")
    for r in doc["class_of_admission"][:8]:
        print(f"     {r['value'][:22]:24} {r['count']:>7,}  {r['share']:>5.1f}%")
    print("  top countries:", ", ".join(
        f"{r['value'].title()} {r['share']}%" for r in doc["country_of_citizenship"][:4]))
    print(f"  universities matched: {len(uni_rows)}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
