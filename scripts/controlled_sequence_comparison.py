"""The solver-controlled refinement sequence: L2 -> N1R -> N2R, and N1 vs N1R.

N2R's committed record compares it against N1, which ran a two-level multigrid
V-cycle where N2R ran one level with the preconditioner applied directly. That
step is therefore not preconditioner-controlled, and the record says so. N1R is
N1's discrete problem re-solved with the same one-level configuration N2R used,
so with it on disk two comparisons become available that no committed record
computes:

* N1R -> N2R -- the same refinement step, same solver strategy on both sides.
  Computed with the driver's own ``compare_against_baseline``, so the matching
  rule, the magnitude convention and the frozen tolerances are the unchanged
  ones and nothing here re-decides an admission.
* N1 vs N1R -- the SAME discrete problem under two solver paths. This is the
  empirical size of the solver-path effect the N1 -> N2R comparison could only
  caveat; ``compare_against_baseline`` refuses equal-depth pairs by design, so
  the two runs are matched here with the same ``match_runs`` rule and the
  differences reported per mode.

Historical records are read, never modified. The output is written beside the
N1R candidate, not inside any results/ record, so no manifest is disturbed.

    uv run python scripts/controlled_sequence_comparison.py \\
        --n1r COUPLED-LADDER-O1-L2-N1R-<stamp>
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

N1_RECORD = "COUPLED-LADDER-O1-L2-N1-20260917T001735Z"
N2R_RECORD = "COUPLED-LADDER-O1-L2-N2R-20260918T061455Z"
L2_RECORD = "COUPLED-LADDER-O1-L2-20260916T080802Z"
OUT = REPO_ROOT / "experiments" / "N1R-controlled-preconditioner" / "controlled-comparison.json"


def _ladder():
    spec = importlib.util.spec_from_file_location(
        "palace_order1_ladder", REPO_ROOT / "scripts" / "palace_order1_ladder.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rung(record: str) -> dict:
    return json.loads((REPO_ROOT / "results" / record / "summary.json").read_text())["rung"]


def _flatten(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def _config_delta(a_record: str, b_record: str) -> list[str]:
    """Dotted paths at which the two SOLVED config.json files differ."""
    def load(record):
        path = REPO_ROOT / "results" / record / "L2" / "solver" / "config.json"
        return dict(_flatten(json.loads(path.read_text())))
    fa, fb = load(a_record), load(b_record)
    return sorted(k for k in set(fa) | set(fb) if fa.get(k, object()) != fb.get(k, object()))


def _require_n1r_control(record: str) -> dict:
    """Refuse, before anything is written, unless the record IS the N1R control."""
    path = REPO_ROOT / "results" / record / "summary.json"
    if not path.is_file():
        raise SystemExit(f"{record} is not a record on disk")
    rung = json.loads(path.read_text())["rung"]
    ref = rung.get("palace_refinement") or {}
    boxes = ref.get("boxes") or []
    override = (ref.get("solver_linear_overrides") or {}).get("MGMaxLevels")
    problems = []
    if ref.get("id") != "N1R":
        problems.append(f"palace_refinement.id is {ref.get('id')!r}, not 'N1R'")
    if override != 1:
        problems.append(f"MGMaxLevels override is {override!r}, not 1")
    if [b.get("Levels") for b in boxes] != [1]:
        problems.append(f"box Levels are {[b.get('Levels') for b in boxes]}, not [1]")
    if problems:
        raise SystemExit(f"{record} is not the N1R control: " + "; ".join(problems))
    return rung


def _guarded_output_path(raw: str) -> Path:
    """Never inside results/: a committed record is history and stays that way."""
    out = Path(raw).resolve()
    results = (REPO_ROOT / "results").resolve()
    if out == results or results in out.parents:
        raise SystemExit(f"refusing to write {out}: outputs never go inside results/")
    return out


def same_problem_two_solver_paths(ladder, a_record: str, b_record: str) -> dict:
    """Per-mode differences between two runs of the SAME discrete problem."""
    from solvers.palace.mode_admission import match_runs  # noqa: PLC0415

    a, b = _rung(a_record), _rung(b_record)
    for name, r in ((a_record, a), (b_record, b)):
        if r.get("status") != "COMPLETED":
            return {"available": False, "reason": f"{name} is {r.get('status')}"}
    # The control is only a control if the two solved the same mesh and box.
    identity = {
        "mesh_sha256_equal": a["mesh"]["sha256"] == b["mesh"]["sha256"],
        "boxes_equal": a["palace_refinement"]["boxes"] == b["palace_refinement"]["boxes"],
        "dof_solved_equal": ladder.solved_dof(a) == ladder.solved_dof(b),
        "config_differs_only_in": _config_delta(a_record, b_record),
        "multigrid_levels": [ladder.multigrid_levels(a), ladder.multigrid_levels(b)],
    }
    # Not inferred from upstream guarantees: the two solved config.json files
    # are read and must differ in nothing but the preconditioner keys.
    identity["configs_equal_outside_preconditioner"] = set(
        identity["config_differs_only_in"]
    ) <= {"Solver.Linear.MGMaxLevels", "Solver.Linear.MGUseMesh"}
    if not all(identity[k] for k in (
        "mesh_sha256_equal", "boxes_equal", "dof_solved_equal", "configs_equal_outside_preconditioner"
    )):
        return {"available": False, "reason": "not the same discrete problem", "identity": identity}

    floor = ladder.COUPLED_SOLVER_RULES["band_floor_GHz"]
    ceiling = ladder.COUPLED_SOLVER_RULES["band_ceiling_GHz"]
    ma = ladder.rebuild_admitted(a["admission"]["modes"], floor, ceiling)
    mb = ladder.rebuild_admitted(b["admission"]["modes"], floor, ceiling)
    match = match_runs(f"{a_record} vs {b_record}", ma, mb)
    out = {
        "available": match.comparable,
        "what": (
            "the SAME discrete problem - same mesh file, same box, same solved DOF - under two "
            "solver paths. Every difference here is solver-path effect, up to the convergence "
            "tolerances both runs met. It is NOT a refinement effect."
        ),
        "a": a_record, "b": b_record,
        "identity": identity,
        "match": match.as_dict(),
        "pairs": [],
    }
    if not match.comparable:
        out["reason"] = f"{match.status}: {match.reason}"
        return out
    for pair in match.pairs:
        out["pairs"].append({
            "mode": pair.a.mode,
            "f_a_GHz": pair.a.frequency_GHz,
            "f_b_GHz": pair.b.frequency_GHz,
            "delta_f_GHz": pair.b.frequency_GHz - pair.a.frequency_GHz,
            "delta_f_relative": pair.delta_f_relative,
            "delta_abs_p_relative": pair.delta_abs_participation_relative.get(1),
            "backward_error": [pair.a.backward_error, pair.b.backward_error],
        })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n1r", required=True, help="the N1R record id under results/")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args(argv)

    out_path = _guarded_output_path(args.out)
    n1r = _require_n1r_control(args.n1r)
    ladder = _ladder()
    n2r = _rung(N2R_RECORD)

    # The controlled step, through the driver's own comparison. Baseline = N1R,
    # entry = N2R, exactly as a run would compute it had N1R existed first.
    controlled = ladder.compare_against_baseline(n2r, args.n1r)
    # And the step below it, from N1R's own record, so the whole solver-
    # controlled sequence is in one place.
    lower = (json.loads((REPO_ROOT / "results" / args.n1r / "summary.json").read_text())
             .get("baseline_comparison") or {})

    result = {
        "schema": "qmhp-cem.controlled-sequence-comparison/0.1.0",
        "records": {"L2": L2_RECORD, "N1": N1_RECORD, "N1R": args.n1r, "N2R": N2R_RECORD},
        "multigrid_levels": {
            k: ladder.multigrid_levels(_rung(v))
            for k, v in (("L2", L2_RECORD), ("N1", N1_RECORD), ("N1R", args.n1r), ("N2R", N2R_RECORD))
        },
        "sequence_L2_to_N1R": {
            "available": bool(lower.get("available")),
            "reason": lower.get("reason") if not lower.get("available") else None,
            "baseline": lower.get("baseline"),
            "preconditioner": lower.get("preconditioner"),
            "pairs": lower.get("pairs"),
            "source": f"results/{args.n1r}/summary.json baseline_comparison, as the run computed it",
        },
        "sequence_N1R_to_N2R": controlled,
        "same_problem_N1_vs_N1R": same_problem_two_solver_paths(ladder, N1_RECORD, args.n1r),
        "not_established": [
            "any order of convergence or continuum limit: two steps and a local refinement",
            "global mesh convergence",
            "causal attribution to the port face",
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=1) + "\n")

    print(f"multigrid levels: {result['multigrid_levels']}")
    for name in ("sequence_L2_to_N1R", "sequence_N1R_to_N2R"):
        block = result[name]
        pc = block.get("preconditioner") or {}
        print(f"{name}: available={block.get('available')} "
              f"same_preconditioner_on_both_sides={pc.get('same_on_both_sides')}")
        for p in block.get("pairs") or []:
            print(f"   m{p['baseline_mode']}: {p['baseline_frequency_GHz']:.6f} -> "
                  f"{p['refined_frequency_GHz']:.6f}  df={p['delta_f_GHz']:+.6f} GHz  "
                  f"df_rel={p['delta_f_relative']:.4e}  d|p|_rel={p.get('delta_abs_p_relative')}")
    sp = result["same_problem_N1_vs_N1R"]
    print(f"same_problem_N1_vs_N1R: available={sp.get('available')} identity={sp.get('identity')}")
    for p in sp.get("pairs") or []:
        print(f"   m{p['mode']}: {p['f_a_GHz']:.6f} -> {p['f_b_GHz']:.6f}  "
              f"df={p['delta_f_GHz']:+.3e} GHz  df_rel={p['delta_f_relative']:.3e}  "
              f"d|p|_rel={p['delta_abs_p_relative']}")
    print(f"written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
