# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Verification of the study's solvers and certificate on SYNTHETIC cases only.

No QMHP data is read. Run before anything touches the QMHP mesh; the committed output is
solver_verification.json. Each check states what would make it fail.

  V1  exact known answer: a layered box whose exact potential P1 reproduces; direct and
      two-grid must return the exact energy at levels 0, 1, 2, within their certificates.
  V2  discrete known answer at level 2 on QMHP-like cells: two-grid against the direct
      solve of the same system, for C and C'; the certificate must reach 1e-9.
  V3  the certificate is an upper bound at EVERY iterate, not only at convergence, and
      the energy of every iterate is above the direct solution (an inexact solve only
      raises the energy). Its looseness is reported.
  V4  the implementation matches the code already reviewed: problem C bit for bit against
      static_capacitance.static_capacitance, problem C' against
      spectral.port_constrained_energy; and on a cell small enough for every eigenpair,
      Palace's sheet-port pencil satisfies N = 1 and sum p/lambda = L C'_h.
  V5  negative controls: (a) a truncated solve is not certified; (b) the certificate's
      precondition matters: on the grounded cell A >= c M_ff and M_ff >= D_m hold; on a
      bar held only at its two ends the precondition is reported, A >= c M_ff fails, and
      a lowest-mode perturbation has a true energy excess the formula UNDERSTATES;
      (c) a non-nested prolongation is caught by the Galerkin check, and the certificate
      still holds; (d) an indefinite preconditioner ends in BREAKDOWN, never CERTIFIED;
      (e) a zero initial guess still certifies the same energy; (f) a perturbed solution
      has a higher energy and the certificate covers the increase.

Usage: verify_solver.py --out solver_verification.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import scipy.linalg as sla
import scipy.sparse as sp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nested_solver as ns  # noqa: E402
import synthetic_cells as syn  # noqa: E402

af = ns.af
SMALL = {"h0": 0.1, "q": 3.0, "hmax": 1.0, "split_port": True}
MEDIUM = {"h0": 0.06, "q": 2.0, "hmax": 0.6}


def _module(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, HERE.parent / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def p1_mass(mesh: dict, xyz_nd) -> sp.csr_matrix:
    """The consistent P1 mass matrix, int phi_i phi_j = vol (1 + d_ij) / 20 per element."""
    _, vol = af._tet_geometry(xyz_nd, mesh["tets"])
    loc = (np.ones((4, 4)) + np.eye(4))[None] * (vol / 20.0)[:, None, None]
    t = mesh["tets"]
    n = len(xyz_nd)
    return sp.coo_matrix((loc.ravel(), (np.repeat(t, 4, axis=1).ravel(), np.tile(t, (1, 4)).ravel())),
                         shape=(n, n)).tocsr()


def _ladder(mesh, model, levels, kinds=ns.KINDS):
    out = [ns.Level(mesh, model, kinds)]
    for _ in range(levels):
        mesh = af.refine_red(mesh)
        out.append(ns.Level(mesh, model, kinds))
    return out


def _agree(a: dict, b: dict) -> dict:
    """Two energies of the same discrete problem must lie within their summed bounds."""
    diff = abs(a["energy_nd"] - b["energy_nd"])
    allow = a["total_error_bound_nd"] + b["total_error_bound_nd"]
    return {"abs_diff_nd": diff, "allowed_nd": allow, "rel_diff": diff / b["energy_nd"],
            "within_bounds": bool(diff <= allow)}


def v1_exact() -> dict:
    mesh, model, profile, E_exact = syn.layered_box(4)
    rows, prev, prev_phi = [], None, None
    for level in range(3):
        L = ns.Level(mesh, model, kinds=())
        L.dd["exact"] = syn.exact_dirichlet(mesh, profile)
        pre = ns.certificate_preconditions(L, ns.boundary_facts(mesh))
        rd, phid = ns.solve(L, "exact", "direct")
        row = {"level": level, "n_unknowns": rd["n_unknowns"], "preconditions_failed": pre,
               "direct_rel_err": abs(rd["energy_nd"] - E_exact) / E_exact,
               "direct_bound_rel": rd["total_error_bound_rel"]}
        if prev is not None:
            # the prolonged coarse solution is already exact here, so also start from zero
            for start, cphi in (("prolonged", prev_phi), ("zero", np.zeros_like(prev_phi))):
                rt, _ = ns.solve(L, "exact", "twogrid", coarse=prev, coarse_phi=cphi)
                row[f"twogrid_{start}"] = {
                    "rel_err": abs(rt["energy_nd"] - E_exact) / E_exact,
                    "bound_rel": rt["total_error_bound_rel"], "status": rt["solver"]["status"],
                    "iterations": rt["solver"]["iterations"],
                    "error_within_bound": bool(abs(rt["energy_nd"] - E_exact)
                                               <= rt["total_error_bound_nd"] + rd["total_error_bound_nd"]
                                               + abs(rd["energy_nd"] - E_exact))}
        rows.append(row)
        prev, prev_phi = L, phid
        mesh = af.refine_red(mesh)
    return {"E_exact_nd": E_exact, "rows": rows}


def v2_level2(cell: dict) -> dict:
    mesh, model = syn.chip_cell(**cell)
    lv = _ladder(mesh, model, 2)
    out = {"cell": cell, "tets": [int(len(L.mesh["tets"])) for L in lv],
           "preconditions_failed": [ns.certificate_preconditions(L, ns.boundary_facts(L.mesh))
                                    for L in lv]}
    for kind in ns.KINDS:
        r0, p0 = ns.solve(lv[0], kind, "direct")
        r1, p1 = ns.solve(lv[1], kind, "direct")
        t = time.monotonic()
        rt, _ = ns.solve(lv[2], kind, "twogrid", coarse=lv[1], coarse_phi=p1)
        tt = time.monotonic() - t
        t = time.monotonic()
        rd, _ = ns.solve(lv[2], kind, "direct")
        td = time.monotonic() - t
        out[kind] = {"C_fF_levels_012": [r0["C_fF"], r1["C_fF"], rd["C_fF"]],
                     "n_unknowns_level2": rd["n_unknowns"],
                     "twogrid": {k: rt["solver"][k] for k in ("status", "iterations",
                                                               "galerkin_identity_rel",
                                                               "fixed_rows_from_free_coarse_nnz")},
                     "twogrid_bound_rel": rt["total_error_bound_rel"],
                     "direct_bound_rel": rd["total_error_bound_rel"],
                     "agreement": _agree(rt, rd), "wall_s_twogrid": tt, "wall_s_direct": td,
                     "port_voltage": [r0["port_voltage"], r1["port_voltage"], rt["port_voltage"]]}
    return out


def v3_every_iterate(cell: dict) -> dict:
    """Audit the certificate at every PCG iterate against the direct solution."""
    mesh, model = syn.chip_cell(**cell)
    lv = _ladder(mesh, model, 1)
    out = {}
    for kind in ns.KINDS:
        _, p0 = ns.solve(lv[0], kind, "direct")
        rd, _ = ns.solve(lv[1], kind, "direct")
        L, dd = lv[1], lv[1].dd[kind]
        sysm = ns.system(L.K, dd)
        Pfull = ns.prolongation(lv[0].mesh, L.mesh)
        P = Pfull[dd["free"]][:, lv[0].dd[kind]["free"]].tocsr()
        tg = ns.TwoGrid(sysm["A"], P, ns.SOLVER["nu"])
        m_free, c = L.m[dd["free"]], L.poincare["c"]
        work, audit = dd["phi"].copy(), []

        def certify(x):
            work[dd["free"]] = x
            E = float(work @ (L.K @ work))
            bnd = ns.certificate(sysm, x, m_free, c)["error_bound_nd"]
            excess = E - rd["energy_nd"]
            audit.append({"energy_excess_nd": excess, "bound_nd": bnd})
            return bnd / (E - bnd) if E > bnd else math.inf

        for start in ("prolonged", "zero"):
            audit.clear()
            x0 = ((Pfull @ p0)[dd["free"]] if start == "prolonged"
                  else np.zeros(len(dd["free"])))
            _, it = ns.pcg(sysm["A"], sysm["b"], x0, tg, maxiter=200, check_every=1,
                           target_rel=1e-13, stagnation_checks=30, certify=certify)
            slack = rd["total_error_bound_nd"]
            ok = all(a["bound_nd"] + slack >= a["energy_excess_nd"] for a in audit)
            above = all(a["energy_excess_nd"] >= -slack for a in audit)
            ratios = [a["bound_nd"] / a["energy_excess_nd"] for a in audit
                      if a["energy_excess_nd"] > 1e3 * slack]
            out[f"{kind}_{start}"] = {
                "status": it["status"], "iterations": it["iterations"], "iterates_audited": len(audit),
                "bound_holds_at_every_iterate": bool(ok),
                "every_iterate_energy_at_or_above_direct": bool(above),
                "bound_over_true_excess_min_median_max": (
                    [float(min(ratios)), float(np.median(ratios)), float(max(ratios))] if ratios else None)}
    return out


def v4_consistency() -> dict:
    sc = _module("static-anchor-hypothesis/static_capacitance.py", "sah_static")
    spc = _module("static-band-pairing/spectral.py", "sbp_spectral")
    out = {}
    for name, cell in (("small", SMALL), ("medium", MEDIUM)):
        mesh, model = syn.chip_cell(**cell)
        L = ns.Level(mesh, model)
        rC, _ = ns.solve(L, "C", "direct")
        rP, _ = ns.solve(L, "Cprime", "direct")
        ref_C = sc.static_capacitance(mesh, **model)
        ref_P = spc.port_constrained_energy(mesh, model)
        out[name] = {"C_bit_identical_to_static_capacitance": rC["energy_nd"] == ref_C["energy_nd"],
                     "Cprime_bit_identical_to_spectral": rP["energy_nd"] == ref_P,
                     "delta": rP["energy_nd"] / rC["energy_nd"] - 1.0}
    # every eigenpair of Palace's sheet-port pencil on the small cell (dense)
    mesh, model = syn.chip_cell(**SMALL)
    s = af.assemble_edge_system(mesh, **model)
    xyz, edges, Lnd = s["scales"]["xyz_nd"], s["edges"], s["scales"]["L_nd"]
    _, t2e = af.edge_table(mesh)
    K = spc.curl_curl(mesh, xyz, edges, t2e) + spc.sheet_port(
        mesh, xyz, edges, model["port_attr"], Lnd, s["port"]["w_nd"], s["port"]["l_nd"])
    lam, E = spc.all_modes(K, s["M_all"], s["free"])
    mo = spc.moments(lam, E, s["f_free"], Lnd)
    L = ns.Level(mesh, model)
    rP, _ = ns.solve(L, "Cprime", "direct")
    rC, _ = ns.solve(L, "C", "direct")
    out["dense_sheet_identity_small_cell"] = {
        "free_edges": int(len(s["free"])), "N_minus_1": mo["N"] - 1.0,
        "sum_p_over_lambda_over_L_Cprime_minus_1": mo["inv_moment"] / (Lnd * rP["energy_nd"]) - 1.0,
        "delta": rP["energy_nd"] / rC["energy_nd"] - 1.0,
        "S_over_H_minus_1_from_spectrum": mo["inv_moment"] / (Lnd * rC["energy_nd"]) - 1.0}
    return out


def v5_negative() -> dict:
    out = {}
    mesh, model = syn.chip_cell(**SMALL)
    lv = _ladder(mesh, model, 1)
    _, p0 = ns.solve(lv[0], "C", "direct")
    rd, pd = ns.solve(lv[1], "C", "direct")
    # (a) truncated
    rt, _ = ns.solve(lv[1], "C", "twogrid", coarse=lv[0], coarse_phi=p0,
                     settings={"maxiter": 2, "check_every": 1})
    out["a_truncated"] = {"status": rt["solver"]["status"],
                          "bound_rel": rt["total_error_bound_rel"],
                          "certified_at_1e-9": bool(rt["total_error_bound_rel"] <= 1e-9),
                          "error_within_bound": bool(rt["energy_nd"] - rd["energy_nd"]
                                                     <= rt["total_error_bound_nd"] + rd["total_error_bound_nd"])}
    # (b) the precondition and the inequality chain it protects: A >= c M_ff (Poincare on
    # the box) and M_ff >= D_m. On the grounded cell both hold. On a bar held only at its
    # two ends (side walls free) the precondition is reported, A >= c M_ff fails, and an
    # admissible vector exists whose true energy excess the "certificate" UNDERSTATES.
    rows = {}
    bar = syn.tensor_mesh(np.linspace(0, 1, 11), np.linspace(0, 0.1, 3), np.linspace(0, 0.1, 3))
    bar_mesh = {"xyz": bar["xyz"], "tets": bar["tets"], "tet_attr": bar["tet_attr"],
                "tris": bar["faces"][bar["boundary"]],
                "tri_attr": np.full(int(bar["boundary"].sum()), 2)}
    bar_model = {"eps_r": {1: 1.0}, "pec_attrs": (2,), "port_attr": 10,
                 "direction": (1.0, 0.0, 0.0), "L0_m": 1.0e-3, "L_H": 1.0e-8}
    Lb = ns.Level(bar_mesh, bar_model, kinds=())
    xb = bar_mesh["xyz"][:, 0]
    fixed = (xb < 1e-12) | (xb > 1 - 1e-12)
    Lb.dd["ends"] = {"fixed": fixed, "phi": np.where(xb > 0.5, 1.0, 0.0) * fixed,
                     "free": np.flatnonzero(~fixed), "geo": None}
    for name, L, kind in (("grounded_cell", ns.Level(*syn.chip_cell(**SMALL), kinds=("C",)), "C"),
                          ("bar_free_sides", Lb, "ends")):
        dd = L.dd[kind]
        f = dd["free"]
        A = L.K[f][:, f].toarray()
        M = p1_mass(L.mesh, L.xyz)[f][:, f].toarray()
        Dm = L.m[f]
        c = L.poincare["c"]
        lam_AM = float(sla.eigh(A, M, eigvals_only=True, subset_by_index=[0, 0])[0])
        lam_AD, vec = sla.eigh(A, np.diag(Dm), subset_by_index=[0, 0])
        row = {"preconditions_failed": ns.certificate_preconditions(L, ns.boundary_facts(L.mesh)),
               "c": c, "min_eig_A_over_M": lam_AM, "min_eig_A_over_Dm": float(lam_AD[0]),
               "min_eig_M_minus_Dm": float(np.linalg.eigvalsh(M - np.diag(Dm)).min()),
               "poincare_step_A_ge_cM_holds": bool(lam_AM >= c)}
        sysm = ns.system(L.K, dd)
        xs = ns.solve_direct(sysm)
        work = dd["phi"].copy()
        work[f] = xs
        E0 = float(work @ (L.K @ work))
        work[f] = xs + 1e-3 * vec[:, 0] / np.abs(vec[:, 0]).max()
        excess = float(work @ (L.K @ work)) - E0
        bnd = ns.certificate(sysm, work[f], L.m[f], c)["error_bound_nd"]
        row.update({"lowest_mode_perturbation_excess_nd": excess, "certificate_nd": bnd,
                    "certificate_covers_excess": bool(bnd >= excess)})
        rows[name] = row
    out["b_precondition"] = rows
    # (c) a non-nested prolongation: Galerkin check fails, certificate still valid
    L, dd = lv[1], lv[1].dd["C"]
    sysm = ns.system(L.K, dd)
    Pfull = ns.prolongation(lv[0].mesh, L.mesh)
    P = Pfull[dd["free"]][:, lv[0].dd["C"]["free"]].tocsr()
    rng = np.random.default_rng(3)
    P_bad = P.copy()
    P_bad.data = P_bad.data * rng.uniform(0.5, 1.5, P_bad.nnz)
    tg = ns.TwoGrid(sysm["A"], P_bad, ns.SOLVER["nu"])
    Acoarse = lv[0].K[lv[0].dd["C"]["free"]][:, lv[0].dd["C"]["free"]]
    m_free, c = L.m[dd["free"]], L.poincare["c"]
    work = dd["phi"].copy()

    def certify(x):
        work[dd["free"]] = x
        E = float(work @ (L.K @ work))
        b = ns.certificate(sysm, x, m_free, c)["error_bound_nd"]
        return b / (E - b) if E > b else math.inf

    x, it = ns.pcg(sysm["A"], sysm["b"], (Pfull @ p0)[dd["free"]], tg, maxiter=1000,
                   check_every=5, target_rel=1e-12, stagnation_checks=20, certify=certify)
    work[dd["free"]] = x
    E = float(work @ (L.K @ work))
    out["c_non_nested_P"] = {"galerkin_identity_rel": float(abs(tg.Ac - Acoarse).max() / abs(Acoarse).max()),
                             "status": it["status"], "iterations": it["iterations"],
                             "energy_rel_diff_vs_direct": (E - rd["energy_nd"]) / rd["energy_nd"]}
    # (d) an indefinite preconditioner
    _, it = ns.pcg(sysm["A"], sysm["b"], np.zeros(len(dd["free"])), lambda r: -r, maxiter=50,
                   check_every=5, target_rel=1e-12, stagnation_checks=20, certify=certify)
    out["d_indefinite_preconditioner"] = {"status": it["status"], "iterations": it["iterations"]}
    # (e) zero initial guess
    tg = ns.TwoGrid(sysm["A"], P, ns.SOLVER["nu"])
    x, it = ns.pcg(sysm["A"], sysm["b"], np.zeros(len(dd["free"])), tg, maxiter=1000,
                   check_every=5, target_rel=1e-12, stagnation_checks=20, certify=certify)
    work[dd["free"]] = x
    E = float(work @ (L.K @ work))
    out["e_zero_initial_guess"] = {"status": it["status"], "iterations": it["iterations"],
                                   "energy_rel_diff_vs_direct": (E - rd["energy_nd"]) / rd["energy_nd"]}
    # (f) a perturbed solution
    xd = pd[dd["free"]]
    xp = xd + 1e-6 * rng.standard_normal(len(xd))
    work[dd["free"]] = xp
    Ep = float(work @ (L.K @ work))
    bnd = ns.certificate(sysm, xp, m_free, c)["error_bound_nd"]
    out["f_perturbed"] = {"energy_increase_nd": Ep - rd["energy_nd"], "bound_nd": bnd,
                          "increase_positive": bool(Ep > rd["energy_nd"]),
                          "bound_covers_increase": bool(bnd + rd["total_error_bound_nd"]
                                                        >= Ep - rd["energy_nd"])}
    return out


def run() -> dict:
    ns.require_extended_precision()
    t0 = time.monotonic()
    res = {"record": "solver verification on synthetic cases only; no QMHP data read",
           "solver_settings": ns.SOLVER, "V1_exact_known_answer": v1_exact(),
           "V2_level2_small": v2_level2(SMALL), "V2_level2_medium": v2_level2(MEDIUM),
           "V3_every_iterate": v3_every_iterate(MEDIUM), "V4_consistency": v4_consistency(),
           "V5_negative_controls": v5_negative(), "qmhp_data_read": False}
    res["wall_s"] = time.monotonic() - t0
    import study_driver  # noqa: PLC0415 - provenance only
    res["environment"] = study_driver._environment(study_driver.EVIDENCE_CODE)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    text = json.dumps(run(), indent=1, default=float)
    if a.out:
        Path(a.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
