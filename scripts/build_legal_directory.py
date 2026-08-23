#!/usr/bin/env python3
"""Publish the searchable directory of who files university H-1B paperwork.

WHAT IS INCLUDED, AND WHY
    Everything DOL discloses about the filer: name, firm, email, phone,
    postal address, the universities they file for, and the years they were
    active. These are public records -- an employer is required to file a
    Labor Condition Application and the filer's details are part of the
    public disclosure, published by DOL for exactly this kind of scrutiny.

COVERAGE, WHICH IS NOT THE WHOLE ARCHIVE
    DOL added the attorney name in FY2015 and the law firm in FY2020, so this
    describes about 6% of matched filings. Most universities file without an
    agent at all and name nobody. Every count below is against its own
    denominator and must not be read as a share of all filings.

USAGE
    python3 scripts/build_legal_directory.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGAL = ROOT / "data" / "h1b" / "lca_legal_by_university.json"
GEO = ROOT / "data" / "h1b" / "lca_legal_geo.json"
OUT = ROOT / "site" / "data" / "legal_directory.json"


def best(pairs: list, n: int = 1):
    """The most-used value(s), which for a contact means the current one."""
    return [p[0] for p in pairs[:n]]


def main() -> int:
    for f in (LEGAL, GEO):
        if not f.exists():
            print(f"  {f} missing")
            return 1
    legal = json.loads(LEGAL.read_text())
    geo = json.loads(GEO.read_text())
    firms, attys = legal["firms"], legal["attorneys"]
    gatt, gfirm = geo["attorneys"], geo["firms"]

    people = []
    for name, v in sorted(attys.items(), key=lambda kv: -kv[1]["filings"]):
        loc = (gatt.get(name) or {}).get("location") or {}
        people.append({
            "name": name,
            "filings": v["filings"],
            "firm": (v["firms"][0][0] if v["firms"] else None),
            "emails": best(v["emails"], 2),
            "phones": best(v["phones"], 2),
            "address": (v["addresses"][0][0] if v["addresses"] else None),
            "city": loc.get("city"), "state": loc.get("state"),
            "lat": loc.get("lat"), "lon": loc.get("lon"),
            "located_by": loc.get("matched_on"),
            "first_year": v.get("first_year"), "last_year": v.get("last_year"),
            "universities": [[u, n] for u, n in v["universities"][:6]],
        })

    orgs = []
    for name, v in sorted(firms.items(), key=lambda kv: -kv[1]["filings"]):
        g = gfirm.get(name) or {}
        orgs.append({
            "name": name,
            "filings": v["filings"],
            "feins": best(v["feins"], 1),
            "attorneys": [[a, n] for a, n in v["attorneys"][:8]],
            "universities": [[u, n] for u, n in v["universities"][:10]],
            "offices": [f"{c}, {s}" for c, s in (g.get("offices") or [])][:6],
            "lat": g.get("lat"), "lon": g.get("lon"),
        })

    total = sum(f["filings"] for f in orgs)
    payload = {
        "source": "US DOL OFLC Labor Condition Application disclosure files",
        "note": ("Public disclosure. DOL began publishing the attorney name in "
                 "FY2015 and the law firm in FY2020, so this covers about 6% "
                 "of matched filings; most universities file without an agent "
                 "and name nobody."),
        "counts": {
            "firms": len(orgs), "attorneys": len(people),
            "filings_with_a_named_firm": total,
            "matched_filings": legal["_meta"]["rows_matched_to_a_university"],
            "attorneys_located": sum(1 for p in people if p["lat"]),
        },
        "firms": orgs,
        "attorneys": people,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.partial")
    tmp.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    os.replace(tmp, OUT)
    print(f"  {len(orgs)} firms, {len(people)} attorneys "
          f"({payload['counts']['attorneys_located']} located)")
    print(f"  wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
