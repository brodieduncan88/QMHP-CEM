# Corrective analysis of the coupled-pilot record

Record `COUPLED-PILOT-CORR-20260916T064943Z` (schema `qmhp-cem.corrective-analysis/0.1.0`, version 1).
Source: `COUPLED-PILOT-20260916T035733Z`, 35 files, manifest `8639bef802d70d19…`, verified intact before and after.

Corrective analysis of an already-executed numerical-method pilot. No solve was launched and no solver output was modified: the source record is read-only evidence and its manifest is verified before and after. NO coupling extraction was performed — no Route A inversion, no g, no charging energy, no capacitance, no circuit parameter. Every geometric value remains an unapproved ENGINEERING-SEED and the 10 % agreement ENGINEERING-RULE is untouched.

## 1. Execution completion

| run | order | halo (mm) | DOF | wall clock (s) | status as executed |
|---|---|---|---|---|---|
| P1 | 2 | 0.08 | 208670 | 2009.7 | COMPLETED |
| P2 | 1 | 0.08 | 39832 | 32.4 | COMPLETED |
| P3 | 2 | 0.12 | 235806 | 2567.5 | COMPLETED |

Unchanged by this analysis. Completion is a statement about the job, not about the physics.

## 2. Algebraic convergence

Backward error against the solver's existing tolerance 1e-06, unchanged here.

| run | modes computed | worst backward error | all converged |
|---|---|---|---|
| P1 | 6 | 7.8660e-11 | yes |
| P2 | 9 | 5.5548e-12 | yes |
| P3 | 8 | 1.1887e-10 | yes |

A small backward error certifies that the eigenpair solves the discrete problem. It says nothing about whether that eigenpair is a resonance.

## 3. Row correspondence

The five per-mode tables are joined on the `m` column, never by row position, and two independent identities that span them are checked:

- `|p_j| == E_ind / (E_elec + E_cap)`  — `port-EPR.csv` against `domain-E.csv`
- `|V_j| == 2*pi*f * L_j * |I_j|`      — `port-V.csv` against `port-I.csv` and `eig.csv`

| run | modes checked | worst participation/energy mismatch | worst port impedance mismatch | ok |
|---|---|---|---|---|
| P1 | 6 | 2.9128e-10 | 2.1414e-10 | yes |
| P2 | 9 | 4.0959e-10 | 2.7099e-10 | yes |
| P3 | 8 | 4.2379e-10 | 2.6806e-10 | yes |

## 4. Mode validity

Admission rule `qmhp-cem.mode-admission/0.1.0`: abs(R - 1) <= 1e-3, with `R = (E_mag + E_ind) / (E_elec + E_cap)`.

Status: **retrospective** for this record, **prospective** for the next confirmatory run. It is a numerical-analysis rule about which rows are resonances. It is not a physical QMHP threshold and it gates no coupling.

### P1

| m | f (GHz) | backward error | R | \|R−1\| | signed p | \|p\| | E_ind/(E_mag+E_ind) | disposition |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.707442 | 2.50e-11 | 9.999947e-01 | 5.347e-06 | +9.979640e-01 | 9.979640e-01 | 9.980e-01 | ADMITTED |
| 2 | 4.184874 | 7.87e-11 | 9.999986e-01 | 1.365e-06 | +1.203472e-03 | 1.203472e-03 | 1.203e-03 | ADMITTED |
| 3 | 8.845860 | 4.48e-11 | 1.518230e-05 | 1.000e+00 | -1.219228e-07 | 1.219228e-07 | 8.031e-03 | REJECTED_ENERGY_BALANCE |
| 4 | 9.271015 | 3.98e-11 | 1.717461e-05 | 1.000e+00 | +1.692211e-07 | 1.692211e-07 | 9.853e-03 | REJECTED_ENERGY_BALANCE |
| 5 | 9.432441 | 4.80e-11 | 1.759729e-05 | 1.000e+00 | +5.901273e-08 | 5.901273e-08 | 3.354e-03 | REJECTED_ENERGY_BALANCE |
| 6 | 9.666431 | 4.94e-11 | 1.879541e-05 | 1.000e+00 | +6.986449e-08 | 6.986449e-08 | 3.717e-03 | REJECTED_ENERGY_BALANCE |

Admitted: [1, 2] in the declared window [0.5, 9.0] GHz. The admitted and rejected populations are separated by 5.27 decades in |R−1|.

### P2

| m | f (GHz) | backward error | R | \|R−1\| | signed p | \|p\| | E_ind/(E_mag+E_ind) | disposition |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.158333 | 1.26e-17 | 1.000000e+00 | 4.959e-09 | +9.985099e-01 | 9.985099e-01 | 9.985e-01 | ADMITTED |
| 2 | 3.693189 | 3.41e-17 | 1.000000e+00 | 1.769e-08 | -9.336026e-04 | 9.336026e-04 | 9.336e-04 | ADMITTED |
| 3 | 6.699425 | 3.79e-12 | 5.526005e-05 | 9.999e-01 | +3.410620e-09 | 3.410620e-09 | 6.172e-05 | REJECTED_ENERGY_BALANCE |
| 4 | 7.044198 | 8.60e-14 | 4.670657e-05 | 1.000e+00 | -1.386335e-11 | 1.386335e-11 | 2.968e-07 | REJECTED_ENERGY_BALANCE |
| 5 | 7.300318 | 6.07e-14 | 5.037223e-05 | 9.999e-01 | -3.093840e-11 | 3.093840e-11 | 6.142e-07 | REJECTED_ENERGY_BALANCE |
| 6 | 7.694394 | 2.74e-13 | 5.318054e-05 | 9.999e-01 | -3.709362e-11 | 3.709362e-11 | 6.975e-07 | REJECTED_ENERGY_BALANCE |
| 7 | 8.184160 | 6.16e-14 | 6.197800e-05 | 9.999e-01 | +3.378874e-11 | 3.378874e-11 | 5.452e-07 | REJECTED_ENERGY_BALANCE |
| 8 | 8.469361 | 1.78e-13 | 7.444890e-05 | 9.999e-01 | +2.570868e-11 | 2.570868e-11 | 3.453e-07 | REJECTED_ENERGY_BALANCE |
| 9 | 9.961037 | 5.55e-12 | 9.999997e-01 | 2.783e-07 | -1.893574e-05 | 1.893574e-05 | 1.894e-05 | ADMITTED |

Admitted: [1, 2] in the declared window [0.5, 9.0] GHz, [9] outside it. The admitted and rejected populations are separated by 6.56 decades in |R−1|.

### P3

| m | f (GHz) | backward error | R | \|R−1\| | signed p | \|p\| | E_ind/(E_mag+E_ind) | disposition |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.784106 | 2.74e-11 | 9.999825e-01 | 1.747e-05 | +9.982990e-01 | 9.982990e-01 | 9.983e-01 | ADMITTED |
| 2 | 4.236676 | 1.19e-10 | 9.999988e-01 | 1.194e-06 | +9.093879e-04 | 9.093879e-04 | 9.094e-04 | ADMITTED |
| 3 | 8.296061 | 7.04e-11 | 1.673977e-05 | 1.000e+00 | +1.882190e-07 | 1.882190e-07 | 1.124e-02 | REJECTED_ENERGY_BALANCE |
| 4 | 8.811356 | 7.05e-11 | 1.921419e-05 | 1.000e+00 | -3.539929e-07 | 3.539929e-07 | 1.842e-02 | REJECTED_ENERGY_BALANCE |
| 5 | 9.171484 | 8.36e-11 | 2.060246e-05 | 1.000e+00 | +1.944971e-07 | 1.944971e-07 | 9.440e-03 | REJECTED_ENERGY_BALANCE |
| 6 | 9.253443 | 1.14e-10 | 2.069674e-05 | 1.000e+00 | -1.084477e-07 | 1.084477e-07 | 5.240e-03 | REJECTED_ENERGY_BALANCE |
| 7 | 9.464060 | 6.27e-11 | 3.866091e-05 | 1.000e+00 | +3.628769e-06 | 3.628769e-06 | 9.386e-02 | REJECTED_ENERGY_BALANCE |
| 8 | 9.667001 | 7.34e-11 | 5.970025e-05 | 9.999e-01 | -7.776677e-06 | 7.776677e-06 | 1.303e-01 | REJECTED_ENERGY_BALANCE |

Admitted: [1, 2] in the declared window [0.5, 9.0] GHz. The admitted and rejected populations are separated by 4.76 decades in |R−1|.

## 5. Mode matching

### P1 vs P3 — MATCHED

the frequency and |p| orderings agree and every pair is inside the separation guard

| pair | f_a (GHz) | f_b (GHz) | Δf | Δ\|p\| | shift (GHz) | separation limit (GHz) |
|---|---|---|---|---|---|---|
| m1↔m1 | 1.707442 | 1.784106 | 4.4900e-02 | 3.3557e-04 | 0.0767 | 1.2263 |
| m2↔m2 | 4.184874 | 4.236676 | 1.2379e-02 | 2.4436e-01 | 0.0518 | 1.2263 |

Against the unchanged frozen criteria (Δ\|p\| ≤ 1e-02, Δf ≤ 1e-04):

| pair | Δf | frequency | Δ\|p\| | participation | criterion subject |
|---|---|---|---|---|---|
| m1↔m1 | 4.4900e-02 | FAIL | 3.3557e-04 | PASS |  |
| m2↔m2 | 1.2379e-02 | FAIL | 2.4436e-01 | FAIL | yes |

### P1 vs P2 — MATCHED

the frequency and |p| orderings agree and every pair is inside the separation guard

| pair | f_a (GHz) | f_b (GHz) | Δf | Δ\|p\| | shift (GHz) | separation limit (GHz) |
|---|---|---|---|---|---|---|
| m1↔m1 | 1.707442 | 1.158333 | 3.2160e-01 | 5.4673e-04 | 0.5491 | 1.2387 |
| m2↔m2 | 4.184874 | 3.693189 | 1.1749e-01 | 2.2424e-01 | 0.4917 | 1.2387 |

Against the unchanged frozen criteria (Δ\|p\| ≤ 1e-02, Δf ≤ 1e-04):

| pair | Δf | frequency | Δ\|p\| | participation | criterion subject |
|---|---|---|---|---|---|
| m1↔m1 | 3.2160e-01 | FAIL | 5.4673e-04 | PASS |  |
| m2↔m2 | 1.1749e-01 | FAIL | 2.2424e-01 | FAIL | yes |

Δ\|p\| uses **magnitudes**: `abs(|p_a| − |p_b|) / max(|p_a|, |p_b|)`. The signed participation and the complex port current are preserved unchanged in the machine-readable record; only the comparison uses magnitudes, because Palace's sign is `sign(Re I)` and the phase of a single port phasor is not invariant under the eigenvector's arbitrary global scale.

## 6. Diagnostic findings

16 of 23 computed rows fail the reported energy identity. The distribution is bimodal: the worst admitted defect is 1.747e-05 and the best rejected one is 9.999e-01, so the admitted set is unchanged for any cutoff between them.

**Cause: SUPPORTED-NOT-PROVEN.** Palace's E_ind is not the port stiffness quadratic form but the rank-one surrogate |V|^2/(2 w^2 L) built from the port's AREA-AVERAGED, +Y-PROJECTED voltage, which by Cauchy-Schwarz is a LOWER BOUND on the port energy integral (1/Ls)|E_t|^2 dS. A failing row is therefore either (1) an algebraically spurious Ritz vector whose reported eigenvalue is meaningless, or (2) a genuine eigenpair of (K, M) whose stiffness energy sits almost entirely in the lumped port's Robin term, in a tangential field that is non-uniform or transverse to +Y.

(2) is the better supported of the two, and is still not proven. The evidence:

- Palace builds the auxiliary-boundary marker for its divergence-free projector as the union of the Dirichlet, farfield, conductivity, impedance and LUMPED-PORT markers (palace/models/spaceoperator.cpp), and those become the essential true dofs of the H1 spaces the projector uses. Its potential is pinned to zero on the inductive port face, so a discrete gradient whose potential varies ON that face lies outside the projector's range. Palace's own source records the residue in a commented-out line beside it: 'Mark all boundaries ... As tested, this does not eliminate all DC modes!'
- The lumped inductance enters the STIFFNESS as a Robin surface term (1/Ls) integral |E_t|^2 dS, so such a gradient has strictly positive stiffness energy and a finite w^2. The objection that a gradient mode must sit at w = 0 therefore does not apply.
- The failing rows form one family: (E_mag + E_ind) * f^2, proportional to the measured stiffness energy of the unit-normalised field, spans a factor of only 4.84 across all of them, over three discretisations, while the admitted rows span a factor of 74 and sit orders of magnitude higher.
- A residual bound points the same way without closing it: from |x^H r| <= ||x|| ||r|| with r = Kx - mu Mx, and R near zero, the failing rows' mass-matrix Rayleigh quotient is bounded by Err_abs/mu, so these must be strongly localised vectors - which is what explanation (2) predicts and explanation (1) does not naturally produce. Whether the bound is outright impossible depends on ||M||, which this record does not carry, so this supports (2) without excluding (1).

The reported participation p = E_ind/(E_elec + E_cap) is computed from the SAME surrogate, so under either explanation the p of a failing row is not a quantity two independent solves may be compared on. That is what the admission rule screens.

Mode budget: At order 1 three admitted modes were found below 10 GHz; at order 2 on the byte-identical mesh six converged rows yielded only two, because four failing rows occupied slots 3-6. The family dilutes the requested mode count, so eigenmodes_requested should be chosen from the admitted yield.

Withdrawn: An earlier note called these rows 'null-space / gradient artefacts that the divergence-free projection did not remove'. That asserted a mechanism the evidence does not carry and is withdrawn.

**Backward error.** Palace normalises the reported backward error by the GLOBAL operator norms. The record shows it directly: within each run Error(Abs.)/Error(Bkwd.) is constant to about five parts in a million, so the printed backward error is the true residual divided by a number of order 1e5. Measured per run: P1 3.0124e+05–3.0124e+05, P2 1.5822e+05–1.5822e+05, P3 2.5482e+05–2.5483e+05. Consequence: a small printed backward error is a weaker certificate than its size suggests, and certifies the eigenpair rather than its physics.

| missing diagnostic | what it would show | why it is absent |
|---|---|---|
| per-mode port stiffness integral (1/Ls)|E_t|^2 dS / (2 w^2) | whether the reported E_ind understates the true port energy | Palace v0.13.0 never writes it |
| the saved mode fields | E_t on the port and div(eps E) in the volume, directly | all three configs set Solver.Eigenmode.Save = 0 |
| per-mode ||x||_2, x^H K x, or an M-norm-relative residual | the Rayleigh quotient independent of the surrogate | Palace v0.13.0 emits none of them |

**Participation sign.** The sign of p is sign(Re I), and Palace computes I = V/(i w L) exactly, so arg(I) = arg(V) - 90 degrees identically and V/I is the constant i w L. The sign therefore tracks the eigenvector's arbitrary overall complex phase. The pinned Palace tree contains no phase-fixing step: its only post-solve normalisation is multiplication by a real, non-negative scalar. Conclusion: The sign is a solver gauge choice, not a physical current direction.

Withdrawn: An earlier note said the port current direction is not stable under discretisation. That described a gauge artefact as physics and is withdrawn.

Missing diagnostic: A gauge-invariant SIGNED observable would need a second inductive lumped port in the same solve, so that arg(I_1) - arg(I_2) could be compared between runs, or the saved mode fields. Neither exists in this record.

**Reproducibility claim — QUALIFIED - not supported at that strength.** Supported: The eigenfrequencies and backward errors printed in attempt 1's job log agree with the committed record to every digit the log prints, for all 6, 9 and 8 modes of P1, P2 and P3. That is agreement to the precision of the log. Not supported: A raw-file or hash comparison. Attempt 1's postpro files were never committed - its commit-back step failed - and its uploaded artifact was not retrievable here. Missing: attempt 1's postpro/ files, or their sha256 digests.

## 7. Halo disposition

**NOT-A-HALO-VERDICT**

the frequency check failed, which that section predeclared is not a halo verdict at all: a frequency moving that much between two size fields at the same refinement level indicates the level-1 mesh is too coarse for this geometry, or the model is wrong. The halo question is not answerable from this record.

## 8. What this corrects

The source record reports Δp = 1.6478e+00, Δf = 6.2153e-02 and the verdict `NOT-A-HALO-VERDICT`. Two things produced those numbers:

- Mode selection: the source driver defined 'the readout-like mode' as the in-window row with the smallest |p|. A row whose reported energies do not balance has a small |p| for that reason, so the rule selected the least trustworthy row in the window, and selected a different one in each run.
- Comparison convention: the participation difference was taken on SIGNED values. Palace's sign is sign(Re I) and is not invariant under the eigenvector's global phase, so a sign difference between two independent solves inflates the difference without measuring anything.

The rows that rule selected, with their dispositions under the corrected rule:

| run | mode | f (GHz) | \|p\| | disposition |
|---|---|---|---|---|
| P1 | 3 | 8.845860 | 1.2192e-07 | REJECTED_ENERGY_BALANCE |
| P2 | 4 | 7.044198 | 1.3863e-11 | REJECTED_ENERGY_BALANCE |
| P3 | 3 | 8.296061 | 1.8822e-07 | REJECTED_ENERGY_BALANCE |

The source record's own halo_verdict is preserved unchanged in that record. It is restated here beside the corrected comparison so the difference is visible, not hidden. The verdict is the same; the numbers behind it are not.

