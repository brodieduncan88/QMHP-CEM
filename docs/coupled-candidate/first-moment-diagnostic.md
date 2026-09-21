# The direct first-moment diagnostic — PREPARED, NOT APPROVED, NOT EXECUTED ON N2R

**What this note now covers.** The implementation is accepted as the direction;
this revision makes three corrections and adds one qualification. The error
statement is replaced by an exact identity and a *certified one-sided* bound;
provenance is made fail-closed and the caps are given a real enforcement
mechanism, prepared but not activated; and the C++ has been **compiled and run**
on synthetic, non-QMHP fixtures against an independently assembled answer. No
N2R assembly, solve, `A`, `N`, `E_C` or `g` exists. Record:
`experiments/first-moment-diagnostic/`; patch
`docker/patches/first-moment-diagnostic.patch`, sha256 `e8a1ad51d4e355b0426e84c70cb9c796a4915b1216bb035d5fe60913de512fee`.

## 1. The error qualification, corrected

The previous `ResidualBound = ‖x‖‖r‖/L` was **not** a bound. With `x` the
computed solution, `r = M x − f` and `x* = M⁻¹f`, substituting `f = M x − r`
into both quadratic forms gives the exact identity

```
f^H x      = x^H M x − r^H x
f^H M^-1 f = x^H M x − 2 Re(x^H r) + r^H M^-1 r
=>  A_computed − A_exact = ( Re(x^H r) − r^H M^-1 r ) / L
```

that is, **A_computed − A_exact = (Re(xᴴr) − rᴴM⁻¹r) / L**. It is verified on
synthetic fixtures to `7.3e-16`
relative to `A` (measured against `|A|`, not against the cancelling difference).

**What is certified.** `M` is SPD, so `rᴴM⁻¹r ≥ 0` and therefore

```
A_computed − A_exact  <=  Re(x^H r) / L          (certified, no conditioning information)
A_exact               >=  A_computed − Re(x^H r) / L
```

The same number is the variational lower bound `(2fᵀx − xᵀMx)/L`; the two agree
to `4.4e-16`.
Over all trials there were **0
violations** of the certified bound. For a conjugate-gradient iterate from a
zero start, `xᵀr = 0` in exact arithmetic, so `A_computed` *underestimates*
`A_exact`; the computable `Re(xᴴr)/L` term covers the floating-point case
without assuming it.

**What is not certified.** A certified *upper* bound on `A_exact` needs
`rᴴM⁻¹r`, hence a lower bound on `λ_min(M_free)` or a second solve. Neither is
measured and neither is authorised, so **no upper bound is reported** and
`CertifiedUpperBound` is written as `UNAVAILABLE`. `‖x‖‖r‖/L` is retained only
as `UncertifiedErrorEstimate`, and the record says in words that it **is an
ESTIMATE, not a bound**. The checkable condition that would promote it is
stated with its threshold: `λ_min(M_free) ≥ ‖r‖/‖x‖`.

**Counterexamples, not assertions.** Take `M = diag(1, ε)`, `x = (1,0)`,
`r = (0, δ)`. Then the error is `−δ²/ε` while `‖x‖‖r‖ = δ`, so the old quantity
fails whenever `δ > ε`:

| ε | δ | relative residual | \|error\| / estimate |
|---|---|---|---|
| 1e-12 | 0.0001 | 1.0e-04 | 1e+08x |
| 1e-16 | 1e-13 | 1.0e-13 | 1e+03x |
| 1e-08 | 1e-06 | 1.0e-06 | 100x |

The middle row has a relative residual of 1e-13 — it would **pass** the
residual check — and still violates the old quantity by a factor of 1000. The
certified bound holds in every row.

**Two uncertainties, kept apart.** The record and the evaluator never merge
them:

- *Mass solve*: the identity, `Re(xᴴr)`, the certified error bound, the
  certified lower bound on `A`, the uncertified estimate and its sufficient
  condition.
- *`A_saved`*: Palace prints every column with `%+.9e`, so the printed
  precision alone gives an exact interval for `A_saved = Σ|p_m|f_m²` — half
  width `1.657e-09` GHz²
  on the all-nine sum. The eigensolver's own convergence error is a *separate*
  contribution that the committed record does not quantify: `eig.csv` reports a
  backward error (max `5.311e-11`)
  and an absolute error (max `3.971e-05`),
  but turning either into an error on `p_m` needs a spectral gap that is not
  measured. It is carried as `UNQUANTIFIED` and must be accounted for before
  any tail conclusion.

**Verdicts.** Because every mode weight is non-negative, `A_exact ≥ A_saved`.
So the evaluator returns one of:

- `OMITTED_MOMENT_CERTIFIED_LOWER_BOUND` — `A_certified_lower − A_saved_hi > 0`;
  the omitted modes carry *at least* that much first moment.
- **`INCONSISTENT`** — a materially negative difference, beyond both
  uncertainties. The non-negative weights forbid it, so it is either an
  under-converged mass solve or a mismatch of functional, space or
  normalisation. It is **never** labelled an omitted moment.
- `NOT_RESOLVED` — inside the combined uncertainty. Not evidence of a small
  tail: with no certified upper bound, `tail_upper_bound` is always
  `UNAVAILABLE`.
- `UNQUALIFIED` — any check failed.

On the fixture, where the omitted moment is known by construction
(`1.751108261251e-07`), the evaluator measures `1.751108261252e-07` and its
certified lower bound stays below the truth.

## 2. Provenance fails closed, and the caps have a mechanism

**Nothing expected is reported as verified.** `prepare.py` emits a
`required_provenance` block: `PALACE_VERSION`, `PALACE_COMMIT`,
`PALACE_PATCH`, `PALACE_PATCH_SHA256` and the sha256 of the config, mesh,
patch and Dockerfile, plus the image ID the execution must supply. The driver
does not take these on trust: it **reads** `PALACE_VERSION`, `PALACE_COMMIT`,
`PALACE_PATCH` and `PALACE_PATCH_SHA256` out of the image at `/opt/palace` and
writes them into the record, marking any absent file `unavailable`. The
directory it read is recorded, and `ImageInfoDirIsDefault` is false for a
developer build, which cannot then qualify as an image run.

The evaluator requires *all* of it. Missing, `unavailable`, mismatched against
the required value, or a measured digest that differs from the required one —
each fails a named check, and any failure makes the verdict `UNQUALIFIED`. The
fixture exercises nine spoiled variants, including a developer build, a
withheld required image ID and a mismatched mesh digest.

**The caps.** The bare `docker run` in the earlier proposal was not a timeout
mechanism. `experiments/first-moment-diagnostic/run_diagnostic.py` is that
mechanism and is **PREPARED, NOT ACTIVATED**: it refuses unless
`EXECUTION-APPROVAL.json` exists beside it and matches the prepared digests,
and that file is deliberately absent, so the module cannot start a solve. When
an approval does exist it reads the container line by line under a deadline and
kills it on expiry; probes the streamed log for Palace's finest-space
`ND (p = 1)` count and kills the container the moment it exceeds the budget;
and writes image ID, repo digests, labels, the four `PALACE_*` files and every
input digest to `provenance.json`. The **250 000**-DOF rule and the **2 700 s**
cap are carried as **hard caps, not runtime promises**, and a run that hits
either is FAILED, never retried.

## 3. Compiled, and qualified on synthetic fixtures

**The image could not be built here.** `docker build` of
`docker/palace-first-moment.Dockerfile` fails at the base-image pull: the
session's egress gateway answers **403 to CONNECT** for
**production.cloudfront.docker.com**:443, Docker Hub's blob CDN, while fetching
the digest-pinned `ubuntu:24.04`. That is an organization policy denial, so it
was reported and **not routed around**: no alternative registry or mirror was
used. The image ID, repo digest and in-image `PALACE_PATCH_SHA256` that a
qualifying run must carry can only be produced where that host is allowed.

**What was compiled instead.** The pinned tag was cloned from GitHub
(`git clone --branch v0.13.0 --depth 1`), its commit asserted equal to
`a61c8cbe0cacf496cde3c62e93085fae0d6299ac`, the committed patch applied with
`git apply --check` then `git apply`, and Palace built natively with the
Dockerfile's own CMake options (SLEPc on, SuperLU on, GSLIB on, CUDA/HIP off,
Release, `-O2`). All nine patched files in the build tree were verified
byte-identical to a fresh clone with the committed patch applied. This is a
developer build, not the reviewed image, and every record it produced says so.

**The independent answer.** `synthetic_fixture.py` assembles the lowest-order
Nédélec mass matrix and the port linear form from the Whitney element formulas,
in Palace's nondimensional units, and solves the free-dof system densely. It
shares no code with Palace or MFEM. It carries its own exact self-check: the
space reproduces constant vector fields, so `uᵀMu` must equal `Σ ε_K |c|² V_K`
— which it does to
`5.3e-16`.
That invariant caught a transposed Jacobian inverse in the first version of the
assembler, which had left the volumes right and the mass matrix wrong.

**The fixtures** are a plain two-material brick, 2 × 1 × 1 mm, ε_r 1 and 4, one
lumped port on the x = 0 face and PEC on two faces — deliberately unlike the
QMHP cell, and the qualifier refuses any config that is not one of them.

| check | result |
|---|---|
| A against the independent assembly | `8.9e-16` relative |
| dof counts, `Lc`, `t_c`, `A_GHz²` conversion | agree exactly |
| functional vs `GetVoltage` (complex, PEC-constrained) | `0e+00` |
| PEC restriction actually bites | `‖f_PEC‖² = 2.273e-02 > 0`, `‖x_PEC‖ = 0` |
| exact 1/L scaling | `1.8e-16` relative |
| JSON output finite | yes |
| non-convergence (`MaxIts: 1`) | `Converged: false`, relative residual `0.41` |
| failed check (inactive port) | exit 1, structured `FAILED` record with provenance, **no** `first-moment.json` |
| log preserved | in every run, including the failures |

The unconverged run is the sharpest confirmation of §1 on real compiled output:
it **underestimates** `A` by `9.954`
(nondimensional), its certified lower bound still holds against the known
answer, and there the old quantity's sufficient condition
`λ_min(M_free) ≥ ‖r‖/‖x‖` **fails** — exactly the regime where the estimate is
not a bound.

**The parallel path and fault injection.** The same fixture run at 1, 2, 3 and
4 MPI ranks gives `A_nd` identical to 15 significant figures. A second binary
was built with `GetVoltageFunctional` taking the leading true-dof entries of
the local linear form instead of the dual assembly `Pᵀv`. It is
**caught at four ranks** — the driver aborts with the structured FAILED record
and writes no result — and is silent at one to three ranks, where the two
expressions coincide for this partitioning. That is a limit of the fixture,
not a pass: this fixture cannot falsify a dual-assembly error below four ranks,
and the note says so rather than claiming the check is proven in general.

**The sampled check is not a proof.** `uᵀKu ≥ (fᵀu)²/L` is evaluated on the
solution and four random constrained fields and is recorded with
`IsSampledNotProof: true`. It is a runtime sanity check on finitely many
vectors. The argument that `K ≥ q qᴴ` holds for *every* vector is the separate
quadrature-parity argument against the source (§4 of the previous revision:
the voltage form and the port stiffness share `DefaultIntegrationOrder`'s rule,
order 2, positive weights), and the two are kept apart.

## 4. The updated execution proposal

Unchanged in substance: **one** execution of `config.candidate.json` (N2R's
solved config with only the problem type and solver block changed, shown by
literal diff) on N2R's mesh, no retry. Changed in mechanism: it runs through
`run_diagnostic.py`, which enforces the **250 000**-DOF and **2 700 s** hard
caps and captures provenance, and it needs an image built where the Docker Hub
CDN is reachable. The approval must name the mechanism; it must not reuse the
**spent PO1 approval** or edit `.github/ladder-approval.json`. It authorises no
eigensolve, no driven sweep, no N3, no Route A/B extraction, no real-data `E_C`
or `g`, no registered-definition change, no historical-record rewrite, no
budget or cap increase and no merge of PR #7. Whatever the number,
`E_C` stays UNAVAILABLE and `g` stays blocked.

## 5. Files

| file | role |
|---|---|
| `docker/patches/first-moment-diagnostic.patch` | the Palace patch (9 files; applies to `a61c8cbe`; compiled and run here) |
| `docker/palace-first-moment.Dockerfile`, `.dockerignore` | the image that applies it; built by no workflow, and not buildable in this session |
| `experiments/first-moment-diagnostic/reference_model.py` | the algebra, the error identity, the counterexamples, the record schema and the evaluator |
| `experiments/first-moment-diagnostic/synthetic_fixture.py` | the non-QMHP fixtures and the independent Whitney assembly, with its constant-field invariant |
| `experiments/first-moment-diagnostic/compiled_qualification.py` | runs the fixtures through the compiled binary; refuses anything else |
| `experiments/first-moment-diagnostic/run_diagnostic.py` | the launcher: caps and provenance, PREPARED, NOT ACTIVATED |
| `experiments/first-moment-diagnostic/prepare.py`, `evaluate_record.py` | the candidate and proposal; the fail-closed evaluation |
| `tests/test_first_moment_diagnostic.py` | 47 tests |
