"""Regression checks on the GitHub Actions workflow files.

These are structural: they pin the trigger strategy and the record-handling
of the Palace golden-run workflow so a later edit cannot quietly reintroduce
a stale branch trigger, a glob over earlier records, or an unchecked
manifest. They do not execute the workflows.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
GOLDEN = WORKFLOWS / "palace-golden.yml"


def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    # PyYAML parses the bare key `on` as the boolean True.
    data["on"] = data.pop(True, data.get("on"))
    return data


def _steps(workflow: dict) -> list[dict]:
    return workflow["jobs"]["golden"]["steps"]


def test_golden_workflow_triggers_are_maintained_not_a_session_branch():
    wf = _load(GOLDEN)
    on = wf["on"]
    assert "workflow_dispatch" in on
    push = on["push"]
    assert push["branches"] == ["main", "palace/**"]
    assert set(push["paths"]) >= {
        ".github/workflows/palace-golden.yml",
        "docker/palace.Dockerfile",
        "solvers/palace/**",
        "scripts/palace_golden_run.py",
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
    steps = _steps(_load(GOLDEN))
    commit = next(s for s in steps if s.get("name", "").startswith("Commit the golden record"))
    assert 'git add "$GOLDEN_RECORD"' in commit["run"]
    assert '"$GOLDEN_RECORD/execution_record.json"' in commit["run"]
    upload = next(s for s in steps if s.get("name") == "Upload results")
    assert "${{ steps.record.outputs.path }}" in upload["with"]["path"]
    assert "PALACE-GOLDEN-*" not in upload["with"]["path"]


def test_golden_workflow_fails_on_a_manifest_mismatch_but_keeps_the_artefacts():
    wf = _load(GOLDEN)
    steps = _steps(wf)
    by_id = {s.get("id"): s for s in steps if s.get("id")}
    manifest_step = by_id["manifest"]
    assert "cem verify-results" in manifest_step["run"]
    assert manifest_step.get("continue-on-error") is True          # the step records, the last step fails
    names = [s.get("name", s.get("uses", "")) for s in steps]   # bare `uses:` steps carry no name
    upload = next(s for s in steps if s.get("name") == "Upload results")
    commit = next(s for s in steps if s.get("name", "").startswith("Commit the golden record"))
    assert str(upload["if"]).startswith("always()") and str(commit["if"]).startswith("always()")
    final = steps[-1]
    assert str(final["if"]).startswith("always()")                 # runs after any earlier hard failure too
    assert "steps.manifest.outcome == 'failure'" in final["if"]
    assert "steps.golden.outcome != 'success'" in final["if"]
    assert "exit 1" in final["run"]
    assert names.index("Verify the record manifest") < names.index("Upload results") < names.index(commit["name"])
