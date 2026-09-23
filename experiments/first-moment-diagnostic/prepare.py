#!/usr/bin/env python3
"""Prepare the direct first-moment diagnostic on N2R: candidate config, literal delta, proposal.

The diagnostic is N2R's discrete problem - mesh file, two-level refinement
box, order 1, ``MGMaxLevels: 1``, materials, PEC set, the F1 lumped port - with
the problem type changed from ``Eigenmode`` to the patched ``FirstMoment`` type
and the eigensolver block replaced by the diagnostic's own block. Everything
that defines the finite-element space, the material model and the mass matrix
is N2R's, byte for byte; the delta is shown as a literal diff.

This script writes the candidate config, the delta, the execution proposal and
the recomputed saved moments. It launches nothing, compiles nothing, writes
nothing under ``results/`` and never touches ``.github/``. No real-data A, E_C,
N or g is computed: the only N2R numbers here are the committed scalar columns
(eig.csv, port-EPR.csv), summed exactly as the committed first-moment record
already does.
"""
from __future__ import annotations

import copy
import csv
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from reference_model import (  # noqa: E402
    DOF_HARD_CAP, WALL_HARD_CAP_S, a_nd_from_ghz2, inductance_nd, saved_moment_interval,
    unit_scales,
)

#: N2R's record and the config it actually SOLVED - not a candidate file.
N2R_RECORD = "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z"
N2R_DIR = REPO / "results" / N2R_RECORD / "L2" / "solver"
N2R_SOLVED_CONFIG = N2R_DIR / "config.json"
N2R_SOLVED_CONFIG_SHA256 = "79304b5f8bd7c67741e995ec7ae7880b41dfcee23d6c3c12984f5baba8c1f33f"
N2R_MESH = N2R_DIR / "coupled_chip_cell_L2.msh"
N2R_MESH_SHA256 = "d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428"
N2R_LOG = N2R_DIR / "palace_log.txt"
N2R_POSTPRO = N2R_DIR / "postpro"
N2R_TRUE_DOFS = 103411
N2R_PORT_L_H = 1.0345665367517793e-07
#: The characteristic length Palace derived for N2R: the largest bounding-box extent
#: of the 4 mm cell (palace_log.txt:18-19 prints 'L0 = 4.000e-03 m, t0 = 1.334e-02 ns').
N2R_LC_M = 4.0e-3
SPECTRAL = REPO / "experiments" / "fem-spectral-mapping" / "spectral_compatibility.json"

PATCH = REPO / "docker" / "patches" / "first-moment-diagnostic.patch"
DOCKERFILE = REPO / "docker" / "palace-first-moment.Dockerfile"
PROD_DOCKERFILE = REPO / "docker" / "palace.Dockerfile"
PALACE_VERSION = "0.13.0"
PALACE_COMMIT = "a61c8cbe0cacf496cde3c62e93085fae0d6299ac"
IMAGE = "qmhp-cem/palace-first-moment:0.13.0"

#: The diagnostic's own solver block (config["Solver"]["FirstMoment"], parsed by the patch).
#:
#: Tol is the PCG STOPPING tolerance, not the acceptance criterion. Those are different
#: numbers and were briefly the same one: run 35721700281 stopped on Tol = 1e-12 and was
#: then refused because the INDEPENDENTLY recomputed residual, ||M x - f|| / ||f||, came
#: out at 1.3313e-12, just above the 1e-12 acceptance limit in reference_model.evaluate.
#: A stopping rule cannot be asked to beat itself, so the SOLVE is tightened here and the
#: acceptance limit is left exactly where it was.
#:
#: 1e-14 was measured, not guessed, against the attainable floor of the recomputed
#: residual (docs/coupled-candidate/first-moment-tolerance-verification.md):
#:   - N2R base mesh, 56050 free dofs, assembled independently: kappa(D^-1/2 M D^-1/2)
#:     = 148.7, floor = 1.02e-15, i.e. 980x below the 1e-12 acceptance limit;
#:   - at Tol = 1e-14 that solve stops in 126-133 iterations with a recomputed residual
#:     of 9.4e-15, ~107x inside the limit, against a 2000-iteration budget;
#:   - kappa and the floor are mesh-size independent for this element family (measured
#:     flat over a 4x refinement), so the 2-level box refinement does not move them.
#: The floor sits BELOW 1e-14, so the solve converges rather than stagnating.
FIRST_MOMENT_BLOCK = {
    "Tol": 1e-14,
    "MaxIts": 2000,
    "CheckFunctional": True,
    "CheckNullSpace": True,
    "NullSpaceSamples": 4,
    "Seed": 20260920,
}

#: Paths whose modification starts a Palace run somewhere. This preparation must not
#: touch any of them (checked by the tests against the working tree).
WORKFLOW_TRIGGER_PATHS = [
    ".github/ladder-approval.json",
    ".github/pilot-approval.json",
    ".github/workflows/",
    "docker/palace.Dockerfile",
    "solvers/palace/",
    "scripts/palace_golden_run.py",
    "scripts/palace_verify_campaign.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_candidate(n2r_config: dict) -> dict:
    """N2R's solved config with exactly the diagnostic delta applied."""
    cand = copy.deepcopy(n2r_config)
    cand["Problem"]["Type"] = "FirstMoment"
    del cand["Solver"]["Eigenmode"]
    cand["Solver"]["FirstMoment"] = copy.deepcopy(FIRST_MOMENT_BLOCK)
    return cand


def delta_text(before: dict, after: dict) -> str:
    """Unified diff of the two configs in one canonical rendering."""
    a = json.dumps(before, indent=2).splitlines(keepends=True)
    b = json.dumps(after, indent=2).splitlines(keepends=True)
    return "".join(difflib.unified_diff(a, b, fromfile="N2R solved config.json (canonical)",
                                        tofile="first-moment config.candidate.json (canonical)"))


def _rows(name: str) -> list[list[float]]:
    return [[float(c) for c in r] for r in list(csv.reader((N2R_POSTPRO / name).open()))[1:]]


def saved_moments(tc_ns: float) -> dict:
    """The saved partial moments from the committed N2R scalar columns, both variants,
    summed exactly as experiments/first-moment/n2r_moments.py sums them, together with
    the interval that the PRINTED PRECISION of those columns alone implies and the
    eigensolver's own reported errors, which are NOT propagated into that interval."""
    eig, epr = _rows("eig.csv"), _rows("port-EPR.csv")
    f = [r[1] for r in eig]
    p = [abs(r[1]) for r in epr]
    bkwd = [abs(r[4]) for r in eig]
    absr = [abs(r[5]) for r in eig]
    variants = json.loads(SPECTRAL.read_text())["records"]["N2R"]["spectral_variants"]
    out = {}
    for key, v in variants.items():
        idx = v["included_modes"]
        per_mode = [{"mode": i, "f_GHz": f[i - 1], "abs_p": p[i - 1],
                     "abs_p_f2_GHz2": p[i - 1] * f[i - 1] ** 2,
                     "error_bkwd": bkwd[i - 1], "error_abs": absr[i - 1]} for i in idx]
        interval = saved_moment_interval(per_mode)
        n = sum(p[i - 1] for i in idx)
        a = sum(p[i - 1] * f[i - 1] ** 2 for i in idx)
        assert abs(interval["central_GHz2"] - a) <= 1e-12 * a
        out[key] = {
            "modes": idx,
            "N_partial": n,
            "A_partial_GHz2": a,
            "A_partial_nd_at_expected_tc": a_nd_from_ghz2(a, tc_ns),
            "per_mode": per_mode,
            **interval,
            "eigensolver_convergence": {
                "max_backward_error": max(bkwd[i - 1] for i in idx),
                "max_absolute_error": max(absr[i - 1] for i in idx),
                "propagated_into_A": "UNQUANTIFIED",
                "why": ("eig.csv reports a backward and an absolute error per eigenpair; "
                        "turning either into an error on p_m = (q^H E_m)^2 / lambda_m "
                        "needs a spectral gap, which the committed record does not "
                        "measure. It is therefore kept out of the interval and stated "
                        "separately, and any tail conclusion must account for it."),
            },
        }
    return out


def scales_from_log() -> dict:
    """The Lc and tc Palace printed for N2R (three significant digits) and the exact
    expected values from Lc = 4 mm."""
    m = re.search(r"L₀ = ([0-9.e+-]+) m, t₀ = ([0-9.e+-]+) ns", N2R_LOG.read_text())
    assert m, "the N2R log does not print the characteristic scales"
    printed_Lc, printed_tc = float(m.group(1)), float(m.group(2))
    exp = unit_scales(N2R_LC_M)
    assert abs(printed_Lc - N2R_LC_M) <= 5e-7 and abs(printed_tc - exp["tc_ns"]) <= 5e-6
    return {"printed_by_palace": {"Lc_m": printed_Lc, "tc_ns": printed_tc},
            "expected_exact_from_Lc_4mm": exp,
            "L_nd_expected": inductance_nd(N2R_PORT_L_H, N2R_LC_M),
            "note": ("expected values only: the diagnostic record reports Lc, tc and the "
                     "scales it actually used, and the evaluator compares against those")}


def required_provenance(config_sha256: str) -> dict:
    """What a qualifying execution record must carry. Anything missing or mismatched
    prevents qualification; these are REQUIRED values, never reported as verified ones."""
    return {
        "PALACE_VERSION": PALACE_VERSION,
        "PALACE_COMMIT": PALACE_COMMIT,
        "PALACE_PATCH": "first-moment-diagnostic",
        "PALACE_PATCH_SHA256": sha256(PATCH),
        "config_sha256": config_sha256,
        "mesh_sha256": N2R_MESH_SHA256,
        "patch_sha256": sha256(PATCH),
        "dockerfile_sha256": sha256(DOCKERFILE),
        "image_id": "SUPPLIED BY THE EXECUTION: the image ID the launcher records",
    }


def _refuse_results(path: Path) -> None:
    if "results" in path.resolve().relative_to(REPO).parts:
        raise SystemExit(f"refusing to write a candidate under results/: {path}")


def main() -> None:
    assert sha256(N2R_SOLVED_CONFIG) == N2R_SOLVED_CONFIG_SHA256, "N2R solved config drifted"
    assert sha256(N2R_MESH) == N2R_MESH_SHA256, "N2R mesh drifted"
    n2r = json.loads(N2R_SOLVED_CONFIG.read_text())
    cand = build_candidate(n2r)

    out_cfg = HERE / "config.candidate.json"
    out_delta = HERE / "config.delta.txt"
    out_prop = HERE / "proposal.json"
    for p in (out_cfg, out_delta, out_prop):
        _refuse_results(p)
    out_cfg.write_text(json.dumps(cand, indent=2) + "\n")
    out_delta.write_text(delta_text(n2r, cand))

    scales = scales_from_log()
    tc = scales["expected_exact_from_Lc_4mm"]["tc_ns"]
    saved = saved_moments(tc)
    code_hashes = {name: sha256(HERE / name)
                   for name in ("reference_model.py", "prepare.py", "evaluate_record.py",
                                "run_diagnostic.py", "synthetic_fixture.py")}

    proposal = {
        "label": "FIRST-MOMENT DIAGNOSTIC ON N2R - PREPARED, QUALIFIED ON SYNTHETIC "
                 "FIXTURES, NOT APPROVED, NOT EXECUTED ON N2R",
        "status": {
            "prepared": True, "compiled": True, "approved": False, "executed_on_N2R": False,
            "compiled_where": ("natively from the pinned tag with the patch applied; see "
                               "compiled_qualification.json. The reviewed IMAGE could not "
                               "be built in the preparation session - see image_blocker."),
        },
        "image_blocker": {
            "what": "docker build of docker/palace-first-moment.Dockerfile",
            "blocked_by": "the session egress policy",
            "exact_error": ("gateway answered 403 to CONNECT for "
                            "production.cloudfront.docker.com:443 (Docker Hub blob CDN) "
                            "while pulling the digest-pinned ubuntu:24.04 base"),
            "not_routed_around": ("no alternative registry or mirror was used: an "
                                  "organization egress denial is reported, not worked "
                                  "around"),
            "consequence": ("the image ID, repo digest and PALACE_PATCH_SHA256 that a "
                            "qualifying run must carry can only be produced by a build "
                            "in an environment where that host is allowed"),
        },
        "what_would_be_computed": {
            "space": ("N2R's Nedelec space: same mesh file, same two-level box refinement, "
                      "order 1, MGMaxLevels 1, same PEC attributes {2, 4}, same lumped port "
                      "(attribute 10, +Y, L = 1.0345665367517793e-07 H, R = C = 0)"),
            "functional": "f = P^T v, v = LumpedPortData::v (the exact GetVoltage form), zeroed on the PEC true dofs",
            "operator": "M = SpaceOperator::GetMassMatrix(DIAG_ONE) = [[M_free, 0], [0, I]]",
            "solve": "M x = f by PCG + Jacobi, RelTol 1e-12, MaxIts 2000; independent residual r = M x - f",
            "A_nd": "Re(f^T x) / L_nd  with  L_nd = L_H / (mu0 Lc)",
            "A_GHz2": "A_nd * (1 / (2 pi tc_ns))^2",
            "error_qualification": {
                "identity": "A_computed - A_exact = (Re(x^H r) - r^H M^-1 r) / L",
                "certified": ("one-sided only: A_exact >= A_computed - Re(x^H r)/L, "
                              "because r^H M^-1 r >= 0 for SPD M"),
                "not_certified": ("no upper bound on A_exact; ||x|| ||r|| / L is reported "
                                  "as an ESTIMATE and is not a bound"),
            },
            "checks_built_in": [
                "f . Re(E) + i f . Im(E) == GetVoltage(E) on a random complex field zeroed on the PEC dofs (structured FAILED record, then abort)",
                "u^T K u >= (f . u)^2 / L_nd for x and four random constrained fields - a SAMPLED runtime check, not a proof",
                "x vanishes on the PEC dofs; ||r|| / ||f|| reported",
            ],
            "written": "postpro/first-moment.json (see reference_model.RECORD_KEYS); no fields",
        },
        "the_one_execution": {
            "launcher": {
                "script": "experiments/first-moment-diagnostic/run_diagnostic.py",
                "state": "PREPARED, NOT ACTIVATED",
                "refuses_without": "experiments/first-moment-diagnostic/EXECUTION-APPROVAL.json",
                "approval_absent": not (HERE / "EXECUTION-APPROVAL.json").exists(),
                "enforces": {
                    "wall_clock": ("the container is read line by line under a deadline and "
                                   "KILLED on expiry; the bare docker command in the earlier "
                                   "proposal was not a timeout mechanism"),
                    "dof": ("the streamed log is probed for the finest-space ND count and "
                            "the container is KILLED the moment it exceeds the budget"),
                    "provenance": ("image ID, repo digests, labels, the four PALACE_* files "
                                   "read from inside the image, and the sha256 of config, "
                                   "mesh, patch, Dockerfile and diagnostic code are written "
                                   "to provenance.json"),
                },
                "argv": ["docker", "run", "--rm", "--network", "none", "--hostname",
                         "localhost", "--name", "<name>", "--entrypoint", "stdbuf",
                         "-e", "HOME=/tmp", "-e", "OMP_NUM_THREADS=1",
                         "-e", "OPENBLAS_NUM_THREADS=1", "-v", "<workdir>:/work",
                         "-w", "/work", IMAGE, "-oL", "-eL", "palace", "-np", "1",
                         "config.json"],
            },
            "image": {
                "dockerfile": "docker/palace-first-moment.Dockerfile",
                "dockerfile_sha256": sha256(DOCKERFILE),
                "production_dockerfile": "docker/palace.Dockerfile",
                "production_dockerfile_sha256_untouched": sha256(PROD_DOCKERFILE),
                "patch": "docker/patches/first-moment-diagnostic.patch",
                "patch_sha256": sha256(PATCH),
                "palace_version": PALACE_VERSION,
                "palace_commit": PALACE_COMMIT,
                "build": f"docker build -f docker/palace-first-moment.Dockerfile -t {IMAGE} .",
                "must_be_built_where": ("an environment whose egress policy allows the "
                                        "Docker Hub blob CDN; see image_blocker"),
            },
            "inputs": {
                "config": "experiments/first-moment-diagnostic/config.candidate.json",
                "config_sha256": sha256(out_cfg),
                "delta_vs_N2R_solved_config": "experiments/first-moment-diagnostic/config.delta.txt",
                "N2R_solved_config_sha256": N2R_SOLVED_CONFIG_SHA256,
                "mesh": f"results/{N2R_RECORD}/L2/solver/coupled_chip_cell_L2.msh",
                "mesh_sha256": N2R_MESH_SHA256,
            },
            "required_provenance": required_provenance(sha256(out_cfg)),
            "mpi_processes": 1,
            "hard_caps": {
                "dof": DOF_HARD_CAP,
                "wall_s": WALL_HARD_CAP_S,
                "meaning": ("hard caps on the execution, not runtime promises. The space is "
                            f"N2R's, {N2R_TRUE_DOFS} true dofs, so the DOF cap is known to hold; "
                            "the wall cap is enforced by the launcher, and a run that hits "
                            "either cap is FAILED, never retried"),
                "enforced_by": "experiments/first-moment-diagnostic/run_diagnostic.py",
            },
            "expected_outputs": ["postpro/first-moment.json", "postpro/palace.json",
                                 "palace_log.txt", "provenance.json"],
            "evaluation": "uv run python experiments/first-moment-diagnostic/evaluate_record.py --record <record dir>",
            "mechanism": (
                "NO workflow runs this and none is added by this preparation. The approval "
                "must name the mechanism - a separate manually dispatched workflow that builds "
                "docker/palace-first-moment.Dockerfile, or a local run whose record is "
                "committed - and must not reuse the spent PO1 approval or edit "
                ".github/ladder-approval.json."
            ),
            "what_it_authorises": "one execution of this config with this image, once; no retry",
            "what_it_does_not_authorise": [
                "no eigensolve, no driven sweep, no N3, no golden run",
                "no Route A or Route B extraction, no real-data E_C or g",
                "no registered-definition change, no historical-record rewrite",
                "no budget or cap increase, no merge of PR #7",
            ],
        },
        "expected_scales": scales,
        "A_saved_from_committed_columns": saved,
        "what_the_comparison_will_and_will_not_say": [
            "A_direct - A_saved is called an omitted first moment only after every "
            "provenance and numerical check in evaluate_record.py passes",
            "only a CERTIFIED LOWER BOUND on the omitted moment can be stated, from "
            "A_certified_lower - A_saved_hi; there is no certified upper bound, so a small "
            "difference is NOT RESOLVED and never a small tail",
            "a materially negative difference is flagged INCONSISTENT - the non-negative "
            "mode weights forbid it - and is never labelled an omitted moment",
            "mass-solve uncertainty and A_saved uncertainty are reported separately",
            "E_C and g stay UNAVAILABLE whatever the number",
        ],
        "not_done_in_preparation": [
            "no N2R FEM assembly, functional, matrix or solve",
            "no build of the reviewed image (blocked; see image_blocker)",
            "no golden run, no reuse of the spent PO1 approval, no workflow added",
            "no registered-definition change, no historical-record rewrite, no Route A/B, no N3, no budget increase, no PR #7 merge",
        ],
        "workflow_trigger_paths_untouched": WORKFLOW_TRIGGER_PATHS,
        "code_sha256": code_hashes,
    }
    out_prop.write_text(json.dumps(proposal, indent=1) + "\n")
    print(proposal["label"])
    print(f"  candidate config sha256 {sha256(out_cfg)}")
    print(f"  patch sha256            {sha256(PATCH)}")
    print(f"  expected L_nd           {scales['L_nd_expected']:.12f}")
    for k, v in saved.items():
        print(f"  {k:<22} N={v['N_partial']:.12f}  A={v['A_partial_GHz2']:.9f} GHz^2  "
              f"A_nd={v['A_partial_nd_at_expected_tc']:.9f}")


if __name__ == "__main__":
    main()
