# QUTIP-A-READOUT-CROSSCHECK-v1: Branch-A fixed-point QuTiP cross-check (draft protocol)

**Status: PREPARED, NOT APPROVED, NOT EXECUTED. Scientific execution is BLOCKED.**

- **What exists.** This document, the schema, the exporter, the standalone checker and contract tests on synthetic fixtures.
- **What does not exist.** No reference snapshot has been generated. No QuTiP calculation has been run. No approval, frozen-rules file or execution record exists.
- **Basis.**
  - The owner-supplied *QMHP–QuTiP Integration Brief* (25 September 2026, 8 pages). The brief was read at pinned commit `3d14c095e7ac4b8971f5476bd9a9f315ba7df2e1`.
  - The fifteen files the brief lists are byte-identical at the commit where this bridge was prepared (`e8a3c7f`).
- **Policy.** AGENTS.md and CLAUDE.md govern and are additive. Where they and this document differ, the stricter rule applies.

## 1. The question, and what the answer cannot mean

**Question.** At one frozen operating point, does a QuTiP operator/tensor assembly of the declared finite model reproduce the CEM-assembled Hamiltonian, and, with the same eigensolver and labelling rule, the CEM spectrum and named observables, when both receive the same static spectrum and charge matrix?

**The only claim this bridge may make:** independent QuTiP operator/tensor assembly of the same finite model, followed by a controlled numerical comparison.

**What is and is not independent of CEM:**

| step | implementation | independent of CEM? |
|---|---|---|
| operator and tensor assembly | QuTiP: `Qobj`, `tensor`, `qeye`, `num`, `destroy`, `dag` | yes, the one independent step |
| charge-element omission below 1e-14 | NumPy `where`/`abs`, the same rule as CEM | no, a shared convention |
| dense eigensolve | `numpy.linalg.eigh(UPLO='L')` on `Qobj.full()`, the **same routine** CEM calls | **no** |
| state labelling | NumPy argmax of \|⟨bare\|dressed⟩\|², the same rule as CEM | no |
| observables | NumPy formulas equivalent to `models/dressed_system.py` | no |
| SciPy | not called directly (QuTiP may use it internally) | — |

So agreement of eigenvalues, labels and observables is a consistency check that follows from the assembly comparison. It is **not** an independent eigensolver or labelling result.

**What it does not validate:**
- the supplied static fluxonium spectrum or charge matrix;
- any electromagnetic extraction, geometry or continuum convergence;
- hardware;
- coupling extraction;
- the QMHP architecture.

**How independent the check is.** NumPy/SciPy and QuTiP can share numerical libraries, so agreement is not fully independent numerical evidence (AGENTS.md §6). Shared-input agreement does not validate how those inputs were built.

**Coupling g.** The reference g = 0.150 GHz is classified VERIFIED-COMPUTATIONAL: a reference coefficient from the release readout-replication script. It is **not** a geometry-derived or S1-extracted coupling. It must never be substituted for one or labelled as one. A future geometry-derived branch needs its own authorised parameter record and its own approval. If those inputs are missing, that branch is BLOCKED; the reference values do not stand in.

**Not in v1:**
- no frequency or root search;
- no mediator or Branch B;
- no rotating-wave or two-level substitution;
- no drive;
- no dissipation or Lindblad dynamics;
- no sweep.

The Purcell model needs κ at the dressed emission frequency, and there is no default κ (`models/purcell.py`). No loss rate is guessed.

## 2. The declared finite model

| item | value | classification (existing) |
|---|---|---|
| E_C/h, E_J/h, E_L/h | 0.60, 5.72, 1.58 GHz | MASTER-FROZEN (`branch_a_device`) |
| φ_ext | π (exported as the float `3.141592653589793`, with symbol `pi`) | MASTER-FROZEN |
| phase grid | 3201 points on [−8π, +8π], second-difference kinetic operator | MASTER-FROZEN / VERIFIED-COMPUTATIONAL |
| retained levels, photons | N_q = 10, N_ph = 12 (120 states) | MASTER-FROZEN (`production_convention`) |
| readout frequency f_R | 4.301974466 GHz, **held fixed** | MASTER-FROZEN (`production_convention.root_GHz`) |
| coupling g | 0.150 GHz | VERIFIED-COMPUTATIONAL |
| logical states / sink | levels {0, 2} / level 1 | MASTER-FROZEN |

**Hamiltonian**, with fluxonium first and resonator second, and flat index `level*Nph + photon`:

```
H/h [GHz] = F (x) I_12  +  f_R * I_10 (x) num(12)  +  g * n_skip (x) (a + a^dag)
```

- **F** is the diagonal matrix of the ten retained frequencies, taken relative to the ground state.
- **n** is the full signed, complex charge matrix n_ij = −i⟨i|d/dφ|j⟩, exported unmodified as real and imaginary parts.
- **n_skip** equals n, except that elements with |n_ij| < 1e-14 are omitted. This is the existing `models/dressed_system.py` assembly convention, kept for a like-for-like comparison and recorded in the snapshot. Nothing is:
  - replaced by an absolute value;
  - partially rephased;
  - symmetrised by averaging;
  - normalised away.
- **num(12)** is used rather than a†a, so that the photon-number diagonal is exactly 0…11. The CEM baseline uses `readout * photon` with an integer photon number, and the product a†a would round.

**Eigensolve.** An explicitly selected dense solver: `numpy.linalg.eigh(H, UPLO='L')`. The CEM baseline uses the same call on its assembled matrix. On the QuTiP side it is applied to `Qobj.full()`. **This eigensolver is shared with CEM, not independent of it.** It reads only the lower triangle, so the full-matrix entry comparison, not the eigenvalues, is what detects an upper-triangle difference.

**QuTiP tidy-up.** QuTiP's automatic tidy-up is switched off (`CoreOptions(auto_tidyup=False)`) for the whole assembly. The declared model omits only charge elements below 1e-14; tidy-up would silently zero other small entries. If the installed QuTiP has no `CoreOptions`, the checker is BLOCKED.

**Equivalence, not byte identity.** The QuTiP product g·(n_ij·x_pq) may differ from CEM's (g·n_ij)·x_pq in the last bit. The comparison is numerical equivalence within the frozen threshold, not byte identity (CLAUDE.md §13).

**Hermiticity is a gate, not a note.** The charge matrix is built from a finite-difference derivative, so it need not be exactly Hermitian at round-off. The Hermiticity defect max |H − H†| of both matrices is measured and recorded, never repaired.
- It is a named check, `hermiticity`. It PASSES only if both the QuTiP-assembled and the baseline matrix are within the approved `max_hamiltonian_hermiticity_defect_GHz`. A non-finite defect FAILS.
- `eigh(UPLO='L')` reads only the lower triangle, so the eigensolve cannot see an upper-triangle defect. If `hermiticity` FAILS:
  - the eigensolve, labelling and observables are **not run**;
  - the eigenvalue, labels and observable checks are all reported NOT-EVALUATED, with no difference value.
- The Hamiltonian entry comparison does not depend on the gate and is always reported.
- No matrix is ever symmetrised, averaged with its adjoint or otherwise repaired.

**Labels.** The existing maximum-bare-overlap rule is used. For each bare (level, photon) with level ∈ {0,1,2} and photon ∈ {0,1}, the label is the dressed index maximising |⟨bare|dressed⟩|², taking the first maximum on exact ties.
- The overlap and the runner-up overlap are recorded.
- Duplicate or ambiguous assignments are **reported, not repaired**. There is no frequency-proximity fallback, and frequencies are never chosen because they "look right".
- **Labels gate the observables.** Labels are a named check, `labels`. It PASSES only if no label is duplicated or below the frozen minimum overlap or margin, and the assignment equals the baseline's. Otherwise it FAILS, and every observable check is reported NOT-EVALUATED. The Hamiltonian and eigenvalue checks are still reported. If the Hermiticity gate fails, `labels` itself is NOT-EVALUATED.
- **The ambiguity rule is not yet approved.** Until a frozen-rules file supplies it, execution is BLOCKED; the checker invents no criterion.
- **Schema slack.** The schema allows overlaps up to 1.000000001. That is floating-point slack for a squared eigenvector component, **not** a scientific acceptance tolerance.

**Observables:**
- the full ordered spectrum;
- the readout pulls of levels 0, 1 and 2 in MHz;
- the sink–logical contrast;
- the sink line, f_R + pull₁/1000, in GHz;
- the dressed emission E(2,0) − E(1,0), in GHz;
- the F8 weight |⟨dressed(1,0)| I ⊗ a |dressed(2,0)⟩|².

**F8 contraction: an implementation note (the Mac Accelerate issue).** The checker evaluates the F8 scalar Σᵢⱼ conj(v1ᵢ) Aᵢⱼ v2ⱼ with `np.einsum("i,ij,j->", v1.conj(), A, v2, optimize=False)`, not with a chained `v1.conj() @ A @ v2`. Here v1 and v2 are the dressed (1,0) and (2,0) eigenvectors and A = I ⊗ a.
- **Why.** The owner reported a problem with the chained matmul route on the Mac, whose NumPy is linked to Apple Accelerate. The observed symptom is recorded by the owner, not here, and was not reproduced in this repository's environment.
- **What changes.** With `optimize=False`, `np.einsum` calls NumPy's own C einsum (`c_einsum`) directly, rather than the matmul route that goes through the linked BLAS. That dispatch was read in NumPy 2.4.6's `einsumfunc.py`; the Mac's NumPy 2.0.2 source and the C internals were not inspected.
- **What does not change.** The observable's definition, the Hamiltonian, the labels and the thresholds. Nothing is symmetrised or repaired.
- **Equivalence.** The summation order differs, so the two routes agree to round-off, not bit for bit (CLAUDE.md §13). The contract tests check the einsum route against exact rational arithmetic on the same inputs and against the previous chained form.

## 3. Acceptance rules: existing rules and proposed rules are kept apart

### 3.1 Existing rules (unchanged by this protocol)

These are `master/qmhp_v158f_requirements.yaml` `regression_pins` and `docs/regression-pins.md`. This protocol neither edits nor merges them.

- **exact** group (MASTER-FROZEN, 1e-6 relative): the dressed roots, f01, f02 and sin_delta_over_2_02.
- **display_precision** group: sink line 4.310696 GHz, dressed emission 3.395056 GHz, contrast 18.228 MHz and n12. Each is compared at its printed decimals.
- **cross_implementation** group: **FLAGGED-FOR-REVIEW**, 5e-6.
  - It covers the F8 weight, the sink pull and the logical pull.
  - These discrepancies stay flagged. A same-input QuTiP agreement neither resolves them nor hides them behind a blanket PASS.

The frozen display references are **references, not results**. They were evaluated at a more precise root, and they are identified separately from the paired same-frequency comparison below.

### 3.2 PROPOSED ENGINEERING-RULES for the same-input CEM-versus-QuTiP comparison

These are **not** frozen master requirements. They are **not approved**, and **no result was used to choose them**. They are initial engineering thresholds, not error bounds.

| comparison | proposed absolute limit (relative tolerance 0) |
|---|---|
| maximum Hamiltonian entry difference | 1e-12 GHz |
| maximum ordered eigenvalue difference | 1e-10 GHz |
| each readout pull, and the sink–logical contrast | 1e-6 MHz |
| sink line, and dressed emission frequency | 1e-9 GHz |
| F8 weight | 1e-10 |

**Still to be frozen by a human before any evidence-bearing run.** The checker refuses to calculate without a hash-bound frozen-rules file carrying all of these:
- `rules_status: "FROZEN-BY-HUMAN-APPROVAL (ENGINEERING-RULE, not MASTER-FROZEN)"`. Any other status, including the proposed values copied into a file without that approval, keeps execution BLOCKED. The file is agent-writable, so this is a declaration, not proof of authorisation;
- the thresholds above, as approved;
- the label rule: a minimum assigned overlap and a minimum margin over the runner-up;
- the maximum Hamiltonian Hermiticity defect, which is a gate (§2);
- `approved_runtime`: the exact `python_version`, `numpy_version`, `scipy_version` and `qutip_version` strings. The values live only in this file; no version is hard-coded in the checker. A missing field is BLOCKED, an empty or non-string one is REJECTED, and a field the checker does not enforce is REJECTED;
- the wall-time and memory limits;
- `permitted_attempts: 1`;
- the eigensolver string;
- an approval reference.

If the comparison fails, none of these is relaxed.

The primary comparator is the paired CEM calculation at the **same** fixed frequency. The fixed frequency is never changed to improve agreement.

## 4. The JSON handoff

- **Schema.** `schemas/qutip/branch-a-reference-v1.schema.json` (`$id` `qmhp-cem.qutip-branch-a-reference/1`).
- **One source of truth.** The checker enforces that exact file. It refuses any schema keyword outside the subset it implements, so the schema cannot quietly declare a check that is not made.
- **Required content.** The snapshot carries every field the brief lists:
  - provenance: schema, protocol ID, payload kind, evidence scope, repository, source commit and clean-tree flag, source-file hashes, master revision and hash;
  - declarations: branch, classifications, units, E_C, E_J, E_L and φ_ext, the phase-grid definition, N_q, N_ph and dimension, tensor order and flat index;
  - the operating point: the fixed readout frequency, and `root_search_performed: false`;
  - the coupling: g, its classification, `coupling_is_geometry_derived: false`, and its note;
  - the inputs: the 10 frequencies, the real and imaginary 10×10 charge matrix, and the skip threshold and rule;
  - the baseline: the real and imaginary 120×120 CEM Hamiltonian, the eigensolver, the 120 ordered eigenvalues, the label convention and labels with scores, the observables, the diagnostics, the runtime, and the implementation hashes.
- **Payload kind.** `CEM-EXPORT` or `SYNTHETIC-TEST-FIXTURE`. Synthetic fixtures exist only inside unit tests and are never evidence. The checker refuses to execute them.
- **Authentication is outside the payload.** The snapshot, schema and frozen-rules hashes, plus the expected source hashes, are supplied separately. A self-reported digest, or an approval flag an agent wrote, is not proof of human authorisation. The exact bytes are hashed.
- **The expected-hashes record is itself bound.** Its sha256 is supplied on the command line as `--expected-sha256` (lowercase hex). Without it the checker is BLOCKED; a record with any other hash is REJECTED. Otherwise a tampered snapshot shipped with its own self-consistent record would validate. The measured record hash is carried into the VALIDATED line and into `attempt.json` and `result.json`.

## 5. The exporter (`scripts/export_qutip_branch_a_reference.py`)

- **Where it runs.** Only in the supported CEM environment (Python ≥ 3.11, `uv.lock`). Its default is `--dry-run`: it reports the plan, source hashes and tree state, and performs no solve.
- **What it calls.** The existing functions only:
  - `fluxonium.nominal_spectrum(levels=10)`;
  - `dressed_system.solve_dressed(4.301974466, spectrum, 10, 12, g_GHz=0.150)`;
  - `DressedSolution.purcell_weight()`.

  It never calls `nominal_solution()` or `dressed_spectrum()`, and nothing that triggers `brentq`.
- **Root-search guard.** For the duration of the call, those entry points are replaced by functions that raise.
- **Capturing the exact matrix.** The exporter wraps the `eigh` that `models/dressed_system.py` calls. So the baseline is the matrix production actually diagonalised, not a re-assembly. A second `eigh` call is refused, because a root search would make many.
- **Production code is untouched.** Wrapping is scoped and restored in a `finally` block on success and on every exception. No production file is modified.
- **Capture count.** Zero captured matrices or more than one refuse the export.
- **Nesting and concurrency.** A process-wide lock refuses a nested or concurrent guard. **Limitation:** the lock cannot stop an unrelated thread from calling `models.dressed_system` while a guard is active. The exporter is a single-threaded CLI and must stay one.
- **`--execute` requires all of the following:**
  - a clean tree;
  - a new output directory outside `results/` and `master/`;
  - `--approval FILE` and `--approval-sha256`, bound to protocol, commit and output.

  The exporter validates the snapshot bytes with the standalone checker's schema and structural checks before writing. It then writes a `manifest.sha256` with `orchestrator/manifest.write_verified`.
- **Enforcement limit.** An approval file is agent-writable. The approved launcher, not this script, must enforce authority, attempt count and resource limits.

## 6. The standalone checker (`tools/qutip_bridge/check_branch_a_reference.py`)

**Runtime.** It targets the owner's Mac. The brief names Python 3.9.6 and QuTiP 5.0.4, with NumPy 2.0.2 and SciPy 1.13.1 observed in conversation; that is context, not a qualification, and the checker does not use those numbers. It uses Python 3.9 syntax and imports no QMHP-CEM module. Validation needs only the standard library.

**Runtime gate.** Before anything is written or calculated, the actual `python_version`, `numpy_version`, `scipy_version` and `qutip_version` are compared exactly, character for character, with the frozen-rules `approved_runtime`.
- A missing approval, an unreadable version (a module that fails to import or has no `__version__`) or any mismatch is BLOCKED. Nothing is written and nothing is calculated.
- Reading a version imports the module; importing is not a calculation.
- The platform and the linked numerical libraries are recorded, not qualified.

**It validates before any calculation, in this order:**
1. file presence (BLOCKED if missing);
2. the expected-hashes record bytes against `--expected-sha256` (BLOCKED if not supplied, REJECTED on mismatch), before the record is parsed;
3. strict JSON, rejecting NaN, Infinity, overflowing literals and duplicate keys;
4. the schema, covering required fields, constants (protocol, units, tensor order, N_q/N_ph, readout, g, threshold), exact list shapes and types;
5. the external hashes: snapshot bytes, schema bytes, source commit, source-file, master and implementation hashes;
6. structural checks:
   - frequencies start at 0 and do not decrease;
   - eigenvalues are ascending;
   - the baseline diagonal equals frequencies[level] + f_R·photon bit for bit, in the declared tensor order;
   - there are no entries outside the g·n(a+a†) pattern;
   - the skip count, label completeness and consistency, and the observable aliases agree.

**Calculation.** It needs `--execute` plus a hash-bound frozen-rules file and a new output directory. Without them it stops at VALIDATED or BLOCKED. The runtime gate then runs before anything else.

**The record.** Execution writes an append-only record in this order: `attempt.json` first, then `raw.json`, then `result.json`, then `manifest.sha256`.
- `attempt.json` and `result.json` carry the measured `expected_sha256`. `attempt.json` also carries the approved-versus-actual runtime comparison.
- Execution status, provenance qualification and scientific verdict are separate fields.
- The named checks are `hermiticity`, `hamiltonian_max_entry`, `ordered_eigenvalues_max`, `labels` and the seven observables. Each has its own PASS, FAIL or NOT-EVALUATED, tied to the frozen-rules sha256. The tool issues no overall verdict.
- Provenance is reported as INPUTS-HASH-VERIFIED and RUNTIME-VERSIONS-MATCHED. The platform and linked libraries are recorded, not qualified.

**Failures.** A failure is preserved and never retried. The in-process timer is not a hard stop; the external launcher must enforce the limits.

**Exit codes:** 0 validated or executed; 2 BLOCKED; 3 REJECTED; 4 EXECUTION-FAILED.

## 7. Contract tests (`tests/test_qutip_bridge_contract.py`)

They use **synthetic** fixtures only: made-up frequencies and a seeded charge matrix, with `payload_kind: SYNTHETIC-TEST-FIXTURE`. They build no physics snapshot and run no QuTiP calculation.

- **Positive control:** a consistent synthetic payload validates.
- **Negative controls:**
  - wrong shapes;
  - a missing charge entry or field;
  - NaN, Infinity and overflow;
  - reversed tensor order;
  - wrong units;
  - snapshot, schema and source-hash mismatches;
  - an altered baseline, both with and without re-hashing;
  - a boolean or text in place of a number;
  - integer-to-float;
  - ×100 corruption;
  - a duplicate or ambiguous label;
  - a root-search entry point reached through the exporter guard;
  - a second `eigh`;
  - an altered fixed frequency;
  - executing a synthetic payload;
  - a CEM import, or Python-3.10-only syntax, in the checker;
  - pickle, eval or exec use;
  - a missing, wrong, truncated or upper-case `--expected-sha256`, and a substituted self-consistent expected-hashes record;
  - a missing, null, empty, non-string or unenforced `approved_runtime` field, and every runtime version mismatched, suffixed or unavailable;
  - a non-Hermitian independent matrix, baseline matrix or both (upper-triangle only, invisible to `eigh(UPLO='L')`), the exact-limit boundary, a non-finite defect and an invalid limit;
  - the F8 einsum contraction against exact rational arithmetic and the previous chained `@` form, with static checks that no `@` and no symmetrisation or repair remain.
- **Not run in this environment:** QuTiP is not installed here and was not installed, so the QuTiP assembly path is exercised by no test.

## 8. What would be needed to execute, and in what order

Each step is a separate human approval (AGENTS.md §3, CLAUDE.md §2–3). None is granted by this document.

1. Review, and if accepted commit, these prepared files. Record their hashes.
2. Approve the numerical export:
   - the source commit;
   - the output path;
   - the approval record and its sha256;
   - one attempt;
   - the environment (the CEM `uv.lock` runtime).
3. Freeze the frozen-rules file: thresholds, label rule, Hermiticity limit, the approved runtime versions, wall-time and memory limits, eigensolver and one attempt. Record its sha256.
4. Build the expected-hashes record from the verified export:
   - the snapshot and schema bytes;
   - the source commit;
   - the source-file, master and implementation hashes.

   Record its sha256; it is passed as `--expected-sha256`.
5. Approve one QuTiP execution on the Mac through a launcher that enforces the limits and passes `--expected-sha256` and `--frozen-rules-sha256`. The checker refuses to calculate unless the runtime matches the approved versions exactly.

Open items:
- the launcher mechanism for the Mac;
- where the returned record is verified and stored;
- retention.
