#!/usr/bin/env python3
"""Which institutions enrol the most foreign science and engineering students?

The project already ranks institutions on DEGREES CONFERRED from IPEDS. This
ranks them on ENROLMENT from the GSS, which is a different collection with a
different field definition, and which separates master's from doctoral study
within science, engineering and health.

TWO SEPARATE MEANINGS OF ONE TOKEN. In the GSS Race sheet 'forgn' sits
alongside black, white, asian and the other reporting categories, so there it
is the student's citizenship -- a temporary-visa holder. In the Support sheet
the same token sits alongside 'inst' and 'othus' and means a FOREIGN SOURCE OF
FUNDS. Only the Race sheet is used here.

FLOORS, NOT A LEAGUE TABLE OF SMALL PROGRAMMES. A department with eleven
students and nine foreign ones is 82% and tells you nothing, so a minimum
enrolment applies to each ranking.

Usage:
  python3 scripts/build_gss_institution_ranking.py
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "nsf_gss" / "graduate_students_postdocs_2024.zip"
INNER = "gss2024_Code.xlsx"
OUT = ROOT / "site" / "data" / "gss_institution_ranking.json"

LEVELS = {"dr": "doctoral", "ma": "master's"}
FLOOR = {"dr": 300, "ma": 200}      # minimum full-time enrolment to be ranked
TOP_N = 25


def main() -> int:
    if not SRC.exists():
        print(f"  missing {SRC.relative_to(ROOT)}")
        return 1
    import openpyxl
    with zipfile.ZipFile(SRC) as z:
        wb = openpyxl.load_workbook(io.BytesIO(z.read(INNER)), read_only=True)
    ws = wb["Race"]
    it = ws.iter_rows(values_only=True)
    cols = [str(c) if c is not None else "" for c in next(it)]
    idx = {c: i for i, c in enumerate(cols)}

    need = ["Institution_Name", "UNITID"]
    for lv in LEVELS:
        need += [f"{lv}_ft_tot_forgn_v", f"{lv}_ft_tot_all_races_v"]
    missing = [c for c in need if c not in idx]
    if missing:
        print(f"  missing columns: {missing}")
        return 1

    # The GSS reports one row per ORGANISATIONAL UNIT, not per institution --
    # a university appears once for each school it returns. Rows must be
    # summed to the institution or every large university is ranked as a
    # handful of small departments.
    acc: dict[str, dict] = {}
    warns = []
    for r in it:
        name = str(r[idx["Institution_Name"]] or "").strip()
        key = str(r[idx["UNITID"]] or "").strip() or name
        if not name:
            continue
        rec = acc.setdefault(key, {"institution": name, "units": 0,
                                   **{lv: [0, 0] for lv in LEVELS}})
        rec["units"] += 1
        for lv in LEVELS:
            tot = r[idx[f"{lv}_ft_tot_all_races_v"]]
            forg = r[idx[f"{lv}_ft_tot_forgn_v"]]
            if not isinstance(tot, (int, float)) or not isinstance(forg, (int, float)):
                continue
            if forg > tot:
                warns.append(f"{name}: {int(forg):,} foreign of {int(tot):,}")
                continue
            rec[lv][0] += int(tot)
            rec[lv][1] += int(forg)

    recs = {}
    for key, rec in acc.items():
        out = {"institution": rec["institution"], "unitid": key,
               "units": rec["units"]}
        keep = False
        for lv, label in LEVELS.items():
            tot, forg = rec[lv]
            if tot <= 0:
                continue
            out[label] = {"total": tot, "foreign": forg,
                          "share": round(100 * forg / tot, 1)}
            keep = True
        if keep:
            recs[key] = out

    if len(recs) < 100:
        print(f"  only {len(recs)} institutions parsed")
        return 1

    rankings, national = {}, {}
    for lv, label in LEVELS.items():
        have = [v for v in recs.values() if label in v]
        tot = sum(v[label]["total"] for v in have)
        forg = sum(v[label]["foreign"] for v in have)
        national[label] = {"institutions": len(have), "total": tot,
                           "foreign": forg,
                           "share": round(100 * forg / tot, 1) if tot else None}
        eligible = [v for v in have if v[label]["total"] >= FLOOR[lv]]
        rankings[label] = {
            "floor": FLOOR[lv],
            "eligible": len(eligible),
            "by_share": [{"institution": v["institution"], **v[label]}
                         for v in sorted(eligible,
                                         key=lambda x: -x[label]["share"])[:TOP_N]],
            "by_count": [{"institution": v["institution"], **v[label]}
                         for v in sorted(have,
                                         key=lambda x: -x[label]["foreign"])[:TOP_N]],
        }

    doc = {
        "_comment": (
            "Full-time science, engineering and health graduate enrolment by "
            "institution, and the share held by temporary-visa holders, from "
            "the GSS Race sheet where 'forgn' is the STUDENT'S CITIZENSHIP. "
            "(In the GSS Support sheet the same token means a foreign SOURCE "
            "OF FUNDS; that sheet is not used here.) COUNTS ARE ENROLMENTS, "
            "not degrees, and the field basis is S&E&H units -- neither is "
            "comparable with the IPEDS core-STEM degree rankings elsewhere in "
            "this project. Ranked by share only above an enrolment floor, "
            "because a small programme produces meaningless percentages; the "
            "by_count ranking has no floor since a large count is already "
            "evidence of scale. Permanent residents are counted under their "
            "race and so appear as domestic here. Single year, 2024."),
        "source": "NSF NCSES, Survey of Graduate Students and Postdoctorates, 2024",
        "national": national,
        # The full set, not only the ranked extracts: other builders join
        # against this and a truncated list silently shrinks their universe.
        "institutions": sorted(recs.values(), key=lambda v: v["institution"]),
        "rankings": rankings,
        "warnings": warns,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {len(recs)} institutions")
    for label, n in national.items():
        print(f"  {label:10} {n['foreign']:,} of {n['total']:,} full-time "
              f"({n['share']}%) across {n['institutions']} institutions")
    for label in LEVELS.values():
        rk = rankings[label]
        print(f"\n  {label}, highest share (floor {rk['floor']}, "
              f"{rk['eligible']} eligible):")
        for r in rk["by_share"][:8]:
            print(f"   {r['institution'][:40]:42}{r['share']:>6.1f}%"
                  f"{r['foreign']:>8,} of{r['total']:>7,}")
    for w in warns[:5]:
        print(f"  WARN {w}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
