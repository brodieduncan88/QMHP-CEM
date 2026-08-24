"""Coupled dressed-system model (spec §5.2). NOT IMPLEMENTED in v0.1.

Required implementation:

* construct the coupled fluxonium-resonator Hamiltonian;
* production truncation Nq=10, Nph=12; support the (14, 25) spot check;
* adiabatic maximum-overlap state labelling;
* Eq.(7) used ONLY to seed the root search — it is a diagnostic, not the
  operating point (spec §4.3);
* ``scipy.optimize.brentq`` or an explicitly equivalent bracketed root solver;
* solve the logical-blind condition in the dressed system.

The production-to-high-truncation shift of approximately +0.92 kHz is expected
and is NOT an error condition (spec §4.4).
"""

from __future__ import annotations

from typing import Any

from contracts import master
from models._stub import PhysicsNotImplemented

#: Production truncation (spec §4.4).
PRODUCTION_NQ = 10
PRODUCTION_NPH = 12

#: High-truncation spot check (spec §4.4).
SPOT_CHECK_NQ = 14
SPOT_CHECK_NPH = 25


def eq7_seed() -> dict[str, Any]:
    """Frozen Eq.(7) dispersive diagnostic used to seed the root search.

    These are DIAGNOSTIC quantities. The exact dressed root is authoritative
    for the operating point (spec §4.3).
    """
    return dict(master.get("eq7_diagnostic"))


def regression_pins() -> dict[str, Any]:
    """Frozen §4.4 dressed-system pins."""
    ds = master.get("dressed_system")
    return {
        "root_10_12_GHz": ds["production_convention"]["root_GHz"],
        "root_14_25_GHz": ds["high_truncation_spot_check"]["root_GHz"],
        "sink_line_GHz": ds["physical_pull_references"]["sink_line_GHz"],
        "dressed_f12_GHz": ds["physical_pull_references"]["dressed_f12_GHz"],
        "sink_logical_contrast_MHz": ds["physical_pull_references"][
            "sink_logical_contrast_MHz"
        ],
    }


def solve_dressed_root(Nq: int = PRODUCTION_NQ, Nph: int = PRODUCTION_NPH) -> float:
    """Solve the logical-blind dressed root in GHz. NOT IMPLEMENTED.

    Raises:
        PhysicsNotImplemented: always, in v0.1.
    """
    raise PhysicsNotImplemented(
        model="dressed_system",
        spec_section="5.2",
        regression_pins=regression_pins(),
        detail=(
            f"Requested truncation Nq={Nq}, Nph={Nph}. Use a bracketed root "
            "solver seeded from Eq.(7); do not report the perturbative root as "
            "the operating point."
        ),
    )


def dressed_spectrum(Nq: int = PRODUCTION_NQ, Nph: int = PRODUCTION_NPH) -> dict[str, Any]:
    """Full dressed spectrum including omega24 and pulls. NOT IMPLEMENTED."""
    raise PhysicsNotImplemented(
        model="dressed_spectrum",
        spec_section="5.2",
        regression_pins=regression_pins(),
        detail=(
            "Must supply omega24 for the COLLISION gate and the dressed f12 "
            "emission frequency for the P6E2_FILTER gate."
        ),
    )
