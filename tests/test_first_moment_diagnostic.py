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
PATCH_SHA256 = "e8a1ad51d4e355b0426e84c70cb9c796a4915b1216bb035d5fe60913de512fee"
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


def _json_mismatch(a, b, path: str = "") -> str | None:
    """Compare two regenerations of one artefact on everything EXCEPT float values.

    Three CI failures taught this. The test was asserting that a floating-point artefact
    reproduces across machines; that property is false, and no per-leaf tolerance captured
    it. Each run named a different field of the same class, every one a residue of a
    DELIBERATELY perturbed solve:

      run 35553777395  /evaluator/error_vs_truth_nd            7 percent
      run 35554886550  /negative_discrepancy/threshold_GHz2    4.1e-07
      run 35556211180  .../checks[16]/detail/relative_residual 5.9e-04

    The last one is alone in its object, so a scale taken from its neighbours is its own
    magnitude and no scale rule can ever exempt it. Tightening the constant again would
    have been tuning until green.

    So floats are not compared here at all, and the two properties that ARE true and DO
    matter are asserted instead: structure and discrete content are identical (keys, list
    lengths, strings, booleans, integers - which includes every verdict, every check name,
    every passed flag and every mode list), and the regenerated numbers are checked
    against the KNOWN truth recorded beside them by _truth_mismatches, rather than against
    a previous run. The physical values are additionally asserted against known answers by
    test_the_residual_error_identity_is_exact,
    test_the_evaluator_recovers_a_known_omitted_moment_and_never_overstates_it,
    test_the_saved_moment_interval_comes_from_the_printed_precision and
    test_the_compiled_diagnostic_matches_an_independent_assembly.

    Returns None when equivalent, else the path, so a failure names the field.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return f"{path}: keys differ ({sorted(set(a) ^ set(b))})"
        for k in a:
            m = _json_mismatch(a[k], b[k], f"{path}/{k}")
            if m:
                return m
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            m = _json_mismatch(x, y, f"{path}[{i}]")
            if m:
                return m
        return None
    if isinstance(a, bool) or isinstance(b, bool):
        return None if a == b else f"{path}: {a} != {b}"
    if isinstance(a, float) or isinstance(b, float):
        return None                                  # see the docstring
    return None if a == b else f"{path}: {a!r} != {b!r}"


def _truth_mismatches(doc: dict) -> list[str]:
    """Check a regenerated fixture evaluation against the truth recorded inside it.

    These hold on any machine because each compares quantities that move together, so
    they pin the numbers without demanding cross-machine reproduction of any one of them.
    """
    out = []
    truth, ev = doc["truth"], doc["evaluator"]
    omitted = truth["omitted_first_moment_exact_nd"]
    if abs((truth["A_total_nd"] - truth["A_saved_nd"]) - omitted) > 1e-12 * abs(omitted):
        out.append("A_total - A_saved != omitted_first_moment_exact")
    if abs(ev["A_direct_minus_A_saved_nd"] - omitted) > 1e-9 * abs(omitted):
        out.append("the measured difference does not equal the known omitted moment")
    if ev["certified_omitted_moment_lower_bound_nd"] > omitted * (1 + 1e-12):
        out.append("the certified lower bound exceeds the truth")
    if ev["verdict"] != "OMITTED_MOMENT_CERTIFIED_LOWER_BOUND":
        out.append(f"verdict is {ev['verdict']}")
    if not ev["all_checks_passed"]:
        out.append("the good record did not pass its own checks")
    return out


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


@pytest.fixture(scope="module")
def compiled() -> dict:
    return json.loads((FMD / "compiled_qualification.json").read_text())


@pytest.fixture(scope="module")
def synthetic() -> dict:
    return json.loads((FMD / "synthetic_fixture.json").read_text())


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
    assert "WriteFailure(\"the true-dof voltage functional does not reproduce GetVoltage\"" in drv
    assert "MFEM_ABORT(\"The true-dof voltage functional does not reproduce GetVoltage!\")" in drv
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
    assert "const double ghz2_per_nd = freq_scale * freq_scale;" in drv
    assert "const double A_GHz2 = A_nd * ghz2_per_nd;" in drv
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
    assert "WriteFailure(\"K >= q q^H violated on the constrained assembly\", check_k);" in drv
    assert "MFEM_ABORT(\"K \u2265 q q\u1d34 violated on the constrained assembly!\");" in drv
    for forbidden in ("EigenvalueSolver", "slepc", "arpack", "DivFreeSolver", "Driven", "omega"):
        assert forbidden not in drv, forbidden


# --- 5. outputs and numerical checks -------------------------------------------------

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




# --- 5. outputs, error qualification and numerical checks ----------------------------

def test_every_record_key_is_written_by_the_driver(rm, patch_text):
    drv = patch_text.split("palace/drivers/firstmomentsolver.cpp", 1)[1]
    for k, subs in rm.RECORD_KEYS.items():
        assert f'"{k}"' in drv, k
        for s in subs:
            assert f'"{s}"' in drv, f"{k}.{s}"
    for extra in ("WallTime_s", "MaxRSS_MB", "RelativeResidual", "Converged", "Free",
                  "Essential", "Lc_m", "tc_ns", "A_nd", "A_GHz2", "ImageInfoDirIsDefault"):
        assert f'"{extra}"' in drv


def test_the_driver_no_longer_reports_the_old_quantity_as_a_bound(patch_text):
    drv = patch_text.split("palace/drivers/firstmomentsolver.cpp", 1)[1]
    assert '"ResidualBound_nd"' not in drv and '"ResidualBound_GHz2"' not in drv
    assert '"UncertifiedErrorEstimate_nd"' in drv
    assert '"CertifiedErrorUpperBound_nd"' in drv
    assert '"CertifiedUpperBound"' in drv and '"UNAVAILABLE"' in drv
    assert "ESTIMATE, not a bound" in drv


def test_the_residual_error_identity_is_exact(rm):
    """A_computed - A_exact = (Re(x^H r) - r^H M^-1 r)/L, term by term."""
    rng = np.random.default_rng(31)
    for _ in range(8):
        fx = rm.Fixture(rng)
        f = rm.restrict_to_free(fx.f_true, fx.dbc)
        Mp = rm.padded_mass(fx.M, fx.dbc, "DIAG_ONE")
        x_star = np.linalg.solve(Mp, f)
        for scale in (1e-2, 1e-6, 1e-11):
            pert = rng.normal(size=x_star.size)
            pert[fx.dbc] = 0.0
            x = x_star + scale * np.linalg.norm(x_star) * pert / np.linalg.norm(pert)
            idn = rm.residual_error_identity(Mp, f, x, fx.L)
            assert abs(idn["lhs"] - idn["rhs"]) <= 1e-12 * abs(idn["A_exact"])
            # the certified statement, from r^H M^-1 r >= 0 alone
            assert idn["r_Minv_r"] >= 0.0
            assert idn["lhs"] <= idn["certified_error_upper_bound"] + 1e-12 * abs(idn["A_exact"])
            assert idn["certified_lower_bound_A"] <= idn["A_exact"] * (1 + 1e-12)
            # the variational form gives the same number
            assert abs(idn["variational_lower_bound_A"] - idn["certified_lower_bound_A"]) \
                <= 1e-9 * abs(idn["certified_lower_bound_A"])


def test_the_old_quantity_is_not_a_bound_even_at_a_tiny_residual(rm):
    """The counterexample family, including one that would pass the residual check."""
    loose = rm.bound_counterexample(1e-12, 1e-4)
    assert loose["estimate_is_a_bound"] is False
    assert loose["violation_factor"] > 1e6
    tight = rm.bound_counterexample(1e-16, 1e-13)
    assert tight["relative_residual"] <= 1e-12, "this one passes the residual check"
    assert tight["estimate_is_a_bound"] is False
    assert tight["violation_factor"] > 100
    for c in (loose, tight):
        assert c["certified_bound_holds"] is True
    # and the sufficient condition that would make the estimate a bound is reported
    assert loose["sufficient_lambda_min_for_estimate_to_bound"] > loose["lambda_min_M"]


def test_the_error_trials_and_counterexamples_are_recorded(rm):
    e = json.loads((FMD / "reference_model.json").read_text())["error_qualification"]
    t = e["trials"]
    assert t["identity_max_error_relative_to_A"] < 1e-12
    assert t["certified_bound_violations"] == 0
    assert t["variational_equals_certified_max_rel"] < 1e-12
    assert t["cg_like_solution_A_hat_never_exceeds_A_exact"] is True
    assert t["max_shortfall_of_A_hat_below_A_exact_relative"] > 0
    assert len(e["counterexamples_to_the_old_quantity"]) >= 3
    assert all(c["estimate_is_a_bound"] is False and c["certified_bound_holds"] is True
               for c in e["counterexamples_to_the_old_quantity"])


def test_the_saved_moment_interval_comes_from_the_printed_precision(rm, prep):
    saved = prep.saved_moments(rm.unit_scales(4.0e-3)["tc_ns"])["A_all_saved_modes"]
    assert abs(saved["central_GHz2"] - 2.351511939494728) < 1e-12
    assert saved["lo_GHz2"] < saved["central_GHz2"] < saved["hi_GHz2"]
    # "%+.9e" is 10 significant digits, so the half width is ~1e-9 of A, not more
    assert 0 < saved["halfwidth_GHz2"] < 1e-8 * saved["central_GHz2"]
    assert abs(rm.printed_halfwidth(3.885827871) - 0.5e-9) < 1e-20
    assert rm.printed_halfwidth(0.0) == 0.0
    ec = saved["eigensolver_convergence"]
    assert ec["propagated_into_A"] == "UNQUANTIFIED"
    assert ec["max_backward_error"] > 0 and ec["max_absolute_error"] > 0
    assert "spectral gap" in ec["why"]


def test_the_two_uncertainties_are_reported_separately(fixture_eval):
    good = fixture_eval["full_evaluation_of_the_good_record"]
    ms, sv = good["mass_solve_uncertainty"], good["A_saved_uncertainty"]
    assert set(ms) >= {"identity", "certified_error_upper_bound_GHz2",
                       "certified_lower_bound_A_GHz2", "certified_upper_bound_A_GHz2",
                       "uncertified_error_estimate_GHz2",
                       "sufficient_condition_for_the_estimate_to_be_a_bound"}
    assert ms["certified_upper_bound_A_GHz2"] == "UNAVAILABLE"
    cond = ms["sufficient_condition_for_the_estimate_to_be_a_bound"]
    assert cond["condition"] == "lambda_min(M_free) >= ||r|| / ||x||"
    assert cond["lambda_min_measured"] is False and cond["threshold"] > 0
    assert sv["kept_separate_from_mass_solve_uncertainty"] is True
    assert sv["eigensolver_convergence"]["propagated_into_A"] == "UNQUANTIFIED"
    assert good["tail_upper_bound"] == "UNAVAILABLE"


def test_the_evaluator_recovers_a_known_omitted_moment_and_never_overstates_it(fixture_eval):
    ev, truth = fixture_eval["evaluator"], fixture_eval["truth"]
    assert ev["verdict"] == "OMITTED_MOMENT_CERTIFIED_LOWER_BOUND"
    assert ev["all_checks_passed"] is True
    assert truth["omitted_first_moment_exact_nd"] > 0
    assert abs(ev["error_vs_truth_nd"]) <= 1e-9 * truth["omitted_first_moment_exact_nd"]
    assert ev["certified_lower_bound_is_below_the_truth"] is True
    assert ev["certified_omitted_moment_lower_bound_nd"] <= \
        truth["omitted_first_moment_exact_nd"]
    good = fixture_eval["full_evaluation_of_the_good_record"]
    assert good["E_C"] == "UNAVAILABLE" and good["g"] == "UNAVAILABLE"
    assert good["N"] == "not measured by this diagnostic"


def test_a_materially_negative_difference_is_inconsistent_not_an_omitted_moment(fixture_eval):
    neg = fixture_eval["negative_discrepancy"]
    assert neg["verdict"] == "INCONSISTENT"
    assert neg["difference_GHz2"] < neg["threshold_GHz2"]
    assert neg["interpretation"].startswith("INCONSISTENT")
    assert "NOT an omitted moment" in neg["interpretation"]
    assert "under-converged" in neg["interpretation"]


def test_a_difference_inside_the_combined_uncertainty_is_not_a_small_tail(fixture_eval):
    u = fixture_eval["difference_inside_the_combined_uncertainty"]
    assert u["verdict"] == "NOT_RESOLVED"
    assert "not evidence of a small tail" in u["interpretation"]
    assert u["tail_upper_bound"] == "UNAVAILABLE"


def test_the_hard_caps_and_the_space_identity_are_enforced(rm):
    rng = np.random.default_rng(12)
    fx = rm.Fixture(rng)
    base = rm.synthetic_record(fx, 4.0e-3, seed=12)
    saved = {"central_GHz2": base["A"]["A_GHz2"] * 0.9, "lo_GHz2": base["A"]["A_GHz2"] * 0.9,
             "hi_GHz2": base["A"]["A_GHz2"] * 0.9, "halfwidth_GHz2": 0.0}
    req = {"PALACE_VERSION": "0.13.0",
           "PALACE_COMMIT": "a61c8cbe0cacf496cde3c62e93085fae0d6299ac",
           "PALACE_PATCH": "first-moment-diagnostic", "PALACE_PATCH_SHA256": "0" * 64,
           "config_sha256": "c", "mesh_sha256": "d", "patch_sha256": "e",
           "dockerfile_sha256": "f", "image_id": "i"}
    act = {k: req[k] for k in ("config_sha256", "mesh_sha256", "patch_sha256",
                               "dockerfile_sha256", "image_id")}

    def ev(rec, **kw):
        return rm.evaluate(rec, saved, required_provenance=req, actual=act, **kw)

    assert ev(base, expected_dofs=fx.n_true)["all_checks_passed"]
    slow = json.loads(json.dumps(base))
    slow["Resources"]["WallTime_s"] = 2700.5
    assert not ev(slow)["all_checks_passed"]
    big = json.loads(json.dumps(base))
    big["Dofs"]["True"] = 250001
    big["Dofs"]["Free"] = 250001 - big["Dofs"]["Essential"]
    assert not ev(big)["all_checks_passed"]
    other = ev(base, expected_dofs=fx.n_true + 1)
    assert any("same true-dof count" in c["check"] and not c["passed"]
               for c in other["checks"])
    incomplete = json.loads(json.dumps(base))
    del incomplete["A"]["CertifiedLowerBound_A_nd"]
    assert rm.validate_record(incomplete) == ["A.CertifiedLowerBound_A_nd"]
    assert ev(incomplete)["verdict"] == "UNQUALIFIED"


# --- 5b. provenance fails closed ------------------------------------------------------

def test_every_spoiled_provenance_prevents_qualification(fixture_eval):
    spoiled = fixture_eval["spoiled_records_are_unqualified"]
    expected = {
        "provenance_missing": "provenance carries no unavailable field",
        "provenance_mismatch": "embedded PALACE_COMMIT matches the required value",
        "developer_build": "run came from the image identity directory",
        "required_image_id_not_supplied": "image_id measured and matches the required value",
        "measured_mesh_digest_mismatch": "mesh_sha256 measured and matches the required value",
        "status": "record status is COMPLETED",
        "functional": "functional reproduces GetVoltage",
        "null_space": "sampled K >= q q^H",
        "convergence": "linear solve converged",
    }
    for key, needle in expected.items():
        assert spoiled[key]["verdict"] == "UNQUALIFIED", key
        assert any(needle in c for c in spoiled[key]["failed"]), (key, spoiled[key])
    assert fixture_eval["sloppy_solve"]["verdict"] == "UNQUALIFIED"


def test_required_provenance_is_required_not_merely_reported(rm, prep):
    req = prep.required_provenance("cfg")
    assert set(req) >= set(rm.REQUIRED_PROVENANCE_FIELDS) | set(rm.REQUIRED_DIGEST_FIELDS)
    assert req["PALACE_COMMIT"] == PALACE_COMMIT
    assert req["PALACE_PATCH_SHA256"] == PATCH_SHA256 == _sha256(PATCH)
    assert req["dockerfile_sha256"] == _sha256(DOCKERFILE)
    assert req["mesh_sha256"] == "d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428"
    assert "SUPPLIED BY THE EXECUTION" in req["image_id"]
    # the driver reads the identity from the image rather than being told it
    drv = PATCH.read_text().split("palace/drivers/firstmomentsolver.cpp", 1)[1]
    assert "ReadImageInfoFile" in drv and "/opt/palace" in drv
    assert "PALACE_PATCH_SHA256" in drv and '"unavailable"' in drv


def test_the_launcher_is_prepared_but_inert():
    launcher = FMD / "run_diagnostic.py"
    assert launcher.is_file()
    assert not (FMD / "EXECUTION-APPROVAL.json").exists(), "the diagnostic must not be armed"
    proc = subprocess.run([sys.executable, str(launcher), "--record-dir", "/tmp/nope",
                           "--mesh", "/tmp/nope"], capture_output=True, text=True,
                          cwd=REPO_ROOT)
    assert proc.returncode == 2
    assert "REFUSED" in proc.stderr and "PREPARED, NOT ACTIVATED" in proc.stderr
    assert "spent PO1 approval" in proc.stderr
    src = launcher.read_text()
    for token in ("DOF_HARD_CAP", "WALL_HARD_CAP_S", "docker", "kill"):
        assert token in src
    assert "no_retry" in src


def test_the_launcher_argv_and_caps_are_pinned():
    mod = _load("run_diagnostic")
    argv = mod.build_command(workdir=Path("/w"), name="n", user=False)
    assert argv[:6] == ["docker", "run", "--rm", "--network", "none", "--hostname"]
    assert argv[-4:] == ["palace", "-np", "1", "config.json"]
    assert "--entrypoint" in argv and "stdbuf" in argv
    assert "-v" in argv and "/w:/work" in argv
    assert mod.DOF_HARD_CAP == 250_000 and mod.WALL_HARD_CAP_S == 2_700
    with pytest.raises(mod.Refusal):
        mod.load_approval()
    # the DOF pattern matches the finest-space line and not the multigrid lines, checked
    # against the committed N2R log
    pat = mod.dof_probe_pattern(1)
    log = (REPO_ROOT / "results" / "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z" / "L2"
           / "solver" / "palace_log.txt").read_text()
    hits = [int(m) for m in pat.findall(log)]
    assert hits == [103411]
    assert not pat.search(" Level 0 (p = 1): 79944 unknowns")


# --- 5c. the compiled diagnostic ------------------------------------------------------

def test_the_compiled_diagnostic_matches_an_independent_assembly(compiled, synthetic):
    for name in ("A-nominal", "B-scaled-L"):
        r = compiled["runs"][name]
        assert r["converged"] is True
        assert r["relative_error_vs_independent"] < 1e-12, name
        assert r["dof_counts_agree"] is True
        assert r["Lc_agrees"] and r["tc_agrees"] and r["A_GHz2_conversion_consistent"]
        assert r["json_is_finite"] is True
        assert r["functional_check_passed"] is True
        assert r["functional_check_relative_error"] <= 1e-10
        assert r["functional_norm2_essential"] > 0, "the PEC restriction must bite"
        assert r["solution_essential_norm"] == 0.0
        assert r["null_space_is_sampled_not_proof"] is True
        assert r["null_space_min_gap"] > 0
        assert r["certified_lower_bound_holds_vs_independent"] is True
    assert compiled["L_scaling"]["relative_error"] < 1e-12
    inv = synthetic["fixtures"]["A-nominal"]["independent"]
    assert inv["constant_field_invariant_max_relative_error"] < 1e-12


def test_the_compiled_diagnostic_handles_non_convergence_and_failed_checks(compiled):
    c = compiled["runs"]["C-maxits-1"]
    assert c["converged"] is False and c["relative_residual"] > 1e-3
    assert c["log_preserved"] is True and c["json_is_finite"] is True
    # an under-converged solve UNDERESTIMATES A, and the certified bound still holds
    assert c["unconverged_solve_underestimates_A"] is True
    assert c["shortfall_of_A_below_independent_nd"] > 0
    assert c["certified_lower_bound_holds_vs_independent"] is True
    # and there the old quantity's sufficient condition fails, on real compiled output
    assert c["estimate_is_a_bound_here"] is False
    d = compiled["runs"]["D-port-inactive"]
    assert d["returncode"] != 0
    assert d["wrote_first_moment_json"] is False, "a failed check must write no result"
    assert d["failed_record"]["Status"] == "FAILED"
    assert d["failed_record_has_provenance"] is True
    assert d["log_preserved"] is True


def test_the_functional_check_is_not_vacuous_and_its_limit_is_stated(compiled):
    fi = compiled["fault_injection"]
    assert fi["caught_at"] == ["np=4"]
    assert fi["not_caught_at"] == ["np=1", "np=2", "np=3"]
    assert "NOT vacuous" in fi["reading"]
    assert "limit of the fixture, not a pass" in fi["reading"]
    assert fi["good_binary_agrees_across_ranks"] is True
    sweep = compiled["mpi_sweep"]
    assert sweep["np=4"]["faulted"]["aborted"] is True
    assert sweep["np=4"]["faulted"]["wrote_first_moment_json"] is False
    assert "does not reproduce GetVoltage" in sweep["np=4"]["faulted"]["failed_reason"]
    for row in sweep.values():
        assert row["good"]["relative_error_vs_independent"] < 1e-12


def test_the_compiled_run_is_recorded_as_a_developer_build_not_an_image_run(compiled, rm):
    prov = compiled["runs"]["A-nominal"]["provenance"]
    assert prov["PALACE_COMMIT"] == PALACE_COMMIT
    assert prov["PALACE_PATCH_SHA256"] == PATCH_SHA256
    assert prov["ImageInfoDirIsDefault"] is False, (
        "a native build must not be able to masquerade as an image run")
    rec = {"Diagnostic": "FirstMoment", "Status": "COMPLETED", "Provenance": prov}
    assert "Port" in rm.validate_record(rec)


def test_the_compiled_qualification_refuses_anything_but_the_synthetic_fixtures():
    mod = _load("compiled_qualification")
    with pytest.raises(mod.Refusal):
        mod.assert_synthetic(REPO_ROOT / "results" /
                             "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z" / "L2" / "solver"
                             / "config.json")
    with pytest.raises(mod.Refusal):
        mod.assert_synthetic(FMD / "config.candidate.json")
    cfg = mod.assert_synthetic(FMD / "fixtures" / "config-A-nominal.json")
    assert cfg["Problem"]["Type"] == "FirstMoment"
    assert cfg["Model"]["Mesh"] == "fm_synthetic.msh"
    src = (FMD / "compiled_qualification.py").read_text()
    assert "SYNTHETIC" in src and "refuses to execute anything" in src


def test_the_synthetic_fixture_is_not_the_qmhp_cell(synthetic):
    assert "NOT the QMHP-CEM coupled cell" in (FMD / "synthetic_fixture.py").read_text()
    assert synthetic["mesh"]["n_tets"] < 2000, "small by construction"
    src = (FMD / "synthetic_fixture.py").read_text()
    for token in ("results/", "COUPLED-LADDER", "coupled_chip_cell", "11.45"):
        assert token not in src, token
    cfg = json.loads((FMD / "fixtures" / "config-A-nominal.json").read_text())
    assert cfg["Domains"]["Materials"][1]["Permittivity"] == 4.0


# --- 6b. preparation only, offline and inert -----------------------------------------

def test_the_offline_scripts_are_deterministic_and_cannot_launch_anything():
    offline = ("reference_model.py", "prepare.py", "evaluate_record.py")
    for name in offline:
        src = (FMD / name).read_text()
        for forbidden in ("requests", "urllib", "socket", "http://", "https://",
                          "subprocess", "os.system", "Popen", "podman"):
            assert forbidden not in src, (name, forbidden)
    # the two scripts that DO shell out are the inert launcher and the synthetic-only
    # qualifier; neither can reach a QMHP config
    launcher = (FMD / "run_diagnostic.py").read_text()
    assert "raise Refusal" in launcher and "APPROVAL_PATH" in launcher
    qualifier = (FMD / "compiled_qualification.py").read_text()
    assert "assert_synthetic(config_path)" in qualifier

    outputs = {p: p.read_text() for p in (
        FMD / "reference_model.json", FMD / "config.candidate.json",
        FMD / "config.delta.txt", FMD / "proposal.json", FMD / "fixture_evaluation.json")}
    try:
        for name, extra in (("reference_model.py", []), ("prepare.py", []),
                            ("evaluate_record.py", ["--fixture"])):
            proc = subprocess.run([sys.executable, str(FMD / name), *extra],
                                  capture_output=True, text=True, cwd=REPO_ROOT)
            assert proc.returncode == 0, proc.stderr
        for p, before in outputs.items():
            after = p.read_text()
            if p.suffix == ".json":
                was, now = json.loads(before), json.loads(after)
                mismatch = _json_mismatch(now, was)
                assert mismatch is None, f"{p.name}{mismatch}"
                if p.name == "fixture_evaluation.json":
                    # the regenerated numbers, against the truth recorded beside them
                    assert _truth_mismatches(now) == [], p.name
            else:
                assert after == before, p.name
    finally:
        for p, before in outputs.items():
            p.write_text(before)
    assert not list((REPO_ROOT / "results").rglob("first-moment*.json"))


def test_the_proposal_states_the_blocker_the_launcher_and_one_execution(proposal):
    st = proposal["status"]
    assert st["prepared"] is True and st["compiled"] is True
    assert st["approved"] is False and st["executed_on_N2R"] is False
    blocker = proposal["image_blocker"]
    assert "production.cloudfront.docker.com:443" in blocker["exact_error"]
    assert "403 to CONNECT" in blocker["exact_error"]
    assert "not routed around" in " ".join(blocker).lower() or \
        "no alternative registry" in blocker["not_routed_around"]
    one = proposal["the_one_execution"]
    assert one["launcher"]["state"] == "PREPARED, NOT ACTIVATED"
    assert one["launcher"]["approval_absent"] is True
    assert "not a timeout mechanism" in one["launcher"]["enforces"]["wall_clock"]
    assert one["hard_caps"]["dof"] == 250000 and one["hard_caps"]["wall_s"] == 2700
    assert "not runtime promises" in one["hard_caps"]["meaning"]
    assert one["hard_caps"]["enforced_by"].endswith("run_diagnostic.py")
    assert one["what_it_authorises"] == "one execution of this config with this image, once; no retry"
    assert one["mechanism"].startswith("NO workflow runs this and none is added")
    assert "spent PO1 approval" in one["mechanism"]
    img = one["image"]
    assert img["patch_sha256"] == _sha256(PATCH) == PATCH_SHA256
    assert img["production_dockerfile_sha256_untouched"] == PROD_DOCKERFILE_SHA256
    assert img["palace_commit"] == PALACE_COMMIT
    assert one["inputs"]["config_sha256"] == _sha256(FMD / "config.candidate.json")
    saved = proposal["A_saved_from_committed_columns"]["A_all_saved_modes"]
    assert abs(saved["A_partial_GHz2"] - 2.351511939494728) < 1e-12
    assert saved["halfwidth_GHz2"] > 0
    assert saved["eigensolver_convergence"]["propagated_into_A"] == "UNQUANTIFIED"
    for s in ("no eigensolve", "no Route A or Route B", "no registered-definition change",
              "no budget or cap increase, no merge of PR #7"):
        assert any(s in x for x in one["what_it_does_not_authorise"]), s
    says = " ".join(proposal["what_the_comparison_will_and_will_not_say"])
    assert "CERTIFIED LOWER BOUND" in says and "never a small tail" in says
    assert "INCONSISTENT" in says


def test_the_doc_is_indexed_and_states_the_corrections():
    readme = (REPO_ROOT / "docs" / "coupled-candidate" / "README.md").read_text()
    assert "](first-moment-diagnostic.md)" in readme
    norm = _norm(DOC.read_text())
    for phrase in (
        "PREPARED, NOT APPROVED, NOT EXECUTED ON N2R",
        "A_computed − A_exact = (Re(xᴴr) − rᴴM⁻¹r) / L",
        "is an ESTIMATE, not a bound",
        "production.cloudfront.docker.com",
        "403 to CONNECT",
        "not routed around",
        "8.9e-16",
        "caught at four ranks",
        "PREPARED, NOT ACTIVATED",
        "250 000",
        "2 700 s",
        "hard caps, not runtime promises",
        "INCONSISTENT",
        "E_C` stays UNAVAILABLE",
        "spent PO1 approval",
        PATCH_SHA256,
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
        assert "sys.executable" in a and ("FMD /" in a or "launcher" in a), a
    # no test here shells out to a container runtime or an MPI launcher
    for a in argv:
        for token in ("docker", "podman", "mpirun", "palace"):
            assert token not in a, (token, a)


def test_the_artefact_comparison_rejects_real_change_and_the_truth_checks_bite():
    """A comparison that only ever passes is worthless, so both halves are pinned.

    The structural half must catch every discrete edit and name its path. The truth half
    must catch a wrong number, which the structural half deliberately no longer compares.
    """
    import copy

    committed = json.loads((FMD / "fixture_evaluation.json").read_text())
    assert _json_mismatch(committed, committed) is None
    assert _truth_mismatches(committed) == []

    # solver-noise residues vary across machines and must NOT fail the structural half
    for path, value in ((("evaluator", "error_vs_truth_nd"), 5.381306e-20),
                        (("negative_discrepancy", "threshold_GHz2"), -1.65115204e-13)):
        alt = copy.deepcopy(committed)
        alt[path[0]][path[1]] = value
        assert _json_mismatch(alt, committed) is None, path
    noisy = copy.deepcopy(committed)
    noisy["full_evaluation_of_the_good_record"]["checks"][16]["detail"][
        "relative_residual"] = 1.279034924178295e-13
    assert _json_mismatch(noisy, committed) is None

    # every discrete edit must be caught AND named
    discrete = {
        "verdict string": lambda d: d["evaluator"].__setitem__("verdict", "NOT_RESOLVED"),
        "boolean": lambda d: d["evaluator"].__setitem__(
            "certified_lower_bound_is_below_the_truth", False),
        "check name": lambda d: d["full_evaluation_of_the_good_record"]["checks"][0]
            .__setitem__("check", "something else"),
        "a check's passed flag": lambda d: d["full_evaluation_of_the_good_record"]["checks"][0]
            .__setitem__("passed", False),
        "missing key": lambda d: d["evaluator"].pop("verdict"),
        "shortened list": lambda d: d["full_evaluation_of_the_good_record"].__setitem__(
            "checks", d["full_evaluation_of_the_good_record"]["checks"][:-1]),
        "mode list": lambda d: d["fixture"].__setitem__("n_modes_saved", 999),
    }
    for label, mutate in discrete.items():
        bad = copy.deepcopy(committed)
        mutate(bad)
        mismatch = _json_mismatch(bad, committed)
        assert mismatch is not None, label
        assert mismatch.startswith("/"), (label, mismatch)

    # and a wrong NUMBER, which the structural half skips, must be caught by the truth half
    numeric = {
        "measured difference off by 1e-6": lambda d: d["evaluator"].__setitem__(
            "A_direct_minus_A_saved_nd",
            d["evaluator"]["A_direct_minus_A_saved_nd"] * (1 + 1e-6)),
        "certified bound above the truth": lambda d: d["evaluator"].__setitem__(
            "certified_omitted_moment_lower_bound_nd",
            d["truth"]["omitted_first_moment_exact_nd"] * 1.001),
        "truth internally inconsistent": lambda d: d["truth"].__setitem__(
            "A_saved_nd", d["truth"]["A_saved_nd"] * 1.001),
    }
    for label, mutate in numeric.items():
        bad = copy.deepcopy(committed)
        mutate(bad)
        assert _json_mismatch(bad, committed) is None, f"{label}: structural half should skip"
        assert _truth_mismatches(bad) != [], label

    # The one place a float survives into a compared STRING: the interpretation renders
    # the certified lower bound. It is rendered to 7 significant digits while the bound
    # itself varies across machines at 1e-13 relative (measured on CI run 35553777395),
    # six orders of margin. Pinned so the rendering cannot quietly gain digits.
    rendered = re.findall(r"(\d\.\d+)e[+-]\d\d", committed["evaluator"]["interpretation"])
    assert rendered, committed["evaluator"]["interpretation"]
    for mantissa in rendered:
        assert len(mantissa.replace(".", "")) <= 7, mantissa
