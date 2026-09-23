# Order-1 mesh-refinement check — level 3

Record `COUPLED-LADDER-O1-L3-20260916T091212Z`. Order-1 mesh-refinement check, one level per invocation, at fixed element order 1 and fixed 0.08 mm halo. Measures whether the discretisation converges, and tests the supported-but-unproven port-stiffness explanation of the energy-balance failures using Palace's own boundary quadrature. NO coupling extraction: no Route A inversion, no g, no charging energy, no capacitance, no circuit parameter. The 250 000-DOF rule, the 45-minute cap and the prospective admission, matching and magnitude rules are unchanged.

## 1. Dry runs (offline, no solver)

| level | h_gap (mm) | tetrahedra | DOF order 1 | DOF order 2 | order 1 ≤ 250 000 | order 2 ≤ 250 000 |
|---|---|---|---|---|---|---|
| 2 | 0.006667 | 64434 | 79944 | 420664 | yes | NO |
| 3 | 0.005000 | 120370 | 147372 | 781554 | yes | NO |

## 2. The solve

Status **COMPLETED**, order 1, halo 0.08 mm, 147372 DOF.
Wall clock 159.1 s, 5.9 % of the 2700 s cap.

| Palace timer | s |
|---|---|
| Total | 158.808 |
| Setup | 0.090 |
| Preconditioner | 12.722 |
| LinearSolve | 14.556 |
| EigenvalueSolve | 4.609 |
| Div.-FreeProjection | 7.397 |

Palace's own timer names. 'Preconditioner' is preconditioner APPLICATION inside the linear solves, not setup; 'Setup' is the separate setup line. The log names no preconditioner type, so none is asserted.

## 3. Admitted modes

| m | f (GHz) | backward error | R | \|R−1\| | \|p\| | disposition |
|---|---|---|---|---|---|---|
| 1 | 1.709562 | 1.55e-17 | 9.999823e-01 | 1.768e-05 | 9.983176e-01 | ADMITTED |
| 2 | 4.087683 | 6.05e-17 | 9.999997e-01 | 3.165e-07 | 9.112764e-04 | ADMITTED |
| 3 | 9.109258 | 3.55e-12 | 5.549244e-05 | 9.999e-01 | 2.627565e-06 | REJECTED_ENERGY_BALANCE |
| 4 | 10.272094 | 1.40e-12 | 3.206315e-05 | 1.000e+00 | 2.768794e-07 | REJECTED_ENERGY_BALANCE |
| 5 | 11.098712 | 1.07e-12 | 3.253497e-05 | 1.000e+00 | 1.416941e-07 | REJECTED_ENERGY_BALANCE |
| 6 | 11.836121 | 3.46e-11 | 9.991821e-01 | 8.179e-04 | 4.203529e-05 | ADMITTED |

## 4. Correspondence with level 1 (P2)

Matching: **MATCHED**.

| L1 m | L2 m | f_L1 (GHz) | f_L2 (GHz) | Δf | Δ\|p\| | guard | margin |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 1.158333 | 1.709562 | 4.7588e-01 | 1.9262e-04 | APPLIED | 2.16× |
| 2 | 2 | 3.693189 | 4.087683 | 1.0682e-01 | 2.3914e-02 | APPLIED | 3.01× |

## 5. The port-field test

**CALIBRATION-UNSOUND** — the admitted modes disagree about kappa by a factor of 20.5; the surrogate is not faithful even on them, so nothing can be concluded about the failing rows

κ calibrated from the admitted modes: 3.776432e+01, spread across them 20.4566×.

| m | admitted | reported R | s_t | κ·s_t/f² | restored R | E_ind/E_port |
|---|---|---|---|---|---|---|
| 1 | yes | 9.9998e-01 | 5.2757e-02 | 6.8170e-01 | 0.683367 | 1.4644e+00 |
| 2 | yes | 1.0000e+00 | 2.7542e-04 | 6.2247e-04 | 0.999711 | 1.4640e+00 |
| 3 | no | 5.5492e-05 | 1.5003e+00 | 6.8280e-01 | 0.682856 | 3.8482e-06 |
| 4 | no | 3.2063e-05 | 1.9078e+00 | 6.8282e-01 | 0.682850 | 4.0550e-07 |
| 5 | no | 3.2535e-05 | 2.2272e+00 | 6.8282e-01 | 0.682850 | 2.0751e-07 |
| 6 | yes | 9.9918e-01 | 2.1783e-03 | 5.8718e-04 | 0.999727 | 7.1588e-02 |

## 6. Convergence over the rungs

| level | h_gap (mm) | DOF | wall clock (s) | source |
|---|---|---|---|---|
| 1 | 0.010000 | 39832 | 32.4 | `COUPLED-PILOT-20260916T035733Z/P2` |
| 2 | 0.006667 | 79944 | 81.2 | `COUPLED-LADDER-O1-L2-20260916T080802Z` |
| 3 | 0.005000 | 147372 | 159.1 | `COUPLED-LADDER-O1-L3-20260916T091212Z` |

Mode tracking: the composed L1->L2->L3 correspondence agrees with the direct L1->L3 match

### L1m1 (LUMPED_DOMINATED)

| level | mode | f (GHz) | \|p\| |
|---|---|---|---|
| 1 | 1 | 1.158333 | 9.9851e-01 |
| 2 | 1 | 1.461887 | 9.9856e-01 |
| 3 | 1 | 1.709562 | 9.9832e-01 |

- **no order of convergence**: the successive differences shrink by only 1.226, at or below the 1.409 that the refinement ratios impose even as the order tends to zero: no positive order of convergence fits these three rungs
- differences: L1→L2 -3.0355e-01, L2→L3 -2.4768e-01; shrinking: True; monotone: True
- ratio of successive differences 1.226 against the 1.409 floor these refinement ratios impose for any positive order
- \|p\|: no order — the sequence is not monotone in h, so no single power law describes it

### L1m2 (FIELD_DOMINATED)

| level | mode | f (GHz) | \|p\| |
|---|---|---|---|
| 1 | 2 | 3.693189 | 9.3360e-04 |
| 2 | 2 | 3.885511 | 7.7813e-04 |
| 3 | 2 | 4.087683 | 9.1128e-04 |

- **no order of convergence**: the successive differences shrink by only 0.9513, at or below the 1.409 that the refinement ratios impose even as the order tends to zero: no positive order of convergence fits these three rungs
- differences: L1→L2 -1.9232e-01, L2→L3 -2.0217e-01; shrinking: False; monotone: True
- ratio of successive differences 0.9513 against the 1.409 floor these refinement ratios impose for any positive order
- \|p\|: no order — the sequence is not monotone in h, so no single power law describes it

Three rungs give the FIRST order estimate, not a confirmed one: confirming it needs a fourth, because a three-point fit has no degrees of freedom left to test itself.

## 7. Is the sequence still clearly pre-asymptotic?

**YES** — worst estimated remaining relative error at the finest rung inf.

- `L1m1`: **NO-ORDER** — the successive differences shrink by only 1.226, at or below the 1.409 that the refinement ratios impose even as the order tends to zero: no positive order of convergence fits these three rungs
- `L1m2`: **NO-ORDER** — the successive differences shrink by only 0.9513, at or below the 1.409 that the refinement ratios impose even as the order tends to zero: no positive order of convergence fits these three rungs

clearly pre-asymptotic if any tracked mode yields no positive order, or an order far from the method's expected 2, or an estimated remaining error above 1e-2 at the finest rung. This is a descriptive numerical criterion introduced with this record; it gates nothing and is not a physical threshold.

## 8. What order-2 mesh the frozen tolerance would need

**Not projectable.** No tracked mode yielded an extrapolated limit, so there is no continuum value to measure an order-2 mesh against:

- `L1m1`: the order-1 sequence yields no extrapolated limit, so nothing can be projected
- `L1m2`: the order-1 sequence yields no extrapolated limit, so nothing can be projected

## 9. Does the port-field mechanism reproduce?

- L2: **EXPLANATION-2-SUPPORTED**
- L3: **CALIBRATION-UNSOUND**

## 10. Is the next level justified and affordable?

Level 3 measures **147372 DOF** at order 1 against the 250000 rule: inside.
Projected wall clock 159 s (linear in DOF) to 159 s (quadratic), against the 2700 s cap. bracketed by linear and quadratic scaling in DOF, because two rungs give one within-order timing ratio and that is not enough to fix an exponent.

**FOR REVIEW — this script launches one level per invocation and stops**

