#!/usr/bin/env python3
"""The N2R partial moments, the bookkeeping reconciled, and the tail that is NOT bounded.

Reads only committed N2R columns. Computes, with the two variants kept apart:

    N_partial = sum over the record's modes of |p_m|
    A_partial = sum over the record's modes of |p_m| f_m^2      [GHz^2]

and reconciles A_partial / N_partial against the a/N values already recorded in
spectral_compatibility.json, to establish that the recorded ``a`` IS the first
moment of the identity verified in moment_identities.py.

It then shows the thing that matters: the tail of A is not controlled by the
tail of N. A weight w omitted at frequency F contributes w to N and w F^2 to A,
so w -> 0 bounds nothing about A without a bound on F.

Offline. No network, no Palace, no FEM assembly.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
N2R = REPO / "results" / "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z" / "L2" / "solver" / "postpro"
SPECTRAL = REPO / "experiments" / "fem-spectral-mapping" / "spectral_compatibility.json"

#: Frequencies at which a hypothetical omitted weight is PLACED. These are
#: scenarios, not a range believed to contain anything: see the note in the
#: output. The list deliberately runs past the earlier 12-50 GHz table to show
#: that nothing in the data closes it off at the top.
PLACEMENTS_GHZ = (12.0, 15.0, 20.0, 30.0, 50.0, 100.0, 200.0)


def _rows(name: str) -> list[list[float]]:
    return [[float(c) for c in r] for r in list(csv.reader((N2R / name).open()))[1:]]


def main() -> None:
    eig, epr = _rows("eig.csv"), _rows("port-EPR.csv")
    f = [r[1] for r in eig]
    p = [abs(r[1]) for r in epr]
    spec = json.loads(SPECTRAL.read_text())
    variants = spec["records"]["N2R"]["spectral_variants"]
    recorded = spec["E_C_F1F1"]["a_over_N_spread_GHz2"]

    out = {}
    for key, v in variants.items():
        idx = v["included_modes"]
        n = sum(p[i - 1] for i in idx)
        a = sum(p[i - 1] * f[i - 1] ** 2 for i in idx)
        out[key] = {
            "modes": idx,
            "N_partial": n,
            "A_partial_GHz2": a,
            "A_over_N_GHz2": a / n,
            "recorded_a_over_N": recorded[f"N2R|{key}|normalisation_N_equals_sum_abs_p"],
            "recorded_a_with_N_equals_one": recorded[f"N2R|{key}|normalisation_N_equals_one"],
            "reproduces_the_record": (
                abs(a / n - recorded[f"N2R|{key}|normalisation_N_equals_sum_abs_p"]) < 1e-9
                and abs(a - recorded[f"N2R|{key}|normalisation_N_equals_one"]) < 1e-9
            ),
        }

    A, B = out["A_all_saved_modes"], out["B_field_resonant_only"]
    aA, nA = A["A_partial_GHz2"], A["N_partial"]
    delta = 1.0 - nA

    result = {
        "label": "N2R PARTIAL MOMENTS - RECONCILED, AND THE TAIL OF A LEFT OPEN",
        "what_this_establishes": (
            "the quantity the existing analysis calls 'a' IS the first moment "
            "A = sum_m p_m f_m^2 of the identity verified in moment_identities.py. Both "
            "variants reproduce the recorded a/N and a values to better than 1e-9 from the raw "
            "columns, so the identity A = q^H M^-1 q applies to the recorded number directly."
        ),
        "variants": out,
        "bookkeeping_correction": {
            "the_inconsistency": (
                "the N interval quoted previously used ALL NINE weights, while the a/N "
                "denominator sweep it was compared against used variant B's four. They are "
                "different denominators and must not appear in one budget."
            ),
            "N_all_nine": nA,
            "N_variant_B": B["N_partial"],
            "difference_in_N": nA - B["N_partial"],
            "difference_in_N_relative": (nA - B["N_partial"]) / nA,
            "difference_in_A_GHz2": aA - B["A_partial_GHz2"],
            "difference_in_A_relative": (aA - B["A_partial_GHz2"]) / aA,
            "size": (
                "the inconsistency is real but small - 5.1e-06 in N (5e-04 of it) and "
                "6.2e-04 GHz^2 in A (2.7e-04 of it). It is corrected by quoting one variant "
                "throughout, not by arguing it does not matter."
            ),
        },
        "the_tail_of_A_is_not_controlled_by_the_tail_of_N": {
            "delta_saved_all_nine": delta,
            "statement": (
                "a weight w omitted at frequency F contributes w to N and w F^2 to A. For fixed "
                "w, w F^2 is unbounded in F. So 'approximately zero omitted weight' constrains N "
                "and constrains NOTHING about A without an independent bound on F or on the "
                "moment itself."
            ),
            "scenarios": [
                {
                    "F_GHz": F,
                    "contribution_to_A_GHz2": delta * F * F,
                    "as_a_fraction_of_A_partial": delta * F * F / aA,
                }
                for F in PLACEMENTS_GHZ
            ],
            "these_are_scenarios_not_bounds": (
                "each row asks what WOULD follow if the whole of delta_saved were a single mode "
                "at that frequency. Nothing in the committed data says any of them is the case, "
                "nothing establishes that the missing spectrum lies in 12-50 GHz, and the list "
                "is not an uncertainty interval. The 100 and 200 GHz rows are included precisely "
                "to show the data does not close the top end."
            ),
            "no_universal_tail_rate_is_claimed": (
                "p_m = (q^H E_m)^2 / lambda_m has a 1/lambda denominator, but the numerator "
                "(q^H E_m)^2 varies with the mode and is not bounded below or above by anything "
                "measured here. A 1/omega^2 decay rate cannot be asserted from the denominator "
                "alone, and no rate is assumed in this record."
            ),
        },
        "what_a_direct_measurement_of_A_would_settle": (
            "A - A_partial is EXACTLY the omitted first moment, measured rather than scenarioed. "
            "If it is small the whole placement table above is excluded as a class, without "
            "assuming anything about where the missing weight sits. That is the tail bound the "
            "correction calls for, and no number of extra eigenmodes supplies it cheaply."
        ),
    }
    (HERE / "n2r_moments.json").write_text(json.dumps(result, indent=1) + "\n")
    print(result["label"])
    for k, v in out.items():
        print(f"  {k:<22} modes {v['modes']}")
        print(f"      N={v['N_partial']:.12f}  A={v['A_partial_GHz2']:.9f} GHz^2  "
              f"reproduces the record: {v['reproduces_the_record']}")
    print(f"  omitted-moment scenarios, delta_saved = {delta:.4e}:")
    for s in result["the_tail_of_A_is_not_controlled_by_the_tail_of_N"]["scenarios"]:
        print(f"      {s['F_GHz']:>6.0f} GHz -> {s['contribution_to_A_GHz2']:>9.4f} GHz^2 "
              f"({s['as_a_fraction_of_A_partial']:>7.2%} of A_partial)")


if __name__ == "__main__":
    main()
