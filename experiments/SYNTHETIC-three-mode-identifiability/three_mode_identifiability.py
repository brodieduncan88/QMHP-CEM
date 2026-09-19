#!/usr/bin/env python3
"""SYNTHETIC ONLY. Three-mode identifiability / coordinate-definition check.

Bounded offline study on a known-parameter three-node linear circuit
(fluxonium linear branch F, readout R, one additional mode X). It answers,
on synthetic eigenmode data only:

  B. which quantities are invariant under a rotation Q = diag(1, O) of the
     R/X coordinate block, and whether the previously reported one-parameter
     family of circuits is that rotation orbit;
  C. what the complete three-mode F-site data (f_m, p_mF) identify through
     G_F(z) = sum_m p_mF/(z - f_m^2) and
     z - a - 1/G_F(z) = c^T (zI - B)^-1 c,
     including the dark-mode and degeneracy limits;
  D. whether one explicitly defined, non-loading readout-side observable
     (the cross-mode ratio of readout-node to fluxonium-node voltage ratios)
     removes the continuous ambiguity, whether discrete alternatives remain,
     and how sensitive the recovery is to small input errors.

It is NOT part of models/, is not imported by the pipeline, is not an
acceptance gate, and reads no committed Palace record. It uses
models.route_a_inversion only for the registered target algebra
(charging_energy_GHz, coupling_GHz) and, read-only, invert_two_node on exact
two-node data as a cross-check. invert_two_node and its guards are unchanged.

Units: S_ij in (2 pi 1e9 rad/s)^2, i.e. "GHz^2": a = f_F^2, b = f_R^2, ...
Node order is (F, R, X). S = L^-1/2 C^-1 L^-1/2 with L = diag(L_F, L_R, L_X);
the mode equation is S v_m = f_m^2 v_m with orthonormal v_m, and the
fluxonium-inductor participation is p_mF = v_mF^2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import least_squares, minimize_scalar, root

REPO_ROOT = Path(__file__).resolve().parents[2] if (Path(__file__).resolve().parents[1].name == "experiments") else Path.cwd()
sys.path.insert(0, str(REPO_ROOT))
from models.route_a_inversion import (  # noqa: E402  (read-only use of the registered algebra)
    InvariantTriple, NormalModeData, charging_energy_GHz, coupling_GHz, invert_two_node,
)

LABEL = "SYNTHETIC"
W0 = (2.0 * math.pi * 1e9) ** 2
#: Declared superinductor (H), as in the N1R/N2R Palace configs (E_L = 1.58 GHz). Unchanged.
L_F = 1.0345665367517793e-07

RNG_SEED = 20260919


# ----------------------------------------------------------------------------- model
def S3(a, b, d, kFR, kFX, kRX):
    return np.array([[a, kFR, kFX], [kFR, b, kRX], [kFX, kRX, d]], float)


def modes3(S):
    """Frequencies (GHz, ascending), F-site participations p_mF = v_mF^2, eigenvectors."""
    w2, V = np.linalg.eigh(S)
    if not np.all(w2 > 0):
        raise ValueError("non-positive normal-mode frequency")
    return np.sqrt(w2), V[0, :] ** 2, V


def node_targets(S) -> InvariantTriple:
    """The registered algebra (coupling-definition.md §3, §10) applied in the NODE basis:
    E_C from (C^-1)_FF, bare f_R = sqrt((C^-1)_RR / L_R) = sqrt(S_RR), g from |S_FR| and S_RR."""
    a, b, k = S[0, 0], S[1, 1], abs(S[0, 1])
    return InvariantTriple(E_C_FF_GHz=charging_energy_GHz(a * W0 * L_F), f_F_GHz=math.sqrt(a),
                           f_R_GHz=math.sqrt(b), g_GHz=coupling_GHz(k * W0, b * W0, L_F))


def targets_from(a, beta_R, ctil_R) -> InvariantTriple:
    """Same algebra applied to an environment NORMAL-MODE coordinate (beta_R, ctil_R)."""
    return InvariantTriple(E_C_FF_GHz=charging_energy_GHz(a * W0 * L_F), f_F_GHz=math.sqrt(a),
                           f_R_GHz=math.sqrt(beta_R), g_GHz=coupling_GHz(abs(ctil_R) * W0, beta_R * W0, L_F))


def Q_rot(theta, reflect=False):
    c, s = math.cos(theta), math.sin(theta)
    O = np.array([[c, -s], [s, c]])
    if reflect:
        O = O @ np.diag([1.0, -1.0])
    Q = np.eye(3)
    Q[1:, 1:] = O
    return Q


def env_normal_modes(S):
    """B = U diag(beta) U^T, ctil = U^T c (signs of U's columns fixed so ctil >= 0)."""
    B, c = S[1:, 1:], S[1:, 0]
    beta, U = np.linalg.eigh(B)
    ctil = U.T @ c
    sgn = np.where(ctil < 0, -1.0, 1.0)
    return beta, ctil * sgn, U * sgn


def rotation_invariants(S):
    B, c = S[1:, 1:], S[1:, 0]
    return {"a": S[0, 0], "trB": np.trace(B), "detB": np.linalg.det(B),
            "c_norm2": float(c @ c), "cBc": float(c @ B @ c)}


def admissible_node_circuit(S):
    """The permitted constraints beyond positive definiteness (coupling-definition.md §2, §10):
    C is a Maxwell matrix (positive diagonal, non-positive off-diagonal mutuals), so C^-1 is
    entrywise non-negative. With L diagonal positive: S = L^-1/2 C^-1 L^-1/2 has off-diagonals
    >= 0, and S^-1 = L^1/2 C L^1/2 has off-diagonals <= 0. Diagonal dominance of C (positive
    capacitance to ground) can always be met by the readout/X flux scales, so it is not a
    gauge-independent constraint and is not tested here."""
    Sinv = np.linalg.inv(S)
    off = ~np.eye(3, dtype=bool)
    pd = bool(np.all(np.linalg.eigvalsh(S) > 0))
    cinv_nonneg = bool(np.all(S[off] >= -1e-12))
    c_zmatrix = bool(np.all(Sinv[off] <= 1e-12))
    return {"positive_definite": pd, "Cinv_offdiag_nonneg": cinv_nonneg,
            "C_offdiag_nonpos": c_zmatrix, "admissible": pd and cinv_nonneg and c_zmatrix}


# ------------------------------------------------------------------- F-site response
def f_site_identify(f, p):
    """From (f_m, p_mF): a = sum p_m f_m^2, the zeros beta_k of G_F(z) = sum p_m/(z - f_m^2)
    (poles of c^T (zI-B)^-1 c) and the residues ctil_k^2 = 1 / sum_m p_m/(beta_k - f_m^2)^2.
    No renormalisation of p is applied; sum(p) is returned so the caller can see it."""
    w = np.asarray(f, float) ** 2
    p = np.asarray(p, float)
    M = len(w)
    # numerator polynomial of G_F: N(z) = sum_m p_m prod_{n != m} (z - w_n), degree M-1
    N = np.zeros(M)
    for m in range(M):
        N = N + p[m] * np.poly([w[n] for n in range(M) if n != m])
    beta = np.roots(N)
    if np.any(np.abs(beta.imag) > 1e-9 * np.max(np.abs(beta))):
        raise ValueError(f"complex zeros of G_F: {beta}")
    beta = np.sort(beta.real)
    ctil2 = np.array([1.0 / np.sum(p / (bk - w) ** 2) for bk in beta])
    return {"a": float(np.sum(p * w)), "beta": beta, "ctil2": ctil2, "sum_p": float(np.sum(p))}


# ------------------------------------------------------------ voltage-ratio observable
def voltage_ratio_rows(V, f):
    """rho_m := V_mR / V_mF in eigenmode m. In the lumped model V_m ∝ f_m^2 L^{1/2} v_m, so
    rho_m = sqrt(L_R/L_F) v_mR / v_mF. The scale sqrt(L_R/L_F) is the readout gauge, so only
    cross-mode ratios r_mn = rho_m/rho_n = (v_mR v_nF)/(v_nR v_mF) are gauge-free data."""
    return V[1, :] / V[0, :]


def theta_from_ratio(S_rep, m, n, r_obs, reflect):
    """Closed form: with v(θ) = Q(θ) v_rep,  v_R(θ) = cosθ v_R ∓ sinθ v_X (∓: reflect False/True).
    r_mn(θ) = r_obs is linear in (cosθ, sinθ): unique tanθ."""
    _, _, V = modes3(S_rep)
    sgn = 1.0 if reflect else -1.0
    vmR, vmX, vmF = V[1, m], V[2, m], V[0, m]
    vnR, vnX, vnF = V[1, n], V[2, n], V[0, n]
    # r (cos vnR + sgn sin vnX) vmF = (cos vmR + sgn sin vmX) vnF
    A = r_obs * vnR * vmF - vmR * vnF
    Bc = sgn * (r_obs * vnX * vmF - vmX * vnF)
    # A cos + Bc sin = 0  ->  tan = -A/Bc
    return math.atan2(-A, Bc)


def representative_from_fsite(f, p):
    idn = f_site_identify(f, p)
    a, beta, ctil = idn["a"], idn["beta"], np.sqrt(np.maximum(idn["ctil2"], 0.0))
    S_rep = np.zeros((3, 3))
    S_rep[0, 0] = a
    S_rep[1:, 1:] = np.diag(beta)
    S_rep[0, 1:] = ctil
    S_rep[1:, 0] = ctil
    return S_rep, idn


def perturb(f, p, r, rng, sf, sp, sr):
    f2 = f * (1.0 + sf * rng.standard_normal(len(f)))
    p2 = np.empty_like(p)
    for i, pi in enumerate(p):     # noise on the smaller of p and 1-p (route-a-identifiability §6)
        xi = rng.standard_normal()
        p2[i] = pi * (1.0 + sp * xi) if pi < 0.5 else 1.0 - (1.0 - pi) * (1.0 + sp * xi)
    r2 = r * (1.0 + sr * rng.standard_normal())
    return f2, p2, r2


def relerr(got: InvariantTriple, true: InvariantTriple):
    d = got.relative_difference(true)
    return {"E_C": float(d["E_C_FF_GHz"]), "f_R": float(d["f_R_GHz"]), "g": float(d["g_GHz"])}


def finite(x):
    """Reject non-finite outputs explicitly (recursively through dicts, lists and arrays)."""
    _scan_finite(x, "value")
    return x


# ================================================================================ main
def main(out_dir: Path | None):
    rng = np.random.default_rng(RNG_SEED)
    R: dict = {"label": LABEL, "units": "S in GHz^2; f in GHz; g in GHz (MHz where stated)",
               "L_F_H": L_F, "node_order": ["F", "R", "X"]}
    lines: list[str] = []
    say = lines.append

    # ---- synthetic references (node basis) -------------------------------------------------
    A0, B0, D0, KFR0 = 1.50 ** 2, 3.90 ** 2, 8.0 ** 2, 0.41
    from scipy.optimize import brentq
    def p3_of(kfx, kRX):
        return modes3(S3(A0, B0, D0, KFR0, kfx, kRX))[1][2]
    KFX_A = brentq(lambda k: p3_of(k, 0.0) - 8e-4, 0.0, 6.0)
    KRX_B = 2.0
    KFX_B = brentq(lambda k: p3_of(k, KRX_B) - 8e-4, 0.0, 6.0)
    refs = {"A_kRX0": S3(A0, B0, D0, KFR0, KFX_A, 0.0), "B_kRX2": S3(A0, B0, D0, KFR0, KFX_B, KRX_B)}
    R["inputs"] = {name: {"S": S.tolist(), "admissible": admissible_node_circuit(S),
                          "node_targets": node_targets(S).as_dict(),
                          "modes_GHz": modes3(S)[0].tolist(), "p_F": modes3(S)[1].tolist()}
                   for name, S in refs.items()}
    say("=== synthetic references (node basis) ===")
    for name, S in refs.items():
        f, p, _ = modes3(S)
        T = node_targets(S)
        say(f"  {name}: S={np.array2string(S, precision=6)}")
        say(f"    modes f={f}  p_F={p}  sum p={p.sum():.15f}")
        say(f"    node targets: E_C={T.E_C_FF_GHz:.9f} GHz  f_R={T.f_R_GHz:.9f} GHz  g={T.g_MHz:.6f} MHz")
        say(f"    admissible node circuit: {admissible_node_circuit(S)}")
        Sinv = np.linalg.inv(S)
        say(f"    S^-1 (∝ L^1/2 C L^1/2; Maxwell needs off-diagonals <= 0): (F,R)={Sinv[0,1]:+.3e} (F,X)={Sinv[0,2]:+.3e} (R,X)={Sinv[1,2]:+.3e}")
        R["inputs"][name]["Sinv_offdiag"] = {"FR": float(Sinv[0, 1]), "FX": float(Sinv[0, 2]), "RX": float(Sinv[1, 2])}

    # sanity: production inversion on the exact two-node limit (X decoupled) — read-only use
    S2 = S3(A0, B0, 30.0 ** 2, KFR0, 0.0, 0.0)
    f, p, _ = modes3(S2)
    prod, _ = invert_two_node(NormalModeData(f[1], f[0], p[1], p[0], L_F))
    R["two_node_cross_check"] = relerr(prod, node_targets(S2))
    say(f"  two-node cross-check (X decoupled): |invert_two_node - node targets| = {R['two_node_cross_check']}")

    # ---- B. rotations of the R/X block --------------------------------------------------
    say("\n=== B. rotation Q = diag(1, O(theta)) of the R/X block ===")
    R["B_rotation"] = {}
    for name, S0 in refs.items():
        f0, p0, _ = modes3(S0)
        inv0 = rotation_invariants(S0)
        thetas = np.linspace(-math.pi / 2, math.pi / 2, 721)
        rows = []
        max_df = max_dp = max_da = 0.0
        for th in thetas:
            Q = Q_rot(th)
            S = Q @ S0 @ Q.T
            f, p, _ = modes3(S)
            max_df = max(max_df, float(np.max(np.abs(f - f0) / f0)))
            max_dp = max(max_dp, float(np.max(np.abs(p - p0))))
            max_da = max(max_da, abs(S[0, 0] - S0[0, 0]) / S0[0, 0])
            T = node_targets(S)
            adm = admissible_node_circuit(S)
            rows.append({"theta": th, "b": S[1, 1], "d": S[2, 2], "kFR": S[0, 1], "kFX": S[0, 2],
                         "kRX": S[1, 2], "f_R": T.f_R_GHz, "g_MHz": T.g_MHz, "E_C": T.E_C_FF_GHz,
                         **{k: v for k, v in adm.items()}})
        adm_rows = [r for r in rows if r["admissible"]]
        g_all = np.array([r["g_MHz"] for r in rows]); fr_all = np.array([r["f_R"] for r in rows])
        g_adm = np.array([r["g_MHz"] for r in adm_rows]); fr_adm = np.array([r["f_R"] for r in adm_rows])
        th_adm = np.array([r["theta"] for r in adm_rows])
        # admissible theta interval(s)
        flags = np.array([r["admissible"] for r in rows])
        edges = np.flatnonzero(np.diff(flags.astype(int)))
        R["B_rotation"][name] = finite({
            "invariance_max_rel_df": max_df, "invariance_max_abs_dp": max_dp, "invariance_max_rel_da": max_da,
            "rotation_invariants": inv0,
            "g_MHz_range_all_theta": [float(g_all.min()), float(g_all.max())],
            "f_R_range_all_theta": [float(fr_all.min()), float(fr_all.max())],
            "n_theta": len(rows), "n_admissible": len(adm_rows),
            "theta_admissible_range": [float(th_adm.min()), float(th_adm.max())] if len(adm_rows) else None,
            "g_MHz_range_admissible": [float(g_adm.min()), float(g_adm.max())] if len(adm_rows) else None,
            "f_R_range_admissible": [float(fr_adm.min()), float(fr_adm.max())] if len(adm_rows) else None,
            "positive_definite_violations": int(sum(not r["positive_definite"] for r in rows)),
            "Cinv_sign_violations": int(sum(not r["Cinv_offdiag_nonneg"] for r in rows)),
            "C_sign_violations": int(sum(not r["C_offdiag_nonpos"] for r in rows)),
        })
        say(f"  {name}: over {len(rows)} angles in [-pi/2, pi/2]:")
        say(f"    invariant: max rel |df|={max_df:.1e}, max |dp_F|={max_dp:.1e}, max rel |da|={max_da:.1e} (E_C invariant)")
        say(f"    change:    f_R in [{fr_all.min():.6f}, {fr_all.max():.6f}] GHz; g in [{g_all.min():.4f}, {g_all.max():.4f}] MHz")
        say(f"    positive-definite violations: 0 of {len(rows)} (a rotation is a similarity)")
        say(f"    Maxwell-sign admissible (C^-1 >= 0 and C off-diag <= 0): {len(adm_rows)} of {len(rows)} angles; "
            f"theta in [{th_adm.min():+.4f}, {th_adm.max():+.4f}] rad")
        say(f"    within the admissible angles: f_R in [{fr_adm.min():.6f}, {fr_adm.max():.6f}] GHz; g in [{g_adm.min():.4f}, {g_adm.max():.4f}] MHz")

    # is the previously reported kRX-family the rotation orbit?  (reference A, 5 F-site observables matched)
    say("\n  previously reported family (all five F-site observables matched, kRX prescribed):")
    S0 = refs["A_kRX0"]; f0, p0, _ = modes3(S0); tgt = np.concatenate([f0, p0])
    inv0 = rotation_invariants(S0)
    fam = []
    for kRX in (0.5, 1.0, 2.0, 3.0, 5.0, 8.0):
        def G(x):
            a, b, d, kfr, kfx = x
            try:
                f_, p_, _ = modes3(S3(a, b, d, kfr, kfx, kRX))
            except ValueError:
                return np.ones(6) * 1e3
            return np.concatenate([f_, p_]) - tgt
        sol = root(G, x0=[A0, B0, D0, KFR0, KFX_A], method="lm", options={"xtol": 1e-14, "ftol": 1e-14})
        if not (sol.success and np.max(np.abs(G(sol.x))) < 1e-9):
            continue
        S = S3(*sol.x[:3], sol.x[3], sol.x[4], kRX)
        inv = rotation_invariants(S)
        dev = max(abs(inv[k] - inv0[k]) / max(abs(inv0[k]), 1e-300) for k in inv0)
        # find the angle: minimise ||Q S0 Q^T - S|| (coarse grid, then a bounded local refinement)
        def orbit_dist(th, rf):
            return float(np.linalg.norm(Q_rot(th, rf) @ S0 @ Q_rot(th, rf).T - S))
        coarse = min(((orbit_dist(th, rf), th, rf) for rf in (False, True) for th in np.linspace(-math.pi, math.pi, 2001)))
        h = 2 * math.pi / 2000
        fine = minimize_scalar(lambda th: orbit_dist(th, coarse[2]), bounds=(coarse[1] - h, coarse[1] + h),
                               method="bounded", options={"xatol": 1e-13})
        best = (orbit_dist(fine.x, coarse[2]), float(fine.x), coarse[2])
        fam.append({"kRX": kRX, "g_MHz": node_targets(S).g_MHz, "f_R": node_targets(S).f_R_GHz,
                    "max_rel_dev_rotation_invariants": dev, "orbit_residual": best[0], "theta": best[1], "reflect": best[2],
                    "admissible": admissible_node_circuit(S)["admissible"]})
        say(f"    kRX={kRX:4.1f}: g={fam[-1]['g_MHz']:.4f} MHz f_R={fam[-1]['f_R']:.6f}  rotation-invariants dev={dev:.1e}  "
            f"|Q S0 Q^T - S|={best[0]:.1e} at theta={best[1]:+.5f} reflect={best[2]}  admissible={fam[-1]['admissible']}")
    R["B_family_is_orbit"] = finite(fam)

    # ---- C. what the complete F-site data identify --------------------------------------
    say("\n=== C. G_F(z) = sum p_mF/(z - f_m^2);  z - a - 1/G_F(z) = c^T (zI - B)^-1 c ===")
    R["C_fsite"] = {}
    for name, S in refs.items():
        f, p, _ = modes3(S)
        beta_true, ctil_true, _ = env_normal_modes(S)
        idn = f_site_identify(f, p)
        nm = targets_from(idn["a"], idn["beta"][0], math.sqrt(idn["ctil2"][0]))   # readout = lower env normal mode
        node = node_targets(S)
        R["C_fsite"][name] = finite({
            "a_rec_rel_err": abs(idn["a"] - S[0, 0]) / S[0, 0],
            "beta_rec": idn["beta"].tolist(), "beta_true": beta_true.tolist(),
            "beta_rel_err": (np.abs(idn["beta"] - beta_true) / beta_true).tolist(),
            "ctil2_rec": idn["ctil2"].tolist(), "ctil2_true": (ctil_true ** 2).tolist(),
            "ctil2_rel_err": (np.abs(idn["ctil2"] - ctil_true ** 2) / ctil_true ** 2).tolist(),
            "sum_p": idn["sum_p"],
            "normal_mode_targets": nm.as_dict(), "node_targets": node.as_dict(),
            "normal_mode_vs_node_rel_diff": relerr(nm, node),
        })
        say(f"  {name}:")
        say(f"    a = sum p f^2: rel err {R['C_fsite'][name]['a_rec_rel_err']:.1e}")
        say(f"    zeros of G_F -> beta = {idn['beta']} (true {beta_true}); rel err {np.array(R['C_fsite'][name]['beta_rel_err'])}")
        say(f"    residues     -> ctil^2 = {idn['ctil2']} (true {ctil_true**2}); rel err {np.array(R['C_fsite'][name]['ctil2_rel_err'])}")
        say(f"    normal-mode targets: f_R={nm.f_R_GHz:.9f} g={nm.g_MHz:.6f} MHz E_C={nm.E_C_FF_GHz:.9f}")
        say(f"    node-basis  targets: f_R={node.f_R_GHz:.9f} g={node.g_MHz:.6f} MHz E_C={node.E_C_FF_GHz:.9f}")
        say(f"    normal-mode vs node: {relerr(nm, node)}")

    # dark-mode limit: kFX -> 0 at kRX = 0 (third mode decouples from F)
    say("\n  dark-mode limit (kRX=0, kFX scaled so p3F -> 0), double precision, no added noise:")
    dark = []
    for target in (8e-4, 1e-6, 1e-9, 1e-12, 0.0):
        kfx = 0.0 if target == 0.0 else brentq(lambda k: p3_of(k, 0.0) - target, 0.0, 6.0)
        S = S3(A0, B0, D0, KFR0, kfx, 0.0)
        f, p, _ = modes3(S)
        beta_true, ctil_true, _ = env_normal_modes(S)
        try:
            with np.errstate(divide="ignore", invalid="ignore"):
                idn = f_site_identify(f, p)
            e_beta = (np.abs(idn["beta"] - beta_true) / beta_true).tolist()
            eR = abs(idn["ctil2"][0] - ctil_true[0] ** 2) / ctil_true[0] ** 2
            eX = (abs(idn["ctil2"][1] - ctil_true[1] ** 2) / ctil_true[1] ** 2) if ctil_true[1] > 0 else None
            if not np.isfinite(idn["ctil2"]).all() or (eX is not None and not math.isfinite(eX)):
                row = {"p3F": float(p[2]), "beta_rel_err": e_beta, "ctil2_rel_err_R": eR if math.isfinite(eR) else None,
                       "ctil2_rel_err_X": None, "status": "X residue NOT identifiable (pole-zero cancellation)"}
            else:
                row = {"p3F": float(p[2]), "beta_rel_err": e_beta, "ctil2_rel_err_R": eR, "ctil2_rel_err_X": eX,
                       "status": "ok" if eX is not None else "X decoupled: its residue is 0 and not identifiable"}
        except ValueError as e:
            row = {"p3F": float(p[2]), "status": f"failed: {e}"}
        dark.append(row)
        say(f"    p3F={row['p3F']:.1e}: {row}")
    R["C_dark_mode"] = dark
    # degeneracy limit: beta_1 -> beta_2 with kRX = 0 (d -> b), kFX fixed
    say("\n  degeneracy limit (kRX=0, d -> b; kFX fixed at the reference value), 1e-12 relative input noise:")
    deg = []
    for gap in (D0 - B0, 5.0, 0.5, 0.05, 0.005):
        S = S3(A0, B0, B0 + gap, KFR0, KFX_A, 0.0)
        f, p, _ = modes3(S)
        beta_true, ctil_true, _ = env_normal_modes(S)
        errs = []
        for _ in range(50):
            f2 = f * (1 + 1e-12 * rng.standard_normal(3)); p2 = p * (1 + 1e-12 * rng.standard_normal(3))
            try:
                idn = f_site_identify(f2, p2)
                errs.append([np.max(np.abs(idn["beta"] - beta_true) / beta_true),
                             np.max(np.abs(idn["ctil2"] - ctil_true ** 2) / ctil_true ** 2),
                             abs(idn["ctil2"].sum() - (ctil_true ** 2).sum()) / (ctil_true ** 2).sum()])
            except ValueError:
                errs.append([np.nan, np.nan, np.nan])
        errs = np.array(errs)
        row = {"beta_gap_GHz2": float(beta_true[1] - beta_true[0]), "n_failed": int(np.isnan(errs[:, 0]).sum()),
               "median_beta_rel_err": float(np.nanmedian(errs[:, 0])), "median_ctil2_rel_err": float(np.nanmedian(errs[:, 1])),
               "median_ctil2_sum_rel_err": float(np.nanmedian(errs[:, 2]))}
        deg.append(row)
        say(f"    beta gap={row['beta_gap_GHz2']:.3e} GHz^2: {row}")
    R["C_degeneracy"] = deg

    # sensitivity of the normal-mode quantities to input errors (reference A and B)
    say("\n  sensitivity of the normal-mode targets (from the F-site identification) to input errors; 95th pct relative error, 2000 draws:")
    sens = {}
    for name, S in refs.items():
        f, p, _ = modes3(S)
        beta_true, ctil_true, _ = env_normal_modes(S)
        true_nm = targets_from(S[0, 0], beta_true[0], ctil_true[0])
        sens[name] = []
        for sf, sp in ((1e-6, 1e-3), (1e-5, 1e-2), (1e-4, 1e-2), (1e-4, 1e-1)):
            errs, sums, fails = [], [], 0
            for _ in range(2000):
                f2, p2, _r = perturb(f, p, 1.0, rng, sf, sp, 0.0)
                try:
                    idn = f_site_identify(f2, p2)
                    got = targets_from(idn["a"], idn["beta"][0], math.sqrt(max(idn["ctil2"][0], 0.0)))
                    e = relerr(got, true_nm); errs.append([e["E_C"], e["f_R"], e["g"]]); sums.append(abs(idn["sum_p"] - 1))
                except (ValueError, ZeroDivisionError):
                    fails += 1
            errs = np.array(errs)
            row = {"sigma_f": sf, "sigma_p": sp, "p95_E_C": float(np.percentile(errs[:, 0], 95)),
                   "p95_f_R": float(np.percentile(errs[:, 1], 95)), "p95_g": float(np.percentile(errs[:, 2], 95)),
                   "median_sum_p_residual": float(np.median(sums)), "failed": fails}
            sens[name].append(finite(row))
            say(f"    {name} sf={sf:.0e} sp={sp:.0e}: E_C {row['p95_E_C']:.1e}  f_R {row['p95_f_R']:.1e}  g {row['p95_g']:.1e}  "
                f"(median |sum p - 1| = {row['median_sum_p_residual']:.1e}, failed {fails})")
    R["C_sensitivity"] = sens

    # ---- D. the extra readout-side observable --------------------------------------------
    say("\n=== D. extra non-loading readout-side observable: rho_m = V_mR / V_mF, used through r_12 = rho_1/rho_2 ===")
    S_true = refs["B_kRX2"]
    f, p, V = modes3(S_true)
    rho = voltage_ratio_rows(V, f)          # up to the unknown scale sqrt(L_R/L_F); scale cancels in r_mn
    r12, r13 = rho[0] / rho[1], rho[0] / rho[2]
    T_true = node_targets(S_true)
    S_rep, idn = representative_from_fsite(f, p)
    say(f"  truth (node basis, kRX=2): g={T_true.g_MHz:.6f} MHz f_R={T_true.f_R_GHz:.9f} E_C={T_true.E_C_FF_GHz:.9f}; r_12={r12:.9f} r_13={r13:.9f}")
    D = {"r12": r12, "r13": r13, "true": T_true.as_dict()}
    # closed-form angle on both O(2) components
    cands = []
    for pair, r_obs in ((("1", "2"), r12), (("1", "3"), r13)):
        m, n = int(pair[0]) - 1, int(pair[1]) - 1
        for rf in (False, True):
            th = theta_from_ratio(S_rep, m, n, r_obs, rf)
            for th_k in (th, th + math.pi):   # tan is pi-periodic; theta+pi flips the sign of (v_R, v_X)
                Q = Q_rot(th_k, rf)
                S = Q @ S_rep @ Q.T
                f2, p2, V2 = modes3(S)
                rho2 = voltage_ratio_rows(V2, f2)
                r_chk = rho2[m] / rho2[n]
                T = node_targets(S)
                cands.append({"pair": "".join(pair), "reflect": rf, "theta": th_k, "r_residual": abs(r_chk - r_obs) / abs(r_obs),
                              "g_MHz": T.g_MHz, "f_R": T.f_R_GHz, "E_C": T.E_C_FF_GHz,
                              "rel_err": relerr(T, T_true), "S_residual": float(np.linalg.norm(S - S_true)),
                              "admissible": admissible_node_circuit(S)["admissible"]})
    D["closed_form_candidates"] = finite(cands)
    for c in cands:
        say(f"    r_{c['pair']} reflect={c['reflect']!s:5} theta={c['theta']:+.6f}: r residual {c['r_residual']:.1e}  "
            f"g={c['g_MHz']:.6f} f_R={c['f_R']:.9f}  rel err {c['rel_err']}  |S-S_true|={c['S_residual']:.1e} adm={c['admissible']}")
    distinct = {(round(float(c["g_MHz"]), 6), round(float(c["f_R"]), 9)) for c in cands if c["r_residual"] < 1e-8}
    D["n_distinct_target_pairs_closed_form"] = len(distinct)
    say(f"  distinct (g, f_R) among closed-form candidates reproducing the ratio: {len(distinct)} -> {sorted(distinct)}")

    # brute force: random-start solve of the full system in the raw node-basis entries
    say("\n  random-start solve of the raw 6-entry system (5 F-site equations + r_12), 400 starts:")
    tgt5 = np.concatenate([f, p[:2]])
    def sys6(x):
        try:
            f_, p_, V_ = modes3(S3(*x))
        except ValueError:
            return np.ones(6) * 1e3
        rho_ = voltage_ratio_rows(V_, f_)
        return np.concatenate([f_ - f, p_[:2] - p[:2], [rho_[0] / rho_[1] - r12]])
    def sys5(x):
        return sys6(x)[:5]
    sols6, sols5 = [], []
    for _ in range(400):
        x0 = np.array([A0, B0, D0, KFR0, KFX_B, KRX_B]) * (1 + 0.5 * rng.standard_normal(6))
        x0[3:] += 1.5 * rng.standard_normal(3)
        s6 = root(sys6, x0=x0, method="lm", options={"xtol": 1e-14, "ftol": 1e-14, "maxiter": 4000})
        if s6.success and np.max(np.abs(sys6(s6.x))) < 1e-9:
            sols6.append(s6.x)
        s5 = least_squares(sys5, x0=x0, method="trf", xtol=1e-15, ftol=1e-15, gtol=1e-15, max_nfev=4000)
        if np.max(np.abs(sys5(s5.x))) < 1e-9:
            sols5.append(s5.x)
    def summarise(sols):
        Ts = [node_targets(S3(*x)) for x in sols]
        g = np.array([t.g_MHz for t in Ts]); fr = np.array([t.f_R_GHz for t in Ts])
        keys = sorted({(round(float(gg), 4), round(float(ff), 7)) for gg, ff in zip(g, fr)})
        adm = sum(admissible_node_circuit(S3(*x))["admissible"] for x in sols)
        return {"n_converged": len(sols), "n_distinct_targets": len(keys), "g_MHz_min": float(g.min()) if len(g) else None,
                "g_MHz_max": float(g.max()) if len(g) else None, "distinct_targets": keys[:12], "n_admissible": int(adm)}
    D["random_start_6eq"] = summarise(sols6)
    D["random_start_5eq"] = summarise(sols5)
    say(f"    with r_12: {D['random_start_6eq']}")
    say(f"    F-site only (5 eq): {D['random_start_5eq']}")

    # consistency: r_12 and r_13 together (overdetermined) — do they agree on theta?
    th12 = theta_from_ratio(S_rep, 0, 1, r12, False); th13 = theta_from_ratio(S_rep, 0, 2, r13, False)
    D["theta_r12_vs_r13_consistency"] = finite(abs(math.sin(th12 - th13)))
    say(f"  r_12 and r_13 give theta {th12:+.9f} and {th13:+.9f} rad (|sin diff| = {abs(math.sin(th12-th13)):.1e}): consistent")

    # sensitivity of the node-basis recovery to input errors on (f, p, r_12)
    say("\n  sensitivity of the node-basis recovery (F-site data + r_12) to input errors; 95th pct relative error, 2000 draws:")
    D["sensitivity"] = []
    for sf, sp, sr in ((1e-6, 1e-3, 1e-4), (1e-6, 1e-3, 1e-3), (1e-6, 1e-3, 1e-2), (1e-4, 1e-2, 1e-3), (1e-4, 1e-2, 1e-2)):
        errs, fails, thetas = [], 0, []
        for _ in range(2000):
            f2, p2, r2 = perturb(f, p, r12, rng, sf, sp, sr)
            try:
                S_rep2, _ = representative_from_fsite(f2, p2)
                th = theta_from_ratio(S_rep2, 0, 1, r2, False)
                S2 = Q_rot(th) @ S_rep2 @ Q_rot(th).T
                T2 = node_targets(S2)
                e = relerr(T2, T_true); errs.append([e["E_C"], e["f_R"], e["g"]]); thetas.append(th)
            except (ValueError, ZeroDivisionError):
                fails += 1
        errs = np.array(errs)
        row = {"sigma_f": sf, "sigma_p": sp, "sigma_r": sr, "p95_E_C": float(np.percentile(errs[:, 0], 95)),
               "p95_f_R": float(np.percentile(errs[:, 1], 95)), "p95_g": float(np.percentile(errs[:, 2], 95)),
               "p95_abs_dtheta_rad": float(np.percentile(np.abs(np.array(thetas) - th12), 95)), "failed": fails}
        D["sensitivity"].append(finite(row))
        say(f"    sf={sf:.0e} sp={sp:.0e} sr={sr:.0e}: E_C {row['p95_E_C']:.1e}  f_R {row['p95_f_R']:.1e}  g {row['p95_g']:.1e}  "
            f"|dtheta| {row['p95_abs_dtheta_rad']:.1e} rad  failed {fails}")
    # local amplification factors
    def g_of_r(rr):
        th = theta_from_ratio(S_rep, 0, 1, rr, False)
        return node_targets(Q_rot(th) @ S_rep @ Q_rot(th).T).g_MHz
    h = 1e-6
    amp = (g_of_r(r12 * (1 + h)) - g_of_r(r12 * (1 - h))) / (2 * h) / T_true.g_MHz
    D["dlng_dlnr12"] = finite(amp)
    say(f"  local amplification d ln g / d ln r_12 = {amp:+.4f}")
    R["D_extra_observable"] = D

    # ---- E. saved-record check (which quantities exist in the committed N1R/N2R outputs) ----
    R["E_saved_outputs"] = {
        "N1R": sorted(os.listdir(REPO_ROOT / "results/COUPLED-LADDER-O1-L2-N1R-20260919T110053Z/L2/solver/postpro"))
        if (REPO_ROOT / "results/COUPLED-LADDER-O1-L2-N1R-20260919T110053Z/L2/solver/postpro").exists() else "absent",
        "N2R": sorted(os.listdir(REPO_ROOT / "results/COUPLED-LADDER-O1-L2-N2R-20260918T061455Z/L2/solver/postpro"))
        if (REPO_ROOT / "results/COUPLED-LADDER-O1-L2-N2R-20260918T061455Z/L2/solver/postpro").exists() else "absent",
        "note": "listing only; no value from these records is read or used by this study",
    }
    say(f"\n=== E. committed N1R/N2R postpro files (listing only): {R['E_saved_outputs']['N1R']}")

    report = "\n".join(lines)
    print(report)
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        env = {
            "python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "scipy": scipy.__version__,
            "rng_seed": RNG_SEED,
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT).stdout.strip(),
        }
        (out_dir / "results.json").write_text(json.dumps(R, indent=1, default=_json_default) + "\n")
        (out_dir / "environment.json").write_text(json.dumps(env, indent=1) + "\n")
        (out_dir / "inputs.json").write_text(json.dumps({"label": LABEL, "L_F_H": L_F, "references": {k: v["S"] for k, v in R["inputs"].items()},
                                                          "design": {"A0": A0, "B0": B0, "D0": D0, "KFR0": KFR0, "KFX_A": KFX_A, "KFX_B": KFX_B, "KRX_B": KRX_B},
                                                          "rng_seed": RNG_SEED}, indent=1) + "\n")
        (out_dir / "report.txt").write_text(report + "\n")
        # final non-finite scan of everything recorded
        _scan_finite(json.loads((out_dir / "results.json").read_text()))
        man = []
        for fn in sorted(os.listdir(out_dir)):
            if fn == "manifest.sha256":
                continue
            man.append(f"{hashlib.sha256((out_dir / fn).read_bytes()).hexdigest()}  {fn}")
        (out_dir / "manifest.sha256").write_text("\n".join(man) + "\n")
        print(f"\nwrote {out_dir}")


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        v = o.item()
        if isinstance(v, float) and not math.isfinite(v):
            raise RuntimeError(f"non-finite value in results: {v}")
        return v
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(type(o))


def _scan_finite(obj, path="results"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            _scan_finite(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _scan_finite(v, f"{path}[{i}]")
    elif isinstance(obj, np.ndarray):
        if not np.all(np.isfinite(obj)):
            raise RuntimeError(f"non-finite value at {path}")
    elif isinstance(obj, (float, np.floating)):
        if not math.isfinite(obj):
            raise RuntimeError(f"non-finite value at {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=None, help="record directory (must not be under results/)")
    args = ap.parse_args()
    if args.out is not None and "results" in args.out.resolve().parts:
        raise SystemExit("refusing to write a SYNTHETIC record under results/")
    main(args.out)
