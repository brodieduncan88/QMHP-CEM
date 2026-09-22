# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""The static-anchor hypothesis record: preserved measurements, the prepared (unexecuted)
electrostatic test, its refusal paths, and the guarantee that the existing method is left
untouched while the alternative is tested. No test here computes a capacitance on the QMHP
mesh."""
from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import scipy.sparse.linalg as spla

REPO = Path(__file__).resolve().parents[1]
HERE = REPO / "experiments" / "static-anchor-hypothesis"
FMD = REPO / "experiments" / "first-moment-diagnostic"
DOC = REPO / "docs" / "coupled-candidate" / "static-anchor-hypothesis.md"

#: frozen before any static value existed on the QMHP mesh; changing it needs a new
#: pre-declaration, not an edit
PREDECLARATION_SHA256 = "6f31470a38a58cfbe33eb7bee61c6ec06eeea428bdfbd943b39e52e3e4868f29"

#: the existing method, which this record tests an alternative to and must not change
EXISTING_METHOD = {
    "models/route_a_inversion.py": "4dcf9ef584f2a1e99828bde1ee8bab179178c1b0539bfb63cba60974ebbbac03",
    "models/coupling_extraction.py": "2f7b845e08659e691cb2028c8a9ba1582b748281ee0939e7b3d6bd63b61668f8",
    "experiments/first-moment-diagnostic/reference_model.py": "14700555f63c126cf76b96b406d4e6a101ec12f49395a7d46b11803fcf515a57",
    "experiments/first-moment-diagnostic/evaluate_record.py": "1ee8c824408d0719e57ad4f4d935a90ccfc005b401e3be389b9a74d2ac1f647b",
    "experiments/first-moment-diagnostic/prepare.py": "e14b54338c46e418e5a8193ab4742b20cf0ffb90e9de7d5168582d6239ed110d",
    "experiments/first-moment-diagnostic/run_diagnostic.py": "05f21ce4a7d4b276ec1a822e27ed9a1fe87f4281ce813e7f09441532a64f3db1",
    "experiments/first-moment-diagnostic/config.candidate.json": "eb15031cd18c4db120e7a35d5dfa3360206c9e34c23aca804c121c0b596d8454",
    "docs/coupled-candidate/coupling-definition.md": "143091c596b41c46baeed372ba6afdd6eb524c3c9d87e8af57bb9de19cc6b5d1",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str):
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location(f"sah_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def sc():
    return _load("static_capacitance")


@pytest.fixture(scope="module")
def af():
    return _load("anchor_fem")


@pytest.fixture(scope="module")
def pre():
    return json.loads((HERE / "predeclaration.json").read_text())


@pytest.fixture(scope="module")
def measured():
    return json.loads((HERE / "measurements.json").read_text())


# --- the gate ---------------------------------------------------------------------------

def test_no_approval_is_committed_and_the_test_refuses_without_one():
    assert not (HERE / "TEST-APPROVAL.json").exists(), "prepared, not approved"
    proc = subprocess.run([sys.executable, str(HERE / "static_capacitance.py")],
                          capture_output=True, text=True, cwd=REPO)
    assert proc.returncode == 2
    assert proc.stderr.startswith("REFUSED:") and "PREPARED, NOT APPROVED" in proc.stderr
    assert not list((REPO / "results").glob("STATIC-ANCHOR-TEST-*")), "nothing was written"


def test_a_stale_approval_is_refused_before_anything_is_created(sc, pre, tmp_path,
                                                                monkeypatch):
    stale = {"authorises": "one execution of the static-anchor test",
             "mesh_sha256": "0" * 64, "predeclaration_sha256": _sha(sc.PREDECLARATION),
             "code_sha256": {n: _sha(HERE / n) for n in sc.CODE_FILES}}
    approval = tmp_path / "TEST-APPROVAL.json"
    approval.write_text(json.dumps(stale))
    monkeypatch.setattr(sc, "APPROVAL", approval)
    monkeypatch.setattr(sc, "RESULTS_ROOT", tmp_path / "results")
    with pytest.raises(sc.Refusal, match="mesh_sha256 does not match"):
        sc.execute()
    assert not (tmp_path / "results").exists(), "refused before the attempt was spent"


def test_an_approval_for_other_code_is_refused(sc, tmp_path, monkeypatch):
    other = {"authorises": "one execution of the static-anchor test",
             "mesh_sha256": json.loads(sc.PREDECLARATION.read_text())["configuration"]["mesh_sha256"],
             "predeclaration_sha256": _sha(sc.PREDECLARATION),
             "code_sha256": {n: "0" * 64 for n in sc.CODE_FILES}}
    approval = tmp_path / "TEST-APPROVAL.json"
    approval.write_text(json.dumps(other))
    monkeypatch.setattr(sc, "APPROVAL", approval)
    monkeypatch.setattr(sc, "RESULTS_ROOT", tmp_path / "results")
    with pytest.raises(sc.Refusal, match="code_sha256 does not match"):
        sc.execute()


def _synthetic_gate(sc, tmp_path, monkeypatch):
    """Route execute() onto a synthetic slab in tmp_path: no QMHP data, no process limits."""
    approval = tmp_path / "TEST-APPROVAL.json"
    approval.write_text("{}")
    monkeypatch.setattr(sc, "APPROVAL", approval)
    monkeypatch.setattr(sc, "RESULTS_ROOT", tmp_path / "results")
    monkeypatch.setattr(sc, "require_approval", lambda pre: {"run_label": "synthetic"})
    monkeypatch.setattr(sc, "band_baseline", lambda pre: 2.0)
    monkeypatch.setattr(sc, "_qmhp_mesh", lambda pre: sc._slab(4, island_patch=True))
    monkeypatch.setattr(sc, "_enforce_budget", lambda pre: {"synthetic": "no limits in pytest"})


def test_a_granted_attempt_writes_raw_levels_then_a_summary_and_is_spent(sc, tmp_path,
                                                                         monkeypatch):
    _synthetic_gate(sc, tmp_path, monkeypatch)
    rec = sc.execute()
    assert rec.parent == tmp_path / "results" and rec.name.startswith("STATIC-ANCHOR-TEST-")
    assert sorted(p.name for p in rec.iterdir()) == ["level0.json", "level1.json",
                                                     "summary.json"]
    summary = json.loads((rec / "summary.json").read_text())
    assert "verdict" in summary["outcome"]
    assert summary["environment"]["code_sha256"] == {n: _sha(HERE / n) for n in sc.CODE_FILES}
    assert summary["predeclaration_sha256"] == PREDECLARATION_SHA256
    with pytest.raises(sc.Refusal, match="the one attempt is spent"):
        sc.execute()


def test_a_failure_inside_the_attempt_is_recorded_beside_the_raw_levels(sc, tmp_path,
                                                                        monkeypatch):
    _synthetic_gate(sc, tmp_path, monkeypatch)
    real, calls = sc.static_capacitance, []

    def fails_on_level_1(mesh, **model):
        calls.append(1)
        if len(calls) == 2:
            raise sc.BudgetExceeded("SIGALRM: a declared budget limit was reached")
        return real(mesh, **model)

    monkeypatch.setattr(sc, "static_capacitance", fails_on_level_1)
    with pytest.raises(sc.BudgetExceeded):
        sc.execute()
    (rec,) = (tmp_path / "results").glob("STATIC-ANCHOR-TEST-*")
    assert sorted(p.name for p in rec.iterdir()) == ["failure.json", "level0.json"]
    failure = json.loads((rec / "failure.json").read_text())
    assert failure["levels_completed"] == [0] and "no retry" in failure["verdict"]
    assert "SIGALRM" in failure["error"]
    with pytest.raises(sc.Refusal, match="the one attempt is spent"):
        sc.execute()


def test_a_failure_after_both_levels_still_leaves_a_failure_record(sc, tmp_path, monkeypatch):
    _synthetic_gate(sc, tmp_path, monkeypatch)

    def broken(levels, pre):
        raise RuntimeError("integrity evaluation crashed")

    monkeypatch.setattr(sc, "integrity", broken)
    with pytest.raises(RuntimeError, match="integrity evaluation crashed"):
        sc.execute()
    (rec,) = (tmp_path / "results").glob("STATIC-ANCHOR-TEST-*")
    assert sorted(p.name for p in rec.iterdir()) == ["failure.json", "level0.json",
                                                     "level1.json"]
    assert json.loads((rec / "failure.json").read_text())["levels_completed"] == [0, 1]


@pytest.mark.parametrize("budget, work, expect", [
    ({"cpu_minutes": 10, "memory_GB": 8, "wall_cap_minutes": 1 / 60},
     "import time\nwhile True: time.sleep(0.05)", "SIGALRM"),
    ({"cpu_minutes": 1 / 60, "memory_GB": 8, "wall_cap_minutes": 1},
     "while True: pass", "SIGXCPU"),
    ({"cpu_minutes": 10, "memory_GB": 4, "wall_cap_minutes": 1},
     "import numpy\nnumpy.ones(6 * 1024**3 // 8)", "MemoryError"),
])
def test_the_declared_budget_binds_the_process(budget, work, expect):
    # a subprocess, so the limits never apply to the test runner
    script = (f"import importlib.util, sys\nsys.path.insert(0, {str(HERE)!r})\n"
              f"spec = importlib.util.spec_from_file_location('sc', {str(HERE / 'static_capacitance.py')!r})\n"
              "sc = importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)\n"
              f"sc._enforce_budget({{'budget': {budget!r}}})\n{work}\n")
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                          timeout=60)
    assert proc.returncode != 0 and expect in proc.stderr, proc.stderr[-400:]


def test_an_environment_that_cannot_apply_the_budget_is_refused_before_the_attempt(
        sc, pre, tmp_path, monkeypatch):
    _synthetic_gate(sc, tmp_path, monkeypatch)
    real_getrlimit = sc.resource.getrlimit
    monkeypatch.setattr(sc.resource, "getrlimit",
                        lambda r: (1024, 1024) if r == sc.resource.RLIMIT_AS else real_getrlimit(r))
    with pytest.raises(sc.Refusal, match="cannot be applied as declared"):
        sc.execute()
    assert not list((tmp_path / "results").glob("STATIC-ANCHOR-TEST-*")), "attempt not spent"


def test_the_draft_approval_matches_the_files_and_grants_exactly_one_attempt(sc, tmp_path,
                                                                          monkeypatch):
    draft = json.loads((HERE / "TEST-APPROVAL.draft.json").read_text())
    assert "NOT AN APPROVAL" in draft["DRAFT"], "a draft authorises nothing"
    assert draft["predeclaration_sha256"] == PREDECLARATION_SHA256
    assert draft["code_sha256"] == {n: _sha(HERE / n) for n in sc.CODE_FILES}, (
        "the code changed after the draft was reviewed: re-review the draft")
    granted = {k: v for k, v in draft.items() if k not in ("DRAFT", "how_to_grant_it")}
    approval = tmp_path / "TEST-APPROVAL.json"
    approval.write_text(json.dumps(granted))
    monkeypatch.setattr(sc, "APPROVAL", approval)
    assert sc.require_approval(json.loads(sc.PREDECLARATION.read_text()))["authorises"] == \
        "one execution of the static-anchor test"
    assert granted["budget"]["attempts"] == 1


def test_the_invocation_carries_an_outer_hard_kill_beyond_the_wall_cap(pre):
    b = pre["budget"]
    assert "timeout --signal=KILL 1860" in b["invocation"]
    assert 1860 > b["wall_cap_minutes"] * 60 and "no workflow" in b["invocation"]


# --- the pre-declaration ----------------------------------------------------------------

def test_the_predeclaration_is_frozen_and_complete(pre):
    assert _sha(HERE / "predeclaration.json") == PREDECLARATION_SHA256
    for key in ("question", "hypotheses", "configuration", "measured_quantity",
                "relation_to_registered_E_C", "baseline", "controlled_variables",
                "not_a_target", "no_combination", "integrity", "outcomes", "budget",
                "stop_conditions", "expected_evidence", "cannot_establish"):
        assert key in pre, key
    assert pre["budget"]["attempts"] == 1 and "none" in pre["budget"]["retry"]
    assert "NOT EXECUTED" in pre["status"]
    assert "UNAVAILABLE" in pre["relation_to_registered_E_C"]["consequence"]
    assert "must NOT be taken from the conditional Route A coupling" in \
        pre["relation_to_registered_E_C"]["consequence"]
    assert "not a target" in pre["not_a_target"].lower()


def test_the_band_baseline_is_recomputed_from_committed_columns(sc, pre):
    assert sc.band_baseline(pre) == pytest.approx(
        pre["baseline"]["band_estimate_same_mesh"]["value_GHz2"], rel=1e-14)


@pytest.mark.parametrize("S0, S1, verdict", [
    (2.0, 2.2, "SUPPORTS"),            # r0 0.93, rho 1.10
    (1.2, 1.3, "SUPPORTS"),            # r0 0.56
    (4.2, 4.4, "SUPPORTS"),            # r0 1.95
    (8.0, 8.5, "WEAKENS"),             # r0 3.7
    (0.5, 0.55, "WEAKENS"),            # r0 0.23
    (60.0, 62.0, "CONTRADICTS"),       # r0 28, near the complete-moment scale
    (0.05, 0.051, "CONTRADICTS"),      # r0 0.023
    (2.0, 3.0, "UNRESOLVED"),          # rho 1.5
    (2.0, 3.9, "WEAKENS"),             # rho 1.95, as fast as the divergent moment
])
def test_the_decision_is_the_frozen_table(sc, pre, S0, S1, verdict):
    B0 = pre["baseline"]["band_estimate_same_mesh"]["value_GHz2"]
    assert sc.decide(S0, S1, B0, pre)["verdict"] == verdict


def test_integrity_failures_are_never_a_scientific_verdict(sc, pre):
    good = {"level": 0, "C_F": 1.0, "S_GHz2": 2.0, "solve_relative_residual": 1e-14,
            "identity": {"port_voltage_of_grad_phi": 1.0, "grad_phi_on_pec_edges_max_abs": 0.0,
                         "edge_energy_vs_p1_energy_rel": 1e-15, "S_two_routes_rel": 1e-15}}
    assert sc.integrity([good, {**good, "level": 1, "C_F": 0.99, "S_GHz2": 2.02}], pre) == []
    increased = {**good, "level": 1, "C_F": 1.01}
    assert any("Dirichlet" in m for m in sc.integrity([good, increased], pre))
    broken = {**good, "identity": {**good["identity"], "port_voltage_of_grad_phi": 0.9}}
    assert sc.integrity([broken], pre)
    too_big = {**good, "S_GHz2": 400.0}
    assert any("complete first moment" in m for m in sc.integrity([too_big], pre))


# --- the machinery, on known answers ----------------------------------------------------

def test_the_vectorised_assembly_reproduces_compiled_palace_on_the_fixture(af):
    sys.path.insert(0, str(FMD))
    import synthetic_fixture as sf
    z = dict(np.load(sf.FIXTURE_DIR / "fm_synthetic_arrays.npz"))
    mesh = {"xyz": z["xyz_mm"], "tets": z["tets"], "tet_attr": z["tet_attr"],
            "tris": z["tris"], "tri_attr": z["tri_attr"]}
    L_H = json.loads((sf.FIXTURE_DIR / "config-A-nominal.json").read_text())[
        "Boundaries"]["LumpedPort"][0]["L"]
    s = af.assemble_edge_system(mesh, eps_r=sf.EPS_R, pec_attrs=(sf.ATTR_PEC_X, sf.ATTR_PEC_Z),
                                port_attr=sf.ATTR_PORT, direction=sf.PORT_DIRECTION,
                                L0_m=sf.L0_M, L_H=L_H)
    x = spla.spsolve(s["M_free"].tocsc(), s["f_free"])
    A = float(s["f_free"] @ x) / s["scales"]["L_nd"]
    assert A == pytest.approx(64.16250164577238, rel=1e-13), "compiled Palace, committed"
    assert (len(s["edges"]), len(s["free"]), int(s["pec"].sum())) == (663, 534, 129)


def test_synthetic_known_answer_and_the_negative_control(sc):
    out = sc.synthetic_controls()
    slab = out["slab_exact"]
    for row in slab["rows"]:
        assert row["C_rel_error_vs_exact"] < 1e-12, "P1 is exact for a uniform field"
        idn = row["identity"]
        assert abs(idn["port_voltage_of_grad_phi"] - 1.0) < 1e-12
        assert idn["grad_phi_on_pec_edges_max_abs"] == 0.0
        assert idn["edge_energy_vs_p1_energy_rel"] < 1e-12
        assert idn["S_two_routes_rel"] < 1e-12
        assert row["S_GHz2"] <= row["A_complete_GHz2"], "a restricted maximum"
    # the mechanism on a geometry with a known answer: static fixed, complete growing
    assert slab["static_growth"] == pytest.approx(1.0, abs=1e-12)
    assert slab["complete_growth"] > 1.8
    fr = out["fringe_nested"]
    assert fr["C1_over_C0"] < 1.0, "nested refinement lowers the Dirichlet energy"
    for idn in fr["identities"]:
        assert abs(idn["port_voltage_of_grad_phi"] - 1.0) < 1e-12
        assert idn["S_two_routes_rel"] < 1e-12


# --- the preserved measurements ---------------------------------------------------------

def test_the_level0_lower_bound_reproduces_from_committed_inputs(measured):
    lb = _load("lower_bounds")
    row = lb.bounds(lb.af.read_gmsh22(lb.MESH))
    kept = measured["C_reproduced_by_this_record"]["lower_bounds"]["rows"][0]
    for key in ("n_edges", "n_free", "LB1_GHz2", "LB2_GHz2", "fT_Dinv_f"):
        assert row[key] == pytest.approx(kept[key], rel=1e-12), key


def test_the_lower_bounds_double_and_bound_the_measured_moments(measured):
    rows = measured["C_reproduced_by_this_record"]["lower_bounds"]["rows"]
    assert [r["level"] for r in rows] == [0, 1, 2]
    assert rows[1]["LB2_ratio_to_previous"] > 1.9 and rows[2]["LB2_ratio_to_previous"] > 1.9
    A0 = measured["D_earlier_analysis_not_rerun"]["complete_first_moment_base_mesh"]["A_GHz2"]
    assert rows[0]["LB2_GHz2"] <= A0, "a lower bound"
    A_N2R = measured["B_derived_from_committed"]["A_direct_N2R_GHz2"]["value"]
    assert rows[2]["LB2_GHz2"] <= A_N2R * 1.01


def test_the_preflight_found_the_test_well_defined_without_solving(measured):
    """Two conductors, the port bridging both, and the port-voltage integrity condition
    already exact for the island indicator - checked before approval, with no solve."""
    pf = measured["C_reproduced_by_this_record"]["conductors_and_problem_sizes"]
    assert [lv["level"] for lv in pf["levels"]] == [0, 1]
    for lv in pf["levels"]:
        assert lv["n_conductors"] == 2 and lv["port_touches"] == [True, True]
        assert lv["port_voltage_of_island_indicator"] == pytest.approx(1.0, abs=1e-12)
        assert lv["indicator_gradient_on_pec_edges_max_abs"] == 0.0
    assert pf["band_baseline_matches_predeclaration"] is True


def test_the_band_moments_match_the_committed_columns(measured):
    for name, b in measured["A_committed_palace"]["band_moments_by_rung"].items():
        for fname, digest in b["sha256"].items():
            hits = [p for p in (REPO / "results").glob(f"*/*/solver/postpro/{fname}")
                    if _sha(p) == digest]
            assert hits, (name, fname)
            rows = list(csv.reader(open(hits[0].parent / "eig.csv")))[1:]
            assert float(rows[0][1]) == pytest.approx(b["f1_GHz"], rel=1e-15)


# --- the boundaries of this record ------------------------------------------------------

def test_the_static_test_imports_nothing_from_route_a_or_the_coupling():
    allowed = {"__future__", "argparse", "csv", "json", "math", "sys", "datetime", "pathlib",
               "platform", "resource", "signal", "time", "traceback",
               "numpy", "scipy", "scipy.sparse", "scipy.sparse.linalg",
               "scipy.sparse.csgraph", "hashlib", "anchor_fem"}
    for name in ("static_capacitance.py", "anchor_fem.py", "lower_bounds.py"):
        tree = ast.parse((HERE / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module]
            else:
                continue
            for m in mods:
                assert m in allowed, (name, m)


def test_the_existing_method_is_unchanged_while_the_alternative_is_tested():
    for rel, digest in EXISTING_METHOD.items():
        assert _sha(REPO / rel) == digest, (
            f"{rel} changed. This record tests an ALTERNATIVE and must not alter the "
            "existing method; a change to it needs its own review, and then this pin.")


def test_every_new_source_file_carries_the_approved_header():
    header = "Copyright (c) 2026 Brodie Duncan. All rights reserved."
    for path in [*HERE.glob("*.py"), Path(__file__)]:
        assert header in path.read_text().splitlines()[1] or \
            header in path.read_text().splitlines()[0], path.name


def test_the_record_separates_measurement_proof_and_prediction():
    text = DOC.read_text()
    for heading in ("## 2. Measurements", "## 3. Mathematics", "## 4. Predictions",
                    "## 5. The prepared test"):
        assert heading in text, heading
    assert "PREPARED, NOT APPROVED, NOT EXECUTED" in text
