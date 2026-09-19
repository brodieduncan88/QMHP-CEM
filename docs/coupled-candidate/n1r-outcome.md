# N1R outcome — the control held, and it bounds the solver-path effect

Record: `results/COUPLED-LADDER-O1-L2-N1R-20260919T110053Z`.
Workflow run 35438882836. Approval commit `77f0659`; machinery `9e323d4`.
Offline comparison: `experiments/N1R-controlled-preconditioner/controlled-comparison.json`.

## 1. Execution

**COMPLETED in 110.7 s — 4.1 % of the unchanged 2,700 s cap**, against N1's 923.5 s on the
identical discrete problem: **8.34× faster**.

Every pre-declaration held exactly, including two the N2R run could not test:

| | predicted | measured |
|---|---|---|
| finest ND(p=1) DOF | 84,485 | **84,485** |
| DOF added by refinement | +4,541 | **+4,541** |
| mesh V / E / F / T | 14,667 / 84,485 / 138,118 / 68,299 | **identical** |
| `Parallel Mesh Stats` blocks | 1, un-prefixed | **1** |
| multigrid hierarchy | `Level 0` only | **Level 0 only, 84,485 unknowns** |

Probe: one unambiguous count at 1.73 s, 33.8 % of the 250,000 rule, not refused. Max backward
error 2.532e-11, inside the unchanged 1e-6. `Rebalancing` 0.000 s. No post-solve failure.

## 2. The solver-path effect, measured

N1 and N1R solve the **same discrete problem**: the offline check reads both solved `config.json`
files and finds they differ in `Solver.Linear.MGMaxLevels` and nothing else, on the same mesh hash,
the same box and the same solved DOF. Every difference below is therefore solver path.

| | N1 (2 levels) | N1R (1 level) | Δf (GHz) | Δf rel | Δ\|p\| rel |
|---|---|---|---|---|---|
| m1 | 1.515754 | 1.515754 | −7.0e-09 | **4.618e-09** | 2.104e-09 |
| m2 | 3.887132 | 3.887132 | −3.0e-09 | **7.718e-10** | 3.142e-07 |

That is **21,654× and 129,567× below** the frozen `Δf ≤ 1e-4` relative tolerance, and **6 to 7
orders of magnitude below** the movements it could have confounded (`8.0e+06×` smaller than the
L2 → N1R step, `1.5e+06×` smaller than N1R → N2R).

`n2r-outcome.md` §5 said the N1 → N2R frequency difference was "an observed difference between two
runs that also differ in preconditioner", not certified free of solver-path effects, because no
measurement bounded that. **This is the measurement.** The bound is ~5e-09 relative, so those
movements are refinement effects to six significant figures.

## 3. The controlled sequence

With N1R on disk every step runs one multigrid level — `same_on_both_sides` is true throughout.

| step | levels | m1 Δf rel | m2 Δf rel |
|---|---|---|---|
| original L2 → N1R | 1 → 1 | 3.684760e-02 | 4.170440e-04 |
| **N1R → N2R** (primary) | 1 → 1 | **6.7698e-03** | **6.1506e-05** |
| successive ratio | | 5.443 | 6.781 |

Against the uncontrolled sequence in `n2r-outcome.md` §4 — L2 → N1 then N1 → N2R, which crossed
two preconditioner changes — the figures are **5.443 / 6.781 either way**, and the per-step values
agree to six significant figures (`3.684761e-02` vs `3.684760e-02`; `4.170447e-04` vs
`4.170440e-04`). Participation agrees likewise: `2.78992134e-04` vs `2.78994237e-04` on m1,
`1.56038155e-01` vs `1.56037890e-01` on m2.

So the control **confirms rather than revises** the reported sequence. Both tracked modes still
move less at the second level than the first, by 5.4× and 6.8×, and that is still an observation
and not an order of convergence: two steps, a local refinement, no uniform h ratio.

## 4. The diagnosis again, at a third problem size

| | L2 | N1 | **N1R** | N2 | N2R |
|---|---|---|---|---|---|
| finest DOF | 79,944 | 84,485 | **84,485** | 103,411 | 103,411 |
| multigrid levels | 1 | 2 | **1** | 3 | 1 |
| GMRES its / solve | 1.00 | 15.37 | **2.00** | 20.05 | 2.00 |
| Preconditioner (s) | 3.253 | 635.561 | **5.910** | — killed | 7.905 |
| `CoarseSolve` calls | 0 | 622 | **0** | — | 0 |
| Div.-Free (s) | 2.401 | 146.634 | **4.754** | — | 6.399 |
| total (s) | 78.524 | 921.710 | **110.392** | >2700 | 158.690 |

On the identical problem N1 solved: preconditioner time **107.5× lower**, cost per application
**19.7× lower** (1.0218 s → 0.0518 s), divergence-free projection **30.8× lower**, `CoarseSolve`
called **zero** times. Estimation and disk I/O are 78.3 % of the run, the same domination
`n2-runtime-diagnosis.md` §8 predicted and N2R first showed.

## 5. What this establishes, and what it does not

**Established.** That the solver-path contribution to the tracked frequencies and participations is
~5e-09 relative — four orders below the frozen tolerance — so the L2 → N1 → N2 refinement movements
reported across this campaign are refinement effects, not artefacts of the preconditioner that
changed alongside them. And that the diagnosis holds at a third problem size.

**Not established, and not claimed.** Any order of convergence or continuum limit. Global mesh
convergence — the refinement is local. Causal attribution to the port face. That the tracked pair
has converged: m1's N1R → N2R movement is still 68× the frozen relative tolerance. Anything about
the physics N1 was not already approved to ask.

N1's record stands unmodified; N1R is a separate run under a separate approval, and the comparison
is computed offline from both.

**STOP as approved.** One control run was made and it completed.
