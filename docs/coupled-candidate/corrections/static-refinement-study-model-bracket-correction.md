# Correction record: the static refinement study's class-C model bracket (E1 Q2: MODEL_BRACKET_PREMISE_REFUTED)

**Status: CORRECTION RECORD** (CLAUDE.md §1 and §14; AGENTS.md: "Make corrections in a new linked record").

- **Why it exists.** Prepared 2026-09-24. It is the record that E1 contract revision 8.5 §1 requires on `MODEL_BRACKET_PREMISE_REFUTED`: "A separate correction record would follow; the frozen study is not edited."
- **Human review.** A human reviewed a first draft on 2026-09-24 and directed the amendments this version carries.
- **Pre-commit review.** One narrow review of the amended text found four defects (two material minor, two minor) and four notes. This text addresses all eight.
- **It edits no evidence.** The frozen static study stays byte-unchanged: its record, manifest, page, driver and predeclaration. So does every evidence file cited here.
  - §8 gives sha256 digests measured at `9d0579d25ead4524c10a07e2c78bc0e9e2e6ec5f`, the parent of the commit that adds this record.
  - That commit also edits two documents, neither of them evidence: the E1 page and the coupled-candidate README.
    - Both get the pointers of §6. The README gets two: one in the E1 row and one in the static-study row.
    - The E1 page also gets one unrelated wording fix: C_br is recomputed bit-exactly, not copied.
  - Every other file in §8.1 is byte-unchanged by that commit.
- **Nothing was run for it.** No experiment, solver, Palace, Route A or E1 run, and no capacitance, energy or matrix computation, was performed. Its only computed numbers are arithmetic on recorded values, each listed in §8.2.

## Summary

- **Refuted, for this model only, and conditionally.** What is refuted is the premise behind the frozen study's class-C limit bracket: "two terms, orders 1 and q in (1, 2], coefficients of one sign".
  - Under that premise, the limit of the study's C_h sequence lies in 53.748899623323325–56.67470653023562 fF. The page rounds this to "53.75–56.68 fF".
  - E1 certifies C_static ≥ 57.220910660500294 fF, and every C_h is at least C_static. So the limit lies above the bracket, and the premise is false for this sequence.
  - Which condition of the premise fails is not identified.
- **The conditions (§4).**
  - the libm ASSUMPTION of contract §4.4;
  - a correct E1 implementation (it was reviewed);
  - the study and E1 solving the same problem C on the same meshed model;
  - no error in the study's level values large enough to overturn the comparison. The refutation survives worst-case level-value errors up to about 1.06e-3 relative. That is a threshold for the result, not a claim that the values are accurate to that level.
- **Affected claims (§6).**
  - Refuted: the class-C bracket (frozen record, study page, README row) and its level-2 remaining-error range (frozen record, study page).
  - Basis refuted: the S bracket. It is the C bracket mapped by S = k_S/C, and no new S value, bound or location is stated here.
  - Not assessed: the C′ and H brackets.
  - The exploratory items that used the bracket stay withdrawn.
- **Not concluded (§5).** This record concludes nothing about:
  - E_C, g, deviation, suitability, the device or the QMHP architecture;
  - C′, the C′ bracket or the H bracket;
  - any quantity in frequency units;
  - which part of the premise failed;
  - any new value, estimate or bracket for C.

## 1. The original claim (verbatim, unchanged)

### 1.1 The frozen record

`results/STATIC-REFINEMENT-STUDY-20260923T062048Z/summary.json` (sha256 `7eca21f3688a662f0324003093de2902cfbd67503fa0de71f5c028df13181298`; the record's `manifest.sha256` has sha256 `e3e447068dea6b4c2790c29de7a34be77f971717fa6e40964f6e31fdee193622`), `classes.C`:

```text
values                                 [3.2283807973564986, 2.320997120851734, 1.9193047424615535]
d1, d2                                 0.9073836765047645, 0.4016923783901807
R, p_obs                               2.2589018993618657, 1.1756216180628698
limit_bracket_model_based              [1.5176123640713728, 1.6002231852776319]
remaining_rel_error_at_level2_bracket  [0.1993981590315243, 0.2646870755009803]
bracket_assumption                     "two terms, orders 1 and q in (1, 2], coefficients of one sign"
cls                                    "CONVERGING"
```

- `C_fF` is [114.33875970637405, 82.2021777287097, 67.97553867601651].
  - The factor `C_fF[h] / values[h]` is 35.41675127048156 at all three levels.
  - In fF the bracket is therefore [53.748899623323325, 56.67470653023562].
  - Its upper end is E1's C_br. Contract §1 says of it: "It must equal 56.67470653023562 fF bit for bit."
- **The record never claimed the bracket as rigorous.** `bound_basis` ends: "A limit bracket, where given, is MODEL-BASED and carries its bracket_assumption; it is not covered by this basis."
- **`classes.S` carries a derived bracket.**
  - `limit_bracket_model_based_GHz2` is [4.320087630856472, 4.555250440093621].
  - It has the same `bracket_assumption` and the same `remaining_rel_error_at_level2_bracket` as class C.

### 1.2 The rule that produced it

`experiments/static-refinement-study/study_driver.py` (sha256 `97783b3b2749c6b4b21e266f4251038b216d5306dfeb8269786ea8c17304a799`), lines 401–403:

```text
    CONVERGING      R_min <= R <= R_max. The limit is bracketed, MODEL-BASED (two terms of
                    orders 1 and q in (1, 2], coefficients of one sign - an assumption the
                    theory does not supply), by X2 - d2 and X2 - d2 / (R - 1).
```

Lines 439–443 compute it:

```text
    lim1, lim_obs = X2 - d2, X2 - d2 / (R - 1.0)
    remaining_hi = d2 / lim1
    out.update(limit_bracket_model_based=[lim1, lim_obs],
               remaining_rel_error_at_level2_bracket=[d2 / (R - 1.0) / lim_obs, remaining_hi],
               bracket_assumption="two terms, orders 1 and q in (1, 2], coefficients of one sign")
```

- **The S bracket is derived from the C bracket.** Lines 618 and 626 build it as `sorted(k / e for e in c["limit_bracket_model_based"])`, with k = `S_GHz2 × energy_nd` at level 0.
- That is the C bracket mapped by `S_h = 1/((2π)² L_F C_h)` (`static-refinement-study.md:159`). This record writes the constant as k_S.

### 1.3 The study page and the README

`docs/coupled-candidate/static-refinement-study.md` (sha256 `f9ab52bb9f9c7764c8bfb66462c09de67d53e4a9e8bb10cbde29049a641174a1`), lines 43–48:

```text
- **Model-based limit brackets.** These are not rigorous. Each rests on an assumption the
  theory does not supply: two error terms, of orders 1 and `q ∈ (1, 2]`, with coefficients of
  one sign.
  - `C` in 53.75–56.68 fF, and `C′` in 53.83–56.78 fF;
  - `S` in 4.320–4.555 GHz², and `H` in 4.312–4.548 GHz²;
  - the level-2 remaining relative error is 19.9–26.5 %.
```

`docs/coupled-candidate/README.md` (sha256 `c72203bafdbce567744fcf9a9b812887b3ea285a4100f056002f7d2b127381a4`), line 51, in the static-study row:

```text
MODEL-BASED limit brackets C in 53.75-56.68 fF, S in 4.320-4.555 GHz^2, H in 4.312-4.548 GHz^2 (two one-sign error terms assumed)
```

### 1.4 What the study itself said about the premise

The study predicted this failure mode in advance. `experiments/static-refinement-study/predeclaration.json` (sha256 `29276d45f333be5a7e64678023b5f4e87cb8d24b411bc7bd34e70b389e9e54a5`), line 198, key `"theory"`:

> The one-sign premise is an ASSUMPTION the theory does not supply. Known mechanisms can violate it, such as the edge-vertex cutoff and the change of element-shape population under red refinement of a Gmsh mesh. With mixed signs, R < 2 can occur in the genuine order-1 regime, and a sequence inside [2, 4] can have its limit outside the bracket.

The page repeats it at lines 325–326: "A sequence inside the window can also have its limit outside the bracket."

## 2. What Q2 refuted

### 2.1 The premise, written out

Let X_h be the class-C value at levels 0, 1 and 2, with mesh sizes h₀, h₀/2 and h₀/4. Let X∞ := lim X_h under continued uniform refinement: the quantity the page calls "The continuum limit of `C`" (line 97). The premise P is that, at these three levels,

X_h − X∞ = a·h + b·h^q,

with the following three conditions:

- **P1 (form):** exactly these two terms, of orders 1 and q, and no other;
- **P2 (order):** 1 < q ≤ 2;
- **P3 (sign):** a and b have one sign.

### 2.2 P implies the bracket (re-derived for this record)

Put A = a·h₀/4, B = (2^q − 1)·b·(h₀/4)^q and m = 2^q − 1, so that 1 < m ≤ 3. Then:

- d2 = X1 − X2 = A + B;
- d1 = X0 − X1 = 2A + (m + 1)B, so R − 1 = (A + mB)/(A + B);
- X2 − X∞ = A + B/m.

The recorded `d2_certified_range` is positive, so d2 > 0, and under P3 both A ≥ 0 and B ≥ 0. Hence:

- X2 − X∞ ≤ A + B = d2, since m > 1;
- X2 − X∞ ≥ (A + B)²/(A + mB) = d2/(R − 1), since (A + mB)(A + B/m) − (A + B)² = AB(m + 1/m − 2) ≥ 0.

So X∞ ∈ [X2 − d2, X2 − d2/(R − 1)], which is the recorded bracket (`study_driver.py:439–443`). R − 1 then lies between 1 and m, so R ∈ [2, 2^q] ⊂ [2, 4]: the CONVERGING window.

The bracket is a correct consequence of P. This record finds no error in the study's arithmetic.

### 2.3 The refutation

1. Under P, lim C_h ≤ C_br = 56.67470653023562 fF, the bracket's upper end in fF.
2. Every C_h is at least C_static.
   - The energy error of the conforming P1 Dirichlet problem is E_h − E = ‖u − u_h‖²_a ≥ 0 (predeclaration.json `"theory"`; contract §2 item 2).
   - So lim C_h ≥ C_static.
3. E1 certifies C_static ≥ C_lo^static = 57.220910660500294 fF (§3), under the assumptions of §4.
4. Q2's test holds: C_lo^static·(1 − 10⁻⁶) = 57.22085343958963 fF > C_br.
   - The margin is 0.5461469093540162 fF, which is 0.9637 % of C_br.
   - It was re-checked for this record in exact rational arithmetic on the recorded floats.
5. So lim C_h ≥ 57.2209 fF > 56.6747 fF. This contradicts item 1, so P is false for this sequence.

### 2.4 Exactly what is refuted, and what is not

- **Refuted:** P, for the class-C sequence of the frozen study on this meshed model at levels 0–2. At least one of P1, P2 and P3 fails.
- **Not identified:** which one fails.
  - E1 bounds C_static. It does not measure the error terms.
  - This record does not diagnose them. The mechanisms quoted in §1.4 are the predeclaration's list of possibilities, not a finding.
- **Not refuted:**
  - the study's arithmetic and its certified values;
  - its class labels and its Dirichlet bounds;
  - the theory that the leading error term is of order 1.
- **R alone could not have shown this.** R = 2.2589 lies inside the window, and §1.4 already said that is not enough.

### 2.5 The same inequality at level 2

- **What P requires.** C_2 − lim C_h ≥ d2/(R − 1) in fF, which is C_fF[2] − C_br = 11.300832145780895 fF.
  - That is a level-2 remaining relative error of at least 19.94 %.
  - The recorded range is 19.94–26.47 %.
- **What E1 allows.** C_2 − lim C_h ≤ C_2 − C_lo^static = 10.754628015516218 fF.
  - That is a level-2 remaining relative error of at most 18.795 %.

This is Q2 restated without γ, not a second result. It is not an estimate of the discretisation error and not a convergence claim (§5).

### 2.6 The corrected statement

- **The corrected claim.** For problem C of the meshed S1 model, and under the assumptions of §4, the limit of the frozen study's class-C sequence is not in the model bracket [53.748899623323325, 56.67470653023562] fF.
- **The refuted premise.** The premise "two terms, orders 1 and q in (1, 2], coefficients of one sign" is false for that sequence at levels 0–2. Which of its conditions fails is not identified.
- **No replacement.** No model-based bracket replaces it.
- **What remains.** The only interval available is E1's reported one, C_static ∈ [57.220910, 67.975539] fF, on E1's stated bases (§3.2): C_lo^static certified under the libm ASSUMPTION, and C_hi rigorous relative to the assembled operator up to the uncertified ρ.

## 3. The E1 evidence

### 3.1 Record and execution

| item | value |
|---|---|
| record | `results/E1-S1-LOWER-BOUND-20260924T222847Z/`, committed at `40b8069` |
| manifest | `manifest.sha256`, sha256 `8d70ee11252c96fbbb0de5a666e963d8886273bafc7ad1aab4f36110f7f067ad`. All 12 entries verify (`sha256sum -c`, run for this record). It is pinned in `tests/test_frozen_evidence.py` |
| contract | revision 8.5, sha256 `2db93be49ee455f1da952acbe300f370d7614a8986c4151a9563adf805f00150` |
| approval | human; one execution at `4baeb67e5c135a97eb23d5e0057a086baa681f4e`. `E1-APPROVAL.consumed.json` has sha256 `b8f6883b6fa431aaca5778e135667bd5cfa0afd830822f908e263db263b8ee7d`. `tolerance_scope_decision` is `COPIED_NUMBERS_WITHIN_SCOPE` and `q2_within_D5` is true |
| run | 2026-09-24T22:28:47Z to 22:34:19Z. Exit 0 with empty stderr. CPU 331.4 s and peak address space 1.43 GiB, against a budget of 900 s and 4 GiB. No stop signal; `provenance_remeasured_equal` is true |
| inputs, measured at run time | contract, mesh `d8dc1a92159d7659c8a86bf3340241bf78ad751c71684a62fd14394b92c14428`, baseline summary and manifest (above), and six code files. All equal the approval's pins. C_hi and C_br are bit-exact |
| environment | python 3.11.15, numpy 2.4.6, scipy 1.17.1 and glibc 2.39. 80-bit long double (nmant 63); BLAS single-threaded |
| attempt | spent. `ATTEMPT-SPENT.json` names this record. There is no retry, and E1 is the last capacitance computation on S1 (contract §8) |

### 3.2 The reported result

`summary.json`, sha256 `3d1733ebad73fb53414f4b02cf2ff3865509b09305c9546efe2d014a0b6e9c11`, verbatim key–value excerpts (nesting flattened):

```text
"outcome": "QUALIFIED"
"C_lo_static_fF": 57.220910660500294
"C_hi_fF": 67.9755386760262
"display_fF": "[57.220910, 67.975539]"
"C_lo_static_basis": "certified Thomson/Galerkin lower bound for E1.2 under the libm ASSUMPTION of section 4.4, in the model's eps0 convention (1/(mu0 c_light^2), mu0 = 4 pi 1e-7 H/m)"
"C_hi_basis": "the frozen static study's Dirichlet upper bound, rigorous relative to the assembled operator up to the uncertified rho (contract section 1)"
"Q2": {"label": "MODEL_BRACKET_PREMISE_REFUTED", "gamma": "1e-6",
       "basis": "CONDITIONAL_ON_LIBM_ASSUMPTION (contract section 4.4)",
       "premise": "two terms, orders 1 and q in (1, 2], coefficients of one sign",
       "note": "for this model; a separate correction record follows; the frozen study is not edited"}
```

### 3.3 How C_lo^static is certified

- **The bound.** Thomson/Galerkin: C_static ≥ κ·Q²/(σᵀSσ) for a trial charge σ on the metal (contract §2 item 1).
  - E1.2 is the main panel set. It has 9,995 panels: 1,024 on the island and 8,971 on ground.
- **The E1.2 solve.**
  - It ran on the Cholesky path.
  - Check (g) was 2.72e-10 relative, against a limit of 1e-7.
  - The underflow requirement held.
  - The certified value is C_lo(P) = RD(Q²·κ_lo/E_up): E_up is the upper end of the energy enclosure, and the quotient is rounded toward −∞ (contract §4.3).
  - The recorded `width_rel` = (C̃ − C_lo)/C_lo, with C̃ = Q²·κ_lo/Ê, is 4.49e-8 (about 2.6e-6 fF). It is shown only for scale.
- **Probes, run before anything was spent.**
  - The dispatch probe compared 3,000 inputs (2,998 not representable in float64) with libm `logl` and `sqrtl`. There were 0 mismatches.
  - The arithmetic probe passed, including s − 1 = 2⁻⁶³ and s·s = 1 + 2⁻⁶².
  - The derived c₀ = 11.5649 is within its limit.

### 3.4 Controls and checks

All passed; every `failures` list is empty.

| control | recorded |
|---|---|
| K1: unit-square closed form | relative difference 7.7e-20 in long double (limit 1e-17) and 2.1e-16 in float64 (limit 1e-13) |
| K2: 24 pairs against quadrature | at most 7.0e-12 for long double against quadrature (limit 1e-9) and 1.5e-8 for float64 against long double (limit 1e-6); 0 quadrature warnings |
| K2b: entry bound | 10,096 pairs, 42 of them overlapping. The pair list matches its frozen sha256. 0 violations of the bound or of the c₀ bound. Largest implied constant 0.297, against c₀ = 11.56 |
| K3: staircase disk, a known answer | C_lo(a/32)/D = 0.977106 (required 0.97–1). C_lo(a/16) = 6.7353 fF ≤ C_lo(a/32) = 6.9212 fF |
| N3: demonstration | the free-space Galerkin value is 45.49 times the exact value (required: more than 10) |
| N4: broken entry routine | fails K2, on 12 pairs, as required |
| N1, N2, N3b, N3c | every refusal and every positive counterpart as required |
| S1 model checks | 19 of 19 passed |
| K4: nesting consistency of the internal sets | inequalities 1–3 PASS |

The internal sets' values (E1.1, E1.1-half, E1.2-excl-R1) are in `internal-sets.json` for audit only. They are not results and are not used here (contract D2, D10).

### 3.5 Before execution

- **The approval candidate.** `4baeb67` bound, by sha256:
  - the contract and every code file;
  - the mesh and the baseline;
  - the environment pins, the invocation and the budget;
  - the fresh rehearsal and both Confirmations.
- **Its checks.** CI run 264 passed on it. One focused final review returned CLEAN_WITH_NOTES, with nothing blocking (`EXECUTION-LOG.json`).
- **Fixed in advance.** Contract §1: "Q2's criterion predates every exploratory S1 calculation that charged ground or R1 panels." The criterion's definition includes γ and the C_br formula, and γ has been fixed "since revision 2".

### 3.6 The margin, set against what could move it

- **The margin** is 0.546 fF, or 9.6e-3 relative to C_br.
- **E1's side.**
  - γ·C_lo^static = 5.7e-5 fF is already subtracted in Q2.
  - E1.2's enclosure width, about 2.6e-6 fF, does not reduce the margin: C_lo^static is formed from the enclosure's upper end E_up.
- **The study's side.** The refutation survives worst-case relative errors of up to about 1.06e-3 in the study's three level values (§8.2 item 5).
  - This is a threshold for the result, not a statement of how accurate those values are.
  - For comparison, the study records a certified solve error of at most 1.43e-13 relative at level 2 (smaller at levels 0 and 1). It also records an uncertified assembly-term estimate of 9.6e-11 relative.
  - The certified solve error is itself conditional on the uncertified ρ. ρ is estimated at no more than 4.9e-7 of c, and BOUND_SAFETY = 1.001 covers ρ/c up to 5e-4.

## 4. Assumptions and scope

### 4.1 Assumptions the result depends on

1. **The libm ASSUMPTION** (contract §4.4): "glibc logl ≤ 2 ulp and sqrtl correctly rounded, with numpy longdouble log and sqrt dispatching to them."
   - The probes passed (§3.3), but the assumption itself is not certified.
   - That is why Q2's basis is `CONDITIONAL_ON_LIBM_ASSUMPTION`.
2. **A correct implementation.** The certificate is only as sound as the code pinned by sha256 in `provenance.json`.
   - That code passed three frozen-code reviews, a final review, the test suite and the controls of §3.4.
   - That is evidence of correctness, not proof.
3. **The same problem in both records.** The study's problem C at levels 0–2 and E1's C_static are the same continuum problem on the same meshed domain:
   - mesh `d8dc1a92…c14428`, whose uniform red refinements are levels 1 and 2;
   - the island at 1 V and all other metal at 0 V;
   - the port face open;
   - the same dielectrics and the same ε₀ convention (contract §1).

   It also includes the study's discretisation being the conforming P1 Dirichlet discretisation it declares (predeclaration.json `"theory"`).

   E1's reported interval already relies on both, because C_hi is the study's bound. Together they give every C_h ≥ C_static.

   The refutation needs only that inequality, not convergence. E1 does not establish convergence (contract §10), and this record does not claim it.
4. **Level-value errors below about 1.06e-3 relative.** The refutation holds provided no error in the study's level values reaches that size (§3.6).
   - This record does not claim the values are accurate to that level. It states only the error the refutation survives.
   - The recorded error figures are far smaller. But the assembly-term figure is an estimate, not a certificate.

Two notes on these assumptions:

- The Q2 label names only the libm ASSUMPTION, as the contract requires. Assumptions 2–4 underlie any use of an E1 number; they are stated here so that none is hidden.
- γ = 1e-6 is a conventional guard, not derived. It only makes REFUTED harder to reach (contract §1).

### 4.2 Scope

- **The model.** This meshed model only: zero-thickness PEC sheets, ε_r = 11.45 (an unapproved seed) and a 4 mm cell (contract §10).
- **The problem and the sequence.** Problem C only, and the study's class-C sequence at levels 0–2 only.
- **Excluded.** Other meshes, refinement paths or levels; C′ and every other electrostatic problem; the device.

## 5. What this record does not conclude

- **Nothing about E_C,F1F1 or g_F1R1.** Both stay UNAVAILABLE. E1's fixed statements stand:
  - `EC_NOT_EVALUATED_BY_E1`;
  - correspondence NOT_ESTABLISHED;
  - deviation NOT_EVALUATED;
  - suitability SUITABILITY_NOT_ASSESSED.
- **Nothing about the device or the architecture.** No statement is made about device suitability, the device's capacitance or the QMHP architecture.
- **No new quantity in frequency units** (contract §1; the approval's `does_not_authorise`):
  - no GHz image of C_lo^static, C_hi or C_br;
  - no replacement S bracket;
  - the S and H figures in §1 and §6 are the study's own, quoted only to identify the claims.
- **No new value, estimate, extrapolation or bracket for C_static.** The only interval is E1's reported [57.220910, 67.975539] fF.
- **Nothing about C′, the C′ bracket or the H bracket.**
  - E1's lower bound is mathematically also a lower bound on C′. But contract §10 says: "The mathematical relations of §2 items 1–2 are not E1 results."
  - Their status is unchanged: model-based, as the study says.
- **No finding on which of P1–P3 failed.**
- **No re-evaluation of the study's other results:** its QUALIFIED verdict, its class labels, its level-0 CONSISTENT verdict and its rigorous bounds.
- **No validation of any exploratory value,** for example 57.00 fF.
- **No tolerance may be applied** to any number here that is in, or derived from, an E1 file (contract §7; `tolerance_scope_decision` `COPIED_NUMBERS_WITHIN_SCOPE`).
  - That includes C_br, the margin, 18.795 % and the 1.06e-3 threshold.
  - It also includes every figure in §2.5 and §3.6.

## 6. Every prior claim affected

| # | claim (location) | status | why |
|---|---|---|---|
| 1 | `summary.json` `classes.C.limit_bracket_model_based`, read as a bracket on the limit of C_h (53.7489–56.6747 fF) | **REFUTED for this model (conditional)** | §2.3 |
| 2 | `classes.C.remaining_rel_error_at_level2_bracket` [0.1994, 0.2647], as the model's range for the level-2 remaining relative error | **REFUTED as a model range (conditional).** E1 implies at most 0.18795, below the range's lower end. The upper end is numerically compatible with E1, but it loses its model-bracket status (see lines 40–42 below) | §2.5 |
| 3 | `classes.C.bracket_assumption`, as a description of this sequence | **REFUTED (conditional).** P1, P2 or P3 fails; which one is not identified | §2.4 |
| 4 | `classes.S.limit_bracket_model_based_GHz2` [4.3201, 4.5553] and its `remaining_rel_error_at_level2_bracket` | **BASIS REFUTED.** It is the C bracket mapped by S = k_S/C (`study_driver.py:618, 626`) and has no other basis. No new S value, bound or location is stated here | §1.2, §5 |
| 5 | study page, line 46: "`C` in 53.75–56.68 fF" | **REFUTED (conditional)** | as 1 |
| 6 | study page, line 48: "the level-2 remaining relative error is 19.9–26.5 %" (the class-C figure) | **REFUTED as a model range (conditional)** | as 2 |
| 7 | study page, line 47: "`S` in 4.320–4.555 GHz²" | **BASIS REFUTED** | as 4 |
| 8 | README, line 51: "C in 53.75-56.68 fF" and "S in 4.320-4.555 GHz^2" | C: **REFUTED (conditional)**. S: **BASIS REFUTED** | as 1 and 4 |
| 9 | exploratory items that used the bracket, or its image e²/(2hC), as an input: A-29, A-45, A-54, C-02, C-10, C-12, C-16, C-19, C-23, C-32, C-33, C-40, C-41, C-44, C-53, C-70 and E-13 (`corrections/e1-exploratory-claims-correction.md`) | **Stay WITHDRAWN** (there under reasons A, Astatic, C, Ckthr or Cmodel). Their bracket input is now refuted too. Nothing replaces it: no E_C reading may be formed from C_lo^static or C_hi | reasons A and Astatic there; contract D5, §10 |
| 10 | F-01 to F-06: the Q2 outcome asserted in advance from an unreproduced 57.00 fF (the same record, reason F) | **Stay WITHDRAWN as made.** The outcome they asserted is now E1's, on E1's basis alone. E1 did not reproduce 57.00 fF or the method behind it, and E1 was not blind. Their agreement with E1 is not independent confirmation of either | reason F there; contract §8; CLAUDE.md §7 |
| 11 | C-22: "Either way it lies below the operating window of about 0.887–1.114 × target." (the same record) | **Stays WITHDRAWN** (reason C there). It may rest on the bracket in part ("Either way"). Its source file is not committed, so this record does not decide | as 9 |

**Not assessed.** These are outside E1's scope (§5), and their status is unchanged:

- study page line 46, "`C′` in 53.83–56.78 fF";
- study page line 47, "`H` in 4.312–4.548 GHz²";
- README line 51, "H in 4.312-4.548 GHz^2";
- the Cprime and H bracket fields of `summary.json`.

**The 26.47 % inequality (study page lines 40–42, "Why not CONVERGED"; README line 51, "certified remaining error 0.26 > tau 0.05").**

- **The frozen rule's use of the figure stands.**
  - 0.2647 is the certified value of the number d2/(X2 − d2), which the rule compares with τ = 0.05.
  - The rule's output, not CONVERGED, is unchanged.
- **Read as an inequality on the level-2 error, it is numerically compatible with E1.** The inequality is "level-2 remaining relative error ≤ 26.47 %", and E1 implies at most 18.795 %.
- **But its model-bracket status is not preserved.**
  - It was the conservative end of the refuted bracket.
  - It may no longer be cited as a result of the model bracket.
  - Its compatibility with E1 does not restore that status.
- **C′ is not assessed here.** Both places also state C′'s figure: the study page gives 0.2641, and the README says "both". That part is not assessed (§5).

**Stand, not affected:**

- **Study page, lines 43–45 and 55–56.** Lines 43–45 say the brackets are "not rigorous" and rest on an assumption the "theory does not supply". Lines 55–56 are "What the brackets are not". Both stand, and §2 bears them out.
- **Study page, line 97 and lines 625–626.** Line 97 reads "The continuum limit of `C`: the brackets are model-based". Lines 625–626 say the study cannot establish "a rigorous continuum value or lower bound for `C`". Both stand as statements about the study.
- **Study page, lines 318–334, and `predeclaration.json`.** The theory, the window and the rule table stand. The rule is unchanged; its premise failed for this sequence, which lines 325–326 allow.
- **The study's rigorous results.** These stand as the study states them:
  - its Dirichlet bounds on C, C′, S and H (study page lines 49–51);
  - its certified values and class labels;
  - its level-0 CONSISTENT verdict and its QUALIFIED verdict.

  No figure from them is restated here.
- **Other documents that do not use the bracket.** `static-anchor-ec-bound-correction.md`, `static-anchor-hypothesis.md` and `static-band-pairing.md`.
- **Files that discuss the mechanism, not S1's bracket.** These are:
  - the synthetic dry run, `dry_run.json` (`analysis_of_the_synthetic_levels`);
  - the study's two code reviews, `review/review_9aa951f.json` and `review/review_864c0ba.json`.
- **E1's own files.** The contract, approval package, driver and tests use C_br only as Q2's constant.
- **The exploratory record's §3, "What remains valid".** It is unchanged, including its exploratory capacitance numbers. They remain exploratory prior knowledge only.

**Pointers.** The commit that adds this record updates two documents, in three places, to name it. These are documents, not claims:

- the E1 page, line 86, which at `9d0579d` read "It has not been written yet";
- README line 52, the E1 row, which at `9d0579d` read "its correction record is still to be written";
- README line 51, the static-study row, which at `9d0579d` had no pointer.
  - It gets a dated correction note naming this record, placed before the row's "Record:" entry, as in line 50.
  - The row's original text, including the passages quoted in §1.3 and §6, is unchanged.

**How the list was built.** I ran `git grep` over every tracked file at `9d0579d`.

- **Search terms:**
  - the bracket figures: 53.75, 56.68, 56.675, 4.320, 4.555, "19.9–26.5", 0.2647 and 0.26;
  - their E_C images: 0.342, 0.360 GHz and 0.34–0.37;
  - the field name `limit_bracket`;
  - the phrases "model-based bracket", "model-based value", "model-based reading", "model-based E_S" and "limit of the meshed model";
  - `MODEL_BRACKET`;
  - "bracket" in every document.
- **The exploratory record, item by item.** Every one of its 225 items was scanned for three things:
  - the words "bracket", "model", "model-based" and "either way";
  - the reason code Cmodel;
  - the bracket's images: 0.57–0.60 × target, 0.3417 and 0.3604 GHz, 0.34–0.37 GHz, 2.0–2.3 GHz and 1.7×.
- **Omissions found by the pre-commit review.** An earlier version of this list missed four items: C-23, C-41, C-70 and README line 51's "0.26". They are included above.
- **Coincidences.** Matches in meshes, solver logs and unrelated JSON were numeric coincidences, for example `cap_fraction` 0.342… and `LinearSolve` 14.555….
- **Not re-searched.** Uncommitted exploratory material was not searched again: `e1-exploratory-claims-correction.md` already covers it. Session transcripts were not read.

## 7. Blindness and prior knowledge

- **E1 was not blind** (contract §8; `summary.json` `fixed_statements.blindness`). Exploratory S1 values existed before it:
  - the ~57 fF value (contract D4);
  - the in-advance Q2 assertions F-01 to F-06.
- **What was fixed in advance:**
  - Q2's criterion, whose definition includes γ and the C_br formula, predates every exploratory S1 calculation that charged ground or R1 panels (contract §1).
  - The configuration was re-selected by a rule that uses no S1 capacitance value (contract §8).
  - The tolerance set is T0.
- **Consequence.** The Q2 result is not an independent reproduction of the exploratory statements, and they are not independent confirmation of it.

## 8. Files, digests and arithmetic

### 8.1 Files cited (sha256 measured at `9d0579d25ead4524c10a07e2c78bc0e9e2e6ec5f`)

The commit that adds this record changes only the E1 page and the README among these. Their digests below are the pre-edit ones.

| file | sha256 |
|---|---|
| `results/STATIC-REFINEMENT-STUDY-20260923T062048Z/summary.json` | `7eca21f3688a662f0324003093de2902cfbd67503fa0de71f5c028df13181298` |
| `results/STATIC-REFINEMENT-STUDY-20260923T062048Z/manifest.sha256` | `e3e447068dea6b4c2790c29de7a34be77f971717fa6e40964f6e31fdee193622` |
| `docs/coupled-candidate/static-refinement-study.md` | `f9ab52bb9f9c7764c8bfb66462c09de67d53e4a9e8bb10cbde29049a641174a1` |
| `experiments/static-refinement-study/study_driver.py` | `97783b3b2749c6b4b21e266f4251038b216d5306dfeb8269786ea8c17304a799` |
| `experiments/static-refinement-study/predeclaration.json` | `29276d45f333be5a7e64678023b5f4e87cb8d24b411bc7bd34e70b389e9e54a5` |
| `docs/coupled-candidate/README.md` | `c72203bafdbce567744fcf9a9b812887b3ea285a4100f056002f7d2b127381a4` |
| `docs/coupled-candidate/corrections/e1-exploratory-claims-correction.md` | `7e3bc9441700811e6182b2893eec62b9d5a5d23f0d672a246f6c263b9c8a172c` |
| `experiments/e1-s1-lower-bound/E1-CONTRACT.rev8.5.md` | `2db93be49ee455f1da952acbe300f370d7614a8986c4151a9563adf805f00150` |
| `docs/coupled-candidate/e1-s1-lower-bound.md` | `10c5613206579882d951bfacbb4af69661aa294e708f915ac6cd30f00a74833c` |
| `results/E1-S1-LOWER-BOUND-20260924T222847Z/manifest.sha256` | `8d70ee11252c96fbbb0de5a666e963d8886273bafc7ad1aab4f36110f7f067ad` |
| `results/E1-S1-LOWER-BOUND-20260924T222847Z/summary.json` | `3d1733ebad73fb53414f4b02cf2ff3865509b09305c9546efe2d014a0b6e9c11` |
| `results/E1-S1-LOWER-BOUND-20260924T222847Z/provenance.json` | `255fb82bd168bbf12679f73c607fb426bab069285e4eedf9bc0598a2364b172f` |
| `results/E1-S1-LOWER-BOUND-20260924T222847Z/controls.json` | `cd1478d17de55567b6346260ce363aba089946f6432fabe893cbce6ba27374fd` |
| `results/E1-S1-LOWER-BOUND-20260924T222847Z/geometry.json` | `3ff76ab8355178b61f7f8024e315ffb3737e54ade610b4d1a5714d94cd74ece4` |
| `results/E1-S1-LOWER-BOUND-20260924T222847Z/pass-E1.2+E1.2-excl-R1.json` | `c69a032d7f801e05d64fb6c7cd00655e02f5d78c5f4b1757b97f483364b41b04` |
| `experiments/e1-s1-lower-bound/ATTEMPT-SPENT.json` | `5100a1317f8fc6267b9d4469b089f2dc4fc1fe92f645701e8665a1970658711a` |
| `experiments/e1-s1-lower-bound/E1-APPROVAL.consumed.json` | `b8f6883b6fa431aaca5778e135667bd5cfa0afd830822f908e263db263b8ee7d` |
| `experiments/e1-s1-lower-bound/EXECUTION-LOG.json` | `c08d1f793e24e99458153904596048da2ff9ef33bcff1806f43148b6d67b217f` |

### 8.2 Arithmetic done for this record

All of it uses recorded float64 values. Comparisons were made in exact rational arithmetic (Python `fractions`). No capacitance, energy or matrix computation was involved.

1. **C_br.** `limit_bracket_model_based[1] × C_fF[2] / values[2]` = 56.67470653023562 fF. It equals, bit for bit, contract §1 and `provenance.json` `baseline.C_br_fF`.
2. **The bracket's lower end.** `limit_bracket_model_based[0] × C_fF[2] / values[2]` = 53.748899623323325 fF.
3. **The Q2 margin.**
   - C_lo^static × (1 − 10⁻⁶) = 57.22085343958963 fF.
   - Its margin over C_br is 0.5461469093540162 fF, or 0.9637 % of C_br.
   - γ·C_lo^static = 5.72e-5 fF.
4. **The level-2 figures.**
   - `C_fF[1] − C_fF[2]` = 14.226639052693187 fF (d2 in fF).
   - `C_fF[2] − C_br` = 11.300832145780895 fF.
   - `C_fF[2] − C_lo^static` = 10.754628015516218 fF.
   - (C_fF[2] − C_lo^static)/C_lo^static = 0.18794926.
5. **The 1.06e-3 threshold.** The bracket's upper end in solver units is U = X2 − d2²/(d1 − d2).
   - U increases with X0 and X2 and decreases with X1 wherever d1, d2 and d1 − d2 are positive. That holds throughout the range considered.
   - So its largest value, when each level value may be in error by up to a relative ε, is U(X0(1 + ε), X1(1 − ε), X2(1 + ε)).
   - Evaluated exactly and converted to fF, it reaches C_lo^static·(1 − 10⁻⁶) at ε ≈ 1.06e-3.
6. **The E1 manifest.** `sha256sum -c manifest.sha256` in the E1 record: 12 of 12 OK.

### 8.3 Not done

- No solver, Palace, Route A, E1 or Confirmation run, no second E1 attempt and no rehearsal.
- No S1 capacitance, energy, Cholesky or matrix computation.
- The six `/tmp/qmhp-e1-confirmation-*` directories that hold S1 values were not opened.
- No session transcript was read.

## 9. Open decision

- **Whether the C′ and H brackets need separate treatment** is a human decision. They rest on the same premise.
- **E1 cannot supply it** (contract §10). It would need its own predeclaration and approval.
- **Nothing is proposed here.**
