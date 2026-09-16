"""S1 numerical recovery: the mesh measurements, the experiment, and durability.

Three groups.

* *The meshes as built.* Measurements on the committed L1/L2/L3 files: the port
  face's area, orientation and element coverage, that the model did not change
  between levels, and the separation of what the size rule asked for from what
  the mesh has.
* *The prepared experiment.* That the mesher's default path is untouched, that
  the local constraint can only refine, and that the two proposed meshes are
  inside the unchanged DOF rule.
* *Evidence durability.* A deliberate renderer failure, and the commit gate
  that refuses a file kind a record may not carry.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from orchestrator import manifest
from solvers.palace import mesh as pmesh
from solvers.palace.coupled_geometry import chip_cell_from_declaration
from solvers.palace.coupled_mesh import (
    LEVELS,
    PortRefinement,
    dry_run,
    mesh_sizes_mm,
)
from solvers.palace.mesh_inspection import (
    classify_size_field_curves,
    compare_across_levels,
    distance_at_which_size_doubles,
    inspect_mesh,
    read_msh2,
    size_field_profile,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DECLARATION = REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json"
needs_gmsh = pytest.mark.skipif(not pmesh.gmsh_available(), reason="gmsh not importable")

MESHES = {
    "L1": (REPO_ROOT / "results/COUPLED-PILOT-20260916T035733Z/P2/solver/coupled_chip_cell_L1.msh", 1),
    "L2": (REPO_ROOT / "results/COUPLED-LADDER-O1-L2-20260916T080802Z/L2/solver/coupled_chip_cell_L2.msh", 2),
    "L3": (REPO_ROOT / "results/COUPLED-LADDER-O1-L3-20260916T091212Z/L3/solver/coupled_chip_cell_L3.msh", 3),
}
PORT_TAGS = {"port_F1": 10, "port_R1_a": 11, "port_R1_b": 12}
PORT_DIMENSIONS = {"port_F1": (0.04, 0.02), "port_R1_a": (0.02, 0.03), "port_R1_b": (0.02, 0.03)}

HALO_MM = 0.08
DOF_BUDGET = 250_000
#: The two prepared meshes, as the record proposes them.
EXPERIMENT = {
    "R1": {"divisor": 2.0, "dof_order1": 80_762, "port_triangles": 176},
    "R2": {"divisor": 4.0, "dof_order1": 111_238, "port_triangles": 680},
}
EXPERIMENT_BASE_LEVEL = 2
EXPERIMENT_PAD_MM = 0.010
EXPERIMENT_TRANSITION_MM = 0.020


def _cell():
    return chip_cell_from_declaration(json.loads(DECLARATION.read_text()))


def _report(name: str):
    path, level = MESHES[name]
    _, h_gap, _ = mesh_sizes_mm(_cell(), level)
    report = inspect_mesh(
        path, requested_h_gap_mm=h_gap, port_tags=PORT_TAGS,
        port_dimensions=PORT_DIMENSIONS, other_tags=(2, 4),
    )
    report["requested_h_gap_mm"] = h_gap
    return report


# --------------------------------------------------------------------------
# The meshes as built
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(MESHES))
def test_the_port_face_is_the_declared_rectangle(name: str):
    """0.02 x 0.04 mm, planar, normal +z, one physical tag, at every level."""
    face = _report(name)["ports"]["port_F1"]
    assert face["area_mm2"] == pytest.approx(0.0008, rel=1e-9)
    assert face["area_mm2"] == pytest.approx(face["declared_area_mm2"], rel=1e-9)
    assert face["planar"] is True
    assert face["unit_normals"] == [[0.0, 0.0, 1.0]]
    box = face["bounding_box_mm"]
    assert box["max"][0] - box["min"][0] == pytest.approx(0.02, abs=1e-12)
    assert box["max"][1] - box["min"][1] == pytest.approx(0.04, abs=1e-12)
    assert box["min"][2] == box["max"][2] == 0.0


@pytest.mark.parametrize("name", sorted(MESHES))
def test_Lc_is_four_millimetres_measured_from_the_mesh(name: str):
    """The conversion's ``Lc`` is measured, not read from Palace's 4-digit log line."""
    report = _report(name)
    assert report["largest_extent_mm"] == pytest.approx(4.0, abs=1e-12)
    assert report["Lc_m_implied"] == pytest.approx(4.0e-3, rel=1e-12)


def test_the_model_did_not_change_between_levels():
    """A refinement study is only one if the model is the same at every level."""
    consistency = compare_across_levels({name: _report(name) for name in MESHES})
    assert consistency["verdict"] == "MODEL UNCHANGED ACROSS LEVELS"
    assert consistency["physical_names_identical"] is True
    assert consistency["bounding_box_identical"] is True
    assert all(consistency["areas_identical"].values())
    assert all(consistency["port_orientation_identical"].values())


def test_the_port_face_is_coarser_than_the_rule_asked_for():
    """Requested ``h_gap`` and measured local resolution are different numbers.

    The ladder reported only the first. Both are reported here, and at every
    level the longest element edge on the port face is about twice ``h_gap``.
    """
    for name in MESHES:
        face = _report(name)["ports"]["port_F1"]
        measured = face["measured_over_requested"]
        assert measured["longest_edge_over_h_gap"] > 1.9, name
        assert measured["equivalent_element_size_over_h_gap"] > 1.0, name


def test_fewer_than_four_elements_span_the_port_width_at_every_tested_level():
    across = {name: _report(name)["ports"]["port_F1"]["elements_across_width"] for name in MESHES}
    assert across["L1"] < across["L2"] < across["L3"]
    assert across["L3"] < 4.0
    assert across["L1"] < 2.0


def test_the_threshold_profile_is_linear_and_its_reach_is_computed_not_assumed():
    assert size_field_profile(0.005, 0.1, 0.08, 0.0) == pytest.approx(0.005)
    assert size_field_profile(0.005, 0.1, 0.08, 0.08) == pytest.approx(0.1)
    assert size_field_profile(0.005, 0.1, 0.08, 1.0) == pytest.approx(0.1)
    assert size_field_profile(0.005, 0.1, 0.08, 0.04) == pytest.approx(0.0525)
    assert distance_at_which_size_doubles(0.005, 0.105, 0.08) == pytest.approx(0.08 * 0.005 / 0.1)


def test_read_msh2_refuses_a_format_it_does_not_understand(tmp_path: Path):
    bad = tmp_path / "bad.msh"
    bad.write_text("$MeshFormat\n4.1 0 8\n$EndMeshFormat\n")
    with pytest.raises(Exception, match="2.2"):
        read_msh2(bad)


def test_the_committed_meshes_parse_to_the_counts_the_records_state():
    """Cross-check the parser against the ladder record's own measured counts."""
    summary = json.loads(
        (REPO_ROOT / "results/COUPLED-LADDER-O1-L3-20260916T091212Z/summary.json").read_text()
    )
    measured = summary["rung"]["mesh"]["measured"]
    mesh = read_msh2(MESHES["L3"][0])
    assert len(mesh.nodes) == measured["nodes"]
    assert sum(len(v) for v in mesh.tetrahedra.values()) == measured["tetrahedra"]


# --------------------------------------------------------------------------
# The size field, and the early port-face continue
# --------------------------------------------------------------------------


@needs_gmsh
@pytest.mark.parametrize("level", sorted(LEVELS))
def test_three_of_the_four_port_curves_are_already_in_the_distance_field(level: int):
    """The early ``continue`` is not, on this model, the defect it looks like.

    The neighbouring conductor and etch faces contribute three of the port's
    four curves. Only the curve whose other neighbour is the untagged ground
    plane is omitted -- and adding it would not resolve the face either,
    because it is the blend that coarsens the interior.
    """
    findings = classify_size_field_curves(_cell(), level, HALO_MM)
    port = findings["ports"]["port_F1"]
    assert port["curves_total"] == 4
    assert port["curves_in_field"] == 3
    assert port["missing_curve_neighbours"] == ["ground_plane"]
    for name in ("port_R1_a", "port_R1_b"):
        assert findings["ports"][name]["curves_in_field"] == 3


@needs_gmsh
def test_the_size_prescribed_at_the_port_centre_is_scale_invariant_in_h_gap():
    """This is why the ladder could never resolve the port face.

    ``h_gap`` and ``h_far`` both carry the level factor while the halo does
    not, so the whole Threshold profile scales by the level factor and the
    ratio of the prescribed size at the port centre to ``h_gap`` is the same at
    every level.
    """
    ratios = {
        level: classify_size_field_curves(_cell(), level, HALO_MM)["size_field"][
            "prescribed_size_at_port_centre_over_h_gap"
        ]
        for level in sorted(LEVELS)
    }
    assert max(ratios.values()) - min(ratios.values()) < 1e-9
    assert ratios[1] == pytest.approx(5.0416666, rel=1e-6)


@needs_gmsh
def test_the_prescribed_size_at_the_port_centre_exceeds_the_port_width_at_level_one():
    """At level 1 the field asks for an element 2.5x the whole face."""
    field = classify_size_field_curves(_cell(), 1, HALO_MM)["size_field"]
    assert field["prescribed_size_at_port_centre_over_port_width"] > 2.0
    assert field["reach_covers_half_the_port_width"] is False


# --------------------------------------------------------------------------
# The prepared experiment
# --------------------------------------------------------------------------


def test_port_refinement_validates_its_own_numbers():
    with pytest.raises(ValueError, match="h_port_mm"):
        PortRefinement(h_port_mm=0.0, pad_mm=0.01, transition_mm=0.02)
    with pytest.raises(ValueError, match="pad_mm"):
        PortRefinement(h_port_mm=0.001, pad_mm=-1.0, transition_mm=0.02)
    with pytest.raises(ValueError, match="transition_mm"):
        PortRefinement(h_port_mm=0.001, pad_mm=0.01, transition_mm=0.0)
    with pytest.raises(ValueError, match="unknown port"):
        PortRefinement(h_port_mm=0.001, pad_mm=0.01, transition_mm=0.02, ports=("port_Z9",))
    with pytest.raises(ValueError, match="at least one port"):
        PortRefinement(h_port_mm=0.001, pad_mm=0.01, transition_mm=0.02, ports=())


def test_the_refinement_box_surrounds_the_port_rectangle():
    cell = _cell()
    rect = cell.ports["P_F1"][0]
    refinement = PortRefinement(h_port_mm=0.001, pad_mm=0.01, transition_mm=0.02)
    x0, x1, y0, y1, z0, z1 = refinement.box_mm(rect, cell.z_chip_top_mm)
    assert x0 == pytest.approx(rect.x_min - 0.01)
    assert x1 == pytest.approx(rect.x_max + 0.01)
    assert y0 == pytest.approx(rect.y_min - 0.01)
    assert y1 == pytest.approx(rect.y_max + 0.01)
    assert z1 - z0 == pytest.approx(0.02)
    assert refinement.refined_volume_mm3(rect) == pytest.approx(0.04 * 0.06 * 0.02)


def test_the_refinement_is_reported_and_absent_by_default():
    refinement = PortRefinement(h_port_mm=0.001, pad_mm=0.01, transition_mm=0.02)
    payload = refinement.as_dict()
    assert payload["can_only_refine"] is True
    assert "h_far" in payload["holds_fixed"]
    assert payload["ports"] == ["port_F1"]


@needs_gmsh
@pytest.mark.slow
def test_the_default_mesher_path_is_byte_identical_to_the_committed_level_three_mesh():
    """Adding the local constraint must not perturb a run that does not use it."""
    with tempfile.TemporaryDirectory() as scratch:
        report = dry_run(_cell(), 3, Path(scratch), halo_mm=HALO_MM)
    assert report.sha256 == manifest.file_digest(MESHES["L3"][0])
    assert report.dof_order1 == 147_372
    assert report.port_refinement is None


@needs_gmsh
@pytest.mark.slow
@pytest.mark.parametrize("name", sorted(EXPERIMENT))
def test_each_proposed_mesh_measures_its_recorded_dof_inside_the_unchanged_rule(name: str):
    """Measured, not estimated, and reproducible: the dry run is deterministic."""
    spec = EXPERIMENT[name]
    cell = _cell()
    _, h_gap, h_far = mesh_sizes_mm(cell, EXPERIMENT_BASE_LEVEL)
    refinement = PortRefinement(
        h_port_mm=h_gap / spec["divisor"],
        pad_mm=EXPERIMENT_PAD_MM,
        transition_mm=EXPERIMENT_TRANSITION_MM,
    )
    with tempfile.TemporaryDirectory() as scratch:
        report = dry_run(
            cell, EXPERIMENT_BASE_LEVEL, Path(scratch), dof_budget=DOF_BUDGET,
            halo_mm=HALO_MM, port_refinement=refinement, mesh_filename="m.msh",
        )
        face = inspect_mesh(
            report.mesh_path, requested_h_gap_mm=refinement.h_port_mm,
            port_tags={"port_F1": 10}, port_dimensions={"port_F1": (0.04, 0.02)},
        )["ports"]["port_F1"]
    assert report.dof_order1 == spec["dof_order1"]
    assert report.dof_order1 <= DOF_BUDGET
    assert face["triangles"] == spec["port_triangles"]
    # The constraint now actually holds on the face, unlike the ladder's field.
    assert face["equivalent_element_size_mm"] / refinement.h_port_mm == pytest.approx(1.0, abs=0.05)
    assert report.h_far_mm == pytest.approx(h_far)
    assert report.halo_mm == pytest.approx(HALO_MM)


@needs_gmsh
@pytest.mark.slow
def test_the_two_proposed_meshes_differ_in_exactly_one_prescribed_number():
    cell = _cell()
    _, h_gap, _ = mesh_sizes_mm(cell, EXPERIMENT_BASE_LEVEL)
    payloads = []
    for name in ("R1", "R2"):
        refinement = PortRefinement(
            h_port_mm=h_gap / EXPERIMENT[name]["divisor"],
            pad_mm=EXPERIMENT_PAD_MM, transition_mm=EXPERIMENT_TRANSITION_MM,
        )
        payloads.append(refinement.as_dict())
    differing = {k for k in payloads[0] if payloads[0][k] != payloads[1][k]}
    assert differing == {"h_port_mm"}
    assert payloads[1]["h_port_mm"] == pytest.approx(payloads[0]["h_port_mm"] / 2.0)


# --------------------------------------------------------------------------
# The approval record is the only way a refinement is introduced
# --------------------------------------------------------------------------


def _ladder_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ladder_under_test", REPO_ROOT / "scripts" / "palace_order1_ladder.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_committed_approval_record_now_authorises_R1_only():
    """The owner approved R1 after review. R2 is prepared and NOT approved.

    This test asserted the opposite before the approval, which was correct then:
    the change that prepared the experiment could not also start it.
    """
    label, refinement, expected_sha = _ladder_module().approved_port_refinement()
    assert label == "R1"
    assert refinement.h_port_mm == 0.003333333333333333
    assert expected_sha == "a49ef282c7f07c56f210a450b291a2e027de530ba7c3e78bbdcead3b67315fee"


def test_an_approved_refinement_is_read_from_the_record_and_validated(tmp_path: Path):
    ladder = _ladder_module()
    path = tmp_path / "approval.json"
    path.write_text(json.dumps({
        "level": 2,
        "port_refinement": {
            "id": "R1", "h_port_mm": 0.003333333333333333,
            "pad_mm": 0.010, "transition_mm": 0.020,
        },
    }))
    label, refinement, expected_sha = ladder.approved_port_refinement(path)
    assert label == "R1"
    assert refinement.h_port_mm == 0.003333333333333333
    assert refinement.pad_mm == pytest.approx(0.010)
    assert expected_sha is None, "no mesh named, so nothing to check against"

    # A named mesh becomes a gate: a different one is not the approved experiment.
    path.write_text(json.dumps({
        "level": 2,
        "port_refinement": {
            "id": "R1", "h_port_mm": 0.003333333333333333,
            "pad_mm": 0.010, "transition_mm": 0.020,
        },
        "dry_run_mesh_sha256": {"R1": "deadbeef"},
    }))
    assert ladder.approved_port_refinement(path)[2] == "deadbeef"
    entry = ladder.execute_level(
        2, json.loads((REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json").read_text()),
        tmp_path / "solver", runtime="docker", image="unused", np_processes=1,
        prepare_only=True, port_refinement=refinement, expected_mesh_sha256="deadbeef",
    )
    assert entry["status"] == "REFUSED-MESH-MISMATCH"
    assert "not the deadbeef the approval record named" in entry["failure"]

    path.write_text(json.dumps({"port_refinement": {"id": "R1", "h_port_mm": 0.003}}))
    with pytest.raises(ladder.LadderError, match="missing"):
        ladder.approved_port_refinement(path)

    path.write_text(json.dumps({"port_refinement": {
        "id": "R 1", "h_port_mm": 0.003, "pad_mm": 0.01, "transition_mm": 0.02}}))
    with pytest.raises(ladder.LadderError, match="alphanumeric"):
        ladder.approved_port_refinement(path)


# --------------------------------------------------------------------------
# Evidence durability
# --------------------------------------------------------------------------


@needs_gmsh
@pytest.mark.slow
def test_a_renderer_failure_loses_no_evidence(tmp_path: Path):
    """Exercised, not asserted: the renderer is made to raise and the record survives.

    The level-3 rung's first attempt completed its solve and lost it, because
    the report was rendered before the manifest and the record pointer were
    written and the renderer raised on a result the estimator is designed to
    return.
    """
    pointer = tmp_path / "pointer"
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "palace_s1_recovery.py"),
         "--results-root", str(tmp_path / "results"),
         "--record-pointer", str(pointer), "--fail-render"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=1800,
    )
    assert completed.returncode == 2, completed.stderr
    assert "deliberate renderer failure" in completed.stderr

    record = Path(pointer.read_text().strip())
    assert record.is_dir()
    assert manifest.verify(record) == []
    summary = json.loads((record / "summary.json").read_text())
    assert summary["palace_launched"] is False
    assert summary["prepared_experiment"]["meshes"]["R2"]["measured"]["dof_order1"] == 111_238
    assert summary["port_diagnostic"]["L3"]["worst_relative_disagreement_probe_vs_closure"] < 1e-5
    report = (record / "report.md").read_text()
    assert "could not be rendered" in report
    assert "not a loss of evidence" in report
    manifested = (record / "manifest.sha256").read_text()
    assert "summary.json" in manifested and "report.md" in manifested


def test_the_commit_gate_refuses_a_file_kind_a_record_may_not_carry(tmp_path: Path):
    record = tmp_path / "record"
    (record / "paraview" / "Mode1").mkdir(parents=True)
    (record / "summary.json").write_text("{}\n")
    (record / "paraview" / "Mode1" / "mode.vtu").write_text("x")
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_record_files.py"), str(record)],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert completed.returncode == 1
    assert "paraview/Mode1/mode.vtu" in completed.stderr

    (record / "paraview" / "Mode1" / "mode.vtu").unlink()
    ok = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_record_files.py"), str(record)],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert ok.returncode == 0


def test_the_committed_records_pass_the_commit_gate():
    for record in (
        "results/COUPLED-PILOT-20260916T035733Z",
        "results/COUPLED-LADDER-O1-L2-20260916T080802Z",
        "results/COUPLED-LADDER-O1-L3-20260916T091212Z",
    ):
        assert manifest.unexpected_files(REPO_ROOT / record) == [], record


def test_the_ladder_workflow_gates_the_commit_and_uploads_regardless():
    workflow = (REPO_ROOT / ".github" / "workflows" / "palace-order1-ladder.yml").read_text()
    assert "scripts/check_record_files.py" in workflow
    gate = workflow.index("Refuse unexpected file kinds")
    commit = workflow.index("Commit the record to the branch")
    assert gate < commit, "the gate must run before git add"
    for step in ("Upload the record", "Upload the field output"):
        section = workflow[workflow.index(step):]
        assert "if: always()" in section[: section.index("uses:")], step


def test_the_recorded_mesh_hashes_match_the_predeclared_approval_block():
    """The approval block, the record and the document must name one mesh each."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "predeclaration_under_test", REPO_ROOT / "scripts" / "s1_experiment_predeclaration.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    block = module.PREDECLARATION["approval_block_to_paste"]

    records = sorted((REPO_ROOT / "results").glob("COUPLED-S1-RECOVERY-*"))
    assert records, "the recovery record is not present"
    summary = json.loads((records[-1] / "summary.json").read_text())
    meshes = summary["prepared_experiment"]["meshes"]
    for name in ("R1", "R2"):
        assert meshes[name]["port_refinement"]["h_port_mm"] == block[name]["h_port_mm"]
        assert meshes[name]["port_refinement"]["pad_mm"] == block[name]["pad_mm"]
        assert meshes[name]["port_refinement"]["transition_mm"] == block[name]["transition_mm"]
        assert meshes[name]["measured"]["mesh_sha256"] == block["dry_run_mesh_sha256"][name]
        assert meshes[name]["measured"]["dof_order1"] == EXPERIMENT[name]["dof_order1"]
        assert meshes[name]["base_level"] == block["level"] == EXPERIMENT_BASE_LEVEL

    document = (REPO_ROOT / "docs" / "coupled-candidate" / "s1-numerical-recovery.md").read_text()
    for name in ("R1", "R2"):
        assert block["dry_run_mesh_sha256"][name][:16] in document, name
        assert repr(block[name]["h_port_mm"]) in document or f"{block[name]['h_port_mm']:.6f}" in document


def test_the_record_states_what_the_experiment_cannot_do():
    records = sorted((REPO_ROOT / "results").glob("COUPLED-S1-RECOVERY-*"))
    summary = json.loads((records[-1] / "summary.json").read_text())
    predeclaration = summary["prepared_experiment"]["predeclaration"]
    assert "establish convergence" in predeclaration["what_two_meshes_cannot_do"]
    assert {o["id"] for o in predeclaration["outcomes"]} == {"A", "B", "C", "D", "E"}
    for outcome in predeclaration["outcomes"]:
        assert outcome["would_not_mean"], outcome["id"]
    disclaimers = " ".join(summary["refinement_trend"]["what_this_does_not_establish"])
    assert "does not prove mathematical nonconvergence" in disclaimers
    assert "physical architecture fails" in disclaimers
    assert "every in-budget mesh has been exhausted" in disclaimers
    assert summary["palace_launched"] is False
    assert summary["mesh_inspection"]["consistency_across_levels"]["verdict"] == (
        "MODEL UNCHANGED ACROSS LEVELS"
    )


def test_the_recovery_record_preserves_and_references_its_sources():
    records = sorted((REPO_ROOT / "results").glob("COUPLED-S1-RECOVERY-*"))
    summary = json.loads((records[-1] / "summary.json").read_text())
    for name, entry in summary["source_records"].items():
        source = REPO_ROOT / entry["record"]
        assert manifest.verify(source) == [], name
        assert manifest.file_digest(source / "manifest.sha256") == entry["manifest_sha256"], name
    assert manifest.verify(records[-1]) == []

# --- the approved R1 run ------------------------------------------------------


def test_the_approval_record_authorises_exactly_the_prepared_R1_mesh():
    """The owner approved R1. The record must name the mesh that was dry-run.

    The approved h_port is written out to the last double because the hash below
    is for that exact value; a rounded literal would build a different mesh and
    the gate would refuse to solve it.
    """
    approval = json.loads((REPO_ROOT / ".github" / "ladder-approval.json").read_text())
    refinement = approval["port_refinement"]
    assert refinement["id"] == "R1"
    assert refinement["h_port_mm"] == 0.003333333333333333
    assert refinement["pad_mm"] == EXPERIMENT_PAD_MM
    assert refinement["transition_mm"] == EXPERIMENT_TRANSITION_MM
    assert refinement["ports"] == ["port_F1"]
    assert approval["level"] == EXPERIMENT_BASE_LEVEL
    assert approval["baseline_record"] == "COUPLED-LADDER-O1-L2-20260916T080802Z"
    assert (
        approval["dry_run_mesh_sha256"]["R1"]
        == "a49ef282c7f07c56f210a450b291a2e027de530ba7c3e78bbdcead3b67315fee"
    )
    # R2 is prepared but NOT approved.
    assert "R2" not in approval["dry_run_mesh_sha256"]
    assert any("R2" in item for item in approval["explicitly_out_of_scope"])


def test_the_approved_refinement_matches_the_predeclared_experiment():
    """What is approved and what was predeclared must be the same numbers."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "predeclaration_check", REPO_ROOT / "scripts" / "s1_experiment_predeclaration.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    predeclared = module.PREDECLARATION["approval_block_to_paste"]["R1"]
    approval = json.loads((REPO_ROOT / ".github" / "ladder-approval.json").read_text())
    for key in ("id", "h_port_mm", "pad_mm", "transition_mm", "ports"):
        assert approval["port_refinement"][key] == predeclared[key], key


def test_the_mesh_the_approval_pins_is_the_one_the_mesher_builds():
    """The gate is only meaningful if the pinned hash is reproducible."""
    approval = json.loads((REPO_ROOT / ".github" / "ladder-approval.json").read_text())
    refinement = PortRefinement(
        h_port_mm=approval["port_refinement"]["h_port_mm"],
        pad_mm=approval["port_refinement"]["pad_mm"],
        transition_mm=approval["port_refinement"]["transition_mm"],
        ports=tuple(approval["port_refinement"]["ports"]),
    )
    with tempfile.TemporaryDirectory() as scratch:
        report = dry_run(
            _cell(), approval["level"], Path(scratch), dof_budget=DOF_BUDGET,
            halo_mm=HALO_MM, port_refinement=refinement, mesh_filename="m.msh",
        )
    assert report.sha256 == approval["dry_run_mesh_sha256"]["R1"]
    assert report.dof_order1 == EXPERIMENT["R1"]["dof_order1"]


def test_a_refined_record_is_excluded_from_the_convergence_fit(tmp_path: Path):
    """Not by lexicographic luck: by payload, for any label.

    A label sorting BEFORE the plain record (one starting with a digit, say)
    would otherwise win the level dedup and put a different mesh into a fit that
    assumes one size prescription scaled by the level factor.
    """
    import shutil

    ladder = _ladder_module()
    root = tmp_path / "results"
    root.mkdir()
    for name in (
        "COUPLED-PILOT-20260916T035733Z",
        "COUPLED-LADDER-O1-L2-20260916T080802Z",
        "COUPLED-LADDER-O1-L3-20260916T091212Z",
    ):
        shutil.copytree(REPO_ROOT / "results" / name, root / name)

    plain = root / "COUPLED-LADDER-O1-L2-20260916T080802Z"
    for label in ("R1", "0A", "1P0"):
        refined = root / f"COUPLED-LADDER-O1-L2-{label}-20260916T999999Z"
        shutil.copytree(plain, refined)
        summary = json.loads((refined / "summary.json").read_text())
        summary["rung"]["port_refinement"] = {"h_port_mm": 0.00333, "pad_mm": 0.01}
        (refined / "summary.json").write_text(json.dumps(summary))

    sources = [r["source"] for r in ladder.earlier_rungs(root)]
    assert sources == [
        "COUPLED-PILOT-20260916T035733Z/P2",
        "COUPLED-LADDER-O1-L2-20260916T080802Z",
        "COUPLED-LADDER-O1-L3-20260916T091212Z",
    ]

    # And with the plain record gone, the level is simply ABSENT rather than
    # being filled by a mesh that does not belong to the sequence.
    shutil.rmtree(plain)
    levels = [r["level"] for r in ladder.earlier_rungs(root)]
    assert levels == [1, 3]


def test_the_derived_diagnostic_runs_on_a_real_record():
    """The exact post-solve code path, on committed outputs.

    Palace cannot run here, so this is the only way to exercise what the solve
    will execute. It reproduces the numbers the recovery record published.
    """
    from solvers.palace import outputs as pout
    from solvers.palace.mode_admission import join_modes_by_id

    ladder = _ladder_module()
    solver = REPO_ROOT / "results/COUPLED-LADDER-O1-L3-20260916T091212Z/L3/solver"
    result = ladder.derived_port_diagnostic(
        join_modes_by_id(solver / "postpro"),
        pout.parse_surface_q_csv(solver / "postpro" / "surface-Q.csv"),
        config=json.loads((solver / "config.json").read_text()),
        mesh_path=solver / "coupled_chip_cell_L3.msh",
        requested_h_gap_mm=0.005,
    )
    assert result["available"] is True
    assert result["conversion"]["kappa"] == pytest.approx(0.38868825288128767, rel=1e-12)
    assert result["worst_relative_disagreement_probe_vs_closure"] < 1e-5
    assert len(result["modes"]) == 6
    for row in result["modes"]:
        assert row["uniformity_factor_E_ind_over_E_port"] <= 1.0 + 1e-9


def test_the_derived_diagnostic_never_costs_a_solve():
    """A diagnostic that raises must degrade to a reason, not kill the record."""
    ladder = _ladder_module()
    result = ladder.derived_port_diagnostic(
        [], [], config={}, mesh_path=Path("/nonexistent.msh"), requested_h_gap_mm=0.005,
    )
    assert result["available"] is False
    assert result["reason"]


def test_the_baseline_comparison_answers_the_question_the_run_exists_for():
    """Standing the L3 rung in for a refined run exercises the real path.

    Sensitivity comes out exactly 1 because the numerator and the denominator
    are then the same quantity, which is the correct self-consistency result and
    pins the mode correspondence and the arithmetic.
    """
    ladder = _ladder_module()
    l3 = json.loads(
        (REPO_ROOT / "results/COUPLED-LADDER-O1-L3-20260916T091212Z/summary.json").read_text()
    )
    entry = dict(l3["rung"])
    entry["port_refinement"] = {"h_port_mm": 0.003333333333333333}

    comparison = ladder.compare_against_baseline(entry, "COUPLED-LADDER-O1-L2-20260916T080802Z")
    assert comparison["available"] is True
    assert comparison["match"]["status"] == "MATCHED"
    assert len(comparison["pairs"]) == 2
    assert comparison["pairs"][0]["delta_f_GHz"] == pytest.approx(0.247675, abs=1e-6)

    sensitivity = ladder.port_resolution_sensitivity(comparison, l3["convergence"])
    assert sensitivity["available"] is True
    for row in sensitivity["per_mode"]:
        assert row["available"] is True
        assert row["sensitivity"] == pytest.approx(1.0, abs=1e-9)
    assert any("does not establish convergence" in c for c in sensitivity["what_it_cannot_say"])


def test_the_baseline_comparison_refuses_a_baseline_that_is_not_one():
    ladder = _ladder_module()
    entry = {"status": "COMPLETED", "admission": {"modes": []}}
    assert not ladder.compare_against_baseline(entry, "NO-SUCH-RECORD")["available"]
    assert "not on disk" in ladder.compare_against_baseline(entry, "NO-SUCH-RECORD")["reason"]
    assert not ladder.compare_against_baseline({"status": "TIMEOUT"}, "x")["available"]


def test_a_refined_run_reports_stop_rather_than_costing_the_next_level():
    ladder = _ladder_module()
    refined = ladder.next_level_disposition({"port_refinement": {"h_port_mm": 0.003}}, {})
    assert refined["queued"] is None
    assert refined["decision"].startswith("STOP")
    assert "not a ladder rung" in refined["decision"]
    plain = ladder.next_level_disposition(
        {"port_refinement": None, "dof_measured": 79_944},
        {"L3": {"measured": {"dof_order1": 147_372}}},
    )
    assert plain["decision"].startswith("FOR REVIEW")
    assert plain["dof_measured"] == 147_372


def test_the_renderer_survives_a_refined_summary():
    """The regression a prepare-only dry run caught before the solve was spent.

    render_report raised KeyError('dof_measured') on a refined run, because
    next_level_disposition returns the refinement branch and the renderer
    assumed the level-3 shape.
    """
    ladder = _ladder_module()
    l3 = json.loads(
        (REPO_ROOT / "results/COUPLED-LADDER-O1-L3-20260916T091212Z/summary.json").read_text()
    )
    l3["rung"]["port_refinement"] = {"h_port_mm": 0.003333333333333333, "pad_mm": 0.01}
    l3["next_level"] = ladder.next_level_disposition(l3["rung"], l3.get("dry_runs") or {})
    l3["baseline_comparison"] = {"available": False, "reason": "not a port-refined run"}
    l3["port_resolution_sensitivity"] = {"available": False, "reason": "not a port-refined run"}
    text = ladder.render_report(l3)
    assert "STOP" in text
    assert "could not be rendered" not in text


def test_the_approval_describer_never_fails_a_step_that_runs_after_a_solve(tmp_path: Path):
    """It runs in the commit step; raising there would strand a paid-for solve."""
    import subprocess
    import sys

    script = REPO_ROOT / "scripts" / "describe_ladder_approval.py"
    junk = tmp_path / "junk.json"
    junk.write_text("{}")
    done = subprocess.run(
        [sys.executable, str(script), "--headline", str(junk)],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert done.returncode == 0

    broken = tmp_path / "broken.json"
    broken.write_text("not json at all")
    done = subprocess.run(
        [sys.executable, str(script), "--headline", str(broken)],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert done.returncode == 0
    assert "record written" in done.stdout

    described = subprocess.run(
        [sys.executable, str(script), "--approval", str(REPO_ROOT / ".github/ladder-approval.json")],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert described.returncode == 0
    assert "R1" in described.stdout
    assert "a49ef282" in described.stdout


def test_the_workflow_describes_the_approval_and_builds_its_headline_from_a_script():
    """A multi-line python -c inside a YAML block scalar broke the file once."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "palace-order1-ladder.yml").read_text()
    assert "scripts/describe_ladder_approval.py --approval" in workflow
    assert "scripts/describe_ladder_approval.py --headline" in workflow
    import yaml

    parsed = yaml.safe_load(workflow)
    assert parsed["jobs"]["ladder"]["steps"]


# --- the guards the pre-flight audit added ------------------------------------


def test_the_post_solve_analysis_cannot_cost_a_paid_for_solve(tmp_path: Path, monkeypatch):
    """The window between the solve returning and the durable write is guarded.

    The evidence-before-presentation fix guarded the RENDERER. Everything from
    execute_level() returning to summary.json being written - manifest
    verification, mode matching, the convergence fit, the baseline comparison -
    was still fatal, and every function added there widened the exposure.
    """
    ladder = _ladder_module()
    monkeypatch.setattr(
        ladder, "earlier_rungs",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("analysis exploded")),
    )
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({"level": 2}))
    pointer = tmp_path / "pointer"
    code = ladder.main([
        "--level", "2", "--prepare-only",
        "--approval", str(approval),
        "--results-root", str(tmp_path / "results"),
        "--record-pointer", str(pointer),
    ])
    assert code == 1, "an analysis failure is reported, not swallowed"

    record = Path(pointer.read_text().strip())
    assert record.is_dir(), "the record the workflow uploads must still exist"
    assert manifest.verify(record) == [], "and it must still be manifested"
    summary = json.loads((record / "summary.json").read_text())
    assert "analysis exploded" in summary["post_solve_analysis_failed"]
    # The solve's OWN outputs survive untouched; only the analysis is missing.
    assert summary["rung"]["status"] == "PREPARED"
    assert summary["rung"]["dof_measured"] == 79_944
    assert summary["comparison"]["available"] is False
    report = (record / "report.md").read_text()
    assert "post-solve analysis failed" in report
    assert "not a loss of evidence" in report


def test_the_superseded_port_field_test_cannot_downgrade_a_completed_solve():
    """It is guarded as widely as its successor.

    Guarded only against PalaceOutputError, any other exception from the fitted
    procedure fell through to execute_level's outer handler, turned a COMPLETED
    solve into ERROR, and skipped the derived diagnostic entirely.
    """
    source = (REPO_ROOT / "scripts" / "palace_order1_ladder.py").read_text()
    call = source.index("entry[\"port_field_test\"] = port_field_analysis(")
    guard = source.index("except Exception", call)
    successor = source.index("entry[\"port_diagnostic\"] = derived_port_diagnostic(", call)
    assert guard < successor, "the fitted test must be guarded before the derived one runs"


def test_the_refinement_label_reaches_the_record_and_the_commit_headline():
    """Without it both a refined run and a plain rerun read "L2 COMPLETED"."""
    refinement = PortRefinement(
        h_port_mm=0.003333333333333333, pad_mm=0.010, transition_mm=0.020, label="R1",
    )
    assert refinement.as_dict()["id"] == "R1"
    label, built, _ = _ladder_module().approved_port_refinement(
        REPO_ROOT / ".github" / "ladder-approval.json"
    )
    assert built.label == label == "R1"
    assert built.as_dict()["id"] == "R1"


def test_a_missing_or_refined_baseline_refuses_before_anything_is_launched(tmp_path: Path):
    """A solve may not be spent only to find the comparison impossible."""
    ladder = _ladder_module()
    approval = tmp_path / "approval.json"
    block = {
        "id": "R1", "h_port_mm": 0.003333333333333333,
        "pad_mm": 0.010, "transition_mm": 0.020,
    }
    approval.write_text(json.dumps({
        "level": 2, "baseline_record": "NO-SUCH-RECORD", "port_refinement": block,
    }))
    with pytest.raises(ladder.LadderError, match="not a record on disk"):
        ladder.approved_port_refinement(approval)


def test_the_baseline_port_participation_is_recomputed_when_the_record_predates_it():
    """Otherwise the headline delta is a column of n/a.

    The committed level-2 baseline was solved before the derived diagnostic
    existed, so it carries none. It is recomputed read-only from that record's
    own committed outputs and must reproduce the published numbers.
    """
    ladder = _ladder_module()
    l3 = json.loads(
        (REPO_ROOT / "results/COUPLED-LADDER-O1-L3-20260916T091212Z/summary.json").read_text()
    )
    entry = dict(l3["rung"])
    entry["port_refinement"] = {"h_port_mm": 0.003333333333333333}
    comparison = ladder.compare_against_baseline(
        entry, "COUPLED-LADDER-O1-L2-20260916T080802Z"
    )
    assert comparison["baseline_diagnostic_recomputed"] is True
    ports = [p["port_participation_from_probes"]["baseline"] for p in comparison["pairs"]]
    assert ports[0] == pytest.approx(9.985982e-01, rel=1e-6)
    assert ports[1] == pytest.approx(7.803572e-04, rel=1e-5)
    # And the baseline record itself is untouched.
    assert manifest.verify(REPO_ROOT / "results/COUPLED-LADDER-O1-L2-20260916T080802Z") == []


def test_the_confounded_trend_is_refused_on_a_refined_run():
    """Against level 1 a refined run changes the level AND the port box."""
    ladder = _ladder_module()
    trend = ladder.refinement_trend({}, {"port_refinement": {"h_port_mm": 0.003}}, {})
    assert trend["available"] is False
    assert "confounds" in trend["reason"]
    assert "baseline_comparison" in trend["reason"]


def test_the_file_kind_gate_actually_gates_the_commit():
    """Both steps on always() meant a failed gate printed and the commit ran."""
    import yaml

    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "palace-order1-ladder.yml").read_text()
    )
    steps = {s.get("name", ""): s for s in workflow["jobs"]["ladder"]["steps"]}
    gate = next(k for k in steps if "Refuse unexpected file kinds" in k)
    commit = next(k for k in steps if "Commit the record" in k)
    assert steps[gate].get("id") == "filekinds"
    assert "steps.filekinds.outcome != 'failure'" in steps[commit]["if"]
    fail = next(k for k in steps if k.startswith("Fail the job"))
    assert "steps.filekinds.outcome == 'failure'" in steps[fail]["if"]
    # A re-run attempt must be able to upload its artifacts.
    for name, step in steps.items():
        if name.startswith("Upload"):
            assert "github.run_attempt" in step["with"]["name"], name


def test_the_report_states_which_refinement_it_reports_on():
    ladder = _ladder_module()
    l3 = json.loads(
        (REPO_ROOT / "results/COUPLED-LADDER-O1-L3-20260916T091212Z/summary.json").read_text()
    )
    l3["rung"]["port_refinement"] = {
        "id": "R1", "h_port_mm": 0.003333333333333333, "pad_mm": 0.01,
        "transition_mm": 0.02, "ports": ["port_F1"],
        "holds_fixed": "h_far and the rest", "combination": "Min",
    }
    l3["next_level"] = ladder.next_level_disposition(l3["rung"], l3.get("dry_runs") or {})
    l3["baseline_comparison"] = {"available": False, "reason": "not a port-refined run"}
    l3["port_resolution_sensitivity"] = {"available": False, "reason": "not a port-refined run"}
    text = ladder.render_report(l3)
    assert "Approved as **R1**" in text
    assert "This is not a ladder rung" in text
    assert "UNREFINED level prescription" in text
    assert "SUPERSEDED" in text


@pytest.mark.parametrize(
    "partial",
    [
        {"h_port_mm": 0.003},
        {"id": "R1"},
        {},
        None,
    ],
)
def test_the_renderer_is_total_over_a_partial_refinement_payload(partial):
    """A renderer that can raise is the bug class that lost a completed solve.

    Bracket access on the refinement dict was reintroduced while fixing the
    report and raised KeyError on anything but a complete payload.
    """
    ladder = _ladder_module()
    summary = json.loads(
        (REPO_ROOT / "results/COUPLED-LADDER-O1-L3-20260916T091212Z/summary.json").read_text()
    )
    summary["rung"]["port_refinement"] = partial
    summary["next_level"] = ladder.next_level_disposition(
        summary["rung"], summary.get("dry_runs") or {}
    )
    summary["baseline_comparison"] = {"available": False, "reason": "x"}
    summary["port_resolution_sensitivity"] = {"available": False, "reason": "x"}
    text = ladder.render_report(summary)
    assert text
    assert "could not be rendered" not in text


# --- the R1 corrections, pinned to the numbers that justify them --------------

R1_RECORD = REPO_ROOT / "results" / "COUPLED-LADDER-O1-L2-R1-20260916T120954Z"


def test_the_r1_run_solved_the_approved_mesh_and_nothing_else():
    summary = json.loads((R1_RECORD / "summary.json").read_text())
    rung = summary["rung"]
    approval = json.loads((REPO_ROOT / ".github" / "ladder-approval.json").read_text())
    assert rung["status"] == "COMPLETED"
    assert rung["mesh"]["sha256"] == approval["dry_run_mesh_sha256"]["R1"]
    assert rung["dof_measured"] == 80_762 <= DOF_BUDGET
    assert rung["run"]["wall_clock_s"] < 2700
    assert summary["post_solve_analysis_failed"] is None
    assert manifest.verify(R1_RECORD) == []


def test_the_claim_that_survives_every_correction():
    """R1's port face is finer than L3's yet its frequency is below L3's.

    Two measured frequencies and two triangle counts: no ratio, no regional
    decomposition, no efficiency claim. Everything else in the first write-up
    was faulted by independent readings and is struck in the document.
    """
    from solvers.palace.mesh_inspection import read_msh2

    r1_face = len(read_msh2(R1_RECORD / "L2" / "solver" / "coupled_chip_cell_L2.msh").triangles[10])
    l3_face = len(
        read_msh2(
            REPO_ROOT
            / "results/COUPLED-LADDER-O1-L3-20260916T091212Z/L3/solver/coupled_chip_cell_L3.msh"
        ).triangles[10]
    )
    assert r1_face == 176 and l3_face == 45
    assert r1_face / l3_face == pytest.approx(3.91, abs=0.01)

    r1_f = json.loads((R1_RECORD / "summary.json").read_text())["rung"]["admission"]["modes"][0]
    l3_f = json.loads(
        (REPO_ROOT / "results/COUPLED-LADDER-O1-L3-20260916T091212Z/summary.json").read_text()
    )["rung"]["admission"]["modes"][0]
    assert r1_f["frequency_GHz"] == pytest.approx(1.521003, abs=1e-6)
    assert l3_f["frequency_GHz"] == pytest.approx(1.709562, abs=1e-6)
    # Finer port face, LOWER frequency: the port face is not the sole driver.
    assert r1_f["frequency_GHz"] < l3_f["frequency_GHz"]


def test_the_withdrawn_cost_ratios_are_not_restated():
    """The per-second ratio is 1.28x. The document once said 3.2x, wrongly."""
    r1 = json.loads((R1_RECORD / "summary.json").read_text())["rung"]["run"]["wall_clock_s"]
    base = json.loads(
        (REPO_ROOT / "results/COUPLED-LADDER-O1-L2-20260916T080802Z/summary.json").read_text()
    )["rung"]["run"]["wall_clock_s"]
    ratio = (0.059116 / (r1 - base)) / (0.247675 / (159.1 - base))
    assert ratio == pytest.approx(1.28, abs=0.02), "the corrected per-second ratio"
    document = (
        REPO_ROOT / "docs" / "coupled-candidate" / "r1-port-refinement-outcome.md"
    ).read_text()
    assert "1.28" in document
    assert "withdrawn; the measured per-second ratio is 1.28" in document


def test_port_refinement_made_the_admitted_closure_worse_and_the_record_says_so():
    """Reported because it is the reason the separation margin fell."""
    r1 = json.loads((R1_RECORD / "summary.json").read_text())["rung"]["admission"]
    base = json.loads(
        (REPO_ROOT / "results/COUPLED-LADDER-O1-L2-20260916T080802Z/summary.json").read_text()
    )["rung"]["admission"]
    r1_m1 = [m for m in r1["modes"] if m["disposition"] == "ADMITTED"][0]
    base_m1 = [m for m in base["modes"] if m["disposition"] == "ADMITTED"][0]
    assert r1_m1["energy_balance_defect"] > base_m1["energy_balance_defect"]
    assert r1["separation_decades"] < base["separation_decades"]
    document = (
        REPO_ROOT / "docs" / "coupled-candidate" / "r1-port-refinement-outcome.md"
    ).read_text()
    assert "+22.9" in document
    assert "0.090 decades **worse**" in document


def test_the_order_verdict_is_shown_to_depend_on_the_choice_of_h():
    """Against the DELIVERED face size a positive order fits; against h_gap none does.

    Not a convergence claim. It is why "the ladder shows no positive order of
    convergence" is withdrawn as a statement about the solution.
    """
    import math

    def fits(h, f):
        H1, H2 = h[0] / h[2], h[1] / h[2]
        floor = (math.log(H1) - math.log(H2)) / math.log(H2)
        return (f[0] - f[1]) / (f[1] - f[2]) > floor

    f1 = [1.158332505, 1.461886595, 1.709561611]
    f2 = [3.693188998, 3.885511214, 4.087683186]
    requested = [0.010, 0.0066666666, 0.005]
    delivered = [0.010425, 0.008597, 0.006407]
    assert not fits(requested, f1) and not fits(requested, f2)
    assert fits(delivered, f1) and fits(delivered, f2)

    document = (
        REPO_ROOT / "docs" / "coupled-candidate" / "r1-port-refinement-outcome.md"
    ).read_text()
    assert "not robust to the" in document and "choice of `h`" in document
    assert "is **not** a claim that" in document


def test_two_records_claiming_one_ladder_level_are_refused(tmp_path: Path):
    """Silently taking the first meant the OLDEST stamp won, unannounced."""
    import shutil

    ladder = _ladder_module()
    root = tmp_path / "results"
    root.mkdir()
    for name in (
        "COUPLED-PILOT-20260916T035733Z",
        "COUPLED-LADDER-O1-L2-20260916T080802Z",
        "COUPLED-LADDER-O1-L3-20260916T091212Z",
    ):
        shutil.copytree(REPO_ROOT / "results" / name, root / name)
    assert [r["level"] for r in ladder.earlier_rungs(root)] == [1, 2, 3]

    shutil.copytree(
        root / "COUPLED-LADDER-O1-L2-20260916T080802Z",
        root / "COUPLED-LADDER-O1-L2-20260916T999999Z",
    )
    with pytest.raises(ladder.LadderError, match="two records claim ladder level 2"):
        ladder.earlier_rungs(root)


def test_the_refinement_is_a_volume_and_the_code_says_so():
    """`pad_mm` applies in z too, so this is not a port-FACE refinement.

    Describing it as one asserts a physical channel that the prescription does
    not establish, and the record and the docstring both had to be corrected.
    """
    cell = _cell()
    rect = cell.ports["P_F1"][0]
    refinement = PortRefinement(h_port_mm=0.003333333333333333, pad_mm=0.010, transition_mm=0.020)
    x0, x1, y0, y1, z0, z1 = refinement.box_mm(rect, cell.z_chip_top_mm)
    assert (x1 - x0, y1 - y0) == pytest.approx((0.040, 0.060), abs=1e-12)
    assert z1 - z0 == pytest.approx(0.020, abs=1e-12), "it pads in z, into vacuum and substrate"
    assert "volume, not a face" in PortRefinement.__doc__

    ladder = _ladder_module()
    source = (REPO_ROOT / "scripts" / "palace_order1_ladder.py").read_text()
    assert "it is NOT one physical channel" in source
    assert "UPPER BOUND, not a share" in source
    assert ladder is not None


def test_the_readout_mode_shift_does_not_scale_with_its_port_participation():
    """A positive-definite port term cannot move two positive-participation modes
    in opposite directions, so mode 2 moved through some other channel.

    This is what withdrew the causal attribution: the prescription changed one
    number, but the channel is the refined volume, not the port.
    """
    summary = json.loads((R1_RECORD / "summary.json").read_text())
    pairs = summary["baseline_comparison"]["pairs"]
    m1, m2 = pairs[0], pairs[1]
    p1 = m1["port_participation_from_probes"]["baseline"]
    p2 = m2["port_participation_from_probes"]["baseline"]

    rel1 = abs(m1["delta_f_GHz"]) / m1["baseline_frequency_GHz"]
    predicted_rel2 = rel1 * (p2 / p1)
    predicted_GHz = predicted_rel2 * m2["baseline_frequency_GHz"]
    observed_GHz = abs(m2["delta_f_GHz"])

    assert observed_GHz / predicted_GHz > 100, "two orders too large for a port-mediated shift"
    # ... and the signs are opposite, which a positive-definite term forbids.
    assert m1["delta_f_GHz"] > 0 > m2["delta_f_GHz"]
    # It is not solver noise either.
    assert abs(m2["delta_f_relative"]) > 40 * 1.0e-4


def test_the_denominator_applies_a_far_weaker_port_perturbation():
    """So the ratio is an upper bound, never a share."""
    recovery = sorted((REPO_ROOT / "results").glob("COUPLED-S1-RECOVERY-*"))[-1]
    field = json.loads((recovery / "summary.json").read_text())["mesh_inspection"]["size_field"]
    centre = {
        level: block["size_field"]["prescribed_size_at_port_centre_mm"]
        for level, block in field["per_level"].items()
    }
    ladder_step = centre["L2"] / centre["L3"]
    refined_step = centre["L2"] / 0.003333333333333333
    assert ladder_step == pytest.approx(1.3333, abs=1e-3)
    assert refined_step == pytest.approx(10.08, abs=0.02)
    assert refined_step / ladder_step > 7.0


def _eig_mode1_GHz(record: Path) -> float:
    """Mode 1's Re{f} in GHz, read from the committed eig.csv."""
    path = next(record.glob("*/solver/postpro/eig.csv"))
    lines = [r for r in path.read_text().splitlines() if r.strip()]
    header = [c.strip() for c in lines[0].split(",")]
    col = next(i for i, c in enumerate(header) if c.startswith("Re{f}"))
    return float(lines[1].split(",")[col])


def _surface_q_mode1(record: Path) -> tuple[float, float]:
    """(p_Default, p_MA) for mode 1, read from the committed surface-Q.csv."""
    path = next(record.glob("*/solver/postpro/surface-Q.csv"))
    rows = [r for r in path.read_text().splitlines() if r.strip()][1:]
    cols = [c.strip() for c in rows[0].split(",")]
    return float(cols[1]), float(cols[3])


def test_r1_resolved_the_port_face_by_a_field_measure_and_still_missed_L3():
    """The record's one surviving claim, checked against the raw CSVs.

    The two surface probes share the face, thickness, permittivity and side, so
    they differ only by the tangential term and `p_MA/p_Default` is the face's
    normal-field energy fraction. R1 brings that fraction to within 6% of L3's
    for ~1% more DOF -- and its frequency still sits far below L3's. The claim
    is about a converged RATIO, never about the absolute integral, which is
    asserted here to be still moving so the two statements cannot be conflated.
    """
    baseline = REPO_ROOT / "results" / "COUPLED-LADDER-O1-L2-20260916T080802Z"
    l3 = REPO_ROOT / "results" / "COUPLED-LADDER-O1-L3-20260916T091212Z"

    pd_b, pma_b = _surface_q_mode1(baseline)
    pd_r, pma_r = _surface_q_mode1(R1_RECORD)
    pd_3, pma_3 = _surface_q_mode1(l3)

    frac_b, frac_r, frac_3 = pma_b / pd_b, pma_r / pd_r, pma_3 / pd_3
    assert frac_b == pytest.approx(0.006402, abs=5e-6)
    assert frac_r == pytest.approx(0.105803, abs=5e-6)
    assert frac_3 == pytest.approx(0.100041, abs=5e-6)

    assert frac_3 / frac_b == pytest.approx(15.63, abs=0.02), "baseline face is ~15.6x deficient"
    assert abs(frac_r - frac_3) / frac_3 < 0.06, "R1 recovers L3's normal fraction to <6%"

    # The absolute integral is NOT converged; only the ratio is. Both are stated
    # in the record and the caveat exists so they are not conflated.
    assert pd_b < pd_r < pd_3, "p_Default is still climbing monotonically"
    assert (pd_3 - pd_r) / pd_r > 0.2, "and by more than 20% from R1 to L3"

    # And having resolved the face, R1's frequency still misses L3's by far more
    # than anything the frozen tolerance would call agreement.
    f_r1 = _eig_mode1_GHz(R1_RECORD)
    f_l3 = _eig_mode1_GHz(l3)
    assert f_l3 - f_r1 == pytest.approx(0.188559, abs=1e-5)
    assert (f_l3 - f_r1) / f_r1 > 1e-1, "four orders of magnitude past the frozen 1e-4"
