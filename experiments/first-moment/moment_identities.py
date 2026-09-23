#!/usr/bin/env python3
"""The two spectral moments of the F-site functional, derived and tested synthetically.

SETUP. A constrained finite-dimensional pencil ``K E_m = lambda_m M E_m`` with
``K`` symmetric positive SEMI-definite (singular, as the assembled curl-curl plus
port stiffness is) and ``M`` symmetric positive definite (the eps-weighted mass
matrix). Eigenvectors are normalised to unit electric energy, ``E_m^H M E_m = 1``,
which makes them M-orthonormal and gives the completeness relation
``sum_m E_m E_m^H = M^-1``.

THE PORT FUNCTIONAL. ``V = f^H E`` is the width-averaged line voltage. With
``q = f / sqrt(L)``:

    p_m = (f^H E_m)^2 / (lambda_m L) = (q^H E_m)^2 / lambda_m      (lambda_m > 0)

THE TWO MOMENTS.

    N = sum_m p_m            = q^H K^+ q          (zeroth moment)
    A = sum_m lambda_m p_m   = q^H M^-1 q         (first moment)

A is the striking one: ``sum_m lambda_m p_m = sum_m (q^H E_m)^2`` is a PARSEVAL
sum, so the first moment needs only ``M``, never ``K`` and never a pseudoinverse.

THE ONE EXTRA CONDITION, for BOTH. ``q^H E_0 = 0`` for every zero mode, i.e.
``q`` is orthogonal to ``ker(K)``. It is needed twice over:

  * without it ``p_0 = (q^H E_0)^2 / 0`` diverges and neither sum exists;
  * with it, ``q`` lies in ``range(K)``, so ``q^H K^+ q`` takes the same value
    for the Moore-Penrose pseudoinverse and for every other generalised
    inverse - any two solutions of ``K x = q`` differ by a ``ker(K)`` vector,
    which ``q`` annihilates. That is what makes ``K^+`` unambiguous in the N
    identity, and it is an ASSUMPTION about this model, not a theorem about it.

This script derives nothing from QMHP data. It tests the identities, and the
three ways they fail, on random synthetic pencils.

Offline. No network, no Palace, no FEM assembly.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

#: Trials and size. Small and many, so the null-space cases are exercised often.
TRIALS = 200
DIM = 40
NULLITY = 6
RNG_SEED = 20260920


def _pencil(rng: np.random.Generator, n: int, nullity: int):
    """A symmetric PSD K with a known nullity, and an SPD M. Not commuting."""
    B = rng.normal(size=(n, n))
    M = B @ B.T + n * np.eye(n)                      # SPD, well conditioned
    C = rng.normal(size=(n, n - nullity))
    K = C @ C.T                                      # PSD, rank n - nullity
    return K, M


def _eig(K, M):
    """All eigenpairs, M-orthonormalised: E^H M E = I."""
    Minv_half = np.linalg.inv(np.linalg.cholesky(M))          # L^-1 with M = L L^H
    S = Minv_half @ K @ Minv_half.T
    S = 0.5 * (S + S.T)
    lam, U = np.linalg.eigh(S)
    E = Minv_half.T @ U
    return lam, E


def _moments(lam, E, q, tol):
    """p_m over the POSITIVE eigenvalues, and the two sums."""
    pos = lam > tol
    proj = E.T @ q
    p = np.zeros_like(lam)
    p[pos] = proj[pos] ** 2 / lam[pos]
    return p, p[pos].sum(), (lam[pos] * p[pos]).sum(), pos


def main() -> None:
    rng = np.random.default_rng(RNG_SEED)
    worst = {"N": 0.0, "A": 0.0, "leak": 0.0}
    failures = {"filtered_subset_N": [], "filtered_subset_A": [],
                "q_not_orthogonal_to_kernel_N": [], "q_not_orthogonal_to_kernel_A": [],
                "wrong_normalisation_N": []}

    for _ in range(TRIALS):
        K, M = _pencil(rng, DIM, NULLITY)
        lam, E = _eig(K, M)
        tol = max(1e-9, 1e-9 * lam.max())
        null = lam <= tol

        # q MUST be orthogonal to ker(K): build it that way, by projecting a
        # random vector off the zero modes in the M-geometry.
        raw = rng.normal(size=DIM)
        q = raw - (M @ E[:, null]) @ (E[:, null].T @ raw)
        assert abs(E[:, null].T @ q).max() < 1e-9

        p, N_sum, A_sum, pos = _moments(lam, E, q, tol)

        N_form = q @ np.linalg.pinv(K) @ q
        A_form = q @ np.linalg.solve(M, q)
        worst["N"] = max(worst["N"], abs(N_sum - N_form) / abs(N_form))
        worst["A"] = max(worst["A"], abs(A_sum - A_form) / abs(A_form))

        # FAILURE 1 - a filtered subset is not a complete basis.
        keep = np.argsort(p)[::-1][: max(1, int(pos.sum() // 3))]
        failures["filtered_subset_N"].append(p[keep].sum() / N_form)
        failures["filtered_subset_A"].append((lam[keep] * p[keep]).sum() / A_form)

        # FAILURE 2 - q with a kernel component: p_0 diverges, both sums void.
        qbad = q + (M @ E[:, null]) @ rng.normal(size=int(null.sum()))
        projbad = E.T @ qbad
        leak = (projbad[null] ** 2).sum() / (projbad**2).sum()
        worst["leak"] = max(worst["leak"], leak)
        pbad, Nbad, Abad, _ = _moments(lam, E, qbad, tol)
        failures["q_not_orthogonal_to_kernel_N"].append(
            Nbad / (qbad @ np.linalg.pinv(K) @ qbad))
        failures["q_not_orthogonal_to_kernel_A"].append(
            Abad / (qbad @ np.linalg.solve(M, qbad)))

        # FAILURE 3 - eigenvectors not normalised to unit electric energy.
        s = rng.uniform(0.5, 2.0, size=DIM)
        Es = E * s
        lams = lam
        _, Ns, _, _ = _moments(lams, Es, q, tol)
        failures["wrong_normalisation_N"].append(Ns / N_form)

    def stat(key):
        v = np.array(failures[key])
        return {"min": float(v.min()), "max": float(v.max()), "median": float(np.median(v))}

    result = {
        "label": "MOMENT IDENTITIES - DERIVED AND VERIFIED ON SYNTHETIC PENCILS ONLY",
        "supplied_package_status": (
            "the small review package named in the task did NOT reach this environment; the "
            "uploads directory holds only the three earlier archives. Nothing here is a "
            "cross-check against it, and it is not treated as authority or as reproduced."
        ),
        "trials": TRIALS, "dimension": DIM, "nullity": NULLITY, "seed": RNG_SEED,
        "identities": {
            "zeroth_moment": "N = sum_m p_m = q^H K^+ q",
            "first_moment": "A = sum_m lambda_m p_m = q^H M^-1 q",
            "max_relative_error_N": float(worst["N"]),
            "max_relative_error_A": float(worst["A"]),
            "both_verified": bool(worst["N"] < 1e-8 and worst["A"] < 1e-8),
            "why_A_is_the_easy_one": (
                "sum_m lambda_m p_m = sum_m (q^H E_m)^2 is a Parseval sum over the M-orthonormal "
                "basis, so the first moment needs only M - no K, no pseudoinverse, no null-space "
                "handling beyond the condition below. The zeroth moment needs K^+."
            ),
        },
        "assumptions": {
            "completeness": (
                "the sums run over ALL eigenpairs of the constrained pencil, not a filtered "
                "subset. sum_m E_m E_m^H = M^-1 holds only for the complete set."
            ),
            "null_space": (
                "q^H E_0 = 0 for every zero mode. Without it p_0 diverges and neither sum exists; "
                "with it q lies in range(K), which is what makes q^H K^+ q independent of which "
                "generalised inverse is used. This is an ASSUMPTION about the QMHP model, not "
                "something these synthetic trials establish for it."
            ),
            "normalisation": (
                "E_m^H M E_m = 1, unit electric energy. Any other scaling rescales p_m and both "
                "moments; Palace's reported p already carries its own normalisation, which must "
                "be reconciled rather than assumed to match."
            ),
            "projection": (
                "the divergence-free projector changes the space the returned eigenvectors span. "
                "If it removes a direction q has a component along, the returned set is not "
                "complete FOR q and both sums fall short by that component - silently."
            ),
            "units": (
                "lambda_m = omega_m^2. A therefore carries the units of lambda; the GHz^2 moment "
                "the existing analysis uses is A / (2*pi*1e9)^2, which is sum_m p_m f_m^2 with "
                "f_m in GHz. N is dimensionless."
            ),
        },
        "how_the_identities_fail": {
            "filtered_subset_keeps_a_third_of_the_modes": {
                "fraction_of_N_recovered": stat("filtered_subset_N"),
                "fraction_of_A_recovered": stat("filtered_subset_A"),
                "reading": (
                    "a filtered subset is not a basis. Note the two fractions differ: filtering "
                    "by weight preserves N far better than A, because A is weighted by lambda "
                    "and the discarded high-lambda modes carry little weight but much moment."
                ),
            },
            "q_with_a_kernel_component": {
                "max_fraction_of_q_in_the_kernel": float(worst["leak"]),
                "ratio_of_the_sum_to_the_quadratic_form_N": stat("q_not_orthogonal_to_kernel_N"),
                "ratio_of_the_sum_to_the_quadratic_form_A": stat("q_not_orthogonal_to_kernel_A"),
                "reading": (
                    "both identities break. The sums omit the kernel component entirely while "
                    "the quadratic forms do not, so they disagree by exactly that component - "
                    "and p_0 itself is infinite, so the 'sum' is only defined by dropping it."
                ),
            },
            "eigenvectors_not_M_normalised": {
                "ratio_of_the_sum_to_the_quadratic_form_N": stat("wrong_normalisation_N"),
                "reading": "an arbitrary per-mode rescaling breaks N by an arbitrary factor.",
            },
        },
    }
    (HERE / "moment_identities.json").write_text(json.dumps(result, indent=1) + "\n")
    print(result["label"])
    print(f"  N = q^H K^+ q   max relative error over {TRIALS} pencils: {worst['N']:.3e}")
    print(f"  A = q^H M^-1 q  max relative error over {TRIALS} pencils: {worst['A']:.3e}")
    print(f"  both verified: {result['identities']['both_verified']}")
    f = result["how_the_identities_fail"]["filtered_subset_keeps_a_third_of_the_modes"]
    print(f"  filtered subset recovers N to {f['fraction_of_N_recovered']['median']:.4f} "
          f"but A to only {f['fraction_of_A_recovered']['median']:.4f} (median)")


if __name__ == "__main__":
    main()
