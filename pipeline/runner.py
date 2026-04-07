"""
Pipeline runner — composes steps into a pipeline and executes them.

Follows railway-oriented programming: each step receives PipelineState
and returns PipelineState. Failures short-circuit via the halted flag.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Callable

from .state import PipelineConfig, PipelineState, StepOutcome


# A step function takes state and returns new state
StepFunction = Callable[[PipelineState], PipelineState]


def compose_pipeline(*steps: StepFunction) -> StepFunction:
    """Compose multiple steps into a single pipeline function.

    Each step receives the state from the previous step.
    If any step sets halted=True, subsequent steps are skipped.
    """
    def pipeline(state: PipelineState) -> PipelineState:
        for step in steps:
            if state.should_halt():
                break
            state = step(state)
        return state
    return pipeline


def load_manifest(base_dir: Path) -> dict:
    """Load existing manifest or return empty dict."""
    manifest_path = base_dir / "pipeline" / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            return json.load(f)
    return {}


def save_manifest(base_dir: Path, manifest: dict) -> None:
    """Save manifest to disk."""
    manifest_path = base_dir / "pipeline" / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def run_pipeline(
    base_dir: Path,
    steps: list[StepFunction] | None = None,
    university_filter: str | list[str] | None = None,
    dry_run: bool = False,
) -> PipelineState:
    """Run the full pipeline or selected steps.

    Args:
        base_dir: Project root directory
        steps: List of step functions to run (default: all steps)
        university_filter: Single key, list of keys, or None for all
        dry_run: If True, show what would be done without executing
    """
    print("Loading pipeline configuration...")
    config = PipelineConfig.load(base_dir)
    manifest = load_manifest(base_dir)

    if university_filter:
        # Normalize to list
        keys = [university_filter] if isinstance(university_filter, str) else list(university_filter)
        missing = [k for k in keys if k not in config.universities]
        if missing:
            print(f"WARNING: Unknown university keys: {missing[:5]}")
            keys = [k for k in keys if k in config.universities]
        if not keys:
            return PipelineState(config=config, outcomes=(), manifest=manifest, halted=True,
                                halt_reason="No valid university keys")
        filtered = {k: config.universities[k] for k in keys}
        config = PipelineConfig(
            universities=filtered,
            entity_map=config.entity_map,
            base_dir=config.base_dir,
            raw_dir=config.raw_dir,
            processed_dir=config.processed_dir,
            site_dir=config.site_dir,
        )
        if len(keys) == 1:
            print(f"  Filtering to: {keys[0]} ({config.universities[keys[0]].name})")
        else:
            print(f"  Filtering to {len(keys)} universities")

    print(f"  {len(config.universities)} universities configured")
    print(f"  {len(config.entity_map)} employer name mappings")

    state = PipelineState(config=config, outcomes=(), manifest=manifest)

    if dry_run:
        print("\n[DRY RUN] Would execute these steps:")
        if steps:
            for step in steps:
                print(f"  - {step.__name__}")
        else:
            print("  - (no steps provided)")
        return state

    if steps:
        pipeline = compose_pipeline(*steps)
    else:
        print("No steps provided. Use --step or provide steps programmatically.")
        return state

    print("\nExecuting pipeline...")
    start = time.time()
    state = pipeline(state)
    elapsed = time.time() - start

    # Save updated manifest
    save_manifest(base_dir, state.manifest)

    print(f"\n{'='*60}")
    print(state.summary())
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'='*60}")

    return state
