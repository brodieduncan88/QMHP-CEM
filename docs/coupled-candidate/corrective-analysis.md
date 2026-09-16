# Corrective analysis of the coupled-pilot record

The bounded three-solve pilot `COUPLED-PILOT-20260916T035733Z` is **accepted as
executed evidence**. Its solver outputs, manifest, summary and report are
preserved byte-for-byte and are not rewritten here. What follows is a separate,
versioned analysis of those same files, recorded at
`results/COUPLED-PILOT-CORR-20260916T064943Z` with the source record's per-file digests.

**Nothing was launched and nothing was extracted.** No Palace run, no container,
no solve. No Route A inversion, no `g`, no charging energy, no capacitance, no
circuit parameter of any kind. The frozen halo criteria (`Δ|p| ≤ 1e-2`,
`Δf ≤ 1e-4`) and the backward-error tolerance (`1e-6`) are unchanged, and are
cross-checked from two independent places before the analysis runs.

Five questions are kept apart, because the pilot's own analysis ran them
together and that is how it went wrong.

---

## A. Execution completion

**ESTABLISHED, unchanged.** All three solves ran to completion inside the
45-minute cap and inside the 250 000-DOF rule, on one job, with no additional
compute.

| run | order | halo | DOF | wall clock | status |
|---|---|---|---|---|---|
| P1 | 2 | 0.08 mm | 208 670 | 2009.7 s | COMPLETED |
| P2 | 1 | 0.08 mm | 39 832 | 32.4 s | COMPLETED |
| P3 | 2 | 0.12 mm | 235 806 | 2567.5 s | COMPLETED |

The record's 35 manifest entries recompute to their recorded digests. P1 and P2
share a mesh file *by digest*, not merely by element count
(`b21424959652487eca005893d9b1900e9b278f973290c280c786f72d42fac300`), so the
order comparison is a p-refinement at exactly fixed mesh. P3's mesh digest
differs, as its halo requires.

Completion is a statement about the job. It carries no claim about the physics,
and this section makes none.

## B. Algebraic convergence

**ESTABLISHED, and it certifies less than it appears to.** All 23 computed mode
rows have backward errors between `1.3e-17` and `1.2e-10`, six to sixteen
orders below the `1e-6` tolerance. Every row converged.

A small backward error says the eigenpair solves the discrete problem to that
residual. It says nothing about whether the eigenpair is a resonance of the
stated model, and in this record **16 of the 23 converged rows fail the energy
identity that a resonance satisfies**.

It is also a weaker certificate than its size suggests. Palace normalises the
residual by the **global** operator norms, `‖K‖ + |μ|‖M‖`. The record shows this
directly: within each run the ratio `Error(Abs.)/Error(Bkwd.)` is constant to
five parts in a million — 3.0124e5 for P1, 1.5822e5 for P2, 2.5482e5 for P3 —
so the printed backward error is the true residual divided by a number of order
`1e5`. For a vector whose own stiffness quotient is a minute fraction of `‖K‖`,
that normalisation flatters it. Convergence and validity are different questions
and are reported separately from here on.

## C. Mode validity

### C.1 What the rule is

For an exact eigenpair of the discrete generalised problem `K x = ω² M x`, the
Rayleigh identity `xᴴKx = ω² xᴴMx` holds by algebra, not by approximation.
Palace's own postprocessing asserts the same equality as a fact in a source
comment (`palace/models/postoperator.cpp`: *"energy in mode m:
E_m = E_elec + E_cap = E_mag + E_ind"*). So

```
R = (E_mag + E_ind) / (E_elec + E_cap)
```

is 1 for a resonance. The admission rule is `|R − 1| ≤ 1e-3`.

It uses no participation rank and no mode index. Both were checked against the
pinned Palace v0.13.0 tree and against the record:

- Each converged eigenvector is rescaled by `1/sqrt(xᴴ Re(M) x)`, where `Re(M)`
  is the real-permittivity mass plus any lumped-port capacitance. With no port
  capacitance and no loss tangent in this pilot that fixes `E_elec + E_cap` to a
  per-run constant, which is why `E_elec` is byte-identical
  (`+6.671281904e-03`) on all 23 rows of all three runs.
- The four `domain-E.csv` columns headed `(J)` are **not joules**: Palace's
  energy dimensionalisation collapses to the characteristic time, which it
  carries in nanoseconds, so every printed value is `1e9` times the SI value.
  Verified on the record: `E_ind == 1e9 · ½L|I|²` on all 23 rows to `3.2e-10`.
  Every quantity used here is a ratio of two such columns, so the scale cancels.

### C.2 What the record shows

`|R − 1|` is **strictly bimodal**. Seven rows lie at or below `1.7473e-5`; the
other sixteen lie at or above `0.999926`. Nothing lies between. The admitted
set is therefore identical for any cutoff in `(1.75e-5, 0.9999)` — about
4.8 decades of insensitivity — so the threshold is not doing the work, the
separation is.

| run | rows | admitted | in the 0.5–9.0 GHz window | rejected |
|---|---|---|---|---|
| P1 | 6 | m1, m2 | m1, m2 | m3–m6 |
| P2 | 9 | m1, m2, **m9** | m1, m2 | m3–m8 |
| P3 | 8 | m1, m2 | m1, m2 | m3–m8 |

**P2 admits m9 at 9.961 GHz, above six rejected rows.** Any rule that had
hard-coded "modes 1 and 2" would have silently discarded it. It falls outside
the declared window and so does not enter the comparisons, but it is admitted
on its own evidence, and that is the point. Its *position* above six rejected
rows carries no separate information: Palace does not sort, it emits SLEPc's
converged pairs in SLEPc's order, which under `EPS_TARGET_REAL` with a target at
the band floor is simply ascending frequency.

### C.3 The diagnostic finding, and what stays unproven

The imbalance is a diagnostic finding, not a conclusion. The saved evidence
establishes *that* it occurs and bounds *what it costs us*; it does not
establish *why*.

Palace's `E_ind` is **not** the port stiffness quadratic form. It is the
rank-one surrogate `|V|²/(2ω²L)` built from the port's **area-averaged, +Y
projected** voltage functional, whereas the stiffness carries
`∫_Γ (1/L_s)|E_t|² dS`. By Cauchy–Schwarz the surrogate is a *lower bound* on
the true port energy, with equality only when the tangential field on the port
is uniform and aligned with the port direction. So a failing row is one of:

1. **an algebraically spurious Ritz vector** whose reported eigenvalue is
   meaningless; or
2. **a genuine eigenpair of `(K, M)`** whose stiffness energy sits almost
   entirely in the lumped port's Robin term, in a tangential field that is
   non-uniform or transverse to `+Y`, which the area average grossly
   understates.

**Explanation 2 is the better supported of the two, and it is still not
proven.** Four pieces of evidence point at it:

- **The projector cannot remove a port-face gradient.** Palace builds the
  auxiliary-boundary marker for its divergence-free projector as the union of
  the Dirichlet, farfield, conductivity, impedance and **lumped-port** markers
  (`palace/models/spaceoperator.cpp`), and those become the *essential* true
  dofs of the H1 spaces the projector uses. Its scalar potential is therefore
  pinned to zero on the inductive port face, so a discrete gradient whose
  potential varies *on that face* lies outside the projector's range. Palace's
  own source records the residue in a commented-out line beside it:
  *"Mark all boundaries … As tested, this does not eliminate all DC modes!"*
- **The inductor lifts such a gradient off zero.** The objection that a gradient
  mode must sit at `ω = 0` does not hold here: the lumped inductance enters the
  *stiffness* as a Robin surface term `(1/L_s)∫_Γ |E_t|² dS`, so any gradient
  with a nonzero tangential trace on the port face has strictly positive
  stiffness energy and a finite `ω²`.
- **The failing rows form one family.** `(E_mag + E_ind)·f²`, proportional to
  the measured stiffness energy of the unit-normalised field, spans a factor of
  only **4.84** across all 16 failing rows — three different discretisations,
  frequencies from 6.70 to 9.67 GHz — while the 7 admitted rows span a factor of
  74 and sit two to five orders of magnitude higher.
- **A residual bound points the same way, without closing it.** From
  `|xᴴr| ≤ ‖x‖‖r‖` with `r = Kx − μMx`, and `R` near zero, the failing rows'
  mass-matrix Rayleigh quotient is bounded by `Err_abs/μ`: they must be strongly
  *localised* vectors, which is what explanation 2 predicts and explanation 1
  does not naturally produce. Whether that bound is outright impossible depends
  on `‖M‖`, which this record does not carry — so this supports explanation 2
  without excluding explanation 1.

None of that is proof. What would be proof is field output, and there is none.
An earlier note called these rows *"null-space / gradient artefacts that the
divergence-free projection did not remove"* — asserting flatly what the evidence
supports only conditionally, and naming a mechanism (failed projection) that is
not quite the one the source suggests (a gradient family the projector is
*structurally unable* to reach). It is withdrawn and replaced by the reading
above, at its proper strength.

It does not need to be settled for the rule to be sound, because the reported
participation `p = E_ind/(E_elec + E_cap)` is computed from the **same**
surrogate. Under either explanation the `p` of a failing row is not a quantity
on which two independent solves may be compared. That is precisely what the
rule screens, and it is the strongest claim the evidence supports.

It does, however, cost mode budget. At order 1 (P2) three admitted modes were
found below 10 GHz; at order 2 on the **byte-identical mesh** (P1) six converged
rows yielded only two, because four failing rows occupied slots 3–6 and the
third admitted mode was never reached. The family **dilutes the requested mode
count**, and `eigenmodes_requested` should be chosen from the admitted yield
rather than from the number of rows wanted.

**Missing diagnostics.** Settling the cause needs one of:

| diagnostic | what it would show | why it is absent |
|---|---|---|
| per-mode port stiffness `∫_Γ (1/L_s)\|E_t\|² dS / (2ω²)` | whether the reported `E_ind` understates the true port energy, separating explanation 2 from 1 | Palace v0.13.0 never writes it |
| the saved mode fields | direct inspection of `E_t` on the port and of `∇·(εE)` in the volume | all three configs set `Solver.Eigenmode.Save = 0`, so no fields were written |
| per-mode `‖x‖₂`, `xᴴKx`, or an M-norm-relative residual | the Rayleigh quotient independent of the surrogate | Palace v0.13.0 emits none of them |

## D. Mode matching

**ESTABLISHED for both comparisons, under a rule that can refuse.**

Two runs are put in correspondence only when two *independent* one-to-one
pairings over the admitted in-window modes agree: by ascending frequency, and
by descending `|p|`. Frequency and participation are independent quantities, so
their agreement is evidence; the participation *ordering* is used only to
confirm or contradict, never to select. A separation guard then requires each
pair's frequency shift to be below half the smallest adjacent-mode spacing in
either run, so no swap is possible. The rule **refuses to report a comparison**
when the runs admit different numbers of in-window modes, when the two pairings
disagree, or when the guard fails.

Row correspondence is checked before any of this, rather than assumed. The five
per-mode tables are joined on the `m` column, never by position, and two
identities that span them are verified:

| identity | ties together | worst relative mismatch over 23 rows |
|---|---|---|
| `\|p_j\| == E_ind/(E_elec + E_cap)` | `port-EPR.csv` ↔ `domain-E.csv` | `4.24e-10` |
| `\|V_j\| == 2πf · L_j · \|I_j\|` | `port-V.csv` ↔ `port-I.csv` ↔ `eig.csv` | `2.71e-10` |

In the pinned source all five tables are written from one loop over the same
converged-mode index, with the literal value `i+1` in the `m` column, so the
correspondence also holds by construction. The row *count* is the converged
count, not the requested `N = 6` — which is why P2 has nine rows — and the
emission *order* is SLEPc's, not something Palace guarantees; this analysis
never relies on row order, only on the `m` key.

### D.1 The comparison convention

`Δ|p| = abs(|p_a| − |p_b|) / max(|p_a|, |p_b|)` — **magnitudes**. This is the
corrective change. The denominator and the `1e-2` tolerance are unchanged.

Palace's participation sign is `sign(Re I)`. Its port current is computed as
`I = V/(iωL)` exactly, so `arg(I) = arg(V) − 90°` identically and the ratio
`V/I` is the constant `iωL`, carrying no information. The sign is therefore
`sign(Im V)`, which rotates with the eigenvector's overall complex phase, and
the pinned Palace tree contains no phase-fixing step — its only post-solve
normalisation is multiplication by a real, non-negative scalar. With a single
inductive port there is no second phase reference in the solve. **The sign is a
gauge choice, not a physical current direction**, and an earlier note calling it
an unstable current direction is withdrawn.

A gauge-invariant *signed* observable would need a second inductive port in the
same solve, so that `arg(I₁) − arg(I₂)` could be compared, or the saved fields.
Neither exists here. The signed participations and the complex port currents are
preserved verbatim in the machine-readable record; only the comparison uses
magnitudes.

## E. Mesh convergence

**NOT ESTABLISHED. This is the open question.**

On matched admitted modes, with magnitudes:

| comparison | pair | Δf | Δ\|p\| |
|---|---|---|---|
| P1 vs P3 — halo, order 2 both | m1 ↔ m1 | **4.49e-2** | 3.36e-4 |
| | m2 ↔ m2 | **1.24e-2** | 2.44e-1 |
| P1 vs P2 — element order, identical mesh | m1 ↔ m1 | **3.22e-1** | 5.47e-4 |
| | m2 ↔ m2 | **1.17e-1** | 2.24e-1 |

Against the frozen `Δf ≤ 1e-4` the halo comparison fails by 124× and 449×. That
is the **third predeclared outcome** of `execution-proposal.md` §4.2, written
before the pilot ran: a frequency moving that much between two size fields at
one refinement level is not a halo verdict at all. **NOT-A-HALO-VERDICT** —
the 0.08 mm halo is neither admitted nor rejected, the criteria are not
loosened, and `Δ|p|` is not carried into `δ_A` because there is no admissible
halo to carry it from.

The order comparison is the sharper statement: a **32 % shift in the
fluxonium-like frequency from p-refinement on a byte-identical mesh**. At mesh
level 1 the discretisation error dwarfs both knobs under test.

Two measured costs bound what can be done about it. P3 used **95 % of its
45-minute cap**, and the time is the AMS preconditioner setup (1769 s of P3's
2567 s; 1340 s of P1's 2008 s) rather than the eigensolve (3.3 s and 2.3 s).
A level-2 mesh at order 2 fits neither the cap nor the DOF rule.

---

## F. Corrections owed

| withdrawn | replacement |
|---|---|
| *"Only mode 1 and mode 2 of each solve are physical circuit modes."* | Admission is per row. P2 admits m1, m2 **and m9**; P1 and P3 admit m1 and m2. No index is hard-coded. |
| The rejected rows are *"null-space / gradient artefacts that the divergence-free projection did not remove."* | The rows fail the reported energy balance. The cause is **SUPPORTED-NOT-PROVEN**, not established: `E_ind` is a rank-one surrogate that lower-bounds the true port energy, so the row is either not an eigenvector at its frequency or an eigenvector whose port field is strongly non-uniform — the second being the better supported of the two (§C.3). Either way its reported `p` is untrustworthy. |
| *"the current direction through the port is not stable under discretisation"* | The participation *sign* is `sign(Re I)` and `I = V/(iωL)` exactly, so the sign tracks the eigenvector's arbitrary global phase. It is a gauge artefact, not a physical current instability. |
| The published halo numbers `Δp = 1.648`, `Δf = 6.22e-2`. | Those compared two unmatched **rejected** rows (P1 m3 at 8.846 GHz against P3 m3 at 8.296 GHz) with a **signed** participation difference. On matched admitted modes the figures are `Δf = 4.49e-2` / `1.24e-2` and `Δ|p| = 3.36e-4` / `2.44e-1`. The verdict is unchanged. |
| *"bit-for-bit"* identical between pilot attempt 1 (run 35048375845) and the committed re-run. | **Qualified.** Attempt 1's files were never committed and its artifact was not retrievable here, so the comparison rests on the eigenfrequencies and backward errors printed in that run's log, which agree with the committed record to every digit printed — 6, 9 and 8 modes for P1, P2, P3. That is agreement to the precision the log carries, not a raw-file or hash comparison. Settling it would need attempt 1's `postpro/` files or their digests. |

## G. Status of the rules introduced here

| rule | for this record | for the next confirmatory run |
|---|---|---|
| admission `\|R − 1\| ≤ 1e-3` | **retrospective** — the solves ran before it existed and are re-read, never re-run, under it | **prospective** — declared in advance, and not changeable after the numbers are seen |
| matching: two agreeing orderings + separation guard | retrospective | prospective |
| comparison on `\|p\|` | retrospective | prospective |
| row-correspondence tolerance `1e-6` | retrospective | prospective |

None is a physical QMHP threshold. None gates a coupling. The frozen halo
criteria, the backward-error tolerance and the 10 % agreement
`ENGINEERING-RULE` are untouched.

## H. The next numerical test

**An order-1 mesh-refinement sequence at fixed 0.08 mm halo, with
`Solver.Eigenmode.Save` enabled.** One test, two answers.

*Why order 1.* Nothing currently establishes that the discretisation converges
at all, and that is the only fact that decides whether the extraction is
executable. Order 1 is the cheap probe: P2 measured **32.4 s at 39 832 DOF**
against P1's **2009.7 s at 208 670 DOF** on the byte-identical mesh, a factor of
62. A sequence that is unaffordable at order 2 is affordable at order 1. Because
both orders discretise the same continuous problem, the mesh order 2 needs for a
given accuracy is no worse than the mesh order 1 needs, so an order-1 sequence
gives a **conservative bound on the mesh requirement** — and the measured
order-1-to-order-2 offset at fixed mesh (32 % on `f₁`) is already in hand to
place it.

*Why the field output, at no solver cost.* §C.3's cause is the one thing this
record leaves unproven, and the diagnostic that settles it is the saved mode
fields. Enabling them costs disk and a little I/O, not solver time, and order-1
solves are the cheapest place to pay it. The fields would show directly whether
the failing rows are curl-free in the bulk with their energy concentrated on the
port face, confirming or refuting explanation 2. The same solves would also
measure how the failing family behaves under refinement, which is what sets
`eigenmodes_requested` for any later order-2 run.

*What it would settle that this record cannot.* Whether `f` and `|p|` for the
admitted modes converge under refinement, at what observed rate, hence what mesh
a target tolerance needs and therefore what an order-2 run would cost — and,
separately, what the 16 failing rows actually are.

*Proposed cost.* Level 1 is already in hand (P2). **Two further order-1 solves**
(levels 2 and 3), each capped at 45 minutes, one job on the existing runner,
**no additional or purchased compute**. The existing offline `dry_run` measures
each level's DOF at zero solver cost *before* anything is launched; any level
that exceeds the 250 000-DOF rule is **not** run and returns to review as a
resource decision rather than being quietly waived. Field output is kept as a
workflow artifact and only the derived per-mode diagnostics are committed, so
the record does not grow by hundreds of megabytes. We hold exactly one order-1
timing point, so the sequence's wall clock cannot be extrapolated honestly in
advance — the first rung is the measurement that fixes it, and the 45-minute cap
bounds the exposure either way.

*What it is not.* It is not a coupling extraction, not Route A or Route B, and
it changes no geometry: the same declared cell, the same halo, the same port,
the same frozen criteria. It is a convergence measurement and a diagnostic.

**Disposition: the extraction stage REQUIRES ANOTHER BOUNDED NUMERICAL CHECK.**
Not READY, and not BLOCKED in the sense of being unexecutable — the open
question is mesh convergence and its cost, and the test above is the cheapest
way to close it.
