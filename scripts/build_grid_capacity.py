#!/usr/bin/env python3
"""How many Americans the country trains to run its energy infrastructure.

A DIFFERENT QUESTION FROM THE REST OF THIS SITE. Everywhere else here asks who
gets the degree: what share of a field goes to people on temporary visas. Ask
that about the grid and the answer is nothing -- electrician completions are
0.2% non-resident, lineworker 0.0%. These jobs are already done by Americans.

So the question that matters is not WHO. It is HOW MANY. The United States
awards fewer than a hundred power plant technology credentials a year, at every
level combined, while planning the largest grid build-out in decades. That is a
capacity number, and nothing else on this site measures capacity.

WHAT THIS COUNTS. IPEDS Completions, every award level from a short certificate
to a doctorate, for the programmes that staff generation, transmission and the
buildings that hang off them. Counts, not shares. The non-resident share is
carried too, because its smallness is the finding that justifies the page.

THE LIMIT THAT MATTERS MOST, and it belongs on the page and not only here:
IPEDS covers institutions that take Title IV federal aid. A great deal of
electrical and line work is learned in union or employer apprenticeships --
IBEW and NECA programmes among them -- that award no IPEDS credential and
appear nowhere in this file. For the trades these counts are a FLOOR on the
pipeline, not the pipeline. The engineering and power-plant numbers do not have
that problem, because those credentials are awarded by colleges.

Usage:
    python3 scripts/build_grid_capacity.py
"""
from __future__ import annotations

import csv
import io
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IPEDS = ROOT / "data" / "ipeds"
OUT = ROOT / "site" / "data" / "grid_capacity.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

#: IPEDS award levels. 20 and 21 are rollup rows that repeat the detail rows,
#: so counting them double-counts every award; 99 is a total row.
LEVELS = {"1": "Certificate, under 1 year", "2": "Certificate, 1-2 years",
          "3": "Associate", "4": "Certificate, 2-4 years", "5": "Bachelor's",
          "7": "Master's", "17": "Doctorate", "18": "Professional practice",
          "19": "Other doctorate"}
ROLLUPS = {"20", "21", "99"}

#: The programmes that actually staff the grid and the plants, grouped by the
#: part of the system they work on. Codes, not keywords, so the list can be
#: argued with precisely.
GROUPS = [
    ("Generation", {
        "15.1702": "Power Plant Technology",
        "41.0205": "Nuclear/Nuclear Power Technology",
        "14.2301": "Nuclear Engineering",
        "15.0503": "Energy Systems Technology",
    }),
    ("Transmission and distribution", {
        "46.0303": "Lineworker",
        "46.0399": "Electrical and Power Transmission Installers, Other",
        "46.0301": "Electrical and Power Transmission Installation, General",
    }),
    ("Electrical trade and technicians", {
        "46.0302": "Electrician",
        "15.0303": "Electrical and Electronics Engineering Technology",
        "47.0105": "Industrial Electronics Technology",
    }),
    ("Engineering that designs it", {
        "14.1001": "Electrical and Electronics Engineering",
        "14.2401": "Ocean Engineering",
    }),
    ("The buildings that hang off it", {
        "15.0501": "HVAC and Refrigeration Engineering Technology",
        "47.0201": "HVAC and Refrigeration Maintenance Technology",
    }),
]
WANTED = {c: (g, t) for g, codes in GROUPS for c, t in codes.items()}


def year_files() -> list[tuple[int, Path]]:
    """One file per survey year, preferring the revised (_rv) release."""
    best: dict[int, Path] = {}
    for p in sorted(IPEDS.iterdir()):
        m = re.match(r"^[cC](\d{4})_[aA](_rv|_RV)?\.(csv|zip)$", p.name)
        if not m:
            continue
        year = int(m.group(1))
        # The 1990s releases are named for a span -- c9596_a.csv is 1995-96 --
        # and reading that as the year 9596 made it the newest file on disk,
        # which quietly emptied every count. Modern four-digit years only.
        if not 1990 <= year <= 2100:
            continue
        # A revised file supersedes the provisional one for the same year.
        if year in best and not m.group(2):
            continue
        best[year] = p
    return sorted(best.items())


def rows(path: Path):
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(name) as fh:
                yield from csv.DictReader(io.TextIOWrapper(fh, "utf-8-sig", errors="replace"))
        return
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        yield from csv.DictReader(fh)


def main() -> int:
    files = year_files()
    if not files:
        print(f"  no IPEDS completions files in {IPEDS.relative_to(ROOT)}")
        return 1

    per_year = defaultdict(lambda: defaultdict(lambda: [0, 0]))      # year -> cip
    per_level = defaultdict(lambda: defaultdict(lambda: [0, 0]))     # cip -> level
    institutions = defaultdict(set)
    latest = max(y for y, _ in files)

    for year, path in files:
        for row in rows(path):
            code = (row.get("CIPCODE") or row.get("cipcode") or "").strip()
            if code not in WANTED:
                continue
            # First-major rows only; a second-major row repeats a student
            # already counted under their first.
            if (row.get("MAJORNUM") or row.get("majornum") or "1").strip() != "1":
                continue
            lvl = (row.get("AWLEVEL") or row.get("awlevel") or "").strip()
            if lvl in ROLLUPS:
                continue
            def num(*keys):
                for k in keys:
                    v = row.get(k) or row.get(k.lower())
                    if v not in (None, "", "."):
                        try:
                            return int(float(v))
                        except ValueError:
                            return 0
                return 0
            total = num("CTOTALT")
            nra = num("CNRALT")
            per_year[year][code][0] += total
            per_year[year][code][1] += nra
            if year == latest:
                per_level[code][lvl][0] += total
                per_level[code][lvl][1] += nra
                uid = (row.get("UNITID") or row.get("unitid") or "").strip()
                if uid and total:
                    institutions[code].add(uid)

    def pct(n, t):
        return round(100 * n / t, 1) if t else None

    years = sorted(per_year)
    groups = []
    for gname, codes in GROUPS:
        progs = []
        for code, title in codes.items():
            series = {str(y): per_year[y][code][0] for y in years if per_year[y][code][0]}
            if not series:
                continue
            t, n = per_year[latest][code]
            progs.append({
                "cip": code, "title": title,
                "latest_awards": t, "latest_nra": n,
                "nra_share": pct(n, t),
                "institutions": len(institutions[code]),
                "levels": [{"level": LEVELS.get(l, l), "awards": v[0],
                            "nra_share": pct(v[1], v[0])}
                           for l, v in sorted(per_level[code].items(),
                                              key=lambda kv: -kv[1][0]) if v[0]],
                "series": series,
                # Ten years is long enough to show a trend and short enough
                # that a programme renamed in the 1990s does not distort it.
                "change_10y": None,
            })
            # A programme with no awards in the latest year is absent from
            # the series, not zero in it, so both ends must be checked.
            then, now = str(latest - 10), str(latest)
            if series.get(then) and now in series:
                progs[-1]["change_10y"] = round(
                    100 * (series[now] - series[then]) / series[then], 1)
        progs.sort(key=lambda p: -p["latest_awards"])
        tot = sum(p["latest_awards"] for p in progs)
        nra = sum(p["latest_nra"] for p in progs)
        groups.append({"group": gname, "latest_awards": tot, "latest_nra": nra,
                       "nra_share": pct(nra, tot), "programmes": progs})

    all_t = sum(g["latest_awards"] for g in groups)
    all_n = sum(g["latest_nra"] for g in groups)
    # Scarce means few, not none: a programme awarding nothing in the latest
    # year has ended, which is a different fact and does not belong in a list
    # of the smallest surviving pipelines.
    scarcest = sorted(
        (p for g in groups for p in g["programmes"] if p["latest_awards"] > 0),
        key=lambda p: p["latest_awards"])[:6]

    out = {
        "_comment": __doc__.split("Usage:")[0].strip(),
        "source": f"NCES IPEDS Completions, all award levels, {years[0]}-{latest}",
        "source_url": "https://nces.ed.gov/ipeds/use-the-data",
        "latest_year": latest,
        "years": years,
        "totals": {"awards": all_t, "nra": all_n, "nra_share": pct(all_n, all_t)},
        "definitions": {
            "counts_not_shares":
                "This page counts people. Every other industry page on this "
                "site measures the non-resident share of a field; here that "
                "share is near zero, so the number that matters is how many "
                "the country trains at all.",
            "award_levels":
                "Every level from a certificate under a year to a doctorate. "
                "IPEDS rollup rows (20, 21, 99) are excluded because they "
                "repeat the detail rows.",
            "first_major_only":
                "First-major rows only. A second-major row repeats a student "
                "already counted.",
        },
        "groups": groups,
        "scarcest": [{"title": p["title"], "cip": p["cip"],
                      "latest_awards": p["latest_awards"],
                      "institutions": p["institutions"]} for p in scarcest],
        "caveats": [
            "IPEDS covers institutions that take Title IV federal aid. Much "
            "electrical and line work is learned in union or employer "
            "apprenticeships that award no IPEDS credential, so for the trades "
            "these counts are a floor on the pipeline rather than the pipeline.",
            "A credential awarded is not a worker hired, and not a worker who "
            "stayed in the field.",
            "Programmes are matched by CIP code. A college that teaches line "
            "work inside a broader electrical programme is counted under that "
            "broader code.",
            "'Non-resident alien' is the IPEDS category: a student on a "
            "temporary visa. Permanent residents count as domestic.",
        ],
    }
    write_json(OUT, out, indent=1)
    print(f"  wrote {OUT.relative_to(ROOT)}: {len(years)} years to {latest}, "
          f"{all_t:,} awards in the latest year, {out['totals']['nra_share']}% non-resident")
    for g in groups:
        print(f"    {g['group']:<34}{g['latest_awards']:>8,} awards  "
              f"{g['nra_share']}% non-resident")
    print("    scarcest programmes:")
    for p in scarcest[:4]:
        print(f"      {p['title']:<44}{p['latest_awards']:>6,} awards "
              f"at {p['institutions']} institutions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
