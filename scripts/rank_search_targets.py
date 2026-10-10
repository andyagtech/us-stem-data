#!/usr/bin/env python3
"""Where to look for lab rosters next, ranked by the data we already hold.

The roster harvester needs seeds, and hand-picking them does not scale to
the hundreds of examples the question deserves. This ranks every
university-and-department pair the dissertation record covers, so the
search goes where the concentration actually is rather than where someone
happened to look.

HOW IT RANKS. Four things, and each is a number this project already
publishes:

  SIZE        a department with eleven doctorates is noise at any share
  CONCENTRATION  the share of its thesis authors carrying name markers
  INSTITUTION the university's own non-resident share, from IPEDS
  SECTOR      whether the field is one of the critical industries, which
              is where the national-security question actually bites

WHAT THIS IS AND IS NOT. It is a list of DEPARTMENTS to go and read the
public roster pages of. It names no individual, and the per-author
classification that produces a department share is computed here and
discarded -- only the totals are written, the same rule the harvester
follows.

A share here is a FLOOR. The classifier is conservative and skips names it
cannot place, so a department's real concentration is at least what this
reports.

Usage:
  python3 scripts/rank_search_targets.py
  python3 scripts/rank_search_targets.py --critical-only --top 40
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

OUT = ROOT / "data" / "labs" / "search_targets.json"
MIN_RECORDS = 40          # below this a share is not a finding

#: Department-name fragments that place a department in a critical sector.
#: Matched on the department string the harvest recorded, which is messy
#: and institution-specific, so this is deliberately generous: a false
#: positive costs one wasted page fetch, a false negative loses a target.
CRITICAL = {
    "ai": ("computer sci", "computing", "artificial intel", "machine learning",
           "data scien", "informatics", "electrical", "computer eng"),
    "aerospace": ("aerospace", "aeronaut", "astronaut", "avionic"),
    "nuclear": ("nuclear", "radiolog", "health physics"),
    "battery": ("materials sci", "materials eng", "chemical eng",
                "electrochem"),
    "mining": ("mining", "metallurg", "geolog", "earth scien", "mineral"),
    "petroleum": ("petroleum", "energy resources", "reservoir"),
    "semiconductor": ("microelectron", "semiconductor", "solid state",
                      "photonic", "optoelectron"),
    "robotics": ("robotic", "mechatronic", "control system"),
    "bio": ("bioengineer", "biomedical eng", "synthetic bio", "genom"),
}


def sector_for(dept: str) -> str | None:
    d = dept.lower()
    for sector, frags in CRITICAL.items():
        if any(f in d for f in frags):
            return sector
    return None


def institution_nra() -> dict:
    """IPEDS/GSS non-resident share per institution, keyed loosely."""
    f = ROOT / "site" / "data" / "gss_institution_ranking.json"
    out = {}
    if not f.exists():
        return out
    for r in json.loads(f.read_text()).get("institutions", []):
        doc = r.get("doctoral") or {}
        if doc.get("total", 0) >= 100:
            out[r["institution"].lower()] = doc.get("share", 0.0)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--critical-only", action="store_true")
    ap.add_argument("--top", type=int, default=60)
    a = ap.parse_args()

    try:
        import name_classifier as nc
    except Exception as e:                                     # noqa: BLE001
        print(f"  name classifier unavailable: {e}")
        return 1

    nra = institution_nra()
    rows = []
    for track in ("stem", "nonstem"):
        d = ROOT / "site" / "data" / track
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.json")):
            if f.name.startswith("_"):
                continue
            blob = json.loads(f.read_text())
            uni, key = blob.get("name") or f.stem, blob.get("key") or f.stem
            uni_share = blob.get("nra")
            #: fall back to the survey where the harvest has no IPEDS share
            if uni_share is None:
                uni_share = next((v for k, v in nra.items()
                                  if uni.lower()[:14] in k), None)
            by_dept = collections.defaultdict(list)
            for r in blob.get("records") or []:
                if isinstance(r, list) and len(r) > 2 and isinstance(r[2], str):
                    by_dept[r[0]].append(r[2])
            for dept, names in by_dept.items():
                if len(names) < MIN_RECORDS:
                    continue
                #: classification happens here and is thrown away; only the
                #: counts below leave this loop.
                cn = sum(1 for n in names if nc.is_chinese(n))
                inn = sum(1 for n in names if nc.is_indian(n))
                sector = sector_for(dept)
                if a.critical_only and not sector:
                    continue
                share_cn = cn / len(names) * 100
                #: The score answers "where is the concentration worth a
                #: look", so it leans on the Chinese-marker share and the
                #: institution's own non-resident share, with size as a
                #: confidence weight and a bonus for a critical sector.
                import math
                score = (share_cn * 1.0
                         + (uni_share or 0) * 0.35
                         + math.log10(len(names)) * 8
                         + (14 if sector else 0))
                rows.append({
                    "university": uni, "key": key, "department": dept,
                    "records": len(names),
                    "share_chinese_markers": round(share_cn, 1),
                    "share_indian_markers": round(inn / len(names) * 100, 1),
                    "institution_nra_share": uni_share,
                    "critical_sector": sector,
                    "score": round(score, 1),
                    "search": (f"https://www.google.com/search?q="
                               f"{'+'.join((uni + ' ' + dept + ' lab members').split())}"),
                })

    rows.sort(key=lambda r: -r["score"])
    payload = {
        "built_from": "site/data/{stem,nonstem}/*.json, gss_institution_ranking",
        "min_records": MIN_RECORDS,
        "note": ("Departments ranked as places to go and read public lab "
                 "roster pages. Shares are counts of NAME MARKERS over "
                 "thesis authors, not nationalities, and are floors because "
                 "the classifier skips names it cannot place. No individual "
                 "is named or labelled."),
        "departments_ranked": len(rows),
        "targets": rows[:a.top],
    }
    write_text(OUT, json.dumps(payload, indent=2))

    print(f"  {len(rows)} departments clear {MIN_RECORDS} records\n")
    print(f"  {'university':<22}{'department':<30}{'recs':>6}{'cn%':>7}  sector")
    for r in rows[:a.top]:
        print(f"  {r['university'][:21]:<22}{r['department'][:29]:<30}"
              f"{r['records']:>6}{r['share_chinese_markers']:>7}  "
              f"{r['critical_sector'] or ''}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
