"""Regression tests for the gaps left after PR #10 (design note §7, D1, D3, D4).

Each defect was reproduced on main at 79844b7 before the fix. Every test here
fails on that commit and passes after it; the controls pass on both.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
from pathlib import Path

import pytest

from contracts.common import GateStatus
from contracts.results import QUANTUM_RESULTS_SCHEMA, QuantumResults
from evaluator.base import GateInputs
from evaluator.computational import CollisionGate
from models import collision
from orchestrator import results_store
from orchestrator.results_store import BatchStore, ResultAlreadyExists

READOUT_GHz = 4.301974466427182


def _quantum(candidate_id: str = "QMHP-CEM-A-RF-000001", omega24: float = 4.40038762682525) -> QuantumResults:
    return QuantumResults.model_validate({
        "schema": QUANTUM_RESULTS_SCHEMA,
        "candidate_id": candidate_id,
        "master_revision": "v1.5.8f",
        "classification": "SOLVED",
        "collision": {"omega24_GHz": omega24, "f_readout_GHz": READOUT_GHz},
    })


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
def test_the_collision_gate_is_incomplete_on_non_finite_data_that_bypassed_the_contract(seed_candidate, value):
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


# --- D3: no gate can be evaluated on another candidate's evidence ---------


def test_a_directly_built_gate_input_refuses_another_candidates_evidence(seed_candidate, monkeypatch):
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
    store.write_json(b / "candidate.json", {"input": "original"})
    store.write_json(b / "gate_report.json", {"overall_status": "PASS"})
    return store, a, b


@pytest.mark.parametrize("name", ["candidate.json", "brand_new.json", "nested/new.json"])
def test_nothing_more_is_written_into_a_completed_candidate(completed, name):
    store, _, b = completed
    before = _digest(b)
    with pytest.raises(ResultAlreadyExists):
        store.write_json(b / name, {"after": "completion"})
    assert _digest(b) == before


def test_another_candidates_path_cannot_be_reached_with_dot_dot(completed):
    store, a, b = completed
    with pytest.raises(ValueError, match="'..'"):
        store.write_json(a / ".." / "CAND-B" / "injected.json", {"x": 1})
    with pytest.raises(ValueError, match="'..'"):
        store.write_json(a / ".." / "CAND-A" / "same.json", {"x": 1})
    assert not (b / "injected.json").exists()


@pytest.mark.parametrize("target_completed", [True, False])
def test_a_symbolic_link_inside_the_batch_is_refused(completed, tmp_path, target_completed):
    store, a, b = completed
    target = b if target_completed else store.candidate_dir("CAND-C")
    (a / "link").symlink_to(target)
    with pytest.raises(ValueError, match="symbolic link"):
        store.write_json(a / "link" / "via_link.json", {"x": 1})
    assert not (target / "via_link.json").exists()


def test_a_symbolic_link_out_of_the_batch_is_refused(completed, tmp_path):
    store, a, _ = completed
    outside = tmp_path / "outside"
    outside.mkdir()
    (a / "out").symlink_to(outside)
    with pytest.raises(ValueError):
        store.write_json(a / "out" / "x.json", {"x": 1})
    assert list(outside.iterdir()) == []


def test_a_completed_batch_accepts_nothing_more(completed):
    store, a, _ = completed
    store.write_json(store.batch_dir / "batch_report.json", {"done": True})
    with pytest.raises(ResultAlreadyExists):
        store.write_json(a / "late.json", {"x": 1})
    with pytest.raises(ResultAlreadyExists):
        store.write_json(store.batch_dir / "late.json", {"x": 1})
    with pytest.raises(ResultAlreadyExists):
        store.candidate_dir("CAND-LATE")


def test_an_incomplete_candidate_still_accepts_new_files(completed):
    store, a, _ = completed
    store.write_json(a / "candidate.json", {"input": 1})
    store.write_json(a / "solver" / "solver_input.json", {"input": 1})
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
    t1 = threading.Thread(target=store.write_json, args=(cand / "late_input.json", {"x": 1}), name="T1")
    t1.start()
    assert paused.wait(10)
    t2 = threading.Thread(target=store.write_json, args=(cand / "gate_report.json", {"done": True}), name="T2")
    t2.start()
    t2.join(0.5)
    assert t2.is_alive(), "completion did not wait for the writer holding the lock"
    assert not (cand / "gate_report.json").exists()
    release.set()
    t1.join(10)
    t2.join(10)
    assert (cand / "late_input.json").exists() and (cand / "gate_report.json").exists()
    with pytest.raises(ResultAlreadyExists):
        store.write_json(cand / "later.json", {"x": 1})


def test_concurrent_completions_produce_exactly_one_marker(tmp_path):
    store = BatchStore("BATCH-RACE2", tmp_path)
    cand = store.candidate_dir("CAND")
    barrier = threading.Barrier(8)
    outcomes = []

    def complete(i):
        barrier.wait()
        try:
            store.write_json(cand / "gate_report.json", {"writer": i})
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
    assert results_store.BATCH_COMPLETION_MARKER == "batch_report.json"
