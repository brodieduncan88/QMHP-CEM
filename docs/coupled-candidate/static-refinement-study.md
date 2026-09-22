# The static-only nested refinement study — PREPARED, NOT APPROVED, NOT EXECUTED

**Status: PREPARED, NOT APPROVED, NOT EXECUTED.** No linear solve has been run on the QMHP
mesh for this study, and no attempt has been spent. The following have run:

- the solver verification, on synthetic cases only;
- a dry run of the exact execution path, on a synthetic stand-in of QMHP size;
- a preflight on the QMHP mesh that refines and assembles but solves nothing.

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
- `δ_h = C'_h / C_h − 1`;
- `H_h = S_h/(1 + δ_h) = 1/((2π)² L_F C'_h)`. By the sheet-port identity
  (`static-band-pairing.md` §2, verified to 1e-12), this is Palace's **complete** harmonic
  moment on that mesh. It is **derived through the identity, not measured by Palace**.

The static-anchor test stopped at UNRESOLVED because one refinement step moved `C` by 28 %.
This study asks the next question with three nested levels: **does `C_h` converge at the rate
theory predicts, and what limit does that imply?** It also measures `δ_h`, which is how far
Palace's distributed port departs from the declared lumped port in the static moment.

**Already known before execution, and stated in the pre-declaration:**

- `C_0` = 114.339 fF and `C_1` = 82.202 fF (executed record). The class of `C` is therefore a
  function of `C_2` alone; the intervals are in §4.
- `δ_0 ≥ 6.585e-4`, from the band data.

## 2. The level-2 solver and its rigorous error bound

Levels 0 and 1 are solved directly, exactly as the executed record was, and must reproduce
its `C_0` and `C_1` to 1e-10. Level 2 has 584,914 unknowns and is solved by **preconditioned
conjugate gradients with a symmetric two-grid preconditioner** on the nested hierarchy:

- Gauss–Seidel smoothing;
- an exact coarse correction with the Galerkin operator `PᵀAP` of level 1.

Level 1 is also solved this way, as an in-run cross-check on the real operator.

**Every energy carries a rigorous a-posteriori bound**, for direct and iterative solves alike
(proof in `nested_solver.py`):

- With the Dirichlet data imposed exactly, `E(φ̃) − E_h = rᵀA⁻¹r ≥ 0`. An inexact solve can
  only **raise** the energy, so the solver never understates `C_h`.
- Every outer-boundary node is constrained, and this is checked on every level. So a
  homogeneous discrete function lies in `H¹₀` of the bounding box `B`, and

      A ≥ ε_min λ₁(B) M ≥ ε_min λ₁(B) D_m,   D_m = diag(Σ vol/20)

  hence `E(φ̃) − E_h ≤ Σ r_i²/m_i / (ε_min λ₁(B))`.
- `r` is the true residual, bounded including its own floating-point evaluation. The energy's
  evaluation error is bounded by re-evaluating it in 80-bit extended precision.

The bound is relative to the assembled matrix. Assembly round-off is common to every solver
and is not certified.

**Verification before any QMHP solve** (`solver_verification.json`, synthetic only):

| check | result |
|---|---|
| V1 exact known answer (layered box, exact potential at every level) | direct and two-grid (from zero) within 1.3e-13 of exact |
| V2 two-grid against direct at level 2, two QMHP-like cells (349k and 992k tets), C and C′ | agree to 1.2e-16 to 5.7e-16; bounds ≤ 3e-12; CERTIFIED in 65–120 iterations |
| V3 the bound at EVERY iterate (202 iterates over four runs, prolonged and zero starts) | always holds; every iterate's energy ≥ the direct solution; loose by 8.7e3–1.1e5 (that costs iterations, not validity) |
| V4 bit identity with the reviewed code | problem C = `static_capacitance`, problem C′ = `spectral.port_constrained_energy`, bit for bit; the dense sheet-port identity holds to 1.4e-10 |
| V5a truncated solve | not certified; its error still inside its bound |
| V5b the precondition is necessary | bar with free sides: reported, `A ≥ cM` fails, and the formula understates a real error 40× |
| V5c non-nested prolongation | Galerkin check 0.37 (caught); PCG still certifies the same energy |
| V5d indefinite preconditioner | BREAKDOWN, never CERTIFIED |
| V5e / V5f zero start; perturbed solution | certified; the energy rises and the bound covers it |

## 3. Integrity: what makes the record UNQUALIFIED

Any of the following makes the record **UNQUALIFIED**. No class is read from it, although its
raw values are kept.

- a refined mesh differing from its pre-declared digest (this check runs before the attempt is
  spent);
- a failed precondition: conformity, tagged boundary, constrained outer boundary, or the
  port-face rectangle with its conductor nodes only on the end lines;
- a missing, non-finite or non-positive value;
- any of the six energies (or the two level-1 cross-checks) not certified to **1e-9**;
- a two-grid solve not CERTIFIED;
- a Galerkin identity worse than 1e-12, or a coarse leak into constrained nodes;
- level-1 direct and iterative results disagreeing beyond their bounds;
- a port voltage ≠ 1;
- `C′ < C` or an energy rising under refinement, beyond the bounds;
- **`C_0`, `C_1` not reproducing the executed record to 1e-10.**

## 4. The frozen classification: convergence, non-convergence, UNRESOLVED

The rule works on `d1 = X0 − X1`, `d2 = X1 − X2` and `R = d1/d2`, each over its certified range.

**The theory behind the window.** The energy error is `‖u − u_h‖²_a`.

- Every sheet edge carries an `r^{1/2}` singularity. The eps-interface transmission condition
  keeps it at 1/2, so the leading term is `O(h)`.
- Higher-order terms go up to `h²`, and no P1 energy term is faster than that.
- For `X_h = X + a h + b h^q` with `1 < q ≤ 2` and `a`, `b` of one sign, `R ∈ [2, 4]`, and the
  level-2 error lies between `d2/(R−1)` and `d2`.

| class | rule |
|---|---|
| **CONVERGED** | `2 ≤ R ≤ 4` and the conservative remaining error `\|d2\|/\|X2 − d2\|` ≤ 0.05 |
| **CONVERGING** | `2 ≤ R ≤ 4`. The limit is reported with its **model-based** bracket `[X2 − d2, X2 − d2/(R−1)]`, which is **not rigorous** |
| **NON-CONVERGENT** | `\|d2\| ≥ \|d1\|`. There is no evidence of convergence at these levels. This is not a claim of mathematical divergence, which density excludes |
| **UNRESOLVED** | `1 < R < 2` (slower than theory); `R > 4` (pre-asymptotic); a difference within its certified error of zero; oscillation (δ only); or a certified range touching a class edge (fail-safe) |
| **UNQUALIFIED** | any integrity failure |

The same rule is applied to `C`, `C′` (and hence `S` and `H`) and `δ`. For `δ` the class is
descriptive, since the rate theory is not derived for it. `max δ_h` and "S and H within 1 % on
every level" are also reported.

**What is rigorous regardless of the class:** `C ≤ C_2`, and so `S ≥ S_2`, for the meshed
model's continuum (Dirichlet principle). Each is widened by its certificate.

**`C_2` intervals, stated before `C_2` exists** (`d1` = 32.137 fF):

| `C_2` | class |
|---|---|
| ≤ 50.066 fF | NON-CONVERGENT |
| 50.066–66.134 fF | UNRESOLVED (slower than order 1) |
| **66.134–74.168 fF** | **CONVERGING** |
| 74.168–82.202 fF | UNRESOLVED (faster than order 2) |
| > 82.202 fF | UNQUALIFIED (nesting forbids it) |

**CONVERGED is unreachable for `C`.** Inside the CONVERGING window the conservative remaining
error is at least 12 %. This is stated in advance so that its absence is not read as news.

**Expected classes, recorded before the run.** These come from synthetic analogues, not QMHP
data, and the rules were not tuned to them:

- On three QMHP-like cells, `C` gave `R` = 2.76, 2.93 and 2.60: CONVERGING.
- On the dry-run cell, `δ` **grew** under refinement (3.3e-4 → 1.0e-3 → 1.7e-3): NON-CONVERGENT
  at these levels. A port face resolved by few elements barely constrains the potential at
  level 0, and constrains it more as nodes are added.

**The level-0 consistency check — a cross-code check, not an acceptance criterion.** At level 0
the mesh is byte-identical to the L2 rung, which is Palace's eigensolver.

- **The prediction.** The identity, with `p ≥ 0` and no missed low mode, forces
  `δ_0 ∈ [S_0 Σ_band p/f² − 1, … + S_0(1 − N_B)/f_max²]`, widened by **η = 1e-8**. η is derived
  from CSV print precision, Palace's backward errors and the certificates. At freeze the
  window is `[6.5852e-4, 6.7622e-4]`.
- **CONSISTENT.** `H_h` may be read as Palace's complete harmonic moment.
- **INCONSISTENT-LOW / INCONSISTENT-HIGH.** The identity is not confirmed on the QMHP mesh, and
  `H_h` is reported only as the static `S′_h`. The classes of `C`, `C′` and `δ` are unaffected.
- **The window is fixed now and may not be widened.**

## 5. Preflight on the QMHP mesh — geometry and assembly only, no solve

`preflight.json` (65 s, 3.7 GB):

| level | tets | nodes | unknowns C / C′ | nnz(A) | Galerkin to previous level | error-bound round-off floor |
|---|---|---|---|---|---|---|
| 0 | 64,434 | 13,991 | 4,558 / 4,543 | 49,716 | — | 5e-20 |
| 1 | 515,472 | 93,935 | 60,608 / 60,552 | 766,864 | 6.6e-15 | 4e-17 |
| 2 | 4,123,776 | 709,421 | 584,914 / 584,701 | 8,073,624 | 2.3e-14 | 1.1e-15 |

- **Preconditions.** Every one holds on every level: the mesh is conforming, all boundary faces
  are tagged and constrained, and the port face is a 0.01 × 0.005 rectangle with
  `area/(l·w) − 1` ≤ 1.1e-15. At levels 0, 1 and 2, the C′ problem constrains 15, 56 and 213
  port nodes off the conductors.
- **Frozen mesh digests.** The level digests are frozen in the pre-declaration, and the driver
  refuses before spending the attempt if a refined mesh differs.
- **Round-off floor.** The certificate's floor (about 5e-16 relative) is far below the 1e-9
  tolerance.

## 6. Resource estimate and the proposed command

The estimate is measured, not modelled. `dry_run.json` runs the exact execution path under the
declared limits, on a stand-in that is **larger** than the QMHP ladder and has **worse**
elements:

- level 2: 5.0 M tets and 792 k unknowns, against 4.1 M and 585 k;
- aspect p99: 25, against 14.

| | stand-in, measured | QMHP, expected | declared cap |
|---|---|---|---|
| wall | 241 s | about 3–5 min | 60 min |
| CPU | 379 s | about 5–8 min | 60 min |
| peak resident | 4.4 GB | 4–5 GB | — |
| peak address space | 7.4 GB | < 8 GB | 12 GB |
| level-2 PCG | 120 iterations; 0.32–0.36 s each; 21–27 s set-up | not known until the run | maxiter 1000 |

- **Worst case within the settings.** With `maxiter` = 1000 everywhere, the run takes about
  16 min wall and 26 min CPU. It would be recorded as an integrity failure, not retried.
- **Attempts.** 1. No retry.
- **Enforcement.** In-process `RLIMIT_CPU`, `RLIMIT_AS` and `SIGALRM`, plus an outer hard kill.
- **What the run writes.** `level0/1/2.json` (raw, each as its level completes), then
  `summary.json` or `failure.json`, then `manifest.sha256` by
  `orchestrator.manifest.write_verified`, on every path.

**Proposed command, from the repository root, locally, with no workflow and no network.** It
runs only once `STUDY-APPROVAL.json` exists and binds the digests in
`STUDY-APPROVAL.draft.json`:

    timeout --signal=KILL 3660 .venv/bin/python experiments/static-refinement-study/study_driver.py

## 7. What this study cannot establish; files

It cannot establish:

- `E_C,F1F1` or `g`;
- that Route A is valid or invalid;
- the device's capacitance (this is the meshed model);
- a rigorous continuum value or lower bound for `C` (the bracket is model-based);
- `B/H`, which needs eigen data;
- Palace's box-refined operators;
- any `H_h` *measured* by Palace.

| file | role |
|---|---|
| `predeclaration.json` | the frozen question, method, integrity, classification, consistency check, budget |
| `nested_solver.py` | the two problems, the direct and two-grid solvers, the certificate (with its proof) |
| `study_driver.py` | preflight, dry run, and the gated one-attempt execution with `write_verified` |
| `synthetic_cells.py`, `verify_solver.py` | the synthetic cells and the solver verification V1–V5 |
| `solver_verification.json`, `preflight.json`, `dry_run.json` | the committed evidence of the preparation |
| `STUDY-APPROVAL.draft.json` | the approval a human would grant, **not** an approval |
| `tests/test_static_refinement_study.py` | rules, integrity, gate, budget, evidence, pins |
