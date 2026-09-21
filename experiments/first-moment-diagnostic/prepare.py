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
    DOF_HARD_CAP, WALL_HARD_CAP_S, a_nd_from_ghz2, inductance_nd, unit_scales,
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
FIRST_MOMENT_BLOCK = {
    "Tol": 1e-12,
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
    exactly as experiments/first-moment/n2r_moments.py sums them, plus their
    nondimensional equivalents for the direct comparison."""
    eig, epr = _rows("eig.csv"), _rows("port-EPR.csv")
    f = [r[1] for r in eig]
    p = [abs(r[1]) for r in epr]
    variants = json.loads(SPECTRAL.read_text())["records"]["N2R"]["spectral_variants"]
    out = {}
    for key, v in variants.items():
        idx = v["included_modes"]
        n = sum(p[i - 1] for i in idx)
        a = sum(p[i - 1] * f[i - 1] ** 2 for i in idx)
        out[key] = {
            "modes": idx,
            "N_partial": n,
            "A_partial_GHz2": a,
            "A_partial_nd_at_expected_tc": a_nd_from_ghz2(a, tc_ns),
            "per_mode": [{"mode": i, "f_GHz": f[i - 1], "abs_p": p[i - 1],
                          "abs_p_f2_GHz2": p[i - 1] * f[i - 1] ** 2} for i in idx],
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
                   for name in ("reference_model.py", "prepare.py", "evaluate_record.py")}

    proposal = {
        "label": "FIRST-MOMENT DIAGNOSTIC ON N2R - PREPARED, NOT APPROVED, NOT EXECUTED",
        "status": {
            "prepared": True, "compiled": False, "approved": False, "executed": False,
            "why_not_compiled": ("no Palace toolchain in the preparation environment; the "
                                 "patch was verified to apply cleanly to the pinned commit "
                                 "with `git apply --check` and is built only by the image"),
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
            "checks_built_in": [
                "f . Re(E) + i f . Im(E) == GetVoltage(E) on a random complex field zeroed on the PEC dofs (abort on failure)",
                "u^T K u >= (f . u)^2 / L_nd for x and four random constrained fields (abort on failure)",
                "x vanishes on the PEC dofs; ||r|| / ||f|| reported",
            ],
            "written": "postpro/first-moment.json (see reference_model.RECORD_KEYS); no fields",
        },
        "the_one_execution": {
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
            },
            "inputs": {
                "config": "experiments/first-moment-diagnostic/config.candidate.json",
                "config_sha256": sha256(out_cfg),
                "delta_vs_N2R_solved_config": "experiments/first-moment-diagnostic/config.delta.txt",
                "N2R_solved_config_sha256": N2R_SOLVED_CONFIG_SHA256,
                "mesh": f"results/{N2R_RECORD}/L2/solver/coupled_chip_cell_L2.msh",
                "mesh_sha256": N2R_MESH_SHA256,
            },
            "command": [
                "docker", "run", "--rm", "--network", "none", "--hostname", "localhost",
                "-e", "HOME=/tmp", "-e", "OMP_NUM_THREADS=1", "-e", "OPENBLAS_NUM_THREADS=1",
                "-v", "<workdir>:/work", "-w", "/work", IMAGE, "-np", "1", "config.json",
            ],
            "workdir_contents": ["config.json (= config.candidate.json)", "coupled_chip_cell_L2.msh"],
            "mpi_processes": 1,
            "hard_caps": {
                "dof": DOF_HARD_CAP,
                "wall_s": WALL_HARD_CAP_S,
                "meaning": ("hard caps on the execution, not runtime promises. The space is "
                            f"N2R's, {N2R_TRUE_DOFS} true dofs, so the DOF cap is known to hold; "
                            "the wall cap is enforced by the launcher's timeout, as the ladder "
                            "driver enforces its own, and a run that hits it is FAILED, not retried"),
            },
            "expected_outputs": ["postpro/first-moment.json", "postpro/palace.json", "palace_log.txt"],
            "record_must_carry": [
                "config sha256, mesh sha256, patch sha256, Dockerfile sha256",
                "image ID and RepoDigests; PALACE_COMMIT and PALACE_PATCH_SHA256 read from the image",
                "sha256 of reference_model.py, evaluate_record.py and prepare.py",
                "total, essential and free true-dof counts",
                "Lc, tc, frequency and inductance scales as the solver used them",
                "linear-solve residual, iterations and convergence status",
                "A_nd and A_GHz2",
                "all-nine A_saved recomputed from the committed columns (and variant B)",
                "A_direct - A_saved with the residual bound and the first-order correction",
                "wall time and max RSS",
            ],
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
            "A_direct - A_saved is called the omitted first moment only after the functional, "
            "null-space, unit and numerical checks in evaluate_record.py pass",
            "a raw difference smaller than the residual bound is 'not resolved', not 'small tail'",
            "E_C and g stay UNAVAILABLE whatever the number",
        ],
        "not_done_in_preparation": [
            "no N2R FEM assembly, functional, matrix or solve",
            "no compilation of the C++ patch (verified to apply; built only by the image)",
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
