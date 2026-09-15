"""Mesh-refinement and height-sensitive verification of the empty-cavity benchmark.

This is the numerical-verification milestone that follows the first golden
run (spec §15): the same 22 x 22 x 1.5 mm empty PEC box on three meshes, and
a second benchmark that solves modes with p >= 1, the only modes whose
frequency depends on the cavity height. Everything here is an
ENGINEERING-RULE of numerical verification. None of it is a frozen QMHP
physical requirement, and nothing here is evidence about the physical
package: the chip, recess, launches and lid are not in the model.

Two benchmarks with heights are defined:

* ``object001_height``: the Object 001 box itself (d = 1.5 mm) against
  d = 1.65 mm. Its first height-dependent mode, (0,1,1), lies near 100 GHz
  with about 150 modes below it, and resolving it to the declared mesh rule
  needs more degrees of freedom than the hosted runner can be expected to
  carry. The campaign records that level as BLOCKED by budget and makes one
  bounded exploratory attempt at a coarser level; without refinement the
  verdict can be at most INCOMPLETE.
* ``aux_height``: an auxiliary taller box, 22 x 22 mm by 7.0 and 7.7 mm,
  whose (0,1,1) mode lies at 22.47 and 20.62 GHz with only a handful of
  modes below it. It verifies the Z pipeline end to end and is labelled as
  auxiliary everywhere: it is not a verification of Object 001.

The golden path is untouched: every default in :mod:`solvers.palace.config`
stays what the committed golden records carry, and a campaign run sets its
own mesh length, mode count, target and probes explicitly per run.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any

from solvers.palace import analytic
from solvers.palace.config import SOLVER_RULES, SolverDomain, default_target_GHz

CAMPAIGN_SCHEMA = "qmhp-cem.palace-verify-campaign/0.2.0"
SUMMARY_SCHEMA = "qmhp-cem.palace-verify-summary/0.2.0"

#: Numerical acceptance rules for this benchmark (ENGINEERING-RULE, declared
#: before any run and not to be loosened after one).
RULES: dict[str, Any] = {
    # Objective 1: mesh convergence of the 22 x 22 x 1.5 mm box.
    "mesh_levels_min": 3,
    "finest_relative_analytic_error_max": 1.0e-4,
    "final_two_levels_relative_change_max": 1.0e-4,
    "refinement_factors": [1.0, 1.5, 2.0],
    # Objective 2: height sensitivity through p >= 1 modes.
    "height_mode_match_relative_tolerance": 2.0e-3,
    "height_shift_relative_disagreement_max": 1.0e-2,
    "height_shift_to_uncertainty_min_ratio": 10.0,
    "height_levels_min_for_pass": 2,
    "height_mesh_rule": "min(min(a, b) / 12, d / 4, lambda(f_target) / 6)",
    "height_target_rule": "midway between the target mode and the highest analytic mode below it",
    "height_window_above_mode": 0.01,
    "height_modes_margin": 6,
    # Field-probe classification of a computed mode from sum|E_z|^2 / sum|E|^2.
    "probe_z_fraction_tm0_min": 0.9,
    "probe_z_fraction_transverse_max": 0.1,
    "probe_fractions": [[0.31, 0.23, 0.45], [0.67, 0.41, 0.55], [0.19, 0.71, 0.5]],
    # Runner budget. The DOF estimate is made from the real mesh before Palace
    # is launched; a level above the budget is BLOCKED and its mesh kept.
    "dof_budget": 400_000,
    "dof_per_tetrahedron_estimate": 8.2,
    "timeout_s_ladder": 1800,
    "timeout_s_height": 1800,
    "timeout_s_exploratory": 3600,
    # Unchanged from the golden run: Palace's own convergence rules.
    "eigenvalue_tolerance": SOLVER_RULES["eigenvalue_tolerance"],
    "eigenmode_backward_error_max_tolerance": SOLVER_RULES["eigenmode_backward_error_max_tolerance"],
    "finite_element_order": SOLVER_RULES["finite_element_order"],
}

PASS, FAIL, INCOMPLETE, BLOCKED = "PASS", "FAIL", "INCOMPLETE", "BLOCKED"


# --- definitions -------------------------------------------------------------


@dataclass(frozen=True)
class CavityBox:
    a_mm: float
    b_mm: float
    d_mm: float

    def domain(self, mesh_length_mm: float | None = None) -> SolverDomain:
        """Spec §7.3 frame: centred in X/Y, z from 0 (chip top) to d (lid)."""
        return SolverDomain(
            x_min_mm=-self.a_mm / 2.0, x_max_mm=self.a_mm / 2.0,
            y_min_mm=-self.b_mm / 2.0, y_max_mm=self.b_mm / 2.0,
            z_min_mm=0.0, z_max_mm=self.d_mm,
            mesh_length_mm=mesh_length_mm,
        )

    def frequency(self, m: int, n: int, p: int) -> float:
        return analytic.mode_frequency_GHz(self.a_mm, self.b_mm, self.d_mm, m, n, p)

    def modes_below(self, f_max_GHz: float) -> list[analytic.CavityMode]:
        return analytic.rectangular_cavity_modes_below(self.a_mm, self.b_mm, self.d_mm, f_max_GHz)

    def as_dict(self) -> dict[str, float]:
        return {"a_mm": self.a_mm, "b_mm": self.b_mm, "d_mm": self.d_mm}


@dataclass(frozen=True)
class RunSpec:
    name: str
    benchmark: str
    role: str                      # "mesh_ladder" | "height" | "height_exploratory" | "height_rule"
    cavity: CavityBox
    level: int
    mesh_length_mm: float
    eigenmodes: int
    target_GHz: float | None       # None: the golden default (0.85 x fundamental)
    probes: bool
    timeout_s: int
    height_mode: tuple[int, int, int] | None = None
    note: str = ""

    def overrides(self) -> dict[str, Any]:
        """The ``RunContext.extra['palace']`` block for this run."""
        domain = self.cavity.domain(self.mesh_length_mm)
        out: dict[str, Any] = {
            "domain": domain.as_dict(),
            "mesh_length_mm": self.mesh_length_mm,
            "eigenmodes": self.eigenmodes,
            "label": self.name,
        }
        if self.target_GHz is not None:
            out["target_GHz"] = self.target_GHz
        if self.probes:
            out["probes_mm"] = domain.probe_points_mm([tuple(f) for f in RULES["probe_fractions"]])
        return out

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["cavity"] = self.cavity.as_dict()
        d["height_mode"] = list(self.height_mode) if self.height_mode else None
        d["overrides"] = self.overrides()
        return d


@dataclass(frozen=True)
class HeightBenchmark:
    name: str
    cavity_a_mm: float
    cavity_b_mm: float
    heights_mm: tuple[float, float]
    mode: tuple[int, int, int]
    is_object001: bool
    exploratory_mesh_rule: str | None = None    # e.g. "d / 3"

    def box(self, d_mm: float) -> CavityBox:
        return CavityBox(self.cavity_a_mm, self.cavity_b_mm, d_mm)


@dataclass
class Campaign:
    schema: str
    name: str
    rules: dict[str, Any]
    object001: CavityBox
    ladder: list[RunSpec]
    height_benchmarks: list[HeightBenchmark]
    height_runs: list[RunSpec]
    statement: str
    analytic_design: dict[str, Any] = field(default_factory=dict)

    @property
    def runs(self) -> list[RunSpec]:
        return [*self.ladder, *self.height_runs]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "rules": self.rules,
            "object001": self.object001.as_dict(),
            "ladder": [r.as_dict() for r in self.ladder],
            "height_benchmarks": [
                {**asdict(b), "heights_mm": list(b.heights_mm), "mode": list(b.mode)}
                for b in self.height_benchmarks
            ],
            "height_runs": [r.as_dict() for r in self.height_runs],
            "analytic_design": self.analytic_design,
            "statement": self.statement,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


def object001_box() -> CavityBox:
    return CavityBox(22.0, 22.0, 1.5)


def golden_mesh_length_mm(box: CavityBox) -> float:
    return box.domain().default_characteristic_length_mm


def height_mesh_length_mm(box: CavityBox, f_target_GHz: float) -> float:
    """The declared rule for height-sensitive runs: resolve the shortest structure.

    The in-plane rule, four elements across the height (a p = 1 mode has one
    half-wave in z), and six elements per free-space wavelength at the target
    frequency, whichever is smallest.
    """
    wavelength_mm = analytic.C_M_PER_S / (f_target_GHz * 1e9) * 1e3
    return min(min(box.a_mm, box.b_mm) / 12.0, box.d_mm / 4.0, wavelength_mm / 6.0)


def height_target_GHz(box: CavityBox, mode: tuple[int, int, int]) -> tuple[float, float, float]:
    """Target midway between the wanted mode and the highest analytic mode below it.

    Palace returns eigenvalues close to but not below the target, so the
    target must sit below the mode; halfway to the previous mode keeps a
    p = 0 neighbour that the discretisation shifts upward from crowding the
    window. Returns (target, f_mode, f_previous).
    """
    f_mode = box.frequency(*mode)
    below = [m for m in box.modes_below(f_mode) if m.frequency_GHz < f_mode * (1 - 1e-9)]
    f_prev = below[-1].frequency_GHz if below else 0.0
    return 0.5 * (f_mode + f_prev), f_mode, f_prev


def modes_counted_below(box: CavityBox, f_GHz: float) -> int:
    return sum(m.multiplicity for m in box.modes_below(f_GHz) if m.frequency_GHz < f_GHz * (1 - 1e-9))


def mesh_ladder(box: CavityBox) -> list[RunSpec]:
    """The Objective 1 ladder: golden settings, only the mesh length changes."""
    h0 = golden_mesh_length_mm(box)
    runs = []
    for level, factor in enumerate(RULES["refinement_factors"], start=1):
        runs.append(RunSpec(
            name=f"ladder-L{level}", benchmark="object001_mesh_ladder", role="mesh_ladder",
            cavity=box, level=level, mesh_length_mm=h0 / factor,
            eigenmodes=int(SOLVER_RULES["eigenmodes_requested"]), target_GHz=None,
            probes=True, timeout_s=int(RULES["timeout_s_ladder"]),
            note=f"h0 / {factor:g}; identical physics, order, tolerances and target to the golden run",
        ))
    return runs


def height_benchmarks() -> list[HeightBenchmark]:
    return [
        HeightBenchmark(
            name="object001_height", cavity_a_mm=22.0, cavity_b_mm=22.0,
            heights_mm=(1.5, 1.65), mode=(0, 1, 1), is_object001=True,
            exploratory_mesh_rule="d / 3",
        ),
        HeightBenchmark(
            name="aux_height", cavity_a_mm=22.0, cavity_b_mm=22.0,
            heights_mm=(7.0, 7.7), mode=(0, 1, 1), is_object001=False,
        ),
    ]


def height_eigenmodes(box: CavityBox, target_GHz: float, f_mode: float, rules: dict[str, Any] = RULES) -> int:
    """Modes to request: every analytic mode from the target to the declared
    window above the wanted mode, plus a margin for p = 0 modes that the
    discretisation shifts upward into the window."""
    upper = f_mode * (1.0 + rules["height_window_above_mode"])
    window = modes_counted_below(box, upper) - modes_counted_below(box, target_GHz)
    return max(6, window + int(rules["height_modes_margin"]))


def height_runs_for(bench: HeightBenchmark) -> list[RunSpec]:
    runs: list[RunSpec] = []
    for d in bench.heights_mm:
        box = bench.box(d)
        target, f_mode, _ = height_target_GHz(box, bench.mode)
        n_modes = height_eigenmodes(box, target, f_mode)
        rule_lc = height_mesh_length_mm(box, f_mode)
        levels: list[tuple[str, int, float, str, int]] = []
        if bench.exploratory_mesh_rule == "d / 3":
            levels.append(("height_exploratory", 1, box.d_mm / 3.0,
                           "exploratory: three elements across the height, below the declared rule",
                           int(RULES["timeout_s_exploratory"])))
            levels.append(("height_rule", 2, rule_lc, "the declared rule level", int(RULES["timeout_s_exploratory"])))
        else:
            levels.append(("height", 1, rule_lc, "the declared rule level", int(RULES["timeout_s_height"])))
            levels.append(("height", 2, rule_lc / 1.5, "rule level / 1.5", int(RULES["timeout_s_height"])))
        for role, level, lc, note, timeout in levels:
            runs.append(RunSpec(
                name=f"{bench.name}-d{d:g}-L{level}", benchmark=bench.name, role=role,
                cavity=box, level=level, mesh_length_mm=lc, eigenmodes=n_modes,
                target_GHz=round(target, 6), probes=True, timeout_s=timeout,
                height_mode=bench.mode, note=note,
            ))
    # Order: level 1 at both heights first, so a single-level comparison exists early.
    runs.sort(key=lambda r: (r.level, r.name))
    return runs


def analytic_design(benches: list[HeightBenchmark]) -> dict[str, Any]:
    """The numbers behind the design, recorded so the record explains itself."""
    out: dict[str, Any] = {}
    for bench in benches:
        entry: dict[str, Any] = {"heights": {}}
        fs = []
        for d in bench.heights_mm:
            box = bench.box(d)
            target, f_mode, f_prev = height_target_GHz(box, bench.mode)
            fs.append(f_mode)
            entry["heights"][f"{d:g}"] = {
                "f_mode_GHz": f_mode,
                "f_previous_analytic_mode_GHz": f_prev,
                "target_GHz": target,
                "modes_below_target_with_multiplicity": modes_counted_below(box, target),
                "modes_below_mode_with_multiplicity": modes_counted_below(box, f_mode),
                "neighbourhood": [
                    {"label": m.label, "frequency_GHz": m.frequency_GHz, "multiplicity": m.multiplicity, "p": m.p}
                    for m in box.modes_below(f_mode * 1.03) if m.frequency_GHz >= target
                ],
                "rule_mesh_length_mm": height_mesh_length_mm(box, f_mode),
                "eigenmodes_requested": height_eigenmodes(box, target, f_mode),
            }
        entry["delta_f_exact_GHz"] = fs[1] - fs[0]
        entry["delta_f_exact_relative"] = (fs[1] - fs[0]) / fs[0]
        entry["p0_modes_are_height_independent"] = True
        out[bench.name] = entry
    return out


def build_campaign(probes: bool = True) -> Campaign:
    """The frozen campaign. ``probes=False`` drops the field probes from every
    run (for an image built without GSLIB); the mode-family check then reports
    'unknown' and matching rests on frequency alone, which the record states."""
    box = object001_box()
    benches = height_benchmarks()
    runs = [r for b in benches for r in height_runs_for(b)]
    if not probes:
        runs = [RunSpec(**{**asdict(r), "cavity": r.cavity, "probes": False}) for r in runs]
    # Object 001 exploratory attempts are the most expensive: run the cheap,
    # decisive auxiliary benchmark before them.
    runs.sort(key=lambda r: (0 if r.benchmark == "aux_height" else 1, r.level, r.name))
    return Campaign(
        schema=CAMPAIGN_SCHEMA,
        name="mesh-height-verification-v1" + ("" if probes else "-noprobes"),
        rules=dict(RULES),
        object001=box,
        ladder=[RunSpec(**{**asdict(r), "cavity": r.cavity, "probes": probes}) for r in mesh_ladder(box)],
        height_benchmarks=benches,
        height_runs=runs,
        analytic_design=analytic_design(benches),
        statement=(
            "Numerical verification of the empty PEC box only. Mesh convergence of "
            "the 22 x 22 x 1.5 mm box on three meshes, and height sensitivity through "
            "p >= 1 modes: the Object 001 box itself where the runner budget allows, "
            "and an auxiliary 22 x 22 x 7.0/7.7 mm box that verifies the Z pipeline "
            "and is not a verification of Object 001. All rules are ENGINEERING-RULEs "
            "of numerical verification, not frozen QMHP physical requirements. No mode "
            "splitting here is physical QMHP coupling."
        ),
    )


# --- per-run results ------------------------------------------------------------


@dataclass
class RunResult:
    """What one executed (or blocked) run contributes to the comparisons."""

    name: str
    status: str                                   # CONVERGED | NOT_CONVERGED | RUN_FAILED | BLOCKED | ERROR
    mesh_length_mm: float
    level: int | None = None                      # refinement level within its benchmark
    nodes: int | None = None
    tetrahedra: int | None = None
    dof: int | None = None
    dof_estimate: int | None = None
    mesh_sha256: str | None = None
    config_sha256: str | None = None
    frequencies_GHz: list[float] = field(default_factory=list)
    backward_errors: list[float] = field(default_factory=list)
    backward_error_max: float | None = None
    palace_status: str | None = None
    runtime_s: float | None = None
    palace_total_s: float | None = None
    z_fraction: dict[int, float | None] = field(default_factory=dict)
    failure: str | None = None

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["z_fraction"] = {str(k): v for k, v in self.z_fraction.items()}
        return d


def estimate_dof(tetrahedra: int) -> int:
    return int(round(RULES["dof_per_tetrahedron_estimate"] * tetrahedra))


# --- Objective 1: mesh convergence --------------------------------------------------


def mesh_convergence_table(levels: list[RunResult], expected_GHz: list[float]) -> list[dict[str, Any]]:
    """One row per level with analytic errors and the change from the previous level."""
    rows: list[dict[str, Any]] = []
    prev: RunResult | None = None
    for r in sorted(levels, key=lambda x: -x.mesh_length_mm):
        n = len(expected_GHz)
        freqs = list(r.frequencies_GHz[:n])
        rel_err = [(f - e) / e for f, e in zip(freqs, expected_GHz)] if r.status == "CONVERGED" else []
        delta = None
        if prev is not None and prev.status == "CONVERGED" and r.status == "CONVERGED":
            delta = [(f - g) / g for f, g in zip(freqs, prev.frequencies_GHz[:n])]
        rows.append({
            "run": r.name, "status": r.status, "mesh_length_mm": r.mesh_length_mm,
            "nodes": r.nodes, "tetrahedra": r.tetrahedra, "dof": r.dof, "mesh_sha256": r.mesh_sha256,
            "frequencies_GHz": freqs, "analytic_GHz": list(expected_GHz),
            "relative_analytic_error": rel_err,
            "max_abs_relative_analytic_error": (max(abs(x) for x in rel_err) if rel_err else None),
            "relative_change_vs_previous_level": delta,
            "max_abs_relative_change_vs_previous_level": (max(abs(x) for x in delta) if delta else None),
            "backward_errors": list(r.backward_errors), "backward_error_max": r.backward_error_max,
            "palace_status": r.palace_status, "runtime_s": r.runtime_s, "palace_total_s": r.palace_total_s,
        })
        prev = r
    return rows


def degenerate_pair_table(levels: list[RunResult], pair: tuple[int, int] = (1, 2)) -> list[dict[str, Any]]:
    """The (1,2,0)/(2,1,0) pair, modes 2 and 3 (0-based 1 and 2), level by level."""
    rows = []
    for r in sorted(levels, key=lambda x: -x.mesh_length_mm):
        if r.status != "CONVERGED" or len(r.frequencies_GHz) <= max(pair):
            rows.append({"run": r.name, "status": r.status})
            continue
        f1, f2 = r.frequencies_GHz[pair[0]], r.frequencies_GHz[pair[1]]
        centre = 0.5 * (f1 + f2)
        rows.append({
            "run": r.name, "status": r.status, "mesh_length_mm": r.mesh_length_mm,
            "mode_a_GHz": f1, "mode_b_GHz": f2, "centre_GHz": centre,
            "splitting_MHz": (f2 - f1) * 1e3, "splitting_relative": (f2 - f1) / centre,
            "note": "numerical splitting of an exactly degenerate analytic pair; not physical coupling",
        })
    return rows


def mesh_convergence_verdict(table: list[dict[str, Any]], rules: dict[str, Any] = RULES) -> dict[str, Any]:
    reasons: list[str] = []
    converged = [row for row in table if row["status"] == "CONVERGED"]
    if len(table) < rules["mesh_levels_min"] or len(converged) < rules["mesh_levels_min"]:
        reasons.append(f"{len(converged)} of {len(table)} levels converged; {rules['mesh_levels_min']} required")
        return {"verdict": INCOMPLETE, "reasons": reasons}
    finest = table[-1]
    if finest["max_abs_relative_analytic_error"] is None:
        return {"verdict": INCOMPLETE, "reasons": ["finest level carries no analytic comparison"]}
    verdict = PASS
    if finest["max_abs_relative_analytic_error"] > rules["finest_relative_analytic_error_max"]:
        verdict = FAIL
        reasons.append(
            f"finest-mesh relative analytic error {finest['max_abs_relative_analytic_error']:.3e} "
            f"> {rules['finest_relative_analytic_error_max']:.0e}"
        )
    if finest["max_abs_relative_change_vs_previous_level"] is None:
        verdict = INCOMPLETE if verdict == PASS else verdict
        reasons.append("no converged previous level to compare the finest with")
    elif finest["max_abs_relative_change_vs_previous_level"] > rules["final_two_levels_relative_change_max"]:
        verdict = FAIL
        reasons.append(
            f"relative change between the final two levels {finest['max_abs_relative_change_vs_previous_level']:.3e} "
            f"> {rules['final_two_levels_relative_change_max']:.0e}"
        )
    for row in table:
        if row["backward_error_max"] is not None and row["backward_error_max"] > rules["eigenmode_backward_error_max_tolerance"]:
            verdict = FAIL
            reasons.append(f"{row['run']}: backward error {row['backward_error_max']:.3e} above the unchanged rule")
    if verdict == PASS:
        reasons.append(
            f"finest error {finest['max_abs_relative_analytic_error']:.3e}, final-two-level change "
            f"{finest['max_abs_relative_change_vs_previous_level']:.3e}, all levels CONVERGED"
        )
    return {"verdict": verdict, "reasons": reasons}


# --- Objective 2: height sensitivity ----------------------------------------------


def classify_family(z_fraction: float | None, rules: dict[str, Any] = RULES) -> str:
    if z_fraction is None:
        return "unknown"
    if z_fraction >= rules["probe_z_fraction_tm0_min"]:
        return "z-polarised (TM_mn0-like)"
    if z_fraction <= rules["probe_z_fraction_transverse_max"]:
        return "transverse (TE, p>=1)"
    return "mixed (TM, p>=1)"


def _family_consistent(family: str, mode: analytic.CavityMode) -> bool | None:
    if family == "unknown":
        return None
    if mode.p == 0:
        return family.startswith("z-polarised")
    if mode.m == 0 or mode.n == 0:      # TE only
        return family.startswith("transverse")
    return not family.startswith("z-polarised")   # TE or TM with p >= 1


def match_modes(
    frequencies_GHz: list[float],
    box: CavityBox,
    f_max_GHz: float,
    z_fraction: dict[int, float | None] | None = None,
    rules: dict[str, Any] = RULES,
) -> list[dict[str, Any]]:
    """Assign each computed mode to an analytic mode, honouring multiplicity.

    Greedy in ascending computed frequency: a computed mode takes the nearest
    analytic mode within the tolerance that still has capacity (its
    multiplicity). The decision carries the probe family where probes exist,
    and whether that family is consistent with the analytic triple.
    """
    tol = rules["height_mode_match_relative_tolerance"]
    candidates = box.modes_below(f_max_GHz)
    capacity = {i: m.multiplicity for i, m in enumerate(candidates)}
    decisions: list[dict[str, Any]] = []
    for k, f in enumerate(sorted(frequencies_GHz)):
        best: tuple[float, int] | None = None
        for i, m in enumerate(candidates):
            if capacity[i] <= 0:
                continue
            rel = abs(f - m.frequency_GHz) / m.frequency_GHz
            if rel <= tol and (best is None or rel < best[0]):
                best = (rel, i)
        zf = (z_fraction or {}).get(k + 1)
        family = classify_family(zf, rules)
        if best is None:
            decisions.append({
                "computed_index": k + 1, "frequency_GHz": f, "analytic": None, "analytic_GHz": None,
                "relative_error": None, "z_fraction": zf, "family": family, "consistent": None,
                "decision": "unmatched: no analytic mode within tolerance with free multiplicity",
            })
            continue
        rel, i = best
        capacity[i] -= 1
        m = candidates[i]
        consistent = _family_consistent(family, m)
        decisions.append({
            "computed_index": k + 1, "frequency_GHz": f, "analytic": m.label, "m": m.m, "n": m.n, "p": m.p,
            "analytic_GHz": m.frequency_GHz, "relative_error": (f - m.frequency_GHz) / m.frequency_GHz,
            "z_fraction": zf, "family": family, "consistent": consistent,
            "decision": ("matched" if consistent in (True, None) else "matched by frequency but probe family disagrees"),
        })
    return decisions


def height_mode_frequencies(decisions: list[dict[str, Any]], mode: tuple[int, int, int], box: CavityBox) -> list[float]:
    """The computed frequencies matched to the wanted mode and, for a square box, its twin."""
    m, n, p = mode
    labels = {f"analytic_{m}{n}{p}"}
    if abs(box.a_mm - box.b_mm) < 1e-12 and m != n:
        labels.add(f"analytic_{n}{m}{p}")
    return sorted(
        d["frequency_GHz"] for d in decisions
        if d.get("analytic") in labels and d.get("consistent") in (True, None)
    )


def height_shift(
    bench: HeightBenchmark,
    per_height: dict[str, list[RunResult]],
    decisions: dict[str, list[dict[str, Any]]],
    rules: dict[str, Any] = RULES,
) -> dict[str, Any]:
    """Δf_Palace versus Δf_exact for the wanted mode, with the verdict rules applied."""
    d1, d2 = bench.heights_mm
    box1, box2 = bench.box(d1), bench.box(d2)
    f_exact = {f"{d1:g}": box1.frequency(*bench.mode), f"{d2:g}": box2.frequency(*bench.mode)}
    delta_exact = f_exact[f"{d2:g}"] - f_exact[f"{d1:g}"]
    expected_count = 2 if (abs(box1.a_mm - box1.b_mm) < 1e-12 and bench.mode[0] != bench.mode[1]) else 1

    # Runs pair up by refinement LEVEL, not by mesh length: the declared mesh
    # rule is applied to each height separately and legitimately gives the two
    # heights different lengths at the same level (d/4 for one, min(a,b)/12
    # for the other).
    per_level: dict[int, dict[str, Any]] = {}
    executed = 0
    converged = 0
    for key, box in ((f"{d1:g}", box1), (f"{d2:g}", box2)):
        for r in per_height.get(key, []):
            if r.status in ("BLOCKED",):
                continue
            executed += 1
            level = r.level if r.level is not None else 0
            lvl = per_level.setdefault(level, {})
            if r.status != "CONVERGED":
                lvl[key] = {"status": r.status, "identified": [], "mesh_length_mm": r.mesh_length_mm,
                            "failure": (r.failure or "")[:200]}
                continue
            converged += 1
            found = height_mode_frequencies(decisions.get(r.name, []), bench.mode, box)
            lvl[key] = {"status": r.status, "identified": found, "mesh_length_mm": r.mesh_length_mm,
                        "mean_GHz": (sum(found) / len(found) if found else None)}
    base: dict[str, Any] = {
        "mode": list(bench.mode), "heights_mm": [d1, d2], "f_exact_GHz": f_exact,
        "delta_f_exact_GHz": delta_exact, "delta_f_exact_relative": delta_exact / f_exact[f"{d1:g}"],
        "levels": {}, "levels_executed": len(per_level), "levels_identified": 0,
    }
    base["per_level"] = {str(k): v for k, v in sorted(per_level.items())}
    if executed == 0:
        return {**base, "verdict": BLOCKED,
                "reasons": ["no run of this benchmark could be executed within the budget"]}
    if converged == 0:
        # Attempted for real and every attempt failed or timed out: the
        # benchmark is blocked on this runner, and that is a measurement.
        failures = [f"{key} L{level}: {v['status']} ({v.get('failure', '')[:90]})"
                    for level, lvl in sorted(per_level.items()) for key, v in lvl.items()]
        return {**base, "verdict": BLOCKED, "reasons": ["no attempted run converged within its budget"] + failures}

    levels_ok: list[tuple[int, float, float, float]] = []   # (level, lc_max, mean_h1, mean_h2)
    reasons: list[str] = []
    for level in sorted(per_level):
        lvl = per_level[level]
        a, b = lvl.get(f"{d1:g}"), lvl.get(f"{d2:g}")
        if not a or not b:
            reasons.append(f"level {level}: only one height executed")
            continue
        if a["status"] != "CONVERGED" or b["status"] != "CONVERGED":
            reasons.append(f"level {level}: {a['status']} / {b['status']}")
            continue
        if len(a["identified"]) != expected_count or len(b["identified"]) != expected_count:
            reasons.append(
                f"level {level}: mode {bench.mode} identified {len(a['identified'])}/{len(b['identified'])} times, "
                f"{expected_count} expected at each height"
            )
            continue
        levels_ok.append((level, max(a["mesh_length_mm"], b["mesh_length_mm"]), a["mean_GHz"], b["mean_GHz"]))

    out: dict[str, Any] = {
        **base,
        "levels": {
            f"L{level}": {"mesh_length_mm": [per_level[level][f"{d1:g}"]["mesh_length_mm"], per_level[level][f"{d2:g}"]["mesh_length_mm"]],
                          "f_palace_GHz": [m1, m2], "delta_f_palace_GHz": m2 - m1}
            for level, _, m1, m2 in levels_ok
        },
        "levels_identified": len(levels_ok),
    }
    if not levels_ok:
        out.update({"verdict": INCOMPLETE, "reasons": reasons or ["the wanted mode was not identified at both heights"]})
        return out

    level, lc, m1, m2 = levels_ok[-1]        # finest level with both heights identified
    delta_p = m2 - m1
    disagreement = abs(delta_p - delta_exact) / abs(delta_exact)
    out.update({
        "finest_level": level, "finest_level_mm": lc, "delta_f_palace_GHz": delta_p,
        "relative_disagreement": disagreement,
        "analytic_error_at_finest": [
            (m1 - f_exact[f"{d1:g}"]) / f_exact[f"{d1:g}"], (m2 - f_exact[f"{d2:g}"]) / f_exact[f"{d2:g}"]
        ],
    })
    if len(levels_ok) >= 2:
        _, _, p1, p2 = levels_ok[-2]
        u = max(abs(m1 - p1), abs(m2 - p2))
        out["numerical_uncertainty_GHz"] = u
        out["uncertainty_source"] = "max change of the identified mode between the final two mesh levels, over both heights"
    else:
        u = max(abs(m1 - f_exact[f"{d1:g}"]), abs(m2 - f_exact[f"{d2:g}"]))
        out["numerical_uncertainty_GHz"] = u
        out["uncertainty_source"] = "single level: bounded by the analytic error (no refinement executed)"
    out["shift_to_uncertainty_ratio"] = (abs(delta_exact) / u) if u > 0 else math.inf

    verdict = PASS
    if disagreement > rules["height_shift_relative_disagreement_max"]:
        verdict = FAIL
        reasons.append(f"Δf disagreement {disagreement:.3e} > {rules['height_shift_relative_disagreement_max']:.0e}")
    if out["shift_to_uncertainty_ratio"] < rules["height_shift_to_uncertainty_min_ratio"]:
        verdict = FAIL
        reasons.append(f"|Δf_exact| / uncertainty = {out['shift_to_uncertainty_ratio']:.2f} < {rules['height_shift_to_uncertainty_min_ratio']}")
    if verdict == PASS and len(levels_ok) < rules["height_levels_min_for_pass"]:
        verdict = INCOMPLETE
        reasons.append(f"only {len(levels_ok)} mesh level(s) identified the mode at both heights; {rules['height_levels_min_for_pass']} required for PASS")
    if verdict == PASS:
        reasons.append(
            f"Δf_Palace {delta_p:+.5f} GHz vs Δf_exact {delta_exact:+.5f} GHz (disagreement {disagreement:.2e}); "
            f"|Δf_exact| is {out['shift_to_uncertainty_ratio']:.0f}x the numerical uncertainty"
        )
    out.update({"verdict": verdict, "reasons": reasons})
    return out
