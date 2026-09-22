#!/usr/bin/env python3
# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""THE STATIC-ONLY NESTED REFINEMENT STUDY - PREPARED, NOT APPROVED, NOT EXECUTED.

What it measures (predeclaration.json is the frozen statement; this is a summary)
------------------------------------------------------------------------------
On the committed N2R/L2 mesh (level 0) and its first and second uniform red refinements
(levels 1 and 2), two electrostatic capacitances of the island, by the Dirichlet
principle (nested_solver.py):

    C_h    island at 1, every other conductor at 0            (the static-anchor quantity)
    C'_h   the same, with the port-face potential also held linear along the port

and from them S_h = 1/((2 pi)^2 L_F C_h), delta_h = C'_h / C_h - 1 and, by the verified
sheet-port identity S_h = (1 + delta_h) H_h, H_h = 1/((2 pi)^2 L_F C'_h): the complete
harmonic moment Palace's pencil would have on that mesh (derived, not measured by Palace).

Levels 0 and 1 are solved directly (SuperLU), exactly as the executed static-anchor test,
whose C_0 and C_1 must be reproduced. Level 2 is solved by two-grid preconditioned
conjugate gradients; level 1 is ALSO solved that way as an in-run cross-check on the real
operator. Every energy carries a rigorous a-posteriori bound (nested_solver.certificate).

It does not report E_C,F1F1 or g, reads no Route A output, and combines nothing with them.

Modes
-----
``--preflight``  QMHP mesh, GEOMETRY AND ASSEMBLY ONLY: digests of levels 0-2, topology, the
                 certificate's and the identity's preconditions, Galerkin identities, sizes,
                 the certificate's round-off floor. No linear solve, no capacitance.
``--dry-run``    the exact execution path, on the QMHP-sized synthetic cell, under the
                 declared budget. No QMHP data.
(default)        THE STUDY. Refuses unless STUDY-APPROVAL.json binds the mesh, the
                 pre-declaration and every code file by sha256. One attempt: the record
                 directory is created before any solve and its existence spends it. Raw
                 levels are written as each completes; summary.json (or failure.json) next;
                 manifest.sha256 last, by orchestrator.manifest.write_verified, on every path.
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

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))
import nested_solver as ns  # noqa: E402
from orchestrator import manifest  # noqa: E402

af = ns.af
PREDECLARATION = HERE / "predeclaration.json"
APPROVAL = HERE / "STUDY-APPROVAL.json"
RESULTS_ROOT = REPO / "results"
RECORD_PREFIX = "STATIC-REFINEMENT-STUDY-"
CODE_FILES = {"study_driver.py": HERE / "study_driver.py",
              "nested_solver.py": HERE / "nested_solver.py",
              "anchor_fem.py": HERE.parent / "static-anchor-hypothesis" / "anchor_fem.py",
              "orchestrator/manifest.py": REPO / "orchestrator" / "manifest.py"}
LEVELS = (0, 1, 2)

#: The configuration. predeclaration.json repeats it and a test binds the two.
CONFIG = {
    "mesh": "results/COUPLED-LADDER-O1-L2-N2R-20260918T061455Z/L2/solver/coupled_chip_cell_L2.msh",
    "mesh_sha256": "d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428",
    "eps_r": {"1": 1.0, "3": 11.45}, "pec_attrs": [2, 4], "port_attr": 10,
    "direction": [0.0, 1.0, 0.0], "L0_m": 0.001, "L_H": 1.0345665367517793e-07,
}
#: The QMHP-sized synthetic stand-in for the dry run (synthetic_cells.chip_cell arguments).
DRY_RUN_CELL = {"h0": 0.02, "q": 1.6, "hmax": 0.5}


class Refusal(RuntimeError):
    """Raised instead of computing anything."""


class BudgetExceeded(RuntimeError):
    """A declared budget limit was reached. The attempt is spent; the record says so."""


class AttemptFailed(RuntimeError):
    """Anything that went wrong AFTER the record directory existed: the one attempt is spent,
    failure.json and a verified manifest are written, and nothing is retried. Distinct from
    Refusal, which is raised only before the attempt is spent."""


def _model(cfg: dict = CONFIG) -> dict:
    return {"eps_r": {int(k): v for k, v in cfg["eps_r"].items()},
            "pec_attrs": tuple(cfg["pec_attrs"]), "port_attr": cfg["port_attr"],
            "direction": tuple(cfg["direction"]), "L0_m": cfg["L0_m"], "L_H": cfg["L_H"]}


def _usage(t0: float) -> dict:
    ru = resource.getrusage(resource.RUSAGE_SELF)
    peak_vm = None
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmPeak:"):
                peak_vm = int(line.split()[1]) / 1024.0
    except OSError:
        pass
    return {"wall_s": time.monotonic() - t0, "cpu_s": ru.ru_utime + ru.ru_stime,
            "max_rss_MB": ru.ru_maxrss / 1024.0, "peak_address_space_MB": peak_vm}


# --- the execution path (shared by the study and the dry run) ----------------------------

def ladder(mesh0: dict) -> list[dict]:
    """Levels 0, 1, 2: the mesh and two uniform red refinements (anchor_fem.refine_red)."""
    meshes = [mesh0]
    for _ in LEVELS[1:]:
        meshes.append(af.refine_red(meshes[-1]))
    return meshes


_CROSS_KEYS = ("energy_nd", "total_error_bound_nd", "total_error_bound_rel", "C_fF",
               "port_voltage", "cpu_s", "wall_s")


def run_levels(meshes: list[dict], model: dict, write, t0: float,
               levels: list | None = None) -> list[dict]:
    """Solve both problems on every level, writing each level's raw record as it completes.
    Completed levels are appended to ``levels`` as they finish, so a caller that passes its
    own list still sees them if a later level raises."""
    levels = [] if levels is None else levels
    prev, prev_phi = None, {}
    for h, mesh in zip(LEVELS, meshes):
        L = ns.Level(mesh, model)
        bf = ns.boundary_facts(mesh)
        geo = L.dd["C"]["geo"]
        rec = {"level": h, "mesh_digest": ns.mesh_digest(mesh), "n_tets": int(len(mesh["tets"])),
               "n_nodes": int(len(mesh["xyz"])),
               "conductor_nodes": [int(len(L.dd["C"]["ground"])), int(len(L.dd["C"]["island"]))],
               "boundary": {k: bf[k] for k in ("max_face_multiplicity", "boundary_faces",
                                               "every_boundary_face_is_tagged")},
               "preconditions_failed": ns.certificate_preconditions(L, bf),
               "poincare": L.poincare,
               "port": {k: geo[k] for k in geo if k not in ("port_nodes", "t")},
               "problems": {}}
        del bf
        phis = {}
        for kind in ns.KINDS:
            method = "direct" if h < 2 else "twogrid"
            r, phi = ns.solve(L, kind, method, coarse=prev, coarse_phi=prev_phi.get(kind))
            if h == 1:
                rx, _ = ns.solve(L, kind, "twogrid", coarse=prev, coarse_phi=prev_phi[kind])
                r["twogrid_cross_check"] = {**{k: rx[k] for k in _CROSS_KEYS},
                                            "solver": rx["solver"]}
            rec["problems"][kind] = r
            phis[kind] = phi
        rec["resources_so_far"] = _usage(t0)
        write(h, rec)
        levels.append(rec)
        prev, prev_phi = L, phis
    return levels


# --- the frozen analysis ---------------------------------------------------------------

def _finite_real(v) -> bool:
    return (isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool)
            and math.isfinite(v))


def numerical_validity(levels) -> list[str]:
    """Missing, non-finite or non-physical values. Empty means every required value is
    present, finite and of the admissible sign; nothing is compared with a threshold first."""
    if not isinstance(levels, list) or len(levels) != len(LEVELS):
        n = len(levels) if isinstance(levels, list) else type(levels).__name__
        return [f"expected exactly the {len(LEVELS)} declared levels, got {n}"]
    bad = []
    for h, lv in zip(LEVELS, levels):
        if not isinstance(lv, dict) or lv.get("level") != h:
            bad.append(f"level {h}: missing or mislabelled")
            continue
        probs = lv.get("problems")
        if not isinstance(probs, dict):
            bad.append(f"level {h}: no problems block")
            continue
        for kind in ns.KINDS:
            r = probs.get(kind)
            if not isinstance(r, dict):
                bad.append(f"level {h} {kind}: missing")
                continue
            blocks = [(f"{kind}", r)]
            if h == 1:
                x = r.get("twogrid_cross_check")
                if not isinstance(x, dict):
                    bad.append(f"level 1 {kind}: cross-check missing")
                else:
                    blocks.append((f"{kind} cross-check", x))
            for name, b in blocks:
                for key in ("energy_nd", "C_fF"):
                    v = b.get(key)
                    if not (_finite_real(v) and v > 0):
                        bad.append(f"level {h} {name}: {key} = {v!r} is not a finite positive number")
                for key in ("total_error_bound_nd", "total_error_bound_rel"):
                    v = b.get(key)
                    if not (_finite_real(v) and v >= 0):
                        bad.append(f"level {h} {name}: {key} = {v!r} is not a finite non-negative number")
                if not _finite_real(b.get("port_voltage")):
                    bad.append(f"level {h} {name}: port_voltage = {b.get('port_voltage')!r}")
            if not (_finite_real(r.get("S_GHz2")) and r["S_GHz2"] > 0):
                bad.append(f"level {h} {kind}: S_GHz2 = {r.get('S_GHz2')!r}")
    return bad


def _solver_problems(tag: str, solver: dict, t: dict) -> list[str]:
    bad = []
    if solver.get("method") != "twogrid":
        return bad
    if solver.get("status") != "CERTIFIED":
        bad.append(f"{tag}: two-grid status {solver.get('status')!r}")
    g = solver.get("galerkin_identity_rel")
    if not (_finite_real(g) and g <= t["galerkin_identity_rel_tol"]):
        bad.append(f"{tag}: Galerkin identity {g!r}")
    if solver.get("fixed_rows_from_free_coarse_nnz") != 0:
        bad.append(f"{tag}: the coarse homogeneous space leaks into constrained fine nodes")
    return bad


def integrity(levels, pre: dict, anchor: dict | None) -> list[str]:
    """Every failure makes the record UNQUALIFIED. None of these is a scientific outcome."""
    invalid = numerical_validity(levels)
    if invalid:
        return invalid                        # no threshold is compared with an invalid number
    t = pre["integrity"]
    bad = []
    want = pre["configuration"]["level_mesh_digests"]
    for h, lv in zip(LEVELS, levels):
        if lv["mesh_digest"] != want[str(h)]:
            bad.append(f"level {h}: mesh digest differs from the pre-declared one")
        bad += [f"level {h}: {p}" for p in lv["preconditions_failed"]]
        for kind in ns.KINDS:
            r = lv["problems"][kind]
            if r["total_error_bound_rel"] > t["certificate_rel_tol"]:
                bad.append(f"level {h} {kind}: certified error {r['total_error_bound_rel']!r} "
                           f"exceeds {t['certificate_rel_tol']}")
            if abs(r["port_voltage"] - 1.0) > t["port_voltage_abs_tol"]:
                bad.append(f"level {h} {kind}: port voltage {r['port_voltage']!r} is not 1")
            bad += _solver_problems(f"level {h} {kind}", r["solver"], t)
            if h == 1:
                x = r["twogrid_cross_check"]
                bad += _solver_problems(f"level 1 {kind} cross-check", x["solver"], t)
                if x["total_error_bound_rel"] > t["certificate_rel_tol"]:
                    bad.append(f"level 1 {kind} cross-check: certified error "
                               f"{x['total_error_bound_rel']!r}")
                if abs(x["energy_nd"] - r["energy_nd"]) > (x["total_error_bound_nd"]
                                                          + r["total_error_bound_nd"]):
                    bad.append(f"level 1 {kind}: direct and two-grid disagree beyond their bounds")
        # C' >= C on every level (more constraints), within the two bounds
        e, ep = lv["problems"]["C"], lv["problems"]["Cprime"]
        if ep["energy_nd"] < e["energy_nd"] - e["total_error_bound_nd"] - ep["total_error_bound_nd"]:
            bad.append(f"level {h}: C' < C, which more constraints forbid")
    for kind in ns.KINDS:                      # nested refinement cannot raise the energy
        for h in LEVELS[1:]:
            a, b = levels[h - 1]["problems"][kind], levels[h]["problems"][kind]
            if b["energy_nd"] > a["energy_nd"] + a["total_error_bound_nd"] + b["total_error_bound_nd"]:
                bad.append(f"{kind}: energy rose from level {h - 1} to {h}, which nesting forbids")
    if anchor is not None:                     # the executed record must be reproduced
        for h in (0, 1):
            new, old = levels[h]["problems"]["C"]["C_F"], anchor[f"C{h}_F"]
            if abs(new - old) > t["reproduction_rel_tol"] * old:
                bad.append(f"level {h}: C_h {new!r} does not reproduce the executed static-anchor "
                           f"record {old!r}")
    return bad


def _interval(lv: dict, kind: str) -> tuple[float, float, float]:
    r = lv["problems"][kind]
    return r["energy_nd"], r["energy_nd"] - r["total_error_bound_nd"], r["energy_nd"] + r["total_error_bound_nd"]


def classify(values, lows, highs, w: dict, *, signed: bool = False) -> dict:
    """The frozen convergence rule for a three-level sequence X_0, X_1, X_2 (predeclaration
    'classification'). d1 = X0 - X1, d2 = X1 - X2, R = d1 / d2; each X_h is known only to
    lie in [low_h, high_h] (its certificate), and the rule is applied to those ranges.

    UNRESOLVED      a difference within its certified error of zero; differences of opposite
                    sign that shrink (oscillation); R outside [R_min, R_max] but above 1; or
                    the certified range of R straddling a class edge (1, R_min, R_max).
    NON-CONVERGENT  |d2| >= |d1|: the differences do not shrink.
    CONVERGING      R_min <= R <= R_max: consistent with leading order 1 plus higher orders up
                    to 2 with coefficients of one sign. The limit is bracketed, MODEL-BASED and
                    not rigorous, by X2 - d2 (order 1) and X2 - d2 / (R - 1) (observed order).
    CONVERGED       CONVERGING and |d2| / |X2 - d2| <= tau (the bracket's conservative end).
    UNQUALIFIED     (monotone sequences) a difference certainly negative: nesting forbids it.
    """
    X0, X1, X2 = values
    d1, d2 = X0 - X1, X1 - X2
    d1r = (lows[0] - highs[1], highs[0] - lows[1])
    d2r = (lows[1] - highs[2], highs[1] - lows[2])
    out = {"values": list(values), "d1": d1, "d2": d2,
           "d1_certified_range": list(d1r), "d2_certified_range": list(d2r)}
    if not signed and (d1r[1] < 0 or d2r[1] < 0):
        return {**out, "cls": "UNQUALIFIED", "reason": "a difference is negative, which nesting forbids"}
    if d1r[0] <= 0 <= d1r[1] or d2r[0] <= 0 <= d2r[1]:
        return {**out, "cls": "UNRESOLVED", "reason": "a difference is within its certified error of zero"}
    if (d1 > 0) != (d2 > 0):
        if abs(d2) >= abs(d1):
            return {**out, "cls": "NON-CONVERGENT", "reason": "the differences do not shrink"}
        return {**out, "cls": "UNRESOLVED", "reason": "the differences change sign (oscillation)"}
    a1 = sorted(abs(v) for v in d1r)
    a2 = sorted(abs(v) for v in d2r)
    R, Rs = d1 / d2, [a1[0] / a2[1], a1[1] / a2[0]]
    out.update(R=R, R_certified_range=Rs, p_obs=math.log2(R))
    if any(Rs[0] <= e <= Rs[1] for e in (1.0, w["R_min"], w["R_max"])):
        return {**out, "cls": "UNRESOLVED", "reason": "R is within its certified error of a class edge"}
    if R < 1.0:
        return {**out, "cls": "NON-CONVERGENT", "reason": "the differences do not shrink"}
    if R < w["R_min"]:
        return {**out, "cls": "UNRESOLVED", "reason": "slower than the theoretical leading order 1"}
    if R > w["R_max"]:
        return {**out, "cls": "UNRESOLVED", "reason": "faster than any order a P1 energy error can have"}
    lim1, lim_obs = X2 - d2, X2 - d2 / (R - 1.0)
    remaining_hi = abs(d2) / abs(lim1)
    out.update(limit_bracket_model_based=sorted([lim1, lim_obs]),
               remaining_rel_error_at_level2_bracket=[abs(d2) / (R - 1.0) / abs(lim_obs), remaining_hi])
    if remaining_hi <= w["tau_converged"]:
        return {**out, "cls": "CONVERGED", "reason": "rate consistent with theory; level 2 within tau"}
    return {**out, "cls": "CONVERGING", "reason": "rate consistent with theory; level 2 not yet within tau"}


def band_baseline(pre: dict) -> dict:
    """The committed L2 band, same mesh as level 0, from its pinned columns."""
    b = pre["consistency_check"]["band"]
    post = REPO / b["postpro"]
    for name, digest in b["sha256"].items():
        if af.sha256(post / name) != digest:
            raise Refusal(f"{name} does not match its pinned digest")
    rows = lambda f: list(csv.reader(open(post / f)))[1:]
    f = np.array([float(r[1]) for r in rows("eig.csv")])
    p = np.abs(np.array([float(r[1]) for r in rows("port-EPR.csv")]))
    return {"sum_p_over_f2_GHz-2": float((p / f ** 2).sum()), "N_B": float(p.sum()),
            "f_max_GHz": float(f.max()), "H_band_GHz2": float(1.0 / (p / f ** 2).sum()),
            "modes": int(len(f))}


def anchor_values(pre: dict) -> dict:
    a = pre["reproduction"]
    root = REPO / a["record"]
    for name, digest in a["sha256"].items():
        if af.sha256(root / name) != digest:
            raise Refusal(f"{a['record']}/{name} does not match its pinned digest")
    return {f"C{h}_F": json.loads((root / f"level{h}.json").read_text())["C_F"] for h in (0, 1)}


def consistency(levels, pre: dict, band: dict) -> dict:
    """The level-0 cross-code check (predeclaration 'consistency_check'). Not an acceptance
    criterion: it decides only whether H_h may be read as Palace's complete harmonic moment."""
    c = pre["consistency_check"]
    E, El, Eh = _interval(levels[0], "C")
    Ep, Epl, Eph = _interval(levels[0], "Cprime")
    delta, lo, hi = Ep / E - 1.0, Epl / Eh - 1.0, Eph / El - 1.0
    S0 = levels[0]["problems"]["C"]["S_GHz2"]
    d_band = S0 * band["sum_p_over_f2_GHz-2"] - 1.0
    tail = S0 * (1.0 - band["N_B"]) / band["f_max_GHz"] ** 2
    w = [d_band - c["eta"], d_band + tail + c["eta"]]
    if w[0] <= lo and hi <= w[1]:
        verdict = "CONSISTENT"
    elif hi < w[0]:
        verdict = "INCONSISTENT-LOW"
    elif lo > w[1]:
        verdict = "INCONSISTENT-HIGH"
    else:
        verdict = "UNRESOLVED"
    return {"verdict": verdict, "delta0": delta, "delta0_certified_range": [lo, hi],
            "delta_band_lower": d_band, "tail_bound": tail, "window": w,
            "H0_static_GHz2": levels[0]["problems"]["Cprime"]["S_GHz2"],
            "H_band_GHz2": band["H_band_GHz2"],
            "meaning": c["consequence"][verdict]}


def analyse(levels, pre: dict, band: dict | None, anchor: dict | None) -> dict:
    bad = integrity(levels, pre, anchor)
    out = {"integrity_failures": bad}
    if bad:
        out["outcome"] = {"verdict": "UNQUALIFIED", "reason": "; ".join(bad)}
        return out
    w = pre["classification"]
    cls = {}
    for kind in ns.KINDS:
        iv = [_interval(lv, kind) for lv in levels]
        cls[kind] = classify([v[0] for v in iv], [v[1] for v in iv], [v[2] for v in iv], w)
    # delta = C'/C - 1 on each level, with its certified range
    dv, dl, dh = [], [], []
    for lv in levels:
        E, El, Eh = _interval(lv, "C")
        Ep, Epl, Eph = _interval(lv, "Cprime")
        dv.append(Ep / E - 1.0); dl.append(Epl / Eh - 1.0); dh.append(Eph / El - 1.0)
    cls["delta"] = classify(dv, dl, dh, w, signed=True)
    cls["delta"]["max_delta"] = max(dv)
    cls["delta"]["S_and_H_within_1_percent_on_every_level"] = bool(max(dv) <= w["delta_small"])
    unit = lambda kind: levels[0]["problems"][kind]["S_GHz2"] * levels[0]["problems"][kind]["energy_nd"]
    for kind, name in (("C", "S"), ("Cprime", "H")):
        k = unit(kind)                         # S = k / E on every level (same L_F and Lc)
        c = cls[kind]
        r2 = levels[2]["problems"][kind]
        cls[name] = {"cls": c["cls"], "values_GHz2": [lv["problems"][kind]["S_GHz2"] for lv in levels],
                     "rigorous_lower_bound_GHz2": r2["S_GHz2"] / (1.0 + r2["total_error_bound_rel"])}
        if "limit_bracket_model_based" in c:
            cls[name]["limit_bracket_model_based_GHz2"] = sorted(k / e for e in c["limit_bracket_model_based"])
    for kind in ns.KINDS:                      # C <= C_2 (Dirichlet principle), widened by its bound
        r2 = levels[2]["problems"][kind]
        cls[kind]["rigorous_upper_bound_fF"] = r2["C_fF"] * (1.0 + r2["total_error_bound_rel"])
    out["classes"] = cls
    out["consistency_check"] = (consistency(levels, pre, band) if band is not None
                                else "not applicable (synthetic dry run)")
    out["outcome"] = {"verdict": "QUALIFIED", "C": cls["C"]["cls"], "Cprime_and_H": cls["Cprime"]["cls"],
                      "delta": cls["delta"]["cls"],
                      "consistency_check": (out["consistency_check"]["verdict"]
                                            if band is not None else None)}
    return out


# --- QMHP modes -------------------------------------------------------------------------

def load_pre() -> dict:
    return json.loads(PREDECLARATION.read_text())


def qmhp_mesh(cfg: dict = CONFIG) -> dict:
    path = REPO / cfg["mesh"]
    if af.sha256(path) != cfg["mesh_sha256"]:
        raise Refusal("the mesh digest does not match the configuration")
    return af.read_gmsh22(path)


def _preflight_level(L: "ns.Level", bf: dict, prev: "ns.Level | None", Pfull) -> dict:
    out = {"mesh_digest": ns.mesh_digest(L.mesh), "n_tets": int(len(L.mesh["tets"])),
           "n_nodes": int(len(L.mesh["xyz"])),
           "boundary": {k: bf[k] for k in ("max_face_multiplicity", "boundary_faces",
                                           "every_boundary_face_is_tagged")},
           "preconditions_failed": ns.certificate_preconditions(L, bf),
           "poincare": L.poincare, "element_quality": ns.element_quality(L.mesh, L.xyz),
           "port": {k: v for k, v in L.dd["C"]["geo"].items() if k not in ("port_nodes", "t")},
           "problems": {}}
    for kind in ns.KINDS:
        dd = L.dd[kind]
        sysm = ns.system(L.K, dd)
        A = sysm["A"]
        # the certificate's floor if the solve were exact, with |x| <= 1 as the proxy
        kA = int(np.diff(A.indptr).max())
        g = (ns.gamma(kA + 1) * (np.abs(sysm["b"]) + abs(A) @ np.ones(A.shape[0]))
             + ns.gamma(int(np.diff(sysm["KfD"].indptr).max())) * (abs(sysm["KfD"]) @ np.abs(sysm["phiD"])))
        row = {"n_unknowns": int(A.shape[0]), "nnz_A": int(A.nnz),
               "n_port_nodes_constrained_off_conductors": int(dd["fixed"].sum()
                                                              - L.dd["C"]["fixed"].sum()),
               "certificate_floor_nd": ns.BOUND_SAFETY * float((g * g / L.m[dd["free"]]).sum())
               / L.poincare["c"]}
        if prev is not None:
            cd = prev.dd[kind]
            leak = Pfull[np.flatnonzero(dd["fixed"])][:, cd["free"]]
            P = Pfull[dd["free"]][:, cd["free"]].tocsr()
            Ac = P.T @ A @ P
            Acoarse = prev.K[cd["free"]][:, cd["free"]]
            row["galerkin_identity_rel"] = float(abs(Ac - Acoarse).max() / abs(Acoarse).max())
            row["fixed_rows_from_free_coarse_nnz"] = int(leak.nnz)
        out["problems"][kind] = row
    return out


def preflight() -> dict:
    """Geometry and assembly only. No linear solve; no capacitance is computed."""
    t0 = time.monotonic()
    ns.require_extended_precision()
    model = _model()
    meshes = ladder(qmhp_mesh())
    out = {"mesh_sha256": CONFIG["mesh_sha256"], "linear_solves": 0, "levels": {}}
    prev = None
    for h, mesh in zip(LEVELS, meshes):
        L = ns.Level(mesh, model)
        bf = ns.boundary_facts(mesh)
        Pfull = ns.prolongation(meshes[h - 1], mesh) if h else None
        out["levels"][str(h)] = _preflight_level(L, bf, prev, Pfull)
        prev = L
    out["resources"] = _usage(t0)
    out["environment"] = _environment(EVIDENCE_CODE)
    return out


def require_approval(pre: dict) -> dict:
    if not APPROVAL.is_file():
        raise Refusal("no STUDY-APPROVAL.json: the static-only nested refinement study is "
                      "PREPARED, NOT APPROVED. A human grants it by writing the approval that "
                      "binds the mesh, the pre-declaration and every code file by sha256.")
    ap = json.loads(APPROVAL.read_text())
    want = {"authorises": "one execution of the static-only nested refinement study",
            "mesh_sha256": CONFIG["mesh_sha256"],
            "predeclaration_sha256": af.sha256(PREDECLARATION),
            "code_sha256": {name: af.sha256(path) for name, path in CODE_FILES.items()}}
    for key, value in want.items():
        if ap.get(key) != value:
            raise Refusal(f"approval {key} does not match: the reviewed state has changed")
    return ap


def _on_limit(signum, _frame):
    raise BudgetExceeded(f"{signal.Signals(signum).name}: a declared budget limit was reached")


def _require_enforceable_budget(pre: dict) -> None:
    b = pre["budget"]
    wanted = {resource.RLIMIT_CPU: int(b["cpu_minutes"] * 60) + 60,
              resource.RLIMIT_AS: int(b["memory_GB"] * 1024 ** 3)}
    for rlim, value in wanted.items():
        hard = resource.getrlimit(rlim)[1]
        if hard != resource.RLIM_INFINITY and hard < value:
            raise Refusal(f"this environment's hard limit {hard} is below the declared "
                          f"budget {value}; the budget cannot be applied as declared")


def _enforce_budget(pre: dict) -> dict:
    """CPU: SIGXCPU raises BudgetExceeded, the hard limit 60 s later is a kernel kill.
    Memory: RLIMIT_AS makes an allocation beyond it fail. Wall: SIGALRM raises. Python
    handles signals between bytecodes, so the approved command also carries an outer
    ``timeout`` hard kill."""
    b = pre["budget"]
    cpu_s, wall_s = int(b["cpu_minutes"] * 60), int(b["wall_cap_minutes"] * 60)
    mem = int(b["memory_GB"] * 1024 ** 3)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 60))
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
    signal.signal(signal.SIGXCPU, _on_limit)
    signal.signal(signal.SIGALRM, _on_limit)
    signal.alarm(wall_s)
    return {"cpu_s": cpu_s, "cpu_hard_kill_s": cpu_s + 60, "address_space_bytes": mem,
            "wall_s": wall_s}


#: every file whose code produced the committed preparation evidence
EVIDENCE_CODE = {**CODE_FILES, "synthetic_cells.py": HERE / "synthetic_cells.py",
                 "verify_solver.py": HERE / "verify_solver.py"}


def _environment(files: dict = CODE_FILES) -> dict:
    return {"python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "platform": platform.platform(),
            "longdouble_eps": float(np.finfo(np.longdouble).eps),
            "code_sha256": {name: af.sha256(path) for name, path in files.items()}}


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1, default=float) + "\n")


def execute(results_root: Path | None = None) -> Path:
    t0 = time.monotonic()
    results_root = RESULTS_ROOT if results_root is None else results_root
    pre = load_pre()
    approval = require_approval(pre)
    ns.require_extended_precision()
    band = band_baseline(pre)                  # digests checked before anything is spent
    anchor = anchor_values(pre)
    meshes = ladder(qmhp_mesh())
    digests = {str(h): ns.mesh_digest(m) for h, m in zip(LEVELS, meshes)}
    if digests != pre["configuration"]["level_mesh_digests"]:
        raise Refusal("a refined mesh differs from the pre-declared one")
    results_root.mkdir(exist_ok=True)
    for existing in results_root.glob(RECORD_PREFIX + "*"):
        raise Refusal(f"{existing.name} exists: the one attempt is spent")
    _require_enforceable_budget(pre)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rec = results_root / f"{RECORD_PREFIX}{stamp}"
    rec.mkdir(exist_ok=False)                  # spends the attempt before any solve
    limits = _enforce_budget(pre)
    levels: list = []
    try:
        run_levels(meshes, _model(), lambda h, r: _dump(rec / f"level{h}.json", r), t0, levels)
        signal.alarm(0)
        summary = {"predeclaration_sha256": af.sha256(PREDECLARATION),
                   "approval_sha256": af.sha256(APPROVAL),
                   "approval_run_label": approval.get("run_label"),
                   "mesh_sha256": CONFIG["mesh_sha256"], "level_mesh_digests": digests,
                   "band_baseline": band, "static_anchor_values": anchor,
                   "environment": _environment(), "limits": limits, "resources": _usage(t0),
                   "C_fF": [lv["problems"]["C"]["C_fF"] for lv in levels],
                   "Cprime_fF": [lv["problems"]["Cprime"]["C_fF"] for lv in levels],
                   **analyse(levels, pre, band, anchor),
                   "not_reported": "E_C,F1F1 and g; no coupling, readout frequency or Route A "
                                   "output is read or combined"}
        _dump(rec / "summary.json", summary)
    except BaseException as exc:               # the failure is the recorded outcome
        signal.alarm(0)
        _dump(rec / "failure.json", {
            "verdict": "FAILED - the one attempt is spent; no retry",
            "levels_completed": [lv["level"] for lv in levels], "error": repr(exc),
            "traceback": traceback.format_exc(), "limits": limits, "resources": _usage(t0)})
        manifest.write_verified(rec)
        raise AttemptFailed(f"{rec.name}: {exc!r} (recorded in failure.json; the one attempt "
                            "is spent; no retry)") from exc
    manifest.write_verified(rec)
    return rec


def dry_run(budget: dict | None = None) -> dict:
    """The execution path on the QMHP-sized synthetic cell, optionally under a budget."""
    import synthetic_cells as syn  # noqa: PLC0415 - synthetic only
    t0 = time.monotonic()
    limits = _enforce_budget({"budget": budget}) if budget else None
    mesh, model = syn.chip_cell(**DRY_RUN_CELL)
    quality = ns.element_quality(mesh, af.scales(mesh, model["L0_m"], model["L_H"])["xyz_nd"])
    levels = run_levels(ladder(mesh), model, lambda h, r: None, t0)
    signal.alarm(0)
    pre = {"integrity": load_pre()["integrity"], "classification": load_pre()["classification"],
           "configuration": {"level_mesh_digests": {str(lv["level"]): lv["mesh_digest"] for lv in levels}}}
    per_iteration = {}
    for kind in ns.KINDS:
        sv = levels[2]["problems"][kind]["solver"]
        hist = sv["history_iter_residual_relcert_wall"]
        per_iteration[kind] = {"setup_wall_s": sv["setup_wall_s"],
                               "iterations": sv["iterations"],
                               "pcg_wall_s": hist[-1][3],
                               "wall_s_per_iteration": hist[-1][3] / max(1, sv["iterations"])}
    return {"cell": DRY_RUN_CELL, "element_quality_level0": quality,
            "level2_pcg_timing": per_iteration, "limits": limits, "resources": _usage(t0),
            "per_level": [{"level": lv["level"], "n_tets": lv["n_tets"], "n_nodes": lv["n_nodes"],
                           "resources_so_far": lv["resources_so_far"],
                           "problems": {k: {"n_unknowns": r["n_unknowns"], "C_fF": r["C_fF"],
                                            "bound_rel": r["total_error_bound_rel"],
                                            "solver": {kk: r["solver"].get(kk) for kk in
                                                       ("method", "status", "iterations",
                                                        "galerkin_identity_rel")},
                                            "cross_check": ({kk: r["twogrid_cross_check"]["solver"].get(kk)
                                                             for kk in ("status", "iterations")}
                                                            if "twogrid_cross_check" in r else None),
                                            "cpu_s": r["cpu_s"], "wall_s": r["wall_s"]}
                                        for k, r in lv["problems"].items()}}
                          for lv in levels],
            "analysis_of_the_synthetic_levels": analyse(levels, pre, None, None),
            "environment": _environment(EVIDENCE_CODE), "qmhp_data_read": False}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    try:
        if args.preflight:
            res = preflight()
        elif args.dry_run:
            res = dry_run(load_pre()["budget"])
        else:
            print(execute())
            return 0
        text = json.dumps(res, indent=1, default=float)
        if args.out:
            Path(args.out).write_text(text + "\n")
        print(text)
    except AttemptFailed as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 3
    except (Refusal, ns.Refusal) as exc:
        print(f"REFUSED (nothing spent): {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
