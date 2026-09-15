#!/usr/bin/env python
"""Execute the mesh-refinement and height-sensitive verification campaign in Palace.

    uv run python scripts/palace_verify_campaign.py [--image REF] [--np N]
        [--results-root DIR] [--record-pointer FILE] [--only RUN ...] [--prepare-only]

The campaign is defined in :mod:`solvers.palace.verification` and frozen into
``campaign.json`` (with its sha256) at the top of the record directory
``results/PALACE-VERIFY-<UTC>/``. Every run goes through the unchanged
boundary ``prepare -> run -> parse -> validate_convergence`` of the Palace
adapter, with its mesh length, mode count, target and probes set explicitly
through ``RunContext.extra``. The record is append-only: a new directory per
execution, the summary, report and manifest rewritten after every run so a
job that dies mid-way still leaves a coherent partial record.

Exit codes:
    0  every run executed; mesh convergence PASS and the auxiliary height
       benchmark PASS (the Object 001 height benchmark is reported separately
       and expected INCOMPLETE or BLOCKED on the hosted runner)
    2  Palace cannot execute here (nothing is written)
    3  a verdict is FAIL
    4  mesh convergence or the auxiliary height benchmark is INCOMPLETE/BLOCKED
    5  golden candidate digest mismatch

``--prepare-only`` meshes every run and records the DOF estimates without
launching Palace (no container needed); such a record is labelled as
prepare-only and carries no verdicts.
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
from orchestrator import environment, manifest  # noqa: E402
from solvers import ConvergenceFailure, RunContext, SolverUnavailable  # noqa: E402
from solvers.palace import outputs as palace_outputs  # noqa: E402
from solvers.palace import verification as V  # noqa: E402
from solvers.palace.adapter import DEFAULT_IMAGE, PalaceRunFailed, PalaceSolver  # noqa: E402
from solvers.palace.config import expected_solver_modes_GHz  # noqa: E402

GOLDEN_DIR = REPO_ROOT / "solvers" / "palace" / "golden"
GOLDEN = GOLDEN_DIR / "QMHP-CEM-A-RF-000001.json"


def _dump(obj) -> str:  # noqa: ANN001
    return json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n"


def load_golden() -> Candidate:
    recorded, _, _ = (GOLDEN_DIR / "GOLDEN.sha256").read_text().strip().partition("  ")
    if hashlib.sha256(GOLDEN.read_bytes()).hexdigest() != recorded:
        print("error: golden candidate digest mismatch", file=sys.stderr)
        raise SystemExit(5)
    return Candidate.model_validate(json.loads(GOLDEN.read_text()))


def execute_run(adapter: PalaceSolver, candidate: Candidate, spec: V.RunSpec, run_dir: Path,
                run_id: str, prepare_only: bool) -> tuple[V.RunResult, list[dict] | None]:
    """One run through the adapter boundary; never raises, always returns a RunResult."""
    solver_dir = run_dir / "solver"
    solver_dir.mkdir(parents=True, exist_ok=False)
    rr = V.RunResult(name=spec.name, status="PREPARED", mesh_length_mm=spec.mesh_length_mm)
    decisions = None
    try:
        context = RunContext(run_id=run_id, work_dir=solver_dir, extra={"palace": spec.overrides()})
        prepared = adapter.prepare(candidate, None, context)
        (solver_dir / "solver_input.json").write_text(_dump(prepared.payload))
        mesh = prepared.payload["mesh"]
        rr.nodes, rr.tetrahedra = int(mesh["node_count"]), int(mesh["tetrahedron_count"])
        rr.mesh_sha256, rr.config_sha256 = mesh["sha256"], prepared.payload["config_sha256"]
        rr.dof_estimate = V.estimate_dof(rr.tetrahedra)
        print(f"  {spec.name}: lc {spec.mesh_length_mm:.4f} mm, {rr.tetrahedra} tets, ~{rr.dof_estimate} DOF est.", flush=True)
        if rr.dof_estimate > V.RULES["dof_budget"]:
            rr.status = "BLOCKED"
            rr.failure = (f"estimated {rr.dof_estimate} DOF exceeds the declared runner budget of "
                          f"{V.RULES['dof_budget']}; mesh kept, Palace not launched")
            print(f"  {spec.name}: BLOCKED ({rr.failure})", flush=True)
            return rr, None
        if prepare_only:
            return rr, None
        adapter.timeout_s = spec.timeout_s
        print(f"  {spec.name}: running Palace (timeout {spec.timeout_s}s) ...", flush=True)
        raw = adapter.run(prepared)
        rr.runtime_s = (raw.ended_utc - raw.started_utc).total_seconds()
        parsed = adapter.parse(raw)
        (solver_dir / "solver_results.json").write_text(_dump(parsed.model_dump(mode="json", by_alias=True)))
        table = palace_outputs.parse_eig_csv(raw.output_dir / "eig.csv")
        rr.frequencies_GHz = [r.frequency_re_GHz for r in table.rows]
        rr.backward_errors = [r.backward_error for r in table.rows]
        rr.backward_error_max = float(parsed.convergence.value)
        rr.palace_status = parsed.convergence.status.value
        meta = palace_outputs.read_metadata_json(raw.output_dir / "palace.json")
        rr.dof = int(meta.get("Problem", {}).get("DegreesOfFreedom", 0)) or None
        rr.palace_total_s = (meta.get("ElapsedTime", {}).get("Durations", {}) or {}).get("Total")
        samples = palace_outputs.parse_probe_csv(raw.output_dir / "probe-E.csv")
        rr.z_fraction = palace_outputs.z_polarisation_fraction(samples)
        (run_dir / "probe_summary.json").write_text(_dump({
            "probes_mm": prepared.payload.get("effective", {}).get("probes_mm"),
            "z_polarisation_fraction_by_mode": {str(k): v for k, v in rr.z_fraction.items()},
            "samples": len(samples),
            "definition": "sum over probes of |E_z|^2 divided by sum of |E|^2, per mode",
        }))
        try:
            adapter.validate_convergence(parsed)
            rr.status = "CONVERGED"
        except ConvergenceFailure as exc:
            rr.status = "NOT_CONVERGED"
            rr.failure = str(exc)
        if spec.height_mode is not None:
            f_max = max(rr.frequencies_GHz) * 1.05 if rr.frequencies_GHz else spec.target_GHz * 1.2
            decisions = V.match_modes(rr.frequencies_GHz, spec.cavity, f_max, rr.z_fraction)
            (run_dir / "mode_matching.json").write_text(_dump({
                "run": spec.name, "target_mode": list(spec.height_mode), "tolerance": V.RULES["height_mode_match_relative_tolerance"],
                "decisions": decisions,
            }))
        print(f"  {spec.name}: {rr.status}, DOF {rr.dof}, {rr.runtime_s:.0f}s, modes {['%.6f' % f for f in rr.frequencies_GHz[:6]]}", flush=True)
    except PalaceRunFailed as exc:
        rr.status = "RUN_FAILED"
        rr.failure = f"PalaceRunFailed: {exc}"
        print(f"  {spec.name}: RUN_FAILED ({str(exc)[:160]})", flush=True)
    except (SolverUnavailable, palace_outputs.PalaceOutputError) as exc:
        rr.status = "RUN_FAILED"
        rr.failure = f"{exc.__class__.__name__}: {exc}"
        print(f"  {spec.name}: RUN_FAILED ({str(exc)[:160]})", flush=True)
    except Exception as exc:  # noqa: BLE001 - the record must be written whatever happened
        rr.status = "ERROR"
        rr.failure = f"{exc.__class__.__name__}: {exc}\n{traceback.format_exc()}"
        print(f"  {spec.name}: ERROR ({exc})", flush=True)
    return rr, decisions


def evaluate(campaign: V.Campaign, results: dict[str, V.RunResult], decisions: dict[str, list[dict]]) -> dict:
    """The comparisons and verdicts from whatever has been executed so far."""
    out: dict = {}
    expected = expected_solver_modes_GHz(campaign.object001.domain())
    ladder = [results[r.name] for r in campaign.ladder if r.name in results]
    table = V.mesh_convergence_table(ladder, expected)
    out["mesh_convergence"] = {
        "expected_analytic_GHz": expected,
        "table": table,
        "degenerate_pair": V.degenerate_pair_table(ladder),
        **V.mesh_convergence_verdict(table),
    }
    out["height"] = {}
    for bench in campaign.height_benchmarks:
        per_height: dict[str, list[V.RunResult]] = {}
        for spec in campaign.height_runs:
            if spec.benchmark == bench.name and spec.name in results:
                per_height.setdefault(f"{spec.cavity.d_mm:g}", []).append(results[spec.name])
        shift = V.height_shift(bench, per_height, decisions)
        shift["is_object001"] = bench.is_object001
        shift["label"] = ("Object 001 box (22 x 22 x 1.5 mm against 1.65 mm)" if bench.is_object001
                          else "AUXILIARY taller box (22 x 22 x 7.0 mm against 7.7 mm); not a verification of Object 001")
        out["height"][bench.name] = shift
    out["verdicts"] = {
        "mesh_convergence": out["mesh_convergence"]["verdict"],
        "height_sensitivity_aux": out["height"].get("aux_height", {}).get("verdict", V.INCOMPLETE),
        "height_sensitivity_object001": out["height"].get("object001_height", {}).get("verdict", V.INCOMPLETE),
    }
    return out


def _num(value, spec: str = ".2e") -> str:  # noqa: ANN001
    return "-" if value is None else format(value, spec)


def render_report(campaign: V.Campaign, summary: dict) -> str:
    L: list[str] = []
    L.append("# Palace mesh-refinement and height-sensitive verification\n")
    L.append(f"Campaign `{campaign.name}`, definition sha256 `{summary['campaign_sha256']}`; execution `{summary['execution']}`.\n")
    L.append(f"{campaign.statement}\n")
    v = summary["verdicts"]
    L.append("## Verdicts\n")
    L.append(f"- Mesh convergence (22 x 22 x 1.5 mm box): **{v['mesh_convergence']}**")
    L.append(f"- Height sensitivity, auxiliary 22 x 22 x 7.0/7.7 mm box (Z pipeline, not Object 001): **{v['height_sensitivity_aux']}**")
    L.append(f"- Height sensitivity, Object 001 box (1.5 mm against 1.65 mm): **{v['height_sensitivity_object001']}**\n")
    mc = summary["mesh_convergence"]
    L.append("## Objective 1: mesh convergence\n")
    L.append("Analytic (GHz): " + ", ".join(f"{f:.6f}" for f in mc["expected_analytic_GHz"]) + "\n")
    L.append("| run | status | lc (mm) | nodes | tets | DOF | f1..f4 (GHz) | max |rel analytic err| | max |rel change vs prev| | max bkwd err | Palace s |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for row in mc["table"]:
        fs = ", ".join(f"{f:.6f}" for f in row["frequencies_GHz"]) or "-"
        L.append(f"| {row['run']} | {row['status']} | {row['mesh_length_mm']:.4f} | {row['nodes']} | {row['tetrahedra']} | {row['dof']} | {fs} | "
                 f"{_num(row['max_abs_relative_analytic_error'])} | {_num(row['max_abs_relative_change_vs_previous_level'])} | "
                 f"{_num(row['backward_error_max'])} | {_num(row['palace_total_s'], '.1f')} |")
    L.append("\nDegenerate (1,2,0)/(2,1,0) pair (numerical splitting of an exact degeneracy, not physical coupling):\n")
    L.append("| run | mode a (GHz) | mode b (GHz) | centre (GHz) | splitting (MHz) | relative |")
    L.append("|---|---|---|---|---|---|")
    for row in mc["degenerate_pair"]:
        if "centre_GHz" in row:
            L.append(f"| {row['run']} | {row['mode_a_GHz']:.6f} | {row['mode_b_GHz']:.6f} | {row['centre_GHz']:.6f} | {row['splitting_MHz']:.3f} | {row['splitting_relative']:.2e} |")
        else:
            L.append(f"| {row['run']} | {row['status']} | | | | |")
    L.append("\n" + "; ".join(mc["reasons"]) + "\n")
    L.append("## Objective 2: height sensitivity (p >= 1 modes)\n")
    for name, h in summary["height"].items():
        L.append(f"### {name}: {h['label']}\n")
        L.append(f"Verdict **{h['verdict']}**. " + "; ".join(h.get("reasons", [])) + "\n")
        if "f_exact_GHz" in h:
            L.append(f"- mode {tuple(h['mode'])}, heights {h['heights_mm']} mm, exact f {h['f_exact_GHz']}, Δf_exact {h['delta_f_exact_GHz']:+.5f} GHz ({h['delta_f_exact_relative']:+.3%})")
        for lc, lv in h.get("levels", {}).items():
            L.append(f"- lc {lc} mm: f_Palace {[round(x, 6) for x in lv['f_palace_GHz']]} GHz, Δf_Palace {lv['delta_f_palace_GHz']:+.5f} GHz")
        if "relative_disagreement" in h:
            L.append(f"- finest level {h['finest_level_mm']:.4g} mm: Δf_Palace {h['delta_f_palace_GHz']:+.5f} vs Δf_exact {h['delta_f_exact_GHz']:+.5f} GHz, "
                     f"relative disagreement {h['relative_disagreement']:.3e}; numerical uncertainty {h['numerical_uncertainty_GHz']:.3e} GHz "
                     f"({h['uncertainty_source']}); |Δf_exact|/uncertainty = {h['shift_to_uncertainty_ratio']:.1f}")
        L.append("")
    L.append("## Runs\n")
    L.append("| run | role | status | lc (mm) | tets | DOF (est.) | DOF | Palace s | failure |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for spec in campaign.runs:
        r = summary["runs"].get(spec.name)
        if r is None:
            L.append(f"| {spec.name} | {spec.role} | not executed | {spec.mesh_length_mm:.4f} | | | | | |")
            continue
        failure = (r["failure"] or "")[:120].replace("|", "/")
        L.append(f"| {spec.name} | {spec.role} | {r['status']} | {r['mesh_length_mm']:.4f} | {r['tetrahedra']} | {r['dof_estimate']} | {r['dof']} | "
                 f"{_num(r['palace_total_s'], '.1f')} | {failure} |")
    L.append("\nEvery number above is a numerical-verification result for the empty PEC box. It says nothing about the physical package.\n")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--np", type=int, default=1, help="MPI processes")
    parser.add_argument("--results-root", default=str(REPO_ROOT / "results"))
    parser.add_argument("--record-pointer", default=None, metavar="FILE")
    parser.add_argument("--only", action="append", default=None, help="run only these run names (repeatable)")
    parser.add_argument("--prepare-only", action="store_true", help="mesh and estimate every run without launching Palace")
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc)
    campaign = V.build_campaign()
    candidate = load_golden()
    selected = [r for r in campaign.runs if not args.only or r.name in set(args.only)]
    if args.only:
        unknown = set(args.only) - {r.name for r in campaign.runs}
        if unknown:
            print(f"error: unknown run name(s) {sorted(unknown)}; known: {[r.name for r in campaign.runs]}", file=sys.stderr)
            return 2

    adapter = PalaceSolver(image=args.image, runtime=args.runtime, mpi_processes=args.np)
    provenance: dict = {}
    if not args.prepare_only:
        try:
            adapter.preflight()
        except SolverUnavailable as exc:
            print(f"\nPalace cannot execute here: {exc.reason}\n{exc}", file=sys.stderr)
            return 2
        provenance = adapter.provenance()
        print(f"image      : {args.image} id {provenance.get('image_id')}  palace {provenance.get('palace_version')} @ {provenance.get('palace_commit')}")

    batch = f"PALACE-VERIFY-{started.strftime('%Y%m%dT%H%M%SZ')}"
    root = Path(args.results_root) / batch
    root.mkdir(parents=True, exist_ok=False)
    (root / "campaign.json").write_text(_dump(campaign.as_dict()))
    (root / "campaign.sha256").write_text(f"{campaign.sha256()}  campaign.json\n")
    if args.record_pointer:
        Path(args.record_pointer).write_text(str(root) + "\n")
    print(f"record     : {root}\ncampaign   : {campaign.name} sha256 {campaign.sha256()[:16]}… ({len(selected)} of {len(campaign.runs)} runs)")

    results: dict[str, V.RunResult] = {}
    decisions: dict[str, list[dict]] = {}

    def write_record(final: bool) -> dict:
        ended = datetime.now(timezone.utc)
        summary = {
            "schema": V.SUMMARY_SCHEMA,
            "batch_id": batch,
            "campaign": campaign.name,
            "campaign_sha256": campaign.sha256(),
            "execution": "prepare-only" if args.prepare_only else "palace",
            "complete": final,
            "runs": {name: r.as_dict() for name, r in results.items()},
            "runs_selected": [r.name for r in selected],
            "solver_provenance": provenance,
            "started_utc": started.isoformat(),
            "ended_utc": ended.isoformat(),
            "statement": campaign.statement,
        }
        if args.prepare_only:
            summary["verdicts"] = {"mesh_convergence": "NOT-EVALUATED", "height_sensitivity_aux": "NOT-EVALUATED",
                                   "height_sensitivity_object001": "NOT-EVALUATED"}
            summary["mesh_convergence"] = {"expected_analytic_GHz": expected_solver_modes_GHz(campaign.object001.domain()),
                                           "table": [], "degenerate_pair": [], "verdict": "NOT-EVALUATED", "reasons": ["prepare-only"]}
            summary["height"] = {}
        else:
            summary.update(evaluate(campaign, results, decisions))
            env = environment.record(
                started_utc=started, solver_name="palace",
                solver_version=f"{provenance.get('palace_version')}+{str(provenance.get('palace_commit'))[:12]}",
                solver_identity=f"{args.image}@{provenance.get('image_id')}", ended_utc=ended,
            )
            summary["environment"] = env.model_dump(mode="json")
        (root / "summary.json").write_text(_dump(summary))
        (root / "report.md").write_text(render_report(campaign, summary))
        manifest.write(root)
        return summary

    for spec in selected:
        run_id = f"RUN-{batch}-{spec.name}"
        rr, dec = execute_run(adapter, candidate, spec, root / "runs" / spec.name, run_id, args.prepare_only)
        results[spec.name] = rr
        if dec is not None:
            decisions[spec.name] = dec
        write_record(final=False)

    summary = write_record(final=True)
    v = summary["verdicts"]
    print(f"\nverdicts   : mesh convergence {v['mesh_convergence']} | aux height {v['height_sensitivity_aux']} | "
          f"object001 height {v['height_sensitivity_object001']}")
    print(f"record     : {root}")
    if args.prepare_only:
        return 0 if all(r.status in ("PREPARED", "BLOCKED") for r in results.values()) else 3
    if V.FAIL in v.values():
        return 3
    if v["mesh_convergence"] != V.PASS or v["height_sensitivity_aux"] != V.PASS:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
