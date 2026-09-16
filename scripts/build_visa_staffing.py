#!/usr/bin/env python3
"""Who actually sponsors H-1B workers: the staffing and consulting trade.

WHY THIS EXISTS. The published lists of "top employers" are Amazon, Google and
Microsoft, which is what a reader of the news sees. They are not where the
volume sits. This reads every row USCIS publishes -- fifteen fiscal years of
its H-1B Employer Data Hub, one row per employer per year -- and separates the
firms whose business IS supplying workers from the firms that hire them for
themselves, using the employer's own NAICS code rather than a guess from its
name.

WHAT IT MEASURES, AND WHAT EACH FIGURE MEANS.
  * INITIAL approvals are new workers entering the programme; CONTINUING
    approvals are extensions and amendments for someone already in it. They
    must never be summed: the same person appears again every time their
    petition is renewed. The ratio between them is itself the signal --
    a firm with many continuing approvals per initial one is holding workers
    over years, which is what a staffing arrangement looks like.
  * The DENIAL rate is USCIS's own, per employer and year.
  * INDUSTRY, as far as the hub goes. Every row carries a NAICS code of
    exactly two digits -- "54", "56" -- which is a sector, not an industry:
    "54" holds law firms, engineering consultancies and IT consultancies
    alike. A staffing agency CANNOT be separated from its clients here. That
    classification needs the Labor Department's disclosure files, which carry
    six digits plus the employer's own dependency and third-party-placement
    answers; it is done in build_visa_bodyshops.py, and this file's job is
    the thing the hub does better than anything else -- counting approved
    people, by employer, over fifteen years.

WHO IS BARRED. The Labor Department's debarment lists are joined on the
employer name (data/policy/debarments.json, verified against the live DOL
pages). Two things about that list matter more than its contents: it is very
short, and a SUSPENSION pending investigation -- the action reported against
Cloudera and Cognizant -- never appears on it at all, because DOL publishes
no list of suspensions.

Usage:
  python3 scripts/build_visa_staffing.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

HUB = ROOT / "data" / "uscis_hub"
DEBAR = ROOT / "data" / "policy" / "debarments.json"
OUT = ROOT / "site" / "data" / "visa_staffing.json"

# The hub's NAICS field is two digits in every row of every year -- checked,
# not assumed. These are therefore sectors, and the two that matter here are
# the two that CONTAIN the staffing trade without isolating it.
SECTORS = {"54": "Professional, scientific and technical services",
           "56": "Administrative and support services (includes staffing agencies)",
           "51": "Information", "52": "Finance and insurance",
           "61": "Educational services", "62": "Health care and social assistance",
           "33": "Manufacturing", "99": "Unclassified"}
FIELDS = {"initial_approval": ("Initial Approval", "Initial Approvals"),
          "initial_denial": ("Initial Denial", "Initial Denials"),
          "continuing_approval": ("Continuing Approval", "Continuing Approvals"),
          "continuing_denial": ("Continuing Denial", "Continuing Denials")}


def _num(v: str) -> int:
    try:
        return int(float(str(v).replace(",", "").strip() or 0))
    except ValueError:
        return 0


# Firms abbreviate on the form and the abbreviations are not consistent: one
# company files as TECH SOLNS, TECHNOLOGY SOLUTIONS and TECH SOLUTIONS in the
# same year. Expand first, then drop, so the three reduce to one name.
_ABBREV = {"svcs": "services", "svc": "services", "solns": "solutions",
           "soln": "solutions", "tech": "technologies", "techs": "technologies",
           "intl": "international", "ltd": "limited", "incorporated": "inc"}
_DROP = {"inc", "llc", "llp", "ltd", "limited", "corp", "corporation", "co", "company",
         "technologies", "technology", "solutions", "services", "group", "usa", "us",
         "the", "of"}


def _norm(name: str) -> str:
    """A name reduced for joining: case, punctuation, abbreviations, suffixes."""
    words = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower()).split()
    words = [_ABBREV.get(w, w) for w in words]
    return " ".join(w for w in words if w not in _DROP).strip()


def rows():
    for f in sorted(HUB.glob("*.csv")):
        with open(f, encoding="utf-8-sig", errors="replace") as fh:
            for r in csv.DictReader(fh):
                r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
                got = {}
                for key, names in FIELDS.items():
                    got[key] = next((_num(r[n]) for n in names if n in r), 0)
                yield {"year": r.get("Fiscal Year", f.stem[-4:]),
                       "employer": r.get("Employer", ""),
                       "naics": (r.get("NAICS") or "").strip(),
                       "state": r.get("State", ""), "city": r.get("City", ""),
                       **got}


def sector_label(naics: str) -> str | None:
    """The sector name, or None. Never a claim about what the firm does."""
    return SECTORS.get((naics or "")[:2])


def main() -> int:
    if not HUB.exists():
        print(f"  missing {HUB.relative_to(ROOT)}")
        return 1
    per_emp: dict[tuple, dict] = {}
    per_year: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    by_sector: dict[str, dict] = defaultdict(
        lambda: {"initial_approval": 0, "continuing_approval": 0, "employers": set()})
    for r in rows():
        if not r["employer"]:
            continue
        key = (r["employer"].upper(), r["state"])
        e = per_emp.setdefault(key, {
            "employer": r["employer"], "state": r["state"], "city": r["city"],
            "naics": r["naics"], "years": {}, "initial_approval": 0, "initial_denial": 0,
            "continuing_approval": 0, "continuing_denial": 0})
        for k in FIELDS:
            e[k] += r[k]
        e["years"][r["year"]] = e["years"].get(r["year"], 0) + r["initial_approval"]
        if r["naics"] and len(r["naics"]) > len(e["naics"]):
            e["naics"] = r["naics"]          # keep the most specific code seen
        y = per_year[r["year"]]
        y["initial_approval"] += r["initial_approval"]
        y["continuing_approval"] += r["continuing_approval"]
        y["initial_denial"] += r["initial_denial"]
        sector = (r["naics"] or "")[:2]
        if sector:
            by_sector[sector]["initial_approval"] += r["initial_approval"]
            by_sector[sector]["continuing_approval"] += r["continuing_approval"]
            by_sector[sector]["employers"].add(r["employer"].upper())

    employers = list(per_emp.values())
    for e in employers:
        e["sector"] = sector_label(e["naics"])
        ia, ca = e["initial_approval"], e["continuing_approval"]
        e["continuing_per_initial"] = round(ca / ia, 2) if ia else None
        tot = ia + e["initial_denial"]
        e["initial_denial_rate_pct"] = round(100 * e["initial_denial"] / tot, 1) if tot else None
        e["first_year"] = min(e["years"]) if e["years"] else None
        e["last_year"] = max(e["years"]) if e["years"] else None

    # The long tail: how much of the programme is small employers nobody names.
    by_initial = sorted(employers, key=lambda e: -e["initial_approval"])
    total_initial = sum(e["initial_approval"] for e in employers)
    def share(n): return round(100 * sum(e["initial_approval"] for e in by_initial[:n]) / total_initial, 1)
    tail = [e for e in employers if e["initial_approval"] <= 5]

    # The same firm files under several names -- "TATA CONSULTANCY SERVICES
    # LIMITED" and "TATA CONSULTANCY SVCS LTD" are two rows for one company,
    # and read separately they understate it by half. Grouping on the reduced
    # name repairs that. It groups by NAME, not by ownership: subsidiaries with
    # unrelated names stay apart, so these totals remain floors.
    fam: dict[str, dict] = {}
    for e in employers:
        f = fam.setdefault(_norm(e["employer"]) or e["employer"].lower(),
                           {"initial_approval": 0, "continuing_approval": 0, "names": set()})
        f["initial_approval"] += e["initial_approval"]
        f["continuing_approval"] += e["continuing_approval"]
        f["names"].add(e["employer"])
    families = sorted(({"family": max(v["names"], key=len), "names": sorted(v["names"]),
                        "initial_approval": v["initial_approval"],
                        "continuing_approval": v["continuing_approval"],
                        "share_pct": round(100 * v["initial_approval"] / total_initial, 2)}
                       for v in fam.values()), key=lambda f: -f["initial_approval"])

    debar = json.loads(DEBAR.read_text()) if DEBAR.exists() else {"lists": [], "specific_claims": []}
    barred = {}
    for lst in debar.get("lists", []):
        prog = lst["programme"].split("(")[0].strip()
        for ent in lst.get("entries", []):
            barred.setdefault(_norm(ent.get("employer", "")), []).append(
                {"programme": prog, "start": ent.get("start"), "end": ent.get("end"),
                 "reason": ent.get("reason"), "employer_as_listed": ent.get("employer")})
    matched = []
    for e in employers:
        hit = barred.get(_norm(e["employer"]))
        if hit:
            matched.append({"employer": e["employer"], "state": e["state"],
                            "initial_approval": e["initial_approval"],
                            "continuing_approval": e["continuing_approval"],
                            "debarments": hit})

    years = sorted(per_year)
    latest = years[-1] if years else None
    out = {
        "_comment": __doc__.split("Usage:")[0].strip(),
        "sources": {
            "employers": "USCIS H-1B Employer Data Hub, fiscal years " + (years[0] if years else "") +
                         "-" + (latest or ""),
            "employers_url": "https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub",
            "debarments": "US Department of Labor debarment lists (WHD H-1B; ETA PERM, H-2A, H-2B)",
            "debarments_url": "https://www.dol.gov/agencies/whd/immigration/h1b/debarment"},
        "definitions": {
            "initial_vs_continuing": ("Initial approvals are new workers entering the programme; "
                                      "continuing approvals are extensions for people already in "
                                      "it. Summing them counts the same person every year."),
            "sectors": SECTORS,
            "naics_limit": ("Every hub row carries a two-digit NAICS sector, never an industry. "
                            "Sector 54 holds law firms and IT consultancies together, so a "
                            "staffing firm cannot be separated from its clients in this data. "
                            "That separation is made from the Labor Department's disclosure "
                            "files instead, in visa_bodyshops.json.")},
        "years": years,
        "by_year": {y: dict(v) for y, v in sorted(per_year.items())},
        "totals": {
            "employers": len(employers),
            "initial_approvals": total_initial,
            "top10_share_pct": share(10), "top50_share_pct": share(50), "top200_share_pct": share(200),
            "employers_with_5_or_fewer": len(tail),
            "employers_with_5_or_fewer_share_pct": round(100 * sum(e["initial_approval"] for e in tail) / total_initial, 1),
        },
        "by_sector": {s: {"sector": SECTORS.get(s, "Other"),
                          "initial_approval": v["initial_approval"],
                          "continuing_approval": v["continuing_approval"],
                          "employers": len(v["employers"]),
                          "share_pct": round(100 * v["initial_approval"] / total_initial, 1)}
                      for s, v in sorted(by_sector.items(),
                                         key=lambda kv: -kv[1]["initial_approval"])},
        "top_firm_families": [{k: f[k] for k in ("family", "names", "initial_approval",
                                                 "continuing_approval", "share_pct")}
                              for f in families[:40]],
        "top_employers": [
            {k: e[k] for k in ("employer", "state", "city", "naics", "sector", "initial_approval",
                               "continuing_approval", "continuing_per_initial",
                               "initial_denial_rate_pct", "first_year", "last_year")}
            for e in by_initial[:60]],
        "debarred_in_the_hub": matched,
        "debarment_lists": [{"programme": l["programme"], "as_of": l.get("as_of"),
                             "source_url": l.get("source_url"), "count": len(l.get("entries", [])),
                             "entries": l.get("entries", [])}
                            for l in debar.get("lists", [])],
        # Only the claims that are NOT simply a row of the published list read
        # back. What is left is the interesting case: an action that was
        # reported and that no public list records.
        "suspensions": [c for c in debar.get("specific_claims", [])
                        if not str(c.get("verdict", "")).startswith("CONFIRMED")],
        # What was looked for and does not exist. An empty search result is a
        # finding when the thing searched for is a public enforcement list.
        "no_list_published": debar.get("no_list_published", []),
        "caveats": [
            "Every hub row carries a two-digit NAICS sector and nothing finer, so no count here "
            "separates a staffing firm from the companies it supplies.",
            "The hub names an employer per fiscal year; a firm that renames or splits entities "
            "appears as more than one employer.",
            "Debarment is a formal bar with dates. A suspension pending investigation is not "
            "published in any list, so absence from these lists is not evidence of good standing.",
        ] + debar.get("notes", []),
    }
    write_json(OUT, out, indent=1)
    t = out["totals"]
    print(f"  wrote {OUT.relative_to(ROOT)}: {t['employers']:,} employers, "
          f"{t['initial_approvals']:,} initial approvals {years[0]}-{latest}; "
          f"top 10 = {t['top10_share_pct']}%; top 200 = {t['top200_share_pct']}%; "
          f"{t['employers_with_5_or_fewer']:,} employers with <=5 ({t['employers_with_5_or_fewer_share_pct']}%); "
          f"{len(matched)} debarred employers found in the hub")
    return 0


if __name__ == "__main__":
    sys.exit(main())
