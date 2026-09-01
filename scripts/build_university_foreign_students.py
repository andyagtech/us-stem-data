#!/usr/bin/env python3
"""Which universities enrol the most foreign students.

The obvious question -- which universities receive the most F-1 visas -- has
no published answer. State issues visas by consulate and nationality, not by
school, and SEVP publishes school-level figures only for OPT. What CAN be
answered is who ENROLS them, from IPEDS, and who places the most graduates
into STEM OPT, from SEVP.

THREE MEASURES, THREE POPULATIONS. IPEDS non-resident enrolment covers every
level and field and counts people enrolled in a fall term. SEVP's table
counts STEM OPT authorisations, which are graduates already working. The GSS
ranking elsewhere covers science, engineering and health graduate students
only. They rank institutions differently because they measure different
things, and are reported side by side rather than blended.

NON-RESIDENT IS A VISA CATEGORY. A permanent resident is counted under their
race in IPEDS and appears here as domestic, so every share is a floor on the
foreign-born proportion.

Usage:
  python3 scripts/build_university_foreign_students.py
"""
from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EF = ROOT / "data" / "ipeds_enrollment"
HD = ROOT / "data" / "ipeds" / "hd2024.csv"
SEVP = ROOT / "data" / "sevp" / "2024_top100_schools_stemopt.pdf"
OUT = ROOT / "site" / "data" / "university_foreign_students.json"
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

LEVELS = {12: "graduate", 2: "undergraduate", 1: "all"}


def institutions() -> dict[str, dict]:
    out = {}
    with open(HD, encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            uid = (r.get("UNITID") or "").strip()
            if uid:
                out[uid] = {"name": (r.get("INSTNM") or "").strip(),
                            "state": (r.get("STABBR") or "").strip(),
                            "control": (r.get("CONTROL") or "").strip()}
    return out


def enrolment(inst: dict) -> tuple[dict, int]:
    """UNITID -> level -> (total, non-resident), for the latest EF year."""
    files = sorted(EF.glob("EF*A.zip"))
    if not files:
        return {}, 0
    path = files[-1]
    year = int(path.stem[2:6])
    out: dict[str, dict] = {}
    with zipfile.ZipFile(path) as z:
        inner = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(inner) as fh:
            for r in csv.DictReader(io.TextIOWrapper(
                    fh, encoding="utf-8-sig", errors="replace")):
                try:
                    lv = int(float(r.get("EFALEVEL") or 0))
                    tot = int(float(r.get("EFTOTLT") or 0))
                    nra = int(float(r.get("EFNRALT") or 0))
                except (TypeError, ValueError):
                    continue
                if lv not in LEVELS or tot <= 0:
                    continue
                uid = (r.get("UNITID") or "").strip()
                if uid not in inst:
                    continue
                out.setdefault(uid, {})[LEVELS[lv]] = {
                    "total": tot, "non_resident": nra,
                    "share": round(100 * nra / tot, 1)}
    return out, year


def stem_opt() -> list[dict]:
    """SEVP's top-100 campuses by STEM OPT authorisations."""
    if not SEVP.exists():
        return []
    r = subprocess.run(["pdftotext", "-layout", str(SEVP), "-"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return []
    rows = []
    for line in r.stdout.splitlines():
        # "<campus>  <school>  <employed>  <authorisations>"
        m = re.match(r"^(.{5,70}?)\s{2,}.{5,70}?\s{2,}([\d,]+)\s+([\d,]+)\s*$", line)
        if not m:
            continue
        try:
            rows.append({"campus": m.group(1).strip(),
                         "students_employed": int(m.group(2).replace(",", "")),
                         "authorisations": int(m.group(3).replace(",", ""))})
        except ValueError:
            continue
    return rows


def main() -> int:
    if not HD.exists():
        print(f"  missing {HD.relative_to(ROOT)}")
        return 1
    inst = institutions()
    enr, year = enrolment(inst)
    if not enr:
        print(f"  no enrolment files in {EF.relative_to(ROOT)}")
        return 1
    opt = stem_opt()

    rows = []
    for uid, lv in enr.items():
        meta = inst[uid]
        rec = {"unitid": uid, "institution": meta["name"],
               "state": meta["state"],
               "control": "public" if meta["control"] == "1" else "private"}
        for level, v in lv.items():
            rec[level] = v
        if "all" in lv:
            rows.append(rec)

    def top(level: str, key: str, floor: int = 0):
        have = [r for r in rows if level in r and r[level]["total"] >= floor]
        return sorted(have, key=lambda r: -r[level][key])[:30]

    national = {}
    for level in LEVELS.values():
        t = sum(r[level]["total"] for r in rows if level in r)
        n = sum(r[level]["non_resident"] for r in rows if level in r)
        if t:
            national[level] = {"total": t, "non_resident": n,
                               "share": round(100 * n / t, 1),
                               "institutions": sum(1 for r in rows if level in r)}

    doc = {
        "_comment": (
            "Non-resident enrolment by institution (IPEDS Fall Enrolment, "
            f"{year}) with SEVP's top campuses by STEM OPT authorisation "
            "beside it. F-1 ISSUANCE BY UNIVERSITY IS NOT PUBLISHED: State "
            "reports visas by consulate and nationality, never by school, and "
            "SEVP publishes school-level figures only for OPT. So this "
            "answers who ENROLS foreign students, not who receives F-1 visas, "
            "and the two are not the same question. THE THREE MEASURES COUNT "
            "DIFFERENT POPULATIONS -- IPEDS counts everyone enrolled in a "
            "fall term at every level and field, SEVP counts graduates "
            "already working on STEM OPT, and the GSS ranking elsewhere "
            "covers science, engineering and health graduate students only -- "
            "so they rank institutions differently and are reported side by "
            "side rather than blended. NON-RESIDENT IS A VISA CATEGORY: "
            "permanent residents are counted under their race and appear as "
            "domestic, so every share here is a floor. Ranked by COUNT rather "
            "than share, because share rankings at this level are dominated "
            "by very small institutions."),
        "sources": {
            "enrolment": f"NCES IPEDS Fall Enrolment {year}",
            "stem_opt": "DHS SEVP, 2024 top 100 school campuses with STEM OPT",
        },
        "enrolment_year": year,
        "institutions": len(rows),
        "national": national,
        "largest_by_non_resident_total": [
            {"institution": r["institution"], "state": r["state"],
             "control": r["control"],
             "non_resident": r["all"]["non_resident"],
             "total": r["all"]["total"], "share": r["all"]["share"],
             "graduate_non_resident": r.get("graduate", {}).get("non_resident")}
            for r in top("all", "non_resident")],
        "largest_by_graduate_non_resident": [
            {"institution": r["institution"], "state": r["state"],
             "control": r["control"],
             "non_resident": r["graduate"]["non_resident"],
             "total": r["graduate"]["total"], "share": r["graduate"]["share"]}
            for r in top("graduate", "non_resident")],
        "highest_share_large_institutions": [
            {"institution": r["institution"], "state": r["state"],
             "share": r["all"]["share"], "non_resident": r["all"]["non_resident"],
             "total": r["all"]["total"]}
            for r in sorted((r for r in rows if r["all"]["total"] >= 5000),
                            key=lambda r: -r["all"]["share"])[:25]],
        "stem_opt_top_campuses": opt[:40],
    }
    write_json(OUT, doc)

    print(f"  {len(rows):,} institutions, IPEDS {year}")
    for level, n in national.items():
        print(f"   {level:14} {n['non_resident']:>9,} of {n['total']:>10,} "
              f"({n['share']}%)")
    print(f"\n  most non-resident students, all levels:")
    print(f"  {'institution':46}{'non-res':>9}{'total':>9}{'share':>8}")
    for r in doc["largest_by_non_resident_total"][:12]:
        print(f"  {r['institution'][:44]:46}{r['non_resident']:>9,}"
              f"{r['total']:>9,}{r['share']:>7.1f}%")
    if opt:
        print(f"\n  SEVP top campuses by STEM OPT authorisations: {len(opt)} parsed")
        for r in opt[:5]:
            print(f"   {r['campus'][:44]:46}{r['authorisations']:>8,}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
