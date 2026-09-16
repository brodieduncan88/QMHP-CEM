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
from pathlib import Path

import pytest

from solvers.palace.coupled_config import PORT_FIELD_PROBES, build_coupled_config
from solvers.palace.coupled_mesh import TAGS
from solvers.palace.mode_admission import ADMISSION_RULE, MATCHING_RULE, ModeRecord
from solvers.palace.outputs import PalaceOutputError, SurfaceParticipationRow, parse_surface_q_csv

REPO_ROOT = Path(__file__).resolve().parents[1]
APPROVAL = REPO_ROOT / ".github" / "ladder-approval.json"


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
