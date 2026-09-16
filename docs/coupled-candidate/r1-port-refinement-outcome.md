# R1: what refining the port face alone changed

> **Corrected in eight places, the same day it was written**, across four
> independent readings of the committed record and two adversarial refutations of
> what survived them. Every *measured* number reproduced independently every time
> — frequencies and deltas to the last printed digit, `κ` bit-identically from the
> raw mesh and config, `p_port` to ~1e-15. **The measurements were never the
> problem.** What was wrong was the interpretation: first its framing, then the
> arithmetic of a correction to that framing, and finally the causal attribution
> itself. Withdrawn wording is kept as a marked quotation; §7 lists all eight.
>
> **This run is not a port-face refinement.** `PortRefinement.box_mm` pads
> ±0.010 mm in *z* as well as in *x* and *y*, so the gmsh Box field is a
> 0.040 × 0.060 × 0.020 mm **volume** around a 0.020 × 0.040 mm rectangle,
> blending a further 0.020 mm — reaching about 0.03 mm into vacuum and
> substrate. One *prescribed number* changed; one *physical channel* did not.
> That is a defect in code written for this experiment, not a reading error.
>
> The one claim that survives all three rounds: **R1's port face is 3.91× finer
> than L3's, yet its mode-1 frequency is 0.189 GHz below L3's** — so the port
> neighbourhood is not the bulk of what the ladder was buying. No ratio, no
> share, no decomposition. A field-based measure says it more sharply than the
> triangle counts do: R1 brings the face's normal-field energy fraction
> `p_MA/p_Default` to **0.1058** against L3's **0.1000** — within 5.8 %, from a
> baseline 15.6× deficient at 0.0064 — for **818** added DOF against L3's
> **67 428**. The face was resolved, and the frequency still did not follow.

Record: `results/COUPLED-LADDER-O1-L2-R1-20260916T120954Z`
(workflow run 35094133974, commit `96bef92`). Manifest intact; the preserved
pilot record verified untouched by the run itself.

**Where the withdrawn wording still lives, and why it is left there.** Records
are written once and never modified — that is what makes them evidence. So the
committed record states, in its own `summary.json` (`baseline_comparison.
why_this_comparison`, line 207) and in `report.md` line 97, that a frequency
difference between R1 and its baseline is *"attributable to port-face resolution
and to nothing else"*, and in `port_resolution_sensitivity.statistic` that the
numerator "changes only the port box". **Both claims are withdrawn by this
document** (§§1, 5 and 7): the box is a volume, the meshes are not nested, and
the denominator refines the face too.
The approval record `.github/ladder-approval.json` carries the same framing in
`what_this_run_answers.statistic` ("the numerator changes only the port box"),
and is **also left untouched** — for a second reason on top of immutability:
committing that file on a `palace/**` branch is what *starts* a solve, so editing
it to fix prose would launch a run nobody approved.

The driver that writes those strings has been corrected, so no *future* record
will carry them; this one is left exactly as the run produced it, and this
paragraph is the pointer a reader needs. The anti-regression guard covers the
documents, not the records or the approval, for the same reason.

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

## 1. The answer: the port neighbourhood is not the bulk of what the ladder was buying

| tracked mode | role | port-only Δf (+1.0 % DOF) | global L2→L3 Δf (+84 % DOF) | **sensitivity** |
|---|---|---|---|---|
| L1m1 | LUMPED_DOMINATED | **+0.059116 GHz** | +0.247675 GHz | **0.2387** |
| L1m2 | FIELD_DOMINATED | **−0.018289 GHz** | +0.202172 GHz | **0.0905** |

**The cleanest statement of the result uses no ratio at all.** R1's port face
carries 176 triangles against L3's 45 — **3.91× finer** — and yet
`f(R1 m1) = 1.521003 GHz` sits **0.188559 GHz below** `f(L3 m1) = 1.709562 GHz`.
Refining the port face well past L3's resolution does not reproduce L3's
frequency, so the port face is **not** the sole driver of the ladder's movement.
That rests on two measured frequencies and two triangle counts.

**A field-based measure says the same thing, and says it more sharply than the
triangle counts do.** The two `surface-Q.csv` probes sit on the same port face
(attribute 10, `t = 1.0`, `eps = 1.0`, same side) and differ by the tangential
term `½·t·|E_t|²`, so their ratio `p_MA/p_Default = ∫|E_n|²dS / ∫|E|²dS` is the
port face's **normal-field energy fraction** — a quantity that converges only
once the face itself is resolved. For mode 1:

| | port-face triangles | `p_Default` | `p_MA` | `p_MA/p_Default` | DOF added |
|---|---|---|---|---|---|
| baseline `L2` | 25 | 3.883687e-02 | 2.486271e-04 | **0.006402** | — |
| **R1** | **176** | 4.669391e-02 | 4.940375e-03 | **0.105803** | **818** |
| `L3` | 45 | 5.862196e-02 | 5.864623e-03 | **0.100041** | 67 428 |

The baseline face is **15.6× deficient** in this fraction. R1 recovers it to
within **5.8 %** of L3's value for **818** added DOF against L3's **67 428** —
82× fewer. So R1 did resolve the port face, by a field measure and not merely by
element count; and having resolved it, `f(R1 m1)` still sits 0.188559 GHz below
`f(L3 m1)`. Whatever L3's other 66 610 DOF bought, it was not this. (A DOF count, not a
share of the error: the two are not the same and this record does not decompose
the error at all.)

This is the one claim in the record that survived every round of correction, and
it is deliberately stated without a ratio, a share, or a decomposition.

**The readout-like mode's shift falsifies the port mechanism for that mode.**
First-order perturbation through a positive-definite stiffness term makes the
fractional shift scale with that term's participation. Mode 2 holds
`p₂/p₁ = 7.81e-04` of mode 1's port participation, so a port-mediated shift
would be `4.044e-02 × 7.81e-04 = 3.16e-05` relative — about **1.23e-04 GHz**.
Observed: **−1.83e-02 GHz, 149× too large and in the opposite direction.** A
positive-definite term cannot push two modes of positive participation opposite
ways, so mode 2 moved through a different channel — the volume refinement, not
the port.

It is not solver noise: mode 2's shift is ~2.5e9× its own absolute error
estimate and 47× the frozen `Δf ≤ 1e-4`. It is real discretisation movement in
the wrong direction, and it is the record's own strongest evidence that the
perturbation is not acting through the port.

**So 0.2387 is an upper bound on a quantity that was never isolated.** The same
perturbation moved a mode holding 0.078 % of its energy on the port by
4.71e-03 relative; mode 1's whole shift is 4.04e-02 relative. An effect of that
size is ~12 % of mode 1's movement and could bias it either way.

> **Struck and replaced.** This read *"Port-face resolution accounts for part of
> the ladder's frequency movement and not the bulk of it"* and quantified it as
> *"23.9 % of what a 1.5× global refinement bought"*. Both are withdrawn. The
> sensitivity statistic's numerator and denominator apply **different-sized port
> perturbations**: at the port centre the prescribed size goes 0.033611 →
> 0.025208 mm across L2→L3, a factor **1.333**, while R1 holds 0.003333 mm
> there, a factor **10.08** — so the numerator's port perturbation is about
> **7.6× stronger** than the denominator's, and whatever part of the ladder step
> is genuinely port-related is far below 23.9 %. The phrase *"a 1.5× global
> refinement"* is also wrong and is withdrawn: L2→L3 is a **1.333×** step;
> 1.5× is L1→L2. Nor does the share arithmetic close — with magnitude bars mode
> 2's remainder is 109 %, not 91 %. The related claim *"the remaining ~76 % comes from elsewhere"* is
> withdrawn outright: it presumes an eigenvalue error decomposes additively into
> regional contributions, and no such theorem exists. An eigenvalue is a global
> functional.

**On cost: the local refinement is roughly break-even, not cheap.** R1 bought
0.059116 GHz for +14.5 s (4.07e-03 GHz/s); L3 bought 0.247675 GHz for +77.9 s
(3.18e-03 GHz/s). The ratio is **1.28×** — essentially flat. Even that is
contaminated: R1 returned seven converged eigenpairs to the baseline's six from
the same `N = 6` request, so part of the +14.5 s is an extra mode's estimation,
postprocessing and field write rather than the 818 DOF.

> **Struck and replaced, twice.** The first version claimed *"19.7× more
> frequency movement per DOF"*. That treats `Δf` as linear in DOF on a sequence
> with no established order and is unbounded by construction. The correction to
> it then claimed *"3.2× more movement per second"*, which is **arithmetically
> wrong**: `(0.059116/14.5357)/(0.247675/77.8861) = 1.279`. The figure 3.2 was
> L3's own rate, 3.18e-03 GHz/s, restated as though it were a ratio. Both are
> withdrawn; the measured per-second ratio is 1.28×.

Against the predeclared outcomes this is **neither A nor B**: m1 did not move
comparably to its global step, and it did not barely move either — 4.0 %
relative is 590× the frozen `Δf ≤ 1e-4`. It lies between them, closest to a
partial C, with the important qualification that the two modes moved by
different fractions *and in opposite directions*.

## 2. The derived diagnostic, and what its agreement does and does not show

`κ = 1/(t_nd·L_s_nd) = 0.3886882529` was derived from pinned Palace v0.13.0
source and the declared port geometry, fitted to nothing.

> **Struck and replaced.** The heading read *"The derived diagnostic held on a
> mesh it had never seen"*, which is withdrawn. `κ` depends on the mesh only
> through two bounding boxes — the global extent (4.000 mm) and the port face
> (0.020 × 0.040 mm) — and a Box field refining the interior changes neither, so
> `κ` is **identical by construction** on R1. R1 is not an out-of-sample test of
> `κ`. What it does test is that the probe-to-closure relationship holds on a new
> eigenvector with new frequencies and new probe values, which is a real test but
> not the one the heading implied. Nor are the three runs three independent
> confirmations: a mesh-independent error in the derivation — a swapped `w/l`, a
> wrong `t_nd` — would produce the same offset on every mode of every run.

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

> **Struck and replaced.** This section read *"The strongest corroboration is
> above the window"* and concluded that the changed spectrum was *"direct
> evidence the port face was under-resolved"*. Withdrawn on two grounds. The
> count going four → five is **SLEPc returning `nconv` = 6 for the baseline and 7
> for R1, both at `N = 6`** — a solver artifact, not a physical change. And by
> this record's own sensitivity statistic the rejected rows score 0.205, 0.176,
> 0.085 and 0.471, which **bracket** mode 1's 0.239 rather than exceed it: they
> move more in absolute terms, not by the measure being used. There is also no
> established correspondence between the two runs' rows above m = 2, so they
> must not be compared mode by mode. This was the weakest item in the record,
> not the strongest.

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

> **Struck and replaced.** This read *"The admission margin, which had eroded
> 6.56 → 4.47 → 3.09 decades over the ladder, is 4.39 here"*, which is withdrawn:
> it invites the reading that port refinement arrested the erosion. It did not. R1 is a
> **level-2** run, so the like-for-like comparison is against level 2's 4.4748,
> and against that the margin is 0.090 decades **worse**. R1 says nothing about
> the level-3 value.

## 5. What this does not establish

- **No convergence claim.** One refined mesh identifies no limit, measures no
  order, and says nothing about whether refining the face further would settle
  the frequency.
- **A bounded sensitivity does not identify anything else.** 0.2387 and 0.0905
  bound what refining that volume moved; they do **not** imply that the
  complement — "the remaining ~76 %" — is a located or even a well-defined
  quantity. An eigenvalue discretisation error is not known to decompose
  additively by mesh region, and this record does not decompose it. The honest
  statement is the negative one: **this run does not locate the rest of the
  ladder's movement, and does not bound it either.**
- **Nothing here bears on the physical architecture.** Every number is about the
  discretisation of a declared idealisation.
- **The opposite sign on the readout-like mode is not explained.** Refining the
  port face pushed it the other way from the ladder; that is a fact of the
  record, not an account of it. It also falsifies any single-sign model of
  port-face discretisation error.
- **The two runs are not nested.** The prescription differs in one number and
  `config.json` is byte-identical, but gmsh re-meshed globally: **18.4 % of the
  baseline's 13 991 nodes (2 571) do not exist in R1**, at a median distance of
  1.37 mm from the port and a maximum of **3.32 mm**, most of the way across a
  4 mm cell. `sheet_pec` gained 79 triangles and the tetrahedron count rose by
  634. No replicate — same prescription, perturbed seed, or an identically sized
  box placed away from the port — establishes the re-meshing noise floor, so an
  unknown part of the +0.059 GHz is uncontrolled.
- **"Port face" is too narrow.** The Box field pads 0.010 mm and blends a further
  0.020 mm, so the added elements sit on the face *and* in a neighbourhood
  extending 0.030 mm beyond it.
- **The port-face field integral is not converged even at 176 triangles.**
  `p_Default` for mode 1 climbs monotonically 3.884e-02 (L2) → 4.669e-02 (R1) →
  5.862e-02 (L3). This does not contradict §1's normal-field fraction: the
  *absolute* integral is still moving (it is normalised by `E_elec + E_cap`, and
  the mode itself is still moving), while the *ratio* `p_MA/p_Default` has
  settled. Two different statistics, both measured, and only the ratio is
  claimed to have converged.
- **The whole ladder comparison depends on the 9.0 GHz band ceiling.** At 10 or
  12 GHz, L1 and L3 admit three modes against L2 and R1's two, which the matching
  rule refuses as a count mismatch.
- **The frozen tolerances are exceeded, and by how much should be stated:**
  `Δf` relative by **404×** on m1 and **47×** on m2; `Δ|p|` by **29×** on m2. The
  comparison gates nothing, but a reader should not have to do the division.

## 6. Disposition

**STOP**, as approved. R1 is a diagnostic run, not a ladder rung: it carries a
size constraint the other rungs do not, so it is excluded from the convergence
fit, and `refinement_trend` refused to publish its confounded movement against
level 1. R2 is prepared and dry-run at 111 238 DOF but is **not approved** and
was not run. No coupling extraction, Route A inversion, Route B, pulse work,
AMD-E or mediator work; the DOF rule, the cap and every tolerance are unchanged.

## 7. What was corrected, and one correction to the ladder's own headline

Four independent readings of this record — arithmetic, port physics, the modes
above the window, and a reading whose only brief was to find what the evidence
does not support — followed by two adversarial refutations of the surviving
headline, reproduced every measured number and faulted the interpretation in
eight places.

Five are struck in place above, each keeping the withdrawn wording as a marked
quotation: the "accounts for part of the movement" framing (§1), the two
efficiency claims (§1), `κ` holding "out of sample" (§2), the modes above the
window as "the strongest corroboration" (§3), and the admission margin as
"recovered" (§4). Two more are corrected without a quotation because they were
never single sentences: that this refines a *face* rather than a volume — a
defect in `PortRefinement.box_mm`, now in its docstring and under test — and
that the sensitivity ratio is a *share* rather than an upper bound. An eighth
lives in a different document: `s1-numerical-recovery.md` predicted, before the
run, that the two axes were cleanly separated and a large shift would localise
the cause; the meshes are not nested, so it is struck there.

The last item is not about R1 at all.

**The ladder's "no positive order of convergence" verdict is not robust to the
choice of `h`.** The estimator fits order against the *requested* `h_gap`
(0.010 / 0.006667 / 0.005 mm). But `s1-numerical-recovery.md` §3 measured that
**`h_gap` never held on the port face**: the delivered face element sizes are
0.010425 / 0.008597 / 0.006407 mm. Running the same estimator against the
delivered sizes:

| tracked mode | against requested `h_gap` | against delivered face `h` |
|---|---|---|
| L1m1 | ratio 1.2256 < floor 1.4094 → **no positive order** | ratio 1.2256 > floor 0.6557 → **q = 2.63 fits** |
| L1m2 | ratio 0.9513 < floor 1.4094 → **no positive order** | ratio 0.9513 > floor 0.6557 → **q = 1.55 fits** |

Same frequencies, same estimator, opposite verdict. This is **not** a claim that
the ladder converges at those orders — three points, and the port-face size is
one of several length scales in the problem, so neither choice of `h` is
obviously the right one. What it does mean is that *"the ladder shows no
positive order of convergence"* is withdrawn as a statement about the solution
and must not be repeated as one. It is a fact about the estimator run against
`h_gap`, and using `h_gap` sits badly with this project's own demonstration that
`h_gap` never reaches the face.

`order1-ladder-outcome.md` §1 already carries a correction narrowing its heading
to *"No order of convergence fits these three rungs"*. That remains accurate as
stated — it is about these rungs under that estimator — but the sentence should
be read with this section, and a future ladder should say which length scale it
is fitting against.

**What survives all of it**, and the only claim defended without qualification:
R1's port face is 3.91× finer than L3's — and, by the field measure of §1, has a
normal-field energy fraction within 5.8 % of L3's — yet its mode-1 frequency is
0.189 GHz *below* L3's. **The port neighbourhood is not the bulk of what the
ladder was buying.** No ratio, no share, no decomposition, no efficiency claim,
and no statement about where the rest of the movement comes from — this record
does not locate it and does not claim to.
