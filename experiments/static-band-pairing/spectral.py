# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Operators and spectral moments for the static-vs-band analysis.

Adds to ``anchor_fem`` (unchanged) exactly what the spectral identities need:

* the Whitney curl-curl matrix ``K_curl = int mu_r^-1 curl w_e . curl w_f``,
  with curl(lam_a grad lam_b - lam_b grad lam_a) = 2 grad lam_a x grad lam_b and the
  same lo -> hi orientation as ``anchor_fem.whitney_mass``;
* the two port models: the declared LUMPED inductor, rank one, ``f f^T / L``; and the
  DISTRIBUTED sheet Palace assembles, ``int_port (1/L_s) E_t . E_t dS`` with
  ``L_s = L (w/l) n_elem`` (pinned Palace a61c8cbe, lumpedportoperator.cpp
  AddStiffnessBdrCoefficients; one element here, n_elem = 1);
* all eigenpairs of a small pencil (dense; synthetic sizes only) and its moments
  N = sum p, sum p/lambda, sum p lambda, with Palace's rank-one participation
  p_m = (f . E_m)^2 / (L lambda_m E_m^T M E_m).

Nothing here reads or solves anything on the QMHP mesh.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "static-anchor-hypothesis"))
import anchor_fem as af  # noqa: E402


def curl_curl(mesh: dict, xyz_nd, edges, t2e, mu_r: float = 1.0) -> sp.csr_matrix:
    g, vol = af._tet_geometry(xyz_nd, mesh["tets"])
    c = 2.0 * np.cross(g[:, af._EA], g[:, af._EB])            # (ntet, 6, 3) local curls
    t = mesh["tets"]
    sgn = np.where(t[:, af._EA] < t[:, af._EB], 1.0, -1.0)
    c = c * sgn[:, :, None]
    loc = np.einsum("tik,tjk->tij", c, c) * (vol / mu_r)[:, None, None]
    rows = np.repeat(t2e, 6, axis=1).ravel()
    cols = np.tile(t2e, (1, 6)).ravel()
    ne = len(edges)
    return sp.coo_matrix((loc.ravel(), (rows, cols)), shape=(ne, ne)).tocsr()


def sheet_port(mesh: dict, xyz_nd, edges, port_attr: int, L_nd: float, w_nd: float,
               l_nd: float, n_elem: int = 1) -> sp.csr_matrix:
    """(1/L_s) int_port w_e,t . w_f,t dS on the face's 2-D Whitney functions (the
    tangential trace of every edge off the face vanishes on it)."""
    tris = mesh["tris"][mesh["tri_attr"] == port_attr]
    p = xyz_nd[tris]
    e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
    nrm = np.cross(e1, e2)
    area = 0.5 * np.linalg.norm(nrm, axis=1)
    J = np.stack([e1, e2, nrm / np.linalg.norm(nrm, axis=1)[:, None]], 2)
    Ginv = np.linalg.inv(J)
    g2 = np.empty((len(tris), 3, 3))
    g2[:, 1], g2[:, 2] = Ginv[:, 0], Ginv[:, 1]
    g2[:, 0] = -(g2[:, 1] + g2[:, 2])
    GG = np.einsum("tik,tjk->tij", g2, g2)
    ea = np.array([a for a, _ in af.TRI_EDGES]); eb = np.array([b for _, b in af.TRI_EDGES])
    Ae, Be, Af, Bf = ea[:, None], eb[:, None], ea[None, :], eb[None, :]
    # int_T lam_i lam_j = area (1 + d_ij) / 12
    loc = ((1 + (Ae == Af)) * GG[:, Be, Bf] - (1 + (Ae == Bf)) * GG[:, Be, Af]
           - (1 + (Be == Af)) * GG[:, Ae, Bf] + (1 + (Be == Bf)) * GG[:, Ae, Af])
    loc = loc * (area / 12.0)[:, None, None]
    sgn = np.where(tris[:, ea] < tris[:, eb], 1.0, -1.0)
    loc = loc * sgn[:, :, None] * sgn[:, None, :]
    n = len(mesh["xyz"])
    ids = np.stack([af._edge_ids(edges, n, tris[:, a], tris[:, b]) for a, b in af.TRI_EDGES], 1)
    rows = np.repeat(ids, 3, axis=1).ravel()
    cols = np.tile(ids, (1, 3)).ravel()
    Ls = L_nd * (w_nd / l_nd) * n_elem
    ne = len(edges)
    return sp.coo_matrix((loc.ravel() / Ls, (rows, cols)), shape=(ne, ne)).tocsr()


def all_modes(K, M, free):
    """Every eigenpair of the pencil restricted to the free (non-PEC) edges, dense."""
    Kf = K[free][:, free].toarray() if sp.issparse(K) else K[np.ix_(free, free)]
    Mf = M[free][:, free].toarray()
    Linv = np.linalg.inv(np.linalg.cholesky(Mf))
    A = Linv @ Kf @ Linv.T
    lam, U = np.linalg.eigh(0.5 * (A + A.T))
    return lam, Linv.T @ U                                    # M-orthonormal columns


def moments(lam, E, f_free, L_nd, zero_rel: float = 1e-10) -> dict:
    """Palace's rank-one participation and the moments over the nonzero modes, lowest first."""
    keep = lam > zero_rel * lam.max()
    lam, V = lam[keep], (f_free @ E)[keep]
    p = V ** 2 / (L_nd * lam)
    return {"lam": lam, "p": p, "N": float(p.sum()), "inv_moment": float((p / lam).sum()),
            "first_moment": float((p * lam).sum()), "null_dim": int((~keep).sum())}


def port_constrained_energy(mesh: dict, model: dict) -> float:
    """The Dirichlet energy with the port-face potential ALSO held linear along the port
    direction (0 at the ground end, 1 at the island end). For Palace's distributed sheet
    port this is exact: N = 1 and sum over all modes of p/lambda = L C'_h, so
    delta = C'_h / C_h - 1 >= 0 needs no eigen-solve. Derivation: with psi linear on the
    rectangular port face, K_sheet grad(psi) = f / L (L_s = L w/l), K_curl grad(psi) = 0,
    and the M-orthogonality to the kernel makes psi the constrained Dirichlet minimiser.
    Requires a rectangular port face whose conductor nodes lie only on its two end lines."""
    ground, island = af.conductor_components(mesh, model["pec_attrs"])
    xyz = af.scales(mesh, model["L0_m"], model["L_H"])["xyz_nd"]
    port = np.unique(mesh["tris"][mesh["tri_attr"] == model["port_attr"]])
    d = np.asarray(model["direction"], float)
    d = d / np.linalg.norm(d)
    t = xyz @ d
    tg, ti = t[np.intersect1d(port, ground)].mean(), t[np.intersect1d(port, island)].mean()
    n = len(xyz)
    phi, fixed = np.zeros(n), np.zeros(n, dtype=bool)
    fixed[ground] = fixed[island] = True
    phi[island] = 1.0
    inner = port[~fixed[port]]
    phi[inner], fixed[inner] = (t[inner] - tg) / (ti - tg), True
    K = af.p1_stiffness(mesh, xyz, model["eps_r"])
    used = np.unique(mesh["tets"])
    free = used[~fixed[used]]
    phi[free] = spla.spsolve(K[free][:, free].tocsc(), -(K[free][:, fixed] @ phi[fixed]))
    return float(phi @ (K @ phi))
