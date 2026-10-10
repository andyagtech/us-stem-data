#!/usr/bin/env python3
"""Export the normalised reference tables for browser-side SQL.

WHY THESE AND NOT OTHERS. The query page already carries the dissertation
corpus and the labour-visa tables. What it could not do was JOIN them to
anything: there was no institution table, no field-level enrolment, and
no way to ask "which universities with a high non-resident share in
electrical engineering also sponsor H-1Bs". These five tables close that.

  ipeds_awards        the raw IPEDS index every share on this site is
                      computed from -- year x institution x CIP x award
                      basis, with totals and non-resident counts. This
                      is the one that makes the rest checkable, because
                      a reader can recompute a published share from it.
  institutions        2,290 institutions with their identifiers, so the
                      other tables have something to join on.
  field_shares        the ranked institution-field pairs behind the lab
                      directory, both the six critical sectors and the
                      wider STEM search list.
  department_pages    the resolved and verified department URLs, with
                      which roster each one publishes.
  cap_exempt          the cap-exempt employer directory.

THE 2010 RECODE IS IN THE DATA, NOT HIDDEN. ipeds_awards carries its
`basis` column rather than being filtered to one. IPEDS recoded award
levels in 2010 and the transition years appear under both bases, so
summing across `basis` double-counts them. The column is there so the
reader can see that and choose; the table's description says so, and the
query page's examples all filter on it.

Usage:
  python3 scripts/build_reference_parquet.py
"""
from __future__ import annotations

import csv
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

DATA = ROOT / "site" / "data"
OUT = DATA / "exports"
IPEDS = ROOT / "data" / "ipeds"
LABS = ROOT / "data" / "labs"

#: Belongs to another builder. Named so an edit here cannot overwrite it.
PROTECTED = {"stem_records.parquet", "nonstem_records.parquet",
             "h1b_perm_public.parquet", "h1b_industry.parquet",
             "h1b_occupation.parquet", "h1b_employers.parquet"}


def write(rows: list[dict], name: str) -> None:
    import duckdb
    import pandas as pd
    if name in PROTECTED:
        raise SystemExit(f"FAIL: {name} is built elsewhere. Refusing.")
    if not rows:
        print(f"  {name:<26} SKIPPED (no rows)")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    con = duckdb.connect()
    con.register("t", pd.DataFrame(rows))
    con.execute(f"COPY t TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()
    print(f"  {name:<26}{len(rows):>9,} rows  "
          f"{path.stat().st_size / 1e6:>6.1f} MB")


def ipeds_awards() -> list[dict]:
    """The index behind every non-resident share this site publishes."""
    src = IPEDS / "nra_index.csv.gz"
    if not src.exists():
        return []
    out = []
    with gzip.open(src, "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t, n = int(r["total"]), int(r["nra"])
            out.append({
                #: NOT "year". Squirreling treats YEAR as a keyword, so a
                #: qualified reference -- "a.year" in any join -- fails to
                #: parse with "Expected identifier after '.'". Unqualified
                #: "year" happens to work, which makes the failure appear
                #: only once a reader writes their first join. Renaming the
                #: column costs nothing and removes the trap.
                "award_year": int(r["year"]),
                "unitid": r["unitid"],
                "cipcode": r["cipcode"],
                #: aw09 before the 2010 recode, aw17 after. The
                #: transition years appear under both: never sum across
                #: this column.
                "basis": r["basis"],
                "awards": t,
                "nonresident": n,
                "nonresident_pct": round(n / t * 100, 2) if t else None,
            })
    return out


def ipeds_directory() -> dict[str, dict]:
    """unitid -> name/state, straight from the IPEDS directory file.

    institution_profiles.json covers the institutions this site profiles,
    which is not all of them: 323 rows of field_by_institution had a null
    institution because their unitid is in the awards file and not in the
    profiles. A null name in a table people read is a defect, and
    dropping the row would be worse -- it would silently remove real
    awards from a total.
    """
    #: EVERY directory year, newest first. The awards index runs back to
    #: 1995 and carries institutions that have since closed or merged, so
    #: they are absent from the current directory: unitid 456348 is only
    #: in hd2018. Taking the newest file alone left 323 rows unnamed.
    years = sorted(
        (int(m), f) for f in IPEDS.glob("hd*.csv")
        if (m := f.stem[2:]).isdigit())
    out: dict[str, dict] = {}
    for _, f in reversed(years):
        with open(f, newline="", encoding="utf-8-sig", errors="replace") as fh:
            for row in csv.DictReader(fh):
                uid = (row.get("UNITID") or row.get("unitid") or "").strip()
                nm = (row.get("INSTNM") or row.get("instnm") or "").strip()
                if uid and nm and uid not in out:
                    out[uid] = {"name": nm,
                                "state": (row.get("STABBR")
                                          or row.get("stabbr") or "").strip(),
                                "city": (row.get("CITY")
                                         or row.get("city") or "").strip()}
    return out


def institutions() -> list[dict]:
    """Flat, because nested objects do not survive into SQL.

    institution_profiles.json nests its counts -- doctorate.awarded,
    doctorate.share -- which a Parquet column cannot hold usefully and a
    browser SQL engine cannot address. The nesting is flattened to
    prefixed columns so a reader can filter on them.
    """
    src = DATA / "institution_profiles.json"
    if not src.exists():
        return []
    out = []
    for i in json.loads(src.read_text()).get("institutions", []):
        row = {
            "unitid": i.get("unitid"),
            #: Called "name" here, not "institution": every other table
            #: in this export uses `institution` for the NAME, and a
            #: join reads better as institutions.name.
            "name": i.get("institution"),
            "state": i.get("state"),
            "city": i.get("city"),
            "control": i.get("control"),
            "graduate_enrolment": i.get("graduate_enrolment"),
            "total_enrolment": i.get("total_enrolment"),
            "gss_foreign_share": i.get("gss_foreign_share"),
            "graduate_tuition_out_of_state":
                i.get("graduate_tuition_out_of_state"),
        }
        for level in ("masters", "doctorate", "all_research_doctorates"):
            blk = i.get(level) or {}
            if isinstance(blk, dict):
                row[f"{level}_awarded"] = blk.get("awarded")
                row[f"{level}_nonresident"] = blk.get("non_resident")
                row[f"{level}_nonresident_pct"] = blk.get("share")
        out.append(row)
    return out


def field_shares() -> list[dict]:
    out = []
    for fn, key, fld in (("stem_targets.json", "field", "field_name"),
                         ("security_targets.json", "sector", "sector_name")):
        p = LABS / fn
        if not p.exists():
            continue
        src = json.loads(p.read_text())
        for t in src.get("targets", []):
            out.append({
                "field": t.get(key),
                "field_name": t.get(fld),
                "institution": t.get("institution"),
                "unitid": t.get("unitid"),
                "doctorates": t.get("doctorates"),
                "nonresident": t.get("nra"),
                "nonresident_pct": t.get("nra_share"),
                #: The six critical sectors carry a restriction note; the
                #: wider STEM list does not, and null here means "no
                #: claim made", not "no regime applies".
                "restriction": t.get("restriction"),
                "list": "critical_sector" if key == "sector" else "stem_search",
            })
    return out


def department_pages() -> list[dict]:
    p = LABS / "program_urls.json"
    if not p.exists():
        return []
    out = []
    for r in json.loads(p.read_text()).get("rows", []):
        if r.get("status") != "ok":
            continue
        out.append({
            "institution": r.get("institution"),
            "field": r.get("sector"),
            "department_url": r.get("url"),
            "page_title": r.get("title"),
            "students_url": r.get("students_url"),
            "faculty_url": r.get("faculty_url"),
            "directory_url": r.get("directory_url"),
            "publishes_student_roster": bool(r.get("students_url")),
            "publishes_faculty_page": bool(r.get("faculty_url")),
        })
    return out


def cap_exempt() -> list[dict]:
    for fn in ("cap_exempt_merged_employers.json", "cap_exempt_directory.json"):
        p = DATA / fn
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        rows = d.get("employers") or []
        if rows and isinstance(rows[0], dict):
            return rows
    return []


def cip_titles() -> dict[str, str]:
    """code -> title, so a reader is not left decoding "45.0603"."""
    f = IPEDS / "cip_titles.csv"
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


def field_by_institution(awards: list[dict], insts: list[dict]) -> list[dict]:
    """The pre-computed answer to the question people actually ask.

    "Non-resident share for this field at this university" is the shape
    of nearly every question this table gets, and answering it from
    ipeds_awards means scanning 260,170 rows and joining to institutions:
    2.1 seconds in the browser, which is long enough that a reader
    assumes the page has hung.

    So it is pre-aggregated here: one basis, the published window,
    summed to institution x CIP, with the institution name already
    folded in. 12,594 rows and no join. ipeds_awards stays for anyone
    who needs another window, another basis, or a year-by-year series --
    this table cannot answer those, and says so in its description.
    """
    names = {i["unitid"]: i for i in insts}
    titles = cip_titles()
    #: Fall back to the IPEDS directory for any unitid the profiles do
    #: not carry, so no row ships with a null institution.
    for uid, d in ipeds_directory().items():
        names.setdefault(uid, {"name": d["name"], "state": d["state"],
                               "control": None})
    acc: dict = {}
    for r in awards:
        if r["basis"] != "aw17" or not 2015 <= r["award_year"] <= 2022:
            continue
        k = (r["unitid"], r["cipcode"])
        cell = acc.setdefault(k, [0, 0])
        cell[0] += r["awards"]
        cell[1] += r["nonresident"]
    out = []
    for (uid, cip), (tot, nra) in acc.items():
        i = names.get(uid) or {}
        out.append({
            "unitid": uid,
            "institution": i.get("name"),
            "state": i.get("state"),
            "control": i.get("control"),
            "cipcode": cip,
            "field": titles.get(cip),
            #: The two rollup levels, so a reader can group by discipline
            #: without writing a LIKE over a string.
            "cip2": cip.split(".")[0],
            "cip4": cip[:5],
            "awards": tot,
            "nonresident": nra,
            "nonresident_pct": round(nra / tot * 100, 1) if tot else None,
        })
    out.sort(key=lambda r: -(r["nonresident_pct"] or 0))
    return out


def main() -> int:
    print("Reference tables for browser-side SQL")
    awards, insts = ipeds_awards(), institutions()
    write(awards, "ipeds_awards.parquet")
    write(insts, "institutions.parquet")
    write(field_by_institution(awards, insts), "field_by_institution.parquet")
    write(field_shares(), "field_shares.parquet")
    write(department_pages(), "department_pages.parquet")
    write(cap_exempt(), "cap_exempt.parquet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
