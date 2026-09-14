"""F8 Purcell model (spec §5.3).

Executable definition (spec §4.5)::

    Gamma_P = kappa(omega_if) * |<f|a|i>|^2

The required quantity is the actual dressed transition matrix element::

    |<dressed(1,0)| a |dressed(2,0)>|^2

The bare-admixture overlap (0.011815) is a DIFFERENT QUANTITY and is not
implemented as a substitute (spec §4.5, §5.3). :func:`assert_not_bare_admixture`
guards against the two being confused, and is applied to every computed weight.
"""

from __future__ import annotations

from typing import Any

from contracts import master
from models import dressed_system


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


def purcell_weight(
    Nq: int = dressed_system.PRODUCTION_NQ,
    Nph: int = dressed_system.PRODUCTION_NPH,
) -> float:
    """|<dressed(1,0)| a |dressed(2,0)>|² at the nominal operating point."""
    weight = dressed_system.nominal_solution(Nq, Nph).purcell_weight()
    assert_not_bare_admixture(weight)
    return weight


def purcell_rate(kappa_at_emission_Hz: float, weight: float | None = None) -> float:
    """Gamma_P = kappa(omega_if) * |<f|a|i>|², in the units of ``kappa``.

    Args:
        kappa_at_emission_Hz: Resonator linewidth evaluated at the dressed
            emission frequency. In QMHP-CEM v0.1 this is a SOLVED quantity that
            must come from an EM solver; there is no default, because assuming
            one would fabricate the very number the filter gate exists to test.
        weight: F8 weight. Defaults to the computed nominal weight.
    """
    if weight is None:
        weight = purcell_weight()
    assert_not_bare_admixture(weight)
    return kappa_at_emission_Hz * weight


def emission_frequency_GHz(
    Nq: int = dressed_system.PRODUCTION_NQ,
    Nph: int = dressed_system.PRODUCTION_NPH,
) -> float:
    """Dressed |1> -> |2> emission frequency, the filter stopband target."""
    return dressed_system.nominal_solution(Nq, Nph).dressed_f12_GHz


def filter_constraint() -> dict[str, Any]:
    """Frozen filter constraint driving the P6E2_FILTER gate (spec §4.5)."""
    return dict(master.get("purcell_f8.filter_constraint"))
