# Verification record for the deep-research assessment

What was independently reproduced, what was refined, and what remains unverified.
The assessment text in
[`G0-followup-audit-v0.1-deep-research-assessment.md`](G0-followup-audit-v0.1-deep-research-assessment.md)
is kept as received; corrections and additions live here and in
[`m3-coherent-prescreen-registration.md`](m3-coherent-prescreen-registration.md).

Method: every numerical and physics claim cluster was given to two independent
verifiers with opposing briefs — one recomputing from first principles, one
trying to refute — plus a separate pass over the cited literature. Everything
marked "reproduced" below is also executed by
[`tools/v2a/check_assessment_arithmetic.py`](../../tools/v2a/check_assessment_arithmetic.py)
and covered by [`tests/`](../../tests/).

## Summary

| Cluster | Result |
|---|---|
| M1 static-wait timing | **Confirmed.** `T_π = 1/(2ζ) = 8.0515 µs` at 62.1 kHz; 1 µs needs exactly 500 kHz. |
| Rabi duration ladder | **Confirmed.** All seven `f_R = 1/T` rows and all seven `f_R/Δ_min` ratios reproduce. |
| `u_C` at 150 ns vs the 5 MHz cap | **Confirmed with material additions** — see below. |
| Drive factor-of-two | **Confirmed**, and two further independent factors identified. |
| Thermal occupation | **Confirmed.** 1.78×10⁻¹⁰, 4.88×10⁻⁸, 1.34×10⁻⁵ at 15/20/30 mK. |
| Crosstalk dB | **Confirmed**, with the hazard restated — see below. |
| Schedule structure | **Confirmed** here: the pair counts are exactly the Surface-17 stabiliser degree sequence and a balanced 4×6 conflict-free layering exists; three layers are impossible. |
| Once-only ledger arithmetic | **Confirmed.** Every identity checks exactly. |
| Static SQUID sign | **Confirmed.** Spectral equivalence holds for the stated reason. |
| Cited literature | **NOT VERIFIED.** See [`references.md`](references.md). |

No stated number was refuted. Every difference between the assessment and an
independent recomputation is rounding at the assessment's own quoted precision;
the largest is the 30 mK occupation, quoted 1.3×10⁻⁵ against 1.3352×10⁻⁵ (−2.6 %,
which is 1.34×10⁻⁵ at three significant figures).

## Material additions

These change what the registration must bind. They are not corrections to any
stated number.

**The 5 MHz cap binds on convention and envelope jointly, not on duration alone.**
The assessment applies its finite-edge argument only at 150 ns. Applied
consistently across the ladder at `n_C = 1.300454`, the durations that breach a
5 MHz *peak* cap are:

| Envelope | One-factor convention | Two-factor convention |
|---|---|---|
| rectangular | 150 ns | none |
| Gaussian ±2σ | 150, 200 ns | none |
| Hann (cos²) | 150, 200, 300 ns | 150 ns |

Two things follow. The 150 ns boundary label is **more robust than the assessment
argues**: with a Hann envelope it breaches under either convention, because the
Hann peak penalty (×2) exactly cancels the convention factor (÷2). But under the
one-factor convention the breach is **not confined to 150 ns**, so if that
convention is bound together with a Hann envelope, 200 and 300 ns need the same
label. The assessment's "No threshold needs to be changed" survives only because
relabelling is not a threshold change; the set of rows that get relabelled is
larger than it states.

**Clamping at the cap is not a soft alternative.** Holding a rectangular 150 ns
pulse at exactly 5 MHz under-rotates by 2.47 % and leaves `P(1_C) = 6.0×10⁻³` in
the mediator, about 7.5× the 8×10⁻⁴ screen.

**Two factors of two are not the drive prefactor.** `MHz → Mrad s⁻¹` is ×2π =
6.283, not ×2 (the assessment's "the same rule applies to MHz versus Mrad/s" sits
under a factor-of-two heading and invites the conflation). Separately, writing the
rotating-frame Hamiltonian as `ħΩ σ_x` rather than `(ħΩ/2) σ_x` while calling the
prefactor "the Rabi frequency" is an independent factor of two on top of whichever
drive form is bound.

**`ζ` carries the same unfrozen hazard as `u_C`.** `T_π = 1/(2ζ)` holds only where
`ζ` is the full conditional shift `(E₂₂ − E₂₀ − E₀₂ + E₀₀)/h`. If the code reports
the coefficient `J` in `H/h = (J/2) Z⊗Z`, the same 62.1 kHz gives 4.03 µs, not
8.05 µs. The assessment freezes the drive convention but not this one.

**The crosstalk hazard is mixing, not `20 log10` versus `10 log10`.** A
consistently applied power definition `10 log10 |S|²` gives the identical dB figure
and the identical amplitude. The failure mode is a number produced under one
definition and consumed under the other. Separately, an uncalibrated in-phase
−40 dB term on the mediator's own drive is a 1 % amplitude error that leaves
`sin²(π·10⁻²) = 9.9×10⁻⁴` on its own, already above the 8×10⁻⁴ screen — so whether
crosstalk on that line is calibrated out has to be bound, not left implicit.

**The M1 shortfall is a range.** "About a factor of eight" is 8.05 at the strongest
tested point (62.1 kHz) and 8.37 at the weakest (59.74 kHz, implied by the 8.37 µs
end of the sweep). The 500 kHz requirement is also a lower bound: it assumes the
entire 1 µs layer is available for the wait, with no ramp, adapter, recovery or
single-qubit time inside it.

**The crossover matrix element is exactly 4/3.** The assessment's "with `n_C` toward
1.36 it may fall just inside the cap" is correct — 4.90 MHz, 2.0 % inside — and the
value that separates inside from outside at 150 ns is `n_C* = 4/3 = 1.3333`. The
provenance of 1.36 is never given, so it reads as a hypothetical, not a second
reported value.

## Assumptions the assessment relies on without stating

Relevant to how the prescreen is registered and read:

- **Two-level truncation.** The `u_C` arithmetic treats the mediator as
  `{|0_C⟩,|1_C⟩}` with `n_C → n σ_x`. Adequate for the Rabi period; not for
  leakage, which is the question being asked. The `1_C → 2_C` element
  (≈ √2 × 1.30) and the mediator anharmonicity are never reported.
- **Zero diagonal elements** of `n_C` in the dressed basis. Exact for a bare
  transmon by parity, only approximate once dressed.
- **Exact resonance and the rotating-wave approximation.** Safe at these rates
  (Bloch-Siegert ≈ 1.6 kHz at the 150 ns point) but unstated.
- **The pulse-area argument is on-resonance only.** It fixes the required peak in
  the driven `22` sector and says nothing about the detuned `00`, `02`, `20`
  sectors, where envelope shape changes the response in a way that does not follow
  from area.
- **The 5 MHz cap is a search-domain bound chosen by the audit, not a measured
  hardware limit.** Physical controls are BLOCKED, so "inside or outside the cap"
  is bookkeeping against a self-imposed domain, not a feasibility statement.
- **Nominal versus effective temperature.** The 15/20/30 mK sweep assumes the
  mediator equilibrates with a bath at the plate temperature. Measured effective
  mode temperatures in superconducting hardware are commonly 40–80 mK. The
  assessment's own stress occupations correspond to 48.7 mK (10⁻³) and 73.0 mK
  (10⁻²), so those values are not exotic — they are near the range real devices
  routinely show, which strengthens rather than weakens the case for keeping them.
- **Temperature and initial occupation are not independent in a Lindblad model.**
  Keeping them as separate stress axes is a coherent-prescreen convenience; at P4,
  detailed balance ties the steady-state occupation to the bath temperature, and
  the two axes cannot then be varied freely.
- **`S_ij` is not a ratio of drive coefficients.** Converting it into `u_j/u_C`
  needs the per-element port-to-operator mapping. Until that mapping is stated, a
  dB figure is not yet a drive.
- **The ZZ sign is irrelevant to `T_π`** but not to the compiled gate; only `|ζ|`
  enters the timing argument.

## Notation drift in the received text

Minor, recorded so the repository version is not silently "corrected":

- The main body writes the mediator residual as `P_{residual,C}`, the trailing
  summary as `P_{C,residual}`. Same quantity.
- The main body says the 150 ns coefficient "slightly exceeds" the cap; the
  trailing summary says "at or slightly beyond". Under the one-factor convention
  it is unambiguously beyond, by 2.53 %; the hedge conflates the two conventions.
- `n_C` appears as "≈1.30", "1.300454" and "toward 1.36" in three places.

## Not verified here

- **Every cited work.** The assessment's citation markers were opaque tool tokens;
  they have been mapped to keys but the works themselves are not confirmed. See
  [`references.md`](references.md).
- **Every audit input.** `f_22`, `Δ_min`, `n_C`, `ζ`, the overlaps 0.994562 and
  0.897881, the ledger parents, the 5 s⁻¹ bypass limit, `N_1Q ≤ 5` and 196.773 ns
  are taken on report. See [`reported-not-reproduced.md`](reported-not-reproduced.md).
- **The physical dispositions.** Whether physical G0 is correctly BLOCKED is a
  judgement about missing evidence, not an arithmetic question, and nothing here
  tests it.
