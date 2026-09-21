#!/usr/bin/env python3
"""Run the SYNTHETIC fixtures through the COMPILED first-moment diagnostic.

This is the only script here that executes a solver, and it refuses to execute anything
but the synthetic fixtures: every config it is given must live in ``fixtures/`` and name
the synthetic mesh. No QMHP mesh, config or committed result can be reached through it,
and it computes no physical E_C or g.

It checks, against the compiled binary:
  * GetVoltageFunctional versus GetVoltage (the driver's own check, reported in the record)
  * PEC restriction (the functional's essential-dof norm is nonzero and the solution's is 0)
  * DIAG_ONE padding and the mass solve, against the INDEPENDENT answer assembled in
    synthetic_fixture.py from the Whitney element formulas
  * the exact 1/L scaling of A between two fixtures
  * the internal unit conversions (Lc, tc, A_GHz2) against the record's own scales
  * finite JSON output
  * non-convergence handling and failed-check handling, including that a failed check
    writes structured FAILED evidence and NO first-moment.json
  * preservation of the log in every case
  * optionally, a fault-injected binary, to show the functional check actually catches a
    broken functional rather than passing vacuously

Run it with --palace pointing at a compiled palace wrapper. It is not run by the test
suite, which checks its refusals instead.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE_DIR = HERE / "fixtures"
sys.path.insert(0, str(HERE))
import synthetic_fixture as sf  # noqa: E402

SYNTHETIC_MESH = "fm_synthetic.msh"
RUN_TIMEOUT_S = 600


class Refusal(RuntimeError):
    pass


def assert_synthetic(config_path: Path) -> dict:
    """Refuse anything that is not one of this directory's synthetic fixtures."""
    config_path = Path(config_path).resolve()
    if config_path.parent != FIXTURE_DIR.resolve():
        raise Refusal(f"{config_path} is not in {FIXTURE_DIR}: only synthetic fixtures run")
    cfg = json.loads(config_path.read_text())
    if cfg.get("Model", {}).get("Mesh") != SYNTHETIC_MESH:
        raise Refusal(f"{config_path} does not name the synthetic mesh {SYNTHETIC_MESH}")
    return cfg


def run_fixture(palace: Path, config_path: Path, workdir: Path, *,
                info_dir: Path | None = None, np_processes: int = 1) -> dict:
    """One compiled run of one synthetic fixture. Returns what it produced."""
    assert_synthetic(config_path)
    workdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(config_path, workdir / "config.json")
    shutil.copy2(FIXTURE_DIR / SYNTHETIC_MESH, workdir / SYNTHETIC_MESH)
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               OMPI_ALLOW_RUN_AS_ROOT="1", OMPI_ALLOW_RUN_AS_ROOT_CONFIRM="1")
    if info_dir:
        env["PALACE_IMAGE_INFO_DIR"] = str(info_dir)
    argv = ([str(palace), "--serial", "config.json"] if np_processes == 1
            else [str(palace), "-np", str(np_processes), "config.json"])
    t0 = time.perf_counter()
    proc = subprocess.run(argv, cwd=workdir, env=env, capture_output=True, text=True,
                          timeout=RUN_TIMEOUT_S)
    wall = time.perf_counter() - t0
    log = proc.stdout + proc.stderr
    (workdir / "palace_log.txt").write_text(log)
    post = workdir / "postpro"
    ok, failed = post / "first-moment.json", post / "first-moment-FAILED.json"
    return {
        "returncode": proc.returncode,
        "wall_s": wall,
        "log_bytes": len(log),
        "log_preserved": (workdir / "palace_log.txt").is_file() and len(log) > 0,
        "record": json.loads(ok.read_text()) if ok.is_file() else None,
        "failed_record": json.loads(failed.read_text()) if failed.is_file() else None,
        "wrote_first_moment_json": ok.is_file(),
        "log_tail": log.strip().splitlines()[-6:],
    }


def _finite(obj) -> bool:
    if isinstance(obj, dict):
        return all(_finite(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_finite(v) for v in obj)
    if isinstance(obj, bool):
        return True
    if isinstance(obj, (int, float)):
        return math.isfinite(obj)
    return True


def qualify(palace: Path, *, info_dir: Path | None, workroot: Path,
            faulted_palace: Path | None = None,
            mpi_ranks: tuple[int, ...] = (1, 2, 3, 4)) -> dict:
    fixtures = json.loads((HERE / "synthetic_fixture.json").read_text())
    out = {"label": "COMPILED FIRST-MOMENT DIAGNOSTIC - SYNTHETIC QUALIFICATION",
           "palace": str(palace), "image_info_dir": str(info_dir) if info_dir else None,
           "synthetic_only": ("every config is a fixture in experiments/first-moment-"
                              "diagnostic/fixtures naming " + SYNTHETIC_MESH),
           "runs": {}}
    for name, spec in fixtures["fixtures"].items():
        cfg = FIXTURE_DIR / spec["config"]
        res = run_fixture(palace, cfg, workroot / name, info_dir=info_dir)
        entry = {"purpose": spec["purpose"], "returncode": res["returncode"],
                 "wall_s": res["wall_s"], "log_preserved": res["log_preserved"],
                 "wrote_first_moment_json": res["wrote_first_moment_json"]}
        rec = res["record"]
        if rec:
            A = rec["A"]
            ls, sc = rec["LinearSolve"], rec["Scales"]
            entry.update({
                "A_nd": A["A_nd"], "A_GHz2": A["A_GHz2"],
                "certified_lower_bound_A_nd": A["CertifiedLowerBound_A_nd"],
                "x_dot_r_nd": A["XDotR_nd"],
                "certified_upper_bound": A["CertifiedUpperBound"],
                "converged": ls["Converged"], "iterations": ls["Iterations"],
                "relative_residual": ls["RelativeResidual"],
                "solution_essential_norm": ls["SolutionEssentialNorm"],
                "functional_check_relative_error":
                    rec["Functional"]["Check"]["RelativeError"],
                "functional_check_passed": rec["Functional"]["Check"]["Passed"],
                "functional_norm2_essential": rec["Functional"]["NormSquaredEssential"],
                "null_space_min_gap": rec["NullSpaceCheck"].get("MinRelativeGap"),
                "null_space_is_sampled_not_proof":
                    rec["NullSpaceCheck"].get("IsSampledNotProof"),
                "dofs": rec["Dofs"], "scales": sc,
                "provenance": rec["Provenance"],
                "json_is_finite": _finite(rec),
            })
            ind = spec.get("independent")
            if ind:
                entry["independent_A_nd"] = ind["A_nd"]
                entry["relative_error_vs_independent"] = (
                    abs(A["A_nd"] - ind["A_nd"]) / abs(ind["A_nd"]))
                entry["independent_free_dofs"] = ind["n_edges_free"]
                entry["dof_counts_agree"] = (rec["Dofs"]["Free"] == ind["n_edges_free"]
                                             and rec["Dofs"]["True"] == ind["n_edges_total"])
                entry["Lc_agrees"] = abs(sc["Lc_m"] - ind["Lc_m"]) <= 1e-12 * ind["Lc_m"]
                entry["tc_agrees"] = abs(sc["tc_ns"] - ind["tc_ns"]) <= 1e-12 * ind["tc_ns"]
                entry["A_GHz2_conversion_consistent"] = (
                    abs(A["A_GHz2"] - A["A_nd"] * sc["A_GHz2_per_nd"])
                    <= 1e-12 * abs(A["A_GHz2"]))
                lam_min = ind["lambda_min_M_free"]
                needed = (ls["ResidualNorm"] / ls["SolutionNorm"]) if ls["SolutionNorm"] else None
                entry["estimate_is_a_bound_here"] = (
                    needed is not None and lam_min >= needed)
                # The certified one-sided bound, checked against a KNOWN exact answer:
                # A_exact >= A_computed - Re(x^H r)/L must hold even when the solve is
                # deliberately stopped after one iteration.
                entry["certified_lower_bound_holds_vs_independent"] = (
                    A["CertifiedLowerBound_A_nd"] <= ind["A_nd"] * (1.0 + 1e-12))
                entry["shortfall_of_A_below_independent_nd"] = ind["A_nd"] - A["A_nd"]
                entry["unconverged_solve_underestimates_A"] = A["A_nd"] <= ind["A_nd"] * (
                    1.0 + 1e-12)
                entry["lambda_min_M_free_independent"] = lam_min
                entry["cond_M_free_independent"] = ind["cond_M_free"]
        if res["failed_record"]:
            entry["failed_record"] = {k: res["failed_record"][k]
                                      for k in ("Status", "Reason") if k in res["failed_record"]}
            entry["failed_record_has_provenance"] = "Provenance" in res["failed_record"]
        entry["log_tail"] = res["log_tail"]
        out["runs"][name] = entry

    a, b = out["runs"].get("A-nominal", {}), out["runs"].get("B-scaled-L", {})
    if "A_nd" in a and "A_nd" in b:
        ratio = a["A_nd"] / b["A_nd"]
        expected = (fixtures["fixtures"]["B-scaled-L"]["L_H"]
                    / fixtures["fixtures"]["A-nominal"]["L_H"])
        out["L_scaling"] = {"ratio": ratio, "expected": expected,
                            "relative_error": abs(ratio - expected) / expected}
    # The parallel path, and whether the functional check actually falsifies a broken
    # dual assembly. The fault is the realistic one: take the leading GetTrueVSize entries
    # of the LOCAL linear form instead of P^T v.
    if mpi_ranks:
        cfg = FIXTURE_DIR / "config-A-nominal.json"
        ind = fixtures["fixtures"]["A-nominal"]["independent"]
        sweep = {}
        for nproc in mpi_ranks:
            row = {}
            for kind, binary in (("good", palace), ("faulted", faulted_palace)):
                if binary is None:
                    continue
                res = run_fixture(binary, cfg, workroot / f"mpi-{kind}-{nproc}",
                                  info_dir=info_dir, np_processes=nproc)
                rec = res["record"]
                row[kind] = {
                    "returncode": res["returncode"],
                    "aborted": res["returncode"] != 0,
                    "wrote_first_moment_json": res["wrote_first_moment_json"],
                    "log_preserved": res["log_preserved"],
                    "A_nd": rec["A"]["A_nd"] if rec else None,
                    "functional_check_relative_error":
                        rec["Functional"]["Check"]["RelativeError"] if rec else None,
                    "mpi_size": rec["Provenance"]["MpiSize"] if rec else None,
                    "failed_reason": (res["failed_record"] or {}).get("Reason"),
                }
                if rec:
                    row[kind]["relative_error_vs_independent"] = (
                        abs(rec["A"]["A_nd"] - ind["A_nd"]) / abs(ind["A_nd"]))
            sweep[f"np={nproc}"] = row
        out["mpi_sweep"] = sweep
        if faulted_palace:
            caught = [k for k, v in sweep.items()
                      if v.get("faulted", {}).get("aborted")]
            silent = [k for k, v in sweep.items()
                      if "faulted" in v and not v["faulted"]["aborted"]]
            out["fault_injection"] = {
                "what": ("a binary rebuilt with GetVoltageFunctional taking the leading "
                         "GetTrueVSize entries of the LOCAL linear form instead of the "
                         "dual assembly P^T v"),
                "caught_at": caught,
                "not_caught_at": silent,
                "reading": (
                    "the functional check is NOT vacuous: at np=4 the faulted binary "
                    "aborts with structured FAILED evidence and writes no result. At "
                    "np=1..3 on this fixture the two expressions coincide - the leading "
                    "true-dof entries of the local form happen to equal P^T v for that "
                    "partitioning - so the check is silent there. That is a limit of the "
                    "fixture, not a pass: this fixture cannot falsify a dual-assembly "
                    "error below four ranks."),
                "good_binary_agrees_across_ranks": len({
                    round(v["good"]["A_nd"], 12) for v in sweep.values()
                    if v.get("good", {}).get("A_nd") is not None}) == 1,
            }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--palace", type=Path, required=True)
    ap.add_argument("--faulted-palace", type=Path)
    ap.add_argument("--image-info-dir", type=Path)
    ap.add_argument("--workroot", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=HERE / "compiled_qualification.json")
    args = ap.parse_args(argv)
    out = qualify(args.palace, info_dir=args.image_info_dir, workroot=args.workroot,
                  faulted_palace=args.faulted_palace)
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    print(out["label"])
    for name, r in out["runs"].items():
        if "A_nd" in r:
            print(f"  {name:<16} A_nd={r['A_nd']:.12e}  vs independent "
                  f"{r.get('relative_error_vs_independent', float('nan')):.3e}  "
                  f"converged={r['converged']}  relres={r['relative_residual']:.2e}")
        else:
            print(f"  {name:<16} rc={r['returncode']} wrote_json={r['wrote_first_moment_json']} "
                  f"failed_record={r.get('failed_record')}")
    if "L_scaling" in out:
        print(f"  L scaling ratio {out['L_scaling']['ratio']:.12f} "
              f"(expected {out['L_scaling']['expected']}, "
              f"rel err {out['L_scaling']['relative_error']:.2e})")
    for nproc, row in out.get("mpi_sweep", {}).items():
        g = row.get("good", {})
        f_ = row.get("faulted", {})
        print(f"  {nproc:<8} good A_nd={g.get('A_nd')}  faulted aborted={f_.get('aborted')}"
              f" reason={f_.get('failed_reason')}")
    if "fault_injection" in out:
        fi = out["fault_injection"]
        print(f"  fault injection caught at {fi['caught_at']}, silent at {fi['not_caught_at']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
