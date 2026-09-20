#!/usr/bin/env python3
"""Verify the SUPPLIED full-field correspondence package as far as it can be verified here.

The package in ``supplied/`` was computed elsewhere, in an environment that
could read the two field archives. This environment still cannot: the artifacts
API redirects to ``*.blob.core.windows.net`` and the egress policy denies it.
So this script does NOT recompute the overlaps from fields. It cannot, and it
does not pretend to.

What it DOES do is check everything about the package that is checkable without
the fields:

  * the package's own manifest;
  * the artefact digests against the ones this repository's Actions API reported
    (recorded in experiments/po1-n2r-correspondence/correspondence.json, which
    was written before this package existed);
  * the script's physical constants against the repository's own declaration -
    the permittivity and the vacuum/substrate attribute numbers;
  * the saved-mode count against the solved config's ``Solver.Eigenmode.Save``;
  * the export shape: points == 4 x cells, i.e. per-element vertex samples
    rather than node-averaged ones, which is what makes the affine-per-tet
    argument valid for a lowest-order Nedelec field;
  * the internal algebra - that the reported RMS is the identity
    ``sqrt(1 - overlap^2)`` and therefore NOT independent evidence, that Bessel
    holds over the saved set, and what that bounds for the N2R modes the archive
    does not contain;
  * the frequency arithmetic, against this repository's own independent
    computation of the same three numbers.

What it CANNOT check is the field data itself. Not one field sample was read
here. If the exports were not what they are said to be, or the VTU parse were
wrong, nothing in this script would notice.

Offline. No network, no Palace, no field archive.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUPPLIED = HERE / "supplied"
PRIOR = REPO / "experiments" / "po1-n2r-correspondence" / "correspondence.json"
PO1_CONFIG = (REPO / "results" / "COUPLED-LADDER-O1-L2-PO1-20260920T204837Z"
              / "L2" / "solver" / "config.json")

#: The correspondence the package asserts. Pinned so a silently different
#: package cannot pass this script unnoticed.
CLAIMED_PARTNER = ("PO1 m1", "N2R m2")
CLAIMED_OVERLAP = 0.9999270208301023


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_manifest() -> dict:
    lines = [ln.split() for ln in (SUPPLIED / "manifest.sha256").read_text().split("\n") if ln.strip()]
    out = {}
    for digest, name in lines:
        out[name] = {"expected": digest, "actual": _sha256(SUPPLIED / name)}
        out[name]["ok"] = out[name]["expected"] == out[name]["actual"]
    return out


def main() -> None:
    res = json.loads((SUPPLIED / "results.json").read_text())
    prior = json.loads(PRIOR.read_text())
    row = res["overlap"][0]
    best = max(range(len(row)), key=lambda j: row[j])
    runner = sorted(range(len(row)), key=lambda j: row[j], reverse=True)[1]
    bessel = sum(v * v for v in row)

    checks = {
        "package_manifest": check_manifest(),
        "artefact_digests_match_this_repositorys_api_reading": {
            tag: {
                "package": res["provenance"][tag]["artifact_sha256"],
                "recorded_here_before_the_package_existed":
                    prior["artefacts"][tag]["digest"].removeprefix("sha256:"),
                "ok": res["provenance"][tag]["artifact_sha256"]
                      == prior["artefacts"][tag]["digest"].removeprefix("sha256:"),
            }
            for tag in ("PO1", "N2R")
        },
        "constants_match_the_repository": {},
        "export_shape": {
            "points": res["mesh"]["points"],
            "cells": res["mesh"]["cells"],
            "points_equals_four_times_cells": res["mesh"]["points"] == 4 * res["mesh"]["cells"],
            "why_it_matters": (
                "per-element vertex samples, not node-averaged ones. A lowest-order Nedelec "
                "field is affine inside a tetrahedron, so P1 interpolation from four "
                "per-element vertex values reproduces it exactly and the P1 mass formula the "
                "script uses is the exact integral. Node averaging would have destroyed the "
                "normal-component jumps and made that formula an approximation."
            ),
        },
        "mesh_identity_AS_REPORTED_BY_THE_PACKAGE": {
            "coords_exact": res["mesh"]["coords_exact"],
            "connectivity_exact": res["mesh"]["connectivity_exact"],
            "attributes_exact": res["mesh"]["attributes_exact"],
            "caveat": (
                "these three booleans are the package's own output. They were not verified "
                "here, because verifying them needs the meshes this environment cannot read."
            ),
        },
        "internal_algebra": {
            "rms_is_the_identity_sqrt_one_minus_overlap_squared": {
                "reported_rms": res["po1_m1_n2r_m2"]["rms"],
                "sqrt_1_minus_ov2": math.sqrt(1 - CLAIMED_OVERLAP ** 2),
                "ok": abs(res["po1_m1_n2r_m2"]["rms"] - math.sqrt(1 - CLAIMED_OVERLAP ** 2)) < 1e-12,
                "consequence": (
                    "the RMS carries no information the overlap does not. It is a restatement, "
                    "not a second measurement, and must not be cited as corroboration."
                ),
            },
            "bessel_over_the_saved_set": {
                "sum_of_squared_overlaps": bessel,
                "at_most_one": bessel <= 1.0,
                "squared_norm_outside_the_saved_span": 1.0 - bessel,
            },
            "bound_on_the_N2R_modes_the_archive_does_not_contain": {
                "which": "N2R m7, m8, m9 - the run converged 9 modes and Solver.Eigenmode.Save is 6",
                "loose_bound_orthogonal_to_m2_only": math.sqrt(1 - CLAIMED_OVERLAP ** 2),
                "tighter_bound_from_bessel": math.sqrt(max(0.0, 1.0 - bessel)),
                "m2_exceeds_the_tighter_bound_by": CLAIMED_OVERLAP / math.sqrt(max(1e-300, 1.0 - bessel)),
                "why_the_bound_is_valid": (
                    "the inner product is the epsilon-weighted volume integral, which IS the "
                    "mass-matrix inner product of the generalised eigenproblem, so N2R's "
                    "eigenvectors are orthogonal under it. Bessel's inequality then bounds every "
                    "unsaved mode's overlap by the norm PO1 m1 leaves outside the saved span."
                ),
            },
            "best_and_second_best": {
                "best": {"n2r_mode": best + 1, "overlap": row[best]},
                "second": {"n2r_mode": runner + 1, "overlap": row[runner]},
                "ratio": row[best] / row[runner],
            },
        },
        "completes_the_prior_exclusion_analysis": {
            "prior_surviving_candidates": prior["what_the_committed_records_do_establish"]["surviving_candidates"],
            "resolution": {
                "2": f"overlap {row[1]:.12f} - the partner",
                "5": f"overlap {row[4]:.12f} - refuted by the field data",
                "8": (f"not in the archive; bounded at <= {math.sqrt(max(0.0, 1.0 - bessel)):.9f} "
                      "by Bessel over the saved set - cannot be the partner"),
            },
            "note": (
                "the prior analysis used only frequency-free port-face scalars and could not "
                "separate these three. It is completed, not contradicted."
            ),
        },
        "frequency_arithmetic_against_this_repositorys_own_computation": {},
    }

    decl = json.loads((REPO / "config" / "coupled" / "v2a_five_node_candidate.json").read_text())
    substrate = next(m for m in decl["materials"] if m["id"] == "substrate")
    sys.path.insert(0, str(REPO))
    from solvers.palace.coupled_mesh import TAGS  # noqa: PLC0415

    src = (SUPPLIED / "field_overlap_check.py").read_text()
    checks["constants_match_the_repository"] = {
        "substrate_permittivity": {
            "declared": float(substrate["permittivity"]),
            "used_by_the_script": 11.45,
            "ok": float(substrate["permittivity"]) == 11.45 and "11.45" in src,
        },
        "attribute_numbers": {
            "vacuum": TAGS["vacuum"], "substrate": TAGS["substrate"],
            "script_maps": "attr 1 -> 1.0, attr 3 -> 11.45",
            "ok": TAGS["vacuum"] == 1 and TAGS["substrate"] == 3,
        },
        "saved_mode_count": {
            "config_Solver_Eigenmode_Save": json.loads(PO1_CONFIG.read_text())["Solver"]["Eigenmode"]["Save"],
            "script_loops_over": 6,
            "ok": json.loads(PO1_CONFIG.read_text())["Solver"]["Eigenmode"]["Save"] == 6,
        },
    }

    fc = res["frequency_comparison"]
    mine = json.loads(PRIOR.read_text())["frequency_comparison"]["predictions"]
    checks["frequency_arithmetic_against_this_repositorys_own_computation"] = {
        "K_minus_Q": {
            "package_signed_Hz": fc["K_minus_Q_signed_Hz"],
            "computed_here_signed_Hz": mine["conditional_K_minus_Q_GHz2"]["signed_difference_Hz"],
            "ok": abs(fc["K_minus_Q_signed_Hz"]
                      - mine["conditional_K_minus_Q_GHz2"]["signed_difference_Hz"]) < 1e-6,
        },
        "K_minus_Q_over_N": {
            "package_signed_Hz": fc["K_minus_Q_over_N_signed_Hz"],
            "computed_here_signed_Hz": mine["conditional_K_minus_Q_over_N_GHz2"]["signed_difference_Hz"],
            "ok": abs(fc["K_minus_Q_over_N_signed_Hz"]
                      - mine["conditional_K_minus_Q_over_N_GHz2"]["signed_difference_Hz"]) < 1e-6,
        },
        "note": "the same arithmetic was done here independently, before the package arrived.",
    }

    def _all_ok(node) -> bool:
        if isinstance(node, dict):
            if "ok" in node and node["ok"] is False:
                return False
            return all(_all_ok(v) for v in node.values())
        return True

    out = {
        "label": "EXTERNAL FULL-FIELD CORRESPONDENCE - VERIFIED AS FAR AS IT CAN BE WITHOUT THE FIELDS",
        "supersedes": (
            "ONLY the transport limitation of experiments/po1-n2r-correspondence: that the "
            "archives were unreachable and so no overlap existed. An overlap now exists, "
            "computed elsewhere. Nothing else in that record is withdrawn, and PO1's committed "
            "record and its pre-declared INCONCLUSIVE FOR MODE IDENTITY verdict are untouched."
        ),
        "correspondence": {
            "partner": CLAIMED_PARTNER,
            "overlap": CLAIMED_OVERLAP,
            "rms_optimal_complex_scale": res["po1_m1_n2r_m2"]["rms"],
            "optimal_complex_scale": complex(res["po1_m1_n2r_m2"]["optimal_scale_real"],
                                             res["po1_m1_n2r_m2"]["optimal_scale_imag"]).__repr__(),
            "phase_rad": res["po1_m1_n2r_m2"]["phase_rad"],
            "po1_m1_overlap_row": row,
            "status": "ESTABLISHED BY EXTERNAL COMPUTATION, VERIFIED HERE ONLY IN ITS ALGEBRA AND PROVENANCE",
        },
        "not_verifiable_here": (
            "the field values themselves. No field sample was read in this environment - the "
            "egress policy still denies the archives. Every overlap number above is the "
            "package's; this record verifies its manifest, provenance, constants, export shape "
            "and internal algebra, and nothing about the fields."
        ),
        "checks": checks,
        "all_checks_pass": _all_ok(checks),
    }
    (HERE / "verification.json").write_text(json.dumps(out, indent=1) + "\n")
    print(out["label"])
    print(f"  all checks pass: {out['all_checks_pass']}")
    print(f"  partner: {CLAIMED_PARTNER[0]} <-> {CLAIMED_PARTNER[1]}  overlap {CLAIMED_OVERLAP:.12f}")
    b = checks["internal_algebra"]["bound_on_the_N2R_modes_the_archive_does_not_contain"]
    print(f"  unsaved N2R modes bounded at <= {b['tighter_bound_from_bessel']:.9f} "
          f"({b['m2_exceeds_the_tighter_bound_by']:.0f}x below m2)")


if __name__ == "__main__":
    main()
