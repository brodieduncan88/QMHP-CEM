"""Geometry tests (spec §12.6).

Planar tests skip cleanly without gdsfactory and PicoGK tests skip cleanly
without the .NET SDK, so default CI needs neither (spec §12.8).
"""

from __future__ import annotations

import json
import shutil

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
