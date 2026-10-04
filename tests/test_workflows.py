"""Regression checks on the GitHub Actions workflow files.

These are structural: they pin the trigger strategy, least-privilege token
boundary and record handling of the real-solver workflows so a later edit
cannot quietly reintroduce a stale branch trigger, a glob over earlier
records, an unchecked manifest or write credentials in a solver job. They do
not execute the workflows.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
GLOBAL_JSON = ROOT / "global.json"
GOLDEN = WORKFLOWS / "palace-golden.yml"
VERIFY = WORKFLOWS / "palace-verify.yml"
CI = WORKFLOWS / "ci.yml"
FIRST_MOMENT_IMAGE = WORKFLOWS / "first-moment-image.yml"
FIRST_MOMENT_N2R = WORKFLOWS / "first-moment-n2r.yml"
FULL_ACTION_SHA = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    # PyYAML parses the bare key `on` as the boolean True.
    data["on"] = data.pop(True, data.get("on"))
    return data


def _steps(workflow: dict, job: str = "golden") -> list[dict]:
    return workflow["jobs"][job]["steps"]


def test_real_solver_workflows_are_manual_dispatch_only():
    """A Palace solve is consequential (CLAUDE.md sections 2-3): no push, pull
    request or schedule may start one. Merging a code change must not solve."""
    for path in (GOLDEN, VERIFY):
        wf = _load(path)
        assert set(wf["on"]) == {"workflow_dispatch"}, path.name
        assert "claude/" not in path.read_text()


def test_real_solver_dispatch_requires_the_declaration_inputs():
    for path in (GOLDEN, VERIFY):
        inputs = _load(path)["on"]["workflow_dispatch"]["inputs"]
        for name in ("expected_sha", "declaration_ref", "approval_ref"):
            assert inputs[name]["required"] is True, (path.name, name)
            assert inputs[name]["type"] == "string", (path.name, name)
            assert "default" not in inputs[name], (path.name, name)


def test_solver_jobs_wait_on_the_gate_and_the_protected_environment():
    for path, compute_job, workflow, cap in (
        (GOLDEN, "golden", "palace-golden", 360),
        (VERIFY, "verify", "palace-verify", 350),
    ):
        wf = _load(path)
        job = wf["jobs"][compute_job]
        assert job["needs"] == "authorize"
        assert job["environment"] == "palace-solver"
        assert job["timeout-minutes"] == cap
        gate = wf["jobs"]["authorize"]
        assert "environment" not in gate and "permissions" not in gate
        step = next(s for s in gate["steps"] if "palace_dispatch_gate.py" in s.get("run", ""))
        assert f"--workflow {workflow}" in step["run"]
        assert f"--timeout-cap-minutes {cap}" in step["run"]
        # inputs reach the gate as data in the environment, never interpolated into shell
        assert step["env"]["DISPATCH_INPUTS"] == "${{ toJSON(inputs) }}"
        assert "${{" not in step["run"]
        checkout = next(s for s in gate["steps"] if s.get("uses", "").startswith("actions/checkout@"))
        assert checkout["with"]["fetch-depth"] == 0
        assert checkout["with"]["persist-credentials"] is False
        assert wf["concurrency"]["cancel-in-progress"] is False


def test_golden_workflow_acts_on_the_record_it_created_not_a_glob():
    text = GOLDEN.read_text()
    assert "${dirs[0]}" not in text
    assert "dirs=(results/PALACE-GOLDEN-*)" not in text
    steps = {s.get("id"): s for s in _steps(_load(GOLDEN)) if s.get("id")}
    assert "--record-pointer" in steps["golden"]["run"]
    assert "GITHUB_OUTPUT" in steps["record"]["run"] and "GOLDEN_RECORD" in steps["record"]["run"]
    wf = _load(GOLDEN)
    steps = _steps(wf)
    package = next(s for s in steps if s.get("id") == "package")
    assert 'basename "$GOLDEN_RECORD"' in package["run"]
    assert "tar -C results" in package["run"]
    writeback = _steps(wf, "writeback")
    commit = next(s for s in writeback if s.get("name") == "Verify, extract and commit only the record")
    assert 'git add -- "$record"' in commit["run"]
    assert "PALACE-GOLDEN-*" in commit["run"]
    upload = next(s for s in steps if s.get("name") == "Upload results")
    assert "${{ steps.record.outputs.path }}" in upload["with"]["path"]
    assert "workflow-artifacts" in upload["with"]["path"]
    assert "PALACE-GOLDEN-*" not in upload["with"]["path"]


def test_golden_workflow_fails_on_a_manifest_mismatch_but_keeps_the_artefacts():
    wf = _load(GOLDEN)
    steps = _steps(wf)
    by_id = {s.get("id"): s for s in steps if s.get("id")}
    manifest_step = by_id["manifest"]
    assert "cem verify-results" in manifest_step["run"]
    assert manifest_step.get("continue-on-error") is True          # the step records, the last step fails
    names = [s.get("name", s.get("uses", "")) for s in steps]   # bare `uses:` steps carry no name
    package = by_id["package"]
    upload = next(s for s in steps if s.get("name") == "Upload results")
    assert str(package["if"]).startswith("always()")
    assert str(upload["if"]).startswith("always()")
    final = steps[-1]
    assert str(final["if"]).startswith("always()")                 # runs after any earlier hard failure too
    assert "steps.manifest.outcome == 'failure'" in final["if"]
    assert "steps.golden.outcome != 'success'" in final["if"]
    assert "exit 1" in final["run"]
    assert names.index("Verify the record manifest") < names.index("Upload results") < names.index(final["name"])


def test_real_solver_jobs_are_read_only_and_writeback_is_manual_only():
    for path, compute_job in ((GOLDEN, "golden"), (VERIFY, "verify")):
        wf = _load(path)
        assert wf["permissions"] == {"contents": "read"}
        checkout = next(s for s in _steps(wf, compute_job) if s.get("uses", "").startswith("actions/checkout@"))
        assert checkout["with"]["persist-credentials"] is False

        writeback = wf["jobs"]["writeback"]
        assert writeback["permissions"] == {"actions": "read", "contents": "write"}
        condition = writeback["if"]
        assert "github.event_name == 'workflow_dispatch'" in condition
        assert "github.ref_type == 'branch'" in condition
        assert "inputs.commit_results" in condition

        dispatch = wf["on"]["workflow_dispatch"]["inputs"]
        assert dispatch["commit_results"]["default"] is False


def test_default_ci_has_no_write_token_or_persisted_checkout_credentials():
    wf = _load(CI)
    assert wf["permissions"] == {"contents": "read"}
    for job in wf["jobs"].values():
        checkout = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@"))
        assert checkout["with"]["persist-credentials"] is False


def test_default_ci_runs_the_dotnet_test_project_not_just_a_build():
    dotnet_steps = _load(CI)["jobs"]["dotnet"]["steps"]
    test = next(s for s in dotnet_steps if s.get("name") == "Test the implemented scaffold contract")
    assert test["run"].startswith("dotnet test ")
    assert "QmhpCem.Geometry.Tests.csproj" in test["run"]
    assert "--no-build" in test["run"] and "--no-restore" in test["run"]


def test_repository_selects_dotnet_9_even_when_a_newer_sdk_is_installed():
    sdk = json.loads(GLOBAL_JSON.read_text())["sdk"]
    assert sdk == {
        "version": "9.0.100",
        "rollForward": "latestFeature",
        "allowPrerelease": False,
    }


def test_first_moment_files_are_registration_only_on_main():
    expected_ref = "refs/heads/palace/physical-coupled-candidate"
    for path, job in (
        (FIRST_MOMENT_IMAGE, "build-and-qualify"),
        (FIRST_MOMENT_N2R, "n2r-first-moment"),
    ):
        wf = _load(path)
        assert set(wf["on"]) == {"workflow_dispatch"}
        assert wf["permissions"]["contents"] == "read"
        guard = _steps(wf, job)[0]
        assert guard["name"] == "Refuse a ref without the reviewed support bundle"
        assert expected_ref in guard["run"]
        checkout = next(s for s in _steps(wf, job) if s.get("uses", "").startswith("actions/checkout@"))
        assert checkout["with"]["persist-credentials"] is False


def test_every_external_action_is_pinned_to_a_full_commit_sha():
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = _load(path)
        uses = []
        for job in workflow["jobs"].values():
            if "uses" in job:
                uses.append(job["uses"])
            uses.extend(step["uses"] for step in job.get("steps", []) if "uses" in step)
        for action in uses:
            if action.startswith("./") or action.startswith("docker://"):
                continue
            assert FULL_ACTION_SHA.fullmatch(action), f"{path.name}: unpinned action {action}"
