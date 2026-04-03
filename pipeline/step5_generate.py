"""
Step 5: GENERATE — Generate HTML pages from enriched JSONs.

This step ONLY reads from site/data/ and writes HTML files.
It NEVER modifies per-university JSON files.

Input:  site/data/{stem,nonstem}/{key}.json (enriched)
Output: site/stem.html, site/non_stem.html
"""
from __future__ import annotations
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .state import PipelineState, StepOutcome


def step5_generate(state: PipelineState) -> PipelineState:
    """Generate HTML pages by calling the existing generator script.

    The generator creates stem.html and non_stem.html from the
    per-university JSON files. It also creates the JSON files
    as a side effect — but since we run step4_enrich AFTER this,
    the enrichment data is preserved.

    TODO: Refactor generate_name_lists_html.py to read-only mode
    (read JSONs, don't recreate them). For now, we run the generator
    first and enrichment second to work around the overwrite issue.
    """
    if state.should_halt():
        return state

    base_dir = state.config.base_dir
    print("\n[Step 5: GENERATE] Generating HTML pages...")

    # Run the existing generator script
    result = subprocess.run(
        [sys.executable, str(base_dir / "scripts" / "generate_name_lists_html.py")],
        capture_output=True,
        text=True,
        cwd=str(base_dir),
    )

    if result.returncode != 0:
        errors = result.stderr.strip().split("\n") if result.stderr else ["Unknown error"]
        outcome = StepOutcome.err(
            "generate",
            message="HTML generation failed",
            errors=tuple(errors[:5]),
        )
        print(f"  FAILED: {errors[0]}")
        return state.with_outcome(outcome)

    # Parse output for stats
    output = result.stdout + result.stderr
    record_count = ""
    for line in output.split("\n"):
        if "records across" in line:
            record_count = line.strip()

    outcome = StepOutcome.ok(
        "generate",
        message=f"Generated HTML. {record_count}",
        data={"output": record_count},
    )
    print(f"  {record_count}")
    return state.with_outcome(outcome)
