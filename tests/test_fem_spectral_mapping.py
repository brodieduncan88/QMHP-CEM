"""The FEM-to-spectral compatibility record: labelled conditional, corrected, and not promoted."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REC = REPO_ROOT / "experiments" / "fem-spectral-mapping"
DOC = REPO_ROOT / "docs" / "coupled-candidate" / "fem-spectral-mapping.md"
DECISION = REPO_ROOT / "docs" / "coupled-candidate" / "r1-definition-decision.md"


def _norm(text: str) -> str:
    """Collapse whitespace and strip blockquote markers, so prose assertions
    do not depend on line wrapping or on a passage being inside a blockquote."""
    lines = [ln.lstrip().removeprefix("> ").removeprefix(">") for ln in text.splitlines()]
    return " ".join(" ".join(lines).split())


@pytest.fixture(scope="module")
def result():
    return json.loads((REC / "spectral_compatibility.json").read_text())


@pytest.fixture(scope="module")
def checks():
    return json.loads((REC / "review_checks_reconstructed.json").read_text())


def test_every_number_is_labelled_conditional_and_not_route_a(result):
    assert result["label"] == "CONDITIONAL SPECTRAL CALCULATION - EM MAPPING UNVERIFIED"
    joined = " ".join(result["not"])
    for claim in ("not a Route A result", "not VERIFIED-COMPUTATIONAL coupling evidence", "not gate input"):
        assert claim in joined
    assert "participations never renormalised" in joined
    assert DOC.is_file() and "CONDITIONAL" in DOC.read_text()
    assert "are not Route A evidence" in _norm(DOC.read_text())


def test_both_records_are_read_whole_and_n2r_is_not_truncated(result):
    assert result["records"]["N1R"]["saved_eigenpairs"] == 6
    assert result["records"]["N2R"]["saved_eigenpairs"] == 9
    for rec in result["records"].values():
        for variant in rec["spectral_variants"].values():
            covered = set(variant["included_modes"]) | {e["m"] for e in variant["excluded_modes"]}
            assert covered == {mo["m"] for mo in rec["modes"]}, "every mode included or excluded with a reason"
            for e in variant["excluded_modes"]:
                assert "equipartition defect" in e["reason"]


def test_the_rank_one_premise_is_refuted_by_the_committed_records(result):
    for name, rec in result["records"].items():
        t = rec["rank_one_premise_test"]
        # if K_port were f f^T / L, p_assembled would equal |p| for every mode
        assert t["max_abs_difference_over_modes"] > 0.99, name
        assert t["sum_p_assembled_over_saved_modes"] > 4.0, name
        for m, d in t["difference_on_field_resonant_modes"].items():
            assert 0.0 < d < 1e-3, (name, m)


def test_delta_saved_is_reported_without_being_renamed(result):
    for rec in result["records"].values():
        assert rec["delta_saved"] == pytest.approx(1.0 - rec["sum_abs_p_over_saved_modes"], rel=1e-12)
        assert 7e-4 < rec["delta_saved"] < 8e-4
        assert "NOT renamed delta_far" in rec["delta_saved_definition"]
        d = rec["decomposition_of_the_saved_sum"]
        assert sum(d.values()) == pytest.approx(rec["sum_abs_p_over_saved_modes"], rel=1e-12)
    n2 = result["records"]["N2R"]
    assert n2["decomposition_of_the_saved_sum"]["field_resonant_above_declared_band"] > 5e-5
    # neither contribution to delta_saved is claimed as measured
    assert "neither has been measured separately" in _norm(DOC.read_text()).lower()


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
    norm = _norm(DOC.read_text())
    assert "UNAVAILABLE" in norm and "No value is reported" in norm


def test_units_conversion_is_stated(result):
    u = result["units"]["conversion_to_angular_squared"]
    assert "(2*pi*1e9)^2" in u and "(rad/s)^2" in u and "coupling_GHz" in u
    text = DOC.read_text()
    assert "GHz²" in text and "(rad/s)²" in text and "W0 = (2π·10⁹)²" in text


# --- the two claims withdrawn after the 46bf8b5 review ---------------------------------------


def test_the_withdrawn_claims_are_recorded_and_not_restated(result):
    w = result["withdrawn_claims"]
    assert w["rank_implies_N_below_one"].startswith("WITHDRAWN")
    assert "does NOT imply N < 1" in w["rank_implies_N_below_one"]
    assert w["readout_zero_error_bound_2p3e_7"].startswith("WITHDRAWN")
    assert "UNBOUNDED BY THE CURRENT EVIDENCE" in w["readout_zero_error_bound_2p3e_7"]
    norm = _norm(DOC.read_text())
    assert "UNBOUNDED BY THE CURRENT EVIDENCE" in norm
    assert "not a claim that it is large" in norm
    # the withdrawn bound is never restated as live, here or in the draft decision
    assert "bounded at `≲2.3e-7`" not in norm
    assert "bounded at `≲2.3e-7`" not in _norm(DECISION.read_text())


def test_N_is_retained_as_at_most_one_with_the_alignment_equality_condition():
    norm = _norm(DOC.read_text())
    assert "N ≤ 1" in norm
    assert "K_curl u = 0" in norm and "ΔK u = 0" in norm
    assert "not about the rank of the port operator" in norm


def test_the_review_checks_verify(checks):
    assert "did NOT reach this environment" in checks["supplied_file_status"]
    # 1. a port term of rank > 1 with N exactly 1: the rank implication is false
    cases = [c for c in checks["check_1_normalisation_rank_implication"] if "rank_K_port" in c]
    assert cases and all(c["rank_K_port"] > 1 and c["N_equals_one"] and c["K_port_minus_Q_is_PSD"] for c in cases)
    ident = [c for c in checks["check_1_normalisation_rank_implication"] if "max_abs_violation" in c][0]
    assert ident["max_abs_violation"] < 1e-12 and ident["all_N_le_one"]
    # 2. the diagonal participation is not a bound on the finite shift
    c2 = checks["check_2_finite_operator_removal"]
    assert c2["verdict"] == "FALSE"
    assert max(r["ratio_actual_over_diagonal"] for r in c2["rows"]) > 10.0
    assert all(r["K_minus_dK_is_PSD"] for r in c2["rows"])
    # 3. the determinant identity and the Q/N consequence
    c3 = checks["check_3_exact_removal_identity"]
    assert c3["max_identity_rel_error"] < 1e-9
    assert c3["max_rel_distance_zeros_to_K_minus_Q_over_N"] < 1e-9


def test_declared_and_normalised_rank_one_removals_are_both_recorded(result):
    for name, rec in result["records"].items():
        for v, ent in rec["spectral_variants"].items():
            q = ent["rank_one_removal_Q_versus_Q_over_N"]
            assert q["identity"] == "det(zM - K + Q)/det(zM - K) = z G(z) + 1 - N"
            assert q["readout_root_declared_removal_GHz2"] is not None
            assert q["readout_zero_normalised_removal_GHz2"] is not None
            assert 1e-7 < q["relative_difference_readout"] < 1e-5
            assert q["extra_low_root_GHz2"] > 0.0            # the removal pencil stays PSD
            assert "not bounded by the committed evidence" in q["caveat"]
    norm = _norm(DOC.read_text())
    assert "normalised" in norm and "declared" in norm


def test_the_variant_B_threshold_is_declared_ad_hoc():
    src = (REC / "spectral_compatibility.py").read_text()
    assert "VARIANT_B_DEFECT_THRESHOLD" in src
    assert "chosen after seeing the values" in src and "was wrong" in src
    norm = _norm(DOC.read_text())
    # the old wording may appear only inside the sentence that corrects it
    assert norm.lower().count("no threshold is invented") == 1
    assert 'as "no threshold is invented" was wrong' in norm
    assert "ad-hoc post-hoc threshold" in norm


def test_roots_are_rejected_not_realified():
    src = (REC / "spectral_compatibility.py").read_text()
    assert "ROOT_IMAG_RTOL" in src and "rather than realified" in src
    assert "np.roots(poly).real" not in src       # the old silent realification is gone
    spec = importlib.util.spec_from_file_location("sc", REC / "spectral_compatibility.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with pytest.raises(RuntimeError, match="materially complex"):
        mod._real_roots(np.array([1.0, 0.0, 1.0]), np.array([1.0, 2.0]))     # roots +-i


def test_the_spreads_are_not_presented_as_total_uncertainty():
    norm = _norm(DOC.read_text())
    assert "These spreads are not a total uncertainty" in norm
    assert "not an error bound and not continuum accuracy" in norm


def test_the_next_action_does_not_overclaim():
    norm = _norm(DOC.read_text())
    assert "does not touch the operator mapping" in norm
    assert "must not silently replace the declared probe classification" in norm
    assert "supplementary evidence, not a substitute criterion" in norm


def test_the_draft_decision_document_carries_the_corrections():
    norm = _norm(DECISION.read_text())
    assert "Corrections forced by the transfer-function compatibility check" in norm
    assert "§5 item 2 is withdrawn" in norm
    assert "cavity-height shift-to-uncertainty rule" in norm
    assert "probe-E.csv" in norm
    assert "must not be renamed" in norm and "δ_far" in norm
    assert "withdrawn" in norm.lower()
    assert "UNBOUNDED BY THE CURRENT EVIDENCE" in norm
    assert "remains unapproved" in norm or "remain unapproved" in norm


def test_the_production_inversion_and_its_guards_are_untouched():
    from models import route_a_inversion as m

    assert m.SUM_RULE_RTOL == 1.0e-6 and m.ROOT_SELECTION_RTOL == 1.0e-9
    src = (REPO_ROOT / "models" / "route_a_inversion.py").read_text()
    assert "check_sum_rule: bool = True" in src
    for layer in ("models", "orchestrator", "evaluator", "solvers", "contracts"):
        for path in (REPO_ROOT / layer).rglob("*.py"):
            text = path.read_text()
            assert "spectral_compatibility" not in text, path
            assert "review_checks_reconstructed" not in text, path
