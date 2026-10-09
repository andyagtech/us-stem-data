#!/usr/bin/env python3
"""H-1B by what the employer actually does, at six digits.

WHY SIX DIGITS MATTERS

The USCIS Data Hub publishes a TWO-digit NAICS, which is a sector and not an
industry: code 61 holds Harvard, a high school and a driving school, and code
44 holds a department store and a gas station. Nothing useful about who
sponsors H-1B workers survives that. The Labor Department's disclosure files
carry the employer's own SIX-digit code, which separates them.

ONE SCAN, EVERY TOPIC. Reading the corpus takes ten minutes, so this emits
EVERY six-digit code it finds rather than the handful anyone asked for today.
A new question -- gas stations, nursing homes, abattoirs -- is then a filter
over a published file instead of another pass over 1.6 GB.

THE 2022 NAICS REVISION IS NOT COSMETIC. Gasoline stations moved from 447 to
457 in the 2022 edition, so a filing from 2021 and one from 2024 describing
the identical business carry different codes. Codes are therefore reported as
filed, and the named groups below list every code that has ever meant that
thing. A group that silently used one edition would show a business vanishing
in 2022.

SELF-REPORTED. The employer picks its own code. Nothing checks it, and the
body-shop work on this site already found firms whose code flatters them.
Treat a code as the employer's claim about itself.

Output: site/data/h1b_by_industry.json

Usage:
    python3 scripts/build_h1b_by_industry.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LCA = ROOT / "data" / "h1b" / "lca"
OUT = ROOT / "site" / "data" / "h1b_by_industry.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402
from build_visa_bodyshops import drop_contained              # noqa: E402

#: Named groups. Each lists every code that has meant that thing across NAICS
#: editions, so a business does not appear to vanish at a revision.
GROUPS = {
    "universities_and_colleges": {
        "label": "Colleges, universities and professional schools",
        "codes": ("611310",),
    },
    "junior_colleges": {"label": "Junior colleges", "codes": ("611210",)},
    "schools_k12": {
        "label": "Elementary and secondary schools",
        "codes": ("611110",),
    },
    "other_schools": {
        "label": "Technical, trade and other schools",
        "codes": ("611410", "611420", "611430", "611511", "611512", "611513",
                  "611519", "611610", "611620", "611630", "611691", "611692",
                  "611699", "611710"),
    },
    "gas_stations": {
        "label": "Gas stations and convenience retail",
        # 447110/447190 under the 2017 edition; 457110/457120 and 445131
        # from 2022. All of them are the same shops.
        "codes": ("447110", "447190", "457110", "457120", "445131"),
    },
    "hospitals": {
        "label": "Hospitals",
        "codes": ("622110", "622210", "622310"),
    },
    "public_administration": {
        "label": "Public administration",
        "codes": tuple(str(c) for c in range(921110, 928120)),
    },
}


def annual(wage, unit) -> float | None:
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
        raise SystemExit(f"FAIL: no LCA files in {LCA}. Restore them with the "
                         f"command in data/h1b/lca_archive_manifest.json.")
    # The same overlap guard the body-shop builder uses: two of these files
    # are cumulative and contain others whole.
    files, _spans = drop_contained(files, strict=False)

    import openpyxl
    # THREE SCHEMAS OVER EIGHTEEN YEARS. FY2008-09 is the "Case Data" layout,
    # FY2010-14 the iCERT one with an LCA_CASE_ prefix, FY2015 onward the
    # current names. Every column is read through all of its spellings.
    #
    # FY2008 AND FY2009 CARRY NO NAICS CODE AT ALL, so the industry series
    # cannot begin before FY2010. Those files are skipped with a reason rather
    # than counted as industries unknown, which would show every trade losing
    # its first two years.
    need = {
        "CASE_STATUS": ("CASE_STATUS", "STATUS", "APPROVAL_STATUS"),
        "EMPLOYER_NAME": ("EMPLOYER_NAME", "LCA_CASE_EMPLOYER_NAME", "NAME"),
        "NAICS_CODE": ("NAICS_CODE", "LCA_CASE_NAICS_CODE", "NAIC_CODE"),
        "JOB_TITLE": ("JOB_TITLE", "LCA_CASE_JOB_TITLE"),
        "WAGE_RATE_OF_PAY_FROM": ("WAGE_RATE_OF_PAY_FROM",
                                  "LCA_CASE_WAGE_RATE_FROM", "WAGE_RATE_OF_PAY"),
        "WAGE_UNIT_OF_PAY": ("WAGE_UNIT_OF_PAY", "LCA_CASE_WAGE_RATE_UNIT"),
        "WORKSITE_STATE": ("WORKSITE_STATE", "LCA_CASE_WORKLOC1_STATE",
                           "WORKSITE_STATE_1", "STATE_1"),
        "PW_WAGE_LEVEL": ("PW_WAGE_LEVEL", "PW_WAGE_LEVEL_1",
                          "LCA_CASE_WAGE_RATE_UNIT"),
        "TOTAL_WORKER_POSITIONS": ("TOTAL_WORKER_POSITIONS", "TOTAL_WORKERS",
                                   "LCA_CASE_NUMBER_OF_EMPLOYEES"),
    }
    REQUIRED = ("CASE_STATUS", "EMPLOYER_NAME", "NAICS_CODE")
    CASE_KEY = ("CASE_NUMBER", "LCA_CASE_NUMBER")
    seen: set = set()
    dupes = 0
    skipped = []
    codes: dict[str, dict] = defaultdict(
        lambda: {"filings": 0, "positions": 0, "wages": [], "low": 0, "lvl": 0,
                 "employers": defaultdict(int), "titles": defaultdict(int),
                 "states": defaultdict(int)})
    total = 0
    for path in files:
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        hdr = [str(h).strip().upper() if h else "" for h in next(it)]
        idx = {}
        for field, spellings in need.items():
            hit = next((sp for sp in spellings if sp in hdr), None)
            if hit is not None:
                idx[field] = hdr.index(hit)
        missing = [c for c in REQUIRED if c not in idx]
        if missing:
            wb.close()
            if missing == ["NAICS_CODE"]:
                skipped.append((path.name, "carries no NAICS code"))
                print(f"  SKIP {path.name}: no NAICS column, so it cannot "
                      f"contribute to an industry series", flush=True)
                continue
            raise SystemExit(f"FAIL: {path.name} has no column for "
                             f"{', '.join(missing)} under any known spelling. "
                             f"Nothing written.")
        ci = next((hdr.index(c) for c in CASE_KEY if c in hdr), None)
        for row in it:
            # EXACT DE-DUPLICATION, by the case number DOL assigns. Two
            # releases can cover the same period -- FY2011's spills three days
            # into FY2012, and several years ship a cumulative file alongside
            # its quarters. Dropping whole files handles containment but not a
            # three-day tail; the case number handles every shape of it.
            if ci is not None:
                cn = str(row[ci] or "").strip().upper()
                if cn:
                    if cn in seen:
                        dupes += 1
                        continue
                    seen.add(cn)
            status = str(row[idx["CASE_STATUS"]] or "").strip().lower()
            # The old layouts say "certified" too, but FY2008-09 also uses
            # "certified-withdrawn"; only a plain certification counts.
            if status != "certified":
                continue
            code = re.sub(r"\D", "", str(row[idx["NAICS_CODE"]] or ""))[:6]
            if not code:
                continue
            total += 1
            e = codes[code]
            e["filings"] += 1
            try:
                e["positions"] += int(float(
                    row[idx["TOTAL_WORKER_POSITIONS"]] or 1)) \
                    if "TOTAL_WORKER_POSITIONS" in idx else 1
            except (TypeError, ValueError):
                e["positions"] += 1
            name = str(row[idx["EMPLOYER_NAME"]] or "").strip()
            if name:
                e["employers"][name.upper()] += 1
            t = str(row[idx["JOB_TITLE"]] or "").strip() if "JOB_TITLE" in idx else ""
            if t.startswith('="') and t.endswith('"'):
                t = t[2:-1]
            t = t.strip('="').strip().title()
            if t:
                e["titles"][t] += 1
            st = (str(row[idx["WORKSITE_STATE"]] or "").strip()
                  if "WORKSITE_STATE" in idx else "")
            if st:
                e["states"][st] += 1
            lvl = (re.sub(r"[^IV]", "", str(row[idx["PW_WAGE_LEVEL"]] or "").upper())
                   if "PW_WAGE_LEVEL" in idx else "")
            if lvl in ("I", "II", "III", "IV"):
                e["lvl"] += 1
                if lvl in ("I", "II"):
                    e["low"] += 1
            w = (annual(row[idx["WAGE_RATE_OF_PAY_FROM"]],
                        row.__getitem__(idx["WAGE_UNIT_OF_PAY"])
                        if "WAGE_UNIT_OF_PAY" in idx else "year")
                 if "WAGE_RATE_OF_PAY_FROM" in idx else None)
            if w and 10_000 < w < 1_000_000 and len(e["wages"]) < 60_000:
                e["wages"].append(w)
        wb.close()
        print(f"  read {path.name}", flush=True)

    def pack(e: dict) -> dict:
        ws = sorted(e["wages"])
        return {
            "filings": e["filings"], "positions": e["positions"],
            "employers": len(e["employers"]),
            "median_wage": round(ws[len(ws) // 2]) if ws else None,
            "low_level_pct": round(100 * e["low"] / e["lvl"], 1) if e["lvl"] else None,
            "top_employers": sorted(e["employers"].items(), key=lambda kv: -kv[1])[:15],
            "top_titles": sorted(e["titles"].items(), key=lambda kv: -kv[1])[:12],
            "top_states": sorted(e["states"].items(), key=lambda kv: -kv[1])[:10],
        }

    groups = {}
    for key, spec in GROUPS.items():
        merged = {"filings": 0, "positions": 0, "wages": [], "low": 0, "lvl": 0,
                  "employers": defaultdict(int), "titles": defaultdict(int),
                  "states": defaultdict(int)}
        present = []
        for c in spec["codes"]:
            if c not in codes:
                continue
            present.append(c)
            e = codes[c]
            for k in ("filings", "positions", "low", "lvl"):
                merged[k] += e[k]
            merged["wages"] += e["wages"]
            for k in ("employers", "titles", "states"):
                for name, v in e[k].items():
                    merged[k][name] += v
        groups[key] = {"label": spec["label"], "codes_declared": list(spec["codes"]),
                       "codes_present": present, **pack(merged)}

    out = {
        "source": "US DOL Office of Foreign Labor Certification, LCA disclosure files",
        "source_url": "https://www.dol.gov/agencies/eta/foreign-labor/performance",
        "files": [f.name for f in files],
        "files_skipped": [{"file": n, "reason": r} for n, r in skipped],
        "certified_filings": total,
        "duplicate_rows_skipped": dupes,
        "distinct_codes": len(codes),
        "caveats": [
            "The six-digit code is the employer's own answer on its own form. "
            "Nothing verifies it.",
            "Certified applications only. An LCA is permission to employ at a "
            "stated wage, not proof that anyone was hired.",
            "Counted by application, not by position. One application can "
            "cover many workers.",
            "NAICS was revised in 2022 and some industries changed code. Each "
            "named group lists every code that has meant that thing, and codes "
            "are otherwise reported exactly as filed.",
        ],
        "groups": groups,
        "by_code": {c: pack(e) for c, e in
                    sorted(codes.items(), key=lambda kv: -kv[1]["filings"])},
    }
    write_json(OUT, out, indent=1)
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {total:,} certified applications across {len(codes):,} six-digit codes")
    print(f"  {dupes:,} duplicate rows skipped by case number")
    for k, g in groups.items():
        print(f"    {g['label'][:44]:<46}{g['filings']:>8,} filings  "
              f"{g['employers']:>6,} employers  "
              f"{('$' + format(g['median_wage'], ',')) if g['median_wage'] else '-':>10}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
