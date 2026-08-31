#!/usr/bin/env python3
"""How much of an institution's income is tuition, against how foreign it is.

The tuition pages price what foreign master's students are billed at
published rates. That is a sticker-price scenario, not revenue: it says
nothing about whether an institution actually depends on that money. IPEDS
finance reports what each institution took in, and from where.

This asks whether the institutions with the highest foreign graduate
enrolment are the ones most dependent on tuition.

PUBLIC AND PRIVATE ARE NEVER POOLED. They file on different accounting
standards -- GASB for public, FASB for private -- with different forms and
line items that are not interchangeable. Public tuition revenue is net of
discounts and allowances; the private total includes investment return.
Combining them would produce a ratio that means nothing.

THIS IS TUITION FROM EVERY STUDENT, not from foreign students. IPEDS does
not report revenue by citizenship and nothing here claims it does: the
question is whether tuition-dependent institutions run higher foreign
enrolment, not how much any group paid.

Usage:
  python3 scripts/build_tuition_dependence.py
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIN = ROOT / "data" / "ipeds_finance"
HD = ROOT / "data" / "ipeds" / "hd2024.csv"
RANKING = ROOT / "site" / "data" / "gss_institution_ranking.json"
OUT = ROOT / "site" / "data" / "tuition_dependence.json"

# Verified against the IPEDS dictionaries shipped beside the data.
SECTORS = {
    "public": {"file": "f{y}_f1a.csv", "standard": "GASB",
               "tuition": "F1B01",       # net of discounts and allowances
               "total": "F1D01"},        # total revenues and other additions
    "private": {"file": "f{y}_f2.csv", "standard": "FASB",
                "tuition": "F2D01",      # tuition and fees, total
                "total": "F2D16"},       # total revenues and investment return
}
YEAR = "2324"


def num(v):
    s = str(v or "").strip().replace(",", "")
    if not s or s in ("."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main() -> int:
    if not RANKING.exists():
        print(f"  missing {RANKING.relative_to(ROOT)}; build the ranking first")
        return 1
    rank = json.loads(RANKING.read_text())
    enrol = {r["unitid"]: r for r in rank["institutions"] if r.get("unitid")}

    control = {}
    with open(HD, encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            control[(r.get("UNITID") or "").strip()] = (r.get("CONTROL") or "").strip()

    out, warns = {}, []
    for sector, spec in SECTORS.items():
        path = FIN / spec["file"].format(y=YEAR)
        if not path.exists():
            warns.append(f"{sector}: {path.name} not on disk")
            continue
        rows = []
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            rd = csv.DictReader(fh)
            if spec["tuition"] not in (rd.fieldnames or []):
                warns.append(f"{sector}: {path.name} has no {spec['tuition']}")
                continue
            for r in rd:
                uid = (r.get("UNITID") or "").strip()
                e = enrol.get(uid)
                if not e:
                    continue
                tui, tot = num(r.get(spec["tuition"])), num(r.get(spec["total"]))
                if not tui or not tot or tot <= 0 or tui < 0:
                    continue
                share = 100 * tui / tot
                if not 0 <= share <= 100:
                    warns.append(f"{uid}: tuition share {share:.1f}%")
                    continue
                grad = e.get("graduate") or {}
                if not grad:
                    d, m = e.get("doctoral"), e.get("master's")
                    t = (d["total"] if d else 0) + (m["total"] if m else 0)
                    f_ = (d["foreign"] if d else 0) + (m["foreign"] if m else 0)
                    if not t:
                        continue
                    grad = {"total": t, "foreign": f_,
                            "share": round(100 * f_ / t, 1)}
                rows.append({
                    "unitid": uid, "institution": e["institution"],
                    "tuition_revenue": round(tui), "total_revenue": round(tot),
                    "tuition_share_pct": round(share, 1),
                    "foreign_grad_share_pct": grad["share"],
                    "graduate_enrolment": grad["total"],
                    "graduate_foreign": grad["foreign"]})
        if len(rows) < 20:
            warns.append(f"{sector}: only {len(rows)} institutions matched")
            continue

        # Split by tuition dependence and compare foreign share across the
        # halves. A median split rather than a fitted line: this is a few
        # hundred institutions with a strong size gradient running through it.
        rows.sort(key=lambda r: r["tuition_share_pct"])
        half = len(rows) // 2
        low, high = rows[:half], rows[half:]

        def agg(rs):
            return {
                "institutions": len(rs),
                "median_tuition_share_pct": round(
                    statistics.median(r["tuition_share_pct"] for r in rs), 1),
                # Pooled from the raw counts, so a large programme counts
                # for more than a small one. Weighting the percentages and
                # multiplying by 100 again gave shares above 4,000%.
                "foreign_grad_share_pct": round(
                    100 * sum(r["graduate_foreign"] for r in rs)
                    / sum(r["graduate_enrolment"] for r in rs), 1),
                "graduate_enrolment": sum(r["graduate_enrolment"] for r in rs)}

        out[sector] = {
            "accounting_standard": spec["standard"],
            "institutions": len(rows),
            "least_tuition_dependent_half": agg(low),
            "most_tuition_dependent_half": agg(high),
            "most_dependent": sorted(
                rows, key=lambda r: -r["tuition_share_pct"])[:15],
            "largest_foreign_share": sorted(
                rows, key=lambda r: -r["foreign_grad_share_pct"])[:15],
        }

    if not out:
        print("  nothing built")
        for w in warns:
            print(f"  WARN {w}")
        return 1

    doc = {
        "_comment": (
            "Tuition and fees as a share of an institution's total revenue "
            "(IPEDS finance, FY2023-24), against the temporary-visa share of "
            "its graduate enrolment (GSS 2024). THE ANSWER SPLITS BY SECTOR "
            "AND MUST BE QUOTED THAT WAY: among public institutions the more "
            "tuition-dependent half runs a HIGHER foreign graduate share, "
            "among private institutions a LOWER one. The opposite signs are "
            "themselves the argument against reading either causally. PUBLIC "
            "AND PRIVATE ARE NEVER "
            "POOLED: they report on different accounting standards, GASB and "
            "FASB, with line items that are not interchangeable -- public "
            "tuition is net of discounts while the private revenue total "
            "includes investment return. THE TUITION FIGURE IS FROM EVERY "
            "STUDENT, not from foreign students: IPEDS does not report "
            "revenue by citizenship and nothing here claims it does. The "
            "question is whether tuition-dependent institutions run higher "
            "foreign enrolment, NOT how much any group paid. Foreign shares "
            "are pooled within each half rather than averaged, so a large "
            "programme counts for more than a small one."),
        "sources": {
            "finance": "NCES IPEDS Finance, FY2023-24 (F1A public, F2 private)",
            "enrolment": "NSF NCSES Survey of Graduate Students and Postdoctorates, 2024",
        },
        "source_url": "https://nces.ed.gov/ipeds/use-the-data",
        "fiscal_year": "2023-24",
        "sectors": out,
        "warnings": warns,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    for sector, s in out.items():
        lo, hi = s["least_tuition_dependent_half"], s["most_tuition_dependent_half"]
        print(f"\n  {sector} ({s['accounting_standard']}), {s['institutions']} institutions")
        print(f"   {'half':30}{'median tuition share':>22}{'foreign grad share':>21}")
        print(f"   {'least tuition-dependent':30}{lo['median_tuition_share_pct']:>21}%"
              f"{lo['foreign_grad_share_pct']:>20}%")
        print(f"   {'most tuition-dependent':30}{hi['median_tuition_share_pct']:>21}%"
              f"{hi['foreign_grad_share_pct']:>20}%")
    for w in warns[:6]:
        print(f"  WARN {w}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
