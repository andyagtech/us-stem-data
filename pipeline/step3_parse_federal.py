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


def _normalize_job_title(title: str) -> str:
    """Normalize H-1B job titles to remove duplicates and Excel artifacts."""
    t = title.strip()
    # Remove Excel formula artifacts: ="Title" → Title
    if t.startswith('="') and t.endswith('"'):
        t = t[2:-1]
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

    Uses DuckDB for fast SQL-based aggregation when available,
    falls back to openpyxl row-by-row parsing otherwise.
    """
    lca_dir = base_dir / "data" / "h1b" / "lca"
    if not lca_dir.exists():
        return {}

    # Try DuckDB fast path first
    try:
        result = _parse_lca_duckdb(lca_dir, entity_map)
        if result is not None:
            return result
    except Exception as e:
        print(f"  DuckDB LCA parse failed ({e}), falling back to openpyxl...")

    return _parse_lca_openpyxl(lca_dir, entity_map)


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
            print("  WARNING: openpyxl not installed, cannot convert XLSX")
            return None

        for fname in need_convert:
            xlsx_path = lca_dir / fname
            csv_path = csv_dir / fname.replace(".xlsx", ".csv")
            try:
                wb = openpyxl.load_workbook(str(xlsx_path), read_only=True)
                ws = wb.active
                with open(csv_path, "w", newline="", encoding="utf-8") as cf:
                    writer = csv.writer(cf)
                    for row in ws.iter_rows(values_only=True):
                        writer.writerow([str(c) if c is not None else "" for c in row])
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

    # Read all CSVs into a single view, auto-detecting columns
    csv_glob = str(csv_dir / "*.csv")
    con.execute(f"""
        CREATE VIEW lca_raw AS
        SELECT * FROM read_csv('{csv_glob}',
            header=true,
            auto_detect=true,
            ignore_errors=true,
            filename=true,
            union_by_name=true,
            all_varchar=true
        )
    """)

    # Check available columns
    cols = [row[0] for row in con.execute("DESCRIBE lca_raw").fetchall()]
    cols_upper = {c.upper(): c for c in cols}

    def find_col(*names):
        for n in names:
            for cu, c in cols_upper.items():
                if n in cu:
                    return c
        return None

    emp_col = find_col("EMPLOYER_NAME")
    status_col = find_col("CASE_STATUS")
    title_col = find_col("JOB_TITLE")
    soc_col = find_col("SOC_CODE")
    soc_name_col = find_col("SOC_NAME", "SOC_TITLE")
    wage_col = find_col("WAGE_RATE_OF_PAY_FROM")
    wage_unit_col = find_col("WAGE_UNIT_OF_PAY")
    # NOTE: no LCA layout DOL has published carries a FISCAL_YEAR column, so
    # this always resolves to DECISION_DATE and the year buckets are CALENDAR
    # years, not fiscal. Label them accordingly downstream; DOL now ships
    # FY2026 cumulatively, so a part-year file otherwise reads as a collapse
    # in volume rather than an incomplete year.
    fy_col = find_col("FISCAL_YEAR", "DECISION_DATE")

    if not emp_col:
        con.close()
        return None

    # Match employers and extract data using SQL
    con.execute(f"""
        CREATE TABLE matched AS
        SELECT
            e.uni_key,
            COALESCE(l."{status_col}", '') as case_status,
            COALESCE(l."{title_col}", '') as job_title,
            COALESCE(l."{soc_col}", '') as soc_code,
            COALESCE(l."{soc_name_col or soc_col}", '') as soc_name,
            COALESCE(l."{wage_col or 'NULL'}", '') as wage_str,
            COALESCE(l."{wage_unit_col or 'NULL'}", '') as wage_unit,
            COALESCE(l."{fy_col or 'NULL'}", '') as fy_str
        FROM lca_raw l
        JOIN entity_map e ON UPPER(TRIM(l."{emp_col}")) = e.employer_name
    """)

    total_matched = con.execute("SELECT COUNT(*) FROM matched").fetchone()[0]
    print(f"    Total matched rows: {total_matched:,}")

    # Fetch matched data for Python-side aggregation
    # (DuckDB's SQL handles the join; Python handles title normalization + wage conversion)
    lca_by_uni = defaultdict(lambda: {
        "job_titles": Counter(), "soc_codes": Counter(), "wages": [],
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
                d["soc_codes"][f"{soc} {soc_name}"] += 1

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


def _parse_lca_openpyxl(lca_dir: Path, entity_map: dict) -> dict:
    """Fallback: parse LCA files row-by-row with openpyxl."""
    try:
        import openpyxl
    except ImportError:
        print("  WARNING: openpyxl not installed, skipping LCA parsing")
        return {}

    lca_by_uni = defaultdict(lambda: {
        "job_titles": Counter(), "soc_codes": Counter(), "wages": [],
        "title_wages": defaultdict(list),
        "yearly_certified": defaultdict(int), "yearly_total": defaultdict(int),
    })

    files = sorted(f for f in os.listdir(lca_dir) if f.endswith(".xlsx"))
    print(f"  LCA: parsing {len(files)} files with openpyxl...")

    for fname in files:
        path = lca_dir / fname
        try:
            wb = openpyxl.load_workbook(str(path), read_only=True)
            ws = wb.active
            headers = None
            matched = 0

            for row in ws.iter_rows(values_only=True):
                if headers is None:
                    headers = [str(c).upper().strip() if c else "" for c in row]

                    def find_col(*names):
                        for n in names:
                            for i, h in enumerate(headers):
                                if n in h:
                                    return i
                        return None

                    emp_col = find_col("EMPLOYER_NAME")
                    status_col = find_col("CASE_STATUS")
                    title_col = find_col("JOB_TITLE")
                    soc_col = find_col("SOC_CODE")
                    soc_name_col = find_col("SOC_NAME", "SOC_TITLE")
                    wage_col = find_col("WAGE_RATE_OF_PAY_FROM")
                    wage_unit_col = find_col("WAGE_UNIT_OF_PAY")
                    # NOTE: no LCA layout DOL has published carries a FISCAL_YEAR column, so
                    # this always resolves to DECISION_DATE and the year buckets are CALENDAR
                    # years, not fiscal. Label them accordingly downstream; DOL now ships
                    # FY2026 cumulatively, so a part-year file otherwise reads as a collapse
                    # in volume rather than an incomplete year.
                    fy_col = find_col("FISCAL_YEAR", "DECISION_DATE")
                    if emp_col is None:
                        break
                    continue

                emp = str(row[emp_col] or "") if emp_col < len(row) else ""
                key = _match_employer(emp, entity_map)
                if not key:
                    continue
                matched += 1

                status = str(row[status_col] or "").upper() if status_col and status_col < len(row) else ""
                title = str(row[title_col] or "") if title_col and title_col < len(row) else ""
                soc = str(row[soc_col] or "") if soc_col and soc_col < len(row) else ""
                soc_name = str(row[soc_name_col] or "") if soc_name_col and soc_name_col < len(row) else ""

                wage = None
                if wage_col and wage_col < len(row):
                    try:
                        w = float(row[wage_col])
                        unit = str(row[wage_unit_col] or "").upper() if wage_unit_col and wage_unit_col < len(row) else "YEAR"
                        if "HOUR" in unit: w *= 2080
                        elif "WEEK" in unit: w *= 52
                        elif "MONTH" in unit: w *= 12
                        if 20000 < w < 500000:
                            wage = int(w)
                    except (ValueError, TypeError):
                        pass

                year = None
                if fy_col and fy_col < len(row):
                    fy_val = str(row[fy_col] or "")
                    if len(fy_val) >= 4:
                        try:
                            year = int(fy_val[:4])
                        except ValueError:
                            pass

                d = lca_by_uni[key]
                norm_title = _normalize_job_title(title)[:60] if title else ""
                if norm_title:
                    d["job_titles"][norm_title] += 1
                if soc:
                    d["soc_codes"][f"{soc} {soc_name}"] += 1
                if wage:
                    d["wages"].append(wage)
                    if norm_title:
                        d["title_wages"][norm_title].append(wage)
                if year:
                    d["yearly_total"][year] += 1
                    if "CERTIFIED" in status:
                        d["yearly_certified"][year] += 1

            wb.close()
            print(f"    {fname}: {matched} matched", flush=True)
        except Exception as e:
            print(f"    {fname}: ERROR {e}")

    return _finalize_lca(lca_by_uni)


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
            "top_titles": data["job_titles"].most_common(10),
            "top_soc": data["soc_codes"].most_common(10),
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
        outcome = StepOutcome(
            step_name="parse_federal", university_key="",
            success=True, message=f"Parsed with {len(errors)} warnings",
            data=data, errors=tuple(errors), warnings=(),
            timestamp=datetime.utcnow().isoformat(),
        )
    else:
        outcome = StepOutcome.ok("parse_federal", message="All federal sources parsed", data=data)

    return state.with_outcome(outcome)
