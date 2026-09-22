#!/usr/bin/env python3
# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""THE STATIC-ANCHOR TEST - PREPARED, NOT EXECUTED ON THE QMHP MESH WITHOUT APPROVAL.

What it measures
----------------
The electrostatic (Maxwell) self-capacitance ``C_h`` of the island conductor with every
other conductor grounded, on the committed N2R mesh and on one uniform red refinement of
it, by the Dirichlet principle: P1 potential ``phi`` = 1 on the island, 0 on ground,
minimising ``int eps |grad phi|^2``. Reported as

    S_h = 1 / ((2 pi)^2 L_F C_h)     [GHz^2]

- the first moment a single-node circuit with that capacitance and the declared ``L_F``
would have - so it can be set beside the band estimate ``a/N`` in the same units.

The same number is also computed a second way, as the first-moment Rayleigh quotient
restricted to curl-free fields, ``(f . G phi)^2 / ((G phi)^T M (G phi))``, with the SAME
``M`` and ``f`` the first-moment diagnostic uses. The two must agree to round-off; that is
the check that the static quantity really is the first-moment quotient with the port-face
content removed.

What it does NOT do
-------------------
It does not report ``E_C,F1F1``. It does not read, use or combine with any coupling ``g``,
readout frequency ``f_R`` or Route A output. It does not touch the first-moment diagnostic
or Route A. The outcome is decided by the frozen ``predeclaration.json`` alone.

Modes
-----
``--synthetic``   known-answer and control geometries, no QMHP data; runs freely.
``--preflight``   QMHP mesh digest, conductors, port bridging, problem sizes. No solve.
(default)         THE TEST. Refuses unless TEST-APPROVAL.json exists and binds the mesh,
                  the pre-declaration and this code by sha256. One attempt: the record
                  directory is created before any solve and its existence spends it.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import resource
import signal
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
import scipy.sparse.linalg as spla

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import anchor_fem as af  # noqa: E402

REPO = HERE.parents[1]
PREDECLARATION = HERE / "predeclaration.json"
APPROVAL = HERE / "TEST-APPROVAL.json"
RESULTS_ROOT = REPO / "results"
CODE_FILES = ("static_capacitance.py", "anchor_fem.py")


class Refusal(RuntimeError):
    """Raised instead of computing anything."""


# --- the measurement --------------------------------------------------------------------

def static_capacitance(mesh: dict, *, eps_r: dict, pec_attrs, port_attr: int, direction,
                       L0_m: float, L_H: float) -> dict:
    """C_h by the Dirichlet principle, and the same quantity as the curl-free-restricted
    first-moment quotient. Exactly two conductors are required and the port face must
    bridge them; with two conductors the capacitance is symmetric, so which one is held at
    1 does not change C_h."""
    comps = af.conductor_components(mesh, pec_attrs)
    if len(comps) != 2:
        raise Refusal(f"{len(comps)} conductors; the test is defined for exactly two")
    ground, island = comps[0], comps[1]                   # largest first
    sc = af.scales(mesh, L0_m, L_H)
    edges, t2e = af.edge_table(mesh)
    f_all, port = af.port_functional(mesh, sc["xyz_nd"], edges, port_attr, direction)
    pn = port["port_nodes"]
    if not (np.isin(pn, island).any() and np.isin(pn, ground).any()):
        raise Refusal("the port face does not bridge the two conductors")
    n = len(mesh["xyz"])
    used = np.unique(mesh["tets"])
    fixed = np.zeros(n, dtype=bool)
    fixed[island] = fixed[ground] = True
    free = used[~fixed[used]]
    phi = np.zeros(n)
    phi[island] = 1.0
    K = af.p1_stiffness(mesh, sc["xyz_nd"], eps_r)
    rhs = -(K[free][:, fixed] @ phi[fixed])
    Kff = K[free][:, free].tocsc()
    phi[free] = spla.spsolve(Kff, rhs)
    resid = float(np.linalg.norm(Kff @ phi[free] - rhs) / np.linalg.norm(rhs))
    energy = float(phi @ (K @ phi))                         # nondimensional int eps|grad phi|^2
    C = af.EPSILON0 * sc["Lc_m"] * energy                   # farads
    S = 1.0 / ((2.0 * math.pi) ** 2 * L_H * C) * 1e-18      # GHz^2
    # the same quantity on the edge space: curl-free restriction of the first-moment quotient
    M = af.whitney_mass(mesh, sc["xyz_nd"], edges, t2e, eps_r)
    pec = af.pec_edge_mask(mesh, edges, pec_attrs)
    gphi = af.gradient_matrix(edges, n) @ phi
    V = float(f_all @ gphi)
    e_edge = float(gphi @ (M @ gphi))
    S_edge = (V * V / e_edge) / sc["L_nd"] * sc["A_GHz2_per_nd"]
    return {
        "n_nodes": int(n), "n_unknowns": int(len(free)), "n_tets": int(len(mesh["tets"])),
        "island_nodes": int(len(island)), "ground_nodes": int(len(ground)),
        "C_F": C, "C_fF": C * 1e15, "S_GHz2": S, "energy_nd": energy,
        "Lc_m": sc["Lc_m"], "solve_relative_residual": resid,
        "identity": {
            "port_voltage_of_grad_phi": V,
            "grad_phi_on_pec_edges_max_abs": float(np.abs(gphi[pec]).max()) if pec.any() else 0.0,
            "edge_energy_vs_p1_energy_rel": abs(e_edge - energy) / energy,
            "S_edge_route_GHz2": S_edge,
            "S_two_routes_rel": abs(S_edge - S) / S,
        },
    }


# --- the frozen decision ----------------------------------------------------------------

def band_baseline(pre: dict) -> float:
    """a/N on the SAME base mesh, recomputed from the committed L2-rung columns exactly as
    the records sum them (all saved modes, |p|, N = sum |p|)."""
    b = pre["baseline"]["band_estimate_same_mesh"]
    post = REPO / b["postpro"]
    for name, digest in b["sha256"].items():
        if af.sha256(post / name) != digest:
            raise Refusal(f"{name} does not match its pinned digest")
    f = [float(r[1]) for r in list(csv.reader(open(post / "eig.csv")))[1:]]
    p = [abs(float(r[1])) for r in list(csv.reader(open(post / "port-EPR.csv")))[1:]]
    return sum(pi * fi * fi for pi, fi in zip(p, f)) / sum(p)


#: Every value an integrity check or the verdict reads. Each must be present and a finite
#: real number before any threshold is compared with it: a comparison with NaN is always
#: False, so an unchecked NaN would pass every "value > tolerance" test. Capacitance,
#: energy, S and the unit scale must also be strictly positive; residuals, errors and
#: magnitudes must be non-negative. None of this changes a threshold.
_POSITIVE = ("C_F", "C_fF", "S_GHz2", "energy_nd", "Lc_m")
_POSITIVE_IDENTITY = ("S_edge_route_GHz2",)
_NONNEGATIVE = ("solve_relative_residual",)
_NONNEGATIVE_IDENTITY = ("grad_phi_on_pec_edges_max_abs", "edge_energy_vs_p1_energy_rel",
                         "S_two_routes_rel")
_FINITE_IDENTITY = ("port_voltage_of_grad_phi",)


def _finite_real(v) -> bool:
    return (isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool)
            and math.isfinite(v))


def numerical_validity(levels, B0=None) -> list[str]:
    """Why the numbers cannot be read at all: missing, non-finite or non-physical values.
    Empty means every required value is present, finite and of the admissible sign."""
    if not isinstance(levels, list) or len(levels) != 2:
        n = len(levels) if isinstance(levels, list) else type(levels).__name__
        return [f"expected exactly the two declared levels, got {n}"]
    bad = []
    for i, r in enumerate(levels):
        if not isinstance(r, dict):
            bad.append(f"level {i}: not a record")
            continue
        if r.get("level") != i:
            bad.append(f"level {i}: level label is {r.get('level')!r}")
        idn = r.get("identity")
        if not isinstance(idn, dict):
            bad.append(f"level {i}: identity block is missing")
            idn = {}
        for block, keys, sign in ((r, _POSITIVE, "positive"),
                                  (idn, _POSITIVE_IDENTITY, "positive"),
                                  (r, _NONNEGATIVE, "non-negative"),
                                  (idn, _NONNEGATIVE_IDENTITY, "non-negative"),
                                  (idn, _FINITE_IDENTITY, None)):
            for key in keys:
                if key not in block:
                    bad.append(f"level {i}: {key} is missing")
                elif not _finite_real(block[key]):
                    bad.append(f"level {i}: {key} = {block[key]!r} is not a finite number")
                elif sign == "positive" and not block[key] > 0:
                    bad.append(f"level {i}: {key} = {block[key]!r} is not positive")
                elif sign == "non-negative" and not block[key] >= 0:
                    bad.append(f"level {i}: {key} = {block[key]!r} is negative")
    if B0 is not None and not (_finite_real(B0) and B0 > 0):
        bad.append(f"band baseline B0 = {B0!r} is not a finite positive number")
    return bad


def integrity(levels: list[dict], pre: dict, B0=None) -> list[str]:
    """Every failure makes the record UNQUALIFIED. None of these is a scientific outcome."""
    invalid = numerical_validity(levels, B0)
    if invalid:
        return invalid                      # no threshold is compared with an invalid number
    t = pre["integrity"]
    bad = []
    for r in levels:
        idn = r["identity"]
        if abs(abs(idn["port_voltage_of_grad_phi"]) - 1.0) > t["port_voltage_abs_tol"]:
            bad.append(f"level {r['level']}: port voltage of grad phi is not 1")
        if idn["grad_phi_on_pec_edges_max_abs"] > t["pec_edge_abs_tol"]:
            bad.append(f"level {r['level']}: grad phi is nonzero on a PEC edge")
        if idn["edge_energy_vs_p1_energy_rel"] > t["identity_rel_tol"]:
            bad.append(f"level {r['level']}: (G phi)^T M (G phi) != phi^T K phi")
        if idn["S_two_routes_rel"] > t["identity_rel_tol"]:
            bad.append(f"level {r['level']}: the two routes to S disagree")
        if r["solve_relative_residual"] > t["solve_residual_tol"]:
            bad.append(f"level {r['level']}: Dirichlet solve residual too large")
    if len(levels) == 2 and levels[1]["C_F"] > levels[0]["C_F"] * (1 + t["nested_monotone_rel_tol"]):
        bad.append("C increased under nested refinement, which the Dirichlet principle forbids")
    if levels and levels[0]["S_GHz2"] > t["S0_must_not_exceed_complete_moment_GHz2"]:
        bad.append("S0 exceeds the complete first moment measured on the same mesh")
    return bad


def decide(S0: float, S1: float, B0: float, pre: dict) -> dict:
    """The frozen outcome table. Pure function of three numbers and the pre-declaration."""
    w = pre["outcomes"]
    invalid = [f"{name} = {v!r} is not a finite positive number"
               for name, v in (("S0", S0), ("S1", S1), ("B0", B0))
               if not (_finite_real(v) and v > 0)]
    if invalid:                             # never a scientific verdict from invalid numbers
        return {"verdict": "UNQUALIFIED", "reason": "; ".join(invalid)}
    r0, rho = S0 / B0, S1 / S0
    if rho >= w["rho_weakens_at_or_above"]:
        verdict, why = "WEAKENS", "the static quantity grew like the divergent first moment"
    elif rho > w["rho_resolved_at_most"]:
        verdict, why = "UNRESOLVED", "the static quantity is not resolved on the base mesh"
    elif w["support_r0_min"] <= r0 <= w["support_r0_max"]:
        verdict, why = "SUPPORTS", "the band estimate tracks the static quantity"
    elif r0 > w["contradicts_r0_above"]:
        verdict, why = "CONTRADICTS", "the static quantity sits near the complete-moment scale"
    elif r0 < w["contradicts_r0_below"]:
        verdict, why = "CONTRADICTS", "the static quantity sits far below the band estimate"
    else:
        verdict, why = "WEAKENS", "the band estimate does not track the static quantity"
    return {"verdict": verdict, "reason": why, "r0": r0, "rho": rho, "B0_GHz2": B0,
            "lumped_one_sided_relation_S0_le_B0": S0 <= B0,
            "note": "r0 and rho are the only decisive numbers; the one-sided relation is "
                    "a reported diagnostic, never decisive"}


# --- synthetic controls (no QMHP data) --------------------------------------------------

def _slab(n: int, island_patch: bool) -> tuple[dict, dict]:
    """A 2 x 1 x 1 box: ground plane z=0, top conductor z=1 (whole face, or a patch
    x<1, 0.25<y<0.75 that reaches the x=0 wall), two dielectric layers split at z=0.5,
    and a port on the x=0 wall spanning ground to top within 0.25<y<0.75, direction +Z."""
    mesh = af.box_mesh(2 * n, n, n, size=(2.0, 1.0, 1.0))
    xyz = mesh["xyz"]
    cz = xyz[mesh["tets"]][:, :, 2].mean(1)
    mesh["tet_attr"] = np.where(cz < 0.5, 1, 3)
    c = xyz[mesh["tris"]].mean(1)
    on = lambda k, v: np.all(np.isclose(xyz[mesh["tris"]][:, :, k], v), axis=1)
    attr = np.zeros(len(c), dtype=int)
    attr[on(2, 0.0)] = 2
    top = on(2, 1.0)
    if island_patch:
        top &= (c[:, 0] < 1.0) & (c[:, 1] > 0.25) & (c[:, 1] < 0.75)
    attr[top] = 4
    attr[on(0, 0.0) & (c[:, 1] > 0.25) & (c[:, 1] < 0.75)] = 10
    mesh["tri_attr"] = attr
    model = {"eps_r": {1: 2.0, 3: 5.0}, "pec_attrs": (2, 4), "port_attr": 10,
             "direction": (0.0, 0.0, 1.0), "L0_m": 1.0e-3, "L_H": 1.0e-8}
    return mesh, model


def synthetic_controls(n: int = 4) -> dict:
    """(1) exact known answer: a full-face layered slab has a uniform field, which P1
    reproduces exactly, so C_h must equal eps0 A / (d1/e1 + d2/e2) at every resolution;
    (2) nested monotonicity with fringing: C_h must not increase under red refinement;
    (3) the negative control for the hypothesis: on the same slab the static quotient stays
    exact while the complete first moment f^T M^-1 f keeps growing under refinement."""
    out = {}
    exact = af.EPSILON0 * (2e-3 * 1e-3) / (0.5e-3 / 2.0 + 0.5e-3 / 5.0)
    rows = []
    mesh, model = _slab(n, island_patch=False)
    for level in (0, 1):
        r = static_capacitance(mesh, **model)
        s = af.assemble_edge_system(mesh, **model)
        x = spla.spsolve(s["M_free"].tocsc(), s["f_free"])
        A_complete = float(s["f_free"] @ x) / s["scales"]["L_nd"] * s["scales"]["A_GHz2_per_nd"]
        rows.append({"level": level, "C_rel_error_vs_exact": abs(r["C_F"] - exact) / exact,
                     "S_GHz2": r["S_GHz2"], "A_complete_GHz2": A_complete,
                     "identity": r["identity"]})
        mesh = af.refine_red(mesh)
    out["slab_exact"] = {"C_exact_F": exact, "rows": rows,
                         "complete_growth": rows[1]["A_complete_GHz2"] / rows[0]["A_complete_GHz2"],
                         "static_growth": rows[1]["S_GHz2"] / rows[0]["S_GHz2"]}
    mesh, model = _slab(n, island_patch=True)
    r0 = static_capacitance(mesh, **model)
    r1 = static_capacitance(af.refine_red(mesh), **model)
    out["fringe_nested"] = {"C0_F": r0["C_F"], "C1_F": r1["C_F"],
                            "C1_over_C0": r1["C_F"] / r0["C_F"],
                            "identities": [r0["identity"], r1["identity"]]}
    return out


# --- QMHP modes -------------------------------------------------------------------------

def _load_pre() -> dict:
    return json.loads(PREDECLARATION.read_text())


def _qmhp_mesh(pre: dict) -> tuple[dict, dict]:
    cfg = pre["configuration"]
    path = REPO / cfg["mesh"]
    if af.sha256(path) != cfg["mesh_sha256"]:
        raise Refusal("the mesh digest does not match the pre-declaration")
    model = {"eps_r": {int(k): v for k, v in cfg["eps_r"].items()},
             "pec_attrs": tuple(cfg["pec_attrs"]), "port_attr": cfg["port_attr"],
             "direction": tuple(cfg["direction"]), "L0_m": cfg["L0_m"], "L_H": cfg["L_H"]}
    return af.read_gmsh22(path), model


def preflight() -> dict:
    """Everything the test needs, checked without solving anything."""
    pre = _load_pre()
    mesh, model = _qmhp_mesh(pre)
    out = {"mesh_sha256": pre["configuration"]["mesh_sha256"], "levels": []}
    for level in (0, 1):
        comps = af.conductor_components(mesh, model["pec_attrs"])
        port_nodes = np.unique(mesh["tris"][mesh["tri_attr"] == model["port_attr"]])
        used = np.unique(mesh["tets"])
        fixed = np.zeros(len(mesh["xyz"]), dtype=bool)
        for c in comps:
            fixed[c] = True
        # The port voltage of grad(phi) depends only on phi along the face's two end lines,
        # which lie on the conductors. So ANY phi that is 1 on the island and 0 on ground -
        # the island indicator will do - must give exactly 1, with no solve. This checks the
        # integrity condition the test will apply, before the test is approved.
        sc = af.scales(mesh, model["L0_m"], model["L_H"])
        edges, _ = af.edge_table(mesh)
        f_all, _ = af.port_functional(mesh, sc["xyz_nd"], edges, model["port_attr"],
                                      model["direction"])
        indicator = np.zeros(len(mesh["xyz"]))
        indicator[comps[-1]] = 1.0
        g_ind = af.gradient_matrix(edges, len(mesh["xyz"])) @ indicator
        pec = af.pec_edge_mask(mesh, edges, model["pec_attrs"])
        out["levels"].append({
            "level": level, "n_tets": int(len(mesh["tets"])), "n_nodes": int(len(mesh["xyz"])),
            "n_conductors": len(comps), "conductor_nodes": [int(len(c)) for c in comps],
            "port_touches": [bool(np.isin(port_nodes, c).any()) for c in comps],
            "dirichlet_unknowns": int((~fixed[used]).sum()),
            "port_voltage_of_island_indicator": float(f_all @ g_ind),
            "indicator_gradient_on_pec_edges_max_abs": float(np.abs(g_ind[pec]).max())})
        if level == 0:
            mesh = af.refine_red(mesh)
    out["band_baseline_B0_GHz2"] = band_baseline(pre)
    out["band_baseline_matches_predeclaration"] = (
        abs(out["band_baseline_B0_GHz2"] - pre["baseline"]["band_estimate_same_mesh"]["value_GHz2"])
        <= 1e-12 * out["band_baseline_B0_GHz2"])
    return out


def require_approval(pre: dict) -> dict:
    if not APPROVAL.is_file():
        raise Refusal("no TEST-APPROVAL.json: the static-anchor test is PREPARED, NOT "
                      "APPROVED. A human grants it by writing the approval that binds the "
                      "mesh, the pre-declaration and this code by sha256.")
    ap = json.loads(APPROVAL.read_text())
    want = {"authorises": "one execution of the static-anchor test",
            "mesh_sha256": pre["configuration"]["mesh_sha256"],
            "predeclaration_sha256": af.sha256(PREDECLARATION),
            "code_sha256": {name: af.sha256(HERE / name) for name in CODE_FILES}}
    for key, value in want.items():
        if ap.get(key) != value:
            raise Refusal(f"approval {key} does not match: the reviewed state has changed")
    return ap


class BudgetExceeded(RuntimeError):
    """A declared budget limit was reached. The attempt is spent; the record says so."""


def _on_limit(signum, _frame):
    raise BudgetExceeded(f"{signal.Signals(signum).name}: a declared budget limit was reached")


def _require_enforceable_budget(pre: dict) -> None:
    """Refuse, before the attempt is spent, if this environment cannot apply the budget."""
    b = pre["budget"]
    wanted = {resource.RLIMIT_CPU: int(b["cpu_minutes"] * 60) + 60,
              resource.RLIMIT_AS: int(b["memory_GB"] * 1024 ** 3)}
    for rlim, value in wanted.items():
        hard = resource.getrlimit(rlim)[1]
        if hard != resource.RLIM_INFINITY and hard < value:
            raise Refusal(f"this environment's hard limit {hard} is below the declared "
                          f"budget {value}; the budget cannot be applied as declared")


def _enforce_budget(pre: dict) -> dict:
    """Make the pre-declared budget binding on this process.

    CPU: soft limit raises BudgetExceeded (SIGXCPU); the hard limit, 60 s later, is a kernel
    kill. Memory: the address-space limit makes an allocation beyond it fail (MemoryError).
    Wall: SIGALRM raises BudgetExceeded. Python handles signals between bytecodes, so a
    single native call is not interrupted mid-way; the approved command therefore also runs
    under an outer ``timeout`` hard kill."""
    b = pre["budget"]
    cpu_s = int(b["cpu_minutes"] * 60)
    mem_bytes = int(b["memory_GB"] * 1024 ** 3)
    wall_s = int(b["wall_cap_minutes"] * 60)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 60))
    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    signal.signal(signal.SIGXCPU, _on_limit)
    signal.signal(signal.SIGALRM, _on_limit)
    signal.alarm(wall_s)
    return {"cpu_s": cpu_s, "cpu_hard_kill_s": cpu_s + 60, "address_space_bytes": mem_bytes,
            "wall_s": wall_s}


def _usage(t0: float) -> dict:
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return {"wall_s": time.monotonic() - t0, "cpu_s": ru.ru_utime + ru.ru_stime,
            "max_rss_MB": ru.ru_maxrss / 1024.0}


def _environment() -> dict:
    return {"python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "platform": platform.platform(),
            "code_sha256": {name: af.sha256(HERE / name) for name in CODE_FILES}}


def execute() -> Path:
    t0 = time.monotonic()
    pre = _load_pre()
    approval = require_approval(pre)
    B0 = band_baseline(pre)                     # digests checked before any solve
    mesh, model = _qmhp_mesh(pre)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RESULTS_ROOT.mkdir(exist_ok=True)
    for existing in RESULTS_ROOT.glob("STATIC-ANCHOR-TEST-*"):
        raise Refusal(f"{existing.name} exists: the one attempt is spent")
    _require_enforceable_budget(pre)
    rec = RESULTS_ROOT / f"STATIC-ANCHOR-TEST-{stamp}"
    rec.mkdir(exist_ok=False)                   # spends the attempt before any solve
    limits = _enforce_budget(pre)
    levels = []
    try:
        for level in (0, 1):
            r = static_capacitance(mesh, **model)
            r["level"] = level
            r["resources_so_far"] = _usage(t0)
            levels.append(r)
            (rec / f"level{level}.json").write_text(json.dumps(r, indent=1) + "\n")  # raw first
            if level == 0:
                mesh = af.refine_red(mesh)
        signal.alarm(0)
        bad = integrity(levels, pre, B0)
        summary = {"predeclaration_sha256": af.sha256(PREDECLARATION),
                   "approval_sha256": af.sha256(APPROVAL),
                   "approval_run_label": approval.get("run_label"),
                   "mesh_sha256": pre["configuration"]["mesh_sha256"],
                   "band_baseline_B0_GHz2": B0,
                   "environment": _environment(), "limits": limits, "resources": _usage(t0),
                   "S0_GHz2": levels[0].get("S_GHz2"), "S1_GHz2": levels[1].get("S_GHz2"),
                   "C0_fF": levels[0].get("C_fF"), "C1_fF": levels[1].get("C_fF"),
                   "integrity_failures": bad,
                   "outcome": ({"verdict": "UNQUALIFIED", "reason": "; ".join(bad)} if bad
                               else decide(levels[0]["S_GHz2"], levels[1]["S_GHz2"], B0, pre)),
                   "not_reported": "E_C,F1F1 (see predeclaration.relation_to_registered_E_C); "
                                   "no coupling, readout frequency or Route A output is used"}
        (rec / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    except BaseException as exc:                # the failure is the recorded outcome
        signal.alarm(0)
        (rec / "failure.json").write_text(json.dumps({
            "verdict": "FAILED - the one attempt is spent; no retry",
            "levels_completed": [lv["level"] for lv in levels],
            "error": repr(exc), "traceback": traceback.format_exc(),
            "limits": limits, "resources": _usage(t0)}, indent=1) + "\n")
        raise
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--synthetic", action="store_true")
    g.add_argument("--preflight", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.synthetic:
            print(json.dumps(synthetic_controls(), indent=1, default=float))
        elif args.preflight:
            print(json.dumps(preflight(), indent=1))
        else:
            print(execute())
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except BudgetExceeded as exc:
        print(f"FAILED: {exc} (recorded in failure.json; no retry)", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
