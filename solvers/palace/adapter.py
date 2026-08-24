"""Palace solver adapter (spec §10.3).

Invoked via a container runner. Records solver version, image digest where
available, command line, input hash, output hashes and convergence.

Spec §10.5 is absolute: if Palace is requested and cannot execute, the run
fails clearly. This adapter never falls back to the mock.

STATUS: the container invocation and output parsing are NOT implemented in
v0.1. The adapter is wired into the registry and fails clearly, which is the
specified behaviour when the solver cannot execute.
"""

from __future__ import annotations

import json
import shutil
from typing import Any

from contracts.common import Classification
from contracts.results import SolverResults
from solvers.adapter import (
    PreparedInput,
    RunContext,
    SolverAdapter,
    SolverUnavailable,
    register,
)

#: Image built from docker/palace.Dockerfile.
DEFAULT_IMAGE = "qmhp-cem/palace:0.1.0"


@register
class PalaceSolver(SolverAdapter):
    """Palace finite-element EM solver."""

    name = "palace"
    version = "0.1.0-adapter"
    classification = Classification.SOLVED

    def __init__(self, image: str = DEFAULT_IMAGE, runtime: str = "docker") -> None:
        self.image = image
        self.runtime = runtime

    def preflight(self) -> None:
        """Fail clearly when the container runtime or image is unavailable."""
        if shutil.which(self.runtime) is None:
            raise SolverUnavailable(
                self.name,
                f"container runtime {self.runtime!r} is not on PATH",
                f"Install {self.runtime}, or run with --solver mock for the "
                f"synthetic pipeline check.",
            )
        raise SolverUnavailable(
            self.name,
            "the Palace container invocation is not implemented in QMHP-CEM v0.1",
            f"Build the image from docker/palace.Dockerfile and implement "
            f"PalaceSolver.run(). Real Palace validation of Object 001 is "
            f"explicitly deferred to v0.2 (spec §15).",
        )

    def prepare(self, candidate, geometry, run_context: RunContext) -> PreparedInput:  # noqa: ANN001
        self.preflight()
        raise AssertionError("unreachable: preflight always raises in v0.1")

    def run(self, prepared: PreparedInput) -> Any:
        self.preflight()
        raise AssertionError("unreachable: preflight always raises in v0.1")

    def parse(self, raw_output: Any) -> SolverResults:
        raise SolverUnavailable(
            self.name,
            "Palace output parsing is not implemented in QMHP-CEM v0.1",
        )

    def provenance(self) -> dict[str, str]:
        """Solver identity fields required in the manifest (spec §10.3)."""
        return {
            "solver": self.name,
            "adapter_version": self.version,
            "image": self.image,
            "runtime": self.runtime,
        }
