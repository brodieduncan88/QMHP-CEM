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
project's and must be written into R1.1. Whichever form is bound, the 150 ns point
is registered as a **boundary/stress duration**, not a normal candidate, for two
reasons that do not depend on the convention: the target Rabi scale at 150 ns
(6.67 MHz) exceeds the 5.90 MHz nearest-line separation, and any smooth envelope
needs a larger peak than a rectangle of the same area (Hann: 2.0×; Gaussian
truncated at ±2σ: 1.67×), so the rectangular-pulse `u_C` above is a lower bound on
the peak that the bound envelope will actually require.

Values under both forms for every duration are produced by
`tools/v2a/check_assessment_arithmetic.py` (`u_C_table`).

## R2. Crosstalk convention  (`BIND` before execution)

| Field | Value |
|---|---|
| R2.1 Definition | `BIND` — presumptive: `XT_ij = 20 log10 |S_ij|` (amplitude), `S_ij` a complex scattering coefficient from drive port `j` to the effective drive seen by element `i` |
| R2.2 Port normalisation | `BIND` — reference impedance (e.g. 50 Ω power-wave normalisation) and whether `S_ij` is normalised to the *intended* drive amplitude on the mediator |
| R2.3 Phase reference | `BIND` — the plane at which the phase of `S_ij` is defined; the four stress phases `{0°, 90°, 180°, 270°}` are relative to the mediator drive at that plane |
| R2.4 Stress points | `−80, −60, −50, −40 dB` → amplitude ratios `10⁻⁴, 10⁻³, 3.16×10⁻³, 10⁻²`. **Stress samples only, not a measured transfer function.** |
| R2.5 Where the leaked drive lands | `BIND` — which operators (data-qubit charge operators, readout modes, mediator flux) receive `S_ij · u_C(t)` |

If anyone reads the stress points as power dB (`10 log10`), the assumed leaked
amplitude is wrong by the ratio itself (10⁻⁴ to 10⁻² at these points). The
registration therefore states the definition literally rather than "dB".

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
| 150 ns | 6.67 MHz | 1.13 | **boundary / stress** |
| 200 ns | 5.00 MHz | 0.85 | candidate (same order as `Δ_min`) |
| 300 ns | 3.33 MHz | 0.56 | candidate |
| 400 ns | 2.50 MHz | 0.42 | candidate |
| 500 ns | 2.00 MHz | 0.34 | candidate |
| 650 ns | 1.54 MHz | 0.26 | candidate |
| 800 ns | 1.25 MHz | 0.21 | candidate |

No durations are added or removed after the first propagation. The ladder is a
mechanism test, not a search.

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
  conditional cycle with mediator return and a clearly usable coherent-error
  window inside the registered domain.
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
