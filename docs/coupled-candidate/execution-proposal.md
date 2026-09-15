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

### 4.1 A bounded pilot, before any ladder

Two Palace eigenmode solves of the same declared geometry at level 1, both
inside the existing budget and the existing runner allowance:

| run | order | DOF | what it measures |
|---|---|---|---|
| P1 | 2 | 208 670 (option A) | wall clock, memory, the participation, and whether the solve completes at all |
| P2 | 1 | 39 832 | the same quantities at order 1 |

Comparing the participation of P1 and P2 at the same mesh gives the
order-dependence directly. The pilot decides the element order with data, and
its cost is bounded: **two solves, each capped at 45 minutes**, one job, well
under the 6 h ceiling. It launches only on approval.

The pilot is not an extraction. It produces no coupling and feeds no gate: its
outputs are timing, memory, the mode list in the window, and the participation
with its convergence behaviour. It would be recorded like any other run, with
a manifest, and labelled a pilot.

### 4.2 The ladder the pilot selects

- If P1 completes comfortably, propose **order 2** with a two-level ladder
  (L1 and a level between L1 and L2 sized to the measured budget), and state
  plainly that two levels is the minimum defensible convergence evidence and
  weaker than the three levels the empty-box campaign carried.
- If P1 is too slow or too large, propose **order 1** with the full three
  levels of option A, with the participation convergence reported per level
  and the Route A floor on `g` derived from it rather than assumed.
- If neither delivers a participation whose level-to-level change is small
  enough to give a useful floor on `g`, the honest outcome is that the
  extraction is **not executable within the current allowance**, and the
  decision returns to the review.

### 4.3 The one approval being requested

**Change the Route A mesh-rule halo `DistMax` from 0.30 mm to 0.08 mm, or
approve the pilot that tests it.** This is the only change with a large effect
that costs no geometry: it does not touch a single declared dimension, and the
declaration's `ENGINEERING-SEED` values stay exactly as they are. Its risk is
specific and testable: a halo that is too tight puts the coarse/fine
transition where the fields are still strong, which would show up as a
participation that moves between halo settings. That is a measurement the
pilot can make at the same time, by repeating P1 at a 0.15 mm halo.

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

1. Approve, or decline, the bounded pilot of §4.1 (two eigenmode solves, one
   job, ≤ 45 min each, no new allowance).
2. If approved, confirm that the halo change of §4.3 may be tested as part of
   it while the declaration itself stays unchanged.

Until one of these is answered, execution stays BLOCKED and the checkpoint-A
package stands as it is.
