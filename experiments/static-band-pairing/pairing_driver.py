#!/usr/bin/env python3
# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""THE PAIRED STATIC-VS-BAND REFINEMENT TEST - WITHDRAWN BEFORE APPROVAL, NEVER EXECUTED.

Withdrawn after an independent adversarial review (WITHDRAWN.json): its decisive comparison
is fixed by an exact identity, and three defects would have spent the single attempt. The
code is kept as the reviewed reference for the static solve on saved meshes, the decision
plumbing and the execution-time manifest; require_approval() refuses unconditionally.

Original description:

What it does
------------
On the committed L2 mesh and on two nested Palace box refinements of the island-gap-port
region (levels 0, 1, 2), it computes, ON THE SAME DISCRETE MESH AT EVERY LEVEL:

* the band quantities from Palace's eigenmode solve: B_h (the participation-weighted
  arithmetic mean of f^2 over the saved modes, the records' variant-A rule), H_h
  (1 / sum |p|/f^2, the band's inverse -1 moment) and N_B;
* the static quantity S_h = 1/((2 pi)^2 L_F C_h) from the Dirichlet capacitance of the
  island, computed by static_capacitance.py on the mesh Palace ACTUALLY refined (saved
  with Model.Refinement.SaveAdaptMesh; the level-0 mesh is the committed file);
* the identity residual delta_h = S_h * sum_B(|p|/f^2) - 1 (zero for the declared lumped
  port, a measured perturbation for Palace's distributed sheet port);

and checks, at every step, that the refinement Palace performed is nested (vertices and
edge midpoints matched, then the Galerkin identity P^T K_fine P = K_coarse). The outcome
is decided by the frozen predeclaration.json alone.

Evidence order: Palace's raw outputs are copied into the record as each level finishes,
then the static result, then the nesting check, then summary.json, and LAST the
manifest.sha256 this driver writes with orchestrator.manifest (on the failure path too).

Modes
-----
``--preflight``  generate the three configs and print their digests; no Palace, no solve.
``--execute``    THE TEST. Refuses unless PAIRING-APPROVAL.json binds everything by
                 sha256, and the GitHub run number and attempt are the approved ones.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import math
import os
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE.parent / "static-anchor-hypothesis"))
import anchor_fem as af  # noqa: E402
from orchestrator import manifest  # noqa: E402

PREDECLARATION = HERE / "predeclaration.json"
APPROVAL = HERE / "PAIRING-APPROVAL.json"
RESULTS_ROOT = REPO / "results"
RECORD_PREFIX = "STATIC-BAND-PAIRING-"
BASE_SOLVER_DIR = REPO / "results" / "COUPLED-LADDER-O1-L2-20260916T080802Z" / "L2" / "solver"
BASE_CONFIG = BASE_SOLVER_DIR / "config.json"
BASE_MESH = BASE_SOLVER_DIR / "coupled_chip_cell_L2.msh"
MESH_NAME = "coupled_chip_cell_L2.msh"
SAVED_MESH_NAME = "coupled_chip_cell_L2.mesh"        # Palace: <output>/<mesh stem>.mesh
CODE_FILES = (
    "experiments/static-band-pairing/pairing_driver.py",
    "experiments/static-anchor-hypothesis/static_capacitance.py",
    "experiments/static-anchor-hypothesis/anchor_fem.py",
    "scripts/palace_order1_ladder.py",
    "orchestrator/manifest.py",
    "docker/palace.Dockerfile",
    ".github/workflows/static-band-pairing.yml",
)
PALACE_OUTPUTS = ("eig.csv", "port-EPR.csv", "domain-E.csv", "palace.json",
                  "error-indicators.csv", "port-V.csv", "port-I.csv")


class Refusal(RuntimeError):
    """The test was not run: nothing was spent."""


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_pre() -> dict:
    return json.loads(PREDECLARATION.read_text())


def _static_module():
    spec = importlib.util.spec_from_file_location(
        "sah_static_capacitance", HERE.parent / "static-anchor-hypothesis" / "static_capacitance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def model_from(pre: dict) -> dict:
    m = pre["configuration"]["static_model"]
    return {"eps_r": {int(k): v for k, v in m["eps_r"].items()},
            "pec_attrs": tuple(m["pec_attrs"]), "port_attr": m["port_attr"],
            "direction": tuple(m["direction"]), "L0_m": m["L0_m"], "L_H": m["L_H"]}


# --- the three Palace configurations ----------------------------------------------------

def level_config(level: int, pre: dict) -> dict:
    """The committed L2 config with exactly the declared deltas, and nothing else."""
    cfg = copy.deepcopy(json.loads(BASE_CONFIG.read_text()))
    d = pre["configuration"]["palace_deltas"]
    cfg["Solver"]["Eigenmode"]["Save"] = d["Solver.Eigenmode.Save"]
    cfg["Solver"]["Linear"]["MGMaxLevels"] = d["Solver.Linear.MGMaxLevels"]
    if level > 0:
        box = pre["configuration"]["box"]
        ref = cfg["Model"]["Refinement"]
        ref["Boxes"] = [{"Levels": level, "BoundingBoxMin": box["min_mm"],
                         "BoundingBoxMax": box["max_mm"]}]
        ref["SaveAdaptMesh"] = True
    return cfg


# --- meshes --------------------------------------------------------------------------------

def read_mfem_mesh(path: Path) -> dict:
    """A linear tetrahedral MFEM mesh (v1.x) as Palace's SaveAdaptMesh prints it:
    ``elements`` (attr geom v0..v3, TETRAHEDRON = 4), ``boundary`` (attr geom v0..v2,
    TRIANGLE = 2), ``vertices`` (count, dimension, coordinates). A curved mesh (a
    ``nodes`` section) or any other element type is refused rather than misread."""
    raw = [ln.split("#", 1)[0].strip() for ln in Path(path).read_text().splitlines()]
    lines = [ln for ln in raw if ln]
    if not lines or not lines[0].startswith("MFEM mesh v1."):
        raise ValueError(f"not a conforming MFEM mesh file: {lines[:1]}")
    out, i = {}, 1
    while i < len(lines):
        key = lines[i]
        if key == "dimension":
            if int(lines[i + 1]) != 3:
                raise ValueError("dimension is not 3")
            i += 2
        elif key in ("elements", "boundary"):
            n = int(lines[i + 1])
            rows = np.array([[int(v) for v in lines[i + 2 + j].split()] for j in range(n)])
            want_geom, nv = (4, 4) if key == "elements" else (2, 3)
            if n and (np.any(rows[:, 1] != want_geom) or rows.shape[1] != 2 + nv):
                raise ValueError(f"{key}: only linear {'tetrahedra' if nv == 4 else 'triangles'}")
            out[key] = rows
            i += 2 + n
        elif key == "vertices":
            n = int(lines[i + 1])
            if i + 2 < len(lines) and lines[i + 2] == "nodes":
                raise ValueError("curved mesh (nodes section): refused")
            dim = int(lines[i + 2])
            if dim != 3:
                raise ValueError("vertex dimension is not 3")
            xyz = np.array([[float(v) for v in lines[i + 3 + j].split()] for j in range(n)])
            out["vertices"] = xyz
            i += 3 + n
        elif key in ("nodes", "mfem_NC_mesh", "vertex_parents"):
            raise ValueError(f"unsupported MFEM mesh section {key!r}: refused")
        elif key == "mfem_mesh_end":
            break
        else:
            i += 1
    for need in ("elements", "boundary", "vertices"):
        if need not in out:
            raise ValueError(f"MFEM mesh without a {need} section")
    el, bd = out["elements"], out["boundary"]
    return {"xyz": out["vertices"], "tets": el[:, 2:6].astype(np.int64), "tet_attr": el[:, 0],
            "tris": bd[:, 2:5].astype(np.int64), "tri_attr": bd[:, 0]}


def write_mfem_mesh(mesh: dict, path: Path) -> None:
    """The same format, for synthetic tests and fixtures."""
    L = ["MFEM mesh v1.0", "", "dimension", "3", "", "elements", str(len(mesh["tets"]))]
    L += [f"{a} 4 {t[0]} {t[1]} {t[2]} {t[3]}" for a, t in zip(mesh["tet_attr"], mesh["tets"])]
    L += ["", "boundary", str(len(mesh["tris"]))]
    L += [f"{a} 2 {t[0]} {t[1]} {t[2]}" for a, t in zip(mesh["tri_attr"], mesh["tris"])]
    L += ["", "vertices", str(len(mesh["xyz"])), "3"]
    L += [" ".join(f"{v:.17g}" for v in p) for p in mesh["xyz"]]
    Path(path).write_text("\n".join(L) + "\n")


def nesting(coarse: dict, fine: dict, eps_r: dict, pec_attrs, L0_m: float = 1e-3,
            tol_rel: float = 1e-9) -> dict:
    """Is ``fine`` a nested refinement of ``coarse``? Every fine vertex must be a coarse
    vertex or the midpoint of a coarse edge (bisection and red refinement both add only
    edge midpoints); then P^T K_fine P must equal K_coarse, which fails if the children do
    not partition the parents, if an attribute changed, or if the geometry moved."""
    scale = float(np.abs(coarse["xyz"]).max())
    tol = tol_rel * scale
    tree = cKDTree(fine["xyz"])
    d, idx = tree.query(coarse["xyz"])
    out = {"coarse_vertices_found": bool(np.all(d <= tol)), "max_vertex_offset_rel": float(d.max() / scale)}
    n0, n1 = len(coarse["xyz"]), len(fine["xyz"])
    coarse_of = np.full(n1, -1)
    coarse_of[idx[d <= tol]] = np.flatnonzero(d <= tol)
    edges, _ = af.edge_table(coarse)
    mids = 0.5 * (coarse["xyz"][edges[:, 0]] + coarse["xyz"][edges[:, 1]])
    new = np.flatnonzero(coarse_of < 0)
    dm, em = cKDTree(mids).query(fine["xyz"][new]) if len(new) else (np.zeros(0), np.zeros(0, int))
    out["new_vertices"] = int(len(new))
    out["new_vertices_are_coarse_edge_midpoints"] = bool(np.all(dm <= tol))
    out["max_midpoint_offset_rel"] = float(dm.max() / scale) if len(new) else 0.0
    if not (out["coarse_vertices_found"] and out["new_vertices_are_coarse_edge_midpoints"]):
        out["nested"] = False
        return out
    import scipy.sparse as sp
    old = np.flatnonzero(coarse_of >= 0)
    rows = np.concatenate([old, new, new])
    cols = np.concatenate([coarse_of[old], edges[em, 0], edges[em, 1]])
    vals = np.concatenate([np.ones(len(old)), np.full(len(new), 0.5), np.full(len(new), 0.5)])
    P = sp.csr_matrix((vals, (rows, cols)), shape=(n1, n0))
    Lc = af.scales(coarse, L0_m, 1.0)["Lc_m"]
    K0 = af.p1_stiffness(coarse, coarse["xyz"] * L0_m / Lc, eps_r)
    K1 = af.p1_stiffness(fine, fine["xyz"] * L0_m / Lc, eps_r)
    out["galerkin_identity_rel"] = float(abs(P.T @ K1 @ P - K0).max() / abs(K0).max())
    c0 = af.conductor_components(coarse, pec_attrs)
    c1 = af.conductor_components(fine, pec_attrs)
    lab0 = np.full(n0, -1)
    for k, c in enumerate(c0):
        lab0[c] = k
    out["conductors_coarse_fine"] = [[int(len(c)) for c in c0], [int(len(c)) for c in c1]]
    same = len(c0) == len(c1)
    ok = same and all(np.all(lab0[P[c].indices] == k) for k, c in enumerate(c1))
    kept = same and all(set(coarse_of[c1[k][coarse_of[c1[k]] >= 0]].tolist()) == set(c0[k].tolist())
                        for k in range(len(c0)))
    out["constraint_sets_nested"] = bool(ok and kept)
    out["nested"] = bool(out["constraint_sets_nested"])
    return out


# --- band quantities from Palace's own output -----------------------------------------------

def band(postpro: Path) -> dict:
    rows = list(csv.reader(open(postpro / "eig.csv")))[1:]
    f = np.array([float(r[1]) for r in rows]); fi = np.array([float(r[2]) for r in rows])
    err = np.array([float(r[4]) for r in rows])
    p = np.abs(np.array([float(r[1]) for r in list(csv.reader(open(postpro / "port-EPR.csv")))[1:]]))
    if len(p) != len(f):
        raise ValueError("eig.csv and port-EPR.csv disagree on the number of modes")
    NB = float(p.sum())
    inv = float((p / f ** 2).sum())
    B = float((p * f ** 2).sum() / NB)
    return {"f_GHz": f.tolist(), "imag_f_GHz": fi.tolist(), "backward_error": err.tolist(),
            "p_abs": p.tolist(), "N_B": NB, "sum_p_over_f2": inv, "B_GHz2": B,
            "H_GHz2": 1.0 / inv, "n_modes": int(len(f))}


# --- the frozen decision ------------------------------------------------------------------

def _finite_pos(v) -> bool:
    return (isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool)
            and math.isfinite(v) and v > 0)


def decide(levels: list[dict], pre: dict) -> dict:
    """Pure function of the per-level (S, B, H) and the pre-declaration. Invalid numbers are
    UNQUALIFIED, never a verdict."""
    w = pre["outcomes"]
    need = [(i, k) for i, lv in enumerate(levels) for k in ("S_GHz2", "B_GHz2", "H_GHz2")
            if not _finite_pos(lv.get(k))]
    if len(levels) != len(pre["configuration"]["levels"]) or need:
        return {"verdict": "UNQUALIFIED", "reason": f"missing or invalid values: {need or len(levels)}"}
    S = [lv["S_GHz2"] for lv in levels]; B = [lv["B_GHz2"] for lv in levels]
    H = [lv["H_GHz2"] for lv in levels]
    r = [s / b for s, b in zip(S, B)]
    delta = [s / h - 1.0 for s, h in zip(S, H)]
    g = S[-1] / S[0]
    dr = max(abs(x - r[0]) for x in r)
    dmax = max(abs(x) for x in delta)
    if g < w["power_min_static_growth"]:
        verdict, why = "UNRESOLVED", "LOW POWER: the refinement did not move the static quantity enough"
    elif dmax <= w["supports_max_abs_delta"] and dr <= w["supports_max_ratio_drift"]:
        verdict, why = "SUPPORTS", "the band moves with the static quantity, as the identity predicts"
    elif dmax > w["contradicts_abs_delta_above"] or dr > w["contradicts_ratio_drift_above"]:
        verdict, why = "CONTRADICTS", "the band and the static quantity decouple under refinement"
    else:
        verdict, why = "UNRESOLVED", "between the support and contradiction bounds"
    return {"verdict": verdict, "reason": why, "static_growth_g": g, "band_growth_b": B[-1] / B[0],
            "ratio_S_over_B": r, "ratio_drift": dr, "delta": delta, "max_abs_delta": dmax}


def integrity(levels: list[dict], nest: list[dict], pre: dict) -> list[str]:
    t = pre["integrity"]
    bad = []
    for lv in levels:
        k = lv.get("level")
        run = lv.get("palace_run", {})
        if run.get("returncode") != 0 or run.get("timed_out") or (run.get("dof_probe") or {}).get("refused"):
            bad.append(f"level {k}: Palace did not complete within the budget")
        dof = (run.get("dof_probe") or {}).get("dof_reported")
        if not isinstance(dof, int) or dof > t["dof_cap_per_level"]:
            bad.append(f"level {k}: DOF {dof!r} missing or above the cap")
        bd = lv.get("band") or {}
        if bd.get("n_modes") != t["modes_saved"]:
            bad.append(f"level {k}: {bd.get('n_modes')} modes saved, not {t['modes_saved']}")
        vals = bd.get("f_GHz", []) + bd.get("p_abs", []) + bd.get("backward_error", [])
        if not vals or not all(isinstance(v, float) and math.isfinite(v) for v in vals):
            bad.append(f"level {k}: non-finite band data")
        elif max(bd["backward_error"]) > t["eigen_backward_error_max"]:
            bad.append(f"level {k}: an eigenpair's backward error exceeds the tolerance")
        elif not bd["N_B"] <= 1.0 + t["N_B_excess_tol"]:
            bad.append(f"level {k}: N_B exceeds 1")
        st = lv.get("static") or {}
        idn = st.get("identity") or {}
        checks = [("port voltage", abs(abs(idn.get("port_voltage_of_grad_phi", float("nan"))) - 1.0), t["port_voltage_abs_tol"]),
                  ("PEC gradient", idn.get("grad_phi_on_pec_edges_max_abs", float("nan")), t["pec_edge_abs_tol"]),
                  ("energy identity", idn.get("edge_energy_vs_p1_energy_rel", float("nan")), t["identity_rel_tol"]),
                  ("two routes", idn.get("S_two_routes_rel", float("nan")), t["identity_rel_tol"]),
                  ("static residual", st.get("solve_relative_residual", float("nan")), t["solve_residual_tol"])]
        for name, v, tol in checks:
            if not (isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= tol):
                bad.append(f"level {k}: static {name} {v!r} not within {tol}")
    for n in nest:
        if not n.get("nested") or not (n.get("galerkin_identity_rel", 1.0) <= t["galerkin_identity_rel_tol"]):
            bad.append(f"levels {n.get('from')}->{n.get('to')}: refinement not verified nested")
    C = [lv.get("static", {}).get("C_F") for lv in levels]
    if all(_finite_pos(c) for c in C) and any(C[i + 1] > C[i] * (1 + t["nested_monotone_rel_tol"])
                                              for i in range(len(C) - 1)):
        bad.append("C increased under verified nested refinement")
    if levels and levels[0].get("static", {}).get("S_GHz2") is not None:
        ref = t["level0_static_reproduces_GHz2"]
        if not abs(levels[0]["static"]["S_GHz2"] / ref - 1) <= t["level0_reproduction_rel_tol"]:
            bad.append("level 0 static does not reproduce the committed S0")
    if levels and (levels[0].get("band") or {}).get("f_GHz"):
        ref = t["level0_band_f1_reproduces_GHz"]
        if not abs(levels[0]["band"]["f_GHz"][0] / ref - 1) <= t["level0_band_f1_rel_tol"]:
            bad.append("level 0 band does not reproduce the committed L2 mode 1")
    return bad


# --- gate, one attempt, execution ----------------------------------------------------------

WITHDRAWN = HERE / "WITHDRAWN.json"


def require_approval(pre: dict, env: dict) -> dict:
    if WITHDRAWN.is_file():
        raise Refusal("this test was WITHDRAWN before approval (WITHDRAWN.json): it is not "
                      "to be executed; a replacement needs its own pre-declaration")
    if not APPROVAL.is_file():
        raise Refusal("no PAIRING-APPROVAL.json: the paired test is PREPARED, NOT APPROVED.")
    ap = json.loads(APPROVAL.read_text())
    want = {"authorises": "one execution of the paired static-vs-band refinement test",
            "predeclaration_sha256": sha256(PREDECLARATION),
            "code_sha256": {p: sha256(REPO / p) for p in CODE_FILES},
            "base_mesh_sha256": pre["configuration"]["base_mesh_sha256"],
            "base_config_sha256": pre["configuration"]["base_config_sha256"]}
    for key, value in want.items():
        if ap.get(key) != value:
            raise Refusal(f"approval {key} does not match: the reviewed state has changed")
    if str(env.get("GITHUB_RUN_NUMBER")) != str(ap.get("github_run_number")) or env.get("GITHUB_RUN_ATTEMPT") != "1":
        raise Refusal("this is not the approved workflow run number and first attempt")
    return ap


def _inputs_ok(pre: dict) -> None:
    c = pre["configuration"]
    if sha256(BASE_MESH) != c["base_mesh_sha256"] or sha256(BASE_CONFIG) != c["base_config_sha256"]:
        raise Refusal("an input digest does not match the pre-declaration")
    for lvl in c["levels"]:
        if canonical_sha(level_config(lvl, pre)) != c["config_sha256"][str(lvl)]:
            raise Refusal(f"the level-{lvl} config does not match the pre-declared digest")


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=float) + "\n")


def _finish(rec: Path) -> dict:
    """Last step on every path: the manifest this driver writes at execution time, then
    verified before the process exits (orchestrator.manifest.write_verified)."""
    _, digest = manifest.write_verified(rec)
    return {"manifest_sha256": digest}


def execute(*, runtime: str, image: str, scratch: Path, env: dict | None = None,
            run_palace=None, static_capacitance=None) -> Path:
    env = dict(os.environ if env is None else env)
    pre = load_pre()
    approval = require_approval(pre, env)
    _inputs_ok(pre)
    RESULTS_ROOT.mkdir(exist_ok=True)
    for existing in RESULTS_ROOT.glob(RECORD_PREFIX + "*"):
        raise Refusal(f"{existing.name} exists: the one attempt is spent")
    if run_palace is None:
        sys.path.insert(0, str(REPO / "scripts"))
        from palace_order1_ladder import _run_palace as run_palace  # reviewed launcher
    if static_capacitance is None:
        static_capacitance = _static_module().static_capacitance
    model = model_from(pre)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rec = RESULTS_ROOT / f"{RECORD_PREFIX}{stamp}"
    rec.mkdir(exist_ok=False)                           # the attempt is spent from here
    t0 = time.monotonic()
    levels, nest, prev_mesh = [], [], None
    try:
        for lvl in pre["configuration"]["levels"]:
            work = Path(scratch) / f"level{lvl}"
            work.mkdir(parents=True, exist_ok=False)
            cfg = level_config(lvl, pre)
            (work / "config.json").write_text(json.dumps(cfg, indent=1) + "\n")
            shutil.copy2(BASE_MESH, work / MESH_NAME)
            run = run_palace(runtime, image, work, 1, f"pairing-level{lvl}",
                             dof_budget=pre["integrity"]["dof_cap_per_level"])
            out = rec / f"level{lvl}"
            _write(out / "palace_run.json", {k: v for k, v in run.items() if k != "command"}
                   | {"command": list(map(str, run.get("command", [])))})
            _write(out / "config.json", cfg)
            post = work / "postpro"
            (out / "palace").mkdir(parents=True, exist_ok=True)
            for name in PALACE_OUTPUTS:                     # raw solver output, first
                if (post / name).is_file():
                    shutil.copy2(post / name, out / "palace" / name)
            if (work / "palace_log.txt").is_file():
                shutil.copy2(work / "palace_log.txt", out / "palace" / "palace_log.txt")
            if run.get("returncode") != 0:
                raise RuntimeError(f"Palace level {lvl} did not complete: {run.get('returncode')}")
            mesh_path = work / MESH_NAME if lvl == 0 else post / SAVED_MESH_NAME
            mesh = af.read_gmsh22(mesh_path) if lvl == 0 else read_mfem_mesh(mesh_path)
            info = {"level": lvl, "mesh_file": mesh_path.name, "mesh_sha256": sha256(mesh_path),
                    "n_tets": int(len(mesh["tets"])), "n_nodes": int(len(mesh["xyz"])),
                    "committed": False, "artefact_dir": str(work)}
            _write(out / "mesh.json", info)
            st = static_capacitance(mesh, **model)
            _write(out / "static.json", st)                  # raw static result first
            bd = band(post)
            _write(out / "band.json", bd)
            if prev_mesh is not None:
                n = nesting(prev_mesh, mesh, model["eps_r"], model["pec_attrs"], model["L0_m"])
                n.update({"from": lvl - 1, "to": lvl})
                _write(out / "nesting.json", n)
                nest.append(n)
            levels.append({"level": lvl, "palace_run": run, "static": st, "band": bd,
                           "S_GHz2": st["S_GHz2"], "B_GHz2": bd["B_GHz2"], "H_GHz2": bd["H_GHz2"]})
            prev_mesh = mesh
        bad = integrity(levels, nest, pre)
        outcome = {"verdict": "UNQUALIFIED", "reason": "; ".join(bad)} if bad else decide(levels, pre)
        summary = {"predeclaration_sha256": sha256(PREDECLARATION), "approval_sha256": sha256(APPROVAL),
                   "approval_run_number": approval.get("github_run_number"),
                   "per_level": [{"level": lv["level"], "S_GHz2": lv["S_GHz2"], "B_GHz2": lv["B_GHz2"],
                                  "H_GHz2": lv["H_GHz2"], "C_fF": lv["static"].get("C_fF"),
                                  "N_B": lv["band"]["N_B"], "f1_GHz": lv["band"]["f_GHz"][0],
                                  "dof": (lv["palace_run"].get("dof_probe") or {}).get("dof_reported")}
                                 for lv in levels],
                   "integrity_failures": bad, "outcome": outcome,
                   "wall_s": time.monotonic() - t0,
                   "not_reported": "E_C,F1F1 and g (UNAVAILABLE); nothing is combined with Route A"}
        _write(rec / "summary.json", summary)
        _finish(rec)
    except BaseException as exc:                         # the failure is the recorded outcome
        _write(rec / "failure.json", {"verdict": "FAILED - the one attempt is spent; no retry",
                                      "levels_completed": [lv["level"] for lv in levels],
                                      "error": repr(exc), "traceback": traceback.format_exc(),
                                      "wall_s": time.monotonic() - t0})
        _finish(rec)
        raise
    return rec


def preflight() -> dict:
    pre = load_pre()
    return {"base_mesh_sha256": sha256(BASE_MESH), "base_config_sha256": sha256(BASE_CONFIG),
            "config_sha256": {str(l): canonical_sha(level_config(l, pre)) for l in pre["configuration"]["levels"]},
            "code_sha256": {p: sha256(REPO / p) for p in CODE_FILES if (REPO / p).is_file()},
            "palace_run": "none", "solves_performed": 0}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--execute", action="store_true")
    ap.add_argument("--image")
    ap.add_argument("--runtime", default="docker")
    ap.add_argument("--scratch")
    a = ap.parse_args(argv)
    try:
        if a.preflight:
            print(json.dumps(preflight(), indent=1))
        else:
            if not (a.image and a.scratch):
                raise Refusal("--execute needs --image and --scratch")
            print(execute(runtime=a.runtime, image=a.image, scratch=Path(a.scratch)))
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
