"""The preserved external readout-field diagnostic: intact, labelled, consistent, and no archive in Git."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE = REPO_ROOT / "experiments" / "readout-voltage-functional"
EXT = BASE / "external-diagnostic"
SUPPLIED = EXT / "supplied"


def test_supplied_package_matches_its_manifest():
    for line in (SUPPLIED / "manifest.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((SUPPLIED / name).read_bytes()).hexdigest() == digest, name
    assert (EXT / "supplied-archive.sha256").read_text().split()[0] == "4408146e016aa5079ab4fada7cc509fdc006342ea43071c6c65be671ec21f97e"


def test_external_results_are_labelled_and_not_claimed_as_reproduced():
    prov = json.loads((EXT / "provenance.json").read_text())
    assert "EXTERNALLY PRODUCED" in prov["label"]
    for arc in prov["field_archives"].values():
        if isinstance(arc, dict):
            assert arc["present_in_analysis_environment"] is False
    review = json.loads((EXT / "review.json").read_text())
    assert review["label"].startswith("DERIVED-FROM-EXTERNAL")
    assert review["all_consistency_checks_pass"] is True
    results = json.loads((SUPPLIED / "evaluation" / "results.json").read_text())
    assert results["classification"].startswith("OFFLINE POSTPROCESSING DIAGNOSTIC")


def test_script_pins_match_the_repository_and_the_functional():
    text = (SUPPLIED / "evaluate_readout_fields.py").read_text()
    pin = "5bc50d01e7c4578feb7df532b3b31956f6cefac1"
    assert pin in text
    for path, blob in (
        ("experiments/readout-voltage-functional/functional.json", "4a605e89513236695a17a66f261003bec6b6abc8"),
        ("results/COUPLED-LADDER-O1-L2-N1R-20260919T110053Z/L2/solver/postpro/port-V.csv", "12286f083959af9491c94be42d3496303d76f770"),
        ("results/COUPLED-LADDER-O1-L2-N2R-20260918T061455Z/L2/solver/postpro/port-V.csv", "a16a65f0a5f1b93eb55e72aed0a376ff229f9642"),
    ):
        assert blob in text
        got = subprocess.run(["git", "rev-parse", f"{pin}:{path}"], capture_output=True, text=True, cwd=REPO_ROOT)
        if got.returncode != 0:
            pytest.skip("pinned commit not available in this checkout")
        assert got.stdout.strip() == blob, path
    f = json.loads((BASE / "functional.json").read_text())
    s = f["readout_functional"]["surfaces"]
    assert "'plusY':(-.485,-.405,.05,.08,-1)" in text and s["Gamma_R_plusY"]["x"] == [-0.485, -0.405] and s["Gamma_R_plusY"]["y"] == [0.05, 0.08]
    assert "'minusY':(-.485,-.405,-.08,-.05,1)" in text and s["Gamma_R_minusY"]["y"] == [-0.08, -0.05]
    assert "SQRT_Z0=19.409541814844687" in text and f["palace_dimensionalisation"]["sqrt_Z0"] == 19.409541814844687
    assert "LAMBDA=4.0" in text


def test_review_preserves_signs_and_both_surfaces():
    review = json.loads((EXT / "review.json").read_text())
    for rec in review["records"].values():
        rp, rm = rec["r12_plusY_primary"], rec["r12_minusY_mirror"]
        assert rp[0] < 0 and rm[0] < 0                      # signs retained, not magnitudes
        assert rp != rm                                      # no averaging or substitution
        assert 0.13 < rec["r12_mirror_rel_diff"] < 0.14
        m1, m2 = rec["modes"]["1"], rec["modes"]["2"]
        assert m1["difference_rel_to_V_R_mirror_metric"] > 0.13
        assert m2["difference_rel_to_V_R_mirror_metric"] < 0.002
    for side in ("plusY", "minusY"):
        assert 0.015 < review["between_meshes"][side]["relative_change"] < 0.02


def test_no_field_archive_is_tracked():
    tracked = subprocess.run(["git", "ls-files", "experiments", "results", "docs"], capture_output=True, text=True, cwd=REPO_ROOT).stdout.split()
    assert not [p for p in tracked if "_fields_" in p and p.endswith(".zip")]
    ignore = (REPO_ROOT / ".gitignore").read_text()
    assert "*_fields_*.zip" in ignore
