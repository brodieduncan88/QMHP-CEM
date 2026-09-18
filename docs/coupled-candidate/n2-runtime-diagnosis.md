# N2 runtime diagnosis — refinement cost 11× before it cost any DOF

**Scope.** Offline only. Nothing was executed for this note: it reads the three
committed Palace logs (L2 baseline, N1, N2), the committed N2 `config.json`, and
the pinned Palace `a61c8cbe` / MFEM `c444b17c` sources. No configuration was
changed, no run was launched, and nothing here is approved for execution.

**Question.** Why did N2's 103,411 DOF exceed the 2,700 s cap when N1's 84,485
DOF finished in 923.5 s and the unrefined L2 baseline's 79,944 DOF finished in
81.2 s? And is there a solver configuration Palace already supports that would
solve the *same* discrete problem faster?

---

## 1. The cost is not in the DOF

| | L2 baseline | N1 | N2 |
|---|---|---|---|
| finest ND(p=1) DOF | 79,944 | 84,485 | 103,411 |
| DOF vs. baseline | 1.000× | 1.057× | 1.294× |
| multigrid levels built | 1 | 2 | 3 |
| wall clock (ladder-measured) | 81.2 s | 923.5 s | 2,700.1 s (killed at the cap) |
| wall vs. baseline | 1.0× | 11.4× | >33× |

A 5.7 % increase in unknowns bought an 11.4× increase in wall clock. Whatever
happened between the baseline and N1 is not a size effect.

## 2. Where the time went

The rows below are Palace's own elapsed-time report (78.524 s and 921.710 s
totals; the ladder's wall clock in §1 additionally covers container start and
teardown). They are exclusive accumulators — indented sub-timers are
*not* included in their parent, and all rows sum to the reported total (verified:
baseline rows sum to 78.297 of 78.524; N1 rows sum to 921.487 of 921.710).

| row (s) | L2 baseline | N1 | change |
|---|---|---|---|
| Preconditioner | 3.253 | 635.561 | **+632.31** |
| Div.-Free Projection | 2.401 | 146.634 | **+144.23** |
| Linear Solve (Krylov only) | 2.448 | 46.930 | +44.48 |
| Coarse Solve | — | 19.731 | +19.73 |
| Setup | 0.029 | 4.269 | +4.24 |
| *subtotal, linear-solver stack* | *8.131* | *853.125* | ***+844.99*** |
| everything else combined | 70.393 | 68.585 | **−1.81** |
| **Total** | **78.524** | **921.710** | **+843.19** |

`844.99 − 1.81 = 843.19`, which is the whole difference. Mesh loading, operator
assembly, error estimation, post-processing and disk I/O did not get slower.
Every second of the regression is inside the preconditioner and the two solvers
that use it.

## 3. The preconditioner stopped working

The eigensolver prints its GMRES convergence, so preconditioner quality is
directly measurable:

| | L2 baseline | N1 | N2 (killed mid-run) |
|---|---|---|---|
| GMRES solves logged | 29 | 38 | 37 |
| total GMRES iterations | 29 | 584 | 742 |
| mean iterations per solve | **1.00** | **15.37** | **20.05** |
| mean reduction factor per iteration | ~5e-09 | ~0.26 | ~0.35 |
| Preconditioner s / GMRES iteration | 0.112 | 1.088 | — |

In the baseline every linear solve converged in a **single** GMRES iteration with
a residual reduction of ~5e-9 — the preconditioner was, to solver tolerance, an
exact solve. After refinement it reduces the residual by a factor of ~0.26 per
iteration and needs 15 of them, and each one costs 9.7× more. The product
`15.37 × 9.70 × (38/29 solves) = 195×` is exactly the observed growth of the
Preconditioner row (`635.561 / 3.253 = 195.4×`).

So the regression decomposes into two independent factors, neither of which is
DOF count: the preconditioner became **15× weaker** and each application became
**~10× more expensive**. The 9.7× is if anything conservative:
`Timer::KSP_PRECONDITIONER` is started only inside the Krylov solver's `ApplyB`
(`iterative.cpp:244-246`), so it measures applications — but the baseline's
3.253 s is spread over just 29 of them, and it must also absorb the direct
solver's one-time numeric factorisation: the baseline `Setup` row is 0.029 s,
far too small to hold a factorisation of a 79,944-DOF operator, and the rows
account for the total to within 0.23 s, so there is nowhere else for it to be.

Note also what the N1 rows say about *where* the V-cycle spends its time:
635.561 s in the smoother and inter-level transfers against 19.731 s in the
coarse solve, which is a separate exclusive row. 97 % of the preconditioner's
time is spent smoothing a fine level whose coarse level is already 95 % its
size.

## 4. Why, from the pinned source

For an eigenmode problem Palace resolves `Solver.Linear.Type: "Default"` to a
**sparse direct solver**, not an iterative one (`iodata.cpp:338-349`: the
`else` branch prefers SuperLU when available; `docker/palace.Dockerfile:132`
builds with `PALACE_WITH_SUPERLU=ON`). That is why one iteration sufficed.

`ksp.cpp:202-231` then decides how the chosen preconditioner is *used*:

```cpp
if (fespaces.GetNumLevels() > 1)
{
  // This will construct the multigrid hierarchy using pc as the coarse solver
  // (ownership of pc is transferred to the GeometricMultigridSolver). ...
  return gmg;
}
else
{
  return pc;
}
```

With one level the direct solve is applied to the fine operator. With more than
one it is **demoted to the coarse-level solver at the bottom of a V-cycle**, and
the fine level is left to the smoother. The same pattern appears independently in
`divfree.cpp:88-100`, where BoomerAMG is demoted the same way — which is why the
Div.-Free Projection row grew 61× on a completely different preconditioner. The
mechanism is the hierarchy, not the solver.

The hierarchy exists only because refinement created it. `geodata.cpp:204-206`
reserves capacity for extra mesh levels, and `geodata.cpp:346-350` pushes a copy
of the mesh before each refinement stage, so `Levels: 1` yields two meshes and
`Levels: 2` yields three. The logs confirm it:

```
N2:  Level 0 (p = 1):  79944 unknowns
     Level 1 (p = 1):  84485 unknowns      <- exactly N1's solved DOF
     Level 2 (p = 1): 103411 unknowns
```

## 5. Why this hierarchy cannot work

A geometric multigrid V-cycle is efficient when each level is much smaller than
the one above it — in 3-D, about 8× per level. Here the box marks **221 of
64,434 tetrahedra (0.34 %)**, so the level-to-level ratios are **1.057×** and
**1.224×**.

The coarse solve is therefore nearly as large as the fine problem, and
correspondingly useless as a correction: it is cheap per call (19.731 s over the
whole N1 run, ~0.03 s per application) but leaves almost all of the fine-level
error to the smoother. For an eigenmode problem that smoother is distributive
relaxation — a Chebyshev sweep on the fine ND space plus a second one on the
auxiliary H1 space, with discrete-gradient transfers between them (`gmg.cpp:40-46`,
reached because `mg_smooth_aux` resolves to 1 for this problem type,
`iodata.cpp:400-412`; the auxiliary levels are visible in the log alongside the
primary ones). That is where the remaining ~1.0 s per application goes, and it
still only buys a ~0.26 reduction factor.

N2 made this strictly worse — a third level at 1.224× the second — which is why
its iteration count rose from 15.37 to 20.05 and it never finished. For the
record, N2 was killed after 37 logged solves having reached EPS restart 2 with
4 of 6 eigenvalues converged; N1 needed 3 restarts. How much further it had to go
is unknown.

## 6. A supported configuration that solves the same problem

**`Solver.Linear.MGMaxLevels: 1`.** The schema documents this exactly
(`configfile.hpp:776`: "Maximum number of levels for geometric multigrid (set to
1 to disable multigrid)"). Traced through the pinned source, setting it changes
the preconditioner and nothing else:

| step | with the default (100) | with `MGMaxLevels: 1` |
|---|---|---|
| `geodata.cpp:204` | `mesh.reserve(1 + uniform + region)` | skipped, so `capacity() == 1` |
| `geodata.cpp:346` | `capacity() > 1` → copy each stage | false → no copy |
| `geodata.cpp:350` | `GeneralRefinement(refs, -1)` on the copy | **identical call**, in place |
| `geodata.cpp:353-355` | not reached | `RebalanceMesh(mesh[0], …)` |
| `geodata.cpp:362` | `reorient_tet` false → no-op | `reorient_tet` false → no-op |
| `multigrid.hpp:88` | 3 meshes → hierarchy of 3 levels | 1 mesh → **1 level** |
| `ksp.cpp:202` | wrap `pc` in a V-cycle | **return `pc` directly** |

The refinement flags, the `GeneralRefinement` call and hence the final fine mesh
are the same; only the intermediate copies are not retained. The two things that
could have perturbed the mesh on this path do not fire:

* `RebalanceMesh` returns `1.0` immediately at `Mpi::Size(comm) == 1`
  (`geodata.cpp:1445-1448`), and its only preceding work is gated on
  `save_adapt_mesh`, which defaults to `false` (`configfile.hpp:169`) and is not
  set in the committed config.
* `ReorientTetMesh` is gated on `reorient_tet`, which defaults to `false`
  (`configfile.hpp:206`) and is not set in the committed config.

`MGMaxLevels` also feeds `ConstructFECollections`, but at `Order: 1` that loop
breaks after one collection regardless (`multigrid.hpp:57-60`, `p == pmin`), and
the estimator hierarchy is already single-level because `estimator_mg` defaults
to `false` (`configfile.hpp:883`). Both are confirmed by the logs, where the
Estimation rows are flat across all three runs (31.3 s → 34.6 s).

**Unchanged by this setting:** the mesh, the element order, the ND/H1/RT spaces,
the assembled operators, `Tol: 1e-08`, `MaxIts: 400`, `KSPType: "GMRES"`, the
eigenvalue target, count and tolerance, the materials, ports and boundary
conditions. It is the same discrete eigenproblem; only the preconditioner applied
to it differs.

**`Solver.Linear.MGUseMesh: false`** is the narrower equivalent — it has exactly
one use site in the entire codebase (`geodata.cpp:204`) and produces the same
one-level hierarchy at `Order: 1`. Either is defensible; `MGMaxLevels: 1` is the
one the schema documents for this purpose.

**What would *not* fix it:** writing `Type: "SuperLU"` explicitly. The demotion in
`ksp.cpp:202` is keyed on `GetNumLevels()`, not on the preconditioner type, so
naming the solver changes nothing. Raising `MGSmoothIts` or `MGCycleIts` would
buy iterations at proportionate cost per application and leaves the cause — a
coarse level 82 % the size of the fine one — untouched.

## 7. A second, orthogonal lever

The run used `mpi_processes: 1` (`summary.json: environment.mpi_processes`), on a
runner the Dockerfile documents as 4 vCPU. Raising it is pure parallelism: the
continuous problem, the discretisation and the global FE space are unchanged.

It is worth separating honestly from §6, though. Changing the rank count changes
the METIS partition and therefore the order of floating-point reduction, so
results would agree to solver tolerance but would **not** be bit-identical, and
`RebalanceMesh` stops being a no-op. `MGMaxLevels: 1` preserves the computed
numbers exactly; `--np 4` preserves them only up to parallel reassociation.

## 8. What this note does not establish

It does not establish that N2 would finish inside the cap. The direct
factorisation would act on 103,411 DOF instead of 79,944 — 1.29× the unknowns,
with superlinear fill — and no factorisation at that size has been measured. The
supporting evidence is only that the identical single-level code path solved
79,944 DOF with a total linear-solver stack of 8.1 s out of a 78.5 s Palace
total, which leaves a large margin. The risks are factorisation time and memory,
and neither is bounded here — in particular the recorded `runner_cli_peak_rss_kb`
(238–242 MB, flat across all three runs) measures the container-runtime CLI in
the harness process tree, not the solver inside the container, so no memory
headroom can be read off it.

For scale, the parts of the baseline run that a preconditioner change does not
touch — error estimation (0.494 + 6.820 + 31.272 = 38.6 s) and disk I/O
(25.8 s) — already account for 64.3 s of its 78.5 s, and both grow with problem
size. A single-level N2 would be dominated by those, not by the solver.

**Outcome.** `MGMaxLevels: 1` was subsequently approved and run as N2R. It completed in 159.0 s
against N2's 2,700.1 s timeout, at the same 103,411 DOF on a mesh identical to four independent
counts: preconditioner time 635.561 s → 7.905 s, GMRES 15.37 → 2.00 iterations per solve, zero
`CoarseSolve` calls. The §8 caveats above were the right ones to state — no factorisation cost was
predicted, and the run did turn out to be dominated by estimation and I/O (77.4 % of its total).
See [`n2r-outcome.md`](n2r-outcome.md).

It also does not change the N2 result. N2 refused on time, and that refusal
stands as recorded in `n2-outcome.md`. This note explains the cause and names a
configuration that could be proposed later; it does not propose one now, and no
budget, tolerance or threshold is touched anywhere in it.
