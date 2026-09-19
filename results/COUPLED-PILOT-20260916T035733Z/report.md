# Coupled chip-cell numerical-method pilot

Record `COUPLED-PILOT-20260916T035733Z`. Numerical-method pilot. Three Palace eigenmode solves of the same declared S1 chip cell, differing only in element order and size-field halo. NO coupling extraction was performed: no Route A inversion, no g, no invariant triple, no gate input, no Route B. The record carries completion, the mode list in the declared window, the site energy participation, wall time and memory. Every geometric value remains an unapproved ENGINEERING-SEED.

## 1. Did each solve complete?

| run | order | halo (mm) | DOF | status | Palace s | modes in window | max backward error |
|---|---|---|---|---|---|---|---|
| P1 | 2 | 0.08 | 208670 | COMPLETED | 2009.7 | 3 | 7.87e-11 |
| P2 | 1 | 0.08 | 39832 | COMPLETED | 32.4 | 8 | 5.55e-12 |
| P3 | 2 | 0.12 | 235806 | COMPLETED | 2567.5 | 4 | 1.19e-10 |

## 2. P1 vs P2: element-order sensitivity

- readout-like mode: {"P1": {"frequency_GHz": 8.845860386, "site_participation": -1.219227886e-07}, "P2": {"frequency_GHz": 7.044198362, "site_participation": -1.386334771e-11}}
- relative frequency change: 2.037e-01
- relative participation change: 9.999e-01
- fluxonium-like mode: {"P1": {"frequency_GHz": 1.707441654, "site_participation": 0.9979639976}, "P2": {"frequency_GHz": 1.158332505, "site_participation": 0.9985099177}}

## 3. P1 vs P3: halo sensitivity

- readout-like mode: {"P1": {"frequency_GHz": 8.845860386, "site_participation": -1.219227886e-07}, "P3": {"frequency_GHz": 8.296061308, "site_participation": 1.882190014e-07}}
- relative frequency change: 6.215e-02
- relative participation change: 1.648e+00
- fluxonium-like mode: {"P1": {"frequency_GHz": 1.707441654, "site_participation": 0.9979639976}, "P3": {"frequency_GHz": 1.784105812, "site_participation": 0.9982989962}}

## 4. Is the 0.08 mm halo admissible under the frozen criteria?

Criteria, frozen in execution-proposal.md §4.2 before this ran: Δp ≤ 1e-02, Δf ≤ 1e-04.

**NOT-A-HALO-VERDICT**
- participation: FAIL (Δp = 1.648e+00)
- frequency: FAIL (Δf = 6.215e-02)
- the frequency check failed, which indicates the level-1 mesh is too coarse for this geometry or the model is wrong, not that the halo is bad; the halo question is not answerable from this pilot

## 5. Which element order is justified for the next ladder?

**order 2** — P1 completed inside its 45 minute cap, so order 2 is selected
- order sensitivity: Δp = 9.999e-01, Δf = 2.037e-01

## 6. Next extraction stage

**REQUIRES-ANOTHER-BOUNDED-NUMERICAL-CHECK** — the frequency check failed, which indicates the level-1 mesh is too coarse for this geometry or the model is wrong, not that the halo is bad; the halo question is not answerable from this pilot

## Statement

Numerical-method pilot. Three Palace eigenmode solves of the same declared S1 chip cell, differing only in element order and size-field halo. NO coupling extraction was performed: no Route A inversion, no g, no invariant triple, no gate input, no Route B. The record carries completion, the mode list in the declared window, the site energy participation, wall time and memory. Every geometric value remains an unapproved ENGINEERING-SEED.
