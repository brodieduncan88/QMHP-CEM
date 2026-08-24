"""Common solver adapter boundary (spec §10.1).

Conceptual operations::

    prepare(candidate, geometry, run_context)
    run(prepared_input)
    parse(raw_output)
    validate_convergence(parsed_output)
    -> SolverResults

Rule §10.5: no silent substitution. If a named solver is requested and cannot
execute, the run fails clearly. It must never fall back to the mock.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contracts.common import Classification, ConvergenceStatus
from contracts.results import SolverResults


class SolverUnavailable(RuntimeError):
    """A requested solver cannot execute in this environment.

    Raised instead of falling back to another solver (spec §10.5).
    """

    def __init__(self, solver: str, reason: str, remedy: str = "") -> None:
        self.solver = solver
        self.reason = reason
        message = (
            f"solver {solver!r} cannot execute: {reason}. "
            f"QMHP-CEM will not silently substitute another solver (spec §10.5)."
        )
        if remedy:
            message += f" {remedy}"
        super().__init__(message)


class ConvergenceFailure(RuntimeError):
    """A solver produced output that did not meet its convergence criterion."""


@dataclass
class RunContext:
    """Everything a solver run needs that is not the candidate itself."""

    run_id: str
    work_dir: Path
    frequency_start_GHz: float = 3.0
    frequency_stop_GHz: float = 5.0
    frequency_points: int = 401
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreparedInput:
    """Solver-specific input produced by :meth:`SolverAdapter.prepare`."""

    candidate_id: str
    run_id: str
    work_dir: Path
    payload: dict[str, Any] = field(default_factory=dict)
    input_files: list[Path] = field(default_factory=list)


class SolverAdapter(abc.ABC):
    """Base class for all solver adapters."""

    #: Adapter name as used on the command line, e.g. ``"mock"``.
    name: str
    #: Adapter version, recorded in every result.
    version: str
    #: Evidence classification of the values this adapter produces.
    classification: Classification

    # --- §10.1 interface ----------------------------------------------------

    @abc.abstractmethod
    def prepare(self, candidate, geometry, run_context: RunContext) -> PreparedInput:  # noqa: ANN001
        """Build solver input from a candidate and its geometry."""

    @abc.abstractmethod
    def run(self, prepared: PreparedInput) -> Any:
        """Execute the solver and return its raw output."""

    @abc.abstractmethod
    def parse(self, raw_output: Any) -> SolverResults:
        """Parse raw solver output into typed results."""

    def validate_convergence(self, results: SolverResults) -> SolverResults:
        """Reject results that did not converge.

        Convergence metadata is mandatory (spec §3.2); the contract already
        refuses to build a ``SolverResults`` without it, so this checks the
        status rather than the presence of the block.
        """
        if results.convergence.status is not ConvergenceStatus.CONVERGED:
            raise ConvergenceFailure(
                f"solver {self.name!r} reported convergence status "
                f"{results.convergence.status.value} for candidate "
                f"{results.candidate_id}: {results.convergence.metric}="
                f"{results.convergence.value} against tolerance "
                f"{results.convergence.tolerance}."
            )
        return results

    # --- convenience --------------------------------------------------------

    def solve(self, candidate, geometry, run_context: RunContext) -> SolverResults:  # noqa: ANN001
        """prepare -> run -> parse -> validate_convergence."""
        prepared = self.prepare(candidate, geometry, run_context)
        raw = self.run(prepared)
        parsed = self.parse(raw)
        return self.validate_convergence(parsed)

    def preflight(self) -> None:
        """Raise :class:`SolverUnavailable` if this solver cannot run here.

        Called before a batch starts so an unavailable solver fails before any
        candidate is processed, rather than midway through.
        """
        return None


# --- registry ---------------------------------------------------------------

_REGISTRY: dict[str, type[SolverAdapter]] = {}


def register(adapter_type: type[SolverAdapter]) -> type[SolverAdapter]:
    _REGISTRY[adapter_type.name] = adapter_type
    return adapter_type


def get_adapter(name: str) -> SolverAdapter:
    """Instantiate a registered adapter by name.

    Raises:
        SolverUnavailable: if the name is not registered. Never falls back.
    """
    # Import for side-effect registration; kept local to avoid import cycles.
    from solvers import mock, openems, palace  # noqa: F401

    if name not in _REGISTRY:
        raise SolverUnavailable(
            name,
            f"no adapter named {name!r} is registered",
            f"Registered adapters: {sorted(_REGISTRY)}.",
        )
    return _REGISTRY[name]()


def registered_names() -> list[str]:
    from solvers import mock, openems, palace  # noqa: F401

    return sorted(_REGISTRY)
