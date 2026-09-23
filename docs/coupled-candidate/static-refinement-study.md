# The static-only nested refinement study — PREPARED, NOT APPROVED, NOT EXECUTED

**Status: PREPARED, NOT APPROVED, NOT EXECUTED.** No linear solve has been run on the QMHP
mesh for this study, and no attempt has been spent. The following have run:

- the solver verification, on synthetic cases only;
- a dry run of the solve path and its per-solve evidence writes, on a synthetic stand-in
  larger than the QMHP ladder;
- a preflight on the QMHP mesh that refines and assembles (including an extended-precision
  re-assembly) but solves nothing.

This is **revision 3** of the preparation.

- Revision 1 (`864c0ba`) was reviewed adversarially on a frozen snapshot. The review confirmed
  10 major findings, recorded 25 minor ones, and found nothing blocking.
- Revision 2 (`9aa951f`) was reviewed the same way:
  - 3 new major findings were confirmed;
  - 2 revision-1 majors were confirmed as only partly fixed;
  - 21 new minor findings and 3 partly fixed revision-1 minors were recorded;
  - nothing was blocking.
- One of those majors was push CI: revision 2's commit was red on CI (§7).
- Every finding is addressed below, before approval and before any QMHP solve, so no result
  can have informed the changes.
- Both reviews are kept verbatim in `review/`.
- A targeted closure check of the round-2 majors, run on the frozen revision-3 commit
  `3270469` with `9aa951f` as the pre-fix control, found every mechanism reproduced before
  the fix and absent after it, with two minor residuals (`review/closure_3270469.json`).

Record: `experiments/static-refinement-study/`. The frozen statement is `predeclaration.json`;
this page summarises it.

Unchanged by this preparation:

- Route A, the first-moment diagnostic and the registered definitions;
- the executed static-anchor record and its verdict, **UNRESOLVED**;
- the withdrawn paired test, `experiments/static-band-pairing/` (pinned byte for byte by a
  test).

`E_C,F1F1` and `g` stay **UNAVAILABLE**. Nothing here is combined with Route A.

## 1. What the study measures, and why

It measures two electrostatic capacitances of the island, on the committed mesh (level 0) and
on its first and second uniform red refinements (levels 1 and 2):

- `C_h`: the island at 1 and every other conductor at 0. This is the static-anchor quantity.
- `C'_h`: the same, with the port-face potential also held linear along the port.

From these come:

- `S_h = 1/((2π)² L_F C_h)`;
- `δ_h = C'_h/C_h − 1`;
- `S'_h = 1/((2π)² L_F C'_h)`.

**The link to Palace is a hypothesis.**

- Under the sheet-port identity, `S'_h` would be `H_h`, Palace's complete harmonic moment on
  that mesh. For levels 1 and 2 it is the moment Palace *would* have if given those red-refined
  meshes, which Palace has never been run on.
- The identity is verified only on the project's own dense-pencil model of Palace's port
  (`static-band-pairing.md` §2), not against Palace. The solver module's docstring now says so
  too; revision 2 had missed that line.
- The level-0 consistency check (§4) is its first test against Palace. **`S'_h` is reported
  under the name H only in a QUALIFIED record whose level-0 check is CONSISTENT**; otherwise it
  is reported as `Sprime_static_identity_not_confirmed`. An UNQUALIFIED record reports no
  second-moment value under any name.

The static-anchor test stopped at UNRESOLVED because one refinement step moved `C` by 28 %.
This study asks the next question with three nested levels: **does `C_h` converge at the rate
theory predicts, and what limit does that imply?**

**Known before execution, and stated in the pre-declaration:**

- **`C_0` and `C_1` are known.** They are 114.339 fF and 82.202 fF from the executed record,
  so the class of `C` is a function of `C_2` alone; the intervals are in §4.
- **CONVERGED is unreachable for `C`, and effectively for `C′`, `S` and `H`.**
  - For `C`, the conservative remaining error inside the CONVERGING window is at least 0.1214.
    Its minimum is 0.121483, at `R` = 4.
  - For `C′`, CONVERGED needs `d1′/C′_1 ≤ τ/(1/4 + τ/2)` = 0.1818. With `δ_0` inside the
    consistency window, that means `δ_1 ≥ 0.1777`: the exact threshold is 0.17773–0.17775,
    about 270 times `δ_0`.
  - Revision 2 stated these two figures as 0.1215 and 0.178. Both were rounded the wrong way.
  - So the 5 % tolerance decides nothing here and is kept only as a definition.
- **The classes of `C′`, `S` and `H` are not independent evidence.** They follow `C`'s class
  up to `O(δ)`.
- **`δ_0 ≥ 6.585e-4` is a prediction, not a known value.** It holds only under the identity.

## 2. The level-2 solver and its error bound

Levels 0 and 1 are solved directly, exactly as the executed record was, and must reproduce
its `C_0` and `C_1` to 1e-10. Level 2 has 584,914 unknowns and is solved by **preconditioned
conjugate gradients with a symmetric two-grid preconditioner**:

- Gauss–Seidel smoothing;
- an exact coarse correction with the Galerkin operator `PᵀAP` of level 1.

Level 1 is also solved this way, as an in-run cross-check on the real operator.

**Every energy carries a bound that is rigorous relative to the assembled operator**, for
direct and iterative solves alike (proof in `nested_solver.py`):

- **An inexact solve can only raise the energy.** With the Dirichlet data exact,
  `E(φ̃) − E_h = r_sᵀ A_s⁻¹ r_s ≥ 0`, so the solver never understates `C_h`. Here `r_s` is the
  true residual of the *symmetric* problem the energy sees, including the assembled matrix's
  asymmetry.
- **The Poincaré step needs a tiling, and holds up to ρ.** If the mesh tiles its bounding box
  `B` and every boundary node is constrained, then the **exact** Galerkin matrix satisfies
  `A ≥ ε_min λ₁(B) D_m`. Tiling means:
  - conforming;
  - every interior face separates its two tetrahedra;
  - every boundary face lies on the surface of `B`;
  - the volumes sum to `vol(B)`.

  The assembled matrix differs from the exact one by round-off, so `A_s ≥ (c − ρ) D_m`.
  `BOUND_SAFETY` = 1.001 is declared to cover `1/(1 − ρ/c)` for `ρ/c` up to 5e-4. Revision 2
  applied the step to the assembled matrix without saying so.
  `ρ` is not certified. The preflight estimates it (a Gershgorin bound against an
  extended-precision re-assembly) on every level of the QMHP ladder: at most **4.9e-7**
  (§5).
- **The evaluation error.** The energy is re-evaluated in 80-bit extended precision. The
  worst-case `n`-term factor multiplies only `Σ|φ_i y_i|`, which has no cancellation.
- **The arithmetic is probed, not only the format.** A 53-bit x87 precision-control word
  passes a storage-format check but not the arithmetic this bound assumes. Every evaluation
  therefore re-runs a probe: `(1 + 2⁻⁶⁰) − 1` through scalar, CSR and dot operations in long
  double. A failed probe is an integrity failure, and a pre-spend refusal.
- **The assembly term is measured, not asserted.** Revision 2 asserted one universal figure,
  which its own V1 row contradicted. The round-off of assembling `K` is common to every solver and is **not** certified. Its
  first-order effect on an energy is `φᵀ(K − K_exact)φ`, and it depends on the problem:
  - 1.3e-13 relative on V1's layered box, which fully explains V1's known-answer discrepancy
    (V7);
  - 5e-17 to 3e-15 on the QMHP-like chip cells.

  The summary reports it beside each bound as an **estimate**, `max|φ|² Σ|K − K_ld| / E`, with
  `Σ|K − K_ld|` taken from the preflight. The one rigorous bound, `C ≤ C_2(1 + certified
  error)`, is therefore rigorous relative to the assembled operator, up to `ρ`.

**Integrity judges the certificate, not the solver.** Only the certificate is compared with
1e-9, because it does not depend on how `x` was obtained. The PCG status and the Gauss–Seidel
probes are recorded diagnostics.

**The stagnation rule counts finite and infinite checks separately.**

- Finite certificates are compared with the best finite certificate.
- Infinite ones, where the bound still exceeds the energy, are compared with the best true
  residual.
- A stuck solve whose certificate never becomes finite now stops after 20 checks. Revision 2
  ran it to `maxiter`.

**Verification before any QMHP solve** (`solver_verification.json`, synthetic only):

| check | result |
|---|---|
| V1 continuum known answer (accuracy only) | direct and two-grid (also from zero) within 5.4e-15, 1.8e-14 and 1.3e-13 of the continuum energy at levels 0–2; the level-2 figure is the assembly term (V7) |
| V1b the total bound against the exact rational discrete minimum | holds for direct and two-grid. At these converged solutions the total is dominated by the evaluation bound, now reported separately, so V1b does **not** test the residual certificate. Revision 2 called it "tight" |
| V1c **the residual certificate against the exact rational excess** (new) | holds at all 13 PCG iterates from zero (16–25,000 times the true excess). Along the lowest mode of `(A_s, D_m)`, where it is tightest, the margin is **7.05**. The negative control `c × 10` fails |
| V2 two-grid against direct at level 2, two QMHP-like cells (349k and 992k tets), C and C′ | agree to 1.1e-16 to 5.7e-16; CERTIFIED in 65–120 iterations |
| V3 the bound at every iterate (202 iterates, prolonged and zero starts) | always holds, 8.7e3–1.1e5 times loose; every iterate's energy ≥ the direct solution |
| V4 bit identity with the reviewed code | C = `static_capacitance` and C′ = `spectral.port_constrained_energy`, bit for bit; dense sheet-port identity: `N − 1` = 1.9e-11, `Σp/λ / (L C′) − 1` = 3.8e-11 |
| V5a–g truncated solve; bar with free sides; non-nested P; indefinite preconditioner; zero start; perturbed solution; folded mesh | each detected or covered; the folded mesh is caught by the tiling checks, and the formula would understate its error 1.8× |
| V5h **the stagnation rule** | infinite checks with a falling residual, then convergence: CERTIFIED. Flat infinite checks: STAGNATED. Flat finite checks: STAGNATED. A real stuck solve (masked preconditioner): STAGNATED at 115 iterations with no finite check |
| V6 **the evaluation bound against exact rational arithmetic** | the total covers the float64 error on every case, 2.8–33× tighter than revision 1's at the solutions. The extended value is covered by its **analytic** terms alone, also on rows with heavy cancellation (`φ + 10³`). The float64 negative control breaks those terms on 2 of the 4 cancellation rows |
| V7 **the assembly term** (new) | `ρ/c` ≤ 2.6e-8 on the chip cells; the estimate covers the first-order effect everywhere; the layered box's V1 discrepancy is the assembly term to within its certificate |

## 3. Integrity: what makes the record UNQUALIFIED, and what makes it FAILED

**UNQUALIFIED.** No class is read, but the raw values are kept. Any of:

- a failed precondition: tiling, tagged boundary, constrained boundary, or the port-face
  rectangle with its conductor nodes only on the end lines;
- a missing, non-finite or non-positive value;
- any of the six energies, or either level-1 cross-check, not certified to **1e-9**, or a
  failed long-double arithmetic probe;
- a Galerkin identity worse than 1e-12, or a coarse leak;
- a level-1 disagreement between direct and two-grid beyond their bounds;
- a port voltage ≠ 1, on any solve including the cross-checks;
- `C′ < C`, or an energy rising under refinement;
- **`C_0` or `C_1` not reproducing the executed record to 1e-10.** This check runs inside the
  attempt, because every QMHP solve must happen inside a recorded attempt.

**The level-0 scope.** The level-0 items alone qualify the level-0 consistency verdict. They
are its digest, preconditions and values, its **two** certified energies (`C_0` and `C′_0`),
its port voltages, `C′_0 ≥ C_0`, and `C_0` reproduction. There is one cross-level exception.
If levels 0 and 1 both pass their own items and an energy still rises from level 0 to level 1
beyond the bounds, the fault could be at level 0. The level-0 verdict then becomes
UNQUALIFIED (fail-closed).

**How the verdict is written.**

- The verdict is written to `consistency-level0.json` as soon as level 0 completes.
- If that analysis itself raises, `consistency-level0.error.json` is written instead, and the
  solves go on. In revision 2 an analysis fault there ended the attempt.
- `failure.json` reads the verdict back from the file and never recomputes it. Revision 2
  recomputed it inside the `failure.json` write, so a fault there could lose both
  `failure.json` and the manifest.

**FAILED.** An exception after the attempt is spent gives FAILED: a refusal inside the run, a
budget limit, a stop signal or a crash. The record then holds `failure.json`, every raw file
already written, and a verified manifest, on every catchable path (§6).

**REFUSED.** Nothing is spent. The run refuses on any mismatch of the mesh, a refined-mesh
digest, the band columns, the static-anchor record, the pre-declaration, the code, the
environment, the **measured invocation**, or the approval.

## 4. The frozen classification, and the consistency check

The rule works on `d1 = X0 − X1`, `d2 = X1 − X2` and `R = d1/d2`, each over its certified range.

**The theory behind the window.**

- **Leading order.** Every sheet edge carries an `r^{1/2}` singularity, and sheets on the
  eps interface keep it. So the energy error's leading term is `O(h)`, with a positive
  coefficient.
- **The window.** If the next term is of order `q ∈ (1, 2]` with a coefficient of the **same
  sign**, then `R ∈ [2, 4]` and the level-2 error lies between `d2/(R−1)` and `d2`.
- **The same-sign premise is an assumption the theory does not supply.** With mixed signs,
  `R < 2` and even `R < 1` can occur in the genuine order-1 regime. For example,
  `X = 5 + h − 0.5h²` gives `R` = 0.8 with positive, monotonically decreasing errors. A
  sequence inside the window can also have its limit outside the bracket.

| class | rule |
|---|---|
| **CONVERGED** | `2 ≤ R ≤ 4` and `d2/(X2 − d2)` ≤ 0.05 |
| **CONVERGING** | `2 ≤ R ≤ 4`. The limit is reported with its **model-based** bracket `[X2 − d2, X2 − d2/(R−1)]`, not a rigorous one. The bracket carries its assumption in every block that shows it, including `S` and `H` |
| **NON-CONVERGENT** | `R < 1`: no evidence of convergence at levels 0–2. Not a claim of mathematical divergence, which density excludes. It is also consistent with order 1 and a negative next term, or with pre-asymptotic behaviour. **Not** evidence against the order-1 theory |
| **UNRESOLVED** | `1 < R < 2`: observed order below 1. `R > 4`: observed order above 2, pre-asymptotic. Also a difference within its certified error of zero, or a certified range touching a class edge (fail-safe) |
| **UNQUALIFIED** | any integrity failure |

**`δ` is classified descriptively.** No rate theory exists for it, so it gets no bracket and
no CONVERGED. Its classes are UNRESOLVED, NON-CONVERGENT or DIFFERENCES-SHRINKING.

**What is rigorous regardless of the class:** `C ≤ C_2` and `S ≥ S_2`, each widened by its
certificate. They are rigorous relative to the assembled operator up to `ρ`, and they hold by
the Dirichlet principle. The basis says it covers these two values only; the assembly-term
estimate sits beside them.

**`C_2` intervals, stated before `C_2` exists** (`d1` = 32.137 fF):

| `C_2` | class |
|---|---|
| ≤ 50.066 fF | NON-CONVERGENT |
| 50.066–66.134 fF | UNRESOLVED (observed order below 1) |
| **66.134–74.168 fF** | **CONVERGING** |
| 74.168–82.202 fF | UNRESOLVED (observed order above 2) |
| > 82.202 fF | UNQUALIFIED (nesting forbids it) |

**The level-0 consistency check — a cross-code test of the identity, not an acceptance
criterion.**

- **The prediction.** The identity forces `δ_0` into `[6.5852e-4, 6.7622e-4]`, widened by
  **η = 1e-8** and fixed now.
- **What η covers:**
  - CSV precision;
  - Palace's backward errors, with an *estimated* forward error;
  - the level-0 certificates up to their 1e-9 tolerance;
  - LossTan 0;
  - an assembly-difference term between the two codes, which is an estimate.

  The derivation now gives the weak-mode sensitivity correctly. A relative `p` error of
  1.3–2.8 % moves the lower edge by more than η for modes 3–5, and about 15 % does so for
  mode 6, which cannot move the upper edge.
- **CONSISTENT.** In a QUALIFIED record, `S′_h` is reported as `H_h`.
- **INCONSISTENT-LOW or INCONSISTENT-HIGH.** Both list the same possible causes:
  - the identity as applied to Palace's pencil;
  - the **static C′ implementation**;
  - `N ≠ 1`;
  - a `p`-definition mismatch;
  - weak-mode `p` inaccuracy;
  - for HIGH only, a missed mode.

  Revision 2's HIGH list omitted the static side. The second moment is named
  `Sprime_static_identity_not_confirmed`.
- **UNQUALIFIED.** The level-0 scope failed, or the 0-to-1 nesting check implicated level 0.
- **None of these affects the classes of `C`, `C′` or `δ`.**
- **SIGKILL.** In a record ended by an uncatchable SIGKILL, with no driver-written manifest,
  `consistency-level0.json` is preserved as raw evidence but is **not** a verdict of the study.

**Expected classes, recorded before the run** (synthetic analogues only, not QMHP data):

- `C`: `R` = 2.76, 2.93 and 2.60 on three QMHP-like cells, so CONVERGING. The observed orders
  are 1.4–1.6: pre-asymptotic contamination by higher-order terms.
- `δ` **grew** on the dry-run cell (3.3e-4 → 1.0e-3 → 1.7e-3), so NON-CONVERGENT at these
  levels. The same is expected on the QMHP ladder, and it says nothing about the limit.

## 5. Preflight on the QMHP mesh — geometry and assembly only, no solve

`preflight.json` (95 s, 3.7 GB):

| level | tets | nodes | unknowns C / C′ | Galerkin to previous level | tiling (Σ vol / box − 1) | residual floor | evaluation matvec term | ρ/c estimate | Σ\|K − K_ld\| |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 64,434 | 13,991 | 4,558 / 4,543 | — | −1.1e-16 | 5e-20 | 1.3e-13 | 1.0e-8 | 8.8e-12 |
| 1 | 515,472 | 93,935 | 60,608 / 60,552 | 6.6e-15 | 2.2e-16 | 4e-17 | 5.7e-13 | 5.3e-8 | 4.1e-11 |
| 2 | 4,123,776 | 709,421 | 584,914 / 584,701 | 2.3e-14 | 2.2e-16 | 1.1e-15 | 2.3e-12 | 4.9e-7 | 1.8e-10 |

The floor, term and `Σ|K − K_ld|` columns are nondimensional proxies with `|φ| ≤ 1`; no solve
is involved. The `ρ/c` column is an estimate against an extended-precision re-assembly, not a
certificate.

- **Preconditions.** Every precondition holds on every level:
  - the mesh tiles its box: every interior face separates its tetrahedra and every boundary
    face lies on the box;
  - every boundary face is tagged and constrained;
  - the port face is an exact 0.01 × 0.005 rectangle.
- **What the preflight establishes about the margin.**
  - It establishes the **evaluation** part only. Relative to an energy of about 2, that part
    is about 1e-12 at level 2, against the 1e-9 tolerance.
  - The **residual** part depends on PCG reaching its target on the real operator, which is
    known only at the run. The residual floor proxy shows that the floor itself is far below
    the tolerance.
  - Revision 2 overstated this as "established on the ladder itself".
- **Frozen values.** The refined-mesh digests and the assembly-gap estimates are frozen in the
  pre-declaration, quoted exactly from this file.

## 6. The one attempt, and what the run writes

**The approval must name:**

- the commit the human reviewed, which must be HEAD at execution;
- this checkout's path;
- a validity window of at most 7 days;
- `attempt 1` and `prior_records []`.

**The ledger: three entries, created before any solve and in this order.**

1. `<git common directory>/qmhp-attempts/STATIC-REFINEMENT-STUDY.json`, created exclusively.
   No checkout, reset, clean or branch switch of this clone touches it, and neither does any
   worktree that shares its git directory. It is never committed.
2. `ATTEMPT-SPENT.json`, created exclusively.
3. The approval itself, renamed to `STUDY-APPROVAL.consumed.json`, so that no later checkout
   holds a usable approval.

The run refuses if any of the three, or any record, exists.

- **What revision 2 allowed.** Its ledger lived only in the working tree. After the record and
  marker were committed, an ordinary `git checkout` of the approved commit removed both. The
  approval, necessarily untracked, survived, and the reviewers ran a second attempt to
  completion.
- **Residual risk.** In a *fresh* clone of the approved commit, a human who deliberately
  re-writes an approval could start a second attempt. The driver cannot see across clones. The
  pushed record, the marker and the consumed approval are the ledger a reviewer checks.

**The invocation is measured, not only compared as text.** Revision 2 compared only the
approval's text. Before spending anything, `execute()` measures, records in
`provenance.json`, and refuses if any differs:

- the working directory;
- `argv`;
- the parent process's command line (`timeout --signal=KILL 3660 .venv/bin/python …`);
- the interpreter prefix (the repository's `.venv`);
- the optimisation flag;
- that bytecode caches were bypassed.

**Only bound code runs.**

- As the study, the driver sets a pycache prefix that cannot exist, so every repository module
  is compiled from its source. The digests the approval binds are therefore of the code that
  runs.
- `orchestrator/manifest.py` is loaded by path. `execute()` refuses if any other repository
  module is loaded.
- The verified Python, numpy and scipy versions and single-threaded BLAS are required, and the
  long-double arithmetic probe must pass.
- The approval and pre-declaration digests come from the same reads as their parsed contents.

**What the run writes, in this order.** Each file is written **atomically**: to `.partial`,
then fsync, then rename. An interruption leaves the complete file or a `.partial` one, never an
empty file under the final name. A `.partial` file is kept and sealed.

1. `provenance.json`;
2. `level0.json` (mesh facts, before any solve), `level0-C.json`, `level0-Cprime.json`;
3. `consistency-level0.json` (or `consistency-level0.error.json`);
4. `level1.json`, `level1-C.json`, `level1-C-crosscheck.json`, `level1-Cprime.json`,
   `level1-Cprime-crosscheck.json`;
5. `level2.json`, `level2-C.json`, `level2-Cprime.json`;
6. `summary.json`, or `failure.json`;
7. `manifest.sha256`, by `write_verified`.

**Stop signals: the first raises, the rest are recorded.** SIGXCPU, SIGALRM, SIGTERM, SIGHUP
and SIGINT (Ctrl-C) all end the attempt.

- **What revision 2 lost.** GNU `timeout` forwards a process-group signal to the child a
  second time. The second delivery then raised inside revision 2's failure path. On a bytecode
  loop, a Ctrl-C lost `failure.json` and the manifest in 8 of 8 trials; on the real workload,
  in 2 of 38.
- **What revision 3 does.**
  - The handler raises once. Every later delivery is recorded in `signals_received` and
    returns.
  - The failure path ignores every stop signal, cancels the alarm and lifts the soft limits.
  - Every other step it takes is guarded, so `failure.json` and the manifest are always
    written.
  - A test sends SIGINT, SIGTERM and SIGHUP to the process group of the real driver under
    `timeout` and checks the sealed record, 4 trials each.
- **Before the ledger.** The budget and handlers are installed before the first ledger entry.
  A signal or error before that entry refuses with nothing spent.
- **Before the record directory.** A failure after the ledger but before the record directory
  exists is written into the ledger entries this process created. Revision 2 spent the attempt
  with no record and a raw traceback in that case.

**What cannot be caught: SIGKILL.** A kernel SIGKILL (the hard CPU limit or the OOM killer),
or the outer timeout's SIGKILL, leaves the spent record with its raw files but with no
`failure.json` and no manifest. It must then be quarantined by content, as the static-anchor
record was. SIGALRM is armed from process start, so the outer kill really is 60 s later.

## 7. Resource estimate, the proposed command, and CI

`dry_run.json` runs the solve path and its per-solve evidence writes under the declared limits
and with single-threaded BLAS. The writes are atomic strict JSON, sealed and verified by
`write_verified`: 11 files, and the manifest verifies. It does not exercise the approval, the
ledger, provenance, the level-0 check or the summary; the gate tests do, on a small cell.

**The stand-in** is **larger** than the QMHP ladder:

- level 2: 5.0 M tets and 792 k unknowns, against 4.1 M and 585 k;
- aspect p99: 25, against 14.

But it is **not conservative for the certificate**:

- its minimum edge is 4.9 times longer (`preflight.json` against `dry_run.json`);
- its residual-certificate floor is about 100 times lower at level 1. That figure was measured
  by the round-2 review (`review/review_9aa951f.json`), not by the committed evidence.

It bounds time and memory, not the certified error.

| | stand-in, measured | QMHP, expected | declared cap |
|---|---|---|---|
| wall | 254.5 s | about 3–5 min | 60 min |
| CPU | 253.2 s | about the same (single-threaded) | 60 min |
| peak resident | 4,435 MB | 4–5 GB | — |
| peak address space | 7,315 MB | < 8 GB | 12 GiB soft, 13 GiB hard |
| level-2 PCG | 120 iterations each; 0.327 / 0.328 s per iteration; 20.0 / 26.5 s set-up | not known until the run | maxiter 1000 |
| level-2 certified error | 3.2e-13 | not known until the run (evaluation part about 1e-12) | 1e-9 |

- **Worst case within the settings.** With `maxiter` = 1000 everywhere, the run takes about
  14 min wall and about the same CPU. The caps allow about 4.2 times that.
- **Attempts.** 1. No retry.

**Proposed command, from the repository root, locally, with no workflow and no network.** It
runs only once `STUDY-APPROVAL.json` exists, filled in from `STUDY-APPROVAL.draft.json`. The
driver measures that it was started exactly this way:

    env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 3660 .venv/bin/python experiments/static-refinement-study/study_driver.py

**Push CI is not the verified environment.**

- Revision 2's environment test asserted that the test host *is* the verified interpreter.
  Push CI resolves its own Python patch release (3.11.16), so CI went red.
- The test is now hermetic. It declares an environment equal to the running interpreter and
  checks each difference as a negative control.
- The host-identity assertion runs only on the verified host and is skipped with its reason
  elsewhere.
- The repository pins Python only to 3.11. A rebuild of `.venv` with another patch release
  makes the study refuse, with nothing spent, and needs a new pre-declaration and approval.

## 8. What this study cannot establish; files

It cannot establish:

- `E_C,F1F1` or `g`;
- that Route A is valid or invalid;
- the device's capacitance (this is the meshed model);
- a rigorous continuum value or lower bound for `C` (the bracket is model-based and rests on
  an unproven sign assumption);
- anything beyond the assembled operator: its round-off is estimated, not certified, and no
  universal figure is claimed;
- `B/H`;
- Palace's box-refined operators;
- that `S′_h` is Palace's `H_h`, unless the level-0 check is CONSISTENT (and then only under
  the identity);
- convergence of `δ`.

| file | role |
|---|---|
| `predeclaration.json` | revision 3: the frozen question, method, environment, integrity, diagnostics, classification, consistency check, one-attempt ledger, invocation, budget and estimate |
| `nested_solver.py` | the two problems, the direct and two-grid solvers, the certificate, the evaluation bound, the arithmetic probe and the assembly-gap estimate, with their proofs |
| `study_driver.py` | preflight, dry run, invocation check, and the gated one-attempt execution |
| `synthetic_cells.py`, `verify_solver.py` | the synthetic cells (including the folded-mesh control) and the verification V1–V7 |
| `solver_verification.json`, `preflight.json`, `dry_run.json` | the committed evidence of the preparation, each bound to the code and environment that produced it |
| `review/review_864c0ba.json`, `review/review_9aa951f.json`, `review/closure_3270469.json` | the adversarial reviews of revisions 1 and 2, verbatim, and the targeted closure check of revision 3, with its raw outputs and harness sources |
| `STUDY-APPROVAL.draft.json` | the approval a human would grant, with the commit and window left to fill; **not** an approval |
| `tests/test_static_refinement_study.py` | rules, integrity, gate, invocation, ledger, failure paths, signals, budget, evidence, pins |
