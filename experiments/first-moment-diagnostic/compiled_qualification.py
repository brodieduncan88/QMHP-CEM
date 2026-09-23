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

It then DECIDES, and exits nonzero when the image did not qualify. Collecting fixture
results is not qualifying an image: see ``decide`` below for the criteria, every one of
which is declared elsewhere in this repository and cited there.

Run it with --palace pointing at a compiled palace wrapper. It is not run by the test
suite, which checks its refusals and its decision instead.
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
import reference_model as rm  # noqa: E402
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
        if rec is not None:
            # The DECLARED record schema, reference_model.RECORD_KEYS. A record missing a
            # declared key is incomplete evidence, not a result: it is recorded as such and
            # its numbers are not read, so a truncated record reaches the decision below as
            # a refusal instead of as a KeyError traceback.
            entry["record_schema_missing"] = rm.validate_record(rec)
        if rec and not entry["record_schema_missing"]:
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


# --- the qualification DECISION -------------------------------------------------------
#
# Collecting fixture results and printing them is not qualifying an image. Until this
# block existed ``main`` returned 0 whatever the fixtures did, so the workflow step that
# runs this command read "the command succeeded" as "the image qualified" - and a wrong
# A, a crashed fixture, a fixture that wrote no record at all, a failed functional check
# and a developer-build provenance every one of them exited 0.
#
# NOTHING BELOW IS A NEW TOLERANCE. Every threshold and every expected outcome is
# already declared in this repository, and is cited where it is used:
#
#   tests/test_first_moment_diagnostic.py
#     test_the_compiled_diagnostic_matches_an_independent_assembly
#     test_the_compiled_diagnostic_handles_non_convergence_and_failed_checks
#     test_the_functional_check_is_not_vacuous_and_its_limit_is_stated
#   experiments/first-moment-diagnostic/synthetic_fixture.json   the fixture set, each
#     fixture's `purpose` and its `independent` block
#   experiments/first-moment-diagnostic/proposal.json            required_provenance
#   reference_model.RECORD_KEYS / reference_model.evaluate       the record schema and
#     the "not a developer build" provenance check, by the same predicate
#
# Where a quantity has NO declared criterion it is listed under `undeclared_criteria`
# and is reported rather than silently given one.

#: A against the independent Whitney assembly, and the exact 1/L scaling.
REL_TO_INDEPENDENT = 1e-12          # test_..._matches_an_independent_assembly
L_SCALING_REL = 1e-12               # test_..._matches_an_independent_assembly
#: the driver's own functional-vs-GetVoltage check, as the suite bounds it.
FUNCTIONAL_CHECK_REL = 1e-10        # test_..._matches_an_independent_assembly
#: the non-convergence fixture must be visibly unconverged, not marginally so.
NONCONVERGENCE_RELRES = 1e-3        # test_..._handles_non_convergence_and_failed_checks
#: the parallel path the qualification must cover.
REQUIRED_MPI_RANKS = (1, 2, 3, 4)   # test_..._functional_check_is_not_vacuous..., and
                                    # docs/coupled-candidate/first-moment-diagnostic.md
#: the in-image identity a record must carry, read from the committed proposal rather
#: than retyped here.
IN_IMAGE_IDENTITY_KEYS = ("PALACE_VERSION", "PALACE_COMMIT", "PALACE_PATCH",
                          "PALACE_PATCH_SHA256")

#: Which declared fixture must do what. A fixture declared in synthetic_fixture.json but
#: absent from these three groups has no declared expected outcome, and that is itself a
#: refusal rather than a silent pass.
MUST_SUCCEED = ("A-nominal", "B-scaled-L")          # purpose: the full path; 1/L scaling
MUST_NOT_CONVERGE = ("C-maxits-1",)                 # purpose: "the record must say so"
MUST_FAIL_CLOSED = ("D-port-inactive",)             # purpose: structured FAILED evidence


def _num(value) -> float | None:
    """A finite number, or None. Keeps a missing or NaN field from passing a comparison."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _want(checks: list, name: str, passed, detail=None) -> bool:
    checks.append({"check": name, "passed": bool(passed), "detail": detail})
    return bool(passed)


def _common(checks: list, who: str, e: dict, *, expect_returncode_zero: bool) -> None:
    """What every fixture owes whatever its intended outcome: a preserved log, a record
    that matches the declared schema if one was written, and the exit status its purpose
    calls for. An arbitrary crash fails here; an intended failure does not."""
    _want(checks, f"{who}: the log was preserved", e.get("log_preserved") is True,
          {"log_preserved": e.get("log_preserved")})
    _want(checks, f"{who}: the record matches the declared schema",
          not e.get("record_schema_missing"),
          {"missing": e.get("record_schema_missing")})
    rc = e.get("returncode")
    if expect_returncode_zero:
        _want(checks, f"{who}: exited 0", rc == 0, {"returncode": rc})
    else:
        _want(checks, f"{who}: exited nonzero, as its declared purpose requires", rc not in (0, None),
              {"returncode": rc})


def decide(report: dict, *, require_in_image_identity: bool = True) -> dict:
    """Decide whether this report qualifies the thing that produced it.

    ``require_in_image_identity`` is a keyword, not a command-line flag, and defaults to
    requiring it: this command exists to qualify an IMAGE, and a run whose record says it
    read its identity files from somewhere other than the in-image /opt/palace is a
    developer build. The historical NATIVE qualification record is such a run; the test
    suite passes False to evaluate it on its own terms and True to show the requirement
    bites. There is deliberately no way to relax it from the command line.
    """
    checks: list = []
    undeclared = [
        "the Reason text of an intended FAILED record: the suite declares Status == "
        "'FAILED' and the presence of provenance, but no criterion declares the wording, "
        "so the observed reason is reported and not gated",
        "a wall-clock or memory budget per fixture: Resources.WallTime_s and MaxRSS_MB "
        "are recorded by the driver but no criterion declares a limit, so neither is gated",
    ]
    not_established: list = []

    runs = report.get("runs")
    if not isinstance(runs, dict) or not runs:
        return {"label": "QUALIFICATION DECISION", "qualified": False,
                "decision": "NOT QUALIFIED",
                "checks": [{"check": "the report carries a runs block", "passed": False,
                            "detail": {"runs": type(runs).__name__}}],
                "failed": ["the report carries a runs block"],
                "coverage": {}, "not_established": ["nothing: the report is malformed"],
                "undeclared_criteria": undeclared}

    declared = json.loads((HERE / "synthetic_fixture.json").read_text())["fixtures"]
    classified = MUST_SUCCEED + MUST_NOT_CONVERGE + MUST_FAIL_CLOSED
    missing_runs = [n for n in declared if n not in runs]
    _want(checks, "every declared fixture ran", not missing_runs, {"missing": missing_runs})
    unclassified = [n for n in declared if n not in classified]
    _want(checks, "every declared fixture has a declared expected outcome",
          not unclassified, {"no declared outcome for": unclassified})

    # --- the fixtures that must simply work ---
    for who in MUST_SUCCEED:
        e = runs.get(who) or {}
        _common(checks, who, e, expect_returncode_zero=True)
        _want(checks, f"{who}: wrote a first-moment record",
              e.get("wrote_first_moment_json") is True,
              {"wrote_first_moment_json": e.get("wrote_first_moment_json")})
        _want(checks, f"{who}: the record is finite", e.get("json_is_finite") is True)
        _want(checks, f"{who}: the solve converged", e.get("converged") is True,
              {"converged": e.get("converged"), "iterations": e.get("iterations")})
        rel = _num(e.get("relative_error_vs_independent"))
        _want(checks, f"{who}: A agrees with the independent assembly to "
                      f"{REL_TO_INDEPENDENT:g}",
              rel is not None and rel < REL_TO_INDEPENDENT, {"relative_error": rel})
        _want(checks, f"{who}: dof counts, Lc, tc and the A_GHz2 conversion agree",
              all(e.get(k) is True for k in ("dof_counts_agree", "Lc_agrees", "tc_agrees",
                                             "A_GHz2_conversion_consistent")),
              {k: e.get(k) for k in ("dof_counts_agree", "Lc_agrees", "tc_agrees",
                                     "A_GHz2_conversion_consistent")})
        fc = _num(e.get("functional_check_relative_error"))
        _want(checks, f"{who}: the functional check passed within "
                      f"{FUNCTIONAL_CHECK_REL:g}",
              e.get("functional_check_passed") is True and fc is not None
              and fc <= FUNCTIONAL_CHECK_REL,
              {"passed": e.get("functional_check_passed"), "relative_error": fc})
        ess = _num(e.get("functional_norm2_essential"))
        _want(checks, f"{who}: the PEC restriction bites",
              ess is not None and ess > 0 and e.get("solution_essential_norm") == 0.0,
              {"functional_norm2_essential": ess,
               "solution_essential_norm": e.get("solution_essential_norm")})
        gap = _num(e.get("null_space_min_gap"))
        _want(checks, f"{who}: the sampled null-space check is positive and is reported "
                      f"as sampled, not proof",
              gap is not None and gap > 0
              and e.get("null_space_is_sampled_not_proof") is True,
              {"min_gap": gap,
               "is_sampled_not_proof": e.get("null_space_is_sampled_not_proof")})
        _want(checks, f"{who}: the certified lower bound holds against the known answer",
              e.get("certified_lower_bound_holds_vs_independent") is True)

    # --- the fixture whose declared purpose is NOT to converge ---
    for who in MUST_NOT_CONVERGE:
        e = runs.get(who) or {}
        _common(checks, who, e, expect_returncode_zero=True)
        _want(checks, f"{who}: wrote a first-moment record",
              e.get("wrote_first_moment_json") is True)
        _want(checks, f"{who}: the record is finite", e.get("json_is_finite") is True)
        relres = _num(e.get("relative_residual"))
        _want(checks, f"{who}: the record SAYS it did not converge, and visibly so "
                      f"(relative residual > {NONCONVERGENCE_RELRES:g})",
              e.get("converged") is False and relres is not None
              and relres > NONCONVERGENCE_RELRES,
              {"converged": e.get("converged"), "relative_residual": relres})
        short = _num(e.get("shortfall_of_A_below_independent_nd"))
        _want(checks, f"{who}: the under-converged solve UNDERESTIMATES A and its "
                      f"certified lower bound still holds",
              e.get("unconverged_solve_underestimates_A") is True and short is not None
              and short > 0 and e.get("certified_lower_bound_holds_vs_independent") is True,
              {"shortfall_nd": short})
        _want(checks, f"{who}: the uncertified estimate is shown NOT to be a bound here",
              e.get("estimate_is_a_bound_here") is False,
              {"estimate_is_a_bound_here": e.get("estimate_is_a_bound_here")})

    # --- the fixture whose declared purpose is to fail closed ---
    #
    # An intended failure is not a qualification failure. An ARBITRARY crash is not the
    # intended negative result either: it exits nonzero and writes no structured
    # evidence, so it fails the three checks below and refuses.
    for who in MUST_FAIL_CLOSED:
        e = runs.get(who) or {}
        _common(checks, who, e, expect_returncode_zero=False)
        _want(checks, f"{who}: wrote NO first-moment record",
              e.get("wrote_first_moment_json") is False,
              {"wrote_first_moment_json": e.get("wrote_first_moment_json")})
        failed = e.get("failed_record") or {}
        _want(checks, f"{who}: wrote structured FAILED evidence, with provenance",
              failed.get("Status") == "FAILED" and bool(failed.get("Reason"))
              and e.get("failed_record_has_provenance") is True,
              {"failed_record": failed or None,
               "has_provenance": e.get("failed_record_has_provenance")})

    # --- the exact 1/L scaling between the two nominal fixtures ---
    ls = report.get("L_scaling") or {}
    ls_rel = _num(ls.get("relative_error"))
    _want(checks, f"A scales exactly as 1/L, to {L_SCALING_REL:g}",
          ls_rel is not None and ls_rel < L_SCALING_REL,
          {"ratio": ls.get("ratio"), "expected": ls.get("expected"),
           "relative_error": ls_rel})

    # --- the parallel path ---
    sweep = report.get("mpi_sweep") or {}
    ran_ranks = sorted(int(k.split("=")[1]) for k in sweep if k.startswith("np="))
    _want(checks, f"the parallel path covers {list(REQUIRED_MPI_RANKS)} ranks",
          all(n in ran_ranks for n in REQUIRED_MPI_RANKS), {"ranks_run": ran_ranks})
    good_A = []
    for n in REQUIRED_MPI_RANKS:
        row = (sweep.get(f"np={n}") or {}).get("good") or {}
        rel = _num(row.get("relative_error_vs_independent"))
        _want(checks, f"np={n}: the good binary ran, wrote a record and agrees with the "
                      f"independent assembly to {REL_TO_INDEPENDENT:g}",
              row.get("returncode") == 0 and row.get("wrote_first_moment_json") is True
              and row.get("log_preserved") is True and row.get("mpi_size") == n
              and rel is not None and rel < REL_TO_INDEPENDENT,
              {"returncode": row.get("returncode"), "mpi_size": row.get("mpi_size"),
               "relative_error": rel})
        if _num(row.get("A_nd")) is not None:
            good_A.append(round(float(row["A_nd"]), 12))
    # the same expression qualify() uses for the same claim
    _want(checks, "the good binary agrees across ranks",
          len(good_A) == len(REQUIRED_MPI_RANKS) and len(set(good_A)) == 1,
          {"distinct_A_nd": sorted(set(good_A))})

    # --- fault injection: claimed ONLY if it actually ran ---
    fi = report.get("fault_injection")
    if fi is None:
        coverage_fi = ("NOT RUN: --faulted-palace was not supplied, so this qualification "
                       "establishes nothing about whether the functional check is vacuous")
        not_established.append(coverage_fi)
    else:
        coverage_fi = "RAN"
        _want(checks, "fault injection is caught at np=4 and its limit is stated",
              fi.get("caught_at") == ["np=4"]
              and fi.get("not_caught_at") == ["np=1", "np=2", "np=3"]
              and "limit of the fixture, not a pass" in str(fi.get("reading", "")),
              {"caught_at": fi.get("caught_at"), "not_caught_at": fi.get("not_caught_at")})

    # --- the in-image identity every record must carry ---
    required = json.loads((HERE / "proposal.json").read_text())
    required = required["the_one_execution"]["required_provenance"]
    provs = {who: (runs.get(who) or {}).get("provenance") for who in
             MUST_SUCCEED + MUST_NOT_CONVERGE}
    for who, prov in provs.items():
        prov = prov or {}
        mismatched = {k: {"record": prov.get(k), "required": required[k]}
                      for k in IN_IMAGE_IDENTITY_KEYS if prov.get(k) != required[k]}
        _want(checks, f"{who}: the record carries the reviewed Palace identity",
              bool(prov) and not mismatched, mismatched or None)
        if require_in_image_identity:
            # the same predicate reference_model.evaluate uses for the same claim
            _want(checks, f"{who}: the run read its identity from the in-image "
                          f"/opt/palace, not a developer build",
                  prov.get("ImageInfoDirIsDefault") is True,
                  {"ImageInfoDir": prov.get("ImageInfoDir"),
                   "ImageInfoDirIsDefault": prov.get("ImageInfoDirIsDefault")})
    if not require_in_image_identity:
        not_established.append(
            "that the qualified binary came from the image: require_in_image_identity "
            "was False, so ImageInfoDirIsDefault was not required")

    failed = [c["check"] for c in checks if not c["passed"]]
    return {
        "label": "QUALIFICATION DECISION",
        "qualified": not failed,
        "decision": "QUALIFIED" if not failed else "NOT QUALIFIED",
        "checks": checks,
        "failed": failed,
        "coverage": {
            "fixtures_declared": sorted(declared),
            "fixtures_run": sorted(runs),
            "mpi_ranks_required": list(REQUIRED_MPI_RANKS),
            "mpi_ranks_run": ran_ranks,
            "fault_injection": coverage_fi,
            "in_image_identity_required": require_in_image_identity,
        },
        "not_established": not_established,
        "undeclared_criteria": undeclared,
    }


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
    # Evidence before presentation: the collected report is written BEFORE the decision is
    # computed, so a defect in deciding cannot destroy the fixtures' results. It is then
    # rewritten with the decision embedded.
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    out["decision"] = decide(out)
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
    d = out["decision"]
    print(f"  DECISION  {d['decision']}")
    for name in d["failed"]:
        print(f"    FAILED          {name}")
    for line in d["not_established"]:
        print(f"    NOT ESTABLISHED {line}")
    # The exit status IS the verdict. A caller that only checks "did the command run"
    # now learns the answer, which is the whole point of this block.
    return 0 if d["qualified"] else 1


if __name__ == "__main__":
    sys.exit(main())
