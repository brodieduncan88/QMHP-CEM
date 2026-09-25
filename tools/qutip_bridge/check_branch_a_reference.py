#!/usr/bin/env python3
# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Standalone checker for QUTIP-A-READOUT-CROSSCHECK-v1.

STATUS: PREPARED, NOT APPROVED, NOT EXECUTED.

A fixed-point cross-implementation check. Given a hash-bound JSON snapshot
exported from the QMHP-CEM environment (``scripts/export_qutip_branch_a_reference.py``),
it assembles the declared finite Branch-A fluxonium-readout Hamiltonian with QuTiP
operators and tensor products, and compares it with the CEM-assembled baseline
carried in the snapshot.

What is and is not independent of CEM:
  * QuTiP: operator and tensor assembly only (Qobj, tensor, qeye, num, destroy, dag).
  * NumPy: the charge-element omission, the dense eigensolve (numpy.linalg.eigh,
    UPLO='L' - the SAME routine CEM uses), labelling, observables and comparisons.
  * SciPy: not called directly (QuTiP may use it internally).
The permitted claim is therefore: independent QuTiP operator/tensor assembly of the
same finite model, followed by a controlled numerical comparison. The eigensolver,
labelling rule and observable formulas are shared with CEM, not independent.

What this does NOT do: it does not validate the static fluxonium spectrum, any
electromagnetic extraction, geometry, hardware, coupling extraction or the QMHP
architecture. It performs no frequency or root search. It implements no open-system
or Lindblad physics. It never generates or fills in a snapshot.

Deliberate constraints (docs/qutip/branch-a-fixed-point-crosscheck-v1.md):

* Standalone. It must not import QMHP-CEM (contracts, models, orchestrator,
  evaluator, geometry, solvers); it runs on a separate machine.
* Python 3.9 syntax. Target runtime: the owner's Mac, Python 3.9.6 and QuTiP 5.0.4.
  That runtime is recorded at execution time, not assumed.
* Validation uses the standard library only. NumPy and QuTiP are imported lazily,
  inside the execution path, and only after every validation step has passed.
* Fail closed. JSON is parsed strictly: NaN, Infinity, overflowing literals and
  duplicate keys are rejected. No pickle, no eval/exec, no executable configuration,
  no downloads, no dependency installation.
* Hashes that authenticate the snapshot are supplied OUTSIDE the snapshot.

Exit codes: 0 VALIDATED (or EXECUTED), 2 BLOCKED (a required input is missing),
3 REJECTED (an input failed a check), 4 EXECUTION-FAILED (preserved, never retried).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import platform
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

PROTOCOL_ID = "QUTIP-A-READOUT-CROSSCHECK-v1"
SCHEMA_ID = "qmhp-cem.qutip-branch-a-reference/1"

NQ = 10
NPH = 12
DIMENSION = NQ * NPH
READOUT_GHZ = 4.301974466
COUPLING_G_GHZ = 0.15
SKIP_THRESHOLD = 1e-14
TENSOR_ORDER = ["fluxonium", "resonator"]
LABEL_PAIRS = [(level, photon) for level in (0, 1, 2) for photon in (0, 1)]
LOGICAL_STATES = (0, 2)
SINK_STATE = 1

EXIT_OK = 0
EXIT_BLOCKED = 2
EXIT_REJECTED = 3
EXIT_EXECUTION_FAILED = 4

#: JSON-Schema keywords this checker enforces. Any other non-annotation keyword in
#: the schema file is a REJECTION: an unenforced keyword would look like a check
#: that is not being made.
SUPPORTED_KEYWORDS = frozenset(
    {
        "type", "required", "properties", "additionalProperties", "const", "enum",
        "items", "minItems", "maxItems", "minimum", "maximum", "exclusiveMinimum",
        "pattern", "minLength",
    }
)
ANNOTATION_KEYWORDS = frozenset({"$schema", "$id", "$comment", "title", "description"})

#: PROPOSED ENGINEERING-RULES (brief §3). NOT frozen master requirements and NOT
#: approved. Execution reads the thresholds from the separately hash-bound
#: frozen-rules file; these values exist only so that a mismatch can be reported.
PROPOSED_ENGINEERING_RULES = {
    "max_hamiltonian_entry_abs_diff_GHz": 1e-12,
    "max_ordered_eigenvalue_abs_diff_GHz": 1e-10,
    "max_pull_or_contrast_abs_diff_MHz": 1e-6,
    "max_sink_line_or_emission_abs_diff_GHz": 1e-9,
    "max_f8_weight_abs_diff": 1e-10,
}

#: Fields a frozen-rules file must carry before any calculation is allowed.
FROZEN_RULES_REQUIRED = (
    "protocol_id",
    "rules_status",
    "approval_reference",
    "thresholds",
    "label_min_overlap",
    "label_min_margin",
    "max_hamiltonian_hermiticity_defect_GHz",
    "wall_time_limit_s",
    "memory_limit_MB",
    "permitted_attempts",
    "eigensolver",
)

#: The only rules status under which execution may proceed. Anything else - in
#: particular the PROPOSED values copied into a file without that approval - keeps
#: execution BLOCKED. The file is agent-writable, so this is an explicit declaration,
#: not proof of human authorisation; the approved launcher must enforce that.
FROZEN_RULES_STATUS = "FROZEN-BY-HUMAN-APPROVAL (ENGINEERING-RULE, not MASTER-FROZEN)"

FORBIDDEN_TOP_LEVEL_MODULES = frozenset(
    {"contracts", "models", "orchestrator", "evaluator", "geometry", "solvers", "pickle"}
)


class CheckFailure(Exception):
    """A check rejected the input. ``status`` is REJECTED or BLOCKED."""

    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


def _reject(message: str) -> CheckFailure:
    return CheckFailure("REJECTED", message)


def _blocked(message: str) -> CheckFailure:
    return CheckFailure("BLOCKED", message)


# --------------------------------------------------------------------------- JSON


def _no_duplicate_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _reject("duplicate JSON key %r" % key)
        result[key] = value
    return result


def _no_constants(token: str) -> Any:
    raise _reject("non-finite JSON constant %r is not permitted" % token)


def _assert_finite_tree(value: Any, path: str) -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _reject("%s: non-finite number (overflowing literal?)" % path)
    elif isinstance(value, dict):
        for key, item in value.items():
            _assert_finite_tree(item, "%s.%s" % (path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_finite_tree(item, "%s[%d]" % (path, index))


def strict_json_loads(data: bytes, what: str) -> Any:
    """Parse JSON bytes, failing closed on anything non-standard."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _reject("%s: not UTF-8 (%s)" % (what, exc))
    try:
        value = json.loads(
            text, object_pairs_hook=_no_duplicate_keys, parse_constant=_no_constants
        )
    except CheckFailure:
        raise
    except ValueError as exc:
        raise _reject("%s: malformed JSON (%s)" % (what, exc))
    _assert_finite_tree(value, what)
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_required_file(path: Optional[str], what: str) -> bytes:
    if not path:
        raise _blocked("%s was not supplied" % what)
    if not os.path.isfile(path):
        raise _blocked("%s is missing: %s" % (what, path))
    with open(path, "rb") as handle:
        return handle.read()


# ------------------------------------------------------------------- schema subset


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    raise _reject("schema uses unsupported type %r" % expected)


def _json_equal(left: Any, right: Any) -> bool:
    """Equality that does not let True equal 1 or 1.0 equal True."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return type(left) is type(right) and left == right
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_json_equal(left[k], right[k]) for k in left)
    return type(left) is type(right) and left == right


def check_schema_keywords(schema: Any, path: str = "schema") -> None:
    """Refuse a schema using keywords this checker would silently ignore."""
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in ANNOTATION_KEYWORDS:
                continue
            if key not in SUPPORTED_KEYWORDS:
                raise _reject("%s: unsupported schema keyword %r" % (path, key))
            if key == "properties":
                for name, sub in value.items():
                    check_schema_keywords(sub, "%s.properties.%s" % (path, name))
            elif key == "items":
                check_schema_keywords(value, "%s.items" % path)


def validate_schema(instance: Any, schema: Dict[str, Any], path: str = "$") -> None:
    """Validate ``instance`` against the supported JSON-Schema subset."""
    if "const" in schema and not _json_equal(instance, schema["const"]):
        raise _reject("%s: expected constant %r, got %r" % (path, schema["const"], instance))
    if "enum" in schema and not any(_json_equal(instance, option) for option in schema["enum"]):
        raise _reject("%s: %r is not one of %r" % (path, instance, schema["enum"]))
    if "type" in schema and not _type_ok(instance, schema["type"]):
        raise _reject("%s: expected type %s, got %s" % (path, schema["type"], type(instance).__name__))
    if isinstance(instance, dict):
        for name in schema.get("required", []):
            if name not in instance:
                raise _reject("%s: missing required field %r" % (path, name))
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(instance) - set(properties))
            if extra:
                raise _reject("%s: unexpected fields %r" % (path, extra))
        for name, sub in properties.items():
            if name in instance:
                validate_schema(instance[name], sub, "%s.%s" % (path, name))
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise _reject("%s: %d items, fewer than %d" % (path, len(instance), schema["minItems"]))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise _reject("%s: %d items, more than %d" % (path, len(instance), schema["maxItems"]))
        if "items" in schema:
            for index, item in enumerate(instance):
                validate_schema(item, schema["items"], "%s[%d]" % (path, index))
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise _reject("%s: %r below minimum %r" % (path, instance, schema["minimum"]))
        if "maximum" in schema and instance > schema["maximum"]:
            raise _reject("%s: %r above maximum %r" % (path, instance, schema["maximum"]))
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            raise _reject("%s: %r not above %r" % (path, instance, schema["exclusiveMinimum"]))
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise _reject("%s: string shorter than %d" % (path, schema["minLength"]))
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            raise _reject("%s: %r does not match %s" % (path, instance, schema["pattern"]))


# ---------------------------------------------------------------- semantic checks


def _matrix(payload: Dict[str, Any], key: str, rows: int, cols: int) -> List[List[float]]:
    value = payload[key]
    if not isinstance(value, list) or len(value) != rows:
        raise _reject("%s: expected %d rows" % (key, rows))
    for index, row in enumerate(value):
        if not isinstance(row, list) or len(row) != cols:
            raise _reject("%s[%d]: expected %d columns" % (key, index, cols))
        for column, entry in enumerate(row):
            if isinstance(entry, bool) or not isinstance(entry, (int, float)):
                raise _reject("%s[%d][%d]: not a number" % (key, index, column))
            if not math.isfinite(entry):
                raise _reject("%s[%d][%d]: not finite" % (key, index, column))
    return value


def semantic_checks(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Checks the schema cannot express. Returns a findings dictionary.

    These are structural. They do not reassemble the Hamiltonian from the inputs;
    that comparison is the calculation and is only reached through ``execute``.
    """
    findings: Dict[str, Any] = {}

    frequencies = payload["frequencies_GHz"]
    if frequencies[0] != 0.0:
        raise _reject("frequencies_GHz[0] must be exactly 0 (energies relative to the ground state)")
    if any(frequencies[i + 1] < frequencies[i] for i in range(NQ - 1)):
        raise _reject("frequencies_GHz must be non-decreasing")

    charge_re = _matrix(payload, "charge_matrix_real", NQ, NQ)
    charge_im = _matrix(payload, "charge_matrix_imag", NQ, NQ)
    h_re = _matrix(payload, "baseline_H_real", DIMENSION, DIMENSION)
    h_im = _matrix(payload, "baseline_H_imag", DIMENSION, DIMENSION)

    eigenvalues = payload["baseline_eigenvalues"]
    if any(eigenvalues[i + 1] < eigenvalues[i] for i in range(DIMENSION - 1)):
        raise _reject("baseline_eigenvalues must be in ascending order")

    readout = payload["readout_GHz"]
    # Block structure of the declared model, level-major (fluxonium first):
    #   diagonal:     frequencies[level] + readout*photon, bit for bit;
    #   off-diagonal: nonzero only where photon numbers differ by exactly one.
    for row in range(DIMENSION):
        level_r, photon_r = divmod(row, NPH)
        expected_diagonal = frequencies[level_r] + readout * photon_r
        if h_re[row][row] != expected_diagonal or h_im[row][row] != 0.0:
            raise _reject(
                "baseline_H[%d][%d] is not frequencies[%d] + readout*%d; the matrix is "
                "altered or not assembled in the declared tensor order" % (row, row, level_r, photon_r)
            )
        for col in range(DIMENSION):
            if col == row:
                continue
            level_c, photon_c = divmod(col, NPH)
            if abs(photon_r - photon_c) != 1 and (h_re[row][col] != 0.0 or h_im[row][col] != 0.0):
                raise _reject(
                    "baseline_H[%d][%d] is nonzero outside the declared g*n(a+a^dag) "
                    "coupling pattern" % (row, col)
                )
    skipped = sum(
        1
        for i in range(NQ)
        for j in range(NQ)
        if math.hypot(charge_re[i][j], charge_im[i][j]) < SKIP_THRESHOLD
    )
    if skipped != payload["baseline_diagnostics"]["skipped_charge_elements"]:
        raise _reject("baseline_diagnostics.skipped_charge_elements disagrees with the charge matrix")
    findings["skipped_charge_elements"] = skipped

    labels = payload["baseline_labels"]
    pairs = [(item["level"], item["photon"]) for item in labels]
    if sorted(pairs) != sorted(LABEL_PAIRS):
        raise _reject("baseline_labels must cover exactly (level, photon) in {0,1,2} x {0,1}")
    for item in labels:
        if item["bare_index"] != item["level"] * NPH + item["photon"]:
            raise _reject("baseline_labels: bare_index is not level*Nph + photon")
        if item["energy_GHz"] != eigenvalues[item["dressed_index"]]:
            raise _reject("baseline_labels: energy_GHz is not baseline_eigenvalues[dressed_index]")
        if item["runner_up_index"] == item["dressed_index"]:
            raise _reject("baseline_labels: runner_up_index equals dressed_index")
        if item["runner_up_overlap"] > item["overlap"]:
            raise _reject("baseline_labels: runner-up overlap exceeds the assigned overlap")
    dressed = [item["dressed_index"] for item in labels]
    duplicated = len(set(dressed)) != len(dressed)
    if duplicated != payload["baseline_diagnostics"]["duplicate_label_assignment"]:
        raise _reject("baseline_diagnostics.duplicate_label_assignment disagrees with baseline_labels")
    findings["duplicate_label_assignment"] = duplicated
    findings["label_margins"] = {
        "%d,%d" % (item["level"], item["photon"]): item["overlap"] - item["runner_up_overlap"]
        for item in labels
    }

    observables = payload["baseline_observables"]
    if observables["logical_pull_MHz"] != observables["pull_MHz_level%d" % LOGICAL_STATES[0]]:
        raise _reject("baseline_observables.logical_pull_MHz is not the level-0 pull")
    if observables["sink_pull_MHz"] != observables["pull_MHz_level%d" % SINK_STATE]:
        raise _reject("baseline_observables.sink_pull_MHz is not the level-1 pull")
    return findings


# ------------------------------------------------------------------- hash binding


def check_expected_hashes(
    payload: Dict[str, Any],
    snapshot_bytes: bytes,
    schema_bytes: bytes,
    expected: Dict[str, Any],
) -> None:
    """Compare measured hashes and declared provenance with the external record."""
    required = (
        "protocol_id", "snapshot_sha256", "schema_sha256", "source_commit",
        "source_file_hashes", "master_file_sha256", "baseline_implementation_hashes",
    )
    for key in required:
        if key not in expected:
            raise _blocked("expected-hashes record lacks %r" % key)
    if expected["protocol_id"] != PROTOCOL_ID:
        raise _reject("expected-hashes record is for protocol %r" % expected["protocol_id"])
    measured_snapshot = sha256_bytes(snapshot_bytes)
    if measured_snapshot != expected["snapshot_sha256"]:
        raise _reject(
            "snapshot bytes sha256 %s does not match the expected %s"
            % (measured_snapshot, expected["snapshot_sha256"])
        )
    measured_schema = sha256_bytes(schema_bytes)
    if measured_schema != expected["schema_sha256"]:
        raise _reject(
            "schema bytes sha256 %s does not match the expected %s"
            % (measured_schema, expected["schema_sha256"])
        )
    if payload["source_commit"] != expected["source_commit"]:
        raise _reject("source_commit does not match the expected commit")
    if payload["master_file_sha256"] != expected["master_file_sha256"]:
        raise _reject("master_file_sha256 does not match the expected master hash")
    if payload["source_file_hashes"].get(payload["master_file"]) != payload["master_file_sha256"]:
        raise _reject("master_file_sha256 disagrees with source_file_hashes")
    for key in ("source_file_hashes", "baseline_implementation_hashes"):
        declared = payload[key]
        wanted = expected[key]
        if not isinstance(wanted, dict) or set(declared) != set(wanted):
            raise _reject("%s: file set does not match the expected record" % key)
        for name in sorted(wanted):
            if declared[name] != wanted[name]:
                raise _reject("%s[%s]: hash mismatch" % (key, name))


# ------------------------------------------------------------------- validation


def validate(
    snapshot_path: Optional[str],
    schema_path: Optional[str],
    expected_path: Optional[str],
) -> Dict[str, Any]:
    """Every check that must pass before a calculation is allowed.

    Raises CheckFailure (BLOCKED or REJECTED). Returns the parsed payload and
    findings. Performs no numerical model calculation.
    """
    schema_bytes = read_required_file(schema_path, "schema file")
    expected_bytes = read_required_file(expected_path, "expected-hashes record")
    snapshot_bytes = read_required_file(snapshot_path, "reference snapshot")

    schema = strict_json_loads(schema_bytes, "schema")
    if not isinstance(schema, dict) or schema.get("$id") != SCHEMA_ID:
        raise _reject("schema file is not %s" % SCHEMA_ID)
    check_schema_keywords(schema)
    expected = strict_json_loads(expected_bytes, "expected-hashes record")
    if not isinstance(expected, dict):
        raise _reject("expected-hashes record is not a JSON object")
    payload = strict_json_loads(snapshot_bytes, "snapshot")
    if not isinstance(payload, dict):
        raise _reject("snapshot is not a JSON object")

    validate_schema(payload, schema)
    check_expected_hashes(payload, snapshot_bytes, schema_bytes, expected)
    findings = semantic_checks(payload)
    return {
        "payload": payload,
        "findings": findings,
        "snapshot_sha256": sha256_bytes(snapshot_bytes),
        "schema_sha256": sha256_bytes(schema_bytes),
    }


# ------------------------------------------------------------------ numerical parts
#
# Pure-NumPy helpers shared by the execution path. They take arrays and return
# numbers; they assemble nothing and search for nothing.


def label_states(eigenvectors: Any, nph: int, pairs: List[Tuple[int, int]]) -> Dict[str, Any]:
    """Maximum-bare-overlap labelling, the existing models/dressed_system.py rule.

    For each bare state (level, photon) the assigned dressed index is
    ``argmax_k |<bare|dressed_k>|^2`` (first maximum on exact ties). The runner-up
    is recorded so that near-ties are visible. Duplicate assignments are REPORTED,
    never repaired.
    """
    import numpy as np

    overlap = np.abs(np.asarray(eigenvectors)) ** 2
    labels = []
    for level, photon in pairs:
        bare = level * nph + photon
        row = overlap[bare, :]
        best = int(np.argmax(row))
        masked = row.copy()
        masked[best] = -1.0
        runner = int(np.argmax(masked))
        labels.append(
            {
                "level": level,
                "photon": photon,
                "bare_index": bare,
                "dressed_index": best,
                "overlap": float(row[best]),
                "runner_up_index": runner,
                "runner_up_overlap": float(row[runner]),
            }
        )
    assigned = [item["dressed_index"] for item in labels]
    duplicates = sorted({index for index in assigned if assigned.count(index) > 1})
    return {"labels": labels, "duplicate_dressed_indices": duplicates}


def label_quality(labels: List[Dict[str, Any]], min_overlap: float, min_margin: float) -> List[str]:
    """Label problems under the frozen ambiguity rule. Empty means unambiguous."""
    problems = []
    seen: Dict[int, Tuple[int, int]] = {}
    for item in labels:
        key = (item["level"], item["photon"])
        if item["dressed_index"] in seen:
            problems.append("DUPLICATE: %r and %r share dressed index %d"
                            % (seen[item["dressed_index"]], key, item["dressed_index"]))
        seen[item["dressed_index"]] = key
        if item["overlap"] < min_overlap:
            problems.append("LOW-OVERLAP: %r overlap %.6g < %.6g" % (key, item["overlap"], min_overlap))
        margin = item["overlap"] - item["runner_up_overlap"]
        if margin < min_margin:
            problems.append("AMBIGUOUS: %r margin %.6g < %.6g" % (key, margin, min_margin))
    return problems


def observables_from(eigenvalues: Any, eigenvectors: Any, labels: List[Dict[str, Any]],
                     readout: float, annihilation: Any) -> Dict[str, float]:
    """Named observables from a labelled dressed spectrum (brief §3)."""
    import numpy as np

    index = {(item["level"], item["photon"]): item["dressed_index"] for item in labels}
    energy = {key: float(eigenvalues[value]) for key, value in index.items()}
    pulls = [(energy[(level, 1)] - energy[(level, 0)] - readout) * 1e3 for level in range(3)]
    vectors = np.asarray(eigenvectors)
    element = vectors[:, index[(1, 0)]].conj() @ np.asarray(annihilation) @ vectors[:, index[(2, 0)]]
    return {
        "pull_MHz_level0": pulls[0],
        "pull_MHz_level1": pulls[1],
        "pull_MHz_level2": pulls[2],
        "logical_pull_MHz": pulls[LOGICAL_STATES[0]],
        "sink_pull_MHz": pulls[SINK_STATE],
        "sink_logical_contrast_MHz": pulls[SINK_STATE] - pulls[LOGICAL_STATES[0]],
        "sink_line_GHz": readout + pulls[SINK_STATE] / 1e3,
        "dressed_emission_GHz": energy[(2, 0)] - energy[(1, 0)],
        "f8_weight": float(abs(element) ** 2),
    }


OBSERVABLE_CHECKS = (
    "pull_MHz_level0", "pull_MHz_level1", "pull_MHz_level2", "sink_logical_contrast_MHz",
    "sink_line_GHz", "dressed_emission_GHz", "f8_weight",
)


def compare(independent: Dict[str, Any], baseline: Dict[str, Any], thresholds: Dict[str, float],
            labels_ok: bool = False) -> Dict[str, Any]:
    """Named absolute differences against the frozen thresholds. No blanket PASS.

    Observables depend on the state labels. Unless ``labels_ok`` is True (labels
    unambiguous under the frozen rule AND identical to the baseline assignment) the
    observable checks are NOT-EVALUATED; they never fall back to another assignment.
    """
    import numpy as np

    checks = {}

    def record(name: str, difference: float, limit_key: str) -> None:
        limit = thresholds[limit_key]
        verdict = "PASS" if difference <= limit else "FAIL"
        if name in OBSERVABLE_CHECKS and not labels_ok:
            verdict = "NOT-EVALUATED: labels ambiguous, duplicated or not identical to the baseline"
        checks[name] = {
            "abs_difference": difference,
            "limit": limit,
            "limit_rule": limit_key,
            "verdict": verdict,
        }

    record("hamiltonian_max_entry",
           float(np.max(np.abs(independent["H"] - baseline["H"]))),
           "max_hamiltonian_entry_abs_diff_GHz")
    record("ordered_eigenvalues_max",
           float(np.max(np.abs(independent["eigenvalues"] - baseline["eigenvalues"]))),
           "max_ordered_eigenvalue_abs_diff_GHz")
    for key in ("pull_MHz_level0", "pull_MHz_level1", "pull_MHz_level2", "sink_logical_contrast_MHz"):
        record(key, abs(independent["observables"][key] - baseline["observables"][key]),
               "max_pull_or_contrast_abs_diff_MHz")
    for key in ("sink_line_GHz", "dressed_emission_GHz"):
        record(key, abs(independent["observables"][key] - baseline["observables"][key]),
               "max_sink_line_or_emission_abs_diff_GHz")
    record("f8_weight", abs(independent["observables"]["f8_weight"] - baseline["observables"]["f8_weight"]),
           "max_f8_weight_abs_diff")
    return checks


def hermiticity_defect(matrix: Any) -> float:
    import numpy as np

    array = np.asarray(matrix)
    return float(np.max(np.abs(array - array.conj().T)))


def assemble_with_qutip(payload: Dict[str, Any], qutip: Any) -> Any:
    """Independent QuTiP assembly of the declared finite Hamiltonian.

        H/h [GHz] = F (x) I_Nph + f_R * I_Nq (x) num(Nph) + g * n_skip (x) (a + a^dag)

    Tensor order: fluxonium first, resonator second. ``num(Nph)`` is used for the
    photon number so that its diagonal is exactly 0..Nph-1 (``a.dag()*a`` rounds).
    ``n_skip`` is the unmodified charge matrix with elements below the declared
    threshold set to zero, the existing CEM assembly convention. Nothing is
    symmetrised, rephased or normalised.
    """
    import numpy as np

    frequencies = np.asarray(payload["frequencies_GHz"], dtype=float)
    charge = np.asarray(payload["charge_matrix_real"], dtype=float) + 1j * np.asarray(
        payload["charge_matrix_imag"], dtype=float
    )
    charge_skip = np.where(np.abs(charge) < payload["charge_element_skip_threshold"], 0.0, charge)
    core_options = getattr(qutip, "CoreOptions", None)
    if core_options is None:
        raise _blocked("this QuTiP has no CoreOptions; automatic tidy-up cannot be disabled")
    # QuTiP's automatic tidy-up would silently zero small entries after each
    # operation. The declared model omits ONLY charge elements below the threshold,
    # so tidy-up is switched off for the whole assembly.
    with core_options(auto_tidyup=False):
        fluxonium_energy = qutip.Qobj(np.diag(frequencies))
        charge_operator = qutip.Qobj(charge_skip)
        a = qutip.destroy(NPH)
        hamiltonian = (
            qutip.tensor(fluxonium_energy, qutip.qeye(NPH))
            + payload["readout_GHz"] * qutip.tensor(qutip.qeye(NQ), qutip.num(NPH))
            + payload["coupling_g_GHz"] * qutip.tensor(charge_operator, a + a.dag())
        )
    if [list(d) for d in hamiltonian.dims] != [[NQ, NPH], [NQ, NPH]]:
        raise _reject("QuTiP tensor dims %r are not fluxonium-first" % (hamiltonian.dims,))
    return hamiltonian


# ------------------------------------------------------------------- execution


def load_frozen_rules(path: Optional[str], expected_sha256: Optional[str]) -> Dict[str, Any]:
    """The separately approved rules. Absent or unbound rules BLOCK execution."""
    data = read_required_file(path, "frozen-rules file")
    if not expected_sha256:
        raise _blocked("the expected sha256 of the frozen-rules file was not supplied")
    measured = sha256_bytes(data)
    if measured != expected_sha256:
        raise _reject("frozen-rules sha256 %s does not match the expected %s" % (measured, expected_sha256))
    rules = strict_json_loads(data, "frozen-rules file")
    if not isinstance(rules, dict):
        raise _reject("frozen-rules file is not a JSON object")
    for key in FROZEN_RULES_REQUIRED:
        if key not in rules:
            raise _blocked("frozen-rules file lacks %r; execution stays BLOCKED" % key)
    if rules["protocol_id"] != PROTOCOL_ID:
        raise _reject("frozen-rules file is for protocol %r" % rules["protocol_id"])
    if rules["rules_status"] != FROZEN_RULES_STATUS:
        raise _blocked("frozen-rules status is %r, not %r; the PROPOSED rules are not approved and "
                       "execution stays BLOCKED" % (rules["rules_status"], FROZEN_RULES_STATUS))
    for key in ("label_min_overlap", "label_min_margin", "max_hamiltonian_hermiticity_defect_GHz",
                "wall_time_limit_s", "memory_limit_MB"):
        value = rules[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0:
            raise _reject("frozen-rules %s must be a positive number" % key)
    if rules["permitted_attempts"] != 1:
        raise _reject("frozen-rules file must permit exactly one attempt")
    if rules["eigensolver"] != "numpy.linalg.eigh (UPLO='L') on Qobj.full()":
        raise _reject("frozen-rules eigensolver %r is not the declared dense solver" % rules["eigensolver"])
    thresholds = rules["thresholds"]
    if not isinstance(thresholds, dict) or set(thresholds) != set(PROPOSED_ENGINEERING_RULES):
        raise _reject("frozen-rules thresholds must name exactly %r" % sorted(PROPOSED_ENGINEERING_RULES))
    for key, value in thresholds.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0:
            raise _reject("frozen-rules threshold %s must be a positive number" % key)
    return rules


def _utc_now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _write_json(path: str, value: Any) -> None:
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, allow_nan=False)
        handle.write("\n")


def _write_manifest(root: str) -> str:
    """sha256sum-format manifest over the record, sorted by relative POSIX path.

    Mirrors the orchestrator/manifest.py convention without importing it.
    """
    entries = []
    for directory, _dirs, files in os.walk(root):
        for name in files:
            if name == "manifest.sha256":
                continue
            full = os.path.join(directory, name)
            relative = os.path.relpath(full, root).replace(os.sep, "/")
            with open(full, "rb") as handle:
                entries.append((relative, sha256_bytes(handle.read())))
    body = "".join("%s  %s\n" % (digest, relative) for relative, digest in sorted(entries))
    with open(os.path.join(root, "manifest.sha256"), "x", encoding="utf-8") as handle:
        handle.write(body)
    return sha256_bytes(body.encode("utf-8"))


def runtime_identity() -> Dict[str, Any]:
    identity: Dict[str, Any] = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    for name in ("numpy", "scipy", "qutip"):
        try:
            module = __import__(name)
            identity["%s_version" % name] = getattr(module, "__version__", "unknown")
        except ImportError:
            identity["%s_version" % name] = None
    return identity


def execute(validated: Dict[str, Any], rules: Dict[str, Any], output_dir: str,
            rules_sha256: Optional[str] = None) -> Dict[str, Any]:
    """The QuTiP calculation. Reached only after validation and frozen rules.

    Writes an append-only record into a NEW directory: the attempt marker first,
    then raw outputs, then the named checks, then the manifest. A failure is
    preserved, never retried. The in-process timer is not a hard stop; the wall and
    memory limits must be enforced by the approved external launcher.
    """
    payload = validated["payload"]
    if payload["payload_kind"] != "CEM-EXPORT":
        raise _reject("payload_kind %r cannot be executed; synthetic fixtures are never evidence"
                      % payload["payload_kind"])
    if os.path.exists(output_dir):
        raise _reject("output directory %s already exists; a record is never overwritten" % output_dir)
    os.makedirs(output_dir)
    attempt = {
        "protocol_id": PROTOCOL_ID,
        "attempt": 1,
        "status": "STARTED",
        "started_utc": _utc_now(),
        "snapshot_sha256": validated["snapshot_sha256"],
        "schema_sha256": validated["schema_sha256"],
        "frozen_rules": rules,
        "frozen_rules_sha256": rules_sha256,
        "runtime": runtime_identity(),
    }
    _write_json(os.path.join(output_dir, "attempt.json"), attempt)
    started = time.monotonic()
    result: Dict[str, Any] = {"protocol_id": PROTOCOL_ID, "snapshot_sha256": validated["snapshot_sha256"]}
    try:
        import numpy as np
        import qutip

        hamiltonian = assemble_with_qutip(payload, qutip)
        independent_h = hamiltonian.full()
        eigenvalues, eigenvectors = np.linalg.eigh(independent_h, UPLO="L")
        labelled = label_states(eigenvectors, NPH, LABEL_PAIRS)
        annihilation = qutip.tensor(qutip.qeye(NQ), qutip.destroy(NPH)).full()
        independent = {
            "H": independent_h,
            "eigenvalues": eigenvalues,
            "observables": observables_from(eigenvalues, eigenvectors, labelled["labels"],
                                            payload["readout_GHz"], annihilation),
        }
        baseline = {
            "H": np.asarray(payload["baseline_H_real"]) + 1j * np.asarray(payload["baseline_H_imag"]),
            "eigenvalues": np.asarray(payload["baseline_eigenvalues"]),
            "observables": payload["baseline_observables"],
        }
        result["raw"] = {
            "eigenvalues_GHz": [float(value) for value in eigenvalues],
            "labels": labelled["labels"],
            "duplicate_dressed_indices": labelled["duplicate_dressed_indices"],
            "observables": independent["observables"],
            "independent_hamiltonian_hermiticity_defect_GHz": hermiticity_defect(independent_h),
            "baseline_hamiltonian_hermiticity_defect_GHz": hermiticity_defect(baseline["H"]),
        }
        _write_json(os.path.join(output_dir, "raw.json"), result["raw"])
        result["label_problems"] = label_quality(labelled["labels"], rules["label_min_overlap"],
                                                 rules["label_min_margin"])
        result["label_assignment_matches_baseline"] = [
            (item["level"], item["photon"], item["dressed_index"]) for item in labelled["labels"]
        ] == [
            (item["level"], item["photon"], item["dressed_index"]) for item in payload["baseline_labels"]
        ]
        labels_ok = not result["label_problems"] and result["label_assignment_matches_baseline"]
        result["checks"] = compare(independent, baseline, rules["thresholds"], labels_ok=labels_ok)
        result["checks_rule_basis"] = "frozen-rules sha256 %s (%s)" % (rules_sha256, rules["rules_status"])
        result["hermiticity_within_rule"] = (
            result["raw"]["independent_hamiltonian_hermiticity_defect_GHz"]
            <= rules["max_hamiltonian_hermiticity_defect_GHz"]
        )
        result["execution_status"] = "COMPLETED"
    except Exception as exc:  # preserved, never retried
        result["execution_status"] = "EXECUTION-FAILED"
        result["error"] = "%s: %s" % (type(exc).__name__, exc)
    result["wall_seconds_in_process"] = time.monotonic() - started
    result["provenance_qualification"] = (
        "INPUTS-HASH-VERIFIED (runtime identity recorded, not qualified against a frozen expectation)"
        if result["execution_status"] == "COMPLETED" else "NOT-QUALIFIED"
    )
    result["scientific_verdict"] = (
        "NOT ISSUED BY THIS TOOL: named checks are reported individually; any verdict is a "
        "separately reviewed human decision"
    )
    result["scope"] = payload["evidence_scope"]
    result["ended_utc"] = _utc_now()
    _write_json(os.path.join(output_dir, "result.json"), result)
    result["manifest_sha256"] = _write_manifest(output_dir)
    return result


# ------------------------------------------------------------------------- CLI


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", help="reference snapshot JSON exported by the CEM environment")
    parser.add_argument("--schema", help="schemas/qutip/branch-a-reference-v1.schema.json")
    parser.add_argument("--expected", help="external expected-hashes record (JSON)")
    parser.add_argument("--execute", action="store_true",
                        help="run the QuTiP calculation after validation (requires frozen rules)")
    parser.add_argument("--frozen-rules", help="separately approved frozen-rules JSON")
    parser.add_argument("--frozen-rules-sha256", help="expected sha256 of the frozen-rules bytes")
    parser.add_argument("--output", help="NEW directory for the execution record")
    args = parser.parse_args(argv)

    try:
        validated = validate(args.snapshot, args.schema, args.expected)
    except CheckFailure as failure:
        print("%s: %s" % (failure.status, failure))
        return EXIT_BLOCKED if failure.status == "BLOCKED" else EXIT_REJECTED
    print("VALIDATED: %s (snapshot sha256 %s); no calculation performed"
          % (validated["payload"]["protocol_id"], validated["snapshot_sha256"]))
    if not args.execute:
        return EXIT_OK

    try:
        rules = load_frozen_rules(args.frozen_rules, args.frozen_rules_sha256)
        if not args.output:
            raise _blocked("--output was not supplied")
        result = execute(validated, rules, args.output, args.frozen_rules_sha256)
    except CheckFailure as failure:
        print("%s: %s" % (failure.status, failure))
        return EXIT_BLOCKED if failure.status == "BLOCKED" else EXIT_REJECTED
    print("%s; record at %s (manifest sha256 %s)"
          % (result["execution_status"], args.output, result["manifest_sha256"]))
    return EXIT_OK if result["execution_status"] == "COMPLETED" else EXIT_EXECUTION_FAILED


if __name__ == "__main__":
    sys.exit(main())
