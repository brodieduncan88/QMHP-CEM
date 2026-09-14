#!/usr/bin/env python
"""Recompute the digests recorded in master/provenance.json.

The Master PDF digest and the operative-base digest are NEVER touched by this
script. Per spec §2.4, adopting a different rendered byte sequence as the
canonical frozen Master is a deliberate human act: verify and record the
replacement explicitly, do not let tooling substitute it.

Usage:
    uv run python scripts/refresh_provenance.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVENANCE = REPO_ROOT / "master" / "provenance.json"

#: Fields this script must never rewrite.
PROTECTED = ("qmhp_master_pdf_sha256", "operative_base_v158e_sha256")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift without writing (exit 1 if any)",
    )
    args = parser.parse_args(argv)

    payload = json.loads(PROVENANCE.read_text())
    before = json.dumps(payload, sort_keys=True)

    spec = REPO_ROOT / payload["cem_spec_file"]
    payload["cem_spec_sha256"] = hashlib.sha256(spec.read_bytes()).hexdigest()
    payload["master_files"] = {
        name: hashlib.sha256((REPO_ROOT / "master" / name).read_bytes()).hexdigest()
        for name in sorted(payload["master_files"])
    }

    original = json.loads(PROVENANCE.read_text())
    for field in PROTECTED:
        if payload[field] != original[field]:
            print(f"refusing to modify protected field {field}", file=sys.stderr)
            return 2

    if json.dumps(payload, sort_keys=True) == before:
        print("provenance is up to date")
        return 0

    if args.check:
        print("provenance is STALE; run without --check to refresh", file=sys.stderr)
        return 1

    PROVENANCE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"refreshed {PROVENANCE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
