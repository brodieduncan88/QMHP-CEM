# Coupling definition for the first coupled EM candidate (checkpoint A)

**Status:** checkpoint-A definition, frozen for review. Nothing here has been
executed against an EM model. Every rule stated here is an ENGINEERING-RULE
of numerical extraction unless it cites a MASTER-FROZEN or
VERIFIED-COMPUTATIONAL source, and none of it alters the frozen QMHP
requirements in `master/`.

This document fixes, before any solver runs, *what quantity* the two
extraction routes of spec §5.5 estimate for the coupled candidate declared in
`config/coupled/v2a_five_mode_candidate.json`, in which basis, in which
units, with which sign and normalisation, and how a coupling that cannot be
resolved is reported. The routes themselves are in
[`extraction-routes.md`](extraction-routes.md).

## 1. Units and conventions

| Quantity | Unit | Source |
|---|---|---|
| Lengths, coordinates | mm, frame of spec §7.3 (origin at the centre of the chip top surface, +X/+Y chip plane, +Z toward the lid) | `master/qmhp_v158f_requirements.yaml` `conventions` (QMHP-CEM-NORMATIVE) |
| Energies `E/h`, frequencies `f = ω/2π` | GHz | same, `rf_frequency_unit` |
| Couplings, pulls, offsets | MHz (cycles per second, never rad s⁻¹) | same, `rf_offset_unit`; the R1.3 hazard of `docs/v2a/m3-coherent-prescreen-registration.md` |
| Capacitance, inductance | fF, nH | this document |
| Fluxonium external flux | `phi_ext` in rad, `pi` for Branch A | `branch_a_device.phi_ext` (MASTER-FROZEN) |
| Mediator SQUID flux | `f_C = Φ_ext/Φ₀`, dimensionless | V2A registration R1c (reported, not bound) |
| Charge | Cooper-pair number `n = Q/2e`, dimensionless | the Master static Hamiltonian `H = -4 E_C d²/dφ² + …`, i.e. `n = -i d/dφ` |

Constants: `e = 1.602176634e-19 C`, `h = 6.62607015e-34 J s`,
`Φ₀ = h/2e = 2.067833848e-15 Wb`.

## 2. Node basis and the governing circuit Hamiltonian

The declaration names a set of **electrical nodes** `k ∈ 𝒩`. For the full
V2A five-mode proposal `𝒩 = {F1, F2, C, R1, R2}`: two grounded Branch-A
encoded fluxoniums `F1`, `F2`, the SQUID-transmon mediator `C`, and two
passive readout modes `R1`, `R2`. For the first executable candidate (the
bounded subsystem S1, see `README.md`) `𝒩 = {F1, R1}`. The **ground** is the
chip ground plane, continuous with the package floor (spec §7.4).

Each node `k` carries a node flux `Φ_k` (Wb), reduced phase
`φ_k = 2π Φ_k/Φ₀`, node charge `Q_k` and Cooper-pair number `n_k = Q_k/2e`,
with `[φ_k, n_l] = i δ_kl`. Every inductive or nonlinear branch of the
candidate connects a node to ground (grounded elements); there are no
floating differential elements in this candidate.

The circuit Hamiltonian is

```
H = H_C + Σ_k U_k(φ_k)

H_C = ½ Qᵀ C⁻¹ Q
    = 4 Σ_k E_C,kk n_k² + 8 Σ_{k<l} E_C,kl n_k n_l ,      E_C = (e²/2) C⁻¹
```

where `C` is the **Maxwell capacitance matrix** of the linear
electromagnetic environment reduced to the declared nodes (all passive
conductors that are not declared nodes are eliminated by Kron reduction, i.e.
they are part of the environment). `E_C,kk = e²(C⁻¹)_kk/2` reproduces the
Master's single-node form `4 E_C n²` (`E_C = e²/2C_Σ`) exactly, so for the
Branch-A fluxonium `E_C,F1F1` *is* the quantity the Master freezes at
0.60 GHz. That fixes `C_Σ = e²/(2 h · 0.60 GHz) = 32.28 fF` as the total
capacitance the geometry must realise; it is a suitability check (section 7),
not an extraction target.

Branch potentials:

- Branch-A fluxonium `k ∈ {F1, F2}` (MASTER-FROZEN §4.1/§4.2):
  `U_k = ½ E_L φ_k² − E_J cos(φ_k − φ_ext)`, `E_J = 5.72`, `E_L = 1.58`,
  `φ_ext = π` GHz; the `sin` matrix element convention is on `(φ − φ_ext)/2`.
  Lumped equivalents: superinductor `L_super = (Φ₀/2π)²/(h E_L) = 103.46 nH`,
  small junction `L_J = 28.58 nH` (linear Josephson inductance at zero phase,
  **never used as a linear element**, see section 8).
- Mediator `C` (structure taken from the V2A documents; parameters
  **unbound**, see the declaration): a symmetric SQUID transmon
  `U_C = −E_J,Σ |cos(π f_C)| cos(φ_C − θ_C)` with the irrotational 0.5/0.5
  flux allocation of registration R1c.2 as the presumptive convention;
  asymmetry `d` and `θ_C` are declared fields, not defaults.
- Readout modes `R ∈ {R1, R2}`: linear, `U_R = ½ E_L,R φ_R²`, the
  single-mode (fundamental) representation of a distributed resonator at its
  coupling node.

The Master's dressed-system Hamiltonian
`H = diag(w_i) + w_r a†a + g n (a + a†)` (VERIFIED-COMPUTATIONAL,
`dressed_system.hamiltonian`) is the `{F1, R1}` case of the above after the
readout oscillator is written in ladder operators, which is how `g` gets its
meaning (section 3).

## 3. The extraction target

**Both routes estimate the same object: the gauge-invariant triple of the
declared circuit** — for S1, `{E_C,F1F1, f_R1, g_F1R1}`, and in general the
fluxonium and mediator charging energies, each readout mode's bare frequency,
and the coupling coefficient of every required pair.

> **Correction (checkpoint A, after review).** This section first declared the
> target to be the charging-energy matrix `E_C,kl` together with each readout
> node's `(E_C,RR, E_L,R)`, and called those "circuit-level, convention-free
> quantities". That is true of a node carrying a declared lumped branch, and
> **false of a readout node**, which carries none: nothing in the EM model
> fixes the scale of its node flux, so `E_C,kR`, `E_C,RR` and `L_R`
> individually are conventions, not measurements. The coupling `g`, the bare
> readout frequency and the fluxonium charging energy are invariant and are
> the reportable outputs. The derivation, the witness and the demonstration
> are in [`route-a-identifiability.md`](route-a-identifiability.md); the
> reported coupling and every threshold are unchanged, because `g` was
> invariant all along.

From them the reported coupling coefficients follow by fixed algebra:

- **Nonlinear element `k` ↔ readout mode `R`** (the interaction the existing
  gate consumes): with `n_R = n_zpf,R (a + a†)`,
  `n_zpf,R = (E_L,R / 32 E_C,RR)^{1/4}`, and bare
  `ω_R/2π = √(8 E_C,RR E_L,R)`,

  ```
  g_kR = 8 E_C,kR · n_zpf,R        [GHz → reported in MHz]
  ```

  This is exactly the `g` of the Master convention `g n (a + a†)`: for
  `{F1, R1}` the Master carries `g = 0.150 GHz` and `w_r = 4.301974466 GHz`
  (the bare readout frequency at the logical-blind root). The sign of `g` is a
  gauge choice (`a → −a`); `|g|` is reported and compared.
- **Nonlinear element `k` ↔ nonlinear element `l`** (`F1–C`, `F2–C`, and the
  parasitic `F1–F2`): the charge–charge coupling energy

  ```
  J_kl = 8 E_C,kl        [GHz → reported in MHz],   H_int = J_kl n_k n_l
  ```

  is the circuit-level coupling. No ladder-operator form is imposed on the
  fluxonium side (section 8).
- **Readout ↔ readout, mediator ↔ readout** (parasitic): `J_kl = 8 E_C,kl`
  likewise, reported in MHz.

Each route therefore delivers, per required pair, the invariant coefficient
(`g_kR` or `J_kl`) in MHz, together with the invariant diagonal quantities it
can determine; the COUPLING_EXTRACTION comparison is made on those
coefficients, so the existing `eigenmode_MHz` / `blackbox_MHz` semantics are
kept. Matrix entries that depend on a readout-node normalisation are reported
only alongside the gauge they are stated in, and are never compared between
the routes.

## 4. What the target is *not*

| Quantity | Relation to the target | Where it lives |
|---|---|---|
| Circuit-level coupling `g_kR`, `J_kl` | **the target** (section 3) | EM extraction, both routes |
| Transition-specific matrix elements, e.g. `⟨22,1_C\|n_C\|22,0_C⟩ = 1.300454` (reported) | derived from the diagonalised *nonlinear* circuit built with the extracted `E_C`; never extracted from EM | `models/` (static + dressed system), V2A registration |
| Normal-mode splitting / hybridisation of the *linear* EM eigenmodes | Route A intermediate (section 3 of `extraction-routes.md`); it is not the coupling and is not compared as such | Route A only |
| Readout-node matrix entries `E_C,kR`, `E_C,RR`, `L_R` | **not identifiable**: each depends on an arbitrary readout-node normalisation. Reported only in a stated gauge, never compared | `route-a-identifiability.md` |
| Dispersive pulls `χ`, logical/sink pulls, sink line | outputs of the frozen dressed-system model; unchanged and still computed for the nominal device | `models/dressed_system.py` |
| Effective gate interactions: static `ζ`, conditional mediator lines `f_22`, `Δ_min`, drive `u_C` | properties of the driven or dressed nonlinear spectrum; **not admitted** at this milestone, not targets, not acceptance quantities | V2A M3 registration, out of scope |

## 5. Interactions required for the milestone (declared before any result)

For the **full five-mode proposal** the required interaction set is the whole
upper triangle of `E_C`:

| pair | class | why it is required |
|---|---|---|
| F1–C, F2–C | essential | the mechanism of the hypothesis (mediator conditioned on the fluxonium states) |
| F1–R1, F2–R2 | essential | readout of each encoded fluxonium; F1–R1 is the Master's `g` |
| F1–F2 | parasitic, must be reported | direct coupling bypassing the mediator |
| C–R1, C–R2 | parasitic, must be reported | mediator leakage into readout |
| R1–R2, F1–R2, F2–R1 | parasitic, must be reported | cross-readout paths |

For the **first executable candidate S1** (`𝒩 = {F1, R1}`) the required set is
the single essential pair **F1–R1**, plus the diagonal `E_C,F1F1` and the bare
`(ω_R1, E_L,R1)` as suitability quantities. Reporting fewer pairs than the
declared required set, or choosing which pairs to report after seeing values,
makes the extraction INCOMPLETE.

## 6. The consistency rule, unchanged

The existing ENGINEERING-RULE of spec §5.5 and
`master/qmhp_v158f_requirements.yaml` `coupling_extraction` applies per
required pair and is not modified:

```
relative disagreement = |a − b| / mean(|a|, |b|) > 0.10  →  EXTRACTION-INCONSISTENT
```

with `a` from Route A and `b` from Route B, never averaged when inconsistent
(`models/coupling_extraction.py`). No target value of `g`, `J` or `E_C` and no
new physical acceptance threshold is introduced by this checkpoint.

## 7. Candidate suitability, separate from extraction agreement

Extraction agreement says the two routes see the same linear environment. It
does not say the candidate is the Branch-A device. The following are reported
as **information**, with no PASS/FAIL attached, alongside the extraction:

- `E_C,F1F1` against the frozen 0.60 GHz (relative deviation);
- bare `ω_R1/2π` against the frozen bare readout root 4.301974466 GHz;
- `|g_F1R1|` against the VERIFIED-COMPUTATIONAL 0.150 GHz;
- the frozen tolerance scale (σ = 2 % on `E_C`, `E_J`, `E_L`; QMHP-CEM-NORMATIVE)
  is quoted next to the `E_C` deviation as context, not as a limit.

The nominal-reference quantum calculation (`evaluate_quantum`, frozen device)
is unchanged. A geometry-derived calculation, when one is made, is a separate
block labelled as such (`implementation-plan.md` §3); the extracted values
never overwrite the nominal ones.

## 8. Linear environment / nonlinear circuit boundary, and double counting

The EM solver models the **linear environment only**: conductors, substrate,
vacuum, package walls, and (Route A only) the declared *linear* lumped
inductances. The nonlinear circuit is assembled afterwards from the extracted
`E_C`, the declared `E_J`, `E_L`, `f_C` and any declared non-geometric
capacitance, and diagonalised with the existing `models/` machinery
(3201-point phase grid, `Nq = 10`, `Nph = 12`).

Rules that prevent double counting:

1. The small junction's Josephson inductance is **never** a linear element of
   the EM model. At `φ_ext = π` the fluxonium branch curvature
   `E_L − E_J = −4.14 GHz` is negative: there is no positive linear
   inductance for the `junction ∥ superinductor` branch, so a linearised
   ("weakly anharmonic", transmon-style) treatment of the Branch-A fluxonium
   is outside its regime and is not applied anywhere. The fluxonium
   nonlinearity enters only through `−E_J cos(φ_k − π)` on the phase grid.
2. The superinductor is a declared lumped inductance `L_super = 103.46 nH`.
   In Route A it is attached to the EM eigenmode model as the port inductance
   and is **removed analytically** in the inversion (`extraction-routes.md`
   §2.3); in Route B it is absent. Its internal array modes are an *omitted
   effect* in the declaration.
3. The mediator SQUID is weakly anharmonic (`E_J,Σ/E_C,C ≫ 1` if the
   unbound seed is adopted); its linear inductance
   `L_C(f_C) = (Φ₀/2π)²/(h E_J,Σ|cos π f_C|)` may be attached in Route A and
   is likewise removed in the inversion. Its nonlinearity is applied in the
   circuit model, not in EM.
4. Every capacitance that is **not geometric** (the small junction's
   intrinsic `C_J`, the array junctions' capacitances inside the
   superinductor) is either declared once as a lumped capacitance added to
   `C` after extraction, or declared absent; it is never both in the EM model
   and in the lumped model.
5. The distributed readout resonators are part of the EM model in both
   routes. Their single-mode representation `(E_C,RR, E_L,R)` is an output of
   each route, not an input; higher resonator modes are screened (numerical
   plan) and omitted from the circuit model.
6. `E_C` is used once: the same matrix drives both the self-charging terms
   and the couplings, as the V2A assessment requires (Maxwell matrix, not
   isolated `E_C` values with appended `g`s).

## 9. Vanishing or numerically unresolved couplings

Each route reports, for every required pair, a value and a **resolution
floor** `δ` (MHz): the larger of the change of the value between the final
two refinement levels of that route (mesh for both, response-fit order for
Route B) and the route's own fit or convergence residual expressed in the
same unit. The status of a pair is then

| status | condition | reported as |
|---|---|---|
| RESOLVED | `|value| ≥ 10 δ` in **both** routes | value, `δ`, and the 10 % comparison |
| UNRESOLVED | `|value| < 10 δ` in either route | an upper bound `|coupling| < 10 δ_max` and **no** 10 % comparison |
| MISSING | a route did not produce the pair (mode not identified, fit failed, run failed) | the failure, and the extraction is INCOMPLETE |

The factor 10 is the existing numerical-verification ratio of
`solvers/palace/verification.py` (`height_shift_to_uncertainty_min_ratio`),
reused rather than invented. Two near-zero values that agree are **not**
evidence that the interaction exists: for an essential pair UNRESOLVED means
the extraction is INCOMPLETE and the gate must not PASS; for a parasitic
pair it is the legitimate result "bounded above by `10 δ_max`". The existing
`CouplingExtraction.relative_disagreement`, which returns 0.0 when both
values are zero, is therefore only ever fed RESOLVED pairs
(`implementation-plan.md` §3).

## 10. Sign, phase and normalisation bindings for this checkpoint

| item | binding |
|---|---|
| `E_C` sign | `E_C = (e²/2) C⁻¹` with `C` the Maxwell matrix (positive diagonal, negative off-diagonal mutuals); off-diagonal `E_C,kl` is then **positive** for capacitive coupling |
| `g_kR` | `8 E_C,kR n_zpf,R`, `n_zpf,R = (E_L,R/32 E_C,RR)^{1/4}`, magnitude reported. Gauge-invariant: in closed form `g = 2 e^{3/2}√(L_k φ_r) k /(h b^{1/4})` with no `L_R` (`route-a-identifiability.md` §2) |
| readout-node gauge | the readout node flux has no scale until one is declared. Any matrix entry shown for a readout node states its gauge; the reported coefficients do not depend on it |
| `J_kl` | `8 E_C,kl`, magnitude reported |
| readout operator phase | `n_R = n_zpf,R (a + a†)`, matching the Master's `g n (a + a†)` |
| fluxonium charge operator | `n = −i d/dφ` on the Master grid; the Master's `n12 = 0.659915` is the regression anchor |
| flux allocation, SQUID phase sign | declared per registration R1c; the static spectrum is invariant under the sign, which is why it is declared, not tested |
| frequencies | cycles per second; `ω = 2π f` only inside formulas |
