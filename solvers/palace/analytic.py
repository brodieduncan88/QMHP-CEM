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

Classification of any number computed here: derived from ENGINEERING-SEED
dimensions, so ENGINEERING-SEED. It is a check on the solver, not a QMHP
requirement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Speed of light in vacuum, exact (SI).
C_M_PER_S = 299_792_458.0


@dataclass(frozen=True)
class CavityMode:
    m: int
    n: int
    p: int
    frequency_GHz: float

    @property
    def label(self) -> str:
        return f"analytic_{self.m}{self.n}{self.p}"


def rectangular_cavity_modes(
    a_mm: float, b_mm: float, d_mm: float, count: int = 8, max_index: int = 6
) -> list[CavityMode]:
    """Lowest ``count`` distinct-frequency modes of an ``a x b x d`` PEC box.

    Degenerate modes (identical frequency from different index triples) are
    returned once, at the lowest-lexicographic triple, so that ``count`` refers
    to distinct resonances a solver would report.
    """
    if min(a_mm, b_mm, d_mm) <= 0:
        raise ValueError("cavity dimensions must be positive")
    a, b, d = (x * 1e-3 for x in (a_mm, b_mm, d_mm))
    found: dict[float, CavityMode] = {}
    for m in range(0, max_index + 1):
        for n in range(0, max_index + 1):
            for p in range(0, max_index + 1):
                if (m == 0) + (n == 0) + (p == 0) >= 2:
                    continue
                f_hz = 0.5 * C_M_PER_S * math.sqrt((m / a) ** 2 + (n / b) ** 2 + (p / d) ** 2)
                key = round(f_hz / 1e9, 9)
                if key not in found:
                    found[key] = CavityMode(m, n, p, f_hz / 1e9)
    return [found[k] for k in sorted(found)][:count]


def fundamental_GHz(a_mm: float, b_mm: float, d_mm: float) -> float:
    return rectangular_cavity_modes(a_mm, b_mm, d_mm, count=1)[0].frequency_GHz
