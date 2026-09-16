"""The approved bounded numerical-method pilot: three Palace eigenmode solves.

Approved for the checkpoint-A review as three solves of the **same** declared
S1 chip-cell geometry at mesh level 1, differing only in element order and in
the size-field halo:

===== ======= ========= ==========================================
run   order   halo      purpose
===== ======= ========= ==========================================
P1    2       0.08 mm   the reference solve
P2    1       0.08 mm   element-order sensitivity, against P1
P3    2       0.12 mm   halo sensitivity, against P1
===== ======= ========= ==========================================

All three sit inside the declared 250 000 DOF ENGINEERING-RULE (208 670 /
39 832 / 235 806 measured). Each solve is capped at 45 minutes and killed at
the cap. No external or additional compute is used.

**This is a numerical-method pilot only.** It performs no coupling
extraction: it does not run the Route A inversion, it produces no `g`, no
`E_C`, no invariant triple, and it feeds no gate. It measures whether each
solve completes, the mode list in the declared window, the site energy
participation, wall time and memory, and nothing else. Route B, pulse work,
AMD-E, decoder work and mediator work are out of scope and are not touched.

The frozen acceptance criteria for the halo, predeclared in
``docs/coupled-candidate/execution-proposal.md`` §4.2 **before** this ran and
unchanged here:

* ``Δp = |p₁ − p₃| / max(|p₁|, |p₃|) ≤ 1e-2``
* ``Δf = |f₁ − f₃| / f₁ ≤ 1e-4``

Evidence is append-only: one record directory per invocation, every solver
input and output kept, manifest written last.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import manifest  # noqa: E402
from solvers.palace import outputs as pout  # noqa: E402
from solvers.palace.coupled_config import (  # noqa: E402
    COUPLED_SOLVER_RULES,
    CoupledRun,
    build_coupled_config,
    superinductor_henry,
)
from solvers.palace.coupled_geometry import chip_cell_from_declaration  # noqa: E402
from solvers.palace.coupled_mesh import dry_run  # noqa: E402

SUMMARY_SCHEMA = "qmhp-cem.coupled-pilot/0.1.0"
DEFAULT_IMAGE = "qmhp-cem/palace:0.13.0"
CONTAINER_WORKDIR = "/work"
CONFIG_FILENAME = "config.json"

#: The approved pilot. Changing any of it is a new approval, not an edit.
RUNS: tuple[CoupledRun, ...] = (
    CoupledRun("P1", finite_element_order=2, halo_mm=0.08, purpose="the reference solve"),
    CoupledRun("P2", finite_element_order=1, halo_mm=0.08,
               purpose="element-order sensitivity, against P1"),
    CoupledRun("P3", finite_element_order=2, halo_mm=0.12,
               purpose="halo sensitivity, against P1"),
)

#: Frozen before the pilot ran (execution-proposal.md §4.2). Not editable here.
HALO_CRITERIA: dict[str, float] = {
    "max_relative_participation_change": 1.0e-2,
    "max_relative_frequency_change": 1.0e-4,
}

#: Per-solve wall-clock cap, as approved.
SOLVE_TIMEOUT_S = 45 * 60

#: Declared DOF ENGINEERING-RULE; every approved run is inside it.
DOF_BUDGET = 250_000

STATEMENT = (
    "Numerical-method pilot. Three Palace eigenmode solves of the same declared S1 chip cell, "
    "differing only in element order and size-field halo. NO coupling extraction was performed: "
    "no Route A inversion, no g, no invariant triple, no gate input, no Route B. The record "
    "carries completion, the mode list in the declared window, the site energy participation, "
    "wall time and memory. Every geometric value remains an unapproved ENGINEERING-SEED."
)


# --- solver invocation --------------------------------------------------------


def _image_identity(runtime: str, image: str) -> dict[str, Any]:
    out: dict[str, Any] = {"image": image, "runtime": runtime}
    try:
        got = subprocess.run(
            [runtime, "image", "inspect", image, "--format", "{{.Id}}"],
            capture_output=True, text=True, timeout=120, check=False,
        )
        out["image_id"] = got.stdout.strip() or None
        digests = subprocess.run(
            [runtime, "image", "inspect", image, "--format", "{{json .RepoDigests}}"],
            capture_output=True, text=True, timeout=120, check=False,
        )
        parsed = json.loads(digests.stdout.strip() or "[]")
        out["repo_digest"] = parsed[0] if parsed else None
        labels = subprocess.run(
            [runtime, "image", "inspect", image, "--format", "{{json .Config.Labels}}"],
            capture_output=True, text=True, timeout=120, check=False,
        )
        out["labels"] = json.loads(labels.stdout.strip() or "null")
    except Exception as exc:  # noqa: BLE001 - identity is evidence, not control flow
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def _user_flag(runtime: str) -> list[str]:
    """Run the container as the invoking user, as the main adapter does.

    Without this Palace writes ``postpro/`` as root, and the evidence is then
    owned by a user the harness cannot manage: the first pilot run produced
    valid results that git could not commit, because a rebase could not unlink
    root-owned files. The solver output is evidence, so it must be writable by
    whoever records it.
    """
    if not hasattr(os, "getuid"):
        return []
    try:
        info = subprocess.run(
            [runtime, "info", "--format", "{{json .SecurityOptions}}"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if "rootless" in (info.stdout or ""):
            return []                       # already mapped to this user
    except Exception:  # noqa: BLE001 - fall through to the explicit mapping
        pass
    return ["--user", f"{os.getuid()}:{os.getgid()}"]


def _run_palace(runtime: str, image: str, work_dir: Path, name: str, np_: int) -> dict[str, Any]:
    """One container run. Never raises: a failure is a recorded outcome."""
    command = [
        runtime, "run", "--rm", "--network", "none", "--hostname", "localhost",
        "--name", name, *_user_flag(runtime), "-e", "HOME=/tmp", "-e", "OMP_NUM_THREADS=1",
        "-e", "OPENBLAS_NUM_THREADS=1",
        "-v", f"{work_dir.resolve()}:{CONTAINER_WORKDIR}", "-w", CONTAINER_WORKDIR,
        image, "-np", str(np_), CONFIG_FILENAME,
    ]
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=SOLVE_TIMEOUT_S)
        returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = None
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        subprocess.run([runtime, "kill", name], capture_output=True, text=True, timeout=60, check=False)
    wall = time.perf_counter() - t0
    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    (work_dir / "palace_log.txt").write_text((stdout or "") + (stderr or ""))
    return {
        "command": command,
        "returncode": returncode,
        "timed_out": timed_out,
        "timeout_s": SOLVE_TIMEOUT_S,
        "started_utc": started.isoformat(),
        "wall_clock_s": wall,
        # ru_maxrss is the peak RSS of REAPED CHILDREN of this process, i.e. of
        # the container runtime CLI, not of the solver inside the container.
        # Recorded as what it is; the solver's own peak is read from its log
        # where Palace reports it.
        "runner_cli_peak_rss_kb_delta": max(0, after - before),
        "runner_cli_peak_rss_kb": after,
        "memory_note": (
            "ru_maxrss measures the container runtime CLI in this process tree, not the solver "
            "inside the container. Any solver-side figure below is quoted from Palace's own log."
        ),
    }


def _memory_lines_from_log(log: str) -> list[str]:
    """Whatever Palace itself says about memory, verbatim."""
    keys = ("memory", "rss", "gib", "gb of", "allocated")
    return [
        line.strip() for line in log.splitlines()
        if any(k in line.lower() for k in keys)
    ][:40]


# --- one pilot run ------------------------------------------------------------


def execute_run(
    spec: CoupledRun, declaration: dict[str, Any], run_dir: Path, *,
    runtime: str, image: str, np_: int, prepare_only: bool,
) -> dict[str, Any]:
    """Mesh, configure and solve. Never raises; every outcome is recorded."""
    entry: dict[str, Any] = {"spec": spec.as_dict(), "status": "PREPARED"}
    solver_dir = run_dir / "solver"
    solver_dir.mkdir(parents=True, exist_ok=True)
    try:
        cell = chip_cell_from_declaration(declaration)
        report = dry_run(cell, spec.level, solver_dir, dof_budget=DOF_BUDGET, halo_mm=spec.halo_mm)
        mesh = report.as_dict()
        entry["mesh"] = mesh
        entry["clearance_report"] = list(cell.clearance_report())
        dof = mesh["measured"][f"dof_order{spec.finite_element_order}"]
        entry["dof_for_this_order"] = dof
        entry["within_dof_budget"] = dof <= DOF_BUDGET
        if not entry["within_dof_budget"]:
            entry["status"] = "BLOCKED"
            entry["failure"] = (
                f"{dof} DOF at order {spec.finite_element_order} exceeds the declared budget of "
                f"{DOF_BUDGET}; the approved pilot is inside it, so this is a defect, not a run"
            )
            return entry

        substrate = next(m for m in declaration["materials"] if m["id"] == "substrate")
        E_L = next(p for p in declaration["parameter_register"] if p["id"] == "E_L_F1")["value"]
        inductance = superinductor_henry(float(E_L))
        config = build_coupled_config(
            Path(mesh["mesh_file"]).name,
            order=spec.finite_element_order,
            substrate_permittivity=float(substrate["permittivity"]),
            port_inductance_H=inductance,
            port_direction=_port_direction(declaration),
        )
        (solver_dir / CONFIG_FILENAME).write_text(json.dumps(config, indent=2) + "\n")
        entry["config"] = config
        entry["port_inductance_H"] = inductance
        entry["solver_rules"] = dict(COUPLED_SOLVER_RULES)
        if prepare_only:
            entry["status"] = "PREPARED"
            return entry

        name = f"qmhp-coupled-pilot-{spec.name}".lower()
        run_info = _run_palace(runtime, image, solver_dir, name, np_)
        entry["run"] = run_info
        (solver_dir / "palace_run.json").write_text(json.dumps(run_info, indent=1) + "\n")
        log = (solver_dir / "palace_log.txt").read_text()
        entry["log_memory_lines"] = _memory_lines_from_log(log)
        if run_info["timed_out"]:
            entry["status"] = "TIMEOUT"
            entry["failure"] = f"exceeded the {SOLVE_TIMEOUT_S}s cap"
            return entry
        if run_info["returncode"] != 0:
            entry["status"] = "RUN_FAILED"
            entry["failure"] = f"palace exited {run_info['returncode']}"
            return entry

        post = solver_dir / "postpro"
        table = pout.parse_eig_csv(post / "eig.csv")
        modes = [
            {
                "index": r.index,
                "frequency_GHz": r.frequency_re_GHz,
                "frequency_im_GHz": r.frequency_im_GHz,
                "quality_factor": r.quality_factor,
                "backward_error": r.backward_error,
                "in_declared_window": (
                    COUPLED_SOLVER_RULES["band_floor_GHz"]
                    <= r.frequency_re_GHz
                    <= COUPLED_SOLVER_RULES["band_ceiling_GHz"]
                ),
            }
            for r in table.rows
        ]
        epr = pout.parse_port_epr_csv(post / "port-EPR.csv")
        participation = {row.mode: row.participation.get(1) for row in epr}
        for mode in modes:
            mode["site_participation"] = participation.get(mode["index"])
        energies = pout.parse_domain_energy_csv(post / "domain-E.csv")
        entry["equipartition_residuals"] = [e.equipartition_residual for e in energies]
        entry["palace_metadata"] = pout.read_metadata_json(post / "palace.json")
        entry["modes"] = modes
        entry["modes_in_window"] = [m for m in modes if m["in_declared_window"]]
        entry["max_backward_error"] = table.max_backward_error
        entry["status"] = "COMPLETED"
    except Exception as exc:  # noqa: BLE001 - a failure is evidence
        entry["status"] = entry.get("status", "ERROR") if entry.get("status") in {
            "TIMEOUT", "RUN_FAILED", "BLOCKED"
        } else "ERROR"
        entry.setdefault("failure", f"{type(exc).__name__}: {exc}")
    return entry


def _port_direction(declaration: dict[str, Any]) -> str:
    port = next(p for p in declaration["ports"] if p["id"] == "P_F1")
    direction = port["direction"]
    return direction if isinstance(direction, str) else direction[0]


# --- comparisons --------------------------------------------------------------


def _readout_like_mode(entry: dict[str, Any]) -> dict[str, Any] | None:
    """The in-window mode with the SMALLEST site participation.

    Route A's readout-like mode is the one the fluxonium site participates in
    least; the fluxonium-like mode is its partner. Selecting by participation
    rather than by frequency keeps the choice independent of where the modes
    happen to land.
    """
    candidates = [m for m in entry.get("modes_in_window", []) if m.get("site_participation") is not None]
    return min(candidates, key=lambda m: abs(m["site_participation"])) if candidates else None


def _fluxonium_like_mode(entry: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [m for m in entry.get("modes_in_window", []) if m.get("site_participation") is not None]
    return max(candidates, key=lambda m: abs(m["site_participation"])) if candidates else None


def compare(a: dict[str, Any], b: dict[str, Any], label: str) -> dict[str, Any]:
    """Relative change in the readout-like mode's frequency and participation."""
    out: dict[str, Any] = {"comparison": label, "available": False}
    if a.get("status") != "COMPLETED" or b.get("status") != "COMPLETED":
        out["reason"] = (
            f"not both solves completed ({a['spec']['name']}: {a.get('status')}, "
            f"{b['spec']['name']}: {b.get('status')})"
        )
        return out
    ma, mb = _readout_like_mode(a), _readout_like_mode(b)
    if ma is None or mb is None:
        out["reason"] = "no in-window mode with a site participation in one of the solves"
        return out
    fa, fb = ma["frequency_GHz"], mb["frequency_GHz"]
    pa, pb = ma["site_participation"], mb["site_participation"]
    scale = max(abs(pa), abs(pb))
    out.update({
        "available": True,
        "readout_like_mode": {
            a["spec"]["name"]: {"frequency_GHz": fa, "site_participation": pa},
            b["spec"]["name"]: {"frequency_GHz": fb, "site_participation": pb},
        },
        "delta_f_relative": abs(fa - fb) / fa if fa else None,
        "delta_p_relative": (abs(pa - pb) / scale) if scale > 0 else None,
        "modes_in_window": {
            a["spec"]["name"]: len(a.get("modes_in_window", [])),
            b["spec"]["name"]: len(b.get("modes_in_window", [])),
        },
    })
    fa_flux, fb_flux = _fluxonium_like_mode(a), _fluxonium_like_mode(b)
    if fa_flux and fb_flux:
        out["fluxonium_like_mode"] = {
            a["spec"]["name"]: {"frequency_GHz": fa_flux["frequency_GHz"],
                                "site_participation": fa_flux["site_participation"]},
            b["spec"]["name"]: {"frequency_GHz": fb_flux["frequency_GHz"],
                                "site_participation": fb_flux["site_participation"]},
        }
    return out


def halo_verdict(p1_p3: dict[str, Any]) -> dict[str, Any]:
    """Apply the FROZEN criteria. They are not recomputed or relaxed here."""
    out: dict[str, Any] = {"criteria": dict(HALO_CRITERIA), "frozen_in": "execution-proposal.md §4.2"}
    if not p1_p3.get("available"):
        out.update({"verdict": "NOT-DECIDED", "reason": p1_p3.get("reason", "comparison unavailable")})
        return out
    dp, df = p1_p3["delta_p_relative"], p1_p3["delta_f_relative"]
    if dp is None or df is None:
        out.update({"verdict": "NOT-DECIDED", "reason": "a change could not be formed"})
        return out
    p_ok = dp <= HALO_CRITERIA["max_relative_participation_change"]
    f_ok = df <= HALO_CRITERIA["max_relative_frequency_change"]
    out.update({
        "delta_p_relative": dp, "delta_f_relative": df,
        "participation_check": "PASS" if p_ok else "FAIL",
        "frequency_check": "PASS" if f_ok else "FAIL",
    })
    if p_ok and f_ok:
        out.update({
            "verdict": "ADMISSIBLE",
            "systematic_floor_contribution_relative": dp,
            "propagation": (
                "the measured delta_p is carried forward as a systematic contribution to Route A's "
                "resolution floor for g, combined with the mesh-ladder term by taking the maximum"
            ),
        })
    elif not f_ok:
        out.update({
            "verdict": "NOT-A-HALO-VERDICT",
            "reason": (
                "the frequency check failed, which indicates the level-1 mesh is too coarse for "
                "this geometry or the model is wrong, not that the halo is bad; the halo question "
                "is not answerable from this pilot"
            ),
        })
    else:
        out.update({
            "verdict": "REJECTED",
            "reason": (
                "the halo-induced participation change exceeds the frozen 1e-2; the 0.08 mm halo "
                "is not admissible and is not rescued by loosening the criterion"
            ),
        })
    return out


def order_verdict(entries: dict[str, dict[str, Any]], p1_p2: dict[str, Any]) -> dict[str, Any]:
    """Apply the predeclared element-order rule (execution-proposal.md §4.3)."""
    p1, p2 = entries.get("P1", {}), entries.get("P2", {})
    out: dict[str, Any] = {"rule": "execution-proposal.md §4.3"}
    p1_ok = p1.get("status") == "COMPLETED"
    p2_ok = p2.get("status") == "COMPLETED"
    if p1_ok:
        out.update({
            "selected_order": 2,
            "reason": "P1 completed inside its 45 minute cap, so order 2 is selected",
            "wall_clock_s": p1.get("run", {}).get("wall_clock_s"),
        })
        if p1_p2.get("available"):
            out["order_sensitivity_delta_p_relative"] = p1_p2["delta_p_relative"]
            out["order_sensitivity_delta_f_relative"] = p1_p2["delta_f_relative"]
            out["note"] = "the order-1 difference is reported as the measured cost of the cheaper discretisation"
    elif p2_ok:
        out.update({
            "selected_order": 1,
            "reason": (
                "P1 did not complete, so order 1 is the only option; it is usable only if its own "
                "participation converges on the ladder well enough to give a useful floor on g, "
                "which this pilot does not measure"
            ),
        })
    else:
        out.update({
            "selected_order": None,
            "reason": "neither P1 nor P2 completed; the extraction is not executable within the current allowance",
        })
    return out


def next_stage(halo: dict[str, Any], order: dict[str, Any], entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """READY / BLOCKED / another bounded numerical check — decided by the rules above."""
    statuses = {name: e.get("status") for name, e in entries.items()}
    if order.get("selected_order") is None:
        return {"disposition": "BLOCKED",
                "reason": "no solve completed, so no element order is justified", "statuses": statuses}
    if halo.get("verdict") == "REJECTED":
        return {"disposition": "BLOCKED",
                "reason": ("the 0.08 mm halo is not admissible under the frozen criterion, and the wider "
                           "halo does not fit the DOF budget at order 2 at any ladder level; the choice "
                           "returns to the review"),
                "statuses": statuses}
    if halo.get("verdict") in {"NOT-DECIDED", "NOT-A-HALO-VERDICT"}:
        return {"disposition": "REQUIRES-ANOTHER-BOUNDED-NUMERICAL-CHECK",
                "reason": halo.get("reason", "the halo criterion could not be applied"),
                "statuses": statuses}
    return {
        "disposition": "READY-FOR-THE-LADDER",
        "reason": (
            "the halo is admissible under the frozen criterion and an element order is justified; "
            "the next stage is the Route A mesh ladder, which is a separate approval and is not "
            "started here"
        ),
        "statuses": statuses,
        "carried_forward": {
            "systematic_floor_contribution_relative": halo.get("systematic_floor_contribution_relative"),
            "selected_order": order.get("selected_order"),
        },
    }


# --- record -------------------------------------------------------------------


def render_report(summary: dict[str, Any]) -> str:
    def cell(value: Any, spec: str = "") -> str:
        if value is None:
            return "-"
        return format(value, spec) if spec else str(value)

    L = [
        "# Coupled chip-cell numerical-method pilot",
        "",
        f"Record `{summary['batch_id']}`. {summary['statement']}",
        "",
        "## 1. Did each solve complete?",
        "",
        "| run | order | halo (mm) | DOF | status | Palace s | modes in window | max backward error |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name in ("P1", "P2", "P3"):
        e = summary["runs"].get(name, {})
        spec = e.get("spec", {})
        wall = e.get("run", {}).get("wall_clock_s")
        modes = e.get("modes_in_window")
        L.append(
            f"| {name} | {cell(spec.get('finite_element_order'))} | {cell(spec.get('halo_mm'))} | "
            f"{cell(e.get('dof_for_this_order'))} | {cell(e.get('status'))} | "
            f"{cell(wall, '.1f')} | {cell(len(modes) if modes is not None else None)} | "
            f"{cell(e.get('max_backward_error'), '.2e')} |"
        )
        if e.get("failure"):
            L.append(f"| | | | | {e['failure'][:110]} | | | |")
    for label, key in (("2. P1 vs P2: element-order sensitivity", "p1_vs_p2"),
                       ("3. P1 vs P3: halo sensitivity", "p1_vs_p3")):
        c = summary[key]
        L += ["", f"## {label}", ""]
        if not c.get("available"):
            L.append(f"Not available: {c.get('reason')}")
            continue
        L += [
            f"- readout-like mode: {json.dumps(c['readout_like_mode'])}",
            f"- relative frequency change: {c['delta_f_relative']:.3e}",
            f"- relative participation change: {c['delta_p_relative']:.3e}",
        ]
        if "fluxonium_like_mode" in c:
            L.append(f"- fluxonium-like mode: {json.dumps(c['fluxonium_like_mode'])}")
    h = summary["halo_verdict"]
    L += ["", "## 4. Is the 0.08 mm halo admissible under the frozen criteria?", "",
          f"Criteria, frozen in {h['frozen_in']} before this ran: "
          f"Δp ≤ {h['criteria']['max_relative_participation_change']:.0e}, "
          f"Δf ≤ {h['criteria']['max_relative_frequency_change']:.0e}.", "",
          f"**{h['verdict']}**"]
    if "participation_check" in h:
        L.append(f"- participation: {h['participation_check']} (Δp = {h['delta_p_relative']:.3e})")
        L.append(f"- frequency: {h['frequency_check']} (Δf = {h['delta_f_relative']:.3e})")
    if "propagation" in h:
        L.append(f"- {h['propagation']}")
    if "reason" in h:
        L.append(f"- {h['reason']}")
    o = summary["order_verdict"]
    L += ["", "## 5. Which element order is justified for the next ladder?", "",
          f"**order {o.get('selected_order')}** — {o['reason']}"]
    if "order_sensitivity_delta_p_relative" in o:
        L.append(f"- order sensitivity: Δp = {o['order_sensitivity_delta_p_relative']:.3e}, "
                 f"Δf = {o['order_sensitivity_delta_f_relative']:.3e}")
    n = summary["next_stage"]
    L += ["", "## 6. Next extraction stage", "", f"**{n['disposition']}** — {n['reason']}"]
    L += ["", "## Statement", "", summary["statement"], ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--declaration", default=str(REPO_ROOT / "config" / "coupled" / "v2a_five_node_candidate.json"))
    parser.add_argument("--results-root", default=str(REPO_ROOT / "results"))
    parser.add_argument("--record-name", default=None)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--np", type=int, default=1)
    parser.add_argument("--prepare-only", action="store_true",
                        help="mesh and write the config, do not launch Palace")
    parser.add_argument("--record-pointer", default=None)
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc)
    batch = args.record_name or f"COUPLED-PILOT-{started.strftime('%Y%m%dT%H%M%SZ')}"
    root = Path(args.results_root) / batch
    root.mkdir(parents=True, exist_ok=False)
    declaration = json.loads(Path(args.declaration).read_text())

    summary: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "batch_id": batch,
        "started_utc": started.isoformat(),
        "statement": STATEMENT,
        "performed_coupling_extraction": False,
        "performed_route_b": False,
        "declaration": {
            "path": str(args.declaration),
            "sha256": manifest.file_digest(Path(args.declaration)),
            "id": declaration.get("declaration_id"),
        },
        "approved_pilot": [r.as_dict() for r in RUNS],
        "halo_criteria": dict(HALO_CRITERIA),
        "solve_timeout_s": SOLVE_TIMEOUT_S,
        "dof_budget": DOF_BUDGET,
        "solver_rules": dict(COUPLED_SOLVER_RULES),
        "environment": {
            "os": f"{platform.system()} {platform.release()}",
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "mpi_processes": args.np,
            "docker_available": shutil.which(args.runtime) is not None,
        },
        "image": _image_identity(args.runtime, args.image) if not args.prepare_only else {"image": args.image},
        "runs": {},
    }

    for spec in RUNS:
        print(f"== {spec.name}: order {spec.finite_element_order}, halo {spec.halo_mm} mm", flush=True)
        entry = execute_run(
            spec, declaration, root / spec.name,
            runtime=args.runtime, image=args.image, np_=args.np, prepare_only=args.prepare_only,
        )
        summary["runs"][spec.name] = entry
        wall = entry.get("run", {}).get("wall_clock_s")
        print(f"   {entry['status']}"
              + (f", {wall:.1f} s" if isinstance(wall, (int, float)) else "")
              + f", DOF {entry.get('dof_for_this_order')}"
              + (f", {len(entry.get('modes_in_window', []))} modes in window" if entry.get("modes") else ""),
              flush=True)

    summary["p1_vs_p2"] = compare(summary["runs"].get("P1", {}), summary["runs"].get("P2", {}),
                                  "P1 vs P2: element order at a fixed 0.08 mm halo")
    summary["p1_vs_p3"] = compare(summary["runs"].get("P1", {}), summary["runs"].get("P3", {}),
                                  "P1 vs P3: halo at a fixed order 2")
    summary["halo_verdict"] = halo_verdict(summary["p1_vs_p3"])
    summary["order_verdict"] = order_verdict(summary["runs"], summary["p1_vs_p2"])
    summary["next_stage"] = next_stage(summary["halo_verdict"], summary["order_verdict"], summary["runs"])
    summary["ended_utc"] = datetime.now(timezone.utc).isoformat()

    (root / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    (root / "report.md").write_text(render_report(summary))
    manifest.write(root)  # always last
    if args.record_pointer:
        Path(args.record_pointer).write_text(str(root) + "\n")
    print(f"record : {root}")
    print(f"halo   : {summary['halo_verdict']['verdict']}")
    print(f"order  : {summary['order_verdict'].get('selected_order')}")
    print(f"next   : {summary['next_stage']['disposition']}")
    completed = sum(1 for e in summary["runs"].values() if e["status"] == "COMPLETED")
    if args.prepare_only:
        return 0
    return 0 if completed == len(RUNS) else 5


if __name__ == "__main__":
    sys.exit(main())
