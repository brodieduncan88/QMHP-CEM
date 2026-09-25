# R1 correspondence scoping note: from the static result to the registered E_C,F1F1

**Status: DESK SCOPING NOTE; NON-DECISION RECORD. It registers, adopts and authorises nothing.**

*Supplement (25 September 2026): PA's pole characterisation (dark-mode and degeneracy caveat), the island harmonic-field condition, and PA's H(curl) well-posedness under the PEC-end condition are recorded in [`corrections/r1-correspondence-scoping-supplement-1.md`](corrections/r1-correspondence-scoping-supplement-1.md). The text below is otherwise unchanged.*

- **What it is.** A scoping note, written 2026-09-25 and committed the same day, at the human's direction, as a desk-only, non-decision record. It covers what is needed to get from the E1 static result to the registered E_C,F1F1:
  - the definitional options, and what each combination means;
  - what the existing records can and cannot establish;
  - the gaps;
  - the smallest decision and the smallest follow-on step.
- **What it does not do.**
  - It does not choose between M1, M2 and M3, or between PA and PB.
  - It runs nothing: no Palace, Route A, solver, S1 capacitance work or experiment.
  - It proposes nothing for execution. Any step named in §9 or §12 would need its own pre-declaration and explicit human approval (CLAUDE.md §3).
  - It edits no evidence. The commit that adds it adds this note and one README row, and nothing else.
  - It states no E_C, g or f_R1 value of its own and no new bound. Recorded frequencies are quoted only as what the records contain (candidate poles or zeros), with their source labels. No frequency-unit figure derived from an E1 number is given (the consumed E1 approval's `does_not_authorise`).
- **Basis.**
  - Committed files at `91bb82ca8c5898eb413c8cda3b521fe70ec4e507`, the parent of the commit that adds this note, cited as `path:line`.
  - The E1 contract's derivations live in a frozen revision-6 pre-declaration that was **never committed** (sha256 `bc59ac5b…`, digest pinned at `E1-CONTRACT.rev8.5.md:643`). It is cited as **[rev6:N, uncommitted]**. Anything resting only on it is labelled so.
  - Arguments made only in this note or its review are labelled **DERIVED-DESK (this note)**. They are desk arguments, not verified derivations; committing this note does not change that.
- **How the evidence was gathered.**
  - Five desk maps covered the definitions, N1R/N2R, PO1, the first-moment work, and the static evidence with a gap register. Each map was checked by a separate refute-first verifier against the frozen snapshot: 477 claims, 0 wrong, 15 overstated, corrected here.
  - The note then underwent a four-lens adversarial review (v1) and a focused refute-first review (v2). Their confirmed findings are incorporated.
  - The maps are a scratch file that is not in the repository, `work/maps.json` (sha256 `6f2cb56c…e07a`). These counts describe the desk process; they are not evidence.

## 0. Summary

1. **Two decisions are open.** The registered E_C,F1F1 = e²(C⁻¹)_FF/2 does not fix how the distributed, shorted R1 enters C (`E1-CONTRACT.rev8.5.md:107-113`). The open choices are:
   - a **reading**:
     - M1: the DC limit plus the exact R1 pole and residue;
     - M2: the high-frequency limit;
     - M3: a band fit;
   - a **port model** at the F1 site:
     - PA: a transparent face with a uniform current;
     - PB: Palace's sheet port.

   Each is a registered-definition decision (`:113`; `corrections/static-anchor-ec-bound-correction.md:117`).
2. **Static evidence differs by port model.**
   - **PA.** Both ends of C_DC are recorded results only under PA: E1 reports C_static ∈ [57.220910, 67.975539] fF for the meshed model.
     - The lower end holds under the libm ASSUMPTION.
     - The upper end is the frozen study's Dirichlet bound, rigorous only up to the uncertified ρ (conditions in §3.1).
   - **PB.** Only an upper bound on C′ is a recorded result.
     - C′ ≥ C ≥ C_lo^static holds mathematically, but it is not an E1 result (`E1-CONTRACT.rev8.5.md:102, 663`).
3. **Dynamic evidence.**
   - No record supplies the R1 pole ω_p, its residue a_R1, the second pole ω₂ or a completeness certificate of either port model:
     - N1R and N2R are eigen-solves of the **L_F1-loaded** sheet-port pencil;
     - PO1 is its **port-removed** (F-open) counterpart;
     - the first-moment run certifies only that the saved spectra are incomplete.
   - On a desk reading, PO1's F-open modes and recorded face functional are partial inputs to PA's Y_FF. They lack the same-space DC term and completeness (§3).
4. **M2 appears degenerate under both port models, but no source derives this.**
   - Committed text asserts that the complete first moment diverges under refinement "for **both** port models" (`static-band-pairing.md:92-94`). The support is a sketched argument (`static-anchor-hypothesis.md:78-84`) and rigorous lower bounds over two uniform refinements of L2 (§5.3). Divergence is not proved.
   - "C_∞ = 0" is committed for "the registered sheet port" (`corrections/e1-exploratory-claims-correction.md:30`). It cites [rev6:139], which sits inside rev6's **PA** definition, so its port-model attribution is ambiguous.
   - The identity C_∞(PA) = 1/(fᵀM⁻¹f), which ties PA's C_∞ to that first moment, is DERIVED-DESK (this note; §2).
5. **M3 exists only on sheet-port data in the sources.** The contract defines M3 as "a band fit" (`E1-CONTRACT.rev8.5.md:112`) and pairs it with "a Route B band fit" (`:117`); rev6 identifies M3 with Route A's fit [rev6:164, uncommitted]. Both routes' fits are realised only on Palace sheet-port data. No source defines M3 under PA.
6. **The five named gaps are all open:**
   - readout-mode identification;
   - residue extraction;
   - pole/zero bounds;
   - spectral completeness;
   - the rank-one port-term error.

   Underneath them are two method gaps. No method in the repository gives **one-sided bounds on discrete Maxwell eigenvalues** relative to the continuum, and none gives a **pole-counting or completeness certificate**. No single experiment can yet close a certified quantity.
7. **The smallest registered decision before any experiment is a reading together with a declared port model.** Each reading needs the port model for a different reason (§8). No order between the two is implied. C_J and the R1-coordinate decision can wait.
8. **PB needs a C′ lower-bound treatment.** For an E_C upper bound, PB needs one, and no recorded result supplies it (§6). PA's pole and residue data need a same-space DC term, and a new S1 static solve conflicts with the E1 stop rule unless separately re-approved (§3).

## 1. What is registered, and what is open

- **The target.**
  - E_C,F1F1 = e²(C⁻¹)_F1F1/2, with C the Maxwell capacitance matrix Kron-reduced to the declared nodes.
  - For S1 the node set is 𝒩 = {F1, R1} (`coupling-definition.md:36-37, 55-58`).
- **R1's representation.** R1 is "the single-mode (fundamental) representation of a distributed resonator at its coupling node" (`coupling-definition.md:78-80`). Higher resonator modes are screened and omitted (`:249-250`). The text does not say whether their static contribution is kept.
- **R1 as declared.** It is a quarter-wave CPW, galvanically shorted to ground (`E1-CONTRACT.rev8.5.md:107`).
- **Unapproved seeds.**
  - The declared R1 geometry and the F1 port `P_F1` are unapproved ENGINEERING-SEEDs (`config/coupled/v2a_five_node_candidate.json:576-579, 626-629`).
  - C_J is an unapproved 0 fF seed (`:538-543`). The registered rule is to declare it once, or declare it absent (`coupling-definition.md:240-244`).
- **What the E1 contract fixes.** It fixes the vocabulary but adopts nothing:
  - the readings (`E1-CONTRACT.rev8.5.md:110-113`);
  - the port models and bound directions (`:114-134`);
  - correspondence NOT_ESTABLISHED (`:135-139`).
- **A second, unlinked decision is in flight: the R1 coordinate for g and f_R1.** It is drafted in `r1-definition-decision.md`, which is **unapproved** (`:41-46`), with 2026-09-20 corrections that take precedence (`:3-6`; the corrections run to `:39`).
  - No source links it to the E_C reading.
  - The draft's E_C clause is (C⁻¹)_F1F1/L_F1 = a, "the large-`z` coefficient of `1/G_F`" (`:216-217`). That is M2-type [rev6:163, uncommitted].
  - Its completeness clause was itself corrected by correction 3 (`:18-27`). It also offers, as one alternative to resolving δ_far, "the static limit … supplied by Route B or an electrostatic terminal solve" (`:223-226`).
  - No source states how that clause relates to the readings.

## 2. The readings M1, M2, M3

All three are defined in `E1-CONTRACT.rev8.5.md:110-113` and derived in [rev6:150-168, uncommitted].

- **The Foster form they rest on.** Y_FF(s) = s·C_∞ + Σ a_n·s/(s² + ω_n²), with DC limit C_DC = C_∞ + Σ a_n/ω_n². This is committed at `corrections/static-anchor-ec-bound-correction.md:72`.
- **Its check.** The M1 and M2 direction inequalities were checked by a reviewer on 40,000 random synthetic Foster admittances, with 0 violations. That check is reported at `:145`; its basis is uncommitted session material (`:143`).

- **M1.** The DC limit plus the exact R1 fundamental pole and residue of **one declared port model's** Y_FF (P_R1 absent). All other modes fold into a frequency-independent capacitance.
  - 1/(C⁻¹)_FF = C_DC − ΔC_R1, with ΔC_R1 = a_R1/ω_p² ≥ 0.
  - M1 needs no L_F and no fit band. Its error is the in-band dispersion of the non-R1 modes [rev6:151-168, uncommitted].
  - Under M1, the M1 two-node model's F-open zero f_R* is in general not the first zero f_z of the declared model's Y_FF. If R1 is the lowest pole, f_z ≤ f_R*, with equality only if every non-R1 residue vanishes [rev6:156-157, uncommitted].
  - f_z is the physical F-open resonance under PA. Under PB that identification is not derived [rev6:158-159, uncommitted].
- **M2.** The high-frequency limit, which is the complete first moment: 1/(C⁻¹)_FF = C_∞ ≤ C_DC.
  - The correction is not ΔC_R1 alone: C_DC − C_∞ = Σ over **all** modes of a_n/ω_n² (`static-anchor-ec-bound-correction.md:72`).
  - **What the sources say about C_∞.**
    - rev6 states C_∞ = 0 "for the sheet port with any port-loop inductance", resting on the first-moment argument (`static-anchor-hypothesis.md:26-28`) [rev6:162, uncommitted].
    - The committed statement is for "the registered sheet port" (`corrections/e1-exploratory-claims-correction.md:30`). It cites [rev6:139], but that line sits inside rev6's **PA** bullet: "(C_∞ = 0 for the sheet port)" [rev6:138-139, uncommitted]. So which port model the committed statement covers is **ambiguous**.
    - Committed text asserts that the complete first moment "diverges under refinement for **both** port models" (`static-band-pairing.md:92-94`).
  - **Under PA**, DERIVED-DESK (this note; independently re-derived in review):
    - With a uniform face current, the conjugate voltage is the width-averaged face functional f of the first moment (`fem-spectral-mapping.md:49-50`).
    - The open-face impedance behaves as Z_FF(ω) → fᵀM⁻¹f/(iω) as ω → ∞, so on each mesh C_∞(PA) = 1/(fᵀM⁻¹f) > 0.
    - If the asserted divergence of that moment holds, C_∞(PA) → 0 under refinement. The evidence is a sketched argument plus rigorous lower bounds that grew ×1.94 and ×2.01 over two uniform refinements of L2, on the project's own assembly rather than Palace's box-refined space (`static-anchor-hypothesis.md:55, 205, 216`; §5.3).
  - **Consequence.** If the divergence holds, M2 has no usable continuum limit under either port model, and its E_C lower bound is formally valid but uninformative. Neither the divergence nor either port model's C_∞ → 0 has a committed derivation. The PA identity is a desk result, to be checked before any reliance.
- **M3.** Route A's two-mode band fit [rev6:164, uncommitted]. The contract keeps "a Route B band fit" alongside it (`E1-CONTRACT.rev8.5.md:117`).
  - **What it depends on.** The declared L_F, the band modes and the fit band.
  - **It can exceed C_DC.** On a synthetic S1-like network with C_DC = 53.689 fF, an M3-like fit gives 53.848 fF and a Route-B-like band constant gives 53.817 fF [rev6:184-186, uncommitted].
  - **Continuum limit (synthetic only).** In a synthetic quarter-wave ladder it has one: 8-digit convergence under 16× refinement [rev6:165, uncommitted]. This is not shown on S1 data.
  - **Port model.** It is realised in the sources only on Palace sheet-port (PB) data. No source defines M3 under PA.
  - **The registered Route B text is itself inconsistent** (`extraction-routes.md:226-228, 250-252`) [rev6:170-176, uncommitted].
- **The registered routes compute neither M1 nor M2.**
  - Route A's fit is M3 [rev6:164, uncommitted].
  - Route B's band-limited fit "does not compute M1" [rev6:170-176, uncommitted; defects reported, not fixed].
  - Yet `extraction-routes.md:246-252` says Route B's fit determines E_C,F1F1 and f_R1. Adopting M1 or M2 would leave that registered text unreconciled.

## 3. The port models PA and PB

The committed text covers the C_DC row (`E1-CONTRACT.rev8.5.md:115`; `static-anchor-ec-bound-correction.md:82-84`). **Every other row rests on [rev6:137-159, uncommitted].**

| | **PA**: transparent face, uniform current | **PB**: Palace's lumped sheet port |
|---|---|---|
| C_DC | C_static (problem C: face open, shorted R1 metal at 0 V) | C′ (face potential held linear along the port) |
| poles of Y_FF | zeros of Z_FF, which are **not** the PEC-face eigenfrequencies [rev6:142, uncommitted] | the eigenmodes with the F1 face PEC-shorted [rev6:143-145, uncommitted] |
| first zero of Y_FF | the physical F-open (open-face) resonance [rev6:158, uncommitted] | its identification with the open-face resonance is **not derived** [rev6:159, uncommitted] |
| static evidence (recorded) | both ends, on the meshed model: C_static ∈ [57.220910, 67.975539] fF, with the conditions of §3.1 | upper end only: C′ ≤ 68.04546246723753 fF, with the conditions of §6 (`static-refinement-study.md:50`) |
| realisation of the pole problem | **Not named in any source for PA's poles or residue.** DERIVED-DESK (this note): PA's Y_FF poles are the zeros of the face-open Z_FF, so the constraint need not be imposed. On one mesh, Z_FF(ω) = 1/(iω C_h) + iω Σ_k \|fᵀE_k\|²/(λ_k − ω²). Its resonant data are what a PO1-type port-removed solve records (PO1 has `port-V.csv` and `port-EPR.csv`). **Missing:** (i) the DC term 1/C_h on the same discrete space, which is Palace's box-refined space, not rebuilt by the project's static code (`static-anchor-hypothesis.md:205`); the identity with 1/C_h also needs the face condition of `static-anchor-hypothesis.md:88-89`, checked only on the static meshes (`static-refinement-study.md:17-18`); (ii) whether that term exists there at all: it needs the island's harmonic field ∇φ_island in the discrete space, and the PO1 document says the island potential is pinned (`po1-port-removed-control.md:96-100`), which a review desk argument disputes (DERIVED-DESK); (iii) completeness of the modal sum; (iv) reconciling Palace's recorded normalisation with M-normalised modes (`first-moment.md:45-47`); (v) identification of the R1 zero. The PO1 projector change does not enter PA's use of PO1's own pencil, since λ > 0 modes are M-orthogonal to the whole kernel (DERIVED-DESK). A same-space static solve is a new S1 capacitance computation, which conflicts with the E1 stop rule (`E1-CONTRACT.rev8.5.md:626`) unless separately re-approved. | Palace's lumped port. The pole problem would be N2R's discrete problem with P_F1 as a PEC short. **Whether pinned Palace can pose it is unchecked.** Whether a PB residue can be read from such a mode is also unchecked (CLAUDE.md §6). |

**The PA–PB static gap.**

- At level 2 of the static study, C′ − C = 0.0699 fF (arithmetic on recorded values).
- δ = C′/C − 1 grew at every level: 6.60e-4, then 7.07e-4, then 1.03e-3, classed NON-CONVERGENT (`static-refinement-study.md:38`).
- rev6 calls the gap "comparable to the R1 correction at the Master design point (≈ 0.07 fF)" [rev6:146, uncommitted]. No committed derivation of the 0.07 fF was found, so the size of ΔC_R1 relative to the gap is **UNRESOLVED**.

### 3.1 Conditions on PA's static evidence (parallel to PB's in §6)

1. **What the interval covers.** It is for the **meshed S1 model**: zero-thickness PEC, ε_r = 11.45 (an unapproved seed), a 4 mm cell. It says nothing about the device (`E1-CONTRACT.rev8.5.md:664`).
2. **The lower end.** C_lo^static is certified under the libm ASSUMPTION of contract §4.4 (E1 `summary.json` `reported_result.C_lo_static_basis`).
3. **The upper end.** C_hi is the frozen study's Dirichlet bound, copied into E1. It is "rigorous relative to the assembled operator up to the uncertified rho" (`C_hi_basis`). E1 cannot establish its convergence (`E1-CONTRACT.rev8.5.md:665`).
4. **The identification C_DC(PA) = C_static.** It is DERIVED. It is restated in committed text (`E1-CONTRACT.rev8.5.md:115`; `static-anchor-ec-bound-correction.md:82-84`), but its derivation is [rev6:141, uncommitted].
5. **Tolerance.** The E1 approval records tolerance set T0 and `COPIED_NUMBERS_WITHIN_SCOPE`. So no tolerance may be applied to any quantity formed from C_lo^static or C_hi (`E1-CONTRACT.rev8.5.md:592`).
6. **An unresolved tension, needing a human ruling.** The consumed approval does not authorise "any statement in frequency units, from any E1 number" (`E1-APPROVAL.consumed.json`, `does_not_authorise`). Yet contract §7 says the arithmetic K/(C_hi + C_J) "exists independently of E1" (`:592`).

## 4. The six combinations

How to read the table:

- The "E_C,F1F1: direction available" column means available **only after** a registered-definition decision and its own pre-declaration.
- K := e²/2h, and every E_C figure is omitted.
- Under M1, E_C,F1F1/h = K/(C_DC + C_J − ΔC_R1), and a lower bound is K/(C_up + C_J) (`E1-CONTRACT.rev8.5.md:120-123`).

| combination | C_DC | ΔC_R1 | 1/(C⁻¹)_FF | E_C,F1F1: direction available | needed for the other direction |
|---|---|---|---|---|---|
| **M1-PA** | C_static (both ends recorded, §3.1) | a_R1/ω_p², PA's R1 pole (a zero of Z_FF) | C_static − ΔC_R1 | **lower** bound from C_hi (no tolerance may be applied; §3.1) | either the triple (ω_p↓, ω_z↑, ω₂↓) with a completeness certificate (`:127-131`), or (ω_p↓, a_R1↑) (`:132-134`), under PA, with C_DC from below for the bound on 1/(C⁻¹)_FF. None is computed. The PA pole problem needs a same-space DC term (§3) |
| **M1-PB** | C′ (upper end recorded) | a_R1/ω_p², ω_p the PEC-short R1 pole | C′ − ΔC_R1 | **lower** bound from the C′ bound | the same routes under PB, **plus C′ from below** (§6) |
| **M2-PA** | C_static | not the relevant correction (all modes) | C_∞(PA) = 1/(fᵀM⁻¹f) (DERIVED-DESK), → 0 if the asserted divergence holds (§2) | formally a lower bound, **uninformative** if C_∞ → 0 | none possible, if the divergence holds |
| **M2-PB** | C′ | not the relevant correction | C_∞ = 0 as committed for "the registered sheet port" (`e1-exploratory-claims-correction.md:30`; attribution ambiguous, §2) | formally a lower bound, **uninformative** if C_∞ → 0 | none possible, if the divergence holds |
| **M3-PA** | C_static | not defined (band fit) | **not defined in any source**. M3 is realised only on sheet-port (PB) data (§2) | none | a definition of a PA band fit, and a PA realisation, first |
| **M3-PB** | C′ | not defined (band fit) | band-dependent, **can exceed C_DC** | **none** in either direction from static data | a band-fit protocol with its own convergence evidence, and readout identification (Route A's existing construction) |

**Bound directions under M1** (`E1-CONTRACT.rev8.5.md:118-134`):

- A lower bound on C_static bounds E_C **under no reading**.
- A certified pole/zero **pair** bounds ΔC_R1 **only from below**, which is the wrong direction (`:126`).
- An upper bound needs one of two routes, all under one declared port model:
  - the pole–zero–pole triple with a completeness certificate (`:127-131`); or
  - a_R1 from above with ω_p from below (`:132-134`).
- [rev6:222, uncommitted] adds "Route A outputs may not be used". The committed contract does not repeat this, so whether L_F-loaded (G_F) data are admissible for a ΔC̄ route is **open**.

**Committed conditional E_C statements already exist for both port models.** `corrections/static-anchor-ec-bound-correction.md` §3–§4:

- withdraws the static-anchor E_C lower-bound statements SA-1, SA-2, SA-3, SB-1 and SB-2 "as stated" (`:108-113`);
- replaces them with the conditional form K/(C_up + C_J), for PA (C_h) and PB (C′_h), at levels 0–1 only;
- makes that form usable only after a decision adopting M1 or M2 and declaring the port model and C_J (`:117`);
- states no level-2 figure (`:139`).

## 5. What the existing records establish

**First, status corrections.** Several committed headers are stale (the full list is in §10), and this note relies on the records, not the headers.

- **PO1 was executed once.**
  - It is approved in `.github/ladder-approval.json` and the approval is spent (`normalisation.md:111`). The record is `results/COUPLED-LADDER-O1-L2-PO1-20260920T204837Z`.
  - Four places still read "PREPARED, NOT APPROVED, NOT LAUNCHED" (§10).
  - The owner's approval is asserted in the file's `approved_by` text. As with every approval file here, it was committed by the agent and cannot be verified independently from the repository.
- **The first-moment diagnostic was executed on N2R twice.**
  - **Run 1** (35721700281) was UNQUALIFIED: independent relative residual 1.3313e-12 > 1e-12 (`experiments/first-moment-diagnostic/EXECUTION-APPROVAL.json`, `previous_outcome`).
  - **Run 2** (35730927756) returned `OMITTED_MOMENT_CERTIFIED_LOWER_BOUND` (`experiments/static-anchor-hypothesis/measurements.json`).
  - **How run 2 was authorised.** The same file was edited in place (`9ef5a52` → `4848eae`) from run_number 1 to run_number 2, with the config digest changed for the PCG stopping tolerance (1e-12 → 1e-14; the acceptance limit was unchanged).
  - **Provenance of run 2 is unresolved.**
    - The file states that it "authorises run number 2 … and nothing else" (`why_run_number_2`). Its scope line still reads "no retry", and it names no approver. The snapshot does not show whether explicit human approval covered run 2.
    - There is **no `results/` record**: run 2's numbers are transcribed from the job log, and the artefact sits behind an egress policy.
    - The run-2 figures in §5.3 and §7 are therefore provenance-qualified.

### 5.1 N1R and N2R (`results/COUPLED-LADDER-O1-L2-N1R-20260919T110053Z`, `…-N2R-20260918T061455Z`)

**What they are.**

- Eigen-solves of the L2 mesh with the 103.46 nH superinductor attached through Palace's lumped sheet port, P_F1 at attribute 10.
- Order 1, with one and two levels of Palace box refinement around the port: 84,485 and 103,411 DOF.
- N2R requested 6 eigenpairs and wrote 9 rows (`static-band-pairing.md:163`).
- There is **no probe block** in either configuration (`…N1R…/L2/solver/config.json:66-89`).
- Field archives exist only as uncommitted workflow artefacts, for six exported modes (`fem-spectral-mapping.md:360-361`).

| quantity | can establish | cannot establish |
|---|---|---|
| **loaded readout-like eigenfrequency** (not ω_p) | Point values for m2: 3.887131643 GHz (N1R) and 3.887370723 GHz (N2R). The local N1R→N2R movement is 6.15e-5. | ω_p of either port model. These are poles of G_F with L_F1 attached, not Y_FF poles. There is no convergence evidence: the uniform ladder L1/L2/L3 gives 3.693189 / 3.885511 / 4.087683 GHz (`…N1R…/report.md:153-162`). Element quality is a confound the box-refined records cannot separate (`…N1R…/report.md:104`; `…N2R…/report.md:113`). |
| **ω_z** | Conditional G_F zeros: 3.885610652 GHz (N1R) and 3.885825996 GHz (N2R), labelled "CONDITIONAL SPECTRAL CALCULATION — EM MAPPING UNVERIFIED" (`fem-spectral-mapping.md:248, 277-286`). Numerically they are also the unapproved draft's √β candidates; they are not a stated f_R1, since no R1 coordinate is adopted. | ω_z of either port model. A G_F zero is an eigenvalue of the **normalised rank-one removal** (K − Q/N), not of the assembled K_port removal (`:195-222`). |
| **ω₂** | Nothing. | A lower bound on the next pole, for four reasons. N1R's saved modes above m2 are port-operator-localised, and N2R's field-resonant 10.84 and 11.61 GHz modes are unidentified (`fem-spectral-mapping.md:147-150`). The 11.61 GHz mode has no saved field: "Wrote mode" lines appear only for modes 1–6 (`…N2R…/L2/solver/palace_log.txt:273-296`). No two runs share a higher mode. The second Y_FF pole is a PEC-short eigenmode under PB and a Z_FF zero under PA [rev6:142-145, uncommitted], and no record contains either. |
| **a_R1** | Only the G_F weight of m2 in the loaded pencil: \|p_2F\| = 9.219974e-4 (N1R) and 9.385321e-4 (N2R). | A Y_FF residue of any port model, from either side. The weight is also unstable: Δ\|p\| rel = 1.560e-01 from L2 to N1R (`…N1R…/report.md:109`), and 1.76× the frozen tolerance from N1 to N2R (`n2r-outcome.md:74`). |
| **completeness** | A desk-derived upper bound on the omitted rank-one weight: δ_saved = 7.838e-4 (N1R) and 7.454e-4 (N2R). N ∈ [0.999254583556, 1] on N2R. | A lowest-pole or pole-free-interval certificate. Four points: shift-and-invert gives no eigenvalue count; the eigenpair count Palace returns is an nconv artefact; 4 of 6 (N1R) and 5 of 9 (N2R) saved modes are port-operator-localised (`fem-spectral-mapping.md:140-150`); and more eigenpairs do not close the deficit (`:152-155`). |
| **readout identity** | Consistency-only evidence: p_2F < 0.5; a FIELD_DOMINATED label; a frequency in the 3.7–5.0 GHz window; an external V_R/V_F ≈ 3.73 that is path-dependent and not reproduced in-repo (`fem-spectral-mapping.md:305-316`). | The declared probe classification cannot execute: there are no probes and no `probe-E.csv`. Identification is **not established** (`r1-definition-decision.md:13-17`). |
| **C_DC, ΔC_R1, E_C, g, f_R1** | Nothing. Committed conditional f_R and g arithmetic exists (`fem-spectral-mapping.md:277-294`), labelled "not Route A evidence"; its figures are not restated here. | Any of them. |

### 5.2 PO1 (`results/COUPLED-LADDER-O1-L2-PO1-20260920T204837Z`)

**What it is.**

- N2R's discrete problem with the F1 port deactivated: K → K − K_port (`report.md:5`).
- The same change also alters the divergence-free projector's constraint set, so PO1 measures the operator change and the projector change together (`po1-n2r-field-correspondence-external.md:129-132`).
- It ran with a three-point probe block and recorded the face functional (`postpro/port-V.csv`, `port-EPR.csv`).
- It returned 8 converged modes, from 3.885828 to 23.817963 GHz, with none near zero (`report.md:56-63`).

| quantity | can establish | cannot establish |
|---|---|---|
| **ω_z (F-open)** | One-mesh point value: PO1 m1 = 3.885827871 GHz (`po1-n2r-field-correspondence-external.md:106`). Under PA only, this is the kind of quantity the first Y_FF zero is [rev6:158, uncommitted]. The recorded face functional gives the Z_FF modal weights on this mesh (desk reading, §3). | A certified ω_z of either model: one mesh, with no one-sided relation to the continuum value. Under PB its identification with the Y_FF zero is not derived. Two points are unreconciled in the sources. (i) **Floating island.** rev6's F-open column needs a floating island [rev6:116, uncommitted]. The PO1 document says the island potential is pinned in the discrete spaces (`po1-port-removed-control.md:96-100`). A desk argument (DERIVED-DESK, this note's review) suggests PO1's positive modes nonetheless carry zero net island charge. (ii) **Missing low roots.** N2R m1, the port-supported island mode, was expected before the run to move a long way, with no destination predeclared (`po1-port-removed-control.md:240-245`). No post-run document accounts for it. Likewise, the K − Q rank-one pencil's low root near 0.042 GHz, "the island's floating mode" (`fem-spectral-mapping.md:213-216`), has no PO1 counterpart. |
| **readout identity** | The predeclared classifier is **reported** to have returned INCONCLUSIVE FOR MODE IDENTITY, with 7 readout-like modes. That verdict and count are stated in the later correspondence notes (`po1-n2r-field-correspondence-external.md:140-142`); no committed PO1 record artefact computes them. A post-hoc external overlap pairs PO1 m1 with N2R m2 at 0.999927 (`:26-27`). | The physical readout mode. The overlap is "a separate post-hoc analysis by a different method" (`:16-18`), and its field values were not verified in-repo (`:75-80`). It pairs runs; it does not satisfy the declared rule. |
| **rank-one port-term error** | A single post-hoc point difference, for one mode on one mesh. PO1 m1 lies +900.586 Hz above the conditional K − Q root and +1874.896 Hz (4.825e-7 relative) above the conditional K − Q/N root, the G_F zero (`po1-n2r-field-correspondence-external.md:104-118`). The mode pairing rests on external field evidence not reproduced in-repo (`:135-139`). | A bound, or the error of K_port alone, for five reasons. The difference is confounded with the projector change. PO1's predeclaration "settles nothing" without a unique candidate, and there was none (`.github/ladder-approval.json:149`). No agree/disagree tolerance was predeclared for the comparison (`:142`), and the frozen Δf criterion is "reported and not gating" (`:158`). The sign of the shift in general is not established (`fem-spectral-mapping.md:170-174`); this one point is positive. Both reference roots take N as the truncated saved sum (`:203-204, 210`). |
| **ω_p, a_R1 (of Y_FF), ω₂, completeness, C_DC, ΔC_R1, E_C, g** | Nothing directly. | All of them. PO1 computes F-open modes (candidate zeros), not F-shorted poles, and no Y_FF residue. |

### 5.3 The first-moment work (`first-moment.md`, `first-moment-diagnostic.md`, `static-anchor-hypothesis.md`)

**What it is.** One mass solve for the complete first moment A = Re(fᴴM⁻¹f)/L on N2R's space. Its approval is scoped "No coupling extraction, no E_C, no g, no second level, no retry" (`EXECUTION-APPROVAL.json`; run-2 provenance caveat in §5).

| quantity | can establish | cannot establish |
|---|---|---|
| **completeness (as weight)** | The saved N2R set is incomplete in the first-moment sense: the omitted moment is ≥ 1420.315 GHz² (certified lower bound, run 2). The omitted weight is ≤ 7.454e-4, so its participation-weighted RMS frequency is ≥ 1380 GHz (`static-anchor-hypothesis.md:49-54`). | Where the omitted poles are. A low-frequency pole of weight ≤ 7.454e-4 is not excluded, and dark modes (p = 0) are invisible to every moment. The omitted-moment reading also assumes q ⟂ ker(K) (`first-moment.md:41-44`). |
| **M2 viability** | Growth of the complete first moment on this geometry: guaranteed lower bounds 340.13 → 659.72 → 1324.09 GHz² under uniform refinement (`static-anchor-hypothesis.md:55`). A sketched standard argument says it has no finite limit for a sheet-shaped port (`:78-84`). Restricted to curl-free fields, the same quotient is exactly 1/C_h (`:88-90`). | That the divergence is proved. It is a sketched argument with two refinement steps of rigorous lower bounds. |
| **ω_p, a_R1, ω_z, ω₂, rank-one error, E_C, g, f_R1** | Nothing. | All. A is a single scalar with no pole location, and E_C stays UNAVAILABLE by scope (`first-moment-diagnostic.md:214-215`). |

## 6. Does PB require a separately predeclared C′ bound?

**For an E_C lower bound, no new C′ computation is needed. For an E_C upper bound, yes: a C′ lower-bound treatment is needed, and none is a recorded result.**

- **E_C lower bound: C_DC from above.**
  - The frozen Dirichlet bound C′ ≤ 68.04546246723753 fF is the port-consistent upper bound (`E1-CONTRACT.rev8.5.md:121`). It stands after Q2 (`corrections/static-refinement-study-model-bracket-correction.md:371-376`). **No new C′ computation is needed.**
  - **The identification.** The discrete sheet-port identity is committed: `static-band-pairing.md:96-107`, "Proved, for Palace's actual port", with N = 1 and Σp/λ = L·C′_h, under a face condition that held on every static level (`static-refinement-study.md:17-18, 276-277`).
  - **Its checks.** Its 1e-12 verification was against the project's own dense model of Palace's port, not Palace (`docs/coupled-candidate/README.md:50`). Against Palace it was tested once, at level 0, where the verdict was CONSISTENT.
  - **Its application.** Applying it to PB's continuum DC limit is DERIVED (`E1-CONTRACT.rev8.5.md:115`) [rev6:143-145, uncommitted].
  - **The bound's own conditions.**
    - It is for the meshed model only.
    - It is rigorous relative to the assembled operator only up to the uncertified ρ.
    - C′ is CONVERGING, not CONVERGED (`static-refinement-study.md:35, 49-56`).
  - **Committed text disagrees on the scope of the rigorous bounds.**
    - The study's pre-execution text (`static-refinement-study.md:362-365`) names only C and S. So does `docs/coupled-candidate/README.md:51`.
    - The record's `bound_basis` (`summary.json:122`), study page `:50` and the Q2 correction (`:371-372`) include C′.
    - The record basis governs; the discrepancy is reported here for the human.
  - **Its tolerance scope is unresolved.**
    - The C′ value appears in the E1 contract text (`:105`) but in no E1 output.
    - Contract §7 places the PA arithmetic in the no-tolerance scope (`:592`) and is silent on the PB analogue. Whether the C′ figure, which sits in the contract file under `experiments/e1-s1-lower-bound/`, counts as "a number in E1's files" (`:592`) is part of the same ruling.
  - **The mesh scope** does not change this inequality. It limits combining C′ with Palace box-refined dynamic data (below).
- **E_C upper bound, or 1/(C⁻¹)_FF from below: C_DC from below.** Under M1-PB this needs a **C′ lower bound**, and **no recorded result supplies one.**
  - C′ ≥ C ≥ C_lo^static holds mathematically (`E1-CONTRACT.rev8.5.md:102`). But contract §10 says those relations "are not E1 results" (`:663`).
  - **The C′ and H model brackets are NOT ASSESSED.**
    - The Q2 correction record leaves them so as outside E1's scope (`:30, 347`) and records their treatment as an open human decision (`:475-479`).
    - On 2026-09-25 the human decided, in session, to leave them NOT ASSESSED unless a specific acceptance gate needs them, in which case they get their own pre-declaration. This note only reports that decision; it is not a registered decision record.
    - Being model-based ("not rigorous", `static-refinement-study.md:43-45`), the C′ bracket could not supply a certified lower bound anyway.
  - **So PB would need one of two things. Both are human decisions:**
    - **(a)** a separately predeclared decision admitting C′ ≥ C_lo^static as the bound. The uncommitted rev6 derivation already uses C_lo^static as C_DC from below for either port model, which presumes (a) [rev6:201, 213, 217, uncommitted]. The committed contract (`:131, 134`) does not.
    - **(b)** a new C′ lower-bound certificate on S1. That conflicts with the E1 stop rule, "E1 is the last capacitance computation on S1" (`:626`), unless it is explicitly re-approved as a redesign.
  - **Discretisation pairing.** The static bounds are on L2 and its uniform refinements, and N2R/PO1 are Palace box-refined. Contract `:126` requires one port model, but no source says whether it also requires one discretisation. Any pre-declaration must state this.
- **PA's position is the reverse.** Its C_DC is recorded at both ends (§3.1). Its pole and residue data need a same-space DC term (§3), which meets the same stop-rule conflict.

## 7. The gap register

| gap | current status (committed) | what exists | what is missing |
|---|---|---|---|
| **readout-mode identification** | **Not established.** The probe classification cannot run on N1R/N2R. PO1's is reported INCONCLUSIVE, with 7 readout-like modes (reported in the correspondence notes, not in the PO1 record). The ownership guard is withdrawn (`r1-definition-decision.md:8-17`). | Consistency-only indicators (§5.1). External, post-hoc field overlaps, not reproduced in-repo (§5.2). | An identification rule that can succeed; PO1's report suggests the three-point rule does not discriminate. Evidence produced in-repo. Identification **in the pencil the decision selects** (F-shorted or F-open for M1; loaded for M3). |
| **residue extraction** | No Y_FF residue under either port model in any record. | G_F weights of the loaded pencil, unstable under refinement. PO1's recorded face functional, which on a desk reading gives PA's Z_FF modal weights on one mesh (§3). | For PB: whether pinned Palace can yield a residue from an F-shorted mode is **unchecked** (CLAUDE.md §6). For PA: the same-space DC term and modal completeness. For the residue route: a_R1 from above. |
| **pole/zero bounds** | No F-shorted solve exists under either model. ω_z has only point candidates: the G_F zero (rank-one) and PO1 m1 (port-removed, one mesh). | Point values. Local-refinement stability of 6e-5, confounded with element quality. A uniform-ladder drift of 10.7 %. | ω_p↓ and ω₂↓, and ω_z↑. **No method in the repository gives one-sided (certified) bounds on discrete Maxwell eigenvalues relative to the continuum.** This is a method gap. Also: whether C_DC and dynamic data must share a discretisation (§6). |
| **spectral completeness** | No lowest-pole or pole-free-interval certificate. | Bounds on omitted *weight*: δ_saved, and N ∈ [0.99925, 1] on N2R. A lower bound on the omitted *moment*: ≥ 1420.315 GHz² (run 2, provenance-qualified). | A certificate of where poles are **not**. Moments cannot give one (§5.3). A counting method (for example, an inertia count at chosen shifts) is not in the repository; for Maxwell it would also need the exact dim ker K, which is undetermined (`po1-port-removed-control.md:104-123`). **Method gap.** |
| **rank-one port-term error** | "UNBOUNDED BY THE CURRENT EVIDENCE" (`fem-spectral-mapping.md:176-177`; `r1-definition-decision.md:28-39`). That "is not a claim that the error is large" (`r1-definition-decision.md:39`). No committed post-PO1 amendment. | One post-hoc, confounded, externally paired point difference, 4.8e-7 relative (§5.2). | A bound that separates K_port from the projector change. It matters for routes that use G_F zeros; an M1 route on F-shorted or F-open data does not need it. |
| **N** | Unmeasured on N1R/N2R. N = 1 is proved for the sheet port under a face condition (`static-band-pairing.md:96-107`), checked only on the static meshes. It is not reconciled with `fem-spectral-mapping.md:115-121`. | The window on N2R. | The DC response u = K⁺q. The low-frequency driven route is **blocked at source** at R = 0 (`docs/coupled-candidate/README.md:45`). It matters for a/N-type routes, not for M1. |

**Provenance items any follow-on must handle:**

- The Palace commit `a61c8cbe` is declared, not measured; the logs print only v0.13.0.
- The first-moment image source expires on 2026-12-21 (`EXECUTION-APPROVAL.json`).
- The field archives are uncommitted.
- `P_F1`, the R1 geometry and C_J are unapproved seeds.

## 8. The smallest registered-definition decision before any experiment

**Decision: adopt a reading together with a declared port model at P_F1.** No order between the two is implied, and the choice is the human's. The structure is as follows.

- **Why a reading is needed.** It fixes which quantities an experiment must target:
  - **M1** needs pole, residue and completeness data of one declared port model's Y_FF (`E1-CONTRACT.rev8.5.md:126`, for the M1 routes).
  - **M2** would leave nothing to measure under either port model if the asserted first-moment divergence holds. No source derives that for either port model (§2).
  - **M3** needs a band-fit protocol on loaded data. As defined in the sources, it is realised only on PB data.
- **Why a port model is needed with every reading.**
  - **M1.** Y_FF, and with it ω_p, a_R1, ω_z, ω₂ and completeness, exists "only once the weighting of the port face is declared" [rev6:137, uncommitted]. The two models' pole problems differ: PB's poles are PEC-short eigenmodes; PA's are Z_FF zeros, reachable from F-open modal data plus a same-space DC term [rev6:142-144, uncommitted; §3].
  - **M2.** The only statement M2 allows, K/(C_up + C_J), needs the port-model-consistent C_up (`E1-CONTRACT.rev8.5.md:120-121`). The committed conditional form requires a decision that "adopts reading M1 or M2 and declares the port model and C_J" (`corrections/static-anchor-ec-bound-correction.md:117`).
  - **M3.** It is realised only on PB data. M3 with PA would first need a PA definition (§2).
- **What the decision leaves unreconciled.** Route B's registered text is internally inconsistent under any reading (§2). Adopting M1 or M2 would also leave its statement that the fit determines E_C,F1F1 and f_R1 (`extraction-routes.md:246-252`) unreconciled with the reading. Whether the decision must also amend that text is **open**, and that bears on how large the decision really is.
- **What can wait.**
  - C_J (needed only when an E_C number is stated; the committed conditional form bundles it with the decision, `corrections/static-anchor-ec-bound-correction.md:117`).
  - The R1-coordinate decision, node basis vs normal mode (needed for g and f_R1).
  - The PB C′-lower-bound route of §6 (needed only for an E_C upper bound under PB).
- **Scope.** Under the repository's rules, even a decision scoped "for the next experiment only" is a registered-definition decision needing explicit approval (`E1-CONTRACT.rev8.5.md:113`; CLAUDE.md §3).

## 9. The smallest follow-on experiment or pre-declaration, per choice

Nothing here is proposed for execution. Any solve, field-archive analysis or pre-declaration needs explicit human approval (CLAUDE.md §3).

In every branch, the next missing quantity is closed only as a **point value, not a certified bound**: the method gaps of §7 remain.

| if the decision declares | next missing quantity | smallest follow-on |
|---|---|---|
| **M1-PB** | ω_p(PB), the R1 pole of the F-shorted sheet-port problem, with its identity | **Desk first:** determine against pinned Palace whether the F1 face can be posed as a PEC short, and whether a PB residue can be read from that mode. **Then:** a pre-declaration for one eigen-solve of N2R's discrete problem with P_F1 PEC-shorted. It would be the F-shorted counterpart of PO1: same mesh and refinement, a probe block, saved fields, and a **newly predeclared identification rule**. It must also state the discretisation-pairing rule (§6). |
| **M1-PA** | ω_p(PA), a zero of the face-open Z_FF | **Desk first:** set out, as DERIVED-DESK to be verified, how PA's Y_FF poles and residues follow from F-open modal data (PO1-type: eigenpairs plus the face functional) together with the same-space DC term 1/C_h. State what is missing: the same-space static solve, which conflicts with the E1 stop rule unless re-approved; whether ∇φ_island lies in the discrete space; modal completeness; the normalisation reconciliation; and identification. **Then:** a pre-declaration, if a same-space DC term is admitted. |
| **M2 (either)** | none, if the asserted divergence holds | Nothing to measure if the divergence holds (§2). First, an independent desk check of the PA identity and of the divergence argument (CLAUDE.md §7). |
| **M3-PB** | readout identity in the loaded pencil, and a band-fit convergence protocol | **Desk first:** a new identification rule and the fit protocol. **Then:** a pre-declaration for one probe-equipped rerun of N2R's configuration. |
| **M3-PA** | a definition | No source defines a band fit under PA. It needs a PA definition and realisation before any experiment. An N2R rerun gives PB data only. |

**Reported, not proposed.** The external correspondence note names in-repo reproduction of the PO1↔N2R field overlap as its next action. That would retire only the "external evidence" blocker. It closes no quantity on the E_C chain, needs access to the uncommitted field archives, and would need its own pre-declaration and approval.

## 10. Stale committed statements found (reported only; each needs a correction record, not an edit)

- **E1 contract status.** `E1-CONTRACT.rev8.5.md:3` reads "NOT APPROVED. NOT EXECUTED." E1 was executed. The file is digest-pinned by the consumed approval, so only a correction or pointer record is possible.
- **PO1 status.** Four places read "PREPARED, NOT APPROVED, NOT LAUNCHED":
  - `po1-port-removed-control.md:3`;
  - `experiments/PO1-port-removed-control/README.md:3`;
  - `experiments/PO1-port-removed-control/candidate.json:4`;
  - `docs/coupled-candidate/README.md:41`.
- **PO1 verdict.** `po1-n2r-field-correspondence.md:6-7` says the PO1 verdict stands "as recorded". No committed PO1 record artefact contains that verdict.
- **First-moment status.** These read "NOT EXECUTED", say no N2R solve exists, or call the approval file absent:
  - `first-moment-diagnostic.md:1, 9`;
  - the experiment README;
  - `docs/coupled-candidate/README.md:46`;
  - `docs/agent-contract-implementation.md:54`.
- **First-moment image binding.** `first-moment-image-qualification.md:114-116` still calls the image-binding requirement outstanding. It is addressed in `first-moment-diagnostic.md` §4a.
- **"NOT COMMITTED" headers on committed records.**
  - `corrections/static-anchor-ec-bound-correction.md:3` (committed `e40fd27`);
  - `corrections/e1-exploratory-claims-correction.md:3` (committed `411a910`).
- **E1 execution.** `corrections/e1-confirmation-s1-internal-sets-correction.md:277` says E1 has not been executed.
- **Mode count.** `r1-definition-decision.md:245` says "six modes in each record"; N2R wrote nine rows.
- **Rank-one error.** It is still "unbounded by the current evidence" (`fem-spectral-mapping.md:176-177, 333-335`), and no post-PO1 committed amendment exists. The PO1 point difference is post-hoc and does not by itself change the status.

## 11. What this note does not establish

- It establishes no value or bound for E_C,F1F1, g_F1R1 or f_R1. All stay UNAVAILABLE.
- It chooses no reading, port model or C_J.
- It asserts nothing about the device or the architecture.
- It does not establish that the complete first moment diverges, under either port model.
- It does not establish that any discrete eigenvalue bounds its continuum counterpart.
- It does not establish that the PB PEC-short problem can be posed, or a PB residue extracted, in pinned Palace. Both are unchecked.
- Its DERIVED-DESK statements are desk arguments, not source statements. They cover the PA identity C_∞(PA) = 1/(fᵀM⁻¹f), PA's poles from F-open data, the island harmonic field's membership of the discrete space, the irrelevance of the projector change to PA, and PO1's island charge. Each would need independent verification before any reliance (CLAUDE.md §7).
- It does not reconcile the uncommitted rev6 derivations into committed text. Several conclusions above rest on them and are marked.

## 12. Decision table

Nothing in the last column is proposed for execution. Each entry needs its own pre-declaration and explicit human approval.

| decision required | consequence | evidence already available | evidence still missing | next experiment if chosen |
|---|---|---|---|---|
| **Reading = M1** | E_C,F1F1/h = K/(C_DC + C_J − ΔC_R1). A lower bound K/(C_up + C_J) becomes available only after the decision and its own pre-declaration; under PA, which uses C_hi, it also needs a ruling on §3.1 item 6. An upper bound needs ΔC̄. Registered route text stays unreconciled (§8). | The routes are specified (`E1-CONTRACT.rev8.5.md:126-134`). Static C_DC evidence per port model. Committed conditional levels 0–1 statements (`corrections/static-anchor-ec-bound-correction.md` §4). | Pole, residue, triple and completeness data, plus **one-sided eigenvalue-bound and completeness methods**. | Per port model, below. |
| **Reading = M2** | E_C from C_∞. Degenerate under both port models if the asserted first-moment divergence holds; no source derives this for either (§2). Any lower bound is formal only. | Committed divergence assertion for both port models, with a sketched argument and two refinement steps of rigorous lower bounds (§5.3). Committed C_∞ = 0 for "the registered sheet port" (attribution ambiguous). The same conditional levels 0–1 statements, which `:117` also allows under M2. | A proof of the divergence. An independent check of the PA identity. | None to measure; first an independent desk check (CLAUDE.md §7). |
| **Reading = M3** | Band-fit value that can exceed C_DC. No static anchor in either direction. Realised only on PB data. | Loaded N1R/N2R data, conditional arithmetic only. | Readout identity, fit protocol, participation to about 1 % relative (`route-a-identifiability.md:171`), not established. A PA definition, if PA. | PB: a desk identification rule and protocol, then one probe-equipped N2R rerun. PA: none until defined. |
| **Port model = PA** | C_DC = C_static. Under M1, poles are Z_FF zeros, and the first Y_FF zero is the physical F-open resonance [rev6:142, 158, uncommitted]. Under M3, no PA definition exists. | C_static at both ends (conditions §3.1). PO1 F-open modes with face functional (one mesh; pinned-island caveat, §3, §5.2). | A same-space DC term (conflicts with the E1 stop rule unless separately re-approved), whether ∇φ_island lies in the discrete space, modal completeness, normalisation reconciliation, identification. | Desk derivation of PA poles from F-open data plus a DC term; a pre-declaration only if a same-space DC term is admitted. |
| **Port model = PB** | C_DC = C′. Under M1, poles are PEC-short eigenmodes [rev6:143-145, uncommitted], and the first-zero identification is not derived. M3 as sourced uses PB data. | C′ upper bound (conditions §6). Loaded and port-removed spectra, none giving a PB Y_FF pole, zero or residue (§5). | PEC-short posability and a residue method in pinned Palace. **C′ from below** (§6). Completeness. Identification. Discretisation pairing. | A desk check in pinned Palace, then one F-shorted N2R solve with a new identification rule. |
| **PB only: C′ lower-bound route** | Needed for any E_C upper bound under PB. | C′ ≥ C ≥ C_lo^static, mathematically (not an E1 result). | A decision to admit it, or a new certificate, which conflicts with the E1 stop rule unless re-approved as a redesign. | Decision only; no experiment without a redesign approval. |
| **C′/H brackets** (recorded as open, `static-refinement-study-model-bracket-correction.md:475-479`) | The human's 2026-09-25 in-session decision (leave NOT ASSESSED unless a gate needs them) is reported in §6 only; no registered decision records it. | Q2 record: NOT ASSESSED, outside E1's scope. | A recorded decision. | None. |
| **C_J** (can wait) | Enters every E_C figure once. | Unapproved 0 fF seed. | A declared value, or "absent". | None. |
| **R1 coordinate for g/f_R1** (can wait) | Fixes which frequency object is f_R1. | An unapproved draft with corrections. | Link to the E_C reading; coupling-definition §8 item 6 requires one capacitance model. | None before the above. |
