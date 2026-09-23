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

and from them S_h = 1/((2 pi)^2 L_F C_h), delta_h = C'_h / C_h - 1 and
S'_h = 1/((2 pi)^2 L_F C'_h). Under the sheet-port identity (verified on the project's own
dense-pencil model of Palace's port, not yet against Palace), S'_h = H_h would be the
complete harmonic moment Palace's pencil has on that mesh. The level-0 consistency check
is the first test of that identity against Palace's own eigensolver; the second moment is
reported under the name H only if that check is CONSISTENT.

Levels 0 and 1 are solved directly (SuperLU), exactly as the executed static-anchor test,
whose C_0 and C_1 must be reproduced. Level 2 is solved by two-grid preconditioned
conjugate gradients; level 1 is ALSO solved that way as an in-run cross-check on the real
operator. Every energy carries a rigorous a-posteriori bound relative to the assembled
operator (nested_solver.certificate and nested_solver.energy).

It does not report E_C,F1F1 or g, reads no Route A output, and combines nothing with them.

Modes
-----
``--preflight``  QMHP mesh, GEOMETRY AND ASSEMBLY ONLY: digests of levels 0-2, topology, the
                 tiling, certificate and identity preconditions, Galerkin identities, sizes,
                 round-off proxies. No linear solve, no capacitance.
``--dry-run``    the solve path (run_levels) and its per-solve evidence writes on the
                 QMHP-sized synthetic cell, under the declared budget, into a scratch
                 directory sealed by write_verified. The approval, the ledger, provenance,
                 the level-0 check and the summary are not exercised. No QMHP data.
(default)        THE STUDY. Refuses unless STUDY-APPROVAL.json binds the mesh, the
                 pre-declaration, every executed code file, the environment, the declared
                 invocation, the approved commit, this checkout and a validity window. One
                 attempt, spent before any solve by three ledger entries: a marker in the
                 git common directory (which no checkout touches), ATTEMPT-SPENT.json, and
                 the approval itself, renamed to STUDY-APPROVAL.consumed.json. Then
                 provenance.json, each solve's raw result as it completes, summary.json (or
                 failure.json), and manifest.sha256 by orchestrator/manifest.py's
                 write_verified. A signal raises once; every later one is recorded and
                 ignored, so the failure path completes. A kernel or outer SIGKILL (the hard
                 CPU limit, the outer timeout, the OOM killer) cannot be caught: it leaves the
                 spent record with no failure.json and no manifest, to be quarantined by
                 content.
"""
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import resource
import signal
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import scipy

_T_START = time.monotonic()
#: As the study, every repository module is compiled from its source: bytecode caches are
#: neither read (the prefix cannot exist) nor written, so the digests the approval binds
#: are of the code that runs. invocation_problems() checks that this is in force.
NO_BYTECODE_CACHE = "/dev/null/qmhp-no-bytecode-cache"
if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.pycache_prefix = NO_BYTECODE_CACHE
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import nested_solver as ns  # noqa: E402

af = ns.af


def _load_by_path(name: str, path: Path):
    """Load one repository module without executing its package __init__, so that exactly
    the files the approval binds are the repository code this process runs."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


manifest = _load_by_path("qmhp_orchestrator_manifest", REPO / "orchestrator" / "manifest.py")

PREDECLARATION = HERE / "predeclaration.json"
APPROVAL = HERE / "STUDY-APPROVAL.json"
#: the approval, renamed when the attempt is spent, so no later checkout holds a usable one
APPROVAL_CONSUMED = HERE / "STUDY-APPROVAL.consumed.json"
ATTEMPT_MARKER = HERE / "ATTEMPT-SPENT.json"
#: the ledger entry in the git common directory, relative to it
COMMON_LEDGER = Path("qmhp-attempts") / "STATIC-REFINEMENT-STUDY.json"
RESULTS_ROOT = REPO / "results"
RECORD_PREFIX = "STATIC-REFINEMENT-STUDY-"
#: every repository file this process executes on the execution path; a test and
#: execute() itself check that no other repository module is loaded
CODE_FILES = {"study_driver.py": HERE / "study_driver.py",
              "nested_solver.py": HERE / "nested_solver.py",
              "anchor_fem.py": HERE.parent / "static-anchor-hypothesis" / "anchor_fem.py",
              "orchestrator/manifest.py": REPO / "orchestrator" / "manifest.py"}
LEVELS = (0, 1, 2)
#: the signals that end the attempt: each raises BudgetExceeded once (see _on_limit)
STOP_SIGNALS = (signal.SIGXCPU, signal.SIGALRM, signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
#: RLIMIT_AS hard limit above the soft one, so the failure path can raise its own soft limit
AS_HEADROOM_BYTES = 1024 ** 3
MAX_APPROVAL_WINDOW = timedelta(days=7)

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
    """Raised instead of computing anything, before the attempt is spent."""


class BudgetExceeded(RuntimeError):
    """A declared budget limit or a termination signal was reached inside the attempt."""


class AttemptFailed(RuntimeError):
    """Anything that went wrong AFTER the attempt was spent: failure.json and a verified
    manifest are written where possible, and nothing is retried."""


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


def _clean(o):
    """JSON-safe copy: non-finite floats become null (strict JSON), numpy scalars plain."""
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (float, np.floating)):
        return float(o) if math.isfinite(o) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def _dump(path: Path, obj) -> None:
    """Strict JSON, written atomically: to <name>.partial, flushed and fsynced, then renamed.
    An interruption leaves either the complete file or a .partial one, never an empty or
    truncated file under the final name."""
    text = json.dumps(_clean(obj), indent=1, allow_nan=False) + "\n"
    part = path.with_name(path.name + ".partial")
    with open(part, "w") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(part, path)


# --- the execution path (shared by the study and the dry run) ----------------------------

def ladder(mesh0: dict) -> list[dict]:
    """Levels 0, 1, 2: the mesh and two uniform red refinements (anchor_fem.refine_red)."""
    meshes = [mesh0]
    for _ in LEVELS[1:]:
        meshes.append(af.refine_red(meshes[-1]))
    return meshes


_CROSS_KEYS = ("energy_nd", "total_error_bound_nd", "total_error_bound_rel", "C_fF",
               "port_voltage", "extended_precision_probe_ok", "phi_abs_max", "cpu_s", "wall_s")
_FACT_KEYS = ("max_face_multiplicity", "boundary_faces", "every_boundary_face_is_tagged",
              "every_boundary_face_on_the_box_surface",
              "every_interior_face_separates_its_tetrahedra", "volume_sum_over_box_minus_1")


def run_levels(meshes: list[dict], model: dict, write, t0: float,
               levels: list | None = None, after_level=None) -> list[dict]:
    """Solve both problems on every level. Each level's facts are written before its first
    solve and each solve's raw result as soon as it completes (``write(name, obj)``), so a
    later failure never discards a completed solve. Completed levels are appended to
    ``levels`` and passed to ``after_level(h, level)``."""
    levels = [] if levels is None else levels
    prev, prev_phi = None, {}
    for h, mesh in zip(LEVELS, meshes):
        L = ns.Level(mesh, model)
        bf = ns.boundary_facts(mesh, L.xyz)
        geo = L.dd["C"]["geo"]
        facts = {"level": h, "mesh_digest": ns.mesh_digest(mesh), "n_tets": int(len(mesh["tets"])),
                 "n_nodes": int(len(mesh["xyz"])),
                 "conductor_nodes": [int(len(L.dd["C"]["ground"])), int(len(L.dd["C"]["island"]))],
                 "mesh_facts": {k: bf[k] for k in _FACT_KEYS},
                 "preconditions_failed": ns.certificate_preconditions(L, bf),
                 "poincare": L.poincare,
                 "port": {k: geo[k] for k in geo if k not in ("port_nodes", "t")}}
        del bf
        write(f"level{h}.json", facts)
        rec = {**facts, "problems": {}}
        phis = {}
        for kind in ns.KINDS:
            method = "direct" if h < 2 else "twogrid"
            r, phi = ns.solve(L, kind, method, coarse=prev, coarse_phi=prev_phi.get(kind))
            write(f"level{h}-{kind}.json", r)
            if h == 1:
                rx, _ = ns.solve(L, kind, "twogrid", coarse=prev, coarse_phi=prev_phi[kind])
                write(f"level1-{kind}-crosscheck.json", rx)
                r = {**r, "twogrid_cross_check": {**{k: rx[k] for k in _CROSS_KEYS},
                                                  "solver": rx["solver"]}}
            rec["problems"][kind] = r
            phis[kind] = phi
        rec["resources_so_far"] = _usage(t0)
        levels.append(rec)
        if after_level is not None:
            after_level(h, rec)
        prev, prev_phi = L, phis
    return levels


# --- the frozen analysis ---------------------------------------------------------------

def _finite_real(v) -> bool:
    return (isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool)
            and math.isfinite(v))


def _level_validity(lv, h: int) -> list[str]:
    """Missing, non-finite or non-physical values on one level; nothing is compared with a
    threshold before this is empty."""
    if not isinstance(lv, dict) or lv.get("level") != h:
        return [f"level {h}: missing or mislabelled"]
    probs = lv.get("problems")
    if not isinstance(probs, dict):
        return [f"level {h}: no problems block"]
    bad = []
    for kind in ns.KINDS:
        r = probs.get(kind)
        if not isinstance(r, dict):
            bad.append(f"level {h} {kind}: missing")
            continue
        blocks = [(kind, r)]
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
        for key in ("S_GHz2", "C_F"):
            if not (_finite_real(r.get(key)) and r[key] > 0):
                bad.append(f"level {h} {kind}: {key} = {r.get(key)!r}")
    return bad


def _solver_problems(tag: str, solver: dict, t: dict) -> list[str]:
    """Nesting checks of a two-grid solve. Its PCG status and Gauss-Seidel probes are
    diagnostics: the certificate, checked separately, does not depend on the solver."""
    bad = []
    if solver.get("method") != "twogrid":
        return bad
    g = solver.get("galerkin_identity_rel")
    if not (_finite_real(g) and g <= t["galerkin_identity_rel_tol"]):
        bad.append(f"{tag}: Galerkin identity {g!r}")
    if solver.get("fixed_rows_from_free_coarse_nnz") != 0:
        bad.append(f"{tag}: the coarse homogeneous space leaks into constrained fine nodes")
    return bad


def level_integrity(lv, h: int, pre: dict, anchor: dict | None) -> list[str]:
    """Every integrity item that needs only level h."""
    invalid = _level_validity(lv, h)
    if invalid:
        return invalid
    t = pre["integrity"]
    bad = []
    if lv["mesh_digest"] != pre["configuration"]["level_mesh_digests"][str(h)]:
        bad.append(f"level {h}: mesh digest differs from the pre-declared one")
    bad += [f"level {h}: {p}" for p in lv["preconditions_failed"]]
    for kind in ns.KINDS:
        r = lv["problems"][kind]
        checked = [(f"level {h} {kind}", r)]
        if h == 1:
            checked.append((f"level 1 {kind} cross-check", r["twogrid_cross_check"]))
        for tag, b in checked:
            if b["total_error_bound_rel"] > t["certificate_rel_tol"]:
                bad.append(f"{tag}: certified error {b['total_error_bound_rel']!r} exceeds "
                           f"{t['certificate_rel_tol']}")
            if abs(b["port_voltage"] - 1.0) > t["port_voltage_abs_tol"]:
                bad.append(f"{tag}: port voltage {b['port_voltage']!r} is not 1")
            if b.get("extended_precision_probe_ok") is not True:
                bad.append(f"{tag}: the long-double arithmetic probe failed or is missing, so "
                           "the evaluation bound is invalid")
            bad += _solver_problems(tag, b["solver"], t)
        if h == 1:
            x = r["twogrid_cross_check"]
            if abs(x["energy_nd"] - r["energy_nd"]) > x["total_error_bound_nd"] + r["total_error_bound_nd"]:
                bad.append(f"level 1 {kind}: direct and two-grid disagree beyond their bounds")
    e, ep = lv["problems"]["C"], lv["problems"]["Cprime"]
    if ep["energy_nd"] < e["energy_nd"] - e["total_error_bound_nd"] - ep["total_error_bound_nd"]:
        bad.append(f"level {h}: C' < C, which more constraints forbid")
    if anchor is not None and h in (0, 1):
        new, old = lv["problems"]["C"]["C_F"], anchor[f"C{h}_F"]
        if abs(new - old) > t["reproduction_rel_tol"] * old:
            bad.append(f"level {h}: C_h {new!r} does not reproduce the executed static-anchor "
                       f"record {old!r}")
    return bad


def nesting_failures(levels, pairs) -> list[str]:
    """Nested refinement cannot raise the energy: E_b <= E_a within the two bounds."""
    bad = []
    for kind in ns.KINDS:
        for ha, hb in pairs:
            a, b = levels[ha]["problems"][kind], levels[hb]["problems"][kind]
            if b["energy_nd"] > a["energy_nd"] + a["total_error_bound_nd"] + b["total_error_bound_nd"]:
                bad.append(f"{kind}: energy rose from level {ha} to {hb}, which nesting forbids")
    return bad


def integrity(levels, pre: dict, anchor: dict | None) -> list[str]:
    """Every failure makes the record UNQUALIFIED. None of these is a scientific outcome."""
    if not isinstance(levels, list) or len(levels) != len(LEVELS):
        n = len(levels) if isinstance(levels, list) else type(levels).__name__
        return [f"expected exactly the {len(LEVELS)} declared levels, got {n}"]
    bad = []
    for h, lv in zip(LEVELS, levels):
        bad += level_integrity(lv, h, pre, anchor)
    if bad:
        return bad
    return nesting_failures(levels, [(h - 1, h) for h in LEVELS[1:]])


def _interval(lv: dict, kind: str) -> tuple[float, float, float]:
    r = lv["problems"][kind]
    return r["energy_nd"], r["energy_nd"] - r["total_error_bound_nd"], r["energy_nd"] + r["total_error_bound_nd"]


def _differences(values, lows, highs):
    X0, X1, X2 = values
    d1, d2 = X0 - X1, X1 - X2
    d1r = (lows[0] - highs[1], highs[0] - lows[1])
    d2r = (lows[1] - highs[2], highs[1] - lows[2])
    return d1, d2, d1r, d2r


def classify(values, lows, highs, w: dict) -> dict:
    """The frozen convergence rule for the energies of C or C' at levels 0, 1, 2
    (predeclaration 'classification'). d1 = X0 - X1, d2 = X1 - X2, R = d1 / d2; each X_h
    is known only to lie in [low_h, high_h] (its certificate) and the rule uses those ranges.

    UNQUALIFIED     a difference certainly negative: nesting forbids it.
    UNRESOLVED      a difference within its certified error of zero; 1 < R < R_min; R > R_max;
                    or the certified range of R touching 1, R_min or R_max (fail-safe).
    NON-CONVERGENT  R < 1: the differences do not shrink.
    CONVERGING      R_min <= R <= R_max. The limit is bracketed, MODEL-BASED (two terms of
                    orders 1 and q in (1, 2], coefficients of one sign - an assumption the
                    theory does not supply), by X2 - d2 and X2 - d2 / (R - 1).
    CONVERGED       CONVERGING and |d2| / |X2 - d2| <= tau (the bracket's conservative end).
    """
    d1, d2, d1r, d2r = _differences(values, lows, highs)
    out = {"values": list(values), "d1": d1, "d2": d2,
           "d1_certified_range": list(d1r), "d2_certified_range": list(d2r)}
    if d1r[1] < 0 or d2r[1] < 0:
        return {**out, "cls": "UNQUALIFIED", "reason": "a difference is negative, which nesting forbids"}
    if d1r[0] <= 0 <= d1r[1] or d2r[0] <= 0 <= d2r[1]:
        return {**out, "cls": "UNRESOLVED", "reason": "a difference is within its certified error of zero"}
    R, Rs = d1 / d2, [d1r[0] / d2r[1], d1r[1] / d2r[0]]
    out.update(R=R, R_certified_range=Rs, p_obs=math.log2(R))
    if any(Rs[0] <= e <= Rs[1] for e in (1.0, w["R_min"], w["R_max"])):
        return {**out, "cls": "UNRESOLVED", "reason": "R is within its certified error of a class edge"}
    if R < 1.0:
        return {**out, "cls": "NON-CONVERGENT",
                "reason": "the differences do not shrink at levels 0-2: no evidence of "
                          "convergence at these levels. Also consistent with a leading order "
                          "of 1 and a negative next term (h - 0.5 h^2 gives R = 0.8), or "
                          "pre-asymptotic; not evidence against the order-1 theory"}
    if R < w["R_min"]:
        return {**out, "cls": "UNRESOLVED",
                "reason": "observed order below 1: consistent with a leading order of 1 and a "
                          "negative next term, or pre-asymptotic; not classified"}
    if R > w["R_max"]:
        return {**out, "cls": "UNRESOLVED",
                "reason": "observed order above 2: pre-asymptotic; not classified"}
    X2 = values[2]
    lim1, lim_obs = X2 - d2, X2 - d2 / (R - 1.0)
    remaining_hi = d2 / lim1
    out.update(limit_bracket_model_based=[lim1, lim_obs],
               remaining_rel_error_at_level2_bracket=[d2 / (R - 1.0) / lim_obs, remaining_hi],
               bracket_assumption="two terms, orders 1 and q in (1, 2], coefficients of one sign")
    if remaining_hi <= w["tau_converged"]:
        return {**out, "cls": "CONVERGED",
                "reason": "observed order within [1, 2]; level 2 within tau of the model limit"}
    return {**out, "cls": "CONVERGING",
            "reason": "observed order within [1, 2]; level 2 not within tau of the model limit"}


def classify_delta(values, lows, highs) -> dict:
    """DESCRIPTIVE only: no rate theory exists for delta, so no bracket and no CONVERGED.

    UNRESOLVED             a difference within its certified error of zero; oscillation
                           (differences of opposite sign that shrink); or a certified ratio
                           range touching 1.
    NON-CONVERGENT         |d2| >= |d1|: the differences do not shrink at levels 0-2.
    DIFFERENCES-SHRINKING  |d2| < |d1| with one sign; R reported, nothing extrapolated.
    """
    d1, d2, d1r, d2r = _differences(values, lows, highs)
    out = {"values": list(values), "d1": d1, "d2": d2,
           "d1_certified_range": list(d1r), "d2_certified_range": list(d2r)}
    if d1r[0] <= 0 <= d1r[1] or d2r[0] <= 0 <= d2r[1]:
        return {**out, "cls": "UNRESOLVED", "reason": "a difference is within its certified error of zero"}
    a1, a2 = sorted(abs(v) for v in d1r), sorted(abs(v) for v in d2r)
    Rs = [a1[0] / a2[1], a1[1] / a2[0]]
    out.update(R=d1 / d2, abs_R_certified_range=Rs)
    if Rs[0] <= 1.0 <= Rs[1]:
        return {**out, "cls": "UNRESOLVED", "reason": "|R| is within its certified error of 1"}
    if abs(d2) >= abs(d1):
        return {**out, "cls": "NON-CONVERGENT", "reason": "the differences do not shrink at levels 0-2"}
    if (d1 > 0) != (d2 > 0):
        return {**out, "cls": "UNRESOLVED", "reason": "the differences change sign (oscillation)"}
    return {**out, "cls": "DIFFERENCES-SHRINKING",
            "reason": "descriptive: the differences shrink; no rate theory, nothing extrapolated"}


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
    """The level-0 cross-code check (predeclaration 'consistency_check'). Reads level 0 only.
    Not an acceptance criterion: it decides only whether S'_h may be read as H_h."""
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
            "Sprime0_static_GHz2": levels[0]["problems"]["Cprime"]["S_GHz2"],
            "H_band_GHz2": band["H_band_GHz2"], "meaning": c["consequence"][verdict]}


def level0_consistency(levels, pre: dict, band: dict | None, anchor: dict | None) -> dict:
    """The consistency verdict with its own scope: it needs level 0 only, so it is qualified
    by the level-0 integrity items alone and survives any failure at levels 1-2 (but see
    nesting_0_to_1). This is what consistency-level0.json holds, written after level 0."""
    if band is None:
        return {"verdict": "NOT APPLICABLE", "reason": "synthetic run: no Palace band"}
    if not levels:
        return {"verdict": "UNQUALIFIED", "reason": "level 0 did not complete"}
    bad = level_integrity(levels[0], 0, pre, anchor)
    if bad:
        return {"verdict": "UNQUALIFIED", "level0_integrity_failures": bad,
                "meaning": pre["consistency_check"]["consequence"]["UNQUALIFIED"]}
    return {**consistency(levels, pre, band), "level0_integrity_failures": []}


def nesting_0_to_1(levels, pre: dict, anchor: dict | None) -> dict:
    """The one cross-level check that can implicate level 0: an energy that rises from level
    0 to level 1 beyond both bounds means an energy or a certificate at level 0 or level 1
    is wrong, and which one cannot be told. Checked only when both levels pass their own
    integrity items."""
    if not isinstance(levels, list) or len(levels) < 2:
        return {"status": "NOT CHECKED", "reason": "level 1 did not complete"}
    if level_integrity(levels[0], 0, pre, anchor) or level_integrity(levels[1], 1, pre, anchor):
        return {"status": "NOT CHECKED", "reason": "level 0 or level 1 failed its own integrity items"}
    bad = nesting_failures(levels, [(0, 1)])
    return {"status": "FAILED" if bad else "PASSED", "failures": bad}


def level0_verdict(levels, pre: dict, band: dict | None, anchor: dict | None) -> dict:
    """The level-0 verdict as the summary reads it: level0_consistency, made UNQUALIFIED if
    the 0-to-1 nesting check fails (fail-closed: it may implicate level 0)."""
    v = level0_consistency(levels[:1], pre, band, anchor)
    n = nesting_0_to_1(levels, pre, anchor)
    v = {**v, "nesting_0_to_1": n}
    if n["status"] == "FAILED" and v["verdict"] not in ("NOT APPLICABLE", "UNQUALIFIED"):
        v = {**v, "verdict": "UNQUALIFIED", "verdict_before_the_nesting_check": v["verdict"],
             "reason": "an energy rose from level 0 to level 1 beyond the bounds: an energy or "
                       "a certificate at level 0 or level 1 is wrong",
             "meaning": pre["consistency_check"]["consequence"]["UNQUALIFIED"]}
    return v


def _assembly_term(pre: dict, lv: dict, kind: str):
    """max|phi|^2 sum|K - K_ld| / E at this level: the estimated first-order effect of the
    uncertified assembly round-off, relative (None where the preflight did not measure it)."""
    gap = pre.get("configuration", {}).get("assembly_gap_preflight", {}).get("abs_sum_nd")
    r = lv["problems"][kind]
    if not gap or str(lv["level"]) not in gap or not _finite_real(r.get("phi_abs_max")):
        return None
    return r["phi_abs_max"] ** 2 * gap[str(lv["level"])] / r["energy_nd"]


def analyse(levels, pre: dict, band: dict | None, anchor: dict | None) -> dict:
    level0 = level0_verdict(levels, pre, band, anchor)
    bad = integrity(levels, pre, anchor)
    out = {"consistency_check_level0": level0, "integrity_failures": bad}
    if bad:
        out["consistency_check_level0"] = {
            **level0, "in_this_record": pre["consistency_check"]["in_an_unqualified_record"]}
        out["outcome"] = {"verdict": "UNQUALIFIED", "reason": "; ".join(bad),
                          "consistency_check_level0": level0["verdict"]}
        return out
    w = pre["classification"]
    cls = {}
    for kind in ns.KINDS:
        iv = [_interval(lv, kind) for lv in levels]
        cls[kind] = classify([v[0] for v in iv], [v[1] for v in iv], [v[2] for v in iv], w)
    dv, dl, dh = [], [], []
    for lv in levels:
        E, El, Eh = _interval(lv, "C")
        Ep, Epl, Eph = _interval(lv, "Cprime")
        dv.append(Ep / E - 1.0); dl.append(Epl / Eh - 1.0); dh.append(Eph / El - 1.0)
    cls["delta"] = classify_delta(dv, dl, dh)
    cls["delta"]["max_delta_levels_0_to_2"] = max(dv)
    cls["delta"]["S_and_Sprime_within_1_percent_at_levels_0_to_2"] = bool(max(dv) <= w["delta_small"])
    identity_confirmed = level0["verdict"] == "CONSISTENT"
    hname = "H" if identity_confirmed else (
        "Sprime_static_identity_not_tested" if band is None else "Sprime_static_identity_not_confirmed")
    for kind, name in (("C", "S"), ("Cprime", hname)):
        k = levels[0]["problems"][kind]["S_GHz2"] * levels[0]["problems"][kind]["energy_nd"]
        r2 = levels[2]["problems"][kind]
        c = cls[kind]
        cls[name] = {"cls": c["cls"], "values_GHz2": [lv["problems"][kind]["S_GHz2"] for lv in levels],
                     "lower_bound_GHz2": r2["S_GHz2"] / (1.0 + r2["total_error_bound_rel"]),
                     "bound_basis": pre["classification"]["bound_basis"],
                     "assembly_term_estimate_rel_at_level2": _assembly_term(pre, levels[2], kind)}
        if "limit_bracket_model_based" in c:
            cls[name]["limit_bracket_model_based_GHz2"] = sorted(k / e for e in c["limit_bracket_model_based"])
            cls[name]["bracket_assumption"] = c["bracket_assumption"]
            cls[name]["remaining_rel_error_at_level2_bracket"] = c["remaining_rel_error_at_level2_bracket"]
    for kind in ns.KINDS:                      # C <= C_2 (Dirichlet principle)
        r2 = levels[2]["problems"][kind]
        cls[kind]["upper_bound_fF"] = r2["C_fF"] * (1.0 + r2["total_error_bound_rel"])
        cls[kind]["bound_basis"] = pre["classification"]["bound_basis"]
        cls[kind]["assembly_term_estimate_rel_at_level2"] = _assembly_term(pre, levels[2], kind)
    out["classes"] = cls
    out["outcome"] = {"verdict": "QUALIFIED", "C": cls["C"]["cls"], "Cprime": cls["Cprime"]["cls"],
                      "delta": cls["delta"]["cls"], "consistency_check_level0": level0["verdict"],
                      "second_moment_name": hname,
                      "note": pre["classification"]["dependence_note"]}
    return out


# --- provenance, approval and the one attempt ----------------------------------------------

def load_pre() -> dict:
    return json.loads(PREDECLARATION.read_text())


def _read_pre() -> tuple[dict, str]:
    """The pre-declaration and its digest from ONE read of the file."""
    raw = PREDECLARATION.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def qmhp_mesh(cfg: dict = CONFIG) -> dict:
    path = REPO / cfg["mesh"]
    if af.sha256(path) != cfg["mesh_sha256"]:
        raise Refusal("the mesh digest does not match the configuration")
    return af.read_gmsh22(path)


def _git_dirs(repo: Path = REPO) -> tuple[Path, Path]:
    """This checkout's git directory and the common directory it shares with every other
    worktree of the same clone, read without running git."""
    g = repo / ".git"
    if g.is_file():                                        # a linked worktree
        gitdir = Path(g.read_text().split("gitdir:", 1)[1].strip())
        gitdir = gitdir if gitdir.is_absolute() else (repo / gitdir).resolve()
    else:
        gitdir = g
    common = gitdir
    if (gitdir / "commondir").is_file():
        common = (gitdir / (gitdir / "commondir").read_text().strip()).resolve()
    return gitdir, common


def common_ledger_path(repo: Path = REPO) -> Path:
    """The ledger entry that survives any checkout, reset or clean of this clone and of
    every worktree that shares its git directory. It is never committed."""
    return _git_dirs(repo)[1] / COMMON_LEDGER


def git_head(repo: Path = REPO) -> str:
    """The commit this checkout has checked out, read from .git without running git."""
    gitdir, common = _git_dirs(repo)
    head = (gitdir / "HEAD").read_text().strip()
    if not head.startswith("ref:"):
        return head
    ref = head[4:].strip()
    for base in (gitdir, common):
        if (base / ref).is_file():
            return (base / ref).read_text().strip()
    packed = common / "packed-refs"
    if packed.is_file():
        for line in packed.read_text().splitlines():
            if line and not line.startswith(("#", "^")):
                sha, name = line.split(" ", 1)
                if name.strip() == ref:
                    return sha
    raise Refusal(f"cannot resolve HEAD ({ref})")


def unbound_repo_modules() -> list[str]:
    """Repository files loaded in this process that the approval does not bind. The
    interpreter's own environment (sys.prefix, e.g. the repository's .venv) is excluded:
    its libraries are bound by the verified versions instead (environment_problems)."""
    bound = {p.resolve() for p in CODE_FILES.values()}
    envs = {Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()}
    out = []
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        p = Path(f).resolve()
        if REPO not in p.parents or p in bound or any(e == p or e in p.parents for e in envs):
            continue
        out.append(str(p.relative_to(REPO)))
    return sorted(set(out))


def environment_problems(pre: dict) -> list[str]:
    """Differences between this process and the verified environment."""
    want = pre["environment"]
    have = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}
    bad = [f"{k} is {have[k]}, verified {want[k]}" for k in ("python", "numpy", "scipy")
           if have[k] != want[k]]
    for var, val in want["threads_env"].items():
        if os.environ.get(var) != val:
            bad.append(f"environment variable {var} is {os.environ.get(var)!r}, required {val!r}")
    if not float(np.finfo(np.longdouble).eps) < want["longdouble_eps_below"]:
        bad.append("no extended-precision long double")
    probe = ns.extended_precision_probe()
    if not all(probe.values()):
        bad.append(f"long-double arithmetic is not extended: {probe}")
    return bad


def _parent_argv() -> list[str] | None:
    try:
        raw = Path(f"/proc/{os.getppid()}/cmdline").read_bytes()
    except OSError:
        return None
    return [a.decode(errors="replace") for a in raw.split(b"\0") if a]


def measure_invocation() -> dict:
    """How this process was started, as far as it can see: recorded in provenance.json and
    compared with the declared invocation before the attempt is spent."""
    bound = {name: getattr(sys.modules.get(mod), "__cached__", None)
             for name, mod in (("nested_solver.py", "nested_solver"),
                               ("anchor_fem.py", "anchor_fem"),
                               ("orchestrator/manifest.py", "qmhp_orchestrator_manifest"))}
    return {"cwd": os.getcwd(), "argv": list(sys.argv), "parent_argv": _parent_argv(),
            "executable": sys.executable, "prefix": sys.prefix,
            "optimize": sys.flags.optimize, "dont_write_bytecode": bool(sys.dont_write_bytecode),
            "pycache_prefix": sys.pycache_prefix, "bytecode_cache_paths": bound,
            "threads_env": {v: os.environ.get(v) for v in
                            ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}}


def invocation_problems(pre: dict, measured: dict | None = None) -> list[str]:
    """Differences between the measured invocation and the declared one
    (predeclaration budget.invocation_measured_as)."""
    want = pre["budget"]["invocation_measured_as"]
    m = measure_invocation() if measured is None else measured
    bad = []
    if Path(m["cwd"]).resolve() != REPO:
        bad.append(f"working directory {m['cwd']} is not the repository root {REPO}")
    if m["argv"] != want["argv"]:
        bad.append(f"argv {m['argv']} is not {want['argv']}")
    pa = m["parent_argv"]
    if not pa or Path(pa[0]).name != want["parent_argv"][0] or pa[1:] != want["parent_argv"][1:]:
        bad.append(f"the parent process {pa} is not the declared {want['parent_argv']}")
    if Path(m["prefix"]).resolve() != (REPO / want["interpreter_prefix"]).resolve():
        bad.append(f"interpreter prefix {m['prefix']} is not the repository's {want['interpreter_prefix']}")
    if m["optimize"] != 0:
        bad.append(f"python optimisation level {m['optimize']} (asserts removed)")
    if not (m["dont_write_bytecode"] and m["pycache_prefix"] == NO_BYTECODE_CACHE
            and all(c is None or str(c).startswith(NO_BYTECODE_CACHE)
                    for c in m["bytecode_cache_paths"].values())):
        bad.append("repository modules were not compiled from their source "
                   "(bytecode caches not bypassed)")
    return bad


def _parse_utc(s) -> datetime:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refusal(f"{s!r} is not an ISO time") from exc
    if t.tzinfo is None:
        raise Refusal(f"{s!r} carries no time zone")
    return t.astimezone(timezone.utc)


def _read_approval() -> bytes:
    if not APPROVAL.is_file():
        raise Refusal("no STUDY-APPROVAL.json: the static-only nested refinement study is "
                      "PREPARED, NOT APPROVED. A human grants it by writing the approval that "
                      "binds the mesh, the pre-declaration, the code, the environment, the "
                      "approved commit, this checkout and a validity window.")
    return APPROVAL.read_bytes()


def require_approval(pre: dict, now: datetime | None = None, *, raw: bytes | None = None,
                     pre_sha256: str | None = None) -> dict:
    """The approval, from ``raw`` (one read of STUDY-APPROVAL.json) if given. The
    pre-declaration digest is ``pre_sha256`` (from the same read as ``pre``) if given."""
    ap = json.loads(_read_approval() if raw is None else raw)
    b = pre["budget"]
    want = {"authorises": "one execution of the static-only nested refinement study",
            "attempt": 1, "prior_records": [],
            "mesh_sha256": CONFIG["mesh_sha256"],
            "predeclaration_sha256": af.sha256(PREDECLARATION) if pre_sha256 is None else pre_sha256,
            "code_sha256": {name: af.sha256(path) for name, path in CODE_FILES.items()},
            "environment": pre["environment"], "invocation": b["invocation"],
            "budget": {k: b[k] for k in ("cpu_minutes", "memory_GB", "wall_cap_minutes",
                                         "attempts", "retry")},
            "repository_path": str(REPO)}
    for key, value in want.items():
        if ap.get(key) != value:
            raise Refusal(f"approval {key} does not match: the reviewed state has changed")
    if not re.fullmatch(r"[0-9a-f]{40}", str(ap.get("source_commit"))):
        raise Refusal("approval source_commit is not a full commit SHA")
    head = git_head(REPO)
    if head != ap["source_commit"]:
        raise Refusal(f"approval source_commit {ap['source_commit']} is not HEAD {head}")
    nb, na = _parse_utc(ap.get("not_before_utc")), _parse_utc(ap.get("not_after_utc"))
    if not (nb < na <= nb + MAX_APPROVAL_WINDOW):
        raise Refusal("the approval window is empty or longer than 7 days")
    now = datetime.now(timezone.utc) if now is None else now
    if not nb <= now <= na:
        raise Refusal("the approval is outside its validity window")
    return ap


#: signal state of the attempt: the first stop signal raises, every later one is recorded
_SIGNALS = {"stopping": False, "received": []}


def _on_limit(signum, _frame):
    """Raise BudgetExceeded for the FIRST stop signal only. Every later delivery - a second
    SIGINT or SIGTERM forwarded by the outer timeout, a signal arriving while the failure
    path runs - is recorded and returns, so nothing can interrupt the evidence writes."""
    name = signal.Signals(signum).name
    _SIGNALS["received"].append({"signal": name, "at_s": time.monotonic() - _T_START})
    if _SIGNALS["stopping"]:
        return
    _SIGNALS["stopping"] = True
    raise BudgetExceeded(f"{name}: a declared budget limit or a termination signal was reached")


def _require_enforceable_budget(pre: dict) -> None:
    b = pre["budget"]
    wanted = {resource.RLIMIT_CPU: int(b["cpu_minutes"] * 60) + 60,
              resource.RLIMIT_AS: int(b["memory_GB"] * 1024 ** 3) + AS_HEADROOM_BYTES}
    for rlim, value in wanted.items():
        hard = resource.getrlimit(rlim)[1]
        if hard != resource.RLIM_INFINITY and hard < value:
            raise Refusal(f"this environment's hard limit {hard} is below the declared "
                          f"budget {value}; the budget cannot be applied as declared")


def _enforce_budget(pre: dict) -> dict:
    """CPU: SIGXCPU raises BudgetExceeded; the hard limit 60 CPU-s later is a kernel kill.
    Memory: RLIMIT_AS soft limit (an allocation beyond it fails), with a hard limit 1 GiB
    above so the failure path can raise its own soft limit. Wall: SIGALRM at the wall cap
    measured from module import, so the outer kill 60 s beyond the cap really is 60 s
    later. SIGTERM, SIGHUP and SIGINT also raise, once (_on_limit)."""
    b = pre["budget"]
    cpu_s = int(b["cpu_minutes"] * 60)
    wall_s = max(1, int(b["wall_cap_minutes"] * 60 - (time.monotonic() - _T_START)))
    mem = int(b["memory_GB"] * 1024 ** 3)
    _SIGNALS.update(stopping=False, received=[])
    for sig in STOP_SIGNALS:
        signal.signal(sig, _on_limit)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 60))
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem + AS_HEADROOM_BYTES))
    signal.alarm(wall_s)
    return {"cpu_s": cpu_s, "cpu_hard_kill_s": cpu_s + 60, "address_space_bytes": mem,
            "address_space_hard_bytes": mem + AS_HEADROOM_BYTES, "wall_alarm_s": wall_s,
            "wall_cap_from_start_s": int(b["wall_cap_minutes"] * 60),
            "stop_signals": [sig.name for sig in STOP_SIGNALS]}


def _disarm() -> None:
    """On the way out: no further signal can interrupt the evidence writes (the stop flag
    first, then every stop signal ignored and the alarm cancelled), and the soft limits rise
    to the hard ones so the writes can allocate and run."""
    _SIGNALS["stopping"] = True
    for sig in STOP_SIGNALS:
        signal.signal(sig, signal.SIG_IGN)
    signal.alarm(0)
    for rlim in (resource.RLIMIT_CPU, resource.RLIMIT_AS):
        try:
            hard = resource.getrlimit(rlim)[1]
            resource.setrlimit(rlim, (hard, hard))
        except (ValueError, OSError):
            pass


def _shutdown() -> None:
    """_disarm, retried: a first stop signal landing in the few bytecodes before the flag
    is set raises here once, and the retry then completes (the flag is set by then)."""
    for _ in range(3):
        try:
            _disarm()
            return
        except BaseException:              # noqa: BLE001 - a signal raised once; retry
            _SIGNALS["stopping"] = True


def _environment(files: dict = CODE_FILES) -> dict:
    return {"python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "platform": platform.platform(),
            "longdouble_eps": float(np.finfo(np.longdouble).eps),
            "extended_precision_probe": ns.extended_precision_probe(),
            "threads_env": {v: os.environ.get(v) for v in
                            ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
            "code_sha256": {name: af.sha256(path) for name, path in files.items()}}


def _guarded(fn):
    """A failure-path extra: never lets its own failure stop the evidence writes."""
    try:
        return fn()
    except BaseException as exc:            # noqa: BLE001
        return {"could_not_be_computed": repr(exc)}


def _create_exclusive(path: Path, obj) -> None:
    """Create a ledger entry that must not exist (O_EXCL), with its content."""
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(_clean(obj), indent=1, allow_nan=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def spent_state(results_root: Path | None = None) -> list[str]:
    """Every ledger entry that shows the one attempt has been spent."""
    results_root = RESULTS_ROOT if results_root is None else results_root
    found = [p.name for p in (ATTEMPT_MARKER, APPROVAL_CONSUMED) if p.exists()]
    if common_ledger_path().exists():
        found.append(f"<git common dir>/{COMMON_LEDGER}")
    if results_root.exists():
        found += sorted(p.name for p in results_root.glob(RECORD_PREFIX + "*"))
    return found


def execute(results_root: Path | None = None) -> Path:
    t0 = time.monotonic()
    results_root = RESULTS_ROOT if results_root is None else results_root
    pre, pre_sha = _read_pre()
    spent = spent_state(results_root)
    if spent:
        raise Refusal(f"{spent[0]} exists: the one attempt is spent")
    raw = _read_approval()
    approval = require_approval(pre, raw=raw, pre_sha256=pre_sha)
    unbound = unbound_repo_modules()
    if unbound:
        raise Refusal(f"repository code the approval does not bind is loaded: {unbound}")
    env_bad = environment_problems(pre)
    if env_bad:
        raise Refusal(f"the environment differs from the verified one: {env_bad}")
    inv_bad = invocation_problems(pre)
    if inv_bad:
        raise Refusal(f"the invocation differs from the declared one: {inv_bad}")
    band = band_baseline(pre)                  # digests checked before anything is spent
    anchor = anchor_values(pre)
    meshes = ladder(qmhp_mesh())
    digests = {str(h): ns.mesh_digest(m) for h, m in zip(LEVELS, meshes)}
    if digests != pre["configuration"]["level_mesh_digests"]:
        raise Refusal("a refined mesh differs from the pre-declared one")
    _require_enforceable_budget(pre)
    common = common_ledger_path()
    provenance = {"predeclaration_sha256": pre_sha,
                  "approval_sha256": hashlib.sha256(raw).hexdigest(), "approval": approval,
                  "source_commit_measured": git_head(REPO), "repository_path": str(REPO),
                  "mesh_sha256": CONFIG["mesh_sha256"], "level_mesh_digests": digests,
                  "band_baseline": band, "static_anchor_values": anchor,
                  "environment": _environment(), "invocation": measure_invocation(),
                  "started_utc": datetime.now(timezone.utc).isoformat()}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rec = results_root / f"{RECORD_PREFIX}{stamp}"
    ledger = {"record": rec.name, "approval_sha256": provenance["approval_sha256"],
              "source_commit": provenance["source_commit_measured"],
              "repository_path": str(REPO), "spent_utc": provenance["started_utc"]}
    levels, written, created, limits, refused_exists = [], [], [], None, False

    def write(name, obj):
        _dump(rec / name, obj)
        written.append(name)

    def after_level(h, lv):
        if h != 0:
            return
        try:                                   # an analysis fault must not end the solves
            verdict = level0_consistency([lv], pre, band, anchor)
        except (BudgetExceeded, MemoryError):
            raise
        except Exception as exc:               # noqa: BLE001
            write("consistency-level0.error.json", {"error": repr(exc),
                                                    "traceback": traceback.format_exc()})
            return
        write("consistency-level0.json", verdict)

    try:
        limits = _enforce_budget(pre)          # from here a stop signal raises, once
        common.parent.mkdir(exist_ok=True)
        try:                                   # the first ledger entry spends the attempt
            _create_exclusive(common, ledger)
        except FileExistsError:
            refused_exists = True
            raise
        created.append(common)
        _create_exclusive(ATTEMPT_MARKER, ledger)
        created.append(ATTEMPT_MARKER)
        os.rename(APPROVAL, APPROVAL_CONSUMED)  # the approval cannot be used again
        results_root.mkdir(exist_ok=True)
        rec.mkdir(exist_ok=False)
        write("provenance.json", {**provenance, "limits": limits})
        run_levels(meshes, _model(), write, t0, levels, after_level)
        _shutdown()
        write("summary.json", {"provenance": "provenance.json", "resources": _usage(t0),
                               "C_fF": [lv["problems"]["C"]["C_fF"] for lv in levels],
                               "Cprime_fF": [lv["problems"]["Cprime"]["C_fF"] for lv in levels],
                               **analyse(levels, pre, band, anchor),
                               "signals_received": _SIGNALS["received"],
                               "not_reported": "E_C,F1F1 and g; no coupling, readout frequency "
                                               "or Route A output is read or combined"})
        manifest.write_verified(rec)
    except BaseException as exc:               # the failure is the recorded outcome
        _shutdown()
        if refused_exists:
            raise Refusal(f"{COMMON_LEDGER} exists in the git common directory: the one "
                          "attempt is spent") from None
        if not common.exists():
            raise Refusal(f"the attempt could not be started and nothing was spent: {exc!r}") from exc
        _record_failure(exc, rec, ledger, created, pre, band, anchor, levels, written, limits,
                        provenance, t0)
    return rec


def _record_failure(exc, rec: Path, ledger: dict, created: list, pre, band, anchor, levels,
                    written, limits, provenance, t0) -> None:
    """The failure path of a spent attempt. Signals can no longer raise (_shutdown). Every
    extra is guarded, so failure.json and the manifest are written whatever else fails; the
    level-0 verdict is READ BACK from consistency-level0.json, never recomputed."""
    tb = _guarded(traceback.format_exc)
    _guarded(lambda: traceback.clear_frames(exc.__traceback__))
    _guarded(gc.collect)
    if APPROVAL.exists() and not APPROVAL_CONSUMED.exists():   # spent before the rename
        _guarded(lambda: os.rename(APPROVAL, APPROVAL_CONSUMED))
    if not rec.is_dir():                       # spent before the record existed
        note = {**ledger, "record_created": False, "error": repr(exc), "traceback": tb,
                "verdict": "FAILED - the one attempt is spent; no record could be created; no retry"}
        where = created or [common_ledger_path()]     # only entries this process created
        errs = [_guarded(lambda p=p: _dump(p, note)) for p in where]
        raise AttemptFailed(f"{rec.name}: {exc!r}; no record could be created; the error is "
                            f"in {[str(p) for p in where]} {[e for e in errs if e]}") from exc
    level0_file = rec / "consistency-level0.json"
    failure = {
        "verdict": "FAILED - the one attempt is spent; no retry",
        "error": repr(exc), "traceback": tb,
        "levels_completed": _guarded(lambda: [lv["level"] for lv in levels]),
        "files_written": list(written),
        "partial_files": _guarded(lambda: sorted(p.name for p in rec.glob("*.partial"))),
        "consistency_check_level0": _guarded(
            lambda: json.loads(level0_file.read_text()) if level0_file.is_file() else None),
        "consistency_check_level0_status": (
            "as written after level 0 (consistency-level0.json); provisional: in a failed "
            "record the 0-to-1 nesting check below is the only cross-level check applied"),
        "nesting_0_to_1": _guarded(lambda: nesting_0_to_1(levels, pre, anchor)),
        "summary_json_superseded": (rec / "summary.json").is_file(),
        "signals_received": list(_SIGNALS["received"]),
        "limits": limits, "resources": _guarded(lambda: _usage(t0)), "provenance": provenance}
    err = None
    try:
        _dump(rec / "failure.json", failure)
    except BaseException as exc1:              # noqa: BLE001 - still seal what exists
        err = exc1
    try:
        manifest.write_verified(rec)
    except BaseException as exc2:              # noqa: BLE001
        raise AttemptFailed(f"{rec.name}: {exc!r}; the failure record could not be "
                            f"completed: {err!r} {exc2!r}") from exc
    if err is not None:
        raise AttemptFailed(f"{rec.name}: {exc!r}; failure.json could not be written "
                            f"({err!r}); the record is sealed by its manifest") from exc
    raise AttemptFailed(f"{rec.name}: {exc!r} (recorded in failure.json; the one attempt "
                        "is spent; no retry)") from exc


# --- preflight and dry run -----------------------------------------------------------------

#: every file whose code produced the committed preparation evidence
EVIDENCE_CODE = {**CODE_FILES, "synthetic_cells.py": HERE / "synthetic_cells.py",
                 "verify_solver.py": HERE / "verify_solver.py"}


def _preflight_level(L: "ns.Level", bf: dict, prev: "ns.Level | None", Pfull) -> dict:
    out = {"mesh_digest": ns.mesh_digest(L.mesh), "n_tets": int(len(L.mesh["tets"])),
           "n_nodes": int(len(L.mesh["xyz"])), "mesh_facts": {k: bf[k] for k in _FACT_KEYS},
           "preconditions_failed": ns.certificate_preconditions(L, bf),
           "poincare": L.poincare, "element_quality": ns.element_quality(L.mesh, L.xyz),
           "port": {k: v for k, v in L.dd["C"]["geo"].items() if k not in ("port_nodes", "t")},
           "problems": {}}
    Kc = L.K.tocsr()
    k = int(np.diff(Kc.indptr).max())
    abs_row = abs(Kc) @ np.ones(Kc.shape[0])
    used = np.unique(L.mesh["tets"])
    for kind in ns.KINDS:
        dd = L.dd[kind]
        sysm = ns.system(L.K, dd)
        A = sysm["A"]
        ones = np.ones(A.shape[0])
        # proxies with |x| <= 1, NO solve: the residual term's floor if the solve were exact,
        # and the evaluation bound's matrix-vector term
        kA = int(np.diff(A.indptr).max())
        g = (ns.gamma(kA + 1) * (np.abs(sysm["b"]) + abs(A) @ ones)
             + ns.gamma(int(np.diff(sysm["KfD"].indptr).max())) * (abs(sysm["KfD"]) @ np.abs(sysm["phiD"]))
             + 0.5 * (sysm["A_asym_abs"] @ ones + sysm["D_asym_abs"] @ np.abs(sysm["phiD"])))
        row = {"n_unknowns": int(A.shape[0]), "nnz_A": int(A.nnz),
               "n_port_nodes_constrained_off_conductors": int(dd["fixed"].sum() - L.dd["C"]["fixed"].sum()),
               "certificate_floor_proxy_nd": ns.BOUND_SAFETY * float((g * g / L.m[dd["free"]]).sum())
               / L.poincare["c"],
               "evaluation_matvec_term_proxy_nd": ns.gamma(k, ns.ULD) * float(abs_row[used].sum()),
               "evaluation_dot_term_factor": ns.gamma(len(L.xyz), ns.ULD)}
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
    """Geometry and assembly only. No linear solve; no capacitance is computed. Includes the
    assembly-gap estimate (an extended-precision re-assembly of K, compared entry by entry)."""
    t0 = time.monotonic()
    ns.require_extended_precision()
    model = _model()
    meshes = ladder(qmhp_mesh())
    out = {"mesh_sha256": CONFIG["mesh_sha256"], "linear_solves": 0, "levels": {}}
    prev = None
    for h, mesh in zip(LEVELS, meshes):
        L = ns.Level(mesh, model)
        bf = ns.boundary_facts(mesh, L.xyz)
        Pfull = ns.prolongation(meshes[h - 1], mesh) if h else None
        out["levels"][str(h)] = _preflight_level(L, bf, prev, Pfull)
        del bf, Pfull
        out["levels"][str(h)]["assembly_gap_estimate"] = ns.assembly_gap(L)
        prev = L
    out["resources"] = _usage(t0)
    out["environment"] = _environment(EVIDENCE_CODE)
    return out


def dry_run(budget: dict | None = None, evidence_dir: Path | None = None) -> dict:
    """The solve path (run_levels) on the QMHP-sized synthetic cell, optionally under a
    budget, with its per-solve evidence writes (_dump, strict JSON) into ``evidence_dir``
    (a fresh temporary directory if None), sealed and verified by write_verified. Not
    exercised: the approval, the ledger, provenance, the level-0 check and the summary."""
    import synthetic_cells as syn  # noqa: PLC0415 - synthetic only
    import tempfile  # noqa: PLC0415
    t0 = time.monotonic()
    limits = _enforce_budget({"budget": budget}) if budget else None
    evidence_dir = Path(tempfile.mkdtemp(prefix="qmhp-dry-run-")) if evidence_dir is None else evidence_dir
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if any(evidence_dir.iterdir()):
        raise Refusal(f"the dry-run evidence directory {evidence_dir} is not empty")
    written = []

    def write(name, obj):
        _dump(evidence_dir / name, obj)
        written.append(name)

    mesh, model = syn.chip_cell(**DRY_RUN_CELL)
    quality = ns.element_quality(mesh, af.scales(mesh, model["L0_m"], model["L_H"])["xyz_nd"])
    levels = run_levels(ladder(mesh), model, write, t0)
    manifest.write_verified(evidence_dir)
    writes = {"files": written, "bytes": sum((evidence_dir / n).stat().st_size for n in written),
              "manifest_verify": manifest.verify(evidence_dir),
              "unexpected_files": manifest.unexpected_files(evidence_dir),
              "strict_json": all(_strict_parse_ok(evidence_dir / n) for n in written)}
    _disarm()
    pre = load_pre()
    fake = {"integrity": pre["integrity"], "classification": pre["classification"],
            "configuration": {"level_mesh_digests": {str(lv["level"]): lv["mesh_digest"] for lv in levels}}}
    timing, histories = {}, {}
    for kind in ns.KINDS:
        sv = levels[2]["problems"][kind]["solver"]
        timing[kind] = {"setup_wall_s": sv["setup_wall_s"], "iterations": sv["iterations"],
                        "status": sv["status"], "pcg_wall_s": sv["history"][-1]["wall_s"],
                        "wall_s_per_iteration": sv["history"][-1]["wall_s"] / max(1, sv["iterations"])}
        histories[f"level2-{kind}"] = sv["history"]
        histories[f"level1-{kind}-crosscheck"] = levels[1]["problems"][kind]["twogrid_cross_check"]["solver"]["history"]
    return {"cell": DRY_RUN_CELL, "element_quality_level0": quality, "limits": limits,
            "resources": _usage(t0), "level2_pcg_timing": timing, "pcg_histories": histories,
            "per_level": [{"level": lv["level"], "n_tets": lv["n_tets"], "n_nodes": lv["n_nodes"],
                           "resources_so_far": lv["resources_so_far"],
                           "problems": {k: {"n_unknowns": r["n_unknowns"], "C_fF": r["C_fF"],
                                            "bound_rel": r["total_error_bound_rel"],
                                            "evaluation_bound_terms_nd": r["evaluation_bound_terms_nd"],
                                            "certificate_error_bound_nd": r["certificate"]["error_bound_nd"],
                                            "solver": {kk: r["solver"].get(kk) for kk in
                                                       ("method", "status", "iterations",
                                                        "galerkin_identity_rel",
                                                        "gauss_seidel_probe_rel",
                                                        "gauss_seidel_probe_backward_rel")},
                                            "cross_check": ({kk: r["twogrid_cross_check"]["solver"].get(kk)
                                                             for kk in ("status", "iterations")}
                                                            if "twogrid_cross_check" in r else None),
                                            "cpu_s": r["cpu_s"], "wall_s": r["wall_s"]}
                                        for k, r in lv["problems"].items()}}
                          for lv in levels],
            "analysis_of_the_synthetic_levels": analyse(levels, fake, None, None),
            "evidence_writes": writes,
            "environment": _environment(EVIDENCE_CODE), "qmhp_data_read": False}


def _strict_parse_ok(path: Path) -> bool:
    def bad(token):
        raise ValueError(token)
    try:
        json.loads(path.read_text(), parse_constant=bad)
        return True
    except ValueError:
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out")
    g.add_argument("--show-invocation", action="store_true",
                   help="print the measured invocation and its differences from the declared "
                        "one, then exit; reads nothing else and computes nothing")
    ap.add_argument("--evidence-dir", help="dry run only: where its per-solve files are written")
    args = ap.parse_args(argv)
    try:
        if args.show_invocation:
            m = measure_invocation()
            res = {"measured": m, "differences_from_declared": invocation_problems(load_pre(), m)}
        elif args.preflight:
            res = preflight()
        elif args.dry_run:
            res = dry_run(load_pre()["budget"], Path(args.evidence_dir) if args.evidence_dir else None)
        else:
            print(execute())
            return 0
        text = json.dumps(_clean(res), indent=1, allow_nan=False)
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
