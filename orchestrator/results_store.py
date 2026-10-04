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

Normal execution never reopens an existing batch or candidate directory and
never overwrites an artifact, including a partial one left by an interrupted
run. JSON files are created atomically from a same-directory temporary file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from contracts.master import REPO_ROOT

DEFAULT_RESULTS_ROOT = REPO_ROOT / "results"

class ResultAlreadyExists(RuntimeError):
    """An attempt was made to reopen or overwrite a result (spec §11.3)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            f"refusing to reopen or overwrite result at {path}. Results are "
            f"append-only (spec §11.3); start a new batch instead of "
            f"rewriting a decision-bearing artifact."
        )


class BatchStore:
    """Filesystem store for one batch."""

    def __init__(self, batch_id: str, root: Path | None = None) -> None:
        self.batch_id = batch_id
        self.root = Path(root or DEFAULT_RESULTS_ROOT)
        self.batch_dir = self.root / batch_id
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            # mkdir(exist_ok=False) is the batch allocation lock. Two
            # processes racing for the same timestamp can never share a batch
            # directory or overwrite one another's partial output.
            self.batch_dir.mkdir(exist_ok=False)
        except FileExistsError as exc:
            raise ResultAlreadyExists(self.batch_dir) from exc

    # --- candidate directories ---------------------------------------------

    def candidate_dir(self, candidate_id: str) -> Path:
        path = self.batch_dir / candidate_id
        try:
            path.mkdir(exist_ok=False)
        except FileExistsError as exc:
            raise ResultAlreadyExists(path) from exc
        return path

    def write_json(self, path: Path, payload: Any) -> Path:
        """Atomically create deterministic JSON without overwriting a file.

        The content is flushed to a temporary file in the target directory,
        then hard-linked into place. Creating the link is atomic and fails if
        another writer already created ``path``. The temporary file is always
        removed, including on a racing-write failure.
        """
        path = Path(path)
        self._require_inside_batch(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"

        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as fh:
                temporary = Path(fh.name)
                fh.write(body)
                fh.flush()
                os.fsync(fh.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise ResultAlreadyExists(path) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return path

    def write_model(self, path: Path, model) -> Path:  # noqa: ANN001 - pydantic model
        return self.write_json(path, model.model_dump(mode="json", by_alias=True))

    def _require_inside_batch(self, path: Path) -> None:
        """Reject accidental or hostile writes outside this batch."""
        try:
            path.resolve().relative_to(self.batch_dir.resolve())
        except ValueError as exc:
            raise ValueError(
                f"result path {path} is outside batch directory {self.batch_dir}"
            ) from exc
