# Pre-approval Confirmation runs, revision 8.5: predeclaration

**Status: PREDECLARED, NOT RUN** when this file was committed. Human instruction of 2026-09-24: "Proceed with the final pre-execution Confirmation stage only."

- **Question.** Does the frozen implementation pass the Confirmation of contract §3.2 item 2, nominal and forced fallback, on the separated synthetic stand-in? Each run must stay within 450 s CPU and 2 GiB peak address space.
- **Baseline.** The `90bf9eb` Confirmations (`../confirmation-nominal.json`, `../confirmation-forced.json`) measured 288.0 s / 1.43 GiB and 312.6 s / 1.45 GiB. They ran on the revision-8.2 stand-in, whose island was S1's island (D14). They are superseded, kept byte-unchanged and not overwritten.
- **Exact configuration.**
  - Contract: `E1-CONTRACT.rev8.5.md`, sha256 `2db93be49ee455f1da952acbe300f370d7614a8986c4151a9563adf805f00150`.
  - Code: the implementation frozen at `88988d4`. The runs execute from HEAD, the commit of this file; its code is byte-identical. sha256 of each file:
    - `driver.py` `75121e5f199bce4344e2dc84d4c6fc2d966659ae72233807d6439ef1f133d807`;
    - `e1_numerics.py` `d3094dac0c5a0907a6fadd66986f37afd9e5d306d5c3d6f09f879e9551e4ab8d`;
    - `e1_geometry.py` `226153c5351d101c9b2565dcbc3252781f4c0a2ebc658b9942ce86ff0fe639d3`;
    - `e1_controls.py` `7fa268c1eefa7e3d738c2c3104649be263d5044fb1fdf1524bf5bafe825d3e8f`;
    - `anchor_fem.py` `1123e38f16b6c443fd397330db568e8c5d4e18fa9a7c4dc844c599204e6437c1`;
    - `orchestrator/manifest.py` `66a68dd40b8b2644efa8d204e723f27fe0a8e2127d038853e28271b8280d463f`;
    - `e1_standin.py` (pre-approval) `ad3643836bcd6d9e3eed98ab7c7a4f2e320dd1a2c04093e66e3cde564b9c0d77`.
  - Inputs (measured before this commit, equal to the pins):
    - mesh `d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428`;
    - baseline manifest `e3e447068dea6b4c2790c29de7a34be77f971717fa6e40964f6e31fdee193622`;
    - baseline summary `7eca21f3688a662f0324003093de2902cfbd67503fa0de71f5c028df13181298`.
  - Environment (measured):
    - Python 3.11.15, numpy 2.4.6, scipy 1.17.1, glibc 2.39, long double with a 63-bit mantissa;
    - BLAS/OpenMP threads 1; 4 CPUs;
    - the driver's preflight is clean; the attempt is unspent.
- **Independent variable.** The mode: nominal, or forced fallback (every factorisation fallback forced for E1.2 and E1.2-excl-R1).
- **Controlled variables.**
  - The frozen stand-in generator, the synthetic controls and the S1 geometry phase (geometry only).
  - The budget the driver enforces: CPU soft 900 s and hard 960 s; address space 4 GiB soft; wall alarm 1,200 s; outer kill 1,260 s.
  - The environment and the thread counts.
  - One run at a time on a quiet host.
- **Invocation.** Each run starts from the repository root:

  `env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 1260 .venv/bin/python experiments/e1-s1-lower-bound/driver.py --confirmation <nominal|forced> --out <scratch>/confirmation-<mode>.json`

  Its stdout and stderr are captured.
- **Acceptance, per run.** Exit code 0 and `confirmation_pass` true, which needs every check true:
  - `cpu_within_limit` (≤ 450 s);
  - `peak_within_limit` (≤ 2 GiB);
  - `budget_enforced`;
  - `separated_from_s1`: the stand-in and control separation problems are both empty;
  - `capacitance_phase_ran_on_expected_paths`: in the forced run, E1.2 and E1.2-excl-R1 on `last_resort`;
  - `no_stop_signal`, `no_error`, `evidence_directory_verifies`, `preflight_clean_on_this_host`.

  Also reported, but not criteria:
  - the control results;
  - the outcome on the stand-in;
  - the K4 statuses;
  - per set: the path, m, `width_rel`, `check_g_rel` and g_E, all dimensionless, on the synthetic stand-in.
- **Failure.** Any check false, a non-zero exit, a kill or a timeout fails the run. The configuration is not re-selected silently (contract §3.2 item 2). There is no retry: preserve the evidence and stop.
- **Budget and attempts.**
  - CPU: 450 s per run is the criterion, and the driver's caps apply above it.
  - Wall clock: 1,260 s per run.
  - Attempts: exactly one per mode, no retry.
  - Order: nominal, then forced.
- **Expected evidence, per run.**
  - The output JSON, and the stdout and stderr logs.
  - The driver's evidence directory (`/tmp/qmhp-e1-confirmation-*`), sealed by its `manifest.sha256`.
  - A run record: UTC start and end, exit code, HEAD, `git status`, host load.

  The evidence is frozen by copying it into this directory with a SHA-256 manifest and committing it. The stand-in's numbers are synthetic, not S1 values.
- **What is not computed.**
  - No S1 matrix is assembled or factorised, and no S1 energy or capacitance is formed. The S1 geometry phase assembles no matrix. The stand-in and the control sets are checked for separation from the S1 attempt sets before any numerics on them.
  - The stand-in's ground shares 534 individual panels with S1's E1.2 (476 of them in E1.2-excl-R1), which D15 permits. So the stand-in's matrix holds entries for those panel pairs, but no S1 attempt set, and no image of one, is assembled, factorised or used in an energy.
- **Out of scope.** Proxy A, the configuration selection, the rehearsal (not instructed), Palace, Route A and E1 execution.
- **Stop.** After both runs, or at the first failure, the evidence is frozen and the work stops.
