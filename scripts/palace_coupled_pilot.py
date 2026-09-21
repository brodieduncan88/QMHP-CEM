"""The approved bounded numerical-method pilot: three Palace eigenmode solves.

Approved for the checkpoint-A review as three solves of the **same** declared
S1 chip-cell geometry at mesh level 1, differing only in element order and in
the size-field halo:

===== ======= ========= ==========================================
run   order   halo      purpose
===== ======= ========= ==========================================
P1    2       0.08 mm   the reference solve
P2    1       0.08 mm   element-order sensitivity, against P1
P3    2       0.12 mm   halo sensitivity, against P1
===== ======= ========= ==========================================

All three sit inside the declared 250 000 DOF ENGINEERING-RULE (208 670 /
39 832 / 235 806 measured). Each solve is capped at 45 minutes and killed at
the cap. No external or additional compute is used.

**This is a numerical-method pilot only.** It performs no coupling
extraction: it does not run the Route A inversion, it produces no `g`, no
`E_C`, no invariant triple, and it feeds no gate. It measures whether each
solve completes, the mode list in the declared window, the site energy
participation, wall time and memory, and nothing else. Route B, pulse work,
AMD-E, decoder work and mediator work are out of scope and are not touched.

The frozen acceptance criteria for the halo, predeclared in
``docs/coupled-candidate/execution-proposal.md`` §4.2 **before** this ran and
unchanged here:

* ``Δp = abs(|p₁| − |p₃|) / max(|p₁|, |p₃|) ≤ 1e-2``
* ``Δf = |f₁ − f₃| / f₁ ≤ 1e-4``

The **tolerances** are exactly as frozen. The Δp *numerator* is the one
corrective change: §4.2 wrote it as ``|p₁ − p₃|`` on the signed participation,
and Palace's sign is ``sign(Re I)``, which tracks the eigenvector's arbitrary
global phase rather than anything physical. Comparing signed values across two
independent solves therefore mixes a solver convention into the measurement.
See ``docs/coupled-candidate/corrective-analysis.md`` §D.1.

Evidence is append-only: one record directory per invocation, every solver
input and output kept, manifest written last.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import time
import weakref
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import manifest  # noqa: E402
from solvers.palace import outputs as pout  # noqa: E402
from solvers.palace.coupled_config import (  # noqa: E402
    COUPLED_SOLVER_RULES,
    CoupledRun,
    build_coupled_config,
    superinductor_henry,
)
from solvers.palace.coupled_geometry import chip_cell_from_declaration  # noqa: E402
from solvers.palace.mode_admission import (  # noqa: E402
    ADMISSION_RULE,
    COMPARISON_CONVENTION,
    MATCHING_RULE,
    admit_modes,
    check_row_correspondence,
    join_modes_by_id,
    label_roles,
    match_runs,
    unique_field_dominated,
)
from solvers.palace.coupled_mesh import dry_run  # noqa: E402

SUMMARY_SCHEMA = "qmhp-cem.coupled-pilot/0.1.0"
DEFAULT_IMAGE = "qmhp-cem/palace:0.13.0"
CONTAINER_WORKDIR = "/work"
CONFIG_FILENAME = "config.json"

#: The approved pilot. Changing any of it is a new approval, not an edit.
RUNS: tuple[CoupledRun, ...] = (
    CoupledRun("P1", finite_element_order=2, halo_mm=0.08, purpose="the reference solve"),
    CoupledRun("P2", finite_element_order=1, halo_mm=0.08,
               purpose="element-order sensitivity, against P1"),
    CoupledRun("P3", finite_element_order=2, halo_mm=0.12,
               purpose="halo sensitivity, against P1"),
)

#: Frozen before the pilot ran (execution-proposal.md §4.2). Not editable here.
HALO_CRITERIA: dict[str, float] = {
    "max_relative_participation_change": 1.0e-2,
    "max_relative_frequency_change": 1.0e-4,
}

#: Per-solve wall-clock cap, as approved.
SOLVE_TIMEOUT_S = 45 * 60

#: Declared DOF ENGINEERING-RULE; every approved run is inside it.
DOF_BUDGET = 250_000

STATEMENT = (
    "Numerical-method pilot. Three Palace eigenmode solves of the same declared S1 chip cell, "
    "differing only in element order and size-field halo. NO coupling extraction was performed: "
    "no Route A inversion, no g, no invariant triple, no gate input, no Route B. The record "
    "carries completion, the mode list in the declared window, the site energy participation, "
    "wall time and memory. Every geometric value remains an unapproved ENGINEERING-SEED."
)


# --- execution authority ------------------------------------------------------
#
# .github/pilot-approval.json ALREADY EXISTS. It is the HISTORICAL record of the
# 16 September 2026 approval and the record of attempt 1, which ran. Its mere
# presence is not permission to solve again, and this module must not read it as
# though it were: a file that has been on disk since September cannot authorise a
# launch today.
#
# So the authority this module requires is a SEPARATE, EXPLICIT block --
# `execution_authority` -- which that file does not currently carry. Until a human
# adds one, every solver-capable subprocess here refuses. `--prepare-only` is
# unaffected: it meshes and writes configs and cannot launch Palace, so it does
# not consult this gate at all.
#
# The block binds an execution to all six things at once. Any one of them being
# absent, wrong or merely stale is a refusal BEFORE a runtime is invoked:
#
#   reviewed code           driver_sha256 -- this file's own bytes, so an approval
#                           cannot survive an edit to the driver it approved
#   reviewed configuration  declaration_sha256 -- the declaration actually passed
#   frozen run set          runs -- exactly P1/P2/P3, order, halo and level
#   resource caps           dof_budget 250000 and per_solve_wall_clock_cap_s 2700
#   execution mechanism     runtime, image and mpi_processes, checked again at the
#                           launch primitive, not only at the top
#   a narrow attempt        a strictly new attempt number, inside a short explicit UTC
#                           window. NOT single-use: nothing consumes the attempt, since
#                           that would mean writing to an approval record. Within a live
#                           window the same block admits a further invocation, and note
#                           that the workflow re-triggers on any later push touching
#                           .github/pilot-approval.json. The window and the ledger bound
#                           that exposure; they do not close it.

#: The historical approval record, which is also the workflow trigger. Read here
#: ONLY for the `execution_authority` block; nothing else in it grants authority.
PILOT_APPROVAL = REPO_ROOT / ".github" / "pilot-approval.json"

#: Where this repository's committed evidence lives. Deliberately NOT ``--results-root``:
#: what has already executed is a property of the repository, not of where this
#: invocation happens to be told to write, and reading the CLI value here would let an
#: invocation shrink its own history by pointing at an empty directory.
RESULTS_ROOT = REPO_ROOT / "results"

#: This file. Its digest is what an authority must name, so approving the pilot
#: approves the code that was reviewed rather than the name of a script.
DRIVER_PATH = Path(__file__).resolve()

#: Keys an `execution_authority` block must carry. Unknown keys are refused
#: rather than ignored: a typo must not silently become "no constraint".
AUTHORITY_REQUIRED_KEYS = frozenset({
    "schema", "authorises", "attempt", "approved_by", "not_before_utc", "expires_utc",
    "driver_sha256", "declaration_sha256", "runs", "dof_budget",
    "per_solve_wall_clock_cap_s", "execution_mechanism", "out_of_scope", "supersedes",
})
AUTHORITY_SCHEMA = "qmhp-cem.pilot-execution-authority/0.1.0"
MECHANISM_REQUIRED_KEYS = frozenset({"runtime", "image", "mpi_processes"})

#: An authority window wider than this is not a narrowly defined attempt. Without
#: a ceiling, "expires" could be set decades out and the block would become the
#: same standing permission the historical record must not be.
MAX_AUTHORITY_WINDOW_S = 7 * 24 * 3600

#: The scope the pilot was approved under. An authority must restate it exactly,
#: AND the approval record must still carry it: dropping "the Route A inversion"
#: from either is an altered scope, not a formatting change.
OUT_OF_SCOPE: tuple[str, ...] = (
    "the coupling extraction itself",
    "the Route A inversion",
    "Route B",
    "pulse optimisation",
    "AMD-E",
    "decoder work",
    "mediator work",
    "any broader redesign",
)


class PilotRefusal(RuntimeError):
    """Raised instead of launching anything."""


_AUTHORITY_TOKEN = object()

#: The authorities this process actually granted. Identity-based and weak, so an
#: authority cannot be forged by producing an object of the right type and cannot
#: be resurrected by id reuse after it is dropped.
_GRANTED: "weakref.WeakSet[ExecutionAuthority]" = weakref.WeakSet()


class ExecutionAuthority:
    """Proof that a live `execution_authority` block was read and accepted.

    Being an INSTANCE of this class is deliberately not sufficient. Three routes
    produce one without the gate ever running -- ``object.__new__`` followed by
    setting the slots, a subclass whose ``__init__`` never calls ``super()``, and
    reading the module-private token and calling the constructor -- and all three
    were demonstrated reaching a real ``docker`` argv before this was tightened.

    So the authority is a MEMBERSHIP, not a type. Only
    :func:`require_execution_authority` registers an instance in ``_GRANTED``, and
    :func:`_require_authority` demands membership as well as the exact type.
    ``object.__new__`` and the subclass never enter the set, subclassing is
    refused outright, and the token alone no longer buys anything.

    The honest residual: code that can edit this module, or reach ``_GRANTED``
    itself, can still forge. This is a guard against a careless or mistaken launch
    path, not a security boundary against code running inside the process.
    """

    _FIELDS = ("attempt", "runtime", "image", "mpi_processes",
               "approval_sha256", "driver_sha256", "declaration_sha256", "granted_utc")
    __slots__ = (*_FIELDS, "__weakref__")

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise PilotRefusal(
            "ExecutionAuthority may not be subclassed: a subclass would satisfy an "
            "isinstance check without ever passing the gate")

    def __init__(self, token: Any, **fields: Any) -> None:
        if token is not _AUTHORITY_TOKEN:
            raise PilotRefusal(
                "an ExecutionAuthority can only be produced by require_execution_authority(); "
                "constructing one directly would forge the approval it stands for"
            )
        for key in self._FIELDS:
            setattr(self, key, fields[key])

    def as_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self._FIELDS}


def _same(a: Any, b: Any) -> bool:
    """Equality that does not let ``1``, ``1.0`` and ``true`` stand in for one another.

    JSON is written by hand here, and Python's ``==`` would accept
    ``"dof_budget": 250000.0`` and ``"level": true`` as the declared integers. A bound
    field must match in TYPE as well as value, or the binding is weaker than it reads.
    """
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def executed_pilots(results_root: Path | None = None) -> list[str]:
    """Every committed record THIS driver produced, identified by its own schema.

    The approval record's ``reruns`` ledger is not a complete history and must not be
    read as one. It lists attempt 1 and explains that a re-run followed; that re-run is
    the execution which produced ``results/COUPLED-PILOT-20260916T035733Z`` (workflow run
    35053649226), and it has no ledger entry of its own. Counting the ledger alone
    therefore makes the pilot look like it ran once when it ran twice, and would admit
    "attempt 2" as new.

    So prior executions are derived from the evidence as well. A record counts only if
    its ``summary.json`` carries this module's SUMMARY_SCHEMA, which excludes the
    corrective-analysis record ``COUPLED-PILOT-CORR-*`` - that one launched nothing.
    """
    root = RESULTS_ROOT if results_root is None else Path(results_root)
    if not root.is_dir():
        return []
    found = []
    for record in sorted(root.iterdir()):
        if not record.is_dir():
            continue
        summary = record / "summary.json"
        if not summary.is_file():
            continue
        try:
            body = json.loads(summary.read_text())
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            # FAIL CLOSED. A record this gate cannot read might be an execution, and
            # skipping it would quietly lower the floor the next attempt must clear.
            raise PilotRefusal(
                f"{summary} cannot be read ({type(exc).__name__}: {exc}), so the number of "
                "executions this repository accounts for cannot be established. Resolve that "
                "before an execution is authorised.")
        if isinstance(body, dict) and body.get("schema") == SUMMARY_SCHEMA:
            found.append(record.name)
    return found


def prior_executions(approval: dict[str, Any], results_root: Path | None = None) -> list[str]:
    """Everything the repository can account for as an execution of this pilot."""
    reruns = approval.get("reruns") or []
    if not isinstance(reruns, list):
        raise PilotRefusal(
            f"the approval record's reruns ledger is a {type(reruns).__name__}, not a list; "
            "this gate cannot establish what has already executed")
    ledger = []
    for entry in reruns:
        attempt = entry.get("attempt") if isinstance(entry, dict) else None
        if not isinstance(attempt, int) or isinstance(attempt, bool):
            # FAIL CLOSED rather than filtering. Dropping an entry the gate cannot parse
            # would read as "nothing has been spent", which is the opposite of what an
            # unreadable ledger means.
            raise PilotRefusal(
                f"the approval record's reruns ledger has an entry this gate cannot read "
                f"({entry!r}); an unreadable ledger is not an empty one")
        ledger.append(attempt)
    return [f"attempt {n}" for n in sorted(ledger)] + [
        f"record {name}" for name in executed_pilots(results_root)]


def _authority_instant(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise PilotRefusal(f"execution_authority.{field} must be an RFC 3339 UTC string")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PilotRefusal(f"execution_authority.{field} is not a timestamp: {value!r} ({exc})")
    if moment.tzinfo is None:
        raise PilotRefusal(f"execution_authority.{field} must carry a UTC offset, got {value!r}")
    return moment.astimezone(timezone.utc)


def require_execution_authority(
    *,
    runtime: str,
    image: str,
    mpi_processes: int,
    declaration_path: Path,
    path: Path | None = None,
    now: datetime | None = None,
    results_root: Path | None = None,
) -> ExecutionAuthority:
    """Refuse unless a live, matching `execution_authority` block authorises THIS run.

    Every refusal happens before any runtime is invoked. The checks are ordered
    from the cheapest and most structural to the most specific so that a missing
    block -- the current state of the repository -- is named as such rather than
    as one of the mismatches below it.
    """
    path = PILOT_APPROVAL if path is None else Path(path)
    if not path.is_file():
        raise PilotRefusal(
            f"no approval record at {path}: the coupled pilot launches nothing without one")
    try:
        approval = json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        raise PilotRefusal(f"{path} could not be read as JSON ({type(exc).__name__}): {exc}")
    if not isinstance(approval, dict):
        raise PilotRefusal(f"{path} must be a JSON object, got {type(approval).__name__}")

    if "execution_authority" not in approval:
        raise PilotRefusal(
            f"{path} carries no execution_authority block. It is the HISTORICAL record of the "
            "2026-09-16 approval and of attempt 1, which already ran; its presence is not "
            "permission to solve again. A new execution needs a separate, explicit "
            "execution_authority naming the reviewed driver and declaration digests, the frozen "
            "P1/P2/P3 run set, the 250000 DOF and 2700 s caps, the image and runtime, and one "
            "narrowly bounded attempt. Use --prepare-only to mesh and write configs instead.")
    authority = approval["execution_authority"]
    if not isinstance(authority, dict):
        raise PilotRefusal("execution_authority must be a JSON object")

    unknown = sorted(set(authority) - AUTHORITY_REQUIRED_KEYS)
    if unknown:
        raise PilotRefusal(f"unknown execution_authority key(s): {unknown}")
    missing = sorted(AUTHORITY_REQUIRED_KEYS - set(authority))
    if missing:
        raise PilotRefusal(f"execution_authority is missing {missing}")

    if authority["schema"] != AUTHORITY_SCHEMA:
        raise PilotRefusal(
            f"execution_authority.schema is {authority['schema']!r}, not {AUTHORITY_SCHEMA!r}")
    if authority["authorises"] != "one execution":
        raise PilotRefusal(
            f"execution_authority.authorises is {authority['authorises']!r}; this gate accepts "
            "the literal 'one execution' only. NOTE what that does and does not mean: nothing "
            "here CONSUMES the attempt, because doing so would write to an approval record. "
            "Reuse is bounded by the window and by the spent-attempt ledger, not prevented "
            "within a live window.")
    if not isinstance(authority["approved_by"], str) or not authority["approved_by"].strip():
        raise PilotRefusal("execution_authority.approved_by must name who approved this attempt")

    # --- the attempt is new, and every prior one is acknowledged ---------------
    attempt = authority["attempt"]
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise PilotRefusal(f"execution_authority.attempt must be a positive integer, got {attempt!r}")
    prior = prior_executions(approval, results_root)
    if not _same(authority["supersedes"], prior):
        raise PilotRefusal(
            f"execution_authority.supersedes is {authority['supersedes']!r}, but this repository "
            f"accounts for {prior!r}. An approval must name every execution it follows, and the "
            "list is derived from the ledger AND from the committed records this driver wrote - "
            "the ledger alone is incomplete, because the re-run that produced "
            "results/COUPLED-PILOT-20260916T035733Z has no ledger entry.")
    if attempt <= len(prior):
        raise PilotRefusal(
            f"execution_authority.attempt {attempt} is not new: {len(prior)} execution(s) are "
            f"already accounted for ({prior}). A spent attempt is evidence, not authority.")

    # --- the window is live and narrow -----------------------------------------
    not_before = _authority_instant(authority["not_before_utc"], "not_before_utc")
    expires = _authority_instant(authority["expires_utc"], "expires_utc")
    if expires <= not_before:
        raise PilotRefusal(
            f"execution_authority expires_utc {expires.isoformat()} is not after not_before_utc "
            f"{not_before.isoformat()}")
    window = (expires - not_before).total_seconds()
    if window > MAX_AUTHORITY_WINDOW_S:
        raise PilotRefusal(
            f"execution_authority covers {window / 86400:.1f} days; a narrowly defined attempt is "
            f"at most {MAX_AUTHORITY_WINDOW_S / 86400:.0f} days, otherwise the block becomes the "
            "standing permission the historical record must not be")
    moment = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
    if moment < not_before:
        raise PilotRefusal(
            f"execution_authority is not yet live: it begins {not_before.isoformat()}, now is "
            f"{moment.isoformat()}")
    if moment >= expires:
        raise PilotRefusal(
            f"execution_authority expired {expires.isoformat()}; now is {moment.isoformat()}. A "
            "historical authority is not a current one.")

    # --- bound to the reviewed code and configuration ---------------------------
    driver_sha = manifest.file_digest(DRIVER_PATH)
    if authority["driver_sha256"] != driver_sha:
        raise PilotRefusal(
            f"execution_authority.driver_sha256 is {authority['driver_sha256']!r} but "
            f"{DRIVER_PATH.name} hashes to {driver_sha!r}: this approval was given for different "
            "driver code and does not carry over to an edited one")
    declaration_path = Path(declaration_path)
    if not declaration_path.is_file():
        raise PilotRefusal(f"the declaration {declaration_path} does not exist")
    declaration_sha = manifest.file_digest(declaration_path)
    if authority["declaration_sha256"] != declaration_sha:
        raise PilotRefusal(
            f"execution_authority.declaration_sha256 is {authority['declaration_sha256']!r} but "
            f"{declaration_path} hashes to {declaration_sha!r}")

    # --- bound to the frozen run set and the caps -------------------------------
    approved_runs = [
        {"name": r.name, "finite_element_order": r.finite_element_order,
         "halo_mm": r.halo_mm, "level": r.level}
        for r in RUNS
    ]
    if not _same(authority["runs"], approved_runs):
        raise PilotRefusal(
            f"execution_authority.runs is {authority['runs']!r}, which is not the frozen pilot "
            f"{approved_runs!r}. Changing the run set is a new approval, not an edit.")
    if not _same(authority["dof_budget"], DOF_BUDGET):
        raise PilotRefusal(
            f"execution_authority.dof_budget is {authority['dof_budget']!r}, not the declared "
            f"{DOF_BUDGET}")
    if not _same(authority["per_solve_wall_clock_cap_s"], SOLVE_TIMEOUT_S):
        raise PilotRefusal(
            f"execution_authority.per_solve_wall_clock_cap_s is "
            f"{authority['per_solve_wall_clock_cap_s']!r}, not the approved {SOLVE_TIMEOUT_S}")

    # --- bound to the execution mechanism ---------------------------------------
    mechanism = authority["execution_mechanism"]
    if not isinstance(mechanism, dict):
        raise PilotRefusal("execution_authority.execution_mechanism must be a JSON object")
    unknown = sorted(set(mechanism) - MECHANISM_REQUIRED_KEYS)
    if unknown:
        raise PilotRefusal(f"unknown execution_mechanism key(s): {unknown}")
    missing = sorted(MECHANISM_REQUIRED_KEYS - set(mechanism))
    if missing:
        raise PilotRefusal(f"execution_mechanism is missing {missing}")
    for key, got in (("runtime", runtime), ("image", image), ("mpi_processes", mpi_processes)):
        if not _same(mechanism[key], got):
            raise PilotRefusal(
                f"execution_mechanism.{key} is {mechanism[key]!r} but this invocation would use "
                f"{got!r}: the approval does not cover this execution mechanism")

    # --- bound to the approved scope, in both places ----------------------------
    if not _same(authority["out_of_scope"], list(OUT_OF_SCOPE)):
        raise PilotRefusal(
            "execution_authority.out_of_scope does not restate the approved scope exactly; "
            f"expected {list(OUT_OF_SCOPE)!r}")
    if not _same(approval.get("explicitly_out_of_scope"), list(OUT_OF_SCOPE)):
        raise PilotRefusal(
            "the approval record's explicitly_out_of_scope no longer matches the approved scope. "
            f"Expected {list(OUT_OF_SCOPE)!r}, found {approval.get('explicitly_out_of_scope')!r}. "
            "An altered scope is a new approval, not an execution of this one.")

    granted = ExecutionAuthority(
        _AUTHORITY_TOKEN,
        attempt=attempt,
        runtime=runtime,
        image=image,
        mpi_processes=mpi_processes,
        approval_sha256=manifest.file_digest(path),
        driver_sha256=driver_sha,
        declaration_sha256=declaration_sha,
        granted_utc=moment.isoformat(),
    )
    _GRANTED.add(granted)
    return granted


def _require_authority(authority: Any, what: str, *,
                       runtime: str | None = None,
                       image: str | None = None) -> ExecutionAuthority:
    """The precondition of every solver-capable subprocess in this module.

    Re-checking the runtime and image HERE, and not only in
    :func:`require_execution_authority`, is deliberate: an authority granted for
    ``docker``/``qmhp-cem/palace:0.13.0`` cannot be carried into a call that
    would launch something else.
    """
    if type(authority) is not ExecutionAuthority or authority not in _GRANTED:
        raise PilotRefusal(
            f"{what} requires a validated execution authority; got "
            f"{type(authority).__name__}. Being one of these objects is not enough: it must be "
            "one require_execution_authority() granted in this process. Nothing in this module "
            "launches a runtime without that.")
    if runtime is not None and authority.runtime != runtime:
        raise PilotRefusal(
            f"{what} would use runtime {runtime!r}, but the authority covers "
            f"{authority.runtime!r}")
    if image is not None and authority.image != image:
        raise PilotRefusal(
            f"{what} would use image {image!r}, but the authority covers {authority.image!r}")
    return authority

# --- solver invocation --------------------------------------------------------


def _image_identity(authority: Any, runtime: str, image: str) -> dict[str, Any]:
    """Inspect the image. Docker inspection is a container-runtime execution, so it
    sits behind the same gate as the solve it would identify."""
    _require_authority(authority, "image inspection", runtime=runtime, image=image)
    out: dict[str, Any] = {"image": image, "runtime": runtime}
    try:
        got = subprocess.run(
            [runtime, "image", "inspect", image, "--format", "{{.Id}}"],
            capture_output=True, text=True, timeout=120, check=False,
        )
        out["image_id"] = got.stdout.strip() or None
        digests = subprocess.run(
            [runtime, "image", "inspect", image, "--format", "{{json .RepoDigests}}"],
            capture_output=True, text=True, timeout=120, check=False,
        )
        parsed = json.loads(digests.stdout.strip() or "[]")
        out["repo_digest"] = parsed[0] if parsed else None
        labels = subprocess.run(
            [runtime, "image", "inspect", image, "--format", "{{json .Config.Labels}}"],
            capture_output=True, text=True, timeout=120, check=False,
        )
        out["labels"] = json.loads(labels.stdout.strip() or "null")
    except Exception as exc:  # noqa: BLE001 - identity is evidence, not control flow
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def _user_flag(authority: Any, runtime: str) -> list[str]:
    """Run the container as the invoking user, as the main adapter does.

    Without this Palace writes ``postpro/`` as root, and the evidence is then
    owned by a user the harness cannot manage: the first pilot run produced
    valid results that git could not commit, because a rebase could not unlink
    root-owned files. The solver output is evidence, so it must be writable by
    whoever records it.
    """
    _require_authority(authority, "runtime capability probe", runtime=runtime)
    if not hasattr(os, "getuid"):
        return []
    try:
        info = subprocess.run(
            [runtime, "info", "--format", "{{json .SecurityOptions}}"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if "rootless" in (info.stdout or ""):
            return []                       # already mapped to this user
    except Exception:  # noqa: BLE001 - fall through to the explicit mapping
        pass
    return ["--user", f"{os.getuid()}:{os.getgid()}"]


def _run_palace(authority: Any, runtime: str, image: str, work_dir: Path, name: str,
                np_: int) -> dict[str, Any]:
    """One container run. Refuses without a validated authority; otherwise never raises,
    because from that point on a failure is a recorded outcome rather than an error."""
    _require_authority(authority, "a Palace container run", runtime=runtime, image=image)
    if not _same(np_, authority.mpi_processes):
        raise PilotRefusal(
            f"a Palace container run would use {np_} MPI process(es), but the authority covers "
            f"{authority.mpi_processes}")
    command = [
        runtime, "run", "--rm", "--network", "none", "--hostname", "localhost",
        "--name", name, *_user_flag(authority, runtime), "-e", "HOME=/tmp",
        "-e", "OMP_NUM_THREADS=1",
        "-e", "OPENBLAS_NUM_THREADS=1",
        "-v", f"{work_dir.resolve()}:{CONTAINER_WORKDIR}", "-w", CONTAINER_WORKDIR,
        image, "-np", str(np_), CONFIG_FILENAME,
    ]
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=SOLVE_TIMEOUT_S)
        returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = None
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        subprocess.run([runtime, "kill", name], capture_output=True, text=True, timeout=60, check=False)
    wall = time.perf_counter() - t0
    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    (work_dir / "palace_log.txt").write_text((stdout or "") + (stderr or ""))
    return {
        "command": command,
        "returncode": returncode,
        "timed_out": timed_out,
        "timeout_s": SOLVE_TIMEOUT_S,
        "started_utc": started.isoformat(),
        "wall_clock_s": wall,
        # ru_maxrss is the peak RSS of REAPED CHILDREN of this process, i.e. of
        # the container runtime CLI, not of the solver inside the container.
        # Recorded as what it is; the solver's own peak is read from its log
        # where Palace reports it.
        "runner_cli_peak_rss_kb_delta": max(0, after - before),
        "runner_cli_peak_rss_kb": after,
        "memory_note": (
            "ru_maxrss measures the container runtime CLI in this process tree, not the solver "
            "inside the container. Any solver-side figure below is quoted from Palace's own log."
        ),
    }


def _memory_lines_from_log(log: str) -> list[str]:
    """Whatever Palace itself says about memory, verbatim."""
    keys = ("memory", "rss", "gib", "gb of", "allocated")
    return [
        line.strip() for line in log.splitlines()
        if any(k in line.lower() for k in keys)
    ][:40]


# --- one pilot run ------------------------------------------------------------


def execute_run(
    spec: CoupledRun, declaration: dict[str, Any], run_dir: Path, *,
    runtime: str, image: str, np_: int, prepare_only: bool, authority: Any = None,
) -> dict[str, Any]:
    """Mesh, configure and solve.

    Raises ONLY :class:`PilotRefusal`, and only when no valid authority was granted.
    Every other outcome - a timeout, a nonzero exit, a mesh failure, a DOF overrun - is
    recorded as evidence and returned, which is the property ``main`` relies on to write
    ``summary.json``, ``report.md`` and the manifest for a failed run. A refusal is not
    one of those outcomes: it is the pilot not happening, so filing it as an ERROR entry
    would put the absence of authority in the record where something that ran belongs.
    ``main`` cannot meet that raise in practice, because it validates before the loop.

    ``prepare_only`` meshes and writes the config and returns before any runtime is
    touched, so it needs no authority. Anything else does, and it is demanded here
    BEFORE the mesh is built rather than at the container call: refusing after twenty
    minutes of meshing would be a refusal in name only.
    """
    if not prepare_only:
        _require_authority(authority, "a pilot solve", runtime=runtime, image=image)
    entry: dict[str, Any] = {"spec": spec.as_dict(), "status": "PREPARED"}
    solver_dir = run_dir / "solver"
    solver_dir.mkdir(parents=True, exist_ok=True)
    try:
        cell = chip_cell_from_declaration(declaration)
        report = dry_run(cell, spec.level, solver_dir, dof_budget=DOF_BUDGET, halo_mm=spec.halo_mm)
        mesh = report.as_dict()
        entry["mesh"] = mesh
        entry["clearance_report"] = list(cell.clearance_report())
        dof = mesh["measured"][f"dof_order{spec.finite_element_order}"]
        entry["dof_for_this_order"] = dof
        entry["within_dof_budget"] = dof <= DOF_BUDGET
        if not entry["within_dof_budget"]:
            entry["status"] = "BLOCKED"
            entry["failure"] = (
                f"{dof} DOF at order {spec.finite_element_order} exceeds the declared budget of "
                f"{DOF_BUDGET}; the approved pilot is inside it, so this is a defect, not a run"
            )
            return entry

        substrate = next(m for m in declaration["materials"] if m["id"] == "substrate")
        E_L = next(p for p in declaration["parameter_register"] if p["id"] == "E_L_F1")["value"]
        inductance = superinductor_henry(float(E_L))
        config = build_coupled_config(
            Path(mesh["mesh_file"]).name,
            order=spec.finite_element_order,
            substrate_permittivity=float(substrate["permittivity"]),
            port_inductance_H=inductance,
            port_direction=_port_direction(declaration),
        )
        (solver_dir / CONFIG_FILENAME).write_text(json.dumps(config, indent=2) + "\n")
        entry["config"] = config
        entry["port_inductance_H"] = inductance
        entry["solver_rules"] = dict(COUPLED_SOLVER_RULES)
        if prepare_only:
            entry["status"] = "PREPARED"
            return entry

        name = f"qmhp-coupled-pilot-{spec.name}".lower()
        run_info = _run_palace(authority, runtime, image, solver_dir, name, np_)
        entry["run"] = run_info
        (solver_dir / "palace_run.json").write_text(json.dumps(run_info, indent=1) + "\n")
        log = (solver_dir / "palace_log.txt").read_text()
        entry["log_memory_lines"] = _memory_lines_from_log(log)
        if run_info["timed_out"]:
            entry["status"] = "TIMEOUT"
            entry["failure"] = f"exceeded the {SOLVE_TIMEOUT_S}s cap"
            return entry
        if run_info["returncode"] != 0:
            entry["status"] = "RUN_FAILED"
            entry["failure"] = f"palace exited {run_info['returncode']}"
            return entry

        post = solver_dir / "postpro"
        table = pout.parse_eig_csv(post / "eig.csv")
        modes = [
            {
                "index": r.index,
                "frequency_GHz": r.frequency_re_GHz,
                "frequency_im_GHz": r.frequency_im_GHz,
                "quality_factor": r.quality_factor,
                "backward_error": r.backward_error,
                "in_declared_window": (
                    COUPLED_SOLVER_RULES["band_floor_GHz"]
                    <= r.frequency_re_GHz
                    <= COUPLED_SOLVER_RULES["band_ceiling_GHz"]
                ),
            }
            for r in table.rows
        ]
        # Join the five per-mode tables ON THE MODE ID, check the identities
        # that span them, then decide validity. Algebraic convergence and mode
        # validity are separate dispositions; neither uses participation rank.
        joined = join_modes_by_id(post)
        correspondence = check_row_correspondence(joined, {1: inductance})
        admission = admit_modes(
            spec.name,
            joined,
            backward_error_tolerance=COUPLED_SOLVER_RULES["eigenmode_backward_error_max_tolerance"],
            row_correspondence=correspondence,
        )
        by_mode = {m.record.mode: m for m in admission.modes}
        for mode in modes:
            classified = by_mode.get(int(round(mode["index"])))
            if classified is None:
                raise pout.PalaceOutputError(
                    f"eig.csv mode {mode['index']} has no joined row; the per-mode tables disagree"
                )
            mode["site_participation"] = classified.record.signed_participation(1)
            mode["abs_site_participation"] = classified.record.abs_participation(1)
            mode["energy_balance_ratio"] = classified.record.energy_balance_ratio
            mode["energy_balance_defect"] = classified.record.energy_balance_defect
            mode["disposition"] = classified.disposition
        entry["row_correspondence"] = correspondence.as_dict()
        entry["admission"] = admission.as_dict()
        entry["roles"] = [r.as_dict() for r in label_roles(admission.admitted)]
        # Keyed by mode id: an array whose only link back to a mode is its
        # position is a positional join waiting to slip.
        entry["energy_balance_by_mode"] = {
            str(m.record.mode): m.record.energy_balance_defect for m in admission.modes
        }
        entry["palace_metadata"] = pout.read_metadata_json(post / "palace.json")
        entry["modes"] = modes
        entry["modes_in_window"] = [m for m in modes if m["in_declared_window"]]
        entry["admitted_in_window"] = [
            m.mode
            for m in admission.admitted_in_window(
                COUPLED_SOLVER_RULES["band_floor_GHz"], COUPLED_SOLVER_RULES["band_ceiling_GHz"]
            )
        ]
        entry["max_backward_error"] = table.max_backward_error
        entry["status"] = "COMPLETED"
    except PilotRefusal:
        # A refusal is not an outcome of the pilot; it is the pilot not happening.
        # Recording it as an ERROR entry would file the absence of authority
        # alongside solver failures, where it would read as something that ran.
        raise
    except Exception as exc:  # noqa: BLE001 - a failure is evidence
        entry["status"] = entry.get("status", "ERROR") if entry.get("status") in {
            "TIMEOUT", "RUN_FAILED", "BLOCKED"
        } else "ERROR"
        entry.setdefault("failure", f"{type(exc).__name__}: {exc}")
    return entry


def _port_direction(declaration: dict[str, Any]) -> str:
    port = next(p for p in declaration["ports"] if p["id"] == "P_F1")
    direction = port["direction"]
    return direction if isinstance(direction, str) else direction[0]


# --- comparisons --------------------------------------------------------------


def _admitted_in_window(entry: dict[str, Any]) -> list[Any]:
    """The admitted modes of one run inside the declared window.

    Rebuilt from the admission report the run already recorded, so the
    comparison cannot see a mode the admission step rejected.
    """
    admission = entry.get("admission") or {}
    floor = COUPLED_SOLVER_RULES["band_floor_GHz"]
    ceiling = COUPLED_SOLVER_RULES["band_ceiling_GHz"]
    from solvers.palace.mode_admission import ModeRecord

    admitted = []
    for mode in admission.get("modes", []):
        if mode.get("disposition") != "ADMITTED":
            continue
        frequency = mode["frequency_GHz"]
        if not (floor <= frequency <= ceiling):
            continue
        signed = {int(k): v for k, v in mode["participation_signed"].items()}
        admitted.append(
            ModeRecord(
                mode=mode["mode"],
                frequency_GHz=frequency,
                frequency_im_GHz=mode["frequency_im_GHz"],
                backward_error=mode["backward_error"],
                absolute_error=mode.get("absolute_error"),
                electric_J=mode["energy_J"]["E_elec"],
                magnetic_J=mode["energy_J"]["E_mag"],
                capacitive_J=mode["energy_J"]["E_cap"],
                inductive_J=mode["energy_J"]["E_ind"],
                participation=signed,
                current_A={
                    int(k): complex(v["re"], v["im"]) for k, v in mode["current_A"].items()
                },
                voltage_V={
                    int(k): complex(v["re"], v["im"]) for k, v in mode["voltage_V"].items()
                },
            )
        )
    return admitted


def compare(a: dict[str, Any], b: dict[str, Any], label: str) -> dict[str, Any]:
    """Relative change between two runs, over MATCHED admitted modes.

    The mode the frozen criterion is written about — "the readout-like mode" —
    is identified as the single field-dominated admitted mode of run A, after
    admission, not as whatever row carries the smallest ``|p|``. Every matched
    pair is reported, so no pair is selected once the numbers are known; the
    headline delta is the criterion's own subject where that subject is
    unique, and the worst pair where it is not.

    The participation change uses MAGNITUDES. Palace's participation sign is
    ``sign(Re I)`` and the phase of a single port phasor is not invariant under
    the eigenvector's arbitrary global scale, so a signed difference between
    two independent solves mixes a solver convention into the comparison. The
    signed values are carried through unchanged.
    """
    out: dict[str, Any] = {
        "comparison": label,
        "available": False,
        "matching_rule": dict(MATCHING_RULE),
        "admission_rule": dict(ADMISSION_RULE),
        "convention": dict(COMPARISON_CONVENTION),
    }
    if a.get("status") != "COMPLETED" or b.get("status") != "COMPLETED":
        out["reason"] = (
            f"not both solves completed ({a['spec']['name']}: {a.get('status')}, "
            f"{b['spec']['name']}: {b.get('status')})"
        )
        return out

    admitted_a, admitted_b = _admitted_in_window(a), _admitted_in_window(b)
    match = match_runs(f"{a['spec']['name']} vs {b['spec']['name']}", admitted_a, admitted_b)
    out["match"] = match.as_dict()
    out["admitted_in_window"] = {
        a["spec"]["name"]: [r.mode for r in admitted_a],
        b["spec"]["name"]: [r.mode for r in admitted_b],
    }
    if not match.comparable:
        out["reason"] = match.reason
        return out

    subject = unique_field_dominated(admitted_a)
    pairs = [
        {
            "a_mode": pair.a.mode,
            "b_mode": pair.b.mode,
            "a_frequency_GHz": pair.a.frequency_GHz,
            "b_frequency_GHz": pair.b.frequency_GHz,
            "delta_f_relative": pair.delta_f_relative,
            "delta_abs_p_relative": pair.delta_abs_participation_relative.get(1),
            "is_criterion_subject": bool(subject is not None and pair.a.mode == subject.mode),
            "signed_participation": pair.signed_participation,
        }
        for pair in match.pairs
    ]
    chosen = next((row for row in pairs if row["is_criterion_subject"]), None)
    if chosen is None:
        chosen = max(pairs, key=lambda row: (row["delta_f_relative"], row["delta_abs_p_relative"] or 0.0))
        basis = "no unique field-dominated admitted mode; the worst matched pair is reported"
    else:
        basis = "the single field-dominated admitted in-window mode of the reference run"

    out.update(
        {
            "available": True,
            "criterion_subject": {"basis": basis, "a_mode": chosen["a_mode"], "b_mode": chosen["b_mode"]},
            "pairs": pairs,
            "delta_f_relative": chosen["delta_f_relative"],
            "delta_p_relative": chosen["delta_abs_p_relative"],
            "modes_in_window": {
                a["spec"]["name"]: len(a.get("modes_in_window", [])),
                b["spec"]["name"]: len(b.get("modes_in_window", [])),
            },
        }
    )
    return out


def halo_verdict(p1_p3: dict[str, Any]) -> dict[str, Any]:
    """Apply the FROZEN criteria. They are not recomputed or relaxed here."""
    out: dict[str, Any] = {"criteria": dict(HALO_CRITERIA), "frozen_in": "execution-proposal.md §4.2"}
    if not p1_p3.get("available"):
        out.update({"verdict": "NOT-DECIDED", "reason": p1_p3.get("reason", "comparison unavailable")})
        return out
    dp, df = p1_p3["delta_p_relative"], p1_p3["delta_f_relative"]
    if dp is None or df is None:
        out.update({"verdict": "NOT-DECIDED", "reason": "a change could not be formed"})
        return out
    p_ok = dp <= HALO_CRITERIA["max_relative_participation_change"]
    f_ok = df <= HALO_CRITERIA["max_relative_frequency_change"]
    out.update({
        "delta_p_relative": dp, "delta_f_relative": df,
        "participation_check": "PASS" if p_ok else "FAIL",
        "frequency_check": "PASS" if f_ok else "FAIL",
    })
    if p_ok and f_ok:
        out.update({
            "verdict": "ADMISSIBLE",
            "systematic_floor_contribution_relative": dp,
            "propagation": (
                "the measured delta_p is carried forward as a systematic contribution to Route A's "
                "resolution floor for g, combined with the mesh-ladder term by taking the maximum"
            ),
        })
    elif not f_ok:
        out.update({
            "verdict": "NOT-A-HALO-VERDICT",
            "reason": (
                "the frequency check failed, which indicates the level-1 mesh is too coarse for "
                "this geometry or the model is wrong, not that the halo is bad; the halo question "
                "is not answerable from this pilot"
            ),
        })
    else:
        out.update({
            "verdict": "REJECTED",
            "reason": (
                "the halo-induced participation change exceeds the frozen 1e-2; the 0.08 mm halo "
                "is not admissible and is not rescued by loosening the criterion"
            ),
        })
    return out


def order_verdict(entries: dict[str, dict[str, Any]], p1_p2: dict[str, Any]) -> dict[str, Any]:
    """Apply the predeclared element-order rule (execution-proposal.md §4.3)."""
    p1, p2 = entries.get("P1", {}), entries.get("P2", {})
    out: dict[str, Any] = {"rule": "execution-proposal.md §4.3"}
    p1_ok = p1.get("status") == "COMPLETED"
    p2_ok = p2.get("status") == "COMPLETED"
    if p1_ok:
        out.update({
            "selected_order": 2,
            "reason": "P1 completed inside its 45 minute cap, so order 2 is selected",
            "wall_clock_s": p1.get("run", {}).get("wall_clock_s"),
        })
        if p1_p2.get("available"):
            out["order_sensitivity_delta_p_relative"] = p1_p2["delta_p_relative"]
            out["order_sensitivity_delta_f_relative"] = p1_p2["delta_f_relative"]
            out["note"] = "the order-1 difference is reported as the measured cost of the cheaper discretisation"
    elif p2_ok:
        out.update({
            "selected_order": 1,
            "reason": (
                "P1 did not complete, so order 1 is the only option; it is usable only if its own "
                "participation converges on the ladder well enough to give a useful floor on g, "
                "which this pilot does not measure"
            ),
        })
    else:
        out.update({
            "selected_order": None,
            "reason": "neither P1 nor P2 completed; the extraction is not executable within the current allowance",
        })
    return out


def next_stage(halo: dict[str, Any], order: dict[str, Any], entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """READY / BLOCKED / another bounded numerical check — decided by the rules above."""
    statuses = {name: e.get("status") for name, e in entries.items()}
    if order.get("selected_order") is None:
        return {"disposition": "BLOCKED",
                "reason": "no solve completed, so no element order is justified", "statuses": statuses}
    if halo.get("verdict") == "REJECTED":
        return {"disposition": "BLOCKED",
                "reason": ("the 0.08 mm halo is not admissible under the frozen criterion, and the wider "
                           "halo does not fit the DOF budget at order 2 at any ladder level; the choice "
                           "returns to the review"),
                "statuses": statuses}
    if halo.get("verdict") in {"NOT-DECIDED", "NOT-A-HALO-VERDICT"}:
        return {"disposition": "REQUIRES-ANOTHER-BOUNDED-NUMERICAL-CHECK",
                "reason": halo.get("reason", "the halo criterion could not be applied"),
                "statuses": statuses}
    return {
        "disposition": "READY-FOR-THE-LADDER",
        "reason": (
            "the halo is admissible under the frozen criterion and an element order is justified; "
            "the next stage is the Route A mesh ladder, which is a separate approval and is not "
            "started here"
        ),
        "statuses": statuses,
        "carried_forward": {
            "systematic_floor_contribution_relative": halo.get("systematic_floor_contribution_relative"),
            "selected_order": order.get("selected_order"),
        },
    }


# --- record -------------------------------------------------------------------


def render_report(summary: dict[str, Any]) -> str:
    def cell(value: Any, spec: str = "") -> str:
        if value is None:
            return "-"
        return format(value, spec) if spec else str(value)

    L = [
        "# Coupled chip-cell numerical-method pilot",
        "",
        f"Record `{summary['batch_id']}`. {summary['statement']}",
        "",
        "## 1. Did each solve complete?",
        "",
        "| run | order | halo (mm) | DOF | status | Palace s | modes in window | max backward error |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name in ("P1", "P2", "P3"):
        e = summary["runs"].get(name, {})
        spec = e.get("spec", {})
        wall = e.get("run", {}).get("wall_clock_s")
        modes = e.get("modes_in_window")
        L.append(
            f"| {name} | {cell(spec.get('finite_element_order'))} | {cell(spec.get('halo_mm'))} | "
            f"{cell(e.get('dof_for_this_order'))} | {cell(e.get('status'))} | "
            f"{cell(wall, '.1f')} | {cell(len(modes) if modes is not None else None)} | "
            f"{cell(e.get('max_backward_error'), '.2e')} |"
        )
        if e.get("failure"):
            L.append(f"| | | | | {e['failure'][:110]} | | | |")
    for label, key in (("2. P1 vs P2: element-order sensitivity", "p1_vs_p2"),
                       ("3. P1 vs P3: halo sensitivity", "p1_vs_p3")):
        c = summary[key]
        L += ["", f"## {label}", ""]
        if not c.get("available"):
            L.append(f"Not available: {c.get('reason')}")
            continue
        L += [
            f"Admitted in the declared window: {json.dumps(c['admitted_in_window'])}. "
            f"Matching: {c['match']['status']}.",
            "",
            "| pair | f_a (GHz) | f_b (GHz) | Δf | Δ\\|p\\| | criterion subject |",
            "|---|---|---|---|---|---|",
        ]
        for row in c["pairs"]:
            L.append(
                f"| m{row['a_mode']}↔m{row['b_mode']} | {row['a_frequency_GHz']:.6f} "
                f"| {row['b_frequency_GHz']:.6f} | {row['delta_f_relative']:.3e} "
                f"| {cell(row['delta_abs_p_relative'], '.3e')} "
                f"| {'yes' if row['is_criterion_subject'] else ''} |"
            )
        L += [
            "",
            f"Headline pair: {c['criterion_subject']['basis']}.",
            f"- relative frequency change: {c['delta_f_relative']:.3e}",
            f"- relative participation change (magnitudes): {c['delta_p_relative']:.3e}",
        ]
    h = summary["halo_verdict"]
    L += ["", "## 4. Is the 0.08 mm halo admissible under the frozen criteria?", "",
          f"Criteria, frozen in {h['frozen_in']} before this ran: "
          f"Δp ≤ {h['criteria']['max_relative_participation_change']:.0e}, "
          f"Δf ≤ {h['criteria']['max_relative_frequency_change']:.0e}.", "",
          f"**{h['verdict']}**"]
    if "participation_check" in h:
        L.append(f"- participation: {h['participation_check']} (Δp = {h['delta_p_relative']:.3e})")
        L.append(f"- frequency: {h['frequency_check']} (Δf = {h['delta_f_relative']:.3e})")
    if "propagation" in h:
        L.append(f"- {h['propagation']}")
    if "reason" in h:
        L.append(f"- {h['reason']}")
    o = summary["order_verdict"]
    L += ["", "## 5. Which element order is justified for the next ladder?", "",
          f"**order {o.get('selected_order')}** — {o['reason']}"]
    if "order_sensitivity_delta_p_relative" in o:
        L.append(f"- order sensitivity: Δp = {o['order_sensitivity_delta_p_relative']:.3e}, "
                 f"Δf = {o['order_sensitivity_delta_f_relative']:.3e}")
    n = summary["next_stage"]
    L += ["", "## 6. Next extraction stage", "", f"**{n['disposition']}** — {n['reason']}"]
    L += ["", "## Statement", "", summary["statement"], ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--declaration", default=str(REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json"))
    parser.add_argument("--results-root", default=str(REPO_ROOT / "results"))
    parser.add_argument("--record-name", default=None)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--np", type=int, default=1)
    parser.add_argument("--prepare-only", action="store_true",
                        help="mesh and write the config, do not launch Palace")
    parser.add_argument("--record-pointer", default=None)
    args = parser.parse_args(argv)

    # The gate comes first: before the record directory exists, before the
    # declaration is parsed for meshing, and before any runtime is named to a
    # subprocess. A refused invocation must leave nothing behind, so there is no
    # empty record to mistake for an attempt.
    authority: ExecutionAuthority | None = None
    if not args.prepare_only:
        try:
            authority = require_execution_authority(
                runtime=args.runtime, image=args.image, mpi_processes=args.np,
                declaration_path=Path(args.declaration),
            )
        except PilotRefusal as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2

    started = datetime.now(timezone.utc)
    batch = args.record_name or f"COUPLED-PILOT-{started.strftime('%Y%m%dT%H%M%SZ')}"
    root = Path(args.results_root) / batch
    root.mkdir(parents=True, exist_ok=False)
    declaration = json.loads(Path(args.declaration).read_text())

    summary: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "batch_id": batch,
        "started_utc": started.isoformat(),
        "statement": STATEMENT,
        "performed_coupling_extraction": False,
        "performed_route_b": False,
        "declaration": {
            "path": str(args.declaration),
            "sha256": manifest.file_digest(Path(args.declaration)),
            "id": declaration.get("declaration_id"),
        },
        "approved_pilot": [r.as_dict() for r in RUNS],
        "halo_criteria": dict(HALO_CRITERIA),
        "solve_timeout_s": SOLVE_TIMEOUT_S,
        "dof_budget": DOF_BUDGET,
        "solver_rules": dict(COUPLED_SOLVER_RULES),
        "environment": {
            "os": f"{platform.system()} {platform.release()}",
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "mpi_processes": args.np,
            "docker_available": shutil.which(args.runtime) is not None,
        },
        "image": (_image_identity(authority, args.runtime, args.image)
                  if not args.prepare_only else {"image": args.image}),
        "execution_authority": (authority.as_dict() if authority is not None
                                else {"granted": False, "reason": "--prepare-only launches nothing"}),
        "runs": {},
    }

    for spec in RUNS:
        print(f"== {spec.name}: order {spec.finite_element_order}, halo {spec.halo_mm} mm", flush=True)
        entry = execute_run(
            spec, declaration, root / spec.name,
            runtime=args.runtime, image=args.image, np_=args.np, prepare_only=args.prepare_only,
            authority=authority,
        )
        summary["runs"][spec.name] = entry
        wall = entry.get("run", {}).get("wall_clock_s")
        print(f"   {entry['status']}"
              + (f", {wall:.1f} s" if isinstance(wall, (int, float)) else "")
              + f", DOF {entry.get('dof_for_this_order')}"
              + (f", {len(entry.get('modes_in_window', []))} modes in window" if entry.get("modes") else ""),
              flush=True)

    summary["p1_vs_p2"] = compare(summary["runs"].get("P1", {}), summary["runs"].get("P2", {}),
                                  "P1 vs P2: element order at a fixed 0.08 mm halo")
    summary["p1_vs_p3"] = compare(summary["runs"].get("P1", {}), summary["runs"].get("P3", {}),
                                  "P1 vs P3: halo at a fixed order 2")
    summary["halo_verdict"] = halo_verdict(summary["p1_vs_p3"])
    summary["order_verdict"] = order_verdict(summary["runs"], summary["p1_vs_p2"])
    summary["next_stage"] = next_stage(summary["halo_verdict"], summary["order_verdict"], summary["runs"])
    summary["ended_utc"] = datetime.now(timezone.utc).isoformat()

    (root / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    (root / "report.md").write_text(render_report(summary))
    manifest.write(root)  # always last
    if args.record_pointer:
        Path(args.record_pointer).write_text(str(root) + "\n")
    print(f"record : {root}")
    print(f"halo   : {summary['halo_verdict']['verdict']}")
    print(f"order  : {summary['order_verdict'].get('selected_order')}")
    print(f"next   : {summary['next_stage']['disposition']}")
    completed = sum(1 for e in summary["runs"].values() if e["status"] == "COMPLETED")
    if args.prepare_only:
        return 0
    return 0 if completed == len(RUNS) else 5


if __name__ == "__main__":
    sys.exit(main())
