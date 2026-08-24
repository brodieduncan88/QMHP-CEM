"""Static fluxonium model (spec §5.1). NOT IMPLEMENTED in v0.1.

Required implementation:

* verified finite-difference Hamiltonian on the declared 3201-point phase grid
  over [-8*pi, +8*pi], second-difference kinetic operator;
* outputs: first relevant eigenfrequencies, charge matrix elements,
  sin(delta/2) matrix element, optional convergence diagnostics;
* regression-tested against spec §4.2.
"""

from __future__ import annotations

from typing import Any

from contracts import master
from models._stub import PhysicsNotImplemented


def phase_grid_convention() -> dict[str, Any]:
    """The frozen phase-grid convention. Reading frozen data is always allowed."""
    grid = master.get("static_fluxonium.phase_grid")
    return {
        "grid_points": grid["grid_points"],
        "phase_min": grid["phase_min"],
        "phase_max": grid["phase_max"],
        "kinetic_operator": grid["kinetic_operator"],
    }


def reference_values() -> dict[str, Any]:
    """Frozen §4.2 reference values the implementation must reproduce."""
    return dict(master.get("static_fluxonium.reference_values"))


def solve_static(
    EC_GHz: float | None = None,
    EJ_GHz: float | None = None,
    EL_GHz: float | None = None,
    phi_ext: float | None = None,
) -> dict[str, Any]:
    """Solve the static fluxonium spectrum. NOT IMPLEMENTED.

    Raises:
        PhysicsNotImplemented: always, in v0.1.
    """
    raise PhysicsNotImplemented(
        model="static_fluxonium",
        spec_section="5.1",
        regression_pins={
            "f01_GHz": master.get("static_fluxonium.reference_values.f01_GHz"),
            "f02_GHz": master.get("static_fluxonium.reference_values.f02_GHz"),
            "n12": master.get("static_fluxonium.reference_values.n12"),
            "sin_delta_over_2_02": master.get(
                "static_fluxonium.reference_values.sin_delta_over_2_02"
            ),
        },
        detail=(
            "Implement the finite-difference Hamiltonian on the frozen "
            "3201-point grid; do not substitute an analytic approximation."
        ),
    )
