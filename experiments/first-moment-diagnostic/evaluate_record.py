#!/usr/bin/env python3
"""Evaluate a first-moment diagnostic record against the saved partial moment.

Two modes:

``--fixture``  builds a synthetic record from the reference model, in which the
               exact omitted first moment is KNOWN by construction, and checks
               that the evaluator recovers it within its own residual bound; it
               also exercises the three ways a record fails qualification. This
               is the only mode that runs in preparation.

``--record DIR``  evaluates a real record written by the patched Palace image
               (``DIR/postpro/first-moment.json``) against the all-nine saved
               moment recomputed from N2R's committed columns. No such record
               exists until the separately approved execution has run; the
               script refuses to invent one.

Offline. No network, no Palace, no FEM assembly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from reference_model import (  # noqa: E402
    Fixture, RNG_SEED, constrained_eigenbasis, evaluate, parseval_first_moment,
    restrict_to_free, synthetic_record, unit_scales,
)
import prepare  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_evaluation(seed: int = RNG_SEED) -> dict:
    rng = np.random.default_rng(seed)
    fx = Fixture(rng)
    Lc = 4.0e-3
    sc = unit_scales(Lc)
    f = restrict_to_free(fx.f_true, fx.dbc)
    lam, Em = constrained_eigenbasis(fx.K, fx.M, fx.dbc)
    q = f / np.sqrt(fx.L)
    weights = (q @ Em) ** 2                              # (q^H E_m)^2 per mode
    A_total_nd, _ = parseval_first_moment(f, fx.L, lam, Em)
    # 'saved' modes: the heaviest half by weight; the omitted moment is exact by construction
    order = np.argsort(weights)[::-1]
    saved = order[: len(order) // 2]
    A_saved_nd = float(weights[saved].sum())
    omitted_exact_nd = A_total_nd - A_saved_nd
    A_saved_GHz2 = A_saved_nd * sc["A_GHz2_per_nd"]

    rec = synthetic_record(fx, Lc, residual_scale=1e-13, seed=seed)
    good = evaluate(rec, A_saved_GHz2, expected_dofs=fx.n_true,
                    expected_L_H=fx.L * sc["InductanceScale_H"],
                    hashes={"fixture": "synthetic"})
    diff = good["difference"]["A_direct_minus_A_saved_nd"]
    bound = good["numerical_qualification"]["residual_bound_GHz2"] / sc["A_GHz2_per_nd"]
    broken = {}
    for what in ("functional", "null_space", "convergence"):
        r = evaluate(synthetic_record(fx, Lc, residual_scale=1e-13, seed=seed, break_check=what),
                     A_saved_GHz2, expected_dofs=fx.n_true)
        broken[what] = {"all_checks_passed": r["all_checks_passed"],
                        "interpretation": r["interpretation"],
                        "failed": [c["check"] for c in r["checks"] if not c["passed"]]}
    # a sloppy solve: the difference must then be qualified by a bound it cannot beat
    sloppy = evaluate(synthetic_record(fx, Lc, residual_scale=1e-6, seed=seed), A_saved_GHz2,
                      expected_dofs=fx.n_true)
    return {
        "label": "FIXTURE EVALUATION - THE EVALUATOR RECOVERS A KNOWN OMITTED MOMENT",
        "fixture": {"n_true": fx.n_true, "n_essential": int(len(fx.dbc)),
                    "n_modes_total": int(len(lam)), "n_modes_saved": int(len(saved))},
        "truth": {"A_total_nd": A_total_nd, "A_saved_nd": A_saved_nd,
                  "omitted_first_moment_exact_nd": omitted_exact_nd},
        "evaluator": {"A_direct_minus_A_saved_nd": diff, "residual_bound_nd": bound,
                      "error_vs_truth_nd": diff - omitted_exact_nd,
                      "error_within_bound": abs(diff - omitted_exact_nd) <= bound,
                      "difference_exceeds_bound": good["numerical_qualification"]["difference_exceeds_residual_bound"],
                      "all_checks_passed": good["all_checks_passed"],
                      "interpretation": good["interpretation"]},
        "broken_records_are_unqualified": broken,
        "sloppy_solve": {"relative_residual": 1e-6,
                         "all_checks_passed": sloppy["all_checks_passed"],
                         "failed": [c["check"] for c in sloppy["checks"] if not c["passed"]],
                         "interpretation": sloppy["interpretation"]},
        "full_evaluation_of_the_good_record": good,
    }


def record_evaluation(record_dir: Path) -> dict:
    rec_path = record_dir / "postpro" / "first-moment.json"
    if not rec_path.is_file():
        rec_path = record_dir / "first-moment.json"
    if not rec_path.is_file():
        raise SystemExit(f"no first-moment.json under {record_dir}: nothing has been executed")
    rec = json.loads(rec_path.read_text())
    scales = prepare.scales_from_log()
    tc = rec["Scales"]["tc_ns"]
    saved = prepare.saved_moments(tc)
    hashes = {
        "record": sha256(rec_path),
        "config_candidate": sha256(HERE / "config.candidate.json"),
        "mesh": prepare.N2R_MESH_SHA256,
        "patch": sha256(prepare.PATCH),
        "dockerfile": sha256(prepare.DOCKERFILE),
        "code": {n: sha256(HERE / n) for n in ("reference_model.py", "prepare.py", "evaluate_record.py")},
    }
    for name in ("config.json", "palace_log.txt"):
        p = record_dir / name
        if p.is_file():
            hashes[name] = sha256(p)
    all_nine = saved["A_all_saved_modes"]["A_partial_GHz2"]
    result = evaluate(rec, all_nine, expected_dofs=prepare.N2R_TRUE_DOFS,
                      expected_L_H=prepare.N2R_PORT_L_H, hashes=hashes)
    result["A_saved_variants"] = saved
    result["expected_scales"] = scales
    result["comparison_scope"] = (
        "A_saved sums the nine saved N2R eigenpairs; A_direct is the moment over the whole "
        "constrained space; their difference is the moment carried by everything the "
        "eigensolver did not return, subject to the checks above"
    )
    return result


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--fixture", action="store_true")
    g.add_argument("--record", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if args.fixture:
        result = fixture_evaluation()
        out = args.out or (HERE / "fixture_evaluation.json")
    else:
        result = record_evaluation(args.record)
        out = args.out or (args.record / "first-moment-evaluation.json")
    out.write_text(json.dumps(result, indent=1) + "\n")
    print(result["label"] if "label" in result else result["interpretation"])
    if args.fixture:
        ev = result["evaluator"]
        print(f"  omitted exact {result['truth']['omitted_first_moment_exact_nd']:.12e}")
        print(f"  evaluator     {ev['A_direct_minus_A_saved_nd']:.12e}  bound {ev['residual_bound_nd']:.3e}  "
              f"within bound: {ev['error_within_bound']}")
        for k, v in result["broken_records_are_unqualified"].items():
            print(f"  broken {k:<12} passed={v['all_checks_passed']} failed={v['failed']}")
        print(f"  sloppy solve  passed={result['sloppy_solve']['all_checks_passed']} failed={result['sloppy_solve']['failed']}")


if __name__ == "__main__":
    main()
