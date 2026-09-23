# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""The two static Dirichlet problems of the static-only nested refinement study, the
solvers for them, and a rigorous a-posteriori bound on every energy they report.

Problems (P1, eps-weighted, on anchor_fem's nondimensional mesh; anchor_fem is unchanged):

  "C"       phi = 1 on the island, 0 on ground. C_h = eps0 Lc E_h: the static-anchor quantity.
  "Cprime"  the same, and phi on every port-face node is also held at the linear function
            of the coordinate along the port direction (0 on the ground end line, 1 on the
            island end line). More constraints, so C'_h >= C_h. For Palace's distributed
            sheet port S_h = (1 + delta_h) H_h exactly, delta_h = C'_h / C_h - 1
            (docs/coupled-candidate/static-band-pairing.md section 2).

Solvers:

  direct    scipy spsolve (SuperLU) with exactly the expressions static_capacitance.py uses,
            so problem C at levels 0 and 1 must reproduce the executed static-anchor record.
  twogrid   preconditioned conjugate gradients. The preconditioner is one symmetric
            two-grid cycle on the nested hierarchy: NU forward Gauss-Seidel sweeps, an exact
            coarse correction with the Galerkin operator P^T A P (SuperLU), NU backward
            Gauss-Seidel sweeps. Backward is the adjoint of forward, so the cycle is
            symmetric; Gauss-Seidel contracts in the energy norm for SPD A, so it is positive
            definite. The initial guess is the prolonged coarse solution. The preconditioner
            only affects speed: the certificate below does not depend on it.

Certificate (both solvers, the same code):

  The discrete problem is the quadratic form phi^T K phi of the ASSEMBLED matrix K, which
  sees only its symmetric part K_s. With the Dirichlet data imposed exactly,
  E(phi~) - E_h = e^T A_s e = r_s^T A_s^-1 r_s >= 0 for the TRUE residual of the symmetric
  problem, r_s = r + (A - A^T) x / 2 + (K_fD - K_Df^T) phi_D / 2 with r = b - A x: an inexact
  solve can only RAISE the energy. If the mesh tiles its bounding box B (conforming; every
  interior face separates its two tetrahedra; every boundary face lies on the surface of B;
  sum |vol| = vol(B)) and every node of every boundary face is constrained, a homogeneous
  discrete function extends by zero into H1_0(B), and

      x^T A_s x >= eps_min int |grad v|^2 >= eps_min lambda_1(B) int v^2
                >= eps_min lambda_1(B) sum_i m_i x_i^2,   m_i = sum_{K contains i} vol_K / 20

  (Dirichlet eigenvalue monotonicity under domain inclusion; the P1 element mass
  vol/20 (I + 1 1^T) dominates vol/20 I). So A_s >= c D_m with c = eps_min lambda_1(B), and

      0 <= E(phi~) - E_h <= sum_i r_s,i^2 / m_i / c.

  |r_s,i| is bounded by the computed residual, the computed asymmetry terms and the
  floating-point error of computing r and b (gamma_n = n u / (1 - n u)).

  Evaluation error: phi^T K phi is re-evaluated in extended precision as y = K phi, then
  s = phi . y. |s - phi^T K phi| <= gamma_k |phi|^T |K| |phi| + gamma_n sum |phi_i y_i|
  (k the longest row, n the length; u of the extended format). The n-term factor multiplies
  sum |phi_i y_i|, which carries no cancellation: y vanishes at free nodes to solver
  accuracy and is the nodal charge at constrained ones. The float64 energy's error is that
  bound plus |e64 - s| and the rounding of s to float64.

  Relative to the assembled operator: the round-off of assembling K from the coordinates
  (about 1e-14 relative) is common to every solver and is NOT certified. "Rigorous" in this
  study always means rigorous relative to the assembled operator.

Nothing here reads the QMHP mesh, launches anything or writes anything.
"""
from __future__ import annotations

import hashlib
import math
import sys
import time
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "static-anchor-hypothesis"))
import anchor_fem as af  # noqa: E402

KINDS = ("C", "Cprime")
U64 = float(np.finfo(np.float64).eps) / 2.0
ULD = float(np.finfo(np.longdouble).eps) / 2.0
#: covers the floating-point evaluation of the bound itself (relative error < n u < 1e-9)
BOUND_SAFETY = 1.001


class Refusal(RuntimeError):
    """A precondition of the method does not hold; nothing is computed."""


def gamma(n: int, u: float = U64) -> float:
    return n * u / (1.0 - n * u)


def require_extended_precision() -> None:
    """The evaluation-error bound needs a long double wider than float64."""
    if not np.finfo(np.longdouble).eps < 1e-18:
        raise Refusal(f"np.longdouble has eps {np.finfo(np.longdouble).eps}: no extended "
                      "precision on this platform, so the evaluation-error bound is unavailable")


# --- mesh facts -----------------------------------------------------------------------

def mesh_digest(mesh: dict) -> str:
    """sha256 over the canonical little-endian bytes and shapes of the mesh arrays."""
    h = hashlib.sha256()
    for key in ("xyz", "tets", "tet_attr", "tris", "tri_attr"):
        a = np.ascontiguousarray(mesh[key]).astype("<f8" if key == "xyz" else "<i8")
        h.update(key.encode())
        h.update(repr(a.shape).encode())
        h.update(a.tobytes())
    return h.hexdigest()


def boundary_facts(mesh: dict, xyz_nd=None) -> dict:
    """Faces shared by one tetrahedron: their nodes, the face multiplicity, and whether
    each is a tagged triangle (a hanging node would leave an untagged one). With the
    coordinates, also whether the mesh tiles its bounding box: every interior face
    separates its two tetrahedra, every boundary face lies on the box surface, and the
    unsigned volumes sum to the box volume. A folded or overlapping mesh fails these."""
    t, n = mesh["tets"], len(mesh["xyz"])
    if n ** 3 >= 2 ** 63:
        raise Refusal("too many nodes for the face key")
    loc = ((0, 1, 2, 3), (0, 1, 3, 2), (0, 2, 3, 1), (1, 2, 3, 0))
    faces = np.sort(np.vstack([t[:, list(f[:3])] for f in loc]), axis=1).astype(np.int64)
    opp = np.concatenate([t[:, f[3]] for f in loc])
    key = (faces[:, 0] * n + faces[:, 1]) * n + faces[:, 2]
    order = np.argsort(key, kind="stable")
    key, faces, opp = key[order], faces[order], opp[order]
    del order
    uk, first, cnt = np.unique(key, return_index=True, return_counts=True)
    single = uk[cnt == 1]
    tri = np.sort(mesh["tris"], axis=1).astype(np.int64)
    tkey = (tri[:, 0] * n + tri[:, 1]) * n + tri[:, 2]
    nodes = np.unique(np.concatenate([single // (n * n), (single // n) % n, single % n]))
    out = {"max_face_multiplicity": int(cnt.max()), "boundary_faces": int(len(single)),
           "every_boundary_face_is_tagged": bool(np.isin(single, tkey).all()),
           "boundary_nodes": nodes}
    if xyz_nd is not None:
        lo, hi = xyz_nd.min(0), xyz_nd.max(0)
        ext = hi - lo
        tol = 1e-12 * float(ext.max())
        bf = faces[first[cnt == 1]]
        P = xyz_nd[bf]                                        # (nb, 3, 3)
        on = np.zeros(len(bf), dtype=bool)
        for ax in range(3):
            for v in (lo[ax], hi[ax]):
                on |= np.all(np.abs(P[:, :, ax] - v) <= tol, axis=1)
        pair = first[cnt == 2]
        f2, o1, o2 = faces[pair], opp[pair], opp[pair + 1]
        del faces, opp, key
        a0, a1, a2 = xyz_nd[f2[:, 0]], xyz_nd[f2[:, 1]], xyz_nd[f2[:, 2]]
        nrm = np.cross(a1 - a0, a2 - a0)
        s1 = np.einsum("ij,ij->i", nrm, xyz_nd[o1] - a0)
        s2 = np.einsum("ij,ij->i", nrm, xyz_nd[o2] - a0)
        _, vol = af._tet_geometry(xyz_nd, t)
        out.update({"every_boundary_face_on_the_box_surface": bool(on.all()),
                    "every_interior_face_separates_its_tetrahedra": bool(np.all(s1 * s2 < 0)),
                    "volume_sum_over_box_minus_1": float(vol.sum() / float(np.prod(ext)) - 1.0)})
    return out


#: sum |vol| / vol(B) - 1 must be within this for the mesh to count as tiling its box
TILING_VOLUME_TOL = 1e-9


def nodal_mass_lower(mesh: dict, xyz_nd) -> np.ndarray:
    """m_i = sum over tetrahedra containing node i of vol / 20 (nondimensional)."""
    _, vol = af._tet_geometry(xyz_nd, mesh["tets"])
    m = np.zeros(len(xyz_nd))
    np.add.at(m, mesh["tets"].ravel(), np.repeat(vol / 20.0, 4))
    return m


def poincare_constant(mesh: dict, xyz_nd, eps_r: dict) -> dict:
    """c = eps_min lambda_1(B), B the bounding box of the nondimensional mesh."""
    ext = xyz_nd.max(0) - xyz_nd.min(0)
    lam1 = math.pi ** 2 * float((1.0 / ext ** 2).sum())
    eps_min = float(min(eps_r[int(a)] for a in np.unique(mesh["tet_attr"])))
    return {"box_extent_nd": ext.tolist(), "lambda1_box": lam1, "eps_min": eps_min,
            "c": eps_min * lam1}


def element_quality(mesh: dict, xyz_nd) -> dict:
    """Radius-ratio aspect (1 for a regular tetrahedron) and edge-length spread."""
    p = xyz_nd[mesh["tets"]]
    E = np.stack([np.linalg.norm(p[:, a] - p[:, b], axis=1) for a, b in af.TET_EDGES], 1)
    _, vol = af._tet_geometry(xyz_nd, mesh["tets"])
    area = sum(0.5 * np.linalg.norm(np.cross(p[:, b] - p[:, a], p[:, c] - p[:, a]), axis=1)
               for a, b, c in ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)))
    ar = E.max(1) / (2.0 * math.sqrt(6.0) * (3.0 * vol / area))
    return {"aspect_p50_p90_p99_max": [float(v) for v in np.percentile(ar, [50, 90, 99])]
            + [float(ar.max())],
            "edge_nd_min_median_max": [float(E.min()), float(np.median(E)), float(E.max())]}


# --- the port face and the Dirichlet data ------------------------------------------------

def port_geometry(mesh: dict, xyz_nd, model: dict, ground, island) -> dict:
    """The facts the sheet-port identity needs: a planar rectangle along the direction whose
    conductor nodes lie only on its two end lines (ground at t_g, island at t_i)."""
    tris = mesh["tris"][mesh["tri_attr"] == model["port_attr"]]
    if len(tris) == 0:
        raise Refusal(f"no triangles carry port attribute {model['port_attr']}")
    pn = np.unique(tris)
    d = np.asarray(model["direction"], float)
    d = d / np.linalg.norm(d)
    t = xyz_nd @ d
    pg, pi = np.intersect1d(pn, ground), np.intersect1d(pn, island)
    if len(pg) == 0 or len(pi) == 0:
        raise Refusal("the port face does not bridge the two conductors")
    tg, ti = float(t[pg].mean()), float(t[pi].mean())
    l = abs(ti - tg)
    p = xyz_nd[tris]
    nrm = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area = 0.5 * np.linalg.norm(nrm, axis=1)
    nh = nrm / np.linalg.norm(nrm, axis=1)[:, None]
    u = np.cross(nh[0], d)
    u = u / np.linalg.norm(u)
    w = float(np.ptp(xyz_nd[pn] @ u))
    lo, hi = min(tg, ti), max(tg, ti)
    return {"t_ground": tg, "t_island": ti, "l_nd": l, "w_nd": w, "n_port_tris": int(len(tris)),
            "n_port_nodes": int(len(pn)),
            "end_line_spread_rel": float(max(np.ptp(t[pg]), np.ptp(t[pi])) / l),
            "outside_end_lines_rel": float(max(0.0, lo - t[pn].min(), t[pn].max() - hi) / l),
            "normal_spread": float(np.abs(np.cross(nh, nh[0])).max()),
            "direction_out_of_plane": float(abs(nh[0] @ d)),
            "area_over_lw_minus_1": float(area.sum() / (l * w) - 1.0),
            "port_nodes": pn, "t": t}


PORT_GEOMETRY_TOL = 1e-12
#: diagnostic only: how well the Gauss-Seidel triangular solves reproduce a probe vector
GS_PROBE_TOL = 1e-10


def port_geometry_problems(geo: dict) -> list[str]:
    bad = []
    for key in ("end_line_spread_rel", "outside_end_lines_rel", "normal_spread",
                "direction_out_of_plane"):
        if not geo[key] <= PORT_GEOMETRY_TOL:
            bad.append(f"port face: {key} = {geo[key]!r}")
    if not abs(geo["area_over_lw_minus_1"]) <= PORT_GEOMETRY_TOL:
        bad.append(f"port face is not the l x w rectangle: {geo['area_over_lw_minus_1']!r}")
    return bad


def port_voltage(mesh: dict, xyz_nd, geo: dict, model: dict, phi) -> float:
    """(1/w) int_port grad(phi) . d dS, on the face itself. For any phi that is 0 along the
    whole ground end line and 1 along the whole island end line it is exactly 1."""
    tris = mesh["tris"][mesh["tri_attr"] == model["port_attr"]]
    p = xyz_nd[tris]
    e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
    nrm = np.cross(e1, e2)
    area = 0.5 * np.linalg.norm(nrm, axis=1)
    J = np.stack([e1, e2, nrm / np.linalg.norm(nrm, axis=1)[:, None]], 2)
    Ginv = np.linalg.inv(J)
    grad = (Ginv[:, 0] * (phi[tris[:, 1]] - phi[tris[:, 0]])[:, None]
            + Ginv[:, 1] * (phi[tris[:, 2]] - phi[tris[:, 0]])[:, None])
    d = np.asarray(model["direction"], float)
    d = d / np.linalg.norm(d)
    return float((area * (grad @ d)).sum() / geo["w_nd"])


def dirichlet(mesh: dict, xyz_nd, model: dict, kind: str) -> dict:
    """Constrained nodes and their values. Problem C is set up exactly as
    static_capacitance.static_capacitance; Cprime exactly as spectral.port_constrained_energy."""
    if kind not in KINDS:
        raise ValueError(kind)
    comps = af.conductor_components(mesh, model["pec_attrs"])
    if len(comps) != 2:
        raise Refusal(f"{len(comps)} conductors; the study is defined for exactly two")
    ground, island = comps[0], comps[1]
    geo = port_geometry(mesh, xyz_nd, model, ground, island)
    n = len(xyz_nd)
    fixed = np.zeros(n, dtype=bool)
    fixed[island] = fixed[ground] = True
    phi = np.zeros(n)
    phi[island] = 1.0
    if kind == "Cprime":
        pn, t = geo["port_nodes"], geo["t"]
        inner = pn[~fixed[pn]]
        phi[inner] = (t[inner] - geo["t_ground"]) / (geo["t_island"] - geo["t_ground"])
        fixed[inner] = True
    used = np.unique(mesh["tets"])
    free = used[~fixed[used]]
    return {"fixed": fixed, "phi": phi, "free": free, "ground": ground, "island": island,
            "geo": geo}


# --- the linear algebra ----------------------------------------------------------------

def system(K, dd: dict) -> dict:
    """A = K_ff and b = -K_fD phi_D, with exactly static_capacitance's expressions, and the
    moduli of the assembled matrix's asymmetry, which the certificate must include."""
    free, fixed, phi = dd["free"], dd["fixed"], dd["phi"]
    KfD = K[free][:, fixed]
    rhs = -(KfD @ phi[fixed])
    A = K[free][:, free].tocsr()
    KDf = K[fixed][:, free].tocsr()
    return {"A": A, "b": rhs, "KfD": KfD.tocsr(), "phiD": phi[fixed],
            "A_asym_abs": abs(A - A.T).tocsr(), "D_asym_abs": abs(KfD - KDf.T).tocsr()}


def solve_direct(sysm: dict) -> np.ndarray:
    return spla.spsolve(sysm["A"].tocsc(), sysm["b"])


def prolongation(coarse: dict, fine: dict) -> sp.csr_matrix:
    """The P1 prolongation of anchor_fem.refine_red: identity on coarse nodes, the mean of
    an edge's endpoints on its midpoint, numbered exactly as refine_red numbers them."""
    t, s = coarse["tets"], coarse["tris"]
    tp = np.vstack([np.stack([t[:, a], t[:, b]], 1) for a, b in af.TET_EDGES])
    fp = np.vstack([np.stack([s[:, a], s[:, b]], 1) for a, b in af.TRI_EDGES])
    uniq = np.unique(np.sort(np.vstack([tp, fp]), axis=1), axis=0)
    n0, n1 = len(coarse["xyz"]), len(fine["xyz"])
    if n1 != n0 + len(uniq):
        raise Refusal("the fine mesh is not the red refinement of the coarse mesh")
    mid = np.arange(n0, n1)
    rows = np.concatenate([np.arange(n0), mid, mid])
    cols = np.concatenate([np.arange(n0), uniq[:, 0], uniq[:, 1]])
    vals = np.concatenate([np.ones(n0), np.full(len(mid), 0.5), np.full(len(mid), 0.5)])
    return sp.csr_matrix((vals, (rows, cols)), shape=(n1, n0))


class TwoGrid:
    """One symmetric two-grid cycle as a preconditioner (see the module docstring)."""

    def __init__(self, A: sp.csr_matrix, P: sp.csr_matrix, nu: int):
        if nu < 1:
            raise ValueError("nu must be at least 1")
        self.A, self.P, self.nu = A, P, nu
        if not (A.diagonal() > 0).all():
            raise Refusal("A has a non-positive diagonal entry")
        Lower = sp.tril(A, format="csc")
        # SuperLU on a triangular matrix in natural order is a compiled triangular solve
        self.gs = spla.splu(Lower, permc_spec="NATURAL", diag_pivot_thresh=0.0,
                            options={"SymmetricMode": True})
        # diagnostics only: the certificate does not depend on the preconditioner
        probe = np.random.default_rng(0).standard_normal(A.shape[0])
        scale = np.abs(probe).max()
        self.gs_probe_rel = float(np.abs(self.gs.solve(Lower @ probe) - probe).max() / scale)
        self.gs_probe_backward_rel = float(
            np.abs(self.gs.solve(Lower.T @ probe, trans="T") - probe).max() / scale)
        self.Ac = (P.T @ A @ P).tocsc()
        self.lu = spla.splu(self.Ac)

    def __call__(self, r: np.ndarray) -> np.ndarray:
        A = self.A
        x = self.gs.solve(r)
        for _ in range(self.nu - 1):
            x += self.gs.solve(r - A @ x)
        x += self.P @ self.lu.solve(self.P.T @ (r - A @ x))
        for _ in range(self.nu):
            x += self.gs.solve(r - A @ x, trans="T")
        return x


def certificate(sysm: dict, x: np.ndarray, m_free: np.ndarray, c: float) -> dict:
    """Rigorous bound on E(phi~) - E_h >= 0 from the true residual (module docstring)."""
    A, b, KfD, phiD = sysm["A"], sysm["b"], sysm["KfD"], sysm["phiD"]
    r = b - A @ x
    kA = int(np.diff(A.indptr).max())
    kD = max(1, int(np.diff(KfD.indptr).max()) if KfD.nnz else 1)
    g = (gamma(kA + 1) * (np.abs(b) + abs(A) @ np.abs(x))
         + gamma(kD) * (abs(KfD) @ np.abs(phiD)))
    asym = 0.5 * (sysm["A_asym_abs"] @ np.abs(x) + sysm["D_asym_abs"] @ np.abs(phiD))
    rb = np.abs(r) + g + asym
    return {"residual_2norm": float(np.linalg.norm(r)), "rhs_2norm": float(np.linalg.norm(b)),
            "relative_residual": float(np.linalg.norm(r) / np.linalg.norm(b)),
            "asymmetry_max": float(asym.max()) if len(asym) else 0.0,
            "error_bound_nd": BOUND_SAFETY * float((rb * rb / m_free).sum()) / c,
            "roundoff_floor_nd": BOUND_SAFETY * float(((g + asym) ** 2 / m_free).sum()) / c}


def energy(K, phi: np.ndarray) -> dict:
    """phi^T K phi in float64 exactly as static_capacitance computes it, and a rigorous
    bound on its evaluation error from an extended-precision re-evaluation (module
    docstring): gamma_k |phi|^T|K||phi| for the matrix-vector product, gamma_n sum|phi_i y_i|
    for the dot product, plus the float64-to-extended difference and its rounding."""
    e64 = float(phi @ (K @ phi))
    Kc = K.tocsr()
    pl = phi.astype(np.longdouble)
    y = Kc.astype(np.longdouble) @ pl
    s_ld = pl @ y
    k = int(np.diff(Kc.indptr).max())
    t_matvec = gamma(k, ULD) * float(np.abs(phi) @ (abs(Kc) @ np.abs(phi)))
    t_dot = gamma(len(phi), ULD) * float(np.abs(pl * y).sum())
    s64 = float(s_ld)
    t_diff = abs(e64 - s64) + U64 * abs(s64)
    return {"energy_nd": e64, "energy_nd_extended": s64,
            "evaluation_error_bound_nd": BOUND_SAFETY * (t_matvec + t_dot + t_diff),
            "evaluation_bound_terms_nd": {"matvec": t_matvec, "dot": t_dot,
                                          "float64_vs_extended": t_diff}}


def pcg(A, b, x0, precond, *, maxiter: int, check_every: int, target_rel: float,
        stagnation_checks: int, certify) -> tuple[np.ndarray, dict]:
    """Preconditioned conjugate gradients. Every ``check_every`` iterations ``certify(x)``
    returns (relative certificate, TRUE residual norm). It stops when the relative
    certificate reaches ``target_rel`` (CERTIFIED), after ``stagnation_checks`` FINITE
    checks without a 10 % improvement on the best finite one (STAGNATED; an infinite
    certificate - the bound still above the energy - never counts toward stagnation), on
    breakdown, or at ``maxiter``. The status is a recorded diagnostic, not a verdict."""
    w0 = time.monotonic()
    x = x0.copy()
    r = b - A @ x
    z = precond(r)
    p = z.copy()
    rz = float(r @ z)
    hist, best, since, status, k = [], math.inf, 0, "MAXITER", 0

    def record(k_, rel_, true_):
        hist.append({"k": k_, "recursive_residual": float(np.linalg.norm(r)),
                     "true_residual": true_, "rel_certificate": rel_ if math.isfinite(rel_) else None,
                     "wall_s": time.monotonic() - w0})

    rel0, true0 = certify(x)
    record(0, rel0, true0)
    if rel0 <= target_rel:
        return x, {"status": "CERTIFIED", "iterations": 0, "history": hist}
    for k in range(1, maxiter + 1):
        Ap = A @ p
        pAp = float(p @ Ap)
        if not (math.isfinite(pAp) and pAp > 0):
            status = "BREAKDOWN"
            break
        alpha = rz / pAp
        x += alpha * p
        r -= alpha * Ap
        if k % check_every == 0:
            rel, true = certify(x)
            record(k, rel, true)
            if rel <= target_rel:
                status = "CERTIFIED"
                break
            if math.isfinite(rel):
                if rel < 0.9 * best:
                    best, since = rel, 0
                else:
                    since += 1
                    if since >= stagnation_checks:
                        status = "STAGNATED"
                        break
        z = precond(r)
        rz_new = float(r @ z)
        if not (math.isfinite(rz_new) and rz_new > 0):
            status = "BREAKDOWN"
            break
        p = z + (rz_new / rz) * p
        rz = rz_new
    return x, {"status": status, "iterations": k, "history": hist}


#: The frozen solver settings. predeclaration.json repeats them and a test binds the two.
SOLVER = {"nu": 1, "maxiter": 1000, "check_every": 5, "target_rel": 1e-12,
          "stagnation_checks": 20}


class Level:
    """Everything one level needs, assembled once: K, the nodal masses, the constant c and
    the Dirichlet data of each problem (``kinds``; a synthetic caller may add its own)."""

    def __init__(self, mesh: dict, model: dict, kinds=KINDS):
        sc = af.scales(mesh, model["L0_m"], model["L_H"])
        self.mesh, self.model, self.sc = mesh, model, sc
        self.xyz = sc["xyz_nd"]
        self.K = af.p1_stiffness(mesh, self.xyz, model["eps_r"])
        self.m = nodal_mass_lower(mesh, self.xyz)
        self.poincare = poincare_constant(mesh, self.xyz, model["eps_r"])
        self.dd = {k: dirichlet(mesh, self.xyz, model, k) for k in kinds}


def certificate_preconditions(level: Level, bfacts: dict) -> list[str]:
    """Why the certificate would not be rigorous on this level. Empty means it is."""
    bad = []
    if bfacts["max_face_multiplicity"] > 2:
        bad.append("non-conforming: a face is shared by more than two tetrahedra")
    if not bfacts["every_boundary_face_is_tagged"]:
        bad.append("an untagged boundary face (a hanging node or a hole)")
    if "volume_sum_over_box_minus_1" not in bfacts:
        bad.append("the tiling of the bounding box was not checked (no coordinates)")
    else:
        if not bfacts["every_interior_face_separates_its_tetrahedra"]:
            bad.append("an interior face does not separate its two tetrahedra (folded mesh)")
        if not bfacts["every_boundary_face_on_the_box_surface"]:
            bad.append("a boundary face lies off the bounding-box surface")
        if not abs(bfacts["volume_sum_over_box_minus_1"]) <= TILING_VOLUME_TOL:
            bad.append(f"the volumes do not tile the bounding box: "
                       f"{bfacts['volume_sum_over_box_minus_1']!r}")
    for kind, dd in level.dd.items():
        if not dd["fixed"][bfacts["boundary_nodes"]].all():
            bad.append(f"{kind}: an outer-boundary node is not constrained")
        if dd.get("geo") is not None:
            bad += [f"{kind}: {p}" for p in port_geometry_problems(dd["geo"])]
    return bad


def solve(level: Level, kind: str, method: str, *, coarse: Level | None = None,
          coarse_phi: np.ndarray | None = None, settings: dict | None = None) -> tuple[dict, np.ndarray]:
    """Solve one problem on one level. Returns the raw result and the full potential."""
    t0 = time.process_time()
    w0 = time.monotonic()
    dd = level.dd[kind]
    sysm = system(level.K, dd)
    phi = dd["phi"].copy()
    m_free = level.m[dd["free"]]
    c = level.poincare["c"]
    info: dict = {"method": method}
    if method == "direct":
        x = solve_direct(sysm)
    elif method == "twogrid":
        s = dict(SOLVER, **(settings or {}))
        cd = coarse.dd[kind]
        Pfull = prolongation(coarse.mesh, level.mesh)
        # the homogeneous coarse space must prolong into the homogeneous fine space
        leak = Pfull[np.flatnonzero(dd["fixed"])][:, cd["free"]]
        info["fixed_rows_from_free_coarse_nnz"] = int(leak.nnz)
        P = Pfull[dd["free"]][:, cd["free"]].tocsr()
        ws = time.monotonic()
        tg = TwoGrid(sysm["A"], P, s["nu"])
        info["setup_wall_s"] = time.monotonic() - ws
        Acoarse = coarse.K[cd["free"]][:, cd["free"]]
        info["galerkin_identity_rel"] = float(abs(tg.Ac - Acoarse).max() / abs(Acoarse).max())
        info["gauss_seidel_probe_rel"] = tg.gs_probe_rel
        info["gauss_seidel_probe_backward_rel"] = tg.gs_probe_backward_rel
        x0 = (Pfull @ coarse_phi)[dd["free"]]
        phi_work = phi.copy()

        def certify(xk):
            phi_work[dd["free"]] = xk
            e = float(phi_work @ (level.K @ phi_work))
            ce = certificate(sysm, xk, m_free, c)
            bnd = ce["error_bound_nd"]
            return (bnd / (e - bnd) if e > bnd else math.inf), ce["residual_2norm"]

        x, it = pcg(sysm["A"], sysm["b"], x0, tg, maxiter=s["maxiter"],
                    check_every=s["check_every"], target_rel=s["target_rel"],
                    stagnation_checks=s["stagnation_checks"], certify=certify)
        info.update({"settings": s, "status": it["status"], "iterations": it["iterations"],
                     "history": it["history"]})
    else:
        raise ValueError(method)
    phi[dd["free"]] = x
    en = energy(level.K, phi)
    cert = certificate(sysm, x, m_free, c)
    E = en["energy_nd"]
    total = cert["error_bound_nd"] + en["evaluation_error_bound_nd"]
    C = af.EPSILON0 * level.sc["Lc_m"] * E
    out = {"kind": kind, "n_unknowns": int(len(dd["free"])), **en, "certificate": cert,
           "total_error_bound_nd": total,
           "total_error_bound_rel": total / (E - total) if E > total else math.inf,
           "C_F": C, "C_fF": C * 1e15,
           "S_GHz2": 1.0 / ((2.0 * math.pi) ** 2 * level.model["L_H"] * C) * 1e-18,
           "port_voltage": (port_voltage(level.mesh, level.xyz, dd["geo"], level.model, phi)
                            if dd.get("geo") is not None else None),
           "solution_sha256": hashlib.sha256(np.ascontiguousarray(phi, "<f8").tobytes()).hexdigest(),
           "solver": info, "cpu_s": time.process_time() - t0, "wall_s": time.monotonic() - w0}
    return out, phi
