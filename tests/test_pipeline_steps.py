"""The pipeline steps themselves. Nothing imported them before 2026-08-22.

Every existing suite checks DOWNSTREAM artifacts -- the built site, the JSON,
the published figures. That leaves the machinery producing them untested, and
it is where the expensive failures have actually happened:

  * step6_deploy reported success=True inside `if errors:`, so a deploy that
    uploaded no JSON at all printed "1 succeeded, 0 failed".
  * step1_harvest hardcoded success=True while collecting errors from four
    sites, so a harvest where every repository failed reported OK.
  * step2_process caught ImportError on duckdb, printed a warning, returned,
    and let the step pass -- shipping a four-month-old Parquet export.

All three are the same defect: the failure was observed and then discarded.
These tests assert the railway holds, using no network, no AWS and no data.
"""
from __future__ import annotations

import ast
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.state import PipelineState, StepOutcome   # noqa: E402

STEP_FILES = sorted((ROOT / "pipeline").glob("step*.py"))
# Exposes no step function and is absent from the registry in __main__.py.
NON_STEPS = {"step2b_ai_classify"}


def _outcome(success: bool, name: str = "t") -> StepOutcome:
    return StepOutcome(step_name=name, university_key="", success=success,
                       message="m", data={}, errors=(), warnings=(),
                       timestamp=datetime.now(timezone.utc).isoformat())


class TestRailway:
    """with_outcome must switch tracks, and should_halt must stay switched."""

    def _state(self):
        """A minimal real config. PipelineConfig is a frozen dataclass with six
        required fields; none are touched by the railway logic under test."""
        from pipeline.state import PipelineConfig
        cfg = PipelineConfig(
            universities={}, entity_map={}, base_dir=ROOT,
            raw_dir=ROOT / "data", processed_dir=ROOT / "data" / "processed",
            site_dir=ROOT / "site")
        return PipelineState(config=cfg, outcomes=(), manifest={})

    def test_success_does_not_halt(self):
        s = self._state().with_outcome(_outcome(True))
        assert not s.should_halt()

    def test_failure_halts(self):
        s = self._state().with_outcome(_outcome(False))
        assert s.should_halt()

    def test_halt_is_sticky(self):
        """A later success must NOT clear an earlier failure."""
        s = self._state().with_outcome(_outcome(False)).with_outcome(_outcome(True))
        assert s.should_halt(), "a success after a failure un-halted the pipeline"

    def test_halt_reason_is_kept(self):
        s = self._state().with_outcome(_outcome(False))
        assert s.halt_reason, "halted with no reason recorded"

    def test_state_is_immutable(self):
        a = self._state()
        b = a.with_outcome(_outcome(True))
        assert a is not b and a.outcomes == ()


class TestStepsCanFail:
    """Each real step must be able to signal onto the failure track.

    An AST check, not a grep: grepping `success=False` missed both computed
    conditions (`success=len(errors) == 0`) and the StepOutcome.err()
    constructor, and produced a confident wrong claim that six of eight steps
    could not fail.
    """

    @pytest.mark.parametrize("path", STEP_FILES, ids=lambda p: p.stem)
    def test_step_can_report_failure(self, path):
        if path.stem in NON_STEPS:
            pytest.skip(f"{path.stem} is a standalone CLI, not a pipeline step")
        kinds = set()
        for n in ast.walk(ast.parse(path.read_text())):
            if not isinstance(n, ast.Call):
                continue
            fn = ast.unparse(n.func)
            if "StepOutcome" not in fn:
                continue
            if fn.endswith(".ok"):
                kinds.add("ok")
            elif fn.endswith(".err"):
                kinds.add("err")
            else:
                kw = {k.arg: ast.unparse(k.value) for k in n.keywords}
                kinds.add("success=" + kw.get("success", "?"))
        can_fail = any(
            k == "err" or (k.startswith("success=")
                           and k not in ("success=True", "success=?"))
            for k in kinds)
        assert can_fail, (
            f"{path.stem} only ever reports success ({sorted(kinds)}). A step "
            f"that cannot fail makes every downstream step run on bad data.")

    @pytest.mark.parametrize("path", STEP_FILES, ids=lambda p: p.stem)
    def test_step_reads_the_halt_track(self, path):
        if path.stem in NON_STEPS:
            pytest.skip(f"{path.stem} is a standalone CLI, not a pipeline step")
        assert "should_halt()" in path.read_text(), (
            f"{path.stem} never checks should_halt(), so it runs even after an "
            f"upstream step has failed.")


class TestDeployLock:
    """The deploy mutex. Two concurrent syncs into one bucket can interleave."""

    def test_second_acquire_is_refused(self, tmp_path):
        from pipeline.step6_deploy import _DeployLock
        p = tmp_path / "d.lock"
        a = _DeployLock(p); a.acquire()
        try:
            with pytest.raises(RuntimeError):
                _DeployLock(p).acquire()
        finally:
            a.release()

    def test_release_allows_reacquire(self, tmp_path):
        from pipeline.step6_deploy import _DeployLock
        p = tmp_path / "d.lock"
        a = _DeployLock(p); a.acquire(); a.release()
        b = _DeployLock(p); b.acquire(); b.release()

    def test_refusal_does_not_erase_the_holder(self, tmp_path):
        """Opening with "w" truncated the file before flock was attempted, so a
        refused deploy erased the pid it was meant to report."""
        from pipeline.step6_deploy import _DeployLock
        p = tmp_path / "d.lock"
        a = _DeployLock(p); a.acquire()
        held = p.read_text()
        try:
            with pytest.raises(RuntimeError):
                _DeployLock(p).acquire()
            assert p.read_text() == held, "a refused acquire wiped the holder's pid"
        finally:
            a.release()
