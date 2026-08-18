#!/usr/bin/env python3
"""
Build a searchable index of non-resident-alien (NRA) share of research
doctorate completions, by (institution, CIP code, year).

NRA is the federal IPEDS reporting category "Nonresident alien" (renamed
"U.S. Nonresident" in recent collections): a student who is not a U.S.
citizen, national, or permanent resident.  It is a visa/residency status
reported by the institution.  It is NOT ethnicity, race, or country of
origin, and nothing in this index should be read as such.

Source: IPEDS Completions, data/ipeds/C{year}_A.csv (and the 1995-98
academic-year files C{yy}{yy}_A).  Research doctorates only.

Output (all under data/ipeds/):
  nra_index.csv.gz        year,unitid,cipcode,basis,total,nra   (one row per
                          institution x CIP x year)
  nra_index_meta.json     build metadata, per-year coverage, caveats
  cip_titles.csv          cipcode,title  (CIP 2020 titles + 2-digit families)

Query it with scripts/query_nra_index.py.

Usage:
    python3 scripts/build_nra_index.py                # all available years
    python3 scripts/build_nra_index.py --start 2010 --end 2024
"""

import argparse
import csv
import gzip
import io
import json
import os
import sys
import zipfile
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ipeds_config import IPEDS_DATA_DIR, YEAR_FILES  # noqa: E402

OUT_INDEX = os.path.join(IPEDS_DATA_DIR, "nra_index.csv.gz")
OUT_META = os.path.join(IPEDS_DATA_DIR, "nra_index_meta.json")
OUT_CIP = os.path.join(IPEDS_DATA_DIR, "cip_titles.csv")
DICT_XLSX = os.path.join(IPEDS_DATA_DIR, "dictionaries", "C2023_a_dict.xlsx")

# Years with a usable NRA breakdown.  1984-1994 completions files carry only
# CRACE15/CRACE16 (grand totals by sex) with no race/residency detail, so no
# NRA share can be computed for them.  1990 and 1999 are missing upstream.
FIRST_YEAR = 1995
LAST_YEAR = 2025

# CIP 2020 two-digit series titles (for family-level rollups).
CIP_FAMILIES = {
    "01": "Agriculture and Related Sciences", "03": "Natural Resources and Conservation",
    "04": "Architecture", "05": "Area, Ethnic, Cultural, Gender and Group Studies",
    "09": "Communication and Journalism", "10": "Communications Technologies",
    "11": "Computer and Information Sciences", "12": "Personal and Culinary Services",
    "13": "Education", "14": "Engineering", "15": "Engineering Technologies",
    "16": "Foreign Languages and Linguistics", "19": "Family and Consumer Sciences",
    "21": "Technology Education", "22": "Legal Professions and Studies",
    "23": "English Language and Literature", "24": "Liberal Arts and Humanities",
    "25": "Library Science", "26": "Biological and Biomedical Sciences",
    "27": "Mathematics and Statistics", "28": "Military Science and Operations",
    "29": "Military Technologies", "30": "Multi/Interdisciplinary Studies",
    "31": "Parks, Recreation and Fitness Studies", "32": "Basic Skills",
    "33": "Citizenship Activities", "34": "Health-Related Knowledge and Skills",
    "35": "Interpersonal and Social Skills", "36": "Leisure and Recreational Activities",
    "37": "Personal Awareness and Self-Improvement", "38": "Philosophy and Religious Studies",
    "39": "Theology and Religious Vocations", "40": "Physical Sciences",
    "41": "Science Technologies", "42": "Psychology", "43": "Homeland Security and Protective Services",
    "44": "Public Administration and Social Service", "45": "Social Sciences",
    "46": "Construction Trades", "47": "Mechanic and Repair Technologies",
    "48": "Precision Production", "49": "Transportation and Materials Moving",
    "50": "Visual and Performing Arts", "51": "Health Professions and Clinical Sciences",
    "52": "Business, Management and Marketing", "53": "High School/Secondary Diplomas",
    "54": "History", "55": "Bilingual/Multilingual Education", "60": "Residency Programs",
    "61": "Medical Residency/Fellowship", "99": "Grand total (institution aggregate)",
}


# ---------------------------------------------------------------------------
# File resolution / reading
# ---------------------------------------------------------------------------

def find_source(year: int):
    """Return (label, opener) for a year's completions file, or None.

    Mirrors scripts/ipeds_filter._find_csv: exact stem wins, then the revised
    (_RV) variant, so this index matches the rest of the repo.  Also reads
    C{year}_A.zip in place, since the newest release ships zipped and disk is
    tight.
    """
    stem = YEAR_FILES[year].completions.lower()
    names = os.listdir(IPEDS_DATA_DIR)
    csvs = {n.lower().rsplit(".", 1)[0]: n for n in names if n.lower().endswith(".csv")}
    for cand in (stem, stem + "_rv"):
        if cand in csvs:
            path = os.path.join(IPEDS_DATA_DIR, csvs[cand])
            return csvs[cand], lambda p=path: open(p, encoding="utf-8-sig", errors="replace")
    zips = {n.lower().rsplit(".", 1)[0]: n for n in names if n.lower().endswith(".zip")}
    if stem in zips:
        zpath = os.path.join(IPEDS_DATA_DIR, zips[stem])

        def _open(zp=zpath):
            zf = zipfile.ZipFile(zp)
            inner = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
            return io.TextIOWrapper(zf.open(inner), encoding="utf-8-sig", errors="replace")

        return zips[stem] + " (zipped)", _open
    return None


def _num(v: str) -> int:
    v = v.strip().strip('"').strip()
    if not v or v in ("Z", "R", "A", "."):
        return 0
    try:
        return int(float(v))
    except ValueError:
        return 0


def scan_year(year: int):
    """Return (rows, stats) for one year.

    rows: list of (unitid, cipcode, basis, total, nra)
    Gotchas handled here, all verified against the files on disk:
      * The first column name carries a UTF-8 BOM -> opened with utf-8-sig.
      * CIPCODE values are space padded in 2008-2010 ('99     ') and quoted
        in the pre-2008 files -> stripped before comparison.
      * CIPCODE '99' is the institution-level GRAND TOTAL, not a program.
        Including it alongside real CIP rows double-counts every institution.
      * AWLEVEL is zero padded ('09'), so it is compared as an int.
      * MAJORNUM is absent before 2003; where present only first majors are
        counted (second majors are <0.3% of doctorate completions).
      * Residency columns changed name in 2008: legacy CRACE01/CRACE02 are
        NRA men/women and CRACE15/CRACE16 are grand totals by sex; from 2008
        on CNRALT and CTOTALT carry the same quantities.  In 2008-2010 the
        legacy and modern *race* detail columns coexist row by row, but
        CNRALT/CTOTALT are populated for every row under either scheme
        (verified: 0 blanks), so no summing across schemes is needed for the
        residency and total measures this index uses.
    """
    found = find_source(year)
    if not found:
        return [], {"error": "file not found"}
    label, opener = found

    fh = opener()
    reader = csv.reader(fh)
    header = [c.strip().strip('"').upper() for c in next(reader)]
    idx = {c: n for n, c in enumerate(header)}

    modern = "CNRALT" in idx and "CTOTALT" in idx
    i_unit, i_cip, i_aw = idx["UNITID"], idx["CIPCODE"], idx["AWLEVEL"]
    i_major = idx.get("MAJORNUM")
    i_part = idx.get("PART")
    if modern:
        i_nra, i_tot = idx["CNRALT"], idx["CTOTALT"]
    else:
        i_nra = (idx["CRACE01"], idx["CRACE02"])
        i_tot = (idx["CRACE15"], idx["CRACE16"])

    # Pass 1 (2008-2009 only): which institutions report the new doctorate
    # award levels?  NCES split AWLEVEL 9 into 17/18/19 in 2008 and each
    # institution used one scheme or the other, never both (verified: zero
    # overlap).  For institutions on 17/18/19, 17 is the research doctorate;
    # institutions still on 9 have their professional doctorates in AWLEVEL 10,
    # so 9 is still research-only for them.
    new_scheme = set()
    transition = year in (2008, 2009)
    raw = None
    if transition:
        raw = list(reader)
        for row in raw:
            if _num(row[i_aw]) in (17, 18, 19):
                new_scheme.add(row[i_unit].strip())
        rows_iter = raw
    else:
        rows_iter = reader

    agg = defaultdict(lambda: [0, 0])  # (unitid, cip, basis) -> [total, nra]
    stats = {"file": label, "aw9_institutions": 0, "aw17_institutions": 0,
             "skipped_aggregate_rows": 0}
    seen9, seen17 = set(), set()

    for row in rows_iter:
        if i_part is not None and row[i_part].strip().strip('"').upper() != "A":
            continue
        if i_major is not None and row[i_major].strip().strip('"') != "1":
            continue
        aw = _num(row[i_aw])
        unit = row[i_unit].strip().strip('"')
        if year >= 2010:
            if aw != 17:
                continue
            basis = "aw17"
        elif transition:
            if unit in new_scheme:
                if aw != 17:
                    continue
                basis = "aw17"
            else:
                if aw != 9:
                    continue
                basis = "aw09"
        else:
            if aw != 9:
                continue
            basis = "aw09"

        cip = row[i_cip].strip().strip('"').strip()
        if cip in ("99", "99.0000"):
            stats["skipped_aggregate_rows"] += 1
            continue
        if modern:
            tot, nra = _num(row[i_tot]), _num(row[i_nra])
        else:
            tot = _num(row[i_tot[0]]) + _num(row[i_tot[1]])
            nra = _num(row[i_nra[0]]) + _num(row[i_nra[1]])
        if tot <= 0:
            continue
        nra = min(nra, tot)
        (seen17 if basis == "aw17" else seen9).add(unit)
        cell = agg[(unit, cip, basis)]
        cell[0] += tot
        cell[1] += nra

    fh.close()
    stats["aw9_institutions"] = len(seen9)
    stats["aw17_institutions"] = len(seen17)
    rows = [(u, c, b, v[0], v[1]) for (u, c, b), v in agg.items()]
    stats["cells"] = len(rows)
    stats["completions"] = sum(r[3] for r in rows)
    stats["nra_completions"] = sum(r[4] for r in rows)
    return rows, stats


# ---------------------------------------------------------------------------
# CIP titles
# ---------------------------------------------------------------------------

def build_cip_titles() -> dict:
    titles = {}
    try:
        import openpyxl
        wb = openpyxl.load_workbook(DICT_XLSX, read_only=True)
        ws = wb["Frequencies"]
        for row in ws.iter_rows(values_only=True):
            if not row or len(row) < 4:
                continue
            if str(row[1]).strip().upper() != "CIPCODE":
                continue
            code = str(row[2]).strip()
            label = str(row[3]).strip()
            if code and label and label != "None":
                titles[code] = label
        wb.close()
    except Exception as exc:  # pragma: no cover
        print(f"  warning: could not read CIP titles from dictionary: {exc}")
    for fam, name in CIP_FAMILIES.items():
        titles.setdefault(fam, name)
    return titles


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", type=int, default=FIRST_YEAR)
    ap.add_argument("--end", type=int, default=LAST_YEAR)
    args = ap.parse_args()

    years = [y for y in range(args.start, args.end + 1) if y in YEAR_FILES]
    per_year = {}
    total_rows = 0

    with gzip.open(OUT_INDEX, "wt", newline="", compresslevel=6) as fh:
        w = csv.writer(fh)
        w.writerow(["year", "unitid", "cipcode", "basis", "total", "nra"])
        for y in years:
            rows, stats = scan_year(y)
            if not rows:
                print(f"{y}: skipped ({stats.get('error', 'no rows')})")
                continue
            rows.sort()
            for u, c, b, t, n in rows:
                w.writerow([y, u, c, b, t, n])
            total_rows += len(rows)
            share = stats["nra_completions"] / stats["completions"] * 100
            per_year[y] = stats
            print(f"{y}: {stats['cells']:>6,} cells  {stats['completions']:>7,} doctorates  "
                  f"NRA {share:5.1f}%  [{stats['file']}]")

    titles = build_cip_titles()
    with open(OUT_CIP, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cipcode", "title"])
        for code in sorted(titles):
            w.writerow([code, titles[code]])

    meta = {
        "built": date.today().isoformat(),
        "source": "IPEDS Completions (Survey component C, part A)",
        "measure": ("NRA = IPEDS 'Nonresident alien' / 'U.S. Nonresident' reporting "
                    "category: a reported visa/residency status, not ethnicity, race, "
                    "or country of origin."),
        "population": "Research/scholarship doctorates, first majors, CIPCODE 99 excluded",
        "awlevel_rule": {
            "1995-2007": "AWLEVEL 9 (Doctor's degree; first-professional was AWLEVEL 10)",
            "2008-2009": "AWLEVEL 17 for institutions on the new scheme, AWLEVEL 9 otherwise",
            "2010+": "AWLEVEL 17 (research/scholarship)",
        },
        "cip_vintages": "CIP1990 (1995-99), CIP2000 (2000-09), CIP2010 (2010-19), CIP2020 (2020+); "
                        "6-digit codes are not fully comparable across vintages, 2-digit families are",
        "rows": total_rows,
        "years": per_year,
    }
    with open(OUT_META, "w") as fh:
        json.dump(meta, fh, indent=2)

    print(f"\nwrote {OUT_INDEX} ({total_rows:,} rows, "
          f"{os.path.getsize(OUT_INDEX)/1e6:.1f} MB)")
    print(f"wrote {OUT_CIP} ({len(titles):,} titles)")
    print(f"wrote {OUT_META}")


if __name__ == "__main__":
    main()
