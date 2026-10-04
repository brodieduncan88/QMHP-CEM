"""Regression tests for PR #10 gaps (design note §7, D1, D3, store-scoped D4).

Each defect was reproduced on main at 79844b7 before the fix. Regression tests
fail there and pass after the fix; explicitly named controls pass on both.

D4 coverage binds cooperating BatchStore writers. It does not establish the
design note's static writer inventory, process/kill stress campaign, or control
direct writes by adapters, geometry, scripts, experiments, and other callers.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
from pathlib import Path

import numpy as np
import pytest

from contracts.common import GateStatus
from contracts.results import (
    QUANTUM_RESULTS_SCHEMA,
    SOLVER_RESULTS_SCHEMA,
    QuantumResults,
    SolverResults,
)
from evaluator import evaluate_candidate
from evaluator.base import EvidenceIdentityError, GateInputs
from evaluator.computational import (
    CollisionGate,
    CouplingExtractionGate,
    P4PreSpectralGate,
    P6E2FilterGate,
    ToleranceGate,
)
from models import collision
from orchestrator import batch_manifest as manifest
from orchestrator import results_store
from orchestrator.results_store import BatchStore, ResultAlreadyExists

READOUT_GHz = 4.301974466427182


def _quantum(
    candidate_id: str = "QMHP-CEM-A-RF-000001",
    omega24: float = 4.40038762682525,
) -> QuantumResults:
    return QuantumResults.model_validate({
        "schema": QUANTUM_RESULTS_SCHEMA,
        "candidate_id": candidate_id,
        "master_revision": "v1.5.8f",
        "classification": "SOLVED",
        "collision": {"omega24_GHz": omega24, "f_readout_GHz": READOUT_GHz},
    })


def _complete_inputs(seed_candidate) -> GateInputs:
    solver = SolverResults.model_validate(
        {
            "schema": SOLVER_RESULTS_SCHEMA,
            "candidate_id": seed_candidate.candidate_id,
            "master_revision": seed_candidate.master_revision,
            "solver": {
                "name": "mock",
                "version": "0.1.0",
                "classification": "TEST_FIXTURE",
            },
            "run_id": "RUN-HARDENING",
            "convergence": {
                "status": "CONVERGED",
                "metric": "relative_change",
                "value": 1e-4,
                "tolerance": 1e-3,
            },
            "frequency_GHz": [3.395056, 5.0],
            "s_parameters": {"S21_dB": [-40.0, -1.0]},
            "eigenmodes": [{"frequency_GHz": 7.0}],
            "capabilities": {
                "eigenmode_spectrum": True,
                "p4pre_spectral_domain_complete": True,
                "domain_kind": "TEST_FIXTURE",
            },
            "synthetic": True,
        }
    )
    quantum = QuantumResults.model_validate(
        {
            "schema": QUANTUM_RESULTS_SCHEMA,
            "candidate_id": seed_candidate.candidate_id,
            "master_revision": seed_candidate.master_revision,
            "classification": "SOLVED",
            "collision": {
                "omega24_GHz": 4.40038762682525,
                "f_readout_GHz": READOUT_GHz,
            },
            "dressed_system": {
                "root_GHz": READOUT_GHz,
                "coupling_extraction": {
                    "eigenmode_MHz": 100.0,
                    "blackbox_MHz": 105.0,
                },
            },
            "tolerance": {
                "sample_count": 4,
                "screened_count": 4,
                "unscreened_count": 0,
                "seed": 7,
                "pass_count": 3,
                "fail_count": 1,
                "rejection_rate": 0.25,
                "confidence_interval": [0.05, 0.70],
                "failure_reasons_by_category": {},
            },
        }
    )
    return GateInputs(seed_candidate, solver, quantum)


NON_FINITE_GATE_CASES = [
    (CollisionGate, "quantum_results.collision.omega24_GHz"),
    (CollisionGate, "quantum_results.collision.f_readout_GHz"),
    (P6E2FilterGate, "solver_results.frequency_GHz[0]"),
    (P6E2FilterGate, "solver_results.frequency_GHz[1]"),
    (P6E2FilterGate, "solver_results.s_parameters.S21_dB[0]"),
    (P6E2FilterGate, "solver_results.s_parameters.S21_dB[1]"),
    (P4PreSpectralGate, "quantum_results.dressed_system.root_GHz"),
    (P4PreSpectralGate, "solver_results.eigenmodes[0].frequency_GHz"),
    (ToleranceGate, "quantum_results.tolerance.rejection_rate"),
    (ToleranceGate, "quantum_results.tolerance.confidence_interval[0]"),
    (ToleranceGate, "quantum_results.tolerance.sample_count"),
    (ToleranceGate, "quantum_results.tolerance.seed"),
    (ToleranceGate, "quantum_results.tolerance.pass_count"),
    (ToleranceGate, "quantum_results.tolerance.fail_count"),
    (ToleranceGate, "quantum_results.tolerance.screened_count"),
    (ToleranceGate, "quantum_results.tolerance.unscreened_count"),
    (
        ToleranceGate,
        "quantum_results.tolerance.failure_reasons_by_category.geometry",
    ),
    (
        CouplingExtractionGate,
        "quantum_results.dressed_system.coupling_extraction.eigenmode_MHz",
    ),
    (
        CouplingExtractionGate,
        "quantum_results.dressed_system.coupling_extraction.blackbox_MHz",
    ),
]

FINITE_GATE_SHA256 = {
    CollisionGate: "535604c8e860cc5f5b237510d1e541195a4aa6386611d21973ef2c74b2d9915b",
    P6E2FilterGate: "897054f421ff7c145d41bd7744cb602cd8e3b3c8e74f5efdf870ecc3079d6088",
    P4PreSpectralGate: "27b94919f1230b4cf405709d70fa066dd9cd76ff86ab1c938631affdd2658884",
    ToleranceGate: "2745fc41ddaf42bd8f390df4c7e59746c58f068d56fab9bdcfe5cff0d29202a8",
    CouplingExtractionGate: "ef15dbd161256758b3be0573018f4509657da4d8b827e896763771643ff9cb20",
}
FINITE_REPORT_SHA256 = (
    "5b5ee0891294f6e53f5b55f8cbec7522997a3af2eebe6f8ba4dff429141f0f7b"
)


def _inject_non_finite(inputs: GateInputs, path: str, value: float) -> None:
    if path == "quantum_results.collision.omega24_GHz":
        inputs.quantum_results.collision["omega24_GHz"] = value
    elif path == "quantum_results.collision.f_readout_GHz":
        inputs.quantum_results.collision["f_readout_GHz"] = value
    elif path == "solver_results.frequency_GHz[0]":
        inputs.solver_results.frequency_GHz[0] = value
    elif path == "solver_results.frequency_GHz[1]":
        inputs.solver_results.frequency_GHz[1] = value
    elif path == "solver_results.s_parameters.S21_dB[0]":
        inputs.solver_results.s_parameters["S21_dB"][0] = value
    elif path == "solver_results.s_parameters.S21_dB[1]":
        inputs.solver_results.s_parameters["S21_dB"][1] = value
    elif path == "quantum_results.dressed_system.root_GHz":
        inputs.quantum_results.dressed_system["root_GHz"] = value
    elif path == "solver_results.eigenmodes[0].frequency_GHz":
        # model_copy bypasses the assignment validator without mutating the
        # original Pydantic object in place.
        inputs.solver_results.eigenmodes[0] = (
            inputs.solver_results.eigenmodes[0].model_copy(
                update={"frequency_GHz": value}
            )
        )
    elif path.startswith("quantum_results.tolerance."):
        leaf = path.removeprefix("quantum_results.tolerance.")
        if leaf == "confidence_interval[0]":
            inputs.quantum_results.tolerance["confidence_interval"][0] = value
        elif leaf == "failure_reasons_by_category.geometry":
            inputs.quantum_results.tolerance["failure_reasons_by_category"][
                "geometry"
            ] = value
        else:
            inputs.quantum_results.tolerance[leaf] = value
    elif path.endswith("coupling_extraction.eigenmode_MHz"):
        inputs.quantum_results.dressed_system["coupling_extraction"][
            "eigenmode_MHz"
        ] = value
    elif path.endswith("coupling_extraction.blackbox_MHz"):
        inputs.quantum_results.dressed_system["coupling_extraction"][
            "blackbox_MHz"
        ] = value
    else:  # pragma: no cover - the parameter table and injector must agree
        raise AssertionError(f"no injector for {path}")


# --- D1: non-finite values never clear the collision rule -----------------


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_the_collision_rule_refuses_a_non_finite_frequency(value):
    with pytest.raises(ValueError, match="non-finite"):
        collision.passes(value, READOUT_GHz)
    with pytest.raises(ValueError, match="non-finite"):
        collision.passes(READOUT_GHz, value)


def test_the_collision_rule_is_unchanged_for_finite_values():
    assert collision.passes(READOUT_GHz, READOUT_GHz - 0.013)
    assert not collision.passes(READOUT_GHz, READOUT_GHz - 0.0129)


@pytest.mark.parametrize("value", [math.inf, math.nan])
def test_the_collision_gate_is_incomplete_on_non_finite_data_that_bypassed_the_contract(
    seed_candidate, value
):
    valid = _quantum()
    bypass = QuantumResults.model_construct(
        **{**valid.__dict__, "collision": {"omega24_GHz": value, "f_readout_GHz": READOUT_GHz}}
    )
    result = CollisionGate().evaluate(GateInputs(seed_candidate, quantum_results=bypass))
    assert result.status is GateStatus.INCOMPLETE
    assert "non-finite" in result.reason


def test_the_collision_gate_still_passes_the_nominal_device(seed_candidate):
    result = CollisionGate().evaluate(GateInputs(seed_candidate, quantum_results=_quantum()))
    assert result.status is GateStatus.PASS


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize(
    "gate_type",
    [
        CollisionGate,
        P6E2FilterGate,
        P4PreSpectralGate,
        ToleranceGate,
        CouplingExtractionGate,
    ],
)
def test_every_computational_gate_fails_closed_on_bypassed_non_finite_evidence(
    seed_candidate, gate_type, value
):
    inputs = _complete_inputs(seed_candidate)
    # Mutating a list bypasses Pydantic assignment validation and reproduces
    # the route a direct GateInputs caller could previously use to get PASS.
    inputs.solver_results.frequency_GHz[1] = value
    result = gate_type().evaluate(inputs)
    assert result.status is GateStatus.INCOMPLETE
    assert "non-finite" in result.reason
    assert "solver_results.frequency_GHz[1]" in result.reason


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize(
    ("gate_type", "path"),
    NON_FINITE_GATE_CASES,
    ids=[path for _, path in NON_FINITE_GATE_CASES],
)
def test_every_gate_numeric_leaf_fails_closed(
    seed_candidate, gate_type, path, value
):
    inputs = _complete_inputs(seed_candidate)
    _inject_non_finite(inputs, path, value)
    result = gate_type().evaluate(inputs)
    assert result.status is GateStatus.INCOMPLETE
    assert "non-finite" in result.reason
    assert path in result.reason


def test_finite_gate_and_report_bytes_match_the_pre_fix_branch(seed_candidate):
    inputs = _complete_inputs(seed_candidate)
    for gate_type, expected in FINITE_GATE_SHA256.items():
        body = gate_type().evaluate(inputs).model_dump_json().encode()
        assert hashlib.sha256(body).hexdigest() == expected

    report = evaluate_candidate(
        seed_candidate,
        inputs.solver_results,
        inputs.quantum_results,
    )
    assert (
        hashlib.sha256(report.model_dump_json().encode()).hexdigest()
        == FINITE_REPORT_SHA256
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_p4_cannot_pass_a_non_finite_readout_root(seed_candidate, value):
    inputs = _complete_inputs(seed_candidate)
    inputs.quantum_results.dressed_system["root_GHz"] = value
    result = P4PreSpectralGate().evaluate(inputs)
    assert result.status is GateStatus.INCOMPLETE
    assert "quantum_results.dressed_system.root_GHz" in result.reason


def test_quantum_contract_finds_non_finite_values_inside_numpy_arrays():
    with pytest.raises(ValueError, match=r"tolerance.samples\[1\]"):
        QuantumResults.model_validate(
            {
                "schema": QUANTUM_RESULTS_SCHEMA,
                "candidate_id": "QMHP-CEM-A-RF-000001",
                "master_revision": "v1.5.8f",
                "classification": "SOLVED",
                "tolerance": {"samples": np.array([0.0, math.nan])},
            }
        )


@pytest.mark.parametrize("parameter", ["EC_GHz", "EJ_GHz", "EL_GHz"])
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_collision_screen_refuses_non_finite_energy_before_solving(
    monkeypatch, parameter, value
):
    calls = []
    monkeypatch.setattr(
        collision.fluxonium,
        "solve_static",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    with pytest.raises(collision.NonFiniteDomainError) as exc_info:
        collision.screen(**{parameter: value})
    assert exc_info.value.parameter == parameter
    assert exc_info.value.value == value or math.isnan(exc_info.value.value)
    assert exc_info.value.domain == "finite real"
    assert calls == []


def test_collision_screen_does_not_prejudge_the_pending_positive_domain(monkeypatch):
    class Spectrum:
        @staticmethod
        def f(upper, lower):
            assert (upper, lower) == (4, 2)
            return 4.4

    calls = []

    def solve_static(*args, **kwargs):
        calls.append((args, kwargs))
        return Spectrum()

    monkeypatch.setattr(collision.fluxonium, "solve_static", solve_static)
    monkeypatch.setattr(
        collision.dressed_system,
        "solve_dressed_root",
        lambda *, spectrum: READOUT_GHz,
    )
    collision.screen(EC_GHz=-0.6, EJ_GHz=0.0, EL_GHz=-1.58)
    assert calls, "finite zero/negative energies remain pending the D2 decision"


# --- D3: no gate can be evaluated on another candidate's evidence ---------


def test_a_directly_built_gate_input_refuses_another_candidates_evidence(
    seed_candidate, monkeypatch
):
    calls = []
    monkeypatch.setattr(CollisionGate, "_evaluate", lambda self, inputs: calls.append(inputs))
    with pytest.raises(ValueError, match="quantum result candidate_id"):
        CollisionGate().evaluate(
            GateInputs(seed_candidate, quantum_results=_quantum("QMHP-CEM-A-RF-000009"))
        )
    assert calls == []


def test_a_directly_built_gate_input_refuses_another_master_revision(seed_candidate):
    other = _quantum().model_copy(update={"master_revision": "different-revision"})
    with pytest.raises(ValueError, match="quantum result master_revision"):
        GateInputs(seed_candidate, quantum_results=other)


def test_matching_evidence_is_accepted(seed_candidate):
    inputs = GateInputs(seed_candidate, quantum_results=_quantum())
    assert inputs.quantum_results.candidate_id == seed_candidate.candidate_id


def test_identity_is_rechecked_after_evidence_mutation(seed_candidate):
    inputs = GateInputs(seed_candidate, quantum_results=_quantum())
    inputs.quantum_results.candidate_id = "QMHP-CEM-A-RF-000009"
    with pytest.raises(EvidenceIdentityError, match="quantum result candidate_id"):
        CollisionGate().evaluate(inputs)


def test_identity_is_rechecked_after_evidence_replacement(seed_candidate):
    inputs = GateInputs(seed_candidate, quantum_results=_quantum())
    inputs.quantum_results = _quantum("QMHP-CEM-A-RF-000009")
    with pytest.raises(EvidenceIdentityError, match="quantum result candidate_id"):
        CollisionGate().evaluate(inputs)


def test_same_identity_evidence_replacement_remains_supported(seed_candidate):
    inputs = GateInputs(seed_candidate, quantum_results=_quantum())
    inputs.quantum_results = _quantum()
    assert CollisionGate().evaluate(inputs).status is GateStatus.PASS


def test_candidate_none_mode_remains_supported_for_standalone_gate_calls():
    inputs = GateInputs(None, quantum_results=_quantum())
    assert CollisionGate().evaluate(inputs).status is GateStatus.PASS


def test_an_overridden_public_validator_cannot_bypass_the_choke_point(
    seed_candidate, monkeypatch
):
    class UnsafeInputs(GateInputs):
        def validate_identity(self):
            return None

    inputs = UnsafeInputs(seed_candidate, quantum_results=_quantum())
    inputs.quantum_results.candidate_id = "QMHP-CEM-A-RF-000009"
    calls = []
    monkeypatch.setattr(
        CollisionGate,
        "_evaluate",
        lambda self, current_inputs: calls.append(current_inputs),
    )
    with pytest.raises(EvidenceIdentityError, match="quantum result candidate_id"):
        CollisionGate().evaluate(inputs)
    assert calls == []


def test_direct_gate_inputs_refuse_a_stale_candidate_revision(seed_candidate):
    candidate = seed_candidate.model_copy(
        update={"master_revision": "stale-revision"}, deep=True
    )
    quantum = _quantum().model_copy(update={"master_revision": "stale-revision"})
    with pytest.raises(EvidenceIdentityError, match="loaded frozen master"):
        GateInputs(candidate, quantum_results=quantum)


def test_a_bound_solver_revision_cannot_be_downgraded_to_legacy_none(
    seed_candidate,
):
    inputs = _complete_inputs(seed_candidate)
    inputs.solver_results.master_revision = None
    with pytest.raises(EvidenceIdentityError, match="construction-bound"):
        P6E2FilterGate().evaluate(inputs)


def test_coordinated_candidate_and_evidence_mutation_cannot_change_the_binding(
    seed_candidate,
):
    candidate = seed_candidate.model_copy(deep=True)
    quantum = _quantum()
    inputs = GateInputs(candidate, quantum_results=quantum)
    candidate.candidate_id = "QMHP-CEM-A-RF-000009"
    quantum.candidate_id = "QMHP-CEM-A-RF-000009"
    with pytest.raises(EvidenceIdentityError, match="construction-bound"):
        CollisionGate().evaluate(inputs)


def test_gate_mutation_cannot_escape_the_post_evaluation_identity_check(
    seed_candidate, monkeypatch
):
    inputs = GateInputs(seed_candidate, quantum_results=_quantum())

    def mutate_then_pass(gate, current_inputs):
        current_inputs.quantum_results.candidate_id = "QMHP-CEM-A-RF-000009"
        return gate._result(
            GateStatus.PASS,
            "would otherwise pass",
            evidence_class=current_inputs.quantum_results.classification,
        )

    monkeypatch.setattr(CollisionGate, "_evaluate", mutate_then_pass)
    with pytest.raises(EvidenceIdentityError, match="quantum result candidate_id"):
        CollisionGate().evaluate(inputs)


# --- D4: a completed record is final through the store --------------------


def _digest(directory: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(directory.rglob("*")):
        h.update(p.relative_to(directory).as_posix().encode())
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


@pytest.fixture()
def completed(tmp_path):
    store = BatchStore("BATCH-HARDEN", tmp_path)
    a = store.candidate_dir("CAND-A")
    b = store.candidate_dir("CAND-B")
    store.write_json(Path("CAND-B/candidate.json"), {"input": "original"})
    store.write_json(Path("CAND-B/gate_report.json"), {"overall_status": "PASS"})
    return store, a, b


@pytest.mark.parametrize("name", ["candidate.json", "brand_new.json", "nested/new.json"])
def test_nothing_more_is_written_into_a_completed_candidate(completed, name):
    store, _, b = completed
    before = _digest(b)
    with pytest.raises(ResultAlreadyExists):
        store.write_json(Path("CAND-B") / name, {"after": "completion"})
    assert _digest(b) == before


def test_another_candidates_path_cannot_be_reached_with_dot_dot(completed):
    store, a, b = completed
    with pytest.raises(ValueError, match="'..'"):
        store.write_json(Path("CAND-A/../CAND-B/injected.json"), {"x": 1})
    with pytest.raises(ValueError, match="'..'"):
        store.write_json(Path("CAND-A/../CAND-A/same.json"), {"x": 1})
    assert not (b / "injected.json").exists()


@pytest.mark.parametrize("target_completed", [True, False])
def test_a_symbolic_link_inside_the_batch_is_refused(completed, tmp_path, target_completed):
    store, a, b = completed
    target = b if target_completed else store.candidate_dir("CAND-C")
    (a / "link").symlink_to(target)
    with pytest.raises(ValueError, match="symbolic link"):
        store.write_json(Path("CAND-A/link/via_link.json"), {"x": 1})
    assert not (target / "via_link.json").exists()


def test_a_symbolic_link_out_of_the_batch_is_refused(completed, tmp_path):
    store, a, _ = completed
    outside = tmp_path / "outside"
    outside.mkdir()
    (a / "out").symlink_to(outside)
    with pytest.raises(ValueError):
        store.write_json(Path("CAND-A/out/x.json"), {"x": 1})
    assert list(outside.iterdir()) == []


def test_an_absolute_path_inside_the_batch_is_refused(completed):
    store, a, _ = completed
    with pytest.raises(ValueError, match="absolute"):
        store.write_json(a / "absolute.json", {"x": 1})
    assert not (a / "absolute.json").exists()


@pytest.mark.parametrize(
    "path",
    [
        "manifest.sha256/nested.json",
        "Manifest.sha256/nested.json",
        "Batch_Report.json",
        "batch_report.json/nested.json",
        "CAND/Gate_Report.json",
        "CAND/gate_report.json/nested.json",
    ],
)
def test_completion_markers_cannot_be_turned_into_directories(tmp_path, path):
    store = BatchStore("BATCH-RESERVED", tmp_path)
    store.candidate_dir("CAND")
    with pytest.raises(ValueError, match="created only|reserved"):
        store.write_json(Path(path), {"x": 1})
    assert not (store.batch_dir / path).exists()


@pytest.mark.parametrize(
    "candidate_id",
    ["manifest.sha256", "Manifest.sha256", "batch_report.json", "gate_report.json"],
)
def test_reserved_batch_names_cannot_be_candidate_directories(
    tmp_path, candidate_id
):
    store = BatchStore("BATCH-RESERVED-CANDIDATE", tmp_path)
    with pytest.raises(ValueError, match="reserved"):
        store.candidate_dir(candidate_id)


def test_a_completed_batch_accepts_nothing_more(completed):
    store, a, _ = completed
    draft = {"manifest_sha256": manifest.MANIFEST_DIGEST_PLACEHOLDER}
    _, expected = manifest.preview_with_batch_report(store.batch_dir, draft)
    store.write_json(Path("batch_report.json"), {"manifest_sha256": expected})
    store.seal_batch(
        lambda: manifest.build(store.batch_dir, self_referential_report=True),
        expected,
    )
    with pytest.raises(ResultAlreadyExists):
        store.write_json(Path("CAND-A/late.json"), {"x": 1})
    with pytest.raises(ResultAlreadyExists):
        store.write_json(Path("late.json"), {"x": 1})
    with pytest.raises(ResultAlreadyExists):
        store.candidate_dir("CAND-LATE")


def test_an_incomplete_candidate_still_accepts_new_files(completed):
    store, a, _ = completed
    store.write_json(Path("CAND-A/candidate.json"), {"input": 1})
    store.write_json(Path("CAND-A/solver/solver_input.json"), {"input": 1})
    assert json.loads((a / "solver" / "solver_input.json").read_text()) == {"input": 1}


def test_a_writer_that_passed_the_check_finishes_before_completion_lands(tmp_path, monkeypatch):
    """The check and the write are one locked step.

    T1 is paused inside the lock just after its completion check. A completion
    started meanwhile must wait for T1, so T1's file is never written into a
    directory that is already complete, and a later write is refused.
    """
    store = BatchStore("BATCH-RACE", tmp_path)
    cand = store.candidate_dir("CAND")
    paused, release = threading.Event(), threading.Event()
    real_check = BatchStore._refuse_if_completed

    def check_then_pause(self, relative):
        real_check(self, relative)
        if threading.current_thread().name == "T1":
            paused.set()
            release.wait(10)

    monkeypatch.setattr(BatchStore, "_refuse_if_completed", check_then_pause)
    t1 = threading.Thread(
        target=store.write_json,
        args=(Path("CAND/late_input.json"), {"x": 1}),
        name="T1",
    )
    t1.start()
    assert paused.wait(10)
    t2 = threading.Thread(
        target=store.write_json,
        args=(Path("CAND/gate_report.json"), {"done": True}),
        name="T2",
    )
    t2.start()
    t2.join(0.5)
    assert t2.is_alive(), "completion did not wait for the writer holding the lock"
    assert not (cand / "gate_report.json").exists()
    release.set()
    t1.join(10)
    t2.join(10)
    assert (cand / "late_input.json").exists() and (cand / "gate_report.json").exists()
    with pytest.raises(ResultAlreadyExists):
        store.write_json(Path("CAND/later.json"), {"x": 1})


def test_concurrent_completions_produce_exactly_one_marker(tmp_path):
    store = BatchStore("BATCH-RACE2", tmp_path)
    cand = store.candidate_dir("CAND")
    barrier = threading.Barrier(8)
    outcomes = []

    def complete(i):
        barrier.wait()
        try:
            store.write_json(Path("CAND/gate_report.json"), {"writer": i})
            outcomes.append("ok")
        except ResultAlreadyExists:
            outcomes.append("refused")

    threads = [threading.Thread(target=complete, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert outcomes.count("ok") == 1 and outcomes.count("refused") == 7
    assert [p.name for p in cand.iterdir()] == ["gate_report.json"]


def test_the_markers_are_the_pipeline_ones():
    assert results_store.CANDIDATE_COMPLETION_MARKER == "gate_report.json"
    assert results_store.BATCH_COMPLETION_MARKER == "manifest.sha256"


def test_batch_seal_refuses_manifest_drift_without_publishing_marker(tmp_path):
    store = BatchStore("BATCH-SEAL-DRIFT", tmp_path)
    store.write_json(Path("record.json"), {"version": 1})
    draft = {"manifest_sha256": manifest.MANIFEST_DIGEST_PLACEHOLDER}
    _, expected = manifest.preview_with_batch_report(store.batch_dir, draft)
    store.write_json(Path("batch_report.json"), {"manifest_sha256": expected})
    store.write_json(Path("late.json"), {"version": 2})

    with pytest.raises(RuntimeError, match="preview changed"):
        store.seal_batch(
            lambda: manifest.build(store.batch_dir, self_referential_report=True),
            expected,
        )
    assert not (store.batch_dir / "manifest.sha256").exists()


def test_batch_seal_refuses_a_wrong_embedded_digest(tmp_path):
    store = BatchStore("BATCH-SEAL-REPORT", tmp_path)
    store.write_json(Path("record.json"), {"version": 1})
    draft = {"manifest_sha256": manifest.MANIFEST_DIGEST_PLACEHOLDER}
    _, expected = manifest.preview_with_batch_report(store.batch_dir, draft)
    store.write_json(Path("batch_report.json"), {"manifest_sha256": "f" * 64})

    with pytest.raises(RuntimeError, match="embedded|manifest_sha256"):
        store.seal_batch(
            lambda: manifest.build(store.batch_dir, self_referential_report=True),
            expected,
        )
    assert not (store.batch_dir / "manifest.sha256").exists()


def test_batch_seal_hashes_the_manifest_body_itself(tmp_path):
    store = BatchStore("BATCH-SEAL-BUILDER", tmp_path)
    store.write_json(Path("record.json"), {"version": 1})
    draft = {"manifest_sha256": manifest.MANIFEST_DIGEST_PLACEHOLDER}
    _, expected = manifest.preview_with_batch_report(store.batch_dir, draft)
    store.write_json(Path("batch_report.json"), {"manifest_sha256": expected})

    with pytest.raises(RuntimeError, match="builder reported"):
        store.seal_batch(lambda: ("not a manifest\n", expected), expected)
    assert not (store.batch_dir / "manifest.sha256").exists()


def test_batch_seal_and_root_writer_share_one_completion_lock(tmp_path):
    store = BatchStore("BATCH-SEAL-WRITER", tmp_path)
    store.write_json(Path("record.json"), {"version": 1})
    draft = {"manifest_sha256": manifest.MANIFEST_DIGEST_PLACEHOLDER}
    _, expected = manifest.preview_with_batch_report(store.batch_dir, draft)
    store.write_json(Path("batch_report.json"), {"manifest_sha256": expected})
    building, release = threading.Event(), threading.Event()
    outcomes = []

    def paused_build():
        building.set()
        assert release.wait(10)
        return manifest.build(store.batch_dir, self_referential_report=True)

    def seal():
        store.seal_batch(paused_build, expected)
        outcomes.append("sealed")

    def write():
        try:
            store.write_json(Path("late.json"), {"version": 2})
            outcomes.append("wrote")
        except ResultAlreadyExists:
            outcomes.append("refused")

    sealer = threading.Thread(target=seal)
    sealer.start()
    assert building.wait(10)
    writer = threading.Thread(target=write)
    writer.start()
    writer.join(0.5)
    assert writer.is_alive(), "writer did not wait for the sealing lock"
    release.set()
    sealer.join(10)
    writer.join(10)

    assert sorted(outcomes) == ["refused", "sealed"]
    assert not (store.batch_dir / "late.json").exists()
    assert manifest.verify(store.batch_dir) == []


def test_large_finite_integers_do_not_overflow_the_finiteness_scan(seed_candidate):
    inputs = _complete_inputs(seed_candidate)
    inputs.quantum_results.tolerance["seed"] = 10**1000
    assert ToleranceGate().evaluate(inputs).status is GateStatus.PASS


def test_two_batch_sealers_publish_exactly_one_manifest(tmp_path):
    store = BatchStore("BATCH-SEAL-RACE", tmp_path)
    store.write_json(Path("record.json"), {"version": 1})
    draft = {"manifest_sha256": manifest.MANIFEST_DIGEST_PLACEHOLDER}
    _, expected = manifest.preview_with_batch_report(store.batch_dir, draft)
    store.write_json(Path("batch_report.json"), {"manifest_sha256": expected})
    barrier = threading.Barrier(2)
    outcomes = []

    def seal():
        barrier.wait()
        try:
            store.seal_batch(
                lambda: manifest.build(
                    store.batch_dir, self_referential_report=True
                ),
                expected,
            )
            outcomes.append("ok")
        except ResultAlreadyExists:
            outcomes.append("refused")

    threads = [threading.Thread(target=seal) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert sorted(outcomes) == ["ok", "refused"]
    assert manifest.verify(store.batch_dir) == []
