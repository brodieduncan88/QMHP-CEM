# N2R outcome — the rescue completed, and the comparison N2 could not deliver

Record: `results/COUPLED-LADDER-O1-L2-N2R-20260918T061455Z`.
Workflow run 35313973073. Approval commit `581e93f`; machinery `44c25d4`.

## 1. Execution

**COMPLETED in 159.0 s — 5.9 % of the unchanged 2,700 s cap.** N2 timed out at
2,700.1 s on the identical discrete problem, so the same mathematics finished
**17.0× faster** for one added config key.

| | value | pre-declared? |
|---|---|---|
| status | COMPLETED | — |
| finest ND(p=1) DOF | **103,411** | yes, exactly |
| within the 250,000 rule | YES, 41.4 % of it | yes |
| DOF probe | one unambiguous count at 2.16 s, not refused | yes |
| wall clock | 159.0 s (5.9 % of cap) | **no — no runtime was predicted** |
| max backward error | 5.311e-11, inside the unchanged 1e-6 | — |
| refinement took effect | yes, +23,467 DOF over the loaded mesh | — |
| post-solve analysis | no failure; manifest intact | — |

Every falsifiable pre-declaration held:

* Palace printed a **single un-prefixed `Parallel Mesh Stats` block** — the shape
  `geodata.cpp:394-400` gives when `mesh.size() == 1` — where N2 printed a
  `Coarse` and a `Refined` block.
* Its counts were **17,447 / 103,411 / 170,410 / 84,445** (V/E/F/T), N2's finest
  mesh exactly. (`V − E + F − T = 1`, necessary but not sufficient; the mesh-hash
  gate plus the identical box is what guarantees it.)
* `ND (p = 1): 103411` on the header line the probe reads.
* The multigrid hierarchy printed **Level 0 only, 103,411 unknowns** — one level.
* The `Rebalancing` timer reads **0.000 s**: `RebalanceMesh` fired on this branch,
  as it only can when `capacity() == 1`, and was inert at one rank exactly as
  `geodata.cpp:1445-1448` said it would be.

## 2. The diagnosis, confirmed by measurement

| | L2 baseline | N1 | N2 | **N2R** |
|---|---|---|---|---|
| finest DOF | 79,944 | 84,485 | 103,411 | **103,411** |
| multigrid levels | 1 | 2 | 3 | **1** |
| GMRES iterations / solve | 1.00 | 15.37 | 20.05 | **2.00** |
| Preconditioner (s) | 3.253 | 635.561 | — killed | **7.905** |
| `CoarseSolve` calls | 0 | 622 | — | **0** |
| Div.-Free Projection (s) | 2.401 | 146.634 | — | **6.399** |
| total (s) | 78.524 | 921.710 | >2700 | **158.690** |

Against N1, on a problem 22 % *larger*: preconditioner time **80× lower**, cost
per application **15.5× lower** (1.0218 s → 0.0659 s), divergence-free projection
**22.9× lower**, and `CoarseSolve` called **zero** times — there is no V-cycle to
have a coarse level. That is `ksp.cpp:202` returning the preconditioner directly,
which is what the diagnosis said the one key would do.

The prediction in `n2-runtime-diagnosis.md` §8 also held: with the solver fixed,
the run is dominated by the parts a preconditioner change does not touch.
**Estimation and disk I/O are now 77.4 % of the total** (122.9 s of 158.7 s);
the whole linear-solver stack is 15.5 %.

## 3. Primary comparison — N1 → N2R

Available. Matching **MATCHED** under the unchanged rule
`qmhp-cem.mode-matching/0.1.1`; in-window admitted set `{1, 2}` on both sides.

| | f N1 (GHz) | f N2R (GHz) | Δf (GHz) | Δf rel | Δ\|p\| rel |
|---|---|---|---|---|---|
| m1 | 1.515754 | 1.526015 | +0.010261 | 6.770e-03 | 6.937e-05 |
| m2 | 3.887132 | 3.887371 | +0.000239 | 6.150e-05 | 1.762e-02 |

Against the frozen criteria — **reported, not gating**, and both **relative and
dimensionless**:

* `Δf ≤ 1e-4`: m1 is **67.7× above** it; m2 is **0.62×**, i.e. below.
* `Δ|p| ≤ 1e-2`: m1 is **0.0069×**, below; m2 is **1.76× above**.

## 4. The sequence

| step | m1 Δf rel | m2 Δf rel |
|---|---|---|
| original L2 → N1 | 3.6848e-02 | 4.1704e-04 |
| **N1 → N2R** (primary) | **6.7697e-03** | **6.1505e-05** |
| successive ratio | 5.44 | 6.78 |

Both tracked modes moved less at the second level than at the first, by a factor
of 5.4 and 6.8. **That is an observation, not an order of convergence.** Two
steps cannot establish one; the refinement is local, so no global mesh
convergence follows; the steps do not share a uniform h ratio; and the two runs
did not use the same preconditioner (below). Nothing about a continuum limit is
claimed, and m1 remains 68× above the frozen relative tolerance.

## 5. What this comparison is not

**It is not preconditioner-controlled, and the record says so.** N1 ran a
two-level V-cycle; N2R ran one level with the preconditioner applied directly.
The driver now derives multigrid depth from each record and discloses any step
that crosses a change — including `L2 → N1`, which crossed one too (1 level → 2)
and had never been flagged.

**This was subsequently measured.** N1R re-solved N1's problem with N2R's one-level configuration;
N1 vs N1R differ in `Solver.Linear.MGMaxLevels` and nothing else, and their tracked frequencies
differ by **4.618e-09** and **7.718e-10** relative — four orders below the frozen tolerance and six
below the movements below. The Δf figures in §3 are therefore refinement effects to six significant
figures, and the controlled sequence reproduces them. See [`n1r-outcome.md`](n1r-outcome.md).

Neither of Palace's error columns bounds the resulting uncertainty:
`ErrorType::ABSOLUTE` is the raw residual norm and `BACKWARD` divides it by
`‖K‖ + |λ|‖M‖` (`slepc.cpp:473-484`), so neither is a frequency without an
eigenvalue condition number that is not computed. The Δf figures above are
therefore **observed differences between two runs that also differ in
preconditioner**, not measurements of refinement alone. What *is* enforced is the
unchanged 1e-6 backward-error tolerance, met at 5.31e-11.

Two visible solver-side effects, reported rather than smoothed over:

* **Q and Im{f} collapse to round-off.** m1/m2 backward errors are 2.1e-17 and
  4.2e-17 (N1: 3.3e-11, 9.8e-12) and Q reads 3.07e14 / 4.83e15 (N1: 1.14e10 /
  2.12e10). The model is lossless, so Im{f} *should* be zero; an exact inverse
  gets closer to it than a V-cycle does. Q is not a tracked quantity here.
* **The modes above the tracked pair differ** — N2R's are all above 10 GHz where
  N1's were 7.23–9.52. This is not new and is not attributable to the rescue:
  **no two runs in this campaign have ever shared a higher mode.** L2 gave
  5.09/6.04/7.18/8.71, R1 gave 5.91/6.78/6.84/7.23/7.33, N1 gave
  7.23/7.88/8.63/9.52. Only m1 and m2 have ever been stable, which is why they
  are the tracked pair and why the band stops at 9.0 GHz.

## 6. Diagnostics

The **derived** port conversion — the one built from source rather than fitted —
reproduces the energy closure on a mesh it had never seen to
**1.00000000** (m1) and **0.99999995** (m2). That is its best agreement in the
campaign.

The **superseded fitted-κ** test moved from `EXPLANATION-2-SUPPORTED` to
`INCONCLUSIVE`, with κ spread 1.0002 → 1.998. The cause is the admitted set, not
the port: admission grew from 2 modes to 4, and the two additions sit at 10.84
and 11.61 GHz, outside the declared 0.5–9.0 GHz window. On the tracked pair the
fitted κ is unchanged to four figures — 55.304 / 55.291 (N1) against
55.304 / 55.298 (N2R). The test that superseded it is the one quoted above.

## 7. What is established, and what is not

**Established.** That N2's discrete problem is solvable inside the cap on this
runner, and that its timeout was a preconditioner artefact rather than a property
of the mesh or the DOF count — 103,411 DOF, the same mesh to four independent
counts, 159.0 s against 2,700.1 s. And the N1 → N2R frequency and participation
differences above, as observed differences.

**Not established, and not claimed.** Any order of convergence or continuum
limit. Global mesh convergence — the refinement is local. Causal attribution to
the port face. That the tracked pair has converged: m1's movement is still 68×
the frozen relative tolerance. That the movement is refinement alone, since the
step crosses a preconditioner change. Anything about the physics that N2 was not
already approved to ask.

N2's TIMEOUT stands as recorded in `n2-outcome.md`. N2R does not replace it and
does not reinterpret it; it is a separate run under a separate approval.

**STOP as approved.** One rescue attempt was made and it completed. A third
refinement level, R2, another solver setting or a second attempt are each a
separate approval.
