"""Candidate lifecycle state machine (spec §11.2).

::

    DEFINED -> VALIDATED -> GEOMETRY_GENERATED -> SOLVER_INPUT_PREPARED
            -> SOLVED -> QUANTUM_EVALUATED -> GATES_EVALUATED
            -> PASS | FAIL | INCOMPLETE | HARDWARE-GATED

Invalid transitions are rejected.
"""

from __future__ import annotations

from contracts.common import TERMINAL_STATES, CandidateState

S = CandidateState

#: Allowed forward transitions. A candidate may also terminate early from any
#: pre-terminal state — an unavailable solver or missing physics ends it as
#: INCOMPLETE rather than letting it proceed on absent evidence.
_ALLOWED: dict[CandidateState, frozenset[CandidateState]] = {
    S.DEFINED: frozenset({S.VALIDATED, S.INCOMPLETE, S.FAIL}),
    S.VALIDATED: frozenset({S.GEOMETRY_GENERATED, S.INCOMPLETE, S.FAIL}),
    S.GEOMETRY_GENERATED: frozenset({S.SOLVER_INPUT_PREPARED, S.INCOMPLETE, S.FAIL}),
    S.SOLVER_INPUT_PREPARED: frozenset({S.SOLVED, S.INCOMPLETE, S.FAIL}),
    S.SOLVED: frozenset({S.QUANTUM_EVALUATED, S.INCOMPLETE, S.FAIL}),
    S.QUANTUM_EVALUATED: frozenset({S.GATES_EVALUATED, S.INCOMPLETE, S.FAIL}),
    S.GATES_EVALUATED: frozenset(
        {S.PASS, S.FAIL, S.INCOMPLETE, S.HARDWARE_GATED}
    ),
}


class InvalidTransition(RuntimeError):
    """An illegal candidate lifecycle transition was attempted."""

    def __init__(self, current: CandidateState, requested: CandidateState) -> None:
        allowed = sorted(s.value for s in _ALLOWED.get(current, frozenset()))
        super().__init__(
            f"invalid candidate transition {current.value} -> {requested.value}; "
            f"allowed from {current.value}: {allowed or '(terminal state)'}"
        )


def can_transition(current: CandidateState, requested: CandidateState) -> bool:
    return requested in _ALLOWED.get(current, frozenset())


class CandidateLifecycle:
    """Tracks one candidate's state and rejects invalid transitions."""

    def __init__(self, candidate_id: str) -> None:
        self.candidate_id = candidate_id
        self.state = S.DEFINED
        self.history: list[CandidateState] = [S.DEFINED]

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def to(self, requested: CandidateState) -> CandidateState:
        if not can_transition(self.state, requested):
            raise InvalidTransition(self.state, requested)
        self.state = requested
        self.history.append(requested)
        return self.state
