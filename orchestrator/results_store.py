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

Completion is final. Once a candidate directory holds ``gate_report.json`` the
store writes nothing more into it, and once the batch holds
``batch_report.json`` the store writes nothing more into the batch. A target
path may not contain ``..`` or pass through a symbolic link below the batch
directory, so one candidate cannot be written through another's path. The
completion check and the write happen under one exclusive lock on the batch
directory, so a writer cannot pass the check and land its file after a
concurrent completion.

What this does not cover: code that writes into a batch without the store
(the solver adapters and the geometry driver write their own files before
completion), and processes that do not take the lock.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from contracts.master import REPO_ROOT

DEFAULT_RESULTS_ROOT = REPO_ROOT / "results"

#: A candidate directory holding this file is complete.
CANDIDATE_COMPLETION_MARKER = "gate_report.json"
#: A batch directory holding this file is complete.
BATCH_COMPLETION_MARKER = "batch_report.json"

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
        self._relative_target(path)
        with self._batch_lock():
            if (self.batch_dir / BATCH_COMPLETION_MARKER).exists():
                raise ResultAlreadyExists(self.batch_dir)
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
        relative = self._relative_target(path)
        body = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"

        with self._batch_lock():
            self._refuse_if_completed(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Re-checked after mkdir: no component below the batch may be a link.
            self._relative_target(path)
            self._create(path, body)
        return path

    def _create(self, path: Path, body: str) -> None:
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

    def write_model(self, path: Path, model) -> Path:  # noqa: ANN001 - pydantic model
        return self.write_json(path, model.model_dump(mode="json", by_alias=True))

    def _relative_target(self, path: Path) -> Path:
        """Return ``path`` relative to the batch, refusing any indirection.

        Refused: a path outside the batch, a path containing ``..``, the batch
        directory itself, and any path with a symbolic link at or below the
        batch directory. The check is lexical and then per component, so a
        link cannot redirect a write into another candidate or out of the batch.
        """
        if ".." in Path(path).parts:
            raise ValueError(f"result path {path} contains '..'; refusing traversal")
        absolute = Path(os.path.abspath(path))
        batch = Path(os.path.abspath(self.batch_dir))
        try:
            relative = absolute.relative_to(batch)
        except ValueError as exc:
            raise ValueError(
                f"result path {path} is outside batch directory {self.batch_dir}"
            ) from exc
        if not relative.parts:
            raise ValueError(f"result path {path} is the batch directory itself")
        try:
            absolute.resolve().relative_to(batch.resolve())
        except ValueError as exc:
            raise ValueError(
                f"result path {path} is outside batch directory {self.batch_dir}"
            ) from exc
        current = batch
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(
                    f"result path {path} passes through the symbolic link {current}"
                )
        return relative

    def _refuse_if_completed(self, relative: Path) -> None:
        """Refuse a write into a completed batch or candidate directory."""
        if (self.batch_dir / BATCH_COMPLETION_MARKER).exists():
            raise ResultAlreadyExists(self.batch_dir)
        if len(relative.parts) >= 2:
            candidate = self.batch_dir / relative.parts[0]
            if (candidate / CANDIDATE_COMPLETION_MARKER).exists():
                raise ResultAlreadyExists(candidate)

    @contextlib.contextmanager
    def _batch_lock(self):
        """Hold an exclusive lock on the batch directory (advisory, flock).

        Every store write takes it, so the completion check and the write are
        one step with respect to every other store writer, in this process or
        another. Writers that bypass the store are not bound by it.
        """
        fd = os.open(self.batch_dir, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)
