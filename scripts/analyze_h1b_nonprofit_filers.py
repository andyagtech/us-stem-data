#!/usr/bin/env python3
"""Who the large cap-exempt H-1B filers are, as far as the data allows.

The USCIS Report to Congress gives national totals by exempt employer
category but never names an employer. The USCIS H-1B Employer Data Hub names
every employer but carries no cap flag. Neither answers "which organisations
are the biggest cap-exempt filers" on its own.

This gets as close as the published data permits, and no closer:

  educational services   NAICS 61 filers, the cleanest proxy for the
                         higher-education exemption. It is a proxy: it
                         includes for-profit schools and school districts,
                         which are not cap-exempt, and it misses affiliated
                         nonprofits, which file under other codes.
  named nonprofits       organisations known to run university-affiliated
                         cap-exempt sponsorship, tracked by name across
                         years. A name list is not a census -- it finds only
                         what it is told to look for.

NOTHING HERE ESTABLISHES CAP STATUS FOR ANY NAMED EMPLOYER. That field is
not published. Treat every figure as "petitions from an employer of a type
that is usually cap-exempt", never as "cap-exempt petitions".

Usage:
  python3 scripts/analyze_h1b_nonprofit_filers.py
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "data" / "h1b"
OUT = HUB / "h1b_nonprofit_filers.json"

# Organisations that publicly describe university-affiliated cap-exempt
# sponsorship. Extend deliberately; every addition changes what the totals
# mean, so the list is data, not a heuristic.
WATCHED = {
    "OPEN AVENUES FOUNDATION": "Open Avenues Foundation",
}

# The hub changed format at FY2024. Before that it is a comma-separated
# latin-1 file with 11 columns; from FY2024 it is UTF-16, tab-separated, with
# 20. Same data, different shape -- reading every year with the newer layout
# silently produced zero educational-services employers for FY2010-FY2023,
# which looks like "no universities filed" rather than "wrong columns".
LAYOUTS = {
    "modern": {"name": 2, "naics": 4, "state": 6,
               "new_appr": 8, "cont_appr": 10, "min_cols": 12},
    "legacy": {"name": 1, "naics": 6, "state": 8,
               "new_appr": 2, "cont_appr": 4, "min_cols": 9},
}


def read_year(path: Path):
    """Yield (row, layout) for a year, whichever shape the file is in."""
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text, delim, layout = raw.decode("utf-16", errors="replace"), "\t", LAYOUTS["modern"]
    else:
        text, delim, layout = raw.decode("latin-1", errors="replace"), ",", LAYOUTS["legacy"]
    r = csv.reader(io.StringIO(text), delimiter=delim)
    header = next(r, None) or []
    # Confirm the layout rather than trusting the encoding: a legacy file
    # names its second column "Employer", a modern one "Employer (Petitioner)
    # Name" in column three.
    joined = " ".join(header).lower()
    if "petitioner" in joined:
        layout = LAYOUTS["modern"]
    elif "employer" in joined and len(header) < 15:
        layout = LAYOUTS["legacy"]
    for row in r:
        if len(row) >= layout["min_cols"]:
            yield row, layout


def num(x: str) -> int:
    x = (x or "").replace(",", "").strip()
    return int(x) if x.isdigit() else 0


def main() -> int:
    files = sorted(p for p in HUB.glob("h1b_datahub_fy*.csv")
                   if re.fullmatch(r"h1b_datahub_fy\d{4}\.csv", p.name))
    if not files:
        print("  no data hub files found")
        return 1

    edu: dict[str, dict] = {}
    watched: dict[str, dict] = {}
    for path in files:
        year = re.search(r"fy(\d{4})", path.name).group(1)
        tally = defaultdict(lambda: [0, 0, None, None])
        seen_watch = defaultdict(lambda: [0, 0, None, None])
        for row, L in read_year(path):
            name = row[L["name"]].strip()
            key = name.upper()
            naics = (row[L["naics"]] or "").strip().strip('"')
            if naics.startswith("61"):
                t = tally[name]
                t[0] += num(row[L["new_appr"]])
                t[1] += num(row[L["cont_appr"]])
                t[2], t[3] = row[L["state"]], naics[:2]
            for watch_key, label in WATCHED.items():
                if watch_key in key:
                    w = seen_watch[label]
                    w[0] += num(row[L["new_appr"]])
                    w[1] += num(row[L["cont_appr"]])
                    w[2], w[3] = row[L["state"]], naics[:2]
        edu[year] = {
            "employers": len(tally),
            "approvals": sum(v[0] + v[1] for v in tally.values()),
            "top": [{"employer": n, "new": v[0], "continuation": v[1],
                     "total": v[0] + v[1], "state": v[2]}
                    for n, v in sorted(tally.items(),
                                       key=lambda kv: -(kv[1][0] + kv[1][1]))[:20]],
        }
        for label, v in seen_watch.items():
            watched.setdefault(label, {})[year] = {
                "new": v[0], "continuation": v[1], "total": v[0] + v[1],
                "state": v[2], "naics": v[3]}
        print(f"  FY{year}: {len(tally):>5,} educational-services employers, "
              f"{edu[year]['approvals']:>7,} approvals"
              + (f"   [{', '.join(f'{k} {vv[year]['total']}' for k, vv in watched.items() if year in vv)}]"
                 if any(year in vv for vv in watched.values()) else ""))

    # A year whose approvals fall far below both neighbours is flagged, not
    # dropped. FY2023 is the case: 33,333 rows against about 60,000 either
    # side. That round number looked like a truncated download, but
    # re-fetching the file from USCIS returns exactly the same 33,333 rows,
    # so it is what USCIS publishes rather than a bad copy. The cause is not
    # documented; the flag records the anomaly without asserting a reason.
    years = sorted(edu)
    for i, y in enumerate(years[1:-1], start=1):
        cur = edu[y]["approvals"]
        prev, nxt = edu[years[i-1]]["approvals"], edu[years[i+1]]["approvals"]
        if prev and nxt and cur < 0.6 * min(prev, nxt):
            edu[y]["suspect"] = (f"{cur:,} approvals against {prev:,} and "
                                 f"{nxt:,} either side; matches the file USCIS "
                                 f"publishes, cause undocumented")
            print(f"  FY{y}: SUSPECT -- {edu[y]['suspect']}")
    if edu.get(years[-1], {}).get("approvals") == 0:
        edu[years[-1]]["suspect"] = "no approvals recorded; fiscal year incomplete"
        print(f"  FY{years[-1]}: incomplete fiscal year")

    OUT.write_text(json.dumps({
        "_comment": ("Large H-1B filers among employer types that are usually "
                     "cap-exempt. NAICS 61 is a PROXY for the higher-education "
                     "exemption: it includes for-profit schools and school "
                     "districts that are not cap-exempt, and misses affiliated "
                     "nonprofits filing under other codes. No published source "
                     "records cap status for a named employer, so nothing here "
                     "should be described as a count of cap-exempt petitions."),
        "source": "USCIS H-1B Employer Data Hub",
        "measure": "petitions approved (new employment + continuation)",
        "educational_services": edu,
        "watched_nonprofits": watched,
    }, indent=1) + "\n")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
