"""Collision screen (spec §4.6, §6.2).

The collision *rule* is a frozen threshold comparison and is implemented here.
Computing omega24 is physics and requires the dressed system (spec §5.2), so
:func:`omega24` is a stub.
"""

from __future__ import annotations

from contracts import master
from models import dressed_system, fluxonium


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


def omega24(
    Nq: int = dressed_system.PRODUCTION_NQ,
    Nph: int = dressed_system.PRODUCTION_NPH,
) -> float:
    """The omega24 transition in GHz, from the static spectrum.

    omega24 = f_4 - f_2, the spectator transition screened against the readout
    line by the frozen 13 MHz gate.
    """
    return fluxonium.nominal_spectrum(
        levels=max(Nq, fluxonium.DEFAULT_LEVELS)
    ).f(4, 2)


def readout_root_GHz(
    Nq: int = dressed_system.PRODUCTION_NQ,
    Nph: int = dressed_system.PRODUCTION_NPH,
) -> float:
    """The dressed logical-blind readout root in GHz."""
    return dressed_system.nominal_root(Nq, Nph)


def screen(
    EC_GHz: float | None = None,
    EJ_GHz: float | None = None,
    EL_GHz: float | None = None,
) -> dict[str, float | bool]:
    """Run the collision screen for one device.

    Passing no arguments screens the frozen Branch-A nominal device. Passing
    perturbed energies screens one draw of a tolerance ensemble.
    """
    if EC_GHz is None and EJ_GHz is None and EL_GHz is None:
        spectrum = fluxonium.nominal_spectrum()
        root = dressed_system.nominal_root()
    else:
        spectrum = fluxonium.solve_static(EC_GHz, EJ_GHz, EL_GHz)
        root = dressed_system.solve_dressed_root(spectrum=spectrum)

    w24 = spectrum.f(4, 2)
    separation = separation_MHz(w24, root)
    return {
        "omega24_GHz": w24,
        "f_readout_GHz": root,
        "separation_MHz": separation,
        "threshold_MHz": minimum_separation_MHz(),
        "passes": passes(w24, root),
    }
