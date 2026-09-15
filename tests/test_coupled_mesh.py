"""Coupled chip-cell geometry and mesh dry run (checkpoint A).

Pure-Python geometry tests always run. The gmsh tests skip cleanly when gmsh
is not importable (same idiom as tests/test_palace.py). The last test runs
the real dry run of the committed S1 declaration at ``h0`` under a 600 s
wall-clock limit and is marked ``slow``; its numbers are what the checkpoint
disposition is decided on, so it prints them rather than asserting a budget.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from solvers.palace import coupled_mesh as cmesh
from solvers.palace import mesh as pmesh
from solvers.palace.coupled_geometry import (
    MEANDER_FIRST_STRAIGHT_MM,
    ChipCell,
    Rect,
    centreline_length_mm,
    chip_cell_from_declaration,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DECLARATION = REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json"

needs_gmsh = pytest.mark.skipif(not pmesh.gmsh_available(), reason="gmsh not importable")


def _declaration() -> dict:
    return json.loads(DECLARATION.read_text())


def _feature(decl: dict, fid: str) -> dict:
    return next(f for f in decl["geometry"]["features"] if f["id"] == fid)


def _small_declaration() -> dict:
    """A 1.4 x 1.1 mm synthetic cell: 0.15 mm island, 1.2 mm resonator.

    Software-test geometry only (``synthetic``): it keeps the committed
    gaps, CPW cross-section and vertical stack, and shrinks the lateral cell
    and the meander so a full 3D dry run takes seconds.
    """
    decl = _declaration()
    decl["geometry"]["cell"].update({"x_min_mm": -0.7, "x_max_mm": 0.7, "y_min_mm": -0.55, "y_max_mm": 0.55})
    _feature(decl, "F1.island")["centre_mm"] = [-0.3, 0.0, 0.0]
    _feature(decl, "F1.element_site")["centre_mm"] = [-0.3, -0.095, 0.0]
    _feature(decl, "R1.coupling_pad")["centre_mm"] = [-0.155, 0.0, 0.0]
    cpw = _feature(decl, "R1.cpw")
    cpw["total_length_mm"] = 1.2
    cpw["path"] = (
        "from R1.coupling_pad along +X, then a meander of 0.5 mm legs along Y with "
        "0.15 mm pitch inside x in [0.10, 0.60], y in [-0.35, 0.35], ending in a short to ground"
    )
    decl["geometry"]["clearances_mm"] = {"island_to_cell_wall_min": 0.125, "meander_to_cell_wall_min": 0.10}
    decl["geometry"]["cell"]["binding"]["lateral_4mm"]["rationale"] = (
        "synthetic software-test cell; not the declared S1 geometry"
    )
    for port in decl["ports"]:
        if port["id"] == "P_F1":
            port["centre_mm"] = [-0.3, -0.095, 0.0]
    return decl


@pytest.fixture
def s1() -> ChipCell:
    return chip_cell_from_declaration(_declaration())


@pytest.fixture
def small() -> ChipCell:
    return chip_cell_from_declaration(_small_declaration())


# --- Rect ---------------------------------------------------------------------


def test_rect_helpers():
    r = Rect(0.0, 0.0, 2.0, 1.0)
    assert (r.x_min, r.x_max, r.y_min, r.y_max) == (-1.0, 1.0, -0.5, 0.5)
    assert r.inflate(0.5) == Rect(0.0, 0.0, 3.0, 2.0)
    assert r.contains(Rect(0.0, 0.0, 2.0, 1.0))          # closed containment
    assert not r.contains(Rect(0.0, 0.0, 2.0, 1.1))
    assert r.overlaps(Rect(0.9, 0.0, 0.4, 0.4))
    assert not r.overlaps(Rect(1.5, 0.0, 1.0, 1.0))      # touching edge is not overlap
    with pytest.raises(ValueError):
        Rect(0.0, 0.0, 0.0, 1.0)


# --- committed S1 geometry -----------------------------------------------------


def test_committed_declaration_builds_with_empty_clearance_report(s1):
    assert s1.clearance_report() == []
    assert set(s1.conductors) == {"F1.island", "R1.coupling_pad", "R1.cpw"}
    assert set(s1.ports) == {"P_F1", "P_R1"}
    assert len(s1.ports["P_F1"]) == 1 and len(s1.ports["P_R1"]) == 2
    assert s1.min_gap_mm == pytest.approx(0.02)
    assert s1.substrate_eps_r == pytest.approx(11.45)
    assert (s1.z_substrate_bottom_mm, s1.z_chip_top_mm, s1.z_lid_mm) == (-0.43, 0.0, 1.5)


def test_meander_centreline_length_equals_declared_total(s1):
    assert abs(centreline_length_mm(s1) - s1.resonator_total_length_mm) < 1e-9
    assert s1.resonator_total_length_mm == 6.983
    first = s1.conductors["R1.cpw"][0]
    pad = s1.conductors["R1.coupling_pad"][0]
    assert first.x_min == pytest.approx(pad.x_max)          # starts at the pad's +X edge
    assert first.w_mm == pytest.approx(MEANDER_FIRST_STRAIGHT_MM + 0.05 / 2.0)


def test_meander_stays_inside_declared_ranges(s1):
    for r in s1.conductors["R1.cpw"][1:]:
        assert -0.30 <= r.x_min and r.x_max <= 1.50
        assert -0.75 <= r.y_min and r.y_max <= 0.75


def test_short_exists_at_the_far_end(s1):
    last = s1.conductors["R1.cpw"][-1]
    assert not any(e.contains(last) for e in s1.etch), "the short bar must reach the ground region"
    leg = s1.conductors["R1.cpw"][-2]
    assert any(e.contains(leg) for e in s1.etch)
    # the bar touches the last leg's end and spans both gaps
    assert last.y_max == pytest.approx(leg.y_min) or last.y_min == pytest.approx(leg.y_max)
    assert last.w_mm == pytest.approx(0.05 + 2 * 0.03)


def test_ports_lie_in_etch_and_off_conductors(s1):
    for pid, rects in s1.ports.items():
        for pr in rects:
            assert any(e.contains(pr) for e in s1.etch), pid
            assert not any(pr.overlaps(c) for c in s1.all_conductor_rects()), pid
    f1 = s1.ports["P_F1"][0]
    island = s1.conductors["F1.island"][0]
    assert f1.y_max == pytest.approx(island.y_min)                  # spans the -Y gap
    assert f1.y_min == pytest.approx(island.y_min - 0.04)
    a, b = s1.ports["P_R1"]
    leg = s1.conductors["R1.cpw"][-2]
    assert a.cy_mm == pytest.approx(b.cy_mm)
    assert abs(a.cy_mm - leg.y_min) == pytest.approx(0.150)         # 0.150 mm before the short
    assert (a.w_mm, a.h_mm) == (0.03, 0.02)
    assert s1.port_directions["P_F1"] == ["+Y"]
    assert s1.port_directions["P_R1"] == ["+X", "-X"]               # perpendicular to a Y leg
    assert any("P_R1 directions realised" in n for n in s1.notes)


def test_preview_is_json_serialisable_and_deterministic(s1):
    a = json.dumps(s1.preview_polygons(), sort_keys=True)
    b = json.dumps(chip_cell_from_declaration(_declaration()).preview_polygons(), sort_keys=True)
    assert a == b
    d = json.loads(a)
    for key in ("cell", "substrate", "conductors", "etch", "ports", "port_directions", "ground_plane_note"):
        assert key in d
    assert d["etched_area_mm2"] > d["conductor_area_mm2"] > 0.0
    assert s1.etched_area_mm2() == pytest.approx(d["etched_area_mm2"], abs=1e-9)


def test_island_at_cell_edge_is_reported():
    decl = _declaration()
    _feature(decl, "F1.island")["centre_mm"] = [-1.95, 0.0, 0.0]
    _feature(decl, "F1.element_site")["centre_mm"] = [-1.95, -0.095, 0.0]
    for port in decl["ports"]:
        if port["id"] == "P_F1":
            port["centre_mm"] = [-1.95, -0.095, 0.0]
    report = chip_cell_from_declaration(decl).clearance_report()
    assert report
    assert any("island_to_cell_wall_min" in line for line in report)


def test_meander_that_cannot_fit_raises():
    decl = _declaration()
    _feature(decl, "R1.cpw")["total_length_mm"] = 60.0
    with pytest.raises(ValueError, match="does not fit"):
        chip_cell_from_declaration(decl)


def test_small_synthetic_cell_is_consistent(small):
    assert small.clearance_report() == []
    assert abs(centreline_length_mm(small) - 1.2) < 1e-9
    assert small.x_size_mm == pytest.approx(1.4) and small.y_size_mm == pytest.approx(1.1)


# --- mesh sizes ---------------------------------------------------------------


def test_mesh_sizes_follow_the_ladder_rule(s1):
    h0, h1, hf1 = cmesh.mesh_sizes_mm(s1, 1)
    assert h0 == pytest.approx(0.01) and h1 == pytest.approx(0.01)
    assert hf1 == pytest.approx(4.0 / 12.0)
    _, h2, hf2 = cmesh.mesh_sizes_mm(s1, 2)
    _, h3, hf3 = cmesh.mesh_sizes_mm(s1, 3)
    assert h2 == pytest.approx(0.01 / 1.5) and h3 == pytest.approx(0.005)
    assert hf2 == pytest.approx(hf1 / 1.5) and hf3 == pytest.approx(hf1 / 2)
    with pytest.raises(ValueError):
        cmesh.mesh_sizes_mm(s1, 4)
    assert cmesh.TAGS == {
        "vacuum": 1, "outer_pec": 2, "substrate": 3, "sheet_pec": 4,
        "port_F1": 10, "port_R1_a": 11, "port_R1_b": 12,
    }


# --- gmsh dry run -------------------------------------------------------------


@needs_gmsh
def test_dry_run_small_cell_level_1(small, tmp_path):
    report = cmesh.dry_run(small, 1, tmp_path)
    assert report.aborted_reason is None
    assert report.tetrahedra > 0 and report.nodes > 0
    assert set(report.tetrahedra_by_tag) == {"vacuum", "substrate"}
    assert set(report.triangles_by_tag) == {"outer_pec", "sheet_pec", "port_F1", "port_R1_a", "port_R1_b"}
    assert all(v > 0 for v in report.tetrahedra_by_tag.values())
    assert all(v > 0 for v in report.triangles_by_tag.values())
    assert sum(report.tetrahedra_by_tag.values()) == report.tetrahedra
    assert report.min_gap_elements == pytest.approx(2.0)
    assert report.dof_estimate_order2 == round(8.2 * report.tetrahedra)
    assert report.dof_estimate_order1 == round(1.2 * report.tetrahedra)
    assert report.mesh_path.exists() and report.mesh_path.suffix == ".msh"
    head = report.mesh_path.read_text().splitlines()[:2]
    assert head[0] == "$MeshFormat" and head[1].startswith("2.2 0")
    d = report.as_dict()
    json.dumps(d)
    assert d["physical_groups"] == cmesh.TAGS
    assert len(d["sha256"]) == 64
    assert d["within_budget_order2"] == (d["dof_estimate_order2"] <= 250_000)


@needs_gmsh
def test_dry_run_is_deterministic(small, tmp_path):
    a = cmesh.dry_run(small, 1, tmp_path / "a")
    b = cmesh.dry_run(small, 1, tmp_path / "b")
    assert a.tetrahedra == b.tetrahedra
    assert a.nodes == b.nodes
    assert a.sha256 == b.sha256


@needs_gmsh
def test_surface_element_guard_aborts_before_3d(small, tmp_path):
    report = cmesh.dry_run(small, 1, tmp_path, max_surface_elements=10)
    assert report.aborted_reason is not None
    assert "above the guard of 10" in report.aborted_reason
    assert str(report.surface_elements_total) in report.aborted_reason
    assert report.tetrahedra == 0
    assert report.within_budget_order2 is False and report.within_budget_order1 is False
    assert report.mesh_path.exists()
    json.dumps(report.as_dict())


_S1_DRY_RUN_SCRIPT = """
import json, sys
from pathlib import Path
from solvers.palace.coupled_geometry import chip_cell_from_declaration
from solvers.palace.coupled_mesh import dry_run
decl = json.loads(Path(sys.argv[1]).read_text())
report = dry_run(chip_cell_from_declaration(decl), 1, Path(sys.argv[2]))
print(json.dumps(report.as_dict()))
"""


@needs_gmsh
@pytest.mark.slow
def test_dry_run_committed_s1_level_1_within_600s(tmp_path):
    """The real h0 dry run of the committed S1 geometry (decision number).

    Runs in a subprocess so the 600 s wall-clock limit is enforced; the
    report is printed for the checkpoint record. Exceeding the DOF budget is
    a disposition, not a test failure; not finishing in 600 s is reported as
    a failure with that reason.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _S1_DRY_RUN_SCRIPT, str(DECLARATION), str(tmp_path)],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("S1 dry run at level 1 did not finish in 600 s")
    assert proc.returncode == 0, proc.stderr[-4000:]
    d = json.loads(proc.stdout.strip().splitlines()[-1])
    print("S1 level-1 dry run:", json.dumps(d, indent=1))
    assert d["level"] == 1 and d["h_gap_mm"] == pytest.approx(0.01)
    assert d["physical_groups"] == cmesh.TAGS
    if d["aborted_reason"] is None:
        assert d["tetrahedra"] > 0
        assert all(d["triangles_by_tag"][k] > 0 for k in ("sheet_pec", "port_F1", "port_R1_a", "port_R1_b"))
    assert Path(d["mesh_path"]).exists()
