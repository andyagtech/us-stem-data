"""
Immutable state types for the pipeline.

All state flows through frozen dataclasses — no mutation, explicit error types,
clear data lineage from inputs to outputs.
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class UniversityConfig:
    """Configuration for a single university — from universities.json."""
    key: str
    name: str
    nra: float
    unitid: int | None
    harvest: dict[str, Any]
    processing: dict[str, Any]
    employer_names: list[str]

    @staticmethod
    def from_dict(key: str, d: dict) -> UniversityConfig:
        return UniversityConfig(
            key=key,
            name=d["name"],
            nra=d.get("nra", 0),
            unitid=d.get("unitid"),
            harvest=d.get("harvest", {}),
            processing=d.get("processing", {}),
            employer_names=d.get("employer_names", []),
        )


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable pipeline configuration."""
    universities: dict[str, UniversityConfig]
    entity_map: dict[str, str]  # employer name → university key
    base_dir: Path
    raw_dir: Path
    processed_dir: Path
    site_dir: Path
    # Selective-harvest cutoff (YYYY-MM-DD). Empty means a full harvest of
    # repositories that have no data yet, which is the historical behaviour.
    harvest_since: str = ""

    @staticmethod
    def load(base_dir: Path) -> PipelineConfig:
        import json
        pipeline_dir = base_dir / "pipeline"

        with open(pipeline_dir / "universities.json") as f:
            raw_unis = json.load(f)
        universities = {k: UniversityConfig.from_dict(k, v) for k, v in raw_unis.items()}

        with open(pipeline_dir / "entity_map.json") as f:
            entity_map = json.load(f)

        return PipelineConfig(
            universities=universities,
            entity_map=entity_map,
            base_dir=base_dir,
            raw_dir=base_dir / "data",
            processed_dir=base_dir / "data" / "processed",
            site_dir=base_dir / "site",
        )


@dataclass(frozen=True)
class StepOutcome:
    """Immutable result of a single pipeline step for one university."""
    step_name: str
    university_key: str  # "" for global steps
    success: bool
    message: str
    data: dict[str, Any]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    timestamp: str

    @staticmethod
    def ok(step_name: str, university_key: str = "", message: str = "", data: dict | None = None) -> StepOutcome:
        return StepOutcome(
            step_name=step_name,
            university_key=university_key,
            success=True,
            message=message,
            data=data or {},
            errors=(),
            warnings=(),
            timestamp=datetime.utcnow().isoformat(),
        )

    @staticmethod
    def err(step_name: str, university_key: str = "", message: str = "", errors: tuple[str, ...] = ()) -> StepOutcome:
        return StepOutcome(
            step_name=step_name,
            university_key=university_key,
            success=False,
            message=message,
            data={},
            errors=errors,
            warnings=(),
            timestamp=datetime.utcnow().isoformat(),
        )


@dataclass(frozen=True)
class ManifestEntry:
    """Per-university processing state."""
    last_run: str
    record_count: int = 0
    sha256: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineState:
    """Immutable pipeline state — flows through composed steps."""
    config: PipelineConfig
    outcomes: tuple[StepOutcome, ...]
    manifest: dict[str, dict[str, Any]]  # key → step → ManifestEntry-like dict
    halted: bool = False
    halt_reason: str = ""

    def with_outcome(self, outcome: StepOutcome) -> PipelineState:
        """Return new state with outcome appended. Auto-halt on failure."""
        new_outcomes = self.outcomes + (outcome,)
        halted = self.halted or (not outcome.success)
        halt_reason = self.halt_reason or (outcome.message if not outcome.success else "")
        return replace(self, outcomes=new_outcomes, halted=halted, halt_reason=halt_reason)

    def with_manifest_update(self, key: str, step: str, entry: dict) -> PipelineState:
        """Return new state with manifest entry updated."""
        new_manifest = dict(self.manifest)
        if key not in new_manifest:
            new_manifest[key] = {}
        new_manifest[key] = dict(new_manifest[key])
        new_manifest[key][step] = entry
        return replace(self, manifest=new_manifest)

    def should_halt(self) -> bool:
        return self.halted

    @property
    def error_count(self) -> int:
        return sum(1 for o in self.outcomes if not o.success)

    @property
    def success_count(self) -> int:
        return sum(1 for o in self.outcomes if o.success)

    def summary(self) -> str:
        """Human-readable summary of pipeline state."""
        lines = [f"Pipeline: {self.success_count} succeeded, {self.error_count} failed"]
        if self.halted:
            lines.append(f"  HALTED: {self.halt_reason}")
        for o in self.outcomes:
            status = "OK" if o.success else "FAIL"
            uni = f" [{o.university_key}]" if o.university_key else ""
            lines.append(f"  {o.step_name}{uni}: {status} — {o.message}")
            for e in o.errors:
                lines.append(f"    ERROR: {e}")
            for w in o.warnings:
                lines.append(f"    WARN: {w}")
        return "\n".join(lines)
