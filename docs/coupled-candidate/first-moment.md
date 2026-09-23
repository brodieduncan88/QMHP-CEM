# The two spectral moments of the F-site functional

**Offline assessment.** No FEM solve, no driven sweep, no N3, no extraction, no
`E_C`, no `g`, no approval-file edit. The supplied review package named in the
task **did not reach this environment**; the identities below are derived and
verified independently, as instructed. Record: `experiments/first-moment/`.

## 1. The identities, and the assumptions they rest on

For the constrained pencil `K E_m = λ_m M E_m` — `K` symmetric positive
*semi*-definite, `M` symmetric positive definite, `E_mᴴ M E_m = 1` — with
`V = fᴴE` the port functional and `q = f/√L`:

```
p_m = (qᴴE_m)² / λ_m
N   = Σ_m p_m          = qᴴ K⁺ q        (zeroth moment, dimensionless)
A   = Σ_m λ_m p_m      = qᴴ M⁻¹ q       (first moment, units of λ)
```

The GHz² moment the existing analysis uses is `A/(2π·10⁹)²`, i.e. `Σ p_m f_m²`
with `f_m` in GHz.

**Verified on 200 synthetic pencils** (dimension 40, nullity 6, seed 20260920):
max relative error **1.57e-13** for `N`, **1.16e-15** for `A`.

**`A` is the better-posed of the two.** `Σ_m λ_m p_m = Σ_m (qᴴE_m)²` is a
*Parseval* sum over the M-orthonormal basis, so the first moment needs only
`M` — no `K`, no pseudoinverse, no null-space inversion. The zeroth moment
needs `K⁺`.

**Assumptions, stated rather than implied.**

- **Completeness.** The sums run over *all* eigenpairs. `Σ_m E_m E_mᴴ = M⁻¹`
  holds only for the complete set. A filtered subset is not a basis — and the
  damage is asymmetric: keeping the heaviest third of the modes recovers `N` to
  a median **0.946** but `A` to only **0.603**, because `A` is λ-weighted and
  the discarded high-λ modes carry little weight but much moment.
- **Null space.** `qᴴE₀ = 0` for every zero mode. Without it `p₀` diverges and
  neither sum exists. With it `q ∈ range(K)`, which is what makes `qᴴK⁺q`
  independent of *which* generalised inverse is used — any two solutions of
  `Kx = q` differ by a `ker(K)` vector, which `q` annihilates. The same
  condition is needed for `A`: `qᴴM⁻¹q` sums over *all* modes, so any kernel
  component would make it **overcount** relative to `Σ_{λ>0}`. This is an
  assumption about the QMHP model, **not** established by the synthetic trials.
- **Normalisation.** `E_mᴴ M E_m = 1`. Any other scaling rescales `p_m` and
  both moments. Palace's reported `p` carries its own normalisation, which must
  be reconciled, not assumed to match.
- **Projection.** The divergence-free projector changes the space the returned
  eigenvectors span. If it removes a direction `q` has a component along, the
  returned set is not complete *for `q`* and both sums fall short — silently.

## 2. The recorded `a` **is** this first moment

Both variants reproduce the recorded `a/N` and `a` from the raw N2R columns to
better than `1e-9`:

| variant | modes | `N_partial` | `A_partial` (GHz²) | reproduces record |
|---|---|---|---|---|
| A, all saved | 1–9 | 0.999254583556 | 2.351511939 | ✓ |
| B, field-resonant | 1, 2, 5, 8 | 0.999249524331 | 2.350887035 | ✓ |

So the identity `A = qᴴM⁻¹q` applies to the recorded number directly.

## 3. Six corrections

**1. Near-zero omitted weight does not bound the moment.** A weight `w` omitted
at frequency `F` contributes `w` to `N` and `w F²` to `A`; for fixed `w`, `w F²`
is unbounded in `F`. The earlier claim that `omitted_weight ≈ 0` makes the
far-mode ambiguity "vanish entirely" is **withdrawn**: it holds for *exactly*
zero, not approximately zero, and needs a tail-frequency or tail-moment bound
that no committed column supplies.

**2. Zero omitted F-site weight does not exclude dark modes.** `p_m = 0` means
`qᴴE_m = 0` — the mode is invisible *to this functional*. Such modes exist, are
not excluded by any moment of `q`, and may matter physically. A complete `N`
and `A` say nothing about them.

**3. The placements are scenarios, not bounds.** The 12–50 GHz table asks what
*would* follow if the whole of `δ_saved` were one mode at that frequency.
Nothing establishes that the missing spectrum lies in that window, and it is not
an uncertainty interval. The record now carries 100 and 200 GHz rows
(`+317 %`, `+1268 %` of `A_partial`) precisely to show the data does not close
the top end.

**4. Bookkeeping, unmixed.** The previously quoted `N` interval used **all nine**
weights; the `7.505e-4` denominator sweep it was set against used **variant B's
four**. Different denominators, not interchangeable. The gap is real but small —
`5.1e-06` in `N` (5e-04 of it), `6.2e-04 GHz²` in `A` (2.7e-04 of it) — and is
corrected by quoting one variant throughout, not by arguing it is negligible.

**5. No universal `1/ω²` tail rate.** `p_m = (qᴴE_m)²/λ_m` has a `1/λ`
denominator, but the numerator varies per mode and is bounded by nothing
measured here. The earlier "converges only as the `1/ω²` tail" is **withdrawn**;
no rate is assumed.

**6. A third refinement adds a trend point, not convergence.** The 1.9 % figure
is a comparison of two *truncated* proxies — partial sums over each record's own
saved set, not the converged moments. A third level would give three points on a
trend, which is not a continuum statement and does not certify an order.

## 4. Feasibility with the pinned code

**The port functional already exists as a vector.** `LumpedPortData::v`
(`lumpedportoperator.cpp`, `InitializeLinearForms`) is an assembled
`mfem::LinearForm` with a `VectorFEBoundaryLFIntegrator` over the port face,
coefficient `1/(w·n_elem)` — the width-averaging. `GetVoltage` computes `V = v·E`
from it. **This is exactly `f`**, not a postprocessed surrogate, and no new
assembly is required to obtain it.

**Both matrices are already exposed.** `SpaceOperator::GetStiffnessMatrix`,
`GetMassMatrix`, `GetDampingMatrix` are public.

So `A = (fᴴM⁻¹f)/L` needs **two existing accessors and one SPD solve**. `M` is
positive definite and well-conditioned; there is no pseudoinverse, no null
space to project, and no interaction with the divergence-free projector.

**`N` is the harder half**: `qᴴK⁺q` needs a singular solve, the `q ⊥ ker(K)`
condition actually checked rather than assumed, and the essential-DOF and
diagonal-policy treatment matched to the eigensolver's.

### The driven route is blocked at source

`LumpedPortOperator::AddExcitationBdrCoefficients` contains

```cpp
MFEM_VERIFY(std::abs(data.R) > 0.0,
            "Unexpected zero resistance in excited lumped port!");
```

and `InitializeLinearForms` builds the S-parameter form `s` with
`Hinc = (|Rs| > 0) ? 1/sqrt(...) : 0`, so at `R = 0` it assembles to the **zero
vector**. The F1 port has `R = 0`. An excited driven solve therefore **aborts**,
and the only way to run one is to add a resistance — which changes the loading,
adds a damping term to the pencil, and makes it a different operator. That is
forbidden, and it is also scientifically not the same problem.

**Verdict.** The direct quadratic form has decisively fewer unverified
assumptions. The driven route's central assumption — that some reported driven
voltage equals `fᴴ(K − ω²M)⁻¹f` — cannot even be tested, because the excitation
that would produce it cannot be assembled at `R = 0`.

**One honest caveat on both.** Neither is a configuration change. Every route
needs new code calling into Palace — the direct one needs the least, but it is
not zero, and that is a change to a pinned dependency's call surface.

## 5. Scope: what `A` and `N` would and would not be

They characterise **the specified discrete spectral construction** — the moments
of one functional against one constrained pencil at one discretisation. They are
**not** the registered physical `E_C`, and must not be promoted to it
automatically. Still requiring justification:

1. **Coordinate mapping.** That the F-coordinate of the registered two-node
   model is the one whose resolvent is `G_F`, rather than a normal-mode
   coordinate — the unresolved question of `r1-definition-decision.md`.
2. **Operator mapping.** That removing the rank-one `Q` is the right stand-in
   for opening the physical port. PO1 measured the *pair* of that removal and
   the projector's changed constraints, and could not separate them.
3. **Discretisation.** One mesh; no continuum statement.
4. **Circuit identification.** That `a/N` maps onto `E_C,F1F1` by the registered
   algebra, with the declared `L` and no further normalisation.

## 6. Recommended next computational task — for separate approval

**Evaluate the first moment `A = (fᴴM⁻¹f)/L` directly on N2R's discrete
problem.** Not `N`: `A` is the numerator where the leverage is, it is the
better-posed half, and it answers the question correction 1 raises.

| | |
|---|---|
| **inputs** | N2R's mesh, hash-gated `d8dc1a92…c14428`; N2R's solved config, sha256 `79304b5f…ba8c1f33f`, unchanged — order 1, `MGMaxLevels: 1`, same materials, same port, `R = 0` untouched; `L = 1.0345665367517793e-07 H` |
| **computation** | `M ← SpaceOperator::GetMassMatrix`; `f ← LumpedPortData::v`; one SPD solve `M x = f`; `A = (f·x)/L`, and `A/(2π·10⁹)²` in GHz² |
| **outputs** | `A` in λ-units and GHz²; the solve residual; `A − A_partial` against the recorded `2.351511939 GHz²` (variant A, all nine) |
| **what it settles** | `A − A_partial` **is** the omitted first moment, measured rather than scenarioed. Small ⇒ the whole placement table of §3.3 is excluded *as a class*, with no assumption about where missing weight sits. Large ⇒ the moment is genuinely incomplete and `a` is not a converged numerator |
| **what it does not settle** | `N`; the four mappings of §5; anything about dark modes; anything about the continuum |
| **cost** | one SPD solve on a 103 411-DOF space — far below an eigensolve; the 250 000-DOF rule and the 2 700 s cap are untouched and unchallenged |
| **what it needs first** | the code that calls those two accessors, reviewed; the essential-DOF and `DiagonalPolicy` treatment of `M` matched to the eigensolver's; and `qᴴE₀ = 0` checked, not assumed |

Not prepared, not configured, not approved. Nothing was launched, the approval
file is untouched, and PO1's approval is spent.
