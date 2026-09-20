#!/usr/bin/env python3
"""Review of the EXTERNALLY PRODUCED readout-field diagnostic.

Reads ``supplied/evaluation/results.json`` (produced outside this repository
from the hash-verified N1R/N2R field archives, which this environment cannot
read) and derives, by arithmetic on those numbers only:

  * per record and mode: the complex readout voltages on the pre-declared
    primary (+Y) and mirror (-Y) surfaces, their signed complex difference,
    that difference relative to the readout voltage and to the F-port voltage,
    rho_m on each surface, and the phase angle between the two surfaces;
  * per record: r12 on each surface, the signed complex mirror difference of
    r12 and its relative size;
  * between records: the signed and relative change of r12 per surface,
    reported separately from the surface dependence;
  * internal-consistency checks of the supplied file (r12 = rho_1/rho_2,
    the mirror and mesh metrics, and the F-port relative errors recomputed
    from the listed voltages).

Nothing here reproduces a field integral. Every number is derived from the
supplied JSON and is labelled DERIVED-FROM-EXTERNAL. No averaging of the two
surfaces and no substitution of one for the other is performed.
"""
from __future__ import annotations

import cmath
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "supplied" / "evaluation" / "results.json"
OUT = HERE / "review.json"


def c(d):
    return complex(d["real"], d["imag"])


def rel(a, b):
    return abs(a - b) / max(abs(a), abs(b))


def main():
    R = json.loads(SRC.read_text())
    out = {"label": "DERIVED-FROM-EXTERNAL: arithmetic on the supplied results.json; no field integral reproduced here",
           "source": "supplied/evaluation/results.json", "source_schema": R["schema"],
           "source_classification": R["classification"], "repository_pin_claimed_by_source": R["repository_read_only_pin"],
           "records": {}, "consistency": {}}
    tol = 1e-9
    for name, rec in R["datasets"].items():
        entry = {"modes": {}}
        for m, row in rec["modes"].items():
            vf = c(row["F_port"]["voltage_reconstructed_V"])
            vf_ref = c(row["F_port"]["voltage_reference_V"])
            vp = c(row["readout"]["plusY"]["voltage_V"])
            vm = c(row["readout"]["minusY"]["voltage_V"])
            rp = c(row["readout"]["plusY"]["rho"])
            rm = c(row["readout"]["minusY"]["rho"])
            d = vp - vm
            entry["modes"][m] = {
                "V_F_reconstructed_V": [vf.real, vf.imag],
                "V_F_csv_V": [vf_ref.real, vf_ref.imag],
                "V_R_plusY_V": [vp.real, vp.imag],
                "V_R_minusY_V": [vm.real, vm.imag],
                "V_plus_minus_V_minus_V": [d.real, d.imag],
                "abs_difference_V": abs(d),
                "difference_rel_to_V_R_plusY": abs(d) / abs(vp),
                "difference_rel_to_V_R_minusY": abs(d) / abs(vm),
                "difference_rel_to_V_R_mirror_metric": rel(vp, vm),
                "difference_rel_to_V_F": abs(d) / abs(vf),
                "phase_plusY_minus_minusY_deg": math.degrees(cmath.phase(vp / vm)),
                "rho_plusY": [rp.real, rp.imag], "rho_minusY": [rm.real, rm.imag],
                "rho_mirror_rel_diff": rel(rp, rm),
                "abs_imag_over_abs_rho_plusY": abs(rp.imag) / abs(rp),
                "abs_imag_over_abs_rho_minusY": abs(rm.imag) / abs(rm),
            }
            # consistency of the supplied file
            f_err = abs(vf - vf_ref) / abs(vf_ref)
            entry["modes"][m]["check_F_port_rel_error_recomputed"] = f_err
            entry["modes"][m]["check_F_port_rel_error_matches_supplied"] = abs(f_err - row["F_port"]["relative_complex_error"]) < 1e-15
            entry["modes"][m]["check_rho_plusY_equals_V_over_VF"] = abs(rp - vp / vf) <= tol * abs(rp)
            entry["modes"][m]["check_rho_minusY_equals_V_over_VF"] = abs(rm - vm / vf) <= tol * abs(rm)
            entry["modes"][m]["check_mirror_voltage_metric_matches_supplied"] = abs(rel(vp, vm) - row["mirror_voltage_relative_difference"]) < 1e-12
        r12p = c(rec["r12"]["plusY"]); r12m = c(rec["r12"]["minusY"])
        rho1p = c(rec["modes"]["1"]["readout"]["plusY"]["rho"]); rho2p = c(rec["modes"]["2"]["readout"]["plusY"]["rho"])
        rho1m = c(rec["modes"]["1"]["readout"]["minusY"]["rho"]); rho2m = c(rec["modes"]["2"]["readout"]["minusY"]["rho"])
        entry["r12_plusY_primary"] = [r12p.real, r12p.imag]
        entry["r12_minusY_mirror"] = [r12m.real, r12m.imag]
        entry["r12_plus_minus_r12_minus"] = [(r12p - r12m).real, (r12p - r12m).imag]
        entry["r12_mirror_rel_diff"] = rel(r12p, r12m)
        entry["r12_abs_imag_over_abs_plusY"] = abs(r12p.imag) / abs(r12p)
        entry["check_r12_plusY_equals_rho1_over_rho2"] = abs(r12p - rho1p / rho2p) <= tol * abs(r12p)
        entry["check_r12_minusY_equals_rho1_over_rho2"] = abs(r12m - rho1m / rho2m) <= tol * abs(r12m)
        entry["check_r12_mirror_metric_matches_supplied"] = abs(rel(r12p, r12m) - rec["r12_mirror_relative_difference"]) < 1e-12
        out["records"][name] = entry
    a, b = out["records"]["N1R"], out["records"]["N2R"]
    between = {}
    for side, key in (("plusY", "r12_plusY_primary"), ("minusY", "r12_minusY_mirror")):
        ra, rb = complex(*a[key]), complex(*b[key])
        sup = R["between_meshes"][side]
        between[side] = {"r12_N1R": [ra.real, ra.imag], "r12_N2R": [rb.real, rb.imag],
                         "signed_change_N2R_minus_N1R": [(rb - ra).real, (rb - ra).imag],
                         "relative_change": abs(rb - ra) / abs(ra),
                         "check_matches_supplied": abs(abs(rb - ra) / abs(ra) - sup["r12_relative_change"]) < 1e-12,
                         "same_exported_readout_triangle_geometry_per_source": sup["same_exported_readout_triangle_geometry"]}
    # per-mode voltage change between meshes, on each surface (mesh effect, separate from surface effect)
    for m in ("1", "2"):
        for side in ("V_R_plusY_V", "V_R_minusY_V", "V_F_reconstructed_V"):
            va = complex(*a["modes"][m][side]); vb = complex(*b["modes"][m][side])
            between.setdefault("per_mode_voltage_change", {})[f"m{m}_{side}"] = {
                "complex_rel_change": abs(vb - va) / abs(va),
                "magnitude_rel_change": (abs(vb) - abs(va)) / abs(va),
                "phase_change_deg": math.degrees(cmath.phase(vb / va)),
                "note": "the eigenvector's global phase differs between solves, so the complex change mixes a phase "
                        "rotation with a magnitude change; magnitudes share Palace's unit-energy normalisation, and "
                        "only ratios between quantities of one solve are free of both",
            }
        for side in ("plusY", "minusY"):
            ra1, rb1 = complex(*a["modes"][m][f"rho_{side}"]), complex(*b["modes"][m][f"rho_{side}"])
            between.setdefault("per_mode_rho_change", {})[f"m{m}_{side}"] = {
                "signed_change_N2R_minus_N1R": [(rb1 - ra1).real, (rb1 - ra1).imag],
                "relative_change": abs(rb1 - ra1) / abs(ra1)}
    out["between_meshes"] = between
    out["surface_vs_mesh_summary"] = {
        "surface_dependence_of_r12": {n: out["records"][n]["r12_mirror_rel_diff"] for n in out["records"]},
        "mesh_dependence_of_r12": {s: between[s]["relative_change"] for s in ("plusY", "minusY")},
        "ratio_surface_to_mesh_effect_plusY": out["records"]["N1R"]["r12_mirror_rel_diff"] / between["plusY"]["relative_change"],
    }
    out["all_consistency_checks_pass"] = all(
        v for e in out["records"].values() for k, v in e.items() if k.startswith("check_")
    ) and all(v for e in out["records"].values() for mm in e["modes"].values() for k, v in mm.items() if k.startswith("check_")) \
        and all(between[s]["check_matches_supplied"] for s in ("plusY", "minusY"))
    _finite(out)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    # printed table
    print(f"{out['label']}\n")
    print(f"{'rec':4} {'m':2} {'surface':7} {'Re V_R (V)':>14} {'Im V_R (V)':>14} {'Re rho':>14} {'Im rho':>12}")
    for n, e in out["records"].items():
        for m, mm in e["modes"].items():
            for side in ("plusY", "minusY"):
                v = mm[f"V_R_{side}_V"]; r = mm[f"rho_{side}"]
                print(f"{n:4} {m:2} {side:7} {v[0]:>14.9f} {v[1]:>14.9f} {r[0]:>14.9e} {r[1]:>12.2e}")
            d = mm["V_plus_minus_V_minus_V"]
            print(f"{'':4} {'':2} {'diff':7} {d[0]:>14.9f} {d[1]:>14.9f}  |d|={mm['abs_difference_V']:.4e} V  "
                  f"rel V_R(+Y)={mm['difference_rel_to_V_R_plusY']:.4e}  mirror={mm['difference_rel_to_V_R_mirror_metric']:.4e}  "
                  f"rel V_F={mm['difference_rel_to_V_F']:.4e}  phase(+/-)={mm['phase_plusY_minus_minusY_deg']:+.4f} deg")
        print(f"{n:4} r12 +Y {e['r12_plusY_primary']}  -Y {e['r12_minusY_mirror']}  diff {e['r12_plus_minus_r12_minus']}  "
              f"mirror rel {e['r12_mirror_rel_diff']:.5f}")
    for s, bb in between.items():
        if s.startswith("per_mode"):
            continue
        print(f"mesh N1R->N2R {s}: signed {bb['signed_change_N2R_minus_N1R']} rel {bb['relative_change']:.5f}")
    print("all consistency checks pass:", out["all_consistency_checks_pass"])


def _finite(obj, path="review"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            _finite(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _finite(v, f"{path}[{i}]")
    elif isinstance(obj, float) and not math.isfinite(obj):
        raise RuntimeError(f"non-finite at {path}")


if __name__ == "__main__":
    main()
