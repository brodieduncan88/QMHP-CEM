"""Phase C, increment 5: the implementation record cannot quietly become false.

`docs/agent-contract-implementation.md` states, per contract clause, which mechanism
enforces it and which tests prove the mechanism rejects the failure. Two checks already
guard it: every test NAME it cites must exist, and the MECHANISM / BEHAVIOURAL ONLY
separation must survive. Everything else in it was unchecked prose.

REPRODUCED ON THE FROZEN SNAPSHOT ec8dd20d137425a9ccd0005b6cde1546475864e2. The record on
that snapshot was accurate - all 16 path-like references resolved, all 8 cited commits
existed, every MECHANISM row named a live test. So this is NOT a live inconsistency being
corrected; what was reproduced is the ABSENCE OF THE CONTROL. A copy of the record on that
snapshot was edited to name `orchestrator/nonexistent_guard.py` as the module implementing
evidence promotion and to cite commit `deadbee`, and the entire existing suite that reads
the record - all 16 tests in `tests/test_launch_authority.py` - passed. A record can name a
module that does not exist and cite a commit that was never made, and nothing notices.

These checks are therefore PREVENTIVE, and are described as such rather than as a repair.

WHAT IS DELIBERATELY NOT CHECKED. Whether a report is well written, whether a task was
bounded, whether a conclusion is sound, whether reviewer independence was sufficient. None
is derivable from repository state, and a test that pretended to derive it would be the
decoration this record's own closing paragraph warns about. Those stay BEHAVIOURAL ONLY.

A NEAR-MISS WORTH RECORDING. The first draft of the path check flagged ten "missing"
files, among them `summary.json`, `manifest.sha256` and `campaign.sha256`. Every one was a
BARE FILENAME used in prose, resolving somewhere in the tree but not at the repository
root - and `EXECUTION-APPROVAL.json` is deliberately absent, which is the entire point of
increment 3. Only references containing a path separator can be judged root-relative, and
judging the others would have produced exactly the false failure this repository has
already talked itself out of twice.
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORD = REPO_ROOT / "docs" / "agent-contract-implementation.md"

FROZEN_SHA = "ec8dd20d137425a9ccd0005b6cde1546475864e2"

#: Backticked things that look like files. Split below into references that can be judged
#: root-relative and prose filenames that cannot.
_FILEISH = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|md|json|yml|yaml|sha256))`")


def record_text() -> str:
    return RECORD.read_text()


def named_paths(text: str | None = None) -> tuple[list[str], list[str]]:
    """(root-relative references, prose filenames) named in the record."""
    found = sorted(set(_FILEISH.findall(record_text() if text is None else text)))
    return [p for p in found if "/" in p], [p for p in found if "/" not in p]


def defined_tests() -> set[str]:
    out: set[str] = set()
    for path in sorted((REPO_ROOT / "tests").glob("test_*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name.startswith("test_"):
                out.add(node.name)
    return out


def mechanism_rows(text: str | None = None) -> list[str]:
    body = record_text() if text is None else text
    table = body.split("**MECHANISM**")[1].split("**BEHAVIOURAL ONLY**")[0]
    return [line for line in table.splitlines()
            if line.startswith("|") and not set(line) <= set("|- ")
            and not line.startswith("| clause")]


def cited_commits(text: str | None = None) -> list[str]:
    body = record_text() if text is None else text
    return sorted(set(re.findall(r"`([0-9a-f]{7,40})`", body)))


def shallow() -> bool:
    got = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse",
                          "--is-shallow-repository"], capture_output=True, text=True)
    return got.stdout.strip() == "true"


# --- the checks ----------------------------------------------------------------------


def test_every_root_relative_path_the_record_names_exists():
    """A record naming a module that is not there asserts a control that is not there."""
    pathlike, _ = named_paths()
    missing = [p for p in pathlike if not (REPO_ROOT / p).exists()]
    assert not missing, f"the record names paths that do not exist: {missing}"
    assert len(pathlike) >= 12, f"only {len(pathlike)} path-like references; has it been gutted?"


def test_prose_filenames_are_not_judged_as_paths():
    """Pins the distinction the first draft got wrong, so nobody 'fixes' it back.

    These are bare filenames in prose. They are NOT root-relative, and one of them -
    EXECUTION-APPROVAL.json - is deliberately absent. Treating them as paths produces a
    false failure on an accurate record.
    """
    _, bare = named_paths()
    assert "EXECUTION-APPROVAL.json" in bare
    assert not (REPO_ROOT / "EXECUTION-APPROVAL.json").exists()
    for name in ("summary.json", "manifest.sha256"):
        if name in bare:
            assert not (REPO_ROOT / name).exists(), f"{name} is prose, not a root path"


def test_every_mechanism_row_names_at_least_one_test_that_exists():
    """A MECHANISM row is a claim that something is enforced AND proved. A row citing no
    live test is a claim with no evidence attached."""
    defined = defined_tests()
    rows = mechanism_rows()
    assert len(rows) >= 14, f"only {len(rows)} MECHANISM rows; has the table been gutted?"
    unevidenced = []
    for row in rows:
        names = set(re.findall(r"\b(test_[a-z0-9_]+)\b", row))
        if not (names & defined):
            unevidenced.append(row.split("|")[1].strip()[:70])
    assert not unevidenced, f"MECHANISM rows with no existing test: {unevidenced}"


@pytest.mark.skipif(shallow(),
                    reason="shallow checkout: actions/checkout@v4 fetches depth 1, so "
                           "historical commits are absent and cannot be resolved here")
def test_every_commit_the_record_cites_exists():
    shas = cited_commits()
    assert len(shas) >= 6, f"only {len(shas)} commits cited; has the record been gutted?"
    unknown = [s for s in shas
               if subprocess.run(["git", "-C", str(REPO_ROOT), "cat-file", "-e",
                                  f"{s}^{{commit}}"], capture_output=True).returncode != 0]
    assert not unknown, f"the record cites commits that do not exist: {unknown}"


def test_the_post_push_only_gap_is_no_longer_claimed():
    """A stale known gap is as misleading as a missing one. The record said the secret
    scan was post-push and that "nothing invokes them automatically"; a pre-push hook now
    exists, so that text must have been corrected rather than left standing."""
    assert (REPO_ROOT / ".githooks" / "pre-push").is_file()
    text = record_text()
    assert "nothing invokes them automatically" not in text, \
        "the known-gap text still claims nothing invokes the scanner; a pre-push hook exists"
    assert ".githooks/pre-push" in text, "the record does not mention the mechanism that exists"


def test_the_record_does_not_claim_complete_secret_protection():
    """The contract forbids overclaiming, and this is the claim most tempting to make."""
    text = record_text().lower()
    for overclaim in ("no secret can", "guarantees no secret", "complete secret protection",
                      "prevents all secrets", "all secrets are caught"):
        assert overclaim not in text, overclaim


# --- the checks reject what they are for ---------------------------------------------


def test_the_checks_reject_a_record_that_has_become_false():
    """Negative controls, applied to a COPY of the record in memory. Each is the exact
    mutation that passed the whole existing suite on the frozen snapshot."""
    text = record_text()

    broken_path = text.replace("`orchestrator/promotion.py`",
                               "`orchestrator/nonexistent_guard.py`", 1)
    pathlike, _ = named_paths(broken_path)
    assert "orchestrator/nonexistent_guard.py" in pathlike
    assert not (REPO_ROOT / "orchestrator/nonexistent_guard.py").exists()

    broken_sha = text.replace("`9ea3912`", "`deadbee`", 1)
    assert "deadbee" in cited_commits(broken_sha)
    if not shallow():
        assert subprocess.run(["git", "-C", str(REPO_ROOT), "cat-file", "-e",
                               "deadbee^{commit}"], capture_output=True).returncode != 0

    # a MECHANISM row stripped of its evidence
    rows = mechanism_rows(text)
    gutted = rows[0].split("|")
    gutted[3] = " (removed) "
    stripped = text.replace(rows[0], "|".join(gutted), 1)
    defined = defined_tests()
    row = [r for r in mechanism_rows(stripped) if "(removed)" in r][0]
    assert not (set(re.findall(r"\b(test_[a-z0-9_]+)\b", row)) & defined), \
        "the gutted row must read as unevidenced"


def test_this_module_cannot_launch_a_container():
    """It shells out to git, which is why it lives here and not in
    tests/test_launch_authority.py, whose stated property is that it calls no subprocess."""
    tree = ast.parse(Path(__file__).read_text())
    # The runtime names are assembled rather than written out, so this assertion does not
    # put the very literals it forbids into the file it is checking.
    runtimes = {"doc" + "ker", "pod" + "man", "mpi" + "run", "-" + "np"}
    literals = {n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not (literals & runtimes), sorted(literals & runtimes)
    calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "subprocess.run" in calls, "this module does use subprocess, deliberately"
    assert not (calls & {"subprocess.Popen", "os.system", "os.execv"})
