# The static-only nested refinement study — PREPARED, NOT APPROVED, NOT EXECUTED

**Status: PREPARED, NOT APPROVED, NOT EXECUTED.** No linear solve has been run on the QMHP
mesh for this study, and no attempt has been spent. The following have run:

- the solver verification, on synthetic cases only;
- a dry run of the exact execution path, on a synthetic stand-in larger than the QMHP ladder;
- a preflight on the QMHP mesh that refines and assembles but solves nothing.

This is **revision 2** of the preparation.

- Revision 1 (`864c0ba`) was reviewed adversarially on a frozen snapshot: 10 major findings
  were confirmed, 25 minor findings were recorded, and none were blocking.
- Every finding is addressed below, before approval and before any QMHP solve, so no result
  can have informed the changes.
- The review is kept verbatim in `review/review_864c0ba.json`.

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
  (`static-band-pairing.md` §2), not against Palace.
- The level-0 consistency check (§4) is its first test against Palace. **`S'_h` is reported
  under the name H only if that check is CONSISTENT**; otherwise it is reported as
  `Sprime_static_identity_not_confirmed`.

The static-anchor test stopped at UNRESOLVED because one refinement step moved `C` by 28 %.
This study asks the next question with three nested levels: **does `C_h` converge at the rate
theory predicts, and what limit does that imply?**

**Known before execution, and stated in the pre-declaration:**

- **`C_0` and `C_1` are known.** They are 114.339 fF and 82.202 fF from the executed record,
  so the class of `C` is a function of `C_2` alone; the intervals are in §4.
- **CONVERGED is unreachable for `C`, and effectively for `C′`, `S` and `H`.** For `C′` it
  would need `δ_1 ≥ 0.178`, about 270 times `δ_0`. The 5 % tolerance decides nothing here and
  is kept only as a definition.
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
  asymmetry. Revision 1 omitted that term.
- **The Poincaré step needs a tiling.** If the mesh tiles its bounding box `B` and every
  boundary node is constrained, then `A_s ≥ ε_min λ₁(B) M ≥ ε_min λ₁(B) D_m`, and so
  `E(φ̃) − E_h ≤ Σ r_s,i²/m_i / (ε_min λ₁(B))`. Tiling means:
  - conforming;
  - every interior face separates its two tetrahedra;
  - every boundary face lies on the surface of `B`;
  - the volumes sum to `vol(B)`.

  Revision 1 did not check the tiling: a folded mesh passed its checks.
- **The evaluation error has a much tighter bound.** The energy is re-evaluated in 80-bit
  extended precision. The worst-case `n`-term factor now multiplies only `Σ|φ_i y_i|`, which
  has no cancellation. Checked against exact rational arithmetic, the new bound is valid and
  3–33 times tighter than revision 1's.
- **What "rigorous" covers.** Assembling `K` from the coordinates costs about 1e-14 relative.
  That round-off is common to every solver and is **not** certified, so "rigorous" in this
  study always means rigorous relative to the assembled operator.

**Integrity judges the certificate, not the solver.** Only the certificate is compared with
1e-9, because it does not depend on how `x` was obtained. The PCG status (CERTIFIED,
STAGNATED, MAXITER, BREAKDOWN) and the Gauss–Seidel probes are recorded diagnostics. The
stagnation rule ignores checks where the bound still exceeds the energy.

**Verification before any QMHP solve** (`solver_verification.json`, synthetic only):

| check | result |
|---|---|
| V1 continuum known answer (accuracy only; includes assembly round-off) | direct and two-grid (also from zero) within 1.3e-13 of the continuum energy |
| V1b **the bound against the exact rational discrete minimum** | holds for direct and two-grid; errors are 14–89 % of the bound, so it is tight |
| V2 two-grid against direct at level 2, two QMHP-like cells (349k and 992k tets), C and C′ | agree to 1.2e-16 to 5.7e-16; CERTIFIED in 65–120 iterations |
| V3 the bound at every iterate (202 iterates, prolonged and zero starts) | always holds; every iterate's energy ≥ the direct solution |
| V4 bit identity with the reviewed code | C = `static_capacitance`, C′ = `spectral.port_constrained_energy`, bit for bit; dense sheet-port identity to 1.4e-10 |
| V5a–f truncated solve; bar with free sides; non-nested P; indefinite preconditioner; zero start; perturbed solution | each detected or covered, as in revision 1 |
| V5g **a folded mesh** | caught by the tiling checks; the formula would understate its error 1.8× |
| V5h **the stagnation rule** | 30 infinite checks, then convergence: CERTIFIED; 20 flat finite checks: STAGNATED |
| V6 **the evaluation bound against exact rational arithmetic** | covers the true error on every case; 3–33× tighter than revision 1's |

## 3. Integrity: what makes the record UNQUALIFIED, and what makes it FAILED

**UNQUALIFIED.** No class is read, but the raw values are kept. Any of:

- a failed precondition: tiling, tagged boundary, constrained boundary, or the port-face
  rectangle with its conductor nodes only on the end lines;
- a missing, non-finite or non-positive value;
- any of the six energies, or either level-1 cross-check, not certified to **1e-9**;
- a Galerkin identity worse than 1e-12, or a coarse leak;
- a level-1 disagreement between direct and two-grid beyond their bounds;
- a port voltage ≠ 1, on any solve including the cross-checks;
- `C′ < C`, or an energy rising under refinement;
- **`C_0` or `C_1` not reproducing the executed record to 1e-10.** This check runs inside the
  attempt, because every QMHP solve must happen inside a recorded attempt.

**The level-0 scope.** The level-0 items alone qualify the level-0 consistency verdict. That
verdict is written to `consistency-level0.json` as soon as level 0 completes, so a failure at
level 1 or 2 cannot forfeit it. Revision 1 could lose it.

**FAILED.** An exception after the attempt is spent gives FAILED: a refusal inside the run, a
budget limit, SIGTERM or SIGHUP, or a crash. The record then holds `failure.json`, every raw
file already written, and a verified manifest.

**REFUSED.** Nothing is spent. The run refuses on any mismatch of the mesh, a refined-mesh
digest, the band columns, the static-anchor record, the pre-declaration, the code, the
environment or the approval.

## 4. The frozen classification, and the consistency check

The rule works on `d1 = X0 − X1`, `d2 = X1 − X2` and `R = d1/d2`, each over its certified range.

**The theory behind the window.**

- **Leading order.** Every sheet edge carries an `r^{1/2}` singularity, and sheets on the
  eps interface keep it. So the energy error's leading term is `O(h)`, with a positive
  coefficient.
- **The window.** If the next term is of order `q ∈ (1, 2]` with a coefficient of the **same
  sign**, then `R ∈ [2, 4]` and the level-2 error lies between `d2/(R−1)` and `d2`.
- **The same-sign premise is an assumption the theory does not supply.** The edge–vertex
  cutoff and red refinement's change of element shapes can break it. With mixed signs, `R < 2`
  can occur in the genuine order-1 regime, and a sequence inside the window can have its limit
  outside the bracket.

| class | rule |
|---|---|
| **CONVERGED** | `2 ≤ R ≤ 4` and `d2/(X2 − d2)` ≤ 0.05 |
| **CONVERGING** | `2 ≤ R ≤ 4`. The limit is reported with its **model-based** bracket `[X2 − d2, X2 − d2/(R−1)]`, not a rigorous one, together with the assumption it rests on |
| **NON-CONVERGENT** | `R < 1`: no evidence of convergence at levels 0–2. This is not a claim of mathematical divergence, which density excludes |
| **UNRESOLVED** | `1 < R < 2`: observed order below 1, consistent with order 1 and a negative next term, or pre-asymptotic. `R > 4`: observed order above 2, pre-asymptotic. Also a difference within its certified error of zero, or a certified range touching a class edge (fail-safe) |
| **UNQUALIFIED** | any integrity failure |

**`δ` is classified descriptively.** No rate theory exists for it, so it gets no bracket and
no CONVERGED. Its classes are UNRESOLVED, NON-CONVERGENT or DIFFERENCES-SHRINKING. The flag
"S and S′ within 1 %" covers levels 0–2 only.

**What is rigorous regardless of the class:** `C ≤ C_2` and `S ≥ S_2`, relative to the
assembled operator (Dirichlet principle), each widened by its certificate.

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
  **η = 1e-8** and fixed now. η covers CSV precision, Palace's backward errors with an
  *estimated* forward error, the certificates, and LossTan 0.
- **CONSISTENT.** `S′_h` is reported as `H_h`.
- **INCONSISTENT-LOW or INCONSISTENT-HIGH.** The identity is not confirmed on the QMHP mesh,
  and the second moment is named `Sprime_static_identity_not_confirmed`. One possible cause is
  eigenvector inaccuracy of the weak band modes 3–6.
- **UNQUALIFIED.** The level-0 scope failed, and no verdict is read.
- **None of these affects the classes of `C`, `C′` or `δ`.**

**Expected classes, recorded before the run** (synthetic analogues only, not QMHP data):

- `C`: `R` = 2.76, 2.93 and 2.60 on three QMHP-like cells, so CONVERGING. The observed orders
  are 1.4–1.6: pre-asymptotic contamination by higher-order terms.
- `δ` **grew** on the dry-run cell (3.3e-4 → 1.0e-3 → 1.7e-3), so NON-CONVERGENT at these
  levels. The same is expected on the QMHP ladder, and it says nothing about the limit.

## 5. Preflight on the QMHP mesh — geometry and assembly only, no solve

`preflight.json` (71 s, 3.7 GB):

| level | tets | nodes | unknowns C / C′ | Galerkin to previous level | tiling (Σ vol / box − 1) | residual floor | evaluation matvec term |
|---|---|---|---|---|---|---|---|
| 0 | 64,434 | 13,991 | 4,558 / 4,543 | — | −1.1e-16 | 5e-20 | 1.3e-13 |
| 1 | 515,472 | 93,935 | 60,608 / 60,552 | 6.6e-15 | 2.2e-16 | 4e-17 | 5.7e-13 |
| 2 | 4,123,776 | 709,421 | 584,914 / 584,701 | 2.3e-14 | 2.2e-16 | 1.1e-15 | 2.3e-12 |

The floor and term columns are nondimensional proxies with `|φ| ≤ 1`; no solve is involved.

- **Preconditions.** Every precondition holds on every level:
  - the mesh tiles its box: every interior face separates its tetrahedra and every boundary
    face lies on the box;
  - every boundary face is tagged and constrained;
  - the port face is an exact 0.01 × 0.005 rectangle.
- **Margin on the real ladder.** Relative to an energy of about 2, the evaluation term is
  about 1e-12 at level 2. So the margin to the 1e-9 tolerance is established on the ladder
  itself; revision 1 had not established it.
- **Frozen mesh digests.** The refined-mesh digests are frozen in the pre-declaration.

## 6. The one attempt, and what the run writes

**The ledger.** The approval must name all of the following:

- the commit the human reviewed, which must be HEAD at execution;
- this checkout's path;
- a validity window of at most 7 days;
- `attempt 1` and `prior_records []`.

Before any solve, `ATTEMPT-SPENT.json` is created exclusively, then the record directory; the
run refuses if either exists. Both stay and are committed with the record.

Revision 1's ledger was the local `results/` folder alone. A second checkout, or a deleted
record, would have allowed a second attempt. The residual risk is deliberate deletion of the
marker and record, or rewriting HEAD, both prohibited by CLAUDE.md §§1 and 9.

**Only bound code runs.** The driver loads `orchestrator/manifest.py` by path, so no package
`__init__` executes. `execute()` refuses if any repository module outside the four bound
files is loaded. Revision 1 executed 30 unbound modules. The verified Python, numpy and scipy
versions and single-threaded BLAS are required.

**What the run writes, in order:**

1. `provenance.json`;
2. for each level: `level{h}.json` (mesh facts, written before any solve), then each solve's
   raw result **as it completes** (`level{h}-C.json`, `level{h}-Cprime.json`,
   `level1-*-crosscheck.json`); revision 1 could discard a completed level-2 C solve;
3. `consistency-level0.json`;
4. `summary.json`, or `failure.json`;
5. `manifest.sha256`, by `write_verified`.

Non-finite values are written as null (strict JSON).

**The failure path.** It first disarms every budget signal and lifts the soft limits. The
address-space hard limit is 1 GiB above the soft one for this purpose. It then writes and
verifies. Revision 1 could lose the manifest under memory exhaustion by small allocations; a
test now shows it survives.

**What cannot be caught: SIGKILL.** A kernel SIGKILL (the hard CPU limit or the OOM killer),
or the outer timeout's SIGKILL, leaves the spent record with its raw files but with no
`failure.json` and no manifest. It must then be quarantined by content, as the static-anchor
record was. SIGALRM is armed from process start, so the outer kill really is 60 s later.

## 7. Resource estimate and the proposed command

`dry_run.json` runs the exact execution path under the declared limits and with
single-threaded BLAS. Its stand-in is **larger** than the QMHP ladder and has **worse**
elements:

- level 2: 5.0 M tets and 792 k unknowns, against 4.1 M and 585 k;
- aspect p99: 25, against 14.

| | stand-in, measured | QMHP, expected | declared cap |
|---|---|---|---|
| wall | 211.6 s | about 3–4 min | 60 min |
| CPU | 210.5 s | about the same (single-threaded) | 60 min |
| peak resident | 4,516 MB | 4–5 GB | — |
| peak address space | 7,316 MB | < 8 GB | 12 GiB soft, 13 GiB hard |
| level-2 PCG | 120 iterations each; 0.294 / 0.291 s per iteration; 16.8 / 21.6 s set-up | not known until the run | maxiter 1000 |
| level-2 certified error | 3.2e-13 | about 1e-12 (preflight proxy) | 1e-9 |

- **Worst case within the settings.** With `maxiter` = 1000 everywhere, the run takes about
  13 min wall and about the same CPU. The caps allow about 4.6 times that.
- **Attempts.** 1. No retry.

**Proposed command, from the repository root, locally, with no workflow and no network.** It
runs only once `STUDY-APPROVAL.json` exists, filled in from `STUDY-APPROVAL.draft.json`:

    env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 3660 .venv/bin/python experiments/static-refinement-study/study_driver.py

## 8. What this study cannot establish; files

It cannot establish:

- `E_C,F1F1` or `g`;
- that Route A is valid or invalid;
- the device's capacitance (this is the meshed model);
- a rigorous continuum value or lower bound for `C` (the bracket is model-based and rests on
  an unproven sign assumption);
- anything beyond the assembled operator;
- `B/H`;
- Palace's box-refined operators;
- that `S′_h` is Palace's `H_h`, unless the level-0 check is CONSISTENT (and then only under
  the identity);
- convergence of `δ`.

| file | role |
|---|---|
| `predeclaration.json` | revision 2: the frozen question, method, environment, integrity, diagnostics, classification, consistency check, one-attempt ledger, budget and estimate |
| `nested_solver.py` | the two problems, the direct and two-grid solvers, the certificate and the evaluation bound, with their proofs |
| `study_driver.py` | preflight, dry run, and the gated one-attempt execution |
| `synthetic_cells.py`, `verify_solver.py` | the synthetic cells (including the folded-mesh control) and the verification V1–V6 |
| `solver_verification.json`, `preflight.json`, `dry_run.json` | the committed evidence of the preparation, each bound to the code and environment that produced it |
| `review/review_864c0ba.json` | the adversarial review of revision 1, verbatim |
| `STUDY-APPROVAL.draft.json` | the approval a human would grant, with the commit and window left to fill; **not** an approval |
| `tests/test_static_refinement_study.py` | rules, integrity, gate, ledger, failure paths, budget, evidence, pins |
