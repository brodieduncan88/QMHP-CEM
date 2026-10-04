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
``manifest.sha256`` the store writes nothing more into the batch. Public store
writes accept batch-relative paths only; absolute paths, ``..`` and symbolic
links below the batch are refused. The completion check and the write happen
under one exclusive lock on the batch directory, so a cooperating writer
cannot pass the check and land its file after a concurrent completion.

What this does not cover: code that writes into a batch without the store
(the solver adapters and the geometry driver write their own files before
completion), processes that do not take the lock, a static writer inventory,
cross-process stress evidence, or crash cleanup of a temporary file left by a
hard-killed writer. The final path is never published partially.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from contracts.master import REPO_ROOT

DEFAULT_RESULTS_ROOT = REPO_ROOT / "results"

#: A candidate directory holding this file is complete.
CANDIDATE_COMPLETION_MARKER = "gate_report.json"
#: A batch directory holding this file is complete.
BATCH_COMPLETION_MARKER = "manifest.sha256"


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
        relative = self._require_relative(Path(candidate_id))
        if len(relative.parts) != 1:
            raise ValueError(
                f"candidate id {candidate_id!r} must name one directory"
            )
        if relative.name.casefold() in {
            BATCH_COMPLETION_MARKER.casefold(),
            "batch_report.json".casefold(),
            CANDIDATE_COMPLETION_MARKER.casefold(),
        }:
            raise ValueError(f"candidate id {candidate_id!r} is a reserved name")
        path = self._absolute_target(relative)
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
        another writer already created ``path``. The temporary file is removed
        on ordinary success and Python exceptions, including a racing-write
        failure; a hard-killed process can leave that hidden temporary file.
        """
        relative = self._require_relative(Path(path))
        target = self._absolute_target(relative)
        first = relative.parts[0].casefold()
        if first == BATCH_COMPLETION_MARKER.casefold():
            raise ValueError(
                f"{BATCH_COMPLETION_MARKER} is reserved for seal_batch()"
            )
        if first == "batch_report.json".casefold() and (
            len(relative.parts) > 1 or relative.parts[0] != "batch_report.json"
        ):
            raise ValueError("batch_report.json may be created only as a file")
        if (
            len(relative.parts) >= 2
            and relative.parts[1].casefold()
            == CANDIDATE_COMPLETION_MARKER.casefold()
            and (
                len(relative.parts) > 2
                or relative.parts[1] != CANDIDATE_COMPLETION_MARKER
            )
        ):
            raise ValueError(
                f"{CANDIDATE_COMPLETION_MARKER} may be created only as a file"
            )
        body = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"

        with self._batch_lock():
            self._refuse_if_completed(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Re-checked after mkdir: no component below the batch may be a link.
            self._absolute_target(relative)
            self._create(target, body)
        return target

    def seal_batch(
        self,
        build_manifest: Callable[[], tuple[str, str]],
        expected_sha256: str,
    ) -> tuple[Path, str]:
        """Atomically publish the manifest that marks this batch complete."""
        marker = self.batch_dir / BATCH_COMPLETION_MARKER
        report = self.batch_dir / "batch_report.json"
        with self._batch_lock():
            if marker.exists():
                raise ResultAlreadyExists(marker)
            if report.is_symlink() or not report.is_file():
                raise RuntimeError(
                    "batch_report.json must be a regular file before sealing"
                )
            try:
                embedded = json.loads(report.read_text())["manifest_sha256"]
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise RuntimeError(
                    "batch_report.json has no valid manifest_sha256"
                ) from exc
            if embedded != expected_sha256:
                raise RuntimeError(
                    "batch_report.json manifest_sha256 differs from the "
                    "expected preview digest"
                )

            body, reported_sha256 = build_manifest()
            actual_sha256 = hashlib.sha256(body.encode()).hexdigest()
            if reported_sha256 != actual_sha256:
                raise RuntimeError(
                    "manifest builder reported a digest that does not match "
                    "its body; refusing to publish a completion marker"
                )
            if actual_sha256 != expected_sha256:
                raise RuntimeError(
                    "manifest preview changed while finalizing the batch; "
                    "refusing to publish a completion marker"
                )
            self._create(marker, body)
        return marker, actual_sha256

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

    def _require_relative(self, path: Path) -> Path:
        """Validate and return a batch-relative public store path."""
        relative = Path(path)
        if relative.is_absolute():
            raise ValueError(
                f"result path {path} is absolute; use a batch-relative path"
            )
        if not relative.parts or relative == Path("."):
            raise ValueError(f"result path {path} does not name a file")
        if ".." in relative.parts:
            raise ValueError(f"result path {path} contains '..'; refusing traversal")
        return relative

    def _absolute_target(self, relative: Path) -> Path:
        """Resolve a validated relative path, refusing any indirection.

        A symbolic link may not redirect a write into another candidate or out
        of the batch. Callers must first pass the public path through
        :meth:`_require_relative`.
        """
        relative = self._require_relative(relative)
        batch = Path(os.path.abspath(self.batch_dir))
        absolute = batch / relative
        try:
            absolute.resolve().relative_to(batch.resolve())
        except ValueError as exc:
            raise ValueError(
                f"result path {relative} is outside batch directory {self.batch_dir}"
            ) from exc
        current = batch
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(
                    f"result path {relative} passes through the symbolic link {current}"
                )
        return absolute

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
