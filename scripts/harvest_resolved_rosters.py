#!/usr/bin/env python3
"""Archive the student rosters the URL resolver already found.

WHY THIS AND NOT harvest_lab_rosters. That one works from a hand-written
SEEDS list of seven institutions, which is why the directory shows three
archived rosters and looks like the work stopped. The resolver has since
found 236 departments that publish a student roster or a directory,
across 37 states. Those are the pages to archive; nobody needs to type
them in.

REGION BEFORE RANK. Sorting by non-resident share alone would archive
the same handful of small programmes and the page would say nothing
about the country. This fills each census region in turn -- West,
Midwest, South, Northeast -- taking the strongest unarchived candidate
from each before coming back round. A reader should be able to find
their own part of the country on the page.

BOTH MEASURES ARE KEPT. Share says how concentrated a programme is,
volume says how many people it graduates, and they rank almost
oppositely. Each row carries both, and the directory can sort on
either.

Totals only. No per-person label leaves composition(), which is the
same rule the original harvester follows.

Usage:
  python3 scripts/harvest_resolved_rosters.py --limit 24
  python3 scripts/harvest_resolved_rosters.py --region West --limit 8
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402
import harvest_lab_rosters as hl                               # noqa: E402

URLS = ROOT / "data" / "labs" / "program_urls.json"
FIELDS = ROOT / "site" / "data" / "exports" / "field_by_institution.parquet"
OUT = ROOT / "data" / "labs" / "resolved_rosters.json"

REGIONS = {
    "West": set("WA OR CA NV AZ UT ID MT WY CO NM AK HI".split()),
    "Midwest": set("OH IN IL MI WI MN IA MO ND SD NE KS".split()),
    "South": set("TX OK AR LA MS AL TN KY GA FL SC NC VA WV MD DE DC".split()),
    "Northeast": set("NY PA NJ CT RI MA VT NH ME".split()),
}


def region_of(state: str) -> str:
    for name, states in REGIONS.items():
        if state in states:
            return name
    return "?"


def candidates() -> list[dict]:
    """Every resolved department with a student roster, with its state
    and both measures attached."""
    rows = json.loads(URLS.read_text())["rows"]
    con = duckdb.connect()
    facts = con.sql(f"""
        SELECT institution, state,
               SUM(nonresident) AS nra, SUM(awards) AS awards
        FROM '{FIELDS}' WHERE institution IS NOT NULL
        GROUP BY institution, state""").fetchall()
    by_inst = {r[0]: r for r in facts}

    def look(name: str):
        if name in by_inst:
            return by_inst[name]
        for k, v in by_inst.items():
            if k.lower().startswith(name.lower()[:16]):
                return v
        return None

    out = []
    for r in rows:
        if r.get("status") != "ok":
            continue
        url = r.get("students_url") or r.get("directory_url")
        if not url:
            continue
        f = look(r["institution"])
        state = f[1] if f else "?"
        nra = f[2] if f else 0
        awards = f[3] if f else 0
        out.append({
            "institution": r["institution"], "sector": r["sector"],
            "url": url, "state": state, "region": region_of(state),
            "nonresident": int(nra or 0), "awards": int(awards or 0),
            "nonresident_pct": round((nra or 0) / awards * 100, 1)
                               if awards else None,
            "is_student_page": bool(r.get("students_url")),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--region", choices=list(REGIONS))
    ap.add_argument("--ignore-robots", action="store_true")
    a = ap.parse_args()
    if a.ignore_robots:
        hl.IGNORE_ROBOTS = True

    cands = candidates()
    done = set()
    if OUT.exists():
        done = {r["url"] for r in json.loads(OUT.read_text()).get("rows", [])}

    pools: dict = {k: [] for k in REGIONS}
    for c in cands:
        if c["url"] in done or c["region"] not in pools:
            continue
        pools[c["region"]].append(c)
    for k in pools:
        #: a real student page before a generic directory, then by the
        #: concentration, then by how many people it graduates
        pools[k].sort(key=lambda r: (not r["is_student_page"],
                                     -(r["nonresident_pct"] or 0),
                                     -r["nonresident"]))

    #: round robin, so no region is crowded out by another
    picked, order = [], [k for k in REGIONS if pools[k]]
    while order and len(picked) < a.limit:
        for k in list(order):
            if a.region and k != a.region:
                order.remove(k)
                continue
            if not pools[k]:
                order.remove(k)
                continue
            picked.append(pools[k].pop(0))
            if len(picked) >= a.limit:
                break

    print(f"Archiving {len(picked)} rosters")
    for p in picked:
        print(f"  {p['region']:10} {p['state']:3} {p['institution'][:32]:34} "
              f"{p['nonresident_pct'] or 0:>5}%  {p['nonresident']:>5} nra")

    rows = []
    if OUT.exists():
        rows = json.loads(OUT.read_text()).get("rows", [])
    cache: dict = {}
    for p in picked:
        #: harvest(key, cfg, cache) is the existing entry point and it
        #: takes a seed list, so one page is a one-item list.
        key = p["institution"].lower().replace(" ", "_")[:28]
        try:
            got = hl.harvest(key, {"seeds": [p["url"]],
                                   "institution": p["institution"]}, cache)
        except Exception as e:                                 # noqa: BLE001
            print(f"    error {p['institution'][:28]}: {str(e)[:50]}")
            got = None
        #: A PAGE THAT IS NOT A ROSTER MUST NOT GET A COMPOSITION. Some
        #: resolved "student" pages are section landing pages: Stanford's
        #: returns "Page Not Found", UT Dallas's is a student-resources
        #: page. The extractor then returns navigation, and a share
        #: computed over navigation is a number with no meaning that
        #: looks exactly like a finding. Under ten clean names, the page
        #: is recorded as having no roster and carries no percentage.
        for g in (got or []):
            #: the key is members_detected, not total -- reading the
            #: wrong one made every single page look empty and gated
            #: out all 36, including one with 640 names on it
            n = (g.get("composition") or {}).get("members_detected") or 0
            if g.get("status") == "ok" and n < 10:
                g["status"] = "no_roster"
                g["reason"] = f"only {n} person-shaped names; not a roster"
                g.pop("composition", None)
        if got:
            for g in got:
                g.update({k: p[k] for k in
                          ("institution", "state", "region", "sector",
                           "nonresident", "awards", "nonresident_pct")})
                rows.append(g)

    write_text(OUT, json.dumps({
        "note": ("Rosters archived from the URL resolver's output, filled "
                 "region by region so the page is not four programmes in "
                 "one state. Totals only; no per-person label is stored."),
        "regions": {k: sum(1 for r in rows if r.get("region") == k)
                    for k in REGIONS},
        "count": len(rows), "rows": rows}, indent=2))
    print(f"\n  {len(rows)} archived, wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
