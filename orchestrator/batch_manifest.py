"""Batch manifests with a self-referential batch report (manifest version 2).

A batch report records the digest of the manifest that lists the report, which
would be a cryptographic fixed point if hashed literally. Version 2 hashes the
report with only its ``manifest_sha256`` field set to a placeholder, marks the
manifest with a header line, and verification separately checks that the
stored field equals the digest of the completed manifest, so changing either
side is detected.

This module carries the version-2 logic that main introduced in PR #10. It is
kept apart from :mod:`orchestrator.manifest` on the successor integration
branch because that module's exact bytes are bound by executed, consumed
approvals (E1 and the static-refinement study load it by path and pin its
sha256). Version-1 manifests verify here exactly as they do there.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from orchestrator.manifest import (
    EXCLUDED_NAMES,
    EmptyManifest,
    file_digest,
    is_decision_relevant,
)

SELF_REFERENTIAL_HEADER = (
    "# qmhp-cem-manifest-v2: batch_report.json manifest_sha256 canonicalized\n"
)
MANIFEST_DIGEST_PLACEHOLDER = "0" * 64


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


def write(
    root: Path,
    filename: str = "manifest.sha256",
    *,
    self_referential_report: bool = False,
    exclusive: bool = False,
) -> tuple[Path, str]:
    """Write the manifest for ``root`` and return its path and sha256."""
    root = Path(root)
    entries = collect(root, self_referential_report=self_referential_report)

    if not entries and any(
        p.is_file() and p.name not in EXCLUDED_NAMES for p in root.rglob("*")
    ):
        raise EmptyManifest(
            f"{root} holds files but none is decision-relevant; refusing to "
            f"write an empty manifest that would erase the audit trail of a "
            f"populated batch (spec §11.4)."
        )

    body = render(entries, self_referential_report=self_referential_report)
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
    return path, hashlib.sha256(body.encode()).hexdigest()


def verify(root: Path, filename: str = "manifest.sha256") -> list[str]:
    """Re-hash a results tree against a version-1 or version-2 manifest.

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
