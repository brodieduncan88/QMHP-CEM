# Does the Palace F-port observable support the spectral construction?

**Status:** offline compatibility check, **corrected 2026-09-20** after review
of 46bf8b5. No Palace run, no Route B, no Route A result, no coupling
evidence, no gate input. The draft amendment of
[`r1-definition-decision.md`](r1-definition-decision.md) remains **unapproved
and unapplied**. `invert_two_node` and its guards, the frozen Master values,
the 10 % Route-A/Route-B rule and every historical record are untouched.
Arithmetic and record: `experiments/fem-spectral-mapping/`.

> **Two claims made at 46bf8b5 are withdrawn here.**
> 1. *"`K_port ≠ f fᵀ/L` implies `N < 1`"* is **false**. A rank-2 (and a
>    rank-3) port term with `N = 1` exactly is exhibited in
>    `experiments/fem-spectral-mapping/review_checks_reconstructed.json`. The
>    actual equality condition is derived in §3. `N ≤ 1` is retained.
> 2. The *"`≲2.3e-7` readout-zero error"* from removing the assembled port
>    operator is **withdrawn**. A mode's diagonal participation in `ΔK` is the
>    first-order term only and does not bound the finite shift. That error is
>    now recorded as **UNBOUNDED BY THE CURRENT EVIDENCE**, which is not a
>    claim that it is large (§4).
>
> The reviewer's `QMHP_46bf8b5_review_checks.py` did not reach this
> environment. The three items were reconstructed from their descriptions and
> verified independently (`review_checks_reconstructed.py`); reconciliation
> with the supplied file is outstanding.

**Verdict: CONDITIONAL, and weaker than stated at 46bf8b5.** One premise is
established exactly. The normalisation is `≤ 1` with an equality condition
that is not evaluated. The operator-removal error is unbounded by the current
evidence. Mode identity is not met by these records.

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

the **full tangential field** over the port face. Palace reports, separately, a
rank-one functional of the same face: the width-averaged line voltage
`V_m = f·E_m` with `f = (1/(w·n_elem)) ∫_Γ (·)·l̂ dS`, and from it
`p_m = sign(Re I_m)·½L|I_m|²/(E_elec + E_cap)`, `I_m = V_m/(iω_m L)`;
`E_ind` uses the same rank-one `V`. `solvers/palace/port_diagnostic.py`
already records that distinction and derives the port energy independently
from the `surface-Q.csv` probes.

Throughout, `q := f/√L`, `Q := q qᵀ = f fᵀ/L`, and `ΔK := K_port − Q ⪰ 0`.

**Pseudoinverse convention.** `K` is positive semidefinite and singular: its
null space is the gradient fields whose tangential trace vanishes on `Γ`.
`f` annihilates that null space, so `f ∈ range(K)` and `f ᵀK⁺f` is
well-defined; equivalently the spectral sums below run over the modes with
`λ_m > 0`, which is what the records contain.

## 2. Q1 — why the magnitude of the saved EPR is a spectral weight

With `E_cap = 0` and `E_elec = ½EᵀME`, `p_m = (f·E_m)²/(λ_m L EᵀME)`. Take
`E_m` normalised as Palace does (`RescaleEigenvectors`, `EᵀME = 1`) and set
`φ_m := E_m/√λ_m`, which is K-orthonormal. Then

```
p_m = (f·φ_m)²/L = (g·v_m)² ,   g := K^{-1/2}f/√L ,   v_m := K^{1/2}φ_m
```

with `v_m` the orthonormal eigenvectors of `S := K^{1/2}M⁻¹K^{1/2}`.

> **`|p_m|` is exactly the spectral weight of the fixed vector `g` in mode
> `m`.** An identity, not an approximation. The reported sign is
> `sign(Re I_m)`, a phase convention of the complex eigenvector; the mixed
> signs in the two records confirm it carries no spectral information.

So `G_F(z) = Σ_m |p_m|/(z − λ_m)` is the exact scalar resolvent
`gᵀ(zI − S)⁻¹g`. The synthetic identity `p_mF = v_mF²` transfers in that
precise sense; the lumped circuit is the case `K = L⁻¹`, `M = C`, `f = e_F`,
where `g = e_F`. **What does not transfer automatically is which vector `g`
is**, and that is §3 and §4.

## 3. Q2 — the complete-mode normalisation

```
N := Σ_all m |p_m| = f ᵀK⁺f / L = qᵀK⁺q .
```

Let `u := K⁺q`, so `Ku = q` on the range and `N = qᵀu = uᵀKu`. Splitting
`K = K_curl + Q + ΔK` and using `uᵀQu = (qᵀu)² = N²`:

```
N − N²  =  uᵀ K_curl u  +  uᵀ ΔK u  ≥ 0 .
```

Both terms are non-negative, so **`N ≤ 1`**, and

> **`N = 1` exactly when `K_curl u = 0` and `ΔK u = 0`** — that is, when the
> static response to the port source is curl-free *and* its tangential trace
> on the port face is exactly the uniform mode along `l̂`.

The identity is verified to `3.1e-15` on 200 random pencils, and `N ≤ 1` held
on every draw (`review_checks_reconstructed.json`).

**Withdrawn.** The earlier implication *`K_port ≠ Q` ⟹ `N < 1`* does not
follow: `ΔK` can be non-zero and still annihilate `u`. Two explicit
counterexamples with `N = 1` are recorded, at `rank(K_port) = 2` and `3`. The
condition is about the **alignment of the static solution**, not about the
rank of the port operator.

**Consequence for the records.** Whether `N = 1` here is not decided by any
committed column: it needs `u = K⁺q`, the DC response, which no output
carries. Physically the island is galvanically isolated, so the only DC path
to ground is the inductor and `K_curl u = 0` is plausible; whether the DC
tangential profile across a 0.030 mm gap is exactly uniform is not known. So
`1 − N ≥ 0` is retained as an unmeasured quantity, not as a demonstrated
positive one.

## 4. Q3 — removing the assembled port operator

**What stands.** The committed records refute `K_port = Q`. For an exactly
solved eigenpair the Rayleigh identity gives
`E_mag + E_port = E_elec + E_cap`, so `domain-E.csv` alone yields the
participation of the **assembled** operator,
`p_assembled(m) = 1 − E_mag(m)/(E_elec + E_cap)`, and
`p_assembled − |p| = 1 − (E_mag + E_ind)/(E_elec + E_cap)`, the equipartition
defect. (It equals the independent probe-derived `p_port` of
`port_diagnostic.py`: 0.9982975 against the record's own 0.99829748 for N1R
mode 1.) If `K_port` were rank one these would be equal mode by mode:

| record | modes | max \|p_assembled − \|p\|\| | Σ p_assembled over saved modes |
|---|---|---|---|
| N1R | 6 | 0.99998 (mode 3) | 4.9991 |
| N2R | 9 | 0.99999 (mode 4) | 5.9991 |

Four of N1R's six and five of N2R's nine saved modes have
`E_mag/(E_elec+E_cap) ≈ 1e-5`: essentially all their energy in the port
surface term with a near-zero width-averaged voltage. They are
**port-operator-localised modes**, artefacts of representing the declared
lumped superinductor as a distributed sheet over a 0.020 × 0.040 mm face. A
rank-one port cannot produce them.

| record | field-resonant modes (GHz) | port-operator-localised modes (GHz) |
|---|---|---|
| N1R | 1.5158, 3.8871 | 7.233, 7.879, 8.633, 9.522 |
| N2R | 1.5260, 3.8874, 10.8415, 11.6094 | 10.214, 10.438, 10.998, 11.218, 11.778 |

Two consequences that need no threshold: **requesting more eigenpairs does
not close the deficit** (N2R computed three more modes, found two genuine
resonances above the 9.0 GHz ceiling worth `9.41e-5`, and `δ_saved` moved only
from `7.838e-4` to `7.454e-4`, the rest being artefacts worth `~1e-6`); and
**the declared equipartition check needs restating**, since measured with
`E_ind` every mode violates the eigen tolerance, the rule having been written
as if `E_ind` were the assembled port energy.

**Withdrawn: the `≲2.3e-7` error bound.** The claim was that removing
`ΔK ⪰ 0` shifts a mode by at most its diagonal participation
`E ᵀΔK E / E ᵀK E`. That is the **first-order** term only. Positive
semidefiniteness constrains the off-diagonals only through
`|ΔK_mn|² ≤ ΔK_mm ΔK_nn`, so a diagonal of `1e-8` still permits an
off-diagonal of `1e-4`, and against a finite gap the second-order term
`Σ_n |E_mᵀΔK E_n|²/(λ_m − λ_n)` can exceed the diagonal by orders. Verified
on constructed pencils: actual-shift-to-diagonal ratios of 11, 101 and 991
(`review_checks_reconstructed.json`).

Even the **sign** of the shift is not established. Monotonicity from the
min-max principle would need the difference of the two operators being
compared to be definite. §5 shows the construction removes `Q/N`, and
`K_port ⪰ Q/N` is strictly stronger than the Cauchy–Schwarz inequality
`K_port ⪰ Q` whenever `N < 1`; it is not established here.

> **Status of the operator-mapping error: UNBOUNDED BY THE CURRENT
> EVIDENCE.** This is not a demonstration that the error is large. A valid
> bound would need the off-diagonal couplings `‖(I − P_m) ΔK E_m‖` and the
> spectral gaps to the states `ΔK` connects to. `domain-E.csv` and
> `port-EPR.csv` carry only the diagonal, so no committed column supplies the
> required premise.

## 5. The exact rank-one removal identity, and which removal the zeros are

With `q = f/√L`, `Q = qqᵀ` and `N = qᵀK⁺q`, the matrix determinant lemma
gives `det(zM − K + Q)/det(zM − K) = 1 + qᵀ(zM − K)⁻¹q`, and the spectral sum
`qᵀ(zM − K)⁻¹q = Σ_m λ_m p_m/(z − λ_m) = z G_F(z) − N`. Hence

```
det(zM − K + Q) / det(zM − K)  =  z G_F(z) + 1 − N .
```

Verified to `3.9e-13` on 50 random pencils. Two readings follow:

- The eigenvalues of `(K − Q, M)` — the **declared** rank-one inductor
  removed — are the roots of `z G_F(z) + 1 − N = 0`.
- Replacing `Q` by `Q/N` gives `det(zM − K + Q/N)/det(zM − K) = z G_F(z)/N`,
  so the **zeros of `G_F` are the nonzero eigenvalues of `(K − Q/N, M)`**: the
  **normalised** rank-one removal, which is a *stiffer* rank-one term than the
  declared one, corresponding to an inductance `N·L` rather than `L`. Verified
  to `9.6e-14`.

They coincide only at `N = 1`. On the committed data, with `N` taken as the
saved sum, the two readout roots differ by `5.0e-7` to `5.3e-7` relative:

| record | variant | declared removal `(K−Q)` | normalised removal `(K−Q/N)` | relative difference |
|---|---|---|---|---|
| N1R | A (6 modes) | 15.097977993 | 15.097970136 | 5.204e-07 |
| N1R | B (2 modes) | 15.097978095 | 15.097970157 | 5.258e-07 |
| N2R | A (9 modes) | 15.099651244 | 15.099643672 | 5.015e-07 |
| N2R | B (4 modes) | 15.099651303 | 15.099643679 | 5.049e-07 |

(GHz². The declared-removal pencil is positive semidefinite on each
truncation, as `N ≤ 1` requires, and carries a low root at `1.74e-3` to
`1.82e-3 GHz²`, about 0.042 GHz: the island's floating mode, displaced from
zero by the truncation. Polynomial roots are cross-checked against the
explicit truncated pencils.)

**This is a difference between two rank-one removals only.** Neither is the
removal of the assembled `K_port`, and §4 says that difference is not bounded
by the committed evidence. The small diagonal participation differences of §4
do **not** establish their equivalence.

## 6. Missing participation, kept separate

```
δ_saved := 1 − Σ_m |p_mF| over the modes saved in the record
         = 7.837981e-04  (N1R, 6 modes)      7.454164e-04  (N2R, 9 modes)
```

It is **not** renamed `δ_far`. From §3,
`δ_saved = (1 − N) + Σ_unsaved |p|` with both terms non-negative.
**Neither has been measured separately**, and §3 withdraws the earlier
argument that the first is strictly positive. The four contributions the
campaign must keep apart:

| contribution | status here |
|---|---|
| normalisation/completeness deficit `1 − N` | non-negative, **unmeasured**; equality condition in §3 not evaluated |
| omitted high-frequency spectral weight | demonstrated to exist (N2R's 10.84 and 11.61 GHz modes, `9.41e-5`), size of the remainder unknown |
| discretisation sensitivity | observed N1R → N2R, §7; not an error bound |
| model-reduction uncertainty | untouched by this check |

The synthetic far-mode examples of
[`synthetic-three-mode-identifiability.md`](synthetic-three-mode-identifiability.md)
are **not** an unconditional bound and are not used as one.

## 7. CONDITIONAL SPECTRAL CALCULATION — EM MAPPING UNVERIFIED

Everything here is conditional on §2–§5 and on the mode identity of §8. It is
**not a Route A result, not VERIFIED-COMPUTATIONAL coupling evidence, and not
gate input.** The values below are **not promoted**. No previously quoted
value was used as a target and none is hard-coded; participations are never
renormalised; `N` is carried explicitly.

**Units.** Frequencies are read from `eig.csv` in GHz and used as
`w_m = f_m²` in GHz². `coupling_GHz(k, b, L_F)` takes **both** arguments in
(rad/s)², so every GHz² quantity is multiplied by
`W0 = (2π·10⁹)² = 3.947841760e+19`. The residue `c̃²` comes out in GHz⁴;
`c̃ = √(c̃²)` is in GHz² and is likewise multiplied by `W0`.
`L_F = 1.0345665367517793e-07 H`.

**Algebra.** With `N = Σ|p_m|`, `1/G = (1/N)(z − a/N − Σ̂(z))` and the
self-energy residue at a zero `β` is `N / Σ_m |p_m|/(β − w_m)²`; then
`f_R = √β` and `g = coupling_GHz(√residue · W0, β · W0, L_F)`.

**Inclusions and exclusions.** Variant A uses every saved mode (N1R 6, N2R 9;
N2R is **not** truncated to six). Variant B excludes the
port-operator-localised modes, each exclusion recorded with its equipartition
defect. That split uses an **ad-hoc post-hoc threshold** of `1e-2` on the
defect, chosen after seeing the values; it is not a declared or approved
criterion, and describing it at 46bf8b5 as "no threshold is invented" was
wrong. Nothing material rests on it: A and B differ by `2e-9` in `f_R` and
`6e-6` in `g`. Roots are rejected, not realified, if materially complex or
non-finite; on these data the imaginary parts are exactly zero.

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

**These spreads are not a total uncertainty.** The normalisation choice moves
`g` by `3.9e-4` (since `g ∝ √N`), and the observed N1R → N2R change is
`5.5e-5` in `f_R` and `6.7e-3` in `g` — two solved discretisations, not an
error bound and not continuum accuracy. Neither covers the unbounded
operator-mapping error of §4, the unmeasured `1 − N` of §3, or the
unestablished mode identity of §8. **The 111–112 MHz figures are conditional
arithmetic and are not Route A evidence.**

**Conditional far-mode sensitivity** (conditional on an interpretation of
`δ_saved` that §6 says is not established): placing the whole deficit at a
single frequency from 12 to 50 GHz shifts `f_R` by `≤3.1e-8`, `g` by
`≈4e-4`, and `a/N` by 4.5 % to 85 %.

**`E_C,F1F1`: UNAVAILABLE.** It is fixed by `a/N`, and `N` is unmeasured.
Across the eight variants `a/N` spans 2.3075 to 2.3533 GHz²; under the
far-mode placement it moves by up to 85 %. No value is reported.

## 8. Mode identity is not established by these records

The declared rule (`numerical-plan.md` §2) classifies a mode as readout-like
from **probe polarisation fractions** at three declared points plus
`p_mF < 0.5`. The solved configurations contain no
`Domains.Postprocessing.Probe` and the records contain no `probe-E.csv`, so
**the declared classification cannot be executed on N1R or N2R**. What exists:
`p_mF = 9.2e-4` / `9.4e-4` for mode 2 (necessary, not sufficient); the
external readout-field diagnostic's `V_R/V_F ≈ 3.73` for mode 2 against
`−3.8e-3` for mode 1 (field evidence, externally produced, and a
path-dependent functional); and a frequency inside the declared 3.7–5.0 GHz
window (consistency only, not a selector).

The residue-term dominance ratio is a **diagnostic, not proof**: `1.08e3`
(N1R) and `1.06e3` (N2R), reported as information. The 10.0 of
`solvers/palace/verification.py` is a cavity-height shift-to-uncertainty rule;
proposing it as a modal-ownership criterion was a new criterion presented as
an existing guard, and is withdrawn.

## 9. Corrections to the draft decision document

[`r1-definition-decision.md`](r1-definition-decision.md) stays unapproved. Its
correction block carries: the withdrawal of the 10.0 as an ownership guard;
the qualification that probe classification is not executable on these
records; the replacement of `Σ p_mF + δ_far = 1` by `N = f ᵀK⁺f/L ≤ 1` with
`δ_saved` an upper bound on omitted weight; and the statement that the zeros
remove a rank-one term rather than the assembled `K_port`. That last item is
further corrected here: the removal is the **normalised** `Q/N` (§5), and the
difference from the assembled removal is **unbounded by the current
evidence** (§4), not `≲2.3e-7`.

## 10. The smallest remaining evidence requirement

The blocking gap is now §4: nothing in the committed outputs bounds the
difference between the rank-one removal the construction performs and the
removal of the assembled port operator. The smallest evidence that would
settle it **measures the environment instead of bounding it**: one eigenmode
solve of the same discrete problem — same mesh, order, tolerances and band —
with the F1 lumped inductive port absent, whose spectrum *is* the F-open
environment. Comparing its readout mode with the zeros of §5 replaces the
unbounded quantity with a measured one, and would also expose the
port-operator-localised modes for what they are. It is a solve; it is named
here as the requirement and is **not proposed for approval, scheduled or
executed** in this task.

Two things that do **not** settle it:

- **Archived-field mode classification.** A surface-energy localisation
  diagnostic — for each saved mode, the fraction of exported boundary
  electric energy over the declared readout conductors
  (`R1.coupling_pad`, `R1.cpw`) against the F1 island, computed from the
  existing hash-verified archives with no solve — would add mode-identity
  evidence for §8. **It does not touch the operator mapping of §3–§5.** Its
  limitations must be stated wherever it is used: it is a *boundary* energy
  fraction over chosen conductor footprints, not the declared three-point
  probe polarisation; the footprints are a new choice; it is Float32; and for
  the N1R/N2R archives it can only cover the six exported modes. **It must
  not silently replace the declared probe classification**, which remains
  unexecuted, and it is supplementary evidence, not a substitute criterion.
- **More eigenpairs.** §4 shows most of the extra modes returned are
  port-operator-localised artefacts and that `δ_saved` barely moved.
