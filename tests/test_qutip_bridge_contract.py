# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Contract tests for the QUTIP-A-READOUT-CROSSCHECK-v1 bridge.

SYNTHETIC FIXTURES ONLY. Every payload here is built from made-up frequencies and a
seeded random charge matrix, carries ``payload_kind: SYNTHETIC-TEST-FIXTURE``, lives
in ``tmp_path`` and is never evidence. No Branch-A physics export, no QuTiP evidence
calculation and no root search is performed. The test-side matrix assembly is an
oracle for the synthetic fixture, not a physics result.

Each acceptance or refusal gate has a positive control and at least one intended
negative control (AGENTS.md §7).
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
CHECKER_PATH = REPO / "tools" / "qutip_bridge" / "check_branch_a_reference.py"
EXPORTER_PATH = REPO / "scripts" / "export_qutip_branch_a_reference.py"
SCHEMA_PATH = REPO / "schemas" / "qutip" / "branch-a-reference-v1.schema.json"
DOC_PATH = REPO / "docs" / "qutip" / "branch-a-fixed-point-crosscheck-v1.md"

NQ, NPH, DIM = 10, 12, 120
READOUT = 4.301974466
G = 0.15
CEM_PACKAGES = {"contracts", "models", "orchestrator", "evaluator", "geometry", "solvers"}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load(CHECKER_PATH, "qutip_bridge_checker_under_test")
exporter = _load(EXPORTER_PATH, "qutip_bridge_exporter_under_test")


# --------------------------------------------------------------- synthetic fixture


def _oracle_hamiltonian(frequencies, charge, readout=READOUT, g=G):
    """Test oracle mirroring the declared assembly, for SYNTHETIC inputs only."""
    a = np.diag(np.sqrt(np.arange(1, NPH)), 1)
    x = a + a.T
    h = np.zeros((DIM, DIM), dtype=complex)
    for level in range(NQ):
        for photon in range(NPH):
            index = level * NPH + photon
            h[index, index] = frequencies[level] + readout * photon
    for i in range(NQ):
        for j in range(NQ):
            if abs(charge[i, j]) < 1e-14:
                continue
            h[i * NPH:(i + 1) * NPH, j * NPH:(j + 1) * NPH] += g * charge[i, j] * x
    return h


def _synthetic(seed: int = 7):
    rng = np.random.default_rng(seed)
    frequencies = np.concatenate([[0.0], np.sort(rng.uniform(0.2, 25.0, NQ - 1))])
    antisymmetric = rng.normal(size=(NQ, NQ))
    antisymmetric = antisymmetric - antisymmetric.T
    antisymmetric[0, 5] = antisymmetric[5, 0] = 0.0
    charge = -1j * antisymmetric
    hamiltonian = _oracle_hamiltonian(frequencies, charge)
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    labelled = checker.label_states(eigenvectors, NPH, checker.LABEL_PAIRS)
    labels = [dict(item, energy_GHz=float(eigenvalues[item["dressed_index"]]))
              for item in labelled["labels"]]
    annihilation = np.kron(np.eye(NQ), np.diag(np.sqrt(np.arange(1, NPH)), 1))
    observables = checker.observables_from(eigenvalues, eigenvectors, labels, READOUT, annihilation)
    return {
        "frequencies": frequencies,
        "charge": charge,
        "hamiltonian": hamiltonian,
        "eigenvalues": eigenvalues,
        "eigenvectors": eigenvectors,
        "labels": labels,
        "observables": observables,
    }


def _payload(seed: int = 7) -> dict:
    data = _synthetic(seed)
    provenance = {
        "source_commit": "0" * 40,
        "source_tree_clean": True,
        "source_file_hashes": {name: hashlib.sha256(name.encode()).hexdigest()
                               for name in exporter.SOURCE_FILES},
        "baseline_implementation_hashes": {name: hashlib.sha256(b"impl:" + name.encode()).hexdigest()
                                           for name in exporter.IMPLEMENTATION_FILES},
    }
    runtime = {
        "python_version": "synthetic", "numpy_version": "synthetic", "scipy_version": "synthetic",
        "platform": "synthetic", "started_utc": "2026-01-01T00:00:00.0Z",
        "ended_utc": "2026-01-01T00:00:01.0Z", "wall_seconds": 1.0,
    }
    return exporter.build_payload(
        payload_kind="SYNTHETIC-TEST-FIXTURE",
        frequencies=data["frequencies"],
        charge_matrix=data["charge"],
        hamiltonian=data["hamiltonian"],
        eigenvalues=data["eigenvalues"],
        labels=data["labels"],
        observables=data["observables"],
        provenance=provenance,
        runtime=runtime,
        eigh_calls=1,
    )


@pytest.fixture(scope="module")
def base_payload() -> dict:
    return _payload()


def _expected_record(payload: dict, snapshot_bytes: bytes) -> dict:
    return {
        "protocol_id": checker.PROTOCOL_ID,
        "snapshot_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        "schema_sha256": hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(),
        "source_commit": payload["source_commit"],
        "source_file_hashes": dict(payload["source_file_hashes"]),
        "master_file_sha256": payload["master_file_sha256"],
        "baseline_implementation_hashes": dict(payload["baseline_implementation_hashes"]),
    }


def _write(tmp_path: Path, payload=None, *, raw: bytes | None = None, expected: dict | None = None,
           schema: Path = SCHEMA_PATH):
    snapshot_bytes = raw if raw is not None else json.dumps(payload).encode()
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_bytes(snapshot_bytes)
    if expected is None:
        expected = _expected_record(payload, snapshot_bytes)
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(json.dumps(expected))
    return str(snapshot), str(schema), str(expected_path)


def _status(tmp_path: Path, payload=None, **kwargs) -> tuple[str, str]:
    try:
        checker.validate(*_write(tmp_path, payload, **kwargs))
    except checker.CheckFailure as failure:
        return failure.status, str(failure)
    return "VALIDATED", ""


def _mutated(payload: dict, mutate) -> dict:
    changed = copy.deepcopy(payload)
    mutate(changed)
    return changed


# ------------------------------------------------------------------ positive control


def test_consistent_synthetic_payload_validates(tmp_path, base_payload):
    result = checker.validate(*_write(tmp_path, base_payload))
    assert result["payload"]["payload_kind"] == "SYNTHETIC-TEST-FIXTURE"
    assert result["findings"]["skipped_charge_elements"] == 12  # 10 diagonal + the zeroed pair


def test_schema_uses_only_enforced_keywords_and_matches_exporter_fields(base_payload):
    schema = checker.strict_json_loads(SCHEMA_PATH.read_bytes(), "schema")
    checker.check_schema_keywords(schema)
    assert set(schema["required"]) == set(schema["properties"]) == set(base_payload)


def test_schema_with_an_unenforced_keyword_is_rejected(tmp_path, base_payload):
    schema = json.loads(SCHEMA_PATH.read_text())
    schema["properties"]["Nq"]["multipleOf"] = 2
    altered = tmp_path / "schema.json"
    altered.write_text(json.dumps(schema))
    status, message = _status(tmp_path, base_payload, schema=altered)
    assert status == "REJECTED" and "multipleOf" in message


# ------------------------------------------------------------------ missing inputs


def test_missing_snapshot_is_blocked_not_generated(tmp_path):
    expected = tmp_path / "expected.json"
    expected.write_text("{}")
    with pytest.raises(checker.CheckFailure) as info:
        checker.validate(str(tmp_path / "absent.json"), str(SCHEMA_PATH), str(expected))
    assert info.value.status == "BLOCKED"
    assert not (tmp_path / "absent.json").exists()


def test_missing_expected_record_is_blocked(tmp_path, base_payload):
    snapshot, schema, _ = _write(tmp_path, base_payload)
    with pytest.raises(checker.CheckFailure) as info:
        checker.validate(snapshot, schema, None)
    assert info.value.status == "BLOCKED"


# ------------------------------------------------------------ shape and completeness


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["charge_matrix_real"].pop(),                      # 9 rows
        lambda p: p["charge_matrix_imag"][3].pop(),                   # missing entry
        lambda p: p["baseline_H_real"][0].pop(),                      # 119 columns
        lambda p: p["baseline_H_imag"].append([0.0] * DIM),           # 121 rows
        lambda p: p["frequencies_GHz"].pop(),                         # 9 frequencies
        lambda p: p["baseline_eigenvalues"].pop(),
        lambda p: p.pop("charge_matrix_imag"),                        # missing field
        lambda p: p.pop("baseline_runtime"),
        lambda p: p["baseline_labels"].pop(),
    ],
    ids=["charge-9-rows", "charge-missing-entry", "H-119-cols", "H-121-rows", "freq-9",
         "eigs-119", "missing-imag-field", "missing-runtime", "5-labels"],
)
def test_malformed_dimensions_and_missing_fields_are_rejected(tmp_path, base_payload, mutate):
    status, _ = _status(tmp_path, _mutated(base_payload, mutate))
    assert status == "REJECTED"


# ------------------------------------------------------------------ non-finite values


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_non_finite_numbers_are_rejected(tmp_path, base_payload, token):
    text = json.dumps(base_payload).replace('"readout_GHz": 4.301974466', '"readout_GHz": %s' % token, 1)
    assert token in text
    status, message = _status(tmp_path, raw=text.encode(), expected=_expected_record(base_payload, text.encode()))
    assert status == "REJECTED"


def test_duplicate_json_key_is_rejected(tmp_path, base_payload):
    text = json.dumps(base_payload)
    text = text.replace('"Nq": 10,', '"Nq": 10, "Nq": 10,', 1)
    status, message = _status(tmp_path, raw=text.encode(), expected=_expected_record(base_payload, text.encode()))
    assert status == "REJECTED" and "duplicate" in message


# ------------------------------------------------------------ declared conventions


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.__setitem__("tensor_order", ["resonator", "fluxonium"]),
        lambda p: p.__setitem__("flat_index", "photon*Nq + level"),
        lambda p: p["units"].__setitem__("hamiltonian", "MHz (H/h)"),
        lambda p: p["units"].__setitem__("pulls", "GHz"),
        lambda p: p.__setitem__("protocol_id", "QUTIP-A-READOUT-CROSSCHECK-v2"),
        lambda p: p.__setitem__("readout_GHz", 4.3019745),            # altered fixed point
        lambda p: p.__setitem__("readout_GHz", 430.1974466),          # x100 corruption
        lambda p: p.__setitem__("readout_GHz", "4.301974466"),        # text for number
        lambda p: p.__setitem__("Nq", 10.0),                          # integer to float
        lambda p: p.__setitem__("EC_over_h_GHz", True),               # boolean for number
        lambda p: p.__setitem__("root_search_performed", True),
        lambda p: p.__setitem__("coupling_is_geometry_derived", True),
        lambda p: p.__setitem__("coupling_classification", "S1-EXTRACTED"),
        lambda p: p.__setitem__("charge_element_skip_threshold", 1e-12),
        lambda p: p["baseline_H_real"][0].__setitem__(1, "0.0"),     # text inside matrix
    ],
    ids=["tensor-order", "flat-index", "hamiltonian-units", "pull-units", "protocol",
         "readout-altered", "readout-x100", "readout-text", "Nq-float", "EC-bool",
         "root-search-flag", "geometry-derived-g", "g-relabelled-S1", "skip-threshold",
         "matrix-text"],
)
def test_declared_conventions_are_enforced(tmp_path, base_payload, mutate):
    status, _ = _status(tmp_path, _mutated(base_payload, mutate))
    assert status == "REJECTED"


# -------------------------------------------------------------------- hash binding


def test_snapshot_bytes_hash_mismatch_is_rejected(tmp_path, base_payload):
    expected = _expected_record(base_payload, json.dumps(base_payload).encode())
    expected["snapshot_sha256"] = "f" * 64
    status, message = _status(tmp_path, base_payload, expected=expected)
    assert status == "REJECTED" and "snapshot bytes" in message


def test_schema_hash_mismatch_is_rejected(tmp_path, base_payload):
    expected = _expected_record(base_payload, json.dumps(base_payload).encode())
    expected["schema_sha256"] = "e" * 64
    status, message = _status(tmp_path, base_payload, expected=expected)
    assert status == "REJECTED" and "schema bytes" in message


@pytest.mark.parametrize(
    "field,key",
    [("source_file_hashes", "models/dressed_system.py"),
     ("source_file_hashes", "master/qmhp_v158f_requirements.yaml"),
     ("baseline_implementation_hashes", "scripts/export_qutip_branch_a_reference.py")],
)
def test_source_hash_mismatch_is_rejected(tmp_path, base_payload, field, key):
    expected = _expected_record(base_payload, json.dumps(base_payload).encode())
    expected[field][key] = "d" * 64
    if key.startswith("master/"):
        expected["master_file_sha256"] = "d" * 64
    status, message = _status(tmp_path, base_payload, expected=expected)
    assert status == "REJECTED"


def test_source_commit_mismatch_is_rejected(tmp_path, base_payload):
    expected = _expected_record(base_payload, json.dumps(base_payload).encode())
    expected["source_commit"] = "1" * 40
    assert _status(tmp_path, base_payload, expected=expected)[0] == "REJECTED"


def test_expected_record_missing_a_hash_is_blocked(tmp_path, base_payload):
    expected = _expected_record(base_payload, json.dumps(base_payload).encode())
    expected.pop("source_file_hashes")
    assert _status(tmp_path, base_payload, expected=expected)[0] == "BLOCKED"


# ----------------------------------------------------------------- altered baseline


def test_altered_baseline_without_rehash_is_rejected_by_the_hash(tmp_path, base_payload):
    original_bytes = json.dumps(base_payload).encode()
    altered = _mutated(base_payload, lambda p: p["baseline_H_real"][0].__setitem__(13, 0.123))
    status, message = _status(tmp_path, altered, expected=_expected_record(base_payload, original_bytes))
    assert status == "REJECTED" and "snapshot bytes" in message


@pytest.mark.parametrize(
    "row,col",
    [(0, 0), (5, 5), (0, 2), (0, 24)],
    ids=["diagonal-0", "diagonal-5", "outside-pattern-same-block", "outside-pattern-other-block"],
)
def test_altered_baseline_with_rehash_fails_structural_check(tmp_path, base_payload, row, col):
    altered = _mutated(base_payload, lambda p: p["baseline_H_real"][row].__setitem__(col, 1e-9 + p["baseline_H_real"][row][col]))
    status, message = _status(tmp_path, altered)
    assert status == "REJECTED" and "baseline_H" in message


def test_altered_coupling_entry_with_rehash_is_caught_by_the_comparator(base_payload):
    """An entry inside the allowed pattern passes the structural check; the named
    Hamiltonian comparison is what must catch it."""
    data = _synthetic()
    baseline_h = data["hamiltonian"].copy()
    baseline_h[0, 13] += 1e-9
    independent = {"H": data["hamiltonian"], "eigenvalues": data["eigenvalues"], "observables": data["observables"]}
    baseline = {"H": baseline_h, "eigenvalues": data["eigenvalues"], "observables": data["observables"]}
    checks = checker.compare(independent, baseline, checker.PROPOSED_ENGINEERING_RULES)
    assert checks["hamiltonian_max_entry"]["verdict"] == "FAIL"
    assert checks["ordered_eigenvalues_max"]["verdict"] == "PASS"
    unaltered = checker.compare(independent, independent, checker.PROPOSED_ENGINEERING_RULES, labels_ok=True)
    assert all(item["verdict"] == "PASS" for item in unaltered.values())


def test_comparator_reports_named_checks_not_a_blanket_verdict(base_payload):
    data = _synthetic()
    same = {"H": data["hamiltonian"], "eigenvalues": data["eigenvalues"], "observables": data["observables"]}
    checks = checker.compare(same, same, checker.PROPOSED_ENGINEERING_RULES)
    assert set(checks) == {
        "hamiltonian_max_entry", "ordered_eigenvalues_max", "pull_MHz_level0", "pull_MHz_level1",
        "pull_MHz_level2", "sink_logical_contrast_MHz", "sink_line_GHz", "dressed_emission_GHz",
        "f8_weight",
    }


def test_inconsistent_diagnostics_are_rejected(tmp_path, base_payload):
    for mutate in (
        lambda p: p["baseline_diagnostics"].__setitem__("skipped_charge_elements", 11),
        lambda p: p["baseline_diagnostics"].__setitem__("duplicate_label_assignment", True),
        lambda p: p["baseline_observables"].__setitem__("logical_pull_MHz", 0.0),
        lambda p: p["baseline_labels"][0].__setitem__("energy_GHz", 0.5),
    ):
        assert _status(tmp_path, _mutated(base_payload, mutate))[0] == "REJECTED"


# --------------------------------------------------------------------- labelling


def test_duplicate_assignment_is_reported_not_repaired():
    vectors = np.eye(DIM)
    vectors[0, 0], vectors[1, 1] = 0.6, 0.3
    vectors[1, 0] = 0.7                     # bare (0,1) now also peaks at dressed 0
    result = checker.label_states(vectors, NPH, [(0, 0), (0, 1)])
    assert result["duplicate_dressed_indices"] == [0]
    problems = checker.label_quality(result["labels"], min_overlap=0.1, min_margin=0.01)
    assert any(problem.startswith("DUPLICATE") for problem in problems)


def test_near_tie_is_reported_as_ambiguous():
    vectors = np.eye(DIM)
    vectors[0, 0], vectors[0, 1] = np.sqrt(0.50), np.sqrt(0.49)
    result = checker.label_states(vectors, NPH, [(0, 0)])
    assert result["labels"][0]["runner_up_index"] == 1
    problems = checker.label_quality(result["labels"], min_overlap=0.1, min_margin=0.05)
    assert any(problem.startswith("AMBIGUOUS") for problem in problems)
    assert checker.label_quality(result["labels"], min_overlap=0.1, min_margin=0.001) == []


def test_payload_with_duplicate_labels_validates_but_reports_them(tmp_path, base_payload):
    def duplicate(p):
        p["baseline_labels"][1]["dressed_index"] = p["baseline_labels"][0]["dressed_index"]
        p["baseline_labels"][1]["energy_GHz"] = p["baseline_labels"][0]["energy_GHz"]
        if p["baseline_labels"][1]["runner_up_index"] == p["baseline_labels"][1]["dressed_index"]:
            p["baseline_labels"][1]["runner_up_index"] = p["baseline_labels"][0]["runner_up_index"]
        p["baseline_diagnostics"]["duplicate_label_assignment"] = True

    result = checker.validate(*_write(tmp_path, _mutated(base_payload, duplicate)))
    assert result["findings"]["duplicate_label_assignment"] is True


# --------------------------------------------------------------- execution gates


def test_synthetic_payload_is_never_executed(tmp_path, base_payload):
    validated = checker.validate(*_write(tmp_path, base_payload))
    output = tmp_path / "run"
    with pytest.raises(checker.CheckFailure) as info:
        checker.execute(validated, {"thresholds": checker.PROPOSED_ENGINEERING_RULES}, str(output))
    assert info.value.status == "REJECTED" and not output.exists()


def _rules(**overrides) -> dict:
    rules = {
        "protocol_id": checker.PROTOCOL_ID,
        "rules_status": checker.FROZEN_RULES_STATUS,
        "approval_reference": "synthetic",
        "thresholds": dict(checker.PROPOSED_ENGINEERING_RULES),
        "label_min_overlap": 0.5,
        "label_min_margin": 0.1,
        "max_hamiltonian_hermiticity_defect_GHz": 1e-12,
        "wall_time_limit_s": 60,
        "memory_limit_MB": 512,
        "permitted_attempts": 1,
        "eigensolver": "numpy.linalg.eigh (UPLO='L') on Qobj.full()",
    }
    rules.update(overrides)
    return rules


def _rules_file(tmp_path: Path, rules: dict) -> tuple[str, str]:
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(rules))
    return str(path), hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_rules_gate(tmp_path):
    path, digest = _rules_file(tmp_path, _rules())
    assert checker.load_frozen_rules(path, digest)["permitted_attempts"] == 1
    with pytest.raises(checker.CheckFailure) as info:
        checker.load_frozen_rules(None, None)
    assert info.value.status == "BLOCKED"
    with pytest.raises(checker.CheckFailure) as info:
        checker.load_frozen_rules(path, None)
    assert info.value.status == "BLOCKED"
    with pytest.raises(checker.CheckFailure) as info:
        checker.load_frozen_rules(path, "0" * 64)
    assert info.value.status == "REJECTED"
    for bad, status in (
        (_rules(permitted_attempts=2), "REJECTED"),
        (_rules(eigensolver="qutip.Qobj.eigenenergies"), "REJECTED"),
        ({k: v for k, v in _rules().items() if k != "wall_time_limit_s"}, "BLOCKED"),
        (_rules(thresholds={"max_hamiltonian_entry_abs_diff_GHz": 1e-12}), "REJECTED"),
        ({k: v for k, v in _rules().items() if k != "rules_status"}, "BLOCKED"),
        (_rules(rules_status="PROPOSED ENGINEERING-RULE"), "BLOCKED"),
        (_rules(rules_status="MASTER-FROZEN"), "BLOCKED"),
        (_rules(label_min_margin=0), "REJECTED"),
        (_rules(wall_time_limit_s=True), "REJECTED"),
    ):
        path_bad, digest_bad = _rules_file(tmp_path, bad)
        with pytest.raises(checker.CheckFailure) as info:
            checker.load_frozen_rules(path_bad, digest_bad)
        assert info.value.status == status


def test_cli_without_execute_performs_no_calculation(tmp_path, base_payload, capsys):
    snapshot, schema, expected = _write(tmp_path, base_payload)
    code = checker.main(["--snapshot", snapshot, "--schema", schema, "--expected", expected])
    assert code == checker.EXIT_OK
    assert "no calculation performed" in capsys.readouterr().out
    assert sorted(p.name for p in tmp_path.iterdir()) == ["expected.json", "snapshot.json"]


def test_cli_exit_codes_for_blocked_and_rejected(tmp_path, base_payload):
    assert checker.main([]) == checker.EXIT_BLOCKED
    bad = _mutated(base_payload, lambda p: p.__setitem__("tensor_order", ["resonator", "fluxonium"]))
    snapshot, schema, expected = _write(tmp_path, bad)
    assert checker.main(["--snapshot", snapshot, "--schema", schema, "--expected", expected]) == checker.EXIT_REJECTED


# ----------------------------------------------- isolation of the standalone checker


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def test_checker_parses_as_python_3_9():
    ast.parse(CHECKER_PATH.read_text(), feature_version=(3, 9))
    for node in ast.walk(_tree(CHECKER_PATH)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "zip":
            assert not any(k.arg == "strict" for k in node.keywords), "zip(strict=) is Python 3.10+"


def test_checker_imports_no_cem_module_and_no_forbidden_capability():
    allowed = {"__future__", "argparse", "datetime", "hashlib", "json", "math", "os", "platform",
               "re", "sys", "time", "typing", "numpy", "qutip"}
    for node in ast.walk(_tree(CHECKER_PATH)):
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        else:
            continue
        assert set(names) <= allowed, names
    # Scan code identifiers, not docstrings (which state what is forbidden).
    identifiers = set()
    for node in ast.walk(_tree(CHECKER_PATH)):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            identifiers.update(alias.name for alias in node.names)
            identifiers.add(getattr(node, "module", None) or "")
    forbidden = {"pickle", "eval", "exec", "compile", "brentq", "optimize", "fsolve", "root_scalar",
                 "minimize", "urllib", "urlopen", "subprocess", "loads_pickle", "marshal", "shelve"}
    assert not identifiers & forbidden, identifiers & forbidden


def test_checker_keeps_numpy_and_qutip_out_of_module_scope():
    module_level = [node for node in _tree(CHECKER_PATH).body if isinstance(node, (ast.Import, ast.ImportFrom))]
    names = {alias.name for node in module_level for alias in node.names}
    assert not names & {"numpy", "qutip", "scipy"}


def test_checker_runs_in_a_fresh_interpreter_without_importing_cem(tmp_path):
    probe = (
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('c', %r)\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "code = m.main([])\n"
        "print(code, sorted(set(sys.modules) & %r))\n" % (str(CHECKER_PATH), CEM_PACKAGES | {"numpy", "qutip"})
    )
    out = subprocess.run([sys.executable, "-I", "-c", probe], cwd=tmp_path, capture_output=True,
                         text=True, check=True).stdout
    assert out.strip().splitlines()[-1] == "2 []"


# ------------------------------------------------------------------- the exporter


class _FakeDressedModule:
    """Stand-in for models.dressed_system; performs no physics."""

    la = np.linalg

    def solve_dressed_root(self, *args, **kwargs):
        return 4.3

    nominal_root = nominal_solution = dressed_spectrum = brentq = solve_dressed_root

    def fixed_point(self):
        return self.la.eigh(np.eye(2))

    def twice(self):
        self.la.eigh(np.eye(2))
        return self.la.eigh(np.eye(2))

    def with_root_search(self):
        return self.solve_dressed_root()


def test_guard_captures_exactly_one_hamiltonian_and_restores():
    fake = _FakeDressedModule()
    with exporter.fixed_point_guard(fake) as captured:
        fake.fixed_point()
    assert len(captured) == 1 and np.array_equal(captured[0], np.eye(2))
    assert fake.la is np.linalg and fake.solve_dressed_root() == 4.3


@pytest.mark.parametrize("method", ["twice", "with_root_search"])
def test_guard_refuses_root_search_and_repeated_solves(method):
    fake = _FakeDressedModule()
    with pytest.raises(exporter.RootSearchForbidden):
        with exporter.fixed_point_guard(fake):
            getattr(fake, method)()


@pytest.mark.parametrize("entry", ["nominal_solution", "dressed_spectrum", "solve_dressed_root", "nominal_root"])
def test_guard_blocks_the_real_root_search_entry_points(entry):
    from models import dressed_system

    original = getattr(dressed_system, entry)
    with pytest.raises(exporter.RootSearchForbidden):
        with exporter.fixed_point_guard(dressed_system):
            getattr(dressed_system, entry)()
    assert getattr(dressed_system, entry) is original and dressed_system.la is not None


def test_exporter_never_calls_root_search_entry_points_directly():
    tree = _tree(EXPORTER_PATH)
    called = {getattr(node.func, "attr", getattr(node.func, "id", None))
              for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert not called & {"nominal_solution", "dressed_spectrum", "solve_dressed_root", "nominal_root", "brentq"}
    assert "solve_dressed" in called


def test_exporter_output_path_refusals(tmp_path):
    for bad in (REPO / "results" / "QUTIP", REPO / "master" / "x", REPO / "results"):
        with pytest.raises(exporter.ExportRefused):
            exporter.check_output_path(bad)
    existing = tmp_path / "exists"
    existing.mkdir()
    with pytest.raises(exporter.ExportRefused):
        exporter.check_output_path(existing)
    assert exporter.check_output_path(tmp_path / "new") == (tmp_path / "new").resolve()


def test_exporter_dry_run_performs_no_solve(monkeypatch, capsys):
    from models import dressed_system, fluxonium

    def refuse(*_args, **_kwargs):
        raise AssertionError("a solve was attempted during a dry run")

    for module, name in ((fluxonium, "nominal_spectrum"), (fluxonium, "solve_static"),
                         (dressed_system, "solve_dressed")):
        monkeypatch.setattr(module, name, refuse)
    assert exporter.main(["--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"].startswith("DRY-RUN") and report["fixed_readout_GHz"] == READOUT


def test_exporter_execute_is_blocked_without_approval(tmp_path, capsys):
    output = tmp_path / "export"
    assert exporter.main(["--execute", "--output", str(output)]) == 2
    assert "BLOCKED" in capsys.readouterr().out and not output.exists()


def test_exporter_approval_binding(tmp_path):
    output = (tmp_path / "out").resolve()
    record = {"protocol_id": exporter.PROTOCOL_ID, "source_commit": "a" * 40, "output": str(output),
              "approved_by": "synthetic", "scope": "synthetic"}
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(record))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    exporter.load_approval(path, digest, "a" * 40, output)
    for args in ((path, "0" * 64, "a" * 40, output), (path, digest, "b" * 40, output),
                 (path, digest, "a" * 40, tmp_path / "elsewhere"), (None, None, "a" * 40, output)):
        with pytest.raises(exporter.ExportRefused):
            exporter.load_approval(*args)


def test_exporter_payload_passes_the_standalone_validation(base_payload):
    exporter.validate_with_checker(json.dumps(base_payload).encode())


# ------------------------------------------------ optional: QuTiP on synthetic input


def test_qutip_assembly_matches_the_synthetic_oracle(base_payload):
    """Runs only where QuTiP is installed; SYNTHETIC input, not the Branch-A model."""
    qutip = pytest.importorskip("qutip")
    independent = checker.assemble_with_qutip(base_payload, qutip).full()
    oracle = np.asarray(base_payload["baseline_H_real"]) + 1j * np.asarray(base_payload["baseline_H_imag"])
    assert np.max(np.abs(independent - oracle)) <= checker.PROPOSED_ENGINEERING_RULES[
        "max_hamiltonian_entry_abs_diff_GHz"]


# ----------------------------------------------------- documentation boundaries


def test_protocol_doc_separates_existing_and_proposed_rules():
    text = DOC_PATH.read_text()
    assert "PREPARED, NOT APPROVED, NOT EXECUTED" in text
    assert "### 3.1 Existing rules" in text and "### 3.2 PROPOSED ENGINEERING-RULES" in text
    assert "FLAGGED-FOR-REVIEW" in text
    assert "It is **not** a geometry-derived or S1-extracted coupling" in text
    for value in ("1e-12 GHz", "1e-10 GHz", "1e-6 MHz", "1e-9 GHz", "| F8 weight | 1e-10 |"):
        assert value in text


# ======================================================= static review additions


def test_guard_restores_everything_on_an_exception_path():
    fake = _FakeDressedModule()
    real_la, real_root = fake.la, fake.solve_dressed_root

    class Boom(Exception):
        pass

    with pytest.raises(Boom):
        with exporter.fixed_point_guard(fake):
            fake.fixed_point()
            raise Boom()
    assert fake.la is real_la and fake.solve_dressed_root == real_root
    for name in exporter.ROOT_SEARCH_ENTRY_POINTS:
        # restored to the original underlying function, not a raiser
        assert getattr(fake, name).__func__ is getattr(_FakeDressedModule, name), name
    assert fake.solve_dressed_root() == 4.3


def test_guard_restores_when_the_wrapped_eigh_itself_fails():
    class Failing(Exception):
        pass

    class _FailingLinalg:
        @staticmethod
        def eigh(matrix):
            raise Failing()

    fake = _FakeDressedModule()
    failing_la = _FailingLinalg()
    fake.la = failing_la
    with pytest.raises(Failing):
        with exporter.fixed_point_guard(fake):
            fake.fixed_point()
    assert fake.la is failing_la
    assert fake.solve_dressed_root() == 4.3
    with exporter.fixed_point_guard(_FakeDressedModule()):   # lock released after the failure
        pass


def test_wrapped_eigh_returns_exactly_the_original_result():
    fake = _FakeDressedModule()
    matrix = np.array([[2.0, 1.0 - 0.5j], [1.0 + 0.5j, 3.0]])
    expected_values, expected_vectors = np.linalg.eigh(matrix)
    with exporter.fixed_point_guard(fake) as captured:
        values, vectors = fake.la.eigh(matrix)
    assert np.array_equal(values, expected_values) and np.array_equal(vectors, expected_vectors)
    assert np.array_equal(captured[0], matrix) and captured[0] is not matrix


def test_wrapped_eigh_refuses_non_production_arguments():
    fake = _FakeDressedModule()
    with pytest.raises(exporter.RootSearchForbidden):
        with exporter.fixed_point_guard(fake):
            fake.la.eigh(np.eye(2), UPLO="U")


def test_zero_and_multiple_captures_fail_closed():
    with pytest.raises(exporter.ExportRefused):
        exporter.require_single_capture([])
    with pytest.raises(exporter.ExportRefused):
        exporter.require_single_capture([np.eye(2), np.eye(2)])
    one = np.eye(2)
    assert exporter.require_single_capture([one]) is one


def test_nested_or_concurrent_guard_is_refused_and_lock_released():
    outer, inner = _FakeDressedModule(), _FakeDressedModule()
    with exporter.fixed_point_guard(outer):
        with pytest.raises(exporter.ExportRefused):
            with exporter.fixed_point_guard(inner):
                pass
        assert inner.la is np.linalg
    with exporter.fixed_point_guard(inner) as captured:   # lock released after exit
        inner.fixed_point()
    assert len(captured) == 1


def test_exporter_solves_only_at_the_fixed_readout_constant():
    tree = _tree(EXPORTER_PATH)
    assignments = {node.targets[0].id: node.value for node in tree.body
                   if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    assert isinstance(assignments["READOUT_GHZ"], ast.Constant)
    assert assignments["READOUT_GHZ"].value == 4.301974466
    solves = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
              and getattr(node.func, "attr", None) == "solve_dressed"]
    assert len(solves) == 1
    assert isinstance(solves[0].args[0], ast.Name) and solves[0].args[0].id == "READOUT_GHZ"
    readout_writes = [node for node in ast.walk(tree) if isinstance(node, (ast.Assign, ast.AugAssign))
                      and any(isinstance(target, ast.Name) and target.id == "READOUT_GHZ"
                              for target in (node.targets if isinstance(node, ast.Assign) else [node.target]))]
    assert len(readout_writes) == 1
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names}
    assert not imported & {"brentq", "optimize", "root_scalar", "fsolve"}


def test_qutip_assembly_disables_tidyup_and_never_symmetrises():
    function = next(node for node in _tree(CHECKER_PATH).body
                    if isinstance(node, ast.FunctionDef) and node.name == "assemble_with_qutip")
    source = ast.unparse(function)
    assert "core_options(auto_tidyup=False)" in source
    for forbidden in (".conj().T) / 2", "dag()) / 2", "np.abs(charge)", "rwa", "isherm", "tidyup(",
                      "sigmaz", "sigmax"):
        if forbidden == "np.abs(charge)":
            # abs is allowed ONLY inside the omission criterion
            assert source.count("np.abs(charge)") == 1 and "np.abs(charge) <" in source
            continue
        assert forbidden not in source, forbidden
    for required in ("qutip.tensor(fluxonium_energy, qutip.qeye(NPH))",
                     "qutip.tensor(qutip.qeye(NQ), qutip.num(NPH))",
                     "qutip.tensor(charge_operator, a + a.dag())",
                     "[[NQ, NPH], [NQ, NPH]]"):
        assert required in source, required


def test_qutip_assembly_blocks_without_core_options(base_payload):
    class NoCoreOptions:
        pass

    with pytest.raises(checker.CheckFailure) as info:
        checker.assemble_with_qutip(base_payload, NoCoreOptions())
    assert info.value.status == "BLOCKED"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.__setitem__("Nq", 11),
        lambda p: p.__setitem__("Nph", 13),
        lambda p: p.__setitem__("dimension", 121),
        lambda p: p.__setitem__("coupling_g_GHz", 0.2),
        lambda p: p.__setitem__("schema", "qmhp-cem.qutip-branch-a-reference/2"),
        lambda p: p["baseline_H_imag"][7].__setitem__(7, None),
    ],
    ids=["Nq-11", "Nph-13", "dimension", "g-value", "schema-id", "missing-imag-element"],
)
def test_further_contract_violations_are_rejected(tmp_path, base_payload, mutate):
    assert _status(tmp_path, _mutated(base_payload, mutate))[0] == "REJECTED"


def test_master_hash_mismatches_are_rejected(tmp_path, base_payload):
    expected = _expected_record(base_payload, json.dumps(base_payload).encode())
    expected["master_file_sha256"] = "c" * 64
    status, message = _status(tmp_path, base_payload, expected=expected)
    assert status == "REJECTED" and "master" in message
    inconsistent = _mutated(base_payload, lambda p: p.__setitem__("master_file_sha256", "c" * 64))
    expected = _expected_record(inconsistent, json.dumps(inconsistent).encode())
    status, message = _status(tmp_path, inconsistent, expected=expected)
    assert status == "REJECTED" and "master" in message


def test_observables_are_not_evaluated_when_labels_are_not_safe():
    data = _synthetic()
    same = {"H": data["hamiltonian"], "eigenvalues": data["eigenvalues"], "observables": data["observables"]}
    unsafe = checker.compare(same, same, checker.PROPOSED_ENGINEERING_RULES, labels_ok=False)
    for key in checker.OBSERVABLE_CHECKS:
        assert unsafe[key]["verdict"].startswith("NOT-EVALUATED"), key
    assert unsafe["hamiltonian_max_entry"]["verdict"] == "PASS"
    default = checker.compare(same, same, checker.PROPOSED_ENGINEERING_RULES)
    assert all(default[key]["verdict"].startswith("NOT-EVALUATED") for key in checker.OBSERVABLE_CHECKS)


def test_labelling_has_no_frequency_fallback():
    source = ast.unparse(next(node for node in _tree(CHECKER_PATH).body
                              if isinstance(node, ast.FunctionDef) and node.name == "label_states"))
    assert "argmax" in source
    for forbidden in ("eigenvalues", "readout", "frequenc", "argmin", "argsort", ".sort("):
        assert forbidden not in source, forbidden
    # the only ordering in label_states is of the duplicate-index report itself
    assert source.count("sorted(") == 1 and "duplicates = sorted(" in source


def test_proposed_rules_are_never_labelled_frozen_or_approved():
    doc = DOC_PATH.read_text()
    section = doc.split("### 3.2 PROPOSED ENGINEERING-RULES", 1)[1].split("## 4.", 1)[0]
    assert "**not** frozen master requirements" in section and "**not approved**" in section
    assert checker.FROZEN_RULES_STATUS.endswith("(ENGINEERING-RULE, not MASTER-FROZEN)")
    schema = json.loads(SCHEMA_PATH.read_text())
    assert "PROPOSED ENGINEERING-RULE, not approved" in \
        schema["properties"]["input_classifications"]["properties"]["comparison_thresholds"]["const"]
    assert "MASTER-FROZEN" not in json.dumps(checker.PROPOSED_ENGINEERING_RULES)


def test_protocol_doc_does_not_call_the_eigensolver_independent():
    doc = DOC_PATH.read_text()
    assert "independent QuTiP operator/tensor assembly of the same finite model, followed by a controlled numerical comparison" in doc
    assert "**This eigensolver is shared with CEM, not independent of it.**" in doc
    assert "floating-point slack" in doc and "**not** a scientific acceptance tolerance" in doc
    scope = json.loads(SCHEMA_PATH.read_text())["properties"]["evidence_scope"]["const"]
    assert "shared with CEM, not independent" in scope
