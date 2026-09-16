# The bounded three-solve pilot: what it measured

Record: `results/COUPLED-PILOT-20260916T035733Z` (workflow run 35053649226),
committed append-only, manifest verified. Approval record:
`.github/pilot-approval.json`.

> **Superseded in part.** Sections 2, 3 and 5 below were written before the
> bounded corrective analysis of this record. That analysis corrected three
> things: which rows are admissible (P2 admits a *third* mode, m9 at
> 9.961 GHz, above six rejected rows, so "modes 1 and 2" was wrong as a rule);
> what the energy-balance defect establishes (it flags the rows whose reported
> participation cannot be trusted, and does **not** prove a mechanism); and the
> participation sign (a solver gauge artefact, not a physical current
> direction). The corrected text is below, with the superseded wording named
> where it was wrong. The record itself is unchanged; the corrected analysis is
> a separate record, `results/COUPLED-PILOT-CORR-20260916T064943Z`, and the reasoning is in
> [`corrective-analysis.md`](corrective-analysis.md).

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

## 2. Most computed rows fail the reported energy balance

For an exact eigenpair of the discrete problem `K x = ω² M x` the identity
`x'Kx = ω² x'Mx` holds by algebra, so `R = (E_mag + E_ind) / (E_elec + E_cap)`
is 1 for a resonance. Across all 23 mode rows of the three solves, `R` is
**strictly bimodal**: 7 rows have `|R − 1| ≤ 1.7473e-5` and the other 16 have
`|R − 1| ≥ 0.999926`, with nothing in between. The admitted set is therefore
the same for any cutoff between `1.75e-5` and `0.9999`.

| run | rows | admitted | admitted in the 0.5–9.0 GHz window |
|---|---|---|---|
| P1 | 6 | m1, m2 | m1, m2 |
| P2 | 9 | m1, m2, **m9** | m1, m2 |
| P3 | 8 | m1, m2 | m1, m2 |

**P2 admits a third mode, m9 at 9.961 GHz, sitting above six rejected rows.**
The earlier wording — *"Only mode 1 and mode 2 of each solve are physical
circuit modes"* — was wrong as a rule: it happened to hold for P1 and P3 and
does not hold for P2. Admission is decided per row, never by index.

What the defect establishes, and what it does not:

- Palace's `E_ind` is not the port stiffness quadratic form but the rank-one
  surrogate `|V|²/(2ω²L)` built from the port's **width-averaged line voltage**,
  projected on the declared `+Y` direction, which by Cauchy–Schwarz is a *lower
  bound* on it. A failing row is therefore either not an eigenvector at its
  reported frequency, **or** an eigenvector whose stiffness sits in a strongly
  non-uniform tangential field on the port that the average grossly understates.
  The record cannot separate those, though the second is the better supported;
  see [`corrective-analysis.md`](corrective-analysis.md) §C.3.
- It does not matter for admission, because the reported participation
  `p = E_ind/(E_elec + E_cap)` is built from the *same* surrogate: in either
  case the `p` of a failing row is not a quantity two solves may be compared
  on.
- The earlier claim that these are *"null-space / gradient artefacts that the
  divergence-free projection did not remove"* asserted a mechanism the
  evidence does not carry. It is withdrawn. Settling the cause needs the
  per-mode port stiffness integral `∫(1/L_s)|E_t|² dS`, which Palace does not
  write, or the saved mode fields, which this record does not contain
  (`Solver.Eigenmode.Save = 0` in all three configs).

## 3. The measured sensitivities

Relative differences, `|a − b| / |a|` with P1 as reference:

| pair | quantity | mode 1 (fluxonium-like) | mode 2 (readout-like) |
|---|---|---|---|
| P1 vs P2 (element order, same mesh) | `Δf` | **3.22e-1** | 1.17e-1 |
| P1 vs P2 | `Δp` | 5.47e-4 | 2.24e-1 (magnitude) |
| P1 vs P3 (halo, same order) | `Δf` | **4.49e-2** | 1.24e-2 |
| P1 vs P3 | `Δp` | 3.36e-4 | 2.44e-1 |

All four `Δp` figures above are **magnitudes**, `abs(|p_a| − |p_b|) /
max(|p_a|, |p_b|)`, which is the corrected convention. Note that
`abs(|a| − |b|) ≤ |a − b|` always, so the change can only make the criterion
easier to pass: on the readout pair it moves `Δp` from `1.78` to `0.224`. Both
still fail the frozen `1e-2`, by 178× and by 22×, so no verdict turns on it.

Two further observations, recorded because they bear on the next stage:

- The readout-like mode's *signed* participation differs between order 1 and
  order 2 (`−9.34e-4` against `+1.20e-3`). This is **not** a physical current
  instability, and the earlier claim that *"the current direction through the
  port is not stable under discretisation"* is withdrawn. Palace computes the
  port current as `I = V/(iωL)` exactly, so `arg(I) = arg(V) − 90°`
  identically and `V/I` is the constant `iωL` — the ratio carries no
  information. The EPR sign is `sign(Re I) = sign(Im V)`, which rotates with
  the eigenvector's overall complex phase, and the pinned Palace tree contains
  no phase-fixing step: its only post-solve normalisation is multiplication by
  a real non-negative scalar. With a single inductive port there is no second
  phase reference in the solve, so the sign is a gauge choice. A signed
  comparison of that quantity gives `Δp = 1.78`; the magnitude comparison
  gives `2.24e-1`, and the magnitude is the defensible one.
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

`scripts/palace_coupled_pilot.py::_readout_like_mode` implemented "the
readout-like mode" as the in-window row with the **smallest** `|p|`. Because a
failing row's `p` is small *precisely because* its reported energies do not
balance, that rule selects the least trustworthy row in the window in
preference to the mode it was meant to find. Re-deriving the selector against
the record reproduces exactly the rows the report names: P1 m3 (8.846 GHz,
`p = −1.22e-7`, `|R−1| = 0.99998`), P2 m4 (7.044 GHz, `p = −1.39e-11`) and
P3 m3 (8.296 GHz, `p = +1.88e-7`). The published `Δp = 1.648`,
`Δf = 6.22e-2` are comparisons between unmatched rejected rows, and the `Δp`
also used a **signed** difference, which compounds the error.

**The verdict is unchanged by the defect.** On matched admitted modes the halo
comparison gives `Δf = 4.49e-2` and `1.24e-2`, both exceeding the frozen
`1e-4` by two to three orders of magnitude, so outcome three of §4.2 is
reached either way. The recorded verdict `NOT-A-HALO-VERDICT` stands.

The record is **not** rewritten. The corrected comparison is a separate,
versioned record (`results/COUPLED-PILOT-CORR-20260916T064943Z`) that references the source
record's hashes, and the rules it introduces are labelled retrospective for
this record and prospective for the next confirmatory run. Both defects are
fixed in the driver: it now joins the five per-mode tables by mode id, checks
two identities that span them, admits rows on the energy balance, matches two
runs by two independent orderings with a separation guard, and compares
magnitudes.

## 6. Where the three proposals ended up

This section originally listed three things the next bounded check would need.
The corrective analysis settled two of them and withdrew the third.

1. **Mode identification by physics, not by rank — done.** Admission is now
   `|R − 1| ≤ 1e-3` on `R = (E_mag + E_ind)/(E_elec + E_cap)`, applied before
   any participation is looked at, and implemented in
   `solvers/palace/mode_admission.py`. It adds no solve. The rule is
   retrospective for this record and prospective for the next run. (The
   quantity named here originally, `equipartition_residual`, normalised by the
   sum of all four energies rather than by the electric side; `R` is the ratio
   the Rayleigh identity is actually about.)
2. **The open question is mesh level, not halo — unchanged, and still open.**
   The halo is not separable from discretisation error at level 1. The proposed
   next test is in [`corrective-analysis.md`](corrective-analysis.md) §H: an
   order-1 mesh-refinement sequence at fixed 0.08 mm halo, preceded by the free
   offline DOF dry run, because order 1 measured 32.4 s where order 2 measured
   2009.7 s on the same mesh. It is a proposal, not an approval.
3. **Withdrawn.** The third item said the participation *"needs a sign
   convention that survives discretisation"*. There is nothing to survive: the
   sign is a solver gauge choice, per §3. The comparison uses magnitudes and
   the signed values are preserved.

The extraction stage is not executable on this evidence. Its disposition is
**REQUIRES-ANOTHER-BOUNDED-NUMERICAL-CHECK**, as the record states.
