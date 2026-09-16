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
import traceback
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

#: The frozen frequency tolerance, used as the TARGET of the order-2 projection
#: so that projection invents no threshold of its own. Read from the approval
#: record the pilot ran under rather than restated here.
FROZEN_FREQUENCY_TOLERANCE = float(
    json.loads((REPO_ROOT / ".github" / "pilot-approval.json").read_text())
    ["frozen_criteria"]["max_relative_frequency_change"]
)

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


def rebuild_admitted(modes: list[dict[str, Any]], floor: float, ceiling: float) -> list[Any]:
    """Rebuild the admitted in-window ModeRecords a record already decided.

    A record's admission is evidence: it is read back, never re-decided.
    """
    from solvers.palace.mode_admission import ModeRecord  # noqa: PLC0415

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


def earlier_rungs(root: Path | None = None) -> list[dict[str, Any]]:
    """Every earlier order-1 rung already on disk, lowest level first.

    Level 1 is the preserved pilot run P2; higher levels are this ladder's own
    committed records. Each is read-only.
    """
    from solvers.palace.coupled_mesh import mesh_sizes_mm  # noqa: PLC0415

    results = root or (REPO_ROOT / "results")
    floor = COUPLED_SOLVER_RULES["band_floor_GHz"]
    ceiling = COUPLED_SOLVER_RULES["band_ceiling_GHz"]
    declaration = json.loads((REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json").read_text())
    cell = chip_cell_from_declaration(declaration)

    rungs: list[dict[str, Any]] = []
    reference, reference_meta = reference_modes(results)
    admitted = admit_modes(
        REFERENCE_RUN, reference,
        backward_error_tolerance=COUPLED_SOLVER_RULES["eigenmode_backward_error_max_tolerance"],
    )
    rungs.append({
        "level": REFERENCE_LEVEL,
        "h_gap_mm": mesh_sizes_mm(cell, REFERENCE_LEVEL)[1],
        "source": f"{REFERENCE_RECORD}/{REFERENCE_RUN}",
        "modes": admitted.admitted_in_window(floor, ceiling),
        "dof": reference_meta.get("dof_for_this_order"),
        "wall_clock_s": reference_meta.get("run", {}).get("wall_clock_s"),
    })

    for record in sorted(results.glob(f"{RECORD_PREFIX}-L*")):
        summary_path = record / "summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text())
        rung = summary.get("rung") or {}
        if rung.get("status") != "COMPLETED":
            continue
        level = int(summary["level"])
        if any(r["level"] == level for r in rungs):
            continue
        rungs.append({
            "level": level,
            "h_gap_mm": mesh_sizes_mm(cell, level)[1],
            "source": record.name,
            "modes": rebuild_admitted(rung["admission"]["modes"], floor, ceiling),
            "dof": rung.get("dof_measured"),
            "wall_clock_s": (rung.get("run") or {}).get("wall_clock_s"),
            "port_field_test": rung.get("port_field_test"),
        })
    return sorted(rungs, key=lambda r: r["level"])


def track_modes(rungs: list[dict[str, Any]]) -> dict[str, Any]:
    """Follow each admitted mode across every rung, using the matching rule.

    Adjacent levels are matched pairwise with the unchanged prospective rule,
    and the chain is then checked for transitivity against the direct
    first-to-last match. A mode that cannot be followed the whole way is
    reported as untracked rather than guessed at.
    """
    if len(rungs) < 2:
        return {"available": False, "reason": "fewer than two rungs"}
    pairwise = {}
    for a, b in zip(rungs, rungs[1:]):
        report = match_runs(f"L{a['level']} vs L{b['level']}", a["modes"], b["modes"])
        pairwise[f"L{a['level']}->L{b['level']}"] = report.as_dict()
        if not report.comparable:
            return {
                "available": False,
                "reason": f"L{a['level']} and L{b['level']} could not be matched: {report.reason}",
                "pairwise": pairwise,
            }
        a.setdefault("_pairs", {})[b["level"]] = {p.a.mode: p.b.mode for p in report.pairs}

    direct = match_runs(f"L{rungs[0]['level']} vs L{rungs[-1]['level']}", rungs[0]["modes"], rungs[-1]["modes"])
    pairwise[f"L{rungs[0]['level']}->L{rungs[-1]['level']} (direct)"] = direct.as_dict()

    series: dict[str, Any] = {}
    for start in rungs[0]["modes"]:
        chain = [start]
        current = start.mode
        ok = True
        for a, b in zip(rungs, rungs[1:]):
            nxt = a.get("_pairs", {}).get(b["level"], {}).get(current)
            if nxt is None:
                ok = False
                break
            record = next((r for r in b["modes"] if r.mode == nxt), None)
            if record is None:
                ok = False
                break
            chain.append(record)
            current = nxt
        if not ok:
            continue
        key = f"L{rungs[0]['level']}m{start.mode}"
        series[key] = {
            "points": [
                {
                    "level": rung["level"],
                    "h_gap_mm": rung["h_gap_mm"],
                    "mode": record.mode,
                    "frequency_GHz": record.frequency_GHz,
                    "abs_participation": record.abs_participation(),
                    "dof": rung["dof"],
                }
                for rung, record in zip(rungs, chain)
            ],
            "role": label_roles([start])[0].label,
        }

    transitive = True
    if direct.comparable:
        composed = {}
        for key, track in series.items():
            composed[track["points"][0]["mode"]] = track["points"][-1]["mode"]
        straight = {p.a.mode: p.b.mode for p in direct.pairs}
        transitive = composed == straight
    return {
        "available": bool(series),
        "series": series,
        "pairwise": pairwise,
        "chain_is_transitive": transitive,
        "transitivity_note": (
            "the composed L1->L2->L3 correspondence agrees with the direct L1->L3 match"
            if transitive else
            "the composed correspondence DISAGREES with the direct match; the chain is not trusted"
        ),
    }


# --- convergence, over three rungs --------------------------------------------


def observed_order(h: list[float], values: list[float]) -> dict[str, Any]:
    """The observed order of convergence from three rungs, or a refusal.

    Fits ``f(h) = f* + C h^p`` to three points. The refinement ratios here are
    not equal (h scales by 1, 2/3, 1/2), so ``p`` is not the textbook two-ratio
    formula: it solves

        (f1 - f2)/(f2 - f3) = (H1^p - H2^p)/(H2^p - 1),   H_i = h_i/h3

    whose right-hand side increases monotonically from
    ``(ln H1 - ln H2)/ln H2`` at ``p -> 0`` to infinity. That floor matters: a
    sequence whose successive differences shrink more slowly than it has **no
    positive order** and this returns NOT-SOLVABLE rather than a number. So
    does a non-monotone sequence. An estimator that always returns a value
    would be worthless here, because the question being asked is precisely
    whether the sequence is converging at all.
    """
    if len(h) != 3 or len(values) != 3:
        return {"solvable": False, "reason": "three rungs are required"}
    if not (h[0] > h[1] > h[2] > 0):
        return {"solvable": False, "reason": "the mesh sizes are not strictly decreasing"}

    d12, d23 = values[0] - values[1], values[1] - values[2]
    out: dict[str, Any] = {
        "h": list(h),
        "values": list(values),
        "difference_12": d12,
        "difference_23": d23,
        "differences_shrinking": abs(d23) < abs(d12),
        "monotone": (d12 > 0 and d23 > 0) or (d12 < 0 and d23 < 0),
    }
    if d23 == 0.0:
        out.update({"solvable": False, "reason": "the last two rungs are identical"})
        return out
    if not out["monotone"]:
        out.update({
            "solvable": False,
            "reason": "the sequence is not monotone in h, so no single power law describes it",
        })
        return out

    H = [x / h[2] for x in h]
    lhs = d12 / d23
    floor = (math.log(H[0]) - math.log(H[1])) / math.log(H[1])
    out["ratio_of_differences"] = lhs
    out["ratio_floor_for_any_positive_order"] = floor
    if lhs <= floor:
        out.update({
            "solvable": False,
            "reason": (
                f"the successive differences shrink by only {lhs:.4g}, at or below the {floor:.4g} "
                f"that the refinement ratios impose even as the order tends to zero: no positive "
                f"order of convergence fits these three rungs"
            ),
        })
        return out

    def rhs(power: float) -> float:
        return (H[0] ** power - H[1] ** power) / (H[1] ** power - 1.0)

    lo, hi = 1.0e-6, 1.0
    while rhs(hi) < lhs and hi < 64.0:
        hi *= 2.0
    if rhs(hi) < lhs:
        out.update({
            "solvable": False,
            "reason": f"no order below {hi:.0f} fits; the sequence collapses faster than a power law",
        })
        return out
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if rhs(mid) < lhs:
            lo = mid
        else:
            hi = mid
    power = 0.5 * (lo + hi)

    amplitude = d23 / (H[1] ** power - 1.0)
    limit = values[2] - amplitude
    out.update({
        "solvable": True,
        "observed_order": power,
        "extrapolated_limit": limit,
        "amplitude": amplitude,
        "remaining_relative_error": [
            (abs(v - limit) / abs(limit)) if limit else math.nan for v in values
        ],
    })
    return out


def convergence_over_rungs(series: dict[str, Any]) -> dict[str, Any]:
    """Observed order for each tracked mode's frequency and |p|."""
    out: dict[str, Any] = {"note": (
        "Three rungs give the FIRST order estimate, not a confirmed one: confirming it needs a "
        "fourth, because a three-point fit has no degrees of freedom left to test itself."
    )}
    per_mode = {}
    for key, track in series.items():
        h = [point["h_gap_mm"] for point in track["points"]]
        per_mode[key] = {
            "modes_by_level": {str(point["level"]): point["mode"] for point in track["points"]},
            "frequency": observed_order(h, [point["frequency_GHz"] for point in track["points"]]),
            "abs_participation": observed_order(h, [point["abs_participation"] for point in track["points"]]),
            "role": track.get("role"),
        }
    out["per_mode"] = per_mode
    solvable = [m["frequency"] for m in per_mode.values() if m["frequency"].get("solvable")]
    out["frequency_orders"] = [m["observed_order"] for m in solvable]
    out["all_frequencies_solvable"] = len(solvable) == len(per_mode) and bool(per_mode)
    return out


def asymptotic_assessment(convergence: dict[str, Any], expected_order: float = 2.0) -> dict[str, Any]:
    """Is the sequence clearly pre-asymptotic?

    For lowest-order Nedelec elements the textbook eigenvalue convergence is
    ``O(h^2)``. That is the expectation, not a measurement, and it is used only
    to say whether the observed orders are anywhere near where the method
    should land — never to replace them.
    """
    per_mode = convergence.get("per_mode", {})
    verdicts = []
    for key, entry in per_mode.items():
        frequency = entry["frequency"]
        if not frequency.get("solvable"):
            verdicts.append({"mode": key, "verdict": "NO-ORDER", "reason": frequency.get("reason")})
            continue
        power = frequency["observed_order"]
        remaining = frequency["remaining_relative_error"][-1]
        plausible = 0.5 <= power <= 2.0 * expected_order
        verdicts.append({
            "mode": key,
            "verdict": "PLAUSIBLE-ORDER" if plausible else "IMPLAUSIBLE-ORDER",
            "observed_order": power,
            "expected_order_for_the_method": expected_order,
            "remaining_relative_error_at_finest": remaining,
            "reason": (
                f"observed order {power:.3f} against the {expected_order:.0f} this method should "
                f"reach; estimated remaining error at the finest rung {remaining:.3e}"
            ),
        })
    any_implausible = any(v["verdict"] != "PLAUSIBLE-ORDER" for v in verdicts)
    worst_remaining = max(
        (v.get("remaining_relative_error_at_finest", math.inf) for v in verdicts), default=math.inf
    )
    return {
        "per_mode": verdicts,
        "still_clearly_pre_asymptotic": bool(any_implausible or worst_remaining > 1.0e-2),
        "worst_remaining_relative_error": worst_remaining,
        "criterion": (
            "clearly pre-asymptotic if any tracked mode yields no positive order, or an order far "
            "from the method's expected 2, or an estimated remaining error above 1e-2 at the "
            "finest rung. This is a descriptive numerical criterion introduced with this record; "
            "it gates nothing and is not a physical threshold."
        ),
    }


def order_two_projection(
    convergence: dict[str, Any],
    dof_by_level_order1: dict[int, int],
    dof_by_level_order2: dict[int, int],
    h_by_level: dict[int, float],
    order2_reference: dict[str, Any],
    target_relative: float,
) -> dict[str, Any]:
    """What order-2 mesh the frozen frequency tolerance would need.

    A projection, and labelled as one. It uses: the continuum limit from the
    order-1 extrapolation; the single order-2 datum available (level 1 from the
    pilot); and the measured ``DOF ~ h^-q`` scaling of this mesh family. The
    convergence rate of the order-2 discretisation is **not** measured — one
    point cannot give a rate — so the requirement is bracketed between the
    textbook ``O(h^4)`` for degree-2 elements and the pessimistic assumption
    that it converges no faster than the order-1 sequence does.
    """
    per_mode = convergence.get("per_mode", {})
    tracked = order2_reference.get("mode")
    entry = per_mode.get(tracked or "")
    if not entry or not entry["frequency"].get("solvable"):
        return {
            "available": False,
            "reason": "the order-1 sequence yields no extrapolated limit, so nothing can be projected",
        }
    limit = entry["frequency"]["extrapolated_limit"]
    observed = entry["frequency"]["observed_order"]
    f_order2 = order2_reference["frequency_GHz"]
    h_order2 = h_by_level[order2_reference["level"]]
    error_order2 = abs(f_order2 - limit) / abs(limit)

    levels = sorted(dof_by_level_order2)
    q = math.log(dof_by_level_order2[levels[-1]] / dof_by_level_order2[levels[0]]) / math.log(
        h_by_level[levels[0]] / h_by_level[levels[-1]]
    )

    projections = {}
    for name, rate in (("textbook_h4", 4.0), ("pessimistic_same_as_order1", observed)):
        if error_order2 <= target_relative:
            projections[name] = {
                "already_met": True,
                "required_h_mm": h_order2,
                "required_dof": dof_by_level_order2[order2_reference["level"]],
            }
            continue
        shrink = (target_relative / error_order2) ** (1.0 / rate)
        required_h = h_order2 * shrink
        required_dof = dof_by_level_order2[order2_reference["level"]] * (h_order2 / required_h) ** q
        projections[name] = {
            "assumed_rate": rate,
            "required_h_mm": required_h,
            "h_shrink_factor": 1.0 / shrink,
            "required_dof": required_dof,
            "required_dof_over_budget": required_dof / DOF_BUDGET,
            "within_dof_budget": required_dof <= DOF_BUDGET,
            "already_met": False,
        }
    return {
        "available": True,
        "target_relative_frequency_error": target_relative,
        "target_source": "the frozen halo criterion's frequency tolerance; no new threshold",
        "tracked_mode": tracked,
        "extrapolated_limit_GHz": limit,
        "order1_observed_order": observed,
        "order2_datum": {
            "level": order2_reference["level"],
            "frequency_GHz": f_order2,
            "h_gap_mm": h_order2,
            "dof": dof_by_level_order2[order2_reference["level"]],
            "relative_error_against_the_limit": error_order2,
        },
        "measured_dof_scaling_exponent_q": q,
        "dof_scaling_note": "DOF ~ h^-q measured over the three meshes of this family, not assumed",
        "projections": projections,
        "caveats": [
            "the order-1 sequence must be asymptotic for its extrapolated limit to mean anything",
            "the order-2 rate is not measured: one datum cannot give a rate, so it is bracketed",
            "DOF ~ h^-q is measured on three meshes of this family and extended beyond them",
        ],
    }


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
    this_level = rebuild_admitted(entry["admission"]["modes"], floor, ceiling)
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

    def num(value: Any, spec: str = ".4e") -> str:
        """Format a number, or say plainly that there is not one.

        Every section below can be handed a refusal instead of a value — that
        is the point of an estimator that can refuse — so the renderer must
        never assume a key is present. A report that crashes on a negative
        result loses the negative result.
        """
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "—"
        try:
            return format(value, spec)
        except (TypeError, ValueError):
            return str(value)

    convergence = summary.get("convergence") or {}
    tracking = summary.get("tracking") or {}
    series_all = tracking.get("series") or {}
    if convergence.get("available"):
        add("## 6. Convergence over the rungs")
        add("")
        add("| level | h_gap (mm) | DOF | wall clock (s) | source |")
        add("|---|---|---|---|---|")
        for r in summary.get("rungs", []):
            add(f"| {r.get('level')} | {num(r.get('h_gap_mm'), '.6f')} | {r.get('dof')} "
                f"| {num(r.get('wall_clock_s'), '.1f')} | `{r.get('source')}` |")
        add("")
        add(f"Mode tracking: {tracking.get('transitivity_note', 'not reported')}")
        add("")
        for key, entry_m in (convergence.get("per_mode") or {}).items():
            freq = entry_m.get("frequency") or {}
            add(f"### {key} ({entry_m.get('role')})")
            add("")
            points = (series_all.get(key) or {}).get("points") or []
            if points:
                add("| level | mode | f (GHz) | \\|p\\| |")
                add("|---|---|---|---|")
                for point in points:
                    add(f"| {point['level']} | {point['mode']} | {num(point['frequency_GHz'], '.6f')} "
                        f"| {num(point['abs_participation'])} |")
                add("")
            if freq.get("solvable"):
                add(f"- observed order **{num(freq.get('observed_order'), '.3f')}**, extrapolated limit "
                    f"**{num(freq.get('extrapolated_limit'), '.6f')} GHz**")
                remaining = freq.get("remaining_relative_error") or []
                if points and len(remaining) == len(points):
                    add("- estimated remaining relative error: "
                        + ", ".join(f"L{point['level']} {num(err, '.3e')}"
                                    for point, err in zip(points, remaining)))
            else:
                add(f"- **no order of convergence**: {freq.get('reason', 'not reported')}")
                add(f"- differences: L1→L2 {num(freq.get('difference_12'))}, "
                    f"L2→L3 {num(freq.get('difference_23'))}; shrinking: "
                    f"{freq.get('differences_shrinking')}; monotone: {freq.get('monotone')}")
                if freq.get("ratio_of_differences") is not None:
                    add(f"- ratio of successive differences {num(freq.get('ratio_of_differences'), '.4g')} "
                        f"against the {num(freq.get('ratio_floor_for_any_positive_order'), '.4g')} floor "
                        f"these refinement ratios impose for any positive order")
            part = entry_m.get("abs_participation") or {}
            if part.get("solvable"):
                add(f"- \\|p\\| observed order {num(part.get('observed_order'), '.3f')}, limit "
                    f"{num(part.get('extrapolated_limit'))}")
            else:
                add(f"- \\|p\\|: no order — {part.get('reason', 'not reported')}")
            add("")
        add(convergence.get("note", ""))
        add("")

    asymptotic = summary.get("asymptotic") or {}
    if asymptotic:
        add("## 7. Is the sequence still clearly pre-asymptotic?")
        add("")
        add(f"**{'YES' if asymptotic.get('still_clearly_pre_asymptotic') else 'NO'}** — worst estimated "
            f"remaining relative error at the finest rung "
            f"{num(asymptotic.get('worst_remaining_relative_error'), '.3e')}.")
        add("")
        for verdict in asymptotic.get("per_mode", []):
            add(f"- `{verdict.get('mode')}`: **{verdict.get('verdict')}** — {verdict.get('reason')}")
        add("")
        add(asymptotic.get("criterion", ""))
        add("")

    order_two = summary.get("order_two_projection") or {}
    if order_two.get("available"):
        add("## 8. What order-2 mesh the frozen tolerance would need")
        add("")
        usable = [v for v in (order_two.get("per_mode") or {}).values() if v.get("available")]
        if not usable:
            add("**Not projectable.** No tracked mode yielded an extrapolated limit, so there is "
                "no continuum value to measure an order-2 mesh against:")
            add("")
            for key, projection in (order_two.get("per_mode") or {}).items():
                add(f"- `{key}`: {projection.get('reason', 'not reported')}")
            add("")
        else:
            first = usable[0]
            add(f"Target: relative frequency error ≤ {num(first.get('target_relative_frequency_error'), '.0e')} "
                f"— {first.get('target_source')}.")
            add("")
            add("| mode | order-2 error at L1 | assumption | required h (mm) | required DOF | ≤ 250 000 |")
            add("|---|---|---|---|---|---|")
            for key, projection in (order_two.get("per_mode") or {}).items():
                if not projection.get("available"):
                    add(f"| {key} | — | not projectable: {projection.get('reason')} | — | — | — |")
                    continue
                datum = projection.get("order2_datum") or {}
                for name, values in (projection.get("projections") or {}).items():
                    if values.get("already_met"):
                        add(f"| {key} | {num(datum.get('relative_error_against_the_limit'), '.3e')} | {name} "
                            f"| already met | {num(values.get('required_dof'), '.0f')} | yes |")
                        continue
                    add(f"| {key} | {num(datum.get('relative_error_against_the_limit'), '.3e')} | {name} "
                        f"| {num(values.get('required_h_mm'), '.3e')} | {num(values.get('required_dof'), '.3e')} "
                        f"| {'yes' if values.get('within_dof_budget') else 'NO'} |")
            add("")
            add(f"Measured DOF scaling exponent q = {num(first.get('measured_dof_scaling_exponent_q'), '.3f')} "
                f"({first.get('dof_scaling_note')}).")
            add("")
            for caveat in first.get("caveats", []):
                add(f"- {caveat}")
            add("")
    elif order_two:
        add("## 8. What order-2 mesh the frozen tolerance would need")
        add("")
        add(f"Not available: {order_two.get('reason', 'not reported')}")
        add("")

    reproduction = summary.get("port_field_reproduction") or {}
    if reproduction:
        add("## 9. Does the port-field mechanism reproduce?")
        add("")
        for level, verdict in sorted(reproduction.items()):
            add(f"- {level}: **{verdict}**")
        add("")

    add("## 10. Is the next level justified and affordable?")
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

    # Every rung on disk, plus this one, tracked mode by mode.
    floor = COUPLED_SOLVER_RULES["band_floor_GHz"]
    ceiling = COUPLED_SOLVER_RULES["band_ceiling_GHz"]
    rungs = earlier_rungs()
    if entry.get("status") == "COMPLETED":
        from solvers.palace.coupled_mesh import mesh_sizes_mm  # noqa: PLC0415

        rungs.append({
            "level": args.level,
            "h_gap_mm": mesh_sizes_mm(cell, args.level)[1],
            "source": batch_id,
            "modes": rebuild_admitted(entry["admission"]["modes"], floor, ceiling),
            "dof": entry.get("dof_measured"),
            "wall_clock_s": (entry.get("run") or {}).get("wall_clock_s"),
            "port_field_test": entry.get("port_field_test"),
        })
    rungs = sorted({r["level"]: r for r in rungs}.values(), key=lambda r: r["level"])
    tracking = track_modes(rungs)

    convergence: dict[str, Any] = {"available": False, "reason": tracking.get("reason", "not tracked")}
    asymptotic: dict[str, Any] = {}
    order_two: dict[str, Any] = {"available": False, "reason": "fewer than three rungs"}
    if tracking.get("available") and len(rungs) >= 3:
        convergence = convergence_over_rungs(tracking["series"])
        convergence["available"] = True
        asymptotic = asymptotic_assessment(convergence)

        from solvers.palace.coupled_mesh import mesh_sizes_mm  # noqa: PLC0415

        h_by_level = {r["level"]: mesh_sizes_mm(cell, r["level"])[1] for r in rungs}
        dof1 = {r["level"]: r["dof"] for r in rungs}
        dof2 = {1: 208_670}
        for name, report in dry_runs.items():
            dof2[int(report["level"])] = report["measured"]["dof_order2"]
        # Which tracked mode each order-2 datum belongs to, decided by the
        # matching rule against the order-1 rung at the same level, not assumed.
        pilot = json.loads((REPO_ROOT / "results" / REFERENCE_RECORD / "summary.json").read_text())
        p1_modes = rebuild_admitted(
            admit_modes(
                "P1",
                join_modes_by_id(REPO_ROOT / "results" / REFERENCE_RECORD / "P1" / "solver" / "postpro"),
                backward_error_tolerance=COUPLED_SOLVER_RULES["eigenmode_backward_error_max_tolerance"],
            ).as_dict()["modes"],
            floor, ceiling,
        )
        order_match = match_runs("P2 vs P1 (order, level 1)", rungs[0]["modes"], p1_modes)
        order_two = {"available": False, "reason": order_match.reason, "match": order_match.as_dict()}
        if order_match.comparable:
            per_mode = {}
            for pair in order_match.pairs:
                key = f"L{rungs[0]['level']}m{pair.a.mode}"
                per_mode[key] = order_two_projection(
                    convergence, dof1, dof2, h_by_level,
                    {"mode": key, "level": 1, "frequency_GHz": pair.b.frequency_GHz},
                    FROZEN_FREQUENCY_TOLERANCE,
                )
            order_two = {
                "available": True,
                "match": order_match.as_dict(),
                "per_mode": per_mode,
                "order2_source": f"{REFERENCE_RECORD}/P1 (level 1, order 2)",
            }

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
        "rungs": [
            {k: v for k, v in r.items() if k not in {"modes", "_pairs", "port_field_test"}}
            for r in rungs
        ],
        "tracking": {k: v for k, v in tracking.items() if k != "series"} | (
            {"series": tracking["series"]} if tracking.get("series") else {}
        ),
        "convergence": convergence,
        "asymptotic": asymptotic,
        "order_two_projection": order_two,
        "port_field_reproduction": {
            f"L{r['level']}": (r.get("port_field_test") or {}).get("verdict")
            for r in rungs if r.get("port_field_test")
        },
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

    # The record is made durable BEFORE anything presentational runs. The
    # level-3 run rendered its report before writing the manifest and the
    # pointer, the renderer raised on a negative result the estimator was
    # designed to return, and the solve's outputs were never manifested,
    # uploaded or committed. Presentation must not be able to destroy evidence.
    (record_dir / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n")
    if args.record_pointer:
        Path(args.record_pointer).write_text(str(record_dir))

    render_failed: str | None = None
    try:
        report = render_report(summary)
    except Exception as exc:  # noqa: BLE001 - the record still has to survive
        render_failed = f"{type(exc).__name__}: {exc}"
        report = (
            f"# Order-1 mesh-refinement check — level {args.level}\n\n"
            f"**The report could not be rendered: {render_failed}**\n\n"
            f"Every measured quantity is in `summary.json`, which is written and manifested. "
            f"This is a presentation failure, not a loss of evidence.\n\n"
            f"```\n{traceback.format_exc()}\n```\n"
        )
    (record_dir / "report.md").write_text(report)
    manifest.write(record_dir)
    print(report)
    print(f"{record_dir}: written")
    if render_failed:
        print(f"WARNING: the report failed to render ({render_failed}); the record is intact")
        return 1
    return 0 if entry["status"] in {"COMPLETED", "PREPARED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
