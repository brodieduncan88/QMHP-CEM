# E1 — static-capacitance lower-bound certificate for the S1 island (problem C): scientific experiment contract, revision 8.3

**Status: revision 8.3 (revision 8.2 plus the stand-in separation of D14). NOT APPROVED. NOT EXECUTED.**

- **Scope.** This document holds only the scientific experiment contract: the quantity, the bound direction, the geometry and configuration, the numerical certification criteria, the controls, the resources, the one-attempt rule and the stop conditions.
  - It does not specify the implementation mechanics: the attempt ledger, the output files and schemas, the output guard, and the failure paths. Those are verified against the frozen code with synthetic and negative tests (D8).
- **Repository state at drafting.** E1's inputs (§9) are byte-identical at `3d14c095e7ac4b8971f5476bd9a9f315ba7df2e1` (`palace/physical-coupled-candidate`) and at `e40fd275523148979f388934aef8da0393720372` (`claude/v2a-audit-deep-research-96omim`). The latter adds only the two correction records (`411a910`, `e40fd27`). Nothing here is evidence. COMPUTED-DESK numbers are scratch computations.
- **Superseded drafts.** Revisions 1–8.2.
  - Revision 6 is frozen as sha256 `bc59ac5bc252b314a43431315f78a86cc340c00bb913607ddb31d67252ac677c`. Its §2.3–§2.4 derivations were reviewed in three rounds, and §2 relies on their conclusions.
  - Revision 7 is frozen as sha256 `e62488c8aeb1b2892b3e814697663f4f093ac90b0be86f0e4d9ffb1a8192cdf5`. Its review found 4 distinct blocking findings. §11 maps every revision-7 finding to its fix.
  - Revision 8 is frozen as sha256 `340e54823f252dd254e36955959f039c97f2ae8dc094a0e21b94cd606c89d764`. Its four-lens review (bounds, certification, configuration, closure) found 0 blocking and 14 minor findings, 10 of them distinct. Revision 8.1 applies only those 10 fixes (§12) and changes nothing else (D13).
  - Revision 8.1 is frozen as sha256 `877464aeade14d313a9f24cd37fc86dc0a6d51e5403bb637320023f4b5d54df8`. Its focused closure review found 9 of the 10 findings closed, finding 2 partly closed, and 2 new minor text defects. Revision 8.2 applies only three text fixes: the §5 K4 rule (finding 2), the c ≥ 2 wording in §3.2 item 7, and the §6 stand-in description. It changes nothing else.
  - Revision 8.2 is frozen as sha256 `24ffff7d92c93757a13f9f6ba4505598be83b1628f4c5d6912c6abbbbdaf504c`. It was implemented at `90bf9eb`, and the review of that frozen code found finding D-1 (D14). Revision 8.3 changes only §3.2 item 2 and §6 (the stand-in and its separation from the S1 attempt sets), records D14 and adds §13. It changes nothing else. The correction record is `docs/coupled-candidate/corrections/e1-confirmation-s1-internal-sets-correction.md`.
- **Separate documents.** E1 code reads none of these.
  - The exploratory-claims correction record: `docs/coupled-candidate/corrections/e1-exploratory-claims-correction.md`, committed alone in `411a910`.
  - The non-E1 planning note, revision 7 (unchanged).
  - The static-anchor E_C-bound correction record: `docs/coupled-candidate/corrections/static-anchor-ec-bound-correction.md`, committed alone in `e40fd27`.
  - The sha256 of each is in §9.

**Claim labels:** SOURCE (file:line), DERIVED, COMPUTED-DESK, ASSUMPTION, HUMAN DECISION.

**Human decisions applied**

Earlier decisions:

- **D2.** E1.2-excl-R1 is an internal numerical nesting check, with no physical or E_C interpretation.
- **D3.** The E_C field is the constant `EC_NOT_EVALUATED_BY_E1`.
- **D4.** The earlier ~57 fF calculation is exploratory prior knowledge only. It is not used to tune configuration, thresholds or acceptance logic.
- **D5.** E1 certifies only the static problem-C capacitance bound, and makes no E_C claim and no suitability claim.

Decisions of 2026-09-23:

- **D8.** Three-part split. This contract holds only the science; the implementation mechanics are verified on frozen code; the correction record is separate.
- **D9.** The configuration is re-frozen by a value-independent rule: the tightest configuration that satisfies the frozen certification requirements within the 15-minute CPU / 4-GiB budget, without reference to exploratory S1 capacitance values (§3).
- **D10.** E1.1 is internal-only.
- **D11.** Conditional tolerance rule. E1 uses T0 and makes no suitability claim. Any T1–T4 criterion intended for later use with E1 must be adopted separately by the human before E1 execution approval. None is chosen here (§7).
- **D12 (revision-8 instruction).**
  - The selected configuration is kept only if the corrected symmetric-block implementation demonstrates the required resource margin.
  - No 2× CPU safety margin is claimed unless measured or predicted CPU is ≤ 450 s against the 900 s cap (§3.2 item 2, §6).
- **D13 (revision-8.1 instruction, 2026-09-24).** Revision 8.1 applies only the 10 minor fixes of the revision-8 review. It preserves the physics, the selected configuration and the earlier decisions:
  - g_E-only configuration screening (§3.2 item 4);
  - the full enclosure for certification (§4.3);
  - no Q2/C_br decision logic in configuration screening or acceptance. Q2 itself is kept unchanged, and whether it stays is confirmed at approval (§1);
  - E1.1 internal-only;
  - no E_C or suitability conclusion.
- **D14 (revision-8.3 instruction, 2026-09-24).** The Confirmation of the revision-8.2 implementation (`90bf9eb`) factorised and formed energies for S1's internal sets E1.1 and E1.1-half, because its stand-in's island was the selected island itself (review finding D-1). This is acknowledged as an unintended pre-execution computation, not as approved behaviour. No Confirmation or rehearsal numeric set may coincide with an S1 attempt set (§3.2 item 2, §6). Revision 8.3 changes only the stand-in wording needed to enforce this; the physics, the configuration, the thresholds, the Q2/C_br behaviour and the scope are unchanged.

---

## 1. The quantity

- **C_static (problem C).** The electrostatic capacitance of the F1 island in the meshed S1 model (mesh sha256 `d8dc1a92…c14428`).
  - The island (one galvanically isolated zero-thickness PEC sheet) is at 1 V.
  - Every other conductor is at 0 V: one grounded body made of the ground plane, all six box faces, and the R1 metal. The R1 metal is galvanically joined to the ground plane by its short (`config/coupled/v2a_five_node_candidate.json:404, 483`).
  - The port face P_F1 (attribute 10) is open.
  - The R1 tap faces (attributes 11 and 12) are dielectric.
  - Dielectrics: ε_r = 1 for z ∈ [0, 1.5] mm (tetrahedron attribute 1) and ε_r = 11.45 for z ∈ [−0.43, 0] mm (attribute 3), tan δ = 0.
  - All 3,040 boundary faces carry attribute 2 (grounded); there is no Neumann, absorbing or impedance boundary.
  - Non-geometric capacitance (C_J, array capacitance) is not part of C_static and does not enter E1.
- **Reported result.** C_static ∈ [C_lo^static, C_hi] fF.
  - **C_lo^static** := C_lo(E1.2), the certified Thomson/Galerkin lower bound for the main panel set E1.2 (§3, §4). The internal sets E1.1 and E1.2-excl-R1 do not enter it (D2, D10).
    - It is certified under the libm ASSUMPTION of §4.4, in the model's ε₀ convention.
    - That convention is ε₀ = `anchor_fem.EPSILON0` = 1/(μ₀·c_light²), with μ₀ = 4π×10⁻⁷ H/m and c_light = 299,792,458 m/s exactly, as used by the operator behind C_hi. This ε₀ is 5.4e-10 relative above the CODATA-2018 value.
    - C_static, C_lo^static and C_hi are all stated in the model convention.
  - **C_hi** := `classes.C.upper_bound_fF` of the verified baseline `results/STATIC-REFINEMENT-STUDY-20260923T062048Z/summary.json`: float64 67.9755386760262 fF, bit-exact.
    - It is the frozen Dirichlet upper bound on C_static.
    - It is rigorous relative to the assembled operator up to the uncertified ρ, which is estimated at ≤ 4.9e-7 of c and covered by BOUND_SAFETY = 1.001 if that estimate holds.
    - Beside it sits an uncertified assembly-term estimate of 9.6e-11 relative (SOURCE: `docs/coupled-candidate/static-refinement-study.md:50, 53-54, 222-227`).
  - Displays round C_lo^static down and C_hi up. Neither end is converted to GHz, and no E1 output contains a GHz or MHz quantity.
- **Secondary declared comparison (Q2).** Whether C_lo^static·(1 − γ) > C_br, with γ = 1e-6.
  - C_br := `classes.C.limit_bracket_model_based[1] × C_fF[2] / classes.C.values[2]`, recomputed in float64 from the verified baseline. It must equal 56.67470653023562 fF bit for bit. Index [1] is the upper end of the bracket.
  - If the inequality holds: `MODEL_BRACKET_PREMISE_REFUTED` for this model. The premise is "two terms, orders 1 and q ∈ (1, 2], coefficients of one sign". A separate correction record would follow; the frozen study is not edited.
  - Otherwise: `MODEL_BRACKET_NOT_CONTRADICTED`, which is not evidence for the bracket.
  - Q2 always carries the basis "conditional on the libm ASSUMPTION" (§4.4).
  - γ = 1e-6 is a conventional guard, fixed since revision 2 and not derived; it only makes the REFUTED label harder to reach.
  - Q2's criterion predates every exploratory S1 calculation that charged ground or R1 panels.
  - At approval, the human confirms that Q2 stays within D5; otherwise Q2 is dropped before execution.
- **Fixed statements in every state:**
  - correspondence to the registered operator: NOT_ESTABLISHED;
  - E_C,F1F1: `EC_NOT_EVALUATED_BY_E1`;
  - deviation from the registered value: NOT_EVALUATED;
  - suitability: SUITABILITY_NOT_ASSESSED;
  - blindness: not blind (exploratory prior knowledge exists; §8).

## 2. Bound direction and correspondence

1. **Thomson/Galerkin (E1).** C_static ≥ κ·Q²/(σᵀSσ) for any trial charge σ on metal with net island charge Q > 0, free charges on grounded metal, and no charge on the remaining metal (§4.1).
   - Here κ = 4π·ε₀·ε_avg·10¹² fF/mm, bounded below by κ_lo (§4.3), and S is in mm⁻¹.
   - This is a **lower** bound on C_static.
   - Because C′ ≥ C (Dirichlet principle), it is also mathematically a lower bound on C′, the static capacitance with the port-face potential held linear. E1 reports nothing about C′ (§10).
2. **Dirichlet (frozen study).** C_static ≤ C_hi.
   - C_hi bounds C_static, and hence anything ≤ C_static, such as the R1-floating and R1-removed capacitances.
   - It does not bound C′. The frozen `classes.Cprime.upper_bound_fF` = 68.04546246723753 fF bounds C′.
3. **The registered invariant.** E_C,F1F1 = e²(C⁻¹)_FF/2 for the circuit {F1, R1}.
   - R1 is the single-mode representation of a distributed resonator (`coupling-definition.md:46-63, 78-80`). It is declared as a quarter-wave CPW resonator galvanically shorted to ground (`config/coupled/v2a_five_node_candidate.json:404, 483, 561`).
   - R1 is a modal coordinate, not an electrostatic conductor.
   - The registered wording does not fix how the distributed, shorted R1 enters C. The readings differ:
     - **M1:** the DC limit plus the exact R1 pole and residue of one declared port model;
     - **M2:** the high-frequency limit;
     - **M3:** a band fit.
   - Adopting any reading is a registered-definition decision under CLAUDE.md §3, and E1 makes no such decision. The derivations are in the frozen revision 6, §2.3.
4. **Directions under the readings** (DERIVED; frozen revision 6, §2.3–§2.4).
   - **M1:** 1/(C⁻¹)_FF = C_DC − ΔC_R1, with ΔC_R1 ≥ 0. C_DC is the declared port model's DC limit: C for the transparent-face model PA, C′ for Palace's sheet port PB.
   - **M2:** 1/(C⁻¹)_FF = C_∞ ≤ C_DC.
   - **M3, or a Route B band fit:** 1/(C⁻¹)_FF can exceed C_DC.
   - Therefore:
     - **A lower bound on C_static bounds E_C,F1F1 under no reading.** An upper bound on E_C,F1F1 would need, under M1, a certified upper bound on ΔC_R1. Under M3 the relation is not one-signed.
     - **An upper bound on the declared port model's DC limit C_DC** (C_static under PA; C′ under PB) gives a lower bound on E_C,F1F1/h, K/(C_up + C_J), with K := e²/(2h) ≈ 19.37022932465913 fF·GHz. This holds only after a registered-definition decision adopting M1 or M2, and then only with:
       - the port-model-consistent upper bound (C_hi under PA; the C′ bound under PB);
       - a declared C_J (0 fF at the current unapproved seed);
       - validity up to the uncertified ρ.

       Among the readings above, only M1 and M2 give this; the floating-R1 and R1-removed readings are not adopted.
     - **Routes to an upper bound on ΔC_R1 under M1** (for a later experiment only). A certified pole/zero pair is **not** sufficient: it bounds ΔC_R1 only from below. Each sufficient route below is certified one-sided, and all its inputs come from one declared port model.
       - **A pole–zero–pole triple.** It needs a lower bound on ω_p, an upper bound on ω_z and a lower bound on ω₂, with ω₂,lo > ω_z,hi. It also needs a spectral-completeness certificate that R1 is the lowest pole and that no pole with nonzero residue lies in (ω_z, ω₂).
         - This gives C_DC/(1+p) ≤ ΔC_R1 ≤ C_DC·r/(p+r), with p = ω_p²/(ω_z²−ω_p²) and r = ω₂²/(ω₂²−ω_z²).
         - Write p_lo for p evaluated at ω_p,lo and ω_z,hi, and r̄ for r evaluated at ω₂,lo and ω_z,hi.
         - The upper bound ΔC̄ = C_DC,hi·r̄/(p_lo + r̄) needs C_DC from above (the port-consistent upper bound).
         - The bound 1/(C⁻¹)_FF ≥ C_DC,lo·p_lo/(p_lo + r̄) needs C_DC from below.
       - **The R1 term.** It needs the coefficient a_R1 of a_R1·s/(s² + ω_p²) in Y_FF (twice the complex residue at s = jω_p) from above, and ω_p from below, under one declared port model.
         - This gives ΔC̄ = ā_R1/ω_p,lo².
         - The bound on 1/(C⁻¹)_FF then uses that model's DC limit from below: 1/(C⁻¹)_FF ≥ C_DC,lo − ā_R1/ω_p,lo².
5. **Correspondence status: NOT ESTABLISHED.**
   - **E1 establishes no bound, in either direction, on 1/(C⁻¹)_F1F1 or E_C,F1F1.**
   - No E1 value may be used as, or combined into, such a bound without a separate registered-definition decision under CLAUDE.md §3 and its own pre-declaration.
   - A reading that treats R1 as a floating conductor is excluded by requirement R-1, and a reading that treats R1 as removed metal is not adopted. No statement about E_C,F1F1 may be drawn from any E1 value under either.
   - R-1's fallback label INCONCLUSIVE is superseded by D3 and D5. E1 makes no E_C statement, its field is `EC_NOT_EVALUATED_BY_E1`, and correspondence is reported as NOT_ESTABLISHED in every state (frozen revision 6 §12).
6. **Internal sets (D2, D10).** E1.1 (island panels only) and E1.2-excl-R1 (E1.2 without the panels on R1 metal) are computed only for the nesting consistency check K4.
   - No physical or E_C interpretation is attached to their values, in E1 or in any later record. This is a rule of use, not a claim about what the numbers bound mathematically.
   - Neither enters C_lo^static, and neither is reported as a result.

## 3. Geometry and configuration

### 3.1 Fixed geometric definitions (mesh sha256 `d8dc1a92…c14428`, geometry and tags only)

- **Island.** The node-connected attribute-4 component of 283 triangles and 189 nodes.
  - Its measured bounding box is x ∈ [−0.6749999999999999, −0.5249999999999999], y ∈ [−0.07500000000000001, 0.075] mm.
  - Its area is 0.022500000000000003 mm².
- **Ground body.** The remaining attribute-4 triangles (ground plane and R1 metal).
- **R1 metal** (used only for E1.2-excl-R1 and control N2).
  1. Cut every edge of the ground-body triangles whose end nodes satisfy |y + 0.433| ≤ 1e-9 mm and 1.12 − 1e-9 ≤ x ≤ 1.17 + 1e-9 mm. Measured: 8 edges between 9 nodes.
  2. R1 is the edge-connected component containing the unique triangle that contains (−0.455, 0).
  3. Required: exactly 2 components (5,610 and 5,531 triangles), 5,531 R1 triangles, and |A_R1 − 0.35915| ≤ 1e-12 mm².
- **Lattices.** Base lattices of step h ∈ {5, 2.5, 1.25} µm: lines x = i/K and y = j/K mm for integers i and j, with K = 200, 400 and 800 respectively. Each line value is float(Fraction(i, K)).
  - Every metal boundary edge in W lies on a 5 µm lattice line to within 1e-15 mm. The float64 node coordinates carry offsets of up to about 1e-16 mm. The shrink below covers these offsets, and all counts come from exact clipping (COMPUTED-DESK, geometry only).
  - A 5 µm cell is a **candidate** if its rectangle, shrunk by 1e-9 mm on every side, is covered by ground-body triangles with exactly its area (exact rational clipping).
  - Finer cells inherit their parent 5 µm cell's candidacy.
- **Island panels.** Node coordinates x_k = −0.6 + s_k and y_k = s_k (mm), with s_k = sign(k)·(0.075 − 1e-12)·(1 − (1 − |k|/(n/2))^q) for k = −n/2 … n/2.
  - Each is evaluated once in float64, in exactly this order, and shared by adjacent panels.
  - The panels are the n × n tensor cells.
  - The nested (n/2) × (n/2) grid uses the even k and serves K4.
- **Ground panels** for window half-width w (a multiple of 0.04 mm) about (−0.6, 0), base lattice h, and threshold κ:
  - **Window.** W = [−0.6 − w, −0.6 + w] × [−w, w].
  - **Distance.** For each base cell c of W, d(c) is the chessboard distance, in base cells, to the nearest non-candidate base cell of W. It equals `scipy.ndimage.distance_transform_cdt(mask, metric="chessboard")` on W's candidate mask. Cells outside W do not count.
  - **Merging.** Blocks of m × m base cells, with m·h ∈ {2h, 4h, …} ≤ 40 µm and aligned to global multiples of m·h, are formed from the largest m to the smallest. A block becomes one panel if all its cells are candidates, not yet used, and have d ≥ κ·m.
  - **Remaining cells.** Every remaining candidate base cell becomes a panel.
  - **Shrink.** Every ground panel is shrunk by 1e-9 mm on each side.
  - **Nesting (pre-shrink partitions only).**
    - For fixed (h, n, q), the block partitions before the shrink are nested in κ and in w (with window bounds on the 0.04 mm grid).
    - A larger κ, or a larger w, refines the partition on the smaller window. d can only decrease when W grows, because cells outside W do not count, and a larger w adds panels outside the smaller window.
    - After the 1e-9 mm shrink, the trial spaces are **not** nested: a shrunk block covers the 2e-9 mm strips between its shrunk sub-blocks. So the Galerkin principle does not guarantee that a larger κ or w gives a larger value.
    - K4 does not use this nesting: its set pairs are exact subsets, or share island nodes.
- **Panel sets.**
  - E1.2 = island panels ∪ ground panels (including those on R1).
  - E1.2-excl-R1 = island panels ∪ ground panels fully covered by ground-body triangles not in R1.
  - E1.1 = island panels only.
  - E1.1-half = the nested (n/2)² island grid.

### 3.2 Selection rule (D9; value-independent)

The rule uses only exact geometry, host cost measurements on synthetic sets, and synthetic proxies. No exploratory S1 capacitance value, and no capacitance computed on S1 geometry, enters it.

1. **Family Φ.**
   - h ∈ {5, 2.5, 1.25} µm;
   - w ∈ {0.40, 0.48, 0.56, 0.64, 0.72} mm;
   - κ ∈ {0.50, 0.75, …, 10.00};
   - island n ∈ {32, 64} and q ∈ {1.5, 2.0, 2.5, …} in steps of 0.5. For each n, q rises until the float64 Cholesky fails on any of the three proxies (item 5). Larger q are treated as infeasible by the same criterion (ASSUMPTION: conditioning worsens monotonically with q);
   - blocks ≤ 40 µm.
2. **Budget feasibility.** Predicted CPU ≤ 450 s and predicted peak address space ≤ 2 GiB for the full run on S1-sized sets. These are 50 % of the 15 min / 4 GiB budget.
   - **Cost model (declared before any measurement of the corrected implementation).**
     - CPU = 2.22e-6·N² s + 1.5e-11·(N³ + N_x³) s + 200 s. N and N_x are the E1.2 and E1.2-excl-R1 sizes, and 200 s is a declared allowance for geometry, controls and the smaller sets.
     - The coefficients were measured on this host with synthetic sets (COMPUTED-DESK): symmetric float64 assembly, 0.39 µs per N², counted twice; the long-double enclosure pass, 1.44 µs per N²; Cholesky, 0.015 ns per N³.
     - N and N_x come from exact S1 geometry counts; no S1 matrix is assembled.
   - **Peak model.** 8(N² + N_x²) bytes + 0.5 GiB. This assumes that each float64 factorisation works in place, and that the geometry phase's working data is released before the capacitance phase. A factorisation that copies adds 8N² bytes.
   - **Confirmation (before execution approval).**
     - The frozen implementation's CPU and peak address space are measured end to end on synthetic stand-ins of the selected sizes (N = 9,995 and N_x = 6,710), with the S1 geometry phase and all controls.
     - The measurement is made twice: on the nominal path, and with every factorisation fallback forced for E1.2 and E1.2-excl-R1. Both runs must be ≤ 450 s CPU and ≤ 2 GiB.
     - The stand-in generator and its sha256 are frozen with the implementation.
     - **Separation (revision 8.3, D14).** No panel set on which the Confirmation, the rehearsal or any other pre-approval run assembles a matrix, factorises it or forms an energy may coincide with an S1 attempt set (E1.2, E1.2-excl-R1, E1.1 or E1.1-half), byte for byte or up to translation, axis reflection, exchange of x and y, and uniform scaling. The frozen stand-in (§6) satisfies this by construction. The frozen code also checks it against the S1 geometry phase's sets before the stand-in's capacitance phase, and computes nothing on the stand-in if the check fails.
     - Its g_E on proxy A for the selected configuration must be ≤ 1e-9 (item 4).
     - If any of these fails, the configuration is not re-selected silently. A new revision re-applies the rule with the measured coefficients and is reviewed before approval.
3. **Frontier.** For each (h, w, n), κ* is the largest κ in the grid that satisfies item 2, i.e. the finest pre-shrink partition within the budget. This is a rule, not a theorem about the shrunk trial spaces (§3.1).
4. **Certification feasibility.** A frontier configuration is feasible if both hold:
   - float64 Cholesky succeeds on all three proxies A, B and C (item 5); a failure on any proxy excludes it;
   - on proxy A, the float64/long-double energy consistency g_E := |σᵀS₆₄σ − Ê|/Ê is ≤ 1e-9, i.e. 100 × below the check (g) criterion (§4.5).
     - g_E is computed with the corrected routines: long-double entries including the areas, the symmetric block-pair pass, and in-place Cholesky.
     - The enclosure width is not part of g_E or of check (g). It depends on c, which is frozen at 64 (§4.3). It is recorded for every configuration as W (the width per unit of c), but it is not a criterion.
5. **Tightness order on generic synthetic proxies (not S1).**
   - Each proxy is an island [−0.075, 0.075]² mm at the origin, in a square ground hole of half-width 0.115 (A), 0.100 (B) or 0.130 mm (C), in a ground sheet filling the window [−w, w]², with the same panelling rules.
     - This window is W translated to the origin. −0.6 mm is a multiple of every block size, so the partition rules are unchanged.
   - Configuration x is **tighter** than y iff x's float64 Galerkin value Q is larger than y's on **all three** proxies (unanimous dominance).
   - A difference on which the proxies disagree is not resolved.
6. **Selection.** Take the maximal elements, under this order, of the certification-feasible frontier configurations. If there is more than one, choose the one with the largest smallest panel side (numerical robustness), then the smallest N.
7. **Disclosure of the rule's development** (synthetic data only, and exact S1 geometry counts; no S1 capacitance value at any step). In order (ASSUMPTION for the order: file modification times):
   - **First grid.** h ∈ {5, 2.5} µm, κ ≥ 1.0, and q ∈ {1.5, 2.0} for n = 32 (q = 1.5 only for n = 64). 25 proxy-A results were computed on it (`frontier.py`, `proxy_results.jsonl`).
   - **Extension.** The grid was extended to h = 1.25 µm, κ ≥ 0.5 and q ≤ 3.0 (`frontier2.py`, `proxy_results2.jsonl`). Proxy-A certification diagnostics were computed for 26 configurations (`cert_results.jsonl`).
   - **Proxies B and C** (ground-hole half-widths 0.100 and 0.130 mm; `proxy_hole.py`) were introduced after the proxy-A results and those diagnostics had been seen.
   - **The δ-variant** (`select.py`, `selection.json`) was computed after proxies B and C existed.
     - It used a mean normalised score over proxies A, B and C, and declared ties within a global proxy resolution δ: the largest relative difference whose sign reverses between two proxies, δ = 0.29 %.
     - That left 86 of 112 configurations tied, so it would have selected on robustness alone (q = 1.5).
   - **Unanimous dominance over the three proxies** (`select2.py`) was adopted after the δ-variant's output had been seen, because it uses the proxies' pairwise agreement.
   - **The q extension.** The grid was extended to q = 3.5 and 4.0 after unanimous dominance had selected a q = 3.0 configuration at the edge of the q ≤ 3.0 grid.
   - **Revision-8 changes after the revision-7 review.**
     - Item 4's second condition was corrected from "check (g) ≤ 1e-9" to g_E ≤ 1e-9. The revision-7 selection script had computed g_E, not check (g).
     - **The g_E-only form was a choice** (preserved by D13).
       - The revision-7 configuration review had proposed a width-inclusive form, g_E + c·W + γ-term ≤ 1e-9. That review showed that form excludes the selected configuration for every c ≥ 2, including the frozen c = 64.
       - The revision-8 configuration review computed, from the recorded W values with c = 64, that the width-inclusive form would admit 27 of the 127 Cholesky-feasible configurations (all with n = 32 and q ≤ 2.0) and would select (h, w, n, q, κ) = (2.5 µm, 0.64 mm, 32, 2.0, 1.5). That figure is COMPUTED-DESK by that review, on synthetic data only, and is not re-derived here.
       - At the same time, check (g) (§4.5) was redefined to exclude the width, so that no E1 criterion depends on c.
       - Reason: the width lowers C_lo rigorously and never invalidates it. For the selected configuration it is about 800 times smaller than the smallest dominance margin, so it is a tightness cost, not a certification requirement.
       - The choice was made knowing its consequence for the selection.
     - g_E was re-evaluated with the corrected routines for all 127 Cholesky-feasible configurations.
     - The resource model was confirmed with a corrected prototype (§6).
     - Neither change can alter the selection, because excluding configurations cannot remove a unique maximal element that is itself feasible (DERIVED). The selection was re-run and is unchanged.

**Result of the rule** (COMPUTED-DESK; every script and result is listed with its sha256 in the selection manifests, §9).

- **Frontier.** 28 of the 30 (h, w, n) points have a feasible κ.
- **Cholesky condition.** 155 configurations were evaluated on all three proxies.
  - For 127, float64 Cholesky succeeds on all three.
  - For 28, it fails on all three: all 15 with n = 32 and q = 4.0, and all 13 with n = 64 and q = 3.5.
  - No configuration fails on only some proxies.
- **g_E condition** (proxy A, corrected routines, all 127): g_E ≤ 1e-9 for 114 of the 127, ranging from 5.7e-14 to 1.5e-10. It exceeds 1e-9 for all 13 configurations with n = 64 and q = 3.0 (2.33e-9 to 2.45e-9), which are excluded.
- **Certification-feasible:** 114 configurations.
- **Unanimous dominance.** Exactly one configuration exceeds every other Cholesky-feasible configuration on all three proxies, so the tie-break is not needed. Its margins over the runner-up (q = 3.0, same h, w, n, κ) are 3.4e-5, 4.1e-5 and 3.1e-5 on A, B and C.
- **Selected configuration on proxy A** (corrected routines): N = 4,080. The float64 Cholesky succeeds without a fallback, with squared pivot ratio 8.7e-5. g_E = 9.2e-11 (≤ 1e-9). W = 6.0e-10 per unit of c, so with c = 64 the enclosure width is 3.9e-8 of C̃. That is about 800 times smaller than the smallest dominance margin (3.1e-5).
- **The K2 pairs of §5 as frozen** (s_min = 0.004577637 µm, h_min = 1.25 µm). Synthetic tests with two placements (R_i starting at x = 0 as frozen, and the separated pairs shifted to start at x = −0.6 mm):
  - long double against dblquad (the K2 criterion, 1e-9): ≤ 8.7e-12;
  - float64 against long double (criterion 1e-6): ≤ 1.5e-8;
  - dblquad against a 60-digit reference: ≤ 8.7e-12;
  - 0 IntegrationWarnings.

  These maxima depend on placement and implementation.
- **The revision 3–6 configuration** (h = 5 µm, w = 0.40 mm, fixed thresholds 6 and 20, q = 1.5) is withdrawn.

**Frozen configuration** (unchanged from revision 7).

- **Island.** n = 32 and q = 3.5 in the §3.1 node formula.
  - The panels are 32 × 32 = 1,024, with sides from 0.004577637 µm (at the edges) to 15.164251 µm (at the centre).
  - E1.1-half is the nested 16 × 16 = 256 grid (even k).
- **Ground.**
  - base lattice h = 1.25 µm (lines x = i/800 mm, y = j/800 mm);
  - w = 0.48 mm, so W = [−1.08, −0.12] × [−0.48, 0.48] mm;
  - κ = 1.25;
  - blocks of m = 32, 16, 8, 4 and 2 base cells (40, 20, 10, 5 and 2.5 µm), each allowed where all cells are unused candidates with d ≥ 1.25·m;
  - every other candidate base cell is a 1.25 µm panel.
- **Resources.**
  - Predicted by the item-2 model: 441 s CPU (limit 450 s) and 1.58 GiB peak (limit 2 GiB).
  - Measured with the corrected prototype: 279–281 s CPU on a quiet host (up to 322 s nominal and about 356 s on the forced-fallback path under concurrent load), and 1.43 GiB peak with the geometry data released (§6).

### 3.3 Expected counts (COMPUTED-DESK, geometry only)

- **Window W (5 µm cells).** 36,864 cells:
  - 33,394 candidates, 1,152 of them fully in R1;
  - 900 fully in the island;
  - 2,570 without metal;
  - **0 partially covered.** Every metal boundary edge in W lies on a 5 µm lattice line to within 1e-15 mm (§3.1).
- **E1.2 ground panels.** 8,971, by side:

  | side | panels |
  |---|---|
  | 1.25 µm | 5,264 |
  | 2.5 µm | 1,316 |
  | 5 µm | 1,376 |
  | 10 µm | 352 |
  | 20 µm | 260 |
  | 40 µm | 403 |

  3,285 lie on R1 metal, and none straddles R1 and the rest of the ground body.
- **E1.2-excl-R1 ground panels:** 5,686.
- **Set sizes:**
  - N(E1.2) = 9,995;
  - N(E1.2-excl-R1) = 6,710;
  - N(E1.1) = 1,024;
  - N(E1.1-half) = 256.
- **Exact containment** passes for every final panel: 1,024 island, 8,971 ground-body, and 5,686 for the ground body without R1.
- **R1 cut:** 8 cut edges; components of 5,610 and 5,531 triangles.

E1 recomputes every count and fails qualification on any difference.

## 4. Numerical certification criteria

### 4.1 Validity of the bound

- **Kernel.** G(r) = 1/(4π·ε₀·ε_avg·r) for charges on z = 0, with ε_avg = (1 + ε_r)/2.
- **Why the half-space factor is exact.**
  - The potential of a planar charge layer in the two-half-space medium is even in z. So E_z vanishes on z = 0 off the charged panels, and D_z = 0 there on both sides.
  - On a panel, D_z jumps by exactly the panel's charge density.
  - Metal that carries no panel charge carries no flux: ground beyond W, the uncharged part of R1, and all of R1 in E1.1 and E1.2-excl-R1.
  - Charged R1 panels in E1.2 are admissible, because R1 is part of the grounded body in problem C.
- **Truncation.** Truncating the resulting field at the grounded walls, floor and lid only removes energy. Hence C_static ≥ κ·Q²/(σᵀSσ) for every σ, with κ = 4π·ε₀·ε_avg·10¹² fF/mm ≥ κ_lo.
- **Required model facts**, checked exactly, else UNQUALIFIED:
  - the tetrahedron attribute set is {1, 3}; attribute-1 tetrahedra have z ≥ 0 and attribute-3 tetrahedra z ≤ 0; none straddles z = 0; every z = 0 face lies between an attribute-1 and an attribute-3 tetrahedron;
  - every face is shared by at most two tetrahedra, on opposite sides (exact orientation test), and no tetrahedron has zero volume;
  - every node lies in [−2, 2]² × [−0.43, 1.5] (exact comparison of the float64 coordinates with Fraction(−2), Fraction(2), Fraction(−0.43) and Fraction(1.5));
  - the faces in exactly one tetrahedron are exactly the 3,040 attribute-2 faces. Each lies in one of the six wall planes x = Fraction(−2), x = Fraction(2), y = Fraction(−2), y = Fraction(2), z = Fraction(−0.43), z = Fraction(1.5), by exact comparison of all three vertices;
  - the absolute volumes sum, exactly in rationals from Fraction(float64) coordinates, to (Fraction(2) − Fraction(−2))²·(Fraction(1.5) − Fraction(−0.43)), with the attribute-3 part 16·(0 − Fraction(−0.43)) and the attribute-1 part 24 mm³;
  - the z = 0 faces have exact total area 16 mm², and every z = 0 edge lies on the square boundary or in exactly two faces on opposite sides;
  - the tagged z = 0 triangles are distinct tetrahedral faces;
  - every attribute-4 triangle has all three nodes at z = 0 exactly. So the (x, y) containment of §4.2 places panel charge only on metal.

  Together these certify that the two dielectrics tile the box. The boundary faces lie on the wall planes, so the cover count is constant in the box, and the volume sum forces it to be 1.
- **Dielectric constant used in the certificate.** ε_avg,lo := (1 + Fraction(11.45))/2, the exact value of the float64 11.45 used by the operator behind C_hi. It lies 3.6e-16 below 249/40, so the bound holds under either reading of ε_r.

### 4.2 Exact admissibility

- **Island panels and every final ground panel** must be covered by the relevant triangles with exactly their area:
  - island triangles for island panels;
  - ground-body triangles for E1.2;
  - ground-body triangles not in R1 for E1.2-excl-R1.
- **Clipping** is exact in rationals (Sutherland–Hodgman on Fraction(float64) coordinates). Triangles are pre-selected by bounding box, so a missed triangle can only cause a false refusal.

### 4.3 Entries and enclosure

- **Entries.** S_ij := I_ij/(A_i·A_j) in mm⁻¹.
  - I_ij = Σ_{p,q,s,t∈{1,2}} (−1)^{p+q+s+t} F(x_p^(i) − x_q^(j), y_s^(i) − y_t^(j)).
  - F(X, Y) = ½X²|Y|·ln((|Y|+r)/|X|) + ½|X|Y²·ln((|X|+r)/|Y|) − r³/6, with r = (X² + Y²)^{1/2}, F(0, Y) = −|Y|³/6, F(X, 0) = −|X|³/6 and F(0, 0) = 0.
  - S̃_ij is evaluated in x87 long double, including the coordinate differences, A_i, A_j and their product. It uses only logl, sqrtl, +, −, × and ÷, from the float64 panel coordinates used by the containment proof.
  - Each evaluated value S̃_ij (i ≤ j) is used for both (i, j) and (j, i).
- **Entry error bound.** B̃_ij := c·u_ld·Σ_k r̃_k³/(Ã_i·Ã_j), evaluated in long double from the same intermediates, with u_ld = 2⁻⁶⁴ and **c := 64 (frozen)**.
  - **Requirement.** The frozen code carries a derivation, from its operation sequence, of a constant c₀ with |S̃_ij − S_ij| ≤ c₀·u_ld·Σ_k r_k³/(A_i·A_j) for every pair (exact r_k and A).
    - The derivation counts the coordinate differences, the log argument, every product, A_i, A_j and the final division, with logl ≤ 2 ulp and sqrtl ≤ 0.5 ulp (ASSUMPTION, §4.4).
    - It also gives the exact rounding count q_B of the B̃ computation.
    - The requirement is c₀ ≤ 64·(1 − γ_{q_B}), which gives B̃_ij ≥ |S̃_ij − S_ij| for every pair.
    - The derivation and its number are reviewed in the frozen-code review. A larger c₀ refuses the run before anything is spent.
    - Notation: c₀ denotes this derived entry-error constant here, in §5 K2b and in §8. The speed of light is written c_light (§1; κ_lo below).
  - **Desk estimate** (DERIVED, first order, for the routine structure of the corrected prototype):
    - c₀ ≈ 8.3: 4.45 from the evaluation of F; 15 × 1/6 from the 16-term corner sum; 8 × 1/6 from the areas, their product and the division.
    - q_B ≈ 31.
    - c = 64 therefore leaves a factor of about 7.7.
  - A bound relative to Σ|F_k| or |S_ij| is not valid, for two reasons:
    - F vanishes on |Y| = 0.3975554·|X| and |X| = 0.3975554·|Y|;
    - the corner sum cancels by up to about 10²² for the frozen side classes. COMPUTED-DESK (revision-7 review): Σ|F_k|/|I| = 2.1e22 for two 4.58 nm panels at the window diagonal, and 5.7e12 for 4.58 nm against 40 µm at 0.5 mm.

    Long-double entries of such pairs are accurate only to within B̃_ij.
- **Energy.** Three long-double sums are formed by the same block-pair structure:
  - Ê := fl(σᵀS̃σ);
  - Ŵ := fl(Σ_ij |σ_i|·B̃_ij·|σ_j|);
  - Ĝ := fl(Σ_ij |σ_i|·|S̃_ij|·|σ_j|).

  Then

      E_up := Ê + (Ŵ + γ_m·Ĝ)/(1 − γ_m),   γ_m := m·u_ld/(1 − m·u_ld),   m := m(N_pass),

  evaluated exactly in Fraction arithmetic from the long-double values.
  - **Validity** (DERIVED):
    - σᵀSσ ≤ σᵀS̃σ + Σ|σ_i||σ_j|B̃_ij, by the entry bound;
    - |Ê − σᵀS̃σ| ≤ γ_m·Σ|σ_i||S̃_ij||σ_j|;
    - each exact non-negative sum is at most its computed value divided by (1 − γ_m).
    - Hence σᵀSσ ≤ E_up.
  - **Summation structure.** The set is split into blocks of 256 panels (the last block smaller), n_b = ⌈N/256⌉ blocks. For each block pair (I, J) with J ≥ I, in a fixed order:
    - the block S̃_IJ is formed;
    - t_IJ = σ_Iᵀ(S̃_IJ·σ_J) is computed (and likewise with |σ|, B̃ and |S̃|);
    - t_IJ is doubled when J > I (exact);
    - t_IJ is added to a running accumulator that starts at 0.
  - **Exact rounding count.** Each term σ_i·S̃_ij·σ_j passes through at most m(N) := 2·min(N, 256) + P(N) − 1 roundings, with P(N) = n_b(n_b + 1)/2 block pairs. The count is:
    - one multiplication S̃_ij·σ_j;
    - at most |J| − 1 additions in the block matrix–vector product;
    - one multiplication by σ_i;
    - at most |I| − 1 additions in the block dot product;
    - at most P(N) − 1 additions in the accumulator (the first addition to the zero accumulator is exact).

    This holds for any order of summation inside each sum, because a sum of k terms formed by pairwise additions passes each term through at most k − 1 additions.
  - **Values.**

    | pass | N | n_b | P(N) | m(N) |
    |---|---|---|---|---|
    | E1.2 (also used for E1.2-excl-R1) | 9,995 | 40 | 820 | 1,331 |
    | E1.1 | 1,024 | 4 | 10 | 521 |
    | E1.1-half | 256 | 1 | 1 | 512 |
    | K3, n = 32 | 3,080 | 13 | 91 | 602 |
    | K3, n = 16 | 732 | 3 | 6 | 517 |

    E1.2-excl-R1 is evaluated in the E1.2 pass with its σ extended by zeros. Zero terms add no rounding, so the pass's m(9,995) applies. The code computes m for each pass from this formula and uses γ_{m}.
  - **No underflow.** The rounding model above assumes that no product underflows.
    - E1 records, per pass, the smallest nonzero |σ_i|, |S̃_ij| and B̃_ij. With s := min|σ| and e := min(|S̃|, B̃) over nonzero values, it requires s·e ≥ 2⁻¹⁶³⁰⁰ and s²·e·2⁻⁶⁴ ≥ 2⁻¹⁶³⁰⁰, else UNQUALIFIED. The smallest normal long double is 2⁻¹⁶³⁸², so this leaves a factor of 2⁸² for rounding.
    - Why this suffices (DERIVED): every nonzero partial sum of long-double products is a multiple of the ulp of the smallest product, so its magnitude is at least 2⁻⁶⁴ times that product. So the first products are ≥ s·e, and the second products are ≥ s²·e·2⁻⁶⁴, up to rounding. Both are normal.
    - In the entry routine every nonzero intermediate exceeds 2⁻⁵⁰⁰⁰ in magnitude, because its inputs are float64 coordinate differences (|X| ≥ 2⁻¹⁰⁷⁴ when nonzero) combined in a fixed, short sequence (DERIVED).
    - COMPUTED-DESK (prototype, synthetic stand-in): the product bound is 2.1e-49.
  - Every B̃_ij must be finite and non-negative; Ê, Ŵ and Ĝ must be finite; Ŵ and Ĝ must be non-negative; and E_up must be positive. Otherwise UNQUALIFIED.
- **Charge.** Q = Σ_island σ_i, exact in Fraction arithmetic, and Q > 0 is required.
- **Result.** C_lo(P) = RD(Q²·κ_lo/E_up) fF, evaluated exactly and rounded toward −∞ to float64 once.
  - κ_lo := min(4·π_lo·Fraction(EPSILON0), 10⁷/c_light²)·ε_avg,lo·10¹² fF/mm, with c_light = 299,792,458 m/s exactly. Here EPSILON0 = `anchor_fem.EPSILON0` = 1/(μ₀·c_light²) in float64, π_lo is the 35-digit truncation of π, and ×10¹² converts F/m to fF/mm.
  - COMPUTED-DESK: κ_lo ≈ 692.6246598933774 fF/mm; the two ε₀ forms differ by 7.8e-17 relative.
  - The exact rational κ_lo and ε_avg,lo are frozen as "p/q" strings, recomputed before anything is spent, and must match.
  - The same function with ε_avg = 1 serves K3.

### 4.4 Assumption and probes

- **ASSUMPTION:** glibc logl ≤ 2 ulp and sqrtl correctly rounded, with numpy longdouble log and sqrt dispatching to them.
- **Pinned versions:** python 3.11.15, numpy 2.4.6, scipy 1.17.1, glibc 2.39. A mismatch refuses the run.
- **Dispatch probe.** Before anything is spent, np.log and np.sqrt on np.longdouble arrays, through the same code path as the entry routine, are compared with libm logl and sqrtl.
  - libm is called through ctypes, with c_longdouble subclass types and arguments built from the 80-bit bytes, not through float.
  - The fixed inputs include values not representable in float64.
  - The comparison is on the 80-bit x87 value only: the first 10 bytes of each 16-byte buffer. The 6 padding bytes are ignored.
  - Any mismatch refuses the run.
- **Arithmetic probe.** Before anything is spent, +, −, × and ÷ on np.longdouble arrays, on fixed operands, must reproduce the round-to-nearest 64-bit-significand result computed exactly in Fraction arithmetic. This detects an x87 precision-control word set to 53 bits.
  - The probe cases include s := 1 + 2⁻⁶³, formed by a long-double addition at run time (not loaded as a constant). Then:
    - s − 1 must equal 2⁻⁶³; under 53-bit precision control it gives 0;
    - s·s must equal 1 + 2⁻⁶² (round to nearest).
  - Each expected value is computed exactly in Fraction arithmetic.
  - A case such as 1 + 2⁻⁶⁴ = 1 tests only round-to-nearest, not the precision control, and is not sufficient on its own.
  - Any mismatch refuses the run.

### 4.5 Trial vector and float64 consistency

- **Trial vector.** σ is any float64 vector, and the bound is valid for every σ with Q > 0. E1 takes σ from the float64 Cholesky solve of S₆₄·σ = 1_island, where S₆₄ holds the float64 entries from the float64 routine.
  - Each factorisation works in place. The fallbacks and check (g) use the untouched other triangle and the saved diagonal, so no second N²-sized array is needed per set.
- **Fallbacks,** so that a numerical breakdown does not invalidate the bound. A step **fails** if its factorisation fails, if σ is not finite, or if Q ≤ 0. The steps, in order:
  1. Cholesky of S₆₄.
  2. The Jacobi-scaled system (D^{-1/2}S₆₄D^{-1/2})y = D^{-1/2}·1_island, σ = D^{-1/2}y, with D = diag(S₆₄).
  3. The scaled matrix shifted by τ·I, with τ taken in turn from 2⁻⁴⁰, 2⁻³⁰ and 2⁻²⁰ times its largest diagonal entry.
  4. **Last resort:** σ = D⁻¹·1_island. If this σ is not finite or has Q ≤ 0, E1 is UNQUALIFIED.
  - The path taken is recorded. σ is recorded before any enclosure is computed and is never changed.
  - Each set (E1.2, E1.2-excl-R1, E1.1, E1.1-half) uses its own solve.
  - The fallbacks keep the bound valid; they do not guarantee K4 (§5, K4 rule).
- **Check (g).**
  - Let C64(P) := Q²·κ_lo/(σᵀS₆₄σ), with the same σ, and C̃(P) := Q²·κ_lo/Ê(P).
  - Then |C64(P) − C̃(P)| ≤ 1e-7·C_lo(P) must hold, else UNQUALIFIED.
  - The enclosure width is not part of check (g). This is a float64/long-double consistency check, not a second certificate.

## 5. Controls

Numeric criteria are fixed. Every control and check is evaluated as `isfinite(value) and <inequality>`, so a non-finite quantity is a failure. Any failure is UNQUALIFIED. Controls K1–K3, K2b, N1–N4 and the S1 geometry checks run before any S1 matrix is assembled, and a failure there stops E1 before the S1 capacitance phase.

**Known answers (synthetic).**

- **K1.** The unit-square closed form must equal (4/3)(1 − √2) + 4·ln(1 + √2).
  - The reference is the 47-significant-digit decimal 2.9732095982473787025281856676395717980197454792, as an exact rational; a float64 reference is not permitted.
  - Relative difference ≤ 1e-17 in long double and ≤ 1e-13 in float64.
- **K2.** 24 fixed pairs, all in a regime where the quadrature reference is reliable. Criteria: long double against quadrature ≤ 1e-9 relative, and float64 against long double ≤ 1e-6 relative.
  - **Four contact cases** (µm):
    - R_j = [0, 20]² with R_i = [3, 4] × [2, 3] (contained);
    - R_i = [0, 5]² with R_j = [4, 14] × [2, 12] (partial overlap);
    - R_j = [0, 20]² with R_i = [20, 21] × [0, 1] (edge-sharing);
    - R_i = [0, 5]² with R_j = [5, 10]² (corner-sharing).
  - **Twenty separated pairs.**
    - The size pairs are {s_min/s_min, 40/40, h_min/40, s_min/h_min} µm, where s_min is the selected configuration's smallest island panel side and h_min its base lattice step (§3.2).
    - R_i, the first-named size, spans [0, s₁] in x and is centred on y = 0 (mm coordinates). R_j is centre-aligned with it in y, at edge-to-edge gaps {0.5, 1, 2, 10, 100}·h along +x, where h := the smaller side.
    - Pairs with extreme size ratios (s_min against 40 µm) are covered by K2b, not K2, because the quadrature raises round-off warnings there.
  - **Reference.** `scipy.integrate.dblquad` (epsabs = 0, epsrel = 1e-12) over R_j of the cancellation-free potential of a uniformly charged R_i, φ_i(x, y) = Σ_corners ±[X·asinh(Y/|X|) + Y·asinh(X/|Y|)], with the X = 0 and Y = 0 terms set to 0.
  - The criteria apply to the values only. dblquad IntegrationWarnings and error estimates are counted and recorded, and do not by themselves fail K2.
- **K2b.** Entry bound, on a fixed pair list:
  - **Random pairs.** Exactly 10,000 pairs from `numpy.random.default_rng(20260923)`, drawn in this order: an integer array of shape (10,000, 4), uniform on the 22 side classes; then 10,000 separations d, uniform on [0, D]; then 10,000 directions θ, uniform on [0, 2π).
    - The side classes are, sorted ascending, the 16 island widths s_{k+1} − s_k (k = 0…15, float64 from the §3.1 formula) and the ground sides 1.25, 2.5, 5, 10, 20 and 40 µm.
    - D = 0.96·√2 mm is the window diagonal.
    - Row k gives R_i = w_i × h_i centred at (−0.6, 0) mm, and R_j = w_j × h_j centred at (−0.6 + d·cos θ, d·sin θ).
    - Overlapping pairs are kept: the closed form holds for any relative position.
  - **F-zero pairs.** 96 pairs on the F-zero lines: 24 separations log-spaced from 0.05 mm to D; two size pairs (s_min/s_min and 40/40 µm squares); two orientations. With t = 0.3975553878545899, X = d/√(1 + t²) and Y = t·X, R_i is centred at (−0.6, 0) and R_j at (−0.6 + X, Y) or at (−0.6 + Y, X).
  - All coordinates are float64, and the reference uses them as exact decimals.
  - **Criteria.** Against a 60-digit decimal evaluation of the same closed form, for every pair:
    - |S̃_ij − S_ij| ≤ B̃_ij (the bound used by E1, c = 64);
    - |S̃_ij − S_ij| ≤ c₀·u_ld·Σ_k r_k³/(A_iA_j), with c₀ the code's derived constant. This tests the derivation, not only the margin.
  - The sha256 of the generated pair list is frozen with the implementation before the rehearsal.
  - COMPUTED-DESK (prototype): 0 violations; the largest implied constant was 0.30.
- **K3.** Staircase disk, free space (ε_avg = 1), a = 0.1 mm.
  - Lattice lines at x = i·a/n and y = j·a/n through the centre. A square is a panel iff all four corners satisfy x² + y² ≤ a². n = 32 gives 3,080 panels and n = 16 gives 732 (nested).
  - Criteria: 0.97 ≤ C_lo(disk, a/32)/D ≤ 1 and C_lo(disk, a/16) ≤ C_lo(disk, a/32).
  - D := 7.083350254096311 fF is frozen. It is the correctly rounded value of the exact product 8 × Fraction(8.854187817620389e-12) × 10⁻⁴ × 10¹⁵; the float64 left-to-right product 7.083350254096312 is not used.
  - D is not recomputed from κ_lo or EPSILON0, so K3 catches a units error in κ_lo.
- **K4 (S1, after the enclosures).** Consistency, not identity. With w(P) := C̃(P) − C_lo(P):
  1. C_lo(E1.1) ≥ C_lo(E1.1-half) − (w(E1.1) + w(E1.1-half));
  2. C_lo(E1.1) ≤ C_lo(E1.2-excl-R1) + w(E1.1) + w(E1.2-excl-R1) + 1e-9·C_lo(E1.2-excl-R1);
  3. C_lo(E1.2-excl-R1) ≤ C_lo(E1.2) + w(E1.2-excl-R1) + w(E1.2) + 1e-9·C_lo(E1.2).
  - **Rule for the last-resort σ.** Each inequality compares a smaller trial space with a larger one: the larger is E1.1 in inequality 1, E1.2-excl-R1 in inequality 2 and E1.2 in inequality 3.
    - An inequality is **not evaluated** if its larger set used the last-resort σ (§4.5 step 4). It is recorded as `NOT_EVALUATED_LAST_RESORT`, with the set named. This does not by itself make E1 UNQUALIFIED.
    - A last-resort σ in the smaller set is not a reason to skip. It gives that set a value no larger than its Galerkin optimum (every σ does), so it cannot by itself cause a failure, and the inequality is still evaluated.
    - Whether an evaluated inequality passes rests on the larger set's value, from its §4.5 step-1, step-2 or step-3 σ, not falling below the smaller set's value by more than the slack.
      - For a step-1 σ, the shortfall from the larger set's Galerkin optimum is expected, not derived, to be second order in the float64 solve error and far below the nesting gains, which are not known before execution.
      - For a step-2 (Jacobi-scaled) or step-3 (shifted) σ, reached only after step 1 has failed, no quantitative bound on the shortfall is derived or guaranteed, and the inequality can then fail.
      - Any failure is a K4 failure (UNQUALIFIED). This rule claims no protection against it.
    - For inequalities 2 and 3, the smaller set's float64 matrix is a principal submatrix of the larger set's, with the same Jacobi-scaled entries and the same shifts. By Cauchy interlacing, a step-2 or step-3 σ in the larger set together with a last-resort σ in the smaller set needs the larger set's scaled or shifted factorisation to succeed where the smaller set's failed. That is impossible in exact arithmetic and not expected in floating point, but it is not excluded.
    - The certified number does not depend on K4.
    - COMPUTED-DESK (prototype, forced fallbacks, synthetic): with the last-resort σ in E1.2-excl-R1 and E1.2, inequality 2 fails as predicted. Under this rule it is not evaluated.

**Negative controls, each with a positive counterpart.**

- **N1.** An island panel shifted 1e-6 mm into the gap is refused by exact containment; the unshifted panel is accepted.
- **N2.** A ground panel on R1 is refused for E1.2-excl-R1 and accepted for E1.2.
- **N3 (demonstration).** A plate fills the cross-section of an a × a box with Neumann side walls and lid, and a grounded floor at d = 10a. Its exact capacitance is ε₀a/10. The free-space Galerkin value exceeds it by more than 10× (desk: about 45×), which shows that the bound needs grounded walls.
- **N3b / N3c.** The model checks refuse a copy of the tag arrays with one boundary face set to attribute 0, and a copy with one attribute-3 tetrahedron relabelled 1. The unmodified arrays pass.
- **N4.** A copy of the entry routine replaces pairs with centroid distance 0 < d ≤ max(h_i, h_j) by A_iA_j/d, and pairs with d = 0 by A_iA_j/max(h_i, h_j). It must fail K2.

**Rehearsal (before execution approval, not part of the attempt).** The frozen code runs, in the test suite:

- the synthetic control phase (K1, K2, K2b, K3, N3, N4) with the frozen inputs and seed, which must pass;
- the S1 geometry phase (model checks, island, R1 cut, candidates, merge, containment, counts, N1, N2, N3b, N3c) on the pinned mesh, which must reproduce §3.3;
- the Confirmation run of §3.2 item 2, on synthetic stand-ins.

The geometry rehearsal assembles no matrix and computes no capacitance.

## 6. Resources

- **Invocation.** Run locally from the repository root with no arguments, under `env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 1260 .venv/bin/python experiments/e1-s1-lower-bound/driver.py`.
- **Budget:** 15 min CPU, 4 GiB address space, 20 min wall. Enforced as:
  - RLIMIT_CPU soft 900 s, hard 960 s;
  - RLIMIT_AS 4 GiB;
  - SIGALRM 1,200 s after process start;
  - outer SIGKILL at 1,260 s.
- **Prediction** (cost model, §3.2 item 2): 441 s CPU and 1.58 GiB peak.
- **Measured with the corrected prototype** (COMPUTED-DESK, synthetic).
  - The prototype is not the E1 implementation. It is the symmetric block-pair long-double pass, the exact m(N), in-place F-ordered Cholesky and the §4.5 fallbacks.
  - It ran on a synthetic stand-in of N = 9,995 and N_x = 6,710, with K1, K2, K2b, K3, N3, N4 and K4. The stand-in is built as follows (`standin.py`):
    - the selected island (n = 32, q = 3.5) at (−0.6, 0) mm;
    - 8,971 ground panels drawn at random (`default_rng(5)`) from a synthetic slotted ground sheet in W, panelled with the selected rules. The sheet has a hole of half-width 0.115 mm around the island; twelve 5 µm horizontal slots at evenly spaced y from −0.44 to 0.44 mm, for x < −0.75 mm; and 5 µm vertical slots starting at x = −0.44, −0.40, …, −0.16 mm (eight slots), for |y| < 0.40 mm;
    - the stand-in's R1 set is the 3,285 of those panels that come last when they are sorted by ascending centroid x, with ties broken by ascending centroid y.
  - **The frozen implementation's stand-in (revision 8.3, D14)** differs from the prototype's in its island only.
    - The prototype's island was the selected island itself, so its E1.1 and E1.1-half, and those of the revision-8.2 implementation's Confirmation, were S1's internal sets.
    - The frozen stand-in's island is 32 × 32 panels at (−0.6, 0) mm with node coordinates x_k = −0.6 + s_k(0.075) and y_k = s_k(0.0625) mm, where s_k(a) := sign(k)·(a − 1e-12)·(1 − (1 − |k|/16)^3.5) for k = −16 … 16, each evaluated once in float64. Its nested 16 × 16 grid uses the even k.
    - Everything else (the ground sheet, the draw, the R1 rule and the sizes) is unchanged. The separation rule of §3.2 item 2 applies to it.
  - **Size-class mix.** The stand-in matches N and N_x, but not the S1 size-class mix: it has 36 panels of 20 µm and 9 of 40 µm, against 260 and 403 on S1.
    - The entry cost does not depend on panel size. It rises with the fraction of exactly zero corner differences: 0.48 % in x and 0.44 % in y on the S1 E1.2 set, against 0.26 % and 0.15 % on the stand-in.
    - The revision-8 configuration review estimated that this changes the long-double pass by about 1 %. These are COMPUTED-DESK figures by that review; the S1 figures are geometry-only counts.
  - It included the S1 geometry phase: the island, the R1 cut, the candidates, the merge, exact containment of every panel, and the model checks, run three times as an upper bound for N3b/N3c. That phase was geometry only.
  - N1 and N2 (single-panel containment tests) were not run separately; their cost is negligible.
  - It ran under RLIMIT_AS = 4 GiB with single-threaded BLAS.

  | run | CPU | peak address space |
  |---|---|---|
  | nominal, geometry data released before the capacitance phase | 279.0 s | 1.43 GiB |
  | nominal, geometry data retained | 281.2 s | 1.91 GiB |
  | every factorisation fallback forced for E1.2 and E1.2-excl-R1 (worst path; measured without the geometry phase, whose CPU is added) | ≈ 308 s (nominal + 26.5 s) | 1.44 GiB without geometry data (the fallbacks allocate no further N²-sized array) |

  - Components of the nominal run: S1 geometry 63 s; controls 49 s (K2b 27 s, K3 19 s, K2 3 s); float64 assembly of E1.2 23 s; the two factorisations 7 s; the long-double pass 135 s (1.36 µs per N²); the small sets 2 s.
  - **Spread (COMPUTED-DESK by the revision-8 configuration review).** The review re-measured the same prototype on the same host under concurrent load. Every numerical result was bit-identical, and process CPU time rose by 5–16 %. All figures are ≤ 450 s.
    - nominal: 293.2 s with geometry data released, 321.8 s with it retained;
    - forced fallback: 284.6 s without the geometry phase, about 356 s with it;
    - peaks: 1.43, 1.91 and 1.44 GiB.
- **Margin.**
  - The measured CPU is ≤ 450 s, so the prototype supports a CPU margin of at least 2× against the 900 s cap.
    - On a quiet host: 3.2× nominal and 2.9× on the worst path.
    - Under concurrent load: 2.8× nominal and 2.5× on the worst path (see below).
    - For the frozen implementation this margin is claimed only if both Confirmation runs (nominal and forced fallback, §3.2 item 2) are ≤ 450 s.
  - The memory margin against 4 GiB is 2.8× with the geometry data released, and 2.1× retained.
  - The cost model over-predicts the prototype by about 1.6×. With measured coefficients the budget frontier would admit finer partitions. The rule is not re-applied with them: the declared rule re-applies only when the Confirmation limits are exceeded. The prototype's measurements do not exceed them. The Confirmation on the frozen implementation is still to be made.
- **Record.** Evidence goes in `results/E1-S1-LOWER-BOUND-<UTC>/`. The Galerkin matrix is not stored.

## 7. Tolerance rule (D11)

- E1 uses T0: no tolerance is applied by E1, and E1 makes no suitability claim.
- The candidate criteria T1–T4 are recorded, with derivation and sidedness, in the non-E1 planning note §5.
- **Any T1–T4 criterion intended for later use with E1's numbers must be adopted separately by the human, by a recorded decision identifying the criterion and the note's sha256, before E1 execution approval.** None is chosen here.
- No tolerance adopted after execution approval may ever be applied to any number in, or derived from, any E1 file.
- **Consequence (disclosed for the approval decision; no choice is made here).**
  - C_hi is a number in E1's files. If no criterion is adopted before execution approval, no tolerance may afterwards be applied to any quantity formed from C_lo^static or C_hi. That includes the planning note's conditional class-B arithmetic K/(C_hi + C_J) (note §3). That arithmetic exists independently of E1. It is a bound on E_C,F1F1 only under M1 or M2, after a registered-definition decision, and only with the conditions of §2 item 4.
  - Whether the scope should instead exclude numbers that E1 only copies from the frozen static study is a human decision. The approval must record it, and an approval without it is refused (§8). No choice is made here.
- Any later application also needs a registered-definition decision establishing the correspondence (§2 item 5), and that later record's own pre-declaration.
- E1's internal values (E1.1, E1.1-half, E1.2-excl-R1, C64, C̃, w, raw energies) never enter such an application.

## 8. One attempt, outcomes and stop conditions

- **One attempt, no retry** under any outcome.
- **Refusal before anything is spent** when any of the following holds:
  - a prior attempt exists;
  - the approval is absent, stale, or not bound to this contract, the code and the mesh;
  - the approval does not carry γ = 1e-6 and tolerance set T0;
  - the approval does not record the human's §7 scope decision (whether numbers that E1 only copies from the frozen static study are within the §7 rule);
  - an environment pin fails, or the dispatch or arithmetic probe (§4.4) fails;
  - the frozen κ_lo or ε_avg,lo does not match;
  - the code's derived c₀ exceeds 64·(1 − γ_{q_B}) (§4.3);
  - budget enforcement is unavailable, or the invocation differs;
  - an input digest (§9) differs;
  - C_hi or C_br is not bit-exact.

  A refused run spends nothing.
- **UNQUALIFIED**, and E1 stops, on any of:
  - a failed model check, island check, R1 cut, tiling, containment or count;
  - a failed control (a K4 inequality recorded `NOT_EVALUATED_LAST_RESORT` is not a failure);
  - a last-resort σ that is not finite or has Q ≤ 0;
  - Q ≤ 0, or a non-finite or non-positive energy;
  - a non-finite or negative enclosure component;
  - a failed no-underflow requirement (§4.3);
  - a failed check (g);
  - C_lo^static > C_hi (no slack);
  - a provenance re-measurement mismatch.

  An UNQUALIFIED run reports no capacitance value.
- **FAILED** on a catchable exception or a resource limit. A kernel SIGKILL leaves the spent record without a final manifest, quarantined by content.
- **Stop rule.** E1 is the last capacitance computation on S1, whatever its outcome. It is not followed by a level 3, a Crouzeix–Raviart/RT0 dual, or further S1 refinement. A certified-triple or residue experiment, a definition decision or a redesign each needs its own pre-declaration and approval.
- **Blindness.** Exploratory S1 capacitance values exist from before this contract. They are exploratory prior knowledge only, and they are corrected where misused in the separate correction record. E1 is not blind.
  - The configuration was re-selected by the rule of §3.2, which uses no S1 capacitance value.
  - The earlier configuration (revisions 3–6) was shaped by an exploratory margin, as disclosed in revision 6 §3.3, and is withdrawn.

## 9. Inputs and pinned environment

| input | read by E1 code | sha256 |
|---|---|---|
| mesh `results/COUPLED-LADDER-O1-L2-N2R-20260918T061455Z/L2/solver/coupled_chip_cell_L2.msh` | yes | `d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428` |
| baseline `results/STATIC-REFINEMENT-STUDY-20260923T062048Z/manifest.sha256` | yes | `e3e447068dea6b4c2790c29de7a34be77f971717fa6e40964f6e31fdee193622` |
| baseline `results/STATIC-REFINEMENT-STUDY-20260923T062048Z/summary.json` | yes | `7eca21f3688a662f0324003093de2902cfbd67503fa0de71f5c028df13181298` |
| `experiments/static-anchor-hypothesis/anchor_fem.py` | imported | `1123e38f16b6c443fd397330db568e8c5d4e18fa9a7c4dc844c599204e6437c1` |
| `orchestrator/manifest.py` | imported | `66a68dd40b8b2644efa8d204e723f27fe0a8e2127d038853e28271b8280d463f` |
| `docs/coupled-candidate/coupling-definition.md` (cited) | no | `143091c596b41c46baeed372ba6afdd6eb524c3c9d87e8af57bb9de19cc6b5d1` |
| `docs/coupled-candidate/static-refinement-study.md` (cited) | no | `f9ab52bb9f9c7764c8bfb66462c09de67d53e4a9e8bb10cbde29049a641174a1` |
| `config/coupled/v2a_five_node_candidate.json` (cited) | no | `6d1e21a75f44ed67027f6b69dcda93ee667d396a78737b223022cc78e7617dcf` |
| frozen revision 6 (derivations of §2) | no | `bc59ac5bc252b314a43431315f78a86cc340c00bb913607ddb31d67252ac677c` |
| frozen revision 7 (superseded; findings mapped in §11) | no | `e62488c8aeb1b2892b3e814697663f4f093ac90b0be86f0e4d9ffb1a8192cdf5` |
| frozen revision 8 (superseded; findings mapped in §12) | no | `340e54823f252dd254e36955959f039c97f2ae8dc094a0e21b94cd606c89d764` |
| frozen revision 8.1 (superseded by the three text fixes of revision 8.2) | no | `877464aeade14d313a9f24cd37fc86dc0a6d51e5403bb637320023f4b5d54df8` |
| frozen revision 8.2 (implemented at `90bf9eb`; superseded by the stand-in separation of revision 8.3) | no | `24ffff7d92c93757a13f9f6ba4505598be83b1628f4c5d6912c6abbbbdaf504c` |
| planning note revision 7 (non-E1; T1–T4) | never | `6338ae236763eceef175fbc5c9240ab3355784d99d55de095deca79a18142f32` |
| exploratory-claims correction record (committed alone, `411a910`) | never | `7e3bc9441700811e6182b2893eec62b9d5a5d23f0d672a246f6c263b9c8a172c` |
| static-anchor E_C-bound correction record (committed alone, `e40fd27`) | never | `3156a9f0d828e9e685da6bc260df6dc7ce197c3e920a82c5908ee7794de5aed9` |
| configuration-selection manifest (revision 7; 40 files; S1 geometry counts and synthetic proxies only) | never | `e1b85e0cfc6a3b6a8a30e6c0773d01bbab853b9acdda8f7fe7b6280d9fc07060` |
| revision-8 cost and certification manifest (prototype, stand-ins, proxy-A g_E, K2 check, c₀ derivation; synthetic, and S1 geometry only) | never | `c781b6ef814292bffe33f17425375f3be20c81df1c3fcdcf3bf7e98ba34f008e` |

Pinned environment: python 3.11.15, numpy 2.4.6, scipy 1.17.1, glibc 2.39; `np.longdouble` has a 64-bit significand.

## 10. What E1 cannot establish

- **E_C,F1F1:** any bound, in either direction.
- **Deviation from the registered value, and suitability.**
- **g_F1R1 and f_R1:** they remain UNAVAILABLE.
- **Any other electrostatic problem.** E1 reports nothing about any electrostatic problem other than C: not C′, not R1 floating, not R1 removed. The mathematical relations of §2 items 1–2 are not E1 results.
- **The device's capacitance.** E1 bounds only the meshed model: zero-thickness PEC, ε_r = 11.45 (an unapproved seed), a 4 mm cell.
- **Convergence of the upper bound.**
- **The Route B §3.3 defects:** reported only.

## 11. Revision-7 findings and their fixes

| revision-7 finding (lens) | fix in revision 8 |
|---|---|
| BLOCKING: wall-plane clause dropped; tiling claim false; attribute-4 triangles not required at z = 0 (bounds, certification) | §4.1 model facts: nodes in the box, one-tetrahedron faces on the wall planes, attribute-4 triangles at z = 0; the tiling argument stated |
| BLOCKING: depth inequality false at N = 256, 257 (certification, closure) | §4.3: block-pair structure with the exact count m(N) = 2·min(N, 256) + P(N) − 1 and γ_{m}; no depth inequality asserted; table of m per pass |
| BLOCKING: "check (g) ≤ 1e-9" was g_E; c unbounded (certification, configuration) | §3.2 item 4 uses g_E; §4.5 check (g) excludes the width; c := 64 frozen, with c₀ ≤ 64(1 − γ_{q_B}) required before anything is spent; g_E recomputed for all 127 Cholesky-feasible configurations |
| BLOCKING: nesting claimed for shrunk trial spaces (configuration) | §3.1 nesting restricted to pre-shrink partitions; §3.2 item 3 frontier stated as a rule |
| MINOR: full-row structure vs cost model (certification) | §4.3 symmetric block-pair structure; §6 measured cost with it |
| MINOR: fallback σ can fail K4; σ finiteness (certification) | §4.5 step-failure rule and finiteness; §5 K4 rule for the last-resort σ |
| MINOR: K2 desk figures, dblquad warnings, placement (certification, closure) | §5 K2 pairs in the quadrature-reliable regime, placement fixed, warnings recorded not failing; §3.2 figures re-measured with dblquad |
| MINOR: K2b only partly fixed (closure) | §5 K2b: exact count, draw order, distributions, F-zero pairs, and a second criterion against c₀ |
| MINOR: cancellation "10¹⁰" (closure) | §4.3: about 10²², with the COMPUTED-DESK figures |
| MINOR: triple/residue C_DC sides, one port model, ω₂,lo > ω_z,hi (bounds, closure) | §2 item 4, both route bullets |
| MINOR: K undefined; PB lead clause (bounds) | §2 item 4 lead clause on C_DC with K defined |
| MINOR: "shorted" mis-cited (bounds) | §1 and §2 item 3 cite the configuration JSON |
| MINOR: libm basis and ε₀ convention missing from the result (bounds) | §1 Reported result |
| MINOR: §7 scope covers C_hi, consequence undisclosed (bounds) | §7 Consequence bullet |
| MINOR: §10 vs §2 on C′ (bounds) | §10 "Any other electrostatic problem" |
| MINOR: κ missing from the Thomson inequality (bounds) | §2 item 1 and §4.1 Truncation |
| MINOR: R-1 INCONCLUSIVE supersession not carried (bounds) | §2 item 5 |
| MINOR: peak model ignores a copying Cholesky; confirmation has no outcome rule (configuration) | §3.2 item 2 peak model and Confirmation clause; §6 measured peak |
| MINOR: rule-development disclosure incomplete (configuration) | §3.2 item 7. The order of proxies B/C and the δ-variant was corrected, and the g_E-only choice disclosed, in revision 8.1 (§12) |
| MINOR: lattice statement false at float resolution (configuration) | §3.1 Lattices and §3.3 |
| (noted, not a finding) K1 literal has 47 significant digits | §5 K1 |
| (noted) Cholesky condition stated three ways | §3.2 items 1 and 4: "on any of the three proxies" |

## 12. Revision-8 findings and their fixes (revision 8.1)

The revision-8 review raised 14 minor findings, 10 of them distinct, and no blocking finding.

| revision-8 finding (lens) | fix in revision 8.1 |
|---|---|
| 1. c₀ denotes both the speed of light and the entry-error constant (bounds, certification) | §1 and §4.3 κ_lo use c_light; the notation note in §4.3 reserves c₀ for the entry-error constant |
| 2. The K4 last-resort rationale overclaims "cannot fail spuriously" for a scaled or shifted σ in the larger set (bounds, certification, closure) | §5 K4 rule rewritten: step-1 shortfall expected, not derived, to be second order; no quantitative guarantee for steps 2 and 3, where a failure is UNQUALIFIED; interlacing remark; K4 does not enter the certified number (step-1/2 wording corrected in revision 8.2) |
| 3. §7 "class-B bound … exists" lacks its reading qualifier (bounds) | §7 Consequence bullet: the planning note's conditional class-B arithmetic, a bound only under M1/M2 after a definition decision |
| 4. §8 does not require the §7 scope decision at approval (bounds) | §7 (the approval must record it) and a new §8 refusal condition; no choice is made |
| 5. Disclosure: the g_E-only choice and its consequence undisclosed; δ-variant out of order (configuration, closure) | §3.2 item 7: order corrected; width-inclusive alternative and its selection disclosed; §11 row updated |
| 6. The Confirmation measures only the nominal path; stand-in not pinned (configuration) | §3.2 item 2: nominal and forced-fallback runs, both ≤ 450 s and ≤ 2 GiB; stand-in generator frozen; §6 Margin |
| 7. "and they are not" presumes the Confirmation; spread under load unstated (configuration) | §6 Margin wording; review re-measurement and load spread stated; §3.2 Resources |
| 8. Stand-in size-class mix not stated (configuration) | §6: stand-in construction described exactly; size-class mix and the ~1 % cost effect stated |
| 9. Proxy window wording (configuration) | §3.2 item 5: window [−w, w]² about the origin |
| 10. Arithmetic-probe example cannot detect 53-bit precision control (closure) | §4.4: s := 1 + 2⁻⁶³ formed at run time; s − 1 and s·s cases |

Nothing else changes from revision 8. In particular, these are unchanged:

- the physics and bound directions (§1, §2, §4.1);
- the selected configuration and the counts (§3);
- the enclosure and certification criteria (§4.2–§4.5, apart from the notation note and the probe cases);
- the controls other than the K4 rationale (§5);
- Q2 (§1).

## 13. Revision-8.2 frozen-code finding and its fix (revision 8.3)

| finding (frozen-code review of `90bf9eb`) | fix in revision 8.3 |
|---|---|
| D-1: the Confirmation stand-in's island was the selected island, so the Confirmation factorised S1's internal sets E1.1 and E1.1-half and formed their energies (D14) | §3.2 item 2: the separation rule; §6: the frozen stand-in's island |

Nothing else changes from revision 8.2. The other findings of the same review (the approval and output guard, the failure path under stop signals, blocked stop signals, non-finite control values and the Confirmation's resource flags) concern implementation mechanics (D8). They are fixed in the frozen code without a contract change.
