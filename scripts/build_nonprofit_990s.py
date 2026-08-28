#!/usr/bin/env python3
"""IRS Form 990 financials for the cap-exempt sponsoring nonprofits.

The USCIS Report to Congress counts petitions from "nonprofits related to or
affiliated with an institution of higher education" but never names one. The
Employer Data Hub names employers but records no cap status. So the size and
growth of the organisations running this route was, in this project, an open
question.

Form 990 closes part of it. Any nonprofit large enough to matter files one,
and the filings carry revenue, expenses, employee counts and program
descriptions. Matching a name from the Data Hub to an EIN here turns "an
organisation appears in the H-1B data" into "an organisation with this
revenue, growing at this rate".

WHAT THIS IS NOT. A 990 says nothing about cap status, and revenue is not a
count of sponsorships. Read alongside the Data Hub approvals, not instead of
them.

Source: ProPublica Nonprofit Explorer API, which republishes IRS Form 990
data. Free, no key.

Usage:
  python3 scripts/build_nonprofit_990s.py
  python3 scripts/build_nonprofit_990s.py --search "name"   # find an EIN
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "h1b" / "nonprofit_990s.json"
API = "https://projects.propublica.org/nonprofits/api/v2"

# EINs confirmed by name search. Extend deliberately: an EIN is an assertion
# that this filer is the organisation seen in the H-1B data, and a wrong one
# attributes another charity's finances to it.
# Each entry pairs an EIN with the employer name seen in the USCIS H-1B
# Employer Data Hub. Candidates were found by scanning the hub for
# nonprofit-shaped filers -- FOUNDATION, INSTITUTE, FUND and the like,
# excluding universities and hospitals -- then confirmed by name and city
# against the IRS filer.
#
# These are nonprofits that FILE H-1B PETITIONS AT VOLUME and fall within
# the statutory cap-exempt employer types. That is not the same as a
# confirmed cap-exempt filing: no source records cap status per employer.
WATCHED = {
    "822344731": "Open Avenues Foundation",       # university-affiliated sponsorship
    "263428781": "Broad Institute",               # affiliated with MIT and Harvard
    "042263040": "Dana-Farber Cancer Institute",  # affiliated with Harvard
    "590735717": "Howard Hughes Medical Institute",   # nonprofit research
    "314379427": "Battelle Memorial Institute",       # nonprofit research
}


def get(url: str) -> dict | None:
    r = subprocess.run(["curl", "-s", "--max-time", "30", url],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def search(name: str) -> int:
    doc = get(f"{API}/search.json?q={name.replace(' ', '+')}")
    if not doc:
        print("  search failed")
        return 1
    print(f"  {doc.get('total_results', 0)} result(s)")
    for o in doc.get("organizations", [])[:10]:
        print(f"   EIN {o.get('ein')}  {(o.get('name') or '')[:48]:50} "
              f"{o.get('city')}, {o.get('state')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--search", metavar="NAME", help="find an EIN by name")
    args = ap.parse_args()
    if args.search:
        return search(args.search)

    out = {}
    for ein, label in WATCHED.items():
        # An EIN is nine digits. ProPublica returns it as an integer, so a
        # leading zero is lost -- Dana-Farber's 04-2263040 comes back as
        # "42263040", which fails a lookup anywhere else. Query without the
        # padding, store with it.
        doc = get(f"{API}/organizations/{ein.lstrip('0')}.json")
        if not doc or "organization" not in doc:
            print(f"  {label}: lookup failed")
            continue
        org = doc["organization"]
        filings = []
        for f in sorted(doc.get("filings_with_data", []),
                        key=lambda x: x.get("tax_prd_yr") or 0):
            filings.append({
                "year": f.get("tax_prd_yr"),
                "revenue": f.get("totrevenue"),
                "expenses": f.get("totfuncexpns"),
                "assets": f.get("totassetsend"),
                # W-3 employee count. Frequently 0 in the API even when the
                # filing reports staff, so absence is not evidence of none.
                "employees_w3": f.get("noemplyeesw3cnt"),
            })
        if not filings:
            print(f"  {label}: no filings with data")
            continue
        first, last = filings[0], filings[-1]
        growth = (100 * (last["revenue"] / first["revenue"] - 1)
                  if first.get("revenue") else None)
        out[ein] = {
            "name": org.get("name"), "ein": ein,
            "city": org.get("city"), "state": org.get("state"),
            "ntee_code": org.get("ntee_code"),
            "subsection": org.get("subsection_code"),
            "filings": filings,
            "revenue_growth_pct": round(growth, 1) if growth is not None else None,
        }
        print(f"  {label}: {len(filings)} filings, FY{first['year']} "
              f"${first['revenue'] or 0:,} -> FY{last['year']} ${last['revenue'] or 0:,}"
              + (f"  ({growth:+.0f}%)" if growth is not None else ""))
        time.sleep(0.4)

    if not out:
        return 1
    OUT.write_text(json.dumps({
        "_comment": ("IRS Form 990 financials for nonprofits that appear in the "
                     "H-1B Employer Data Hub and describe university-affiliated "
                     "cap-exempt sponsorship. Revenue is not a count of "
                     "sponsorships, and a 990 records no cap status; read "
                     "alongside h1b_nonprofit_filers.json. employees_w3 is often "
                     "0 in the source even where staff are reported, so treat a "
                     "zero as unreported."),
        "source": "IRS Form 990 via the ProPublica Nonprofit Explorer API",
        "organizations": out,
    }, indent=1) + "\n")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
