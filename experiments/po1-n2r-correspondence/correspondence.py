#!/usr/bin/env python3
"""What the COMMITTED records can and cannot say about PO1 m1 <-> N2R mode correspondence.

The declared method for this analysis needs the archived volume fields. They are
NOT reachable from this environment (see ``artefacts`` below), so steps 2-6 of
that method did not run and no overlap matrix exists here. This script does the
part that IS possible offline, and is explicit that it is a WEAKER test:

  * both runs normalise every eigenvector to the SAME unit electric energy
    (E_elec = 6.671281904e-03 J in every row of both domain-E.csv files), so
    functionals of E are directly comparable between the two runs;
  * surface-Q.csv gives p_D and p_MA, the interface-dielectric integrals of
    |E|^2 and |E_n|^2 over the F1 port face, normalised by E_elec + E_cap;
  * port-V.csv gives the width-averaged line voltage V, a linear functional
    of E on that same face.

None of those three carries omega, L_s or an inductance, so none of them
smuggles the eigenfrequency into the comparison - which the task forbids.

What they CANNOT do is confirm a correspondence. They are three scalars against
~1e5 degrees of freedom, and every one of them is supported on the port face,
which is exactly where the operator was changed. A mode pair can therefore
differ substantially in these numbers while agreeing almost everywhere else.
They are used here only to EXCLUDE, never to select.

Offline. Reads only committed records. No network, no Palace, no field archive.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PO1 = REPO / "results" / "COUPLED-LADDER-O1-L2-PO1-20260920T204837Z" / "L2" / "solver" / "postpro"
N2R = REPO / "results" / "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z" / "L2" / "solver" / "postpro"

#: An N2R mode is EXCLUDED when a frequency-free field functional differs from
#: PO1 m1's by this factor or more. Declared here, and deliberately loose: the
#: port-face functionals are the quantities the operator change perturbs most,
#: so a tight threshold would exclude the true partner. It is an exclusion
#: rule only - passing it selects nothing.
EXCLUSION_FACTOR = 10.0


def _rows(path: Path) -> list[list[str]]:
    return [[c.strip() for c in r] for r in list(csv.reader(path.open()))[1:]]


def signatures(base: Path) -> dict[int, dict[str, float]]:
    """p_D, p_MA and |V| per mode: the frequency-free functionals both runs share."""
    q = {int(float(r[0])): (float(r[1]), float(r[3])) for r in _rows(base / "surface-Q.csv")}
    v = {int(float(r[0])): (float(r[1]), float(r[2])) for r in _rows(base / "port-V.csv")}
    out = {}
    for m in sorted(q):
        p_d, p_ma = q[m]
        out[m] = {
            "p_D": p_d,
            "p_MA": p_ma,
            "p_tangential": p_d - p_ma,
            "abs_V": math.hypot(*v[m]),
        }
    return out


def normalisation_is_common() -> dict[str, object]:
    """Both runs fix E_elec to one value, which is what makes the comparison legal."""
    seen = {}
    for tag, base in (("PO1", PO1), ("N2R", N2R)):
        vals = {f"{float(r[1]):.12e}" for r in _rows(base / "domain-E.csv")}
        seen[tag] = sorted(vals)
    common = len(seen["PO1"]) == 1 and seen["PO1"] == seen["N2R"]
    return {
        "each_run_uses_one_E_elec": {k: len(v) == 1 for k, v in seen.items()},
        "the_two_runs_agree": common,
        "E_elec_J": float(seen["PO1"][0]) if common else None,
        "why_it_matters": (
            "eigenvectors are scaled to unit electric energy, so a linear or quadratic "
            "functional of E has the same normalisation in both runs and may be compared "
            "directly. Without this the scalars would not be commensurable at all."
        ),
    }


def main() -> None:
    po1, n2r = signatures(PO1), signatures(N2R)
    target = po1[1]
    rows = []
    for m, s in n2r.items():
        ratios = {k: (s[k] / target[k]) for k in ("p_D", "p_MA", "abs_V")}
        worst = max(max(ratios.values()), 1.0 / min(ratios.values()))
        rows.append({
            "n2r_mode": m,
            "signature": s,
            "ratio_to_PO1_m1": ratios,
            "worst_factor": worst,
            "excluded": worst >= EXCLUSION_FACTOR,
        })
    surviving = [r["n2r_mode"] for r in rows if not r["excluded"]]

    po1_m1_GHz = float(_rows(PO1 / "eig.csv")[0][1])
    predictions = {
        "conditional_K_minus_Q_GHz2": 15.099651244,
        "conditional_K_minus_Q_over_N_GHz2": 15.099643672,
    }
    freq = {}
    for name, z in predictions.items():
        f = math.sqrt(z)
        freq[name] = {
            "predicted_GHz": f,
            "signed_difference_Hz": (po1_m1_GHz - f) * 1e9,
            "absolute_difference_Hz": abs(po1_m1_GHz - f) * 1e9,
            "relative_difference": abs(po1_m1_GHz - f) / po1_m1_GHz,
        }

    result = {
        "label": "OFFLINE CORRESPONDENCE ATTEMPT - FIELD ARCHIVES UNREACHABLE, CORRESPONDENCE NOT ESTABLISHED",
        "does_not_alter": (
            "PO1's committed record and its pre-declared verdict INCONCLUSIVE FOR MODE IDENTITY "
            "stand exactly as recorded. Nothing here amends them."
        ),
        "artefacts": {
            "PO1": {
                "workflow_run": 35536625799,
                "artifact_id": 10612713395,
                "name": "order1-ladder-fields-35536625799-1",
                "size_in_bytes": 114545095,
                "digest": "sha256:a156768cbd0723c9988ce4617db1d1c07f29d5376d2cc5e7bf6ee25906ea8dc8",
                "digest_source": "GitHub Actions artifacts API for this repository",
            },
            "N2R": {
                "workflow_run": 35313973073,
                "artifact_id": 10533683685,
                "name": "order1-ladder-fields-35313973073-1",
                "size_in_bytes": 113746865,
                "digest": "sha256:1ca851c4da54210270d6834f378bd8e5cf96e4db047beb546ac69a5079eb8b0e",
                "digest_source": "GitHub Actions artifacts API for this repository",
                "independently_corroborated": (
                    "this digest equals the one supplied separately, before the API was queried, "
                    "so the two agree on the same archive."
                ),
            },
            "download_status": "REFUSED BY EGRESS POLICY",
            "mechanism": (
                "the artifacts API returns HTTP 302 to *.blob.core.windows.net "
                "(productionresultssa16 for PO1, productionresultssa10 for N2R). The agent "
                "proxy answers 403 to the CONNECT for that host: connect_rejected, organisation "
                "policy. No attempt was made to work around it."
            ),
            "consequence": (
                "steps 2-6 of the declared method - mesh-identity verification, the complex-E "
                "overlap matrix, the weighted inner product, the optimal phase and scale, and "
                "the weighted RMS difference - DID NOT RUN. No overlap number in this record is "
                "computed from fields, because no field was read."
            ),
        },
        "externally_supplied_numbers": {
            "status": "NOT REPRODUCED - recorded as unverified third-party input, not adopted as evidence",
            "claim": {
                "PO1_m1_to_N2R_m2_overlap": 0.999927,
                "optimal_phase_weighted_RMS_difference": 0.01208,
                "PO1_m1_overlaps_with_N2R_m1_m3_m4_m5_m6": [0.0120, 0.000006, 0.000011, 0.000055, 0.000287],
            },
            "why_not_adopted": (
                "the task required independent reproduction. The inputs it needs are unreachable "
                "here, so nothing in this record confirms or contradicts these values."
            ),
            "one_internal_consistency_remark": (
                "the quoted overlap with N2R m1, 0.0120, equals the quoted RMS difference to "
                "three figures. That is what a near-unit overlap with m2 plus a small residue "
                "along m1 would look like, and it is consistent with removing a term supported "
                "at the F1 site. It is a remark about the supplied numbers' internal structure, "
                "NOT a verification of them."
            ),
        },
        "normalisation": normalisation_is_common(),
        "what_the_committed_records_do_establish": {
            "method": (
                "compare PO1 m1's frequency-free port-face functionals (p_D, p_MA, |V|) against "
                "every N2R mode's, and EXCLUDE any mode differing by a factor of "
                f"{EXCLUSION_FACTOR} or more in any of them."
            ),
            "uses_no_frequency": True,
            "exclusion_factor": EXCLUSION_FACTOR,
            "rows": rows,
            "surviving_candidates": surviving,
            "verdict": (
                f"{len(rows) - len(surviving)} of {len(rows)} N2R modes are excluded. "
                f"Modes {surviving} survive and CANNOT be separated by this evidence."
            ),
        },
        "why_this_cannot_confirm_a_correspondence": (
            "three scalars against roughly 1e5 degrees of freedom, and all three are supported on "
            "the F1 port face - precisely where the operator was changed. PO1 m1 and N2R m2 differ "
            "by about 37 % in p_D, which is entirely compatible with agreeing to ~1e-2 in a global "
            "norm. These functionals are therefore the WORST available proxy for a global overlap: "
            "they can rule a mode out, and they can never rule one in."
        ),
        "frequency_comparison": {
            "status": "CONDITIONAL - it presumes the correspondence this record did NOT establish",
            "PO1_m1_measured_GHz": po1_m1_GHz,
            "predictions": freq,
            "note_on_the_surviving_set": (
                "the three surviving N2R candidates are its field-resonant modes. Choosing among "
                "them by frequency is exactly the tiebreak the approval forbids, so this "
                "comparison is reported as conditional and is not used to select anything."
            ),
        },
    }
    (HERE / "correspondence.json").write_text(json.dumps(result, indent=1) + "\n")
    print(result["label"])
    print(f"\nexcluded {len(rows) - len(surviving)}/{len(rows)} N2R modes; surviving: {surviving}")
    for name, d in freq.items():
        print(f"  {name}: {d['predicted_GHz']:.9f} GHz  signed {d['signed_difference_Hz']:+.1f} Hz  "
              f"relative {d['relative_difference']:.3e}")


if __name__ == "__main__":
    main()
