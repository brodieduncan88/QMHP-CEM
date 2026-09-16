"""Guards for the two review fixes.

1. No document, and no field of the declaration, may claim that Route A (or
   Route B) identifies ``E_C,F1R1``, ``E_C,R1R1`` or ``E_L,R1`` as a
   convention-independent physical output. Every statement of the extraction
   target must be the corrected invariant triple
   ``{E_C,F1F1, f_R1, g_F1R1}``.

2. The bounded pilot must be unambiguous: three solves, their orders and
   halos, the 45-minute cap, no external compute, and a predeclared numerical
   criterion for the P1/P3 halo comparison whose numbers come from rules that
   already exist rather than from a new physical threshold.

These are documentation and declaration guards. They assert nothing about
physics and they launch nothing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from contracts.coupled_candidate import load_declaration, load_register

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs" / "coupled-candidate"
DECLARATION = REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json"
REGISTER = REPO_ROOT / "config" / "coupled" / "source_register.json"
PROPOSAL = DOCS / "execution-proposal.md"

#: Every prose file that states or restates the extraction target.
TARGET_DOCS = [
    DOCS / "README.md",
    DOCS / "coupling-definition.md",
    DOCS / "extraction-routes.md",
    DOCS / "numerical-plan.md",
    DOCS / "implementation-plan.md",
    DOCS / "route-a-identifiability.md",
]

#: Phrasings that would assert a readout-node entry is an output. Each is
#: matched case-insensitively against the whole file with its surrounding
#: sentence, so a correction that *names* the entry in order to deny it does
#: not trip the guard; the guard is on the claim, not the symbol.
STALE_CLAIM_PATTERNS = [
    r"\(E_C,RR,\s*E_L,R\)\s*(?:of each readout node\s*)?is an output",
    r"output is again[^.]*E_C,RR",
    r"E_C,F1R1[^.]*\(E_C,R1R1,\s*E_L,R1\)\s*and hence",
    r"routes estimate the same object:\s*the off-diagonal charging-energy",
    r"bare linear-mode parameters\s*`?\(E_C,RR,\s*E_L,R\)`?\s*of\s*each readout node[^.]*convention-free",
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Collapse whitespace and blockquote markers.

    A guard should be on the wording, not on how markdown wrapped it or on
    whether the sentence happens to sit inside a blockquote.
    """
    without_quotes = re.sub(r"(?m)^\s*>\s?", "", text)
    return re.sub(r"\s+", " ", without_quotes)


# --- fix 1: the corrected invariant target -----------------------------------


@pytest.mark.parametrize("path", TARGET_DOCS, ids=lambda p: p.name)
def test_no_document_claims_a_readout_node_entry_is_an_output(path):
    text = _text(path)
    for pattern in STALE_CLAIM_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        assert match is None, (
            f"{path.name} still claims a readout-node entry is an output: "
            f"{match.group(0)[:160]!r}"
        )


def test_the_definition_states_the_invariant_triple_as_the_target():
    text = _text(DOCS / "coupling-definition.md")
    assert "gauge-invariant triple" in text
    assert "{E_C,F1F1, f_R1, g_F1R1}" in text
    # And it carries the explicit correction rather than silently rewriting.
    assert "Correction (checkpoint A, after review)" in text
    assert "false" in text.lower() and "readout node" in text


def test_both_routes_are_documented_as_returning_the_same_invariants():
    text = _text(DOCS / "extraction-routes.md")
    assert "Route B's output is the same invariant triple as Route A's" in text
    # Route B's own gauge argument must be present, not merely asserted.
    assert "rescaling the" in text and "leaves every fitted" in text
    assert "| Output | the invariant triple" in text


def test_the_identifiability_document_carries_the_witness_and_the_derivation():
    text = _text(DOCS / "route-a-identifiability.md")
    assert "not identifiable" in text
    assert "no `L_R` at all" in text or "in which `L_R` has cancelled" in text
    for quantity in ("E_C,FR", "E_C,RR", "L_R"):
        assert quantity in text


def test_the_declaration_declares_the_invariant_target_and_what_is_not_identifiable():
    declaration = load_declaration(DECLARATION, register=load_register(REGISTER))
    scope = declaration.executable_scope

    assert declaration.extraction.target is not None
    assert declaration.extraction.target.invariant_triple == [
        "E_C_F1F1_GHz", "f_R1_GHz", "g_F1R1_GHz"
    ]

    assert scope.not_identifiable is not None
    for quantity in ("E_C,F1R1", "E_C,R1R1", "E_L,R1"):
        assert quantity in scope.not_identifiable.quantities
    assert "never an output" in scope.not_identifiable.treatment

    # The claim string must not promise the unidentifiable entries.
    assert "invariant triple" in scope.claims
    for quantity in ("E_C,F1R1", "E_C,R1R1", "E_L,R1"):
        assert quantity not in scope.claims

    # Every suitability quantity is invariant, and E_L,R1 is not among them.
    assert {q.id for q in scope.suitability_quantities} == {
        "E_C_F1F1_GHz", "bare_readout_GHz", "g_F1R1_GHz"
    }
    assert all(q.invariant for q in scope.suitability_quantities)


def test_a_non_invariant_suitability_quantity_is_rejected():
    raw = json.loads(DECLARATION.read_text())
    raw["executable_scope"]["suitability_quantities"].append({
        "id": "E_L_R1_GHz", "source_value": 88.4, "invariant": False,
        "binding": {"class": "ENGINEERING-SEED", "approved": False, "rationale": "x"},
    })
    with pytest.raises(ValueError, match="not gauge-invariant"):
        load_declaration_from_dict(raw)


def load_declaration_from_dict(raw: dict):
    from contracts.coupled_candidate import CoupledCandidateDeclaration

    return CoupledCandidateDeclaration.model_validate(raw)


# --- fix 2: the pilot is unambiguous -----------------------------------------


def test_the_pilot_declares_exactly_three_solves_with_their_orders_and_halos():
    text = _text(PROPOSAL)
    assert "The bounded pilot: three solves" in text
    rows = re.findall(r"\|\s*\*\*(P[123])\*\*\s*\|\s*(\d)\s*\|\s*([0-9.]+) mm\s*\|", text)
    assert rows == [("P1", "2", "0.08"), ("P2", "1", "0.08"), ("P3", "2", "0.15")], rows


def test_the_pilot_states_its_cap_and_that_no_external_compute_is_used():
    text = _text(PROPOSAL)
    assert "capped at **45 minutes**" in text
    assert "No external or additional compute is used" in _flat(text)
    assert "no new allowance and no external" in _flat(text)


def test_the_pilot_surfaces_that_P3_exceeds_the_declared_dof_budget():
    text = _text(PROPOSAL)
    assert "281 332" in text
    assert "above the declared 250 000 DOF" in _flat(text)
    assert "this proposal does not relax it" in _flat(text)
    # And offers the measured in-budget alternatives rather than only the breach.
    assert "0.12 mm" in text and "235 806" in text


def test_the_halo_criterion_is_predeclared_with_both_checks():
    text = _text(PROPOSAL)
    assert "The predeclared numerical criterion for the halo" in text
    body = text[text.index("### 4.2"):text.index("### 4.3")]
    assert "Δp ≤ 1e-2" in body and "Δf ≤ 1e-4" in body
    # Its provenance: both numbers come from rules that already exist.
    assert "existing frequency convergence rule" in body
    assert "roughly one-for-one" in body
    # It is explicitly a numerical rule, not a physical threshold.
    assert "not a physical QMHP threshold" in body
    assert "leaves the 10 % agreement rule untouched" in body


def test_the_halo_criterion_propagates_rather_than_only_passing():
    body = _text(PROPOSAL)
    body = body[body.index("### 4.2"):body.index("### 4.3")]
    assert "systematic" in body and "resolution floor" in body
    assert "taking the maximum" in body
    # All three outcomes are written down in advance.
    for outcome in ("Both checks pass", "The participation check fails",
                    "The frequency check fails"):
        assert outcome in body
    # A failure is not rescued by loosening the rule.
    assert "not rescued by loosening the criterion" in _flat(body)


def test_the_element_order_rule_is_predeclared_too():
    text = _text(PROPOSAL)
    body = text[text.index("### 4.3"):text.index("## 5.")]
    assert "P1 completes inside its 45 minute cap" in body
    assert "order 2 is selected" in body
    assert "returns to the review" in body


def test_the_decision_request_matches_the_three_solve_pilot():
    text = _text(PROPOSAL)
    body = text[text.index("## 6. Decision requested"):]
    assert "three-solve" in body
    assert "P1 order 2" in body and "P2 order 1" in body and "P3 order 2" in body
    assert "0.15 mm" in body and "0.12 mm" in body
    assert "are predeclared here and are not revisited" in _flat(body)


def test_nothing_in_the_proposal_relaxes_a_frozen_rule():
    flat = _flat(_text(PROPOSAL))
    assert "the 10 % agreement ENGINEERING-RULE is untouched" in flat
    assert "No seed is promoted" in flat
    # The DOF rule is named as predeclared and explicitly not relaxed.
    assert "predeclared ENGINEERING-RULE and this proposal does not relax it" in flat
