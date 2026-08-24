"""Environment record for batch manifests (spec §13.3)."""

from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from contracts.master import REPO_ROOT
from contracts.results import EnvironmentRecord
from geometry.package_picogk import driver as picogk_driver


def _run(command: list[str]) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    try:
        out = subprocess.run(command, capture_output=True, text=True, timeout=60, check=True)
    except (subprocess.SubprocessError, OSError):
        return None
    return out.stdout.strip() or None


def uv_version() -> str | None:
    version = _run(["uv", "--version"])
    return version.split()[-1] if version else None


def git_commit() -> str | None:
    return _run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"])


def dependency_lock_sha256() -> str | None:
    lock = REPO_ROOT / "uv.lock"
    if not lock.exists():
        return None
    return hashlib.sha256(lock.read_bytes()).hexdigest()


def record(
    started_utc: datetime,
    solver_name: str,
    solver_version: str | None = None,
    solver_identity: str | None = None,
    ended_utc: datetime | None = None,
) -> EnvironmentRecord:
    """Build the environment record required in every batch manifest."""
    geometry_env = picogk_driver.environment_record()
    return EnvironmentRecord(
        os=f"{platform.system()} {platform.release()}",
        architecture=platform.machine(),
        python_version=sys.version.split()[0],
        uv_version=uv_version(),
        dependency_lock_sha256=dependency_lock_sha256(),
        dotnet_version=geometry_env["dotnet_version"],
        picogk_version=geometry_env["picogk_version"],
        shapekernel_revision=geometry_env["shapekernel_revision"],
        git_commit=git_commit(),
        solver_version=solver_version,
        solver_identity=solver_identity or solver_name,
        started_utc=started_utc,
        ended_utc=ended_utc,
    )
