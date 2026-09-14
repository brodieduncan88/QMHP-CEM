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
