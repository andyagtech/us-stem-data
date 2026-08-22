#!/usr/bin/env python3
"""Chain SED releases into one annual doctorates-by-citizenship series.

WHY THIS IS NOT JUST READING ONE TABLE
    No single SED release carries a long annual citizenship series:

        table 1-1 / table 1   annual totals from 1958, NO citizenship
        table 1-6 / table 17  citizenship, but only five-year intervals
        table 1-7 / table 18  citizenship annually, rolling ~10-year window

    The rolling window is the whole difficulty. The 2024 release covers
    2014-24; the 2018 release covers 2009-18. Chaining them gives an annual
    series longer than any one release publishes.

REVISIONS
    Releases disagree slightly on years they share -- SED 2018 reports 53,989
    doctorates for 2014 and SED 2024 reports 53,986, because NCSES revises.
    The newest release wins for any year, and every disagreement is recorded
    in the output rather than quietly averaged or dropped.

OUTPUT
    data/nsf_sed/parsed/sed_citizenship_annual.json
        annual      year -> {all, us, temp, temp_share}, newest release wins
        five_year   the 1979-> series from table 1-6, for the long view
        revisions   years where releases disagreed, with both values
        provenance  which release each annual year came from
"""
from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
RELEASES = ROOT / "data" / "nsf_sed" / "releases"
OUT = ROOT / "data" / "nsf_sed" / "parsed" / "sed_citizenship_annual.json"

# Release -> the data year it reports. Newest last; later entries win.
ORDER = [("nsf20301", 2018), ("nsf21308", 2019), ("nsf22300", 2020),
         ("nsf23300", 2021), ("nsf24300", 2022), ("nsf24336", 2023),
         ("nsf25349", 2024)]

US = "U.S. citizen or permanent resident"
TEMP = "Temporary visa holder"


def load(path: Path):
    import openpyxl
    wb = openpyxl.load_workbook(str(path), read_only=True)
    rows = [[c for c in r] for r in wb.active.iter_rows(values_only=True)]
    wb.close()
    return rows


def title_of(rows) -> str:
    return " ".join(str(r[0]) for r in rows[:3] if r and r[0])


def find_table(pubid: str, want_annual: bool) -> Path | None:
    """Locate a release's citizenship table by TITLE, not by number.

    Table numbering is not stable across releases: what is table 18 in the
    2018 release is table 1-7 in the 2024 one.
    """
    best = None
    for f in sorted((RELEASES / pubid).glob("*.xlsx")):
        try:
            rows = load(f)
        except Exception:                                     # noqa: BLE001
            continue
        t = title_of(rows).lower()
        if "citizenship status" not in t:
            continue
        if want_annual and "major field" in t and "selected years" not in t:
            return f
        if not want_annual and "broad field" in t and "selected years" in t:
            best = f
    return best


def year_cols(rows) -> tuple[int, dict[int, int]]:
    """Row index of the header, and a map of year -> column index."""
    for i, r in enumerate(rows[:8]):
        cols = {}
        for j, c in enumerate(r or []):
            m = re.fullmatch(r"(19|20)\d{2}", str(c).strip().replace(".0", ""))
            if m:
                cols[int(m.group(0))] = j
        if len(cols) >= 3:
            return i, cols
    return -1, {}


def num(v):
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def section_row(rows, label: str, cols: dict[int, int]) -> dict[int, int]:
    for r in rows:
        if r and str(r[0]).strip() == label:
            return {y: num(r[j]) for y, j in cols.items() if num(r[j]) is not None}
    return {}


def main() -> int:
    annual: dict[int, dict] = {}
    provenance: dict[int, str] = {}
    revisions: list[dict] = []

    for pubid, dyear in ORDER:
        d = RELEASES / pubid
        if not d.exists():
            print(f"  {pubid}: not downloaded, skipping")
            continue
        f = find_table(pubid, want_annual=True)
        if not f:
            print(f"  {pubid}: no annual citizenship table found")
            continue
        rows = load(f)
        hi, cols = year_cols(rows)
        if not cols:
            print(f"  {pubid}: could not read a year header")
            continue
        alls = {y: num(rows[hi + 1][j]) for y, j in cols.items()
                if num(rows[hi + 1][j]) is not None}
        us, temp = section_row(rows, US, cols), section_row(rows, TEMP, cols)
        print(f"  {pubid} (SED {dyear}): {f.name}  years "
              f"{min(cols)}-{max(cols)}")
        for y in sorted(cols):
            if y not in alls or y not in temp:
                continue
            rec = {"all": alls[y], "us": us.get(y), "temp": temp[y]}
            if y in annual and annual[y]["all"] != rec["all"]:
                revisions.append({"year": y, "was": annual[y]["all"],
                                  "now": rec["all"], "superseded_by": pubid,
                                  "previous_release": provenance[y]})
            annual[y] = rec
            provenance[y] = pubid

    for y, rec in annual.items():
        rec["temp_share"] = round(100 * rec["temp"] / rec["all"], 2) if rec["all"] else None

    # The five-year long view, from the newest release that has it.
    five: dict[int, dict] = {}
    for pubid, _ in reversed(ORDER):
        if not (RELEASES / pubid).exists():
            continue
        f = find_table(pubid, want_annual=False)
        if not f:
            continue
        rows = load(f)
        hi, cols = year_cols(rows)
        if not cols:
            continue
        alls = {y: num(rows[hi + 1][j]) for y, j in cols.items()}
        us, temp = section_row(rows, US, cols), section_row(rows, TEMP, cols)
        for y in sorted(cols):
            if alls.get(y) and temp.get(y):
                five[y] = {"all": alls[y], "us": us.get(y), "temp": temp[y],
                           "temp_share": round(100 * temp[y] / alls[y], 2)}
        print(f"  five-year series from {pubid}: {min(five)}-{max(five)}")
        break

    payload = {
        "_meta": {
            "source": "NSF NCSES Survey of Earned Doctorates, data tables",
            "what": ("A census of research doctorates awarded by US "
                     "institutions, reported by citizenship status."),
            "annual_span": f"{min(annual)}-{max(annual)}" if annual else None,
            "five_year_span": f"{min(five)}-{max(five)}" if five else None,
            "method": ("No single release carries a long annual citizenship "
                       "series; each publishes a rolling ~10-year window. "
                       "These are chained, newest release winning any shared "
                       "year, with disagreements recorded under `revisions`."),
            "releases_used": [p for p, _ in ORDER if (RELEASES / p).exists()],
        },
        "annual": {str(y): annual[y] for y in sorted(annual)},
        "five_year": {str(y): five[y] for y in sorted(five)},
        "revisions": revisions,
        "provenance": {str(y): provenance[y] for y in sorted(provenance)},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.partial")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(OUT)
    print(f"\n  annual {payload['_meta']['annual_span']}, "
          f"five-year {payload['_meta']['five_year_span']}, "
          f"{len(revisions)} revision(s) recorded")
    print(f"  wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
