"""Solver adapter tests (spec §8.4, §10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from contracts.common import Classification, ConvergenceStatus
from solvers import ConvergenceFailure, RunContext, get_adapter, registered_names
from solvers.mock.adapter import FIXTURES, MockSolver


@pytest.fixture
def context(tmp_path) -> RunContext:
    return RunContext(run_id="RUN-TEST", work_dir=tmp_path)


def solve(candidate, context, fixture="default"):
    return MockSolver(fixture=fixture).solve(candidate, None, context)


def test_all_adapters_registered():
    assert set(registered_names()) == {"mock", "palace", "openems"}


def test_mock_is_a_test_fixture():
    assert get_adapter("mock").classification is Classification.TEST_FIXTURE


def test_mock_output_is_marked_synthetic(seed_candidate, context):
    results = solve(seed_candidate, context)
    assert results.synthetic is True
    assert any("SYNTHETIC" in note for note in results.notes)


def test_mock_is_deterministic(seed_candidate, context):
    first = solve(seed_candidate, context)
    second = solve(seed_candidate, context)
    assert first.s_parameters == second.s_parameters
    assert first.frequency_GHz == second.frequency_GHz
    assert [m.frequency_GHz for m in first.eigenmodes] == [
        m.frequency_GHz for m in second.eigenmodes
    ]


def test_mock_varies_with_candidate(seed_candidate, context):
    from contracts import Candidate

    payload = seed_candidate.to_ordered_dict()
    payload["parameters"]["vacuum_cavity"]["height_above_chip_mm"] = 1.75
    payload["candidate_id"] = "QMHP-CEM-A-RF-000009"
    other = Candidate.model_validate(payload)

    assert solve(seed_candidate, context).s_parameters != solve(other, context).s_parameters


def test_mock_grid_contains_the_dressed_emission_frequency(seed_candidate, context):
    """The filter gate refuses to interpolate, so this must be exact."""
    results = solve(seed_candidate, context)
    assert 3.395056 in results.frequency_GHz


def test_mock_reports_convergence(seed_candidate, context):
    results = solve(seed_candidate, context)
    assert results.convergence.status is ConvergenceStatus.CONVERGED
    assert results.convergence.tolerance > 0


def test_mock_produces_eigenmodes(seed_candidate, context):
    assert solve(seed_candidate, context).eigenmodes


@pytest.mark.parametrize("fixture", FIXTURES)
def test_every_fixture_produces_valid_results(seed_candidate, context, fixture):
    results = solve(seed_candidate, context, fixture)
    assert results.candidate_id == seed_candidate.candidate_id
    assert any(f"fixture={fixture}" in note for note in results.notes)


def test_filter_fixtures_straddle_the_34dB_boundary(seed_candidate, context):
    from evaluator.base import GateInputs
    from evaluator.computational import P6E2FilterGate
    from contracts.common import GateStatus

    passing = P6E2FilterGate().evaluate(
        GateInputs(seed_candidate, solver_results=solve(seed_candidate, context, "filter_pass"))
    )
    failing = P6E2FilterGate().evaluate(
        GateInputs(seed_candidate, solver_results=solve(seed_candidate, context, "filter_fail"))
    )
    assert passing.status is GateStatus.PASS
    assert failing.status is GateStatus.FAIL


def test_unknown_fixture_rejected():
    with pytest.raises(ValueError, match="unknown mock fixture"):
        MockSolver(fixture="wishful_thinking")


def test_convergence_failure_is_raised(seed_candidate, context, monkeypatch):
    adapter = MockSolver()
    results = adapter.parse(adapter.run(adapter.prepare(seed_candidate, None, context)))
    object.__setattr__(
        results.convergence, "status", ConvergenceStatus.NOT_CONVERGED
    )
    with pytest.raises(ConvergenceFailure):
        adapter.validate_convergence(results)
