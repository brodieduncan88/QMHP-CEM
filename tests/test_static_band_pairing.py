# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""The paired static-vs-band refinement test: PREPARED, NOT APPROVED, NOT EXECUTED.

Covers the three verifications that justify it (the monotonicity/bound claim on the
actual implementation, the spectral identities, the L2 same-mesh check), the driver's
refinement-nesting check and MFEM reader, the frozen decision and integrity rules, the
gate and one-attempt refusal, an end-to-end synthetic execution with a mock Palace that
proves the driver writes a manifest that verifies (on success AND on failure), the
dispatch-only workflow, and that no QMHP solve is run and the existing method is
unchanged."""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
HERE = REPO / "experiments" / "static-band-pairing"
WORKFLOW = REPO / ".github" / "workflows" / "static-band-pairing.yml"
DOC = REPO / "docs" / "coupled-candidate" / "static-band-pairing.md"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))
import pairing_driver as pd  # noqa: E402
import spectral as spc  # noqa: E402
import verify_nesting as vn  # noqa: E402
from orchestrator import manifest  # noqa: E402

af = pd.af
REAL_MESH = REPO / "results/COUPLED-LADDER-O1-L2-20260916T080802Z/L2/solver/coupled_chip_cell_L2.msh"

#: frozen before any refined QMHP mesh or value existed; a change needs a new pre-declaration
PREDECLARATION_SHA256 = "3f588d2e6bca206aa509d7a40585b2c5421f94944a2c2938b262b2e7c4ce80d5"

#: the executed static-anchor record and the method this test must not change
UNCHANGED = {
    "experiments/static-anchor-hypothesis/static_capacitance.py": "54dd810f93f8d7af967cdfffb9fac78d0a583c8003c104e0c00002e2b8e98aab",
    "experiments/static-anchor-hypothesis/anchor_fem.py": "1123e38f16b6c443fd397330db568e8c5d4e18fa9a7c4dc844c599204e6437c1",
    "experiments/static-anchor-hypothesis/predeclaration.json": "6f31470a38a58cfbe33eb7bee61c6ec06eeea428bdfbd943b39e52e3e4868f29",
    "results/STATIC-ANCHOR-TEST-20260922T192243Z/summary.json": "93db9bc22003c137adfeb8399445a9f6958e4ea4bd6c882b46262338167381d6",
    "models/route_a_inversion.py": "4dcf9ef584f2a1e99828bde1ee8bab179178c1b0539bfb63cba60974ebbbac03",
    "models/coupling_extraction.py": "2f7b845e08659e691cb2028c8a9ba1582b748281ee0939e7b3d6bd63b61668f8",
    "docs/coupled-candidate/coupling-definition.md": "143091c596b41c46baeed372ba6afdd6eb524c3c9d87e8af57bb9de19cc6b5d1",
    "scripts/palace_order1_ladder.py": "51dfe5030c85b7e21d3f4f7c4da38f26d49f902cc041bc2a4ae5cb95584a9947",
    "docker/palace.Dockerfile": "ae61175a4237cfed043d0df47126080215fa06c42acd897a53107b2c99fc88a9",
}


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def pre():
    return json.loads((HERE / "predeclaration.json").read_text())


@pytest.fixture(scope="module")
def sc():
    return pd._static_module()


# --- item 1: monotonicity and the bound, on the actual implementation -------------------

def test_the_real_mesh_is_conforming_and_its_red_refinement_is_verified_nested():
    m = af.read_gmsh22(REAL_MESH)
    c = vn.conformity(m)
    assert c["max_face_multiplicity"] == 2 and c["coincident_nodes"] == 0
    assert c["every_tagged_triangle_is_a_tet_face"] and c["nodes_in_no_tet"] == 0
    assert vn.conductor_consistency(m)["every_conductor_triangle_in_one_conductor"]
    n = vn.nesting(m, af.refine_red(m))
    assert n["coarse_nodes_unchanged"] and n["midpoints_exact_rel"] == 0.0
    assert n["children_volume_sum_rel_err"] < 1e-13
    assert n["galerkin_identity_rel"] < 1e-13            # P^T K1 P = K0: the nesting proof
    assert n["constraint_sets_nested"] and n["coarse_conductor_nodes_kept"]
    assert n["fine"]["max_face_multiplicity"] == 2 and n["prolonged_indicator_admissible"]


def test_each_condition_of_the_monotonicity_proof_is_necessary():
    s = vn.synthetic_controls()
    assert s["nested_refinement_C1_over_C0"] <= 1.0
    assert s["galerkin_identity_rel_nested"] < 1e-13
    assert s["non_nested_space_orientation_preserved"]
    assert s["galerkin_identity_rel_non_nested"] > 0.1    # the verifier detects non-nesting
    assert s["non_nested_constraints_C1_over_C0"] > 1.0   # without constraint nesting, C rises


def test_the_committed_item1_evidence_matches(pre):
    ev = json.loads((HERE / "nesting_verification.json").read_text())
    assert ev["real_mesh"]["mesh_sha256"] == pre["configuration"]["base_mesh_sha256"]
    assert ev["real_mesh"]["solves_performed"] == 0
    assert ev["real_mesh"]["level0_to_1"]["galerkin_identity_rel"] < 1e-13


# --- item 2: the spectral identities -----------------------------------------------------

def test_known_answer_the_static_quantity_is_the_exact_harmonic_moment_of_the_lumped_pencil():
    import identities
    r = identities.synthetic(3)
    assert abs(r["port_voltage"] - 1.0) < 1e-12 and r["curl_grad_rel"] < 1e-13
    lu = r["lumped"]
    assert abs(lu["N"] - 1) < 1e-9
    assert abs(lu["inv_moment_times_V2_over_L_C_minus_1"]) < 1e-9     # sum p/lambda = L C_h
    assert abs(lu["parseval_rel"]) < 1e-12
    assert lu["min_over_k_B_k_over_N_k_S"] >= 1.0 - 1e-12              # S <= B_k/N_k, every k
    sh = r["sheet"]
    assert abs(sh["parseval_rel"]) < 1e-12                             # the +1 moment is K-free
    assert sh["inv_moment_times_V2_over_L_C_minus_1"] > 0.01           # the sheet perturbs the -1 moment
    assert sh["min_over_k_B_k_over_N_k_S"] < 1.0                       # and can break S <= B/N
    assert r["sheet_minus_lumped_port_psd_min_eig"] > -1e-12           # K_port >= f f^T / L


def test_a_malformed_port_scales_the_identity_by_one_over_V_squared():
    import identities
    r = identities.synthetic(2)
    assert abs(r["port_voltage"] - 0.5) < 1e-12
    assert abs(r["lumped"]["inv_moment_times_V2_over_L_C_minus_1"]) < 1e-9


def test_on_the_committed_L2_mesh_palaces_band_exceeds_the_lumped_identity():
    ev = json.loads((HERE / "identities.json").read_text())
    chk = ev["L2_same_mesh_check"]
    assert chk["S0_static_GHz2"] == 2.1413534596006496
    assert 6e-4 < chk["delta_band_lower_bound"] < 7e-4                 # the sheet port, measured
    assert chk["B0_over_N_B_over_S0"] > 1.0                            # S0 <= B0/N_B still holds here
    rungs = ev["committed_rungs"]
    assert all(0.99 < r["H_over_B"] < 0.997 for r in rungs.values())   # the ratio is not 1
    assert ev["solves_on_qmhp_mesh"] == 0


# --- the driver's refinement check and mesh reader --------------------------------------

def test_mfem_round_trip_and_nesting_through_a_renumbering(sc):
    mesh, model = sc._slab(4, island_patch=True)
    fine = af.refine_red(mesh)
    perm = np.random.default_rng(3).permutation(len(fine["xyz"]))
    inv = np.argsort(perm)
    shuf = dict(fine, xyz=fine["xyz"][perm], tets=inv[fine["tets"]], tris=inv[fine["tris"]])
    import tempfile
    path = Path(tempfile.mkdtemp()) / "m.mesh"
    pd.write_mfem_mesh(shuf, path)
    back = pd.read_mfem_mesh(path)
    assert np.array_equal(back["xyz"], shuf["xyz"]) and np.array_equal(back["tets"], shuf["tets"])
    n = pd.nesting(mesh, back, model["eps_r"], model["pec_attrs"])
    assert n["nested"] and n["galerkin_identity_rel"] < 1e-13


def test_the_nesting_check_refuses_moved_vertices_and_grown_conductors(sc):
    mesh, model = sc._slab(4, island_patch=True)
    fine = af.refine_red(mesh)
    x = fine["xyz"].copy()
    x[len(mesh["xyz"]):, 0] += 1e-4
    assert not pd.nesting(mesh, dict(fine, xyz=x), model["eps_r"], model["pec_attrs"])["nested"]
    xyz, tris = fine["xyz"], fine["tris"]
    isl = fine["tri_attr"] == 4
    top = np.all(np.isclose(xyz[tris][:, :, 2], 1.0), axis=1)
    ring = top & ~isl & np.isin(tris, np.unique(tris[isl])).any(1)
    attr = fine["tri_attr"].copy(); attr[ring] = 4
    n = pd.nesting(mesh, dict(fine, tri_attr=attr), model["eps_r"], model["pec_attrs"])
    assert not n["constraint_sets_nested"] and not n["nested"]


@pytest.mark.parametrize("text", ["MFEM mesh v1.0\ndimension\n3\nvertices\n1\n\nnodes\nFiniteElementSpace\n",
                                  "MFEM NC mesh v1.0\n", "not a mesh\n"])
def test_the_mfem_reader_refuses_what_it_cannot_read(text, tmp_path):
    p = tmp_path / "x.mesh"
    p.write_text(text)
    with pytest.raises(ValueError):
        pd.read_mfem_mesh(p)


# --- the frozen decision and integrity ----------------------------------------------------

def _lv(S, B, H):
    return {"S_GHz2": S, "B_GHz2": B, "H_GHz2": H}


@pytest.mark.parametrize("levels, verdict", [
    ([_lv(2.14, 2.148, 2.140), _lv(2.60, 2.61, 2.598), _lv(2.90, 2.912, 2.897)], "SUPPORTS"),
    ([_lv(2.14, 2.148, 2.140), _lv(2.15, 2.16, 2.148), _lv(2.16, 2.17, 2.158)], "UNRESOLVED"),   # low power
    ([_lv(2.14, 2.148, 2.140), _lv(2.60, 2.30, 2.29), _lv(2.90, 2.40, 2.39)], "CONTRADICTS"),    # decouples
    ([_lv(2.14, 2.148, 2.140), _lv(2.60, 2.61, 2.56), _lv(2.90, 2.912, 2.85)], "UNRESOLVED"),   # delta 1.8 %
    ([_lv(2.14, 2.148, 2.140), _lv(2.60, 2.61, 2.598), _lv(2.90, 2.912, 2.78)], "CONTRADICTS"),  # delta 4.3 %
])
def test_the_decision_is_the_frozen_table(pre, levels, verdict):
    assert pd.decide(levels, pre)["verdict"] == verdict


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0.0, -1.0, None, "2.1", True])
def test_an_invalid_decisive_value_is_unqualified(pre, bad):
    levels = [_lv(2.14, 2.148, 2.140), _lv(2.60, 2.61, 2.598), _lv(2.90, 2.912, 2.897)]
    levels[1]["S_GHz2"] = bad
    assert pd.decide(levels, pre)["verdict"] == "UNQUALIFIED"
    assert pd.decide(levels[:2], pre)["verdict"] == "UNQUALIFIED"


# --- gate and one attempt -----------------------------------------------------------------

def test_no_approval_is_committed_and_the_driver_refuses_before_any_solve(tmp_path, monkeypatch):
    assert not pd.APPROVAL.exists(), "prepared, not approved"
    calls = []
    monkeypatch.setattr(pd, "RESULTS_ROOT", tmp_path / "results")
    with pytest.raises(pd.Refusal, match="PREPARED, NOT APPROVED"):
        pd.execute(runtime="docker", image="x", scratch=tmp_path / "s", env={},
                   run_palace=lambda *a, **k: calls.append(1))
    assert not calls and not (tmp_path / "results").exists()


def test_a_wrong_run_number_or_a_rerun_attempt_is_refused(tmp_path, monkeypatch, pre):
    good = json.loads((HERE / "PAIRING-APPROVAL.draft.json").read_text())
    good = {k: v for k, v in good.items() if k not in ("DRAFT", "how_to_grant_it")}
    ap = tmp_path / "PAIRING-APPROVAL.json"
    ap.write_text(json.dumps(good))
    monkeypatch.setattr(pd, "APPROVAL", ap)
    assert pd.require_approval(pre, {"GITHUB_RUN_NUMBER": "1", "GITHUB_RUN_ATTEMPT": "1"})
    for env in ({"GITHUB_RUN_NUMBER": "2", "GITHUB_RUN_ATTEMPT": "1"},
                {"GITHUB_RUN_NUMBER": "1", "GITHUB_RUN_ATTEMPT": "2"}, {}):
        with pytest.raises(pd.Refusal, match="approved workflow run number"):
            pd.require_approval(pre, env)
    stale = dict(good, code_sha256={k: "0" * 64 for k in good["code_sha256"]})
    ap.write_text(json.dumps(stale))
    with pytest.raises(pd.Refusal, match="code_sha256 does not match"):
        pd.require_approval(pre, {"GITHUB_RUN_NUMBER": "1", "GITHUB_RUN_ATTEMPT": "1"})


def test_the_draft_approval_binds_the_current_files_and_run_number_one(pre):
    d = json.loads((HERE / "PAIRING-APPROVAL.draft.json").read_text())
    assert "NOT AN APPROVAL" in d["DRAFT"]
    assert d["predeclaration_sha256"] == PREDECLARATION_SHA256
    assert d["code_sha256"] == {p: _sha(REPO / p) for p in pd.CODE_FILES}, "re-review the draft"
    assert d["github_run_number"] == 1
    assert d["base_mesh_sha256"] == pre["configuration"]["base_mesh_sha256"]


# --- end to end, synthetic, with a mock Palace: the manifest proof -------------------------

def _write_gmsh22(mesh: dict, path: Path) -> None:
    L = ["$MeshFormat", "2.2 0 8", "$EndMeshFormat", "$Nodes", str(len(mesh["xyz"]))]
    L += [f"{i + 1} {x:.17g} {y:.17g} {z:.17g}" for i, (x, y, z) in enumerate(mesh["xyz"])]
    L += ["$EndNodes", "$Elements", str(len(mesh["tris"]) + len(mesh["tets"]))]
    k = 1
    for a, t in zip(mesh["tri_attr"], mesh["tris"]):
        L.append(f"{k} 2 2 {a} {a} {t[0] + 1} {t[1] + 1} {t[2] + 1}"); k += 1
    for a, t in zip(mesh["tet_attr"], mesh["tets"]):
        L.append(f"{k} 4 2 {a} {a} {t[0] + 1} {t[1] + 1} {t[2] + 1} {t[3] + 1}"); k += 1
    L += ["$EndElements"]
    path.write_text("\n".join(L) + "\n")


def _synthetic_world(tmp_path, monkeypatch, pre, sc, delta: float, fail_at: int | None = None):
    """Point the driver at a synthetic slab and a mock Palace whose band obeys the identity
    with a chosen perturbation delta. Nothing here touches the QMHP mesh."""
    base, model = sc._slab(3, island_patch=True)
    solver = tmp_path / "base"; solver.mkdir()
    _write_gmsh22(base, solver / pd.MESH_NAME)
    (solver / "config.json").write_text(pd.BASE_CONFIG.read_text())
    monkeypatch.setattr(pd, "BASE_MESH", solver / pd.MESH_NAME)
    monkeypatch.setattr(pd, "RESULTS_ROOT", tmp_path / "results")
    monkeypatch.setattr(pd, "require_approval", lambda p, e: {"github_run_number": 1})
    monkeypatch.setattr(pd, "_inputs_ok", lambda p: None)
    monkeypatch.setattr(pd, "APPROVAL", tmp_path / "approval.json")
    (tmp_path / "approval.json").write_text("{}")
    p2 = json.loads(json.dumps(pre))
    p2["configuration"]["static_model"] = {"eps_r": {"1": 2.0, "3": 5.0}, "pec_attrs": [2, 4],
                                           "port_attr": 10, "direction": [0.0, 0.0, 1.0],
                                           "L0_m": 1e-3, "L_H": 1e-8}
    s0 = sc.static_capacitance(base, **model)
    p2["integrity"]["level0_static_reproduces_GHz2"] = s0["S_GHz2"]
    # this exercises the driver's plumbing and evidence path, not the power condition on
    # a coarse synthetic slab; the frozen table itself is tested on its own above
    p2["outcomes"]["power_min_static_growth"] = 1.0
    monkeypatch.setattr(pd, "load_pre", lambda: p2)
    meshes = {0: base, 1: af.refine_red(base)}
    meshes[2] = af.refine_red(meshes[1])
    p1, p2w, ratio = 0.999, 0.001, 10.0

    def mock_palace(runtime, image, work, np_, name, *, dof_budget):
        lvl = int(name[-1])
        if fail_at == lvl:
            raise RuntimeError("synthetic Palace failure")
        post = work / "postpro"; post.mkdir()
        mesh = meshes[lvl]
        if lvl:
            pd.write_mfem_mesh(mesh, post / pd.SAVED_MESH_NAME)
        S = sc.static_capacitance(mesh, **model)["S_GHz2"]
        f1sq = p1 / ((1 + delta) / S - p2w / (ratio * S))
        f = [f1sq ** 0.5, (ratio * S) ** 0.5] + [(40 * S) ** 0.5 + i for i in range(4)]
        p = [p1, p2w] + [1e-9] * 4
        if lvl == 0:
            p2["integrity"]["level0_band_f1_reproduces_GHz"] = f[0]
        with open(post / "eig.csv", "w") as fh:
            fh.write("m, Re{f}, Im{f}, Q, Bkwd, Abs\n")
            for i, fi in enumerate(f):
                fh.write(f"{i + 1}, {fi:.12e}, 0.0, 1e12, 1e-15, 1e-12\n")
        with open(post / "port-EPR.csv", "w") as fh:
            fh.write("m, p[1]\n")
            for i, pi in enumerate(p):
                fh.write(f"{i + 1}, {-pi:.12e}\n")
        (work / "palace_log.txt").write_text("synthetic\n")
        return {"command": ["mock"], "returncode": 0, "timed_out": False,
                "dof_probe": {"dof_reported": 1000 * (lvl + 1), "refused": False}}
    return mock_palace


@pytest.mark.parametrize("delta, verdict", [(0.002, "SUPPORTS"), (0.05, "CONTRADICTS")])
def test_end_to_end_the_driver_decides_and_writes_a_manifest_that_verifies(
        tmp_path, monkeypatch, pre, sc, delta, verdict):
    mock = _synthetic_world(tmp_path, monkeypatch, pre, sc, delta)
    rec = pd.execute(runtime="docker", image="x", scratch=tmp_path / "scratch", env={}, run_palace=mock)
    names = sorted(p.relative_to(rec).as_posix() for p in rec.rglob("*") if p.is_file())
    for lvl in (0, 1, 2):
        for f in ("config.json", "palace_run.json", "palace/eig.csv", "palace/port-EPR.csv",
                  "palace/palace_log.txt", "mesh.json", "static.json", "band.json"):
            assert f"level{lvl}/{f}" in names, (lvl, f)
    assert "level1/nesting.json" in names and "level2/nesting.json" in names
    assert "manifest.sha256" in names and "summary.json" in names
    assert not any(n.endswith(".mesh") for n in names), "refined meshes are never in the record"
    assert manifest.verify(rec) == []                          # item 4: written, and it verifies
    s = json.loads((rec / "summary.json").read_text())
    assert s["integrity_failures"] == [] and s["outcome"]["verdict"] == verdict
    assert abs(s["outcome"]["delta"][1] - delta) < 1e-6
    with pytest.raises(pd.Refusal, match="the one attempt is spent"):
        pd.execute(runtime="docker", image="x", scratch=tmp_path / "s2", env={}, run_palace=mock)


def test_a_failure_mid_attempt_still_leaves_a_verified_manifest(tmp_path, monkeypatch, pre, sc):
    mock = _synthetic_world(tmp_path, monkeypatch, pre, sc, 0.002, fail_at=1)
    with pytest.raises(RuntimeError, match="synthetic Palace failure"):
        pd.execute(runtime="docker", image="x", scratch=tmp_path / "scratch", env={}, run_palace=mock)
    (rec,) = (tmp_path / "results").glob(pd.RECORD_PREFIX + "*")
    assert (rec / "failure.json").is_file() and (rec / "level0" / "static.json").is_file()
    assert json.loads((rec / "failure.json").read_text())["levels_completed"] == [0]
    assert manifest.verify(rec) == []
    assert manifest.verify(rec) == [] and (rec / "manifest.sha256").read_text().count("level0/") >= 5


# --- configuration, workflow and boundaries ------------------------------------------------

def test_the_predeclaration_is_frozen_and_the_configs_are_exactly_the_declared_deltas(pre):
    assert _sha(HERE / "predeclaration.json") == PREDECLARATION_SHA256
    assert "NOT EXECUTED" in pre["status"]
    base = json.loads(pd.BASE_CONFIG.read_text())
    for lvl in (0, 1, 2):
        cfg = pd.level_config(lvl, pre)
        assert pd.canonical_sha(cfg) == pre["configuration"]["config_sha256"][str(lvl)]
        assert cfg["Solver"]["Eigenmode"] == dict(base["Solver"]["Eigenmode"], Save=0)
        assert cfg["Solver"]["Linear"] == dict(base["Solver"]["Linear"], MGMaxLevels=1)
        assert cfg["Boundaries"] == base["Boundaries"] and cfg["Domains"] == base["Domains"]
        ref = cfg["Model"]["Refinement"]
        if lvl == 0:
            assert ref == base["Model"]["Refinement"]
        else:
            assert ref["SaveAdaptMesh"] is True and ref["Boxes"][0]["Levels"] == lvl
    for key in ("question", "theory", "configuration", "measured", "integrity", "outcomes",
                "feasibility", "budget", "stop_conditions", "expected_evidence", "cannot_establish"):
        assert key in pre, key


def test_the_workflow_is_dispatch_only_confirmed_and_commits_only_the_verified_record():
    text = WORKFLOW.read_text()
    data = yaml.safe_load(text)
    on = data.get("on", data.get(True))
    assert list(on) == ["workflow_dispatch"]
    steps = data["jobs"]["pairing"]["steps"]
    runs = [s.get("run", "") for s in steps]
    assert not any("${{" in r for r in runs), "no expression expansion inside run scripts"
    assert "run-the-approved-pairing-attempt" in text
    names = [s.get("name", "") for s in steps]
    i_attempt = names.index("THE ONE APPROVED ATTEMPT")
    i_verify = names.index("Verify the record manifest")
    i_kinds = names.index("Refuse unexpected file kinds in the evidence commit")
    i_commit = names.index("Commit the record to the branch")
    assert i_attempt < i_verify < i_kinds < i_commit
    assert "cem verify-results" in steps[i_verify]["run"]
    assert 'git add "$RECORD"' in steps[i_commit]["run"]
    assert "--execute" in steps[i_attempt]["run"]


def test_the_existing_method_and_the_executed_record_are_unchanged():
    for rel, digest in UNCHANGED.items():
        assert _sha(REPO / rel) == digest, rel


def test_the_driver_is_not_itself_launch_capable_and_imports_nothing_from_route_a():
    for name in ("pairing_driver.py", "spectral.py", "verify_nesting.py", "identities.py"):
        tree = ast.parse((HERE / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert not ast.unparse(node.func).startswith(("subprocess.", "os.system", "os.popen")), name
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                assert not any("route_a" in m or "coupling" in m for m in mods), (name, mods)


def test_every_new_source_file_carries_the_approved_header():
    for p in list(HERE.glob("*.py")) + [Path(__file__)]:
        head = p.read_text().splitlines()[:3]
        assert any("Copyright (c) 2026 Brodie Duncan. All rights reserved." in h for h in head), p


def test_the_report_keeps_proof_measurement_and_prediction_apart():
    text = DOC.read_text()
    for h in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6."):
        assert h in text, h
    assert "PREPARED, NOT APPROVED, NOT EXECUTED" in text
    assert "UNRESOLVED" in text and "UNAVAILABLE" in text
