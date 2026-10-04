"""SHA-256 manifests over decision-relevant artifacts (spec §11.4).

Every decision-relevant file is included: candidate YAML/JSON, GDS, STL,
ports.json, geometry manifest, solver inputs and outputs, quantum results,
gate report, candidate report, batch report. Version 2 handles the batch
report's manifest self-reference by canonicalizing only that digest field and
then independently verifying it against the completed manifest's digest.

Manifest ordering is deterministic (sorted by POSIX-style relative path), so
the manifest digest is reproducible across machines and filesystems.

Temporary caches are excluded unless deliberately promoted to scientific
artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

#: Suffixes treated as decision-relevant scientific artifacts.
DECISION_RELEVANT_SUFFIXES = frozenset(
    {".json", ".yaml", ".yml", ".gds", ".stl", ".step", ".s2p", ".csv", ".txt", ".msh", ".md"}
)

#: Names/directories excluded as transient caches (spec §11.4).
EXCLUDED_NAMES = frozenset({"manifest.sha256", ".DS_Store"})
EXCLUDED_DIRS = frozenset({"__pycache__", ".cache", "scratch", "tmp"})

CHUNK = 1 << 20

# A batch report contains the digest of the manifest that contains the report.
# Hashing the literal field would be an impossible cryptographic fixed-point.
# Version 2 therefore hashes a canonical report with only that one field set to
# this placeholder. Verification separately checks that the stored field equals
# the digest of the completed manifest, so changing either side is detected.
SELF_REFERENTIAL_HEADER = (
    "# qmhp-cem-manifest-v2: batch_report.json manifest_sha256 canonicalized\n"
)
MANIFEST_DIGEST_PLACEHOLDER = "0" * 64


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


def _json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    ).encode()


def canonical_batch_report_digest(payload: dict[str, Any]) -> str:
    """Hash a report with its self-referential manifest field normalized."""
    normalized = dict(payload)
    normalized["manifest_sha256"] = MANIFEST_DIGEST_PLACEHOLDER
    return hashlib.sha256(_json_bytes(normalized)).hexdigest()


def _artifact_digest(
    path: Path, root: Path, self_referential_report: bool
) -> str:
    if (
        self_referential_report
        and path.relative_to(root).as_posix() == "batch_report.json"
    ):
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            raise ValueError(f"{path} must contain a JSON object")
        return canonical_batch_report_digest(payload)
    return file_digest(path)


def collect(
    root: Path, *, self_referential_report: bool = False
) -> list[tuple[str, str]]:
    """Collect ``(relative_path, sha256)`` pairs in deterministic order."""
    root = Path(root)
    entries = [
        (
            path.relative_to(root).as_posix(),
            _artifact_digest(path, root, self_referential_report),
        )
        for path in root.rglob("*")
        if path.is_file() and is_decision_relevant(path, root)
    ]
    return sorted(entries, key=lambda item: item[0])


def render(
    entries: list[tuple[str, str]], *, self_referential_report: bool = False
) -> str:
    """Render entries in ``sha256sum`` format."""
    header = SELF_REFERENTIAL_HEADER if self_referential_report else ""
    return header + "".join(f"{digest}  {rel}\n" for rel, digest in entries)


def preview_with_batch_report(
    root: Path, report_payload: dict[str, Any]
) -> tuple[str, str]:
    """Return the final v2 manifest body/digest before writing the report.

    This lets the report be created exactly once with the digest of the final
    manifest already embedded. Calling :func:`write` afterwards with
    ``self_referential_report=True`` must reproduce this body byte-for-byte.
    """
    root = Path(root)
    if (root / "batch_report.json").exists():
        raise FileExistsError(f"batch_report.json already exists in {root}")
    entries = collect(root)
    entries.append(
        ("batch_report.json", canonical_batch_report_digest(report_payload))
    )
    entries.sort(key=lambda item: item[0])
    body = render(entries, self_referential_report=True)
    return body, hashlib.sha256(body.encode()).hexdigest()


def build(
    root: Path, *, self_referential_report: bool = False
) -> tuple[str, str]:
    """Build a manifest body and digest without publishing the marker."""
    root = Path(root)
    entries = collect(root, self_referential_report=self_referential_report)

    if not entries and any(
        p.is_file() and p.name not in EXCLUDED_NAMES for p in root.rglob("*")
    ):
        raise EmptyManifest(
            f"{root} contains files but none were collected as "
            f"decision-relevant. Refusing to write an empty manifest over a "
            f"populated batch (spec §11.4)."
        )

    body = render(entries, self_referential_report=self_referential_report)
    return body, hashlib.sha256(body.encode()).hexdigest()


def write(
    root: Path,
    filename: str = "manifest.sha256",
    *,
    self_referential_report: bool = False,
    exclusive: bool = False,
) -> tuple[Path, str]:
    """Write the manifest for ``root``.

    Returns:
        The manifest path and the SHA-256 of the manifest itself, which is what
        a :class:`contracts.results.BatchReport` records.
    """
    root = Path(root)
    body, digest = build(
        root, self_referential_report=self_referential_report
    )
    path = root / filename
    if exclusive:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=root,
                prefix=f".{filename}.",
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
                raise FileExistsError(f"refusing to overwrite {path}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    else:
        path.write_text(body)
    return path, digest


def verify(root: Path, filename: str = "manifest.sha256") -> list[str]:
    """Re-hash a results tree against its manifest.

    Returns a list of discrepancies; empty means the tree is intact.
    """
    root = Path(root)
    path = root / filename
    if not path.exists():
        return [f"{filename} is missing from {root}"]

    body = path.read_text()
    self_referential_report = body.startswith(SELF_REFERENTIAL_HEADER)
    recorded: dict[str, str] = {}
    for line in body.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        digest, _, rel = line.partition("  ")
        recorded[rel] = digest

    actual = dict(
        collect(root, self_referential_report=self_referential_report)
    )
    findings: list[str] = []
    for rel, digest in sorted(recorded.items()):
        if rel not in actual:
            findings.append(f"{rel}: recorded in manifest but missing from disk")
        elif actual[rel] != digest:
            findings.append(f"{rel}: content changed since the manifest was written")
    for rel in sorted(set(actual) - set(recorded)):
        findings.append(f"{rel}: present on disk but absent from the manifest")

    if self_referential_report:
        report_path = root / "batch_report.json"
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text())
                embedded = report.get("manifest_sha256")
            except (json.JSONDecodeError, AttributeError):
                embedded = None
            manifest_digest = hashlib.sha256(body.encode()).hexdigest()
            if embedded != manifest_digest:
                findings.append(
                    "batch_report.json: manifest_sha256 does not identify "
                    "the completed manifest"
                )
    return findings
