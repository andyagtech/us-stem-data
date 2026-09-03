#!/usr/bin/env python3
"""Compact lookup files so the assistant can answer from data, not from prose.

THE GAP THIS CLOSES. The Lambda already ships 44 published datasets in
chat_data/datasets/ -- about 12 MB -- and no tool reads any of them. The
assistant carries a knowledge file per finding, so it can describe the wage
levels or the institution table, and then cannot give you a number from either.
Everything it can actually look up comes from six files built long before most
of those datasets existed.

Two files are written here, both small enough to parse on a cold start:

  summary.json             the headline figure from every finding, with the
                           limit attached to each -- a copy of the published
                           artifact, so the assistant and the site quote the
                           same numbers from the same build.

  institutions_compact.json  one trimmed row per institution plus the national
                           rankings and the state rollup. The full profile file
                           is 2.4 MB, which is affordable to ship and wasteful
                           to parse on every cold start; the fields dropped are
                           the ones no question reaches for.

KEYS ARE SHORT ON PURPOSE. This file is read by a machine, not a person, and
the field names are a third of its size at full length. The mapping is written
into the file itself under "fields" so nothing has to remember it.

Usage:
  python3 scripts/build_chat_lookups.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

SITE = ROOT / "site" / "data"
OUT = ROOT / "cloud" / "chat" / "chat_data"

FIELDS = {
    "u": "unitid", "n": "institution", "st": "state", "c": "control",
    "m": "core-STEM master's awarded 2021-2025",
    "ms": "non-resident share of those master's, pct",
    "mc": "change in that share since 2010-2014, percentage points",
    "d": "core-STEM research doctorates awarded 2021-2025",
    "ds": "non-resident share of those doctorates, pct",
    "dc": "change in that share since 2010-2014, percentage points",
    "g": "graduate enrolment, autumn 2023",
    "gs": "non-resident share of graduate enrolment, pct",
    "fo": "federal obligations from all agencies FY2023, USD",
    "fr": "federally financed R&D FY2024, USD",
    "ft": "S&E fellowships, traineeships and training grants FY2023, USD",
    "fpd": "federal obligations per core-STEM research doctorate per year, USD",
    "fps": "core-STEM as a share of all research doctorates, pct -- how much of "
           "the doctoral output the fpd denominator covers",
    "fpp": "professional doctorates awarded 2015-2022 (MD, DDS, JD) -- large "
           "here means fpd is measured against a small part of the output",
    "t": "published out-of-state graduate tuition 2023-24, USD",
}


def row(p: dict) -> dict:
    """One institution, trimmed. Absent stays absent -- never filled with zero."""
    ge = p.get("graduate_enrolment") or {}
    fed = p.get("federal") or {}
    out = {"u": p["unitid"], "n": p["institution"], "st": p["state"],
           "c": p["control"][:3]}
    for key, block, field in (
            ("m", "masters", "awarded"), ("ms", "masters", "share"),
            ("mc", "masters", "share_change"),
            ("d", "doctorate", "awarded"), ("ds", "doctorate", "share"),
            ("dc", "doctorate", "share_change")):
        v = (p.get(block) or {}).get(field)
        if v:
            out[key] = v
    for key, v in (("g", ge.get("total")), ("gs", ge.get("share")),
                   ("fo", fed.get("obligations")), ("fr", fed.get("rd_federal")),
                   ("ft", fed.get("training")),
                   ("fpd", p.get("federal_per_doctorate")),
                   ("fps", p.get("cost_basis_share_of_all_doctorates")),
                   ("fpp", p.get("cost_basis_professional_doctorates")),
                   ("t", p.get("graduate_tuition_out_of_state"))):
        if v:
            out[key] = v
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    summary = json.loads((SITE / "summary.json").read_text())
    write_json(OUT / "summary.json", summary)

    src = SITE / "institution_profiles.json"
    prof = json.loads(src.read_text())
    compact = {
        "_comment": [
            "One trimmed row per institution, plus the national rankings and "
            "the state rollup, for the assistant to look figures up in.",
            "",
            "Field names are abbreviated; 'fields' below is the mapping and is "
            "authoritative. A field that is absent from a row means no data, "
            "never zero: an institution with no federal block was not surveyed, "
            "it did not spend nothing.",
            "",
            "Non-resident is a visa category, not a birthplace, so every share "
            "here is a floor on the foreign-born proportion. fpd is an "
            "intensity ratio and not a price -- read fps and fpp beside it "
            "before quoting it, because the top of that ranking is medical "
            "schools where the denominator covers a fraction of the output.",
            "",
            "Shares in 'states' are recomputed from the sums, never averaged "
            "across institutions.",
        ],
        "fields": FIELDS,
        "sources": prof["sources"],
        "windows": prof["windows"],
        "floors": prof["floors"],
        "coverage": prof["coverage"],
        "crosswalk": {k: v for k, v in prof["crosswalk"].items()
                      if k != "largest_unmatched"},
        "national_per_doctorate": prof["national_per_doctorate"],
        "rankings": prof["rankings"],
        "ranked_counts": prof["ranked_counts"],
        "states": prof["states"],
        "institutions": [row(p) for p in prof["institutions"]],
    }
    write_json(OUT / "institutions_compact.json", compact)

    full = src.stat().st_size / 1024
    small = (OUT / "institutions_compact.json").stat().st_size / 1024
    print(f"  wrote {(OUT / 'summary.json').relative_to(ROOT)}: "
          f"{summary['figure_count']} figures")
    print(f"  wrote {(OUT / 'institutions_compact.json').relative_to(ROOT)}: "
          f"{len(compact['institutions']):,} institutions, "
          f"{small:.0f} KB from {full:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
