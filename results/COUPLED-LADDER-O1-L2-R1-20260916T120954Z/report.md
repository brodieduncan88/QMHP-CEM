# Order-1 mesh-refinement check — level 2

Record `COUPLED-LADDER-O1-L2-R1-20260916T120954Z`. Order-1 mesh-refinement check, one level per invocation, at fixed element order 1 and fixed 0.08 mm halo. Measures whether the discretisation converges, and tests the supported-but-unproven port-stiffness explanation of the energy-balance failures using Palace's own boundary quadrature. NO coupling extraction: no Route A inversion, no g, no charging energy, no capacitance, no circuit parameter. The 250 000-DOF rule, the 45-minute cap and the prospective admission, matching and magnitude rules are unchanged.

## 1. Dry runs (offline, no solver)

| level | h_gap (mm) | tetrahedra | DOF order 1 | DOF order 2 | order 1 ≤ 250 000 | order 2 ≤ 250 000 |
|---|---|---|---|---|---|---|
| 2 | 0.006667 | 64434 | 79944 | 420664 | yes | NO |
| 3 | 0.005000 | 120370 | 147372 | 781554 | yes | NO |

The table above is the UNREFINED level prescription, which is what the ladder rungs use. This run adds a local constraint on top of it; its own measured DOF is in section 2 and differs from the level row above.

## 1b. The local refinement this run carries

Approved as **R1**: `h_port = 0.003333333333333333 mm` held over the port rectangle padded by `0.01 mm`, blending back to `h_far` over `0.02 mm`, on ['port_F1'].

h_far, the conductor/etch Distance field, the halo, the geometry, the materials, the port dimensions and inductance, the boundary conditions and the physical groups. Combined by `Min with the existing conductor/etch Threshold`, so it can only refine.

Mesh `sha256 a49ef282c7f07c56f210a450b291a2e027de530ba7c3e78bbdcead3b67315fee`.

**This is not a ladder rung.** It carries a size constraint the other rungs do not, so it is excluded from the convergence fit and compared against the plain rung at its own level.

## 2. The solve

Status **COMPLETED**, order 1, halo 0.08 mm, 80762 DOF.
Wall clock 95.7 s, 3.5 % of the 2700 s cap.

| Palace timer | s |
|---|---|
| Total | 95.457 |
| Setup | 0.038 |
| Preconditioner | 5.202 |
| LinearSolve | 5.074 |
| EigenvalueSolve | 1.873 |
| Div.-FreeProjection | 2.773 |

Palace's own timer names. 'Preconditioner' is preconditioner APPLICATION inside the linear solves, not setup; 'Setup' is the separate setup line. The log names no preconditioner type, so none is asserted.

## 3. Admitted modes

| m | f (GHz) | backward error | R | \|R−1\| | \|p\| | disposition |
|---|---|---|---|---|---|---|
| 1 | 1.521003 | 1.39e-17 | 9.999588e-01 | 4.119e-05 | 9.981103e-01 | ADMITTED |
| 2 | 3.867223 | 3.37e-17 | 9.999973e-01 | 2.710e-06 | 1.089944e-03 | ADMITTED |
| 3 | 5.913013 | 2.93e-12 | 2.511403e-05 | 1.000e+00 | 6.603987e-06 | REJECTED_ENERGY_BALANCE |
| 4 | 6.784334 | 3.79e-14 | 3.639144e-05 | 1.000e+00 | 1.364264e-05 | REJECTED_ENERGY_BALANCE |
| 5 | 6.843502 | 5.50e-13 | 2.399770e-05 | 1.000e+00 | 1.444141e-06 | REJECTED_ENERGY_BALANCE |
| 6 | 7.232512 | 5.79e-11 | 2.856776e-05 | 1.000e+00 | 2.753735e-06 | REJECTED_ENERGY_BALANCE |
| 7 | 7.331706 | 3.04e-11 | 2.040510e-05 | 1.000e+00 | 1.926531e-07 | REJECTED_ENERGY_BALANCE |

## 4. Correspondence with level 1 (P2)

Matching: **MATCHED**.

| L1 m | L2 m | f_L1 (GHz) | f_L2 (GHz) | Δf | Δ\|p\| | guard | margin |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 1.158333 | 1.521003 | 3.1310e-01 | 4.0024e-04 | APPLIED | 3.23× |
| 2 | 2 | 3.693189 | 3.867223 | 4.7123e-02 | 1.4344e-01 | APPLIED | 6.74× |

## 5. The port-field test (SUPERSEDED: it calibrates its constant)

Kept because it is the record of what the earlier procedure returned. The number to read is section 5b, whose constant is derived from pinned Palace source and fits nothing.

**EXPLANATION-2-SUPPORTED** — the restored balance is 1 to within 1e-2 on every failing row (range 0.998739 to 0.998739): the tangential port field accounts for the missing stiffness, as a genuine eigenpair whose average understates it predicts

κ calibrated from the admitted modes: 5.523508e+01, spread across them 1.0024×.

| m | admitted | reported R | s_t | κ·s_t/f² | restored R | E_ind/E_port |
|---|---|---|---|---|---|---|
| 1 | yes | 9.9996e-01 | 4.1754e-02 | 9.9689e-01 | 0.998741 | 1.0012e+00 |
| 2 | yes | 1.0000e+00 | 2.9547e-04 | 1.0913e-03 | 0.999999 | 9.9878e-01 |
| 3 | no | 2.5114e-05 | 6.3219e-01 | 9.9872e-01 | 0.998739 | 6.6124e-06 |
| 4 | no | 3.6391e-05 | 8.3223e-01 | 9.9872e-01 | 0.998739 | 1.3660e-05 |
| 5 | no | 2.3998e-05 | 8.4681e-01 | 9.9872e-01 | 0.998739 | 1.4460e-06 |
| 6 | no | 2.8568e-05 | 9.4581e-01 | 9.9871e-01 | 0.998739 | 2.7573e-06 |
| 7 | no | 2.0405e-05 | 9.7194e-01 | 9.9872e-01 | 0.998739 | 1.9290e-07 |

## 5b. Port participation, from a conversion derived from source

`kappa = 1/(t_nd * Ls_nd) = 0.3886882529`, from `Lc = 4.000000e-03 m` measured on this run's own mesh, `L = 1.034567e-07 H`, the port face `0.04 x 0.02 mm` and `t_nd = 0.25`. Nothing is fitted and no solver output is read to form it.

| mode | f (GHz) | p from probes | p reported (E_ind) | p from closure | probe/closure | E_ind/E_port |
|---|---|---|---|---|---|---|
| 1 | 1.521003 | 9.981515e-01 | 9.981103e-01 | 9.981515e-01 | 1.00000000 | 9.9996e-01 |
| 2 | 3.867223 | 1.092655e-03 | 1.089944e-03 | 1.092654e-03 | 1.00000131 | 9.9752e-01 |
| 3 | 5.913013 | 9.999815e-01 | 6.603987e-06 | 9.999815e-01 | 1.00000000 | 6.6041e-06 |
| 4 | 6.784334 | 9.999773e-01 | 1.364264e-05 | 9.999773e-01 | 1.00000000 | 1.3643e-05 |
| 5 | 6.843502 | 9.999774e-01 | 1.444141e-06 | 9.999774e-01 | 1.00000000 | 1.4442e-06 |
| 6 | 7.232512 | 9.999742e-01 | 2.753735e-06 | 9.999742e-01 | 1.00000000 | 2.7538e-06 |
| 7 | 7.331706 | 9.999798e-01 | 1.926531e-07 | 9.999798e-01 | 1.00000000 | 1.9266e-07 |

Worst relative disagreement between the independent evaluation and the closure requirement: **1.31e-06**. They share no input — the first reads `surface-Q.csv`, `eig.csv` and geometry, the second reads `domain-E.csv` — so their agreement is evidence. The closure number is **not** an independent measurement of the port energy.

## 5c. Against the plain rung at the same level

Baseline `COUPLED-LADDER-O1-L2-20260916T080802Z`. the refined run and the baseline differ in exactly one prescribed number, the element size held over the port box, so a frequency difference between them is attributable to port-face resolution and to nothing else.

| baseline mode | refined mode | f baseline (GHz) | f refined (GHz) | Δf (GHz) | Δf rel | Δ\|p\| rel | p_port baseline | p_port refined |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1.461887 | 1.521003 | +0.059116 | 4.044e-02 | 4.551e-04 | 9.985982e-01 | 9.981515e-01 |
| 2 | 2 | 3.885511 | 3.867223 | -0.018289 | 4.707e-03 | 2.861e-01 | 7.803572e-04 | 1.092655e-03 |

DOF 79944 -> 80762; wall clock 81.2 s -> 95.7 s.

the baseline record predates the derived diagnostic, so it was recomputed from that record's own committed surface-Q.csv, config.json and mesh. The baseline record itself is not modified.

## 5d. Is the ladder's frequency movement sensitive to port-face resolution?

Statistic: |delta_f(baseline -> refined)| / |delta_f(L2 -> L3)|, per tracked mode, where the numerator changes only the port box and the denominator changes the whole mesh.

| tracked | role | f(L1,L2,L3) GHz | port-only Δf | global L2→L3 Δf | sensitivity |
|---|---|---|---|---|---|
| L1m1 | LUMPED_DOMINATED | 1.158333, 1.461887, 1.709562 | +0.059116 | +0.247675 | 0.2387 |
| L1m2 | FIELD_DOMINATED | 3.693189, 3.885511, 4.087683 | -0.018289 | +0.202172 | 0.0905 |

- it does not establish convergence, identify a limit or measure an order
- one refined mesh is one point: a large sensitivity says the port face matters, not that resolving it further would settle the frequency
- a small sensitivity does not make the mesh adequate; it relocates the question

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

## 10. What happens next

it carries a size constraint the other rungs do not, so it is excluded from the convergence fit by earlier_rungs()

**STOP — this is a port-refined diagnostic run, not a ladder rung. It is compared against the plain rung at the same level and stops there. A further refined mesh is a separate approval and this script will not start one.**

