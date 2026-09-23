"""The port-stiffness diagnostic, derived from pinned Palace v0.13.0 source.

Palace reports two numbers for a lumped inductive port in an eigenmode run,
and they are not the same quantity:

``E_ind``
    ``1/2 |L| |I|²`` with ``I = V/(iωL)`` and ``V`` the *width-averaged line
    voltage* ``V = 1/w ∫_Γ E·l̂ dS`` (``lumpedportoperator.cpp:200-213``,
    ``postoperator.cpp:493-508``). It is a rank-one functional of the port
    field: it sees one scalar, the average of ``E`` along the port direction.

the port's contribution to the stiffness matrix
    Palace assembles the inductive port face into ``K`` as a boundary
    ``VectorFEMassIntegrator`` with coefficient ``1/L_s``
    (``lumpedportoperator.cpp:571-591``, ``spaceoperator.cpp:300-307`` and
    ``:236-238``), so what enters the eigenvalue is
    ``∫_Γ (1/L_s) |E_t|² dS`` — the *full* tangential field, pointwise.

For an eigenpair the Rayleigh identity ``xᴴKx = ω² xᴴMx`` splits into

    E_mag + E_port  =  E_elec + E_cap ,        E_port := (1/2ω²) ∫_Γ (1/L_s)|E_t|² dS

so an energy-balance "failure" measured with ``E_ind`` in place of ``E_port``
is a statement about the two functionals differing, not about the solve.

This module evaluates ``E_port`` **independently of the energy balance**, from
the two interface-dielectric probes written to ``surface-Q.csv``. The
conversion constant is *derived* from the pinned source, the declared port
geometry and the unit conventions; nothing here is fitted, and in particular
nothing is calibrated on modes selected for having a favourable balance.

Derivation
----------

``Boundaries.Postprocessing.Dielectric`` with ``Type: "Default"`` integrates
``0.5·t·ε·|E|²`` and with ``Type: "MA"`` integrates ``0.5·(t/ε)·|E_n|²``
(``fem/coefficient.hpp:373-413``); both take the field from the same side by
the same rule (``GetLocalVectorValue``, ``coefficient.hpp:330-360``), so with
equal ``t`` and ``ε = 1`` their difference is exactly ``0.5·t_nd·|E_t|²``
pointwise, and the side choice cancels. Each is integrated with
``BoundaryLFIntegrator`` against the H1 space, whose basis is a partition of
unity, so the linear-form sum is the plain surface integral
(``surfacepostoperator.cpp:287-301``). The driver divides by ``E_elec+E_cap``
(``postoperator.cpp:419-427``, ``basesolver.cpp:538-540``,
``eigensolver.cpp:349``) — the same denominator the port EPR uses. Hence

    p_D - p_MA = (0.5 · t_nd · ∫_Γ |E_t|² dS) / (E_elec + E_cap)

and therefore the port participation is

    p_port = E_port / (E_elec + E_cap) = KAPPA · (p_D - p_MA) / ω_nd²
    KAPPA  = 1 / (t_nd · L_s_nd)

with every factor fixed by the configuration and the mesh:

``t_nd``
    ``t_config / (Lc/L0)`` (``iodata.cpp:535``).
``L_s_nd``
    ``L_nd · (w/l) · n_elements`` (``lumpedportoperator.cpp:578``,
    ``lumpedportoperator.hpp:57-60``), with ``L_nd = L_SI/(μ₀·Lc)``
    (``iodata.cpp:512``), and ``l`` the port bounding-box extent most aligned
    with the declared direction, ``w`` the largest remaining extent
    (``fem/lumpedelement.cpp:53-69``).
``ω_nd``
    ``2π · f_GHz · tc``, ``tc = 1e9·Lc/c₀`` ns (``iodata.cpp:465, 539``).
``Lc``
    the largest axis-aligned mesh bounding-box extent, in metres
    (``iodata.cpp:452-464``) — measured from the mesh, not read from the log.

Note that ``E_elec + E_cap`` cancels: the conversion never touches an energy
column. That is what makes ``p_port`` independent of the balance it is used to
test.

What this can and cannot establish
----------------------------------

``p_port`` uses ``surface-Q.csv``, ``eig.csv`` and geometry. ``p_closure :=
1 - (E_mag+E_cap)/(E_elec+E_cap)`` uses ``domain-E.csv``. They share no input,
so agreement between them is evidence. ``p_closure`` on its own is **not** an
independent measurement of the port energy: it is what the port term *must* be
for the balance to close, so quoting it as a verification of that balance
would be circular. :func:`compare` labels it accordingly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

#: Palace's own electromagnetic constants (``utils/constants.hpp:17-38``).
MU0 = 4.0e-7 * math.pi
EPSILON0 = 8.8541878176e-12
C0 = 1.0 / math.sqrt(EPSILON0 * MU0)

#: Every factor of the conversion, with the pinned-source line that fixes it.
#: The tree is Palace v0.13.0 at commit a61c8cbe0cacf496cde3c62e93085fae0d6299ac.
PALACE_SOURCE_CITATIONS: dict[str, str] = {
    "port_enters_K_as_a_boundary_mass_term": (
        "palace/models/lumpedportoperator.cpp:571-591 assembles the inductive port face "
        "with coefficient 1/Ls; palace/models/spaceoperator.cpp:300-307 puts it in the "
        "stiffness matrix and :236-238 makes it a VectorFEMassIntegrator, i.e. "
        "INT_Gamma (1/Ls) |E_t|^2 dS"
    ),
    "Ls_definition": (
        "palace/models/lumpedportoperator.cpp:578 Ls = L * GetToSquare(elem); "
        "palace/models/lumpedportoperator.hpp:57-60 GetToSquare = (w/l) * elems.size()"
    ),
    "l_and_w_definition": (
        "palace/fem/lumpedelement.cpp:53-69: l is the port bounding-box extent most "
        "aligned with the declared direction, w the largest remaining extent"
    ),
    "L_nondimensionalisation": "palace/utils/iodata.cpp:512 data.L /= mu0_ * Lc",
    "t_nondimensionalisation": "palace/utils/iodata.cpp:535 data.t /= Lc / model.L0",
    "Lc_definition": (
        "palace/utils/iodata.cpp:452-464: Model.Lc if given, else the largest "
        "axis-aligned mesh bounding-box extent, in metres"
    ),
    "tc_definition": "palace/utils/iodata.cpp:465 tc = 1.0e9 * Lc / c0_ [ns]",
    "omega_nondimensionalisation": (
        "palace/utils/iodata.cpp:539 and :575 - frequencies carry 1/(2 pi tc), so "
        "omega_nd = 2 pi f_GHz tc"
    ),
    "probe_default": "palace/fem/coefficient.hpp:373-391 gives 0.5 * t * eps * |E|^2",
    "probe_ma": "palace/fem/coefficient.hpp:393-413 gives 0.5 * (t/eps) * |E_n|^2",
    "probe_side_rule": (
        "palace/fem/coefficient.hpp:330-360 GetLocalVectorValue - the same side rule for "
        "both probe types, so the choice cancels in their difference"
    ),
    "probe_integration": (
        "palace/models/surfacepostoperator.cpp:287-301 integrates the coefficient with "
        "BoundaryLFIntegrator against H1, whose basis is a partition of unity, so the "
        "sum of the linear form is the plain surface integral"
    ),
    "probe_normalisation": (
        "palace/models/postoperator.cpp:419-427 divides by E_m; "
        "palace/drivers/basesolver.cpp:538-540 passes the argument named E_elec; "
        "palace/drivers/eigensolver.cpp:349 supplies E_elec + E_cap"
    ),
    "E_ind_is_rank_one": (
        "palace/models/lumpedportoperator.cpp:200-213 V = 1/w INT E.l_hat dS; "
        "palace/models/postoperator.cpp:493-508 E_ind = 0.5 |L| |I|^2 with I = V/(i w L)"
    ),
    "energy_scale_is_1e9_times_SI": (
        "palace/utils/iodata.cpp:565-602: the ENERGY scale factor is Hc^2 Z0 Lc^2 tc "
        "with Hc^2 Z0 Lc^2 = 1 W by construction and tc in NANOseconds, so the columns "
        "headed (J) in domain-E.csv carry 1e9 x SI joules"
    ),
    "B_carries_one_over_omega": (
        "palace/drivers/eigensolver.cpp:310-315 B = -1/(i omega) curl E, so E_mag "
        "carries 1/omega^2, exactly as E_port does"
    ),
}

#: Assumptions the derivation makes that the saved evidence does not pin down.
#: Reported with every result rather than left implicit.
UNVERIFIED_ASSUMPTIONS: tuple[dict[str, str], ...] = (
    {
        "assumption": "quadrature",
        "statement": (
            "the probes are integrated by BoundaryLFIntegrator against H1 while the "
            "stiffness term is integrated by a libCEED VectorFEMassIntegrator; the two "
            "need not use the same quadrature rule"
        ),
        "why_it_is_believed_harmless": (
            "both integrands are degree-2 polynomials per face for order-1 Nedelec on "
            "affine tetrahedra, which either rule integrates exactly"
        ),
        "what_would_settle_it": (
            "a Palace build instrumented to print INT_Gamma (1/Ls)|E_t|^2 dS directly; "
            "not available from the saved outputs"
        ),
    },
    {
        "assumption": "single port element",
        "statement": "elems.size() == 1, so GetToSquare is w/l with no multiplicity",
        "why_it_is_believed_harmless": (
            "the configuration declares LumpedPort[0].Attributes = [10], one attribute "
            "and one coplanar rectangle, which builds exactly one UniformElementData"
        ),
        "what_would_settle_it": "already settled by the committed config.json",
    },
    {
        "assumption": "tangential trace",
        "statement": (
            "the boundary VectorFEMassIntegrator on a Nedelec space sees the tangential "
            "trace, so the assembled term is INT |E_t|^2 dS and not INT |E|^2 dS"
        ),
        "why_it_is_believed_harmless": (
            "it is the defining property of the H(curl)-conforming trace, and the "
            "measured agreement with the closure defect would not survive otherwise"
        ),
        "what_would_settle_it": "the measured agreement, which is reported per mode",
    },
)


@dataclass(frozen=True)
class PortGeometry:
    """The declared lumped-port face, in mesh length units."""

    length_mm: float
    """Extent along the declared port direction: Palace's ``l``."""
    width_mm: float
    """Largest remaining in-plane extent: Palace's ``w``."""
    n_elements: int = 1
    direction: str = "+Y"

    def __post_init__(self) -> None:
        if not (self.length_mm > 0.0 and self.width_mm > 0.0):
            raise ValueError("port length and width must be positive")
        if self.n_elements < 1:
            raise ValueError("a lumped port has at least one element")

    @property
    def area_mm2(self) -> float:
        return self.length_mm * self.width_mm * self.n_elements

    @property
    def to_square(self) -> float:
        """Palace's ``GetToSquare``: ``(w/l) * elems.size()``."""
        return self.width_mm / self.length_mm * self.n_elements


@dataclass(frozen=True)
class NonDimensionalisation:
    """Palace's characteristic scales for a run."""

    Lc_m: float
    """Characteristic length in metres: the largest mesh bounding-box extent."""
    L0_m: float
    """``Model.L0``: metres per mesh length unit."""

    def __post_init__(self) -> None:
        if not (self.Lc_m > 0.0 and self.L0_m > 0.0):
            raise ValueError("Lc and L0 must be positive")

    @property
    def length_scale(self) -> float:
        """``Lc / L0``: mesh length units per characteristic length."""
        return self.Lc_m / self.L0_m

    @property
    def tc_ns(self) -> float:
        return 1.0e9 * self.Lc_m / C0

    def omega(self, frequency_GHz: float) -> float:
        """Palace's nondimensional angular frequency."""
        return 2.0 * math.pi * frequency_GHz * self.tc_ns

    def inductance(self, L_henry: float) -> float:
        return L_henry / (MU0 * self.Lc_m)

    def thickness(self, t_mesh_units: float) -> float:
        return t_mesh_units / self.length_scale


@dataclass(frozen=True)
class PortConversion:
    """The derived ``surface-Q`` to port-stiffness-energy conversion.

    ``kappa`` is computed, never fitted: see the module docstring.
    """

    geometry: PortGeometry
    scales: NonDimensionalisation
    inductance_H: float
    probe_thickness_mesh_units: float
    probe_permittivity: float

    def __post_init__(self) -> None:
        if self.probe_permittivity != 1.0:
            raise ValueError(
                "the Default minus MA reduction to |E_t|^2 needs equal probe permittivity "
                f"of 1, got {self.probe_permittivity}: Default carries t*eps and MA t/eps"
            )

    @property
    def inductance_nd(self) -> float:
        return self.scales.inductance(self.inductance_H)

    @property
    def sheet_inductance_nd(self) -> float:
        """Palace's ``Ls = L * GetToSquare(elem)``."""
        return self.inductance_nd * self.geometry.to_square

    @property
    def probe_thickness_nd(self) -> float:
        return self.scales.thickness(self.probe_thickness_mesh_units)

    @property
    def kappa(self) -> float:
        """``1 / (t_nd * Ls_nd)``. Dimensionless; fixed by geometry and units."""
        return 1.0 / (self.probe_thickness_nd * self.sheet_inductance_nd)

    def tangential_integral(self, p_default: float, p_ma: float) -> float:
        """``INT_Gamma |E_t|^2 dS / (E_elec + E_cap)``, nondimensional.

        The denominator is Palace's own normalisation of ``p_surf``; it is not
        introduced here and it cancels in :meth:`port_participation`.
        """
        return 2.0 * (p_default - p_ma) / self.probe_thickness_nd

    def port_participation(self, p_default: float, p_ma: float, frequency_GHz: float) -> float:
        """``E_port / (E_elec + E_cap)``, from the probes alone."""
        omega = self.scales.omega(frequency_GHz)
        if omega == 0.0:
            raise ValueError("port participation is undefined at zero frequency")
        return self.kappa * (p_default - p_ma) / (omega * omega)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kappa": self.kappa,
            "kappa_definition": "1 / (t_nd * Ls_nd); derived, not fitted",
            "factors": {
                "Lc_m": self.scales.Lc_m,
                "L0_m": self.scales.L0_m,
                "length_scale_Lc_over_L0": self.scales.length_scale,
                "tc_ns": self.scales.tc_ns,
                "inductance_H": self.inductance_H,
                "inductance_nd": self.inductance_nd,
                "port_length_mm": self.geometry.length_mm,
                "port_width_mm": self.geometry.width_mm,
                "port_area_mm2": self.geometry.area_mm2,
                "port_n_elements": self.geometry.n_elements,
                "to_square_w_over_l": self.geometry.to_square,
                "sheet_inductance_nd": self.sheet_inductance_nd,
                "probe_thickness_mesh_units": self.probe_thickness_mesh_units,
                "probe_thickness_nd": self.probe_thickness_nd,
                "probe_permittivity": self.probe_permittivity,
            },
            "source": dict(PALACE_SOURCE_CITATIONS),
            "unverified_assumptions": [dict(a) for a in UNVERIFIED_ASSUMPTIONS],
        }


@dataclass(frozen=True)
class ModeComparison:
    """The three port numbers for one mode, and what each of them is worth."""

    mode: int
    frequency_GHz: float
    participation_from_probes: float
    """Independent: ``surface-Q.csv`` + frequency + geometry. No energy column."""
    participation_reported: float
    """Palace's own ``E_ind/(E_elec+E_cap)``, the rank-one averaged-voltage surrogate."""
    participation_from_closure: float
    """NOT independent: what the port term must be for the balance to close."""
    tangential_integral: float
    """``INT |E_t|^2 dS / (E_elec+E_cap)``, nondimensional."""

    @property
    def probe_versus_closure(self) -> float:
        """Agreement of the independent evaluation with the closure requirement."""
        if self.participation_from_closure == 0.0:
            return math.inf
        return self.participation_from_probes / self.participation_from_closure

    @property
    def uniformity_factor(self) -> float:
        """``E_ind / E_port = |INT E.d_hat dS|^2 / (A INT |E_t|^2 dS)``.

        Cauchy-Schwarz bounds this by 1, with equality exactly when the port
        face's tangential field is uniform and aligned with the declared
        direction. It is therefore a direct measure of how far the port field
        is from the one configuration the ``E_ind`` surrogate represents, and
        it is one-sided: the surrogate can only understate the port energy.
        """
        if self.participation_from_probes == 0.0:
            return math.inf
        return abs(self.participation_reported) / self.participation_from_probes

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "frequency_GHz": self.frequency_GHz,
            "participation": {
                "from_probes": self.participation_from_probes,
                "reported_E_ind": self.participation_reported,
                "from_closure": self.participation_from_closure,
            },
            "independence": {
                "from_probes": (
                    "independent of the energy balance: surface-Q.csv, eig.csv and "
                    "geometry only"
                ),
                "reported_E_ind": "Palace's rank-one averaged-voltage surrogate",
                "from_closure": (
                    "NOT independent: this is what the port term must be for the balance "
                    "to close, so it cannot verify that balance"
                ),
            },
            "probe_over_closure": self.probe_versus_closure,
            "uniformity_factor_E_ind_over_E_port": self.uniformity_factor,
            "tangential_integral_over_E_elec_plus_E_cap": self.tangential_integral,
        }


def compare(
    conversion: PortConversion,
    *,
    mode: int,
    frequency_GHz: float,
    p_default: float,
    p_ma: float,
    E_elec: float,
    E_mag: float,
    E_cap: float,
    E_ind: float,
) -> ModeComparison:
    """The three-way comparison for one mode.

    ``E_*`` may be given in any consistent units: only ratios are formed, so
    the 1e9 factor Palace's ``(J)`` columns carry cancels.
    """
    denominator = E_elec + E_cap
    if denominator == 0.0:
        raise ValueError("E_elec + E_cap is zero; participations are undefined")
    return ModeComparison(
        mode=mode,
        frequency_GHz=frequency_GHz,
        participation_from_probes=conversion.port_participation(p_default, p_ma, frequency_GHz),
        participation_reported=E_ind / denominator,
        participation_from_closure=1.0 - (E_mag + E_cap) / denominator,
        tangential_integral=conversion.tangential_integral(p_default, p_ma),
    )


class PortConversionError(RuntimeError):
    """The run's own configuration does not support the derived conversion."""


def conversion_from_run(config: dict[str, Any], mesh_report: dict[str, Any]) -> PortConversion:
    """Derive the conversion for one solve, from its own config and its own mesh.

    Shared by every driver that reports the diagnostic, so the ladder run and
    the recovery analysis cannot drift apart on how ``kappa`` is formed.

    ``Lc`` is measured from the mesh bounding box rather than read from
    Palace's log, which prints it to four significant figures. ``l`` is the
    extent along the declared port direction and ``w`` the remaining in-plane
    extent, matching ``fem/lumpedelement.cpp:53-69``.

    ``mesh_report`` is a :func:`solvers.palace.mesh_inspection.inspect_mesh`
    result; only ``largest_extent_mm`` and the port face's bounding box are used.
    """
    try:
        port = config["Boundaries"]["LumpedPort"][0]
        probes = config["Boundaries"]["Postprocessing"]["Dielectric"]
        L0_m = float(config["Model"]["L0"])
    except (KeyError, IndexError, TypeError) as exc:
        raise PortConversionError(f"the configuration has no lumped port with probes: {exc}") from exc

    thicknesses = {p["Thickness"] for p in probes}
    permittivities = {p["Permittivity"] for p in probes}
    sides = {p["Side"] for p in probes}
    if len(thicknesses) != 1 or len(permittivities) != 1 or len(sides) != 1:
        raise PortConversionError(
            "the Default and MA probes must share thickness, permittivity and side for their "
            f"difference to be 0.5 t |E_t|^2; got {thicknesses}, {permittivities}, {sides}"
        )

    direction = str(port["Direction"])
    if direction not in ("+Y", "-Y"):
        raise PortConversionError(
            f"the port direction is {direction}; this conversion measures the face assuming "
            "a +/-Y direction and refuses rather than guessing which extent is the length"
        )

    face = mesh_report["ports"]["port_F1"]
    box = face["bounding_box_mm"]
    length_mm = box["max"][1] - box["min"][1]
    width_mm = box["max"][0] - box["min"][0]

    return PortConversion(
        geometry=PortGeometry(
            length_mm=length_mm,
            width_mm=width_mm,
            n_elements=len(port["Attributes"]),
            direction=direction,
        ),
        scales=NonDimensionalisation(
            Lc_m=mesh_report["largest_extent_mm"] * L0_m,
            L0_m=L0_m,
        ),
        inductance_H=float(port["L"]),
        probe_thickness_mesh_units=float(next(iter(thicknesses))),
        probe_permittivity=float(next(iter(permittivities))),
    )


# --------------------------------------------------------------------------
# Synthetic port fields: the formula is tested against fields whose integrals
# are known in closed form, so a test failure is a fault in the conversion and
# not a disagreement with a solve.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SyntheticPortField:
    """A field on the port rectangle, evaluated the way Palace's probes do.

    ``field(u, v)`` takes coordinates in mesh length units measured from the
    face centre — ``u`` across the width, ``v`` along the port direction — and
    returns ``(E_along, E_across, E_normal)``: the component along the declared
    direction, the in-plane component perpendicular to it, and the component
    out of the face. Everything else is quadrature.
    """

    geometry: PortGeometry
    scales: NonDimensionalisation
    field: Any
    quadrature: int = 400

    def _integrate(self, integrand: Any) -> float:
        """Midpoint rule over the face, in mesh length units squared."""
        n = self.quadrature
        du = self.geometry.width_mm / n
        dv = self.geometry.length_mm / n
        total = 0.0
        for i in range(n):
            u = -0.5 * self.geometry.width_mm + (i + 0.5) * du
            for j in range(n):
                v = -0.5 * self.geometry.length_mm + (j + 0.5) * dv
                total += integrand(u, v)
        return total * du * dv * self.geometry.n_elements

    def probe_integrals(self, thickness_mesh_units: float) -> tuple[float, float]:
        """``(INT 0.5 t eps |E|^2 dS, INT 0.5 t/eps |E_n|^2 dS)``, nondimensional.

        Lengths are converted to Palace's nondimensional units, which is where
        the conversion constant lives.
        """
        t_nd = self.scales.thickness(thickness_mesh_units)
        scale = self.scales.length_scale ** 2  # mm^2 -> nondimensional area

        def full(u: float, v: float) -> float:
            a, b, c = self.field(u, v)
            return 0.5 * (a * a + b * b + c * c)

        def normal(u: float, v: float) -> float:
            _, _, c = self.field(u, v)
            return 0.5 * c * c

        return (t_nd * self._integrate(full) / scale, t_nd * self._integrate(normal) / scale)

    def tangential_integral(self) -> float:
        """``INT_Gamma |E_t|^2 dS``, nondimensional."""

        def tangential(u: float, v: float) -> float:
            a, b, _ = self.field(u, v)
            return a * a + b * b

        return self._integrate(tangential) / self.scales.length_scale ** 2

    def averaged_voltage(self) -> float:
        """Palace's ``V = 1/(w n) INT E.l_hat dS``, nondimensional."""
        integral = self._integrate(lambda u, v: self.field(u, v)[0])
        width_nd = self.geometry.width_mm / self.scales.length_scale
        area_scale = self.scales.length_scale ** 2
        return integral / area_scale / (width_nd * self.geometry.n_elements)

    def port_stiffness_energy(self, conversion: PortConversion, frequency_GHz: float) -> float:
        """``E_port`` evaluated directly from its definition, nondimensional."""
        omega = self.scales.omega(frequency_GHz)
        return self.tangential_integral() / (2.0 * omega * omega * conversion.sheet_inductance_nd)

    def inductor_energy(self, conversion: PortConversion, frequency_GHz: float) -> float:
        """Palace's ``E_ind = |V|^2/(2 omega^2 L)``, nondimensional."""
        omega = self.scales.omega(frequency_GHz)
        voltage = self.averaged_voltage()
        return voltage * voltage / (2.0 * omega * omega * conversion.inductance_nd)


def uniform_aligned_field(amplitude: float = 1.0) -> Any:
    """``E = amplitude * d_hat``: the one field ``E_ind`` represents exactly."""
    return lambda u, v: (amplitude, 0.0, 0.0)


def cosine_modulated_field(width_mm: float, amplitude: float = 1.0, contrast: float = 0.5) -> Any:
    """``E_along = amplitude (1 + contrast cos(2 pi u / w))``, zero-mean modulation.

    One full period across the width, so the modulation integrates to zero and
    ``V`` is exactly the uniform field's, while ``INT |E_t|^2 dS`` grows by
    ``1 + contrast^2/2``. Deliberately non-uniform, with a closed-form answer:
    the uniformity factor is ``1/(1 + contrast^2/2)``.
    """

    def f(u: float, v: float) -> tuple[float, float, float]:
        return (amplitude * (1.0 + contrast * math.cos(2.0 * math.pi * u / width_mm)), 0.0, 0.0)

    return f


def transverse_field(along: float = 1.0, across: float = 1.0) -> Any:
    """Uniform, but with a component perpendicular to the declared direction.

    ``V`` sees only ``along``; the stiffness term sees both. The uniformity
    factor is ``along^2/(along^2 + across^2)``.
    """
    return lambda u, v: (along, across, 0.0)


def with_normal_component(base: Any, normal: float) -> Any:
    """``base`` plus a uniform out-of-face component.

    The MA probe subtracts it exactly, so nothing the conversion computes may
    move. A regression guard on the ``Default - MA`` reduction.
    """

    def f(u: float, v: float) -> tuple[float, float, float]:
        a, b, _ = base(u, v)
        return (a, b, normal)

    return f


__all__ = [
    "C0",
    "EPSILON0",
    "MU0",
    "PALACE_SOURCE_CITATIONS",
    "UNVERIFIED_ASSUMPTIONS",
    "ModeComparison",
    "NonDimensionalisation",
    "PortConversionError",
    "PortConversion",
    "PortGeometry",
    "SyntheticPortField",
    "compare",
    "conversion_from_run",
    "cosine_modulated_field",
    "transverse_field",
    "uniform_aligned_field",
    "with_normal_component",
]
