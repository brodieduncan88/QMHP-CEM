# Readout-voltage functional: definition, and what the archived fields can and cannot yet support

**Status:** offline feasibility record. No Palace run, no readout element, no
coupling extraction. **No field value was evaluated:** the N1R/N2R field
artefacts exist (correction below) but could not be retrieved from the
analysis environment, so this note fixes the functional and its evaluation
recipe, measures the mesh-side feasibility on the committed mesh, and stops.
The record is `experiments/readout-voltage-functional/`. The registered
target of `coupling-definition.md` §3 is retained; the environment
normal-mode coupling of the synthetic study is not adopted.

## 0. Correction and the state of the artefacts

An earlier note in this campaign said N1R and N2R saved no fields. That was
wrong. Each record's `summary.json` (`rung.field_output`) states that Palace
wrote `postpro/paraview` (132 MB for N1R, 157 MB for N2R), that it was moved
out of the record and uploaded as a workflow artefact, and that it is not
committed. The GitHub API confirms both artefacts:

| record | run | artifact | name | size (bytes) | digest (API) |
|---|---|---|---|---|---|
| N1R | 35438882836 | 10583481701 | `order1-ladder-fields-35438882836-1` | 95 969 529 | `sha256:79c0401c…1ff0` |
| N2R | 35313973073 | 10533683685 | `order1-ladder-fields-35313973073-1` | 113 746 865 | `sha256:1ca851c4…e08e` |

Both API digests equal the SHA-256 values supplied with the task
(`experiments/readout-voltage-functional/artefacts.json` holds them in
full). **The bytes were not obtained:** the API download resolves to
`productionresultssa19.blob.core.windows.net` (N1R) and
`productionresultssa10.blob.core.windows.net` (N2R), and the session's
egress proxy rejected the CONNECT to the first with a 403, which the
environment documents as an organisation network-policy denial to be reported
and not worked around. The unauthenticated GitHub web URL for the artefact
also returns 403. So the content digests were not recomputed here, and
steps 3 and 4 of the task (F-port cross-check, `ρ_m`, `r₁₂`) were **not
executed**. Everything below that does not need the bytes was done.

## 1. The functional, defined before any evaluation

**Coordinate.** `coupling-definition.md` §2 defines node `R1` as "the
single-mode (fundamental) representation of a distributed resonator at its
coupling node", and the declaration names the `R1` conductor as
`R1.coupling_pad + R1.cpw centre conductor`, shorted to ground at the meander
end. The coupling node is therefore the coupling pad, and the node voltage of
`R1` is the pad's voltage against the chip ground plane. The fluxonium port
`P_F1` fixes the sign convention: "from ground (−Y side) to the island (+Y
side); `V_port = V_F1 − V_ground`".

**Registered geometry (mm, spec §7.3 frame, from the declaration through
`solvers.palace.coupled_geometry`):** island `[−0.675, −0.525] × [−0.075, 0.075]`;
coupling pad `[−0.505, −0.405] × [−0.05, 0.05]`; pad etch (pad inflated by the
declared 0.030 mm) `[−0.535, −0.375] × [−0.08, 0.08]`; island etch (island
inflated by 0.040 mm) `[−0.715, −0.485] × [−0.115, 0.115]`; port face `P_F1`
`[−0.61, −0.59] × [−0.115, −0.075]`, direction `+Y`, length 0.040 along the
direction, width 0.020.

**Palace's port voltage,** from the pinned source
(`lumpedportoperator.cpp`, `InitializeLinearForms`): for a rectangular
element, `V = (1/w) ∫_Γ E · l̂ dS`, the width-averaged line integral of `E`
along the element direction over the port face. This is the rule the
functional reuses, on a surface that carries no element.

**Definition.**

```
V_R := (1/w_R) ∫_{Γ_R} E · l̂ dS        (per eigenmode, complex)
Γ_R(+Y) = [−0.485, −0.405] × [0.050, 0.080] at z = 0,   l̂ = −ŷ   (ground at +0.080 → pad at +0.050)
Γ_R(−Y) = [−0.485, −0.405] × [−0.080, −0.050] at z = 0, l̂ = +ŷ   (ground at −0.080 → pad at −0.050)
w_R = 0.080 mm
```

- *Location and reference conductor:* the pad's `±Y` gaps to the ground
  plane (the `z = 0` PEC sheet outside the etch; physical `sheet_pec`).
- *Orientation:* from the ground plane into the pad, the `P_F1` convention,
  so `V_R = V_pad − V_ground` in the same sense as `V_F = V_island − V_ground`.
- *Why this rectangle and not the full 0.100 mm pad edge:* for
  `x ∈ [−0.505, −0.485]` the island's etch removes the ground beyond
  `|y| = 0.080` up to `0.115`, so the pad-to-ground distance there is
  0.065 mm, not the declared 0.030 mm. The clean part of the edge, facing
  ground across exactly the declared gap, is `x ∈ [−0.485, −0.405]`. The
  mesh confirms this (§3).
- *Why not the other sides:* the `−X` side faces the island across the
  0.020 mm coupling gap, not ground; the `+X` edge joins the CPW centre
  conductor for `|y| ≤ 0.025` and otherwise faces the merged pad/slot etch
  with no ground at a uniform distance.
- *Why not the declared `P_R1` tap:* it sits 0.150 mm from the shorted end,
  at the current antinode, as a Route B excitation surface. A quarter-wave
  line driven off resonance has a mode-dependent standing-wave profile
  (`∝ cos k_m x` with `k_m ∝ f_m`), so a tap voltage relates to the pad
  voltage by a factor that differs between modes 1 and 2; it is not the
  coupling-node coordinate.
- *Units:* the exported field arrays are Palace's nondimensional `E`
  (`postoperator.cpp` `WriteFields`/`ScaleGridFunctions` write the mesh in
  input units and rescale the coefficients so that evaluated values are the
  nondimensional field). With `λ = Lc/L0` in mesh units,
  `V_nd = (1/λ)(1/w_mm) ∫ E_nd · l̂ dS_mm` and `V [V] = √Z0 · V_nd`
  (`iodata.cpp` `DimensionalizeValue`: `Hc · Z0 · Lc` with
  `Hc = 1/√(Z0 Lc²)`). The config declares no `Model.Lc`, so `Lc` is the
  largest bounding-box extent: the mesh spans `4.0 × 4.0 × 1.93 mm`, hence
  `λ = 4.0`, and `√Z0 = 19.409541814844687` with Palace's constants. Every
  one of these factors cancels in `ρ_m`.

Two things were **not** chosen: the location (fixed by the registered
definition and the layout) and the sign convention (fixed by `P_F1`). The
mirror surface `Γ_R(−Y)` is kept only as the path-independence check.

**Why this is the synthetic `R` observable.** In the lumped model
`V_m ∝ f_m² L^{1/2} v_m`, so the ratio of node voltages in one eigenmode is
`ρ_m = V_mR/V_mF = √(L_R/L_F) · v_mR/v_mF`. `V_mF` is Palace's `P_F1` port
voltage (island against ground); `V_mR` as defined above is the pad against
ground in the same field. The factor `√(L_R/L_F)` is the readout scale gauge
and is not a physical number, so the datum is `r₁₂ = ρ₁/ρ₂`, complex; the
eigenvector's global phase cancels inside each `ρ_m`, and `Im ρ_m / Re ρ_m`
is a diagnostic of numerical non-reality, not a licence to take `|r₁₂|`.

## 2. F-port cross-check recipe (specified, not executed)

The boundary data collection (`paraview/eigenmode_boundary`) carries the
boundary elements with their attribute and `E_real`, `E_imag` as
per-element Lagrange point data (`SetHighOrderOutput(true)`,
`SetLevelsOfDetail(order = 1)`, `VTKFormat::BINARY32`). Palace writes one
cycle per saved mode through `PostprocessFields(post_op, i, i + 1)`
(`eigensolver.cpp`): cycle `i` holds mode `i + 1` and the stored time is the
mode number; the config saved 6. For mode `m`: select the attribute-10 triangles; on each,
`∫ E·ŷ dS = area × mean of the three vertex values` (the order-1 Nédélec
field is linear inside every element, so this is exact up to Float32); sum,
divide by `w = 0.020 mm` and by `λ = 4.0`, multiply by `√Z0`; compare `Re`
and `Im` separately with `port-V.csv`. Tangential continuity of the Nédélec
space makes `E·ŷ` on the `z = 0` face identical from either neighbouring
element, so the side the boundary export evaluates (the larger permittivity)
does not affect this integral. Expected floor: Float32 on values
(`6e-8` relative) and on coordinates (`≈3e-8 mm` on a 0.040 mm face) gives an
order-`1e-6` relative floor, which is the size of the independently reported
`≈2e-6`. Reproducing that number would confirm the file layout, the scale
factors and the integration; it says nothing yet about the readout surface.

## 3. Mesh-side feasibility, measured on the committed L2 mesh

`mesh_feasibility.py` reads the committed N1R mesh
(`coupled_chip_cell_L2.msh`, byte-identical to N2R's) and classifies every
`z = 0` face of the volume mesh by whether it is a `sheet_pec` boundary
element, a port element, or etched dielectric.

| check | result |
|---|---|
| `port_F1` face | 25 triangles, area `8.000e-4 mm²` = declared `0.020 × 0.040`; bbox `[−0.61, −0.59] × [−0.115, −0.075]`, `z = 0` |
| `Γ_R(+Y)` / `Γ_R(−Y)` | 60 / 60 faces, all etched, 0 PEC faces inside; 23 distinct node levels across the 0.030 mm gap; edge lengths 0.0042 / 0.0089 (median) / 0.018 mm |
| pad side of each rectangle (`0.040 < |y| < 0.050`) | 24 of 24 faces PEC (the pad) |
| ground side (`0.080 < |y| < 0.090`) | 22 of 22 faces PEC (the ground plane) |
| corner `x ∈ [−0.505, −0.485]`, `0.080 < |y| < 0.115` | 23 faces, 0 PEC: island etch, as predicted |
| island–pad gap `x ∈ [−0.525, −0.505]` | 54 faces, 0 PEC |
| N1R/N2R refinement box `[−0.62, −0.58] × [−0.125, −0.065]` | does not overlap `Γ_R` |

So the integration surfaces exist as etched dielectric faces of the volume
mesh, bounded by the pad on one side and by ground on the other, resolved
by about three to four elements across the gap. They are **not boundary
elements**, so `V_R` must come from the volume data collection
(`paraview/eigenmode`), from the tetrahedra whose faces lie on `z = 0`
inside `Γ_R`; the port face, by contrast, is a boundary element and can be
taken from the boundary collection.

Because the Palace-side refinement of N1R (1 level) and N2R (2 levels) is
confined to the port box, the readout gap is discretised identically in both
records. Therefore an N1R-versus-N2R difference in `ρ_m` or `r₁₂` would
measure the effect of port-face refinement on the mode fields and on `V_F`,
**not** the convergence of the readout integral; a readout-gap mesh
sensitivity would need a different mesh, which is not proposed here.

## 4. Precision and what the cross-check would and would not establish

- **Float32:** values to `6e-8` relative, coordinates to about `3e-8 mm`;
  order-`1e-6` on each voltage, order-`2e-6` on `ρ_m`. Adequate for a
  diagnostic; the exports are not a substitute for the double-precision FE
  coefficients and must not be re-used as such.
- **Interpolation:** none is needed where the surface coincides with element
  faces; per-element vertex values are exact for the linear field. If a
  quadrature point falls inside an element rather than on a face, the
  containing element's linear interpolant is still exact.
- **Path dependence:** `∮ E·dl = −iω Φ_B` between the two surfaces, so
  `V_R(Γ_R+) − V_R(Γ_R−)` bounds the Faraday term plus mesh asymmetry; it is
  the first number to look at, and it is not yet known.
- **Agreement on the F port** would certify the layout, scale and integration
  routine. It would not certify the readout surface, whose faces are volume
  faces of a different kind, in an unrefined region, with no Palace number to
  compare against.

## 5. What the synthetic three-mode inversion assumes that the real EM model has not verified

1. **Model adequacy.** A three-node lumped circuit with one additional mode.
   The real environment is distributed: the resonator's profile is
   mode-dependent, the six computed modes span 1.5–9.5 GHz, and which mode, if
   any, plays the synthetic `X` is unknown; the dark-mode limit of the
   synthetic study says the F-site data cannot tell.
2. **Mode completeness.** The sum-rule deficit of the two-mode inversion is
   unresolved (the compatibility note); `r₁₂` does not address it.
3. **The pad as the single-mode coordinate.** Choosing the coupling pad makes
   the coordinate the registered one; it does not make the single-mode
   representation exact, and the pad-versus-tap argument of §1 shows the
   representation is mode-dependent at some level not yet quantified.
4. **Path independence of `V_R`** (§4), untested.
5. **`V_F` as the island node voltage.** The 2e-6 reproduction, once done,
   confirms Palace's own definition on its 0.020 mm strip, not that this
   equals the lumped node voltage of the island.
6. **Participation accuracy.** The node-basis recovery amplifies the
   participation error about seven-fold into `g`. The ladder's own record
   (`summary.json`, `port_resolution_sensitivity`) shows the probe-derived
   port participation of the readout-like mode moving from `7.80e-4` to
   `9.22e-4` between the L2 baseline and the refined N1R mesh, an 18 %
   change; at that level the synthetic sensitivity table gives no useful
   bound on `g`, whichever coordinate is chosen.
7. **Maxwell admissibility** of any fitted node-basis circuit, and the
   signed-EPR and equipartition conversions, remain to be checked on real
   data.

Obtaining `r₁₂` establishes none of these; it removes one continuous
ambiguity of the synthetic model and nothing else. It confers no permission
to extract `g`.

## 6. Result

The registered readout coordinate **can** be mapped unambiguously to a
non-loading functional: the pad-to-ground voltage on `Γ_R`, with location,
orientation, reference, surface, width and units fixed above from the
declaration and Palace's own rules, and its integration surfaces are present
and resolved in the committed mesh. The archived fields **should** support the
evaluation (boundary collection for the port, volume collection for the pad),
and the F-port cross-check is fully specified. **It was not carried out**,
because the artefact bytes are unreachable from this environment under the
current network policy. The one action that would let the next attempt
proceed is making the two archives reachable (a permitted host, or the files
placed where the analysis can read them); no solve, no readout element and
no extraction follow from that.

Not done, by instruction: no Palace run, no active readout element, no
real-data coupling extraction, no guard relaxation, no Route B, no N3, no
physical redesign, no merge of PR #7, no random-start or identifiability
campaign.
