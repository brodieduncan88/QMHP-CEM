# Release scope, frozen from ba076d9

**Approved by the owner on 26 September 2026**, in the working session:
"Approve narrow release scope — Palace benchmark + QuTiP fixed-point bundle only, openEMS/geometry
explicitly unsupported". That approval is a session statement, and repository files cannot prove it.

The scope is frozen from commit `ba076d9d972077a7a3e256a6404ab455fd748461` on branch
`qutip/branch-a-fixed-point-crosscheck-v1-prep`. Everything below was measured from that commit's git
objects.

**What this approval does not approve.** It approves no release tag, publication, merge or pull
request. It also approves no new solve, QuTiP run, export or extraction. It defines what a release built
from this repository may claim. Each further action needs its own approval.

| document | role |
|---|---|
| [`CLAIM-REGISTER.json`](CLAIM-REGISTER.json) | every claim and non-claim the release makes, with measured digests and facts |
| [`EXCEPTION-REGISTER.json`](EXCEPTION-REGISTER.json) | every quarantine, approved deviation, disclosed defect, unrecomputable item and open decision |
| [`STATUS-ADDENDUM-2026-09-26.md`](STATUS-ADDENDUM-2026-09-26.md) | dated reconciliation of stale statements; edits nothing |
| `tests/test_release_registers.py` | freezes this file and the three documents above by sha256 and checks the registers against the evidence; the test file itself is not pinned |

## 1. In scope

### (a) The Palace empty-cavity benchmark

The golden records solve the empty Object 001 vacuum cavity, 22 × 22 × 1.5 mm, as a closed PEC box. The
verification records also solve an auxiliary 22 × 22 × 7.0/7.7 mm box and attempt the 1.5/1.65 mm Object 001
height benchmark, which is BLOCKED. No record models the chip, recess, launches or lid.

- 13 golden records, `results/PALACE-GOLDEN-20260915T014639Z` through `results/PALACE-GOLDEN-20260920T120817Z`.
  Each verifies against its execution-time `manifest.sha256`.
- 4 verification-campaign records:
  - `results/PALACE-VERIFY-20260915T065055Z`, `…T091242Z` and `…T115901Z` verify against their
    `manifest.sha256`.
  - `results/PALACE-VERIFY-20260915T063014Z` is a failed execution. It is QUARANTINED, has no register and
    is content-pinned (EXC-P01).
- The code that produced them. It is cited, not pinned, because each record was produced by the code at
  its own recorded commit:
  - `solvers/palace/` `__init__.py`, `adapter.py`, `analytic.py`, `config.py`, `mesh.py`, `outputs.py` and
    `verification.py`, with `golden/GOLDEN.sha256` and `golden/QMHP-CEM-A-RF-000001.json`;
  - `scripts/palace_golden_run.py` and `scripts/palace_verify_campaign.py`;
  - `docker/palace.Dockerfile` and the two Palace workflows.

  The scripts also use shared modules that are not Palace-specific: `contracts/`, `evaluator/` (the gate
  verdicts), `orchestrator/environment.py`, `manifest.py` and `pipeline.py`, `solvers/__init__.py`,
  `solvers/adapter.py` (`validate_convergence()`) and `models/` (the nominal device model). The other
  modules in `solvers/palace/` (`coupled_*`, `mesh_inspection`, `mode_admission`, `port_diagnostic`) belong
  to the out-of-scope coupled-candidate work.

The register digest of every record is in `CLAIM-REGISTER.json` → `in_scope_records`.

### (b) The QuTiP fixed-point bundle (QUTIP-A-READOUT-CROSSCHECK-v1)

- `results/QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z`: the one approved execution, and the only
  scientific evidence in this part.
- Supporting provenance, none of it a scientific attempt:
  - `results/QUTIP-A-LAUNCH-BLOCKED-20260926T025352Z`
  - `results/QUTIP-A-MAC-MEMORY-DIAGNOSTIC-20260926T045655Z`
  - `results/QUTIP-A-LAUNCHER-CONTROL-TEST-20260926T060642Z`
- The bridge: `docs/qutip/branch-a-fixed-point-crosscheck-v1.md`,
  `tools/qutip_bridge/check_branch_a_reference.py`, `schemas/qutip/branch-a-reference-v1.schema.json`
  and `scripts/export_qutip_branch_a_reference.py`. Their bytes are pinned by the executed record.
- `experiments/qutip-a-readout-crosscheck/`: the launcher, the resource-rule approval, the attempt
  ledger, the execution log and the README.

The model is Branch A fluxonium-readout, Nq = 10, Nph = 12, at a fixed readout of 4.301974466 GHz. The
coupling is g = 0.150 GHz, classified VERIFIED-COMPUTATIONAL. It is a reference coefficient, **not
geometry-derived and not S1-extracted**.

## 2. Explicitly unsupported

| capability | why it is unsupported | register |
|---|---|---|
| openEMS (`solvers/openems/`, `docker/openems.Dockerfile`) | `OpenemsSolver.preflight()` always raises `SolverUnavailable`, and the CLI returns exit code 4. No openEMS record exists, and the Dockerfile is an unpinned skeleton | REL-BD-01, EXC-B01 |
| planar chip geometry (`geometry/chip_planar/`) | every cell and the DRC raise `PlanarGeometryNotImplemented` | REL-BD-02 |
| PicoGK package geometry (`geometry/package_picogk/`) | `Program.cs` returns 3 (NOT IMPLEMENTED) and `Object001Package.Generate` throws | REL-BD-03 |

`tests/test_release_registers.py` pins the bytes of every file in `solvers/openems/`,
`geometry/chip_planar/` and `geometry/package_picogk/`, plus `docker/openems.Dockerfile`. It also pins the
file set of those three directories. It exercises the registry-resolved openEMS adapter and the
package-level planar cells, and it executes them only while their bytes match the pins. Any change there,
including an implementation, fails the test until a superseding scope is approved. An implementation
placed in some other directory would not be detected by this mechanism, and the C# project itself is not
run by the tests.

## 3. Out of scope

Out of scope means no release claim, neither endorsed nor withdrawn (REL-BD-04):

- the coupled-candidate campaign (`COUPLED-*`, `ROUTE-A-SYNTHETIC-*`, `docs/coupled-candidate/`,
  first-moment);
- E1 (`E1-S1-LOWER-BOUND-*`);
- the static studies (`STATIC-ANCHOR-TEST-*`, `STATIC-REFINEMENT-STUDY-*`);
- the V2A audit (`docs/v2a/`, `tools/v2a/`);
- mock sweeps;
- the README's V2A and mock-sweep sections.

Their records remain frozen evidence under `tests/test_frozen_evidence.py`.

## 4. What a release may say, and what it must not

**It may say**, always with the qualifications attached in the claim register:

- **Palace execution.** Palace 0.13.0 executed end to end 13 times on the empty PEC box. All four
  requested TM_mn0 modes agree with the closed form, with a worst relative deviation of
  4.7230588919842275e-05. This check verifies the X/Y extent and unit scaling, not the height.
- **Palace verification campaign.**
  - Empty-box mesh refinement passes the predeclared 1e-4 rules in three records.
  - The auxiliary-box height benchmark passes in two records.
  - The Object 001 height benchmark is BLOCKED.
- **QuTiP cross-check.** The classification has three parts, always quoted together:
  - **numerical cross-check PASS 11/11**, as per-check checker verdicts against frozen engineering
    thresholds;
  - **execution integrity VERIFIED**;
  - **protocol conformance QUALIFIED: RESOURCE-LIMIT DEVIATION**. The frozen `memory_limit_MB = 1024` was
    not enforced. The approved address-space-growth control was used instead, and it is not a
    total-memory limit.

  No tool issued an overall scientific verdict. This is not an unqualified overall scientific PASS.

**It makes none of the following claims.** The claim register excludes each of them. The first is excluded
by REL-QT-01 (overall scientific verdict NOT ISSUED) and the growth-control item by REL-QT-06 and EXC-Q01.
The rest are NOT-ESTABLISHED entries:

- no claim that anything is an **overall scientific PASS**;
- no claim that the P4PRE_SPECTRAL PASS or the 9.635690 GHz empty-box mode describes the Object 001
  **package**, and no claim that the COLLISION PASS is evidence about the box or the package: it is computed
  from the nominal Branch-A device model and reads no Palace output;
- no claim that Object 001 has been validated in Palace. The `"validated": true` field in the golden records
  means only that the empty-box result passed `validate_convergence()`;
- no claim that any number is an **error bound**, a convergence order or a physical uncertainty;
- no claim that agreement beyond the QuTiP Hamiltonian is **independent** confirmation;
- no claim that g = 0.150 GHz is geometry-derived;
- no claim that the FLAGGED regression pins are resolved;
- no claim that a test exercises the QuTiP assembly path;
- no claim that the checker's memory was bounded;
- no claim that the growth control is a memory limit;
- no claim that linked-library provenance was recorded.

## 5. Open items that travel with the release

These are in the exception register. None is resolved by this scope:

- the resource-limit deviation (EXC-Q01, approved and carried);
- the narrow record-specific file-type exception (EXC-Q02);
- the provenance overclaim inside pinned bytes (EXC-Q03);
- the unrecorded licence status of QuTiP (EXC-Q06) and of the tools that produced the Palace evidence:
  Palace, the libraries its image builds (MFEM, hypre, METIS, PETSc/SLEPc, SuperLU_DIST, libCEED, GSLIB and
  others) and gmsh (EXC-P14). Both **need human or legal review**;
- the FLAGGED regression pins (EXC-R02, **needs a human decision**);
- out-of-scope material reading the empty-box mode as a package mode (EXC-P10);
- the unmet v0.1 definition of done (EXC-B02).

## 6. How to check it

```bash
uv run pytest -q tests/test_frozen_evidence.py tests/test_release_registers.py
```

`cem verify-results` and `cem report` cannot verify the launcher-registered or quarantined records
(EXC-R05). Use the tests above.
