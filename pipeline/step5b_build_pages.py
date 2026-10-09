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

    # SAFEGUARD: refuse to build if site/data JSONs look unenriched.
    # An enriched JSON has fields beyond {key, name, nra, records}.
    # A bare JSON (just generated, no enrich) has only those 4 keys.
    # If we built static pages from bare JSONs, the universities would be broken.
    import json
    sample_path = base_dir / "site" / "data" / "stem" / "mit.json"
    if sample_path.exists():
        try:
            sample = json.load(open(sample_path))
            extra_keys = set(sample.keys()) - {"key", "name", "nra", "records"}
            if not extra_keys:
                msg = (
                    "site/data/stem/mit.json has no enrichment fields. "
                    "Run 'enrich' before 'build_pages' to avoid building broken pages."
                )
                print(f"  ERROR: {msg}")
                return state.with_outcome(StepOutcome.err(
                    "build_pages",
                    message=msg,
                    errors=("Unenriched JSONs detected",),
                ))
        except Exception as e:
            print(f"  WARNING: Could not validate enrichment state: {e}")

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
            # This used to warn and continue, and the step still reported OK.
            # A missing duckdb therefore shipped an April snapshot on every
            # deploy for four months without anyone noticing. A build that
            # cannot produce its outputs has not succeeded.
            detail = result.stderr.strip()[:300] or "no stderr"
            return state.with_outcome(StepOutcome.err(
                "build_pages",
                message=f"Parquet build failed: {detail}",
                errors=(f"scripts/build_parquet_from_site.py exited "
                        f"{result.returncode}",),
            ))
        else:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    print(f"  {line}")

    # 1b. Refresh the dashboard snapshots inlined into the pages.
    #
    # medical, workforce, canada and uk do not fetch their JSON at runtime --
    # the whole dataset is written into the page as `const D = {...}`. That is
    # fine until the builder reruns and the page keeps the old copy, which is
    # exactly what happened: /workforce.html was still serving a topline whose
    # shares disagreed with the dataset beside it, and it published the
    # sentence "22% naturalized citizens + 7% green card holders" when the
    # counts gave 20.2% and 7.9%. The inliner existed and was simply never
    # run by anything.
    inline_script = base_dir / "scripts" / "inline_dashboard_data.py"
    if inline_script.exists():
        result = subprocess.run(
            [sys.executable, str(inline_script)],
            capture_output=True, text=True, cwd=str(base_dir),
        )
        if result.returncode != 0:
            detail = result.stderr.strip()[:300] or "no stderr"
            return state.with_outcome(StepOutcome.err(
                "build_pages",
                message=f"Dashboard inlining failed: {detail}",
                errors=(f"scripts/inline_dashboard_data.py exited "
                        f"{result.returncode}",),
            ))
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                print(f"  {line}")

    # 1c. The generated topic pages.
    #
    # Neither of these was run by anything. build_industry_pages.py built six
    # pages and the hub; build_state_pages.py builds one page per published
    # state. Both read a dataset at build time, so leaving them out of the
    # pipeline meant a dataset could move while the pages kept the old
    # numbers -- the same failure 1b exists to prevent, waiting to happen
    # twice more. They run here, and a non-zero exit fails the step.
    for name in ("build_state_residency.py", "build_institution_funding.py",
                 "build_industry_pages.py",
                 "build_state_pages.py"):
        script = base_dir / "scripts" / name
        if not script.exists():
            continue
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, cwd=str(base_dir),
        )
        if result.returncode != 0:
            detail = result.stderr.strip()[:300] or "no stderr"
            return state.with_outcome(StepOutcome.err(
                "build_pages",
                message=f"{name} failed: {detail}",
                errors=(f"scripts/{name} exited {result.returncode}",),
            ))
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
