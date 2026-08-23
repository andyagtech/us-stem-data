"""
Step 3: PARSE_FEDERAL — Parse all federal data sources into processed JSONs.

Pure transforms: raw CSV/XLSX/PDF → processed JSON aggregates.

Input:  data/h1b/*.csv (H-1B hub), data/h1b/lca/*.xlsx (LCA),
        data/h1b/opt_by_school.json (OPT PDFs already extracted),
        data/h1b/perm_*.xlsx (PERM), data/ipeds/*.csv, data/herd/*.xlsx, data/gss/*.csv
Output: data/h1b/h1b_by_university.json, data/h1b/lca_by_university.json,
        data/h1b/opt_by_university.json, data/h1b/perm_by_university.json,
        data/h1b/lca_legal_by_university.json  (law firms and attorneys)

LCA notes, because they are the fiddly part:
  * Files are read ONE AT A TIME with their own header. A single read_csv()
    over the glob with union_by_name made DuckDB mis-sniff the older layouts
    and silently drop five whole files. See data/h1b/LCA_ARCHIVE.md.
  * Rows are deduplicated on the case number. DOL's quarterly files overlap
    inconsistently, so add every file DOL publishes and never delete one that
    looks superseded.
  * Legal-representation fields are OPTIONAL: coverage starts at FY2015 for
    the attorney and FY2020 for the firm, and FY2013 has none.
"""
from __future__ import annotations
import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .state import PipelineState, StepOutcome


def _load_entity_map(base_dir: Path) -> dict[str, str]:
    """Load employer name → university key mappings."""
    with open(base_dir / "pipeline" / "entity_map.json") as f:
        return json.load(f)


_WORD_RE_CACHE: dict[str, "re.Pattern"] = {}


def _match_employer(name: str, entity_map: dict[str, str]) -> str | None:
    """Match an employer name to a university key using entity map.

    Substring matching used to be a bare `pattern in upper`, which is unsafe
    for short patterns: the entry "MIT" matched WIPRO LIMITED, INFOSYS
    LIMITED, TATA CONSULTANCY SERVICES LIMITED and 166 other employers with
    those three letters anywhere inside a word. MIT's LCA total read 565,883
    against a corpus median of 1,035 — it had absorbed the largest H-1B filers
    in the country.

    Patterns must now match on word boundaries, so "MIT" matches the employer
    MIT but not LIMITED, SMITH or SUMMIT.
    """
    upper = (name or "").upper().strip()
    if not upper:
        return None
    # Exact match first; unambiguous and cheapest.
    if upper in entity_map:
        return entity_map[upper]
    # Then word-boundary substring match. Longest pattern first, so a specific
    # campus name wins over a shorter system name that is a prefix of it.
    for pattern in sorted(entity_map, key=len, reverse=True):
        rx = _WORD_RE_CACHE.get(pattern)
        if rx is None:
            rx = _WORD_RE_CACHE[pattern] = re.compile(
                r"\b" + re.escape(pattern) + r"\b")
        if rx.search(upper):
            return entity_map[pattern]
    return None


def _parse_h1b_files(base_dir: Path, entity_map: dict) -> dict:
    """Parse all H-1B Data Hub CSV files into aggregated data."""
    h1b = defaultdict(lambda: defaultdict(lambda: {
        "initial_approvals": 0, "initial_denials": 0,
        "continuing_approvals": 0, "continuing_denials": 0,
    }))

    h1b_dir = base_dir / "data" / "h1b"
    for fn in sorted(os.listdir(h1b_dir)):
        if not fn.startswith("h1b_datahub") or not fn.endswith(".csv") or "checkthis" in fn:
            continue
        path = h1b_dir / fn

        with open(path, "rb") as f:
            raw = f.read(4)

        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            # UTF-16 Crosstab format
            with open(path, encoding="utf-16") as f:
                reader = csv.reader(f, delimiter="\t")
                next(reader)  # skip header
                for row in reader:
                    if len(row) < 10:
                        continue
                    emp, fy = row[2].strip(), row[1].strip()
                    key = _match_employer(emp, entity_map)
                    if not key or not fy:
                        continue
                    try:
                        h1b[key][fy]["initial_approvals"] += int(float(row[8])) if row[8] else 0
                        h1b[key][fy]["initial_denials"] += int(float(row[9])) if row[9] else 0
                        h1b[key][fy]["continuing_approvals"] += int(float(row[10])) if row[10] else 0
                        h1b[key][fy]["continuing_denials"] += int(float(row[11])) if row[11] else 0
                    except (ValueError, IndexError):
                        continue
        else:
            # Check for HTML (anti-bot page)
            with open(path, encoding="utf-8-sig") as f:
                first = f.read(20)
            if "<!DOCTYPE" in first or "<html" in first:
                continue
            # Standard CSV
            with open(path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                cols = reader.fieldnames or []
                ia = "Initial Approvals" if "Initial Approvals" in cols else "Initial Approval"
                id_ = "Initial Denials" if "Initial Denials" in cols else "Initial Denial"
                ca = "Continuing Approvals" if "Continuing Approvals" in cols else "Continuing Approval"
                cd = "Continuing Denials" if "Continuing Denials" in cols else "Continuing Denial"
                for row in reader:
                    emp = (row.get("Employer", "") or "").strip()
                    fy = (row.get("Fiscal Year", "") or "").strip()
                    key = _match_employer(emp, entity_map)
                    if not key:
                        continue
                    try:
                        h1b[key][fy]["initial_approvals"] += int(row.get(ia, 0) or 0)
                        h1b[key][fy]["initial_denials"] += int(row.get(id_, 0) or 0)
                        h1b[key][fy]["continuing_approvals"] += int(row.get(ca, 0) or 0)
                        h1b[key][fy]["continuing_denials"] += int(row.get(cd, 0) or 0)
                    except (ValueError, TypeError):
                        continue

    return {k: {fy: counts for fy, counts in sorted(v.items()) if fy} for k, v in h1b.items()}


def _strip_excel_formula(v: str) -> str:
    """DOL ships some cells as the literal ="VALUE". Unwrap to VALUE."""
    t = v.strip()
    if t.startswith('="') and t.endswith('"'):
        t = t[2:-1]
    return t


def _normalize_soc(code: str, name: str) -> tuple[str, str]:
    """Split a SOC cell into (code, name), normalising the code only.

    DOL's layouts disagree on both halves. Newer files write '25-1032.00';
    older ones '25-1032'. Only the '.00' suffix is dropped -- it denotes the
    base occupation, while the '.01'/'.02' detail codes are genuinely
    different occupations and must survive.

    The NAME is deliberately left alone. It varies in ways no case rule fixes
    -- 'Biochemists and Biophysicists' vs 'Biochemists And Biophysicists', and
    truncations like 'Foreign Language And Literature Teachers,'. Counting is
    keyed on the code, which is the real identifier; _best_soc_name() picks
    one spelling for display.
    """
    c = _strip_excel_formula(code)
    if c.endswith(".00"):
        c = c[:-3]
    return c, _strip_excel_formula(name)


_SOC_SMALL_WORDS = {"and", "or", "of", "the", "in", "for", "to", "a", "an",
                    "with", "on", "at", "nec"}


def _display_case(name: str) -> str:
    """Title-case an all-caps occupation name for display.

    Only applied when the source is entirely upper case: DOL's newer files
    already ship mixed case and re-casing those would corrupt forms like R&D.
    str.title() alone gives 'Biochemists And Biophysicists', so the small
    words are lowered again -- except in first position.
    """
    if not name.isupper():
        return name
    words = name.title().split(" ")
    out = [words[0]] + [w.lower() if w.lower() in _SOC_SMALL_WORDS else w
                        for w in words[1:]]
    return " ".join(out)


def _best_soc_name(names: dict, code: str) -> str:
    """The name to show for a SOC code: the most common, then the longest.

    Length breaks the tie because the short variant is usually a truncation.
    """
    counter = names.get(code)
    if not counter:
        return ""
    best = max(counter.items(), key=lambda kv: (kv[1], len(kv[0]), kv[0]))[0]
    return _display_case(best)


def _normalize_job_title(title: str) -> str:
    """Normalize H-1B job titles to remove duplicates and Excel artifacts."""
    t = _strip_excel_formula(title)
    # Normalize whitespace
    t = " ".join(t.split())
    # Normalize common variants
    t = t.title()
    # Merge postdoc variants
    t = re.sub(r"Post[\s-]*Doctoral", "Postdoctoral", t)
    t = re.sub(r"Post[\s-]*Doc\b", "Postdoc", t)
    # Merge "Assistant Professor Of X" → "Assistant Professor"
    # (keep the specific ones but group the generic)
    return t


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Write via a temp file and rename, so a crash cannot leave a half file."""
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
    os.replace(tmp, path)


# Read every CSV with its OWN header and project it onto one canonical
# schema. This replaces a single read_csv() over a glob with
# union_by_name=true + auto_detect=true + ignore_errors=true, which was
# silently corrupting the data: DOL's layouts range from 35 to 260
# columns, and across that spread DuckDB mis-sniffed the header on the
# older files, so the union came back with 506 columns whose names were
# DATA VALUES ('I-200-09121-701936', 'WITHDRAWN', '"MEDTRONIC', 'INC."').
# Those files then had a NULL CASE_NUMBER for every row and were dropped
# wholesale by the dedup -- five files and 1.6M rows contributing nothing,
# with no error raised. Reading one homogeneous file at a time removes the
# cross-schema sniffing entirely.
#
# Column names also drift across layouts, so each canonical field lists
# its aliases newest-first. Matching is EXACT (case-insensitive), never
# substring: the modern layout carries both JOB_TITLE and
# EMPLOYER_POC_JOB_TITLE, and a substring match can pick the contact
# person's job title instead of the worker's.
CANON: dict[str, tuple[str, ...]] = {
    "case_number":   ("CASE_NUMBER", "LCA_CASE_NUMBER", "CASE_NO"),
    "case_status":   ("CASE_STATUS", "STATUS", "APPROVAL_STATUS"),
    # FY2008 calls the employer column simply NAME. It is last so that a
    # layout carrying both always resolves to the explicit one.
    "employer_name": ("EMPLOYER_NAME", "LCA_CASE_EMPLOYER_NAME", "NAME"),
    "job_title":     ("JOB_TITLE", "LCA_CASE_JOB_TITLE"),
    "soc_code":      ("SOC_CODE", "LCA_CASE_SOC_CODE"),
    "soc_name":      ("SOC_NAME", "SOC_TITLE", "LCA_CASE_SOC_NAME"),
    # FY2015/16 name this WAGE_RATE_OF_PAY with no _FROM suffix; the old
    # substring lookup for "WAGE_RATE_OF_PAY_FROM" never matched it, so
    # those years contributed no wages at all.
    # FY2019's 260-column layout repeats the wage block per worksite as
    # WAGE_RATE_OF_PAY_FROM_1..n; _1 is the primary worksite.
    "wage_from":     ("WAGE_RATE_OF_PAY_FROM", "WAGE_RATE_OF_PAY_FROM_1",
                      "WAGE_RATE_OF_PAY", "LCA_CASE_WAGE_RATE_FROM",
                      "WAGE_RATE_1"),
    "wage_unit":     ("WAGE_UNIT_OF_PAY", "WAGE_UNIT_OF_PAY_1",
                      "LCA_CASE_WAGE_RATE_UNIT", "RATE_PER_1"),
    # No DOL layout carries a fiscal-year column, so these are CALENDAR
    # years. FY2013 has no DECISION_DATE and falls back to the submit date.
    "decision_date": ("DECISION_DATE", "LCA_CASE_SUBMIT", "DOL_DECISION_DATE"),
}

# SOC did not exist in this dataset before FY2010. The FY2008 and FY2009
# files carry JOB_CODE / OCCUPATIONAL_CODE, which are DOT/OES-era codes on
# a different taxonomy -- 30 for "systems analysis", 76 for "therapists".
# Aliasing those to soc_code would silently blend two incompatible coding
# schemes into one occupation column, so they are left NULL and the
# required-field guard is waived for exactly these two fields on exactly
# these files. Everything else about them is still required.
PRE_SOC_LAYOUTS = {"lca_H-1B_Case_Data_FY2008.csv",
                   "lca_H-1B_Case_Data_FY2009.csv"}
PRE_SOC_FIELDS = {"soc_code", "soc_name"}

# FY2010 states the offered wage (LCA_CASE_WAGE_RATE_FROM) but publishes no
# unit for it. The file does carry PW_UNIT_1, which is the unit of the
# PREVAILING wage -- a different field for a different number. Aliasing it
# in would be a guess dressed as data, the same mistake as folding a DOT
# code into soc_code, so the unit is left NULL.
#
# The consequence is contained: a missing unit defaults to annual, so
# genuinely annual wages parse correctly and an hourly or weekly figure
# falls outside the 20k-500k sanity range and is dropped. FY2010
# contributes fewer wages, never wrong ones.
NO_WAGE_UNIT_LAYOUTS = {"lca_H-1B_FY2010.csv"}
NO_WAGE_UNIT_FIELDS = {"wage_unit"}

# Legal representation. OPTIONAL, unlike CANON: FY2013 carries no legal
# fields at all, FY2015-19 only a combined AGENT_ATTORNEY_NAME with city
# and state, and the law firm's own name does not appear until FY2020.
# Making these required would fail the whole build on layouts that simply
# predate the disclosure, so an absent one becomes NULL and is reported
# rather than fatal.
#
# Attorney email and phone ARE collected. They are part of the public DOL
# disclosure and identify the filer, which is the point of the dataset.
# They land in data/h1b/, which is not deployed -- the site publishes only
# what is under site/ -- so retrieval and display stay separate decisions.
OPTIONAL: dict[str, tuple[str, ...]] = {
    "attorney_last":  ("AGENT_ATTORNEY_LAST_NAME",),
    "attorney_first": ("AGENT_ATTORNEY_FIRST_NAME",),
    "attorney_full":  ("AGENT_ATTORNEY_NAME",),
    "attorney_city":  ("AGENT_ATTORNEY_CITY",),
    "attorney_state": ("AGENT_ATTORNEY_STATE",),
    "lawfirm_name":   ("LAWFIRM_NAME_BUSINESS_NAME",),
    "lawfirm_fein":   ("LAWFIRM_BUSINESS_FEIN",),
    "attorney_email": ("AGENT_ATTORNEY_EMAIL_ADDRESS",),
    "attorney_phone": ("AGENT_ATTORNEY_PHONE",),
    "attorney_city2": ("AGENT_ATTORNEY_ADDRESS1",),
    "has_agent":      ("AGENT_REPRESENTING_EMPLOYER",),
}


def _canon_for_preflight() -> tuple[dict[str, tuple[str, ...]], dict[str, set[str]]]:
    """The required schema and its per-file exemptions.

    _parse_lca_duckdb() only discovers an unmappable layout AFTER the CSV
    conversion -- on the full archive that is twenty minutes of work thrown
    away over one unknown column name. A caller can resolve the workbook
    headers against this first and fail in seconds. These are the very objects
    the parser uses, not copies, so the two cannot drift apart.
    """
    exempt: dict[str, set[str]] = {}
    for f in PRE_SOC_LAYOUTS:
        exempt.setdefault(f, set()).update(PRE_SOC_FIELDS)
    for f in NO_WAGE_UNIT_LAYOUTS:
        exempt.setdefault(f, set()).update(NO_WAGE_UNIT_FIELDS)
    return CANON, exempt


def _parse_lca_files(base_dir: Path, entity_map: dict) -> dict:
    """Parse LCA disclosure Excel files.

    DuckDB only: see the comment below on why there is no fallback.
    """
    lca_dir = base_dir / "data" / "h1b" / "lca"
    if not lca_dir.exists():
        return {}

    # There is deliberately no fallback parser. The openpyxl one that used to
    # sit here did not deduplicate at all, so it summed DOL's overlapping
    # quarterly files -- and it was reached by `except Exception`, which meant
    # the guards in _parse_lca_duckdb() against dropped files would have been
    # swallowed and answered with an inflated, double-counted total instead.
    # A loud failure is the correct outcome; duckdb is a pinned dependency.
    try:
        import duckdb  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "duckdb is required to parse LCA data and is not installed. "
            "Install it rather than publishing LCA totals that double-count "
            "DOL's overlapping quarterly files.") from e

    result = _parse_lca_duckdb(lca_dir, entity_map)
    if result is None:
        return {}

    # The legal-representation aggregate rides along on the same DuckDB pass
    # (re-parsing 6GB of CSV to get it separately would be wasteful), but it is
    # a different dataset with a different shape and different coverage, so it
    # is split out to its own file here. Every caller of this function expects
    # a dict keyed by university and nothing else.
    legal = result.pop("_legal", None)
    if legal is not None:
        out = base_dir / "data" / "h1b" / "lca_legal_by_university.json"
        _atomic_write_json(out, legal)
        m = legal["_meta"]
        print(f"    LCA legal: {m['distinct_firms']:,} firms, "
              f"{m['distinct_attorneys']:,} attorneys over "
              f"{m['rows_with_a_named_firm']:,} rows -> {out.name}")
    return result


def _parse_lca_duckdb(lca_dir: Path, entity_map: dict) -> dict | None:
    """Fast LCA parsing via DuckDB — reads CSVs converted from XLSX.

    Phase 1: Convert XLSX → CSV if not already done (one-time cost).
    Phase 2: Query all CSVs with SQL for aggregation.
    """
    import duckdb

    csv_dir = lca_dir / "csv_cache"
    xlsx_files = sorted(f for f in os.listdir(lca_dir) if f.endswith(".xlsx"))
    if not xlsx_files:
        return None

    # Phase 1: Convert any missing XLSX → CSV
    need_convert = []
    for xlsx in xlsx_files:
        csv_name = xlsx.replace(".xlsx", ".csv")
        csv_path = csv_dir / csv_name
        if not csv_path.exists():
            need_convert.append(xlsx)

    if need_convert:
        csv_dir.mkdir(exist_ok=True)
        print(f"  LCA: converting {len(need_convert)} XLSX → CSV (one-time)...")
        try:
            import openpyxl
        except ImportError:
            # Returning None here used to mean "no LCA data" and the step
            # still reported success. A missing dependency is a broken
            # environment, not an empty dataset.
            raise RuntimeError(
                "openpyxl is required to convert LCA XLSX files and is not "
                "installed. Install it rather than shipping empty LCA data.")

        for fname in need_convert:
            xlsx_path = lca_dir / fname
            csv_path = csv_dir / fname.replace(".xlsx", ".csv")
            try:
                wb = openpyxl.load_workbook(str(xlsx_path), read_only=True)
                ws = wb.active
                with open(csv_path, "w", newline="", encoding="utf-8") as cf:
                    writer = csv.writer(cf)
                    for row in ws.iter_rows(values_only=True):
                        cells = [str(c) if c is not None else "" for c in row]
                        # openpyxl iterates to the sheet's DECLARED dimension,
                        # which DOL's files overstate badly -- FY2025_Q1 yields
                        # 1,042,871 rows of which 935,457 are entirely empty.
                        # Writing them bloats the cache and slows every later
                        # scan; they carry nothing.
                        if not any(c.strip() for c in cells):
                            continue
                        writer.writerow(cells)
                wb.close()
                print(f"    Converted {fname}", flush=True)
            except Exception as e:
                print(f"    ERROR converting {fname}: {e}")
                if csv_path.exists():
                    csv_path.unlink()

    csv_files = sorted(csv_dir.glob("*.csv"))
    if not csv_files:
        return None

    print(f"  LCA: querying {len(csv_files)} CSVs with DuckDB...")

    # Build employer name lookup table for DuckDB
    con = duckdb.connect()

    # Create entity map table
    entity_rows = [(name, key) for name, key in entity_map.items()]
    con.execute("CREATE TABLE entity_map (employer_name VARCHAR, uni_key VARCHAR)")
    con.executemany("INSERT INTO entity_map VALUES (?, ?)", entity_rows)


    def read_header(path: Path) -> list[str]:
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            return next(csv.reader(fh), [])

    selects, layouts, no_key = [], {}, []
    for cpath in csv_files:
        header = read_header(cpath)
        lookup = {h.strip().upper(): h for h in header if h and h.strip()}
        parts, resolved = [f"'{cpath.name}' AS source_file"], {}
        for canon, aliases in {**CANON, **OPTIONAL}.items():
            actual = next((lookup[a] for a in aliases if a in lookup), None)
            resolved[canon] = actual
            # Qualify with the table alias: DuckDB matches identifiers
            # case-insensitively, so a bare "CASE_NUMBER" AS case_number reads
            # as a self-reference to the alias and fails to bind.
            # A bare NULL types as INT32, and COALESCE(int_null, '') then
            # fails to convert. Every projected column is VARCHAR here.
            parts.append(f'src."{actual}" AS {canon}' if actual
                         else f"CAST(NULL AS VARCHAR) AS {canon}")
        # EVERY canonical field must resolve, not just the key ones. FY2019
        # names its wage columns WAGE_RATE_OF_PAY_FROM_1; before that alias
        # existed the file matched on case number and employer, passed the
        # key check, and silently contributed no wages at all. That is the
        # same class of loss as a dropped file, just harder to notice.
        # Only the REQUIRED fields are fatal; an OPTIONAL one may be absent
        # on an older layout, which is a fact about DOL, not a defect.
        exempt: set[str] = set()
        if cpath.name in PRE_SOC_LAYOUTS:
            exempt |= PRE_SOC_FIELDS
        if cpath.name in NO_WAGE_UNIT_LAYOUTS:
            exempt |= NO_WAGE_UNIT_FIELDS
        unresolved = [c for c in CANON
                      if not resolved.get(c) and c not in exempt]
        if exempt:
            print(f"    {cpath.name}: layout predates "
                  f"{', '.join(sorted(exempt))}; left unmapped")
        if unresolved:
            no_key.append((cpath.name, unresolved))
        layouts.setdefault(len(header), []).append(cpath.name)
        selects.append(
            f"SELECT {', '.join(parts)} FROM read_csv('{cpath.as_posix()}', "
            "header=true, all_varchar=true, ignore_errors=true) AS src")

    print(f"    LCA: {len(csv_files)} files across "
          f"{len(layouts)} layouts ({sorted(layouts)} columns)")

    if no_key:
        # Previously this was the silent failure mode. Publishing a total that
        # omits whole files is worse than publishing nothing.
        detail = "; ".join(f"{n} -> {', '.join(f)}" for n, f in no_key)
        raise RuntimeError(
            "LCA files with unrecognised columns for these canonical fields: "
            f"{detail}. Add the layout's column names to CANON in "
            "_parse_lca_duckdb rather than letting the data be dropped.")

    # A TABLE, not a VIEW: the rows are scanned three times below (per-file
    # audit, dedup, employer join) and a view re-parses every CSV each time.
    con.execute("CREATE TABLE lca_raw AS " + " UNION ALL ".join(selects))

    # Every file must contribute keyed rows. A file that parses to zero is the
    # exact defect this rewrite exists to catch, so fail loudly on it.
    per_file = con.execute("""
        SELECT source_file, COUNT(*), COUNT(case_number)
        FROM lca_raw GROUP BY 1 ORDER BY 1
    """).fetchall()
    empty = [f for f, _n, k in per_file if k == 0]
    if empty:
        raise RuntimeError(
            f"{len(empty)} LCA file(s) parsed to zero keyed rows: "
            f"{', '.join(empty)}. Refusing to publish a partial total.")

    raw_rows = sum(n for _f, n, _k in per_file)
    keyed = sum(k for _f, _n, k in per_file)
    print(f"    LCA: {raw_rows:,} rows read, {keyed:,} carry a case number")

    # ---- DEDUPLICATE BY CASE NUMBER -------------------------------------
    # DOL's quarterly files OVERLAP, and not consistently. Within FY2021 alone,
    # by their own DECISION_DATE spans:
    #
    #   lca_fy2021_Q1   2020-10-01 -> 2020-12-31   one quarter
    #   lca_fy2021_Q3   2020-10-01 -> 2021-03-25   cumulative, and only to March
    #   lca_fy2021_Q4   2021-07-01 -> 2021-09-30   one quarter
    #
    # The file names do not describe the contents, so neither summing nor
    # last-file-wins is correct. Deduplicating on the case number is robust to
    # all of it: one row per LCA, whichever files it appears in. See
    # data/h1b/LCA_ARCHIVE.md -- never delete a file that looks superseded.
    con.execute("""
        CREATE TABLE lca_dedup AS SELECT * EXCLUDE (_rn) FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY case_number ORDER BY source_file DESC) AS _rn
            FROM lca_raw WHERE case_number IS NOT NULL
        ) WHERE _rn = 1
    """)
    unique = con.execute("SELECT COUNT(*) FROM lca_dedup").fetchone()[0]
    dropped = keyed - unique
    print(f"    LCA dedup on case_number: {keyed:,} keyed rows -> {unique:,} "
          f"unique ({dropped:,} duplicates, {100*dropped/keyed:.1f}%)")

    # Match employers. Exact equality on the trimmed, upper-cased name: an
    # earlier substring match let the three-letter pattern 'MIT' sweep in
    # INFOSYS LIMITED and every other employer containing those letters.
    con.execute("""
        CREATE TABLE matched AS
        SELECT e.uni_key,
               COALESCE(l.case_status, '')   AS case_status,
               COALESCE(l.job_title, '')     AS job_title,
               COALESCE(l.soc_code, '')      AS soc_code,
               COALESCE(l.soc_name, '')      AS soc_name,
               COALESCE(l.wage_from, '')     AS wage_str,
               COALESCE(l.wage_unit, '')     AS wage_unit,
               COALESCE(l.decision_date, '') AS fy_str,
               COALESCE(l.lawfirm_name, '')   AS lawfirm_name,
               COALESCE(l.attorney_full, '')  AS attorney_full,
               COALESCE(l.attorney_last, '')  AS attorney_last,
               COALESCE(l.attorney_first, '') AS attorney_first,
               COALESCE(l.attorney_city, '')  AS attorney_city,
               COALESCE(l.attorney_state, '') AS attorney_state,
               COALESCE(l.has_agent, '')      AS has_agent,
               COALESCE(l.attorney_email, '') AS attorney_email,
               COALESCE(l.attorney_phone, '') AS attorney_phone,
               COALESCE(l.lawfirm_fein, '')   AS lawfirm_fein,
               COALESCE(l.attorney_city2, '') AS attorney_addr
        FROM lca_dedup l
        JOIN entity_map e ON UPPER(TRIM(l.employer_name)) = e.employer_name
    """)
    total_matched = con.execute("SELECT COUNT(*) FROM matched").fetchone()[0]
    print(f"    Total matched rows: {total_matched:,}")

    # Fetch matched data for Python-side aggregation
    # (DuckDB's SQL handles the join; Python handles title normalization + wage conversion)
    lca_by_uni = defaultdict(lambda: {
        "job_titles": Counter(), "soc_codes": Counter(),
        "soc_names": defaultdict(Counter), "wages": [],
        "title_wages": defaultdict(list),
        "yearly_certified": defaultdict(int), "yearly_total": defaultdict(int),
    })

    batch_size = 100_000
    offset = 0
    while True:
        rows = con.execute(f"""
            SELECT uni_key, case_status, job_title, soc_code, soc_name,
                   wage_str, wage_unit, fy_str
            FROM matched
            LIMIT {batch_size} OFFSET {offset}
        """).fetchall()

        if not rows:
            break

        for uni_key, status, title, soc, soc_name, wage_str, wage_unit, fy_str in rows:
            d = lca_by_uni[uni_key]

            norm_title = _normalize_job_title(title)[:60] if title else ""
            if norm_title:
                d["job_titles"][norm_title] += 1
            if soc:
                # Same Excel artifact as job titles: without this, ="25-1032.00"
                # and 25-1032.00 are two entries for one occupation.
                code, sname = _normalize_soc(soc, soc_name or "")
                d["soc_codes"][code] += 1
                if sname:
                    d["soc_names"][code][sname] += 1

            # Convert wage
            wage = None
            if wage_str:
                try:
                    w = float(wage_str)
                    unit = (wage_unit or "YEAR").upper()
                    if "HOUR" in unit: w *= 2080
                    elif "WEEK" in unit: w *= 52
                    elif "MONTH" in unit: w *= 12
                    if 20000 < w < 500000:
                        wage = int(w)
                except (ValueError, TypeError):
                    pass

            if wage:
                d["wages"].append(wage)
                if norm_title:
                    d["title_wages"][norm_title].append(wage)

            # Extract year
            year = None
            if fy_str and len(fy_str) >= 4:
                try:
                    year = int(fy_str[:4])
                except ValueError:
                    pass
            if year:
                d["yearly_total"][year] += 1
                if "CERTIFIED" in (status or "").upper():
                    d["yearly_certified"][year] += 1

        offset += batch_size

    legal = _aggregate_legal(con)

    con.close()
    result = _finalize_lca(lca_by_uni)
    # Stashed rather than returned: _parse_lca_files()'s contract is one dict
    # keyed by university, and every caller relies on that shape.
    result["_legal"] = legal
    return result


def _top_n(counter, n: int = 10) -> list:
    """Top n by count, ties broken alphabetically so the output is stable."""
    return [[k, c] for k, c in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def _clean_firm(name: str) -> str:
    """Normalise a law-firm name enough to group the same firm together.

    DOL takes these as free text from the filer, so one firm arrives many
    ways: trailing punctuation, doubled spaces, and the usual suffix soup
    (LLP / L.L.P. / PLLC / P.C.). Case is folded to title case for display.
    """
    t = _strip_excel_formula(name)
    t = " ".join(t.split()).strip(" ,.;-")
    if not t:
        return ""
    up = t.upper()
    for junk in ("N/A", "NA", "NONE", "NOT APPLICABLE", "-", "."):
        if up == junk:
            return ""
    # Fold the punctuation variants of the common suffixes.
    up = re.sub(r"\bL\.L\.P\.?", "LLP", up)
    up = re.sub(r"\bP\.L\.L\.C\.?", "PLLC", up)
    up = re.sub(r"\bP\.C\.?\b", "PC", up)
    up = re.sub(r"\bL\.L\.C\.?", "LLC", up)
    up = re.sub(r"[.,]+$", "", up).strip()
    return up


def _aggregate_legal(con) -> dict:
    """Who files the LCAs: law firms, attorneys, and self-filing.

    Coverage is uneven by design of the source, not by choice here. FY2013
    carries no legal fields at all; FY2015-19 give a single combined attorney
    name with city and state; the law firm's own name only appears from
    FY2020. So firm-level figures describe FY2020 onward, and attorney-level
    ones reach back to FY2015. Both are reported with their own denominators
    so neither is mistaken for a share of the whole corpus.
    """
    rows = con.execute("""
        SELECT uni_key, lawfirm_name, attorney_full, attorney_last,
               attorney_first, attorney_state, has_agent, fy_str,
               attorney_email, attorney_phone, lawfirm_fein, attorney_addr
        FROM matched
    """).fetchall()

    per = defaultdict(lambda: {
        "firms": Counter(), "attorneys": Counter(), "states": Counter(),
        "with_firm": 0, "with_attorney": 0, "self_filed": 0, "rows": 0})
    nat_firms, nat_attys = Counter(), Counter()
    firm_years = defaultdict(Counter)
    # A directory of the filers themselves, keyed by attorney. Contact details
    # come straight from the public disclosure; each is kept with the count of
    # how often it appears, since a filer's address changes over a decade.
    attorney_dir: dict = defaultdict(lambda: {
        "filings": 0, "emails": Counter(), "phones": Counter(),
        "firms": Counter(), "states": Counter(), "addresses": Counter(),
        "universities": Counter(), "years": Counter()})
    firm_dir: dict = defaultdict(lambda: {
        "filings": 0, "feins": Counter(), "attorneys": Counter(),
        "states": Counter(), "universities": Counter()})

    for (uni, firm, full, last, first, state, agent, fy,
         email, phone, fein, addr) in rows:
        d = per[uni]
        d["rows"] += 1
        f = _clean_firm(firm or "")
        if f:
            d["firms"][f] += 1
            nat_firms[f] += 1
            d["with_firm"] += 1
            y = fy[:4] if fy and len(fy) >= 4 and fy[:4].isdigit() else None
            if y:
                firm_years[f][int(y)] += 1
        # The split pair is FY2020+; the combined field is FY2015-19.
        name = (f"{(last or '').strip()}, {(first or '').strip()}".strip(" ,")
                if (last or first) else _strip_excel_formula(full or ""))
        name = " ".join(name.split()).strip(" ,")
        if name:
            disp = name.title()
            d["attorneys"][disp] += 1
            nat_attys[disp] += 1
            d["with_attorney"] += 1
            a = attorney_dir[disp]
            a["filings"] += 1
            a["universities"][uni] += 1
            e = _strip_excel_formula(email or "").strip().lower()
            if e and "@" in e:
                a["emails"][e] += 1
            ph = re.sub(r"\D", "", _strip_excel_formula(phone or ""))
            if len(ph) >= 10:
                a["phones"][ph] += 1
            if f:
                a["firms"][f] += 1
            ad = " ".join(_strip_excel_formula(addr or "").split())
            if ad:
                a["addresses"][ad] += 1
            st_a = (state or "").strip().upper()
            if len(st_a) == 2:
                a["states"][st_a] += 1
            if fy and len(fy) >= 4 and fy[:4].isdigit():
                a["years"][int(fy[:4])] += 1
        if f:
            fd = firm_dir[f]
            fd["filings"] += 1
            fd["universities"][uni] += 1
            fe = re.sub(r"\D", "", _strip_excel_formula(fein or ""))
            if fe:
                fd["feins"][fe] += 1
            if name:
                fd["attorneys"][name.title()] += 1
            st_f = (state or "").strip().upper()
            if len(st_f) == 2:
                fd["states"][st_f] += 1
        if (agent or "").strip().upper() in ("N", "NO", "FALSE", "0"):
            d["self_filed"] += 1
        st = (state or "").strip().upper()
        if len(st) == 2:
            d["states"][st] += 1

    universities = {}
    for uni, d in per.items():
        universities[uni] = {
            "rows": d["rows"],
            "with_named_firm": d["with_firm"],
            "with_named_attorney": d["with_attorney"],
            "self_filed": d["self_filed"],
            "top_firms": _top_n(d["firms"]),
            "top_attorneys": _top_n(d["attorneys"]),
            "attorney_states": _top_n(d["states"], 5),
        }

    total_firm_rows = sum(nat_firms.values())
    top = _top_n(nat_firms, 25)

    def pick(c: Counter, n: int = 3) -> list:
        return [[k, v] for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]

    attorneys = {
        name: {
            "filings": a["filings"],
            "emails": pick(a["emails"]),
            "phones": pick(a["phones"]),
            "firms": pick(a["firms"]),
            "states": pick(a["states"], 2),
            "addresses": pick(a["addresses"], 2),
            "universities": pick(a["universities"], 8),
            "first_year": min(a["years"]) if a["years"] else None,
            "last_year": max(a["years"]) if a["years"] else None,
        }
        for name, a in attorney_dir.items()
    }
    firms = {
        f: {
            "filings": v["filings"],
            "feins": pick(v["feins"], 2),
            "states": pick(v["states"], 3),
            "attorneys": pick(v["attorneys"], 10),
            "universities": pick(v["universities"], 10),
        }
        for f, v in firm_dir.items()
    }
    with_email = sum(1 for a in attorneys.values() if a["emails"])
    return {
        "_meta": {
            "source": "US DOL OFLC LCA disclosure files",
            "coverage": ("Law-firm name is present from FY2020 only; attorney "
                         "name from FY2015; FY2013 carries no legal fields."),
            "rows_matched_to_a_university": len(rows),
            "rows_with_a_named_firm": total_firm_rows,
            "distinct_firms": len(nat_firms),
            "distinct_attorneys": len(nat_attys),
            "attorneys_with_an_email": with_email,
            "note": ("Contact details are taken from the public DOL "
                     "disclosure. This file lives under data/ and is NOT "
                     "deployed; only site/ is published."),
        },
        "national_top_firms": top,
        "firm_by_year": {f: dict(sorted(firm_years[f].items()))
                         for f, _ in top},
        "firms": firms,
        "attorneys": attorneys,
        "universities": universities,
    }


def _finalize_lca(lca_by_uni: dict) -> dict:
    """Convert raw LCA aggregation dicts into serializable summary."""
    result = {}
    for key, data in lca_by_uni.items():
        wages = sorted(data["wages"])
        n = len(wages)
        # Per-title wage stats
        title_stats = {}
        for title, tw in data.get("title_wages", {}).items():
            if len(tw) >= 3:
                sw = sorted(tw)
                tn = len(sw)
                title_stats[title] = {
                    "count": tn,
                    "min": sw[0],
                    "max": sw[-1],
                    "median": sw[tn // 2],
                    "avg": int(sum(sw) / tn),
                }

        result[key] = {
            "total_lcas": sum(data["yearly_total"].values()),
            # most_common() breaks ties by insertion order, so two runs over
            # the same data could emit different JSON -- observed directly when
            # a rebuild reordered equal-count SOC codes. Sort ties by name.
            "top_titles": _top_n(data["job_titles"]),
            "top_soc": [[f"{c} {_best_soc_name(data['soc_names'], c)}".strip(), n]
                        for c, n in _top_n(data["soc_codes"])],
            "wage_median": wages[n // 2] if n else 0,
            "wage_25th": wages[n // 4] if n else 0,
            "wage_75th": wages[3 * n // 4] if n else 0,
            "title_wages": title_stats,
            "yearly": {str(y): c for y, c in sorted(data["yearly_certified"].items())},
        }
    return result


def step3_parse_federal(state: PipelineState) -> PipelineState:
    """Parse all federal data sources into processed JSON aggregates."""
    if state.should_halt():
        return state

    base_dir = state.config.base_dir
    entity_map = state.config.entity_map
    print("\n[Step 3: PARSE_FEDERAL] Parsing federal data sources...")

    errors = []
    data = {}

    # H-1B
    print("  Parsing H-1B Data Hub files...")
    try:
        h1b = _parse_h1b_files(base_dir, entity_map)
        out_path = base_dir / "data" / "h1b" / "h1b_by_university.json"
        with open(out_path, "w") as f:
            json.dump(h1b, f, indent=2)
        data["h1b_universities"] = len(h1b)
        all_years = sorted(set(y for years in h1b.values() for y in years.keys()))
        print(f"    {len(h1b)} universities, FY{all_years[0]}-FY{all_years[-1]}" if all_years else f"    {len(h1b)} universities")
    except Exception as e:
        errors.append(f"H-1B parse failed: {e}")
        print(f"    ERROR: {e}")

    # LCA (slow — large files)
    try:
        lca = _parse_lca_files(base_dir, entity_map)
        if lca:
            out_path = base_dir / "data" / "h1b" / "lca_by_university.json"
            with open(out_path, "w") as f:
                json.dump(lca, f, indent=2, default=str)
            data["lca_universities"] = len(lca)
            print(f"    {len(lca)} universities with LCA data")
    except Exception as e:
        errors.append(f"LCA parse failed: {e}")
        print(f"    LCA ERROR: {e}")

    # OPT — already parsed into opt_by_university.json by previous extraction
    opt_path = base_dir / "data" / "h1b" / "opt_by_university.json"
    if opt_path.exists():
        with open(opt_path) as f:
            opt = json.load(f)
        data["opt_universities"] = len(opt)
        print(f"  OPT: {len(opt)} universities (pre-parsed from PDFs)")

    # PERM — already parsed into perm_by_university.json
    perm_path = base_dir / "data" / "h1b" / "perm_by_university.json"
    if perm_path.exists():
        with open(perm_path) as f:
            perm = json.load(f)
        data["perm_universities"] = len(perm)
        print(f"  PERM: {len(perm)} universities (pre-parsed)")

    if errors:
        # This reported success=True with a "warnings" message, so a federal
        # source failing to parse at all still let the pipeline run on and
        # publish. Each entry here is a whole source that did not parse.
        outcome = StepOutcome(
            step_name="parse_federal", university_key="",
            success=False,
            message=f"{len(errors)} federal source(s) failed to parse",
            data=data, errors=tuple(errors), warnings=(),
            timestamp=datetime.utcnow().isoformat(),
        )
    else:
        outcome = StepOutcome.ok("parse_federal", message="All federal sources parsed", data=data)

    return state.with_outcome(outcome)
