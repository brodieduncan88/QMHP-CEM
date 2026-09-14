"""Shared enumerations and base model configuration for QMHP-CEM contracts.

Spec §3: all Python contracts use Pydantic v2, all controlled top-level
records carry a string `schema` field, unknown fields are rejected on core
scientific records, and units are explicit.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Classification(StrEnum):
    """Evidence / value classification (spec §2.2)."""

    MASTER_FROZEN = "MASTER-FROZEN"
    VERIFIED_COMPUTATIONAL = "VERIFIED-COMPUTATIONAL"
    ENGINEERING_SEED = "ENGINEERING-SEED"
    SOLVED = "SOLVED"
    MEASURED = "MEASURED"

    #: CEM-introduced conventions and rules. Not QMHP requirements.
    QMHP_CEM_NORMATIVE = "QMHP-CEM-NORMATIVE"
    ENGINEERING_RULE = "ENGINEERING-RULE"

    #: Deterministic test fixtures (the mock solver, spec §8.4/§10.2).
    TEST_FIXTURE = "TEST_FIXTURE"


#: Evidence classes that may never, on their own, close a hardware gate
#: (spec §2.3). MEASURED is deliberately absent: it is the only class that can.
NON_HARDWARE_EVIDENCE: frozenset[Classification] = frozenset(
    {
        Classification.MASTER_FROZEN,
        Classification.VERIFIED_COMPUTATIONAL,
        Classification.ENGINEERING_SEED,
        Classification.SOLVED,
        Classification.QMHP_CEM_NORMATIVE,
        Classification.ENGINEERING_RULE,
        Classification.TEST_FIXTURE,
    }
)


class GateStatus(StrEnum):
    """Allowed gate statuses (spec §3.4)."""

    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"
    HARDWARE_GATED = "HARDWARE-GATED"
    NOT_EVALUATED = "NOT-EVALUATED"
    NOT_APPLICABLE = "NOT-APPLICABLE"
    EXTRACTION_INCONSISTENT = "EXTRACTION-INCONSISTENT"


class BatchOutcome(StrEnum):
    """Allowed batch outcomes (spec §3.5).

    ``NO_FEASIBLE_DESIGN_FOUND`` is a successful scientific outcome, not a
    software failure (spec §1.2, §12.7).
    """

    FEASIBLE_CANDIDATE_FOUND = "FEASIBLE_CANDIDATE_FOUND"
    NO_FEASIBLE_DESIGN_FOUND = "NO_FEASIBLE_DESIGN_FOUND"
    INCOMPLETE = "INCOMPLETE"
    SOLVER_FAILURE = "SOLVER_FAILURE"
    BLOCKED = "BLOCKED"


class Severity(StrEnum):
    """Whether an optimiser may ever trade a gate away. HARD gates may not."""

    HARD = "HARD"
    SOFT = "SOFT"


class ConvergenceStatus(StrEnum):
    CONVERGED = "CONVERGED"
    NOT_CONVERGED = "NOT_CONVERGED"
    UNKNOWN = "UNKNOWN"


class CandidateState(StrEnum):
    """Candidate lifecycle states (spec §11.2)."""

    DEFINED = "DEFINED"
    VALIDATED = "VALIDATED"
    GEOMETRY_GENERATED = "GEOMETRY_GENERATED"
    SOLVER_INPUT_PREPARED = "SOLVER_INPUT_PREPARED"
    SOLVED = "SOLVED"
    QUANTUM_EVALUATED = "QUANTUM_EVALUATED"
    GATES_EVALUATED = "GATES_EVALUATED"

    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"
    HARDWARE_GATED = "HARDWARE-GATED"


#: Terminal states a candidate may finish in (spec §11.2).
TERMINAL_STATES: frozenset[CandidateState] = frozenset(
    {
        CandidateState.PASS,
        CandidateState.FAIL,
        CandidateState.INCOMPLETE,
        CandidateState.HARDWARE_GATED,
    }
)


class StrictModel(BaseModel):
    """Base for core scientific records.

    ``extra="forbid"`` implements the spec §3 rule that unknown fields are
    rejected on core scientific records.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True, frozen=False)


class FrozenModel(StrictModel):
    """Strict and immutable. Used for records that must not mutate in place."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, frozen=True)
