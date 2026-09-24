# E1 execution-approval package, revision 8.5 (approval candidate)

**APPROVAL CANDIDATE, NOT AN APPROVAL.** It authorises nothing, and the driver never reads it. E1 is PREPARED, NOT APPROVED, NOT EXECUTED, and the one attempt is unspent.

- **What it is.** The human-readable companion of [`APPROVAL-PACKAGE.rev8.5.json`](APPROVAL-PACKAGE.rev8.5.json). The JSON binds every file below by sha256, and binds this file too.
- **How the binding is checked.** The test `test_the_approval_package_binds_every_file_it_names_and_the_driver_pins` recomputes every hash on each commit.
- **The commit to approve.** The commit that adds this file is the approval candidate. Its SHA cannot be written inside it, so it is reported to the approver with this package. That SHA is the `source_commit` to approve, and it must be HEAD at execution.

## 1. Contract

`experiments/e1-s1-lower-bound/E1-CONTRACT.rev8.5.md`, sha256 `2db93be49ee455f1da952acbe300f370d7614a8986c4151a9563adf805f00150`.

## 2. Implementation

| file | sha256 |
|---|---|
| `driver.py` | `75121e5f199bce4344e2dc84d4c6fc2d966659ae72233807d6439ef1f133d807` |
| `e1_numerics.py` | `d3094dac0c5a0907a6fadd66986f37afd9e5d306d5c3d6f09f879e9551e4ab8d` |
| `e1_geometry.py` | `226153c5351d101c9b2565dcbc3252781f4c0a2ebc658b9942ce86ff0fe639d3` |
| `e1_controls.py` | `7fa268c1eefa7e3d738c2c3104649be263d5044fb1fdf1524bf5bafe825d3e8f` |
| `anchor_fem.py` | `1123e38f16b6c443fd397330db568e8c5d4e18fa9a7c4dc844c599204e6437c1` |
| `orchestrator/manifest.py` | `66a68dd40b8b2644efa8d204e723f27fe0a8e2127d038853e28271b8280d463f` |
| `e1_standin.py` (`preapproval_code_sha256`) | `ad3643836bcd6d9e3eed98ab7c7a4f2e320dd1a2c04093e66e3cde564b9c0d77` |
| `E1-APPROVAL.draft.json` | `75bfb5814cdc691d5b5890c42231f5b79f55b3fc9c0137814a7b5a9d8752ce2e` |

- **Unchanged since review.** Every file in this table, and the contract, is byte-identical to the reviewed implementation `88988d43a49b290e7c7537c41033aec3d61af672`.
- **What changed after `88988d4`.** Only records, documents and tests:
  - the Confirmation and rehearsal evidence;
  - the correction record;
  - the C-2 diagnosis;
  - the E1 page and README;
  - `tests/test_e1_s1_lower_bound.py`;
  - this package.

## 3. S1 inputs

| input | path | sha256 |
|---|---|---|
| mesh | `results/COUPLED-LADDER-O1-L2-N2R-20260918T061455Z/L2/solver/coupled_chip_cell_L2.msh` | `d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428` |
| baseline manifest | `results/STATIC-REFINEMENT-STUDY-20260923T062048Z/manifest.sha256` | `e3e447068dea6b4c2790c29de7a34be77f971717fa6e40964f6e31fdee193622` |
| baseline summary | `results/STATIC-REFINEMENT-STUDY-20260923T062048Z/summary.json` | `7eca21f3688a662f0324003093de2902cfbd67503fa0de71f5c028df13181298` |

The driver also requires C_hi and C_br to be bit-exact against its pinned constants, and the baseline record to verify against its own manifest.

## 4. Environment, invocation and budget

- **Environment.** Python 3.11.15, numpy 2.4.6, scipy 1.17.1, glibc 2.39, long double with a 63-bit mantissa; `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS` and `MKL_NUM_THREADS` = 1. These were measured equal on this host.
- **Invocation**, from the repository root `/home/user/QMHP-CEM`:

  `env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 1260 .venv/bin/python experiments/e1-s1-lower-bound/driver.py`
- **Budget.**
  - CPU: soft 900 s, hard 960 s.
  - Address space: 4 GiB, plus 1 GiB hard headroom.
  - Wall clock: alarm at 1,200 s, outer SIGKILL at 1,260 s.
  - One attempt, no retry.

## 5. Pre-approval evidence

| evidence | directory (`experiments/e1-s1-lower-bound/`) | run from | `MANIFEST.sha256` | result |
|---|---|---|---|---|
| Confirmation, nominal and forced fallback | `preapproval-confirmation-rev8.5/` | `ca19ece` | `8761f952eca2ea305659737a27aae16c87a1584135a4e8989383dfcfb50c16b8` | both passed |
| rehearsal (contract §5) | `preapproval-rehearsal-rev8.5/` | `017f90e` | `f3f7db902cd8315b54a082ff234607e238bb99668b6c78328cb9203675631161` | passed |
| C-2 test diagnosis | `c2-stop-signal-test-diagnosis/` | `b0fec36` (pre-fix) | `70da8bcdc103df90f257f8fb3326ba9dbddc395e6cc21c4fcfe088ba37ce8f0c` | test timing, not the implementation |

- **The Confirmations.**
  - Nominal: 332.8 s CPU and 1.427 GiB peak (limits 450 s and 2 GiB); all four sets on Cholesky; K4 inequalities 1–3 PASS.
  - Forced fallback: 388.9 s CPU and 1.451 GiB; E1.2 and E1.2-excl-R1 on the last resort; K4 inequality 1 PASS, 2 and 3 NOT_EVALUATED_LAST_RESORT.
  - Both: every check true, and the separation problems empty.
  - The stand-in's `summary.json` carries S1's copied C_hi. The correction for the index sentence that said otherwise is `docs/coupled-candidate/corrections/e1-preapproval-confirmation-rev8.5-readme-correction.md`.
- **The rehearsal.**
  - Every predeclared check is true: the controls, every §3.3 geometry fact, N1, N2, N3b, N3c and the separation. It took 142.9 s CPU with a 0.69 GB peak.
  - The contract §5 test with the assembly spy passed: no S1 matrix was assembled.
  - Output sha256 `4f6b56ed8b58693837811e54effdcb78ba7936f01c0b13ec90e0358064628170`.
- **The C-2 test.** It was made deterministic. On the pre-fix code, no lost signal was found in 90 instrumented runs, and the replacement passed 25 of 25 repetitions.
- **Superseded, byte-unchanged.** The `90bf9eb` evidence files `rehearsal.json`, `proxyA-gE.json`, `confirmation-nominal.json` and `confirmation-forced.json`.
- **Evidence and code identity.** The Confirmation and rehearsal evidence were produced from `ca19ece` and `017f90e`, not from the approval candidate. At all three commits, every file in §2 is byte-identical. An approval cannot come from the same commit as evidence committed in it. The draft approval's rule says "produced from this commit after its review". Whether byte-identical code at an ancestor commit satisfies that rule is the approver's decision.

## 6. The attempt: UNSPENT

- **Checked at the parent of the approval candidate.** `driver.spent_state()` is empty, and `.git/qmhp-attempts/E1-S1-LOWER-BOUND.json` does not exist.
- **Also absent:** `E1-APPROVAL.json`, `E1-APPROVAL.consumed.json`, `ATTEMPT-SPENT.json` and any `results/E1-S1-LOWER-BOUND-*`.
- **Spending the attempt.** Running E1 spends the one attempt before any control runs. There is no retry, whatever the outcome.

## 7. Approval scope (from the draft, unchanged)

- **Authorises:** one execution of E1, the static-capacitance lower-bound certificate for the S1 island (problem C). It is attempt 1; there are no prior records. The tolerance set is T0 and γ = 1e-6.
- **Does not authorise:**
  - a second attempt, whatever the first one's outcome;
  - running from another checkout, another commit or outside the validity window;
  - removing or editing `ATTEMPT-SPENT.json`, the git-common-directory ledger entry, `E1-APPROVAL.consumed.json` or the record;
  - any further capacitance computation on S1 after E1 (the contract §8 stop rule);
  - any E_C, g, deviation or suitability statement, or any statement in frequency units, from any E1 number;
  - any tolerance T1–T4 not adopted by a recorded human decision before this approval;
  - any Palace solve, Route A inversion, workflow dispatch or physical extraction.

## 8. Fields the approver fills in `E1-APPROVAL.json`

It is written from `E1-APPROVAL.draft.json`: every field except `DRAFT` and `how_to_grant_it`.

- `source_commit`: the full SHA of the approval candidate, which must be HEAD at execution.
- `not_before_utc` and `not_after_utc`: ISO-8601 UTC, at most 7 days apart.
- `tolerance_scope_decision`: `COPIED_NUMBERS_WITHIN_SCOPE` or `COPIED_NUMBERS_EXCLUDED` (contract §7).
- `q2_within_D5`: `true` (Q2 stays) or `false` (Q2 is dropped before execution).

The driver refuses, spending nothing, if any digest, the environment, the invocation, the budget, the checkout path, HEAD or the time differs.

## 9. What is NOT established

- **Any S1 E1.2 or E1.2-excl-R1 quantity.** E1 has not been executed.
- **What the stand-in's resources say about S1's.** The Confirmation's resources were measured on the synthetic stand-in, not on S1.
- **Any E_C, g or suitability statement.** `E_C` and `g` stay UNAVAILABLE.
