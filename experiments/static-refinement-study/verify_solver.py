# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Verification of the study's solvers and certificate on SYNTHETIC cases only.

No QMHP data is read. Run before anything touches the QMHP mesh; the committed output is
solver_verification.json. Each check states what would make it fail.

  V1  continuum known answer (ACCURACY only): a layered box whose exact potential P1
      reproduces; direct and two-grid (also from a zero start) must return the continuum
      energy to 1e-12. The difference includes assembly round-off, which the certificate
      does not cover, so this row does not test the certificate.
  V1b the total bound against TRUTH for the discrete problem: the exact rational minimum of
      the assembled quadratic form, with non-linear boundary data; direct and two-grid. At
      these converged solutions the total is dominated by the evaluation bound (reported
      separately), so V1b does NOT test the residual certificate; V1c does.
  V1c the RESIDUAL certificate against the exact rational energy excess: (i) at every PCG
      iterate from a zero start and (ii) at a perturbation along the lowest mode of
      (A_s, D_m), where the certificate is tightest; with the margin, and a negative control
      (the constant c inflated beyond the margin) that must fail.
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
      has a higher energy and the certificate covers the increase; (g) a FOLDED mesh that
      passes conformity, tagging and constrained-boundary checks is caught by the tiling
      checks, and the formula would understate its error; (h) the stagnation rule: finite
      certificates without a 10 % improvement stop it, infinite ones with a decreasing true
      residual do not, infinite ones with a flat true residual do.
  V6  the evaluation-error bound against the exact rational value of phi^T K phi: the
      extended-precision value against its ANALYTIC terms alone (matrix-vector and dot),
      with a negative control (the same evaluation in float64 violates them), and the
      float64 energy against the total.
  V7  the uncertified assembly round-off: an extended-precision re-assembly, the Gershgorin
      estimate of rho/c (Poincare step), the first-order energy effect against its
      max|phi|^2 sum|dK| estimate, and on the layered box the known-answer discrepancy of V1
      explained by it.

Usage: verify_solver.py --out solver_verification.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from fractions import Fraction
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


def _exact_min_energy(K, phi, fixed) -> Fraction:
    """The exact minimum of phi^T K phi (the symmetric part of the assembled K, in rational
    arithmetic) over the free nodes, with phi fixed elsewhere. Small problems only."""
    Kd = K.toarray()
    n = len(Kd)
    Ks = [[(Fraction(Kd[i, j]) + Fraction(Kd[j, i])) / 2 for j in range(n)] for i in range(n)]
    fr = [i for i in range(n) if not fixed[i]]
    fx = [i for i in range(n) if fixed[i]]
    p = [Fraction(float(v)) for v in phi]
    A = [[Ks[i][j] for j in fr] for i in fr]
    b = [-sum(Ks[i][j] * p[j] for j in fx) for i in fr]
    m = len(fr)
    for c in range(m):                                     # Gaussian elimination, exact
        piv = next(r for r in range(c, m) if A[r][c] != 0)
        A[c], A[piv], b[c], b[piv] = A[piv], A[c], b[piv], b[c]
        for r in range(c + 1, m):
            if A[r][c] != 0:
                f = A[r][c] / A[c][c]
                A[r] = [a - f * q for a, q in zip(A[r], A[c])]
                b[r] -= f * b[c]
    x = [Fraction(0)] * m
    for c in range(m - 1, -1, -1):
        x[c] = (b[c] - sum(A[c][j] * x[j] for j in range(c + 1, m))) / A[c][c]
    for k, i in enumerate(fr):
        p[i] = x[k]
    return sum(p[i] * Ks[i][j] * p[j] for i in range(n) for j in range(n))


def _exact_quadratic(K, phi) -> Fraction:
    """phi^T K phi in exact rational arithmetic from the float64 data."""
    Kc = K.tocoo()
    p = [Fraction(float(v)) for v in phi]
    return sum(Fraction(float(v)) * p[i] * p[j] for i, j, v in zip(Kc.row, Kc.col, Kc.data))


def _v1b_cell():
    """A layered 2x2x2 box with non-linear boundary data (so the discrete solution is not
    trivially exact) at levels 0 (1 unknown) and 1 (27 unknowns)."""
    xs = np.linspace(0.0, 1.0, 3)
    tm = syn.tensor_mesh(xs, xs, xs)
    mesh = {"xyz": tm["xyz"], "tets": tm["tets"],
            "tet_attr": np.where(tm["xyz"][tm["tets"]][:, :, 2].mean(1) < 0.5, 1, 3),
            "tris": tm["faces"][tm["boundary"]], "tri_attr": np.full(int(tm["boundary"].sum()), 2)}
    model = {"eps_r": {1: 2.0, 3: 5.0}, "pec_attrs": (2,), "port_attr": 10,
             "direction": (0.0, 0.0, 1.0), "L0_m": 1.0e-3, "L_H": 1.0e-8}
    g = lambda x: x[:, 2] + 0.3 * np.sin(np.pi * x[:, 0]) * np.sin(np.pi * x[:, 1])

    def data(m):
        bn = ns.boundary_facts(m)["boundary_nodes"]
        fixed = np.zeros(len(m["xyz"]), dtype=bool)
        fixed[bn] = True
        phi = np.where(fixed, g(m["xyz"]), 0.0)
        used = np.unique(m["tets"])
        return {"fixed": fixed, "phi": phi, "free": used[~fixed[used]], "geo": None}

    L0 = ns.Level(mesh, model, kinds=())
    L0.dd["g"] = data(mesh)
    fine = af.refine_red(mesh)
    L1 = ns.Level(fine, model, kinds=())
    L1.dd["g"] = data(fine)
    return L0, L1


def v1b_certificate_against_exact_discrete_minimum() -> dict:
    """The total bound against TRUTH for the discrete problem: the exact rational minimum of
    the assembled quadratic form, on _v1b_cell; direct and two-grid from zero. The residual
    and evaluation parts are reported separately."""
    L0, L1 = _v1b_cell()
    _, p0 = ns.solve(L0, "g", "direct")
    rows = {}
    for name, (L, method, kw) in {"level0_direct": (L0, "direct", {}),
                                  "level1_direct": (L1, "direct", {}),
                                  "level1_twogrid_from_zero": (L1, "twogrid",
                                                               {"coarse": L0, "coarse_phi": np.zeros_like(p0)})}.items():
        r, _ = ns.solve(L, "g", method, **kw)
        Eh = _exact_min_energy(L.K, L.dd["g"]["phi"], L.dd["g"]["fixed"])
        err = abs(Fraction(r["energy_nd"]) - Eh)
        rows[name] = {"preconditions_failed": ns.certificate_preconditions(L, ns.boundary_facts(L.mesh, L.xyz)),
                      "n_unknowns": r["n_unknowns"], "energy_nd": r["energy_nd"],
                      "exact_discrete_minimum": float(Eh), "abs_error": float(err),
                      "total_bound_nd": r["total_error_bound_nd"],
                      "residual_certificate_nd": r["certificate"]["error_bound_nd"],
                      "evaluation_bound_nd": r["evaluation_error_bound_nd"],
                      "evaluation_float64_vs_extended_nd": r["evaluation_bound_terms_nd"]["float64_vs_extended"],
                      "within_certificate": bool(err <= Fraction(r["total_error_bound_nd"])),
                      "at_or_above_minimum_up_to_evaluation": bool(
                          Fraction(r["energy_nd"]) >= Eh - Fraction(r["evaluation_error_bound_nd"]))}
    return rows


def _frac(x) -> Fraction:
    return Fraction(*x.as_integer_ratio())


def v1c_residual_certificate_against_exact_excess(inflate: float = 1.0) -> dict:
    """The RESIDUAL certificate alone against the exact energy excess E(x) - E_h (both in
    rational arithmetic from the float data) on the 27-unknown level of _v1b_cell. ``inflate``
    multiplies c: 1 is the certificate; a value above the reported margin is the negative
    control and must fail."""
    L0, L1 = _v1b_cell()
    dd = L1.dd["g"]
    f = dd["free"]
    Eh = _exact_min_energy(L1.K, dd["phi"], dd["fixed"])
    sysm = ns.system(L1.K, dd)
    m, c = L1.m[f], inflate * L1.poincare["c"]

    def check(x):
        phi = dd["phi"].copy()
        phi[f] = x
        excess = _exact_quadratic(L1.K, phi) - Eh
        bound = ns.certificate(sysm, x, m, c)["error_bound_nd"]
        return float(excess), bound, bool(Fraction(bound) >= excess)

    # (i) every PCG iterate from zero with the two-grid preconditioner
    Pfull = ns.prolongation(L0.mesh, L1.mesh)
    P = Pfull[f][:, L0.dd["g"]["free"]].tocsr()
    tg = ns.TwoGrid(sysm["A"], P, ns.SOLVER["nu"])
    rows = []
    ns.pcg(sysm["A"], sysm["b"], np.zeros(len(f)), tg, maxiter=12, check_every=1,
           target_rel=0.0, stagnation_checks=100,
           certify=lambda x: (rows.append(check(x)), (math.inf, 0.0))[1])
    iterates = [r for r in rows if r[0] > 0]
    # (ii) the direct solution plus a perturbation along the lowest mode of (A_s, D_m)
    A = sysm["A"].toarray()
    _, vec = sla.eigh(0.5 * (A + A.T), np.diag(m), subset_by_index=[0, 0])
    xd = ns.solve_direct(sysm)
    low = check(xd + 1e-3 * vec[:, 0] / np.abs(vec[:, 0]).max())
    return {"c_inflated_by": inflate, "n_unknowns": int(len(f)),
            "iterates_audited": len(iterates),
            "bound_covers_exact_excess_at_every_iterate": all(r[2] for r in iterates),
            "bound_over_exact_excess_iterates_min_max": [min(r[1] / r[0] for r in iterates),
                                                         max(r[1] / r[0] for r in iterates)],
            "lowest_mode": {"exact_excess_nd": low[0], "certificate_nd": low[1],
                            "margin": low[1] / low[0], "bound_covers_exact_excess": low[2]}}


def v6_evaluation_bound() -> dict:
    """The evaluation-error bound against the EXACT rational value of phi^T K phi for the
    float64 data, on the small cell at levels 0 and 1: at the solution, and at the solution
    shifted by 1e3 (heavy cancellation: 1^T K 1 vanishes up to round-off, so terms of size
    1e6 |K| cancel). Two claims are checked separately: the float64 energy's total bound,
    and the extended value against the ANALYTIC terms alone (matrix-vector and dot). The
    negative control evaluates in float64 against the same analytic terms; on the shifted
    rows it must violate them. Also the size against the worst-case bound it replaces."""
    mesh, model = syn.chip_cell(**SMALL)
    lv = _ladder(mesh, model, 1)
    out = {}
    for h, L in enumerate(lv):
        for kind in ns.KINDS:
            r, phi0 = ns.solve(L, kind, "direct")
            for tag, phi in (("", phi0), ("_shifted_1e3", phi0 + 1e3)):
                en = ns.energy(L.K, phi)
                exact = _exact_quadratic(L.K, phi)
                err = abs(Fraction(en["energy_nd"]) - exact)
                k = int(np.diff(L.K.tocsr().indptr).max())
                old = ns.gamma(len(phi) + k, ns.ULD) * float(np.abs(phi) @ (abs(L.K) @ np.abs(phi)))
                s_ld, t_mv, t_dot = ns.extended_energy(L.K, phi)
                ext_err = abs(_frac(s_ld) - exact)
                s_64, _, _ = ns.extended_energy(L.K, phi, dtype=np.float64)   # negative control
                f64_err = abs(_frac(s_64) - exact)
                analytic = Fraction(t_mv) + Fraction(t_dot)
                out[f"level{h}_{kind}{tag}"] = {
                    "float64_abs_error_vs_exact": float(err),
                    "evaluation_bound_nd": en["evaluation_error_bound_nd"],
                    "bound_covers_error": bool(err <= Fraction(en["evaluation_error_bound_nd"])),
                    "terms_nd": en["evaluation_bound_terms_nd"],
                    "extended_abs_error_vs_exact": float(ext_err),
                    "analytic_terms_nd": float(analytic),
                    "analytic_terms_cover_extended_error": bool(ext_err <= analytic),
                    "negative_control_float64_evaluation_abs_error": float(f64_err),
                    "negative_control_violates_the_analytic_terms": bool(f64_err > analytic),
                    "previous_worst_case_bound_nd": old,
                    "tightening_factor_total": old / en["evaluation_error_bound_nd"],
                    "tightening_factor_analytic_terms": old / float(analytic)}
    return out


def v7_assembly_term() -> dict:
    """The uncertified assembly round-off on synthetic ladders (module docstring)."""
    out = {}
    mesh, model, profile, E_exact = syn.layered_box(4)
    cells = [("layered_box", mesh, model, profile, E_exact),
             ("chip_small", *syn.chip_cell(**SMALL), None, None)]
    for name, mesh, model, profile, E_exact in cells:
        rows = []
        for level in range(3):
            if profile is not None:
                L = ns.Level(mesh, model, kinds=())
                L.dd["x"] = syn.exact_dirichlet(mesh, profile)
                kinds = ("x",)
            else:
                L = ns.Level(mesh, model)
                kinds = ns.KINDS
            gap = ns.assembly_gap(L)
            Kl = ns.stiffness_extended(L.mesh, L.xyz, model["eps_r"])
            dK = L.K.astype(np.longdouble) - Kl
            row = {"level": level, "n_tets": int(len(mesh["tets"])), "gap": gap, "problems": {}}
            for kind in kinds:
                r, phi = ns.solve(L, kind, "direct")
                pl = phi.astype(np.longdouble)
                first = float(pl @ (dK @ pl)) / r["energy_nd"]
                est = r["phi_abs_max"] ** 2 * gap["abs_sum_nd"] / r["energy_nd"]
                q = {"first_order_effect_rel": first, "estimate_rel": est,
                     "estimate_covers_first_order_effect": bool(abs(first) <= est),
                     "certified_total_rel": r["total_error_bound_rel"]}
                if E_exact is not None:
                    q["direct_rel_err_vs_continuum"] = (r["energy_nd"] - E_exact) / E_exact
                    q["continuum_minus_first_order_effect_rel"] = (
                        (r["energy_nd"] - E_exact) / E_exact - first)
                row["problems"][kind] = q
            rows.append(row)
            mesh = af.refine_red(mesh)
        out[name] = rows
    return out


def v1_exact() -> dict:
    mesh, model, profile, E_exact = syn.layered_box(4)
    rows, prev, prev_phi = [], None, None
    for level in range(3):
        L = ns.Level(mesh, model, kinds=())
        L.dd["exact"] = syn.exact_dirichlet(mesh, profile)
        pre = ns.certificate_preconditions(L, ns.boundary_facts(mesh, L.xyz))
        rd, phid = ns.solve(L, "exact", "direct")
        row = {"level": level, "n_unknowns": rd["n_unknowns"], "preconditions_failed": pre,
               "direct_rel_err_vs_continuum": abs(rd["energy_nd"] - E_exact) / E_exact,
               "direct_bound_rel": rd["total_error_bound_rel"]}
        if prev is not None:
            # the prolonged coarse solution is already exact here, so also start from zero
            for start, cphi in (("prolonged", prev_phi), ("zero", np.zeros_like(prev_phi))):
                rt, _ = ns.solve(L, "exact", "twogrid", coarse=prev, coarse_phi=cphi)
                row[f"twogrid_{start}"] = {
                    "rel_err_vs_continuum": abs(rt["energy_nd"] - E_exact) / E_exact,
                    "bound_rel": rt["total_error_bound_rel"], "status": rt["solver"]["status"],
                    "iterations": rt["solver"]["iterations"]}
        rows.append(row)
        prev, prev_phi = L, phid
        mesh = af.refine_red(mesh)
    return {"E_exact_nd": E_exact, "rows": rows}


def v2_level2(cell: dict) -> dict:
    mesh, model = syn.chip_cell(**cell)
    lv = _ladder(mesh, model, 2)
    out = {"cell": cell, "tets": [int(len(L.mesh["tets"])) for L in lv],
           "preconditions_failed": [ns.certificate_preconditions(L, ns.boundary_facts(L.mesh, L.xyz))
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
            ce = ns.certificate(sysm, x, m_free, c)
            bnd = ce["error_bound_nd"]
            excess = E - rd["energy_nd"]
            audit.append({"energy_excess_nd": excess, "bound_nd": bnd})
            return (bnd / (E - bnd) if E > bnd else math.inf), ce["residual_2norm"]

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
        row = {"preconditions_failed": ns.certificate_preconditions(L, ns.boundary_facts(L.mesh, L.xyz)),
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
        ce = ns.certificate(sysm, x, m_free, c)
        b = ce["error_bound_nd"]
        return (b / (E - b) if E > b else math.inf), ce["residual_2norm"]

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
    # (g) a folded mesh: conforming, every boundary face tagged and constrained, yet the
    # tetrahedra overlap. The tiling checks must report it, and the bound formula would
    # understate a real error there.
    fm, fmodel = syn.folded_box(3.0, 6)
    Lf = ns.Level(fm, fmodel, kinds=())
    bff = ns.boundary_facts(fm, Lf.xyz)
    xf = fm["xyz"]
    fixed = np.zeros(len(xf), dtype=bool)
    fixed[bff["boundary_nodes"]] = True
    Lf.dd["walls"] = {"fixed": fixed, "phi": np.where(fixed, xf[:, 0], 0.0),
                      "free": np.flatnonzero(~fixed), "geo": None}
    f = Lf.dd["walls"]["free"]
    A = Lf.K[f][:, f].toarray()
    lam, vec = sla.eigh(A, np.diag(Lf.m[f]), subset_by_index=[0, 0])
    sysm_f = ns.system(Lf.K, Lf.dd["walls"])
    xs = ns.solve_direct(sysm_f)
    wf = Lf.dd["walls"]["phi"].copy()
    wf[f] = xs
    E0 = float(wf @ (Lf.K @ wf))
    wf[f] = xs + 1e-3 * vec[:, 0] / np.abs(vec[:, 0]).max()
    excess = float(wf @ (Lf.K @ wf)) - E0
    bnd_f = ns.certificate(sysm_f, wf[f], Lf.m[f], Lf.poincare["c"])["error_bound_nd"]
    out["g_folded_mesh"] = {"mesh_facts": {k: bff[k] for k in (
        "max_face_multiplicity", "every_boundary_face_is_tagged",
        "every_interior_face_separates_its_tetrahedra", "every_boundary_face_on_the_box_surface",
        "volume_sum_over_box_minus_1")},
        "preconditions_failed": ns.certificate_preconditions(Lf, bff),
        "min_eig_A_over_Dm": float(lam[0]), "c": Lf.poincare["c"],
        "lowest_mode_perturbation_excess_nd": excess, "certificate_nd": bnd_f,
        "certificate_covers_excess": bool(bnd_f >= excess)}
    # (h) the stagnation rule: finite checks against the best finite certificate, infinite
    # ones against the best true residual among infinite checks
    n = 3000
    Aq = sp.diags(np.linspace(1.0, 50.0, n)).tocsr()
    bq = np.ones(n)
    runs = {}
    for name, seq in (("inf_30_residual_falling_then_converging",
                       [(math.inf, 0.8 ** i) for i in range(30)] + [(1e-3, 1e-4), (1e-6, 1e-7), (1e-13, 1e-9)]),
                      ("inf_flat_residual", [(math.inf, 0.5)] * 40),
                      ("finite_flat", [(1e-3, 0.5)] * 40)):
        it_seq = iter(seq)
        _, it = ns.pcg(Aq, bq, np.zeros(n), lambda r: r, maxiter=500, check_every=1,
                       target_rel=1e-12, stagnation_checks=20,
                       certify=lambda x: next(it_seq, (1e-3, 0.5)))
        runs[name] = {"status": it["status"], "iterations": it["iterations"]}
    # a real stuck solve: a semidefinite preconditioner that never updates 30 % of the
    # unknowns, so the certificate stays infinite and the true residual flat
    dd1 = lv[1].dd["C"]
    sysm1 = ns.system(lv[1].K, dd1)
    P1 = ns.prolongation(lv[0].mesh, lv[1].mesh)[dd1["free"]][:, lv[0].dd["C"]["free"]].tocsr()
    tg1 = ns.TwoGrid(sysm1["A"], P1, ns.SOLVER["nu"])
    mask = (rng.uniform(size=len(dd1["free"])) > 0.3).astype(float)
    m1, c1 = lv[1].m[dd1["free"]], lv[1].poincare["c"]
    w1 = dd1["phi"].copy()

    def certify1(x):
        w1[dd1["free"]] = x
        E = float(w1 @ (lv[1].K @ w1))
        ce = ns.certificate(sysm1, x, m1, c1)
        b = ce["error_bound_nd"]
        return (b / (E - b) if E > b else math.inf), ce["residual_2norm"]

    _, it = ns.pcg(sysm1["A"], sysm1["b"], np.zeros(len(dd1["free"])), lambda r: mask * tg1(mask * r),
                   **{k: ns.SOLVER[k] for k in ("maxiter", "check_every", "target_rel", "stagnation_checks")},
                   certify=certify1)
    runs["stuck_solve_masked_preconditioner"] = {
        "status": it["status"], "iterations": it["iterations"],
        "finite_checks": sum(e["rel_certificate"] is not None for e in it["history"])}
    out["h_stagnation_rule"] = runs
    return out


def run() -> dict:
    ns.require_extended_precision()
    t0 = time.monotonic()
    res = {"record": "solver verification on synthetic cases only; no QMHP data read",
           "solver_settings": ns.SOLVER, "V1_exact_known_answer": v1_exact(),
           "V1b_certificate_against_exact_discrete_minimum": v1b_certificate_against_exact_discrete_minimum(),
           "V1c_residual_certificate_against_exact_excess": {
               "certificate": v1c_residual_certificate_against_exact_excess(),
               "negative_control_c_times_10": v1c_residual_certificate_against_exact_excess(10.0)},
           "V6_evaluation_bound_against_exact_arithmetic": v6_evaluation_bound(),
           "V7_assembly_term": v7_assembly_term(),
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
    import study_driver  # noqa: PLC0415 - the same strict-JSON writer as the records
    text = json.dumps(study_driver._clean(run()), indent=1, allow_nan=False)
    if a.out:
        Path(a.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
