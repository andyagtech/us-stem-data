#!/usr/bin/env python3
"""How many permanent residents were already here on a temporary visa?

The degree data counts visa holders, and the SDR shows that most who earn a
doctorate on one end up settling. Both are about a specific population. This
is the same question asked of the whole immigration system, from the other
end: of the people granted employment-based permanent residence, how many
were new arrivals, and how many were already in the country on a
non-immigrant visa and adjusted status?

DHS publishes exactly that split. Table 6 of the Yearbook reports every major
class of admission three times over -- a TOTAL block, an ADJUSTMENTS OF
STATUS block, and a NEW ARRIVALS block -- so the share is read directly
rather than inferred.

WHAT AN ADJUSTMENT MEANS. The person was physically present in the United
States in some other status and changed to permanent residence without
leaving. For the employment classes that status is usually H-1B, and before
that often F-1 and OPT. The table does not record the prior status, so this
measures the ROUTE, not the sequence: it establishes that the person was
already here, not which visa brought them.

Usage:
  python3 scripts/build_lpr_adjustments.py
"""
from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "dhs_yearbook" / "lpr_fy2023.xlsx"
OUT = ROOT / "site" / "data" / "lpr_adjustments.json"

BLOCKS = {"TOTAL": "total",
          "ADJUSTMENTS OF STATUS": "adjustment",
          "NEW ARRIVALS": "new_arrival"}

# Classes worth carrying. "Employment-based preferences" is the one the
# argument rests on; the others are context, so a reader can see that the
# employment route is not simply typical of everything.
KEEP = {"Total": "All classes",
        "Employment-based preferences": "Employment-based",
        "Family-sponsored preferences": "Family-sponsored",
        "Immediate relatives of U.S. citizens": "Immediate relatives",
        "Diversity": "Diversity lottery",
        "Refugees": "Refugees",
        "Asylees": "Asylees"}


def clean(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().rstrip("1234567890").strip()


def main() -> int:
    if not SRC.exists():
        print(f"  missing {SRC.relative_to(ROOT)}")
        return 1
    import openpyxl
    ws = openpyxl.load_workbook(SRC)["Table 6"]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]

    years, hdr_at = [], None
    for i, r in enumerate(rows[:12]):
        cand = [str(x).strip() for x in r[1:] if x is not None]
        if len(cand) >= 5 and all(re.fullmatch(r"(19|20)\d\d", c) for c in cand):
            years, hdr_at = cand, i
            break
    if not years:
        print("  could not find the year header")
        return 1

    data: dict[str, dict[str, dict[str, int]]] = {}
    block = None
    for r in rows[hdr_at + 1:]:
        label = clean(r[0])
        # Block headers are all-caps in the sheet and every block also has a
        # "Total" ROW inside it. Matching case-insensitively made that row
        # look like the TOTAL block header and silently reset the block, so
        # the adjustment and new-arrival figures were filed under total.
        if label in BLOCKS:
            block = BLOCKS[label]
            continue
        if block is None or label not in KEEP:
            continue
        vals = {}
        for y, v in zip(years, r[1:]):
            if isinstance(v, (int, float)):
                vals[y] = int(v)
        if vals:
            data.setdefault(KEEP[label], {})[block] = vals

    emp = data.get("Employment-based", {})
    if not {"total", "adjustment", "new_arrival"} <= set(emp):
        print(f"  employment-based is missing a block: {sorted(emp)}")
        return 1

    # Each class must reconcile: adjustments plus new arrivals is the total.
    warns = []
    for name, blocks in data.items():
        if not {"total", "adjustment", "new_arrival"} <= set(blocks):
            warns.append(f"{name}: missing a block")
            continue
        for y in years:
            t = blocks["total"].get(y)
            a = blocks["adjustment"].get(y)
            n = blocks["new_arrival"].get(y)
            if None in (t, a, n):
                continue
            # DHS rounds every cell to the nearest ten, so the parts can miss
            # the published total by a few units without anything being wrong.
            if abs((a + n) - t) > 30:
                warns.append(f"{name} {y}: {a:,}+{n:,} != {t:,}")

    share = {y: round(100 * emp["adjustment"][y] / emp["total"][y], 1)
             for y in years if emp["total"].get(y)}

    doc = {
        "_comment": (
            "Persons obtaining lawful permanent residence by major class and "
            "by TYPE -- adjustment of status against new arrival. An "
            "ADJUSTMENT means the person was already in the United States in "
            "another status and became a permanent resident without leaving. "
            "The table does NOT record the prior status, so this shows that "
            "the person was already here, not which visa brought them and not "
            "that they studied here. COUNTS ARE PERSONS, rounded by DHS to "
            "the nearest ten, so parts need not sum exactly to totals."),
        "source": "DHS Office of Homeland Security Statistics, Yearbook of "
                  "Immigration Statistics, table 6",
        "source_file": SRC.name,
        "years": [int(y) for y in years],
        "classes": data,
        "employment_based_adjustment_share_pct": share,
        "warnings": warns,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    f, l = years[0], years[-1]
    print(f"  {len(years)} years, {f}-{l}")
    print(f"  {'class':22}{'adjustment share ' + f:>22}{'  ' + l:>10}")
    for name, blocks in data.items():
        if {"total", "adjustment"} <= set(blocks) and blocks["total"].get(f):
            a = 100 * blocks["adjustment"][f] / blocks["total"][f]
            b = 100 * blocks["adjustment"][l] / blocks["total"][l]
            print(f"  {name:22}{a:>21.1f}%{b:>9.1f}%")
    print(f"  employment-based {l}: {emp['adjustment'][l]:,} of {emp['total'][l]:,} "
          f"were already here ({share[l]}%)")
    for w in warns:
        print(f"  WARN {w}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
