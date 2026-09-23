# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""The static-only nested refinement study: PREPARED, NOT APPROVED, NOT EXECUTED.

Tested here on synthetic data only: no test solves anything on the QMHP mesh.

- the solver and its certificate against known answers and negative controls;
- the frozen classification and consistency rules;
- every integrity failure reaching UNQUALIFIED rather than a class;
- the approval gate, the invocation check and the one-attempt ledger (including a real
  checkout-like removal of the tracked entries);
- per-solve atomic raw writes and write_verified on success and failure paths, including
  stop signals delivered twice to a real process group under `timeout`;
- the budget binding a real process;
- the committed verification, preflight and dry-run evidence;
- the pre-declaration's agreement with the code;
- that the withdrawn paired test, the executed static-anchor record and the existing
  method are unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
HERE = REPO / "experiments" / "static-refinement-study"
DOC = REPO / "docs" / "coupled-candidate" / "static-refinement-study.md"
sys.path.insert(0, str(HERE))

import nested_solver as ns  # noqa: E402
import study_driver as sd  # noqa: E402
import synthetic_cells as syn  # noqa: E402

af = ns.af
manifest = sd.manifest

#: frozen before any level-2, C' or delta value existed on the QMHP mesh; changing it
#: needs a new pre-declaration revision, not an edit
PREDECLARATION_SHA256 = "29276d45f333be5a7e64678023b5f4e87cb8d24b411bc7bd34e70b389e9e54a5"

#: the withdrawn paired test and its report, preserved unchanged
WITHDRAWN_UNCHANGED = {
    "experiments/static-band-pairing/WITHDRAWN.json": "252684629f62f34afd773971e8acb1af5c64ab660102df412ead521366d64c81",
    "experiments/static-band-pairing/identities.json": "a8b5dfc056c01e1c3564349e0a40e352f265c553625d61dac7f7604334406eda",
    "experiments/static-band-pairing/nesting_verification.json": "aa9b8cea84bf510e3914af856569d5bf583be806d137fd6786a2c13787af6c21",
    "experiments/static-band-pairing/predeclaration.json": "3f588d2e6bca206aa509d7a40585b2c5421f94944a2c2938b262b2e7c4ce80d5",
    "experiments/static-band-pairing/identities.py": "0021d587cfaad9cc21cfe9af23641430c8cb7435a2319c73a071258040770c23",
    "experiments/static-band-pairing/pairing_driver.py": "6b77f9b4c2989466b8fdef5d81a36c995e58f54b2ae7955d857f4e7e5c14a6a0",
    "experiments/static-band-pairing/spectral.py": "e9361732bd2a64d7e667ba58f729aefa7650ff5d3bc30a3dd6093b6a8c5e48d1",
    "experiments/static-band-pairing/verify_nesting.py": "88a77eb35092af3dcd7bbea277cbebe81ddb0a299d08f74d8e5cbc777583bbfa",
    "experiments/static-band-pairing/review/red_team_findings.json": "171c3b4996ed1213f9cab9283e251f5912921f188b7d59d07c4ebbbb60b6221d",
    "docs/coupled-candidate/static-band-pairing.md": "5d151fd07c69eee14b0eb51be98b45ba4e520a2e8c3dfea0bc42bf3251576de9",
}
#: the executed static-anchor test and the code it ran, unchanged (this study reuses both)
ANCHOR_UNCHANGED = {
    "experiments/static-anchor-hypothesis/anchor_fem.py": "1123e38f16b6c443fd397330db568e8c5d4e18fa9a7c4dc844c599204e6437c1",
    "experiments/static-anchor-hypothesis/static_capacitance.py": "54dd810f93f8d7af967cdfffb9fac78d0a583c8003c104e0c00002e2b8e98aab",
    "experiments/static-anchor-hypothesis/predeclaration.json": "6f31470a38a58cfbe33eb7bee61c6ec06eeea428bdfbd943b39e52e3e4868f29",
    "experiments/static-anchor-hypothesis/TEST-APPROVAL.json": "b6bacb308c4912718be379d2f159d186f271ee9186ac440fa28a6764bb2d39a4",
    "results/STATIC-ANCHOR-TEST-20260922T192243Z/level0.json": "55f1f657dfb5cc476845b1cd4e283e4786206881db5b7d3860ae8e0714a0d3b9",
    "results/STATIC-ANCHOR-TEST-20260922T192243Z/level1.json": "0fc3e70a569734ae71dec6967aa98f37515f469dd567e4acb35c2321d84e7ec6",
    "results/STATIC-ANCHOR-TEST-20260922T192243Z/summary.json": "93db9bc22003c137adfeb8399445a9f6958e4ea4bd6c882b46262338167381d6",
    "models/route_a_inversion.py": "4dcf9ef584f2a1e99828bde1ee8bab179178c1b0539bfb63cba60974ebbbac03",
    "models/coupling_extraction.py": "2f7b845e08659e691cb2028c8a9ba1582b748281ee0939e7b3d6bd63b61668f8",
    "docs/coupled-candidate/coupling-definition.md": "143091c596b41c46baeed372ba6afdd6eb524c3c9d87e8af57bb9de19cc6b5d1",
}
SMALL = {"h0": 0.1, "q": 3.0, "hmax": 1.0, "split_port": True}
THREADS = {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _strict_json(path: Path):
    def bad(token):
        raise ValueError(f"non-standard JSON token {token} in {path.name}")
    return json.loads(path.read_text(), parse_constant=bad)


@pytest.fixture(scope="module")
def pre():
    return json.loads((HERE / "predeclaration.json").read_text())


@pytest.fixture(scope="module")
def small_ladder():
    """The small QMHP-like cell at levels 0 and 1, with direct solutions."""
    mesh, model = syn.chip_cell(**SMALL)
    lv = [ns.Level(mesh, model), ns.Level(af.refine_red(mesh), model)]
    sol = {(h, k): ns.solve(lv[h], k, "direct") for h in (0, 1) for k in ns.KINDS}
    return lv, sol


# --- the solver and its certificate ------------------------------------------------------

def test_exact_known_answer_direct_and_two_grid_from_zero():
    mesh, model, profile, E_exact = syn.layered_box(4)
    L0 = ns.Level(mesh, model, kinds=())
    L0.dd["x"] = syn.exact_dirichlet(mesh, profile)
    r0, p0 = ns.solve(L0, "x", "direct")
    fine = af.refine_red(mesh)
    L1 = ns.Level(fine, model, kinds=())
    L1.dd["x"] = syn.exact_dirichlet(fine, profile)
    assert ns.certificate_preconditions(L1, ns.boundary_facts(fine, L1.xyz)) == []
    rt, _ = ns.solve(L1, "x", "twogrid", coarse=L0, coarse_phi=np.zeros_like(p0))
    assert rt["solver"]["status"] == "CERTIFIED" and rt["solver"]["iterations"] > 0
    for r in (r0, rt):
        assert abs(r["energy_nd"] - E_exact) / E_exact < 1e-12


def test_the_certificate_holds_against_the_exact_rational_discrete_minimum():
    import verify_solver as vs
    for name, row in vs.v1b_certificate_against_exact_discrete_minimum().items():
        assert row["preconditions_failed"] == [], name
        assert row["within_certificate"] and row["at_or_above_minimum_up_to_evaluation"], (name, row)


def test_the_evaluation_bound_holds_against_exact_rational_arithmetic():
    import verify_solver as vs
    for name, row in vs.v6_evaluation_bound().items():
        assert row["bound_covers_error"], (name, row)
        assert row["evaluation_bound_nd"] <= row["previous_worst_case_bound_nd"], name


def test_two_grid_equals_direct_within_the_certificates(small_ladder):
    lv, sol = small_ladder
    for kind in ns.KINDS:
        rt, _ = ns.solve(lv[1], kind, "twogrid", coarse=lv[0], coarse_phi=sol[(0, kind)][1])
        rd = sol[(1, kind)][0]
        assert rt["solver"]["status"] == "CERTIFIED"
        assert rt["solver"]["galerkin_identity_rel"] < 1e-13
        assert rt["solver"]["fixed_rows_from_free_coarse_nnz"] == 0
        assert rt["solver"]["gauss_seidel_probe_rel"] < ns.GS_PROBE_TOL
        assert rt["solver"]["gauss_seidel_probe_backward_rel"] < ns.GS_PROBE_TOL
        assert rt["total_error_bound_rel"] < 1e-9 and rd["total_error_bound_rel"] < 1e-9
        assert abs(rt["energy_nd"] - rd["energy_nd"]) <= rt["total_error_bound_nd"] + rd["total_error_bound_nd"]
        assert abs(rt["port_voltage"] - 1) < 1e-9
        h = rt["solver"]["history"]
        assert all(set(e) == {"k", "recursive_residual", "true_residual", "rel_certificate", "wall_s"} for e in h)


def test_the_certificate_bounds_a_truncated_iterate_and_fails_it(small_ladder):
    lv, sol = small_ladder
    rt, _ = ns.solve(lv[1], "C", "twogrid", coarse=lv[0], coarse_phi=sol[(0, "C")][1],
                     settings={"maxiter": 2, "check_every": 1})
    rd = sol[(1, "C")][0]
    assert rt["solver"]["status"] == "MAXITER"
    assert not rt["total_error_bound_rel"] <= 1e-9
    assert rt["energy_nd"] >= rd["energy_nd"] - rd["total_error_bound_nd"]      # only raised
    assert rt["energy_nd"] - rd["energy_nd"] <= rt["total_error_bound_nd"] + rd["total_error_bound_nd"]


def test_the_asymmetry_of_the_assembled_matrix_enters_the_certificate(small_ladder):
    lv, sol = small_ladder
    dd = lv[1].dd["C"]
    sysm = ns.system(lv[1].K, dd)
    assert sysm["A_asym_abs"].nnz > 0                     # the assembled K is not exactly symmetric
    x = sol[(1, "C")][1][dd["free"]]
    ce = ns.certificate(sysm, x, lv[1].m[dd["free"]], lv[1].poincare["c"])
    sysm0 = dict(sysm, A_asym_abs=sysm["A_asym_abs"] * 0, D_asym_abs=sysm["D_asym_abs"] * 0)
    ce0 = ns.certificate(sysm0, x, lv[1].m[dd["free"]], lv[1].poincare["c"])
    assert ce["asymmetry_max"] > 0 and ce["error_bound_nd"] > ce0["error_bound_nd"]


def _bar():
    bar = syn.tensor_mesh(np.linspace(0, 1, 11), np.linspace(0, 0.1, 3), np.linspace(0, 0.1, 3))
    mesh = {"xyz": bar["xyz"], "tets": bar["tets"], "tet_attr": bar["tet_attr"],
            "tris": bar["faces"][bar["boundary"]], "tri_attr": np.full(int(bar["boundary"].sum()), 2)}
    model = {"eps_r": {1: 1.0}, "pec_attrs": (2,), "port_attr": 10, "direction": (1.0, 0.0, 0.0),
             "L0_m": 1.0e-3, "L_H": 1.0e-8}
    return mesh, model


def _understates(L, key) -> bool:
    import scipy.linalg as sla
    f = L.dd[key]["free"]
    A = L.K[f][:, f].toarray()
    _, vec = sla.eigh(A, np.diag(L.m[f]), subset_by_index=[0, 0])
    sysm = ns.system(L.K, L.dd[key])
    xs = ns.solve_direct(sysm)
    phi = L.dd[key]["phi"].copy()
    phi[f] = xs
    E0 = float(phi @ (L.K @ phi))
    phi[f] = xs + 1e-3 * vec[:, 0] / np.abs(vec[:, 0]).max()
    excess = float(phi @ (L.K @ phi)) - E0
    return ns.certificate(sysm, phi[f], L.m[f], L.poincare["c"])["error_bound_nd"] < excess


def test_the_constrained_boundary_precondition_is_necessary():
    """A bar held only at its ends: the check reports it, and the bound formula would
    understate a real error there - so the check is what makes the bound rigorous."""
    mesh, model = _bar()
    L = ns.Level(mesh, model, kinds=())
    x = mesh["xyz"][:, 0]
    fixed = (x < 1e-12) | (x > 1 - 1e-12)
    L.dd["ends"] = {"fixed": fixed, "phi": np.where(x > 0.5, 1.0, 0.0) * fixed,
                    "free": np.flatnonzero(~fixed), "geo": None}
    assert ns.certificate_preconditions(L, ns.boundary_facts(mesh, L.xyz)) == [
        "ends: an outer-boundary node is not constrained"]
    assert _understates(L, "ends")


def test_the_tiling_precondition_is_necessary_a_folded_mesh():
    mesh, model = syn.folded_box(3.0, 6)
    L = ns.Level(mesh, model, kinds=())
    bf = ns.boundary_facts(mesh, L.xyz)
    assert bf["max_face_multiplicity"] == 2 and bf["every_boundary_face_is_tagged"]
    fixed = np.zeros(len(mesh["xyz"]), dtype=bool)
    fixed[bf["boundary_nodes"]] = True
    L.dd["walls"] = {"fixed": fixed, "phi": np.where(fixed, mesh["xyz"][:, 0], 0.0),
                     "free": np.flatnonzero(~fixed), "geo": None}
    problems = ns.certificate_preconditions(L, bf)
    assert any("folded" in p for p in problems) and any("tile" in p for p in problems)
    assert _understates(L, "walls")
    assert ns.certificate_preconditions(L, ns.boundary_facts(mesh)) == [
        "the tiling of the bounding box was not checked (no coordinates)"]


def test_a_real_hanging_node_is_a_precondition_failure():
    """Red-refine only the first cube of a two-cube box: its face shared with the second
    cube then carries hanging nodes."""
    xs = np.array([0.0, 1.0, 2.0])
    tm = syn.tensor_mesh(xs, [0.0, 1.0], [0.0, 1.0])
    first = np.isclose(tm["xyz"][tm["tets"]][:, :, 0].mean(1), 0.5, atol=0.4)
    sub = {"xyz": tm["xyz"], "tets": tm["tets"][first], "tet_attr": tm["tet_attr"][first],
           "tris": np.zeros((0, 3), dtype=int), "tri_attr": np.zeros(0, dtype=int)}
    ref = af.refine_red(sub)
    mesh = {"xyz": ref["xyz"], "tets": np.vstack([ref["tets"], tm["tets"][~first]]),
            "tet_attr": np.ones(len(ref["tets"]) + int((~first).sum()), dtype=int),
            "tris": tm["faces"][tm["boundary"]], "tri_attr": np.full(int(tm["boundary"].sum()), 2)}
    bf = ns.boundary_facts(mesh, ref["xyz"])
    assert not bf["every_boundary_face_is_tagged"]
    L = ns.Level(mesh, {"eps_r": {1: 1.0}, "pec_attrs": (2,), "port_attr": 10,
                        "direction": (1.0, 0.0, 0.0), "L0_m": 1.0e-3, "L_H": 1.0e-8}, kinds=())
    assert any("untagged boundary face" in p for p in ns.certificate_preconditions(L, bf))


def test_an_indefinite_preconditioner_breaks_down_and_is_never_certified(small_ladder):
    lv, _ = small_ladder
    dd = lv[1].dd["C"]
    sysm = ns.system(lv[1].K, dd)
    _, it = ns.pcg(sysm["A"], sysm["b"], np.zeros(len(dd["free"])), lambda r: -r, maxiter=20,
                   check_every=5, target_rel=1e-12, stagnation_checks=20,
                   certify=lambda x: (math.inf, 0.0))
    assert it["status"] == "BREAKDOWN"


@pytest.mark.parametrize("seq, status, iterations", [
    # infinite checks whose true residual keeps falling do not stop a solve that certifies late
    ([(math.inf, 0.8 ** i) for i in range(30)] + [(1e-3, 1e-4), (1e-6, 1e-7), (1e-13, 1e-9)], "CERTIFIED", 32),
    ([(math.inf, 0.5)] * 40, "STAGNATED", 21),                 # infinite, flat residual
    ([(1e-3, 0.5)] * 40, "STAGNATED", 21),                     # 20 finite, no 10 % gain
    ([(1e-3 * 0.8 ** i, 0.5) for i in range(60)] + [(1e-13, 0.5)], "CERTIFIED", 60),
    # an infinite phase does not count toward the finite count, nor the reverse
    ([(1e-3, 0.5)] * 15 + [(math.inf, 0.5)] * 15 + [(1e-13, 0.5)], "CERTIFIED", 30),
])
def test_the_stagnation_rule(seq, status, iterations):
    n = 3000
    import scipy.sparse as sp
    A = sp.diags(np.linspace(1.0, 50.0, n)).tocsr()
    it_seq = iter(seq)
    _, it = ns.pcg(A, np.ones(n), np.zeros(n), lambda r: r, maxiter=500, check_every=1,
                   target_rel=1e-12, stagnation_checks=20, certify=lambda x: next(it_seq, (1e-3, 0.5)))
    assert (it["status"], it["iterations"]) == (status, iterations)


def test_a_stuck_solve_whose_certificate_stays_infinite_stops(small_ladder):
    """Revision 2 ran such a solve to maxiter: a semidefinite preconditioner that never
    updates 30 % of the unknowns keeps the certificate infinite and the residual flat."""
    lv, _ = small_ladder
    dd = lv[1].dd["C"]
    sysm = ns.system(lv[1].K, dd)
    P = ns.prolongation(lv[0].mesh, lv[1].mesh)[dd["free"]][:, lv[0].dd["C"]["free"]].tocsr()
    tg = ns.TwoGrid(sysm["A"], P, 1)
    mask = (np.random.default_rng(5).uniform(size=len(dd["free"])) > 0.3).astype(float)
    m, c, w = lv[1].m[dd["free"]], lv[1].poincare["c"], dd["phi"].copy()

    def certify(x):
        w[dd["free"]] = x
        E = float(w @ (lv[1].K @ w))
        ce = ns.certificate(sysm, x, m, c)
        return (ce["error_bound_nd"] / (E - ce["error_bound_nd"]) if E > ce["error_bound_nd"] else math.inf,
                ce["residual_2norm"])

    _, it = ns.pcg(sysm["A"], sysm["b"], np.zeros(len(dd["free"])), lambda r: mask * tg(mask * r),
                   **{k: ns.SOLVER[k] for k in ("maxiter", "check_every", "target_rel", "stagnation_checks")},
                   certify=certify)
    assert it["status"] == "STAGNATED" and it["iterations"] < 200
    assert all(e["rel_certificate"] is None for e in it["history"])


def test_the_problems_are_the_reviewed_ones_bit_for_bit():
    import importlib.util
    mods = {}
    for rel, name in (("static-anchor-hypothesis/static_capacitance.py", "sah"),
                      ("static-band-pairing/spectral.py", "sbp")):
        spec = importlib.util.spec_from_file_location(name, REPO / "experiments" / rel)
        mods[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mods[name])
    mesh, model = syn.chip_cell(**SMALL)
    L = ns.Level(mesh, model)
    assert ns.solve(L, "C", "direct")[0]["energy_nd"] == mods["sah"].static_capacitance(mesh, **model)["energy_nd"]
    assert ns.solve(L, "Cprime", "direct")[0]["energy_nd"] == mods["sbp"].port_constrained_energy(mesh, model)


def test_the_mesh_digest_detects_any_change():
    mesh, _ = syn.chip_cell(**SMALL)
    d = ns.mesh_digest(mesh)
    for key in ("xyz", "tets", "tet_attr", "tris", "tri_attr"):
        m = copy.deepcopy(mesh)
        m[key] = m[key].copy()
        m[key].flat[0] = m[key].flat[0] + 1
        assert ns.mesh_digest(m) != d, key
    assert ns.mesh_digest(copy.deepcopy(mesh)) == d


def test_a_malformed_port_is_a_precondition_failure():
    mesh, model = syn.chip_cell(**SMALL)
    L = ns.Level(mesh, model)
    bf = ns.boundary_facts(mesh, L.xyz)
    assert ns.certificate_preconditions(L, bf) == []
    L.dd["Cprime"]["geo"] = dict(L.dd["Cprime"]["geo"], area_over_lw_minus_1=1e-6)
    assert any("rectangle" in p for p in ns.certificate_preconditions(L, bf))


def test_require_extended_precision_is_a_real_check(monkeypatch):
    ns.require_extended_precision()
    assert ns.extended_precision_probe() == {"scalar": True, "csr_matvec": True, "dot": True}
    with monkeypatch.context() as mp:
        real_finfo = np.finfo
        mp.setattr(ns.np, "finfo", lambda t: real_finfo(np.float64))
        with pytest.raises(ns.Refusal, match="no extended"):
            ns.require_extended_precision()
    # the storage format passes but the arithmetic does not (a 53-bit x87 control word)
    monkeypatch.setattr(ns, "extended_precision_probe", lambda: {"scalar": False, "csr_matvec": True, "dot": True})
    with pytest.raises(ns.Refusal, match="arithmetic is not extended"):
        ns.require_extended_precision()
    mesh, model = syn.chip_cell(**SMALL)
    assert ns.solve(ns.Level(mesh, model), "C", "direct")[0]["extended_precision_probe_ok"] is False


def test_the_extended_precision_probe_detects_float64_arithmetic(monkeypatch):
    """The probe itself: with long double replaced by float64 every operation fails it."""
    monkeypatch.setattr(ns.np, "longdouble", np.float64)
    assert ns.extended_precision_probe() == {"scalar": False, "csr_matvec": False, "dot": False}


def test_the_poincare_constant_is_the_box_eigenvalue():
    mesh = syn.tensor_mesh(np.linspace(0, 2, 3), np.linspace(0, 1, 2), np.linspace(0, 0.5, 2))
    xyz = mesh["xyz"]
    attr = np.where(xyz[mesh["tets"]][:, :, 0].mean(1) < 1, 1, 3)
    pc = ns.poincare_constant({"tet_attr": attr}, xyz, {1: 2.5, 3: 11.45})
    assert pc["eps_min"] == 2.5
    assert pc["c"] == pytest.approx(2.5 * math.pi ** 2 * (1 / 4 + 1 + 4), rel=1e-15)


def test_each_half_of_the_asymmetry_term_enters_the_certificate(small_ladder):
    lv, sol = small_ladder
    dd = lv[1].dd["C"]
    sysm = ns.system(lv[1].K, dd)
    assert sysm["A_asym_abs"].nnz > 0 and sysm["D_asym_abs"].nnz > 0
    x = sol[(1, "C")][1][dd["free"]]
    args = (x, lv[1].m[dd["free"]], lv[1].poincare["c"])
    full = ns.certificate(sysm, *args)["error_bound_nd"]
    no_a = ns.certificate(dict(sysm, A_asym_abs=sysm["A_asym_abs"] * 0), *args)["error_bound_nd"]
    no_d = ns.certificate(dict(sysm, D_asym_abs=sysm["D_asym_abs"] * 0), *args)["error_bound_nd"]
    assert full > no_a and full > no_d


def test_the_rounding_term_covers_a_residual_that_rounds_to_zero():
    """One unknown, A = 3, b = 1, x = fl(1/3): the computed residual 1 - fl(3 x) is exactly
    0, but the true residual 1 - 3 x is not. Only the rounding term g covers the excess."""
    import scipy.sparse as sp
    from fractions import Fraction
    x = np.array([1.0 / 3.0])
    A = sp.csr_matrix(np.array([[3.0]]))
    sysm = {"A": A, "b": np.array([1.0]), "KfD": sp.csr_matrix(np.array([[-1.0]])), "phiD": np.array([1.0]),
            "A_asym_abs": sp.csr_matrix((1, 1)), "D_asym_abs": sp.csr_matrix((1, 1))}
    assert float(sysm["b"][0] - (A @ x)[0]) == 0.0
    excess = (1 - 3 * Fraction(float(x[0]))) ** 2 / 3          # exact: (b - A x)^2 / A
    assert excess > 0
    ce = ns.certificate(sysm, x, np.array([1.0]), 1.0)
    assert ce["residual_2norm"] == 0.0 and Fraction(ce["error_bound_nd"]) >= excess


def test_a_genuinely_leaking_prolongation_is_counted_and_fails_integrity(small_ladder, pre):
    """A coarse space in which the fine port nodes are free (problem C's) leaks into the
    fine C' problem's constrained nodes."""
    lv, sol = small_ladder
    coarse = copy.copy(lv[0])
    coarse.dd = {**lv[0].dd, "Cprime": lv[0].dd["C"]}
    r, _ = ns.solve(lv[1], "Cprime", "twogrid", coarse=coarse, coarse_phi=sol[(0, "C")][1])
    assert r["solver"]["fixed_rows_from_free_coarse_nnz"] > 0
    assert any("leaks" in b for b in sd._solver_problems("x", r["solver"], pre["integrity"]))


def test_a_boundary_face_off_the_box_surface_is_a_precondition_failure():
    """An L-shaped domain: conforming, every boundary face tagged, but the re-entrant faces
    lie inside the bounding box, where the zero extension would not be valid."""
    tm = syn.tensor_mesh(np.linspace(0, 2, 5), np.linspace(0, 2, 5), np.linspace(0, 1, 3))
    cen = tm["xyz"][tm["tets"]].mean(1)
    keep = ~((cen[:, 0] > 1) & (cen[:, 1] > 1))
    tets = tm["tets"][keep]
    loc = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))
    faces = np.sort(np.vstack([tets[:, list(f)] for f in loc]), axis=1)
    uniq, cnt = np.unique(faces, axis=0, return_counts=True)
    mesh = {"xyz": tm["xyz"], "tets": tets, "tet_attr": np.ones(len(tets), dtype=int),
            "tris": uniq[cnt == 1], "tri_attr": np.full(int((cnt == 1).sum()), 2)}
    L = ns.Level(mesh, {"eps_r": {1: 1.0}, "pec_attrs": (2,), "port_attr": 10, "direction": (1.0, 0.0, 0.0),
                        "L0_m": 1.0e-3, "L_H": 1.0e-8}, kinds=())
    bf = ns.boundary_facts(mesh, L.xyz)
    assert bf["max_face_multiplicity"] == 2 and bf["every_boundary_face_is_tagged"]
    assert bf["every_interior_face_separates_its_tetrahedra"]
    assert not bf["every_boundary_face_on_the_box_surface"]
    problems = ns.certificate_preconditions(L, bf)
    assert any("off the bounding-box surface" in q for q in problems)


def test_bound_safety_covers_its_declared_budget_on_the_measured_ladder():
    """BOUND_SAFETY must cover the bound's own evaluation (< 1e-9) and 1/(1 - rho/c) for the
    rho/c the preflight estimated on every level of the QMHP ladder."""
    p = _strict_json(HERE / "preflight.json")
    rhos = [q["rho_gershgorin_over_c"] for lv in p["levels"].values()
            for q in lv["assembly_gap_estimate"]["problems"].values()]
    assert len(rhos) == 6 and max(rhos) <= ns.RHO_OVER_C_COVERED
    assert (1 + 1e-9) / (1 - ns.RHO_OVER_C_COVERED) <= ns.BOUND_SAFETY


# --- the frozen rules -------------------------------------------------------------------

def _seq(X, err=1e-12):
    return X, [x - err for x in X], [x + err for x in X]


@pytest.mark.parametrize("X, cls, reason", [
    ([10.0, 8.0, 7.01], "CONVERGING", "within [1, 2]"),       # R = 2.02
    ([10.0, 8.0, 7.49], "CONVERGING", "within [1, 2]"),       # R = 3.92
    ([100.0, 99.0, 98.7], "CONVERGED", "within tau"),         # R = 3.33, 0.3/98.4 < 0.05
    ([10.0, 8.0, 6.5], "UNRESOLVED", "observed order below 1"),
    ([10.0, 8.0, 7.8], "UNRESOLVED", "observed order above 2"),
    ([10.0, 8.0, 5.9], "NON-CONVERGENT", "do not shrink"),    # R = 0.95
    ([10.0, 8.0, 5.0], "NON-CONVERGENT", "do not shrink"),
    # order 1 with a negative next term: positive, monotone errors, yet R = 0.8
    ([5 + h - 0.5 * h * h for h in (1.0, 0.5, 0.25)], "NON-CONVERGENT", "negative next term"),
    ([10.0, 8.0, 8.0], "UNRESOLVED", "within its certified error of zero"),
    ([10.0, 8.0, 8.1], "UNQUALIFIED", "nesting forbids"),
])
def test_the_frozen_classification_table(pre, X, cls, reason):
    c = sd.classify(*_seq(X), pre["classification"])
    assert c["cls"] == cls and reason in c["reason"]


def test_a_certified_range_touching_a_class_edge_is_unresolved(pre):
    w = pre["classification"]
    for X in ([10.0, 8.0, 7.0], [10.0, 8.0, 7.5], [10.0, 8.0, 6.0]):   # R = 2, 4, 1
        assert sd.classify(*_seq(X, 1e-12), w)["cls"] == "UNRESOLVED", X
    assert sd.classify(*_seq([10.0, 8.0, 7.01], 1e-2), w)["cls"] == "UNRESOLVED"


@pytest.mark.parametrize("X, cls", [
    ([1e-3, 2e-3, 1.8e-3], "UNRESOLVED"),           # oscillation
    ([1e-3, 2e-3, 3.2e-3], "NON-CONVERGENT"),       # growing
    ([1e-3, 2e-3, 2.4e-3], "DIFFERENCES-SHRINKING"),
    ([1e-2, 1.1e-2, 1.13e-2], "DIFFERENCES-SHRINKING"),   # would be CONVERGED under the energy rule
])
def test_delta_is_classified_descriptively_with_no_bracket(X, cls):
    c = sd.classify_delta(*_seq(X))
    assert c["cls"] == cls and "limit_bracket_model_based" not in c
    assert "theory" not in c["reason"] or "no rate theory" in c["reason"]


def test_the_declared_C2_intervals_are_what_the_rule_gives(pre):
    """C_0 and C_1 are known: the class of C is a function of C_2 alone, as declared."""
    w, iv = pre["classification"], pre["classification"]["C_intervals_given_the_known_C0_and_C1"]
    C0, C1 = pre["baseline"]["C0_fF"], pre["baseline"]["C1_fF"]
    assert iv["d1_fF"] == C0 - C1
    cls = lambda c2: sd.classify(*_seq([C0, C1, c2], 1e-12), w)["cls"]
    assert cls(50.0) == "NON-CONVERGENT" and cls(50.1) == "UNRESOLVED"
    assert cls(66.13) == "UNRESOLVED" and cls(66.14) == "CONVERGING"
    assert cls(74.16) == "CONVERGING" and cls(74.17) == "UNRESOLVED"
    assert cls(82.2) == "UNRESOLVED" and cls(82.21) == "UNQUALIFIED"
    # the declared minimum remaining error inside the window, at R = 4 (C_2 = C_1 - d1/4)
    c = sd.classify(*_seq([C0, C1, C1 - (C0 - C1) / 4 - 1e-7], 1e-12), w)      # R just below 4
    assert c["cls"] == "CONVERGING" and 0.1214 <= c["remaining_rel_error_at_level2_bracket"][1] < 0.1215
    assert "0.1214" in iv["CONVERGED"]
    classes = {cls(c2) for c2 in np.linspace(1.0, C1 + 1.0, 4001)}
    assert "CONVERGED" not in classes, "declared unreachable for C"
    assert classes == {"NON-CONVERGENT", "UNRESOLVED", "CONVERGING", "UNQUALIFIED"}


def test_converged_is_unreachable_for_cprime_below_the_declared_delta1(pre):
    """Declared: CONVERGED for C' needs delta_1 >= 0.1777 with delta_0 inside the window
    (exact threshold 0.17773-0.17775). Swept where CONVERGED is most reachable, R near 4."""
    w = pre["classification"]
    C0, C1 = pre["baseline"]["C0_fF"], pre["baseline"]["C1_fF"]
    assert "delta_1 >= 0.1777" in pre["classification"]["why_tau_0_05"]
    for d0 in pre["consistency_check"]["window_at_freeze_with_the_record_S0"]:
        Cp0 = C0 * (1 + d0)
        for d1, reachable in ((0.001, False), (0.17, False), (0.1777, False), (0.1778, True), (0.18, True)):
            Cp1 = C1 * (1 + d1)
            dd = Cp0 - Cp1
            got = {sd.classify(*_seq([Cp0, Cp1, c2], 1e-12), w)["cls"]
                   for c2 in np.linspace(Cp1 - dd / 3.9, Cp1 - dd / 4, 20001)}
            assert ("CONVERGED" in got) == reachable, (d0, d1)


def test_the_model_bracket_is_what_the_two_term_model_gives(pre):
    """X_h = X + a h + b h^q with a, b >= 0 and 1 < q <= 2 lands in the window, and its
    limit lies inside the reported bracket."""
    w = pre["classification"]
    for a, b, q in ((1.0, 0.5, 2.0), (0.2, 1.0, 2.0), (1.0, 2.0, 1.6), (0.3, 1.0, 1.2), (1.0, 5.0, 2.0)):
        X = [5.0 + a * h + b * h ** q for h in (1.0, 0.5, 0.25)]
        c = sd.classify(*_seq(X, 1e-14), w)
        assert c["cls"] in ("CONVERGING", "CONVERGED")
        lo, hi = sorted(c["limit_bracket_model_based"])
        assert lo - 1e-12 <= 5.0 <= hi + 1e-12, (a, b, q, c)
    # with coefficients of MIXED sign the bracket can miss: it is model-based, as declared
    X = [5.0 + 1.864 * h - 2.310 * h ** 1.5 + 1.374 * h ** 2 for h in (1.0, 0.5, 0.25)]
    c = sd.classify(*_seq(X, 1e-14), w)
    lo, hi = sorted(c["limit_bracket_model_based"])
    assert c["cls"] in ("CONVERGING", "CONVERGED") and not lo <= 5.0 <= hi


# --- revision 4: the tau comparison uses the certified ranges ------------------------------

def _tau_box(ratio, eps, X2=100.0, R=3.0):
    """A sequence whose conservative remaining error d2/(X2 - d2) is ``ratio`` at R = 3, with
    an absolute certified error ``eps`` on every energy (the external reproduction's form)."""
    d2 = X2 * ratio / (1 + ratio)
    vals = [X2 + d2 + R * d2, X2 + d2, X2]
    return vals, [v - eps for v in vals], [v + eps for v in vals]


def test_the_tau_comparison_uses_the_certified_ranges_at_the_boundary(pre):
    """The external reproduction on 53bac23: central remaining error tau - 1e-10 with 5e-8 on
    each energy. Revision 3 returned CONVERGED although an admissible truth in the certified
    box (X2 lower by 5e-8) is CONVERGING. Now the range straddles tau: UNRESOLVED."""
    w = pre["classification"]
    tau = w["tau_converged"]
    assert tau == 0.05                                    # the threshold itself is unchanged
    vals, lows, highs = _tau_box(tau - 1e-10, 5e-8)
    c = sd.classify(vals, lows, highs, w)
    assert c["cls"] == "UNRESOLVED" and "within its certified error of tau_converged" in c["reason"]
    lo, hi = c["remaining_rel_error_at_level2_certified_range"]
    assert lo < c["remaining_rel_error_at_level2_bracket"][1] < hi and lo < tau < hi
    assert lo == (lows[1] - highs[2]) / (2 * highs[2] - lows[1])
    assert hi == (highs[1] - lows[2]) / (2 * lows[2] - highs[1])
    # both classes are admissible inside the box: its corners, classified exactly
    exact = lambda v: sd.classify(v, v, v, w)["cls"]
    assert exact([vals[0], highs[1], lows[2]]) == "CONVERGING"
    assert exact([vals[0], lows[1], highs[2]]) == "CONVERGED"
    # a range that only TOUCHES tau is UNRESOLVED too (the fail-safe of the R edges)
    c = sd.classify(vals, lows, highs, {**w, "tau_converged": hi})
    assert c["cls"] == "UNRESOLVED"


@pytest.mark.parametrize("ratio, eps, cls", [
    (0.01, 5e-8, "CONVERGED"), (0.10, 5e-8, "CONVERGING"),          # the reproduction's controls
    (0.0499, 1e-12, "CONVERGED"), (0.0501, 1e-12, "CONVERGING"),   # near tau, range clear of it
    (0.0499, 1e-2, "UNRESOLVED"), (0.0501, 1e-2, "UNRESOLVED"),    # same values, wider ranges
])
def test_the_tau_comparison_away_from_and_near_the_boundary(pre, ratio, eps, cls):
    w = pre["classification"]
    c = sd.classify(*_tau_box(ratio, eps), w)
    assert c["cls"] == cls, c
    lo, hi = c["remaining_rel_error_at_level2_certified_range"]
    assert lo <= c["remaining_rel_error_at_level2_bracket"][1] <= hi


def test_a_model_limit_that_is_not_certainly_positive_is_unresolved(pre):
    """Found while deriving the range: [5.8, 2.5, 1.0] has R = 2.2 but X2 - d2 = -0.5, so the
    central remaining error is -3 and revision 3 returned CONVERGED."""
    w = pre["classification"]
    c = sd.classify(*_seq([5.8, 2.5, 1.0], 1e-12), w)
    assert c["cls"] == "UNRESOLVED" and "model limit" in c["reason"]
    assert c["remaining_rel_error_at_level2_bracket"][1] < 0          # what revision 3 compared
    # a positive central limit (1e-7) whose certified range reaches zero, R = 3: UNRESOLVED
    X2, lim = 1.0, 1e-7
    X1 = 2 * X2 - lim
    X = [X1 + 3 * (X1 - X2), X1, X2]
    c = sd.classify(*_seq(X, 1e-7), w)
    assert c["remaining_rel_error_at_level2_bracket"][1] > 0 and c["cls"] == "UNRESOLVED"
    assert "model limit" in c["reason"]


def test_no_admissible_point_contradicts_a_returned_class(pre):
    """Soundness, sampled: whenever classify returns CONVERGED or CONVERGING, every point of
    the certified box (its corners and random interior points), classified with zero error,
    gets the same class; whenever the certified range of the remaining error lies wholly on
    one side of tau, the class is not UNRESOLVED on account of tau."""
    w = pre["classification"]
    tau = w["tau_converged"]
    rng = np.random.default_rng(20260923)
    exact = lambda v: sd.classify(v, v, v, w)["cls"]
    checked = {"CONVERGED": 0, "CONVERGING": 0, "UNRESOLVED": 0}
    for i in range(3000):
        X2 = rng.uniform(1.0, 200.0)
        eps = X2 * 10 ** rng.uniform(-9, -3)
        width = 4 * eps / X2                          # about the width of the remaining range
        ratio = (tau * rng.uniform(0.5, 1.5) if i % 2 else          # anywhere, or within a few
                 tau + width * rng.uniform(-3.0, 3.0))               # widths of tau
        vals, lows, highs = _tau_box(ratio, eps, X2=X2, R=rng.uniform(2.05, 3.95))
        c = sd.classify(vals, lows, highs, w)
        if c["cls"] not in checked:
            continue
        checked[c["cls"]] += 1
        if c["cls"] == "UNRESOLVED":
            if "tau_converged" in c["reason"]:
                lo, hi = c["remaining_rel_error_at_level2_certified_range"]
                assert lo <= tau <= hi
            continue
        corners = [[a, b, e] for a in (lows[0], highs[0]) for b in (lows[1], highs[1]) for e in (lows[2], highs[2])]
        inner = [[rng.uniform(lows[i], highs[i]) for i in range(3)] for _ in range(8)]
        got = {exact(p) for p in corners + inner}
        assert got == {c["cls"]}, (vals, eps, c["cls"], got)
    assert min(checked.values()) > 100, checked


def _fake_levels(E, Ep, bound=1e-15):
    out = []
    for h in range(3):
        mk = lambda e: {"energy_nd": e, "C_fF": e * 30.0, "S_GHz2": 7.0 / e,
                        "total_error_bound_nd": bound, "total_error_bound_rel": bound / e,
                        "port_voltage": 1.0, "C_F": e * 3e-14, "phi_abs_max": 1.0,
                        "extended_precision_probe_ok": True,
                        "solver": {"method": "direct" if h < 2 else "twogrid", "status": "CERTIFIED",
                                   "galerkin_identity_rel": 1e-15, "fixed_rows_from_free_coarse_nnz": 0}}
        probs = {"C": mk(E[h]), "Cprime": mk(Ep[h])}
        if h == 1:
            for k in ns.KINDS:
                probs[k]["twogrid_cross_check"] = {**{kk: probs[k][kk] for kk in
                                                      ("energy_nd", "total_error_bound_nd",
                                                       "total_error_bound_rel", "C_fF", "port_voltage",
                                                       "extended_precision_probe_ok")},
                                                   "solver": {"method": "twogrid", "status": "CERTIFIED",
                                                              "galerkin_identity_rel": 1e-15,
                                                              "fixed_rows_from_free_coarse_nnz": 0}}
        out.append({"level": h, "mesh_digest": f"d{h}", "preconditions_failed": [], "problems": probs})
    return out


def _fake_pre(pre):
    p = copy.deepcopy(pre)
    p["configuration"]["level_mesh_digests"] = {"0": "d0", "1": "d1", "2": "d2"}
    return p


ANCHOR = {"C0_F": 3.2 * 3e-14, "C1_F": 2.3 * 3e-14}


def test_a_clean_synthetic_record_is_qualified_and_classified(pre):
    lv = _fake_levels([3.2, 2.3, 1.9], [3.21, 2.31, 1.91])
    out = sd.analyse(lv, _fake_pre(pre), None, ANCHOR)
    assert out["integrity_failures"] == [] and out["outcome"]["verdict"] == "QUALIFIED"
    assert out["classes"]["C"]["cls"] == "CONVERGING"                 # R = 0.9/0.4 = 2.25
    assert out["outcome"]["second_moment_name"] == "Sprime_static_identity_not_tested"
    assert "H" not in out["classes"] and "not independent" in out["outcome"]["note"]
    # every block with a model-based bracket carries its assumption; the bound basis says
    # which value it covers; the assembly-term estimate sits beside every bound
    for name in ("C", "Cprime", "S", "Sprime_static_identity_not_tested"):
        b = out["classes"][name]
        assert b["bracket_assumption"].startswith("two terms") and "ONLY" in b["bound_basis"]
        gap = pre["configuration"]["assembly_gap_preflight"]["abs_sum_nd"]["2"]
        assert b["assembly_term_estimate_rel_at_level2"] == pytest.approx(gap / (1.9 if name in ("C", "S") else 1.91))


@pytest.mark.parametrize("poison, needle", [
    (lambda lv: lv[2]["problems"]["C"].__setitem__("energy_nd", float("nan")), "not a finite positive"),
    (lambda lv: lv[1]["problems"]["Cprime"].__setitem__("C_fF", float("inf")), "not a finite positive"),
    (lambda lv: lv[0]["problems"]["C"].pop("total_error_bound_rel"), "not a finite non-negative"),
    (lambda lv: lv[2]["problems"]["C"].__setitem__("total_error_bound_rel", 1e-6), "certified error"),
    (lambda lv: lv[1]["problems"]["C"]["twogrid_cross_check"].__setitem__("total_error_bound_rel", 1e-6), "cross-check: certified error"),
    (lambda lv: lv[2]["problems"]["C"]["solver"].__setitem__("galerkin_identity_rel", 1e-9), "Galerkin"),
    (lambda lv: lv[2]["problems"]["C"]["solver"].__setitem__("fixed_rows_from_free_coarse_nnz", 3), "leaks"),
    (lambda lv: lv[1]["problems"]["C"]["twogrid_cross_check"].__setitem__("energy_nd", 2.4), "disagree"),
    (lambda lv: lv[0]["problems"]["C"].__setitem__("port_voltage", 0.5), "port voltage"),
    (lambda lv: lv[1]["problems"]["Cprime"]["twogrid_cross_check"].__setitem__("port_voltage", 0.5), "cross-check: port voltage"),
    (lambda lv: lv[2].__setitem__("mesh_digest", "other"), "mesh digest"),
    (lambda lv: lv[1]["preconditions_failed"].append("an outer-boundary node is not constrained"), "outer-boundary"),
    (lambda lv: lv[2]["problems"]["Cprime"].__setitem__("energy_nd", 1.5), "C' < C"),
    (lambda lv: (lv[2]["problems"]["C"].__setitem__("energy_nd", 2.5),
                 lv[2]["problems"]["Cprime"].__setitem__("energy_nd", 2.51)), "nesting forbids"),
    (lambda lv: lv[1]["problems"]["C"].__setitem__("C_F", 2.3 * 3e-14 * (1 + 1e-9)), "does not reproduce"),
    (lambda lv: lv[0]["problems"]["C"].__setitem__("C_F", 3.2 * 3e-14 * (1 + 1e-9)), "does not reproduce"),
    (lambda lv: lv[2]["problems"]["Cprime"].__setitem__("extended_precision_probe_ok", False), "arithmetic probe"),
    (lambda lv: lv[1]["problems"]["C"]["twogrid_cross_check"].pop("extended_precision_probe_ok"), "arithmetic probe"),
    (lambda lv: lv.pop(), "declared levels"),
])
def test_every_integrity_failure_is_unqualified_never_a_class(pre, poison, needle):
    lv = _fake_levels([3.2, 2.3, 1.9], [3.21, 2.31, 1.91])
    poison(lv)
    out = sd.analyse(lv, _fake_pre(pre), None, ANCHOR)
    assert out["outcome"]["verdict"] == "UNQUALIFIED" and "classes" not in out
    assert any(needle in f for f in out["integrity_failures"]), out["integrity_failures"]


@pytest.mark.parametrize("poison", [
    lambda lv: lv[2]["problems"]["C"]["solver"].__setitem__("status", "STAGNATED"),
    lambda lv: lv[2]["problems"]["Cprime"]["solver"].__setitem__("status", "MAXITER"),
    lambda lv: lv[2]["problems"]["C"]["solver"].__setitem__("gauss_seidel_probe_rel", 1.0),
])
def test_solver_diagnostics_are_not_integrity_the_certificate_decides(pre, poison):
    lv = _fake_levels([3.2, 2.3, 1.9], [3.21, 2.31, 1.91])
    poison(lv)
    assert sd.analyse(lv, _fake_pre(pre), None, ANCHOR)["outcome"]["verdict"] == "QUALIFIED"


def _band(pre):
    return pre["consistency_check"]["band"]["values_at_freeze"]


def _levels_with_delta0(pre, delta0, E=3.0):
    lv = _fake_levels([E, 2.3, 1.9], [E * (1 + delta0), 2.31, 1.91])
    lv[0]["problems"]["C"]["S_GHz2"] = pre["baseline"]["S0_GHz2"]
    return lv


@pytest.mark.parametrize("delta0, verdict", [
    (6.60e-4, "CONSISTENT"), (6.70e-4, "CONSISTENT"),
    (6.50e-4, "INCONSISTENT-LOW"), (6.90e-4, "INCONSISTENT-HIGH"),
])
def test_the_level0_consistency_check(pre, delta0, verdict):
    c = sd.consistency(_levels_with_delta0(pre, delta0), pre, _band(pre))
    assert c["verdict"] == verdict
    assert c["window"] == pytest.approx(pre["consistency_check"]["window_at_freeze_with_the_record_S0"], rel=1e-12)


@pytest.mark.parametrize("delta0, name", [
    (6.60e-4, "H"), (6.50e-4, "Sprime_static_identity_not_confirmed"),
    (6.90e-4, "Sprime_static_identity_not_confirmed"),
])
def test_the_second_moment_is_named_H_only_if_the_check_is_consistent(pre, delta0, name):
    anchor = {"C0_F": 3.0 * 3e-14, "C1_F": 2.3 * 3e-14}
    out = sd.analyse(_levels_with_delta0(pre, delta0), _fake_pre(pre), _band(pre), anchor)
    assert out["outcome"]["verdict"] == "QUALIFIED" and out["outcome"]["second_moment_name"] == name
    assert name in out["classes"] and ({"H", "Sprime_static_identity_not_confirmed"} - {name}).isdisjoint(out["classes"])


def test_a_failure_at_level_2_does_not_forfeit_the_level0_verdict(pre):
    anchor = {"C0_F": 3.0 * 3e-14, "C1_F": 2.3 * 3e-14}
    lv = _levels_with_delta0(pre, 6.60e-4)
    lv[2]["problems"]["C"]["total_error_bound_rel"] = 1e-6
    out = sd.analyse(lv, _fake_pre(pre), _band(pre), anchor)
    assert out["outcome"]["verdict"] == "UNQUALIFIED"
    v = out["consistency_check_level0"]
    assert v["verdict"] == "CONSISTENT" and v["nesting_0_to_1"]["status"] == "PASSED"
    # the UNQUALIFIED record says it reports no H, whatever the level-0 verdict
    assert v["in_this_record"] == pre["consistency_check"]["in_an_unqualified_record"]
    assert "no second-moment value is reported" in v["in_this_record"]
    lv[0]["problems"]["C"]["port_voltage"] = 0.5          # a level-0 failure does forfeit it
    assert sd.analyse(lv, _fake_pre(pre), _band(pre), anchor)["consistency_check_level0"]["verdict"] == "UNQUALIFIED"


def test_a_level0_to_1_nesting_failure_unqualifies_the_level0_verdict(pre):
    anchor = {"C0_F": 3.0 * 3e-14, "C1_F": 2.3 * 3e-14}
    lv = _levels_with_delta0(pre, 6.60e-4)
    lv[1]["problems"]["Cprime"]["energy_nd"] = 3.5        # E'_1 > E'_0: nesting forbids it
    for k in ("energy_nd",):
        lv[1]["problems"]["Cprime"]["twogrid_cross_check"][k] = 3.5
    out = sd.analyse(lv, _fake_pre(pre), _band(pre), anchor)
    v = out["consistency_check_level0"]
    assert out["outcome"]["verdict"] == "UNQUALIFIED"
    assert v["verdict"] == "UNQUALIFIED" and v["verdict_before_the_nesting_check"] == "CONSISTENT"
    assert v["nesting_0_to_1"]["status"] == "FAILED"
    # a level-1 failure of its own leaves the check NOT CHECKED and the verdict standing
    lv[1]["problems"]["C"]["port_voltage"] = 0.5
    v = sd.analyse(lv, _fake_pre(pre), _band(pre), anchor)["consistency_check_level0"]
    assert v["verdict"] == "CONSISTENT" and v["nesting_0_to_1"]["status"] == "NOT CHECKED"


def test_an_unresolved_level0_check_does_not_name_the_moment_H(pre):
    anchor = {"C0_F": 3.0 * 3e-14, "C1_F": 2.3 * 3e-14}
    lo = pre["consistency_check"]["window_at_freeze_with_the_record_S0"][0]
    lv = _levels_with_delta0(pre, lo, E=3.0)
    for kind in ("C", "Cprime"):                        # a certified range straddling the edge
        lv[0]["problems"][kind]["total_error_bound_nd"] = 3e-6
        lv[0]["problems"][kind]["total_error_bound_rel"] = 1e-6
    fake = _fake_pre(pre)
    fake["integrity"]["certificate_rel_tol"] = 1e-5
    out = sd.analyse(lv, fake, _band(pre), anchor)
    assert out["consistency_check_level0"]["verdict"] == "UNRESOLVED"
    assert out["outcome"]["second_moment_name"] == "Sprime_static_identity_not_confirmed" and "H" not in out["classes"]


def test_the_consistency_window_is_recomputed_from_the_pinned_band(pre):
    got = sd.band_baseline(pre)
    for k, v in _band(pre).items():
        assert got[k] == v, k


def test_tampered_band_or_anchor_inputs_refuse(pre, tmp_path, monkeypatch):
    fake = copy.deepcopy(pre)
    fake["consistency_check"]["band"]["sha256"]["eig.csv"] = "0" * 64
    with pytest.raises(sd.Refusal, match="eig.csv does not match"):
        sd.band_baseline(fake)
    fake = copy.deepcopy(pre)
    fake["reproduction"]["sha256"]["level1.json"] = "0" * 64
    with pytest.raises(sd.Refusal, match="level1.json does not match"):
        sd.anchor_values(fake)


# --- the gate, the one attempt and the evidence --------------------------------------------

def _synthetic_gate(tmp_path, monkeypatch, pre):
    """Route execute() onto the small synthetic cell in tmp_path: no QMHP data, no limits.
    Everything the gate checks before the attempt is stubbed to pass here; each check has
    its own test below."""
    mesh, model = syn.chip_cell(**SMALL)
    meshes = sd.ladder(mesh)
    fake = copy.deepcopy(pre)
    fake["configuration"]["level_mesh_digests"] = {str(h): ns.mesh_digest(m) for h, m in enumerate(meshes)}
    L0, L1 = ns.Level(meshes[0], model), ns.Level(meshes[1], model)
    anchor = {"C0_F": ns.solve(L0, "C", "direct")[0]["C_F"], "C1_F": ns.solve(L1, "C", "direct")[0]["C_F"]}
    approval = tmp_path / "STUDY-APPROVAL.json"
    approval.write_text("{}")
    monkeypatch.setattr(sd, "APPROVAL", approval)
    monkeypatch.setattr(sd, "APPROVAL_CONSUMED", tmp_path / "STUDY-APPROVAL.consumed.json")
    monkeypatch.setattr(sd, "ATTEMPT_MARKER", tmp_path / "ATTEMPT-SPENT.json")
    monkeypatch.setattr(sd, "RESULTS_ROOT", tmp_path / "results")
    monkeypatch.setattr(sd, "common_ledger_path", lambda repo=None: tmp_path / "gitcommon" / sd.COMMON_LEDGER)
    (tmp_path / "gitcommon").mkdir()
    monkeypatch.setattr(sd, "require_approval", lambda p, now=None, **k: {"run_label": "synthetic"})
    monkeypatch.setattr(sd, "unbound_repo_modules", lambda: [])
    monkeypatch.setattr(sd, "environment_problems", lambda p: [])
    monkeypatch.setattr(sd, "invocation_problems", lambda p, m=None: [])
    monkeypatch.setattr(sd, "load_pre", lambda: fake)
    monkeypatch.setattr(sd, "_read_pre", lambda: (fake, "f" * 64))
    monkeypatch.setattr(sd, "qmhp_mesh", lambda cfg=None: mesh)
    monkeypatch.setattr(sd, "_model", lambda cfg=None: model)
    monkeypatch.setattr(sd, "band_baseline", lambda p: fake["consistency_check"]["band"]["values_at_freeze"])
    monkeypatch.setattr(sd, "anchor_values", lambda p: anchor)
    monkeypatch.setattr(sd, "_enforce_budget", lambda p: {"synthetic": "no limits in pytest"})
    monkeypatch.setattr(sd, "_disarm", lambda: None)
    return fake


RAW = ["level0.json", "level0-C.json", "level0-Cprime.json", "consistency-level0.json",
       "level1.json", "level1-C.json", "level1-C-crosscheck.json", "level1-Cprime.json",
       "level1-Cprime-crosscheck.json", "level2.json", "level2-C.json", "level2-Cprime.json"]


def test_without_an_approval_the_study_refuses_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(sd, "APPROVAL", tmp_path / "STUDY-APPROVAL.json")
    monkeypatch.setattr(sd, "APPROVAL_CONSUMED", tmp_path / "STUDY-APPROVAL.consumed.json")
    monkeypatch.setattr(sd, "ATTEMPT_MARKER", tmp_path / "ATTEMPT-SPENT.json")
    monkeypatch.setattr(sd, "RESULTS_ROOT", tmp_path / "results")
    monkeypatch.setattr(sd, "common_ledger_path", lambda repo=None: tmp_path / "gitcommon" / sd.COMMON_LEDGER)
    with pytest.raises(sd.Refusal, match="PREPARED, NOT APPROVED"):
        sd.execute()
    assert sorted(p.name for p in tmp_path.iterdir()) == []


def test_the_real_invocation_refuses_today():
    assert not sd.APPROVAL.exists(), "an approval exists: this study is no longer NOT APPROVED"
    assert not sd.APPROVAL_CONSUMED.exists(), "an approval has been consumed: the attempt was spent"
    assert not sd.ATTEMPT_MARKER.exists(), "the attempt has been spent"
    assert not sd.common_ledger_path().exists(), "the attempt has been spent (git common directory)"
    assert not list((REPO / "results").glob(sd.RECORD_PREFIX + "*")), "the attempt has been spent"
    assert sd.spent_state() == []
    assert sd.main([]) == 2


def test_a_granted_attempt_writes_every_solve_then_a_summary_and_a_verified_manifest(tmp_path, monkeypatch, pre):
    _synthetic_gate(tmp_path, monkeypatch, pre)
    rec = sd.execute()
    assert rec.parent == tmp_path / "results" and rec.name.startswith(sd.RECORD_PREFIX)
    assert sorted(p.name for p in rec.iterdir()) == sorted(RAW + ["provenance.json", "summary.json", "manifest.sha256"])
    assert manifest.verify(rec) == [] and manifest.unexpected_files(rec) == []
    for p in rec.glob("*.json"):
        _strict_json(p)                                   # no Infinity or NaN tokens anywhere
    s = _strict_json(rec / "summary.json")
    assert s["integrity_failures"] == [] and s["outcome"]["verdict"] == "QUALIFIED"
    assert s["consistency_check_level0"]["level0_integrity_failures"] == []
    assert _strict_json(rec / "consistency-level0.json")["verdict"] == s["consistency_check_level0"]["verdict"]
    prov = _strict_json(rec / "provenance.json")
    assert prov["environment"]["code_sha256"] == {n: _sha(p) for n, p in sd.CODE_FILES.items()}
    assert prov["source_commit_measured"] == sd.git_head(REPO)
    assert prov["approval_sha256"] == hashlib.sha256(b"{}").hexdigest()
    assert set(prov["invocation"]) >= {"cwd", "argv", "parent_argv", "prefix", "optimize", "pycache_prefix"}
    assert all(prov["environment"]["extended_precision_probe"].values())
    # the three ledger entries: the common-directory entry, the marker, the consumed approval
    for entry in (sd.common_ledger_path(), sd.ATTEMPT_MARKER):
        assert _strict_json(entry)["record"] == rec.name
    assert not sd.APPROVAL.exists() and sd.APPROVAL_CONSUMED.read_text() == "{}"
    assert s["signals_received"] == [] and not list(rec.glob("*.partial"))
    with pytest.raises(sd.Refusal, match="the one attempt is spent"):
        sd.execute()


def test_a_checkout_that_removes_the_tracked_ledger_does_not_reopen_the_attempt(tmp_path, monkeypatch, pre):
    """Revision 2: after the record and marker were committed, `git checkout <approved
    commit>` removed both from the working tree while the untracked approval survived, and
    a second attempt ran. Now the git-common-directory entry survives, and the approval was
    consumed."""
    _synthetic_gate(tmp_path, monkeypatch, pre)
    rec = sd.execute()
    import shutil
    shutil.rmtree(rec.parent)                              # what a checkout of C1 removes
    sd.ATTEMPT_MARKER.unlink()
    sd.APPROVAL.write_text("{}")                          # even a re-supplied approval
    with pytest.raises(sd.Refusal, match="the one attempt is spent"):
        sd.execute()
    sd.APPROVAL_CONSUMED.unlink()                         # and even without the consumed copy
    with pytest.raises(sd.Refusal, match="git common dir"):
        sd.execute()
    assert not (tmp_path / "results").exists()


def test_the_ledger_entries_are_created_exclusively(tmp_path, monkeypatch, pre):
    """A ledger entry created between the pre-check and the exclusive create: the common
    entry refuses with nothing of ours created; the marker (after the common entry) spends
    the attempt, and the failure goes into the entry this process created, never into one
    it did not create."""
    _synthetic_gate(tmp_path, monkeypatch, pre)
    monkeypatch.setattr(sd, "spent_state", lambda root=None: [])
    common = sd.common_ledger_path()
    common.parent.mkdir(parents=True)
    common.write_text('{"someone": "else"}')
    with pytest.raises(sd.Refusal, match="git common directory: the one attempt is spent"):
        sd.execute()
    assert common.read_text() == '{"someone": "else"}' and sd.APPROVAL.exists()
    assert not sd.ATTEMPT_MARKER.exists() and not (tmp_path / "results").exists()
    common.unlink()
    sd.ATTEMPT_MARKER.write_text('{"someone": "else"}')
    with pytest.raises(sd.AttemptFailed, match="no record could be created"):
        sd.execute()
    assert sd.ATTEMPT_MARKER.read_text() == '{"someone": "else"}'
    note = _strict_json(common)
    assert note["record_created"] is False and "FileExistsError" in note["error"]
    assert sd.APPROVAL_CONSUMED.exists() and not sd.APPROVAL.exists()


def test_a_failure_before_the_record_exists_is_written_into_the_ledger(tmp_path, monkeypatch, pre, capsys):
    """Revision 2 spent the attempt with no record, no failure.json and a raw traceback when
    the record directory could not be created."""
    _synthetic_gate(tmp_path, monkeypatch, pre)
    (tmp_path / "results").write_text("not a directory")
    assert sd.main([]) == 3
    assert "no record could be created" in capsys.readouterr().err
    for entry in (sd.common_ledger_path(), sd.ATTEMPT_MARKER):
        note = _strict_json(entry)
        assert note["record_created"] is False and "Error" in note["error"] and note["traceback"]
    assert sd.APPROVAL_CONSUMED.exists()
    assert sd.main([]) == 2                               # spent: refused, nothing more


def test_a_failure_before_the_first_ledger_entry_spends_nothing(tmp_path, monkeypatch, pre):
    _synthetic_gate(tmp_path, monkeypatch, pre)

    def broken(p):
        raise OSError("setrlimit failed")

    monkeypatch.setattr(sd, "_enforce_budget", broken)
    with pytest.raises(sd.Refusal, match="nothing was spent"):
        sd.execute()
    assert sd.spent_state() == [] and sd.APPROVAL.exists()


def test_the_attempt_marker_alone_refuses_even_without_a_record(tmp_path, monkeypatch, pre):
    _synthetic_gate(tmp_path, monkeypatch, pre)
    sd.ATTEMPT_MARKER.write_text("{}")
    with pytest.raises(sd.Refusal, match="the one attempt is spent"):
        sd.execute()
    assert not (tmp_path / "results").exists()


def test_a_failure_in_the_last_solve_keeps_every_completed_solve(tmp_path, monkeypatch, pre):
    """Revision 1 discarded a completed, certified level-2 C solve when the level-2 C'
    solve raised. Now each solve is written as it completes."""
    _synthetic_gate(tmp_path, monkeypatch, pre)
    real, calls = ns.solve, []

    def fails_last(level, kind, method, **kw):
        calls.append((len(level.mesh["tets"]), kind, method))
        if len(calls) == 8:
            raise sd.BudgetExceeded("SIGXCPU: a declared budget limit was reached")
        return real(level, kind, method, **kw)

    monkeypatch.setattr(sd.ns, "solve", fails_last)
    with pytest.raises(sd.AttemptFailed, match="SIGXCPU") as err:
        sd.execute()
    assert isinstance(err.value.__cause__, sd.BudgetExceeded)
    (rec,) = (tmp_path / "results").glob(sd.RECORD_PREFIX + "*")
    names = sorted(p.name for p in rec.iterdir())
    assert "level2-C.json" in names and "level2-Cprime.json" not in names
    assert manifest.verify(rec) == []
    f = _strict_json(rec / "failure.json")
    assert f["levels_completed"] == [0, 1] and f["files_written"] == ["provenance.json"] + RAW[:-1]
    assert f["consistency_check_level0"] == _strict_json(rec / "consistency-level0.json")   # read back
    assert f["nesting_0_to_1"]["status"] in ("PASSED", "NOT CHECKED")
    assert f["provenance"]["mesh_sha256"] == sd.CONFIG["mesh_sha256"]
    assert f["summary_json_superseded"] is False and f["partial_files"] == []
    assert _strict_json(rec / "level2-C.json")["solver"]["status"] == "CERTIFIED"


@pytest.mark.parametrize("fail_at, written", [
    (1, ["provenance.json", "level0.json"]),                         # the first level-0 solve
    (3, ["provenance.json", "level0.json", "level0-C.json", "level0-Cprime.json",
         "consistency-level0.json", "level1.json"]),                 # the first level-1 solve
])
def test_the_write_order_is_the_declared_one(tmp_path, monkeypatch, pre, fail_at, written):
    """provenance.json first, each level's facts before its solves, consistency-level0.json
    as soon as level 0 completes; the marker and the common entry exist on a failed attempt."""
    _synthetic_gate(tmp_path, monkeypatch, pre)
    real, calls = ns.solve, []

    def fails(level, kind, method, **kw):
        calls.append(1)
        if len(calls) == fail_at:
            raise RuntimeError("injected")
        return real(level, kind, method, **kw)

    monkeypatch.setattr(sd.ns, "solve", fails)
    with pytest.raises(sd.AttemptFailed, match="injected"):
        sd.execute()
    (rec,) = (tmp_path / "results").glob(sd.RECORD_PREFIX + "*")
    assert _strict_json(rec / "failure.json")["files_written"] == written
    assert manifest.verify(rec) == []
    for entry in (sd.common_ledger_path(), sd.ATTEMPT_MARKER):
        assert _strict_json(entry)["record"] == rec.name


def test_an_analysis_fault_after_level0_does_not_stop_the_solves(tmp_path, monkeypatch, pre):
    """Revision 2: an exception in the level-0 analysis ended run_levels, and the failure
    path re-ran the same analysis while writing failure.json, losing it and the manifest."""
    _synthetic_gate(tmp_path, monkeypatch, pre)

    def broken(*a, **k):
        raise ZeroDivisionError("latent defect in the consistency code")

    monkeypatch.setattr(sd, "consistency", broken)
    with pytest.raises(sd.AttemptFailed, match="latent defect"):
        sd.execute()                                  # analyse() at the end raises too
    (rec,) = (tmp_path / "results").glob(sd.RECORD_PREFIX + "*")
    raw = [n for n in RAW if n != "consistency-level0.json"] + ["consistency-level0.error.json"]
    assert sorted(p.name for p in rec.iterdir()) == sorted(raw + ["provenance.json", "failure.json", "manifest.sha256"])
    assert manifest.verify(rec) == []
    f = _strict_json(rec / "failure.json")
    assert f["levels_completed"] == [0, 1, 2] and f["consistency_check_level0"] is None


def test_a_crash_in_the_analysis_still_leaves_every_raw_file_and_a_verified_manifest(
        tmp_path, monkeypatch, pre):
    _synthetic_gate(tmp_path, monkeypatch, pre)

    def broken(*a, **k):
        raise RuntimeError("analysis crashed")

    monkeypatch.setattr(sd, "analyse", broken)
    with pytest.raises(sd.AttemptFailed, match="analysis crashed"):
        sd.execute()
    (rec,) = (tmp_path / "results").glob(sd.RECORD_PREFIX + "*")
    assert sorted(p.name for p in rec.iterdir()) == sorted(RAW + ["provenance.json", "failure.json", "manifest.sha256"])
    assert manifest.verify(rec) == []
    assert sd.main([]) == 2                          # a second attempt is refused, nothing spent


def test_a_refusal_inside_the_attempt_is_reported_as_a_spent_failure(tmp_path, monkeypatch, pre, capsys):
    _synthetic_gate(tmp_path, monkeypatch, pre)

    def refuses(*a, **k):
        raise ns.Refusal("3 conductors; the study is defined for exactly two")

    monkeypatch.setattr(sd.ns, "Level", refuses)
    assert sd.main([]) == 3
    assert "FAILED" in capsys.readouterr().err
    (rec,) = (tmp_path / "results").glob(sd.RECORD_PREFIX + "*")
    assert (rec / "failure.json").is_file() and manifest.verify(rec) == []


def test_a_failing_manifest_write_on_the_success_path_reaches_the_failure_path(tmp_path, monkeypatch, pre):
    _synthetic_gate(tmp_path, monkeypatch, pre)
    real, calls = sd.manifest.write_verified, []

    def flaky(root, filename="manifest.sha256"):
        calls.append(1)
        if len(calls) == 1:
            raise OSError(28, "No space left on device")
        return real(root, filename)

    monkeypatch.setattr(sd.manifest, "write_verified", flaky)
    with pytest.raises(sd.AttemptFailed, match="No space"):
        sd.execute()
    (rec,) = (tmp_path / "results").glob(sd.RECORD_PREFIX + "*")
    assert (rec / "summary.json").is_file() and (rec / "failure.json").is_file()
    assert manifest.verify(rec) == []


def test_a_refined_mesh_that_differs_is_refused_before_the_attempt(tmp_path, monkeypatch, pre):
    fake = _synthetic_gate(tmp_path, monkeypatch, pre)
    fake["configuration"]["level_mesh_digests"]["2"] = "0" * 64
    with pytest.raises(sd.Refusal, match="differs from the pre-declared"):
        sd.execute()
    assert not (tmp_path / "results").exists() and not sd.ATTEMPT_MARKER.exists()


@pytest.mark.parametrize("stub, message", [
    ("unbound_repo_modules", "does not bind is loaded"),
    ("environment_problems", "environment differs"),
])
def test_unbound_code_or_a_different_environment_refuses_before_the_attempt(tmp_path, monkeypatch, pre, stub, message):
    _synthetic_gate(tmp_path, monkeypatch, pre)
    monkeypatch.setattr(sd, stub, lambda *a: ["something"])
    with pytest.raises(sd.Refusal, match=message):
        sd.execute()
    assert not sd.ATTEMPT_MARKER.exists()


def test_an_environment_that_cannot_apply_the_budget_is_refused_before_the_attempt(
        tmp_path, monkeypatch, pre):
    _synthetic_gate(tmp_path, monkeypatch, pre)
    real = sd.resource.getrlimit
    monkeypatch.setattr(sd.resource, "getrlimit",
                        lambda r: (1024, 1024) if r == sd.resource.RLIMIT_AS else real(r))
    with pytest.raises(sd.Refusal, match="cannot be applied as declared"):
        sd.execute()
    assert not sd.ATTEMPT_MARKER.exists()


# --- the approval ----------------------------------------------------------------------------

def _granted(pre, **over):
    draft = json.loads((HERE / "STUDY-APPROVAL.draft.json").read_text())
    now = datetime.now(timezone.utc)
    ap = {k: v for k, v in draft.items() if k not in ("DRAFT", "how_to_grant_it")}
    ap.update(source_commit=sd.git_head(REPO), repository_path=str(sd.REPO),
              not_before_utc=(now - timedelta(hours=1)).isoformat(),
              not_after_utc=(now + timedelta(days=2)).isoformat())
    ap.update(over)
    return ap


def test_the_draft_approval_matches_the_files_and_grants_exactly_one_attempt(tmp_path, monkeypatch, pre):
    draft = json.loads((HERE / "STUDY-APPROVAL.draft.json").read_text())
    assert "NOT AN APPROVAL" in draft["DRAFT"]
    assert draft["predeclaration_sha256"] == _sha(HERE / "predeclaration.json") == PREDECLARATION_SHA256
    assert draft["code_sha256"] == {n: _sha(p) for n, p in sd.CODE_FILES.items()}, (
        "the code changed after the draft was reviewed: re-review the draft")
    for key in ("source_commit", "not_before_utc", "not_after_utc"):
        assert draft[key].startswith("<"), f"{key} must be filled in by the approving human"
    assert draft["attempt"] == 1 and draft["prior_records"] == [] and draft["budget"]["attempts"] == 1
    assert draft["environment"] == pre["environment"] and draft["invocation"] == pre["budget"]["invocation"]
    ap = tmp_path / "STUDY-APPROVAL.json"
    ap.write_text(json.dumps(_granted(pre)))
    monkeypatch.setattr(sd, "APPROVAL", ap)
    assert sd.require_approval(pre)["authorises"] == "one execution of the static-only nested refinement study"


@pytest.mark.parametrize("over, message", [
    ({"source_commit": "0" * 40}, "is not HEAD"),
    ({"source_commit": "HEAD"}, "not a full commit SHA"),
    ({"repository_path": "/somewhere/else"}, "repository_path does not match"),
    ({"attempt": 2}, "attempt does not match"),
    ({"prior_records": ["STATIC-REFINEMENT-STUDY-20260101T000000Z"]}, "prior_records does not match"),
    ({"predeclaration_sha256": "0" * 64}, "predeclaration_sha256 does not match"),
    ({"mesh_sha256": "1" * 64}, "mesh_sha256 does not match"),
    ({"code_sha256": {}}, "code_sha256 does not match"),
    ({"environment": {}}, "environment does not match"),
    ({"invocation": "python study_driver.py"}, "invocation does not match"),
    ({"budget": {}}, "budget does not match"),
    ({"authorises": "two executions"}, "authorises does not match"),
    ({"not_before_utc": "2026-01-01T00:00:00+00:00", "not_after_utc": "2026-01-02T00:00:00+00:00"}, "outside its validity window"),
    ({"not_after_utc": "2099-01-01T00:00:00+00:00"}, "longer than 7 days"),
    ({"not_before_utc": "2026-09-23T00:00:00"}, "no time zone"),
])
def test_a_stale_foreign_or_misdirected_approval_is_refused(tmp_path, monkeypatch, pre, over, message):
    ap = tmp_path / "STUDY-APPROVAL.json"
    ap.write_text(json.dumps(_granted(pre, **over)))
    monkeypatch.setattr(sd, "APPROVAL", ap)
    with pytest.raises(sd.Refusal, match=message):
        sd.require_approval(pre)


def test_an_approval_window_longer_than_seven_days_is_refused(tmp_path, monkeypatch, pre):
    now = datetime.now(timezone.utc)
    ap = tmp_path / "STUDY-APPROVAL.json"
    monkeypatch.setattr(sd, "APPROVAL", ap)
    for days, ok in ((6.9, True), (7.0, True), (7.01, False), (8.0, False), (30.0, False)):
        ap.write_text(json.dumps(_granted(pre, not_before_utc=(now - timedelta(hours=1)).isoformat(),
                                          not_after_utc=(now - timedelta(hours=1) + timedelta(days=days)).isoformat())))
        if ok:
            assert sd.require_approval(pre)["attempt"] == 1
        else:
            with pytest.raises(sd.Refusal, match="longer than 7 days"):
                sd.require_approval(pre)


def test_the_approval_is_parsed_from_the_bytes_that_are_hashed(tmp_path, monkeypatch, pre):
    ap = tmp_path / "STUDY-APPROVAL.json"
    ap.write_text(json.dumps(_granted(pre)))
    monkeypatch.setattr(sd, "APPROVAL", ap)
    raw = ap.read_bytes()
    ap.write_text("{}")                                   # the file changes after the read
    assert sd.require_approval(pre, raw=raw)["attempt"] == 1
    with pytest.raises(sd.Refusal, match="predeclaration_sha256 does not match"):
        sd.require_approval(pre, raw=raw, pre_sha256="0" * 64)


def test_git_head_is_read_correctly_without_running_git():
    want = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()
    assert sd.git_head(REPO) == want


def test_the_common_ledger_is_shared_by_every_worktree_of_a_clone(tmp_path):
    git = lambda *a, cwd=tmp_path / "main": subprocess.run(
        ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *a], cwd=cwd,
        capture_output=True, text=True, check=True).stdout.strip()
    (tmp_path / "main").mkdir()
    git("init", "-q")
    (tmp_path / "main" / "f").write_text("x")
    git("add", "f")
    git("commit", "-q", "-m", "c1")
    git("worktree", "add", "-q", str(tmp_path / "wt"))
    common = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    for tree in (tmp_path / "main", tmp_path / "wt"):
        assert sd.common_ledger_path(tree) == common / sd.COMMON_LEDGER
        assert sd.git_head(tree) == git("rev-parse", "HEAD", cwd=tree)


# --- process-level checks, each in a fresh interpreter ----------------------------------------

def _python(code: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], capture_output=True,
                          text=True, timeout=120, env=env, cwd=str(REPO))


def test_the_execution_path_loads_only_bound_repository_code():
    code = f"""
        import sys; sys.path.insert(0, {str(HERE)!r})
        import study_driver as sd
        print(sd.unbound_repo_modules())
        import importlib; sys.path.insert(0, {str(REPO)!r}); importlib.import_module('orchestrator')
        print(sd.unbound_repo_modules())
    """
    out = _python(code)
    assert out.returncode == 0, out.stderr[-500:]
    first, second = out.stdout.strip().splitlines()
    assert first == "[]", "the driver executes repository code the approval does not bind"
    assert "orchestrator/__init__.py" in second, "the negative control must be detected"


def test_the_environment_check_requires_the_verified_versions_and_single_threads(pre, monkeypatch):
    """Hermetic: the check itself, against a declared environment equal to THIS interpreter
    (push CI runs another patch release; revision 2's test required the host to be the
    verified one and turned CI red), then each difference as a negative control."""
    import platform
    import scipy
    here = copy.deepcopy(pre)
    here["environment"].update(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__)
    for k, v in THREADS.items():
        monkeypatch.setenv(k, v)
    assert sd.environment_problems(here) == []
    for key, value in (("python", "3.11.0"), ("numpy", "0.0"), ("scipy", "0.0")):
        other = copy.deepcopy(here)
        other["environment"][key] = value
        assert any(p.startswith(f"{key} is ") for p in sd.environment_problems(other)), key
    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "4")
    assert any("OPENBLAS_NUM_THREADS" in p for p in sd.environment_problems(here))
    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "1")
    monkeypatch.delenv("MKL_NUM_THREADS")
    assert any("MKL_NUM_THREADS" in p for p in sd.environment_problems(here))
    monkeypatch.setenv("MKL_NUM_THREADS", "1")
    real_finfo = np.finfo
    with monkeypatch.context() as mp:
        mp.setattr(sd.np, "finfo", lambda t: real_finfo(np.float64))
        assert "no extended-precision long double" in sd.environment_problems(here)
    monkeypatch.setattr(sd.ns, "extended_precision_probe", lambda: {"scalar": True, "csr_matvec": False, "dot": True})
    assert any("arithmetic is not extended" in p for p in sd.environment_problems(here))


def test_this_host_matches_the_verified_environment_where_it_is_the_execution_host(pre):
    """The host-identity assertion, skipped with its reason on any host that is not the
    verified one (push CI resolves its own Python patch release)."""
    import platform
    import scipy
    have = (platform.python_version(), np.__version__, scipy.__version__)
    want = tuple(pre["environment"][k] for k in ("python", "numpy", "scipy"))
    if have != want or Path(sys.prefix).resolve() != (REPO / ".venv").resolve():
        pytest.skip(f"not the verified execution host: {have} with prefix {sys.prefix}, verified {want} in .venv")
    out = _python(f"""
        import sys, json; sys.path.insert(0, {str(HERE)!r})
        import study_driver as sd
        print(json.dumps(sd.environment_problems(sd.load_pre())))
    """, THREADS)
    assert out.returncode == 0 and json.loads(out.stdout) == [], out.stdout + out.stderr[-300:]


def _measured(**over):
    m = {"cwd": str(REPO), "argv": ["experiments/static-refinement-study/study_driver.py"],
         "parent_argv": ["/usr/bin/timeout", "--signal=KILL", "3660", ".venv/bin/python",
                         "experiments/static-refinement-study/study_driver.py"],
         "executable": str(REPO / ".venv" / "bin" / "python"), "prefix": str(REPO / ".venv"),
         "optimize": 0, "dont_write_bytecode": True, "pycache_prefix": sd.NO_BYTECODE_CACHE,
         "bytecode_cache_paths": {"nested_solver.py": sd.NO_BYTECODE_CACHE + "/x.pyc"}}
    m.update(over)
    return m


@pytest.mark.parametrize("over, needle", [
    ({"cwd": "/"}, "working directory"),
    ({"argv": ["study_driver.py"]}, "argv"),
    ({"parent_argv": ["bash"]}, "parent process"),
    ({"parent_argv": None}, "parent process"),
    ({"parent_argv": ["timeout", "--signal=KILL", "99999", ".venv/bin/python",
                      "experiments/static-refinement-study/study_driver.py"]}, "parent process"),
    ({"prefix": "/usr"}, "interpreter prefix"),
    ({"optimize": 1}, "optimisation"),
    ({"dont_write_bytecode": False}, "bytecode"),
    ({"pycache_prefix": None}, "bytecode"),
    ({"bytecode_cache_paths": {"nested_solver.py": "/repo/__pycache__/nested_solver.cpython-311.pyc"}}, "bytecode"),
])
def test_the_invocation_is_measured_and_compared_not_just_its_text(pre, over, needle):
    assert sd.invocation_problems(pre, _measured()) == []
    got = sd.invocation_problems(pre, _measured(**over))
    assert len(got) == 1 and needle in got[0], got


def test_the_declared_invocation_text_and_its_measured_form_agree(pre):
    b = pre["budget"]
    m = b["invocation_measured_as"]
    assert b["invocation"].endswith("env " + " ".join(f"{k}={v}" for k, v in pre["environment"]["threads_env"].items())
                                    + " " + " ".join(m["parent_argv"]))
    assert m["parent_argv"][-1:] == m["argv"] and m["parent_argv"][2] == str(int(b["wall_cap_minutes"] * 60) + 60)


def test_the_study_process_measures_its_real_invocation_and_bypasses_bytecode_caches():
    """The real driver, started as the study is (from the repository root under timeout),
    in its read-only --show-invocation mode."""
    out = subprocess.run(["timeout", "--signal=KILL", "120", sys.executable,
                          "experiments/static-refinement-study/study_driver.py", "--show-invocation"],
                         cwd=str(REPO), capture_output=True, text=True, timeout=180,
                         env={**os.environ, **THREADS})
    assert out.returncode == 0, out.stderr[-500:]
    r = json.loads(out.stdout)
    m = r["measured"]
    assert Path(m["parent_argv"][0]).name == "timeout" and m["parent_argv"][1:3] == ["--signal=KILL", "120"]
    assert m["dont_write_bytecode"] and m["pycache_prefix"] == sd.NO_BYTECODE_CACHE
    assert set(m["bytecode_cache_paths"]) == {"nested_solver.py", "anchor_fem.py", "orchestrator/manifest.py"}
    assert all(c.startswith(sd.NO_BYTECODE_CACHE) for c in m["bytecode_cache_paths"].values())
    diffs = r["differences_from_declared"]
    assert any(d.startswith("argv") for d in diffs) and any("parent process" in d for d in diffs)
    assert not any("bytecode" in d or "optimisation" in d or "working directory" in d for d in diffs)


@pytest.mark.parametrize("budget, work, expect", [
    ({"cpu_minutes": 10, "memory_GB": 8, "wall_cap_minutes": 1 / 60},
     "import time\nwhile True: time.sleep(0.05)", "SIGALRM"),
    ({"cpu_minutes": 1 / 60, "memory_GB": 8, "wall_cap_minutes": 1}, "while True: pass", "SIGXCPU"),
    ({"cpu_minutes": 10, "memory_GB": 4, "wall_cap_minutes": 1},
     "import numpy\nnumpy.ones(6 * 1024**3 // 8)", "MemoryError"),
    ({"cpu_minutes": 10, "memory_GB": 8, "wall_cap_minutes": 1},
     "import os, signal, time\nos.kill(os.getpid(), signal.SIGTERM)\ntime.sleep(5)", "SIGTERM"),
    ({"cpu_minutes": 10, "memory_GB": 8, "wall_cap_minutes": 1},
     "import os, signal, time\nos.kill(os.getpid(), signal.SIGHUP)\ntime.sleep(5)", "SIGHUP"),
    ({"cpu_minutes": 10, "memory_GB": 8, "wall_cap_minutes": 1},
     "import os, signal, time\nos.kill(os.getpid(), signal.SIGINT)\ntime.sleep(5)", "BudgetExceeded: SIGINT"),
])
def test_the_declared_budget_binds_a_real_process(budget, work, expect):
    code = (f"import sys\nsys.path.insert(0, {str(HERE)!r})\nimport study_driver as sd\n"
            f"sd._enforce_budget({{'budget': {budget!r}}})\n{work}\n")
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0 and expect in proc.stderr, proc.stderr[-400:]


def test_disarm_ignores_every_stop_signal_cancels_the_alarm_and_lifts_the_soft_limits():
    """Each step of _disarm, checked on its own in a fresh process."""
    out = _python(f"""
        import sys, json, signal, resource
        sys.path.insert(0, {str(HERE)!r})
        import study_driver as sd
        sd._enforce_budget({{"budget": {{"cpu_minutes": 10, "memory_GB": 8, "wall_cap_minutes": 5}}}})
        armed = [signal.getsignal(s) is sd._on_limit for s in sd.STOP_SIGNALS]
        sd._disarm()
        print(json.dumps({{"armed": armed, "stopping": sd._SIGNALS["stopping"],
                          "ignored": [signal.getsignal(s) == signal.SIG_IGN for s in sd.STOP_SIGNALS],
                          "alarm_left": signal.alarm(0),
                          "soft_eq_hard": [resource.getrlimit(r)[0] == resource.getrlimit(r)[1]
                                           for r in (resource.RLIMIT_CPU, resource.RLIMIT_AS)]}}))
    """)
    assert out.returncode == 0, out.stderr[-500:]
    r = json.loads(out.stdout)
    assert r == {"armed": [True] * 5, "stopping": True, "ignored": [True] * 5, "alarm_left": 0,
                 "soft_eq_hard": [True, True]}
    assert {s.name for s in sd.STOP_SIGNALS} == {"SIGXCPU", "SIGALRM", "SIGTERM", "SIGHUP", "SIGINT"}


_SIGNAL_CHILD = """
import sys, json, time
sys.path.insert(0, {here!r})
import study_driver as sd, synthetic_cells as syn, nested_solver as ns
from pathlib import Path
tmp = Path({tmp!r})
sd.APPROVAL = tmp / "STUDY-APPROVAL.json"; sd.APPROVAL.write_text("{{}}")
sd.APPROVAL_CONSUMED = tmp / "STUDY-APPROVAL.consumed.json"
sd.ATTEMPT_MARKER = tmp / "ATTEMPT-SPENT.json"
sd.RESULTS_ROOT = tmp / "results"
sd.common_ledger_path = lambda repo=None: tmp / "gitcommon" / sd.COMMON_LEDGER
(tmp / "gitcommon").mkdir()
pre = sd.load_pre()
mesh, model = syn.chip_cell(h0=0.1, q=3.0, hmax=1.0, split_port=True)
sd.ladder = lambda m: [m, m, m]
pre["configuration"]["level_mesh_digests"] = {{str(h): ns.mesh_digest(mesh) for h in range(3)}}
sd._read_pre = lambda: (pre, "f" * 64)
sd.require_approval = lambda p, now=None, **k: {{}}
sd.unbound_repo_modules = lambda: []
sd.environment_problems = lambda p: []
sd.invocation_problems = lambda p, m=None: []
sd.qmhp_mesh = lambda cfg=None: mesh
sd._model = lambda cfg=None: model
sd.band_baseline = lambda p: pre["consistency_check"]["band"]["values_at_freeze"]
sd.anchor_values = lambda p: {{"C0_F": 1.0, "C1_F": 1.0}}
def busy(meshes, model, write, t0, levels, after_level=None):
    write("level0.json", {{"level": 0}})
    print("READY", flush=True)
    while True:                     # a bytecode loop: the handler runs between bytecodes
        pass
sd.run_levels = busy
sys.exit(sd.main([]))
"""


@pytest.mark.parametrize("sig", ["SIGINT", "SIGTERM", "SIGHUP"])
def test_a_stop_signal_delivered_twice_to_the_process_group_still_leaves_a_sealed_record(tmp_path, sig):
    """Revision 2 lost failure.json and the manifest when GNU timeout forwarded a group
    signal a second time (Ctrl-C: 8 of 8 trials on a bytecode loop). The real
    _enforce_budget, _on_limit, _disarm and failure path, under the declared wrapper."""
    import signal as sg
    import time
    for trial in range(4):
        d = tmp_path / f"t{trial}"
        d.mkdir()
        code = _SIGNAL_CHILD.format(here=str(HERE), tmp=str(d))
        proc = subprocess.Popen(["timeout", "--signal=KILL", "120", sys.executable, "-c", code],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                start_new_session=True, env={**os.environ, **THREADS}, cwd=str(REPO))
        assert proc.stdout.readline().strip() == "READY", proc.stderr.read()[-800:]
        time.sleep(0.05 * trial)
        os.killpg(proc.pid, getattr(sg, sig))
        _, err = proc.communicate(timeout=120)
        assert proc.returncode == 3, (trial, proc.returncode, err[-1500:])
        (rec,) = (d / "results").glob(sd.RECORD_PREFIX + "*")
        assert manifest.verify(rec) == [], trial
        f = _strict_json(rec / "failure.json")
        got = [e["signal"] for e in f["signals_received"]]
        # up to three deliveries: ours, then GNU timeout's forward to the child and again to
        # the whole process group (coreutils cleanup(): send_sig(child), send_sig(0)); the
        # interpreter merges deliveries that arrive before its handler runs
        assert sig in f["error"] and 1 <= len(got) <= 3 and set(got) == {sig}, (trial, got)


def test_the_evidence_writes_are_atomic_and_strict(tmp_path, monkeypatch):
    target = tmp_path / "x.json"
    sd._dump(target, {"nan": float("nan"), "inf": [np.inf, -np.inf], "np": np.float64(2.5), "i": np.int64(3), "b": np.bool_(True)})
    assert _strict_json(target) == {"nan": None, "inf": [None, None], "np": 2.5, "i": 3, "b": True}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["x.json"]

    def interrupted(src, dst):
        raise sd.BudgetExceeded("SIGTERM")

    monkeypatch.setattr(sd.os, "replace", interrupted)
    with pytest.raises(sd.BudgetExceeded):
        sd._dump(tmp_path / "y.json", {"a": 1})
    assert not (tmp_path / "y.json").exists() and (tmp_path / "y.json.partial").is_file()


def test_the_failure_path_survives_memory_exhaustion_by_small_allocations(tmp_path):
    """Revision 1 could leave no manifest when RLIMIT_AS was exhausted by small allocations
    (the frames kept everything alive and the hard limit equalled the soft one)."""
    code = f"""
        import sys, json, types
        sys.path.insert(0, {str(HERE)!r})
        import study_driver as sd, nested_solver as ns, synthetic_cells as syn
        from pathlib import Path
        tmp = Path({str(tmp_path)!r})
        sd.APPROVAL = tmp / "STUDY-APPROVAL.json"; sd.APPROVAL.write_text("{{}}")
        sd.APPROVAL_CONSUMED = tmp / "STUDY-APPROVAL.consumed.json"
        sd.ATTEMPT_MARKER = tmp / "ATTEMPT-SPENT.json"
        sd.RESULTS_ROOT = tmp / "results"
        sd.common_ledger_path = lambda repo=None: tmp / "gitcommon" / sd.COMMON_LEDGER
        (tmp / "gitcommon").mkdir()
        pre = sd.load_pre()
        mesh, model = syn.chip_cell(h0=0.1, q=3.0, hmax=1.0, split_port=True)
        pre["configuration"]["level_mesh_digests"] = {{str(h): ns.mesh_digest(m) for h, m in enumerate(sd.ladder(mesh))}}
        pre["budget"]["memory_GB"] = 1.5
        sd.load_pre = lambda: pre
        sd._read_pre = lambda: (pre, "f" * 64)
        sd.require_approval = lambda p, now=None, **k: {{}}
        sd.unbound_repo_modules = lambda: []
        sd.environment_problems = lambda p: []
        sd.invocation_problems = lambda p, m=None: []
        sd.qmhp_mesh = lambda cfg=None: mesh
        sd._model = lambda cfg=None: model
        sd.band_baseline = lambda p: pre["consistency_check"]["band"]["values_at_freeze"]
        sd.anchor_values = lambda p: {{"C0_F": 1.0, "C1_F": 1.0}}
        def hog(meshes, model, write, t0, levels, after_level=None):
            write("level0.json", {{"level": 0}})
            keep = []
            while True:
                keep.append(bytearray(64 * 1024))
        sd.run_levels = hog
        try:
            sd.execute()
        except sd.AttemptFailed as e:
            print("ATTEMPT_FAILED", "MemoryError" in str(e))
    """
    out = _python(code)
    assert "ATTEMPT_FAILED True" in out.stdout, out.stdout[-500:] + out.stderr[-1500:]
    (rec,) = (tmp_path / "results").glob(sd.RECORD_PREFIX + "*")
    assert (rec / "failure.json").is_file() and manifest.verify(rec) == []


# --- the committed evidence of the preparation --------------------------------------------

#: preflight.json (QMHP geometry and assembly, no solve) was produced by the revision-3
#: study_driver.py below and NOT re-run for revision 4: revision 4 changes only classify(),
#: which the preflight never executes. Both facts are checked here; the AST digest was
#: computed from that revision-3 file (git show 53bac23:.../study_driver.py) and equals the
#: current file's with classify() removed.
PREFLIGHT_STUDY_DRIVER_SHA256 = "ee36a09369abb00c3a9435e625e39617a5105a3b9ff20fd293eada333432fbb3"
PREFLIGHT_STUDY_DRIVER_AST_WITHOUT_CLASSIFY = "fec30d64a0b73167105d06cb599cd193a2534cf348241e9bc09c8c74d47dfbb7"


def _ast_sha256_without(path: Path, names=("classify",)) -> str:
    import ast
    tree = ast.parse(Path(path).read_text())
    tree.body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name in names)]
    return hashlib.sha256(ast.dump(tree).encode()).hexdigest()


def test_the_preflight_evidence_is_valid_for_the_current_code():
    import ast
    assert _ast_sha256_without(HERE / "study_driver.py") == PREFLIGHT_STUDY_DRIVER_AST_WITHOUT_CLASSIFY, (
        "study_driver.py now differs from the preflight's producing code outside classify(): "
        "the preflight must be re-run, which needs approval (it reads the QMHP mesh)")
    tree = ast.parse((HERE / "study_driver.py").read_text())
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    seen, todo = set(), ["preflight"]
    while todo:
        f = todo.pop()
        if f not in seen:
            seen.add(f)
            todo += [n.id for n in ast.walk(fns[f]) if isinstance(n, ast.Name) and n.id in fns]
    assert "classify" not in seen and {"_preflight_level", "ladder", "qmhp_mesh"} <= seen


@pytest.mark.parametrize("name", ["solver_verification.json", "preflight.json", "dry_run.json"])
def test_the_committed_evidence_was_produced_by_the_committed_code_in_the_verified_environment(name, pre):
    ev = _strict_json(HERE / name)
    env = ev["environment"]
    want = {n: _sha(p) for n, p in sd.EVIDENCE_CODE.items()}
    if name == "preflight.json":                        # see PREFLIGHT_STUDY_DRIVER_SHA256
        want["study_driver.py"] = PREFLIGHT_STUDY_DRIVER_SHA256
    assert env["code_sha256"] == want, f"{name} was produced by other code: regenerate it"
    for k in ("python", "numpy", "scipy"):
        assert env[k] == pre["environment"][k], (name, k)
    assert env["longdouble_eps"] < pre["environment"]["longdouble_eps_below"]
    if name == "dry_run.json":
        assert env["threads_env"] == pre["environment"]["threads_env"]


def test_the_committed_solver_verification_passes_every_check():
    v = _strict_json(HERE / "solver_verification.json")
    assert v["qmhp_data_read"] is False and v["solver_settings"] == ns.SOLVER
    for row in v["V1_exact_known_answer"]["rows"]:
        assert row["preconditions_failed"] == [] and row["direct_rel_err_vs_continuum"] < 1e-12
        for start in ("prolonged", "zero"):
            if f"twogrid_{start}" in row:
                t = row[f"twogrid_{start}"]
                assert t["status"] == "CERTIFIED" and t["rel_err_vs_continuum"] < 1e-12
    for name, row in v["V1b_certificate_against_exact_discrete_minimum"].items():
        assert row["within_certificate"] and row["at_or_above_minimum_up_to_evaluation"], name
        assert row["total_bound_nd"] >= row["residual_certificate_nd"] + row["evaluation_bound_nd"] * (1 - 1e-12)
    c = v["V1c_residual_certificate_against_exact_excess"]
    good, bad = c["certificate"], c["negative_control_c_times_10"]
    assert good["bound_covers_exact_excess_at_every_iterate"] and good["lowest_mode"]["bound_covers_exact_excess"]
    assert good["iterates_audited"] >= 10 and 1 < good["lowest_mode"]["margin"] < 10
    assert not bad["lowest_mode"]["bound_covers_exact_excess"], "the negative control must fail"
    v6 = v["V6_evaluation_bound_against_exact_arithmetic"]
    for name, row in v6.items():
        assert row["bound_covers_error"] and row["analytic_terms_cover_extended_error"], name
    assert any(row["negative_control_violates_the_analytic_terms"] for n, row in v6.items() if "shifted" in n)
    for cell, rows in v["V7_assembly_term"].items():
        for row in rows:
            for q in row["problems"].values():
                assert q["estimate_covers_first_order_effect"], (cell, row["level"])
            assert all(r["rho_gershgorin_over_c"] <= ns.RHO_OVER_C_COVERED for r in row["gap"]["problems"].values())
    lb = v["V7_assembly_term"]["layered_box"][2]["problems"]["x"]      # V1's discrepancy, explained
    assert abs(lb["continuum_minus_first_order_effect_rel"]) <= 2 * lb["certified_total_rel"] < abs(lb["direct_rel_err_vs_continuum"])
    for cell in ("V2_level2_small", "V2_level2_medium"):
        c = v[cell]
        assert c["preconditions_failed"] == [[], [], []]
        for kind in ns.KINDS:
            k = c[kind]
            assert k["twogrid"]["status"] == "CERTIFIED" and k["agreement"]["within_bounds"]
            assert k["twogrid_bound_rel"] < 1e-9 and k["direct_bound_rel"] < 1e-9
            assert all(abs(x - 1) < 1e-9 for x in k["port_voltage"])
    for k, a in v["V3_every_iterate"].items():
        assert a["bound_holds_at_every_iterate"] and a["every_iterate_energy_at_or_above_direct"], k
    c = v["V4_consistency"]
    assert c["small"]["C_bit_identical_to_static_capacitance"] and c["small"]["Cprime_bit_identical_to_spectral"]
    assert c["medium"]["C_bit_identical_to_static_capacitance"] and c["medium"]["Cprime_bit_identical_to_spectral"]
    d = c["dense_sheet_identity_small_cell"]
    assert abs(d["N_minus_1"]) < 1e-9 and abs(d["sum_p_over_lambda_over_L_Cprime_minus_1"]) < 1e-9
    n = v["V5_negative_controls"]
    assert not n["a_truncated"]["certified_at_1e-9"] and n["a_truncated"]["error_within_bound"]
    assert n["b_precondition"]["grounded_cell"]["poincare_step_A_ge_cM_holds"]
    assert n["b_precondition"]["grounded_cell"]["certificate_covers_excess"]
    assert n["b_precondition"]["bar_free_sides"]["preconditions_failed"]
    assert not n["b_precondition"]["bar_free_sides"]["poincare_step_A_ge_cM_holds"]
    assert not n["b_precondition"]["bar_free_sides"]["certificate_covers_excess"]
    assert n["c_non_nested_P"]["galerkin_identity_rel"] > 1e-3 and n["c_non_nested_P"]["status"] == "CERTIFIED"
    assert n["d_indefinite_preconditioner"]["status"] == "BREAKDOWN"
    assert n["e_zero_initial_guess"]["status"] == "CERTIFIED"
    assert n["f_perturbed"]["increase_positive"] and n["f_perturbed"]["bound_covers_increase"]
    assert n["g_folded_mesh"]["preconditions_failed"] and not n["g_folded_mesh"]["certificate_covers_excess"]
    h = n["h_stagnation_rule"]
    assert h["inf_30_residual_falling_then_converging"] == {"status": "CERTIFIED", "iterations": 32}
    assert h["inf_flat_residual"] == {"status": "STAGNATED", "iterations": 21}
    assert h["finite_flat"] == {"status": "STAGNATED", "iterations": 21}
    assert h["stuck_solve_masked_preconditioner"]["status"] == "STAGNATED"
    assert h["stuck_solve_masked_preconditioner"]["finite_checks"] == 0 and h["stuck_solve_masked_preconditioner"]["iterations"] < 200


def test_the_committed_preflight_solved_nothing_and_found_the_study_well_posed(pre):
    p = _strict_json(HERE / "preflight.json")
    assert p["linear_solves"] == 0 and p["mesh_sha256"] == pre["configuration"]["mesh_sha256"]
    t = pre["integrity"]
    for h, lv in p["levels"].items():
        assert lv["mesh_digest"] == pre["configuration"]["level_mesh_digests"][h]
        assert lv["preconditions_failed"] == []
        f = lv["mesh_facts"]
        assert f["max_face_multiplicity"] == 2 and f["every_interior_face_separates_its_tetrahedra"]
        assert f["every_boundary_face_on_the_box_surface"] and abs(f["volume_sum_over_box_minus_1"]) < t["tiling_volume_tol"]
        sizes = pre["configuration"]["level_sizes_tets_nodes_unknownsC_unknownsCprime_nnzA"][h]
        assert sizes == [lv["n_tets"], lv["n_nodes"], lv["problems"]["C"]["n_unknowns"],
                         lv["problems"]["Cprime"]["n_unknowns"], lv["problems"]["C"]["nnz_A"]]
        g = lv["assembly_gap_estimate"]
        assert g == pre["configuration"]["assembly_gap_preflight"]["levels"][h], "the pre-declaration quotes it exactly"
        assert pre["configuration"]["assembly_gap_preflight"]["abs_sum_nd"][h] == g["abs_sum_nd"]
        for kind in ns.KINDS:
            assert g["problems"][kind]["rho_gershgorin_over_c"] <= ns.RHO_OVER_C_COVERED
            q = lv["problems"][kind]
            assert q["certificate_floor_proxy_nd"] < 1e-3 * t["certificate_rel_tol"]
            # a margin of at least 100 to the tolerance for any energy >= 1 (E_1 = 2.32 on record)
            assert q["evaluation_matvec_term_proxy_nd"] < 1e-2 * t["certificate_rel_tol"]
            if h != "0":
                assert q["galerkin_identity_rel"] < t["galerkin_identity_rel_tol"]
                assert q["fixed_rows_from_free_coarse_nnz"] == 0


def test_the_committed_dry_run_fits_the_budget_and_matches_the_stated_estimate(pre):
    d = _strict_json(HERE / "dry_run.json")
    b = pre["budget"]
    assert d["qmhp_data_read"] is False and d["cell"] == sd.DRY_RUN_CELL
    assert d["analysis_of_the_synthetic_levels"]["integrity_failures"] == []
    assert d["limits"]["address_space_bytes"] == int(b["memory_GB"] * 1024 ** 3)
    r = d["resources"]
    assert r["wall_s"] < 0.25 * b["wall_cap_minutes"] * 60 and r["cpu_s"] < 0.25 * b["cpu_minutes"] * 60
    assert r["peak_address_space_MB"] * 1024 ** 2 < 0.75 * b["memory_GB"] * 1024 ** 3
    lv2 = pre["configuration"]["level_sizes_tets_nodes_unknownsC_unknownsCprime_nnzA"]["2"]
    assert d["per_level"][2]["n_tets"] > lv2[0], "the stand-in must be at least QMHP-sized"
    assert d["per_level"][2]["problems"]["C"]["n_unknowns"] > lv2[2]
    m = b["estimate"]["stand_in_measured"]                 # quoted exactly, not from another run
    assert m["wall_s"] == round(r["wall_s"], 1) and m["cpu_s"] == round(r["cpu_s"], 1)
    assert m["peak_rss_MB"] == round(r["max_rss_MB"]) and m["peak_address_space_MB"] == round(r["peak_address_space_MB"])
    for k in ns.KINDS:
        t = d["level2_pcg_timing"][k]
        assert m["level2"][k] == {"iterations": t["iterations"], "status": t["status"],
                                  "setup_wall_s": round(t["setup_wall_s"], 2),
                                  "wall_s_per_iteration": round(t["wall_s_per_iteration"], 4)}
    assert set(d["pcg_histories"]) == {"level2-C", "level2-Cprime", "level1-C-crosscheck", "level1-Cprime-crosscheck"}
    w = d["evidence_writes"]                              # the per-solve writes, at full size
    assert w["files"] == [n for n in RAW if n != "consistency-level0.json"]
    assert w["manifest_verify"] == [] and w["unexpected_files"] == [] and w["strict_json"] is True


# --- the pre-declaration and the code agree -------------------------------------------------

def test_the_predeclaration_is_frozen_and_complete(pre):
    assert _sha(HERE / "predeclaration.json") == PREDECLARATION_SHA256
    for key in ("question", "baseline", "already_known_before_execution", "configuration",
                "measured_quantities", "independent_variable", "controlled_variables", "method",
                "environment", "integrity", "diagnostics_not_integrity", "reproduction",
                "classification", "consistency_check", "one_attempt", "not_a_target",
                "no_combination", "budget", "stop_conditions", "expected_evidence",
                "cannot_establish", "revision", "synthetic_expectations"):
        assert key in pre, key
    assert pre["status"].startswith("PREPARED. NOT APPROVED. NOT EXECUTED. Revision 4.")
    assert pre["revision"]["number"] == 4 and "3270469" in pre["revision"]["previous"]
    assert "9aa951f" in pre["revision"]["previous"] and "864c0ba" in pre["revision"]["previous"]
    rules = pre["classification"]["rules"]
    assert "certified range" in rules["CONVERGED"] and "tau_converged" in rules["UNRESOLVED"]
    assert pre["classification"]["tau_converged"] == 0.05
    oa = pre["one_attempt"]
    assert {"C-1", "C-2", "C-3"} <= set(oa["residuals"])
    assert "ATTEMPT-LEDGER-NOTE.json" in oa["preservation_before_the_environment_is_discarded"]


def test_the_predeclaration_states_exactly_what_the_code_does(pre):
    cfg = pre["configuration"]
    for k, v in sd.CONFIG.items():
        assert cfg[k] == v, k
    assert pre["method"]["solver_settings"] == ns.SOLVER
    t = pre["integrity"]
    assert t["port_geometry_tol"] == ns.PORT_GEOMETRY_TOL and t["tiling_volume_tol"] == ns.TILING_VOLUME_TOL
    assert pre["diagnostics_not_integrity"]["gauss_seidel_probe_rel_tol_reference"] == ns.GS_PROBE_TOL
    b = pre["budget"]
    assert f"timeout --signal=KILL {int(b['wall_cap_minutes'] * 60) + 60} " in b["invocation"]
    assert all(f"{k}={v}" in b["invocation"] for k, v in pre["environment"]["threads_env"].items())
    assert b["attempts"] == 1 and "no workflow" in b["invocation"]
    assert pre["reproduction"]["sha256"] == {n: ANCHOR_UNCHANGED[f"{pre['reproduction']['record']}/{n}"]
                                             for n in pre["reproduction"]["sha256"]}
    assert set(pre["consistency_check"]["consequence"]) == {"CONSISTENT", "INCONSISTENT-LOW",
                                                            "INCONSISTENT-HIGH", "UNRESOLVED", "UNQUALIFIED"}
    cons = pre["consistency_check"]["consequence"]
    for cause in ("static C' implementation", "N != 1", "p definition", "weak-mode p", "identity as applied"):
        assert cause in cons["INCONSISTENT-LOW"] and cause in cons["INCONSISTENT-HIGH"], cause
    assert ns.RHO_OVER_C_COVERED == 5e-4 and "RHO_OVER_C_COVERED = 5e-4" in pre["method"]["certificate"]
    assert f"BOUND_SAFETY = {ns.BOUND_SAFETY}" in pre["method"]["certificate"]
    current = json.dumps({k: v for k, v in pre.items() if k != "revision"})   # the history may quote it
    assert "about 1e-14" not in current, "the assembly term is estimated, not asserted"
    assert "SIGINT" in b["enforcement"] and "FIRST stop signal raises" in b["enforcement"]


def test_the_review_records_are_kept():
    r = _strict_json(HERE / "review" / "review_864c0ba.json")
    assert r["snapshot"].startswith("864c0baef389bbe0a45345b7b27cf74f8afd17c4")
    assert r["summary_counts"] == {"blocking": 0, "major_confirmed": 10, "minor": 25}
    r = _strict_json(HERE / "review" / "review_9aa951f.json")
    assert r["snapshot"].startswith("9aa951fae23c413c47518e2c4f3bfed8096c4f4d")
    assert r["summary_counts"] == {"blocking": 0, "major_new_confirmed": 3, "major_revision1_partly_fixed_confirmed": 2,
                                   "minor_new": 21, "minor_revision1_partly_fixed_confirmed": 3,
                                   "revision1_fixed": 30, "revision1_partly_fixed": 5}
    found = sorted(f["id"] for lens in r["lenses"] for f in lens["review"]["findings"])
    assert len(found) == 24 and {"R2-1", "R2-2", "R2-CC-1"} <= set(found)


def test_the_withdrawn_paired_test_is_preserved_unchanged():
    for rel, digest in WITHDRAWN_UNCHANGED.items():
        assert _sha(REPO / rel) == digest, rel
    assert (REPO / "experiments" / "static-band-pairing" / "WITHDRAWN.json").is_file()


def test_the_executed_record_and_the_existing_method_are_unchanged():
    for rel, digest in ANCHOR_UNCHANGED.items():
        assert _sha(REPO / rel) == digest, rel


def test_nothing_here_can_launch_anything():
    import ast
    for p in HERE.glob("*.py"):
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                assert not name.startswith(("subprocess.", "os.system", "os.popen", "os.exec")), (p.name, name)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                assert not any(m.split(".")[0] in ("subprocess", "models", "orchestrator", "solvers")
                               or "palace" in m.lower() for m in mods), (p.name, mods)


def test_every_new_source_file_carries_the_approved_header():
    for p in [*HERE.glob("*.py"), Path(__file__)]:
        head = p.read_text().splitlines()[:3]
        assert any("Copyright (c) 2026 Brodie Duncan. All rights reserved." in h for h in head), p


def test_the_report_states_the_status_and_keeps_proof_and_model_apart():
    text = DOC.read_text()
    assert "PREPARED, NOT APPROVED, NOT EXECUTED" in text
    for h in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6.", "## 7.", "## 8."):
        assert h in text, h
    for phrase in ("model-based", "relative to the assembled operator", "UNAVAILABLE",
                   "Sprime_static_identity_not_confirmed", "revision 4", "SIGKILL", "git common directory",
                   "ATTEMPT-LEDGER-NOTE.json", "within its certified error of τ",
                   "STUDY-APPROVAL.consumed.json", "not conservative for the certificate"):
        assert phrase in text, phrase
    for stale in ("about 1e-14", "exact execution path", "10^2-10^4", "four certificates", "so it is tight"):
        assert stale not in text, stale
