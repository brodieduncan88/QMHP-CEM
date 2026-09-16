#!/usr/bin/env python3
"""The approved order-1 mesh-refinement check, one level per invocation.

The coupled pilot established that at mesh level 1 the discretisation error
dwarfs both knobs it tested: a 32 % frequency shift from p-refinement on a
byte-identical mesh, and 4.5 % from a size-field halo change. Nothing in that
record establishes that the discretisation converges at all, and that is the
only fact deciding whether the extraction is executable.

This runs the cheap probe. Order 1 measured 32.4 s at 39 832 DOF against
order 2's 2009.7 s on the same mesh, so a refinement sequence that is
unaffordable at order 2 is affordable at order 1; and because both orders
discretise the same continuous problem, the mesh order 2 needs for a given
accuracy is no worse than the mesh order 1 needs.

**Sequential by construction.** One level per invocation, so each rung is
reviewed before the next is launched. Nothing here launches a ladder.

Held fixed and unchanged: the element order (1), the size-field halo
(0.08 mm), the 250 000-DOF ENGINEERING-RULE, the 45-minute per-solve cap, the
declared 0.5-9.0 GHz window, the backward-error tolerance, and the prospective
admission, matching and magnitude-comparison rules of
``solvers/palace/mode_admission.py``. This script imports those rules; it does
not restate or relax them.

**No coupling extraction.** No Route A inversion, no ``g``, no charging energy,
no capacitance, no circuit parameter derived from a frequency. The one new
quantity is a dimensionless consistency ratio described in
:func:`port_field_analysis`, and it produces no circuit parameter either.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import manifest  # noqa: E402
from solvers.palace import outputs as pout  # noqa: E402
from solvers.palace.coupled_config import (  # noqa: E402
    COUPLED_SOLVER_RULES,
    PORT_FIELD_PROBES,
    build_coupled_config,
    superinductor_henry,
)
from solvers.palace.coupled_geometry import chip_cell_from_declaration  # noqa: E402
from solvers.palace.coupled_mesh import dry_run  # noqa: E402
from solvers.palace.mode_admission import (  # noqa: E402
    ADMISSION_RULE,
    COMPARISON_CONVENTION,
    MATCHING_RULE,
    admit_modes,
    check_row_correspondence,
    join_modes_by_id,
    label_roles,
    match_runs,
)

SUMMARY_SCHEMA = "qmhp-cem.coupled-order1-ladder/0.1.0"
RECORD_PREFIX = "COUPLED-LADDER-O1"
DEFAULT_IMAGE = "qmhp-cem/palace:0.13.0"
CONTAINER_WORKDIR = "/work"
CONFIG_FILENAME = "config.json"

#: Fixed for every rung. Not arguments, so a rung cannot drift from the check.
FINITE_ELEMENT_ORDER = 1
HALO_MM = 0.08

#: Unchanged from the pilot. This script may not raise either.
SOLVE_TIMEOUT_S = 45 * 60
DOF_BUDGET = 250_000

#: The reference rung, already executed and preserved. Level 2 and level 3 are
#: compared against it; it is never re-run.
REFERENCE_RECORD = "COUPLED-PILOT-20260916T035733Z"
REFERENCE_RUN = "P2"
REFERENCE_LEVEL = 1

STATEMENT = (
    "Order-1 mesh-refinement check, one level per invocation, at fixed element order 1 and "
    "fixed 0.08 mm halo. Measures whether the discretisation converges, and tests the "
    "supported-but-unproven port-stiffness explanation of the energy-balance failures using "
    "Palace's own boundary quadrature. NO coupling extraction: no Route A inversion, no g, no "
    "charging energy, no capacitance, no circuit parameter. The 250 000-DOF rule, the 45-minute "
    "cap and the prospective admission, matching and magnitude rules are unchanged."
)


class LadderError(RuntimeError):
    """The rung cannot be run as specified."""


# --- the solve ----------------------------------------------------------------


def _user_flag(runtime: str) -> list[str]:
    """Run the container as this user, so its output is ours to commit."""
    if runtime == "docker" and hasattr(os, "getuid"):
        return ["--user", f"{os.getuid()}:{os.getgid()}"]
    return []


def _run_palace(runtime: str, image: str, solver_dir: Path, np_processes: int, name: str) -> dict[str, Any]:
    command = [
        runtime, "run", "--rm", "--network", "none", "--hostname", "localhost",
        "--name", name, *_user_flag(runtime),
        "-e", "HOME=/tmp", "-e", "OMP_NUM_THREADS=1", "-e", "OPENBLAS_NUM_THREADS=1",
        "-v", f"{solver_dir}:{CONTAINER_WORKDIR}", "-w", CONTAINER_WORKDIR,
        image, "-np", str(np_processes), CONFIG_FILENAME,
    ]
    started = datetime.now(timezone.utc)
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    t0 = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=SOLVE_TIMEOUT_S)
        returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = None
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        subprocess.run([runtime, "kill", name], capture_output=True, text=True, timeout=60, check=False)
    wall = time.perf_counter() - t0
    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    (solver_dir / "palace_log.txt").write_text(stdout + ("\n" + stderr if stderr else ""))
    return {
        "command": command,
        "returncode": returncode,
        "timed_out": timed_out,
        "timeout_s": SOLVE_TIMEOUT_S,
        "started_utc": started.isoformat(),
        "wall_clock_s": wall,
        "cap_fraction_used": wall / SOLVE_TIMEOUT_S,
        "runner_cli_peak_rss_kb": after,
        "runner_cli_peak_rss_kb_delta": max(0, after - before),
        "memory_note": (
            "ru_maxrss measures the container runtime CLI in this process tree, not the solver "
            "inside the container. Solver-side timing is quoted from Palace's own log."
        ),
    }


def palace_timers(metadata: dict[str, Any]) -> dict[str, Any]:
    """Palace's own elapsed-time report, as it writes it.

    Reported verbatim. In particular ``Preconditioner`` is the time spent
    *applying* the preconditioner inside the linear solves; ``Setup`` is a
    separate, much smaller line, and Palace names no preconditioner type.
    """
    elapsed = (metadata.get("ElapsedTime") or {}).get("Durations") or {}
    counts = (metadata.get("ElapsedTime") or {}).get("Counts") or {}
    keys = (
        "Total", "Setup", "Preconditioner", "CoarseSolve", "LinearSolve",
        "EigenvalueSolve", "Div.-FreeProjection", "Estimation", "Solve",
        "OperatorConstruction", "Postprocessing",
    )
    return {
        "durations_s": {k: elapsed[k] for k in keys if k in elapsed},
        "counts": {k: counts[k] for k in keys if k in counts},
        "note": (
            "Palace's own timer names. 'Preconditioner' is preconditioner APPLICATION inside "
            "the linear solves, not setup; 'Setup' is the separate setup line. The log names "
            "no preconditioner type, so none is asserted."
        ),
    }


# --- the port-field test ------------------------------------------------------


def port_field_analysis(
    modes: list[Any],
    surface_rows: list[pout.SurfaceParticipationRow],
    *,
    admitted_modes: set[int],
) -> dict[str, Any]:
    """Test the port-stiffness explanation using Palace's own boundary quadrature.

    Palace's ``E_ind`` is the rank-one surrogate ``|V|^2/(2 w^2 L_s)`` built
    from the port's width-averaged line voltage, whereas the stiffness carries
    ``integral (1/L_s)|E_t|^2 dS``. Two interface-dielectric probes on the port
    face, with unit thickness and unit permittivity, give (per mode, already
    divided by ``E_elec + E_cap``):

        s_default = 0.5 * integral |E|^2 dS / E_elec      (Type "Default")
        s_normal  = 0.5 * integral |E_n|^2 dS / E_elec    (Type "MA")
        s_t       = s_default - s_normal = 0.5 * integral |E_t|^2 dS / E_elec

    The true port participation is ``kappa * s_t / f^2`` for a single constant
    ``kappa`` that absorbs ``L_s`` and Palace's nondimensionalisation. That
    constant is not assumed: it is **calibrated from the admitted modes**, for
    which the Rayleigh identity forces the true port energy to equal the
    reported ``E_ind``. If the surrogate is faithful on those modes, every
    admitted mode gives the same ``kappa``; the spread across them is reported
    and is what makes the calibration checkable rather than fitted.

    The test on a failing row is then the **restored balance**

        R_true = E_mag/E_elec + kappa * s_t / f^2

    Explanation 2 (a genuine eigenpair whose stiffness the average understates)
    predicts ``R_true = 1``. Explanation 1 (an algebraically spurious Ritz
    vector) predicts ``R_true`` stays near the reported ``R``, i.e. near 0.
    The test can return either, which is the point of running it.

    A built-in sanity check: ``E_ind / E_port_true`` is a Cauchy-Schwarz ratio
    and must not exceed 1 for any mode. A value above 1 would falsify the
    framing rather than either explanation.
    """
    by_mode = {int(r.mode): r for r in surface_rows}
    default_idx = PORT_FIELD_PROBES["default_index"]
    normal_idx = PORT_FIELD_PROBES["normal_index"]

    rows: dict[int, dict[str, Any]] = {}
    for record in modes:
        entry = by_mode.get(record.mode)
        if entry is None:
            continue
        s_default = entry.participation.get(default_idx)
        s_normal = entry.participation.get(normal_idx)
        if s_default is None or s_normal is None:
            continue
        s_t = s_default - s_normal
        rows[record.mode] = {
            "mode": record.mode,
            "frequency_GHz": record.frequency_GHz,
            "s_default": s_default,
            "s_normal": s_normal,
            "s_tangential": s_t,
            "normal_fraction": (s_normal / s_default) if s_default else math.nan,
            "reported_participation": record.abs_participation(),
            "E_mag_over_E_elec": (
                record.magnetic_J / record.electric_side_J if record.electric_side_J else math.nan
            ),
            "reported_balance": record.energy_balance_ratio,
            "admitted": record.mode in admitted_modes,
        }

    calibration = {}
    for mode, row in rows.items():
        if not row["admitted"] or row["s_tangential"] <= 0:
            continue
        calibration[mode] = (
            row["reported_participation"] * row["frequency_GHz"] ** 2 / row["s_tangential"]
        )
    if not calibration:
        return {
            "available": False,
            "reason": "no admitted mode has a positive tangential probe, so kappa cannot be calibrated",
            "rows": list(rows.values()),
        }

    values = list(calibration.values())
    kappa = sum(values) / len(values)
    spread = (max(values) / min(values)) if min(values) > 0 else math.inf

    for row in rows.values():
        predicted = kappa * row["s_tangential"] / (row["frequency_GHz"] ** 2)
        row["port_participation_from_fields"] = predicted
        row["restored_balance"] = row["E_mag_over_E_elec"] + predicted
        row["cauchy_schwarz_ratio"] = (
            row["reported_participation"] / predicted if predicted > 0 else math.nan
        )

    failing = [r for r in rows.values() if not r["admitted"]]
    verdict, reason = _port_field_verdict(spread, failing)
    return {
        "available": True,
        "method": port_field_analysis.__doc__.strip().splitlines()[0],
        "probes": dict(PORT_FIELD_PROBES),
        "kappa": kappa,
        "kappa_per_admitted_mode": calibration,
        "kappa_spread_max_over_min": spread,
        "rows": [rows[m] for m in sorted(rows)],
        "verdict": verdict,
        "reason": reason,
    }


def _port_field_verdict(spread: float, failing: list[dict[str, Any]]) -> tuple[str, str]:
    if spread > 2.0:
        return (
            "CALIBRATION-UNSOUND",
            f"the admitted modes disagree about kappa by a factor of {spread:.3g}; the surrogate "
            f"is not faithful even on them, so nothing can be concluded about the failing rows",
        )
    if not failing:
        return ("NO-FAILING-ROWS", "every computed mode was admitted, so there is nothing to test")
    restored = [r["restored_balance"] for r in failing]
    worst_cs = max((r["cauchy_schwarz_ratio"] for r in failing), default=math.nan)
    if worst_cs > 1.5:
        return (
            "FRAMING-FALSIFIED",
            f"a failing row has E_ind above its own true port energy (ratio {worst_cs:.3g}), which "
            f"Cauchy-Schwarz forbids; the port-stiffness framing is wrong, not either explanation",
        )
    if all(abs(value - 1.0) <= 1.0e-2 for value in restored):
        return (
            "EXPLANATION-2-SUPPORTED",
            f"the restored balance is 1 to within 1e-2 on every failing row (range "
            f"{min(restored):.6g} to {max(restored):.6g}): the tangential port field accounts for "
            f"the missing stiffness, as a genuine eigenpair whose average understates it predicts",
        )
    if all(value < 0.5 for value in restored):
        return (
            "EXPLANATION-2-REFUTED",
            f"the tangential port field does not account for the missing stiffness (restored "
            f"balance {min(restored):.6g} to {max(restored):.6g}); the failing rows are not "
            f"eigenpairs whose port energy the average understates",
        )
    return (
        "INCONCLUSIVE",
        f"the restored balance is neither near 1 nor near the reported value (range "
        f"{min(restored):.6g} to {max(restored):.6g})",
    )


# --- the rung -----------------------------------------------------------------


def reference_modes(root: Path | None = None) -> tuple[list[Any], dict[str, Any]]:
    """The preserved level-1 order-1 rung, read-only.

    Always located in the repository's ``results/`` tree: it is a fixed piece
    of evidence, not an output of this run, so it does not follow
    ``--results-root``.
    """
    record = (root or (REPO_ROOT / "results")) / REFERENCE_RECORD
    discrepancies = manifest.verify(record)
    if discrepancies:
        raise LadderError(f"{record} does not match its manifest: {discrepancies}")
    modes = join_modes_by_id(record / REFERENCE_RUN / "solver" / "postpro")
    summary = json.loads((record / "summary.json").read_text())
    return modes, summary["runs"][REFERENCE_RUN]


def execute_level(
    level: int,
    declaration: dict[str, Any],
    solver_dir: Path,
    *,
    runtime: str,
    image: str,
    np_processes: int,
    prepare_only: bool,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "level": level,
        "finite_element_order": FINITE_ELEMENT_ORDER,
        "halo_mm": HALO_MM,
        "status": "NOT-RUN",
    }
    try:
        cell = chip_cell_from_declaration(declaration)
        report = dry_run(cell, level, solver_dir, dof_budget=DOF_BUDGET, halo_mm=HALO_MM)
        mesh = report.as_dict()
        entry["mesh"] = mesh
        dof = mesh["measured"][f"dof_order{FINITE_ELEMENT_ORDER}"]
        entry["dof_measured"] = dof
        entry["within_dof_budget"] = dof <= DOF_BUDGET
        if not entry["within_dof_budget"]:
            entry["status"] = "REFUSED-DOF-BUDGET"
            entry["failure"] = (
                f"level {level} at order {FINITE_ELEMENT_ORDER} measures {dof} DOF, above the "
                f"declared {DOF_BUDGET}. The rule is not relaxed and the solve is not launched."
            )
            return entry

        substrate = next(m for m in declaration["materials"] if m["id"] == "substrate")
        E_L = next(p for p in declaration["parameter_register"] if p["id"] == "E_L_F1")["value"]
        inductance = superinductor_henry(float(E_L))
        port = next(p for p in declaration["ports"] if p["id"] == "P_F1")
        direction = port["direction"] if isinstance(port["direction"], str) else port["direction"][0]
        n_modes = COUPLED_SOLVER_RULES["eigenmodes_requested"]
        config = build_coupled_config(
            Path(mesh["mesh_file"]).name,
            order=FINITE_ELEMENT_ORDER,
            substrate_permittivity=float(substrate["permittivity"]),
            port_inductance_H=inductance,
            port_direction=direction,
            save_modes=n_modes,
            port_field_probes=True,
        )
        (solver_dir / CONFIG_FILENAME).write_text(json.dumps(config, indent=2) + "\n")
        entry["port_inductance_H"] = inductance
        entry["port_size_mm"] = port["size_mm"]
        entry["solver_rules"] = dict(COUPLED_SOLVER_RULES)
        entry["field_output_modes"] = n_modes

        if prepare_only:
            entry["status"] = "PREPARED"
            return entry

        run_info = _run_palace(runtime, image, solver_dir, np_processes, f"qmhp-ladder-o1-l{level}")
        entry["run"] = run_info
        if run_info["timed_out"]:
            entry["status"] = "TIMEOUT"
            entry["failure"] = f"the solve did not finish inside the {SOLVE_TIMEOUT_S} s cap"
            return entry
        if run_info["returncode"] != 0:
            entry["status"] = "RUN_FAILED"
            entry["failure"] = f"palace exited {run_info['returncode']}"
            return entry

        post = solver_dir / "postpro"
        joined = join_modes_by_id(post)
        correspondence = check_row_correspondence(joined, {1: inductance})
        admission = admit_modes(
            f"L{level}",
            joined,
            backward_error_tolerance=COUPLED_SOLVER_RULES["eigenmode_backward_error_max_tolerance"],
            row_correspondence=correspondence,
        )
        entry["row_correspondence"] = correspondence.as_dict()
        entry["admission"] = admission.as_dict()
        entry["roles"] = [r.as_dict() for r in label_roles(admission.admitted)]
        entry["palace_metadata"] = pout.read_metadata_json(post / "palace.json")
        entry["palace_timers"] = palace_timers(entry["palace_metadata"])
        entry["max_backward_error"] = max(m.record.backward_error for m in admission.modes)

        try:
            surface_rows = pout.parse_surface_q_csv(post / "surface-Q.csv")
            entry["port_field_test"] = port_field_analysis(
                joined, surface_rows, admitted_modes={r.mode for r in admission.admitted}
            )
        except pout.PalaceOutputError as exc:
            entry["port_field_test"] = {"available": False, "reason": str(exc)}

        # Palace writes paraview/ UNDER Problem.Output, not beside it. The
        # level-2 rung looked beside it, reported "written: false" for output
        # that had in fact been written, and so committed 123 MB it had said
        # it would not. Derived from the config rather than hard-coded, so the
        # two cannot drift apart again.
        paraview = solver_dir / str(config["Problem"]["Output"]) / "paraview"
        written = paraview.is_dir()
        entry["field_output"] = {
            "written": written,
            "path": str(paraview.relative_to(solver_dir)) if written else None,
            "bytes": sum(f.stat().st_size for f in paraview.rglob("*") if f.is_file()) if written else 0,
            "note": (
                "ParaView field output is uploaded as a workflow artifact and is NOT committed: "
                "it runs to ~120 MB per rung and the quantitative test uses surface-Q.csv, which "
                "is committed and manifested."
            ),
        }
        entry["status"] = "COMPLETED"
    except Exception as exc:  # noqa: BLE001 - a failure is evidence
        if entry.get("status") in {"TIMEOUT", "RUN_FAILED", "REFUSED-DOF-BUDGET"}:
            pass
        else:
            entry["status"] = "ERROR"
        entry.setdefault("failure", f"{type(exc).__name__}: {exc}")
    return entry


def compare_against_reference(entry: dict[str, Any], reference: list[Any], reference_meta: dict[str, Any]) -> dict[str, Any]:
    """Match this rung's admitted modes against the preserved level-1 rung.

    Uses the prospective matching rule and the magnitude convention unchanged.
    """
    out: dict[str, Any] = {
        "reference": f"{REFERENCE_RECORD}/{REFERENCE_RUN} (level {REFERENCE_LEVEL}, order 1)",
        "matching_rule": dict(MATCHING_RULE),
        "convention": dict(COMPARISON_CONVENTION),
        "available": False,
    }
    if entry.get("status") != "COMPLETED":
        out["reason"] = f"this rung is {entry.get('status')}"
        return out

    floor = COUPLED_SOLVER_RULES["band_floor_GHz"]
    ceiling = COUPLED_SOLVER_RULES["band_ceiling_GHz"]
    from solvers.palace.mode_admission import ModeRecord  # noqa: PLC0415

    def rebuild(modes: list[dict[str, Any]]) -> list[ModeRecord]:
        built = []
        for m in modes:
            if m.get("disposition") != "ADMITTED":
                continue
            built.append(
                ModeRecord(
                    mode=m["mode"],
                    frequency_GHz=m["frequency_GHz"],
                    frequency_im_GHz=m["frequency_im_GHz"],
                    backward_error=m["backward_error"],
                    absolute_error=m.get("absolute_error"),
                    electric_J=m["energy_J"]["E_elec"],
                    magnetic_J=m["energy_J"]["E_mag"],
                    capacitive_J=m["energy_J"]["E_cap"],
                    inductive_J=m["energy_J"]["E_ind"],
                    participation={int(k): v for k, v in m["participation_signed"].items()},
                    current_A={int(k): complex(v["re"], v["im"]) for k, v in m["current_A"].items()},
                    voltage_V={int(k): complex(v["re"], v["im"]) for k, v in m["voltage_V"].items()},
                )
            )
        return [r for r in built if r.in_window(floor, ceiling)]

    this_level = rebuild(entry["admission"]["modes"])
    reference_admitted = admit_modes(
        REFERENCE_RUN,
        reference,
        backward_error_tolerance=COUPLED_SOLVER_RULES["eigenmode_backward_error_max_tolerance"],
    )
    reference_window = reference_admitted.admitted_in_window(floor, ceiling)

    match = match_runs(f"L{REFERENCE_LEVEL} vs L{entry['level']}", reference_window, this_level)
    out["match"] = match.as_dict()
    out["reference_admitted_in_window"] = [r.mode for r in reference_window]
    out["this_admitted_in_window"] = [r.mode for r in this_level]
    out["reference_admitted_all"] = [r.mode for r in reference_admitted.admitted]
    out["reference_wall_clock_s"] = reference_meta.get("run", {}).get("wall_clock_s")
    out["reference_dof"] = reference_meta.get("dof_for_this_order")
    if match.comparable:
        out["available"] = True
        out["pairs"] = [
            {
                "reference_mode": pair.a.mode,
                "this_mode": pair.b.mode,
                "reference_frequency_GHz": pair.a.frequency_GHz,
                "this_frequency_GHz": pair.b.frequency_GHz,
                "delta_f_relative": pair.delta_f_relative,
                "delta_abs_p_relative": pair.delta_abs_participation_relative.get(1),
                "guard": pair.guard,
                "separation_margin": pair.separation_margin,
            }
            for pair in match.pairs
        ]
    else:
        out["reason"] = match.reason
    return out


def refinement_trend(comparison: dict[str, Any], entry: dict[str, Any], reference_meta: dict[str, Any]) -> dict[str, Any]:
    """What one extra rung can and cannot say about convergence."""
    out: dict[str, Any] = {
        "levels_available": 2,
        "note": (
            "Two rungs give a difference, not a rate: an observed order of convergence needs a "
            "third. What two rungs do give is the SIZE of the level-1 to level-2 change, which "
            "bounds how far level 1 was from the refined answer."
        ),
    }
    if not comparison.get("available"):
        out["available"] = False
        return out
    out["available"] = True
    out["cost"] = {
        "reference_dof": comparison.get("reference_dof"),
        "this_dof": entry.get("dof_measured"),
        "dof_ratio": (
            entry["dof_measured"] / comparison["reference_dof"]
            if comparison.get("reference_dof") else None
        ),
        "reference_wall_clock_s": comparison.get("reference_wall_clock_s"),
        "this_wall_clock_s": entry.get("run", {}).get("wall_clock_s"),
        "wall_clock_ratio": (
            entry["run"]["wall_clock_s"] / comparison["reference_wall_clock_s"]
            if comparison.get("reference_wall_clock_s") else None
        ),
        "cap_fraction_used": entry.get("run", {}).get("cap_fraction_used"),
    }
    out["per_pair"] = [
        {
            "reference_mode": p["reference_mode"],
            "this_mode": p["this_mode"],
            "delta_f_relative": p["delta_f_relative"],
            "delta_abs_p_relative": p["delta_abs_p_relative"],
        }
        for p in comparison["pairs"]
    ]
    deltas = [p["delta_f_relative"] for p in comparison["pairs"]]
    out["max_delta_f_relative"] = max(deltas) if deltas else None
    out["comparison_to_the_order_change"] = (
        "the pilot measured a 3.22e-01 relative frequency change between order 1 and order 2 on a "
        "byte-identical level-1 mesh; this rung's level-1 to level-2 change is the mesh half of "
        "the same question"
    )
    return out


def next_level_disposition(entry: dict[str, Any], dry_runs: dict[str, Any]) -> dict[str, Any]:
    """Whether level 3 remains justified and affordable. Advisory only."""
    level3 = dry_runs.get("L3") or {}
    dof3 = (level3.get("measured") or {}).get(f"dof_order{FINITE_ELEMENT_ORDER}")
    within = dof3 is not None and dof3 <= DOF_BUDGET
    this_wall = entry.get("run", {}).get("wall_clock_s")
    dof2 = entry.get("dof_measured")
    projected = None
    if this_wall and dof2 and dof3:
        # Scaled by the measured DOF ratio to a power taken from the one
        # within-order datum available; reported as a range, not a number.
        ratio = dof3 / dof2
        projected = {"linear_s": this_wall * ratio, "quadratic_s": this_wall * ratio**2}
    return {
        "level": 3,
        "dof_measured": dof3,
        "dof_budget": DOF_BUDGET,
        "within_dof_budget": within,
        "cap_s": SOLVE_TIMEOUT_S,
        "projected_wall_clock": projected,
        "projection_note": (
            "bracketed by linear and quadratic scaling in DOF, because two rungs give one "
            "within-order timing ratio and that is not enough to fix an exponent"
        ),
        "decision": "FOR REVIEW — this script launches one level per invocation and stops",
    }


# --- record -------------------------------------------------------------------


def render_report(summary: dict[str, Any]) -> str:
    L: list[str] = []
    add = L.append
    level = summary["level"]
    entry = summary["rung"]
    add(f"# Order-1 mesh-refinement check — level {level}")
    add("")
    add(f"Record `{summary['batch_id']}`. {summary['statement']}")
    add("")

    add("## 1. Dry runs (offline, no solver)")
    add("")
    add("| level | h_gap (mm) | tetrahedra | DOF order 1 | DOF order 2 | order 1 ≤ 250 000 | order 2 ≤ 250 000 |")
    add("|---|---|---|---|---|---|---|")
    for name in sorted(summary["dry_runs"]):
        d = summary["dry_runs"][name]
        m = d["measured"]
        add(
            f"| {d['level']} | {d['h_gap_mm']:.6f} | {m['tetrahedra']} | {m['dof_order1']} "
            f"| {m['dof_order2']} | {'yes' if d['within_budget_order1'] else 'NO'} "
            f"| {'yes' if d['within_budget_order2'] else 'NO'} |"
        )
    add("")

    add("## 2. The solve")
    add("")
    add(f"Status **{entry['status']}**, order {FINITE_ELEMENT_ORDER}, halo {HALO_MM} mm, "
        f"{entry.get('dof_measured')} DOF.")
    if entry.get("run"):
        run = entry["run"]
        add(f"Wall clock {run['wall_clock_s']:.1f} s, {100 * run['cap_fraction_used']:.1f} % of the "
            f"{SOLVE_TIMEOUT_S} s cap.")
    timers = entry.get("palace_timers", {}).get("durations_s", {})
    if timers:
        add("")
        add("| Palace timer | s |")
        add("|---|---|")
        for key in ("Total", "Setup", "Preconditioner", "LinearSolve", "EigenvalueSolve", "Div.-FreeProjection"):
            if key in timers:
                add(f"| {key} | {timers[key]:.3f} |")
        add("")
        add(entry["palace_timers"]["note"])
    add("")

    add("## 3. Admitted modes")
    add("")
    admission = entry.get("admission") or {}
    if admission:
        add("| m | f (GHz) | backward error | R | \\|R−1\\| | \\|p\\| | disposition |")
        add("|---|---|---|---|---|---|---|")
        for mode in admission["modes"]:
            p_abs = mode["participation_abs"].get("1", mode["participation_abs"].get(1, 0.0))
            add(
                f"| {mode['mode']} | {mode['frequency_GHz']:.6f} | {mode['backward_error']:.2e} "
                f"| {mode['energy_balance_ratio']:.6e} | {mode['energy_balance_defect']:.3e} "
                f"| {p_abs:.6e} | {mode['disposition']} |"
            )
        add("")

    add("## 4. Correspondence with level 1 (P2)")
    add("")
    comparison = summary["comparison"]
    if comparison.get("available"):
        add(f"Matching: **{comparison['match']['status']}**.")
        add("")
        add("| L1 m | L2 m | f_L1 (GHz) | f_L2 (GHz) | Δf | Δ\\|p\\| | guard | margin |")
        add("|---|---|---|---|---|---|---|---|")
        for p in comparison["pairs"]:
            add(
                f"| {p['reference_mode']} | {p['this_mode']} | {p['reference_frequency_GHz']:.6f} "
                f"| {p['this_frequency_GHz']:.6f} | {p['delta_f_relative']:.4e} "
                f"| {p['delta_abs_p_relative']:.4e} | {p['guard']} | {p['separation_margin']:.2f}× |"
            )
    else:
        add(f"Not available: {comparison.get('reason')}")
    add("")

    add("## 5. The port-field test")
    add("")
    test = entry.get("port_field_test") or {}
    if test.get("available"):
        add(f"**{test['verdict']}** — {test['reason']}")
        add("")
        add(f"κ calibrated from the admitted modes: {test['kappa']:.6e}, "
            f"spread across them {test['kappa_spread_max_over_min']:.4f}×.")
        add("")
        add("| m | admitted | reported R | s_t | κ·s_t/f² | restored R | E_ind/E_port |")
        add("|---|---|---|---|---|---|---|")
        for row in test["rows"]:
            add(
                f"| {row['mode']} | {'yes' if row['admitted'] else 'no'} "
                f"| {row['reported_balance']:.4e} | {row['s_tangential']:.4e} "
                f"| {row.get('port_participation_from_fields', float('nan')):.4e} "
                f"| {row.get('restored_balance', float('nan')):.6f} "
                f"| {row.get('cauchy_schwarz_ratio', float('nan')):.4e} |"
            )
    else:
        add(f"Not available: {test.get('reason')}")
    add("")

    add("## 6. Is level 3 justified and affordable?")
    add("")
    nxt = summary["next_level"]
    add(f"Level 3 measures **{nxt['dof_measured']} DOF** at order 1 against the "
        f"{nxt['dof_budget']} rule: {'inside' if nxt['within_dof_budget'] else 'OUTSIDE'}.")
    if nxt.get("projected_wall_clock"):
        p = nxt["projected_wall_clock"]
        add(f"Projected wall clock {p['linear_s']:.0f} s (linear in DOF) to {p['quadratic_s']:.0f} s "
            f"(quadratic), against the {nxt['cap_s']} s cap. {nxt['projection_note']}.")
    add("")
    add(f"**{nxt['decision']}**")
    add("")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", type=int, required=True, help="the single ladder level to run")
    parser.add_argument("--declaration", default="config/coupled/v2a_five_node_candidate.json")
    parser.add_argument("--results-root", default="results")
    parser.add_argument("--runtime", default=None)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--np", type=int, default=1)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--record-pointer", default=None)
    parser.add_argument(
        "--field-output-dir",
        default=None,
        help=(
            "move Palace's paraview/ output here after the analysis, so it can be uploaded as an "
            "artifact without being committed. Left in place when not given."
        ),
    )
    args = parser.parse_args(argv)

    if args.level == REFERENCE_LEVEL:
        raise SystemExit(f"level {REFERENCE_LEVEL} is the preserved reference rung and is not re-run")

    runtime = args.runtime or ("docker" if shutil.which("docker") else "podman")
    declaration = json.loads((REPO_ROOT / args.declaration).read_text())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_id = f"{RECORD_PREFIX}-L{args.level}-{stamp}"
    root = REPO_ROOT / args.results_root
    record_dir = root / batch_id
    solver_dir = record_dir / f"L{args.level}" / "solver"
    solver_dir.mkdir(parents=True, exist_ok=True)

    # Dry-run every level of interest first: free, and it decides admissibility.
    cell = chip_cell_from_declaration(declaration)
    dry_runs: dict[str, Any] = {}
    scratch = record_dir / "dryrun"
    for level in (2, 3):
        report = dry_run(cell, level, scratch / f"L{level}", dof_budget=DOF_BUDGET, halo_mm=HALO_MM)
        dry_runs[f"L{level}"] = report.as_dict()

    entry = execute_level(
        args.level, declaration, solver_dir,
        runtime=runtime, image=args.image, np_processes=args.np, prepare_only=args.prepare_only,
    )
    reference, reference_meta = reference_modes()
    comparison = compare_against_reference(entry, reference, reference_meta)

    summary = {
        "schema": SUMMARY_SCHEMA,
        "batch_id": batch_id,
        "statement": STATEMENT,
        "level": args.level,
        "finite_element_order": FINITE_ELEMENT_ORDER,
        "halo_mm": HALO_MM,
        "dof_budget": DOF_BUDGET,
        "wall_clock_cap_s": SOLVE_TIMEOUT_S,
        "rules_unchanged": {
            "admission": dict(ADMISSION_RULE),
            "matching": dict(MATCHING_RULE),
            "comparison_convention": dict(COMPARISON_CONVENTION),
            "solver": dict(COUPLED_SOLVER_RULES),
        },
        "dry_runs": dry_runs,
        "rung": entry,
        "comparison": comparison,
        "trend": refinement_trend(comparison, entry, reference_meta),
        "next_level": next_level_disposition(entry, dry_runs),
        "environment": {
            "python_version": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "container_runtime": runtime,
            "mpi_processes": args.np,
        },
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }

    # The dry-run meshes are regenerable; their measurements are not, and those
    # are in the summary. The field output is evidence but far too large to
    # commit, so it is moved aside for artifact upload rather than deleted.
    if scratch.is_dir():
        shutil.rmtree(scratch)
    paraview_relative = (summary["rung"].get("field_output") or {}).get("path")
    paraview = (solver_dir / paraview_relative) if paraview_relative else None
    if paraview and paraview.is_dir() and args.field_output_dir:
        destination = Path(args.field_output_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(str(paraview), str(destination))
        summary["rung"].setdefault("field_output", {})["moved_to"] = str(destination)

    (record_dir / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n")
    (record_dir / "report.md").write_text(render_report(summary))
    manifest.write(record_dir)
    if args.record_pointer:
        Path(args.record_pointer).write_text(str(record_dir))
    print(render_report(summary))
    print(f"{record_dir}: written")
    return 0 if entry["status"] in {"COMPLETED", "PREPARED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
