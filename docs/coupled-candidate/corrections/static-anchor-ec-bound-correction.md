# Correction record: the E_C,F1F1 lower-bound statements of the static-anchor record

**Status: PREPARED FOR HUMAN REVIEW. NOT COMMITTED. NOT A REGISTERED DECISION.**

- Prepared 2026-09-23, under CLAUDE.md §1 (corrections are new records) and §14 (report contradictions).
- This record changes no file. Every corrected text stays byte-unchanged. The sha256 values in §6 are the measured digests at commit `411a910ff5ce8ab2e6ead75afde01d0817662940`; for these files they are identical to `3d14c095e7ac4b8971f5476bd9a9f315ba7df2e1`.
- No computation was run for this record, apart from the arithmetic K/C in §4. That arithmetic uses capacitance values already in committed records.
- It makes no registered-definition decision and adopts no reading of the registered operator. E_C,F1F1 and g stay **UNAVAILABLE**.

## 1. The claims corrected

The committed record states, under assumption A-R alone, that its capacitance gives a lower bound on E_C,F1F1, and it states that bound numerically. Both statements are withdrawn as stated. Each excerpt below is verbatim.

**SA-1.** `docs/coupled-candidate/static-anchor-hypothesis.md`, lines 126–134 (§5, "How it relates to the registered charging energy"):

```text
    e²/(2 C_h)  ≤  e²/(2 C_FF)  ≤  e²(C⁻¹)_FF/2 = E_C,F1F1

- The first inequality is the Dirichlet principle.
- The middle identification (`C = C_FF`) rests on **assumption A-R**: the readout is one
  connected, DC-grounded conductor on this mesh, standing in for node R1 held at zero.
- The last inequality is the Schur complement. Its gap, `1/(1 − k²)`, is **not measured**,
  and must not be taken from the conditional Route A coupling.

So the test gives a **lower bound** on `E_C,F1F1` under A-R, never `E_C,F1F1` itself.
```

**SA-2.** Same file, lines 274–277 (§8, "What is established regardless of the verdict", item 4):

```text
4. **Derived arithmetic (class B).** Under assumption A-R, `e²/(2 C_h)` gives a lower bound
   on `E_C,F1F1`: `E_C,F1F1/h ≥ 235.6 MHz` from level 1 (169.4 MHz from level 0). This is a
   bound, not a value. `E_C,F1F1` and `g` stay **UNAVAILABLE**, and nothing here is combined
   with any Route A output.
```

**SA-3.** `experiments/static-anchor-hypothesis/predeclaration.json`, lines 49–50 (`relation_to_registered_E_C.chain` and `.consequence`), part of the frozen pre-declaration:

```text
"chain": "e^2 / (2 C_h)  <=  e^2 / (2 C_FF)  <=  e^2 (C^-1)_FF / 2 = E_C,F1F1. The first inequality is the Dirichlet principle (C_h >= C for the discrete minimum; rigorous for this model). The equality C = C_FF needs assumption A-R. The second inequality is the Schur complement of a positive-definite 2 x 2 Maxwell matrix (rigorous algebra); equality only if the island-readout mutual capacitance vanishes.",
"consequence": "The test yields a lower bound on e^2/(2 C_FF) and, under A-R, on E_C,F1F1. It does NOT yield E_C,F1F1: the gap is 1/(1 - k^2) with k^2 = C_FR^2 / (C_FF C_RR), which this test does not measure and which must NOT be taken from the conditional Route A coupling. E_C,F1F1 stays UNAVAILABLE."
```

**Related occurrences.** The same chain is repeated in the withdrawn, never-executed paired test:

- **SB-1.** `experiments/static-band-pairing/predeclaration.json`, line 79. Among the descriptive outputs: `e^2/(2 C_2) as a lower bound on E_C,F1F1 under assumption A-R`. That test was never run, and its driver does not compute this output (`experiments/static-band-pairing/review/red_team_findings.json:400`).
- **SB-2.** Same file, line 81: `Unchanged from the static-anchor pre-declaration: e^2/(2 C_h) <= e^2/(2 C_FF) <= E_C,F1F1 under A-R, with the Schur gap 1/(1 - k^2) unmeasured.`

A repository search (`grep` for `235.6`, `169.4`, `A-R` and `lower bound on E_C`, excluding the committed E1 exploratory-claims correction record) found no other occurrence.

`docs/coupled-candidate/static-band-pairing.md:68` says the capacitance bound is "not a bound on `C_FF` without assumption A-R". It states no E_C bound, so it is not withdrawn here. Its A-R qualification is, however, subject to the same reading dependence as §2(a).

## 2. What is wrong

The first inequality, e²/(2C_h) ≤ e²/(2C), is correct: C_h ≥ C by the Dirichlet principle, for the discrete minimum of this model. The defects are in the steps after it, and in the conditions attached to the conclusion. A-R is necessary for them, but it is not sufficient.

**(a) The Schur step is algebra about a lumped two-node matrix, not about the registered invariant.**

- SA-3 calls the second inequality "the Schur complement of a positive-definite 2 x 2 Maxwell matrix (rigorous algebra)". SA-1 cites the Schur complement in the same way.
- That algebra requires R1 to be a conductor with its own electrostatic potential.
- In the registered definition, R1 is "the single-mode (fundamental) representation of a distributed resonator at its coupling node" (`coupling-definition.md:78-80`; E_C = (e²/2)C⁻¹ with C the Maxwell matrix reduced to the declared nodes, `:46-63`). The candidate declares that resonator as a "quarter-wave CPW resonator, open end coupled to F1, shorted end to ground", with a "galvanic short at the meander end" (`config/coupled/v2a_five_node_candidate.json:561, 483`; `shorted_end: ground`, `:404`).
- At DC the R1 metal is part of ground. R1 is therefore a modal coordinate, not an electrostatic node, and the registered wording does not fix how it enters (C⁻¹)_FF.
- The candidate readings differ:
  - **M1:** the declared port model's DC limit C_DC plus the exact R1 pole and residue of that one port model;
  - **M2:** the high-frequency limit C_∞;
  - **M3:** a band fit.
- Adopting any reading is a registered-definition decision under CLAUDE.md §3. None has been made.
- A-R ("the readout is one connected, DC-grounded conductor … standing in for node R1 held at zero") identifies the static capacitance with the lumped entry C_FF. It does not select a reading.

**(b) Direction of E_C,F1F1 relative to the static capacitance under each reading** (DERIVED; see §5 for the basis).

The port admittance of a declared lossless port model has the Foster form Y_FF(s) = s·C_∞ + Σ_n a_n·s/(s² + ω_n²), with every a_n ≥ 0. Its DC limit is C_DC = C_∞ + Σ_n a_n/ω_n².

- **M1:** 1/(C⁻¹)_FF = C_DC − ΔC_R1, with ΔC_R1 = a_R1/ω_R1² ≥ 0. In the lumped model this is C_FF − C_FR²/C_RR, which is the SA-1/SA-3 Schur relation.
- **M2:** 1/(C⁻¹)_FF = C_∞ ≤ C_DC.
- **M3, or a Route B band fit:** 1/(C⁻¹)_FF is not constrained to lie below C_DC.

Hence E_C,F1F1 ≥ e²/(2C_DC) holds under M1 or M2 and fails under M3. The stated chain holds only after a decision adopting M1 or M2.

**(c) The upper bound must match the declared port model.**

- C_DC is the DC limit of the declared port model:
  - C, with the port face open, for the transparent-face model (PA);
  - C′, with the port-face potential held linear, for Palace's sheet port (PB).
- C_h is the C quantity. `static-refinement-study.md:154` says "`C_h`: the island at 1 and every other conductor at 0. This is the static-anchor quantity". Its levels 0 and 1 "reproduce the executed static-anchor record bit for bit" (`:19`).
- C′ ≥ C, and C_h does not bound C′ from above. At level 1, C′ = 82.26025937045856 fF, which exceeds C = 82.2021777287097 fF (`results/STATIC-REFINEMENT-STUDY-20260923T062048Z/summary.json`, `C_fF[1]` and `Cprime_fF[1]`).
- Under PB, the level-1 figure from C_h is therefore not established.

**(d) C_J is part of C_FF.**

- With a junction or other non-geometric capacitance C_J on F1, the relations of (b) hold with C_DC + C_J in place of C_DC. C_J enters C_FF only, and ΔC_R1 = C_FR²/C_RR is unchanged. So the bound is e²/(2(C_up + C_J)).
- The 235.6 MHz and 169.4 MHz figures take C_J = 0. That is the current engineering seed, `F1.junction_intrinsic_capacitance` `C_fF: 0.0`, `approved: false` (`config/coupled/v2a_five_node_candidate.json:537-545`; also `C_J_F1`, `:869-875`), and the record did not state it.

**(e) Basis of C_h as an upper bound.**

- C ≤ C_h is exact for the discrete minimum of the meshed model.
- The computed C_h carries solve and assembly round-off. The later study quantifies this for the same operator: "rigorous relative to the assembled operator, up to ρ", with an uncertified assembly-term estimate beside it (`static-refinement-study.md:50-54, 222-227`).
- The effect on the MHz digits is negligible, but it belongs to the statement's basis.

**(f) Model scope.** The bound concerns the meshed model: zero-thickness PEC sheets, ε_r = 11.45 (an unapproved seed), and the 4 mm cell with grounded walls. It is not a statement about the device.

SA-2 inherits (a)–(f). It is presented as unconditional apart from A-R.

## 3. Status of each item

| item | status |
|---|---|
| SA-1 | **WITHDRAWN as stated.** The first inequality stands. The second inequality and the conclusion hold only under the conditions of §4. |
| SA-2 | **WITHDRAWN as stated.** Replaced by the conditional statement of §4. |
| SA-3 | **WITHDRAWN as stated**, as an interpretation. The frozen pre-declaration's question, configuration, integrity checks and outcome table are unaffected. So are the executed record's measured values and its verdict, UNRESOLVED. |
| SB-1, SB-2 | **WITHDRAWN as stated** (withdrawn test; never executed; the output was never computed). |

"Withdrawn" means the item may not be used as, or cited for, a lower bound on E_C,F1F1 without the conditions of §4.

## 4. Corrected statement (derived arithmetic, class B; conditional)

**Only after** a registered-definition decision (CLAUDE.md §3) that adopts reading M1 or M2 and declares the port model and C_J:

    E_C,F1F1/h ≥ K / (C_up + C_J),   K := e²/(2h) = 19.370229324659128 fF·GHz (float64 of the exact SI value)

Here C_up is an upper bound on the declared port model's C_DC:

- **under PA**, C_h (class C);
- **under PB**, C′_h (class C′).

With C_J = 0 (the unapproved seed), the recorded levels give:

| level | PA: C_h (fF) | PA bound | PB: C′_h (fF) | PB bound |
|---|---|---|---|---|
| 0 | 114.33875970637405 | 169.41 MHz | 114.41426753772744 | 169.30 MHz |
| 1 | 82.2021777287097 | 235.64 MHz | 82.26025937045856 | 235.47 MHz |

Sources: `results/STATIC-ANCHOR-TEST-20260922T192243Z/summary.json` (`C0_fF`, `C1_fF`) and `results/STATIC-REFINEMENT-STUDY-20260923T062048Z/summary.json` (`C_fF`, `Cprime_fF`). The digits are truncated for display.

Each figure holds on the meshed model, up to the round-off basis of §2(e). Under M3, or a Route B band fit, no lower bound on E_C,F1F1 follows from these capacitances.

A lower bound on a capacitance bounds E_C,F1F1 under no reading. Nothing here gives an upper bound on E_C,F1F1.

The later level-2 Dirichlet bounds (`static-refinement-study.md:50`) are tighter, and they carry exactly the same conditions. This record states no figure from them.

## 5. Basis of the corrected analysis

- **Readings and directions (§2(a)–(b)).** DERIVED during the E1 pre-declaration work: revision 6 §2.3–§2.4 and revision 7 §2 items 3–4 (uncommitted session material; sha256 `bc59ac5bc252b314a43431315f78a86cc340c00bb913607ddb31d67252ac677c` and `e62488c8aeb1b2892b3e814697663f4f093ac90b0be86f0e4d9ffb1a8192cdf5`).
  - Reviewed adversarially in the revision-6 and revision-7 physics/mathematics reviews.
  - The revision-7 bounds reviewer checked the M1 and M2 directions on 40,000 random synthetic Foster admittances and found 0 violations of 1/(C⁻¹)_FF ≤ C_DC under M1 and C_∞ ≤ C_DC.
  - The Foster-form argument of §2(b) is included here so that this record does not depend on uncommitted files for its logic.
- **Port-model split (§2(c)).** SOURCE: `static-refinement-study.md:19, 24-28, 154-155`, and the study's summary.json.
- **C_J (§2(d)).** SOURCE: `config/coupled/v2a_five_node_candidate.json:537-545, 869-875`.
- **Relation to the E1 exploratory-claims correction record.** That record (`docs/coupled-candidate/corrections/e1-exploratory-claims-correction.md`, commit `411a910`) withdraws session statements of the same form, under its reasons B and Binc. Its §5, "Out of scope, reported for human decision", names this document's lines 126, 131 and 274–275 and says that correcting them needs a separate correction record. This record is that separate correction.

## 6. Files and digests (measured at `411a910`)

| file | sha256 | last changed in |
|---|---|---|
| `docs/coupled-candidate/static-anchor-hypothesis.md` | `c57f1ac4d11d372e0778c545bb851b6f7d6d158acd1648ae8f229a6cb04610ef` | `72aec54` |
| `experiments/static-anchor-hypothesis/predeclaration.json` | `6f31470a38a58cfbe33eb7bee61c6ec06eeea428bdfbd943b39e52e3e4868f29` | `16937ad` |
| `experiments/static-band-pairing/predeclaration.json` | `3f588d2e6bca206aa509d7a40585b2c5421f94944a2c2938b262b2e7c4ce80d5` | `72aec54` |
| `results/STATIC-ANCHOR-TEST-20260922T192243Z/summary.json` (read only) | `93db9bc22003c137adfeb8399445a9f6958e4ea4bd6c882b46262338167381d6` | — |
| `docs/coupled-candidate/coupling-definition.md` (cited) | `143091c596b41c46baeed372ba6afdd6eb524c3c9d87e8af57bb9de19cc6b5d1` | — |
| `docs/coupled-candidate/static-refinement-study.md` (cited) | `f9ab52bb9f9c7764c8bfb66462c09de67d53e4a9e8bb10cbde29049a641174a1` | — |
| `config/coupled/v2a_five_node_candidate.json` (cited) | `6d1e21a75f44ed67027f6b69dcda93ee667d396a78737b223022cc78e7617dcf` | — |

The executed record, `results/STATIC-ANCHOR-TEST-20260922T192243Z/`, reports no E_C value. Its `summary.json` field `not_reported` names E_C,F1F1. Nothing in it is corrected.

## 7. What this record does not establish

- Any value of, or bound on, E_C,F1F1 or g. Both stay UNAVAILABLE.
- Any reading (M1, M2 or M3), any port model or any C_J. Each is a human decision under CLAUDE.md §3.
- Suitability or deviation from the registered 0.60 GHz. No tolerance is adopted.
- Anything about the device, rather than the meshed model.
- Any change to the static-anchor verdict (UNRESOLVED), to Route A, or to the first-moment diagnostic.
