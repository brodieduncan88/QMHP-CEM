# Quantities taken on report from the follow-up audit

The deep-research assessment builds arithmetic on numbers it received from the
QMHP-CoPro V2A G0 follow-up audit v0.1. The audit's own artefacts (the five-node
capacitance matrix, the diagonalisation, the sweep outputs, the ledger inputs) are
**not** in this repository, so the quantities below are reproduced nowhere here.
`tools/v2a/check_assessment_arithmetic.py` checks only what is derived *from* them.

| Quantity | Value as reported | Used by |
|---|---|---|
| Target 22-conditioned mediator transition `f_22` | 7.016031785 GHz | thermal occupation, carrier `f_d` |
| Nearest other logical-conditioned mediator line separation `Δ_min` | ≈ 5.90 MHz | Rabi ladder ratios |
| Charge matrix element `|⟨22,1_C| n_C |22,0_C⟩|` | 1.300454 (text also uses ≈1.30 and "toward 1.36") | `u_C` at each duration |
| Displayed static ZZ point `ζ/2π` | 62.1 kHz | M1 `T_π` |
| M1 nominal static-wait sweep range | 8.05–8.37 µs over `f_C = 0` to `0.30 Φ₀` | M1 deprioritisation |
| Minimum dressed-label continuation overlap | 0.994562 | label validity at `0`, `0.2 Φ₀` |
| Final bare-state overlap | 0.897881 | label validity at `0`, `0.2 Φ₀` |
| Proposed `u_C` search cap | 5 MHz (convention not yet bound; see registration R1) | 150 ns boundary status |
| Two-qubit gate error screen | 8×10⁻⁴ | ledger diagnostic average |
| Schedule pair counts | [2,3,2,3,4,3,2,3,2] | four-layer structure |
| Schedule length / gate layers | 20 µs / four 1 µs layers | 0.8 time factor |
| Background parent term | 1.700×10⁻³ | 1.360×10⁻³ |
| Dephasing residual | 1.441×10⁻³ (parent ≈ 1.80125×10⁻³) | ledger check |
| Direct unlocated 2→0 bypass limit | 5 s⁻¹ | separate physical requirement |
| Mediator lifetime stress sweep | 1.2 µs to 1 ms — the 1.2 µs low end is attributed to the Singh experiment as "traceable"; **no retrievable text confirms it** (see `references.md`) | loss stress domain |
| Temperature stress sweep | 15 / 20 / 30 mK | thermal occupation |
| Initial mediator population stress values | 0, 10⁻³, 10⁻² | non-equilibrium interpretation |
| Crosstalk stress points | −80 / −60 / −50 / −40 dB, four quadrature phases | registration R2 |
| Surface-17 insertion duration that remains prohibited | 196.773 ns | programme restriction |
| Claimed single-qubit gate count bound | `N_1Q ≤ 5` | unverified schedule claim |

Anything in the assessment that cites one of these values inherits its
"reported, not reproduced" status.
