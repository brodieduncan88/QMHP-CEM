# Definition decision: R1 as the readout normal mode of the linear environment

**Status:** assessment and draft only. The registered target is **not changed
by this document**; a draft amendment is given in §7 for approval, labelled
as a conceptual clarification forced by the multimode identifiability analysis
and the Faraday result, not as a numerical retuning. No frozen Master value,
no threshold, no guard and no rule changes. No Palace run, no Route B, no
real-data extraction; nothing here produces a coupling value.

Inputs: `coupling-definition.md`, `extraction-routes.md`,
`route-a-identifiability.md`, `synthetic-three-mode-identifiability.md`, the
external readout-field diagnostic (`readout-surface-difference-review.md`) and
the external Faraday diagnostic
(`experiments/readout-voltage-functional/external-faraday/`).

## 1. The Faraday result, and the two corrections, recorded

The external evaluation reproduced `V₊ − V₋` of the two pre-declared readout
surfaces by Faraday's law on the same exported fields: relative complex
disagreement 9.53e-7 (N1R m1), 8.57e-6 (N1R m2), 8.23e-7 (N2R m1), 1.14e-5
(N2R m2). Two corrections to the pre-declared test were needed and are
verified here without the archives (`external-faraday/review.json`):

1. **Orientation.** The declared loop is clockwise viewed from +z (signed
   area −0.0585 mm² at `x = −0.45`), so its Stokes normal is −z and, with
   Palace's `∇ × E = −iωB` and the exported +z `B_z`, `V₊ − V₋ = +iω Φ_z`.
   The pre-declaration's `−iω` assumed a +z normal.
2. **Spanning surface.** `A_west` (0.0284 mm², recomputed from the registered
   geometry) contains the `P_F1` port face, attribute 10, a boundary element
   of the input mesh; restricting the flux to the interface attribute 25, as
   the review note proposed, omits 4.0–5.5 % of the weighted flux.

**Conclusion supported.** The 5–7 mV difference between the +Y and −Y
pad-to-ground voltages is the magnetic-flux/path term of the stored discrete
solution to the precision of the Float32 export. **Not concluded:** that
either path is wrong; that the 13–14 % `r₁₂` difference is a coupling error;
continuum convergence; or that the flux term belongs to any particular lumped
inductive element.

What it decides, for the definition: a voltage taken along a path across
the coupling pad is a path-dependent functional of the field at 15 % of its
own value in the fluxonium-like mode. The registered Hamiltonian is a
capacitive network with every inductive branch to ground; it has no
coordinate for which such a path term is a property of a node. A local pad
path voltage therefore cannot be *the* readout node coordinate without an
added path/tree/gauge convention that the registered definition does not
contain.

## 2. Is the Master's `a` a normal-mode oscillator?

The Master dressed system is `H = diag(w_i) + w_r a†a + g n (a + a†)`
(`models/dressed_system.py`, `master/qmhp_v158f_requirements.yaml`
`dressed_system`): a single harmonic oscillator of frequency `w_r`, coupled to
the fluxonium charge `n` and to nothing else. `w_r` is the "bare" readout
frequency, i.e. the oscillator's frequency with the coupling term switched
off while its capacitive loading is kept.

For a linear environment with several modes, the exact charge-coupled form
is `H_F + Σ_k ω_k a_k†a_k + Σ_k g_k n (a_k + a_k†)` **in the basis of the
environment's normal modes** with the F1 node's charge frozen (F1 open):
`ω_k² = β_k`, the eigenvalues of the environment block `B` of
`S = L^{−1/2} C^{−1} L^{−1/2}`, and `g_k ∝ c̃_k`, the components of the
coupling vector on `B`'s eigenvectors (`synthetic-three-mode-identifiability.md`
§3). In any other coordinate basis of the environment there are additional
`a_R a_X†`-type cross terms that the Master form does not have. The Master's
`a` is therefore the readout **normal mode** of that basis, and the
single-mode Master Hamiltonian is its truncation to `k = R1`. In the
two-node circuit `{F1, R1}` the environment block is 1 × 1, so the normal
mode is the node `R1` itself and `w_r = √((C⁻¹)_R1R1/L_R1)` exactly as
registered. **Yes:** `a` corresponds physically to the environment normal
mode, and the registered §3 algebra is its two-node special case.

## 3. Do Route A and Route B then estimate the same path-independent object?

Both routes observe the linear environment **only at the F1 element site**,
the one place with a declared lumped element and a declared reference plane.

- **Route A** (eigenmodes with `L_F1` attached): `G_F(z) = Σ_m p_mF/(z − f_m²)`
  and `1/G_F(z) = z − a − Σ_k c̃_k²/(z − β_k)`. The zeros of `G_F` are the
  environment normal-mode frequencies with F1 open; the residues are the
  squared couplings; `a = Σ_m p_mF f_m²` is `(C⁻¹)_F1F1/L_F1`. Exact on
  synthetic data to 1e-12 (`synthetic-three-mode-identifiability.md` §3).
- **Route B** (driven response with `L_F1` absent): the poles of
  `Z_F1F1(ω)`, the impedance seen at the open F1 port, are the same
  F1-open environment modes `β_k`, and the residues of `Z_F1F1` at those poles
  are the same couplings; this is the Nigg/black-box form that
  `extraction-routes.md` §3.3 already names.

Neither involves a readout-side path, surface or probe; both are defined at
the port terminal pair. **Yes:** under the normal-mode definition the routes
estimate the same, path-independent object, `{a, β_R1, c̃_R1²}` →
`{E_C,F1F1, f_R1, g_F1R1}`. One wording in §3.3 has to be corrected for this
to hold literally: it calls the target "the pole of `Y_FF`", which is the
F1-**shorted** resonance and a different number; the pole of `Z_FF` (the
zero of `Y_FF`) is the F1-open mode `β_R1` that matches Route A's `b` and
the registered `√(8 E_C,RR E_L,R)`.

## 4. Is the `Z_FF` pole/residue description already the same target?

Yes, up to that wording. `route-a-identifiability.md` §4 derives Route A's
`b = ω_R² = (C⁻¹)_RR/L_R`, the F1-open (charge-frozen) readout frequency;
`extraction-routes.md` §3.3 says Route B "estimates the same invariants" and
cites `Z_FF(ω)` poles and residues, then in the same paragraph names the
pole of `Y_FF`. With the `Y`/`Z` wording fixed, the Route B description is
the normal-mode target, and the multimode Route A identification of §3 is
its eigenmode-side counterpart.

## 5. Selecting the readout fundamental among several environment modes

A pre-declared **mode-correspondence rule**, using field information, not
frequency alone:

1. **Eigenmode classification (existing rule).** Every computed eigenmode `m`
   in the band is classified by `numerical-plan.md` §2: `p_mF` and the probe
   polarisation fractions over the pad, the resonator open end and the
   resonator mid-length; "readout-like" if the resonator-probe energy
   dominates and `p_mF < 0.5`; "fluxonium-like" if `p_mF ≥ 0.5`; otherwise
   hidden and reported, with the existing INCOMPLETE criteria (a hidden mode
   within 1.0 GHz of the readout mode or with `p_mF ≥ 0.05`).
2. **Zero ownership (new, participation-based).** The zeros `β_k` of `G_F`
   interlace the eigenfrequencies (a guard: if they do not, the data are not
   those of a lossless linear environment). Each zero's residue is
   `c̃_k² = 1/Σ_m p_mF/(β_k − f_m²)²`; the zero is **owned** by the eigenmode
   whose term dominates that sum, i.e. the environment mode to which that
   eigenmode connects continuously as the F1 coupling is switched off.
   `β_R1` is the zero owned by the unique readout-like eigenmode. On the
   synthetic reference circuit the dominance ratio is about 1.2e3 for the
   readout zero and about 1.2e3 for the third-mode zero, so the assignment is
   unambiguous; a dominance ratio below the existing resolution ratio 10
   (`solvers/palace/verification.py`) is declared INCOMPLETE, not resolved by
   frequency.
3. **Two-mode limit.** With two modes there is one zero, owned trivially:
   the rule reduces to `invert_two_node`.

Frequency proximity enters only through the participation-weighted terms of
the residue sum, never as a stand-alone selector; the readout-like label is
fixed by the probe fields.

## 6. Does the exact two-mode limit reproduce `invert_two_node` and the Master convention?

Exactly. With one environment coordinate, `B = [b]`, `c = [k]`, so
`β_R1 = b`, `c̃_R1 = k` and `g_F1R1 = coupling_GHz(k, b, L_F)`: the same
closed form, the same `n_zpf,R = (E_L,R/32 E_C,RR)^{1/4}` convention with
`L_R` cancelling, the same `|g|`. Numerically, the synthetic record shows the
normal-mode and node-basis triples agreeing to 5e-13 when the third mode
decouples, and the two-node cross-check against `invert_two_node` at 4e-16.
`invert_two_node` and its guards stay as they are for the exactly-two-mode
scope; the multimode identification is a separate function with its own
guards (§8), not a relaxation of theirs.

## 7. Recommended formal definition (draft amendment, not applied)

> **Conceptual clarification forced by the multimode identifiability analysis
> and the Faraday result. It changes no numerical value, threshold or rule;
> in the two-node scope every existing formula is unchanged.**
>
> **R1.** Let the *linear environment seen from F1* be the EM model with the
> F1 branch's declared linear inductance removed and the F1 node open (its
> charge frozen; the F1 port open-circuited). `R1` is the **normal mode of
> that environment** that corresponds to the R1 resonator's fundamental under
> the mode-correspondence rule of `numerical-plan.md` §2 (readout-like
> eigenmode by probe fields and participation; zero of `G_F` owned by that
> eigenmode). Its frequency is the registered bare readout frequency
> `f_R1 = √β_R1`. In the two-node circuit `{F1, R1}` this is exactly
> `√((C⁻¹)_R1R1/L_R1)`. `R1` is **not** a voltage along any path across the
> coupling pad; such a voltage is a diagnostic functional of the field, shown
> to be path-dependent by the Faraday term.
>
> **g_F1R1.** The coefficient of `n (a_R1 + a_R1†)` in
> `H = H_F1 + Σ_k ω_k a_k†a_k + Σ_k g_k n (a_k + a_k†)`, i.e. the registered
> algebra `g = 8 E_C,F1R1 n_zpf,R1` applied to the normal-mode coordinate:
> `g_F1R1 = coupling_GHz(c̃_R1, β_R1, L_F1)` with `c̃_R1²` the residue of
> `z − a − 1/G_F(z)` at `β_R1` (Route A) or, equivalently, from the residue of
> `Z_F1F1` at its pole `β_R1` (Route B). `|g|` is reported. In the two-node
> circuit `c̃_R1 = |c_F1R1|/√(L_F1 L_R1)` and the formula is the existing
> `invert_two_node` result.
>
> **E_C,F1F1.** Unchanged: `e²(C⁻¹)_F1F1/2h`, with `(C⁻¹)_F1F1/L_F1 = a`, the
> large-`z` coefficient of `1/G_F`.
>
> **Completeness.** For the exactly-two-mode scope the pair sum rule and
> `invert_two_node` apply unchanged. For a multimode environment the per-site
> rule is `Σ_m p_mF + δ_far = 1` over the identified in-band modes, with
> `δ_far ≥ 0` the weight of modes above the band; `δ_far` is reported, bounds
> the shift of `f_R1` and `g_F1R1` (see §8), and makes `E_C,F1F1`
> **unidentifiable from in-band eigenmode data alone** unless `δ_far` is
> resolved or the static limit is supplied by Route B or an electrostatic
> terminal solve.

## 8. Exact documents and code that would need correction

| item | change | pinned by tests |
|---|---|---|
| `coupling-definition.md` §2 (readout modes "at its coupling node"), §3 (`f_R1`, `g_kR` definitions), §8 item 5, §10 readout-node row | add the normal-mode statement of §7 as a second "Correction" block; keep every existing formula and the existing correction block | `test_coupled_review_fixes.py`: "gauge-invariant triple", "{E_C,F1F1, f_R1, g_F1R1}", "Correction (checkpoint A, after review)" must remain |
| `extraction-routes.md` §1 (shared "single-mode representation"), §2.3 (Route A general case: `G_F` zeros/residues, completeness with `δ_far`, two-node closed form retained), §3.3 ("pole of `Y_FF`" → "pole of `Z_FF`, zero of `Y_FF`") | wording and the multimode statement | "Route B's output is the same invariant triple as Route A's", "rescaling the", "leaves every fitted", "\| Output \| the invariant triple" must remain |
| `route-a-identifiability.md` | add §8: the readout node's *direction* in a multimode environment is also a convention; identifiable content is the normal-mode set | "not identifiable", "`L_R` has cancelled", `E_C,FR`, `E_C,RR`, `L_R` must remain |
| `numerical-plan.md` §2 | add the zero-ownership rule and the `δ_far` reporting; INCOMPLETE criteria unchanged | none |
| `config/coupled/v2a_five_node_candidate.json` `electrical_nodes[R1]`, `readout_structures[R1]` | optional descriptive clarification only; `extraction.target.invariant_triple` ids and `not_identifiable` unchanged | `test_coupled_review_fixes.py` pins the ids and the not-identifiable list |
| `models/route_a_inversion.py` | **no change**; docstring cross-reference only | guards pinned by `test_synthetic_three_mode_identifiability.py` |
| new `models/route_a_multimode.py` (future, after approval) | the identification of §3 with its own guards: interlacing, unique readout-like eigenmode, ownership dominance ≥ 10, `δ_far` reported and bounded, forward-map residual; production version of the SYNTHETIC `f_site_identify` | new tests |
| `contracts/extraction.py` | no change to keys or the readout-node-entry guard; optionally list `V_R`, `ρ`, `r₁₂` as non-outputs | pinned ids unchanged |
| `synthetic-three-mode-identifiability.md` §5, `readout-voltage-functional.md` §1 | note that the decision is taken and the pad functional is a diagnostic, not the coordinate | index guard only |

## 9. Are the current N1R/N2R data sufficient under this definition?

**In kind, yes.** The definition needs only F1-port data: `f_m` and `p_mF`
for the in-band eigenmodes (`eig.csv`, `port-EPR.csv`, six modes in each
record, signed EPR converted as already settled), plus the probe-based
classification. No readout surface, probe or path enters, so the 13–14 %
surface dependence of `r₁₂` is outside the target by construction.

**In precision, not yet, on two counts.**

1. *Completeness.* The six computed modes leave a participation deficit of
   order 8e-4 that the higher in-band modes do not carry (the compatibility
   note). Under §7 it is `δ_far`. A SYNTHETIC check on the reference circuit
   (`experiments/SYNTHETIC-three-mode-identifiability/far-mode-background/`)
   places a weight 7.8e-4 at 9.5–50 GHz and identifies from the in-band data
   only: `f_R1` shifts by ≤ 4e-8 and `g` by ≤ 1.4e-4 relative, but
   `E_C,F1F1` by 3 % to 46 %, growing without bound with the missing modes'
   frequency. So, **if** the deficit is far-mode weight, `f_R1` and `g_F1R1`
   are robust to it and `E_C,F1F1` is not identifiable from these records;
   **if** it is discretisation error in `p_2F` itself, no such bound holds.
2. *Participation convergence.* The readout-like mode's probe participation
   moved 18 % between the L2 baseline and N1R (`summary.json`), and `g`
   tracks the participation one-for-one; the Route A floor of about 1 %
   (`route-a-identifiability.md` §6) is not established by these two records.

## 10. The single minimum next computation

**Offline, no solve:** apply the normal-mode identification of §3 with the
correspondence rule of §5 to the existing N1R and N2R six-mode records, and
report `f_R1` and `g_F1R1` with `δ_far` and its §9 bound, the ownership
dominance ratios, and the N1R → N2R movement as the current Route A
resolution floor, with `E_C,F1F1` flagged unidentified. It produces
real-data values under the clarified definition, so it waits on the approval
of §7 and is not executed here. If its N1R → N2R movement of `g` exceeds the
floor the plan requires, the following step is a discretisation change, which
this document does not propose; resolving `E_C,F1F1` needs `δ_far` or the
static limit from Route B or an electrostatic terminal solve, likewise not
proposed here.

Not done, by instruction: no change to `coupling-definition.md` or any
registered text; no Master value, 10 % rule, guard, Palace, Route B, N3,
pulse, AMD-E or redesign work.
