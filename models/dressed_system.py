"""Coupled dressed-system model (spec §5.2).

Hamiltonian, in the frozen convention::

    H = diag(w_i) + w_r a†a + g n (a + a†)

built on the truncated product space of ``Nq`` fluxonium levels and ``Nph``
resonator photon numbers, complex-Hermitian. Dressed states are labelled
adiabatically by maximum bare overlap. The logical-blind condition — equal
dispersive pull on the two logical states |0> and |2> — is solved with
``scipy.optimize.brentq``, seeded from the Eq.(7) perturbative estimate.

Eq.(7) is a DIAGNOSTIC only (spec §4.3). It seeds the bracket; the exact
dressed root is authoritative for the operating point.

Production truncation is (Nq, Nph) = (10, 12). The (14, 25) spot check shifts
the root by approximately +0.92 kHz, which is expected and is NOT an error
condition (spec §4.4).

Implemented against ``reference/v1_5_8f_release_bundle/
qmhp_v158f_readout_replication.py`` and regression-tested against spec §4.4.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import numpy.linalg as la
from scipy.optimize import brentq

from contracts import master
from models.fluxonium import DEFAULT_LEVELS, StaticSpectrum, nominal_spectrum, solve_static

#: Production truncation (spec §4.4).
PRODUCTION_NQ = 10
PRODUCTION_NPH = 12

#: High-truncation spot check (spec §4.4).
SPOT_CHECK_NQ = 14
SPOT_CHECK_NPH = 25

#: Fluxonium-resonator coupling in GHz.
#:
#: Classification: VERIFIED-COMPUTATIONAL. The consolidated Master does not
#: print g; it is carried by the release's readout replication script
#: (``g = 0.150``) and is required to reproduce the frozen dressed root.
COUPLING_G_GHz = 0.150

#: Default bracket for the logical-blind root search, in GHz.
#:
#: Matches the reference implementation's default. It is deliberately wider
#: than the nominal ladder bracket: perturbed ensemble devices move the root,
#: and a bracket sized for the nominal device fails to contain them.
DEFAULT_BRACKET = (4.05, 4.55)

#: Narrow bracket used for the nominal truncation ladder, matching the
#: reference implementation's explicit ladder call.
NOMINAL_BRACKET = (4.20, 4.40)

#: Which fluxonium levels are the logical pair and the sink.
LOGICAL_STATES = (0, 2)
SINK_STATE = 1


class RootNotBracketed(RuntimeError):
    """The logical-blind root does not lie inside the search bracket.

    Raised rather than silently widening the bracket. A device whose root
    escapes the declared bracket has not been screened, and must be reported
    as unscreened rather than counted as either a pass or a rejection.
    """

    def __init__(self, bracket: tuple[float, float], low: float, high: float) -> None:
        self.bracket = bracket
        super().__init__(
            f"logical-blind condition does not change sign across "
            f"[{bracket[0]}, {bracket[1]}] GHz "
            f"(endpoints {low:+.4f}, {high:+.4f} MHz); the root is outside the "
            f"declared bracket and this device is unscreened."
        )


@dataclass(frozen=True)
class DressedSolution:
    """Dressed-system solution at a given readout frequency."""

    readout_GHz: float
    #: Dispersive pulls in MHz, indexed by bare fluxonium level (0, 1, 2).
    pulls_MHz: np.ndarray
    #: Eigenvalues of the full coupled Hamiltonian.
    eigenvalues: np.ndarray
    #: Eigenvectors of the full coupled Hamiltonian.
    eigenvectors: np.ndarray
    #: Map (level, photon) -> (energy, eigenindex) from adiabatic labelling.
    labels: dict[tuple[int, int], tuple[float, int]]
    Nq: int
    Nph: int

    @property
    def logical_pull_MHz(self) -> float:
        return float(self.pulls_MHz[LOGICAL_STATES[0]])

    @property
    def sink_pull_MHz(self) -> float:
        return float(self.pulls_MHz[SINK_STATE])

    @property
    def sink_logical_contrast_MHz(self) -> float:
        """Separation between the sink and logical dispersive lines."""
        return float(self.pulls_MHz[SINK_STATE] - self.pulls_MHz[LOGICAL_STATES[0]])

    @property
    def sink_line_GHz(self) -> float:
        return float(self.readout_GHz + self.sink_pull_MHz / 1e3)

    @property
    def dressed_f12_GHz(self) -> float:
        """Dressed |1> -> |2> emission frequency — the Purcell filter target."""
        return float(
            self.eigenvalues[self.labels[(2, 0)][1]]
            - self.eigenvalues[self.labels[(1, 0)][1]]
        )

    def purcell_weight(self) -> float:
        """|<dressed(1,0)| a |dressed(2,0)>|², the F8 weight (spec §5.3)."""
        annihilation = np.kron(
            np.eye(self.Nq), np.diag(np.sqrt(np.arange(1, self.Nph)), 1)
        )
        element = abs(
            self.eigenvectors[:, self.labels[(1, 0)][1]].conj()
            @ annihilation
            @ self.eigenvectors[:, self.labels[(2, 0)][1]]
        )
        return float(element * element)


def eq7_seed() -> dict[str, object]:
    """Frozen Eq.(7) dispersive diagnostic (spec §4.3). Seeds the search only."""
    return dict(master.get("eq7_diagnostic"))


def regression_pins() -> dict[str, float]:
    """Frozen §4.4 dressed-system pins."""
    system = master.get("dressed_system")
    return {
        "root_10_12_GHz": system["production_convention"]["root_GHz"],
        "root_14_25_GHz": system["high_truncation_spot_check"]["root_GHz"],
        "sink_line_GHz": system["physical_pull_references"]["sink_line_GHz"],
        "dressed_f12_GHz": system["physical_pull_references"]["dressed_f12_GHz"],
        "sink_logical_contrast_MHz": system["physical_pull_references"][
            "sink_logical_contrast_MHz"
        ],
    }


def solve_dressed(
    readout_GHz: float,
    spectrum: StaticSpectrum | None = None,
    Nq: int = PRODUCTION_NQ,
    Nph: int = PRODUCTION_NPH,
    g_GHz: float = COUPLING_G_GHz,
) -> DressedSolution:
    """Diagonalise the coupled system at a given readout frequency."""
    if spectrum is None:
        spectrum = nominal_spectrum(levels=max(Nq, DEFAULT_LEVELS))

    frequencies = spectrum.frequencies_GHz
    charge = spectrum.charge_matrix

    photon_annihilation = np.diag(np.sqrt(np.arange(1, Nph)), 1)
    photon_x = photon_annihilation + photon_annihilation.T

    dimension = Nq * Nph
    H = np.zeros((dimension, dimension), dtype=complex)

    for level in range(Nq):
        for photon in range(Nph):
            index = level * Nph + photon
            H[index, index] = frequencies[level] + readout_GHz * photon

    for i in range(Nq):
        for j in range(Nq):
            if abs(charge[i, j]) < 1e-14:
                continue
            H[i * Nph : (i + 1) * Nph, j * Nph : (j + 1) * Nph] += (
                g_GHz * charge[i, j] * photon_x
            )

    eigenvalues, eigenvectors = la.eigh(H)
    overlap = np.abs(eigenvectors) ** 2

    labels: dict[tuple[int, int], tuple[float, int]] = {}
    for level in (0, 1, 2):
        for photon in (0, 1):
            index = int(np.argmax(overlap[level * Nph + photon, :]))
            labels[(level, photon)] = (float(eigenvalues[index]), index)

    pulls = (
        np.array(
            [
                labels[(level, 1)][0] - labels[(level, 0)][0] - readout_GHz
                for level in range(3)
            ]
        )
        * 1e3
    )

    return DressedSolution(
        readout_GHz=readout_GHz,
        pulls_MHz=pulls,
        eigenvalues=eigenvalues,
        eigenvectors=eigenvectors,
        labels=labels,
        Nq=Nq,
        Nph=Nph,
    )


def solve_dressed_root(
    Nq: int = PRODUCTION_NQ,
    Nph: int = PRODUCTION_NPH,
    spectrum: StaticSpectrum | None = None,
    bracket: tuple[float, float] = DEFAULT_BRACKET,
    xtol: float = 1e-10,
) -> float:
    """Solve the logical-blind dressed root in GHz.

    The logical-blind condition is equal dispersive pull on the two logical
    states: ``pull(|0>) - pull(|2>) = 0``.
    """
    if spectrum is None:
        spectrum = nominal_spectrum(levels=max(Nq, DEFAULT_LEVELS))

    def blindness(readout_GHz: float) -> float:
        pulls = solve_dressed(readout_GHz, spectrum, Nq, Nph).pulls_MHz
        return pulls[LOGICAL_STATES[0]] - pulls[LOGICAL_STATES[1]]

    low, high = blindness(bracket[0]), blindness(bracket[1])
    if np.sign(low) == np.sign(high):
        raise RootNotBracketed(bracket, low, high)

    return float(brentq(blindness, bracket[0], bracket[1], xtol=xtol))


@lru_cache(maxsize=4)
def nominal_root(Nq: int = PRODUCTION_NQ, Nph: int = PRODUCTION_NPH) -> float:
    """The frozen Branch-A nominal dressed root, cached."""
    return solve_dressed_root(Nq, Nph, bracket=NOMINAL_BRACKET)


@lru_cache(maxsize=4)
def nominal_solution(
    Nq: int = PRODUCTION_NQ, Nph: int = PRODUCTION_NPH
) -> DressedSolution:
    """The dressed solution at the nominal root, cached."""
    return solve_dressed(nominal_root(Nq, Nph), None, Nq, Nph)


def dressed_spectrum(
    Nq: int = PRODUCTION_NQ, Nph: int = PRODUCTION_NPH
) -> dict[str, float]:
    """Dressed observables at the nominal operating point.

    Supplies ``omega24`` for the COLLISION gate and ``dressed_f12_GHz`` for the
    P6E2_FILTER gate.
    """
    solution = nominal_solution(Nq, Nph)
    spectrum = nominal_spectrum(levels=max(Nq, DEFAULT_LEVELS))
    return {
        "root_GHz": solution.readout_GHz,
        "logical_pull_MHz": solution.logical_pull_MHz,
        "sink_pull_MHz": solution.sink_pull_MHz,
        "sink_logical_contrast_MHz": solution.sink_logical_contrast_MHz,
        "sink_line_GHz": solution.sink_line_GHz,
        "dressed_f12_GHz": solution.dressed_f12_GHz,
        "purcell_weight": solution.purcell_weight(),
        "omega24_GHz": spectrum.f(4, 2),
        "Nq": Nq,
        "Nph": Nph,
        "coupling_g_GHz": COUPLING_G_GHz,
    }
