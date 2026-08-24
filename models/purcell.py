"""F8 Purcell model (spec §5.3). NOT IMPLEMENTED in v0.1.

Executable definition (spec §4.5)::

    Gamma_P = kappa(omega_if) * |<f|a|i>|^2

The required quantity is the actual dressed transition matrix element::

    |<dressed(1,0)| a |dressed(2,0)>|^2  ->  0.01182198

The bare-admixture overlap (0.011815) is a DIFFERENT QUANTITY and must not be
implemented as a substitute (spec §4.5, §5.3). :func:`assert_not_bare_admixture`
exists so that a future implementation trips loudly if the two are confused.
"""

from __future__ import annotations

from typing import Any

from contracts import master
from models._stub import PhysicsNotImplemented


def dressed_weight_pin() -> float:
    """Frozen exact dressed weight (spec §4.5)."""
    return master.get("purcell_f8.dressed_weight")


def bare_admixture_reference() -> float:
    """The DIFFERENT quantity, carried only so it can be distinguished."""
    return master.get("purcell_f8.bare_admixture_overlap_approx")


def assert_not_bare_admixture(weight: float, rel_tol: float = 1e-4) -> None:
    """Guard against substituting the bare-admixture overlap for F8.

    Raises:
        ValueError: if ``weight`` matches the bare admixture rather than the
            frozen dressed weight.
    """
    bare = bare_admixture_reference()
    dressed = dressed_weight_pin()
    if abs(weight - bare) <= rel_tol * abs(bare) and abs(weight - dressed) > rel_tol * abs(
        dressed
    ):
        raise ValueError(
            f"computed Purcell weight {weight!r} matches the bare-admixture "
            f"overlap ({bare}) rather than the exact dressed weight ({dressed}). "
            f"These are different quantities and must not be substituted "
            f"(spec §4.5)."
        )


def purcell_weight() -> float:
    """|<dressed(1,0)| a |dressed(2,0)>|^2. NOT IMPLEMENTED."""
    raise PhysicsNotImplemented(
        model="f8_purcell_weight",
        spec_section="5.3",
        regression_pins={"f8_dressed_weight": dressed_weight_pin()},
        detail=(
            "Compute the dressed transition matrix element. Do NOT implement "
            f"the bare-admixture overlap ({bare_admixture_reference()}) as a "
            "substitute."
        ),
    )


def purcell_rate(kappa_at_emission: float) -> float:
    """Gamma_P = kappa(omega_if) * |<f|a|i>|^2. NOT IMPLEMENTED."""
    raise PhysicsNotImplemented(
        model="purcell_rate",
        spec_section="5.3",
        regression_pins={"f8_dressed_weight": dressed_weight_pin()},
    )


def filter_constraint() -> dict[str, Any]:
    """Frozen filter constraint driving the P6E2_FILTER gate (spec §4.5)."""
    return dict(master.get("purcell_f8.filter_constraint"))
