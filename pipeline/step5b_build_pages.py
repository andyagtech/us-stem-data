"""
Step 5b: BUILD_PAGES — Pre-render static HTML for each university.

For high traffic, every university gets its own static HTML file at
site/universities/{key}.html. CloudFront caches each URL at the edge
with a high hit rate, instead of serving an SPA shell that requires
a JSON fetch round-trip.

Input:  site/data/{stem,nonstem}/{key}.json (enriched per-university data)
Output: site/universities/{key}.html (101 STEM pages)
        site/universities/nonstem/{key}.html (101 non-STEM pages)
        site/sitemap.xml (with all university URLs)

Also rebuilds Parquet exports from the enriched JSONs (for the query page).
"""
from __future__ import annotations
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .state import PipelineState, StepOutcome


def step5b_build_pages(state: PipelineState) -> PipelineState:
    if state.should_halt():
        return state

    base_dir = state.config.base_dir
    print("\n[Step 5b: BUILD_PAGES] Building static university pages and Parquet exports...")

    # 1. Rebuild Parquet exports from enriched site/data JSONs (with all 9 fields)
    parquet_script = base_dir / "scripts" / "build_parquet_from_site.py"
    if parquet_script.exists():
        result = subprocess.run(
            [sys.executable, str(parquet_script)],
            capture_output=True,
            text=True,
            cwd=str(base_dir),
        )
        if result.returncode != 0:
            print(f"  WARNING: Parquet build failed: {result.stderr.strip()[:200]}")
        else:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    print(f"  {line}")

    # 2. Build static university pages
    pages_script = base_dir / "scripts" / "build_static_pages.py"
    if not pages_script.exists():
        outcome = StepOutcome.err(
            "build_pages",
            message="build_static_pages.py not found",
            errors=("Missing script",),
        )
        return state.with_outcome(outcome)

    result = subprocess.run(
        [sys.executable, str(pages_script)],
        capture_output=True,
        text=True,
        cwd=str(base_dir),
    )

    if result.returncode != 0:
        errors = result.stderr.strip().split("\n") if result.stderr else ["Unknown error"]
        outcome = StepOutcome.err(
            "build_pages",
            message="Static page build failed",
            errors=tuple(errors[:5]),
        )
        print(f"  FAILED: {errors[0]}")
        return state.with_outcome(outcome)

    # Parse output for stats
    output = result.stdout
    page_count = ""
    for line in output.split("\n"):
        line = line.strip()
        if line and (":built" in line.replace(" ", "") or "Sitemap" in line):
            print(f"  {line}")
            if "stem:" in line and "built" in line:
                page_count = line

    outcome = StepOutcome.ok(
        "build_pages",
        message=f"Built static pages. {page_count}",
        data={"output": page_count},
    )
    return state.with_outcome(outcome)
