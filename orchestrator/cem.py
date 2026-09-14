"""``cem`` command-line orchestrator (spec §11.1).

::

    uv run cem generate <sweep.yaml>
    uv run cem simulate <sweep.yaml> --solver mock
    uv run cem evaluate <batch-dir>
    uv run cem sweep    <sweep.yaml> --solver mock
    uv run cem report   <batch-dir>

The required acceptance command is::

    uv run cem sweep sweeps/object001_grid.yaml --solver mock
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from contracts import master
from contracts.common import GateStatus
from contracts.sweep import SweepDefinition
from orchestrator import manifest, pipeline
from solvers import SolverUnavailable, registered_names
from solvers.mock.adapter import FIXTURES


def load_sweep(path: Path) -> SweepDefinition:
    with Path(path).open() as fh:
        return SweepDefinition.model_validate(yaml.safe_load(fh))


# --- commands ---------------------------------------------------------------


def cmd_generate(args: argparse.Namespace) -> int:
    """Expand a sweep into candidates without solving."""
    sweep = load_sweep(args.sweep)
    base = pipeline.load_base_candidate(master.REPO_ROOT / sweep.base_candidate)
    candidates = pipeline.build_candidates(sweep, base)

    print(f"sweep      : {sweep.name}")
    print(f"object     : {sweep.object_type}")
    print(f"candidates : {len(candidates)}")
    for candidate in candidates:
        cavity = candidate.parameters.vacuum_cavity.height_above_chip_mm
        bore = candidate.parameters.launches.bore_diameter_mm
        print(
            f"  {candidate.candidate_id}  cavity={cavity:.2f} mm  bore={bore:.2f} mm"
        )
    if args.output:
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        for candidate in candidates:
            (out / f"{candidate.candidate_id}.json").write_text(
                json.dumps(candidate.to_ordered_dict(), indent=2, sort_keys=True) + "\n"
            )
        print(f"written to : {out}")
    return 0


def cmd_sweep(args: argparse.Namespace) -> int:
    """Run a full deterministic sweep."""
    sweep = load_sweep(args.sweep)
    try:
        report, outcomes = pipeline.run_sweep(
            sweep,
            solver_name=args.solver,
            results_root=Path(args.results_root) if args.results_root else None,
            fixture=args.fixture,
            tolerance_samples=args.tolerance_samples,
        )
    except SolverUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4

    _print_batch(report, outcomes)
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """Alias of ``sweep``; kept because spec §11.1 names both."""
    return cmd_sweep(args)


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Re-read an existing batch and print its gate outcomes."""
    batch_dir = Path(args.batch)
    report_path = batch_dir / "batch_report.json"
    if not report_path.exists():
        print(f"error: no batch_report.json in {batch_dir}", file=sys.stderr)
        return 2

    report = json.loads(report_path.read_text())
    print(f"batch      : {report['batch_id']}")
    print(f"solver     : {report['solver']}")
    print(f"outcome    : {report['batch_outcome']}")
    for candidate_id in report.get("candidate_ids", []):
        gate_path = batch_dir / candidate_id / "gate_report.json"
        if not gate_path.exists():
            print(f"  {candidate_id}  (no gate report — candidate did not adjudicate)")
            continue
        gates = json.loads(gate_path.read_text())
        print(f"  {candidate_id}  {gates['overall_status']}")
        if args.verbose:
            for gate in gates["gates"]:
                print(f"      {gate['gate_id']:22} {gate['status']}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Print a batch summary and verify its manifest."""
    batch_dir = Path(args.batch)
    report_path = batch_dir / "batch_report.json"
    if not report_path.exists():
        print(f"error: no batch_report.json in {batch_dir}", file=sys.stderr)
        return 2

    report = json.loads(report_path.read_text())
    print(f"batch          : {report['batch_id']}")
    print(f"solver         : {report['solver']}")
    print(f"candidates     : {report['candidate_count']}")
    print(f"  pass         : {report['pass_count']}")
    print(f"  fail         : {report['fail_count']}")
    print(f"  incomplete   : {report.get('incomplete_count', 0)}")
    print(f"  hardware     : {report['hardware_gated_count']}")
    print(f"outcome        : {report['batch_outcome']}")
    print(f"rng seed       : {report.get('rng_seed')}")

    findings = manifest.verify(batch_dir)
    if findings:
        print(f"manifest       : {len(findings)} DISCREPANCIES")
        for finding in findings:
            print(f"  ! {finding}")
    else:
        print("manifest       : verified")

    for note in report.get("notes", []):
        print(f"note           : {note}")
    return 0 if not findings else 5


def cmd_verify_master(args: argparse.Namespace) -> int:
    """Verify frozen master provenance digests (spec §12.1)."""
    findings = master.verify_provenance()
    if findings:
        print("master provenance: MISMATCH")
        for finding in findings:
            print(f"  ! {finding}")
        return 5
    print("master provenance: verified")
    print(f"  revision : {master.master_revision()}")
    print(f"  gates    : {', '.join(sorted(master.gate_definitions()))}")
    return 0


# --- output helpers ---------------------------------------------------------


def _print_batch(report, outcomes) -> None:  # noqa: ANN001
    print(f"batch      : {report.batch_id}")
    print(f"solver     : {report.solver}")
    print(f"candidates : {report.candidate_count}")
    print()
    for outcome in outcomes:
        line = f"  {outcome.candidate.candidate_id}  {outcome.state.value}"
        if outcome.gate_report:
            failed = [
                g.gate_id
                for g in outcome.gate_report.gates
                if g.status in (GateStatus.FAIL, GateStatus.EXTRACTION_INCONSISTENT)
            ]
            if failed:
                line += f"  (failing: {', '.join(failed)})"
        print(line)
    print()
    print(f"  pass       : {report.pass_count}")
    print(f"  fail       : {report.fail_count}")
    print(f"  incomplete : {report.incomplete_count}")
    print(f"  hardware   : {report.hardware_gated_count}")
    print()
    print(f"outcome    : {report.batch_outcome.value}")
    print(f"manifest   : {report.manifest_sha256[:16]}…")
    print()
    for note in report.notes:
        print(f"note: {note}")


# --- entry point ------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cem",
        description=(
            "QMHP-CEM v0.1 — computational-engineering orchestrator. "
            "A computational PASS is not hardware validation."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_solver_args(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--solver",
            default=None,
            help=f"solver adapter (default: the sweep's own). Known: {registered_names()}",
        )
        p.add_argument(
            "--fixture",
            default="default",
            choices=FIXTURES,
            help="mock solver fixture (mock only)",
        )
        p.add_argument("--results-root", default=None, help="override results/ root")
        p.add_argument(
            "--tolerance-samples",
            type=int,
            default=0,
            help=(
                "ensemble size for the TOLERANCE gate (0 = skip). Each device "
                "costs a full static solve plus a root search, ~50 ms."
            ),
        )

    p_generate = sub.add_parser("generate", help="expand a sweep into candidates")
    p_generate.add_argument("sweep", type=Path)
    p_generate.add_argument("--output", default=None, help="write candidate JSON here")
    p_generate.set_defaults(func=cmd_generate)

    p_simulate = sub.add_parser("simulate", help="run a sweep through a solver")
    p_simulate.add_argument("sweep", type=Path)
    add_solver_args(p_simulate)
    p_simulate.set_defaults(func=cmd_simulate)

    p_sweep = sub.add_parser("sweep", help="run a full deterministic sweep")
    p_sweep.add_argument("sweep", type=Path)
    add_solver_args(p_sweep)
    p_sweep.set_defaults(func=cmd_sweep)

    p_evaluate = sub.add_parser("evaluate", help="print gate outcomes for a batch")
    p_evaluate.add_argument("batch", type=Path)
    p_evaluate.add_argument("-v", "--verbose", action="store_true")
    p_evaluate.set_defaults(func=cmd_evaluate)

    p_report = sub.add_parser("report", help="summarise a batch and verify its manifest")
    p_report.add_argument("batch", type=Path)
    p_report.set_defaults(func=cmd_report)

    p_master = sub.add_parser("verify-master", help="verify frozen master provenance")
    p_master.set_defaults(func=cmd_verify_master)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
