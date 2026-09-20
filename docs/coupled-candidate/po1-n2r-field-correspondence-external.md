# PO1 m1 ↔ N2R m2: the external full-field correspondence

**Status: CORRESPONDENCE ESTABLISHED BY EXTERNAL COMPUTATION.** A package
computed in an environment that could read the two field archives supplies the
overlap this environment could not produce.

**What this supersedes, and only this:** the *transport limitation* recorded in
[`po1-n2r-field-correspondence.md`](po1-n2r-field-correspondence.md) §3 — that
the archives were unreachable, so steps 2–6 did not run and no overlap existed.
An overlap now exists.

**What it does not supersede.** That note's other findings stand unwithdrawn:
the digest verification, the frequency-free exclusion of six of nine N2R modes,
and the statement that port-face scalars can exclude but never select. Commit
`282d216` is not rewritten. **PO1's committed record and its pre-declared
verdict — INCONCLUSIVE FOR MODE IDENTITY — are untouched**: that verdict is the
historical outcome of the three-point classifier declared before the run, and
this is a separate post-hoc analysis by a different method. No coupling, no
`g`, no residue, no `E_C`, no registered-definition change, no Palace run.
Record: `experiments/po1-n2r-correspondence-external/`.

## 1. The result

| quantity | value |
|---|---|
| correspondence | **PO1 m1 ↔ N2R m2** |
| normalised overlap | **0.999927020830** |
| optimal-phase RMS difference | 0.012081101516 |
| optimal complex scale | `−0.417565897 + 0.908566325i` |
| phase | 2.0015947110 rad |

PO1 m1 against the six saved N2R modes:

| N2R m | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| overlap | 0.012036416 | **0.999927021** | 0.000006104 | 0.000010973 | 0.000059979 | 0.000287128 |

Best exceeds second-best (N2R m1) by **83×**.

## 2. Method, as supplied

Both volume exports were checked for exact equality of point coordinates,
tetrahedral connectivity and material attributes. The inner product is the
material-weighted volume integral `⟨A,B⟩ = ∫ εᵣ A* · B dV`, evaluated with the
exact P1 tetrahedral mass formula `V/20·[(ΣA)*·(ΣB) + Σᵢ Aᵢ*·Bᵢ]` on
per-element vertex samples, with `εᵣ = 1.0` in vacuum and `11.45` in substrate.
Overlap is `|⟨A,B⟩|/√(⟨A,A⟩⟨B,B⟩)`; the optimal complex scale
`c = ⟨B,A⟩/⟨B,B⟩` removes the arbitrary global phase and amplitude.

The method is sound. A lowest-order Nédélec field is `a + b × r`, i.e. affine
inside each tetrahedron, so P1 interpolation from four per-element vertex
values reproduces it **exactly** and that mass formula is the exact integral,
not a quadrature. The ε-weighted integral is the mass-matrix inner product of
the generalised eigenproblem, so N2R's eigenvectors are orthogonal under it —
which is what makes §4's bound valid.

## 3. What was verified here, and what was not

Verified (`verify_external.py`, all pass):

- the package's own manifest — all three files;
- the artefact digests, against the digests this repository's Actions API
  reported **before the package existed**: PO1 `a156768c…06ea8dc8`, N2R
  `1ca851c4…9eb8b0e`;
- `εᵣ = 11.45` against the declaration's substrate permittivity, and the
  attribute map `1 → vacuum, 3 → substrate` against `coupled_mesh.TAGS`;
- six saved modes against the solved config's `Solver.Eigenmode.Save = 6`;
- `points = 4 × cells` (337 780 = 4 × 84 445), i.e. **per-element** vertex
  samples rather than node-averaged ones — node averaging would have destroyed
  the normal-component jumps and made the P1 formula an approximation;
- the internal algebra (§4);
- the frequency arithmetic, against this repository's own independent
  computation of the same three numbers, done before the package arrived.

**Not verified here: the field values.** Not one field sample was read in this
environment — the egress policy still denies `*.blob.core.windows.net`. Every
overlap above is the package's. The three mesh-identity booleans are the
package's own output, checked by it and not by this repository. If the exports
were not what they are said to be, or the VTU parse were wrong, nothing here
would catch it.

## 4. Two things the algebra settles

**The RMS is not a second measurement.** `0.012081101516` equals
`√(1 − 0.999927020830²)` to twelve figures. It is an algebraic restatement of
the overlap, and must not be cited as corroborating it. (The prior note flagged
the near-equality of this number with the m1 overlap as suggestive; it is in
fact an identity, and the resemblance to the m1 overlap is a separate
coincidence of magnitude.)

**The unsaved modes cannot compete — and the bound is tighter than claimed.**
N2R converged nine modes and saved six, so m7, m8 and m9 are not in the
archive. The package bounds any mode orthogonal to m2 at
`√(1 − ov²) = 0.012081`. Bessel over the whole saved set is stronger: the six
overlaps satisfy `Σ ov² = 0.999999008496`, leaving only `9.92e-07` of PO1 m1's
squared norm outside the saved span, so **any unsaved mode has overlap
≤ 0.000996** — m2 exceeds that by **1004×**.

That closes the one gap the prior note left. Its frequency-free exclusion left
`{m2, m5, m8}` inseparable; the field data refutes m5 at `6.0e-05`, Bessel
bounds m8 at `≤ 9.96e-04`, and m2 stands alone. **The two analyses agree; the
external one completes the earlier one rather than contradicting it.**

## 5. Frequency comparison, now unconditional in its correspondence

PO1 m1 = **3.885827871 GHz**, identified with N2R m2 by field, not frequency.

| prediction | GHz | signed | absolute | relative |
|---|---|---|---|---|
| conditional `K − Q` (declared removal) | 3.885826970 | **+900.586 Hz** | 900.586 Hz | 2.318e-07 |
| conditional `K − Q/N` (normalised removal) | 3.885825996 | **+1874.896 Hz** | 1874.896 Hz | 4.825e-07 |

PO1 m1 lies above both, nearer the declared removal `K − Q`. N2R m2, the
port-loaded partner, is 3.887370723 GHz, so the port-open shift is
**−1.542852 MHz**.

The correspondence no longer rests on frequency, so this comparison is no
longer conditional *on the pairing*. It remains conditional on everything in §6.

## 6. What this resolves, and what still blocks `g`

**Resolves.** Which N2R mode PO1 m1 is, without frequency as the selector. It
also confirms from field evidence what the scalar records suggested: the five
port-operator-localised N2R modes carry essentially none of PO1 m1
(≤ 2.9e-04), consistent with their being modes *of* the removed term.

**Still blocks `g`, unchanged by this.**

1. **The pair, not the operator.** PO1 changed the assembled operator *and*,
   through the same `Active` flag, the divergence-free projector's constraint
   set. The 900 Hz agreement is against that pair. No control here separates
   them.
2. **`N = fᵀK⁺f/L` is unmeasured**, so `E_C,F1F1` stays **UNAVAILABLE** — and
   without it no coupling can be formed. A frequency agreement does not supply
   a normalisation.
3. **One mesh.** Neither a continuum result nor a bound.
4. **The field evidence is external.** It is verified in provenance and algebra
   here, not reproduced from fields here.

**PO1's own verdict is unchanged.** The three-point classifier declared before
the run returned seven readout-like modes and was recorded INCONCLUSIVE. That
stands as the outcome of the declared rule. This note does not retrofit it —
it records that a different method, applied afterwards, answered the question
the declared rule could not.

## 7. One minimum next action

**Reproduce the overlap from the field archives inside this repository's own
toolchain**, in an environment whose egress policy permits the artefact host —
the same computation, under the repository's manifest and test guards, so the
correspondence rests on reproduced evidence rather than a supplied package.
That changes none of blockers 1–3 above; it retires blocker 4.
