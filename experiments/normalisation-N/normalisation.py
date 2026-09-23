#!/usr/bin/env python3
"""How far the committed records pin N, and whether pinning N unblocks E_C.

N is the complete-mode normalisation ``N = f^T K^+ f / L``, equivalently the sum
of the EPR participations over ALL modes, since ``p_m = (g . v_m)^2 >= 0`` with
``g = K^-1/2 f / sqrt(L)``.

Two facts already in the committed record bound it from both sides:

  * partial sums bound it BELOW, because every term is non-negative:
    ``N >= sum over the saved modes of |p_m|``;
  * the exact identity ``N - N^2 = u^T K_curl u + u^T (K_port - Q) u`` with
    ``u = K^+ q``, both terms non-negative, bounds it ABOVE by 1.

So ``N`` is confined to ``[sum_saved |p|, 1]``, a window of width exactly
``delta_saved``. That is a restatement of what fem-spectral-mapping.json already
holds, not a new measurement - but it is worth stating as a bound, because it
shows precisely why the committed data CANNOT split ``delta_saved`` into its two
parts: the window and the quantity to be split are the same number.

The second half of this script asks whether pinning N would unblock E_C, by
putting N's own contribution to ``a/N`` beside the other two contributions the
record measures. It would not, directly: N is the smallest of the three. Its
value is indirect - it decides whether the largest contribution exists at all.

Offline. Reads only committed records. No network, no Palace, no field archive.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SPECTRAL = REPO / "experiments" / "fem-spectral-mapping" / "spectral_compatibility.json"

#: The variant the budget is quoted in. B is field-resonant modes only with
#: N = sum|p|; the choice is stated rather than implied, and the A variant is
#: reported alongside so the conclusion can be seen not to depend on it.
VARIANT = "B_field_resonant_only"


def main() -> None:
    r = json.loads(SPECTRAL.read_text())
    spread = r["E_C_F1F1"]["a_over_N_spread_GHz2"]
    out = {}

    for record in ("N2R", "N1R"):
        rec = r["records"][record]
        lo = rec["sum_abs_p_over_saved_modes"]
        delta = rec["delta_saved"]
        base = spread[f"{record}|{VARIANT}|normalisation_N_equals_sum_abs_p"]
        unit = spread[f"{record}|{VARIANT}|normalisation_N_equals_one"]
        out[record] = {
            "bound_on_N": {
                "lower": lo,
                "lower_is": "sum of |p_m| over the modes this record saved; a partial sum of a non-negative series",
                "upper": 1.0,
                "upper_is": "N - N^2 = u^T K_curl u + u^T (K_port - Q) u with both terms >= 0, so N(1 - N) >= 0",
                "width": 1.0 - lo,
                "width_equals_delta_saved": abs((1.0 - lo) - delta) < 1e-15,
                "relative_width": 1.0 - lo,
                "status": (
                    "N is CONFINED, two-sidedly, to 0.0745 % - but not MEASURED. The window is "
                    "delta_saved itself, so this bound carries no information about how "
                    "delta_saved splits into (1 - N) and omitted spectral weight."
                ),
            },
            "a_over_N_budget": {
                "baseline_GHz2": base,
                "contributions": {
                    "the_N_normalisation_itself": {
                        "relative": abs(base - unit) / base,
                        "what_it_spans": "the entire admissible range of N, from sum|p| to 1",
                    },
                },
            },
        }
        if record == "N2R":
            r1 = spread[f"N1R|{VARIANT}|normalisation_N_equals_sum_abs_p"]
            c = out[record]["a_over_N_budget"]["contributions"]
            c["refinement_N1R_to_N2R"] = {
                "relative": abs(base - r1) / r1,
                "what_it_is": "an observed difference between two solved discretisations; not an error bound",
            }
            for row in rec["conditional_far_mode_sensitivity"]["rows"]:
                if row["f_far_GHz"] is None:
                    continue
                c[f"placing_the_omitted_weight_at_{row['f_far_GHz']:.0f}_GHz"] = {
                    "relative": row["shift_a_over_N_rel"],
                    "what_it_is": "conditional on the whole of delta_saved being one omitted mode there",
                }

    n2 = out["N2R"]["a_over_N_budget"]["contributions"]
    n_own = n2["the_N_normalisation_itself"]["relative"]
    refine = n2["refinement_N1R_to_N2R"]["relative"]
    far_min = min(v["relative"] for k, v in n2.items() if k.startswith("placing"))

    result = {
        "label": "N: BOUNDED TWO-SIDEDLY BY THE COMMITTED RECORDS, NOT MEASURED - AND NOT THE BINDING CONSTRAINT ON E_C",
        "question": "does measuring N unblock E_C?",
        "answer": "NO, not on its own.",
        "why": {
            "1_N_is_the_smallest_term": (
                f"across its ENTIRE admissible range, N moves a/N by {n_own:.3e}. The refinement "
                f"difference moves it by {refine:.3e}, {refine / n_own:.0f}x more, and the "
                f"far-mode placement by at least {far_min:.3e}, {far_min / n_own:.0f}x more. "
                "Pinning N exactly would collapse the smallest of the three."
            ),
            "2_but_N_is_still_the_right_lever": (
                "delta_saved = (1 - N) + omitted_weight, both non-negative. Measuring N splits "
                "it: omitted_weight = delta_saved - (1 - N). If that comes out ~0 there are no "
                "missing modes and the far-mode ambiguity - the LARGEST contribution - vanishes "
                "entirely. If it comes out ~delta_saved the ambiguity stands in full. So N does "
                "not tighten a/N directly; it decides whether the dominant term exists."
            ),
            "3_even_then_E_C_is_not_unblocked": (
                f"the refinement contribution, {refine:.3e}, is an observed difference between "
                "two discretisations and is untouched by any measurement of N. E_C would still "
                "rest on one mesh with no convergence statement."
            ),
        },
        "what_measuring_N_would_take": {
            "it_is_not_an_eigenvalue": (
                "N = f^T K^+ f / L is a STATIC quantity: one linear solve K u = f with the same "
                "operator the eigensolver assembles, then N = f^T u / L. No eigenproblem computes "
                "it, and summing p_m over more eigenmodes converges only as the 1/omega^2 tail."
            ),
            "pinned_palace_cannot_do_it_directly": (
                "the five solver types are DRIVEN, EIGENMODE, ELECTROSTATIC, MAGNETOSTATIC and "
                "TRANSIENT (utils/configfile.hpp). None computes f^T K^+ f / L. In particular "
                "MAGNETOSTATIC builds CurlCurlOperator with SurfaceCurrentOperator excitation, so "
                "it omits K_port entirely and its excitation is not the port voltage functional f."
            ),
            "the_plausible_supported_route": (
                "a DRIVEN sweep at frequencies well below the lowest resonance. The driven system "
                "matrix carries the same K = K_curl + K_port, and f^T (K - omega^2 M)^-1 f / L = "
                "sum_m p_m / (1 - omega^2 / lambda_m) -> N as omega -> 0, so two or three low "
                "frequencies extrapolated in omega^2 would give N. This is NOT proposed as ready: "
                "it needs the exact identification of which reported driven quantity equals "
                "f^T (K - omega^2 M)^-1 f, verified against the pinned source, and it is a solver "
                "type this campaign has never run."
            ),
            "not_attempted_here": (
                "no configuration was written, nothing was launched, and no approval exists for a "
                "driven solve. The PO1 approval authorised one eigenmode run and is spent."
            ),
        },
        "records": out,
    }
    (HERE / "normalisation.json").write_text(json.dumps(result, indent=1) + "\n")
    print(result["label"])
    print(f"  N in [{out['N2R']['bound_on_N']['lower']:.12f}, 1]  width "
          f"{out['N2R']['bound_on_N']['width']:.3e}")
    print(f"  a/N contributions: N itself {n_own:.3e} | refinement {refine:.3e} | far-mode >= {far_min:.3e}")
    print(f"  answer: {result['answer']}")


if __name__ == "__main__":
    main()
