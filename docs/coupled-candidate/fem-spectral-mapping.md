# Does the Palace F-port observable support the spectral construction?

**Status:** offline compatibility check. No Palace run, no Route B, no Route A
result, no coupling evidence, no gate input. It answers one question about the
extraction proposed in [`r1-definition-decision.md`](r1-definition-decision.md),
whose draft amendment remains **unapproved and unapplied**. `invert_two_node`
and its guards, the frozen Master values, the 10 % Route-A/Route-B rule and
every historical record are untouched. Arithmetic and record:
`experiments/fem-spectral-mapping/`.

**Verdict: CONDITIONAL.** One premise is established exactly, one is refuted
as stated and replaced by a bounded correction, and one is refuted outright
with the correction bounded only for the readout zero. A fourth requirement,
physical mode identity, is not met by these records at all.

## 1. Notation and the actual operators

Palace's eigenmode solve is the real symmetric pencil

```
K E_m = λ_m M E_m ,   λ_m = ω_m² ,   K = K_curl + K_port ,   M = ∫ ε (·)·(·)
```

with `K_curl = ∫ μ⁻¹ (∇×·)·(∇×·)`. The inductive port enters the **stiffness**
as a boundary mass term (`lumpedportoperator.cpp` `AddStiffnessBdrCoefficients`,
coefficient `1/L_s`; `spaceoperator.cpp` puts it in `K`):

```
K_port(E,E) = ∫_Γ (1/L_s) |E_t|² dS ,   L_s = L · (w/l) · n_elem
```

the **full tangential field** over the port face. Palace reports, separately,
a rank-one functional of the same face: the width-averaged line voltage
`V_m = f·E_m` with `f = (1/(w·n_elem)) ∫_Γ (·)·l̂ dS`
(`InitializeLinearForms`), and from it

```
p_m = sign(Re I_m) · ½ L |I_m|² / (E_elec + E_cap) ,   I_m = V_m/(iω_m L)
E_ind = Σ_j ½ L_j |I_j|²            (GetLumpedInductorEnergy — the same rank-one V)
```

These are two different objects on the same surface. `solvers/palace/port_diagnostic.py`
already records that distinction and derives the port energy independently from
the `surface-Q.csv` probes; this note uses it.

## 2. Q1 — why the magnitude of the saved EPR is a spectral weight

With `E_cap = 0` (no lumped capacitors in this model) and `E_elec = ½ EᵀME`,

```
p_m = |V_m|²/(2ω_m² L) / (½ EᵀME) = (f·E_m)² / (λ_m L EᵀME) .
```

Take `E_m` normalised as Palace does (`RescaleEigenvectors`, unit electric
energy, `EᵀME = 1`) and set `φ_m := E_m/√λ_m`. Then `φ_mᵀKφ_n = δ_mn`: the
`φ` are **K-orthonormal**, and

```
p_m = (f·φ_m)²/L = (g·v_m)² ,    g := K^{-1/2} f/√L ,    v_m := K^{1/2}φ_m
```

where the `v_m` are the orthonormal eigenvectors of the symmetric operator
`S := K^{1/2} M^{-1} K^{1/2}`, whose eigenvalues are the `λ_m`. So

> **`|p_m|` is exactly the spectral weight of the fixed vector `g` in the mode
> `m`.** This is an identity, not an approximation. The reported sign is
> `sign(Re I_m)`, a phase convention of the complex eigenvector, and carries no
> spectral information; the mixed signs in the two records (`−,−,…` in N1R,
> `−,+,…` in N2R) confirm it.

`G_F(z) = Σ_m |p_m|/(z − λ_m)` is therefore the exact scalar resolvent
`gᵀ(zI − S)⁻¹g` of a well-defined vector. The synthetic identity
`p_mF = v_mF²` transfers in this precise sense: the lumped circuit is the case
`K = L⁻¹`, `M = C`, `f = e_F`, where `g = e_F` exactly. **What does not
transfer automatically is which vector `g` is**, and that is Q2 and Q3.

## 3. Q2 — the complete-mode normalisation, and why it is not 1

From §2, over **all** modes of the discrete problem,

```
Σ_m |p_m| = ‖g‖² = fᵀK⁻¹f / L .
```

By Cauchy–Schwarz on the port face, for any field,

```
(f·E)²/L = (1/(w²L))(∫_Γ E·l̂)² ≤ (l/(wL)) ∫_Γ |E·l̂|² ≤ (1/L_s)∫_Γ |E_t|² = K_port(E,E)
```

using Palace's own `L_s = L w/l`. Hence `K_port ⪰ f fᵀ/L` and
`K ⪰ K_curl + f fᵀ/L`, so

```
Σ_all |p_m| = fᵀK⁻¹f/L  ≤  1 ,   with equality only if K_port = f fᵀ/L exactly.
```

The value 1 is reached in the idealisation where (i) the port term is the
rank-one circuit term and (ii) the port inductor is the only DC path from the
island to ground, so that `f ∉ range(K_curl)` and the static response is
inductor-limited. Condition (ii) does hold here: the F1 island is galvanically
isolated by its etched gap. Condition (i) is **false** (§4). So:

> **The correct complete-mode normalisation is `fᵀK⁻¹f/L`, a number strictly
> below 1 that no committed column measures.** `Σ_m p_mF = 1` is an
> approximation whose defect is the port field's non-uniformity, not an
> identity, and the two-mode sum rule enforced by `invert_two_node` inherits
> that status for the FEM model (its status for an exact lumped circuit is
> unchanged).

## 4. Q3 — the construction's environment is not the port operator removed

The zeros of `gᵀ(zI−S)⁻¹g` are the eigenvalues of `S` compressed to `g⊥`:
**one** direction is freed. Removing the actual `K_port` frees
`rank(K_port)` directions, one per tangential degree of freedom on the port
face. The two coincide only if `K_port` is rank one.

**The committed records refute that, and quantify it.** For an exactly solved
eigenpair the Rayleigh identity `EᵀKE = λEᵀME` splits as
`E_mag + E_port = E_elec + E_cap`, so the participation of the **assembled**
port operator is available from `domain-E.csv` alone:

```
p_assembled(m) = 1 − E_mag(m)/(E_elec + E_cap) ,
p_assembled(m) − |p_m| = 1 − (E_mag + E_ind)/(E_elec + E_cap) = the equipartition defect.
```

(That quantity equals the independent probe-derived `p_port` of
`port_diagnostic.py`: for N1R mode 1 it gives 0.9982975 against the record's
own `port_participation_from_probes` 0.99829748.) If the assembled term were
`f fᵀ/L`, then `p_assembled = |p|` for every mode. Observed:

| record | modes | max \|p_assembled − \|p\|\| | Σ p_assembled over saved modes |
|---|---|---|---|
| N1R | 6 | 0.99998 (mode 3) | 4.9991 |
| N2R | 9 | 0.99999 (mode 4) | 5.9991 |

The mechanism is visible mode by mode. Four of N1R's six saved modes and five
of N2R's nine have `E_mag/(E_elec+E_cap) ≈ 1e-5`: essentially all of their
energy sits in the port surface term, with a width-averaged voltage near zero.
They are **port-operator-localised modes** — artefacts of representing the
declared lumped superinductor as a distributed sheet inductance over a
0.020 × 0.040 mm face. A rank-one port cannot produce them.

| record | field-resonant modes (GHz) | port-operator-localised modes (GHz) |
|---|---|---|
| N1R | 1.5158, 3.8871 | 7.233, 7.879, 8.633, 9.522 |
| N2R | 1.5260, 3.8874, 10.8415, 11.6094 | 10.214, 10.438, 10.998, 11.218, 11.778 |

The split is read off a seven-order-of-magnitude gap in the defect
(`1e-7 … 6e-5` against `≈1.0`); no threshold is proposed. Two consequences
follow that are independent of any threshold:

- **Requesting more eigenpairs does not close the deficit.** N2R computed
  three more modes than N1R and found two genuine resonances above the
  declared 9.0 GHz ceiling (10.84, 11.61 GHz) worth `9.41e-5` of weight, yet
  `δ_saved` moved only from `7.838e-4` to `7.454e-4`. Most of the extra modes
  returned were artefacts carrying `~1e-6` in total.
- **The declared equipartition check needs restating.** `extraction-routes.md`
  §2.2 says a mode violating equipartition "beyond the eigen tolerance"
  (1e-6) is flagged and not used. Measured with `E_ind`, *every* mode violates
  it, including the two physical ones (`1.1e-5`, `2.3e-7`). The rule was
  written as if `E_ind` were the assembled port energy; it is the rank-one
  surrogate, so the residual it measures is the non-uniformity, not a solve
  failure.

**How large is the Q3 error on the quantity of interest?** Removing the extra
positive-semidefinite part `ΔK = K_port − f fᵀ/L` can only lower eigenvalues,
and the relative lowering of a mode is bounded by the fraction of its energy
in that sector, which is exactly `p_assembled − |p|`. For the readout-like
mode that fraction is `2.26e-7` (N1R) and `1.11e-7` (N2R). So the difference
between "compress to `g⊥`" and "remove the assembled port operator" perturbs
the readout zero by `≲2.3e-7` relative in `ω²`, i.e. `≲1.2e-7` in frequency,
up to the hybridisation correction of order `1e-3` that relates the coupled
eigenvector to the environment eigenvector. **This is a demonstrated
approximation with a data-grounded bound, not an identity.** The same
argument gives no bound on the normalisation of §3, which is a global
quantity three orders larger.

## 5. Missing participation, kept separate

```
δ_saved := 1 − Σ_m |p_mF|  over the modes saved in the record
         = 7.837981e-04  (N1R, 6 modes)      7.454164e-04  (N2R, 9 modes)
```

It is **not** renamed `δ_far`. From §3, `δ_saved = [1 − fᵀK⁻¹f/L] + Σ_unsaved |p|`
with both terms non-negative and the first strictly positive, so `δ_saved` is
an **upper bound** on omitted spectral weight and is strictly larger than it.
The four contributions the campaign must keep apart:

| contribution | status here |
|---|---|
| normalisation/completeness deficit `1 − fᵀK⁻¹f/L` | strictly positive, **unmeasured**; no committed column carries it |
| omitted high-frequency spectral weight | demonstrated to exist (N2R's 10.84 and 11.61 GHz modes, `9.41e-5`) but far from accounting for `δ_saved` |
| discretisation sensitivity | observed N1R → N2R, §6; not an error bound |
| model-reduction uncertainty | untouched by this check |

The synthetic far-mode examples of
[`synthetic-three-mode-identifiability.md`](synthetic-three-mode-identifiability.md)
are **not** an unconditional bound and are not used as one.

## 6. CONDITIONAL SPECTRAL CALCULATION — EM MAPPING UNVERIFIED

Everything in this section is conditional on the mapping of §2–§4 and on the
mode identity of §7, neither of which is established. It is **not a Route A
result, not VERIFIED-COMPUTATIONAL coupling evidence, and not gate input.** No
previously quoted value was used as a target and none is hard-coded;
participations are never renormalised, and where the algebra needs the total
weight `N` it is carried explicitly.

**Units.** Mode frequencies are read from `eig.csv` in GHz and used as
`w_m = f_m²` in GHz². `coupling_GHz(k, b, L_F)` of `models/route_a_inversion.py`
takes **both** `k` and `b` in (rad/s)², so every GHz² quantity is multiplied by
`W0 = (2π·10⁹)² = 3.947841760e+19` before it is passed. The self-energy
residue `c̃²` comes out in GHz⁴; `c̃ = √(c̃²)` is in GHz² and is multiplied by
`W0`. `L_F = 1.0345665367517793e-07 H` is the declared superinductor.

**Algebra, carrying `N`.** With `G(z) = Σ_m |p_m|/(z − w_m)` and `N = Σ_m |p_m|`,
`1/G = (1/N)(z − a/N − Σ̂(z))` with `a = Σ_m |p_m| w_m`, so the self-energy
residue at a zero `β` is `N / Σ_m |p_m|/(β − w_m)²`. Then
`f_R = √β` and `g = coupling_GHz(√residue · W0, β · W0, L_F)`.

**Inclusions and exclusions.** Variant A uses every saved mode (N1R 6, N2R 9).
Variant B excludes the port-operator-localised modes of §4, each exclusion
recorded with its equipartition defect in
`experiments/fem-spectral-mapping/spectral_compatibility.json`. N2R is **not**
truncated to six. Two normalisations are reported: `N = Σ|p|` (self-consistent
truncation) and `N = 1` (the sum rule assumed).

| record | variant | `N` | `f_R` (GHz) | `g` (MHz) |
|---|---|---|---|---|
| N1R | A, 6 modes | Σ\|p\| | 3.885610652 | 111.017713 |
| N1R | A, 6 modes | 1 | 3.885610652 | 111.061246 |
| N1R | B, 2 modes | Σ\|p\| | 3.885610654 | 111.017069 |
| N1R | B, 2 modes | 1 | 3.885610654 | 111.061051 |
| N2R | A, 9 modes | Σ\|p\| | 3.885825996 | 111.757217 |
| N2R | A, 9 modes | 1 | 3.885825996 | 111.798894 |
| N2R | B, 4 modes | Σ\|p\| | 3.885825997 | 111.756868 |
| N2R | B, 4 modes | 1 | 3.885825997 | 111.798827 |

Spreads within one record: including or excluding the port-localised modes
moves `f_R` by `2e-9` and `g` by `6e-6` relative; the normalisation choice
moves `g` by `3.9e-4` and `f_R` not at all. Since `g ∝ √N` and
`Σ_saved|p| ≤ N < 1`, the normalisation contributes at most `3.9e-4` to `g`
however §3 is resolved — but it is not bounded for `a`.

**Observed refinement sensitivity, N1R → N2R** (two solved discretisations;
not an error bound, not a convergence statement, not continuum accuracy):
`f_R` `5.54e-5`, `g` `6.66e-3` relative. This is an order of magnitude larger
than every completeness effect above.

**Conditional far-mode sensitivity** (conditional on an interpretation of
`δ_saved` that §5 says is not established): placing the whole deficit at a
single frequency from 12 to 50 GHz shifts `f_R` by `≤3.1e-8` and `g` by
`≈4e-4`, and shifts `a/N` by 4.5 % to 85 %.

**`E_C,F1F1`: UNAVAILABLE.** It is fixed by `a/N`, and `N` is the unmeasured
normalisation of §3. Across the eight variants `a/N` spans 2.3075 to
2.3533 GHz²; under the far-mode placement it moves by up to 85 %. No value is
reported.

## 7. Mode identity is not established by these records

The declared rule (`numerical-plan.md` §2) classifies a mode as readout-like
from **probe polarisation fractions** at three declared points plus
`p_mF < 0.5`. The solved configurations contain no
`Domains.Postprocessing.Probe` block and the records contain no `probe-E.csv`,
so **the declared classification cannot be executed on N1R or N2R**. What
exists:

- `p_mF = 9.2e-4` (N1R) and `9.4e-4` (N2R) for mode 2: necessary, not sufficient.
- The external readout-field diagnostic gives `V_R/V_F ≈ 3.73` for mode 2
  against `−3.8e-3` for mode 1, i.e. mode 2's voltage is concentrated at the
  readout pad. This is field evidence, but it is externally produced and it is
  a path-dependent functional (0.15 % path dependence for mode 2, 15 % for
  mode 1).
- The frequency 3.887 GHz lies inside the declared readout window 3.7–5.0 GHz.
  Consistency only; frequency is not a selector.

The evidence is consistent with mode 2 being the readout fundamental and does
not establish it under the declared rule. **The residue-term dominance ratio
is a diagnostic, not proof**: the readout zero's largest residue term exceeds
the next by `1.08e3` (N1R) and `1.06e3` (N2R), which is reported as
information only. The 10.0 of `solvers/palace/verification.py` is a
cavity-height shift-to-uncertainty rule; proposing it as a modal-ownership
criterion, as the draft decision document did, was a new criterion presented as
an existing guard, and is withdrawn in §8.

## 8. Smallest necessary correction to the draft decision document

[`r1-definition-decision.md`](r1-definition-decision.md) is a draft and stays
unapproved. Four corrections, entered there as a correction block rather than
by rewriting it:

1. **§5 item 2** — withdraw the reuse of the 10.0 from `verification.py` as an
   ownership guard. The dominance ratio is a diagnostic; any ownership
   criterion is new and needs its own justification and pre-declaration.
2. **§5 item 1 and §9** — the declared probe classification is not executable
   on these records (no `probe-E.csv`), so readout identification is not
   established from the record's own evidence.
3. **§7 "Completeness"** — replace `Σ_m p_mF + δ_far = 1` by the derived
   statement of §3: `Σ_all |p_mF| = fᵀK⁻¹f/L < 1`, with `δ_saved` an upper
   bound on omitted spectral weight, not equal to it.
4. **§3 and §7** — the zeros of `G_F` correspond to removing the rank-one
   surrogate `f fᵀ/L`, not the assembled `K_port`; the difference is bounded
   at `≲2.3e-7` for the readout zero by §4 and is unbounded for `a`.

## 9. One minimum next action

**Classify the saved modes from field energy, offline, on the archives that
already exist.** For each saved mode of N1R and N2R, compute from the exported
boundary fields the fraction of electric energy over the declared readout
structures (`R1.coupling_pad` and `R1.cpw`) against the F1 island, and report
it as the substitute for the missing `probe-E.csv`.

*Purpose:* to settle mode identity — the one requirement that blocks every
conditional number of §6 regardless of how §3 and §4 are resolved.
*Controlled variables:* the same two hash-verified archives, the registered
conductor rectangles, the same cycle-to-mode mapping, both records, all saved
modes; no solve, no new configuration, no change to any functional or
threshold. *Why this and not more modes:* §4 shows that requesting further
eigenpairs mostly returns port-operator-localised artefacts and does not close
`δ_saved`. *What it does not do:* it does not measure `fᵀK⁻¹f/L`, so
`E_C,F1F1` stays unavailable, and it is not authority to extract `g`.

It requires no Palace run. It is proposed, not executed.
