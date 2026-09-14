#!/usr/bin/env python
"""Execute the frozen golden candidate in Palace and record the proof.

This is the v0.2 milestone check: one real Palace eigenmode calculation of
the Object 001 empty vacuum cavity, end to end, with the solver version,
container image identity, command line, input and output hashes and the
solver's own convergence figure recorded, and the lowest mode compared with
the closed-form value.

    uv run python scripts/palace_golden_run.py [--image REF] [--np N]
                                              [--results-root DIR] [--timeout S]

Exit codes:
    0  ran, converged, and the fundamental is within the analytic tolerance
    2  Palace cannot execute here (the reason is printed; nothing is substituted)
    3  Palace ran but did not converge, or its output could not be parsed
    4  Palace converged but the fundamental disagrees with the closed form
       beyond the golden tolerance
    5  golden candidate digest mismatch

The analytic tolerance (``GOLDEN_RELATIVE_TOLERANCE``) is an ENGINEERING-RULE
of this script for a coarse first mesh. It is not a validation gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from contracts import Candidate  # noqa: E402
from orchestrator import environment, manifest  # noqa: E402
from solvers import ConvergenceFailure, RunContext, SolverUnavailable  # noqa: E402
from solvers.palace import analytic  # noqa: E402
from solvers.palace.adapter import DEFAULT_IMAGE, PalaceRunFailed, PalaceSolver  # noqa: E402
from solvers.palace.outputs import PalaceOutputError  # noqa: E402

GOLDEN_DIR = REPO_ROOT / "solvers" / "palace" / "golden"
GOLDEN = GOLDEN_DIR / "QMHP-CEM-A-RF-000001.json"
GOLDEN_RELATIVE_TOLERANCE = 0.02


def load_golden() -> Candidate:
    recorded, _, _ = (GOLDEN_DIR / "GOLDEN.sha256").read_text().strip().partition("  ")
    actual = hashlib.sha256(GOLDEN.read_bytes()).hexdigest()
    if actual != recorded:
        print(f"error: golden candidate digest {actual} != recorded {recorded}", file=sys.stderr)
        raise SystemExit(5)
    return Candidate.model_validate(json.loads(GOLDEN.read_text()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--np", type=int, default=1, help="MPI processes")
    parser.add_argument("--timeout", type=int, default=3600, help="seconds")
    parser.add_argument("--results-root", default=str(REPO_ROOT / "results"))
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
    (candidate_dir / "candidate.json").write_text(json.dumps(candidate.to_ordered_dict(), indent=2, sort_keys=True) + "\n")

    context = RunContext(run_id=f"RUN-{batch_id}", work_dir=solver_dir)
    outcome = "UNKNOWN"
    exit_code = 0
    results = None
    failure = None
    try:
        prepared = adapter.prepare(candidate, None, context)
        (solver_dir / "solver_input.json").write_text(json.dumps(prepared.payload, indent=2, sort_keys=True, default=str) + "\n")
        print(f"mesh       : {prepared.payload['mesh']['tetrahedron_count']} tets, sha256 {prepared.payload['mesh']['sha256'][:16]}…")
        print(f"config     : sha256 {prepared.payload['config_sha256'][:16]}…")
        print("running Palace ...", flush=True)
        raw = adapter.run(prepared)
        print(f"palace exit: {raw.returncode} in {(raw.ended_utc - raw.started_utc).total_seconds():.1f}s")
        results = adapter.parse(raw)
        results = adapter.validate_convergence(results)
        outcome = "CONVERGED"
    except (PalaceRunFailed, PalaceOutputError) as exc:
        failure = f"{exc.__class__.__name__}: {exc}"
        outcome = "RUN_FAILED"
        exit_code = 3
    except ConvergenceFailure as exc:
        failure = f"ConvergenceFailure: {exc}"
        outcome = "NOT_CONVERGED"
        exit_code = 3

    analytic_check = None
    if results is not None:
        (solver_dir / "solver_results.json").write_text(
            json.dumps(results.model_dump(mode="json", by_alias=True), indent=2, sort_keys=True) + "\n"
        )
        f_exact = analytic.fundamental_GHz(22.0, 22.0, 1.5)
        if results.eigenmodes:
            f_solved = results.eigenmodes[0].frequency_GHz
            deviation = (f_solved - f_exact) / f_exact
            within = abs(deviation) <= GOLDEN_RELATIVE_TOLERANCE
            analytic_check = {
                "closed_form_fundamental_GHz": f_exact,
                "palace_fundamental_GHz": f_solved,
                "relative_deviation": deviation,
                "tolerance": GOLDEN_RELATIVE_TOLERANCE,
                "within_tolerance": within,
            }
            if not within:
                outcome = "ANALYTIC_MISMATCH"
                exit_code = 4

    ended = datetime.now(timezone.utc)
    env = environment.record(
        started_utc=started,
        solver_name="palace",
        solver_version=(results.solver.version if results else identity.get("palace_version")),
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
        "convergence": (results.convergence.model_dump() if results else None),
        "eigenmodes_GHz": ([m.frequency_GHz for m in results.eigenmodes] if results else None),
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
        print(f"fundamental: palace {analytic_check['palace_fundamental_GHz']:.6f} GHz  "
              f"closed form {analytic_check['closed_form_fundamental_GHz']:.6f} GHz  "
              f"deviation {analytic_check['relative_deviation']:+.3e}")
    if results:
        print(f"convergence: {results.convergence.metric} = {results.convergence.value:.3e} "
              f"(tol {results.convergence.tolerance:.1e})")
    print(f"record     : {root.relative_to(REPO_ROOT) if root.is_relative_to(REPO_ROOT) else root}")
    print(f"manifest   : {manifest_digest[:16]}…")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
