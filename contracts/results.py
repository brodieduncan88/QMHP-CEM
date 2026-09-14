"""Solver, quantum, gate and batch result contracts (spec §3.2 – §3.5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from contracts.common import (
    BatchOutcome,
    Classification,
    ConvergenceStatus,
    GateStatus,
    Severity,
    StrictModel,
)

SOLVER_RESULTS_SCHEMA = "qmhp-cem.solver-results/0.1.0"
QUANTUM_RESULTS_SCHEMA = "qmhp-cem.quantum-results/0.1.0"
GATE_REPORT_SCHEMA = "qmhp-cem.gate-report/0.1.0"
BATCH_REPORT_SCHEMA = "qmhp-cem.batch-report/0.1.0"


# --- §3.2 SolverResults -----------------------------------------------------


class SolverIdentity(StrictModel):
    name: str
    version: str
    classification: Classification
    #: Container image digest where available (spec §10.3).
    image_digest: str | None = None
    command_line: str | None = None


class Convergence(StrictModel):
    """Mandatory convergence metadata (spec §3.2).

    A solver result without this block must fail validation.
    """

    status: ConvergenceStatus
    metric: str
    value: float
    tolerance: float


class Eigenmode(StrictModel):
    frequency_GHz: float = Field(gt=0)
    quality_factor: float | None = Field(default=None, gt=0)
    label: str | None = None


class Artifact(StrictModel):
    path: str
    sha256: str
    role: str


class SolverResults(StrictModel):
    schema_: Literal[SOLVER_RESULTS_SCHEMA] = Field(alias="schema")
    candidate_id: str
    solver: SolverIdentity
    run_id: str
    #: Mandatory. Omitting it is a validation error, by construction.
    convergence: Convergence
    frequency_GHz: list[float] = Field(default_factory=list)
    s_parameters: dict[str, list[float]] = Field(default_factory=dict)
    z_parameters: dict[str, list[float]] = Field(default_factory=dict)
    eigenmodes: list[Eigenmode] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    #: Set by TEST_FIXTURE solvers so synthetic output is obvious (spec §8.4).
    synthetic: bool = False
    notes: list[str] = Field(default_factory=list)

    model_config = StrictModel.model_config | {"populate_by_name": True}

    @model_validator(mode="after")
    def _validate(self) -> "SolverResults":
        n = len(self.frequency_GHz)
        for key, values in {**self.s_parameters, **self.z_parameters}.items():
            if len(values) != n:
                raise ValueError(
                    f"{key} has {len(values)} points but the frequency grid has {n}"
                )
        if any(f <= 0 for f in self.frequency_GHz):
            raise ValueError("frequency grid must be strictly positive (GHz)")
        if list(self.frequency_GHz) != sorted(self.frequency_GHz):
            raise ValueError("frequency grid must be ascending")
        if self.solver.classification is Classification.TEST_FIXTURE and not self.synthetic:
            raise ValueError(
                "a TEST_FIXTURE solver must mark its results synthetic=True "
                "so that synthetic output is obvious (spec §8.4)"
            )
        return self


# --- §3.3 QuantumResults ----------------------------------------------------


class QuantumResults(StrictModel):
    schema_: Literal[QUANTUM_RESULTS_SCHEMA] = Field(alias="schema")
    candidate_id: str
    master_revision: str
    classification: Classification
    spectrum: dict[str, Any] = Field(default_factory=dict)
    dressed_system: dict[str, Any] = Field(default_factory=dict)
    purcell: dict[str, Any] = Field(default_factory=dict)
    collision: dict[str, Any] = Field(default_factory=dict)
    tolerance: dict[str, Any] = Field(default_factory=dict)
    regression_status: dict[str, Any] = Field(default_factory=dict)
    #: v0.1 physics models are not implemented; record which blocks are absent
    #: rather than emitting a fabricated number.
    unavailable: list[str] = Field(default_factory=list)

    model_config = StrictModel.model_config | {"populate_by_name": True}

    @model_validator(mode="after")
    def _validate(self) -> "QuantumResults":
        if self.classification is Classification.MEASURED:
            raise ValueError(
                "QMHP-CEM v0.1 does not manufacture MEASURED values (spec §2.2)"
            )
        return self


# --- §3.4 GateReport --------------------------------------------------------


class GateResult(StrictModel):
    gate_id: str
    status: GateStatus
    severity: Severity
    evidence_class: Classification | None = None
    measured: float | None = None
    threshold: float | None = None
    units: str | None = None
    margin: float | None = None
    reason: str
    spec_section: str | None = None
    hardware_required: bool = False

    @model_validator(mode="after")
    def _enforce_hardware_boundary(self) -> "GateResult":
        """Spec §2.3 / §6.1: hardware gates never PASS from non-measured evidence.

        This is the load-bearing invariant of the whole evidence model, so it
        is enforced in the contract itself rather than only in the evaluator.
        """
        if self.hardware_required and self.status is GateStatus.PASS:
            if self.evidence_class is not Classification.MEASURED:
                raise ValueError(
                    f"gate {self.gate_id} is hardware-required and may not emit "
                    f"PASS from evidence class {self.evidence_class}; only a "
                    f"typed MEASURED evidence object can close it (spec §2.3)"
                )
        return self


class GateReport(StrictModel):
    schema_: Literal[GATE_REPORT_SCHEMA] = Field(alias="schema")
    candidate_id: str
    master_revision: str
    overall_status: GateStatus
    gates: list[GateResult]

    model_config = StrictModel.model_config | {"populate_by_name": True}

    @model_validator(mode="after")
    def _unique_gate_ids(self) -> "GateReport":
        ids = [g.gate_id for g in self.gates]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate gate_id(s) in report: {sorted(dupes)}")
        return self

    def by_id(self, gate_id: str) -> GateResult:
        for gate in self.gates:
            if gate.gate_id == gate_id:
                return gate
        raise KeyError(gate_id)


# --- §3.5 BatchReport -------------------------------------------------------


class EnvironmentRecord(StrictModel):
    """Environment record required in every batch manifest (spec §13.3)."""

    os: str
    architecture: str
    python_version: str
    uv_version: str | None = None
    dependency_lock_sha256: str | None = None
    dotnet_version: str | None = None
    picogk_version: str | None = None
    shapekernel_revision: str | None = None
    git_commit: str | None = None
    solver_version: str | None = None
    solver_identity: str | None = None
    started_utc: datetime
    ended_utc: datetime | None = None


class BatchReport(StrictModel):
    schema_: Literal[BATCH_REPORT_SCHEMA] = Field(alias="schema")
    batch_id: str
    solver: str
    candidate_count: int = Field(ge=0)
    pass_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    hardware_gated_count: int = Field(ge=0)
    incomplete_count: int = Field(default=0, ge=0)
    batch_outcome: BatchOutcome
    manifest_sha256: str
    environment: EnvironmentRecord | None = None
    rng_seed: int | None = None
    candidate_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    model_config = StrictModel.model_config | {"populate_by_name": True}

    @model_validator(mode="after")
    def _validate(self) -> "BatchReport":
        if self.candidate_ids and len(self.candidate_ids) != self.candidate_count:
            raise ValueError(
                f"candidate_count={self.candidate_count} but "
                f"{len(self.candidate_ids)} candidate_ids were listed"
            )
        if self.pass_count > self.candidate_count:
            raise ValueError("pass_count exceeds candidate_count")
        return self
