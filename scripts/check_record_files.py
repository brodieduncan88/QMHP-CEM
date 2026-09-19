#!/usr/bin/env python3
"""Refuse to commit a record containing a file kind that is not evidence.

Used from the workflows immediately before ``git add``. It is the check that
was missing when the order-1 ladder's level-2 rung committed a 123 MB ParaView
tree that both the approval record and the workflow header said would be
uploaded as an artifact and not committed.

Exit status: 0 when the record contains only committable file kinds, 1 when it
does not, naming every offender.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.manifest import COMMITTABLE_SUFFIXES, unexpected_files  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", help="the record directory about to be committed")
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        help="an extra suffix to permit, e.g. --allow .png (repeatable)",
    )
    args = parser.parse_args(argv)

    record = Path(args.record)
    if not record.is_dir():
        print(f"not a directory: {record}", file=sys.stderr)
        return 1
    allowed = frozenset(COMMITTABLE_SUFFIXES | {s.lower() for s in args.allow})
    offenders = unexpected_files(record, allowed)
    if offenders:
        print(
            f"{record}: {len(offenders)} file(s) of a kind this record may not commit:",
            file=sys.stderr,
        )
        for name in offenders[:50]:
            print(f"  {name}", file=sys.stderr)
        if len(offenders) > 50:
            print(f"  ... and {len(offenders) - 50} more", file=sys.stderr)
        print(f"permitted suffixes: {sorted(allowed)}", file=sys.stderr)
        return 1
    print(f"{record}: only committable file kinds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
