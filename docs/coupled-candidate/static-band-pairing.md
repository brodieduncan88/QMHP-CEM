# The paired static-vs-band refinement test

**PREPARED, NOT APPROVED, NOT EXECUTED.** No Palace solve and no QMHP static solve has
been run for this test; no refined QMHP mesh exists. The static-anchor test's verdict,
**UNRESOLVED**, is unchanged. Route A, the first-moment diagnostic and the registered
definitions are unchanged. `E_C,F1F1` and `g` stay **UNAVAILABLE**.
Record: `experiments/static-band-pairing/`.

This record answers the three questions asked before the test could be prepared, then
prepares the test. It keeps apart what is **proved**, what is **measured** (and by what),
and what is **predicted**.

## 1. Can the capacitance only decrease under refinement, and is 82.2 fF a rigorous bound?

**Yes to both, for the implementation actually used, within a precisely stated model.**
The two claims rest on different conditions, and the earlier wording ran them together.

- **The bound `C ≤ C_h` needs only conformity.** Every admissible P1 function (1 at the
  island's nodes, 0 at the ground's) equals 1 on each island triangle and 0 on each
  ground triangle. So it is admissible for the continuum Dirichlet problem on the same
  polyhedral domain, and the continuum minimum cannot exceed the discrete one. The energy
  `static_capacitance.py` reports is the quadratic form of an exactly constrained vector,
  so the bound does not depend on solver accuracy, only on round-off.
- **Monotonicity `C_{h+1} ≤ C_h` needs nesting**:
  - the coarse space lies inside the fine one;
  - the coarse admissible set lies inside the fine one;
  - the functional is unchanged.

**Verified on the committed mesh and its red refinement, with no solve**
(`nesting_verification.json`):

| check | result |
|---|---|
| conforming: tetrahedra per face | at most 2 |
| coincident nodes | 0 |
| every tagged triangle is a tetrahedron face | yes |
| outer boundary | all 3,040 faces are grounded walls |
| every conductor triangle lies in one conductor | yes |
| coarse nodes unchanged; midpoints exactly on the edges | yes, error 0 |
| children's volumes sum to the parent's | 2.2e-15 |
| **Galerkin identity `PᵀK₁P = K₀`** | **6.9e-15** |
| fine constrained nodes prolonged only from the same conductor | yes |
| interior edges joining two nodes of one conductor at level 0 (freed at level 1) | 543 |

**Negative controls on synthetic geometry**, each removing one condition of the proof:

| case | Galerkin identity | C₁/C₀ |
|---|---|---|
| nested refinement | 9.5e-16 | 0.953 |
| spaces not nested, same model | 0.17 (detected) | 0.954 (no violation in this instance) |
| constraint sets not nested | — | **1.055: C rises** |

So the verification detects a non-nested refinement, and constraint nesting is genuinely
necessary.

**What 82.2 fF is.** It is a rigorous upper bound on the island capacitance of the
*continuum electrostatic problem posed on the meshed geometry*:

- zero-thickness conductor sheets;
- grounded enclosing walls;
- ε_r = 1 and 11.45;
- the port face open.

It is exact up to assembly round-off; the two independent energy evaluations in the
record agreed exactly. It is **not** a bound on the physical device, whose geometry and
enclosure the mesh models. It is also not a bound on `C_FF` without assumption A-R.

A clarification to my earlier chat summary, which said the bound held "because
refinement can only lower the capacitance": the bound follows from conformity, and the
monotonicity from nesting. The record's own §8 wording was correct.

## 2. What relationship should S_static and S_band have?

**Not a ratio that converges to 1.** They are different spectral moments.

**Proved, for the declared lumped port** (the rank-one inductor term `ffᵀ/L`, and a port
whose Dirichlet voltage is `V`). Over all modes of the pencil, with `p` the port
participation:

- `N = Σ p = 1`;
- `Σ p/λ = L·C_h / V²`;
- `Σ p·λ = fᵀM⁻¹f / L`, which is Parseval.

So with `V = 1`, `S_h = 1/(L·C_h)` is **exactly the participation-weighted harmonic mean
of λ over the complete spectrum** (the −1 moment). The complete first moment `A` is the
arithmetic mean (the +1 moment), and it diverges for the sheet port. For every truncation
to the lowest k modes, Cauchy–Schwarz gives `S_h ≤ B_k/N_k`.

**Verified to machine precision** on synthetic geometries, with every eigenpair computed
(`identities.json`):

- `Σp/λ = L·C_h/V²` to 1e-12, and `N = 1` to 1e-12;
- Parseval to 1e-16;
- `S ≤ B_k/N_k` for all k.

The n = 2 slab has `V = 0.5` and reproduces the `1/V²` factor exactly. It is a
malformed-port negative control.

**Palace's port is not rank-one.** It assembles `∫_Γ (1/L_s)|E_t|² dS` over the full
tangential field (`lumpedportoperator.cpp`, pinned `a61c8cbe`; `fem-spectral-mapping.md`
§1), but it reports `p` from the rank-one voltage. For that pencil:

- **Parseval still holds exactly**, because the +1 moment does not involve `K`.
- **The −1 moment is perturbed.** `δ = S·Σp/λ − 1` is +2.3% and +3.0% on the synthetic
  slabs, whose port face is comparable to the whole structure.
- **`S ≤ B_k/N_k` can fail**, by up to 2.7%.
- `K_port − ffᵀ/L` is positive semi-definite to round-off.

**Measured on the committed L2 mesh, the same mesh as static level 0:**

| quantity | value |
|---|---|
| Palace's band `Σ\|p\|/f²` | 0.467302 GHz⁻² |
| `1/S0` | 0.466994 GHz⁻² |
| **`δ ≥ +6.6e-4`** | the sheet port's effect, band part only |
| `S0 ≤ B0/N_B` | still holds here, with 0.39% to spare |

**The lumped circuit meaning.** In a two-node reduction:

- `B/S → C_FF·(C⁻¹)_FF = 1/(1−k²)`, the Schur gap;
- the band's arithmetic moment corresponds to `(C⁻¹)_FF/L_F`, which is what the registered
  `E_C` is defined from;
- the harmonic moment corresponds to `1/(C_FF·L_F)`, which is the static quantity.

So `S/B` should tend to about `1 − k²_eff`, perturbed by δ. On the committed rungs
`H/B` = 0.991–0.996.

**The harmonic moment is robust; the arithmetic one is not.** N2R's 9-mode band, which
carries more high in-band modes, has `H/B` = 0.9912 against 0.996 for the 6-mode bands.
High, weakly participating modes inflate `B` and barely touch `H` or `S`.

**Corrections to how the executed static-anchor test was read** (its verdict,
UNRESOLVED, stands):

1. **`r0 = S0/B0 = 0.997` was not a coincidence of shared discretisation error**, as
   `static-anchor-hypothesis.md` §8 allowed. On one mesh it is what the identity
   predicts: `S0 ≈ H·(1+δ)` and `H/B ≈ 0.996`. So its closeness to 1 was never
   independent evidence for H1 over H0.
2. **The "CONTRADICTS, favours H0" branch (`r0 > 20`) was mathematically unreachable**
   for the lumped pencil, since `S ≤ B/N_B`. For Palace's pencil it was unreachable by a
   wide margin. The pre-declaration had called that branch only "physically
   implausible".

## 3. Proof, measurement and prediction, kept apart

| claim | kind | where |
|---|---|---|
| `C ≤ C_h` for the meshed model | proof, conditions verified on the implementation | §1, `nesting_verification.json` |
| `C_{h+1} ≤ C_h` under red refinement | proof, nesting verified (6.9e-15) | §1 |
| static = harmonic moment, lumped port | proof, known answer 1e-12 | §2, `identities.json` |
| Palace's sheet port perturbs it, δ > 0 | measured: synthetic +2.3%/+3.0%, L2 ≥ +6.6e-4 | §2 |
| `S/B → 1 − k²_eff`, not 1 | derivation (lumped reduction) | §2 |
| band and static co-move under refinement | **prediction, untested** | §4 |
| the static error sits in the island–gap–port region | **prediction, untested** | §4 |

## 4. The prepared test

**Question.** Under nested Palace box refinement of the island–gap–port region (levels
0, 1, 2 of the committed L2 mesh), does Palace's band first moment move with the static
quantity computed on the same meshes, as §2 predicts? And by how much do both move?

**Design.**

- **Box.** One box, `[−0.700, −0.125, −0.020]` to `[−0.500, 0.100, 0.020]` mm. It covers
  the 0.15 mm island, the whole 0.020 mm gap to ground, and the port face. The mesh
  resolves that gap with about two elements (median edge 0.010 mm near the island), which
  is the likely source of the 28% change in the static quantity under one uniform
  refinement. Palace marks every tetrahedron with a vertex inside the box, 1,880 at
  level 0, and splits each into 8 with conforming closure.
- **Levels.** Palace runs the committed L2 eigenmode config at box levels 0, 1 and 2.
  The deltas are only:
  - `Save: 0`;
  - `MGMaxLevels: 1`;
  - at levels 1 and 2, the box and `SaveAdaptMesh: true`.

  The configs' sha256s are frozen in `predeclaration.json`. `MGMaxLevels: 1` is what
  makes pinned Palace write the refined mesh (`geodata.cpp` `RefineMesh` →
  `RebalanceMesh`, with a single-mesh vector as `main.cpp` builds it).
- **Pairing.** On each level's mesh, the static quantity is computed with the unchanged
  `static_capacitance.py`. The level-0 mesh is the committed file; levels 1 and 2 use the
  mesh Palace saved. Band quantities come from Palace's own CSVs.
- **Nesting.** Each step is verified nested before anything is read: every new vertex
  must be a coarse edge midpoint, and the Galerkin identity must hold.

**Outcome table** (frozen). Here `g = S₂/S₀`, `δ_h = S_h·Σ_B|p|/f² − 1`, and the drift is
`max_h |S_h/B_h − S₀/B₀|`.

| condition | outcome |
|---|---|
| any integrity failure (DOF cap, eigen backward error, `N_B > 1`, static identities, nesting, `C` rising, level-0 static not reproducing `S0`, level-0 band not reproducing the L2 mode 1, any invalid value or digest) | UNQUALIFIED |
| `g < 1.05` | UNRESOLVED: LOW POWER. The box did not move the static quantity, so the error lies elsewhere |
| `g ≥ 1.05`, `max\|δ\| ≤ 0.01` and drift ≤ 0.01 | SUPPORTS: the band moves with the static quantity, and Palace's sheet port stays within 1% of the lumped element |
| `g ≥ 1.05` and (`max\|δ\| > 0.03` or drift > 0.03) | CONTRADICTS: they decouple, or the sheet port departs from the lumped element by over 3% |
| otherwise | UNRESOLVED |

**Power.** SUPPORTS is only reachable if the static quantity actually moves. A box that
misses the static error returns LOW POWER, not SUPPORTS. The 5% threshold is a fifth of
the ×1.39 that one uniform refinement produced.

**Not a target.** Co-movement is §2's prediction. The static quantity is computed without
reading any band value, and the windows were fixed before any refined QMHP value existed.

**Feasibility.**

| level | DOFs | Palace eigen time |
|---|---|---|
| 0 | 79,944 (measured) | about 80 s |
| 1 | 96k–119k | about 3 min |
| 2 | 227k–433k | about 10–17 min |

The level-2 range comes from 1,880 marked tetrahedra grown 8× per level, times the
1.4–2.4× closure factor measured on the N1R/N2R box, with time scaled as `DOF^1.3` from
N2R's 103k DOFs in 159 s. Static solves take seconds. Level 3 (1.3–2.9 M DOFs) is
infeasible on the runner and is not part of the test.

**Budget.**

- a cap of 450,000 DOFs per level, enforced by the reviewed DOF probe, which kills a
  breach;
- 2,700 s per solve;
- a 180-minute workflow;
- one attempt, bound to the workflow's run number and attempt 1. The record directory is
  created before any solve.

**Execution.**

- `.github/workflows/static-band-pairing.yml`:
  - dispatch-only, with the confirmation string `run-the-approved-pairing-attempt`;
  - builds the pinned image exactly as the ladder does;
  - refuses a Palace commit other than `a61c8cbe`.
- `pairing_driver.py --execute` is the one step that runs Palace, through the ladder's
  reviewed `_run_palace`.
- The refined meshes are uploaded as an artefact and never committed; their sha256s are
  in the record.

## 5. The evidence driver writes its own manifest (item 4)

`pairing_driver.py` writes the record in this order:

1. raw Palace outputs, as each level finishes;
2. the static result;
3. the nesting check;
4. `summary.json`;
5. **`manifest.sha256`, written by `orchestrator.manifest.write` at execution time, then
   verified with `manifest.verify` before the process exits.**

The failure path writes `failure.json` and then the same manifest. The workflow verifies
it again (`cem verify-results`) and refuses unexpected file kinds before committing.

The end-to-end synthetic tests prove both paths with a mock Palace: the record verifies,
a second attempt is refused, and no refined mesh enters the record. The executed
static-anchor record keeps its quarantine; it was not given a manifest after the fact.

## 6. What this record does not establish, and what needs approval

It does not establish:

- `E_C` or `g`;
- that Route A is valid or invalid;
- convergence, since three levels of *local* refinement are not a limit;
- anything outside the box;
- the physical device's capacitance.

The co-movement is a prediction until the test runs.

**Approval needed.** Executing the test means committing
`experiments/static-band-pairing/PAIRING-APPROVAL.json` (the reviewed draft without its
`DRAFT` and `how_to_grant_it` keys) and dispatching the workflow once. That is three
consequential Palace solves.

## 7. Files

| file | role |
|---|---|
| `verify_nesting.py` | item 1: conformity, conductor consistency, red-refinement nesting and the Galerkin identity on a mesh; synthetic positive and negative controls |
| `spectral.py` | the Whitney curl-curl, the lumped and sheet port terms, all eigenpairs and moments of small synthetic pencils |
| `identities.py` | item 2: the known-answer identities, the L2 same-mesh check, the band moments of every committed rung |
| `nesting_verification.json`, `identities.json` | their outputs, regenerated from committed inputs; no QMHP solve |
| `pairing_driver.py` | the future evidence driver: gate, configs, Palace, the static solve on the saved meshes, nesting, decision, manifest |
| `predeclaration.json` | the frozen question, theory, configuration, integrity, outcomes, feasibility and budget |
| `PAIRING-APPROVAL.draft.json` | the approval to review; it authorises nothing |
