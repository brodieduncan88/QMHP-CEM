"""Mesh-refinement and height-sensitive verification (spec §15): rules, matching, records.

Everything here runs without a container. The analytic checks are exact; the
verdict functions are exercised on synthetic run results so that a missing,
unconverged or wrongly-meshed run can never pass; the campaign executor is
exercised in prepare-only mode (meshes only) where gmsh is importable.
"""

from __future__ import annotations

import importlib.util
import json
import math
import platform
from pathlib import Path

import pytest

from contracts import Candidate
from orchestrator import manifest
from solvers import RunContext
from solvers.palace import analytic
from solvers.palace import config as pconfig
from solvers.palace import mesh as pmesh
from solvers.palace import outputs as pout
from solvers.palace import verification as V
from solvers.palace.adapter import PalaceSolver

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN = REPO_ROOT / "solvers" / "palace" / "golden" / "QMHP-CEM-A-RF-000001.json"
GOLDEN_RECORD = REPO_ROOT / "results" / "PALACE-GOLDEN-20260915T030418Z" / "QMHP-CEM-A-RF-000001" / "solver"
needs_gmsh = pytest.mark.skipif(not pmesh.gmsh_available(), reason="gmsh not importable")

BOX = V.object001_box()


@pytest.fixture
def golden() -> Candidate:
    return Candidate.model_validate(json.loads(GOLDEN.read_text()))


# --- original golden defaults remain unchanged ------------------------------------


@needs_gmsh
def test_golden_prepare_still_matches_the_committed_record(golden, tmp_path):
    """No override: the prepared input is what the committed golden record carries."""
    record = json.loads((GOLDEN_RECORD / "solver_input.json").read_text())
    prepared = PalaceSolver().prepare(golden, None, RunContext(run_id="x", work_dir=tmp_path / "s"))
    for key in ("config", "config_sha256", "analytic_reference", "expected_solver_modes_GHz", "solver_domain_mm", "solver_rules"):
        assert prepared.payload[key] == record[key], key
    assert "overrides" not in prepared.payload and "effective" not in prepared.payload
    assert prepared.payload["mesh"]["characteristic_length_mm"] == record["mesh"]["characteristic_length_mm"]
    assert prepared.payload["mesh"]["tetrahedron_count"] == record["mesh"]["tetrahedron_count"]
    same_platform = platform.system() == "Linux" and platform.machine() == "x86_64"
    if same_platform and prepared.payload["mesh"]["gmsh_version"] == record["mesh"]["gmsh_version"]:
        assert prepared.payload["mesh"]["sha256"] == record["mesh"]["sha256"]


def test_golden_config_document_unchanged_by_the_new_keywords(golden):
    d = pconfig.solver_domain(golden)
    assert pconfig.build_config("mesh.msh", d) == pconfig.build_config("mesh.msh", d, eigenmodes=None, target_GHz=None, probes_mm=None)
    assert "Postprocessing" not in pconfig.build_config("mesh.msh", d)["Domains"]
    assert d.mesh_length_mm is None and d.characteristic_length_mm == pytest.approx(22.0 / 12.0)
    assert "mesh_length_mm" not in d.as_dict()


def test_unknown_override_is_rejected(golden, tmp_path):
    ctx = RunContext(run_id="x", work_dir=tmp_path / "s", extra={"palace": {"mesh_size": 1.0}})
    with pytest.raises(ValueError, match="unknown Palace override"):
        PalaceSolver().prepare(golden, None, ctx)


# --- mesh-resolution and eigen overrides --------------------------------------------


@needs_gmsh
def test_mesh_length_override_refines_only_the_mesh(golden, tmp_path):
    base = PalaceSolver().prepare(golden, None, RunContext(run_id="x", work_dir=tmp_path / "a"))
    fine = PalaceSolver().prepare(
        golden, None,
        RunContext(run_id="x", work_dir=tmp_path / "b", extra={"palace": {"mesh_length_mm": 22.0 / 24.0}}),
    )
    assert fine.payload["mesh"]["characteristic_length_mm"] == pytest.approx(22.0 / 24.0)
    assert fine.payload["mesh"]["tetrahedron_count"] > 2 * base.payload["mesh"]["tetrahedron_count"]
    assert fine.payload["config"] == base.payload["config"]          # physics, order, tolerances, target untouched
    assert fine.payload["expected_solver_modes_GHz"] == base.payload["expected_solver_modes_GHz"]
    assert fine.payload["overrides"] == {"mesh_length_mm": 22.0 / 24.0}
    assert fine.payload["effective"]["eigenmodes_requested"] == 4


@needs_gmsh
def test_domain_mode_count_target_and_probe_overrides(tmp_path, golden):
    box = V.CavityBox(22.0, 22.0, 7.0)
    target, f_mode, _ = V.height_target_GHz(box, (0, 1, 1))
    spec = V.RunSpec(name="t", benchmark="aux_height", role="height", cavity=box, level=1,
                     mesh_length_mm=1.75, eigenmodes=6, target_GHz=target, probes=True, timeout_s=10, height_mode=(0, 1, 1))
    prepared = PalaceSolver().prepare(golden, None, RunContext(run_id="x", work_dir=tmp_path / "s", extra={"palace": spec.overrides()}))
    cfg = prepared.payload["config"]
    assert cfg["Solver"]["Eigenmode"]["N"] == 6
    assert cfg["Solver"]["Eigenmode"]["Target"] == pytest.approx(target, abs=1e-6)
    assert cfg["Solver"]["Eigenmode"]["Tol"] == pconfig.SOLVER_RULES["eigenvalue_tolerance"]   # unchanged
    assert cfg["Solver"]["Order"] == pconfig.SOLVER_RULES["finite_element_order"]
    probes = cfg["Domains"]["Postprocessing"]["Probe"]
    assert [p["Index"] for p in probes] == [1, 2, 3]
    for p in probes:
        x, y, z = p["Center"]
        assert -11 < x < 11 and -11 < y < 11 and 0 < z < 7.0
    assert prepared.payload["solver_domain_mm"]["z_max_mm"] == 7.0
    assert prepared.payload["expected_solver_modes_GHz"][:2] == pytest.approx([f_mode, f_mode])
    assert any(m["p"] >= 1 for m in prepared.payload["analytic_reference"])
    text = (tmp_path / "s" / "mesh.msh").read_text()
    assert text.startswith("$MeshFormat")


# --- analytic: height independence and dependence, completeness ----------------------


def test_p0_modes_are_height_independent():
    for d in (1.5, 1.65, 7.0, 7.7, 100.0):
        assert analytic.mode_frequency_GHz(22, 22, d, 1, 1, 0) == pytest.approx(9.635694545471965, rel=1e-12)
        assert analytic.mode_frequency_GHz(22, 22, d, 2, 1, 0) == analytic.mode_frequency_GHz(22, 22, d, 1, 2, 0)


def test_p1_modes_depend_on_height_exactly():
    for d1, d2 in ((1.5, 1.65), (7.0, 7.7)):
        f1, f2 = (analytic.mode_frequency_GHz(22, 22, d, 0, 1, 1) for d in (d1, d2))
        assert f2 < f1
        c = analytic.C_M_PER_S
        for d, f in ((d1, f1), (d2, f2)):
            assert f == pytest.approx(0.5 * c * math.sqrt((1 / 0.022) ** 2 + (1 / (d * 1e-3)) ** 2) / 1e9, rel=1e-12)
    assert analytic.mode_frequency_GHz(22, 22, 1.5, 0, 1, 1) == pytest.approx(100.16283, abs=1e-4)
    assert analytic.mode_frequency_GHz(22, 22, 7.0, 0, 1, 1) == pytest.approx(22.47158, abs=1e-4)


def test_range_aware_enumeration_is_complete_against_brute_force():
    for d, f_max in ((1.5, 105.0), (7.0, 30.0), (1.65, 95.0)):
        found = analytic.rectangular_cavity_modes_below(22, 22, d, f_max)
        brute: dict[float, int] = {}
        for m in range(0, 40):
            for n in range(0, 40):
                for p in range(0, 40):
                    if (m == 0) + (n == 0) + (p == 0) >= 2:
                        continue
                    f = analytic.mode_frequency_GHz(22, 22, d, m, n, p)
                    if f <= f_max:
                        brute[round(f, 9)] = brute.get(round(f, 9), 0) + (2 if (m and n and p) else 1)
        assert {round(x.frequency_GHz, 9): x.multiplicity for x in found} == brute
    below = V.modes_counted_below(BOX, analytic.mode_frequency_GHz(22, 22, 1.5, 0, 1, 1))
    assert below == 154      # far beyond any fixed index cap of 6


def test_index_bounds_are_exact():
    m_max, _, p_max = analytic.index_bounds(22, 22, 1.5, 100.0)
    assert analytic.mode_frequency_GHz(22, 22, 1.5, m_max, 0, 1) > 0     # a valid triple
    assert analytic.mode_frequency_GHz(22, 22, 1.5, m_max + 1, 1, 0) > 100.0
    assert p_max == 1 and analytic.mode_frequency_GHz(22, 22, 1.5, 0, 1, 2) > 100.0


def test_lowest_modes_helper_is_unchanged_and_complete():
    old_style = analytic.rectangular_cavity_modes(22, 22, 1.5, count=8, max_index=6)
    below = analytic.rectangular_cavity_modes_below(22, 22, 1.5, 40.0)[:8]
    assert [(m.m, m.n, m.p, m.multiplicity) for m in old_style] == [(m.m, m.n, m.p, m.multiplicity) for m in below]
    assert [m.frequency_GHz for m in old_style] == [m.frequency_GHz for m in below]


def test_expected_modes_start_at_the_target():
    box = V.CavityBox(22, 22, 7.0)
    target, f_mode, f_prev = V.height_target_GHz(box, (0, 1, 1))
    assert f_prev < target < f_mode
    modes = analytic.expected_solver_modes(22, 22, 7.0, 6, f_min_GHz=target)
    assert modes[:2] == pytest.approx([f_mode, f_mode])
    assert all(f >= target for f in modes)


# --- mode matching ---------------------------------------------------------------------


def test_degenerate_pair_matching_honours_multiplicity():
    box = V.CavityBox(22, 22, 7.0)
    f = box.frequency(0, 1, 1)
    decisions = V.match_modes([f * (1 + 2e-5), f * (1 - 1e-5), f * (1 + 8e-5)], box, f * 1.1)
    labels = [d["analytic"] for d in decisions]
    assert labels[:2] == ["analytic_011", "analytic_011"]
    assert labels[2] is None and decisions[2]["decision"].startswith("unmatched")
    assert V.height_mode_frequencies(decisions, (0, 1, 1), box) == sorted([f * (1 - 1e-5), f * (1 + 2e-5)])


def test_probe_family_check_flags_a_wrong_family():
    box = V.CavityBox(22, 22, 7.0)
    f = box.frequency(0, 1, 1)
    ok = V.match_modes([f, f], box, f * 1.1, z_fraction={1: 0.0, 2: 0.02})
    assert all(d["consistent"] is True and d["decision"] == "matched" for d in ok)
    bad = V.match_modes([f, f], box, f * 1.1, z_fraction={1: 0.99, 2: 0.0})
    assert bad[0]["consistent"] is False and "disagrees" in bad[0]["decision"]
    assert V.height_mode_frequencies(bad, (0, 1, 1), box) == [f]     # the inconsistent one is not counted
    f220 = box.frequency(2, 2, 0)
    p0 = V.match_modes([f220], box, f220 * 1.1, z_fraction={1: 0.999})
    assert p0[0]["analytic"] == "analytic_220" and p0[0]["consistent"] is True
    assert V.classify_family(None) == "unknown"


# --- verdicts on synthetic results: missing/unconverged never pass ------------------------


def _ladder(errors: list[list[float]], statuses=None, bkwd=1e-11):
    expected = pconfig.expected_solver_modes_GHz(BOX.domain())
    out = []
    for level, errs in enumerate(errors, start=1):
        lc = (22.0 / 12.0) / V.RULES["refinement_factors"][level - 1]
        status = (statuses or ["CONVERGED"] * len(errors))[level - 1]
        out.append(V.RunResult(
            name=f"ladder-L{level}", status=status, mesh_length_mm=lc, nodes=100 * level, tetrahedra=1000 * level,
            dof=8000 * level, mesh_sha256="a" * 64,
            frequencies_GHz=[e0 * (1 + e) for e0, e in zip(expected, errs)] if status == "CONVERGED" else [],
            backward_errors=[bkwd] * 4 if status == "CONVERGED" else [], backward_error_max=(bkwd if status == "CONVERGED" else None),
            palace_status=("CONVERGED" if status == "CONVERGED" else "NOT_CONVERGED"),
        ))
    return out, expected


def test_mesh_convergence_pass_and_tables():
    levels, expected = _ladder([[2e-5, 5e-6, 2e-5, 5e-5], [6e-6, 2e-6, 6e-6, 1.5e-5], [1e-6, 5e-7, 1e-6, 3e-6]])
    table = V.mesh_convergence_table(levels, expected)
    assert [r["run"] for r in table] == ["ladder-L1", "ladder-L2", "ladder-L3"]
    assert table[0]["relative_change_vs_previous_level"] is None
    assert table[2]["max_abs_relative_change_vs_previous_level"] == pytest.approx(1.2e-5, rel=1e-3)
    v = V.mesh_convergence_verdict(table)
    assert v["verdict"] == V.PASS
    pair = V.degenerate_pair_table(levels)
    # The synthetic errors 5e-6 and 2e-5 on the exactly degenerate pair imply this splitting.
    assert pair[0]["splitting_MHz"] == pytest.approx(expected[1] * (2e-5 - 5e-6) * 1e3, rel=1e-6)
    assert pair[0]["centre_GHz"] == pytest.approx(expected[1] * (1 + 1.25e-5), rel=1e-9)
    assert pair[2]["splitting_MHz"] < pair[0]["splitting_MHz"]      # shrinks with refinement here
    assert "not physical coupling" in pair[0]["note"]


def test_mesh_convergence_fails_when_the_finest_level_disagrees_or_still_moves():
    levels, expected = _ladder([[2e-5] * 4, [1e-5] * 4, [3e-4] * 4])
    assert V.mesh_convergence_verdict(V.mesh_convergence_table(levels, expected))["verdict"] == V.FAIL
    levels, expected = _ladder([[5e-4] * 4, [2.5e-4] * 4, [5e-5] * 4])   # within analytic tol but changing > 1e-4
    assert V.mesh_convergence_verdict(V.mesh_convergence_table(levels, expected))["verdict"] == V.FAIL
    levels, expected = _ladder([[1e-5] * 4] * 3, bkwd=5e-6)                # backward error above the unchanged rule
    assert V.mesh_convergence_verdict(V.mesh_convergence_table(levels, expected))["verdict"] == V.FAIL


def test_mesh_convergence_incomplete_with_missing_or_unconverged_levels():
    levels, expected = _ladder([[1e-5] * 4, [1e-6] * 4])
    assert V.mesh_convergence_verdict(V.mesh_convergence_table(levels, expected))["verdict"] == V.INCOMPLETE
    levels, expected = _ladder([[1e-5] * 4, [1e-6] * 4, [1e-7] * 4], statuses=["CONVERGED", "CONVERGED", "NOT_CONVERGED"])
    assert V.mesh_convergence_verdict(V.mesh_convergence_table(levels, expected))["verdict"] == V.INCOMPLETE
    levels, expected = _ladder([[1e-5] * 4, [1e-6] * 4, [1e-7] * 4], statuses=["CONVERGED", "RUN_FAILED", "CONVERGED"])
    verdict = V.mesh_convergence_verdict(V.mesh_convergence_table(levels, expected))
    assert verdict["verdict"] == V.INCOMPLETE


AUX = next(b for b in V.height_benchmarks() if b.name == "aux_height")


def _height_results(bench: V.HeightBenchmark, errors_by_level: dict[float, tuple[float, float]], *,
                    status="CONVERGED", wrong_z=False, identify=True):
    """Synthetic converged runs at both heights; errors are per (height1, height2)."""
    results: dict[str, list[V.RunResult]] = {}
    decisions: dict[str, list[dict]] = {}
    for d in bench.heights_mm:
        box = bench.box(d)
        f_true = box.frequency(*bench.mode)
        for lc, (e1, e2) in errors_by_level.items():
            err = e1 if d == bench.heights_mm[0] else e2
            f_used = bench.box(bench.heights_mm[0]).frequency(*bench.mode) if wrong_z else f_true
            freqs = sorted([f_used * (1 + err), f_used * (1 + err * 1.1), f_used * 1.04, f_used * 1.08])
            name = f"{bench.name}-d{d:g}-L{lc}"
            rr = V.RunResult(name=name, status=status, mesh_length_mm=lc, frequencies_GHz=freqs if status == "CONVERGED" else [],
                             backward_error_max=1e-11, palace_status=status)
            results.setdefault(f"{d:g}", []).append(rr)
            if identify and status == "CONVERGED":
                decisions[name] = V.match_modes(freqs, box, max(freqs) * 1.05, {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0})
    return results, decisions


def test_height_sensitivity_passes_with_two_levels_and_a_matching_shift():
    results, decisions = _height_results(AUX, {1.75: (3e-5, 4e-5), 1.1667: (8e-6, 1e-5)})
    out = V.height_shift(AUX, results, decisions)
    assert out["verdict"] == V.PASS, out["reasons"]
    assert out["delta_f_exact_GHz"] == pytest.approx(-1.84662, abs=1e-4)
    assert out["relative_disagreement"] < 1e-3
    assert out["shift_to_uncertainty_ratio"] > 1000
    assert out["levels_identified"] == 2


def test_height_sensitivity_is_incomplete_with_one_level_or_no_identification():
    results, decisions = _height_results(AUX, {1.75: (3e-5, 4e-5)})
    out = V.height_shift(AUX, results, decisions)
    assert out["verdict"] == V.INCOMPLETE and "single level" in out["uncertainty_source"]
    results, decisions = _height_results(AUX, {1.75: (3e-5, 4e-5), 1.1667: (8e-6, 1e-5)}, identify=False)
    assert V.height_shift(AUX, results, decisions)["verdict"] == V.INCOMPLETE
    results, decisions = _height_results(AUX, {1.75: (3e-5, 4e-5), 1.1667: (8e-6, 1e-5)}, status="NOT_CONVERGED")
    assert V.height_shift(AUX, results, decisions)["verdict"] == V.INCOMPLETE
    assert V.height_shift(AUX, {}, {})["verdict"] == V.BLOCKED


def test_wrong_z_dimension_fails_the_height_benchmark():
    """Both heights meshed with the same (wrong) box: the mode does not move."""
    results, decisions = _height_results(AUX, {1.75: (3e-5, 4e-5), 1.1667: (8e-6, 1e-5)}, wrong_z=True)
    out = V.height_shift(AUX, results, decisions)
    assert out["verdict"] in (V.FAIL, V.INCOMPLETE)
    # At the second height the computed modes sit at the first height's frequency, 8 % away from
    # the analytic value there, so they are not identified: the benchmark cannot pass.
    assert out["levels_identified"] == 0 or out["relative_disagreement"] > 0.5


def test_campaign_domains_carry_the_declared_heights():
    campaign = V.build_campaign()
    for spec in campaign.height_runs:
        assert spec.overrides()["domain"]["z_max_mm"] == spec.cavity.d_mm
        assert spec.overrides()["mesh_length_mm"] == spec.mesh_length_mm
        assert spec.overrides()["target_GHz"] < spec.cavity.frequency(*spec.height_mode)
    for spec in campaign.ladder:
        assert "target_GHz" not in spec.overrides()          # golden target and N, only the mesh changes
        assert spec.overrides()["domain"]["z_max_mm"] == 1.5
        assert spec.eigenmodes == 4


# --- the frozen campaign ---------------------------------------------------------------


def test_campaign_is_frozen_deterministic_and_serialisable():
    a, b = V.build_campaign(), V.build_campaign()
    assert a.sha256() == b.sha256()
    json.loads(a.canonical_json())
    names = [r.name for r in a.runs]
    assert names[:3] == ["ladder-L1", "ladder-L2", "ladder-L3"]
    assert [r.mesh_length_mm for r in a.ladder] == pytest.approx([22 / 12, 22 / 12 / 1.5, 22 / 12 / 2])
    assert V.height_mesh_length_mm(V.CavityBox(22, 22, 1.5), 100.16) == pytest.approx(0.375)
    assert V.height_mesh_length_mm(V.CavityBox(22, 22, 7.0), 22.47) == pytest.approx(1.75)
    obj = a.analytic_design["object001_height"]
    assert obj["heights"]["1.5"]["modes_below_mode_with_multiplicity"] == 154
    assert obj["delta_f_exact_GHz"] == pytest.approx(-9.06148, abs=1e-4)
    assert a.analytic_design["aux_height"]["delta_f_exact_GHz"] == pytest.approx(-1.84662, abs=1e-4)
    assert a.rules["finest_relative_analytic_error_max"] == 1e-4
    assert a.rules["eigenvalue_tolerance"] == pconfig.SOLVER_RULES["eigenvalue_tolerance"]


# --- probe parser ----------------------------------------------------------------------


def test_probe_csv_parser_and_z_fraction(tmp_path):
    path = tmp_path / "probe-E.csv"
    path.write_text(
        "                   m,   Re{E_x[1]} (V/m),   Im{E_x[1]} (V/m),   Re{E_y[1]} (V/m),   Im{E_y[1]} (V/m),   Re{E_z[1]} (V/m),   Im{E_z[1]} (V/m),"
        "   Re{E_x[2]} (V/m),   Im{E_x[2]} (V/m),   Re{E_y[2]} (V/m),   Im{E_y[2]} (V/m),   Re{E_z[2]} (V/m),   Im{E_z[2]} (V/m)\n"
        " 1.000000000e+00, 0.0, 0.0, 0.0, 0.0, 3.0, 4.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0\n"
        " 2.000000000e+00, 2.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0\n"
        " 3.000000000e+00, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0\n"
    )
    samples = pout.parse_probe_csv(path)
    assert len(samples) == 6 and samples[0].E[2] == complex(3.0, 4.0)
    zf = pout.z_polarisation_fraction(samples)
    assert zf[1] == pytest.approx(1.0) and zf[2] == pytest.approx(0.0) and zf[3] == pytest.approx(0.5)
    assert pout.parse_probe_csv(tmp_path / "absent.csv") == []
    assert V.classify_family(zf[1]).startswith("z-polarised") and V.classify_family(zf[2]).startswith("transverse")
    assert V.classify_family(zf[3]).startswith("mixed")


# --- executor: append-only record, manifest, pointer ---------------------------------------


def _load_script():
    spec = importlib.util.spec_from_file_location("palace_verify_campaign", REPO_ROOT / "scripts" / "palace_verify_campaign.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@needs_gmsh
def test_campaign_prepare_only_writes_an_append_only_verified_record(tmp_path):
    script = _load_script()
    pointer = tmp_path / "ptr"
    code = script.main(["--prepare-only", "--results-root", str(tmp_path / "results"), "--record-pointer", str(pointer),
                        "--only", "ladder-L1", "--only", "aux_height-d7-L1"])
    assert code == 0
    root = Path(pointer.read_text().strip())
    assert root.name.startswith("PALACE-VERIFY-") and root.parent == tmp_path / "results"
    assert not any(p.name.startswith("PALACE-GOLDEN") for p in root.parent.iterdir())
    recorded, _, name = (root / "campaign.sha256").read_text().split()[0], None, None
    assert recorded == V.build_campaign().sha256()
    summary = json.loads((root / "summary.json").read_text())
    assert summary["execution"] == "prepare-only" and summary["complete"] is True
    assert set(summary["runs"]) == {"ladder-L1", "aux_height-d7-L1"}
    assert summary["runs"]["ladder-L1"]["tetrahedra"] == 1200          # the golden mesh
    assert summary["verdicts"] == {"mesh_convergence": "NOT-EVALUATED", "height_sensitivity_aux": "NOT-EVALUATED",
                                   "height_sensitivity_object001": "NOT-EVALUATED"}
    assert (root / "report.md").exists() and (root / "runs" / "ladder-L1" / "solver" / "mesh.msh").exists()
    assert manifest.verify(root) == []
    (root / "summary.json").write_text("{}\n")
    assert manifest.verify(root) != []                                   # tampering is detected
    with pytest.raises(FileExistsError):
        (root / "runs" / "ladder-L1" / "solver").mkdir(parents=True, exist_ok=False)


def test_campaign_rejects_an_unknown_run_name(tmp_path, capsys):
    script = _load_script()
    assert script.main(["--prepare-only", "--results-root", str(tmp_path), "--only", "nope"]) == 2
    assert "unknown run name" in capsys.readouterr().err


# --- the record must be written whatever happens ---------------------------------------


def test_report_renders_for_a_blocked_or_empty_campaign():
    """The first real run died in report rendering on a BLOCKED entry; never again."""
    script = _load_script()
    campaign = V.build_campaign()
    summary = {"campaign_sha256": campaign.sha256(), "execution": "palace", "runs": {},
               **script.evaluate(campaign, {}, {})}
    text = script.render_report(campaign, summary)
    assert "BLOCKED" in text and "INCOMPLETE" in text
    assert summary["height"]["aux_height"]["verdict"] == V.BLOCKED
    assert summary["height"]["aux_height"]["mode"] == [0, 1, 1]
    failed = V.RunResult(name="ladder-L1", status="RUN_FAILED", mesh_length_mm=22 / 12, tetrahedra=1200, dof_estimate=9840,
                         failure="PalaceRunFailed: Palace exited with code 1 | requires MFEM_USE_GSLIB")
    summary = {"campaign_sha256": campaign.sha256(), "execution": "palace", "runs": {"ladder-L1": failed.as_dict()},
               **script.evaluate(campaign, {"ladder-L1": failed}, {})}
    assert "requires MFEM_USE_GSLIB" in script.render_report(campaign, summary)


@needs_gmsh
def test_record_survives_a_report_rendering_failure(monkeypatch, tmp_path):
    script = _load_script()

    def broken(campaign, summary):  # noqa: ANN001
        raise KeyError("simulated rendering defect")

    monkeypatch.setattr(script, "render_report", broken)
    pointer = tmp_path / "ptr"
    code = script.main(["--prepare-only", "--results-root", str(tmp_path / "results"), "--record-pointer", str(pointer),
                        "--only", "ladder-L1"])
    assert code == 0
    root = Path(pointer.read_text().strip())
    assert "Report rendering failed" in (root / "report.md").read_text()
    assert json.loads((root / "summary.json").read_text())["complete"] is True
    assert manifest.verify(root) == []                                    # the manifest was still written last


def test_no_probes_campaign_is_distinct_and_probe_free():
    with_probes, without = V.build_campaign(), V.build_campaign(probes=False)
    assert without.name.endswith("-noprobes") and without.sha256() != with_probes.sha256()
    assert all(r.probes for r in with_probes.runs) and not any(r.probes for r in without.runs)
    assert all("probes_mm" not in r.overrides() for r in without.runs)
