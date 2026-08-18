"""
Step 2: PROCESS — Process raw CSV data into per-university record JSONs.

Pure transforms: raw CSV → classified records with degree labels,
department taxonomy, name origin classification.

This step imports the battle-tested functions from generate_name_lists.py
(infer_degree_type, load_records, department extraction, STEM taxonomy)
and runs them for each configured university, producing per-university
JSON files in data/processed/{key}.json.

The processed files contain arrays of record dicts with:
  dept, year, name, classification, confidence, title, url, degree

These are consumed by step4_enrich (merge federal data) and step5_generate (HTML).
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from .state import PipelineState, StepOutcome

# Increase CSV field size limit for long descriptions
csv.field_size_limit(1_000_000)

# Import the pure processing functions from generate_name_lists.py
_scripts_dir = str(Path(__file__).parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from generate_name_lists import (  # noqa: E402
    CONFIGS,
    NON_STEM_DEPTS,
    infer_degree_type,
    load_records,
)


def _process_university(config: dict, stem_filter: str = "stem") -> dict:
    """Process a single university config into classified records.

    Pure function: config dict → result dict with records and stats.
    No side effects — caller decides what to do with the result.
    """
    cfg = dict(config)
    cfg["_stem_filter"] = stem_filter

    if not os.path.exists(cfg["file"]):
        return {
            "key": cfg["key"],
            "name": cfg["name"],
            "records": [],
            "error": f"Source file not found: {cfg['file']}",
        }

    records = load_records(cfg)

    # Compute labeling statistics
    degree_counts = Counter(r["degree"] for r in records)

    return {
        "key": cfg["key"],
        "name": cfg["name"],
        "nra": cfg["nra"],
        "records": records,
        "stats": {
            "total": len(records),
            "phd": degree_counts.get("phd", 0),
            "ms": degree_counts.get("ms", 0),
            "unlabeled": degree_counts.get("", 0),
            "labeling_pct": round(
                (1 - degree_counts.get("", 0) / max(len(records), 1)) * 100, 1
            ),
        },
    }


def _process_all(stem_filter: str = "stem", allowed: set | None = None) -> list[dict]:
    """Process universities for a given STEM filter.

    Returns list of result dicts (one per university key, merging
    configs that share a key like Missouri S&T PhD + MS).

    `allowed` restricts processing to a set of university keys. Without it
    this step iterated the module-level CONFIGS unconditionally, so
    --university and --mode were accepted, echoed back, and then ignored:
    the runner filtered its own copy of the university config while this
    step processed all 101 regardless.
    """
    results_by_key: dict[str, dict] = {}

    for config in CONFIGS:
        if allowed is not None and config.get("key") not in allowed:
            continue
        result = _process_university(config, stem_filter)
        key = result["key"]

        if config.get("_merge") and key in results_by_key:
            # Merge records into existing entry (e.g. separate PhD + MS configs)
            existing = results_by_key[key]
            existing["records"].extend(result["records"])
            # Recompute stats after merge
            degree_counts = Counter(r["degree"] for r in existing["records"])
            existing["stats"] = {
                "total": len(existing["records"]),
                "phd": degree_counts.get("phd", 0),
                "ms": degree_counts.get("ms", 0),
                "unlabeled": degree_counts.get("", 0),
                "labeling_pct": round(
                    (1 - degree_counts.get("", 0) / max(len(existing["records"]), 1))
                    * 100,
                    1,
                ),
            }
        else:
            results_by_key[key] = result

    return list(results_by_key.values())


def _write_processed_json(result: dict, output_dir: Path) -> Path:
    """Write a processed university result to a JSON file.

    Returns the output path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{result['key']}.json"

    # Write records in compact format (same as site/data/ format)
    compact = []
    for r in result["records"]:
        compact.append([
            r["dept"],
            r["year"],
            r["name"],
            r["classification"] or "",
            r["confidence"] or "",
            r["title"][:90],
            r["url"],
            r.get("degree", ""),
        ])

    data = {
        "key": result["key"],
        "name": result["name"],
        "nra": result.get("nra", 0),
        "count": len(compact),
        "records": compact,
        "stats": result["stats"],
    }

    with open(out_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    return out_path


def _export_parquet(processed_dir: Path):
    """Export all processed records to Parquet for reproducibility.

    Writes two files:
      data/processed/stem_records.parquet
      data/processed/nonstem_records.parquet

    Schema: university, department, year, name, classification, confidence, title, url, degree
    Compressed with ZSTD via DuckDB.
    """
    try:
        import duckdb
    except ImportError:
        print("  Parquet export skipped (duckdb not installed)")
        return

    for track in ("stem", "nonstem"):
        json_dir = processed_dir / track
        if not json_dir.exists():
            continue

        json_files = sorted(json_dir.glob("*.json"))
        if not json_files:
            continue

        # Collect all records from per-university JSONs
        all_rows = []
        for jf in json_files:
            with open(jf) as f:
                data = json.load(f)
            key = data.get("key", jf.stem)
            for r in data.get("records", []):
                # records are compact arrays: [dept, year, name, classification, confidence, title, url, degree]
                all_rows.append({
                    "university": key,
                    "department": r[0] if len(r) > 0 else "",
                    "year": r[1] if len(r) > 1 else 0,
                    "name": r[2] if len(r) > 2 else "",
                    "classification": r[3] if len(r) > 3 else "",
                    "confidence": r[4] if len(r) > 4 else "",
                    "title": r[5] if len(r) > 5 else "",
                    "url": r[6] if len(r) > 6 else "",
                    "degree": r[7] if len(r) > 7 else "",
                })

        if not all_rows:
            continue

        import pandas as pd
        df = pd.DataFrame(all_rows)
        con = duckdb.connect()
        con.register("records_df", df)
        out_path = processed_dir / f"{track}_records.parquet"
        con.execute(
            f"COPY records_df TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        row_count = len(df)
        con.close()

        size_mb = out_path.stat().st_size / 1024 / 1024
        print(f"  Exported {track}: {row_count:,} records → {out_path.name} ({size_mb:.1f} MB)")


def step2_process(state: PipelineState) -> PipelineState:
    """Process all university raw data into classified records.

    For each university in CONFIGS:
    1. Load raw CSV
    2. Apply degree inference (infer_degree_type)
    3. Extract and normalize department
    4. Classify name origin
    5. Deduplicate
    6. Write to data/processed/{key}.json

    Updates manifest with per-university labeling statistics.
    """
    if state.should_halt():
        return state

    print("\n[Step 2: PROCESS] Processing university records...")

    processed_dir = state.config.base_dir / "data" / "processed"
    # The runner has already narrowed config.universities to whatever
    # --university / --mode selected; honour that here too.
    allowed_keys = set(state.config.universities)
    total_records = 0
    total_phd = 0
    total_ms = 0
    total_unlabeled = 0
    uni_count = 0
    errors = []
    warnings = []

    for stem_filter in ("stem", "non-stem"):
        label = "STEM" if stem_filter == "stem" else "Non-STEM"
        results = _process_all(stem_filter, allowed=allowed_keys)

        for result in results:
            if result.get("error"):
                errors.append(f"{result['key']}: {result['error']}")
                continue

            # Write processed JSON
            out_dir = processed_dir / stem_filter.replace("-", "")
            _write_processed_json(result, out_dir)

            stats = result["stats"]
            total_records += stats["total"]
            total_phd += stats["phd"]
            total_ms += stats["ms"]
            total_unlabeled += stats["unlabeled"]

            if stem_filter == "stem":
                uni_count += 1

            # Warn on low labeling
            if stats["labeling_pct"] < 20 and stats["total"] > 50:
                warnings.append(
                    f"{result['key']}: {stats['labeling_pct']}% labeled "
                    f"({stats['unlabeled']}/{stats['total']} unlabeled)"
                )

            # Update manifest. STEM and non-STEM are separate passes over the
            # same keys, so they must land in separate entries — writing both
            # to "process" made the second pass silently overwrite the first.
            state = state.with_manifest_update(
                result["key"],
                "process" if stem_filter == "stem" else "process_nonstem",
                {
                    "last_run": datetime.utcnow().isoformat(),
                    "records": stats["total"],
                    "phd": stats["phd"],
                    "ms": stats["ms"],
                    "unlabeled": stats["unlabeled"],
                    "labeling_pct": stats["labeling_pct"],
                    "filter": stem_filter,
                },
            )

            # The "records" block is what the manifest reports as current
            # state. Nothing refreshed it, so it drifted stale while the
            # pipeline kept running. Rebuild it from the STEM pass.
            if stem_filter == "stem":
                state = state.with_manifest_update(
                    result["key"],
                    "records",
                    {
                        "total": stats["total"],
                        "phd": stats["phd"],
                        "ms": stats["ms"],
                        "unlabeled": stats["unlabeled"],
                        "label_pct": stats["labeling_pct"],
                    },
                )

    # Export to Parquet for reproducibility
    _export_parquet(processed_dir)

    labeling_pct = round((1 - total_unlabeled / max(total_records, 1)) * 100, 1)
    msg = (
        f"Processed {uni_count} universities: "
        f"{total_records:,} records ({total_phd:,} PhD, {total_ms:,} MS, "
        f"{total_unlabeled:,} unlabeled — {labeling_pct}% labeled)"
    )
    print(f"  {msg}")

    if warnings:
        print(f"  {len(warnings)} universities with <20% labeling:")
        for w in warnings[:10]:
            print(f"    {w}")

    outcome = StepOutcome(
        step_name="process",
        university_key="",
        success=len(errors) == 0,
        message=msg,
        data={
            "universities": uni_count,
            "total_records": total_records,
            "phd": total_phd,
            "ms": total_ms,
            "unlabeled": total_unlabeled,
            "labeling_pct": labeling_pct,
        },
        errors=tuple(errors[:10]),
        warnings=tuple(warnings[:10]),
        timestamp=datetime.utcnow().isoformat(),
    )

    return state.with_outcome(outcome)
