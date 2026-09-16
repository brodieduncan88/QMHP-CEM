# S1 numerical recovery: the port diagnostic, the meshes, and one prepared experiment

Record: `results/COUPLED-S1-RECOVERY-20260916T105215Z` (116 KB, manifest intact).
**No Palace was launched.** Every source record was verified against its own
manifest before and after this analysis and none was written to; this record is
separately versioned and references the sources by their manifest digests:

| source | manifest digest | files |
|---|---|---|
| `COUPLED-PILOT-20260916T035733Z` (L1) | `8639bef802d70d19…` | 35 |
| `COUPLED-LADDER-O1-L2-20260916T080802Z` | `ced09e5913189ad0…` | 13 |
| `COUPLED-LADDER-O1-L3-20260916T091212Z` | `41d9645add217668…` | 13 |

The level-3 **CALIBRATION-UNSOUND** verdict stands as what the predeclared
procedure returned. What follows replaces the procedure, not the verdict.

---

## 1. The conversion is derived from source, and it is not calibrated on anything

The level-2 and level-3 rungs tried to *fit* a constant `κ` relating the two
port-face field probes to the port's stiffness energy, using modes whose energy
balance looked favourable. That was the wrong instrument. `κ` is not a free
parameter — it is fixed by the configuration, the mesh and Palace's unit
conventions, and every factor is in the pinned v0.13.0 tree.

**What Palace actually assembles.** An inductive lumped port enters the
stiffness matrix as a boundary `VectorFEMassIntegrator` with coefficient
`1/L_s` (`models/lumpedportoperator.cpp:571-591`,
`models/spaceoperator.cpp:300-307` and `:236-238`), so what enters the
eigenvalue is

```
E_port = (1 / 2ω²) ∫_Γ (1/L_s) |E_t|² dS ,   L_s = L · (w/l) · n
```

(`lumpedportoperator.cpp:578`, `lumpedportoperator.hpp:57-60`). What Palace
*reports* as `E_ind` is something else: `½|L||I|²` with `I = V/(iωL)` and `V`
the width-averaged line voltage `V = (1/w)∫_Γ E·l̂ dS`
(`lumpedportoperator.cpp:200-213`, `postoperator.cpp:493-508`). It is a
rank-one functional — it sees one scalar where the stiffness sees a field.

**What the probes measure.** `Type: "Default"` integrates `0.5·t·ε·|E|²` and
`Type: "MA"` integrates `0.5·(t/ε)·|E_n|²` (`fem/coefficient.hpp:373-413`),
both taking the field from the same side by the same rule
(`coefficient.hpp:330-360`), so at equal `t` and `ε = 1` their difference is
exactly `0.5·t_nd·|E_t|²` pointwise and the side choice cancels. Each is
integrated against the H1 space, whose basis is a partition of unity, so the
linear-form sum is the plain surface integral
(`surfacepostoperator.cpp:287-301`), and the driver divides by `E_elec + E_cap`
(`postoperator.cpp:419-427`, `basesolver.cpp:538-540`, `eigensolver.cpp:349`) —
the same denominator the port EPR uses. Therefore

```
p_port = E_port / (E_elec + E_cap) = κ · (p_D − p_MA) / ω_nd²
κ      = 1 / (t_nd · L_s_nd)
```

with `t_nd = t/(Lc/L0)` (`iodata.cpp:535`), `L_nd = L/(μ₀Lc)` (`:512`),
`ω_nd = 2πf·tc` and `tc = 10⁹Lc/c₀` ns (`:465`, `:539`), and `Lc` the largest
mesh bounding-box extent (`:452-464`) — **measured from the mesh file**, 4.000
mm exactly, not read from Palace's four-significant-figure log line.

For S1: `t_nd = 0.25`, `L_nd = 20.5820…`, `w/l = 0.02/0.04` measured from the
mesh, `n = 1`, giving

> **κ = 0.3886882529**, computed from declared numbers alone.

No solver output is read to produce it. That is what "not calibrated on modes
whose balance looks favourable" has to mean operationally, and
`tests/test_port_diagnostic.py` asserts it.

## 2. The three port numbers, and which of them is independent

`E_elec + E_cap` cancels out of the conversion, so `p_port` never touches an
energy column. It and the closure requirement share no input:

| quantity | reads | status |
|---|---|---|
| `p_probe = κ(p_D − p_MA)/ω²` | `surface-Q.csv`, `eig.csv`, geometry | **independent** |
| `p_reported = E_ind/(E_elec+E_cap)` | `domain-E.csv` | Palace's rank-one surrogate |
| `p_closure = 1 − (E_mag+E_cap)/(E_elec+E_cap)` | `domain-E.csv` | **not independent** |

`p_closure` is what the port term *must* be for the balance to close. Quoting
it as verification of that balance would be circular, and this record never
does. It is the *agreement* of `p_probe` with `p_closure` that is evidence,
because the two are computed from disjoint inputs.

**Level 3**, one `κ` for all six modes:

| mode | f (GHz) | `p_probe` | `p_reported` | `p_probe/p_closure` | `E_ind/E_port` |
|---|---|---|---|---|---|
| 1 | 1.709562 | 9.983353e-01 | 9.983176e-01 | 1.000000 | 0.9999823 |
| 2 | 4.087683 | 9.115929e-04 | 9.112764e-04 | 1.000000 | 0.9996528 |
| 3 | 9.109258 | 9.999471e-01 | 2.627565e-06 | 1.000000 | 2.63e-06 |
| 4 | 10.272094 | 9.999682e-01 | 2.768794e-07 | 1.000000 | 2.77e-07 |
| 5 | 11.098712 | 9.999676e-01 | 1.416941e-07 | 1.000000 | 1.42e-07 |
| 6 | 11.836121 | 8.599130e-04 | 4.203529e-05 | 1.000000 | 0.0488832 |

Worst relative disagreement: **2.05e-08 at level 3, 4.35e-07 at level 2**,
across all twelve rows, with the same derived `κ`.

So: **the port stiffness term accounts for the entire energy-balance defect, on
every mode, at both levels.** The "failures" were never about the solve. The
last column is the whole story — `E_ind/E_port = |∫E·d̂ dS|²/(A∫|E_t|²dS)`,
which Cauchy–Schwarz bounds by 1, with equality exactly when the port-face
tangential field is uniform and aligned. It is a direct measure of how far each
mode's port field is from the one configuration the lumped-port circuit model
represents, and it is one-sided: the surrogate can only *understate*.

**What this does not establish.** It says nothing about whether the mesh
resolves that term, and it is not a convergence statement about anything.

**A consequence worth naming.** With the port term evaluated correctly the
balance closes for *every* mode to about 2e-5, including the modes the
admission rule rejects. The rule's discriminating power therefore comes from
the surrogate's failure, not from algebraic convergence: it selects modes whose
port field is close to uniform and aligned. That is a defensible criterion, and
it is not the same thing as "this row is an eigenvector". The rule's own
`what_it_establishes` already said it tests the *reported* energies; this makes
the point quantitative. **No threshold changes.**

## 3. The meshes, as built rather than as prescribed

Measured on the committed mesh files. The model is identical at every level —
same physical names, same bounding box, same face areas, same port orientation
(`MODEL UNCHANGED ACROSS LEVELS`), so the ladder was a refinement study.

| level | requested `h_gap` | port triangles | element size **on the face** | longest edge / `h_gap` | elements across the 0.02 mm width |
|---|---|---|---|---|---|
| 1 | 0.010000 mm | 17 | 0.010425 mm | 2.00 | **1.92** |
| 2 | 0.006667 mm | 25 | 0.008597 mm | 2.07 | **2.33** |
| 3 | 0.005000 mm | 45 | 0.006407 mm | 2.21 | **3.12** |

The port face is `0.02 × 0.04 mm`, planar, normal `+ẑ`, one physical tag (10),
area `8.0e-4 mm²` to 1e-9 at every level. It spans the declared 0.04 mm gap in
`Y` between the **`F1.island`** conductor at `y = −0.075` and the ground plane
at `y = −0.115` — both PEC — with its two X-normal edges on etched dielectric.
So the two edges bounding the face *along the port direction* are
zero-thickness conducting edges, i.e. field singularities, and the port
direction is perpendicular to them. That is the correct topology for a
fluxonium element site bridging island to ground; it is also the worst case for
resolving `|E_t|` on the face.

**Why the ladder could never resolve this face.** The size field is a gmsh
`Distance`/`Threshold` anchored to the *conductor and etch curves*: `h_gap` on
those curves, blending linearly to `h_far` over the 0.08 mm halo. The port
face's interior is up to half its width (0.01 mm) from the nearest such curve,
and the prescribed size there is

| level | `h_gap` | prescribed size at the port centre | ÷ `h_gap` | ÷ port width |
|---|---|---|---|---|
| 1 | 0.010000 | 0.050417 mm | **5.0417** | 2.52 |
| 2 | 0.006667 | 0.033611 mm | **5.0417** | 1.68 |
| 3 | 0.005000 | 0.025208 mm | **5.0417** | 1.26 |

`h_gap` and `h_far` both carry the level factor while the halo does not, so the
whole profile scales by the level factor and **the ratio is scale-invariant**.
At every level the field asks for an element larger than the port width itself;
the only thing setting the element count on the face is the face's own
boundary. Refining the ladder does not change that, and did not.

**The early port-face `continue` is not the defect it looks like.** Rebuilding
the OCC model with the mesher's own code and asking directly: three of the port
face's four curves *are* in the Distance field, contributed by the neighbouring
conductor and etch faces. Only the curve whose other neighbour is the untagged
ground plane is omitted — the same pattern on all three ports. Adding it would
not resolve the face either, because it is the blend that coarsens the interior,
not the missing curve. The fix is a constraint anchored to the face.

## 4. How the tested sequence actually moved

The ladder's estimator refused an order of convergence on these three rungs and
that refusal stands. The complementary question — do the three points follow a
consistent law in the *divergent* direction? — separates the two tracked modes
sharply:

| tracked mode | role | f(L1), f(L2), f(L3) | q in `f² ∝ h^−q` | the two intervals agree to |
|---|---|---|---|---|
| L1m1 | LUMPED_DOMINATED | 1.158333, 1.461887, 1.709562 | 1.148, 1.088 | **5.2 %** |
| L1m2 | FIELD_DOMINATED | 3.693189, 3.885511, 4.087683 | 0.250, 0.353 | 40.8 % |

The fluxonium-like mode's port participation is 0.9985 — its stiffness is
essentially *all* port term — so its `ω²` and the port-face integral
`∫|E_t|²dS` must move together, and they do: the integral grows by 1.3672 from
L2 to L3 against `(f₃/f₂)² = 1.3674`. (That is an internal consistency check on
the conversion, not independent evidence about the frequency.) The readout-like
mode, whose port participation is 9e-4, follows no consistent exponent.

**What this does not establish**, stated because the earlier write-up went too
far:

- it does **not** prove mathematical nonconvergence — three points and two
  intervals cannot, and a sequence may follow one law over a range and another
  beyond it;
- it says **nothing about the physical architecture**. Every number here is
  about the discretisation of a declared idealisation;
- it does **not** show that every in-budget mesh has been exhausted. §5 exhibits
  two that are not.

What it does say is narrower and useful: the tested sequence moves in a
consistent direction with a consistent exponent on the port-dominated mode,
which is what an unresolved local feature looks like, and is a reason to refine
*locally* rather than globally.

## 5. One controlled local-refinement experiment, prepared and dry-run

Held fixed: the S1 geometry, materials and substrate permittivity; the port
dimensions, direction, inductance and formulation; conductor thickness and edge
treatment; every boundary condition and physical group; the pinned Palace
v0.13.0 image and every solver setting; `h_far`, the halo and the conductor/etch
Distance field, so the **distant size prescription is the baseline's**.

Changed: one number. A gmsh `Box` field holds `h_port` over the port rectangle
padded by 0.010 mm in every direction, blending back to `h_far` over 0.020 mm,
combined with the existing field by `Min`. Because the box field returns `h_far`
outside the padded box and the combination is a minimum, **it can only refine**.
The default mesher path is byte-identical to the committed level-3 mesh
(`sha256 93948899be17c6c5…`), asserted in CI.

| mesh | base | `h_port` | DOF (order 1) | of the 250 000 rule | port triangles | across the width |
|---|---|---|---|---|---|---|
| baseline `L2` *(already solved)* | 2 | — | 79 944 | 32.0 % | 25 | 2.33 |
| **R1** | 2 | 0.003333 mm | **80 762** | 32.3 % | 176 | **6.17** |
| **R2** | 2 | 0.001667 mm | **111 238** | 44.5 % | 680 | **12.13** |
| contrast `L3` *(already solved)* | 3 | — | 147 372 | 58.9 % | 45 | 3.12 |

All measured by dry run, not estimated, and reproducible: both meshes hash
identically on repeat runs. Unlike the ladder's field, this constraint actually
holds on the face — the achieved element size is within 5 % of `h_port`.

The contrast is the point. **R1 costs 818 DOF more than the baseline — 1.0 % —
and gives 2.6× the port-face resolution. L3 cost 67 428 more DOF — 84 % — for
1.34×.** The two axes are cleanly separated, so a large shift under R1 would
localise the cause.

**Unchanged**: `Δ|p| ≤ 1e-2`, `Δf ≤ 1e-4`, backward error `1e-6`, admission
`|R−1| ≤ 1e-3`, matching rule `0.1.1`, the magnitude convention, the 0.5–9.0 GHz
window, the 250 000-DOF rule, the 45-minute cap, order 1.

**Predeclared outcomes** (full text in the record's
`prepared_experiment.predeclaration`):

| | if | would mean | would *not* mean |
|---|---|---|---|
| **A** | m1 moves ≳ its 0.248 GHz L2→L3 shift; m2 moves ≪ its 0.202 GHz shift | the port face's discretisation drives the port-dominated mode, and the ladder spent its budget on the wrong region | that anything converges, or that a limit exists |
| **B** | m1 barely moves | the port face is not the frequency driver; the port-stiffness account of the *imbalance* stands regardless | that the mesh is adequate |
| **C** | both move comparably | a global effect reached the box, or the box perturbed more than intended — check the distant element sizes first | that local refinement failed |
| **D** | m1 moves to R1 then much less to R2 | the face was under-resolved and R1 resolves it *for this mode* | that the frequency converged |
| **E** | `p_probe` changes materially R1→R2 | the port-face integral has not settled | anything about a limit |

**Two meshes cannot establish convergence and this experiment does not claim
to.** It discriminates between candidate causes; it does not resolve them.

**Stop conditions**, predeclared so that stopping is a planned outcome rather
than a judgement made after seeing numbers:

| condition | what happens | enforced by |
|---|---|---|
| measured DOF above the 250 000 rule | the solve is not launched; `REFUSED-DOF-BUDGET` | the driver, already in place and unchanged |
| a solve exceeds the 45-minute cap | killed and recorded as failed; the cap is not extended | the existing timeout |
| the built mesh does not hash to the mesh the approval names | stop before solving; `REFUSED-MESH-MISMATCH` | the approval's `dry_run_mesh_sha256`, checked by the driver |
| the matching rule refuses | report and stop — a mode set changing under a mesh change confined to the port neighbourhood *is* the finding | matching rule `0.1.1`, unchanged |
| `p_probe` vs `p_closure` disagrees by more than 1e-4 on any mode | stop and resolve that **before reading any frequency**: the derived conversion would not describe the refined mesh and every other number would rest on it. Observed range on the committed rows is 2e-8 to 4.3e-7, so this is a wide margin | reported per mode by the diagnostic |
| both runs complete | report against the five outcomes and **stop for review** — no third mesh, no base-level change, no order-2 run without a further approval | this predeclaration |

**Cost**: two order-1 solves, projected ≈82 s and ≈120 s from the baseline's
81.2 s at 79 944 DOF and the measured within-order timing exponent of 1.10.
Both far inside the 45-minute cap.

**Nothing here starts it.** `.github/ladder-approval.json` is untouched and
carries no `port_refinement` block, asserted in CI. Approving the experiment
means adding one:

```json
"port_refinement": {
  "id": "R1", "h_port_mm": 0.003333333333333333,
  "pad_mm": 0.010, "transition_mm": 0.020, "ports": ["port_F1"]
}
```

`h_port_mm` is `h_gap(level 2)/2 = 0.006666666666666666/2` for R1 and `/4 =
0.0016666666666666666` for R2, written out to the last digit because the mesh
hashes below are for those exact values:

| mesh | `sha256` of the dry-run mesh |
|---|---|
| R1 | `a49ef282c7f07c56…` |
| R2 | `5a983c9125a9b9ce…` |

The driver reads every number from that record, so no code change can introduce
a refinement; a refined run gets its own record id and is deliberately kept out
of the ladder's convergence fit, because it is not a point on a sequence in `h`.

## 6. Evidence durability, exercised

The level-3 rung's first attempt completed its solve and lost it: the report was
rendered before the manifest and the record pointer were written, and the
renderer raised. That ordering is now inverted, and the guarantee is
**exercised rather than asserted** — `--fail-render` forces the renderer to
raise, and CI checks that afterwards the record pointer names the directory, the
manifest verifies, `summary.json` carries every measured quantity, `report.md`
explains the failure, and the process exits non-zero.

Two further gates, both regression-tested:

- `scripts/check_record_files.py` refuses a record containing a file kind it may
  not carry, and now runs **before `git add`** in the ladder workflow. This is
  the check that was missing when the level-2 rung committed a 123 MB ParaView
  tree that both the approval record and the workflow header said would be
  uploaded and not committed. All three existing records pass it.
- The artifact uploads are `if: always()`, so field output leaves the runner
  whatever else fails, while staying out of Git.

## 7. Confirmed implementation defects

| | defect | status |
|---|---|---|
| 1 | The port-field verdict was produced by *fitting* `κ` on admitted modes, assuming the rank-one surrogate faithful on them. It is not faithful on all of them, which is how level 3 reached CALIBRATION-UNSOUND. | **Fixed by removal.** `κ` is derived; no calibration step remains. The L3 verdict stands as the record of what the old procedure returned. |
| 2 | Nothing checked what a record contained before committing it; 123 MB of ParaView output was committed against both the approval record and the workflow header. | **Fixed.** Shared guard, run before `git add`, regression-tested both ways. |
| 3 | The report was rendered before the manifest and the record pointer were written, so a presentation bug destroyed a completed solve. | **Fixed and exercised**, not merely asserted. |
| 4 | The size field is anchored to conductor/etch curves only, so the port face's interior is never at `h_gap` — at any level. | **Diagnosed and quantified** (§3). Not silently "fixed": the correction is the proposed experiment, which is the owner's to approve. |

Not a defect, checked and cleared: the early port-face `continue` in the mesher
(§3). Three of four curves arrive from the neighbours.

## 8. What is still open

- **The readout-like mode's drift is unexplained.** Its port participation is
  9e-4, so §1–§4 do not account for it, and its exponents do not agree between
  intervals. If outcome B or C obtains, this is the next thing to chase.
- **No convergence claim exists for either mode**, and none is proposed here.
- **The zero-thickness PEC idealisation** puts field singularities on every
  conductor edge in the model, not only at the port. That is a modelling
  question, and it is not settled by any measurement in this record.
- **Quadrature.** The probes integrate through `BoundaryLFIntegrator` while the
  stiffness term goes through a libCEED `VectorFEMassIntegrator`; the two need
  not share a rule. Both integrands are degree-2 per face for order-1 Nédélec on
  affine tetrahedra, which either rule integrates exactly, and the measured 2e-8
  agreement would not survive a mismatch — but a Palace build instrumented to
  print `∫_Γ(1/L_s)|E_t|²dS` directly would settle it, and the saved outputs
  cannot. Recorded as an unverified assumption in the record itself.
- **The port-face field distribution is not in evidence.** The ParaView trees
  were uploaded as artifacts, not committed, so the *shape* of `E_t` on the face
  — as opposed to its integral — cannot be examined from the repository.
