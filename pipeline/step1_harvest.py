"""
Step 1: HARVEST — Fetch raw data from university repositories.

Pure plan + effectful fetch: builds a harvest plan from config,
then executes OAI-PMH fetches and REST API calls.

Input:  pipeline/universities.json harvest configs
Output: data/western_us_dissertations/{key}_etds.csv (raw OAI data)

This step wraps the existing scrape_oai_etds.py and enrich_concurrent.py
scripts, adding manifest tracking.
"""
from __future__ import annotations
import hashlib
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .state import PipelineState, StepOutcome


def _file_sha256(path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_csv_rows(path: Path) -> int:
    """Count rows in a CSV file (excluding header)."""
    with open(path) as f:
        return sum(1 for _ in f) - 1


def _build_harvest_plan(state: PipelineState) -> list[dict]:
    """Pure: determine which universities need re-harvesting."""
    plan = []
    for key, uni in state.config.universities.items():
        harvest = uni.harvest
        if not harvest.get("oai_base"):
            continue

        # Check if we have existing data
        src_file = state.config.base_dir / uni.processing.get("file", "")
        has_data = src_file.exists() and src_file.stat().st_size > 100

        # Check manifest for last harvest
        manifest_entry = state.manifest.get(key, {}).get("harvest", {})
        last_run = manifest_entry.get("last_run", "")

        plan.append({
            "key": key,
            "name": uni.name,
            "oai_base": harvest["oai_base"],
            "platform": harvest.get("platform", ""),
            "sets": harvest.get("sets", []),
            "metadata_prefix": harvest.get("metadata_prefix", "oai_dc"),
            "output_file": str(src_file),
            "has_existing_data": has_data,
            "last_harvest": last_run,
            "needs_harvest": not has_data,  # Simple: harvest if no data
        })

    return plan


def step1_harvest(state: PipelineState) -> PipelineState:
    """Harvest ETD data from university repositories.

    By default, only harvests universities that don't have existing data.
    Use --force to re-harvest all.
    """
    if state.should_halt():
        return state

    base_dir = state.config.base_dir
    print("\n[Step 1: HARVEST] Building harvest plan...")

    plan = _build_harvest_plan(state)
    need_harvest = [p for p in plan if p["needs_harvest"]]
    have_data = [p for p in plan if p["has_existing_data"]]

    print(f"  {len(plan)} universities with harvest configs")
    print(f"  {len(have_data)} already have data")
    print(f"  {len(need_harvest)} need harvesting")

    if not need_harvest:
        outcome = StepOutcome.ok(
            "harvest",
            message=f"All {len(have_data)} universities have data, no harvesting needed",
            data={"total": len(plan), "existing": len(have_data), "harvested": 0},
        )
        return state.with_outcome(outcome)

    # Execute harvests
    harvested = 0
    errors = []
    new_state = state

    for entry in need_harvest:
        key = entry["key"]
        print(f"  Harvesting {key} ({entry['name']})...")

        try:
            result = subprocess.run(
                [sys.executable, str(base_dir / "scripts" / "scrape_oai_etds.py"),
                 "--repo", key],
                capture_output=True, text=True, timeout=600,
                cwd=str(base_dir),
            )

            output_path = Path(entry["output_file"])
            if output_path.exists() and output_path.stat().st_size > 100:
                row_count = _count_csv_rows(output_path)
                sha = _file_sha256(output_path)
                new_state = new_state.with_manifest_update(key, "harvest", {
                    "last_run": datetime.utcnow().isoformat(),
                    "record_count": row_count,
                    "sha256": sha,
                })
                harvested += 1
                print(f"    OK: {row_count} records")
            else:
                errors.append(f"{key}: no output file produced")
                print(f"    FAILED: no output")

        except subprocess.TimeoutExpired:
            errors.append(f"{key}: harvest timed out (600s)")
            print(f"    TIMEOUT")
        except Exception as e:
            errors.append(f"{key}: {e}")
            print(f"    ERROR: {e}")

    data = {"total": len(plan), "existing": len(have_data), "harvested": harvested, "errors": len(errors)}
    if errors:
        outcome = StepOutcome(
            step_name="harvest", university_key="", success=True,
            message=f"Harvested {harvested} universities, {len(errors)} errors",
            data=data, errors=tuple(errors[:10]), warnings=(),
            timestamp=datetime.utcnow().isoformat(),
        )
    else:
        outcome = StepOutcome.ok("harvest", message=f"Harvested {harvested} universities", data=data)

    return new_state.with_outcome(outcome)
