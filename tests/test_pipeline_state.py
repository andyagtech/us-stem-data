"""Tests for the immutable pipeline state types.

Verifies that the functional architecture enforces immutability
and correct state transitions.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pipeline.state import PipelineState, PipelineConfig, StepOutcome, UniversityConfig


class TestStepOutcome:

    def test_ok_factory(self):
        o = StepOutcome.ok('harvest', message='Done', data={'count': 100})
        assert o.success is True
        assert o.step_name == 'harvest'
        assert o.data == {'count': 100}
        assert o.errors == ()

    def test_err_factory(self):
        o = StepOutcome.err('harvest', message='Failed', errors=('timeout',))
        assert o.success is False
        assert o.errors == ('timeout',)

    def test_outcome_is_frozen(self):
        o = StepOutcome.ok('test')
        try:
            o.success = False
            assert False, "Should not allow mutation"
        except AttributeError:
            pass


class TestPipelineState:

    def _make_state(self):
        config = PipelineConfig(
            universities={},
            entity_map={},
            base_dir=os.getcwd(),
            raw_dir=os.path.join(os.getcwd(), 'data'),
            processed_dir=os.path.join(os.getcwd(), 'data', 'processed'),
            site_dir=os.path.join(os.getcwd(), 'site'),
        )
        return PipelineState(
            config=config,
            outcomes=(),
            manifest={},
        )

    def test_initial_state_not_halted(self):
        state = self._make_state()
        assert state.halted is False
        assert state.should_halt() is False

    def test_with_outcome_appends(self):
        state = self._make_state()
        outcome = StepOutcome.ok('harvest', message='Done')
        new_state = state.with_outcome(outcome)
        assert len(new_state.outcomes) == 1
        assert len(state.outcomes) == 0  # Original unchanged

    def test_failure_halts_pipeline(self):
        state = self._make_state()
        failure = StepOutcome.err('harvest', message='Failed')
        new_state = state.with_outcome(failure)
        assert new_state.halted is True
        assert new_state.should_halt() is True

    def test_success_does_not_halt(self):
        state = self._make_state()
        success = StepOutcome.ok('harvest')
        new_state = state.with_outcome(success)
        assert new_state.halted is False

    def test_state_is_frozen(self):
        state = self._make_state()
        try:
            state.halted = True
            assert False, "Should not allow mutation"
        except AttributeError:
            pass

    def test_manifest_update_returns_new_state(self):
        state = self._make_state()
        new_state = state.with_manifest_update('mit', 'harvest', {'records': 100})
        assert 'mit' in new_state.manifest
        assert 'mit' not in state.manifest  # Original unchanged

    def test_summary(self):
        state = self._make_state()
        state = state.with_outcome(StepOutcome.ok('harvest'))
        state = state.with_outcome(StepOutcome.ok('process'))
        summary = state.summary()
        assert '2 succeeded' in summary
        assert '0 failed' in summary


class TestUniversityConfig:

    def test_from_dict(self):
        d = {
            'name': 'MIT',
            'nra': 43.8,
            'unitid': 166683,
            'harvest': {'oai_base': 'https://example.com'},
            'processing': {'file': 'data/mit.csv'},
            'employer_names': ['MASSACHUSETTS INSTITUTE OF TECHNOLOGY'],
        }
        config = UniversityConfig.from_dict('mit', d)
        assert config.key == 'mit'
        assert config.name == 'MIT'
        assert config.nra == 43.8
        assert config.unitid == 166683

    def test_from_dict_defaults(self):
        config = UniversityConfig.from_dict('test', {'name': 'Test U'})
        assert config.nra == 0
        assert config.unitid is None
        assert config.harvest == {}
        assert config.employer_names == []
