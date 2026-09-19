#!/usr/bin/env python
"""Offline checkpoint-A check of the coupled-candidate declaration.

    uv run python scripts/coupled_candidate_check.py [--declaration FILE] [--register FILE]
        [--results-root DIR] [--skip-mesh] [--levels "1 2 3"] [--dof-budget N] [--record-name NAME]

Steps (implementation-plan.md §4), none of which runs Palace or Docker:

1. validate the declaration (``qmhp-cem.coupled-candidate/0.2.0``) and the
   source register (``qmhp-cem.source-register/0.2.0``), resolving every
   SOURCE-BOUND source id — exit 2 on failure, nothing is written;
2. recompute every register digest — exit 3 on any mismatch (the record is
   still written so the mismatch is inspectable, without preview or mesh);
3. build the chip-cell geometry and write ``preview.json`` (every polygon in
   the spec §7.3 frame) and a deterministic ``preview.svg``;
4. unless ``--skip-mesh``, run the gmsh dry run at each ladder level, catching
   failures per level — exit 4 if every level failed;
5. write ``summary.json`` and ``report.md``, then ``manifest.sha256`` last,
   under ``results/COUPLED-CHECKPOINT-A-<UTC>/``.

Nothing this script writes is coupled EM evidence: it checks a declaration,
draws it and estimates a mesh. Every ENGINEERING-SEED in the declaration stays
unapproved.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import manifest  # noqa: E402
from contracts.coupled_candidate import (  # noqa: E402
    CoupledCandidateDeclaration,
    SourceRegister,
    load_declaration,
    load_register,
    sha256_of_declaration,
)

SUMMARY_SCHEMA = "qmhp-cem.coupled-checkpoint-a/0.2.0"
DEFAULT_DECLARATION = REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json"
DEFAULT_REGISTER = REPO_ROOT / "config" / "coupled" / "source_register.json"
DEFAULT_LEVELS = "1 2 3"
DEFAULT_DOF_BUDGET = 250_000

STATEMENT = (
    "Nothing in this record is coupled EM evidence: it validates a declaration, recomputes "
    "source digests, draws the declared seed geometry and estimates a mesh. No Palace solve "
    "was run. Every ENGINEERING-SEED remains unapproved."
)
SVG_TITLE = "PROPOSED ENGINEERING SEED — not approved"

EXIT_OK, EXIT_INVALID, EXIT_REGISTER, EXIT_DRY_RUN = 0, 2, 3, 4


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n"


# --- geometry preview ------------------------------------------------------------------

#: Fixed SVG scale: pixels per mm, and margin for the title, labels and scale bar.
_PX_PER_MM = 200.0
_MARGIN_PX = 60.0
_LABELLED = ("F1.island", "R1.coupling_pad", "P_F1", "P_R1")


def _fmt(v: float) -> str:
    """Fixed-precision number for byte-stable SVG output."""
    s = f"{v:.3f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _poly_points(poly: list[list[float]], x0: float, y1: float) -> str:
    # SVG y grows downward; the §7.3 frame has +Y up, so flip about the cell top.
    return " ".join(f"{_fmt((x - x0) * _PX_PER_MM)},{_fmt((y1 - y) * _PX_PER_MM)}" for x, y in poly)


def _centroid(polys: list[list[list[float]]]) -> tuple[float, float]:
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    return (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0


def render_preview_svg(preview: dict[str, Any]) -> str:
    """Deterministic SVG of the preview polygons: no timestamps, fixed viewBox.

    Ground plane grey, etch white, conductors black, ports red; labels for the
    island, the coupling pad and both ports; a 1 mm scale bar; the title
    states that the geometry is a proposed, unapproved engineering seed.
    """
    cell = preview["cell"]
    x0, x1, y0, y1 = cell["x_min_mm"], cell["x_max_mm"], cell["y_min_mm"], cell["y_max_mm"]
    w, h = (x1 - x0) * _PX_PER_MM, (y1 - y0) * _PX_PER_MM
    vb_w, vb_h = w + 2 * _MARGIN_PX, h + 2 * _MARGIN_PX
    conductors: dict[str, list] = preview.get("conductors", {}) or {}
    etch: list = preview.get("etch", []) or []
    ports: dict[str, list] = preview.get("ports", {}) or {}

    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(vb_w)} {_fmt(vb_h)}" '
        f'width="{_fmt(vb_w)}" height="{_fmt(vb_h)}" font-family="monospace">',
        f"<title>{SVG_TITLE}</title>",
        f'<rect x="0" y="0" width="{_fmt(vb_w)}" height="{_fmt(vb_h)}" fill="#ffffff"/>',
        f'<text x="{_fmt(_MARGIN_PX)}" y="{_fmt(_MARGIN_PX * 0.55)}" font-size="18" fill="#b00000">{SVG_TITLE}</text>',
        f'<text x="{_fmt(_MARGIN_PX)}" y="{_fmt(_MARGIN_PX * 0.85)}" font-size="11" fill="#333333">'
        f"chip cell {_fmt(x1 - x0)} x {_fmt(y1 - y0)} mm, z = 0 (chip top), spec 7.3 frame, +X right, +Y up; "
        f"ground plane grey, etch white, conductors black, ports red</text>",
        f'<g transform="translate({_fmt(_MARGIN_PX)},{_fmt(_MARGIN_PX)})">',
        f'<rect x="0" y="0" width="{_fmt(w)}" height="{_fmt(h)}" fill="#9a9a9a" stroke="#000000" stroke-width="1"/>',
    ]
    for poly in etch:
        lines.append(f'<polygon points="{_poly_points(poly, x0, y1)}" fill="#ffffff" stroke="none"/>')
    for cid in sorted(conductors):
        for poly in conductors[cid]:
            lines.append(f'<polygon points="{_poly_points(poly, x0, y1)}" fill="#000000" stroke="none"/>')
    for pid in sorted(ports):
        for poly in ports[pid]:
            lines.append(f'<polygon points="{_poly_points(poly, x0, y1)}" fill="#e00000" stroke="none"/>')
    for i, label in enumerate(_LABELLED):
        polys = conductors.get(label) or ports.get(label)
        if not polys:
            continue
        cx, cy = _centroid(polys)
        px, py = (cx - x0) * _PX_PER_MM, (y1 - cy) * _PX_PER_MM
        ty = py - 12.0 - 14.0 * (i % 2)
        lines.append(f'<line x1="{_fmt(px)}" y1="{_fmt(py)}" x2="{_fmt(px)}" y2="{_fmt(ty + 3)}" stroke="#0044cc" stroke-width="0.8"/>')
        lines.append(f'<text x="{_fmt(px + 3)}" y="{_fmt(ty)}" font-size="11" fill="#0044cc">{label}</text>')
    # scale bar: 1 mm at the lower left inside the cell
    bx, by = 10.0, h - 14.0
    lines.append(f'<line x1="{_fmt(bx)}" y1="{_fmt(by)}" x2="{_fmt(bx + _PX_PER_MM)}" y2="{_fmt(by)}" stroke="#000000" stroke-width="3"/>')
    lines.append(f'<text x="{_fmt(bx)}" y="{_fmt(by - 5)}" font-size="11" fill="#000000">1 mm</text>')
    lines.append("</g>")
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


# --- dry run --------------------------------------------------------------------------


def _find_dof(report: dict[str, Any], order: int) -> int | None:
    """Locate the MEASURED solver-space dimension for an element order.

    The dry run measures it from the mesh topology (edges and faces); it is
    not an estimate, and the estimated per-tetrahedron cross-check lives in
    the report's ``estimated`` block and is never read here.
    """
    measured = report.get("measured")
    if isinstance(measured, dict):
        key = f"dof_order{order}"
        if measured.get(key) is not None:
            return int(measured[key])
    key = f"dof_order{order}"
    if report.get(key) is not None:
        return int(report[key])
    for k, v in report.items():
        if "dof" in k.lower() and str(order) in k and isinstance(v, (int, float)):
            return int(v)
    return None


def _dry_run_one(cell: Any, level: int, out_dir: Path, dof_budget: int) -> dict[str, Any]:
    """One mesh dry run, as a plain dict."""
    from solvers.palace.coupled_mesh import dry_run

    return dry_run(cell, level, out_dir, dof_budget=dof_budget).as_dict()


def dry_run_levels(cell: Any, levels: list[int], out_root: Path, dof_budget: int) -> dict[str, dict[str, Any]]:
    """Run the mesh dry run per level, recording an error instead of raising."""
    from solvers.palace.coupled_mesh import dry_run

    out: dict[str, dict[str, Any]] = {}
    for level in levels:
        out_dir = out_root / f"L{level}"
        try:
            report = dry_run(cell, level, out_dir, dof_budget=dof_budget)
            out[f"L{level}"] = {"status": "OK", "report": report.as_dict()}
        except Exception as exc:  # noqa: BLE001 - recorded per level, never fatal here
            out[f"L{level}"] = {"status": "ERROR", "error": f"{exc.__class__.__name__}: {exc}", "traceback": traceback.format_exc()}
    return out


def disposition_input(dry: dict[str, dict[str, Any]], dof_budget: int) -> dict[str, Any]:
    """Per level: order-2 / order-1 DOF estimates against the budget (numerical-plan.md §6)."""
    levels: dict[str, Any] = {}
    for name, entry in dry.items():
        if entry.get("status") != "OK":
            levels[name] = {"status": "ERROR", "dof_order2": None, "dof_order1": None,
                            "within_budget_order2": None, "within_budget_order1": None}
            continue
        rep = entry["report"]
        d2, d1 = _find_dof(rep, 2), _find_dof(rep, 1)
        levels[name] = {
            "status": "OK",
            "dof_order2": d2,
            "dof_order1": d1,
            "within_budget_order2": (d2 <= dof_budget) if d2 is not None else None,
            "within_budget_order1": (d1 <= dof_budget) if d1 is not None else None,
        }
    ok = [v for v in levels.values() if v["status"] == "OK"]
    return {
        "dof_budget": dof_budget,
        "levels": levels,
        "all_levels_within_budget_order2": bool(ok) and all(v["within_budget_order2"] for v in ok),
        "all_levels_within_budget_order1": bool(ok) and all(v["within_budget_order1"] for v in ok),
        "rule": "order 2 preferred; order 1 only if the finest level exceeds the budget with order 2 (numerical-plan.md §3)",
    }


# --- report -----------------------------------------------------------------------------


def render_report(summary: dict[str, Any]) -> str:
    s = summary
    lines = [
        "# Coupled candidate checkpoint A: offline check",
        "",
        f"Record `{s['batch_id']}`. {STATEMENT}",
        "",
        "| item | value |",
        "|---|---|",
        f"| declaration | `{s['declaration']['path']}` sha256 `{s['declaration']['sha256']}` |",
        f"| declaration id | {s['declaration'].get('declaration_id')} |",
        f"| register | `{s['register']['path']}` sha256 `{s['register']['sha256']}` |",
        f"| declaration valid | {s['validation']['ok']} |",
        f"| register verified | {s['register']['ok']} ({len(s['register']['mismatches'])} mismatches) |",
        f"| preview | {s['preview'].get('svg') or 'not written'} |",
        f"| mesh dry run | {s['dry_run_mode']} |",
        f"| admission disposition | {s.get('admission_disposition', s['disposition'])} |",
        f"| execution disposition | {s.get('execution_disposition', 'NOT-MEASURED')} |",
        "",
    ]
    if s["register"]["mismatches"]:
        lines += ["## Register mismatches", ""] + [f"- {m}" for m in s["register"]["mismatch_text"]] + [""]
    if s.get("clearance_report"):
        lines += ["## Clearance report", ""] + [f"- {m}" for m in s["clearance_report"]] + [""]
    di = s.get("disposition_input")
    if di:
        lines += ["## Mesh dry run against the DOF budget", "",
                  f"DOF budget {di['dof_budget']} (numerical-plan.md §6). Mesh counts and the "
                  "solver-space dimensions below are MEASURED: the dimension of MFEM's Nedelec "
                  "space on tetrahedra is fixed by the mesh topology (edges for order 1, "
                  "2*edges + 2*faces for order 2), checked against Palace's own reported "
                  "DegreesOfFreedom on the committed golden record. No solver size here is "
                  "extrapolated from a per-tetrahedron ratio.", "",
                  "| level | status | DOF order 2 | within budget | DOF order 1 | within budget |",
                  "|---|---|---|---|---|---|"]
        for name, v in di["levels"].items():
            lines.append(f"| {name} | {v['status']} | {v['dof_order2']} | {v['within_budget_order2']} | "
                         f"{v['dof_order1']} | {v['within_budget_order1']} |")
        lines.append("")
        for name, entry in s["dry_run"].items():
            if entry.get("status") == "ERROR":
                lines.append(f"- {name}: {entry['error']}")
        lines.append("")
    sens = s.get("sensitivity")
    if sens:
        lines += ["## Sensitivity probe (UNADOPTED)", "", sens["statement"], "",
                  "| variant | changes | tets | DOF order 2 | DOF order 1 |", "|---|---|---|---|---|"]
        for name, entry in sens["variants"].items():
            if entry["status"] == "OK":
                rep = entry["report"]
                lines.append(
                    f"| {name} | {entry['changes']} | {rep.get('measured', {}).get('tetrahedra')} | "
                    f"{_find_dof(rep, 2)} | {_find_dof(rep, 1)} |"
                )
            else:
                lines.append(f"| {name} | {entry['changes']} | - | - | {entry['error']} |")
        lines.append("")
    lines += ["## Statement", "", STATEMENT, ""]
    return "\n".join(lines)


# --- main --------------------------------------------------------------------------------


def _admission_disposition(summary: dict[str, Any]) -> str:
    """Is the checkpoint-A package itself admissible for review?

    This is about the declaration, its sources and its geometry, not about
    whether the declared mesh ladder fits the runner: that is
    :func:`_execution_disposition`, and the two are reported separately so a
    compute limit is never read as an invalid candidate, nor the reverse.
    """
    if not summary["validation"]["ok"]:
        return "BLOCKED: declaration invalid"
    if not summary["register"]["ok"]:
        return "BLOCKED: source register mismatch"
    if summary.get("clearance_report"):
        return "BLOCKED: geometry clearance violation"
    return "READY-FOR-REVIEW: declaration valid, sources verified, geometry consistent"


def _execution_disposition(summary: dict[str, Any]) -> str:
    """Does the declared mesh ladder fit the declared compute budget?"""
    if summary["dry_run_mode"] == "skipped":
        return "NOT-MEASURED (mesh dry run skipped)"
    di = summary["disposition_input"]
    if all(v["status"] != "OK" for v in di["levels"].values()):
        return "BLOCKED: mesh dry run failed at every level"
    if di["all_levels_within_budget_order2"]:
        return "READY: ladder fits the DOF budget at order 2"
    if di["all_levels_within_budget_order1"]:
        return "READY: ladder fits the DOF budget at order 1 only"
    return "BLOCKED: ladder exceeds the DOF budget"


def _disposition(summary: dict[str, Any]) -> str:
    """The one-line disposition: admission first, then execution."""
    admission = _admission_disposition(summary)
    if admission.startswith("BLOCKED"):
        return admission
    execution = _execution_disposition(summary)
    if summary["dry_run_mode"] == "skipped":
        return "READY-FOR-REVIEW (mesh dry run skipped)"
    if execution.startswith("BLOCKED"):
        return f"READY-FOR-REVIEW (admission); EXECUTION {execution}"
    return f"READY-FOR-REVIEW (admission); EXECUTION {execution}"


#: Bounded variants probed by ``--sensitivity``. Each entry is a name, a
#: one-line statement of what it changes, and a mutation of the declaration
#: dict. NONE of them is adopted by this checkpoint: they are measurements
#: that tell a reviewer which declared seed drives the mesh cost. Changing
#: the declaration is a human decision.
SENSITIVITY_VARIANTS: list[tuple[str, str, Any]] = [
    ("cell_2mm", "cell 2 x 2 mm instead of 4 x 4 mm; everything else as declared",
     lambda d: d["geometry"]["cell"].update({"x_min_mm": -1.0, "x_max_mm": 1.0, "y_min_mm": -1.0, "y_max_mm": 1.0})),
    ("coupling_gap_40um", "coupling gap 40 um instead of 20 um (the narrowest gap sets the mesh)",
     lambda d: _set_feature(d, "R1.coupling_pad", "gap_to_island_mm", 0.040)),
    ("coupling_gap_40um_cell_2mm", "both of the above together",
     lambda d: (_set_feature(d, "R1.coupling_pad", "gap_to_island_mm", 0.040),
                d["geometry"]["cell"].update({"x_min_mm": -1.0, "x_max_mm": 1.0, "y_min_mm": -1.0, "y_max_mm": 1.0}))),
]


def _set_feature(decl: dict[str, Any], feature_id: str, key: str, value: Any) -> None:
    for f in decl["geometry"]["features"]:
        if f["id"] == feature_id:
            f[key] = value
            return
    raise KeyError(feature_id)


def sensitivity_probe(declaration_dict: dict[str, Any], out_dir: Path, dof_budget: int) -> dict[str, Any]:
    """Level-1 dry runs of bounded, UNADOPTED variants of the declared seed."""
    import copy

    from solvers.palace.coupled_geometry import chip_cell_from_declaration

    out: dict[str, Any] = {
        "statement": (
            "Unadopted measurements. Each row is the declared candidate with one seed changed, meshed at level 1 "
            "only, to show what drives the mesh cost. No variant is part of the declaration; adopting one is a "
            "human decision that would change config/coupled/v2a_five_node_candidate.json and its record."
        ),
        "dof_budget": dof_budget,
        "variants": {},
    }
    for name, what, mutate in SENSITIVITY_VARIANTS:
        d = copy.deepcopy(declaration_dict)
        entry: dict[str, Any] = {"changes": what}
        try:
            mutate(d)
            cell = chip_cell_from_declaration(d)
            report = _dry_run_one(cell, 1, out_dir / name, dof_budget)
            entry.update({"status": "OK", "clearance_report": list(cell.clearance_report()), "report": report})
        except Exception as exc:  # noqa: BLE001 - a variant that cannot be built is a result
            entry.update({"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"})
        out["variants"][name] = entry
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--declaration", default=str(DEFAULT_DECLARATION))
    parser.add_argument("--register", default=str(DEFAULT_REGISTER))
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="root the register paths are relative to")
    parser.add_argument("--results-root", default=str(REPO_ROOT / "results"))
    parser.add_argument("--skip-mesh", action="store_true", help="do not run the gmsh dry run")
    parser.add_argument("--levels", default=DEFAULT_LEVELS, help="ladder levels, space separated")
    parser.add_argument("--dof-budget", type=int, default=DEFAULT_DOF_BUDGET)
    parser.add_argument("--record-name", default=None, help="record directory name (default COUPLED-CHECKPOINT-A-<UTC>)")
    parser.add_argument(
        "--sensitivity",
        action="store_true",
        help=(
            "also mesh a few bounded variants of the declared seed at level 1 and record their DOF estimates. "
            "The variants are NOT adopted: they exist so that a BLOCKED disposition names what drives the cost."
        ),
    )
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc)
    decl_path, reg_path = Path(args.declaration), Path(args.register)
    levels = [int(x) for x in args.levels.split()]

    # 1. validation (exit 2, nothing written)
    try:
        register: SourceRegister = load_register(reg_path)
        declaration: CoupledCandidateDeclaration = load_declaration(decl_path, register=register)
    except Exception as exc:  # noqa: BLE001 - pydantic ValidationError, ValueError, OSError
        print(f"error: declaration or register invalid\n{exc}", file=sys.stderr)
        return EXIT_INVALID

    batch = args.record_name or f"COUPLED-CHECKPOINT-A-{started.strftime('%Y%m%dT%H%M%SZ')}"
    root = Path(args.results_root) / batch
    root.mkdir(parents=True, exist_ok=False)

    # 2. register digests
    mismatches = register.verify(Path(args.repo_root))
    summary: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "batch_id": batch,
        "started_utc": started.isoformat(),
        "declaration": {"path": str(decl_path), "sha256": sha256_of_declaration(decl_path),
                        "declaration_id": declaration.declaration_id, "schema": declaration.schema_,
                        "status": declaration.status},
        "register": {"path": str(reg_path), "sha256": sha256_of_declaration(reg_path), "ok": not mismatches,
                     "mismatches": [{"path": m.path, "expected": m.expected, "actual": m.actual} for m in mismatches],
                     "mismatch_text": [str(m) for m in mismatches]},
        "validation": {"ok": True, "source_ids": sorted(declaration.source_ids()),
                       "unapproved_seeds": sum(1 for _, b in declaration.bindings() if b.class_ == "ENGINEERING-SEED"),
                       "unbound": sum(1 for _, b in declaration.bindings() if b.class_ == "UNBOUND")},
        "preview": {},
        "clearance_report": [],
        "dry_run_mode": "skipped" if args.skip_mesh else "gmsh",
        "dry_run": {},
        "disposition_input": None,
        "sensitivity": None,
        "dof_budget": args.dof_budget,
        "levels": levels,
        "statement": STATEMENT,
    }

    def write_record() -> None:
        summary["ended_utc"] = datetime.now(timezone.utc).isoformat()
        summary["admission_disposition"] = _admission_disposition(summary)
        summary["execution_disposition"] = _execution_disposition(summary)
        summary["disposition"] = _disposition(summary)
        (root / "summary.json").write_text(_dump(summary))
        (root / "report.md").write_text(render_report(summary))
        manifest.write(root)  # always last
        print(f"record     : {root}\ndisposition: {summary['disposition']}")

    if mismatches:
        print("error: source register mismatch(es):", file=sys.stderr)
        for m in mismatches:
            print(f"  - {m}", file=sys.stderr)
        write_record()
        return EXIT_REGISTER

    # 3. geometry preview
    from solvers.palace.coupled_geometry import chip_cell_from_declaration

    cell = chip_cell_from_declaration(declaration.to_ordered_dict())
    preview = cell.preview_polygons()
    (root / "preview.json").write_text(_dump(preview))
    (root / "preview.svg").write_text(render_preview_svg(preview))
    summary["preview"] = {
        "json": "preview.json", "svg": "preview.svg",
        "json_sha256": manifest.file_digest(root / "preview.json"),
        "svg_sha256": manifest.file_digest(root / "preview.svg"),
    }
    summary["clearance_report"] = list(cell.clearance_report())

    # 4. mesh dry run
    if not args.skip_mesh:
        summary["dry_run"] = dry_run_levels(cell, levels, root / "dry_run", args.dof_budget)
        summary["disposition_input"] = disposition_input(summary["dry_run"], args.dof_budget)
        for name, entry in summary["dry_run"].items():
            if entry["status"] == "OK":
                di = summary["disposition_input"]["levels"][name]
                print(f"  {name}: DOF order 2 {di['dof_order2']}, order 1 {di['dof_order1']} "
                      f"(budget {args.dof_budget})")
            else:
                print(f"  {name}: ERROR {entry['error']}")

        if args.sensitivity:
            summary["sensitivity"] = sensitivity_probe(
                declaration.to_ordered_dict(), root / "sensitivity", args.dof_budget
            )
            for name, entry in summary["sensitivity"]["variants"].items():
                if entry["status"] == "OK":
                    rep = entry["report"]
                    print(f"  sensitivity {name}: DOF order 2 {_find_dof(rep, 2)}, order 1 {_find_dof(rep, 1)}")
                else:
                    print(f"  sensitivity {name}: {entry['error']}")

    # 5. record
    write_record()
    if not args.skip_mesh and all(e["status"] != "OK" for e in summary["dry_run"].values()):
        return EXIT_DRY_RUN
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
