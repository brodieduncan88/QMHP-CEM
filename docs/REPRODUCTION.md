# Reproducing and verifying the release

Written 28 September 2026 against commit `cd5c1b2` (branch
`qutip/branch-a-fixed-point-crosscheck-v1-prep`), whose claims are frozen from `ba076d9` in
[`docs/release/`](release/RELEASE-SCOPE.md).

**This file is a guide, not evidence.** It changes no record, register, approval or scope, and
it claims nothing beyond `docs/release/CLAIM-REGISTER.json`.

- **Tiers 0 to 2** read, re-hash or recompute committed data. They were run on `cd5c1b2` on 28
  September 2026 with the results shown.
- **Tier 3** executes a solver or QuTiP. It was **not** run for this guide. Inside the project,
  each Tier 3 run is a new consequential execution. It needs a predeclaration and explicit human
  approval (`CLAUDE.md` §2–§3), and it produces a **new** record. It never replaces an old one.

## 1. What works at `cd5c1b2`

| capability | status | evidence or reason | register |
|---|---|---|---|
| frozen master layer and provenance digests | works; `cem verify-master` passes | the Master PDF digest itself is UNRESOLVED: it matches neither shipped PDF | `master/provenance.json` |
| physics models: fluxonium, dressed root, F8 weight, tolerance ensemble | works; regression-tested | three pins stay FLAGGED-FOR-REVIEW; four carried values have no computing script | EXC-R02, EXC-R03 |
| gate evaluator and the hardware boundary | works | hardware gates return HARDWARE-GATED; `GateResult` refuses a hardware PASS without MEASURED evidence | — |
| orchestrator: lifecycle, append-only store, manifests | works | `cem sweep`, `cem report`, `cem verify-results` | — |
| mock solver (`TEST_FIXTURE`) | works; the only solver in default CI | output is marked synthetic | — |
| Palace eigenmode solve of the empty PEC box | executed: 13 golden and 4 campaign records | needs Docker and a locally built image; not run in default CI | REL-PAL-01 to -10 |
| Palace mesh-refinement and auxiliary height benchmarks | executed | the Object 001 height benchmark is BLOCKED (DOF budget, 3600 s timeouts) | REL-PAL-06 to -08 |
| Palace driven solve and S-parameters | **not implemented** | `P6E2_FILTER` stays INCOMPLETE: no path produces S₂₁ | REL-PAL-05 |
| coupling extraction, Route A and Route B | **not executed** | `COUPLING_EXTRACTION` stays NOT-EVALUATED; the coupled campaign is outside the release | REL-BD-04 |
| QuTiP fixed-point cross-check | executed once, on the owner's Mac | QuTiP is not a declared dependency; the one assembly test skips without it | REL-QT-01 to -10 |
| openEMS | **unsupported**; `preflight()` always raises, and the CLI exits 4 | pinned by `tests/test_release_registers.py` | REL-BD-01 |
| planar chip geometry (gdsfactory) | **unsupported**; every cell raises | pinned | REL-BD-02 |
| PicoGK package geometry (.NET) | **unsupported**; builds in CI, never run | pinned | REL-BD-03 |
| CLI verification of every record | partial: `cem verify-results` covers the 16 manifested Palace records only | the QuTiP and quarantined records are verified by the tests in §3 | EXC-R05 |

## 2. Tier 0: set up

Needs access to the repository, `uv`, and Python 3.11, the version CI pins.

```bash
git clone https://github.com/brodieduncan88/QMHP-CEM && cd QMHP-CEM
git checkout cd5c1b2
uv sync --dev
# Linux, for the gmsh mesher that the Palace tests import:
#   apt-get install libglu1-mesa
```

## 3. Tier 1: confirm the evidence is intact

Each command reads or re-hashes committed files and writes nothing.

```bash
uv run pytest -q tests/test_frozen_evidence.py tests/test_release_registers.py
uv run cem verify-master
uv run python scripts/verify_reference_bundle.py
uv run cem verify-results results/PALACE-GOLDEN-* \
  results/PALACE-VERIFY-20260915T065055Z \
  results/PALACE-VERIFY-20260915T091242Z \
  results/PALACE-VERIFY-20260915T115901Z
for d in results/QUTIP-A-*/; do
  reg=$(ls "$d" | grep -E '^(launcher-manifest|qualification-manifest)\.sha256$|^SHA256SUMS$')
  (cd "$d" && sha256sum -c --quiet "$reg") && echo "OK $d ($reg)"
done
```

The four QuTiP records use three different register names, so a single fixed filename does not
fit them all. The quarantined `results/PALACE-VERIFY-20260915T063014Z` has no register and is
checked only by `tests/test_frozen_evidence.py`.

Results on `cd5c1b2`:

| check | result |
|---|---|
| frozen-evidence and release-register tests | 34 passed |
| `cem verify-master` | `master provenance: verified`, revision v1.5.8f, 11 gates |
| reference bundle | 27/29 verified, 2 listed but not shipped (EXC-R04) |
| `cem verify-results` | `manifest intact` for all 16 records, exit 0 |
| QuTiP registers | `OK` for all four records |
| full suite, `uv run pytest` (about 15 minutes) | 1997 passed, 8 skipped |

## 4. Tier 2: recompute the headline numbers without a solver

**Palace against the closed form** (REL-PAL-02). This prints `4.7230588919842275e-05`:

```bash
uv run python -c "
import csv
from solvers.palace.analytic import mode_frequency_GHz as f
rows = list(csv.reader(open('results/PALACE-GOLDEN-20260915T014639Z/QMHP-CEM-A-RF-000001/solver/postpro/eig.csv')))[1:]
palace = [float(r[1]) for r in rows]
exact = [f(22, 22, 1.5, m, n, 0) for m, n in [(1, 1), (1, 2), (2, 1), (2, 2)]]
print(max(abs(p - e) / e for p, e in zip(palace, exact)))"
```

**The dressed readout root.** This prints `4.301974466427…`, the value of the (10, 12)
truncation convention, not a physical accuracy:

```bash
uv run python -c "from models.dressed_system import nominal_root; print(nominal_root())"
```

**The remaining checks:**

- **Regression pins:** `uv run pytest tests/test_physics_regression.py`. It covers the exact
  group, and it also asserts that the three FLAGGED gaps still exist.
- **The QuTiP comparison, recomputed in plain floats** (REL-QT-03):
  `uv run pytest tests/test_release_registers.py -k qutip`.
- **The mesh-refinement and height tables** (REL-PAL-06, -07):
  `results/PALACE-VERIFY-20260915T091242Z/summary.json`.

**The preserved QuTiP inputs.** The checker's validation-only mode confirms them. It performs no
calculation and prints `VALIDATED … no calculation performed`:

```bash
A=results/QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z/inputs/archive
uv run python tools/qutip_bridge/check_branch_a_reference.py \
  --snapshot $A/qmhp-qutip-branch-a-export-110a2e0-attempt1/branch-a-reference-v1.json \
  --schema schemas/qutip/branch-a-reference-v1.schema.json \
  --expected $A/qmhp-qutip-branch-a-preservation-110a2e0-attempt1/expected-hashes.json \
  --expected-sha256 b667aad5841de92a0c135f8551bc0ecde29f487cb4d354e647af778f195e0a24
```

## 5. Tier 3: re-execute (not run for this guide)

**Write outside `results/`.** Always pass `--results-root` pointing outside `results/`. The
frozen-evidence test pins the record set, so a new directory in `results/` fails it. The same
applies to `cem sweep`, which writes a `BATCH-*` directory.

**Solver workflows.** At `cd5c1b2` a push to `main` or `palace/**` touching the Palace paths
started `palace-golden.yml` or `palace-verify.yml`. On the successor integration branch (from
2026-10-04) both run on manual dispatch only, behind a committed predeclaration
(`.github/palace-declarations/`) and the protected `palace-solver` environment.

### 5.1 The Palace golden run

```bash
docker build -f docker/palace.Dockerfile -t qmhp-cem/palace:0.13.0 .   # first build ~14 min on 4 vCPU
uv sync --extra palace
uv run python scripts/palace_golden_run.py --results-root /tmp/repro
```

Exit codes: 0 means every mode is within the golden tolerance; 2, Palace cannot execute here; 3,
it failed or did not converge; 4, a mode disagrees with the closed form; 5, the golden digest
does not match; 6, the gate evaluation raised.

**It counts as reproduced when:**

- the four frequencies are 9.635896241, 15.23545129, 15.23570396 and 19.27229929 GHz;
- the maximum backward error is about 2.02 × 10⁻¹¹;
- the gate verdicts are the same. **Not on the successor integration branch:** there the Palace
  adapter declares the empty-cavity domain incomplete, so `P4PRE_SPECTRAL` is `INCOMPLETE` for a
  new run where the 13 frozen records say `PASS`. A rerun there reproduces the frequencies and
  the convergence figure, not that gate verdict; the frozen records are unchanged.

**These are not expected to match:**

- **the image ID**, because rebuilds are not bit-identical (EXC-P04);
- **the `eig.csv` bytes**, which already take two patterns (EXC-P02);
- **the wall time**, 23–41 s inside Palace.

A different platform or BLAS may also move the last digits. The claim is agreement with the
closed form within the adapter's rules, not byte identity.

### 5.2 The verification campaign, without the runs known to be blocked

```bash
uv run python scripts/palace_verify_campaign.py --results-root /tmp/repro \
  --only ladder-L1 --only ladder-L2 --only ladder-L3 \
  --only aux_height-d7-L1 --only aux_height-d7.7-L1 \
  --only aux_height-d7-L2 --only aux_height-d7.7-L2
```

The four `object001_height-*` runs either exceed the 400 000-DOF budget or hit the 3600 s
timeout on a GitHub-hosted runner (REL-PAL-08). `--prepare-only` meshes every run and records
DOF estimates without launching Palace.

### 5.3 The QuTiP cross-check

**Environment.** The frozen runtime: Python 3.9.6, NumPy 2.0.2, SciPy 1.13.1 and QuTiP 5.0.4.

**Command.** Take the §4 validation command and add:

```bash
  --execute \
  --frozen-rules $A/qmhp-qutip-branch-a-approval-110a2e0/frozen-rules.json \
  --frozen-rules-sha256 42e1c2a9963b92b7a3d54ff86bdebae479b8aee9a81fbd519821d32b1f3c57d6 \
  --output <a new directory outside results/>
```

**Expected.** 11/11 PASS, with differences at round-off level, about 10⁻¹⁷ to 10⁻¹¹. They need
not be bit-identical on another BLAS. Classify the outcome in the three parts of REL-QT-01, never
as an overall PASS.

**Use the launcher.** The checker alone does not apply the single-attempt ledger, the wall-time
kill or the address-space growth rule (EXC-Q01); the launcher
`experiments/qutip-a-readout-crosscheck/qutip_branch_a_launcher_asgrowth.py` does.

**The project's one approved attempt is spent.** A re-run inside the project needs a new
approval.

## 6. What cannot be reproduced from the repository

- **Two checker-attested values:** the Hamiltonian entry difference and the independent
  Hermiticity defect. The QuTiP Hamiltonian was not stored (EXC-Q04).
- **Artefacts that were never committed:**
  - the original Palace images, which were not retained (EXC-P04);
  - the owner's Mac-side custody digests and upload archives (REL-QT-10);
  - the Palace 3 × 3 sweep, which was a workflow artefact only (REL-PAL-N4).
- **The out-of-scope E1 certificate and static-refinement study.** Both attempts are spent, and
  E1 was declared the last capacitance computation on S1. Neither is part of the release.
