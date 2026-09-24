# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Labelling rules for the read-only viewer, stated as data.

Two questions are answered here and kept apart:

* **Evidence basis** - what KIND of evidence a record is: SYNTHETIC, SOLVED,
  MEASURED, ANALYSIS (derived from committed records, no new solve),
  DECLARATION (prepared, not executed) or UNCLASSIFIED.
* **Status tokens** - what the record SAYS about itself: the verdict, outcome
  and status strings it carries, quoted verbatim with their JSON path.

The viewer never manufactures a verdict. A status label is always a token
taken from the record, shown next to the path it came from. Normalisation to
a small set of display families (QUALIFIED, FAILED, ...) only chooses a colour
and a filter facet; the original token is always displayed.

The rules fail conservatively. ``MEASURED`` is assigned only when a record
literally declares ``evidence_class`` or ``classification`` as ``MEASURED``; it
is never inferred. When no rule matches, the basis is ``UNCLASSIFIED`` and the
viewer says so rather than guessing.
"""

from __future__ import annotations

import re
from typing import Any, Iterator

BASES = ("SYNTHETIC", "SOLVED", "MEASURED", "ANALYSIS", "DECLARATION", "UNCLASSIFIED")

BASIS_EXPLANATIONS = {
    "SYNTHETIC": "Synthetic or test-fixture data: known-answer inputs, mock solvers or "
                 "software demonstrations. Carries no evidentiary weight about any candidate.",
    "SOLVED": "Produced by a numerical solver for a declared input. Computational evidence "
              "only - not hardware validation.",
    "MEASURED": "From physical hardware. Assigned only when a record explicitly declares "
                "it; never inferred by this viewer.",
    "ANALYSIS": "Derived from already-committed records without launching a new solve "
                "(corrective analyses, dry runs, admission checks, recoveries).",
    "DECLARATION": "Prepared or predeclared, not executed: proposals, predeclarations, "
                   "candidate configurations and approval drafts.",
    "UNCLASSIFIED": "No rule matched. The viewer does not guess; read the record itself.",
}

#: Ordered rules for results/ records. The first match wins. Each rule is shown
#: verbatim in the UI so a reader can check why a label was given.
RECORD_RULES = (
    {"id": "R1", "basis": "SYNTHETIC",
     "rule": "The record identifier contains SYNTHETIC."},
    {"id": "R2", "basis": "SYNTHETIC",
     "rule": "The record declares synthetic data: a key 'synthetic' or 'synthetic_only' "
             "set to true, a 'not_qmhp' key, or a classification of TEST_FIXTURE."},
    {"id": "R3", "basis": "MEASURED",
     "rule": "A key 'evidence_class', 'classification' or 'evidence_basis' literally "
             "equals MEASURED. (No inference; absent this, nothing is MEASURED.)"},
    {"id": "R4", "basis": "ANALYSIS",
     "rule": "The record says no solve was launched: 'palace_launched' is false, "
             "'kind' names a corrective analysis, or it is a dry-run/admission record "
             "('dry_run_mode' present)."},
    {"id": "R5", "basis": "SOLVED",
     "rule": "The record carries solver execution provenance: 'solver_provenance', a "
             "'palace_status', a solver identity or image id, eigenmodes, a gate result "
             "with evidence_class SOLVED, or a solver/ output directory."},
    {"id": "R6", "basis": "SOLVED",
     "rule": "The record is an approval-bound numerical execution: one of its files cites "
             "an 'approval_sha256' and one records consumed 'resources'."},
    {"id": "R0", "basis": "UNCLASSIFIED",
     "rule": "No rule above matched."},
)

#: Rules for experiments/ directories.
EXPERIMENT_RULES = (
    {"id": "E1", "basis": "SYNTHETIC",
     "rule": "The directory name contains SYNTHETIC. (Individual files that declare "
             "synthetic fixtures are listed separately; one fixture does not make the "
             "whole experiment synthetic.)"},
    {"id": "E2", "basis": "DECLARATION",
     "rule": "Otherwise an experiment directory is a declaration: its evidence, if any, "
             "is in the results/ records it links to, each classified on its own."},
)

# ---------------------------------------------------------------- statuses

#: JSON keys whose string values are statements of status about the record.
STATUS_KEYS = frozenset({
    "status", "verdict", "outcome", "overall_status", "disposition",
    "execution_disposition", "admission_disposition", "palace_status", "decision",
    "batch_outcome", "conclusion", "status_as_executed", "state", "result",
})

#: Paths tried, in order, for the record's headline statuses.
HEADLINE_PATHS = (
    "outcome.verdict", "outcome", "batch_outcome", "overall_status", "gates.overall_status",
    "execution_disposition", "admission_disposition", "mesh_convergence.verdict",
    "height.aux_height.verdict", "height.object001_height.verdict", "rung.status",
    "rung.port_field_test.verdict", "halo_verdict.verdict", "halo_disposition.verdict",
    "next_stage.disposition", "convergence.status", "status", "verdict",
)

_SEGMENT_SPLIT = re.compile(r"[.;:,()\[\]]|\s[-–—]\s")
_CAPS = re.compile(r"^[A-Z][A-Z0-9_\-/ ]*[A-Z0-9]$")

#: Exact tokens and the display family they belong to. Anything not listed is
#: displayed as recorded, in a neutral colour.
_FAMILY_EXACT = {
    "QUALIFIED": "QUALIFIED",
    "UNQUALIFIED": "UNQUALIFIED",
    "PASS": "PASS", "PASSED": "PASS",
    "FAIL": "FAILED", "FAILED": "FAILED", "RUN_FAILED": "FAILED",
    "SOLVER_FAILURE": "FAILED", "NOT_CONVERGED": "FAILED",
    "REFUSED": "REFUSED",
    "INCOMPLETE": "INCOMPLETE",
    "NOT-EVALUATED": "NOT-EVALUATED",
    "HARDWARE-GATED": "HARDWARE-GATED",
    "BLOCKED": "BLOCKED", "EXECUTION BLOCKED": "BLOCKED",
    "TIMEOUT": "TIMEOUT",
    "UNRESOLVED": "INCONCLUSIVE", "NOT_RESOLVED": "INCONCLUSIVE",
    "INCONCLUSIVE": "INCONCLUSIVE", "UNAVAILABLE": "INCONCLUSIVE",
    "INCONSISTENT": "INCONCLUSIVE", "EXTRACTION-INCONSISTENT": "INCONCLUSIVE",
    "CONVERGED": "COMPLETED", "COMPLETED": "COMPLETED", "MATCHED": "COMPLETED",
    "CERTIFIED": "COMPLETED", "CONSISTENT": "COMPLETED",
    "WITHDRAWN": "WITHDRAWN", "SUPERSEDED": "WITHDRAWN",
    "PREPARED": "PREPARED", "NOT APPROVED": "PREPARED", "NOT EXECUTED": "PREPARED",
    "NOT LAUNCHED": "PREPARED", "DRAFT": "PREPARED",
    "FEASIBLE_CANDIDATE_FOUND": "PASS", "NO_FEASIBLE_DESIGN_FOUND": "FAILED",
}
_FAMILY_PREFIX = (
    ("UNQUALIFIED", "UNQUALIFIED"), ("REFUSED", "REFUSED"), ("BLOCKED", "BLOCKED"),
    ("HARDWARE-GATED", "HARDWARE-GATED"), ("INCONCLUSIVE", "INCONCLUSIVE"),
    ("WITHDRAWN", "WITHDRAWN"), ("SUPERSEDED", "WITHDRAWN"), ("TIMEOUT", "TIMEOUT"),
    ("READY-FOR-REVIEW", "PREPARED"), ("FOR REVIEW", "PREPARED"),
)

#: Display families, their tone, and what the tone means. The UI renders the
#: family as a colour and always prints the original token as text.
FAMILIES = {
    "QUALIFIED": ("positive", "The record's own qualification check passed. Computational only."),
    "PASS": ("positive", "A named computational check passed. Not hardware validation."),
    "COMPLETED": ("positive", "Execution completed / converged / matched. Says nothing about a verdict."),
    "UNQUALIFIED": ("negative", "A required integrity or provenance check failed; no value is qualified."),
    "FAILED": ("negative", "A named check or execution failed."),
    "REFUSED": ("negative", "Refused - by policy, a guard or an egress rule."),
    "BLOCKED": ("negative", "Blocked by a precondition (budget, missing input, gate)."),
    "INCOMPLETE": ("caution", "Could not be adjudicated with the evidence available."),
    "NOT-EVALUATED": ("caution", "Not evaluated."),
    "TIMEOUT": ("caution", "Stopped at its wall-clock cap."),
    "INCONCLUSIVE": ("caution", "Unresolved, inconclusive or unavailable."),
    "HARDWARE-GATED": ("gated", "Requires MEASURED hardware evidence. Cannot pass computationally."),
    "WITHDRAWN": ("muted", "Withdrawn or superseded; preserved as history."),
    "PREPARED": ("muted", "Prepared, drafted or awaiting review - not executed."),
    "AS-RECORDED": ("neutral", "Displayed exactly as recorded; the viewer assigns no meaning."),
}


def leading_tokens(value: str) -> list[str]:
    """Upper-case status tokens at the start of a status string.

    ``"PREPARED. NOT APPROVED. NOT EXECUTED. No solve..."`` gives
    ``["PREPARED", "NOT APPROVED", "NOT EXECUTED"]``; prose gives ``[]``."""
    out: list[str] = []
    for segment in _SEGMENT_SPLIT.split(value):
        segment = segment.strip()
        if not segment:
            continue
        letters = sum(c.isalpha() for c in segment)
        if len(segment) <= 48 and letters >= 2 and _CAPS.match(segment):
            out.append(segment)
        else:
            break
    return out


def family(token: str) -> str:
    if token in _FAMILY_EXACT:
        return _FAMILY_EXACT[token]
    for prefix, fam in _FAMILY_PREFIX:
        if token.startswith(prefix):
            return fam
    return "AS-RECORDED"


def tone(fam: str) -> str:
    return FAMILIES.get(fam, FAMILIES["AS-RECORDED"])[0]


def token_tone(token: str | None) -> str:
    """Display tone of one recorded token; ``neutral`` when it is not recognised."""
    if not isinstance(token, str) or not token:
        return "neutral"
    return tone(family(token.strip().upper()))


def status_item(path: str, raw: str) -> dict | None:
    toks = leading_tokens(raw)
    if not toks:
        return None
    fams = [family(t) for t in toks]
    return {"path": path, "raw": raw[:400], "tokens": toks, "families": fams,
            "tones": [tone(f) for f in fams]}


def walk(obj: Any, prefix: str = "", depth: int = 0, max_depth: int = 7) -> Iterator[tuple[str, Any]]:
    """``(dotted.path, value)`` for every scalar in a JSON document, bounded."""
    if depth > max_depth:
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, (dict, list)):
                yield from walk(value, path, depth + 1, max_depth)
            else:
                yield path, value
    elif isinstance(obj, list):
        for i, value in enumerate(obj[:500]):
            path = f"{prefix}[{i}]"
            if isinstance(value, (dict, list)):
                yield from walk(value, path, depth + 1, max_depth)
            else:
                yield path, value


def get_path(obj: Any, dotted: str) -> Any:
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def all_statuses(doc: Any, limit: int = 300) -> list[dict]:
    """Every status statement in a document, with the path it came from."""
    out = []
    for path, value in walk(doc):
        if not isinstance(value, str):
            continue
        key = re.sub(r"\[\d+\]$", "", path.rsplit(".", 1)[-1])
        if key in STATUS_KEYS or key.endswith("_status") or key.endswith("_verdict"):
            item = status_item(path, value)
            if item:
                out.append(item)
                if len(out) >= limit:
                    break
    return out


def headline_statuses(doc: Any) -> list[dict]:
    """The record's own top-level status statements, in a fixed order."""
    out = []
    if not isinstance(doc, dict):
        return out
    for path in HEADLINE_PATHS:
        value = get_path(doc, path)
        if isinstance(value, str):
            item = status_item(path, value)
            if item:
                out.append(item)
    return out


# ------------------------------------------------------------------ basis

def _any(doc: Any, pred) -> str | None:
    for path, value in walk(doc):
        if pred(path.rsplit(".", 1)[-1], value):
            return path
    return None


def _has_key(doc: Any, names: set[str], max_depth: int = 3) -> str | None:
    def rec(obj, prefix, depth):
        if depth > max_depth or not isinstance(obj, dict):
            return None
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if key in names:
                return path
            if isinstance(value, dict):
                hit = rec(value, path, depth + 1)
                if hit:
                    return hit
        return None
    return rec(doc, "", 0)


def classify_record(record_id: str, docs: dict[str, Any], files: list[str]) -> dict:
    """Evidence basis of a results/ record: ``{basis, rule, reason}``.

    ``docs`` maps file name to parsed JSON for the record's top-level and
    candidate JSON files; ``files`` lists its repository-relative paths."""
    def verdict(rule_id: str, reason: str) -> dict:
        rule = next(r for r in RECORD_RULES if r["id"] == rule_id)
        return {"basis": rule["basis"], "rule": rule_id, "reason": reason}

    if "SYNTHETIC" in record_id.upper():
        return verdict("R1", f"identifier {record_id} contains SYNTHETIC")

    for name, doc in docs.items():
        hit = _any(doc, lambda k, v: (k in ("synthetic", "synthetic_only") and v is True)
                   or (k in ("classification", "evidence_class") and v == "TEST_FIXTURE"))
        if hit:
            return verdict("R2", f"{name}: {hit}")
        hit = _has_key(doc, {"not_qmhp"})
        if hit:
            return verdict("R2", f"{name}: {hit} present")

    for name, doc in docs.items():
        hit = _any(doc, lambda k, v: k in ("evidence_class", "classification", "evidence_basis")
                   and v == "MEASURED")
        if hit:
            return verdict("R3", f"{name}: {hit} = MEASURED")

    for name, doc in docs.items():
        if not isinstance(doc, dict):
            continue
        if doc.get("palace_launched") is False:
            return verdict("R4", f"{name}: palace_launched = false")
        kind = doc.get("kind")
        if isinstance(kind, str) and "correct" in kind.lower():
            return verdict("R4", f"{name}: kind = {kind}")
        if "dry_run_mode" in doc:
            return verdict("R4", f"{name}: dry_run_mode present (admission / dry-run record)")

    for name, doc in docs.items():
        hit = _has_key(doc, {"solver_provenance", "palace_status", "solver_identity",
                             "image_id", "eigenmodes_GHz"}, max_depth=4)
        if hit:
            return verdict("R5", f"{name}: {hit} present")
        hit = _any(doc, lambda k, v: k == "evidence_class" and v == "SOLVED")
        if hit:
            return verdict("R5", f"{name}: {hit} = SOLVED")
    solver_file = next((f for f in files if "/solver/" in f), None)
    if solver_file:
        return verdict("R5", f"solver output present: {solver_file}")

    approval = next((n for n, d in docs.items() if isinstance(d, dict) and "approval_sha256" in d), None)
    resources = next((n for n, d in docs.items() if isinstance(d, dict) and "resources" in d), None)
    if approval and resources:
        return verdict("R6", f"{approval}: approval_sha256; {resources}: resources")

    return verdict("R0", "no rule matched")


def synthetic_files(docs: dict[str, Any]) -> list[dict]:
    """Files that declare themselves synthetic, with the key that says so."""
    out = []
    for fname, doc in docs.items():
        hit = (_any(doc, lambda k, v: k in ("synthetic", "synthetic_only") and v is True)
               or _has_key(doc, {"not_qmhp", "synthetic_only"}))
        if hit:
            out.append({"file": fname, "path": hit})
    return out


def classify_experiment(name: str, docs: dict[str, Any]) -> dict:
    if "SYNTHETIC" in name.upper():
        return {"basis": "SYNTHETIC", "rule": "E1", "reason": f"directory name {name}"}
    return {"basis": "DECLARATION", "rule": "E2",
            "reason": "experiment directory; its executed evidence is in linked results/ records"}
