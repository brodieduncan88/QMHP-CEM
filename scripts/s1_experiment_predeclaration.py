"""What the controlled local-refinement experiment will do, written before it runs.

Separated from the driver so it is a single reviewable artifact: the matching
rule, the diagnostic checks, the tolerances that do not change, and what each
possible outcome would and would not mean. Nothing here authorises a solve.

The experiment is a *discriminating diagnostic*, not a convergence study. Two
meshes at one base level cannot establish that anything converges, and this
predeclaration does not claim they can.
"""

from __future__ import annotations

from typing import Any

#: Measured on the committed records, and the numbers the outcomes are read against.
OBSERVED: dict[str, Any] = {
    "fluxonium_like_mode": {
        "frequency_GHz": {"L1": 1.158333, "L2": 1.461887, "L3": 1.709562},
        "shift_L2_to_L3_GHz": 0.247675,
        "port_participation_from_probes": {"L2": 9.985982e-01, "L3": 9.983353e-01},
        "note": (
            "its stiffness is almost entirely the port boundary term, so its frequency "
            "tracks the port-face tangential-field integral"
        ),
    },
    "readout_like_mode": {
        "frequency_GHz": {"L1": 3.693189, "L2": 3.885511, "L3": 4.087683},
        "shift_L2_to_L3_GHz": 0.202172,
        "port_participation_from_probes": {"L2": 7.803572e-04, "L3": 9.115929e-04},
        "note": "its stiffness is essentially all domain curl-curl; the port is negligible",
    },
    "port_face_elements_across_width": {"L1": 1.92, "L2": 2.33, "L3": 3.12},
}

#: Every acceptance tolerance, unchanged. Listed so a change would be visible.
UNCHANGED_TOLERANCES: dict[str, Any] = {
    "frozen_halo_participation_tolerance_abs": 1.0e-2,
    "frozen_halo_frequency_tolerance_rel": 1.0e-4,
    "eigenmode_backward_error_max_tolerance": 1.0e-6,
    "mode_admission_rule": "qmhp-cem.mode-admission/0.1.0, abs(R - 1) <= 1e-3",
    "mode_matching_rule": "qmhp-cem.mode-matching/0.1.1, two orderings plus the separation guard",
    "comparison_convention": "magnitudes, with the sign preserved and reported",
    "declared_window_GHz": [0.5, 9.0],
    "dof_budget": 250_000,
    "per_solve_wall_clock_cap_s": 2700,
    "finite_element_order": 1,
}

#: How modes are put in correspondence between the runs.
MODE_MATCHING: dict[str, Any] = {
    "rule": "qmhp-cem.mode-matching/0.1.1, imported unchanged",
    "applied_to": (
        "the admitted, in-window modes of the base level-2 run and of each refined run"
    ),
    "baseline": (
        "the committed COUPLED-LADDER-O1-L2 run is the baseline and is NOT re-solved: "
        "R1 and R2 differ from it in the mesh alone"
    ),
    "global_comparison_point": (
        "the committed COUPLED-LADDER-O1-L3 run, which refines everywhere by the same "
        "factor, is the contrast: it buys a 1.34x finer port face for 84 % more DOF"
    ),
    "if_matching_refuses": (
        "report the refusal and stop. A refusal is a result: it would mean the mode set "
        "changed under a mesh change that touches only the port neighbourhood, which is "
        "itself the finding."
    ),
}

#: Diagnostics computed on every run, reported rather than gating.
DIAGNOSTIC_CHECKS: list[dict[str, str]] = [
    {
        "check": "independent port participation",
        "how": (
            "solvers.palace.port_diagnostic with the conversion derived from that run's own "
            "config and its own mesh bounding box"
        ),
        "status": "reported, not a gate",
    },
    {
        "check": "probe versus closure",
        "how": "abs(p_probe/p_closure - 1); it was below 2e-5 on all 12 committed rows",
        "status": (
            "reported. A material disagreement would mean the derived conversion does not "
            "describe the refined mesh, and would have to be resolved before reading "
            "anything else."
        ),
    },
    {
        "check": "uniformity factor",
        "how": "E_ind/E_port, which Cauchy-Schwarz bounds by 1",
        "status": (
            "reported. It measures how far the port field is from the rank-one form the "
            "lumped-port circuit model represents, and refining the face may move it."
        ),
    },
    {
        "check": "port-face resolution, measured",
        "how": "solvers.palace.mesh_inspection: triangles, element size and elements across the width",
        "status": "reported; distinguishes what was requested from what was built",
    },
    {
        "check": "energy-balance admission",
        "how": "the unchanged rule, on the reported energies",
        "status": (
            "gate, unchanged. Note what it actually tests: with the port term evaluated "
            "correctly the balance closes for EVERY mode to about 2e-5, so the rule's "
            "discriminating power comes from the surrogate's failure. It selects modes "
            "whose port field is close to uniform and aligned, which is a useful "
            "criterion but is not the same as algebraic convergence."
        ),
    },
]

#: What each possible result would mean. Written before the runs.
OUTCOMES: list[dict[str, str]] = [
    {
        "id": "A",
        "if": (
            "the fluxonium-like mode moves under R1 and R2 by an amount comparable to or "
            "larger than its 0.248 GHz L2->L3 shift, while the readout-like mode moves by "
            "much less than its own 0.202 GHz L2->L3 shift"
        ),
        "would_mean": (
            "the port face's discretisation drives the fluxonium-like mode's frequency, and "
            "the global ladder was spending its DOF budget on the wrong region. R1 costs "
            "818 DOF more than the baseline, so a large shift at that price is strong "
            "evidence of locality."
        ),
        "would_not_mean": (
            "that the mode converges under port refinement, or that any limit has been "
            "identified. Two meshes cannot show that."
        ),
        "next_step": "a port-anchored refinement sequence long enough to test for an order",
    },
    {
        "id": "B",
        "if": "the fluxonium-like mode barely moves under R1 and R2",
        "would_mean": (
            "the port face is not what the L2->L3 shift was buying. The port-stiffness "
            "account of the energy *imbalance* is established separately and would stand; "
            "it would simply not be the frequency driver."
        ),
        "would_not_mean": "that the mesh is adequate, or that the ladder had converged",
        "next_step": (
            "refine at the zero-thickness PEC sheet edges generally, which are field "
            "singularities everywhere in this model, not only at the port"
        ),
    },
    {
        "id": "C",
        "if": "both modes move by comparable fractions of their L2->L3 shifts",
        "would_mean": (
            "a global effect reached the port box too, or the box perturbed more than "
            "intended. Check the measured distant element sizes against the baseline's "
            "before reading anything into it."
        ),
        "would_not_mean": "that local refinement failed",
        "next_step": "reduce the pad and repeat before drawing any conclusion",
    },
    {
        "id": "D",
        "if": (
            "the fluxonium-like mode moves from the baseline to R1 and then much less from "
            "R1 to R2"
        ),
        "would_mean": (
            "the port face was under-resolved and R1 resolves it enough for this mode. That "
            "is a statement about the port face only: the global mesh's own contribution "
            "would still be untested."
        ),
        "would_not_mean": "that the frequency has converged",
        "next_step": "repeat the pair at base level 3 to separate the two axes",
    },
    {
        "id": "E",
        "if": "the independent port participation changes materially between R1 and R2",
        "would_mean": "the port-face integral itself has not settled under the refinement",
        "would_not_mean": "anything about a limit; report the trend and its direction",
        "next_step": "extend the port-refinement sequence, not the global one",
    },
]

#: When the run stops without reading a frequency. Predeclared so that a stop
#: is a planned outcome and not a judgement call made after seeing numbers.
STOP_CONDITIONS: list[dict[str, str]] = [
    {
        "condition": "measured DOF above the 250 000 rule",
        "action": "the driver refuses to launch the solve and records REFUSED-DOF-BUDGET",
        "enforced_by": "scripts/palace_order1_ladder.py, already in place and unchanged",
    },
    {
        "condition": "a solve exceeds the 45-minute per-solve cap",
        "action": "the solve is killed and the rung is recorded as failed",
        "enforced_by": "the existing SOLVE_TIMEOUT_S; the cap is not extended",
    },
    {
        "condition": "the built mesh does not hash to the dry-run mesh named in the approval",
        "action": "stop before solving; the mesh is not the one that was approved",
        "enforced_by": "the approval's dry_run_mesh_sha256, checked by the driver",
    },
    {
        "condition": "the matching rule refuses",
        "action": (
            "report the refusal and stop. It would mean the mode set changed under a mesh "
            "change confined to the port neighbourhood, which is itself the finding."
        ),
        "enforced_by": "qmhp-cem.mode-matching/0.1.1, unchanged",
    },
    {
        "condition": (
            "the independent port participation disagrees with the closure requirement by "
            "more than 1e-4 on any mode"
        ),
        "action": (
            "stop and resolve that before reading any frequency: it would mean the derived "
            "conversion does not describe the refined mesh, and every other number in the "
            "run would be resting on it. Observed range on the committed rows is 2e-8 to "
            "4.3e-7, so this is a wide margin."
        ),
        "enforced_by": "reported per mode by solvers.palace.port_diagnostic",
    },
    {
        "condition": "both runs complete",
        "action": (
            "report against the five predeclared outcomes and STOP for review. No third "
            "mesh, no base-level change and no order-2 run without a further approval."
        ),
        "enforced_by": "this predeclaration",
    },
]

PREDECLARATION: dict[str, Any] = {
    "id": "qmhp-cem.s1-port-refinement-experiment/0.1.0",
    "status": "predeclared; awaiting the owner's approval. No solve is authorised by it.",
    "what_is_held_fixed": [
        "the S1 geometry, materials and substrate permittivity",
        "the port dimensions, direction and inductance",
        "the port formulation, conductor thickness and edge treatment",
        "every boundary condition and physical group",
        "the pinned Palace v0.13.0 image and every solver setting",
        "h_far, the halo, and the conductor/etch Distance field, so the distant size "
        "prescription is the baseline's",
    ],
    "what_changes": (
        "one number: the element size held over a declared box around the port face. The "
        "two meshes differ from each other in that number alone."
    ),
    "observed": OBSERVED,
    "unchanged_tolerances": UNCHANGED_TOLERANCES,
    "mode_matching": MODE_MATCHING,
    "stop_conditions": STOP_CONDITIONS,
    "diagnostic_checks": DIAGNOSTIC_CHECKS,
    "outcomes": OUTCOMES,
    "what_two_meshes_cannot_do": (
        "establish convergence, identify a limit, or measure an order. This experiment "
        "discriminates between candidate causes of the observed frequency drift; it does "
        "not resolve it."
    ),
    "approval_block_to_paste": {
        "where": ".github/ladder-approval.json, alongside the approved level",
        "R1": {
            "id": "R1", "h_port_mm": 0.003333333333333333,
            "pad_mm": 0.010, "transition_mm": 0.020, "ports": ["port_F1"],
        },
        "R2": {
            "id": "R2", "h_port_mm": 0.0016666666666666666,
            "pad_mm": 0.010, "transition_mm": 0.020, "ports": ["port_F1"],
        },
        "level": 2,
        "dry_run_mesh_sha256": {
            "R1": "a49ef282c7f07c56f210a450b291a2e027de530ba7c3e78bbdcead3b67315fee",
            "R2": "5a983c9125a9b9cefff017275e4088853fd93e4e9a41eee2109a2edb25c97bca",
        },
        "note": (
            "the hashes are for those exact values; the dry run is deterministic and "
            "reproduces them, which is asserted in tests/test_s1_recovery.py"
        ),
    },
    "cost": {
        "solves": 2,
        "order": 1,
        "dof_order1": {"R1": 80_762, "R2": 111_238},
        "dof_budget": 250_000,
        "per_solve_cap_s": 2700,
        "projected_wall_clock_s": {
            "R1": "about 82 s, from the baseline's 81.2 s at 79 944 DOF",
            "R2": "about 120 s, from the measured within-order timing exponent of 1.10",
        },
    },
}

__all__ = [
    "DIAGNOSTIC_CHECKS",
    "STOP_CONDITIONS",
    "MODE_MATCHING",
    "OBSERVED",
    "OUTCOMES",
    "PREDECLARATION",
    "UNCHANGED_TOLERANCES",
]
