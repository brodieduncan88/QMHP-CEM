#!/usr/bin/env python
"""Verify the vendored release bundle against its own AMD-C manifest.

Exit codes: 0 verified, 1 discrepancies found.

Two manifest entries name base PDFs that the bundle does not ship
(`base_v1_5_8e_117pp_operative.pdf`, `base_v1_5_8e_109pp_provenance.pdf`).
Those are reported as absent, not as failures.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE = REPO_ROOT / "reference" / "v1_5_8f_release_bundle"
MANIFEST = BUNDLE / "qmhp_v158f_amdc_manifest.json"

#: Listed in the manifest but not shipped inside the bundle.
KNOWN_ABSENT = frozenset(
    {"base_v1_5_8e_117pp_operative.pdf", "base_v1_5_8e_109pp_provenance.pdf"}
)


def verify() -> tuple[int, list[str]]:
    manifest = json.loads(MANIFEST.read_text())
    verified = 0
    findings: list[str] = []

    for name, expected in sorted(manifest.items()):
        path = BUNDLE / name
        if not path.exists():
            if name not in KNOWN_ABSENT:
                findings.append(f"{name}: listed in the manifest but missing")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual == expected:
            verified += 1
        else:
            findings.append(
                f"{name}: manifest {expected[:12]}… but file hashes {actual[:12]}…"
            )

    listed = set(manifest)
    for path in sorted(BUNDLE.iterdir()):
        if path.name == MANIFEST.name or path.name.startswith("__"):
            continue
        if path.name not in listed:
            findings.append(f"{path.name}: present but absent from the manifest")

    return verified, findings


def main() -> int:
    verified, findings = verify()
    total = len(json.loads(MANIFEST.read_text()))
    print(f"reference bundle: {verified}/{total} verified, "
          f"{len(KNOWN_ABSENT)} listed-but-not-shipped")
    for finding in findings:
        print(f"  ! {finding}")
    if findings:
        print("BUNDLE INTEGRITY FAILED", file=sys.stderr)
        return 1
    print("bundle integrity verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
