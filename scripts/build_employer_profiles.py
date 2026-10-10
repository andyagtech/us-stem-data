#!/usr/bin/env python3
"""One row per employer: what it asked for, what it got, what it promised.

The H-1B evidence in this project sits in three files that never meet. The
Labor Department records the labour condition applications an employer filed
and the wage level on each. USCIS records the petitions it approved and
denied. The Wage and Hour Division records the violations it found. Read
separately they answer three different questions; joined they answer the one
people actually ask, which is who is using this programme and how.

NAMES ARE THE WHOLE DIFFICULTY. The three agencies do not share an
identifier and each employer files under several spellings -- Cognizant
appears eighteen times in the USCIS file alone. Nothing here is
fuzzy-matched: names are normalised for case, punctuation and the common
suffixes, and anything that does not then match exactly is reported
unmatched. Totals per company are therefore FLOORS.

NO EQUIVALENT EXISTS FOR L-1 OR O-1. Neither requires a labour condition
application and USCIS publishes no employer hub for either, so the same
question cannot be asked of them at all. That absence is a finding and is
recorded here rather than left as a silence.

Usage:
  python3 scripts/build_employer_profiles.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "data"
OUT = SITE / "employer_profiles.json"
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402
from employer_name import pretty as _pn

# Legal-form suffixes that vary between filings of the same company.
SUFFIX = re.compile(
    r"\b(inc|inc\.|incorporated|llc|l\.l\.c|llp|l\.l\.p|ltd|ltd\.|limited|"
    r"corp|corp\.|corporation|co|co\.|company|plc|pvt|private|lp|l\.p|"
    r"usa|us|u\.s|u\.s\.a|america|american|na|n\.a)\b", re.I)
NOISE = re.compile(r"\b(dba|d/b/a|the)\b", re.I)
# Deterministic expansions, not fuzzy matching: the same company files as
# "Cognizant Tech Solns" and "Cognizant Technology Solutions". Every merge is
# auditable because each row lists the spellings it absorbed.
EXPAND = {"SOLNS": "SOLUTIONS", "SVCS": "SERVICES", "SVC": "SERVICES",
          "TECH": "TECHNOLOGY", "TECHNOLOGIES": "TECHNOLOGY",
          "SERVICE": "SERVICES", "SOLUTION": "SOLUTIONS",
          "INTL": "INTERNATIONAL", "SYS": "SYSTEMS", "SYSTEM": "SYSTEMS",
          "MFG": "MANUFACTURING", "CONSULTING": "CONSULTANCY"}


def canon(name: str) -> str:
    """Case, punctuation and legal suffixes only. Never fuzzy."""
    s = re.sub(r"\s+", " ", str(name or "")).strip().upper()
    s = s.replace("&", " AND ")
    s = re.sub(r"[.,'\"()/-]", " ", s)
    s = NOISE.sub(" ", s)
    s = SUFFIX.sub(" ", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return " ".join(EXPAND.get(w, w) for w in s.split())


def main() -> int:
    need = {"approvals": "h1b_approvals", "wages": "lca_wage_levels",
            "enforcement": "h1b_enforcement"}
    src = {}
    for key, fname in need.items():
        p = SITE / f"{fname}.json"
        if not p.exists():
            print(f"  missing {p.relative_to(ROOT)}")
            return 1
        src[key] = json.loads(p.read_text())

    profiles: dict[str, dict] = {}

    def slot(name: str) -> dict:
        k = canon(name)
        return profiles.setdefault(k, {
            "canonical": k, "names": set(),
            # None, not zero: these inputs are top-N extracts, so absence
            # means "not in that list" and never "none".
            "initial_approvals": None, "continuing_approvals": None,
            "initial_denials": None, "lca_filings": None,
            "low_level_filings": None, "enforcement_cases": None,
            "back_wages": None, "employees_covered": None})

    for e in src["approvals"]["top_employers_by_initial_approvals"]:
        r = slot(e["employer"])
        r["names"].add(e["employer"])
        r["initial_approvals"] = (r["initial_approvals"] or 0) + e["initial_approval"]
        r["continuing_approvals"] = (r["continuing_approvals"] or 0) + e["continuing_approval"]
        r["initial_denials"] = (r["initial_denials"] or 0) + e.get("initial_denial", 0)

    for e in src["wages"]["largest_filers"]:
        r = slot(e["employer"])
        r["names"].add(e["employer"])
        r["lca_filings"] = (r["lca_filings"] or 0) + e["filings"]
        r["low_level_filings"] = ((r["low_level_filings"] or 0)
                                  + round(e["filings"] * e["low_level_pct"] / 100))

    for e in (src["enforcement"]["top_employers_by_back_wages"]
              + src["enforcement"]["top_employers_by_employees"]):
        r = slot(e["employer"])
        r["names"].add(e["employer"])
        # The two lists overlap; take the maximum rather than adding twice.
        r["enforcement_cases"] = max(r["enforcement_cases"] or 0, e["cases"])
        r["back_wages"] = max(r["back_wages"] or 0.0, e["back_wages"])
        r["employees_covered"] = max(r["employees_covered"] or 0, e["employees"])

    rows = []
    for r in profiles.values():
        r["names"] = sorted(r["names"])
        r["spellings"] = len(r["names"])
        r["display"] = _pn(min(r["names"], key=len))
        if r["lca_filings"]:
            r["low_level_pct"] = round(
                100 * r["low_level_filings"] / r["lca_filings"], 1)
        tot = (r["initial_approvals"] or 0) + (r["initial_denials"] or 0)
        r["initial_denial_rate_pct"] = (
            round(100 * r["initial_denials"] / tot, 1) if tot else None)
        r["absent_from"] = [k for k, v in (("uscis", r["initial_approvals"]),
                                           ("lca", r["lca_filings"]),
                                           ("enforcement", r["enforcement_cases"]))
                            if v is None]
        r["sources"] = [k for k, cond in
                        (("uscis", r["initial_approvals"] or r["continuing_approvals"]),
                         ("lca", r["lca_filings"]),
                         ("enforcement", r["enforcement_cases"])) if cond]
        rows.append(r)

    rows.sort(key=lambda r: -((r["initial_approvals"] or 0)
                              or (r["lca_filings"] or 0)))
    in_both = [r for r in rows if {"uscis", "lca"} <= set(r["sources"])]
    with_enf = [r for r in rows if "enforcement" in r["sources"]]

    doc = {
        "_comment": (
            "One row per employer, joining what was REQUESTED (DOL labour "
            "condition applications, with the promised wage level), what was "
            "GRANTED (USCIS approvals and denials) and what was FOUND (Wage "
            "and Hour Division violations). NAMES ARE THE WHOLE DIFFICULTY: "
            "the three agencies share no identifier and each employer files "
            "under several spellings, so names are normalised for case, "
            "punctuation and legal suffixes and matched EXACTLY -- nothing is "
            "fuzzy-matched, and every company total is therefore a FLOOR. "
            "Each row lists the spellings it merged so the join can be "
            "audited. THE INPUTS ARE TOP-N EXTRACTS, not full registers: an "
            "employer absent from the enforcement list has no findings IN "
            "THAT EXTRACT, which is not the same as having none. NO "
            "EQUIVALENT EXISTS FOR L-1 OR O-1 -- neither requires a labour "
            "condition application and USCIS publishes no employer hub for "
            "either, so this question cannot be asked of them at all."),
        "sources": {
            "requested": "US DOL OFLC, H-1B LCA disclosure data",
            "granted": "USCIS H-1B Employer Data Hub, FY2009-2023",
            "enforcement": "US DOL Wage and Hour Division (WHISARD)",
        },
        "employers": len(rows),
        "in_uscis_and_lca": len(in_both),
        "with_enforcement": len(with_enf),
        "not_published_by_employer": ["L-1", "O-1"],
        "profiles": rows[:120],
    }
    write_json(OUT, doc)

    print(f"  {len(rows)} employers; {len(in_both)} appear in both USCIS and "
          f"LCA, {len(with_enf)} in the enforcement extract")
    print(f"\n  {'employer':30}{'approved':>10}{'requested':>11}"
          f"{'Lvl I+II':>10}{'denial':>8}")
    for r in rows[:14]:
        low = f"{r['low_level_pct']:.0f}%" if r.get("low_level_pct") else "-"
        den = (f"{r['initial_denial_rate_pct']:.0f}%"
               if r["initial_denial_rate_pct"] is not None else "-")
        ap = f"{r['initial_approvals']:,}" if r["initial_approvals"] is not None else "n/a"
        lc = f"{r['lca_filings']:,}" if r["lca_filings"] is not None else "n/a"
        print(f"  {r['display'][:28]:30}{ap:>10}{lc:>11}{low:>10}{den:>8}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
