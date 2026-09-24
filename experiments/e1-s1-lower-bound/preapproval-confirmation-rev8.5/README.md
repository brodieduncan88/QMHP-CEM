# Pre-approval Confirmation evidence, revision 8.5 (regenerated 2026-09-24)

**Status: BOTH CONFIRMATIONS PASS** (contract `E1-CONTRACT.rev8.5.md` §3.2 item 2).

- **How they ran.** Each was run once, as predeclared at `ca19ece` ([`PREDECLARATION.md`](PREDECLARATION.md)), on a human instruction of 2026-09-24.
  - They ran from HEAD `ca19ece`, whose code is byte-identical to the implementation frozen at `88988d4`.
  - They used the separated synthetic stand-in.
- **What they replace.** For the corrected code, they supersede the `90bf9eb` Confirmations (`../confirmation-nominal.json`, `../confirmation-forced.json`), which stay byte-unchanged.
- **What was not run.** E1 is not executed, and nothing was run on S1 beyond its geometry.

| mode | UTC | exit | `confirmation_pass` | CPU | peak address space | path E1.2 / E1.2-excl-R1 | K4 | stand-in outcome |
|---|---|---|---|---|---|---|---|---|
| nominal | 19:36:23–19:42:01 | 0 | true | 332.8 s | 1,532,198,912 B (1.427 GiB) | cholesky / cholesky | 1, 2, 3 PASS | QUALIFIED |
| forced fallback | 19:42:01–19:48:34 | 0 | true | 388.9 s | 1,557,753,856 B (1.451 GiB) | last_resort / last_resort | 1 PASS; 2, 3 NOT_EVALUATED_LAST_RESORT | QUALIFIED |

Limits: CPU ≤ 450 s and peak ≤ 2 GiB, both runs. Both are met.

- **Checks (all true in both runs):**
  - `cpu_within_limit`, `peak_within_limit`, `budget_enforced`;
  - `separated_from_s1`, `capacitance_phase_ran_on_expected_paths`;
  - `no_stop_signal`, `no_error`, `evidence_directory_verifies`, `preflight_clean_on_this_host`.

  Stderr is empty in both runs, and the tree was clean before and after each.
- **Controls.** K1, K2, K2b, K3, N3 and N4 all pass (`evidence-dir/controls.json`, failures `[]`).
- **Separation.**
  - The control sets against S1's E1.1 and E1.1-half: `[]`.
  - The stand-in's four sets against the S1 geometry phase's four sets: `[]`.
  - Each check ran before any numerics on the sets concerned.
- **The stand-in.**
  - N = 9,995, N_x = 6,710, n_island = 1,024, drawn from a sheet of 58,116 panels.
  - The frozen generator is `e1_standin.py`, sha256 `ad3643836bcd6d9e3eed98ab7c7a4f2e320dd1a2c04093e66e3cde564b9c0d77`.
  - Its island is synthetic. Its ground shares 534 individual panels with S1's E1.2 (476 of them in E1.2-excl-R1), which D15 permits. No S1 attempt set, and no image of one, was assembled, factorised or used in an energy.
- **Terminal states.**
  - The outcome on the stand-in is QUALIFIED.
  - `summary.json` names its subject "SYNTHETIC STAND-IN of the Confirmation (contract section 3.2 item 2): NOT S1".
  - The fixed statements are: E_C_F1F1 `EC_NOT_EVALUATED_BY_E1`; correspondence `NOT_ESTABLISHED`; deviation `NOT_EVALUATED`; suitability `SUITABILITY_NOT_ASSESSED`.
  - The Q2 label is `Q2_DROPPED_AT_APPROVAL`, because a Confirmation has no approval.
  - There is no frequency unit.
  - The numbers in `summary.json` and `internal-sets.json` are the synthetic stand-in's, not S1 values.
- **The forced run.**
  - The last resort is σ = D⁻¹·1 on the island and zero on the ground. So E1.2 and E1.2-excl-R1 have the same trial vector and identical diagnostics, by construction.
  - K4 inequalities 2 and 3 are `NOT_EVALUATED_LAST_RESORT`, as the contract requires.
- **Dimensionless diagnostics** (synthetic stand-in; the ratio check (g) must stay ≤ 1e-7):

  | set | check (g), nominal | check (g), forced |
  |---|---|---|
  | E1.2 | 1.43e-9 | 1.74e-9 |
  | E1.2-excl-R1 | 1.39e-9 | 1.74e-9 |
  | E1.1 | 1.00e-9 | 1.00e-9 |
  | E1.1-half | 5.0e-12 | 5.0e-12 |

  The g_E ≤ 1e-9 condition of §3.2 item 4 applies to proxy A in the configuration selection, not to the Confirmation.
- **Provenance.**
  - Both runs: HEAD `ca19ece`, a clean tree, and the invocation predeclared.
  - Each output's `code_sha256` equals the draft approval's `code_sha256` and `preapproval_code_sha256`, and its `contract_sha256` equals the frozen pin.
  - Each `evidence-dir` is the driver's sealed evidence directory, copied byte for byte from `/tmp/qmhp-e1-confirmation-fcmqvgg0` (nominal) and `/tmp/qmhp-e1-confirmation-cucsev_g` (forced). Each verifies against its own `manifest.sha256`.
  - [`MANIFEST.sha256`](MANIFEST.sha256) covers every file in this directory.
- **Files.**
  - Per mode:
    - `<mode>/confirmation-<mode>.json`: the driver's output;
    - `stdout-<mode>.log`: identical to that output;
    - `stderr-<mode>.log`: empty;
    - `run-<mode>.record`: times, HEAD, git status, load, invocation and exit code;
    - `evidence-dir/`.
  - `run.sh`: the script that ran both.
- **Not run.**
  - The rehearsal. The draft approval's rule also asks for it from the approved code, but it was not instructed here.
  - Proxy A, the configuration selection, Palace, Route A and E1.
