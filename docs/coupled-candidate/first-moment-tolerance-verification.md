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
relative residual has a **floor** of roughly `C · ε · ‖M‖‖x‖/‖f‖`, with ε = 2.22e-16. If
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
| κ(D⁻¹ᐟ²MD⁻¹ᐟ²) | 148.7 |
| alignment factor ‖M‖‖x‖/‖f‖ | 1.19e+02 |
| **floor of the recomputed residual** | **1.020e-15** (iteration 148) |
| iterations at RelTol 1e-14 | 126 (recurrence) / 133 (preconditioned) |
| recomputed residual at RelTol 1e-14 | **9.36e-15** / 1.54e-15 |

No stagnation or breakdown out to 1851 iterations at any tolerance tested.

### Mesh-size dependence (same geometry, four resolutions)

| h (mm) | n_free | κ | floor | iters@1e-14 |
|---|---|---|---|---|
| 0.50 | 276 | 4.65 | 3.14e-16 | 33 |
| 0.40 | 510 | 5.81 | 3.84e-16 | 37 |
| 0.30 | 1033 | 7.81 | 4.64e-16 | 41 |
| 0.25 | 1063 | 7.83 | 3.99e-16 | 41 |

κ and the floor **plateau** under refinement, as theory predicts for Whitney mass
matrices: both are governed by element shape quality and material contrast, not by h. The
config's 2-level box refinement takes N2R from 79 944 to 103 411 dofs — **+29 %**, local to
a small box — so it cannot move them materially.

### Why the solve converges rather than stagnating

The measured floor, **1.02e-15**, lies an order of magnitude **below** 1e-14. Separately,
the iteration's own residual measure keeps falling well past the true floor (the classic
CG residual gap: on the fixture the recurrence residual reaches 1.8e-20 while the true
residual has flattened at 5.18e-16). Both facts point the same way: the stopping test at
1e-14 is met with room to spare.

## 4. Margins

* floor 1.02e-15 vs the 1e-12 acceptance limit → **980×**
* recomputed residual at 1e-14, 9.36e-15, vs 1e-12 → **107×**
* ~126–133 iterations measured on the base mesh; scaling by Palace's own refined-to-base
  ratio gives ≈ 220 against `MaxIts = 2000` → **~9×**
* wall clock was 5.88 s against a 2700 s cap; a ~20 % iteration increase is immaterial

For 1e-14 to fail the acceptance limit, the refined operator would have to be ~100× worse
than measured; for it to stagnate, the floor would have to rise ~1000×.

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
* Palace's exact `CgSolver` stopping predicate was **not** read from upstream source: the
  session's GitHub access is scoped to this repository and the image artefact is behind an
  egress policy that returns 403. Both candidate predicates (recurrence and preconditioned
  residual) were therefore measured, and **both** clear the limit — so the verdict does not
  depend on which one Palace uses.
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
