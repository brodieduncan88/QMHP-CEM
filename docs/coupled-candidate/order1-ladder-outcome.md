# The order-1 mesh-refinement check: what three rungs measured

Records, each committed append-only with its own manifest:

| level | h_gap | DOF (order 1) | wall clock | record |
|---|---|---|---|---|
| 1 | 0.010000 mm | 39 832 | 32.4 s | `COUPLED-PILOT-20260916T035733Z/P2` |
| 2 | 0.006667 mm | 79 944 | 81.2 s | `COUPLED-LADDER-O1-L2-20260916T080802Z` |
| 3 | 0.005000 mm | 147 372 | 159.1 s | `COUPLED-LADDER-O1-L3-20260916T091212Z` |

Order 1 and a 0.08 mm halo throughout, the same S1 geometry and port model, the
same declared 0.5–9.0 GHz window, and the prospective admission, matching and
magnitude rules imported unchanged. Every rung inside the 250 000-DOF rule and
far inside the 45-minute cap. **No coupling extraction** — no Route A inversion,
no `g`, no charging energy, no capacitance, no circuit parameter.

---

## 1. The sequence does not converge

Both tracked modes fail the weakest possible test of convergence.

| mode | L1 | L2 | L3 | Δ(L1→L2) | Δ(L2→L3) | ratio | cumulative |
|---|---|---|---|---|---|---|---|
| fluxonium-like | 1.158333 | 1.461887 | 1.709562 | −0.303554 | −0.247675 | **1.226** | **+47.6 %** |
| readout-like | 3.693189 | 3.885511 | 4.087683 | −0.192322 | −0.202172 | **0.951** | +10.7 % |

For `f(h) = f* + C h^p` with any `p > 0`, the refinement ratios used here
(`h` scaling 1, 2/3, 1/2) force the ratio of successive differences above
`(ln H₁ − ln H₂)/ln H₂ = 1.4094` even in the limit `p → 0`. The fluxonium-like
mode gives 1.226; the readout-like mode gives 0.951, meaning its differences are
**growing**. So:

- **there is no observed order of convergence** for either mode;
- **there is no extrapolated limit**, and therefore nothing to measure a
  required order-2 mesh against;
- halving `h` moved the fluxonium-like frequency by 47.6 % and the increments
  did not decay.

This is a stronger negative than level 2 alone implied. Two rungs gave a large
difference; three show the differences are not shrinking.

The estimator is built to return this. It recovers `p = 2.000000` and the exact
limit on a synthetic `h²` sequence, and refuses on non-monotone and
slowly-shrinking sequences, with the refusal reported rather than rounded into
a number.

*One observation, not to be over-read.* Order 1 at level 3 (1.709562 GHz) lands
within 0.12 % of order 2 at level 1 (1.707442 GHz). Two different
discretisations landing near each other says nothing about the limit while
neither is converging.

## 2. The port-stiffness mechanism reproduces — but the procedure said otherwise

The predeclared procedure returned **CALIBRATION-UNSOUND** at level 3: the
admitted modes disagreed about the constant `κ` by 20.5×, so it withheld a
verdict rather than issuing one. That stands as the record.

**Why it withheld, and what the data actually say.** `κ` is calibrated on
admitted modes by assuming Palace's rank-one `E_ind` surrogate is faithful on
them. It is not faithful on all of them:

| mode | reported `p` | true `p = 1 − E_mag/E_elec` | ratio | `κ` |
|---|---|---|---|---|
| m1 (1.710 GHz, in window) | 9.9832e-1 | 9.9834e-1 | 1.0000 | **55.3039** |
| m2 (4.088 GHz, in window) | 9.1128e-4 | 9.1159e-4 | 0.9997 | **55.2856** |
| m6 (11.836 GHz, **out of window**) | 4.2035e-5 | 8.5991e-4 | **0.0489** | 2.7035 |

The two in-window admitted modes agree on `κ` to **0.033 %**, and match level
2's calibration (55.303, 55.147) to **0.13 %**. `κ` is a genuine constant of the
port geometry, reproducing across two mesh levels. Using it, **every** mode's
restored balance is 0.99982 to 1.00000 — including all three failing rows.
**The mechanism reproduces at level 3.**

**The flaw is mine, and it is specific: admission does not imply the surrogate
is faithful.** Admission tests the balance of the *reported* energies. For a
mode whose port term is a negligible part of its magnetic side — m6 has
`E_mag/E_elec = 0.99914` — the balance is dominated by `E_mag` and is
insensitive to `E_ind` being 20× wrong. Such a mode passes admission and then
poisons a calibration that assumes faithfulness.

**The fix, to be predeclared before the next run and not applied to this one.**
The true port participation is available exactly from the balance identity with
no field probes at all: `p_true = 1 − (E_mag + E_cap)/(E_elec + E_cap)`.
Calibrate `κ` only on modes where the surrogate is demonstrably faithful,
`|p_reported − p_true| / p_true` small. That is computable per mode, is not
circular — `p_true` never uses the surrogate — and would have excluded m6 and
admitted m1 and m2. The probes' role is then what it should always have been:
confirming that the port-face tangential field accounts for `p_true`, which
here it does to about `2e-4`.

## 3. The admission rule's margin is eroding

| level | separation between admitted and rejected populations |
|---|---|
| 1 | 6.56 decades |
| 2 | 4.47 decades |
| 3 | **3.09 decades** |

At level 3, m6's defect is `8.179e-4` — **82 % of the `1e-3` threshold**. The
rule has been comfortable because its two populations were decades apart; that
is no longer as true, and at the next level the threshold itself may start to
decide cases. Worth watching, and not a reason to move it.

## 4. Cost

| level | DOF | wall clock | cap used | within-order exponent |
|---|---|---|---|---|
| 1 → 2 | 39 832 → 79 944 | 32.4 → 81.2 s | 3.0 % | 1.32 |
| 2 → 3 | 79 944 → 147 372 | 81.2 → 159.1 s | **5.9 %** | **1.10** |

Cost is close to linear in DOF and is not the constraint. Palace's own timers at
level 3: Total 158.8 s, of which `Solve` (the error estimator) 46.7 s,
`LinearSolve` 14.6 s, preconditioner *application* 12.7 s,
`OperatorConstruction` 8.4 s, `Div.-FreeProjection` 7.4 s, `EigenvalueSolve`
4.6 s.

## 5. Where this leaves the extraction

**Compute-limited under the existing rules — and the evidence suggests the limit
is not mesh count.**

The ladder is exhausted at order 1 inside the 250 000-DOF rule: level 3 is
147 372 DOF, and a further halving of `h` would be roughly four times that.
Order 2 is already outside the rule from level 2 on (420 664). So there is no
further rung available under the current allowance.

But more refinement is not obviously the answer either, because the sequence
shows no convergence over a factor of two in `h`. Two features of the model are
candidate causes, both testable and neither established here:

- **Zero-thickness PEC sheets have edges.** The field is singular at a
  conducting edge, and eigenvalue convergence under refinement that is *not*
  graded toward that edge is reduced and can be very slow. This ladder scales
  `h_gap` and `h_far` by a common factor; it does not resolve an edge
  singularity.
- **The lumped port face is 0.02 × 0.04 mm on a 4 mm cell**, spanning few
  elements, and its tangential field is measurably far from uniform — that is
  the whole subject of §2. A mode frequency that depends on that face may not
  converge under uniform refinement.

Both point at the geometry idealisation rather than the element count. The next
step is therefore a **modelling decision, not a larger solve**, and it is the
owner's to make. Nothing here recommends spending more compute on the same
geometry.
