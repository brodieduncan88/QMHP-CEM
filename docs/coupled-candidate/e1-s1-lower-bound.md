# E1 — the static-capacitance lower-bound certificate for the S1 island (problem C)

**Status: IMPLEMENTED; CORRECTED AFTER THE FROZEN-CODE REVIEW (contract revision 8.3). PREPARED,
NOT APPROVED, NOT EXECUTED. PRE-APPROVAL EVIDENCE PENDING REGENERATION.**

- **E1 has not been executed.** The one attempt is unspent. Execution needs a separate human approval (`E1-APPROVAL.json`, written from `E1-APPROVAL.draft.json`).
- **What has and has not been computed on S1.** No matrix of E1.2 or E1.2-excl-R1 has been assembled on S1 geometry, and no S1 ground panel has entered any numerics. However, the Confirmation runs of the implementation reviewed at `90bf9eb`, and the revision-8 prototype, did assemble, factorise and form energies and internal lower bounds for S1's island-only internal sets E1.1 and E1.1-half. Their stand-in's island was S1's island (review finding D-1).
  - This was an **unintended pre-execution computation, not approved behaviour** (D14).
  - The runs are listed, and the statements to the contrary in `90bf9eb`'s commit message and in this page's earlier version are corrected, in [`corrections/e1-confirmation-s1-internal-sets-correction.md`](corrections/e1-confirmation-s1-internal-sets-correction.md).
  - Contract revision 8.3 forbids any pre-approval numeric set from coinciding with an S1 attempt set, and the code enforces it.
- **Contract.** `experiments/e1-s1-lower-bound/E1-CONTRACT.rev8.3.md`, sha256 `2b9b9357bb438987723914727a851161201a7a9f477aa66ae674fb0ed9d6b296`.
  - It is revision 8.2 (sha256 `24ffff7d…504c`, kept byte-unchanged beside it) plus the stand-in separation of D14.
  - The physics, the configuration, the thresholds, the Q2/C_br behaviour and the scope are unchanged.
- **What E1 would certify, and only that.** `C_static ∈ [C_lo^static, C_hi]` fF for the meshed S1 model (problem C, contract §1).
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
| `E1-CONTRACT.rev8.3.md` | the frozen contract the code implements |
| `E1-CONTRACT.rev8.2.md` | the superseded revision 8.2, byte-unchanged |
| `driver.py` | the attempt (contract §8), and the read-only modes `--rehearsal`, `--confirmation nominal\|forced`, `--proxy-a-ge` and `--show-invocation` |
| `e1_numerics.py` | the entries in x87 long double; the derived entry-error constant `c0` and `q_B`; `m(N)`; the symmetric block-pair pass; `E_up` and RD; the no-underflow requirement; the in-place trial vector with its §4.5 fallbacks; check (g); the dispatch and arithmetic probes. A non-finite or non-positive quantity fails its requirement and never raises. |
| `e1_geometry.py` | the §4.1 model checks, island, R1 cut, candidates, merge, exact containment, the §3.3 counts, and N1, N2, N3b and N3c. It assembles no matrix. |
| `e1_controls.py` | K1, K2, K2b (with the frozen pair-list sha256), K3, N3 and N4. A non-finite value fails the control and never raises. |
| `e1_standin.py` | the SYNTHETIC stand-in of contract §6 (revision 8.3 island), proxy A of §3.2 item 5, and the §3.2 item 2 separation check. The attempt never loads it and refuses if it is loaded. |
| `E1-APPROVAL.draft.json` | the approval a human would grant, with the human's fields as placeholders; it authorises nothing |
| `rehearsal.json`, `proxyA-gE.json`, `confirmation-nominal.json`, `confirmation-forced.json` | the pre-approval evidence of `90bf9eb`: SUPERSEDED, kept byte-unchanged (see below) |

The attempt would be run once, from the repository root, exactly as contract §6 states:

    env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 1260 .venv/bin/python experiments/e1-s1-lower-bound/driver.py

## Pre-approval evidence: PENDING REGENERATION

The four evidence files in the directory were produced by the code reviewed at `90bf9eb`, and each carries that code's sha256. They are superseded and kept byte-unchanged, for two reasons:

- the Confirmation's stand-in island was S1's island (finding D-1);
- the code has since changed.

What they recorded at `90bf9eb`:

| run | result |
|---|---|
| rehearsal | Every control passed (K1, K2, K2b, K3, N3, N4). The S1 geometry phase reproduced every §3.3 count. 115.6 s CPU. |
| proxy A | g_E = 9.24e-11 at N = 4,080, on the Cholesky path. |
| Confirmation, nominal | 288.0 s CPU and 1.43 GiB peak address space, on the revision-8.2 stand-in (which contained S1's island). |
| Confirmation, forced fallback | 312.6 s CPU and 1.45 GiB. The same stand-in. |

The evidence is regenerated from the corrected code only after the corrected stand-in separation has passed review, and only on a human instruction. Until then:

- no Confirmation margin is claimed for the corrected code;
- the draft approval tells the approver to approve only a commit whose evidence carries its code_sha256.

## Implementation interpretations for the reviewer and the approver

The contract leaves the implementation mechanics to the frozen code (contract D8). These choices are the implementation's, not the contract's, and each one is tested.

1. **Address-space limit.**
   - `RLIMIT_AS` has a soft limit of 4 GiB, which every allocation of the attempt obeys. The hard limit is 1 GiB above it, as in the static refinement study, only so that the failure path can lift its own soft limit to write `failure.json` and the manifest.
   - `RLIMIT_CPU` is soft 900 s and hard 960 s.
   - The stop signals are unblocked, and the enforcement is read back (handlers, both limits, the wall alarm) before anything is spent. If it cannot be confirmed, the run refuses.
2. **Stop signals.** A stop signal received at any point before the attempt ends makes it FAILED, with `failure.json` and a verified manifest. The failure path marks itself stopping before any call, so a signal pending when it starts is recorded, not raised.
3. **The approval** has an exact field set.
   - The bound fields must match.
   - The human fields are `source_commit`, `not_before_utc`, `not_after_utc`, `tolerance_scope_decision` (the §7 scope decision: `COPIED_NUMBERS_WITHIN_SCOPE` or `COPIED_NUMBERS_EXCLUDED`) and `q2_within_D5` (the Q2 decision of §1: true or false).
   - The optional `does_not_authorise` must equal the draft's list.
   - Any other field refuses.
   - The provenance and ledger texts are rendered and passed through the output guard before the attempt is spent. An accepted approval therefore cannot spend the attempt and then lose its provenance.
   - If `provenance.json` is still missing after spending, the failure path writes it from memory, or keeps it in the ledger note.
4. **No capacitance value in an UNQUALIFIED report.**
   - `summary.json` of an UNQUALIFIED run carries the reasons and dimensionless diagnostics only.
   - `internal-sets.json` is written only for QUALIFIED.
   - The raw files written before any enclosure (`sigma-*.json`, `pass-*.json`) are kept in every state, as contract §4.5 requires. A non-finite value is written there as a labelled string.
5. **Anticipated numerical abnormalities are UNQUALIFIED, never FAILED.** They include a non-finite, zero or negative Ê, Ŵ, Ĝ or σᵀS₆₄σ, a non-finite or negative B̃, a failed no-underflow requirement, Q ≤ 0, an invalid last-resort σ, and a non-finite value in a control.
   - K3's C_lo also applies the §4.3 B̃ and no-underflow requirements.
   - A genuine exception remains FAILED (contract §8).
6. **The derived `c0` = 11.5649** is rigorous, not first order, with `q_B` = 31. The contract's first-order desk estimate was about 8.3. The requirement `c0 ≤ 64(1 − γ_31)` holds with a factor of about 5.5.
7. **"The tagged z = 0 triangles"** (contract §4.1) are read as every mesh triangle whose three nodes have z = 0 exactly.
8. **Host-independent generation.**
   - The island nodes, the stand-in's island nodes and K2b's 24 log-spaced F-zero separations use libm `pow`. K2's quadrature integrand uses libm `asinh`. numpy's vectorised float64 versions are not used, because their SIMD dispatch depends on the CPU.
   - The K2b pair-list sha256 is `9f47657181725147b14f3c2d05034d9bbde2d9f5e2f7419fcf9704cf38a6cb9e`.
9. **The separation rule** (contract §3.2 item 2) compares every numeric set of the Confirmation, the rehearsal and proxy A with the four S1 attempt sets. The comparison is byte for byte, and up to translation, axis reflection, exchange of x and y, and uniform scaling.
   - Sorted aspect ratios decide non-similarity first; otherwise eight canonical forms are compared.
   - Proxy A's full 4,080-panel set contains a translated copy of the selected island, as the frozen selection rule defines it. Only the full set is solved.
10. **The Confirmation fails closed.** `confirmation_pass` is true only if all of the following hold, and the mode exits 4 otherwise:
    - every measurement exists and is within its limit;
    - the budget was enforced;
    - the stand-in was separated from the S1 sets;
    - the capacitance phase ran on the expected paths;
    - no stop signal arrived and nothing raised;
    - the evidence directory verifies.
11. **The Confirmation in the test suite** (contract §5) re-runs only with `E1_RUN_CONFIRMATION=1`. It is not to be run before the corrected separation has passed review.

## What is NOT established

- Any S1 E1.2 or E1.2-excl-R1 quantity: E1 has not been executed.
- Any use of the S1 E1.1 or E1.1-half quantities formed unintentionally by the `90bf9eb` Confirmation. They are not results (D14).
- The corrected code's Confirmation resources: the evidence is pending regeneration.
- Anything listed in contract §10.
