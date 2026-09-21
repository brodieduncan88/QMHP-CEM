#!/usr/bin/env python3
"""SYNTHETIC, NON-QMHP fixtures for the compiled first-moment diagnostic, and the
independent answer they are checked against.

The geometry here is a plain two-material brick. It is NOT the QMHP-CEM coupled cell:
different dimensions, different permittivities, different port, no island, no resonator,
no refinement box. Nothing in this file reads the N2R mesh, the N2R config or any
committed result, and nothing here computes a physical E_C or g.

    box       2 x 1 x 1 mm, split at x = 1 mm
    materials attribute 1: eps_r = 1  (x < 1 mm)     attribute 2: eps_r = 4  (x > 1 mm)
    port      attribute 10, the whole x = 0 face, direction +Y, lumped inductance L
    PEC       attribute 2 (x = 2 mm face) and attribute 4 (z = 0 face)

The PEC face at z = 0 shares its edge line with the port face, so the port functional has
nonzero entries on essential dofs and the PEC restriction is actually exercised.

THE INDEPENDENT ANSWER. ``independent_first_moment`` assembles the lowest-order Nedelec
(Whitney) mass matrix and the port linear form directly from the mesh arrays, in Palace's
nondimensional units, and solves the free-dof system densely. It shares no code with
Palace or MFEM: the element formulas are written out here. A is a scalar invariant of the
pair (M, f), so it does not depend on matching Palace's dof numbering or edge orientation,
only on using one consistent convention for both - which this file does.

Offline except for gmsh meshing, which is local. No network, no Palace, no committed data.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FIXTURE_DIR = HERE / "fixtures"
MSH_FORMAT_VERSION = 2.2

EPSILON0 = 8.8541878176e-12
MU0 = 4.0e-7 * math.pi
C0 = 1.0 / math.sqrt(EPSILON0 * MU0)

#: Geometry in mm (Model.L0 = 0.001). Deliberately unlike the QMHP cell.
LX1, LX2, LY, LZ = 1.0, 1.0, 1.0, 1.0
MESH_SIZE_MM = 0.34
ATTR_VACUUM, ATTR_DIELECTRIC = 1, 2
EPS_R = {ATTR_VACUUM: 1.0, ATTR_DIELECTRIC: 4.0}
ATTR_PORT, ATTR_PEC_X, ATTR_PEC_Z = 10, 2, 4
PORT_DIRECTION = np.array([0.0, 1.0, 0.0])
L0_M = 1.0e-3


def generate_mesh(path: Path, *, mesh_size_mm: float = MESH_SIZE_MM) -> dict:
    """Mesh the brick with gmsh and return the raw arrays the assembler needs."""
    import gmsh

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("Mesh.MshFileVersion", MSH_FORMAT_VERSION)
        gmsh.model.add("first-moment-synthetic")
        occ = gmsh.model.occ
        b1 = occ.addBox(0.0, 0.0, 0.0, LX1, LY, LZ)
        b2 = occ.addBox(LX1, 0.0, 0.0, LX2, LY, LZ)
        occ.fragment([(3, b1)], [(3, b2)])
        occ.synchronize()

        vols = gmsh.model.getEntities(3)
        vol_tag = {}
        for dim, tag in vols:
            x, _, _ = gmsh.model.occ.getCenterOfMass(dim, tag)
            vol_tag[ATTR_VACUUM if x < LX1 else ATTR_DIELECTRIC] = tag
        for attr, tag in vol_tag.items():
            gmsh.model.addPhysicalGroup(3, [tag], attr)

        faces = {}
        for dim, tag in gmsh.model.getEntities(2):
            x, y, z = gmsh.model.occ.getCenterOfMass(dim, tag)
            if abs(x) < 1e-9:
                faces.setdefault(ATTR_PORT, []).append(tag)
            elif abs(x - (LX1 + LX2)) < 1e-9:
                faces.setdefault(ATTR_PEC_X, []).append(tag)
            elif abs(z) < 1e-9:
                faces.setdefault(ATTR_PEC_Z, []).append(tag)
        for attr, tags in faces.items():
            gmsh.model.addPhysicalGroup(2, tags, attr)

        gmsh.option.setNumber("Mesh.MeshSizeMin", mesh_size_mm)
        gmsh.option.setNumber("Mesh.MeshSizeMax", mesh_size_mm)
        gmsh.model.mesh.generate(3)
        path.parent.mkdir(parents=True, exist_ok=True)
        gmsh.write(str(path))

        node_tags, coords, _ = gmsh.model.mesh.getNodes()
        order = np.argsort(node_tags)
        node_tags = np.asarray(node_tags)[order]
        xyz = np.asarray(coords).reshape(-1, 3)[order]
        index = {int(t): i for i, t in enumerate(node_tags)}

        def cells(dim: int, etype: int) -> tuple[np.ndarray, np.ndarray]:
            conn, attrs = [], []
            for attr in gmsh.model.getPhysicalGroups(dim):
                a = attr[1]
                for ent in gmsh.model.getEntitiesForPhysicalGroup(dim, a):
                    types, _, nodes = gmsh.model.mesh.getElements(dim, ent)
                    for t, nd in zip(types, nodes):
                        if t != etype:
                            continue
                        npe = 4 if etype == 4 else 3
                        blk = np.asarray(nd).reshape(-1, npe)
                        conn.append(np.vectorize(index.get)(blk))
                        attrs.append(np.full(blk.shape[0], a))
            return np.vstack(conn), np.concatenate(attrs)

        tets, tet_attr = cells(3, 4)
        tris, tri_attr = cells(2, 2)
    finally:
        gmsh.finalize()
    return {"xyz_mm": xyz, "tets": tets, "tet_attr": tet_attr, "tris": tris,
            "tri_attr": tri_attr}


# --- the independent assembly -------------------------------------------------------
#: Degree-2 exact rule on the reference tetrahedron (4 points, equal weights).
_TET_A, _TET_B = 0.5854101966249685, 0.1381966011250105
_TET_BARY = np.array([[_TET_A, _TET_B, _TET_B, _TET_B],
                      [_TET_B, _TET_A, _TET_B, _TET_B],
                      [_TET_B, _TET_B, _TET_A, _TET_B],
                      [_TET_B, _TET_B, _TET_B, _TET_A]])
_TET_W = np.full(4, 0.25)
#: Degree-2 exact rule on the reference triangle (3 points, equal weights).
_TRI_BARY = np.array([[2 / 3, 1 / 6, 1 / 6], [1 / 6, 2 / 3, 1 / 6], [1 / 6, 1 / 6, 2 / 3]])
_TRI_W = np.full(3, 1 / 3)
#: Local edges of a tetrahedron and of a triangle, as vertex-index pairs.
_TET_EDGES = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
_TRI_EDGES = ((0, 1), (0, 2), (1, 2))


def _edge_key(a: int, b: int) -> tuple[int, int]:
    """One global orientation per edge: from the lower to the higher node index."""
    return (a, b) if a < b else (b, a)


def _tet_gradients(p: np.ndarray) -> tuple[np.ndarray, float]:
    """Constant barycentric gradients and the signed volume of an affine tetrahedron."""
    J = np.column_stack([p[1] - p[0], p[2] - p[0], p[3] - p[0]])
    vol = float(np.linalg.det(J)) / 6.0
    Jinv = np.linalg.inv(J)
    # x = p0 + J xi, so grad_x(lambda_i) = J^-T e_i, which is the i-th ROW of J^-1.
    # (Taking the columns instead - Jinv.T - silently gives a wrong mass matrix that
    # still has the right volume; the constant-field invariant below catches it.)
    g = np.zeros((4, 3))
    g[1:] = Jinv
    g[0] = -g[1:].sum(axis=0)
    return g, vol


def constant_field_invariant(mesh: dict, M: np.ndarray, edges: dict, xyz: np.ndarray,
                             vol_by_attr: dict, eps_r: dict) -> dict:
    """An exact check on the assembled mass matrix, independent of Palace.

    The lowest-order Nedelec space reproduces constant vector fields exactly: for E = c the
    edge dof is c . (x_b - x_a), and the interpolant IS c, so u^T M u must equal
    sum_K eps_K |c|^2 vol_K. This caught a transposed Jacobian inverse in the barycentric
    gradients that left the element volumes right and the mass matrix wrong.
    """
    out = []
    for c in (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]),
              np.array([0.0, 0.0, 1.0]), np.array([0.3, -0.7, 0.2])):
        u = np.zeros(M.shape[0])
        for (a, b), i in edges.items():
            u[i] = c @ (xyz[b] - xyz[a])
        got = float(u @ M @ u)
        want = sum(eps_r[k] * v for k, v in vol_by_attr.items()) * float(c @ c)
        out.append({"c": c.tolist(), "uMu": got, "exact": want,
                    "relative_error": abs(got - want) / want})
    return {"checks": out, "max_relative_error": max(o["relative_error"] for o in out)}


def independent_first_moment(mesh: dict, *, L_H: float, eps_r: dict | None = None,
                             port_attr: int = ATTR_PORT,
                             pec_attrs: tuple[int, ...] = (ATTR_PEC_X, ATTR_PEC_Z),
                             direction: np.ndarray = PORT_DIRECTION,
                             L0_m: float = L0_M) -> dict:
    """A = f_free^T M_free^-1 f_free / L_nd, assembled from scratch.

    Whitney edge function of edge (i, j): w_ij = lam_i grad(lam_j) - lam_j grad(lam_i).
    On an affine tetrahedron the gradients are constant, so w . w is quadratic and the
    4-point rule is exact; on a face w restricted to the face is linear, so the 3-point
    rule is exact. Palace integrates both with fem::DefaultIntegrationOrder = 2p + order|J|
    = 2 for order-1 elements on affine cells, which is exact for the same degrees.
    """
    eps_r = EPS_R if eps_r is None else eps_r
    xyz_mm, tets, tet_attr = mesh["xyz_mm"], mesh["tets"], mesh["tet_attr"]
    tris, tri_attr = mesh["tris"], mesh["tri_attr"]

    # Nondimensionalization: Lc is the largest axis-aligned bounding-box extent in metres
    # (no Model.Lc in the config), and the mesh is divided by it.
    bbox_m = (xyz_mm.max(axis=0) - xyz_mm.min(axis=0)) * L0_m
    Lc_m = float(bbox_m.max())
    xyz = xyz_mm * L0_m / Lc_m
    L_nd = L_H / (MU0 * Lc_m)
    tc_ns = 1.0e9 * Lc_m / C0

    edges: dict[tuple[int, int], int] = {}

    def edge_id(a: int, b: int) -> int:
        k = _edge_key(a, b)
        if k not in edges:
            edges[k] = len(edges)
        return edges[k]

    for t in tets:
        for a, b in _TET_EDGES:
            edge_id(int(t[a]), int(t[b]))
    n = len(edges)

    # Mass matrix: M_ef = sum_K eps_r(K) int_K w_e . w_f
    M = np.zeros((n, n))
    vol_by_attr: dict[int, float] = {}
    for t, attr in zip(tets, tet_attr):
        p = xyz[t]
        g, vol = _tet_gradients(p)
        if vol < 0:                      # use a consistent positive volume
            vol = -vol
        vol_by_attr[int(attr)] = vol_by_attr.get(int(attr), 0.0) + vol
        eps = eps_r[int(attr)]
        loc = np.zeros((6, 6))
        for q in range(4):
            lam = _TET_BARY[q]
            w = np.array([lam[i] * g[j] - lam[j] * g[i] for i, j in _TET_EDGES])
            loc += _TET_W[q] * vol * eps * (w @ w.T)
        ids, sgn = [], []
        for a, b in _TET_EDGES:
            ga, gb = int(t[a]), int(t[b])
            ids.append(edge_id(ga, gb))
            sgn.append(1.0 if ga < gb else -1.0)
        ids, sgn = np.array(ids), np.array(sgn)
        M[np.ix_(ids, ids)] += (sgn[:, None] * sgn[None, :]) * loc

    # Port geometry, exactly as UniformElementData computes it: l is the bounding-box
    # extent along the direction, w the largest remaining extent. The coefficient of the
    # voltage form is 1 / (w * n_elem) with n_elem = 1.
    port_mask = tri_attr == port_attr
    pts = xyz[np.unique(tris[port_mask])]
    extents = pts.max(axis=0) - pts.min(axis=0)
    axis_l = int(np.argmax(np.abs(direction)))
    l_geom = float(extents[axis_l])
    rest = extents.copy()
    rest[axis_l] = 0.0
    w_geom = float(rest.max())
    coeff = 1.0 / w_geom
    d_hat = direction / np.linalg.norm(direction)

    # f_e = int_port (coeff * d_hat) . w_e dS, over the face Whitney functions.
    f = np.zeros(n)
    for tri in tris[port_mask]:
        p = xyz[tri]
        e1, e2 = p[1] - p[0], p[2] - p[0]
        nrm = np.cross(e1, e2)
        area = 0.5 * float(np.linalg.norm(nrm))
        # in-plane barycentric gradients of the triangle
        G = np.linalg.pinv(np.column_stack([e1, e2, nrm / np.linalg.norm(nrm)]))
        g2 = np.zeros((3, 3))
        g2[1] = G[0]
        g2[2] = G[1]
        g2[0] = -(g2[1] + g2[2])
        loc = np.zeros(3)
        for q in range(3):
            lam = _TRI_BARY[q]
            w = np.array([lam[i] * g2[j] - lam[j] * g2[i] for i, j in _TRI_EDGES])
            loc += _TRI_W[q] * area * (w @ (coeff * d_hat))
        for k, (a, b) in enumerate(_TRI_EDGES):
            ga, gb = int(tri[a]), int(tri[b])
            f[edge_id(ga, gb)] += loc[k] * (1.0 if ga < gb else -1.0)

    # PEC elimination: every edge of every PEC boundary triangle.
    pec = np.zeros(n, dtype=bool)
    for tri, attr in zip(tris, tri_attr):
        if int(attr) in pec_attrs:
            for a, b in _TRI_EDGES:
                pec[edge_id(int(tri[a]), int(tri[b]))] = True
    free = np.flatnonzero(~pec)

    invariant = constant_field_invariant(mesh, M, edges, xyz, vol_by_attr, eps_r)
    assert invariant["max_relative_error"] < 1e-12, invariant

    x = np.linalg.solve(M[np.ix_(free, free)], f[free])
    A_nd = float(f[free] @ x / L_nd)
    return {
        "A_nd": A_nd,
        "constant_field_invariant_max_relative_error": invariant["max_relative_error"],
        "solution_norm": float(np.linalg.norm(x)),
        "A_GHz2": A_nd / (2.0 * math.pi * tc_ns) ** 2,
        "n_edges_total": n,
        "n_edges_pec": int(pec.sum()),
        "n_edges_free": int(free.size),
        "Lc_m": Lc_m,
        "tc_ns": tc_ns,
        "L_nd": L_nd,
        "port_w_nd": w_geom,
        "port_l_nd": l_geom,
        "f_norm2_full": float(f @ f),
        "f_norm2_free": float(f[free] @ f[free]),
        "f_norm2_essential": float(f @ f - f[free] @ f[free]),
        "cond_M_free": float(np.linalg.cond(M[np.ix_(free, free)])),
        "lambda_min_M_free": float(np.linalg.eigvalsh(M[np.ix_(free, free)]).min()),
        "n_tets": int(len(tets)),
        "n_port_tris": int(port_mask.sum()),
    }


def palace_config(mesh_name: str, *, L_H: float, max_its: int = 2000,
                  port_active: bool = True, check_null_space: bool = True) -> dict:
    """A Palace FirstMoment config for the fixture. Not derived from any QMHP config."""
    port = {"Index": 1, "Attributes": [ATTR_PORT], "Direction": "+Y", "L": L_H}
    if not port_active:
        port["Active"] = False
    return {
        "Problem": {"Type": "FirstMoment", "Verbose": 2, "Output": "postpro"},
        "Model": {"Mesh": mesh_name, "L0": L0_M},
        "Domains": {"Materials": [
            {"Attributes": [ATTR_VACUUM], "Permittivity": EPS_R[ATTR_VACUUM],
             "Permeability": 1.0},
            {"Attributes": [ATTR_DIELECTRIC], "Permittivity": EPS_R[ATTR_DIELECTRIC],
             "Permeability": 1.0}]},
        "Boundaries": {"PEC": {"Attributes": [ATTR_PEC_X, ATTR_PEC_Z]},
                       "LumpedPort": [port]},
        "Solver": {"Order": 1, "Device": "CPU",
                   "Linear": {"Type": "Default", "KSPType": "CG", "Tol": 1e-8,
                              "MaxIts": 100, "MGMaxLevels": 1},
                   "FirstMoment": {"Tol": 1e-12, "MaxIts": max_its,
                                   "CheckFunctional": True,
                                   "CheckNullSpace": check_null_space,
                                   "NullSpaceSamples": 4, "Seed": 20260920}},
    }


#: The fixtures, each with what it is for.
FIXTURES = {
    "A-nominal": {"L_H": 1.0e-9, "purpose": "the full path: functional, PEC restriction, "
                                            "DIAG_ONE padding, mass solve, units"},
    "B-scaled-L": {"L_H": 1.0e-8, "purpose": "A must scale exactly as 1/L"},
    "C-maxits-1": {"L_H": 1.0e-9, "max_its": 1,
                   "purpose": "non-convergence handling: the record must say so"},
    "D-port-inactive": {"L_H": 1.0e-9, "port_active": False,
                        "purpose": "failed-check handling: structured FAILED evidence, "
                                   "no first-moment.json"},
}


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    mesh_path = FIXTURE_DIR / "fm_synthetic.msh"
    mesh = generate_mesh(mesh_path)
    np.savez_compressed(FIXTURE_DIR / "fm_synthetic_arrays.npz", **mesh)
    out = {
        "label": "SYNTHETIC NON-QMHP FIXTURES FOR THE COMPILED DIAGNOSTIC",
        "not_qmhp": ("a plain two-material brick; no QMHP geometry, mesh, material or "
                     "port is used, and no committed QMHP result is read"),
        "mesh": {"file": mesh_path.name, "n_nodes": int(len(mesh["xyz_mm"])),
                 "n_tets": int(len(mesh["tets"])), "n_tris": int(len(mesh["tris"]))},
        "fixtures": {},
    }
    for name, spec in FIXTURES.items():
        cfg = palace_config(mesh_path.name, L_H=spec["L_H"],
                            max_its=spec.get("max_its", 2000),
                            port_active=spec.get("port_active", True))
        (FIXTURE_DIR / f"config-{name}.json").write_text(json.dumps(cfg, indent=2) + "\n")
        entry = {"purpose": spec["purpose"], "config": f"config-{name}.json",
                 "L_H": spec["L_H"]}
        if spec.get("port_active", True):
            entry["independent"] = independent_first_moment(mesh, L_H=spec["L_H"])
        out["fixtures"][name] = entry
    a, b = out["fixtures"]["A-nominal"], out["fixtures"]["B-scaled-L"]
    out["scaling_check"] = {
        "A_nominal_times_L_ratio": a["independent"]["A_nd"] / b["independent"]["A_nd"],
        "expected": b["L_H"] / a["L_H"],
    }
    (HERE / "synthetic_fixture.json").write_text(json.dumps(out, indent=1) + "\n")
    print(out["label"])
    print(f"  mesh: {out['mesh']}")
    for name, e in out["fixtures"].items():
        ind = e.get("independent")
        if ind:
            print(f"  {name:<16} A_nd = {ind['A_nd']:.12e}  free dofs {ind['n_edges_free']}"
                  f"/{ind['n_edges_total']}  cond(M_free) = {ind['cond_M_free']:.3e}")
        else:
            print(f"  {name:<16} (no independent answer: {e['purpose']})")


if __name__ == "__main__":
    main()
