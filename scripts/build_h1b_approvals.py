#!/usr/bin/env python3
"""H-1B approvals by employer, FY2009-2023, from USCIS.

The project already holds what employers ASKED for -- labour condition
applications, with the wage level they promised -- and what the Labor
Department FOUND when it investigated. This is the middle term: what USCIS
actually approved, by employer, every year for fifteen years.

INITIAL AGAINST CONTINUING. USCIS separates the two, and the distinction
matters more than it looks. An initial approval is a new worker entering the
programme; a continuing approval is an extension or amendment for someone
already in it. Adding them together counts the same person repeatedly across
years, so the two are kept apart throughout and the headline uses initial
approvals.

DENIAL RATES ARE A POLICY SERIES, NOT A QUALITY ONE. They move sharply with
adjudication policy rather than with applicants, so a rise or fall says more
about the agency than about employers.

Usage:
  python3 scripts/build_h1b_approvals.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "uscis_hub"
OUT = ROOT / "site" / "data" / "h1b_approvals.json"
WAGES = ROOT / "site" / "data" / "lca_wage_levels.json"

# USCIS renamed these columns in FY2020: the earlier exports write the
# plural ("Initial Approvals"), the later ones the singular. Reading only one
# form silently scores eleven years at zero rather than failing.
FIELDS = {"initial_approval": ("Initial Approval", "Initial Approvals"),
          "initial_denial": ("Initial Denial", "Initial Denials"),
          "continuing_approval": ("Continuing Approval", "Continuing Approvals"),
          "continuing_denial": ("Continuing Denial", "Continuing Denials")}


def pick(row: dict, names: tuple[str, ...]) -> str | None:
    return next((n for n in names if n in row), None)


def norm(s: str) -> str:
    """Case and whitespace only; nothing is fuzzy-matched."""
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()


def num(v) -> int:
    try:
        return int(float(str(v).replace(",", "") or 0))
    except (TypeError, ValueError):
        return 0


def main() -> int:
    files = sorted(SRC.glob("h1b_datahubexport-*.csv"))
    if not files:
        print(f"  no files in {SRC.relative_to(ROOT)}")
        return 1

    by_year: dict[int, dict] = defaultdict(lambda: dict.fromkeys(FIELDS, 0)
                                           | {"employers": 0})
    employers: dict[str, dict] = {}
    warns: list[str] = []
    blank_employer = 0

    for path in files:
        m = re.search(r"(\d{4})", path.name)
        year = int(m.group(1))
        seen = set()
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            for r in csv.DictReader(fh):
                vals = {k: num(r.get(pick(r, cols))) for k, cols in FIELDS.items()}
                if not any(vals.values()):
                    continue
                name = norm(r.get("Employer"))
                if not name:
                    # USCIS ships rows with an empty employer; they are real
                    # counts and are kept in the national totals but cannot
                    # be attributed, so they are reported separately.
                    blank_employer += 1
                for k, v in vals.items():
                    by_year[year][k] += v
                if not name:
                    continue
                seen.add(name)
                e = employers.setdefault(name, {
                    "employer": name, "years": {},
                    **dict.fromkeys(FIELDS, 0),
                    "state": (r.get("State") or "").strip(),
                    "naics": (r.get("NAICS") or "").strip()})
                for k, v in vals.items():
                    e[k] += v
                y = e["years"].setdefault(str(year), dict.fromkeys(FIELDS, 0))
                for k, v in vals.items():
                    y[k] += v
        by_year[year]["employers"] = len(seen)

    years = sorted(by_year)
    if len(years) < 5:
        print(f"  only {len(years)} years")
        return 1

    # A year far below its neighbours is a partial export, not a collapse in
    # the programme. Flag it rather than let it read as a finding.
    initials = [by_year[y]["initial_approval"] for y in years]
    med = sorted(initials)[len(initials) // 2]
    incomplete = [y for y in years
                  if by_year[y]["initial_approval"] < 0.5 * med]
    for y in incomplete:
        warns.append(f"FY{y}: {by_year[y]['initial_approval']:,} initial "
                     f"approvals against a median of {med:,} -- likely a "
                     f"partial export; treat as incomplete")

    def rate(d: dict, kind: str) -> float | None:
        a, x = d[f"{kind}_approval"], d[f"{kind}_denial"]
        return round(100 * x / (a + x), 1) if (a + x) else None

    series = {str(y): dict(by_year[y]) | {
        "initial_denial_rate_pct": rate(by_year[y], "initial"),
        "continuing_denial_rate_pct": rate(by_year[y], "continuing")}
        for y in years}

    top = sorted(employers.values(), key=lambda e: -e["initial_approval"])[:40]

    # The three-way join this dataset exists for: what an employer asked for,
    # at what wage level, and what it was actually granted.
    joined = []
    if WAGES.exists():
        wl = {norm(r["employer"]): r
              for r in json.loads(WAGES.read_text())["largest_filers"]}
        for e in top:
            w = wl.get(e["employer"])
            if w:
                joined.append({
                    "employer": e["employer"],
                    "initial_approvals": e["initial_approval"],
                    "continuing_approvals": e["continuing_approval"],
                    "lca_filings": w["filings"],
                    "low_level_pct": w["low_level_pct"]})

    # Employers file under several spellings and nothing here is
    # fuzzy-matched, so the ranking above understates the largest of them.
    # Rather than merge silently, the variants are DISCLOSED: each spelling is
    # listed with its own count beside the total, so a reader can see exactly
    # what is being added and disagree with it.
    STEMS = ("COGNIZANT", "TATA CONSULTANCY", "INFOSYS", "WIPRO", "AMAZON",
             "ACCENTURE", "DELOITTE", "HCL ", "CAPGEMINI", "IBM ")
    variants = []
    for stem in STEMS:
        hits = sorted((e for e in employers.values()
                       if e["employer"].startswith(stem)
                       and e["initial_approval"] > 0),
                      key=lambda e: -e["initial_approval"])
        if len(hits) > 1:
            variants.append({
                "stem": stem.strip(),
                "spellings": len(hits),
                "largest_single": hits[0]["initial_approval"],
                "combined_initial_approvals": sum(h["initial_approval"] for h in hits),
                "detail": [{"employer": h["employer"],
                            "initial_approval": h["initial_approval"]}
                           for h in hits[:8]]})
    variants.sort(key=lambda v: -v["combined_initial_approvals"])

    doc = {
        "_comment": (
            "H-1B petitions approved and denied by employer, USCIS Employer "
            "Data Hub, FY2009-2023. INITIAL AND CONTINUING ARE KEPT APART: an "
            "initial approval is a new worker entering the programme, a "
            "continuing approval an extension or amendment for someone "
            "already in it, so summing them counts the same person across "
            "years. Headline figures use INITIAL approvals. DENIAL RATES ARE "
            "A POLICY SERIES -- they move with adjudication policy rather "
            "than with applicants, and a change says more about the agency "
            "than about employers. Counts are PETITIONS, not people. "
            "Employers are grouped on the filed name with case and whitespace "
            "normalised only; nothing is fuzzy-matched, so two spellings of "
            "one company remain two rows and a company total is a FLOOR -- "
            "materially so: Cognizant files under five spellings whose "
            "combined initial approvals are more than twice its largest "
            "single one. The name_variants block lists each spelling with its "
            "own count so the addition is visible rather than assumed. "
            "USCIS also ships rows with no employer name; those are counted "
            "in the national totals and reported as blank_employer_rows."),
        "source": "USCIS H-1B Employer Data Hub",
        "source_url": "https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub",
        "years": years,
        "incomplete_years": incomplete,
        "employers": len(employers),
        "blank_employer_rows": blank_employer,
        "series": series,
        "top_employers_by_initial_approvals": top,
        "approvals_against_wage_levels": joined,
        "name_variants": variants,
        "warnings": warns,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    f, l = years[0], years[-1]
    print(f"  {len(years)} years {f}-{l}; {len(employers):,} employers")
    print(f"  {'year':6}{'initial':>11}{'continuing':>13}{'init denial':>13}")
    for y in years:
        s = series[str(y)]
        print(f"  {y:6}{s['initial_approval']:>11,}{s['continuing_approval']:>13,}"
              f"{(str(s['initial_denial_rate_pct']) + '%'):>13}")
    print(f"\n  largest by initial approvals, {f}-{l}:")
    print(f"  {'employer':40}{'initial':>10}{'continuing':>12}")
    for e in top[:10]:
        print(f"  {e['employer'][:38]:40}{e['initial_approval']:>10,}"
              f"{e['continuing_approval']:>12,}")
    if joined:
        print(f"\n  approvals against the wage level promised:")
        print(f"  {'employer':40}{'initial':>10}{'LCA':>9}{'Lvl I+II':>10}")
        for r in joined[:10]:
            print(f"  {r['employer'][:38]:40}{r['initial_approvals']:>10,}"
                  f"{r['lca_filings']:>9,}{r['low_level_pct']:>9.1f}%")
    if variants:
        print(f"\n  the same employer under several spellings:")
        print(f"  {'employer':22}{'spellings':>11}{'largest':>10}{'combined':>11}")
        for v in variants[:6]:
            print(f"  {v['stem'][:20]:22}{v['spellings']:>11}"
                  f"{v['largest_single']:>10,}{v['combined_initial_approvals']:>11,}")
    for w in warns:
        print(f"  WARN {w}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
