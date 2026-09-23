# The paired static-vs-band refinement test — withdrawn before approval

**WITHDRAWN. Never approved, never executed.** No Palace solve and no QMHP static solve
was run for it. It was prepared (commit `72aec54`), then withdrawn after an independent
adversarial review found two things:

- its decisive comparison is **fixed by an exact identity**;
- **three defects would each have spent the single attempt**.

`WITHDRAWN.json` records each reason and how it was verified. The static-anchor test's
verdict, **UNRESOLVED**, is unchanged. Route A, the first-moment diagnostic and the
registered definitions are unchanged. `E_C,F1F1` and `g` stay **UNAVAILABLE**.
Record: `experiments/static-band-pairing/`.

Three questions had to be settled before the test could be prepared. This record answers
them, and keeps apart what is **proved**, what is **measured** (and by what), and what is
only **predicted**. The status line of the test it prepared read "PREPARED, NOT APPROVED,
NOT EXECUTED" until the withdrawal.

## 1. Can the capacitance only decrease under refinement, and is 82.2 fF a rigorous bound?

**Yes to both, for the implementation actually used, within a precisely stated model.**
The two claims rest on different conditions.

- **The bound `C ≤ C_h` needs only conformity.** Every admissible P1 function (1 at the
  island's nodes, 0 at the ground's) equals 1 on each island triangle and 0 on each
  ground triangle, so it is admissible for the continuum Dirichlet problem on the same
  polyhedral domain. The 543 interior edges that join two nodes of one conductor only
  constrain the discrete function further, so they can only raise `C_h`. The energy
  `static_capacitance.py` reports is the quadratic form of an exactly constrained vector,
  so the bound does not depend on solver accuracy, only on round-off.
- **Monotonicity `C_{h+1} ≤ C_h` needs nesting**: the coarse space and admissible set lie
  inside the fine ones, and the functional is unchanged. Algebraically,
  `PᵀK_{h+1}P = K_h` plus constraint inclusion already implies it.

**Verified on the committed mesh and its red refinement, with no solve**
(`nesting_verification.json`):

| check | result |
|---|---|
| conforming: tetrahedra per face | at most 2 |
| every face shared by one tetrahedron is a tagged boundary triangle (excludes hanging nodes) | yes, both levels |
| coincident nodes | 0 |
| outer boundary | all 3,040 faces are grounded walls |
| every conductor triangle lies in one conductor | yes |
| coarse nodes unchanged; midpoints exact | yes, error 0 |
| children's volumes sum to the parent's | 2.2e-15 |
| **Galerkin identity `PᵀK₁P = K₀`** | **6.9e-15** |
| constraint sets nested | yes |

**Negative controls, synthetic:**

| case | Galerkin identity | C₁/C₀ |
|---|---|---|
| nested refinement | 9.5e-16 | 0.953 |
| spaces not nested, same model | 0.17 (detected) | 0.954 (no violation in this instance) |
| constraint sets not nested | — | **1.055: C rises** |

**What 82.2 fF is.** It is a rigorous upper bound on the island capacitance of the
*continuum electrostatic problem posed on the meshed geometry*:

- zero-thickness conductor sheets;
- grounded enclosing walls;
- ε_r = 1 and 11.45;
- the port face open.

It is exact up to assembly round-off. It is **not** a bound on the physical device, and
not a bound on `C_FF` without assumption A-R.

Two wording corrections:

- My earlier chat summary said the bound held "because refinement can only lower the
  capacitance". It follows from conformity; the monotonicity follows from nesting.
- The record's P1 and edge-route energies agree exactly, but that is an **algebraic
  consistency check** of the de Rham identity. They share φ, the mesh and ε, so they are
  not independent confirmation.

## 2. What relationship should S_static and S_band have?

**Not a ratio that converges to 1.** They are different spectral moments, and on each mesh
they are tied together by exact identities.

**Proved, for the declared lumped port** (rank-one inductor term `ffᵀ/L`, port Dirichlet
voltage `V`). Over all modes, with `p` the port participation:

- `N = Σ p = 1`;
- `Σ p/λ = L·C_h / V²`;
- `Σ p·λ = fᵀM⁻¹f / L`, which is Parseval.

So with `V = 1`, `S_h = 1/(L·C_h)` is **exactly the participation-weighted harmonic mean
of λ over the complete spectrum**, and Cauchy–Schwarz gives `S_h ≤ B_k/N_k` for every set
of k modes. The complete first moment `A = Σ p·λ` depends only on `f` and `M`. It
diverges under refinement for **both** port models, because the port functional is a
surface average over a sheet face.

**Proved, for Palace's actual port**: the distributed sheet `∫_Γ (1/L_s)|E_t|² dS`, with
`p` reported from the rank-one voltage. With `ψ` 0 on ground, 1 on the island and linear
along the port direction on the rectangular port face:

- `K_sheet ∇ψ = f/L` (because `L_s = L·w/l`) and `K_curl ∇ψ = 0`;
- therefore `N = 1` and `Σ p/λ = L·C'_h`, where `C'_h` is the static capacitance with the
  port-face potential also held linear;
- so **`S_h = (1 + δ_h)·H_h(all modes)` exactly, with `δ_h = C'_h/C_h − 1 ≥ 0` a static
  quantity**.

The identity needs a rectangular port face whose conductor nodes lie only on its two end
lines. That holds on L2: area/(l·w) = 1.0000000000000002.

This was found by the independent review. I re-derived it, and my own implementation
(`spectral.port_constrained_energy`) reproduces the dense-eigen sheet δ to **1.1e-12 and
1.2e-12** (`identities.json`).

**Checked on synthetic geometries** (`identities.json`, every eigenpair computed):

- lumped: `N = 1` and `Σp/λ = L·C_h/V²` to 1e-12; Parseval to 1e-16; `S ≤ B_k/N_k` for
  every k;
- sheet: Parseval exact; `δ` = +2.3% and +3.0% on slabs whose port face is comparable to
  the structure; `S ≤ B_k/N_k` can fail (by up to 2.7%);
- `K_sheet − ffᵀ/L` is positive semi-definite to round-off;
- the malformed-port slab (V = 0.5) reproduces `1/V²` exactly.

These identities do not depend on `K_curl` beyond its null space, so they cannot detect
an error in `K_curl` itself.

**On the committed L2 mesh, the same mesh as static level 0:** Palace's band gives
`Σ|p|/f²` = 0.467302 GHz⁻², against the executed record's `1/S0` = 0.466994. So
**`δ_0 ≥ +6.6e-4`**, a lower bound from band data. Its exact value is
`C'_0/C_0 − 1`, which needs one static solve on the QMHP mesh. That solve has **not** been
run.

**The band arithmetic moment.** `B_h = (B/H)·H_h`, where `B/H` is the dispersion of the
band's participation spectrum: 1.004–1.009 on the committed rungs (`H/B` = 0.991–0.996).
It is inflated by high, weakly participating modes, which barely touch `H` or `S`.

In a lumped two-node reduction, `B/S = C_FF·(C⁻¹)_FF = 1/(1−k²)`, but only if two
conditions hold:

- (i) the second node is DC-grounded through its own inductance;
- (ii) every mode of the reduction lies in the band.

The meshed problem has only two conductors, ground (including the readout) and island. So
`C_FF` and `(C⁻¹)_FF` are not quantities of this mesh, and `1 − k²_eff := H/B` is a
definition, not a measured circuit parameter.

**What this changes about the executed static-anchor test** (its verdict, UNRESOLVED,
stands):

1. `r0 = S0/B0 = 0.997` was what the identities predict on one mesh, not a coincidence.
2. Its "CONTRADICTS, favours H0" branch was unreachable.

## 3. Was the paired test justified? — No, as designed

The prepared test was to run Palace at box levels 0, 1 and 2 over the island–gap–port
region, compute the static quantity on the mesh Palace refined, and decide on the
identity residual δ and the ratio drift. The review (`review/red_team_findings.json`, 42
findings from four independent read-only reviewers) and my own verification found:

| | finding | verified by |
|---|---|---|
| W1 | Co-movement and δ are **fixed by the identity in §2**. `S_h = (1+δ_h)·H_h`, with δ static, so SUPPORTS was close to predetermined once the static quantity moved | re-derived; reproduced to 1e-12 |
| W2 | Palace saves the refined mesh with a `nodes` section, which the reader refused. The attempt would have failed at level 1 | source `geodata.cpp:1554-1570`; every log prints "Mesh curvature order: 1" |
| W3 | The nesting check wrongly rejected MFEM bisection at level 1→2 | reviewer's MFEM emulation; consistent with bisection closure; not re-run by me |
| W4 | Integrity demanded 6 modes, but Palace writes every converged pair | N2R: `N = 6`, 9 rows written |
| W5 | The box missed the ground edge on three sides. The gap is 0.040 mm on x−, y− and y+, and 0.020 mm only on x+; I took the minimum distance for every side | mesh geometry |
| W6 | A dispatch-only workflow must exist on `main`. The approval procedure omitted that separately approvable merge | `origin/main`; commit `30fca75` |

Smaller issues are listed in `WITHDRAWN.json`:

- the commit-back step pushed without a rebase;
- the refined meshes would have survived only as a 90-day artefact;
- the one-attempt binding was weaker than the project's `run_authority`;
- the drift was defined on the fragile `B` rather than `H`;
- the `CONTRADICTS` reason string always said "decouple";
- the level-3 DOF estimate was too high;
- the claim "5% is a fifth of ×1.39" was wrong: a fifth is 7.8%.

**Withdrawn, not repaired.** Fixing W2–W6 would still leave a test whose decisive quantity
an identity fixes. The dispatch workflow and the approval draft were removed; they remain
in git history. `pairing_driver.py` stays as reviewed reference code, and its
`require_approval()` refuses while `WITHDRAWN.json` exists. `predeclaration.json` is
unchanged.

**The alternative, proposed and NOT prepared** (it needs your approval, because it solves
on the QMHP mesh): a **static-only** nested refinement study, with no Palace and no
eigen-solves.

- **Levels.** Uniform red levels 0, 1 and 2 of the committed mesh; level 2 needs an
  iterative solver, itself to be verified. At each level compute `C_h` and `C'_h`, hence
  `S_h`, `δ_h`, and exactly (by §2) Palace's complete harmonic band moment
  `H_h = S_h/(1+δ_h)` on those meshes.
- **Its one sharp test.** At level 0, `S0/(1+δ_0)` must equal the committed L2 band's
  `H = 2.13994 GHz²` to about 2e-5 plus eigen tolerance. That is where two independent
  codes, the static solver and Palace's eigensolver, meet on the same mesh.
- **What it would measure.** The convergence of both moments, and how far Palace's sheet
  port departs from the declared lumped element as the mesh is refined (δ). Both bear
  directly on Route A's inputs.
- **What it could not give.** `B/H`, the band dispersion, still needs eigen data.

## 4. The execution-time manifest (item 4)

`orchestrator.manifest.write_verified(root)` writes `manifest.sha256` **at execution time**
and re-verifies it at once. It raises if the tree does not match, so a driver cannot exit
claiming an intact record it did not check.

It is tested on its own, including a negative control. It is also tested end to end
through `pairing_driver.py`'s success and failure paths with a mock Palace: the record
verifies, a second attempt is refused, and no refined mesh enters the record.

Any future evidence driver calls it as its last step on every path. The executed
static-anchor record keeps its quarantine; it was not given a manifest after the fact.

## 5. What this record does not establish

It does not establish:

- `E_C` or `g`;
- that Route A is valid or invalid;
- the convergence of either moment;
- `δ_0` exactly;
- anything about the physical device.

The static-only alternative is a proposal, not a prepared test.

## 6. Files

| file | role |
|---|---|
| `WITHDRAWN.json` | why the test was withdrawn, each reason's verification, what carries forward |
| `review/red_team_findings.json` | the four reviewers' verbatim outputs (reviewer agreement is not evidence by itself) |
| `verify_nesting.py`, `nesting_verification.json` | item 1: conformity, conductor consistency, nesting and the Galerkin identity; synthetic controls |
| `spectral.py` | Whitney curl-curl, lumped and sheet port terms, all eigenpairs and moments of small pencils, the port-constrained static energy |
| `identities.py`, `identities.json` | item 2: the known-answer identities (lumped and sheet), the L2 same-mesh check, the committed rungs' band moments |
| `pairing_driver.py` | the withdrawn driver, kept as reviewed reference; it refuses to run |
| `predeclaration.json` | the withdrawn test's frozen pre-declaration, unchanged |
