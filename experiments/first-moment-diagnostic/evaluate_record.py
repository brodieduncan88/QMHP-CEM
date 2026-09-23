#!/usr/bin/env python3
"""Evaluate a first-moment diagnostic record, fail closed.

``--fixture``  builds synthetic records from the reference model, in which the omitted
               first moment is KNOWN by construction, and checks that the evaluator
               recovers it, refuses every spoiled record, and reaches the right verdict
               for a negative discrepancy. This is the only mode that runs in preparation.

``--record DIR``  evaluates a record written by the patched Palace (DIR/postpro/
               first-moment.json) together with the launcher's DIR/provenance.json. Every
               required provenance field must be present AND match; anything missing or
               mismatched prevents qualification. No such record exists until the
               separately approved execution has run, and this script never invents one.

               The EXPECTED image ID comes from DIR/approval-snapshot.json - the exact
               approval bytes the launcher froze beside the record - and never from the
               launcher's own provenance, which would compare a field with itself, and
               never from the live EXECUTION-APPROVAL.json, which can be written, edited
               or deleted after the run. A missing, undigested or altered snapshot
               prevents qualification; nothing is ever filled in from what was observed.

Offline. No network, no Palace, no FEM assembly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from reference_model import (  # noqa: E402
    Fixture, RNG_SEED, bound_counterexample, constrained_eigenbasis, evaluate,
    parseval_first_moment, printed_halfwidth, restrict_to_free, synthetic_record,
    unit_scales,
)
import prepare  # noqa: E402


#: A full immutable image ID. Anything else - a tag, a short ID - is not an identity.
IMAGE_ID_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
#: What the launcher froze beside the record: the approval that authorised THAT run.
APPROVAL_SNAPSHOT = "approval-snapshot.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def approval_snapshot(record_dir: Path, launcher: dict) -> tuple[dict | None, list[str]]:
    """The approval that AUTHORISED this execution, read from beside the record.

    Not the live EXECUTION-APPROVAL.json: that can be created, edited or deleted after a
    run, so a record judged against it later is not judged against what authorised it.
    Every failure below is a PROBLEM that prevents qualification. Nothing falls back to
    launcher provenance - that is the defect this replaces.
    """
    problems: list[str] = []
    name = launcher.get("approval_snapshot")
    digest = launcher.get("approval_sha256")
    if not name:
        problems.append("the launcher provenance names no approval snapshot, so there is "
                        "no record of which approval authorised this execution")
        return None, problems
    path = Path(record_dir) / str(name)
    if not path.is_file():
        problems.append(f"the approval snapshot {name!r} is missing from the record")
        return None, problems
    raw = path.read_bytes()
    measured = hashlib.sha256(raw).hexdigest()
    if not digest:
        problems.append("the launcher provenance records no approval_sha256, so the "
                        "snapshot cannot be shown to be the bytes that were accepted")
    elif measured != digest:
        problems.append(f"the approval snapshot digest is {measured}, but the provenance "
                        f"records {digest}: the snapshot has changed since the run")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        problems.append(f"the approval snapshot is not valid JSON: {exc}")
        return None, problems
    if not isinstance(body, dict):
        problems.append("the approval snapshot is not a JSON object")
        return None, problems
    return body, problems


def command_image_ref(command) -> str | None:
    """The image the RECORDED launch command actually names.

    A command that names a tag yields None, which refuses: an approved ID checked and
    then a tag launched is exactly the substitution this evaluation exists to catch.
    """
    if not isinstance(command, list):
        return None
    for token in command:
        if isinstance(token, str) and IMAGE_ID_RE.fullmatch(token):
            return token
    return None


def well_formed_image_id(value) -> str | None:
    if isinstance(value, str) and IMAGE_ID_RE.fullmatch(value.strip()):
        return value.strip()
    return None


def image_binding_checks(approval: dict | None, launcher: dict,
                         problems: list[str]) -> list[dict]:
    """Three identities that must agree: the one a human APPROVED, the one the run
    OBSERVED, and the one the recorded COMMAND launched."""
    checks: list[dict] = []

    def check(name, passed, detail=None):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    check("the approval that authorised this run is preserved with the record, "
          "and its digest matches", approval is not None and not problems,
          {"problems": problems} if problems else None)
    approved = well_formed_image_id((approval or {}).get("image_id"))
    observed = launcher.get("image_id")
    commanded = command_image_ref(launcher.get("command"))
    check("the approval names a full immutable image ID", approved is not None,
          {"approval image_id": (approval or {}).get("image_id")})
    check("the image observed by the run is the approved one",
          approved is not None and observed == approved,
          {"approved": approved, "observed": observed})
    check("the recorded launch command used the approved image ID, not a tag",
          approved is not None and commanded == approved,
          {"approved": approved, "command_image": commanded})
    return checks


def _fixture_saved(weights, saved_idx, ghz2_per_nd) -> dict:
    """A saved moment with a printed-precision interval, as the real one carries."""
    central = float(weights[saved_idx].sum()) * ghz2_per_nd
    half = sum(printed_halfwidth(float(w) * ghz2_per_nd) for w in weights[saved_idx])
    return {"central_GHz2": central, "lo_GHz2": central - half, "hi_GHz2": central + half,
            "halfwidth_GHz2": half, "modes": [int(i) for i in saved_idx],
            "source": "synthetic fixture, printed precision emulated",
            "eigensolver_convergence": {"propagated_into_A": "UNQUANTIFIED"}}


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
    order = np.argsort(weights)[::-1]
    saved_idx = order[: len(order) // 2]
    omitted_exact_nd = A_total_nd - float(weights[saved_idx].sum())
    saved = _fixture_saved(weights, saved_idx, sc["A_GHz2_per_nd"])

    prov = {"PALACE_PATCH_SHA256": "a" * 64}
    required = {"PALACE_VERSION": "0.13.0",
                "PALACE_COMMIT": "a61c8cbe0cacf496cde3c62e93085fae0d6299ac",
                "PALACE_PATCH": "first-moment-diagnostic",
                "PALACE_PATCH_SHA256": "a" * 64,
                "config_sha256": "c" * 64, "mesh_sha256": "d" * 64,
                "patch_sha256": "e" * 64, "dockerfile_sha256": "f" * 64,
                "image_id": "sha256:" + "1" * 64}
    actual = {k: required[k] for k in ("config_sha256", "mesh_sha256", "patch_sha256",
                                       "dockerfile_sha256", "image_id")}

    def ev(rec, sv=saved, req=required, act=actual):
        return evaluate(rec, sv, required_provenance=req, actual=act,
                        expected_dofs=fx.n_true,
                        expected_L_H=fx.L * sc["InductanceScale_H"])

    good = ev(synthetic_record(fx, Lc, residual_scale=1e-13, seed=seed, provenance=prov))
    diff = good["difference"]["A_direct_minus_A_saved_GHz2"] / sc["A_GHz2_per_nd"]
    certified = good["difference"]["certified_omitted_moment_lower_bound_GHz2"]

    spoiled = {}
    for what in ("functional", "null_space", "convergence", "status",
                 "provenance_missing", "provenance_mismatch", "developer_build"):
        r = ev(synthetic_record(fx, Lc, residual_scale=1e-13, seed=seed, break_check=what,
                                provenance=prov))
        spoiled[what] = {"verdict": r["verdict"],
                         "failed": [c["check"] for c in r["checks"] if not c["passed"]]}
    # a missing required digest, and a mismatched measured digest
    r = ev(synthetic_record(fx, Lc, seed=seed, provenance=prov), req={k: v for k, v in
                                                                      required.items()
                                                                      if k != "image_id"})
    spoiled["required_image_id_not_supplied"] = {
        "verdict": r["verdict"],
        "failed": [c["check"] for c in r["checks"] if not c["passed"]]}
    bad_act = dict(actual, mesh_sha256="0" * 64)
    r = ev(synthetic_record(fx, Lc, seed=seed, provenance=prov), act=bad_act)
    spoiled["measured_mesh_digest_mismatch"] = {
        "verdict": r["verdict"],
        "failed": [c["check"] for c in r["checks"] if not c["passed"]]}

    sloppy = ev(synthetic_record(fx, Lc, residual_scale=1e-6, seed=seed, provenance=prov))
    # a materially negative discrepancy: the saved moment claims more than A_direct
    rec = synthetic_record(fx, Lc, residual_scale=1e-13, seed=seed, provenance=prov)
    # A_saved claiming MORE first moment than the direct evaluation found: the
    # non-negative mode weights forbid it, so the verdict must be INCONSISTENT.
    inflated = dict(saved)
    shift = rec["A"]["A_GHz2"] * (1.0 + 1e-3) - saved["central_GHz2"]
    for k in ("central_GHz2", "lo_GHz2", "hi_GHz2"):
        inflated[k] = saved[k] + shift
    negative = ev(rec, sv=inflated)
    # and a difference well inside the combined uncertainty
    tiny = dict(saved)
    for k in ("central_GHz2", "lo_GHz2", "hi_GHz2"):
        tiny[k] = rec["A"]["A_GHz2"] + (saved[k] - saved["central_GHz2"])
    unresolved = ev(rec, sv=tiny)

    return {
        "label": "FIXTURE EVALUATION - THE EVALUATOR RECOVERS A KNOWN OMITTED MOMENT AND "
                 "FAILS CLOSED OTHERWISE",
        "fixture": {"n_true": fx.n_true, "n_essential": int(len(fx.dbc)),
                    "n_modes_total": int(len(lam)), "n_modes_saved": int(len(saved_idx))},
        "truth": {"A_total_nd": A_total_nd,
                  "A_saved_nd": float(weights[saved_idx].sum()),
                  "omitted_first_moment_exact_nd": omitted_exact_nd},
        "evaluator": {
            "verdict": good["verdict"],
            "all_checks_passed": good["all_checks_passed"],
            "A_direct_minus_A_saved_nd": diff,
            "certified_omitted_moment_lower_bound_nd": certified / sc["A_GHz2_per_nd"],
            "error_vs_truth_nd": diff - omitted_exact_nd,
            "certified_lower_bound_is_below_the_truth":
                certified / sc["A_GHz2_per_nd"] <= omitted_exact_nd,
            "interpretation": good["interpretation"],
        },
        "spoiled_records_are_unqualified": spoiled,
        "sloppy_solve": {"relative_residual": 1e-6, "verdict": sloppy["verdict"],
                         "failed": [c["check"] for c in sloppy["checks"]
                                    if not c["passed"]]},
        "negative_discrepancy": {
            "verdict": negative["verdict"],
            "difference_GHz2": negative["difference"]["A_direct_minus_A_saved_GHz2"],
            "threshold_GHz2": negative["difference"]["materially_negative_threshold_GHz2"],
            "interpretation": negative["interpretation"],
        },
        "difference_inside_the_combined_uncertainty": {
            "verdict": unresolved["verdict"],
            "interpretation": unresolved["interpretation"],
            "tail_upper_bound": unresolved["tail_upper_bound"],
        },
        "the_old_quantity_was_not_a_bound": [
            {k: v for k, v in bound_counterexample(eps, delta).items()
             if k in ("eps", "delta", "relative_residual", "lhs", "uncertified_estimate",
                      "estimate_is_a_bound", "certified_bound_holds", "violation_factor")}
            for eps, delta in ((1e-16, 1e-13), (1e-8, 1e-6))
        ],
        "full_evaluation_of_the_good_record": good,
    }


def record_evaluation(record_dir: Path) -> dict:
    record_dir = Path(record_dir)
    rec_path = record_dir / "postpro" / "first-moment.json"
    if not rec_path.is_file():
        rec_path = record_dir / "solver" / "postpro" / "first-moment.json"
    if not rec_path.is_file():
        raise SystemExit(f"no first-moment.json under {record_dir}: nothing has been executed")
    rec = json.loads(rec_path.read_text())
    prov_path = record_dir / "provenance.json"
    launcher = json.loads(prov_path.read_text()) if prov_path.is_file() else {}
    cfg = prepare.HERE / "config.candidate.json"
    required = prepare.required_provenance(sha256(cfg))
    # THE EXPECTED IMAGE ID COMES FROM THE APPROVAL, not from the launcher. It used to be
    # `required["image_id"] = launcher.get("image_id") or None`, which compared a field
    # with itself: any value the launcher wrote - including a string that is not an image
    # ID at all - satisfied it. prepare.required_provenance() still carries the
    # placeholder "SUPPLIED BY THE EXECUTION ..." for that key; it is superseded here and
    # is never used as an expected value. A missing or unusable approval leaves this None,
    # which the "required value for image_id was supplied" check then refuses. It is NEVER
    # filled in from what was observed.
    approval, approval_problems = approval_snapshot(record_dir, launcher)
    required["image_id"] = well_formed_image_id((approval or {}).get("image_id"))
    actual = {k: launcher.get(k) for k in ("config_sha256", "mesh_sha256", "patch_sha256",
                                           "dockerfile_sha256", "image_id")}
    # Re-measure what is on disk rather than trusting the launcher's own statement.
    solver = record_dir / "solver"
    if (solver / "config.json").is_file():
        actual["config_sha256"] = sha256(solver / "config.json")
    saved = prepare.saved_moments(rec["Scales"]["tc_ns"])["A_all_saved_modes"]
    result = evaluate(rec, saved, required_provenance=required, actual=actual,
                      expected_dofs=prepare.N2R_TRUE_DOFS,
                      expected_L_H=prepare.N2R_PORT_L_H)
    # The three-way image binding, appended to the same fail-closed checklist. These can
    # only TIGHTEN the verdict: a record that would otherwise qualify is refused when the
    # approved, observed and launched identities do not all agree.
    binding = image_binding_checks(approval, launcher, approval_problems)
    result["checks"] = list(result["checks"]) + binding
    failed = [c["check"] for c in binding if not c["passed"]]
    result["image_binding"] = {
        "approved_image_id": well_formed_image_id((approval or {}).get("image_id")),
        "observed_image_id": launcher.get("image_id"),
        "command_image_id": command_image_ref(launcher.get("command")),
        "approval_snapshot_problems": approval_problems,
        "expected_id_source": (f"{APPROVAL_SNAPSHOT} frozen with the record"
                               if approval is not None else "UNAVAILABLE"),
        "never_taken_from": "the launcher's own provenance, or the live approval file",
    }
    if failed:
        result["all_checks_passed"] = False
        result["verdict"] = "UNQUALIFIED"
        result["interpretation"] = "UNQUALIFIED: " + "; ".join(failed)
    result["launcher_provenance"] = launcher or "MISSING: the launcher wrote no provenance.json"
    result["A_saved_variants"] = prepare.saved_moments(rec["Scales"]["tc_ns"])
    result["comparison_scope"] = (
        "A_saved sums the nine saved N2R eigenpairs; A_direct is the moment over the whole "
        "constrained space; their difference is the moment carried by everything the "
        "eigensolver did not return, subject to the checks above")
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
    if args.fixture:
        print(result["label"])
        ev, truth = result["evaluator"], result["truth"]
        print(f"  omitted exact        {truth['omitted_first_moment_exact_nd']:.12e}")
        print(f"  measured difference  {ev['A_direct_minus_A_saved_nd']:.12e}")
        print(f"  certified lower      {ev['certified_omitted_moment_lower_bound_nd']:.12e}"
              f"  (<= truth: {ev['certified_lower_bound_is_below_the_truth']})")
        print(f"  verdict              {ev['verdict']}")
        for k, v in result["spoiled_records_are_unqualified"].items():
            print(f"  spoiled {k:<34} {v['verdict']}  {v['failed']}")
        print(f"  sloppy solve         {result['sloppy_solve']['verdict']}")
        print(f"  negative discrepancy {result['negative_discrepancy']['verdict']}")
        print(f"  inside uncertainty   "
              f"{result['difference_inside_the_combined_uncertainty']['verdict']}")
    else:
        print(result["verdict"], "-", result["interpretation"])


if __name__ == "__main__":
    main()
