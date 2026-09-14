# Regression pins: what reproduces, and what does not

QMHP-CEM's physics models are implemented against the frozen conventions and
regression-tested against the v1.5.8f pins. This records what was measured, so
that the tolerances in `master/qmhp_v158f_requirements.yaml` can be audited
rather than taken on trust.

**Authority:** `reference/v1_5_8f_release_bundle/qmhp_v158f_readout_replication.py`
— the third independent implementation shipped with the frozen release.

**Measured under:** the release's own declared runtime (Python 3.12.3,
numpy 2.4.4, scipy 1.17.1), and cross-checked under the CEM runtime
(Python 3.11, numpy 2.4.6). The deviations below are identical in both, so
they are **not** environment artifacts.

## Reproduces at the declared 1e-6 or better

| Pin | Frozen | Observed | Rel. deviation |
|---|---|---|---|
| `dressed_root_10_12_GHz` | 4.301974466 | 4.301974466 | 9.9e-11 |
| `dressed_root_14_25_GHz` | 4.301975383 | 4.301975383 | 9.9e-11 |
| `f01_GHz` | 0.175710013 | 0.175710013 | 0 |
| `f02_GHz` | 3.581724312 | 3.581724312 | 0 |
| `sin_delta_over_2_02` | 0.295705232 | 0.295705232 | 0 |

## Printed at fewer digits than the computation carries

Compared at their printed precision, under the spec §12.3 carve-out for
references "deliberately printed at fewer digits".

| Pin | Frozen (printed) | Observed |
|---|---|---|
| `sink_line_GHz` | 4.310696 | 4.310695632 |
| `dressed_f12_GHz` | 3.395056 | 3.395056362 |
| `sink_logical_contrast_MHz` | 18.228 | 18.228246287 |
| `n12` | 0.659915 | 0.659914846 |

Each rounds correctly to its printed value.

## FLAGGED — printed to more digits than reproduce

**These three pins do not reach the declared 1e-6 relative tolerance.**

| Pin | Frozen | Observed | Rel. deviation | vs 1e-6 |
|---|---|---|---|---|
| `f8_purcell_weight` | 0.01182198 | 0.0118220064 | 2.23e-6 | **exceeds** |
| `sink_pull_MHz` | 8.721155 | 8.7211658846 | 1.25e-6 | **exceeds** |
| `logical_pull_MHz` | -9.507089 | -9.5070804035 | 9.04e-7 | within, marginal |

Spec §12.3 forbids weakening a tolerance merely to make CI pass, so these were
**not** absorbed into the exact group. They sit in a separate
`cross_implementation` group carrying `status: FLAGGED-FOR-REVIEW`, asserted at
the *measured* agreement (5e-6) rather than at a convenient round number, and
`tests/test_physics_regression.py` additionally asserts that the deviation is
still real — so if a future change closes the gap, the flag can be lifted
deliberately rather than drifting away unnoticed.

### What this probably is

The magnitude (parts in 10⁶ on derived quantities, while the roots themselves
agree to 1e-10) is consistent with the extra digits having been recorded from a
*different* one of the release's independent implementations than the vendored
third one. Cross-implementation agreement at ~2e-6 on a second-order derived
quantity is unremarkable in itself; what is not established is which
implementation the printed digits came from.

**This is a human decision.** Do not tighten or loosen these tolerances without
adjudicating it.

## Carried but unverifiable

No script in the release bundle implements the Eq.(7) perturbative diagnostic
or the curvature/quasiparticle quantities, so these are asserted as frozen
values only and never compared against a computation:

- `perturbative_root_GHz` = 4.314628047
- `eq7_chi_MHz` = [-5.366823, -0.305447, 7.214942]
- `richardson_curvature_GHz_per_Phi0_sq` = 5064.55
- `gamma_qp_over_xqp_per_s` = 4.106e10

The Eq.(7) root is used only to motivate the search bracket; it is 12.7 MHz
from the exact dressed root and must never be reported as the operating point.

## Conventions that turned out to be load-bearing

Two details are not cosmetic — getting either wrong silently changes the answer:

1. **`sin((phi - phi_ext)/2)`, not `sin(phi/2)`.** With the frozen
   `phi_ext = pi`, the 0-2 element of `sin(phi/2)` vanishes identically by
   parity. The offset is what makes 0.295705232 reproduce at all.
2. **The root-search bracket.** The nominal ladder uses [4.20, 4.40] GHz, but
   perturbed ensemble devices move the root outside it. Ensembles use
   [4.05, 4.55] GHz, matching the reference default. A device whose root
   escapes even that raises `RootNotBracketed` and is counted as *unscreened* —
   neither a pass nor a rejection, because it was never actually screened.

## Ensemble cross-check

The CEM tolerance convention (`EC -> EJ -> EL`, per-device draws) is
deliberately **not** the legacy draw order, so finite-sample counts differ from
the release by construction. The rates agree:

| Source | Rate |
|---|---|
| Frozen pooled reference (20 x 400) | 6.66% [6.12%, 7.21%] |
| Reference impl, seed 20260725 | 8.00% |
| Reference impl, seed 77 | 6.75% |
| QMHP-CEM, seed 20260725 (400) | 6.25% [4.27%, 9.06%] |

The CEM 95% interval contains the frozen pooled rate.
