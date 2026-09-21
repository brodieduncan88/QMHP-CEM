#!/usr/bin/env python3
"""Reference model of the direct first-moment diagnostic, verified on synthetic fixtures.

The diagnostic evaluates, on the PEC-constrained (free) true dofs of N2R's
Nedelec space,

    A = Re(f_free^H M_free^-1 f_free) / L          (nondimensional, Palace units)
    A_GHz2 = A_nd / (2 pi t_c)^2                     (t_c in ns)

with ``f = P^T v`` the exact ``LumpedPortData::GetVoltage`` linear form assembled
to true dofs, ``M`` the eigenmode driver's mass matrix, and ``L`` the port
inductance in Palace's nondimensional units. This module is the algebra of that
computation, written against the pinned source (Palace v0.13.0, a61c8cbe),
together with the synthetic fixture the tests exercise it on:

  * dual assembly ``P^T v`` versus the local dot product ``GetVoltage`` uses,
    with shared (duplicated) local dofs so that the two differ unless the
    transpose is taken (``plinearform.cpp:95-99``, ``lumpedportoperator.cpp:297-308``);
  * the DIAG_ONE / DIAG_ZERO padded operators exactly as ``ParOperator::Mult``
    applies them (``rap.cpp:198-227``): DIAG_ONE is ``[[M_free, 0], [0, I]]``,
    DIAG_ZERO is ``[[M_free, 0], [0, 0]]`` and singular;
  * the free-dof form, the padded DIAG_ONE form with the right-hand side
    zeroed on the essential dofs (identical), and the padded form WITHOUT that
    zeroing (adds exactly ``sum_dbc f_dbc^2 / L``, the artificial boundary term);
  * Parseval: ``A = sum_m (q^H E_m)^2`` over the complete M-orthonormal
    constrained eigenbasis, ``q = f / sqrt(L)``;
  * the null-space argument: the port stiffness ``K_port = P^T Q^T diag(a/L_s) Q P``
    and the functional ``f = P^T Q^T (a c)`` are built from the SAME quadrature
    points ``Q`` with positive weights ``a``, so ``f`` lies in ``range(K_port)``
    and annihilates ``ker(K) \\subseteq ker(K_port)``; with the same WEIGHTS the
    quantitative ``K_port >= q q^H`` follows by Cauchy-Schwarz; a mismatched
    rule is the negative control;
  * Palace's reported EPR ``p = 1/2 L |I|^2 / E_m`` with ``I = V / (i omega L)`` and
    ``E_m = E_elec = 1/2 E^H M E`` (``postoperator.cpp:644-660``,
    ``domainpostoperator.cpp:142-154``) reconciled with ``|f^H E|^2 / (L lambda E^H M E)``;
  * IoData's scales (``iodata.cpp:453-465``, ``:512``, ``:562-620``) and the
    phase invariance of every quantity under ``E -> e^{i theta} E``;
  * the output record the patched driver writes, its evaluation against a saved
    partial moment, and the numerical qualification of the difference.

Offline. No network, no Palace, no FEM assembly of the N2R problem, no real-data
A, E_C, N or g.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RNG_SEED = 20260920
TRIALS = 60

# --- Palace's physical constants: palace/utils/constants.hpp:17-38 ---------------
EPSILON0 = 8.8541878176e-12
MU0 = 4.0e-7 * math.pi
C0 = 1.0 / math.sqrt(EPSILON0 * MU0)
Z0 = math.sqrt(MU0 / EPSILON0)


# --- units: IoData::NondimensionalizeInputs and DimensionalizeValue -----------------
def unit_scales(Lc_m: float) -> dict:
    """The scales Palace derives from the characteristic length.

    ``iodata.cpp:453-465``: ``Lc`` is ``Model.Lc * L0`` if given, else the largest
    axis-aligned bounding-box extent of the mesh times ``L0``; ``tc = 1e9 Lc / c0``
    in ns. ``iodata.cpp:562-620``: FREQUENCY scale ``1/(2 pi tc)`` (GHz per
    nondimensional radian frequency), INDUCTANCE scale ``mu0 Lc``, VOLTAGE scale
    ``Hc Z0 Lc``, ENERGY scale ``Hc^2 Z0 Lc^2 tc`` with ``Hc = 1/sqrt(Z0 Lc^2)``.
    """
    tc_ns = 1.0e9 * Lc_m / C0
    Hc = 1.0 / math.sqrt(Z0 * Lc_m * Lc_m)
    freq = 1.0 / (2.0 * math.pi * tc_ns)
    return {
        "Lc_m": Lc_m,
        "tc_ns": tc_ns,
        "FrequencyScale_GHz": freq,
        "InductanceScale_H": MU0 * Lc_m,
        "VoltageScale_V": Hc * Z0 * Lc_m,
        "EnergyScale_J": Hc * Hc * Z0 * Lc_m * Lc_m * tc_ns,
        "A_GHz2_per_nd": freq * freq,
    }


def inductance_nd(L_H: float, Lc_m: float) -> float:
    """``data.L /= mu0 * Lc`` (``iodata.cpp:512``)."""
    return L_H / (MU0 * Lc_m)


def a_ghz2_from_nd(A_nd: float, tc_ns: float) -> float:
    """lambda_nd = omega_nd^2 with f_GHz = omega_nd / (2 pi tc): A_GHz2 = A_nd / (2 pi tc)^2."""
    return A_nd / (2.0 * math.pi * tc_ns) ** 2


def a_nd_from_ghz2(A_GHz2: float, tc_ns: float) -> float:
    return A_GHz2 * (2.0 * math.pi * tc_ns) ** 2


def lambda_nd_from_f_ghz(f_GHz: float, tc_ns: float) -> float:
    return (2.0 * math.pi * f_GHz * tc_ns) ** 2


# --- the synthetic fixture ----------------------------------------------------------
class Fixture:
    """A small model with the structure the diagnostic relies on.

    true dofs (n_true) --P--> local dofs (n_loc) --Q--> port quadrature points (n_q).

    ``P`` is a 0/1 prolongation with ``n_shared`` duplicated local dofs, so the
    local vector is longer than the true vector and ``P^T v`` is a genuine dual
    assembly. ``Q`` evaluates the local basis at the port's quadrature points;
    ``a`` are the positive quadrature weights, ``sum(a) = w * l`` (port area).
    One lumped element (``elems.size() == 1``), width ``w``, length ``l``, so the
    voltage coefficient is ``c = 1/w`` and the surface inductance ``L_s = L w / l``
    (``LumpedPortData::GetToSquare``, ``InitializeLinearForms``,
    ``AddStiffnessBdrCoefficients``).
    """

    def __init__(self, rng: np.random.Generator, n_true: int = 36, n_shared: int = 8,
                 n_port_elems: int = 4, q_per_elem: int = 3, n_dbc: int = 6,
                 kernel_dim: int = 3, L: float = 20.58, w: float = 0.05, l: float = 0.2):
        self.n_true, self.L, self.w, self.l = n_true, L, w, l
        self.n_elems = 1                       # one lumped element
        shared = rng.choice(n_true, size=n_shared, replace=False)
        n_loc = n_true + n_shared
        P = np.zeros((n_loc, n_true))
        P[np.arange(n_true), np.arange(n_true)] = 1.0
        P[n_true + np.arange(n_shared), shared] = 1.0
        self.P, self.n_loc = P, n_loc

        # The port touches a fixed block of local dofs (some of them shared copies).
        port_loc = np.concatenate([np.arange(0, 9), n_true + np.arange(0, 3)])
        n_q = n_port_elems * q_per_elem
        Q = np.zeros((n_q, n_loc))
        for e in range(n_port_elems):
            dofs = rng.choice(port_loc, size=3, replace=False)
            for q in range(q_per_elem):
                Q[e * q_per_elem + q, dofs] = rng.uniform(0.2, 1.0, size=3)
        self.Q = Q
        area_e = w * l / n_port_elems
        ref_w = np.full(q_per_elem, 1.0 / q_per_elem)
        self.a = np.concatenate([area_e * ref_w for _ in range(n_port_elems)])
        assert abs(self.a.sum() - w * l) < 1e-14

        self.c = 1.0 / (w * self.n_elems)      # GetModeCoefficient(1/(w * elems.size()))
        self.Ls = L * w / l * self.n_elems     # L * GetToSquare(elem)
        self.v_loc = Q.T @ (self.a * self.c)   # VectorFEBoundaryLFIntegrator, same rule
        self.K_port = P.T @ Q.T @ np.diag(self.a / self.Ls) @ Q @ P
        # The true dofs the functional actually touches (the port's support).
        self.port_true = np.nonzero(np.abs(P.T @ self.v_loc) > 0.0)[0]

        # SPD local mass, assembled to true dofs.
        B = rng.normal(size=(n_loc, n_loc))
        self.M_loc = B @ B.T + n_loc * np.eye(n_loc)
        self.M = P.T @ self.M_loc @ P

        # A PSD 'curl-curl' term whose kernel is supported away from the port, so K
        # has a nontrivial kernel: ker(K) = span(Z), K_port Z = 0 because Z vanishes at
        # every port dof.
        off_port = np.setdiff1d(np.arange(n_true), self.port_true)
        Z = np.zeros((n_true, kernel_dim))
        pick = rng.choice(off_port, size=kernel_dim * 3, replace=False).reshape(kernel_dim, 3)
        for k in range(kernel_dim):
            Z[pick[k], k] = rng.normal(size=3)
        Zq, _ = np.linalg.qr(Z)
        G = rng.normal(size=(n_true - kernel_dim, n_true))
        G = G - (G @ Zq) @ Zq.T                # rows orthogonal to span(Z)
        self.K_curl = G.T @ G
        self.K = self.K_curl + self.K_port
        self.kernel = Zq

        # Essential (PEC) dofs: some on the port (so f_dbc != 0), none in supp(Z).
        cand = np.setdiff1d(np.arange(n_true), pick.ravel())
        on_port = rng.choice(np.intersect1d(cand, self.port_true), size=2, replace=False)
        rest = rng.choice(np.setdiff1d(cand, self.port_true), size=n_dbc - 2, replace=False)
        self.dbc = np.sort(np.concatenate([on_port, rest]))
        self.free = np.setdiff1d(np.arange(n_true), self.dbc)

    # -- the objects the diagnostic uses --
    @property
    def f_true(self) -> np.ndarray:
        return dual_assemble(self.P, self.v_loc)


def dual_assemble(P: np.ndarray, v_loc: np.ndarray) -> np.ndarray:
    """``ParLinearForm::ParallelAssemble``: ``prolong->MultTranspose(v, tv)`` (plinearform.cpp:95-99)."""
    return P.T @ v_loc


def voltage_palace(v_loc: np.ndarray, P: np.ndarray, E_true: np.ndarray) -> complex:
    """``GetVoltage``: ``(*v) * E.Real()`` + i ``(*v) * E.Imag()`` on the LOCAL vectors,
    summed over ranks (lumpedportoperator.cpp:297-308). The local field is ``P E_true``."""
    El = P @ E_true
    return complex(v_loc @ El.real, v_loc @ El.imag)


def voltage_from_functional(f_true: np.ndarray, E_true: np.ndarray) -> complex:
    """What the driver computes: ``f . Re(E_true) + i f . Im(E_true)``."""
    return complex(f_true @ E_true.real, f_true @ E_true.imag)


def restrict_to_free(x: np.ndarray, dbc: np.ndarray) -> np.ndarray:
    y = x.copy()
    y[dbc] = 0.0
    return y


def padded_mass(M: np.ndarray, dbc: np.ndarray, policy: str) -> np.ndarray:
    """``ParOperator::Mult`` with essential dofs (rap.cpp:198-227): the input is zeroed on
    ``dbc`` before prolongation; the output is set to ``x`` (DIAG_ONE) or ``0``
    (DIAG_ZERO) on ``dbc`` afterwards."""
    n = M.shape[0]
    zf = np.ones(n)
    zf[dbc] = 0.0
    Z = np.diag(zf)
    Mp = Z @ M @ Z
    if policy == "DIAG_ONE":
        Mp = Mp + np.diag(1.0 - zf)
    elif policy != "DIAG_ZERO":
        raise ValueError(policy)
    return Mp


def first_moment_free(M: np.ndarray, f: np.ndarray, dbc: np.ndarray, L: float) -> float:
    """``A = f_free^T M_free^-1 f_free / L`` on the free dofs only."""
    free = np.setdiff1d(np.arange(M.shape[0]), dbc)
    x = np.linalg.solve(M[np.ix_(free, free)], f[free])
    return float(f[free] @ x / L)


def first_moment_padded(M: np.ndarray, f: np.ndarray, dbc: np.ndarray, L: float,
                        policy: str, zero_rhs_on_dbc: bool) -> float | None:
    """The padded solve as the driver performs it. Returns None when the padded operator
    is singular (DIAG_ZERO)."""
    Mp = padded_mass(M, dbc, policy)
    if np.linalg.matrix_rank(Mp) < Mp.shape[0]:
        return None
    b = restrict_to_free(f, dbc) if zero_rhs_on_dbc else f
    x = np.linalg.solve(Mp, b)
    return float(b @ x / L)


def constrained_eigenbasis(K: np.ndarray, M: np.ndarray, dbc: np.ndarray):
    """All eigenpairs of the constrained pencil (K_free, M_free), M_free-orthonormal,
    embedded in the full true-dof length with zeros on ``dbc``."""
    n = K.shape[0]
    free = np.setdiff1d(np.arange(n), dbc)
    Kf, Mf = K[np.ix_(free, free)], M[np.ix_(free, free)]
    Linv = np.linalg.inv(np.linalg.cholesky(Mf))
    S = Linv @ Kf @ Linv.T
    S = 0.5 * (S + S.T)
    lam, U = np.linalg.eigh(S)
    Ef = Linv.T @ U
    E = np.zeros((n, len(free)))
    E[free] = Ef
    return lam, E


def parseval_first_moment(f: np.ndarray, L: float, lam: np.ndarray, E: np.ndarray,
                          zero_tol: float = 1e-9) -> tuple[float, float]:
    """``sum_m (q^H E_m)^2`` over all modes and over the nonzero modes only."""
    q = f / math.sqrt(L)
    w = (q @ E) ** 2
    return float(w.sum()), float(w[lam > zero_tol * lam.max()].sum())


def zeroth_moment(f: np.ndarray, L: float, lam: np.ndarray, E: np.ndarray,
                  zero_tol: float = 1e-9) -> float:
    q = f / math.sqrt(L)
    keep = lam > zero_tol * lam.max()
    return float(((q @ E[:, keep]) ** 2 / lam[keep]).sum())


def electric_energy_palace(M: np.ndarray, E: np.ndarray) -> float:
    """``GetElectricFieldEnergy``: ``0.5 (E_r^T M E_r + E_i^T M E_i)`` (domainpostoperator.cpp:142-154)."""
    return 0.5 * float(E.real @ M @ E.real + E.imag @ M @ E.imag)


def epr_palace(V: complex, L: float, omega: float, E_m: float) -> float:
    """``GetInductorParticipation`` (postoperator.cpp:644-660): ``I = V / Z_L`` with
    ``Z_L = i omega L`` (``GetCharacteristicImpedance``, Branch::L), ``p = copysign(0.5 |L|
    |I|^2 / E_m, Re I)``."""
    I = V / (1j * omega * L)
    return math.copysign(0.5 * abs(L) * abs(I) ** 2 / E_m, I.real)


def epr_from_functional(f: np.ndarray, L: float, lam: float, M: np.ndarray,
                        E: np.ndarray) -> float:
    """``|f^H E|^2 / (L lambda E^H M E)``, the absolute square form."""
    V = np.vdot(f, E)
    return float(abs(V) ** 2 / (L * lam * np.real(np.vdot(E, M @ E))))


def port_inequality_min_eig(K_port: np.ndarray, f: np.ndarray, L: float) -> float:
    """Smallest eigenvalue of ``K_port - q q^T``; ``>= 0`` is ``K_port >= q q^T``."""
    q = f / math.sqrt(L)
    return float(np.linalg.eigvalsh(K_port - np.outer(q, q)).min())


def kernel_annihilation(K: np.ndarray, f: np.ndarray) -> float:
    """``max_z |f . z| / (|f| |z|)`` over an orthonormal basis of ``ker(K)``."""
    w, V = np.linalg.eigh(K)
    Z = V[:, w < 1e-10 * w.max()]
    if Z.shape[1] == 0:
        return 0.0
    return float(np.abs(Z.T @ f).max() / np.linalg.norm(f))


def null_space_gap(K: np.ndarray, f: np.ndarray, L: float, u: np.ndarray) -> float:
    """The driver's check: ``(u^T K u - (f.u)^2 / L) / u^T K u``."""
    uKu = float(u @ K @ u)
    return (uKu - float(f @ u) ** 2 / L) / uKu


# --- the residual error qualification -----------------------------------------------
#
# With x* = M^-1 f exact, x the computed solution and r = M x - f, substituting f = M x - r
# into both quadratic forms gives, for SPD M,
#
#     f^H x         = x^H M x - r^H x
#     f^H M^-1 f    = x^H M x - 2 Re(x^H r) + r^H M^-1 r
#     ==> A_computed - A_exact = [Re(x^H r) - r^H M^-1 r] / L        (EXACT identity)
#
# r^H M^-1 r >= 0, so Re(x^H r)/L is a CERTIFIED upper bound on the error and
# A_computed - Re(x^H r)/L is a CERTIFIED lower bound on A_exact, with no conditioning
# information. The same number is the variational lower bound (2 f^T x - x^T M x)/L.
# A certified UPPER bound on A_exact needs r^H M^-1 r, hence a lower bound on
# lambda_min(M_free) or a second solve. ||x|| ||r|| / L is an ESTIMATE, not a bound.


def residual_error_identity(M: np.ndarray, f: np.ndarray, x: np.ndarray, L: float) -> dict:
    """Every term of the identity, evaluated exactly for a small dense fixture."""
    r = M @ x - f
    A_hat = float(np.real(np.vdot(f, x))) / L
    A_exact = float(np.real(np.vdot(f, np.linalg.solve(M, f)))) / L
    xr = float(np.real(np.vdot(x, r)))
    rMinvr = float(np.real(np.vdot(r, np.linalg.solve(M, r))))
    return {
        "A_hat": A_hat,
        "A_exact": A_exact,
        "lhs": A_hat - A_exact,
        "rhs": (xr - rMinvr) / L,
        "x_dot_r": xr,
        "r_Minv_r": rMinvr,
        "certified_error_upper_bound": xr / L,
        "certified_lower_bound_A": A_hat - xr / L,
        "variational_lower_bound_A": (2.0 * float(np.real(np.vdot(f, x)))
                                      - float(np.real(np.vdot(x, M @ x)))) / L,
        "uncertified_estimate": float(np.linalg.norm(x) * np.linalg.norm(r)) / L,
        "lambda_min_M": float(np.linalg.eigvalsh(M).min()),
        "sufficient_lambda_min_for_estimate_to_bound": float(
            np.linalg.norm(r) / max(np.linalg.norm(x), np.finfo(float).tiny)),
    }


def bound_counterexample(eps: float, delta: float) -> dict:
    """A 2x2 SPD system where ||x|| ||r|| / L is NOT a bound on the error.

    M = diag(1, eps), x = (1, 0), r = (0, delta), f = M x - r = (1, -delta). Then
    A_hat = 1, A_exact = 1 + delta^2/eps, so the error is -delta^2/eps while the claimed
    bound is ||x|| ||r|| = delta. It is violated whenever delta > eps, i.e. whenever the
    mass matrix is more ill conditioned than the residual is small.
    """
    M = np.diag([1.0, eps])
    x = np.array([1.0, 0.0])
    f = M @ x - np.array([0.0, delta])
    out = residual_error_identity(M, f, x, 1.0)
    out.update({
        "eps": eps,
        "delta": delta,
        "relative_residual": float(delta / np.linalg.norm(f)),
        "estimate_is_a_bound": abs(out["lhs"]) <= out["uncertified_estimate"],
        "certified_bound_holds": out["lhs"] <= out["certified_error_upper_bound"] + 1e-30,
        "violation_factor": abs(out["lhs"]) / out["uncertified_estimate"],
    })
    return out


# --- the uncertainty of the SAVED moment, kept separate from the mass solve ------------
#
# Palace prints every postprocessing column with "%+.9e" (BaseSolver::Table(8, 9, 9)), so a
# printed value v carries |v_true - v| <= 0.5 * 10^(exponent - 9). A_saved = sum |p_m| f_m^2
# is increasing in each |p_m| and each f_m, so the printed-precision interval is exact at
# the corners. The eigensolver's own convergence error is a SECOND, separate contribution
# that the printed record does not quantify: eig.csv reports a backward and an absolute
# error per mode, but converting either into an error on p_m needs a spectral gap that is
# not measured here.

PRINTED_DIGITS = 9  # "%+.9e": 10 significant digits


def printed_halfwidth(v: float, digits: int = PRINTED_DIGITS) -> float:
    """Half of the last printed decimal place of v."""
    if v == 0.0:
        return 0.0
    return 0.5 * 10.0 ** (math.floor(math.log10(abs(v))) - digits)


def saved_moment_interval(per_mode: list[dict]) -> dict:
    """[lo, hi] for A_saved = sum |p| f^2 from the printed precision of p and f alone."""
    lo = hi = central = 0.0
    for m in per_mode:
        p, f = abs(m["abs_p"]), m["f_GHz"]
        dp, df = printed_halfwidth(p), printed_halfwidth(f)
        central += p * f * f
        lo += max(p - dp, 0.0) * (f - df) ** 2
        hi += (p + dp) * (f + df) ** 2
    return {"central_GHz2": central, "lo_GHz2": lo, "hi_GHz2": hi,
            "halfwidth_GHz2": 0.5 * (hi - lo),
            "source": "printed precision of the committed columns only"}


# --- the record the patched driver writes, and its evaluation ----------------------
RECORD_KEYS = {
    "Diagnostic": (),
    "Status": (),
    "Provenance": ("ImageInfoDir", "ImageInfoDirIsDefault", "PALACE_VERSION",
                   "PALACE_COMMIT", "PALACE_PATCH", "PALACE_PATCH_SHA256", "ConfigMesh",
                   "MpiSize"),
    "Port": ("Index", "L_nd", "L_H", "NumElements"),
    "Dofs": ("True", "Essential", "Free"),
    "Scales": ("Lc_m", "tc_ns", "FrequencyScale_GHz", "InductanceScale_H", "A_GHz2_per_nd"),
    "Functional": ("NormSquaredFull", "NormSquaredFree", "NormSquaredEssential", "Check"),
    "LinearSolve": ("Type", "RelTol", "MaxIts", "Iterations", "Converged", "SolverFinalRes",
                    "ResidualNorm", "RhsNorm", "RelativeResidual", "SolutionNorm",
                    "SolutionEssentialNorm"),
    "A": ("A_nd", "A_GHz2", "ErrorIdentity", "XDotR_nd", "CertifiedErrorUpperBound_nd",
          "CertifiedErrorUpperBound_GHz2", "CertifiedLowerBound_A_nd",
          "CertifiedLowerBound_A_GHz2", "UncertifiedErrorEstimate_nd",
          "UncertifiedErrorEstimate_GHz2", "CertifiedUpperBound"),
    "NullSpaceCheck": ("Enabled", "IsSampledNotProof"),
    "Resources": ("WallTime_s", "MaxRSS_MB"),
}

#: Provenance every qualifying record must carry, checked against the record and against
#: the files on disk. Anything missing or mismatched prevents qualification.
REQUIRED_PROVENANCE_FIELDS = (
    "PALACE_VERSION", "PALACE_COMMIT", "PALACE_PATCH", "PALACE_PATCH_SHA256",
)
REQUIRED_DIGEST_FIELDS = ("config_sha256", "mesh_sha256", "patch_sha256",
                          "dockerfile_sha256", "image_id")

#: Frozen limits, carried as HARD CAPS on any execution; they are not runtime promises.
DOF_HARD_CAP = 250_000
WALL_HARD_CAP_S = 2_700


def validate_record(rec: dict) -> list[str]:
    missing = []
    for k, subs in RECORD_KEYS.items():
        if k not in rec:
            missing.append(k)
            continue
        for s in subs:
            if s not in rec[k]:
                missing.append(f"{k}.{s}")
    return missing


def synthetic_record(fx, Lc_m: float, *, residual_scale: float = 1e-13,
                     seed: int = 0, break_check: str | None = None,
                     provenance: dict | None = None) -> dict:
    """What the patched driver would write for the fixture, computed with the reference
    algebra, with a deliberately imperfect solve so the qualification is exercised.
    ``break_check`` names one thing to spoil."""
    rng = np.random.default_rng(seed)
    sc = unit_scales(Lc_m)
    f_full = fx.f_true
    f = restrict_to_free(f_full, fx.dbc)
    Mp = padded_mass(fx.M, fx.dbc, "DIAG_ONE")
    x_exact = np.linalg.solve(Mp, f)
    pert = rng.normal(size=x_exact.size)
    pert[fx.dbc] = 0.0
    x = x_exact + residual_scale * np.linalg.norm(x_exact) * pert / np.linalg.norm(pert)
    r = Mp @ x - f
    L = fx.L
    A_nd = float(f @ x / L)
    xr = float(x @ r)
    est = float(np.linalg.norm(x) * np.linalg.norm(r)) / L
    Et = rng.normal(size=fx.n_true) + 1j * rng.normal(size=fx.n_true)
    Et[fx.dbc] = 0.0
    V_ref = voltage_palace(fx.v_loc, fx.P, Et)
    V_f = voltage_from_functional(f, Et)
    rel = abs(V_f - V_ref) / abs(V_ref)
    if break_check == "functional":
        rel = 1e-3
    gaps = [null_space_gap(fx.K, f, L, x)]
    for _k in range(4):
        u = rng.normal(size=fx.n_true)
        u[fx.dbc] = 0.0
        gaps.append(null_space_gap(fx.K, f, L, u))
    min_gap = min(gaps) if break_check != "null_space" else -1e-3
    prov = {
        "ImageInfoDir": "/opt/palace",
        "ImageInfoDirIsDefault": True,
        "PALACE_VERSION": "0.13.0",
        "PALACE_COMMIT": "a61c8cbe0cacf496cde3c62e93085fae0d6299ac",
        "PALACE_PATCH": "first-moment-diagnostic",
        "PALACE_PATCH_SHA256": "0" * 64,
        "ConfigMesh": "fixture.msh",
        "MpiSize": 1,
    }
    if provenance:
        prov.update(provenance)
    if break_check == "provenance_missing":
        prov["PALACE_PATCH_SHA256"] = "unavailable"
    if break_check == "provenance_mismatch":
        prov["PALACE_COMMIT"] = "deadbeef" * 5
    if break_check == "developer_build":
        prov["ImageInfoDir"] = "/tmp/dev-build"
        prov["ImageInfoDirIsDefault"] = False
    return {
        "Diagnostic": "FirstMoment",
        "Status": "FAILED" if break_check == "status" else "COMPLETED",
        "Provenance": prov,
        "Port": {"Index": 1, "L_nd": L, "L_H": L * sc["InductanceScale_H"], "NumElements": 1},
        "Dofs": {"True": fx.n_true, "Essential": int(len(fx.dbc)),
                 "Free": fx.n_true - int(len(fx.dbc))},
        "Scales": {k: sc[k] for k in RECORD_KEYS["Scales"]},
        "Functional": {
            "NormSquaredFull": float(f_full @ f_full),
            "NormSquaredFree": float(f @ f),
            "NormSquaredEssential": float(f_full @ f_full - f @ f),
            "Check": {"Enabled": True, "Seed": seed, "V_GetVoltage": [V_ref.real, V_ref.imag],
                      "V_Functional": [V_f.real, V_f.imag], "RelativeError": rel,
                      "Tolerance": 1e-10, "Passed": rel < 1e-10},
        },
        "LinearSolve": {
            "Type": "PCG+Jacobi on M(DIAG_ONE)", "RelTol": 1e-12, "MaxIts": 2000,
            "Iterations": 17, "Converged": break_check != "convergence",
            "SolverFinalRes": float(np.linalg.norm(r)),
            "ResidualNorm": float(np.linalg.norm(r)), "RhsNorm": float(np.linalg.norm(f)),
            "RelativeResidual": float(np.linalg.norm(r) / np.linalg.norm(f)),
            "SolutionNorm": float(np.linalg.norm(x)),
            "SolutionEssentialNorm": float(np.linalg.norm(x[fx.dbc])),
        },
        "A": {
            "A_nd": A_nd,
            "A_GHz2": A_nd * sc["A_GHz2_per_nd"],
            "ErrorIdentity":
                "A_computed - A_exact = (Re(x^H r) - r^H M^-1 r) / L, with r = M x - f",
            "XDotR_nd": xr,
            "CertifiedErrorUpperBound_nd": xr / L,
            "CertifiedErrorUpperBound_GHz2": xr / L * sc["A_GHz2_per_nd"],
            "CertifiedLowerBound_A_nd": A_nd - xr / L,
            "CertifiedLowerBound_A_GHz2": (A_nd - xr / L) * sc["A_GHz2_per_nd"],
            "UncertifiedErrorEstimate_nd": est,
            "UncertifiedErrorEstimate_GHz2": est * sc["A_GHz2_per_nd"],
            "CertifiedUpperBound": "UNAVAILABLE",
        },
        "NullSpaceCheck": {"Enabled": True, "IsSampledNotProof": True, "NumSamples": 5,
                           "MinRelativeGap": min_gap, "Tolerance": -1e-10,
                           "Passed": min_gap >= -1e-10},
        "Resources": {"WallTime_s": 12.5, "MaxRSS_MB": 480.0},
    }


def evaluate(rec: dict, saved: dict, *, required_provenance: dict | None = None,
             actual: dict | None = None, expected_dofs: int | None = None,
             expected_L_H: float | None = None, residual_tol: float = 1e-12,
             dof_hard_cap: int = DOF_HARD_CAP,
             wall_hard_cap_s: float = WALL_HARD_CAP_S) -> dict:
    """Evaluate a diagnostic record against a saved partial first moment.

    FAIL CLOSED. Every provenance and numerical check must pass before the difference
    ``A_direct - A_saved`` may be read as an omitted first moment. Mass-solve uncertainty
    and A_saved uncertainty are reported separately and never merged into one number.
    Physical ``E_C`` and ``g`` are never produced here.

    ``saved`` carries the saved moment and its own interval; ``required_provenance`` the
    values a qualifying run must carry; ``actual`` the digests measured from the record.
    """
    checks = []

    def check(name, passed, detail):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    missing = validate_record(rec)
    check("record schema complete", not missing, {"missing": missing})
    if missing:
        return {"checks": checks, "all_checks_passed": False, "verdict": "UNQUALIFIED",
                "interpretation": "UNQUALIFIED: incomplete record",
                "E_C": "UNAVAILABLE", "g": "UNAVAILABLE"}

    # --- provenance, fail closed ---
    prov = rec["Provenance"]
    req = required_provenance or {}
    check("record status is COMPLETED", rec.get("Status") == "COMPLETED",
          {"status": rec.get("Status")})
    check("provenance carries no unavailable field",
          all(str(prov.get(k, "unavailable")) != "unavailable"
              for k in REQUIRED_PROVENANCE_FIELDS),
          {k: prov.get(k) for k in REQUIRED_PROVENANCE_FIELDS})
    check("run came from the image identity directory (/opt/palace), not a developer build",
          prov.get("ImageInfoDirIsDefault") is True,
          {"dir": prov.get("ImageInfoDir")})
    for key in REQUIRED_PROVENANCE_FIELDS:
        if key in req:
            check(f"embedded {key} matches the required value", prov.get(key) == req[key],
                  {"record": prov.get(key), "required": req[key]})
        else:
            check(f"required value for {key} was supplied", False,
                  {"record": prov.get(key), "required": None})
    act = actual or {}
    for key in REQUIRED_DIGEST_FIELDS:
        have, want = act.get(key), req.get(key)
        check(f"{key} measured and matches the required value",
              have is not None and want is not None and have == want,
              {"measured": have, "required": want})

    # --- the checks the driver performed ---
    fc, ls, sc, A, d = (rec["Functional"]["Check"], rec["LinearSolve"], rec["Scales"],
                        rec["A"], rec["Dofs"])
    check("functional reproduces GetVoltage (complex, PEC-constrained field)",
          fc.get("Enabled") and fc.get("Passed"),
          {"relative_error": fc.get("RelativeError"), "tolerance": fc.get("Tolerance")})
    nc = rec["NullSpaceCheck"]
    check("sampled K >= q q^H check ran and passed on every sample",
          nc.get("Enabled") and nc.get("Passed"),
          {"min_relative_gap": nc.get("MinRelativeGap"), "tolerance": nc.get("Tolerance"),
           "note": "sampled runtime check, not a proof for every vector"})
    check("linear solve converged", ls["Converged"], {"iterations": ls["Iterations"]})
    check(f"independent relative residual <= {residual_tol:g}",
          ls["RelativeResidual"] <= residual_tol,
          {"relative_residual": ls["RelativeResidual"]})
    check("solution vanishes on the essential dofs",
          ls["SolutionEssentialNorm"] <= 1e-14 * max(ls["SolutionNorm"], 1e-300),
          {"essential_norm": ls["SolutionEssentialNorm"], "norm": ls["SolutionNorm"]})
    check("Free == True - Essential", d["Free"] == d["True"] - d["Essential"], dict(d))
    check(f"true dofs within the {dof_hard_cap} hard cap", d["True"] <= dof_hard_cap,
          {"true": d["True"], "cap": dof_hard_cap})
    if expected_dofs is not None:
        check("same true-dof count as the saved eigenmode record",
              d["True"] == expected_dofs, {"true": d["True"], "expected": expected_dofs})
    if expected_L_H is not None:
        check("port inductance matches the configured L (henries)",
              abs(rec["Port"]["L_H"] - expected_L_H) <= 1e-12 * expected_L_H,
              {"L_H": rec["Port"]["L_H"], "expected": expected_L_H})

    def close(a, b, tol=1e-12):
        return abs(a - b) <= tol * max(abs(a), abs(b), 1e-300)

    ref = unit_scales(sc["Lc_m"])
    check("tc_ns == 1e9 Lc / c0", close(sc["tc_ns"], ref["tc_ns"], 1e-9),
          {"tc_ns": sc["tc_ns"], "expected": ref["tc_ns"]})
    check("FrequencyScale_GHz == 1/(2 pi tc)",
          close(sc["FrequencyScale_GHz"], ref["FrequencyScale_GHz"], 1e-9),
          {"scale": sc["FrequencyScale_GHz"], "expected": ref["FrequencyScale_GHz"]})
    check("InductanceScale_H == mu0 Lc",
          close(sc["InductanceScale_H"], ref["InductanceScale_H"], 1e-9),
          {"scale": sc["InductanceScale_H"], "expected": ref["InductanceScale_H"]})
    check("A_GHz2_per_nd == FrequencyScale^2",
          close(sc["A_GHz2_per_nd"], sc["FrequencyScale_GHz"] ** 2), {})
    check("A_GHz2 == A_nd * A_GHz2_per_nd",
          close(A["A_GHz2"], A["A_nd"] * sc["A_GHz2_per_nd"]),
          {"A_GHz2": A["A_GHz2"], "A_nd": A["A_nd"]})
    check("certified lower bound == A_nd - Re(x^H r)/L, converted consistently",
          close(A["CertifiedLowerBound_A_nd"], A["A_nd"] - A["CertifiedErrorUpperBound_nd"])
          and close(A["CertifiedLowerBound_A_GHz2"],
                    A["CertifiedLowerBound_A_nd"] * sc["A_GHz2_per_nd"]),
          {"lower_nd": A["CertifiedLowerBound_A_nd"], "A_nd": A["A_nd"],
           "err_ub_nd": A["CertifiedErrorUpperBound_nd"]})
    check("no certified upper bound is claimed", A["CertifiedUpperBound"] == "UNAVAILABLE",
          {"value": A["CertifiedUpperBound"]})
    check("L_H == L_nd * InductanceScale_H",
          close(rec["Port"]["L_H"], rec["Port"]["L_nd"] * sc["InductanceScale_H"]), {})
    check(f"wall time within the {wall_hard_cap_s} s hard cap",
          rec["Resources"]["WallTime_s"] <= wall_hard_cap_s,
          {"wall_s": rec["Resources"]["WallTime_s"], "cap_s": wall_hard_cap_s})

    all_ok = all(c["passed"] for c in checks)

    # --- the two uncertainties, kept apart ---
    A_direct = A["A_GHz2"]
    A_lower = A["CertifiedLowerBound_A_GHz2"]
    est = A["UncertifiedErrorEstimate_GHz2"]
    sv_c, sv_lo, sv_hi = saved["central_GHz2"], saved["lo_GHz2"], saved["hi_GHz2"]
    sv_half = saved.get("halfwidth_GHz2", 0.5 * (sv_hi - sv_lo))
    lam_min_needed = (ls["ResidualNorm"] / ls["SolutionNorm"]) if ls["SolutionNorm"] else None
    mass_solve_uncertainty = {
        "identity": A["ErrorIdentity"],
        "x_dot_r_nd": A["XDotR_nd"],
        "certified_error_upper_bound_GHz2": A["CertifiedErrorUpperBound_GHz2"],
        "certified_lower_bound_A_GHz2": A_lower,
        "certified_upper_bound_A_GHz2": "UNAVAILABLE",
        "uncertified_error_estimate_GHz2": est,
        "why_the_estimate_is_not_a_bound": (
            "the identity's r^H M^-1 r term is bounded by ||r||^2 / lambda_min(M_free), "
            "which exceeds ||x|| ||r|| whenever lambda_min(M_free) < ||r||/||x||"),
        "sufficient_condition_for_the_estimate_to_be_a_bound": {
            "condition": "lambda_min(M_free) >= ||r|| / ||x||",
            "threshold": lam_min_needed,
            "lambda_min_measured": False,
        },
        "why_no_certified_upper_bound": (
            "a certified upper bound on A_exact requires r^H M^-1 r, hence a lower bound "
            "on lambda_min(M_free) or a second solve; neither is authorised or performed"),
    }
    A_saved_uncertainty = {
        "central_GHz2": sv_c,
        "printed_precision_interval_GHz2": [sv_lo, sv_hi],
        "halfwidth_GHz2": sv_half,
        "source": saved.get("source"),
        "eigensolver_convergence": saved.get("eigensolver_convergence",
                                             {"propagated_into_A": "UNQUANTIFIED"}),
        "kept_separate_from_mass_solve_uncertainty": True,
    }

    # --- the discrepancy and its verdict ---
    diff = A_direct - sv_c
    certified_omitted_lower = A_lower - sv_hi
    negative_margin = -(sv_half + est)
    if not all_ok:
        verdict = "UNQUALIFIED"
    elif certified_omitted_lower > 0.0:
        verdict = "OMITTED_MOMENT_CERTIFIED_LOWER_BOUND"
    elif diff < negative_margin:
        verdict = "INCONSISTENT"
    else:
        verdict = "NOT_RESOLVED"
    interpretation = {
        "UNQUALIFIED": ("UNQUALIFIED: a provenance or numerical check failed; the "
                        "difference is not an omitted spectral moment"),
        "OMITTED_MOMENT_CERTIFIED_LOWER_BOUND": (
            "the modes absent from the saved set carry at least "
            f"{certified_omitted_lower:.6e} GHz^2 of first moment"),
        "INCONSISTENT": (
            "INCONSISTENT: A_direct is materially below A_saved, which the non-negative "
            "mode weights forbid. Either the mass solve is under-converged (A_computed "
            "underestimates A_exact by r^H M^-1 r) or the functional, space or "
            "normalisation does not match the saved record. NOT an omitted moment."),
        "NOT_RESOLVED": ("NOT RESOLVED: the difference lies inside the combined "
                         "uncertainty; this is not evidence of a small tail"),
    }[verdict]
    return {
        "checks": checks,
        "all_checks_passed": all_ok,
        "verdict": verdict,
        "interpretation": interpretation,
        "A_direct": {"A_nd": A["A_nd"], "A_GHz2": A_direct,
                     "certified_lower_bound_GHz2": A_lower},
        "A_saved": {"central_GHz2": sv_c, "modes": saved.get("modes")},
        "difference": {
            "A_direct_minus_A_saved_GHz2": diff,
            "relative_to_A_saved": diff / sv_c if sv_c else None,
            "certified_omitted_moment_lower_bound_GHz2": certified_omitted_lower,
            "materially_negative_threshold_GHz2": negative_margin,
        },
        "mass_solve_uncertainty": mass_solve_uncertainty,
        "A_saved_uncertainty": A_saved_uncertainty,
        "tail_upper_bound": "UNAVAILABLE",
        "not_established_here": [
            "no upper bound on A_exact is certified, so a small difference NEVER "
            "establishes a small omitted tail; it establishes only 'not resolved'",
            "the eigensolver convergence error of A_saved is not propagated into A_saved's "
            "interval and must be accounted for before any tail conclusion",
            "the sampled K >= q q^H check is a runtime sanity check on finitely many "
            "vectors, not a proof; the proof is the separate quadrature-parity argument",
        ],
        "N": "not measured by this diagnostic",
        "E_C": "UNAVAILABLE",
        "g": "UNAVAILABLE",
    }


# --- the synthetic verification ---------------------------------------------------------
def run_trials(trials: int = TRIALS, seed: int = RNG_SEED) -> dict:
    rng = np.random.default_rng(seed)
    worst = {
        "dual_assembly_vs_GetVoltage": 0.0,
        "free_restricted_functional_vs_GetVoltage_when_E_dbc_is_zero": 0.0,
        "free_restricted_functional_mismatch_when_E_dbc_nonzero_min": math.inf,
        "padded_DIAG_ONE_zeroed_rhs_vs_free": 0.0,
        "padded_DIAG_ONE_unzeroed_rhs_minus_free_vs_sum_f_dbc2_over_L": 0.0,
        "padded_DIAG_ZERO_singular_in_every_trial": True,
        "parseval_all_modes_vs_free_solve": 0.0,
        "parseval_nonzero_modes_vs_free_solve": 0.0,
        "kernel_annihilation_same_points": 0.0,
        "kernel_dim_min": math.inf,
        "K_port_minus_qq_min_eig_same_rule_min": math.inf,
        "K_port_minus_qq_min_eig_mismatched_rule_min": math.inf,
        "null_space_gap_min_over_random_fields": math.inf,
        "epr_palace_vs_absolute_square": 0.0,
        "epr_phase_invariance": 0.0,
        "A_phase_invariance": 0.0,
        "unit_roundtrip_A_GHz2": 0.0,
        "zeroth_moment_vs_pseudoinverse": 0.0,
    }
    for _ in range(trials):
        fx = Fixture(rng)
        f_full, dbc, L = fx.f_true, fx.dbc, fx.L
        f = restrict_to_free(f_full, dbc)

        # 1. dual assembly: (P^T v) . E == v . (P E) for ANY complex true vector.
        E = rng.normal(size=fx.n_true) + 1j * rng.normal(size=fx.n_true)
        Vp = voltage_palace(fx.v_loc, fx.P, E)
        worst["dual_assembly_vs_GetVoltage"] = max(
            worst["dual_assembly_vs_GetVoltage"], abs(voltage_from_functional(f_full, E) - Vp) / abs(Vp))
        # the free-restricted f agrees iff E vanishes on the essential dofs
        Ec = E.copy()
        Ec[dbc] = 0.0
        Vc = voltage_palace(fx.v_loc, fx.P, Ec)
        worst["free_restricted_functional_vs_GetVoltage_when_E_dbc_is_zero"] = max(
            worst["free_restricted_functional_vs_GetVoltage_when_E_dbc_is_zero"],
            abs(voltage_from_functional(f, Ec) - Vc) / abs(Vc))
        worst["free_restricted_functional_mismatch_when_E_dbc_nonzero_min"] = min(
            worst["free_restricted_functional_mismatch_when_E_dbc_nonzero_min"],
            abs(voltage_from_functional(f, E) - Vp) / abs(Vp))

        # 2. constrained mass operator.
        A_free = first_moment_free(fx.M, f_full, dbc, L)
        A_pad = first_moment_padded(fx.M, f_full, dbc, L, "DIAG_ONE", True)
        A_bad = first_moment_padded(fx.M, f_full, dbc, L, "DIAG_ONE", False)
        worst["padded_DIAG_ONE_zeroed_rhs_vs_free"] = max(
            worst["padded_DIAG_ONE_zeroed_rhs_vs_free"], abs(A_pad - A_free) / A_free)
        art = float(f_full[dbc] @ f_full[dbc]) / L
        worst["padded_DIAG_ONE_unzeroed_rhs_minus_free_vs_sum_f_dbc2_over_L"] = max(
            worst["padded_DIAG_ONE_unzeroed_rhs_minus_free_vs_sum_f_dbc2_over_L"],
            abs((A_bad - A_free) - art) / art)
        worst["padded_DIAG_ZERO_singular_in_every_trial"] &= (
            first_moment_padded(fx.M, f_full, dbc, L, "DIAG_ZERO", True) is None)

        # 3. Parseval and the null space on the constrained pencil.
        lam, Em = constrained_eigenbasis(fx.K, fx.M, dbc)
        p_all, p_nz = parseval_first_moment(f, L, lam, Em)
        worst["parseval_all_modes_vs_free_solve"] = max(
            worst["parseval_all_modes_vs_free_solve"], abs(p_all - A_free) / A_free)
        worst["parseval_nonzero_modes_vs_free_solve"] = max(
            worst["parseval_nonzero_modes_vs_free_solve"], abs(p_nz - A_free) / A_free)
        free = fx.free
        Kf = fx.K[np.ix_(free, free)]
        worst["kernel_annihilation_same_points"] = max(
            worst["kernel_annihilation_same_points"], kernel_annihilation(Kf, f[free]))
        wK = np.linalg.eigvalsh(Kf)
        worst["kernel_dim_min"] = min(worst["kernel_dim_min"], int((wK < 1e-10 * wK.max()).sum()))
        Kp = fx.K_port[np.ix_(free, free)]
        worst["K_port_minus_qq_min_eig_same_rule_min"] = min(
            worst["K_port_minus_qq_min_eig_same_rule_min"],
            port_inequality_min_eig(Kp, f[free], L) / np.linalg.eigvalsh(Kp).max())
        # negative control: v from a mismatched rule (lumped, unequal weights).
        a2 = fx.a * rng.uniform(0.2, 1.8, size=fx.a.size)
        a2 *= fx.a.sum() / a2.sum()
        f2 = restrict_to_free(dual_assemble(fx.P, fx.Q.T @ (a2 * fx.c)), dbc)
        worst["K_port_minus_qq_min_eig_mismatched_rule_min"] = min(
            worst["K_port_minus_qq_min_eig_mismatched_rule_min"],
            port_inequality_min_eig(Kp, f2[free], L) / np.linalg.eigvalsh(Kp).max())
        for _k in range(3):
            u = rng.normal(size=fx.n_true)
            u[dbc] = 0.0
            worst["null_space_gap_min_over_random_fields"] = min(
                worst["null_space_gap_min_over_random_fields"], null_space_gap(fx.K, f, L, u))
        Nq = zeroth_moment(f, L, lam, Em)
        Npinv = float(f[free] @ np.linalg.pinv(Kf) @ f[free] / L)
        worst["zeroth_moment_vs_pseudoinverse"] = max(
            worst["zeroth_moment_vs_pseudoinverse"], abs(Nq - Npinv) / Npinv)

        # 4. EPR reconciliation and phase invariance, on a nonzero mode.
        keep = np.nonzero(lam > 1e-9 * lam.max())[0]
        m = int(rng.choice(keep))
        theta = rng.uniform(0, 2 * math.pi)
        Emode = Em[:, m] * (3.7 * np.exp(1j * theta))      # arbitrary complex scaling
        omega = math.sqrt(lam[m])
        Vm = voltage_from_functional(f, Emode)
        p_pal = epr_palace(Vm, L, omega, electric_energy_palace(fx.M, Emode))
        p_abs = epr_from_functional(f, L, lam[m], fx.M, Emode)
        worst["epr_palace_vs_absolute_square"] = max(
            worst["epr_palace_vs_absolute_square"], abs(abs(p_pal) - p_abs) / p_abs)
        p_abs0 = epr_from_functional(f, L, lam[m], fx.M, Em[:, m].astype(complex))
        worst["epr_phase_invariance"] = max(worst["epr_phase_invariance"], abs(p_abs - p_abs0) / p_abs0)
        Eph = Em[:, keep] * np.exp(1j * rng.uniform(0, 2 * math.pi, size=keep.size))
        q = f / math.sqrt(L)
        A_ph = float(np.sum(np.abs(q @ Eph) ** 2))
        worst["A_phase_invariance"] = max(worst["A_phase_invariance"], abs(A_ph - p_nz) / p_nz)

        # 5. units: a mode at f GHz has lambda_nd = (2 pi f tc)^2, so A_GHz2 = sum p f^2.
        Lc = rng.uniform(1e-3, 1e-2)
        tc = unit_scales(Lc)["tc_ns"]
        fghz = rng.uniform(1, 20, size=4)
        p = rng.uniform(0, 1, size=4)
        A_nd = float((p * lambda_nd_from_f_ghz(fghz, tc)).sum())
        worst["unit_roundtrip_A_GHz2"] = max(
            worst["unit_roundtrip_A_GHz2"],
            abs(a_ghz2_from_nd(A_nd, tc) - float((p * fghz ** 2).sum())) / float((p * fghz ** 2).sum()))
    return worst


def run_error_trials(trials: int = 40, seed: int = RNG_SEED + 1) -> dict:
    """The residual error qualification, verified and falsified where it should be."""
    rng = np.random.default_rng(seed)
    worst = {
        "identity_max_error_relative_to_A": 0.0,
        "certified_bound_violations": 0,
        "variational_equals_certified_max_rel": 0.0,
        "cg_like_solution_A_hat_never_exceeds_A_exact": True,
        "max_shortfall_of_A_hat_below_A_exact_relative": 0.0,
    }
    for _ in range(trials):
        fx = Fixture(rng)
        f = restrict_to_free(fx.f_true, fx.dbc)
        Mp = padded_mass(fx.M, fx.dbc, "DIAG_ONE")
        x_star = np.linalg.solve(Mp, f)
        for scale in (1e-3, 1e-7, 1e-12):
            pert = rng.normal(size=x_star.size)
            pert[fx.dbc] = 0.0
            x = x_star + scale * np.linalg.norm(x_star) * pert / np.linalg.norm(pert)
            idn = residual_error_identity(Mp, f, x, fx.L)
            # The identity is checked against |A| rather than against the difference: for a
            # well-converged solve the two sides agree to round-off while their common
            # value is many orders smaller than A, so a RELATIVE comparison of the
            # difference would measure the cancellation in A_hat - A_exact, not the
            # identity.
            worst["identity_max_error_relative_to_A"] = max(
                worst["identity_max_error_relative_to_A"],
                abs(idn["lhs"] - idn["rhs"]) / max(abs(idn["A_exact"]), 1e-300))
            if idn["lhs"] > idn["certified_error_upper_bound"] + 1e-12 * abs(idn["A_exact"]):
                worst["certified_bound_violations"] += 1
            worst["variational_equals_certified_max_rel"] = max(
                worst["variational_equals_certified_max_rel"],
                abs(idn["variational_lower_bound_A"] - idn["certified_lower_bound_A"])
                / max(abs(idn["certified_lower_bound_A"]), 1e-300))
        # a CG-like iterate: x in a Krylov space, residual M-orthogonal to it, so x.r = 0
        K = np.column_stack([np.linalg.matrix_power(Mp, k) @ f for k in range(4)])
        Q, _ = np.linalg.qr(K)
        G = Q.T @ Mp @ Q
        x_cg = Q @ np.linalg.solve(G, Q.T @ f)      # M-projection of x* onto span(Q)
        idn = residual_error_identity(Mp, f, x_cg, fx.L)
        if idn["A_hat"] > idn["A_exact"] * (1 + 1e-12):
            worst["cg_like_solution_A_hat_never_exceeds_A_exact"] = False
        worst["max_shortfall_of_A_hat_below_A_exact_relative"] = max(
            worst["max_shortfall_of_A_hat_below_A_exact_relative"],
            (idn["A_exact"] - idn["A_hat"]) / abs(idn["A_exact"]))
    return worst


def main() -> None:
    worst = run_trials()
    n2r = unit_scales(4.0e-3)
    out = {
        "label": "FIRST-MOMENT DIAGNOSTIC - REFERENCE MODEL VERIFIED ON SYNTHETIC FIXTURES",
        "trials": TRIALS,
        "seed": RNG_SEED,
        "worst_case": worst,
        "expected_N2R_scales_from_Lc_4mm": {
            **n2r,
            "note": ("Lc = 4.000e-03 m is the mesh bounding-box extent Palace printed for N2R "
                     "(palace_log.txt:18-19, 't0 = 1.334e-02 ns'); the diagnostic record "
                     "reports the exact values and the evaluator uses those, not these."),
        },
        "expected_N2R_L_nd": inductance_nd(1.0345665367517793e-07, 4.0e-3),
        "error_qualification": {
            "identity": "A_computed - A_exact = (Re(x^H r) - r^H M^-1 r) / L, r = M x - f",
            "trials": run_error_trials(),
            "counterexamples_to_the_old_quantity": [
                {k: v for k, v in bound_counterexample(eps, delta).items()
                 if k in ("eps", "delta", "relative_residual", "lhs", "rhs",
                          "uncertified_estimate", "certified_error_upper_bound",
                          "estimate_is_a_bound", "certified_bound_holds",
                          "violation_factor")}
                for eps, delta in ((1e-12, 1e-4), (1e-16, 1e-13), (1e-8, 1e-6))
            ],
            "reading": (
                "||x|| ||r|| / L is an ESTIMATE. It fails as a bound exactly when "
                "lambda_min(M_free) < ||r||/||x||, and the third counterexample has a "
                "relative residual of 1e-13, i.e. it would pass the residual check. The "
                "certified statement is one-sided: A_exact >= A_computed - Re(x^H r)/L."),
        },
        "hard_caps": {"dof": DOF_HARD_CAP, "wall_s": WALL_HARD_CAP_S,
                      "meaning": "hard caps on any execution, not runtime promises"},
        "what_is_and_is_not_verified": {
            "verified_here": [
                "P^T v is the dual assembly GetVoltage's summed local dot products imply",
                "the free-restricted functional reproduces GetVoltage exactly when the field "
                "satisfies the PEC constraint, and only then",
                "DIAG_ONE padding with the right-hand side zeroed on the essential dofs is the "
                "free-dof quadratic form; without the zeroing it adds sum_dbc f_dbc^2 / L; "
                "DIAG_ZERO padding is singular",
                "Parseval: A equals the sum over the complete constrained eigenbasis, and "
                "over the nonzero modes alone, because f annihilates ker(K)",
                "f in range(K_port) whenever v and K_port share quadrature POINTS with "
                "positive weights; K_port >= q q^T whenever they share the WEIGHTS too; a "
                "mismatched rule breaks the inequality (negative control)",
                "Palace's EPR magnitude equals |f^H E|^2 / (L lambda E^H M E) with its 1/2 "
                "energy convention, and both are phase invariant",
                "A_GHz2 = A_nd / (2 pi tc)^2 is the sum of p f^2 with f in GHz",
            ],
            "not_verified_here": [
                "the C++ patch is not compiled in this environment (no Palace toolchain); "
                "its built-in checks run on the real problem only under a separate approval",
                "no N2R matrix, functional or moment is assembled or solved",
            ],
        },
    }
    (HERE / "reference_model.json").write_text(json.dumps(out, indent=1) + "\n")
    print(out["label"])
    for k, v in worst.items():
        print(f"  {k:<70} {v}")


if __name__ == "__main__":
    main()
