"""Phase C, increment 4: evidence-status promotion, enforced.

AGENTS.md section 5 requires that "execution status, evidence basis, qualification and
scientific verdict" be kept distinct, and that PASS/FAIL attach to named checks rather
than standing as blanket verdicts. Those distinctions existed in prose. Nothing computed
them, so nothing stopped one being read as another.

WHAT WAS WRONG, reproduced on the frozen snapshot a8bff6b2c797fd94d977d23cfe7c849d359b20ac
before anything was changed (`scripts/palace_order1_ladder.py`, `earlier_rungs`):

  * promotion into the convergence h-sequence turned on ONE STRING. `rung.status` was
    read out of `summary.json` and compared to "COMPLETED". Flipping it excluded or
    included a rung, both directions demonstrated on a real committed record.
  * the numbers the ladder then consumed came out of the same file, and NOTHING compared
    them to the manifest. Altering one eigenfrequency, 1.709562 -> 2.564342 GHz, was
    consumed verbatim while `manifest.verify` reported "summary.json: content changed
    since the manifest was written".
  * `reference_modes` DID verify the manifest, but never read the run's status. With the
    manifest re-registered, a reference whose P2 was marked RUN_FAILED was still folded
    in as level 1, carrying its 39 832 DOF forward.
  * a rung whose own run block said `timed_out: true, returncode: 137` was promoted, so
    long as the status string above it still said COMPLETED.

ONE CLAIM DID NOT REPRODUCE, and is recorded rather than quietly dropped: "a TIMEOUT
record is promoted by flipping its status". The real TIMEOUT record
(`COUPLED-LADDER-O1-L2-N2-20260917T103405Z`) was killed before any eigenvalue existed, so
it carries no `admission` block and the frozen code raised `KeyError('admission')` instead
of promoting it. That is protection by traceback, not by a guard: it depends on the failed
run happening to lack a field, and `test_a_completed_looking_record_with_no_admission_table_is_refused`
pins that it is now a named refusal.

The guard is `orchestrator/promotion.py`. It invents no vocabulary: the authorities are
`orchestrator.manifest` (increment 2), the status and run block the driver wrote, the
frozen `COUPLED_SOLVER_RULES`, and the admission rule recomputed from the record's own
per-mode table. Nothing here carries a list of known-good records.

Every mutation below runs on a COPY in `tmp_path`. `results/` is never written to, and the
last test in this module checks that.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from orchestrator import manifest
from orchestrator.promotion import (
    GOVERNED_SCHEMAS,
    LADDER_SCHEMA,
    PILOT_SCHEMA,
    Assessment,
    EvidenceLevel,
    PromotionRefused,
    assess,
    classify,
    require,
    solve_units,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS = REPO_ROOT / "results"

PILOT = "COUPLED-PILOT-20260916T035733Z"
L2 = "COUPLED-LADDER-O1-L2-20260916T080802Z"
L3 = "COUPLED-LADDER-O1-L3-20260916T091212Z"
TIMED_OUT = "COUPLED-LADDER-O1-L2-N2-20260917T103405Z"

#: The frozen snapshot every pre-fix reproduction above was run against.
FROZEN_SHA = "a8bff6b2c797fd94d977d23cfe7c849d359b20ac"


# --- helpers: copies only ------------------------------------------------------------


def copy_records(tmp_path: Path, *names: str) -> Path:
    root = tmp_path / "results"
    root.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copytree(RESULTS / name, root / name)
    return root


def rewrite(record: Path, mutate, *, reregister: bool = False) -> Path:
    """Apply a mutation to a COPY's summary.json.

    ``reregister`` rewrites the manifest afterwards, which is the interesting case: it
    defeats the integrity layer, so whatever still refuses is doing so on the strength of
    the contradictions rather than the digests.
    """
    path = record / "summary.json"
    summary = json.loads(path.read_text())
    mutate(summary)
    path.write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    if reregister:
        manifest.write(record)
    return record


def ladder_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ladder_promotion", REPO_ROOT / "scripts" / "palace_order1_ladder.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# --- A. the ladder of levels is a ladder ---------------------------------------------


def test_the_levels_are_ordered_and_named_for_what_they_establish():
    assert [level.name for level in sorted(EvidenceLevel)] == [
        "NONE", "RECORDED", "EXECUTED", "QUALIFIED", "CHECKED", "PROMOTABLE"]
    # the four distinctions AGENTS.md section 5 requires, as strict inequalities
    assert EvidenceLevel.EXECUTED < EvidenceLevel.QUALIFIED     # completed is not qualified
    assert EvidenceLevel.QUALIFIED < EvidenceLevel.CHECKED      # qualified is not a PASS
    assert EvidenceLevel.CHECKED < EvidenceLevel.PROMOTABLE     # a PASS is not readiness
    assert EvidenceLevel.NONE < EvidenceLevel.RECORDED


def test_requires_refuses_below_the_bar_and_names_the_first_unmet_check():
    a = Assessment("R", "rung", EvidenceLevel.EXECUTED,
                   [{"check": "one", "passed": True, "detail": {}},
                    {"check": "the decisive one", "passed": False, "detail": {"why": "x"}}])
    assert a.requires(EvidenceLevel.EXECUTED) is a
    assert a.requires(EvidenceLevel.RECORDED) is a
    with pytest.raises(PromotionRefused, match="the decisive one"):
        a.requires(EvidenceLevel.QUALIFIED)


# --- B. positive controls, derived from the evidence and not from a list --------------


def governed_records() -> list[tuple[str, str, str]]:
    """(record, unit, recorded status) for every governed record on disk.

    Enumerated from the schemas the drivers wrote, so a new record is covered the moment
    it is committed and no hand-maintained good-record list exists to fall out of date.
    """
    out = []
    for record in sorted(RESULTS.iterdir()):
        summary_path = record / "summary.json"
        if not record.is_dir() or not summary_path.is_file():
            continue
        summary = json.loads(summary_path.read_text())
        if summary.get("schema") not in GOVERNED_SCHEMAS:
            continue
        for unit_name, unit in solve_units(summary).items():
            out.append((record.name, unit_name, unit.get("status")))
    return out


def test_every_governed_record_reaches_exactly_the_level_its_evidence_supports():
    """No record is asserted good. Each is asserted to reach the level its OWN recorded
    status and contents justify, which is a property of the evidence, not of a list."""
    seen = {"PROMOTABLE": 0, "QUALIFIED": 0, "RECORDED": 0}
    for name, unit, status in governed_records():
        a = assess(RESULTS / name, unit)
        summary = json.loads((RESULTS / name / "summary.json").read_text())
        if status != "COMPLETED":
            # a recorded non-completion is preserved evidence and stops at RECORDED
            assert a.level == EvidenceLevel.RECORDED, (name, unit, a.blockers[:1])
            assert a.blockers[0]["check"] == "the driver recorded COMPLETED"
        elif summary["schema"] == PILOT_SCHEMA:
            # the committed pilot predates the admission machinery: no per-mode table,
            # so there is no stored scientific verdict to recompute. QUALIFIED is the
            # honest ceiling, and its consumer recomputes admission from postpro instead.
            assert a.level == EvidenceLevel.QUALIFIED, (name, unit, a.blockers[:1])
            assert a.blockers[0]["check"] == "the record carries its admission table"
        else:
            assert a.level == EvidenceLevel.PROMOTABLE, (name, unit, a.blockers[:1])
        seen[a.level.name] = seen.get(a.level.name, 0) + 1
    assert seen["PROMOTABLE"] >= 7 and seen["QUALIFIED"] == 3 and seen["RECORDED"] >= 1


def test_the_one_timed_out_record_is_held_at_recorded():
    """The real TIMEOUT record: preserved as evidence, refused as a rung. Not by a name
    check - by its own driver's status."""
    a = assess(RESULTS / TIMED_OUT, "rung")
    assert a.level == EvidenceLevel.RECORDED
    assert a.blockers[0]["detail"]["status"] == "TIMEOUT"
    with pytest.raises(PromotionRefused, match="reaches RECORDED"):
        a.requires(EvidenceLevel.EXECUTED)


def test_the_real_h_sequence_is_unchanged_by_the_guard():
    """POSITIVE CONTROL for the wiring: the committed evidence still builds levels 1-3."""
    ladder = ladder_module()
    assert [(r["level"], r["source"]) for r in ladder.earlier_rungs()] == [
        (1, f"{PILOT}/P2"), (2, L2), (3, L3)]


def test_a_genuinely_supported_transition_is_accepted(tmp_path: Path):
    root = copy_records(tmp_path, PILOT, L2, L3)
    assert require(root / L3, "rung", level=EvidenceLevel.PROMOTABLE).level \
        == EvidenceLevel.PROMOTABLE
    assert [r["level"] for r in ladder_module().earlier_rungs(root)] == [1, 2, 3]


# --- C. the recomputation is independent of the verdict it checks ---------------------


@pytest.mark.parametrize("error,defect,expected", [
    (1e-12, 1e-5, "ADMITTED"),
    (1e-6, 1e-5, "ADMITTED"),                       # the tolerance boundary admits
    (1.1e-6, 1e-5, "REJECTED_NOT_CONVERGED"),
    (1e-12, 1e-3, "ADMITTED"),                      # the defect boundary admits
    (1e-12, 1.1e-3, "REJECTED_ENERGY_BALANCE"),
    (1.1e-6, 1.1e-3, "REJECTED_NOT_CONVERGED"),     # convergence is decided first
])
def test_classify_matches_the_repositorys_own_admission_rule(error, defect, expected):
    """The stored disposition is checked by recomputing it, so the recomputation must not
    BE the stored rule imported. It is written out separately and pinned against
    `mode_admission.admit_modes` here, so the two cannot drift.

    A first draft collapsed the two rejections into one and reported every genuine ladder
    record as disagreeing with its own table."""
    from solvers.palace.mode_admission import ModeRecord, admit_modes

    assert classify(error, defect, 1e-6, 1e-3) == expected
    record = ModeRecord(
        mode=1, frequency_GHz=1.0, frequency_im_GHz=0.0, backward_error=error,
        absolute_error=None, electric_J=1.0, magnetic_J=1.0 - defect,
        capacitive_J=0.0, inductive_J=0.0, participation={1: 0.0},
        current_A={1: complex(0, 0)}, voltage_V={1: complex(0, 0)})
    authoritative = admit_modes("X", [record], backward_error_tolerance=1e-6,
                                max_energy_balance_defect=1e-3).modes[0]
    assert classify(error, record.energy_balance_defect, 1e-6, 1e-3) == authoritative.disposition


def test_the_guard_recomputes_rather_than_trusting_the_stored_count(tmp_path: Path):
    """Proof the check is a recomputation: the per-mode numbers alone decide, and the
    record's own summary count must agree with them."""
    root = copy_records(tmp_path, L3)
    rewrite(root / L3, lambda s: s["rung"]["admission"].__setitem__("modes_admitted", 99),
            reregister=True)
    a = assess(root / L3, "rung")
    assert a.level == EvidenceLevel.QUALIFIED
    assert a.blockers[0]["check"] == "the admitted count matches the table"
    assert a.blockers[0]["detail"] == {"recorded": 99, "recomputed": 3}


# --- D. the required negative controls ------------------------------------------------


def test_missing_evidence_is_refused(tmp_path: Path):
    assert assess(tmp_path / "ABSENT", "rung").level == EvidenceLevel.NONE
    empty = tmp_path / "EMPTY"
    empty.mkdir()
    a = assess(empty, "rung")
    assert a.level == EvidenceLevel.NONE and a.blockers[0]["check"] == "summary.json is present"

    root = copy_records(tmp_path, L3)
    (root / L3 / "manifest.sha256").unlink()
    a = assess(root / L3, "rung")
    assert a.level == EvidenceLevel.NONE
    assert a.blockers[0]["check"] == "manifest.sha256 is present"

    # a manifested file deleted: recorded in the manifest, missing from disk
    root2 = copy_records(tmp_path / "b", L3)
    (root2 / L3 / "L3" / "solver" / "postpro" / "eig.csv").unlink()
    a = assess(root2 / L3, "rung")
    assert a.level == EvidenceLevel.NONE
    assert a.blockers[0]["check"] == "every file matches the manifest its driver wrote"
    assert "missing from disk" in str(a.blockers[0]["detail"])


def test_a_manifest_failure_is_refused(tmp_path: Path):
    """The R2 reproduction: altering a consumed number is now caught, by the register
    increment 2 established."""
    root = copy_records(tmp_path, L3)
    before = json.loads((root / L3 / "summary.json").read_text())
    f0 = before["rung"]["admission"]["modes"][0]["frequency_GHz"]
    rewrite(root / L3, lambda s: s["rung"]["admission"]["modes"][0].__setitem__(
        "frequency_GHz", f0 * 1.5))
    a = assess(root / L3, "rung")
    assert a.level == EvidenceLevel.NONE
    assert a.blockers[0]["check"] == "every file matches the manifest its driver wrote"
    assert "content changed" in str(a.blockers[0]["detail"])


def test_missing_required_provenance_is_refused(tmp_path: Path):
    for mutate, expected in (
        (lambda s: s["rung"].pop("palace_metadata"), "the solver reported its own identity"),
        (lambda s: s["rung"]["palace_metadata"].__setitem__("GitTag", "  "),
         "the solver reported its own identity"),
        (lambda s: s["rung"].pop("solver_rules"),
         "it ran under the frozen solver rules, unmodified"),
        (lambda s: s["rung"]["solver_rules"].__setitem__(
            "eigenmode_backward_error_max_tolerance", 1e-3),
         "it ran under the frozen solver rules, unmodified"),
    ):
        root = copy_records(tmp_path / str(id(mutate)), L3)
        rewrite(root / L3, mutate, reregister=True)
        a = assess(root / L3, "rung")
        assert a.level == EvidenceLevel.EXECUTED, (expected, a.level, a.blockers[:1])
        assert a.blockers[0]["check"] == expected


@pytest.mark.parametrize("status", ["TIMEOUT", "RUN_FAILED", "BLOCKED", "PREPARED", "ERROR"])
def test_every_non_completed_execution_status_is_refused(tmp_path: Path, status):
    root = copy_records(tmp_path / status, L3)
    rewrite(root / L3, lambda s: s["rung"].__setitem__("status", status), reregister=True)
    a = assess(root / L3, "rung")
    assert a.level == EvidenceLevel.RECORDED
    assert a.blockers[0]["check"] == "the driver recorded COMPLETED"


def test_an_unrecognised_status_is_refused_rather_than_admitted_by_omission(tmp_path: Path):
    """The list is what a driver may write. A status nobody anticipated - including one
    invented to look successful - is refused, not waved through by a `!= FAILED` test."""
    root = copy_records(tmp_path, L3)
    rewrite(root / L3, lambda s: s["rung"].__setitem__("status", "SUCCESS"), reregister=True)
    a = assess(root / L3, "rung")
    assert a.level == EvidenceLevel.RECORDED
    assert a.blockers[0]["check"] == "the status is one the drivers can write"


@pytest.mark.parametrize("mutate,expected", [
    (lambda s: s["rung"]["run"].__setitem__("timed_out", True),
     "the run does not contradict the status: not timed out"),
    (lambda s: s["rung"]["run"].__setitem__("returncode", 137),
     "the run does not contradict the status: exit code 0"),
    (lambda s: s["rung"]["run"].__setitem__("returncode", None),
     "the run does not contradict the status: exit code 0"),
    (lambda s: s["rung"]["run"].__setitem__("wall_clock_s", 9999.0),
     "the run does not contradict the status: inside its own wall-clock cap"),
    (lambda s: s["rung"].pop("run"), "the run block is present"),
    (lambda s: s["rung"].__setitem__("within_dof_budget", False),
     "the DOF budget was honoured, measured not asserted"),
    (lambda s: s["rung"].__setitem__("dof_measured", 999_999),
     "the DOF budget was honoured, measured not asserted"),
    (lambda s: s["rung"].__setitem__("dof_measured", -1),
     "the solved DOF is recorded as a positive integer"),
])
def test_contradictory_subordinate_evidence_is_refused(tmp_path: Path, mutate, expected):
    """The R4 reproduction, generalised. Each of these leaves `status: COMPLETED` in
    place and makes the record's own subordinate evidence disagree with it. The manifest
    is re-registered every time, so the digests cannot be what refuses - the contradiction
    is."""
    root = copy_records(tmp_path / str(id(mutate)), L3)
    rewrite(root / L3, mutate, reregister=True)
    assert manifest.verify(root / L3) == [], "the manifest layer is deliberately satisfied"
    a = assess(root / L3, "rung")
    assert a.blockers and a.blockers[0]["check"] == expected, (a.level, a.blockers[:1])
    assert a.level < EvidenceLevel.QUALIFIED or expected.startswith("the DOF") \
        or expected.startswith("the solved")


def test_a_status_field_rewritten_to_look_successful_is_refused(tmp_path: Path):
    """The headline case. A genuinely TIMED-OUT execution, its status rewritten to
    COMPLETED, cannot be promoted - and it is refused for naming what is missing rather
    than by crashing on a field the failed run never wrote."""
    root = copy_records(tmp_path, TIMED_OUT)
    record = root / TIMED_OUT
    assert json.loads((record / "summary.json").read_text())["rung"]["status"] == "TIMEOUT"
    rewrite(record, lambda s: s["rung"].__setitem__("status", "COMPLETED"), reregister=True)
    a = assess(record, "rung")
    # the status now says COMPLETED and the manifest agrees with the edited bytes, so
    # neither of those is what refuses. The run block the driver wrote when the solve was
    # killed still says so, and that is what refuses.
    assert a.level == EvidenceLevel.RECORDED
    assert a.blockers[0]["check"] == "the run does not contradict the status: not timed out"
    assert a.blockers[0]["detail"] == {"timed_out": True}


def test_a_completed_looking_record_with_no_admission_table_is_refused(tmp_path: Path):
    """Pins the claim that did NOT reproduce pre-fix. On the frozen snapshot this shape
    raised `KeyError('admission')` from deep inside the ladder; it is now a named
    refusal at a named level."""
    root = copy_records(tmp_path, TIMED_OUT)
    record = root / TIMED_OUT

    def launder(summary):
        summary["rung"]["status"] = "COMPLETED"
        summary["rung"]["run"].update({"timed_out": False, "returncode": 0,
                                       "wall_clock_s": 10.0})

    rewrite(record, launder, reregister=True)
    a = assess(record, "rung")
    # Laundering the status AND the run block still does not get there. The solve was
    # killed before Palace wrote its metadata, so the record carries no solver identity
    # at all - it is refused for missing provenance, one level below where the missing
    # admission table would have stopped it.
    assert a.level == EvidenceLevel.EXECUTED
    assert a.blockers[0]["check"] == "the solver reported its own identity"
    assert a.blockers[0]["detail"] == {"GitTag": None}
    with pytest.raises(PromotionRefused, match="the solver reported its own identity"):
        a.requires(EvidenceLevel.CHECKED)


def test_a_hand_promoted_disposition_is_refused(tmp_path: Path):
    """"PASS applies to named checks": a mode marked ADMITTED whose own numbers do not
    admit it is caught by recomputation, with the manifest deliberately satisfied."""
    root = copy_records(tmp_path, L3)

    def promote(summary):
        for mode in summary["rung"]["admission"]["modes"]:
            if mode["disposition"] != "ADMITTED":
                mode["disposition"] = "ADMITTED"
                break
        summary["rung"]["admission"]["modes_admitted"] = 4

    rewrite(root / L3, promote, reregister=True)
    a = assess(root / L3, "rung")
    assert a.level == EvidenceLevel.QUALIFIED
    assert a.blockers[0]["check"] == \
        "every recorded disposition is reproduced from the per-mode table"
    bad = a.blockers[0]["detail"]["disagreements"][0]
    assert bad["recorded"] == "ADMITTED" and bad["recomputed"] == "REJECTED_ENERGY_BALANCE"


def test_a_loosened_admission_tolerance_is_refused(tmp_path: Path):
    """Relaxing the stored tolerance so a rejected mode passes is refused at the frozen
    value, not at the record's own."""
    root = copy_records(tmp_path, L3)
    rewrite(root / L3, lambda s: s["rung"]["admission"].__setitem__(
        "backward_error_tolerance", 1.0), reregister=True)
    a = assess(root / L3, "rung")
    assert a.blockers[0]["check"] == "the admission tolerance is the frozen one"


@pytest.mark.parametrize("mutate,expected", [
    (lambda s: s.__setitem__("batch_id", "COUPLED-LADDER-O1-L9-20991231T000000Z"),
     "the record's own id matches its directory"),
    (lambda s: s.__setitem__("batch_id", None),
     "the record's own id matches its directory"),
    (lambda s: s.__setitem__("level", 9), "the rung's level matches the record's declared level"),
    (lambda s: s.__setitem__("schema", "qmhp-cem.something-else/1.0"),
     "the record family is one this guard governs"),
])
def test_stale_or_inconsistent_promotion_metadata_is_refused(tmp_path: Path, mutate, expected):
    """A record copied under another name, or whose declared level no longer matches the
    rung inside it, is not the record it claims to be."""
    root = copy_records(tmp_path / str(id(mutate)), L3)
    rewrite(root / L3, mutate, reregister=True)
    a = assess(root / L3, "rung")
    assert a.blockers and a.blockers[0]["check"] == expected, a.blockers[:1]


def _pilot_with_an_admission_table(root: Path, *, defects=(1e-5, 1e-5, 1e-5, 1e-5, 1e-5, 1e-5)):
    """A pilot-family record carrying the admission table the committed one lacks.

    The committed pilot predates the admission machinery, so on real evidence the pilot
    branch of PROMOTABLE is never reached and its mirror check would be a line nothing
    exercises. This builds the missing table from the record's OWN per-mode backward
    errors, so the branch is reached and the check is actually tested rather than
    asserted to exist.
    """
    def add(summary):
        run = summary["runs"]["P2"]
        modes = run["modes"]
        table = [{"mode": m["index"], "backward_error": m["backward_error"],
                  "energy_balance_defect": d, "disposition": classify(
                      m["backward_error"], d, 1e-6, 1e-3)}
                 for m, d in zip(modes, defects)]
        run["admission"] = {
            "backward_error_tolerance": 1e-6,
            "rule": {"max_energy_balance_defect": 1e-3},
            "modes": table,
            "modes_admitted": sum(1 for t in table if t["disposition"] == "ADMITTED"),
        }
        run["max_backward_error"] = max(t["backward_error"] for t in table)

    return rewrite(root / PILOT, add, reregister=True)


def test_a_pilot_record_carrying_an_admission_table_can_reach_promotable(tmp_path: Path):
    """POSITIVE control for the pilot branch, so the mirror check below is reachable."""
    root = copy_records(tmp_path, PILOT)
    _pilot_with_an_admission_table(root)
    assert assess(root / PILOT, "P2").level == EvidenceLevel.PROMOTABLE


def test_the_pilots_mirrored_status_must_agree_with_the_run_it_mirrors(tmp_path: Path):
    """`next_stage.statuses` is a second copy of each run's status. Two copies that
    disagree mean one was edited, and the promotion metadata is stale."""
    root = copy_records(tmp_path, PILOT)
    _pilot_with_an_admission_table(root)
    rewrite(root / PILOT, lambda s: s["next_stage"]["statuses"].__setitem__("P2", "RUN_FAILED"),
            reregister=True)
    a = assess(root / PILOT, "P2")
    assert a.level == EvidenceLevel.CHECKED, "it passes the science and fails on staleness"
    assert a.blockers[0]["check"] == \
        "the next-stage status mirror agrees with the run it mirrors"
    assert a.blockers[0]["detail"] == {"next_stage.statuses": "RUN_FAILED",
                                       "run status": "COMPLETED"}
    with pytest.raises(PromotionRefused, match="status mirror"):
        a.requires(EvidenceLevel.PROMOTABLE)


def test_the_pilot_branch_also_recomputes_its_dispositions(tmp_path: Path):
    """The scientific check is recomputed for this family too, not only for the ladder."""
    root = copy_records(tmp_path, PILOT)
    # one mode's energy balance is far outside the bound, so it must be REJECTED
    _pilot_with_an_admission_table(root, defects=(1e-5, 9.9e-1, 1e-5, 1e-5, 1e-5, 1e-5))
    assert assess(root / PILOT, "P2").level == EvidenceLevel.PROMOTABLE
    rewrite(root / PILOT, lambda s: s["runs"]["P2"]["admission"]["modes"][1].__setitem__(
        "disposition", "ADMITTED"), reregister=True)
    a = assess(root / PILOT, "P2")
    assert a.level == EvidenceLevel.QUALIFIED
    assert a.blockers[0]["check"] == \
        "every recorded disposition is reproduced from the per-mode table"


def test_an_ungoverned_record_family_is_refused_not_guessed_at():
    """A rule written for one family must not be applied to another. The S1 recovery
    record is a real, valid record of a different family; it is declined, not judged."""
    with pytest.raises(PromotionRefused, match="not one this guard governs"):
        solve_units(json.loads(
            (RESULTS / "COUPLED-S1-RECOVERY-20260916T105215Z" / "summary.json").read_text()))
    a = assess(RESULTS / "COUPLED-S1-RECOVERY-20260916T105215Z")
    assert a.level == EvidenceLevel.NONE
    assert a.blockers[0]["check"] in {"the record's own id matches its directory",
                                      "the record family is one this guard governs"}


# --- E. the wiring: the ladder actually refuses ---------------------------------------


@pytest.mark.parametrize("label,mutate,reregister", [
    ("altered numbers", lambda s: s["rung"]["admission"]["modes"][0].__setitem__(
        "frequency_GHz", 99.0), False),
    ("contradictory run block", lambda s: s["rung"]["run"].update(
        {"timed_out": True, "returncode": 137}), True),
    ("hand-promoted mode", lambda s: (
        s["rung"]["admission"]["modes"][2].__setitem__("disposition", "ADMITTED"),
        s["rung"]["admission"].__setitem__("modes_admitted", 4)), True),
    ("stale record id", lambda s: s.__setitem__("batch_id", "SOMETHING-ELSE"), True),
])
def test_the_ladder_refuses_a_rung_that_claims_more_than_its_evidence(
        tmp_path: Path, label, mutate, reregister):
    """The pre-fix reproductions, re-run through the real consumer. Each was ACCEPTED on
    the frozen snapshot."""
    ladder = ladder_module()
    root = copy_records(tmp_path / label.replace(" ", "-"), PILOT, L2, L3)
    rewrite(root / L3, mutate, reregister=reregister)
    with pytest.raises(ladder.LadderError, match="does not support promotion"):
        ladder.earlier_rungs(root)


def test_the_ladder_refuses_a_reference_whose_run_failed(tmp_path: Path):
    """The R3 reproduction. The manifest is re-registered, so the digest layer passes and
    the refusal rests on the execution status the frozen code never read."""
    ladder = ladder_module()
    root = copy_records(tmp_path, PILOT, L2, L3)
    rewrite(root / PILOT, lambda s: s["runs"]["P2"].__setitem__("status", "RUN_FAILED"),
            reregister=True)
    assert manifest.verify(root / PILOT) == []
    with pytest.raises(ladder.LadderError, match="level-1 reference cannot be used"):
        ladder.earlier_rungs(root)


def test_a_genuine_non_completion_is_skipped_not_refused(tmp_path: Path):
    """Behaviour preserved. A record that honestly says TIMEOUT is preserved evidence and
    must not break the ladder - only a record that CLAIMS completion is held to the bar."""
    ladder = ladder_module()
    root = copy_records(tmp_path, PILOT, L2, L3, TIMED_OUT)
    assert [r["level"] for r in ladder.earlier_rungs(root)] == [1, 2, 3]


def test_the_existing_refinement_and_duplicate_guards_still_fire_first(tmp_path: Path):
    """The promotion check is deliberately placed AFTER them, so each failure is still
    named by the guard that understands it."""
    ladder = ladder_module()
    root = copy_records(tmp_path, PILOT, L2, L3)
    shutil.copytree(root / L2, root / "COUPLED-LADDER-O1-L2-20260916T999999Z")
    with pytest.raises(ladder.LadderError, match="two records claim ladder level 2"):
        ladder.earlier_rungs(root)


# --- F. this module touched no historical evidence ------------------------------------


def test_the_committed_records_were_not_written_to():
    """Every mutation above ran on a copy. This is the check that says so."""
    for name in (PILOT, L2, L3, TIMED_OUT):
        assert manifest.verify(RESULTS / name) == [], f"{name} was modified by the tests"
