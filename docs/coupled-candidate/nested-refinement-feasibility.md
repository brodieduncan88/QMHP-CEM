# Can the existing L2 mesh be refined locally, without Gmsh?

**Yes — the pinned stack supports it, and it is better controlled than R1.**
**But the 250 000-DOF pre-flight gate cannot be discharged offline.** That single
blocker is the reason this stops for approval rather than proposing a launch.

Offline study. No Palace was executed, no mesh regenerated, no record modified.
Everything below is read from the pinned sources: Palace `v0.13.0`
(`a61c8cbe0cacf496cde3c62e93085fae0d6299ac`, the commit `docker/palace.Dockerfile`
asserts) and the MFEM revision Palace pins for it,
`c444b17c973cc301590a6ac186fb33587b5881e6` (`cmake/ExternalGitTags.cmake:134`).

---

## 1. The mechanism exists and is the right one

Palace accepts `Model.Refinement.Boxes` — a list of axis-aligned boxes, each with
a refinement level — and applies it to the **mesh it loads**. No Gmsh runs, and
**no new mesh file is produced**: the refinement is a *config block*.

The baseline already carries `"Refinement": {"UniformLevels": 0}`, so the
candidate differs from it by that one block and nothing else.

What the source says, step by step:

| step | behaviour | source |
|---|---|---|
| marking | an element is marked if **any one of its vertices** lies inside the closed box | `geodata.cpp:282-306` |
| dispatch | `GeneralRefinement(refs, -1)` | `geodata.cpp:350` |
| conformity | for a 3-D mesh containing simplices, `nonconforming = 0` is forced **before** the argument is consulted | `mesh.cpp:10565-10567` |
| refinement | `Refinement(i)` defaults to `XYZ` (7) → `type = 3` → **octasection**, 7 bisections, 8 children per marked tet | `ncmesh.hpp:44`, `mesh.cpp:10105-10119` |
| conformity restored | a **green-closure loop** bisects neighbours until there are no hanging nodes | `mesh.cpp:10123+` |
| new vertices | **edge midpoints only** — `vertices.Append(V)`; existing coordinates are never moved | `mesh.cpp:10834-10841` |
| element tags | children inherit the parent attribute | `mesh.cpp:10890, 10896` |
| boundary tags | children inherit the parent attribute | `BdrBisection`, `mesh.cpp:10959` |
| parent/child | tracked as `CoarseFineTr.embeddings[i].parent` | `mesh.cpp:10908-10910` |

Two preconditions were checked rather than assumed:

- The tet path asserts `GetRefinementFlag() != 0` and aborts otherwise
  (`mesh.cpp:10826`). Palace loads its mesh with `refine = true`
  (`geodata.cpp:1494`), which sets those flags. **The path is live.**
- `Nonconformal` and `MaxNCLevels` are **inert here**. They only reach
  `NonconformingRefinement`, and the conforming branch is taken first for tets.
  A reader of the Palace docs alone would not know this.

## 2. What this controls that R1 did not

R1's weakness was that its comparison regenerated the mesh. This does not.

| | R1 (Gmsh `Box` size field) | **N1 (Palace `Model.Refinement.Boxes`)** |
|---|---|---|
| mesh file | regenerated | **byte-identical, reused as an input** |
| baseline vertices retained | 81.6 % (2 571 of 13 991 absent, out to 3.32 mm) | **100 %, by construction** |
| nested | no | **yes** |
| parent/child | none | **tracked by MFEM** |
| `w`, `l`, `L_s`, `κ`, `Lc` | unchanged in principle | **unchanged, provably** |

The last row is the one that matters most and is the easiest to get wrong.
Palace derives the lumped port's `w` and `l` from the **bounding box** of the
port attribute (`lumpedelement.cpp:22-69`), and `L_s = L·(w/l)·n`. Every vertex
this refinement adds is a midpoint — a convex combination of existing vertices —
so the convex hull, the bounding box, `w`, `l`, `L_s`, `κ` and `Lc` are all
unchanged. `tests/test_nested_refinement.py` asserts this by inserting every
midpoint (and every midpoint-of-midpoint) and re-measuring, rather than arguing it.

**It is still not a face-only change.** Two reasons, both recorded in the
candidate:

1. The marked region is a **volume** — any tet with a vertex in the box, which
   at a 0.010 mm pad is 221 tets spanning material attributes 1 and 3.
2. The **green closure refines elements outside the box**. Conformity requires
   it. Its extent is not computable offline.

## 3. The blocker: DOF cannot be measured offline

The 250 000-DOF rule requires a *measured* order-1 DOF before launch. For this
mechanism there is no offline measurement, for three independent reasons:

- The refined mesh **exists only inside Palace**, constructed at load time and
  never written out.
- **MFEM has no Python binding in this environment** (checked: `mfem`, `pymfem`
  absent; only `gmsh` is installed), so the refinement cannot be reproduced.
- Palace's `--dry-run` **parses the configuration file and exits** without
  loading a mesh (`main.cpp:246-254`), so it cannot report DOF either.

Computing the green closure offline means reimplementing MFEM's bisection. That
is out of scope by instruction, and a silent mismatch would be worse than no
number at all.

**This weakens an existing guarantee, and that is the decision being asked for.**
The ladder workflow's header states that *"the driver refuses to launch a level
whose measured DOF exceeds the budget"* — a **pre-launch refusal**, made possible
because every mesh so far was built by Gmsh offline and could be counted before
any solver started. A Palace-side refinement cannot be counted that way, so for
N1 the 250 000-DOF rule degrades from a refusal to a **post-hoc detection**: the
run starts, Palace reports its DOF, and the record records a breach after the
fact. The rule's *value* is unchanged and the cost of a breach is bounded by the
45-minute cap, but the enforcement is strictly weaker than for every rung to
date. **No code here changes that rule**, and it should not be changed without
the owner saying so.

What *can* be established rigorously offline is a **lower bound**. The marked
submesh refines uniformly, for which `E' = 2E + 3F + T` is exact, and the closure
only ever adds:

```
E_refined  >=  E_baseline + E(M) + 3·F(M) + T(M)
           =   79 944 + 307 + 3·464 + 221   =   81 864
```

against a budget of 250 000 — **168 136 of headroom** on the bound. For scale,
refining the *whole* mesh uniformly would give 615 486, so this region is
0.34 % of the elements and the budget is not plausibly at risk. **Plausible is
not measured, and the rule says measured.**

## 4. The prepared candidate

`experiments/N1-nested-port-refinement/` — a derived copy. The preserved
baseline record is untouched and still verifies against its manifest.

| | |
|---|---|
| baseline record | `COUPLED-LADDER-O1-L2-20260916T080802Z` |
| baseline mesh sha256 | `d8dc1a92159d7659…` (recorded in `candidate.json`, asserted against the manifest) |
| candidate mesh | **the same file** — the delta is `Model.Refinement` alone |
| region | port attribute-10 bounding box padded 0.010 mm: `[-0.620,-0.125,-0.010] … [-0.580,-0.065,0.010]` mm |
| levels | 1 |
| marked | 221 of 64 434 tets (0.34 %), attributes 1 and 3 |
| DOF | **not measured** — lower bound 81 864, budget 250 000 |
| port face | mean edge 0.008453 mm → **0.004227 mm** after one level |
| quality | marked tets mean radius-ratio **0.2197** against the mesh's 0.3700 (min 0.0913) |

The quality row is the least comfortable number here and is stated plainly: the
elements at the port gap are already the thinnest in the mesh, and octasection is
not quality-preserving in general.

## 5. Proposed next solve — ONE run, for approval

**N1: the level-2 baseline re-solved with one `Model.Refinement.Boxes` entry.**

**Purpose.** To obtain, for the first time, a frequency difference that *is*
attributable — a nested pair on one mesh file, where the only change is added
degrees of freedom in a declared region and `L_s`, `κ` and `Lc` are provably
unchanged. R1 could not support an attribution; this is the experiment that can.

**Remaining confounds**, stated before the run rather than after:

- The refined region is a **volume**, not the port face, and the green closure
  extends it further by an amount not known until the run.
- One nested pair measures a difference, not an order of convergence. **Two
  points cannot establish convergence**, and this proposal does not claim
  otherwise.
- Marked elements are below the mesh's average quality; if the frequency moves,
  element quality is a live alternative explanation to resolution.
- `p_Default` on the port face is still unconverged at every level measured so
  far, so the port-face field integral remains a moving target.

**Stop conditions.**

1. Palace reports order-1 DOF **> 250 000** → the record is written, the run is
   marked over-budget, and no further refinement is proposed. This is the
   blocker in §3 made visible: it is detected *after* the solve starts, and the
   45-minute cap bounds the cost of finding out.
2. Wall clock exceeds the unchanged **45-minute cap** → terminate, record.
3. Max backward error exceeds the unchanged **1e-6** → record and stop.
4. The admitted set is not `{m1, m2}`, or matching against the level-1 rung
   refuses → record and stop; the comparison is not available.
5. Any post-solve analysis raises → the record is still written, manifested and
   committed, per the guarded post-solve window.
6. Completing N1 means **STOP for review**, not a second refinement level.

**Unchanged and not up for negotiation in this proposal:** the geometry,
materials, substrate permittivity, port dimensions, direction, inductance and
formulation, every boundary condition, the pinned image, every solver setting,
`Δ|p| ≤ 1e-2`, `Δf ≤ 1e-4`, backward error `1e-6`, admission `|R−1| ≤ 1e-3`, the
matching rule, the 0.5–9.0 GHz window, the 250 000-DOF rule, the 45-minute cap
and element order 1.

**Nothing in this branch starts it.** `.github/ladder-approval.json` still names
R1 and carries no N1 block; the ladder workflow triggers on that file alone, and
the candidate lives in `experiments/`, outside every trigger path.
`tests/test_nested_refinement.py` asserts both.
