# SYNTHETIC: three-mode identifiability and the readout coordinate definition

**Status:** SYNTHETIC analysis record, offline. No Palace execution, no
extraction from N1R/N2R or any committed EM record, no coupling value from real
data. `invert_two_node()` and its guards are unchanged; nothing here enters the
production pipeline or an acceptance gate. The script, exact inputs,
environment and machine-readable results are in
`experiments/SYNTHETIC-three-mode-identifiability/` (its `README.md` says how to
re-run it). This note does **not** redefine the project's target; where the
registered definition admits two readings it says so and stops.

The question it answers: when the linear environment seen from the fluxonium
site has a third in-band mode, what do complete fluxonium-site eigenmode data
identify, does that match the registered target, and if not, what one
additional observable would?

## 1. Anchoring the target

From [`coupling-definition.md`](coupling-definition.md):

- The target for S1 is the gauge-invariant triple of the **declared circuit**
  `{F1, R1}`: `{E_C,F1F1, f_R1, g_F1R1}` (§3). `C` is the Maxwell matrix of the
  linear environment **Kron-reduced to the declared nodes** (§2).
- `R1` is "the single-mode (fundamental) representation of a distributed
  resonator **at its coupling node**" (§2). Its node flux has no scale (a gauge,
  `route-a-identifiability.md`), but its *direction* in the space of
  environment coordinates is fixed by that sentence: it is the coupling-node
  flux of the resonator's fundamental.
- `g_F1R1 = 8 E_C,F1R1 n_zpf,R1` with `E_C = (e²/2) C⁻¹`, and
  `f_R1 = √(8 E_C,R1R1 E_L,R1) = √((C⁻¹)_R1R1 / L_R1)` (§3, §10). The `n(a+a†)`
  convention names `a` as the ladder operator of that single readout
  oscillator.

**Synthetic correspondence.** The study writes the circuit as
`S = L^{-1/2} C^{-1} L^{-1/2}` in node order `(F, R, X)`, units GHz², with
`L = diag(L_F, L_R, L_X)`, `L_F = 103.457 nH` declared and held fixed, and
`L_R`, `L_X` gauge scales. Modes satisfy `S v_m = f_m² v_m` with orthonormal
`v_m`; the fluxonium-inductor participation is `p_mF = v_mF²`. Applying the
registered algebra to the node `R` gives the **node-basis targets**
`E_C ← S_FF`, `f_R = √S_RR`, `g ← |S_FR|, S_RR` (the module's own
`charging_energy_GHz` and `coupling_GHz`). The synthetic `R` corresponds to the
registered `R1` exactly when it is the coupling-node coordinate of the
resonator's fundamental. `X` is one additional resonant environment mode with
no lumped branch; a resonant conductor cannot be Kron-reduced into a static
`C`, so a three-mode environment is outside the declared two-node circuit by
construction, and how the definition extends to it is the question.

Three different things must be kept apart:

| coordinate | definition | fixed by |
|---|---|---|
| **physically anchored readout coordinate** | node `R1`: the coupling-node flux of the isolated resonator's fundamental | the layout (a specific conductor and reference plane) |
| **normal mode of the linear environment** | an eigenvector of `B`, the `R/X` block of `S`: the environment with the fluxonium inductor removed and the `F` node floating (`q_F = 0`) | the environment's own dynamics; coincides with the anchored coordinate **iff** `S_RX = 0` |
| **arbitrary rotation of the R/X basis** | `Q = diag(1, O)`, `O ∈ O(2)` | a coordinate choice with no physical content |

The registered text anchors `R1` to the first of these.

## 2. The ambiguity, analytically

Write `S = [[a, cᵀ], [c, B]]` and rotate the `R/X` block: `S' = Q S Qᵀ`,
`Q = diag(1, O)`. Then

- **eigenvalues** are invariant (`Q` is orthogonal, `S'` is similar to `S`);
- **eigenvectors** transform as `v' = Q v`, whose `F` component is unchanged,
  so every **F-site participation `p_mF = v_mF²` is invariant**;
- `a = S_FF` is invariant, so **`E_C,FF` is invariant**;
- `c' = O c`, `B' = O B Oᵀ`: the **node-basis `f_R = √B_RR` and
  `g ∝ |c_R|` change** with `O`.

The complete `O(2)` invariants of the pair `(c, B)` are the two eigenvalues
`β₁, β₂` of `B` and the magnitudes `|c̃_k|` of the components of `c` on `B`'s
eigenvectors: four numbers, five with `a`. `S` has six entries, so the orbit is
one-dimensional, and the five independent F-site observables
`(f₁, f₂, f₃, p₁F, p₂F)` (`p₃F` follows from completeness) are functions of
the five invariants only. Numerically (721 angles on `[−π/2, π/2]`, reference
circuit B): frequencies invariant to `1.4e-15`, participations to `7e-18`,
`E_C` exactly; `f_R` runs over 3.89–8.01 GHz and `g` over 0.36–359 MHz.

**Permitted constraints, beyond positive definiteness.** `coupling-definition.md`
§2/§10 require `C` to be a Maxwell matrix: positive diagonal, non-positive
off-diagonal mutuals. A positive-definite matrix with non-positive
off-diagonals is a Stieltjes matrix, whose inverse is entrywise non-negative.
Hence, in the node basis, `S` must have **non-negative off-diagonals** and
`S⁻¹ ∝ L^{1/2} C L^{1/2}` must have **non-positive off-diagonals**. (Diagonal
dominance of `C`, i.e. positive capacitance to ground, can always be met by
choosing the `R` and `X` flux scales, so it does not restrict the orbit.)
A rotation never violates positive definiteness (0 of 721 angles), but the sign
constraints cut the orbit to an interval: for reference B, 202 of 721 angles,
`θ ∈ [−0.842, +0.035]` rad, within which `f_R ∈ [3.890, 6.660]` GHz and
`g ∈ [99.6, 341.8]` MHz.

Two consequences:

1. **`S_RX = 0` is not an admissible layout fact** in the declared framework
   when `F` couples capacitively to both `R` and `X`: an irreducible Stieltjes
   `C` has a strictly positive inverse, so `(C⁻¹)_RX > 0`. The reference
   circuit with `k_RX = 0` used in the earlier reduced-model study has
   `(S⁻¹)_RX = +3.4e-4 > 0`, i.e. a positive mutual capacitance, and is
   inadmissible. (Its conclusions about the two-mode reduction do not rest on
   admissibility, but the point stands and the instruction not to impose
   `k_RX = 0` is confirmed from the constraints themselves.)
2. **The previously reported one-parameter family is the rotation orbit, and
   it consists of physically distinct admissible circuits — both.** Re-solving
   the family (all five F-site observables matched, `k_RX ∈ {0.5, …, 8}`), its
   rotation invariants are constant to `1.4e-13`, each member equals
   `Q(θ) S₀ Q(θ)ᵀ` to `≤ 5e-8` with `θ` from −0.010 to −0.167 rad, and every
   member with `k_RX > 0` satisfies the Maxwell sign constraints. So they are
   at once alternative coordinate descriptions of one dynamical system and
   distinct legitimate node-basis circuits; the F-site data cannot tell them
   apart, and their node-basis `g` runs from 121.9 to 193.8 MHz.

## 3. What complete F-site data identify

With `G_F(z) = [(zI − S)⁻¹]_FF = Σ_m p_mF / (z − f_m²)` and the Schur
complement,

```
1/G_F(z) = z − a − cᵀ (zI − B)⁻¹ c = z − a − Σ_k c̃_k² / (z − β_k) .
```

So the complete three-mode F-site data identify, in the **environment
normal-mode basis**:

| quantity | from the data | meaning |
|---|---|---|
| `a` | `Σ_m p_mF f_m²` (large-`z` limit) | `S_FF` → `E_C,FF` |
| `β_k` | the two **zeros** of `G_F` (they interlace the three poles) | eigenvalues of `B`: squared frequencies of the environment with the fluxonium inductor removed and the `F` node floating; the poles of `Z_FF` at the fluxonium site |
| `c̃_k²` | `1 / Σ_m p_mF /(β_k − f_m²)²` (residues of `z − a − 1/G_F`) | squared coupling of `F` to environment normal mode `k` |

On exact synthetic data (references A and B) `a` is recovered to `2e-16`,
`β_k` to `1e-15` and `c̃_k²` to `1e-12`. Limitations, measured:

- **Dark mode** (`c̃_X → 0`, i.e. `p₃F → 0`): the `X` residue degrades
  (relative error `1e-12` at `p₃F = 8e-4`, `3.7e-10` at `1e-6`, `2.2e-7` at
  `1e-9`, `1.3e-5` at `1e-12`, not identifiable at 0 by pole–zero
  cancellation); the bright readout pair `(β_R, c̃_R)` is unaffected
  (`1e-13`).
- **Degeneracy** (`β₁ → β₂`): the individual residues lose accuracy (median
  relative error `5e-12 → 3.2e-8` as the gap goes from 48.8 to 0.005 GHz²
  under `1e-12` input noise) while their sum stays identified (`2e-9`).
- Only `|c̃_k|` is identified, never its sign; `|g|` is what is reported, so
  this costs nothing.
- **Sensitivity** (95th percentile, 2000 draws, noise on the smaller of `p`
  and `1 − p` as in `route-a-identifiability.md` §6, no renormalisation of the
  participations): the error on the normal-mode `g` is `1.0e-3` at
  `σ_p = 1e-3` and `9.7e-3` at `σ_p = 1e-2`, one-for-one with the
  participation and insensitive to `σ_f`; `f_R` tracks `2σ_f`; `E_C` is
  `4.8e-5` at `σ_p = 1e-3`, set by `p₃F f₃²`, four orders better than the
  two-mode reduction's `1.2e-2` to `2.0e-1`.

**Do these match the registered target?** They are the registered triple
**if and only if the readout coordinate is an environment normal mode**
(`S_RX = 0`, which §2 above shows is not admissible when `F` couples to both).
For reference A (`k_RX = 0`) the normal-mode and node-basis triples agree to
`1e-12`; for reference B (`k_RX = 2` GHz², mixing angle 0.041 rad) they differ
by `2.7e-3` in `f_R` and by **17.3 % in `g`** (96.61 vs 116.79 MHz): the
readout normal mode carries a 4 % amplitude of `X`, and `F` couples to `X`
four times more strongly than to `R`, so a small mixing moves `g` a lot. That
is larger than the 10 % consistency rule. The normal-mode quantities are
exactly the Nigg/BBQ `Z_FF` pole and residue that
[`extraction-routes.md`](extraction-routes.md) §3.3 names as Route B's output
(the same paragraph also calls them "the pole of `Y_FF`", which is the
`F`-shorted resonance and a different number; not resolved here). They are
**not adopted** as a replacement target by this note.

## 4. One extra non-loading readout-side observable

Defined: `ρ_m = V_mR / V_mF`, the ratio, in eigenmode `m`, of the line
voltage across the readout resonator's coupling-node gap to the voltage across
the fluxonium port. Both are line integrals of the same eigenmode field; no
element is added. In the pinned Palace tree an `"Active": false` lumped port
at the readout coupling node provides exactly this: `UpdatePorts` and
`PostprocessPorts` compute and write `V_m` for every port including inactive
ones, while `AddStiffnessBdrCoefficients`, `AddDampingBdrCoefficients` and
`AddMassBdrCoefficients` skip inactive ports (`lumpedportoperator.cpp`
L571–621), so the port's nominal `R/L/C` (one must be declared) is never
applied. Not a physical readout inductor, not a second EPR.

In the lumped model `V_m ∝ f_m² L^{1/2} v_m`, so
`ρ_m = √(L_R/L_F) · v_mR / v_mF`. The scale is the readout gauge, so the datum
is the **cross-mode ratio** `r₁₂ = ρ₁/ρ₂` (gauge-free; its sign is also
immaterial, since `θ → θ + π` flips every `ρ_m`). With
`v(θ) = Q(θ) v_rep`, `r₁₂(θ) = r_obs` is linear in `(cos θ, sin θ)`: **unique
`tan θ`**.

Results (reference B, exact data, six equations in the six node-basis entries):

- closed form: `r₁₂` gives `θ` uniquely mod π on each `O(2)` component; the
  reflection component and `θ + π` reproduce the same `(g, f_R)`; **8
  candidates, 1 distinct target**, `g` to `2e-12`; `r₁₃` gives the same `θ`
  (`|sin Δθ| = 6e-13`);
- random-start solve of the raw 6×6 system: 336 of 400 starts converge, **1
  distinct target** (spread `1e-12`); the same 5-equation system without
  `r₁₂`: 349 converge, **349 distinct targets**, `g` from 0.03 to 355 MHz.

Six equations did not *imply* the unique solution; it was checked. The
discrete alternatives that remain (sign flips, the reflection) are gauges of
the target.

**Sensitivity** (95th percentile, 2000 draws; `σ_r` relative on `r₁₂`):

| `σ_f` | `σ_p` | `σ_r` | `E_C` | `f_R` | `g` |
|---|---|---|---|---|---|
| 1e-6 | 1e-3 | 1e-4 | 4.5e-5 | 2.5e-4 | **7.2e-3** |
| 1e-6 | 1e-3 | 1e-3 | 4.5e-5 | 3.6e-4 | 1.1e-2 |
| 1e-6 | 1e-3 | 1e-2 | 4.6e-5 | 2.4e-3 | 7.6e-2 |
| 1e-4 | 1e-2 | 1e-3 | 6.2e-4 | 2.6e-3 | 6.9e-2 |
| 1e-4 | 1e-2 | 1e-2 | 5.9e-4 | 3.8e-3 | 1.0e-1 |

Local amplification `d ln g / d ln r₁₂ = 4.0`. The dominant term is not the
ratio's own error but the participations': the mixing angle (0.041 rad) is
recovered from a near-cancellation (`v_1R − r v_1F/v_2F ≈ 1.1e-3` against
`2.6e-2`), which amplifies `σ_p` about seven-fold into the node-basis `g`,
against one-for-one for the normal-mode `g` of §3.

## 5. Conclusion

**A specific ambiguity remains, in the definition rather than in the data.**
The registered text anchors `R1` to the resonator's coupling node. With a
third in-band environment mode:

- under that **node-basis reading**, the registered `g_F1R1` is **not
  identifiable from fluxonium-site data of any number of eigenpairs**: the
  data fix the circuit only up to the `R/X` rotation, whose admissible arc
  spans `g` from 99.6 to 341.8 MHz here. It **becomes identifiable with one
  specified additional observable**, the cross-mode voltage ratio `r₁₂` from
  an inactive readout-side port, uniquely and with no discrete alternative,
  at about seven times the participation error;
- under the **normal-mode reading** (the `Z_FF` pole and residue that
  `extraction-routes.md` §3.3 already names for Route B), the target **is
  identifiable from complete three-mode F-site data alone**, with `g` error
  one-for-one with the participation error and `E_C` four orders better than
  the two-mode reduction;
- the two readings differ by 17 % in `g` on the synthetic circuit, above the
  10 % consistency rule, and coincide only when `S_RX = 0`, which the Maxwell
  constraints exclude.

**Minimum next step:** a definition decision, with approval, not a solve —
whether `g_F1R1` in a non-Kron-reducible environment is the coupling to the
anchored coupling-node coordinate or to the environment normal mode. Only then
is it known whether the next datum is a third eigenpair's participation
(normal-mode reading) or `r₁₂` (node-basis reading).

**Can the existing saved outputs supply `r₁₂`?** No. N1R and N2R saved
`eig.csv`, `port-EPR.csv`, `port-V.csv`, `port-I.csv`, `domain-E.csv`,
`error-indicators.csv` and `surface-Q.csv`; the only port is the fluxonium
port, the configs declare no field probes (`Domains.Postprocessing` absent)
and no field output (`Problem.Output = "postpro"`, no ParaView data), so no
readout-side voltage can be post-processed from them. Obtaining `r₁₂` would
need an eigenmode solve with an additional inactive port surface, which is not
proposed and not approved here.

Not done, by instruction: no Palace run, no Route B, no N3, no real-data `g`,
no change to `invert_two_node()` or any guard, threshold or budget, no
physical redesign, no merge of PR #7.
