#!/usr/bin/env python3
"""Where the non-resident share is highest -- at BOTH master's and doctorate.

The site has always ranked doctorates. Master's is the larger population and
the one that actually expanded, and it had never been ranked at all.

Four rankings, each at both levels:
    institutions   pooled non-resident share, cohort floor applied
    programmes     4-digit CIP pooled nationally
    fastest risers change in share between an early and a late window
    biggest cohorts largest absolute non-resident counts

WHY A COHORT FLOOR. Share is a ratio, and a ratio on a small denominator is
noise: a programme conferring 4 master's degrees, all to non-residents, reads
100% and means nothing. Floors are applied per ranking and printed with the
result, so a reader can see what was excluded rather than guess.

AWARD LEVELS. 7 is master's. Doctorate is 17 from 2010 and legacy 9 before it;
across the 2008-09 migration institutions each reported exactly one coding, so
both are summed there. This is pipeline.models.bases_for()'s rule and the same
one the rest of the site uses -- getting it wrong understates 2008 by ~79%.

Usage:
    python3 scripts/build_level_rankings.py --report
    python3 scripts/build_level_rankings.py            # writes site/data/level_rankings.json
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from atomic_write import write_json

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW   # noqa: E402
IPEDS = ROOT / "data" / "ipeds"
OUT = ROOT / "site" / "data" / "level_rankings.json"

STEM_CIP2 = STEM_NARROW   # single source: pipeline/models.py.
# Seven scripts each carried their own copy of this set. They all happened
# to agree, which is exactly why the drift would have been silent: change
# models.py and the copies keep the old definition without a word.
LATE = (2021, 2025)
EARLY = (2010, 2014)

# Floors: master's cohorts are far larger than doctoral ones, so the same
# floor would be lax at one level and crippling at the other.
FLOOR = {"masters": {"inst": 250, "prog": 400},
         "doctorate": {"inst": 60, "prog": 150}}


def award_levels(year: int, level: str) -> set[str]:
    if level == "masters":
        return {"7"}
    if year >= 2010:
        return {"17"}
    if year in (2008, 2009):
        return {"9", "17"}
    return {"9"}


def source_files() -> dict[int, str]:
    out: dict[int, str] = {}
    for path in glob.glob(str(IPEDS / "*_a*.csv")):
        m = re.search(r"c(\d{4})_a", os.path.basename(path).lower())
        if not m:
            continue
        y = int(m.group(1))
        if y not in out or "_rv" in path.lower():
            out[y] = path
    return out


def names() -> dict[str, str]:
    for cand in ("HD2024.csv", "HD2023.csv", "hd2025.csv"):
        p = IPEDS / cand
        if p.exists():
            with open(p, newline="", encoding="utf-8-sig", errors="replace") as fh:
                return {r["UNITID"]: r.get("INSTNM", r["UNITID"])
                        for r in csv.DictReader(fh)}
    return {}


def cip_titles() -> dict[str, str]:
    p = IPEDS / "cip_titles.csv"
    if not p.exists():
        return {}
    with open(p, newline="", encoding="utf-8", errors="replace") as fh:
        rd = csv.DictReader(fh)
        key = "cipcode" if "cipcode" in (rd.fieldnames or []) else (rd.fieldnames or [""])[0]
        ttl = "title" if "title" in (rd.fieldnames or []) else (rd.fieldnames or ["", ""])[1]
        return {r[key]: r[ttl] for r in rd}


def harvest(level: str, window: tuple[int, int]):
    """(by_institution, by_programme, by_institution_and_programme),
    each {key: [nra, total]} pooled over the window."""
    inst: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    prog: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    inst_prog: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(lambda: [0, 0]))
    for year, path in sorted(source_files().items()):
        if not window[0] <= year <= window[1]:
            continue
        want = award_levels(year, level)
        try:
            fh = open(path, newline="", encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        with fh:
            for row in csv.DictReader(fh):
                if (row.get("AWLEVEL") or "").lstrip("0") not in want:
                    continue
                cip = (row.get("CIPCODE") or "").strip()
                if cip.split(".")[0].zfill(2) not in STEM_CIP2:
                    continue
                if cip.endswith(".00") or "." not in cip:      # family rollup row
                    continue
                try:
                    tot = int(row.get("CTOTALT") or 0)
                    nra = int(row.get("CNRALT") or 0)
                except ValueError:
                    continue
                if tot <= 0:
                    continue
                i = inst[row["UNITID"]]
                i[0] += nra; i[1] += tot
                p = prog[cip]
                p[0] += nra; p[1] += tot
                ip = inst_prog[row["UNITID"]][cip]
                ip[0] += nra; ip[1] += tot
    return inst, prog, inst_prog


def rank(d: dict[str, list[int]], floor: int, label: dict[str, str], top: int = 25):
    rows = [{"key": k, "name": label.get(k, k), "nra": v[0], "total": v[1],
             "share": round(100 * v[0] / v[1], 1)}
            for k, v in d.items() if v[1] >= floor]
    rows.sort(key=lambda r: (-r["share"], -r["total"]))
    return rows[:top], len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    nm, ct = names(), cip_titles()
    payload = {"windows": {"late": list(LATE), "early": list(EARLY)},
               "floors": FLOOR, "cip_families": sorted(STEM_CIP2), "levels": {}}

    for level in ("masters", "doctorate"):
        inst, prog, by_inst_prog = harvest(level, LATE)
        einst, _eprog, _eip = harvest(level, EARLY)
        f = FLOOR[level]
        top_i, n_i = rank(inst, f["inst"], nm, args.top)
        #: How many qualifying institutions award MOST of their degrees at
        #: this level to non-residents. The ranking ships only its top 25, so
        #: without this the page can say who is highest and not how common it
        #: is -- and "how many institutions are majority non-resident" is the
        #: question a reader actually asks. Counted over every institution
        #: that clears the same floor as the ranking, so the two agree.
        majority = sum(1 for k, v in inst.items()
                       if v[1] >= f["inst"] and v[1] and v[0] / v[1] > 0.5)
        top_p, n_p = rank(prog, f["prog"], ct, args.top)

        risers = []
        for k, v in inst.items():
            if v[1] < f["inst"] or k not in einst or einst[k][1] < f["inst"]:
                continue
            late = 100 * v[0] / v[1]
            early = 100 * einst[k][0] / einst[k][1]
            risers.append({"key": k, "name": nm.get(k, k),
                           "early": round(early, 1), "late": round(late, 1),
                           "change": round(late - early, 1),
                           "early_n": einst[k][1], "late_n": v[1]})
        risers.sort(key=lambda r: -r["change"])

        biggest = sorted(
            [{"key": k, "name": nm.get(k, k), "nra": v[0], "total": v[1],
              "share": round(100 * v[0] / v[1], 1)} for k, v in inst.items()],
            key=lambda r: -r["nra"])[:args.top]

        # The within-institution contrast. This is the strongest form of the
        # comparison because it holds the institution fixed: same university,
        # same degree level, same admissions office, two programmes far apart.
        # It forecloses "that university is simply internationally oriented".
        cfloor = 120 if level == "masters" else 40
        contrasts = []
        for uid, progs in by_inst_prog.items():
            big = [(c, v) for c, v in progs.items() if v[1] >= cfloor]
            if len(big) < 2:
                continue
            ranked = sorted(((100 * v[0] / v[1], c, v) for c, v in big))
            low, high = ranked[0], ranked[-1]
            gap = high[0] - low[0]
            if gap < 50:
                continue
            contrasts.append({
                "key": uid, "name": nm.get(uid, uid), "gap": round(gap, 1),
                "high": {"cip": high[1], "name": ct.get(high[1], high[1]),
                         "share": round(high[0], 1), "nra": high[2][0], "total": high[2][1]},
                "low": {"cip": low[1], "name": ct.get(low[1], low[1]),
                        "share": round(low[0], 1), "nra": low[2][0], "total": low[2][1]},
            })
        contrasts.sort(key=lambda r: -r["gap"])

        payload["levels"][level] = {
            "contrasts": contrasts[:args.top],
            "contrasts_total": len(contrasts),
            "contrast_floor": cfloor,
            "institutions": top_i, "institutions_eligible": n_i,
            "institutions_majority_nra": majority,
            "programmes": top_p, "programmes_eligible": n_p,
            "risers": risers[:args.top], "biggest": biggest,
            "national": {
                "nra": sum(v[0] for v in inst.values()),
                "total": sum(v[1] for v in inst.values()),
            },
        }
        nat = payload["levels"][level]["national"]
        nat["share"] = round(100 * nat["nra"] / nat["total"], 1)

    if args.report:
        for level in ("masters", "doctorate"):
            L = payload["levels"][level]
            f = FLOOR[level]
            print(f"\n{'='*74}\n{level.upper()}  pooled {LATE[0]}-{LATE[1]}, core STEM"
                  f"   national {L['national']['share']}%"
                  f"  ({L['national']['nra']:,} of {L['national']['total']:,})")
            print(f"\n  Institutions, {f['inst']}+ degrees "
                  f"({L['institutions_eligible']} qualify)")
            for i, r in enumerate(L["institutions"][:12], 1):
                print(f"   {i:>2}. {r['share']:>5.1f}%  {r['name'][:46]:<46}"
                      f"{r['nra']:>7,} of {r['total']:>7,}")
            print(f"\n  Programmes (4-digit CIP), {f['prog']}+ degrees "
                  f"({L['programmes_eligible']} qualify)")
            for i, r in enumerate(L["programmes"][:12], 1):
                print(f"   {i:>2}. {r['share']:>5.1f}%  {r['name'][:46]:<46}"
                      f"{r['nra']:>7,} of {r['total']:>7,}")
            print(f"\n  Largest non-resident cohorts")
            for i, r in enumerate(L["biggest"][:8], 1):
                print(f"   {i:>2}. {r['nra']:>7,}  {r['name'][:46]:<46}"
                      f"{r['share']:>6.1f}% of {r['total']:,}")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_json(OUT, payload, indent=1)
    print(f"  wrote {OUT.relative_to(ROOT)}")
    for level in ("masters", "doctorate"):
        L = payload["levels"][level]
        print(f"    {level:<10} national {L['national']['share']}%  "
              f"{L['institutions_eligible']} institutions, "
              f"{L['programmes_eligible']} programmes above floor")
    return 0


if __name__ == "__main__":
    sys.exit(main())