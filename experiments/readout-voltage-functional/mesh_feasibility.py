#!/usr/bin/env python3
"""Offline mesh feasibility of the readout-voltage functional (no fields, no solve).

Reads the committed L2 mesh of the N1R record (byte-identical to N2R's) and
answers, from geometry alone:

  * where the fluxonium port face (physical ``port_F1``) is, how many triangles
    it has and whether their area is the declared 0.020 x 0.040 mm;
  * whether the proposed readout integration rectangles (the coupling pad's
    +Y and -Y gaps to ground) consist only of etched dielectric faces, border
    PEC on their pad side and on their ground side, and how the mesh resolves
    the 0.030 mm gap (faces, edge lengths, levels across the gap);
  * the mesh bounding box, which fixes Palace's length scale ``Lc`` for the
    dimensionalisation of a reconstructed voltage.

It writes ``mesh_feasibility.json`` next to itself. It does not read any
field file, any Palace output or any result record other than the mesh.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

MESH = REPO_ROOT / "results/COUPLED-LADDER-O1-L2-N1R-20260919T110053Z/L2/solver/coupled_chip_cell_L2.msh"
Z_TOL = 1e-9


def load_mesh(path: Path):
    import gmsh

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.open(str(path))
    tags, coords, _ = gmsh.model.mesh.getNodes()
    xyz = np.asarray(coords, float).reshape(-1, 3)
    index = {int(t): i for i, t in enumerate(tags)}
    physical = {}
    for dim, ptag in gmsh.model.getPhysicalGroups():
        name = gmsh.model.getPhysicalName(dim, ptag)
        tris = []
        tets = []
        for ent in gmsh.model.getEntitiesForPhysicalGroup(dim, ptag):
            etypes, _, enodes = gmsh.model.mesh.getElements(dim, ent)
            for et, nn in zip(etypes, enodes):
                nn = np.asarray(nn, int)
                if et == 2:      # 3-node triangle
                    tris.append(nn.reshape(-1, 3))
                elif et == 4:    # 4-node tetrahedron
                    tets.append(nn.reshape(-1, 4))
                else:
                    raise RuntimeError(f"unexpected element type {et} in physical {name}")
        physical[name] = {
            "dim": dim, "tag": ptag,
            "tris": np.vstack(tris) if tris else np.zeros((0, 3), int),
            "tets": np.vstack(tets) if tets else np.zeros((0, 4), int),
        }
    gmsh.finalize()
    return xyz, index, physical


def tri_area(p):
    return 0.5 * np.linalg.norm(np.cross(p[1] - p[0], p[2] - p[0]))


def main():
    xyz, index, phys = load_mesh(MESH)
    to_i = np.vectorize(index.get)
    out = {"mesh": str(MESH.relative_to(REPO_ROOT)), "units": "mm (mesh units, Model.L0 = 1e-3)"}
    bb_min, bb_max = xyz.min(axis=0), xyz.max(axis=0)
    out["bounding_box_mm"] = {"min": bb_min.tolist(), "max": bb_max.tolist(),
                              "extent": (bb_max - bb_min).tolist(),
                              "Lc_mm_palace_default": float((bb_max - bb_min).max())}

    # --- the port face ---------------------------------------------------------------------
    port = to_i(phys["port_F1"]["tris"])
    P = xyz[port]
    areas = np.array([tri_area(p) for p in P])
    out["port_F1"] = {
        "triangles": int(len(port)), "area_mm2": float(areas.sum()),
        "declared_area_mm2": 0.02 * 0.04,
        "bbox_mm": {"min": P.reshape(-1, 3).min(axis=0).tolist(), "max": P.reshape(-1, 3).max(axis=0).tolist()},
        "z_max_abs": float(np.abs(P[:, :, 2]).max()),
    }

    # --- z = 0 faces of the volume mesh, classified ------------------------------------------
    pec_faces = {tuple(sorted(t)) for t in to_i(phys["sheet_pec"]["tris"])}
    port_faces = {tuple(sorted(t)) for name in ("port_F1", "port_R1_a", "port_R1_b") for t in to_i(phys[name]["tris"])}
    tets = np.vstack([to_i(phys[n]["tets"]) for n in ("vacuum", "substrate")])
    onplane = np.abs(xyz[:, 2]) < Z_TOL
    faces = {}
    for tet in tets:
        m = onplane[tet]
        if m.sum() == 3:
            key = tuple(sorted(tet[m]))
            faces.setdefault(key, 0)
            faces[key] += 1
    out["z0_faces"] = {"unique": len(faces), "shared_by_two_tets": int(sum(v == 2 for v in faces.values())),
                       "pec": int(sum(k in pec_faces for k in faces)), "port": int(sum(k in port_faces for k in faces)),
                       "etched": int(sum((k not in pec_faces and k not in port_faces) for k in faces))}
    face_keys = np.array(list(faces.keys()))
    cent = xyz[face_keys].mean(axis=1)
    is_pec = np.array([k in pec_faces for k in faces])
    is_port = np.array([k in port_faces for k in faces])

    def region(x0, x1, y0, y1):
        return (cent[:, 0] > x0) & (cent[:, 0] < x1) & (cent[:, 1] > y0) & (cent[:, 1] < y1)

    # --- the proposed readout integration rectangles ----------------------------------------
    rects = {
        "Gamma_R_plusY":  {"x": [-0.485, -0.405], "y": [0.05, 0.08], "direction": "-Y (from ground at +Y to the pad at -Y)"},
        "Gamma_R_minusY": {"x": [-0.485, -0.405], "y": [-0.08, -0.05], "direction": "+Y (from ground at -Y to the pad at +Y)"},
    }
    out["readout_rectangles"] = {}
    for name, r in rects.items():
        x0, x1 = r["x"]; y0, y1 = r["y"]
        inside = region(x0, x1, y0, y1)
        keys = face_keys[inside]
        pts = xyz[keys]
        a = np.array([tri_area(p) for p in pts]) if len(keys) else np.zeros(0)
        edges = []
        for k in keys:
            for i, j in ((0, 1), (1, 2), (0, 2)):
                edges.append(np.linalg.norm(xyz[k[i]] - xyz[k[j]]))
        edges = np.array(edges) if edges else np.zeros(0)
        ys = np.unique(np.round(xyz[np.unique(keys)][:, 1], 9)) if len(keys) else np.zeros(0)
        # neighbours: the strip just beyond the ground edge and just inside the pad edge
        pad_side = (0.04, 0.05) if y0 > 0 else (-0.05, -0.04)
        gnd_side = (0.08, 0.09) if y0 > 0 else (-0.09, -0.08)
        pad_n = region(x0, x1, *pad_side)
        gnd_n = region(x0, x1, *gnd_side)
        # the corner region x in [-0.505, -0.485] beyond y = +-0.08 is predicted to be island etch, not ground
        corner = region(-0.505, -0.485, 0.08, 0.115) if y0 > 0 else region(-0.505, -0.485, -0.115, -0.08)
        out["readout_rectangles"][name] = {
            **r, "width_mm": x1 - x0, "gap_mm": y1 - y0,
            "faces": int(len(keys)), "area_mm2": float(a.sum()), "expected_area_mm2": (x1 - x0) * (y1 - y0),
            "all_faces_etched": bool(len(keys) and not np.any(is_pec[inside] | is_port[inside])),
            "pec_faces_inside": int(np.sum(is_pec[inside])),
            "edge_length_mm": {"min": float(edges.min()) if len(edges) else None, "median": float(np.median(edges)) if len(edges) else None,
                               "max": float(edges.max()) if len(edges) else None},
            "distinct_node_y_levels_in_gap": int(len(ys)),
            "pad_side_strip_faces_pec": int(np.sum(is_pec[pad_n])), "pad_side_strip_faces_total": int(np.sum(pad_n)),
            "ground_side_strip_faces_pec": int(np.sum(is_pec[gnd_n])), "ground_side_strip_faces_total": int(np.sum(gnd_n)),
            "corner_region_x[-0.505,-0.485]_beyond_gap": {"faces": int(np.sum(corner)), "pec": int(np.sum(is_pec[corner])),
                                                          "prediction": "island etch, i.e. no ground: 0 pec faces"},
        }

    # the pad itself and the island, as PEC regions (consistency of the geometry mapping)
    for name, (x0, x1, y0, y1) in {"pad_interior": (-0.5, -0.41, -0.045, 0.045), "island_interior": (-0.67, -0.53, -0.07, 0.07)}.items():
        sel = region(x0, x1, y0, y1)
        out[name] = {"faces": int(sel.sum()), "pec": int(np.sum(is_pec[sel])), "etched": int(np.sum(~is_pec[sel] & ~is_port[sel]))}

    # gap between island and pad (x in [-0.525, -0.505]) must be etched
    sel = region(-0.525, -0.505, -0.045, 0.045)
    out["island_pad_gap"] = {"faces": int(sel.sum()), "pec": int(np.sum(is_pec[sel])), "expected_pec": 0}

    # --- the Palace-side refinement boxes of N1R and N2R do not reach the readout rectangles ---
    box = {"min": [-0.62, -0.125, -0.01], "max": [-0.58, -0.065, 0.01]}
    out["refinement_box_vs_readout_rectangles"] = {
        "box_mm": box,
        "overlaps_Gamma_R": bool(box["max"][0] > -0.485 and box["min"][0] < -0.405),
        "note": "N1R (1 level) and N2R (2 levels) refine only this box; the readout rectangles lie outside it, so "
                "their discretisation is the base L2 mesh in both records",
    }

    for k, v in _walk(out):
        if isinstance(v, float) and not math.isfinite(v):
            raise RuntimeError(f"non-finite value at {k}")
    (HERE / "mesh_feasibility.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


def _walk(obj, path="out"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, obj


if __name__ == "__main__":
    main()
