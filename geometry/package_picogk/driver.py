"""Python-side driver for the PicoGK package geometry (spec §7.2).

The C#/Python boundary is deliberately thin and file-based::

    input:   candidate.json
    outputs: body.stl, lid.stl, ports.json, geometry_manifest.json

Environment (spec §7.2, §13.2): .NET 9, PicoGK pinned at exactly 2.3.0, LEAP71
ShapeKernel at a recorded revision.

When the .NET toolchain is unavailable the driver reports geometry as
unavailable rather than raising, so the rest of the pipeline can run and say
plainly that no geometry was generated. It never fabricates an STL.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

#: Pinned exactly (spec §13.2). A different version is a provenance change.
PICOGK_VERSION = "2.3.0"
#: Recorded ShapeKernel revision. Populate when the submodule is vendored.
SHAPEKERNEL_REVISION: str | None = None

PROJECT_DIR = Path(__file__).resolve().parent
PROJECT_FILE = PROJECT_DIR / "QmhpCem.Geometry.csproj"

OUTPUT_FILES = ("body.stl", "lid.stl", "ports.json", "geometry_manifest.json")


@dataclass
class GeometryResult:
    """Outcome of a geometry generation attempt."""

    candidate_id: str
    available: bool
    reason: str
    output_dir: Path | None = None
    artifacts: dict[str, str] = field(default_factory=dict)

    @property
    def generated(self) -> bool:
        return self.available and bool(self.artifacts)


def dotnet_available() -> bool:
    return shutil.which("dotnet") is not None


def dotnet_version() -> str | None:
    if not dotnet_available():
        return None
    try:
        out = subprocess.run(
            ["dotnet", "--version"], capture_output=True, text=True, timeout=60, check=True
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return out.stdout.strip()


def generate(candidate, output_dir: Path, timeout_s: int = 600) -> GeometryResult:  # noqa: ANN001
    """Generate Object 001 geometry for a candidate.

    Writes ``candidate.json`` into ``output_dir`` and invokes the C# geometry
    executable. Returns a :class:`GeometryResult`; never fabricates geometry.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidate_path = output_dir / "candidate.json"
    candidate_path.write_text(
        json.dumps(candidate.to_ordered_dict(), indent=2, sort_keys=True) + "\n"
    )

    if not dotnet_available():
        return GeometryResult(
            candidate_id=candidate.candidate_id,
            available=False,
            reason=(
                "the .NET SDK is not installed, so the PicoGK geometry project "
                "cannot run. Object 001 geometry was NOT generated. Install "
                ".NET 9 and PicoGK " + PICOGK_VERSION + " (spec §7.2, §13.2)."
            ),
            output_dir=output_dir,
        )

    if not PROJECT_FILE.exists():
        return GeometryResult(
            candidate_id=candidate.candidate_id,
            available=False,
            reason=f"geometry project {PROJECT_FILE.name} is missing.",
            output_dir=output_dir,
        )

    command = [
        "dotnet",
        "run",
        "--project",
        str(PROJECT_FILE),
        "--configuration",
        "Release",
        "--",
        "--candidate",
        str(candidate_path),
        "--output",
        str(output_dir),
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout_s
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return GeometryResult(
            candidate_id=candidate.candidate_id,
            available=False,
            reason=f"invoking the geometry project failed: {exc}",
            output_dir=output_dir,
        )

    if completed.returncode != 0:
        return GeometryResult(
            candidate_id=candidate.candidate_id,
            available=False,
            reason=(
                f"the geometry project exited with code {completed.returncode}: "
                f"{completed.stderr.strip()[:500]}"
            ),
            output_dir=output_dir,
        )

    artifacts: dict[str, str] = {}
    missing: list[str] = []
    for name in OUTPUT_FILES:
        path = output_dir / name
        if path.exists():
            artifacts[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            missing.append(name)

    if missing:
        return GeometryResult(
            candidate_id=candidate.candidate_id,
            available=False,
            reason=f"geometry project did not produce: {', '.join(missing)}",
            output_dir=output_dir,
            artifacts=artifacts,
        )

    return GeometryResult(
        candidate_id=candidate.candidate_id,
        available=True,
        reason="Object 001 geometry generated.",
        output_dir=output_dir,
        artifacts=artifacts,
    )


def environment_record() -> dict[str, str | None]:
    """Geometry-toolchain fields for the batch manifest (spec §13.3)."""
    return {
        "dotnet_version": dotnet_version(),
        "picogk_version": PICOGK_VERSION,
        "shapekernel_revision": SHAPEKERNEL_REVISION,
    }
