# Supplement 1 to the R1 correspondence scoping note: port model PA

**Status: SUPPLEMENT / CORRECTION RECORD. DESK ONLY. NON-DECISION.** It registers, adopts and authorises nothing, and nothing was run to produce it.

- **What it supplements.** `docs/coupled-candidate/r1-correspondence-scoping.md`, committed at `d2b227c`. That note is not edited: it gains only a dated pointer to this record (CLAUDE.md §1).
- **Why.** On 2026-09-25 the human directed that three results be recorded:
  - the dark-mode and degeneracy caveat on PA's pole characterisation (§2);
  - the condition that the island's harmonic field be present, not pinned (§3);
  - the well-posedness of PA on H(curl) under the PEC-end condition (§4).
- **Basis.**
  - Committed files at `d2b227c`, cited as `path:line`. Line numbers in the scoping note (`:129`, `:227`, `:370`) refer to its text at `d2b227c`, before the two-line pointer this commit adds.
  - Pinned Palace `a61c8cbe0cacf496cde3c62e93085fae0d6299ac`.
  - The frozen revision-6 pre-declaration, which was never committed, cited as [rev6:N, uncommitted].
- **How it was checked.** Two independent refute-first desk checks, one per question. Each is a single derivation by hand.
  - They share premises with the note, so they are not independent confirmation of it or of each other (CLAUDE.md §7).
  - Their controls are hand arithmetic, not coded known-answer tests.
  - Everything below is **DERIVED-DESK** unless labelled otherwise.
  - Literature is cited from memory and was not read.

## 1. The statements being supplemented (preserved verbatim in the note)

- **§3 table, PA realisation row (`:129`).** "PA's Y_FF poles are the zeros of the face-open Z_FF … On one mesh, Z_FF(ω) = 1/(iω C_h) + iω Σ_k |fᵀE_k|²/(λ_k − ω²)". It lists as missing item "(ii) whether that term exists there at all: it needs the island's harmonic field ∇φ_island in the discrete space".
- **§5.2 (`:227`).** "Under PA only, this is the kind of quantity the first Y_FF zero is".
- **§12, PA row (`:370`).** "the first Y_FF zero is the physical F-open resonance".
- **Not in the note.** After the note was committed, a further desk claim was made in session: that PA's poles are *exactly* the eigenvalues of the Maxwell problem constrained to fᵀE = 0. It was never committed. It is recorded here in corrected form so that it does not propagate.

## 2. PA's poles and the dark-mode and degeneracy caveat

**Discrete setting.**
- Uniform current I is injected across the face Γ, and V = fᵀe, with f Palace's width-averaged voltage functional (`palace/models/lumpedportoperator.cpp:198-216`).
- With the element removed, Z_FF(s) = s·fᵀ(K + s²M)⁻¹f.
- Group the eigenvalues μ_j of (K, M), kernel included, with eigenspace projectors P_j. The Foster form is Z_FF(s) = α₀/s + Σ_{μ_j>0} c_j·s/(s² + μ_j), with c_j = fᵀP_j f ≥ 0 and α₀ the kernel weight (§3).

**What stands.** The note's "Y_FF poles are the zeros of Z_FF" is exact. So is its formula at `:129`: dark modes (c_j = 0) contribute nothing to it.

**Correction to the uncommitted "exactly" claim.**
- **Poles → constrained eigenvalues.** Every finite nonzero pole of Y_FF is an eigenvalue of (K, M) restricted to X_f = {x : fᵀx = 0}. Equivalently, (K − λM)x = μ_L f with fᵀx = 0, where the Lagrange multiplier μ_L is required.
- **The converse is false.** Two kinds of constrained eigenvalue are neither poles nor zeros of Y_FF:
  - **dark face-open eigenvalues** (c_j = 0). They satisfy the constrained problem with μ_L = 0, and their factor cancels between the numerator and denominator of Z_FF;
  - **the leftover of a degenerate bright eigenvalue.** If μ_j has multiplicity d_j > 1, a (d_j − 1)-dimensional part satisfies the constrained problem with μ_L = 0.
- **Corrected statement.** The finite nonzero poles of Y_FF are exactly the constrained eigenvalues that have an eigenvector with nonzero multiplier. The identity behind it is det[[K − zM, f], [fᵀ, 0]] = −det(K − zM)·fᵀ(K − zM)⁻¹f.

**Zeros and interlacing.**
- Apart from DC, the zeros of Y_FF are the **bright** face-open eigenvalues only: those with c_j > 0.
- Index for index, including the kernel, λ_i ≤ λ̃_i ≤ λ_{i+1}, where λ̃ are the constrained eigenvalues.

**Consequences for the note's wording.**
- The note's "the first Y_FF zero is the physical F-open resonance" (`:370`), and the reading of PO1 m1 as that zero (`:227`), hold only for the lowest **bright** F-open mode.
- A dark F-open mode is not a zero of Y_FF.
- Whether PO1 m1 is bright is not established by this record.

**Conditions.** The statements above need all four:
1. **The excitation vector equals the voltage functional.** Pinned Palace builds its excitation and voltage forms from the same mode coefficient with different scalars (`palace/models/lumpedportoperator.cpp:178-212`). They are proportional for a single element, or for elements of identical geometry, but not in general.
2. **The system is lossless**, with real symmetric K ≥ 0 and M > 0.
3. **α₀ > 0** (§3).
4. **Constrained eigenvectors with zero multiplier are excluded.**

**Controls (SYNTHETIC; hand arithmetic, M = I, K = diag(0, 1, 4)).**
- **Positive: f = (1, 1, 1).** The zeros of Z are (5 ± √13)/3. The constrained pencil on the basis (1, −1, 0), (1, 0, −1) has characteristic polynomial 3z² − 10z + 4, so the two agree.
- **Negative A: f = (1, 1, 0), a dark mode.** The constrained eigenvalues are {1/2, 4}. Only 1/2 is a pole of Y; 4 is neither a pole nor a zero.
- **Negative B: K = diag(0, 1, 1), f = (1, 1, 1), a degenerate eigenvalue.** The constrained eigenvalues are {1/3, 1}. Only 1/3 is a pole; 1 has μ_L = 0.

## 3. The island's harmonic field must be present and bright

**The DC term.** α₀ = sup over ker K of (fᵀx)²/(xᵀMx).
- If ker K is the discrete gradients, and the face condition holds (`static-anchor-hypothesis.md:88-89`), then α₀ = 1/C_h. Here C_h is the static capacitance with the face open, and ∇φ_island is bright: fᵀ∇φ_island is the island-to-ground potential difference.
- This also needs the bright kernel to contain no non-gradient harmonic fields, which is a cohomology condition.

**If the island's potential is pinned in the discrete space** (as `po1-port-removed-control.md:96-100` states for PO1), ∇φ_island is absent and α₀ can be 0. Then:
- Z_FF(0) = 0, and Y_FF has a **DC pole**: a 1/(s·L₀)-type term, instead of Y_FF ~ s·C at low frequency;
- rev6's "no 1/(sL₀) term" and "DC limit exactly C" [rev6:140-141, uncommitted] fail;
- the identification C_DC(PA) = C_static (note §3.1 item 4) does not hold for that discrete problem.

Control C (SYNTHETIC: K = diag(0, 1, 4), f = (0, 1, 1)) shows this. The constrained eigenvalue 5/2 still matches the zero of Z, but Y ≈ 1/(s·5/4) at DC.

**Condition to add to the note's item (ii) (`:129`).** Under PA, ∇φ_island must lie in the discrete space and must not be pinned. Without it, it is not only the DC term that cannot be formed on the same space: **the PA Foster form itself fails.**

For PO1's space the dispute is unchanged and **UNRESOLVED**. A desk argument (note `:227`) holds that the field is present. The PO1 document says it is pinned.

## 4. PA is well-posed on H(curl), under the PEC-end condition

**Result.** The functional f(E) = (1/w)∫_Γ E·l̂ dS is a **bounded linear functional on H₀(curl, Ω)**, where Ω is the box minus the zero-thickness PEC sheets. This requires:
- **The PEC-end condition.** Both ends of Γ, the two edges of width w, lie entirely on PEC (island and ground) over their full width.
- The long sides do not matter, because the weight's normal component is continuous across them.

**Proof sketch.**
- Take the lifting W = −(1/w)·χ(x)·η(y)·ψ(z)·x̂, supported in the substrate below Γ, where:
  - χ is the width indicator;
  - η equals 1 on Γ and ramps down inside the two metal strips;
  - ψ(0) = 1, with support shallower than the substrate.
- Green's formula, with zero tangential trace on the PEC strips, gives f(E) = ∫(curl E·W − E·curl W) dV, with W and curl W bounded.
- So |f(E)| ≤ C‖E‖_H(curl). The constant grows as the ramp length or w goes to 0.
- The same identity holds exactly for Nédélec fields, so Palace's discrete f is the restriction of the continuum f, provided its quadrature is exact. That was not inspected.

**The condition checked against the declaration.** The declared rectangles in `config/coupled/v2a_five_node_candidate.json` put P_F1 flush with the island and the ground along its full width. This is desk arithmetic on declared values. On the mesh, the records state only that "the port face touches both" conductors (`static-anchor-hypothesis.md:56`), and that the face condition (conductor nodes only on the two end lines) holds on L2 (`static-band-pairing.md:106-107`). Full-width contact on the box-refined mesh was not checked.

**Negative control (sketch).** If part of an end lay on dielectric, f would be unbounded on H(curl). A gradient field of log-log type near that end segment shows this.

**Relation to L².** f is **not** bounded on L². So fᵀM⁻¹f is infinite in the continuum, and C_∞(PA) = 1/(fᵀM⁻¹f) → 0. This is consistent with note §2 and §5.3, and with the recorded growth factors ×1.94 and ×2.01; that is consistency only, nothing was recomputed.
- One desk derivation suggests the committed divergence sketch (`static-anchor-hypothesis.md:78-84`) is a valid proof of L²-unboundedness.
- That has not been independently verified. The note's "Divergence is not proved" stands until it is.

**Consequences.**
- **{fᵀE = 0} is a closed subspace of H₀(curl).** It is dense in L².
- **Z_PA(s) is finite for every real s > 0.** This follows by Lax–Milgram.
- **The PA pole problem is well-posed with a discrete spectrum.** Two conditions:
  - Maxwell compactness for the screen domain (LITERATURE, not read: Picard, *Math. Z.* 187 (1984); Bauer, Pauly and Schomburg, *SIAM J. Math. Anal.* 48 (2016)).
  - α₀ > 0 with no extra cohomology (§3).
- **Nédélec approximations on V_h ∩ ker f converge**, given discrete compactness (LITERATURE, not read: Kikuchi 1989; Hiptmair, *Acta Numerica* 2002; Boffi, *Acta Numerica* 2010). No convergence rate is claimed.
- **Scope.** This settles a well-posedness question. It supplies **no certified bound**. Certified one-sided bounds on Maxwell eigenvalues and spectral counting remain unavailable (note §7). PA's certification requirements are therefore real, not moot.

## 5. Direction recorded

The human decided on 2026-09-25 to stop comparing PA and PB. The next research task is:

> Can we build a certified lower-bound method for the relevant Maxwell eigenvalue, plus spectral counting, on this zero-thickness PEC-screen geometry?

This record reports that direction. It does not start the task.

## 6. What this record does not establish

- No value or bound for any S1 quantity: E_C, g and f_R1 stay UNAVAILABLE.
- Whether PO1 m1 is bright, and whether PO1's space contains ∇φ_island.
- Maxwell compactness and discrete compactness for screen domains. These rest on unread literature.
- That the PEC-end condition holds on the meshed and box-refined geometry, beyond the declared values and the records cited in §4.
- Palace's quadrature exactness.
- Any correction to the uncommitted rev6. Its [rev6:140-142, 158] carry the same caveats; they are noted here only.
