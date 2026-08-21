#!/usr/bin/env python3
"""How doctorate recipients are paid for, by citizenship — the allocation evidence.

WHY THIS MATTERS MORE THAN COMPOSITION

Everything else on this site measures composition: who received the degrees.
Composition cannot show that anyone was prioritised, because it says nothing
about who paid. This table can.

The NSF Survey of Earned Doctorates asks every research doctorate recipient in
the United States for their PRIMARY SOURCE OF SUPPORT. It is a census, not a
sample -- essentially every doctorate recipient completes it before graduating,
and institutions are required to administer it. Table 4-1 crosses that answer
with citizenship status.

WHAT IT SHOWS (science and engineering, 2024)

                              US citizen/PR   temporary visa
    research assistantship          35.4%          53.6%
    teaching assistantship          17.7%          22.4%
    ASSISTANTSHIPS COMBINED         53.1%          76.0%
    fellowship/scholarship          27.6%          17.4%
    own resources                   16.0%           3.5%

Three in four international S&E doctorate recipients are supported by an
assistantship, against about half of citizens. Research assistantships -- the
category funded most directly by federal research grants -- run 18 points
higher. And citizens are more than four times as likely to be paying their own
way.

WHAT IT DOES AND DOES NOT ESTABLISH

It establishes that the funded route through a US doctorate is used far more by
international students than by citizens, and that self-funding is
overwhelmingly a domestic phenomenon.

It does NOT establish intent, nor that any individual citizen was refused a
funded place. Departments fund the students they admit; this measures the
result, not the decision. Nor does the SED break assistantship funding down by
its ultimate source, so "federal research grant" is an inference from what
research assistantships generally are, not a figure in this table.

Usage:
    python3 scripts/build_support_by_citizenship.py
    python3 scripts/build_support_by_citizenship.py --out site/data/support_by_citizenship.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from atomic_write import write_json

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "nsf_sed" / "tables" / "nsf25349-tab004-001.xlsx"
DEFAULT_OUT = ROOT / "site" / "data" / "support_by_citizenship.json"

# Column layout of SED Table 4-1.
COL_TOTAL, COL_CITIZEN, COL_VISA = 1, 4, 5

SOURCES = {
    "Teaching assistantships": "teaching_assistantship",
    "Research assistantships": "research_assistantship",
    "Fellowships": "fellowship",
    "Own resources": "own_resources",
    "Employer": "employer_other",
}


def build():
    try:
        import openpyxl
    except ImportError:
        sys.exit("openpyxl required")
    if not SRC.exists():
        sys.exit(f"Missing {SRC}")

    wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]

    fields: dict[str, dict] = {}
    current = None
    for row in rows:
        label = str(row[0]).strip() if row and row[0] else ""
        if not label:
            continue
        head = row[COL_TOTAL] if len(row) > COL_TOTAL else None
        # A field header carries the respondent count, not a percentage.
        if isinstance(head, (int, float)) and head > 500:
            current = label.replace(" (number)", "").strip()
            fields[current] = {
                "field": current,
                "n_total": int(head),
                "n_citizen": int(row[COL_CITIZEN]) if row[COL_CITIZEN] else None,
                "n_visa": int(row[COL_VISA]) if row[COL_VISA] else None,
                "sources": {},
            }
            continue
        if not current:
            continue
        key = next((v for k, v in SOURCES.items() if label.startswith(k)), None)
        if not key:
            continue
        try:
            fields[current]["sources"][key] = {
                "citizen": float(row[COL_CITIZEN]),
                "visa": float(row[COL_VISA]),
            }
        except (TypeError, ValueError):
            continue

    for f in fields.values():
        s = f["sources"]
        ra, ta = s.get("research_assistantship"), s.get("teaching_assistantship")
        if ra and ta:
            f["assistantships"] = {
                "citizen": round(ra["citizen"] + ta["citizen"], 1),
                "visa": round(ra["visa"] + ta["visa"], 1),
            }
            f["assistantship_gap"] = round(
                f["assistantships"]["visa"] - f["assistantships"]["citizen"], 1)
        own = s.get("own_resources")
        if own and own["visa"]:
            f["self_fund_ratio"] = round(own["citizen"] / own["visa"], 1)
    return fields


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    fields = build()
    ranked = sorted((f for f in fields.values() if "assistantship_gap" in f),
                    key=lambda f: -f["assistantship_gap"])

    print("PRIMARY SOURCE OF SUPPORT, BY CITIZENSHIP")
    print("NSF Survey of Earned Doctorates, Table 4-1, 2024 · a census of "
          "doctorate recipients\n")
    print(f"{'field':<42}{'assistantship %':>18}{'gap':>8}{'self-fund ratio':>17}")
    print(f"{'':<42}{'citizen':>9}{'visa':>9}{'':>8}{'cit:visa':>17}")
    print("-" * 86)
    for f in ranked[:16]:
        a = f["assistantships"]
        ratio = f.get("self_fund_ratio")
        print(f"{f['field'][:41]:<42}{a['citizen']:>8.1f}%{a['visa']:>8.1f}%"
              f"{f['assistantship_gap']:>+8.1f}"
              f"{(f'{ratio}x' if ratio else '-'):>17}")

    payload = {
        "source": ("NSF Survey of Earned Doctorates, Table 4-1 (2024). A census "
                   "of research doctorate recipients, administered by "
                   "institutions and completed before graduation."),
        "measure": "primary source of financial support, percent of recipients",
        "caveat": ("Establishes that the funded route through a doctorate is "
                   "used far more by international students, and that "
                   "self-funding is overwhelmingly domestic. Does NOT establish "
                   "intent, nor that any individual citizen was refused a funded "
                   "place. The SED does not break assistantship funding down by "
                   "ultimate source, so attributing research assistantships to "
                   "federal grants is an inference about what RAs generally are, "
                   "not a figure in this table."),
        "fields": fields,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, payload, separators=(",", ":"))
    print(f"\nwrote {out} ({out.stat().st_size / 1024:.0f} KB, {len(fields)} fields)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
