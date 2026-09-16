# R1: what refining the port face alone changed

Record: `results/COUPLED-LADDER-O1-L2-R1-20260916T120954Z`
(workflow run 35094133974, commit `96bef92`). Manifest intact; the preserved
pilot record verified untouched by the run itself.

One solve. The plain level-2 rung re-solved with **one prescribed number
changed**: a gmsh `Box` field holding `h_port = 0.003333333333333333 mm` over
the lumped-port rectangle padded by 0.010 mm, blending back to `h_far` over
0.020 mm, combined by `Min` so it can only refine. Geometry, materials,
substrate permittivity, port dimensions, direction, inductance, port
formulation, every boundary condition, the pinned Palace v0.13.0 image, every
solver setting, `h_far`, the halo and the conductor/etch Distance field are the
baseline's.

The mesh hashed to `a49ef282c7f07c56…`, the value the approval record pinned, so
the run solved the approved mesh and nothing else — the driver launches Palace
only on that condition.

| | baseline `L2` | **R1** |
|---|---|---|
| DOF (order 1) | 79 944 | **80 762** (+1.0 %) |
| wall clock | 81.2 s | **95.7 s** (+17.9 %, 3.5 % of the cap) |
| port-face triangles | 25 | **176** |
| element size on the face | 0.008597 mm | **0.003240 mm** (0.97 × requested) |
| elements across the 0.02 mm width | 2.33 | **6.17** |
| max backward error | — | **5.79e-11** |
| admission separation | 4.47 decades | **4.39 decades** |

---

## 1. The answer: partial sensitivity

| tracked mode | role | port-only Δf (+1.0 % DOF) | global L2→L3 Δf (+84 % DOF) | **sensitivity** |
|---|---|---|---|---|
| L1m1 | LUMPED_DOMINATED | **+0.059116 GHz** | +0.247675 GHz | **0.2387** |
| L1m2 | FIELD_DOMINATED | **−0.018289 GHz** | +0.202172 GHz | **0.0905** |

**Port-face resolution accounts for part of the ladder's frequency movement and
not the bulk of it.** Refining only the port box moved the fluxonium-like mode
1.461887 → 1.521003 GHz, which is 23.9 % of what a 1.5× *global* refinement
bought, at 818 extra DOF against 67 428.

The readout-like mode moved **in the opposite direction** to the ladder,
−0.018289 GHz against +0.202172 GHz. Its drift is not port-driven.

**On cost, quote the wall clock, not the DOF.** The +1.0 % DOF figure flatters
the comparison: the added elements are small and cost more than their count
suggests. Measured, R1 bought 0.059116 GHz for +14.5 s where L3 bought
0.247675 GHz for +77.9 s — **3.2× more movement per second**, not the 19.7× the
per-DOF ratio suggests. The per-DOF number is reported here only because DOF is
what the budget rule counts.

Against the predeclared outcomes this is **neither A nor B**: m1 did not move
comparably to its global step, and it did not barely move either — 4.0 %
relative is 590× the frozen `Δf ≤ 1e-4`. It lies between them, closest to a
partial C, with the important qualification that the two modes moved by
different fractions *and in opposite directions*.

## 2. The derived diagnostic held on a mesh it had never seen

`κ = 1/(t_nd·L_s_nd) = 0.3886882529` was derived from pinned Palace v0.13.0
source and the declared port geometry, fitted to nothing, on the L2 and L3
meshes — **before R1 existed**.

| m | f (GHz) | p from probes | p reported (`E_ind`) | p from closure | probe/closure | `E_ind/E_port` |
|---|---|---|---|---|---|---|
| 1 | 1.521003 | 9.981515e-01 | 9.981103e-01 | 9.981515e-01 | 1.00000000 | 0.99996 |
| 2 | 3.867223 | 1.092655e-03 | 1.089944e-03 | 1.092654e-03 | 1.00000131 | 0.99752 |
| 3 | 5.913013 | 9.999815e-01 | 6.603987e-06 | 9.999815e-01 | 1.00000000 | 6.60e-06 |
| 4 | 6.784334 | 9.999773e-01 | 1.364264e-05 | 9.999773e-01 | 1.00000000 | 1.36e-05 |
| 5 | 6.843502 | 9.999774e-01 | 1.444141e-06 | 9.999774e-01 | 1.00000000 | 1.44e-06 |
| 6 | 7.232512 | 9.999742e-01 | 2.753735e-06 | 9.999742e-01 | 1.00000000 | 2.75e-06 |
| 7 | 7.331706 | 9.999798e-01 | 1.926531e-07 | 9.999798e-01 | 1.00000000 | 1.93e-07 |

Worst disagreement between the independent evaluation and the closure
requirement: **1.31e-06**, across all seven modes. The two share no input — the
first reads `surface-Q.csv`, `eig.csv` and geometry, the second reads
`domain-E.csv` — and the closure number is not an independent measurement of the
port energy. Every uniformity factor stays at or below 1, as Cauchy–Schwarz
requires.

The superseded fitted-κ procedure returned **EXPLANATION-2-SUPPORTED** here,
where it returned CALIBRATION-UNSOUND at level 3. Both now agree; the derived
one agrees to 1.31e-06 and needed no modes to calibrate on.

## 3. The strongest corroboration is above the window

The two admitted modes moved modestly. The modes above them changed completely:

| | frequencies (GHz) |
|---|---|
| plain `L2` | 5.088915, 6.039804, 7.177902, 8.706862 (4 modes) |
| **R1** | 5.913013, 6.784334, 6.843502, 7.232512, 7.331706 (5 modes) |

Every one of those has port participation ≈ 0.99998 — they live almost entirely
in the port-face term. Refining that face moved them by hundreds of MHz and
changed how many of them there are. That is direct evidence the port face was
under-resolved, and it is independent of the admitted-mode frequencies the
sensitivity statistic is built from.

## 4. Admission, matching, closure, backward error

| m | disposition | `R` | `\|R−1\|` | backward error |
|---|---|---|---|---|
| 1 | ADMITTED | 0.999958814 | 4.119e-05 | 1.393e-17 |
| 2 | ADMITTED | 0.999997290 | 2.710e-06 | 3.369e-17 |
| 3–7 | REJECTED_ENERGY_BALANCE | ~2.5e-05 | 1.000e+00 | 2.9e-12 … 5.8e-11 |

Matching against the preserved level-1 rung: **MATCHED**, guard applied on both
pairs. Admitted in window: m1, m2. Every backward error is four to fourteen
orders inside the unchanged 1e-6 tolerance. The admission margin, which had
eroded 6.56 → 4.47 → 3.09 decades over the ladder, is **4.39** here.

## 5. What this does not establish

- **No convergence claim.** One refined mesh identifies no limit, measures no
  order, and says nothing about whether refining the face further would settle
  the frequency.
- **A partial sensitivity does not identify the rest.** About three quarters of
  the fluxonium-like mode's movement, and essentially all of the readout-like
  mode's, comes from somewhere this run does not locate.
- **Nothing here bears on the physical architecture.** Every number is about the
  discretisation of a declared idealisation.
- **The opposite sign on the readout-like mode is not explained.** Refining the
  port face pushed it the other way from the ladder; that is a fact of the
  record, not an account of it.

## 6. Disposition

**STOP**, as approved. R1 is a diagnostic run, not a ladder rung: it carries a
size constraint the other rungs do not, so it is excluded from the convergence
fit, and `refinement_trend` refused to publish its confounded movement against
level 1. R2 is prepared and dry-run at 111 238 DOF but is **not approved** and
was not run. No coupling extraction, Route A inversion, Route B, pulse work,
AMD-E or mediator work; the DOF rule, the cap and every tolerance are unchanged.
