# Pre-declared Faraday consistency test for the two readout surfaces

**Status:** declared before any field value has been seen. Nothing here has
been evaluated. It fixes, ahead of the data, the closed paths, connecting
segments, spanning surface, width-averaging treatment, phasor convention and
units of the test that will be applied to the difference between the
pre-declared primary surface `Γ_R(+Y)` and the mirror surface `Γ_R(−Y)` of
`functional.json`. It must be checked against the conventions of the supplied
diagnostic script before use; where they differ, the difference is reported,
not reconciled silently.

## 1. What is being compared

With `x₀ = −0.485`, `x₁ = −0.405`, `w = x₁ − x₀ = 0.080 mm`, `y_p = 0.050`
(pad edge), `y_g = 0.080` (ground edge), all at `z = 0`:

```
V₊ = (1/w) ∫_{x₀}^{x₁} dx ∫_{path₊(x)} E · dl ,  path₊(x): (x, +y_g) → (x, +y_p)   (l̂ = −ŷ)
V₋ = (1/w) ∫_{x₀}^{x₁} dx ∫_{path₋(x)} E · dl ,  path₋(x): (x, −y_g) → (x, −y_p)   (l̂ = +ŷ)
```

Both run from the ground plane into the pad, so both are `V_pad − V_ground`
in the `P_F1` sign convention. The quantity under test is the signed complex
difference `V₊ − V₋` per mode, not their average.

## 2. The closed loop `C(x)` for each `x ∈ [x₀, x₁]`

1. `path₊(x)`: through the dielectric gap from `G₊ = (x, +y_g)` to `P₊ = (x, +y_p)`.
2. **Pad crossing** from `P₊` to `P₋ = (x, −y_p)` along the pad surface. The pad
   is a zero-thickness PEC sheet on which the tangential field is imposed to
   vanish (an essential condition on the Nédélec degrees of freedom), so this
   segment contributes exactly zero to `∮ E · dl` in the discrete solution.
3. The reverse of `path₋(x)`: from `P₋` to `G₋ = (x, −y_g)` through the gap,
   contributing `−∫_{path₋} E · dl`.
4. **Ground return** from `G₋` back to `G₊` along the ground plane, hugging
   the boundary of the etched region: west along `y = −0.080` to
   `x = −0.485`, down to `(−0.485, −0.115)`, west along `y = −0.115` to
   `x = −0.715`, north along `x = −0.715` to `y = +0.115`, east along
   `y = +0.115` to `x = −0.485`, down to `(−0.485, +0.080)`, east along
   `y = +0.080` to `G₊`. Every point lies on the PEC ground sheet, so this
   segment also contributes exactly zero.

Hence `∮_{C(x)} E · dl = ∫_{path₊(x)} E · dl − ∫_{path₋(x)} E · dl`, and
averaging over `x`:

```
V₊ − V₋ = (1/w) ∫_{x₀}^{x₁} dx ∮_{C(x)} E · dl .
```

## 3. Spanning surface and the flux it carries

`C(x)` lies in the plane `z = 0`; its flat spanning surface `S(x)` is the
planar region it encloses: the island etch box `[−0.715, −0.485] × [−0.115, 0.115]`
together with the pad etch strip `[−0.485, x] × [−0.080, 0.080]`. On every PEC
sheet the normal flux density vanishes (`n · B = 0`), so only the etched parts
of `S(x)` carry flux:

- `A_west`: the island etch ring, minus the island `[−0.675, −0.525] × [−0.075, 0.075]`
  and minus the pad's western part `[−0.505, −0.485] × [−0.05, 0.05]`; this
  includes the island–pad gap `[−0.525, −0.505] × [−0.05, 0.05]` and the corner
  regions `[−0.505, −0.485] × (0.05 < |y| < 0.115)`;
- the two gap strips `[−0.485, x] × (0.050 < |y| < 0.080)`, i.e. the parts of
  `Γ_R(±Y)` themselves west of `x`.

With Palace's `e^{+iωt}` convention (`eigensolver.cpp`: `B = −(1/(iω)) ∇ × E`,
so `∇ × E = −iω B`), Stokes' theorem gives, after the `x`-average,

```
V₊ − V₋ = −iω [ ∫_{A_west} B_z dA  +  ∫_{strips} B_z(x', y) · (x₁ − x')/w dA ] ,
```

where the second integral runs over the full strips `[x₀, x₁] × (0.05 < |y| < 0.08)`
with the triangular weight `(x₁ − x')/w` that the width averaging produces.
This is the only flux quantity that may be compared with `V₊ − V₋`; an
unweighted flux through an arbitrary loop may not.

## 4. Units and phasors

Exported `E_real`, `E_imag`, `B_real`, `B_imag` are Palace's nondimensional
fields on a mesh in mm. With `λ = Lc/L0 = 4.0` and `ω_nd = 2π f · t_c`
(`t_c = 1e9 · Lc / c₀` ns, `Lc = 4 mm`), the identity above holds in
nondimensional form with lengths divided by `λ`; both sides are then scaled by
`√Z0` to volts, or left nondimensional, identically on both sides. The
comparison is complex: real and imaginary parts separately, and the phase
of `(V₊ − V₋)` against `−iω Φ` is reported, not the magnitudes alone.

## 5. What the test can and cannot show

For the discrete order-1 Nédélec solution the identity of §3 is exact:
`E_h` is tangentially continuous, `∇ × E_h` is the exact elementwise curl,
and `B_h` is that curl scaled. If the exported fields reproduce `E_h` and `B_h`
(per-element linear vertex data, Float32), the two sides agree to Float32
precision **as a matter of algebra**. Agreement therefore demonstrates that
the measured surface difference is the magnetic flux through the enclosed
gaps in this solve, i.e. an inductive voltage drop around the pad and island
perimeter, and that the export and integration are faithful. It does not
show that this flux, or either voltage, is converged in the mesh, nor that
either surface is "right". Disagreement beyond the Float32 floor would point
at the export, the integration or a mismatch of conventions, not at physics.

## 6. Information the stored fields must contain

- `E_real`, `E_imag` on the volume collection over the etched faces at
  `z = 0` inside `Γ_R(±Y)` (for `V±`) and `B_real`, `B_imag` on the volume
  collection over `A_west` and the strips (for the flux). If `B` is absent,
  `∇ × E` per element follows exactly from the linear vertex data and may
  replace it, with that substitution stated.
- The mode frequency `f_m` from `eig.csv` of the same record, for `ω`.
- The cycle-to-mode mapping (`cycle i` ↔ mode `i + 1`).

If any of these is missing from the archives, the test is not evaluated and
the missing item is named.
