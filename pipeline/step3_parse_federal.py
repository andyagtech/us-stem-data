"""
Step 3: PARSE_FEDERAL — Parse all federal data sources into processed JSONs.

Pure transforms: raw CSV/XLSX/PDF → processed JSON aggregates.

Input:  data/h1b/*.csv (H-1B hub), data/h1b/lca/*.xlsx (LCA),
        data/h1b/opt_by_school.json (OPT PDFs already extracted),
        data/h1b/perm_*.xlsx (PERM), data/ipeds/*.csv, data/herd/*.xlsx, data/gss/*.csv
Output: data/h1b/h1b_by_university.json, data/h1b/lca_by_university.json,
        data/h1b/opt_by_university.json, data/h1b/perm_by_university.json
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
    return result if result is not None else {}


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
        "case_number":   ("CASE_NUMBER", "LCA_CASE_NUMBER"),
        "case_status":   ("CASE_STATUS", "STATUS"),
        "employer_name": ("EMPLOYER_NAME", "LCA_CASE_EMPLOYER_NAME"),
        "job_title":     ("JOB_TITLE", "LCA_CASE_JOB_TITLE"),
        "soc_code":      ("SOC_CODE", "LCA_CASE_SOC_CODE"),
        "soc_name":      ("SOC_NAME", "SOC_TITLE", "LCA_CASE_SOC_NAME"),
        # FY2015/16 name this WAGE_RATE_OF_PAY with no _FROM suffix; the old
        # substring lookup for "WAGE_RATE_OF_PAY_FROM" never matched it, so
        # those years contributed no wages at all.
        # FY2019's 260-column layout repeats the wage block per worksite as
        # WAGE_RATE_OF_PAY_FROM_1..n; _1 is the primary worksite.
        "wage_from":     ("WAGE_RATE_OF_PAY_FROM", "WAGE_RATE_OF_PAY_FROM_1",
                          "WAGE_RATE_OF_PAY", "LCA_CASE_WAGE_RATE_FROM"),
        "wage_unit":     ("WAGE_UNIT_OF_PAY", "WAGE_UNIT_OF_PAY_1",
                          "LCA_CASE_WAGE_RATE_UNIT"),
        # No DOL layout carries a fiscal-year column, so these are CALENDAR
        # years. FY2013 has no DECISION_DATE and falls back to the submit date.
        "decision_date": ("DECISION_DATE", "LCA_CASE_SUBMIT"),
    }

    def read_header(path: Path) -> list[str]:
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            return next(csv.reader(fh), [])

    selects, layouts, no_key = [], {}, []
    for cpath in csv_files:
        header = read_header(cpath)
        lookup = {h.strip().upper(): h for h in header if h and h.strip()}
        parts, resolved = [f"'{cpath.name}' AS source_file"], {}
        for canon, aliases in CANON.items():
            actual = next((lookup[a] for a in aliases if a in lookup), None)
            resolved[canon] = actual
            # Qualify with the table alias: DuckDB matches identifiers
            # case-insensitively, so a bare "CASE_NUMBER" AS case_number reads
            # as a self-reference to the alias and fails to bind.
            parts.append(f'src."{actual}" AS {canon}' if actual
                         else f"NULL AS {canon}")
        # EVERY canonical field must resolve, not just the key ones. FY2019
        # names its wage columns WAGE_RATE_OF_PAY_FROM_1; before that alias
        # existed the file matched on case number and employer, passed the
        # key check, and silently contributed no wages at all. That is the
        # same class of loss as a dropped file, just harder to notice.
        unresolved = [c for c, actual in resolved.items() if not actual]
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
               COALESCE(l.decision_date, '') AS fy_str
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

    con.close()
    return _finalize_lca(lca_by_uni)


def _top_n(counter, n: int = 10) -> list:
    """Top n by count, ties broken alphabetically so the output is stable."""
    return [[k, c] for k, c in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


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
