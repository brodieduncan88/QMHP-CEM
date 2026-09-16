# Order-1 mesh-refinement check — level 2

Record `COUPLED-LADDER-O1-L2-20260916T080802Z`. Order-1 mesh-refinement check, one level per invocation, at fixed element order 1 and fixed 0.08 mm halo. Measures whether the discretisation converges, and tests the supported-but-unproven port-stiffness explanation of the energy-balance failures using Palace's own boundary quadrature. NO coupling extraction: no Route A inversion, no g, no charging energy, no capacitance, no circuit parameter. The 250 000-DOF rule, the 45-minute cap and the prospective admission, matching and magnitude rules are unchanged.

## 1. Dry runs (offline, no solver)

| level | h_gap (mm) | tetrahedra | DOF order 1 | DOF order 2 | order 1 ≤ 250 000 | order 2 ≤ 250 000 |
|---|---|---|---|---|---|---|
| 2 | 0.006667 | 64434 | 79944 | 420664 | yes | NO |
| 3 | 0.005000 | 120370 | 147372 | 781554 | yes | NO |

## 2. The solve

Status **COMPLETED**, order 1, halo 0.08 mm, 79944 DOF.
Wall clock 81.2 s, 3.0 % of the 2700 s cap.

| Palace timer | s |
|---|---|
| Total | 78.524 |
| Setup | 0.029 |
| Preconditioner | 3.253 |
| LinearSolve | 2.448 |
| EigenvalueSolve | 1.741 |
| Div.-FreeProjection | 2.401 |

Palace's own timer names. 'Preconditioner' is preconditioner APPLICATION inside the linear solves, not setup; 'Setup' is the separate setup line. The log names no preconditioner type, so none is asserted.

## 3. Admitted modes

| m | f (GHz) | backward error | R | \|R−1\| | \|p\| | disposition |
|---|---|---|---|---|---|---|
| 1 | 1.461887 | 1.89e-17 | 9.999665e-01 | 3.351e-05 | 9.985647e-01 | ADMITTED |
| 2 | 3.885511 | 4.99e-17 | 9.999978e-01 | 2.227e-06 | 7.781308e-04 | ADMITTED |
| 3 | 5.088915 | 7.40e-17 | 4.643217e-05 | 1.000e+00 | 9.058152e-06 | REJECTED_ENERGY_BALANCE |
| 4 | 6.039804 | 2.56e-15 | 7.042607e-05 | 9.999e-01 | 1.100249e-05 | REJECTED_ENERGY_BALANCE |
| 5 | 7.177902 | 1.46e-11 | 5.850647e-05 | 9.999e-01 | 8.605177e-06 | REJECTED_ENERGY_BALANCE |
| 6 | 8.706862 | 1.62e-11 | 6.029550e-05 | 9.999e-01 | 2.368541e-06 | REJECTED_ENERGY_BALANCE |

## 4. Correspondence with level 1 (P2)

Matching: **MATCHED**.

| L1 m | L2 m | f_L1 (GHz) | f_L2 (GHz) | Δf | Δ\|p\| | guard | margin |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 1.158333 | 1.461887 | 2.6206e-01 | 5.4875e-05 | APPLIED | 3.99× |
| 2 | 2 | 3.693189 | 3.885511 | 5.2075e-02 | 1.6653e-01 | APPLIED | 6.30× |

## 5. The port-field test

**EXPLANATION-2-SUPPORTED** — the restored balance is 1 to within 1e-2 on every failing row (range 0.998557 to 0.998557): the tangential port field accounts for the missing stiffness, as a genuine eigenpair whose average understates it predicts

κ calibrated from the admitted modes: 5.522502e+01, spread across them 1.0028×.

| m | admitted | reported R | s_t | κ·s_t/f² | restored R | E_ind/E_port |
|---|---|---|---|---|---|---|
| 1 | yes | 9.9997e-01 | 3.8588e-02 | 9.9716e-01 | 0.998559 | 1.0014e+00 |
| 2 | yes | 1.0000e+00 | 2.1302e-04 | 7.7923e-04 | 0.999999 | 9.9859e-01 |
| 3 | no | 4.6432e-05 | 4.6824e-01 | 9.9852e-01 | 0.998557 | 9.0716e-06 |
| 4 | no | 7.0426e-05 | 6.5956e-01 | 9.9850e-01 | 0.998557 | 1.1019e-05 |
| 5 | no | 5.8506e-05 | 9.3156e-01 | 9.9851e-01 | 0.998557 | 8.6180e-06 |
| 6 | no | 6.0296e-05 | 1.3707e+00 | 9.9850e-01 | 0.998557 | 2.3721e-06 |

## 6. Is level 3 justified and affordable?

Level 3 measures **147372 DOF** at order 1 against the 250000 rule: inside.
Projected wall clock 150 s (linear in DOF) to 276 s (quadratic), against the 2700 s cap. bracketed by linear and quadratic scaling in DOF, because two rungs give one within-order timing ratio and that is not enough to fix an exponent.

**FOR REVIEW — this script launches one level per invocation and stops**

