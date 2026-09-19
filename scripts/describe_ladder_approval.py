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


#: The driver module cannot be imported here - this script runs on the bare
#: system python in the workflow's approval step, before the project
#: environment exists - so the allow-list is read out of its SOURCE instead of
#: duplicated. Duplication would drift, and a drifted copy asserting
#: "preconditioning only" is exactly the failure this check exists to prevent.
LADDER_DRIVER = Path(__file__).resolve().parent / "palace_order1_ladder.py"


def _allowed_override_keys(source: Path | None = None) -> set[str] | None:
    """The driver's ``_SOLVER_LINEAR_OVERRIDE_KEYS``, or ``None`` if unreadable."""
    import ast

    try:
        tree = ast.parse((source or LADDER_DRIVER).read_text())
    except (OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        targets = (
            [node.target] if isinstance(node, ast.AnnAssign)
            else node.targets if isinstance(node, ast.Assign)
            else []
        )
        if not any(
            isinstance(t, ast.Name) and t.id == "_SOLVER_LINEAR_OVERRIDE_KEYS" for t in targets
        ):
            continue
        value = node.value
        if isinstance(value, ast.Dict):
            keys = [k for k in value.keys if isinstance(k, ast.Constant)]
            if len(keys) == len(value.keys):
                return {k.value for k in keys}
        return None
    return None


def describe_approval(path: Path) -> str:
    approval = json.loads(path.read_text())
    lines = [f"level: {approval.get('level')}"]
    palace = approval.get("palace_refinement")
    if palace is not None:
        # This step is the human-visible record of what a run is about to spend.
        # Reading only port_refinement printed "none (plain ladder rung)" for a
        # Palace-refined run, which is the opposite of true.
        lines.append(f"refinement: {palace.get('id')} via Palace Model.Refinement.Boxes")
        lines.append("  mesh: the baseline's, REUSED byte-identically (gmsh does not run)")
        for box in palace.get("boxes") or []:
            lines.append(
                f"  box: Levels={box.get('Levels')}  "
                f"min={box.get('BoundingBoxMin')}  max={box.get('BoundingBoxMax')} (mm)"
            )
        lines.append(f"  baseline_record: {approval.get('baseline_record')}")
        sha = approval.get("baseline_mesh_sha256")
        lines.append(
            f"  mesh hash gate: ACTIVE against {sha[:16]}..." if sha
            else "  mesh hash gate: INACTIVE - no baseline_mesh_sha256"
        )
        lines.append("  DOF: not measurable offline; enforced by the probe on Palace's output")
        overrides = palace.get("solver_linear_overrides") or {}
        if overrides:
            # Without this line a run that changes the preconditioner reads
            # exactly like one that does not, in the only dump a human sees
            # before the solve is paid for.
            lines.append(
                "  Solver.Linear overrides: "
                + ", ".join(f"{k}={v!r}" for k, v in sorted(overrides.items()))
            )
            allowed = _allowed_override_keys()
            outside = [k for k in sorted(overrides) if k not in (allowed or ())]
            if allowed is None:
                # Never assert the property without having checked it: this dump
                # is what a human reads before a solve is paid for.
                lines.append(
                    "    NOT CHECKED: the driver's allow-list could not be read, so this dump "
                    "cannot say whether these keys are preconditioning-only"
                )
            elif outside:
                lines.append(
                    f"    *** OUTSIDE THE ALLOW-LIST: {outside} - these reach past "
                    f"preconditioning. The driver will REFUSE this approval before launching. ***"
                )
            else:
                lines.append(
                    "    preconditioning only (checked against the driver's allow-list "
                    f"{sorted(allowed)}); mesh, spaces, operators, Tol, MaxIts, KSPType "
                    "and the eigenvalue target are unchanged"
                )
        else:
            lines.append("  Solver.Linear overrides: none (baseline solver configuration)")
        return "\n".join(lines)
    refinement = approval.get("port_refinement")
    if refinement is None:
        lines.append("refinement: none (plain ladder rung)")
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
    refinement = rung.get("port_refinement") or rung.get("palace_refinement") or {}
    label = f"-{refinement['id']}" if refinement.get("id") else ""
    diagnostic = rung.get("port_diagnostic") or {}
    worst = diagnostic.get("worst_relative_disagreement_probe_vs_closure")
    worst_text = f"{worst:.2e}" if isinstance(worst, (int, float)) else "n/a"
    return (
        f"L{summary.get('level')}{label} {rung.get('status')}, "
        f"{rung.get('dof_solved') or rung.get('dof_measured')} DOF; probe-vs-closure {worst_text}"
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
