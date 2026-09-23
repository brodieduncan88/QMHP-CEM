"""The SYNTHETIC three-mode identifiability record: present, finite, labelled, outside production.

`experiments/SYNTHETIC-three-mode-identifiability/` is an offline study on a
known-parameter circuit. These tests pin what makes it safe to keep in the
tree: it is labelled SYNTHETIC, nothing in the production layers imports it,
the production inversion and its guards are untouched, every recorded value is
finite, and its few closed-form claims hold on a fresh small case.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORD = REPO_ROOT / "experiments" / "SYNTHETIC-three-mode-identifiability"
SCRIPT = RECORD / "three_mode_identifiability.py"
DOC = REPO_ROOT / "docs" / "coupled-candidate" / "synthetic-three-mode-identifiability.md"


@pytest.fixture(scope="module")
def study():
    spec = importlib.util.spec_from_file_location("synthetic_three_mode_identifiability", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _scan_finite(obj, path="results"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            _scan_finite(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _scan_finite(v, f"{path}[{i}]")
    elif isinstance(obj, float):
        assert math.isfinite(obj), f"non-finite value at {path}"


# --- the record -----------------------------------------------------------------------------


def test_record_is_complete_labelled_and_finite():
    for name in ("README.md", "three_mode_identifiability.py", "inputs.json", "results.json",
                 "environment.json", "report.txt", "manifest.sha256"):
        assert (RECORD / name).is_file(), name
    results = json.loads((RECORD / "results.json").read_text())
    assert results["label"] == "SYNTHETIC"
    assert json.loads((RECORD / "inputs.json").read_text())["label"] == "SYNTHETIC"
    _scan_finite(results)
    assert "SYNTHETIC" in (RECORD / "README.md").read_text()
    assert "SYNTHETIC" in SCRIPT.read_text().splitlines()[1]
    assert DOC.is_file() and "SYNTHETIC" in DOC.read_text().splitlines()[0]


def test_manifest_matches_the_files():
    for line in (RECORD / "manifest.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((RECORD / name).read_bytes()).hexdigest() == digest, name


def test_nothing_in_production_reaches_the_study():
    for layer in ("models", "orchestrator", "evaluator", "solvers", "contracts", "scripts"):
        for path in (REPO_ROOT / layer).rglob("*.py"):
            assert "three_mode_identifiability" not in path.read_text(), path
    text = SCRIPT.read_text()
    for forbidden in ("import orchestrator", "from orchestrator", "import evaluator", "from evaluator",
                      "import solvers", "from solvers", "coupling_extraction"):
        assert forbidden not in text, forbidden


def test_the_production_inversion_and_its_guards_are_unchanged():
    from models import route_a_inversion as m

    assert m.SUM_RULE_RTOL == 1.0e-6
    assert m.ROOT_SELECTION_RTOL == 1.0e-9
    src = (REPO_ROOT / "models" / "route_a_inversion.py").read_text()
    assert "check_sum_rule: bool = True" in src
    assert "no algebraic root reproduces the supplied data" in src


def test_the_script_refuses_to_write_under_results(tmp_path):
    target = REPO_ROOT / "results" / "SYNTHETIC-must-not-exist"
    proc = subprocess.run([sys.executable, str(SCRIPT), "--out", str(target)],
                          capture_output=True, text=True, cwd=REPO_ROOT, timeout=60)
    assert proc.returncode != 0
    assert "refusing" in (proc.stderr + proc.stdout)
    assert not target.exists()


# --- the closed-form claims, on a fresh case --------------------------------------------------


def test_rotation_leaves_fsite_observables_invariant_and_moves_the_node_targets(study):
    S = study.S3(2.25, 15.21, 64.0, 0.41, 1.7, 2.0)
    f0, p0, _ = study.modes3(S)
    inv0 = study.rotation_invariants(S)
    t0 = study.node_targets(S)
    moved = False
    for theta in (-0.7, -0.2, 0.1, 0.4, 1.3):
        Q = study.Q_rot(theta)
        S1 = Q @ S @ Q.T
        f1, p1, _ = study.modes3(S1)
        assert np.max(np.abs(f1 - f0) / f0) < 1e-12
        assert np.max(np.abs(p1 - p0)) < 1e-12
        inv1 = study.rotation_invariants(S1)
        for key in inv0:
            assert abs(inv1[key] - inv0[key]) <= 1e-10 * max(1.0, abs(inv0[key])), key
        t1 = study.node_targets(S1)
        assert t1.E_C_FF_GHz == pytest.approx(t0.E_C_FF_GHz, rel=1e-14)
        moved |= abs(t1.g_GHz - t0.g_GHz) > 1e-3 * t0.g_GHz
    assert moved, "a rotation of the R/X block must move the node-basis coupling"


def test_fsite_identification_recovers_the_environment_normal_modes(study):
    rng = np.random.default_rng(7)
    for _ in range(20):
        a, b, d = 1.0 + 3 * rng.random(), 9.0 + 20 * rng.random(), 40.0 + 60 * rng.random()
        S = study.S3(a, b, d, 0.1 + rng.random(), 0.1 + 2 * rng.random(), 3 * rng.random())
        f, p, _ = study.modes3(S)
        beta, ctil, _ = study.env_normal_modes(S)
        idn = study.f_site_identify(f, p)
        assert idn["a"] == pytest.approx(a, rel=1e-12)
        assert np.max(np.abs(idn["beta"] - beta) / beta) < 1e-9
        assert np.max(np.abs(idn["ctil2"] - ctil ** 2) / ctil ** 2) < 1e-8


def test_the_voltage_ratio_pins_the_rotation_angle(study):
    S_rep = study.S3(2.25, 15.1, 64.1, 0.34, 1.75, 0.0)   # environment block diagonal: the representative
    for theta0 in (-0.041, 0.2, -0.6):
        Q = study.Q_rot(theta0)
        S_true = Q @ S_rep @ Q.T
        f, p, V = study.modes3(S_true)
        rho = study.voltage_ratio_rows(V, f)
        theta = study.theta_from_ratio(S_rep, 0, 1, rho[0] / rho[1], False)
        assert abs(math.sin(theta - theta0)) < 1e-9
        got = study.node_targets(study.Q_rot(theta) @ S_rep @ study.Q_rot(theta).T)
        want = study.node_targets(S_true)
        assert got.g_GHz == pytest.approx(want.g_GHz, rel=1e-9)
        assert got.f_R_GHz == pytest.approx(want.f_R_GHz, rel=1e-9)


def test_kRX_zero_is_not_maxwell_admissible_when_F_couples_to_both(study):
    S = study.S3(2.25, 15.21, 64.0, 0.41, 1.7, 0.0)
    adm = study.admissible_node_circuit(S)
    assert adm["positive_definite"] and adm["Cinv_offdiag_nonneg"]
    assert not adm["C_offdiag_nonpos"] and not adm["admissible"]
    assert np.linalg.inv(S)[1, 2] > 0          # a positive mutual capacitance
    assert study.admissible_node_circuit(study.S3(2.25, 15.21, 64.0, 0.41, 1.7, 2.0))["admissible"]


# --- the recorded headline numbers ------------------------------------------------------------


def test_recorded_results_carry_the_reported_conclusions():
    R = json.loads((RECORD / "results.json").read_text())
    assert R["inputs"]["A_kRX0"]["admissible"]["admissible"] is False
    assert R["inputs"]["B_kRX2"]["admissible"]["admissible"] is True
    for row in R["B_family_is_orbit"]:
        assert row["max_rel_dev_rotation_invariants"] < 1e-10
        assert row["orbit_residual"] < 1e-6
        assert row["admissible"] is True
    assert R["C_fsite"]["A_kRX0"]["normal_mode_vs_node_rel_diff"]["g"] < 1e-9
    assert R["C_fsite"]["B_kRX2"]["normal_mode_vs_node_rel_diff"]["g"] == pytest.approx(0.1728, abs=1e-3)
    D = R["D_extra_observable"]
    assert D["n_distinct_target_pairs_closed_form"] == 1
    assert D["random_start_6eq"]["n_distinct_targets"] == 1
    assert D["random_start_5eq"]["n_distinct_targets"] > 100
    assert D["theta_r12_vs_r13_consistency"] < 1e-9
    assert R["E_saved_outputs"]["N1R"] == R["E_saved_outputs"]["N2R"]
    assert "probe-E.csv" not in R["E_saved_outputs"]["N1R"]
