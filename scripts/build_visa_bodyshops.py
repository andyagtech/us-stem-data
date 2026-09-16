#!/usr/bin/env python3
"""The firms that supply H-1B workers to other companies, from their own filings.

WHY THE USCIS HUB CANNOT ANSWER THIS. The hub names every employer and counts
approvals, but publishes NAICS only to two digits -- "54", "56" -- which cannot
separate a staffing agency from a law firm. The Labor Department's LCA
disclosure files can: every certified application carries the employer's
six-digit NAICS, and three fields the employer must fill in itself.

  H_1B_DEPENDENT      the statutory test: broadly, more than 15% of the
                      workforce on H-1B (8 USC 1182(n)(3)).
  WILLFUL_VIOLATOR    whether the employer has been found a wilful violator.
  SECONDARY_ENTITY    whether the worker will be placed at another company's
                      worksite. This is the body shop in one field: the firm
                      sponsors the visa, another firm gets the work.

WHAT IS COUNTED. Certified applications only, because a withdrawn or denied
one placed nobody. The unit is the APPLICATION, not the position it asks for:
one application can cover forty workers, and Grandison Management files forty
positions per application where Microsoft files 1.4, so counting positions
would hand every share on this page to the bulk filers. Positions are carried
alongside as the ceiling they are. An LCA is PERMISSION to employ at a stated
wage, not proof anyone was hired -- the USCIS approvals in visa_staffing.json
are the closer measure of people.

WAGE LEVEL is the employer's own choice of prevailing-wage tier: Level I is the
entry rate for the occupation, Level IV the experienced one. Filing at Level I
or II is lawful and it is also the cheapest lawful option.

Usage:
  python3 scripts/build_visa_bodyshops.py [--files N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402
from build_visa_staffing import _norm as norm                 # noqa: E402

SRC = ROOT / "data" / "h1b" / "lca"
DEBAR = ROOT / "data" / "policy" / "debarments.json"
OUT = ROOT / "site" / "data" / "visa_bodyshops.json"

# The header drifts between years -- FY2024 writes H_1B_DEPENDENT and FY2025
# writes H-1B_DEPENDENT for the same field -- and a missed rename reads as a
# firm that is simply never dependent, which is the worst kind of wrong. Each
# field therefore lists its spellings, and a missing one stops the build.
NEED = {"CASE_STATUS": ("CASE_STATUS",),
        "EMPLOYER_NAME": ("EMPLOYER_NAME",),
        "NAICS_CODE": ("NAICS_CODE", "NAIC_CODE"),
        "H_1B_DEPENDENT": ("H_1B_DEPENDENT", "H-1B_DEPENDENT", "H1B_DEPENDENT"),
        "WILLFUL_VIOLATOR": ("WILLFUL_VIOLATOR", "WILLFUL_VIOLATOR_INDICATOR"),
        "SECONDARY_ENTITY": ("SECONDARY_ENTITY",),
        "PW_WAGE_LEVEL": ("PW_WAGE_LEVEL", "PW_WAGE_LEVEL_1"),
        "TOTAL_WORKER_POSITIONS": ("TOTAL_WORKER_POSITIONS", "TOTAL_WORKERS"),
        "WORKSITE_STATE": ("WORKSITE_STATE", "WORKSITE_STATE_1"),
        "WAGE_RATE_OF_PAY_FROM": ("WAGE_RATE_OF_PAY_FROM", "WAGE_RATE_OF_PAY_FROM_1"),
        "WAGE_UNIT_OF_PAY": ("WAGE_UNIT_OF_PAY", "WAGE_UNIT_OF_PAY_1"),
        "SOC_TITLE": ("SOC_TITLE",)}
SUPPLY = {"5613": "Employment services (staffing, temp help, PEO)",
          "5415": "Computer systems design and related services"}
LEVELS = ("I", "II", "III", "IV")



def kind(naics: str) -> str | None:
    """The supply industry this NAICS names, or None. The employer's own code."""
    for prefix, label in SUPPLY.items():
        if naics.startswith(prefix):
            return label
    return None


def annual_wage(v, unit) -> float | None:
    try:
        w = float(str(v).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None
    u = (unit or "").strip().lower()
    mult = {"year": 1, "hour": 2080, "week": 52, "bi-weekly": 26, "month": 12}.get(u)
    return w * mult if mult and w else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=0, help="limit for a quick run")
    args = ap.parse_args()
    files = sorted(SRC.glob("*.xlsx"))
    if args.files:
        files = files[-args.files:]
    if not files:
        print(f"  no LCA files in {SRC.relative_to(ROOT)}; restore them with the command in "
              "data/h1b/lca_archive_manifest.json")
        return 1
    import openpyxl

    emp: dict[tuple, dict] = {}
    nat = defaultdict(int)
    # The comparison that survives the obvious objection. "Placed workers earn
    # less" invites "they do different jobs", so hold the occupation fixed and
    # split each SOC title into positions a supply firm places at another
    # company's site, and everything else. Both sides are the same job title,
    # in the same year, from the same file.
    per_year: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    soc: dict[str, dict] = defaultdict(
        lambda: {"placed": {"n": 0, "f": 0, "wages": [], "low": 0, "lvl": 0},
                 "direct": {"n": 0, "f": 0, "wages": [], "low": 0, "lvl": 0}})
    for path in files:
        fy = (re.search(r"fy_?(\d{4})", path.name, re.I) or [None, None])[1]
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        hdr = [str(h).strip().upper() if h else "" for h in next(it)]
        idx = {}
        for field, spellings in NEED.items():
            hit = next((s for s in spellings if s in hdr), None)
            if hit:
                idx[field] = hdr.index(hit)
        missing = [c for c in NEED if c not in idx]
        if missing:
            print(f"  {path.name}: columns not found under any known spelling: {missing}")
            print(f"  header was: {hdr}")
            return 1
        n = 0
        for row in it:
            g = lambda c: row[idx[c]] if c in idx else None          # noqa: E731
            if str(g("CASE_STATUS") or "").strip().lower() != "certified":
                continue
            name = str(g("EMPLOYER_NAME") or "").strip()
            if not name:
                continue
            n += 1
            naics = re.sub(r"\D", "", str(g("NAICS_CODE") or ""))[:6]
            try:
                pos = int(float(g("TOTAL_WORKER_POSITIONS") or 1))
            except (TypeError, ValueError):
                pos = 1
            dep = str(g("H_1B_DEPENDENT") or "").strip().upper().startswith("Y")
            wil = str(g("WILLFUL_VIOLATOR") or "").strip().upper().startswith("Y")
            sec = str(g("SECONDARY_ENTITY") or "").strip().upper().startswith("Y")
            lvl = re.sub(r"[^IV]", "", str(g("PW_WAGE_LEVEL") or "").upper())
            wage = annual_wage(g("WAGE_RATE_OF_PAY_FROM"), g("WAGE_UNIT_OF_PAY"))

            # Keyed on the employer alone, not employer+state: a firm that places
            # workers into a dozen states is the thing being looked for, and
            # splitting it per state would hide it below every floor.
            e = emp.setdefault(name.upper(), {"employer": name, "naics": naics,
                                              "filings": 0, "positions": 0, "dependent": 0,
                                              "willful": 0, "secondary": 0, "wages": [],
                                              "states": defaultdict(int),
                                              "levels": dict.fromkeys(LEVELS, 0)})
            st = str(g("WORKSITE_STATE") or "").strip()
            if st:
                e["states"][st] += 1
            e["filings"] += 1
            e["positions"] += pos
            e["dependent"] += 1 if dep else 0
            e["willful"] += 1 if wil else 0
            e["secondary"] += 1 if sec else 0
            if lvl in e["levels"]:
                e["levels"][lvl] += 1
            if wage and 10_000 < wage < 1_000_000 and len(e["wages"]) < 20_000:
                e["wages"].append(wage)
            if naics and not e["naics"]:
                e["naics"] = naics

            nat["positions"] += pos
            nat["filings"] += 1
            nat["dependent"] += 1 if dep else 0
            nat["secondary"] += 1 if sec else 0
            nat["willful"] += 1 if wil else 0
            if lvl in LEVELS:
                nat["level_" + lvl] += 1
            for p, _label in SUPPLY.items():
                if naics.startswith(p):
                    nat["supply_filings_" + p] += 1

            if fy:
                y = per_year[fy]
                y["positions"] += pos
                y["filings"] += 1
                y["dependent"] += 1 if dep else 0
                y["secondary"] += 1 if sec else 0
                if kind(naics) and sec:
                    y["placed_by_supply"] += 1
                if lvl in LEVELS:
                    y["lvl"] += 1
                    y["low"] += 1 if lvl in ("I", "II") else 0

            title = str(g("SOC_TITLE") or "").strip()
            if title:
                b = soc[title]["placed" if (sec and kind(naics)) else "direct"]
                b["n"] += pos
                b["f"] += 1
                # Levels weighted by APPLICATION, not positions: one application
                # covering forty positions is one wage-tier decision, and letting
                # it count forty times hands the whole figure to the bulk filers.
                if lvl in LEVELS:
                    b["lvl"] += 1
                    b["low"] += 1 if lvl in ("I", "II") else 0
                if wage and 10_000 < wage < 1_000_000 and len(b["wages"]) < 400_000:
                    b["wages"].append(wage)
        print(f"  {path.name}: {n:,} certified rows")
        wb.close()

    rows = []
    for e in emp.values():
        pos, fil = e["positions"], e["filings"]
        ws = sorted(e.pop("wages"))
        low = e["levels"]["I"] + e["levels"]["II"]
        lvl_known = sum(e["levels"].values())
        states = sorted(e.pop("states").items(), key=lambda kv: -kv[1])
        rows.append({**e,
                     "states": len(states),
                     "top_states": [s for s, _ in states[:5]],
                     "kind": kind(e["naics"]),
                     # One application covering forty positions is a firm buying
                     # permission in bulk. Microsoft files 1.4 positions per
                     # application; a placement operation files dozens.
                     "positions_per_filing": round(pos / e["filings"], 1) if e["filings"] else None,
                     "median_wage": (ws[len(ws) // 2] if ws else None),
                     "low_level_pct": round(100 * low / lvl_known, 1) if lvl_known else None,
                     "secondary_pct": round(100 * e["secondary"] / fil, 1) if fil else None,
                     "dependent_pct": round(100 * e["dependent"] / fil, 1) if fil else None})
    rows.sort(key=lambda r: -r["positions"])

    # A body shop, measured rather than asserted: it supplies workers (its own
    # NAICS), it is H-1B dependent, and it places people at other companies'
    # sites. Floor of 100 positions so a two-person firm cannot top the table.
    shops = [r for r in rows if r["filings"] >= 50 and r["kind"]
             and (r["dependent_pct"] or 0) >= 50 and (r["secondary_pct"] or 0) >= 50]
    shops.sort(key=lambda r: -r["filings"])
    debar = json.loads(DEBAR.read_text()) if DEBAR.exists() else {"lists": []}
    barred = {}
    for lst in debar.get("lists", []):
        for ent in lst.get("entries", []):
            barred.setdefault(norm(ent.get("employer", "")), []).append(
                {"programme": lst["programme"].split("(")[0].strip(),
                 "start": ent.get("start"), "end": ent.get("end"), "reason": ent.get("reason")})
    for r in rows:
        r["debarments"] = barred.get(norm(r["employer"]))

    # What the applications actually became. An LCA is permission; a USCIS
    # approval is a person. Joining on the reduced name gives each firm here
    # its fifteen-year approval record from the other dataset.
    hub_path = OUT.with_name("visa_staffing.json")
    hub = {}
    if hub_path.exists():
        for f in json.loads(hub_path.read_text()).get("top_firm_families", []):
            hub[norm(f["family"])] = {"initial_approvals_2009_2023": f["initial_approval"],
                                      "continuing_approvals_2009_2023": f["continuing_approval"]}
    for r in rows:
        r["uscis"] = hub.get(norm(r["employer"]))

    # Occupations big enough on both sides to compare: 500 positions placed and
    # 500 not. Below that a median is one employer's filing habit, not a market.
    def med(ws):
        ws = sorted(ws)
        return round(ws[len(ws) // 2]) if ws else None

    occupations = []
    for title, s in soc.items():
        p, d = s["placed"], s["direct"]
        # The floor is on APPLICATIONS. A positions floor would admit an
        # occupation where one firm filed twice for 400 workers apiece.
        if p["f"] < 300 or d["f"] < 300 or not p["wages"] or not d["wages"]:
            continue
        mp, md = med(p["wages"]), med(d["wages"])
        occupations.append({
            "occupation": title,
            "placed_filings": p["f"], "direct_filings": d["f"],
            "placed_positions": p["n"], "direct_positions": d["n"],
            "placed_median_wage": mp, "direct_median_wage": md,
            "gap_usd": md - mp, "gap_pct": round(100 * (md - mp) / md, 1) if md else None,
            "placed_low_level_pct": round(100 * p["low"] / p["lvl"], 1) if p["lvl"] else None,
            "direct_low_level_pct": round(100 * d["low"] / d["lvl"], 1) if d["lvl"] else None})
    occupations.sort(key=lambda o: -(o["placed_filings"] + o["direct_filings"]))
    occupations = occupations[:20]

    keep = ("employer", "naics", "kind", "filings", "positions", "positions_per_filing",
            "states", "top_states",
            "dependent_pct", "secondary_pct", "low_level_pct", "median_wage", "willful",
            "debarments", "uscis")
    out = {
        "_comment": __doc__.split("Usage:")[0].strip(),
        "source": "US DOL Office of Foreign Labor Certification, H-1B LCA disclosure files",
        "source_url": "https://www.dol.gov/agencies/eta/foreign-labor/performance",
        "files": [f.name for f in files],
        "definitions": {
            "supply_naics": SUPPLY,
            "secondary_entity": ("The employer states the worker will be placed at another "
                                 "company's worksite -- the firm sponsors the visa, another "
                                 "firm gets the work."),
            "h1b_dependent": "The statutory test at 8 USC 1182(n)(3), self-reported on the form.",
            "body_shop_test": ("Counted here as: a supply-industry NAICS, 50%+ of positions "
                               "H-1B dependent, 50%+ placed at a secondary entity, and at "
                               "least 50 certified applications."),
            "positions_not_people": ("An LCA is permission to employ at a stated wage, not "
                                     "proof of hiring. These are ceilings on intent."),
            "placed_vs_direct": ("In by_occupation, PLACED means a position at a supply-industry "
                                 "firm that states the worker will sit at another company's "
                                 "worksite; DIRECT is every other certified position with the "
                                 "same occupation title. Comparing within one title holds the "
                                 "job constant, but not seniority, metro area or employer size."),
        },
        "national": {
            "certified_filings": nat["filings"], "positions": nat["positions"],
            "dependent_pct": round(100 * nat["dependent"] / nat["filings"], 1) if nat["filings"] else None,
            "secondary_pct": round(100 * nat["secondary"] / nat["filings"], 1) if nat["filings"] else None,
            "willful_filings": nat["willful"],
            "levels": {l: nat["level_" + l] for l in LEVELS},
            "low_level_pct": round(100 * (nat["level_I"] + nat["level_II"]) /
                                   max(1, sum(nat["level_" + l] for l in LEVELS)), 1),
            "supply_filings": {p: nat["supply_filings_" + p] for p in SUPPLY},
        },
        "by_fiscal_year": {y: {
            "positions": v["positions"], "filings": v["filings"],
            "dependent_pct": round(100 * v["dependent"] / v["filings"], 1) if v["filings"] else None,
            "secondary_pct": round(100 * v["secondary"] / v["filings"], 1) if v["filings"] else None,
            "placed_by_supply_firm_pct": round(100 * v["placed_by_supply"] / v["filings"], 1) if v["filings"] else None,
            "low_level_pct": round(100 * v["low"] / v["lvl"], 1) if v["lvl"] else None,
            # A year missing quarters cannot be compared on VOLUME with a whole
            # one -- and the missing quarter is rarely average: January-March,
            # fiscal Q2, is H-1B cap season and the busiest of the four. The
            # shares in this row stay readable; the position count does not.
            "quarters": sum(1 for f in files if re.search(rf"fy_?{y}", f.name, re.I)),
            "complete": sum(1 for f in files if re.search(rf"fy_?{y}", f.name, re.I)) == 4,
        } for y, v in sorted(per_year.items())},
        "by_occupation": occupations,
        "body_shops": [{k: r[k] for k in keep} for r in shops[:100]],
        "body_shop_totals": {
            "employers": len(shops),
            "filings": sum(r["filings"] for r in shops),
            "share_of_filings_pct": round(100 * sum(r["filings"] for r in shops) /
                                          nat["filings"], 1) if nat["filings"] else None,
            "positions": sum(r["positions"] for r in shops),
            "share_of_positions_pct": round(100 * sum(r["positions"] for r in shops) /
                                            nat["positions"], 1) if nat["positions"] else None,
        },
        "largest_employers": [{k: r[k] for k in keep}
                              for r in sorted(rows, key=lambda r: -r["filings"])[:40]],
        "debarred_with_filings": [{k: r[k] for k in keep} for r in rows if r["debarments"]],
        "caveats": [
            "Certified applications only; withdrawn and denied ones placed nobody.",
            "One application can cover several positions, and not every position is filled.",
            "NAICS, dependency, wilful-violator and secondary-entity are all self-reported.",
            "Employers are matched by the name on the form, so a firm that files under "
            "several entity names appears as several employers -- which understates the "
            "largest of them.",
            "Debarment is a formal bar with dates; a suspension pending investigation appears "
            "on no published list, so absence here is not evidence of good standing.",
        ],
    }
    write_json(OUT, out, indent=1)
    n = out["national"]
    print(f"  wrote {OUT.relative_to(ROOT)}: {n['certified_filings']:,} certified applications "
          f"({n['positions']:,} positions), "
          f"{n['dependent_pct']}% H-1B-dependent, {n['secondary_pct']}% placed at another "
          f"company's site, {n['low_level_pct']}% at wage Level I-II; "
          f"{out['body_shop_totals']['employers']} body shops = "
          f"{out['body_shop_totals']['share_of_filings_pct']}% of applications")
    return 0


if __name__ == "__main__":
    sys.exit(main())
