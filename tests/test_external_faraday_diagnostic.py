"""The preserved external Faraday diagnostic: intact, labelled, corrections verified, decision doc present."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXT = REPO_ROOT / "experiments" / "readout-voltage-functional" / "external-faraday"
SUPPLIED = EXT / "supplied"
DOCS = REPO_ROOT / "docs" / "coupled-candidate"


def test_supplied_package_matches_its_manifest():
    for line in (SUPPLIED / "manifest.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((SUPPLIED / name).read_bytes()).hexdigest() == digest, name
    assert (EXT / "supplied-archive.sha256").read_text().split()[0] == "08d160d2f32c443ccb6881f4e0c99ddb84b0a586b7766739459cfd676ed3e7cc"


def test_local_checks_of_the_two_corrections_pass():
    review = json.loads((EXT / "review.json").read_text())
    assert review["label"].startswith("DERIVED-FROM-EXTERNAL")
    assert review["all_pass"] is True
    c = review["checks"]
    assert c["loop_signed_area_mm2_at_x_-0.45"] < 0                # clockwise from +z: +i omega Phi_z
    assert c["P_F1_face_inside_A_west"] is True                     # attribute 10 belongs to the flux surface
    assert abs(c["A_west_area_mm2_from_geometry"] - 0.0284) < 1e-12
    for row in c["comparisons"].values():
        assert row["measured_equals_readout_diagnostic_difference_abs"] == 0.0
        assert row["relative_complex_disagreement_recomputed"] < 2e-5
        assert 0.04 <= row["attribute10_fraction_reported"] <= 0.056


def test_external_results_are_not_claimed_as_reproduced_and_do_not_carry_g():
    results = json.loads((SUPPLIED / "evaluation" / "results.json").read_text())
    assert results["classification"].startswith("OFFLINE POSTPROCESSING DIAGNOSTIC")
    text = json.dumps(results).lower()
    assert "g_f1r1" not in text and "coupling_ghz" not in text
    readme = (EXT / "README.md").read_text()
    assert "EXTERNALLY PRODUCED" in readme and "not reproduced here" in readme


def test_predeclaration_and_review_carry_the_corrections_and_the_decision_doc_exists():
    pre = (REPO_ROOT / "experiments" / "readout-voltage-functional" / "faraday_test_predeclaration.md").read_text()
    assert "clockwise viewed from +z" in pre and "+iω Φ_z" in pre and "attribute 10" in pre
    rev = (DOCS / "readout-surface-difference-review.md").read_text()
    assert "Outcome and corrections" in rev
    assert (DOCS / "r1-definition-decision.md").is_file()
