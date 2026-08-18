#!/usr/bin/env python3
"""
Query the non-resident-alien (NRA) share index of research doctorate
completions built by scripts/build_nra_index.py.

NRA is the IPEDS federal reporting category "Nonresident alien" (now
"U.S. Nonresident"): a reported visa/residency status.  It is not ethnicity,
race, or country of origin.

Levels:
  national      one row per year (all institutions, all fields)
  subject       one row per (CIP, year)              -- across all institutions
  institution   one row per (institution, year)      -- across all fields
  cell          one row per (institution, CIP, year) -- the finest grain

Examples:
  # subjects with the highest NRA share in 2024, cohorts of 50+
  python3 scripts/query_nra_index.py --level subject --year 2024 --min-total 50

  # the most extreme university-subject-year cells since 2015
  python3 scripts/query_nra_index.py --level cell --start 2015 --min-total 20

  # electrical engineering at every institution, pooled 2020-2025
  python3 scripts/query_nra_index.py --level cell --cip 14.10 --start 2020 --pooled

  # how many cells survive at each cohort threshold
  python3 scripts/query_nra_index.py --thresholds --level cell --start 2020

  # 25-year trend for computer science, engineering and math
  python3 scripts/query_nra_index.py --trend --cip 11 --cip 14 --cip 27 --family
"""

import argparse
import csv
import gzip
import os
import sys
from collections import defaultdict

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "ipeds")
DATA = os.path.normpath(DATA)
INDEX = os.path.join(DATA, "nra_index.csv.gz")
CIP_TITLES = os.path.join(DATA, "cip_titles.csv")
def _hd_files():
    """All HD (institutional directory) files, newest year first.

    HD2024 is the primary name source; older files are walked in descending
    year order so institutions that closed or merged (and units that only ever
    reported under a since-retired UNITID) still resolve to a real name.
    """
    out = []
    for name in os.listdir(DATA):
        low = name.lower()
        if low.startswith("hd") and low.endswith(".csv") and low[2:6].isdigit():
            out.append((int(low[2:6]), name))
    out.sort(key=lambda t: -t[0])
    names = [n for _, n in out]
    if "HD2024.csv" in names:
        names.remove("HD2024.csv")
        names.insert(0, "HD2024.csv")
    return names


HD_FILES = _hd_files()


def load_cip_titles() -> dict:
    titles = {}
    if os.path.exists(CIP_TITLES):
        with open(CIP_TITLES, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                titles[row["cipcode"]] = row["title"]
    return titles


def load_institutions(needed: set) -> dict:
    """unitid -> (name, state).  Reads HD files newest-first until resolved.

    The first column name in every IPEDS CSV carries a UTF-8 BOM, so these are
    opened with utf-8-sig and the header is normalised before lookup.
    """
    out = {}
    for fname in HD_FILES:
        path = os.path.join(DATA, fname)
        if not os.path.exists(path) or not (needed - out.keys()):
            continue
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.reader(fh)
            header = [c.strip().strip('"').upper() for c in next(reader)]
            idx = {c: n for n, c in enumerate(header)}
            iu, ins = idx.get("UNITID"), idx.get("INSTNM")
            ist = idx.get("STABBR")
            if iu is None or ins is None:
                continue
            for row in reader:
                uid = row[iu].strip().strip('"')
                if uid in needed and uid not in out:
                    out[uid] = (row[ins].strip().strip('"'),
                                row[ist].strip().strip('"') if ist is not None else "")
    return out


def load_index(args):
    """Stream the index, applying row-level filters."""
    cips = [c.strip() for c in args.cip] if args.cip else None
    units = set(args.unitid) if args.unitid else None
    rows = []
    with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
        for r in csv.reader(fh):
            if r[0] == "year":
                continue
            year = int(r[0])
            if year < args.start or year > args.end:
                continue
            if args.basis and r[3] != args.basis:
                continue
            cip = r[2]
            if cips and not any(cip.startswith(c) for c in cips):
                continue
            if units and r[1] not in units:
                continue
            rows.append((year, r[1], cip, r[3], int(r[4]), int(r[5])))
    return rows


def key_for(level, year, unitid, cip, family, pooled):
    code = cip.split(".")[0] if family else cip
    y = "all" if pooled else year
    if level == "national":
        return (y,)
    if level == "subject":
        return (y, code)
    if level == "institution":
        return (y, unitid)
    return (y, unitid, code)


def aggregate(rows, level, family, pooled):
    agg = defaultdict(lambda: [0, 0])
    for year, unitid, cip, _basis, total, nra in rows:
        k = key_for(level, year, unitid, cip, family, pooled)
        agg[k][0] += total
        agg[k][1] += nra
    return agg


def fmt_rows(agg, level, titles, insts, args):
    out = []
    for k, (total, nra) in agg.items():
        if total < args.min_total:
            continue
        share = nra / total * 100
        if share < args.min_share:
            continue
        rec = {"year": k[0], "total": total, "nra": nra, "nra_share": round(share, 1)}
        if level == "subject":
            rec["cip"] = k[1]
            rec["subject"] = titles.get(k[1], "(title not in CIP2020 list)")
        elif level == "institution":
            rec["unitid"] = k[1]
            name, st = insts.get(k[1], ("(unknown institution)", ""))
            rec["institution"], rec["state"] = name, st
        elif level == "cell":
            rec["unitid"] = k[1]
            name, st = insts.get(k[1], ("(unknown institution)", ""))
            rec["institution"], rec["state"] = name, st
            rec["cip"] = k[2]
            rec["subject"] = titles.get(k[2], "(title not in CIP2020 list)")
        out.append(rec)
    keys = {"share": lambda r: (-r["nra_share"], -r["total"]),
            "total": lambda r: -r["total"],
            "nra": lambda r: -r["nra"],
            "year": lambda r: (r["year"], -r["nra_share"])}
    out.sort(key=keys[args.sort])
    return out


def print_table(recs, level, args):
    if not recs:
        print("no rows matched")
        return
    cols = ["year"]
    if level in ("institution", "cell"):
        cols += ["institution", "state"]
    if level in ("subject", "cell"):
        cols += ["cip", "subject"]
    cols += ["total", "nra", "nra_share"]
    recs = recs[: args.top]
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in recs)) for c in cols}
    widths["subject"] = min(widths.get("subject", 0), 46)
    widths["institution"] = min(widths.get("institution", 0), 42)
    print("  ".join(c.upper().ljust(widths[c]) for c in cols))
    print("  ".join("-" * widths[c] for c in cols))
    for r in recs:
        cells = []
        for c in cols:
            v = str(r.get(c, ""))[: widths[c]]
            cells.append(v.rjust(widths[c]) if c in ("total", "nra", "nra_share", "year")
                         else v.ljust(widths[c]))
        print("  ".join(cells))


def print_csv(recs, level, args):
    if not recs:
        return
    cols = list(recs[0].keys())
    w = csv.DictWriter(sys.stdout, fieldnames=cols)
    w.writeheader()
    for r in recs[: args.top]:
        w.writerow(r)


def print_thresholds(rows, level, args, titles, insts):
    """Show how many cells survive at a range of minimum cohort sizes."""
    agg = aggregate(rows, level, args.family, args.pooled)
    print(f"level={level}  years={args.start}-{args.end}"
          f"{'  (pooled)' if args.pooled else ''}")
    print(f"{'min cohort':>10} {'cells':>8} {'cells >=50% NRA':>16} "
          f"{'>=75%':>8} {'>=90%':>8} {'100%':>8}")
    for thr in args.threshold_list:
        kept = [(t, n) for t, n in agg.values() if t >= thr]
        if not kept:
            print(f"{thr:>10} {0:>8}")
            continue
        s = [n / t for t, n in kept]
        print(f"{thr:>10} {len(kept):>8} {sum(1 for x in s if x >= .5):>16} "
              f"{sum(1 for x in s if x >= .75):>8} {sum(1 for x in s if x >= .90):>8} "
              f"{sum(1 for x in s if x >= 1.0):>8}")


def print_trend(rows, args, titles):
    """Year-by-year NRA share for each requested CIP (or overall)."""
    groups = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for year, _u, cip, _b, total, nra in rows:
        code = cip.split(".")[0] if args.family else cip
        g = groups[code][year]
        g[0] += total
        g[1] += nra
    years = sorted({y for g in groups.values() for y in g})
    label_w = 34
    print("CIP  " + "SUBJECT".ljust(label_w) + "  " +
          "  ".join(f"{str(y)[2:]:>4}" for y in years))
    for code in sorted(groups):
        title = titles.get(code, "")[:label_w]
        cells = []
        for y in years:
            t, n = groups[code].get(y, [0, 0])
            cells.append(f"{n/t*100:4.0f}" if t >= args.min_total else "   .")
        print(f"{code:<4} {title.ljust(label_w)}  " + "  ".join(cells))
    print(f"\n(values are NRA % of research doctorate completions; "
          f"'.' = fewer than {args.min_total} completions that year)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", choices=["national", "subject", "institution", "cell"],
                    default="cell")
    ap.add_argument("--start", type=int, default=1995)
    ap.add_argument("--end", type=int, default=2100)
    ap.add_argument("--year", type=int, help="shorthand for --start Y --end Y")
    ap.add_argument("--cip", action="append",
                    help="CIP code prefix, repeatable (e.g. 14, 14.10, 11.0101)")
    ap.add_argument("--unitid", action="append", help="IPEDS UNITID, repeatable")
    ap.add_argument("--inst", help="substring match on institution name")
    ap.add_argument("--state", help="two-letter state filter")
    ap.add_argument("--family", action="store_true",
                    help="roll CIP codes up to the 2-digit family")
    ap.add_argument("--pooled", action="store_true",
                    help="pool all years in range into one row per group")
    ap.add_argument("--basis", choices=["aw09", "aw17"],
                    help="restrict to one AWLEVEL basis (see nra_index_meta.json)")
    ap.add_argument("--min-total", type=int, default=20,
                    help="minimum completions in the cell (default 20). Small "
                         "cohorts produce meaningless 100%% shares; this is the "
                         "guard, and it is deliberately a parameter.")
    ap.add_argument("--min-share", type=float, default=0.0,
                    help="minimum NRA share, in percent")
    ap.add_argument("--sort", choices=["share", "total", "nra", "year"], default="share")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--csv", action="store_true", help="emit CSV instead of a table")
    ap.add_argument("--trend", action="store_true", help="year-by-year series per CIP")
    ap.add_argument("--thresholds", action="store_true",
                    help="report surviving cell counts at several cohort thresholds")
    ap.add_argument("--threshold-list", type=int, nargs="+",
                    default=[1, 5, 10, 20, 30, 50, 100])
    args = ap.parse_args()

    if args.year:
        args.start = args.end = args.year
    if not os.path.exists(INDEX):
        sys.exit(f"index not found: {INDEX}\nrun: python3 scripts/build_nra_index.py")

    titles = load_cip_titles()
    rows = load_index(args)

    # Institution-name / state filters need the directory file.
    need_names = args.level in ("institution", "cell") or args.inst or args.state
    insts = load_institutions({r[1] for r in rows}) if need_names else {}
    if args.inst or args.state:
        sub = args.inst.lower() if args.inst else None
        st = args.state.upper() if args.state else None
        keep = {u for u, (n, s) in insts.items()
                if (sub is None or sub in n.lower()) and (st is None or s == st)}
        rows = [r for r in rows if r[1] in keep]

    if args.trend:
        print_trend(rows, args, titles)
        return
    if args.thresholds:
        print_thresholds(rows, args.level, args, titles, insts)
        return

    agg = aggregate(rows, args.level, args.family, args.pooled)
    recs = fmt_rows(agg, args.level, titles, insts, args)
    if args.csv:
        print_csv(recs, args.level, args)
    else:
        print_table(recs, args.level, args)
        print(f"\n{len(recs):,} groups at min cohort {args.min_total} "
              f"(showing {min(len(recs), args.top)}); "
              f"years {args.start}-{min(args.end, 2025)}")


if __name__ == "__main__":
    main()
