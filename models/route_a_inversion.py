"""Route A inversion: normal-mode data to the gauge-invariant coupling triple.

Route A (``docs/coupled-candidate/extraction-routes.md`` §2) observes, for the
S1 subsystem, the two normal-mode frequencies of the linear EM model and the
energy participation of the declared lumped inductor at the fluxonium site.
Checkpoint A declared the extraction target to be the charging-energy matrix
``E_C`` together with the readout mode's ``(E_C,RR, E_L,R)`` and called those
"circuit-level, convention-free quantities". **That was wrong for the readout
node**, and this module is the correction
(``docs/coupled-candidate/route-a-identifiability.md``).

The readout node carries no lumped element: nothing in the electromagnetic
model defines the scale of its node flux. The rescaling

.. code-block:: text

    Phi_R -> s Phi_R,  Q_R -> Q_R / s      (s > 0)

leaves the Hamiltonian, every eigenfrequency and every participation exactly
invariant while moving

.. code-block:: text

    (C^-1)_FR -> (C^-1)_FR / s,  (C^-1)_RR -> (C^-1)_RR / s^2,  L_R -> L_R / s^2

by an arbitrary factor. ``E_C,FR``, ``E_C,RR`` and ``L_R`` are therefore **not
identifiable** from Route A data, and reporting them without a declared gauge
would report a convention, not a measurement.

What *is* identifiable is the triple

.. code-block:: text

    E_C,FF   the fluxonium charging energy   (its node is fixed by the declared
                                              lumped branch at the element site)
    f_R      the bare readout frequency      sqrt(8 E_C,RR E_L,R), gauge-invariant
    g        the coupling                    8 E_C,FR n_zpf,R, gauge-invariant

with the fluxonium's linear inductance ``L_F`` known by declaration (the
superinductor). Each is invariant because the gauge factors cancel; the proof
is one line for ``f_R`` and ``E_C,FF`` and is carried out for ``g`` in
:func:`coupling_GHz`, whose closed form contains no ``L_R`` at all.

Counting: with ``L_F`` known the circuit has four parameters
(``c_FF, c_FR, c_RR, L_R``) and one gauge direction, so three physical degrees
of freedom. The data are two frequencies and one participation: the second
participation is not independent because both Route A sum rules hold
(``sum_j p_mj = 1`` per mode and ``sum_m p_mj = 1`` per inductor), which this
module checks rather than assumes. The inversion is therefore exactly
determined, and :func:`invert_two_node` solves it in closed form.

Nothing here reads, imports or depends on any Route B quantity: the inversion
consumes eigenfrequencies and participations only. Nothing here is coupled EM
evidence; it is the arithmetic that will be applied to such evidence, and it
is demonstrated on synthetic circuits with known parameters by
``scripts/route_a_synthetic_demo.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

#: Physical constants (CODATA exact SI, as used throughout the repository).
ELEMENTARY_CHARGE_C = 1.602176634e-19
PLANCK_J_S = 6.62607015e-34
FLUX_QUANTUM_WB = PLANCK_J_S / (2.0 * ELEMENTARY_CHARGE_C)
#: Reduced flux quantum Phi_0 / 2 pi (Wb).
REDUCED_FLUX_QUANTUM_WB = FLUX_QUANTUM_WB / (2.0 * math.pi)

#: Relative tolerance of the forward-map check that discriminates the two
#: algebraic roots of the inversion. ENGINEERING-RULE of this module, not a
#: physical threshold: it only decides which root reproduces the input data.
ROOT_SELECTION_RTOL = 1.0e-9

#: Relative tolerance of the sum-rule checks on the supplied participations.
SUM_RULE_RTOL = 1.0e-6


class RouteAInversionError(RuntimeError):
    """The inversion could not return exactly one root consistent with the data."""


@dataclass(frozen=True)
class TwoNodeCircuit:
    """A two-node linear circuit in one explicit gauge.

    ``c_*`` are entries of the inverse capacitance matrix (1/F) and ``L_*``
    the branch inductances (H). Only ``L_F`` is a declared quantity; the
    readout entries are gauge-dependent (see the module docstring) and are
    carried here so that synthetic circuits can be written down, transformed
    and inverted.
    """

    c_FF: float
    c_FR: float
    c_RR: float
    L_F: float
    L_R: float

    def __post_init__(self) -> None:
        if self.c_FF <= 0 or self.c_RR <= 0:
            raise ValueError("diagonal inverse-capacitance entries must be positive")
        if self.L_F <= 0 or self.L_R <= 0:
            raise ValueError("branch inductances must be positive")
        if self.c_FF * self.c_RR <= self.c_FR**2:
            raise ValueError("the inverse capacitance matrix must be positive definite")

    # --- gauge -------------------------------------------------------------

    def gauge_transform(self, s: float) -> "TwoNodeCircuit":
        """Rescale the readout node flux by ``s``: a different circuit, same physics."""
        if s <= 0:
            raise ValueError("the gauge factor must be positive")
        return TwoNodeCircuit(
            c_FF=self.c_FF, c_FR=self.c_FR / s, c_RR=self.c_RR / s**2,
            L_F=self.L_F, L_R=self.L_R / s**2,
        )

    # --- gauge-invariant parameters ---------------------------------------

    @property
    def a(self) -> float:
        """``omega_F^2`` (rad/s)^2: the fluxonium branch, invariant."""
        return self.c_FF / self.L_F

    @property
    def b(self) -> float:
        """``omega_R^2`` (rad/s)^2: the readout branch; the gauge factors cancel."""
        return self.c_RR / self.L_R

    @property
    def k(self) -> float:
        """Coupling rate ``|c_FR| / sqrt(L_F L_R)`` ((rad/s)^2); invariant."""
        return abs(self.c_FR) / math.sqrt(self.L_F * self.L_R)

    def invariants(self) -> "InvariantTriple":
        return InvariantTriple(
            E_C_FF_GHz=charging_energy_GHz(self.c_FF),
            f_F_GHz=math.sqrt(self.a) / (2.0 * math.pi) / 1e9,
            f_R_GHz=math.sqrt(self.b) / (2.0 * math.pi) / 1e9,
            g_GHz=coupling_GHz(self.k, self.b, self.L_F),
        )

    # --- forward map -------------------------------------------------------

    def normal_modes(self) -> "NormalModeData":
        """Exact normal-mode frequencies and inductor participations."""
        a, b, k2 = self.a, self.b, self.k**2
        root = math.sqrt((a - b) ** 2 + 4.0 * k2)
        w2_plus, w2_minus = 0.5 * ((a + b) + root), 0.5 * ((a + b) - root)
        if w2_minus <= 0:
            raise ValueError("the circuit has a non-positive normal-mode frequency")
        return NormalModeData(
            f_plus_GHz=math.sqrt(w2_plus) / (2.0 * math.pi) / 1e9,
            f_minus_GHz=math.sqrt(w2_minus) / (2.0 * math.pi) / 1e9,
            p_plus_F=_participation(w2_plus, a, k2),
            p_minus_F=_participation(w2_minus, a, k2),
            L_F_H=self.L_F,
        )


def _participation(w2: float, a: float, k2: float) -> float:
    """Fluxonium-inductor participation of the mode at ``w2``.

    From the eigenvector of ``C^-1 L^-1``: ``u_R/u_F = (w^2 - a) L_R / c_FR``,
    so ``p_F = k^2 / (k^2 + (w^2 - a)^2)`` with ``k^2 = c_FR^2/(L_F L_R)``.
    Both ``L_R`` and ``c_FR`` appear only through ``k``, which is why the
    participation is gauge-invariant.
    """
    if k2 == 0.0:
        return 1.0 if abs(w2 - a) < abs(w2) * 1e-15 else 0.0
    return k2 / (k2 + (w2 - a) ** 2)


@dataclass(frozen=True)
class NormalModeData:
    """What Route A observes: two mode frequencies and the site participation.

    ``p_minus_F`` is recorded but is not an independent datum: the Route A sum
    rules make it ``1 - p_plus_F``. :meth:`sum_rule_residual` is the check.
    ``L_F_H`` is the declared lumped inductance at the fluxonium element site,
    not an observation.
    """

    f_plus_GHz: float
    f_minus_GHz: float
    p_plus_F: float
    p_minus_F: float
    L_F_H: float

    def __post_init__(self) -> None:
        if not (self.f_plus_GHz > self.f_minus_GHz > 0):
            raise ValueError("expected f_plus > f_minus > 0 (GHz)")
        for p in (self.p_plus_F, self.p_minus_F):
            if not (0.0 <= p <= 1.0):
                raise ValueError("participations must lie in [0, 1]")
        if self.L_F_H <= 0:
            raise ValueError("the declared L_F must be positive")

    @property
    def sum_rule_residual(self) -> float:
        """``|p_plus_F + p_minus_F - 1|``: zero for a lossless two-mode circuit."""
        return abs(self.p_plus_F + self.p_minus_F - 1.0)

    def check_sum_rule(self, rtol: float = SUM_RULE_RTOL) -> None:
        if self.sum_rule_residual > rtol:
            raise RouteAInversionError(
                f"the Route A sum rule sum_m p_mF = 1 is violated by "
                f"{self.sum_rule_residual:.3e} (tolerance {rtol:.1e}); the mode pair is "
                f"incomplete or a mode outside the pair carries site participation"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "f_plus_GHz": self.f_plus_GHz, "f_minus_GHz": self.f_minus_GHz,
            "p_plus_F": self.p_plus_F, "p_minus_F": self.p_minus_F,
            "L_F_H": self.L_F_H, "sum_rule_residual": self.sum_rule_residual,
        }


@dataclass(frozen=True)
class InvariantTriple:
    """The identifiable output of Route A.

    ``f_F_GHz`` is fixed by ``E_C_FF_GHz`` and the declared ``L_F``, so the
    independent content is three numbers, matching the three independent data.
    """

    E_C_FF_GHz: float
    f_F_GHz: float
    f_R_GHz: float
    g_GHz: float

    @property
    def g_MHz(self) -> float:
        return self.g_GHz * 1e3

    def as_dict(self) -> dict[str, Any]:
        return {
            "E_C_FF_GHz": self.E_C_FF_GHz, "f_F_GHz": self.f_F_GHz,
            "f_R_GHz": self.f_R_GHz, "g_GHz": self.g_GHz, "g_MHz": self.g_MHz,
        }

    def relative_difference(self, other: "InvariantTriple") -> dict[str, float]:
        out: dict[str, float] = {}
        for key, mine in self.as_dict().items():
            theirs = other.as_dict()[key]
            scale = max(abs(mine), abs(theirs))
            out[key] = 0.0 if scale == 0.0 else abs(mine - theirs) / scale
        return out


def charging_energy_GHz(c: float) -> float:
    """``E_C/h = e^2 c / 2h`` in GHz for an inverse-capacitance entry ``c`` (1/F)."""
    return ELEMENTARY_CHARGE_C**2 * c / (2.0 * PLANCK_J_S) / 1e9


def coupling_GHz(k: float, b: float, L_F: float) -> float:
    """``g`` in GHz from the invariants ``k``, ``b = omega_R^2`` and ``L_F``.

    Derivation. ``g = 8 E_C,FR n_zpf,R`` with
    ``n_zpf,R = (E_L,R / 32 E_C,RR)^(1/4)`` (the Master's ``g n (a + a^dag)``
    convention, ``coupling-definition.md`` §3). Substituting
    ``E_C,FR = e^2 c_FR / 2h``, ``E_C,RR = e^2 c_RR / 2h``,
    ``E_L,R = phi_r^2 / (L_R h)``, ``c_FR = k sqrt(L_F L_R)`` and
    ``c_RR = b L_R`` gives

    .. code-block:: text

        g = 2 e^(3/2) sqrt(L_F) sqrt(phi_r) k / (h b^(1/4))

    in which ``L_R`` has cancelled: ``g`` does not depend on the readout gauge.
    """
    if b <= 0:
        raise ValueError("omega_R^2 must be positive")
    g_hz = (
        2.0 * ELEMENTARY_CHARGE_C**1.5 * math.sqrt(L_F)
        * math.sqrt(REDUCED_FLUX_QUANTUM_WB) * k / (PLANCK_J_S * b**0.25)
    )
    return g_hz / 1e9


def forward_two_node(circuit: TwoNodeCircuit) -> NormalModeData:
    """Convenience wrapper: circuit -> Route A observables."""
    return circuit.normal_modes()


def invert_two_node(
    data: NormalModeData,
    *,
    rtol: float = ROOT_SELECTION_RTOL,
    check_sum_rule: bool = True,
) -> tuple[InvariantTriple, dict[str, Any]]:
    """Route A observables -> the gauge-invariant triple, in closed form.

    Solves, for ``a = omega_F^2``, ``b = omega_R^2`` and ``k^2``:

    .. code-block:: text

        a + b               = w2_plus + w2_minus
        (a - b)^2 + 4 k^2   = (w2_plus - w2_minus)^2
        p_plus_F            = k^2 / (k^2 + (w2_plus - a)^2)

    Eliminating ``b`` and ``k^2`` gives a quadratic in ``a`` with two roots,
    both of which satisfy the squared equation; only one reproduces the
    observed data under the forward map, and this function selects it by
    running :func:`forward_two_node` on each candidate. If no candidate or
    more than one candidate reproduces the data, it raises rather than
    guessing, because a silently chosen root would be a fabricated coupling.

    Returns the triple and a diagnostics dict (both roots, the residual of the
    accepted one, the sum-rule residual). Reads no Route B quantity.
    """
    if check_sum_rule:
        data.check_sum_rule()
    if not (0.0 < data.p_plus_F < 1.0):
        raise RouteAInversionError(
            f"p_plus_F = {data.p_plus_F} is 0 or 1: the two modes do not hybridise at the "
            f"fluxonium site, so the coupling is not identifiable from this pair"
        )

    w2p = (2.0 * math.pi * data.f_plus_GHz * 1e9) ** 2
    w2m = (2.0 * math.pi * data.f_minus_GHz * 1e9) ** 2
    L_F = data.L_F_H
    S, D = w2p + w2m, w2p - w2m
    r = data.p_plus_F / (1.0 - data.p_plus_F)

    # (2a - S)^2 + 4 r (w2p - a)^2 = D^2
    A = 4.0 + 4.0 * r
    B = -4.0 * S - 8.0 * r * w2p
    C = S**2 + 4.0 * r * w2p**2 - D**2
    disc = B * B - 4.0 * A * C
    if disc < 0.0:
        raise RouteAInversionError(
            f"the inversion has no real root (discriminant {disc:.3e}); the supplied "
            f"frequencies and participation are not those of a two-node circuit"
        )
    roots = ((-B + math.sqrt(disc)) / (2.0 * A), (-B - math.sqrt(disc)) / (2.0 * A))

    accepted: list[tuple[TwoNodeCircuit, float]] = []
    candidates: list[dict[str, Any]] = []
    for a in roots:
        b = S - a
        k2 = r * (w2p - a) ** 2
        entry: dict[str, Any] = {"a": a, "b": b, "k2": k2}
        if a <= 0 or b <= 0 or k2 < 0:
            entry["rejected"] = "non-physical: a, b or k^2 out of range"
            candidates.append(entry)
            continue
        # Rebuild a circuit in the unit-L_R gauge and run the forward map.
        circuit = _circuit_in_unit_gauge(a, b, k2, L_F)
        residual = _forward_residual(circuit, data)
        entry["forward_residual"] = residual
        if residual <= rtol:
            accepted.append((circuit, residual))
        else:
            entry["rejected"] = f"forward map disagrees with the data ({residual:.3e} > {rtol:.1e})"
        candidates.append(entry)

    if not accepted:
        raise RouteAInversionError(
            "no algebraic root reproduces the supplied data under the forward map; "
            f"candidates: {candidates}"
        )
    if len(accepted) > 1:
        best, second = sorted(accepted, key=lambda x: x[1])[:2]
        raise RouteAInversionError(
            f"the data do not discriminate the two roots (residuals {best[1]:.3e} and "
            f"{second[1]:.3e}); the coupling is not identifiable from them"
        )

    circuit, residual = accepted[0]
    diagnostics = {
        "roots": candidates,
        "accepted_forward_residual": residual,
        "sum_rule_residual": data.sum_rule_residual,
        "gauge": "unit readout inductance (L_R = 1 H); the triple is gauge-invariant",
    }
    return circuit.invariants(), diagnostics


def _circuit_in_unit_gauge(a: float, b: float, k2: float, L_F: float) -> TwoNodeCircuit:
    """A representative circuit with ``L_R = 1 H``; any gauge gives the same triple."""
    L_R = 1.0
    return TwoNodeCircuit(
        c_FF=a * L_F, c_FR=math.sqrt(k2 * L_F * L_R), c_RR=b * L_R, L_F=L_F, L_R=L_R
    )


def _forward_residual(circuit: TwoNodeCircuit, data: NormalModeData) -> float:
    """Largest relative disagreement between a candidate's forward map and the data."""
    try:
        got = circuit.normal_modes()
    except ValueError:
        return math.inf
    terms = [
        abs(got.f_plus_GHz - data.f_plus_GHz) / data.f_plus_GHz,
        abs(got.f_minus_GHz - data.f_minus_GHz) / data.f_minus_GHz,
        abs(got.p_plus_F - data.p_plus_F),
        abs(got.p_minus_F - data.p_minus_F),
    ]
    return max(terms)


def circuit_from_design(
    *, f_F_GHz: float, f_R_GHz: float, g_GHz: float, L_F_H: float, L_R_H: float = 1.0e-9
) -> TwoNodeCircuit:
    """Build a synthetic circuit with prescribed invariants.

    Used to generate known test cases: the invariants are chosen, the circuit
    is constructed in one arbitrary gauge, and the inversion must recover the
    invariants from its normal modes whatever gauge is applied afterwards.
    """
    a = (2.0 * math.pi * f_F_GHz * 1e9) ** 2
    b = (2.0 * math.pi * f_R_GHz * 1e9) ** 2
    # Invert g = 2 e^(3/2) sqrt(L_F phi_r) k / (h b^(1/4)) for k.
    k = (
        g_GHz * 1e9 * PLANCK_J_S * b**0.25
        / (2.0 * ELEMENTARY_CHARGE_C**1.5 * math.sqrt(L_F_H) * math.sqrt(REDUCED_FLUX_QUANTUM_WB))
    )
    return TwoNodeCircuit(
        c_FF=a * L_F_H, c_FR=k * math.sqrt(L_F_H * L_R_H), c_RR=b * L_R_H, L_F=L_F_H, L_R=L_R_H
    )
