#!/usr/bin/env python3
"""Has federal support shifted toward non-citizens, and for how long?

One year can show a gap. It cannot say whether the gap is new, widening, or
long-standing, and "federal money has gone to non-citizens for some time" is
a claim about a trend. The SED publishes the same table with every release,
so the series is assembled from seven of them rather than one.

WHAT THE RESEARCH ASSISTANTSHIP ROW STANDS FOR. The SED never records which
award paid a student. GSS does record the mechanism, and shows federal
support reaches doctoral students overwhelmingly through research
assistantships -- 52,428 federally supported RAs against 1,041 federally
supported TAs. The RA share is therefore the closest published proxy for
"principally funded by a federal grant". It remains a proxy: some
assistantships are institutionally or industrially funded, and the SED
cannot separate them.

WHY THE SERIES IS ALL FIELDS, NOT S&E. NCSES revised the SED field taxonomy
for the 2023 release -- health sciences and multidisciplinary sciences moved
into science and engineering, which had been partly "other". An S&E series
spanning that break would compare two different populations. "All doctorate
recipients reporting primary source of support" is defined the same way in
every release, so the trend runs on that. Where a release also publishes an
S&E rollup, it is carried alongside, clearly scoped to its own taxonomy era.

Usage:
  python3 scripts/build_support_trend.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SED = ROOT / "data" / "sed"
OUT = ROOT / "site" / "data" / "support_trend.json"

# Cohort year -> the release file that reports it. Older releases number this
# table 35 under a flat scheme; 2021 onward number it 4-1 within a chapter.
RELEASES = {
    2018: "nsf20301-tab035.xlsx",
    2019: "nsf21308-tab035.xlsx",
    2020: "nsf22300-tab035.xlsx",
    2021: "nsf23300-tab004-001.xlsx",
    2022: "nsf24300-tab004-001.xlsx",
    2023: "nsf24336-tab004-001.xlsx",
    2024: "nsf25349-tab004-001.xlsx",
}

# The two citizenship columns, found by header text rather than position.
CITIZEN_HDR = "u.s. citizen or permanent"
VISA_HDR = "temporary visa"

# Support categories. Older releases split employer and other into two rows;
# newer releases combine them, so the two are summed to stay comparable.
ROWS = [
    ("teaching", ("teaching assistantship",)),
    ("research", ("research assistantship",)),
    ("fellowship", ("fellowship",)),
    ("own", ("own resources",)),
    ("employer_other", ("employer", "other")),
]


def find_columns(rows: list[list]) -> tuple[int, int]:
    """Locate the citizen and visa columns from the header band."""
    for r in rows[:8]:
        cells = {str(v or "").strip().lower(): j for j, v in enumerate(r)}
        cit = next((j for lab, j in cells.items() if lab.startswith(CITIZEN_HDR)), None)
        vis = next((j for lab, j in cells.items() if lab.startswith(VISA_HDR)), None)
        if cit is not None and vis is not None:
            return cit, vis
    raise ValueError("citizenship columns not found in header")


def read_section(rows: list[list], cit: int, vis: int, start: int) -> dict:
    """Read the support block that follows a section header row."""
    hdr = rows[start]
    out = {"n_citizen": int(hdr[cit]), "n_visa": int(hdr[vis]), "sources": {}}
    for r in rows[start + 1:]:
        label = str(r[0] or "").strip().lower()
        if not label:
            continue
        # Every section header is marked "(number)"; the support rows are
        # percentages. Stopping on the header -- rather than on a row's
        # magnitude -- keeps a section from absorbing the one below it,
        # which matters because some sub-field counts are small and some
        # section names ("Other non-science and engineering") collide with
        # a support category.
        key = next((k for k, frags in ROWS
                    if any(label.startswith(f) for f in frags)), None)
        if "(number)" in label or key is None:
            break
        for col, side in ((cit, "citizen"), (vis, "visa")):
            v = r[col]
            if isinstance(v, (int, float)):
                bucket = out["sources"].setdefault(key, {})
                bucket[side] = round(bucket.get(side, 0.0) + v, 1)
    return out


def read(path: Path) -> dict:
    import openpyxl
    rows = [list(r) for r in
            openpyxl.load_workbook(path).active.iter_rows(values_only=True)]
    cit, vis = find_columns(rows)

    all_fields = None
    sande = None
    for i, r in enumerate(rows):
        label = str(r[0] or "").strip().lower()
        if not isinstance(r[cit], (int, float)) or r[cit] < 1000:
            continue
        if all_fields is None and (label.startswith("all fields")
                                   or label.startswith("all doctorate")):
            # Some releases stack two totals: every recipient, then the
            # smaller number who reported a source of support. The
            # percentages below are of the latter, so walk to the last
            # count row in the run and use that as the denominator.
            j = i
            while (j + 1 < len(rows)
                   and str(rows[j + 1][0] or "").strip().lower().startswith("all")
                   and isinstance(rows[j + 1][cit], (int, float))
                   and rows[j + 1][cit] > 1000):
                j += 1
            all_fields = read_section(rows, cit, vis, j)
            all_fields["base"] = ("reporting a source of support"
                                  if "reporting" in str(rows[j][0] or "").lower()
                                  else "all recipients (release does not "
                                       "publish a separate reporting base)")
        elif label.startswith("science and engineering"):
            sande = read_section(rows, cit, vis, i)
    if all_fields is None:
        raise ValueError(f"{path.name}: no all-fields section")
    return {"all_fields": all_fields, "science_and_engineering": sande}


def check(year: int, sec: dict) -> list[str]:
    """The five support categories should account for everyone, once each."""
    warns = []
    for side in ("citizen", "visa"):
        total = sum(v.get(side, 0.0) for v in sec["sources"].values())
        if abs(total - 100.0) > 1.5:
            warns.append(f"{year} {side}: categories sum to {total:.1f}%")
    missing = {k for k, _ in ROWS} - set(sec["sources"])
    if missing:
        warns.append(f"{year}: missing {sorted(missing)}")
    return warns


def main() -> int:
    series, warns = {}, []
    for year, fname in sorted(RELEASES.items()):
        p = SED / fname
        if not p.exists():
            warns.append(f"{year}: {fname} not downloaded")
            continue
        got = read(p)
        warns += check(year, got["all_fields"])
        if got["science_and_engineering"]:
            warns += [f"S&E {w}" for w in
                      check(year, got["science_and_engineering"])]
        series[str(year)] = got | {"release": fname.split("-")[0]}

    if len(series) < 3:
        print("  too few years for a trend")
        return 1

    years = sorted(series)
    ra = {y: series[y]["all_fields"]["sources"]["research"] for y in years}
    own = {y: series[y]["all_fields"]["sources"]["own"] for y in years}
    head = {y: {side: round(series[y]["all_fields"][f"n_{side}"]
                            * ra[y][side] / 100)
                for side in ("citizen", "visa")} for y in years}

    doc = {
        "_comment": (
            "Primary source of support for research doctorate recipients, by "
            "citizenship, across seven SED releases. Percentages are of each "
            "citizenship group, not of the total. The RESEARCH ASSISTANTSHIP "
            "row is the closest published proxy for federal funding -- GSS "
            "shows federal support reaches doctoral students overwhelmingly "
            "through RAs -- but it is a proxy: the SED does not record which "
            "award paid. The series runs on ALL FIELDS because NCSES revised "
            "the field taxonomy in the 2023 release, so an S&E series would "
            "cross a definitional break; the S&E rollup is carried only where "
            "the release publishes it."),
        "source": "NSF NCSES, Survey of Earned Doctorates, primary-source-of-support table, seven releases",
        "population": "research doctorate recipients reporting primary source of support",
        "years": [int(y) for y in years],
        "series": series,
        "research_assistantship_gap_pts": {
            y: round(ra[y]["visa"] - ra[y]["citizen"], 1) for y in years},
        "self_funding_ratio": {
            y: round(own[y]["citizen"] / own[y]["visa"], 1)
            for y in years if own[y]["visa"]},
        # Percentages describe each group internally; they cannot say how the
        # RA population divides. Rebuilding headcounts from count x percent
        # does. Releases before 2021 publish no separate reporting base, so
        # both groups are scaled off all recipients that year -- an
        # overstatement of a few percent that falls on both sides, which is
        # why this is reported as a share rather than a level.
        "visa_share_of_research_assistantships": {
            y: round(100 * head[y]["visa"] / (head[y]["visa"] + head[y]["citizen"]), 1)
            for y in years},
        "research_assistantship_headcount": head,
        "warnings": warns,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {len(years)} years: {years[0]}-{years[-1]}  (all fields)")
    print(f"  {'year':6}{'RA citizen':>12}{'RA visa':>10}{'gap':>7}"
          f"{'self-fund':>11}{'visa n':>9}")
    for y in years:
        s = series[y]["all_fields"]
        print(f"  {y:6}{ra[y]['citizen']:>11.1f}%{ra[y]['visa']:>9.1f}%"
              f"{doc['research_assistantship_gap_pts'][y]:>7.1f}"
              f"{doc['self_funding_ratio'].get(y, 0):>10.1f}x"
              f"{s['n_visa']:>9,}")
    f, l = years[0], years[-1]
    print(f"  visa RA share {ra[f]['visa']}% -> {ra[l]['visa']}% "
          f"({ra[l]['visa'] - ra[f]['visa']:+.1f} pts); "
          f"citizen {ra[f]['citizen']}% -> {ra[l]['citizen']}% "
          f"({ra[l]['citizen'] - ra[f]['citizen']:+.1f} pts)")
    print(f"  gap {doc['research_assistantship_gap_pts'][f]:.1f} -> "
          f"{doc['research_assistantship_gap_pts'][l]:.1f} pts")
    vs = doc["visa_share_of_research_assistantships"]
    print(f"  RA headcount: visa {head[f]['visa']:,} -> {head[l]['visa']:,} "
          f"({100 * (head[l]['visa'] / head[f]['visa'] - 1):+.1f}%); "
          f"citizen {head[f]['citizen']:,} -> {head[l]['citizen']:,} "
          f"({100 * (head[l]['citizen'] / head[f]['citizen'] - 1):+.1f}%)")
    print(f"  visa share of all RAs: {vs[f]}% -> {vs[l]}%")
    for w in warns:
        print(f"  WARN {w}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
