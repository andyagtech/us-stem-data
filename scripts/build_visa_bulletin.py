#!/usr/bin/env python3
"""Thirty years of the employment green-card queue, in years of waiting.

Every other leverage figure in this project describes structure: who files
the petition, from which status, for how many people. This one puts a number
on it. The State Department publishes the historical final action dates --
the priority date being acted on in each month, back to FY1992 -- for each
employment preference and each oversubscribed country.

THE WAIT IS THE GAP between the date being acted on and the month acting on
it. It is the wait ALREADY SERVED by the person now reaching the front, not a
forecast for someone filing today: where a queue is growing, a new filer's
eventual wait is longer than anything here can show.

"C" MEANS CURRENT -- no queue, processed on demand. "U" MEANS UNAVAILABLE --
a wait of unknown length, and emphatically not zero. Both are carried as a
status with a null wait so neither can be averaged in as though it were a
number.

Source files are the "Employment_Worldwide_{country}_FY23.pdf" charts in
data/state_visas/bulletin/, downloaded by hand because travel.state.gov
refuses automated requests from this project.

Usage:
  python3 scripts/build_visa_bulletin.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "state_visas" / "bulletin"
OUT = ROOT / "site" / "data" / "visa_bulletin.json"

MONTH_N = {"OCT": 10, "NOV": 11, "DEC": 12, "JAN": 1, "FEB": 2, "MAR": 3,
           "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8, "SEP": 9}
# The bulletin writes month labels as "Oct.", "June", "Sept."
MONTH_RE = re.compile(r"^(OCT|NOV|DEC|JAN|FEB|MAR|APR|MAY|JUNE?|JULY?|AUG|SEPT?)\.?$")
DATE_RE = re.compile(r"^(\d{1,2})-([A-Za-z]{3})-(\d{2})$")
# Only the first three value columns are read. Their order -- 1st, 2nd, 3rd --
# is stable across the whole file, where the later columns (Schedule A, 5th
# Pilot) appear and disappear between eras.
PREFERENCES = ("EB-1", "EB-2", "EB-3")


def country_of(name: str) -> str | None:
    m = re.match(r"Employment_Worldwide_([A-Za-z]+)_FY", name)
    if not m:
        return None
    who = m.group(1)
    return "All chargeability areas" if who == "Online" else who


def parse_date(tok: str) -> str | None:
    m = DATE_RE.match(tok)
    if not m:
        return None
    dd, mon, yy = m.groups()
    mon = mon.upper()[:3]
    if mon not in MONTH_N:
        return None
    yy = int(yy)
    year = 1900 + yy if yy >= 70 else 2000 + yy
    return f"{year:04d}-{MONTH_N[mon]:02d}-{int(dd):02d}"


def wait_years(priority: str, y: int, m: int) -> float:
    py, pm, pd = (int(x) for x in priority.split("-"))
    return round((date(y, m, 1) - date(py, pm, pd)).days / 365.25, 1)


# The monthly bulletins write dates as "01JUN23" where the historical charts
# write "1-Jun-23", and they carry TWO employment tables: final action dates
# and the later "dates for filing". Only the final action table is read, so
# the monthly rows stay on the same basis as the historical ones.
MONTHLY_DATE = re.compile(r"^(\d{2})([A-Z]{3})(\d{2})$")
MONTHLY_ROWS = {"1ST": "EB-1", "2ND": "EB-2", "3RD": "EB-3"}
FINAL_ACTION_HEADING = re.compile(
    r"A\.\s*Final Action Dates for Employment-Based", re.I)
FILING_HEADING = re.compile(r"B\.\s*Dates for Filing of Employment-Based", re.I)
BULLETIN_NAME = re.compile(r"visabulletin_([A-Za-z]+)(\d{4})", re.I)
FULL_MONTHS = {"JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5,
               "JUNE": 6, "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9,
               "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12}
# Column order in the monthly employment table.
MONTHLY_COLS = ("All chargeability areas", "China", "India")


def parse_monthly_date(tok: str) -> str | None:
    m = MONTHLY_DATE.match(tok.upper())
    if not m:
        return None
    dd, mon, yy = m.groups()
    if mon not in MONTH_N:
        return None
    yy = int(yy)
    year = 1900 + yy if yy >= 70 else 2000 + yy
    return f"{year:04d}-{MONTH_N[mon]:02d}-{int(dd):02d}"


def parse_monthly_bulletins(series: dict, warns: list) -> int:
    """Extend the series with recent monthly bulletins.

    The historical charts stop at FY2023; these carry the current year.
    """
    added = 0
    for path in sorted(SRC.glob("visabulletin_*.pdf")):
        m = BULLETIN_NAME.search(path.name)
        if not m or m.group(1).upper() not in FULL_MONTHS:
            warns.append(f"cannot date {path.name}")
            continue
        key = f"{int(m.group(2)):04d}-{FULL_MONTHS[m.group(1).upper()]:02d}"
        year, month = (int(x) for x in key.split("-"))
        r = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                           capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            warns.append(f"{path.name}: pdftotext produced nothing")
            continue
        inside = False
        got = 0
        for line in r.stdout.splitlines():
            flat = re.sub(r"\s+", " ", line).strip()
            if FINAL_ACTION_HEADING.search(flat):
                inside = True
                continue
            if FILING_HEADING.search(flat):
                break                       # the filing table must not be read
            if not inside:
                continue
            toks = flat.split()
            if not toks:
                continue
            pref = MONTHLY_ROWS.get(toks[0].upper())
            if not pref:
                continue
            vals = [t for t in toks[1:] if MONTHLY_DATE.match(t.upper())
                    or t.upper() in ("C", "U")]
            if len(vals) < 3:
                continue
            for country, tok in zip(MONTHLY_COLS, vals[:3]):
                iso = parse_monthly_date(tok)
                up = tok.upper()
                series.setdefault(country, {}).setdefault(pref, {})[key] = {
                    "priority_date": iso,
                    "status": None if iso else up,
                    "wait_years": wait_years(iso, year, month) if iso else None}
            got += 1
        if got:
            added += 1
        else:
            warns.append(f"{path.name}: no final-action employment rows matched")
    return added


def main() -> int:
    files = sorted(SRC.glob("Employment_Worldwide_*_FY*.pdf"))
    if not files:
        print(f"  no employment charts in {SRC.relative_to(ROOT)} -- see its README")
        return 1

    series: dict[str, dict] = {}
    warns: list[str] = []
    for path in files:
        country = country_of(path.name)
        if not country:
            warns.append(f"cannot identify country in {path.name}")
            continue
        r = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                           capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            warns.append(f"{path.name}: pdftotext produced nothing")
            continue

        fy = None
        rows = 0
        for line in r.stdout.splitlines():
            flat = re.sub(r"\s+", " ", line).strip()
            m = re.match(r"FY-?(\d{4})", flat)
            if m:
                fy = int(m.group(1))
                continue
            if fy is None:
                continue
            toks = flat.split()
            if not toks or not MONTH_RE.match(toks[0].upper()):
                continue
            mon = MONTH_RE.match(toks[0].upper()).group(1)[:3]
            if mon == "JUN" or mon == "JUL":
                mon = mon
            month = MONTH_N.get(mon if mon in MONTH_N else mon[:3])
            if not month:
                continue
            values = toks[1:]
            if len(values) < 3:
                continue
            # A fiscal year runs October to September: October through
            # December fall in the PRECEDING calendar year.
            cal_year = fy - 1 if month >= 10 else fy
            key = f"{cal_year:04d}-{month:02d}"
            for pref, tok in zip(PREFERENCES, values[:3]):
                iso = parse_date(tok)
                up = tok.upper()
                entry = {"priority_date": iso,
                         "status": None if iso else (up if up in ("C", "U", "-") else up),
                         "wait_years": wait_years(iso, cal_year, month) if iso else None}
                series.setdefault(country, {}).setdefault(pref, {})[key] = entry
            rows += 1
        if not rows:
            warns.append(f"{path.name}: no month rows matched")

    monthly_files = parse_monthly_bulletins(series, warns)

    if not series:
        print("  nothing parsed")
        for w in warns:
            print(f"  WARN {w}")
        return 1

    # Latest month with a real date, per country and preference.
    latest = {}
    for country, prefs in series.items():
        latest[country] = {}
        for pref, months in prefs.items():
            dated = [(k, v) for k, v in sorted(months.items())
                     if v["wait_years"] is not None]
            if dated:
                k, v = dated[-1]
                latest[country][pref] = {"month": k, **v}

    doc = {
        "_comment": (
            "Employment-based FINAL ACTION DATES from the State Department's "
            "historical charts, FY1992 onward. WAIT_YEARS is the gap between "
            "the priority date being acted on and the month acting on it: the "
            "wait ALREADY SERVED by the person now reaching the front, NOT a "
            "forecast for someone filing today -- where a queue is growing, a "
            "new filer's eventual wait is longer than this can show. 'C' is "
            "CURRENT (no queue) and 'U' is UNAVAILABLE (a wait of unknown "
            "length, NOT zero); both are carried as a status with a null wait "
            "so neither can be averaged in as a number. Only the 1st, 2nd and "
            "3rd preference columns are read, because their order is stable "
            "across every era of the chart while later columns come and go. "
            "Retrieved by hand: travel.state.gov refuses automated requests."),
        "source": "US Department of State, Visa Bulletin historical final action dates",
        "source_url": "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html",
        "countries": sorted(series),
        "monthly_bulletins_added": monthly_files,
        "latest": latest,
        "series": series,
        "warnings": warns,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {len(series)} countries: {', '.join(sorted(series))}"
          f"  (+{monthly_files} monthly bulletins)")
    for country in sorted(series):
        months = sorted(series[country]["EB-2"])
        print(f"  {country}: {len(months)} months, {months[0]} to {months[-1]}")
    print(f"\n  {'country':26}{'EB-2':>18}{'EB-3':>18}")
    for country in sorted(latest):
        cells = []
        for pref in ("EB-2", "EB-3"):
            e = latest[country].get(pref)
            cells.append(f"{e['wait_years']} yr @ {e['month']}" if e else "-")
        print(f"  {country:26}{cells[0]:>18}{cells[1]:>18}")
    # A category can retrogress to "U" after its last dated month, which the
    # line above cannot show, so the current state is printed separately.
    newest = max(m for c in series.values() for p in c.values() for m in p)
    print(f"\n  state in {newest}:")
    for country in sorted(series):
        row = []
        for pref in ("EB-2", "EB-3"):
            e = series[country][pref].get(newest)
            row.append(f"{pref} {(e['priority_date'] or e['status']) if e else '-'}")
        print(f"   {country:26}{'   '.join(row)}")
    for w in warns[:6]:
        print(f"  WARN {w}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
