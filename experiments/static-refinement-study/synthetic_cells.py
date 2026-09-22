# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Synthetic geometries for verifying the study's solvers. No QMHP data.

``chip_cell`` is a small analogue of the committed QMHP cell, built to meet the same
preconditions: a box whose six walls are grounded, one sheet plane z = 0 carrying a
ground sheet with a square cutout and a square island inside it, a rectangular port
strip in the gap bridging the island edge to the ground edge along +Y, substrate
(eps 11.45) below the plane and vacuum above, and a mesh graded toward the island with
anisotropic elements (Kuhn tetrahedra on a graded tensor grid). Lengths are in mm, as on
the QMHP mesh (L0 = 1e-3 m), and the default dimensions are the QMHP cell's: 4 x 4 mm,
z from -0.43 to 1.5 mm, a 0.15 mm island, 0.04 mm gaps, a 0.02 mm wide port.

``layered_box`` is the exact known answer: a two-layer box with EVERY boundary node held
at the exact piecewise-linear potential. The kink lies on a grid plane, so P1 reproduces
the exact solution and the discrete energy equals the continuum energy at every level.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "static-anchor-hypothesis"))
import anchor_fem as af  # noqa: E402

QMHP_LIKE_MODEL = {"eps_r": {1: 1.0, 3: 11.45}, "pec_attrs": (2, 4), "port_attr": 10,
                   "direction": (0.0, 1.0, 0.0), "L0_m": 1.0e-3,
                   "L_H": 1.0345665367517793e-07}


def tensor_mesh(xs, ys, zs) -> dict:
    """Kuhn tetrahedra (6 per cell, conforming) on a tensor grid with arbitrary spacing,
    and every face as a triangle list (boundary faces first flagged by ``boundary``)."""
    xs, ys, zs = (np.asarray(v, float) for v in (xs, ys, zs))
    nx, ny, nz = len(xs) - 1, len(ys) - 1, len(zs) - 1
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    xyz = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    I, J, Kk = np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing="ij")
    I, J, Kk = I.ravel(), J.ravel(), Kk.ravel()
    idx = lambda i, j, k: (i * (ny + 1) + j) * (nz + 1) + k
    c = {(a, b, d): idx(I + a, J + b, Kk + d) for a in (0, 1) for b in (0, 1) for d in (0, 1)}
    paths = (((1, 0, 0), (1, 1, 0)), ((1, 0, 0), (1, 0, 1)), ((0, 1, 0), (1, 1, 0)),
             ((0, 1, 0), (0, 1, 1)), ((0, 0, 1), (1, 0, 1)), ((0, 0, 1), (0, 1, 1)))
    tets = np.concatenate([np.stack([c[(0, 0, 0)], c[p], c[q], c[(1, 1, 1)]], 1)
                           for p, q in paths], 0)
    faces = np.sort(np.vstack([tets[:, [0, 1, 2]], tets[:, [0, 1, 3]], tets[:, [0, 2, 3]],
                               tets[:, [1, 2, 3]]]), axis=1)
    uf, cnt = np.unique(faces, axis=0, return_counts=True)
    return {"xyz": xyz, "tets": tets, "tet_attr": np.ones(len(tets), dtype=int),
            "faces": uf, "boundary": cnt == 1}


def _grow(u: float, v: float, h0: float, q: float, hmax: float) -> np.ndarray:
    """Nodes from u to v: first cell h0 at u, growing by q, capped at hmax."""
    pts, x, h = [u], u, h0
    sgn = 1.0 if v > u else -1.0
    while abs(v - x) > 1.5 * h:
        x += sgn * h
        pts.append(x)
        h = min(h * q, hmax)
    pts.append(v)
    return np.array(pts)


def _uniform(u: float, v: float, h0: float) -> np.ndarray:
    return np.linspace(u, v, max(1, int(np.ceil((v - u) / h0 - 1e-9))) + 1)


def _axis(breaks_inner, outer: float, h0: float, q: float, hmax: float) -> np.ndarray:
    inner = np.concatenate([_uniform(a, b, h0)[:-1] for a, b in zip(breaks_inner[:-1],
                                                                    breaks_inner[1:])]
                           + [[breaks_inner[-1]]])
    left = _grow(breaks_inner[0], -outer, h0, q, hmax)[::-1]
    right = _grow(breaks_inner[-1], outer, h0, q, hmax)
    return np.concatenate([left[:-1], inner, right[1:]])


def chip_cell(h0: float = 0.02, q: float = 1.5, hmax: float = 0.4, *, half: float = 2.0,
              z_lo: float = -0.43, z_hi: float = 1.5, island: float = 0.075,
              cutout: float = 0.115, port_half_width: float = 0.01,
              split_port: bool = False) -> tuple[dict, dict]:
    """The QMHP-like cell (module docstring). Attributes as on the QMHP mesh: walls 2,
    sheets 4, port 10, vacuum 1, substrate 3. ``split_port`` adds a grid line through the
    port's middle in each direction, so that even a coarse cell has a port-face node off
    both conductors (otherwise C' = C there)."""
    a, g, s = island, cutout, port_half_width
    xs = _axis([-g, -a, -s] + ([0.0] if split_port else []) + [s, a, g], half, h0, q, hmax)
    ys = _axis([-g] + ([-(a + g) / 2] if split_port else []) + [-a, a, g], half, h0, q, hmax)
    zs = np.concatenate([_grow(0.0, z_lo, h0, q, hmax)[::-1][:-1], _grow(0.0, z_hi, h0, q, hmax)])
    m = tensor_mesh(xs, ys, zs)
    xyz, faces = m["xyz"], m["faces"]
    cz = xyz[m["tets"]][:, :, 2].mean(1)
    tet_attr = np.where(cz < 0.0, 3, 1)
    cen = xyz[faces].mean(1)
    on_plane = np.all(np.abs(xyz[faces][:, :, 2]) < 1e-12, axis=1)
    cx, cy = cen[:, 0], cen[:, 1]
    isl = on_plane & (np.abs(cx) < a) & (np.abs(cy) < a)
    gnd = on_plane & ((np.abs(cx) > g) | (np.abs(cy) > g))
    port = on_plane & (np.abs(cx) < s) & (cy > -g) & (cy < -a)
    attr = np.full(len(faces), -1)
    attr[m["boundary"]] = 2
    attr[isl | gnd] = 4
    attr[port] = 10
    keep = attr >= 0
    mesh = {"xyz": xyz, "tets": m["tets"], "tet_attr": tet_attr, "tris": faces[keep],
            "tri_attr": attr[keep]}
    return mesh, dict(QMHP_LIKE_MODEL)


def layered_box(n: int) -> tuple[dict, dict, np.ndarray, float]:
    """Unit box (mm), eps 2 below z = 0.5 and 5 above, every boundary node held at the exact
    potential. Returns mesh, model, the exact nodal potential, and the exact energy_nd."""
    xs = np.linspace(0.0, 1.0, n + 1)
    m = tensor_mesh(xs, xs, xs)
    xyz = m["xyz"]
    m["tet_attr"] = np.where(xyz[m["tets"]][:, :, 2].mean(1) < 0.5, 1, 3)
    e1, e2 = 2.0, 5.0
    E1 = 1.0 / (0.5 + 0.5 * e1 / e2)
    E2 = E1 * e1 / e2
    mesh = {"xyz": xyz, "tets": m["tets"], "tet_attr": m["tet_attr"],
            "tris": m["faces"][m["boundary"]], "tri_attr": np.full(int(m["boundary"].sum()), 2)}
    model = {"eps_r": {1: e1, 3: e2}, "pec_attrs": (2,), "port_attr": 10,
             "direction": (0.0, 0.0, 1.0), "L0_m": 1.0e-3, "L_H": 1.0e-8}
    return mesh, model, (lambda z: np.where(z <= 0.5, E1 * z, 0.5 * E1 + E2 * (z - 0.5))), \
        0.5 * e1 * E1 ** 2 + 0.5 * e2 * E2 ** 2


def exact_dirichlet(mesh: dict, profile) -> dict:
    """Dirichlet data for layered_box: every node on an outer face held at the exact value."""
    from nested_solver import boundary_facts  # noqa: PLC0415 - avoid a cycle at import
    bn = boundary_facts(mesh)["boundary_nodes"]
    n = len(mesh["xyz"])
    fixed = np.zeros(n, dtype=bool)
    fixed[bn] = True
    phi = np.zeros(n)
    phi[bn] = profile(mesh["xyz"][bn, 2])
    used = np.unique(mesh["tets"])
    return {"fixed": fixed, "phi": phi, "free": used[~fixed[used]], "geo": None}
