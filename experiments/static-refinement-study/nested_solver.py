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

  With the Dirichlet values imposed exactly, E(phi~) - E_h = e^T A e = r^T A^-1 r >= 0 for
  the TRUE residual r = b - A x~: an inexact solve can only RAISE the energy. If every node
  of every outer-boundary face is constrained, a homogeneous discrete function extends by
  zero into H1_0 of the mesh's bounding box B, and

      x^T A x >= eps_min int |grad v|^2 >= eps_min lambda_1(B) int v^2
              >= eps_min lambda_1(B) sum_i m_i x_i^2,     m_i = sum_{K contains i} vol_K / 20

  (Dirichlet eigenvalue monotonicity under domain inclusion; the P1 element mass
  vol/20 (I + 1 1^T) dominates vol/20 I). So A >= c D_m with c = eps_min lambda_1(B), and

      0 <= E(phi~) - E_h <= sum_i r_i^2 / m_i / c.

  |r_i| is bounded by the computed residual plus the floating-point error of computing it
  and the right-hand side (gamma_n = n u / (1 - n u)). The certificate is relative to the
  assembled matrix: assembly round-off is not certified, and is common to every solver.
  The energy is also evaluated in extended precision; the float64-to-extended difference
  plus a worst-case bound on the extended evaluation is the evaluation-error bound.

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


def boundary_facts(mesh: dict) -> dict:
    """Faces shared by one tetrahedron: their nodes, the face multiplicity, and whether
    each is a tagged triangle (a hanging node would leave an untagged one)."""
    t, n = mesh["tets"], len(mesh["xyz"])
    if n ** 3 >= 2 ** 63:
        raise Refusal("too many nodes for the face key")
    faces = np.sort(np.vstack([t[:, [0, 1, 2]], t[:, [0, 1, 3]], t[:, [0, 2, 3]],
                               t[:, [1, 2, 3]]]), axis=1).astype(np.int64)
    key = (faces[:, 0] * n + faces[:, 1]) * n + faces[:, 2]
    del faces
    uk, cnt = np.unique(key, return_counts=True)
    del key
    single = uk[cnt == 1]
    tri = np.sort(mesh["tris"], axis=1).astype(np.int64)
    tkey = (tri[:, 0] * n + tri[:, 1]) * n + tri[:, 2]
    nodes = np.unique(np.concatenate([single // (n * n), (single // n) % n, single % n]))
    return {"max_face_multiplicity": int(cnt.max()), "boundary_faces": int(len(single)),
            "every_boundary_face_is_tagged": bool(np.isin(single, tkey).all()),
            "boundary_nodes": nodes}


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
#: the Gauss-Seidel triangular solve must reproduce a probe vector to this relative accuracy
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
    """A = K_ff and b = -K_fD phi_D, with exactly static_capacitance's expressions."""
    free, fixed, phi = dd["free"], dd["fixed"], dd["phi"]
    KfD = K[free][:, fixed]
    rhs = -(KfD @ phi[fixed])
    return {"A": K[free][:, free].tocsr(), "b": rhs, "KfD": KfD.tocsr(), "phiD": phi[fixed]}


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
        probe = np.random.default_rng(0).standard_normal(A.shape[0])
        self.gs_probe_rel = float(np.abs(self.gs.solve(Lower @ probe) - probe).max()
                                  / np.abs(probe).max())
        if not self.gs_probe_rel <= GS_PROBE_TOL:
            raise Refusal(f"the Gauss-Seidel triangular solve is inexact: {self.gs_probe_rel}")
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
    rb = np.abs(r) + g
    return {"residual_2norm": float(np.linalg.norm(r)), "rhs_2norm": float(np.linalg.norm(b)),
            "relative_residual": float(np.linalg.norm(r) / np.linalg.norm(b)),
            "error_bound_nd": BOUND_SAFETY * float((rb * rb / m_free).sum()) / c,
            "roundoff_floor_nd": BOUND_SAFETY * float((g * g / m_free).sum()) / c}


def energy(K, phi: np.ndarray) -> dict:
    """phi^T K phi in float64 exactly as static_capacitance computes it, and a bound on its
    evaluation error from an extended-precision re-evaluation."""
    e64 = float(phi @ (K @ phi))
    Kl = K.astype(np.longdouble)
    pl = phi.astype(np.longdouble)
    eld = pl @ (Kl @ pl)
    k = int(np.diff(K.tocsr().indptr).max())
    worst_ld = gamma(len(phi) + k, ULD) * float(np.abs(phi) @ (abs(K) @ np.abs(phi)))
    eld64 = float(eld)
    return {"energy_nd": e64, "energy_nd_extended": eld64,
            "evaluation_error_bound_nd": abs(e64 - eld64) + U64 * abs(eld64) + worst_ld}


def pcg(A, b, x0, precond, *, maxiter: int, check_every: int, target_rel: float,
        stagnation_checks: int, certify) -> tuple[np.ndarray, dict]:
    """Preconditioned conjugate gradients. Every ``check_every`` iterations the TRUE
    residual is certified; it stops when the relative certificate reaches ``target_rel``,
    after ``stagnation_checks`` checks without a 10 % improvement, on breakdown, or at
    ``maxiter``. The status is recorded; it is never a verdict by itself."""
    w0 = time.monotonic()
    x = x0.copy()
    r = b - A @ x
    z = precond(r)
    p = z.copy()
    rz = float(r @ z)
    hist, best, since, status, k = [], math.inf, 0, "MAXITER", 0
    cert0 = certify(x)
    hist.append([0, float(np.linalg.norm(r)), cert0, time.monotonic() - w0])
    if cert0 <= target_rel:
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
            rel = certify(x)
            hist.append([k, float(np.linalg.norm(r)), rel, time.monotonic() - w0])
            if rel <= target_rel:
                status = "CERTIFIED"
                break
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
        x0 = (Pfull @ coarse_phi)[dd["free"]]
        phi_work = phi.copy()

        def certify(xk):
            phi_work[dd["free"]] = xk
            e = float(phi_work @ (level.K @ phi_work))
            bnd = certificate(sysm, xk, m_free, c)["error_bound_nd"]
            return bnd / (e - bnd) if e > bnd else math.inf

        x, it = pcg(sysm["A"], sysm["b"], x0, tg, maxiter=s["maxiter"],
                    check_every=s["check_every"], target_rel=s["target_rel"],
                    stagnation_checks=s["stagnation_checks"], certify=certify)
        info.update({"settings": s, "status": it["status"], "iterations": it["iterations"],
                     "history_iter_residual_relcert_wall": it["history"]})
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
