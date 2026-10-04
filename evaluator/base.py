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
from contracts.results import (
    GateResult,
    QuantumResults,
    SolverResults,
    non_finite_path,
)


class GateInputs:
    """Everything a gate may look at.

    Bundled rather than passed piecemeal so that adding an input does not
    change every gate signature.
    """

    __slots__ = (
        "candidate",
        "solver_results",
        "quantum_results",
        "_bound_candidate_identity",
        "_bound_solver_revision_present",
    )

    def __init__(
        self,
        candidate: Any,  # contracts.Candidate; Any avoids a circular import
        solver_results: SolverResults | None = None,
        quantum_results: QuantumResults | None = None,
    ) -> None:
        self._bound_candidate_identity = _candidate_identity(candidate)
        self._bound_solver_revision_present = bool(
            solver_results is not None
            and solver_results.master_revision is not None
        )
        self.candidate = candidate
        self.solver_results = solver_results
        self.quantum_results = quantum_results
        # The identity check lives here, not only in evaluate_candidate, so no
        # gate can be evaluated on another candidate's evidence by building
        # its inputs directly.
        _validate_gate_inputs(self)

    def validate_identity(self) -> None:
        """Revalidate the construction-bound candidate and current evidence."""
        _validate_gate_inputs(self)


class EvidenceIdentityError(ValueError):
    """Evidence labels do not match the candidate being evaluated."""

    def __init__(
        self,
        source: str,
        field: str,
        evidence_value: object,
        candidate_value: object,
        *,
        expected_label: str = "candidate",
    ) -> None:
        self.source = source
        self.field = field
        self.evidence_value = evidence_value
        self.candidate_value = candidate_value
        super().__init__(
            f"{source} {field} {evidence_value!r} does not match "
            f"{expected_label} {candidate_value!r}"
        )


def _candidate_identity(candidate: Any) -> tuple[object, object] | None:
    if candidate is None:
        return None
    return candidate.candidate_id, candidate.master_revision


def _validate_gate_inputs(inputs: GateInputs) -> None:
    """Non-overridable identity enforcement used at construction and use."""
    if not isinstance(inputs, GateInputs):
        raise TypeError("gate inputs must be a GateInputs instance")
    current = _candidate_identity(inputs.candidate)
    if current != inputs._bound_candidate_identity:
        raise EvidenceIdentityError(
            "gate input",
            "candidate identity",
            current,
            inputs._bound_candidate_identity,
            expected_label="construction-bound candidate identity",
        )
    # Preserve the historical candidate=None mode for standalone gate tests.
    # A candidate that was present at construction cannot be removed because
    # that differs from the bound identity above.
    if inputs.candidate is None:
        return

    current_revision = master.master_revision()
    if inputs.candidate.master_revision != current_revision:
        raise EvidenceIdentityError(
            "candidate",
            "master_revision",
            inputs.candidate.master_revision,
            current_revision,
            expected_label="loaded frozen master",
        )
    if (
        inputs._bound_solver_revision_present
        and inputs.solver_results is not None
        and inputs.solver_results.master_revision is None
    ):
        raise EvidenceIdentityError(
            "solver result",
            "master_revision",
            None,
            inputs.candidate.master_revision,
            expected_label="construction-bound candidate revision",
        )
    require_evidence_identity(
        inputs.candidate, inputs.solver_results, inputs.quantum_results
    )


def require_evidence_identity(
    candidate,  # noqa: ANN001 - contracts.Candidate, avoid circular import
    solver_results: SolverResults | None,
    quantum_results: QuantumResults | None,
) -> None:
    """Refuse evidence that does not belong to ``candidate``.

    Raises ``ValueError`` before any gate runs when a solver or quantum
    record names a different candidate or master revision. A legacy solver
    record without ``master_revision`` is checked on its candidate id only.
    With no candidate there is nothing to attribute the evidence to, so there
    is nothing to check; :func:`evaluator.evaluate_candidate` always passes one.
    """
    if candidate is None:
        return
    if solver_results is not None:
        if solver_results.candidate_id != candidate.candidate_id:
            raise EvidenceIdentityError(
                "solver result",
                "candidate_id",
                solver_results.candidate_id,
                candidate.candidate_id,
                expected_label="candidate",
            )
        if (
            solver_results.master_revision is not None
            and solver_results.master_revision != candidate.master_revision
        ):
            raise EvidenceIdentityError(
                "solver result",
                "master_revision",
                solver_results.master_revision,
                candidate.master_revision,
                expected_label="candidate revision",
            )
    if quantum_results is not None:
        if quantum_results.candidate_id != candidate.candidate_id:
            raise EvidenceIdentityError(
                "quantum result",
                "candidate_id",
                quantum_results.candidate_id,
                candidate.candidate_id,
                expected_label="candidate",
            )
        if quantum_results.master_revision != candidate.master_revision:
            raise EvidenceIdentityError(
                "quantum result",
                "master_revision",
                quantum_results.master_revision,
                candidate.master_revision,
                expected_label="candidate revision",
            )


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

    @property
    def required_evidence(self) -> tuple[Classification, ...]:
        return tuple(
            Classification(value) for value in self.definition["required_evidence"]
        )

    # --- evaluation ---------------------------------------------------------

    @abc.abstractmethod
    def _evaluate(self, inputs: GateInputs) -> GateResult:
        """Produce the gate result. Implemented by each gate."""

    def evaluate(self, inputs: GateInputs) -> GateResult:
        """Evaluate the gate and enforce its frozen status contract."""
        # GateInputs and the Pydantic records it points at remain mutable for
        # compatibility. Recheck at the last common choke point so mutating a
        # label after construction cannot make another candidate's evidence
        # adjudicate this gate.
        _validate_gate_inputs(inputs)

        # Contracts reject non-finite values during ordinary construction.
        # Direct callers can deliberately bypass Pydantic validation with
        # model_construct(), so every computational gate performs one shared
        # fail-closed preflight before its threshold logic. Hardware-only gates
        # do not consume these numeric inputs and do not allow INCOMPLETE in
        # their frozen status vocabulary.
        invalid_path = None
        if GateStatus.INCOMPLETE in self.allowed_statuses:
            for source, value in (
                ("candidate", inputs.candidate),
                ("solver_results", inputs.solver_results),
                ("quantum_results", inputs.quantum_results),
            ):
                if value is not None:
                    invalid_path = non_finite_path(value, source)
                    if invalid_path is not None:
                        break
        if invalid_path is not None:
            result = self._incomplete(
                f"gate inputs contain a non-finite scientific value at "
                f"{invalid_path}; non-finite data cannot close a gate."
            )
        else:
            result = self._evaluate(inputs)
        # A gate implementation must not be able to mutate identity and then
        # return an adjudicating result. This also narrows the window for a
        # concurrent caller mutating a shared evidence object.
        _validate_gate_inputs(inputs)
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
        if result.status in {
            GateStatus.PASS,
            GateStatus.FAIL,
            GateStatus.EXTRACTION_INCONSISTENT,
        }:
            fixture_exception = (
                result.evidence_class is Classification.TEST_FIXTURE
                and inputs.solver_results is not None
                and inputs.solver_results.synthetic
                and inputs.solver_results.solver.classification
                is Classification.TEST_FIXTURE
            )
            if (
                result.evidence_class not in self.required_evidence
                and not fixture_exception
            ):
                raise RuntimeError(
                    f"gate {self.gate_id} emitted adjudicating status "
                    f"{result.status.value} from evidence class "
                    f"{result.evidence_class}; frozen required_evidence is "
                    f"{[value.value for value in self.required_evidence]}. "
                    "Only an explicitly synthetic TEST_FIXTURE solver may "
                    "exercise an adjudicating fixture path."
                )
        if result.severity is not self.severity:
            raise RuntimeError(
                f"gate {self.gate_id} returned severity {result.severity!r}; "
                f"the frozen definition requires {self.severity!r}"
            )
        if result.hardware_required is not self.hardware_required:
            raise RuntimeError(
                f"gate {self.gate_id} returned hardware_required="
                f"{result.hardware_required}; the frozen definition requires "
                f"{self.hardware_required}"
            )
        if result.spec_section != self.spec_section:
            raise RuntimeError(
                f"gate {self.gate_id} returned spec_section "
                f"{result.spec_section!r}; the frozen definition requires "
                f"{self.spec_section!r}"
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
