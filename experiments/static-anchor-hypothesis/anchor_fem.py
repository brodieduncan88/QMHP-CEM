# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Shared finite-element primitives for the static-anchor hypothesis record.

Everything here is independent of Palace and MFEM. It reads a Gmsh 2.2 mesh, refines it
uniformly (red, 1 -> 8, nested), and assembles on it, from the element formulas written
out below:

* the epsilon-weighted lowest-order Nedelec (Whitney) mass matrix ``M`` on edges;
* the lumped-port voltage functional ``f`` on edges (the width-averaged tangential field
  over the port face, coefficient ``1/w``), exactly as
  ``synthetic_fixture.independent_first_moment`` builds it;
* the epsilon-weighted P1 stiffness matrix ``K`` on nodes;
* the discrete gradient ``G`` (edges x nodes), which maps a P1 potential onto the edge
  space exactly: for P1 ``phi``, ``sum_e (G phi)_e w_e = grad phi`` (the de Rham property of
  Whitney forms), so ``(G phi)^T M (G phi) = phi^T K phi`` and ``f^T G phi`` is the port
  voltage of the field ``grad phi``.

Conventions match ``synthetic_fixture`` and the first-moment diagnostic: coordinates are
nondimensionalised by ``Lc``, the largest bounding-box extent in metres; each global edge is
oriented from its lower to its higher node index; the Whitney function of edge (i, j) is
``lam_i grad(lam_j) - lam_j grad(lam_i)``, whose tangential integral along the edge is 1.

This module performs no linear solve. It launches nothing and writes nothing.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

MU0 = 4.0e-7 * math.pi
C0 = 299792458.0
#: derived, not typed: with the truncated 8.8541878176e-12 the two routes to the static
#: first moment (farads via eps0, and the nondimensional route via mu0 and c0) differ by
#: 2.3e-12 purely from the constant, which would mask a real identity failure at that level
EPSILON0 = 1.0 / (MU0 * C0 * C0)

TET_EDGES = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
TRI_EDGES = ((0, 1), (0, 2), (1, 2))
_EA = np.array([a for a, _ in TET_EDGES])
_EB = np.array([b for _, b in TET_EDGES])


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- mesh ---------------------------------------------------------------------------

def read_gmsh22(path) -> dict:
    """Nodes, tetrahedra and triangles of an ASCII Gmsh 2.2 mesh, 0-based, with the
    physical tag of each element."""
    lines = Path(path).read_text().split("\n")
    i, ids, xyz, tets, tet_a, tris, tri_a = 0, [], [], [], [], [], []
    while i < len(lines):
        if lines[i] == "$Nodes":
            n = int(lines[i + 1])
            for j in range(n):
                p = lines[i + 2 + j].split()
                ids.append(int(p[0]))
                xyz.append((float(p[1]), float(p[2]), float(p[3])))
            i += 2 + n
        elif lines[i] == "$Elements":
            n = int(lines[i + 1])
            for j in range(n):
                p = [int(v) for v in lines[i + 2 + j].split()]
                etype, ntags, phys, conn = p[1], p[2], p[3], p[3 + p[2]:]
                if etype == 4:
                    tets.append(conn[:4]); tet_a.append(phys)
                elif etype == 2:
                    tris.append(conn[:3]); tri_a.append(phys)
            i += 2 + n
        else:
            i += 1
    ids = np.array(ids)
    remap = np.full(ids.max() + 1, -1, dtype=np.int64)
    remap[ids] = np.arange(len(ids))
    return {"xyz": np.array(xyz), "tets": remap[np.array(tets)],
            "tet_attr": np.array(tet_a), "tris": remap[np.array(tris)],
            "tri_attr": np.array(tri_a)}


def refine_red(mesh: dict) -> dict:
    """Uniform red refinement: every tetrahedron into 8 (4 corners + the inner octahedron
    split along its shortest diagonal), every triangle into 4. Existing nodes keep their
    indices, so the P1 spaces are nested."""
    xyz, tets, tris = mesh["xyz"], mesh["tets"], mesh["tris"]
    n0 = len(xyz)
    tp = np.vstack([np.stack([tets[:, a], tets[:, b]], 1) for a, b in TET_EDGES])
    fp = np.vstack([np.stack([tris[:, a], tris[:, b]], 1) for a, b in TRI_EDGES])
    allp = np.sort(np.vstack([tp, fp]), axis=1)
    uniq, inv = np.unique(allp, axis=0, return_inverse=True)
    inv = inv.ravel()
    xyz2 = np.vstack([xyz, 0.5 * (xyz[uniq[:, 0]] + xyz[uniq[:, 1]])])
    m = inv[:len(tp)].reshape(6, len(tets)).T + n0
    mt = inv[len(tp):].reshape(3, len(tris)).T + n0
    t = tets
    corners = [np.stack([t[:, 0], m[:, 0], m[:, 1], m[:, 2]], 1),
               np.stack([t[:, 1], m[:, 0], m[:, 3], m[:, 4]], 1),
               np.stack([t[:, 2], m[:, 1], m[:, 3], m[:, 5]], 1),
               np.stack([t[:, 3], m[:, 2], m[:, 4], m[:, 5]], 1)]
    diags = [(0, 5, (1, 2, 4, 3)), (1, 4, (0, 2, 5, 3)), (2, 3, (0, 1, 5, 4))]
    lens = np.stack([np.linalg.norm(xyz2[m[:, a]] - xyz2[m[:, b]], axis=1)
                     for a, b, _ in diags], 1)
    pick = np.argmin(lens, axis=1)
    octs = [np.empty_like(corners[0]) for _ in range(4)]
    for k, (a, b, ring) in enumerate(diags):
        sel = pick == k
        ms = m[sel]
        for q in range(4):
            octs[q][sel] = np.stack([ms[:, a], ms[:, b], ms[:, ring[q]],
                                     ms[:, ring[(q + 1) % 4]]], 1)
    s = tris
    tris2 = np.concatenate([np.stack([s[:, 0], mt[:, 0], mt[:, 1]], 1),
                            np.stack([s[:, 1], mt[:, 0], mt[:, 2]], 1),
                            np.stack([s[:, 2], mt[:, 1], mt[:, 2]], 1),
                            np.stack([mt[:, 0], mt[:, 2], mt[:, 1]], 1)], 0)
    return {"xyz": xyz2, "tets": np.concatenate(corners + octs, 0),
            "tet_attr": np.tile(mesh["tet_attr"], 8), "tris": tris2,
            "tri_attr": np.tile(mesh["tri_attr"], 4)}


def box_mesh(nx: int, ny: int, nz: int, size=(1.0, 1.0, 1.0)) -> dict:
    """A structured Kuhn (6 tetrahedra per cube) mesh of a box, conforming, plus every
    boundary triangle. Tetrahedra carry attribute 1; triangles attribute 0 until the caller
    tags them. Synthetic controls only."""
    xs, ys, zs = (np.linspace(0, size[k], n + 1) for k, n in enumerate((nx, ny, nz)))
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    xyz = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    idx = lambda i, j, k: (i * (ny + 1) + j) * (nz + 1) + k
    tets = []
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                v = [idx(i + a, j + b, k + c) for a in (0, 1) for b in (0, 1) for c in (0, 1)]
                c000, c001, c010, c011, c100, c101, c110, c111 = v
                for path in ((c100, c110), (c100, c101), (c010, c110),
                             (c010, c011), (c001, c101), (c001, c011)):
                    tets.append((c000, path[0], path[1], c111))
    tets = np.array(tets)
    faces = np.sort(np.vstack([tets[:, [0, 1, 2]], tets[:, [0, 1, 3]],
                               tets[:, [0, 2, 3]], tets[:, [1, 2, 3]]]), axis=1)
    uf, cnt = np.unique(faces, axis=0, return_counts=True)
    tris = uf[cnt == 1]
    return {"xyz": xyz, "tets": tets, "tet_attr": np.ones(len(tets), dtype=int),
            "tris": tris, "tri_attr": np.zeros(len(tris), dtype=int)}


def conductor_components(mesh: dict, pec_attrs) -> list[np.ndarray]:
    """Connected components of the PEC surface, as node-index arrays, largest first."""
    sel = np.isin(mesh["tri_attr"], list(pec_attrs))
    tri = mesh["tris"][sel]
    n = len(mesh["xyz"])
    rows = np.concatenate([tri[:, 0], tri[:, 1], tri[:, 2]])
    cols = np.concatenate([tri[:, 1], tri[:, 2], tri[:, 0]])
    A = sp.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))
    _, lab = connected_components(A, directed=False)
    nodes = np.unique(tri)
    comps = [nodes[lab[nodes] == c] for c in np.unique(lab[nodes])]
    return sorted(comps, key=len, reverse=True)


# --- scales and edges -----------------------------------------------------------------

def scales(mesh: dict, L0_m: float, L_H: float) -> dict:
    """The nondimensionalisation Palace uses when the config carries no Model.Lc."""
    Lc = float(((mesh["xyz"].max(0) - mesh["xyz"].min(0)) * L0_m).max())
    tc = Lc / C0
    fs_ghz = 1.0 / (2.0 * math.pi * tc) / 1e9
    return {"Lc_m": Lc, "tc_s": tc, "L_nd": L_H / (MU0 * Lc),
            "A_GHz2_per_nd": fs_ghz ** 2, "xyz_nd": mesh["xyz"] * L0_m / Lc}


def edge_table(mesh: dict) -> tuple[np.ndarray, np.ndarray]:
    """Unique global edges (lo, hi) and the (ntet, 6) map from local to global edge."""
    t = mesh["tets"]
    pairs = np.stack([np.stack([t[:, a], t[:, b]], 1) for a, b in TET_EDGES], 1)
    lo, hi = pairs.min(2), pairs.max(2)
    n = len(mesh["xyz"])
    key = lo.astype(np.int64) * n + hi
    uk, inv = np.unique(key.ravel(), return_inverse=True)
    edges = np.stack([uk // n, uk % n], 1)
    return edges, inv.reshape(key.shape)


def _edge_ids(edges: np.ndarray, n: int, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    key = edges[:, 0] * n + edges[:, 1]
    q = np.minimum(a, b).astype(np.int64) * n + np.maximum(a, b)
    pos = np.searchsorted(key, q)
    if not np.array_equal(key[pos], q):
        raise ValueError("a face edge is not an edge of any tetrahedron")
    return pos


def _tet_geometry(xyz_nd: np.ndarray, tets: np.ndarray):
    p = xyz_nd[tets]
    J = np.stack([p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]], 2)
    vol = np.abs(np.linalg.det(J)) / 6.0
    Jinv = np.linalg.inv(J)                      # rows of J^-1 are grad(lambda_1..3)
    g = np.empty((len(tets), 4, 3))
    g[:, 1:] = Jinv
    g[:, 0] = -Jinv.sum(1)
    return g, vol


def _eps(mesh: dict, eps_r: dict) -> np.ndarray:
    return np.array([eps_r[int(a)] for a in mesh["tet_attr"]])


# --- operators --------------------------------------------------------------------------

def whitney_mass(mesh: dict, xyz_nd, edges, t2e, eps_r: dict) -> sp.csr_matrix:
    """sum_K eps_r(K) int_K w_e . w_f, closed form: int lam_i lam_j = vol (1 + d_ij) / 20."""
    g, vol = _tet_geometry(xyz_nd, mesh["tets"])
    GG = np.einsum("tik,tjk->tij", g, g)
    Ae, Be, Af, Bf = _EA[:, None], _EB[:, None], _EA[None, :], _EB[None, :]
    loc = ((1 + (Ae == Af)) * GG[:, Be, Bf] - (1 + (Ae == Bf)) * GG[:, Be, Af]
           - (1 + (Be == Af)) * GG[:, Ae, Bf] + (1 + (Be == Bf)) * GG[:, Ae, Af])
    loc *= (_eps(mesh, eps_r) * vol / 20.0)[:, None, None]
    t = mesh["tets"]
    sgn = np.where(t[:, _EA] < t[:, _EB], 1.0, -1.0)
    loc *= sgn[:, :, None] * sgn[:, None, :]
    rows = np.repeat(t2e, 6, axis=1).ravel()
    cols = np.tile(t2e, (1, 6)).ravel()
    ne = len(edges)
    return sp.coo_matrix((loc.ravel(), (rows, cols)), shape=(ne, ne)).tocsr()


def port_functional(mesh: dict, xyz_nd, edges, port_attr: int, direction) -> tuple:
    """f_e = int_port (d_hat / w) . w_e dS; w and l as Palace's UniformElementData takes
    them (l the extent along the direction, w the largest remaining extent)."""
    tris = mesh["tris"][mesh["tri_attr"] == port_attr]
    if len(tris) == 0:
        raise ValueError(f"no triangles carry port attribute {port_attr}")
    d = np.asarray(direction, float)
    d_hat = d / np.linalg.norm(d)
    pts = xyz_nd[np.unique(tris)]
    ext = pts.max(0) - pts.min(0)
    ax = int(np.argmax(np.abs(d)))
    l_geom = float(ext[ax])
    rest = ext.copy(); rest[ax] = 0.0
    w_geom = float(rest.max())
    p = xyz_nd[tris]
    e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
    nrm = np.cross(e1, e2)
    area = 0.5 * np.linalg.norm(nrm, axis=1)
    J = np.stack([e1, e2, nrm / np.linalg.norm(nrm, axis=1)[:, None]], 2)
    Ginv = np.linalg.inv(J)
    g2 = np.empty((len(tris), 3, 3))
    g2[:, 1], g2[:, 2] = Ginv[:, 0], Ginv[:, 1]
    g2[:, 0] = -(g2[:, 1] + g2[:, 2])
    n = len(mesh["xyz"])
    f = np.zeros(len(edges))
    for a, b in TRI_EDGES:
        val = (area / 3.0) * ((g2[:, b] - g2[:, a]) @ d_hat) / w_geom
        sgn = np.where(tris[:, a] < tris[:, b], 1.0, -1.0)
        np.add.at(f, _edge_ids(edges, n, tris[:, a], tris[:, b]), sgn * val)
    return f, {"w_nd": w_geom, "l_nd": l_geom, "n_port_tris": int(len(tris)),
               "port_nodes": np.unique(tris)}


def pec_edge_mask(mesh: dict, edges, pec_attrs) -> np.ndarray:
    tris = mesh["tris"][np.isin(mesh["tri_attr"], list(pec_attrs))]
    n = len(mesh["xyz"])
    mask = np.zeros(len(edges), dtype=bool)
    for a, b in TRI_EDGES:
        mask[_edge_ids(edges, n, tris[:, a], tris[:, b])] = True
    return mask


def p1_stiffness(mesh: dict, xyz_nd, eps_r: dict) -> sp.csr_matrix:
    """sum_K eps_r(K) int_K grad phi_i . grad phi_j on the nondimensional mesh."""
    g, vol = _tet_geometry(xyz_nd, mesh["tets"])
    loc = np.einsum("tik,tjk->tij", g, g) * (_eps(mesh, eps_r) * vol)[:, None, None]
    t = mesh["tets"]
    n = len(mesh["xyz"])
    rows = np.repeat(t, 4, axis=1).ravel()
    cols = np.tile(t, (1, 4)).ravel()
    return sp.coo_matrix((loc.ravel(), (rows, cols)), shape=(n, n)).tocsr()


def gradient_matrix(edges: np.ndarray, n_nodes: int) -> sp.csr_matrix:
    """(G phi)_e = phi(hi) - phi(lo): the edge degrees of freedom of grad phi."""
    ne = len(edges)
    rows = np.concatenate([np.arange(ne), np.arange(ne)])
    cols = np.concatenate([edges[:, 1], edges[:, 0]])
    vals = np.concatenate([np.ones(ne), -np.ones(ne)])
    return sp.coo_matrix((vals, (rows, cols)), shape=(ne, n_nodes)).tocsr()


def assemble_edge_system(mesh: dict, *, eps_r: dict, pec_attrs, port_attr: int,
                         direction, L0_m: float, L_H: float) -> dict:
    """M and f on the free (non-PEC) edges, with everything needed to relate them."""
    sc = scales(mesh, L0_m, L_H)
    edges, t2e = edge_table(mesh)
    M = whitney_mass(mesh, sc["xyz_nd"], edges, t2e, eps_r)
    f, port = port_functional(mesh, sc["xyz_nd"], edges, port_attr, direction)
    pec = pec_edge_mask(mesh, edges, pec_attrs)
    free = np.flatnonzero(~pec)
    return {"scales": sc, "edges": edges, "pec": pec, "free": free,
            "M_free": M[free][:, free].tocsr(), "M_all": M, "f_all": f,
            "f_free": f[free], "port": port}
