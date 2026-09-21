"""The direct first-moment diagnostic: prepared and verified on fixtures, not executed."""

from __future__ import annotations

import ast
import copy
import csv
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


# --- the regeneration guard ----------------------------------------------------------
#
# This guard answers one question: does re-running the offline scripts reproduce the
# committed artefacts? It is NOT the only check on their numbers - the physical values are
# also asserted against known answers by the dedicated tests - but it must not accept a
# corrupted document. Five corruptions that an earlier float-skipping version accepted are
# pinned in test_the_regeneration_guard_rejects_corruption below.
#
# Floats are handled by class, never by one document-wide magnitude and never by skipping
# them all:
#   stable  - deterministic or well-conditioned; compared to the committed value
#   noise   - residues of a DELIBERATELY perturbed solve, whose last digits differ between
#             machines; each carries an explicit requirement matched to its meaning
#   bound   - a maximum over random trials at round-off level; required to satisfy its
#             declared scientific threshold, which is unchanged from the dedicated tests

#: Relative tolerance for a float that is deterministic or well conditioned. The physical
#: quantities in these documents moved by 7e-13 when the LAPACK eigen driver was swapped;
#: the worst-cancelling of them, the A_direct - A_saved difference, loses about one and a
#: half digits to that subtraction and so moves by 2.3e-11. This leaves it a factor of 40,
#: and every other stable float three orders or more. It is not a floor and not a
#: document-wide magnitude: a float that has no business moving is held to it exactly.
STABLE_TOL = 1e-9


def _type_class(v) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if v is None:
        return "null"
    if isinstance(v, dict):
        return "dict"
    if isinstance(v, list):
        return "list"
    return type(v).__name__


def _stable(path: str, new: float, old: float, tol: float = STABLE_TOL) -> str | None:
    if abs(new - old) <= tol * max(abs(new), abs(old)):
        return None
    rel = abs(new - old) / max(abs(new), abs(old), 1e-300)
    return f"{path}: {new!r} != {old!r} (relative {rel:.2e} > {tol:g})"


def _compare(new, old, float_rule=None, path: str = "") -> list[str]:
    """Type-aware structural comparison. Type classes must match, so a boolean, an integer
    count, a string or a container can never silently interchange with a float. Floats must
    be finite in both documents before any numerical rule is applied.

    With float_rule None this is the SHAPE pass: structure, type classes, discrete values
    and finiteness only. It runs first because the numerical rules and the invariants read
    values out of the document and presume they are finite numbers of the right type.
    """
    tn, to = _type_class(new), _type_class(old)
    if tn != to:
        return [f"{path}: type {tn} != {to} ({new!r} vs {old!r})"]
    if tn == "dict":
        if new.keys() != old.keys():
            return [f"{path}: keys differ ({sorted(set(new) ^ set(old))})"]
        out = []
        for k in new:
            out += _compare(new[k], old[k], float_rule, f"{path}/{k}")
        return out
    if tn == "list":
        if len(new) != len(old):
            return [f"{path}: length {len(new)} != {len(old)}"]
        out = []
        for i, (x, y) in enumerate(zip(new, old)):
            out += _compare(x, y, float_rule, f"{path}[{i}]")
        return out
    if tn == "float":
        for label, v in (("regenerated", new), ("committed", old)):
            if not math.isfinite(v):
                return [f"{path}: {label} value is not finite ({v!r})"]
        if float_rule is None:
            return []
        m = float_rule(path, new, old)
        return [m] if m else []
    return [] if new == old else [f"{path}: {new!r} != {old!r}"]


# --- fixture_evaluation.json ---------------------------------------------------------
#
# The nine residues, each with a requirement that states what the number MEANS. The
# measured magnitudes are in the comments; every requirement leaves at least three orders
# of headroom over what has actually been observed across machines.

def _fixture_noise_rules(doc: dict) -> dict:
    ev, truth = doc["evaluator"], doc["truth"]
    full = doc["full_evaluation_of_the_good_record"]
    A_nd = full["A_direct"]["A_nd"]
    A_GHz2 = full["A_direct"]["A_GHz2"]
    omitted = truth["omitted_first_moment_exact_nd"]
    diff_GHz2 = full["difference"]["A_direct_minus_A_saved_GHz2"]
    return {
        # cancellation residue of two numbers near 1.75e-07; measured 3.3e-13 of the truth
        "/evaluator/error_vs_truth_nd":
            (lambda v: abs(v) <= 1e-9 * abs(omitted),
             "|error vs truth| <= 1e-9 x the known omitted moment"),
        # -(A_saved half width + uncertified estimate); measured 2.0e-07 of the difference
        "/negative_discrepancy/threshold_GHz2":
            (lambda v: v < 0.0 and abs(v) <= 1e-5 * abs(diff_GHz2),
             "negative, and |threshold| <= 1e-5 x the difference"),
        "/full_evaluation_of_the_good_record/difference/materially_negative_threshold_GHz2":
            (lambda v: v < 0.0 and abs(v) <= 1e-5 * abs(diff_GHz2),
             "negative, and |threshold| <= 1e-5 x the difference"),
        # ||r||/||f|| of a solve perturbed at 1e-13 by construction; measured 1.3e-13
        "/full_evaluation_of_the_good_record/checks[16]/detail/relative_residual":
            (lambda v: 0.0 < v <= 1e-10,
             "a positive relative residual no larger than 1e-10"),
        # Re(x^H r), zero in exact arithmetic; measured 2.1e-13 of A
        "/full_evaluation_of_the_good_record/mass_solve_uncertainty/x_dot_r_nd":
            (lambda v: abs(v) <= 1e-9 * abs(A_nd), "|x.r| <= 1e-9 x A_nd"),
        "/full_evaluation_of_the_good_record/mass_solve_uncertainty/certified_error_upper_bound_GHz2":
            (lambda v: abs(v) <= 1e-9 * abs(A_GHz2),
             "|certified error bound| <= 1e-9 x A_GHz2"),
        "/full_evaluation_of_the_good_record/mass_solve_uncertainty/uncertified_error_estimate_GHz2":
            (lambda v: 0.0 < v <= 1e-9 * abs(A_GHz2),
             "a positive estimate no larger than 1e-9 x A_GHz2"),
        "/full_evaluation_of_the_good_record/mass_solve_uncertainty/sufficient_condition_for_the_estimate_to_be_a_bound/threshold":
            (lambda v: 0.0 < v <= 1e-6, "a positive ||r||/||x|| no larger than 1e-6"),
        "/full_evaluation_of_the_good_record/checks[27]/detail/err_ub_nd":
            (lambda v: abs(v) <= 1e-9 * abs(A_nd), "|certified error bound| <= 1e-9 x A_nd"),
    }


def _fixture_float_rule(doc: dict):
    rules = _fixture_noise_rules(doc)

    def rule(path: str, new: float, old: float) -> str | None:
        if path in rules:
            ok, why = rules[path]
            return None if ok(new) else f"{path}: {new!r} fails its requirement: {why}"
        return _stable(path, new, old)

    return rule


def _fixture_invariants(doc: dict, rm) -> list[str]:
    """Cross-checks inside the document, and one INDEPENDENT recomputation.

    The internal checks tie every nested value to its summary and to the unit conversion,
    so a single field cannot drift alone. They cannot catch a COMMON-SCALE error, where
    every related number is multiplied by the same factor, because such a document stays
    internally consistent. The independent recomputation catches that: it recovers the
    fixture's total moment by the dense free-dof solve, which is a different route from
    the eigenbasis Parseval sum that produced the recorded value. It shares the fixture
    construction, so it checks the recorded numbers, not the fixture itself.
    """
    out = []

    def near(label, a, b, tol=1e-9):
        if not (abs(a - b) <= tol * max(abs(a), abs(b), 1e-300)):
            out.append(f"{label}: {a!r} vs {b!r}")

    ev, truth = doc["evaluator"], doc["truth"]
    full = doc["full_evaluation_of_the_good_record"]
    scale = rm.unit_scales(4.0e-3)["A_GHz2_per_nd"]

    # unit conversion, computed here from physical constants rather than read back
    near("A_GHz2 != A_nd x A_GHz2_per_nd",
         full["A_direct"]["A_GHz2"], full["A_direct"]["A_nd"] * scale, 1e-12)
    near("summary difference != nested difference / scale",
         ev["A_direct_minus_A_saved_nd"] * scale,
         full["difference"]["A_direct_minus_A_saved_GHz2"])
    near("summary certified bound != nested certified bound / scale",
         ev["certified_omitted_moment_lower_bound_nd"] * scale,
         full["difference"]["certified_omitted_moment_lower_bound_GHz2"])
    near("nested difference != A_direct - A_saved",
         full["difference"]["A_direct_minus_A_saved_GHz2"],
         full["A_direct"]["A_GHz2"] - full["A_saved"]["central_GHz2"])
    near("relative_to_A_saved is inconsistent",
         full["difference"]["relative_to_A_saved"],
         full["difference"]["A_direct_minus_A_saved_GHz2"] / full["A_saved"]["central_GHz2"])
    near("A_saved summary != A_saved uncertainty block",
         full["A_saved"]["central_GHz2"], full["A_saved_uncertainty"]["central_GHz2"], 1e-15)
    lo, hi = full["A_saved_uncertainty"]["printed_precision_interval_GHz2"]
    if not lo <= full["A_saved_uncertainty"]["central_GHz2"] <= hi:
        out.append("A_saved central lies outside its printed-precision interval")
    # hi and lo are central +- halfwidth ROUNDED to double, so recovering the half width
    # by subtracting them is exact only to the rounding of that pair. The requirement is
    # therefore one ulp of the central value - an absolute bound set by the arithmetic -
    # and not a relative tolerance, which at 1.65e-13 beside 7.9e-04 would be meaningless.
    hw = full["A_saved_uncertainty"]["halfwidth_GHz2"]
    if abs(hw - 0.5 * (hi - lo)) > math.ulp(full["A_saved_uncertainty"]["central_GHz2"]):
        out.append(f"half width {hw!r} is not (hi - lo) / 2 to the rounding of hi and lo")
    near("checks[26] A_GHz2 is inconsistent with its A_nd",
         full["checks"][26]["detail"]["A_GHz2"],
         full["checks"][26]["detail"]["A_nd"] * scale, 1e-12)

    # truth, and the verdict that rests on it
    omitted = truth["omitted_first_moment_exact_nd"]
    near("A_total - A_saved != omitted", truth["A_total_nd"] - truth["A_saved_nd"],
         omitted, 1e-12)
    near("measured difference != the known omitted moment",
         ev["A_direct_minus_A_saved_nd"], omitted)
    if ev["certified_omitted_moment_lower_bound_nd"] > omitted * (1 + 1e-12):
        out.append("the certified lower bound exceeds the truth")
    if ev["verdict"] != "OMITTED_MOMENT_CERTIFIED_LOWER_BOUND":
        out.append(f"verdict is {ev['verdict']}")
    if not ev["all_checks_passed"]:
        out.append("the good record did not pass its own checks")

    # the interpretation renders the certified bound; tie the text to the number
    rendered = re.findall(r"\d\.\d+e[+-]\d\d", ev["interpretation"])
    bound_GHz2 = full["difference"]["certified_omitted_moment_lower_bound_GHz2"]
    if len(rendered) != 1:
        out.append(f"the interpretation renders {len(rendered)} numbers, expected one")
    elif rendered[0] != f"{bound_GHz2:.6e}":
        out.append(f"the interpretation renders {rendered[0]}, not the certified lower "
                   f"bound {bound_GHz2:.6e}")

    # INDEPENDENT: the dense free-dof solve, not the eigenbasis sum that produced the value
    fx = rm.Fixture(np.random.default_rng(rm.RNG_SEED))
    independent = rm.first_moment_free(fx.M, fx.f_true, fx.dbc, fx.L)
    near("recorded A_total disagrees with an independent dense solve",
         truth["A_total_nd"], independent)
    return out


# --- reference_model.json ------------------------------------------------------------
#
# The trial maxima are round-off-level and differ between machines by O(1) relatively, so
# they are required to satisfy their declared threshold rather than to reproduce. The
# thresholds are exactly those the dedicated tests assert; none is relaxed here.

RM_BOUNDS = {
    "/worst_case/dual_assembly_vs_GetVoltage": ("<", 1e-12),
    "/worst_case/free_restricted_functional_vs_GetVoltage_when_E_dbc_is_zero": ("<", 1e-12),
    "/worst_case/padded_DIAG_ONE_zeroed_rhs_vs_free": ("<", 1e-12),
    "/worst_case/padded_DIAG_ONE_unzeroed_rhs_minus_free_vs_sum_f_dbc2_over_L": ("<", 1e-12),
    "/worst_case/parseval_all_modes_vs_free_solve": ("<", 1e-12),
    "/worst_case/parseval_nonzero_modes_vs_free_solve": ("<", 1e-12),
    "/worst_case/kernel_annihilation_same_points": ("<", 1e-12),
    "/worst_case/K_port_minus_qq_min_eig_same_rule_min": (">=", -1e-12),
    "/worst_case/epr_palace_vs_absolute_square": ("<", 1e-12),
    "/worst_case/epr_phase_invariance": ("<", 1e-9),
    "/worst_case/A_phase_invariance": ("<", 1e-12),
    "/worst_case/unit_roundtrip_A_GHz2": ("<", 1e-12),
    "/worst_case/zeroth_moment_vs_pseudoinverse": ("<", 1e-12),
    "/error_qualification/trials/identity_max_error_relative_to_A": ("<", 1e-12),
    "/error_qualification/trials/variational_equals_certified_max_rel": ("<", 1e-12),
}


def _reference_model_float_rule(path: str, new: float, old: float) -> str | None:
    if path in RM_BOUNDS:
        op, limit = RM_BOUNDS[path]
        ok = new < limit if op == "<" else new >= limit
        return None if ok else f"{path}: {new!r} fails {op} {limit:g}"
    return _stable(path, new, old)


def _reference_model_invariants(doc: dict, rm) -> list[str]:
    out = []
    expected = rm.unit_scales(4.0e-3)
    for k, v in doc["expected_N2R_scales_from_Lc_4mm"].items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if abs(v - expected[k]) > 1e-12 * abs(expected[k]):
                out.append(f"expected scale {k} disagrees with unit_scales: {v!r}")
    if abs(doc["expected_N2R_L_nd"] - rm.inductance_nd(1.0345665367517793e-07, 4.0e-3)) > 1e-9:
        out.append("expected_N2R_L_nd disagrees with the inductance conversion")
    for i, cx in enumerate(doc["error_qualification"]["counterexamples_to_the_old_quantity"]):
        if cx["estimate_is_a_bound"] or not cx["certified_bound_holds"]:
            out.append(f"counterexample {i} no longer demonstrates the failure")
    if not doc["worst_case"]["padded_DIAG_ZERO_singular_in_every_trial"]:
        out.append("DIAG_ZERO padding is no longer singular in every trial")
    return out


# --- proposal.json -------------------------------------------------------------------

def _proposal_invariants(doc: dict, rm) -> list[str]:
    """Digests against the files on disk, and the saved moments against an INDEPENDENT
    recomputation from the committed columns - read here rather than through prepare.py,
    so a common-scale error in the proposal is caught."""
    out = []
    one = doc["the_one_execution"]
    for key, path in (("patch_sha256", PATCH), ("dockerfile_sha256", DOCKERFILE),
                      ("production_dockerfile_sha256_untouched", PROD_DOCKERFILE)):
        if one["image"][key] != _sha256(path):
            out.append(f"{key} does not match {path.name} on disk")
    if one["inputs"]["config_sha256"] != _sha256(FMD / "config.candidate.json"):
        out.append("config_sha256 does not match config.candidate.json on disk")

    post = (REPO_ROOT / "results" / "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z" / "L2"
            / "solver" / "postpro")

    def column(name, idx):
        rows = list(csv.reader((post / name).open()))[1:]
        return [float(r[idx]) for r in rows]

    f_GHz, abs_p = column("eig.csv", 1), [abs(v) for v in column("port-EPR.csv", 1)]
    saved = doc["A_saved_from_committed_columns"]["A_all_saved_modes"]
    independent = sum(abs_p[i - 1] * f_GHz[i - 1] ** 2 for i in saved["modes"])
    if abs(saved["A_partial_GHz2"] - independent) > 1e-12 * independent:
        out.append("A_saved disagrees with an independent sum over the committed columns")
    if [row["mode"] for row in saved["per_mode"]] != saved["modes"]:
        out.append("the per-mode rows do not match the saved mode list")
    total = 0.0
    for row in saved["per_mode"]:
        i = row["mode"]
        if abs(row["f_GHz"] - f_GHz[i - 1]) > 1e-12 * abs(f_GHz[i - 1]) or \
                abs(row["abs_p"] - abs_p[i - 1]) > 1e-12 * abs(abs_p[i - 1]):
            out.append(f"mode {i}: f_GHz or abs_p disagrees with the committed columns")
        term = row["abs_p"] * row["f_GHz"] ** 2
        if abs(row["abs_p_f2_GHz2"] - term) > 1e-12 * term:
            out.append(f"mode {i}: abs_p_f2_GHz2 is not abs_p x f_GHz^2")
        total += row["abs_p_f2_GHz2"]
    if abs(saved["A_partial_GHz2"] - total) > 1e-12 * total:
        out.append("A_partial_GHz2 is not the sum of its per-mode terms")
    expected = rm.unit_scales(4.0e-3)
    tc = doc["expected_scales"]["expected_exact_from_Lc_4mm"]["tc_ns"]
    if abs(tc - expected["tc_ns"]) > 1e-12 * expected["tc_ns"]:
        out.append("the proposal's tc disagrees with unit_scales")
    if abs(saved["A_partial_nd_at_expected_tc"] * expected["A_GHz2_per_nd"]
           - saved["A_partial_GHz2"]) > 1e-9 * saved["A_partial_GHz2"]:
        out.append("the proposal's nd and GHz2 saved moments are inconsistent")
    return out


#: Every document the regeneration test checks, and how.
REGENERATED = {
    "reference_model.json": ("json", _reference_model_float_rule, _reference_model_invariants),
    "proposal.json": ("json", lambda p, n, o: _stable(p, n, o), _proposal_invariants),
    "fixture_evaluation.json": ("json", None, None),   # rules built from the document
    "config.candidate.json": ("bytes", None, None),
    "config.delta.txt": ("bytes", None, None),
}


def regeneration_mismatches(name: str, new_text: str, old_text: str, rm) -> list[str]:
    """Every failure for one regenerated document, each naming its path."""
    kind, float_rule, invariants = REGENERATED[name]
    if kind == "bytes":
        return [] if new_text == old_text else [f"{name}: not byte-identical"]
    new, old = json.loads(new_text), json.loads(old_text)

    def named(messages):
        return [f"{name}{m}" if m.startswith("/") else f"{name}: {m}" for m in messages]

    shape = _compare(new, old)
    if shape:
        return named(shape)
    if name == "fixture_evaluation.json":
        float_rule, invariants = _fixture_float_rule(new), _fixture_invariants
    out = _compare(new, old, float_rule)
    if invariants:
        out += invariants(new, rm)
    return named(out)


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

def test_the_offline_scripts_are_deterministic_and_cannot_launch_anything(rm):
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

    # EVERY generated document, each through the guard that knows what its numbers mean
    outputs = {FMD / name: (FMD / name).read_text() for name in REGENERATED}
    try:
        for name, extra in (("reference_model.py", []), ("prepare.py", []),
                            ("evaluate_record.py", ["--fixture"])):
            proc = subprocess.run([sys.executable, str(FMD / name), *extra],
                                  capture_output=True, text=True, cwd=REPO_ROOT)
            assert proc.returncode == 0, proc.stderr
        for p, before in outputs.items():
            mismatches = regeneration_mismatches(p.name, p.read_text(), before, rm)
            assert mismatches == [], mismatches
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


#: The paths in fixture_evaluation.json that carry the first moment's units. A COMMON
#: SCALE ERROR - a wrong normalising length, a factor dropped from the functional - scales
#: all of them together and nothing else. The document then stays internally consistent
#: AND regenerates itself exactly, because the faulty calculation reproduces its own
#: answer. Only a recomputation by an independent route can reject it.
MOMENT_SCALED_PATHS = (
    "/truth/A_total_nd",
    "/truth/A_saved_nd",
    "/truth/omitted_first_moment_exact_nd",
    "/evaluator/A_direct_minus_A_saved_nd",
    "/evaluator/certified_omitted_moment_lower_bound_nd",
    "/evaluator/error_vs_truth_nd",
    "/negative_discrepancy/difference_GHz2",
    "/negative_discrepancy/threshold_GHz2",
    "/full_evaluation_of_the_good_record/checks[26]/detail/A_nd",
    "/full_evaluation_of_the_good_record/checks[26]/detail/A_GHz2",
    "/full_evaluation_of_the_good_record/checks[27]/detail/lower_nd",
    "/full_evaluation_of_the_good_record/checks[27]/detail/A_nd",
    "/full_evaluation_of_the_good_record/checks[27]/detail/err_ub_nd",
    "/full_evaluation_of_the_good_record/A_direct/A_nd",
    "/full_evaluation_of_the_good_record/A_direct/A_GHz2",
    "/full_evaluation_of_the_good_record/A_direct/certified_lower_bound_GHz2",
    "/full_evaluation_of_the_good_record/A_saved/central_GHz2",
    "/full_evaluation_of_the_good_record/difference/A_direct_minus_A_saved_GHz2",
    "/full_evaluation_of_the_good_record/difference/certified_omitted_moment_lower_bound_GHz2",
    "/full_evaluation_of_the_good_record/difference/materially_negative_threshold_GHz2",
    "/full_evaluation_of_the_good_record/mass_solve_uncertainty/x_dot_r_nd",
    "/full_evaluation_of_the_good_record/mass_solve_uncertainty/certified_error_upper_bound_GHz2",
    "/full_evaluation_of_the_good_record/mass_solve_uncertainty/certified_lower_bound_A_GHz2",
    "/full_evaluation_of_the_good_record/mass_solve_uncertainty/uncertified_error_estimate_GHz2",
    "/full_evaluation_of_the_good_record/A_saved_uncertainty/central_GHz2",
    "/full_evaluation_of_the_good_record/A_saved_uncertainty/printed_precision_interval_GHz2[0]",
    "/full_evaluation_of_the_good_record/A_saved_uncertainty/printed_precision_interval_GHz2[1]",
    "/full_evaluation_of_the_good_record/A_saved_uncertainty/halfwidth_GHz2",
)


def _at(doc, path: str):
    """(container, key) for a /a/b[3]/c path, so the leaf can be read or written."""
    node, keys = doc, path.lstrip("/").split("/")
    for i, key in enumerate(keys):
        last = i == len(keys) - 1
        if key.endswith("]"):
            key, idx = key[:-1].split("[")
            if last:
                return node[key], int(idx)
            node = node[key][int(idx)]
        else:
            if last:
                return node, key
            node = node[key]
    raise AssertionError(path)


def _scale_the_moment(doc: dict, k: float) -> dict:
    """Apply a common scale error, consistently, including the rendered interpretation."""
    for path in MOMENT_SCALED_PATHS:
        node, key = _at(doc, path)
        node[key] *= k
    bound = doc["full_evaluation_of_the_good_record"]["difference"][
        "certified_omitted_moment_lower_bound_GHz2"]
    doc["evaluator"]["interpretation"] = re.sub(
        r"\d\.\d+e[+-]\d\d", f"{bound:.6e}", doc["evaluator"]["interpretation"])
    return doc


def test_the_regeneration_guard_rejects_corruption(rm):
    """A guard that only ever passes is worthless, so every class of failure is pinned.

    The five cases marked REGRESSION were all ACCEPTED by the float-skipping guard this
    replaces. Each is asserted here together with the check that rejects it, so a later
    simplification cannot quietly re-open the same hole. The legitimate round-off
    variations are the three actually measured across machines, not imagined ones, and
    they must still pass. No scientific threshold is relaxed to achieve that: the
    thresholds in RM_BOUNDS are the ones the dedicated tests assert.
    """
    committed = {name: (FMD / name).read_text() for name in REGENERATED}
    for name, text in committed.items():
        assert regeneration_mismatches(name, text, text, rm) == [], name
    FIXTURE, RM, PROPOSAL = "fixture_evaluation.json", "reference_model.json", "proposal.json"

    def guard(name, doc):
        return regeneration_mismatches(name, json.dumps(doc), committed[name], rm)

    def mutated(name, mutate):
        bad = json.loads(committed[name])
        mutate(bad)
        return guard(name, bad)

    # --- the legitimate variations: all three measured, all must PASS -----------------
    for label, mutate in {
        # run 35553777395: a cancellation residue near 6e-20 that moved 7 percent when
        # the LAPACK eigen driver was swapped
        "cancellation residue":
            lambda d: d["evaluator"].__setitem__("error_vs_truth_nd", 5.381306e-20),
        # run 35554886550: the exact value the runner produced
        "negative-discrepancy threshold":
            lambda d: d["negative_discrepancy"].__setitem__(
                "threshold_GHz2", -1.6511520418429716e-13),
        # run 35556211180: the committed value moved by the 5.9e-04 that run measured
        # (the runner's own value was reported as a relative move, not recorded)
        "perturbed-solve residual":
            lambda d: d["full_evaluation_of_the_good_record"]["checks"][16]["detail"]
                .__setitem__("relative_residual", 1.279034924178295e-13 * (1 + 5.9e-4)),
    }.items():
        assert mutated(FIXTURE, mutate) == [], label
    # and a round-off-level trial maximum that lands elsewhere but inside its threshold
    assert mutated(RM, lambda d: d["worst_case"].__setitem__(
        "dual_assembly_vs_GetVoltage", 9.126e-16)) == []

    # --- and the requirements those variations satisfy are not vacuous ---------------
    # Each noise field pushed just outside the requirement that states what it MEANS.
    exercised = set()
    for path, value, why in (
        ("/evaluator/error_vs_truth_nd", 1.8e-07,
         "a residue as large as the moment it qualifies"),
        ("/full_evaluation_of_the_good_record/difference/"
         "materially_negative_threshold_GHz2", 1.6511527189666263e-13,
         "a materiality threshold that is not negative"),
        ("/full_evaluation_of_the_good_record/mass_solve_uncertainty/x_dot_r_nd", 1e-10,
         "an x.r at 2e-05 of A_nd, far above round-off"),
        ("/negative_discrepancy/threshold_GHz2", 1.6511527189666263e-13,
         "a threshold that is not negative"),
        ("/full_evaluation_of_the_good_record/checks[16]/detail/relative_residual", 1e-06,
         "a residual of a solve that did not converge"),
        ("/full_evaluation_of_the_good_record/mass_solve_uncertainty/"
         "uncertified_error_estimate_GHz2", 0.0,
         "an error estimate that is not positive"),
        ("/full_evaluation_of_the_good_record/mass_solve_uncertainty/"
         "certified_error_upper_bound_GHz2", 1e-05,
         "a certified bound at 1 percent of A"),
        ("/full_evaluation_of_the_good_record/mass_solve_uncertainty/"
         "sufficient_condition_for_the_estimate_to_be_a_bound/threshold", 1.0,
         "an order-one ||r||/||x||"),
        ("/full_evaluation_of_the_good_record/checks[27]/detail/err_ub_nd", 1e-07,
         "a certified bound at 2 percent of A_nd"),
    ):
        bad = json.loads(committed[FIXTURE])
        node, key = _at(bad, path)
        node[key] = value
        found = guard(FIXTURE, bad)
        assert any("fails its requirement" in m and path in m for m in found), (why, found)
        exercised.add(path)
    # every noise field has a requirement AND a negative control for it
    assert exercised == set(_fixture_noise_rules(json.loads(committed[FIXTURE]))), \
        exercised ^ set(_fixture_noise_rules(json.loads(committed[FIXTURE])))

    # --- REGRESSION: the five corruptions the float-skipping guard accepted -----------
    A_GHz2 = json.loads(committed[FIXTURE])[
        "full_evaluation_of_the_good_record"]["A_direct"]["A_GHz2"]
    for label, mutate, expected in (
        ("a significant output multiplied by 100",
         lambda d: d["full_evaluation_of_the_good_record"]["A_direct"].__setitem__(
             "A_GHz2", A_GHz2 * 100),
         "/full_evaluation_of_the_good_record/A_direct/A_GHz2"),
        ("the same float replaced by a string",
         lambda d: d["full_evaluation_of_the_good_record"]["A_direct"].__setitem__(
             "A_GHz2", "not a number"),
         "type str != float"),
        ("NaN where a finite difference is required",
         lambda d: d["evaluator"].__setitem__("A_direct_minus_A_saved_nd", float("nan")),
         "is not finite"),
        ("-infinity where a finite bound is required",
         lambda d: d["evaluator"].__setitem__(
             "certified_omitted_moment_lower_bound_nd", float("-inf")),
         "is not finite"),
        ("an integer count becoming a float",
         lambda d: d["fixture"].__setitem__("n_modes_saved", 999.0),
         "type float != int"),
    ):
        found = mutated(FIXTURE, mutate)
        assert found, f"ACCEPTED: {label}"
        assert any(expected in m for m in found), (label, expected, found)

    # --- a COMMON SCALE ERROR, which regeneration alone can never catch ---------------
    # Every quantity carrying the moment's units is scaled by 5 percent in BOTH the
    # committed reference and the regenerated document, so the fault reproduces itself.
    scaled = json.dumps(_scale_the_moment(json.loads(committed[FIXTURE]), 1.05))
    structural = _compare(json.loads(scaled), json.loads(scaled),
                          _fixture_float_rule(json.loads(scaled)))
    assert structural == [], structural  # reproduces itself exactly: nothing to compare
    internal = [m for m in _fixture_invariants(json.loads(scaled), rm)
                if "independent dense solve" not in m]
    assert internal == [], internal      # and stays internally consistent throughout
    found = regeneration_mismatches(FIXTURE, scaled, scaled, rm)
    assert len(found) == 1 and "independent dense solve" in found[0], found

    # the same fault in the proposal, caught by the committed eigensolver columns
    def scale_proposal(d):
        saved = d["A_saved_from_committed_columns"]["A_all_saved_modes"]
        saved["A_partial_GHz2"] *= 1.05
        saved["A_partial_nd_at_expected_tc"] *= 1.05
        for row in saved["per_mode"]:
            row["abs_p_f2_GHz2"] *= 1.05
    bad = json.loads(committed[PROPOSAL])
    scale_proposal(bad)
    found = regeneration_mismatches(PROPOSAL, json.dumps(bad), json.dumps(bad), rm)
    assert any("independent sum over the committed columns" in m for m in found), found

    # --- discrete edits: every one caught AND named ----------------------------------
    for label, name, mutate in (
        ("verdict string", FIXTURE,
         lambda d: d["evaluator"].__setitem__("verdict", "NOT_RESOLVED")),
        ("boolean", FIXTURE, lambda d: d["evaluator"].__setitem__(
            "certified_lower_bound_is_below_the_truth", False)),
        ("a boolean becoming an integer", RM, lambda d: d["error_qualification"]["trials"]
            .__setitem__("cg_like_solution_A_hat_never_exceeds_A_exact", 1)),
        ("check name", FIXTURE, lambda d: d["full_evaluation_of_the_good_record"]
            ["checks"][0].__setitem__("check", "something else")),
        ("a check's passed flag", FIXTURE, lambda d: d["full_evaluation_of_the_good_record"]
            ["checks"][0].__setitem__("passed", False)),
        ("missing key", FIXTURE, lambda d: d["evaluator"].pop("verdict")),
        ("shortened list", FIXTURE, lambda d: d["full_evaluation_of_the_good_record"]
            .__setitem__("checks", d["full_evaluation_of_the_good_record"]["checks"][:-1])),
        ("mode count", FIXTURE, lambda d: d["fixture"].__setitem__("n_modes_saved", 999)),
        ("a certified-bound violation count", RM,
         lambda d: d["error_qualification"]["trials"].__setitem__(
             "certified_bound_violations", 1)),
        ("DIAG_ZERO padding no longer singular", RM,
         lambda d: d["worst_case"].__setitem__(
             "padded_DIAG_ZERO_singular_in_every_trial", False)),
        ("a counterexample that no longer demonstrates the failure", RM,
         lambda d: d["error_qualification"]["counterexamples_to_the_old_quantity"][0]
            .__setitem__("estimate_is_a_bound", True)),
        ("a digest", PROPOSAL,
         lambda d: d["the_one_execution"]["image"].__setitem__("patch_sha256", "0" * 64)),
    ):
        found = mutated(name, mutate)
        assert found, f"ACCEPTED: {label}"
        assert found[0].startswith(f"{name}/"), (label, found)

    # --- wrong numbers, each named with the check that rejects it ---------------------
    for label, name, mutate, expected in (
        ("the measured difference off by 1e-6", FIXTURE,
         lambda d: d["evaluator"].__setitem__(
             "A_direct_minus_A_saved_nd",
             d["evaluator"]["A_direct_minus_A_saved_nd"] * (1 + 1e-6)),
         "/evaluator/A_direct_minus_A_saved_nd"),
        ("a certified bound above the truth", FIXTURE,
         lambda d: d["evaluator"].__setitem__(
             "certified_omitted_moment_lower_bound_nd",
             d["truth"]["omitted_first_moment_exact_nd"] * 1.001),
         "the certified lower bound exceeds the truth"),
        ("truth internally inconsistent", FIXTURE,
         lambda d: d["truth"].__setitem__("A_saved_nd", d["truth"]["A_saved_nd"] * 1.001),
         "A_total - A_saved != omitted"),
        ("the nested A_GHz2 no longer its A_nd times the unit scale", FIXTURE,
         lambda d: d["full_evaluation_of_the_good_record"]["checks"][26]["detail"]
            .__setitem__("A_GHz2", 1.0),
         "checks[26] A_GHz2 is inconsistent with its A_nd"),
        ("the summary difference no longer the nested one", FIXTURE,
         lambda d: d["evaluator"].__setitem__(
             "A_direct_minus_A_saved_nd",
             d["truth"]["omitted_first_moment_exact_nd"] * (1 + 1e-7)),
         "summary difference != nested difference"),
        ("A_saved outside its printed-precision interval", FIXTURE,
         lambda d: d["full_evaluation_of_the_good_record"]["A_saved_uncertainty"]
            .__setitem__("printed_precision_interval_GHz2", [1.0, 2.0]),
         "outside its printed-precision interval"),
        ("a scientific threshold no longer met", RM,
         lambda d: d["worst_case"].__setitem__("dual_assembly_vs_GetVoltage", 1e-6),
         "fails < 1e-12"),
        ("a one-sided threshold breached from below", RM,
         lambda d: d["worst_case"].__setitem__(
             "K_port_minus_qq_min_eig_same_rule_min", -1.0),
         "fails >= -1e-12"),
        ("the proposal's nd and GHz2 moments inconsistent", PROPOSAL,
         lambda d: d["A_saved_from_committed_columns"]["A_all_saved_modes"].__setitem__(
             "A_partial_nd_at_expected_tc",
             d["A_saved_from_committed_columns"]["A_all_saved_modes"]
             ["A_partial_nd_at_expected_tc"] * 1.001),
         "nd and GHz2 saved moments are inconsistent"),
        ("a per-mode term that is not its own product", PROPOSAL,
         lambda d: d["A_saved_from_committed_columns"]["A_all_saved_modes"]["per_mode"][0]
            .__setitem__("abs_p", 0.5),
         "disagrees with the committed columns"),
    ):
        found = mutated(name, mutate)
        assert found, f"ACCEPTED: {label}"
        assert any(expected in m for m in found), (label, expected, found)

    # Two reference-model invariants say what the document must CLAIM, not what it must
    # reproduce, so they still bite when the committed copy carries the same regression.
    doc = json.loads(committed[RM])
    doc["worst_case"]["padded_DIAG_ZERO_singular_in_every_trial"] = False
    doc["error_qualification"]["counterexamples_to_the_old_quantity"][0][
        "estimate_is_a_bound"] = True
    found = regeneration_mismatches(RM, json.dumps(doc), json.dumps(doc), rm)
    assert any("no longer singular in every trial" in m for m in found), found
    assert any("no longer demonstrates the failure" in m for m in found), found
    doc = json.loads(committed[PROPOSAL])
    doc["the_one_execution"]["image"]["patch_sha256"] = "0" * 64
    found = regeneration_mismatches(PROPOSAL, json.dumps(doc), json.dumps(doc), rm)
    assert any("patch_sha256 does not match" in m for m in found), found

    # The interpretation renders the certified bound as text. An edited string is caught
    # by the discrete comparison above, so the tie between the text and the number it
    # renders is asserted directly on the invariant that makes it.
    doc = json.loads(committed[FIXTURE])
    doc["evaluator"]["interpretation"] = doc["evaluator"]["interpretation"].replace(
        "2.491579e-05", "9.999999e-05")
    assert any("not the certified lower bound" in m for m in _fixture_invariants(doc, rm))

    # --- the two byte-compared documents ---------------------------------------------
    for name in ("config.candidate.json", "config.delta.txt"):
        text = committed[name]
        assert regeneration_mismatches(name, text.replace("0", "1", 1), text, rm) == \
            [f"{name}: not byte-identical"], name

    # The one place a float survives into a compared STRING: the interpretation renders
    # the certified lower bound. It is rendered to 7 significant digits while the bound
    # itself varies across machines at 1e-13 relative (measured on CI run 35553777395),
    # six orders of margin. Pinned so the rendering cannot quietly gain digits.
    rendered = re.findall(r"(\d\.\d+)e[+-]\d\d",
                          json.loads(committed[FIXTURE])["evaluator"]["interpretation"])
    assert rendered
    for mantissa in rendered:
        assert len(mantissa.replace(".", "")) <= 7, mantissa
