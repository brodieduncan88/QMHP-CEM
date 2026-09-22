# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Verify, without solving anything, the conditions under which the static capacitance
C_h (i) cannot increase under refinement and (ii) bounds the model's continuum value.

(ii) C <= C_h needs only CONFORMITY: every admissible P1 function (1 on the island's
     triangles' vertices, 0 on the ground's) is an H1 function equal to 1 on each island
     triangle and 0 on each ground triangle, so it is admissible for the continuum
     problem on the same polyhedral domain. Checked here: the mesh is conforming (every
     face shared by at most two tetrahedra), no two nodes coincide, every conductor
     triangle has all three vertices in one conductor, and the energy reported is the
     quadratic form of an exactly constrained vector (static_capacitance.py).
(i)  C_{h+1} <= C_h needs NESTING: V_h subset V_{h+1}, the level-h admissible set inside
     the level-(h+1) one, and the same functional. Checked here on the actual refinement:
     coarse nodes unchanged, children partition each parent, P^T K_{h+1} P = K_h to
     round-off (the Galerkin identity, which fails if any of partition, geometry,
     attributes or assembly is wrong), and every constrained fine node is prolonged only
     from coarse nodes of the same conductor.

Usage: verify_nesting.py <mesh.msh> --out result.json   (assembly only, no solve)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "static-anchor-hypothesis"))
import anchor_fem as af  # noqa: E402

EPS_R = {1: 1.0, 3: 11.45}
PEC = (2, 4)


def conformity(mesh: dict) -> dict:
    t = mesh["tets"]
    faces = np.sort(np.vstack([t[:, [0, 1, 2]], t[:, [0, 1, 3]], t[:, [0, 2, 3]],
                               t[:, [1, 2, 3]]]), axis=1)
    uf, cnt = np.unique(faces, axis=0, return_counts=True)
    tri = np.unique(np.sort(mesh["tris"], axis=1), axis=0)
    key = lambda a: a[:, 0].astype(np.int64) * 2**42 + a[:, 1].astype(np.int64) * 2**21 + a[:, 2]
    tri_in_mesh = np.isin(key(tri), key(uf))
    _, first = np.unique(np.round(mesh["xyz"], 12), axis=0, return_index=True)
    return {"max_face_multiplicity": int(cnt.max()),
            "boundary_faces": int((cnt == 1).sum()),
            "every_tagged_triangle_is_a_tet_face": bool(tri_in_mesh.all()),
            "coincident_nodes": int(len(mesh["xyz"]) - len(first)),
            "nodes_in_no_tet": int(len(mesh["xyz"]) - len(np.unique(t)))}


def conductor_consistency(mesh: dict) -> dict:
    comps = af.conductor_components(mesh, PEC)
    label = np.full(len(mesh["xyz"]), -1)
    for k, c in enumerate(comps):
        label[c] = k
    pec_tris = mesh["tris"][np.isin(mesh["tri_attr"], PEC)]
    lab = label[pec_tris]
    return {"components": [int(len(c)) for c in comps],
            "every_conductor_triangle_in_one_conductor": bool((lab == lab[:, :1]).all())}


def prolongation(mesh: dict, fine: dict) -> sp.csr_matrix:
    """The P1 prolongation of refine_red: identity on coarse nodes, the average of an
    edge's two endpoints on its midpoint, reconstructed exactly as refine_red numbers them."""
    t, s = mesh["tets"], mesh["tris"]
    tp = np.vstack([np.stack([t[:, a], t[:, b]], 1) for a, b in af.TET_EDGES])
    fp = np.vstack([np.stack([s[:, a], s[:, b]], 1) for a, b in af.TRI_EDGES])
    uniq = np.unique(np.sort(np.vstack([tp, fp]), axis=1), axis=0)
    n0, n1 = len(mesh["xyz"]), len(fine["xyz"])
    assert n1 == n0 + len(uniq)
    mid = np.arange(n0, n1)
    rows = np.concatenate([np.arange(n0), mid, mid])
    cols = np.concatenate([np.arange(n0), uniq[:, 0], uniq[:, 1]])
    vals = np.concatenate([np.ones(n0), np.full(len(mid), 0.5), np.full(len(mid), 0.5)])
    return sp.csr_matrix((vals, (rows, cols)), shape=(n1, n0)), uniq


def nesting(mesh: dict, fine: dict, L0_m: float = 1e-3) -> dict:
    P, uniq = prolongation(mesh, fine)
    n0 = len(mesh["xyz"])
    out = {"coarse_nodes_unchanged": bool(np.array_equal(fine["xyz"][:n0], mesh["xyz"])),
           "midpoints_exact_rel": float(np.abs(fine["xyz"][n0:] - 0.5 * (
               mesh["xyz"][uniq[:, 0]] + mesh["xyz"][uniq[:, 1]])).max()
               / np.abs(mesh["xyz"]).max())}
    # children partition each parent: the 8 children of tet i are rows i + k*nt
    nt = len(mesh["tets"])
    Lc = af.scales(mesh, L0_m, 1.0)["Lc_m"]
    x0, x1 = mesh["xyz"] * L0_m / Lc, fine["xyz"] * L0_m / Lc
    _, v0 = af._tet_geometry(x0, mesh["tets"])
    _, v1 = af._tet_geometry(x1, fine["tets"])
    out["children_volume_sum_rel_err"] = float(np.abs(v1.reshape(8, nt).sum(0) - v0).max() / v0.max())
    out["fine"] = conformity(fine)
    K0 = af.p1_stiffness(mesh, x0, EPS_R)
    K1 = af.p1_stiffness(fine, x1, EPS_R)
    D = (P.T @ K1 @ P - K0).tocsr()
    out["galerkin_identity_rel"] = float(abs(D).max() / abs(K0).max())
    # constraint nesting: fine constrained nodes are prolonged from same-conductor nodes
    c0 = af.conductor_components(mesh, PEC)
    c1 = af.conductor_components(fine, PEC)
    lab0 = np.full(n0, -1)
    for k, c in enumerate(c0):
        lab0[c] = k
    ok, extension = True, 0
    for k, c in enumerate(c1):
        rows = P[c]
        parents = rows.indices
        ok &= bool(np.all(lab0[parents] == k))
    for k, c in enumerate(c0):          # interior edges joining two nodes of one conductor
        both = (lab0[uniq[:, 0]] == k) & (lab0[uniq[:, 1]] == k)
        in_fine = np.isin(n0 + np.flatnonzero(both), c1[k])
        extension += int((~in_fine).sum())
    out["constraint_sets_nested"] = ok
    out["coarse_conductor_nodes_kept"] = all(np.array_equal(np.sort(c1[k][c1[k] < n0]), np.sort(c0[k]))
                                             for k in range(len(c0)))
    out["numerical_conductor_extension_edges"] = extension
    out["components_coarse_fine"] = [[int(len(a)) for a in c0], [int(len(a)) for a in c1]]
    # an admissible coarse function without any solve: the island indicator
    phi = np.zeros(n0); phi[c0[1]] = 1.0
    e0 = float(phi @ (K0 @ phi)); e1 = float((P @ phi) @ (K1 @ (P @ phi)))
    out["indicator_energy_rel_diff"] = abs(e1 - e0) / e0
    pf = P @ phi
    out["prolonged_indicator_admissible"] = bool(np.all(pf[c1[1]] == 1.0) and np.all(pf[c1[0]] == 0.0))
    return out


def _static_module():
    import importlib.util
    here = Path(__file__).resolve().parents[1] / "static-anchor-hypothesis"
    spec = importlib.util.spec_from_file_location("sah_static", here / "static_capacitance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def synthetic_controls() -> dict:
    """Synthetic geometries only. The positive control and two negative controls, each
    removing one condition of the monotonicity proof."""
    sc = _static_module()
    out = {}
    # positive: nested refinement of the fringing slab cannot raise C
    mesh, model = sc._slab(4, island_patch=True)
    c0 = sc.static_capacitance(mesh, **model)["C_F"]
    fine = af.refine_red(mesh)
    c1 = sc.static_capacitance(fine, **model)["C_F"]
    out["nested_refinement_C1_over_C0"] = c1 / c0
    # negative 1 - spaces NOT nested, SAME model: refine, then move only new nodes that lie
    # strictly inside one homogeneous layer, off every boundary, interface and conductor, so
    # the geometry, materials and constraints are unchanged and only the fine space differs.
    # The Galerkin identity must then fail (the verifier's detection power); whether C
    # happens to rise in this instance is reported, not required.
    mesh, model = sc._slab(4, island_patch=True)
    c0 = sc.static_capacitance(mesh, **model)["C_F"]
    fine = af.refine_red(mesh)
    n0 = len(mesh["xyz"])
    x = fine["xyz"].copy()
    h = 1.0 / 8.0
    z = x[:, 2]
    inner = ((np.arange(len(x)) >= n0) & (x[:, 0] > h / 2) & (x[:, 0] < 2 - h / 2)
             & (x[:, 1] > h / 2) & (x[:, 1] < 1 - h / 2)
             & (((z > h / 2) & (z < 0.5 - h / 2)) | ((z > 0.5 + h / 2) & (z < 1 - h / 2))))
    rng = np.random.default_rng(7)
    x[inner] += rng.uniform(-0.2 * h, 0.2 * h, size=(int(inner.sum()), 3))
    moved = dict(fine, xyz=x)
    g_ref, _ = af._tet_geometry(fine["xyz"], fine["tets"])
    J = lambda xyz: np.linalg.det(np.stack([xyz[fine["tets"]][:, k] - xyz[fine["tets"]][:, 0]
                                            for k in (1, 2, 3)], 2))
    out["non_nested_space_orientation_preserved"] = bool(np.all(np.sign(J(x)) == np.sign(J(fine["xyz"]))))
    out["non_nested_space_nodes_moved"] = int(inner.sum())
    c1 = sc.static_capacitance(moved, **model)["C_F"]
    out["non_nested_space_C1_over_C0"] = c1 / c0
    P, _ = prolongation(mesh, fine)
    K0 = af.p1_stiffness(mesh, mesh["xyz"], model["eps_r"])
    Kn = af.p1_stiffness(moved, x, model["eps_r"])
    Kr = af.p1_stiffness(fine, fine["xyz"], model["eps_r"])
    out["galerkin_identity_rel_nested"] = float(abs(P.T @ Kr @ P - K0).max() / abs(K0).max())
    out["galerkin_identity_rel_non_nested"] = float(abs(P.T @ Kn @ P - K0).max() / abs(K0).max())
    # negative 2 - constraint sets NOT nested: grow the fine island by one ring of top-face
    # triangles; the finer problem then has a larger conductor and C rises
    mesh, model = sc._slab(4, island_patch=True)
    c0 = sc.static_capacitance(mesh, **model)["C_F"]
    fine = af.refine_red(mesh)
    xyz, tris = fine["xyz"], fine["tris"]
    isl = fine["tri_attr"] == 4
    isl_nodes = np.unique(tris[isl])
    top = np.all(np.isclose(xyz[tris][:, :, 2], 1.0), axis=1)
    ring = top & ~isl & np.isin(tris, isl_nodes).any(1)
    attr = fine["tri_attr"].copy(); attr[ring] = 4
    grown = dict(fine, tri_attr=attr)
    c1 = sc.static_capacitance(grown, **model)["C_F"]
    out["non_nested_constraints_C1_over_C0"] = c1 / c0
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args(argv)
    if a.synthetic:
        print(json.dumps(synthetic_controls(), indent=1))
        return 0
    m = af.read_gmsh22(a.mesh)
    res = {"mesh_sha256": af.sha256(a.mesh), "level0": conformity(m),
           "conductors": conductor_consistency(m), "level0_to_1": nesting(m, af.refine_red(m)),
           "solves_performed": 0}
    text = json.dumps(res, indent=1)
    if a.out:
        Path(a.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
