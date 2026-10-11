#!/usr/bin/env python3
"""Rank institutions for STEM fields beyond the six critical industries.

WHY THIS IS SEPARATE FROM rank_security_targets.py. That one reads
critical_industries.json, whose six sectors are a published editorial
claim: each has its own page, its own restriction note, and its own
numbers checked against the public record. Adding maths and mechanical
engineering to that list would silently change six published pages.

These fields are a SEARCH LIST, not a claim. They say where to go and
look, nothing more. So they live here, and they feed only the private
lab directory.

The ranking is the same shape as the other one: non-resident share of
doctorates per institution per field, from the IPEDS CIP index, over one
award-level basis so the 2010 recode cannot double-count.

Usage:
  python3 scripts/rank_stem_targets.py            # all fields
  python3 scripts/rank_stem_targets.py --field math
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

INDEX = ROOT / "data" / "ipeds" / "nra_index.csv.gz"
HD = ROOT / "data" / "ipeds" / "hd2023.csv"
OUT = ROOT / "data" / "labs" / "stem_targets.json"

#: Only the post-2010 basis, and only the window the rest of the site
#: uses, so these numbers sit beside the existing ones without a caveat.
YEAR_LO, YEAR_HI = 2015, 2022
BASIS = "aw17"
MIN_DOCTORATES = 20

#: The fields to search, as IPEDS CIP codes. A field is a LIST of codes
#: because universities split the same subject differently: Berkeley's
#: EECS is one department and Cornell has two, and the codes are how you
#: see both without caring what the department is called.
FIELDS = {
    "math": ("Mathematics and statistics",
             ["27.0101", "27.0301", "27.0501", "27.0502", "27.0303",
              "27.0199", "27.9999", "27.0601"]),
    "cs": ("Computer science",
           ["11.0701", "11.0101", "11.0102", "11.0199", "11.0801",
            "11.0901", "11.1003", "11.0401", "11.9999"]),
    "ee": ("Electrical and computer engineering",
           ["14.1001", "14.1003", "14.1004", "14.0903", "14.3301"]),
    "me": ("Mechanical engineering",
           ["14.1901", "14.1902", "14.0501"]),
    "chemeng": ("Chemical engineering", ["14.0701", "14.0702"]),
    "civil": ("Civil engineering",
              ["14.0801", "14.0802", "14.0803", "14.0804", "14.0805"]),
    "industrial": ("Industrial and systems engineering",
                   ["14.3501", "14.2701", "14.3601"]),
    "physics": ("Physics and astronomy",
                ["40.0801", "40.0802", "40.0806", "40.0810", "40.0201"]),
    "chemistry": ("Chemistry", ["40.0501", "40.0502", "40.0504", "40.0599"]),
    "biomed": ("Biomedical engineering", ["14.0501", "26.1201"]),
    "optics": ("Optics and photonics", ["14.1003", "40.0807"]),
    "oceanatmos": ("Atmospheric, ocean and earth science",
                   ["40.0401", "40.0601", "40.0607", "40.0699", "26.1302"]),
}


def cip_titles() -> dict[str, str]:
    """IPEDS's own name for each field code.

    The card used to be headed with MY name for a group of codes --
    "Earth & atmospheric" -- which is not a programme any university
    offers, so a reader who went looking for it at Missouri S&T could
    not find it. The federal title for what was actually counted,
    "Geological and Earth Sciences/Geosciences, Other", is checkable
    against IPEDS.
    """
    f = INDEX.parent / "cip_titles.csv"
    if not f.exists():
        return {}
    out = {}
    with open(f, newline="", encoding="utf-8-sig", errors="replace") as fh:
        for row in csv.DictReader(fh):
            c = (row.get("cipcode") or row.get("CIPCODE") or "").strip()
            t = (row.get("title") or row.get("TITLE") or "").strip()
            if c and t:
                out[c] = t
    return out


def institution_names() -> dict[str, str]:
    out: dict[str, str] = {}
    if not HD.exists():
        return out
    with open(HD, newline="", encoding="utf-8-sig", errors="replace") as fh:
        for row in csv.DictReader(fh):
            uid = (row.get("UNITID") or row.get("unitid") or "").strip()
            nm = (row.get("INSTNM") or row.get("instnm") or "").strip()
            if uid and nm:
                out[uid] = nm
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--field", help="one field slug, else all")
    ap.add_argument("--top", type=int, default=14,
                    help="institutions kept per field")
    ap.add_argument("--by", choices=["share", "volume"], default="share",
                    help="share: highest non-resident percentage, which "
                         "finds the extreme cases. volume: most "
                         "non-resident doctorates, which finds where the "
                         "people actually are. They rank almost "
                         "oppositely -- 85%% of 20 is 17 people, 60%% of "
                         "400 is 240 -- so a scrape aimed at share "
                         "reaches small programmes and misses the ones "
                         "that produce the most graduates.")
    a = ap.parse_args()

    if not INDEX.exists():
        sys.exit(f"Missing {INDEX}. Run scripts/build_nra_index.py first.")

    fields = ({a.field: FIELDS[a.field]} if a.field else FIELDS)
    wanted = {c: slug for slug, (_, codes) in fields.items() for c in codes}

    #: [total, nra] per (field, institution)
    acc: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["basis"] != BASIS:
                continue
            year = int(row["year"])
            if not YEAR_LO <= year <= YEAR_HI:
                continue
            slug = wanted.get(row["cipcode"])
            if not slug:
                continue
            cell = acc[slug][row["unitid"]]
            cell[0] += int(row["total"])
            cell[1] += int(row["nra"])

    names = institution_names()
    titles = cip_titles()
    #: which single code contributed most of this institution's awards
    #: in this field -- that is the one to name on the card
    top_cip: dict = {}
    with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["basis"] != BASIS:
                continue
            y = int(row["year"])
            if not YEAR_LO <= y <= YEAR_HI:
                continue
            slug = wanted.get(row["cipcode"])
            if not slug:
                continue
            k = (slug, row["unitid"])
            d = top_cip.setdefault(k, {})
            d[row["cipcode"]] = d.get(row["cipcode"], 0) + int(row["total"])
    rows = []
    for slug, (label, codes) in fields.items():
        per = acc.get(slug) or {}
        ranked = []
        for uid, (tot, nra) in per.items():
            if tot < MIN_DOCTORATES:
                continue
            #: An institution the IPEDS directory does not name cannot be
            #: searched for and should not appear as "UNITID 495767".
            if uid not in names:
                continue
            ranked.append({
                "field": slug, "field_name": label,
                "institution": names.get(uid, f"UNITID {uid}"),
                "unitid": uid, "doctorates": tot, "nra": nra,
                "nra_share": round(nra / tot * 100, 1),
                "cips": codes,
                "top_cip": (max(top_cip.get((slug, uid), {}),
                                key=top_cip.get((slug, uid), {}).get)
                            if top_cip.get((slug, uid)) else None),
                "ipeds_field": titles.get(
                    max(top_cip.get((slug, uid), {}),
                        key=top_cip.get((slug, uid), {}).get), "")
                    if top_cip.get((slug, uid)) else "",
            })
        if a.by == "volume":
            ranked.sort(key=lambda r: (-r["nra"], -r["nra_share"]))
        else:
            ranked.sort(key=lambda r: (-r["nra_share"], -r["doctorates"]))
        rows.extend(ranked[: a.top])

    rows.sort(key=lambda r: -(r["nra"] if a.by == "volume"
                              else r["nra_share"]))
    payload = {
        "built_from": "data/ipeds/nra_index.csv.gz",
        "why": ("A search list for the private lab directory. These fields "
                "are not the six critical industries and carry no "
                "restriction claim. They say where to look."),
        "window": f"{YEAR_LO}-{YEAR_HI}",
        "basis": BASIS,
        "basis_note": ("One award-level basis only. IPEDS recoded award "
                       "levels in 2010 and mixing the two counts the "
                       "transition years twice."),
        "ranked_by": a.by,
        "min_doctorates": MIN_DOCTORATES,
        "fields": {s: {"name": n, "cips": c} for s, (n, c) in FIELDS.items()},
        "count": len(rows),
        "targets": rows,
    }
    write_text(OUT, json.dumps(payload, indent=1))
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(rows)} institution-field pairs across {len(fields)} fields")
    for slug, (label, _) in fields.items():
        n = [r for r in rows if r["field"] == slug]
        if n:
            print(f"    {label[:38]:40} {len(n):>3}  top "
                  f"{n[0]['nra_share']}% {n[0]['institution'][:30]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
