# The bounded three-solve pilot: what it measured

Record: `results/COUPLED-PILOT-20260916T035733Z` (workflow run 35053649226),
committed append-only, manifest verified. Approval record:
`.github/pilot-approval.json`.

**This was a numerical-method pilot only.** No coupling extraction was
performed: no Route A inversion, no `g`, no invariant triple, no gate input,
no Route B, no pulse, AMD-E, decoder or mediator work, no redesign. Every
geometric value remains an unapproved `ENGINEERING-SEED`. The 10 % agreement
`ENGINEERING-RULE` is untouched, and no physical QMHP threshold was created,
moved or consulted.

The criteria used below were frozen in `execution-proposal.md` §4.2 **before**
the pilot ran and are unchanged: `Δp ≤ 1e-2` and `Δf ≤ 1e-4`.

## 1. The three solves as executed

The approved configuration: P3 at 0.12 mm, so that all three runs stay inside
the declared 250 000 DOF `ENGINEERING-RULE` and the 0.15 mm exception was not
taken. `execution-proposal.md` §4.1 records the pre-approval proposal, at
0.15 mm, and is deliberately left as written.

| run | order | halo | mesh elements | DOF (measured) | wall clock | status | max backward error |
|---|---|---|---|---|---|---|---|
| **P1** | 2 | 0.08 mm | 31 885 | 208 670 | 2009.7 s (33.5 min) | COMPLETED | 7.87e-11 |
| **P2** | 1 | 0.08 mm | 31 885 | 39 832 | 32.4 s | COMPLETED | 5.55e-12 |
| **P3** | 2 | 0.12 mm | 36 140 | 235 806 | 2567.5 s (42.8 min) | COMPLETED | 1.19e-10 |

All three completed inside the 45 min cap, inside the DOF budget, with no
timeout and no additional compute: one job on the standard runner, 77 min
end to end.

P1 and P2 share the **same mesh file** — Palace reports 31 885 elements for
both, and P2's single-level DOF count 39 832 is exactly P1's coarse multigrid
level. The order comparison is therefore a clean p-refinement at fixed mesh.

Two resource facts for the next stage:

- **P3 used 95 % of its cap.** Order 2 at mesh level 1 with a 0.12 mm halo
  already nearly exhausts 45 minutes. A level-2 mesh at order 2 does not fit
  the cap, let alone the ladder.
- **The cost is the preconditioner**, not the eigensolve: 1339.6 s of P1's
  2007.6 s and 1769.4 s of P3's 2567.2 s, against 2.3 s and 3.3 s of actual
  eigenvalue solve.

## 2. Only two modes in the window are physical

The record's own `equipartition_residual`, computed per mode from the domain
energies and independent of any participation, separates the modes sharply:

| run | modes in window | residual, modes 1–2 | residual, modes 3+ |
|---|---|---|---|
| P1 | 3 | 2.7e-6, 6.8e-7 | 0.99997 (×4) |
| P2 | 8 | 2.5e-9, 8.8e-9 | 0.9999 (×6) |
| P3 | 4 | 8.7e-6, 6.0e-7 | 0.99996 (×6) |

A residual near 1 means the electric-side and magnetic-side energies are not
equal, so the object is not a resonant mode of the problem; these are
null-space / gradient artefacts that the divergence-free projection did not
remove. Their site participation is correspondingly `1e-7` to `1e-11`.

**Only mode 1 and mode 2 of each solve are physical circuit modes.** Mode 1
is the fluxonium-like mode (`p ≈ 0.998`); mode 2 is the readout-like mode
(`p ≈ 1e-3`).

## 3. The measured sensitivities

Relative differences, `|a − b| / |a|` with P1 as reference:

| pair | quantity | mode 1 (fluxonium-like) | mode 2 (readout-like) |
|---|---|---|---|
| P1 vs P2 (element order, same mesh) | `Δf` | **3.22e-1** | 1.17e-1 |
| P1 vs P2 | `Δp` | 5.47e-4 | 2.24e-1 (magnitude) |
| P1 vs P3 (halo, same order) | `Δf` | **4.49e-2** | 1.24e-2 |
| P1 vs P3 | `Δp` | 3.36e-4 | 2.44e-1 |

Two further observations, recorded because they bear on the next stage:

- The readout-like mode's participation **changes sign** between order 1 and
  order 2 (`−9.34e-4` against `+1.20e-3`). Palace's EPR sign is
  `sign(Re I)`, so at the `1e-3` level the current direction through the port
  is not stable under discretisation. A signed comparison of that quantity
  gives `Δp = 1.78`.
- The fluxonium-like participation is stable to `3–5e-4` across both knobs,
  while its **frequency** is not. The participation is pinned near 1 by the
  sum rule; it cannot detect under-resolution on its own.

## 4. The verdict under the frozen criteria

Against `Δf ≤ 1e-4`, the halo comparison fails by **124×** on the readout-like
mode and by **449×** on the fluxonium-like mode. Against `Δp ≤ 1e-2`, the
readout-like participation fails by 24×.

This is the **third** predeclared outcome of §4.2, verbatim:

> **The frequency check fails** (`Δf > 1e-4`) → this is not a halo verdict at
> all: a frequency moving that much between two size fields at the same
> refinement level indicates the level-1 mesh is too coarse for the geometry,
> or the model is wrong. Report and stop; the halo question is not answerable
> from that pilot.

So: **NOT-A-HALO-VERDICT**. The 0.08 mm halo is neither admitted nor rejected.
The criterion is not loosened, and `Δp` is not carried into `δ_A`, because
there is no admissible halo to carry it from.

The 32 % frequency shift between order 1 and order 2 **on an identical mesh**
is the sharper statement of the same thing: at mesh level 1 the discretisation
error dwarfs both knobs under test.

## 5. A defect in the automated mode selection, and why it changes nothing

`scripts/palace_coupled_pilot.py::_readout_like_mode` implements
"the readout-like mode" as the in-window mode with the **smallest** `|p|`.
That implementation predates the discovery in §2 that the window also
contains non-physical modes with `|p| ~ 1e-7`. It therefore selected mode 3 of
P1 (8.846 GHz, `p = −1.22e-7`) against mode 3 of P3 (8.296 GHz,
`p = +1.88e-7`) — two unmatched artefacts — and the numbers it printed as the
verdict (`Δp = 1.648`, `Δf = 6.22e-2`) are comparisons between them.

**The verdict is unchanged by the defect.** Under every candidate pairing —
the artefact pair the script chose, the genuine readout-like mode 2, or the
fluxonium-like mode 1 — `Δf` exceeds `1e-4` by two to three orders of
magnitude, so outcome three of §4.2 is reached on all of them. The recorded
verdict `NOT-A-HALO-VERDICT` stands, and the record's own
`fluxonium_like_mode` block already carries the alternative pairing.

The record is **not** rewritten. Re-running the comparison with a different
selection rule after seeing the numbers is exactly the move the frozen-criteria
discipline forbids, so the fix belongs to the next check, predeclared before
it runs, not to this one.

## 6. Proposed, not adopted: what the next bounded check would need

Nothing below is approved or in force. It is the proposal this pilot's result
implies, for the review to accept, change or refuse.

1. **Mode identification by physics, not by rank.** Admit a mode to the
   comparison only if its `equipartition_residual` is below a predeclared
   floor; identify the readout-like mode among the survivors. The residual is
   already computed and recorded for every mode, so this adds no solve. The
   floor must be written down before the check runs.
2. **The open question is mesh level, not halo.** The halo is not separable
   from discretisation error at level 1, so the next check is a mesh-level
   refinement at fixed order 2 and fixed 0.08 mm halo. On the measured cost
   this does not fit the current 45 min cap or the 250 000 DOF rule, so it
   returns to the review as a resource question before anything is launched.
3. **The readout-like participation needs a sign convention that survives
   discretisation** before it can enter any comparison at the `1e-3` level.

Until those are settled the extraction stage is not executable on this
evidence. Its disposition is
**REQUIRES-ANOTHER-BOUNDED-NUMERICAL-CHECK**, as the record states.
