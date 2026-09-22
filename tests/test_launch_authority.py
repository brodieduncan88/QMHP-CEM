"""Phase C, increment 1: the launch boundary, enforced structurally.

Two of the dangerous boundaries named in the adopted contract - workflow triggering and
solver-launch authority - made hard to cross silently rather than merely forbidden in
prose:

  workflow triggering       the COMPLETE trigger surface of every workflow is pinned
                            EXACTLY, so a new solver workflow, an added branch, a
                            widened path filter, a removed path filter or a
                            pull_request trigger fails here.
  solver-launch authority   the set of modules that can actually EXECUTE a container
                            runtime or an MPI launcher is pinned, so a new one fails
                            here, and each of them is required to name its own gate.

Increment 3 closed the gap this file recorded against scripts/palace_coupled_pilot.py,
which now refuses in-module; tests/test_pilot_execution_authority.py holds that gate's own
positive and negative controls. solvers/palace/adapter.py remains here as the one named
exception, and as an open architecture question rather than an oversight.

Both checks are FUNCTIONS over a directory, so the negative controls run them against
synthetic material and show they reject it. A test that only asserted the present state
would pass just as happily if the check had quietly stopped working - which is exactly
what the contract means by "a test asserting that a check exists is not proof that the
check detects a defect".

This module deliberately calls no subprocess. It must not itself become launch-capable.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import warnings
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


# --- A. workflow triggering ----------------------------------------------------------
#
# tests/test_workflows.py pins the golden workflow's record handling, and checks its
# trigger paths with `>=` - a SUPERSET, which lets the trigger be WIDENED without
# failing. Widening is the direction that matters: adding `scripts/**` to a solver
# workflow's paths turns ordinary commits into solve launches. This pins all five
# workflows exactly, in both directions, and adds the four workflows that file does not
# cover at all.

#: The complete trigger surface, measured 2026-09-21 and pinned.
WORKFLOW_TRIGGERS: dict[str, dict] = {
    "ci.yml": {
        "events": ["pull_request", "push"],
        "push_branches": ["**"],
        "push_paths": None,
    },
    # Build + synthetic qualification of the first-moment image. workflow_dispatch
    # ONLY: no push, no pull_request, no schedule, so nothing an ordinary commit does
    # can start it. It is listed in SOLVER_WORKFLOWS because it CAN execute Palace -
    # on the synthetic fixtures its harness restricts it to, never on a QMHP input.
    "first-moment-image.yml": {
        "events": ["workflow_dispatch"],
        "push_branches": None,
        "push_paths": None,
    },
    "palace-coupled-pilot.yml": {
        "events": ["push", "workflow_dispatch"],
        "push_branches": ["palace/**"],
        "push_paths": [".github/pilot-approval.json"],
    },
    "palace-golden.yml": {
        "events": ["push", "workflow_dispatch"],
        "push_branches": ["main", "palace/**"],
        "push_paths": [".github/workflows/palace-golden.yml", "docker/palace.Dockerfile",
                       "solvers/palace/**", "scripts/palace_golden_run.py"],
    },
    "palace-order1-ladder.yml": {
        "events": ["push", "workflow_dispatch"],
        "push_branches": ["palace/**"],
        "push_paths": [".github/ladder-approval.json"],
    },
    "palace-verify.yml": {
        "events": ["push", "workflow_dispatch"],
        "push_branches": ["main", "palace/**"],
        "push_paths": [".github/workflows/palace-verify.yml",
                       "scripts/palace_verify_campaign.py", "solvers/palace/verification.py"],
    },
}

#: The workflows that can start a Palace solve. ci.yml cannot: it runs the mock solver
#: only (spec section 12.8), which is why it alone may take an unfiltered push.
#: first-moment-image.yml can, so it is listed here even though the only inputs its
#: harness accepts are synthetic fixtures - the classification is by capability.
SOLVER_WORKFLOWS = frozenset({"first-moment-image.yml", "palace-coupled-pilot.yml",
                              "palace-golden.yml", "palace-order1-ladder.yml",
                              "palace-verify.yml"})

#: The two workflows whose trigger IS a human approval record. Nothing else may put an
#: approval file in a trigger path, and these may name nothing else.
APPROVAL_TRIGGERS = {
    "palace-coupled-pilot.yml": ".github/pilot-approval.json",
    "palace-order1-ladder.yml": ".github/ladder-approval.json",
}


def trigger_surface(workflows_dir: Path) -> dict[str, dict]:
    """The push-trigger surface of every workflow in a directory."""
    out = {}
    for wf in sorted(Path(workflows_dir).glob("*.yml")):
        data = yaml.safe_load(wf.read_text()) or {}
        # PyYAML parses the bare key `on` as the boolean True
        on = data.get("on", data.get(True)) or {}
        push = on.get("push") or {}
        out[wf.name] = {"events": sorted(on.keys()),
                        "push_branches": push.get("branches"),
                        "push_paths": push.get("paths")}
    return out


def trigger_mismatches(surface: dict[str, dict],
                       pinned: dict[str, dict] | None = None) -> list[str]:
    """Every way the observed trigger surface differs from the pinned one, or breaks a
    rule that holds whatever the pin says."""
    pinned = WORKFLOW_TRIGGERS if pinned is None else pinned
    out: list[str] = []
    for name in sorted(set(surface) - set(pinned)):
        out.append(f"{name}: a workflow that is not pinned here")
    for name in sorted(set(pinned) - set(surface)):
        out.append(f"{name}: pinned but absent")
    for name in sorted(set(surface) & set(pinned)):
        got, want = surface[name], pinned[name]
        for key in ("events", "push_branches", "push_paths"):
            if got[key] != want[key]:
                out.append(f"{name}: {key} is {got[key]!r}, pinned is {want[key]!r}")
        # rules that hold regardless of the pin
        if name in SOLVER_WORKFLOWS:
            if got["push_branches"] is not None and not got["push_paths"]:
                out.append(f"{name}: a solve-capable workflow with an UNFILTERED push "
                           "trigger - every commit would start a solve")
            if "pull_request" in got["events"]:
                out.append(f"{name}: a solve-capable workflow triggered by pull_request "
                           "- a fork could start a solve")
    return out


def test_the_workflow_trigger_surface_is_exactly_the_pinned_one():
    assert trigger_mismatches(trigger_surface(WORKFLOWS)) == []


def test_only_an_approval_record_triggers_the_two_solve_on_push_workflows():
    surface = trigger_surface(WORKFLOWS)
    for name, approval in APPROVAL_TRIGGERS.items():
        assert surface[name]["push_paths"] == [approval], name
        assert (REPO_ROOT / approval).is_file(), approval
    # and no OTHER workflow may name an approval record in a trigger path
    for name, got in surface.items():
        for path in got["push_paths"] or []:
            if "approval" in path:
                assert APPROVAL_TRIGGERS.get(name) == path, (name, path)


def test_a_widened_or_added_solver_trigger_is_rejected(tmp_path: Path):
    """The negative controls. Each mutation is applied to a copy of the real workflows
    and must be named by trigger_mismatches - otherwise the pin above is decoration."""
    def mutated(change) -> list[str]:
        d = tmp_path / "wf"
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(WORKFLOWS, d)
        change(d)
        return trigger_mismatches(trigger_surface(d))

    def edit(d: Path, name: str, fn) -> None:
        wf = d / name
        data = yaml.safe_load(wf.read_text())
        on = data.pop(True, data.get("on"))
        fn(on)
        data["on"] = on
        wf.write_text(yaml.safe_dump(data, sort_keys=False))

    def widen_paths(on):
        on["push"]["paths"].append("scripts/**")

    def add_branch(on):
        on["push"]["branches"].append("claude/**")

    def drop_the_path_filter(on):
        del on["push"]["paths"]

    def add_pull_request(on):
        on["pull_request"] = None

    cases = {
        "a widened path filter": (lambda d: edit(d, "palace-order1-ladder.yml", widen_paths),
                                  "push_paths"),
        "an added branch": (lambda d: edit(d, "palace-golden.yml", add_branch),
                            "push_branches"),
        "the path filter removed": (lambda d: edit(d, "palace-order1-ladder.yml",
                                                   drop_the_path_filter), "UNFILTERED"),
        "a pull_request trigger": (lambda d: edit(d, "palace-verify.yml", add_pull_request),
                                   "pull_request"),
        "a brand-new workflow": (lambda d: (d / "palace-extra.yml").write_text(
            "name: x\non:\n  push:\n    branches: ['**']\njobs: {}\n"), "not pinned here"),
        "a workflow deleted": (lambda d: (d / "palace-verify.yml").unlink(),
                               "pinned but absent"),
    }
    for label, (change, expected) in cases.items():
        found = mutated(change)
        assert found, f"ACCEPTED: {label}"
        assert any(expected in m for m in found), (label, expected, found)

    # and the unchanged copy is clean, so the rejections above are the mutations and
    # not an artefact of copying
    assert mutated(lambda d: None) == []


# --- B. solver-launch authority ------------------------------------------------------

#: Tokens that name a container runtime or an MPI launcher.
RUNTIME_TOKENS = frozenset({"docker", "podman", "mpirun"})
#: ... and the MPI rank flag, which is how a Palace argv is actually formed here.
RANK_FLAG = "-np"
#: Calls that can start another program.
EXEC_CALLS = frozenset({"subprocess.run", "subprocess.Popen", "subprocess.call",
                        "subprocess.check_call", "subprocess.check_output",
                        "os.system", "os.popen", "os.execv", "os.execvp", "os.spawnv"})

#: The modules that can EXECUTE a container runtime or an MPI launcher: they call a
#: subprocess primitive AND name a runtime or the rank flag. NAMING a runtime without
#: being able to exec is not enough - scripts/palace_golden_run.py,
#: scripts/palace_verify_campaign.py and solvers/openems/adapter.py accept a --runtime
#: and hand it to the adapter, which is the single exec funnel - and a path segment
#: called "docker" is not a runtime, which is why experiments/first-moment-diagnostic/
#: prepare.py is absent despite naming docker/patches/.
LAUNCH_CAPABLE_PRODUCTION = {
    "experiments/first-moment-diagnostic/compiled_qualification.py",
    "experiments/first-moment-diagnostic/run_diagnostic.py",
    "scripts/palace_coupled_pilot.py",
    "scripts/palace_order1_ladder.py",
    "solvers/palace/adapter.py",
}
#: Test modules may also reach a runtime; they are pinned for the same reason.
LAUNCH_CAPABLE_TESTS = {
    "tests/test_first_moment_diagnostic.py",
    "tests/test_port_removed_control.py",
    "tests/test_s1_recovery.py",
}

#: Launch-capable modules that REFUSE in-module, with the symbol that does it. Each is
#: additionally required to contain a `raise`, so the gate is a refusal and not just a
#: name that reads like one.
REFUSES_IN_MODULE = {
    # refuses unless a human approval file exists and matches the prepared digests
    "experiments/first-moment-diagnostic/run_diagnostic.py": "load_approval",
    # refuses an approval that is missing, or that names a level, solver key or
    # boundary it does not authorise
    "scripts/palace_order1_ladder.py": "LADDER_APPROVAL",
    # refuses any config that is not one of this directory's synthetic fixtures
    "experiments/first-moment-diagnostic/compiled_qualification.py": "assert_synthetic",
    # phase C increment 3. Refuses unless .github/pilot-approval.json carries an
    # execution_authority block binding THIS run: the reviewed driver and declaration
    # digests, the frozen P1/P2/P3 set, the 250 000 DOF and 2 700 s caps, the
    # runtime/image/rank mechanism, and one new attempt inside a short UTC window. The
    # committed record carries no such block, so the pilot is inert by default -
    # presence of the historical approval is deliberately NOT permission.
    "scripts/palace_coupled_pilot.py": "require_execution_authority",
}

#: KNOWN GAP, pinned so it cannot grow unnoticed - and now one module, not two.
#:
#:   solvers/palace/adapter.py   the single exec funnel. It launches what a caller hands
#:       it and gates nothing itself; every production caller is listed above. Whether it
#:       should refuse, or whether its authority boundary is intentionally inherited from
#:       its callers, is an open ARCHITECTURE QUESTION rather than an oversight: a gate
#:       inside the funnel would have to be satisfied by the golden run, the verification
#:       campaign and the openEMS path as well, each of which has a different approval
#:       shape. It is deliberately left here, named, until that question is decided.
#:
#: Recorded in docs/agent-contract-implementation.md.
NO_IN_MODULE_REFUSAL = {
    "solvers/palace/adapter.py",
}

SKIP_DIRS = (".venv", ".git", "node_modules", "__pycache__")


def launch_capable(root: Path) -> dict[str, list[str]]:
    """Modules under `root` that can execute a container runtime or an MPI launcher,
    mapped to the tokens found. Uses the AST, so a runtime named in a comment or a
    docstring does not count, and a module that merely names one without being able to
    exec does not count either."""
    out: dict[str, list[str]] = {}
    root = Path(root)
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            with warnings.catch_warnings():   # a scanned file's own lint is not ours
                warnings.simplefilter("ignore")
                tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        execs, tokens = False, set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and ast.unparse(node.func) in EXEC_CALLS:
                execs = True
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in RUNTIME_TOKENS or node.value == RANK_FLAG:
                    tokens.add(node.value)
        if execs and tokens:
            out[path.relative_to(root).as_posix()] = sorted(tokens)
    return out


def test_the_set_of_launch_capable_modules_is_exactly_the_pinned_one():
    found = set(launch_capable(REPO_ROOT))
    production = {m for m in found if not m.startswith("tests/")}
    assert production == LAUNCH_CAPABLE_PRODUCTION, {
        "unpinned": sorted(production - LAUNCH_CAPABLE_PRODUCTION),
        "pinned but gone": sorted(LAUNCH_CAPABLE_PRODUCTION - production)}
    assert {m for m in found if m.startswith("tests/")} == LAUNCH_CAPABLE_TESTS
    # this module must not have become launch-capable itself
    assert "tests/test_launch_authority.py" not in found


def test_every_launch_capable_production_module_is_classified():
    """Every module that can start a container either refuses in-module, or is named in
    the known-gap set. There is no third, unexamined category."""
    assert set(REFUSES_IN_MODULE) | NO_IN_MODULE_REFUSAL == LAUNCH_CAPABLE_PRODUCTION
    assert not (set(REFUSES_IN_MODULE) & NO_IN_MODULE_REFUSAL)


def test_the_modules_that_claim_to_refuse_actually_raise():
    """A gate named but not wired would read as enforcement and be none."""
    for module, gate in REFUSES_IN_MODULE.items():
        src = (REPO_ROOT / module).read_text()
        assert gate in src, (module, gate)
        tree = ast.parse(src)
        assert any(isinstance(n, ast.Raise) for n in ast.walk(tree)), module


def test_the_known_gap_does_not_grow():
    """One ungated launch-capable module remains. A second would fail here rather than
    arrive unnoticed."""
    assert NO_IN_MODULE_REFUSAL == {"solvers/palace/adapter.py"}
    # and the claim about the adapter is true: it really has no approval-file read
    adapter = (REPO_ROOT / "solvers" / "palace" / "adapter.py").read_text()
    assert "approval" not in adapter.lower()
    # while the ladder, which is pinned as refusing, really does read and raise
    ladder = (REPO_ROOT / "scripts" / "palace_order1_ladder.py").read_text()
    assert "ladder-approval.json" in ladder and "raise LadderError" in ladder


def test_the_pilot_gap_is_closed_and_its_approval_is_not_self_authorising():
    """Phase C increment 3, checked here as well as in its own module, because THIS file
    is where the gap was recorded and where a regression would otherwise go unnoticed.

    The subtle failure mode is a gate that reads "the approval file exists" - which would
    pass forever, since .github/pilot-approval.json has been committed since September.
    The pilot must therefore require a block that file does not carry, and must still not
    carry today."""
    pilot = (REPO_ROOT / "scripts" / "palace_coupled_pilot.py").read_text()
    assert "pilot-approval.json" in pilot
    assert "raise PilotRefusal" in pilot
    assert "execution_authority" in pilot
    approval = json.loads((REPO_ROOT / ".github" / "pilot-approval.json").read_text())
    assert "execution_authority" not in approval, (
        "the committed approval now self-authorises; the pilot is no longer inert. Granting a "
        "real execution is deliberately a reviewed change to code AND pins, not a quiet data "
        "edit: see GRANTING_NOTE in tests/test_pilot_execution_authority.py for the four pins "
        "that must move together.")


def test_a_new_module_that_could_launch_a_container_is_rejected(tmp_path: Path):
    """Negative controls for the scanner, including the false positives it must NOT
    raise - a checker that flags everything is as useless as one that flags nothing."""
    (tmp_path / "launcher.py").write_text(
        "import subprocess\n"
        "subprocess.run(['docker', 'run', '--rm', 'qmhp-cem/palace:0.13.0'])\n")
    (tmp_path / "mpi.py").write_text(
        "import subprocess\n"
        "subprocess.Popen(['palace', '-np', '4', 'config.json'])\n")
    (tmp_path / "popen_runtime.py").write_text(
        "import subprocess\n"
        "subprocess.Popen(['podman', 'run', 'x'])\n")
    found = launch_capable(tmp_path)
    assert found["launcher.py"] == ["docker"]
    assert found["mpi.py"] == ["-np"]
    assert found["popen_runtime.py"] == ["podman"]

    # must NOT be flagged: a path segment named docker, a runtime in a comment or
    # docstring, and a subprocess call that starts nothing container-like
    (tmp_path / "paths.py").write_text(
        'from pathlib import Path\nP = Path("repo") / "docker" / "patches" / "x.patch"\n')
    (tmp_path / "prose.py").write_text(
        '"""We do not run docker here."""\n'
        "import subprocess\n# mpirun is not used\nsubprocess.run(['git', 'status'])\n")
    quiet = launch_capable(tmp_path)
    assert "paths.py" not in quiet, "a path segment is not a runtime"
    assert "prose.py" not in quiet, "a comment or docstring is not an invocation"


# --- C. the implementation record cannot rot -----------------------------------------

def test_every_test_named_by_the_implementation_record_exists():
    """docs/agent-contract-implementation.md claims, per contract clause, which tests
    enforce it. A claimed mechanism that has been renamed or deleted would leave the
    record asserting a control that is not there - the precise failure its own closing
    paragraph warns about."""
    record = REPO_ROOT / "docs" / "agent-contract-implementation.md"
    named = set(re.findall(r"\b(test_[a-z0-9_]+)\b(?!\.py)", record.read_text()))
    assert len(named) >= 15, f"the record names only {len(named)} tests; has it been gutted?"
    defined = set()
    for path in sorted((REPO_ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text())
        defined |= {n.name for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name.startswith("test_")}
    missing = sorted(named - defined)
    assert not missing, f"the implementation record names tests that do not exist: {missing}"


def test_the_implementation_record_still_separates_enforced_from_behavioural():
    """The record's value is the separation. If the BEHAVIOURAL ONLY section disappeared,
    the file would read as though every clause were enforced."""
    text = (REPO_ROOT / "docs" / "agent-contract-implementation.md").read_text()
    assert "**MECHANISM**" in text and "**BEHAVIOURAL ONLY**" in text
    assert "Known gaps" in text
    # the clauses with no mechanism today are named, not quietly dropped
    behavioural = text.split("**BEHAVIOURAL ONLY**")[1].split("## Known gaps")[0]
    for clause in ("1", "5", "8", "12"):
        assert re.search(rf"\|\s*{clause}[\s|]", behavioural), clause


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_no_workflow_carries_a_session_branch_trigger(path: Path):
    """A session branch in a trigger would let an agent's own branch start a solve."""
    on = yaml.safe_load(path.read_text()).get("on", yaml.safe_load(path.read_text()).get(True))
    branches = ((on or {}).get("push") or {}).get("branches") or []
    for branch in branches:
        assert not branch.startswith("claude/"), (path.name, branch)
        assert branch in ("**", "main", "palace/**"), (path.name, branch)
