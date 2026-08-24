"""Candidate evaluator (spec §6, §11.2).

Runs every registered gate against a candidate and rolls the results up into a
single :class:`contracts.results.GateReport`.
"""

from __future__ import annotations

from contracts.common import GateStatus, Severity
from contracts.results import GATE_REPORT_SCHEMA, GateReport, QuantumResults, SolverResults
from evaluator.base import Gate, GateInputs
from evaluator.computational import (
    CollisionGate,
    CouplingExtractionGate,
    P4PreSpectralGate,
    P6E2FilterGate,
    ToleranceGate,
)
from evaluator.hardware import (
    P0dGate,
    P1Gate,
    P3Gate,
    P5Gate,
    P6E6JointGate,
    P7Gate,
)

#: Registered gates, in report order: computational first, then hardware.
GATE_TYPES: tuple[type[Gate], ...] = (
    CollisionGate,
    P6E2FilterGate,
    P4PreSpectralGate,
    ToleranceGate,
    CouplingExtractionGate,
    P6E6JointGate,
    P0dGate,
    P1Gate,
    P3Gate,
    P5Gate,
    P7Gate,
)


def evaluate_candidate(
    candidate,  # noqa: ANN001 - contracts.Candidate
    solver_results: SolverResults | None = None,
    quantum_results: QuantumResults | None = None,
) -> GateReport:
    """Evaluate all gates for a candidate."""
    inputs = GateInputs(candidate, solver_results, quantum_results)
    results = [gate_type().evaluate(inputs) for gate_type in GATE_TYPES]

    return GateReport.model_validate(
        {
            "schema": GATE_REPORT_SCHEMA,
            "candidate_id": candidate.candidate_id,
            "master_revision": candidate.master_revision,
            "overall_status": roll_up(results).value,
            "gates": [r.model_dump() for r in results],
        }
    )


def roll_up(results) -> GateStatus:  # noqa: ANN001 - list[GateResult]
    """Roll individual gate results into an overall candidate status.

    Precedence, strictest first:

    1. any HARD gate FAIL                  -> FAIL
    2. any EXTRACTION-INCONSISTENT         -> EXTRACTION-INCONSISTENT
    3. any HARD gate INCOMPLETE            -> INCOMPLETE
    4. any HARD gate unclosed by hardware  -> HARDWARE-GATED
    5. otherwise                           -> PASS

    A candidate is never PASS while a HARD gate is unresolved. Soft gates
    inform but do not by themselves fail a candidate.
    """
    hard = [r for r in results if r.severity is Severity.HARD]

    if any(r.status is GateStatus.FAIL for r in hard):
        return GateStatus.FAIL
    if any(r.status is GateStatus.EXTRACTION_INCONSISTENT for r in results):
        return GateStatus.EXTRACTION_INCONSISTENT
    if any(r.status in (GateStatus.INCOMPLETE, GateStatus.NOT_EVALUATED) for r in hard):
        return GateStatus.INCOMPLETE
    if any(r.status is GateStatus.HARDWARE_GATED for r in hard):
        return GateStatus.HARDWARE_GATED
    return GateStatus.PASS
