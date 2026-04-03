"""
Step 2: PROCESS — Process raw CSV data into per-university record JSONs.

Pure transforms: raw CSV → classified records with degree labels,
department taxonomy, name origin classification.

Input:  Raw CSVs as specified in universities.json processing.file
Output: Updates to site/data/{stem,nonstem}/{key}.json via generate step

This step delegates to the existing generate_name_lists.py which handles
all the complex processing (degree inference, taxonomy, classification).
In a future refactor, the pure functions will be extracted here.
"""
from __future__ import annotations
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .state import PipelineState, StepOutcome

# Increase CSV field size limit for long descriptions
csv.field_size_limit(1_000_000)


def step2_process(state: PipelineState) -> PipelineState:
    """Process all university raw data into classified records.

    Currently delegates to generate_name_lists.py which handles:
    - Loading raw CSVs per university config
    - infer_degree_type() for PhD/MS classification
    - Department taxonomy normalization
    - Name origin classification
    - Deduplication

    The output is written by step5_generate which calls the HTML generator.

    TODO: Extract pure processing functions from generate_name_lists.py
    into this module for better testability and separation of concerns.
    """
    if state.should_halt():
        return state

    print("\n[Step 2: PROCESS] Processing university records...")

    # Validate that all source files exist
    missing = []
    for key, uni in state.config.universities.items():
        src_file = state.config.base_dir / uni.processing.get("file", "")
        if uni.processing.get("file") and not src_file.exists():
            missing.append(f"{key}: {uni.processing['file']}")

    if missing:
        print(f"  WARNING: {len(missing)} source files missing")
        for m in missing[:5]:
            print(f"    {m}")

    # Currently a no-op — processing happens in step5_generate
    # which calls generate_name_lists_html.py
    # In the future, this will extract pure record processing

    total_unis = len(state.config.universities)
    outcome = StepOutcome.ok(
        "process",
        message=f"Validated {total_unis} university configs ({len(missing)} missing files)",
        data={"universities": total_unis, "missing_files": len(missing), "missing": missing[:10]},
    )

    if missing:
        outcome = StepOutcome(
            step_name="process", university_key="", success=True,
            message=f"Validated {total_unis} configs, {len(missing)} missing files",
            data={"universities": total_unis, "missing_files": len(missing)},
            errors=(), warnings=tuple(missing[:10]),
            timestamp=datetime.utcnow().isoformat(),
        )

    print(f"  {total_unis} universities configured")
    return state.with_outcome(outcome)
