#!/usr/bin/env python3
# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Export the Branch-A fixed-point reference snapshot for QUTIP-A-READOUT-CROSSCHECK-v1.

STATUS: PREPARED, NOT APPROVED, NOT EXECUTED. No snapshot has been generated.

Runs only in the supported QMHP-CEM environment (Python >= 3.11, uv.lock). It
calls the EXISTING production functions and records what they produce; it does
not modify, replace or re-implement them:

* ``models.fluxonium.nominal_spectrum(levels=10)`` for the retained frequencies and
  the full signed/complex charge matrix;
* ``models.dressed_system.solve_dressed(4.301974466, spectrum, 10, 12, g)`` for the
  fixed-point dressed baseline. The readout frequency is the MASTER-FROZEN
  production root, held fixed. No root search is performed.

The exact CEM-assembled Hamiltonian is captured by wrapping ``numpy.linalg.eigh``
as seen from ``models.dressed_system`` for the duration of the one call, so the
exported baseline is the matrix the production code actually diagonalised, not a
re-assembly. The wrapper refuses a second call: a root search would call it many
times. Every root-search entry point (``solve_dressed_root``, ``nominal_root``,
``nominal_solution``, ``dressed_spectrum``, ``brentq``) is replaced for the
duration by a function that raises.

Modes:
  --dry-run (default)  report the plan, source hashes and tree state; no solve.
  --execute            the numerical export. Requires --approval FILE and
                       --approval-sha256 HEX, a clean tree, and a NEW output
                       directory outside results/ and master/. An approval file
                       written by an agent is not proof of human authorisation;
                       the approved launcher must enforce that.

This script never writes into results/ or master/ and never overwrites a file.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PROTOCOL_ID = "QUTIP-A-READOUT-CROSSCHECK-v1"
SCHEMA_ID = "qmhp-cem.qutip-branch-a-reference/1"
SCHEMA_PATH = REPO_ROOT / "schemas" / "qutip" / "branch-a-reference-v1.schema.json"
PROTOCOL_DOC_PATH = REPO_ROOT / "docs" / "qutip" / "branch-a-fixed-point-crosscheck-v1.md"
CHECKER_PATH = REPO_ROOT / "tools" / "qutip_bridge" / "check_branch_a_reference.py"

#: Fixed readout frequency: master dressed_system.production_convention.root_GHz.
READOUT_GHZ = 4.301974466
NQ = 10
NPH = 12
SKIP_THRESHOLD = 1e-14

SOURCE_FILES = (
    "models/fluxonium.py",
    "models/dressed_system.py",
    "contracts/master.py",
    "master/qmhp_v158f_requirements.yaml",
    "pyproject.toml",
    "uv.lock",
)
IMPLEMENTATION_FILES = (
    "scripts/export_qutip_branch_a_reference.py",
    "schemas/qutip/branch-a-reference-v1.schema.json",
    "docs/qutip/branch-a-fixed-point-crosscheck-v1.md",
)

#: Entry points that perform (or trigger) the logical-blind root search.
ROOT_SEARCH_ENTRY_POINTS = (
    "solve_dressed_root",
    "nominal_root",
    "nominal_solution",
    "dressed_spectrum",
    "brentq",
)

FORBIDDEN_OUTPUT_ROOTS = ("results", "master")

#: One guard per process. Nested or concurrent guards are refused rather than allowed
#: to capture each other's matrices. This does NOT stop an unrelated thread from
#: calling models.dressed_system while a guard is active; the exporter is a
#: single-threaded CLI and must stay one (documented limitation).
_GUARD_LOCK = threading.Lock()


class ExportRefused(RuntimeError):
    """The export may not proceed. Nothing has been written."""


class RootSearchForbidden(RuntimeError):
    """A root-search entry point was reached during a fixed-point export."""


# ------------------------------------------------------------------ provenance


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hash_files(names: tuple[str, ...], root: Path = REPO_ROOT) -> dict[str, str]:
    missing = [name for name in names if not (root / name).is_file()]
    if missing:
        raise ExportRefused(f"required source files are missing: {missing}")
    return {name: sha256_file(root / name) for name in names}


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def tree_state() -> dict[str, Any]:
    status = git("status", "--porcelain")
    return {"commit": git("rev-parse", "HEAD"), "clean": status == "", "status": status}


def check_output_path(output: Path) -> Path:
    """A NEW directory outside the historical evidence trees."""
    output = Path(output).resolve()
    for name in FORBIDDEN_OUTPUT_ROOTS:
        forbidden = (REPO_ROOT / name).resolve()
        if output == forbidden or forbidden in output.parents:
            raise ExportRefused(f"output {output} is inside {name}/; historical trees are read-only")
    if output.exists():
        raise ExportRefused(f"output {output} already exists; nothing is overwritten")
    return output


# ------------------------------------------------------------- guarded solve


@contextlib.contextmanager
def fixed_point_guard(dressed_module: Any) -> Iterator[list]:
    """Forbid root search and capture the one Hamiltonian passed to eigh.

    Yields a list that receives exactly one copy of the matrix given to
    ``la.eigh`` inside ``dressed_module``. Everything is restored on exit.
    """
    if not _GUARD_LOCK.acquire(blocking=False):
        raise ExportRefused("a fixed-point guard is already active in this process; nested or concurrent capture is refused")
    try:
        with _patched(dressed_module) as captured:
            yield captured
    finally:
        _GUARD_LOCK.release()


@contextlib.contextmanager
def _patched(dressed_module: Any) -> Iterator[list]:
    captured: list = []
    real_la = dressed_module.la

    class _CapturingLinalg:
        def __getattr__(self, name: str) -> Any:
            return getattr(real_la, name)

        @staticmethod
        def eigh(matrix: Any, *args: Any, **kwargs: Any) -> Any:
            if captured:
                raise RootSearchForbidden(
                    "eigh was called more than once; a fixed-point export makes exactly one solve"
                )
            if args or kwargs:
                raise RootSearchForbidden("eigh was called with arguments the production path does not use")
            captured.append(matrix.copy())
            return real_la.eigh(matrix)

    def _forbidden(name: str) -> Any:
        def raiser(*_args: Any, **_kwargs: Any) -> Any:
            raise RootSearchForbidden(f"{name} was invoked during a fixed-point export")

        return raiser

    saved = {name: getattr(dressed_module, name) for name in ROOT_SEARCH_ENTRY_POINTS}
    try:
        dressed_module.la = _CapturingLinalg()
        for name in ROOT_SEARCH_ENTRY_POINTS:
            setattr(dressed_module, name, _forbidden(name))
        yield captured
    finally:
        dressed_module.la = real_la
        for name, value in saved.items():
            setattr(dressed_module, name, value)


def require_single_capture(captured: list) -> Any:
    """Zero or several captured Hamiltonians refuse the export."""
    if len(captured) != 1:
        raise ExportRefused(f"expected exactly one captured Hamiltonian, got {len(captured)}")
    return captured[0]


def label_scores(eigenvectors: Any, labels: dict) -> list[dict[str, Any]]:
    """Scores for the existing maximum-bare-overlap labels, plus the runner-up.

    Re-derives the argmax only to confirm it matches the production labels; a
    mismatch refuses the export rather than choosing between them.
    """
    import numpy as np

    overlap = np.abs(np.asarray(eigenvectors)) ** 2
    rows = []
    for level in (0, 1, 2):
        for photon in (0, 1):
            bare = level * NPH + photon
            row = overlap[bare, :]
            best = int(np.argmax(row))
            if best != labels[(level, photon)][1]:
                raise ExportRefused(f"label ({level},{photon}) does not match the production argmax")
            masked = row.copy()
            masked[best] = -1.0
            runner = int(np.argmax(masked))
            rows.append(
                {
                    "level": level,
                    "photon": photon,
                    "bare_index": bare,
                    "dressed_index": best,
                    "energy_GHz": float(labels[(level, photon)][0]),
                    "overlap": float(row[best]),
                    "runner_up_index": runner,
                    "runner_up_overlap": float(row[runner]),
                }
            )
    return rows


def _matrix_lists(matrix: Any) -> tuple[list, list]:
    import numpy as np

    array = np.asarray(matrix)
    return (
        [[float(x) for x in row] for row in array.real],
        [[float(x) for x in row] for row in np.asarray(array.imag)],
    )


def build_payload(
    *,
    payload_kind: str,
    frequencies: Any,
    charge_matrix: Any,
    hamiltonian: Any,
    eigenvalues: Any,
    labels: list[dict[str, Any]],
    observables: dict[str, float],
    provenance: dict[str, Any],
    runtime: dict[str, Any],
    eigh_calls: int,
) -> dict[str, Any]:
    """Assemble the snapshot dictionary from already-computed arrays.

    Pure bookkeeping: no physics is computed here. Used by ``run_export`` with the
    production outputs, and by the contract tests with SYNTHETIC arrays.
    """
    import numpy as np

    charge = np.asarray(charge_matrix)
    h = np.asarray(hamiltonian)
    charge_re, charge_im = _matrix_lists(charge)
    h_re, h_im = _matrix_lists(h)
    dressed = [item["dressed_index"] for item in labels]
    return {
        "schema": SCHEMA_ID,
        "protocol_id": PROTOCOL_ID,
        "payload_kind": payload_kind,
        "evidence_scope": (
            "Independent QuTiP operator/tensor assembly of the same declared finite Branch-A "
            "fluxonium-readout model at one fixed readout frequency, followed by a controlled "
            "numerical comparison with the CEM baseline. The eigensolver (numpy.linalg.eigh), the "
            "labelling rule and the observable formulas are shared with CEM, not independent. It "
            "does not validate the supplied static spectrum, electromagnetic extraction, geometry, "
            "continuum convergence, hardware, coupling extraction or the QMHP architecture."
        ),
        "repository": "brodieduncan88/QMHP-CEM",
        "source_commit": provenance["source_commit"],
        "source_tree_clean": provenance["source_tree_clean"],
        "source_file_hashes": provenance["source_file_hashes"],
        "master_revision": "v1.5.8f",
        "master_file": "master/qmhp_v158f_requirements.yaml",
        "master_file_sha256": provenance["source_file_hashes"]["master/qmhp_v158f_requirements.yaml"],
        "branch": "A",
        "input_classifications": {
            "device_parameters": "MASTER-FROZEN",
            "phase_grid": "MASTER-FROZEN / VERIFIED-COMPUTATIONAL",
            "truncation": "MASTER-FROZEN",
            "readout_GHz": "MASTER-FROZEN",
            "coupling_g_GHz": "VERIFIED-COMPUTATIONAL",
            "frequencies_and_charge_matrix": "COMPUTED-AT-EXPORT (not a master classification)",
            "baseline": "COMPUTED-AT-EXPORT (not a master classification)",
            "comparison_thresholds": "PROPOSED ENGINEERING-RULE, not approved, not carried in this payload",
        },
        "units": {
            "energies": "GHz (E/h)",
            "frequencies": "GHz",
            "hamiltonian": "GHz (H/h)",
            "coupling": "GHz",
            "pulls": "MHz",
            "phase": "rad",
            "charge_matrix": "dimensionless",
            "f8_weight": "dimensionless",
        },
        "EC_over_h_GHz": 0.6,
        "EJ_over_h_GHz": 5.72,
        "EL_over_h_GHz": 1.58,
        "phi_ext_rad": math.pi,
        "phi_ext_symbolic": "pi",
        "phase_grid_definition": {
            "grid_points": 3201,
            "phase_min_symbolic": "-8*pi",
            "phase_max_symbolic": "+8*pi",
            "phase_min_rad": -8 * math.pi,
            "phase_max_rad": 8 * math.pi,
            "kinetic_operator": "second_difference",
            "hamiltonian": "H = -4 E_C d2/dphi2 + 0.5 E_L phi^2 - E_J cos(phi - phi_ext)",
            "charge_operator": "n_ij = -i <i|d/dphi|j>, numpy.gradient on the same grid",
            "eigensolver": "scipy.linalg.eigh_tridiagonal, select='i', lowest 10",
        },
        "Nq": NQ,
        "Nph": NPH,
        "dimension": NQ * NPH,
        "tensor_order": ["fluxonium", "resonator"],
        "flat_index": "level*Nph + photon",
        "readout_GHz": READOUT_GHZ,
        "readout_source": (
            "master dressed_system.production_convention.root_GHz, held fixed; no root search is "
            "performed by the exporter or the checker"
        ),
        "root_search_performed": False,
        "coupling_g_GHz": 0.15,
        "coupling_classification": "VERIFIED-COMPUTATIONAL",
        "coupling_is_geometry_derived": False,
        "coupling_note": (
            "Reference coefficient from the release readout-replication script (g = 0.150 GHz). "
            "It is not a geometry-derived or S1-extracted coupling and must not be presented as one."
        ),
        "logical_states": [0, 2],
        "sink_state": 1,
        "frequencies_GHz": [float(x) for x in np.asarray(frequencies)],
        "charge_matrix_real": charge_re,
        "charge_matrix_imag": charge_im,
        "charge_element_skip_threshold": SKIP_THRESHOLD,
        "charge_element_skip_rule": (
            "elements with abs(n_ij) < 1e-14 are omitted from the Hamiltonian assembly (existing "
            "models/dressed_system.py convention); the unmodified charge matrix above is the evidence"
        ),
        "baseline_H_real": h_re,
        "baseline_H_imag": h_im,
        "baseline_eigensolver": "numpy.linalg.eigh (UPLO='L')",
        "baseline_eigenvalues": [float(x) for x in np.asarray(eigenvalues)],
        "label_convention": (
            "for each bare state (level, photon) with level in {0,1,2} and photon in {0,1}: the "
            "dressed eigenvector index maximising |<bare|dressed>|^2 (numpy.argmax; first maximum "
            "on exact ties)"
        ),
        "baseline_labels": labels,
        "baseline_observables": {key: float(value) for key, value in observables.items()},
        "baseline_diagnostics": {
            "hamiltonian_hermiticity_defect_max_abs": float(np.max(np.abs(h - h.conj().T))),
            "charge_matrix_hermiticity_defect_max_abs": float(np.max(np.abs(charge - charge.conj().T))),
            "skipped_charge_elements": int(np.sum(np.abs(charge) < SKIP_THRESHOLD)),
            "duplicate_label_assignment": len(set(dressed)) != len(dressed),
            "eigh_calls_captured": eigh_calls,
        },
        "baseline_runtime": runtime,
        "baseline_implementation_hashes": provenance["baseline_implementation_hashes"],
    }


def validate_with_checker(payload_bytes: bytes) -> None:
    """Run the standalone checker's schema and structural validation on the bytes.

    The checker is loaded by path; it imports nothing from QMHP-CEM.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("qutip_bridge_checker", CHECKER_PATH)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    schema = checker.strict_json_loads(SCHEMA_PATH.read_bytes(), "schema")
    checker.check_schema_keywords(schema)
    payload = checker.strict_json_loads(payload_bytes, "snapshot")
    checker.validate_schema(payload, schema)
    checker.semantic_checks(payload)


def run_export(output: Path) -> Path:
    """The numerical export. Reached only through ``main --execute``."""
    import numpy as np
    import scipy

    from contracts import master
    from models import dressed_system, fluxonium
    from orchestrator import manifest

    if master.get("dressed_system.production_convention.root_GHz") != READOUT_GHZ:
        raise ExportRefused("the master production root is not the declared fixed readout frequency")
    if (dressed_system.PRODUCTION_NQ, dressed_system.PRODUCTION_NPH) != (NQ, NPH):
        raise ExportRefused("production truncation is not (10, 12)")
    if not (dressed_system.COUPLING_G_GHz == master.get("dressed_system.coupling_g_GHz") == 0.15):
        raise ExportRefused("coupling g is not the declared VERIFIED-COMPUTATIONAL 0.150 GHz")

    started_wall = datetime.now(timezone.utc)
    started = time.monotonic()
    spectrum = fluxonium.nominal_spectrum(levels=NQ)
    with fixed_point_guard(dressed_system) as captured:
        solution = dressed_system.solve_dressed(
            READOUT_GHZ, spectrum, NQ, NPH, g_GHz=dressed_system.COUPLING_G_GHz
        )
        weight = solution.purcell_weight()
    wall = time.monotonic() - started
    baseline_hamiltonian = require_single_capture(captured)

    observables = {
        "pull_MHz_level0": solution.pulls_MHz[0],
        "pull_MHz_level1": solution.pulls_MHz[1],
        "pull_MHz_level2": solution.pulls_MHz[2],
        "logical_pull_MHz": solution.logical_pull_MHz,
        "sink_pull_MHz": solution.sink_pull_MHz,
        "sink_logical_contrast_MHz": solution.sink_logical_contrast_MHz,
        "sink_line_GHz": solution.sink_line_GHz,
        "dressed_emission_GHz": solution.dressed_f12_GHz,
        "f8_weight": weight,
    }
    state = tree_state()
    provenance = {
        "source_commit": state["commit"],
        "source_tree_clean": state["clean"],
        "source_file_hashes": hash_files(SOURCE_FILES),
        "baseline_implementation_hashes": hash_files(IMPLEMENTATION_FILES),
    }
    runtime = {
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "platform": platform.platform(),
        "started_utc": started_wall.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "ended_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "wall_seconds": wall,
    }
    payload = build_payload(
        payload_kind="CEM-EXPORT",
        frequencies=spectrum.frequencies_GHz,
        charge_matrix=spectrum.charge_matrix,
        hamiltonian=baseline_hamiltonian,
        eigenvalues=solution.eigenvalues,
        labels=label_scores(solution.eigenvectors, solution.labels),
        observables=observables,
        provenance=provenance,
        runtime=runtime,
        eigh_calls=len(captured),
    )
    body = (json.dumps(payload, indent=1, allow_nan=False) + "\n").encode("utf-8")
    validate_with_checker(body)

    output.mkdir(parents=True)
    snapshot = output / "branch-a-reference-v1.json"
    with snapshot.open("xb") as handle:
        handle.write(body)
    manifest.write_verified(output)
    return snapshot


def load_approval(path: Path | None, expected_sha256: str | None, commit: str, output: Path) -> None:
    if path is None or expected_sha256 is None:
        raise ExportRefused("--execute needs --approval and --approval-sha256; execution stays BLOCKED")
    data = Path(path).read_bytes()
    measured = hashlib.sha256(data).hexdigest()
    if measured != expected_sha256:
        raise ExportRefused(f"approval sha256 {measured} does not match {expected_sha256}")
    def _no_duplicates(pairs: list) -> dict:
        keys = [key for key, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ExportRefused("approval record has duplicate keys")
        return dict(pairs)

    def _no_constants(token: str) -> Any:
        raise ExportRefused(f"approval record contains {token}")

    try:
        approval = json.loads(data, object_pairs_hook=_no_duplicates, parse_constant=_no_constants)
    except ValueError as exc:
        raise ExportRefused(f"approval record is not valid JSON: {exc}")
    required = {"protocol_id", "source_commit", "output", "approved_by", "scope"}
    if not isinstance(approval, dict) or not required <= set(approval):
        raise ExportRefused(f"approval must carry {sorted(required)}")
    if approval["protocol_id"] != PROTOCOL_ID:
        raise ExportRefused("approval is for another protocol")
    if approval["source_commit"] != commit:
        raise ExportRefused("approval is bound to another commit")
    if Path(approval["output"]).resolve() != output:
        raise ExportRefused("approval is bound to another output path")


def plan() -> dict[str, Any]:
    """The dry-run report: what would be exported, from what. No solve."""
    state = tree_state()
    return {
        "protocol_id": PROTOCOL_ID,
        "mode": "DRY-RUN: no static solve, no dressed solve, no snapshot written",
        "source_commit": state["commit"],
        "source_tree_clean": state["clean"],
        "source_file_hashes": hash_files(SOURCE_FILES),
        "baseline_implementation_hashes": hash_files(IMPLEMENTATION_FILES),
        "fixed_readout_GHz": READOUT_GHZ,
        "truncation": {"Nq": NQ, "Nph": NPH},
        "calls_that_would_be_made": [
            "models.fluxonium.nominal_spectrum(levels=10)",
            "models.dressed_system.solve_dressed(4.301974466, spectrum, 10, 12, g_GHz=0.150)",
            "DressedSolution.purcell_weight()",
        ],
        "root_search_entry_points_forbidden": list(ROOT_SEARCH_ENTRY_POINTS),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="report the plan only (default)")
    mode.add_argument("--execute", action="store_true", help="perform the approved numerical export")
    parser.add_argument("--output", type=Path, help="NEW directory, outside results/ and master/")
    parser.add_argument("--approval", type=Path, help="approval record for this export")
    parser.add_argument("--approval-sha256", help="expected sha256 of the approval record bytes")
    args = parser.parse_args(argv)

    try:
        if not args.execute:
            print(json.dumps(plan(), indent=1))
            return 0
        if args.output is None:
            raise ExportRefused("--execute needs --output")
        output = check_output_path(args.output)
        state = tree_state()
        if not state["clean"]:
            raise ExportRefused("the working tree is not clean; provenance would be unqualified")
        load_approval(args.approval, args.approval_sha256, state["commit"], output)
        snapshot = run_export(output)
    except (ExportRefused, RootSearchForbidden) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    print(f"EXPORTED: {snapshot} sha256 {sha256_file(snapshot)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
