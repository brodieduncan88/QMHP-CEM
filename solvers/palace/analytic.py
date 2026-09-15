"""Closed-form eigenmodes of a rectangular PEC cavity.

The first real Palace calculation in QMHP-CEM solves the *empty* Object 001
vacuum cavity as a closed perfect-electric-conductor box. That domain has an
exact solution, which is what makes it the right first calculation: a solver
pipeline is only proven when its output can be checked against something it
did not produce itself.

For a box of side lengths ``a``, ``b``, ``d`` the resonant frequencies are

    f_mnp = (c / 2) * sqrt((m/a)^2 + (n/b)^2 + (p/d)^2)

for non-negative integer index triples in which at most one index is zero
(TE and TM families together; a triple with two zero indices is not a mode).

An eigensolver counts eigenvalues with multiplicity, so a solver asked for N
modes returns degenerate frequencies repeated. Two sources of degeneracy are
tracked here: index permutations that coincide for equal side lengths (for a
square cavity (1,2,0) and (2,1,0) share a frequency), and the TE/TM pair that
exists whenever all three indices are non-zero. :func:`expected_solver_modes`
expands the distinct spectrum by those multiplicities, which is what Palace's
``eig.csv`` should line up with.

Enumeration is range-aware: :func:`rectangular_cavity_modes_below` derives the
index bounds from the frequency ceiling (``m <= 2 a f_max / c`` and likewise
for ``n`` and ``p``), so it is complete by construction at any frequency. That
matters for a thin cavity, whose first height-dependent mode (p = 1) lies
far above hundreds of p = 0 modes: for the 22 x 22 x 1.5 mm box it is at
about 100 GHz with 154 modes below it. A fixed index cap would miss most of
them.

Classification of any number computed here: derived from ENGINEERING-SEED
dimensions, so ENGINEERING-SEED. It is a check on the solver, not a QMHP
requirement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Speed of light in vacuum, exact (SI).
C_M_PER_S = 299_792_458.0

#: Frequencies within this relative distance are the same distinct mode.
_DEGENERACY_REL = 1e-9


@dataclass(frozen=True)
class CavityMode:
    m: int
    n: int
    p: int
    frequency_GHz: float
    #: How many eigenvalues a solver reports at this frequency: coinciding index
    #: triples, each counted twice when all three indices are non-zero (TE+TM).
    multiplicity: int = 1

    @property
    def label(self) -> str:
        return f"analytic_{self.m}{self.n}{self.p}"

    @property
    def height_dependent(self) -> bool:
        """True for p >= 1: the frequency depends on the cavity height ``d``."""
        return self.p >= 1


def mode_frequency_GHz(a_mm: float, b_mm: float, d_mm: float, m: int, n: int, p: int) -> float:
    """Closed-form frequency of one index triple."""
    if min(a_mm, b_mm, d_mm) <= 0:
        raise ValueError("cavity dimensions must be positive")
    if (m == 0) + (n == 0) + (p == 0) >= 2:
        raise ValueError(f"({m},{n},{p}) is not a mode: at most one index may be zero")
    a, b, d = (x * 1e-3 for x in (a_mm, b_mm, d_mm))
    return 0.5 * C_M_PER_S * math.sqrt((m / a) ** 2 + (n / b) ** 2 + (p / d) ** 2) / 1e9


def index_bounds(a_mm: float, b_mm: float, d_mm: float, f_max_GHz: float) -> tuple[int, int, int]:
    """Largest ``m``, ``n``, ``p`` any mode at or below ``f_max_GHz`` can carry.

    Since ``f_mnp >= (c/2) m/a`` for every ``n, p``, an index above
    ``2 a f_max / c`` cannot appear below ``f_max``; the bound is exact.
    """
    if f_max_GHz <= 0:
        raise ValueError("f_max_GHz must be positive")
    return tuple(int(math.floor(2.0 * x * 1e-3 * f_max_GHz * 1e9 / C_M_PER_S)) for x in (a_mm, b_mm, d_mm))  # type: ignore[return-value]


def rectangular_cavity_modes_below(
    a_mm: float, b_mm: float, d_mm: float, f_max_GHz: float
) -> list[CavityMode]:
    """Every distinct-frequency mode with ``f <= f_max_GHz``, complete by construction.

    Degenerate modes are returned once, at the lowest-lexicographic triple,
    carrying their multiplicity.
    """
    if min(a_mm, b_mm, d_mm) <= 0:
        raise ValueError("cavity dimensions must be positive")
    m_max, n_max, p_max = index_bounds(a_mm, b_mm, d_mm, f_max_GHz)
    found: dict[float, CavityMode] = {}
    for m in range(0, m_max + 1):
        for n in range(0, n_max + 1):
            for p in range(0, p_max + 1):
                if (m == 0) + (n == 0) + (p == 0) >= 2:
                    continue
                f = mode_frequency_GHz(a_mm, b_mm, d_mm, m, n, p)
                if f > f_max_GHz * (1.0 + _DEGENERACY_REL):
                    continue
                key = round(f, 9)
                weight = 2 if (m and n and p) else 1   # TE and TM both exist
                if key not in found:
                    found[key] = CavityMode(m, n, p, f, weight)
                else:
                    prev = found[key]
                    found[key] = CavityMode(prev.m, prev.n, prev.p, prev.frequency_GHz,
                                            prev.multiplicity + weight)
    return [found[k] for k in sorted(found)]


def rectangular_cavity_modes(
    a_mm: float, b_mm: float, d_mm: float, count: int = 8, max_index: int = 6
) -> list[CavityMode]:
    """Lowest ``count`` distinct-frequency modes of an ``a x b x d`` PEC box.

    ``count`` refers to distinct frequencies; use :func:`expected_solver_modes`
    for the list a solver reports. ``max_index`` is kept for compatibility and
    no longer limits the enumeration: the frequency ceiling is raised until
    ``count`` distinct modes lie below it, so the result is complete.
    """
    if min(a_mm, b_mm, d_mm) <= 0:
        raise ValueError("cavity dimensions must be positive")
    if count < 1:
        return []
    f_max = 2.0 * mode_frequency_GHz(a_mm, b_mm, d_mm, 1, 1, 0)
    for _ in range(64):
        modes = rectangular_cavity_modes_below(a_mm, b_mm, d_mm, f_max)
        if len(modes) >= count:
            return modes[:count]
        f_max *= 2.0
    raise RuntimeError("could not enumerate the requested number of modes")  # pragma: no cover


def expected_solver_modes(
    a_mm: float, b_mm: float, d_mm: float, n_modes: int, f_min_GHz: float | None = None
) -> list[float]:
    """The first ``n_modes`` frequencies a solver should report, with repeats.

    With ``f_min_GHz`` the list starts at the lowest mode at or above it,
    which is what Palace returns for a shift-and-invert target at that
    frequency (eigenvalues close to, but not below, the target). A square
    22 x 22 x 1.5 mm box asked for four modes from the bottom gives
    ``[f_110, f_120, f_120, f_220]``, not four distinct frequencies.
    """
    if n_modes < 1:
        return []
    floor = f_min_GHz if f_min_GHz is not None else 0.0
    f_max = max(2.0 * mode_frequency_GHz(a_mm, b_mm, d_mm, 1, 1, 0), floor * 1.5)
    for _ in range(64):
        out: list[float] = []
        for mode in rectangular_cavity_modes_below(a_mm, b_mm, d_mm, f_max):
            if mode.frequency_GHz < floor * (1.0 - _DEGENERACY_REL):
                continue
            out.extend([mode.frequency_GHz] * mode.multiplicity)
            if len(out) >= n_modes:
                return out[:n_modes]
        f_max *= 2.0
    raise RuntimeError("could not enumerate the requested number of modes")  # pragma: no cover


def fundamental_GHz(a_mm: float, b_mm: float, d_mm: float) -> float:
    return rectangular_cavity_modes(a_mm, b_mm, d_mm, count=1)[0].frequency_GHz
