"""Collision screen (spec §4.6, §6.2).

The collision *rule* is a frozen threshold comparison and is implemented here.
Computing omega24 is physics and requires the dressed system (spec §5.2), so
:func:`omega24` is a stub.
"""

from __future__ import annotations

from contracts import master
from models._stub import PhysicsNotImplemented
from models.dressed_system import regression_pins


def minimum_separation_MHz() -> float:
    """Frozen minimum |omega24 - f_readout| in MHz (MASTER-FROZEN)."""
    return master.get("collision.minimum_abs_omega24_minus_readout_MHz")


def separation_MHz(omega24_GHz: float, f_readout_GHz: float) -> float:
    """|omega24 - f_readout| in MHz.

    Units are explicit throughout: inputs GHz, output MHz (spec §7.3).
    """
    return abs(omega24_GHz - f_readout_GHz) * 1000.0


#: Numerical tolerance on the boundary comparison, in MHz.
#:
#: Classification: ENGINEERING-RULE (not MASTER-FROZEN).
#:
#: The frozen rule is ``>= 13 MHz``, so a separation of exactly 13.000 MHz
#: passes. Computing that separation as a difference of two GHz values in
#: binary floating point can land a nominally-exact 13 MHz at
#: 12.999999999999789 MHz, which would emit a spurious FAIL on a HARD gate.
#: This tolerance is far below any physically meaningful separation (1 uHz)
#: and exists solely to make the frozen boundary behave as specified.
BOUNDARY_ATOL_MHz = 1e-9


def passes(omega24_GHz: float, f_readout_GHz: float) -> bool:
    """Whether the pair clears the frozen 13 MHz collision gate.

    The comparison is ``>=``: exactly 13.0 MHz passes (spec §6.2), within
    :data:`BOUNDARY_ATOL_MHz`.
    """
    separation = separation_MHz(omega24_GHz, f_readout_GHz)
    return separation >= minimum_separation_MHz() - BOUNDARY_ATOL_MHz


def omega24(Nq: int = 10, Nph: int = 12) -> float:
    """Dressed omega24 in GHz. NOT IMPLEMENTED."""
    raise PhysicsNotImplemented(
        model="omega24",
        spec_section="5.2",
        regression_pins=regression_pins(),
        detail="omega24 is produced by the dressed-system spectrum.",
    )
