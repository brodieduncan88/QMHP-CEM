# N1: the first nested refinement, and what it does and does not attribute

**The run completed and every control held.** The mesh file was reused
byte-identically, the config delta was one block, the DOF probe read the solved
count 2.8 s in, and the offline lower bound held. The fluxonium-like mode moved
**+0.053867 GHz** on a refinement of **+4 541 DOF (+5.7 %)**.

**That movement is attributable to added degrees of freedom in the refined
region — and not to port-face resolution.** The region is a volume, the
conforming closure refines elements outside it, and the marked elements are the
worst-shaped in the mesh, so element quality is a live alternative this run
cannot separate. Two points establish no order of convergence and none is
claimed. **The numerical convergence the ladder was meant to demonstrate remains
unestablished.**

Record: `results/COUPLED-LADDER-O1-L2-N1-20260917T001735Z`
(workflow run 35165805220, approved at commit `7f328b1`).

---

## 1. The controls held

| control | result |
|---|---|
| mesh file | `sha256 d8dc1a92…` — **byte-identical to the baseline**, gate passed before launch |
| config delta | `Model.Refinement.Boxes` and nothing else |
| DOF loaded → solved | 79 944 → **84 485** (+4 541, +5.7 %) |
| offline lower bound | 81 864 — **held**; the closure added 2 621 beyond the marked set |
| budget | 84 485 against 250 000 |
| DOF probe | count read at **2.8 s**, line-buffered, no reader error |
| max backward error | **8.76e-11**, four orders inside the unchanged 1e-6 |
| admitted / separation | m1, m2 — **4.944 decades** |
| derived probe-vs-closure | **1.40e-06** worst of 6 modes |

The probe timing is worth recording because the first implementation would have
got it wrong. Palace does not flush its output, so over a pipe the count would
not have surfaced until well into the eigensolve; running Palace under
`stdbuf -oL` is what made "read it during assembly" true rather than merely
claimed. `seen_at_wall_s = 2.8` is the evidence, not the intention.

## 2. What moved

| tracked mode | role | baseline | **N1** | Δf |
|---|---|---|---|---|
| m1 | LUMPED_DOMINATED | 1.461887 | **1.515754 GHz** | **+0.053867** |
| m2 | FIELD_DOMINATED | 3.885511 | **3.887132 GHz** | **+0.001620** |

Against the ladder's own L2→L3 step the ratios are **0.2175** and **0.0080**.
As with R1, these are **ratios of observed frequency changes**, not causal
shares and not upper bounds on a port contribution.

## 3. Three things N1 does that R1 could not

R1 regenerated its mesh, and 18.4 % of the baseline's vertices did not survive.
N1 reuses the mesh file. The differences that follow are measured, not argued.

| | baseline | R1 (non-nested) | **N1 (nested)** |
|---|---|---|---|
| m1 energy-balance defect `\|R−1\|` | 3.351e-05 | 4.119e-05 (**worse**) | **1.137e-05 (better)** |
| admission separation | 4.4748 | 4.3852 (**worse**) | **4.9443 (better)** |
| m2 direction | — | **opposite** to m1 | **same** as m1 |
| m2 vs a port-mediated prediction | — | **149× too large** | **14× too large** |

The last row is the substantive one. A first-order shift through a
positive-definite port term should scale with each mode's port participation
(`p₂/p₁ = 7.81e-04`), predicting ≈ +1.1e-04 GHz for m2. R1 gave −1.83e-02 — two
orders out and the wrong way. N1 gives +1.62e-03 — **the right direction, and
one order out instead of two.**

That is consistent with R1's non-nested re-meshing having injected a
perturbation that dominated the small mode, and is the clearest evidence so far
that **R1's mode-2 anomaly was an artefact of its mechanism rather than physics**.
It does **not** vindicate the port mechanism: 14× is still an order of magnitude,
so mode 2's movement is still not accounted for by port participation alone.

## 4. The awkward measurement

N1 is a **weaker** port-face refinement than R1, by the field measure:

| | port-face normal-field fraction `p_MA/p_Default` | m1 Δf |
|---|---|---|
| baseline | 0.006402 | — |
| **N1** | **0.025533** | +0.053867 GHz |
| R1 | 0.105803 | +0.059116 GHz |
| L3 | 0.100041 | (+0.247675, global) |

N1 reaches about a quarter of R1's face fraction and moves m1 by about
**91 %** as much. The frequency movement does not track the port-face measure.
Recorded as an observation on two runs with different mechanisms — it is **not**
a controlled comparison, and it is not evidence for a mechanism. It does sit
badly with the idea that port-face resolution is what drives the movement.

## 5. The confound that showed up in the timers

`Model.Refinement` is not solver-neutral. Palace keeps the coarse mesh, so N1
ran a **two-level geometric multigrid** preconditioner where the baseline ran
one. The cost is not subtle:

- wall clock **923.5 s** against the baseline's 81.2 s — **11.4× for 5.7 % more DOF**
- of which **635.6 s (69 %) is preconditioner application**, over 622 coarse solves
  where the baseline had none

So **the wall-clock comparison is not like-for-like** and must not be read as the
cost of the refinement. Frequencies are unaffected. This was predicted from the
source before the run and is recorded here because the timers confirmed it.

## 6. What this does not establish

- **No attribution to the port face.** The refined region is a volume; the
  conforming closure refines elements outside it (2 621 of the 4 541 added DOF
  are beyond the marked set); and the marked tets average radius-ratio 0.2197
  against the mesh's 0.3700, so element quality is unseparated from resolution.
- **No convergence.** Two points. The ladder's order remains unestablished, and
  §3's improvements in defect and separation are single-step observations, not a
  trend.
- **No physical claim.** Every number is about the discretisation of a declared
  idealisation.
- **Mode 2 is still not explained.** One order of magnitude closer to the
  port-mediated prediction is not agreement with it.

## 7. Disposition

**STOP**, as approved. N1 is a diagnostic run, not a ladder rung: it is excluded
from the convergence fit and compared against the plain rung at its own level. A
second refinement level is a separate approval and the driver will not start one.
R2 remains prepared and unapproved. No coupling extraction, Route A inversion,
Route B, pulse work, AMD-E or mediator work; the DOF rule, the 45-minute cap and
every tolerance are unchanged.
