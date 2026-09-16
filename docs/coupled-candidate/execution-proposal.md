# Bounded geometry, meshing and resource proposal — for approval

**Status: PROPOSAL. Nothing here is adopted.** No seed is promoted, no
threshold is changed, the 10 % agreement ENGINEERING-RULE is untouched, and no
coupled solve has been launched. The declaration
`config/coupled/v2a_five_node_candidate.json` is unchanged by this document;
adopting any option below would be a human decision recorded as a new
declaration version with its own checkpoint record.

The execution disposition of checkpoint A is BLOCKED on compute. This document
gives the review the measured option space and asks for one decision.

## 1. What is actually binding

Every number below is measured, not estimated: mesh counts from gmsh, and the
Nédélec space dimension from the mesh topology (`numerical-plan.md` §8.1),
checked against Palace's own reported figure on the committed golden record.

The cost is dominated by **how far the fine mesh extends around the
conductors**, not by the gap itself. The declared size field puts
`h = min_gap/2` at every conductor and etch edge and relaxes to `min(a,b)/12`
over a halo of `DistMax = 0.3 mm`. Measured at level 1 with the declared
geometry:

| halo `DistMax` | tets | DOF order 2 | DOF order 1 |
|---|---|---|---|
| 0.30 mm (declared) | 85 233 | 545 734 | 101 668 |
| 0.15 mm | 43 407 | 281 332 | 53 119 |
| 0.08 mm | 31 885 | 208 670 | 39 832 |
| 0.04 mm | 30 186 | 197 656 | 37 723 |

Widening the coupling gap helps only until another gap becomes the narrowest:
at 40 µm and at 60 µm the mesh is identical, because the 30 µm CPW slot then
sets `min_gap`. Widening every gap to 80 µm *increases* the count, because the
wider slots enlarge the fine-meshed area. The cell size behaves the same way:
shrinking it to 2 × 2 mm raises the count, because the far-field size
`min(a,b)/12` shrinks with the cell while the fine region does not.

## 2. The three ladders that were measured

Each is the declared three-level ladder `h0`, `h0/1.5`, `h0/2`.

**Option A — declared geometry, tighter halo (0.08 mm).** No geometric seed
changes; only the mesh rule.

| level | `h` at the gaps | tets | DOF order 2 | DOF order 1 |
|---|---|---|---|---|
| L1 | 10.0 µm | 31 885 | **208 670** | 39 832 |
| L2 | 6.7 µm | 64 434 | 420 664 | 79 944 |
| L3 | 5.0 µm | 120 370 | 781 554 | 147 372 |

**Option B — declared geometry, declared halo (0.30 mm).** Nothing changes.

| level | `h` at the gaps | tets | DOF order 2 | DOF order 1 |
|---|---|---|---|---|
| L1 | 10.0 µm | 85 233 | 545 734 | 101 668 |
| L2 | 6.7 µm | 192 597 | 1 230 572 | 228 572 |
| L3 | 5.0 µm | 373 091 | 2 378 980 | 440 642 |

**Option C — 40 µm coupling gap (a seed change) with a 0.15 mm halo.**

| level | `h` at the gaps | tets | DOF order 2 | DOF order 1 |
|---|---|---|---|---|
| L1 | 15.0 µm | 29 335 | **191 178** | 36 187 |
| L2 | 10.0 µm | 78 462 | 507 114 | 95 115 |
| L3 | 7.5 µm | 144 085 | 928 872 | 173 597 |

**The finding that matters: no option gives a three-level order-2 ladder
inside the 250 000 DOF budget.** Order 2 fits at L1 only, in options A and C.
Order 1 fits all three levels in options A and C, and the first two in B.

## 3. Why this cannot be settled on paper

Route A's accuracy on the coupling is set by the **energy participation**, not
by the frequencies: the measured propagation
(`route-a-identifiability.md` §6) is roughly one-for-one, so about 1 %
participation accuracy gives about 1 % on `g`. Whether an order-1 Nédélec
solve on this mesh delivers a 1 % participation is **not known** and cannot be
argued from the DOF count: order 1 is cheaper per unknown and less accurate
per unknown, and the participation is an energy ratio whose convergence
behaviour on a mesh with 10 µm gaps inside a 4 mm cell has never been measured
here. The honest way to decide the element order is to measure it.

## 4. What is proposed

### 4.1 The bounded pilot: three solves

Three Palace eigenmode solves of the **same declared geometry**, all at mesh
level 1, differing only in element order and in the size-field halo. Each is
capped at **45 minutes** of solver wall clock and killed at the cap. **No
external or additional compute is used**: one job on the existing
GitHub-hosted runner, 2.25 h of solver time plus the 30 min evidence reserve,
inside the 6 h ceiling.

| run | element order | halo `DistMax` | DOF (measured) | purpose |
|---|---|---|---|---|
| **P1** | 2 | 0.08 mm | 208 670 | the reference solve |
| **P2** | 1 | 0.08 mm | 39 832 | element-order sensitivity, against P1 |
| **P3** | 2 | 0.15 mm | **281 332** | halo sensitivity, against P1 |

P1 against P2 tests element-order sensitivity at a fixed halo. P1 against P3
tests whether tightening the halo materially changes the participation, so the
halo change is **validated rather than assumed**.

> **One thing the review must decide with this.** P3 at the 0.15 mm halo
> measures **281 332 DOF**, which is **12.5 % above the declared 250 000 DOF
> budget** of §6 of the numerical plan. That budget is a predeclared
> ENGINEERING-RULE and this proposal does not relax it. Approving the pilot as
> specified therefore means approving P3 as a **single, explicit,
> one-run exception** to the DOF rule, for a validation solve that produces no
> extraction. If the exception is not wanted, the measured in-budget
> alternatives for the second halo are:
>
> | halo | DOF order 2 | within the 250 000 budget |
> |---|---|---|
> | 0.10 mm | 215 586 | yes |
> | 0.12 mm | 235 806 | yes |
> | 0.15 mm | 281 332 | **no** |
>
> A 0.12 mm P3 gives a 1.5× halo contrast instead of 1.9× and keeps the whole
> pilot inside every declared rule. Either choice is acceptable to this
> proposal; what is not acceptable is running P3 at 0.15 mm while leaving the
> budget rule unmarked.

**Approved and executed; this section is left as it was written.** The
review approved the pilot with P3 at **0.12 mm**, so the 0.15 mm DOF
exception above was declined and all three runs stayed inside the 250 000 DOF
rule. The approval is recorded in `.github/pilot-approval.json` and the
result in [`pilot-outcome.md`](pilot-outcome.md); the text above is the
pre-approval proposal and is deliberately not rewritten.

The pilot is **not an extraction**. It produces no coupling, feeds no gate and
touches no threshold. Its outputs are wall clock, memory, the mode list in the
declared window, and the site energy participation with its sensitivity to the
two knobs. It is recorded like any other run, with a manifest, labelled a
pilot, and it launches only on approval.

### 4.2 The predeclared numerical criterion for the halo

Written down before the pilot runs, so it cannot be chosen after seeing the
numbers. **This is a numerical execution rule about a discretisation choice.
It is not a physical QMHP threshold, it introduces no acceptance criterion for
any coupling, and it leaves the 10 % agreement rule untouched.**

Let `p₁` and `p₃` be the site energy participation of the readout-like mode
from P1 and P3, and `f₁`, `f₃` the corresponding mode frequencies. Define

```
Δp = |p₁ − p₃| / max(|p₁|, |p₃|)        the halo-induced relative change in participation
Δf = |f₁ − f₃| / f₁                     the halo-induced relative change in frequency
```

The 0.08 mm halo is **ADMISSIBLE** when both hold:

| check | rule | where the number comes from |
|---|---|---|
| frequency | `Δf ≤ 1e-4` | the existing frequency convergence rule of the numerical plan, applied unchanged to a different perturbation. Nothing new is invented |
| participation | `Δp ≤ 1e-2` | the participation accuracy Route A must reach anyway: the measured propagation is roughly one-for-one from participation to `g`, so a halo-induced shift above 1 % would by itself consume the whole Route A floor on `g` before any mesh refinement is considered |

**The result is propagated, not just passed.** When the halo is admissible,
`Δp` does not vanish from the record: it is carried forward as a *systematic*
contribution to Route A's resolution floor for `g`, combined with the
mesh-ladder term by taking the maximum, which is the same combination rule the
repository already uses for resolution floors. A halo that scrapes past the
criterion therefore raises the floor it must later be judged against, and it
cannot be made free by passing.

Outcomes, all three predeclared:

- **Both checks pass** → the 0.08 mm halo is admissible for the Route A
  ladder; `Δp` enters `δ_A` as above; the element order is then chosen from
  P1 against P2 by the rule in §4.3 below.
- **The participation check fails** (`Δp > 1e-2`) → the 0.08 mm halo is
  **rejected**: the coarse/fine transition is close enough to the fields to
  matter. The ladder would then need a halo at least as wide as 0.15 mm, which
  at order 2 does not fit the DOF budget at any level, so execution returns to
  the review as BLOCKED with that measurement. It is not rescued by loosening
  the criterion.
- **The frequency check fails** (`Δf > 1e-4`) → this is not a halo verdict at
  all: a frequency moving that much between two size fields at the same
  refinement level indicates the level-1 mesh is too coarse for the geometry,
  or the model is wrong. Report and stop; the halo question is not answerable
  from that pilot.

**Outcome reached: the third.** `Δf` exceeded `1e-4` by two to three orders
of magnitude on every candidate mode pairing, so the pilot returned
`NOT-A-HALO-VERDICT`. The criteria above were not loosened and `Δp` was not
carried into `δ_A`. See [`pilot-outcome.md`](pilot-outcome.md).

### 4.3 How the element order is chosen, from P1 against P2

Also predeclared, and also purely numerical. Let `Δp₁₂` be the relative
difference in the same participation between P1 and P2 at the common 0.08 mm
halo.

- If P1 completes inside its 45 minute cap, **order 2 is selected**, and
  `Δp₁₂` is reported as the measured cost of the cheaper discretisation.
- If P1 does not complete, **order 1 is the only option**, and it is usable
  only if its own participation converges on the ladder well enough to give a
  useful floor on `g`; `Δp₁₂` is then unavailable and that is reported.
- If neither completes, the extraction is not executable within the current
  allowance and the decision returns to the review.

### 4.3 The one approval being requested

**Approve the three-solve pilot of §4.1, which tests the halo change rather
than assuming it.** The halo is the only knob with a large effect that costs
no geometry: it does not touch a single declared dimension, and the
declaration's `ENGINEERING-SEED` values stay exactly as they are. Its risk is
specific and testable, and §4.2 states the criterion in advance.

The approval carries one sub-decision: whether P3 runs at 0.15 mm as a
single explicit exception to the 250 000 DOF rule, or at 0.12 mm to stay
inside every declared rule with a slightly smaller halo contrast.

Nothing else is requested. **No additional runner allowance and no purchased
compute is being asked for**, and none is assumed anywhere in this proposal.

## 5. What is explicitly not proposed

- No geometric seed is promoted. Option C's 40 µm coupling gap is measured and
  shown, not recommended: it would change the realised coupling as well as the
  mesh, and the seed plausibility note already records that the declared 20 µm
  gap is expected to over-couple. Changing the gap is a design decision that
  belongs to the review, not to a compute constraint.
- No change to the 10 % agreement rule, to the resolution ratio, to the
  frequency convergence rule or to any frozen threshold.
- No coupled solve, no Route B run, no pulse work, no decoder study, no
  openEMS, no mediator or AMD-E work.
- No relaxation of the requirement that each route carries independent
  convergence evidence. If a route cannot carry it within the allowance, that
  is reported as a limit, not absorbed by weakening the requirement.

## 6. Decision requested

1. Approve, or decline, the **three-solve** pilot of §4.1: P1 order 2 at a
   0.08 mm halo, P2 order 1 at 0.08 mm, P3 order 2 at the wider halo, one
   job, each solve capped at 45 minutes, no new allowance and no external
   compute.
2. Choose P3's halo: **0.15 mm**, accepting one explicit exception to the
   250 000 DOF rule for a validation solve that produces no extraction, or
   **0.12 mm**, which stays inside every declared rule.

The criterion that decides the halo (§4.2) and the rule that selects the
element order (§4.3) are predeclared here and are not revisited after the
pilot runs.

Until one of these is answered, execution stays BLOCKED and the checkpoint-A
package stands as it is.
