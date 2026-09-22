"""The direct first-moment diagnostic: prepared and verified on fixtures, not executed."""

from __future__ import annotations

import ast
import contextlib
import copy
import csv
from fractions import Fraction
import hashlib
import importlib.util
import inspect
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FMD = REPO_ROOT / "experiments" / "first-moment-diagnostic"
#: the NATIVE qualification record, historical evidence: the image
#: qualification writes outside the repository and never overwrites it.
COMPILED_QUALIFICATION_SHA256 = "9f1c77964494ea7d66a52c7a3ab48a1ec02e4b59db658ec443a5bc8248c390f1"
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
#   gate    - a maximum over random trials at round-off level whose size is stable across
#             BLAS kernels and eigen drivers (measured); required to satisfy its declared
#             scientific threshold, unchanged from the dedicated tests
#   diagnostic - a maximum whose size is set by the conditioning of the DRAWN mode, which
#             the document does not record; required to be a finite non-negative float,
#             with the identity it measures gated by named live tests (RM_FIELDS)

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
# Every bounded float is a maximum over seeded random trials of the residual of an exact
# identity. Each is mapped to what it verifies and to one specific check. Measured across
# 18 configurations - OPENBLAS_CORETYPE default, HASWELL, SANDYBRIDGE, PRESCOTT, NEHALEM
# and SKYLAKEX, each with numpy's eigh and scipy's 'ev' and 'evr' drivers - the
# regenerated maxima fall into two classes (min..max over the 18 in each entry):
#
#   gate        stable: spread <= 5x and at least 380x inside the declared threshold,
#               which is applied to the regenerated value unchanged, with the strict
#               operator the dedicated test uses on the committed record.
#   diagnostic  set by the conditioning of the DRAWN fixture or mode - the port-voltage
#               cancellation kappa2, up to 2.5e4 in the seeded trials, or the eigensolver's
#               accuracy on the smallest kept eigenvalue and on the kernel - which the
#               document does not record and the BLAS kernel changes:
#               epr_palace_vs_absolute_square is 2.5e-15 on one kernel and 2.232e-12, the
#               CI run 35559951610 value bit for bit, on HASWELL. Its regenerated
#               MAGNITUDE therefore carries no machine-reproducible information and is not
#               gated here: it must be a finite, non-negative float, and the identity it
#               measures is gated by the named live tests, where the answer is exact or
#               the conditioning is measured. The declared threshold stays asserted on the
#               COMMITTED record by test_the_reference_model_record_is_reproduced_and_
#               within_tolerance; that alone gates no regeneration, hence the named tests.

RM_FIELDS = {
    "/worst_case/dual_assembly_vs_GetVoltage": (                      # 2.1e-16..1.0e-15
        "P^T v_loc . E reproduces GetVoltage on any complex field", ("gate", "<", 1e-12)),
    "/worst_case/free_restricted_functional_vs_GetVoltage_when_E_dbc_is_zero": (
        "the free-restricted functional is GetVoltage when E vanishes on dbc",
        ("gate", "<", 1e-12)),                                        # 2.6e-16..4.6e-16
    "/worst_case/padded_DIAG_ONE_zeroed_rhs_vs_free": (               # 2.7e-16..4.3e-16
        "the DIAG_ONE padded solve with a zeroed rhs is the free-dof form",
        ("gate", "<", 1e-12)),
    "/worst_case/padded_DIAG_ONE_unzeroed_rhs_minus_free_vs_sum_f_dbc2_over_L": (
        "an unzeroed rhs adds exactly sum f_dbc^2 / L", ("gate", "<", 1e-12)),  # ..4.2e-16
    "/worst_case/parseval_all_modes_vs_free_solve": (                 # 1.1e-15..2.6e-15
        "Parseval over the complete constrained basis is the free solve",
        ("gate", "<", 1e-12)),
    "/worst_case/parseval_nonzero_modes_vs_free_solve": (             # 1.1e-15..2.6e-15
        "zero modes carry no first-moment weight", ("gate", "<", 1e-12)),
    "/worst_case/kernel_annihilation_same_points": (                  # 4.4e-15..5.9e-14
        "f annihilates ker K (f lies in range K_port)",
        ("diagnostic", "test_the_diagonal_pencil_is_reproduced_exactly",
         "test_the_functional_lies_in_range_of_the_port_stiffness_and_annihilates_ker_k")),
    "/worst_case/K_port_minus_qq_min_eig_same_rule_min": (            # -1.5e-16..-8.7e-17
        "K_port >= q q^T when both use the same quadrature rule", ("gate", ">=", -1e-12)),
    "/worst_case/epr_palace_vs_absolute_square": (                    # 2.5e-15..2.2e-12
        "GetInductorParticipation equals |V|^2 / (L lam E^H M E)",
        ("diagnostic", "test_epr_palace_and_the_absolute_square_form_agree_as_scalar_algebra",
         "test_the_diagonal_pencil_is_reproduced_exactly",
         "test_the_epr_residuals_in_the_trial_sweep_are_bounded_by_their_measured_cancellation")),
    "/worst_case/epr_phase_invariance": (                             # 2.0e-13..4.8e-12
        # the same cancellation class, but its declared 1e-9 lies inside the derived
        # round-off bound on every seeded trial (asserted by the trial-sweep test), so the
        # declared threshold is provably safe here and stays a gate
        "|p| is invariant under a complex rescaling of the mode", ("gate", "<", 1e-9)),
    "/worst_case/A_phase_invariance": (                               # 2.8e-16..4.7e-16
        "the first moment is invariant under per-mode phases", ("gate", "<", 1e-12)),
    "/worst_case/unit_roundtrip_A_GHz2": (                            # 4.7e-16
        "A_GHz2 = sum p f^2 round-trips through lambda_nd", ("gate", "<", 1e-12)),
    "/worst_case/zeroth_moment_vs_pseudoinverse": (                   # 3.4e-14..1.2e-13
        "the eigen-sum zeroth moment is f^T K^+ f / L",
        ("diagnostic", "test_the_diagonal_pencil_is_reproduced_exactly")),
    "/error_qualification/trials/identity_max_error_relative_to_A": (  # 5.2e-16..7.9e-16
        "A_computed - A_exact = (Re x^H r - r^H M^-1 r) / L", ("gate", "<", 1e-12)),
    "/error_qualification/trials/variational_equals_certified_max_rel": (  # ..4.9e-16
        "the variational lower bound is the certified lower bound", ("gate", "<", 1e-12)),
}


def _reference_model_float_rule(path: str, new: float, old: float) -> str | None:
    if path in RM_FIELDS:
        check = RM_FIELDS[path][1]
        if check[0] == "gate":
            _, op, limit = check
            ok = new < limit if op == "<" else new >= limit
            return None if ok else f"{path}: {new!r} fails {op} {limit:g}"
        return None if new >= 0.0 else f"{path}: {new!r} is negative"
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


# --- 3b. the EPR formulas: scalar algebra, known answers, and the round-off class ------
#
# CI run 35559951610 regenerated worst_case/epr_palace_vs_absolute_square as 2.232e-12
# against its declared 1e-12 while run 35559946775, the same commit, passed. Reproduced
# here BIT FOR BIT with OPENBLAS_CORETYPE=HASWELL (2.2320564950712836e-12). The field is
# a maximum over randomly drawn modes of a RELATIVE residual whose denominator is the
# drawn mode's port voltage |V|^2. The seeded trial with the weakest coupling has
# |V| = 7.2e-07 and a dot-product cancellation factor kappa2 = 2.5e4 (measured inside the
# loop, test_the_epr_residuals_in_the_trial_sweep_are_bounded_by_their_measured_
# cancellation), so its residual is round-off amplified by cancellation and set by the
# BLAS kernel's summation order - not a property of the formulas. Across 18 kernel x
# eigen-driver configurations every such residual stayed within 6.6 u kappa2.
#
# The tests therefore split by WHAT THEY VERIFY:
#   the algebra          - exact, scalar, explicit inputs         (section a)
#   the implementations  - exact, well-conditioned known answers  (section b)
#   the round-off class  - bounded by the cancellation it measures (section c)

U = 2.0 ** -53      # unit round-off, IEEE binary64, round to nearest


def _gamma(n: int) -> float:
    """Higham, Accuracy and Stability of Numerical Algorithms, 2nd ed. (SIAM, 2002),
    Lemma 3.1: gamma_n = n u / (1 - n u); with (3.5), for ANY summation order,
    |fl(x . y) - x . y| <= gamma_n sum_i |x_i y_i|."""
    return n * U / (1.0 - n * U)


def _epr_scalar(V: complex, L: float, omega: float, E_m: float) -> float:
    """The absolute-square form as scalar algebra, written here independently of the
    reference model: |V|^2 / (L omega^2 . 2 E_m), signed by Im V, because
    I = V / (i omega L) has Re I = Im V / (omega L)."""
    return math.copysign((V.real ** 2 + V.imag ** 2) / (L * omega ** 2 * 2.0 * E_m), V.imag)


def _ulps(a: float, b: float, n: int) -> bool:
    return abs(a - b) <= n * U * max(abs(a), abs(b))


# -- (a) scalar algebra ---------------------------------------------------------------

def test_epr_palace_and_the_absolute_square_form_agree_as_scalar_algebra(rm):
    """SCALAR ALGEBRA ONLY. Both formulas are fed the same explicitly known voltage and
    electric energy. This validates neither the voltage functional nor the energy
    assembly - those are the known-answer tests below - only that GetInductorParticipation
    as transcribed is |V|^2 / (L omega^2 2 E_m) with the sign of Im V."""
    # V = 3+4i: |V|^2 = 25; L = 2; omega = 3; E_m = 5  ->  p = 25 / (2 . 9 . 10) = 5/36,
    # I = V / (6i) = (4 - 3i) / 6, Re I = 2/3 > 0. Each expected value is computed by hand.
    cases = {
        (3 + 4j, 2.0, 3.0, 5.0): 5.0 / 36.0,
        (3 - 4j, 2.0, 3.0, 5.0): -5.0 / 36.0,        # Im V < 0 flips the sign ...
        (-3 + 4j, 2.0, 3.0, 5.0): 5.0 / 36.0,        # ... Re V does not
        (1 + 1j, 4.0, 0.5, 0.25): 4.0,               # 2 / (4 . 1/4 . 1/2)
        (6j, 3.0, 2.0, 1.5): 1.0,                    # 36 / (3 . 4 . 3)
        (-6j, 3.0, 2.0, 1.5): -1.0,
        (0.5 + 0.25j, 1.0, 1.0, 0.125): 1.25,        # (5/16) / (1 . 1 . 1/4)
    }
    for (V, L, om, Em), expected in cases.items():
        p = rm.epr_palace(V, L, om, Em)
        assert _ulps(p, expected, 16), (V, L, om, Em, p, expected)
        assert _ulps(_epr_scalar(V, L, om, Em), expected, 16)

    # phase rotation: |p| invariant, sign follows Im(V e^{i theta}); scalings: V -> cV
    # multiplies by |c|^2, E_m -> kE_m divides by k, L -> kL divides by k, omega -> k omega
    # divides by k^2.
    V, L, om, Em, p0 = 3 + 4j, 2.0, 3.0, 5.0, 5.0 / 36.0
    for k in range(1, 24):
        theta = k * math.pi / 12
        Vt = V * complex(math.cos(theta), math.sin(theta))
        if abs(Vt.imag) < 1e-12:
            continue
        p = rm.epr_palace(Vt, L, om, Em)
        assert _ulps(abs(p), p0, 64), theta          # a rotated V carries ~4 extra ops
        assert math.copysign(1.0, p) == math.copysign(1.0, Vt.imag), theta
    for c in (2.0, -3.0, 0.25 + 0.5j, 1j):
        assert _ulps(rm.epr_palace(c * V, L, om, Em), abs(c) ** 2 * p0
                     * math.copysign(1.0, (c * V).imag), 64), c
    assert _ulps(rm.epr_palace(V, L, om, 4 * Em), p0 / 4, 16)
    assert _ulps(rm.epr_palace(V, 4 * L, om, Em), p0 / 4, 16)
    assert _ulps(rm.epr_palace(V, L, 2 * om, Em), p0 / 4, 16)

    # negative controls: three wrong transcriptions, each O(1) off the hand answer
    I = V / (1j * om * L)
    wrong = {
        "|I| instead of |I|^2": 0.5 * L * abs(I) / Em,
        "the half-energy factor dropped": L * abs(I) ** 2 / Em,
        "omega instead of omega^2": abs(V) ** 2 / (L * om * 2 * Em),
    }
    for label, p in wrong.items():
        assert abs(p - p0) > 0.1 * p0, label


# -- (b) known-answer implementation coverage ------------------------------------------

def _known_port():
    """A port small enough to assemble by hand. Three TRUE dofs, four LOCAL dofs with
    local dof 3 a shared copy of true dof 0, two quadrature points, width 1/2, length 1/4
    (area 1/8), coefficient c = 1/w = 2, so a c = (1/8, 1/8) and
        v_loc  = Q^T (a c) = (1/8, 3/8, 1/2, 1/2)
        f_true = P^T v_loc = (5/8, 3/8, 1/2)         dof 0 accumulates 1/8 + 1/2
    All values are binary fractions, so every product and sum below is exact."""
    P = np.array([[1.0, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0]])
    Q = np.array([[1.0, 2, 0, 3], [0, 1, 4, 1]])
    w, l = 0.5, 0.25
    a = np.array([w * l / 2, w * l / 2])
    return P, Q, a, 1.0 / w


KNOWN_E = np.array([1 + 2j, -1 + 1j, 2 - 1j])
KNOWN_V = 1.25 + 1.125j       # 5/8 (1+2i) + 3/8 (-1+i) + 1/2 (2-i) = 5/4 + 9i/8


def test_get_voltage_and_the_assembled_functional_on_a_known_port(rm):
    """The local voltage form (GetVoltage on the local vector) and the true-dof
    functional (P^T v_loc . E) against a HAND answer, on a well-conditioned port: the
    terms of V have no cancellation to speak of, so an exact comparison is justified.
    Agreement between the two routes is NOT the criterion - a shared wrong input keeps
    them agreeing - the hand answer is."""
    P, Q, a, c = _known_port()
    v_loc = Q.T @ (a * c)
    assert np.array_equal(v_loc, [0.125, 0.375, 0.5, 0.5])
    f = rm.dual_assemble(P, v_loc)
    assert np.array_equal(f, [0.625, 0.375, 0.5])
    assert rm.voltage_palace(v_loc, P, KNOWN_E) == KNOWN_V
    assert rm.voltage_from_functional(f, KNOWN_E) == KNOWN_V

    # the shared local dof NOT accumulated: both routes still agree with each other and
    # both are wrong - the hand answer catches what route-vs-route cannot
    P_bad = P.copy()
    P_bad[3, 0] = 0.0
    f_bad = rm.dual_assemble(P_bad, v_loc)
    assert rm.voltage_palace(v_loc, P_bad, KNOWN_E) == rm.voltage_from_functional(f_bad, KNOWN_E)
    assert rm.voltage_from_functional(f_bad, KNOWN_E) != KNOWN_V
    # a factor of two in the coefficient, and in the weights
    for v_wrong in (Q.T @ (a * c / 2), Q.T @ (2 * a * c)):
        f_wrong = rm.dual_assemble(P, v_wrong)
        assert rm.voltage_palace(v_wrong, P, KNOWN_E) == rm.voltage_from_functional(f_wrong, KNOWN_E)
        assert abs(rm.voltage_from_functional(f_wrong, KNOWN_E) - KNOWN_V) > 0.4 * abs(KNOWN_V)
    # a common scaling of the whole assembly
    for k in (1.001, 3.0):
        assert abs(rm.voltage_from_functional(k * f, KNOWN_E) - KNOWN_V) >= (k - 1) * abs(KNOWN_V) * 0.999


def test_pec_restriction_on_the_known_port(rm):
    """With true dof 1 essential, the free-restricted functional is (5/8, 0, 1/2). It
    reproduces GetVoltage exactly when E vanishes on the essential dof, and the mismatch
    otherwise is exactly f_1 E_1 - the boundary term the driver must zero."""
    P, Q, a, c = _known_port()
    f = rm.dual_assemble(P, Q.T @ (a * c))
    dbc = np.array([1])
    f_free = rm.restrict_to_free(f, dbc)
    assert np.array_equal(f_free, [0.625, 0.0, 0.5])
    E0 = KNOWN_E.copy()
    E0[1] = 0.0
    # 5/8 (1+2i) + 1/2 (2-i) = 13/8 + 3i/4
    assert rm.voltage_from_functional(f_free, E0) == 1.625 + 0.75j
    assert rm.voltage_palace(Q.T @ (a * c), P, E0) == 1.625 + 0.75j
    assert rm.voltage_from_functional(f, KNOWN_E) - rm.voltage_from_functional(f_free, KNOWN_E) \
        == f[1] * KNOWN_E[1] == -0.375 + 0.375j
    # the padded solve with the rhs zeroed on dbc is the free-dof form (DIAG_ONE)
    M = np.array([[2.0, 1, 0], [1, 2, 1], [0, 1, 2]])
    assert _ulps(rm.first_moment_padded(M, f, dbc, 2.0, "DIAG_ONE", True),
                 rm.first_moment_free(M, f, dbc, 2.0), 16)


def test_electric_energy_normalisation_on_a_known_answer(rm):
    """GetElectricFieldEnergy is 0.5 (E_r^T M E_r + E_i^T M E_i). With M = diag(1,2,3) and
    E = (1+2i, -1+i, 2-i): E_r^T M E_r = 1 + 2 + 12 = 15, E_i^T M E_i = 4 + 2 + 3 = 9, so
    E_m = 12 and Re(E^H M E) = 24. With the tridiagonal M below: M E_r = (1, 1, 3),
    E_r . M E_r = 6; M E_i = (5, 3, -1), E_i . M E_i = 14; E_m = 10."""
    for M, Em in ((np.diag([1.0, 2.0, 3.0]), 12.0),
                  (np.array([[2.0, 1, 0], [1, 2, 1], [0, 1, 2]]), 10.0)):
        assert rm.electric_energy_palace(M, KNOWN_E) == Em
        assert np.real(np.vdot(KNOWN_E, M @ KNOWN_E)) == 2 * Em
        assert rm.electric_energy_palace(M, 2j * KNOWN_E) == 4 * Em      # E -> cE: |c|^2
        assert rm.electric_energy_palace(3 * M, KNOWN_E) == 3 * Em       # M -> kM: k
        # the half-energy factor dropped, and a factor of two in M, are both O(1) off
        assert np.real(np.vdot(KNOWN_E, M @ KNOWN_E)) - Em == Em
        assert rm.electric_energy_palace(2 * M, KNOWN_E) == 2 * Em


#: A diagonal pencil whose every answer is a small rational, verified with exact
#: arithmetic (fractions) before use:  lambda = (0, 2, 3); M-orthonormal modes
#: e_i / sqrt(M_i); (q . E_m)^2 = f_m^2 / (L M_m) = (0, 1/4, 1/6).
#:   A = sum (q.E_m)^2 = 5/12 = f^T M^-1 f / L        first moment, two routes
#:   N = sum_{lam>0} (q.E_m)^2 / lam = 13/72 = f^T K^+ f / L   zeroth moment, two routes
#:   p_2 = 1/8, p_3 = 1/18, and sum p_m = N            EPR per mode, and their total
PENCIL = dict(K=np.diag([0.0, 4.0, 9.0]), M=np.diag([1.0, 2.0, 3.0]),
              f=np.array([0.0, 1.0, 1.0]), L=2.0)
PENCIL_ANSWERS = dict(A=5 / 12, N=13 / 72, p={1: 1 / 8, 2: 1 / 18})


def _pencil_mismatches(rm, K, M, f, L, answers, scale_out: float = 1.0) -> list[str]:
    """Every pencil identity against its hand answer, each within 16 ulps. `scale_out`
    multiplies every computed moment, modelling a common scale error in the outputs."""
    out = []
    none = np.array([], dtype=int)

    def near(label, a, b):
        if not _ulps(a, b, 16):
            out.append(f"{label}: {a!r} != {b!r}")

    lam, E = rm.constrained_eigenbasis(K, M, none)
    near("A by the free solve", scale_out * rm.first_moment_free(M, f, none, L), answers["A"])
    A_all, A_nz = rm.parseval_first_moment(f, L, lam, E)
    near("A by Parseval", scale_out * A_all, answers["A"])
    near("A by Parseval over nonzero modes", scale_out * A_nz, answers["A"])
    near("N by the eigen-sum", scale_out * rm.zeroth_moment(f, L, lam, E), answers["N"])
    near("N by the pseudoinverse", scale_out * float(f @ np.linalg.pinv(K) @ f / L), answers["N"])
    total = 0.0
    for m, p_m in answers["p"].items():
        for c in (1.0 + 0j, 3.7 * np.exp(0.9j), -2j):          # complex scale and phase
            Ec = E[:, m] * c
            p_abs = rm.epr_from_functional(f, L, lam[m], M, Ec)
            p_pal = rm.epr_palace(rm.voltage_from_functional(f, Ec), L, math.sqrt(lam[m]),
                                  rm.electric_energy_palace(M, Ec))
            near(f"mode {m} EPR by the absolute-square form (c={c})", scale_out * p_abs, p_m)
            near(f"mode {m} EPR by GetInductorParticipation (c={c})", scale_out * abs(p_pal), p_m)
        total += rm.epr_from_functional(f, L, lam[m], M, E[:, m].astype(complex))
    near("the EPRs sum to the zeroth moment", scale_out * total, answers["N"])
    if rm.kernel_annihilation(K, f) != 0.0:                    # f = (0,1,1) is exactly _|_ e_1
        out.append("f does not annihilate ker K exactly")
    return out


def test_the_diagonal_pencil_is_reproduced_exactly(rm):
    """Well-conditioned known answers for every quantity the round-off class qualifies:
    kappa2 = 1 for each mode, so 16 ulps is the justified requirement, and the answers
    are hand-verified rationals rather than a previous run."""
    P = PENCIL
    assert _pencil_mismatches(rm, P["K"], P["M"], P["f"], P["L"], PENCIL_ANSWERS) == []
    # the mutations that must fail, each caught by the hand answers
    faults = {
        "the functional doubled": dict(f=2 * P["f"]),                   # A, N, p all x4
        "the inductance doubled": dict(L=2 * P["L"]),                   # A, N, p all /2
        "the mass doubled": dict(M=2 * P["M"]),                         # A /2, lam /2 ...
        "the stiffness doubled": dict(K=2 * P["K"]),                    # N, p /2
        "a shared dof dropped from the functional": dict(f=np.array([0.0, 1.0, 0.0])),
    }
    for label, change in faults.items():
        args = {**P, **change}
        found = _pencil_mismatches(rm, args["K"], args["M"], args["f"], args["L"], PENCIL_ANSWERS)
        assert found, f"ACCEPTED: {label}"
    for k in (1.05, 100.0):                                            # every output scaled
        assert _pencil_mismatches(rm, P["K"], P["M"], P["f"], P["L"], PENCIL_ANSWERS, k), k
    # and a GENUINE invariance, pinned so the test is known not to be unit-sensitive:
    # (f, L, M, K) -> k (f, L, M, K) leaves A, N and every EPR unchanged
    for k in (0.3, 7.0):
        assert _pencil_mismatches(rm, k * P["K"], k * P["M"], k * P["f"], k * P["L"],
                                  PENCIL_ANSWERS) == [], k


# -- (c) the round-off class ------------------------------------------------------------

def _voltage_conditioning(f: np.ndarray, E: np.ndarray) -> tuple[float, float]:
    """kappa2 and kappa3 of V = f . E, from the sums S_r = sum |f_i Re E_i| and
    S_i = sum |f_i Im E_i|: the error of |V|^2 evaluated from rounded components is
    exactly 2 V_r d_r + 2 V_i d_i + d_r^2 + d_i^2 with |d| <= gamma_n S, so
    |fl(|V|^2) - |V|^2| / |V|^2 <= 2 gamma_n kappa2 + gamma_n^2 kappa3."""
    V = complex(f @ E.real, f @ E.imag)
    S_r, S_i = float(np.abs(f * E.real).sum()), float(np.abs(f * E.imag).sum())
    v2 = abs(V) ** 2
    return (abs(V.real) * S_r + abs(V.imag) * S_i) / v2, (S_r ** 2 + S_i ** 2) / v2


def _energy_conditioning(M: np.ndarray, E: np.ndarray) -> float:
    """kappa_M = sum_ij |E_i| |M_ij| |E_j| / Re(E^H M E), over the real and imaginary
    parts: a matvec then a dot, each within gamma_n of its absolute-value sum, gives
    |fl(x^T M x) - x^T M x| <= 3 gamma_n sum_ij |x_i M_ij x_j|."""
    A = np.abs(M)
    T = float(np.abs(E.real) @ A @ np.abs(E.real) + np.abs(E.imag) @ A @ np.abs(E.imag))
    return T / float(E.real @ M @ E.real + E.imag @ M @ E.imag)


def _epr_round_off_bound(n: int, kappa2: float, kappa3: float, kappa_M: float) -> float:
    """Relative error of ONE evaluation of p = |V|^2 / (L lam 2 E_m) from its rounded
    parts: the |V|^2 term above, the energy term (with gamma_2n, covering the complex
    route's length-2n real accumulation), and at most 16 elementary operations in the
    scalar tail (sqrt, the complex division, abs, square, three products/quotients),
    each within u. First two are Higham (3.5)-derived; the tail is an operation count."""
    g, g2 = _gamma(n), _gamma(2 * n)
    return 2 * g * kappa2 + g * g * kappa3 + 3 * g2 * kappa_M + 16 * U


def test_the_voltage_dot_product_error_is_bounded_by_its_measured_cancellation(rm):
    """A NEAR-ZERO voltage: forty terms of order one whose exact sum is ~1e-9. Each
    route's error is measured against the EXACT sum of the double inputs (fractions), so
    nothing rests on the routes agreeing with each other. The requirement is Higham's
    (3.5) with the measured sum of |f_i E_i| - an ABSOLUTE bound. The relative error is
    what the cancellation makes it and is reported, not asserted small."""
    rng = np.random.default_rng(20260921)
    n = 40
    f = rng.uniform(0.5, 1.5, size=n) / 3.0            # not binary fractions: products round
    parts = []
    for _ in range(2):
        E = rng.uniform(-1.0, 1.0, size=n) / 7.0
        s = sum(Fraction(x) * Fraction(y) for x, y in zip(f[:-1], E[:-1]))
        E[-1] = float((Fraction(1, 10 ** 9) - s) / Fraction(f[-1]))   # cancel to ~1e-9
        parts.append(E)
    E = parts[0] + 1j * parts[1]
    exact = [sum(Fraction(x) * Fraction(y) for x, y in zip(f, p)) for p in parts]
    S = [float(np.abs(f * p).sum()) for p in parts]
    assert all(abs(float(e)) < 2e-9 for e in exact), exact
    kappa2, _ = _voltage_conditioning(f, E)
    assert kappa2 > 1e6, kappa2                        # a genuinely ill-conditioned sum
    routes = {"functional": rm.voltage_from_functional(f, E),
              "vdot": complex(np.vdot(f, E)),
              "local, P = I": rm.voltage_palace(f, np.eye(n), E)}
    for label, V in routes.items():
        for comp, e, s in ((V.real, exact[0], S[0]), (V.imag, exact[1], S[1])):
            err = abs(Fraction(comp) - e)
            assert err <= _gamma(n) * s, (label, float(err), _gamma(n) * s,
                                          f"relative {float(err / abs(e)):.1e}")
    # the bound is not vacuous: one term dropped, or a factor of two, is far outside it
    assert abs(Fraction(float(f[:-1] @ E.real[:-1])) - exact[0]) > 100 * _gamma(n) * S[0]
    assert abs(Fraction(2 * routes["vdot"].real) - exact[0]) > 100 * _gamma(n) * S[0]


def test_the_epr_residuals_in_the_trial_sweep_are_bounded_by_their_measured_cancellation(rm):
    """The gate for epr_palace_vs_absolute_square and epr_phase_invariance, placed where
    the cancellation can be MEASURED: inside the reference model's own trial loop, by
    wrapping the four functions each trial calls - no replication of the random sequence.
    Every residual must satisfy _epr_round_off_bound with the kappas of its own inputs.
    The pairing is checked against the loop's own maxima bit for bit, and the bound's
    strength is pinned: it rejects any error above 1e-8, ten orders below a factor of two.
    Measured here across the 18 BLAS-kernel x eigen-driver configurations listed at
    RM_FIELDS: every palace-vs-absolute residual within 6.6 u kappa2 and every phase
    residual within 3 u (kappa2 + kappa2'), the bound never closer than 67x to any of
    them, and 4.0e-10 at its largest."""
    calls, state = [], {}
    orig = {k: getattr(rm, k) for k in
            ("voltage_from_functional", "electric_energy_palace", "epr_palace",
             "epr_from_functional")}

    def voltage(f, E):
        state["V"] = _voltage_conditioning(f, E) + (f.size,)
        return orig["voltage_from_functional"](f, E)

    def energy(M, E):
        state["M"] = _energy_conditioning(M, E)
        return orig["electric_energy_palace"](M, E)

    def palace(V, L, om, Em):
        p = orig["epr_palace"](V, L, om, Em)
        k2, k3, n = state["V"]
        calls.append({"p_pal": p, "B_pal": _epr_round_off_bound(n, k2, k3, state["M"]),
                      "kappa2": k2})
        return p

    def absolute(f, L, lam, M, E):
        p = orig["epr_from_functional"](f, L, lam, M, E)
        k2, k3 = _voltage_conditioning(f, E)
        B = _epr_round_off_bound(f.size, k2, k3, _energy_conditioning(M, E))
        slot = "abs" if "p_abs" not in calls[-1] else "abs0"
        calls[-1][f"p_{slot}"], calls[-1][f"B_{slot}"] = p, B
        return p

    try:
        for name, fn in (("voltage_from_functional", voltage), ("electric_energy_palace", energy),
                         ("epr_palace", palace), ("epr_from_functional", absolute)):
            setattr(rm, name, fn)
        worst = rm.run_trials()
    finally:
        for name, fn in orig.items():
            setattr(rm, name, fn)

    assert len(calls) == rm.TRIALS and all("p_abs0" in c for c in calls)
    r_pal, r_phase, bounds = [], [], []
    for c in calls:
        r1 = abs(abs(c["p_pal"]) - c["p_abs"]) / c["p_abs"]
        r2 = abs(c["p_abs"] - c["p_abs0"]) / c["p_abs0"]
        b1 = (c["B_pal"] + c["B_abs"]) / (1 - c["B_abs"])       # the divisor is p_abs, not p
        b2 = (c["B_abs"] + c["B_abs0"]) / (1 - c["B_abs0"])
        assert r1 <= b1, ("palace vs absolute square", r1, b1, c["kappa2"])
        assert r2 <= b2, ("phase invariance", r2, b2, c["kappa2"])
        r_pal.append(r1), r_phase.append(r2), bounds.append(max(b1, b2))
    # the wrapper saw exactly what the loop recorded
    assert max(r_pal) == worst["epr_palace_vs_absolute_square"]
    assert max(r_phase) == worst["epr_phase_invariance"]
    # the bound has teeth: nothing above 1e-8 could pass it, on any trial
    assert max(bounds) <= 1e-8, max(bounds)
    # and the declared 1e-9 for epr_phase_invariance is inside the bound on every trial
    assert max((c["B_abs"] + c["B_abs0"]) / (1 - c["B_abs0"]) for c in calls) < 1e-9


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


def trigger_filter_paths(workflow: Path) -> list[str]:
    """Every path a workflow's push/pull_request triggers filter on.

    This is what decides whether a commit can START the workflow. A path named
    anywhere else in the file - the Dockerfile a manually dispatched build builds,
    a comment, a step argument - cannot start anything.
    """
    import yaml

    data = yaml.safe_load(workflow.read_text()) or {}
    on = data.get("on", data.get(True)) or {}           # PyYAML reads bare `on` as True
    out: list[str] = []
    for event in ("push", "pull_request"):
        spec = on.get(event) or {}
        if isinstance(spec, dict):
            out += list(spec.get("paths") or [])
            out += list(spec.get("paths-ignore") or [])
    return out


def test_a_trigger_filter_naming_an_owned_path_is_rejected(tmp_path: Path):
    """The negative control for the narrowing above: the guard still catches the thing
    it exists to catch, and does not catch a dispatch-only workflow that merely names
    the file it builds."""
    caught = tmp_path / "caught.yml"
    caught.write_text(
        "name: x\non:\n  push:\n    branches: ['palace/**']\n"
        "    paths:\n      - docker/palace-first-moment.Dockerfile\njobs: {}\n")
    assert "docker/palace-first-moment.Dockerfile" in trigger_filter_paths(caught)

    pr = tmp_path / "pr.yml"
    pr.write_text("name: x\non:\n  pull_request:\n    paths:\n"
                  "      - experiments/first-moment-diagnostic/run_diagnostic.py\njobs: {}\n")
    assert "experiments/first-moment-diagnostic/run_diagnostic.py" in trigger_filter_paths(pr)

    allowed = tmp_path / "allowed.yml"
    allowed.write_text(
        "name: x\non:\n  workflow_dispatch:\njobs:\n  b:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: docker build -f docker/palace-first-moment.Dockerfile .\n")
    assert trigger_filter_paths(allowed) == [], "a dispatch-only build names it, triggers on nothing"


def test_the_build_workflow_is_dispatch_only_and_runs_no_qmhp_input():
    """The workflow the owner authorised: it must never acquire a push, pull_request or
    schedule trigger, and must not name a QMHP scientific input."""
    import yaml

    wf = REPO_ROOT / ".github" / "workflows" / "first-moment-image.yml"
    assert wf.is_file()
    data = yaml.safe_load(wf.read_text())
    on = data.get("on", data.get(True))
    assert sorted(on) == ["workflow_dispatch"], on
    # WIDENED ONCE, 2026-09-22, under the owner's authorisation to requalify the
    # PRESERVED image: `actions: read` is what lets the run fetch that image from the
    # artefact store of run 35691886143 instead of rebuilding it. The property this
    # guard exists for is unchanged and is now asserted directly rather than implied by
    # a one-key map: no scope may be write.
    assert data["permissions"] == {"contents": "read", "actions": "read"}, data["permissions"]
    for scope, level in data["permissions"].items():
        assert level == "read", (scope, level)
    assert "write" not in yaml.safe_dump(data["permissions"])
    text = wf.read_text()
    # Checked on the EXECUTABLE lines only. The header comment names
    # EXECUTION-APPROVAL.json deliberately, to say the workflow neither creates nor
    # reads it, and PALACE_IMAGE_INFO_DIR to say it is deliberately not passed. A
    # whole-file grep would forbid the file from explaining itself.
    executable = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    for forbidden in ("COUPLED-LADDER", "COUPLED-PILOT", "PALACE-GOLDEN", "results/",
                      "EXECUTION-APPROVAL.json", "ladder-approval", "pilot-approval",
                      "coupled_chip_cell", "PALACE_IMAGE_INFO_DIR="):
        assert forbidden not in executable, forbidden
    # and it must not overwrite the committed NATIVE qualification record
    assert "--out " in text and "$RUNNER_TEMP/image_qualification.json" in text


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
    # Every workflow's TRIGGER is checked against the owned paths. What this protects
    # is that no ordinary commit can start anything by touching the diagnostic: no
    # owned path may appear in a push/pull_request `paths` filter, and no workflow may
    # take an unfiltered push on a branch pattern this repository uses.
    #
    # NARROWED, 2026-09-22, under the owner's authorisation of one build-and-
    # qualification workflow. It previously asserted the owned paths appeared nowhere
    # in a workflow's TEXT at all. That protected the preparation-only state - "no
    # workflow builds this image" - by forbidding the file from being named, which is
    # strictly stronger than forbidding it from being a trigger, and which a manually
    # dispatched build workflow cannot satisfy while still naming the Dockerfile it
    # builds. The protection itself is unchanged and is checked here directly on the
    # parsed `on:` block; `test_a_trigger_filter_naming_an_owned_path_is_rejected`
    # below applies the exact mutation this guard exists to catch.
    for wf in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        for path in owned:
            assert path not in trigger_filter_paths(wf), (wf.name, path)
    # No UNCOMMITTED change may touch a path that triggers a solver workflow - with one
    # exemption, pinned exactly: the build-and-qualification workflow the owner
    # authorised on 2026-09-22. It lives under `.github/workflows/`, which is itself a
    # trigger path, so without naming it this assertion fails for as long as that file
    # is staged and passes again once committed - a guard whose verdict depends on
    # commit timing rather than on what changed. Every other trigger path, including
    # every other workflow, is still guarded.
    authorised = ".github/workflows/first-moment-image.yml"
    assert (REPO_ROOT / authorised).is_file(), "the exemption names a file that must exist"
    changed = subprocess.run(["git", "diff", "--name-only", "HEAD"], capture_output=True,
                             text=True, cwd=REPO_ROOT).stdout.split()
    offending = [c for c in changed if c != authorised
                 and any(c.startswith(t) for t in triggers)]
    assert not offending, offending


def test_the_trigger_path_exemption_is_exactly_one_file(proposal):
    """The exemption above must not widen. Any other workflow, and both approval files,
    stay guarded."""
    triggers = proposal["workflow_trigger_paths_untouched"]
    for still_guarded in (".github/workflows/palace-golden.yml",
                          ".github/workflows/palace-order1-ladder.yml",
                          ".github/workflows/ci.yml",
                          ".github/ladder-approval.json",
                          ".github/pilot-approval.json",
                          "docker/palace.Dockerfile",
                          "solvers/palace/adapter.py"):
        assert any(still_guarded.startswith(t) for t in triggers), still_guarded
        assert still_guarded != ".github/workflows/first-moment-image.yml"




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


# --- 5d. the qualification DECISION ---------------------------------------------------
#
# Collecting fixture results and printing them is not qualifying an image. Before the
# decision existed, compiled_qualification.py's main() returned 0 whatever the fixtures
# did, and the workflow step that runs it read "the command succeeded" as "the image
# qualified". Reproduced at the pre-fix SHA 220aac00c9ff67711f0aff093715832bfd6a7bb7 in
# a detached worktree: with a mock palace and no Palace anywhere, a 50% wrong A, a
# fixture that exited 3, a fixture that wrote no record at all, a failed functional
# check and a developer-build provenance ALL exited 0.
#
# These tests drive the same mock through the real command and check the EXIT STATUS,
# not just a helper. The mock writes the record the real compiled binary wrote, taking
# its numbers from the committed native qualification record, and each mode spoils
# exactly one thing.

MOCK_PALACE = '''#!/usr/bin/env python3
"""A MOCK palace. Runs no FEM: it recognises which synthetic fixture config it was
handed and writes the record the real compiled binary wrote for it. MOCK_FM_MODE
spoils exactly one thing."""
import json, os, sys
from pathlib import Path

MODE = os.environ.get("MOCK_FM_MODE", "good")
cwd = Path.cwd()
cfg = json.loads((cwd / "config.json").read_text())
port = cfg["Boundaries"]["LumpedPort"][0]
L_H, active = port["L"], port.get("Active", True)
maxits = cfg["Solver"]["FirstMoment"]["MaxIts"]
argv = sys.argv[1:]
np_ranks = int(argv[argv.index("-np") + 1]) if "-np" in argv else 1
name = "D" if not active else "C" if maxits == 1 else "B" if L_H == 1e-08 else "A"

print(f"mock palace: fixture {name}, np={np_ranks}, mode={MODE}")
print("Initialization                   0.006       0.006       0.006")
post = cwd / "postpro"
post.mkdir(parents=True, exist_ok=True)

PROV = {"ConfigMesh": "fm_synthetic.msh", "ImageInfoDir": "/opt/palace",
        "ImageInfoDirIsDefault": True, "MpiSize": np_ranks,
        "PALACE_COMMIT": "a61c8cbe0cacf496cde3c62e93085fae0d6299ac",
        "PALACE_PATCH": "first-moment-diagnostic",
        "PALACE_PATCH_SHA256":
            "e8a1ad51d4e355b0426e84c70cb9c796a4915b1216bb035d5fe60913de512fee",
        "PALACE_VERSION": "0.13.0"}
SCALES = {"A_GHz2_per_nd": 569.1433657156557, "FrequencyScale_GHz": 23.85672579621218,
          "InductanceScale_H": 2.5132741228718347e-09, "Lc_m": 0.002,
          "tc_ns": 0.00667128190395536}
SOLNORM = 42.14286916348303
SPEC = {
    "A": dict(A_nd=64.16250164577238, A_GHz2=36517.66213941119, clb=64.16250164577238,
              xr=-3.480182745601994e-16, conv=True, its=32,
              relres=1.2459756972030213e-12, gap=0.9433754934463132,
              L_nd=0.3978873577297383),
    "B": dict(A_nd=6.416250164577237, A_GHz2=3651.7662139411186, clb=6.416250164577237,
              xr=-3.480182745601994e-16, conv=True, its=32,
              relres=1.2459756972030213e-12, gap=0.9939660838546912,
              L_nd=3.9788735772973833),
    "C": dict(A_nd=54.2087085166793, A_GHz2=30852.52681628179, clb=54.208708516679316,
              xr=-6.3976601794024646e-15, conv=False, its=1,
              relres=0.4129210005633967, gap=0.9069987035151496,
              L_nd=0.3978873577297383),
}

if name == "D":
    (post / "first-moment-FAILED.json").write_text(json.dumps(
        {"Diagnostic": "FirstMoment", "Status": "FAILED",
         "Reason": "no active lumped port with nonzero inductance",
         "Provenance": PROV}, indent=1))
    print("no active lumped port with nonzero inductance", file=sys.stderr)
    sys.exit(1)
if MODE == "crash" and name == "A":
    print("mock: segmentation fault in the mass solve", file=sys.stderr)
    sys.exit(3)
if MODE == "no_record" and name == "A":
    print("mock: exiting 0 without writing a record", file=sys.stderr)
    sys.exit(0)

s = dict(SPEC[name])
if MODE in ("wrong_A", "deflated_A") and name == "A":
    f = 1.5 if MODE == "wrong_A" else 0.5
    s["A_nd"] *= f; s["A_GHz2"] *= f; s["clb"] *= f
if MODE == "developer_build":
    PROV = dict(PROV, ImageInfoDir="/host/palace-good", ImageInfoDirIsDefault=False)
if MODE == "unreviewed_binary":
    PROV = dict(PROV, PALACE_COMMIT="deadbeef" * 5)
func_rel, func_pass = ((1e-3, False) if MODE == "functional_broken" and name == "A"
                       else (0.0, True))
if MODE == "nan" and name == "A":
    s["A_nd"] = float("nan")

resnorm = s["relres"] * SOLNORM
rec = {
    "Diagnostic": "FirstMoment", "Status": "COMPLETED", "Provenance": PROV,
    "Port": {"Index": 1, "L_nd": s["L_nd"], "L_H": L_H, "NumElements": 26},
    "Dofs": {"True": 663, "Essential": 129, "Free": 534},
    "Scales": SCALES,
    "Functional": {"NormSquaredFull": 0.5601841337765997,
                   "NormSquaredFree": 0.5374534814822652,
                   "NormSquaredEssential": 0.022730652294334464,
                   "Check": {"RelativeError": func_rel, "Passed": func_pass}},
    "LinearSolve": {"Type": "PCG+Jacobi on M(DIAG_ONE)", "RelTol": 1e-12,
                    "MaxIts": maxits, "Iterations": s["its"], "Converged": s["conv"],
                    "SolverFinalRes": s["relres"], "ResidualNorm": resnorm,
                    "RhsNorm": 0.7331121887, "RelativeResidual": s["relres"],
                    "SolutionNorm": SOLNORM, "SolutionEssentialNorm": 0.0},
    "A": {"A_nd": s["A_nd"], "A_GHz2": s["A_GHz2"],
          "ErrorIdentity": "A_computed - A_exact = (Re(x^H r) - r^H M^-1 r)/L",
          "XDotR_nd": s["xr"],
          "CertifiedErrorUpperBound_nd": "UNAVAILABLE",
          "CertifiedErrorUpperBound_GHz2": "UNAVAILABLE",
          "CertifiedLowerBound_A_nd": s["clb"],
          "CertifiedLowerBound_A_GHz2": s["clb"] * SCALES["A_GHz2_per_nd"],
          "UncertifiedErrorEstimate_nd": resnorm * SOLNORM / s["L_nd"],
          "UncertifiedErrorEstimate_GHz2": 0.0, "CertifiedUpperBound": "UNAVAILABLE"},
    "NullSpaceCheck": {"Enabled": True, "IsSampledNotProof": True,
                       "MinRelativeGap": s["gap"]},
    "Resources": {"WallTime_s": 0.46, "MaxRSS_MB": 120.0},
}
if MODE == "truncated_record" and name == "A":
    rec.pop("NullSpaceCheck")
(post / "first-moment.json").write_text(json.dumps(rec, indent=1))
sys.exit(0)
'''

#: Each mode spoils exactly one thing, and names the check that must catch it.
SPOILED_MODES = {
    "wrong_A": "A agrees with the independent assembly",
    "deflated_A": "A agrees with the independent assembly",
    "crash": "exited 0",
    "no_record": "wrote a first-moment record",
    "functional_broken": "the functional check passed",
    "developer_build": "not a developer build",
    "unreviewed_binary": "carries the reviewed Palace identity",
    "truncated_record": "matches the declared schema",
    "nan": "the record is finite",
}


@pytest.fixture(scope="module")
def mock_palace(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("mock-palace") / "palace"
    p.write_text(MOCK_PALACE)
    p.chmod(0o755)
    return p


def run_qualification(mock: Path, out_dir: Path, mode: str) -> tuple[int, dict | None]:
    """The REAL command, end to end, against the mock. Returns its exit status and the
    report it wrote - which is what the workflow step's success or failure comes from."""
    out = out_dir / "report.json"
    proc = subprocess.run(
        [sys.executable, str(FMD / "compiled_qualification.py"),
         "--palace", str(mock), "--workroot", str(out_dir / "work"), "--out", str(out)],
        capture_output=True, text=True, cwd=REPO_ROOT,
        env=dict(os.environ, MOCK_FM_MODE=mode))
    report = json.loads(out.read_text()) if out.is_file() else None
    return proc.returncode, report


def test_a_faithful_image_qualification_exits_zero_and_says_QUALIFIED(mock_palace, tmp_path):
    rc, report = run_qualification(mock_palace, tmp_path, "good")
    assert rc == 0, report
    d = report["decision"]
    assert d["decision"] == "QUALIFIED" and d["qualified"] is True
    assert d["failed"] == []
    assert len(d["checks"]) > 40, "the decision must actually check things"
    # the committed NATIVE record is not what was judged, and was not written to
    assert _sha256(FMD / "compiled_qualification.json") == COMPILED_QUALIFICATION_SHA256


@pytest.mark.parametrize("mode", sorted(SPOILED_MODES))
def test_a_spoiled_image_qualification_exits_nonzero_and_says_NOT_QUALIFIED(
        mock_palace, tmp_path, mode):
    """The pre-fix behaviour, mode by mode: every one of these exited 0 at
    220aac00c9ff67711f0aff093715832bfd6a7bb7."""
    rc, report = run_qualification(mock_palace, tmp_path, mode)
    assert rc != 0, f"{mode} was accepted"
    d = report["decision"]
    assert d["decision"] == "NOT QUALIFIED" and d["qualified"] is False
    assert any(SPOILED_MODES[mode] in f for f in d["failed"]), (mode, d["failed"])
    # evidence before presentation: the report survives the refusal
    assert report["runs"], "the fixture results must be kept even when it refuses"


def test_the_decision_agrees_with_the_committed_native_qualification(compiled):
    """The control that the criteria are neither stricter nor looser than what this
    repository already accepted: the historical NATIVE qualification record, real
    compiled output, passes every check when judged on its own terms - and is refused
    under the default for exactly one reason, that it is a developer build."""
    mod = _load("compiled_qualification")
    lenient = mod.decide(compiled, require_in_image_identity=False)
    assert lenient["decision"] == "QUALIFIED", lenient["failed"]
    strict = mod.decide(compiled)
    assert strict["decision"] == "NOT QUALIFIED"
    assert all("developer build" in f for f in strict["failed"]), strict["failed"]
    assert len(strict["failed"]) == 3, "one per fixture that wrote a record"


def test_an_intended_failure_passes_but_an_arbitrary_crash_does_not(mock_palace, tmp_path):
    """An intended failure fixture is not automatically a qualification failure:
    D-port-inactive exits 1 by design and the good run is QUALIFIED. An arbitrary crash
    is not the intended negative result either - it exits nonzero and writes no
    structured evidence, so the same fixture refuses."""
    mod = _load("compiled_qualification")
    rc, report = run_qualification(mock_palace, tmp_path, "good")
    assert rc == 0
    d = report["runs"]["D-port-inactive"]
    assert d["returncode"] != 0 and d["wrote_first_moment_json"] is False
    assert d["failed_record"]["Status"] == "FAILED"
    for spoil, why in (({"failed_record": None, "returncode": 139}, "a segfault"),
                       ({"failed_record": {"Status": "FAILED"}}, "no reason given"),
                       ({"failed_record_has_provenance": False}, "no provenance"),
                       ({"returncode": 0, "wrote_first_moment_json": True}, "it succeeded")):
        crashed = copy.deepcopy(report)
        crashed["runs"]["D-port-inactive"].update(spoil)
        out = mod.decide(crashed)
        assert out["decision"] == "NOT QUALIFIED", why
        assert any("D-port-inactive" in f for f in out["failed"]), why


def test_fault_injection_is_not_claimed_unless_it_actually_ran(mock_palace, tmp_path, compiled):
    """--faulted-palace is optional and the workflow does not pass it. The decision must
    say so rather than let its absence read as a pass."""
    mod = _load("compiled_qualification")
    _, report = run_qualification(mock_palace, tmp_path, "good")
    d = report["decision"]
    assert "fault_injection" not in report
    assert d["coverage"]["fault_injection"].startswith("NOT RUN")
    assert any("fault" in n for n in d["not_established"])
    assert not any("fault" in c["check"] for c in d["checks"]), (
        "an absent fault injection must produce no passing check")
    # and when it DID run, as in the committed native record, it is checked
    ran = mod.decide(compiled, require_in_image_identity=False)
    assert ran["coverage"]["fault_injection"] == "RAN"
    assert any("fault injection" in c["check"] and c["passed"] for c in ran["checks"])
    broken = copy.deepcopy(compiled)
    broken["fault_injection"]["caught_at"] = []
    assert mod.decide(broken, require_in_image_identity=False)["decision"] == "NOT QUALIFIED"


@pytest.mark.parametrize("report", [
    {}, {"runs": {}}, {"runs": "nonsense"}, {"runs": None},
    {"label": "no runs at all"},
])
def test_a_malformed_report_refuses(report):
    mod = _load("compiled_qualification")
    out = mod.decide(report)
    assert out["decision"] == "NOT QUALIFIED" and out["failed"]


def test_incomplete_coverage_refuses(mock_palace, tmp_path):
    """Missing fixtures, missing ranks and a rank that silently ran with the wrong
    number of processes are all refusals, not omissions."""
    mod = _load("compiled_qualification")
    _, good = run_qualification(mock_palace, tmp_path, "good")
    assert mod.decide(good)["decision"] == "QUALIFIED"
    for mutate, why in (
            (lambda r: r["runs"].pop("B-scaled-L"), "a fixture did not run"),
            (lambda r: r["mpi_sweep"].pop("np=4"), "a required rank did not run"),
            (lambda r: r["mpi_sweep"]["np=3"]["good"].update({"mpi_size": 1}),
             "a rank ran with the wrong process count"),
            (lambda r: r.pop("L_scaling"), "the 1/L scaling was not measured"),
            (lambda r: r["mpi_sweep"]["np=2"]["good"].update({"A_nd": 1.0}),
             "the ranks disagree")):
        spoiled = copy.deepcopy(good)
        mutate(spoiled)
        assert mod.decide(spoiled)["decision"] == "NOT QUALIFIED", why


def test_the_decision_uses_this_module_s_own_declared_tolerances():
    """No tolerance in the decision is new. Each one is the number this module already
    asserts against the committed record, read out of that test's source so the two
    cannot drift apart silently."""
    mod = _load("compiled_qualification")
    declared = inspect.getsource(test_the_compiled_diagnostic_matches_an_independent_assembly)
    assert 'r["relative_error_vs_independent"] < 1e-12' in declared
    assert 'r["functional_check_relative_error"] <= 1e-10' in declared
    assert 'compiled["L_scaling"]["relative_error"] < 1e-12' in declared
    nonconv = inspect.getsource(
        test_the_compiled_diagnostic_handles_non_convergence_and_failed_checks)
    assert 'c["relative_residual"] > 1e-3' in nonconv
    assert mod.REL_TO_INDEPENDENT == 1e-12
    assert mod.FUNCTIONAL_CHECK_REL == 1e-10
    assert mod.L_SCALING_REL == 1e-12
    assert mod.NONCONVERGENCE_RELRES == 1e-3
    assert mod.REQUIRED_MPI_RANKS == (1, 2, 3, 4)
    # every declared fixture has a declared expected outcome, so a fixture added later
    # cannot pass by being unclassified
    declared_fixtures = set(json.loads((FMD / "synthetic_fixture.json").read_text())["fixtures"])
    classified = set(mod.MUST_SUCCEED + mod.MUST_NOT_CONVERGE + mod.MUST_FAIL_CLOSED)
    assert declared_fixtures == classified, declared_fixtures ^ classified
    # and what has no declared criterion is named, not quietly given one
    assert len(mod.decide({"runs": {}})["undeclared_criteria"]) >= 2


def test_the_decision_cannot_be_relaxed_from_the_command_line():
    """require_in_image_identity is a keyword for the controls above, not a flag: there
    must be no way to accept a developer build by passing an argument."""
    src = (FMD / "compiled_qualification.py").read_text()
    tree = ast.parse(src)
    added = [n.args[0].value for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "add_argument" and n.args
             and isinstance(n.args[0], ast.Constant)]
    assert "--image-info-dir" in added, "the existing flags are unchanged"
    for forbidden in ("--allow-developer-build", "--no-decide", "--skip-decision",
                      "--require-in-image-identity", "--allow", "--force"):
        assert forbidden not in added, forbidden
    assert "require_in_image_identity" not in "".join(added)


# --- 5e. the build workflow's evidence, exit status and input handling ----------------

def workflow_steps() -> list[dict]:
    import yaml
    data = yaml.safe_load((REPO_ROOT / ".github" / "workflows" /
                           "first-moment-image.yml").read_text())
    return data["jobs"]["build-and-qualify"]["steps"]


def has_pipeline(body: str) -> bool:
    lines = [ln for ln in body.splitlines() if not ln.lstrip().startswith("#")]
    return "|" in "\n".join(lines).replace("||", "")


def test_no_dispatch_input_or_ref_text_reaches_shell_source():
    """GitHub substitutes ${{ }} as TEXT before bash parses the script, so an expression
    inside a `run:` body is source code, not data. Reproduced at
    220aac00c9ff67711f0aff093715832bfd6a7bb7: the refusal step interpolated
    inputs.confirm directly, and a confirmation of  x" ; touch INJECTED ; echo "  RAN
    before being refused."""
    for step in workflow_steps():
        body = step.get("run")
        if body:
            assert "${{" not in body, step.get("name")
    named = {step.get("name"): step for step in workflow_steps()}
    assert named["Refuse an unconfirmed dispatch"]["env"]["CONFIRM"] == "${{ inputs.confirm }}"
    env = named["Record what is actually checked out"]["env"]
    assert env["REF"] == "${{ github.ref }}" and env["REF_NAME"] == "${{ github.ref_name }}"


def test_shell_metacharacters_in_the_confirmation_stay_literal_and_are_refused(tmp_path):
    """Harmless and end to end: the step's ACTUAL body, run by bash, with hostile
    confirmation values. Nothing may execute, and the genuine string must still pass -
    a guard that refused everything would satisfy the first half alone."""
    step = {s.get("name"): s for s in workflow_steps()}["Refuse an unconfirmed dispatch"]
    script = tmp_path / "step.sh"
    script.write_text(step["run"])
    hostile = ['x" ; touch INJECTED ; echo "', "$(touch SUBST)", "`touch TICK`",
               "build-and-qualify; touch SEMI", "*"]
    for payload in hostile:
        proc = subprocess.run(["bash", str(script)], cwd=tmp_path, capture_output=True,
                              text=True, env={"CONFIRM": payload, "PATH": os.environ["PATH"]})
        assert proc.returncode == 1, payload
        assert "REFUSED" in proc.stderr, payload
    for marker in ("INJECTED", "SUBST", "TICK", "SEMI"):
        assert not (tmp_path / marker).exists(), f"{marker}: the payload executed"
    ok = subprocess.run(["bash", str(script)], cwd=tmp_path, capture_output=True, text=True,
                        env={"CONFIRM": "build-and-qualify", "PATH": os.environ["PATH"]})
    assert ok.returncode == 0, "the guard must still admit the real confirmation"


def test_every_workflow_pipeline_preserves_the_underlying_exit_status():
    for step in workflow_steps():
        body = step.get("run")
        if body and has_pipeline(body):
            assert "pipefail" in body, step.get("name")


def test_the_pipefail_guard_is_not_vacuous(tmp_path):
    """The construct the workflow used, and the one it uses now, on the same failure.
    Without this the test above would only be checking that a word appears."""
    masked = tmp_path / "masked.sh"
    masked.write_text('set -eux\n{ echo "d=$(sha256sum /no/such/file | cut -d\' \' -f1)"; }'
                      ' | tee out.txt\n')
    assert subprocess.run(["bash", str(masked)], cwd=tmp_path,
                          capture_output=True).returncode == 0
    assert (tmp_path / "out.txt").read_text().strip() == "d=", "an empty digest, recorded"
    guarded = tmp_path / "guarded.sh"
    guarded.write_text('set -euo pipefail\nsha() { sha256sum "$1" | cut -d\' \' -f1; }\n'
                       'd=$(sha /no/such/file)\necho "d=$d" > out2.txt\n')
    assert subprocess.run(["bash", str(guarded)], cwd=tmp_path,
                          capture_output=True).returncode != 0
    assert not (tmp_path / "out2.txt").exists()


def test_the_workflow_retains_the_full_qualification_evidence():
    """Raw solver logs, the executed fixture configurations and synthetic inputs, the
    result records and the structured FAILED records all live under qualify-work, which
    was not uploaded at all before 1bf0fbc. This run also retains what it measured about
    the launch: the topology, the shim it ran and the pointer to the image it restored."""
    steps = {s.get("name"): s for s in workflow_steps()}
    upload = steps["Upload every qualification artefact"]
    paths = [p.strip() for p in upload["with"]["path"].splitlines() if p.strip()]
    for needed in ("qualify-work", "qualification.log", "image_qualification.json",
                   "qualification-decision.txt", "evidence-manifest.txt",
                   "build-inputs.txt", "in_image_identity.txt", "image_id.txt",
                   "restored_image.txt", "topology.txt", "palace-in-container"):
        assert any(needed in p for p in paths), needed
    assert upload["if"] == "always()"
    assert steps["Collect the evidence, whatever the outcome"]["if"] == "always()"
    # The 200 MB image archive is NOT re-uploaded: it is already preserved under run
    # 35691886143 with the checksum this run verifies, and a second copy would be a
    # second thing to keep in step. restored_image.txt records where it came from.
    assert not any("palace-first-moment-0.13.0.tar.gz" in p for p in paths)
    assert upload["with"]["name"] == "first-moment-requalify-${{ github.run_id }}"
    # nor is the PREVIOUS run's retained evidence, which the restore step deletes so it
    # cannot be mistaken for this run's
    restore = steps["Restore the preserved image - checksum first, then image ID"]["run"]
    assert 'rm -rf "$RUNNER_TEMP/preserved/qualify-work"' in restore
    qual = steps["Synthetic qualification, through the preserved image"]["run"]
    assert "$RUNNER_TEMP/image_qualification.json" in qual
    # on the EXECUTABLE lines: the step's comment names the committed native record
    # deliberately, to say that this run does not overwrite it
    runnable = "\n".join(ln for ln in qual.splitlines() if not ln.lstrip().startswith("#"))
    assert "compiled_qualification.json" not in runnable


# --- 5f. the MPI launch correction ----------------------------------------------------
#
# Run 35691886143 qualified nothing at ranks 3 and 4: Open MPI refused them before Palace
# started, because it counts a SLOT as a processor CORE and the approved runner class
# offers fewer cores than hardware threads. The fix is one documented option, passed by
# the synthetic shim only for a parallel launch. Everything below drives the shim's real
# text with a MOCKED docker, so argument forwarding is established without a container,
# an image or a solver.

#: Quoted from /opt/palace/bin/palace inside the preserved image
#: sha256:5df2170a204ea2926f63639848751cb3ec4207520430b8ecdd529c239731dcf1 - the AWS Labs
#: launcher wrapper, Apache-2.0, wrapper sha256
#: 1907df1e90f38f4ece35040c06a3abdbc7b168c5e44545f1c6b7cd763436671d. These are the only
#: two facts about it the correction depends on. The workflow additionally asserts the
#: option against the wrapper IN THE IMAGE before qualifying, so this is a record of what
#: was read, not the only thing holding the change up.
WRAPPER_HELP = "--launcher-args ARGS           Any extra arguments to pass to MPI launcher"
WRAPPER_BUILDS_ITS_COMMAND_AS = ('MPIRUN="$(which $LAUNCHER) -n $NUM_PROCS"',
                                 'MPIRUN="$MPIRUN $LAUNCHER_ARGS"')

#: Verbatim first line of run 35691886143's qualify-work/mpi-good-3/palace_log.txt: what
#: the preserved wrapper ACTUALLY printed and ran. The model below is checked against it,
#: so it is not merely a restatement of how the wrapper was read.
OBSERVED_NP3_LAUNCH = "/usr/bin/mpirun -n 3 /opt/palace/bin/palace-x86_64.bin config.json"
OBSERVED_NP1_LAUNCH = "/opt/palace/bin/palace-x86_64.bin config.json"

IMAGE_REF = "qmhp-cem/palace-first-moment:0.13.0"


def wrapper_launch_command(argv, *, launcher="/usr/bin/mpirun",
                           binary="/opt/palace/bin/palace-x86_64.bin") -> str:
    """The preserved wrapper's documented construction, modelled from the two lines
    quoted above: it collects -np/-launcher/-launcher-args, treats everything else as the
    config, and for a parallel run emits `<launcher> -n <N> [<launcher args>] <bin> <cfg>`."""
    num_procs, launcher_args, serial, positional = "1", "", False, []
    rest = list(argv)
    while rest:
        key = rest.pop(0)
        if key in ("-serial", "--serial", "-sequential", "--sequential"):
            serial = True
        elif key in ("-np", "--np"):
            num_procs = rest.pop(0)
        elif key in ("-launcher", "--launcher"):
            launcher = rest.pop(0)
        elif key in ("-launcher-args", "--launcher-args"):
            launcher_args = rest.pop(0)
        else:
            positional.append(key)
    config = " ".join(positional)
    if serial:
        return f"{binary} {config}"
    mpirun = f"{launcher} -n {num_procs}"
    if launcher_args:
        mpirun = f"{mpirun} {launcher_args}"
    return f"{mpirun} {binary} {config}"


def shim_script(tmp_path: Path) -> Path:
    """The shim's REAL text, lifted out of the workflow's heredoc."""
    body = {s.get("name"): s for s in workflow_steps()}[
        "Container shim, so the harness qualifies the IMAGE and not a binary"]["run"]
    m = re.search(r"<<'SHIM'\n(.*?)\n\s*SHIM\n", body, re.S)
    assert m, "the shim heredoc was not found in the workflow"
    p = tmp_path / "palace-in-container"
    p.write_text(m.group(1) + "\n")
    p.chmod(0o755)
    return p


def mocked_container_runtime(tmp_path: Path) -> tuple[dict, Path]:
    """A recording stand-in for the container runtime, first on PATH. It writes the argv
    it was handed and exits 0, so the shim runs to completion with nothing launched."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    record = tmp_path / "argv.txt"
    mock = bindir / ("doc" + "ker")
    mock.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "' + str(record) + '"\nexit 0\n')
    mock.chmod(0o755)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
    return env, record


def run_shim(tmp_path: Path, *args: str) -> tuple[int, list[str], str]:
    shim = shim_script(tmp_path)
    env, record = mocked_container_runtime(tmp_path)
    if record.exists():
        record.unlink()
    proc = subprocess.run(["bash", str(shim), *args], capture_output=True, text=True,
                          cwd=tmp_path, env=env)
    forwarded = record.read_text().splitlines() if record.exists() else []
    return proc.returncode, forwarded, proc.stderr


def test_the_shim_forwards_a_serial_launch_completely_unchanged(tmp_path):
    """A serial launch never reaches mpirun, so it must not acquire a launcher option."""
    rc, argv, _ = run_shim(tmp_path, "--serial", "config.json")
    assert rc == 0
    assert argv[-3:] == [IMAGE_REF, "--serial", "config.json"], argv
    assert "--launcher-args" not in argv and "--oversubscribe" not in argv
    # and the wrapper would then run the binary directly, as it did at np=1
    assert wrapper_launch_command(argv[argv.index(IMAGE_REF) + 1:]) == OBSERVED_NP1_LAUNCH


@pytest.mark.parametrize("ranks", ["2", "3", "4"])
def test_the_shim_adds_the_documented_launcher_option_for_a_parallel_launch(tmp_path, ranks):
    rc, argv, _ = run_shim(tmp_path, "-np", ranks, "config.json")
    assert rc == 0
    # two argv entries, the flag and ONE value, because the wrapper reads its value as $2
    assert argv[-5:] == [IMAGE_REF, "--launcher-args", "--oversubscribe",
                         "-np", ranks, "config.json"][-5:], argv
    tail = argv[argv.index(IMAGE_REF) + 1:]
    assert tail == ["--launcher-args", "--oversubscribe", "-np", ranks, "config.json"]
    # and the option lands where Open MPI needs it: after -n N, before the binary
    assert wrapper_launch_command(tail) == (
        f"/usr/bin/mpirun -n {ranks} --oversubscribe "
        "/opt/palace/bin/palace-x86_64.bin config.json")


def test_the_wrapper_model_reproduces_what_the_preserved_wrapper_actually_printed():
    """The model is checked against the real logged launch line from run 35691886143, so
    the test above is not just a restatement of how the wrapper source was read."""
    assert wrapper_launch_command(["-np", "3", "config.json"]) == OBSERVED_NP3_LAUNCH
    assert wrapper_launch_command(["--serial", "config.json"]) == OBSERVED_NP1_LAUNCH
    # the option is inserted, not appended after the binary
    built = wrapper_launch_command(["--launcher-args", "--oversubscribe", "-np", "3",
                                    "config.json"])
    assert built.index("--oversubscribe") < built.index("palace-x86_64.bin")
    assert built == OBSERVED_NP3_LAUNCH.replace("-n 3 ", "-n 3 --oversubscribe ")


@pytest.mark.parametrize("bad", ["5", "8", "64"])
def test_the_shim_refuses_more_ranks_than_were_authorised_and_launches_nothing(tmp_path, bad):
    """Oversubscription was authorised for at most four ranks on one runner. The bound is
    checked, not assumed, and it refuses BEFORE the runtime is reached."""
    rc, argv, err = run_shim(tmp_path, "-np", bad, "config.json")
    assert rc == 1 and argv == [], (rc, argv)
    assert "at most 4 ranks" in err


@pytest.mark.parametrize("bad", ["x", "", "3; touch OWNED", "-1"])
def test_the_shim_refuses_a_rank_count_that_is_not_a_number(tmp_path, bad):
    rc, argv, err = run_shim(tmp_path, "-np", bad, "config.json")
    assert rc == 1 and argv == [], (rc, argv)
    assert "not a number" in err
    assert not (tmp_path / "OWNED").exists(), "a rank count was evaluated as shell"


def test_the_shim_still_withholds_the_image_info_dir(tmp_path):
    """The qualification is of the IMAGE. Passing PALACE_IMAGE_INFO_DIR would mark the run
    a developer build, and the decision refuses those - unchanged by this correction."""
    _, argv, _ = run_shim(tmp_path, "-np", "4", "config.json")
    assert not any("PALACE_IMAGE_INFO_DIR" in a for a in argv)
    assert "--network" in argv and argv[argv.index("--network") + 1] == "none"


def test_the_workflow_restores_the_pinned_image_and_never_rebuilds():
    steps = {s.get("name"): s for s in workflow_steps()}
    import yaml
    data = yaml.safe_load((REPO_ROOT / ".github" / "workflows"
                           / "first-moment-image.yml").read_text())
    assert data["permissions"] == {"contents": "read", "actions": "read"}
    env = data["env"]
    assert env["SOURCE_RUN_ID"] == "35691886143"
    assert env["SOURCE_ARTIFACT"] == "first-moment-image-35691886143"
    assert env["EXPECTED_ARCHIVE_SHA256"] == (
        "7e09f5028f4bc028b9aae52cbde6bc837e97c4d11c22622b590f04e764062834")
    assert env["EXPECTED_IMAGE_ID"] == (
        "sha256:5df2170a204ea2926f63639848751cb3ec4207520430b8ecdd529c239731dcf1")
    download = steps["Download the preserved image archive"]
    assert download["uses"].startswith("actions/download-artifact@")
    assert str(download["with"]["run-id"]) == "35691886143"
    restore = steps["Restore the preserved image - checksum first, then image ID"]["run"]
    assert "EXPECTED_ARCHIVE_SHA256" in restore and "ARCHIVE CHECKSUM MISMATCH" in restore
    assert "EXPECTED_IMAGE_ID" in restore and "IMAGE ID MISMATCH" in restore
    # no rebuild anywhere, and no fallback to one
    build = "doc" + "ker build"
    for step in workflow_steps():
        body = step.get("run") or ""
        runnable = "\n".join(ln for ln in body.splitlines()
                             if not ln.lstrip().startswith("#"))
        assert build not in runnable, step.get("name")


def test_the_workflow_measures_the_topology_it_must_not_infer():
    """nproc alone does not say how many slots Open MPI offers. The run records the core
    and thread counts, the MPI version and a DIRECT slot measurement, and fails closed if
    the preserved wrapper does not document the option the shim passes."""
    body = {s.get("name"): s for s in workflow_steps()}[
        "Record the CPU topology, the MPI version and the launch arguments"]["run"]
    for needed in ("lscpu", "nproc", "mpirun --version", "--oversubscribe",
                   "/opt/palace/bin/palace --help", "cpu.max"):
        assert needed in body, needed
    assert "/bin/true" in body, "the slot probe must not run a solver"
    assert "does not document --launcher-args" in body, "the assertion must fail closed"

def test_the_committed_native_qualification_record_is_untouched():
    """Historical evidence. The image qualification writes OUTSIDE the repository."""
    assert _sha256(FMD / "compiled_qualification.json") == COMPILED_QUALIFICATION_SHA256


def test_the_synthetic_fixture_is_not_the_qmhp_cell(synthetic):
    assert "NOT the QMHP-CEM coupled cell" in (FMD / "synthetic_fixture.py").read_text()
    assert synthetic["mesh"]["n_tets"] < 2000, "small by construction"
    src = (FMD / "synthetic_fixture.py").read_text()
    for token in ("results/", "COUPLED-LADDER", "coupled_chip_cell", "11.45"):
        assert token not in src, token
    cfg = json.loads((FMD / "fixtures" / "config-A-nominal.json").read_text())
    assert cfg["Domains"]["Materials"][1]["Permittivity"] == 4.0


# --- 6b. preparation only, offline and inert -----------------------------------------

# --- regeneration isolation ----------------------------------------------------------
#
# The regeneration checks used to run the offline scripts over the TRACKED reference
# files and restore them in a `finally`. That is unsafe in two ways this module now
# proves rather than asserts: two runs racing each other interleave their writes, and a
# process killed between the write and the restore leaves a tracked reference corrupted
# on disk, where it can be committed as though it were real. Both were observed: a
# concurrent suite run left reference_model.json with 16 changed floats in the working
# tree.
#
# The scripts take HERE = Path(__file__).resolve().parent and REPO = HERE.parents[1],
# and every one of their five write targets derives from HERE. So a disposable root
# that SYMLINKS each top-level repository entry except `experiments`, and under it each
# entry except this diagnostic's directory - which is a real 432 KiB copy - gives them
# the whole repository to READ while every write lands inside the copy. The tracked
# references are never opened for writing at all, so neither a race nor a kill -9 can
# reach them.

#: The offline scripts, in the order a regeneration runs them.
REGENERATION_SCRIPTS = (("reference_model.py", ()), ("prepare.py", ()),
                        ("evaluate_record.py", ("--fixture",)))


@contextlib.contextmanager
def isolated_repo_view():
    """Yield (root, fmd): a repository view whose only writable part is a copy of this
    diagnostic's directory. Everything else is a symlink to the real tree, read-only in
    practice because nothing the scripts run writes outside HERE."""
    with tempfile.TemporaryDirectory(prefix="qmhp-regen-") as tmp:
        root = Path(tmp) / "repo"
        root.mkdir()
        for entry in REPO_ROOT.iterdir():
            if entry.name != "experiments":
                (root / entry.name).symlink_to(entry)
        experiments = root / "experiments"
        experiments.mkdir()
        for entry in (REPO_ROOT / "experiments").iterdir():
            if entry.name != FMD.name:
                (experiments / entry.name).symlink_to(entry)
        fmd = experiments / FMD.name
        shutil.copytree(FMD, fmd, symlinks=True)
        yield root, fmd


def regenerate(root: Path, fmd: Path) -> None:
    """Run the three offline scripts inside an isolated view.

    The artefacts are EMPTIED in the copy first. Without that, a script that exits 0
    without writing would leave the copied committed content in place and every
    comparison against it would pass vacuously - the isolation would have removed the
    check rather than made it safe.
    """
    for name in REGENERATED:
        (fmd / name).write_text("")
    for name, extra in REGENERATION_SCRIPTS:
        proc = subprocess.run([sys.executable, str(fmd / name), *extra],
                              capture_output=True, text=True, cwd=root)
        assert proc.returncode == 0, (name, proc.stderr[-2000:])
    for name in REGENERATED:
        assert (fmd / name).read_text().strip(), f"{name} was not regenerated"


def tracked_reference_digests() -> dict[str, str]:
    """sha256 of every tracked artefact a regeneration would otherwise have written."""
    return {name: _sha256(FMD / name) for name in REGENERATED}


#: The git subcommands this module may run. Every one reports state; none checks out,
#: resets, cleans, stashes or writes. The launch-safety test pins this list.
GIT_READ_ONLY = ("status", "diff", "ls-files", "rev-parse")


def _git(*argv: str) -> str:
    assert argv and argv[0] in GIT_READ_ONLY, f"{argv[0]} is not a read-only git command"
    return subprocess.run(["git", *argv], cwd=REPO_ROOT, capture_output=True,
                          text=True, check=True).stdout


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

    # EVERY generated document, regenerated in a disposable view and compared there.
    # The tracked references are READ for the comparison and never written.
    committed = {name: (FMD / name).read_text() for name in REGENERATED}
    before = tracked_reference_digests()
    with isolated_repo_view() as (root, fmd):
        regenerate(root, fmd)
        for name in REGENERATED:
            mismatches = regeneration_mismatches(name, (fmd / name).read_text(),
                                                 committed[name], rm)
            assert mismatches == [], mismatches
    assert tracked_reference_digests() == before, "a regeneration wrote a tracked file"
    assert not list((REPO_ROOT / "results").rglob("first-moment*.json"))


def test_two_concurrent_regenerations_do_not_interfere(rm):
    """The race that was observed: a suite run and a driver sweep regenerating at once
    left reference_model.json with 16 changed floats in the working tree. Two isolated
    views cannot see each other, so each produces a complete, valid regeneration."""
    committed = {name: (FMD / name).read_text() for name in REGENERATED}
    before = tracked_reference_digests()
    produced: dict[int, dict[str, str]] = {}
    roots: dict[int, str] = {}
    failures: dict[int, BaseException] = {}
    barrier = threading.Barrier(2, timeout=300)

    def one(tag: int) -> None:
        try:
            with isolated_repo_view() as (root, fmd):
                roots[tag] = str(root)
                barrier.wait()          # both inside their own view before either writes
                regenerate(root, fmd)
                produced[tag] = {n: (fmd / n).read_text() for n in REGENERATED}
        except BaseException as exc:    # noqa: BLE001 - reported, not swallowed
            failures[tag] = exc
            with contextlib.suppress(threading.BrokenBarrierError):
                barrier.abort()

    threads = [threading.Thread(target=one, args=(t,)) for t in (0, 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=900)
    assert not failures, failures
    assert set(produced) == {0, 1} and roots[0] != roots[1]
    # each run is independently a valid regeneration, so neither read the other's
    # half-written file
    for tag, docs in produced.items():
        for name, text in docs.items():
            assert regeneration_mismatches(name, text, committed[name], rm) == [], (tag, name)
    # the byte-compared documents are deterministic, so the two runs agree exactly
    for name in REGENERATED:
        if REGENERATED[name][0] == "bytes":
            assert produced[0][name] == produced[1][name], name
    assert tracked_reference_digests() == before


def test_a_killed_regeneration_leaves_the_tracked_references_untouched(tmp_path):
    """Forced interruption. The first case is deterministic and is exactly the old
    failure mode: a writer that has ALREADY replaced the artefacts and is killed before
    it could restore them. Inside the isolated view that leaves real corruption - which
    is the point, the corruption exists and is nowhere near the repository."""
    before = tracked_reference_digests()
    stub = tmp_path / "corrupt_then_hang.py"
    stub.write_text("import sys, time\n"
                    "from pathlib import Path\n"
                    "fmd = Path(sys.argv[1])\n"
                    "for name in sys.argv[2:]:\n"
                    "    (fmd / name).write_text('CORRUPTED BY A KILLED WRITER\\n')\n"
                    "time.sleep(600)\n")
    with isolated_repo_view() as (root, fmd):
        proc = subprocess.Popen([sys.executable, str(stub), str(fmd), *REGENERATED],
                                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                with contextlib.suppress(OSError):
                    if all((fmd / n).read_text().startswith("CORRUPTED")
                           for n in REGENERATED):
                        break
                time.sleep(0.02)
            else:
                pytest.fail("the stub never wrote; the interruption proof would be vacuous")
            assert proc.poll() is None, "the stub exited instead of hanging mid-restore"
        finally:
            proc.kill()
            proc.wait(timeout=120)
        assert proc.returncode != 0
        for name in REGENERATED:                      # the corruption is real ...
            assert (fmd / name).read_text().startswith("CORRUPTED"), name
    assert tracked_reference_digests() == before      # ... and it never reached the repo

    # and the real script, killed while it works
    with isolated_repo_view() as (root, fmd):
        proc = subprocess.Popen([sys.executable, str(fmd / "reference_model.py")],
                                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            time.sleep(0.05)
            was_running = proc.poll() is None
        finally:
            proc.kill()
            proc.wait(timeout=120)
        assert was_running, "the script finished before the kill; nothing was interrupted"
    assert tracked_reference_digests() == before
    assert _git("status", "--porcelain", "--", "experiments/first-moment-diagnostic") == ""


def test_the_isolated_view_can_never_target_a_tracked_reference():
    """Structural, so the guarantee does not rest on the scripts behaving. Every
    artefact a regeneration writes resolves OUTSIDE the repository, the scripts run are
    the WORKING-TREE ones (not a checkout of HEAD, which would stop this test seeing an
    uncommitted change to them), and the rest of the repository is a symlinked read."""
    assert _git("status", "--porcelain", "--", "experiments/first-moment-diagnostic") == ""
    with isolated_repo_view() as (root, fmd):
        assert fmd.resolve() != FMD and REPO_ROOT not in fmd.resolve().parents
        for name in REGENERATED:
            target = (fmd / name).resolve()
            assert REPO_ROOT not in target.parents, (name, target)
            assert target.read_text() == (FMD / name).read_text(), name
        for name, _ in REGENERATION_SCRIPTS:
            assert not (fmd / name).is_symlink()
            assert (fmd / name).read_bytes() == (FMD / name).read_bytes(), name
        for shared in ("results", "docker", ".github"):
            assert (root / shared).is_symlink()
            assert (root / shared).resolve() == (REPO_ROOT / shared).resolve()
        assert (root / "experiments" / "fem-spectral-mapping").is_symlink()
        assert not (root / "experiments").is_symlink()
    # the disposable root is gone with its copy
    assert not Path(root).exists()


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
    """No test here can start a container, an MPI launcher or an arbitrary binary.

    Covers subprocess.Popen as well as subprocess.run: the isolation helpers added two
    Popen call sites and a git reader, and a guard that inspected only `run` would have
    stopped covering the file the moment it grew.
    """
    tree = ast.parse(Path(__file__).read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and ast.unparse(n.func) in ("subprocess.run", "subprocess.Popen")]
    argv = [ast.unparse(n.args[0]) for n in calls]
    assert len(argv) >= 6, argv
    for a in argv:
        if a.startswith("['git'"):
            # the one variadic git call is _git, which refuses anything but a read-only
            # subcommand at runtime; the literal call sites are pinned here
            assert a in ("['git', *argv]", "['git', 'diff', '--name-only', 'HEAD']"), a
            continue
        if a.startswith("['bash'"):
            # a shell script written into pytest's tmp_path by the test that runs it:
            # the build workflow's own refusal step, run to show that a hostile
            # confirmation stays data, and the two three-line scripts that show what a
            # trailing tee does to an exit status. Pinned literally, like the git calls,
            # and still subject to the container and MPI ban below.
            assert a in ("['bash', str(script)]", "['bash', str(masked)]",
                         "['bash', str(guarded)]", "['bash', str(shim), *args]"), a
            continue
        # a python interpreter running a script in this diagnostic's directory: the
        # tracked one, its disposable copy, the pinned inert launcher, or a test stub
        assert "sys.executable" in a, a
        assert any(t in a for t in ("FMD /", "fmd /", "str(fmd)", "launcher", "stub")), a
    # no test here shells out to a container runtime or an MPI launcher
    for a in argv:
        # `--palace` is a FLAG of the synthetic-only qualifier and the value given to it
        # is the mock this file writes, never a solver. That one literal pair is
        # exempted by text, so `'--palace', '/usr/bin/palace'` would still fail here.
        probe = a.replace("'--palace', str(mock)", "")
        for token in ("docker", "podman", "mpirun", "palace"):
            assert token not in probe, (token, a)
    # and the mock cannot launch anything either: it writes JSON and exits
    for token in ("docker", "podman", "mpirun", "subprocess", "Popen", "os.system"):
        assert token not in MOCK_PALACE, token
    # the one bash script whose text is not a literal in this file is the workflow's
    # refusal step, read from the workflow. It may not name either, so running it here
    # cannot start anything.
    refusal = {s.get("name"): s for s in workflow_steps()}["Refuse an unconfirmed dispatch"]
    for token in ("docker", "podman", "mpirun", "palace"):
        assert token not in refusal["run"], token
    # and the read-only git allowlist is exactly that: no writing verb may join it
    assert set(GIT_READ_ONLY) == {"status", "diff", "ls-files", "rev-parse"}
    for writer in ("checkout", "reset", "clean", "stash", "restore", "commit", "add"):
        assert writer not in GIT_READ_ONLY, writer
    assert "assert argv and argv[0] in GIT_READ_ONLY" in Path(__file__).read_text()


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
    they must still pass. No scientific threshold is relaxed to achieve that: the gates
    in RM_FIELDS are the thresholds the dedicated tests assert, and a diagnostic field's
    identity is gated by the live tests RM_FIELDS names.
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

    # --- the diagnostic fields: what the guard does and does not reject ---------------
    # A diagnostic's magnitude is set by the drawn mode's conditioning, so the guard
    # requires only a finite, non-negative float of it. A sign or type corruption is
    # rejected here; a magnitude corruption is NOT, and is pinned as accepted so that
    # the contract is explicit: the identity is gated by the tests RM_FIELDS names.
    diag = "/worst_case/epr_palace_vs_absolute_square"
    for value, expected in ((-1e-15, "is negative"), (float("nan"), "is not finite"),
                            ("0.0", "type str != float"), (True, "type bool != float")):
        bad = json.loads(committed[RM])
        bad["worst_case"]["epr_palace_vs_absolute_square"] = value
        found = guard(RM, bad)
        assert any(expected in m and diag in m for m in found), (value, found)
    bad = json.loads(committed[RM])
    bad["worst_case"]["epr_palace_vs_absolute_square"] = 1e-6
    assert guard(RM, bad) == [], "a diagnostic magnitude is not the guard's to gate"
    # ... and the identity behind it IS gated: a factor of two in any EPR fails the pencil
    assert _pencil_mismatches(rm, PENCIL["K"], PENCIL["M"], PENCIL["f"], PENCIL["L"],
                              {**PENCIL_ANSWERS, "p": {1: 2 / 8, 2: 2 / 18}})

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



def test_every_round_off_field_is_mapped_and_every_named_gate_exists(rm):
    """The field map cannot silently lose a field or point at a test that is not there.
    Every RM_FIELDS key exists in the committed record; every round-off-level float under
    worst_case and error_qualification/trials is in RM_FIELDS, so none is left to the
    stable rule by accident; every diagnostic names live tests defined in this module,
    and every gate's threshold is the one the dedicated record test asserts."""
    doc = json.loads((FMD / "reference_model.json").read_text())

    def leaf(path):
        node = doc
        for key in path.lstrip("/").split("/"):
            node = node[key]
        return node

    for path, (prop, check) in RM_FIELDS.items():
        v = leaf(path)
        assert isinstance(v, float) and not isinstance(v, bool), path
        assert prop and check[0] in ("gate", "diagnostic"), path
        if check[0] == "diagnostic":
            assert len(check) > 1, path
            for name in check[1:]:
                assert callable(globals().get(name)), (path, name)
        else:
            assert v < check[2] if check[1] == "<" else v >= check[2], (path, v)
    for section in ("/worst_case", "/error_qualification/trials"):
        for key, v in leaf(section).items():
            if isinstance(v, float) and not isinstance(v, bool) and 0.0 < abs(v) < 1e-9:
                assert f"{section}/{key}" in RM_FIELDS, f"{section}/{key} = {v!r} is unmapped"
    # the gates are the dedicated record test's thresholds, unchanged
    src = inspect.getsource(test_the_reference_model_record_is_reproduced_and_within_tolerance)
    assert "< 1e-12" in src and ">= -1e-12" in src
    gates = {p: c for p, (_, c) in RM_FIELDS.items() if c[0] == "gate"}
    assert sum(c[2] == 1e-12 and c[1] == "<" for c in gates.values()) == 10
    assert gates["/worst_case/K_port_minus_qq_min_eig_same_rule_min"] == ("gate", ">=", -1e-12)
    assert gates["/worst_case/epr_phase_invariance"] == ("gate", "<", 1e-9)
    assert sum(c[0] == "diagnostic" for _, c in RM_FIELDS.values()) == 3
