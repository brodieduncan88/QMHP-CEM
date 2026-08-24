"""Append-only results storage (spec §11.3).

Layout::

    results/
    └── BATCH-<id>/
        ├── batch_report.json
        ├── manifest.sha256
        ├── QMHP-CEM-A-RF-000001/
        │   ├── candidate.json
        │   ├── geometry/
        │   ├── solver/
        │   ├── quantum_results.json
        │   └── gate_report.json
        └── ...

Normal execution never silently overwrites a completed candidate result. A
completed candidate directory is one containing ``gate_report.json``; writing
into it again raises rather than clobbering a decision-bearing artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contracts.master import REPO_ROOT

DEFAULT_RESULTS_ROOT = REPO_ROOT / "results"

#: Presence of this file marks a candidate directory as completed.
COMPLETION_MARKER = "gate_report.json"


class ResultAlreadyExists(RuntimeError):
    """An attempt was made to overwrite a completed result (spec §11.3)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            f"refusing to overwrite completed result at {path}. Results are "
            f"append-only (spec §11.3); start a new batch instead of "
            f"rewriting a decision-bearing artifact."
        )


class BatchStore:
    """Filesystem store for one batch."""

    def __init__(self, batch_id: str, root: Path | None = None) -> None:
        self.batch_id = batch_id
        self.root = Path(root or DEFAULT_RESULTS_ROOT)
        self.batch_dir = self.root / batch_id
        if self.batch_dir.exists() and (self.batch_dir / "batch_report.json").exists():
            raise ResultAlreadyExists(self.batch_dir)
        self.batch_dir.mkdir(parents=True, exist_ok=True)

    # --- candidate directories ---------------------------------------------

    def candidate_dir(self, candidate_id: str) -> Path:
        path = self.batch_dir / candidate_id
        if (path / COMPLETION_MARKER).exists():
            raise ResultAlreadyExists(path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, path: Path, payload: Any) -> Path:
        """Write JSON deterministically (sorted keys, trailing newline)."""
        if path.exists() and path.name == COMPLETION_MARKER:
            raise ResultAlreadyExists(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
        return path

    def write_model(self, path: Path, model) -> Path:  # noqa: ANN001 - pydantic model
        return self.write_json(path, model.model_dump(mode="json", by_alias=True))
