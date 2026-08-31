#!/usr/bin/env python3
"""Do the institutions with the highest foreign enrolment get the federal money?

Two facts sit side by side in this project and have never been crossed: which
institutions enrol the largest share of temporary-visa graduate students, and
which receive the most federal research money. This joins them.

WHY IT MATTERS THAT THE ANSWER IS TWO ANSWERS. The master's programmes with
the highest visa share are mostly not research universities and receive very
little federal R&D -- they are tuition-funded. The institutions receiving the
most federal R&D have high visa shares at DOCTORATE level, where the money
actually goes. These are two different mechanisms and conflating them would
overstate both.

MATCHING IS CONSERVATIVE. HERD writes "U. Pennsylvania" and "Johns Hopkins
U.a"; GSS writes the full name. Names are normalised and matched exactly on
the normalised form. Anything that does not match exactly is REPORTED AS
UNMATCHED rather than guessed at -- an earlier fuzzy match in this project
turned a military college in South Carolina into a trading firm.

Usage:
  python3 scripts/join_enrolment_and_funding.py
"""
from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
RANKING = ROOT / "site" / "data" / "gss_institution_ranking.json"
HERD = ROOT / "data" / "herd" / "herd_fy2024_table14.xlsx"
OUT = ROOT / "site" / "data" / "enrolment_and_funding.json"

# HERD abbreviates heavily: "U. Pennsylvania", "Albany Medical C.",
# "Georgia Inst. of Technology". GSS spells names out.
ABBREV = [
    (r"\bu\.?\b", "university"), (r"\bcoll?\.?\b", "college"),
    (r"\bc\.\B|\bc\.\s", "college "), (r"\binst\.?\b", "institute"),
    (r"\btech\.?\b", "technology"), (r"\bmed\.?\b", "medical"),
    (r"\bctr\.?\b", "center"), (r"\bsci\.?\b", "science"),
    (r"\ba&m\b", "am"), (r"\bpolytech\.?\b", "polytechnic"),
    (r"\bagri\.?\b", "agricultural"), (r"\bintl\.?\b", "international"),
]
STOP = {"the", "of", "at", "and", "for", "in", "system", "main", "campus"}

# "St." is genuinely ambiguous -- "St. Louis U." is Saint, "Kansas St. U." is
# State -- so both readings are generated and either may match. Guessing one
# corrupts the other.
ST_READINGS = ("saint", "state")


# HERD names a flagship by campus ("U. Michigan, Ann Arbor") where the GSS
# gives the plain name -- and fourteen GSS names cover more than one campus,
# so matching on the GSS name alone silently collapsed Ann Arbor, Dearborn
# and Flint into one record and reported the wrong one. IPEDS is consulted
# through the GSS UNITID for the campus-specific name, which resolves both
# problems deterministically.
#
# The few pairs below are what remains after that: HERD phrasings no rule
# recovers. Each was checked against the sheet by hand and a test asserts
# every target still resolves to exactly one HERD row.
ALIASES = {
    "Texas A&M University": "Texas A&M U., College Station and Health Science Center",
    "Vanderbilt University": "Vanderbilt U. and Vanderbilt U. Medical Center",
    "Pennsylvania State University-Main Campus":
        "Pennsylvania State U., University Park and Hershey Medical Center",
}


def variants(name: str) -> set[str]:
    """Normalised keys for a name; a match on any one is a match."""
    base = str(name or "").strip().lower()
    # HERD appends a footnote letter directly after the abbreviating period:
    # "Johns Hopkins U.a". Anchoring on the period matters -- a bare
    # "[a-e]$" also eats the last letter of "University of Chicago, The",
    # which then matches nothing.
    base = re.sub(r"(?<=\.)[a-e]$", "", base)
    base = base.replace("&", " and ").replace("-", " ").replace(",", " ")
    out = set()
    for st in ST_READINGS:
        s = re.sub(r"\bst\.?\b", st, base)
        s = re.sub(r"\bsaint\b", st, s)
        for pat, full in ABBREV:
            s = re.sub(pat, full, s)
        s = re.sub(r"[^a-z0-9 ]", " ", s)
        words = [w for w in s.split() if w and w not in STOP]
        if words:
            out.add(" ".join(sorted(words)))
    return out


def normalise(name: str) -> str:
    v = variants(name)
    return sorted(v)[0] if v else ""


def load_ipeds_names() -> dict[str, str]:
    """UNITID -> campus-specific institution name."""
    import csv
    path = ROOT / "data" / "ipeds" / "hd2024.csv"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return {r["UNITID"].strip(): (r.get("INSTNM") or "").strip()
                for r in csv.DictReader(fh) if r.get("UNITID")}



def load_herd() -> tuple[dict[str, dict], list[str]]:
    import openpyxl
    ws = openpyxl.load_workbook(HERD, read_only=True).active
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    out, dupes = {}, []
    for r in rows:
        name = str(r[0] or "").strip()
        if not name or name.lower().startswith("all institutions"):
            continue
        nums = [x for x in r[1:] if isinstance(x, (int, float))]
        if len(nums) < 3:
            continue
        # Rank, all R&D, then federal. Dollars in thousands.
        _rank, total_rd, federal = nums[0], nums[1], nums[2]
        rec = {"herd_name": name,
               "total_rd": int(total_rd * 1000),
               "federal_rd": int(federal * 1000)}
        keys = variants(name)
        if not keys:
            continue
        for key in keys:
            if key in out and out[key]["herd_name"] != name:
                dupes.append(f"{name} / {out[key]['herd_name']}")
                continue
            out[key] = rec
    return out, dupes


def main() -> int:
    for p in (RANKING, HERD):
        if not p.exists():
            print(f"  missing {p.relative_to(ROOT)}")
            return 1

    herd, dupes = load_herd()
    rank = json.loads(RANKING.read_text())
    ipeds = load_ipeds_names()

    # The full institution list, not the ranked extracts -- reading the top
    # twenty-five of each ranking cut the universe from 649 to 74 and made
    # the match rate meaningless.
    insts = {r["unitid"]: r for r in rank["institutions"] if r.get("unitid")}

    joined, unmatched = [], []
    for unitid, rec in insts.items():
        # The IPEDS name carries the campus; the GSS name often does not.
        name = ipeds.get(unitid) or rec["institution"]
        keys = variants(ALIASES.get(name, name)) | variants(rec["institution"])
        hits = {h["herd_name"]: h for k in keys if (h := herd.get(k))}
        if len(hits) != 1:                # no match, or an ambiguous one
            unmatched.append(rec["institution"])
            continue
        joined.append(rec | {"ipeds_name": name} | next(iter(hits.values())))

    if not joined:
        print("  nothing matched -- check the name normaliser")
        return 1

    def fed(r):
        return r["federal_rd"]

    top_funded = sorted(joined, key=lambda r: -fed(r))[:15]
    ma = [r for r in joined if "master's" in r]
    hi_share = sorted(ma, key=lambda r: -r["master's"]["share"])[:15]

    # The correlation itself, rather than two anecdotal lists. Institutions
    # are split into quartiles by federal R&D and the enrolment share is
    # pooled inside each -- a weighted share, not a mean of percentages, so
    # a tiny programme does not count as much as a large one.
    quartiles = {}
    for label in ("doctoral", "master's"):
        have = sorted((r for r in joined if label in r), key=fed)
        if len(have) < 8:
            continue
        n = len(have)
        cuts = [have[i * n // 4:(i + 1) * n // 4] for i in range(4)]
        quartiles[label] = [
            {"quartile": i + 1,
             "institutions": len(q),
             "federal_rd_median": sorted(fed(r) for r in q)[len(q) // 2],
             "enrolled": sum(r[label]["total"] for r in q),
             "foreign": sum(r[label]["foreign"] for r in q),
             "share": round(100 * sum(r[label]["foreign"] for r in q)
                            / sum(r[label]["total"] for r in q), 1)}
            for i, q in enumerate(cuts) if sum(r[label]["total"] for r in q)]

    doc = {
        "_comment": (
            "Temporary-visa share of full-time S&E&H graduate enrolment (GSS "
            "2024) joined to federal research and development expenditures "
            "(HERD FY2024 table 14). THE MONEY AND THE ENROLMENT SIT IN "
            "THE SAME INSTITUTIONS: by quartile of federal R&D, the doctoral "
            "visa share runs 20.5% in the lowest against 43.6% in the "
            "highest, and the highest quartile holds 167,396 of the doctoral "
            "students against 7,631 in the lowest. Master's runs 32.9% to "
            "50.3%. ONE NUANCE THAT MUST BE KEPT: the very highest master's "
            "SHARES are at institutions with almost no federal R&D -- "
            "tuition-funded programmes -- so 'highest share' and 'most "
            "federal money' name different institutions even though the "
            "overall relationship is positive. MATCHING goes through the GSS "
            "UNITID to the IPEDS campus name, because HERD campus-qualifies "
            "its names and fourteen GSS names cover more than one campus -- "
            "matching on the GSS name alone collapsed Ann Arbor, Dearborn and "
            "Flint into one record. Names are then matched exactly on a "
            "normalised form; nothing is fuzzy-matched. UNMATCHED IS NOT "
            "ZERO: an institution may be absent from HERD, which does suggest "
            "little R&D, or its name may simply not have been recovered, and "
            "these cannot be told apart here. HERD reports R&D EXPENDITURE, "
            "not obligations or student support, and is not all federal money "
            "an institution receives. Enrolments, not degrees."),
        "sources": {
            "enrolment": "NSF NCSES, Survey of Graduate Students and Postdoctorates, 2024",
            "funding": "NSF NCSES, Higher Education R&D Survey, FY2024 table 14",
        },
        "aliases_used": {k: v for k, v in ALIASES.items() if k in insts},
        "matched": len(joined),
        "unmatched_count": len(unmatched),
        "unmatched_examples": sorted(unmatched)[:20],
        "herd_duplicate_names": dupes,
        "by_federal_rd_quartile": quartiles,
        "largest_federal_recipients": [
            {"institution": r["institution"], "federal_rd": r["federal_rd"],
             "doctoral_share": r.get("doctoral", {}).get("share"),
             "masters_share": r.get("master's", {}).get("share")}
            for r in top_funded],
        "highest_masters_share": [
            {"institution": r["institution"],
             "masters_share": r["master's"]["share"],
             "masters_enrolled": r["master's"]["total"],
             "federal_rd": r["federal_rd"]}
            for r in hi_share],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {len(herd)} HERD institutions, {len(insts)} ranked institutions")
    print(f"  matched {len(joined)}, unmatched {len(unmatched)}")
    for label, qs in quartiles.items():
        print(f"\n  {label} visa share by federal R&D quartile:")
        for q in qs:
            print(f"   Q{q['quartile']} ({q['institutions']:>3} inst, median "
                  f"${q['federal_rd_median'] / 1e6:>7,.0f}m): {q['share']:>5.1f}% "
                  f"of {q['enrolled']:,}")
    print(f"\n  largest federal R&D recipients:")
    print(f"  {'institution':38}{'federal R&D':>14}{'PhD visa':>10}{'MA visa':>9}")
    for r in doc["largest_federal_recipients"][:8]:
        d = f"{r['doctoral_share']:.1f}%" if r["doctoral_share"] is not None else "-"
        m = f"{r['masters_share']:.1f}%" if r["masters_share"] is not None else "-"
        print(f"  {r['institution'][:36]:38}${r['federal_rd'] / 1e6:>12,.0f}m{d:>10}{m:>9}")
    print(f"\n  highest master's visa share, with their federal R&D:")
    for r in doc["highest_masters_share"][:8]:
        print(f"  {r['institution'][:36]:38}{r['masters_share']:>9.1f}%"
              f"${r['federal_rd'] / 1e6:>12,.0f}m")
    if unmatched:
        print(f"\n  unmatched examples: {sorted(unmatched)[:4]}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
