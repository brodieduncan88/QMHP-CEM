"""Palace adapter tests (spec §10.3, §10.5).

Everything here except the last test runs without a container: the analytic
reference, domain derivation, config, mesher (when gmsh is importable),
parsers on hand-authored FORMAT fixtures, prepare(), and the no-fallback
guarantees. The real execution test is marked ``palace`` and skips, with the
reason, wherever the container runtime or image is absent. Skipping is not a
fallback: no result is produced and nothing is substituted.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts import Candidate
from contracts.common import Classification, ConvergenceStatus
from solvers import RunContext, SolverUnavailable, get_adapter
from solvers.palace import analytic, config as pconfig, mesh as pmesh, outputs as pout
from solvers.palace.adapter import (
    CONFIG_FILENAME,
    LOG_FILENAME,
    MESH_FILENAME,
    OUTPUT_DIRNAME,
    RUN_RECORD_FILENAME,
    ImageIdentity,
    PalaceRawOutput,
    PalaceSolver,
)

FIXTURES = Path(__file__).parent / "fixtures" / "palace"
GOLDEN_DIR = Path(__file__).resolve().parent.parent / "solvers" / "palace" / "golden"
GOLDEN = GOLDEN_DIR / "QMHP-CEM-A-RF-000001.json"


@pytest.fixture
def golden() -> Candidate:
    return Candidate.model_validate(json.loads(GOLDEN.read_text()))


@pytest.fixture
def context(tmp_path) -> RunContext:
    return RunContext(run_id="RUN-PALACE-TEST", work_dir=tmp_path / "solver")


# --- golden candidate ---------------------------------------------------------


def test_golden_candidate_is_frozen_by_digest():
    recorded, _, name = (GOLDEN_DIR / "GOLDEN.sha256").read_text().strip().partition("  ")
    assert name == GOLDEN.name
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == recorded


def test_golden_candidate_is_the_object001_seed(golden, seed_candidate):
    assert golden.to_ordered_dict() == seed_candidate.to_ordered_dict()
    assert golden.classification is Classification.ENGINEERING_SEED


# --- analytic reference -------------------------------------------------------


def test_rectangular_cavity_fundamental_matches_closed_form():
    a = b = 22.0e-3
    expected = 0.5 * analytic.C_M_PER_S * math.sqrt(2.0) / a / 1e9
    assert analytic.fundamental_GHz(22.0, 22.0, 1.5) == pytest.approx(expected, rel=1e-12)
    assert analytic.fundamental_GHz(22.0, 22.0, 1.5) == pytest.approx(9.6357, abs=5e-4)


def test_cavity_modes_exclude_two_zero_indices_and_are_sorted():
    modes = analytic.rectangular_cavity_modes(22.0, 22.0, 1.5, count=6)
    assert [(m.m, m.n, m.p) for m in modes[:3]] == [(1, 1, 0), (1, 2, 0), (2, 2, 0)]
    assert all((m.m == 0) + (m.n == 0) + (m.p == 0) <= 1 for m in modes)
    freqs = [m.frequency_GHz for m in modes]
    assert freqs == sorted(freqs)


def test_cavity_modes_reject_nonpositive_dimensions():
    with pytest.raises(ValueError):
        analytic.rectangular_cavity_modes(22.0, 0.0, 1.5)


# --- solver domain and config -------------------------------------------------


def test_solver_domain_is_the_centred_vacuum_cavity(golden):
    d = pconfig.solver_domain(golden)
    assert d.size_mm == (22.0, 22.0, 1.5)
    assert (d.x_min_mm, d.x_max_mm) == (-11.0, 11.0)
    assert (d.z_min_mm, d.z_max_mm) == (0.0, 1.5)   # chip top surface to lid underside
    assert d.characteristic_length_mm == 1.5           # min(1.5, 22/12)


def test_config_attributes_match_mesh_physical_groups(golden):
    cfg = pconfig.build_config("mesh.msh", pconfig.solver_domain(golden))
    assert cfg["Problem"]["Type"] == "Eigenmode"
    assert cfg["Model"]["Mesh"] == "mesh.msh"
    assert cfg["Model"]["L0"] == 1.0e-3
    assert cfg["Domains"]["Materials"][0]["Attributes"] == [pconfig.VACUUM_ATTRIBUTE]
    assert cfg["Boundaries"]["PEC"]["Attributes"] == [pconfig.PEC_ATTRIBUTE]
    eig = cfg["Solver"]["Eigenmode"]
    assert eig["N"] == pconfig.SOLVER_RULES["eigenmodes_requested"]
    assert eig["Tol"] == pconfig.SOLVER_RULES["eigenvalue_tolerance"]
    assert eig["Save"] == 0
    assert 0 < eig["Target"] < analytic.fundamental_GHz(22.0, 22.0, 1.5)


def test_config_is_json_serialisable_and_deterministic(golden):
    d = pconfig.solver_domain(golden)
    one = json.dumps(pconfig.build_config("mesh.msh", d), sort_keys=True)
    two = json.dumps(pconfig.build_config("mesh.msh", d), sort_keys=True)
    assert one == two


# --- mesh ---------------------------------------------------------------------

needs_gmsh = pytest.mark.skipif(not pmesh.gmsh_available(), reason="gmsh not importable")


@needs_gmsh
def test_mesh_has_both_physical_groups_and_is_deterministic(golden, tmp_path):
    d = pconfig.solver_domain(golden)
    first = pmesh.generate_box_mesh(d, tmp_path / "a.msh")
    second = pmesh.generate_box_mesh(d, tmp_path / "b.msh")
    assert first.tetrahedron_count > 0 and first.boundary_triangle_count > 0
    assert first.sha256 == second.sha256
    text = (tmp_path / "a.msh").read_text()
    assert text.startswith("$MeshFormat\n2.2 0 8")
    assert f'2 {pconfig.PEC_ATTRIBUTE} "pec"' in text
    assert f'3 {pconfig.VACUUM_ATTRIBUTE} "vacuum"' in text


def test_mesh_reports_remedy_when_gmsh_is_unusable(monkeypatch, golden, tmp_path):
    import builtins

    real_import = builtins.__import__

    def broken(name, *args, **kwargs):
        if name == "gmsh":
            raise OSError("libGLU.so.1: cannot open shared object file")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken)
    with pytest.raises(SolverUnavailable, match="gmsh"):
        pmesh.generate_box_mesh(pconfig.solver_domain(golden), tmp_path / "x.msh")


# --- output parsers on FORMAT fixtures ----------------------------------------


def test_parse_eig_csv_reads_every_column():
    table = pout.parse_eig_csv(FIXTURES / "eig.csv")
    assert [r.index for r in table.rows] == [1, 2, 3, 4]
    assert table.rows[0].frequency_re_GHz == pytest.approx(9.641234567)
    assert table.rows[0].quality_factor == math.inf
    assert table.rows[0].backward_error == pytest.approx(3.214159265e-09)
    assert table.rows[0].absolute_error == pytest.approx(1.234567890e-07)
    assert table.max_backward_error == pytest.approx(8.0e-08)


def test_parse_eig_csv_tolerates_a_missing_absolute_error_column():
    table = pout.parse_eig_csv(FIXTURES / "eig_not_converged.csv")
    assert table.rows[1].absolute_error is None
    assert table.max_backward_error == pytest.approx(2.5e-04)


def test_parse_eig_csv_requires_the_backward_error(tmp_path):
    bad = tmp_path / "eig.csv"
    bad.write_text("m, Re{f} (GHz), Im{f} (GHz), Q\n1, 9.6, 0.0, inf\n")
    with pytest.raises(pout.PalaceOutputError, match="Bkwd"):
        pout.parse_eig_csv(bad)


def test_parse_eig_csv_missing_file_is_an_error(tmp_path):
    with pytest.raises(pout.PalaceOutputError, match="not written"):
        pout.parse_eig_csv(tmp_path / "eig.csv")


def test_log_summary_extracts_identity_fields():
    log = pout.summarise_log((FIXTURES / "palace_log.txt").read_text())
    assert log.version == "0.13.0"
    assert log.git_changeset == "0123456789abcdef0123456789abcdef01234567"
    assert log.mpi_processes == 1
    assert log.device == "cpu"
    assert log.error_lines == []


def test_metadata_git_tag():
    meta = pout.read_metadata_json(FIXTURES / "palace.json")
    assert pout.git_tag_from_metadata(meta) == "v0.13.0"
    assert pout.read_metadata_json(FIXTURES / "does-not-exist.json") == {}


# --- prepare() without a container ------------------------------------------


@needs_gmsh
def test_prepare_writes_mesh_config_and_hashes(golden, context):
    prepared = PalaceSolver().prepare(golden, None, context)
    assert prepared.candidate_id == golden.candidate_id
    assert (context.work_dir / MESH_FILENAME).exists()
    assert (context.work_dir / CONFIG_FILENAME).exists()
    payload = prepared.payload
    assert payload["mesh"]["sha256"] == hashlib.sha256((context.work_dir / MESH_FILENAME).read_bytes()).hexdigest()
    assert payload["config_sha256"] == hashlib.sha256((context.work_dir / CONFIG_FILENAME).read_bytes()).hexdigest()
    assert payload["solver_domain_size_mm"] == [22.0, 22.0, 1.5]
    assert payload["analytic_reference"][0]["label"] == "analytic_110"
    assert "not modelled" in payload["solver_rules"]["domain"].lower()
    assert "No PicoGK geometry" in payload["geometry_note"]
    # The config on disk is exactly the config in the payload.
    assert json.loads((context.work_dir / CONFIG_FILENAME).read_text()) == payload["config"]


# --- §10.5: no silent substitution --------------------------------------------


def test_palace_is_registered_as_solved_evidence():
    adapter = get_adapter("palace")
    assert isinstance(adapter, PalaceSolver)
    assert adapter.classification is Classification.SOLVED


def test_preflight_names_the_missing_runtime(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(pmesh, "gmsh_available", lambda: True)
    with pytest.raises(SolverUnavailable, match="not on PATH"):
        PalaceSolver().preflight()


def test_preflight_names_an_unreachable_daemon(monkeypatch):
    import subprocess

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(pmesh, "gmsh_available", lambda: True)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "", "Cannot connect to the Docker daemon")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SolverUnavailable, match="daemon is not reachable"):
        PalaceSolver().preflight()


def test_preflight_names_the_missing_image(monkeypatch):
    import subprocess

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(pmesh, "gmsh_available", lambda: True)

    def fake_run(cmd, **kwargs):
        if cmd[1] == "info":
            return subprocess.CompletedProcess(cmd, 0, "Server Version: 27\n", "")
        return subprocess.CompletedProcess(cmd, 1, "", "No such image")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SolverUnavailable, match="docker build -f docker/palace.Dockerfile"):
        PalaceSolver().preflight()


def test_run_never_falls_back_when_unavailable(monkeypatch, golden, context):
    """run() on a machine without Palace raises; it never returns mock output."""
    monkeypatch.setattr(shutil, "which", lambda name: None)
    prepared = type("P", (), {"work_dir": context.work_dir, "input_files": [], "payload": {}, "candidate_id": "x", "run_id": "y"})()
    with pytest.raises(SolverUnavailable):
        PalaceSolver().run(prepared)


def test_unavailable_message_states_the_no_substitution_rule():
    try:
        PalaceSolver(runtime="definitely-not-a-runtime").preflight()
    except SolverUnavailable as exc:
        assert "will not silently substitute" in str(exc)
    else:  # pragma: no cover
        pytest.fail("preflight should have raised")


# --- parse() on a fixture-built raw output ----------------------------------


def _fixture_raw(golden, context, eig_name="eig.csv", returncode=0) -> PalaceRawOutput:
    prepared = PalaceSolver().prepare(golden, None, context)
    work = Path(prepared.work_dir)
    out = work / OUTPUT_DIRNAME
    out.mkdir()
    shutil.copy(FIXTURES / eig_name, out / "eig.csv")
    shutil.copy(FIXTURES / "palace.json", out / "palace.json")
    shutil.copy(FIXTURES / "palace_log.txt", work / LOG_FILENAME)
    identity = ImageIdentity(
        reference="qmhp-cem/palace:test",
        image_id="sha256:" + "ab" * 32,
        repo_digest=None,
        palace_version="0.13.0",
        palace_commit="0123456789abcdef0123456789abcdef01234567",
    )
    raw = PalaceRawOutput(
        prepared=prepared,
        image=identity,
        command_line=["docker", "run", "--rm", "qmhp-cem/palace:test", "-np", "1", "config.json"],
        returncode=returncode,
        started_utc=datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc),
        ended_utc=datetime(2026, 9, 14, 12, 0, 5, tzinfo=timezone.utc),
        log_path=work / LOG_FILENAME,
        output_dir=out,
        run_record_path=work / RUN_RECORD_FILENAME,
    )
    PalaceSolver()._write_run_record(raw)
    return raw


@needs_gmsh
def test_parse_builds_a_valid_solved_result(golden, context):
    adapter = PalaceSolver()
    results = adapter.validate_convergence(adapter.parse(_fixture_raw(golden, context)))
    assert results.synthetic is False
    assert results.solver.name == "palace"
    assert results.solver.classification is Classification.SOLVED
    assert results.solver.version.startswith("0.13.0+0123456789ab")
    assert results.solver.image_digest == "sha256:" + "ab" * 32
    assert results.solver.command_line.startswith("docker run --rm")
    assert results.convergence.status is ConvergenceStatus.CONVERGED
    assert results.convergence.metric == "eigenmode_backward_error_max"
    assert results.convergence.value == pytest.approx(8.0e-08)
    assert results.convergence.tolerance == pconfig.SOLVER_RULES["eigenvalue_tolerance"]
    assert [m.label for m in results.eigenmodes] == [f"palace_mode_{i}" for i in (1, 2, 3, 4)]
    assert results.eigenmodes[0].quality_factor is None      # inf -> not a finite Q
    assert results.frequency_GHz == [] and results.s_parameters == {}
    roles = {a.role for a in results.artifacts}
    assert {"palace_config", "mesh", "palace_log", "palace_run_record", "eigenmodes_csv", "palace_metadata"} <= roles
    assert any("Analytic check" in n and "relative deviation" in n for n in results.notes)
    assert any("EMPTY Object 001 vacuum cavity" in n for n in results.notes)


@needs_gmsh
def test_parse_reports_not_converged_when_backward_error_exceeds_tolerance(golden, context):
    from solvers import ConvergenceFailure

    adapter = PalaceSolver()
    results = adapter.parse(_fixture_raw(golden, context, eig_name="eig_not_converged.csv"))
    assert results.convergence.status is ConvergenceStatus.NOT_CONVERGED
    with pytest.raises(ConvergenceFailure):
        adapter.validate_convergence(results)


@needs_gmsh
def test_parse_refuses_a_result_without_a_solver_version(golden, context):
    raw = _fixture_raw(golden, context)
    raw.image = ImageIdentity(reference="x", image_id="sha256:00", repo_digest=None,
                              palace_version=None, palace_commit=None)
    (raw.output_dir / "palace.json").unlink()
    raw.log_path.write_text("no banner here\n")
    with pytest.raises(pout.PalaceOutputError, match="solver version"):
        PalaceSolver().parse(raw)


@needs_gmsh
def test_run_record_carries_every_hash(golden, context):
    raw = _fixture_raw(golden, context)
    record = json.loads(raw.run_record_path.read_text())
    assert record["schema"] == "qmhp-cem.palace-run/0.2.0"
    assert set(record["input_sha256"]) == {MESH_FILENAME, CONFIG_FILENAME}
    assert f"{OUTPUT_DIRNAME}/eig.csv" in record["output_sha256"]
    assert LOG_FILENAME in record["output_sha256"]
    assert record["image"]["palace_commit"].startswith("0123456789ab")
    assert record["command_string"].startswith("docker run --rm")
    assert record["wall_time_s"] == pytest.approx(5.0)


# --- the real thing -----------------------------------------------------------


def _palace_available() -> str | None:
    try:
        PalaceSolver().preflight()
    except SolverUnavailable as exc:
        return exc.reason
    return None


@pytest.mark.palace
def test_golden_candidate_solves_end_to_end_in_palace(golden, context):
    """One real Palace eigenmode calculation, checked against the closed form.

    Skips with the exact reason where the container cannot execute. A skip is
    not a fallback: nothing is substituted and no result is produced.
    """
    reason = _palace_available()
    if reason:
        pytest.skip(f"Palace cannot execute here: {reason}")
    results = PalaceSolver().solve(golden, None, context)
    assert results.convergence.status is ConvergenceStatus.CONVERGED
    assert results.solver.image_digest and results.solver.command_line
    f_solved = results.eigenmodes[0].frequency_GHz
    f_exact = analytic.fundamental_GHz(22.0, 22.0, 1.5)
    assert abs(f_solved - f_exact) / f_exact < 0.02, (f_solved, f_exact)


# --- batch environment record (spec §13.3) ------------------------------------


def test_batch_environment_uses_the_container_identity_when_present():
    from orchestrator.pipeline import solver_identity, solver_version

    adapter = PalaceSolver(image="qmhp-cem/palace:0.13.0")
    # Before preflight nothing is known about the image: fall back to the adapter.
    assert solver_identity(adapter) == "palace@0.2.0-adapter"
    assert solver_version(adapter) == "0.2.0-adapter"
    adapter._identity = ImageIdentity(
        reference="qmhp-cem/palace:0.13.0", image_id="sha256:" + "cd" * 32,
        repo_digest=None, palace_version="0.13.0", palace_commit="abc",
    )
    assert solver_identity(adapter) == "qmhp-cem/palace:0.13.0@sha256:" + "cd" * 32
    assert solver_version(adapter) == "0.13.0"


def test_mock_identity_is_unchanged_by_the_provenance_route():
    from orchestrator.pipeline import solver_identity, solver_version
    from solvers.mock.adapter import MockSolver

    assert solver_identity(MockSolver()) == "mock@0.1.0"
    assert solver_version(MockSolver()) == "0.1.0"
