"""Candidate and batch pipeline (spec §11).

Per candidate::

    DEFINED -> VALIDATED -> GEOMETRY_GENERATED -> SOLVER_INPUT_PREPARED
            -> SOLVED -> QUANTUM_EVALUATED -> GATES_EVALUATED -> terminal

The quantum step is where v0.1 stops short: the physics models are stubs, so
the step records which quantities are unavailable instead of inventing them.
Dependent gates then report INCOMPLETE, and candidates terminate INCOMPLETE.
That is the correct v0.1 outcome, not a bug to work around.
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
from orchestrator import environment, manifest
from orchestrator.lifecycle import CandidateLifecycle
from orchestrator.results_store import DEFAULT_RESULTS_ROOT, BatchStore
from solvers import RunContext, SolverAdapter, SolverUnavailable, get_adapter


@dataclass
class CandidateOutcome:
    """Everything one candidate produced."""

    candidate: Candidate
    state: CandidateState
    gate_report: GateReport | None = None
    solver_results: SolverResults | None = None
    quantum_results: QuantumResults | None = None
    geometry: Any = None
    notes: list[str] = field(default_factory=list)


# --- candidate construction -------------------------------------------------


def load_base_candidate(path: Path) -> Candidate:
    """Load and validate a base candidate YAML."""
    with Path(path).open() as fh:
        return Candidate.model_validate(yaml.safe_load(fh))


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
    """
    unavailable: list[str] = []
    dressed: dict[str, Any] = {}
    collision_block: dict[str, Any] = {}
    purcell_block: dict[str, Any] = {}
    tolerance_block: dict[str, Any] = {}

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
        purcell_block.update(
            {
                "f8_weight": spectrum["purcell_weight"],
                "emission_GHz": spectrum["dressed_f12_GHz"],
            }
        )
        collision_block.update(
            {
                "omega24_GHz": spectrum["omega24_GHz"],
                "f_readout_GHz": spectrum["root_GHz"],
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
                seed=_tolerance_seed(candidate), n_devices=tolerance_samples
            )
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
            "unavailable": unavailable,
        }
    )


def _tolerance_seed(candidate: Candidate) -> int:
    """Deterministic per-candidate RNG seed, recorded in the manifest."""
    digest = hashlib.sha256(candidate.candidate_id.encode()).hexdigest()
    return int(digest[:8], 16)


# --- per-candidate ----------------------------------------------------------

def run_candidate(
    candidate: Candidate,
    adapter: SolverAdapter,
    store: BatchStore,
    run_id: str,
    tolerance_samples: int = 0,
) -> CandidateOutcome:
    """Take one candidate through the full lifecycle."""
    lifecycle = CandidateLifecycle(candidate.candidate_id)
    candidate_dir = store.candidate_dir(candidate.candidate_id)
    notes: list[str] = []

    # DEFINED -> VALIDATED (construction already validated the contract)
    lifecycle.to(CandidateState.VALIDATED)
    store.write_json(candidate_dir / "candidate.json", candidate.to_ordered_dict())

    # -> GEOMETRY_GENERATED
    geometry = picogk_driver.generate(candidate, candidate_dir / "geometry")
    lifecycle.to(CandidateState.GEOMETRY_GENERATED)
    if not geometry.generated:
        notes.append(f"geometry unavailable: {geometry.reason}")

    # -> SOLVER_INPUT_PREPARED -> SOLVED
    solver_dir = candidate_dir / "solver"
    solver_dir.mkdir(parents=True, exist_ok=True)
    context = RunContext(run_id=run_id, work_dir=solver_dir)

    try:
        prepared = adapter.prepare(candidate, geometry, context)
        lifecycle.to(CandidateState.SOLVER_INPUT_PREPARED)
        store.write_json(solver_dir / "solver_input.json", prepared.payload)

        raw = adapter.run(prepared)
        solver_results = adapter.validate_convergence(adapter.parse(raw))
        lifecycle.to(CandidateState.SOLVED)
        store.write_model(solver_dir / "solver_results.json", solver_results)
    except (SolverUnavailable, RuntimeError) as exc:
        notes.append(f"solver failed: {exc}")
        lifecycle.to(CandidateState.INCOMPLETE)
        return CandidateOutcome(
            candidate=candidate,
            state=lifecycle.state,
            geometry=geometry,
            notes=notes,
        )

    # -> QUANTUM_EVALUATED
    quantum_results = evaluate_quantum(candidate, solver_results, tolerance_samples)
    lifecycle.to(CandidateState.QUANTUM_EVALUATED)
    store.write_model(candidate_dir / "quantum_results.json", quantum_results)
    if quantum_results.unavailable:
        notes.append(
            f"{len(quantum_results.unavailable)} quantum quantities unavailable: "
            f"{', '.join(sorted(quantum_results.unavailable))}"
        )

    # -> GATES_EVALUATED -> terminal
    gate_report = evaluate_candidate(candidate, solver_results, quantum_results)
    lifecycle.to(CandidateState.GATES_EVALUATED)
    lifecycle.to(_terminal_state(gate_report.overall_status))
    store.write_model(candidate_dir / "gate_report.json", gate_report)

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
    """Build a unique batch ID.

    Batch IDs are second-resolution for legibility, so two sweeps started
    within the same second would collide. A collision is disambiguated with a
    numeric suffix rather than reusing the directory: reusing it would trip the
    append-only guard and lose a legitimate second run.
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
    name = solver_name or sweep.solver

    adapter = get_adapter(name)
    if name == "mock" and fixture != "default":
        adapter = type(adapter)(fixture=fixture)
    adapter.preflight()

    base = load_base_candidate(master.REPO_ROOT / sweep.base_candidate)
    candidates = build_candidates(sweep, base)

    bid = batch_id(started, results_root)
    store = BatchStore(bid, results_root)
    run_id = f"RUN-{bid}"

    outcomes = [
        run_candidate(c, adapter, store, run_id, tolerance_samples)
        for c in candidates
    ]

    counts = _count(outcomes)
    outcome = _batch_outcome(outcomes)

    # The manifest must cover every candidate artifact, so it is written before
    # the batch report; the batch report then records the manifest digest.
    _, manifest_sha256 = manifest.write(store.batch_dir)

    report = BatchReport.model_validate(
        {
            "schema": BATCH_REPORT_SCHEMA,
            "batch_id": bid,
            "solver": name,
            "candidate_count": len(outcomes),
            "pass_count": counts[GateStatus.PASS],
            "fail_count": counts[GateStatus.FAIL],
            "hardware_gated_count": counts[GateStatus.HARDWARE_GATED],
            "incomplete_count": counts[GateStatus.INCOMPLETE],
            "batch_outcome": outcome.value,
            "manifest_sha256": manifest_sha256,
            "environment": environment.record(
                started_utc=started,
                solver_name=name,
                solver_version=solver_version(adapter),
                solver_identity=solver_identity(adapter),
                ended_utc=datetime.now(timezone.utc),
            ).model_dump(mode="json"),
            "rng_seed": sweep.rng_seed,
            "candidate_ids": [o.candidate.candidate_id for o in outcomes],
            "notes": _batch_notes(outcomes, adapter),
        }
    )
    store.write_model(store.batch_dir / "batch_report.json", report)

    # Rewrite the manifest so it also covers batch_report.json, then record the
    # final digest alongside it. The report's own manifest_sha256 necessarily
    # predates its existence; manifest.verify() checks the final tree.
    manifest.write(store.batch_dir)

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
    counts = {status: 0 for status in GateStatus}
    for outcome in outcomes:
        try:
            counts[GateStatus(outcome.state.value)] += 1
        except ValueError:
            pass
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

    states = [o.state for o in outcomes]
    if any(s is CandidateState.PASS for s in states):
        return BatchOutcome.FEASIBLE_CANDIDATE_FOUND
    if any(s is CandidateState.INCOMPLETE for s in states):
        return BatchOutcome.INCOMPLETE
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
    return notes
