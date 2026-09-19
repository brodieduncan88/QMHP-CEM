# S1 numerical recovery: the port diagnostic and the prepared experiment

Record `COUPLED-S1-RECOVERY-20260916T105215Z`, schema `qmhp-cem.s1-numerical-recovery/0.1.0`. No Palace was launched. Every source record was verified against its own manifest before and after, and none was written to.

## 1. The conversion is derived, not calibrated

`kappa = 1/(t_nd * Ls_nd) = 0.3886882529`, from `Lc = 4.000000e-03 m` (the mesh bounding box), `L = 1.034567e-07 H`, the port face `0.04 x 0.02 mm` and `t_nd = 0.25`. No solver output is read to compute it, and no mode was selected to fit it.

| level | modes | worst probe-vs-closure disagreement |
|---|---|---|
| L1 | n/a | no port-field probes in that run |
| L2 | 6 | 4.35e-07 |
| L3 | 6 | 2.05e-08 |

The probe evaluation and the closure requirement share no input: the first reads `surface-Q.csv`, `eig.csv` and geometry, the second reads `domain-E.csv`. The closure number is **not** an independent measurement of the port energy and is never quoted as verifying the closure it comes from.

## 2. The port face, as built

| level | requested h_gap | port triangles | element size on the face | elements across the width |
|---|---|---|---|---|
| L1 | 0.010000 mm | 17 | 0.010425 mm | 1.92 |
| L2 | 0.006667 mm | 25 | 0.008597 mm | 2.33 |
| L3 | 0.005000 mm | 45 | 0.006407 mm | 3.12 |

`the size the existing field prescribes at the port centre is a fixed multiple of h_gap at every level, so refining the ladder never resolves the port face` — the ratio is {"L1": 5.041666666666666, "L2": 5.041666666666667, "L3": 5.041666666666666}, scale-invariant: True.

## 3. How the tested sequence moved

| tracked mode | role | f(L1), f(L2), f(L3) GHz | exponent q in f^2 ~ h^-q | agreement |
|---|---|---|---|---|
| L1m1 | LUMPED_DOMINATED | 1.158333, 1.461887, 1.709562 | 1.148, 1.088 | 5.2% |
| L1m2 | FIELD_DOMINATED | 3.693189, 3.885511, 4.087683 | 0.250, 0.353 | 40.8% |

The ladder's own estimator already refused an order of convergence on these three rungs and that refusal stands. This is the complementary reading, bounded the same way: three points and two intervals establish no law, prove no mathematical nonconvergence, say nothing about the physical architecture, and do not show that the in-budget meshes are exhausted.

## 4. The prepared experiment

| mesh | h_port | DOF (order 1) | fraction of the 250 000 rule | port triangles | elements across the width |
|---|---|---|---|---|---|
| R1 | 0.003333 mm | 80762 | 32.3% | 176 | 6.17 |
| R2 | 0.001667 mm | 111238 | 44.5% | 680 | 12.13 |

Both are dry-run measurements, not estimates. Nothing here promises that two meshes establish convergence; the experiment is a discriminating diagnostic and `summary.json` states what each possible outcome would and would not mean.
