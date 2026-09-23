# Order-1 mesh-refinement check — level 2

Record `COUPLED-LADDER-O1-L2-N2-20260917T103405Z`. Order-1 mesh-refinement check, one level per invocation, at fixed element order 1 and fixed 0.08 mm halo. Measures whether the discretisation converges, and tests the supported-but-unproven port-stiffness explanation of the energy-balance failures using Palace's own boundary quadrature. NO coupling extraction: no Route A inversion, no g, no charging energy, no capacitance, no circuit parameter. The 250 000-DOF rule, the 45-minute cap and the prospective admission, matching and magnitude rules are unchanged.

## 1. Dry runs (offline, no solver)

| level | h_gap (mm) | tetrahedra | DOF order 1 | DOF order 2 | order 1 ≤ 250 000 | order 2 ≤ 250 000 |
|---|---|---|---|---|---|---|
| 2 | 0.006667 | 64434 | 79944 | 420664 | yes | NO |
| 3 | 0.005000 | 120370 | 147372 | 781554 | yes | NO |

The table above is the UNREFINED level prescription, which is what the ladder rungs use. This run adds a local constraint on top of it; its own measured DOF is in section 2 and differs from the level row above.

## 1b. The local refinement this run carries

Approved as **N2**, refined by **Palace, not gmsh**: 1 `Model.Refinement.Boxes` entry over the loaded mesh.

- `Levels 2` over `[-0.62, -0.125, -0.01]` .. `[-0.58, -0.065, 0.01]` mm

The mesh file is the baseline's, **byte-identical** - it is an input, not a product - so the two meshes are nested and every baseline vertex survives. Refinement is conforming, and its closure refines elements OUTSIDE the box, so this is not a box-only change.

DOF: **79944 loaded -> 103411 solved** (+23467). The loaded count does not bound the solved one; the solved count is read from Palace's own output by the DOF probe.

Mesh `sha256 d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428` - gated against the baseline's before launch.

**This is not a ladder rung.** It carries a refinement the other rungs do not, so it is excluded from the convergence fit and compared against the plain rung at its own level.

## 2. The solve

Status **TIMEOUT**, order 1, halo 0.08 mm, 103411 DOF.
Wall clock 2700.1 s, 100.0 % of the 2700 s cap.

## 3. Admitted modes

## 4. Correspondence with level 1 (P2)

Not available: this rung is TIMEOUT

## 5. The port-field test (SUPERSEDED: it calibrates its constant)

Kept because it is the record of what the earlier procedure returned. The number to read is section 5b, whose constant is derived from pinned Palace source and fits nothing.

Not available: this run produced no solve

## 5c. Against the plain rung at the same level

Not available: this run is TIMEOUT

## 5e. The refinement sequence

no order is fitted and no continuum limit is extrapolated. The refinement is LOCAL, so even a settling sequence would show local stabilisation, NOT global mesh convergence. These points are excluded from the L1/L2/L3 ladder fit.

| step | role | DOF | mode | Δf (GHz) | Δf rel | p_port derived | p_port reported |
|---|---|---|---|---|---|---|---|
| `COUPLED-LADDER-O1-L2-20260916T080802Z` → `COUPLED-LADDER-O1-L2-N1-20260917T001735Z` | earlier | 79944 → 84485 | m1 | +0.053867 | +3.685e-02 | 0.9982974842395562 | 0.998286122 |
|  |  |  | m2 | +0.001620 | +4.170e-04 | 0.0009222231179999545 | 0.0009219976519 |
| `COUPLED-LADDER-O1-L2-N1-20260917T001735Z` → `this run` | **primary** | — | — | — | — | — | *this run is TIMEOUT* |

`p_port derived` is from the boundary quadrature; `p_port reported` is Palace's rank-one surrogate. They are different quantities and are not interchangeable.

## 5d. Is the ladder's frequency movement sensitive to port-face resolution?

Not available: the baseline comparison is unavailable: this run is TIMEOUT

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

## 9b. Why this run did not produce a solve

the solve did not finish inside the 2700 s cap

## 10. What happens next

it carries a size constraint the other rungs do not, so it is excluded from the convergence fit by earlier_rungs()

**STOP - this is a refined diagnostic run, not a ladder rung. It is compared against the plain rung at the same level and stops there. A further refined mesh or a further refinement level is a separate approval and this script will not start one.**

