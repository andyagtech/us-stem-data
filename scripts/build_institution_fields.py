#!/usr/bin/env python3
"""Top non-resident fields inside each of the largest doctorate producers.

The national programme ranking answers "which fields run highest across the
country". It cannot answer "what is Purdue's non-resident share made of",
because a national CIP total pools every institution together.

This computes, for each of the largest core-STEM doctorate producers, the
fields contributing most of its non-resident doctorates -- pooled over the
same 2021-2025 window and the same eight CIP families as the rest of the
report, so the figures add up to the institution totals published there.

Fields are 4-digit CIP. The rollup rows IPEDS carries for each family
(CIPCODE ending .00, and the "99" totals) are skipped, or every institution
would appear to have one enormous field that is really the sum of the rest.

Usage:
  python3 scripts/build_institution_fields.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW  # noqa: E402

IPEDS = ROOT / "data" / "ipeds"
RANKS = ROOT / "site" / "data" / "level_rankings.json"
OUT = ROOT / "site" / "data" / "institution_fields.json"

WINDOW = (2021, 2025)
TOP_N_INSTITUTIONS = 8
TOP_N_FIELDS = 5


def award_levels(year: int) -> set[str]:
    """Research doctorate: 17 from 2010, legacy 9 before it."""
    return {"17"} if year >= 2010 else {"9"}


def rows_for(year: int):
    for name in (f"c{year}_a.csv", f"C{year}_a.csv", f"C{year}_A.csv"):
        p = IPEDS / name
        if p.exists():
            with open(p, newline="", encoding="utf-8-sig", errors="replace") as fh:
                yield from csv.DictReader(fh)
            return
    for name in (f"C{year}_A.zip", f"c{year}_a.zip"):
        p = IPEDS / name
        if p.exists():
            with zipfile.ZipFile(p) as z:
                inner = next(n for n in z.namelist() if n.lower().endswith(".csv"))
                with z.open(inner) as fh:
                    yield from csv.DictReader(
                        io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace"))
            return


def cip_names() -> dict[str, str]:
    """4-digit CIP -> display name, gathered from the site data already built.

    IPEDS completions files carry the code and not the label, and the two
    datasets that do carry labels disagree on the key: level_rankings uses
    "name", programme_shares uses "title". Reading only one leaves fields
    showing as bare codes like 40.0501 on a page meant for a legislator.
    """
    out: dict[str, str] = {}

    def walk(node):
        if isinstance(node, dict):
            cip = node.get("cip") or node.get("key")
            label = node.get("name") or node.get("title")
            if isinstance(cip, str) and isinstance(label, str) \
                    and len(cip) >= 7 and cip[2] == "." and label[:1].isalpha():
                out.setdefault(cip[:7], label)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for f in ("level_rankings.json", "programme_shares.json",
              "concentration_cases.json", "university_distribution.json"):
        path = ROOT / "site" / "data" / f
        if path.exists():
            walk(json.loads(path.read_text()))
    return out


def main() -> int:
    ranks = json.loads(RANKS.read_text())
    biggest = ranks["levels"]["doctorate"]["biggest"][:TOP_N_INSTITUTIONS]
    wanted = {b["key"]: b for b in biggest}
    names = cip_names()

    tally: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for year in range(WINDOW[0], WINDOW[1] + 1):
        want = award_levels(year)
        for row in rows_for(year):
            unitid = (row.get("UNITID") or "").strip()
            if unitid not in wanted:
                continue
            if (row.get("AWLEVEL") or "").lstrip("0") not in want:
                continue
            cip = (row.get("CIPCODE") or "").strip()
            if cip.split(".")[0].zfill(2) not in set(STEM_NARROW):
                continue
            # Family rollups would otherwise dominate every institution.
            if cip.endswith(".00") or "." not in cip or cip.startswith("99"):
                continue
            try:
                tot, nra = int(row.get("CTOTALT") or 0), int(row.get("CNRALT") or 0)
            except ValueError:
                continue
            if int(row.get("MAJORNUM") or 1) != 1:
                continue
            t = tally[unitid][cip[:7]]
            t[0] += tot
            t[1] += nra

    out = []
    for b in biggest:
        fields = tally.get(b["key"], {})
        top = sorted(fields.items(), key=lambda kv: -kv[1][1])[:TOP_N_FIELDS]
        rows = [{"cip": c, "name": names.get(c, c),
                 "total": v[0], "nra": v[1],
                 "share": round(100 * v[1] / v[0], 1) if v[0] else 0.0}
                for c, v in top]
        covered = sum(r["nra"] for r in rows)
        out.append({
            "unitid": b["key"], "institution": b["name"],
            "nra": b["nra"], "total": b["total"], "share": b["share"],
            "fields_counted": len(fields),
            "top_fields": rows,
            "top_share_of_nra": round(100 * covered / b["nra"], 1) if b["nra"] else 0.0,
        })
        print(f"  {b['name'][:38]:40} {b['nra']:>5,} NRA across {len(fields):>3} fields; "
              f"top {len(rows)} hold {out[-1]['top_share_of_nra']:.0f}%")

    OUT.write_text(json.dumps({
        "_comment": ("Fields contributing most of each large producer's non-resident "
                     "doctorates, 2021-2025. 4-digit CIP within the eight core-STEM "
                     "families; IPEDS family rollup rows are excluded, so these sum "
                     "toward the institution total rather than double-counting it."),
        "source": "NCES IPEDS Completions",
        "window": list(WINDOW),
        "institutions": out,
    }, indent=1) + "\n")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
