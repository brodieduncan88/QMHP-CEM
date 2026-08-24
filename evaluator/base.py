"""Gate base machinery (spec §6.1).

Every gate is constructed from its frozen definition in
``master/validation_gates.yaml``. Gates may not invent their own thresholds,
severities or allowed statuses in code — that would put authority level 4
above level 3 (spec §2.1).
"""

from __future__ import annotations

import abc
from typing import Any, Mapping

from contracts import master
from contracts.common import Classification, GateStatus, Severity
from contracts.results import GateResult, QuantumResults, SolverResults


class GateInputs:
    """Everything a gate may look at.

    Bundled rather than passed piecemeal so that adding an input does not
    change every gate signature.
    """

    def __init__(
        self,
        candidate,  # noqa: ANN001 - contracts.Candidate, avoid circular import
        solver_results: SolverResults | None = None,
        quantum_results: QuantumResults | None = None,
    ) -> None:
        self.candidate = candidate
        self.solver_results = solver_results
        self.quantum_results = quantum_results


class Gate(abc.ABC):
    """A single validation gate."""

    #: Must match a ``gate_id`` in master/validation_gates.yaml.
    gate_id: str

    def __init__(self) -> None:
        self.definition: Mapping[str, Any] = master.gate_definition(self.gate_id)

    # --- frozen properties, read from master/ ------------------------------

    @property
    def severity(self) -> Severity:
        return Severity(self.definition["severity"])

    @property
    def spec_section(self) -> str:
        return str(self.definition["spec_section"])

    @property
    def hardware_required(self) -> bool:
        return bool(self.definition["hardware_required"])

    @property
    def allowed_statuses(self) -> tuple[GateStatus, ...]:
        return tuple(GateStatus(s) for s in self.definition["allowed_statuses"])

    # --- evaluation ---------------------------------------------------------

    @abc.abstractmethod
    def _evaluate(self, inputs: GateInputs) -> GateResult:
        """Produce the gate result. Implemented by each gate."""

    def evaluate(self, inputs: GateInputs) -> GateResult:
        """Evaluate the gate and enforce its frozen status contract."""
        result = self._evaluate(inputs)
        if result.gate_id != self.gate_id:
            raise RuntimeError(
                f"gate {type(self).__name__} returned gate_id {result.gate_id!r}"
            )
        if result.status not in self.allowed_statuses:
            raise RuntimeError(
                f"gate {self.gate_id} emitted status {result.status!r}, which is "
                f"not among its frozen allowed statuses "
                f"{[s.value for s in self.allowed_statuses]} "
                f"(master/validation_gates.yaml)"
            )
        return result

    # --- helpers ------------------------------------------------------------

    def _result(
        self,
        status: GateStatus,
        reason: str,
        *,
        evidence_class: Classification | None = None,
        measured: float | None = None,
        threshold: float | None = None,
        units: str | None = None,
        margin: float | None = None,
    ) -> GateResult:
        return GateResult(
            gate_id=self.gate_id,
            status=status,
            severity=self.severity,
            evidence_class=evidence_class,
            measured=measured,
            threshold=threshold,
            units=units,
            margin=margin,
            reason=reason,
            spec_section=self.spec_section,
            hardware_required=self.hardware_required,
        )

    def _incomplete(self, reason: str) -> GateResult:
        return self._result(GateStatus.INCOMPLETE, reason)

    def _not_evaluated(self, reason: str) -> GateResult:
        return self._result(GateStatus.NOT_EVALUATED, reason)


class HardwareGate(Gate):
    """A gate that only measured hardware evidence can close (spec §6.7).

    v0.1 manufactures no ``MEASURED`` evidence objects, so these gates return
    ``HARDWARE-GATED`` unconditionally. The contract layer independently
    refuses to construct a PASS for a hardware-required gate on non-measured
    evidence (:class:`contracts.results.GateResult`), so this cannot be
    defeated by a subclass returning the wrong thing.
    """

    #: Human-readable description of what the gate needs.
    requires: str = "measured hardware evidence"

    def _evaluate(self, inputs: GateInputs) -> GateResult:
        return self._result(
            GateStatus.HARDWARE_GATED,
            reason=(
                f"{self.definition['title']} requires {self.requires}. "
                f"QMHP-CEM v0.1 does not manufacture MEASURED values, so this "
                f"gate cannot be closed computationally (spec §2.3, §6.7)."
            ),
        )
