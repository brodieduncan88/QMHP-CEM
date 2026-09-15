#!/usr/bin/env python
"""Execute the frozen golden candidate in Palace and record the proof.

This is the v0.2 milestone check: one real Palace eigenmode calculation of
the Object 001 empty vacuum cavity, end to end, with the solver version,
container image identity, command line, input and output hashes and the
solver's own convergence figure recorded, and every requested mode compared
with its closed-form value.

    uv run python scripts/palace_golden_run.py [--image REF] [--np N]
                                              [--results-root DIR] [--timeout S]

Exit codes:
    0  ran, converged, and every requested mode is within the golden tolerance
    2  Palace cannot execute here (the reason is printed; nothing is substituted)
    3  Palace ran but failed, did not converge, or its output could not be parsed
    4  Palace converged but a mode disagrees with the closed form beyond the
       golden tolerance
    5  golden candidate digest mismatch
    6  Palace succeeded but the quantum/gate evaluation of its result raised

After a successful solve the result is taken through the same quantum-device
layer and gate evaluation the sweep pipeline uses, so the record also shows
what the CEM gates make of a real Palace eigenmode result. A gate verdict on
the EMPTY box describes the empty box: the chip, recess, launches and lid are
not in the model, and every gate needing S-parameters stays INCOMPLETE.

The golden tolerance is ``solvers.palace.config.GOLDEN_RELATIVE_TOLERANCE``,
an ENGINEERING-RULE for a coarse first mesh, loose on purpose: it catches a
wrong box, a wrong unit scale or a wrong material, not a sub-optimal mesh. A
deviation above ``SOLVER_RULES["expected_relative_deviation"]`` is printed
as a warning and recorded, and does not change the exit code. Neither is a
validation gate.

Every outcome after preflight writes ``execution_record.json`` and a
manifest, including an unexpected exception, so that a failed attempt is on
the record with the same provenance as a successful one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from contracts import Candidate  # noqa: E402
from contracts.results import GateReport, QuantumResults, SolverResults  # noqa: E402
from evaluator import evaluate_candidate  # noqa: E402
from orchestrator import environment, manifest  # noqa: E402
from orchestrator.pipeline import evaluate_quantum  # noqa: E402
from solvers import ConvergenceFailure, RunContext, SolverUnavailable  # noqa: E402
from solvers.palace.adapter import DEFAULT_IMAGE, PalaceRunFailed, PalaceSolver  # noqa: E402
from solvers.palace.config import GOLDEN_RELATIVE_TOLERANCE, SOLVER_RULES  # noqa: E402
from solvers.palace.outputs import PalaceOutputError  # noqa: E402

GOLDEN_DIR = REPO_ROOT / "solvers" / "palace" / "golden"
GOLDEN = GOLDEN_DIR / "QMHP-CEM-A-RF-000001.json"
EXPECTED_RELATIVE_DEVIATION = float(SOLVER_RULES["expected_relative_deviation"])


def load_golden() -> Candidate:
    recorded, _, _ = (GOLDEN_DIR / "GOLDEN.sha256").read_text().strip().partition("  ")
    actual = hashlib.sha256(GOLDEN.read_bytes()).hexdigest()
    if actual != recorded:
        print(f"error: golden candidate digest {actual} != recorded {recorded}", file=sys.stderr)
        raise SystemExit(5)
    return Candidate.model_validate(json.loads(GOLDEN.read_text()))


def analytic_comparison(results, expected_GHz: list[float]) -> dict | None:
    """Compare every requested mode with its closed-form value."""
    if results is None or not results.eigenmodes or not expected_GHz:
        return None
    modes = []
    for i, f_exact in enumerate(expected_GHz):
        if i >= len(results.eigenmodes):
            modes.append({"index": i + 1, "closed_form_GHz": f_exact, "palace_GHz": None,
                          "relative_deviation": None, "within_tolerance": False})
            continue
        f_solved = results.eigenmodes[i].frequency_GHz
        deviation = (f_solved - f_exact) / f_exact
        modes.append({
            "index": i + 1,
            "closed_form_GHz": f_exact,
            "palace_GHz": f_solved,
            "relative_deviation": deviation,
            "within_tolerance": abs(deviation) <= GOLDEN_RELATIVE_TOLERANCE,
        })
    worst = max((abs(m["relative_deviation"]) for m in modes if m["relative_deviation"] is not None), default=None)
    return {
        "closed_form_fundamental_GHz": expected_GHz[0],
        "palace_fundamental_GHz": modes[0]["palace_GHz"],
        "relative_deviation": modes[0]["relative_deviation"],
        "modes": modes,
        "worst_relative_deviation": worst,
        "tolerance": GOLDEN_RELATIVE_TOLERANCE,
        "expected_relative_deviation": EXPECTED_RELATIVE_DEVIATION,
        "within_tolerance": all(m["within_tolerance"] for m in modes),
        "within_expected": (worst is not None and worst <= EXPECTED_RELATIVE_DEVIATION),
        "note": (
            "All requested modes are TM_mn0 of the empty box: this comparison "
            "verifies the X/Y extent and unit scaling, not the cavity height."
        ),
    }


def _dump(model) -> str:  # noqa: ANN001 - pydantic model
    return json.dumps(model.model_dump(mode="json", by_alias=True), indent=2, sort_keys=True) + "\n"


def gate_stage(candidate: Candidate, results: SolverResults, candidate_dir: Path) -> tuple[QuantumResults, GateReport]:
    """Quantum-device layer and gate evaluation, exactly as the sweep does them."""
    quantum = evaluate_quantum(candidate, results, tolerance_samples=0)
    (candidate_dir / "quantum_results.json").write_text(_dump(quantum))
    report = evaluate_candidate(candidate, results, quantum)
    (candidate_dir / "gate_report.json").write_text(_dump(report))
    return quantum, report


def gate_summary(quantum: QuantumResults, report: GateReport) -> dict:
    return {
        "overall_status": report.overall_status.value,
        "master_revision": report.master_revision,
        "quantum_unavailable": sorted(quantum.unavailable),
        "gates": [
            {
                "gate_id": g.gate_id,
                "status": g.status.value,
                "severity": g.severity.value,
                "evidence_class": (g.evidence_class.value if g.evidence_class else None),
                "measured": g.measured,
                "threshold": g.threshold,
                "units": g.units,
                "margin": g.margin,
                "hardware_required": g.hardware_required,
                "reason": g.reason,
            }
            for g in report.gates
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--np", type=int, default=1, help="MPI processes")
    parser.add_argument("--timeout", type=int, default=3600, help="seconds")
    parser.add_argument("--results-root", default=str(REPO_ROOT / "results"))
    parser.add_argument(
        "--record-pointer",
        default=None,
        metavar="FILE",
        help=(
            "write the path of the record directory this execution creates to FILE, "
            "as soon as it is created, so a caller need not guess it from a glob"
        ),
    )
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc)
    candidate = load_golden()
    adapter = PalaceSolver(image=args.image, runtime=args.runtime, mpi_processes=args.np, timeout_s=args.timeout)

    print(f"golden     : {candidate.candidate_id}  ({GOLDEN.relative_to(REPO_ROOT)})")
    print(f"image      : {args.image}")
    try:
        adapter.preflight()
    except SolverUnavailable as exc:
        print(f"\nPalace cannot execute here: {exc.reason}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 2
    identity = adapter.provenance()
    print(f"image id   : {identity.get('image_id')}")
    print(f"repo digest: {identity.get('repo_digest') or '(none: locally built image)'}")
    print(f"palace     : {identity.get('palace_version')} @ {identity.get('palace_commit')}")

    batch_id = f"PALACE-GOLDEN-{started.strftime('%Y%m%dT%H%M%SZ')}"
    root = Path(args.results_root) / batch_id
    candidate_dir = root / candidate.candidate_id
    solver_dir = candidate_dir / "solver"
    solver_dir.mkdir(parents=True, exist_ok=False)
    if args.record_pointer:
        # Written before Palace runs, so the pointer exists for every outcome
        # that has a record; a preflight failure (exit 2) creates neither.
        Path(args.record_pointer).write_text(str(root) + "\n")
    (candidate_dir / "candidate.json").write_text(json.dumps(candidate.to_ordered_dict(), indent=2, sort_keys=True) + "\n")

    context = RunContext(run_id=f"RUN-{batch_id}", work_dir=solver_dir)
    outcome = "UNKNOWN"
    exit_code = 0
    prepared = None
    parsed = None      # what Palace produced, before validation: evidence, never a verdict
    results = None     # set only once validate_convergence() has accepted it
    failure = None
    try:
        prepared = adapter.prepare(candidate, None, context)
        (solver_dir / "solver_input.json").write_text(json.dumps(prepared.payload, indent=2, sort_keys=True, default=str) + "\n")
        print(f"mesh       : {prepared.payload['mesh']['tetrahedron_count']} tets, sha256 {prepared.payload['mesh']['sha256'][:16]}…")
        print(f"config     : sha256 {prepared.payload['config_sha256'][:16]}…")
        print("running Palace ...", flush=True)
        raw = adapter.run(prepared)
        print(f"palace exit: {raw.returncode} in {(raw.ended_utc - raw.started_utc).total_seconds():.1f}s")
        parsed = adapter.parse(raw)
        results = adapter.validate_convergence(parsed)
        outcome = "CONVERGED"
    except (SolverUnavailable, PalaceRunFailed, PalaceOutputError) as exc:
        failure = f"{exc.__class__.__name__}: {exc}"
        outcome = "RUN_FAILED"
        exit_code = 3
    except ConvergenceFailure as exc:
        failure = f"ConvergenceFailure: {exc}"
        outcome = "NOT_CONVERGED"
        exit_code = 3
    except Exception as exc:  # noqa: BLE001 - the record must be written whatever happened
        failure = f"{exc.__class__.__name__}: {exc}\n{traceback.format_exc()}"
        outcome = "ERROR"
        exit_code = 3

    expected = list(prepared.payload.get("expected_solver_modes_GHz", [])) if prepared is not None else []
    if parsed is not None:
        # Written whether or not it was accepted: a NOT_CONVERGED parse is
        # still the record of what Palace produced.
        (solver_dir / "solver_results.json").write_text(_dump(parsed))
    analytic_check = None
    if results is not None:
        # Only a validated result is compared with the closed form; an
        # unconverged one keeps its NOT_CONVERGED outcome and exit code 3.
        analytic_check = analytic_comparison(results, expected)
        if analytic_check is not None and not analytic_check["within_tolerance"]:
            outcome = "ANALYTIC_MISMATCH"
            exit_code = 4

    gates = None
    gate_failure = None
    if results is not None and outcome in ("CONVERGED", "ANALYTIC_MISMATCH"):
        try:
            quantum, report = gate_stage(candidate, results, candidate_dir)
            gates = gate_summary(quantum, report)
        except Exception as exc:  # noqa: BLE001 - recorded, and it changes the exit code
            gate_failure = f"{exc.__class__.__name__}: {exc}\n{traceback.format_exc()}"
            if exit_code == 0:
                exit_code = 6

    ended = datetime.now(timezone.utc)
    env = environment.record(
        started_utc=started,
        solver_name="palace",
        solver_version=(parsed.solver.version if parsed else str(identity.get("palace_version"))),
        solver_identity=f"{args.image}@{identity.get('image_id')}",
        ended_utc=ended,
    )
    record = {
        "schema": "qmhp-cem.palace-golden-run/0.2.0",
        "batch_id": batch_id,
        "outcome": outcome,
        "failure": failure,
        "candidate_id": candidate.candidate_id,
        "golden_sha256": hashlib.sha256(GOLDEN.read_bytes()).hexdigest(),
        "solver_provenance": identity,
        "analytic_check": analytic_check,
        "convergence": (parsed.convergence.model_dump() if parsed else None),
        "eigenmodes_GHz": ([m.frequency_GHz for m in parsed.eigenmodes] if parsed else None),
        "validated": results is not None,
        "expected_modes_GHz": expected or None,
        "gates": gates,
        "gate_failure": gate_failure,
        "environment": env.model_dump(mode="json"),
        "started_utc": started.isoformat(),
        "ended_utc": ended.isoformat(),
        "statement": (
            "Empty Object 001 vacuum cavity as a closed PEC box. ENGINEERING-SEED "
            "dimensions. A computational result; not hardware validation, and not "
            "yet a mesh-converged result (spec §15)."
        ),
    }
    (root / "execution_record.json").write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n")
    _, manifest_digest = manifest.write(root)

    print()
    print(f"outcome    : {outcome}")
    if failure:
        print(f"failure    : {failure}")
    if analytic_check:
        for m in analytic_check["modes"]:
            if m["palace_GHz"] is None:
                print(f"mode {m['index']}     : palace (missing)  closed form {m['closed_form_GHz']:.6f} GHz")
            else:
                print(f"mode {m['index']}     : palace {m['palace_GHz']:.6f} GHz  "
                      f"closed form {m['closed_form_GHz']:.6f} GHz  "
                      f"deviation {m['relative_deviation']:+.3e}")
        if not analytic_check["within_expected"] and analytic_check["within_tolerance"]:
            print(f"WARNING    : worst deviation {analytic_check['worst_relative_deviation']:.3e} exceeds the "
                  f"expected {EXPECTED_RELATIVE_DEVIATION:.0e} for this mesh and order; within the "
                  f"{GOLDEN_RELATIVE_TOLERANCE:.0%} proof gate, but look at the mesh before trusting the number.")
    if parsed:
        print(f"convergence: {parsed.convergence.status.value}: {parsed.convergence.metric} = "
              f"{parsed.convergence.value:.3e} (tol {parsed.convergence.tolerance:.1e})")
        print(f"solver     : {parsed.solver.name} {parsed.solver.version}  image {parsed.solver.image_digest}")
    if gates:
        print(f"gates      : overall {gates['overall_status']} (master {gates['master_revision']})")
        for g in gates["gates"]:
            value = "" if g["measured"] is None else f"  measured {g['measured']:.6g}"
            thr = "" if g["threshold"] is None else f" / threshold {g['threshold']:.6g}"
            unit = f" {g['units']}" if g["units"] else ""
            print(f"  {g['gate_id']:<20} {g['status']:<16} {g['severity']:<6}{value}{thr}{unit}")
        if gates["quantum_unavailable"]:
            print(f"  quantum unavailable: {', '.join(gates['quantum_unavailable'])}")
    if gate_failure:
        print(f"gate stage : FAILED\n{gate_failure}")
    print(f"record     : {root.relative_to(REPO_ROOT) if root.is_relative_to(REPO_ROOT) else root}")
    print(f"manifest   : {manifest_digest[:16]}…")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
