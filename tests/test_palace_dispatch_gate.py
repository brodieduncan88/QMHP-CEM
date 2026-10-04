"""The Palace dispatch gate accepts exactly one consistent case and refuses the rest.

Each test builds a throwaway git repository: a code commit, then a commit that
adds only the declaration. The positive control must pass; every negative
control changes one thing and must be refused. No workflow, solver or network
is involved.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("palace_dispatch_gate", ROOT / "scripts" / "palace_dispatch_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

DECL = ".github/palace-declarations/golden-check.json"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
             "HOME": str(repo), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    ).stdout.strip()


def _declaration(code: str, **overrides) -> dict:
    body = {
        "schema": gate.SCHEMA,
        "workflow": "palace-golden",
        "code_commit": code,
        "question": "Does the golden candidate still converge on this commit?",
        "baseline_record": "results/PALACE-GOLDEN-20260915T014639Z",
        "independent_variable": "source commit",
        "controlled_variables": ["mesh", "Palace image definition", "solver configuration"],
        "inputs": {"mpi_processes": "1", "commit_results": False, "run_sweep": False},
        "approval_ref": "owner decision 2026-10-04",
        "budget": {"timeout_minutes": 120, "attempts": 1},
        "acceptance_criteria": ["four modes within the golden tolerance"],
        "stop_conditions": ["any failure: preserve and stop"],
        "expected_evidence": ["results/PALACE-GOLDEN-<UTC>/ with a verified manifest"],
    }
    body.update(overrides)
    return body


def _dispatch(sha: str, **overrides) -> dict:
    inputs = {
        "expected_sha": sha,
        "declaration_ref": DECL,
        "approval_ref": "owner decision 2026-10-04",
        "mpi_processes": "1",
        "commit_results": False,
        "run_sweep": False,
    }
    inputs.update(overrides)
    return inputs


@pytest.fixture()
def repo(tmp_path: Path):
    """A code commit, then a commit adding only the declaration."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    (r / "solver.py").write_text("print('solve')\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "code")
    code = _git(r, "rev-parse", "HEAD")

    def commit_declaration(body: dict, path: str = DECL) -> str:
        target = r / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(body, indent=2) + "\n")
        _git(r, "add", "-A")
        _git(r, "commit", "-q", "-m", "declaration")
        return _git(r, "rev-parse", "HEAD")

    return r, code, commit_declaration


def test_positive_control_a_consistent_dispatch_is_authorised(repo):
    r, code, commit_declaration = repo
    head = commit_declaration(_declaration(code))
    summary = gate.check(r, "palace-golden", 360, head, _dispatch(head))
    assert summary["code_commit"] == code and summary["executed_commit"] == head
    assert len(summary["declaration_sha256"]) == 64


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d, code, head: (d, _dispatch("0" * 40)), "does not match the executed commit"),
        (lambda d, code, head: (d, _dispatch(head[:12])), "full 40-character"),
        (lambda d, code, head: (d, _dispatch(head, declaration_ref="docs/x.json")), "declaration_ref"),
        (lambda d, code, head: (d, _dispatch(head, declaration_ref=".github/palace-declarations/missing.json")), "not a regular file"),
        (lambda d, code, head: (d, _dispatch(head, approval_ref="someone else")), "approval_ref differs"),
        (lambda d, code, head: (d, _dispatch(head, run_sweep=True)), "differ from the declared"),
        (lambda d, code, head: (d, _dispatch(head, mpi_processes=1)), "differ from the declared"),
        (lambda d, code, head: (d, {**_dispatch(head), "extra": "x"}), "differ from the declared"),
    ],
    ids=["wrong-sha", "short-sha", "outside-dir", "missing-file", "approval", "input-value", "input-type", "extra-input"],
)
def test_dispatch_mismatches_are_refused(repo, mutate, message):
    r, code, commit_declaration = repo
    head = commit_declaration(_declaration(code))
    _, dispatch = mutate(None, code, head)
    with pytest.raises(gate.Refused, match=message):
        gate.check(r, "palace-golden", 360, head, dispatch)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"workflow": "palace-verify"}, "is for 'palace-verify'"),
        ({"schema": "other/1"}, "schema must be"),
        ({"question": "  "}, "'question'"),
        ({"stop_conditions": []}, "'stop_conditions'"),
        ({"budget": {"timeout_minutes": 361, "attempts": 1}}, "1..360"),
        ({"budget": {"timeout_minutes": 60, "attempts": 2}}, "attempts must be 1"),
        ({"budget": {"timeout_minutes": 60.0, "attempts": 1}}, "integer"),
        ({"code_commit": "f" * 40}, "not an ancestor"),
    ],
    ids=["workflow", "schema", "blank-question", "no-stop", "over-budget", "retry", "float-budget", "foreign-commit"],
)
def test_declaration_defects_are_refused(repo, overrides, message):
    r, code, commit_declaration = repo
    head = commit_declaration(_declaration(code, **overrides))
    with pytest.raises(gate.Refused, match=message):
        gate.check(r, "palace-golden", 360, head, _dispatch(head))


def test_unexpected_or_missing_keys_are_refused(repo):
    r, code, commit_declaration = repo
    body = _declaration(code)
    body["note"] = "extra"
    del body["expected_evidence"]
    head = commit_declaration(body)
    with pytest.raises(gate.Refused, match="missing \\['expected_evidence'\\], unexpected \\['note'\\]"):
        gate.check(r, "palace-golden", 360, head, _dispatch(head))


def test_code_changed_alongside_the_declaration_is_refused(repo):
    """The run must execute exactly the declared code."""
    r, code, commit_declaration = repo
    (r / "solver.py").write_text("print('something else')\n")
    head = commit_declaration(_declaration(code))
    with pytest.raises(gate.Refused, match="outside .github/palace-declarations/"):
        gate.check(r, "palace-golden", 360, head, _dispatch(head))


def test_a_declaration_that_is_not_committed_is_refused(repo):
    r, code, _ = repo
    head = _git(r, "rev-parse", "HEAD")
    target = r / DECL
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(_declaration(code)))
    with pytest.raises(gate.Refused, match="not committed"):
        gate.check(r, "palace-golden", 360, head, _dispatch(head))


def test_a_checkout_of_another_commit_is_refused(repo):
    r, code, commit_declaration = repo
    head = commit_declaration(_declaration(code))
    _git(r, "checkout", "-q", code)
    with pytest.raises(gate.Refused, match="not the executed commit"):
        gate.check(r, "palace-golden", 360, head, _dispatch(head))


def test_the_command_line_fails_closed_without_inputs(monkeypatch, capsys):
    monkeypatch.delenv("DISPATCH_INPUTS", raising=False)
    assert gate.main(["--workflow", "palace-golden", "--timeout-cap-minutes", "360"]) == 2
    assert "REFUSED" in capsys.readouterr().err
