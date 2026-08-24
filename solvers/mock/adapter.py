"""Deterministic mock solver (spec §8.4, §10.2).

CLASSIFICATION: ``TEST_FIXTURE``.

Every value this adapter produces is SYNTHETIC. It is not a physical
simulation and carries no evidentiary weight whatsoever. Results are marked
``synthetic=True`` and carry an explicit note, so synthetic output is obvious
in every artifact (spec §8.4).

Its only purpose is to prove that the geometry -> solver -> physics -> gate
loop runs deterministically and unattended. Default CI depends on it alone.

Determinism: all perturbations derive from the SHA-256 of the candidate's
canonical JSON. Same candidate in, same numbers out, on any machine.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from contracts import master
from contracts.common import Classification, ConvergenceStatus
from contracts.results import (
    SOLVER_RESULTS_SCHEMA,
    Convergence,
    Eigenmode,
    SolverIdentity,
    SolverResults,
)
from solvers.adapter import PreparedInput, RunContext, SolverAdapter, register

#: Named fixtures that force a specific downstream gate outcome (spec §8.4).
FIXTURES = (
    "default",
    "filter_pass",
    "filter_fail",
    "collision_pass",
    "collision_fail",
    "no_feasible_design",
)

SYNTHETIC_NOTE = (
    "SYNTHETIC TEST FIXTURE — produced by the QMHP-CEM mock solver. "
    "Not a physical simulation. Carries no evidentiary weight."
)


@register
class MockSolver(SolverAdapter):
    """Deterministic synthetic solver."""

    name = "mock"
    version = "0.1.0"
    classification = Classification.TEST_FIXTURE

    def __init__(self, fixture: str = "default") -> None:
        if fixture not in FIXTURES:
            raise ValueError(f"unknown mock fixture {fixture!r}; known: {list(FIXTURES)}")
        self.fixture = fixture

    # --- §10.1 interface ----------------------------------------------------

    def prepare(self, candidate, geometry, run_context: RunContext) -> PreparedInput:  # noqa: ANN001
        canonical = json.dumps(
            candidate.to_ordered_dict(), sort_keys=True, separators=(",", ":")
        )
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        return PreparedInput(
            candidate_id=candidate.candidate_id,
            run_id=run_context.run_id,
            work_dir=run_context.work_dir,
            payload={
                "candidate_sha256": digest,
                "fixture": self.fixture,
                "frequency_start_GHz": run_context.frequency_start_GHz,
                "frequency_stop_GHz": run_context.frequency_stop_GHz,
                "frequency_points": run_context.frequency_points,
                "cavity_height_above_chip_mm": (
                    candidate.parameters.vacuum_cavity.height_above_chip_mm
                ),
                "bore_diameter_mm": candidate.parameters.launches.bore_diameter_mm,
            },
        )

    def run(self, prepared: PreparedInput) -> dict[str, Any]:
        return {"prepared": prepared}

    def parse(self, raw_output: dict[str, Any]) -> SolverResults:
        prepared: PreparedInput = raw_output["prepared"]
        payload = prepared.payload
        fixture = payload["fixture"]

        emission_GHz = master.get("purcell_f8.filter_constraint.dressed_emission_GHz")
        readout_GHz = master.get("dressed_system.production_convention.root_GHz")

        # Deterministic unit perturbation in [0, 1) from the candidate digest.
        jitter = int(payload["candidate_sha256"][:8], 16) / 0xFFFFFFFF

        stopband_dB = _synthetic_stopband_dB(fixture, payload, jitter)
        frequencies = _frequency_grid(payload, (emission_GHz, readout_GHz))
        s21 = [
            -_bandstop_dB(f, emission_GHz, stopband_dB) for f in frequencies
        ]
        s11 = [-_return_loss_dB(f, readout_GHz, jitter) for f in frequencies]

        eigenmodes = _synthetic_eigenmodes(fixture, readout_GHz, jitter)

        return SolverResults.model_validate(
            {
                "schema": SOLVER_RESULTS_SCHEMA,
                "candidate_id": prepared.candidate_id,
                "solver": SolverIdentity(
                    name=self.name,
                    version=self.version,
                    classification=self.classification,
                    command_line=f"mock://{fixture}",
                ).model_dump(),
                "run_id": prepared.run_id,
                "convergence": Convergence(
                    status=(
                        ConvergenceStatus.NOT_CONVERGED
                        if fixture == "no_feasible_design"
                        and payload.get("force_non_convergence")
                        else ConvergenceStatus.CONVERGED
                    ),
                    metric="relative_change",
                    value=1.0e-4,
                    tolerance=1.0e-3,
                ).model_dump(),
                "frequency_GHz": frequencies,
                "s_parameters": {"S21_dB": s21, "S11_dB": s11},
                "z_parameters": {},
                "eigenmodes": [m.model_dump() for m in eigenmodes],
                "artifacts": [],
                "synthetic": True,
                "notes": [SYNTHETIC_NOTE, f"fixture={fixture}"],
            }
        )


# --- synthetic response shaping --------------------------------------------


def _frequency_grid(payload: dict[str, Any], must_include: tuple[float, ...]) -> list[float]:
    """Ascending grid that contains each ``must_include`` frequency exactly.

    The filter gate refuses to interpolate a stopband figure, so the emission
    frequency must be an exact grid point.
    """
    start = payload["frequency_start_GHz"]
    stop = payload["frequency_stop_GHz"]
    points = payload["frequency_points"]
    step = (stop - start) / (points - 1)
    grid = [start + i * step for i in range(points)]
    grid.extend(f for f in must_include if start <= f <= stop)
    # Deduplicate while preserving exactness of the required points.
    unique = sorted(set(grid))
    return unique


def _synthetic_stopband_dB(fixture: str, payload: dict[str, Any], jitter: float) -> float:
    """Synthetic stopband depth in dB at the emission frequency.

    The frozen gate boundaries are 34 dB (minimum) and 36 dB (target), so the
    fixtures are placed either side of them deliberately.
    """
    if fixture == "filter_pass":
        return 37.5
    if fixture in ("filter_fail", "no_feasible_design"):
        return 28.0
    # Default: depth varies deterministically with the two swept ENGINEERING-SEED
    # parameters, spanning the 34 dB boundary so the 3x3 sweep is not uniform.
    cavity = payload["cavity_height_above_chip_mm"]
    bore = payload["bore_diameter_mm"]
    return 30.0 + 6.0 * (cavity - 1.25) / 0.5 - 2.5 * (bore - 2.25) / 0.5 + 1.5 * jitter


def _bandstop_dB(frequency_GHz: float, centre_GHz: float, depth_dB: float) -> float:
    """Lorentzian-shaped synthetic bandstop, in dB of attenuation."""
    half_width_GHz = 0.15
    detuning = (frequency_GHz - centre_GHz) / half_width_GHz
    return depth_dB / (1.0 + detuning**2)


def _return_loss_dB(frequency_GHz: float, readout_GHz: float, jitter: float) -> float:
    """Synthetic |S11| shape with a dip at the readout line."""
    half_width_GHz = 0.05
    detuning = (frequency_GHz - readout_GHz) / half_width_GHz
    depth = 18.0 + 4.0 * jitter
    return depth / (1.0 + detuning**2) + 0.5


def _synthetic_eigenmodes(fixture: str, readout_GHz: float, jitter: float) -> list[Eigenmode]:
    """Synthetic package/eigenmode census."""
    if fixture in ("collision_fail", "no_feasible_design"):
        # Place a mode 4 MHz from the readout root: inside the pre-check
        # clearance, so P4PRE_SPECTRAL flags it.
        offset_GHz = 0.004
    elif fixture == "collision_pass":
        offset_GHz = 0.250
    else:
        offset_GHz = 0.120 + 0.080 * jitter

    return [
        Eigenmode(
            frequency_GHz=readout_GHz + offset_GHz,
            quality_factor=1.0e4,
            label="synthetic_package_mode_1",
        ),
        Eigenmode(
            frequency_GHz=readout_GHz + 1.35 + 0.2 * jitter,
            quality_factor=5.0e3,
            label="synthetic_package_mode_2",
        ),
    ]
