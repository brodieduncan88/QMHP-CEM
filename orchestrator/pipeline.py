"""Candidate and batch pipeline (spec §11).

Per candidate::

    DEFINED -> VALIDATED -> GEOMETRY_GENERATED -> SOLVER_INPUT_PREPARED
            -> SOLVED -> QUANTUM_EVALUATED -> GATES_EVALUATED -> terminal

Implemented quantum models run where their inputs exist. Coupling extraction
and hardware evidence remain unavailable in v0.1, so dependent gates record
that boundary instead of inventing values. An unresolved hard gate terminates
the candidate as INCOMPLETE or HARDWARE-GATED.
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from contracts import master
from contracts.candidate import Candidate, candidate_id as make_candidate_id
from contracts.common import BatchOutcome, CandidateState, Classification, GateStatus
from contracts.results import (
    BATCH_REPORT_SCHEMA,
    QUANTUM_RESULTS_SCHEMA,
    BatchReport,
    GateReport,
    QuantumResults,
    SolverResults,
)
from contracts.sweep import SweepDefinition
from evaluator import evaluate_candidate
from geometry.package_picogk import driver as picogk_driver
from models import PhysicsNotImplemented
from models import collision as collision_model
from models import dressed_system, purcell, tolerance
from models.dressed_system import RootNotBracketed
from orchestrator import batch_manifest, environment
from orchestrator.lifecycle import CandidateLifecycle
from orchestrator.results_store import (
    DEFAULT_RESULTS_ROOT,
    BatchStore,
    ResultAlreadyExists,
)
from solvers import RunContext, SolverAdapter, get_adapter


@dataclass
class CandidateOutcome:
    """Everything one candidate produced."""

    candidate: Candidate
    state: CandidateState
    gate_report: GateReport | None = None
    solver_results: SolverResults | None = None
    quantum_results: QuantumResults | None = None
    geometry: Any = None
    solver_failed: bool = False
    notes: list[str] = field(default_factory=list)


class RecordBindingError(ValueError):
    """A result belongs to a different candidate or master revision."""


# --- candidate construction -------------------------------------------------


def load_base_candidate(path: Path) -> Candidate:
    """Load and validate a base candidate YAML."""
    with Path(path).open() as fh:
        candidate = Candidate.model_validate(yaml.safe_load(fh))
    _require_current_master(candidate)
    return candidate


def _require_current_master(candidate: Candidate) -> None:
    """Refuse to evaluate a candidate against a different authority set."""
    active_revision = master.master_revision()
    if candidate.master_revision != active_revision:
        raise RecordBindingError(
            f"candidate master_revision {candidate.master_revision!r} does not "
            f"match active frozen master {active_revision!r}"
        )


def _set_by_path(payload: dict[str, Any], dotted: str, value: Any) -> None:
    node = payload
    parts = dotted.split(".")
    for part in parts[:-1]:
        if part not in node:
            raise KeyError(f"no parameter group {part!r} while setting {dotted!r}")
        node = node[part]
    if parts[-1] not in node:
        raise KeyError(f"no parameter {parts[-1]!r} while setting {dotted!r}")
    node[parts[-1]] = value


def build_candidates(sweep: SweepDefinition, base: Candidate) -> list[Candidate]:
    """Expand a sweep into candidates in deterministic order (spec §8.2)."""
    base_payload = base.to_ordered_dict()
    candidates: list[Candidate] = []

    for index, point in enumerate(sweep.points(), start=1):
        payload = copy.deepcopy(base_payload)
        payload["candidate_id"] = make_candidate_id(index)
        payload["parent_candidate_id"] = None
        for dotted, value in point.items():
            _set_by_path(payload["parameters"], dotted, value)
        candidates.append(Candidate.model_validate(payload))

    return candidates


# --- quantum step -----------------------------------------------------------


def evaluate_quantum(
    candidate: Candidate,
    solver_results: SolverResults,
    tolerance_samples: int = 0,
    rng_seed: int = 0,
) -> QuantumResults:
    """Run the quantum-device layer for a candidate.

    The dressed-system, Purcell and collision quantities are computed from the
    frozen Branch-A device. Anything a model cannot supply is recorded in
    ``unavailable`` rather than substituted.

    Args:
        tolerance_samples: Ensemble size for the TOLERANCE gate. Zero skips it,
            which is the sweep default: each device costs a full static solve
            plus a bracketed root search, so a 400-device ensemble per
            candidate would dominate the run.
        rng_seed: Batch seed recorded in the sweep definition. It is combined
            with the candidate ID to create a deterministic independent stream.
    """
    unavailable: list[str] = []
    dressed: dict[str, Any] = {}
    collision_block: dict[str, Any] = {}
    purcell_block: dict[str, Any] = {}
    tolerance_block: dict[str, Any] = {}
    value_provenance: dict[str, Classification] = {}

    try:
        spectrum = dressed_system.dressed_spectrum()
        dressed.update(
            {
                "root_GHz": spectrum["root_GHz"],
                "logical_pull_MHz": spectrum["logical_pull_MHz"],
                "sink_pull_MHz": spectrum["sink_pull_MHz"],
                "sink_logical_contrast_MHz": spectrum["sink_logical_contrast_MHz"],
                "sink_line_GHz": spectrum["sink_line_GHz"],
                "Nq": spectrum["Nq"],
                "Nph": spectrum["Nph"],
                "coupling_g_GHz": spectrum["coupling_g_GHz"],
            }
        )
        value_provenance.update(
            {
                "dressed_system.root_GHz": Classification.SOLVED,
                "dressed_system.logical_pull_MHz": Classification.SOLVED,
                "dressed_system.sink_pull_MHz": Classification.SOLVED,
                "dressed_system.sink_logical_contrast_MHz": Classification.SOLVED,
                "dressed_system.sink_line_GHz": Classification.SOLVED,
                "dressed_system.Nq": Classification.MASTER_FROZEN,
                "dressed_system.Nph": Classification.MASTER_FROZEN,
                "dressed_system.coupling_g_GHz": (
                    Classification.VERIFIED_COMPUTATIONAL
                ),
            }
        )
        purcell_block.update(
            {
                "f8_weight": spectrum["purcell_weight"],
                "emission_GHz": spectrum["dressed_f12_GHz"],
            }
        )
        value_provenance.update(
            {
                "purcell.f8_weight": Classification.SOLVED,
                "purcell.emission_GHz": Classification.SOLVED,
            }
        )
        collision_block.update(
            {
                "omega24_GHz": spectrum["omega24_GHz"],
                "f_readout_GHz": spectrum["root_GHz"],
            }
        )
        value_provenance.update(
            {
                "collision.omega24_GHz": Classification.SOLVED,
                "collision.f_readout_GHz": Classification.SOLVED,
            }
        )
    except (PhysicsNotImplemented, RootNotBracketed) as exc:
        unavailable.append(f"dressed_system: {exc}")

    # Coupling extraction needs BOTH an eigenmode and a black-box value from
    # the solver. The mock fixture supplies neither, so the gate correctly
    # reports NOT-EVALUATED rather than passing on one extraction.
    unavailable.append(
        "dressed_system.coupling_extraction: requires eigenmode and black-box "
        "extractions from an EM solver (spec §5.5); not available from "
        f"solver {solver_results.solver.name!r}."
    )

    if tolerance_samples > 0:
        try:
            tolerance_block = tolerance.evaluate_ensemble(
                seed=_tolerance_seed(candidate, rng_seed),
                n_devices=tolerance_samples,
            )
            value_provenance["tolerance"] = Classification.SOLVED
            value_provenance["tolerance.seed"] = Classification.QMHP_CEM_NORMATIVE
        except PhysicsNotImplemented as exc:
            unavailable.append(f"tolerance: {exc}")
    else:
        unavailable.append(
            "tolerance: ensemble not requested for this run "
            "(--tolerance-samples 0)."
        )

    return QuantumResults.model_validate(
        {
            "schema": QUANTUM_RESULTS_SCHEMA,
            "candidate_id": candidate.candidate_id,
            "master_revision": candidate.master_revision,
            "classification": Classification.SOLVED,
            "spectrum": {},
            "dressed_system": dressed,
            "purcell": purcell_block,
            "collision": collision_block,
            "tolerance": tolerance_block,
            "regression_status": {
                "physics_models_implemented": True,
                "reference": (
                    "reference/v1_5_8f_release_bundle/"
                    "qmhp_v158f_readout_replication.py"
                ),
                "note": (
                    "Dressed-system quantities are computed for the frozen "
                    "Branch-A NOMINAL device, not for this candidate's "
                    "geometry. Candidate geometry enters through the solver "
                    "results, not through the device Hamiltonian."
                ),
            },
            "value_provenance": value_provenance,
            "unavailable": unavailable,
        }
    )


def _tolerance_seed(candidate: Candidate, sweep_seed: int) -> int:
    """Derive a deterministic candidate seed from the recorded sweep seed."""
    material = f"{sweep_seed}:{candidate.candidate_id}".encode()
    digest = hashlib.sha256(material).hexdigest()
    return int(digest[:8], 16)


def _require_record_binding(
    candidate: Candidate,
    record: SolverResults | QuantumResults | GateReport,
    label: str,
) -> None:
    """Ensure a result cannot be used to adjudicate a different candidate."""
    if record.candidate_id != candidate.candidate_id:
        raise RecordBindingError(
            f"{label} candidate_id {record.candidate_id!r} does not match "
            f"candidate {candidate.candidate_id!r}"
        )
    record_revision = getattr(record, "master_revision", None)
    if record_revision is not None and record_revision != candidate.master_revision:
        raise RecordBindingError(
            f"{label} master_revision {record_revision!r} does not match "
            f"candidate revision {candidate.master_revision!r}"
        )


# --- per-candidate ----------------------------------------------------------

def run_candidate(
    candidate: Candidate,
    adapter: SolverAdapter,
    store: BatchStore,
    run_id: str,
    tolerance_samples: int = 0,
    rng_seed: int = 0,
) -> CandidateOutcome:
    """Take one candidate through the full lifecycle."""
    _require_current_master(candidate)
    lifecycle = CandidateLifecycle(candidate.candidate_id)
    candidate_dir = store.candidate_dir(candidate.candidate_id)
    candidate_path = Path(candidate.candidate_id)
    notes: list[str] = []

    # DEFINED -> VALIDATED (construction already validated the contract)
    lifecycle.to(CandidateState.VALIDATED)
    store.write_json(candidate_path / "candidate.json", candidate.to_ordered_dict())

    # -> GEOMETRY_GENERATED
    geometry = picogk_driver.generate(candidate, candidate_dir / "geometry")
    lifecycle.to(CandidateState.GEOMETRY_GENERATED)
    if not geometry.generated:
        notes.append(f"geometry unavailable: {geometry.reason}")

    # -> SOLVER_INPUT_PREPARED -> SOLVED
    solver_dir = candidate_dir / "solver"
    solver_path = candidate_path / "solver"
    solver_dir.mkdir(parents=True, exist_ok=True)
    context = RunContext(run_id=run_id, work_dir=solver_dir)

    try:
        prepared = adapter.prepare(candidate, geometry, context)
        lifecycle.to(CandidateState.SOLVER_INPUT_PREPARED)
        store.write_json(solver_path / "solver_input.json", prepared.payload)

        raw = adapter.run(prepared)
        solver_results = adapter.validate_convergence(adapter.parse(raw))
        _require_record_binding(candidate, solver_results, "solver result")
        lifecycle.to(CandidateState.SOLVED)
        store.write_model(solver_path / "solver_results.json", solver_results)
    except Exception as exc:  # noqa: BLE001 - any solver failure is recorded, never hidden
        # SolverUnavailable (spec §10.5), a run that did not complete, an
        # output that could not be parsed, a convergence failure: every one
        # of them ends this candidate as INCOMPLETE. The cause is carried on
        # the outcome and written into the batch report's notes by
        # _batch_notes. Nothing here retries with another solver.
        notes.append(f"solver failed ({type(exc).__name__}): {exc}")
        lifecycle.to(CandidateState.INCOMPLETE)
        return CandidateOutcome(
            candidate=candidate,
            state=lifecycle.state,
            geometry=geometry,
            solver_failed=True,
            notes=notes,
        )

    # -> QUANTUM_EVALUATED
    quantum_results = evaluate_quantum(
        candidate,
        solver_results,
        tolerance_samples,
        rng_seed,
    )
    _require_record_binding(candidate, quantum_results, "quantum result")
    lifecycle.to(CandidateState.QUANTUM_EVALUATED)
    store.write_model(candidate_path / "quantum_results.json", quantum_results)
    if quantum_results.unavailable:
        notes.append(
            f"{len(quantum_results.unavailable)} quantum quantities unavailable: "
            f"{', '.join(sorted(quantum_results.unavailable))}"
        )

    # -> GATES_EVALUATED -> terminal
    gate_report = evaluate_candidate(candidate, solver_results, quantum_results)
    _require_record_binding(candidate, gate_report, "gate report")
    lifecycle.to(CandidateState.GATES_EVALUATED)
    lifecycle.to(_terminal_state(gate_report.overall_status))
    store.write_model(candidate_path / "gate_report.json", gate_report)

    return CandidateOutcome(
        candidate=candidate,
        state=lifecycle.state,
        gate_report=gate_report,
        solver_results=solver_results,
        quantum_results=quantum_results,
        geometry=geometry,
        notes=notes,
    )


# --- batch ------------------------------------------------------------------


def batch_id(started: datetime, results_root: Path | None = None) -> str:
    """Return the next apparently available batch ID without reserving it.

    Batch IDs are second-resolution for legibility, so two sweeps started
    within the same second would collide. A collision is disambiguated with a
    numeric suffix rather than reusing the directory: reusing it would trip the
    append-only guard and lose a legitimate second run. Callers that create a
    batch must use :func:`_allocate_batch_store`, whose exclusive mkdir closes
    the check/create race; this helper remains for display and compatibility.
    """
    base = f"BATCH-{started.strftime('%Y%m%dT%H%M%SZ')}"
    root = Path(results_root or DEFAULT_RESULTS_ROOT)
    if not (root / base).exists():
        return base
    for suffix in range(2, 1000):
        candidate = f"{base}-{suffix:03d}"
        if not (root / candidate).exists():
            return candidate
    raise RuntimeError(f"could not allocate a unique batch id from {base}")


def _allocate_batch_store(
    started: datetime, results_root: Path | None = None
) -> BatchStore:
    """Atomically reserve a timestamp-based batch directory.

    ``batch_id`` is useful for display and compatibility, but its existence
    check alone cannot prevent a cross-process race. BatchStore performs an
    exclusive mkdir; collisions are retried with deterministic suffixes.
    """
    base = f"BATCH-{started.strftime('%Y%m%dT%H%M%SZ')}"
    for suffix in range(1, 1000):
        candidate = base if suffix == 1 else f"{base}-{suffix:03d}"
        try:
            return BatchStore(candidate, results_root)
        except ResultAlreadyExists:
            continue
    raise RuntimeError(f"could not atomically allocate a batch id from {base}")


def run_sweep(
    sweep: SweepDefinition,
    solver_name: str | None = None,
    results_root: Path | None = None,
    fixture: str = "default",
    tolerance_samples: int = 0,
) -> tuple[BatchReport, list[CandidateOutcome]]:
    """Run a deterministic sweep end to end.

    Raises:
        SolverUnavailable: if the requested solver cannot execute. The batch
            fails before any candidate is processed; it never falls back
            (spec §10.5).
    """
    started = datetime.now(timezone.utc)
    # Capture the source revision before results written under the repository
    # can themselves make the working tree dirty.
    git_revision = environment.git_commit()
    name = solver_name or sweep.solver

    adapter = get_adapter(name)
    if name == "mock" and fixture != "default":
        adapter = type(adapter)(fixture=fixture)
    adapter.preflight()

    base = load_base_candidate(master.REPO_ROOT / sweep.base_candidate)
    candidates = build_candidates(sweep, base)

    store = _allocate_batch_store(started, results_root)
    bid = store.batch_id
    run_id = f"RUN-{bid}"

    outcomes = [
        run_candidate(
            c,
            adapter,
            store,
            run_id,
            tolerance_samples,
            sweep.rng_seed,
        )
        for c in candidates
    ]

    counts = _count(outcomes)
    outcome = _batch_outcome(outcomes)

    # Build a draft using the canonical self-reference placeholder. Manifest
    # v2 can then preview its final bytes, letting both report and manifest be
    # created exactly once with a mutually consistent digest.
    report_draft = BatchReport.model_validate(
        {
            "schema": BATCH_REPORT_SCHEMA,
            "batch_id": bid,
            "solver": name,
            "synthetic": adapter.classification is Classification.TEST_FIXTURE,
            "candidate_count": len(outcomes),
            "pass_count": counts[GateStatus.PASS],
            "fail_count": counts[GateStatus.FAIL],
            "hardware_gated_count": counts[GateStatus.HARDWARE_GATED],
            "incomplete_count": counts[GateStatus.INCOMPLETE],
            "batch_outcome": outcome.value,
            "manifest_sha256": batch_manifest.MANIFEST_DIGEST_PLACEHOLDER,
            "environment": environment.record(
                started_utc=started,
                solver_name=name,
                solver_version=solver_version(adapter),
                solver_identity=solver_identity(adapter),
                ended_utc=datetime.now(timezone.utc),
                git_revision=git_revision,
            ).model_dump(mode="json"),
            "rng_seed": sweep.rng_seed,
            "candidate_ids": [o.candidate.candidate_id for o in outcomes],
            "notes": _batch_notes(outcomes, adapter),
        }
    )
    _, manifest_sha256 = batch_manifest.preview_with_batch_report(
        store.batch_dir,
        report_draft.model_dump(mode="json", by_alias=True),
    )
    final_payload = report_draft.model_dump(mode="json", by_alias=True)
    final_payload["manifest_sha256"] = manifest_sha256
    report = BatchReport.model_validate(final_payload)
    store.write_model(Path("batch_report.json"), report)
    _, written_digest = store.seal_batch(
        lambda: batch_manifest.build(
            store.batch_dir,
            self_referential_report=True,
        ),
        manifest_sha256,
    )
    if written_digest != manifest_sha256:
        raise RuntimeError(
            "manifest preview changed while finalizing the batch; refusing "
            "to return an internally inconsistent report"
        )
    findings = batch_manifest.verify(store.batch_dir)
    if findings:
        raise RuntimeError(
            "sealed batch failed manifest verification: " + "; ".join(findings)
        )

    return report, outcomes


def _terminal_state(status: GateStatus) -> CandidateState:
    """Map a rolled-up gate status onto a candidate lifecycle state.

    The two vocabularies are deliberately different sizes. GateStatus (spec
    §3.4) carries EXTRACTION-INCONSISTENT, NOT-EVALUATED and NOT-APPLICABLE;
    the candidate lifecycle (spec §11.2) terminates only in PASS, FAIL,
    INCOMPLETE or HARDWARE-GATED. Coercing one into the other by value raised
    ValueError for any status outside that intersection and aborted the batch
    before gate_report.json was written, losing the very result that explains
    why. A disagreeing coupling extraction is a legitimate scientific outcome
    and must be recorded, not crash the run.

    EXTRACTION-INCONSISTENT, NOT-EVALUATED and NOT-APPLICABLE all mean the
    candidate was not adjudicated, so they map to INCOMPLETE. The precise gate
    status is preserved verbatim in gate_report.overall_status, which is what
    the report and the manifest carry; nothing is flattened away on disk.
    """
    direct = {
        GateStatus.PASS: CandidateState.PASS,
        GateStatus.FAIL: CandidateState.FAIL,
        GateStatus.INCOMPLETE: CandidateState.INCOMPLETE,
        GateStatus.HARDWARE_GATED: CandidateState.HARDWARE_GATED,
    }
    return direct.get(status, CandidateState.INCOMPLETE)


def solver_version(adapter: SolverAdapter) -> str:
    """The version of the solver that produced the numbers (spec §13.3).

    For a container-backed adapter that is the solver's own version as read
    from the image, not the adapter's; the adapter version is recorded in
    every SolverResults regardless.
    """
    provenance = adapter.provenance() if hasattr(adapter, "provenance") else {}
    return str(provenance.get("palace_version") or provenance.get("solver_version") or adapter.version)


def solver_identity(adapter: SolverAdapter) -> str:
    """Solver/container identity for the batch manifest (spec §13.3)."""
    provenance = adapter.provenance() if hasattr(adapter, "provenance") else {}
    if provenance.get("image_id"):
        return f"{provenance.get('image', adapter.name)}@{provenance['image_id']}"
    return f"{adapter.name}@{adapter.version}"


def _count(outcomes: list[CandidateOutcome]) -> dict[GateStatus, int]:
    """Count terminal outcomes plus overlapping hardware-gate coverage.

    PASS, FAIL and INCOMPLETE count mutually exclusive candidate terminal
    states. ``hardware_gated_count`` has different semantics in spec §3.5: it
    counts candidates carrying at least one unresolved hardware gate, including
    candidates that also terminated FAIL on a computational hard gate.
    """
    counts = {status: 0 for status in GateStatus}
    for outcome in outcomes:
        terminal_status = {
            CandidateState.PASS: GateStatus.PASS,
            CandidateState.FAIL: GateStatus.FAIL,
            CandidateState.INCOMPLETE: GateStatus.INCOMPLETE,
        }.get(outcome.state)
        if terminal_status is not None:
            counts[terminal_status] += 1

        if outcome.gate_report is not None and any(
            gate.status is GateStatus.HARDWARE_GATED
            for gate in outcome.gate_report.gates
        ):
            counts[GateStatus.HARDWARE_GATED] += 1
    return counts


def _batch_outcome(outcomes: list[CandidateOutcome]) -> BatchOutcome:
    """Decide the batch outcome (spec §3.5).

    ``NO_FEASIBLE_DESIGN_FOUND`` is reserved for the case where every candidate
    was actually adjudicated and none survived. Candidates that could not be
    adjudicated — because the physics is missing — make the batch INCOMPLETE.
    Reporting "no feasible design" when nothing was evaluated would overstate
    what the computation established.
    """
    if not outcomes:
        return BatchOutcome.INCOMPLETE

    if any(o.solver_failed for o in outcomes):
        return BatchOutcome.SOLVER_FAILURE

    states = [o.state for o in outcomes]
    if any(s is CandidateState.PASS for s in states):
        return BatchOutcome.FEASIBLE_CANDIDATE_FOUND
    if any(s is CandidateState.INCOMPLETE for s in states):
        return BatchOutcome.INCOMPLETE
    if all(s is CandidateState.HARDWARE_GATED for s in states):
        return BatchOutcome.BLOCKED
    if all(s in (CandidateState.FAIL, CandidateState.HARDWARE_GATED) for s in states):
        if any(s is CandidateState.FAIL for s in states):
            return BatchOutcome.NO_FEASIBLE_DESIGN_FOUND
        return BatchOutcome.INCOMPLETE
    return BatchOutcome.INCOMPLETE


def _batch_notes(outcomes: list[CandidateOutcome], adapter: SolverAdapter) -> list[str]:
    notes: list[str] = []
    if adapter.classification is Classification.TEST_FIXTURE:
        notes.append(
            f"Solver {adapter.name!r} is a TEST_FIXTURE. Every S-parameter and "
            f"eigenmode in this batch is SYNTHETIC and carries no evidentiary "
            f"weight."
        )
    notes.append(
        "Dressed-system quantities are computed for the frozen Branch-A "
        "NOMINAL device. Candidate geometry enters only through the solver "
        "results; it does not perturb the device Hamiltonian."
    )
    if any(o.geometry is not None and not o.geometry.generated for o in outcomes):
        notes.append(
            "Object 001 geometry was not generated; the PicoGK project requires "
            "the .NET 9 SDK (spec §7.2)."
        )
    notes.append(
        "A computational PASS is not hardware validation. Hardware-dependent "
        "gates remain HARDWARE-GATED until measured evidence is supplied."
    )
    # A candidate that ended INCOMPLETE because its solver run failed has no
    # solver_results.json to explain itself; the cause goes on the record here.
    for o in outcomes:
        for note in o.notes:
            if note.startswith("solver failed"):
                notes.append(f"{o.candidate.candidate_id}: {note}")
    return notes
