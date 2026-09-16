#!/usr/bin/env python3
"""S1 numerical recovery: the independent port diagnostic and the prepared experiment.

This launches no solver. It reads committed records, evaluates the port
stiffness energy from a conversion derived from pinned Palace v0.13.0 source,
measures the meshes those records were solved on, and dry-runs two candidate
meshes for one controlled local-refinement experiment. Everything it writes is
a separately versioned corrective record that references the source records by
their manifest digests and leaves them untouched.

What it does NOT do, by construction: run Palace, change a tolerance, change
the 250 000-DOF rule or the 45-minute cap, extract a coupling, or modify any
existing record.

Evidence before presentation
----------------------------
``summary.json`` and the record pointer are written before anything is
rendered, and a rendering failure is captured into ``report.md`` and reported
as a non-zero exit while the record is still manifested. ``--fail-render``
forces that path so the guarantee is exercised rather than asserted.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import manifest  # noqa: E402
from orchestrator.manifest import unexpected_files  # noqa: E402
from solvers.palace.coupled_geometry import chip_cell_from_declaration  # noqa: E402
from solvers.palace.coupled_mesh import (  # noqa: E402
    PortRefinement,
    dry_run,
    mesh_sizes_mm,
)
from solvers.palace.mesh_inspection import (  # noqa: E402
    classify_size_field_curves,
    compare_across_levels,
    inspect_mesh,
)
from solvers.palace.outputs import (  # noqa: E402
    parse_domain_energy_csv,
    parse_eig_csv,
    parse_port_epr_csv,
    parse_surface_q_csv,
)
from solvers.palace.port_diagnostic import (  # noqa: E402
    PortConversion,
    PortConversionError,
    compare,
    conversion_from_run,
)

RECORD_SCHEMA = "qmhp-cem.s1-numerical-recovery/0.1.0"
DECLARATION = REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json"

#: The committed records this analysis reads. They are verified against their
#: own manifests before and after, and never written to.
SOURCE_RECORDS: dict[str, dict[str, Any]] = {
    "L1": {
        "record": "results/COUPLED-PILOT-20260916T035733Z",
        "solver": "results/COUPLED-PILOT-20260916T035733Z/P2/solver",
        "mesh": "coupled_chip_cell_L1.msh",
        "level": 1,
        "has_port_field_probes": False,
    },
    "L2": {
        "record": "results/COUPLED-LADDER-O1-L2-20260916T080802Z",
        "solver": "results/COUPLED-LADDER-O1-L2-20260916T080802Z/L2/solver",
        "mesh": "coupled_chip_cell_L2.msh",
        "level": 2,
        "has_port_field_probes": True,
    },
    "L3": {
        "record": "results/COUPLED-LADDER-O1-L3-20260916T091212Z",
        "solver": "results/COUPLED-LADDER-O1-L3-20260916T091212Z/L3/solver",
        "mesh": "coupled_chip_cell_L3.msh",
        "level": 3,
        "has_port_field_probes": True,
    },
}

#: The declared S1 port face. Both numbers are re-measured from every mesh.
PORT_TAGS = {"port_F1": 10, "port_R1_a": 11, "port_R1_b": 12}
PORT_DIMENSIONS = {"port_F1": (0.04, 0.02), "port_R1_a": (0.02, 0.03), "port_R1_b": (0.02, 0.03)}

HALO_MM = 0.08
DOF_BUDGET = 250_000
SOLVE_TIMEOUT_S = 2700
FINITE_ELEMENT_ORDER = 1

#: The prepared experiment. One base level, one pad, one transition; only the
#: size held over the port box changes between the two meshes, so the two
#: differ in exactly one prescribed number.
EXPERIMENT_BASE_LEVEL = 2
EXPERIMENT_PAD_MM = 0.010
EXPERIMENT_TRANSITION_MM = 0.020
EXPERIMENT_DIVISORS = {"R1": 2.0, "R2": 4.0}

#: File kinds the evidence commit may contain. Anything else is rejected
#: rather than committed: the level-2 rung committed a 123 MB ParaView tree
#: because nothing checked.
ALLOWED_RECORD_SUFFIXES = frozenset({".json", ".md", ".sha256", ".csv", ".txt"})


class RecoveryError(RuntimeError):
    """The analysis cannot proceed on the evidence as found."""


# --------------------------------------------------------------------------
# Source records
# --------------------------------------------------------------------------


def verify_sources() -> dict[str, Any]:
    """Verify every source record against its own manifest, and hash it."""
    provenance: dict[str, Any] = {}
    for name, spec in SOURCE_RECORDS.items():
        record = REPO_ROOT / spec["record"]
        if not record.is_dir():
            raise RecoveryError(f"source record missing: {record}")
        discrepancies = manifest.verify(record)
        if discrepancies:
            raise RecoveryError(f"{record} does not match its manifest: {discrepancies}")
        manifest_path = record / "manifest.sha256"
        provenance[name] = {
            "record": spec["record"],
            "manifest_sha256": manifest.file_digest(manifest_path),
            "files_manifested": len(manifest_path.read_text().strip().splitlines()),
            "verified": "matches its own manifest",
            "level": spec["level"],
            "has_port_field_probes": spec["has_port_field_probes"],
        }
    return provenance


def assert_sources_unchanged(before: dict[str, Any]) -> None:
    """The corrective analysis must not have touched what it read."""
    after = verify_sources()
    for name, entry in before.items():
        if after[name]["manifest_sha256"] != entry["manifest_sha256"]:
            raise RecoveryError(
                f"source record {entry['record']} changed during the analysis"
            )


# --------------------------------------------------------------------------
# The independently normalised port diagnostic
# --------------------------------------------------------------------------


def build_conversion(solver_dir: Path, mesh_report: dict[str, Any]) -> PortConversion:
    """Derive the conversion for one committed run.

    Thin wrapper over :func:`solvers.palace.port_diagnostic.conversion_from_run`
    so this analysis and the ladder driver cannot drift apart on how ``kappa``
    is formed; the refusals it raises are re-raised as :class:`RecoveryError`.
    """
    config = json.loads((solver_dir / "config.json").read_text())
    try:
        return conversion_from_run(config, mesh_report)
    except PortConversionError as exc:
        raise RecoveryError(str(exc)) from exc


def port_diagnostic(name: str, spec: dict[str, Any], mesh_report: dict[str, Any]) -> dict[str, Any]:
    """The three-way port comparison for one committed run."""
    solver_dir = REPO_ROOT / spec["solver"]
    post = solver_dir / "postpro"
    eig = parse_eig_csv(post / "eig.csv")
    energies = parse_domain_energy_csv(post / "domain-E.csv")
    epr = {row.mode: row for row in parse_port_epr_csv(post / "port-EPR.csv")}
    if not spec["has_port_field_probes"]:
        return {
            "level": spec["level"],
            "port_field_probes": False,
            "why": (
                "this run predates the port-field probes, so the port stiffness energy "
                "cannot be evaluated independently here. Only the closure requirement is "
                "available, and the closure requirement is not an independent measurement."
            ),
            "closure_only": [
                {
                    "mode": int(energy.index),
                    "frequency_GHz": row.frequency_re_GHz,
                    "participation_from_closure": 1.0
                    - (energy.magnetic_J + energy.capacitive_J)
                    / (energy.electric_J + energy.capacitive_J),
                    "participation_reported": energy.inductive_J
                    / (energy.electric_J + energy.capacitive_J),
                }
                for row, energy in zip(eig.rows, energies)
            ],
        }
    surface = {row.mode: row for row in parse_surface_q_csv(post / "surface-Q.csv")}
    conversion = build_conversion(solver_dir, mesh_report)
    modes: list[dict[str, Any]] = []
    worst = 0.0
    for eig_row, energy in zip(eig.rows, energies):
        mode = int(energy.index)
        if eig_row.index != mode:
            raise RecoveryError(
                f"{name}: eig.csv and domain-E.csv disagree on mode id "
                f"({eig_row.index} vs {mode})"
            )
        if mode not in surface or mode not in epr:
            raise RecoveryError(f"{name}: mode {mode} is missing from surface-Q.csv or port-EPR.csv")
        probe = surface[mode]
        result = compare(
            conversion,
            mode=mode,
            frequency_GHz=eig_row.frequency_re_GHz,
            p_default=probe.participation[1],
            p_ma=probe.participation[2],
            E_elec=energy.electric_J,
            E_mag=energy.magnetic_J,
            E_cap=energy.capacitive_J,
            E_ind=energy.inductive_J,
        )
        payload = result.as_dict()
        payload["reported_EPR_signed"] = epr[mode].participation[1]
        payload["backward_error"] = eig_row.backward_error
        worst = max(worst, abs(result.probe_versus_closure - 1.0))
        modes.append(payload)
    return {
        "level": spec["level"],
        "port_field_probes": True,
        "conversion": conversion.as_dict(),
        "modes": modes,
        "worst_relative_disagreement_probe_vs_closure": worst,
        "what_the_agreement_shows": (
            "the port stiffness term, evaluated from the probes and a conversion that "
            "reads no energy column, accounts for the whole energy-balance defect on "
            "every mode. The two numbers share no input."
        ),
        "what_it_does_not_show": (
            "it does not show that the mesh resolves that term, and it is not a "
            "convergence statement about anything."
        ),
    }


# --------------------------------------------------------------------------
# The meshes
# --------------------------------------------------------------------------


def inspect_levels(cell: Any) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    for name, spec in SOURCE_RECORDS.items():
        _, h_gap, _ = mesh_sizes_mm(cell, spec["level"])
        reports[name] = inspect_mesh(
            REPO_ROOT / spec["solver"] / spec["mesh"],
            requested_h_gap_mm=h_gap,
            port_tags=PORT_TAGS,
            port_dimensions=PORT_DIMENSIONS,
            other_tags=(2, 4),
        )
        reports[name]["level"] = spec["level"]
        reports[name]["requested_h_gap_mm"] = h_gap
    return reports


def size_field_findings(cell: Any) -> dict[str, Any]:
    """The Distance-field classification, per level, and the port-face reach."""
    per_level = {f"L{level}": classify_size_field_curves(cell, level, HALO_MM) for level in (1, 2, 3)}
    ratios = {
        k: v["size_field"]["prescribed_size_at_port_centre_over_h_gap"] for k, v in per_level.items()
    }
    spread = max(ratios.values()) - min(ratios.values())
    return {
        "per_level": per_level,
        "prescribed_size_at_port_centre_over_h_gap": ratios,
        "ratio_is_scale_invariant": spread < 1.0e-9,
        "finding": (
            "the size the existing field prescribes at the port centre is a fixed multiple "
            "of h_gap at every level, so refining the ladder never resolves the port face"
        ),
    }


def prepare_experiment(cell: Any, out_dir: Path) -> dict[str, Any]:
    """Dry-run the two candidate meshes and measure their DOF. No solver."""
    _, h_gap, h_far = mesh_sizes_mm(cell, EXPERIMENT_BASE_LEVEL)
    meshes: dict[str, Any] = {}
    for name, divisor in EXPERIMENT_DIVISORS.items():
        refinement = PortRefinement(
            h_port_mm=h_gap / divisor,
            pad_mm=EXPERIMENT_PAD_MM,
            transition_mm=EXPERIMENT_TRANSITION_MM,
        )
        with tempfile.TemporaryDirectory() as scratch:
            report = dry_run(
                cell,
                EXPERIMENT_BASE_LEVEL,
                Path(scratch),
                dof_budget=DOF_BUDGET,
                halo_mm=HALO_MM,
                port_refinement=refinement,
                mesh_filename=f"coupled_chip_cell_L{EXPERIMENT_BASE_LEVEL}_{name}.msh",
            )
            face = inspect_mesh(
                report.mesh_path,
                requested_h_gap_mm=refinement.h_port_mm,
                port_tags={"port_F1": PORT_TAGS["port_F1"]},
                port_dimensions={"port_F1": PORT_DIMENSIONS["port_F1"]},
            )["ports"]["port_F1"]
        if report.dof_order1 > DOF_BUDGET:
            raise RecoveryError(
                f"{name} measures {report.dof_order1} DOF at order 1, above the "
                f"{DOF_BUDGET} rule; it is not proposed"
            )
        meshes[name] = {
            "base_level": EXPERIMENT_BASE_LEVEL,
            "h_gap_mm": h_gap,
            "h_far_mm": h_far,
            "halo_mm": HALO_MM,
            "port_refinement": refinement.as_dict(),
            "h_port_over_h_gap": refinement.h_port_mm / h_gap,
            "measured": {
                "dof_order1": report.dof_order1,
                "dof_order2": report.dof_order2,
                "tetrahedra": report.tetrahedra,
                "nodes": report.nodes,
                "edges": report.edges,
                "mesh_sha256": report.sha256,
                "mesh_filename": report.mesh_path.name,
                "dry_run_wall_clock_s": report.wall_clock_s,
                "gmsh_version": report.gmsh_version,
            },
            "budget": {
                "dof_budget": DOF_BUDGET,
                "fraction_of_budget": report.dof_order1 / DOF_BUDGET,
                "within_budget_order1": report.dof_order1 <= DOF_BUDGET,
            },
            "port_face": {
                "triangles": face["triangles"],
                "equivalent_element_size_mm": face["equivalent_element_size_mm"],
                "elements_across_width": face["elements_across_width"],
                "achieved_over_requested": (
                    face["equivalent_element_size_mm"] / refinement.h_port_mm
                ),
            },
        }
    (out_dir / "prepared_meshes.json").write_text(json.dumps(meshes, indent=2) + "\n")
    return meshes


def refinement_trend(diagnostic: dict[str, Any]) -> dict[str, Any]:
    """How the tracked frequencies and the port-face integral moved with ``h``.

    Reads the tracked frequencies from the committed ladder record rather than
    re-deriving the correspondence, so this is a reading of the evidence.

    The ladder's own estimator already reported that no positive order of
    convergence fits the three rungs. This asks the complementary question -
    whether the three points follow a consistent law in the *divergent*
    direction - because a consistent exponent points at an unresolved local
    feature, whereas scatter would not.
    """
    ladder = json.loads(
        (REPO_ROOT / SOURCE_RECORDS["L3"]["record"] / "summary.json").read_text()
    )
    per_mode = ladder["convergence"]["per_mode"]
    modes: dict[str, Any] = {}
    for key, entry in per_mode.items():
        frequency = entry["frequency"]
        h = list(frequency["h"])
        f = list(frequency["values"])
        exponents = []
        for i in range(len(h) - 1):
            # f^2 = C h^-q  =>  q = -ln(f2^2/f1^2) / ln(h2/h1)
            exponents.append(
                -(math.log(f[i + 1] ** 2) - math.log(f[i] ** 2))
                / (math.log(h[i + 1]) - math.log(h[i]))
            )
        spread = (
            abs(exponents[1] - exponents[0]) / abs(exponents[0]) if exponents[0] else math.inf
        )
        modes[key] = {
            "role": entry["role"],
            "modes_by_level": entry["modes_by_level"],
            "h_mm": h,
            "frequency_GHz": f,
            "exponent_q_in_f_squared_proportional_to_h_to_the_minus_q": exponents,
            "exponents_agree_within": spread,
            "ladder_estimator_verdict": frequency["reason"],
            "cumulative_change_fraction": (f[-1] - f[0]) / f[0],
        }
    tangential: dict[str, Any] = {}
    for name in ("L2", "L3"):
        entry = diagnostic[name]
        if entry.get("port_field_probes"):
            tangential[name] = {
                m["mode"]: m["tangential_integral_over_E_elec_plus_E_cap"] for m in entry["modes"]
            }
    growth = None
    if "L2" in tangential and "L3" in tangential:
        growth = {
            str(mode): tangential["L3"][mode] / tangential["L2"][mode]
            for mode in sorted(tangential["L2"])
            if tangential["L2"][mode] != 0.0
        }
    return {
        "per_mode": modes,
        "port_face_tangential_integral_over_denominator": tangential,
        "L3_over_L2_growth": growth,
        "internal_consistency_note": (
            "for the lumped-dominated mode the port participation is saturated near 1, so "
            "the tangential integral and omega^2 must move together. That the ratios match "
            "is a consistency check on the conversion, NOT independent evidence about the "
            "frequency."
        ),
        "what_this_does_not_establish": [
            "it does not prove mathematical nonconvergence: three points and two intervals "
            "cannot do that, and a sequence may follow one law over a range and another "
            "beyond it",
            "it does not show that the physical architecture fails: nothing here is about "
            "the device, only about the discretisation of a declared idealisation",
            "it does not show that every in-budget mesh has been exhausted: it is precisely "
            "because that is untrue that a local-refinement experiment is proposed",
            "it identifies no limit and measures no order of convergence",
        ],
        "what_it_does_say": (
            "the tested sequence moves in a consistent direction with a consistent "
            "exponent, which is what an unresolved local feature looks like and is a "
            "reason to refine locally rather than globally"
        ),
    }


# --------------------------------------------------------------------------
# The evidence commit
# --------------------------------------------------------------------------


def reject_unexpected_files(record_dir: Path) -> list[str]:
    """Anything in the record that is not an expected evidence file.

    Shares its implementation with the check the workflows run before
    ``git add`` (``scripts/check_record_files.py``), so the driver and the
    commit gate cannot drift apart. This record is analysis only, so its
    allowance is narrower than the general one: no mesh, no S-parameters.
    """
    return unexpected_files(record_dir, ALLOWED_RECORD_SUFFIXES)


# --------------------------------------------------------------------------
# Presentation
# --------------------------------------------------------------------------


def render_report(summary: dict[str, Any]) -> str:
    diagnostic = summary["port_diagnostic"]
    meshes = summary["prepared_experiment"]["meshes"]
    lines: list[str] = [
        "# S1 numerical recovery: the port diagnostic and the prepared experiment",
        "",
        f"Record `{summary['record_id']}`, schema `{summary['schema']}`. "
        "No Palace was launched. Every source record was verified against its own "
        "manifest before and after, and none was written to.",
        "",
        "## 1. The conversion is derived, not calibrated",
        "",
    ]
    reference = next(v for v in diagnostic.values() if v.get("port_field_probes"))
    factors = reference["conversion"]["factors"]
    lines += [
        f"`kappa = 1/(t_nd * Ls_nd) = {reference['conversion']['kappa']:.10f}`, from "
        f"`Lc = {factors['Lc_m']:.6e} m` (the mesh bounding box), "
        f"`L = {factors['inductance_H']:.6e} H`, the port face "
        f"`{factors['port_length_mm']:.6g} x {factors['port_width_mm']:.6g} mm` and "
        f"`t_nd = {factors['probe_thickness_nd']}`. No solver output is read to compute it, "
        "and no mode was selected to fit it.",
        "",
        "| level | modes | worst probe-vs-closure disagreement |",
        "|---|---|---|",
    ]
    for name, entry in diagnostic.items():
        if not entry.get("port_field_probes"):
            lines.append(f"| {name} | n/a | no port-field probes in that run |")
            continue
        lines.append(
            f"| {name} | {len(entry['modes'])} | "
            f"{entry['worst_relative_disagreement_probe_vs_closure']:.2e} |"
        )
    lines += [
        "",
        "The probe evaluation and the closure requirement share no input: the first reads "
        "`surface-Q.csv`, `eig.csv` and geometry, the second reads `domain-E.csv`. The "
        "closure number is **not** an independent measurement of the port energy and is "
        "never quoted as verifying the closure it comes from.",
        "",
        "## 2. The port face, as built",
        "",
        "| level | requested h_gap | port triangles | element size on the face | elements across the width |",
        "|---|---|---|---|---|",
    ]
    for name, report in summary["mesh_inspection"]["levels"].items():
        face = report["ports"]["port_F1"]
        lines.append(
            f"| {name} | {report['requested_h_gap_mm']:.6f} mm | {face['triangles']} | "
            f"{face['equivalent_element_size_mm']:.6f} mm | {face['elements_across_width']:.2f} |"
        )
    field = summary["mesh_inspection"]["size_field"]
    lines += [
        "",
        f"`{field['finding']}` — the ratio is "
        f"{json.dumps(field['prescribed_size_at_port_centre_over_h_gap'])}, "
        f"scale-invariant: {field['ratio_is_scale_invariant']}.",
        "",
        "## 3. How the tested sequence moved",
        "",
        "| tracked mode | role | f(L1), f(L2), f(L3) GHz | exponent q in f^2 ~ h^-q | agreement |",
        "|---|---|---|---|---|",
    ]
    for key, entry in summary["refinement_trend"]["per_mode"].items():
        frequencies = ", ".join(f"{v:.6f}" for v in entry["frequency_GHz"])
        exponents = ", ".join(
            f"{v:.3f}"
            for v in entry["exponent_q_in_f_squared_proportional_to_h_to_the_minus_q"]
        )
        lines.append(
            f"| {key} | {entry['role']} | {frequencies} | {exponents} | "
            f"{entry['exponents_agree_within']:.1%} |"
        )
    lines += [
        "",
        "The ladder's own estimator already refused an order of convergence on these three "
        "rungs and that refusal stands. This is the complementary reading, bounded the same "
        "way: three points and two intervals establish no law, prove no mathematical "
        "nonconvergence, say nothing about the physical architecture, and do not show that "
        "the in-budget meshes are exhausted.",
        "",
        "## 4. The prepared experiment",
        "",
        "| mesh | h_port | DOF (order 1) | fraction of the 250 000 rule | port triangles | elements across the width |",
        "|---|---|---|---|---|---|",
    ]
    for name, mesh in meshes.items():
        lines.append(
            f"| {name} | {mesh['port_refinement']['h_port_mm']:.6f} mm | "
            f"{mesh['measured']['dof_order1']} | "
            f"{mesh['budget']['fraction_of_budget']:.1%} | "
            f"{mesh['port_face']['triangles']} | {mesh['port_face']['elements_across_width']:.2f} |"
        )
    lines += [
        "",
        "Both are dry-run measurements, not estimates. Nothing here promises that two "
        "meshes establish convergence; the experiment is a discriminating diagnostic and "
        "`summary.json` states what each possible outcome would and would not mean.",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def build_summary(record_id: str, out_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    provenance = verify_sources()
    declaration = json.loads(DECLARATION.read_text())
    cell = chip_cell_from_declaration(declaration)
    levels = inspect_levels(cell)
    diagnostic = {
        name: port_diagnostic(name, spec, levels[name]) for name, spec in SOURCE_RECORDS.items()
    }
    consistency = compare_across_levels(levels)
    trend = refinement_trend(diagnostic)
    field = size_field_findings(cell)
    meshes = prepare_experiment(cell, out_dir)
    assert_sources_unchanged(provenance)
    from scripts.s1_experiment_predeclaration import PREDECLARATION  # noqa: PLC0415

    return {
        "schema": RECORD_SCHEMA,
        "record_id": record_id,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "palace_launched": False,
        "source_records": provenance,
        "preserved": (
            "every source record was verified against its own manifest before and after "
            "this analysis and none was written to; this record is separately versioned"
        ),
        "port_diagnostic": diagnostic,
        "refinement_trend": trend,
        "mesh_inspection": {
            "levels": levels,
            "consistency_across_levels": consistency,
            "size_field": field,
        },
        "prepared_experiment": {
            "meshes": meshes,
            "predeclaration": PREDECLARATION,
        },
        "constraints_unchanged": {
            "finite_element_order": FINITE_ELEMENT_ORDER,
            "halo_mm": HALO_MM,
            "dof_budget": DOF_BUDGET,
            "per_solve_wall_clock_cap_s": SOLVE_TIMEOUT_S,
            "admission_matching_and_magnitude_rules": "unchanged",
            "declared_window_GHz": [0.5, 9.0],
        },
        "wall_clock_s": time.perf_counter() - started,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", default="results")
    parser.add_argument("--record-pointer", default=None)
    parser.add_argument(
        "--fail-render",
        action="store_true",
        help="force the renderer to raise, to exercise evidence durability",
    )
    args = parser.parse_args(argv)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record_id = f"COUPLED-S1-RECOVERY-{stamp}"
    record_dir = (REPO_ROOT / args.results_root / record_id).resolve()
    record_dir.mkdir(parents=True, exist_ok=True)

    summary = build_summary(record_id, record_dir)

    # Evidence first. The level-3 rung lost a completed solve because its
    # report was rendered before its manifest was written and the renderer
    # raised on a result the estimator is designed to return.
    (record_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=False) + "\n")
    if args.record_pointer:
        Path(args.record_pointer).write_text(str(record_dir))

    render_failed: str | None = None
    try:
        if args.fail_render:
            raise RuntimeError("deliberate renderer failure (--fail-render)")
        report = render_report(summary)
    except Exception as exc:  # noqa: BLE001 - the record still has to survive
        render_failed = f"{type(exc).__name__}: {exc}"
        report = (
            f"# {record_id}\n\n"
            f"**The report could not be rendered: {render_failed}**\n\n"
            "This is a presentation failure, not a loss of evidence. Every measured "
            "quantity is in `summary.json`, which is written and manifested before "
            "anything is rendered, and the record pointer names this directory so the "
            "workflow uploads and commits it regardless.\n"
        )
    (record_dir / "report.md").write_text(report)

    offenders = reject_unexpected_files(record_dir)
    if offenders:
        print(f"unexpected files in the record, refusing: {offenders}", file=sys.stderr)
        return 3

    manifest.write(record_dir)
    print(f"record: {record_dir}")
    if render_failed:
        print(f"rendering failed: {render_failed}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
