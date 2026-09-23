# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""The static-vs-band relationship, checked three ways. Nothing here solves on the QMHP mesh.

1. KNOWN ANSWER, synthetic geometry (the fringing slab: a floating island, a port face
   bridging it to ground). Every eigenpair of the pencil is computed (dense), for the
   declared LUMPED inductor (f f^T / L) and for Palace's distributed SHEET, and every
   moment is compared with the static Dirichlet energy on the same mesh.
2. The committed L2 rung against the executed static record, on the SAME mesh: the band
   part of sum p/f^2 must not exceed 1/S0 if the lumped identity held for Palace's pencil.
3. The band moments of every committed rung (context).

Usage: identities.py --out analysis_identities.json
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sps
import scipy.sparse.linalg as spla

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import spectral as spc  # noqa: E402

af = spc.af
RUNGS = {"L2": "results/COUPLED-LADDER-O1-L2-20260916T080802Z/L2",
         "N1R": "results/COUPLED-LADDER-O1-L2-N1R-20260919T110053Z/L2",
         "N2R": "results/COUPLED-LADDER-O1-L2-N2R-20260918T061455Z/L2",
         "L3": "results/COUPLED-LADDER-O1-L3-20260916T091212Z/L3"}
STATIC_RECORD = "results/STATIC-ANCHOR-TEST-20260922T192243Z"


def _static_module():
    spec = importlib.util.spec_from_file_location(
        "sah_static", HERE.parent / "static-anchor-hypothesis" / "static_capacitance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def synthetic(n: int) -> dict:
    sc = _static_module()
    mesh, model = sc._slab(n, island_patch=True)
    st = sc.static_capacitance(mesh, **model)
    s = af.assemble_edge_system(mesh, **model)
    xyz, edges, L = s["scales"]["xyz_nd"], s["edges"], s["scales"]["L_nd"]
    _, t2e = af.edge_table(mesh)
    Kc = spc.curl_curl(mesh, xyz, edges, t2e)
    G = af.gradient_matrix(edges, len(mesh["xyz"]))
    A_direct = float(s["f_free"] @ spla.spsolve(s["M_free"].tocsc(), s["f_free"])) / L
    LE = L * st["energy_nd"]
    V = st["identity"]["port_voltage_of_grad_phi"]
    out = {"n": n, "free_edges": int(len(s["free"])), "port_voltage": V,
           "curl_grad_rel": float(abs(Kc @ G).max() / abs(Kc).max())}
    for name, K in (("lumped", Kc + sps.csr_matrix(np.outer(s["f_all"], s["f_all"]) / L)),
                    ("sheet", Kc + spc.sheet_port(mesh, xyz, edges, model["port_attr"], L,
                                                  s["port"]["w_nd"], s["port"]["l_nd"]))):
        lam, E = spc.all_modes(K, s["M_all"], s["free"])
        mo = spc.moments(lam, E, s["f_free"], L)
        p, lm = mo["p"], mo["lam"]
        worst = min((p[:k] * lm[:k]).sum() / p[:k].sum() ** 2 * LE for k in range(1, len(lm) + 1))
        out[name] = {"N": mo["N"], "inv_moment_times_V2_over_L_C_minus_1": mo["inv_moment"] * V * V / LE - 1,
                     "parseval_rel": mo["first_moment"] / A_direct - 1,
                     "min_over_k_B_k_over_N_k_S": worst}
    out["sheet"]["static_identity_Cprime_over_C_minus_1"] = (
        spc.port_constrained_energy(mesh, model) / st["energy_nd"] - 1 if abs(V - 1) < 1e-9 else None)
    out["sheet_minus_lumped_port_psd_min_eig"] = float(np.linalg.eigvalsh(
        spc.sheet_port(mesh, xyz, edges, model["port_attr"], L, s["port"]["w_nd"], s["port"]["l_nd"])
        [s["free"]][:, s["free"]].toarray() - np.outer(s["f_free"], s["f_free"]) / L).min())
    return out


def rung_moments(rel: str) -> dict:
    col = lambda f, i: [float(r[i]) for r in list(csv.reader(open(REPO / rel / "solver" / "postpro" / f)))[1:]]
    f = np.array(col("eig.csv", 1)); p = np.abs(np.array(col("port-EPR.csv", 1)))
    NB = float(p.sum()); inv = float((p / f ** 2).sum()); B = float((p * f ** 2).sum() / NB)
    return {"modes": int(len(f)), "N_B": NB, "B_GHz2": B, "H_GHz2": 1 / inv, "H_over_B": 1 / inv / B,
            "sum_p_over_f2": inv, "f1_squared": float(f[0] ** 2), "p1": float(p[0])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    S0 = json.loads((REPO / STATIC_RECORD / "summary.json").read_text())["S0_GHz2"]
    rungs = {k: rung_moments(v) for k, v in RUNGS.items()}
    res = {"synthetic_known_answer": [synthetic(n) for n in (2, 3, 4)],
           "committed_rungs": rungs,
           "L2_same_mesh_check": {"S0_static_GHz2": S0, "band_sum_p_over_f2": rungs["L2"]["sum_p_over_f2"],
                                  "delta_band_lower_bound": S0 * rungs["L2"]["sum_p_over_f2"] - 1,
                                  "S0_over_B0": S0 / rungs["L2"]["B_GHz2"],
                                  "B0_over_N_B_over_S0": rungs["L2"]["B_GHz2"] / rungs["L2"]["N_B"] / S0},
           "solves_on_qmhp_mesh": 0}
    text = json.dumps(res, indent=1, default=float)
    if a.out:
        Path(a.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
