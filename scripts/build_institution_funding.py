#!/usr/bin/env python3
"""State appropriations per institution, from the IPEDS finance survey.

WHY THIS IS SEPARATE FROM THE SHEEO FIGURES

SHEEO publishes what each STATE appropriates. It does not publish what each
INSTITUTION receives, and the state pages need the second to put a campus's
non-resident share beside the public money going into it. IPEDS does collect
it, as F1B11 on the GASB form.

PUBLIC INSTITUTIONS ONLY, AND THAT IS NOT A GAP TO PATCH

The GASB form is filed by public institutions. Private institutions file the
FASB form, which has no equivalent line: a private university does not receive
a state appropriation in this sense, and the state money it does get arrives as
grants and contracts recorded elsewhere. So an institution absent from this
file is almost always private, and a page showing a dash there is correct.
Writing a zero would assert something the data does not say.

Output: site/data/institution_funding.json

Usage:
    python3 scripts/build_institution_funding.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIN = ROOT / "data" / "ipeds_finance"
OUT = ROOT / "site" / "data" / "institution_funding.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

#: F1B11 is state appropriations and F1B10 federal appropriations, both on the
#: GASB form. The names are read from the header rather than assumed by
#: position: IPEDS reorders these files between years, and a column read by
#: index would silently return somebody else's revenue line.
WANTED = {"state_appropriations": "F1B11",
          "federal_appropriations": "F1B10"}


def latest_gasb() -> tuple[Path, str]:
    """The newest f{yy}{yy}_f1a.csv, with the fiscal year it covers."""
    files = sorted(FIN.glob("f[0-9][0-9][0-9][0-9]_f1a.csv"))
    if not files:
        raise SystemExit(f"FAIL: no GASB finance file in {FIN}. Nothing written.")
    newest = files[-1]
    m = re.match(r"f(\d{2})(\d{2})_f1a", newest.stem)
    year = f"20{m.group(2)}" if m else ""
    return newest, year


def main() -> int:
    path, year = latest_gasb()
    rows = list(csv.DictReader(path.open(encoding="latin-1")))
    missing = [c for c in WANTED.values() if c not in (rows[0] if rows else {})]
    if missing:
        raise SystemExit(f"FAIL: {path.name} has no column(s) "
                         f"{', '.join(missing)}. IPEDS renamed them, or this "
                         f"is the wrong form. Nothing written.")

    out: dict[str, dict] = {}
    for r in rows:
        unitid = (r.get("UNITID") or "").strip()
        if not unitid:
            continue
        rec = {}
        for name, col in WANTED.items():
            raw = (r.get(col) or "").strip()
            if raw in ("", "."):
                continue
            try:
                rec[name] = int(float(raw))
            except ValueError:
                continue
        if rec:
            out[unitid] = rec

    with_state = sum(1 for v in out.values() if v.get("state_appropriations"))
    total = sum(v.get("state_appropriations", 0) for v in out.values())
    write_json(OUT, {
        "source": f"IPEDS Finance, GASB form (F1A), fiscal year {year}",
        "source_url": "https://nces.ed.gov/ipeds/use-the-data",
        "fiscal_year": year,
        "variables": WANTED,
        "scope": ("PUBLIC institutions only. Private institutions file the FASB "
                  "form, which has no state-appropriations line, so an "
                  "institution absent here is almost always private and a dash "
                  "is the correct display. Never write a zero."),
        "institutions_reporting": len(out),
        "with_state_appropriations": with_state,
        "state_appropriations_total": total,
        "institutions": out,
    }, indent=2)
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(out):,} institutions from {path.name} (FY{year})")
    print(f"  {with_state:,} report state appropriations, "
          f"${total / 1e9:,.1f}bn in total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
