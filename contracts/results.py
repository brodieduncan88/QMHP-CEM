"""Solver, quantum, gate and batch result contracts (spec §3.2 – §3.5)."""

from __future__ import annotations

from datetime import datetime
import math
import re
from numbers import Real
from typing import Any, Literal

from pydantic import Field, model_validator

from contracts import master
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

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _non_finite_path(value: Any, path: str) -> str | None:
    """Return the first path containing NaN/Inf in an untyped result block.

    Pydantic's ``allow_inf_nan=False`` protects typed float fields.  Quantum
    result blocks deliberately remain extensible ``dict[str, Any]`` records,
    so their nested values need an explicit recursive check.
    """
    if isinstance(value, Real) and not isinstance(value, bool):
        return path if not math.isfinite(float(value)) else None
    if isinstance(value, dict):
        for key, nested in value.items():
            found = _non_finite_path(nested, f"{path}.{key}")
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found = _non_finite_path(nested, f"{path}[{index}]")
            if found is not None:
                return found
    return None


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

    @model_validator(mode="after")
    def _validate_digest(self) -> "Artifact":
        if not _SHA256_PATTERN.fullmatch(self.sha256):
            raise ValueError("artifact sha256 must be 64 lowercase hexadecimal characters")
        return self


class SolverCapabilities(StrictModel):
    """Capabilities and solved-domain coverage asserted by an adapter.

    Defaults fail closed so legacy solver records remain readable but cannot
    obtain a P4PRE absence-of-conflict PASS without an explicit coverage
    assertion.  ``TEST_FIXTURE`` is a complete *synthetic* fixture domain,
    never a claim about the physical candidate.
    """

    eigenmode_spectrum: bool = False
    p4pre_spectral_domain_complete: bool = False
    domain_kind: Literal[
        "UNSPECIFIED", "PARTIAL", "EMPTY_CAVITY", "PHYSICAL_CANDIDATE", "TEST_FIXTURE"
    ] = "UNSPECIFIED"

    @model_validator(mode="after")
    def _validate(self) -> "SolverCapabilities":
        if self.p4pre_spectral_domain_complete and not self.eigenmode_spectrum:
            raise ValueError(
                "p4pre_spectral_domain_complete requires eigenmode_spectrum=True"
            )
        if self.p4pre_spectral_domain_complete and self.domain_kind not in {
            "PHYSICAL_CANDIDATE",
            "TEST_FIXTURE",
        }:
            raise ValueError(
                "a complete P4PRE spectral domain must be PHYSICAL_CANDIDATE "
                "or TEST_FIXTURE"
            )
        return self


class SolverResults(StrictModel):
    schema_: Literal[SOLVER_RESULTS_SCHEMA] = Field(alias="schema")
    candidate_id: str
    #: Added after schema 0.1.0 records had already been committed.  Optional
    #: keeps those immutable legacy records readable; all current adapters
    #: emit it, and evaluators enforce equality whenever it is present.
    master_revision: str | None = None
    solver: SolverIdentity
    run_id: str
    #: Mandatory. Omitting it is a validation error, by construction.
    convergence: Convergence
    frequency_GHz: list[float] = Field(default_factory=list)
    s_parameters: dict[str, list[float]] = Field(default_factory=dict)
    z_parameters: dict[str, list[float]] = Field(default_factory=dict)
    eigenmodes: list[Eigenmode] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    capabilities: SolverCapabilities = Field(default_factory=SolverCapabilities)
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
        if self.synthetic and self.solver.classification is not Classification.TEST_FIXTURE:
            raise ValueError(
                "synthetic=True is reserved for a TEST_FIXTURE solver classification"
            )
        if (
            self.capabilities.domain_kind == "TEST_FIXTURE"
            and self.solver.classification is not Classification.TEST_FIXTURE
        ):
            raise ValueError(
                "domain_kind=TEST_FIXTURE requires a TEST_FIXTURE solver classification"
            )
        if (
            self.solver.classification is Classification.TEST_FIXTURE
            and self.capabilities.p4pre_spectral_domain_complete
            and self.capabilities.domain_kind != "TEST_FIXTURE"
        ):
            raise ValueError(
                "a TEST_FIXTURE may claim complete P4PRE coverage only for a "
                "TEST_FIXTURE domain"
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
    #: Per-value origin for mixed-classification records. Keys are dotted paths
    #: into the result blocks above (for example
    #: ``dressed_system.coupling_g_GHz``). The top-level ``classification``
    #: remains for backwards compatibility and describes the result record,
    #: not necessarily every carried constant.
    value_provenance: dict[str, Classification] = Field(default_factory=dict)
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
        for field_name in (
            "spectrum",
            "dressed_system",
            "purcell",
            "collision",
            "tolerance",
            "regression_status",
        ):
            found = _non_finite_path(getattr(self, field_name), field_name)
            if found is not None:
                raise ValueError(f"non-finite scientific value at {found}")
        result_blocks = {
            "spectrum": self.spectrum,
            "dressed_system": self.dressed_system,
            "purcell": self.purcell,
            "collision": self.collision,
            "tolerance": self.tolerance,
            "regression_status": self.regression_status,
        }
        for path in self.value_provenance:
            parts = path.split(".")
            if any(not part for part in parts) or parts[0] not in result_blocks:
                raise ValueError(f"invalid value_provenance path {path!r}")
            value: Any = result_blocks[parts[0]]
            for part in parts[1:]:
                if not isinstance(value, dict) or part not in value:
                    raise ValueError(
                        f"value_provenance path {path!r} does not identify a "
                        "value in this quantum result"
                    )
                value = value[part]
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
    #: True only for an end-to-end deterministic fixture evaluation.  This
    #: top-level marker prevents consumers from having to inspect every gate
    #: before determining that the report carries no evidentiary weight.
    synthetic: bool = False

    model_config = StrictModel.model_config | {"populate_by_name": True}

    @model_validator(mode="after")
    def _validate_report(self) -> "GateReport":
        current_revision = master.master_revision()
        if self.master_revision != current_revision:
            raise ValueError(
                f"gate report master_revision {self.master_revision!r} does not "
                f"match loaded frozen master {current_revision!r}"
            )

        ids = [g.gate_id for g in self.gates]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate gate_id(s) in report: {sorted(dupes)}")

        definitions = master.gate_definitions()
        missing = sorted(set(definitions) - set(ids))
        unknown = sorted(set(ids) - set(definitions))
        if missing or unknown:
            raise ValueError(
                f"gate report must cover the frozen gate set; missing={missing}, "
                f"unknown={unknown}"
            )

        for gate in self.gates:
            definition = definitions[gate.gate_id]
            expected_severity = Severity(definition["severity"])
            expected_hardware = bool(definition["hardware_required"])
            expected_section = str(definition["spec_section"])
            allowed = {GateStatus(value) for value in definition["allowed_statuses"]}
            if gate.severity is not expected_severity:
                raise ValueError(
                    f"gate {gate.gate_id} severity {gate.severity} does not match "
                    f"frozen definition {expected_severity}"
                )
            if gate.hardware_required is not expected_hardware:
                raise ValueError(
                    f"gate {gate.gate_id} hardware_required does not match its "
                    "frozen definition"
                )
            if gate.spec_section != expected_section:
                raise ValueError(
                    f"gate {gate.gate_id} spec_section {gate.spec_section!r} does "
                    f"not match frozen definition {expected_section!r}"
                )
            if gate.status not in allowed:
                raise ValueError(
                    f"gate {gate.gate_id} status {gate.status} is not allowed by "
                    "its frozen definition"
                )
            if gate.status in {
                GateStatus.PASS,
                GateStatus.FAIL,
                GateStatus.EXTRACTION_INCONSISTENT,
            }:
                required = {
                    Classification(value)
                    for value in definition["required_evidence"]
                }
                fixture_exception = (
                    gate.evidence_class is Classification.TEST_FIXTURE
                    and self.synthetic
                )
                if gate.evidence_class not in required and not fixture_exception:
                    raise ValueError(
                        f"gate {gate.gate_id} adjudicates from evidence class "
                        f"{gate.evidence_class}; frozen required_evidence is "
                        f"{sorted(value.value for value in required)}"
                    )

        fixture_evidence = any(
            gate.evidence_class is Classification.TEST_FIXTURE for gate in self.gates
        )
        if fixture_evidence and not self.synthetic:
            raise ValueError(
                "a report containing TEST_FIXTURE gate evidence must mark "
                "synthetic=True"
            )

        expected_overall = _roll_up(self.gates)
        if self.overall_status is not expected_overall:
            raise ValueError(
                f"overall_status {self.overall_status} does not match gate roll-up "
                f"{expected_overall}"
            )
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
    #: Batch-level fixture marker.  Orchestrators must set this for mock runs;
    #: TEST_FIXTURE outcomes remain useful tests but are not scientific evidence.
    synthetic: bool = False

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
        for name in ("fail_count", "hardware_gated_count", "incomplete_count"):
            if getattr(self, name) > self.candidate_count:
                raise ValueError(f"{name} exceeds candidate_count")
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError("candidate_ids contains duplicates")
        if not _SHA256_PATTERN.fullmatch(self.manifest_sha256):
            raise ValueError(
                "manifest_sha256 must be 64 lowercase hexadecimal characters"
            )
        if (
            self.batch_outcome is BatchOutcome.FEASIBLE_CANDIDATE_FOUND
            and self.pass_count == 0
        ):
            raise ValueError("FEASIBLE_CANDIDATE_FOUND requires pass_count > 0")
        if (
            self.batch_outcome is BatchOutcome.NO_FEASIBLE_DESIGN_FOUND
            and self.pass_count > 0
        ):
            raise ValueError("NO_FEASIBLE_DESIGN_FOUND requires pass_count == 0")
        fixture_note = any("TEST_FIXTURE" in note for note in self.notes)
        if fixture_note and not self.synthetic:
            raise ValueError(
                "a batch carrying TEST_FIXTURE provenance must mark synthetic=True"
            )
        return self


def _roll_up(results: list[GateResult]) -> GateStatus:
    """Contract-local roll-up used to validate deserialised gate reports."""
    hard = [result for result in results if result.severity is Severity.HARD]
    if any(result.status is GateStatus.FAIL for result in hard):
        return GateStatus.FAIL
    if any(
        result.status is GateStatus.EXTRACTION_INCONSISTENT for result in results
    ):
        return GateStatus.EXTRACTION_INCONSISTENT
    if any(
        result.status in (GateStatus.INCOMPLETE, GateStatus.NOT_EVALUATED)
        for result in hard
    ):
        return GateStatus.INCOMPLETE
    if any(result.status is GateStatus.HARDWARE_GATED for result in hard):
        return GateStatus.HARDWARE_GATED
    return GateStatus.PASS
