"""Phase C, increment 3: the coupled pilot's launch authority, made in-module.

Increment 1 found and pinned the gap: `scripts/palace_coupled_pilot.py` could form a
`docker run` argv and contained no approval read and no refusal path. Its three runs were
frozen CONSTANTS in the source and its only launch authority was the workflow trigger, so
anyone running the script directly launched Palace. That is materially weaker than
`scripts/palace_order1_ladder.py`, which reads its approval and raises.

THE TRAP THIS INCREMENT HAD TO AVOID. `.github/pilot-approval.json` already exists. It is
the historical record of the 16 September 2026 approval, and of attempt 1, which ran. The
easy implementation - "refuse unless the approval file is present" - would have been
enforcement in appearance only: the file has been on disk since September, so that gate
would pass today, tomorrow and for every future invocation. Presence is not permission.

So the driver requires a SEPARATE `execution_authority` block that the committed file does
not carry, binding one execution to the reviewed driver bytes, the reviewed declaration,
the frozen P1/P2/P3 set, the 250 000 DOF and 2 700 s caps, the runtime/image/rank
mechanism, and one narrowly bounded attempt inside a short UTC window. The approval file is
NOT modified by this increment, so the pilot is inert by default and this module proves it.

HOW THE NEGATIVE CONTROLS ARE MADE HONEST. Every refusal test runs with the pilot module's
`subprocess` replaced by an object whose every entry point raises, and - this is the part
that makes the interception load-bearing - every altered-approval case is ALSO driven
through `main()`, which continues into `docker image inspect` and the solve the instant the
gate returns. Asserting "nothing was executed" about `require_execution_authority` alone
would be unfalsifiable, since that function cannot reach a runtime whatever it decides. So
the claim proved here is the whole one: it refused, no record directory was created, and
nothing ran.

That interception is broad rather than merely convenient because
`test_the_pilot_executes_nothing_at_import_time` and
`test_every_launch_site_in_the_pilot_is_gated_and_the_set_is_pinned` pin, by AST, that no
function OTHER than the three gated ones reaches an enumerated exec primitive, and that
none runs at import - resolving import aliases, so `os.system`, `sp.run`, a bare `run` and
a rebound `_R` are all covered. Stated exactly: that pins the primitives it enumerates, not
the absence of every conceivable way to start a process (`ctypes`, `pty`,
`asyncio.create_subprocess_exec` are not enumerated).

This module deliberately calls no subprocess of its own.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PILOT_SOURCE = REPO_ROOT / "scripts" / "palace_coupled_pilot.py"
COMMITTED_APPROVAL = REPO_ROOT / ".github" / "pilot-approval.json"
DECLARATION = REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json"

#: A fixed instant inside every synthetic window below. Pinned rather than "now", so the
#: suite does not start failing on a date.
NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)

#: The historical approval record, pinned by content. This increment must not move it, and
#: a future one that does has to change this line deliberately.
#: Granting a real execution means editing .github/pilot-approval.json, which four pins in
#: this repository deliberately forbid: this constant, the two assertions below, and
#: `test_the_pilot_gap_is_closed_and_its_approval_is_not_self_authorising` in
#: tests/test_launch_authority.py. That coupling is the POINT and not an oversight -
#: granting authority is meant to be a reviewed change to code and pins, not a quiet data
#: edit that CI never notices. A grant therefore lands as one change that updates all four.
GRANTING_NOTE = (
    "the committed approval now carries an execution_authority: the pilot is no longer "
    "inert. If that is deliberate, this pin, COMMITTED_APPROVAL_SHA256, "
    "test_the_committed_approval_record_is_not_execution_authority and "
    "test_the_pilot_gap_is_closed_and_its_approval_is_not_self_authorising must be updated "
    "in the SAME reviewed change that grants it."
)

COMMITTED_APPROVAL_SHA256 = "1687e8e16fe605db3acb7ae7f461ed3b9dbf35cebcd66d5f33863a3d791b0bdf"


def _load_pilot():
    spec = importlib.util.spec_from_file_location("palace_coupled_pilot_authority", PILOT_SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


#: Loaded at import, not in a fixture, so the parametrised removal test below can be driven
#: from the guard's OWN key set instead of a third hand-maintained copy that could shrink
#: without anything failing.
_PILOT = _load_pilot()


@pytest.fixture(scope="module")
def pilot():
    return _PILOT


class LaunchReached(AssertionError):
    """Raised if a refusal path executed anything at all."""


class _NoSubprocess:
    """Stands in for the `subprocess` module inside the pilot, and never runs anything.

    Substituted for the pilot module's own global rather than patching the real
    `subprocess` module, so nothing outside the module under test is affected.
    """

    TimeoutExpired = subprocess.TimeoutExpired
    CompletedProcess = subprocess.CompletedProcess

    def __init__(self) -> None:
        self.attempts: list[Any] = []

    def _forbidden(self, *args: Any, **kwargs: Any):
        self.attempts.append(args[0] if args else kwargs)
        raise LaunchReached(f"a launch primitive was reached: {args[:1]!r}")

    run = _forbidden
    Popen = _forbidden
    call = _forbidden
    check_call = _forbidden
    check_output = _forbidden


@pytest.fixture
def no_launch(pilot, monkeypatch):
    """Every test in this module runs under this. Nothing here may execute a program."""
    guard = _NoSubprocess()
    monkeypatch.setattr(pilot, "subprocess", guard)
    return guard


# --- building a synthetic approval ---------------------------------------------------


def valid_authority(pilot, *, declaration: Path = DECLARATION) -> dict[str, Any]:
    """An `execution_authority` the guard must accept: correct in every bound field."""
    from orchestrator import manifest

    prior = pilot.prior_executions(json.loads(COMMITTED_APPROVAL.read_text()))
    return {
        "schema": pilot.AUTHORITY_SCHEMA,
        "authorises": "one execution",
        "attempt": len(prior) + 1,
        "supersedes": prior,
        "approved_by": "the repository owner, in the phase C increment 3 thread",
        "not_before_utc": "2026-09-22T00:00:00Z",
        "expires_utc": "2026-09-23T00:00:00Z",
        "driver_sha256": manifest.file_digest(pilot.DRIVER_PATH),
        "declaration_sha256": manifest.file_digest(declaration),
        "runs": [
            {"name": "P1", "finite_element_order": 2, "halo_mm": 0.08, "level": 1},
            {"name": "P2", "finite_element_order": 1, "halo_mm": 0.08, "level": 1},
            {"name": "P3", "finite_element_order": 2, "halo_mm": 0.12, "level": 1},
        ],
        "dof_budget": 250_000,
        "per_solve_wall_clock_cap_s": 2700,
        "execution_mechanism": {
            "runtime": "docker", "image": pilot.DEFAULT_IMAGE, "mpi_processes": 1,
        },
        "out_of_scope": list(pilot.OUT_OF_SCOPE),
    }


def approval_body(pilot, *, live: bool = False) -> dict[str, Any]:
    """The committed historical record, plus a valid authority block.

    Built FROM the real file so the historical parts - `reruns`, which records attempt 1
    as executed, and `explicitly_out_of_scope` - are the real ones and the spent-attempt
    and scope checks are exercised against genuine data.

    `live=True` moves the window around the real clock. `main()` takes no injectable
    instant - production must read the real one - so the one end-to-end test has to hand
    it an authority that is genuinely current, exactly as a real approval would be. The
    window stays inside the narrowness ceiling, so it is not a relaxed authority.
    """
    body = json.loads(COMMITTED_APPROVAL.read_text())
    body["execution_authority"] = valid_authority(pilot)
    if live:
        moment = datetime.now(timezone.utc)
        body["execution_authority"]["not_before_utc"] = (
            (moment - timedelta(hours=1)).isoformat().replace("+00:00", "Z"))
        body["execution_authority"]["expires_utc"] = (
            (moment + timedelta(hours=1)).isoformat().replace("+00:00", "Z"))
    return body


def write_approval(tmp_path: Path, body: Any) -> Path:
    path = tmp_path / "pilot-approval.json"
    path.write_text(json.dumps(body, indent=1) + "\n")
    return path


def grant(pilot, path: Path, *, runtime: str = "docker", image: str | None = None,
          mpi_processes: int = 1, now: datetime = NOW):
    return pilot.require_execution_authority(
        runtime=runtime, image=pilot.DEFAULT_IMAGE if image is None else image,
        mpi_processes=mpi_processes, declaration_path=DECLARATION, path=path, now=now)


# --- A. the repository is inert, and stays that way ----------------------------------


def test_the_committed_approval_record_is_not_execution_authority(pilot, no_launch):
    """The headline property. The approval file exists and has since September; on its own
    it authorises nothing, and the refusal says why rather than reporting a missing file."""
    with pytest.raises(pilot.PilotRefusal) as exc:
        grant(pilot, COMMITTED_APPROVAL)
    message = str(exc.value)
    assert "no execution_authority block" in message
    assert "presence is not permission" in message
    assert "attempt 1" in message
    assert no_launch.attempts == []


def test_this_increment_did_not_add_authority_to_the_approval_record(no_launch):
    """The approval file must remain untouched, so landing the code cannot start a pilot."""
    body = json.loads(COMMITTED_APPROVAL.read_text())
    assert "execution_authority" not in body, GRANTING_NOTE
    assert [r.get("attempt") for r in body.get("reruns", [])] == [1]


def test_main_refuses_without_authority_and_leaves_no_record(pilot, no_launch, tmp_path,
                                                             capsys):
    """A refused invocation creates nothing: no empty record directory to mistake for an
    attempt, and no runtime invoked on the way to finding out."""
    results = tmp_path / "results"
    results.mkdir()
    assert pilot.main(["--results-root", str(results), "--record-name", "REFUSED-X"]) == 2
    assert list(results.iterdir()) == []
    assert "REFUSED:" in capsys.readouterr().err
    assert no_launch.attempts == []


# --- B. a synthetic valid approval gets through, with execution intercepted ----------


def test_a_synthetic_valid_authority_passes_the_guard(pilot, no_launch, tmp_path):
    from orchestrator import manifest

    path = write_approval(tmp_path, approval_body(pilot))
    authority = grant(pilot, path)
    assert isinstance(authority, pilot.ExecutionAuthority)
    assert authority.attempt == 3, "two executions are already accounted for"
    assert authority.runtime == "docker"
    assert authority.image == pilot.DEFAULT_IMAGE
    assert authority.mpi_processes == 1
    assert authority.driver_sha256 == manifest.file_digest(pilot.DRIVER_PATH)
    assert authority.declaration_sha256 == manifest.file_digest(DECLARATION)
    assert authority.approval_sha256 == manifest.file_digest(path)
    assert authority.granted_utc == NOW.isoformat()
    assert no_launch.attempts == []


def test_with_authority_the_launch_primitive_is_reached_and_forms_the_approved_argv(
        pilot, monkeypatch, tmp_path):
    """The positive path, intercepted at the subprocess boundary: no Docker, no Palace.

    What is asserted is that the guard LET IT THROUGH and that the argv it then formed is
    the approved one - the container isolated with `--network none`, mapped to the calling
    user, the approved image, one rank."""
    path = write_approval(tmp_path, approval_body(pilot))
    authority = grant(pilot, path)

    seen: list[list[str]] = []

    class Intercept(_NoSubprocess):
        def run(self, command, **kwargs):  # noqa: ARG002
            seen.append(list(command))
            if command[1:2] == ["info"]:          # the rootless probe
                return subprocess.CompletedProcess(command, 0, "{}", "")
            return subprocess.CompletedProcess(command, 0, "palace stdout", "")

    monkeypatch.setattr(pilot, "subprocess", Intercept())
    work = tmp_path / "solver"
    work.mkdir()
    info = pilot._run_palace(authority, "docker", pilot.DEFAULT_IMAGE, work, "unit-test", 1)

    assert info["returncode"] == 0 and info["timed_out"] is False
    assert info["timeout_s"] == 2700
    argv = seen[-1]
    assert argv[:2] == ["docker", "run"]
    assert "--network" in argv and argv[argv.index("--network") + 1] == "none"
    assert argv[-3:] == ["-np", "1", "config.json"]
    assert pilot.DEFAULT_IMAGE in argv
    assert (work / "palace_log.txt").read_text() == "palace stdout"


def test_with_authority_image_inspection_is_reached_and_recorded(pilot, monkeypatch,
                                                                 tmp_path):
    path = write_approval(tmp_path, approval_body(pilot))
    authority = grant(pilot, path)

    class Intercept(_NoSubprocess):
        def run(self, command, **kwargs):  # noqa: ARG002
            fmt = command[-1]
            body = {"{{.Id}}": "sha256:feedface", "{{json .RepoDigests}}": '["x@sha256:ab"]',
                    "{{json .Config.Labels}}": '{"org.qmhp":"pilot"}'}[fmt]
            return subprocess.CompletedProcess(command, 0, body + "\n", "")

    monkeypatch.setattr(pilot, "subprocess", Intercept())
    identity = pilot._image_identity(authority, "docker", pilot.DEFAULT_IMAGE)
    assert identity["image_id"] == "sha256:feedface"
    assert identity["repo_digest"] == "x@sha256:ab"
    assert identity["labels"] == {"org.qmhp": "pilot"}
    assert "error" not in identity


def test_main_carries_one_validated_authority_into_every_run(pilot, monkeypatch, tmp_path):
    """End to end through `main`, with meshing and the solve stubbed out. Each of the three
    runs must receive the SAME validated authority object - not a fresh dict, and not
    None."""
    path = write_approval(tmp_path, approval_body(pilot, live=True))
    monkeypatch.setattr(pilot, "PILOT_APPROVAL", path)
    monkeypatch.setattr(pilot, "subprocess", _NoSubprocess())
    monkeypatch.setattr(pilot, "_image_identity",
                        lambda authority, runtime, image: {"image": image, "stubbed": True})

    received: list[Any] = []

    def stub_execute(spec, declaration, run_dir, **kwargs):  # noqa: ARG001
        received.append(kwargs["authority"])
        return {"spec": spec.as_dict(), "status": "COMPLETED"}

    monkeypatch.setattr(pilot, "execute_run", stub_execute)
    results = tmp_path / "results"
    rc = pilot.main(["--results-root", str(results), "--record-name", "SYNTHETIC-OK"])

    assert rc == 0
    assert len(received) == 3
    assert all(isinstance(a, pilot.ExecutionAuthority) for a in received)
    assert len({id(a) for a in received}) == 1, "each run must share the one granted authority"
    summary = json.loads((results / "SYNTHETIC-OK" / "summary.json").read_text())
    assert summary["execution_authority"]["attempt"] == 3
    assert summary["execution_authority"]["approval_sha256"]
    assert summary["execution_authority"]["runtime"] == "docker"


# --- C. prepare-only stays usable ----------------------------------------------------


def test_prepare_only_never_consults_the_gate(pilot, monkeypatch, tmp_path):
    """`--prepare-only` cannot launch Palace, so it must not be gated. Proven by making the
    gate itself explode: if prepare-only touched it, this test would fail."""
    def exploding(**kwargs):  # noqa: ARG001
        raise AssertionError("--prepare-only consulted the execution-authority gate")

    monkeypatch.setattr(pilot, "require_execution_authority", exploding)
    monkeypatch.setattr(pilot, "subprocess", _NoSubprocess())
    monkeypatch.setattr(pilot, "execute_run",
                        lambda spec, declaration, run_dir, **kw: {"spec": spec.as_dict(),
                                                                  "status": "PREPARED"})
    results = tmp_path / "results"
    rc = pilot.main(["--prepare-only", "--results-root", str(results),
                     "--record-name", "PREPARED-X"])
    assert rc == 0
    summary = json.loads((results / "PREPARED-X" / "summary.json").read_text())
    assert summary["execution_authority"] == {
        "granted": False, "reason": "--prepare-only launches nothing"}
    assert summary["image"] == {"image": pilot.DEFAULT_IMAGE}, \
        "prepare-only must not inspect the image"


def test_execute_run_prepare_only_needs_no_authority(pilot, monkeypatch, no_launch,
                                                     tmp_path):
    """The real prepare path, with only the mesher stubbed, reaches PREPARED with
    `authority=None` and shells out to nothing."""
    class Cell:
        def clearance_report(self):
            return ["stub clearance"]

    class Report:
        def as_dict(self):
            return {"mesh_file": str(tmp_path / "mesh.msh"), "measured": {"dof_order2": 1234}}

    monkeypatch.setattr(pilot, "chip_cell_from_declaration", lambda declaration: Cell())
    monkeypatch.setattr(pilot, "dry_run",
                        lambda cell, level, out, **kw: Report())  # noqa: ARG005
    declaration = json.loads(DECLARATION.read_text())
    entry = pilot.execute_run(
        pilot.RUNS[0], declaration, tmp_path / "P1",
        runtime="docker", image=pilot.DEFAULT_IMAGE, np_=1, prepare_only=True, authority=None)
    assert entry["status"] == "PREPARED"
    assert (tmp_path / "P1" / "solver" / "config.json").is_file()
    assert no_launch.attempts == []


def test_a_real_run_without_authority_refuses_instead_of_recording_an_outcome(
        pilot, no_launch, tmp_path):
    """`execute_run` records every failure as evidence. A refusal is NOT a failure of the
    pilot - it is the pilot not happening - so it must propagate rather than be filed as
    an ERROR entry that reads like something that ran."""
    declaration = json.loads(DECLARATION.read_text())
    with pytest.raises(pilot.PilotRefusal, match="requires a validated execution authority"):
        pilot.execute_run(pilot.RUNS[0], declaration, tmp_path / "P1",
                          runtime="docker", image=pilot.DEFAULT_IMAGE, np_=1,
                          prepare_only=False, authority=None)
    assert not (tmp_path / "P1").exists()
    assert no_launch.attempts == []


# --- D. negative controls: every refusal, and nothing executed -----------------------


def _drop_block(body):
    del body["execution_authority"]


def _mutate(**changes):
    def apply(body):
        body["execution_authority"].update(changes)
    return apply


def _mutate_mechanism(**changes):
    def apply(body):
        body["execution_authority"]["execution_mechanism"].update(changes)
    return apply


REFUSALS: dict[str, tuple[Any, str]] = {
    # the block itself
    "no authority block at all": (_drop_block, "no execution_authority block"),
    "the block is not an object": (_mutate(**{}), ""),   # replaced below
    "an unknown key": (lambda b: b["execution_authority"].update({"also": "run N4"}),
                       "unknown execution_authority key"),
    "the wrong schema": (_mutate(schema="qmhp-cem.something-else/9"), "schema is"),
    # scope of the permission
    "an open-ended authorisation": (_mutate(authorises="any number of executions"),
                                    "one execution' only"),
    "no named approver": (_mutate(approved_by="   "), "must name who approved"),
    # the attempt, and the history it must acknowledge
    "the already-spent attempt 1": (_mutate(attempt=1), "is not new"),
    "the already-spent attempt 2, which the LEDGER ALONE would have admitted": (
        _mutate(attempt=2), "is not new"),
    "a supersedes list that omits the committed record": (
        lambda b: b["execution_authority"].__setitem__("supersedes", ["attempt 1"]),
        "must name every execution it follows"),
    "a supersedes list that omits the ledger attempt": (
        lambda b: b["execution_authority"].__setitem__(
            "supersedes", ["record COUPLED-PILOT-20260916T035733Z"]),
        "must name every execution it follows"),
    "an empty supersedes list": (
        lambda b: b["execution_authority"].__setitem__("supersedes", []),
        "must name every execution it follows"),
    "a supersedes list in the wrong order": (
        lambda b: b["execution_authority"]["supersedes"].reverse(),
        "must name every execution it follows"),
    "attempt zero": (_mutate(attempt=0), "positive integer"),
    "attempt as a string": (_mutate(attempt="2"), "positive integer"),
    "attempt as a boolean": (_mutate(attempt=True), "positive integer"),
    # the window
    "a window that has expired": (_mutate(not_before_utc="2026-09-16T00:00:00Z",
                                          expires_utc="2026-09-17T00:00:00Z"), "expired"),
    "a window that is not yet live": (_mutate(not_before_utc="2026-10-01T00:00:00Z",
                                              expires_utc="2026-10-02T00:00:00Z"),
                                      "not yet live"),
    "a window running backwards": (_mutate(not_before_utc="2026-09-23T00:00:00Z",
                                           expires_utc="2026-09-22T00:00:00Z"),
                                   "is not after"),
    "a standing, year-long window": (_mutate(not_before_utc="2026-01-01T00:00:00Z",
                                             expires_utc="2026-12-31T00:00:00Z"),
                                     "narrowly defined attempt"),
    "a timestamp with no offset": (_mutate(not_before_utc="2026-09-22T00:00:00"),
                                   "must carry a UTC offset"),
    "a timestamp that is not one": (_mutate(expires_utc="whenever"), "is not a timestamp"),
    # the reviewed code and configuration
    "a driver digest for other code": (_mutate(driver_sha256="0" * 64), "driver_sha256"),
    "a declaration digest for another file": (_mutate(declaration_sha256="0" * 64),
                                              "declaration_sha256"),
    # the frozen run set
    "a fourth run added": (
        lambda b: b["execution_authority"]["runs"].append(
            {"name": "P4", "finite_element_order": 2, "halo_mm": 0.20, "level": 1}),
        "not the frozen pilot"),
    "a run removed": (lambda b: b["execution_authority"]["runs"].pop(), "not the frozen pilot"),
    "an element order changed": (
        lambda b: b["execution_authority"]["runs"][1].__setitem__("finite_element_order", 2),
        "not the frozen pilot"),
    "a halo widened": (
        lambda b: b["execution_authority"]["runs"][2].__setitem__("halo_mm", 0.15),
        "not the frozen pilot"),
    "a mesh level raised": (
        lambda b: b["execution_authority"]["runs"][0].__setitem__("level", 2),
        "not the frozen pilot"),
    # the caps
    "a raised DOF budget": (_mutate(dof_budget=500_000), "dof_budget"),
    "a DOF budget raised by one": (_mutate(dof_budget=250_001), "dof_budget"),
    "a raised wall-clock cap": (_mutate(per_solve_wall_clock_cap_s=5400),
                                "per_solve_wall_clock_cap_s"),
    # the execution mechanism
    "another container runtime": (_mutate_mechanism(runtime="podman"),
                                  "does not cover this execution mechanism"),
    "another image": (_mutate_mechanism(image="palace:latest"),
                      "does not cover this execution mechanism"),
    "more MPI ranks": (_mutate_mechanism(mpi_processes=8),
                       "does not cover this execution mechanism"),
    "an unknown mechanism key": (_mutate_mechanism(privileged=True),
                                 "unknown execution_mechanism key"),
    "a mechanism that is not an object": (_mutate(execution_mechanism="docker"),
                                          "must be a JSON object"),
    # type coercion: JSON is hand-written, and Python's == would accept all of these
    "a DOF budget written as a float": (_mutate(dof_budget=250_000.0), "dof_budget"),
    "a wall-clock cap written as a float": (_mutate(per_solve_wall_clock_cap_s=2700.0),
                                            "per_solve_wall_clock_cap_s"),
    "an element order written as a boolean": (
        lambda b: b["execution_authority"]["runs"][1].__setitem__("finite_element_order", True),
        "not the frozen pilot"),
    "a mesh level written as a float": (
        lambda b: b["execution_authority"]["runs"][0].__setitem__("level", 1.0),
        "not the frozen pilot"),
    "a rank count written as a boolean": (_mutate_mechanism(mpi_processes=True),
                                          "does not cover this execution mechanism"),
    "the scope reordered": (
        lambda b: b["execution_authority"]["out_of_scope"].reverse(),
        "does not restate the approved scope"),
    "a run key dropped": (
        lambda b: b["execution_authority"]["runs"][0].pop("level"), "not the frozen pilot"),
    "an extra run key added": (
        lambda b: b["execution_authority"]["runs"][0].__setitem__("purpose", "whatever"),
        "not the frozen pilot"),
    # the scope
    "the Route A inversion dropped from the authority's scope": (
        lambda b: b["execution_authority"]["out_of_scope"].remove("the Route A inversion"),
        "does not restate the approved scope"),
    "the Route A inversion dropped from the record's scope": (
        lambda b: b["explicitly_out_of_scope"].remove("the Route A inversion"),
        "no longer matches the approved scope"),
}
REFUSALS["the block is not an object"] = (
    lambda b: b.__setitem__("execution_authority", "approved"), "must be a JSON object")


def refuse_through_main(pilot, monkeypatch, guard, approval: Path, results: Path) -> None:
    """Drive the mutated approval through `main()`, which is the path that WOULD reach
    `docker image inspect` and the solve.

    This is what makes `guard.attempts == []` mean something. Calling
    `require_execution_authority` alone can never touch a runtime whatever it decides, so
    asserting "nothing was executed" about that call is unfalsifiable. `main()` continues
    into `_image_identity` and `execute_run` the moment the gate returns, so here the
    assertion has something to catch.
    """
    monkeypatch.setattr(pilot, "PILOT_APPROVAL", approval)
    results.mkdir(exist_ok=True)
    assert pilot.main(["--results-root", str(results), "--record-name", "MUST-NOT-EXIST"]) == 2
    assert list(results.iterdir()) == [], "a refused invocation created a record directory"
    assert guard.attempts == [], "a refused invocation executed something"


@pytest.mark.parametrize("label", sorted(REFUSALS))
def test_every_altered_or_stale_authority_refuses_before_launch(pilot, no_launch, monkeypatch,
                                                                tmp_path, label):
    mutate, expected = REFUSALS[label]
    body = approval_body(pilot)
    mutate(body)
    path = write_approval(tmp_path, body)
    with pytest.raises(pilot.PilotRefusal) as exc:
        grant(pilot, path)
    assert expected in str(exc.value), (label, str(exc.value))
    refuse_through_main(pilot, monkeypatch, no_launch, path, tmp_path / "results")


@pytest.mark.parametrize("key", sorted(_PILOT.AUTHORITY_REQUIRED_KEYS))
def test_every_required_field_is_required(pilot, no_launch, monkeypatch, tmp_path, key):
    """Each bound field, removed in turn. A field that could be omitted would be a field
    the approval does not actually have to state."""
    body = approval_body(pilot)
    del body["execution_authority"][key]
    path = write_approval(tmp_path, body)
    with pytest.raises(pilot.PilotRefusal, match=f"missing.*{key}"):
        grant(pilot, path)
    refuse_through_main(pilot, monkeypatch, no_launch, path, tmp_path / "results")


def test_the_required_key_set_is_exactly_what_the_guard_enforces(pilot):
    """The three places that could drift - the guard's set, the helper that builds a valid
    block, and the removal parametrisation - are one place. The parametrisation is driven
    from AUTHORITY_REQUIRED_KEYS directly, so adding a required key without exercising it
    is not possible."""
    assert pilot.AUTHORITY_REQUIRED_KEYS == frozenset(valid_authority(pilot))
    assert pilot.MECHANISM_REQUIRED_KEYS == frozenset(
        valid_authority(pilot)["execution_mechanism"])
    assert len(pilot.AUTHORITY_REQUIRED_KEYS) == 14


def test_a_missing_or_malformed_approval_file_refuses(pilot, no_launch, tmp_path):
    with pytest.raises(pilot.PilotRefusal, match="no approval record at"):
        grant(pilot, tmp_path / "absent.json")
    broken = tmp_path / "broken.json"
    broken.write_text('{"execution_authority": {,}')
    with pytest.raises(pilot.PilotRefusal, match="could not be read as JSON"):
        grant(pilot, broken)
    listy = tmp_path / "listy.json"
    listy.write_text("[]\n")
    with pytest.raises(pilot.PilotRefusal, match="must be a JSON object"):
        grant(pilot, listy)
    # a file that is not UTF-8 at all must refuse, not raise UnicodeDecodeError out of
    # main() as a traceback
    binary = tmp_path / "binary.json"
    binary.write_bytes(b"\xff\xfe{\x00}")
    with pytest.raises(pilot.PilotRefusal, match="could not be read as JSON"):
        grant(pilot, binary)
    assert no_launch.attempts == []


def test_an_unreadable_history_refuses_instead_of_reading_as_an_empty_one(pilot, no_launch,
                                                                          tmp_path):
    """The failure mode this fail-closed rule exists for: a ledger or a record the gate
    cannot parse must not silently lower the floor the next attempt has to clear."""
    for ledger, expected in (
        ({"attempt": "one"}, "cannot read"),
        ("not a list", "not a list"),
        (["bare string"], "cannot read"),
        ({"workflow_run": 1}, "cannot read"),
    ):
        body = approval_body(pilot)
        body["reruns"] = ledger if isinstance(ledger, (str, list)) else [ledger]
        path = write_approval(tmp_path, body)
        with pytest.raises(pilot.PilotRefusal, match=expected):
            grant(pilot, path)

    # and an unreadable committed record is refused rather than skipped
    fake = tmp_path / "results"
    (fake / "COUPLED-PILOT-BROKEN").mkdir(parents=True)
    (fake / "COUPLED-PILOT-BROKEN" / "summary.json").write_text("{not json")
    with pytest.raises(pilot.PilotRefusal, match="cannot be read"):
        pilot.executed_pilots(fake)
    assert no_launch.attempts == []


def test_a_mismatch_between_the_authority_and_this_invocation_refuses(pilot, no_launch,
                                                                      tmp_path):
    """The same valid block, pointed at a different execution. The authority is for this
    run or it is for nothing."""
    path = write_approval(tmp_path, approval_body(pilot))
    for kwargs, expected in (
        ({"runtime": "podman"}, "execution_mechanism.runtime"),
        ({"image": "palace:latest"}, "execution_mechanism.image"),
        ({"mpi_processes": 4}, "execution_mechanism.mpi_processes"),
    ):
        with pytest.raises(pilot.PilotRefusal, match=expected):
            grant(pilot, path, **kwargs)
    assert no_launch.attempts == []


# --- E. the authority object cannot be forged, and the primitives check it -----------


FORGED_FIELDS = {"attempt": 99, "runtime": "docker", "image": "qmhp-cem/palace:0.13.0",
                 "mpi_processes": 1, "approval_sha256": "x", "driver_sha256": "y",
                 "declaration_sha256": "z", "granted_utc": "2026-09-22T12:00:00+00:00"}


def test_an_execution_authority_cannot_be_constructed_directly(pilot):
    with pytest.raises(pilot.PilotRefusal, match="can only be produced by"):
        pilot.ExecutionAuthority(object(), **FORGED_FIELDS)


def test_the_three_ways_of_manufacturing_an_authority_object_are_all_refused(pilot,
                                                                             no_launch,
                                                                             tmp_path):
    """Being an instance is deliberately NOT sufficient, and this is why.

    All three produce a genuine `ExecutionAuthority` without the gate ever running, and the
    increment 3 review found that they defeated the `isinstance` check this gate originally
    used. They are the reason it now demands membership of the set the granting function
    populates. What is preserved here is the REFUSAL: the pre-fix reachability was
    demonstrated in the session that found it and is not committed evidence."""
    # (1) __new__ bypasses __init__ entirely, so the token is never seen
    bypassed = object.__new__(pilot.ExecutionAuthority)
    for key, value in FORGED_FIELDS.items():
        setattr(bypassed, key, value)
    # (2) the module-private token, simply read off the module
    with_token = pilot.ExecutionAuthority(pilot._AUTHORITY_TOKEN, **FORGED_FIELDS)
    for forged in (bypassed, with_token):
        assert isinstance(forged, pilot.ExecutionAuthority), "the point: it IS one"
        for call in (
            lambda f=forged: pilot._image_identity(f, "docker", pilot.DEFAULT_IMAGE),
            lambda f=forged: pilot._user_flag(f, "docker"),
            lambda f=forged: pilot._run_palace(f, "docker", pilot.DEFAULT_IMAGE,
                                               tmp_path, "n", 1),
        ):
            with pytest.raises(pilot.PilotRefusal, match="Being one of these objects"):
                call()
    # (3) a subclass would satisfy isinstance without passing the gate; it cannot exist
    with pytest.raises(pilot.PilotRefusal, match="may not be subclassed"):
        type("Forged", (pilot.ExecutionAuthority,), {})
    assert no_launch.attempts == []


def test_only_a_granted_authority_is_in_the_registry(pilot, no_launch, tmp_path):
    """The positive half: the object the gate returns IS registered, and the registry is
    weak, so it cannot accumulate or be revived by id reuse."""
    path = write_approval(tmp_path, approval_body(pilot))
    authority = grant(pilot, path)
    assert authority in pilot._GRANTED
    assert pilot.ExecutionAuthority(pilot._AUTHORITY_TOKEN, **FORGED_FIELDS) \
        not in pilot._GRANTED
    assert "__weakref__" in pilot.ExecutionAuthority.__slots__
    assert no_launch.attempts == []


@pytest.mark.parametrize("forged", [None, "approved", True, 1, {"runtime": "docker"}, object()])
def test_no_launch_primitive_accepts_anything_but_a_granted_authority(pilot, no_launch,
                                                                      tmp_path, forged):
    for call in (
        lambda: pilot._run_palace(forged, "docker", pilot.DEFAULT_IMAGE, tmp_path, "n", 1),
        lambda: pilot._image_identity(forged, "docker", pilot.DEFAULT_IMAGE),
        lambda: pilot._user_flag(forged, "docker"),
    ):
        with pytest.raises(pilot.PilotRefusal, match="requires a validated execution authority"):
            call()
    assert no_launch.attempts == []


def test_a_granted_authority_cannot_be_carried_to_another_mechanism(pilot, no_launch,
                                                                    tmp_path):
    """Re-checked AT the primitive, not only at the top: an authority for docker and the
    approved image cannot be handed to a call that would launch something else."""
    path = write_approval(tmp_path, approval_body(pilot))
    authority = grant(pilot, path)
    with pytest.raises(pilot.PilotRefusal, match="the authority covers 'docker'"):
        pilot._run_palace(authority, "podman", pilot.DEFAULT_IMAGE, tmp_path, "n", 1)
    with pytest.raises(pilot.PilotRefusal, match="the authority covers"):
        pilot._run_palace(authority, "docker", "palace:latest", tmp_path, "n", 1)
    with pytest.raises(pilot.PilotRefusal, match="MPI process"):
        pilot._run_palace(authority, "docker", pilot.DEFAULT_IMAGE, tmp_path, "n", 8)
    with pytest.raises(pilot.PilotRefusal, match="the authority covers"):
        pilot._image_identity(authority, "podman", pilot.DEFAULT_IMAGE)
    with pytest.raises(pilot.PilotRefusal, match="the authority covers"):
        pilot._user_flag(authority, "podman")
    assert no_launch.attempts == []


# --- F. no ungated launch site can be added to the module ----------------------------

#: Exec primitives, by the module that owns them. Resolved through import aliases below
#: rather than matched as literal dotted strings: `import subprocess as sp; sp.run(...)`
#: and `from subprocess import run; run(...)` are the same launch, and a checker that
#: sees only the literal spelling would rate an ungated one of those as clean.
EXEC_MODULES = {
    "subprocess": frozenset({"run", "Popen", "call", "check_call", "check_output"}),
    "os": frozenset({"system", "popen", "execv", "execvp", "spawnv"}),
}
GATE = "_require_authority"


def _exec_bindings(tree: ast.Module) -> tuple[dict[str, str], set[str]]:
    """({local name: owning module}, {local names that ARE an exec callable}).

    Covers `import subprocess`, `import subprocess as sp`, `from os import system`, and a
    module-level rebinding such as `_R = subprocess.run`.
    """
    modules: dict[str, str] = {}
    direct: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in EXEC_MODULES:
                    modules[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in EXEC_MODULES:
            for alias in node.names:
                if alias.name in EXEC_MODULES[node.module]:
                    direct.add(alias.asname or alias.name)
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Attribute):
            continue
        owner = node.value.value
        if (isinstance(owner, ast.Name) and owner.id in modules
                and node.value.attr in EXEC_MODULES[modules[owner.id]]):
            direct |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return modules, direct


def _is_exec_call(node: ast.Call, modules: dict[str, str], direct: set[str]) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        owner = modules.get(func.value.id)
        return owner is not None and func.attr in EXEC_MODULES[owner]
    return isinstance(func, ast.Name) and func.id in direct


def _is_gate_statement(stmt: ast.stmt) -> bool:
    """The statement IS a call to the gate - not a statement that merely contains one.

    A conditional gate (`if os.environ.get(...): _require_authority(...)`) is skippable at
    runtime, so "the gate appears somewhere in the first statement" would bless a launch
    site that can be bypassed.
    """
    value = stmt.value if isinstance(stmt, (ast.Expr, ast.Assign, ast.AnnAssign)) else None
    return (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
            and value.func.id == GATE)


def launch_sites(source: str) -> dict[str, bool]:
    """{function name: is it gated} for every function that can execute a program.

    "Gated" means the FIRST statement of the body, after any docstring, IS a call to the
    gate. Anything later would leave a window in which the function has already decided
    something on the strength of an authority it has not checked.
    """
    tree = ast.parse(source)
    modules, direct = _exec_bindings(tree)
    out: dict[str, bool] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not any(_is_exec_call(n, modules, direct)
                   for n in ast.walk(node) if isinstance(n, ast.Call)):
            continue
        body = list(node.body)
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body = body[1:]
        out[node.name] = bool(body) and _is_gate_statement(body[0])
    return out


def test_every_launch_site_in_the_pilot_is_gated_and_the_set_is_pinned():
    sites = launch_sites(PILOT_SOURCE.read_text())
    assert sites == {"_image_identity": True, "_user_flag": True, "_run_palace": True}, sites


def test_the_launch_site_checker_rejects_what_it_must(tmp_path):
    """Negative controls for the checker itself. A structural test that cannot fail is
    decoration, so each way of getting it wrong is applied and required to be caught."""
    ungated = "import subprocess\ndef go(rt):\n    subprocess.run([rt, 'run', 'img'])\n"
    assert launch_sites(ungated) == {"go": False}

    gated = ("import subprocess\ndef go(a, rt):\n"
             "    _require_authority(a, 'x')\n    subprocess.run([rt, 'run', 'img'])\n")
    assert launch_sites(gated) == {"go": True}

    late = ("import subprocess\ndef go(a, rt):\n"
            "    out = subprocess.run([rt, 'run', 'img'])\n"
            "    _require_authority(a, 'x')\n    return out\n")
    assert launch_sites(late) == {"go": False}, "a gate after the launch is not a gate"

    after_docstring = ('import subprocess\ndef go(a, rt):\n    """Doc."""\n'
                       "    _require_authority(a, 'x')\n    subprocess.run([rt, 'x'])\n")
    assert launch_sites(after_docstring) == {"go": True}

    other_primitive = "import os\ndef go():\n    os.system('docker run img')\n"
    assert launch_sites(other_primitive) == {"go": False}

    # an ALIASED import is the same launch, and must not read as clean
    aliased = ("import subprocess as sp\ndef go(rt):\n    sp.run([rt, 'run', 'img'])\n")
    assert launch_sites(aliased) == {"go": False}, "an alias is still subprocess"
    from_import = ("from subprocess import run\ndef go(rt):\n    run([rt, 'run', 'img'])\n")
    assert launch_sites(from_import) == {"go": False}
    rebound = ("import subprocess\n_R = subprocess.run\n"
               "def go(rt):\n    _R([rt, 'run', 'img'])\n")
    assert launch_sites(rebound) == {"go": False}

    # a CONDITIONAL gate is skippable, so it is not a gate
    conditional = ("import os, subprocess\ndef go(a, rt):\n"
                   "    if os.environ.get('SKIP') != '1':\n"
                   "        _require_authority(a, 'x')\n"
                   "    subprocess.run([rt, 'run', 'img'])\n")
    assert launch_sites(conditional) == {"go": False}, "a skippable gate is not a gate"
    dead = ("import subprocess\ndef go(a, rt):\n    if False:\n"
            "        _require_authority(a, 'x')\n    subprocess.run([rt, 'x'])\n")
    assert launch_sites(dead) == {"go": False}
    # while an assignment form IS one, because the call still runs unconditionally
    assigned = ("import subprocess\ndef go(a, rt):\n"
                "    auth = _require_authority(a, 'x')\n"
                "    subprocess.run([rt, 'run', 'img'])\n    return auth\n")
    assert launch_sites(assigned) == {"go": True}

    assert launch_sites("def pure():\n    return 1\n") == {}


def test_the_pilot_module_still_names_its_gate_and_raises(pilot):
    """Guards the claim `tests/test_launch_authority.py` now pins about this module."""
    source = PILOT_SOURCE.read_text()
    assert "pilot-approval.json" in source
    assert "raise PilotRefusal" in source
    tree = ast.parse(source)
    assert any(isinstance(n, ast.Raise) for n in ast.walk(tree))
    assert pilot.MAX_AUTHORITY_WINDOW_S == 7 * 24 * 3600
    assert pilot.SOLVE_TIMEOUT_S == 2700 and pilot.DOF_BUDGET == 250_000


def module_level_exec_calls(source: str) -> list[str]:
    """Exec primitives called OUTSIDE any function, which `launch_sites` cannot see.

    A module-level `subprocess.run(...)` would execute on import, before any gate could
    run at all. `launch_sites` walks function bodies, so this is the hole it leaves and
    this closes it.
    """
    tree = ast.parse(source)
    modules, direct = _exec_bindings(tree)
    inside: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for child in ast.walk(node):
                inside.add(id(child))
    return sorted({ast.unparse(n.func) for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and id(n) not in inside
                   and _is_exec_call(n, modules, direct)})


def test_the_pilot_executes_nothing_at_import_time():
    assert module_level_exec_calls(PILOT_SOURCE.read_text()) == []
    # and the checker is not blind: a module-level launch IS caught, aliased or not
    assert module_level_exec_calls(
        "import subprocess\nsubprocess.run(['docker', 'run', 'img'])\n") == ["subprocess.run"]
    assert module_level_exec_calls(
        "import subprocess as sp\nsp.run(['docker', 'run'])\n") == ["sp.run"]
    assert module_level_exec_calls(
        "from os import system\nsystem('docker run img')\n") == ["system"]
    # while the same call inside a function is left to launch_sites
    assert module_level_exec_calls(
        "import subprocess\ndef go():\n    subprocess.run(['docker', 'run'])\n") == []


def test_this_module_did_not_become_launch_capable():
    """It exercises refusal paths; it must not itself be able to start a container."""
    source = Path(__file__).read_text()
    assert launch_sites(source) == {}, "this test module can execute a program"
    assert module_level_exec_calls(source) == []


# --- G. the frozen numbers this increment must not have moved ------------------------


def test_prior_executions_counts_the_evidence_not_just_the_ledger(pilot):
    """The defect this rule exists for, pinned against the real repository.

    The approval record's `reruns` ledger lists ONE attempt. The pilot in fact executed
    twice: that attempt, and the re-run (workflow 35053649226) that produced the committed
    record. A floor taken from the ledger alone would admit `attempt: 2`, a number already
    used. Counting the committed records this driver wrote closes that."""
    approval = json.loads(COMMITTED_APPROVAL.read_text())
    assert [r["attempt"] for r in approval["reruns"]] == [1], "the ledger records one attempt"
    assert pilot.executed_pilots() == ["COUPLED-PILOT-20260916T035733Z"]
    assert pilot.prior_executions(approval) == [
        "attempt 1", "record COUPLED-PILOT-20260916T035733Z"]
    # the corrective-analysis record sits beside it and launched nothing, so it must not
    # be counted as an execution
    assert (REPO_ROOT / "results" / "COUPLED-PILOT-CORR-20260916T064943Z").is_dir()
    assert "COUPLED-PILOT-CORR-20260916T064943Z" not in pilot.executed_pilots()


def test_prior_executions_reads_the_repository_not_the_results_root_argument(pilot, tmp_path):
    """A run told to write elsewhere must not thereby forget its own history."""
    empty = tmp_path / "elsewhere"
    empty.mkdir()
    approval = json.loads(COMMITTED_APPROVAL.read_text())
    assert pilot.executed_pilots(empty) == []
    assert pilot.prior_executions(approval, empty) == ["attempt 1"]
    # but main() never passes --results-root into the gate
    source = PILOT_SOURCE.read_text()
    assert "results_root=" not in source.split("def main(")[1], \
        "main() must not let --results-root shrink the accounted history"


def test_no_scientific_constant_moved(pilot):
    """The gate is authority, not physics. Everything it binds must still be what the
    approval record and the driver already said."""
    approval = json.loads(COMMITTED_APPROVAL.read_text())
    assert approval["constraints"]["per_solve_wall_clock_cap_s"] == pilot.SOLVE_TIMEOUT_S
    assert approval["constraints"]["dof_budget"] == pilot.DOF_BUDGET
    assert approval["frozen_criteria"]["max_relative_participation_change"] == \
        pilot.HALO_CRITERIA["max_relative_participation_change"]
    assert approval["frozen_criteria"]["max_relative_frequency_change"] == \
        pilot.HALO_CRITERIA["max_relative_frequency_change"]
    assert [(r.name, r.finite_element_order, r.halo_mm, r.level) for r in pilot.RUNS] == [
        ("P1", 2, 0.08, 1), ("P2", 1, 0.08, 1), ("P3", 2, 0.12, 1)]
    assert list(pilot.OUT_OF_SCOPE) == approval["explicitly_out_of_scope"]


def test_the_committed_approval_record_is_byte_for_byte_the_historical_one():
    """A real immutability pin on the approval record.

    An earlier draft compared the parsed file to itself, which is true for any content
    whatsoever and therefore proved nothing. This pins the bytes."""
    from orchestrator import manifest
    assert manifest.file_digest(COMMITTED_APPROVAL) == COMMITTED_APPROVAL_SHA256, GRANTING_NOTE
