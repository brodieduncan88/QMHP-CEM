"""The FEM-to-spectral compatibility record: labelled conditional, complete, and not promoted."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REC = REPO_ROOT / "experiments" / "fem-spectral-mapping"
DOC = REPO_ROOT / "docs" / "coupled-candidate" / "fem-spectral-mapping.md"
DECISION = REPO_ROOT / "docs" / "coupled-candidate" / "r1-definition-decision.md"


@pytest.fixture(scope="module")
def result():
    return json.loads((REC / "spectral_compatibility.json").read_text())


def test_every_number_is_labelled_conditional_and_not_route_a(result):
    assert result["label"] == "CONDITIONAL SPECTRAL CALCULATION - EM MAPPING UNVERIFIED"
    joined = " ".join(result["not"])
    for claim in ("not a Route A result", "not VERIFIED-COMPUTATIONAL coupling evidence", "not gate input"):
        assert claim in joined
    assert "participations never renormalised" in joined
    assert DOC.is_file() and "CONDITIONAL" in DOC.read_text()


def test_both_records_are_read_whole_and_n2r_is_not_truncated(result):
    assert result["records"]["N1R"]["saved_eigenpairs"] == 6
    assert result["records"]["N2R"]["saved_eigenpairs"] == 9
    for rec in result["records"].values():
        for variant in rec["spectral_variants"].values():
            covered = set(variant["included_modes"]) | {e["m"] for e in variant["excluded_modes"]}
            assert covered == {mo["m"] for mo in rec["modes"]}, "every mode must be included or excluded with a reason"
            for e in variant["excluded_modes"]:
                assert "equipartition defect" in e["reason"]


def test_the_rank_one_premise_is_refuted_by_the_committed_records(result):
    for name, rec in result["records"].items():
        t = rec["rank_one_premise_test"]
        # if K_port were f f^T / L, p_assembled would equal |p| for every mode
        assert t["max_abs_difference_over_modes"] > 0.99, name
        # and the assembled-operator participation would sum to about 1, not to 5 or 6
        assert t["sum_p_assembled_over_saved_modes"] > 4.0, name
        # on the field-resonant modes the gap is small and positive (non-uniformity only)
        for m, d in t["difference_on_field_resonant_modes"].items():
            assert 0.0 < d < 1e-3, (name, m)


def test_delta_saved_is_reported_without_being_renamed(result):
    for rec in result["records"].values():
        assert rec["delta_saved"] == pytest.approx(1.0 - rec["sum_abs_p_over_saved_modes"], rel=1e-12)
        assert 7e-4 < rec["delta_saved"] < 8e-4
        assert "NOT renamed delta_far" in rec["delta_saved_definition"]
        d = rec["decomposition_of_the_saved_sum"]
        assert sum(d.values()) == pytest.approx(rec["sum_abs_p_over_saved_modes"], rel=1e-12)
    # N2R found genuine modes above the declared band, and they do not account for the deficit
    n2 = result["records"]["N2R"]
    assert n2["decomposition_of_the_saved_sum"]["field_resonant_above_declared_band"] > 5e-5
    assert n2["delta_saved"] > 10 * n2["decomposition_of_the_saved_sum"]["field_resonant_above_declared_band"] / 2


def test_far_mode_sensitivity_is_marked_conditional_and_separate(result):
    for rec in result["records"].values():
        s = rec["conditional_far_mode_sensitivity"]
        assert "assumes, without evidence" in s["condition"]
        assert s["delta_saved_placed"] == pytest.approx(rec["delta_saved"], rel=1e-12)
        moved = [r for r in s["rows"] if r["f_far_GHz"] is not None]
        assert moved and all(r["shift_g_rel"] < 1e-2 for r in moved)
        assert max(r["shift_a_over_N_rel"] for r in moved) > 0.04   # a, and so E_C, is not bounded


def test_E_C_is_not_reported_as_a_value(result):
    assert result["E_C_F1F1"]["status"] == "UNAVAILABLE"
    spread = result["E_C_F1F1"]["a_over_N_spread_GHz2"]
    assert len(spread) == 8 and all(math.isfinite(v) for v in spread.values())
    text = DOC.read_text()
    assert "UNAVAILABLE" in text and "No value is\nreported" in text


def test_units_conversion_is_stated(result):
    u = result["units"]["conversion_to_angular_squared"]
    assert "(2*pi*1e9)^2" in u and "(rad/s)^2" in u and "coupling_GHz" in u
    text = DOC.read_text()
    assert "GHz²" in text and "(rad/s)²" in text and "W0 = (2π·10⁹)²" in text


def test_the_draft_decision_document_carries_the_four_corrections():
    text = DECISION.read_text()
    assert "Corrections forced by the transfer-function compatibility check" in text
    assert "§5 item 2 is withdrawn" in text
    assert "cavity-height shift-to-uncertainty rule" in text
    assert "probe-E.csv" in text
    assert "must not be renamed `δ_far`" in text
    assert "rank-one surrogate" in text
    # and it is still a draft
    assert "remains unapproved" in text or "remain unapproved" in text


def test_the_production_inversion_and_its_guards_are_untouched():
    from models import route_a_inversion as m

    assert m.SUM_RULE_RTOL == 1.0e-6 and m.ROOT_SELECTION_RTOL == 1.0e-9
    src = (REPO_ROOT / "models" / "route_a_inversion.py").read_text()
    assert "check_sum_rule: bool = True" in src
    for layer in ("models", "orchestrator", "evaluator", "solvers", "contracts"):
        for path in (REPO_ROOT / layer).rglob("*.py"):
            assert "spectral_compatibility" not in path.read_text(), path
