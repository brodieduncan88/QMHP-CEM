"""QMHP-CEM data contracts (spec §3).

Authority level 4 (code). This layer defines typed records; it never defines
scientific requirements. Frozen requirements live in ``master/`` and are read
through :mod:`contracts.master`.
"""

from contracts.candidate import (
    Candidate,
    CandidateParameters,
    candidate_id,
    utc_now,
)
from contracts.common import (
    BatchOutcome,
    CandidateState,
    Classification,
    ConvergenceStatus,
    GateStatus,
    Severity,
    TERMINAL_STATES,
)
from contracts.results import (
    Artifact,
    BatchReport,
    Convergence,
    Eigenmode,
    EnvironmentRecord,
    GateReport,
    GateResult,
    QuantumResults,
    SolverIdentity,
    SolverResults,
)
from contracts.sweep import SweepDefinition

__all__ = [
    "Artifact",
    "BatchOutcome",
    "BatchReport",
    "Candidate",
    "CandidateParameters",
    "CandidateState",
    "Classification",
    "Convergence",
    "ConvergenceStatus",
    "Eigenmode",
    "EnvironmentRecord",
    "GateReport",
    "GateResult",
    "GateStatus",
    "QuantumResults",
    "Severity",
    "SolverIdentity",
    "SolverResults",
    "SweepDefinition",
    "TERMINAL_STATES",
    "candidate_id",
    "utc_now",
]
