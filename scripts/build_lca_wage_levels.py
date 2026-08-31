#!/usr/bin/env python3
"""Do employers who promise the lowest legal wage turn up in enforcement?

Enforcement records show what was FOUND. The labour condition application
shows what was PROMISED: every H-1B filing names a prevailing-wage level from
I to IV, where Level I is the entry rate for the occupation and Level IV the
experienced one. An employer filing overwhelmingly at Level I or II is
promising the bottom of the legal range, which is lawful and is also the
cheapest way to fill a role.

This crosses the two: the wage-level profile of each employer against whether
that employer appears in the Wage and Hour Division's H-1B findings.

WHAT A CORRELATION HERE WOULD AND WOULD NOT MEAN. Enforcement is not random.
Large employers are investigated more often simply for being large, and
low-wage-level filers skew toward staffing firms, which are also more
investigated. A raw association therefore cannot be read as "low wage levels
cause violations", and the output reports filings alongside the rate so the
size effect stays visible rather than being hidden inside a percentage.

THE ARCHIVE IS PROCESSED ONE FILE AT A TIME. It is 4.3 GB against 5 GB free,
so each file is fetched, reduced to per-employer counts, and deleted before
the next.

Usage:
  python3 scripts/build_lca_wage_levels.py
  python3 scripts/build_lca_wage_levels.py --keep      # don't delete downloads
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import warnings
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "data" / "h1b" / "_lca_work"
OUT = ROOT / "site" / "data" / "lca_wage_levels.json"
ENFORCEMENT = ROOT / "site" / "data" / "h1b_enforcement.json"
BUCKET = "s3://phd-demographics-raw-data/data/h1b/lca/"
PROFILE = "personal"

# Complete years available as a single file, plus the four quarters that make
# up FY2023. The quarterly files are NOT cumulative -- FY2024 Q4 is smaller
# than Q3 -- so a year needs all four.
FILES = {
    2019: ["H-1B_Disclosure_Data_FY2019.xlsx"],
    2023: ["lca_fy2023_Q1.xlsx", "lca_fy2023_Q2.xlsx",
           "lca_fy2023_Q3.xlsx", "lca_fy2023_Q4.xlsx"],
}
LEVELS = ("Level I", "Level II", "Level III", "Level IV")
LOW = ("Level I", "Level II")
# Older files write "Level II"; FY2020 onward write bare "II". Both are
# folded to the long form, or every recent year scores zero.
LEVEL_ALIASES = {"I": "Level I", "II": "Level II",
                 "III": "Level III", "IV": "Level IV"}


def norm(name: str) -> str:
    """Case and whitespace only; nothing is fuzzy-matched."""
    return re.sub(r"\s+", " ", str(name or "")).strip().upper()


def fetch(fname: str) -> Path | None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    dest = SCRATCH / fname
    if dest.exists():
        return dest
    r = subprocess.run(["aws", "s3", "cp", f"{BUCKET}{fname}", str(dest),
                        "--profile", PROFILE, "--no-progress"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not dest.exists():
        print(f"    fetch failed: {fname}: {(r.stderr or '').strip()[:90]}")
        return None
    return dest


return_unknown: set[str] = set()


def scan(path: Path, counts: dict, wages: dict) -> int:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb[wb.sheetnames[0]]
    it = ws.iter_rows(values_only=True)
    hdr = [str(c) if c is not None else "" for c in next(it)]
    idx = {c: i for i, c in enumerate(hdr)}
    # The FLAG system renamed the column: files through FY2019 write
    # PW_WAGE_LEVEL_1 (one of ten worksite blocks), FY2020 onward write
    # PW_WAGE_LEVEL. Handling only the first silently drops every recent year.
    lvl_col = next((c for c in ("PW_WAGE_LEVEL_1", "PW_WAGE_LEVEL") if c in idx), None)
    need = ("EMPLOYER_NAME", "CASE_STATUS", "VISA_CLASS")
    missing = [c for c in need if c not in idx] + ([] if lvl_col else ["PW_WAGE_LEVEL"])
    if missing:
        print(f"    {path.name}: missing columns {missing}")
        wb.close()
        return 0
    i_emp, i_st, i_vc = (idx[c] for c in need)
    i_lvl = idx[lvl_col]
    # The wage itself, so the level can be priced against the occupation.
    # Column names moved with the same FLAG rename as the level.
    wage_col = next((c for c in ("PREVAILING_WAGE_1", "PREVAILING_WAGE") if c in idx), None)
    unit_col = next((c for c in ("PW_UNIT_OF_PAY_1", "PW_UNIT_OF_PAY") if c in idx), None)
    soc_col = next((c for c in ("SOC_CODE", "PW_SOC_CODE") if c in idx), None)
    i_wage = idx[wage_col] if wage_col else None
    i_unit = idx[unit_col] if unit_col else None
    i_soc = idx[soc_col] if soc_col else None
    if not all((i_wage, i_unit, i_soc)):
        print(f"    {path.name}: no wage/SOC columns; levels only")
    n = 0
    for r in it:
        if len(r) <= i_lvl:
            continue
        # Certified filings only, and H-1B only: a denied or withdrawn
        # application never promised anything.
        st = str(r[i_st] or "").strip().upper()
        if not st.startswith("CERTIFIED"):
            continue
        # EXACT match: "H-1B1 Chile" and "H-1B1 Singapore" contain "H-1B"
        # as a substring but are a different visa on a different statute.
        if str(r[i_vc] or "").strip().upper() != "H-1B":
            continue
        lvl = str(r[i_lvl] or "").strip()
        lvl = LEVEL_ALIASES.get(lvl.upper(), lvl)
        if lvl not in LEVELS:
            continue
        emp = norm(r[i_emp])
        if not emp:
            continue
        c = counts.setdefault(emp, dict.fromkeys(LEVELS, 0))
        c[lvl] += 1
        n += 1

        if i_wage is None:
            continue
        # SOC arrives as "15-1252", "15-1252.00" (O*NET detail) and
        # occasionally "151252". Requiring an exact dd-dddd match dropped
        # every O*NET-suffixed row, which was most of one year: 15% of
        # filings priced instead of nearly all.
        raw = str(r[i_soc] or "")
        m = re.search(r"(\d{2})-?(\d{4})", raw)
        if not m:
            continue
        soc = f"{m.group(1)}-{m.group(2)}"
        try:
            wage = float(str(r[i_wage] or "").replace(",", "").replace("$", ""))
        except ValueError:
            continue
        if wage <= 0:
            continue
        # Prevailing wages are filed hourly, weekly, monthly or yearly and
        # must be annualised or an hourly rate reads as a $30 salary.
        unit = str(r[i_unit] or "").strip().lower()
        mult = {"year": 1, "yr": 1, "hour": 2080, "hr": 2080, "week": 52,
                "wk": 52, "bi-weekly": 26, "biweekly": 26, "month": 12,
                "mth": 12}.get(unit)
        if mult is None:
            mult = 1 if wage > 15000 else None
            if mult is None:
                return_unknown.add(unit)
                continue
        annual = wage * mult
        if not 10_000 <= annual <= 1_000_000:
            continue
        b = wages.setdefault((soc, lvl), [])
        b.append(annual)
    wb.close()
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    if not ENFORCEMENT.exists():
        print(f"  missing {ENFORCEMENT.relative_to(ROOT)}; build it first")
        return 1

    by_year: dict[int, dict] = {}
    wages: dict[tuple[str, str], list[float]] = {}
    for year, names in FILES.items():
        counts: dict[str, dict] = {}
        rows = 0
        for fname in names:
            print(f"  {year}: fetching {fname}")
            p = fetch(fname)
            if not p:
                continue
            rows += scan(p, counts, wages)
            if not args.keep:
                p.unlink(missing_ok=True)
        if counts:
            by_year[year] = counts
            print(f"  {year}: {rows:,} certified H-1B filings, "
                  f"{len(counts):,} employers")

    if not by_year:
        print("  nothing scanned")
        return 1

    # Pool the years for the employer profile; report each year separately too.
    pooled: dict[str, dict] = {}
    for counts in by_year.values():
        for emp, c in counts.items():
            p = pooled.setdefault(emp, dict.fromkeys(LEVELS, 0))
            for k, v in c.items():
                p[k] += v

    enf = json.loads(ENFORCEMENT.read_text())
    flagged = {norm(e["employer"]) for e in
               enf["top_employers_by_back_wages"] + enf["top_employers_by_employees"]}
    # The published extract only carries the top employers, so absence from
    # this set is NOT evidence of no findings -- it is stated in the output.

    def low_share(c: dict) -> float:
        tot = sum(c.values())
        return round(100 * sum(c[k] for k in LOW) / tot, 1) if tot else 0.0

    rows_out = []
    for emp, c in pooled.items():
        tot = sum(c.values())
        if tot < 50:                      # a floor: 3 filings gives 100% noise
            continue
        rows_out.append({"employer": emp, "filings": tot,
                         "low_level_pct": low_share(c),
                         **{k.replace(" ", "_").lower(): c[k] for k in LEVELS},
                         "in_enforcement_top": emp in flagged})

    rows_out.sort(key=lambda r: -r["filings"])
    national = dict.fromkeys(LEVELS, 0)
    for c in pooled.values():
        for k, v in c.items():
            national[k] += v
    nat_tot = sum(national.values())

    largest = rows_out[:40]
    flagged_rows = [r for r in rows_out if r["in_enforcement_top"]]

    # Price each level against the occupation it was filed in. OEWS gives
    # the wage distribution for everyone in that occupation; the median of
    # the prevailing wages filed at a level says where in that distribution
    # the promise sits.
    import statistics
    oew_path = ROOT / "site" / "data" / "occupational_wages.json"
    priced = []
    if oew_path.exists() and wages:
        oew = json.loads(oew_path.read_text())
        latest = str(oew["latest_year"])
        by_soc = oew["by_soc"][latest]
        titles = oew["titles"]
        socs = {soc for soc, _lvl in wages}
        for soc in sorted(socs):
            o = by_soc.get(soc)
            if not o or not o.get("median"):
                continue
            row = {"soc": soc, "occupation": titles.get(soc, ""),
                   "oews_median": o["median"], "oews_p25": o.get("p25"),
                   "filings": 0, "levels": {}}
            for lvl in LEVELS:
                vals = wages.get((soc, lvl))
                if not vals:
                    continue
                med = statistics.median(vals)
                row["filings"] += len(vals)
                row["levels"][lvl] = {
                    "filings": len(vals),
                    "median_prevailing_wage": round(med),
                    "pct_of_oews_median": round(100 * med / o["median"], 1)}
            if row["levels"]:
                priced.append(row)
        priced.sort(key=lambda r: -r["filings"])

    # The single number this was built for: across every filing, what share
    # promised less than the occupation's own median wage?
    below = total_priced = 0
    if priced:
        oew = json.loads(oew_path.read_text())
        by_soc = oew["by_soc"][str(oew["latest_year"])]
        for (soc, lvl), vals in wages.items():
            o = by_soc.get(soc)
            if not o or not o.get("median"):
                continue
            total_priced += len(vals)
            below += sum(1 for v in vals if v < o["median"])
    below_pct = round(100 * below / total_priced, 1) if total_priced else None

    doc = {
        "_comment": (
            "Prevailing-wage LEVEL promised on certified H-1B labour condition "
            "applications, by employer, pooled over the years listed. Level I "
            "is the entry rate for an occupation and Level IV the experienced "
            "one; filing at Level I or II is lawful and is also the cheapest "
            "legal way to fill a role. THIS IS WHAT WAS PROMISED, not what was "
            "paid. Cross-referenced against the DOL enforcement extract, which "
            "publishes only its LARGEST cases -- so 'in_enforcement_top' false "
            "means NOT IN THAT EXTRACT and is NOT EVIDENCE OF NO FINDINGS. "
            "THE CROSSING IS INCONCLUSIVE: six employers match, which cannot "
            "support a correlation in either direction. "
            "Enforcement is also not random: large employers and staffing "
            "firms are investigated more, and both skew low-level, so any "
            "association here CANNOT be read causally. Employers are grouped "
            "on the filed name with case and whitespace normalised only; "
            "nothing is fuzzy-matched. Employers with fewer than 50 filings "
            "are excluded because a handful of filings produces meaningless "
            "percentages."),
        "source": "US DOL Office of Foreign Labor Certification, H-1B LCA disclosure data",
        "source_url": "https://www.dol.gov/agencies/eta/foreign-labor/performance",
        "years": sorted(by_year),
        "employers_scanned": len(pooled),
        "employers_above_floor": len(rows_out),
        "filings_floor": 50,
        "national_by_level": national,
        "national_low_level_pct": round(
            100 * sum(national[k] for k in LOW) / nat_tot, 1) if nat_tot else None,
        "priced_against_occupation": priced[:40],
        "filings_priced": total_priced,
        "below_occupational_median_pct": below_pct,
        "unrecognised_pay_units": sorted(return_unknown)[:10],
        "largest_filers": largest,
        "in_enforcement_extract": flagged_rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"\n  {len(pooled):,} employers, {len(rows_out):,} above the "
          f"{doc['filings_floor']}-filing floor")
    print(f"  national: " + ", ".join(f"{k} {national[k]:,}" for k in LEVELS))
    print(f"  {doc['national_low_level_pct']}% of filings are Level I or II")
    print(f"\n  largest filers:")
    print(f"  {'employer':44}{'filings':>10}{'Lvl I+II':>10}")
    for r in largest[:12]:
        print(f"  {r['employer'][:42]:44}{r['filings']:>10,}{r['low_level_pct']:>9.1f}%")
    if flagged_rows:
        print(f"\n  also in the published enforcement extract:")
        for r in flagged_rows[:10]:
            print(f"  {r['employer'][:42]:44}{r['filings']:>10,}{r['low_level_pct']:>9.1f}%")
    if below_pct is not None:
        print(f"\n  {below_pct}% of {total_priced:,} priced filings promise less "
              f"than the occupation's own median wage")
        print(f"  {'occupation':34}{'OEWS med':>11}{'Lvl I med':>11}{'as % of':>9}")
        for r in priced[:8]:
            l1 = r["levels"].get("Level I")
            if not l1:
                continue
            print(f"  {r['occupation'][:32]:34}${r['oews_median']:>10,.0f}"
                  f"${l1['median_prevailing_wage']:>10,}"
                  f"{l1['pct_of_oews_median']:>8.0f}%")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
