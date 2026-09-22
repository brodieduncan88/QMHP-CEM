#!/usr/bin/env python3
"""At most ONE authorised attempt, enforced from GitHub-assigned run metadata.

WHY THE APPROVAL'S OWN WORDS ARE NOT ENOUGH. The approval says
``"authorises": "one execution"``. That is a sentence, not a mechanism: nothing in it
stops a second dispatch, a re-run, or "re-run failed jobs" from reading the same file and
launching again. This module turns the sentence into a check against metadata the RUNNER
assigns, which the caller cannot state for itself.

WHAT IT BINDS, all from the environment GitHub sets and never from a dispatch input:

  GITHUB_REPOSITORY     the repository, so an approval cannot travel to a fork
  GITHUB_WORKFLOW_REF   owner/repo/path@ref - the exact workflow AND the exact ref
  GITHUB_REF            the ref again, checked separately so a rename is visible
  GITHUB_RUN_NUMBER     ONE approved run number. A fresh dispatch gets the next number,
                        so a duplicate dispatch refuses.
  GITHUB_RUN_ATTEMPT    must be 1, and the approval may only ever name 1. A re-run and
                        "re-run failed jobs" both increment it, so both refuse.

and, read from the checkout rather than from the environment, the sha256 of the workflow
file the approval names and of the launcher and this module.

THE LIMITS, stated rather than implied:

  * It trusts the runner's environment. A workflow step could export a different
    GITHUB_RUN_NUMBER before the launcher runs. What makes that trust meaningful is that
    the approval ALSO pins the sha256 of the workflow file, so a workflow edited to forge
    its own metadata no longer matches the approval and refuses. The trust boundary is
    "the reviewed workflow, unmodified", not "any workflow".
  * It cannot stop a human with write access from committing a second approval naming the
    next run number. That is the intended escape hatch, not a hole: another attempt
    requires another human approval, which is the rule being enforced.
  * The run number must be named BEFORE the run exists. A new workflow file starts at 1.
    If run 1 is consumed without launching - an infrastructure failure, a cancelled job -
    the approval is spent and a fresh one naming run 2 is required. That is the boundary
    holding, not a defect.
  * It does not bind the commit. The approval file is part of the commit it would have to
    name, so a commit field cannot be filled in without a self-reference. The reviewed
    state is bound by DIGEST instead - the workflow, the launcher, this module, and the
    config, mesh and patch the launcher already checks.
  * The reservation below is per-run. It makes a second invocation INSIDE one run refuse,
    including after a crash. Across runs the run number and the attempt do that work.

Nothing here computes a physical E_C or g, and nothing here launches anything.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

#: The metadata GitHub assigns to a run. None of it is a dispatch input, and this module
#: never reads one: an input is what the caller says, and a caller may not state its own
#: run number.
RUN_ENV = {
    "repository": "GITHUB_REPOSITORY",
    "workflow_ref": "GITHUB_WORKFLOW_REF",
    "run_id": "GITHUB_RUN_ID",
    "run_number": "GITHUB_RUN_NUMBER",
    "run_attempt": "GITHUB_RUN_ATTEMPT",
    "ref": "GITHUB_REF",
}
NUMERIC = ("run_number", "run_attempt", "run_id")
#: Every field the approval's one_attempt block must carry. A partial block refuses: a
#: binding with a hole in it is not a binding.
REQUIRED_FIELDS = ("repository", "workflow_ref", "workflow_path", "workflow_sha256",
                   "run_number", "run_attempt", "ref", "code_sha256")
#: The code whose identity the approval pins, beside the workflow.
CODE_FILES = ("run_diagnostic.py", "run_authority.py")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class AuthorityRefusal(RuntimeError):
    """Raised instead of launching anything."""


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observed_run(env: dict | None = None) -> dict:
    """The run, as the RUNNER describes it.

    Missing or non-numeric metadata refuses. "I could not tell which run this is" is
    never "therefore proceed": outside a GitHub run there is no one-attempt authority to
    check, so there is nothing to launch under.
    """
    env = os.environ if env is None else env
    out: dict = {}
    for key, name in RUN_ENV.items():
        value = env.get(name)
        if value is None or not str(value).strip():
            raise AuthorityRefusal(
                f"{name} is not set, so the run cannot be identified. The one-attempt "
                "authority is checked against the metadata GitHub assigns; without it "
                "nothing is launched.")
        out[key] = str(value).strip()
    for key in NUMERIC:
        if not out[key].isdigit():
            raise AuthorityRefusal(
                f"{RUN_ENV[key]} is {out[key]!r}, which is not a number. Unreadable run "
                "metadata is not matching run metadata.")
        out[key] = int(out[key])
    return out


def _block(approval: dict) -> dict:
    block = approval.get("one_attempt")
    if not isinstance(block, dict):
        raise AuthorityRefusal(
            "the approval carries no one_attempt block. 'authorises: one execution' is a "
            "sentence; the block is what makes it enforceable, and without it this "
            "launcher has no way to tell a first attempt from a second.")
    missing = [f for f in REQUIRED_FIELDS if f not in block]
    if missing:
        raise AuthorityRefusal(f"the one_attempt block is missing {missing}: a binding "
                               "with a hole in it is not a binding")
    return block


def require_one_attempt(approval: dict, *, env: dict | None = None,
                        repo: Path = REPO) -> dict:
    """Refuse unless THIS run is the one the approval authorised. Returns what matched."""
    block = _block(approval)
    observed = observed_run(env)

    for key in ("run_number", "run_attempt"):
        if not isinstance(block[key], int) or isinstance(block[key], bool):
            raise AuthorityRefusal(f"approval one_attempt.{key} is {block[key]!r}, "
                                   "which is not an integer")
    if block["run_attempt"] != 1:
        raise AuthorityRefusal(
            f"approval one_attempt.run_attempt is {block['run_attempt']}: an approval may "
            "only ever authorise the FIRST attempt. A re-run is a new decision.")
    if observed["run_attempt"] != 1:
        raise AuthorityRefusal(
            f"this is attempt {observed['run_attempt']} of run {observed['run_number']}. "
            "A re-run, including 're-run failed jobs', is a second attempt and needs a "
            "separate human approval. Nothing is launched.")
    if observed["run_number"] != block["run_number"]:
        raise AuthorityRefusal(
            f"this is run number {observed['run_number']}; the approval authorises run "
            f"number {block['run_number']}. A fresh dispatch is a different run and needs "
            "a separate human approval. Nothing is launched.")
    for key, what in (("repository", "repository"), ("workflow_ref", "workflow and ref"),
                      ("ref", "ref")):
        if observed[key] != block[key]:
            raise AuthorityRefusal(
                f"{what} mismatch: the approval names {block[key]!r}, this run is "
                f"{observed[key]!r}")

    # the workflow_ref is owner/repo/path@ref; the path inside it must be the one the
    # approval pins by digest, so the digest cannot be of some other file
    path_in_ref = block["workflow_ref"].split("@", 1)[0]
    expected_tail = f"{block['repository']}/{block['workflow_path']}"
    if path_in_ref != expected_tail:
        raise AuthorityRefusal(
            f"one_attempt.workflow_path {block['workflow_path']!r} is not the path inside "
            f"workflow_ref {block['workflow_ref']!r}")

    workflow = Path(repo) / block["workflow_path"]
    if not workflow.is_file():
        raise AuthorityRefusal(f"the approved workflow {block['workflow_path']} is not in "
                               "this checkout")
    measured = sha256(workflow)
    if not SHA256_RE.fullmatch(str(block["workflow_sha256"])):
        raise AuthorityRefusal(f"one_attempt.workflow_sha256 "
                               f"{block['workflow_sha256']!r} is not a sha256")
    if measured != block["workflow_sha256"]:
        raise AuthorityRefusal(
            f"the workflow running this is {measured}, the approval authorises "
            f"{block['workflow_sha256']}. The reviewed workflow is what the run-metadata "
            "check is trusted through, so a changed one refuses.")

    code = block["code_sha256"]
    if not isinstance(code, dict) or set(code) != set(CODE_FILES):
        raise AuthorityRefusal(
            f"one_attempt.code_sha256 must name exactly {list(CODE_FILES)}, got "
            f"{sorted(code) if isinstance(code, dict) else code!r}")
    for name in CODE_FILES:
        want = str(code[name])
        if not SHA256_RE.fullmatch(want):
            raise AuthorityRefusal(f"one_attempt.code_sha256[{name}] is not a sha256")
        have = sha256(HERE / name)
        if have != want:
            raise AuthorityRefusal(
                f"{name} is {have}, the approval authorises {want}. The reviewed code is "
                "not what is about to run.")

    return {
        "mechanism": "GitHub-assigned run metadata, read from the environment",
        "inputs_are_not_authoritative": ("no dispatch input is read; a caller may not "
                                         "state its own run number"),
        "approved": {k: block[k] for k in REQUIRED_FIELDS},
        "observed": observed,
        "workflow_sha256_measured": measured,
        "code_sha256_measured": {n: sha256(HERE / n) for n in CODE_FILES},
    }


def default_reservation(observed: dict) -> Path:
    """Run-scoped and record-independent, so a second invocation cannot dodge it simply
    by naming a different record directory."""
    root = os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()
    return Path(root) / f"qmhp-first-moment-attempt-{observed['run_id']}.json"


def reserve_attempt(path, *, detail: dict | None = None) -> dict:
    """Spend the attempt BEFORE anything starts.

    Created atomically with O_EXCL, so two invocations racing cannot both win. If it
    already exists the attempt is spent and this refuses - which is the whole point: a
    failure, a cancellation, a timeout or a crash AFTER this line leaves the marker
    behind, and none of them restores permission. Nothing removes it.
    """
    path = Path(path)
    payload = {
        "reserved_utc": datetime.now(timezone.utc).isoformat(),
        "meaning": ("this attempt is SPENT. Its outcome - success, failure, timeout, "
                    "cancellation or no outcome at all - does not restore permission. A "
                    "further attempt requires a separate human approval."),
        **(detail or {}),
    }
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    except FileExistsError:
        existing = ""
        try:
            existing = path.read_text()[:400]
        except OSError:
            pass
        raise AuthorityRefusal(
            f"the attempt is already spent: {path} exists. Whatever happened to it, a "
            f"further attempt needs a separate human approval. {existing}") from None
    except OSError as exc:
        raise AuthorityRefusal(f"could not reserve the attempt at {path}: {exc}") from exc
    with os.fdopen(fd, "w") as handle:
        json.dump(payload, handle, indent=1)
        handle.write("\n")
    return {"reservation": str(path), **payload}
