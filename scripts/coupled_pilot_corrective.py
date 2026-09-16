#!/usr/bin/env python3
"""Corrective analysis of a completed coupled-pilot record.

Re-reads a preserved pilot record and recomputes its cross-run comparisons
under a corrected mode admission and matching procedure. It **launches
nothing**: no Palace, no container, no solve. It reads the solver outputs that
are already on disk.

What it does NOT do, by construction:

* It never writes inside the source record. The source tree's manifest is
  verified before the analysis and again after the new record is written, and
  the run fails if a single byte moved.
* It does not change any existing numerical tolerance. The frozen halo criteria
  (``dp <= 1e-2``, ``df <= 1e-4``) are read from the approval record and from
  the pilot driver and cross-checked against each other; if they disagree, or
  differ from the values frozen before the pilot ran, this refuses to run.
* It performs no coupling extraction: no Route A inversion, no ``g``, no
  charging energy, no capacitance, no circuit parameter of any kind.

What it produces is a separate, versioned record: which computed rows carry a
participation two solves may be compared on, which of them correspond to which
between the runs, and what the frozen criteria say once the comparison is made
on matched admitted modes with magnitudes, instead of on whatever row happened
to carry the smallest signed participation. Where the evidence does not settle
a question it says so and names the diagnostic that would.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import manifest  # noqa: E402
from solvers.palace.coupled_config import COUPLED_SOLVER_RULES  # noqa: E402
from solvers.palace.mode_admission import (  # noqa: E402
    ADMISSION_RULE,
    COMPARISON_CONVENTION,
    MATCHING_RULE,
    ROW_CORRESPONDENCE_TOLERANCE,
    AdmissionReport,
    admit_modes,
    check_row_correspondence,
    join_modes_by_id,
    label_roles,
    match_runs,
    unique_field_dominated,
)

RECORD_SCHEMA = "qmhp-cem.corrective-analysis/0.1.0"
RECORD_VERSION = 1
RECORD_PREFIX = "COUPLED-PILOT-CORR"

#: The values frozen in execution-proposal.md §4.2 BEFORE the pilot ran. This
#: script refuses to run if either of its two independent sources has drifted
#: from them, so a corrective analysis cannot quietly relax what it re-reads.
FROZEN_HALO_CRITERIA: dict[str, float] = {
    "max_relative_participation_change": 1.0e-2,
    "max_relative_frequency_change": 1.0e-4,
}

STATEMENT = (
    "Corrective analysis of an already-executed numerical-method pilot. No solve was launched "
    "and no solver output was modified: the source record is read-only evidence and its manifest "
    "is verified before and after. NO coupling extraction was performed — no Route A inversion, "
    "no g, no charging energy, no capacitance, no circuit parameter. Every geometric value "
    "remains an unapproved ENGINEERING-SEED and the 10 % agreement ENGINEERING-RULE is untouched."
)


class CorrectiveAnalysisError(RuntimeError):
    """The corrective analysis cannot proceed on the evidence as given."""


# --- preconditions ----------------------------------------------------------


def read_frozen_criteria() -> dict[str, Any]:
    """Read the frozen criteria from two independent places and cross-check.

    One is the approval record the pilot ran under; the other is the pilot
    driver's own constant. Both must equal the values frozen before the pilot.
    """
    approval_path = REPO_ROOT / ".github" / "pilot-approval.json"
    approval = json.loads(approval_path.read_text())["frozen_criteria"]
    from_approval = {
        "max_relative_participation_change": float(approval["max_relative_participation_change"]),
        "max_relative_frequency_change": float(approval["max_relative_frequency_change"]),
    }

    driver_path = REPO_ROOT / "scripts" / "palace_coupled_pilot.py"
    namespace: dict[str, Any] = {}
    source = driver_path.read_text()
    marker = "HALO_CRITERIA: dict[str, float] = {"
    start = source.index(marker) + len(marker) - 1
    depth, end = 0, start
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    exec(f"HALO_CRITERIA = {source[start:end]}", namespace)  # noqa: S102 - a literal dict
    from_driver = {k: float(v) for k, v in namespace["HALO_CRITERIA"].items()}

    for name, found in (("pilot-approval.json", from_approval), ("palace_coupled_pilot.py", from_driver)):
        if found != FROZEN_HALO_CRITERIA:
            raise CorrectiveAnalysisError(
                f"the frozen halo criteria in {name} are {found}, not the values frozen before "
                f"the pilot ran ({FROZEN_HALO_CRITERIA}). A corrective analysis may not proceed "
                f"against a moved tolerance."
            )
    return {
        "criteria": dict(FROZEN_HALO_CRITERIA),
        "frozen_in": "docs/coupled-candidate/execution-proposal.md §4.2, before the pilot ran",
        "cross_checked_against": [".github/pilot-approval.json", "scripts/palace_coupled_pilot.py"],
        "unchanged": True,
    }


def source_record_digests(source: Path) -> dict[str, Any]:
    """Verify the source record and capture what it hashed to."""
    discrepancies = manifest.verify(source)
    if discrepancies:
        raise CorrectiveAnalysisError(
            f"{source} does not match its own manifest: {discrepancies}. The corrective analysis "
            f"refuses to build on evidence that has moved."
        )
    manifest_path = source / "manifest.sha256"
    body = manifest_path.read_bytes()
    entries: dict[str, str] = {}
    for line in body.decode().splitlines():
        if not line.strip():
            continue
        digest, _, rel = line.partition("  ")
        entries[rel.strip()] = digest.strip()
    return {
        "record": source.name,
        "path": source.as_posix(),
        "manifest_sha256": hashlib.sha256(body).hexdigest(),
        "files": dict(sorted(entries.items())),
        "file_count": len(entries),
        "verified_utc": datetime.now(timezone.utc).isoformat(),
    }


# --- the analysis -----------------------------------------------------------


def port_inductance_from_record(source: Path, summary: dict[str, Any]) -> dict[int, float]:
    """The lumped-port inductance the solves actually used.

    Taken from the record's own summary, and cross-checked against the solver
    config Palace was handed. These are the numbers that ran; nothing is
    recomputed from the declaration.
    """
    values = {
        run: float(entry["port_inductance_H"])
        for run, entry in summary["runs"].items()
        if entry.get("port_inductance_H")
    }
    distinct = sorted(set(values.values()))
    if len(distinct) != 1:
        raise CorrectiveAnalysisError(f"the runs used different port inductances: {values}")
    inductance = distinct[0]
    for run in sorted(summary["runs"]):
        config_path = source / run / "solver" / "config.json"
        if not config_path.exists():
            continue
        ports = json.loads(config_path.read_text())["Boundaries"]["LumpedPort"]
        for port in ports:
            if abs(float(port["L"]) - inductance) > 1e-18:
                raise CorrectiveAnalysisError(
                    f"{config_path} gives port {port['Index']} L={port['L']}, but the summary "
                    f"records {inductance}"
                )
    return {1: inductance}


def analyse_run(source: Path, run: str, port_inductance_H: dict[int, float]) -> AdmissionReport:
    postpro = source / run / "solver" / "postpro"
    modes = join_modes_by_id(postpro)
    correspondence = check_row_correspondence(modes, port_inductance_H)
    report = admit_modes(
        run,
        modes,
        backward_error_tolerance=COUPLED_SOLVER_RULES["eigenmode_backward_error_max_tolerance"],
        row_correspondence=correspondence,
    )
    return report


def evaluate_frozen_criteria(match: Any, criteria: dict[str, float], subject: Any | None) -> dict[str, Any]:
    """Apply the UNCHANGED frozen criteria to a matched comparison.

    Every matched pair is evaluated, so nothing is selected after the numbers
    are known. The pair the criterion was written about — the single
    field-dominated admitted mode — is named separately, and the verdict is
    driven by the criterion's own subject.
    """
    if not match.comparable:
        return {
            "evaluated": False,
            "reason": match.reason,
            "criteria": dict(criteria),
        }

    rows = []
    for pair in match.pairs:
        delta_f = pair.delta_f_relative
        delta_p = pair.delta_abs_participation_relative.get(1, 0.0)
        rows.append(
            {
                "a_mode": pair.a.mode,
                "b_mode": pair.b.mode,
                "a_frequency_GHz": pair.a.frequency_GHz,
                "b_frequency_GHz": pair.b.frequency_GHz,
                "delta_f_relative": delta_f,
                "delta_abs_p_relative": delta_p,
                "frequency_check": "PASS" if delta_f <= criteria["max_relative_frequency_change"] else "FAIL",
                "participation_check": "PASS" if delta_p <= criteria["max_relative_participation_change"] else "FAIL",
                "is_criterion_subject": bool(subject is not None and pair.a.mode == subject.mode),
            }
        )
    return {
        "evaluated": True,
        "criteria": dict(criteria),
        "convention": dict(COMPARISON_CONVENTION),
        "criterion_subject": (
            {
                "basis": "the single field-dominated admitted in-window mode of run A",
                "mode": subject.mode,
                "frequency_GHz": subject.frequency_GHz,
            }
            if subject is not None
            else {"basis": "no unique field-dominated admitted mode; every pair is reported instead"}
        ),
        "pairs": rows,
        "all_pairs_reported": True,
    }


def halo_disposition(evaluation: dict[str, Any]) -> dict[str, Any]:
    """The predeclared outcome of execution-proposal.md §4.2, re-derived.

    The three outcomes were written down before the pilot ran and are applied
    here unchanged. The frequency outcome dominates: a frequency moving more
    than the tolerance between two size fields at one refinement level is not a
    statement about the halo at all.
    """
    if not evaluation.get("evaluated"):
        return {
            "verdict": "NOT-ASSESSABLE",
            "reason": evaluation.get("reason", "the two runs could not be matched"),
        }
    subject_rows = [r for r in evaluation["pairs"] if r["is_criterion_subject"]]
    rows = subject_rows or evaluation["pairs"]
    frequency_failed = any(r["frequency_check"] == "FAIL" for r in rows)
    participation_failed = any(r["participation_check"] == "FAIL" for r in rows)
    any_frequency_failed = any(r["frequency_check"] == "FAIL" for r in evaluation["pairs"])

    if frequency_failed or any_frequency_failed:
        return {
            "verdict": "NOT-A-HALO-VERDICT",
            "outcome": "the third predeclared outcome of execution-proposal.md §4.2",
            "reason": (
                "the frequency check failed, which that section predeclared is not a halo verdict "
                "at all: a frequency moving that much between two size fields at the same "
                "refinement level indicates the level-1 mesh is too coarse for this geometry, or "
                "the model is wrong. The halo question is not answerable from this record."
            ),
            "frequency_check": "FAIL",
            "participation_check": "FAIL" if participation_failed else "PASS",
        }
    if participation_failed:
        return {
            "verdict": "HALO-REJECTED",
            "outcome": "the second predeclared outcome of execution-proposal.md §4.2",
            "reason": "the participation changed by more than the frozen tolerance",
            "frequency_check": "PASS",
            "participation_check": "FAIL",
        }
    return {
        "verdict": "HALO-ADMISSIBLE",
        "outcome": "the first predeclared outcome of execution-proposal.md §4.2",
        "reason": "both frozen checks passed on matched physical modes",
        "frequency_check": "PASS",
        "participation_check": "PASS",
    }


def build(source: Path, *, batch_id: str) -> dict[str, Any]:
    summary = json.loads((source / "summary.json").read_text())
    frozen = read_frozen_criteria()
    digests = source_record_digests(source)
    inductance = port_inductance_from_record(source, summary)

    runs = sorted(summary["runs"])
    reports = {run: analyse_run(source, run, inductance) for run in runs}

    floor = COUPLED_SOLVER_RULES["band_floor_GHz"]
    ceiling = COUPLED_SOLVER_RULES["band_ceiling_GHz"]

    per_run: dict[str, Any] = {}
    for run in runs:
        report = reports[run]
        in_window = report.admitted_in_window(floor, ceiling)
        entry = report.as_dict()
        entry["spec"] = summary["runs"][run]["spec"]
        entry["status_as_executed"] = summary["runs"][run]["status"]
        entry["wall_clock_s"] = summary["runs"][run]["run"]["wall_clock_s"]
        entry["dof_measured"] = summary["runs"][run]["dof_for_this_order"]
        entry["declared_window_GHz"] = [floor, ceiling]
        entry["admitted_in_window"] = [r.mode for r in in_window]
        entry["admitted_outside_window"] = [
            r.mode for r in report.admitted if not r.in_window(floor, ceiling)
        ]
        entry["roles"] = [r.as_dict() for r in label_roles(report.admitted)]
        per_run[run] = entry

    comparisons: dict[str, Any] = {}
    for label, (a, b) in (
        ("order_sensitivity_P1_vs_P2", ("P1", "P2")),
        ("halo_sensitivity_P1_vs_P3", ("P1", "P3")),
    ):
        if a not in reports or b not in reports:
            continue
        window_a = reports[a].admitted_in_window(floor, ceiling)
        window_b = reports[b].admitted_in_window(floor, ceiling)
        match = match_runs(f"{a} vs {b}", window_a, window_b)
        subject = unique_field_dominated(window_a)
        evaluation = evaluate_frozen_criteria(match, frozen["criteria"], subject)
        comparisons[label] = {
            "runs": [a, b],
            "match": match.as_dict(),
            "frozen_criteria_evaluation": evaluation,
        }

    halo = halo_disposition(comparisons.get("halo_sensitivity_P1_vs_P3", {}).get("frozen_criteria_evaluation", {}))

    superseded = {
        "note": (
            "The source record's own halo_verdict is preserved unchanged in that record. It is "
            "restated here beside the corrected comparison so the difference is visible, not "
            "hidden. The verdict is the same; the numbers behind it are not."
        ),
        "source_record_halo_verdict": summary.get("halo_verdict", {}),
        "why_the_source_numbers_were_wrong": [
            (
                "Mode selection: the source driver defined 'the readout-like mode' as the "
                "in-window row with the smallest |p|. A row whose reported energies do not "
                "balance has a small |p| for that reason, so the rule selected the least "
                "trustworthy row in the window, and selected a different one in each run."
            ),
            (
                "Comparison convention: the participation difference was taken on SIGNED values. "
                "Palace's sign is sign(Re I) and is not invariant under the eigenvector's global "
                "phase, so a sign difference between two independent solves inflates the "
                "difference without measuring anything."
            ),
        ],
        "rows_the_source_rule_selected": {
            run: min(
                (
                    m
                    for m in per_run[run]["modes"]
                    if floor <= m["frequency_GHz"] <= ceiling
                ),
                key=lambda m: abs(m["participation_abs"].get(1, m["participation_abs"].get("1", 0.0))),
                default=None,
            )
            for run in runs
        },
    }

    defects = [
        (m["energy_balance_defect"], m["disposition"])
        for run in runs
        for m in per_run[run]["modes"]
    ]
    admitted_defects = [d for d, disp in defects if disp == "ADMITTED"]
    rejected_defects = [d for d, disp in defects if disp == "REJECTED_ENERGY_BALANCE"]
    stiffness_proxy = {
        "admitted": [
            (m["energy_J"]["E_mag"] + m["energy_J"]["E_ind"]) * m["frequency_GHz"] ** 2
            for run in runs
            for m in per_run[run]["modes"]
            if m["disposition"] == "ADMITTED"
        ],
        "rejected": [
            (m["energy_J"]["E_mag"] + m["energy_J"]["E_ind"]) * m["frequency_GHz"] ** 2
            for run in runs
            for m in per_run[run]["modes"]
            if m["disposition"] == "REJECTED_ENERGY_BALANCE"
        ],
    }
    clustering_factor = (
        max(stiffness_proxy["rejected"]) / min(stiffness_proxy["rejected"])
        if stiffness_proxy["rejected"]
        else float("nan")
    )
    admitted_factor = (
        max(stiffness_proxy["admitted"]) / min(stiffness_proxy["admitted"])
        if stiffness_proxy["admitted"]
        else float("nan")
    )
    abs_over_bkwd = {}
    for run in runs:
        ratios = [
            m["backward_error"] and (m.get("absolute_error") or 0.0) / m["backward_error"]
            for m in per_run[run]["modes"]
        ]
        ratios = [r for r in ratios if r]
        if ratios:
            abs_over_bkwd[run] = {"min": min(ratios), "max": max(ratios)}

    diagnostics = {
        "energy_definitions_checked_against": {
            "solver": "Palace v0.13.0 (pinned; the record's palace.json reports GitTag v0.13.0)",
            "E_elec": "0.5 * Re(x^H M_eps x) over the whole domain, real permittivity only",
            "E_mag": (
                "0.5 * Re(b^H M_muinv b) with b the true-dof vector of B = -(1/(i*w)) curl E, so it "
                "carries an explicit 1/|w|^2"
            ),
            "E_cap": "sum over lumped ports of 0.5 |C_j| |V_j|^2; identically zero here (no port C)",
            "E_ind": "sum over lumped ports of 0.5 |L_j| |I_j|^2 with I_j = V_j/(i w L_j)",
            "eigenvector_normalisation": (
                "each converged eigenvector is rescaled by 1/sqrt(x^H Re(M) x), with Re(M) the "
                "real-permittivity mass plus any lumped-port capacitance. With no port capacitance "
                "and no loss tangent this fixes E_elec + E_cap to a per-run constant, which is why "
                "E_elec is byte-identical on every row of every run in this record"
            ),
            "units": (
                "the four columns are headed (J) but carry 1e9 times the SI value: Palace's energy "
                "dimensionalisation collapses to the characteristic time, which it stores in "
                "nanoseconds. Verified on this record: E_ind == 1e9 * 0.5 L |I|^2 on all rows. "
                "Every quantity used in this analysis is a ratio of two such columns, so the scale "
                "cancels"
            ),
            "equipartition_is_an_identity": (
                "for an exact eigenpair of K x = w^2 M x, x^H K x = w^2 x^H M x holds by algebra. "
                "Palace's own postprocessing asserts E_elec + E_cap = E_mag + E_ind as a fact"
            ),
        },
        "higher_mode_energy_imbalance": {
            "finding": (
                "Most of the computed rows fail the reported energy identity. The distribution of "
                "|R - 1| is strictly bimodal with nothing between the two populations."
            ),
            "rows_total": len(defects),
            "rows_admitted": len(admitted_defects),
            "rows_rejected_on_energy_balance": len(rejected_defects),
            "max_admitted_defect": max(admitted_defects) if admitted_defects else None,
            "min_rejected_defect": min(rejected_defects) if rejected_defects else None,
            "stiffness_proxy_spread": {
                "quantity": "(E_mag + E_ind) * f^2, proportional to the stiffness energy of the unit-normalised field",
                "rejected_max_over_min": clustering_factor,
                "admitted_max_over_min": admitted_factor,
                "rejected_range": (
                    [min(stiffness_proxy["rejected"]), max(stiffness_proxy["rejected"])]
                    if stiffness_proxy["rejected"]
                    else None
                ),
                "admitted_range": (
                    [min(stiffness_proxy["admitted"]), max(stiffness_proxy["admitted"])]
                    if stiffness_proxy["admitted"]
                    else None
                ),
            },
            "cutoff_insensitivity_interval": (
                [max(admitted_defects), min(rejected_defects)]
                if admitted_defects and rejected_defects
                else None
            ),
            "cause": "SUPPORTED-NOT-PROVEN",
            "the_two_explanations": (
                "Palace's E_ind is not the port stiffness quadratic form but the rank-one surrogate "
                "|V|^2/(2 w^2 L) built from the port's AREA-AVERAGED, +Y-PROJECTED voltage, which by "
                "Cauchy-Schwarz is a LOWER BOUND on the port energy integral (1/Ls)|E_t|^2 dS. A "
                "failing row is therefore either (1) an algebraically spurious Ritz vector whose "
                "reported eigenvalue is meaningless, or (2) a genuine eigenpair of (K, M) whose "
                "stiffness energy sits almost entirely in the lumped port's Robin term, in a "
                "tangential field that is non-uniform or transverse to +Y."
            ),
            "leading_explanation": (
                "(2) is the better supported of the two, and is still not proven."
            ),
            "evidence_for_the_leading_explanation": [
                "Palace builds the auxiliary-boundary marker for its divergence-free projector as "
                "the union of the Dirichlet, farfield, conductivity, impedance and LUMPED-PORT "
                "markers (palace/models/spaceoperator.cpp), and those become the essential true dofs "
                "of the H1 spaces the projector uses. Its potential is pinned to zero on the "
                "inductive port face, so a discrete gradient whose potential varies ON that face "
                "lies outside the projector's range. Palace's own source records the residue in a "
                "commented-out line beside it: 'Mark all boundaries ... As tested, this does not "
                "eliminate all DC modes!'",
                "The lumped inductance enters the STIFFNESS as a Robin surface term "
                "(1/Ls) integral |E_t|^2 dS, so such a gradient has strictly positive stiffness "
                "energy and a finite w^2. The objection that a gradient mode must sit at w = 0 "
                "therefore does not apply.",
                "The failing rows form one family: (E_mag + E_ind) * f^2, proportional to the "
                "measured stiffness energy of the unit-normalised field, spans a factor of only "
                "{clustering_factor:.2f} across all of them, over three discretisations, while the "
                "admitted rows span a factor of {admitted_factor:.0f} and sit orders of magnitude "
                "higher.".format(clustering_factor=clustering_factor, admitted_factor=admitted_factor),
                "A residual bound points the same way without closing it: from |x^H r| <= ||x|| ||r|| "
                "with r = Kx - mu Mx, and R near zero, the failing rows' mass-matrix Rayleigh "
                "quotient is bounded by Err_abs/mu, so these must be strongly localised vectors - "
                "which is what explanation (2) predicts and explanation (1) does not naturally "
                "produce. Whether the bound is outright impossible depends on ||M||, which this "
                "record does not carry, so this supports (2) without excluding (1).",
            ],
            "mode_budget_dilution": (
                "At order 1 three admitted modes were found below 10 GHz; at order 2 on the "
                "byte-identical mesh six converged rows yielded only two, because four failing rows "
                "occupied slots 3-6. The family dilutes the requested mode count, so "
                "eigenmodes_requested should be chosen from the admitted yield."
            ),
            "why_it_does_not_block_the_rule": (
                "The reported participation p = E_ind/(E_elec + E_cap) is computed from the SAME "
                "surrogate, so under either explanation the p of a failing row is not a quantity two "
                "independent solves may be compared on. That is what the admission rule screens."
            ),
            "withdrawn_claim": (
                "An earlier note called these rows 'null-space / gradient artefacts that the "
                "divergence-free projection did not remove'. That asserted a mechanism the evidence "
                "does not carry and is withdrawn."
            ),
            "missing_diagnostics": [
                {
                    "diagnostic": "per-mode port stiffness integral (1/Ls)|E_t|^2 dS / (2 w^2)",
                    "would_show": "whether the reported E_ind understates the true port energy",
                    "why_absent": "Palace v0.13.0 never writes it",
                },
                {
                    "diagnostic": "the saved mode fields",
                    "would_show": "E_t on the port and div(eps E) in the volume, directly",
                    "why_absent": "all three configs set Solver.Eigenmode.Save = 0",
                },
                {
                    "diagnostic": "per-mode ||x||_2, x^H K x, or an M-norm-relative residual",
                    "would_show": "the Rayleigh quotient independent of the surrogate",
                    "why_absent": "Palace v0.13.0 emits none of them",
                },
            ],
        },
        "backward_error_normalisation": {
            "finding": (
                "Palace normalises the reported backward error by the GLOBAL operator norms. The "
                "record shows it directly: within each run Error(Abs.)/Error(Bkwd.) is constant to "
                "about five parts in a million, so the printed backward error is the true residual "
                "divided by a number of order 1e5."
            ),
            "abs_over_bkwd_ratio_per_run": abs_over_bkwd,
            "consequence": (
                "a small printed backward error is a weaker certificate than its size suggests, and "
                "certifies the eigenpair rather than its physics"
            ),
        },
        "participation_sign": {
            "finding": (
                "The sign of p is sign(Re I), and Palace computes I = V/(i w L) exactly, so "
                "arg(I) = arg(V) - 90 degrees identically and V/I is the constant i w L. The sign "
                "therefore tracks the eigenvector's arbitrary overall complex phase."
            ),
            "phase_fixing_in_solver": (
                "The pinned Palace tree contains no phase-fixing step: its only post-solve "
                "normalisation is multiplication by a real, non-negative scalar"
            ),
            "conclusion": "The sign is a solver gauge choice, not a physical current direction",
            "withdrawn_claim": (
                "An earlier note said the port current direction is not stable under "
                "discretisation. That described a gauge artefact as physics and is withdrawn."
            ),
            "missing_diagnostic": (
                "A gauge-invariant SIGNED observable would need a second inductive lumped port in "
                "the same solve, so that arg(I_1) - arg(I_2) could be compared between runs, or the "
                "saved mode fields. Neither exists in this record."
            ),
            "action_taken": "comparisons use |p|; signed p and complex I are preserved verbatim",
        },
        "reproducibility_claim_qualified": {
            "claim": (
                "that pilot attempt 1 (workflow run 35048375845) and the committed re-run agree "
                "bit-for-bit"
            ),
            "status": "QUALIFIED - not supported at that strength",
            "what_is_supported": (
                "The eigenfrequencies and backward errors printed in attempt 1's job log agree with "
                "the committed record to every digit the log prints, for all 6, 9 and 8 modes of "
                "P1, P2 and P3. That is agreement to the precision of the log."
            ),
            "what_is_not_supported": (
                "A raw-file or hash comparison. Attempt 1's postpro files were never committed - "
                "its commit-back step failed - and its uploaded artifact was not retrievable here."
            ),
            "missing_diagnostic": "attempt 1's postpro/ files, or their sha256 digests",
        },
    }

    return {
        "schema": RECORD_SCHEMA,
        "record_version": RECORD_VERSION,
        "batch_id": batch_id,
        "kind": "corrective-analysis",
        "statement": STATEMENT,
        "source_record": digests,
        "frozen_criteria": frozen,
        "rules_introduced_here": {
            "admission": dict(ADMISSION_RULE),
            "matching": dict(MATCHING_RULE),
            "comparison_convention": dict(COMPARISON_CONVENTION),
            "row_correspondence_tolerance": dict(ROW_CORRESPONDENCE_TOLERANCE),
            "status": (
                "RETROSPECTIVE for this record: the solves were executed before these rules "
                "existed and are re-read, never re-run, under them. PROSPECTIVE for the next "
                "confirmatory run, where they are declared in advance and may not then be changed."
            ),
        },
        "solver_rules_unchanged": dict(COUPLED_SOLVER_RULES),
        "port_inductance_H": {str(k): v for k, v in inductance.items()},
        "runs": per_run,
        "comparisons": comparisons,
        "halo_disposition": halo,
        "diagnostic_findings": diagnostics,
        "superseded_analysis": superseded,
        "environment": {
            "python_version": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "solver_launched": False,
        },
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }


# --- rendering --------------------------------------------------------------


def _fmt(value: float | None, spec: str = ".4e") -> str:
    return "n/a" if value is None else format(value, spec)


def render_report(record: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# Corrective analysis of the coupled-pilot record")
    add("")
    add(f"Record `{record['batch_id']}` (schema `{record['schema']}`, version {record['record_version']}).")
    add(
        f"Source: `{record['source_record']['record']}`, "
        f"{record['source_record']['file_count']} files, manifest "
        f"`{record['source_record']['manifest_sha256'][:16]}…`, verified intact before and after."
    )
    add("")
    add(record["statement"])
    add("")

    add("## 1. Execution completion")
    add("")
    add("| run | order | halo (mm) | DOF | wall clock (s) | status as executed |")
    add("|---|---|---|---|---|---|")
    for run in sorted(record["runs"]):
        entry = record["runs"][run]
        spec = entry["spec"]
        add(
            f"| {run} | {spec['finite_element_order']} | {spec['halo_mm']} | {entry['dof_measured']} "
            f"| {entry['wall_clock_s']:.1f} | {entry['status_as_executed']} |"
        )
    add("")
    add("Unchanged by this analysis. Completion is a statement about the job, not about the physics.")
    add("")

    add("## 2. Algebraic convergence")
    add("")
    add(
        f"Backward error against the solver's existing tolerance "
        f"{record['solver_rules_unchanged']['eigenmode_backward_error_max_tolerance']:.0e}, unchanged here."
    )
    add("")
    add("| run | modes computed | worst backward error | all converged |")
    add("|---|---|---|---|")
    for run in sorted(record["runs"]):
        entry = record["runs"][run]
        worst = max(m["backward_error"] for m in entry["modes"])
        every = all(m["algebraically_converged"] for m in entry["modes"])
        add(f"| {run} | {entry['modes_computed']} | {_fmt(worst)} | {'yes' if every else 'no'} |")
    add("")
    add(
        "A small backward error certifies that the eigenpair solves the discrete problem. "
        "It says nothing about whether that eigenpair is a resonance."
    )
    add("")

    add("## 3. Row correspondence")
    add("")
    add(
        "The five per-mode tables are joined on the `m` column, never by row position, and two "
        "independent identities that span them are checked:"
    )
    add("")
    add("- `|p_j| == E_ind / (E_elec + E_cap)`  — `port-EPR.csv` against `domain-E.csv`")
    add("- `|V_j| == 2*pi*f * L_j * |I_j|`      — `port-V.csv` against `port-I.csv` and `eig.csv`")
    add("")
    add("| run | modes checked | worst participation/energy mismatch | worst port impedance mismatch | ok |")
    add("|---|---|---|---|---|")
    for run in sorted(record["runs"]):
        rc = record["runs"][run]["row_correspondence"]
        add(
            f"| {run} | {rc['modes_checked']} | {_fmt(rc['max_participation_energy_mismatch'])} "
            f"| {_fmt(rc['max_port_impedance_mismatch'])} | {'yes' if rc['ok'] else 'NO'} |"
        )
    add("")

    add("## 4. Mode validity")
    add("")
    add(f"Admission rule `{record['rules_introduced_here']['admission']['id']}`: "
        f"{record['rules_introduced_here']['admission']['admit_when']}, with "
        f"`R = (E_mag + E_ind) / (E_elec + E_cap)`.")
    add("")
    add(
        "Status: **retrospective** for this record, **prospective** for the next confirmatory run. "
        "It is a numerical-analysis rule about which rows are resonances. It is not a physical "
        "QMHP threshold and it gates no coupling."
    )
    add("")
    for run in sorted(record["runs"]):
        entry = record["runs"][run]
        add(f"### {run}")
        add("")
        add("| m | f (GHz) | backward error | R | \\|R−1\\| | signed p | \\|p\\| | E_ind/(E_mag+E_ind) | disposition |")
        add("|---|---|---|---|---|---|---|---|---|")
        for mode in entry["modes"]:
            p_signed = mode["participation_signed"].get("1", mode["participation_signed"].get(1, 0.0))
            p_abs = mode["participation_abs"].get("1", mode["participation_abs"].get(1, 0.0))
            add(
                f"| {mode['mode']} | {mode['frequency_GHz']:.6f} | {_fmt(mode['backward_error'], '.2e')} "
                f"| {_fmt(mode['energy_balance_ratio'], '.6e')} | {_fmt(mode['energy_balance_defect'], '.3e')} "
                f"| {p_signed:+.6e} | {p_abs:.6e} | {_fmt(mode['lumped_magnetic_fraction'], '.3e')} "
                f"| {mode['disposition']} |"
            )
        add("")
        separation = entry.get("separation_decades")
        add(
            f"Admitted: {entry['admitted_in_window']} in the declared window "
            f"{entry['declared_window_GHz']} GHz"
            + (f", {entry['admitted_outside_window']} outside it" if entry["admitted_outside_window"] else "")
            + (f". The admitted and rejected populations are separated by {separation:.2f} decades in |R−1|."
               if separation is not None else ".")
        )
        add("")

    add("## 5. Mode matching")
    add("")
    for label in sorted(record["comparisons"]):
        comparison = record["comparisons"][label]
        match = comparison["match"]
        add(f"### {match['comparison']} — {match['status']}")
        add("")
        add(f"{match['reason']}")
        add("")
        if match["pairs"]:
            add("| pair | f_a (GHz) | f_b (GHz) | Δf | Δ\\|p\\| | shift (GHz) | separation limit (GHz) |")
            add("|---|---|---|---|---|---|---|")
            for pair in match["pairs"]:
                dp = pair["delta_abs_participation_relative"]
                dp1 = dp.get("1", dp.get(1, 0.0))
                add(
                    f"| m{pair['a']['mode']}↔m{pair['b']['mode']} | {pair['a']['frequency_GHz']:.6f} "
                    f"| {pair['b']['frequency_GHz']:.6f} | {_fmt(pair['delta_f_relative'])} "
                    f"| {_fmt(dp1)} | {pair['frequency_shift_GHz']:.4f} | {pair['separation_limit_GHz']:.4f} |"
                )
            add("")
        evaluation = comparison["frozen_criteria_evaluation"]
        if evaluation.get("evaluated"):
            criteria = evaluation["criteria"]
            add(
                f"Against the unchanged frozen criteria "
                f"(Δ\\|p\\| ≤ {criteria['max_relative_participation_change']:.0e}, "
                f"Δf ≤ {criteria['max_relative_frequency_change']:.0e}):"
            )
            add("")
            add("| pair | Δf | frequency | Δ\\|p\\| | participation | criterion subject |")
            add("|---|---|---|---|---|---|")
            for row in evaluation["pairs"]:
                add(
                    f"| m{row['a_mode']}↔m{row['b_mode']} | {_fmt(row['delta_f_relative'])} "
                    f"| {row['frequency_check']} | {_fmt(row['delta_abs_p_relative'])} "
                    f"| {row['participation_check']} | {'yes' if row['is_criterion_subject'] else ''} |"
                )
            add("")
    add(
        "Δ\\|p\\| uses **magnitudes**: `abs(|p_a| − |p_b|) / max(|p_a|, |p_b|)`. The signed "
        "participation and the complex port current are preserved unchanged in the machine-readable "
        "record; only the comparison uses magnitudes, because Palace's sign is `sign(Re I)` and the "
        "phase of a single port phasor is not invariant under the eigenvector's arbitrary global scale."
    )
    add("")

    add("## 6. Diagnostic findings")
    add("")
    diagnostics = record["diagnostic_findings"]
    imbalance = diagnostics["higher_mode_energy_imbalance"]
    add(
        f"{imbalance['rows_rejected_on_energy_balance']} of {imbalance['rows_total']} computed rows "
        f"fail the reported energy identity. The distribution is bimodal: the worst admitted defect "
        f"is {_fmt(imbalance['max_admitted_defect'], '.3e')} and the best rejected one is "
        f"{_fmt(imbalance['min_rejected_defect'], '.3e')}, so the admitted set is unchanged for any "
        f"cutoff between them."
    )
    add("")
    add(f"**Cause: {imbalance['cause']}.** {imbalance['the_two_explanations']}")
    add("")
    add(f"{imbalance['leading_explanation']} The evidence:")
    add("")
    for item in imbalance["evidence_for_the_leading_explanation"]:
        add(f"- {item}")
    add("")
    add(imbalance["why_it_does_not_block_the_rule"])
    add("")
    add(f"Mode budget: {imbalance['mode_budget_dilution']}")
    add("")
    add(f"Withdrawn: {imbalance['withdrawn_claim']}")
    add("")
    bkwd = diagnostics["backward_error_normalisation"]
    add(f"**Backward error.** {bkwd['finding']} Measured per run: "
        + ", ".join(
            f"{run} {v['min']:.4e}–{v['max']:.4e}" for run, v in sorted(bkwd["abs_over_bkwd_ratio_per_run"].items())
        )
        + f". Consequence: {bkwd['consequence']}.")
    add("")
    add("| missing diagnostic | what it would show | why it is absent |")
    add("|---|---|---|")
    for item in imbalance["missing_diagnostics"]:
        add(f"| {item['diagnostic']} | {item['would_show']} | {item['why_absent']} |")
    add("")
    sign = diagnostics["participation_sign"]
    add(f"**Participation sign.** {sign['finding']} {sign['phase_fixing_in_solver']}. "
        f"Conclusion: {sign['conclusion']}.")
    add("")
    add(f"Withdrawn: {sign['withdrawn_claim']}")
    add("")
    add(f"Missing diagnostic: {sign['missing_diagnostic']}")
    add("")
    repro = diagnostics["reproducibility_claim_qualified"]
    add(f"**Reproducibility claim — {repro['status']}.** Supported: {repro['what_is_supported']} "
        f"Not supported: {repro['what_is_not_supported']} Missing: {repro['missing_diagnostic']}.")
    add("")

    add("## 7. Halo disposition")
    add("")
    halo = record["halo_disposition"]
    add(f"**{halo['verdict']}**")
    add("")
    add(halo.get("reason", ""))
    add("")

    add("## 8. What this corrects")
    add("")
    superseded = record["superseded_analysis"]
    original = superseded["source_record_halo_verdict"]
    if original:
        add(
            f"The source record reports Δp = {_fmt(original.get('delta_p_relative'))}, "
            f"Δf = {_fmt(original.get('delta_f_relative'))} and the verdict "
            f"`{original.get('verdict')}`. Two things produced those numbers:"
        )
        add("")
        for reason in superseded["why_the_source_numbers_were_wrong"]:
            add(f"- {reason}")
        add("")
        selected = superseded.get("rows_the_source_rule_selected", {})
        if any(selected.values()):
            add("The rows that rule selected, with their dispositions under the corrected rule:")
            add("")
            add("| run | mode | f (GHz) | \|p\| | disposition |")
            add("|---|---|---|---|---|")
            for run in sorted(selected):
                row = selected[run]
                if not row:
                    continue
                p_abs = row["participation_abs"].get("1", row["participation_abs"].get(1, 0.0))
                add(
                    f"| {run} | {row['mode']} | {row['frequency_GHz']:.6f} | {_fmt(p_abs)} "
                    f"| {row['disposition']} |"
                )
            add("")
    add(superseded["note"])
    add("")
    return "\n".join(lines) + "\n"


# --- entry point ------------------------------------------------------------


def write_record(record: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "corrective_analysis.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    (out_dir / "report.md").write_text(render_report(record))
    manifest.write(out_dir)
    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default="results/COUPLED-PILOT-20260916T035733Z",
        help="the preserved pilot record to re-read (never modified)",
    )
    parser.add_argument("--results-root", default="results")
    parser.add_argument("--batch-id", default=None, help="override the generated record id")
    parser.add_argument(
        "--check",
        action="store_true",
        help="run the analysis and print the report without writing a record",
    )
    args = parser.parse_args(argv)

    source = (REPO_ROOT / args.source).resolve() if not Path(args.source).is_absolute() else Path(args.source)
    if not source.is_dir():
        raise SystemExit(f"no such record: {source}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_id = args.batch_id or f"{RECORD_PREFIX}-{stamp}"
    record = build(source, batch_id=batch_id)

    if args.check:
        print(render_report(record))
        return 0

    root = (REPO_ROOT / args.results_root) if not Path(args.results_root).is_absolute() else Path(args.results_root)
    out_dir = write_record(record, root / batch_id)

    after = manifest.verify(source)
    if after:
        raise SystemExit(
            f"the source record changed while the corrective analysis ran: {after}. "
            f"This must never happen; the new record at {out_dir} is not trustworthy."
        )
    print(f"{out_dir}: written; source record {source.name} re-verified intact")
    print(f"halo disposition: {record['halo_disposition']['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
