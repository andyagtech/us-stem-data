#!/usr/bin/env python3
"""In-state against out-of-state: how many students, and what each pays.

WHAT THIS IS

SHEEO's State Higher Education Finance survey added a residency breakout in
2020. For public four-year institutions in each state it gives the split of
full-time-equivalent enrolment between in-state and out-of-state students, and
the net tuition and fee revenue collected per FTE from each. Those two together
answer a question the enrolment files cannot: not just who is here, but who
pays, and how much more.

THE ONE THING THAT MUST TRAVEL WITH EVERY FIGURE

**Out-of-state is not the same as foreign.** SHEEO's own note 3 is explicit:
"Out-of-state FTE includes international students and students that do not meet
residency requirements." A student from the next state over and a student from
Shanghai are in the same column here. This dataset therefore measures the PRICE
a non-resident pays and the SHARE of revenue non-residents provide. It never
measures how many of them are foreign, and anything published from it that
implies otherwise is wrong.

WHAT IS AN ESTIMATE AND WHAT IS ABSENT

SHEEO publishes which states estimated a breakout and which could not provide
one, and those lists are parsed from the workbook's own sheet rather than typed
here, so they cannot drift from the source. A state that could not provide a
breakout is recorded as missing and is never shown as a number.

Four-year PUBLIC institutions only. Medical FTE are excluded; dual-enrolment
students are included in state totals.

Source: data/state_funding/sheeo/SHEEO_SHEF_FY24_Residency_Data.xlsx
Output: site/data/state_residency.json

Usage:
    python3 scripts/build_state_residency.py
"""
from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

import openpyxl

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "state_funding" / "sheeo" / "SHEEO_SHEF_FY24_Residency_Data.xlsx"
OUT = ROOT / "site" / "data" / "state_residency.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

COLS = {
    "in_state_fte_share": 2,
    "out_of_state_fte_share": 3,
    "in_state_net_tuition_per_fte": 4,
    "out_of_state_net_tuition_per_fte": 5,
    "in_state_revenue_share": 6,
    "out_of_state_revenue_share": 7,
    "net_fte": 8,
    "net_tuition_revenue": 9,
    "in_state_fte": 10,
    "out_of_state_fte": 11,
    "uncategorizable_fte": 12,
    "in_state_revenue": 13,
    "out_of_state_revenue": 14,
    "uncategorizable_revenue": 15,
}


def parse_flag_cell(text: str) -> dict[str, list[int]]:
    """"AL, AR, KY (2023, 2024), ME (2020, 2021)" -> {state: [years]}.

    An empty year list means the flag applies to every year the state has.
    Parsing this rather than retyping it means the flags cannot drift from the
    workbook, which is the only place they are authoritative.
    """
    out: dict[str, list[int]] = {}
    for part in re.finditer(r"([A-Z]{2})(?:\s*\(([^)]*)\))?", text or ""):
        years = [int(y) for y in re.findall(r"20\d\d", part.group(2) or "")]
        out[part.group(1)] = years
    return out


def main() -> int:
    if not SRC.exists():
        raise SystemExit(f"FAIL: {SRC} is missing. Nothing written.")
    wb = openpyxl.load_workbook(SRC, data_only=True, read_only=True)

    flags = {}
    for row in wb["Estimates or Missing Data"].iter_rows(values_only=True):
        if not row or not row[0]:
            continue
        label = str(row[0]).strip().upper()
        if label in ("ESTIMATES", "MISSING"):
            flags[label] = {"fte": parse_flag_cell(str(row[1] or "")),
                            "tuition": parse_flag_cell(str(row[2] or ""))}
    if set(flags) != {"ESTIMATES", "MISSING"}:
        raise SystemExit("FAIL: the workbook's estimate/missing sheet changed "
                         "shape. Nothing written.")

    rows = list(wb["Residency Data"].iter_rows(values_only=True))
    header = rows[0]
    for name, idx in COLS.items():
        if header[idx] is None:
            raise SystemExit(f"FAIL: column {idx} ({name}) is empty. The "
                             f"workbook layout changed; nothing written.")

    # SHEEO writes "D.C."; this site's table says "District of Columbia".
    ABBR = {"D.C.": "DC"}
    for line in (ROOT / "scripts" / "build_state_pages.py").read_text().splitlines():
        for m in re.finditer(r'"([A-Z]{2})": "([^"]+)"', line):
            ABBR.setdefault(m.group(2), m.group(1))

    states: dict[str, dict] = {}
    unmatched = set()
    for r in rows[1:]:
        if not r or not r[0] or not r[1]:
            continue
        name = str(r[0]).strip()
        abbr = ABBR.get(name)
        if not abbr:
            unmatched.add(name)
            continue
        year = int(r[1])
        rec = {k: r[i] for k, i in COLS.items()}
        rec = {k: (round(v, 4) if isinstance(v, float) else v)
               for k, v in rec.items() if v is not None}

        def flagged(kind: str, which: str) -> bool:
            entry = flags[which][kind].get(abbr)
            return entry is not None and (not entry or year in entry)

        rec["fte_estimated"] = flagged("fte", "ESTIMATES")
        rec["fte_missing"] = flagged("fte", "MISSING")
        rec["tuition_estimated"] = flagged("tuition", "ESTIMATES")
        rec["tuition_missing"] = flagged("tuition", "MISSING")
        # A state that could not provide a breakout must not publish one.
        if rec["fte_missing"]:
            for k in ("in_state_fte_share", "out_of_state_fte_share",
                      "in_state_fte", "out_of_state_fte"):
                rec.pop(k, None)
        if rec["tuition_missing"]:
            for k in ("in_state_net_tuition_per_fte",
                      "out_of_state_net_tuition_per_fte",
                      "in_state_revenue_share", "out_of_state_revenue_share"):
                rec.pop(k, None)
        states.setdefault(abbr, {"state": abbr, "name": name, "years": {}})
        states[abbr]["years"][str(year)] = rec

    if unmatched:
        print(f"  note: {len(unmatched)} row label(s) matched no state "
              f"({', '.join(sorted(unmatched))})")

    latest = max(y for s in states.values() for y in s["years"])
    for s in states.values():
        cur = s["years"].get(latest, {})
        s["latest_year"] = latest
        ins = cur.get("in_state_net_tuition_per_fte")
        out_ = cur.get("out_of_state_net_tuition_per_fte")
        s["premium_multiple"] = round(out_ / ins, 2) if ins and out_ else None
        s["out_of_state_fte_share"] = cur.get("out_of_state_fte_share")
        s["out_of_state_revenue_share"] = cur.get("out_of_state_revenue_share")

    data = {
        "source": ("SHEEO State Higher Education Finance, student residency "
                   "data, FY2020-FY2024"),
        "source_url": "https://shef.sheeo.org/",
        "scope": "public four-year institutions; medical FTE excluded",
        "latest_year": latest,
        "caveat": ("Out-of-state includes international students AND domestic "
                   "students from other states. This measures what a "
                   "non-resident pays, never how many of them are foreign. "
                   "These are NET tuition and fee revenue per FTE -- what the "
                   "institution actually collected after institutional aid, "
                   "not the sticker price. Florida's in-state figure is $604 "
                   "because state scholarships cover most of the posted "
                   "tuition, not because Florida charges $604."),
        "flag_lists": flags,
        "states": dict(sorted(states.items())),
    }
    write_json(OUT, data, indent=2)
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(states)} states, FY{min(y for s in states.values() for y in s['years'])}"
          f"-FY{latest}")
    have = [s for s in states.values() if s["premium_multiple"]]
    have.sort(key=lambda s: -s["premium_multiple"])
    print(f"  {len(have)} states publish both tuition figures for {latest}")
    for s in have[:5]:
        print(f"    {s['name']:<16} out-of-state pays {s['premium_multiple']}x "
              f"(${s['years'][latest]['in_state_net_tuition_per_fte']:,.0f} vs "
              f"${s['years'][latest]['out_of_state_net_tuition_per_fte']:,.0f})")
    missing = sorted(a for a, s in states.items()
                     if s["years"].get(latest, {}).get("tuition_missing"))
    print(f"  no published tuition breakout: {', '.join(missing) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
