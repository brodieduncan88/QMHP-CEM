# N1R — N1's problem with N2R's solver, as a control

**What this is.** One control run: N1's discrete problem — the same baseline mesh file, the same
one-level `Model.Refinement.Boxes` prescription, the same element order, tolerances and eigenvalue
target — plus the one `Solver.Linear` key N2R used, `MGMaxLevels: 1`.

**Why.** `n2r-outcome.md` §5 reports the N1 → N2R step as *not preconditioner-controlled*: N1 ran a
two-level V-cycle where N2R ran one level with the preconditioner applied directly. N1R removes that
difference. With it on disk the sequence **L2 (1 level, unrefined) → N1R (1 level) → N2R (1 level)**
has the same solver strategy at every point, and **N1 vs N1R** is the same discrete problem under
two solver paths — a direct measurement of the solver-path effect that §5 could only caveat.

**What this is not.** Not a new refinement level, not R2, not a re-interpretation of N1. No change
to the mesh, order, tolerances, eigenvalue target, DOF budget or cap.

## 1. The delta, by diff

`config.candidate.json` is the config N1 solved plus one key. `diff
results/COUPLED-LADDER-O1-L2-N1-20260917T001735Z/L2/solver/config.json
experiments/N1R-controlled-preconditioner/config.candidate.json`:

```
104c104,105
<       "MaxIts": 400
---
>       "MaxIts": 400,
>       "MGMaxLevels": 1
```

The mechanism and its source-level verification are those of the N2R approval and are not
repeated here: `n2-runtime-diagnosis.md` §6 and `n2r-rescue-run.md` §2–3. N2R then confirmed them by
measurement (`n2r-outcome.md` §1–2).

## 2. What N1R must reproduce

N1 ran this mesh and box, so these are predictions, not estimates:

| quantity | expected | source |
|---|---|---|
| `ND (p = 1)` on the header line | **84,485** | N1's probe |
| mesh counts V / E / F / T | **14,667 / 84,485 / 138,118 / 68,299** | N1's `Refined Parallel Mesh Stats` |
| print shape | one un-prefixed `Parallel Mesh Stats` block | `geodata.cpp:394-400` at `mesh.size() == 1`, as N2R printed |
| multigrid hierarchy | `Level 0` only | as N2R printed |

`V − E + F − T = 1` is necessary, not sufficient; the hash gate plus the identical box is the
guarantee and the counts cross-check it. No runtime is predicted: N2R solved a larger problem on
this configuration in 159.0 s, which is context, not a prediction.

## 3. Comparisons

**Computed by the run:** original L2 → N1R. `baseline_record` is the plain L2 rung, exactly as
N1's was — N1 is at equal depth and the driver refuses it as a baseline by design.
`sequence_records` is deliberately empty: a one-level run's sequence *is* its baseline comparison,
and naming the plain rung there would print a report banner saying the step is "not against a
plain rung", which for N1R is exactly what it is.

**Computed offline afterwards**, by `scripts/controlled_sequence_comparison.py`, written to
`experiments/N1R-controlled-preconditioner/controlled-comparison.json` and never inside a
`results/` record:

* **N1R → N2R** — through the driver's own `compare_against_baseline` with N1R as the baseline
  and N2R's committed record as the entry: the same matching rule, magnitude convention and frozen
  tolerances, and the same preconditioner-level disclosure, which should now read *same on both
  sides*. Offline because the driver only compares a run against a *shallower* baseline at run
  time, and N2R is deeper than N1R. Checked before the run: the same call with N1 as the baseline
  reproduces N2R's committed comparison exactly.
* **N1 vs N1R** — the same discrete problem: mesh hash, box and solved DOF are asserted equal,
  and the two *solved* `config.json` files are read and must differ in nothing but
  `Solver.Linear.MGMaxLevels` (N1 vs N2R is refused by that check) — under the same `match_runs`
  rule. The script refuses any output path under `results/` and any `--n1r` record that is not the
  N1R control. Every difference is
  solver-path effect, up to the convergence tolerances both runs met. Checked before the run:
  N1 vs N1 gives zero.

## 4. What it will and will not establish

**If it completes:** whether the N1 → N2R movements reported in `n2r-outcome.md` §3 survive with the
preconditioner held fixed, and how large the solver-path effect is on an identical problem.

**Not established, whatever it shows:** any order of convergence or continuum limit — two steps,
local refinement; global mesh convergence; causal attribution to the port face; anything about the
physics N1 was not already approved to ask.

## 5. Status

**Executed.** COMPLETED in 110.7 s, 4.1 % of the cap, at exactly the predicted 84,485 DOF and
+4,541 added, on a mesh Palace printed with exactly the four predicted counts in a single
un-prefixed block with a one-level hierarchy. The solver-path effect it measures is ~5e-09
relative. See [`n1r-outcome.md`](n1r-outcome.md).
