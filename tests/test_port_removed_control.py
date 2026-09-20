"""PO1, the prepared port-removed control: exact delta, declared guards, and no execution path."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REC = REPO_ROOT / "experiments" / "PO1-port-removed-control"
DOC = REPO_ROOT / "docs" / "coupled-candidate" / "po1-port-removed-control.md"
N2R_SOLVED = REPO_ROOT / "results" / "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z" / "L2" / "solver" / "config.json"


def _norm(text: str) -> str:
    lines = [ln.lstrip().removeprefix("> ").removeprefix(">") for ln in text.splitlines()]
    return " ".join(" ".join(lines).split())


@pytest.fixture(scope="module")
def candidate():
    return json.loads((REC / "candidate.json").read_text())


@pytest.fixture(scope="module")
def config():
    return json.loads((REC / "config.candidate.json").read_text())


def test_the_candidate_is_prepared_not_approved(candidate):
    assert candidate["id"] == "PO1"
    assert candidate["status"] == "PREPARED, NOT APPROVED, NOT LAUNCHED"
    assert "NOT an extraction" in candidate["not_this"]
    assert "NOT APPROVED" in _norm(DOC.read_text())


def test_the_config_delta_against_N2R_is_exactly_two_additions(config):
    solved = json.loads(N2R_SOLVED.read_text())

    def leaves(obj, prefix=""):
        out = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                out.update(leaves(v, f"{prefix}.{k}" if prefix else k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                out.update(leaves(v, f"{prefix}[{i}]"))
        else:
            out[prefix] = obj
        return out

    a, b = leaves(solved), leaves(config)
    assert not {k for k in a.keys() & b.keys() if a[k] != b[k]}, "no existing value may change"
    assert not (a.keys() - b.keys()), "nothing may be removed"
    added = b.keys() - a.keys()
    assert "Boundaries.LumpedPort[0].Active" in added
    assert all(k.startswith("Domains.Postprocessing.Probe[") or k == "Boundaries.LumpedPort[0].Active"
               for k in added), sorted(added)


def test_the_operator_change_is_the_port_deactivation(config):
    port = config["Boundaries"]["LumpedPort"][0]
    assert port["Active"] is False
    # everything else about the port is N2R's
    assert port["Index"] == 1 and port["Attributes"] == [10] and port["Direction"] == "+Y"
    assert port["L"] == 1.0345665367517793e-07
    # the prescription the control must preserve
    assert config["Solver"]["Order"] == 1
    assert config["Solver"]["Linear"]["MGMaxLevels"] == 1
    assert config["Model"]["Refinement"]["Boxes"][0]["Levels"] == 2
    assert config["Model"]["Refinement"]["UniformLevels"] == 0
    assert config["Model"]["Mesh"] == "coupled_chip_cell_L2.msh"
    assert config["Solver"]["Eigenmode"] == {"N": 6, "Tol": 1e-06, "Target": 0.5, "Save": 6}


def test_the_probe_block_is_postprocessing_only_and_declared(config, candidate):
    probes = config["Domains"]["Postprocessing"]["Probe"]
    assert [p["Index"] for p in probes] == [1, 2, 3]
    assert [p["Center"] for p in probes] == [[-0.6, 0.0, 0.01], [-0.455, 0.0, 0.01], [0.5865, 0.5, 0.01]]
    assert all(p["Center"][2] == 0.01 for p in probes), "one common height, fixed in advance"
    assert "cannot_change_an_eigenvalue" in candidate["the_postprocessing_addition"]


def test_the_null_space_is_accounted_for(candidate):
    ns = candidate["null_space"]
    assert ns["extra_directions_relative_to_N2R"] == 1
    assert "island" in ns["which"]
    assert "case_A_projected_out" in ns and "case_B_returned" in ns
    assert "NOT_assumed" in " ".join(ns.keys()) or "is_NOT_assumed" in ns["solver_handling_is_NOT_assumed"][:40] \
        or "NOT settled" in ns["solver_handling_is_NOT_assumed"]
    chk = candidate["the_falsifiable_check_that_the_operator_really_changed"]
    assert "E_mag / (E_elec + E_cap) = 1" in chk["pre_declared"]
    assert "must not be computed" in chk["E_ind_must_not_be_used_as_an_equipartition_test_here"]


def test_mode_identification_is_field_based_and_predeclared(candidate):
    mi = candidate["mode_identification"]
    assert mi["declared_before_the_run"] is True
    assert "frequency is never a selector" in mi["principle"]
    assert "UNIQUE" in mi["selection"] and "No frequency tiebreak" in mi["selection"]
    assert "never used to choose a mode" in mi["cross_check_not_a_selector"]
    for key in ("probe_share_i", "port_face_fraction", "rank_one_port_weight"):
        assert key in mi["quantities"]


def test_the_resource_refusal_conditions_are_unchanged(candidate):
    r = candidate["dof_and_resources"]
    assert r["expected_dof"] == 103411 and r["budget"] == 250000 and r["cap_s"] == 2700
    assert r["no_runtime_is_predicted"].startswith("N2R solved the same size")
    joined = " ".join(r["refusal_conditions_unchanged"])
    for token in ("REFUSED-DOF-BUDGET", "TIMEOUT", "RUN_FAILED", "mesh hash gate"):
        assert token in joined


def test_no_execution_path_is_created(candidate):
    gap = candidate["execution_gap"]
    assert "not_implemented_here" in gap and "deliberately_left_undone" in gap
    # the approval file that triggers the workflow is untouched by this preparation
    changed = subprocess.run(["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True,
                             cwd=REPO_ROOT).stdout.split()
    assert ".github/ladder-approval.json" not in changed
    # and the driver still has no port-deactivation option
    src = (REPO_ROOT / "solvers" / "palace" / "coupled_config.py").read_text()
    assert "Active" not in src.split("def build_coupled_config")[1][:4000]


def test_prepare_reproduces_the_candidate_byte_for_byte(tmp_path):
    before = (REC / "config.candidate.json").read_bytes()
    proc = subprocess.run([sys.executable, str(REC / "prepare.py")], capture_output=True, text=True, cwd=REPO_ROOT)
    assert proc.returncode == 0, proc.stderr
    assert (REC / "config.candidate.json").read_bytes() == before
    assert hashlib.sha256(before).hexdigest() == "2826e78c026097aeb90dc1f50ec2b08e2afefce7ecbb43270d34b7667e0d1728"
    # the recorded diff is a true file diff of the two configs
    diff = (REC / "config.delta.txt").read_text()
    assert '+        "Active": false' in diff
    assert '"Probe"' in diff
