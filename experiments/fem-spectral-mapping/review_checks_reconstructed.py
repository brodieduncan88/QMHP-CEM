#!/usr/bin/env python3
"""Independent reconstruction of the three review checks against 46bf8b5.

The supplied ``QMHP_46bf8b5_review_checks.py`` did not reach this environment
(nothing of that name in the session upload directory), so the three stated
items are reconstructed here from their descriptions and verified from
scratch. They are SYNTHETIC counterexamples and identity checks on small
matrices; no QMHP record is read. If the supplied file differs in
construction, these results stand on their own algebra but the two should
still be reconciled.

Conventions throughout: real symmetric pencil (K, M) with M positive
definite and K = K_curl + K_port positive semidefinite, q = f/sqrt(L),
Q = q q^T, N = q^T K^+ q, and G(z) = sum_m p_m/(z - lambda_m) with
p_m = (q^T E_m)^2 / lambda_m for M-orthonormal eigenvectors E_m.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RNG = np.random.default_rng(20260920)


def spectral_data(K, M, q):
    """(lambda_m, p_m) for the pencil, plus N from the weights and from K^+."""
    Minv_half = np.linalg.inv(np.linalg.cholesky(M))
    A = Minv_half @ K @ Minv_half.T
    lam, U = np.linalg.eigh(A)
    E = Minv_half.T @ U                      # columns M-orthonormal
    w = (q @ E) ** 2
    keep = lam > lam.max() * 1e-12           # drop the null space; q annihilates it
    p = np.zeros_like(lam)
    p[keep] = w[keep] / lam[keep]
    return lam[keep], p[keep], float(p.sum()), float(q @ np.linalg.pinv(K) @ q)


def G(z, lam, p):
    return float(np.sum(p / (z - lam)))


def check_1_rank_two_port_with_N_equal_one():
    """rank(K_port) = 2 and N = 1 simultaneously: the rank implication is false.

    Construction from the equality condition derived below: with u := K^+ q,
    N = u^T K u = u^T K_curl u + u^T K_port u >= u^T Q u = (q^T u)^2 = N^2,
    so N <= 1, and N = 1 exactly when u^T K_curl u = 0 and u^T (K_port - Q) u = 0.
    Any K_port whose extra directions are orthogonal to that static solution
    therefore leaves N = 1 at any rank.
    """
    out = []
    # (a) the minimal case
    q = np.array([1.0, 0.0, 0.0])
    K_port = np.diag([1.0, 1.0, 0.0])        # rank 2, and K_port >= q q^T
    K_curl = np.diag([0.0, 0.0, 1.0])
    K = K_curl + K_port
    M = np.eye(3)
    lam, p, sum_p, N = spectral_data(K, M, q)
    out.append({"case": "minimal: K_port = diag(1,1,0), K_curl = diag(0,0,1), q = e1",
                "rank_K_port": int(np.linalg.matrix_rank(K_port)),
                "K_port_minus_Q_is_PSD": bool(np.linalg.eigvalsh(K_port - np.outer(q, q)).min() >= -1e-12),
                "N_from_pseudoinverse": N, "N_from_weights": sum_p,
                "N_equals_one": abs(N - 1.0) < 1e-12})
    # (b) a non-degenerate case with a general M and a rank-3 port term
    P = np.array([[1.0, 0.3, 0.0], [0.3, 2.0, 0.4], [0.0, 0.4, 1.5]])
    M = P @ P.T + 0.5 * np.eye(3)
    q = np.array([1.0, 0.0, 0.0])
    u = np.array([1.0, 0.0, 0.0])            # want K u = q, i.e. N = q.u = 1
    extra = np.diag([0.0, 2.0, 3.0])         # annihilates u, so N is untouched
    K_port = np.outer(q, q) + extra          # rank 3, K_port - Q = extra >= 0
    K_curl = np.diag([0.0, 0.7, 0.9])        # also annihilates u
    K = K_curl + K_port
    lam, p, sum_p, N = spectral_data(K, M, q)
    out.append({"case": "rank-3 port term, general M, extra directions orthogonal to u",
                "rank_K_port": int(np.linalg.matrix_rank(K_port)),
                "K_port_minus_Q_is_PSD": bool(np.linalg.eigvalsh(K_port - np.outer(q, q)).min() >= -1e-12),
                "N_from_pseudoinverse": N, "N_from_weights": sum_p,
                "N_equals_one": abs(N - 1.0) < 1e-12})
    # (c) the equality condition, tested on random draws
    viol = 0.0
    rows = []
    for _ in range(200):
        n = 4
        B = RNG.normal(size=(n, n))
        M = B @ B.T + n * np.eye(n)
        q = RNG.normal(size=n)
        C = RNG.normal(size=(n, n))
        K_curl = C @ C.T * RNG.random()
        D = RNG.normal(size=(n, n))
        K_port = np.outer(q, q) / (q @ q) * 0 + D @ D.T + np.outer(q, q)  # >= Q by construction
        K = K_curl + K_port
        u = np.linalg.pinv(K) @ q
        N = float(q @ u)
        residual = float(u @ K_curl @ u + u @ (K_port - np.outer(q, q)) @ u)
        rows.append({"N": N, "u_K_curl_u_plus_u_dK_u": residual, "N_minus_N2": N - N * N})
        viol = max(viol, abs((N - N * N) - residual))
    out.append({"case": "equality condition on 200 random draws",
                "identity_checked": "N - N^2 = u^T K_curl u + u^T (K_port - Q) u,  u = K^+ q",
                "max_abs_violation": viol,
                "all_N_le_one": bool(all(r["N"] <= 1.0 + 1e-10 for r in rows)),
                "min_N": min(r["N"] for r in rows), "max_N": max(r["N"] for r in rows)})
    return out


def check_2_diagonal_participation_is_not_a_shift_bound():
    """A tiny diagonal participation with a finite eigenvalue shift after removal.

    The first-order term is the diagonal E^T dK E / E^T K E. The finite shift
    also carries the second-order term sum_n |E_m^T dK E_n|^2/(lambda_m -
    lambda_n), which the diagonal does not control: dK >= 0 only forces
    |dK_mn|^2 <= dK_mm dK_nn, so a small dK_mm still permits an off-diagonal
    as large as sqrt(dK_mm dK_nn) against a small denominator.
    """
    rows = []
    for gap, a, c in ((1.0e-3, 1.0e-8, 1.0), (1.0e-2, 1.0e-8, 1.0), (1.0e-1, 1.0e-6, 1.0)):
        lam1, lam2 = 1.0, 1.0 + gap
        b = math.sqrt(a * c)                  # extremal PSD off-diagonal
        dK = np.array([[a, b], [b, c]])
        K = np.diag([lam1, lam2 + c])         # so that K - dK keeps lambda_2 near lam2
        M = np.eye(2)
        before = np.linalg.eigvalsh(K)
        after = np.linalg.eigvalsh(K - dK)
        E1 = np.array([1.0, 0.0])
        diagonal_fraction = float(E1 @ dK @ E1) / float(E1 @ K @ E1)
        # track the eigenvalue that starts nearest lam1
        i = int(np.argmin(abs(before - lam1)))
        j = int(np.argmin(abs(after - before[i])))
        actual = abs(after[j] - before[i]) / before[i]
        rows.append({"gap": gap, "dK_11": a, "dK_22": c, "dK_12": b,
                     "diagonal_participation_fraction": diagonal_fraction,
                     "actual_relative_shift": actual,
                     "ratio_actual_over_diagonal": actual / diagonal_fraction,
                     "K_minus_dK_is_PSD": bool(np.linalg.eigvalsh(K - dK).min() >= -1e-12)})
    return {"claim_tested": "relative eigenvalue shift after removing dK >= 0 is bounded by "
                            "the mode's diagonal participation in dK",
            "verdict": "FALSE", "rows": rows,
            "what_a_valid_bound_needs": "the off-diagonal couplings ||(I - P_m) dK E_m|| and the "
                                        "spectral gaps to the states dK connects to; the diagonal alone "
                                        "is only the first-order term"}


def check_3_determinant_identity():
    """det(zM - K + Q)/det(zM - K) = z G(z) + 1 - N, and the Q/N consequence."""
    rows = []
    for trial in range(50):
        n = 5
        B = RNG.normal(size=(n, n))
        M = B @ B.T + n * np.eye(n)
        C = RNG.normal(size=(n, n))
        K = C @ C.T + 0.1 * np.eye(n)
        q = RNG.normal(size=n)
        Q = np.outer(q, q)
        lam, p, sum_p, N = spectral_data(K, M, q)
        z = float(lam.max() * (1.7 + 0.9 * RNG.random()))
        lhs = np.linalg.det(z * M - K + Q) / np.linalg.det(z * M - K)
        rhs = z * G(z, lam, p) + 1.0 - N
        # zeros of G are the nonzero eigenvalues of (K - Q/N, M); roots of
        # z G(z) = N - 1 are those of (K - Q, M)
        ev_QoverN = np.linalg.eigvalsh(np.linalg.inv(np.linalg.cholesky(M)) @ (K - Q / N)
                                       @ np.linalg.inv(np.linalg.cholesky(M)).T)
        poly_G = np.zeros(n)
        for i in range(n):
            poly_G = poly_G + p[i] * np.poly([lam[j] for j in range(n) if j != i])
        zeros_G = np.sort(np.roots(poly_G).real)
        matched = [float(np.min(np.abs(ev_QoverN - zz)) / max(abs(zz), 1e-30)) for zz in zeros_G]
        rows.append({"trial": trial, "N": N, "sum_p_equals_N": abs(sum_p - N) < 1e-10,
                     "identity_rel_error": abs(lhs - rhs) / max(abs(lhs), 1e-30),
                     "max_rel_distance_zeros_G_to_eig_K_minus_Q_over_N": max(matched)})
    return {"identity": "det(zM - K + Q)/det(zM - K) = z G(z) + 1 - N",
            "derivation": "matrix determinant lemma gives 1 + q^T (zM-K)^-1 q; the spectral sum "
                          "q^T (zM-K)^-1 q = sum_m lambda_m p_m/(z - lambda_m) = z G(z) - N",
            "max_identity_rel_error": max(r["identity_rel_error"] for r in rows),
            "max_rel_distance_zeros_to_K_minus_Q_over_N": max(
                r["max_rel_distance_zeros_G_to_eig_K_minus_Q_over_N"] for r in rows),
            "consequence": "the zeros of G are the nonzero eigenvalues of (K - Q/N, M): the NORMALISED "
                           "rank-one removal. The eigenvalues of (K - Q, M), the declared rank-one "
                           "inductor removed, are instead the roots of z G(z) + 1 - N = 0, which "
                           "coincide with the zeros of G only when N = 1.",
            "rows": rows[:5]}


def main():
    out = {
        "label": "SYNTHETIC counterexamples and identity checks; no QMHP record is read",
        "supplied_file_status": "QMHP_46bf8b5_review_checks.py did NOT reach this environment; the "
                                "three items are reconstructed from their descriptions and verified "
                                "independently. Reconciliation with the supplied file is outstanding.",
        "check_1_normalisation_rank_implication": check_1_rank_two_port_with_N_equal_one(),
        "check_2_finite_operator_removal": check_2_diagonal_participation_is_not_a_shift_bound(),
        "check_3_exact_removal_identity": check_3_determinant_identity(),
    }
    _finite(out)
    (HERE / "review_checks_reconstructed.json").write_text(json.dumps(out, indent=1) + "\n")
    print(out["supplied_file_status"], "\n")
    print("=== 1. rank(K_port) != 1 does NOT imply N < 1 ===")
    for c in out["check_1_normalisation_rank_implication"]:
        if "rank_K_port" in c:
            print(f"  {c['case']}\n     rank(K_port) = {c['rank_K_port']}, K_port - Q PSD = "
                  f"{c['K_port_minus_Q_is_PSD']}, N = {c['N_from_pseudoinverse']:.15f} "
                  f"(weights {c['N_from_weights']:.15f}) -> N == 1: {c['N_equals_one']}")
        else:
            print(f"  {c['case']}: {c['identity_checked']}\n     max violation "
                  f"{c['max_abs_violation']:.3e}; all N <= 1: {c['all_N_le_one']}; "
                  f"N in [{c['min_N']:.6f}, {c['max_N']:.6f}]")
    print("\n=== 2. the diagonal participation is not a bound on the finite shift ===")
    for r in out["check_2_finite_operator_removal"]["rows"]:
        print(f"  gap {r['gap']:.0e}: diagonal fraction {r['diagonal_participation_fraction']:.3e}, "
              f"actual shift {r['actual_relative_shift']:.3e}, ratio {r['ratio_actual_over_diagonal']:.4g}")
    print("\n=== 3. determinant identity ===")
    c3 = out["check_3_exact_removal_identity"]
    print(f"  {c3['identity']}")
    print(f"  max relative error over 50 random pencils: {c3['max_identity_rel_error']:.3e}")
    print(f"  zeros of G vs eigenvalues of (K - Q/N, M): max relative distance "
          f"{c3['max_rel_distance_zeros_to_K_minus_Q_over_N']:.3e}")


def _finite(o, path="out"):
    if isinstance(o, dict):
        for k, v in o.items():
            _finite(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _finite(v, f"{path}[{i}]")
    elif isinstance(o, float) and not math.isfinite(o):
        raise RuntimeError(f"non-finite at {path}")


if __name__ == "__main__":
    main()
