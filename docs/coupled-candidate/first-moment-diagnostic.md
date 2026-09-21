# The direct first-moment diagnostic — PREPARED, NOT APPROVED, NOT EXECUTED

**Preparation only.** This note delivers the implementation diff, its tests,
the exact proposed computation and one execution proposal for the direct
evaluation of the first spectral moment `A` on N2R, as requested after the
first-moment assessment (`first-moment.md`). Nothing here has been run on
N2R: no FEM assembly, no functional, no matrix, no solve. The moment identity
`A = Σ_m λ_m p_m = qᴴM⁻¹q` is taken as accepted under its stated assumptions
and is not re-audited. Record: `experiments/first-moment-diagnostic/`; patch:
`docker/patches/first-moment-diagnostic.patch`
(sha256 `31b5bd29de05c81747841287e33f7b943a9669bea55ea01074e9e9326de872db`);
image: `docker/palace-first-moment.Dockerfile`, built by no workflow.

The C++ patch is **not compiled** in this environment (no Palace toolchain).
It was verified to apply cleanly to the pinned commit `a61c8cbe` with
`git apply --check`; the image builds it, and its two built-in checks run on
the real problem only under the separate approval proposed in §8.

## 1. The constrained mass operator

The eigensolver obtains `M` with `Operator::DIAG_ZERO`
(`eigensolver.cpp:38`). `ParOperator::Mult` (`rap.cpp:198-227`) zeros the input
on the essential true dofs before prolongation and, after restriction, sets the
output to `x` (DIAG_ONE) or `0` (DIAG_ZERO) on those dofs. So on the true dofs

```
M(DIAG_ONE)  = [[M_free, 0], [0, I]]        SPD
M(DIAG_ZERO) = [[M_free, 0], [0, 0]]        singular, rank deficient by |PEC dofs|
```

The diagnostic is defined on the free PEC-constrained true dofs:

```
M_free x = f_free ,        A_nd = Re(f_freeᴴ x) / L_nd .
```

It is *implemented* as the padded DIAG_ONE system with the right-hand side
zeroed on the essential dofs, `M(DIAG_ONE) x = [f_free; 0]`, whose solution is
`[M_free⁻¹ f_free; 0]` and whose `fᵀx` is `f_freeᵀ M_free⁻¹ f_free` exactly —
the same quadratic form with **no artificial boundary contribution**. The
reference model proves the equivalence on synthetic fixtures with shared dofs
and PEC dofs that carry functional weight:

| statement | worst case over 60 fixtures |
|---|---|
| padded DIAG_ONE with zeroed rhs = free-dof form | 4.2e-16 |
| padded DIAG_ONE with rhs **not** zeroed − free form = `Σ_PEC f_dbc²/L` (the artificial term) | 4.2e-16 |
| padded DIAG_ZERO singular in every trial | true |

The driver therefore (i) takes `GetMassMatrix<Operator>(DIAG_ONE)`, (ii) zeros
`f` on `GetNDDbcTDofLists().back()` *before* the solve, (iii) reports the norm of
the solution on the essential dofs (must be 0). No pseudoinverse, no mass
lumping: N2R's physical model and Nédélec space are `SpaceOperator`'s, built
from the same config `Model`/`Boundaries`/`Solver.Order`/`Linear.MGMaxLevels`.

## 2. Port functional access

`LumpedPortData::v` is private and assembled lazily by the private
`InitializeLinearForms`; no public accessor returns it. The patch adds the
smallest one:

```cpp
// lumpedportoperator.hpp — added after GetVoltage
void GetVoltageFunctional(mfem::ParFiniteElementSpace &nd_fespace, mfem::Vector &f) const;
// lumpedportoperator.cpp
InitializeLinearForms(nd_fespace);                       // the exact GetVoltage form
f.SetSize(nd_fespace.GetTrueVSize());
nd_fespace.GetProlongationMatrix()->MultTranspose(*v, f); // f = Pᵀ v
```

`GetVoltage` computes `(*v) * E.Real() + i (*v) * E.Imag()` on the **local**
vectors and sums over ranks (`lumpedportoperator.cpp:297-308`); the local field
is `P E_true`, so the sum is `(Pᵀv) · E_true`. That is the dual assembly
`mfem::ParLinearForm::ParallelAssemble` performs (`plinearform.cpp:95-99`:
`prolong->MultTranspose`), and the operator side uses the same `Pᵀ`
(`ParOperator::RestrictionMatrixMult`, `rap.cpp:356-366`, `use_R == false`).
The local `LinearForm` coefficients are **not** used as a true-dof right-hand
side. The driver then zeros `f` on the PEC dofs; the reference model shows the
free-restricted functional reproduces `GetVoltage` exactly when the field
satisfies the PEC constraint (4.6e-16) and differs otherwise (≥ 3.6 %), which is
why the runtime check uses a constrained field.

**Runtime check built into the driver (aborts on failure):** a random complex
true-dof field is zeroed on the PEC dofs, expanded to a complex `GridFunction`,
and `f·Re(E) + i f·Im(E)` is compared with `port->GetVoltage(E)` to `1e-10`
relative. Synthetic tests cover dual assembly for arbitrary complex fields, the
PEC restriction, and phase rotation (`V(e^{iθ}E) = e^{iθ}V(E)`, `|V|` fixed).
No N2R solve is performed.

## 3. Internal units and normalisation

Everything is computed in Palace's nondimensional units and converted once, at
output. From the pinned `IoData` (`iodata.cpp:453-465`, `:512`, `:562-620`):

| quantity | definition | N2R expected (Lc = 4.000e-03 m, the bbox extent Palace printed) |
|---|---|---|
| `t_c` | `1e9·Lc/c0` ns | 0.013342563808 ns (log prints 1.334e-02) |
| frequency scale | `1/(2π t_c)` GHz per nondimensional rad | 11.925 GHz |
| `L_nd` | `L_H/(μ0·Lc)` | 20.582047285189 |
| inductance scale | `μ0·Lc` H | 5.0265e-09 H |

```
A_nd   = Re(f_ndᴴ M_nd⁻¹ f_nd) / L_nd
A_GHz² = A_nd / (2π t_c)²                (λ_nd = ω_nd², f_GHz = ω_nd/(2π t_c))
```

The driver takes `L_nd = port->L` (already divided by `μ0 Lc`), `freq_scale =
DimensionalizeValue(FREQUENCY, 1.0)` and forms `A_GHz2 = A_nd·freq_scale²`;
henries appear only in the output field `L_H`. Internal matrices are never
combined with `L` in henries. The record also states `Lc_m`, `tc_ns` and both
scales as the solver actually used them, and the evaluator recomputes them from
`Lc_m` (`tc = 1e9 Lc/c0`, `1/(2π tc)`, `μ0 Lc`) before accepting the record.

**Reconciliation with Palace's reported EPR.** `GetInductorParticipation`
(`postoperator.cpp:644-660`) uses `I = V/(iω_m L)` and `p = ½ L|I|²/E_m` with
`E_m = E_elec + E_cap` and `E_elec = ½(E_rᵀME_r + E_iᵀME_i)`
(`domainpostoperator.cpp:142-154`); `E_cap = 0` here (`C = 0`). Hence

```
|p_m| = |V|² / (2 L ω_m² · ½ EᴴME) = |fᴴE_m|² / (L λ_m E_mᴴ M E_m) ,
```

the absolute-square form, invariant under `E → cE` for any complex `c`; with
`E_mᴴME_m = 1` (`RescaleEigenvectors`, `slepc.cpp:487-495`) it is
`(qᴴE_m)²/λ_m`. Verified to 3.4e-15 on the fixtures, phase invariance to
4.8e-12 (for `p`) and 3.8e-16 (for `A`); the unit round trip
`Σ p λ_nd/(2π t_c)² = Σ p f_GHz²` to 4.7e-16. The saved all-nine `A_saved`
converts to `A_saved_nd = 0.016526676` at the expected `t_c` (an expected value;
the comparison uses the record's own `t_c`).

## 4. Null space and comparison scope

**Why the functional annihilates `ker(K)` on the actual assembly.** The port
stiffness term is a boundary `VectorFEMassIntegrator` with coefficient `1/L_s`,
`L_s = L·(w/l)·n` (`AddStiffnessBdrCoefficients`, `lumpedportoperator.cpp:571-591`,
active ports only), assembled by libCEED on the quadrature rule
`IntRules.Get(geom, q_order)` with `q_order = DefaultIntegrationOrder::Get(T)`
(`fespace.cpp:136-142`). The voltage form uses `VectorFEBoundaryLFIntegrator`
with the **same** `DefaultIntegrationOrder::Get(T)` and `IntRules.Get`
(`integrator.cpp:48-71`); both orders are `2p + OrderW(T)` (+ extras)
(`integrator.cpp:14-19`), which for N2R is the printed `quadrature order = 2`
(`palace_log.txt:52`): the 3-point triangle rule with weights `1/6`, all
positive (`mfem/fem/intrules.cpp:1270-1273`). With `Q` the evaluation of the
tangential trace at the port quadrature points and `a > 0` the weights:

```
K_port = Pᵀ Qᵀ diag(a / L_s) Q P ,     f = Pᵀ Qᵀ (a · 1/(w n)) .
```

So `f ∈ range(Qᵀ) = range(K_port)`, and since `K = K_curl + K_port` with both
terms PSD, `ker(K) ⊆ ker(K_port) = range(K_port)^⊥ ∌ f`: **`qᴴE₀ = 0` for every
zero mode.** This needs only the same quadrature *points* and positive weights.
With the same *weights* too, Cauchy–Schwarz on the quadrature sum gives
`|V|² ≤ (l/w)·Σ a|E_t|²` and `K_port(E,E) = (l/(L w))·Σ a|E_t|²`, i.e.
**`K ≥ q qᴴ`** as quadratic forms on the constrained space (fields with
`E_dbc = 0`, where DIAG_ONE adds nothing). The reference model checks both: the
functional lies in `range(K_port)` and annihilates a kernel of dimension ≥ 3 in
every fixture (2.6e-14), `min eig(K_port − qqᵀ) ≥ −1.5e-16` with the same rule,
and a mismatched rule (same points, reweighted) breaks it to `−0.14` — the
negative control that shows the parity condition is doing the work. The driver
checks `uᵀKu ≥ (fᵀu)²/L` on the solution `x` and four random constrained fields
with one stiffness assembly and matvecs — **no eigenbasis is required**.

**Same space.** The direct moment is `f_freeᵀ M_free⁻¹ f_free`, a Parseval sum
over *any* `M_free`-orthonormal eigenbasis of the constrained pencil
`(K_free, M_free)`, the pencil the eigensolver solves. The saved eigenpairs are
`M`-normalised (`E_mᴴME_m = 1`) vectors of that pencil, and their `p_m` are
`(qᴴE_m)²/λ_m` by §3. The divergence-free projector removes gradients `∇ψ`
with `ψ = 0` on the auxiliary essential boundaries (PEC and, for the active
port, its `L_s` face); those directions have zero tangential trace on the port
face, so they lie in `ker(K_port) ∩ ker(K_curl) = ker(K)` and carry zero
`(qᴴE)²` by the argument above. The projector therefore changes which vectors
are *returned*, not the moment: `A_direct` equals the sum over all nonzero-`λ`
modes (verified on the fixtures: sum over all modes = sum over `λ > 0` = free
solve, 1.7e-15), and

```
A_direct − A_saved = the first moment carried by the nonzero-λ modes the eigensolver did not return,
```

*subject to* the checks in §5. Nothing real-data is computed in preparation:
no `A`, `E_C`, `N` or `g`.

## 5. Outputs and numerical checks

The driver writes `postpro/first-moment.json` (schema `reference_model.RECORD_KEYS`,
every key asserted against the patch by the tests):

- `Dofs`: total, essential and free true-dof counts; `Port`: index, `L_nd`, `L_H`;
- `Scales`: `Lc_m`, `tc_ns`, frequency and inductance scales, `A_GHz2_per_nd`;
- `Functional`: `‖f‖²` full, free and essential; the runtime `GetVoltage` check;
- `LinearSolve`: iterations, converged, solver residual, **independent**
  `‖Mx − f‖`, `‖f‖`, relative residual, `‖x‖`, `‖x_dbc‖`;
- `A`: `A_nd`, `A_GHz2`, the first-order residual correction `−xᵀr/L` and the
  bound `‖x‖‖r‖/L`, both also in GHz²;
- `NullSpaceCheck`: the minimum relative gap over the samples;
- `Resources`: wall time and max RSS.

Hashes (config, mesh, patch, Dockerfile, image ID, `PALACE_PATCH_SHA256` read
from the image, the three scripts) are attached by `evaluate_record.py`, which
recomputes the all-nine `A_saved` from the committed `eig.csv`/`port-EPR.csv`
(2.351511939 GHz², `N_partial` 0.999254583556, reproducing
`experiments/first-moment/`) and variant B alongside, and reports
`A_direct − A_saved` with:

- **the numerical qualification**: exact `A* = fᵀx*` with `Mx* = f` satisfies
  `A − A* = x*ᵀr`, so `|A − A*| ≤ ‖x*‖‖r‖/L`, with `‖x*‖` within
  `1 + κ(M_free)·(‖r‖/‖f‖)` of `‖x‖` — negligible at the required
  `‖r‖/‖f‖ ≤ 1e-12` unless `κ(M_free) > 1e6`; the saved moment's own
  eigensolver tolerance is *not* in the bound and is said so;
- **the wording rule**: the difference **is not called an omitted spectral
  moment until** the functional check, the null-space check, convergence, the
  residual threshold, the essential-dof checks, the unit round trips
  (`tc`, scales, `A_GHz2 = A_nd·scale²`, `L_H = L_nd·μ0Lc`), the dof-count
  identity with N2R (103411) and the caps all pass — otherwise it is an
  UNQUALIFIED difference;
- a raw difference within the bound is reported as "not resolved", never as a
  small tail; `E_C` stays UNAVAILABLE and `g` stays blocked whatever the number.

On the synthetic fixture the evaluator recovers a known omitted moment
(1.751108261251e-07 exact, 1.751108261252e-07 evaluated, bound 8.1e-19),
rejects records whose functional, null-space or convergence check fails, and
rejects a solve at 1e-6 relative residual (`fixture_evaluation.json`).

## 6. Preparation only

Built and tested with synthetic fixtures; no N2R FEM assembly or solve, no
export framework, no eigensolve, no driven sweep. The production Palace path is
unchanged by default: the patch adds a problem type and one accessor, removes
exactly two lines (the enum-list tails that gain a comma), and touches neither
the eigenmode driver nor `SpaceOperator`; `docker/palace.Dockerfile` is
byte-identical (sha256 `ae61175a…`), and the diagnostic image is that file plus
one `COPY` and one `git apply --check && git apply` step (`.dockerignore` now
admits exactly that patch). Any execution keeps the **250 000**-DOF rule and the
**2 700 s** cap as **hard caps, not runtime promises** (the space is N2R's,
103411 dofs; the wall cap is the launcher's timeout, and a run that hits it is
FAILED, not retried). Workflow triggers were checked: nothing under
`solvers/palace/`, `.github/`, `docker/palace.Dockerfile`,
`scripts/palace_golden_run.py` or `scripts/palace_verify_campaign.py` is
touched, no golden run is launched, and the **spent PO1 approval** is untouched
(sha256 `be5cbe1a…` pinned by the tests). No registered-definition change, no
historical-record rewrite, no Route A/B extraction, no N3, no budget increase,
no merge of PR #7.

## 7. The exact proposed computation

1. Build `SpaceOperator` from `config.candidate.json` = N2R's solved config with
   `Problem.Type: "FirstMoment"`, `Solver.Eigenmode` removed and
   `Solver.FirstMoment {Tol 1e-12, MaxIts 2000, CheckFunctional, CheckNullSpace,
   NullSpaceSamples 4, Seed 20260920}` added — nothing else
   (`config.delta.txt`, 7 lines removed, 9 added; mesh, boxes, PEC set, port,
   order, `MGMaxLevels` untouched).
2. `f = Pᵀ v` from `GetVoltageFunctional`; record `‖f‖²`; zero `f` on the PEC dofs.
3. Check 1: random complex constrained field, `f·Re E + i f·Im E` vs `GetVoltage(E)`.
4. `M = GetMassMatrix<Operator>(DIAG_ONE)`; PCG + Jacobi, `x₀ = 0`, RelTol 1e-12.
5. `r = Mx − f` independently; `A_nd = fᵀx/L_nd`; `A_GHz² = A_nd/(2π t_c)²`;
   correction `−xᵀr/L_nd`; bound `‖x‖‖r‖/L_nd`; `‖x_dbc‖`.
6. Check 2: `K = GetStiffnessMatrix<Operator>(DIAG_ONE)`; `uᵀKu ≥ (fᵀu)²/L_nd` for
   `u = x` and four random constrained fields.
7. Write `postpro/first-moment.json`; `palace.json` carries dof counts, solver
   totals and timings as for every driver.
8. Offline: `evaluate_record.py --record <dir>` attaches the hashes, recomputes
   `A_saved`, runs the checks of §5 and writes the comparison.

## 8. One execution proposal (for separate approval)

`proposal.json` is the full statement. In brief: build
`docker/palace-first-moment.Dockerfile` (Palace v0.13.0 `a61c8cbe` + patch
`31b5bd29…`), run **once** with `docker run --rm --network none … -np 1
config.json` on a work directory holding `config.candidate.json` (as
`config.json`, sha256 `6d791a2d…`) and N2R's mesh (sha256 `d8dc1a92…`), under
the 250 000-DOF and 2 700 s hard caps, no retry; commit the record with the
hashes listed in §5 and its evaluation. **No workflow runs this and none is
added here**: the approval must name the mechanism (a separate manually
dispatched workflow, or a local run whose record is committed) and must not
reuse the spent PO1 approval or edit `.github/ladder-approval.json`. It
authorises no eigensolve, no driven sweep, no N3, no Route A/B, no real-data
`E_C` or `g`, no registered-definition change, no historical-record rewrite, no
budget or cap increase and no merge of PR #7.

## 9. Files

| file | role |
|---|---|
| `docker/patches/first-moment-diagnostic.patch` | the Palace patch (9 files; `git apply --check` verified against `a61c8cbe`) |
| `docker/palace-first-moment.Dockerfile`, `.dockerignore` | the image that applies it; built by no workflow |
| `experiments/first-moment-diagnostic/reference_model.py` → `.json` | the algebra against the pinned source, verified on 60 synthetic fixtures |
| `experiments/first-moment-diagnostic/prepare.py` → `config.candidate.json`, `config.delta.txt`, `proposal.json` | the candidate, its literal delta, the proposal, the recomputed saved moments |
| `experiments/first-moment-diagnostic/evaluate_record.py` → `fixture_evaluation.json` | the post-run evaluator, exercised on the fixture only |
| `tests/test_first_moment_diagnostic.py` | 31 tests: mass operator, functional access, units, null space, outputs, preparation-only guards |
