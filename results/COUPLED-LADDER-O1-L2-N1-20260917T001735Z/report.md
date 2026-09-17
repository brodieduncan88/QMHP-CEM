# Order-1 mesh-refinement check — level 2

Record `COUPLED-LADDER-O1-L2-N1-20260917T001735Z`. Order-1 mesh-refinement check, one level per invocation, at fixed element order 1 and fixed 0.08 mm halo. Measures whether the discretisation converges, and tests the supported-but-unproven port-stiffness explanation of the energy-balance failures using Palace's own boundary quadrature. NO coupling extraction: no Route A inversion, no g, no charging energy, no capacitance, no circuit parameter. The 250 000-DOF rule, the 45-minute cap and the prospective admission, matching and magnitude rules are unchanged.

## 1. Dry runs (offline, no solver)

| level | h_gap (mm) | tetrahedra | DOF order 1 | DOF order 2 | order 1 ≤ 250 000 | order 2 ≤ 250 000 |
|---|---|---|---|---|---|---|
| 2 | 0.006667 | 64434 | 79944 | 420664 | yes | NO |
| 3 | 0.005000 | 120370 | 147372 | 781554 | yes | NO |

The table above is the UNREFINED level prescription, which is what the ladder rungs use. This run adds a local constraint on top of it; its own measured DOF is in section 2 and differs from the level row above.

## 1b. The local refinement this run carries

Approved as **N1**, refined by **Palace, not gmsh**: 1 `Model.Refinement.Boxes` entry over the loaded mesh.

- `Levels 1` over `[-0.62, -0.125, -0.01]` .. `[-0.58, -0.065, 0.01]` mm

The mesh file is the baseline's, **byte-identical** - it is an input, not a product - so the two meshes are nested and every baseline vertex survives. Refinement is conforming, and its closure refines elements OUTSIDE the box, so this is not a box-only change.

DOF: **79944 loaded -> 84485 solved** (+4541). The loaded count does not bound the solved one; the solved count is read from Palace's own output by the DOF probe.

Mesh `sha256 d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428` - gated against the baseline's before launch.

**This is not a ladder rung.** It carries a refinement the other rungs do not, so it is excluded from the convergence fit and compared against the plain rung at its own level.

## 2. The solve

Status **COMPLETED**, order 1, halo 0.08 mm, 84485 DOF.
Wall clock 923.5 s, 34.2 % of the 2700 s cap.

| Palace timer | s |
|---|---|
| Total | 921.710 |
| Setup | 4.269 |
| Preconditioner | 635.561 |
| LinearSolve | 46.930 |
| EigenvalueSolve | 1.789 |
| Div.-FreeProjection | 146.634 |

Palace's own timer names. 'Preconditioner' is preconditioner APPLICATION inside the linear solves, not setup; 'Setup' is the separate setup line. The log names no preconditioner type, so none is asserted.

## 3. Admitted modes

| m | f (GHz) | backward error | R | \|R−1\| | \|p\| | disposition |
|---|---|---|---|---|---|---|
| 1 | 1.515754 | 3.30e-11 | 9.999886e-01 | 1.137e-05 | 9.982861e-01 | ADMITTED |
| 2 | 3.887132 | 9.76e-12 | 9.999998e-01 | 2.268e-07 | 9.219977e-04 | ADMITTED |
| 3 | 7.232785 | 3.32e-11 | 1.927143e-05 | 1.000e+00 | 6.812764e-08 | REJECTED_ENERGY_BALANCE |
| 4 | 7.878815 | 5.59e-11 | 2.079879e-05 | 1.000e+00 | 2.555286e-07 | REJECTED_ENERGY_BALANCE |
| 5 | 8.632727 | 5.62e-11 | 6.969314e-05 | 9.999e-01 | 7.488690e-06 | REJECTED_ENERGY_BALANCE |
| 6 | 9.521942 | 8.76e-11 | 2.685009e-05 | 1.000e+00 | 2.722895e-07 | REJECTED_ENERGY_BALANCE |

## 4. Correspondence with level 1 (P2)

Matching: **MATCHED**.

| L1 m | L2 m | f_L1 (GHz) | f_L2 (GHz) | Δf | Δ\|p\| | guard | margin |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 1.158333 | 1.515754 | 3.0857e-01 | 2.2413e-04 | APPLIED | 3.32× |
| 2 | 2 | 3.693189 | 3.887132 | 5.2514e-02 | 1.2430e-02 | APPLIED | 6.11× |

## 5. The port-field test (SUPERSEDED: it calibrates its constant)

Kept because it is the record of what the earlier procedure returned. The number to read is section 5b, whose constant is derived from pinned Palace source and fits nothing.

**EXPLANATION-2-SUPPORTED** — the restored balance is 1 to within 1e-2 on every failing row (range 0.999872 to 0.999872): the tangential port field accounts for the missing stiffness, as a genuine eigenpair whose average understates it predicts

κ calibrated from the admitted modes: 5.529776e+01, spread across them 1.0002×.

| m | admitted | reported R | s_t | κ·s_t/f² | restored R | E_ind/E_port |
|---|---|---|---|---|---|---|
| 1 | yes | 9.9999e-01 | 4.1472e-02 | 9.9817e-01 | 0.999872 | 1.0001e+00 |
| 2 | yes | 1.0000e+00 | 2.5196e-04 | 9.2211e-04 | 1.000000 | 9.9988e-01 |
| 3 | no | 1.9271e-05 | 9.4589e-01 | 9.9985e-01 | 0.999872 | 6.8138e-08 |
| 4 | no | 2.0799e-05 | 1.1224e+00 | 9.9985e-01 | 0.999872 | 2.5557e-07 |
| 5 | no | 6.9693e-05 | 1.3474e+00 | 9.9981e-01 | 0.999872 | 7.4901e-06 |
| 6 | no | 2.6850e-05 | 1.6394e+00 | 9.9985e-01 | 0.999872 | 2.7233e-07 |

## 5b. Port participation, from a conversion derived from source

`kappa = 1/(t_nd * Ls_nd) = 0.3886882529`, from `Lc = 4.000000e-03 m` measured on this run's own mesh, `L = 1.034567e-07 H`, the port face `0.04 x 0.02 mm` and `t_nd = 0.25`. Nothing is fitted and no solver output is read to form it.

| mode | f (GHz) | p from probes | p reported (E_ind) | p from closure | probe/closure | E_ind/E_port |
|---|---|---|---|---|---|---|
| 1 | 1.515754 | 9.982975e-01 | 9.982861e-01 | 9.982975e-01 | 0.99999999 | 9.9999e-01 |
| 2 | 3.887132 | 9.222231e-04 | 9.219977e-04 | 9.222244e-04 | 0.99999860 | 9.9976e-01 |
| 3 | 7.232785 | 9.999808e-01 | 6.812764e-08 | 9.999808e-01 | 1.00000000 | 6.8129e-08 |
| 4 | 7.878815 | 9.999795e-01 | 2.555286e-07 | 9.999795e-01 | 1.00000000 | 2.5553e-07 |
| 5 | 8.632727 | 9.999378e-01 | 7.488690e-06 | 9.999378e-01 | 1.00000000 | 7.4892e-06 |
| 6 | 9.521942 | 9.999734e-01 | 2.722895e-07 | 9.999734e-01 | 1.00000000 | 2.7230e-07 |

Worst relative disagreement between the independent evaluation and the closure requirement: **1.40e-06**. They share no input — the first reads `surface-Q.csv`, `eig.csv` and geometry, the second reads `domain-E.csv` — so their agreement is evidence. The closure number is **not** an independent measurement of the port energy.

## 5c. Against the plain rung at the same level

Baseline `COUPLED-LADDER-O1-L2-20260916T080802Z`. the refined run REUSES the baseline's mesh file byte-identically and adds one Model.Refinement.Boxes block. MFEM's conforming refinement only inserts edge midpoints, so every baseline vertex survives and the two meshes are NESTED. A frequency difference between them is therefore attributable to added degrees of freedom in the refined region -- which is NOT the same as the port face: the region is a volume, the conforming closure refines neighbours outside it, and the marked elements are the worst-shaped in the mesh, so element quality is a live alternative explanation this run cannot separate. NOTE the config delta is one block but the SOLVER is not identical: Model.Refinement makes Palace reserve a mesh hierarchy and keep the coarse mesh (geodata.cpp:204-206, 346-349), so this run uses a two-level geometric multigrid preconditioner where the baseline used one. Frequencies are unaffected; the wall-clock comparison is not like-for-like.

| baseline mode | refined mode | f baseline (GHz) | f refined (GHz) | Δf (GHz) | Δf rel | Δ\|p\| rel | p_port baseline | p_port refined |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1.461887 | 1.515754 | +0.053867 | 3.685e-02 | 2.790e-04 | 9.985982e-01 | 9.982975e-01 |
| 2 | 2 | 3.885511 | 3.887132 | +0.001620 | 4.170e-04 | 1.560e-01 | 7.803572e-04 | 9.222231e-04 |

DOF 79944 -> 84485; wall clock 81.2 s -> 923.5 s.

the baseline record predates the derived diagnostic, so it was recomputed from that record's own committed surface-Q.csv, config.json and mesh. The baseline record itself is not modified.

## 5d. Is the ladder's frequency movement sensitive to port-face resolution?

Statistic: |delta_f(baseline -> refined)| / |delta_f(L2 -> L3)|, per tracked mode. This is a RATIO OF OBSERVED FREQUENCY CHANGES between whole runs. It is NOT a causal share and NOT an upper bound on a port contribution: reading it as either would require the numerator to isolate the port (it does not - the box is a volume and the re-mesh is global and non-nested) and an eigenvalue error to decompose additively by mesh region (no such decomposition is available here). Reported as measured; it carries no attribution, and its complement is not 'the rest of the cause'.

| tracked | role | f(L1,L2,L3) GHz | port-only Δf | global L2→L3 Δf | sensitivity |
|---|---|---|---|---|---|
| L1m1 | LUMPED_DOMINATED | 1.158333, 1.461887, 1.709562 | +0.053867 | +0.247675 | 0.2175 |
| L1m2 | FIELD_DOMINATED | 3.693189, 3.885511, 4.087683 | +0.001620 | +0.202172 | 0.0080 |

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

**STOP - this is a refined diagnostic run, not a ladder rung. It is compared against the plain rung at the same level and stops there. A further refined mesh or a further refinement level is a separate approval and this script will not start one.**

