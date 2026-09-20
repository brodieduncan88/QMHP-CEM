# Order-1 mesh-refinement check — level 2

Record `COUPLED-LADDER-O1-L2-PO1-20260920T204837Z`. Order-1 mesh-refinement check, one level per invocation, at fixed element order 1 and fixed 0.08 mm halo. Measures whether the discretisation converges, and tests the supported-but-unproven port-stiffness explanation of the energy-balance failures using Palace's own boundary quadrature. NO coupling extraction: no Route A inversion, no g, no charging energy, no capacitance, no circuit parameter. The 250 000-DOF rule, the 45-minute cap and the prospective admission, matching and magnitude rules are unchanged.

> **NOT A REFINEMENT CHECK.** This run carries the port-removed control `PO1-port-removed`: the baseline's mesh file and refinement prescription are reproduced identically and the deviation is one operator term, `Boundaries.LumpedPort[0].Active = false`, i.e. `K → K − K_port`. Deactivating the port also changes, automatically, the auxiliary H1 essential-DOF lists the divergence-free projector uses, so a difference against the baseline is attributable to that pair and not to the operator alone. It is **not** a rung: it must not enter the L1/L2/L3 convergence fit. `E_ind`, `port-EPR.csv` `|p|` and the derived port participation are still written and are **reference diagnostics only** here — they back no term in this run's operator. See `docs/coupled-candidate/po1-port-removed-control.md`.

## 1. Dry runs (offline, no solver)

| level | h_gap (mm) | tetrahedra | DOF order 1 | DOF order 2 | order 1 ≤ 250 000 | order 2 ≤ 250 000 |
|---|---|---|---|---|---|---|
| 2 | 0.006667 | 64434 | 79944 | 420664 | yes | NO |
| 3 | 0.005000 | 120370 | 147372 | 781554 | yes | NO |

The table above is the UNREFINED level prescription, which is what the ladder rungs use. This run adds a local constraint on top of it; its own measured DOF is in section 2 and differs from the level row above.

## 1b. The local refinement this run carries

Approved as **PO1**, refined by **Palace, not gmsh**: 1 `Model.Refinement.Boxes` entry over the loaded mesh.

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
Wall clock 137.6 s, 5.1 % of the 2700 s cap.

| Palace timer | s |
|---|---|
| Total | 137.237 |
| Setup | 0.055 |
| Preconditioner | 6.234 |
| LinearSolve | 6.682 |
| EigenvalueSolve | 2.677 |
| Div.-FreeProjection | 5.139 |

Palace's own timer names. 'Preconditioner' is preconditioner APPLICATION inside the linear solves, not setup; 'Setup' is the separate setup line. The log names no preconditioner type, so none is asserted.

## 3. Admitted modes

| m | f (GHz) | backward error | R | \|R−1\| | \|p\| | disposition |
|---|---|---|---|---|---|---|
| 1 | 3.885828 | 8.72e-17 | 1.000674e+00 | 6.736e-04 | 6.735589e-04 | ADMITTED |
| 2 | 10.841360 | 2.08e-16 | 1.000031e+00 | 3.066e-05 | 3.066128e-05 | ADMITTED |
| 3 | 11.609014 | 2.80e-16 | 1.000060e+00 | 6.024e-05 | 6.023523e-05 | ADMITTED |
| 4 | 15.489998 | 1.76e-14 | 1.000008e+00 | 7.677e-06 | 7.677049e-06 | ADMITTED |
| 5 | 17.781636 | 2.62e-11 | 1.000025e+00 | 2.494e-05 | 2.494004e-05 | ADMITTED |
| 6 | 19.641986 | 4.95e-13 | 1.000021e+00 | 2.115e-05 | 2.115122e-05 | ADMITTED |
| 7 | 23.397631 | 1.83e-11 | 1.000010e+00 | 9.759e-06 | 9.759134e-06 | ADMITTED |
| 8 | 23.817963 | 5.86e-11 | 1.000006e+00 | 6.327e-06 | 6.327161e-06 | ADMITTED |

## 4. Correspondence with level 1 (P2)

Not available: the runs admit different numbers of in-window modes (2 and 1); pairing a prefix would assume which mode is missing, so no comparison is reported

## 5. The port-field test (SUPERSEDED: it calibrates its constant)

Kept because it is the record of what the earlier procedure returned. The number to read is section 5b, whose constant is derived from pinned Palace source and fits nothing.

**NO-FAILING-ROWS** — every computed mode was admitted, so there is nothing to test

κ calibrated from the admitted modes: 5.140397e+01, spread across them 1.3386×.

| m | admitted | reported R | s_t | κ·s_t/f² | restored R | E_ind/E_port |
|---|---|---|---|---|---|---|
| 1 | yes | 1.0007e+00 | 1.8901e-04 | 6.4344e-04 | 1.000643 | 1.0468e+00 |
| 2 | yes | 1.0000e+00 | 6.6939e-05 | 2.9276e-05 | 1.000029 | 1.0473e+00 |
| 3 | yes | 1.0001e+00 | 1.5088e-04 | 5.7549e-05 | 1.000058 | 1.0467e+00 |
| 4 | yes | 1.0000e+00 | 4.5791e-05 | 9.8101e-06 | 1.000010 | 7.8257e-01 |
| 5 | yes | 1.0000e+00 | 1.4648e-04 | 2.3815e-05 | 1.000024 | 1.0473e+00 |
| 6 | yes | 1.0000e+00 | 1.5154e-04 | 2.0191e-05 | 1.000020 | 1.0476e+00 |
| 7 | yes | 1.0000e+00 | 1.0593e-04 | 9.9464e-06 | 1.000010 | 9.8117e-01 |
| 8 | yes | 1.0000e+00 | 6.9782e-05 | 6.3231e-06 | 1.000006 | 1.0006e+00 |

## 5b. Port participation, from a conversion derived from source

`kappa = 1/(t_nd * Ls_nd) = 0.3886882529`, from `Lc = 4.000000e-03 m` measured on this run's own mesh, `L = 1.034567e-07 H`, the port face `0.04 x 0.02 mm` and `t_nd = 0.25`. Nothing is fitted and no solver output is read to form it.

| mode | f (GHz) | p from probes | p reported (E_ind) | p from closure | probe/closure | E_ind/E_port |
|---|---|---|---|---|---|---|
| 1 | 3.885828 | 6.922663e-04 | 6.735589e-04 | 0.000000e+00 | inf | 9.7298e-01 |
| 2 | 10.841360 | 3.149747e-05 | 3.066128e-05 | 0.000000e+00 | inf | 9.7345e-01 |
| 3 | 11.609014 | 6.191672e-05 | 6.023523e-05 | 0.000000e+00 | inf | 9.7284e-01 |
| 4 | 15.489998 | 1.055454e-05 | 7.677049e-06 | 0.000000e+00 | inf | 7.2737e-01 |
| 5 | 17.781636 | 2.562175e-05 | 2.494004e-05 | -1.498961e-10 | -170930.06642454 | 9.7339e-01 |
| 6 | 19.641986 | 2.172332e-05 | 2.115122e-05 | 0.000000e+00 | inf | 9.7366e-01 |
| 7 | 23.397631 | 1.070118e-05 | 9.759134e-06 | 1.498963e-10 | 71390.52440399 | 9.1197e-01 |
| 8 | 23.817963 | 6.802945e-06 | 6.327161e-06 | 4.496887e-10 | 15128.11980977 | 9.3006e-01 |

Worst relative disagreement between the independent evaluation and the closure requirement: **inf**. They share no input — the first reads `surface-Q.csv`, `eig.csv` and geometry, the second reads `domain-E.csv` — so their agreement is evidence. The closure number is **not** an independent measurement of the port energy.

## 5c. Against the plain rung at the same level

Not available: the named baseline is itself refined, and is not a shallower point of this run's own refinement sequence (same region, fewer levels); it is not a baseline

## 5d. Is the ladder's frequency movement sensitive to port-face resolution?

Not available: the baseline comparison is unavailable: the named baseline is itself refined, and is not a shallower point of this run's own refinement sequence (same region, fewer levels); it is not a baseline

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

