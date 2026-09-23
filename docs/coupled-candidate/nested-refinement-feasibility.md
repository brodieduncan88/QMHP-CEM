# Can the existing L2 mesh be refined locally, without Gmsh?

**Yes — the pinned stack supports it.** The refinement is conforming, nested and
applied to the existing mesh with no Gmsh, and it leaves the lumped-port geometry
untouched. **It is better controlled than R1 on nestedness and geometric
invariance, and strictly worse on pre-launch verifiability**: the DOF cannot be
measured offline, so the 250 000-DOF gate must be enforced by a probe at launch
(§3) rather than before it. That trade is the decision this stops for.

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
| marking | an element is marked if **any one of its vertices** lies inside the closed box | `geodata.cpp:281-307` |
| dispatch | `GeneralRefinement(refs, -1)` | `geodata.cpp:350` |
| conformity | for a 3-D mesh containing simplices, `nonconforming = 0` is forced **before** the argument is consulted | `mesh.cpp:10565-10567` |
| refinement | `Refinement(i)` defaults to `XYZ` (7) → `type = 3` → **octasection**, 7 bisections, 8 children per marked tet | `ncmesh.hpp:44`, `pmesh.cpp:3427-3441` |
| conformity restored | a **green-closure loop** bisects *any* element needing it, marked or not, plus an MPI face exchange and the boundary elements | `pmesh.cpp:3467-3477, 3489-3560, 3568-3580` |
| new vertices | **edge midpoints only** — `vertices.Append(V)`; existing coordinates are never moved | `mesh.cpp:10834-10841` |
| element tags | children inherit the parent attribute | `mesh.cpp:10890`, then `10896` or `10898` depending on `MFEM_USE_MEMALLOC` |
| boundary tags | children inherit the parent attribute | `BdrBisection`, `mesh.cpp:10959` |
| parent/child | tracked as `CoarseFineTr.embeddings[i].parent` | `mesh.cpp:10908-10910` |

**Which code actually runs.** `ParMesh` does not override `GeneralRefinement`
(`mesh.hpp:2185`), so the dispatch above is the serial one — but it calls
`LocalRefinement`, which **is** virtual (`mesh.hpp:429`) and **is** overridden
(`pmesh.hpp:195`). The executed octasection and closure are therefore
`ParMesh::LocalRefinement` (`pmesh.cpp:3385`), not the serial twins in
`mesh.cpp`. Behaviour matches; the citations above point at the executed code.
`Mesh::Bisection` and `Mesh::BdrBisection` are *not* overridden, so the
midpoint and attribute citations are the serial ones and are correct.

Three preconditions were checked rather than assumed:

- The tet path asserts `GetRefinementFlag() != 0` and aborts otherwise
  (`mesh.cpp:10825-10826`). Palace loads with `refine = true`
  (`geodata.cpp:1494`), reaching `MarkTetMeshForRefinement`
  (`mesh.cpp:2667-2688`), which sets those flags. **The path is live.**
- `Nonconformal` and `MaxNCLevels` are **inert for this configuration**. They
  only reach `NonconformingRefinement`. Note the ordering: `if (ncmesh)
  { nonconforming = 1; }` at `mesh.cpp:10561-10563` takes precedence over the
  simplex branch, and is skipped only because `EnsureNCMesh` is called solely
  under `refinement.nonconformal && use_amr` (`geodata.cpp:137-140`), which is
  false here. So "conforming regardless of the argument" holds **for this
  config**, not unconditionally.
- Region refinement `MFEM_ABORT`s outright for any non-simplex mesh
  (`geodata.cpp:237-246`), so there is no silent fallback.

## 2. What this controls that R1 did not

R1's weakness was that its comparison regenerated the mesh. This does not.

| | R1 (Gmsh `Box` size field) | **N1 (Palace `Model.Refinement.Boxes`)** |
|---|---|---|
| mesh file | regenerated | **byte-identical, reused as an input** |
| baseline vertices retained | 81.6 % (2 571 of 13 991 absent, out to 3.32 mm) | **100 %, by construction** |
| nested | no | **yes** |
| parent/child | none | **tracked by MFEM** |
| `w`, `l`, `L_s`, `κ` | unchanged in principle | **unchanged** (see below) |
| `Lc` | unchanged in principle | **cannot change** — computed pre-refinement |
| **pre-launch measured DOF** | **yes — 80 762, dry-run before approval** | **no** (§3) |
| **pre-launch mesh-identity gate** | **yes — `REFUSED-MESH-MISMATCH` on a sha256** | **no** — there is no candidate mesh to hash |

**The comparison is not one-sided, and the last two rows are R1's.** R1 was
measured and hash-gated before it was allowed to start; N1 cannot be either,
because the object being gated does not exist until Palace builds it. **On
pre-launch verifiability N1 is strictly worse than R1**, and the probe in §3 is
what narrows that gap rather than closing it. N1 is better on nestedness and
geometric invariance; that is the trade, and it should be stated as a trade.

`Lc` is the strongest row: `main.cpp:311-313` orders `ReadMesh` →
`NondimensionalizeInputs` → `RefineMesh`, and `Lc` is taken from the
pre-refinement bounding box under `MFEM_VERIFY(!init)` (`iodata.cpp:448-463`).
It cannot see the refinement at all.

**The port-geometry row needs more care than a one-line hull argument**, and an
earlier draft did not give it. Palace derives `w` and `l` from
`mesh::GetBoundingBox` on the port attribute (`lumpedelement.cpp:22-69`), and
that box is **not axis-aligned**: `BoundingBoxFromPointCloud`
(`geodata.cpp:915-1023`) builds an *oriented* box from extremal points, and
`geodata.hpp:124-128` says so — "These do not need to be axis-aligned ... for
other shapes, the result is less predictable". The invariance still holds, for
two reasons that must both be stated:

1. Every selection functional is hull-extremal, and a midpoint is a convex
   combination of existing vertices, so **no inserted vertex can become a new
   extremum**.
2. The selections are `min_element`/`max_element` iterators, tie-broken by list
   order, and refinement reorders the point cloud. For this **rectangular**
   port both off-diagonal corners are equidistant from the main diagonal, so the
   chosen corner can flip. It is harmless only because `geodata.cpp:1013-1014`
   re-sorts the axes by descending length, making `Lengths()`
   permutation-invariant. **On a non-rectangular or non-planar port face that
   rescue would not exist.**

So the conclusion is safe *for this port*, and for a stated reason rather than a
general one. `tests/test_nested_refinement.py` checks an **axis-aligned** box,
which is not the quantity Palace computes; it coincides here only because the
port is an exactly axis-aligned planar 0.020 × 0.040 mm rectangle, which the
test also asserts. It is a necessary condition, not the full invariance.

**It is still not a face-only change.** Two reasons, both recorded in the
candidate:

1. The marked region is a **volume** — any tet with a vertex in the box, which
   at a 0.010 mm pad is 221 tets spanning material attributes 1 and 3.
2. The **green closure refines elements outside the box**. Conformity requires
   it. Its extent is not computable offline.

## 3. The DOF gate: not measurable offline, but still enforceable

The 250 000-DOF rule requires a *measured* order-1 DOF. **No offline measurement
exists** for this mechanism:

- The refined mesh is constructed inside Palace at load time. It is not written
  before the solve. (It *is* written afterwards — `postoperator.cpp:52` builds
  the ParaView collection on `space_op.GetNDSpace().GetParMesh()`, the refined
  mesh, and the candidate keeps `Solver.Eigenmode.Save: 6`. That is post-solve
  and cannot gate anything, but the mesh is not invisible.)
- **MFEM has no Python binding in this environment** (checked: `mfem`, `pymfem`
  absent; only `gmsh`), so the refinement cannot be reproduced offline.
- Palace's `--dry-run` **parses the configuration file and exits**
  (`main.cpp:246-256`) without loading a mesh — the mesh is first touched at
  `main.cpp:311`.

Reproducing the green closure offline means reimplementing MFEM's bisection,
which is out of scope and would be worse than no number if it silently diverged.

### The gate does NOT have to be given up

An earlier draft of this document concluded that the rule must degrade from a
**pre-launch refusal** to a **post-hoc detection**. That was wrong, and it
over-read "not measurable offline" as "not enforceable before the solve".

Palace prints the DOF almost immediately, and long before the expensive work.
From the baseline run's own `palace_log.txt`:

| log line | content |
|---|---|
| 30 | `edges  79944` (parallel mesh stats) |
| **49** | **`H1 (p = 1): 13991, ND (p = 1): 79944, RT (p = 1): 130388`** |
| 54 | `Configuring SLEPc eigenvalue solver` |
| 191 | `Found 6 converged eigenvalues` |

So the enforcement a refined run needs is a **bounded probe**: launch Palace,
read `ND (p = 1)`, and if it exceeds 250 000 kill the job and refuse. Exposure is
**seconds of mesh loading and assembly**, not the 45-minute cap, and the refusal
still happens before any eigenvalue work. That is not identical to a pre-launch
refusal — the process does start — but it is far closer to it than to post-hoc
detection, and it keeps the rule's force intact.

**This requires running Palace, so it is not done here** and is folded into the
proposed run in §5 as its first stop condition. The rule itself is unchanged and
no code in this branch touches it.

### What can be said offline

A *lower* bound is computable exactly. The marked submesh refines uniformly, for
which `E' = 2E + 3F + T` is an identity, and the closure only ever adds:

```
E_refined  >=  79 944 + 307 + 3·464 + 221  =  81 864
```

**A lower bound cannot discharge an upper limit**, and it should not be quoted as
"headroom" — an earlier draft did exactly that, which was this document's weakest
moment. Stated honestly, the offline knowledge is an interval:

```
81 864  <=  E_refined  <=  615 486        (uniform refinement; 2.46x the budget)
```

The useful offline argument is the *breach* argument, not the bound. Refining the
whole mesh uniformly adds 535 542 edges. Breaching 250 000 from a baseline of
79 944 needs 170 056 added edges. The marked octasection supplies 1 920. So a
breach requires the green closure to deliver

> **31.8 % of a full uniform refinement — an 89× expansion of the 221 marked
> elements.**

That is a much stronger statement than "0.34 % of the elements", and it is fully
computable offline. It still is not a measurement, and three things cut against
complacency:

- There is **no upper bound below 615 486**, which is 2.46× the budget.
- The marked set is the mesh's **smallest and worst-shaped** elements, sitting
  directly against much larger neighbours — precisely the configuration in which
  a longest-edge-marked conforming closure has the most propagating to do.
- Boundary elements are bisected too (`pmesh.cpp:3568-3580`), and Palace adds
  9 449 interface boundary elements at load. Neither appears in the 221/64 434
  element accounting. Edge count is unaffected, but the accounting is not
  complete.

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

**Purpose.** To obtain a frequency difference from a **nested** pair on one mesh
file, where the only change is added degrees of freedom in a declared region and
`L_s`, `κ` and `Lc` are unchanged. That is strictly more than R1 could offer —
but it is **not** an answer to the question R1 was asked. A movement here would
be attributable to *added resolution in that region*, which is not the same as
*port-face resolution*: the region is a volume, the closure extends it, and the
marked elements are the worst-shaped in the mesh. Element quality remains a live
alternative explanation and this run cannot separate it.

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

1. **The DOF probe (§3).** Palace prints `ND (p = 1)` at log line 49, before the
   eigensolver is configured at line 54. The run reads that line and, if it
   exceeds **250 000**, kills the job and records `REFUSED-DOF-BUDGET`. Exposure
   is seconds of load and assembly, not the 45-minute cap. This keeps the rule's
   force; it does not weaken it to a post-hoc check.
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
