"""Static fluxonium model (spec §5.1).

Verified finite-difference Hamiltonian on the frozen 3201-point phase grid over
[-8*pi, +8*pi] with a second-difference kinetic operator::

    H = -4 E_C d²/dφ² + ½ E_L φ² - E_J cos(φ - φ_ext)

The tridiagonal form is solved with ``scipy.linalg.eigh_tridiagonal``:

    diagonal    = 8 E_C / h²  +  ½ E_L φ²  -  E_J cos(φ - φ_ext)
    off-diagonal = -4 E_C / h²

Charge matrix elements are taken from the derivative overlap
``n_ij = -i <i|d/dφ|j>``, evaluated with ``numpy.gradient`` on the same grid.

The implementation follows ``reference/v1_5_8f_release_bundle/
qmhp_v158f_readout_replication.py`` — the third independent implementation
shipped with the frozen release — and is regression-tested against spec §4.2.
It is a reimplementation against the frozen conventions, not a wrapper: the
vendored script is never executed.

Convention note: the ``sin(delta/2)`` matrix element uses
``delta = phi - phi_ext``. With the frozen ``phi_ext = pi`` this reproduces the
frozen 0.295705232 exactly; using ``sin(phi/2)`` instead gives identically zero
by parity, so the convention is load-bearing rather than cosmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy.linalg import eigh_tridiagonal

from contracts import master

#: Default number of eigenlevels retained.
DEFAULT_LEVELS = 10


@dataclass(frozen=True)
class StaticSpectrum:
    """Static fluxonium solution on the frozen grid."""

    #: Eigenfrequencies in GHz, relative to the ground state (f_0 = 0).
    frequencies_GHz: np.ndarray
    #: Charge matrix elements n_ij = -i <i|d/dphi|j>.
    charge_matrix: np.ndarray
    #: Phase grid used, in radians.
    phase_grid: np.ndarray
    #: Eigenvectors on the phase grid, column i is state i.
    eigenvectors: np.ndarray

    def f(self, upper: int, lower: int = 0) -> float:
        """Transition frequency f_{upper,lower} in GHz."""
        return float(self.frequencies_GHz[upper] - self.frequencies_GHz[lower])

    def n(self, i: int, j: int) -> float:
        """|n_ij|, the magnitude of the charge matrix element."""
        return float(abs(self.charge_matrix[i, j]))

    def sin_delta_over_2(self, i: int, j: int, phi_ext: float | None = None) -> float:
        """|<i| sin((phi - phi_ext)/2) |j>|.

        Used by the quasiparticle-bypass rate. The offset by ``phi_ext`` is
        required: without it the 0-2 element vanishes by parity.
        """
        if phi_ext is None:
            phi_ext = master.get("branch_a_device.phi_ext")
        operator = np.sin((self.phase_grid - phi_ext) / 2.0)
        return float(
            abs(np.sum(self.eigenvectors[:, i] * operator * self.eigenvectors[:, j]))
        )


def phase_grid_convention() -> dict[str, object]:
    """The frozen phase-grid convention (spec §4.2)."""
    grid = master.get("static_fluxonium.phase_grid")
    return {
        "grid_points": grid["grid_points"],
        "phase_min": grid["phase_min"],
        "phase_max": grid["phase_max"],
        "kinetic_operator": grid["kinetic_operator"],
    }


def reference_values() -> dict[str, object]:
    """Frozen §4.2 reference values the implementation must reproduce."""
    return dict(master.get("static_fluxonium.reference_values"))


def nominal_parameters() -> tuple[float, float, float, float]:
    """Frozen Branch-A nominal (EC, EJ, EL, phi_ext)."""
    device = master.get("branch_a_device")
    return (
        device["EC_over_h_GHz"],
        device["EJ_over_h_GHz"],
        device["EL_over_h_GHz"],
        device["phi_ext"],
    )


def solve_static(
    EC_GHz: float | None = None,
    EJ_GHz: float | None = None,
    EL_GHz: float | None = None,
    phi_ext: float | None = None,
    levels: int = DEFAULT_LEVELS,
) -> StaticSpectrum:
    """Solve the static fluxonium spectrum on the frozen grid.

    Args:
        EC_GHz, EJ_GHz, EL_GHz: Device energies in GHz. Default to the frozen
            Branch-A nominal values.
        phi_ext: External flux phase. Defaults to the frozen ``pi``.
        levels: Number of eigenlevels to retain.

    Returns:
        The :class:`StaticSpectrum`.
    """
    nominal_EC, nominal_EJ, nominal_EL, nominal_phi = nominal_parameters()
    EC = nominal_EC if EC_GHz is None else EC_GHz
    EJ = nominal_EJ if EJ_GHz is None else EJ_GHz
    EL = nominal_EL if EL_GHz is None else EL_GHz
    phi = nominal_phi if phi_ext is None else phi_ext

    grid = phase_grid_convention()
    n_points = int(grid["grid_points"])
    x = np.linspace(float(grid["phase_min"]), float(grid["phase_max"]), n_points)
    h = x[1] - x[0]

    diagonal = 8.0 * EC / h**2 + 0.5 * EL * x**2 - EJ * np.cos(x - phi)
    off_diagonal = np.full(n_points - 1, -4.0 * EC / h**2)

    energies, vectors = eigh_tridiagonal(
        diagonal, off_diagonal, select="i", select_range=(0, levels - 1)
    )

    derivative = np.gradient(vectors, h, axis=0)
    overlap = np.array(
        [
            [np.sum(vectors[:, i] * derivative[:, j]) for j in range(levels)]
            for i in range(levels)
        ]
    )

    return StaticSpectrum(
        frequencies_GHz=energies - energies[0],
        charge_matrix=-1j * overlap,
        phase_grid=x,
        eigenvectors=vectors,
    )


@lru_cache(maxsize=8)
def nominal_spectrum(levels: int = DEFAULT_LEVELS) -> StaticSpectrum:
    """The frozen Branch-A nominal spectrum, cached.

    The solve costs order 100 ms and every dressed-system root evaluation needs
    it, so caching the nominal case keeps sweeps tractable.
    """
    return solve_static(levels=levels)
