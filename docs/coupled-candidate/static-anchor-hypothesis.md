# The static-anchor hypothesis

**HYPOTHESIS RECORD.** The electrostatic comparison it proposes is
**PREPARED, NOT APPROVED, NOT EXECUTED**: no static capacitance has been computed on the QMHP mesh.
Nothing here changes the first-moment diagnostic, Route A, the registered definitions or
any historical record. `E_C,F1F1` and `g` stay **UNAVAILABLE**.
Record: `experiments/static-anchor-hypothesis/`.

## 1. The hypothesis, and the reading it competes with

**The existing reading (H0).** `E_C` is fixed by `a/N` (`fem-spectral-mapping.md` §7). The
band sum over the saved modes is a *truncation* of the complete first moment, and the
dominant uncertainty is where the missing weight sits (`normalisation.md`: +4.5 % to +85 %
for 12–50 GHz placements). `first-moment.md` recommends evaluating `A` directly because
its difference from `A_partial` "IS the omitted first moment", and calls `A` "the
better-posed of the two".

**The hypothesis (H1).** The first moment is a maximum over field shapes:

    A = fᵀM⁻¹f / L = max over fields y of (f·y)² / (yᵀM y) / L

It asks for the largest squared port voltage per unit stored electric energy.

- **Over all fields** — the complete first moment — it has no continuum limit for a
  sheet-shaped port, because a field squeezed into a thinner and thinner layer against the
  port face keeps its voltage while its energy vanishes.
- **Over curl-free fields only**, `y = G φ`, the same maximum is `1/C`, where `C` is the
  electrostatic (Maxwell) capacitance of the island. That is the kind of quantity the
  registered `E_C` is defined from (`coupling-definition.md` §2).

H1 claims the band estimate approximates the second quantity, not a truncation of the
first.

**Where they agree.** Both hold that the direct run is correct *for its mesh*, that the
Parseval identity is exact there, and that far-mode weight can carry a large first moment
(`first-moment.md` correction 1).

## 2. Measurements

The classes are kept apart. **A** means Palace wrote it into a committed record or run
log. **B** is arithmetic on A only. **C** is independent code in this record, re-run from
committed inputs while preparing it. **D** was produced earlier in the session and not
re-run here. Every value is in `measurements.json` with its source.

| class | measurement | value |
|---|---|---|
| A | certified lower bound on the omitted moment, run 35730927756 (run 2, `ae9ff1f`) | ≥ 1420.315 GHz² |
| A | band `a/N` under port-box refinement 0 → 1 → 2 (L2, N1R, N2R) | 2.1484 → 2.3099 → 2.3533 GHz² |
| A | band `a/N` on L3, a different mesh | 2.9412 GHz² |
| B | direct first moment, N2R | 1422.6665 ± 0.0005 GHz² |
| B | omitted participation weight (window proven in `normalisation.md`) | at most 7.454e-4 |
| B | participation-weighted RMS frequency of the omitted modes | at least 1380 GHz |
| C | **guaranteed lower bound** on the first moment, uniform red refinement 0 → 1 → 2 | **340.13 → 659.72 → 1324.09 GHz²** (×1.940, ×2.007) |
| C | conductors on the committed mesh | exactly two: ground and walls (9244 nodes), island (189 nodes, 0.15 × 0.15 mm); the port face touches both |
| C | vectorised assembly vs compiled Palace on the committed fixture | `A_nd` 64.16250164577235 vs 64.16250164577238 (4.4e-16) |
| C | synthetic slab (known answer): static capacitance vs exact | 3.7e-16 and 1.2e-14; **unchanged** by refinement |
| C | the same slab: complete first moment under one refinement | **×2.207** |
| C | synthetic fringing case: C₁/C₀ under nested refinement | 0.953 (must be ≤ 1) |
| C | negative control: the same case with the port edges between grid lines (a staircase port) | port voltage 0.9, so the two routes differ by exactly 1 − 0.9² = 0.19 while the energy identity holds (1.7e-13); aligned, 1.0 and 1e-13 |
| C | budget dry run, synthetic stand-in larger than the QMHP level 1 (560k and 768k tets vs 515k), under the declared limits | 103 s and 229 s wall, 2.9 and 4.2 GB peak RSS, 4.2 and 5.5 GB peak address space |
| D | exact complete first moment, base mesh | 367.8795 GHz² |
| D | share of it recovered by a field living only on the 39 port-face edges | 84 % (92 % with one ring of neighbours) |
| D | Palace base → box-2 ratio vs uniform-bound level 0 → 2 ratio | 3.867 vs 3.893 |

Also relevant and already in the record: `fem-spectral-mapping.md` §4 identifies five of
N2R's saved modes as *port-operator-localised* artefacts of the sheet port. They moved
from 7.2–9.5 GHz (N1R) to 10.2–11.8 GHz (N2R) under port refinement.

## 3. Mathematics

Each item is labelled by what kind of claim it is.

1. **Rayleigh characterisation — rigorous.** For symmetric positive-definite `M`,
   `fᵀM⁻¹f = max_y (f·y)²/(yᵀMy)`, so any trial space gives a lower bound. This is what
   makes the class-C bounds guarantees rather than estimates.
2. **No continuum limit for the complete moment — standard argument, sketched.** Let
   `V(E) = (1/w)∫_S E·d̂ dS` be the port functional. Take `E_t = d̂ ψ(z/t) η(x, y)`, with
   `ψ` a fixed smooth profile across the face and `η` cutting off within `δ` of the
   conductor edges, so the PEC condition holds. Then `V(E_t)` stays close to `l`, while
   `‖E_t‖²` is at most `ε_max·|S|·t·∫ψ²`, which tends to 0 as `t → 0`. So the supremum is
   infinite, and discrete maxima grow as the mesh at the port refines. The class-C bounds
   show that growth on the real geometry.
3. **Curl-free restriction gives the Dirichlet capacitance — rigorous on the discrete
   space.** For P1 `φ`, `G φ` is exactly the Whitney representation of `∇φ` (de Rham), so
   `(Gφ)ᵀM(Gφ) = ∫ε|∇φ|²`. The maximiser over P1 `φ`, constant on each conductor, is the
   Dirichlet solution. When the port face runs from ground to the island, `f·Gφ` is the
   potential difference across it. Hence
   `max_φ (f·Gφ)²/((Gφ)ᵀMGφ) = 1/C_h`. The synthetic controls confirm it: port voltage 1,
   and the two energy routes agree to 1e-14.
4. **Monotonicity and bounds — rigorous.** Nested refinement cannot raise `C_h`, and
   `C_h ≥ C` (the continuum value). So each `S_h = 1/((2π)² L C_h)` is a lower bound on
   its continuum limit. Every `S_h` is also at most the complete moment on the same mesh,
   since it is a restricted maximum.
5. **Schur complement — rigorous algebra.** For a positive-definite Maxwell matrix,
   `(C⁻¹)_FF ≥ 1/C_FF`, with equality only when there is no island–readout mutual
   capacitance.
6. **Bounded lower moments — rigorous (existing).** `N ≤ 1` (`normalisation.md`), and
   `Σ p/λ ≤ N/λ₁`. The complete *first* moment is the one moment in this family without
   a continuum limit for the sheet port.

## 4. Predictions — untested

- **P1:** the static quantity `S` is of the same order as the band estimate on the same
  mesh (the decisive prediction).
- **P2:** `S` changes little under one refinement, unlike the complete moment's ×1.94.
- **P3:** under the lumped two-node reduction, `S ≤ B` (item 5). This is diagnostic only,
  because `B` has its own discretisation bias.
- **P4:** the complete moment keeps roughly doubling beyond level 2. Not tested, and not
  needed for the decision.

Agreement with the band estimate is a **prediction, not a target**. `C_h` has no
adjustable parameter and is computed without reading the band value.

## 5. The prepared test

**What it measures.** The discrete Maxwell self-capacitance `C_h` of the island, with every
other conductor grounded, on the committed mesh (`d8dc1a92…`) and on one uniform red
refinement of it (nested). It is reported as `S_h = 1/((2π)² L_F C_h)` in GHz². `S_h` is
also recomputed as the curl-free-restricted first-moment quotient, using the diagnostic's
own `M` and `f`; the two routes must agree.

**How it relates to the registered charging energy.**

    e²/(2 C_h)  ≤  e²/(2 C_FF)  ≤  e²(C⁻¹)_FF/2 = E_C,F1F1

- The first inequality is the Dirichlet principle.
- The middle identification (`C = C_FF`) rests on **assumption A-R**: the readout is one
  connected, DC-grounded conductor on this mesh, standing in for node R1 held at zero.
- The last inequality is the Schur complement. Its gap, `1/(1 − k²)`, is **not measured**,
  and must not be taken from the conditional Route A coupling.

So the test gives a **lower bound** on `E_C,F1F1` under A-R, never `E_C,F1F1` itself.

**Outcomes** (frozen in `predeclaration.json`; `r0 = S0/B0` with `B0` = 2.1484 GHz² from
the L2 rung on the same mesh; `ρ = S1/S0`):

| condition | outcome |
|---|---|
| any integrity failure (port voltage ≠ 1, identity > 1e-9, residual > 1e-10, `C` rising under nesting, `S0` > 367.88, any digest mismatch) | UNQUALIFIED — no verdict |
| `ρ ≥ 1.9` | WEAKENS H1: static grew like the divergent moment |
| `1.25 < ρ < 1.9` | UNRESOLVED: static not resolved on the base mesh |
| `ρ ≤ 1.25` and `0.5 ≤ r0 ≤ 2` | SUPPORTS H1 |
| `ρ ≤ 1.25` and `2 < r0 ≤ 20` or `0.05 ≤ r0 < 0.5` | WEAKENS H1: the band does not track the static quantity |
| `ρ ≤ 1.25` and `r0 > 20` | CONTRADICTS H1, favours H0 (the complete moment is 171 × `B0` here) |
| `ρ ≤ 1.25` and `r0 < 0.05` | CONTRADICTS H1; does not favour H0 |

**Run parameters.**

- **Gate:** refuses unless `TEST-APPROVAL.json` binds the mesh, the pre-declaration and
  the code by sha256. `TEST-APPROVAL.draft.json` is the reviewed draft. It authorises
  nothing, and a test fails if its digests stop matching the files.
- **One attempt:** the record directory is created before any solve, and its existence
  spends the attempt.
- **Budget:** 10 CPU-minutes, 8 GB, a 30-minute wall cap. No retry, no further level, no
  window change. The budget is enforced in the process once the attempt is spent (CPU and
  address-space limits, a wall-clock alarm), and the command carries an outer hard kill:
  `timeout --signal=KILL 1860 .venv/bin/python experiments/static-anchor-hypothesis/static_capacitance.py`,
  run locally from the repository root. There is no workflow and no network. If this
  environment cannot apply the budget, the run refuses *before* the attempt is spent.
- **Failure is evidence:** any exception or limit writes `failure.json` beside the raw
  levels already written, and the attempt stays spent.
- **Size:** 4,558 unknowns at level 0 and 60,608 at level 1 (from the preflight, which
  solves nothing). A larger synthetic stand-in ran well inside the budget (§2). The QMHP
  run's own cost is not known until it runs.

**Not combined with anything.** `C_h` and `S_h` must not be combined with `g`, `f_R` or any
Route A output until a circuit model is declared that consistently defines `C_FF`, the
band modes, the DC-grounded distributed readout and `k²`.

## 6. What this record does not establish, and does not change

It does not establish:

- that Route A or QMHP-CoPro is invalid;
- any value of `E_C` or `g`;
- convergence of the static quantity (one refinement is one step);
- anything about Palace's box-refined operator, which is not rebuilt here.

It does not change:

- the first-moment diagnostic, Route A or the registered definitions. Their digests are
  pinned by `tests/test_static_anchor_hypothesis.py` while the alternative is being tested.

## 7. Files

| file | role |
|---|---|
| `anchor_fem.py` | mesh reading, nested red refinement, Whitney `M`, port `f`, P1 `K`, gradient `G`; no solve |
| `lower_bounds.py` | reproduces the class-C lower bounds from the committed mesh (level 2 opt-in, ~80 s) |
| `static_capacitance.py` | the prepared test: `--synthetic` (known answers), `--preflight` (no solve), gated execution |
| `predeclaration.json` | the frozen question, configuration, relation to `E_C`, integrity checks and outcome table |
| `measurements.json` | every measured value, by class, with its source |
| `TEST-APPROVAL.draft.json` | the approval to review; granting it means saving it as `TEST-APPROVAL.json` without its `DRAFT` and `how_to_grant_it` keys |
