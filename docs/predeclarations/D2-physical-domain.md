# D2: physical-domain checks on the device energies

**Status: PREDECLARED. NOT IMPLEMENTED.** Blocked on a physics-owner decision about
the domains below. No code enforces them yet.

## Observed on `main` at `79844b7`

`models.fluxonium.solve_static` and `models.collision.screen` accept non-physical
energies and return numbers:

| call | result |
|---|---|
| `solve_static(EC_GHz=-0.6)` | levels 0, 0.1757, 3.5817 GHz |
| `solve_static(EC_GHz=0.0)` | levels 0, 8.9e-16, 1.0e-4 GHz |
| `solve_static(EJ_GHz=-5.72)` | levels returned |
| `solve_static(EL_GHz=-1.58)` | levels returned |
| `collision.screen(EC=-0.6, EJ=5.72, EL=1.58)["passes"]` | `True` |

Non-finite inputs already raise, as a bare numpy `ValueError`.

## Decision needed

**Proposed and provisional:** `EC_GHz`, `EJ_GHz` and `EL_GHz` must each be finite
and strictly positive. The physics owner confirms or replaces this and names the
source clause. Parameters other than these three have not been probed.

## Acceptance criteria (fixed now)

1. A domain table lists every public parameter of `models.fluxonium`,
   `models.collision` and the candidate contract, with its domain, source and
   status (`CONFIRMED` or `PROVISIONAL`).
2. An out-of-domain value raises a typed error naming the parameter, value and
   domain **before** any matrix is built (a spy on the diagonalisation sees zero
   calls).
3. For each parameter, a value just inside the domain is accepted, and one on
   the boundary and one just outside are rejected.
4. The frozen nominal parameters are accepted and their outputs are
   bit-identical to `79844b7` (`tests/test_physics_regression.py` passes).
5. The candidate contract rejects an out-of-domain parameter, so a sweep cannot
   contain one.
