"""Geometry tests (spec §12.6).

Planar tests skip cleanly without gdsfactory and PicoGK tests skip cleanly
without the .NET SDK, so default CI needs neither (spec §12.8).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from geometry import coordinates
from geometry.chip_planar import cells
from geometry.package_picogk import driver

HAS_GDSFACTORY = cells.gdsfactory_available()
HAS_DOTNET = driver.dotnet_available()


# --- frozen conventions -----------------------------------------------------


def test_coordinate_convention_is_frozen():
    convention = coordinates.convention()
    assert convention["origin"] == "centre of top surface of chip substrate"
    assert convention["z_axis"] == "+Z = from chip toward package lid"
    assert convention["geometry_unit"] == "mm"
    assert convention["rf_frequency_unit"] == "GHz"
    assert convention["rf_offset_unit"] == "MHz"


def test_unit_conversions():
    assert coordinates.GHz_to_MHz(1.5) == 1500.0
    assert coordinates.MHz_to_GHz(1500.0) == 1.5


# --- planar (spec §7.1) -----------------------------------------------------


@pytest.mark.planar
@pytest.mark.skipif(HAS_GDSFACTORY, reason="gdsfactory installed; cells still unimplemented")
def test_planar_requires_gdsfactory():
    with pytest.raises(cells.PlanarGeometryNotImplemented, match="gdsfactory"):
        cells.require_gdsfactory()


def test_planar_cells_not_implemented(seed_candidate):
    with pytest.raises(cells.PlanarGeometryNotImplemented):
        cells.readout_resonator(seed_candidate)
    with pytest.raises(cells.PlanarGeometryNotImplemented):
        cells.stepped_filter(seed_candidate)
    with pytest.raises(cells.PlanarGeometryNotImplemented):
        cells.run_drc(None)


# --- PicoGK package (spec §7.2, §7.4) ---------------------------------------


def test_picogk_version_is_pinned_exactly():
    assert driver.PICOGK_VERSION == "2.3.0"


def test_csproj_pins_picogk_exactly():
    text = driver.PROJECT_FILE.read_text()
    assert 'Version="[2.3.0]"' in text, "PicoGK must be pinned, not floated"
    assert "<TargetFramework>net9.0</TargetFramework>" in text


def test_driver_writes_candidate_json(seed_candidate, tmp_path):
    result = driver.generate(seed_candidate, tmp_path / "geometry")
    written = json.loads((tmp_path / "geometry" / "candidate.json").read_text())
    assert written["candidate_id"] == seed_candidate.candidate_id
    assert result.candidate_id == seed_candidate.candidate_id


@pytest.mark.skipif(HAS_DOTNET, reason="requires an environment without .NET")
def test_driver_reports_unavailable_without_dotnet(seed_candidate, tmp_path):
    """Never fabricates geometry when the toolchain is missing."""
    result = driver.generate(seed_candidate, tmp_path / "geometry")
    assert result.available is False
    assert result.generated is False
    assert ".NET" in result.reason
    assert not (tmp_path / "geometry" / "body.stl").exists()
    assert not (tmp_path / "geometry" / "lid.stl").exists()


@pytest.mark.dotnet
@pytest.mark.skipif(not HAS_DOTNET, reason="requires the .NET 9 SDK")
def test_dotnet_project_builds():
    import subprocess

    completed = subprocess.run(
        ["dotnet", "build", str(driver.PROJECT_FILE), "-c", "Release"],
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert completed.returncode == 0, completed.stderr


def test_environment_record_shape():
    record = driver.environment_record()
    assert set(record) == {"dotnet_version", "picogk_version", "shapekernel_revision"}
    assert record["picogk_version"] == "2.3.0"
    if shutil.which("dotnet") is None:
        assert record["dotnet_version"] is None


# --- PicoGK generator boundary (geometry/package_picogk, Object 001) --------------------

SEED_FIXTURE = driver.PROJECT_DIR / "tests" / "fixtures" / "object001_seed.candidate.json"


def test_the_csharp_seed_fixture_is_the_seed_candidate_exactly_as_the_driver_writes_it(seed_candidate):
    """The C# tests and the macOS CI job read this file; it must not drift from the seed."""
    written = json.dumps(seed_candidate.to_ordered_dict(), indent=2, sort_keys=True) + "\n"
    assert SEED_FIXTURE.read_text() == written


def _fake_run(returncode: int, write=None, stderr: str = ""):
    """A stand-in for subprocess.run that records the command and writes outputs."""
    import subprocess

    calls = []

    def run(command, **_kwargs):
        calls.append(command)
        output = Path(command[command.index("--output") + 1])
        if write is not None:
            write(output)
        return subprocess.CompletedProcess(command, returncode, stdout="", stderr=stderr)

    run.calls = calls
    return run


def _write_outputs(manifest_edit=None):
    def write(output: Path) -> None:
        for name, content in (("body.stl", b"body"), ("lid.stl", b"lid"), ("ports.json", b"{}\n")):
            (output / name).write_bytes(content)
        manifest = {
            "status": "PASSED",
            "acceptance": {"all_passed": True, "checks": []},
            "outputs_sha256": {
                name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                for name in ("body.stl", "lid.stl", "ports.json")
            },
        }
        if manifest_edit is not None:
            manifest_edit(manifest)
        (output / "geometry_manifest.json").write_text(json.dumps(manifest))
    return write


@pytest.mark.parametrize("code, phrase", [
    (2, "refused its input"),
    (4, "failed an acceptance check"),
    (5, "native runtime cannot load"),
    (6, "internal error"),
    (134, "unexpected exit code"),
])
def test_the_driver_explains_each_refusal_and_reports_nothing_generated(seed_candidate, tmp_path, monkeypatch, code, phrase):
    fake = _fake_run(code, stderr="from the program")
    monkeypatch.setattr(driver, "dotnet_available", lambda: True)
    monkeypatch.setattr(driver.subprocess, "run", fake)
    result = driver.generate(seed_candidate, tmp_path / "geometry")
    assert result.available is False and result.generated is False
    assert phrase in result.reason and f"exit code {code}" in result.reason and "from the program" in result.reason
    assert fake.calls[0][:3] == ["dotnet", "run", "--project"]


@pytest.mark.parametrize("edit, phrase", [
    (lambda m: m.update(status="REJECTED"), "not 'PASSED'"),
    (lambda m: m["acceptance"].update(all_passed=False), "not every acceptance check passed"),
    (lambda m: m["outputs_sha256"].update({"lid.stl": "0" * 64}), "lid.stl does not match"),
    (lambda m: m.pop("outputs_sha256"), "body.stl does not match"),
])
def test_the_driver_refuses_outputs_its_manifest_does_not_vouch_for(seed_candidate, tmp_path, monkeypatch, edit, phrase):
    monkeypatch.setattr(driver, "dotnet_available", lambda: True)
    monkeypatch.setattr(driver.subprocess, "run", _fake_run(0, _write_outputs(edit)))
    result = driver.generate(seed_candidate, tmp_path / "geometry")
    assert result.available is False and result.generated is False
    assert phrase in result.reason


def test_the_driver_accepts_outputs_its_manifest_vouches_for(seed_candidate, tmp_path, monkeypatch):
    monkeypatch.setattr(driver, "dotnet_available", lambda: True)
    monkeypatch.setattr(driver.subprocess, "run", _fake_run(0, _write_outputs()))
    result = driver.generate(seed_candidate, tmp_path / "geometry")
    assert result.generated is True
    assert set(result.artifacts) == set(driver.OUTPUT_FILES)
    for name, digest in result.artifacts.items():
        assert digest == hashlib.sha256((tmp_path / "geometry" / name).read_bytes()).hexdigest()


def test_a_garbled_manifest_is_refused(tmp_path):
    (tmp_path / "geometry_manifest.json").write_text("not json")
    assert driver.manifest_problems(tmp_path, {})[0].startswith("geometry_manifest.json is unreadable")
    (tmp_path / "geometry_manifest.json").write_text("[1, 2]")
    assert driver.manifest_problems(tmp_path, {}) == ["geometry_manifest.json is not an object"]
