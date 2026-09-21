"""The direct first-moment diagnostic: prepared and verified on fixtures, not executed."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FMD = REPO_ROOT / "experiments" / "first-moment-diagnostic"
DOC = REPO_ROOT / "docs" / "coupled-candidate" / "first-moment-diagnostic.md"
PATCH = REPO_ROOT / "docker" / "patches" / "first-moment-diagnostic.patch"
DOCKERFILE = REPO_ROOT / "docker" / "palace-first-moment.Dockerfile"
PROD_DOCKERFILE = REPO_ROOT / "docker" / "palace.Dockerfile"
APPROVAL = REPO_ROOT / ".github" / "ladder-approval.json"
N2R_SOLVED = (REPO_ROOT / "results" / "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z" / "L2"
              / "solver" / "config.json")

# Pinned: the production Dockerfile and the spent PO1 approval are untouched by this
# preparation, and the patch is the reviewed one.
PROD_DOCKERFILE_SHA256 = "ae61175a4237cfed043d0df47126080215fa06c42acd897a53107b2c99fc88a9"
APPROVAL_SHA256 = "be5cbe1a03882fd508fd2837751a95f111a48fc66a8f6d6485170448142f01bc"
PATCH_SHA256 = "31b5bd29de05c81747841287e33f7b943a9669bea55ea01074e9e9326de872db"
N2R_CONFIG_SHA256 = "79304b5f8bd7c67741e995ec7ae7880b41dfcee23d6c3c12984f5baba8c1f33f"
PALACE_COMMIT = "a61c8cbe0cacf496cde3c62e93085fae0d6299ac"

EXPECTED_PATCHED_FILES = {
    "palace/drivers/CMakeLists.txt",
    "palace/drivers/firstmomentsolver.cpp",
    "palace/drivers/firstmomentsolver.hpp",
    "palace/main.cpp",
    "palace/models/lumpedportoperator.cpp",
    "palace/models/lumpedportoperator.hpp",
    "palace/utils/configfile.cpp",
    "palace/utils/configfile.hpp",
    "palace/utils/iodata.cpp",
}


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _norm(text: str) -> str:
    lines = [ln.lstrip().removeprefix("> ").removeprefix(">") for ln in text.splitlines()]
    return " ".join(" ".join(lines).split())


def _same_json(a, b) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same_json(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same_json(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b or abs(a - b) <= 1e-9 * max(abs(a), abs(b)) or (abs(a) < 1e-11 and abs(b) < 1e-11)
    return a == b


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, FMD / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(FMD))
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rm():
    return _load("reference_model")


@pytest.fixture(scope="module")
def prep():
    return _load("prepare")


@pytest.fixture(scope="module")
def patch_text() -> str:
    return PATCH.read_text()


@pytest.fixture(scope="module")
def proposal() -> dict:
    return json.loads((FMD / "proposal.json").read_text())


@pytest.fixture(scope="module")
def fixture_eval() -> dict:
    return json.loads((FMD / "fixture_evaluation.json").read_text())


# --- 1. the constrained mass operator ------------------------------------------------

def test_diag_one_padding_with_a_zeroed_rhs_is_the_free_dof_form(rm):
    rng = np.random.default_rng(1)
    for _ in range(10):
        fx = rm.Fixture(rng)
        f = fx.f_true
        a_free = rm.first_moment_free(fx.M, f, fx.dbc, fx.L)
        a_pad = rm.first_moment_padded(fx.M, f, fx.dbc, fx.L, "DIAG_ONE", True)
        assert a_free > 0
        assert abs(a_pad - a_free) <= 1e-13 * a_free
        # the padded operator is SPD; the free block is M restricted; the rest is identity
        Mp = rm.padded_mass(fx.M, fx.dbc, "DIAG_ONE")
        assert np.allclose(Mp[np.ix_(fx.free, fx.free)], fx.M[np.ix_(fx.free, fx.free)])
        assert np.allclose(Mp[np.ix_(fx.dbc, fx.dbc)], np.eye(len(fx.dbc)))
        assert np.allclose(Mp[np.ix_(fx.dbc, fx.free)], 0.0)
        assert np.linalg.eigvalsh(Mp).min() > 0


def test_padding_without_zeroing_the_rhs_adds_exactly_the_boundary_term(rm):
    rng = np.random.default_rng(2)
    seen_nonzero = False
    for _ in range(10):
        fx = rm.Fixture(rng)
        f = fx.f_true
        a_free = rm.first_moment_free(fx.M, f, fx.dbc, fx.L)
        a_bad = rm.first_moment_padded(fx.M, f, fx.dbc, fx.L, "DIAG_ONE", False)
        art = float(f[fx.dbc] @ f[fx.dbc]) / fx.L
        seen_nonzero |= art > 0
        assert abs((a_bad - a_free) - art) <= 1e-12 * max(art, a_free)
    assert seen_nonzero, "the fixture must put functional weight on essential dofs"


def test_diag_zero_padding_is_singular_so_the_eigensolver_mass_is_not_solvable(rm):
    rng = np.random.default_rng(3)
    for _ in range(5):
        fx = rm.Fixture(rng)
        assert rm.first_moment_padded(fx.M, fx.f_true, fx.dbc, fx.L, "DIAG_ZERO", True) is None
        Mz = rm.padded_mass(fx.M, fx.dbc, "DIAG_ZERO")
        assert np.linalg.matrix_rank(Mz) == fx.n_true - len(fx.dbc)


def test_the_driver_solves_the_free_form_on_diag_one_with_the_rhs_zeroed(patch_text):
    drv = patch_text.split("palace/drivers/firstmomentsolver.cpp", 1)[1]
    assert "GetMassMatrix<Operator>(Operator::DIAG_ONE)" in drv
    assert "DIAG_ZERO" not in drv
    i_zero = drv.index("linalg::SetSubVector(f, dbc_tdof_list, 0.0);")
    i_solve = drv.index("ksp.Mult(f, x);")
    assert i_zero < i_solve
    for forbidden in ("pseudoinverse", "pinv", "lumping", "Lumping", "MassLump"):
        assert forbidden not in drv
    # the essential part of the solution is measured and reported, not assumed
    assert "SolutionEssentialNorm" in drv and "SetSubVector(xd, dbc_tdof_list, x)" in drv


# --- 2. port functional access ------------------------------------------------------

def test_dual_assembly_reproduces_get_voltage_for_any_complex_field(rm):
    rng = np.random.default_rng(4)
    for _ in range(10):
        fx = rm.Fixture(rng)
        assert fx.n_loc > fx.n_true, "shared dofs make P^T v a genuine dual assembly"
        f = rm.dual_assemble(fx.P, fx.v_loc)
        assert not np.allclose(f, fx.v_loc[: fx.n_true]), "P^T v differs from v truncated"
        E = rng.normal(size=fx.n_true) + 1j * rng.normal(size=fx.n_true)
        Vp = rm.voltage_palace(fx.v_loc, fx.P, E)
        assert abs(rm.voltage_from_functional(f, E) - Vp) <= 1e-13 * abs(Vp)


def test_free_restricted_functional_matches_get_voltage_only_on_pec_constrained_fields(rm):
    rng = np.random.default_rng(5)
    fx = rm.Fixture(rng)
    f = rm.restrict_to_free(fx.f_true, fx.dbc)
    E = rng.normal(size=fx.n_true) + 1j * rng.normal(size=fx.n_true)
    Ec = E.copy()
    Ec[fx.dbc] = 0.0
    Vc = rm.voltage_palace(fx.v_loc, fx.P, Ec)
    assert abs(rm.voltage_from_functional(f, Ec) - Vc) <= 1e-13 * abs(Vc)
    Vu = rm.voltage_palace(fx.v_loc, fx.P, E)
    assert abs(rm.voltage_from_functional(f, E) - Vu) > 1e-6 * abs(Vu)


def test_a_phase_rotation_rotates_the_voltage_and_leaves_its_modulus(rm):
    rng = np.random.default_rng(6)
    fx = rm.Fixture(rng)
    f = rm.restrict_to_free(fx.f_true, fx.dbc)
    E = rng.normal(size=fx.n_true) + 1j * rng.normal(size=fx.n_true)
    E[fx.dbc] = 0.0
    for theta in (0.3, 1.7, math.pi, 5.9):
        V0 = rm.voltage_from_functional(f, E)
        V1 = rm.voltage_from_functional(f, E * np.exp(1j * theta))
        assert abs(V1 - V0 * np.exp(1j * theta)) <= 1e-13 * abs(V0)
        assert abs(abs(V1) - abs(V0)) <= 1e-13 * abs(V0)


def test_the_patch_adds_one_accessor_that_reuses_the_exact_voltage_form(patch_text):
    hpp = patch_text.split("palace/models/lumpedportoperator.hpp", 1)[1].split("diff --git", 1)[0]
    cpp = patch_text.split("palace/models/lumpedportoperator.cpp", 1)[1].split("diff --git", 1)[0]
    assert "void GetVoltageFunctional(mfem::ParFiniteElementSpace &nd_fespace, mfem::Vector &f) const;" in hpp
    assert "InitializeLinearForms(nd_fespace);" in cpp
    assert "nd_fespace.GetProlongationMatrix()->MultTranspose(*v, f);" in cpp
    assert "f.SetSize(nd_fespace.GetTrueVSize());" in cpp
    # nothing existing is removed anywhere in the patch except the two enum-list tails
    removed = [ln[1:] for ln in patch_text.splitlines()
               if ln.startswith("-") and not ln.startswith("---")]
    assert sorted(removed) == sorted([
        "    TRANSIENT",
        '                            {ProblemData::Type::TRANSIENT, "Transient"}})'])


def test_the_driver_checks_the_functional_against_get_voltage_on_a_complex_field(patch_text):
    drv = patch_text.split("palace/drivers/firstmomentsolver.cpp", 1)[1]
    assert "GridFunction E(nd_fespace, true);" in drv
    assert "linalg::SetRandom(comm, Et, opts.seed);" in drv
    assert "linalg::SetSubVector(Et, dbc_tdof_list, 0.0);" in drv
    assert "port->GetVoltage(E)" in drv
    assert "MFEM_VERIFY(rel < check_functional_tol" in drv
    assert "port->GetVoltageFunctional(nd_fespace.Get(), f);" in drv


# --- 3. internal units and normalisation ---------------------------------------------

def test_unit_scales_follow_the_pinned_iodata_and_match_the_n2r_log(rm, prep):
    sc = rm.unit_scales(4.0e-3)
    assert abs(sc["tc_ns"] - 1.0e9 * 4.0e-3 / rm.C0) < 1e-18
    assert abs(sc["tc_ns"] - 0.01334256380791072) < 1e-15
    assert abs(sc["FrequencyScale_GHz"] - 1.0 / (2 * math.pi * sc["tc_ns"])) < 1e-12
    assert abs(sc["InductanceScale_H"] - rm.MU0 * 4.0e-3) < 1e-24
    assert abs(rm.inductance_nd(prep.N2R_PORT_L_H, 4.0e-3) - 20.582047285188583) < 1e-9
    log = prep.N2R_LOG.read_text()
    assert re.search(r"L₀ = 4\.000e-03 m, t₀ = 1\.334e-02 ns", log)
    s = prep.scales_from_log()
    assert s["printed_by_palace"] == {"Lc_m": 4.0e-3, "tc_ns": 1.334e-2}


def test_a_ghz2_is_a_nd_over_two_pi_tc_squared(rm):
    tc = rm.unit_scales(4.0e-3)["tc_ns"]
    for A in (0.0165, 1.0, 2.351511939494728):
        nd = rm.a_nd_from_ghz2(A, tc)
        assert abs(rm.a_ghz2_from_nd(nd, tc) - A) <= 1e-15 * A
        assert abs(nd - A * (2 * math.pi * tc) ** 2) <= 1e-15 * nd
    # a mode at f GHz has lambda_nd = (2 pi f tc)^2, so sum p lambda / (2 pi tc)^2 = sum p f^2
    f, p = np.array([3.9, 7.1, 12.3]), np.array([0.5, 0.3, 0.2])
    A_nd = float((p * rm.lambda_nd_from_f_ghz(f, tc)).sum())
    assert abs(rm.a_ghz2_from_nd(A_nd, tc) - float((p * f ** 2).sum())) < 1e-13


def test_palace_epr_equals_the_absolute_square_form_with_its_half_energy(rm):
    rng = np.random.default_rng(7)
    fx = rm.Fixture(rng)
    f = rm.restrict_to_free(fx.f_true, fx.dbc)
    lam, Em = rm.constrained_eigenbasis(fx.K, fx.M, fx.dbc)
    keep = np.nonzero(lam > 1e-9 * lam.max())[0]
    for m in rng.choice(keep, size=6, replace=False):
        c = rng.normal() + 1j * rng.normal()
        E = Em[:, m] * c
        V = rm.voltage_from_functional(f, E)
        p_pal = rm.epr_palace(V, fx.L, math.sqrt(lam[m]), rm.electric_energy_palace(fx.M, E))
        p_abs = rm.epr_from_functional(f, fx.L, lam[m], fx.M, E)
        assert abs(abs(p_pal) - p_abs) <= 1e-12 * p_abs
        p_unit = rm.epr_from_functional(f, fx.L, lam[m], fx.M, Em[:, m].astype(complex))
        assert abs(p_abs - p_unit) <= 1e-9 * p_unit, "phase and scale invariant"
        # with E^H M E = 1 (Palace's RescaleEigenvectors), p = (q^H E)^2 / lambda
        q = f / math.sqrt(fx.L)
        assert abs(p_unit - (q @ Em[:, m]) ** 2 / lam[m]) <= 1e-12 * p_unit


def test_the_driver_keeps_internal_units_internal(patch_text):
    drv = patch_text.split("palace/drivers/firstmomentsolver.cpp", 1)[1]
    assert "const double L_nd = port->L;" in drv
    assert "const double A_nd = fx / L_nd;" in drv
    assert "iodata.DimensionalizeValue(IoData::ValueType::FREQUENCY, 1.0)" in drv
    assert "const double A_GHz2 = A_nd * freq_scale * freq_scale;" in drv
    # henries appear only as an output conversion of L_nd, never inside the computation
    assert drv.count("ValueType::INDUCTANCE") == 2
    assert "mu0" not in drv and "1e-7" not in drv


# --- 4. null space and comparison scope ----------------------------------------------

def test_the_functional_lies_in_range_of_the_port_stiffness_and_annihilates_ker_k(rm):
    rng = np.random.default_rng(8)
    for _ in range(8):
        fx = rm.Fixture(rng)
        free = fx.free
        f = fx.f_true[free]
        Kp = fx.K_port[np.ix_(free, free)]
        Kf = fx.K[np.ix_(free, free)]
        # f in range(K_port): least-squares residual vanishes
        y, *_ = np.linalg.lstsq(Kp, f, rcond=None)
        assert np.linalg.norm(Kp @ y - f) <= 1e-10 * np.linalg.norm(f)
        w = np.linalg.eigvalsh(Kf)
        assert int((w < 1e-10 * w.max()).sum()) >= 1, "K has a kernel on the free dofs"
        assert rm.kernel_annihilation(Kf, f) <= 1e-12


def test_same_quadrature_gives_k_port_ge_qq_and_a_mismatched_rule_breaks_it(rm):
    rng = np.random.default_rng(9)
    worst_same, worst_mismatch = math.inf, math.inf
    for _ in range(12):
        fx = rm.Fixture(rng)
        free = fx.free
        f = fx.f_true[free]
        Kp = fx.K_port[np.ix_(free, free)]
        scale = np.linalg.eigvalsh(Kp).max()
        worst_same = min(worst_same, rm.port_inequality_min_eig(Kp, f, fx.L) / scale)
        a2 = fx.a * rng.uniform(0.2, 1.8, size=fx.a.size)
        a2 *= fx.a.sum() / a2.sum()
        f2 = rm.dual_assemble(fx.P, fx.Q.T @ (a2 * fx.c))[free]
        worst_mismatch = min(worst_mismatch, rm.port_inequality_min_eig(Kp, f2, fx.L) / scale)
    assert worst_same >= -1e-12
    assert worst_mismatch < -1e-3, "the inequality needs the same weights, not just points"


def test_parseval_over_the_complete_constrained_basis_equals_the_free_solve(rm):
    rng = np.random.default_rng(10)
    for _ in range(8):
        fx = rm.Fixture(rng)
        f = rm.restrict_to_free(fx.f_true, fx.dbc)
        lam, Em = rm.constrained_eigenbasis(fx.K, fx.M, fx.dbc)
        p_all, p_nz = rm.parseval_first_moment(f, fx.L, lam, Em)
        a_free = rm.first_moment_free(fx.M, fx.f_true, fx.dbc, fx.L)
        assert abs(p_all - a_free) <= 1e-12 * a_free
        assert abs(p_nz - a_free) <= 1e-12 * a_free, "zero modes carry no weight"


def test_the_reference_model_record_is_reproduced_and_within_tolerance():
    j = json.loads((FMD / "reference_model.json").read_text())
    w = j["worst_case"]
    for k in ("dual_assembly_vs_GetVoltage", "padded_DIAG_ONE_zeroed_rhs_vs_free",
              "parseval_all_modes_vs_free_solve", "parseval_nonzero_modes_vs_free_solve",
              "epr_palace_vs_absolute_square", "A_phase_invariance", "unit_roundtrip_A_GHz2",
              "padded_DIAG_ONE_unzeroed_rhs_minus_free_vs_sum_f_dbc2_over_L"):
        assert w[k] < 1e-12, k
    assert w["kernel_annihilation_same_points"] < 1e-12
    assert w["kernel_dim_min"] >= 1
    assert w["K_port_minus_qq_min_eig_same_rule_min"] >= -1e-12
    assert w["K_port_minus_qq_min_eig_mismatched_rule_min"] < -1e-3
    assert w["padded_DIAG_ZERO_singular_in_every_trial"] is True
    assert w["free_restricted_functional_mismatch_when_E_dbc_nonzero_min"] > 1e-6
    assert j["hard_caps"] == {"dof": 250000, "wall_s": 2700,
                              "meaning": "hard caps on any execution, not runtime promises"}


def test_the_driver_checks_k_ge_qq_without_any_eigenbasis(patch_text):
    drv = patch_text.split("palace/drivers/firstmomentsolver.cpp", 1)[1]
    assert "GetStiffnessMatrix<Operator>(Operator::DIAG_ONE)" in drv
    assert "K->Mult(u, Ku);" in drv and "const double qu2 = fu * fu / L_nd;" in drv
    assert "MFEM_VERIFY(min_gap >= -1.0e-10" in drv
    for forbidden in ("EigenvalueSolver", "slepc", "arpack", "DivFreeSolver", "Driven", "omega"):
        assert forbidden not in drv, forbidden


# --- 5. outputs and numerical checks -------------------------------------------------

def test_every_record_key_is_written_by_the_driver(rm, patch_text):
    drv = patch_text.split("palace/drivers/firstmomentsolver.cpp", 1)[1]
    for k, subs in rm.RECORD_KEYS.items():
        assert f'"{k}"' in drv, k
        for s in subs:
            assert f'"{s}"' in drv, f"{k}.{s}"
    for extra in ("WallTime_s", "MaxRSS_MB", "RelativeResidual", "Converged", "Free",
                  "Essential", "Lc_m", "tc_ns", "A_nd", "A_GHz2", "ResidualBound_GHz2"):
        assert f'"{extra}"' in drv


def test_the_evaluator_recovers_a_known_omitted_moment_within_its_bound(fixture_eval):
    ev, truth = fixture_eval["evaluator"], fixture_eval["truth"]
    assert ev["all_checks_passed"] is True
    assert ev["error_within_bound"] is True
    assert abs(ev["error_vs_truth_nd"]) <= ev["residual_bound_nd"]
    assert truth["omitted_first_moment_exact_nd"] > 0
    assert "qualified by the residual bound" in ev["interpretation"]
    good = fixture_eval["full_evaluation_of_the_good_record"]
    assert good["E_C"] == "UNAVAILABLE" and good["g"] == "UNAVAILABLE"
    assert good["N"] == "not measured by this diagnostic"


def test_broken_records_are_unqualified_and_a_sloppy_solve_fails_the_residual_check(fixture_eval):
    for what, r in fixture_eval["broken_records_are_unqualified"].items():
        assert r["all_checks_passed"] is False, what
        assert r["interpretation"].startswith("UNQUALIFIED"), what
        assert len(r["failed"]) == 1, what
    s = fixture_eval["sloppy_solve"]
    assert s["all_checks_passed"] is False
    assert s["failed"] == ["independent relative residual <= 1e-12"]


def test_a_difference_inside_the_bound_is_not_called_a_small_tail(rm):
    rng = np.random.default_rng(11)
    fx = rm.Fixture(rng)
    rec = rm.synthetic_record(fx, 4.0e-3, residual_scale=1e-13, seed=11)
    # a saved moment equal to the direct one up to far less than the bound
    res = rm.evaluate(rec, rec["A"]["A_GHz2"] * (1 - 1e-18), expected_dofs=fx.n_true)
    assert res["all_checks_passed"]
    nq = res["numerical_qualification"]
    assert nq["difference_exceeds_residual_bound"] is False
    assert any("not resolved" in s for s in res["not_established_here"])
    assert "calculation error" in nq["bound_statement"] or "calculation-error" in " ".join(res["not_established_here"])


def test_the_evaluator_enforces_the_hard_caps_and_the_space_identity(rm):
    rng = np.random.default_rng(12)
    fx = rm.Fixture(rng)
    base = rm.synthetic_record(fx, 4.0e-3, seed=12)
    saved = base["A"]["A_GHz2"] * 0.9
    assert rm.evaluate(base, saved, expected_dofs=fx.n_true)["all_checks_passed"]
    slow = json.loads(json.dumps(base))
    slow["Resources"]["WallTime_s"] = 2700.5
    assert not rm.evaluate(slow, saved)["all_checks_passed"]
    big = json.loads(json.dumps(base))
    big["Dofs"]["True"] = 250001
    big["Dofs"]["Free"] = 250001 - big["Dofs"]["Essential"]
    assert not rm.evaluate(big, saved)["all_checks_passed"]
    other = rm.evaluate(base, saved, expected_dofs=fx.n_true + 1)
    assert not other["all_checks_passed"]
    assert any("same true-dof count" in c["check"] and not c["passed"] for c in other["checks"])
    incomplete = json.loads(json.dumps(base))
    del incomplete["A"]["ResidualBound_GHz2"]
    assert rm.validate_record(incomplete) == ["A.ResidualBound_GHz2"]
    assert rm.evaluate(incomplete, saved)["interpretation"].startswith("UNQUALIFIED")


# --- 6. preparation only -------------------------------------------------------------

def test_prepare_writes_exactly_the_declared_delta(prep):
    assert _sha256(N2R_SOLVED) == N2R_CONFIG_SHA256
    n2r = json.loads(N2R_SOLVED.read_text())
    cand = json.loads((FMD / "config.candidate.json").read_text())
    assert cand == prep.build_candidate(n2r)
    assert cand["Problem"]["Type"] == "FirstMoment"
    assert "Eigenmode" not in cand["Solver"]
    assert cand["Solver"]["FirstMoment"] == prep.FIRST_MOMENT_BLOCK
    back = json.loads(json.dumps(cand))
    back["Problem"]["Type"] = "Eigenmode"
    del back["Solver"]["FirstMoment"]
    back["Solver"]["Eigenmode"] = n2r["Solver"]["Eigenmode"]
    assert back == n2r, "everything else is N2R's, byte for byte"
    delta = (FMD / "config.delta.txt").read_text()
    assert '-    "Type": "Eigenmode",' in delta and '+    "Type": "FirstMoment",' in delta
    minus = [ln for ln in delta.splitlines() if ln.startswith("-") and not ln.startswith("---")]
    plus = [ln for ln in delta.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    assert len(minus) == 7 and len(plus) == 9, (minus, plus)
    assert "Mesh" not in delta and "Boxes" not in delta and "PEC" not in delta


def test_the_scripts_are_offline_deterministic_and_cannot_launch_anything():
    names = ("reference_model.py", "prepare.py", "evaluate_record.py")
    for name in names:
        src = (FMD / name).read_text()
        for forbidden in ("requests", "urllib", "socket", "http://", "https://",
                          "subprocess", "os.system", "Popen", "podman"):
            assert forbidden not in src, (name, forbidden)
        tree = ast.parse(src)
        calls = [ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)]
        assert not [c for c in calls if c.startswith(("subprocess", "os.", "shutil"))], name
    outputs = {p: p.read_text() for p in (
        FMD / "reference_model.json", FMD / "config.candidate.json", FMD / "config.delta.txt",
        FMD / "proposal.json", FMD / "fixture_evaluation.json")}
    try:
        for name, extra in (("reference_model.py", []), ("prepare.py", []),
                            ("evaluate_record.py", ["--fixture"])):
            proc = subprocess.run([sys.executable, str(FMD / name), *extra], capture_output=True,
                                  text=True, cwd=REPO_ROOT)
            assert proc.returncode == 0, proc.stderr
        for p, before in outputs.items():
            after = p.read_text()
            if p.suffix == ".json":
                # byte-identical on this machine; across BLAS kernels the round-off-level
                # entries (1e-16 worst cases) may differ in their last digits, so the
                # comparison is structural with floats at 1e-9 relative or both below 1e-11
                assert _same_json(json.loads(after), json.loads(before)), f"{p.name} is not deterministic"
            else:
                assert after == before, f"{p.name} is not deterministic"
    finally:
        for p, before in outputs.items():
            p.write_text(before)
    assert not list((REPO_ROOT / "results").rglob("first-moment*.json"))


def test_the_proposal_states_caps_one_execution_and_no_mechanism(proposal):
    st = proposal["status"]
    assert st == {"prepared": True, "compiled": False, "approved": False, "executed": False,
                  "why_not_compiled": st["why_not_compiled"]}
    one = proposal["the_one_execution"]
    assert one["hard_caps"]["dof"] == 250000 and one["hard_caps"]["wall_s"] == 2700
    assert "not runtime promises" in one["hard_caps"]["meaning"]
    assert one["what_it_authorises"] == "one execution of this config with this image, once; no retry"
    assert one["mechanism"].startswith("NO workflow runs this and none is added")
    assert "spent PO1 approval" in one["mechanism"]
    assert one["mpi_processes"] == 1 and one["command"][-3:] == ["-np", "1", "config.json"]
    assert "--network" in one["command"] and "none" in one["command"]
    img = one["image"]
    assert img["patch_sha256"] == _sha256(PATCH) == PATCH_SHA256
    assert img["dockerfile_sha256"] == _sha256(DOCKERFILE)
    assert img["production_dockerfile_sha256_untouched"] == PROD_DOCKERFILE_SHA256
    assert img["palace_commit"] == PALACE_COMMIT
    assert one["inputs"]["config_sha256"] == _sha256(FMD / "config.candidate.json")
    assert one["inputs"]["mesh_sha256"] == "d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428"
    saved = proposal["A_saved_from_committed_columns"]
    assert saved["A_all_saved_modes"]["modes"] == list(range(1, 10))
    assert abs(saved["A_all_saved_modes"]["A_partial_GHz2"] - 2.351511939494728) < 1e-12
    assert abs(saved["A_all_saved_modes"]["N_partial"] - 0.999254583555896) < 1e-12
    assert abs(saved["B_field_resonant_only"]["A_partial_GHz2"] - 2.3508870351819766) < 1e-12
    assert abs(proposal["expected_scales"]["L_nd_expected"] - 20.582047285188583) < 1e-9
    for s in ("no eigensolve", "no Route A or Route B", "no registered-definition change",
              "no budget or cap increase, no merge of PR #7"):
        assert any(s in x for x in one["what_it_does_not_authorise"]), s


def test_the_patch_is_the_reviewed_one_and_touches_only_the_listed_files(patch_text):
    assert _sha256(PATCH) == PATCH_SHA256
    files = set(re.findall(r"^diff --git a/(\S+) b/", patch_text, flags=re.M))
    assert files == EXPECTED_PATCHED_FILES
    header = "diff --git a/palace/drivers/firstmomentsolver.cpp b/palace/drivers/firstmomentsolver.cpp"
    assert "new file mode" in patch_text.split(header, 1)[1][:80]
    assert '{ProblemData::Type::FIRSTMOMENT, "FirstMoment"}' in patch_text
    assert "FirstMomentSolverData firstmoment = {};" in patch_text
    assert 'firstmoment->value("Tol", tol)' in patch_text
    assert "case config::ProblemData::Type::FIRSTMOMENT:" in patch_text
    assert "firstmomentsolver.cpp" in patch_text.split("drivers/CMakeLists.txt", 1)[1][:600]
    # the Eigenmode path is untouched: no hunk in the eigen driver or the space operator
    for untouched in ("eigensolver", "spaceoperator", "postoperator", "divfree", "rap."):
        assert not any(untouched in f for f in files), untouched


def test_the_diagnostic_image_is_the_production_one_plus_the_patch_step():
    assert _sha256(PROD_DOCKERFILE) == PROD_DOCKERFILE_SHA256, "production Dockerfile changed"
    prod = PROD_DOCKERFILE.read_text().splitlines()
    diag = DOCKERFILE.read_text()
    tail = diag.split("# ---- everything below this line is docker/palace.Dockerfile", 1)[1]
    tail = tail.split("\n", 3)[3].splitlines()   # drop the two explanatory comment lines
    added = [ln for ln in tail if ln not in prod]
    assert any("git apply --check /opt/palace-first-moment-diagnostic.patch" in ln for ln in added)
    assert any("COPY docker/patches/first-moment-diagnostic.patch" in ln for ln in added)
    assert any("PALACE_PATCH_SHA256" in ln for ln in added)
    allowed = ("first-moment", "PALACE_PATCH", "git apply", "cd /opt/palace-src", "FIRSTMOMENT",
               "test -f palace/drivers", "RUN set -eux; \\",
               "cat /opt/palace/PALACE_VERSION /opt/palace/PALACE_COMMIT \\")
    for ln in added:
        assert ln.strip() == "" or ln.lstrip().startswith("#") or any(a in ln for a in allowed), ln
    missing = [ln for ln in prod if ln not in tail and not ln.startswith("#")]
    assert missing == [
        "    cat /opt/palace/PALACE_VERSION /opt/palace/PALACE_COMMIT",
        '      org.opencontainers.image.title="qmhp-cem/palace" \\',
        '      org.opencontainers.image.description="Palace EM solver for QMHP-CEM, built from the pinned release tag"',
    ]
    assert f"ARG PALACE_COMMIT={PALACE_COMMIT}" in diag
    assert diag.index("git apply --check") < diag.index("cmake -S /opt/palace-src")
    ignore = (REPO_ROOT / ".dockerignore").read_text().splitlines()
    assert [ln for ln in ignore if ln.startswith("!")] == ["!docker/patches/first-moment-diagnostic.patch"]


def test_no_trigger_path_is_touched_and_the_spent_approval_is_untouched(proposal):
    assert _sha256(APPROVAL) == APPROVAL_SHA256
    assert _sha256(PROD_DOCKERFILE) == PROD_DOCKERFILE_SHA256
    owned = [
        "docker/patches/first-moment-diagnostic.patch", "docker/palace-first-moment.Dockerfile",
        ".dockerignore", "experiments/first-moment-diagnostic/", "tests/test_first_moment_diagnostic.py",
        "docs/coupled-candidate/first-moment-diagnostic.md", "docs/coupled-candidate/README.md",
    ]
    triggers = proposal["workflow_trigger_paths_untouched"]
    assert ".github/workflows/" in triggers and "solvers/palace/" in triggers
    for path in owned:
        assert not any(path.startswith(t) for t in triggers), path
    # every workflow's push-path filter is checked literally against the owned paths
    for wf in (REPO_ROOT / ".github" / "workflows").glob("*.yml"):
        text = wf.read_text()
        for path in owned:
            assert path not in text, (wf.name, path)
    changed = subprocess.run(["git", "diff", "--name-only", "HEAD"], capture_output=True,
                             text=True, cwd=REPO_ROOT).stdout.split()
    assert not any(any(c.startswith(t) for t in triggers) for c in changed), changed


def test_the_doc_is_indexed_and_states_the_scope():
    readme = (REPO_ROOT / "docs" / "coupled-candidate" / "README.md").read_text()
    assert "](first-moment-diagnostic.md)" in readme
    norm = _norm(DOC.read_text())
    for phrase in (
        "PREPARED, NOT APPROVED, NOT EXECUTED",
        "not compiled",
        "M_free x = f_free",
        "no artificial boundary contribution",
        "f = Pᵀ v",
        "A_GHz² = A_nd / (2π t_c)²",
        "|fᴴE_m|² / (L λ_m E_mᴴ M E_m)",
        "K ≥ q qᴴ",
        "250 000",
        "2 700 s",
        "hard caps, not runtime promises",
        "no N2R FEM assembly",
        "E_C` stays UNAVAILABLE",
        "spent PO1 approval",
        "is not called an omitted spectral moment until",
        PATCH_SHA256,
        "20.582047285189",
        "0.016526676",
    ):
        assert phrase in norm, phrase


def test_launch_safety_of_this_test_file():
    tree = ast.parse(Path(__file__).read_text())
    runs = [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and ast.unparse(n.func) == "subprocess.run"]
    argv = [ast.unparse(n.args[0]) for n in runs]
    assert argv
    for a in argv:
        if a.startswith("['git'"):
            assert "'diff'" in a
            continue
        assert "sys.executable" in a and "FMD /" in a, a
