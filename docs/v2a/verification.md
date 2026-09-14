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
| Schedule structure | **Numbers confirmed; the stated inference is invalid.** The pair counts are exactly the Surface-17 stabiliser degree sequence, a balanced 4×6 conflict-free layering exists (481,776 of them), and three layers are impossible. But "sum to 24, therefore edge-colourable into four layers" is a non sequitur — see below. |
| Once-only ledger arithmetic | **Identities confirmed; the 0.8 factor contradicts the assessment's own degree list** — see below. |
| Static SQUID sign | **Isospectrality confirmed; the stated reason is wrong**, and the test it licenses is near-vacuous — see below. |
| Internal consistency | **One substantive contradiction and eleven body-versus-summary divergences** — see below. |
| Cited literature | **Identified from search snippets only; several attributions not supported.** See [`references.md`](references.md). |

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

**The schedule inference is a non sequitur.** The assessment writes that the
counts "sum to 24, consistent with four layers of six interactions. That is
useful: the pair graph can be edge-coloured into the desired four conflict-free
layers." The sum is necessary, not sufficient: a graph with the identical data
degree sequence `[2,3,2,3,4,3,2,3,2]` and the identical 24 edges but one
degree-5 ancilla is *not* 4-edge-colourable (the checker constructs one). What
actually gives four layers is the ancilla side, which the assessment never
states: the data–ancilla Tanner graph is bipartite with maximum degree 4, so
König's theorem gives exactly four colours, and four is the minimum. "Four
layers of six" is also stronger than "four conflict-free layers" — only 7.9 % of
proper 4-colourings are balanced 6/6/6/6. The object coloured is the data–ancilla
incidence graph, not a "pair graph" of data qubits; the V2A channel that was
characterised is a data–data interaction through a mediator, and applying it to
data–ancilla syndrome pairs is an unstated assumption. Hook-error ordering is not
one caveat among seven but the dominant one: for each weight-4 stabiliser, 8 of
the 24 engagement orders reduce the effective distance from 3 to 2. And mediator
occupancy is a further conflict constraint that edge colouring cannot express.

**The 0.8 duty factor contradicts the degree list two subsections earlier.** A
data qubit of degree `d` is inside a native-gate interval for `d` of the four
1 µs layers, so its outside-fraction is `1 − d/20`. Averaged over the assessment's
own `[2,3,2,3,4,3,2,3,2]` this is `13/15 = 0.8667`, not 0.8 (per ancilla 0.85;
over all 17 qubits 0.8588). Only the single degree-4 centre qubit is at 0.8. The
uniform 0.8 is the lowest of every defensible accounting, so it is systematically
background-removing. Applied to the stated parents: 1.700×10⁻³ × 13/15 =
1.473×10⁻³, not 1.360×10⁻³ (+8.3 %). The quoted 1.441×10⁻³ moves the same way.
Separately, 0.8 assumes the all-in channel spans the full 1 µs layer, whereas the
registered pulses are 150–800 ns; pulse-resolved factors are 0.89–0.98.

**"Linear in time" is a Markovian assumption applied to a dephasing term.** Under
quasi-static 1/f dephasing the envelope is `exp[−(t/T_φ)²]` and the factor is
0.8² = 0.64, giving 1.153×10⁻³ against the quoted 1.441×10⁻³, a 25 % difference
the exponent alone decides. The reclosure the assessment defers must declare the
time-scaling exponent per mechanism, not assume it.

**The diagnostic average hides a 2:1 spread.** 24×8×10⁻⁴/9 = 2.133×10⁻³ is
degree-weighted and describes no individual qubit: corners see 1.6×10⁻³, the
centre 3.2×10⁻³. It also charges the whole two-qubit error to the data side;
over all 17 qubits it is 1.129×10⁻³.

**Two layer budgets are in use.** The once-only section uses four 1 µs layers
(4 µs). The standing prohibition on a "196.773 ns Surface-17 insertion" implies
four layers of 196.773 ns (0.787 µs). They differ by 5.08×, and the assessment
does not say which one the 8×10⁻⁴ screen is meant against.

**The SQUID-sign reason is wrong and the test is near-vacuous.** Reversing the
imaginary hopping sign takes `H = A + iB` to `A − iB = Hᵀ = conj(H)`. That is the
antiunitary complex-conjugation image, not "a static phase/gauge transformation":
`det(Hᵀ − λ) = det(H − λ)` identically, so isospectrality is guaranteed for *any*
Hermitian matrix regardless of whether the sign convention in the model is right.
A check with probability one of passing carries no evidential weight, and the
disposition "PASS for static spectrum only" should be read as "not tested". It is
also in tension with the assessment's own list of unestablished items, which
includes "the direction/sign of the available native conditional phase" — the
static test cannot close that. At fixed `f_C` with a real drive the two sign
choices give `U₋ = U₊ᵀ`, so the sign does bear on dynamics even without a flux
ramp. This is a fourth registration item, added as R1c.

**The `dΦ/dt` caveat is unquantified and unsourced.** The irrotational allocation
belongs to You, Sauls and Koch, not to the assessment's unnamed "appropriately
chosen irrotational variables". For a symmetric SQUID the irrotational split is
0.5/0.5; the common all-flux-on-one-junction convention differs by `δa = 1/2`,
which for a ramp gives a connection term `δH/h = δa·(dΦ/dt/Φ₀)·|n_C|` — of order
10² kHz for the ramp rates in play. The assessment asserts the term exists and
gives no magnitude.

**The label-validity standard is applied asymmetrically.** `f_C = 0.28 Φ₀` is
blocked pending label and truncation checks because it lies outside the audited
points 0 and 0.2 Φ₀. The M1 sweep result 8.05–8.37 µs "over `f_C = 0` to
0.30 Φ₀" is accepted on the same unaudited labels, 0.10 Φ₀ beyond the audited
range. Either the M1 sweep needs the same re-check, or the M3 block is stricter
than the standard being applied elsewhere.

**Body and trailing summary diverge in twelve places.** The substantive ones:

- The body computes 5.13 MHz "using the audit's own convention" and then declares
  that convention undetermined; the number is only reproducible under the
  one-factor form, so the assessment has inferred the audit's convention without
  saying so.
- The body demands a "complex multiport S-matrix", "the actual complex multiport
  response" and a "calibrated complex multiport response", and adds that even
  that is not the full driven Hamiltonian; the summary reduces the prerequisite
  to "delivered `S₂₁`", a single two-port element.
- The body forbids "retroactively choosing a coherent-error cutoff after seeing"
  the curves; the summary makes "a clearly usable coherent-error window" the
  retain criterion — an unregistered post-hoc judgement of exactly the kind the
  body forbids. R7 in the registration now requires the criterion to be bound
  before the run.
- The body names only −40 and −80 dB; the summary introduces the four-point set
  −80/−60/−50/−40 dB, which appears nowhere in the body.
- The summary adds the removal rule for an ambiguous `0.28 Φ₀` label; the body
  only requires the checks be repeated.
- The summary drops the body's "do not translate `A_C` or peak population into
  P4 error".
- The executive table gives M3 the disposition RETAIN, while the text gives
  CONDITIONAL GO and defines "M3 retained" as one of two *outcomes* the prescreen
  has not yet produced.
- The declared model domain "150–800 ns / 5 MHz" is empty at its own 150 ns
  endpoint under the one-factor rectangular reading, and empty out to 308 ns
  under one-factor Hann; "No threshold needs to be changed" is true of the cap
  and the screen but not of the domain.
- A 1 µs layer must hold the gate plus ramps, embedded phases, recovery and
  readiness, yet the ladder runs to 800 ns, leaving 200 ns for all of that. The
  assessment does not examine this.

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

- **Every cited work.** This environment's network policy refuses every
  scholarly host, so the works were identified from search snippets and no
  attributed claim was read in its source. Several attributions are not
  supported by what was recoverable, including the ≈1.2 µs mediator lifetime
  that anchors the loss stress sweep and the "several MHz" spectator shifts. See
  [`references.md`](references.md).
- **Every audit input.** `f_22`, `Δ_min`, `n_C`, `ζ`, the overlaps 0.994562 and
  0.897881, the ledger parents, the 5 s⁻¹ bypass limit, `N_1Q ≤ 5` and 196.773 ns
  are taken on report. See [`reported-not-reproduced.md`](reported-not-reproduced.md).
- **The physical dispositions.** Whether physical G0 is correctly BLOCKED is a
  judgement about missing evidence, not an arithmetic question, and nothing here
  tests it.
