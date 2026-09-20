# Review of the external readout-field diagnostic: the two pre-declared surfaces

**Status:** review of an **externally produced** post-processing diagnostic.
No Palace run, no coupling extraction, no change to any historical record or
to the registered target. The supplied package is preserved with its hash in
`experiments/readout-voltage-functional/external-diagnostic/`; every number
below that comes from it is labelled as external, and every number derived
from it by arithmetic is labelled as derived.

## 1. Reproduction: what was and was not done

**Received.** `QMHP_Readout_Field_Diagnostic.zip` (15 429 bytes, SHA-256
`4408146e…f97e`) through the session upload mechanism. Its internal
`manifest.sha256` verifies for all four files (README, HANDOFF, script,
`evaluation/results.json`).

**Not received.** `N1R_fields_35438882836.zip` and
`N2R_fields_35313973073.zip` did not arrive; the only reachable copies remain
the Actions artefacts behind the network policy, which is not to be worked
around. Consequently the supplied script was **not run here**, no archive
hash was recomputed here, and `results.json` is **not reproduced locally**.
It stays an externally produced diagnostic, as its HANDOFF requires.

**Verified locally, without the archives.**

| check | result |
|---|---|
| script's pinned blob SHA of `functional.json` at 5bc50d0 | matches the repository |
| script's pinned blob SHAs of both `port-V.csv` files | match the repository |
| script's port-voltage reference constants | equal the committed CSV values for m1, m2 of N1R and N2R |
| script's surfaces, directions, widths, `√Z0/λ` | equal `functional.json` (+Y `[−0.485, −0.405] × [0.050, 0.080]`, `l̂ = −ŷ`; −Y mirror, `l̂ = +ŷ`; `w_R = 0.080`, `w_F = 0.020`, `19.4095/4`) |
| internal arithmetic of `results.json` | `r₁₂ = ρ₁/ρ₂`, both mirror metrics, both mesh metrics and all four F-port errors recompute exactly from the listed voltages |
| the "interface attribute 25" the diagnostic integrates over | Palace v0.13.0 adds boundary elements at material interfaces on load (`geodata.cpp`), so the substrate–vacuum faces at `z = 0` inside the rectangles are in the boundary export; this corrects the earlier note that the volume collection would be needed |
| tooling for a future local run | `shapely` is in the locked environment; `vtk` is not |

**Discrepancies.** None found between the package's stated inputs and the
repository, and none inside the package. The reported F-port agreement of
`2.0045e-6` to `2.0063e-6` relative is the external evaluator's; it matches
the earlier independent `≈2e-6` and the Float32 floor predicted in
`readout-voltage-functional.md` §2. It certifies the export layout, the unit
scale and the integration on the port face, and nothing about the readout
surfaces.

## 2. The measured surface difference (external values; derived quantities marked †)

Complex readout voltages in volts as the external diagnostic reports them,
with the eigenvector normalisation and global phase of each solve. `V₊` is the
pre-declared primary (+Y), `V₋` the mirror (−Y). Differences are signed
complex values `V₊ − V₋`.

| record | m | `V₊` (V) | `V₋` (V) | `V₊ − V₋` (V) † | `|Δ|/|V₊|` † | `|Δ|/max` † | `|Δ|/|V_F|` † |
|---|---|---|---|---|---|---|---|
| N1R | 1 | 0.042077401 + 0.006812533 i | 0.048509288 + 0.007853886 i | −0.006431887 − 0.001041353 i | 15.29 % | 13.26 % | 5.83e-4 |
| N1R | 2 | −2.430702616 − 2.155870441 i | −2.427038426 − 2.152620553 i | −0.003664191 − 0.003249889 i | 0.151 % | 0.151 % | 5.62e-3 |
| N2R | 1 | 0.023341036 + 0.036386783 i | 0.026973809 + 0.042049981 i | −0.003632773 − 0.005663199 i | 15.56 % | 13.47 % | 5.98e-4 |
| N2R | 2 | −1.811550684 + 2.697269916 i | −1.808755405 + 2.693107952 i | −0.002795279 + 0.004161963 i | 0.154 % | 0.154 % | 5.70e-3 |

The phase of `V₊/V₋` is 0.0000° in all four cases †: the two surfaces are in
phase, and the difference is a pure magnitude difference along the mode's
phasor, as expected for a real lossless eigenmode. The absolute difference is
5–7 mV in every case † although `|V_R|` differs by a factor of about 60
between the modes; the relative difference is therefore large in the
fluxonium-like mode and small in the readout-like mode.

Ratios (external; imaginary parts shown as reported, not discarded):

| record | `ρ₁` (+Y) | `ρ₁` (−Y) | `ρ₂` (+Y) | `ρ₂` (−Y) | `r₁₂` (+Y, primary) | `r₁₂` (−Y, mirror) |
|---|---|---|---|---|---|---|
| N1R | −3.81269423e-3 − 1.1e-12 i | −4.39549679e-3 − 9.4e-12 i | 3.72887572 − 1.4e-10 i | 3.72325459 + 2.6e-9 i | −1.02247823e-3 − 3.4e-13 i | −1.18055231e-3 − 1.7e-12 i |
| N2R | −3.84088065e-3 − 2.7e-11 i | −4.43867109e-3 + 3.0e-12 i | 3.69581095 + 8.4e-10 i | 3.69010821 − 4.5e-9 i | −1.03925247e-3 − 6.9e-12 i | −1.20285662e-3 − 6.5e-13 i |

**Surface dependence, separately from mesh change †:**

| effect | quantity | N1R | N2R |
|---|---|---|---|
| surface (+Y vs −Y) | `r₁₂(+Y) − r₁₂(−Y)` | +1.5807e-4 | +1.6360e-4 |
| surface | relative, max metric | 13.39 % | 13.60 % |
| surface | mode-1 voltage, relative to `V₊` | 15.29 % | 15.56 % |
| surface | mode-2 voltage, relative to `V₊` | 0.151 % | 0.154 % |

| effect | quantity | +Y (primary) | −Y (mirror) |
|---|---|---|---|
| mesh (N1R → N2R) | `r₁₂` signed change | −1.6774e-5 | −2.2304e-5 |
| mesh | `r₁₂` relative change | 1.64 % | 1.89 % |
| mesh | `ρ₁` relative change | 0.74 % | 0.98 % |
| mesh | `ρ₂` relative change | 0.89 % | 0.89 % |
| mesh | `|V_R|` change, mode 1 / mode 2 | +1.42 % / +0.004 % | +1.66 % / +0.0006 % |
| mesh | `|V_F|` change, mode 1 / mode 2 | +0.67 % / +0.90 % | same |

The external diagnostic also reports that the exported triangles
intersecting each rectangle are identical between N1R and N2R (geometry
hashes equal), consistent with the refinement box not reaching the readout
gap. So the mesh change above is the response of the fields to the
port-region refinement, not a readout-gap convergence measure, and the
surface effect is about eight times the mesh effect on `r₁₂`.

Neither the 13–14 % nor the 15 % is a coupling-error percentage, and the
10 % Route-A/Route-B consistency rule does not apply to either: they compare
two functionals of one solve, not two extraction routes.

## 3. Path-dependence test: defined, supportable, not yet evaluated

The pre-declared test is in
`experiments/readout-voltage-functional/faraday_test_predeclaration.md`: for
each `x` across the pad edge, the closed loop runs through the +Y gap into the
pad, across the PEC pad, back through the −Y gap, and returns along the PEC
ground around the island etch; both PEC segments contribute exactly zero, and
the width average turns the enclosed flux into a weighted flux with unit
weight over the island etch ring, the island–pad gap and the corner regions,
and a triangular weight `(x₁ − x')/w` over the two gap strips. With Palace's
convention `∇ × E = −iωB`,

```
V₊ − V₋ = −iω [ ∫_{A_west} B_z dA + ∫_{strips} B_z (x₁ − x')/w dA ] .
```

**Supportability.** The boundary export registers `B_real`, `B_imag` as well
as `E` (`postoperator.cpp`), and the etched `z = 0` faces are present as
interface elements (attribute 25). The normal component `B_z` is continuous
across the interface for the discrete solution, so the side the export
evaluates does not matter. The mode frequency comes from the committed
`eig.csv`. If `B` should turn out to be absent from the archives, `∇ × E` per
element follows exactly from the linear vertex data. So the stored fields
should support a defensible test; **it was not evaluated because the
archives are not readable here**, and it is the one next test proposed in §5.

**What it would mean.** For the discrete Nédélec solution the identity is
exact, so agreement to the Float32 floor would show that the 5–7 mV surface
difference *is* the magnetic flux threading the enclosed gaps in this solve,
an inductive electromotive force, and that the export and integration are
faithful. It would not show that the flux, or either voltage, is converged,
nor that either surface is the right one. Disagreement would point at the
export, the integration or the conventions, not at physics.

**Pattern, not proof.** The committed `port-I.csv` gives a port current
magnitude 33 times larger in the fluxonium-like mode than in the readout-like
mode, and `ω|I|` 12.8 times larger (both records). An inductive term driven by
the island current would therefore be far larger in mode 1, which is where
the surface difference is 15 % rather than 0.15 %, while the absolute
differences are of one size. That is consistent with the Faraday
interpretation; it is not the test, and the diagnostic's own statement stands:
the mechanism is not attributed.

## 4. What is demonstrated about the +Y functional, and what is not

**Demonstrated (externally, on hash-verified archives).** The pre-declared +Y
functional is evaluable on the boundary export exactly as registered: the
integration recovers the declared 0.0024 mm² area, the F-port cross-check of
the same code path holds at 2e-6, the resulting `ρ_m` and `r₁₂` are complex
with imaginary parts at the 1e-12 to 1e-9 level (a real eigenmode, as
expected), in phase with the mirror surface, and stable to 1.64 % in `r₁₂`
between the two port-refinement meshes.

**Not demonstrated.** That the +Y functional is *the* node voltage of the
registered readout coordinate. In the fluxonium-like mode the pad-to-ground
voltage is path-dependent at 15 % of its own value across the two gaps of
the same pad, so at 1.5 GHz in this geometry "the pad voltage" is not a
single number to that precision. The synthetic mapping
`ρ_m = √(L_R/L_F) v_mR/v_mF` presumes a node voltage that is path-independent;
the registered definition fixes the coupling node but not the path. Until the
mechanism of the difference is established, `r₁₂(+Y)` is a well-defined
functional of the solve, not a verified measurement of the lumped
coordinate, and the two surfaces must not be averaged or exchanged to make it
one. Convergence of `V_R` in the readout gap is untested, since both records
discretise it identically; mode completeness and single-mode adequacy remain
as before; and nothing here bears on `g`.

> **Outcome and corrections (2026-09-20).** The test below was executed
> externally on the same archives (`experiments/readout-voltage-functional/external-faraday/`)
> with two corrections: the loop is clockwise from +z, so the sign is
> `+iω Φ_z`; and the flux must include the `P_F1` face (attribute 10) inside
> `A_west`, not attribute 25 alone as written here. With those, the Faraday
> prediction reproduces `V₊ − V₋` to 8.2e-7 … 1.1e-5 relative in all four
> cases: the surface difference is the magnetic-flux/path term of the stored
> discrete solution. The definition decision it forces is in
> [`r1-definition-decision.md`](r1-definition-decision.md).

## 5. One proposed next test, for approval, not executed

**Test.** Evaluate the pre-declared Faraday identity of §3 on the same two
archives, for modes 1 and 2 of N1R and N2R: compute the weighted flux of
`B_z` over the enclosed etched regions from the boundary export (attribute 25
faces), multiply by `−iω` with `ω` from the committed `eig.csv`, and compare,
complex part by part, with the reported `V₊ − V₋`.

**Purpose.** To decide whether the surface difference is the enclosed
magnetic flux of the discrete solution, in which case it is an inductive
electromotive force that a lumped model must place in an inductive branch,
not in the readout node's capacitive coordinate, and the mapping question
becomes one of model adequacy with a known term; or whether it is not, in
which case the export, integration or conventions are implicated before any
mapping question is asked.

**Controlled variables.** Same archives and hashes; same surfaces, width
weighting and directions; same phasor convention and units; same cycle-to-mode
mapping; both records and both modes; no new solve, no readout element, no
change to any functional; the −Y surface kept as the mirror, no averaging.

**Expected discriminating outcome.** Agreement to the Float32 floor
(order 1e-6 relative on the 5–7 mV difference) or not; nothing in between
is informative.

It can be run wherever the archives are readable; it cannot be run here
until they are supplied through an authorised mechanism. Stopping here for
approval.

Not done, by instruction: no g, guard relaxation, target redefinition,
Route B, N3, active readout element, physical redesign, PR #7 merge, audit,
framework or fan-out; the source archives and result records are untouched;
no archive was committed.
