#!/usr/bin/env python3
"""NSF awards for the institutions that host the lab directory's groups.

WHY A SECOND FETCHER. fetch_nsf_awards.py reads its universe from
site/data/stem/*.json -- the 106 universities this site publishes a page for.
The lab directory was assembled by CRAWLING, so it reaches institutions that
set never contained: of the 39 hosting a published group, 21 were already in
nsf_by_university.json and 3 more under a different spelling. Nine -- Johns
Hopkins, Princeton, NYU, Georgia Tech, Brown, Lehigh, Stevens, Lamar, Florida
State -- were simply absent.

Rather than widen a catalogued dataset's universe, which would change what
every figure built on it means, this writes its own file for the gap.

WHAT THIS IS FOR, AND WHAT IT IS NOT. The lab directory says these groups run
on federal money. That is true and, until now, unevidenced on the page. This
supplies the evidence at INSTITUTION level: what NSF obligated to the
university, over a stated window.

It does NOT attribute that money to a particular group, and the join cannot
support it. A PI-level match was tried first and abandoned: the only name on a
lab row is the page's <title>, and 56 of 94 produce nothing usable --
"Students and Postdocs", "Team Members", "Information Processing Lab". A
figure that looked per-lab but was really per-institution would be the exact
upgrade this project's rules forbid.

Usage:
  python3 scripts/fetch_lab_institution_grants.py --report
  python3 scripts/fetch_lab_institution_grants.py --years 2020-2024
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_nsf_awards as NSF                              # noqa: E402
from lab_overrides import apply as apply_overrides          # noqa: E402

#: NSF names an awardee its own way, and the lab rows carry the IPEDS name or
#: this site's short one. Seven came back with ZERO awards on the first run --
#: not because the money is not there, but because nothing matched the string.
#: A zero from a name miss and a zero from no funding are not the same fact,
#: and only one of them is true here.
ALIASES = {
    "Georgia Institute of Technology-Main Campus": "Georgia Tech Research Corporation",
    "Pennsylvania State University-Main Campus": "Pennsylvania State Univ University Park",
    "Stony Brook University": "SUNY at Stony Brook",
    "U Delaware": "University of Delaware",
    "UC Santa Barbara": "University of California-Santa Barbara",
    "UW Seattle": "University of Washington",
    "University of Illinois Urbana-Champaign": "University of Illinois at Urbana-Champaign",
}

LABS = ROOT / "data" / "labs" / "lab_outliers.json"
EXISTING = ROOT / "data" / "state_funding" / "nsf_awards" / "nsf_by_university.json"
OUT = ROOT / "data" / "labs" / "nsf_by_lab_institution.json"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def lab_institutions() -> list[str]:
    rows = apply_overrides(list(json.loads(LABS.read_text())["outliers"]))
    return sorted({r["institution"] for r in rows if r.get("institution")})


def already_known() -> dict[str, dict]:
    """Institution name (normalised) -> the aggregate already on disk."""
    if not EXISTING.exists():
        return {}
    out = {}
    for key, v in json.loads(EXISTING.read_text()).items():
        for name in [v.get("name", "")] + list(v.get("appears_as") or []):
            if name:
                out.setdefault(_norm(name), dict(v, key=key))
    return out


def resolve(name: str, known: dict) -> dict | None:
    hit = known.get(_norm(name))
    if hit:
        return hit
    n = _norm(name)
    cands = [v for k, v in known.items() if n and (n in k or k in n)]
    return cands[0] if len(cands) == 1 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2020-2024")
    ap.add_argument("--report", action="store_true",
                    help="say what is missing and fetch nothing")
    args = ap.parse_args()
    lo, _, hi = args.years.partition("-")
    lo, hi = int(lo), int(hi or lo)
    # aggregate() buckets by NSF.YEARS, so setting only the dates would
    # silently keep the module default window.
    NSF.DATE_START, NSF.DATE_END = f"01/01/{lo}", f"12/31/{hi}"
    NSF.YEARS = [str(y) for y in range(lo, hi + 1)]

    insts = lab_institutions()
    known = already_known()
    have = [i for i in insts if resolve(i, known)]
    gap = [i for i in insts if not resolve(i, known)]
    print(f"  {len(insts)} institutions host a published group")
    print(f"  {len(have)} already in nsf_by_university.json")
    print(f"  {len(gap)} to fetch: {', '.join(gap)}")
    if args.report:
        return 0

    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    for i, name in enumerate(gap, 1):
        if name in out:
            print(f"  [{i}/{len(gap)}] {name}: already fetched, skipping")
            continue
        awardee = ALIASES.get(name, name)
        note = f" (as \"{awardee}\")" if awardee != name else ""
        print(f"  [{i}/{len(gap)}] {name}{note}", flush=True)
        try:
            awards = NSF.fetch_all_awards(awardee)
        except Exception as exc:                            # noqa: BLE001
            print(f"      FAILED: {exc}", flush=True)
            continue
        # aggregate() already returns {by_year, total_awards,
        # total_obligated_5yr}; wrapping it again put ints where the reader
        # expected per-year dicts.
        agg = NSF.aggregate(awards)
        # `resolved` is the honest flag: a zero here means the API returned
        # nothing for that string, which is a failed lookup until someone
        # finds the name NSF uses. Downstream must not read it as "no federal
        # funding".
        out[name] = dict(agg, name=name, awardee_searched=awardee,
                         window=f"{lo}-{hi}",
                         resolved=bool(agg.get("total_awards")))
        # Written after every institution: the fetch is slow and a dropped
        # connection must not cost the ones already paid for.
        OUT.write_text(json.dumps(out, indent=1, sort_keys=True))
        n = out[name]["total_awards"]
        d = out[name]["total_obligated_5yr"]
        print(f"      {n:,} awards, ${d/1e6:,.1f}m obligated", flush=True)
        time.sleep(NSF.SLEEP_SECS)
    print(f"  wrote {OUT.relative_to(ROOT)}: {len(out)} institutions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
