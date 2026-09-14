"""Contract tests (spec §12.2)."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from contracts import Candidate, GateReport, SolverResults
from contracts.candidate import CANDIDATE_SCHEMA, candidate_id
from contracts.common import Classification, GateStatus, Severity
from contracts.results import (
    GATE_REPORT_SCHEMA,
    SOLVER_RESULTS_SCHEMA,
    GateResult,
    QuantumResults,
)


# --- round trips ------------------------------------------------------------


def test_candidate_round_trip(seed_candidate):
    payload = seed_candidate.to_ordered_dict()
    assert Candidate.model_validate(payload) == seed_candidate


def test_candidate_id_format():
    assert candidate_id(1) == "QMHP-CEM-A-RF-000001"
    assert candidate_id(9) == "QMHP-CEM-A-RF-000009"
    with pytest.raises(ValueError):
        candidate_id(0)


# --- schema field -----------------------------------------------------------


def test_missing_schema_rejected(seed_candidate):
    payload = seed_candidate.to_ordered_dict()
    del payload["schema"]
    with pytest.raises(ValidationError):
        Candidate.model_validate(payload)


def test_wrong_schema_rejected(seed_candidate):
    payload = seed_candidate.to_ordered_dict()
    payload["schema"] = "qmhp-cem.candidate/9.9.9"
    with pytest.raises(ValidationError):
        Candidate.model_validate(payload)


def test_unknown_core_field_rejected(seed_candidate):
    payload = seed_candidate.to_ordered_dict()
    payload["surprise"] = 1
    with pytest.raises(ValidationError):
        Candidate.model_validate(payload)


# --- candidate dimension validation (spec §3.1) -----------------------------


@pytest.fixture
def payload(seed_candidate):
    return seed_candidate.to_ordered_dict()


def test_invalid_candidate_id_rejected(payload):
    payload["candidate_id"] = "NOT-AN-ID"
    with pytest.raises(ValidationError, match="does not match"):
        Candidate.model_validate(payload)


def test_negative_dimension_rejected(payload):
    payload["parameters"]["chip"]["width_mm"] = -1.0
    with pytest.raises(ValidationError):
        Candidate.model_validate(payload)


def test_zero_dimension_rejected(payload):
    payload["parameters"]["lid"]["thickness_mm"] = 0.0
    with pytest.raises(ValidationError):
        Candidate.model_validate(payload)


def test_recess_must_fit_inside_package(payload):
    payload["parameters"]["package"]["outer_width_mm"] = 10.0
    payload["parameters"]["package"]["outer_height_mm"] = 10.0
    with pytest.raises(ValidationError, match="does not fit"):
        Candidate.model_validate(payload)


def test_body_height_must_exceed_floor_thickness(payload):
    payload["parameters"]["package"]["floor_thickness_mm"] = 5.0
    with pytest.raises(ValidationError, match="must exceed"):
        Candidate.model_validate(payload)


def test_cavity_must_leave_positive_walls(payload):
    payload["parameters"]["vacuum_cavity"]["width_mm"] = 40.0
    with pytest.raises(ValidationError, match="positive package wall"):
        Candidate.model_validate(payload)


def test_cavity_must_enclose_recess(payload):
    payload["parameters"]["vacuum_cavity"]["width_mm"] = 15.0
    payload["parameters"]["vacuum_cavity"]["height_mm"] = 15.0
    with pytest.raises(ValidationError, match="enclose the chip recess"):
        Candidate.model_validate(payload)


def test_recess_must_accommodate_chip_thickness(payload):
    payload["parameters"]["chip_recess"]["depth_mm"] = 0.1
    with pytest.raises(ValidationError, match="shallower than the"):
        Candidate.model_validate(payload)


def test_unsupported_launch_count_rejected(payload):
    payload["parameters"]["launches"]["count"] = 3
    with pytest.raises(ValidationError, match="not supported"):
        Candidate.model_validate(payload)


def test_units_are_explicit_on_every_geometric_dimension(seed_candidate):
    """No unitless geometric dimensions (spec §3.1)."""
    unitless = {"count", "hole_count"}
    for group_name, group in seed_candidate.to_ordered_dict()["parameters"].items():
        for field_name in group:
            if field_name in unitless:
                continue
            assert field_name.endswith("_mm"), (
                f"parameters.{group_name}.{field_name} carries no unit suffix"
            )


# --- solver results ---------------------------------------------------------


def _solver_payload(**overrides):
    payload = {
        "schema": SOLVER_RESULTS_SCHEMA,
        "candidate_id": "QMHP-CEM-A-RF-000001",
        "solver": {"name": "mock", "version": "0.1.0", "classification": "TEST_FIXTURE"},
        "run_id": "RUN-TEST",
        "convergence": {
            "status": "CONVERGED",
            "metric": "relative_change",
            "value": 1e-4,
            "tolerance": 1e-3,
        },
        "frequency_GHz": [3.0, 4.0],
        "s_parameters": {"S21_dB": [-1.0, -2.0]},
        "synthetic": True,
    }
    payload.update(overrides)
    return payload


def test_solver_results_require_convergence():
    """A solver result without convergence metadata must fail (spec §3.2)."""
    payload = _solver_payload()
    del payload["convergence"]
    with pytest.raises(ValidationError):
        SolverResults.model_validate(payload)


def test_solver_results_accept_valid_payload():
    assert SolverResults.model_validate(_solver_payload()).run_id == "RUN-TEST"


def test_sparameter_length_must_match_frequency_grid():
    payload = _solver_payload(s_parameters={"S21_dB": [-1.0]})
    with pytest.raises(ValidationError, match="frequency grid"):
        SolverResults.model_validate(payload)


def test_frequency_grid_must_ascend():
    payload = _solver_payload(frequency_GHz=[4.0, 3.0])
    with pytest.raises(ValidationError, match="ascending"):
        SolverResults.model_validate(payload)


def test_test_fixture_must_be_marked_synthetic():
    payload = _solver_payload(synthetic=False)
    with pytest.raises(ValidationError, match="synthetic"):
        SolverResults.model_validate(payload)


# --- quantum results --------------------------------------------------------


def test_quantum_results_cannot_be_measured():
    """v0.1 does not manufacture MEASURED values (spec §2.2)."""
    with pytest.raises(ValidationError, match="MEASURED"):
        QuantumResults.model_validate(
            {
                "schema": "qmhp-cem.quantum-results/0.1.0",
                "candidate_id": "QMHP-CEM-A-RF-000001",
                "master_revision": "v1.5.8f",
                "classification": "MEASURED",
            }
        )


# --- gate report ------------------------------------------------------------


def test_duplicate_gate_ids_rejected():
    gate = {
        "gate_id": "COLLISION",
        "status": "INCOMPLETE",
        "severity": "HARD",
        "reason": "x",
    }
    with pytest.raises(ValidationError, match="duplicate"):
        GateReport.model_validate(
            {
                "schema": GATE_REPORT_SCHEMA,
                "candidate_id": "QMHP-CEM-A-RF-000001",
                "master_revision": "v1.5.8f",
                "overall_status": "INCOMPLETE",
                "gates": [gate, copy.deepcopy(gate)],
            }
        )


def test_hardware_gate_cannot_be_constructed_as_pass_without_measured():
    """The contract layer itself refuses this (spec §2.3)."""
    with pytest.raises(ValidationError, match="MEASURED"):
        GateResult(
            gate_id="P7",
            status=GateStatus.PASS,
            severity=Severity.HARD,
            evidence_class=Classification.SOLVED,
            reason="simulated advantage",
            hardware_required=True,
        )


def test_hardware_gate_pass_allowed_only_with_measured_evidence():
    result = GateResult(
        gate_id="P7",
        status=GateStatus.PASS,
        severity=Severity.HARD,
        evidence_class=Classification.MEASURED,
        reason="hypothetical future measured evidence object",
        hardware_required=True,
    )
    assert result.status is GateStatus.PASS


def test_computational_gate_may_pass_on_solved_evidence():
    result = GateResult(
        gate_id="COLLISION",
        status=GateStatus.PASS,
        severity=Severity.HARD,
        evidence_class=Classification.SOLVED,
        reason="clear",
        hardware_required=False,
    )
    assert result.status is GateStatus.PASS
