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
