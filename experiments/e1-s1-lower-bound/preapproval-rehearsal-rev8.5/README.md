# Pre-approval rehearsal, revision 8.5: evidence

**Status: RUN ONCE AS PREDECLARED; PASSED.** This is the rehearsal of contract §5, on a human instruction of 2026-09-24. It covers:

- the synthetic control phase;
- the S1 geometry phase;
- the separation of every control set from the four S1 attempt sets.

No S1 matrix was assembled or factorised, and no S1 energy or capacitance was formed. The Confirmation part of §5 is the frozen evidence in [`../preapproval-confirmation-rev8.5/`](../preapproval-confirmation-rev8.5/), and it was not re-run. E1 has not been executed, and the one attempt is unspent.

- **Predeclaration.** [`PREDECLARATION.md`](PREDECLARATION.md), [`run.sh`](run.sh) and [`check_rehearsal.py`](check_rehearsal.py) were committed at `017f90e8ab492f3d1ef31685dc6f6fc86b4bfb60` (2026-09-24T21:10:37Z), before the run. They are unchanged here.
- **Provenance.** Both parts ran from HEAD `017f90e`, with a clean tree before and after each part.
  - The files the approval binds are byte-identical to those of the reviewed implementation `88988d4`: the contract, the approval draft, and the code under `code_sha256` and `preapproval_code_sha256`.
  - The output's `code_sha256` equals the draft approval's `code_sha256` plus `preapproval_code_sha256`. Its contract and input digests equal the pins.

| part | UTC | exit | result | time |
|---|---|---|---|---|
| 1: `driver.py --rehearsal` | 21:10:46–21:13:10 | 0 | `rehearsal_pass` true; every predeclared check true ([`check-rehearsal.out.json`](part1-driver/check-rehearsal.out.json)) | 142.9 s CPU (driver-measured), 144.3 s wall, 0.69 GB peak address space |
| 2: the contract §5 rehearsal test, with the assembly spy | 21:13:10–21:15:31 | 0 | 1 passed | 140.6 s wall, 137.2 s user CPU |

- **Part 1 checks** (every one true):
  - `rehearsal_pass`, with the preflight clean and the controls, the geometry and the separation all passing;
  - `separation_problems`, the control failures and the geometry failures all empty;
  - every §3.3 geometry fact equal to `e1_geometry.EXPECTED`;
  - K2b: 10,096 pairs, the pair list matching the frozen one, and no violation of B or of the c0 bound;
  - N4's broken routine fails K2;
  - K2's largest long-double versus quad relative difference is ≤ 1e-9;
  - N1, N2, N3b and N3c pass;
  - K3's ratio to D is in [0.97, 1], and N3's ratio is > 10;
  - the bit-exactness flags of C_hi and C_br are true.

  The check script was applied to the output after the run. It exited 0 and wrote nothing to stderr.
- **Part 2.** The same rehearsal ran under a spy on the matrix assembly. The S1 geometry phase assembled no matrix. The only matrices assembled were the synthetic ones of K3 (two disks) and N3 (twice), of sizes 3,080, 732, 256 and 256.
- **Stderr** was empty in both parts. Part 1's stdout equals its output file.
- **Baseline.** The superseded `90bf9eb` rehearsal (`../rehearsal.json`, byte-unchanged) reported 115.6 s CPU and a 0.69 GB peak. The difference in CPU is not analysed.
- **What the output contains.**
  - Synthetic control results.
  - The S1 geometry facts: counts, the island's bounding box and area, and the panel counts per set. These are geometry, not capacitance.
  - The derived c0 and the probe results.
  - The input and code digests.
  - `baseline`, which is copied, not computed on S1:
    - `C_hi_fF`, read from the frozen static study's summary;
    - `C_br_fF`, derived from that summary's values by the formula of contract §1;
    - their bit-exactness flags against the pinned constants.
- **Not computed.** No S1 matrix, Cholesky factorisation, energy or capacitance. Proxy A, the configuration selection and the Confirmations were not run.

## Files

- `PREDECLARATION.md`, `run.sh`, `check_rehearsal.py`: as committed before the run.
- `part1-driver/`:
  - `rehearsal.json`: the output;
  - `stdout-driver.log` and `stderr-driver.log`;
  - `time-driver.txt`: the shell's wall and CPU times;
  - `run-driver.record`: UTC times, HEAD, `git status`, load, invocation and exit code;
  - `check-rehearsal.out.json`, `check-rehearsal.err` and `check-rehearsal.exit`: the predeclared checks.
- `part2-test/`: `stdout-test.log`, `stderr-test.log`, `time-test.txt` and `run-test.record`.
- `DONE`: the script's completion stamp.
- [`MANIFEST.sha256`](MANIFEST.sha256): the sha256 of every file in this directory except itself.

Every file under `part1-driver/` and `part2-test/`, and `DONE`, was copied byte for byte from the run's scratch directory.
