#!/usr/bin/env python3
"""Refuse a Palace workflow dispatch that has no matching predeclaration.

The two real-solver workflows (palace-golden.yml, palace-verify.yml) run this
as their first job. It fails closed unless all of the following hold:

* ``expected_sha`` (typed by the person dispatching) equals the commit the run
  is executing (``GITHUB_SHA``);
* ``declaration_ref`` names a committed JSON file under
  ``.github/palace-declarations/`` in that commit;
* the declaration is for this workflow, pins every dispatch input exactly,
  names the same ``approval_ref``, and carries the CLAUDE.md section 2 fields;
* its compute budget fits inside the job's hard timeout;
* the executed commit is its ``code_commit`` plus, at most, files under
  ``.github/palace-declarations/`` (a declaration cannot contain the hash of
  the commit that adds it, so it pins the code commit it sits on instead).

What this does NOT do: judge whether the declaration is scientifically
adequate, record a human approval, or count attempts. The human approval is the
protected ``palace-solver`` environment's required reviewer; a second dispatch
of the same declaration is not refused here.

Inputs come from the environment, never from shell interpolation:
``GITHUB_SHA``, ``DISPATCH_INPUTS`` (the workflow's ``toJSON(inputs)``).
Exit status 0 means authorised; anything else means refused.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = "qmhp-cem.palace-dispatch-declaration/1"
DECLARATION_DIR = ".github/palace-declarations/"
DECLARATION_PATH = re.compile(r"^\.github/palace-declarations/[A-Za-z0-9][A-Za-z0-9._-]{0,100}\.json$")
SHA = re.compile(r"^[0-9a-f]{40}$")
GATE_INPUTS = frozenset({"expected_sha", "declaration_ref", "approval_ref"})
WORKFLOWS = frozenset({"palace-golden", "palace-verify"})
REQUIRED_KEYS = {
    "schema": str,
    "workflow": str,
    "code_commit": str,
    "question": str,
    "baseline_record": str,
    "independent_variable": str,
    "controlled_variables": list,
    "inputs": dict,
    "approval_ref": str,
    "budget": dict,
    "acceptance_criteria": list,
    "stop_conditions": list,
    "expected_evidence": list,
}


class Refused(Exception):
    """The dispatch is not authorised."""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _non_empty_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise Refused(f"declaration field {field!r} must be a non-empty string")


def _non_empty_list_of_text(value: object, field: str) -> None:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
        raise Refused(f"declaration field {field!r} must be a non-empty list of non-empty strings")


def check(
    repo: Path,
    workflow: str,
    timeout_cap_minutes: int,
    github_sha: str,
    dispatch_inputs: dict,
) -> dict:
    """Return a summary of the authorised dispatch, or raise :class:`Refused`."""
    if workflow not in WORKFLOWS:
        raise Refused(f"unknown workflow {workflow!r}")
    if not SHA.match(github_sha or ""):
        raise Refused(f"GITHUB_SHA {github_sha!r} is not a full commit hash")

    expected = dispatch_inputs.get("expected_sha")
    if not isinstance(expected, str) or not SHA.match(expected):
        raise Refused("expected_sha must be the full 40-character commit hash being run")
    if expected != github_sha:
        raise Refused(f"expected_sha {expected} does not match the executed commit {github_sha}")

    head = _git(repo, "rev-parse", "HEAD")
    if head.returncode != 0 or head.stdout.strip() != github_sha:
        raise Refused("the checked-out tree is not the executed commit")

    ref = dispatch_inputs.get("declaration_ref")
    if not isinstance(ref, str) or not DECLARATION_PATH.match(ref):
        raise Refused(f"declaration_ref must be a file directly under {DECLARATION_DIR} ending in .json")
    path = repo / ref
    if path.is_symlink() or not path.is_file():
        raise Refused(f"{ref} is not a regular file in the executed commit")
    tracked = _git(repo, "ls-files", "--error-unmatch", "--", ref)
    if tracked.returncode != 0:
        raise Refused(f"{ref} is not committed in the executed commit")

    raw = path.read_bytes()
    try:
        declaration = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Refused(f"{ref} is not valid JSON: {exc}") from exc
    if not isinstance(declaration, dict):
        raise Refused(f"{ref} must hold a JSON object")
    if set(declaration) != set(REQUIRED_KEYS):
        missing = sorted(set(REQUIRED_KEYS) - set(declaration))
        extra = sorted(set(declaration) - set(REQUIRED_KEYS))
        raise Refused(f"declaration keys differ from the schema: missing {missing}, unexpected {extra}")
    for key, kind in REQUIRED_KEYS.items():
        if not isinstance(declaration[key], kind):
            raise Refused(f"declaration field {key!r} must be a {kind.__name__}")

    if declaration["schema"] != SCHEMA:
        raise Refused(f"declaration schema must be {SCHEMA!r}")
    if declaration["workflow"] != workflow:
        raise Refused(f"declaration is for {declaration['workflow']!r}, not {workflow!r}")
    for field in ("question", "baseline_record", "independent_variable"):
        _non_empty_text(declaration[field], field)
    for field in ("controlled_variables", "acceptance_criteria", "stop_conditions", "expected_evidence"):
        _non_empty_list_of_text(declaration[field], field)

    approval = dispatch_inputs.get("approval_ref")
    _non_empty_text(approval, "approval_ref (dispatch input)")
    if declaration["approval_ref"] != approval:
        raise Refused("approval_ref differs between the dispatch and the declaration")

    run_inputs = {k: v for k, v in dispatch_inputs.items() if k not in GATE_INPUTS}
    if declaration["inputs"] != run_inputs:
        raise Refused(
            f"dispatch inputs {json.dumps(run_inputs, sort_keys=True)} differ from the declared "
            f"inputs {json.dumps(declaration['inputs'], sort_keys=True)}"
        )

    budget = declaration["budget"]
    if set(budget) != {"timeout_minutes", "attempts"}:
        raise Refused("budget must hold exactly timeout_minutes and attempts")
    minutes, attempts = budget["timeout_minutes"], budget["attempts"]
    if type(minutes) is not int or not 1 <= minutes <= timeout_cap_minutes:
        raise Refused(f"budget.timeout_minutes must be an integer in 1..{timeout_cap_minutes} (the job's hard cap)")
    if attempts != 1:
        raise Refused("budget.attempts must be 1; a retry needs its own declaration")

    code_commit = declaration["code_commit"]
    if not SHA.match(code_commit):
        raise Refused("code_commit must be a full 40-character commit hash")
    if _git(repo, "merge-base", "--is-ancestor", code_commit, github_sha).returncode != 0:
        raise Refused(f"code_commit {code_commit} is not an ancestor of the executed commit")
    diff = _git(repo, "diff", "--name-only", code_commit, github_sha)
    if diff.returncode != 0:
        raise Refused("could not compare the executed commit with code_commit")
    changed = [p for p in diff.stdout.splitlines() if p]
    outside = [p for p in changed if not p.startswith(DECLARATION_DIR)]
    if outside:
        raise Refused(f"the executed commit differs from code_commit outside {DECLARATION_DIR}: {outside[:10]}")

    return {
        "workflow": workflow,
        "executed_commit": github_sha,
        "code_commit": code_commit,
        "declaration": ref,
        "declaration_sha256": hashlib.sha256(raw).hexdigest(),
        "approval_ref": approval,
        "inputs": run_inputs,
        "budget": budget,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--timeout-cap-minutes", type=int, required=True)
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    try:
        dispatch_inputs = json.loads(os.environ.get("DISPATCH_INPUTS", ""))
        if not isinstance(dispatch_inputs, dict):
            raise ValueError("not an object")
    except ValueError:
        print("REFUSED: DISPATCH_INPUTS is missing or is not a JSON object", file=sys.stderr)
        return 2
    try:
        summary = check(
            Path(args.repo).resolve(),
            args.workflow,
            args.timeout_cap_minutes,
            os.environ.get("GITHUB_SHA", ""),
            dispatch_inputs,
        )
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    print("AUTHORISED (declaration consistent; human approval is the environment reviewer)")
    print(json.dumps(summary, indent=2, sort_keys=True))
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write("### Palace dispatch gate\n\n```json\n" + json.dumps(summary, indent=2, sort_keys=True) + "\n```\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
