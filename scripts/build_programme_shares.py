#!/usr/bin/env python3
"""National non-resident share by programme — which fields, not which schools.

The per-university view shows spread inside one institution. This is the other
axis: pooled across every institution, which programmes run high and which run
low. The range is enormous and stable, which is the point — this is a property
of fields, not of particular universities.

    85.3%  Petroleum Engineering            943 doctorates,  16 schools
    71.4%  Electrical & Electronics Eng  17,930 doctorates, 162 schools
    63.1%  Computer Science               8,624 doctorates, 119 schools
     3.5%  Clinical Psychology            8,638 doctorates, 101 schools
     2.5%  Computer & Info Systems Security  511 doctorates,   8 schools
     1.5%  Applied Behavior Analysis        862 doctorates,  12 schools

The security line is worth noticing: information-security doctorates run at
2.5% while general computer science runs at 63.1%. The most plausible reading
is that clearance-adjacent work is effectively closed to non-citizens — which
is a useful control, because it shows the composition is not a fixed property
of "computing" but responds to whether citizenship is required.

That reading is an inference. IPEDS records the degree, not why anyone was
admitted.

Floor: 300 doctorates nationally over 2015-2022, so a programme at two
universities cannot land at the top of the list.

Usage:
    python3 scripts/build_programme_shares.py
    python3 scripts/build_programme_shares.py --min 500
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "ipeds" / "nra_index.csv.gz"
CIP_TITLES = ROOT / "data" / "ipeds" / "cip_titles.csv"
DEFAULT_OUT = ROOT / "site" / "data" / "programme_shares.json"

sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW, bases_for          # noqa: E402
from atomic_write import write_json

YEAR_LO, YEAR_HI = 2015, 2022


def titles() -> dict[str, str]:
    out: dict[str, str] = {}
    if not CIP_TITLES.exists():
        return out
    with open(CIP_TITLES, newline="", encoding="utf-8-sig", errors="replace") as fh:
        for row in csv.DictReader(fh):
            code = (row.get("cipcode") or row.get("CIPCODE") or "").strip()
            title = (row.get("title") or row.get("TITLE") or "").strip()
            if code and title:
                out[code] = title
    return out


def build(min_doctorates: int = 300):
    cip = titles()
    acc = defaultdict(lambda: [0, 0, set()])
    by_year = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            year = int(row["year"])
            if row["basis"] not in bases_for(year):
                continue
            code = row["cipcode"]
            if code.split(".")[0].zfill(2) not in STEM_NARROW or "." not in code:
                continue
            t, n = int(row["total"]), int(row["nra"])
            if YEAR_LO <= year <= YEAR_HI:
                slot = acc[code]
                slot[0] += t
                slot[1] += n
                slot[2].add(row["unitid"])
            ys = by_year[code][year]
            ys[0] += t
            ys[1] += n

    out = []
    for code, (tot, nra, schools) in acc.items():
        if tot < min_doctorates:
            continue
        series = {str(y): round(100 * v[1] / v[0], 1)
                  for y, v in sorted(by_year[code].items()) if v[0] >= 40}
        out.append({
            "cip": code,
            "title": cip.get(code, code),
            "family": code.split(".")[0].zfill(2),
            "doctorates": tot,
            "nra": nra,
            "share": round(100 * nra / tot, 1),
            "institutions": len(schools),
            "series": series,
        })
    out.sort(key=lambda r: -r["share"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--min", type=int, default=300)
    args = ap.parse_args()

    rows = build(args.min)
    payload = {
        "years": [YEAR_LO, YEAR_HI],
        "min_doctorates": args.min,
        "note": ("Pooled across every institution. 4-digit CIP. A programme "
                 "qualifies with at least the stated number of research "
                 "doctorates nationally over the window."),
        "programmes": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, payload, separators=(",", ":"))

    print(f"NATIONAL SHARE BY PROGRAMME, {YEAR_LO}–{YEAR_HI} "
          f"({args.min}+ doctorates)\n")
    print(f"{'share':>7}{'PhDs':>9}{'schools':>9}  programme")
    print("-" * 72)
    for r in rows[:14]:
        print(f"{r['share']:>6.1f}%{r['doctorates']:>9,}{r['institutions']:>9}"
              f"  {r['title'][:42]}")
    print("." * 72)
    for r in rows[-6:]:
        print(f"{r['share']:>6.1f}%{r['doctorates']:>9,}{r['institutions']:>9}"
              f"  {r['title'][:42]}")
    print(f"\n{len(rows)} programmes · range "
          f"{rows[-1]['share']}%–{rows[0]['share']}%")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
