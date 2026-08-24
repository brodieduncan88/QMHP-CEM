"""QMHP-CEM solver adapters (spec §10).

All solvers expose the same boundary: prepare -> run -> parse ->
validate_convergence -> SolverResults.

Two rules are absolute:

* convergence metadata is mandatory on every result (spec §3.2);
* a requested solver that cannot execute fails clearly and is NEVER silently
  replaced by another (spec §10.5).
"""

from solvers.adapter import (
    ConvergenceFailure,
    PreparedInput,
    RunContext,
    SolverAdapter,
    SolverUnavailable,
    get_adapter,
    registered_names,
)

__all__ = [
    "ConvergenceFailure",
    "PreparedInput",
    "RunContext",
    "SolverAdapter",
    "SolverUnavailable",
    "get_adapter",
    "registered_names",
]
