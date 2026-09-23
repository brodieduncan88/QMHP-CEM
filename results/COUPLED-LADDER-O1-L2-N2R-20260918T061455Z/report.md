# Order-1 mesh-refinement check — level 2

Record `COUPLED-LADDER-O1-L2-N2R-20260918T061455Z`. Order-1 mesh-refinement check, one level per invocation, at fixed element order 1 and fixed 0.08 mm halo. Measures whether the discretisation converges, and tests the supported-but-unproven port-stiffness explanation of the energy-balance failures using Palace's own boundary quadrature. NO coupling extraction: no Route A inversion, no g, no charging energy, no capacitance, no circuit parameter. The 250 000-DOF rule, the 45-minute cap and the prospective admission, matching and magnitude rules are unchanged.

## 1. Dry runs (offline, no solver)

| level | h_gap (mm) | tetrahedra | DOF order 1 | DOF order 2 | order 1 ≤ 250 000 | order 2 ≤ 250 000 |
|---|---|---|---|---|---|---|
| 2 | 0.006667 | 64434 | 79944 | 420664 | yes | NO |
| 3 | 0.005000 | 120370 | 147372 | 781554 | yes | NO |

The table above is the UNREFINED level prescription, which is what the ladder rungs use. This run adds a local constraint on top of it; its own measured DOF is in section 2 and differs from the level row above.

## 1b. The local refinement this run carries

Approved as **N2R**, refined by **Palace, not gmsh**: 1 `Model.Refinement.Boxes` entry over the loaded mesh.

- `Levels 2` over `[-0.62, -0.125, -0.01]` .. `[-0.58, -0.065, 0.01]` mm

The mesh file is the baseline's, **byte-identical** - it is an input, not a product - so the two meshes are nested and every baseline vertex survives. Refinement is conforming, and its closure refines elements OUTSIDE the box, so this is not a box-only change.

DOF: **79944 loaded -> 103411 solved** (+23467). The loaded count does not bound the solved one; the solved count is read from Palace's own output by the DOF probe.

Mesh `sha256 d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428` - gated against the baseline's before launch.

`Solver.Linear` also carries an approved override: `MGMaxLevels = 1` (`MGMaxLevels` was unset (Palace default)).

Unchanged alongside it: `KSPType = 'GMRES'`, `MaxIts = 400`, `Tol = 1e-08`, `Type = 'Default'`.

This changes how the operator is preconditioned, not the operator. Comparisons against a baseline solved without it are therefore comparisons of the discretisation, carrying the convergence tolerances as their uncertainty - see the backward error in section 2.

**This is not a ladder rung.** It carries a refinement the other rungs do not, so it is excluded from the convergence fit and compared against the plain rung at its own level.

## 2. The solve

Status **COMPLETED**, order 1, halo 0.08 mm, 103411 DOF.
Wall clock 159.0 s, 5.9 % of the 2700 s cap.

| Palace timer | s |
|---|---|
| Total | 158.690 |
| Setup | 0.055 |
| Preconditioner | 7.905 |
| LinearSolve | 10.240 |
| EigenvalueSolve | 3.632 |
| Div.-FreeProjection | 6.399 |

Palace's own timer names. 'Preconditioner' is preconditioner APPLICATION inside the linear solves, not setup; 'Setup' is the separate setup line. The log names no preconditioner type, so none is asserted.

## 3. Admitted modes

| m | f (GHz) | backward error | R | \|R−1\| | \|p\| | disposition |
|---|---|---|---|---|---|---|
| 1 | 1.526015 | 2.12e-17 | 9.999928e-01 | 7.191e-06 | 9.982169e-01 | ADMITTED |
| 2 | 3.887371 | 4.19e-17 | 9.999999e-01 | 1.111e-07 | 9.385321e-04 | ADMITTED |
| 3 | 10.213998 | 4.52e-13 | 1.586811e-05 | 1.000e+00 | 1.695794e-07 | REJECTED_ENERGY_BALANCE |
| 4 | 10.437862 | 9.53e-12 | 9.322422e-06 | 1.000e+00 | 2.942129e-08 | REJECTED_ENERGY_BALANCE |
| 5 | 10.841525 | 2.52e-14 | 9.999903e-01 | 9.694e-06 | 3.187838e-05 | ADMITTED |
| 6 | 10.997528 | 2.22e-12 | 8.757596e-05 | 9.999e-01 | 3.213212e-06 | REJECTED_ENERGY_BALANCE |
| 7 | 11.217592 | 3.36e-12 | 4.035760e-05 | 1.000e+00 | 1.015989e-06 | REJECTED_ENERGY_BALANCE |
| 8 | 11.609356 | 1.68e-11 | 9.999379e-01 | 6.212e-05 | 6.223817e-05 | ADMITTED |
| 9 | 11.778052 | 5.31e-11 | 7.198253e-05 | 9.999e-01 | 6.310226e-07 | REJECTED_ENERGY_BALANCE |

## 4. Correspondence with level 1 (P2)

Matching: **MATCHED**.

| L1 m | L2 m | f_L1 (GHz) | f_L2 (GHz) | Δf | Δ\|p\| | guard | margin |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 1.158333 | 1.526015 | 3.1742e-01 | 2.9348e-04 | APPLIED | 3.21× |
| 2 | 2 | 3.693189 | 3.887371 | 5.2578e-02 | 5.2524e-03 | APPLIED | 6.08× |

## 5. The port-field test (SUPERSEDED: it calibrates its constant)

Kept because it is the record of what the earlier procedure returned. The number to read is section 5b, whose constant is derived from pinned Palace source and fits nothing.

**INCONCLUSIVE** — the restored balance is neither near 1 nor near the reported value (range 0.81679 to 0.816804)

κ calibrated from the admitted modes: 4.517235e+01, spread across them 1.9981×.

| m | admitted | reported R | s_t | κ·s_t/f² | restored R | E_ind/E_port |
|---|---|---|---|---|---|---|
| 1 | yes | 9.9999e-01 | 4.2032e-02 | 8.1534e-01 | 0.817114 | 1.2243e+00 |
| 2 | yes | 1.0000e+00 | 2.5648e-04 | 7.6667e-04 | 0.999828 | 1.2242e+00 |
| 3 | no | 1.5868e-05 | 1.8863e+00 | 8.1678e-01 | 0.816791 | 2.0762e-07 |
| 4 | no | 9.3224e-06 | 1.9700e+00 | 8.1678e-01 | 0.816790 | 3.6021e-08 |
| 5 | yes | 9.9999e-01 | 8.8354e-05 | 3.3956e-05 | 0.999992 | 9.3881e-01 |
| 6 | no | 8.7576e-05 | 2.1867e+00 | 8.1672e-01 | 0.816804 | 3.9343e-06 |
| 7 | no | 4.0358e-05 | 2.2752e+00 | 8.1676e-01 | 0.816796 | 1.2439e-06 |
| 8 | yes | 9.9994e-01 | 3.0306e-04 | 1.0158e-04 | 0.999977 | 6.1273e-01 |
| 9 | no | 7.1983e-05 | 2.5081e+00 | 8.1673e-01 | 0.816802 | 7.7262e-07 |

## 5b. Port participation, from a conversion derived from source

`kappa = 1/(t_nd * Ls_nd) = 0.3886882529`, from `Lc = 4.000000e-03 m` measured on this run's own mesh, `L = 1.034567e-07 H`, the port face `0.04 x 0.02 mm` and `t_nd = 0.25`. Nothing is fitted and no solver output is read to form it.

| mode | f (GHz) | p from probes | p reported (E_ind) | p from closure | probe/closure | E_ind/E_port |
|---|---|---|---|---|---|---|
| 1 | 1.526015 | 9.982241e-01 | 9.982169e-01 | 9.982241e-01 | 1.00000000 | 9.9999e-01 |
| 2 | 3.887371 | 9.386431e-04 | 9.385321e-04 | 9.386431e-04 | 0.99999995 | 9.9988e-01 |
| 3 | 10.213998 | 9.999843e-01 | 1.695794e-07 | 9.999843e-01 | 1.00000000 | 1.6958e-07 |
| 4 | 10.437862 | 9.999907e-01 | 2.942129e-08 | 9.999907e-01 | 1.00000000 | 2.9422e-08 |
| 5 | 10.841525 | 4.157283e-05 | 3.187838e-05 | 4.157282e-05 | 1.00000013 | 7.6681e-01 |
| 6 | 10.997528 | 9.999156e-01 | 3.213212e-06 | 9.999156e-01 | 1.00000000 | 3.2135e-06 |
| 7 | 11.217592 | 9.999607e-01 | 1.015989e-06 | 9.999607e-01 | 1.00000000 | 1.0160e-06 |
| 8 | 11.609356 | 1.243591e-04 | 6.223817e-05 | 1.243592e-04 | 0.99999930 | 5.0047e-01 |
| 9 | 11.778052 | 9.999286e-01 | 6.310226e-07 | 9.999286e-01 | 1.00000000 | 6.3107e-07 |

Worst relative disagreement between the independent evaluation and the closure requirement: **7.04e-07**. They share no input — the first reads `surface-Q.csv`, `eig.csv` and geometry, the second reads `domain-E.csv` — so their agreement is evidence. The closure number is **not** an independent measurement of the port energy.

## 5c. Against the previous point of this refinement sequence

Baseline `COUPLED-LADDER-O1-L2-N1-20260917T001735Z`. the refined run REUSES the baseline's mesh file byte-identically and adds one Model.Refinement.Boxes block. MFEM's conforming refinement only inserts edge midpoints, so every baseline vertex survives and the two meshes are NESTED. A frequency difference between them is therefore attributable to added degrees of freedom in the refined region -- which is NOT the same as the port face: the region is a volume, the conforming closure refines neighbours outside it, and the marked elements are the worst-shaped in the mesh, so element quality is a live alternative explanation this run cannot separate. NOTE the config delta is one block plus an approved Solver.Linear override (MGMaxLevels=1), which holds the geometric-multigrid hierarchy to 1 level instead of the 1 + levels Model.Refinement would otherwise build (geodata.cpp:204, multigrid.hpp:88). The reserve is the only thing skipped: the refinement flags and the GeneralRefinement call are unchanged, so the mesh and the operators are those of a run without the override. Frequencies are converged to the same tolerances either way, leaving an uncertainty of that order which must be read against the backward error; the wall-clock comparison is not like-for-like.

| baseline mode | refined mode | f baseline (GHz) | f refined (GHz) | Δf (GHz) | Δf rel | Δ\|p\| rel | p_port baseline | p_port refined |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1.515754 | 1.526015 | +0.010261 | 6.770e-03 | 6.937e-05 | 9.982975e-01 | 9.982241e-01 |
| 2 | 2 | 3.887132 | 3.887371 | +0.000239 | 6.150e-05 | 1.762e-02 | 9.222231e-04 | 9.386431e-04 |

DOF 84485 -> 103411; wall clock 923.5 s -> 159.0 s.

**Different preconditioner structure**: 2 multigrid level(s) on the baseline against 1 here. 2 level(s) on the baseline against 1 here, so at one level the preconditioner is applied directly and at more it is demoted to the coarse solver of a V-cycle (ksp.cpp:202). Both runs still converge their own discrete eigenproblem to the same Solver.Eigenmode.Tol and Solver.Linear.Tol, so this changes the path to the solution and not the solution, up to those tolerances - but it does NOT make the wall-clock or iteration-count columns comparable.

## 5e. The refinement sequence

no order is fitted and no continuum limit is extrapolated. The refinement is LOCAL, so even a settling sequence would show local stabilisation, NOT global mesh convergence. These points are excluded from the L1/L2/L3 ladder fit.

| step | role | DOF | mode | Δf (GHz) | Δf rel | p_port derived | p_port reported |
|---|---|---|---|---|---|---|---|
| `COUPLED-LADDER-O1-L2-20260916T080802Z` → `COUPLED-LADDER-O1-L2-N1-20260917T001735Z` | earlier | 79944 → 84485 | m1 | +0.053867 | +3.685e-02 | 0.9982974842395562 | 0.998286122 |
|  |  |  | m2 | +0.001620 | +4.170e-04 | 0.0009222231179999545 | 0.0009219976519 |
| `COUPLED-LADDER-O1-L2-N1-20260917T001735Z` → `this run` | **primary** | 84485 → 103411 | m1 | +0.010261 | +6.770e-03 | 0.9982240665686236 | 0.9982168757 |
|  |  |  | m2 | +0.000239 | +6.150e-05 | 0.0009386430907077909 | 0.000938532088 |

`p_port derived` is from the boundary quadrature; `p_port reported` is Palace's rank-one surrogate. They are different quantities and are not interchangeable.

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

**STOP - this is a refined diagnostic run, not a ladder rung. It is compared against the plain rung at the same level and stops there. A further refined mesh or a further refinement level is a separate approval and this script will not start one.**

