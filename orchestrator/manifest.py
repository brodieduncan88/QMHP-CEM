"""SHA-256 manifests over decision-relevant artifacts (spec §11.4).

Every decision-relevant file is included: candidate YAML/JSON, GDS, STL,
ports.json, geometry manifest, solver inputs and outputs, quantum results,
gate report, candidate report, batch report.

Manifest ordering is deterministic (sorted by POSIX-style relative path), so
the manifest digest is reproducible across machines and filesystems.

Temporary caches are excluded unless deliberately promoted to scientific
artifacts.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

#: Suffixes treated as decision-relevant scientific artifacts.
DECISION_RELEVANT_SUFFIXES = frozenset(
    {".json", ".yaml", ".yml", ".gds", ".stl", ".step", ".s2p", ".csv", ".txt", ".msh", ".md",
     ".svg", ".geo_unrolled"}
)

#: Names/directories excluded as transient caches (spec §11.4).
EXCLUDED_NAMES = frozenset({"manifest.sha256", ".DS_Store"})
EXCLUDED_DIRS = frozenset({"__pycache__", ".cache", "scratch", "tmp"})

CHUNK = 1 << 20


def file_digest(path: Path) -> str:
    """SHA-256 of a file, streamed."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def is_decision_relevant(path: Path, root: Path | None = None) -> bool:
    """Whether ``path`` is a decision-relevant artifact.

    Exclusions are evaluated against the path RELATIVE to ``root``. Matching
    them against the absolute path would let an unrelated ancestor directory
    (a results tree living under ``/tmp``, say) silently exclude the entire
    batch and produce an empty manifest.
    """
    if path.name in EXCLUDED_NAMES:
        return False
    relative = path.relative_to(root) if root is not None else Path(path.name)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    return path.suffix.lower() in DECISION_RELEVANT_SUFFIXES


class EmptyManifest(RuntimeError):
    """A results tree holds files but no decision-relevant artifact was found.

    Always a bug rather than a legitimate state: writing an empty manifest over
    a populated batch would silently discard the audit trail, and a later
    :func:`verify` would report it as intact.
    """


def collect(root: Path) -> list[tuple[str, str]]:
    """Collect ``(relative_path, sha256)`` pairs in deterministic order."""
    root = Path(root)
    entries = [
        (path.relative_to(root).as_posix(), file_digest(path))
        for path in root.rglob("*")
        if path.is_file() and is_decision_relevant(path, root)
    ]
    return sorted(entries, key=lambda item: item[0])


def render(entries: list[tuple[str, str]]) -> str:
    """Render entries in ``sha256sum`` format."""
    return "".join(f"{digest}  {rel}\n" for rel, digest in entries)


def write(root: Path, filename: str = "manifest.sha256") -> tuple[Path, str]:
    """Write the manifest for ``root``.

    Returns:
        The manifest path and the SHA-256 of the manifest itself, which is what
        a :class:`contracts.results.BatchReport` records.
    """
    root = Path(root)
    entries = collect(root)

    if not entries and any(
        p.is_file() and p.name not in EXCLUDED_NAMES for p in root.rglob("*")
    ):
        raise EmptyManifest(
            f"{root} contains files but none were collected as "
            f"decision-relevant. Refusing to write an empty manifest over a "
            f"populated batch (spec §11.4)."
        )

    body = render(entries)
    path = root / filename
    path.write_text(body)
    return path, hashlib.sha256(body.encode()).hexdigest()


#: File kinds an evidence commit may contain. Anything else is a bug in the
#: producing driver rather than evidence: the order-1 ladder's level-2 rung
#: committed a 123 MB ParaView tree because nothing checked what it had made.
COMMITTABLE_SUFFIXES = frozenset(
    {".json", ".yaml", ".yml", ".csv", ".txt", ".md", ".sha256", ".msh", ".svg", ".s2p"}
)


def unexpected_files(root: Path, allowed: frozenset[str] | None = None) -> list[str]:
    """Files in a record whose kind is not committable, relative to ``root``.

    Advisory in the sense that it decides nothing by itself; the caller refuses
    to commit when the list is non-empty. Deliberately keyed on the suffix
    rather than on size: a small stray file is as much a sign that the driver
    wrote somewhere it should not have as a large one.
    """
    suffixes = COMMITTABLE_SUFFIXES if allowed is None else allowed
    root = Path(root)
    offenders = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() not in suffixes:
            offenders.append(relative.as_posix())
    return offenders


def verify(root: Path, filename: str = "manifest.sha256") -> list[str]:
    """Re-hash a results tree against its manifest.

    Returns a list of discrepancies; empty means the tree is intact.
    """
    root = Path(root)
    path = root / filename
    if not path.exists():
        return [f"{filename} is missing from {root}"]

    recorded: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        digest, _, rel = line.partition("  ")
        recorded[rel] = digest

    actual = dict(collect(root))
    findings: list[str] = []
    for rel, digest in sorted(recorded.items()):
        if rel not in actual:
            findings.append(f"{rel}: recorded in manifest but missing from disk")
        elif actual[rel] != digest:
            findings.append(f"{rel}: content changed since the manifest was written")
    for rel in sorted(set(actual) - set(recorded)):
        findings.append(f"{rel}: present on disk but absent from the manifest")
    return findings
