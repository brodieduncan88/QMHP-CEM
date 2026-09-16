#!/usr/bin/env python3
"""Print what an approval record authorises, and the record headline afterwards.

Two modes, both used by .github/workflows/palace-order1-ladder.yml:

  --approval PATH   before the run: say plainly which experiment this is, not
                    just which level, so the log shows the local refinement and
                    the mesh the approval pins.
  --headline PATH   after the run: one line for the commit message, built from
                    the record's summary.json.

Kept out of the workflow YAML because a multi-line python -c inside a block
scalar is fragile, untestable, and a failure in the headline step fails the
commit step AFTER the solve has been paid for.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def describe_approval(path: Path) -> str:
    approval = json.loads(path.read_text())
    lines = [f"level: {approval.get('level')}"]
    refinement = approval.get("port_refinement")
    if refinement is None:
        lines.append("port refinement: none (plain ladder rung)")
        return "\n".join(lines)
    lines.append(
        f"port refinement: {refinement.get('id')}  "
        f"h_port={refinement.get('h_port_mm')} mm  "
        f"pad={refinement.get('pad_mm')} mm  "
        f"transition={refinement.get('transition_mm')} mm  "
        f"ports={refinement.get('ports', ['port_F1'])}"
    )
    lines.append(f"baseline for comparison: {approval.get('baseline_record') or '(none named)'}")
    pinned = (approval.get("dry_run_mesh_sha256") or {}).get(refinement.get("id"))
    lines.append(
        f"approved mesh sha256: {pinned}" if pinned
        else "approved mesh sha256: (none named - the hash gate is INACTIVE)"
    )
    lines.append(
        "this run is a port-refined diagnostic, not a ladder rung: it is excluded "
        "from the convergence fit and compared against the plain rung at its level"
    )
    return "\n".join(lines)


def headline(path: Path) -> str:
    summary = json.loads(path.read_text())
    rung = summary.get("rung") or {}
    refinement = rung.get("port_refinement") or {}
    label = f"-{refinement['id']}" if refinement.get("id") else ""
    diagnostic = rung.get("port_diagnostic") or {}
    worst = diagnostic.get("worst_relative_disagreement_probe_vs_closure")
    worst_text = f"{worst:.2e}" if isinstance(worst, (int, float)) else "n/a"
    return (
        f"L{summary.get('level')}{label} {rung.get('status')}, "
        f"{rung.get('dof_measured')} DOF; probe-vs-closure {worst_text}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--approval", help="the approval record to describe")
    group.add_argument("--headline", help="a record's summary.json to summarise in one line")
    args = parser.parse_args(argv)
    try:
        if args.approval:
            print(describe_approval(Path(args.approval)))
        else:
            print(headline(Path(args.headline)))
    except Exception as exc:  # noqa: BLE001 - never fail a step that runs after a solve
        print(f"(could not describe: {type(exc).__name__}: {exc})", file=sys.stderr)
        print("record written; see summary.json")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
