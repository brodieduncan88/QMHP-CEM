# N2: one further level on the same region — prepared, not approved

**Offline preparation only. No Palace was executed.** The live approval still
names N1, which has already run.

**The question N2 asks:** do the tracked frequencies and participation estimates
begin **stabilising** along `original L2 → N1 → N2`?

**What a settling sequence would and would not mean.** It would be *local*
stabilisation of a *locally* refined region. It would **not** establish global
mesh convergence, it would not identify a continuum limit, and three points
would not be fitted for an order. Those are different claims and this record
does not make them.

**N2 is not R2.** The prepared gmsh R2 experiment regenerates the mesh and
remains unapproved and out of scope.

---

## 1. The exact candidate

`experiments/N2-nested-port-refinement/` — a derived copy. Historical approvals
and results are unchanged.

| pinned | value |
|---|---|
| original L2 mesh | `sha256 d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428` |
| original L2 record | `COUPLED-LADDER-O1-L2-20260916T080802Z` |
| N1 reference record | `COUPLED-LADDER-O1-L2-N1-20260917T001735Z` |
| Palace / MFEM | `a61c8cbe…` / `c444b17c…` |
| region | `[-0.620, -0.125, -0.010] … [-0.580, -0.065, 0.010]` mm — **byte-identical to N1's** |
| levels | **2 total**, from the original mesh — one beyond N1, **not** two beyond |
| element order | 1 |

The candidate config differs from N1's by **one integer**: `Levels` 1 → 2. Same
mesh file, same geometry, materials, port model, boundary conditions and solver
settings — asserted programmatically, not claimed.

## 2. The first stage reproduces N1 — verified from the implementation

Read from pinned source rather than assumed. `geodata.cpp:251`:

```cpp
int region_ref_level = 0;
while (region_ref_level < max_region_ref_levels) {
    // mark elements of mesh.back() having a vertex in the box,
    // for each box with  region_ref_level < box.ref_levels
    if (mesh.capacity() > 1) {                                // :347-349
      mesh.emplace_back(std::make_unique<mfem::ParMesh>(*mesh.back()));
    }
    mesh.back()->GeneralRefinement(refs, -1);                 // :350
    region_ref_level++;
}
```

Note the copy at `:347-349`: the marked mesh is **copied and the copy refined**,
which is how the multigrid hierarchy is built. Capacity is 2 for N1 and 3 for N2,
both `> 1`, so both take the same branch — the depth changes, the code path does
not.

On iteration 0, `mesh.back()` is the **original loaded mesh** and the per-box
test is `0 < box.ref_levels`, which is true for `Levels: 1` and `Levels: 2`
alike. Same input mesh, same box, same marking criterion, same refinement call.

**So iteration 0 of `Levels: 2` is N1's single stage.** N1 is a genuine
intermediate point of this sequence, not a parallel experiment — which is what
makes `L2 → N1 → N2` a sequence at all.

Iteration 1 then marks on the **once-refined** mesh using the same box, refining
the children of stage 1 plus any closure element that now has a vertex in it.

## 3. The DOF guard under a multi-level hierarchy

**It evaluates the final finest-level count.** Verified three ways:

- Palace prints `ND (p = 1)` from `GetNDSpace()`, which is
  `nd_fespaces.GetFinestFESpace()` (`spaceoperator.hpp:121`), at all four call
  sites, behind a **one-shot** `print_hdr` flag (`spaceoperator.cpp:175`, set
  false at `:202`). One line per run, from the finest space, whatever the depth.
- N1's own log confirms it empirically: **one** `ND (p = 1)` line (84 485, the
  finest), while the multigrid hierarchy printed `Level 0 (p = 1): 79944
  unknowns` and `Level 1 (p = 1): 84485 unknowns` in a **different format the
  probe's pattern cannot match**.
- The guard now enforces on the **largest** count seen rather than the first,
  and records `dof_reported_all` plus an `ambiguous` flag. Today first == finest,
  so this changes nothing; it removes the class in which a coarse level could be
  read instead.

**Enforcement limitations, stated plainly:**

- The guard depends on Palace printing that line. If it never appears, the run
  is **`REFUSED-DOF-PROBE-SILENT`** — a missing count is not a pass.
- If the reader thread fails, `reader_error` is recorded and the same refusal
  applies. A truncated log is marked, not left silently short.
- It is **not a pre-launch refusal.** The process starts, and the refusal lands
  once the count is read — 2.8 s into N1. `stdbuf -oL` forces line buffering to
  keep that early; `seen_at_wall_s` records when it actually arrived, so the
  claim is checkable per run rather than trusted.
- It binds **order-1 DOF only**, which is what the rule specifies.

## 4. Resource uncertainty, honestly

**There is no N2 DOF figure here, and there cannot be one yet.** Stage 2 marks
on the stage-1 mesh, which does not exist offline: MFEM has no Python binding in
this environment and Palace's `--dry-run` does not load a mesh. For N1 a rigorous
lower bound was computable (81 864; actual 84 485) from the marked submesh's own
counts; **that method cannot be reapplied**, because it needs the stage-1
submesh, which is exactly what is missing.

A bound does exist, and an earlier draft of this document wrongly said none did:

```
84 485  <  N2  <=  4 857 516          (19.4x the 250 000 budget)
```

The upper bound is real and computable — the uniform-refinement identity
`E' = 2E + 3F + T` **composes**, so two uniform levels of the original mesh bound
any two-level local refinement of it (one level: V=93 935, E=615 486,
F=1 037 024, T=515 472, Euler 1; a second: 4 857 516). **It is useless for gating
at 19.4x the budget** — but "computable and useless" is the honest statement, not
"unavailable". Any tighter figure before the mesh is built would be invented.

**Runtime cannot be extrapolated from DOF.** N1 took **923.5 s** — 11.4× the
baseline's 81.2 s — for **5.7 %** more DOF, with 69 % of it in preconditioner
application over 622 coarse solves. A DOF-based estimate for N2 would be
meaningless, and none is offered.

**The automatic hierarchy change, disclosed.** `Model.Refinement` makes Palace
reserve `1 + levels` meshes (`geodata.cpp:204-206`) and push a copy before each
refinement (`:346-349`). The baseline ran **one** multigrid level, N1 ran
**two**, N2 will run **three**. This is automatic, not chosen: **no solver
setting or preconditioner is changed to make N2 fit.**

**The primary risk is the 45-minute cap, not the DOF budget.** N1 used 34.2 % of
the cap with a two-level hierarchy. A three-level hierarchy on a larger problem
could plausibly exceed it. That outcome is a recorded `TIMEOUT`, not a silent
overrun.

## 5. The comparisons, prepared

`refinement_sequence()` computes every consecutive step by calling the existing
`compare_against_baseline()` per step — no new criterion, no new framework.

| step | role |
|---|---|
| original L2 → N1 | reported **alongside**, recomputed read-only from two committed records |
| **N1 → N2** | the **primary** comparison |

Each step reports signed and relative Δf, mode admission and matching with the
unchanged rules, energy diagnostics, backward error, and **both** participations
kept distinct:

- `port_participation_from_probes` — **derived** from the boundary quadrature
- `port_participation_reported_by_palace` — Palace's **rank-one surrogate**.
  Cauchy–Schwarz bounds `E_ind/E_port ≤ 1` for the **exact** quantities; the
  derived column is itself an estimate built from the difference
  `p_Default − p_MA`, so `reported ≤ derived` is *guaranteed for the exact
  ratio* and *observed* in this data — ~1e-5 margin on m1, ~2.4e-4 on m2.

The L2 → N1 step already computes correctly in the dry run, reproducing N1's
published +0.053867 and +0.001620 GHz.

**The approval must carry three keys**, or the comparisons silently degrade:

```json
"baseline_record":     "COUPLED-LADDER-O1-L2-N1-20260917T001735Z",
"sequence_records":    ["COUPLED-LADDER-O1-L2-20260916T080802Z",
                        "COUPLED-LADDER-O1-L2-N1-20260917T001735Z"],
"baseline_mesh_sha256": "d8dc1a92…"
```

`sequence_records` is a **new top-level approval key**. Without it the `L2 → N1`
step is never computed and only the primary comparison appears. It is validated
to end at `baseline_record`, and every entry must be a record on disk.

`refinement_sequence.available` keys on the **primary** step alone. The earlier
step runs between two committed records and is always available, so reporting
"any step available" would have called the analysis available in precisely the
likeliest failure mode — a `TIMEOUT` on this run, with the only new comparison
missing.

**Matching rules are unchanged. An ambiguous correspondence is reported as
unavailable and is never repaired by changing the criteria.** N2 is excluded
from the gmsh L1/L2/L3 convergence fit by `earlier_rungs()`.

## 6. The proposed run

**One solve.** Level 2, order 1, halo 0.08 mm, the original L2 mesh reused
byte-identically, `Model.Refinement.Boxes` with `Levels: 2` over N1's box.

**Stop conditions**, the existing ones plus the sequence checks:

1. **DOF probe** — Palace's finest order-1 count exceeds 250 000 → container
   killed, `REFUSED-DOF-BUDGET`. Probe silent or reader failed →
   `REFUSED-DOF-PROBE-SILENT`. Neither is a pass.
2. **No-op** — solved DOF not strictly greater than loaded →
   `REFUSED-REFINEMENT-NO-OP`.
3. **Cap** — 45 minutes unchanged; exceeding it is a recorded `TIMEOUT`. This is
   the likeliest failure.
4. **Backward error** above the unchanged 1e-6 → record and stop.
5. **Matching** — admitted set not `{m1, m2}`, or correspondence ambiguous →
   reported **unavailable**, not repaired.
6. **Post-solve analysis raises** → the record is still written, manifested and
   committed.
7. Completing N2 means **STOP for review**, not a third level.

**Unchanged:** geometry, materials, substrate permittivity, port dimensions,
direction, inductance and formulation, every boundary condition, the pinned
image, every solver setting, `Δ|p| ≤ 1e-2`, `Δf ≤ 1e-4`, backward error `1e-6`,
admission `|R−1| ≤ 1e-3`, the matching rule, the 0.5–9.0 GHz window, the
250 000-DOF rule, the 45-minute cap and element order 1.

**Nothing in this branch starts it.** `.github/ladder-approval.json` still names
N1; the ladder triggers on that file alone; `experiments/` is outside every
trigger path. A test asserts that the approval still names N1 and that the
candidate directory sits outside the golden-run paths; the trigger lists
themselves were checked by hand against the workflow files, not by a test.

## 7. What N2 would not establish, whatever it shows

- **Not global mesh convergence.** The refinement is local. A settling sequence
  would be local stabilisation of one region.
- **Not a continuum limit.** Three points are not fitted and nothing is
  extrapolated.
- **Not port-face attribution.** The region is a volume, the closure reaches
  outside it, and the marked elements are the worst-shaped in the mesh, so
  element quality remains unseparated from resolution.
- **Not a comparable cost.** The multigrid depth changes with the refinement
  depth, so wall clock across the sequence is not like-for-like.
