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


def _load_repo_registry(base_dir) -> dict:
    """Endpoint config from scrape_oai_etds.REPOS, keyed by university."""
    import sys as _sys
    scripts_dir = str(base_dir / "scripts")
    if scripts_dir not in _sys.path:
        _sys.path.insert(0, scripts_dir)
    try:
        from scrape_oai_etds import REPOS
    except Exception:
        return {}
    return {
        k: {
            "oai_base": v.get("oai_base", ""),
            "platform": v.get("platform", ""),
            "sets": v.get("sets", []),
            "metadata_prefix": v.get("metadata_prefix", "oai_dc"),
        }
        for k, v in REPOS.items()
    }


def _build_harvest_plan(state: PipelineState) -> list[dict]:
    """Pure: determine which universities need re-harvesting."""
    # universities.json carries an empty "harvest" block for every entry, so
    # resolving endpoints from it alone skipped all 101 and made this step a
    # no-op. The live registry is scrape_oai_etds.REPOS; fall back to it.
    repos = _load_repo_registry(state.config.base_dir)
    since = getattr(state.config, "harvest_since", "")

    plan = []
    for key, uni in state.config.universities.items():
        harvest = uni.harvest or {}
        if not harvest.get("oai_base"):
            harvest = repos.get(key, harvest)
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
            # Without a cutoff we only fill gaps. With one, every configured
            # repository is revisited for records deposited since that date.
            "needs_harvest": (not has_data) or bool(since),
            "since": since,
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
            cmd = [sys.executable, str(base_dir / "scripts" / "scrape_oai_etds.py"),
                   "--repo", key]
            if entry.get("since"):
                cmd += ["--from", entry["since"]]
            result = subprocess.run(
                cmd,
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
        # A partial harvest is tolerable -- repositories rate-limit and time
        # out, and one unreachable endpoint should not stop the run. Total
        # failure is not: if nothing came back, everything downstream would
        # process a stale corpus and report success, which is how a four-month-
        # old artifact shipped once already.
        #
        # This branch previously hardcoded success=True, so a harvest where
        # EVERY repository failed still reported OK, with the failures recorded
        # in a field nobody reads.
        fatal = harvested == 0 and len(errors) > 0
        outcome = StepOutcome(
            step_name="harvest", university_key="", success=not fatal,
            message=(f"Harvest FAILED: 0 of {len(plan)} universities produced "
                     f"data ({len(errors)} errors)" if fatal else
                     f"Harvested {harvested} universities, {len(errors)} errors"),
            data=data, errors=tuple(errors[:10]), warnings=(),
            timestamp=datetime.utcnow().isoformat(),
        )
    else:
        outcome = StepOutcome.ok("harvest", message=f"Harvested {harvested} universities", data=data)

    return new_state.with_outcome(outcome)
