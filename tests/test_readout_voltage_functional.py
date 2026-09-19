"""The readout-voltage functional record: derived from the declaration, mesh-checked, no value evaluated."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORD = REPO_ROOT / "experiments" / "readout-voltage-functional"
DOC = REPO_ROOT / "docs" / "coupled-candidate" / "readout-voltage-functional.md"


def _finite(obj, path="value"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            _finite(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _finite(v, f"{path}[{i}]")
    elif isinstance(obj, float):
        assert math.isfinite(obj), path


def test_record_files_exist_and_are_finite():
    for name in ("README.md", "functional.json", "artefacts.json", "mesh_feasibility.py", "mesh_feasibility.json"):
        assert (RECORD / name).is_file(), name
    for name in ("functional.json", "artefacts.json", "mesh_feasibility.json"):
        _finite(json.loads((RECORD / name).read_text()))
    assert DOC.is_file()


def test_functional_follows_from_the_registered_geometry():
    from solvers.palace.coupled_geometry import chip_cell_from_declaration

    decl = json.loads((REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json").read_text())
    cell = chip_cell_from_declaration(decl)
    pad = cell.conductors["R1.coupling_pad"][0]
    pad_etch, island_etch = cell.etch[1], cell.etch[0]
    f = json.loads((RECORD / "functional.json").read_text())
    surfaces = f["readout_functional"]["surfaces"]
    plus, minus = surfaces["Gamma_R_plusY"], surfaces["Gamma_R_minusY"]
    # x range: the part of the pad edge that faces ground across the declared gap
    assert plus["x"] == [max(pad.x_min, island_etch.x_max), pad.x_max] == minus["x"]
    # y ranges: from the pad edge to the etch boundary, i.e. exactly the declared 0.030 mm gap
    assert plus["y"] == [pad.y_max, pad_etch.y_max]
    assert minus["y"] == [pad_etch.y_min, pad.y_min]
    gap = cell.declared_gaps_mm["R1.coupling_pad.gap_to_ground_mm"]
    assert plus["y"][1] - plus["y"][0] == pytest.approx(gap)
    assert minus["y"][1] - minus["y"][0] == pytest.approx(gap)
    # orientation: from ground into the pad, the P_F1 convention
    assert plus["l_hat"] == [0, -1, 0] and minus["l_hat"] == [0, 1, 0]
    assert f["readout_functional"]["width_normalisation_mm"] == pytest.approx(pad.x_max - max(pad.x_min, island_etch.x_max))
    # Palace's constants and the length scale of this mesh
    mu0, eps0 = 4.0e-7 * math.pi, 8.8541878176e-12
    assert f["palace_dimensionalisation"]["sqrt_Z0"] == pytest.approx(math.sqrt(math.sqrt(mu0 / eps0)), rel=1e-12)
    assert f["palace_dimensionalisation"]["lambda_Lc_over_L0_in_mesh_units"] == 4.0
    assert "NOT EVALUATED" in f["diagnostics_if_evaluated"]["status"]


def test_mesh_feasibility_supports_the_surfaces():
    m = json.loads((RECORD / "mesh_feasibility.json").read_text())
    assert m["port_F1"]["area_mm2"] == pytest.approx(0.02 * 0.04, rel=1e-9)
    assert m["port_F1"]["z_max_abs"] == 0.0
    assert m["bounding_box_mm"]["Lc_mm_palace_default"] == 4.0
    for name in ("Gamma_R_plusY", "Gamma_R_minusY"):
        r = m["readout_rectangles"][name]
        assert r["faces"] > 0 and r["all_faces_etched"] and r["pec_faces_inside"] == 0
        assert r["pad_side_strip_faces_pec"] == r["pad_side_strip_faces_total"] > 0
        assert r["ground_side_strip_faces_pec"] == r["ground_side_strip_faces_total"] > 0
        assert r["corner_region_x[-0.505,-0.485]_beyond_gap"]["pec"] == 0
        assert r["distinct_node_y_levels_in_gap"] >= 3
    assert m["island_pad_gap"]["pec"] == 0
    assert m["refinement_box_vs_readout_rectangles"]["overlaps_Gamma_R"] is False


def test_artefacts_are_identified_but_not_retrieved():
    a = json.loads((RECORD / "artefacts.json").read_text())
    by = {x["record"]: x for x in a["artefacts"]}
    assert by["N1R"]["artifact_id"] == 10583481701 and by["N1R"]["run_id"] == 35438882836
    assert by["N2R"]["artifact_id"] == 10533683685 and by["N2R"]["run_id"] == 35313973073
    for x in a["artefacts"]:
        assert x["api_digest"] == "sha256:" + x["user_supplied_sha256"]
    assert a["retrieval"]["bytes_retrieved"] is False
    assert a["retrieval"]["content_digest_recomputed"] is False
    # no value made it into the record
    text = DOC.read_text()
    assert "No field value was evaluated" in text
