# Pre-approval rehearsal, revision 8.5: predeclaration

**Status: PREDECLARED, NOT RUN** when this file was committed. Human instruction of 2026-09-24: "Regenerate the required rehearsal from the current corrected implementation, under its own predeclaration. It may run synthetic controls and the S1 geometry-only phase, but must not assemble an S1 matrix, perform S1 Cholesky, energy or capacitance calculations, or execute E1."

- **Question.** Does the frozen implementation pass the rehearsal of contract §5? That is:
  - the synthetic control phase (K1, K2, K2b, K3, N3, N4) with the frozen inputs and seed;
  - the S1 geometry phase on the pinned mesh, reproducing §3.3 (model checks, island, R1 cut, candidates, merge, containment, counts, N1, N2, N3b, N3c);
  - the §3.2 item 2 separation of every control set from the four S1 attempt sets, checked before any numerics on it;
  - all of this with no matrix assembled on S1.

  The Confirmation part of §5 is already done: the frozen evidence in `../preapproval-confirmation-rev8.5/`. It is not re-run.
- **Why now.** The approval draft's rule requires the rehearsal to come from the reviewed implementation. The only committed rehearsal, `../rehearsal.json`, is from `90bf9eb`, under contract 8.2. Five of its code digests and its contract digest differ from the current ones.
- **Baseline.** `../rehearsal.json` (`90bf9eb`, sha256 `3b6e31b198ae81b0d8a6a6ab24116457fb04c9d195f3fd373451f9856d45c2b8`).
  - It reported controls and geometry passing, 115.6 s CPU and a 0.69 GB peak address space.
  - It is superseded, kept byte-unchanged and not overwritten.
- **Exact configuration.**
  - Contract: `E1-CONTRACT.rev8.5.md`, sha256 `2db93be49ee455f1da952acbe300f370d7614a8986c4151a9563adf805f00150`.
  - Code: byte-identical to the implementation frozen at `88988d4`. The runs execute from HEAD, the commit of this file. The previous commit, `510915b`, changed only a test and added a diagnosis record. sha256 of each file:
    - `driver.py` `75121e5f199bce4344e2dc84d4c6fc2d966659ae72233807d6439ef1f133d807`;
    - `e1_numerics.py` `d3094dac0c5a0907a6fadd66986f37afd9e5d306d5c3d6f09f879e9551e4ab8d`;
    - `e1_geometry.py` `226153c5351d101c9b2565dcbc3252781f4c0a2ebc658b9942ce86ff0fe639d3`;
    - `e1_controls.py` `7fa268c1eefa7e3d738c2c3104649be263d5044fb1fdf1524bf5bafe825d3e8f`;
    - `anchor_fem.py` `1123e38f16b6c443fd397330db568e8c5d4e18fa9a7c4dc844c599204e6437c1`;
    - `orchestrator/manifest.py` `66a68dd40b8b2644efa8d204e723f27fe0a8e2127d038853e28271b8280d463f`;
    - `e1_standin.py` (pre-approval) `ad3643836bcd6d9e3eed98ab7c7a4f2e320dd1a2c04093e66e3cde564b9c0d77`.
  - Inputs (measured at `510915b` before this commit; equal to the pins):
    - mesh `d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428`;
    - baseline manifest `e3e447068dea6b4c2790c29de7a34be77f971717fa6e40964f6e31fdee193622`;
    - baseline summary `7eca21f3688a662f0324003093de2902cfbd67503fa0de71f5c028df13181298`.
  - Environment (measured):
    - Python 3.11.15, numpy 2.4.6, scipy 1.17.1, glibc 2.39, long double with a 63-bit mantissa;
    - BLAS/OpenMP threads 1; 4 CPUs;
    - the driver's preflight is clean; the attempt is unspent.
- **Independent variable.** None within this run: one configuration. The comparison is with the superseded `90bf9eb` rehearsal (code version).
- **Controlled variables.** The frozen code, inputs, controls and seed; the environment and thread counts; one part at a time on a quiet host.
- **Invocation.** [`run.sh`](run.sh), committed with this file, runs from the repository root:
  - **Part 1.** `env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 1260 .venv/bin/python experiments/e1-s1-lower-bound/driver.py --rehearsal --out <scratch>/rehearsal.json`
  - **Part 2.** The contract §5 rehearsal test, `test_the_rehearsal_runs_the_real_controls_and_the_S1_geometry_phase_and_assembles_nothing_on_S1`, run alone under pytest with the same thread settings and a 1,260 s kill. A spy on the matrix assembly fails the test if the S1 geometry phase assembles any matrix. It requires the only assembled matrices to be the synthetic ones of K3 and N3.
  - Stdout, stderr, the shell's wall and CPU times, and a run record are captured for each part.
- **Acceptance, part 1.**
  - Exit code 0 and `rehearsal_pass` true. That needs `preflight_clean`, `controls_pass`, `geometry_pass` and `separation_pass` all true.
  - `separation_problems`, the control failures and the geometry failures are all empty.
  - The output's `code_sha256` equals the draft approval's `code_sha256` plus `preapproval_code_sha256`.
  - Its `contract_sha256` and `inputs` equal the pins.
  - Every §3.3 geometry fact equals `e1_geometry.EXPECTED`.
  - The controls:
    - K2b has 10,096 pairs, its pair list matches the frozen one, and it has no violation of B or of the c0 bound;
    - N4's broken routine fails K2;
    - K2's largest long-double versus quad relative difference is ≤ 1e-9;
    - N1, N2, N3b and N3c pass;
    - K3's ratio to D is in [0.97, 1], and N3's ratio is > 10.

  These checks are made on the output file after the run, by [`check_rehearsal.py`](check_rehearsal.py), committed with this file. Before the run it was checked on a hand-built output: it passes a passing one and fails each of 12 single-field failures (rehearsal_pass, a separation problem, two geometry facts, K2b, N3c, the driver and stand-in digests, the mesh digest, K3, a bit-exactness flag and a preflight problem).
- **Acceptance, part 2.** Exit code 0 and the one test passed.
- **Failure.** Any criterion not met, a non-zero exit, a kill or a timeout fails the rehearsal. There is no retry: preserve the evidence and stop.
- **Budget and attempts.**
  - Wall clock: 1,260 s per part (SIGKILL).
  - No CPU criterion; CPU time and peak address space are reported.
  - Attempts: exactly one run of each part, no retry. Order: part 1, then part 2, which runs only if part 1 exits 0.
- **Expected evidence.** `rehearsal.json`; stdout and stderr per part; the time files; the two run records; the check script and its output; an index README; and a `MANIFEST.sha256` over every file.
  - These are copied into this directory and committed. `run.sh`, `check_rehearsal.py` and this file stay as committed now.
  - Besides the synthetic control values and S1 geometry facts, the output carries these copied items:
    - `baseline`: S1's frozen static-study C_hi and C_br, as copied constants with their bit-exactness flags;
    - the input digests.

    None of them is computed by the rehearsal.
- **What is not computed.**
  - No S1 matrix is assembled or factorised, and no S1 energy or capacitance is formed.
  - The S1 geometry phase and the construction of S1's four attempt sets (for the separation check) are geometry only.
  - Proxy A, the configuration selection and the Confirmations are not run.
- **Out of scope.** The Confirmations (accepted), proxy A, the configuration selection, Palace, Route A and E1 execution.
- **Stop.** After part 2, or at the first failure, the evidence is frozen and the rehearsal work stops.
