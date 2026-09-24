# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""The single filesystem gateway of the read-only viewer.

Every byte the viewer shows comes through ``ReadOnlyRepo``. It offers read
primitives only - list, stat, read, hash - and every file is opened with mode
``"rb"``. There is deliberately no write, rename, delete, mkdir or chmod
primitive to call, and the tests reject any such call anywhere in the package.

Path confinement
----------------
A request names a repository-relative POSIX path. It is refused when it is
absolute, contains ``..``, NUL or a backslash, names a denied directory
(``.git``, ``.venv``, caches), or resolves - through a symlink or otherwise -
outside the repository root. The git metadata needed to show which commit is
being viewed is read by ``checkout()`` from a fixed set of files, never from a
caller-supplied path.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath

#: Directory names never served, at any depth.
DENIED_PARTS = frozenset({".git", ".venv", "venv", "node_modules", "__pycache__",
                          ".pytest_cache", ".mypy_cache", ".ruff_cache", "scratch"})

#: Default cap on a single text read. Larger files are described, not shown.
TEXT_LIMIT = 2 * 1024 * 1024
#: Cap on a JSON document parsed for indexing.
JSON_LIMIT = 16 * 1024 * 1024
_CHUNK = 1024 * 1024
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


class AccessDenied(Exception):
    """The path is outside what the viewer may read."""


class NotFound(Exception):
    """The path does not exist in this checkout."""


class TooLarge(Exception):
    """The file exceeds the read cap for this operation."""


class ReadOnlyRepo:
    """Bounded, path-confined, read-only access to one repository checkout."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(os.path.realpath(root))
        if not os.path.isdir(self.root):
            raise NotFound(f"repository root {root!s} is not a directory")

    # ------------------------------------------------------------------ paths
    def resolve(self, rel: str) -> Path:
        """Map a repository-relative path to an absolute one, or refuse."""
        if not isinstance(rel, str) or "\x00" in rel or "\\" in rel:
            raise AccessDenied("malformed path")
        rel = rel.strip()
        pure = PurePosixPath(rel) if rel else PurePosixPath(".")
        if pure.is_absolute() or ".." in pure.parts:
            raise AccessDenied("path must be relative and may not contain '..'")
        if any(part in DENIED_PARTS for part in pure.parts):
            raise AccessDenied("path names a directory the viewer does not serve")
        real = Path(os.path.realpath(self.root / pure))
        if real != self.root and self.root not in real.parents:
            raise AccessDenied("path resolves outside the repository")
        if any(part in DENIED_PARTS for part in real.relative_to(self.root).parts):
            raise AccessDenied("path resolves into a directory the viewer does not serve")
        return real

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def exists(self, rel: str) -> bool:
        try:
            return self.resolve(rel).exists()
        except AccessDenied:
            return False

    def is_file(self, rel: str) -> bool:
        try:
            return self.resolve(rel).is_file()
        except AccessDenied:
            return False

    def is_dir(self, rel: str) -> bool:
        try:
            return self.resolve(rel).is_dir()
        except AccessDenied:
            return False

    # -------------------------------------------------------------- listing
    def list_dir(self, rel: str) -> list[tuple[str, bool]]:
        """``(name, is_dir)`` for each servable entry, sorted by name."""
        path = self.resolve(rel)
        if not path.is_dir():
            raise NotFound(rel)
        out = []
        with os.scandir(path) as it:
            for entry in it:
                if entry.name in DENIED_PARTS:
                    continue
                out.append((entry.name, entry.is_dir(follow_symlinks=False)))
        return sorted(out)

    def walk_files(self, rel: str, *, max_depth: int = 8, skip_dirs: tuple[str, ...] = (),
                   limit: int = 20000) -> list[str]:
        """Repository-relative paths of regular files under ``rel``.

        Symlinked directories are not followed, so a link cannot loop the walk
        or lead it outside the tree."""
        out: list[str] = []
        base = self.resolve(rel)
        if not base.is_dir():
            return out
        stack = [(base, 0)]
        while stack and len(out) < limit:
            path, depth = stack.pop()
            try:
                entries = sorted(os.scandir(path), key=lambda e: e.name)
            except OSError:
                continue
            for entry in entries:
                if entry.name in DENIED_PARTS:
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if depth < max_depth and entry.name not in skip_dirs:
                        stack.append((Path(entry.path), depth + 1))
                elif entry.is_file(follow_symlinks=False):
                    out.append(self.rel(Path(entry.path)))
        return sorted(out)

    def size(self, rel: str) -> int:
        return self.resolve(rel).stat().st_size

    def mtime_ns(self, rel: str) -> int:
        try:
            return self.resolve(rel).stat().st_mtime_ns
        except (AccessDenied, OSError):
            return 0

    # ------------------------------------------------------------- reading
    def read_bytes(self, rel: str, limit: int = TEXT_LIMIT) -> bytes:
        path = self.resolve(rel)
        if not path.is_file():
            raise NotFound(rel)
        with open(path, "rb") as fh:
            data = fh.read(limit + 1)
        if len(data) > limit:
            raise TooLarge(f"{rel} exceeds {limit} bytes")
        return data

    def read_text(self, rel: str, limit: int = TEXT_LIMIT) -> str:
        return self.read_bytes(rel, limit).decode("utf-8")

    def read_json(self, rel: str, limit: int = JSON_LIMIT):
        return json.loads(self.read_bytes(rel, limit).decode("utf-8"))

    def sha256(self, rel: str) -> str:
        """SHA-256 of the file's bytes, measured now, streamed."""
        path = self.resolve(rel)
        if not path.is_file():
            raise NotFound(rel)
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(_CHUNK), b""):
                digest.update(chunk)
        return digest.hexdigest()

    # ------------------------------------------------------------ git meta
    def checkout(self) -> dict:
        """Which branch and commit this checkout is at, from git's own files.

        Reads only HEAD, the named ref and packed-refs. No git process is run
        and no git object is written or modified."""
        info = {"available": False, "branch": None, "head_sha": None, "detached": False,
                "remote_branches": []}
        gitdir = self._gitdir()
        if gitdir is None:
            info["reason"] = "no .git metadata in this checkout"
            return info
        common = gitdir
        commondir = gitdir / "commondir"
        if commondir.is_file():
            common = Path(os.path.realpath(gitdir / self._small(commondir).strip()))
        head = self._small(gitdir / "HEAD").strip()
        refs = self._packed_refs(common)
        if head.startswith("ref: "):
            ref = head[5:].strip()
            info["branch"] = ref.removeprefix("refs/heads/")
            info["head_sha"] = self._ref(common, ref, refs) or self._ref(gitdir, ref, refs)
        elif _HEX40.match(head):
            info["detached"] = True
            info["head_sha"] = head
        remotes = sorted(r.removeprefix("refs/remotes/") for r in refs
                         if r.startswith("refs/remotes/"))
        remote_dir = common / "refs" / "remotes"
        if remote_dir.is_dir():
            for dirpath, _dirs, files in os.walk(remote_dir):
                for name in files:
                    full = Path(dirpath) / name
                    remotes.append(full.relative_to(remote_dir).as_posix())
        info["remote_branches"] = sorted(set(r for r in remotes if not r.endswith("/HEAD")))
        info["available"] = info["head_sha"] is not None
        return info

    def _gitdir(self) -> Path | None:
        dotgit = self.root / ".git"
        if dotgit.is_dir():
            return dotgit
        if dotgit.is_file():
            text = self._small(dotgit).strip()
            if text.startswith("gitdir:"):
                target = Path(text[7:].strip())
                if not target.is_absolute():
                    target = self.root / target
                target = Path(os.path.realpath(target))
                return target if target.is_dir() else None
        return None

    @staticmethod
    def _small(path: Path, limit: int = 65536) -> str:
        try:
            with open(path, "rb") as fh:
                return fh.read(limit).decode("utf-8", "replace")
        except OSError:
            return ""

    def _packed_refs(self, common: Path) -> dict[str, str]:
        refs: dict[str, str] = {}
        text = self._small(common / "packed-refs", limit=4 * 1024 * 1024)
        for line in text.splitlines():
            if not line or line[0] in "#^":
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2 and _HEX40.match(parts[0]):
                refs[parts[1].strip()] = parts[0]
        return refs

    def _ref(self, base: Path, ref: str, packed: dict[str, str]) -> str | None:
        if ".." in ref or ref.startswith("/"):
            return None
        loose = self._small(base / ref).strip()
        if _HEX40.match(loose):
            return loose
        return packed.get(ref)
