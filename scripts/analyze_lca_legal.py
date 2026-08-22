#!/usr/bin/env python3
"""Who files the H-1B paperwork for American universities.

Reads data/h1b/lca_legal_by_university.json and reports the firms and
attorneys behind university LCA filings: who files most, how concentrated the
market is, who serves the most institutions, and which universities file for
themselves.

COVERAGE, WHICH IS UNEVEN BY DESIGN OF THE SOURCE
    The law firm's own name only appears in DOL's layout from FY2020, and the
    attorney's name from FY2015. FY2008-FY2014 carry neither. So firm figures
    describe FY2020 onward and attorney figures FY2015 onward -- they are NOT
    shares of the whole archive, and each is reported against its own
    denominator so it cannot be read as one.

USAGE
    python3 scripts/analyze_lca_legal.py
    python3 scripts/analyze_lca_legal.py --top 40
    python3 scripts/analyze_lca_legal.py --university mit
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "h1b" / "lca_legal_by_university.json"


def bar(n: int, top: int, width: int = 26) -> str:
    return "#" * max(1, round(width * n / top)) if n else ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--university")
    args = ap.parse_args()

    if not SRC.exists():
        print(f"  {SRC} not found. Build it with scripts/aws_lca_rebuild.sh")
        return 1
    d = json.loads(SRC.read_text())
    m, firms, attys, unis = d["_meta"], d["firms"], d["attorneys"], d["universities"]

    print("=" * 76)
    print("  WHO FILES THE H-1B PAPERWORK FOR AMERICAN UNIVERSITIES")
    print("=" * 76)
    print(f"  matched filings        {m['rows_matched_to_a_university']:>10,}")
    print(f"  with a named firm      {m['rows_with_a_named_firm']:>10,}"
          f"   ({100*m['rows_with_a_named_firm']/max(m['rows_matched_to_a_university'],1):.1f}%"
          f" -- firm name exists only from FY2020)")
    print(f"  distinct firms         {m['distinct_firms']:>10,}")
    print(f"  distinct attorneys     {m['distinct_attorneys']:>10,}")
    print(f"  attorneys with email   {m.get('attorneys_with_an_email', 0):>10,}")

    if args.university:
        u = unis.get(args.university)
        if not u:
            print(f"\n  no such university key: {args.university}")
            return 1
        print(f"\n  --- {args.university} ---")
        print(f"  filings {u['rows']:,}   named firm {u['with_named_firm']:,}"
              f"   named attorney {u['with_named_attorney']:,}"
              f"   self-filed {u['self_filed']:,}")
        print("\n  firms:")
        for n, c in u["top_firms"][:12]:
            print(f"    {c:>6,}  {n}")
        print("\n  attorneys:")
        for n, c in u["top_attorneys"][:12]:
            print(f"    {c:>6,}  {n}")
        return 0

    ranked = sorted(firms.items(), key=lambda kv: -kv[1]["filings"])
    total = sum(v["filings"] for v in firms.values())
    print(f"\n  TOP {args.top} FIRMS BY UNIVERSITY FILINGS  (of {total:,} with a named firm)")
    print(f"  {'':>6}  {'filings':>8} {'share':>6} {'unis':>5}  firm")
    peak = ranked[0][1]["filings"] if ranked else 1
    for i, (name, v) in enumerate(ranked[:args.top], 1):
        print(f"  {i:>4}.  {v['filings']:>8,} {100*v['filings']/total:>5.1f}%"
              f" {len(v['universities']):>5}  {name[:44]:<44} {bar(v['filings'], peak)}")

    cum = 0
    marks = {}
    for i, (_, v) in enumerate(ranked, 1):
        cum += v["filings"]
        for t in (25, 50, 75):
            if t not in marks and 100 * cum / total >= t:
                marks[t] = i
    print("\n  CONCENTRATION")
    for t in (25, 50, 75):
        if t in marks:
            print(f"    {marks[t]:>4} firm(s) account for {t}% of filings"
                  f"  ({100*marks[t]/len(ranked):.1f}% of all {len(ranked):,} firms)")

    reach = sorted(firms.items(), key=lambda kv: -len(kv[1]["universities"]))
    print(f"\n  WIDEST REACH  (distinct universities served)")
    for name, v in reach[:10]:
        who = ", ".join(u for u, _ in v["universities"][:5])
        print(f"    {len(v['universities']):>3} unis  {v['filings']:>7,} filings  {name[:38]:<38} {who}")

    pa = sorted(attys.items(), key=lambda kv: -kv[1]["filings"])
    print(f"\n  TOP {min(args.top, 15)} INDIVIDUAL ATTORNEYS")
    for i, (name, v) in enumerate(pa[:min(args.top, 15)], 1):
        firm = v["firms"][0][0][:30] if v["firms"] else "-"
        span = (f"{v['first_year']}-{v['last_year']}"
                if v.get("first_year") else "-")
        print(f"  {i:>4}.  {v['filings']:>6,}  {name[:26]:<26} {span:<10} {firm}")

    selfers = sorted(((v["self_filed"], v["rows"], k) for k, v in unis.items()
                      if v["rows"] >= 200), key=lambda t: -t[0] / max(t[1], 1))
    print(f"\n  MOST LIKELY TO FILE WITHOUT AN AGENT  (>=200 filings)")
    for sf, rows, k in selfers[:10]:
        print(f"    {100*sf/rows:>5.1f}%  {sf:>6,} of {rows:>7,}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
