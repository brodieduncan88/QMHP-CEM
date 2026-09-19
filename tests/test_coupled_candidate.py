"""Checkpoint A of the coupled-candidate milestone: declaration, register, extraction record, check script.

Everything here is software validation of a declaration and of typed records
(implementation-plan.md §5, [A]). No Palace solve is involved and nothing here
is coupled EM evidence. The geometry and mesh modules are replaced by small
fakes in the script tests so the tests stay fast and independent of gmsh; the
one test that needs gmsh is marked.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import sys
import types
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts import Candidate, master
from contracts import coupled_candidate as cc
from contracts.extraction import (
    MISSING,
    RESOLVED,
    UNRESOLVED,
    CouplingExtractionRecord,
    InteractionExtraction,
    RouteRecord,
    resolution_ratio,
)
from models.coupling_extraction import CouplingExtraction
from orchestrator import manifest
from solvers.palace import config as pconfig
from solvers.palace import mesh as pmesh
from solvers.palace import verification as V
from solvers.palace.adapter import MESH_FILENAME, OUTPUT_DIRNAME

REPO_ROOT = Path(__file__).resolve().parent.parent
DECLARATION = REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json"
REGISTER = REPO_ROOT / "config" / "coupled" / "source_register.json"
SCRIPT = REPO_ROOT / "scripts" / "coupled_candidate_check.py"
GOLDEN = REPO_ROOT / "solvers" / "palace" / "golden" / "QMHP-CEM-A-RF-000001.json"
GOLDEN_RECORD = REPO_ROOT / "results" / "PALACE-GOLDEN-20260915T030418Z" / "QMHP-CEM-A-RF-000001" / "solver"
needs_gmsh = pytest.mark.skipif(not pmesh.gmsh_available(), reason="gmsh not importable")


# --- fixtures ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def raw_declaration() -> dict:
    return json.loads(DECLARATION.read_text())


@pytest.fixture(scope="module")
def raw_register() -> dict:
    return json.loads(REGISTER.read_text())


@pytest.fixture
def payload(raw_declaration) -> dict:
    return copy.deepcopy(raw_declaration)


@pytest.fixture(scope="module")
def register() -> cc.SourceRegister:
    return cc.load_register(REGISTER)


@pytest.fixture(scope="module")
def declaration(register) -> cc.CoupledCandidateDeclaration:
    return cc.load_declaration(DECLARATION, register=register)


@pytest.fixture
def check_script():
    spec = importlib.util.spec_from_file_location("coupled_candidate_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeCell:
    """A minimal stand-in for ``solvers.palace.coupled_geometry.ChipCell``."""

    def __init__(self, decl: dict) -> None:
        self.decl = decl
        cell = decl["geometry"]["cell"]
        self.bounds = {k: cell[k] for k in ("x_min_mm", "x_max_mm", "y_min_mm", "y_max_mm",
                                            "z_substrate_bottom_mm", "z_chip_top_mm", "z_lid_mm")}

    def preview_polygons(self) -> dict:
        def rect(cx, cy, sx, sy):
            return [[cx - sx / 2, cy - sy / 2], [cx + sx / 2, cy - sy / 2], [cx + sx / 2, cy + sy / 2], [cx - sx / 2, cy + sy / 2]]

        return {
            "cell": self.bounds,
            "conductors": {"F1.island": [rect(-0.6, 0.0, 0.15, 0.15)], "R1.coupling_pad": [rect(-0.455, 0.0, 0.1, 0.1)]},
            "etch": [rect(-0.6, 0.0, 0.23, 0.23), rect(-0.455, 0.0, 0.16, 0.16)],
            "ports": {"P_F1": [rect(-0.6, -0.095, 0.02, 0.04)], "P_R1": [rect(1.1, -0.28, 0.03, 0.02), rect(1.18, -0.28, 0.03, 0.02)]},
            "port_directions": {"P_F1": ["+Y"], "P_R1": ["+X", "-X"]},
        }

    def clearance_report(self) -> list[str]:
        return []


class _FakeReport:
    def __init__(self, level: int, budget: int, out_dir: Path) -> None:
        self.level, self.budget, self.out_dir = level, budget, out_dir

    def as_dict(self) -> dict:
        tets = 20_000 * self.level
        # Shape of a real report: MEASURED mesh counts and solver-space
        # dimensions, with the per-tetrahedron ratio kept only as an estimate.
        dof2, dof1 = int(8.2 * tets), int(1.3 * tets)
        return {"level": self.level,
                "measured": {"tetrahedra": tets, "nodes": tets // 5, "edges": dof1,
                             "faces": (dof2 - 2 * dof1) // 2,
                             "dof_order1": dof1, "dof_order2": dof2},
                "estimated": {"dof_order2_from_per_tetrahedron_ratio": dof2},
                "within_budget_order2": dof2 <= self.budget, "within_budget_order1": dof1 <= self.budget,
                "dof_budget": self.budget, "mesh_path": str(self.out_dir / f"L{self.level}.msh")}


@pytest.fixture
def fake_modules(monkeypatch):
    """Install fake ``coupled_geometry`` / ``coupled_mesh`` modules the script imports lazily."""
    geometry = types.ModuleType("solvers.palace.coupled_geometry")
    geometry.chip_cell_from_declaration = lambda decl: _FakeCell(decl)
    mesh = types.ModuleType("solvers.palace.coupled_mesh")

    def dry_run(cell, level, out_dir, dof_budget=250_000, max_surface_elements=400_000):
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        if level == 3:
            raise RuntimeError("synthetic level-3 failure")
        (Path(out_dir) / f"L{level}.geo_unrolled").write_text("// fake gmsh script\n")
        return _FakeReport(level, dof_budget, Path(out_dir))

    mesh.dry_run = dry_run
    monkeypatch.setitem(sys.modules, "solvers.palace.coupled_geometry", geometry)
    monkeypatch.setitem(sys.modules, "solvers.palace.coupled_mesh", mesh)
    return geometry, mesh


# --- the committed declaration and register ------------------------------------------


def test_committed_declaration_and_register_validate(declaration, register, raw_declaration, raw_register):
    assert declaration.schema_ == cc.COUPLED_CANDIDATE_SCHEMA
    assert register.schema_ == cc.SOURCE_REGISTER_SCHEMA
    assert declaration.executable_scope.nodes == ["F1", "R1"]
    assert declaration.proposed_structure.executable is False
    # every key is modelled: the typed document round-trips to the committed file exactly
    assert declaration.to_ordered_dict() == raw_declaration
    assert list(declaration.to_ordered_dict()) == list(raw_declaration)
    assert register.to_ordered_dict() == raw_register
    assert declaration.source_ids() <= {s.id for s in register.sources}
    assert cc.sha256_of_declaration(DECLARATION) == hashlib.sha256(DECLARATION.read_bytes()).hexdigest()


def test_register_digests_verify_against_the_repository(register):
    assert register.verify(REPO_ROOT) == []


def test_every_seed_is_unapproved_and_every_unbound_is_outside_s1(declaration):
    seeds = [b for _, b in declaration.bindings() if isinstance(b, cc.EngineeringSeedBinding)]
    assert seeds and not any(b.approved for b in seeds)
    unbound = [p for p, b in declaration.bindings() if isinstance(b, cc.UnboundBinding)]
    assert unbound and not any("F1" in p and "R1" in p for p in unbound)


def test_unknown_field_is_rejected(payload):
    payload["geometry"]["features"][0]["colour"] = "blue"
    with pytest.raises(ValidationError, match="colour"):
        cc.CoupledCandidateDeclaration.model_validate(payload)


def test_unresolved_source_id_is_rejected(payload, register):
    payload["frame"]["binding"]["source_id"] = "not_in_register"
    decl = cc.CoupledCandidateDeclaration.model_validate(payload)
    with pytest.raises(ValueError, match="not_in_register"):
        decl.validate_against_register(register)


def test_approved_seed_is_rejected(payload):
    payload["geometry"]["features"][0]["binding"]["approved"] = True
    with pytest.raises(ValidationError, match="approved true; at checkpoint A"):
        cc.CoupledCandidateDeclaration.model_validate(payload)


def test_unbound_parameter_attached_to_an_s1_item_is_rejected(payload):
    entry = next(p for p in payload["parameter_register"] if p["id"] == "island_gap_mm")
    entry["binding"] = {"class": "UNBOUND", "needed_from": "nobody"}
    with pytest.raises(ValidationError, match="island_gap_mm.*UNBOUND"):
        cc.CoupledCandidateDeclaration.model_validate(payload)


def test_unbound_element_on_an_s1_node_is_rejected(payload):
    el = next(e for e in payload["proposed_structure"]["elements"] if e["id"] == "F1.junction")
    el["binding"] = {"class": "UNBOUND", "needed_from": "nobody"}
    with pytest.raises(ValidationError, match="F1.junction.*executable scope"):
        cc.CoupledCandidateDeclaration.model_validate(payload)


def test_non_axis_port_direction_is_rejected(payload):
    payload["ports"][0]["direction"] = "+XY"
    with pytest.raises(ValidationError, match="not axis-aligned"):
        cc.CoupledCandidateDeclaration.model_validate(payload)
    payload["ports"][0]["direction"] = ["+Y", "diag"]
    with pytest.raises(ValidationError, match="not axis-aligned"):
        cc.CoupledCandidateDeclaration.model_validate(payload)


def test_non_positive_port_size_is_rejected(payload):
    payload["ports"][1]["size_mm"] = [0.03, 0.0]
    with pytest.raises(ValidationError, match="size_mm must be positive"):
        cc.CoupledCandidateDeclaration.model_validate(payload)


def test_island_outside_the_cell_is_rejected(payload):
    island = next(f for f in payload["geometry"]["features"] if f["id"] == "F1.island")
    island["centre_mm"] = [-2.5, 0.0, 0.0]
    with pytest.raises(ValidationError, match="outside the cell"):
        cc.CoupledCandidateDeclaration.model_validate(payload)


def test_island_clearance_below_the_declared_minimum_is_rejected(payload):
    island = next(f for f in payload["geometry"]["features"] if f["id"] == "F1.island")
    island["centre_mm"] = [-1.5, 0.0, 0.0]        # inside the cell, 0.425 mm from the wall
    with pytest.raises(ValidationError, match="island_to_cell_wall_min"):
        cc.CoupledCandidateDeclaration.model_validate(payload)


def test_consistency_rule_must_equal_the_master_value(payload):
    payload["extraction"]["consistency_rule"]["max_relative_disagreement"] = 0.2
    with pytest.raises(ValidationError, match="differs from the master ENGINEERING-RULE"):
        cc.CoupledCandidateDeclaration.model_validate(payload)
    assert master.get("coupling_extraction.max_relative_disagreement") == payload["extraction"]["consistency_rule"]["max_relative_disagreement"] * 0.5


def test_resolution_ratio_must_equal_the_verification_rule(payload):
    payload["extraction"]["resolution_ratio"] = 5
    with pytest.raises(ValidationError, match="height_shift_to_uncertainty_min_ratio"):
        cc.CoupledCandidateDeclaration.model_validate(payload)


def test_executable_true_with_unbound_elements_is_rejected(payload):
    payload["proposed_structure"]["executable"] = True
    with pytest.raises(ValidationError, match="executable is true while elements"):
        cc.CoupledCandidateDeclaration.model_validate(payload)


def test_unknown_node_and_missing_s1_conductor_are_rejected(payload):
    bad = copy.deepcopy(payload)
    bad["executable_scope"]["nodes"] = ["F1", "R9"]
    with pytest.raises(ValidationError, match="R9"):
        cc.CoupledCandidateDeclaration.model_validate(bad)
    bad = copy.deepcopy(payload)
    next(n for n in bad["electrical_nodes"] if n["id"] == "R1")["conductor"] = None
    with pytest.raises(ValidationError, match="conductor"):
        cc.CoupledCandidateDeclaration.model_validate(bad)
    bad = copy.deepcopy(payload)
    bad["executable_scope"]["required_interactions"] = [["F1", "C"]]
    with pytest.raises(ValidationError, match="in_S1 false"):
        cc.CoupledCandidateDeclaration.model_validate(bad)


def test_register_verify_reports_changed_and_missing_files(raw_register, tmp_path):
    reg = copy.deepcopy(raw_register)
    reg["sources"][0]["sha256"] = "0" * 64
    reg["sources"][1]["path"] = "master/does_not_exist.yaml"
    mismatches = cc.SourceRegister.model_validate(reg).verify(REPO_ROOT)
    assert {m.path for m in mismatches} == {reg["sources"][0]["path"], "master/does_not_exist.yaml"}
    assert next(m for m in mismatches if m.path == "master/does_not_exist.yaml").actual is None
    assert next(m for m in mismatches if m.path == reg["sources"][0]["path"]).actual is not None


# --- the extraction record -----------------------------------------------------------


def _record(*interactions: InteractionExtraction) -> CouplingExtractionRecord:
    def route(r: str) -> RouteRecord:
        return RouteRecord(route=r, method="synthetic", record_path=f"route_{r}.json", solver_name="test",
                           solver_version="0", classification="TEST_FIXTURE")

    return CouplingExtractionRecord(
        declaration_id="QMHP-CEM-A-CC-000001", declaration_sha256="a" * 64, register_sha256="b" * 64,
        route_a=route("A"), route_b=route("B"), required_pairs=[("F1", "R1")], primary_pair=("F1", "R1"),
        interactions=list(interactions),
    )


def test_resolution_ratio_is_read_from_the_verification_rules():
    assert resolution_ratio() == V.RULES["height_shift_to_uncertainty_min_ratio"]


def test_both_zero_pair_is_unresolved_and_never_consistent():
    ie = InteractionExtraction.resolve(("F1", "R1"), 0.0, 0.5, 0.0, 0.4)
    assert ie.status == UNRESOLVED
    assert ie.consistent is None and ie.relative_disagreement is None
    assert ie.upper_bound_MHz == pytest.approx(resolution_ratio() * 0.5)
    # the underlying formula alone would have called two zeros "consistent"; the record never does
    assert CouplingExtraction(0.0, 0.0).consistent is True
    record = _record(ie)
    assert record.verdict == "INCOMPLETE"
    assert record.gate_block() is None
    assert record.interactions_block()["F1-R1"]["status"] == UNRESOLVED


def test_value_below_ten_floors_on_one_route_is_unresolved():
    ie = InteractionExtraction.resolve(("F1", "R1"), 150.0, 1.0, 150.0, 20.0)
    assert ie.status == UNRESOLVED and ie.upper_bound_MHz == pytest.approx(resolution_ratio() * 20.0)


def test_missing_route_value_is_missing():
    ie = InteractionExtraction.resolve(("F1", "R1"), None, 1.0, 150.0, 1.0)
    assert ie.status == MISSING and ie.consistent is None and ie.upper_bound_MHz is None
    assert _record(ie).verdict == "INCOMPLETE"


def test_resolved_twelve_percent_disagreement_is_inconsistent_and_never_averaged():
    ie = InteractionExtraction.resolve(("F1", "R1"), 150.0, 1.0, 169.15, 1.0)
    assert ie.status == RESOLVED
    assert ie.relative_disagreement == pytest.approx(CouplingExtraction(150.0, 169.15).relative_disagreement)
    assert ie.relative_disagreement == pytest.approx(0.12, abs=1e-3)
    assert ie.consistent is False
    record = _record(ie)
    assert record.verdict == "EXTRACTION-INCONSISTENT"
    block = record.gate_block()
    assert block == {"eigenmode_MHz": 150.0, "blackbox_MHz": 169.15}
    assert not any(v == pytest.approx((150.0 + 169.15) / 2) for v in block.values())
    assert "mean" not in ie.as_dict() and "value_MHz" not in ie.as_dict()


def test_resolved_three_percent_pair_passes():
    ie = InteractionExtraction.resolve(("F1", "R1"), 150.0, 1.0, 154.5, 1.0)
    assert ie.status == RESOLVED and ie.consistent is True
    record = _record(ie)
    assert record.verdict == "PASS"
    assert record.gate_block() == {"eigenmode_MHz": 150.0, "blackbox_MHz": 154.5}
    assert record.interactions_block() == {"F1-R1": ie.as_dict()}
    assert record.model_dump(mode="json", by_alias=True)["schema"] == "qmhp-cem.coupling-extraction-record/0.2.0"


def test_derived_fields_and_verdict_cannot_be_asserted():
    with pytest.raises(ValidationError, match="contradicts"):
        InteractionExtraction.model_validate({"pair": ["F1", "R1"], "route_a_MHz": 0.0, "route_a_floor_MHz": 0.5,
                                              "route_b_MHz": 0.0, "route_b_floor_MHz": 0.5, "status": RESOLVED, "consistent": True})
    with pytest.raises(ValidationError):
        InteractionExtraction.resolve(("F1", "R1"), 1.0, 0.0, 1.0, 1.0)     # a zero floor is not a resolution floor
    ie = InteractionExtraction.resolve(("F1", "R1"), 150.0, 1.0, 169.15, 1.0)
    data = _record(ie).model_dump(mode="json", by_alias=True)
    data["verdict"] = "PASS"
    with pytest.raises(ValidationError, match="verdict"):
        CouplingExtractionRecord.model_validate(data)


# --- the check script ----------------------------------------------------------------


def test_check_script_skip_mesh_is_deterministic_and_manifested(check_script, fake_modules, tmp_path):
    rc1 = check_script.main(["--skip-mesh", "--results-root", str(tmp_path), "--record-name", "one"])
    rc2 = check_script.main(["--skip-mesh", "--results-root", str(tmp_path), "--record-name", "two"])
    assert rc1 == rc2 == 0
    one, two = tmp_path / "one", tmp_path / "two"
    svg1, svg2 = (one / "preview.svg").read_bytes(), (two / "preview.svg").read_bytes()
    assert svg1 == svg2
    assert (one / "preview.json").read_bytes() == (two / "preview.json").read_bytes()
    text = svg1.decode()
    assert "PROPOSED ENGINEERING SEED" in text and "not approved" in text
    for label in ("F1.island", "R1.coupling_pad", "P_F1", "P_R1", "1 mm"):
        assert label in text
    assert "2026" not in text and "T" + "Z" not in text.split("<title>")[0]
    assert manifest.verify(one) == []
    recorded = dict(line.split("  ", 1)[::-1] for line in (one / "manifest.sha256").read_text().splitlines())
    assert set(recorded) == {"preview.json", "preview.svg", "report.md", "summary.json"}
    assert ".svg" in manifest.DECISION_RELEVANT_SUFFIXES and ".geo_unrolled" in manifest.DECISION_RELEVANT_SUFFIXES
    summary = json.loads((one / "summary.json").read_text())
    assert summary["validation"]["ok"] and summary["register"]["ok"]
    assert summary["declaration"]["sha256"] == cc.sha256_of_declaration(DECLARATION)
    assert summary["register"]["sha256"] == cc.sha256_of_declaration(REGISTER)
    assert summary["dry_run_mode"] == "skipped" and summary["disposition_input"] is None
    report = (one / "report.md").read_text()
    assert "coupled EM evidence" in report and "READY-FOR-REVIEW" in report


def test_check_script_dry_run_writes_disposition_input(check_script, fake_modules, tmp_path):
    rc = check_script.main(["--results-root", str(tmp_path), "--record-name", "dry", "--dof-budget", "250000"])
    assert rc == 0                       # levels 1 and 2 succeed, level 3 fails: not every level failed
    root = tmp_path / "dry"
    summary = json.loads((root / "summary.json").read_text())
    assert summary["dry_run"]["L1"]["status"] == "OK" and summary["dry_run"]["L3"]["status"] == "ERROR"
    assert "synthetic level-3 failure" in summary["dry_run"]["L3"]["error"]
    di = summary["disposition_input"]
    assert di["dof_budget"] == 250000
    assert di["levels"]["L1"] == {"status": "OK", "dof_order2": 164000, "dof_order1": 26000,
                                  "within_budget_order2": True, "within_budget_order1": True}
    assert di["levels"]["L2"]["dof_order2"] == 328000 and di["levels"]["L2"]["within_budget_order2"] is False
    assert di["levels"]["L2"]["within_budget_order1"] is True
    assert di["levels"]["L3"]["status"] == "ERROR"
    assert di["all_levels_within_budget_order2"] is False and di["all_levels_within_budget_order1"] is True
    assert summary["disposition"].startswith("READY-FOR-REVIEW") and "order 1 only" in summary["disposition"]
    assert manifest.verify(root) == []
    assert "dry_run/L1/L1.geo_unrolled" in (root / "manifest.sha256").read_text()
    assert "164000" in (root / "report.md").read_text()


def test_check_script_exits_4_when_every_level_fails(check_script, fake_modules, tmp_path):
    rc = check_script.main(["--results-root", str(tmp_path), "--record-name", "fail", "--levels", "3"])
    assert rc == 4
    summary = json.loads((tmp_path / "fail" / "summary.json").read_text())
    # The package itself is admissible; it is EXECUTION that is blocked, and the
    # two dispositions are reported separately so neither is read as the other.
    assert summary["admission_disposition"].startswith("READY-FOR-REVIEW")
    assert summary["execution_disposition"] == "BLOCKED: mesh dry run failed at every level"
    assert "EXECUTION BLOCKED" in summary["disposition"]
    assert manifest.verify(tmp_path / "fail") == []


def test_sensitivity_probe_is_unadopted_and_does_not_touch_the_declaration(check_script, fake_modules, tmp_path):
    """The probe measures variants; it must never change the declared candidate."""
    before = DECLARATION.read_bytes()
    rc = check_script.main(
        ["--results-root", str(tmp_path), "--record-name", "sens", "--levels", "1", "--sensitivity"]
    )
    assert rc == 0
    assert DECLARATION.read_bytes() == before
    summary = json.loads((tmp_path / "sens" / "summary.json").read_text())
    sens = summary["sensitivity"]
    assert "Unadopted" in sens["statement"] and "human decision" in sens["statement"]
    assert set(sens["variants"]) == {name for name, _, _ in check_script.SENSITIVITY_VARIANTS}
    for entry in sens["variants"].values():
        assert entry["changes"] and entry["status"] in {"OK", "ERROR"}
    report = (tmp_path / "sens" / "report.md").read_text()
    assert "Sensitivity probe (UNADOPTED)" in report
    assert manifest.verify(tmp_path / "sens") == []


def test_tampered_register_fails_closed_with_exit_3(check_script, fake_modules, raw_register, tmp_path):
    reg = copy.deepcopy(raw_register)
    reg["sources"][0]["sha256"] = "0" * 64                 # one digest changed
    reg["sources"][4]["path"] = "config/removed_seed.yaml"  # one path removed (file absent)
    tampered = tmp_path / "source_register.json"
    tampered.write_text(json.dumps(reg, indent=1))
    rc = check_script.main(["--skip-mesh", "--register", str(tampered), "--results-root", str(tmp_path), "--record-name", "tampered"])
    assert rc == 3
    root = tmp_path / "tampered"
    summary = json.loads((root / "summary.json").read_text())
    assert summary["register"]["ok"] is False
    assert {m["path"] for m in summary["register"]["mismatches"]} == {reg["sources"][0]["path"], "config/removed_seed.yaml"}
    assert not (root / "preview.svg").exists()             # fails closed: no preview, no mesh
    assert summary["disposition"].startswith("BLOCKED") and manifest.verify(root) == []


def test_invalid_declaration_exits_2_and_writes_nothing(check_script, payload, tmp_path):
    payload["geometry"]["features"][0]["binding"]["approved"] = True
    bad = tmp_path / "decl.json"
    bad.write_text(json.dumps(payload))
    rc = check_script.main(["--skip-mesh", "--declaration", str(bad), "--results-root", str(tmp_path / "out"), "--record-name", "x"])
    assert rc == 2
    assert not (tmp_path / "out").exists()


def test_check_script_never_touches_palace_or_docker():
    text = SCRIPT.read_text()
    for forbidden in ("docker", "PalaceSolver", "subprocess", "preflight("):
        assert forbidden not in text, forbidden


def test_preview_with_the_real_geometry_module_is_deterministic(check_script, declaration):
    geometry = pytest.importorskip("solvers.palace.coupled_geometry")
    cell = geometry.chip_cell_from_declaration(declaration.to_ordered_dict())
    a = check_script.render_preview_svg(cell.preview_polygons())
    b = check_script.render_preview_svg(geometry.chip_cell_from_declaration(declaration.to_ordered_dict()).preview_polygons())
    assert a == b and "P_R1" in a and "R1.coupling_pad" in a
    assert cell.clearance_report() == []


# --- golden untouched ---------------------------------------------------------------------


def test_golden_config_digest_unchanged_without_gmsh():
    """The golden config document (no mesh needed) still hashes to the committed record."""
    golden = Candidate.model_validate(json.loads(GOLDEN.read_text()))
    record = json.loads((GOLDEN_RECORD / "solver_input.json").read_text())
    config = pconfig.build_config(MESH_FILENAME, pconfig.solver_domain(golden), output_dir=OUTPUT_DIRNAME)
    assert config == record["config"]
    body = json.dumps(config, indent=2, sort_keys=True) + "\n"
    assert hashlib.sha256(body.encode()).hexdigest() == record["config_sha256"]


@needs_gmsh
def test_golden_prepare_still_matches_the_committed_record(tmp_path):
    """Re-run the verification suite's byte-identity test of the golden prepare()."""
    import test_verification as tv

    golden = Candidate.model_validate(json.loads(GOLDEN.read_text()))
    tv.test_golden_prepare_still_matches_the_committed_record(golden, tmp_path)


# --- the campaign index stays navigable ---------------------------------------------------


def test_every_coupled_candidate_record_is_listed_in_the_readme():
    """The index drifted nine records behind before this guard existed.

    A reader arriving at the campaign navigates from README.md. A record that is
    committed but unlisted is, for that reader, not there - and the outcome
    records are where the executed runs and their limits are written down.
    """
    docs = REPO_ROOT / "docs" / "coupled-candidate"
    readme = (docs / "README.md").read_text()
    present = {p.name for p in docs.glob("*.md")} - {"README.md"}
    linked = set(re.findall(r"\]\(([a-z0-9][a-z0-9.-]*\.md)\)", readme))

    assert not (present - linked), f"committed but unlisted: {sorted(present - linked)}"
    assert not (linked - present), f"listed but absent: {sorted(linked - present)}"


def test_the_readme_does_not_still_claim_no_solve_has_been_run():
    """It said so at checkpoint A. Seven solves later it was still saying it."""
    readme = (REPO_ROOT / "docs" / "coupled-candidate" / "README.md").read_text()
    for line in readme.splitlines():
        if "No coupled EM solve has been run" in line:
            assert line.lstrip().startswith(">"), (
                "the checkpoint-A claim may only appear inside the superseding note"
            )
    # And what IS still true must be stated, since the distinction is the point.
    assert "no coupling extraction has been run" in readme.lower()
