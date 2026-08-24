# manifests/

Release-level manifests that span more than one batch.

Per-batch manifests live beside their results as
`results/BATCH-<id>/manifest.sha256` and are written automatically by the
orchestrator (spec §11.4). This directory is for manifests that are promoted
deliberately — for example, the set of batches backing a specific engineering
decision or release record.

Manifest ordering is deterministic (sorted by POSIX relative path), so digests
are reproducible across machines.
