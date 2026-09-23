# R1: one local refinement, and why it does not attribute a cause

> **What R1 established:** it changed the frequencies. **What it did not
> establish:** why. The refinement was applied to a *volume*, and the mesh was
> regenerated non-nested, so no clean causal attribution to the port face is
> available from this run. **The numerical convergence the ladder was meant to
> demonstrate remains unestablished.**
>
> Every *measured* number in this record reproduced independently — frequencies
> and deltas to the last printed digit, `κ` bit-identically from the raw mesh and
> config, `p_port` to ~1e-15. The measurements were never in question. The first
> write-up's *interpretation* was, and is corrected here. §6 lists what was
> withdrawn and keeps the original wording.

Record: `results/COUPLED-LADDER-O1-L2-R1-20260916T120954Z`
(workflow run 35094133974, commit `96bef92`). Manifest intact; the preserved
pilot record verified untouched by the run itself.

One solve. The plain level-2 rung re-solved with one prescribed number changed:
a gmsh `Box` field holding `h_port = 0.003333333333333333 mm` over the
lumped-port rectangle padded by 0.010 mm, blending back to `h_far` over
0.020 mm, combined by `Min`. Geometry, materials, substrate permittivity, port
dimensions, direction, inductance, port formulation, every boundary condition,
the pinned Palace v0.13.0 image, every solver setting, `h_far`, the halo and the
conductor/etch Distance field are the baseline's. The mesh hashed to
`a49ef282c7f07c56…`, the value the approval pinned, so the run solved the
approved mesh and nothing else.

**Two properties of that prescription defeat causal attribution**, and both are
measured, not argued:

- **The refined region is a volume, not the port face.** `PortRefinement.box_mm`
  pads ±0.010 mm in `z` as well as `x` and `y`, so the constraint covers a
  0.040 × 0.060 × 0.020 mm box straddling the chip surface, blending 0.020 mm
  further. This is a defect in code written for this experiment.
- **The two meshes are not nested.** `config.json` is byte-identical, but gmsh
  re-meshed globally: **18.4 % of the baseline's 13 991 nodes (2 571) are absent
  from R1**, at a median 1.37 mm and a maximum 3.32 mm from the port. No
  replicate establishes the re-meshing noise floor.

**Where the withdrawn wording still lives.** Records are written once and never
modified — that is what makes them evidence. The committed record states in its
own `summary.json` (`baseline_comparison.why_this_comparison`, line 207) and
`report.md` line 97 that a frequency difference is *"attributable to port-face
resolution and to nothing else"*. **That is withdrawn by this document.** The
approval record `.github/ladder-approval.json` carries the same framing and is
also left untouched, for a second reason: committing that file on a `palace/**`
branch is what *starts* a solve.

---

## 1. What was measured

| tracked mode | role | Δf (baseline → R1) | Δf (L2 → L3) | ratio |
|---|---|---|---|---|
| L1m1 | LUMPED_DOMINATED | **+0.059116 GHz** | +0.247675 GHz | 0.2387 |
| L1m2 | FIELD_DOMINATED | **−0.018289 GHz** | +0.202172 GHz | 0.0905 |

**Those two ratios are ratios of observed frequency changes between whole runs.
They are not causal shares, and they are not upper bounds on a port
contribution.** Reading them as either requires assuming the numerator isolates
the port and that an eigenvalue discretisation error decomposes additively by
mesh region. Neither holds here: the numerator refines a volume and triggers a
global re-mesh, and no such decomposition theorem is available. The ratios are
reported because they are what was measured; they carry no attribution.

**The opposite sign on mode 2 does not falsify port involvement.** Mode 2 moved
−0.018289 GHz where mode 1 moved +0.059116 GHz, and a first-order perturbation
through a positive-definite stiffness term would scale with each mode's port
participation (`p₂/p₁ = 7.81e-04`) and preserve sign. But that argument applies
to changing one stiffness coefficient **on a fixed discretisation**. R1 changed
the discretisation itself, over a volume and non-nested. A sign flip under
re-meshing is ordinary and rules nothing out. An earlier version of this
document treated it as a falsification; that reading is withdrawn.

### Port-face resolution: count is not resolution

| | port-face triangles | face area | mean edge | √(area/n) |
|---|---|---|---|---|
| baseline `L2` | 25 | 0.000800 mm² | 0.008453 mm | 0.005657 mm |
| **R1** | **176** | 0.000800 mm² | **0.003261 mm** | **0.002132 mm** |
| `L3` | 45 | 0.000800 mm² | 0.006266 mm | 0.004216 mm |

R1 carries **3.91× L3's triangle count**, which is a *count* ratio. The
corresponding **linear** resolution ratio is **1.92×** by mean edge (1.98× by
√(area/n); √3.91 = 1.98, as a 2-D count ratio requires). Earlier text quoted
"3.91× finer", conflating the two. The honest statement is that R1's port face
is about **twice** as finely resolved as L3's in linear measure, on an identical
face area.

Alongside that, the face's normal-field energy fraction `p_MA/p_Default` — the
two `surface-Q.csv` probes differ by exactly the tangential term `½·t·|E_t|²` —
is 0.006402 (baseline), 0.105803 (R1), 0.100041 (L3) for mode 1. R1 reaches a
value close to L3's while its mode-1 frequency, 1.521003 GHz, sits 0.188559 GHz
*below* L3's 1.709562 GHz. That is a measured juxtaposition. **It does not
establish that the port is a minority contributor, nor that the bulk mesh
accounts for the remainder** — R1 cannot separate the port neighbourhood from
the global re-mesh that accompanied it, and this record does not locate the rest
of the ladder's movement or bound it.

## 2. The derived diagnostic, and what its agreement does and does not show

`κ = 1/(t_nd·L_s_nd) = 0.3886882529` was derived from pinned Palace v0.13.0
source and the declared port geometry, fitted to nothing.

| m | f (GHz) | p from probes | p reported (`E_ind`) | p from closure | probe/closure | `E_ind/E_port` |
|---|---|---|---|---|---|---|
| 1 | 1.521003 | 9.981515e-01 | 9.981103e-01 | 9.981515e-01 | 1.00000000 | 0.99996 |
| 2 | 3.867223 | 1.092655e-03 | 1.089944e-03 | 1.092654e-03 | 1.00000131 | 0.99752 |
| 3 | 5.913013 | 9.999815e-01 | 6.603987e-06 | 9.999815e-01 | 1.00000000 | 6.60e-06 |
| 4 | 6.784334 | 9.999773e-01 | 1.364264e-05 | 9.999773e-01 | 1.00000000 | 1.36e-05 |
| 5 | 6.843502 | 9.999774e-01 | 1.444141e-06 | 9.999774e-01 | 1.00000000 | 1.44e-06 |
| 6 | 7.232512 | 9.999742e-01 | 2.753735e-06 | 9.999742e-01 | 1.00000000 | 2.75e-06 |
| 7 | 7.331706 | 9.999798e-01 | 1.926531e-07 | 9.999798e-01 | 1.00000000 | 1.93e-07 |

Worst *relative* disagreement between the independent evaluation and the closure
requirement: **1.31e-06**. That is mode 2's, and it is the weakest mode's
constraint rather than a characterisation of the test's precision: in **absolute**
terms the disagreements run **1.9e-11 to 1.75e-09** across all seven modes, and
mode 2's relative figure is large only because `p₂ = 1.09e-03` is small. The
signs are mixed, which bounds a multiplicative error in `κ` at **|δ| ≲ 2e-10** —
a much stronger statement than the headline. The two share no input — the
first reads `surface-Q.csv`, `eig.csv` and geometry, the second reads
`domain-E.csv` — and the closure number is not an independent measurement of the
port energy. Every uniformity factor stays at or below 1, as Cauchy–Schwarz
requires.

The superseded fitted-κ procedure returned **EXPLANATION-2-SUPPORTED** here,
where it returned CALIBRATION-UNSOUND at level 3. Both now agree; the derived
one agrees to 1.31e-06 and needed no modes to calibrate on.

## 3. Above the window: real eigenpairs, and a mode count that is a solver artifact

The two admitted modes moved modestly. The modes above them changed completely:

| | frequencies (GHz) |
|---|---|
| plain `L2` | 5.088915, 6.039804, 7.177902, 8.706862 (4 modes) |
| **R1** | 5.913013, 6.784334, 6.843502, 7.232512, 7.331706 (5 modes) |

Every one of those has port participation ≈ 0.99998 from the probes, confirmed
by the closure route to a ratio of 1.000000000, with `E_mag/E_elec` of 1.9e-05 to
2.6e-05. They are **genuine eigenpairs** whose entire stiffness is the port
boundary term; the admission rule rejects them only because it measures the
balance with the `E_ind` surrogate, which reports `|p| ~ 1e-05` to `1e-07` for
them. Their uniformity factor is five to seven orders below 1.

## 4. Admission, matching, closure, backward error

| m | disposition | `R` | `\|R−1\|` | backward error |
|---|---|---|---|---|
| 1 | ADMITTED | 0.999958814 | 4.119e-05 | 1.393e-17 |
| 2 | ADMITTED | 0.999997290 | 2.710e-06 | 3.369e-17 |
| 3–7 | REJECTED_ENERGY_BALANCE | ~2.5e-05 | 1.000e+00 | 2.9e-12 … 5.8e-11 |

Matching against the preserved level-1 rung: **MATCHED**, guard applied on both
pairs, with separation margins of 19.84× and 64.14×. The two orderings the rule
forms agree *by construction* here — inside each run `|p|` and frequency induce
the same order — so it is the separation guard that carries the correspondence,
as the rule's own text says. Admitted in window: m1, m2. Every backward error is
four to fourteen orders inside the unchanged 1e-6 tolerance.

**Port refinement made the admitted modes' closure slightly worse**, and that is
worth stating plainly: m1's defect went `3.350854e-05 → 4.118581e-05` (**+22.9 %**)
and m2's `2.226681e-06 → 2.709717e-06`. That is the whole reason the admission
separation margin fell from the baseline's **4.4748** to **4.3852** decades.

## 5. What this does not establish

- **No convergence claim.** One refined mesh identifies no limit and measures no
  order. **The numerical convergence the ladder was meant to demonstrate remains
  unestablished**, and R1 does not advance it.
- **No causal attribution.** The refined region is a volume and the meshes are
  not nested, so the frequency movement cannot be assigned to the port face, to
  the port neighbourhood, or to the bulk mesh. The 0.2387 and 0.0905 ratios
  describe what moved, not why.
- **No minority-contributor finding.** R1 does not show the port is a small
  contributor, nor that the remainder lies elsewhere. It does not locate the
  remainder at all.
- **Nothing here bears on the physical architecture.** Every number is about the
  discretisation of a declared idealisation.
- **The opposite sign on mode 2 is unexplained**, and is left that way: it is a
  fact of the record, and re-meshing is a sufficient candidate explanation
  without invoking the port.
- **The port-face field integral is not converged even at 176 triangles.**
  `p_Default` for mode 1 climbs 3.884e-02 (L2) → 4.669e-02 (R1) → 5.862e-02 (L3).
  The *ratio* `p_MA/p_Default` has settled while the absolute integral has not;
  only the ratio is described as settled.
- **Port refinement made the admitted modes' closure worse.** m1's defect went
  `3.350854e-05 → 4.118581e-05` (+22.9 %), which is why the admission separation
  fell from the baseline's 4.4748 to 4.3852 decades. R1 is a level-2 run, so
  level 2 is the like-for-like comparison; R1 says nothing about level 3's value.
- **The window ceiling matters.** At 10 or 12 GHz, L1 and L3 admit three modes
  against L2 and R1's two, which the matching rule refuses as a count mismatch.
- **The frozen tolerances are exceeded**: `Δf` relative by 404× on m1 and 47× on
  m2; `Δ|p|` by 29× on m2. The comparison gates nothing.

## 6. Disposition

**STOP**, as approved. R1 is a diagnostic run, not a ladder rung: it carries a
size constraint the other rungs do not, so it is excluded from the convergence
fit, and `refinement_trend` refused to publish its confounded movement against
level 1. R2 is prepared and dry-run at 111 238 DOF but is **not approved** and
was not run. No coupling extraction, Route A inversion, Route B, pulse work,
AMD-E or mediator work; the DOF rule, the cap and every tolerance are unchanged.

## 7. What was withdrawn

The first write-up of this record was faulted by independent readings and by the
owner's review. The measurements were not; every one reproduced. The withdrawn
wording is kept here so no reader meets a claim without its correction.

| withdrawn wording | why | what replaces it |
|---|---|---|
| *"Port-face resolution accounts for part of the ladder's frequency movement and not the bulk of it"* | asserts a regional decomposition of an eigenvalue error | R1 changed the frequencies; the cause is not attributable (§1) |
| *"23.9 % of what a 1.5× global refinement bought"* | L2→L3 is **1.333×**, not 1.5×; and the quotient is not a share | the two ratios, reported as ratios (§1) |
| *"the remaining ~76 % comes from elsewhere"* | the complement of a ratio is not a located quantity | this record does not locate the remainder (§5) |
| *"19.7× more frequency movement per DOF"* | eigenvalue response is not linear in DOF | withdrawn, not replaced |
| *"3.2× more movement per second"* | arithmetically wrong: 4.08e-3 vs 3.18e-3 GHz/s is **1.28×** | withdrawn, not replaced |
| *"The derived diagnostic held on a mesh it had never seen"* | `κ` depends on the mesh only through two bounding boxes an interior field cannot change, so it is identical by construction | the probe-to-closure agreement is a real check of the conversion, not of `κ` (§2) |
| *"The strongest corroboration is above the window"*, *"direct evidence the port face was under-resolved"* | the 4→5 mode-count change is a SLEPc `nconv` artifact (6 of 6 requested at baseline, 7 of 6 at R1) | §3, which records the rows and claims nothing from them |
| *"The admission margin, which had eroded 6.56 → 4.47 → 3.09 decades over the ladder, is 4.39 here"* | invites the reading that refinement arrested the erosion; against level 2's 4.4748 the margin is **worse** | §5 |
| *"attributable to port-face resolution and to nothing else"* | the refined region is a volume and the meshes are not nested | §1 |
| the sensitivity ratio described as an **upper bound** | an upper bound still presumes the numerator bounds a port contribution | a ratio of observed changes, carrying no attribution (§1) |
| mode 2's opposite sign described as **falsifying** the port mechanism | that argument holds for one stiffness coefficient on a fixed discretisation, not for re-meshing | an unexplained fact of the record (§1, §5) |
| *"3.91× finer"* than L3 | a triangle-**count** ratio quoted as resolution | 3.91× by count, **1.92× linear** by mean edge (§1) |

One further correction is not about R1. **The ladder's own order-of-convergence
verdict is not robust to the choice of `h`.** The estimator fits against the
*requested* `h_gap` (0.010 / 0.006667 / 0.005 mm), but the delivered port-face
sizes are 0.010425 / 0.008597 / 0.006407 mm. Against those, the same estimator
fits q = 2.63 (L1m1) and q = 1.55 (L1m2) where against `h_gap` it fits none.
This does **not** claim the ladder converges — three points, and the face size is
one of several length scales — but as a statement about the *solution*,
*"the ladder shows no positive order of convergence"* is withdrawn: it is a fact
about the estimator run against `h_gap`. A future ladder should say which length
scale it is fitting against.
