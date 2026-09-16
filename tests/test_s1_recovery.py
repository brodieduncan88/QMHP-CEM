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


def test_the_committed_approval_record_authorises_no_refinement():
    """Nothing in this change starts an experiment; approving it is a later act."""
    assert _ladder_module().approved_port_refinement() is None
    approval = json.loads((REPO_ROOT / ".github" / "ladder-approval.json").read_text())
    assert "port_refinement" not in approval


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
