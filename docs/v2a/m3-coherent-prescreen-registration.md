# M3 coherent-selectivity prescreen — registration template (v0.1-draft)

**Status:** DRAFT. This document is the executable registration the deep-research
assessment asks for before the bounded M3 prescreen runs. Every field marked
`BIND` must be given a single value and this file committed **before** any driven
propagation is executed. The registration is frozen by the commit hash of this
file; results obtained under a different value of any `BIND` field belong to a
different registration.

Scope authorised by the assessment: **one frozen, non-optimising, one-tone
coherent prescreen.** Nothing here authorises the 256-evaluation optimiser,
open-system P4 closure, AMD-E, a Surface-17 insertion, or any architecture claim.

---

## R1. Drive normalisation  (`BIND` before execution)

The assessment identifies a factor-of-two ambiguity that decides whether the
150 ns point is inside or outside the 5 MHz cap. It must be closed by writing the
exact drive term used in the simulation.

| Field | Value |
|---|---|
| R1.1 Exact drive Hamiltonian, as coded | `BIND` — one of the two forms below, or the literal expression if different |
| R1.2 Meaning of `u_C` | `BIND` — exactly one of: peak lab-frame cosine coefficient / RWA coupling / Rabi frequency / angular-frequency amplitude |
| R1.3 Units of every quoted amplitude and frequency | `BIND` — cycles per second (Hz, MHz) unless a value is explicitly tagged rad s⁻¹ |
| R1.4 Operator the drive multiplies | `BIND` — the mediator charge operator `n_C` in the full (untruncated-to-two-level) coupled basis |
| R1.5 Envelope family | `BIND` — one smooth one-tone family, e.g. `u_C(t) = u_peak · w(t)` with `w` a Hann (cos²) window on `[0, T]`; give `w(t)` literally |
| R1.6 Carrier | `BIND` — `f_d` (nominally `f_22 = 7.016031785 GHz`), phase `φ`, and whether `f_d` is fixed at `f_22` or re-centred per duration (no per-duration optimisation is permitted) |
| R1.7 What the 5 MHz cap bounds | `BIND` — `max_t |u_C(t)| ≤ 5 MHz` in the meaning fixed by R1.2 |

The two candidate forms and their consequences (two-level subspace `{|0_C⟩,|1_C⟩}`,
real matrix element `n = ⟨22,1_C| n_C |22,0_C⟩ = 1.300454`, resonant rotating-wave
approximation):

| Form | Drive term | Rabi frequency `f_R` (cycles/s) | `u_C` for a 2π cycle in `T` | `u_C` at `T = 150 ns` | 150 ns vs 5 MHz cap |
|---|---|---|---|---|---|
| A (one-factor) | `H_d/h = u_C(t) n_C cos(2π f_d t + φ)` | `f_R = u_C · n` | `u_C = 1/(T n)` | 5.126 MHz | **outside** (needs `T ≥ 153.8 ns`) |
| B (two-factor) | `H_d/h = 2 u_C(t) n_C cos(2π f_d t + φ)` | `f_R = 2 u_C · n` | `u_C = 1/(2 T n)` | 2.563 MHz | inside (needs `T ≥ 76.9 ns`) |

Form A is the convention under which the assessment's own "≈5.13 MHz at 150 ns"
arithmetic is correct, so it is the presumptive default; the choice is still the
project's and must be written into R1.1.

**The cap is a joint constraint on convention *and* envelope, not on duration
alone.** The `u_C` values in the table above are for a rectangular pulse. Under
the on-resonance pulse-area theorem a smooth envelope of the same duration needs
its peak raised by `1/η`, where `η` is the envelope's area as a fraction of
`peak × T` (Hann: `η = 1/2`, so 2.00×; Gaussian truncated at ±2σ: 1.67×). Applying
that consistently to the whole ladder gives the durations that breach a 5 MHz peak
cap at `n_C = 1.300454`:

| Envelope | Convention A (one-factor) | Convention B (two-factor) |
|---|---|---|
| rectangular | 150 ns | none |
| Gaussian ±2σ | 150, 200 ns | none |
| Hann (cos²) | 150, 200, 300 ns | 150 ns |

Two consequences follow, and both are why R1.5 must be bound together with R1.1:

- **The 150 ns breach survives the convention choice** once a Hann envelope is
  used, because the Hann peak penalty (×2) exactly cancels the convention factor
  (÷2): `2/(2 T n) = 1/(T n) = 5.126 MHz` either way. The boundary/stress label on
  150 ns is therefore robust, which the assessment asserts but does not show.
- **Under convention A the breach is not confined to 150 ns.** With a Hann
  envelope 200 ns (7.69 MHz) and 300 ns (5.13 MHz) also exceed the cap. The
  assessment applies its finite-edge argument only at the 150 ns point; if
  convention A and a Hann envelope are bound together, the boundary/stress label
  must extend to 200 and 300 ns, or the cap must be restated as a bound on
  something other than the peak (R1.7).

Clamping at the cap is not a soft alternative. Holding a rectangular 150 ns pulse
at exactly 5 MHz under convention A under-rotates by 2.47 % and leaves
`P(1_C) = 6.0×10⁻³` in the mediator, about 7.5× the 8×10⁻⁴ screen.

Two further factors are routinely confused with the drive prefactor and are
**not** it. They are separate `BIND` hazards:

- `MHz → Mrad s⁻¹` is ×2π = 6.283, not ×2. The 5 MHz cap is 31.4 Mrad s⁻¹.
- Writing the rotating-frame Hamiltonian as `ħΩ σ_x` rather than `(ħΩ/2) σ_x` and
  calling the prefactor "the Rabi frequency" is an independent factor of two, on
  top of whichever drive form R1.1 binds.

Values under both forms for every duration, and the envelope-corrected cap table,
are produced by `tools/v2a/check_assessment_arithmetic.py` (`u_C_table`,
`envelope_cap_table`, `durations_breaching_cap`).

### R1b. The static-ZZ convention carries the same hazard (`BIND`)

The assessment freezes the drive convention but not `ζ`. The M1 arithmetic
`T_π = 1/(2ζ)` holds only where `ζ` is the **full** conditional shift
`(E₂₂ − E₂₀ − E₀₂ + E₀₀)/h`, equivalently `H/h = ζ|22⟩⟨22|` or `(hζ/4) Z⊗Z`. If the
code instead reports the coefficient `J` in `H/h = (J/2) Z⊗Z`, the same 62.1 kHz
gives `T_π = 4.03 µs`, not 8.05 µs. Any revived M1 work must bind `ζ` explicitly.

### R1c. SQUID junction-phase sign and flux allocation  (`BIND`)

The audit's static test — reversing the imaginary hopping sign leaves the
spectrum unchanged — has probability one of passing for any Hermitian matrix,
because the reversed matrix is the complex conjugate and shares the characteristic
polynomial. It therefore does not establish that the sign convention is right,
and at fixed `f_C` with a real drive the two sign choices give transposed
propagators. Bind explicitly:

| Field | Value |
|---|---|
| R1c.1 Sign convention of the imaginary hopping / junction phase in the coded `H` | `BIND` |
| R1c.2 Flux allocation across the SQUID junctions | `BIND` — the irrotational split (0.5/0.5 for a symmetric SQUID, per You–Sauls–Koch) or another declared allocation |
| R1c.3 Statement that `f_C` is held constant for the entire propagation | `BIND` — this is what makes the `dΦ/dt` connection term vanish identically for this run |

## R2. Crosstalk convention  (`BIND` before execution)

| Field | Value |
|---|---|
| R2.1 Definition | `BIND` — presumptive: `XT_ij = 20 log10 |S_ij|` (amplitude), `S_ij` a complex scattering coefficient from drive port `j` to the effective drive seen by element `i` |
| R2.2 Port normalisation | `BIND` — reference impedance (e.g. 50 Ω power-wave normalisation) and whether `S_ij` is normalised to the *intended* drive amplitude on the mediator |
| R2.3 Phase reference | `BIND` — the plane at which the phase of `S_ij` is defined; the four stress phases `{0°, 90°, 180°, 270°}` are relative to the mediator drive at that plane |
| R2.4 Stress points | `−80, −60, −50, −40 dB` → amplitude ratios `10⁻⁴, 10⁻³, 3.16×10⁻³, 10⁻²`. **Stress samples only, not a measured transfer function.** |
| R2.5 Where the leaked drive lands | `BIND` — which operators (data-qubit charge operators, readout modes, mediator flux) receive `S_ij · u_C(t)` |

The hazard is **mixing** conventions, not `20 log10` versus `10 log10` as such: a
consistently applied power definition `10 log10 |S|²` gives the identical dB
figure and the identical amplitude. The failure mode is a number produced under
one definition and consumed under the other, which squares or square-roots the
amplitude (10⁻² becomes 10⁻⁴ at the −40 dB point). The registration therefore
states the definition literally rather than writing "dB".

Two further R2 items the stress grid does not by itself settle:

- **Is crosstalk onto the mediator's own drive calibrated out?** `BIND`. An
  uncalibrated in-phase −40 dB term is a 1 % amplitude error on the `2π` cycle
  and leaves `P(1_C) = sin²(π·10⁻²) = 9.9×10⁻⁴` on its own, already above the
  8×10⁻⁴ screen. Whether that counts against the screen depends entirely on this
  binding.
- **`S_ij` is not the ratio of Hamiltonian drive coefficients.** Converting a
  port-to-port scattering coefficient into `u_j/u_C` needs the per-element
  port-to-operator mapping (coupling capacitance, zero-point charge, matrix
  element). R2.5 must state that mapping, or the dB figure is not yet a drive.
- The four quadrature phases bracket the amplitude extremes of a single
  interfering path. They do not cover several simultaneous paths, a phase that
  rotates across the pulse band (at 150 ns the band is ~13 MHz, so a few ns of
  differential delay is tens of degrees), or inductive crosstalk into `f_C`, which
  is a different operator entirely.

## R3. Validity of the `f_C = 0.28 Φ₀` sensitivity point  (`BIND` before execution)

The two label-audited points are `f_C = 0` and `0.2 Φ₀`. Before `0.28 Φ₀` is used:

| Field | Value |
|---|---|
| R3.1 Dressed-label continuation from `0.2 Φ₀` to `0.28 Φ₀` | `BIND` — step size, minimum acceptable continuation overlap (the audited points reported min 0.994562) |
| R3.2 Independent bare-overlap labelling at `0.28 Φ₀` | `BIND` — minimum acceptable bare overlap (the audited final value was 0.897881) and the rule that the two labellings must agree |
| R3.3 Truncation / grid convergence at `0.28 Φ₀` | `BIND` — the same truncation and grid checks used at the audited points, with the same tolerances |
| R3.4 Removal rule | If state identity is ambiguous by either R3.1 or R3.2, the point is **removed** from the prescreen. It is never relabelled by hand. |

R3 is a static check; it does not require a time-dependent-flux Hamiltonian
because the prescreen holds `f_C` fixed. Any future trajectory with `f_C(t)`
requires a separately registered gauge-consistent time-dependent Hamiltonian
(see the assessment's SQUID-sign section).

## R4. Registered duration ladder

| `T` | `f_R = 1/T` | `f_R / Δ_min` (5.90 MHz) | Registered role |
|---:|---:|---:|---|
| 150 ns | 6.67 MHz | 1.13 | **boundary / stress** under every convention-envelope pair |
| 200 ns | 5.00 MHz | 0.85 | candidate; **boundary/stress if R1 binds convention A with a Hann or ±2σ Gaussian envelope** |
| 300 ns | 3.33 MHz | 0.56 | candidate; **boundary/stress if R1 binds convention A with a Hann envelope** |
| 400 ns | 2.50 MHz | 0.42 | candidate |
| 500 ns | 2.00 MHz | 0.34 | candidate |
| 650 ns | 1.54 MHz | 0.26 | candidate |
| 800 ns | 1.25 MHz | 0.21 | candidate |

No durations are added or removed after the first propagation. The ladder is a
mechanism test, not a search. Which rows carry the boundary/stress label is
decided by the R1 bindings **before** the run, not after seeing the results.

## R5. Exported quantities (per duration, per sector `ij ∈ {00, 02, 20, 22}`)

- `φ_ZZ` — the conditional phase extracted from the coherent logical map.
- `P_return^{ij}` — population returned to the initial encoded state.
- `P_{C,residual}^{ij}` — population left in mediator excited states.
- `P_sink^{ij}` — population in the Branch-A sink manifold.
- `P_higher^{ij}` — population in higher data-qubit levels outside `{0,2}`.
- `P_RO^{ij}` — population in the two modelled readout modes (**negligible values here do not close the omitted-mode question**).
- The untwirled coherent logical channel on the 4-dimensional encoded space.
- Worst-input terminal loss, maximised over arbitrary logical superpositions.
- Peak mediator population and `A_C = ∫ p_C(t) dt`. **Neither is to be converted into a P4 error**; that needs a physical dissipative model that does not yet exist.

Complete curves versus `T` are reported. No coherent-error cutoff is chosen after
seeing them; the P4 screen semantics are registered separately.

## R6. Prohibited in this run

DRAG or FAST-DRAG shaping; reinforcement learning; gradient or any adaptive
waveform optimisation; the 256-evaluation search; more than one envelope family;
per-duration re-tuning of `f_d` or `φ` beyond what R1.6 states; any open-system
propagation used to claim a P4 result; any AMD-E observability calculation.

## R7. Admissible outcomes

- **M3 retained** — at least one duration gives a numerically converged
  conditional cycle with mediator return and coherent error inside a window
  whose bound is **written here before the run** (`BIND`: the maximum
  worst-input terminal loss and the maximum unwanted-sector disturbance that
  count as "usable"). The assessment forbids choosing a coherent-error cutoff
  after seeing the curves and then, in its summary, makes "a clearly usable
  window" the criterion; the only way to honour the first is to bind the second
  now.
- **M3 redesign** — the registered one-tone mechanism cannot simultaneously
  obtain the required conditional phase, return the mediator, and keep unwanted
  logical/sink/higher-state disturbance acceptably small anywhere inside the
  domain.

Either outcome leaves **physical G0 BLOCKED**; that disposition is decided by the
physical evidence table in the assessment, not by this run.

## R8. Sign-off

| Item | Value |
|---|---|
| Registration frozen at commit | `BIND` |
| Hamiltonian file hash (frozen coupled circuit) | `BIND` |
| Person binding R1–R3 | `BIND` |
| Date | `BIND` |
