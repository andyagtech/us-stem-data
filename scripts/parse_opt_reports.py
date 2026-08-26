#!/usr/bin/env python3
"""Extract DHS SEVP OPT reports into reproducible JSON.

OPT data reached this project as JSON that some earlier one-off extraction
produced. step3_parse_federal.py only ever READ it -- its comment says
"already parsed into opt_by_university.json by previous extraction" -- so
when SEVP published a new year, nothing in the repo knew how to ingest it.
This script is that missing step.

Two products, from two different kinds of report:

  opt_national.json     OPT, STEM OPT and CPT authorisations for the whole
                        country, 2007-2024. A complete national count.
  opt_by_university.json  the Top 100 school tables, 2017-2024, in both
                        flavours -- `opt` (pre- + post-completion) and
                        `stem_opt` (the 24-month STEM extension).

READ THIS BEFORE USING THE PER-SCHOOL NUMBERS. The school tables are a
TOP 100 RANKING, not a census. A school absent from a year is not a school
with zero OPT students; it is a school that placed outside the top 100 that
year. Totals across schools are therefore a floor, and a school appearing or
vanishing between years may reflect the cutoff rather than any real change.
The national table above has no such problem and should be preferred for any
published total.

Usage:
  python3 scripts/parse_opt_reports.py            # write the JSON
  python3 scripts/parse_opt_reports.py --check    # parse and report, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The reports arrived in two batches and live in two places. Scanning both
# beats moving files someone else's scripts may still reference.
PDF_DIRS = [ROOT / "data" / "h1b", ROOT / "data" / "sevp"]
PDF_DIR = PDF_DIRS[0]
OUT_UNI = PDF_DIR / "opt_by_university.json"
OUT_NAT = PDF_DIR / "opt_national.json"
OUT_EMP = PDF_DIR / "opt_employers.json"
ENTITY_MAP = ROOT / "pipeline" / "entity_map.json"

# The two report families, and the year each covers. Filenames encode the
# PUBLICATION date, not the data year -- 24_0510_...-2023-... is the 2023
# report published in 2024 -- so the year is taken from the title text, never
# from the filename.
KIND = {"prepost": "opt", "stem": "stem_opt"}

# The same national table exists under two names in two directories.
NAT_FILES = ("opt_stemopt_cpt_authorizations_2007_2024.pdf",
             "TotalNumberAnnualOPT_STEM_OPT_CPT_Authorizations"
             "WithEmpStartDatesDuringIndicatedCY2007_2024.pdf")

# "Columbia University   Columbia University in the City of New York   5,861   4,331"
ROW = re.compile(r"^(.{4,60}?)\s{2,}(.{4,60}?)\s{2,}([\d,]{1,9})\s{2,}([\d,]{1,9})\s*$")


def pdftext(path: Path) -> tuple[str, str]:
    """Text of a PDF, or ("", reason) when it cannot be read.

    Two files in this directory are 10 bytes of the ASCII text "Not found."
    saved with a .pdf extension -- a download that 404'd and was written to
    disk anyway. They look like data in a listing. Reporting the reason beats
    raising, so one bad file cannot stop the other twenty-four being parsed.
    """
    if path.stat().st_size < 1024:
        head = path.read_bytes()[:16]
        if not head.startswith(b"%PDF"):
            return "", f"not a PDF ({path.stat().st_size} bytes: {head[:12]!r})"
    r = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return "", f"pdftotext failed: {(r.stderr or '').strip().splitlines()[0][:80]}"
    return r.stdout, ""


def year_of(text: str, name: str) -> int | None:
    """The data year, from the report title rather than the filename."""
    for pat in (r"(20\d{2})\s+Top\s+100", r"Calendar\s+Year\s+(20\d{2})"):
        m = re.search(pat, text, re.I)
        if m:
            return int(m.group(1))
    m = re.search(r"-(20\d{2})-top100", name, re.I)
    return int(m.group(1)) if m else None


def kind_of(name: str, text: str) -> str | None:
    blob = f"{name} {text[:400]}".lower()
    if "stem opt" in blob or "stem-opt" in blob or "withstem" in blob:
        return "stem_opt"
    if "pre- + post" in blob or "prepost" in blob or "prepostcompletion" in blob:
        return "opt"
    return None


def parse_school_table(text: str) -> list[dict]:
    """Rows of (campus, school, students_employed, authorizations), ranked."""
    rows = []
    for line in text.splitlines():
        if not line.strip() or "Campus Name" in line or "Top 100" in line:
            continue
        m = ROW.match(line.rstrip())
        if not m:
            continue
        campus, school, a, b = m.groups()
        try:
            employed, auth = int(a.replace(",", "")), int(b.replace(",", ""))
        except ValueError:
            continue
        # A header row that happens to match, or a stray year pair.
        if employed < 10 or auth < 1:
            continue
        rows.append({"rank": len(rows) + 1, "campus": campus.strip(),
                     "school": school.strip(),
                     "students_employed": employed, "authorizations": auth})
    return rows


def parse_national(text: str) -> dict:
    """The all-country annual table: OPT, STEM OPT, CPT, and the SEVIS total.

    Parsed line by line rather than with one big regex. The first attempt used
    `^\\s*OPT\\s` with re.search and no re.M, so `^` only ever matched the start
    of the document and every row missed; and its year pattern contained a
    full-width '2', which silently dropped 2020-2024. Both failures produced an
    empty result that looked like "this PDF has no table in it".
    """
    lines = text.splitlines()
    years: list[int] = []
    for ln in lines:
        if "OPT Type" in ln:
            years = [int(y) for y in re.findall(r"\b(20\d{2})\b", ln)]
            break
    if not years:
        return {}

    def nums(ln: str) -> list[int]:
        return [int(v.replace(",", "")) for v in re.findall(r"\b[\d,]{1,12}\b", ln)
                if any(c.isdigit() for c in v)]

    out: dict[str, dict[str, int]] = {}
    pending = None   # "Total SEVIS" wraps onto the next line as "IDs w/ OPT ..."
    for ln in lines:
        stripped = ln.strip()
        key = None
        if re.match(r"^OPT\s+[\d,]", stripped):
            key = "opt"
        elif re.match(r"^STEM OPT\s+[\d,]", stripped):
            key = "stem_opt"
        elif re.match(r"^CPT\s+[\d,]", stripped):
            key = "cpt"
        elif "IDs w/" in stripped and "OPT" in stripped:
            key = "total_sevis_with_opt" if pending != "issued" else None
            pending = "issued"     # the second such row is the EAD-issued table
        if not key:
            continue
        vals = nums(stripped)
        if len(vals) < len(years):
            continue
        for y, v in zip(years, vals[-len(years):]):
            out.setdefault(str(y), {})[key] = v
    return out


def _norm(s: str) -> str:
    """Fold the spelling differences between SEVP and the entity map."""
    s = s.upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    s = re.sub(r"^\s*THE\b", " ", s)
    s = re.sub(r"\b(AT|OF|IN|THE)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


EMP_ROW = re.compile(r"^(.{2,70}?)\s{2,}([\d,]{1,9})\s{2,}([\d,]{1,9})\s{2,}([\d,]{1,9})\s*$")


def parse_employers(text: str) -> list[dict]:
    """The Top 200 employers table: three counts per row, not two.

    Reading it with the two-column school pattern picked up the wrong pair of
    numbers and produced a list that was not even in descending order -- which
    is how the mistake was noticed.
    """
    rows = []
    for line in text.splitlines():
        m = EMP_ROW.match(line.rstrip())
        if not m:
            continue
        name, tot, opt, stem = m.groups()
        try:
            tot, opt, stem = (int(v.replace(",", "")) for v in (tot, opt, stem))
        except ValueError:
            continue
        # The columns do NOT sum to the total: the report counts a student
        # once in `total` but in both programme columns if they held both.
        # So the total sits between the larger column and their sum. The
        # first attempt required opt + stem == total and threw away 96% of
        # the table, keeping only the handful of rows that happened to fit.
        if tot < 10 or not (max(opt, stem) <= tot <= opt + stem):
            continue
        rows.append({"rank": len(rows) + 1, "employer": name.strip(),
                     "total": tot, "opt": opt, "stem_opt": stem})
    return rows


def load_entity_map() -> tuple[dict, dict]:
    if not ENTITY_MAP.exists():
        return {}, {}
    raw = {k.upper(): v for k, v in json.loads(ENTITY_MAP.read_text()).items()}
    nrm: dict[str, str] = {}
    for k, v in raw.items():
        nrm.setdefault(_norm(k), v)
    return raw, nrm


def match_school(school: str, campus: str, raw: dict, nrm: dict) -> str | None:
    """Resolve a SEVP school name to a university key, or None.

    SEVP and the entity map disagree on spelling in predictable ways: a
    leading "The", a campus suffix ("... Carbondale"), an ampersand, an
    abbreviation ("& Health Sys."). Exact and normalised lookups handle most;
    the prefix pass handles the rest.

    A containment match is accepted ONLY when exactly one university matches.
    "University of Texas" is a prefix of half a dozen campuses, and guessing
    one would put another institution's students on its page -- an error
    nothing downstream could detect.
    """
    for cand in (school, campus):
        if cand and cand.upper() in raw:
            return raw[cand.upper()]
    for cand in (school, campus):
        k = nrm.get(_norm(cand or ""))
        if k:
            return k
    for cand in (school, campus):
        c = _norm(cand or "")
        if len(c) < 8:
            continue
        hits = {v for k, v in nrm.items()
                if k and (c.startswith(k + " ") or k.startswith(c + " "))}
        if len(hits) == 1:
            return hits.pop()
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="parse and report, write nothing")
    args = ap.parse_args()

    pdfs = sorted({p.name: p for d in PDF_DIRS if d.is_dir()
                   for p in d.glob("*.pdf")
                   if "opt" in p.name.lower()}.values(), key=lambda p: p.name)
    if not pdfs:
        print(f"  no OPT PDFs under {PDF_DIR}")
        return 2

    # --- national -------------------------------------------------------
    national: dict = {}
    for d in PDF_DIRS:
        for name in NAT_FILES:
            f = d / name
            if not f.exists():
                continue
            nat_text, why = pdftext(f)
            if why:
                print(f"  national table unreadable ({name}): {why}")
                continue
            parsed = parse_national(nat_text)
            if len(parsed) > len(national):
                national = parsed
        if national:
            break
    print(f"  national: {len(national)} years "
          f"({min(national, default='-')}-{max(national, default='-')})")

    # --- employers ------------------------------------------------------
    employers: list[dict] = []
    for d in PDF_DIRS:
        f = d / "2024_top200_employers_opt_stemopt.pdf"
        if f.exists():
            t, why = pdftext(f)
            if not why:
                employers = parse_employers(t)
    if employers:
        print(f"  employers: {len(employers)} (top: {employers[0]['employer']} "
              f"{employers[0]['total']:,})")

    # --- per school -----------------------------------------------------
    tables: dict[tuple[int, str], list[dict]] = {}
    skipped = []
    for pdf in pdfs:
        if pdf.name in NAT_FILES:
            continue
        text, why = pdftext(pdf)
        if why or not text.strip():
            skipped.append((pdf.name, why or "no extractable text"))
            continue
        y, k = year_of(text, pdf.name), kind_of(pdf.name, text)
        rows = parse_school_table(text)
        if not (y and k and rows):
            skipped.append((pdf.name, f"year={y} kind={k} rows={len(rows)}"))
            continue
        # A Top 100 table is a ranking: about 100 rows, ordered by students
        # employed. Short or out of order means the layout changed and the
        # rows are being read wrongly, which would put the wrong rank -- or
        # the wrong school -- on a university page.
        v = [r["students_employed"] for r in rows]
        if len(rows) < 90:
            skipped.append((pdf.name, f"only {len(rows)} rows, expected about 100"))
            continue
        if any(v[i] < v[i + 1] for i in range(len(v) - 1)):
            skipped.append((pdf.name, "rows are not in descending order"))
            continue
        # Prefer the table with more rows when two files cover the same slot
        # (2024 ships both a Top 100 and a differently-named duplicate).
        if len(rows) > len(tables.get((y, k), [])):
            tables[(y, k)] = rows

    for (y, k), rows in sorted(tables.items()):
        print(f"  {y} {k:8} {len(rows):3} schools")
    for name, why in skipped:
        print(f"  skipped {name}: {why}")

    # --- fold into per-university -------------------------------------
    raw_map, nrm_map = load_entity_map()
    uni: dict[str, dict] = {}
    unmatched: set[str] = set()
    for (y, k), rows in tables.items():
        for r in rows:
            key = match_school(r["school"], r["campus"], raw_map, nrm_map)
            if not key:
                unmatched.add(r["school"])
                continue
            uni.setdefault(key, {}).setdefault(str(y), {})[k] = {
                "students_employed": r["students_employed"],
                "authorizations": r["authorizations"],
                "rank": r["rank"],
            }
    print(f"  matched {len(uni)} universities; {len(unmatched)} school names unmatched")

    if args.check:
        return 0

    # Compare against what is already published before replacing it. This file
    # is consumed by 60 university pages; a parser change that silently drops
    # an institution would take its OPT panel with it.
    if OUT_UNI.exists():
        prev = json.loads(OUT_UNI.read_text())
        lost = sorted(set(prev) - set(uni))
        gained = sorted(set(uni) - set(prev))
        if lost:
            print(f"  REFUSING to write: would drop {len(lost)} university(ies) "
                  f"already published: {', '.join(lost[:6])}")
            return 1
        if gained:
            print(f"  adds {len(gained)}: {', '.join(gained)}")
    OUT_UNI.write_text(json.dumps(uni, indent=1, sort_keys=True) + "\n")
    print(f"  wrote {OUT_UNI.relative_to(ROOT)} ({len(uni)} universities)")

    OUT_NAT.write_text(json.dumps({
        "_comment": ("National OPT, STEM OPT and CPT authorisations by calendar "
                     "year. A complete count, unlike the Top 100 school tables. "
                     "Source: DHS SEVP."),
        "source": "DHS Student and Exchange Visitor Program (SEVP)",
        "series": national,
    }, indent=1) + "\n")
    print(f"  wrote {OUT_NAT.relative_to(ROOT)}")

    if employers:
        OUT_EMP.write_text(json.dumps({
            "_comment": ("Top 200 employers of OPT and STEM OPT students, "
                         "calendar year 2024. `total` counts a student once per "
                         "programme, so a student on both OPT and STEM OPT at "
                         "one employer appears in both columns."),
            "source": "DHS SEVP, 2024 Top 200 Employers for OPT and STEM-OPT Students",
            "year": 2024,
            "employers": employers,
        }, indent=1) + "\n")
        print(f"  wrote {OUT_EMP.relative_to(ROOT)} ({len(employers)} employers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
