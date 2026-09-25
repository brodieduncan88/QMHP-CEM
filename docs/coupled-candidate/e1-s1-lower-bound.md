# E1 — the static-capacitance lower-bound certificate for the S1 island (problem C)

**Status: IMPLEMENTED; CORRECTED AFTER THREE FROZEN-CODE REVIEWS (contract revision 8.5). PRE-APPROVAL
EVIDENCE REGENERATED AND FROZEN (revision 8.5: the rehearsal and both Confirmations). APPROVED AND EXECUTED
ONCE (attempt 1 of 1, 2026-09-24): QUALIFIED.**

- **E1 has been executed once, and the one attempt is spent.**
  - It ran on a human approval at `4baeb67` (`E1-APPROVAL.consumed.json`).
  - Its record is `results/E1-S1-LOWER-BOUND-20260924T222847Z/`, committed with `ATTEMPT-SPENT.json` and `EXECUTION-LOG.json`. See "Execution" below.
  - There is no retry, and E1 is the last capacitance computation on S1 (contract §8).
- **What has and has not been computed on S1 panels.** The full account of the runs before the revision-8.5 regeneration, with every run, is in [`corrections/e1-confirmation-s1-internal-sets-correction.md`](corrections/e1-confirmation-s1-internal-sets-correction.md). The revision-8.5 runs are the last item below.
  - Before E1's execution, no set equal to S1's E1.2 or E1.2-excl-R1, and no set containing an image of either, had been assembled, factorised or used in any energy. E1's one approved attempt then did so.
  - The revision-8 prototype, and the Confirmation runs made with the `90bf9eb` implementation and with one pre-freeze build, did assemble, factorise and form energies and internal lower bounds for S1's island-only internal sets E1.1 and E1.1-half. Their stand-in's island was S1's island (D-1).
  - The E1.2 of those Confirmations and of the prototype's full-size runs (N = 9,995) also held 534 ground panels bit-identical to S1 E1.2 ground panels (476 of them in S1's E1.2-excl-R1). The E1.2 of the prototype's reduced run `run8_small` (N = 1,524) held 32 such panels. The stand-in's ground is synthetic, but it uses S1's lattice, window and merge rules.
  - Proxy A of the configuration selection contains S1's E1.1 translated by +0.6 mm in x. So every proxy-A Cholesky factorisation contains the factor of that translated E1.1 as its leading block. The same holds for proxies B and C of the selected configuration.
  - All of this was an **unintended pre-execution computation, not approved behaviour** (D14). Proxy A is kept as **historical** configuration-selection evidence only, and is not re-run (D15).
  - The two opt-in Confirmation tests of the suite (run only with `E1_RUN_CONFIRMATION=1`) were among those runs. The default test selection and CI use only small synthetic sets, apart from the S1 geometry phase, which assembles no matrix.
  - The revision-8.5 Confirmations (below) ran on the separated stand-in, whose island is synthetic. Its ground shares 534 individual panels with S1's E1.2, which D15 permits. No S1 attempt set, and no image of one, was assembled, factorised or used in an energy by them or by the revision-8.5 rehearsal.
- **Contract.** `experiments/e1-s1-lower-bound/E1-CONTRACT.rev8.5.md`, sha256 `2db93be49ee455f1da952acbe300f370d7614a8986c4151a9563adf805f00150`.
  - It is revision 8.4 (sha256 `cdf6cced…71740`, kept byte-unchanged beside it, as are revisions 8.3 and 8.2) with the two text corrections of D16.
  - Revision 8.4 was revision 8.3 with the structural separation rule and the corrected statements of D15.
  - The physics, the configuration, the thresholds, the Q2/C_br behaviour and the scope are unchanged.
- **What E1 certifies, and only that.** `C_static ∈ [C_lo^static, C_hi]` fF for the meshed S1 model (problem C, contract §1).
  - `C_lo^static` is a certified Thomson/Galerkin lower bound under the libm ASSUMPTION of contract §4.4.
  - `C_hi` = 67.9755386760262 fF, copied bit-exactly from the frozen static study.
- **Fixed statements in every state.**
  - `E_C,F1F1` is `EC_NOT_EVALUATED_BY_E1`.
  - Correspondence to the registered operator is NOT_ESTABLISHED, deviation NOT_EVALUATED, and suitability SUITABILITY_NOT_ASSESSED.
  - No E1 output contains a quantity in frequency units.
  - E1.1, E1.1-half and E1.2-excl-R1 are internal (K4 only).
  - `E_C` and `g` stay UNAVAILABLE.

## Files (`experiments/e1-s1-lower-bound/`)

| file | content |
|---|---|
| `E1-CONTRACT.rev8.5.md` | the frozen contract the code implements |
| `E1-CONTRACT.rev8.4.md`, `E1-CONTRACT.rev8.3.md`, `E1-CONTRACT.rev8.2.md` | the superseded revisions, byte-unchanged |
| `driver.py` | the attempt (contract §8), and the pre-approval modes `--rehearsal` and `--confirmation nominal\|forced`. The mode `--proxy-a-ge` refuses, computing nothing (proxy A is historical), and `--show-invocation` shows the measured invocation |
| `e1_numerics.py` | the entries in x87 long double; the derived entry-error constant `c0` and `q_B`; `m(N)`; the symmetric block-pair pass; `E_up` and RD; the no-underflow requirement; the in-place trial vector with its §4.5 fallbacks; check (g); the dispatch and arithmetic probes. A non-finite or non-positive quantity fails its requirement and never raises. So does a finite quantity outside the float64 range. |
| `e1_geometry.py` | the §4.1 model checks, island, R1 cut, candidates, merge, exact containment, the §3.3 counts, and N1, N2, N3b and N3c. It assembles no matrix. |
| `e1_controls.py` | K1, K2, K2b (with the frozen pair-list sha256), K3, N3 and N4. A non-finite value, or a finite one outside the float64 range, fails the control and never raises. |
| `e1_standin.py` | the stand-in of contract §6, the §3.2 item 2 separation rule, and proxy A of §3.2 item 5. The attempt never loads it and refuses if it is loaded, but the approval binds its sha256 (`preapproval_code_sha256`). |
| `E1-APPROVAL.draft.json` | the approval a human would grant, with the human's fields as placeholders; it authorises nothing |
| `rehearsal.json`, `proxyA-gE.json`, `confirmation-nominal.json`, `confirmation-forced.json` | the pre-approval evidence of `90bf9eb`: SUPERSEDED, kept byte-unchanged (see below) |
| `preapproval-confirmation-rev8.5/` | the revision-8.5 Confirmations, nominal and forced fallback: predeclaration, run script, outputs, logs, run records, the driver's sealed evidence directories, index and `MANIFEST.sha256` |
| `preapproval-rehearsal-rev8.5/` | the revision-8.5 rehearsal: predeclaration, run script, acceptance check script, output, logs, run records, index and `MANIFEST.sha256` |
| `ATTEMPT-SPENT.json`, `E1-APPROVAL.consumed.json`, `EXECUTION-LOG.json` | the spent attempt: its marker (byte-identical to the git-common-directory ledger entry), the consumed human approval and the operator's execution log. The record is `results/E1-S1-LOWER-BOUND-20260924T222847Z/` |
| `c2-stop-signal-test-diagnosis/` | why the C-2 stop-signal test was intermittent (its timing, not the implementation), and the evidence for its deterministic replacement |
| `APPROVAL-PACKAGE.rev8.5.json`, `APPROVAL-PACKAGE.rev8.5.md` | the approval candidate: every sha256 the approver is asked to approve, checked by a test; it authorises nothing |

The attempt was run once, from the repository root, exactly as contract §6 states:

    env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 1260 .venv/bin/python experiments/e1-s1-lower-bound/driver.py

## Execution (attempt 1 of 1): QUALIFIED

- **Approval.** A human approved one execution at `4baeb67` on 2026-09-24.
  - The approval is `E1-APPROVAL.consumed.json`, sha256 `b8f6883b6fa431aaca5778e135667bd5cfa0afd830822f908e263db263b8ee7d`.
  - It records `tolerance_scope_decision` `COPIED_NUMBERS_WITHIN_SCOPE` and `q2_within_D5` true, with tolerance set T0 and γ = 1e-6.
- **Run.** 2026-09-24T22:28:47Z–22:34:19Z, from `4baeb67`, with the declared invocation.
  - It exited 0 with stderr empty.
  - It used 331.4 s CPU and 1.43 GiB peak address space (budget 900 s and 4 GiB).
  - No stop signal arrived, and the provenance re-measurement was equal.
- **Record.** `results/E1-S1-LOWER-BOUND-20260924T222847Z/`.
  - It is sealed by its driver's `manifest.sha256`, sha256 `8d70ee11252c96fbbb0de5a666e963d8886273bafc7ad1aab4f36110f7f067ad`, which is pinned in the frozen-evidence guard.
  - It was committed with `ATTEMPT-SPENT.json`, `E1-APPROVAL.consumed.json` and the operator's `EXECUTION-LOG.json`.

| reported (`summary.json`) | value |
|---|---|
| outcome | QUALIFIED |
| C_static, problem C, the meshed S1 model | ∈ [57.220910, 67.975539] fF (C_lo^static rounded down, C_hi rounded up) |
| C_lo^static | 57.220910660500294 fF: the certified Thomson/Galerkin lower bound for E1.2, under the libm ASSUMPTION of contract §4.4, in the model's ε₀ convention |
| C_hi | 67.9755386760262 fF, copied bit-exactly from the frozen static study |
| Q2 | `MODEL_BRACKET_PREMISE_REFUTED` for this model, conditional on the libm ASSUMPTION: C_lo^static·(1 − 10⁻⁶) > C_br = 56.67470653023562 fF |

- **Diagnostics.**
  - All four sets ran on the Cholesky path, and K4 inequalities 1–3 PASS.
  - Check (g) is ≤ 3.2e-10 (limit 1e-7), and every relative enclosure width is ≤ 4.5e-8.
- **Fixed statements.** They hold in this state as in every other:
  - `E_C,F1F1` is `EC_NOT_EVALUATED_BY_E1`;
  - correspondence is NOT_ESTABLISHED, deviation NOT_EVALUATED and suitability SUITABILITY_NOT_ASSESSED;
  - there is no quantity in frequency units;
  - `E_C` and `g` stay UNAVAILABLE.
- **Tolerances.** The §7 scope decision is `COPIED_NUMBERS_WITHIN_SCOPE`, and no T1–T4 criterion was adopted before approval. So no tolerance may ever be applied to any number in, or derived from, any E1 file. That includes C_hi and anything formed from C_lo^static or C_hi.
- **Q2.** Contract §1 requires a separate correction record for the frozen study's model bracket. It is [`corrections/static-refinement-study-model-bracket-correction.md`](corrections/static-refinement-study-model-bracket-correction.md), and the frozen study is not edited.
- **Not blind.** E1 was not blind (contract §8): exploratory S1 values existed before it. Its Q2 label is not an independent reproduction of those exploratory statements; see reason F of [`corrections/e1-exploratory-claims-correction.md`](corrections/e1-exploratory-claims-correction.md).
- **Internal values.** The internal sets' values (E1.1, E1.1-half, E1.2-excl-R1) are in `internal-sets.json` for audit only. They are not results (D2, D10).
- **The attempt is spent.** There is no retry, and E1 is the last capacitance computation on S1 (the contract §8 stop rule).

## Pre-approval evidence (revision 8.5): REGENERATED AND FROZEN

The pre-approval evidence of contract §5 was regenerated from the corrected code on human instructions of 2026-09-24, each part under its own committed predeclaration, one run each, no retry. The files the approval binds (`code_sha256`, `preapproval_code_sha256`, the contract and the approval draft) are byte-identical to those of the reviewed implementation `88988d4`.

| evidence | directory | run from | result |
|---|---|---|---|
| Confirmation, nominal | `preapproval-confirmation-rev8.5/nominal/` | `ca19ece` | passed: 332.8 s CPU and 1.427 GiB peak address space (limits 450 s and 2 GiB); all four sets on Cholesky; K4 inequalities 1–3 PASS; stand-in outcome QUALIFIED |
| Confirmation, forced fallback | `preapproval-confirmation-rev8.5/forced/` | `ca19ece` | passed: 388.9 s CPU and 1.451 GiB; E1.2 and E1.2-excl-R1 on the last resort; K4 inequality 1 PASS, 2 and 3 NOT_EVALUATED_LAST_RESORT; QUALIFIED |
| rehearsal | `preapproval-rehearsal-rev8.5/` | `017f90e` | passed: every control (K1, K2, K2b, K3, N3, N4), every §3.3 geometry fact, N1, N2, N3b, N3c and the separation of every control set; 142.9 s CPU and 0.69 GB peak address space. The contract §5 test with the assembly spy passed: the S1 geometry phase assembled no matrix |

- The Confirmations' stand-in is synthetic (N = 9,995). Its `summary.json` carries S1's frozen C_hi, copied and not computed, and its QUALIFIED outcome includes the check C_lo^static ≤ C_hi against that copied value. The Confirmation index said otherwise; the correction is [`corrections/e1-preapproval-confirmation-rev8.5-readme-correction.md`](corrections/e1-preapproval-confirmation-rev8.5-readme-correction.md).
- The forced run's CPU margin to the 450 s limit is 13.6 %. The Confirmation measures the attempt path on the stand-in, not on S1.
- The rehearsal's output carries S1 geometry facts, C_hi (copied bit-exactly from the frozen static study) and C_br (recomputed bit-exactly by the contract §1 formula from the same frozen record), each with its bit-exactness check. Beyond geometry it computes nothing on S1: recomputing C_br is float64 arithmetic on three recorded values.
- The approval candidate binds all of this by sha256 in `APPROVAL-PACKAGE.rev8.5.json`, with a human-readable companion; a test recomputes every hash.

### The superseded evidence of `90bf9eb`

The four evidence files in the directory were produced by the code reviewed at `90bf9eb`, and each carries that code's sha256. They are superseded and kept byte-unchanged, for three reasons:

- the Confirmation's stand-in island was S1's island (finding D-1);
- proxy A is now historical selection evidence (D15);
- the code has changed three times since.

What they recorded at `90bf9eb`:

| run | result |
|---|---|
| rehearsal | Every control passed (K1, K2, K2b, K3, N3, N4). The S1 geometry phase reproduced every §3.3 count. 115.6 s CPU. |
| proxy A | g_E = 9.24e-11 at N = 4,080, on the Cholesky path. Historical (D15): not re-run. |
| Confirmation, nominal | 288.0 s CPU and 1.43 GiB peak address space, on the revision-8.2 stand-in (which contained S1's island). |
| Confirmation, forced fallback | 312.6 s CPU and 1.45 GiB. The same stand-in. |

Proxy A is not regenerated. The draft approval tells the approver to approve only a commit whose regenerated evidence carries its `code_sha256` and `preapproval_code_sha256`. The revision-8.5 evidence carries them; it was run from `ca19ece` and `017f90e`, whose bound files are byte-identical to those of `88988d4`.

## Implementation interpretations for the reviewer and the approver

The contract leaves the implementation mechanics to the frozen code (contract D8). These choices are the implementation's, not the contract's, and each one is tested.

1. **Address-space limit.**
   - `RLIMIT_AS` has a soft limit of 4 GiB, which every allocation of the attempt obeys. The hard limit is 1 GiB above it, as in the static refinement study, only so that the failure path can lift its own soft limit to write `failure.json` and the manifest.
   - `RLIMIT_CPU` is soft 900 s and hard 960 s.
   - The stop signals are unblocked, and the enforcement is read back (handlers, both limits, the wall alarm) before anything is spent. If it cannot be confirmed, the run refuses.
2. **Stop signals.** A stop signal received at any point before the attempt ends makes it FAILED, with `failure.json` and a verified manifest. The failure path marks itself stopping before any call, so a signal pending when it starts is recorded, not raised. The test (C-2) delivers each stop signal inside one C-level call chain that then raises, so no wall-clock race decides where it lands; its earlier timed version was intermittent because of its own timing (`c2-stop-signal-test-diagnosis/`).
3. **The approval** is strict JSON with an exact field set.
   - A repeated member (at any depth), a non-standard constant (NaN, Infinity), or a number that overflows float64 (such as 1e400) refuses. So does any other parser error, such as an integer beyond Python's digit limit. None of these raises past the approval check.
   - The bound fields must match with their JSON types: `true` is not `1`, and `1.0` is not `1`. The bound fields include `code_sha256` and `preapproval_code_sha256` (the stand-in and separation code).
   - The human fields are `source_commit`, `not_before_utc`, `not_after_utc`, `tolerance_scope_decision` (the §7 scope decision: `COPIED_NUMBERS_WITHIN_SCOPE` or `COPIED_NUMBERS_EXCLUDED`) and `q2_within_D5` (the Q2 decision of §1: true or false).
   - The optional `does_not_authorise` must equal the draft's list.
   - Any other field refuses.
4. **Provenance.**
   - The provenance and ledger texts are rendered and passed through the output guard before the attempt is spent. So text the guard would refuse can never spend the attempt and then cost its provenance.
   - If `provenance.json` cannot be written after spending, the failure path:
     1. writes it from memory;
     2. if that fails, puts the provenance in `failure.json` itself (`provenance_content`);
     3. if `failure.json` cannot be written either, overwrites the ledger entries with a note that carries it.
   - Only if every one of these writes fails is the provenance lost.
5. **No capacitance value in an UNQUALIFIED report.**
   - `summary.json` of an UNQUALIFIED run carries the reasons and dimensionless diagnostics only.
   - `internal-sets.json` is written only for QUALIFIED.
   - The raw files written before any enclosure (`sigma-*.json`, `pass-*.json`) are kept in every state, as contract §4.5 requires. A non-finite value is written there as a labelled string, and an exact fraction of any length in full.
6. **Anticipated numerical abnormalities are UNQUALIFIED, never FAILED.** They include:
   - a non-finite, zero or negative Ê or σᵀS₆₄σ;
   - a non-finite or negative Ŵ or Ĝ (zero is allowed, as in the contract);
   - a non-finite or negative B̃;
   - a failed no-underflow requirement;
   - Q ≤ 0, or an invalid last-resort σ;
   - a finite value outside the float64 range. RD then gives the largest float64, and recorded copies are ±inf (null in JSON).
   - a non-finite value in a control.

   K3's C_lo also applies the §4.3 B̃ and no-underflow requirements. A genuine exception remains FAILED (contract §8).
7. **The derived `c0` = 11.5649** is rigorous, not first order, with `q_B` = 31. The contract's first-order desk estimate was about 8.3. The requirement `c0 ≤ 64(1 − γ_31)` holds with a factor of about 5.5.
8. **"The tagged z = 0 triangles"** (contract §4.1) are read as every mesh triangle whose three nodes have z = 0 exactly.
9. **Host-independent generation.**
   - The island nodes, the stand-in's island nodes and K2b's 24 log-spaced F-zero separations use libm `pow`. K2's quadrature integrand uses libm `asinh`. numpy's vectorised float64 versions are not used, because their SIMD dispatch depends on the CPU.
   - The K2b pair-list sha256 is `9f47657181725147b14f3c2d05034d9bbde2d9f5e2f7419fcf9704cf38a6cb9e`.
10. **The separation rule** (contract §3.2 item 2, D15) is structural, not panel by panel. It refuses a numeric set that contains an image of an S1 attempt set, as the whole set or as an embedded subset.
    - **What counts as an image.** The maps are the eight symmetries of the square, uniform scaling s > 0 and translation. The panels may be in any order, and each panel's bounds in either order.
    - **Tolerance.** Bounds agree to within 2⁻²²·M, M being the largest coordinate magnitude of the set checked.
    - **What is proven to be found (revision 8.5).** An image within that tolerance is found whenever its scaled fitting baseline is resolvable: s·δ > 2·(2⁻²² + 2⁻⁴⁴)·M.
      - δ ≥ 0.80 mm for E1.2 and E1.2-excl-R1, 0.0835 mm for E1.1 and 0.0964 mm for E1.1-half.
      - For M of the order of 1 mm, this covers images scaled by more than about 10⁻⁵. A smaller image is not guaranteed to be found.
    - **What is refused.** A set is refused only if a fitted map gives every panel of the S1 set its own panel within (2 + 2L/δ)·(2⁻²² + 2⁻⁴⁴)·M; L/δ ≤ 1.8 for the S1 sets, and 2⁻⁴⁴·M covers rounding.
    - **The fit.** An anchor panel and a far second anchor fix the map. A perfect matching then assigns the panels one to one.
    - **Permitted.** Individual coincident panels, and proper subsets of an S1 set, are permitted. A near-copy beyond the tolerance is outside the rule (D15).
    - **When it runs.** The Confirmation and the rehearsal check every control set against S1's E1.1 and E1.1-half (from the §3.1 formula) before any control runs. That is enough for all four attempt sets, since E1.1 is a subset of E1.2 and of E1.2-excl-R1. The Confirmation checks the stand-in's four sets against the S1 geometry phase's four sets before any stand-in matrix. A coincidence, or a missing check, computes nothing further.
    - **The current sets.** On the real S1 sets (geometry only), the stand-in and every control set are separated. Proxy A and the revision-8.2 stand-in are refused.
11. **The rehearsal fails closed.** `rehearsal_pass`, and exit 0, need all of: the preflight clean, the controls passed, the §3.3 counts reproduced, and the separation held.
12. **The Confirmation fails closed.** `confirmation_pass` is true only if all of the following hold, and the mode exits 4 otherwise:
    - every measurement exists and is within its limit;
    - the budget was enforced;
    - the control sets and the stand-in were separated from the S1 sets;
    - the capacitance phase ran on the expected paths;
    - no stop signal arrived and nothing raised;
    - the evidence directory verifies.
13. **The Confirmation in the test suite** (contract §5) re-runs only with `E1_RUN_CONFIRMATION=1`, and only on a human instruction after the revision-8.5 correction has passed review.

## What is NOT established

- Anything beyond the reported static interval. E1.2-excl-R1, E1.1 and E1.1-half are internal (K4 only), and no E_C, g, deviation, suitability or correspondence statement follows from any E1 number.
- That the Q2 label independently reproduces the exploratory values that preceded E1. E1 was not blind (contract §8).
- Any use of the S1 E1.1 or E1.1-half quantities formed unintentionally before approval. They are not results (D14).
- That the Confirmation's resources on the synthetic stand-in are those of the attempt on S1: they are measured on the stand-in.
- That the separation rule excludes approximate reproductions beyond its tolerance (D15).
- That the separation check finds an image within the tolerance whose scaled fitting baseline is below 2·(2⁻²² + 2⁻⁴⁴)·M (D16).
- Anything listed in contract §10.
