"""Orchestrator tests (spec §12.7) plus manifest and lifecycle behaviour."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.common import BatchOutcome, CandidateState, GateStatus
from orchestrator import manifest, pipeline
from orchestrator.lifecycle import CandidateLifecycle, InvalidTransition
from orchestrator.results_store import BatchStore, ResultAlreadyExists
from solvers import SolverUnavailable, get_adapter


@pytest.fixture
def results_root(tmp_path) -> Path:
    return tmp_path / "results"


# --- sweep expansion --------------------------------------------------------


def test_sweep_generates_exactly_nine_candidates(object001_sweep, seed_candidate):
    candidates = pipeline.build_candidates(object001_sweep, seed_candidate)
    assert len(candidates) == 9
    assert object001_sweep.candidate_count == 9


def test_candidate_ordering_is_deterministic(object001_sweep, seed_candidate):
    """Outer loop cavity height ascending, inner loop bore ascending (§8.2)."""
    candidates = pipeline.build_candidates(object001_sweep, seed_candidate)
    observed = [
        (
            c.candidate_id,
            c.parameters.vacuum_cavity.height_above_chip_mm,
            c.parameters.launches.bore_diameter_mm,
        )
        for c in candidates
    ]
    assert observed == [
        ("QMHP-CEM-A-RF-000001", 1.25, 2.25),
        ("QMHP-CEM-A-RF-000002", 1.25, 2.50),
        ("QMHP-CEM-A-RF-000003", 1.25, 2.75),
        ("QMHP-CEM-A-RF-000004", 1.50, 2.25),
        ("QMHP-CEM-A-RF-000005", 1.50, 2.50),
        ("QMHP-CEM-A-RF-000006", 1.50, 2.75),
        ("QMHP-CEM-A-RF-000007", 1.75, 2.25),
        ("QMHP-CEM-A-RF-000008", 1.75, 2.50),
        ("QMHP-CEM-A-RF-000009", 1.75, 2.75),
    ]


def test_expansion_is_repeatable(object001_sweep, seed_candidate):
    first = pipeline.build_candidates(object001_sweep, seed_candidate)
    second = pipeline.build_candidates(object001_sweep, seed_candidate)
    assert [c.to_ordered_dict() for c in first] == [c.to_ordered_dict() for c in second]


def test_unswept_parameters_stay_at_seed_values(object001_sweep, seed_candidate):
    for candidate in pipeline.build_candidates(object001_sweep, seed_candidate):
        assert candidate.parameters.chip == seed_candidate.parameters.chip
        assert candidate.parameters.package == seed_candidate.parameters.package
        assert candidate.parameters.lid == seed_candidate.parameters.lid


# --- full sweep -------------------------------------------------------------


def test_mock_sweep_completes_unattended(object001_sweep, results_root):
    report, outcomes = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    assert report.candidate_count == 9
    assert len(outcomes) == 9
    assert all(o.state in (CandidateState.FAIL, CandidateState.INCOMPLETE) for o in outcomes)


def test_batch_manifest_includes_all_required_files(object001_sweep, results_root):
    report, _ = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    batch_dir = results_root / report.batch_id
    entries = dict(manifest.collect(batch_dir))

    assert "batch_report.json" in entries
    for candidate_id in report.candidate_ids:
        assert f"{candidate_id}/candidate.json" in entries
        assert f"{candidate_id}/gate_report.json" in entries
        assert f"{candidate_id}/quantum_results.json" in entries
        assert f"{candidate_id}/solver/solver_results.json" in entries


def test_manifest_verifies_clean(object001_sweep, results_root):
    report, _ = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    assert manifest.verify(results_root / report.batch_id) == []


def test_manifest_detects_tampering(object001_sweep, results_root):
    report, _ = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    batch_dir = results_root / report.batch_id
    target = batch_dir / report.candidate_ids[0] / "gate_report.json"
    payload = json.loads(target.read_text())
    payload["overall_status"] = "PASS"
    target.write_text(json.dumps(payload))

    findings = manifest.verify(batch_dir)
    assert any("content changed" in f for f in findings)


def test_manifest_detects_deletion(object001_sweep, results_root):
    report, _ = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    batch_dir = results_root / report.batch_id
    (batch_dir / report.candidate_ids[0] / "candidate.json").unlink()
    assert any("missing from disk" in f for f in manifest.verify(batch_dir))


def test_manifest_excludes_only_relative_cache_paths(tmp_path):
    """An excluded name in an ANCESTOR path must not empty the manifest."""
    root = tmp_path / "tmp" / "scratch" / "BATCH-1"
    root.mkdir(parents=True)
    (root / "candidate.json").write_text("{}")
    entries = manifest.collect(root)
    assert [rel for rel, _ in entries] == ["candidate.json"]


def test_manifest_still_excludes_nested_caches(tmp_path):
    root = tmp_path / "BATCH-1"
    (root / "__pycache__").mkdir(parents=True)
    (root / "candidate.json").write_text("{}")
    (root / "__pycache__" / "junk.json").write_text("{}")
    assert [rel for rel, _ in manifest.collect(root)] == ["candidate.json"]


def test_empty_manifest_over_populated_tree_is_refused(tmp_path):
    root = tmp_path / "BATCH-1"
    root.mkdir()
    (root / "notes.bin").write_bytes(b"data")
    with pytest.raises(manifest.EmptyManifest):
        manifest.write(root)


# --- NO FEASIBLE DESIGN FOUND (spec §12.7) ----------------------------------


def test_no_feasible_design_found_is_a_successful_batch(object001_sweep, results_root):
    """Not a crash: a valid scientific outcome (spec §1.2, §12.7)."""
    report, outcomes = pipeline.run_sweep(
        object001_sweep,
        solver_name="mock",
        results_root=results_root,
        fixture="no_feasible_design",
    )
    assert report.batch_outcome is BatchOutcome.NO_FEASIBLE_DESIGN_FOUND
    assert report.pass_count == 0
    assert report.fail_count == 9
    assert all(o.state is CandidateState.FAIL for o in outcomes)
    assert (results_root / report.batch_id / "batch_report.json").exists()


def test_incomplete_is_not_reported_as_no_feasible_design(object001_sweep, results_root):
    """Unadjudicated candidates must not be reported as rejected designs."""
    report, _ = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    assert report.batch_outcome is BatchOutcome.INCOMPLETE


# --- append-only (spec §11.3, §12.7) ----------------------------------------


def test_completed_batch_cannot_be_reopened(object001_sweep, results_root):
    report, _ = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    with pytest.raises(ResultAlreadyExists):
        BatchStore(report.batch_id, results_root)


def test_completed_candidate_cannot_be_overwritten(results_root):
    store = BatchStore("BATCH-TEST", results_root)
    candidate_dir = store.candidate_dir("QMHP-CEM-A-RF-000001")
    (candidate_dir / "gate_report.json").write_text("{}")
    with pytest.raises(ResultAlreadyExists):
        store.candidate_dir("QMHP-CEM-A-RF-000001")


def test_consecutive_sweeps_do_not_collide(object001_sweep, results_root):
    first, _ = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    second, _ = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    assert first.batch_id != second.batch_id
    assert (results_root / first.batch_id / "batch_report.json").exists()
    assert (results_root / second.batch_id / "batch_report.json").exists()


# --- lifecycle (spec §11.2) -------------------------------------------------


def test_lifecycle_happy_path():
    lifecycle = CandidateLifecycle("QMHP-CEM-A-RF-000001")
    for state in (
        CandidateState.VALIDATED,
        CandidateState.GEOMETRY_GENERATED,
        CandidateState.SOLVER_INPUT_PREPARED,
        CandidateState.SOLVED,
        CandidateState.QUANTUM_EVALUATED,
        CandidateState.GATES_EVALUATED,
        CandidateState.INCOMPLETE,
    ):
        lifecycle.to(state)
    assert lifecycle.terminal


def test_lifecycle_rejects_skipping_states():
    lifecycle = CandidateLifecycle("QMHP-CEM-A-RF-000001")
    with pytest.raises(InvalidTransition):
        lifecycle.to(CandidateState.SOLVED)


def test_lifecycle_rejects_leaving_a_terminal_state():
    lifecycle = CandidateLifecycle("QMHP-CEM-A-RF-000001")
    lifecycle.to(CandidateState.VALIDATED)
    lifecycle.to(CandidateState.FAIL)
    with pytest.raises(InvalidTransition):
        lifecycle.to(CandidateState.GEOMETRY_GENERATED)


def test_lifecycle_allows_early_termination_as_incomplete():
    lifecycle = CandidateLifecycle("QMHP-CEM-A-RF-000001")
    lifecycle.to(CandidateState.VALIDATED)
    lifecycle.to(CandidateState.INCOMPLETE)
    assert lifecycle.terminal


# --- solver substitution (spec §10.5, §12.8) --------------------------------


def test_unavailable_solver_fails_and_never_falls_back(monkeypatch, object001_sweep, results_root):
    """Deterministic regardless of whether this machine has the Palace image."""
    from solvers.palace.adapter import PalaceSolver

    def unavailable(self):
        raise SolverUnavailable("palace", "no container runtime in this test", "install one")

    monkeypatch.setattr(PalaceSolver, "preflight", unavailable)
    with pytest.raises(SolverUnavailable, match="will not silently substitute"):
        pipeline.run_sweep(
            object001_sweep, solver_name="palace", results_root=results_root
        )
    assert not results_root.exists() or not list(results_root.glob("BATCH-*"))


def test_solver_failure_mid_sweep_ends_the_candidate_incomplete(monkeypatch, object001_sweep, results_root):
    """A Palace run that dies after preflight is recorded, never replaced."""
    from solvers.adapter import PreparedInput
    from solvers.palace.adapter import PalaceRunFailed, PalaceSolver

    def prepare(self, candidate, geometry, run_context):
        return PreparedInput(candidate.candidate_id, run_context.run_id, run_context.work_dir, {}, [])

    def run(self, prepared):
        raise PalaceRunFailed("container exited with code 137")

    monkeypatch.setattr(PalaceSolver, "preflight", lambda self: None)
    monkeypatch.setattr(PalaceSolver, "prepare", prepare)
    monkeypatch.setattr(PalaceSolver, "run", run)
    report, outcomes = pipeline.run_sweep(
        object001_sweep, solver_name="palace", results_root=results_root
    )
    assert report.solver == "palace"
    assert {o.state for o in outcomes} == {CandidateState.INCOMPLETE}
    assert all(any("PalaceRunFailed" in n and "code 137" in n for n in o.notes) for o in outcomes)
    assert all(o.solver_results is None for o in outcomes)
    # The cause is on the batch record too, not only on the in-memory outcome.
    for o in outcomes:
        assert any(n.startswith(f"{o.candidate.candidate_id}: solver failed (PalaceRunFailed)") for n in report.notes)


def test_unknown_solver_is_rejected():
    with pytest.raises(SolverUnavailable, match="no adapter named"):
        get_adapter("hfss")


def test_openems_declares_itself_unavailable():
    with pytest.raises(SolverUnavailable):
        get_adapter("openems").preflight()


def test_palace_preflight_raises_or_finds_a_real_image():
    """v0.2: Palace runs where its container exists and fails clearly elsewhere.

    Either outcome is correct; what is never correct is a silent substitute.
    """
    adapter = get_adapter("palace")
    try:
        adapter.preflight()
    except SolverUnavailable as exc:
        assert "will not silently substitute" in str(exc)
    else:
        identity = adapter.provenance()
        assert identity.get("image_id", "").startswith("sha256:")


def test_batch_report_records_synthetic_provenance(object001_sweep, results_root):
    report, _ = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    assert any("TEST_FIXTURE" in note for note in report.notes)
    assert any("not hardware validation" in note for note in report.notes)


def test_batch_report_records_environment_and_seed(object001_sweep, results_root):
    report, _ = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    assert report.rng_seed == object001_sweep.rng_seed
    assert report.environment is not None
    assert report.environment.python_version
    assert report.environment.picogk_version == "2.3.0"


def test_quantum_results_are_populated_by_the_physics_models(
    object001_sweep, results_root
):
    _, outcomes = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    solved = [o for o in outcomes if o.quantum_results is not None]
    assert solved
    for outcome in solved:
        quantum = outcome.quantum_results
        assert quantum.regression_status["physics_models_implemented"] is True
        assert quantum.dressed_system["root_GHz"] == pytest.approx(
            4.301974466, rel=1e-6
        )
        assert quantum.collision["omega24_GHz"] > 0
        assert quantum.purcell["f8_weight"] > 0


def test_quantum_results_still_record_what_is_unavailable(
    object001_sweep, results_root
):
    """Coupling extraction and the tolerance ensemble are absent by default."""
    _, outcomes = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    quantum = outcomes[0].quantum_results
    assert any("coupling_extraction" in entry for entry in quantum.unavailable)
    assert any("tolerance" in entry for entry in quantum.unavailable)


def test_collision_gate_now_adjudicates(object001_sweep, results_root):
    """With the physics implemented, COLLISION returns a verdict, not INCOMPLETE."""
    _, outcomes = pipeline.run_sweep(
        object001_sweep, solver_name="mock", results_root=results_root
    )
    for outcome in outcomes:
        if outcome.gate_report is None:
            continue
        collision = outcome.gate_report.by_id("COLLISION")
        assert collision.status is GateStatus.PASS
        assert collision.measured == pytest.approx(98.413, abs=0.01)


def test_tolerance_gate_runs_when_samples_requested(object001_sweep, results_root):
    report, outcomes = pipeline.run_sweep(
        object001_sweep,
        solver_name="mock",
        results_root=results_root,
        fixture="filter_pass",
        tolerance_samples=4,
    )
    quantum = outcomes[0].quantum_results
    assert quantum.tolerance["sample_count"] == 4
    assert outcomes[0].gate_report.by_id("TOLERANCE").status is GateStatus.PASS


def test_full_pass_is_blocked_only_by_coupling_extraction_and_hardware(
    object001_sweep, results_root
):
    """Documents exactly what still blocks a PASS in v0.1.

    Every computationally evaluable gate can now pass. What remains is
    COUPLING_EXTRACTION — a HARD gate needing both an eigenmode and a black-box
    extraction from a real EM solver, which the mock TEST_FIXTURE does not
    supply — and the six hardware gates. So the mock pipeline tops out at
    INCOMPLETE by construction, not by accident.
    """
    report, outcomes = pipeline.run_sweep(
        object001_sweep,
        solver_name="mock",
        results_root=results_root,
        fixture="filter_pass",
        tolerance_samples=4,
    )
    assert report.batch_outcome is BatchOutcome.INCOMPLETE

    gates = outcomes[0].gate_report
    for gate_id in ("COLLISION", "P6E2_FILTER", "P4PRE_SPECTRAL", "TOLERANCE"):
        assert gates.by_id(gate_id).status is GateStatus.PASS, gate_id

    assert gates.by_id("COUPLING_EXTRACTION").status is GateStatus.NOT_EVALUATED
    for gate_id in ("P6E6_JOINT", "P0D", "P1", "P3", "P5", "P7"):
        assert gates.by_id(gate_id).status is GateStatus.HARDWARE_GATED, gate_id


def test_no_feasible_design_still_reachable_with_real_physics(
    object001_sweep, results_root
):
    """A hard computational FAIL still adjudicates the whole batch."""
    report, _ = pipeline.run_sweep(
        object001_sweep,
        solver_name="mock",
        results_root=results_root,
        fixture="filter_fail",
    )
    assert report.batch_outcome is BatchOutcome.NO_FEASIBLE_DESIGN_FOUND
    assert report.fail_count == 9


# --- gate status -> candidate state -------------------------------------------
#
# GateStatus (spec §3.4) is larger than the candidate lifecycle (spec §11.2).
# Coercing one into the other by value raised ValueError and aborted the batch
# before the gate report was written.


def test_every_gate_status_maps_to_a_terminal_candidate_state():
    from contracts.common import CandidateState, GateStatus
    from orchestrator.pipeline import _terminal_state

    terminal = {
        CandidateState.PASS,
        CandidateState.FAIL,
        CandidateState.INCOMPLETE,
        CandidateState.HARDWARE_GATED,
    }
    for status in GateStatus:
        assert _terminal_state(status) in terminal, status


def test_unadjudicated_gate_statuses_map_to_incomplete():
    """EXTRACTION-INCONSISTENT is a legitimate outcome, not a crash.

    It, NOT-EVALUATED and NOT-APPLICABLE all mean the candidate was not
    adjudicated. None of them is a member of CandidateState.
    """
    from contracts.common import CandidateState, GateStatus
    from orchestrator.pipeline import _terminal_state

    for status in (
        GateStatus.EXTRACTION_INCONSISTENT,
        GateStatus.NOT_EVALUATED,
        GateStatus.NOT_APPLICABLE,
    ):
        with pytest.raises(ValueError):
            CandidateState(status.value)  # the coercion that used to run
        assert _terminal_state(status) is CandidateState.INCOMPLETE


def test_direct_statuses_are_preserved():
    from contracts.common import CandidateState, GateStatus
    from orchestrator.pipeline import _terminal_state

    assert _terminal_state(GateStatus.PASS) is CandidateState.PASS
    assert _terminal_state(GateStatus.FAIL) is CandidateState.FAIL
    assert _terminal_state(GateStatus.INCOMPLETE) is CandidateState.INCOMPLETE
    assert _terminal_state(GateStatus.HARDWARE_GATED) is CandidateState.HARDWARE_GATED


def test_terminal_state_is_reachable_from_gates_evaluated():
    """Whatever the map returns must be a legal lifecycle transition."""
    from contracts.common import CandidateState, GateStatus
    from orchestrator.lifecycle import can_transition
    from orchestrator.pipeline import _terminal_state

    for status in GateStatus:
        assert can_transition(
            CandidateState.GATES_EVALUATED, _terminal_state(status)
        ), status


# --- cem verify-results (the CI manifest gate) ---------------------------------


def test_verify_results_cli_fails_on_mismatch_and_leaves_the_tree_alone(tmp_path, capsys):
    from orchestrator import cem

    root = tmp_path / "PALACE-GOLDEN-TEST"
    root.mkdir()
    (root / "execution_record.json").write_text('{"outcome": "CONVERGED"}\n')
    (root / "eig.csv").write_text("m, Re{f} (GHz)\n1, 9.6\n")
    manifest.write(root)
    assert cem.main(["verify-results", str(root)]) == 0
    assert "manifest intact" in capsys.readouterr().out

    (root / "eig.csv").write_text("m, Re{f} (GHz)\n1, 9.7\n")   # tampered after the manifest
    before = sorted(p.name for p in root.iterdir())
    assert cem.main(["verify-results", str(root)]) == 5
    out = capsys.readouterr().out
    assert "MISMATCH" in out and "eig.csv" in out
    assert sorted(p.name for p in root.iterdir()) == before          # nothing removed or rewritten
    assert (root / "eig.csv").read_text().endswith("9.7\n")

    missing = tmp_path / "no-such-record"
    missing.mkdir()
    assert cem.main(["verify-results", str(root), str(missing)]) == 5
