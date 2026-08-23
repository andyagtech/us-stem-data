#!/usr/bin/env python3
"""Rebuild lca_by_university.json off-box.

The aggregation is NOT reimplemented here: this driver calls the pipeline's
own _parse_lca_files() so the result is identical to a local run. The only
thing it does itself is the XLSX -> CSV format conversion, which it runs
across cores instead of serially. That conversion is a pure transcription
(same rows, same order, same writer) and _parse_lca_files() skips any file
already present in csv_cache, so parallelising it cannot change the output.
"""
import csv, json, os, sys, time, traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

BASE = Path(__file__).resolve().parent
LCA = BASE / "data" / "h1b" / "lca"
CSV_CACHE = LCA / "csv_cache"


def convert(fname):
    """Transcribe one XLSX to CSV. Mirrors _parse_lca_duckdb's phase 1 exactly."""
    import openpyxl
    src = LCA / fname
    dst = CSV_CACHE / fname.replace(".xlsx", ".csv")
    tmp = dst.with_suffix(".csv.partial")
    t0 = time.time()
    try:
        wb = openpyxl.load_workbook(str(src), read_only=True)
        ws = wb.active
        n = 0
        with open(tmp, "w", newline="", encoding="utf-8") as cf:
            writer = csv.writer(cf)
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                # openpyxl iterates to the sheet's declared dimension, which
                # DOL's files overstate; those rows are entirely empty.
                if not any(c.strip() for c in cells):
                    continue
                writer.writerow(cells)
                n += 1
        wb.close()
        # Only publish a complete file; a half-written CSV in the cache would
        # be silently treated as done by the pipeline on a later run.
        os.replace(tmp, dst)
        return (fname, n, time.time() - t0, None)
    except Exception as e:
        for p in (tmp, dst):
            if p.exists():
                p.unlink()
        return (fname, 0, time.time() - t0, f"{type(e).__name__}: {e}")


def preflight():
    """Resolve every XLSX header against the schema BEFORE converting anything.

    The guard in _parse_lca_duckdb() catches an unmappable layout, but it runs
    after the CSV conversion -- so a single unknown column name cost a
    twenty-minute conversion of 10.7M rows before anything complained. Reading
    just the header row of each workbook takes seconds and fails in the same
    cases, for the same reasons, with the same message.
    """
    import openpyxl
    sys.path.insert(0, str(BASE))
    from pipeline.step3_parse_federal import _canon_for_preflight

    canon, exemptions = _canon_for_preflight()
    problems = []
    for x in sorted(LCA.glob("*.xlsx")):
        wb = openpyxl.load_workbook(str(x), read_only=True)
        try:
            hdr = next(wb.active.iter_rows(values_only=True))
        finally:
            wb.close()
        lookup = {str(c).strip().upper() for c in hdr if c is not None and str(c).strip()}
        exempt = exemptions.get(x.with_suffix(".csv").name, set())
        missing = [f for f, aliases in canon.items()
                   if f not in exempt and not any(a in lookup for a in aliases)]
        if missing:
            problems.append(f"{x.name} -> {', '.join(missing)}")
    if problems:
        print("[preflight] ABORT before converting anything:", flush=True)
        for p_ in problems:
            print(f"    {p_}", flush=True)
        print("    Add the layout's column names to CANON, or exempt the file.",
              flush=True)
        return False
    print(f"[preflight] {len(list(LCA.glob('*.xlsx')))} workbooks resolve "
          f"against the schema", flush=True)
    return True


def main():
    CSV_CACHE.mkdir(parents=True, exist_ok=True)
    if not preflight():
        return 5
    xlsx = sorted(f for f in os.listdir(LCA) if f.endswith(".xlsx"))
    todo = [f for f in xlsx
            if not (CSV_CACHE / f.replace(".xlsx", ".csv")).exists()]
    print(f"[convert] {len(xlsx)} xlsx, {len(todo)} to convert", flush=True)

    workers = max(1, min(len(todo), (os.cpu_count() or 2)))
    failures, rows_total = [], 0
    if todo:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(convert, f): f for f in todo}
            for i, fut in enumerate(as_completed(futs), 1):
                fname, n, secs, err = fut.result()
                if err:
                    failures.append((fname, err))
                    print(f"[convert] {i}/{len(todo)} FAILED {fname}: {err}", flush=True)
                else:
                    rows_total += n
                    print(f"[convert] {i}/{len(todo)} {fname} "
                          f"{n:,} rows in {secs:.0f}s", flush=True)

    if failures:
        # A partial corpus produces a plausible-looking but wrong total.
        print(f"[convert] ABORT: {len(failures)} file(s) failed", flush=True)
        for f, e in failures:
            print(f"    {f}: {e}", flush=True)
        return 2

    print(f"[convert] done, {rows_total:,} rows transcribed", flush=True)

    sys.path.insert(0, str(BASE))
    from pipeline.step3_parse_federal import _parse_lca_files

    entity_map = json.loads((BASE / "pipeline" / "entity_map.json").read_text())
    print(f"[aggregate] entity_map: {len(entity_map)} employer names", flush=True)

    t0 = time.time()
    result = _parse_lca_files(BASE, entity_map)
    print(f"[aggregate] {len(result)} universities in {time.time()-t0:.0f}s", flush=True)

    if not result:
        print("[aggregate] ABORT: empty result", flush=True)
        return 3

    out = BASE / "lca_by_university.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True))
    total = sum(v.get("total_lcas", 0) for v in result.values())
    print(f"[aggregate] total_lcas across all universities: {total:,}", flush=True)
    print(f"[aggregate] wrote {out} ({out.stat().st_size:,} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
