# Verifying the first-moment solver tolerance 1e-14

Why `Solver.FirstMoment.Tol` moved from `1e-12` to `1e-14`, what was measured before it
moved, and what is deliberately **not** claimed.

The acceptance limit did **not** move. It is still `1e-12`
(`reference_model.evaluate(..., residual_tol=1e-12)`).

## 1. What went wrong on run 35721700281

The approved one-attempt run executed correctly on the real N2R cell — 103 411 true dofs,
5.88 s, inside every cap — and was then refused by exactly one check:

    independent relative residual <= 1e-12     measured 1.3313273400616318e-12
    LinearSolve.Converged = True               Iterations = 186

The cause is a design defect in the pairing of two numbers, not in the physics, the mesh,
the image or the patch:

* `Solver.FirstMoment.Tol` is the **PCG stopping tolerance**. The patch sets
  `pcg->SetRelTol(opts.tol)` and stops on the iteration's own residual measure.
* `LinearSolve.RelativeResidual` is an **independently recomputed** `‖Mx − f‖₂ / ‖f‖₂`,
  formed after the solve returns (`M->Mult(x, r); r.Add(-1.0, f);`).

Those are different norms. Both were set to `1e-12`, so the solver was being asked to beat
its own stopping rule. It missed by a factor of 1.33.

The fix is to tighten the **solve**, leaving the **criterion** alone. Loosening the
criterion after seeing the result is forbidden by CLAUDE.md §1 and was not done.

## 2. The risk that had to be excluded

Tightening a tolerance is not automatically safe. In floating point the attainable true
relative residual has a **floor** of a few multiples of ε = 2.22e-16. (A tempting closed
form, `C · ε · ‖M‖‖x‖/‖f‖`, was tested over 25 controlled cases and **refuted**: against a
139× variation in that predictor the floor moved 1.55×, regression slope +0.012, R² =
0.022, and `C` spread 118×. The componentwise bound `C · ε · ‖|M||x|‖₂/‖f‖₂` with C ≈ 0.89
does hold, as the standard `|fl(Mx) − Mx| ≤ γₙ|M||x|` result predicts. Nothing below
extrapolates through the refuted form — the floor is measured directly at every size.) If
`1e-14` lay *below* that floor, PCG would never meet it, would run to `MaxIts = 2000`, and
would record `Converged = false` — failing a *different* check and wasting a second
approved attempt.

This was a live possibility, not a formality. Palace's 186 iterations imply
κ(D⁻¹ᐟ²MD⁻¹ᐟ²) ≈ 180, which places the floor anywhere in 2e-16 … 4e-14. `1e-14` sits
inside that band. The observed run only proves the floor is ≤ 1.33e-12: it stopped on
tolerance, **not** on stagnation, so it revealed nothing about where the floor actually is.

## 3. What was measured

An independent sparse Whitney (lowest-order Nédélec) assembly of the ε-weighted mass
matrix was built directly from the committed N2R mesh, mirroring the conventions of
`synthetic_fixture.independent_first_moment` (materials 1→1.0 and 3→11.45, PEC attributes
2 and 4, port attribute 10 in +Y, `DIAG_ONE` padding). It shares no code with Palace.

**Assembly validated against Palace.** It produces **79 944 edges**, which is exactly the
`Level 0 (p = 1): 79944 unknowns` line in the committed N2R solver log. On the synthetic
fixture it reaches 1e-12 in **33** iterations where compiled Palace reported **32**.

### N2R base mesh (56 050 free dofs)

| quantity | measured |
|---|---|
| κ(D⁻¹ᐟ²MD⁻¹ᐟ²) | 148.73 (two eigensolver routes agree to 13 digits) |
| ‖M‖₂ / ‖x‖ / ‖f‖ | 0.9121 / 69.47 / 1.0431 |
| alignment factor ‖M‖‖x‖/‖f‖ | 60.74 |
| **floor of the recomputed residual** | **7.19e-16** = 3.24 ε, first attained at iteration 159 |
| post-floor behaviour | stagnates flat: max/min = 1.00007 over iterations 159–3000 |
| true residual first below 1e-14 | iteration 126 |

Run for 3000 iterations with **no stopping test at all**, recomputing `‖Mx − f‖/‖f‖`
explicitly every iteration. Two independent assemblies were built (one by me, one by a
separate agent) and agree on the edge count, κ, the iteration-126 crossing and the
norm-mismatch ratio.

### Refinement, measured directly on the N2R mesh — and a correction

An earlier draft of this record claimed that κ and the floor are *mesh-size independent*
for this element family, generalising from a 4× sweep on the **synthetic** geometry where
κ appeared to plateau at ≈ 7.8. **That claim is wrong and is withdrawn.** Applying uniform
red (1→8) refinement to the actual N2R mesh and measuring directly:

| level | n_tets | n_free | κ | floor | iters@1e-14 | residual delivered at Tol 1e-14 |
|---|---|---|---|---|---|---|
| 0 (base) | 64 434 | 56 050 | 148.73 | 9.18e-16 | 125 | 1.43e-14 |
| 1 | 515 472 | 524 306 | 294.40 | 1.13e-15 | 189 | 1.62e-14 |
| 2 | 4 123 776 | 4 501 588 | ≥321.85 (Ritz bound) | 1.43e-15 | 241 | 1.49e-14 |

κ is **not** h-independent: it nearly doubles on the first refinement (+98 %), then
decelerates sharply (+15.6 % like-for-like on the second), which is what red refinement's
bounded set of similarity classes predicts — not h-independence. Element shape quality
does degrade, once: minimum radius ratio 0.0500 → 0.0126 → 0.0091.

**The conclusion survives, on stronger evidence than the withdrawn claim.** What matters is
the floor, and the floor is far flatter than κ: over an **80× increase in free dofs** it
moves by only **1.55×** (9.18e-16 → 1.43e-15), fitting `n^0.100` and `κ^0.499`. The real
operator, at 103 411 dofs, is **bracketed** by levels 0 and 1 — and at *every* level,
including one 43× larger than the real operator, `Tol = 1e-14` delivers a recomputed
residual of 1.4–1.6e-14, comfortably inside the unchanged 1e-12 limit.

For the floor to reach 1e-14 it would have to rise a further 7×, which on the measured
`n^0.100` slope needs ~1.2e15 dofs, or on the `κ^0.499` slope needs κ ≈ 1.6e4 — 50× the
largest value measured.

### Size-matched control: the L3 mesh (a different geometry at the relevant scale)

`results/COUPLED-LADDER-O1-L3-20260916T091212Z/L3/solver/coupled_chip_cell_L3.msh` has
**111 505 free dofs**, close to the refined operator's 103 411, and is the same geometry
family. Independently assembled and measured:

| | L2 base | L3 |
|---|---|---|
| n_free | 56 050 | 111 505 |
| κ(D⁻¹ᐟ²MD⁻¹ᐟ²) | 148.7 | **48.0** |
| alignment factor | 60.7 | 99.7 |
| floor | 7.19e-16 (3.24 ε) | 6.92e-16 (3.12 ε) |
| recomputed residual at RelTol 1e-14 | 1.33e-14 | 1.28e-14 |
| margin under the 1e-12 limit | 75× | 78× |

Between these two operators the dof count differs by 2×, κ by 3.1× and the alignment
factor by 1.6× — yet **the floor moves by 4 %**. Here the *finer* mesh has the *lower* κ,
which is a property of these two particular meshes and **not** evidence of h-independence:
refining one mesh does raise κ, as the table above shows. What both lines of evidence
agree on is the thing the verdict rests on — the floor is far less sensitive than κ, and
stays within a small multiple of machine epsilon across every operator measured.

### Why the solve converges rather than stagnating — verified from Palace's source

`CgSolver<OperType>::Mult` in `palace/linalg/iterative.cpp` at the pinned commit
`a61c8cbe0cacf496cde3c62e93085fae0d6299ac` stops on

    res = sqrt(|rᵀz|),  z = D⁻¹r,  r the RECURRENCE residual (r -= alpha*Ap)

compared against `max(rel_tol · sqrt(fᵀD⁻¹f), abs_tol)`. The preconditioner is confirmed
as `JacobiSmoother` with `omega = 1.0`, i.e. `B = D⁻¹` exactly.

The recurrence residual is never recomputed, so **it has no floor**. Measured on the base
mesh: it falls to 5.3e-163 by iteration 1853 and its 2-norm underflows to exactly 0.0 at
iteration 1848. Non-convergence at `MaxIts = 2000` is therefore not a realistic failure
mode for any tolerance above ~1e-160.

`abs_tol` does not pre-empt the relative test either: 2.22e-16 against an initial
preconditioned norm of 7.254 is a ratio of 3.1e-17, far below 1e-14.

This is also the exact explanation of the original refusal: **the stopping test is in the
D⁻¹ norm, the acceptance check is in the 2-norm.** The ratio between them was measured at
**1.33–1.68 across three different operators**, matching the 1.3313e-12 that a 1e-12
tolerance produced.

### Simulating Palace's own stopping rule

Applying that exact predicate to the independently assembled base mesh:

| RelTol | stops at | recomputed residual | passes the 1e-12 limit? |
|---|---|---|---|
| 1e-12 | iteration 106 | 1.66e-12 | **no** — reproduces the observed failure |
| 1e-14 | iteration 125 | **1.33e-14** | yes, ~75× inside |

The 1e-12 row independently reproduces the failure of run 35721700281 without using that
run's numbers as an input.

## 4. Margins

* floor 7.2e-16 … 1.43e-15 across an 80× dof range vs the 1e-12 limit → **700–1400×**
* recomputed residual at 1e-14: 1.33e-14 (base), 1.62e-14 (level 1), 1.49e-14 (level 2),
  1.28e-14 (L3) vs the 1e-12 limit → **~62–78×** at every size measured
* floor vs the 1e-14 stopping tolerance → **7–14×** of headroom
* iterations at 1e-14: 125 (base), 189 (level 1), 241 (level 2); the real operator's 186
  at 1e-12 extrapolates to ≈ 214–220, against `MaxIts = 2000` → **~9×**
* wall clock was 5.88 s against a 2700 s cap; ≈ +1.1 s is immaterial

**Stagnation is not a failure mode at all.** Palace tests the *recurrence* residual, which
is never recomputed and has no floor; it reaches 5.3e-163 by iteration 1853. And if a
solve did exhaust `MaxIts`, `ksp.cpp` only issues `Mpi::Warning` — print-only, no throw,
no abort — so the outcome would be a recorded `Converged = false` failing the
"linear solve converged" check, not a crash.

## 5. No other check is traded away

A tighter solve makes `r` smaller. `CertifiedErrorUpperBound_nd = Re(xᴴr)/L` shrinks, so
the certified lower bound `A_nd − Re(xᴴr)/L` **tightens toward** `A_nd`, which makes a
definitive `OMITTED_MOMENT_CERTIFIED_LOWER_BOUND` verdict *more* reachable, not less. The
functional check, the sampled null-space check, `SolutionEssentialNorm` and the
scale/unit identities do not depend on the residual magnitude. The residual appears in
exactly two checks: "linear solve converged" and the 1e-12 limit itself.

## 6. What this does NOT establish

* It does **not** predict what A, E_C or g will be. It is a numerical-attainability
  argument about the solve, nothing more.
* The floor and κ were measured on the **base** mesh (56 050 free dofs) and on refinement
  sweeps of the synthetic geometry. The 103 411-dof **2-level-refined** operator was
  **not** assembled locally; its behaviour is extrapolated from the measured
  mesh-independence of κ and the floor. That extrapolation is the one inferential step.
* The refined mesh's **tetrahedral shape quality was not measured**. κ(D⁻¹M) depends on
  shape regularity, and MFEM's bisection refinement can degrade aspect ratios relative to
  the Gmsh base mesh. This is the one uncontrolled variable. Its effect would show up as a
  higher iteration count, against ~9× of `MaxIts` headroom; for it to break the *floor*
  argument the floor would have to be ~14× worse than both independent measurements.
* The measurement PCG is serial NumPy. The approved run uses `np_processes = 1`, so the
  summation order is close but not identical; the orders of magnitude reproduce, the
  round-off-level digits of the floor need not.
* Nothing here re-runs or re-interprets run 35721700281. That record stands as
  UNQUALIFIED and is preserved.

## 7. Reproducing it

The measurement scripts are analysis, not evidence records, and were run from a scratch
directory against the committed mesh and fixtures, writing nothing into the repository.
Each step is reproducible from the committed inputs alone:

1. assemble the ε-weighted Whitney mass matrix from
   `results/COUPLED-LADDER-O1-L2-N2R-20260918T061455Z/L2/solver/coupled_chip_cell_L2.msh`;
2. check the edge count against `Level 0 (p = 1): 79944 unknowns` in the committed log;
3. run Jacobi-PCG from x₀ = 0 with **no** stopping test, recomputing `‖Mx − f‖/‖f‖`
   explicitly at every iteration;
4. read off the minimum (the floor) and the residual at the iteration where each candidate
   stopping measure first crosses the tolerance.
