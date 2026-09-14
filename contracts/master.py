"""Read-only typed access to the frozen ``master/`` requirements (spec §2.1).

``master/`` is authority level 3. Code is level 4. Code may not alter a
higher-authority object to make a test or candidate pass, so this module
exposes the frozen data as deeply-immutable structures and caches them.

The loader resolves the small set of symbolic values the YAML carries for
readability (``pi``, ``-8*pi``, ``+8*pi``) and leaves genuine sentinels
(``numerical_floor``) as strings.
"""

from __future__ import annotations

import functools
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

#: Repository root, i.e. the directory containing ``master/``.
REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER_DIR = REPO_ROOT / "master"

REQUIREMENTS_FILE = MASTER_DIR / "qmhp_v158f_requirements.yaml"
GATES_FILE = MASTER_DIR / "validation_gates.yaml"
PROVENANCE_FILE = MASTER_DIR / "provenance.json"

_SYMBOLIC = {
    "pi": math.pi,
    "-8*pi": -8 * math.pi,
    "+8*pi": 8 * math.pi,
    "8*pi": 8 * math.pi,
}


class MasterMutationError(RuntimeError):
    """Raised on any attempt to mutate frozen master data at runtime."""


def _resolve(value: Any) -> Any:
    if isinstance(value, str) and value in _SYMBOLIC:
        return _SYMBOLIC[value]
    return value


def _deep_freeze(value: Any) -> Any:
    """Recursively convert mappings to read-only proxies and lists to tuples."""
    if isinstance(value, Mapping):
        return MappingProxyType({k: _deep_freeze(_resolve(v)) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(_resolve(v)) for v in value)
    return _resolve(value)


@functools.lru_cache(maxsize=1)
def requirements() -> Mapping[str, Any]:
    """Frozen QMHP v1.5.8f requirements (spec §4)."""
    with REQUIREMENTS_FILE.open() as fh:
        return _deep_freeze(yaml.safe_load(fh))


@functools.lru_cache(maxsize=1)
def validation_gates() -> Mapping[str, Any]:
    """Frozen validation gate definitions (spec §6)."""
    with GATES_FILE.open() as fh:
        return _deep_freeze(yaml.safe_load(fh))


@functools.lru_cache(maxsize=1)
def provenance() -> Mapping[str, Any]:
    """Provenance digests (spec §2.4)."""
    with PROVENANCE_FILE.open() as fh:
        return _deep_freeze(json.load(fh))


@functools.lru_cache(maxsize=1)
def gate_definitions() -> Mapping[str, Mapping[str, Any]]:
    """Gate definitions keyed by ``gate_id``."""
    return MappingProxyType({g["gate_id"]: g for g in validation_gates()["gates"]})


def gate_definition(gate_id: str) -> Mapping[str, Any]:
    try:
        return gate_definitions()[gate_id]
    except KeyError:
        raise KeyError(
            f"unknown gate_id {gate_id!r}; gates are defined in "
            f"{GATES_FILE.relative_to(REPO_ROOT)} and may not be invented in code"
        ) from None


def get(path: str) -> Any:
    """Fetch a frozen requirement by dotted path.

    >>> get("collision.minimum_abs_omega24_minus_readout_MHz")
    13.0
    """
    node: Any = requirements()
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            raise KeyError(f"no frozen requirement at path {path!r} (failed at {part!r})")
        node = node[part]
    return node


def master_revision() -> str:
    return requirements()["master_revision"]


def file_digests() -> dict[str, str]:
    """SHA-256 of each machine-readable master file, excluding provenance.json."""
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (REQUIREMENTS_FILE, GATES_FILE)
    }


def verify_provenance() -> list[str]:
    """Return a list of provenance mismatches. Empty means consistent.

    Deliberately returns findings rather than raising: a digest mismatch is a
    reportable provenance fact, and the decision to accept a replacement
    rendered byte sequence is a human one (spec §2.4).
    """
    findings: list[str] = []
    recorded = provenance().get("master_files", {})
    actual = file_digests()
    for name, digest in actual.items():
        if name not in recorded:
            findings.append(f"{name}: not recorded in provenance.json")
        elif recorded[name] != digest:
            findings.append(
                f"{name}: provenance records {recorded[name][:12]}… but file "
                f"hashes to {digest[:12]}…"
            )
    spec_file = REPO_ROOT / provenance()["cem_spec_file"]
    if spec_file.exists():
        spec_digest = hashlib.sha256(spec_file.read_bytes()).hexdigest()
        if spec_digest != provenance()["cem_spec_sha256"]:
            findings.append(
                f"{spec_file.name}: specification digest mismatch "
                f"(recorded {provenance()['cem_spec_sha256'][:12]}…, "
                f"actual {spec_digest[:12]}…)"
            )
    else:
        findings.append(f"{spec_file.name}: specification file is missing")
    return findings
