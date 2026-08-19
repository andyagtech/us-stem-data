#!/usr/bin/env python3
"""Labor-market outcomes for US doctorate holders, by field, from the SDR.

Answers: is there employment/unemployment data by field we can set against
the NRA shares this project computes from IPEDS?

Yes at the national level, no at the state level. The NSF Survey of Doctorate
Recipients public-use file (data/nsf_workforce/psd23Public/epsd23.csv, 80,143
respondents, 2023) carries labor force status, field of doctorate, citizenship
and survey weights. It carries NO state: geography is suppressed in the public
file for confidentiality, so state-level questions need a different source.

THREE THINGS THIS SCRIPT IS CAREFUL ABOUT:

1. Weights. WTSURVY must be applied for population estimates. Unweighted
   percentages describe the sample, not the workforce.

2. Unemployment barely varies. Doctorate unemployment sits near 1.3% in every
   field. The unweighted unemployed counts per field-by-citizenship cell run
   from 5 to 191, so that cross does not support strong claims -- the apparent
   social-sciences citizenship gap rests on 39 people. Job-relatedness
   (OCEDRLP: is the principal job related to the doctorate?) discriminates far
   better: it ranges 2.6% to 13.1% "not related" across minor field groups,
   on much healthier cell sizes.

3. Field labels are NOT verified. The shipped Fpsd23.sas contains only FORMAT
   assignments, not the PROC FORMAT VALUE definitions, so the code-to-label
   mapping is absent from the download. The nesting (major 1 -> minors 11,12;
   major 2 -> 21,22,23; ...) matches the standard NCSES SESTAT taxonomy
   exactly, and the labels below follow it, but they are UNVERIFIED against
   NCSES documentation. Treat them as provisional and confirm from the
   codebook before publishing any of this.

Usage:
    python3 scripts/analyze_sdr_outcomes.py            # field-level summary
    python3 scripts/analyze_sdr_outcomes.py --minor    # 23 minor groups
    python3 scripts/analyze_sdr_outcomes.py --nra      # set against IPEDS NRA
"""
from __future__ import annotations

import argparse
import csv
import gzip
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDR = ROOT / "data" / "nsf_workforce" / "psd23Public" / "epsd23.csv"
NRA_INDEX = ROOT / "data" / "ipeds" / "nra_index.csv.gz"

# PROVISIONAL -- see note 3 in the docstring.
MAJOR = {"1": "Computer & math sciences",
         "2": "Bio/agricultural/env life sciences",
         "3": "Physical sciences",
         "4": "Social sciences",
         "5": "Engineering",
         "6": "S&E-related fields",
         "7": "Non-S&E fields"}

# CIP 2-digit families mapped onto SDR major groups, so an NRA share can be put
# beside an outcome. Coarse by construction: the two taxonomies do not nest.
CIP_TO_MAJOR = {"11": "1", "27": "1",
                "26": "2", "01": "2", "03": "2",
                "40": "3",
                "45": "4", "42": "4",
                "14": "5",
                "51": "6", "15": "6"}

MIN_UNWEIGHTED = 30      # below this a cell is reported but flagged unreliable


def load_sdr(group_var: str):
    """Return {group: dict of weighted totals and unweighted counts}."""
    acc = defaultdict(lambda: {"emp": 0.0, "unemp": 0.0, "nilf": 0.0,
                               "rel_base": 0.0, "notrel": 0.0,
                               "n_unemp": 0, "n_notrel": 0, "n": 0})
    if not SDR.exists():
        sys.exit(f"SDR public-use file not found: {SDR}")
    with open(SDR, newline="", encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            g = row.get(group_var, "")
            if not g:
                continue
            try:
                w = float(row.get("WTSURVY") or 0)
            except ValueError:
                continue
            if w <= 0:
                continue
            a = acc[g]
            a["n"] += 1
            status = row.get("LFSTAT")
            if status == "1":
                a["emp"] += w
            elif status == "2":
                a["unemp"] += w
                a["n_unemp"] += 1
            elif status == "3":
                a["nilf"] += w
            # OCEDRLP is asked only of people working that week.
            rel = row.get("OCEDRLP")
            if rel in ("1", "2", "3"):
                a["rel_base"] += w
                if rel == "3":
                    a["notrel"] += w
                    a["n_notrel"] += 1
    return acc


def rates(a: dict):
    lf = a["emp"] + a["unemp"]
    unemp = 100 * a["unemp"] / lf if lf else None
    notrel = 100 * a["notrel"] / a["rel_base"] if a["rel_base"] else None
    return lf, unemp, notrel


def nra_by_major() -> dict[str, tuple[int, int]]:
    """{major group: (doctorates, nra)} on the project's pinned basis."""
    tot = defaultdict(int)
    nra = defaultdict(int)
    with gzip.open(NRA_INDEX, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            year = int(row["year"])
            if not (2015 <= year <= 2022) or row["basis"] != "aw17":
                continue
            g = CIP_TO_MAJOR.get(row["cipcode"].split(".")[0].zfill(2))
            if not g:
                continue
            tot[g] += int(row["total"])
            nra[g] += int(row["nra"])
    return {g: (tot[g], nra[g]) for g in tot}


def pearson(pairs):
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    sxx = sum((p[0] - mx) ** 2 for p in pairs) ** 0.5
    syy = sum((p[1] - my) ** 2 for p in pairs) ** 0.5
    return sxy / (sxx * syy) if sxx and syy else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minor", action="store_true",
                    help="23 minor field groups instead of 7 major ones")
    ap.add_argument("--nra", action="store_true",
                    help="put the IPEDS NRA share beside each outcome")
    args = ap.parse_args()

    var = "NDGMENGP" if args.minor else "NDGMEMG"
    acc = load_sdr(var)
    label = (lambda g: g) if args.minor else (lambda g: MAJOR.get(g, g))

    print("SDR 2023 public-use file, survey-weighted (WTSURVY).")
    print("Field labels are PROVISIONAL - the shipped SAS file carries no "
          "value definitions.\n")

    nra = nra_by_major() if (args.nra and not args.minor) else {}
    head = f"{'field':<36}{'labor force':>13}{'unemp':>8}{'n':>6}{'not-rel':>9}{'n':>7}"
    if nra:
        head += f"{'NRA share':>11}"
    print(head)
    print("-" * len(head))

    pairs = []
    for g in sorted(acc):
        a = acc[g]
        lf, unemp, notrel = rates(a)
        if lf < 1:
            continue
        line = (f"{label(g)[:35]:<36}{lf:>13,.0f}"
                f"{unemp:>7.2f}%{a['n_unemp']:>6}"
                f"{notrel if notrel is not None else 0:>8.1f}%{a['n_notrel']:>7}")
        if nra and g in nra:
            t, n = nra[g]
            share = 100 * n / t if t else 0
            line += f"{share:>10.1f}%"
            if notrel is not None:
                pairs.append((share, notrel, g))
        flags = []
        if a["n_unemp"] < MIN_UNWEIGHTED:
            flags.append("unemp n<30")
        if a["n_notrel"] < MIN_UNWEIGHTED:
            flags.append("not-rel n<30")
        if flags:
            line += "  <- " + ", ".join(flags)
        print(line)

    if pairs:
        r = pearson([(p[0], p[1]) for p in pairs])
        print(f"\nPearson r, NRA share vs not-related-to-degree, "
              f"{len(pairs)} field groups: {r:+.3f}"
              if r is not None else "\nToo few groups to correlate.")
        print("Descriptive only. Six or seven points cannot support inference, "
              "and the\ntwo taxonomies map coarsely onto each other.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
