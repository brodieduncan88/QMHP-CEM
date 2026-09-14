"""Gate tests (spec §12.5)."""

from __future__ import annotations

import pytest

from contracts.common import Classification, GateStatus, Severity
from contracts.results import (
    QUANTUM_RESULTS_SCHEMA,
    SOLVER_RESULTS_SCHEMA,
    QuantumResults,
    SolverResults,
)
from evaluator import evaluate_candidate, roll_up
from evaluator.base import GateInputs
from evaluator.computational import (
    CollisionGate,
    CouplingExtractionGate,
    P6E2FilterGate,
    ToleranceGate,
)
from evaluator.hardware import P0dGate, P1Gate, P3Gate, P5Gate, P6E6JointGate, P7Gate
from models import collision as collision_model

READOUT_GHz = 4.301974466
EMISSION_GHz = 3.395056


def quantum(**blocks) -> QuantumResults:
    payload = {
        "schema": QUANTUM_RESULTS_SCHEMA,
        "candidate_id": "QMHP-CEM-A-RF-000001",
        "master_revision": "v1.5.8f",
        "classification": "SOLVED",
    }
    payload.update(blocks)
    return QuantumResults.model_validate(payload)


def solver_with_stopband(attenuation_dB: float) -> SolverResults:
    return SolverResults.model_validate(
        {
            "schema": SOLVER_RESULTS_SCHEMA,
            "candidate_id": "QMHP-CEM-A-RF-000001",
            "solver": {
                "name": "mock",
                "version": "0.1.0",
                "classification": "TEST_FIXTURE",
            },
            "run_id": "RUN-TEST",
            "convergence": {
                "status": "CONVERGED",
                "metric": "relative_change",
                "value": 1e-4,
                "tolerance": 1e-3,
            },
            "frequency_GHz": [EMISSION_GHz, 5.0],
            "s_parameters": {"S21_dB": [-attenuation_dB, -1.0]},
            "synthetic": True,
        }
    )


# --- COLLISION boundary at 13 MHz (spec §12.5) ------------------------------


@pytest.mark.parametrize(
    ("separation_MHz", "expected"),
    [
        (13.0, GateStatus.PASS),      # exactly at the boundary passes
        (13.001, GateStatus.PASS),
        (20.0, GateStatus.PASS),
        (12.999, GateStatus.FAIL),
        (0.0, GateStatus.FAIL),
    ],
)
def test_collision_boundary(seed_candidate, separation_MHz, expected):
    omega24 = READOUT_GHz + separation_MHz / 1000.0
    result = CollisionGate().evaluate(
        GateInputs(
            seed_candidate,
            quantum_results=quantum(
                collision={"omega24_GHz": omega24, "f_readout_GHz": READOUT_GHz}
            ),
        )
    )
    assert result.status is expected
    assert result.threshold == 13.0
    assert result.units == "MHz"


def test_collision_model_boundary_is_inclusive():
    assert collision_model.passes(READOUT_GHz, READOUT_GHz - 0.013)
    assert not collision_model.passes(READOUT_GHz, READOUT_GHz - 0.0129)


def test_collision_incomplete_without_quantum_results(seed_candidate):
    result = CollisionGate().evaluate(GateInputs(seed_candidate))
    assert result.status is GateStatus.INCOMPLETE


def test_collision_incomplete_when_omega24_missing(seed_candidate):
    result = CollisionGate().evaluate(
        GateInputs(seed_candidate, quantum_results=quantum(collision={}))
    )
    assert result.status is GateStatus.INCOMPLETE


# --- P6E2_FILTER boundaries at 34 / 36 dB (spec §12.5) ----------------------


@pytest.mark.parametrize(
    ("attenuation_dB", "expected", "target_met"),
    [
        (33.9, GateStatus.FAIL, False),
        (34.0, GateStatus.PASS, False),   # minimum met, below design target
        (35.5, GateStatus.PASS, False),
        (36.0, GateStatus.PASS, True),    # design target met
        (40.0, GateStatus.PASS, True),
    ],
)
def test_filter_boundaries(seed_candidate, attenuation_dB, expected, target_met):
    result = P6E2FilterGate().evaluate(
        GateInputs(seed_candidate, solver_results=solver_with_stopband(attenuation_dB))
    )
    assert result.status is expected
    assert result.threshold == 34.0
    assert result.units == "dB"
    if expected is GateStatus.PASS:
        assert ("target met" in result.reason) is target_met


def test_filter_pass_does_not_close_hardware_p6e2(seed_candidate):
    result = P6E2FilterGate().evaluate(
        GateInputs(seed_candidate, solver_results=solver_with_stopband(40.0))
    )
    assert result.status is GateStatus.PASS
    assert "does not close hardware P6-E2" in result.reason
    assert result.hardware_required is False


def test_filter_incomplete_without_sample_at_emission_frequency(seed_candidate):
    results = SolverResults.model_validate(
        {
            "schema": SOLVER_RESULTS_SCHEMA,
            "candidate_id": "QMHP-CEM-A-RF-000001",
            "solver": {
                "name": "mock",
                "version": "0.1.0",
                "classification": "TEST_FIXTURE",
            },
            "run_id": "RUN-TEST",
            "convergence": {
                "status": "CONVERGED",
                "metric": "relative_change",
                "value": 1e-4,
                "tolerance": 1e-3,
            },
            "frequency_GHz": [5.0, 6.0],
            "s_parameters": {"S21_dB": [-40.0, -40.0]},
            "synthetic": True,
        }
    )
    result = P6E2FilterGate().evaluate(GateInputs(seed_candidate, solver_results=results))
    assert result.status is GateStatus.INCOMPLETE


# --- COUPLING_EXTRACTION (spec §5.5, §12.5) ---------------------------------


@pytest.mark.parametrize(
    ("eigenmode", "blackbox", "expected"),
    [
        (100.0, 100.0, GateStatus.PASS),
        (100.0, 105.0, GateStatus.PASS),          # ~4.9% disagreement
        (100.0, 130.0, GateStatus.EXTRACTION_INCONSISTENT),
        (100.0, 60.0, GateStatus.EXTRACTION_INCONSISTENT),
    ],
)
def test_coupling_extraction_consistency(seed_candidate, eigenmode, blackbox, expected):
    result = CouplingExtractionGate().evaluate(
        GateInputs(
            seed_candidate,
            quantum_results=quantum(
                dressed_system={
                    "coupling_extraction": {
                        "eigenmode_MHz": eigenmode,
                        "blackbox_MHz": blackbox,
                    }
                }
            ),
        )
    )
    assert result.status is expected


def test_inconsistent_extraction_is_never_averaged():
    from models.coupling_extraction import CouplingExtraction, ExtractionInconsistent

    extraction = CouplingExtraction(eigenmode_MHz=100.0, blackbox_MHz=130.0)
    with pytest.raises(ExtractionInconsistent):
        extraction.value_MHz()


def test_single_extraction_is_insufficient(seed_candidate):
    result = CouplingExtractionGate().evaluate(
        GateInputs(
            seed_candidate,
            quantum_results=quantum(
                dressed_system={"coupling_extraction": {"eigenmode_MHz": 100.0}}
            ),
        )
    )
    assert result.status is GateStatus.INCOMPLETE


# --- hardware gates never PASS (spec §6.7, §12.5) ---------------------------


HARDWARE_GATES = [P6E6JointGate, P0dGate, P1Gate, P3Gate, P5Gate, P7Gate]


@pytest.mark.parametrize("gate_type", HARDWARE_GATES)
def test_hardware_gate_returns_hardware_gated(seed_candidate, gate_type):
    result = gate_type().evaluate(GateInputs(seed_candidate))
    assert result.status is GateStatus.HARDWARE_GATED
    assert result.hardware_required is True


@pytest.mark.parametrize("gate_type", HARDWARE_GATES)
def test_hardware_gate_cannot_pass_even_with_full_solver_and_quantum_results(
    seed_candidate, gate_type
):
    """No code path may make a hardware gate PASS without MEASURED evidence."""
    result = gate_type().evaluate(
        GateInputs(
            seed_candidate,
            solver_results=solver_with_stopband(60.0),
            quantum_results=quantum(
                collision={"omega24_GHz": 4.5, "f_readout_GHz": READOUT_GHz},
                dressed_system={"root_GHz": READOUT_GHz},
            ),
        )
    )
    assert result.status is not GateStatus.PASS
    assert result.status is GateStatus.HARDWARE_GATED


@pytest.mark.parametrize("gate_type", HARDWARE_GATES)
def test_pass_is_not_among_frozen_allowed_statuses(gate_type):
    assert GateStatus.PASS not in gate_type().allowed_statuses


def test_p6e6_does_not_pass_without_measured_evidence(seed_candidate):
    result = P6E6JointGate().evaluate(GateInputs(seed_candidate))
    assert result.status is GateStatus.HARDWARE_GATED
    assert "MEASURED" in result.reason


def test_gate_cannot_emit_status_outside_frozen_allowed_list(seed_candidate, monkeypatch):
    """Emitting a status the frozen definition forbids is a hard error."""
    from contracts.results import GateResult

    def rogue(self, inputs):
        return GateResult(
            gate_id="P7",
            status=GateStatus.NOT_APPLICABLE,  # not in P7's allowed list
            severity=Severity.HARD,
            reason="rogue",
            hardware_required=True,
        )

    monkeypatch.setattr(P7Gate, "_evaluate", rogue)
    with pytest.raises(RuntimeError, match="not among its frozen allowed statuses"):
        P7Gate().evaluate(GateInputs(seed_candidate))


# --- roll-up ----------------------------------------------------------------


def test_candidate_never_passes_while_hard_gates_unresolved(seed_candidate):
    report = evaluate_candidate(seed_candidate)
    assert report.overall_status is not GateStatus.PASS


def test_full_report_covers_every_registered_gate(seed_candidate):
    from evaluator import GATE_TYPES

    report = evaluate_candidate(seed_candidate)
    assert {g.gate_id for g in report.gates} == {t.gate_id for t in GATE_TYPES}


def test_hard_fail_dominates_roll_up():
    from contracts.results import GateResult

    results = [
        GateResult(
            gate_id="COLLISION",
            status=GateStatus.FAIL,
            severity=Severity.HARD,
            reason="collision",
        ),
        GateResult(
            gate_id="P6E2_FILTER",
            status=GateStatus.PASS,
            severity=Severity.HARD,
            reason="ok",
        ),
    ]
    assert roll_up(results) is GateStatus.FAIL


# --- TOLERANCE reporting ------------------------------------------------------
#
# models.tolerance reports rejection_rate = rejected / screened and returns None
# when nothing could be screened. The gate has to survive that and quote the
# rate against the denominator it was actually computed over.


def _tolerance_block(**overrides) -> dict:
    block = {
        "sample_count": 4,
        "screened_count": 4,
        "unscreened_count": 0,
        "seed": 7,
        "pass_count": 3,
        "fail_count": 1,
        "rejection_rate": 0.25,
        "confidence_interval": [0.05, 0.70],
        "failure_reasons_by_category": {},
    }
    block.update(overrides)
    return block


def _tolerance_result(**overrides):
    return ToleranceGate().evaluate(
        GateInputs(
            candidate=None,
            solver_results=None,
            quantum_results=quantum(tolerance=_tolerance_block(**overrides)),
        )
    )


def test_tolerance_not_evaluated_when_nothing_could_be_screened():
    """A None rejection rate used to raise TypeError out of the format string."""
    result = _tolerance_result(
        screened_count=0, unscreened_count=4, pass_count=0, fail_count=0,
        rejection_rate=None,
    )
    assert result.status is GateStatus.NOT_EVALUATED
    assert "could be screened" in result.reason


def test_tolerance_quotes_the_screened_count_as_the_denominator():
    """The rate is rejected/screened, so 'over N draws' is the wrong basis."""
    result = _tolerance_result(
        screened_count=3, unscreened_count=1, pass_count=2, fail_count=1,
        rejection_rate=1 / 3,
    )
    assert result.status is GateStatus.PASS
    assert "3 screened of 4 draws" in result.reason
    assert "1 unscreened" in result.reason


def test_tolerance_pass_does_not_assert_a_threshold_was_met():
    """TOLERANCE is SOFT and the frozen master sets no rejection-rate threshold.

    A fully rejected ensemble still reports PASS, so the reason must say what
    that PASS does and does not mean rather than let a reader infer compliance.
    """
    result = _tolerance_result(pass_count=0, fail_count=4, rejection_rate=1.0)
    assert result.status is GateStatus.PASS
    assert "no rejection-rate threshold" in result.reason
