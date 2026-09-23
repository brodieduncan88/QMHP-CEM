"""Phase C, increment 4: evidence-status promotion (AGENTS.md section 5).

    "Keep execution status, evidence basis, qualification and scientific verdict
     distinct."  -- AGENTS.md section 5
    "PASS and FAIL apply to named checks or claims; they are not blanket verdicts."

Those four things were kept distinct in PROSE. Nothing computed them, so nothing
stopped a later reader -- human or agent -- from treating one as another. This module
computes them, in order, from evidence the repository already holds.

WHAT THIS IS NOT. It invents no new status vocabulary and no parallel record model. The
authorities are the ones already in the repository:

  evidence basis      ``orchestrator.manifest.verify`` -- increment 2's rule, unchanged
  execution status    the ``status`` and ``run`` block the DRIVER wrote at execution time
  qualification       the frozen ``COUPLED_SOLVER_RULES``, the record's own DOF budget
                      and wall-clock cap, and the solver identity Palace itself reported
  scientific verdict  the admission rule the record carries, RECOMPUTED from the record's
                      own per-mode table rather than read from a verdict field

and the shape of the result -- an ordered ``checks`` list, ``all_checks_passed``, a
fail-closed verdict -- follows ``experiments/first-moment-diagnostic/reference_model.py``,
which is how this repository already reports a qualification.

THE LADDER IS ORDERED AND EACH STEP REQUIRES THE ONE BELOW.

    NONE < RECORDED < EXECUTED < QUALIFIED < CHECKED < PROMOTABLE

    RECORDED    the record exists, is the record it claims to be, and its bytes match
                the manifest its own driver wrote
    EXECUTED    a solve ran to completion by its driver's own status, AND nothing in the
                run block contradicts that status
    QUALIFIED   the rules it ran under are the frozen ones, the solver identity is
                present, and the declared caps were honoured
    CHECKED     the record's own named scientific check passes when recomputed from its
                per-mode table
    PROMOTABLE  the promotion metadata is self-consistent and not stale

WHY THIS CANNOT BE PASSED BY EDITING A FIELD. Rewriting ``status`` in ``summary.json``
changes the file's bytes, so ``manifest.verify`` reports it and the record falls to NONE.
Rewriting the manifest to agree is what increment 2's aggregate digest refuses. And
re-registering a manifest wholesale still leaves the contradictions: the ``run`` block
still says the solve was killed, and the per-mode table still disagrees with a flipped
disposition. The layers are independent on purpose -- no single edit satisfies all three.

Scope: the two record families that carry a solve and feed the order-1 h-sequence. Other
families (checkpoint analyses, the S1 recovery, the verification campaigns) have their own
verifiers and are deliberately not judged here.
"""

from __future__ import annotations

import json
import math
from enum import IntEnum
from pathlib import Path
from typing import Any

from orchestrator import manifest

#: The families this guard governs, mapped to the solve units inside one record.
PILOT_SCHEMA = "qmhp-cem.coupled-pilot/0.1.0"
LADDER_SCHEMA = "qmhp-cem.coupled-order1-ladder/0.1.0"
GOVERNED_SCHEMAS = frozenset({PILOT_SCHEMA, LADDER_SCHEMA})

#: The ONLY execution status that means a solve ran to completion. Everything else --
#: TIMEOUT, RUN_FAILED, BLOCKED, PREPARED, ERROR -- is a recorded outcome and is not one.
#: Listed explicitly rather than as "not FAILED", so a status nobody anticipated is
#: refused rather than admitted by omission.
COMPLETED_STATUS = "COMPLETED"
KNOWN_STATUSES = frozenset({
    COMPLETED_STATUS, "TIMEOUT", "RUN_FAILED", "BLOCKED", "PREPARED", "ERROR",
})


class EvidenceLevel(IntEnum):
    """How far the evidence actually reaches. Ordered; each step requires the last."""

    NONE = 0
    RECORDED = 1
    EXECUTED = 2
    QUALIFIED = 3
    CHECKED = 4
    PROMOTABLE = 5


class PromotionRefused(RuntimeError):
    """A record was asked to stand for more than its evidence supports."""


class Assessment:
    """The level the evidence reaches, and every check that decided it."""

    __slots__ = ("record", "unit", "level", "checks")

    def __init__(self, record: str, unit: str, level: EvidenceLevel,
                 checks: list[dict[str, Any]]) -> None:
        self.record, self.unit, self.level, self.checks = record, unit, level, checks

    @property
    def blockers(self) -> list[dict[str, Any]]:
        return [c for c in self.checks if not c["passed"]]

    def requires(self, level: EvidenceLevel) -> "Assessment":
        """Return self, or refuse with the FIRST failing check rather than a summary.

        The first failure is what a reader needs: a record that fails RECORDED will
        trivially fail everything above it, and reporting all of them buries the cause.
        """
        if self.level < level:
            first = self.blockers[0] if self.blockers else {"check": "unknown", "detail": {}}
            raise PromotionRefused(
                f"{self.record}/{self.unit} reaches {self.level.name}, and "
                f"{level.name} is required. First unmet check: {first['check']} "
                f"({first['detail']})")
        return self

    def as_dict(self) -> dict[str, Any]:
        return {"record": self.record, "unit": self.unit, "level": self.level.name,
                "checks": self.checks}


#: The three dispositions the admission rule produces. Written out here rather than
#: imported, so this is an INDEPENDENT recomputation of the record's stored verdict
#: rather than the stored verdict compared against itself; `test_evidence_promotion.py`
#: pins that it agrees with `solvers.palace.mode_admission.admit_modes` on every branch,
#: so the two cannot drift.
#:
#: A FIRST DRAFT OF THIS FUNCTION COLLAPSED THE TWO REJECTIONS INTO ONE and reported
#: every genuine ladder record as disagreeing with its own table -- a false integrity
#: failure on historical evidence, caught before it was believed. Convergence and energy
#: balance are separate dispositions on purpose: a mode can converge perfectly and still
#: not be a resonance.
def classify(backward_error: float, energy_balance_defect: float,
             tolerance: float, max_defect: float) -> str:
    if backward_error > tolerance:
        return "REJECTED_NOT_CONVERGED"
    if energy_balance_defect > max_defect:
        return "REJECTED_ENERGY_BALANCE"
    return "ADMITTED"


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) \
        and math.isfinite(float(value))


def solve_units(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The solve unit(s) in one record, by the record's OWN schema.

    A pilot record carries three (P1/P2/P3); a ladder record carries one rung. Dispatch
    is on the schema the driver wrote, not on which keys happen to be present, so a
    record of an unexpected family is refused rather than guessed at.
    """
    schema = summary.get("schema")
    if schema == PILOT_SCHEMA:
        return dict(summary.get("runs") or {})
    if schema == LADDER_SCHEMA:
        return {"rung": summary["rung"]} if isinstance(summary.get("rung"), dict) else {}
    raise PromotionRefused(
        f"schema {schema!r} is not one this guard governs ({sorted(GOVERNED_SCHEMAS)}); "
        "it is not judged here rather than being judged by a rule written for another "
        "family")


def _unit_dof(unit: dict[str, Any]) -> Any:
    """The solved DOF, under whichever name this family records it."""
    for key in ("dof_measured", "dof_for_this_order"):
        if key in unit:
            return unit[key]
    return None


def assess(record_dir: Path, unit_name: str | None = None, *,
           frozen_rules: dict[str, Any] | None = None) -> Assessment:
    """How far one solve unit's evidence reaches. Never raises on bad evidence."""
    if frozen_rules is None:                                 # imported lazily: this module
        from solvers.palace.coupled_config import (          # noqa: PLC0415
            COUPLED_SOLVER_RULES,                            # is also used by tooling that
        )                                                    # need not pull in the solver
        frozen_rules = dict(COUPLED_SOLVER_RULES)

    record_dir = Path(record_dir)
    name = record_dir.name
    checks: list[dict[str, Any]] = []
    level = EvidenceLevel.NONE

    def check(label: str, passed: bool, detail: Any) -> bool:
        checks.append({"check": label, "passed": bool(passed), "detail": detail})
        return bool(passed)

    def done() -> Assessment:
        return Assessment(name, unit_name or "?", level, checks)

    # --- RECORDED: evidence basis ----------------------------------------------------
    summary_path = record_dir / "summary.json"
    if not check("the record directory exists", record_dir.is_dir(), {"path": str(record_dir)}):
        return done()
    if not check("summary.json is present", summary_path.is_file(), {"path": str(summary_path)}):
        return done()
    try:
        summary = json.loads(summary_path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        check("summary.json parses", False, {"error": f"{type(exc).__name__}: {exc}"})
        return done()
    check("summary.json parses", True, {})

    if not check("manifest.sha256 is present", (record_dir / "manifest.sha256").is_file(),
                 {"note": "a record with no integrity register cannot be promoted"}):
        return done()
    discrepancies = manifest.verify(record_dir)
    if not check("every file matches the manifest its driver wrote", not discrepancies,
                 {"discrepancies": discrepancies[:5]}):
        return done()
    # the record is the record it claims to be
    claimed = summary.get("batch_id")
    if not check("the record's own id matches its directory", claimed == name,
                 {"batch_id": claimed, "directory": name}):
        return done()

    try:
        units = solve_units(summary)
    except PromotionRefused as exc:
        check("the record family is one this guard governs", False, {"error": str(exc)})
        return done()
    check("the record family is one this guard governs", True, {"schema": summary["schema"]})

    if unit_name is None:
        unit_name = next(iter(units), "?")
    if not check("the named solve unit exists", unit_name in units,
                 {"unit": unit_name, "available": sorted(units)}):
        return done()
    unit = units[unit_name]
    level = EvidenceLevel.RECORDED

    # --- EXECUTED: execution status, and nothing that contradicts it -----------------
    status = unit.get("status")
    if not check("the status is one the drivers can write", status in KNOWN_STATUSES,
                 {"status": status, "known": sorted(KNOWN_STATUSES)}):
        return done()
    if not check(f"the driver recorded {COMPLETED_STATUS}", status == COMPLETED_STATUS,
                 {"status": status, "note": "a recorded outcome is evidence, not completion"}):
        return done()
    run = unit.get("run")
    if not check("the run block is present", isinstance(run, dict),
                 {"note": "a COMPLETED status with no run block is a claim without a solve"}):
        return done()
    if not check("the run does not contradict the status: not timed out",
                 run.get("timed_out") is False, {"timed_out": run.get("timed_out")}):
        return done()
    if not check("the run does not contradict the status: exit code 0",
                 run.get("returncode") == 0, {"returncode": run.get("returncode")}):
        return done()
    wall, cap = run.get("wall_clock_s"), run.get("timeout_s")
    if not check("the run does not contradict the status: inside its own wall-clock cap",
                 _finite(wall) and _finite(cap) and float(wall) <= float(cap),
                 {"wall_clock_s": wall, "timeout_s": cap}):
        return done()
    level = EvidenceLevel.EXECUTED

    # --- QUALIFIED: the rules it ran under, its identity, its declared limits ---------
    recorded_rules = unit.get("solver_rules")
    if not check("it ran under the frozen solver rules, unmodified",
                 recorded_rules == frozen_rules,
                 {"differs_in": sorted(k for k in set(frozen_rules) | set(recorded_rules or {})
                                       if (recorded_rules or {}).get(k) != frozen_rules.get(k))}):
        return done()
    metadata = unit.get("palace_metadata")
    if not check("the solver reported its own identity", isinstance(metadata, dict)
                 and bool(str(metadata.get("GitTag") or "").strip()),
                 {"GitTag": (metadata or {}).get("GitTag")}):
        return done()
    dof, budget = _unit_dof(unit), summary.get("dof_budget")
    if not check("the solved DOF is recorded as a positive integer",
                 isinstance(dof, int) and not isinstance(dof, bool) and dof > 0, {"dof": dof}):
        return done()
    if not check("the DOF budget was honoured, measured not asserted",
                 _finite(budget) and dof <= budget and unit.get("within_dof_budget") is True,
                 {"dof": dof, "dof_budget": budget,
                  "within_dof_budget": unit.get("within_dof_budget")}):
        return done()
    level = EvidenceLevel.QUALIFIED

    # --- CHECKED: the named scientific check, RECOMPUTED ------------------------------
    admission = unit.get("admission")
    if not check("the record carries its admission table", isinstance(admission, dict)
                 and isinstance(admission.get("modes"), list) and admission["modes"],
                 {"note": "no per-mode table means no scientific check to recompute here. "
                          "The committed pilot record is exactly this case: it predates the "
                          "admission machinery, so it stops at QUALIFIED and its consumer "
                          "recomputes admission from the postpro tables at use time, which "
                          "is stronger than trusting a stored disposition."}):
        return done()
    tolerance = admission.get("backward_error_tolerance")
    frozen_tolerance = frozen_rules.get("eigenmode_backward_error_max_tolerance")
    if not check("the admission tolerance is the frozen one", tolerance == frozen_tolerance,
                 {"recorded": tolerance, "frozen": frozen_tolerance}):
        return done()
    defect_max = (admission.get("rule") or {}).get("max_energy_balance_defect")
    if not check("the energy-balance bound is stated and finite", _finite(defect_max),
                 {"max_energy_balance_defect": defect_max}):
        return done()

    disagreements, admitted = [], 0
    for mode in admission["modes"]:
        error, defect = mode.get("backward_error"), mode.get("energy_balance_defect")
        if not (_finite(error) and _finite(defect)):
            disagreements.append({"mode": mode.get("mode"), "why": "non-finite check inputs",
                                  "backward_error": error, "energy_balance_defect": defect})
            continue
        recomputed = classify(error, defect, tolerance, defect_max)
        if recomputed == "ADMITTED":
            admitted += 1
        if mode.get("disposition") != recomputed:
            disagreements.append({"mode": mode.get("mode"), "recorded": mode.get("disposition"),
                                  "recomputed": recomputed, "backward_error": error,
                                  "energy_balance_defect": defect})
    if not check("every recorded disposition is reproduced from the per-mode table",
                 not disagreements, {"disagreements": disagreements[:5]}):
        return done()
    if not check("the admitted count matches the table",
                 admission.get("modes_admitted") == admitted,
                 {"recorded": admission.get("modes_admitted"), "recomputed": admitted}):
        return done()
    worst = max(m["backward_error"] for m in admission["modes"])
    if not check("the summary's worst backward error matches the table",
                 _finite(unit.get("max_backward_error"))
                 and math.isclose(float(unit["max_backward_error"]), worst, rel_tol=0.0,
                                  abs_tol=0.0),
                 {"summary": unit.get("max_backward_error"), "table": worst}):
        return done()
    if not check("at least one mode is admitted", admitted > 0, {"admitted": admitted}):
        return done()
    level = EvidenceLevel.CHECKED

    # --- PROMOTABLE: the promotion metadata is self-consistent and not stale ----------
    if summary["schema"] == LADDER_SCHEMA:
        if not check("the rung's level matches the record's declared level",
                     summary.get("level") == unit.get("level"),
                     {"summary.level": summary.get("level"), "rung.level": unit.get("level")}):
            return done()
    else:
        mirrored = ((summary.get("next_stage") or {}).get("statuses") or {}).get(unit_name)
        if not check("the next-stage status mirror agrees with the run it mirrors",
                     mirrored == status, {"next_stage.statuses": mirrored, "run status": status}):
            return done()
    level = EvidenceLevel.PROMOTABLE
    return done()


def require(record_dir: Path, unit_name: str | None = None, *,
            level: EvidenceLevel = EvidenceLevel.CHECKED,
            frozen_rules: dict[str, Any] | None = None) -> Assessment:
    """Assess, and refuse unless the evidence reaches ``level``."""
    return assess(record_dir, unit_name, frozen_rules=frozen_rules).requires(level)
