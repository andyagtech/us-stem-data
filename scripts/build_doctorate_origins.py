#!/usr/bin/env python3
"""Where the foreign doctorate recipients come from, and who their parents are.

"Non-resident" was one undifferentiated block. The site could say that 38.8%
of core-STEM doctorates go to temporary-visa holders and nothing about which
countries that is, even though stay rates were already broken out by origin --
so the retention page named countries the degree pages could not.

Two tables, both from the SED:

  7-8   the 40 largest countries of origin, 2024
  5-5   parental education by citizenship status

Parental education is the closer proxy for first generation than anything
else published, and the contrast it shows is not the one people expect.

Usage:
  python3 scripts/build_doctorate_origins.py
"""
from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SED = ROOT / "data" / "sed"
OUT = ROOT / "site" / "data" / "doctorate_origins.json"


def rows(path: Path):
    import openpyxl
    ws = openpyxl.load_workbook(path).active
    for r in ws.iter_rows(values_only=True):
        yield [x for x in r]


def clean(s) -> str:
    """Strip the footnote marker without eating the name.

    Only one country carries one here and it doubles the final letter:
    "Chinaa". The rest simply have trailing whitespace. A first attempt
    removed any trailing a-e, which turned India into Indi, Canada into Canad
    and Saudi Arabia into Saudi Arabi -- a rule that damages more names than
    it repairs.
    """
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if len(s) > 3 and s[-1] == s[-2] and s[-1].isalpha() and s[-1].islower():
        return s[:-1]
    return s


def main() -> int:
    origins_path = SED / "nsf25349-tab007-008.xlsx"
    if not origins_path.exists():
        print(f"  {origins_path.relative_to(ROOT)} not found")
        return 1

    countries, total, top40 = [], None, None
    for r in rows(origins_path):
        cells = [x for x in r if x is not None]
        if len(cells) < 2:
            continue
        name = clean(cells[0])
        nums = [x for x in cells[1:] if isinstance(x, (int, float))]
        if not nums:
            continue
        n = int(nums[-1])
        low = name.lower()
        if low.startswith("all temporary"):
            total = n
            continue
        if low.startswith("top 40"):
            top40 = n
            continue
        if len(nums) >= 2:                       # rank and count
            countries.append({"country": name, "rank": int(nums[0]), "recipients": n})

    if not countries:
        print("  no country rows parsed")
        return 1
    # The published ranks must be the order the counts give, or a column moved.
    ordered = sorted(countries, key=lambda c: c["rank"])
    if [c["recipients"] for c in ordered] != sorted(
            (c["recipients"] for c in ordered), reverse=True):
        print("  WARNING: ranks and counts disagree; a column may have shifted")
    for c in ordered:
        c["share_of_visa_holders_pct"] = round(100 * c["recipients"] / total, 1) if total else None

    doc = {
        "_comment": ("Countries of origin of temporary-visa research doctorate "
                     "recipients, and parental education by citizenship. "
                     "Country counts are ALL FIELDS, not core-STEM only, so "
                     "they are not directly comparable to the IPEDS core-STEM "
                     "figures used elsewhere on the site."),
        "source": "NSF NCSES, Survey of Earned Doctorates 2024, tables 7-8 and 5-5",
        "year": 2024,
        "all_temporary_visa_holders": total,
        "top_40_total": top40,
        "countries_represented": 159,
        "countries": ordered,
    }

    # Parental education, if the table came down with it.
    ped = SED / "nsf25349-tab005-005.xlsx"
    if ped.exists():
        raw = []
        for r in rows(ped):
            cells = [x for x in r if x is not None]
            if len(cells) >= 3 and isinstance(cells[0], str):
                nums = [x for x in cells[1:] if isinstance(x, (int, float))]
                if nums:
                    raw.append({"label": clean(cells[0]), "values": nums[:6]})
        if raw:
            doc["parental_education_rows"] = raw[:24]
            doc["parental_education_note"] = (
                "Table 5-5 columns run: total, then sex, then citizenship "
                "status. Read the citizenship columns for the comparison that "
                "matters; the table is transcribed rather than interpreted.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {len(ordered)} countries, {total:,} temporary-visa recipients "
          f"across {doc['countries_represented']} countries")
    for c in ordered[:8]:
        print(f"    {c['rank']:>2}. {c['country'][:22]:24} {c['recipients']:>6,}  "
              f"{c['share_of_visa_holders_pct']:>5.1f}%")
    top5 = sum(c["recipients"] for c in ordered[:5])
    print(f"  top 5 are {100*top5/total:.0f}% of all temporary-visa doctorates")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
