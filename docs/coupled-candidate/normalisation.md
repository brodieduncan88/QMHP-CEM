# Measuring `N`: what the records already pin, and why it does not unblock `E_C`

**Answer: `N` is not the binding constraint on `E_C`, and measuring it exactly
would not unblock `E_C` on its own.** The committed records already confine `N`
two-sidedly to 0.0745 %, and that window is the smallest of the three
contributions to the quantity `E_C` is fixed by. No Palace run; nothing
launched. Record: `experiments/normalisation-N/`.

## 1. What the committed records already pin

`N = fᵀK⁺f/L` is the complete-mode normalisation, equivalently `Σ_all |p_m|`,
since `p_m = (g·v_m)² ≥ 0` with `g = K^{-1/2}f/√L`. Two facts already in the
record bound it from both sides:

- **Below**, because a partial sum of a non-negative series is a lower bound:
  `N ≥ Σ_saved |p_m| = 0.999254583556` (N2R, nine saved modes).
- **Above**, by the identity `N − N² = uᵀK_curl u + uᵀ(K_port − Q)u` with
  `u = K⁺q` and both terms non-negative, so `N(1 − N) ≥ 0` and `N ≤ 1`.

So **`N ∈ [0.999254583556, 1]`**, a window of width `7.454e-04`.

This is a *restatement* of what `spectral_compatibility.json` already holds —
`δ_saved = (1 − N) + omitted_weight` with both terms non-negative gives the
lower bound immediately. It is stated here as a bound because that makes the
obstruction visible: **the window and `δ_saved` are the same number.** Bounding
`N` therefore carries no information at all about how `δ_saved` splits.

It also slightly sharpens the wording in
[`fem-spectral-mapping.md`](fem-spectral-mapping.md), which says `N` "is not
measured by any committed column". The columns do not measure it, but together
with the proven identity they do **confine** it, two-sidedly, to 0.0745 %.

## 2. `N` is the smallest of the three contributions

`E_C` is fixed by `a/N`. What that quantity is actually sensitive to, N2R,
field-resonant variant, baseline `2.3526526 GHz²`:

| contribution | relative size | ratio to `N` |
|---|---|---|
| **the `N` normalisation itself**, across its *entire* admissible range | **7.505e-04** | 1× |
| refinement `N1R → N2R`, two solved discretisations | 1.876e-02 | 25× |
| placing the omitted weight at 12 GHz | 4.488e-02 | 60× |
| … at 15 GHz | 7.054e-02 | 94× |
| … at 20 GHz | 1.260e-01 | 168× |
| … at 30 GHz | 2.844e-01 | 379× |
| … at 50 GHz | 7.914e-01 | 1054× |

Pinning `N` exactly would collapse the **smallest** term by a factor of at most
25 relative to the next one. The number `E_C` is fixed by would barely move.

## 3. Why `N` is nevertheless the right lever — indirectly

`δ_saved = (1 − N) + omitted_weight`, both non-negative, neither measured
separately. Measuring `N` **splits** it:

```
omitted_weight = δ_saved − (1 − N)
```

- If `N ≈ 1`, then `omitted_weight ≈ δ_saved = 7.45e-04`: spectral weight is
  genuinely missing, and the far-mode rows above **apply in full** — 4.5 % to
  79 % on `a/N`, depending on where it sits.
- If `N ≈ Σ_saved|p|`, then `omitted_weight ≈ 0`: **no modes are missing**, and
  the largest contribution **vanishes entirely**.

So `N` does not tighten `a/N` directly. It decides whether the dominant
ambiguity exists at all. That is a real and large prize — but it is a different
claim from "measuring `N` unblocks `E_C`", and the distinction matters because
of §4.

## 4. Even an exact `N` does not unblock `E_C`

The refinement contribution, **1.876e-02**, is an observed difference between
two solved discretisations. No measurement of `N` touches it. With `N` known
exactly and `omitted_weight` found to be zero, `a/N` would still rest on one
mesh with no convergence statement and a 1.9 % observed movement under the one
refinement step available. `E_C` would move from **UNAVAILABLE** to *available
on one mesh, with a 1.9 % observed discretisation sensitivity and no continuum
statement* — which is not the same as unblocked, and is not enough to certify a
coupling.

## 5. What measuring `N` would actually take

**It is not an eigenvalue problem.** `N = fᵀK⁺f/L` is *static*: one linear
solve `K u = f` with the same operator the eigensolver already assembles, then
`N = fᵀu/L`. Summing `p_m` over more eigenmodes is the wrong instrument — the
tail converges only as `1/ω²`, and the mode count is dominated by port-operator
artefacts.

**The pinned Palace cannot do it directly.** The five solver types are
`DRIVEN`, `EIGENMODE`, `ELECTROSTATIC`, `MAGNETOSTATIC`, `TRANSIENT`
(`utils/configfile.hpp`). None computes `fᵀK⁺f/L`. In particular
`MAGNETOSTATIC` builds `CurlCurlOperator` with `SurfaceCurrentOperator`
excitation — it omits `K_port` entirely, and its excitation is a surface
current, not the port voltage functional `f`.

**The plausible supported route** is a `DRIVEN` sweep well below the lowest
resonance. The driven system matrix carries the same `K = K_curl + K_port`, and

```
fᵀ(K − ω²M)⁻¹f / L = Σ_m p_m / (1 − ω²/λ_m) → N   as ω → 0
```

so two or three low frequencies extrapolated in `ω²` would give `N`. At
`ω = 0.005 GHz` against `λ₁ = 1.526² GHz²` the leading correction is `~1.1e-05`.

**This is not proposed as ready.** It needs the exact identification of which
reported driven quantity equals `fᵀ(K − ω²M)⁻¹f`, verified against the pinned
source, and it is a solver type this campaign has never run — new config shape,
new postprocessing, new failure modes. Nothing was written and nothing was
launched: the PO1 approval authorised one eigenmode run and is spent.

## 6. Recommendation

Measuring `N` is worth doing, but **not** as "the step that unblocks `E_C`".
Frame it as what it is: the measurement that determines whether any spectral
weight is missing, and so whether the 4.5–79 % far-mode ambiguity is real. If
it returns `omitted_weight ≈ 0`, the dominant obstruction disappears and the
remaining one is the 1.9 % refinement sensitivity — which needs a third
discretisation, not a better `N`.

The honest minimum sequence is therefore **two** measurements, not one:

1. a low-frequency `DRIVEN` solve to measure `N` and split `δ_saved`;
2. a third refinement level, to turn the 1.9 % observed movement into a
   convergence statement.

Neither is designed or approved. Each is a separate approval under the existing
protocol.
