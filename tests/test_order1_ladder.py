"""The order-1 mesh-refinement check: its limits, and its port-field test.

The ladder is sequential and bounded: one level per invocation, order 1, a
fixed halo, the existing DOF rule and the existing cap. These tests pin those
limits to the approval record, assert the driver refuses a level it may not
run, and exercise the port-field test's verdicts in both directions — a test
that can only ever confirm its hypothesis is not a test.

Nothing here launches a solver.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

from orchestrator import manifest
from solvers.palace import mesh as pmesh
from solvers.palace.coupled_config import PORT_FIELD_PROBES, build_coupled_config
from solvers.palace.coupled_mesh import TAGS
from solvers.palace.mode_admission import ADMISSION_RULE, MATCHING_RULE, ModeRecord
from solvers.palace.outputs import PalaceOutputError, SurfaceParticipationRow, parse_surface_q_csv

REPO_ROOT = Path(__file__).resolve().parents[1]
APPROVAL = REPO_ROOT / ".github" / "ladder-approval.json"


needs_gmsh = pytest.mark.skipif(not pmesh.gmsh_available(), reason="gmsh not importable")


def _ladder():
    spec = importlib.util.spec_from_file_location(
        "palace_order1_ladder", REPO_ROOT / "scripts" / "palace_order1_ladder.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the limits are the approved ones ----------------------------------------


def test_the_driver_constants_are_the_approved_ones():
    ladder = _ladder()
    approval = json.loads(APPROVAL.read_text())
    constraints = approval["constraints"]
    assert ladder.FINITE_ELEMENT_ORDER == constraints["finite_element_order"] == 1
    assert ladder.HALO_MM == constraints["halo_mm"] == 0.08
    assert ladder.SOLVE_TIMEOUT_S == constraints["per_solve_wall_clock_cap_s"] == 2700
    assert ladder.DOF_BUDGET == constraints["dof_budget"] == 250_000
    assert approval["level"] in (2, 3), "the approval must name a dry-run level"
    measured = approval["dry_runs_first"]["measured_order1_dof"]
    assert measured[f"level_{approval['level']}"] <= ladder.DOF_BUDGET, (
        "the approved level must have been dry-run inside the DOF rule before approval"
    )
    assert constraints["dof_rule_unchanged"] and constraints["cap_unchanged"]


def test_the_approved_levels_are_inside_the_dof_rule_at_order_one_only():
    approval = json.loads(APPROVAL.read_text())
    measured = approval["dry_runs_first"]["measured_order1_dof"]
    order2 = approval["dry_runs_first"]["measured_order2_dof_for_context"]
    assert measured["level_2"] == 79_944 and measured["level_3"] == 147_372
    assert all(v <= 250_000 for v in measured.values())
    assert all(v > 250_000 for v in order2.values()), (
        "the whole reason this check is at order 1 is that order 2 does not fit"
    )


def test_the_driver_imports_the_prospective_rules_rather_than_restating_them():
    ladder = _ladder()
    source = (REPO_ROOT / "scripts" / "palace_order1_ladder.py").read_text()
    assert "from solvers.palace.mode_admission import" in source
    assert ladder.ADMISSION_RULE is ADMISSION_RULE
    assert ladder.MATCHING_RULE is MATCHING_RULE
    # The thresholds must not be re-declared here under any name.
    assert "1.0e-3" not in source and "max_energy_balance_defect" not in source


def test_the_driver_refuses_to_rerun_the_preserved_reference_level():
    ladder = _ladder()
    with pytest.raises(SystemExit) as excinfo:
        ladder.main(["--level", "1"])
    assert "preserved reference rung" in str(excinfo.value)


def test_the_driver_refuses_a_level_above_the_dof_budget(monkeypatch, tmp_path):
    """The rule is enforced before the solve, not apologised for after."""
    ladder = _ladder()

    class FakeReport:
        def as_dict(self):
            return {
                "level": 9,
                "measured": {"dof_order1": ladder.DOF_BUDGET + 1, "dof_order2": 10**7},
                "mesh_file": "x.msh",
            }

    monkeypatch.setattr(ladder, "dry_run", lambda *a, **k: FakeReport())
    declaration = json.loads((REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json").read_text())
    entry = ladder.execute_level(
        9, declaration, tmp_path, runtime="docker", image="x", np_processes=1, prepare_only=True
    )
    assert entry["status"] == "REFUSED-DOF-BUDGET"
    assert entry["within_dof_budget"] is False
    assert "not relaxed" in entry["failure"]


# --- the config the level actually runs --------------------------------------


def test_field_output_and_port_probes_are_configured_exactly_once():
    config = build_coupled_config(
        "m.msh", order=1, substrate_permittivity=11.45, port_inductance_H=1.0e-7,
        save_modes=6, port_field_probes=True,
    )
    assert config["Solver"]["Eigenmode"]["Save"] == 6
    probes = config["Boundaries"]["Postprocessing"]["Dielectric"]
    assert [p["Index"] for p in probes] == [
        PORT_FIELD_PROBES["default_index"], PORT_FIELD_PROBES["normal_index"]
    ]
    assert [p["Type"] for p in probes] == ["Default", "MA"]
    for probe in probes:
        assert probe["Attributes"] == [TAGS["port_F1"]]
        assert probe["Thickness"] == 1.0 and probe["Permittivity"] == 1.0
    # The probes are postprocessing: the operator side is untouched.
    assert config["Boundaries"]["PEC"]["Attributes"] == [TAGS["outer_pec"], TAGS["sheet_pec"]]
    assert config["Boundaries"]["LumpedPort"][0]["L"] == 1.0e-7
    assert PORT_FIELD_PROBES["changes_the_operator"] is False


def test_the_pilot_config_path_is_unchanged_by_the_new_options():
    """The existing golden/pilot behaviour must be byte-identical by default."""
    base = build_coupled_config("m.msh", order=2, substrate_permittivity=11.45, port_inductance_H=1.0e-7)
    assert base["Solver"]["Eigenmode"]["Save"] == 0
    assert "Postprocessing" not in base["Boundaries"]
    assert set(base["Boundaries"]) == {"PEC", "LumpedPort"}


def test_save_cannot_exceed_the_modes_computed():
    with pytest.raises(ValueError, match="cannot exceed"):
        build_coupled_config(
            "m.msh", order=1, substrate_permittivity=11.45, port_inductance_H=1.0e-7,
            eigenmodes=4, save_modes=5,
        )


def test_the_surface_q_parser_reads_both_probes(tmp_path):
    path = tmp_path / "surface-Q.csv"
    path.write_text(
        "               m,             p_surf[1],             Q_surf[1],"
        "             p_surf[2],             Q_surf[2]\n"
        " 1.000000000e+00,      +2.000000000e-03,      +1.000000000e+30,"
        "      +5.000000000e-04,      +1.000000000e+30\n"
    )
    rows = parse_surface_q_csv(path)
    assert rows[0].mode == 1
    assert rows[0].participation == {1: 2.0e-3, 2: 5.0e-4}


def test_the_surface_q_parser_says_why_the_file_is_absent(tmp_path):
    with pytest.raises(PalaceOutputError, match="Dielectric"):
        parse_surface_q_csv(tmp_path / "surface-Q.csv")


# --- the port-field test, in both directions ---------------------------------


def _mode(m: int, f: float, *, e_mag_frac: float, p: float) -> ModeRecord:
    electric = 1.0
    return ModeRecord(
        mode=m, frequency_GHz=f, frequency_im_GHz=0.0, backward_error=1e-12, absolute_error=1e-7,
        electric_J=electric, magnetic_J=e_mag_frac * electric, capacitive_J=0.0,
        inductive_J=p * electric,
        participation={1: p}, current_A={1: complex(1.0, 0.0)}, voltage_V={1: complex(0.0, 1.0)},
    )


def _surface(m: int, s_default: float, s_normal: float) -> SurfaceParticipationRow:
    return SurfaceParticipationRow(mode=m, participation={1: s_default, 2: s_normal}, quality_factor={})


def _scenario(kappa: float, failing_true_port: float):
    """Two admitted modes that calibrate kappa, plus one failing row.

    ``failing_true_port`` is the true port participation the synthetic fields
    encode for the failing row — the quantity the test has to recover.
    """
    admitted = [
        _mode(1, 1.0, e_mag_frac=0.002, p=0.998),
        _mode(2, 4.0, e_mag_frac=0.999, p=0.001),
    ]
    failing = _mode(3, 8.0, e_mag_frac=1.5e-5, p=1.2e-7)
    modes = [*admitted, failing]
    rows = []
    for record in admitted:
        s_t = record.abs_participation() * record.frequency_GHz**2 / kappa
        rows.append(_surface(record.mode, s_t + 0.25 * s_t, 0.25 * s_t))
    s_t = failing_true_port * failing.frequency_GHz**2 / kappa
    rows.append(_surface(failing.mode, s_t + 0.25 * s_t, 0.25 * s_t))
    return modes, rows, {1, 2}


def test_the_port_field_test_supports_explanation_two_when_the_fields_say_so():
    ladder = _ladder()
    # The failing row's true port participation restores the balance: the
    # missing stiffness is all in the tangential port field.
    modes, rows, admitted = _scenario(kappa=3.0, failing_true_port=1.0 - 1.5e-5)
    result = ladder.port_field_analysis(modes, rows, admitted_modes=admitted)
    assert result["available"]
    assert result["kappa"] == pytest.approx(3.0, rel=1e-9)
    assert result["kappa_spread_max_over_min"] == pytest.approx(1.0, rel=1e-9)
    assert result["verdict"] == "EXPLANATION-2-SUPPORTED"
    failing = [r for r in result["rows"] if not r["admitted"]][0]
    assert failing["restored_balance"] == pytest.approx(1.0, abs=1e-6)


def test_the_port_field_test_refutes_explanation_two_when_the_fields_say_so():
    ladder = _ladder()
    # The tangential port field is as small as the surrogate said: nothing is
    # recovered, so the failing row is not an eigenpair of this kind.
    modes, rows, admitted = _scenario(kappa=3.0, failing_true_port=1.2e-7)
    result = ladder.port_field_analysis(modes, rows, admitted_modes=admitted)
    assert result["verdict"] == "EXPLANATION-2-REFUTED"
    failing = [r for r in result["rows"] if not r["admitted"]][0]
    assert failing["restored_balance"] < 1e-4


def test_the_port_field_test_reports_an_unsound_calibration_rather_than_a_verdict():
    ladder = _ladder()
    modes, rows, admitted = _scenario(kappa=3.0, failing_true_port=0.9)
    # Break one admitted mode's probe so the two disagree about kappa.
    rows = [_surface(r.mode, r.participation[1] * (10.0 if r.mode == 2 else 1.0),
                     r.participation[2]) for r in rows]
    result = ladder.port_field_analysis(modes, rows, admitted_modes=admitted)
    assert result["verdict"] == "CALIBRATION-UNSOUND"
    assert result["kappa_spread_max_over_min"] > 2.0


def test_the_port_field_test_flags_a_cauchy_schwarz_violation_as_its_own_framing_failing():
    ladder = _ladder()
    # The surrogate exceeding the true port energy is forbidden; if it happens,
    # the framing is wrong, not one of the two explanations.
    modes, rows, admitted = _scenario(kappa=3.0, failing_true_port=1.0e-9)
    result = ladder.port_field_analysis(modes, rows, admitted_modes=admitted)
    assert result["verdict"] == "FRAMING-FALSIFIED"


def test_the_port_field_test_needs_an_admitted_mode_to_calibrate_against():
    ladder = _ladder()
    modes, rows, _ = _scenario(kappa=3.0, failing_true_port=0.9)
    result = ladder.port_field_analysis(modes, rows, admitted_modes=set())
    assert result["available"] is False
    assert "kappa cannot be calibrated" in result["reason"]


def test_the_tangential_probe_is_the_difference_of_the_two_configured_probes():
    ladder = _ladder()
    modes, rows, admitted = _scenario(kappa=2.0, failing_true_port=0.5)
    result = ladder.port_field_analysis(modes, rows, admitted_modes=admitted)
    for row, source in zip(result["rows"], rows):
        assert row["s_tangential"] == pytest.approx(
            source.participation[1] - source.participation[2]
        )
        assert math.isfinite(row["normal_fraction"])


def test_the_field_output_path_is_derived_from_the_configured_output_dir():
    """Palace writes paraview/ UNDER Problem.Output, not beside it.

    The level-2 rung looked beside it, reported the output as absent although
    Palace had written it, and so committed 123 MB it had said it would not.
    """
    source = (REPO_ROOT / "scripts" / "palace_order1_ladder.py").read_text()
    assert 'solver_dir / "paraview"' not in source, "the path must not be hard-coded beside postpro"
    assert 'config["Problem"]["Output"]' in source
    # The record must be able to say where it put the output, not just whether.
    assert '"path": str(paraview.relative_to(solver_dir)) if written else None' in source


def test_the_level_two_record_is_free_of_uncommittable_field_output():
    """surface-Q.csv is the evidence; the 120 MB paraview tree is not committed."""
    records = sorted((REPO_ROOT / "results").glob("COUPLED-LADDER-O1-L2-*"))
    if not records:
        pytest.skip("the level-2 record is not present")
    record = records[-1]
    assert not list(record.rglob("*.vtu")), "ParaView volume output must not be committed"
    assert not list(record.rglob("*.pvtu"))
    assert (record / "L2" / "solver" / "postpro" / "surface-Q.csv").exists()
    total = sum(f.stat().st_size for f in record.rglob("*") if f.is_file())
    assert total < 20 * 1024 * 1024, f"the record is {total / 1e6:.0f} MB"


# --- the report must survive every refusal the estimator can return ----------


def _three_rung_summary(frequencies: dict[str, list[float]]) -> dict:
    """A level-3 summary built from explicit frequency sequences."""
    ladder = _ladder()
    h = [0.01, 0.01 * 2.0 / 3.0, 0.005]
    series = {}
    for i, (key, values) in enumerate(frequencies.items(), start=1):
        series[key] = {
            "points": [
                {
                    "level": level, "h_gap_mm": hh, "mode": i,
                    "frequency_GHz": f, "abs_participation": 0.5 / i, "dof": dof,
                }
                for level, hh, f, dof in zip((1, 2, 3), h, values, (39832, 79944, 147372))
            ],
            "role": "LUMPED_DOMINATED" if i == 1 else "FIELD_DOMINATED",
        }
    convergence = ladder.convergence_over_rungs(series)
    convergence["available"] = True
    projections = {
        key: ladder.order_two_projection(
            convergence, {1: 39832, 2: 79944, 3: 147372}, {1: 208670, 2: 420664, 3: 781554},
            {1: h[0], 2: h[1], 3: h[2]},
            {"mode": key, "level": 1, "frequency_GHz": 1.707441654},
            ladder.FROZEN_FREQUENCY_TOLERANCE,
        )
        for key in series
    }
    return {
        "batch_id": "COUPLED-LADDER-O1-L3-TEST", "statement": "test", "level": 3,
        "dry_runs": {}, "rung": {"status": "COMPLETED", "dof_measured": 147372, "admission": {"modes": []}},
        "comparison": {"available": False, "reason": "test"},
        "rungs": [
            {"level": 1, "h_gap_mm": h[0], "dof": 39832, "wall_clock_s": 32.4, "source": "P2"},
            {"level": 2, "h_gap_mm": h[1], "dof": 79944, "wall_clock_s": 81.2, "source": "L2"},
            {"level": 3, "h_gap_mm": h[2], "dof": 147372, "wall_clock_s": None, "source": "L3"},
        ],
        "tracking": {"available": True, "transitivity_note": "ok", "series": series},
        "convergence": convergence,
        "asymptotic": ladder.asymptotic_assessment(convergence),
        "order_two_projection": {"available": True, "per_mode": projections, "match": {}},
        "port_field_reproduction": {"L2": "EXPLANATION-2-SUPPORTED", "L3": None},
        "trend": {"available": False},
        "next_level": {"level": 4, "dof_measured": None, "dof_budget": 250_000,
                       "within_dof_budget": False, "cap_s": 2700, "projected_wall_clock": None,
                       "decision": "FOR REVIEW"},
    }


CONVERGING = [1.158333, 1.461887, 1.55]        # solvable
NOT_SHRINKING = [1.0, 1.1, 1.2]                # no positive order
NON_MONOTONE = [1.0, 1.2, 1.1]                 # no power law


@pytest.mark.parametrize(
    "first,second",
    [
        (CONVERGING, CONVERGING),
        (CONVERGING, NOT_SHRINKING),
        (NOT_SHRINKING, CONVERGING),   # the case that crashed the level-3 run
        (NOT_SHRINKING, NOT_SHRINKING),
        (NON_MONOTONE, CONVERGING),
        (NON_MONOTONE, NON_MONOTONE),
    ],
    ids=["both-ok", "second-refuses", "first-refuses", "both-refuse", "first-non-monotone", "both-non-monotone"],
)
def test_the_report_renders_whatever_the_estimator_returns(first, second):
    """A report that crashes on a negative result loses the negative result.

    The level-3 run refused an order on its FIRST tracked mode and the renderer
    raised, so the record was never manifested, never uploaded and never
    committed, and the solve's outputs were lost. Every combination is covered
    here, not just the one that failed.
    """
    ladder = _ladder()
    summary = _three_rung_summary({"L1m1": first, "L1m2": second})
    text = ladder.render_report(summary)
    assert "Order-1 mesh-refinement check" in text
    assert "## 6. Convergence over the rungs" in text
    for key, values in (("L1m1", first), ("L1m2", second)):
        if values is CONVERGING:
            assert "observed order" in text
        else:
            assert "no order of convergence" in text
    # A refusal must be explained, never silently blank.
    if NOT_SHRINKING in (first, second):
        assert "floor" in text
    if NON_MONOTONE in (first, second):
        assert "not monotone" in text


def test_the_report_says_so_when_nothing_can_be_projected():
    ladder = _ladder()
    summary = _three_rung_summary({"L1m1": NOT_SHRINKING, "L1m2": NON_MONOTONE})
    text = ladder.render_report(summary)
    assert "Not projectable" in text
    assert "no continuum value" in text


def test_the_report_tolerates_a_missing_wall_clock():
    ladder = _ladder()
    summary = _three_rung_summary({"L1m1": CONVERGING, "L1m2": CONVERGING})
    assert summary["rungs"][2]["wall_clock_s"] is None
    assert "| — |" in ladder.render_report(summary)


@needs_gmsh
@pytest.mark.slow
def test_a_ladder_renderer_failure_is_exercised_and_loses_no_evidence(tmp_path, monkeypatch):
    """The ordering test below reads the source; this one makes it happen.

    ``--prepare-only`` meshes and writes the record without launching Palace,
    so the whole record-writing path runs for real. The renderer is then made
    to raise the way it did on the level-3 run's first attempt, and everything
    that attempt lost has to survive: the raw summary, the manifest, the record
    pointer the workflow uploads and commits by, and a non-zero exit.
    """
    ladder = _ladder()
    monkeypatch.setattr(
        ladder, "render_report",
        lambda summary: (_ for _ in ()).throw(KeyError("target_relative_frequency_error")),
    )
    # Pin the approval this test runs under. Without --approval the driver reads
    # the live .github/ladder-approval.json, so whatever is approved at the time
    # silently changes what this test exercises - it built the R1 mesh once the
    # owner approved R1, and asserted the plain rung's DOF against it.
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({"level": 2}))
    pointer = tmp_path / "pointer"
    code = ladder.main([
        "--level", "2", "--prepare-only",
        "--approval", str(approval),
        "--results-root", str(tmp_path / "results"),
        "--record-pointer", str(pointer),
    ])
    assert code == 1, "a rendering failure must be reported, not swallowed"

    record = Path(pointer.read_text().strip())
    assert record.is_dir(), "the record pointer must name the record the workflow uploads"
    assert manifest.verify(record) == [], "the record must be manifested despite the failure"
    summary = json.loads((record / "summary.json").read_text())
    assert summary["rung"]["status"] == "PREPARED"
    assert summary["rung"]["port_refinement"] is None, "the pinned approval refines nothing"
    assert summary["rung"]["dof_measured"] == 79_944
    report = (record / "report.md").read_text()
    assert "could not be rendered" in report
    assert "not a loss of evidence" in report
    assert "target_relative_frequency_error" in report
    assert manifest.unexpected_files(record) == [], "and it must still be committable"


@needs_gmsh
@pytest.mark.slow
def test_a_refined_run_survives_a_renderer_failure_and_stays_off_the_h_sequence(
    tmp_path, monkeypatch
):
    """The same guarantee on the path that had never been exercised.

    A prepare-only run under a port-refined approval, with the renderer made to
    raise. The record must survive, carry the refinement, measure the approved
    mesh, and be excluded from the convergence fit it is not a point on.
    """
    ladder = _ladder()
    monkeypatch.setattr(
        ladder, "render_report", lambda summary: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({
        "level": 2,
        "baseline_record": "COUPLED-LADDER-O1-L2-20260916T080802Z",
        "port_refinement": {
            "id": "R1", "h_port_mm": 0.003333333333333333,
            "pad_mm": 0.010, "transition_mm": 0.020, "ports": ["port_F1"],
        },
        "dry_run_mesh_sha256": {
            "R1": "a49ef282c7f07c56f210a450b291a2e027de530ba7c3e78bbdcead3b67315fee",
        },
    }))
    pointer = tmp_path / "pointer"
    code = ladder.main([
        "--level", "2", "--prepare-only",
        "--approval", str(approval),
        "--results-root", str(tmp_path / "results"),
        "--record-pointer", str(pointer),
    ])
    assert code == 1

    record = Path(pointer.read_text().strip())
    assert "-R1-" in record.name, "a refined run gets its own record id"
    assert manifest.verify(record) == []
    summary = json.loads((record / "summary.json").read_text())
    rung = summary["rung"]
    assert rung["status"] == "PREPARED"
    assert rung["dof_measured"] == 80_762
    assert rung["mesh"]["sha256"] == (
        "a49ef282c7f07c56f210a450b291a2e027de530ba7c3e78bbdcead3b67315fee"
    )
    assert rung["port_refinement"]["h_port_mm"] == 0.003333333333333333
    assert summary["next_level"]["decision"].startswith("STOP")
    # The fit is the three plain rungs; this run is not one of them.
    assert [r["level"] for r in summary["rungs"]] == [1, 2, 3]
    assert not any("R1" in r["source"] for r in summary["rungs"])


@needs_gmsh
@pytest.mark.slow
def test_a_mesh_that_is_not_the_approved_one_is_never_solved(tmp_path):
    """The hash gate: the run solves the approved mesh or it solves nothing."""
    ladder = _ladder()
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({
        "level": 2,
        "port_refinement": {
            "id": "R1", "h_port_mm": 0.003333333333333333,
            "pad_mm": 0.010, "transition_mm": 0.020, "ports": ["port_F1"],
        },
        "dry_run_mesh_sha256": {"R1": "0" * 64},
    }))
    pointer = tmp_path / "pointer"
    ladder.main([
        "--level", "2", "--prepare-only",
        "--approval", str(approval),
        "--results-root", str(tmp_path / "results"),
        "--record-pointer", str(pointer),
    ])
    summary = json.loads((Path(pointer.read_text().strip()) / "summary.json").read_text())
    assert summary["rung"]["status"] == "REFUSED-MESH-MISMATCH"
    assert "not the " + "0" * 64 in summary["rung"]["failure"]


def test_the_record_is_made_durable_before_the_report_is_rendered():
    """Presentation must not be able to destroy evidence.

    summary.json and the record pointer are written first; a rendering failure
    is captured into report.md and reported as a non-zero exit, but the record
    is still manifested.
    """
    source = (REPO_ROOT / "scripts" / "palace_order1_ladder.py").read_text()
    write_summary = source.index('"summary.json").write_text')
    write_pointer = source.index("Path(args.record_pointer).write_text")
    render = source.index("report = render_report(summary)")
    write_manifest = source.index("manifest.write(record_dir)")
    assert write_summary < write_pointer < render < write_manifest
    assert "except Exception as exc:  # noqa: BLE001 - the record still has to survive" in source
    assert "This is a presentation failure, not a loss of evidence." in source


def test_the_level_three_record_reports_no_order_of_convergence():
    """The negative result is the result, and it must survive in the record."""
    records = sorted((REPO_ROOT / "results").glob("COUPLED-LADDER-O1-L3-*"))
    if not records:
        pytest.skip("the level-3 record is not present")
    summary = json.loads((records[-1] / "summary.json").read_text())
    convergence = summary["convergence"]
    assert convergence["available"]
    per_mode = convergence["per_mode"]
    assert len(per_mode) == 2
    for entry in per_mode.values():
        assert entry["frequency"]["solvable"] is False
        assert "no positive order of convergence" in entry["frequency"]["reason"]
    assert summary["asymptotic"]["still_clearly_pre_asymptotic"] is True
    assert summary["order_two_projection"]["available"] is True
    assert all(
        not p.get("available") for p in summary["order_two_projection"]["per_mode"].values()
    ), "no extrapolated limit means no order-2 projection"
    # And the report rendered rather than crashing on it.
    report = (records[-1] / "report.md").read_text()
    assert "no order of convergence" in report
    assert "Not projectable" in report
    assert "could not be rendered" not in report


def test_the_calibration_fix_this_record_proposed_is_withdrawn_not_applied():
    """The level-3 record proposed a repair for a procedure that no longer exists.

    It would have calibrated the probe constant on the modes where the
    surrogate is faithful, using ``p_true = 1 - (E_mag + E_cap)/(E_elec +
    E_cap)`` as the reference. Two problems, both now recorded in the outcome
    document: the constant is computable from pinned source and needs no
    calibration at all, and ``p_true`` so defined is *inferred from the energy
    closure*, so confirming the closure with it would be circular. The
    measurements the proposal rested on are unchanged and still hold, which is
    what the rest of this test checks.
    """
    doc = re.sub(
        r"\s+", " ",
        (REPO_ROOT / "docs" / "coupled-candidate" / "order1-ladder-outcome.md").read_text(),
    )
    assert "The proposed fix is withdrawn" in doc
    assert "would be circular" in doc
    assert "is not circular" not in doc
    assert "s1-numerical-recovery.md" in doc

    records = sorted((REPO_ROOT / "results").glob("COUPLED-LADDER-O1-L3-*"))
    if not records:
        pytest.skip("the level-3 record is not present")
    summary = json.loads((records[-1] / "summary.json").read_text())
    rows = {r["mode"]: r for r in summary["rung"]["port_field_test"]["rows"]}
    # The observation that motivated the proposal stands: the surrogate is
    # faithful on the two in-window admitted modes and not on the third.
    for mode in (1, 2):
        p_true = 1.0 - rows[mode]["E_mag_over_E_elec"]
        assert rows[mode]["reported_participation"] == pytest.approx(p_true, rel=1e-3)
    p_true_6 = 1.0 - rows[6]["E_mag_over_E_elec"]
    assert rows[6]["reported_participation"] / p_true_6 < 0.1
    assert rows[6]["admitted"] is True
    # And the CALIBRATION-UNSOUND verdict is preserved, not quietly rewritten.
    assert summary["rung"]["port_field_test"]["verdict"] == "CALIBRATION-UNSOUND"
