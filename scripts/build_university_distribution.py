#!/usr/bin/env python3
"""Per-university department distributions — the spread inside one institution.

WHY THIS IS THE MORE HONEST CHART

A single headline share per university invites the wrong reading. MIT is not
"43.8% non-resident" in any meaningful sense: it runs from 15.8% in biology to
73.2% in computer science, and the average describes none of its departments.
The same is true everywhere, and it is the site's whole argument applied one
level down — an average hiding a distribution.

It also makes each university page checkable in a way a single number is not. A
reader who knows one department can look for it, and if the figure is wrong for
the department they know, they will say so.

WHAT COUNTS

One 4-digit CIP programme at one institution, pooled over 2015–2022, with at
least 15 research doctorates in that window. The floor keeps out programmes
where one or two students move the share twenty points.

Grain is 4-digit deliberately: at 2-digit, "Engineering" at Purdue collapses
sixteen distinct programmes running from 30% to 82% into a single bar, which is
precisely the averaging this chart exists to undo.

Usage:
    python3 scripts/build_university_distribution.py
    python3 scripts/build_university_distribution.py --key purdue
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
REGISTRY = ROOT / "pipeline" / "universities.json"
DEFAULT_OUT = ROOT / "site" / "data" / "university_distribution.json"

sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW, bases_for          # noqa: E402

YEAR_LO, YEAR_HI = 2015, 2022
MIN_DEPT = 15


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


def build():
    reg = json.loads(REGISTRY.read_text())
    u2k = {str(v["unitid"]): k for k, v in reg.items() if v.get("unitid")}
    names = {str(v["unitid"]): v.get("name", k) for k, v in reg.items() if v.get("unitid")}
    cip = titles()

    acc = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            year = int(row["year"])
            if not (YEAR_LO <= year <= YEAR_HI) or row["basis"] not in bases_for(year):
                continue
            code = row["cipcode"]
            if code.split(".")[0].zfill(2) not in STEM_NARROW or "." not in code:
                continue
            uid = row["unitid"]
            if uid not in u2k:
                continue
            slot = acc[uid][code]
            slot[0] += int(row["total"])
            slot[1] += int(row["nra"])

    out = {}
    for uid, depts in acc.items():
        rows = [{"cip": c, "title": cip.get(c, ""), "total": t, "nra": n,
                 "share": round(100 * n / t, 1)}
                for c, (t, n) in depts.items() if t >= MIN_DEPT]
        if len(rows) < 3:
            continue
        rows.sort(key=lambda r: -r["share"])
        shares = [r["share"] for r in rows]
        tot = sum(r["total"] for r in rows)
        nra = sum(r["nra"] for r in rows)
        out[u2k[uid]] = {
            "key": u2k[uid],
            "unitid": uid,
            "institution": names.get(uid, uid),
            "departments": len(rows),
            "majority_non_resident": sum(1 for s in shares if s > 50),
            "at_or_above_70": sum(1 for s in shares if s >= 70),
            "pooled_share": round(100 * nra / tot, 1) if tot else None,
            "median_share": round(sorted(shares)[len(shares) // 2], 1),
            "min_share": min(shares),
            "max_share": max(shares),
            "spread": round(max(shares) - min(shares), 1),
            "doctorates": tot,
            "depts": rows,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--key", help="print one university's distribution")
    args = ap.parse_args()

    data = build()

    if args.key:
        d = data.get(args.key)
        if not d:
            sys.exit(f"No distribution for {args.key!r}. "
                     f"Known: {', '.join(sorted(data)[:12])} …")
        print(f"{d['institution']} — {d['departments']} departments, "
              f"{YEAR_LO}–{YEAR_HI}, {MIN_DEPT}+ doctorates each\n")
        print(f"{'share':>7}{'PhDs':>7}  programme")
        for r in d["depts"]:
            bar = "#" * round(r["share"] / 4)
            print(f"{r['share']:>6.1f}%{r['total']:>7}  {(r['title'] or r['cip'])[:34]:<34} {bar}")
        print(f"\npooled {d['pooled_share']}% · median {d['median_share']}% · "
              f"range {d['min_share']}–{d['max_share']}% · "
              f"{d['majority_non_resident']} of {d['departments']} majority non-resident")
        return 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":")))

    ranked = sorted(data.values(), key=lambda d: -d["spread"])
    print(f"{len(data)} universities with 3+ qualifying departments\n")
    print("Widest internal spread — where a single headline share misleads most:")
    print(f"{'spread':>8}{'min':>7}{'max':>7}{'depts':>7}{'maj':>5}  institution")
    for d in ranked[:12]:
        print(f"{d['spread']:>7.1f}{d['min_share']:>7.1f}{d['max_share']:>7.1f}"
              f"{d['departments']:>7}{d['majority_non_resident']:>5}  {d['institution'][:34]}")
    print(f"\nwrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
