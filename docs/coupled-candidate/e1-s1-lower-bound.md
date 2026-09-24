# E1 — the static-capacitance lower-bound certificate for the S1 island (problem C)

**Status: IMPLEMENTED AND REHEARSED. PREPARED, NOT APPROVED, NOT EXECUTED.** No S1
capacitance has been computed by E1: no S1 Galerkin matrix has been assembled or factorised,
and no S1 energy has been formed. The one attempt is unspent. Execution needs a separate human
approval (`E1-APPROVAL.json`, from `E1-APPROVAL.draft.json`).

- **Contract.** `experiments/e1-s1-lower-bound/E1-CONTRACT.rev8.2.md`, revision 8.2, frozen
  before any of this code, sha256 `24ffff7d92c93757a13f9f6ba4505598be83b1628f4c5d6912c6abbbbdaf504c`.
  The code implements it and does not restate it. Nothing in it was changed by the
  implementation.
- **What E1 would certify, and only that.** `C_static ∈ [C_lo^static, C_hi]` fF for the meshed S1
  model (problem C, contract §1), with `C_lo^static` a certified Thomson/Galerkin lower bound under
  the libm ASSUMPTION of contract §4.4 and `C_hi` = 67.9755386760262 fF copied bit-exactly from the
  frozen static study. In every state: `E_C,F1F1` is `EC_NOT_EVALUATED_BY_E1`, correspondence to
  the registered operator NOT_ESTABLISHED, deviation NOT_EVALUATED, suitability
  SUITABILITY_NOT_ASSESSED. No E1 output contains a quantity in frequency units. E1.1,
  E1.1-half and E1.2-excl-R1 are internal (K4 only). `E_C` and `g` stay UNAVAILABLE.

## Files (`experiments/e1-s1-lower-bound/`)

| file | content |
|---|---|
| `E1-CONTRACT.rev8.2.md` | the frozen contract, byte-identical to the reviewed revision 8.2 |
| `driver.py` | the attempt (contract §8), and the read-only modes `--rehearsal`, `--confirmation nominal|forced`, `--proxy-a-ge`, `--show-invocation` |
| `e1_numerics.py` | entries in x87 long double, the derived entry-error constant `c0` and `q_B`, `m(N)`, the symmetric block-pair pass, `E_up`, RD, the no-underflow requirement, the trial vector with its §4.5 fallbacks (in place), check (g), the dispatch and arithmetic probes |
| `e1_geometry.py` | the §4.1 model checks, island, R1 cut, candidates, merge, exact containment, the §3.3 counts, N1, N2, N3b, N3c; assembles no matrix |
| `e1_controls.py` | K1, K2, K2b (frozen pair-list sha256), K3, N3, N4 |
| `e1_standin.py` | the SYNTHETIC stand-in of contract §6 and proxy A of §3.2 item 5; never loaded by the attempt (the attempt refuses if it is) |
| `E1-APPROVAL.draft.json` | the approval a human would grant, with the human's fields as placeholders; authorises nothing |
| `rehearsal.json`, `proxyA-gE.json`, `confirmation-nominal.json`, `confirmation-forced.json` | the pre-approval evidence below, each carrying the sha256 of the code that produced it |

The attempt would be run once, from the repository root, exactly as contract §6:

    env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 1260 .venv/bin/python experiments/e1-s1-lower-bound/driver.py

## Pre-approval evidence (S1 geometry and synthetic sets only)

Produced on this host (python 3.11.15, numpy 2.4.6, scipy 1.17.1, glibc 2.39, single-threaded
BLAS, under the declared budget where stated) by the committed code; each file carries the code's
sha256 and the tests check it against the files. No approval, no ledger entry and no S1 capacitance
were involved.

| run | result |
|---|---|
| rehearsal: synthetic controls (contract §5) | all pass. K1: 7.7e-20 (long double), 2.1e-16 (float64). K2: long double vs quadrature ≤ 7.0e-12, float64 vs long double ≤ 1.5e-8, 0 IntegrationWarnings. N4: the broken routine fails K2 on 12 pairs. K2b: 10,096 pairs, pair list sha256 frozen, 0 violations of B̃ and 0 of the derived-`c0` bound, largest implied constant 0.297 (against `c0` = 11.56 and c = 64). K3: ratio 0.97711, nested. N3: free-space Galerkin value 45.5 × the exact ε₀a/10. |
| rehearsal: S1 geometry phase | every §4.1 model check passes; island, R1 cut, candidates, merge, exact containment and every §3.3 count reproduced (N = 9,995 / 6,710 / 1,024 / 256); N1, N2, N3b, N3c pass. No matrix assembled. 115.6 s CPU for the whole rehearsal. |
| proxy A, selected configuration (§3.2 items 4–5) | N = 4,080, Cholesky without fallback (squared pivot ratio 8.7e-5), g_E = 9.24e-11 ≤ 1e-9; enclosure width 3.9e-8 of C̃ at c = 64 |
| Confirmation, nominal (§3.2 item 2) | 288.0 s CPU (limit 450 s), 1.43 GiB peak address space (limit 2 GiB). Every set on Cholesky; K4 PASS × 3; every raw file written and the evidence directory sealed by `write_verified`. |
| Confirmation, every factorisation fallback forced for E1.2 and E1.2-excl-R1 | 312.6 s CPU, 1.45 GiB peak. Both sets reach the last-resort σ; K4 inequalities 2 and 3 are `NOT_EVALUATED_LAST_RESORT`, inequality 1 PASS; the bound stays valid (every enclosure finite and positive). |

The two Confirmation runs are ≤ 450 s CPU, so the contract's condition for claiming a CPU
margin of at least 2× against the 900 s cap is met on this host (3.1× nominal, 2.9× forced);
the memory margin against 4 GiB is 2.8× (2.75× forced). The Confirmations ran on the SYNTHETIC stand-in of
contract §6 (N = 9,995, N_x = 6,710), whose size-class mix differs from S1's as the contract
discloses; they include the S1 geometry phase and every control, and discard the S1 panel sets
before the capacitance phase.

## Implementation interpretations for the reviewer and the approver

The contract leaves the implementation mechanics to the frozen code (contract D8). These
choices are the implementation's, not the contract's, and each is tested:

1. **Address-space limit.** `RLIMIT_AS` soft limit 4 GiB, which every allocation of the attempt
   obeys; the hard limit is 1 GiB above it, as in the static refinement study, only so that the
   failure path can lift its own soft limit to write `failure.json` and the manifest after the
   attempt has ended. `RLIMIT_CPU` is soft 900 s, hard 960 s, as declared.
2. **The Q2 decision at approval** (contract §1) is the approval field `q2_within_D5` (true or false;
   anything else refuses). False, or a non-QUALIFIED outcome, reports no Q2 label.
3. **The §7 scope decision** is the approval field `tolerance_scope_decision`, one of
   `COPIED_NUMBERS_WITHIN_SCOPE` or `COPIED_NUMBERS_EXCLUDED`; without it the run refuses.
4. **No capacitance value in an UNQUALIFIED report.** `summary.json` of an UNQUALIFIED run carries
   the reasons and dimensionless diagnostics only; `internal-sets.json` (the K4 inputs) is written
   only for QUALIFIED. The raw files written before any enclosure (`sigma-*.json`: σ, `Q` as p/q,
   σᵀS₆₄σ; `pass-*.json`: Ê, Ŵ, Ĝ as exact p/q strings) are kept in every state, as contract
   §4.5 requires σ to be recorded before any enclosure. They are raw evidence, not a report.
5. **The derived `c0` = 11.5649** (rigorous, not first order; `q_B` = 31), against the contract's
   first-order desk estimate of about 8.3. The requirement `c0 ≤ 64(1 − γ_31)` holds with a
   factor of about 5.5. The derivation is in `e1_numerics.derive_c0` and its rational angular
   constants are checked by dense sampling in the tests; K2b tests it against a 60-digit reference.
6. **"The tagged z = 0 triangles"** (contract §4.1) are read as every mesh triangle whose three
   nodes have z = 0 exactly; they must be distinct tetrahedral faces.
7. **Host-independent generation.** The island nodes and K2b's 24 log-spaced F-zero separations
   use libm `pow` (`math.pow`), and K2's quadrature integrand uses libm `asinh`, rather than
   numpy's vectorised float64 `power`, `log10` and `arcsinh`, whose SIMD dispatch depends on the
   CPU (this host has AVX512). On this host the island nodes agree with the vectorised form for
   every node (tested); the F-zero separations differ from `np.geomspace` by at most 3.5e-16
   relative. The K2b pair-list sha256 is frozen from the libm form:
   `9f47657181725147b14f3c2d05034d9bbde2d9f5e2f7419fcf9704cf38a6cb9e`.
8. **The rehearsal in the test suite** (contract §5). The synthetic controls and the S1 geometry
   phase run in the suite (`@pytest.mark.slow`, about two minutes). The two Confirmation runs
   (about five minutes each) re-run in the suite only with `E1_RUN_CONFIRMATION=1`; by default
   the suite checks that the committed Confirmation evidence was produced by the committed code
   and meets the limits.
9. **The output guard** checks every evidence file for frequency units and for an `E_C` field
   other than the constant, and the summary for a capacitance value in a state that reports none.

## What is NOT established

- Any S1 capacitance, bound or energy: E1 has not been executed.
- That the frozen implementation's Confirmation margins hold on another host or under other
  load; the figures above are this host's.
- Anything listed in contract §10.
