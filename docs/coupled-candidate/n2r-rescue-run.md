# N2R — N2's problem, solved with the baseline's preconditioner

**What this is.** One rescue re-solve of the N2 discrete problem. The same baseline mesh file, the
same two-level `Model.Refinement.Boxes` prescription, the same element order, the same tolerances
and the same eigenvalue target as the run that timed out — plus one `Solver.Linear` key,
`MGMaxLevels: 1`.

**What this is not.** Not a third refinement level, not the prepared gmsh R2 experiment, not a
rerun of N1, and not a change to the numerical method. It asks the same question N2 was asked and
inherits every one of N2's confounds unchanged.

## 1. Why

N2 did not fail on size: its 103,411 DOF cleared the 250,000 gate 2.3 s in. It failed on time, and
`n2-runtime-diagnosis.md` locates the time. Palace's own exclusive timers put **+844.99 s** of the
L2 → N1 regression inside the preconditioner, Krylov and divergence-free rows and **−1.81 s**
everywhere else, against a measured total of **+843.19 s** — for 5.7 % more unknowns. Box
refinement builds mesh levels, and `ksp.cpp:202` then demotes the preconditioner, a sparse direct
solve for this problem type, to the coarse solver of a V-cycle whose levels barely coarsen.
Measured GMRES iterations per solve: **1.00** in the unrefined baseline, **15.37** in N1,
**20.05** in N2.

`MGMaxLevels: 1` is the documented way to switch that off — `configfile.hpp:776`, "set to 1 to
disable multigrid".

## 2. That the discrete problem is unchanged, by diff rather than by argument

A prepare-only run of the full driver against this approval wrote a `config.json`. Diffing it
against the config N2 actually solved — `diff
results/COUPLED-LADDER-O1-L2-N2-20260917T103405Z/L2/solver/config.json <prepared>/config.json`:

```
104c104,105
<       "MaxIts": 400
---
>       "MaxIts": 400,
>       "MGMaxLevels": 1
```

One added key, at the end of `Solver.Linear` because `apply_solver_linear_overrides` ends with
`linear.update(overrides)`; the changed line above it is the comma JSON now needs there. The
same hunk reproduces against the pinned candidate, `experiments/N2R-rescue-preconditioner/
config.candidate.json`. The mesh file is the baseline's, hash-gated to
`d8dc1a92…c14428` before launch. `Type`, `KSPType`, `Tol` (1e-08), `MaxIts` (400) and the whole
`Solver.Eigenmode` block (`N` 6, `Tol` 1e-06, `Target` 0.5, `Save` 6) are untouched.

The source chain behind that, from pinned Palace `a61c8cbe`:

| step | default (100) | `MGMaxLevels: 1` |
|---|---|---|
| `geodata.cpp:204` | reserve for intermediate meshes | skipped → `capacity() == 1` |
| `geodata.cpp:346` | copy the mesh each stage | no copy |
| `geodata.cpp:350` | `GeneralRefinement(refs, -1)` | **the same call**, in place |
| `multigrid.hpp:88` | 3 meshes → 3 levels | 1 mesh → 1 level |
| `ksp.cpp:202` | wrap the preconditioner in a V-cycle | apply it directly |

Two paths that only this branch reaches were checked rather than assumed. `RebalanceMesh` fires at
`geodata.cpp:353-355` and is inert here: it returns `1.0` at `Mpi::Size(comm) == 1`
(`geodata.cpp:1445-1448`) and its only preceding work is gated on `save_adapt_mesh`, default false
(`configfile.hpp:169`); the run uses one MPI process. `ReorientTetMesh` at `geodata.cpp:362` is
gated on `reorient_tet`, default false (`configfile.hpp:206`). Neither is set in the config.

## 3. What the approval may and may not change

The driver accepts only `MGMaxLevels` and `MGUseMesh` from an approval record
(`_SOLVER_LINEAR_OVERRIDE_KEYS`). `Tol`, `MaxIts`, `Type` and `KSPType` are refused before any
solve is launched, so an approval — which is data — cannot change what "converged" means and then
publish a `COMPLETED` record asserting it did not.

## 4. The DOF guard, and a falsifiable mesh identity

The guard is unchanged. It matches `ND (p = 1): N` in Palace's "Assembling system matrices" line,
which prints the **finest** space once per run, before the multigrid hierarchy block. Removing the
hierarchy removes lines the probe never matched — verified against N2's log, where the probe read
exactly one value, `103411`.

Unlike N2's preparation, this run's DOF is not unknown offline. N2 measured it. So this is a
prediction, not an estimate: **N2R must report 103,411 order-1 ND DOF**, and Palace must print
these four counts for its mesh —

| vertices | edges | faces | elements |
|---|---|---|---|
| 17,447 | 103,411 | 170,410 | 84,445 |

— which satisfy `V − E + F − T = 1`, so they describe one consistent complex rather than four loose
numbers, and whose edge count *is* the order-1 ND dimension. A different count means the mesh is
not N2's and the comparison is void. The converse does not follow: the characteristic is
**necessary, not sufficient** — it holds for the baseline (`13991−79944+130388−64434`) and for N1
(`14667−84485+138118−68299`) too. What *guarantees* the mesh is the hash gate on the mesh file plus
the identical box; these counts are the cross-check that both did what they say. One difference in shape is expected and is not a discrepancy:
with a single mesh, `geodata.cpp:394-400` prints one un-prefixed `Parallel Mesh Stats` block
carrying the refined counts, where N2 printed a `Coarse` and a `Refined` block.

## 5. What is not predicted

No runtime. The baseline solved 79,944 DOF on this same one-level code path in 81.2 s with an 8.1 s
linear-solver stack, but N2R factorises a 1.29× larger operator and sparse-direct cost and memory
grow superlinearly with fill. No factorisation at 103,411 DOF has been measured anywhere in this
project. The risks are a slower-than-expected factorisation (TIMEOUT at the unchanged cap) and
memory exhaustion (RUN_FAILED). **Either is the result.** The cap, the budget and the solver
configuration are not changed to rescue it, and there is no second attempt under this approval.

## 6. The comparison, and the one caveat it carries

Primary: **N1 → N2R**. Alongside: original L2 → N1. Same matching rule, same magnitude convention,
same frozen tolerances, reported and not gating. Excluded from the gmsh L1/L2/L3 convergence fit.

N1 was solved with the V-cycle and N2R with the direct preconditioner, so this step is **not
preconditioner-controlled**. A preconditioner changes the path to the solution, not the solution:
both runs converge their own discrete eigenproblem to the same `Solver.Eigenmode.Tol` of 1e-06 and
`Solver.Linear.Tol` of 1e-08.

What that leaves is stated rather than certified away. **Neither of Palace's error columns is a
frequency.** `ErrorType::ABSOLUTE` returns the raw residual norm `‖(K − λM)x‖`, and
`ErrorType::BACKWARD` divides it by `‖K‖ + |λ|‖M‖` (`slepc.cpp:473-484`, `:824-837`). Neither
bounds a frequency error without an eigenvalue condition number, which is not computed here. So no
measurement in this project certifies the N1 → N2R frequency difference as free of solver-path
effects, and none is claimed.

What *is* enforced is the project's unchanged **backward-error tolerance of 1e-6** — the rule the
driver actually applies. N1 met it at 8.76e-11; N2R must meet it or stop. And the frozen
`Δf ≤ 1e-4` is **relative and dimensionless**, not 1e-4 GHz.

The N1 → N2R frequency difference is therefore reported as an observed difference between two runs
that also differ in preconditioner — not as a measurement of refinement alone. For scale, the
L2 → N1 movements were `3.685e-02` and `4.170e-04` relative, two to three orders of magnitude above
the frozen tolerance. That step crossed a preconditioner change too (1 multigrid level → 2), and
the report now says so on both steps rather than only on this one.

## 7. Status

**Executed.** COMPLETED in 159.0 s, 5.9 % of the cap, at exactly the predicted 103,411 DOF, on a
mesh Palace printed with exactly the four predicted counts and a one-level hierarchy. The outcome,
the N1 → N2R comparison and what it does and does not establish are in
[`n2r-outcome.md`](n2r-outcome.md).

N2's TIMEOUT stands as recorded in `n2-outcome.md` — N2R does not replace it and does not
reinterpret it.
