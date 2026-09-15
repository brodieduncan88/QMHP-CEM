"""Palace adapter tests (spec §10.3, §10.5).

Everything here except the last execution test runs without a container: the
analytic reference, domain derivation, config, mesher (when gmsh is
importable), parsers on hand-authored FORMAT fixtures, prepare(), run() and
preflight() against a fake container runtime, and the no-fallback
guarantees. The real execution test is marked ``palace`` and skips, with the
reason, wherever the container runtime or image is absent. Skipping is not a
fallback: no result is produced and nothing is substituted.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts import Candidate
from contracts.common import Classification, ConvergenceStatus
from orchestrator import manifest
from solvers import RunContext, SolverUnavailable, get_adapter
from solvers.adapter import PreparedInput
from solvers.palace import analytic, config as pconfig, mesh as pmesh, outputs as pout
from solvers.palace.adapter import (
    CONFIG_FILENAME,
    CONTAINER_WORKDIR,
    LOG_FILENAME,
    MESH_FILENAME,
    OUTPUT_DIRNAME,
    RUN_RECORD_FILENAME,
    ImageIdentity,
    PalaceRawOutput,
    PalaceRunFailed,
    PalaceSolver,
)

FIXTURES = Path(__file__).parent / "fixtures" / "palace"
REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = REPO_ROOT / "solvers" / "palace" / "golden"
GOLDEN = GOLDEN_DIR / "QMHP-CEM-A-RF-000001.json"

TAG_COMMIT = "a61c8cbe0cacf496cde3c62e93085fae0d6299ac"
IMAGE_ID = "sha256:" + "ab" * 32


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
    a = 22.0e-3   # square box: b == a, so f_110 = (c/2) * sqrt(2) / a
    expected = 0.5 * analytic.C_M_PER_S * math.sqrt(2.0) / a / 1e9
    assert analytic.fundamental_GHz(22.0, 22.0, 1.5) == pytest.approx(expected, rel=1e-12)
    assert analytic.fundamental_GHz(22.0, 22.0, 1.5) == pytest.approx(9.6357, abs=5e-4)


def test_cavity_modes_exclude_two_zero_indices_and_are_sorted():
    modes = analytic.rectangular_cavity_modes(22.0, 22.0, 1.5, count=6)
    assert [(m.m, m.n, m.p) for m in modes[:3]] == [(1, 1, 0), (1, 2, 0), (2, 2, 0)]
    assert all((m.m == 0) + (m.n == 0) + (m.p == 0) <= 1 for m in modes)
    freqs = [m.frequency_GHz for m in modes]
    assert freqs == sorted(freqs)


def test_square_box_degeneracy_is_counted():
    """(1,2,0) and (2,1,0) coincide for a square box: one entry, multiplicity 2."""
    modes = analytic.rectangular_cavity_modes(22.0, 22.0, 1.5, count=3)
    assert [m.multiplicity for m in modes] == [1, 2, 1]
    expected = analytic.expected_solver_modes(22.0, 22.0, 1.5, 4)
    assert len(expected) == 4
    assert expected[1] == expected[2]
    assert expected[0] < expected[1] < expected[3]


def test_cavity_modes_reject_nonpositive_dimensions():
    with pytest.raises(ValueError):
        analytic.rectangular_cavity_modes(22.0, 0.0, 1.5)


# --- solver domain and config -------------------------------------------------


def test_solver_domain_is_the_centred_vacuum_cavity(golden):
    d = pconfig.solver_domain(golden)
    assert d.size_mm == (22.0, 22.0, 1.5)
    assert (d.x_min_mm, d.x_max_mm) == (-11.0, 11.0)
    assert (d.z_min_mm, d.z_max_mm) == (0.0, 1.5)   # chip top surface to lid underside
    assert d.characteristic_length_mm == pytest.approx(22.0 / 12.0)   # in-plane rule


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


def test_expected_solver_modes_follow_the_requested_count(golden):
    d = pconfig.solver_domain(golden)
    modes = pconfig.expected_solver_modes_GHz(d)
    assert len(modes) == pconfig.SOLVER_RULES["eigenmodes_requested"]
    assert modes[0] == pytest.approx(analytic.fundamental_GHz(22.0, 22.0, 1.5))
    ref = pconfig.analytic_reference(d, count=3)
    assert [r["multiplicity"] for r in ref] == [1, 2, 1]


# --- mesh ---------------------------------------------------------------------

needs_gmsh = pytest.mark.skipif(not pmesh.gmsh_available(), reason="gmsh not importable")


@needs_gmsh
def test_mesh_has_both_physical_groups_and_is_deterministic(golden, tmp_path):
    d = pconfig.solver_domain(golden)
    first = pmesh.generate_box_mesh(d, tmp_path / "a.msh")
    second = pmesh.generate_box_mesh(d, tmp_path / "b.msh")
    assert first.tetrahedron_count > 0 and first.boundary_triangle_count > 0
    assert first.sha256 == second.sha256
    assert first.characteristic_length_mm == pytest.approx(22.0 / 12.0)
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


def test_mesh_files_are_decision_relevant_in_the_batch_manifest(tmp_path):
    assert ".msh" in manifest.DECISION_RELEVANT_SUFFIXES
    (tmp_path / "mesh.msh").write_text("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n")
    (tmp_path / "solver_results.json").write_text("{}\n")
    assert {name for name, _ in manifest.collect(tmp_path)} == {"mesh.msh", "solver_results.json"}


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
    assert log.git_changeset == "v0.13.0"
    assert log.version == "0.13.0"
    assert log.mpi_processes == 1
    assert log.device == "cpu"
    assert log.libceed_backend == "/cpu/self/xsmm/blocked"
    # The stdout eigenvalue table's "Bkwd. Error" heading is not a diagnostic.
    assert log.error_lines == []


def test_log_summary_flags_real_diagnostics_only():
    log = pout.summarise_log("Git changeset ID: v0.13.0-3-gabcdef1\nBkwd. Error column\nError: mesh file not found\n")
    assert log.version == "0.13.0"
    assert log.git_changeset == "v0.13.0-3-gabcdef1"
    assert log.error_lines == ["Error: mesh file not found"]


def test_metadata_git_tag():
    meta = pout.read_metadata_json(FIXTURES / "palace.json")
    assert pout.git_tag_from_metadata(meta) == "v0.13.0"
    assert pout.read_metadata_json(FIXTURES / "does-not-exist.json") == {}


# --- prepare() without a container ------------------------------------------


@needs_gmsh
def test_prepare_writes_mesh_config_and_hashes(golden, context):
    prepared = PalaceSolver().prepare(golden, None, context)
    assert prepared.candidate_id == golden.candidate_id
    assert Path(prepared.work_dir).is_absolute()
    assert (context.work_dir / MESH_FILENAME).exists()
    assert (context.work_dir / CONFIG_FILENAME).exists()
    payload = prepared.payload
    assert payload["mesh"]["sha256"] == hashlib.sha256((context.work_dir / MESH_FILENAME).read_bytes()).hexdigest()
    assert payload["config_sha256"] == hashlib.sha256((context.work_dir / CONFIG_FILENAME).read_bytes()).hexdigest()
    assert payload["solver_domain_size_mm"] == [22.0, 22.0, 1.5]
    assert payload["analytic_reference"][0]["label"] == "analytic_110"
    assert len(payload["expected_solver_modes_GHz"]) == pconfig.SOLVER_RULES["eigenmodes_requested"]
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
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(pmesh, "gmsh_available", lambda: True)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "", "Cannot connect to the Docker daemon at unix:///var/run/docker.sock\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SolverUnavailable, match=r"daemon is not reachable \(Cannot connect") as info:
        PalaceSolver().preflight()
    assert "['" not in str(info.value)   # the message quotes the line, not a list repr


def test_preflight_names_the_missing_image(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(pmesh, "gmsh_available", lambda: True)

    def fake_run(cmd, **kwargs):
        if cmd[1] == "info":
            return subprocess.CompletedProcess(cmd, 0, '["name=seccomp,profile=builtin"]\n', "")
        return subprocess.CompletedProcess(cmd, 1, "", "No such image")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SolverUnavailable, match="docker build -f docker/palace.Dockerfile"):
        PalaceSolver().preflight()


class FakeRuntime:
    """A scripted ``docker`` CLI: records every argv, answers from a table."""

    def __init__(self, *, rootless=False, probe="version=0.13.0\ncommit=" + TAG_COMMIT + "\n",
                 probe_rc=0, run_rc=0, run_stdout="", run_stderr="", run_raises=None,
                 digest="qmhp-cem/palace@sha256:" + "ef" * 32):
        self.calls: list[list[str]] = []
        self.rootless = rootless
        self.probe = probe
        self.probe_rc = probe_rc
        self.run_rc = run_rc
        self.run_stdout = run_stdout
        self.run_stderr = run_stderr
        self.run_raises = run_raises
        self.digest = digest

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        sub = cmd[1]
        if sub == "info":
            opts = '["name=seccomp,profile=builtin","name=rootless","name=cgroupns"]' if self.rootless else '["name=seccomp,profile=builtin"]'
            return subprocess.CompletedProcess(cmd, 0, opts + "\n", "")
        if sub == "image":
            assert cmd[3] == "--format" and "{{json .RepoDigests}}" in cmd[4], cmd
            labels = json.dumps({"org.qmhp.cem.palace-version": "0.13.0", "org.qmhp.cem.palace-commit": "label-commit"})
            digests = json.dumps([self.digest] if self.digest else [])
            return subprocess.CompletedProcess(cmd, 0, f"{IMAGE_ID}\t{digests}\t{labels}\n", "")
        if sub == "run" and "--entrypoint" in cmd:
            return subprocess.CompletedProcess(cmd, self.probe_rc, self.probe, "" if self.probe_rc == 0 else "exec failed")
        if sub == "run":
            if self.run_raises is not None:
                raise self.run_raises
            return subprocess.CompletedProcess(cmd, self.run_rc, self.run_stdout, self.run_stderr)
        if sub == "kill":
            return subprocess.CompletedProcess(cmd, 0, "", "")
        raise AssertionError(f"unexpected runtime call {cmd}")


@pytest.fixture
def fake_runtime(monkeypatch):
    def install(**kwargs) -> FakeRuntime:
        runtime = FakeRuntime(**kwargs)
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")
        monkeypatch.setattr(pmesh, "gmsh_available", lambda: True)
        monkeypatch.setattr(subprocess, "run", runtime)
        return runtime
    return install


def test_preflight_reads_the_image_identity(fake_runtime):
    runtime = fake_runtime()
    adapter = PalaceSolver()
    adapter.preflight()
    identity = adapter._identity
    assert identity.image_id == IMAGE_ID
    assert identity.repo_digest == runtime.digest
    assert identity.digest_for_record == runtime.digest
    assert identity.palace_version == "0.13.0"
    assert identity.palace_commit == TAG_COMMIT           # the image file wins over the label
    assert identity.labels["org.qmhp.cem.palace-version"] == "0.13.0"
    assert identity.rootless is False
    assert [c[1] for c in runtime.calls] == ["info", "image", "run"]
    probe = runtime.calls[2]
    assert probe[:6] == ["docker", "run", "--rm", "--network", "none", "--entrypoint"]
    assert "printf 'version=%s\\ncommit=%s\\n'" in probe[-1]
    assert adapter.provenance()["palace_commit"] == TAG_COMMIT


def test_preflight_handles_a_locally_built_image_without_a_registry_digest(fake_runtime):
    """The golden image is built locally: RepoDigests is [] and the ID stands in."""
    fake_runtime(digest=None)
    adapter = PalaceSolver()
    adapter.preflight()
    assert adapter._identity.repo_digest is None
    assert adapter._identity.digest_for_record == IMAGE_ID


def test_first_digest_accepts_json_null_list_and_legacy_forms():
    from solvers.palace.adapter import _first_digest

    assert _first_digest("null") is None
    assert _first_digest("[]") is None
    assert _first_digest("") is None
    assert _first_digest('["a@sha256:1", "b@sha256:2"]') == "a@sha256:1"
    assert _first_digest("a@sha256:1,b@sha256:2") == "a@sha256:1"


def test_preflight_probe_with_an_empty_commit_falls_back_to_the_label(fake_runtime):
    fake_runtime(probe="version=0.13.0\ncommit=\n")
    adapter = PalaceSolver()
    adapter.preflight()
    assert adapter._identity.palace_version == "0.13.0"
    assert adapter._identity.palace_commit == "label-commit"


def test_preflight_treats_a_failed_probe_as_unavailable(fake_runtime):
    fake_runtime(probe_rc=125, probe="")
    with pytest.raises(SolverUnavailable, match="could not run"):
        PalaceSolver().preflight()


def test_preflight_detects_a_rootless_daemon(fake_runtime):
    fake_runtime(rootless=True)
    adapter = PalaceSolver()
    adapter.preflight()
    assert adapter._identity.rootless is True


def _fake_prepared(work_dir: Path, *, run_id="RUN-PALACE-TEST", candidate_id="QMHP-CEM-A-RF-000001") -> PreparedInput:
    """A PreparedInput with placeholder inputs, so run() is testable without gmsh."""
    work_dir.mkdir(parents=True, exist_ok=True)
    mesh = work_dir / MESH_FILENAME
    cfg = work_dir / CONFIG_FILENAME
    mesh.write_text("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n")
    cfg.write_text("{}\n")
    return PreparedInput(
        candidate_id=candidate_id,
        run_id=run_id,
        work_dir=work_dir,
        payload={"candidate_sha256": "c" * 64, "config_sha256": "d" * 64, "mesh": {"sha256": "e" * 64}},
        input_files=[mesh, cfg],
    )


def test_run_executes_the_exact_command_line(fake_runtime, tmp_path):
    runtime = fake_runtime(run_stdout="Git changeset ID: v0.13.0\nRunning with 1 MPI process\n")
    adapter = PalaceSolver(image="qmhp-cem/palace:0.13.0", mpi_processes=2)
    prepared = _fake_prepared(tmp_path / "solver")
    raw = adapter.run(prepared)

    argv = runtime.calls[-1]
    resolved = (tmp_path / "solver").resolve()
    assert argv == adapter.command_for(prepared, adapter._identity)
    assert argv[:7] == ["docker", "run", "--rm", "--network", "none", "--hostname", "localhost"]
    assert argv[argv.index("--name") + 1] == "qmhp-palace-RUN-PALACE-TEST-QMHP-CEM-A-RF-000001"
    assert argv[argv.index("--user") + 1] == f"{os.getuid()}:{os.getgid()}"
    assert argv[argv.index("-e") + 1] == "HOME=/tmp"
    assert argv[argv.index("-v") + 1] == f"{resolved}:{CONTAINER_WORKDIR}"
    assert argv[argv.index("-w") + 1] == CONTAINER_WORKDIR
    assert argv[-4:] == ["qmhp-cem/palace:0.13.0", "-np", "2", CONFIG_FILENAME]

    assert raw.returncode == 0 and raw.outcome == "completed"
    assert raw.work_dir == resolved
    assert raw.log_path.read_text().startswith("Git changeset ID: v0.13.0")
    record = json.loads(raw.run_record_path.read_text())
    assert record["command_line"] == argv
    assert record["outcome"] == "completed"
    assert record["image"]["image_id"] == IMAGE_ID
    assert set(record["input_sha256"]) == {MESH_FILENAME, CONFIG_FILENAME}
    assert LOG_FILENAME in record["output_sha256"]


def test_run_omits_the_user_flag_for_a_rootless_daemon(fake_runtime, tmp_path):
    runtime = fake_runtime(rootless=True)
    PalaceSolver().run(_fake_prepared(tmp_path / "solver"))
    assert "--user" not in runtime.calls[-1]


def test_run_honours_an_explicit_user_setting(fake_runtime, tmp_path):
    runtime = fake_runtime()
    PalaceSolver(user=None).run(_fake_prepared(tmp_path / "a"))
    assert "--user" not in runtime.calls[-1]
    PalaceSolver(user="1000:1000").run(_fake_prepared(tmp_path / "b"))
    argv = runtime.calls[-1]
    assert argv[argv.index("--user") + 1] == "1000:1000"


def test_run_nonzero_exit_writes_the_record_then_raises(fake_runtime, tmp_path):
    fake_runtime(run_rc=3, run_stdout="Reading mesh...\n", run_stderr="Error: mesh file not found\n")
    prepared = _fake_prepared(tmp_path / "solver")
    with pytest.raises(PalaceRunFailed, match="exited with code 3"):
        PalaceSolver().run(prepared)
    work = (tmp_path / "solver").resolve()
    assert "--- stderr ---\nError: mesh file not found" in (work / LOG_FILENAME).read_text()
    record = json.loads((work / RUN_RECORD_FILENAME).read_text())
    assert record["returncode"] == 3
    assert record["outcome"] == "exit 3"


def test_run_timeout_kills_the_container_and_records_it(fake_runtime, tmp_path):
    exc = subprocess.TimeoutExpired(["docker", "run"], 5, output=b"partial banner\n", stderr=b"still going\n")
    runtime = fake_runtime(run_raises=exc)
    prepared = _fake_prepared(tmp_path / "solver")
    with pytest.raises(PalaceRunFailed, match="exceeded the 5s timeout"):
        PalaceSolver(timeout_s=5).run(prepared)
    assert runtime.calls[-1] == ["docker", "kill", "qmhp-palace-RUN-PALACE-TEST-QMHP-CEM-A-RF-000001"]
    work = (tmp_path / "solver").resolve()
    assert (work / LOG_FILENAME).read_text() == "partial banner\n\n--- stderr ---\nstill going\n"
    record = json.loads((work / RUN_RECORD_FILENAME).read_text())
    assert record["returncode"] is None
    assert record["outcome"].startswith("timeout")


def test_run_records_when_the_runtime_cannot_start(fake_runtime, tmp_path):
    fake_runtime(run_raises=OSError(13, "Permission denied"))
    prepared = _fake_prepared(tmp_path / "solver")
    with pytest.raises(PalaceRunFailed, match="could not start docker"):
        PalaceSolver().run(prepared)
    record = json.loads(((tmp_path / "solver").resolve() / RUN_RECORD_FILENAME).read_text())
    assert record["returncode"] is None
    assert record["outcome"].startswith("runtime not started")


def test_run_resolves_a_symlinked_work_dir_once(fake_runtime, tmp_path):
    runtime = fake_runtime()
    real = tmp_path / "real"
    link = tmp_path / "link"
    real.mkdir()
    link.symlink_to(real, target_is_directory=True)
    prepared = _fake_prepared(link / "solver")
    raw = PalaceSolver().run(prepared)
    assert raw.work_dir == (real / "solver").resolve()
    argv = runtime.calls[-1]
    assert argv[argv.index("-v") + 1].startswith(str((real / "solver").resolve()))
    record = json.loads(raw.run_record_path.read_text())
    assert set(record["input_sha256"]) == {MESH_FILENAME, CONFIG_FILENAME}
    assert record["work_dir"] == str((real / "solver").resolve())


def test_run_never_falls_back_when_unavailable(monkeypatch, tmp_path):
    """run() on a machine without Palace raises; it never returns mock output."""
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(pmesh, "gmsh_available", lambda: True)
    with pytest.raises(SolverUnavailable):
        PalaceSolver().run(_fake_prepared(tmp_path / "solver"))


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
        image_id=IMAGE_ID,
        repo_digest=None,
        palace_version="0.13.0",
        palace_commit=TAG_COMMIT,
    )
    raw = PalaceRawOutput(
        prepared=prepared,
        image=identity,
        command_line=["docker", "run", "--rm", "qmhp-cem/palace:test", "-np", "1", "config.json"],
        returncode=returncode,
        started_utc=datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc),
        ended_utc=datetime(2026, 9, 14, 12, 0, 5, tzinfo=timezone.utc),
        work_dir=work,
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
    assert results.solver.version == "0.13.0+" + TAG_COMMIT[:12]
    assert results.solver.image_digest == IMAGE_ID
    assert results.solver.command_line.startswith("docker run --rm")
    assert results.convergence.status is ConvergenceStatus.CONVERGED
    assert results.convergence.metric == "eigenmode_backward_error_max"
    assert results.convergence.value == pytest.approx(8.0e-08)
    assert results.convergence.tolerance == pconfig.SOLVER_RULES["eigenmode_backward_error_max_tolerance"]
    assert [m.label for m in results.eigenmodes] == [f"palace_mode_{i}" for i in (1, 2, 3, 4)]
    assert results.eigenmodes[0].quality_factor is None      # inf -> not a finite Q
    assert results.frequency_GHz == [] and results.s_parameters == {}
    roles = {a.role for a in results.artifacts}
    assert {"palace_config", "mesh", "palace_log", "palace_run_record", "eigenmodes_csv", "palace_metadata"} <= roles
    assert all(not Path(a.path).is_absolute() for a in results.artifacts)
    assert any("Analytic check" in n and "relative deviation" in n for n in results.notes)
    assert any("EMPTY Object 001 vacuum cavity" in n for n in results.notes)
    assert any("Solver.Eigenmode.Tol" in n for n in results.notes)
    assert any("git changeset: v0.13.0" in n for n in results.notes)


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
def test_parse_takes_the_version_from_the_log_when_the_image_is_silent(golden, context):
    raw = _fixture_raw(golden, context)
    raw.image = ImageIdentity(reference="x", image_id="sha256:00", repo_digest=None,
                              palace_version=None, palace_commit=None)
    (raw.output_dir / "palace.json").unlink()
    results = PalaceSolver().parse(raw)
    assert results.solver.version == "0.13.0"


@needs_gmsh
def test_run_record_carries_every_hash(golden, context):
    raw = _fixture_raw(golden, context)
    record = json.loads(raw.run_record_path.read_text())
    assert record["schema"] == "qmhp-cem.palace-run/0.2.0"
    assert set(record["input_sha256"]) == {MESH_FILENAME, CONFIG_FILENAME}
    assert f"{OUTPUT_DIRNAME}/eig.csv" in record["output_sha256"]
    assert LOG_FILENAME in record["output_sha256"]
    assert record["image"]["palace_commit"] == TAG_COMMIT
    assert record["command_string"].startswith("docker run --rm")
    assert record["wall_time_s"] == pytest.approx(5.0)
    assert record["solver_rules"] == pconfig.SOLVER_RULES


# --- the golden harness -------------------------------------------------------


def _load_golden_script():
    spec = importlib.util.spec_from_file_location("palace_golden_run", REPO_ROOT / "scripts" / "palace_golden_run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_golden_harness_exits_2_and_writes_nothing_when_palace_is_unavailable(monkeypatch, tmp_path, capsys):
    script = _load_golden_script()

    def unavailable(self):
        raise SolverUnavailable("palace", "no daemon in this test", "start one")

    monkeypatch.setattr(PalaceSolver, "preflight", unavailable)
    code = script.main(["--results-root", str(tmp_path / "results")])
    assert code == 2
    assert not (tmp_path / "results").exists()
    assert "no daemon in this test" in capsys.readouterr().err


def test_golden_harness_uses_the_shared_tolerance():
    script = _load_golden_script()
    assert script.GOLDEN_RELATIVE_TOLERANCE is pconfig.GOLDEN_RELATIVE_TOLERANCE


@needs_gmsh
def test_golden_harness_gate_stage_evaluates_the_cem_gates(golden, context, tmp_path):
    """The harness takes a parsed Palace result through quantum + gates.

    Fixture-built results: this checks the plumbing, not Palace.
    """
    from contracts.common import GateStatus

    script = _load_golden_script()
    adapter = PalaceSolver()
    results = adapter.validate_convergence(adapter.parse(_fixture_raw(golden, context)))
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    quantum, report = script.gate_stage(golden, results, candidate_dir)
    assert (candidate_dir / "quantum_results.json").exists()
    assert (candidate_dir / "gate_report.json").exists()
    assert report.candidate_id == golden.candidate_id
    assert isinstance(report.overall_status, GateStatus)
    ids = {g.gate_id for g in report.gates}
    assert {"P4PRE_SPECTRAL", "COUPLING_EXTRACTION"} <= ids
    summary = script.gate_summary(quantum, report)
    assert summary["overall_status"] == report.overall_status.value
    assert {g["gate_id"] for g in summary["gates"]} == ids


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
    expected = pconfig.expected_solver_modes_GHz(pconfig.solver_domain(golden))
    solved = [m.frequency_GHz for m in results.eigenmodes[: len(expected)]]
    assert len(solved) == len(expected)
    for f_solved, f_exact in zip(solved, expected):
        assert abs(f_solved - f_exact) / f_exact < pconfig.GOLDEN_RELATIVE_TOLERANCE, (solved, expected)


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
