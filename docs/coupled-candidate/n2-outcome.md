# N2: refused on time. The DOF gate passed; the 45-minute cap did not.

**N2 did not complete.** It reached 100 % of the unchanged 2700 s cap while still
inside the eigensolve and was terminated as `TIMEOUT`. **That refusal is the
result.** No frequencies were produced, so the primary `N1 → N2` comparison is
**unavailable**, and nothing about stabilisation along the sequence can be said
in either direction.

This is the failure the proposal named as most likely, for the reason it gave:
the multigrid hierarchy deepens with the refinement depth, so cost does not track
DOF. The budget and solver configuration were **not** changed to rescue it.

Record: `results/COUPLED-LADDER-O1-L2-N2-20260917T103405Z`
(workflow run 35211061541, approved at commit `241cfe3`). Manifest intact.

---

## 1. Execution

| | measured |
|---|---|
| final finest-level order-1 DOF | **103 411** |
| DOF increase N1 → N2 | **+18 926** (+22.4 % on N1's 84 485) |
| DOF increase L2 → N2 | +23 467 (+29.4 % on 79 944) |
| within the 250 000 rule | **yes** — the DOF gate passed |
| wall clock | **2700.1 s — 100.0 % of the cap**, `timed_out = true` |
| Palace timing breakdown | **not available** — Palace was killed before it wrote its timer summary; `palace_metadata` and `palace_timers` are both absent |
| hierarchy depth | **3 levels**: 79 944 / 84 485 / 103 411 unknowns (auxiliary 13 991 / 14 667 / 17 447) |
| max backward error | **not available** — no eigenvalues were produced |
| manifest / evidence | **intact**; `post_solve_analysis_failed` is null |

**The DOF probe worked exactly as specified.** It read `ND (p = 1) = 103 411` at
**2.3 s**, a single unambiguous count (`dof_reported_all = [103411]`,
`ambiguous = false`, no reader error), from the finest space. 103 411 is well
inside 250 000, so the gate correctly did **not** refuse — the run was stopped by
the cap, not the budget.

**The hierarchy confirms the preparation's central claim empirically.** Level 1
of N2's own multigrid hierarchy is **84 485 unknowns — exactly N1's solved DOF**.
The source-level argument that iteration 0 of `Levels: 2` reproduces N1's single
stage is now corroborated by Palace's own output.

## 2. Primary comparison, N1 → N2

**Not available.** The solve did not reach an eigenvalue, so there is no mode
correspondence, no frequency, no participation of either kind, no energy
diagnostic, no backward error and no separation margin.

`baseline_comparison.available = false`, reason *"this run is TIMEOUT"*. Nothing
was repaired, substituted or estimated to fill the gap.

## 3. Sequence

| step | status |
|---|---|
| original L2 → N1 | **available** — recomputed read-only from two committed records |
| **N1 → N2** | **unavailable** — this run timed out |

**Whether the new `N1 → N2` changes are smaller, similar or larger than
`L2 → N1` cannot be stated.** The measurement does not exist. This is the one
question N2 was run to answer and it remains open.

`refinement_sequence.available` is **false**, keyed on the primary step alone —
with `earlier_steps_available = [true]` recorded separately, so the historical
step is not mistaken for the missing one.

## 4. Refinement behaviour

Measured from Palace's own refined-mesh statistics.

| | loaded L2 | N1 (1 level) | **N2 (2 levels)** |
|---|---|---|---|
| vertices | 13 991 | 14 667 | **17 447** |
| edges (order-1 DOF) | 79 944 | 84 485 | **103 411** |
| elements | 64 434 | 68 299 | **84 445** |
| min element size `h` (mm) | 0.00215083 | 0.00139897 | **0.000699484** |
| max `kappa` (quality) | 56.5643 | 56.5643 | **58.2487** |

- **Propagation beyond the marked region is substantial and compounds.** Stage 1
  marked 221 elements; octasection alone would add 1 547, but N1's mesh gained
  **3 865** — the conforming closure more than doubled the marked contribution.
  Stage 2 added a further **16 146** elements. Neither stage is confined to the
  box, as the preparation said.
- **Element quality degraded at depth 2, as anticipated.** Worst-case `kappa`
  was unchanged by the first level (56.5643, identical to the loaded mesh) but
  rose to **58.2487** at the second. Minimum `h` halved exactly (0.00139897 →
  0.000699484), which is what bisection of the marked set should do.
- **Physical tags and port connectivity remain intact.** After two levels Palace
  still configures the lumped port on attribute 10 with
  `Ls = 5.173e-08 H/sq`, `n = (0, 0, +1)` and `L = 1.035e-07 H` — **identical to
  N1's and the baseline's** — and Dirichlet PEC on attributes 2 and 4. The
  invariance argument for `w`, `l`, `L_s` and `κ` holds through a second level.
- **The multigrid hierarchy deepened automatically to three levels**, as
  disclosed before the run. No solver setting or preconditioner was changed.

**Wall clock must not be read as mesh-complexity scaling.** N2 used at least
2.92× N1's wall clock for 22.4 % more DOF — but the preconditioner hierarchy is
deeper, so the two runs do not solve the same problem per iteration. N1 already
established this, and N2's timing cannot separate the two effects. Palace's own
timers, which might have apportioned it, were never written.

## 5. What this establishes, and what it does not

**Measured:** N2's finest order-1 space is 103 411 DOF, comfortably inside the
250 000 rule; the refinement is nested with N1 as its middle hierarchy level;
physical tags and the port model survive two levels; element quality degrades
slightly at the second; and the solve exceeds the 45-minute cap.

**Not established, and not claimed:**

- **Nothing about stabilisation.** The primary comparison does not exist. The
  sequence question is open, not answered either way.
- **No global mesh convergence, no continuum limit, no order.** Unchanged, and
  N2 adds no evidence in any direction.
- **No causal attribution** of eigenvalue movement to the port face, and no
  additive regional error shares.
- **No physical validation or falsification of QMHP-CoPro.** Every number here is
  about the discretisation of a declared idealisation.
- **No claim that N2 is infeasible in principle** — only that it does not fit
  this cap under this configuration. What would change that is a separate
  question and a separate approval.

## 6. Disposition

**STOP**, as approved. One N2 attempt was made and it refused on time. The
budget, the cap, the tolerances and the solver configuration are unchanged, and
no rescue was attempted. R2 remains prepared and unapproved; no third level, no
rerun of N1, no coupling extraction, Route A or Route B, no `g`, no pulse, AMD-E,
decoder or mediator work, and no change to the physical candidate.
