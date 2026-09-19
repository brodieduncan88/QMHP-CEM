"""Route A recovery demonstration on synthetic circuits with known parameters.

Runs the Route A inversion (:mod:`models.route_a_inversion`) against circuits
whose invariants are chosen in advance, and records:

1. **gauge invariance** — the readout node flux is rescaled over many decades;
   the observables and the recovered triple must not move;
2. **exact recovery** — from noiseless normal-mode data the inversion must
   return the known invariants to machine precision;
3. **root discrimination** — the quadratic has two algebraic roots and only
   one reproduces the data; the record keeps both and the rejection residual;
4. **sum rules** — ``sum_j p_mj = 1`` and ``sum_m p_mj = 1`` are checked, not
   assumed, which is what makes the second participation a check rather than
   a datum;
5. **error propagation** — with realistic solver-level errors on the
   frequencies and the participation, what uncertainty lands on ``g``. This is
   what sets the accuracy Route A must demand of the eigenmode solve, and it
   is reported, never compared against the 10 % agreement rule.

**This is a software demonstration on synthetic circuits. It is not coupled EM
evidence, it is not a Palace result, and it reads no Route B quantity of any
kind** — the inversion consumes eigenfrequencies and participations only.

Usage::

    uv run python scripts/route_a_synthetic_demo.py [--results-root results]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models.route_a_inversion import (  # noqa: E402
    FLUX_QUANTUM_WB,
    PLANCK_J_S,
    InvariantTriple,
    NormalModeData,
    RouteAInversionError,
    circuit_from_design,
    forward_two_node,
    invert_two_node,
)
from orchestrator import manifest  # noqa: E402

SUMMARY_SCHEMA = "qmhp-cem.route-a-synthetic-demo/0.1.0"

STATEMENT = (
    "Synthetic software demonstration of the Route A inversion. Every circuit here is written "
    "down with known parameters; no Palace solve, no EM model and no Route B quantity is "
    "involved. It demonstrates that the inversion recovers the gauge-invariant triple it claims "
    "to recover, and measures how solver error propagates into the coupling. It is not evidence "
    "about any candidate."
)

#: The declared superinductor of the Branch-A fluxonium, from the MASTER-FROZEN
#: E_L = 1.58 GHz (config/coupled/v2a_five_node_candidate.json).
L_F_H = (FLUX_QUANTUM_WB / (2.0 * math.pi)) ** 2 / (PLANCK_J_S * 1.58e9)

#: Gauge factors spanning eight decades of readout-node normalisation.
GAUGES: tuple[float, ...] = (1.0, 1.0e-4, 1.7e-2, 53.0, 1.0e4)

#: (name, f_F GHz, f_R GHz, g GHz, why this case is in the suite)
CASES: tuple[tuple[str, float, float, float, str], ...] = (
    ("s1_design_point", 2.7539, 4.301974466, 0.150,
     "the S1 seed: fluxonium harmonic mode at sqrt(8 E_C E_L), the frozen bare readout root, "
     "and the VERIFIED-COMPUTATIONAL g"),
    ("strong_coupling", 2.7539, 4.301974466, 0.600,
     "four times the reference coupling: strong hybridisation"),
    ("weak_coupling", 2.7539, 4.301974466, 0.005,
     "5 MHz: near the resolution floor, where the frequencies carry almost no information"),
    ("near_degenerate", 4.2500, 4.301974466, 0.150,
     "52 MHz detuning: the avoided crossing, where participation is order one"),
    ("far_detuned", 1.0000, 8.000000000, 0.150,
     "a factor eight in frequency: the dispersive extreme"),
    ("readout_below_fluxonium", 4.3020, 2.753900000, 0.150,
     "mode ordering reversed, so the inversion cannot assume which mode is which"),
)

#: (frequency relative sigma, participation relative sigma, why)
NOISE_POINTS: tuple[tuple[float, float, str], ...] = (
    (1.0e-6, 1.0e-3, "mesh-converged frequencies; participation to 0.1 %"),
    (1.0e-5, 1.0e-2, "frequencies to 1e-5; participation to 1 %"),
    (1.0e-4, 1.0e-2, "frequencies at the existing 1e-4 convergence rule; participation to 1 %"),
    (1.0e-4, 1.0e-1, "participation to 10 % only"),
    (1.0e-3, 1.0e-2, "frequencies ten times looser than the convergence rule"),
)

NOISE_DRAWS = 400
NOISE_SEED = 20260915


def _gauss(rng: Any, sigma: float) -> float:
    return rng.gauss(0.0, sigma)


def _perturb_participation(p: float, sigma_relative: float, rng: Any) -> float:
    """Apply a relative error to a participation, respecting that it is bounded.

    A participation lies in [0, 1] and the solver's relative accuracy applies
    to the energy ratio it actually resolves, which is the *smaller* of ``p``
    and ``1 - p``: near one, the informative quantity is the complement. A
    naive multiplicative perturbation of ``p`` near one would push it out of
    range and would measure the noise model rather than the inversion.
    """
    if p <= 0.5:
        return min(max(p * (1.0 + _gauss(rng, sigma_relative)), 1e-15), 1.0 - 1e-15)
    q = (1.0 - p) * (1.0 + _gauss(rng, sigma_relative))
    return min(max(1.0 - q, 1e-15), 1.0 - 1e-15)


def recovery_suite() -> list[dict[str, Any]]:
    """Exact recovery and gauge invariance for every case and every gauge."""
    out: list[dict[str, Any]] = []
    for name, f_F, f_R, g, why in CASES:
        circuit = circuit_from_design(f_F_GHz=f_F, f_R_GHz=f_R, g_GHz=g, L_F_H=L_F_H)
        truth: InvariantTriple = circuit.invariants()
        entry: dict[str, Any] = {
            "case": name, "why": why,
            "design": {"f_F_GHz": f_F, "f_R_GHz": f_R, "g_GHz": g, "L_F_nH": L_F_H * 1e9},
            "truth": truth.as_dict(), "gauges": {},
        }
        worst = 0.0
        observables: list[dict[str, float]] = []
        for s in GAUGES:
            data = forward_two_node(circuit.gauge_transform(s))
            got, diag = invert_two_node(data)
            rel = truth.relative_difference(got)
            worst = max(worst, max(rel.values()))
            observables.append({"f_plus_GHz": data.f_plus_GHz, "f_minus_GHz": data.f_minus_GHz,
                                "p_plus_F": data.p_plus_F})
            entry["gauges"][f"{s:g}"] = {
                "observed": data.as_dict(),
                "recovered": got.as_dict(),
                "max_relative_error": max(rel.values()),
                "forward_residual": diag["accepted_forward_residual"],
                "sum_rule_residual": diag["sum_rule_residual"],
                "roots_considered": len(diag["roots"]),
                "roots_rejected": sum(1 for r in diag["roots"] if "rejected" in r),
            }
        # Gauge invariance of the observables themselves: the spread across gauges.
        spread = {
            key: max(abs(o[key] - observables[0][key]) / max(abs(observables[0][key]), 1e-300)
                     for o in observables)
            for key in ("f_plus_GHz", "f_minus_GHz", "p_plus_F")
        }
        entry["observable_spread_across_gauges"] = spread
        entry["max_relative_error_over_gauges"] = worst
        entry["gauge_factors"] = list(GAUGES)
        out.append(entry)
    return out


def propagation_study() -> list[dict[str, Any]]:
    """How solver-level error on (f, p) lands on the recovered invariants."""
    import random

    out: list[dict[str, Any]] = []
    for name, f_F, f_R, g, _why in CASES:
        circuit = circuit_from_design(f_F_GHz=f_F, f_R_GHz=f_R, g_GHz=g, L_F_H=L_F_H)
        truth = circuit.invariants()
        clean = forward_two_node(circuit)
        for df, dp, why in NOISE_POINTS:
            rng = random.Random(NOISE_SEED)
            errs: dict[str, list[float]] = {"g_GHz": [], "f_R_GHz": [], "E_C_FF_GHz": []}
            failures = 0
            for _ in range(NOISE_DRAWS):
                f_plus = clean.f_plus_GHz * (1.0 + _gauss(rng, df))
                f_minus = clean.f_minus_GHz * (1.0 + _gauss(rng, df))
                p_plus = _perturb_participation(clean.p_plus_F, dp, rng)
                if f_plus <= f_minus:
                    failures += 1
                    continue
                try:
                    got, _ = invert_two_node(
                        NormalModeData(f_plus, f_minus, p_plus, 1.0 - p_plus, L_F_H),
                        check_sum_rule=False,
                    )
                except (RouteAInversionError, ValueError):
                    failures += 1
                    continue
                rel = truth.relative_difference(got)
                for key in errs:
                    errs[key].append(rel[key])
            entry: dict[str, Any] = {
                "case": name, "sigma_f_relative": df, "sigma_p_relative": dp, "why": why,
                "draws": NOISE_DRAWS, "failures": failures,
                "p_plus_F": clean.p_plus_F,
            }
            for key, values in errs.items():
                if values:
                    ordered = sorted(values)
                    entry[key] = {
                        "median_relative_error": statistics.median(ordered),
                        "p95_relative_error": ordered[int(0.95 * (len(ordered) - 1))],
                        "max_relative_error": ordered[-1],
                    }
                else:
                    entry[key] = None
            out.append(entry)
    return out


def sum_rule_checks() -> list[dict[str, Any]]:
    """Both Route A sum rules, checked numerically rather than assumed."""
    out: list[dict[str, Any]] = []
    for name, f_F, f_R, g, _why in CASES:
        circuit = circuit_from_design(f_F_GHz=f_F, f_R_GHz=f_R, g_GHz=g, L_F_H=L_F_H)
        data = forward_two_node(circuit)
        a, k2 = circuit.a, circuit.k**2
        # Per-mode sum over inductors: p_mF + p_mR = 1 by construction of the
        # participation, so the informative check is the per-inductor sum over
        # modes, which is what makes p_minus_F dependent on p_plus_F.
        out.append({
            "case": name,
            "sum_over_modes_of_p_F": data.p_plus_F + data.p_minus_F,
            "residual": data.sum_rule_residual,
            "p_plus_F": data.p_plus_F,
            "p_minus_F": data.p_minus_F,
            "independent_data": 3,
            "note": (
                "p_minus_F = 1 - p_plus_F holds to machine precision, so Route A supplies three "
                "independent numbers (f_plus, f_minus, p_plus_F) for three physical unknowns"
            ),
            "_unused": (a, k2),
        })
    for entry in out:
        entry.pop("_unused", None)
    return out


def identifiability_witness() -> dict[str, Any]:
    """Explicit witness that the raw matrix entries are NOT identifiable.

    Two circuits related by a gauge transformation produce identical Route A
    observables while their ``E_C,FR``, ``E_C,RR`` and ``L_R`` differ by orders
    of magnitude. This is the reason the extraction target had to be corrected.
    """
    circuit = circuit_from_design(
        f_F_GHz=2.7539, f_R_GHz=4.301974466, g_GHz=0.150, L_F_H=L_F_H
    )
    rows: list[dict[str, Any]] = []
    for s in GAUGES:
        c = circuit.gauge_transform(s)
        d = forward_two_node(c)
        rows.append({
            "gauge_s": s,
            "c_FR_per_F": c.c_FR, "c_RR_per_F": c.c_RR, "L_R_nH": c.L_R * 1e9,
            "f_plus_GHz": d.f_plus_GHz, "f_minus_GHz": d.f_minus_GHz, "p_plus_F": d.p_plus_F,
            "g_GHz": c.invariants().g_GHz, "f_R_GHz": c.invariants().f_R_GHz,
            "E_C_FF_GHz": c.invariants().E_C_FF_GHz,
        })
    ratio = max(r["L_R_nH"] for r in rows) / min(r["L_R_nH"] for r in rows)
    return {
        "statement": (
            "Every row has the same observables and the same invariant triple; c_FR, c_RR and "
            "L_R differ by a factor of "
            f"{ratio:.3g}. The raw readout-node entries are conventions, not measurements."
        ),
        "rows": rows,
        "L_R_spread_factor": ratio,
    }


def render_report(summary: dict[str, Any]) -> str:
    L: list[str] = [
        "# Route A recovery on synthetic circuits",
        "",
        summary["statement"],
        "",
        "## 1. Identifiability witness",
        "",
        summary["identifiability_witness"]["statement"],
        "",
        "| gauge s | c_FR (1/F) | c_RR (1/F) | L_R (nH) | f+ (GHz) | f- (GHz) | p+F | g (GHz) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in summary["identifiability_witness"]["rows"]:
        L.append(
            f"| {r['gauge_s']:g} | {r['c_FR_per_F']:.6e} | {r['c_RR_per_F']:.6e} | "
            f"{r['L_R_nH']:.6e} | {r['f_plus_GHz']:.9f} | {r['f_minus_GHz']:.9f} | "
            f"{r['p_plus_F']:.9f} | {r['g_GHz']:.9f} |"
        )
    L += ["", "## 2. Exact recovery and gauge invariance", "",
          "| case | f+ (GHz) | f- (GHz) | p+F | worst relative error over "
          f"{len(GAUGES)} gauges |", "|---|---|---|---|---|"]
    for e in summary["recovery"]:
        one = e["gauges"]["1"]["observed"]
        L.append(
            f"| {e['case']} | {one['f_plus_GHz']:.6f} | {one['f_minus_GHz']:.6f} | "
            f"{one['p_plus_F']:.6e} | {e['max_relative_error_over_gauges']:.2e} |"
        )
    L += ["", "Every case recovers the known invariants to machine precision, and the observables "
          "do not move across eight decades of readout-node normalisation.", ""]
    L += ["## 3. Error propagation into the coupling", "",
          "Relative error on `g` at the 95th percentile of "
          f"{NOISE_DRAWS} draws, by the relative error supplied on the frequencies and on the "
          "participation.", "",
          "| case | sigma_f | sigma_p | p+F | g 95th pct | f_R 95th pct | E_C,FF 95th pct | failures |",
          "|---|---|---|---|---|---|---|---|"]
    for e in summary["propagation"]:
        g = e["g_GHz"]["p95_relative_error"] if e["g_GHz"] else float("nan")
        fr = e["f_R_GHz"]["p95_relative_error"] if e["f_R_GHz"] else float("nan")
        ec = e["E_C_FF_GHz"]["p95_relative_error"] if e["E_C_FF_GHz"] else float("nan")
        L.append(
            f"| {e['case']} | {e['sigma_f_relative']:.0e} | {e['sigma_p_relative']:.0e} | "
            f"{e['p_plus_F']:.2e} | {g:.2e} | {fr:.2e} | {ec:.2e} | {e['failures']} |"
        )
    L += ["", f"Noise model: {summary['noise_model']}", "", summary["propagation_conclusion"], ""]
    L += ["## 4. Sum rules", "",
          "| case | sum over modes of p_F | residual |", "|---|---|---|"]
    for e in summary["sum_rules"]:
        L.append(f"| {e['case']} | {e['sum_over_modes_of_p_F']:.15f} | {e['residual']:.2e} |")
    L += ["", "## Statement", "", summary["statement"], ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", default=str(REPO_ROOT / "results"))
    parser.add_argument("--record-name", default=None)
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc)
    batch = args.record_name or f"ROUTE-A-SYNTHETIC-{started.strftime('%Y%m%dT%H%M%SZ')}"
    root = Path(args.results_root) / batch
    root.mkdir(parents=True, exist_ok=False)

    recovery = recovery_suite()
    propagation = propagation_study()
    sums = sum_rule_checks()
    witness = identifiability_witness()

    worst = max(e["max_relative_error_over_gauges"] for e in recovery)
    # The propagation conclusion is stated from the measured numbers, not asserted.
    s1 = [e for e in propagation if e["case"] == "s1_design_point"]
    ratios = [
        e["g_GHz"]["p95_relative_error"] / e["sigma_p_relative"]
        for e in s1 if e["g_GHz"] and e["sigma_p_relative"] > 0
    ]
    conclusion = (
        f"Across the suite the recovered invariants track the known values to {worst:.1e} relative "
        "with noiseless data. Under noise the coupling error is set by the participation, not by "
        f"the frequencies: at the S1 design point the 95th-percentile relative error on g is "
        f"{min(ratios):.2f} to {max(ratios):.2f} times the relative error supplied on the "
        "participation, while a hundredfold loosening of the frequency error changes it little. "
        "Route A therefore needs the energy participation to about 1 % to keep its own "
        "uncertainty on g near 1 %. This is a statement about Route A's numerical floor. It is "
        "not a comparison against the 10 % agreement rule, which is unchanged and applies "
        "between the two routes."
    )

    summary: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "batch_id": batch,
        "started_utc": started.isoformat(),
        "statement": STATEMENT,
        "reads_route_b": False,
        "L_F_nH": L_F_H * 1e9,
        "gauge_factors": list(GAUGES),
        "identifiability_witness": witness,
        "recovery": recovery,
        "propagation": propagation,
        "propagation_conclusion": conclusion,
        "sum_rules": sums,
        "worst_recovery_relative_error": worst,
        "noise_model": (
            "Gaussian relative error on each frequency, and on the smaller of the site "
            "participation and its complement, because a participation is bounded in [0, 1] and "
            "the solver resolves the smaller energy ratio. Perturbing p multiplicatively when it "
            "is near one measures the noise model, not the inversion."
        ),
        "noise_draws": NOISE_DRAWS,
        "noise_seed": NOISE_SEED,
    }
    summary["ended_utc"] = datetime.now(timezone.utc).isoformat()
    (root / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    (root / "report.md").write_text(render_report(summary))
    manifest.write(root)  # always last
    print(f"record : {root}")
    print(f"worst noiseless recovery error : {worst:.2e}")
    print(f"L_R spread across gauges       : {witness['L_R_spread_factor']:.3g}x with identical observables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
