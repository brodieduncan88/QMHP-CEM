#!/usr/bin/env python3
"""CONDITIONAL SPECTRAL CALCULATION - EM MAPPING UNVERIFIED.

Offline arithmetic on the committed scalar records of N1R (six eigenpairs) and
N2R (nine eigenpairs). It does two separate things:

1. FEM/EPR compatibility evidence. For every saved mode it computes the
   equipartition ratio R = (E_mag + E_ind)/(E_elec + E_cap) from domain-E.csv
   and, with it, the participation of the ASSEMBLED port operator
   p_exact = 1 - E_mag/(E_elec + E_cap), against Palace's REPORTED rank-one
   EPR |p| from port-EPR.csv. If the assembled port term were the rank-one
   circuit term f f^T / L, these two would be equal mode by mode.

2. The spectral construction G_F(z) = sum_m p_m/(z - f_m^2), evaluated as a
   CONDITIONAL DIAGNOSTIC in explicit variants, with every inclusion and
   exclusion recorded. Participation weights are never renormalised; where the
   algebra needs the total weight N it is carried explicitly and both
   N = sum|p| (self-consistent truncation) and N = 1 (assumed sum rule) are
   reported, so the dependence is visible rather than hidden.

No Palace run, no Route A result, no gate input, no coupling evidence. E_C is
not reported as a value: its normalisation is unestablished (see the note).
"""
from __future__ import annotations

import csv
import json
import math
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from models.route_a_inversion import charging_energy_GHz, coupling_GHz  # noqa: E402

LABEL = "CONDITIONAL SPECTRAL CALCULATION - EM MAPPING UNVERIFIED"
#: GHz^2 -> (rad/s)^2. coupling_GHz() takes k and b in (rad/s)^2, so every
#: quantity built from f^2 in GHz^2 is multiplied by this before it is passed.
W0 = (2.0 * math.pi * 1e9) ** 2
#: Declared superinductor at the F1 element site (H), from the solved config.
L_F = 1.0345665367517793e-07
RECORDS = {
    "N1R": "results/COUPLED-LADDER-O1-L2-N1R-20260919T110053Z",
    "N2R": "results/COUPLED-LADDER-O1-L2-N2R-20260918T061455Z",
}
#: Declared Route A eigenmode band (numerical-plan.md section 1).
BAND_GHz = (0.5, 9.0)


def _rows(path: Path):
    return [r for r in csv.reader(path.open())][1:]


def read_record(base: Path):
    post = base / "L2" / "solver" / "postpro"
    eig, epr, dom = _rows(post / "eig.csv"), _rows(post / "port-EPR.csv"), _rows(post / "domain-E.csv")
    if not (len(eig) == len(epr) == len(dom)):
        raise RuntimeError("eig/port-EPR/domain-E disagree on the mode count")
    modes = []
    for i, (e, p, d) in enumerate(zip(eig, epr, dom), start=1):
        E_elec, E_mag, E_cap, E_ind = (float(x) for x in d[1:5])
        total = E_elec + E_cap
        R = (E_mag + E_ind) / total
        modes.append({
            "m": i, "f_GHz": float(e[1]), "backward_error": float(e[4]),
            "p_reported_signed": float(p[1]), "p_reported_abs": abs(float(p[1])),
            "E_elec_J": E_elec, "E_mag_J": E_mag, "E_cap_J": E_cap, "E_ind_J": E_ind,
            "E_mag_over_total": E_mag / total,
            "equipartition_ratio_R": R, "equipartition_defect_1_minus_R": 1.0 - R,
            # p of the ASSEMBLED port operator: (E_elec+E_cap-E_mag)/(E_elec+E_cap)
            "p_assembled_operator": 1.0 - E_mag / total,
            "in_declared_band": BAND_GHz[0] <= float(e[1]) <= BAND_GHz[1],
        })
    return modes


#: An ad-hoc post-hoc separator on the equipartition defect, used ONLY to label
#: variant B. It was chosen after seeing the values and is not a declared or
#: approved criterion; the earlier description of this split as "no threshold is
#: invented" was wrong. The observed defects fall in two clusters, 1e-7..6e-5 and
#: ~1.0, and this constant sits between them; every mode's defect is reported so a
#: reader may apply any rule. Nothing material rests on it: variant A keeps every
#: mode and differs from variant B by 2e-9 in f_R and 6e-6 in g.
VARIANT_B_DEFECT_THRESHOLD = 1.0e-2


def classify(modes):
    """Label modes by the equipartition defect, using the ad-hoc threshold above."""
    for mo in modes:
        d = abs(mo["equipartition_defect_1_minus_R"])
        mo["group"] = "field-resonant (equipartition holds)" if d < VARIANT_B_DEFECT_THRESHOLD else \
                      "port-operator-localised (equipartition fails; E_mag is ~1e-5 of E_elec)"
        mo["included_in_variant_B"] = d < VARIANT_B_DEFECT_THRESHOLD
    return modes


#: A root is rejected, not silently realified, if its imaginary part is material
#: at this relative scale, or if any root is non-finite.
ROOT_IMAG_RTOL = 1.0e-9


def _real_roots(poly, w):
    """Roots of the numerator polynomial, rejecting materially complex or non-finite ones.

    For non-negative weights and distinct poles the zeros interlace the poles and are
    real; a materially complex root means the input is not of that form, or the
    polynomial root-finding is ill-conditioned for it. Either way it is reported as a
    failure rather than realified.
    """
    r = np.roots(poly)
    if not np.all(np.isfinite(r)):
        raise RuntimeError(f"non-finite root of the G_F numerator: {r}")
    scale = max(float(np.max(np.abs(w))), 1e-300)
    bad = np.abs(r.imag) > ROOT_IMAG_RTOL * np.maximum(np.abs(r), scale)
    if np.any(bad):
        raise RuntimeError(
            "materially complex roots of the G_F numerator, rejected rather than realified: "
            f"{r[bad]} (relative tolerance {ROOT_IMAG_RTOL:.1e})")
    return np.sort(r.real)


def removed_Q_roots(weights, w_GHz2, N):
    """Roots of z G(z) + 1 - N = 0: the eigenvalues of (K - Q, M) for this truncation.

    The exact identity det(zM - K + Q)/det(zM - K) = z G(z) + 1 - N (verified in
    review_checks_reconstructed.py) makes these the DECLARED rank-one removal, whereas
    the zeros of G are the NORMALISED removal (K - Q/N, M). They coincide only at N = 1.
    """
    weights = np.asarray(weights, float)
    w = np.asarray(w_GHz2, float)
    # z * Num(z) + (1 - N) * Den(z); z * Num shifts Num UP one degree, i.e. poly[:-1].
    poly = np.zeros(len(w) + 1)
    for i in range(len(w)):
        poly[:-1] = poly[:-1] + weights[i] * np.poly([w[j] for j in range(len(w)) if j != i])
    poly = poly + (1.0 - N) * np.poly(w)
    roots = _real_roots(poly, w)
    # Cross-check against the explicit truncated pencil: with A = diag(w) and
    # q_m = sqrt(w_m p_m), the declared removal is A - q q^T and the normalised one
    # is A - q q^T / N. Both must be positive semidefinite, since N <= 1.
    A = np.diag(w)
    qv = np.sqrt(np.maximum(weights * w, 0.0))
    direct = np.sort(np.linalg.eigvalsh(A - np.outer(qv, qv)))
    if direct.min() < -1e-9 * max(abs(w).max(), 1.0):
        raise RuntimeError(f"declared rank-one removal is not PSD on this truncation: {direct.min()}")
    if np.max(np.abs(direct - roots)) > 1e-6 * max(abs(w).max(), 1.0):
        raise RuntimeError(f"polynomial roots {roots} disagree with the explicit pencil {direct}")
    return roots


def spectral(weights, w_GHz2, N):
    """Zeros and residues of G(z) = sum_m weights_m/(z - w_m), carrying the total N.

    With G(z) ~ N/z at large z, 1/G = (1/N)(z - a/N - Sigma_hat(z)), so the
    self-energy residue at a zero beta is N / sum_m weights_m/(beta - w_m)^2.
    """
    weights = np.asarray(weights, float)
    w = np.asarray(w_GHz2, float)
    poly = np.zeros(len(w))
    for i in range(len(w)):
        poly = poly + weights[i] * np.poly([w[j] for j in range(len(w)) if j != i])
    beta = _real_roots(poly, w) if len(w) > 1 else np.array([])
    out = []
    for b in beta:
        terms = weights / (b - w) ** 2
        order = np.argsort(terms)[::-1]
        out.append({
            "beta_GHz2": float(b), "f_GHz": float(math.sqrt(b)) if b > 0 else float("nan"),
            "ctilde2_GHz4": float(N / terms.sum()),
            "residue_term_shares": {int(i + 1): float(terms[i] / terms.sum()) for i in order},
            "largest_term_mode": int(order[0] + 1),
            "term_ratio_largest_to_next": float(terms[order[0]] / terms[order[1]]) if len(terms) > 1 else float("inf"),
        })
    return {"a_GHz2_unnormalised": float((weights * w).sum()), "a_over_N_GHz2": float((weights * w).sum() / N),
            "N_used": float(N), "zeros": out}


def main():
    result = {
        "label": LABEL,
        "not": ["not a Route A result", "not VERIFIED-COMPUTATIONAL coupling evidence",
                "not gate input", "no Palace run", "no Route B", "participations never renormalised"],
        "withdrawn_claims": {
            "rank_implies_N_below_one": "WITHDRAWN. K_port != f f^T/L does NOT imply N < 1. The exact "
                                        "statement is N - N^2 = u^T K_curl u + u^T (K_port - Q) u with "
                                        "u = K^+ q, so N <= 1 always and N = 1 exactly when the static "
                                        "solution is curl-free AND its port trace is the uniform mode. "
                                        "A rank-2 port term with N = 1 is exhibited in "
                                        "review_checks_reconstructed.json.",
            "readout_zero_error_bound_2p3e_7": "WITHDRAWN. The mode's diagonal participation in "
                                               "DeltaK = K_port - Q is only the first-order term and does "
                                               "not bound the finite shift after removing DeltaK. The "
                                               "operator-mapping error is UNBOUNDED BY THE CURRENT "
                                               "EVIDENCE, which is not a claim that it is large.",
        },
        "units": {
            "mode_frequencies": "GHz from eig.csv; w_m = f_m^2 in GHz^2",
            "conversion_to_angular_squared": "multiply a GHz^2 quantity by W0 = (2*pi*1e9)^2 = "
                                             f"{W0:.9e} to obtain (rad/s)^2, which is what "
                                             "models.route_a_inversion.coupling_GHz expects for both k and b",
            "ctilde": "the self-energy residue ctilde^2 is in GHz^4; ctilde = sqrt(residue) is in GHz^2 "
                      "and is multiplied by W0 before it is passed as k",
            "L_F_H": L_F,
        },
        "records": {},
    }
    for name, rel in RECORDS.items():
        modes = classify(read_record(REPO / rel))
        sum_abs = sum(mo["p_reported_abs"] for mo in modes)
        resonant = [mo for mo in modes if mo["included_in_variant_B"]]
        localised = [mo for mo in modes if not mo["included_in_variant_B"]]
        in_band_res = [mo for mo in resonant if mo["in_declared_band"]]
        out_band_res = [mo for mo in resonant if not mo["in_declared_band"]]
        rec = {
            "record": rel, "saved_eigenpairs": len(modes), "modes": modes,
            "sum_abs_p_over_saved_modes": sum_abs,
            "delta_saved": 1.0 - sum_abs,
            "delta_saved_definition": "1 - sum(|p_mF|) over the modes saved in this record; "
                                      "NOT renamed delta_far: see the decomposition below",
            "decomposition_of_the_saved_sum": {
                "field_resonant_in_declared_band": sum(mo["p_reported_abs"] for mo in in_band_res),
                "field_resonant_above_declared_band": sum(mo["p_reported_abs"] for mo in out_band_res),
                "port_operator_localised": sum(mo["p_reported_abs"] for mo in localised),
            },
            "rank_one_premise_test": {
                "statement": "if the assembled port term were the rank-one circuit term f f^T / L, then "
                             "p_assembled_operator would equal |p_reported| for EVERY mode",
                "max_abs_difference_over_modes": max(abs(mo["p_assembled_operator"] - mo["p_reported_abs"]) for mo in modes),
                "worst_mode": max(modes, key=lambda mo: abs(mo["p_assembled_operator"] - mo["p_reported_abs"]))["m"],
                "difference_on_field_resonant_modes": {mo["m"]: mo["p_assembled_operator"] - mo["p_reported_abs"] for mo in resonant},
                "sum_p_assembled_over_saved_modes": sum(mo["p_assembled_operator"] for mo in modes),
            },
            "spectral_variants": {},
        }
        for vname, sel in (("A_all_saved_modes", modes), ("B_field_resonant_only", resonant)):
            w = [mo["f_GHz"] ** 2 for mo in sel]
            p = [mo["p_reported_abs"] for mo in sel]
            Nobs = float(sum(p))
            entry = {
                "included_modes": [mo["m"] for mo in sel],
                "excluded_modes": [{"m": mo["m"], "f_GHz": mo["f_GHz"],
                                    "reason": "equipartition defect 1-R = "
                                              f"{mo['equipartition_defect_1_minus_R']:.3e}: the mode's magnetic "
                                              "field energy is ~1e-5 of its electric energy, so it is not a "
                                              "field resonance of the modelled environment"}
                                   for mo in modes if mo not in sel],
                "normalisation_N_equals_sum_abs_p": spectral(p, w, Nobs),
                "normalisation_N_equals_one": spectral(p, w, 1.0),
            }
            # The zeros of G are the (K - Q/N, M) removal. The declared rank-one removal
            # (K - Q, M) is the root set of z G(z) + 1 - N; both are recorded, neither is
            # claimed to be the removal of the assembled K_port.
            declared = removed_Q_roots(p, w, Nobs)
            zeros_QoverN = [z["beta_GHz2"] for z in entry["normalisation_N_equals_sum_abs_p"]["zeros"]]
            lo, hi = w[0], w[1]
            cand_declared = [b for b in declared if lo < b < hi]
            cand_norm = [b for b in zeros_QoverN if lo < b < hi]
            entry["rank_one_removal_Q_versus_Q_over_N"] = {
                "identity": "det(zM - K + Q)/det(zM - K) = z G(z) + 1 - N",
                "zeros_of_G_are": "the nonzero eigenvalues of (K - Q/N, M), the NORMALISED removal",
                "roots_of_zG_plus_1_minus_N_are": "the eigenvalues of (K - Q, M), the DECLARED removal",
                "N_used": Nobs,
                "declared_removal_roots_GHz2": [float(b) for b in declared],
                "readout_root_declared_removal_GHz2": float(cand_declared[0]) if len(cand_declared) == 1 else None,
                "readout_zero_normalised_removal_GHz2": float(cand_norm[0]) if len(cand_norm) == 1 else None,
                "relative_difference_readout": (
                    abs(cand_declared[0] - cand_norm[0]) / cand_norm[0]
                    if len(cand_declared) == 1 and len(cand_norm) == 1 else None),
                "extra_low_root_GHz2": float(min(declared)) if len(declared) == len(w) else None,
                "extra_low_root_note": "the declared removal frees the island, so its pencil carries a "
                                       "zero mode; on this truncation that mode appears as a small "
                                       "positive root rather than exactly zero",
                "caveat": "both root sets are rank-one removals. Neither is the removal of the "
                          "assembled K_port, and that difference is not bounded by the committed evidence",
            }
            # the zero between the two lowest included modes is the readout candidate
            for key in ("normalisation_N_equals_sum_abs_p", "normalisation_N_equals_one"):
                zeros = entry[key]["zeros"]
                lo, hi = w[0], w[1]
                cand = [z for z in zeros if lo < z["beta_GHz2"] < hi]
                if len(cand) == 1:
                    z = cand[0]
                    ct = math.sqrt(max(z["ctilde2_GHz4"], 0.0))
                    z["derived_CONDITIONAL"] = {
                        "f_R_GHz": z["f_GHz"],
                        "g_MHz": coupling_GHz(ct * W0, z["beta_GHz2"] * W0, L_F) * 1e3,
                        "how": "f_R = sqrt(beta); g = coupling_GHz(sqrt(residue)*W0, beta*W0, L_F), "
                               "the registered algebra applied to the normal-mode coordinate",
                    }
                    z["is_readout_candidate_by_interlacing_only"] = True
            rec["spectral_variants"][vname] = entry
        result["records"][name] = rec

    # ---- CONDITIONAL far-mode sensitivity, on the real weights.
    # This is conditional on an interpretation of delta_saved that is NOT established:
    # that the deficit is omitted spectral weight at a frequency above the saved set.
    # It is reported separately from the unexplained deficit and is not an error bound.
    for name, rec in result["records"].items():
        sel = [mo for mo in rec["modes"] if mo["included_in_variant_B"]]
        w = [mo["f_GHz"] ** 2 for mo in sel]
        pw = [mo["p_reported_abs"] for mo in sel]
        base = None
        rows = []
        for f_far in (None, 12.0, 15.0, 20.0, 30.0, 50.0):
            ww, pp = (list(w), list(pw)) if f_far is None else (list(w) + [f_far ** 2], list(pw) + [rec["delta_saved"]])
            sp = spectral(pp, ww, sum(pp))
            z = [q for q in sp["zeros"] if ww[0] < q["beta_GHz2"] < ww[1]]
            if len(z) != 1:
                continue
            ct = math.sqrt(max(z[0]["ctilde2_GHz4"], 0.0))
            got = {"f_far_GHz": f_far, "f_R_GHz": z[0]["f_GHz"],
                   "g_MHz": coupling_GHz(ct * W0, z[0]["beta_GHz2"] * W0, L_F) * 1e3,
                   "a_over_N_GHz2": sp["a_over_N_GHz2"]}
            if f_far is None:
                base = got
            else:
                got["shift_f_R_rel"] = abs(got["f_R_GHz"] - base["f_R_GHz"]) / base["f_R_GHz"]
                got["shift_g_rel"] = abs(got["g_MHz"] - base["g_MHz"]) / base["g_MHz"]
                got["shift_a_over_N_rel"] = abs(got["a_over_N_GHz2"] - base["a_over_N_GHz2"]) / base["a_over_N_GHz2"]
            rows.append(got)
        rec["conditional_far_mode_sensitivity"] = {
            "condition": "assumes, without evidence, that the whole of delta_saved is spectral weight of a "
                         "single omitted mode at f_far; the deficit's actual origin is unresolved and includes "
                         "a strictly positive normalisation term (see the note)",
            "delta_saved_placed": rec["delta_saved"], "rows": rows}

    a, b = result["records"]["N1R"], result["records"]["N2R"]
    obs = {}
    for v in ("A_all_saved_modes", "B_field_resonant_only"):
        for n in ("normalisation_N_equals_sum_abs_p", "normalisation_N_equals_one"):
            ga = [z for z in a["spectral_variants"][v][n]["zeros"] if "derived_CONDITIONAL" in z]
            gb = [z for z in b["spectral_variants"][v][n]["zeros"] if "derived_CONDITIONAL" in z]
            if ga and gb:
                x, y = ga[0]["derived_CONDITIONAL"], gb[0]["derived_CONDITIONAL"]
                obs[f"{v}|{n}"] = {
                    "N1R": x, "N2R": y,
                    "observed_refinement_sensitivity_f_R": abs(y["f_R_GHz"] - x["f_R_GHz"]) / x["f_R_GHz"],
                    "observed_refinement_sensitivity_g": abs(y["g_MHz"] - x["g_MHz"]) / x["g_MHz"],
                    "caveat": "an observed difference between two solved discretisations; not an error "
                              "bound, not a convergence statement, not continuum accuracy",
                }
    result["observed_refinement_sensitivity"] = obs
    result["E_C_F1F1"] = {
        "status": "UNAVAILABLE",
        "why": "E_C is fixed by a = sum_m p_m f_m^2 divided by the total weight N, and N is the "
               "complete-mode normalisation f^T K^-1 f / L, which is not 1 for this FEM model and is "
               "not measured by any committed column. The spread of a/N across the variants below is "
               "recorded as evidence of that, not as a value.",
        "a_over_N_spread_GHz2": {
            f"{r}|{v}|{n}": result["records"][r]["spectral_variants"][v][n]["a_over_N_GHz2"]
            for r in ("N1R", "N2R") for v in ("A_all_saved_modes", "B_field_resonant_only")
            for n in ("normalisation_N_equals_sum_abs_p", "normalisation_N_equals_one")},
    }
    result["environment"] = {
        "python": platform.python_version(), "numpy": np.__version__,
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO).stdout.strip(),
    }
    _finite(result)
    (HERE / "spectral_compatibility.json").write_text(json.dumps(result, indent=1) + "\n")

    # ---- printed summary
    print(LABEL, "\n")
    for name, rec in result["records"].items():
        print(f"=== {name}: {rec['saved_eigenpairs']} saved eigenpairs ===")
        print(f"{'m':>2} {'f (GHz)':>12} {'|p| reported':>13} {'p assembled':>12} {'1-R':>10}  group")
        for mo in rec["modes"]:
            print(f"{mo['m']:>2} {mo['f_GHz']:>12.6f} {mo['p_reported_abs']:>13.6e} "
                  f"{mo['p_assembled_operator']:>12.6e} {mo['equipartition_defect_1_minus_R']:>10.3e}  {mo['group'][:38]}")
        d = rec["decomposition_of_the_saved_sum"]
        print(f"  sum|p| = {rec['sum_abs_p_over_saved_modes']:.10f}   delta_saved = {rec['delta_saved']:.6e}")
        print(f"    of the saved sum: in-band resonant {d['field_resonant_in_declared_band']:.7e}, "
              f"above-band resonant {d['field_resonant_above_declared_band']:.4e}, "
              f"port-localised {d['port_operator_localised']:.4e}")
        t = rec["rank_one_premise_test"]
        print(f"  rank-one premise: max |p_assembled - |p_reported|| = {t['max_abs_difference_over_modes']:.4e} "
              f"(mode {t['worst_mode']}); sum p_assembled over saved = {t['sum_p_assembled_over_saved_modes']:.4f}")
        for v, ent in rec["spectral_variants"].items():
            for n in ("normalisation_N_equals_sum_abs_p", "normalisation_N_equals_one"):
                zz = [z for z in ent[n]["zeros"] if "derived_CONDITIONAL" in z]
                if zz:
                    z = zz[0]; dd = z["derived_CONDITIONAL"]
                    print(f"    {v:24s} {n:34s} -> f_R = {dd['f_R_GHz']:.9f} GHz, g = {dd['g_MHz']:.6f} MHz "
                          f"(zero at {z['beta_GHz2']:.6f} GHz^2, residue {z['ctilde2_GHz4']:.6e} GHz^4, "
                          f"largest term mode {z['largest_term_mode']}, ratio {z['term_ratio_largest_to_next']:.3g})")
        print()
    print("observed refinement sensitivity (N1R -> N2R), not an error bound:")
    for k, v in result["observed_refinement_sensitivity"].items():
        print(f"  {k:62s} f_R {v['observed_refinement_sensitivity_f_R']:.3e}   g {v['observed_refinement_sensitivity_g']:.3e}")
    print("conditional far-mode sensitivity (conditional on an unestablished interpretation of delta_saved):")
    for name, rec in result["records"].items():
        for r in rec["conditional_far_mode_sensitivity"]["rows"]:
            if r["f_far_GHz"] is not None:
                print(f"  {name} f_far={r['f_far_GHz']:5.1f} GHz  f_R shift {r['shift_f_R_rel']:.2e}  "
                      f"g shift {r['shift_g_rel']:.2e}  a/N shift {r['shift_a_over_N_rel']:.2e}")
    print("\nE_C_F1F1:", result["E_C_F1F1"]["status"], "- a/N spread (GHz^2):",
          {k: round(v, 6) for k, v in result["E_C_F1F1"]["a_over_N_spread_GHz2"].items()})


def _finite(o, path="result"):
    if isinstance(o, dict):
        for k, v in o.items():
            _finite(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _finite(v, f"{path}[{i}]")
    elif isinstance(o, float) and not math.isfinite(o):
        raise RuntimeError(f"non-finite at {path}")


if __name__ == "__main__":
    main()
