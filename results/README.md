# results/

Append-only batch outputs (spec §11.3).

```
results/
└── BATCH-<timestamp>/
    ├── batch_report.json
    ├── manifest.sha256
    ├── QMHP-CEM-A-RF-000001/
    │   ├── candidate.json
    │   ├── geometry/
    │   ├── solver/
    │   ├── quantum_results.json
    │   └── gate_report.json
    └── ...
```

Normal execution never silently overwrites a completed candidate result, and a
completed batch cannot be reopened. Verify a tree against its manifest with:

```bash
uv run cem report results/BATCH-<id>
```

Batches produced with `--solver mock` contain **synthetic** values from a
`TEST_FIXTURE` and carry no evidentiary weight. Every such batch report says so
in its notes.

## Corrective-analysis records

`COUPLED-PILOT-CORR-<timestamp>/` is a **corrective analysis** of an already
executed record, written by `scripts/coupled_pilot_corrective.py`. It re-reads a
preserved record's solver outputs, launches nothing, and records the source
record's per-file sha256 digests alongside its own conclusions. The source
record is never modified: its manifest is verified before the analysis and again
after the new record is written, and the run fails if a byte moved. A corrective
analysis supersedes an earlier *reading* of the evidence; it never supersedes
the evidence.

`COUPLED-S1-RECOVERY-<timestamp>/` is an **analysis-only** record written by
`scripts/palace_s1_recovery.py`: no solver is launched. It evaluates the lumped
port's stiffness energy from a conversion derived from pinned Palace v0.13.0
source rather than fitted, measures the committed meshes, and dry-runs the
candidate meshes of one prepared experiment. It verifies every source record
against its own manifest before and after and references them by digest; it
writes to none of them. Its own `report.md` is rendered only after
`summary.json` and the record pointer are written, so a presentation failure
cannot destroy the evidence, and `scripts/check_record_files.py` refuses any
file kind the record may not carry.

## QuTiP cross-check records (external launcher)

Four `QUTIP-A-*` records were written on the owner's Mac, not by a driver in this
repository, and are committed byte for byte as delivered:

- `QUTIP-A-LAUNCH-BLOCKED-20260926T025352Z/`: supporting execution provenance. The first
  launcher stopped at BLOCKED-PREFLIGHT; the checker was not launched and the attempt was
  not consumed.
- `QUTIP-A-MAC-MEMORY-DIAGNOSTIC-20260926T045655Z/`: supporting control provenance. A
  dummy-only memory-limit diagnostic; not a QMHP or QuTiP calculation.
- `QUTIP-A-LAUNCHER-CONTROL-TEST-20260926T060642Z/`: supporting control provenance.
  Pre-flight qualification with dummy probes; no checker was launched.
- `QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z/`: scientific evidence. The one approved
  QUTIP-A-READOUT-CROSSCHECK-v1 execution: numerical cross-check PASS 11/11, execution
  integrity VERIFIED, protocol conformance QUALIFIED (resource-limit deviation). It is
  not an unqualified overall scientific PASS.

Their execution-time registers are the writers' own sha256sum-format manifests
(`launcher-manifest.sha256`, `SHA256SUMS`, `qualification-manifest.sha256`). These list
every file, not only the decision-relevant suffixes, and none is written as a
`manifest.sha256` now. `tests/test_frozen_evidence.py` verifies each record against its
register and pins the register's digest. Their non-standard text file kinds are a narrow,
record-specific exception; the general evidence file-type policy is unchanged. See
`experiments/qutip-a-readout-crosscheck/` for the approvals, the ledger and the
execution log.
