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


def test_golden_workflow_triggers_are_maintained_not_a_session_branch():
    wf = _load(GOLDEN)
    on = wf["on"]
    assert "workflow_dispatch" in on
    push = on["push"]
    assert push["branches"] == ["main", "palace/**"]
    assert set(push["paths"]) >= {
        ".github/workflows/palace-golden.yml",
        "docker/palace.Dockerfile",
        "pyproject.toml",
        "uv.lock",
        "contracts/**",
        "evaluator/**",
        "models/**",
        "orchestrator/**",
        "solvers/**",
        "scripts/palace_golden_run.py",
        "tests/test_palace.py",
    }
    assert "pull_request" not in on
    assert "claude/" not in GOLDEN.read_text()


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


def test_verification_workflow_tracks_all_load_bearing_paths():
    paths = set(_load(VERIFY)["on"]["push"]["paths"])
    assert paths >= {
        ".github/workflows/palace-verify.yml",
        "docker/palace.Dockerfile",
        "pyproject.toml",
        "uv.lock",
        "contracts/**",
        "orchestrator/**",
        "scripts/palace_verify_campaign.py",
        "solvers/**",
        "tests/test_palace.py",
    }


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
