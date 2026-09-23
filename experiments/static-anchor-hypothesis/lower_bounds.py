#!/usr/bin/env python3
# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Rigorous LOWER bounds on the discrete first moment ``A = f^T M^-1 f / L`` of the N2R
port, on the committed mesh and on uniform red refinements of it.

For a symmetric positive-definite ``M`` and ANY trial space ``V``,

    f^T M^-1 f  >=  b^T G^-1 b ,   G = V^T M V ,  b = V^T f              (Rayleigh-Ritz)

because ``f^T M^-1 f = max_y (f.y)^2 / (y^T M y)``. Two trial vectors are used:
``y1 = D^-1 f`` (supported only on the port-face edges, since f is) and
``y2 = D^-1 M y1`` (one ring of neighbours further out), with ``D = diag(M)``. Only
matrix-vector products and a 2 x 2 dense solve are performed: this is not a solve of the
finite-element system, and no value here depends on an iterative tolerance.

What it measures: a number the direct first moment on that mesh CANNOT be below. If the
bound doubles each time the mesh is halved, the first moment has no finite limit under
that refinement - whatever the exact values are.

Reads only committed inputs (the N2R mesh, whose sha256 is checked). Writes nothing
unless ``--out`` is given. Level 2 (4.1 M tetrahedra) is opt-in: it needs several GB.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import anchor_fem as af  # noqa: E402

REPO = HERE.parents[1]
MESH = (REPO / "results" / "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z" / "L2" / "solver"
        / "coupled_chip_cell_L2.msh")
MESH_SHA256 = "d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428"
#: the N2R model, from experiments/first-moment-diagnostic/config.candidate.json
MODEL = {"eps_r": {1: 1.0, 3: 11.45}, "pec_attrs": (2, 4), "port_attr": 10,
         "direction": (0.0, 1.0, 0.0), "L0_m": 1.0e-3, "L_H": 1.0345665367517793e-07}


def bounds(mesh: dict) -> dict:
    s = af.assemble_edge_system(mesh, **MODEL)
    M, f = s["M_free"], s["f_free"]
    d = M.diagonal()
    y1 = f / d
    My1 = M @ y1
    y2 = My1 / d
    My2 = M @ y2
    G = np.array([[y1 @ My1, y1 @ My2], [y2 @ My1, y2 @ My2]])
    b = np.array([f @ y1, f @ y2])
    k = s["scales"]["A_GHz2_per_nd"] / s["scales"]["L_nd"]
    return {"n_tets": int(len(mesh["tets"])), "n_edges": int(len(s["edges"])),
            "n_free": int(M.shape[0]), "port_edges_with_nonzero_f": int(np.count_nonzero(f)),
            "f_norm_2": float(np.linalg.norm(f)), "fT_Dinv_f": float(f @ y1),
            "LB1_GHz2": float((f @ y1) ** 2 / (y1 @ My1)) * k,
            "LB2_GHz2": float(b @ np.linalg.solve(G, b)) * k,
            "A_GHz2_per_nd": s["scales"]["A_GHz2_per_nd"], "L_nd": s["scales"]["L_nd"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--levels", type=int, nargs="+", default=[0, 1])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if af.sha256(MESH) != MESH_SHA256:
        print("REFUSED: the N2R mesh digest does not match", file=sys.stderr)
        return 2
    mesh = af.read_gmsh22(MESH)
    rows, level = [], 0
    for target in sorted(args.levels):
        while level < target:
            mesh = af.refine_red(mesh)
            level += 1
        r = {"level": level, **bounds(mesh)}
        if rows:
            r["LB2_ratio_to_previous"] = r["LB2_GHz2"] / rows[-1]["LB2_GHz2"]
        rows.append(r)
        print(json.dumps(r), flush=True)
    if args.out:
        args.out.write_text(json.dumps({"mesh_sha256": MESH_SHA256, "rows": rows}, indent=1)
                            + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
