# E1 exploratory-claims correction record (corrected and completed; for human review)

Prepared 2026-09-23. Not committed. Not a registered record. For human review.

## 1. Status

- **What this is.** A correction record under CLAUDE.md §1 and §14. It identifies exploratory claims this session made before the E1 pre-declaration, and some it repeated afterwards. For each claim it states why the claim is wrong or unsupported, and withdraws it.
- **What is corrected.** Exploratory, non-evidential desk material in the session scratchpad (`scratchpad/next/`), and statements made to the user in chat. **None of the corrected items is a registered record.** This record changes no repository file, record, manifest or git state. It also leaves every corrected scratch file byte-unchanged (the sha256 values below are the measured digests of the unchanged files).
- **Basis.** The frozen E1 pre-declaration, revision 6: rev6 (`e1/frozen/E1-PREDECLARATION.rev6.bc59ac5bc252b314a43431315f78a86cc340c00bb913607ddb31d67252ac677c.md`, sha256 `bc59ac5bc252b314a43431315f78a86cc340c00bb913607ddb31d67252ac677c`), §2.3–§2.5, §3.2–§3.3 and §11. Also the rev6 review findings, `e1/rev6_findings.txt` (sha256 `77687a7505132714dbd9c6b49c53fdbdcf4d8afefca572a47745d0f4deaca815`), section "[prior-knowledge] [BLOCKING] §11 Contradicted exploratory interpretations" (lines 1334–1396) and the prior-knowledge MINOR findings (lines 1398–1491). Every claim in that BLOCKING section was checked against its source. All of them were found, except one: "−3 %/+5 %" appears in `verify_results.json` [1] only as the object of that review's refutation, not as an assertion. It is asserted in `DRAFT-recommendation.md` line 40 (item C-01).
- **Correction of the rev6 §11 attribution.** rev6 §11 calls "S1 is out of tolerance for any k²" and the "−3 %/+5 %" tolerance "chat-level statements". They are file-level: `verify_results.json` [2]/bottom_line (item C-29) and `DRAFT-recommendation.md` line 40 (item C-01). A search of the assistant text in transcript lines 1–35004 finds neither phrase asserted in chat. Both occur only in the withdrawal notices listed in §2.9. The nearest chat forms are items E-02, E-03 and E-10.
- **Quotations.** Every excerpt below is verbatim. `verify_items.py` checked the 140 items and 4 withdrawal notices of the draft, and `audit_verify.py` re-checked them independently from the draft text: 0 mismatches. `audit_build.py` checked every item added in this version the same way and refuses to write on any mismatch: 0 mismatches out of 85 added items. Total: 225 items and 4 withdrawal notices.
- **Claim types used.** Exploratory agent report, claim, verdict or open question (JSON); exploratory review finding, bottom line, replacement text, or review claim with status CONFIRMED by that review (JSON); drafting input (JSON, `e1/inputs.json`); exploratory draft recommendation (Markdown); superseded pre-declaration draft, revision 2 or 3 (Markdown); superseded frozen pre-declaration, revision 4 (Markdown); script print format or script code; chat statement (assistant text).
- **Status of every item: WITHDRAWN.** A qualifier is added where the claim is withdrawn only in part: as unconditional, as stated, as a statement about E_C,F1F1 or about the registered operator, as an E_C statement (scripts), or as a conclusion. Group G items are also marked as already corrected in a later revision. Withdrawal means the item may not be used as, or cited for, the withdrawn conclusion by E1, by the planning note or anywhere else.

## 2. Corrections

### 2.1 Reasons (cited by code in each item)

- **A.** A lower bound on the static capacitance bounds E_C,F1F1 under no reading. Under M1, 1/(C⁻¹)_FF = C_DC − ΔC_R1, so an upper bound on E_C,F1F1 would need a certified upper bound on ΔC_R1. No exploratory calculation supplies one. Under M3 the relation is not even one-signed. Sources: rev6 §2.4 row 2 (line 201) and §2.3 item 5 (lines 179–194). Counterexamples in rev6 line 201: a 2×2 circuit with C_FF = 40 fF and k² = 0.4 has E_C,F1F1 = 0.807 GHz, while K/C_FF = 0.484 GHz. A synthetic QT-S network with C_static = 53.689 fF has an M1 value of 53.261 fF, which is below the valid lower bound 53.6 fF.
- **Acond.** This is a hypothetical ("if it is proven to bound 1/(C⁻¹)_FF"). A capacitance lower bound on its own cannot meet that condition under any reading (rev6 §2.4 row 2, line 201). The statements were then used as drafting inputs (rev6 §11 register; rev6 review, prior-knowledge MINOR, rev6_findings.txt lines 1398–1436).
- **Astatic.** Read as arithmetic on the static term e²/(2hC_static), with C_FF read as C_static under A-R, this is not false, provided the unreproduced and unrecorded lower bound is valid. It is withdrawn because it was presented as a statement about E_C,F1F1, or next to one, and rev6 §2.4 row 2 (line 201) excludes such statements. rev6 §2.5 item 1 (lines 233–235) also forbids converting either end of the static interval to GHz and any GHz or MHz quantity in E1 outputs. Source for this treatment: rev6 review, prior-knowledge MINOR, rev6_findings.txt lines 1488–1491.
- **Aprint.** A script format string. It prints a capacitance lower bound as an E_C upper bound, or as a percentage of 0.60 GHz, and so has the defect described under reason A (rev6 §2.4 row 2, line 201). The script is kept unchanged as exploratory material. Any line it printed is withdrawn as an E_C statement. That output was not logged: rev6 §11 P2 (line 1081) says so for the P2 scripts, and no log file exists in `agents/`, `verify/thomson/`, `verify/s3/` or `e1/verify/numbers/` (directory listing).
- **B.** The step from C ≤ C_hi to E_C,F1F1 ≥ K/C_hi holds only under reading M1 or M2. It also needs a registered-definition decision (CLAUDE.md §3), which has not been made, and the upper bound that matches the declared port model: C_hi under PA, the frozen C′ bound of 68.04546246723753 fF under PB. It does not hold under M3 or under Route B band fits. Sources: rev6 §2.4 row 1 (line 200), §2.3 item 3 (line 169) and §2.2 notes. No record states such a bound; the baseline reports E_C,F1F1 as UNAVAILABLE (rev6 line 200). The claim is therefore withdrawn as unconditional.
- **Binc.** The statement gives a condition (A-R, "this reduction", M1 or "M1 (or M2)", the lumped two-node Schur relation, or "once the correspondence is established") but leaves out part of what rev6 §2.4 row 1 (line 200) requires: a registered-definition decision adopting M1 or M2, and the port-model-consistent upper bound. For a distributed, shorted R1 the lumped Schur step is a reading, not an identity (rev6 §2.3 items 3 and 5, lines 153–194). It is withdrawn as stated.
- **C.** No suitability tolerance is registered or adopted: T0 (rev6 §3.2(b), line 271; coupling-definition.md §6–§7). A suitability, "on target", out-of-tolerance or window conclusion therefore has no criterion to rest on. In addition, each of these conclusions rests on an E_C upper bound taken from a capacitance lower bound (reason A) or on a model-based E_C reading (reason Cmodel). Both are withdrawn.
- **Ctol.** This presents a tolerance as derived. None is registered or adopted (T0; rev6 §3.2(b), line 271). The "~−5.1 %" notch edge is a derived sensitivity, "not a requirement and not a threshold" (rev6 line 272). The "−3 %/+5 %" proposal was also refuted as a sampling artefact (verify_results.json [1]/bottom_line: "The tolerance itself is a sampling artefact."). The frozen-model sensitivities behind these figures remain valid as model facts (§3).
- **Cmodel.** This is a model-based E_C reading: the image e²/(2hC) of the study's non-rigorous model bracket, 53.75–56.68 fF, taken as E_C,F1F1 on the assumption that k² is small. rev6 adopts no reading and asserts no inequality between the registered 1/(C⁻¹)_F1F1 and C_static (rev6 §2.3 item 5, lines 191–193), so no approximation of one by the other is available either. So this is not an E_C value, and the deviation or required capacitance change derived from it is withdrawn.
- **Ckthr.** This infers a deviation from thresholds on ΔC_R1, k² or g built from the nominal and a capacitance lower bound (or, in C-40, C-41 and C-70, from the model-based value or from K/C_hi). Those thresholds exist only under M1, which is not adopted (rev6 §2.3 item 3, line 169). rev6 §2.5 item 2 (lines 236–239) forbids them as E1 outputs because they invite a DEV_BELOW or "unsuitable" reading (e1/verify3_results.json [0]/findings[0]).
- **Dfloat.** R1 is not a floating conductor in S1. It is galvanically part of ground and enters the registered operator as a modal coordinate (rev6 §2.1 closing paragraph, line 106; §2.3 item 5, line 194). Requirement R-1 excludes equating the R1 coordinate with a floating conductor, and the removed-metal reading is not adopted (R-1 as quoted in rev6 §12; rev6 review, full-wave MINOR on §2.5 item 6). No one-signed relation to the floating-body capacitance is available either: in quasi-TEM synthetic models under M1 the M1 value lay below C_float,body (lines 188–189), and in synthetic models with a port-to-line mutual inductance, which lie outside the quasi-TEM family, it can exceed it (line 190). "Any k²" or floating/removed-readout arguments therefore establish no bound on the registered 1/(C⁻¹)_F1F1 or on E_C,F1F1. The capacitance values themselves stand as bounds on C_static and on the floating-R1 capacitance (rev6 line 253; §3).
- **DQT.** Quasi-TEM (QT) results are facts about a surrogate model, not proofs about the registered operator. The QT-S family assumes no port-loop inductance and no port-to-line mutual inductance (planning note rev6 §6, lines 103–106). The first assumption fails for S1: the registered sheet port has C_∞ = 0 and port-loop inductance is present (planning note rev6 lines 114–116; rev6 §2.3 item 1, line 139). Whether a port-to-line mutual inductance is present in S1 is not assessed (rev6 line 190). rev6 says of the QT results that "Neither result is established for S1 or for the registered operator" (rev6 §2.3 item 5, lines 187–194). Any E_C interval, bound or transfer "CONDITIONAL ON QT" is therefore withdrawn as a statement about the registered invariant. Relations stated strictly inside the QT-S surrogate under M1 are not withdrawn as surrogate statements, but their proof "must be written into a repository file before it can be cited" (planning note rev6 line 110).
- **F.** This asserts E1's Q2 outcome in advance, from an exploratory value that was never reproduced (57.00 fF). Whether the ±0.40 mm A-R value is 56.88 fF or 57.00 fF is also unresolved (rev6 review, prior-knowledge MINOR, rev6_findings.txt lines 1437–1448). rev6 makes the premise test E1's own predeclared outcome (§1 Q2, lines 75–81). Exploratory values are prior knowledge only, not evidence (§3.3 item 3, line 292). A later MODEL_BRACKET_PREMISE_REFUTED would not be an independent reproduction of these statements, and a MODEL_BRACKET_NOT_CONTRADICTED would not contradict any record.

- **Ag.** An upper bound of the form E_C,F1F1 ≤ K/C_T + g²/(4f_R), or a numerical "extra term" g²/(4f_R), uses the two-node identity E_C,F1F1 = K/C_FF + g²/(4f_R). For the distributed, shorted R1 that holds only under M1, which is not adopted (rev6 §2.3 items 3 and 5, lines 153–194), and it needs S1's own g and f_R*, which are UNAVAILABLE (verify_results.json [0]/items[9]/evidence: "S1's g is UNAVAILABLE, so 1.3 MHz is an evaluation, not a bound"). Using the Master g is a Master-g conversion (rev6 §2.5 item 3, line 240). As stated, the condition is missing.
- **Breg.** This states the M1 relation (C⁻¹)_FF = 1/C_static + 1/C_R1,eff, and hence C_Σ,reg < C_static, as a fact about the registered operator, with no reading. rev6 asserts no inequality between the registered 1/(C⁻¹)_F1F1 and C_static (§2.3 item 5, line 193). Under M3 or a Route B band fit, 1/(C⁻¹)_FF can exceed C_DC (line 184). Combined with C_static ≤ C_hi, the relation would give an unconditional E_C,F1F1 ≥ K/C_hi (reason B). The review of revision 4 raised this (e1/final_findings.txt lines 121–122), and revision 5 replaced the text.
- **Dreg.** This asserts that the registered 1/(C⁻¹)_FF lies below the floating-metal capacitance. That ordering was observed only in quasi-TEM synthetic models under M1 (rev6 lines 187–189). rev6 says "Neither result is established for S1 or for the registered operator", and with a port-to-line mutual inductance the M1 value can exceed C_float,body (line 190).

Reason codes A to F are defined by `build_record.py`; Ag, Breg and Dreg are added by `audit_build.py` (sha256 values in §4 and §6). rev6 line numbers refer to the frozen file named in §1. "Planning note rev6" is `e1/frozen/E1-PLANNING-NOTE.rev6.9f22bcd8497aeb42189b273b119ce386379dc0869abdb3b9d5a197c801b531a1.md` (sha256 `9f22bcd8497aeb42189b273b119ce386379dc0869abdb3b9d5a197c801b531a1`).

### 2.2 (A) E_C upper bounds taken from capacitance lower bounds — 55 items (42 in the draft, 13 added)

Includes the static-term GHz forms and the script print formats.

**A-01**

```text
So C ≥ 6.225 × 8ε₀a = 33.07 fF, and E_C,F1F1 ≤ 0.586 GHz, for any k² and any C_J ≥ 0.
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 55`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **A** (§2.1). Note: also (D): "for any k²"
- Status: **WITHDRAWN**

**A-02**

```text
C ≥ 37.32 fF, so E_C ≤ 0.519 GHz (−13.5 %).
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 58`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-03**

```text
C ≥ 33.07 fF, so E_C,F1F1 ≤ 0.586 GHz. With the external Pólya–Szegő theorem the bound tightens to C ≥ 37.3 fF, E_C ≤ 0.519 GHz.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-04**

```text
C >= ((1 + 11.45)/2) x 8 eps0 x 75 um = 33.07 fF, so e^2/2C <= 0.5857 GHz (x0.976 of target).
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[5]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **A** (§2.1). Note: presented as excluding 0.60 GHz for E_C (same claim: "It already excludes 0.60 GHz for the declared model.")
- Status: **WITHDRAWN**

**A-05**

```text
C >= 37.32 fF, so E_C <= 0.519 GHz (x0.865).
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[6]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-06**

```text
C >= 37.48 fF, E_C <= 0.517 GHz.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[6]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **A** (§2.1). Note: literature square-plate constant; the source script calls it "not rigorous here" (agents/bounds.py line 11)
- Status: **WITHDRAWN**

**A-07**

```text
so E_C,F1F1 <= 0.586 GHz whatever k^2 or g is.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[7]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **A** (§2.1). Note: also (D): floating-readout Kron argument
- Status: **WITHDRAWN**

**A-08**

```text
a rigorous desk bound for the declared model gives E_C,F1F1 ≤ 0.586 GHz (≤ 0.519 with Pólya–Szegő)
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-09**

```text
But a rigorous lower bound on C and an upper bound on E_C,F1F1 are available by monotonicity at zero compute, and they exclude 0.60 GHz for the declared model at ε_r = 11.45.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-10**

```text
So E_C,F1F1 ≤ 0.519 GHz (0.865 × target), or ≤ 0.509 GHz.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-11**

```text
this gives E_C,F1F1 <= 0.5857 / 0.5191 / 0.5083 / 0.5086 GHz
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/claims[6]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-12**

```text
Rigorously, for any k² and any C_J ≥ 0, E_C,F1F1 ≤ 0.519 GHz (0.865 × target).
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **A** (§2.1). Note: also (D): "for any k²"
- Status: **WITHDRAWN**

**A-13**

```text
or ≤ 0.509 GHz on my synthetic Galerkin plate value.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-14**

```text
C_J from island to ground adds to the Schur complement, so e^2(C^-1)_FF/2 <= 0.5857 GHz.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/items[7]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **A** (§2.1). Note: also (D): rests on "1/(C^-1)_FF >= 33.07 fF whatever the geometric k^2"
- Status: **WITHDRAWN**

**A-15**

```text
So C_box >= 37.33 fF and >= 38.11 fF (E_C <= 0.5083 GHz, -15.3%).
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/items[10]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-16**

```text
giving E_C <= 0.585727 GHz (-2.379% vs 0.60, 0.621 points inside the -3% edge).
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/items[11]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **A** (§2.1). Note: also (C): "-3% edge"
- Status: **WITHDRAWN**

**A-17**

```text
and >= 38.11 fF on a fine one (E_C <= 0.508 GHz).
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-18**

```text
64 panels give C >= 37.79 fF (E_C,F1F1 <= 0.5126 GHz, -14.6 %) in milliseconds.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/items[0]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-19**

```text
1,024 panels give C >= 38.085 fF (<= 0.5086 GHz, -15.2 %) in 0.7 s.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/items[0]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-20**

```text
With no charge on any R1 conductor it gives C >= 53.57-53.61 fF, so E_C,F1F1 <= 0.361 GHz for any k^2, in 19-37 s.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/items[0]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **A** (§2.1). Note: also (D): "for any k^2"
- Status: **WITHDRAWN**

**A-21**

```text
In under 1 s it gives S1 a capacitance of at least 38.09 fF, so E_C,F1F1 <= 0.509 GHz (-15 %).
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-22**

```text
This holds for any k^2, any C_J >= 0, any box and any metal thickness, and for eps_r above 10.9.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **A** (§2.1). Note: also (D)
- Status: **WITHDRAWN**

**A-23**

```text
C >= 53.6 fF for any k^2, so E_C,F1F1 <= 0.361 GHz;
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **A** (§2.1). Note: also (D)
- Status: **WITHDRAWN**

**A-24**

```text
What each available lower bound gives if it is proven to bound 1/(C⁻¹)_FF: E_C ≤ 0.5857 GHz (deviation ≤ −2.38 %) from T = 33.07 fF;
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/claims[24]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Acond** (§2.1)
- Status: **WITHDRAWN**

**A-25**

```text
E_C ≤ 0.5085 GHz (≤ −15.24 %) from T = 38.09 fF;
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/claims[24]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Acond** (§2.1)
- Status: **WITHDRAWN**

**A-26**

```text
E_C ≤ 0.3398 GHz (≤ −43.4 %) from T = 57.00 fF.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/claims[24]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Acond** (§2.1)
- Status: **WITHDRAWN**

**A-27**

```text
uniform n = 32 gives C_lo = 37.8491 fF and E_hi = 0.51177 GHz.
```

- Source: `e1/verify_results.json` (sha256 `cf730feb4755cef84b0788b485835740bb2001d6c0431bd70418526e8d1c7fec`), JSON path `[2]/items[22]/evidence`
- Also verbatim in (same claim, same status): `e1/refuted.txt` (sha256 `1acfd7ea8b597a675ea4a647ac9ca5b2430e647dcadfa4c5ad859705aff42488`)
- Type: exploratory review finding (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-28**

```text
The declared uniform n = 32 gives 37.849 fF (E_hi 0.5118 GHz).
```

- Source: `e1/verify_results.json` (sha256 `cf730feb4755cef84b0788b485835740bb2001d6c0431bd70418526e8d1c7fec`), JSON path `[2]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**A-29**

```text
Under A-R this gives e^2/(2 C_FF) <= 0.340 GHz, below the draft's 0.342-0.360 GHz.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/items[13]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **Astatic** (§2.1)
- Status: **WITHDRAWN as a statement about E_C,F1F1 (not asserted false as static-term arithmetic)**

**A-30**

```text
C_T = 38.09 fF gives E_C^DC ≤ 508.54 MHz.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[0]/claims[14]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Astatic** (§2.1)
- Status: **WITHDRAWN as a statement about E_C,F1F1 (not asserted false as static-term arithmetic)**

**A-31**

```text
C_T = 57.00 fF gives E_C^DC ≤ 339.83 MHz.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[0]/claims[14]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Astatic** (§2.1)
- Status: **WITHDRAWN as a statement about E_C,F1F1 (not asserted false as static-term arithmetic)**

**A-32**

```text
Static term using the desk C_lo = 38.09 fF (unrecorded): [0.28496, 0.50854] GHz.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[2]/summary`
- Type: drafting input, agent summary (JSON)
- Why: reason **Astatic** (§2.1)
- Status: **WITHDRAWN as a statement about E_C,F1F1 (not asserted false as static-term arithmetic)**

**A-33**

```text
The desk upper ends are K/57.00 = 0.33983 GHz and K/37.849 = 0.51178 GHz.
```

- Source: `e1/verify3_results.json` (sha256 `0906538735f1631d9d69bbdfcdd414eb9aa163f356f25f6b9351d560e6a58961`), JSON path `[0]/findings[2]/evidence`
- Also verbatim in (same claim, same status): `e1/rev3_findings.txt` (sha256 `0224fdc4e4a3d80c68c465c58bcf602f5eea01293c94b2a7d7f8a70d03e91fb7`)
- Type: exploratory review finding (JSON)
- Why: reason **Astatic** (§2.1). Note: stated by a reviewer while objecting to GHz output; listed because it states the numbers
- Status: **WITHDRAWN as a statement about E_C,F1F1 (not asserted false as static-term arithmetic)**

**A-34**

```text
print(f'{name}: C >= {C:.3f} fF -> E_C,F1F1 <= {K/C:.4f} GHz ({K/C/0.6:.4f} x target)')
```

- Source: `agents/bounds.py` (sha256 `a7690a33864992bd4c9a5fcd8425aec88120c6cb86fa861361e4783e5ed94dce`), `line 13`
- Type: script print format
- Why: reason **Aprint** (§2.1)
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**

**A-35**

```text
print('eps_r', er, 'disk bound E_C <=', round(K/(8*eps0*(a/2)*f*1e15),4), ' P-S bound E_C <=', round(K/(8*eps0*math.sqrt(a*a/math.pi)*f*1e15),4))
```

- Source: `agents/bounds.py` (sha256 `a7690a33864992bd4c9a5fcd8425aec88120c6cb86fa861361e4783e5ed94dce`), `line 19`
- Type: script print format
- Why: reason **Aprint** (§2.1)
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**

**A-36**

```text
E_C <= {EC(Cth):.6f} GHz ({EC(Cth)/0.6-1:+.4%} vs 0.60)
```

- Source: `verify/thomson/consts.py` (sha256 `74db861e81a925653a737ffdcc4a0e1074966386314962964236a3dfb79feea1`), `line 11`
- Type: script print format
- Why: reason **Aprint** (§2.1). Note: file not in the rev6 §11 register (rev6 review MINOR finding)
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**

**A-37**

```text
PS C = {Cps*1e15:.5f} fF; E_C <= {EC(Cps):.6f} GHz ({EC(Cps)/0.6-1:+.4%})
```

- Source: `verify/thomson/consts.py` (sha256 `74db861e81a925653a737ffdcc4a0e1074966386314962964236a3dfb79feea1`), `line 12`
- Type: script print format
- Why: reason **Aprint** (§2.1)
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**

**A-38**

```text
C_box >= {Cbox*1e15:.4f} fF; E_C <= {e*e/(2*h*Cbox)/1e9:.5f} GHz ({e*e/(2*h*Cbox)/1e9/0.6-1:+.2%})
```

- Source: `verify/thomson/square_rq.py` (sha256 `1105f95e7ba143454c3cbd331a6705c02ab53c357cf875690d9b829f6422f268`), `line 16`
- Type: script print format
- Why: reason **Aprint** (§2.1)
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**

**A-39**

```text
C >= {C*1e15:.2f} fF ; E_C <= {e*e/(2*C)/h/1e9:.4f} GHz
```

- Source: `verify/s3/eprime2.py` (sha256 `1ca9bd089bf0a03ec41f9e80331f54328f31a4b4678eccd5b62fc3eeffc6260c`), `line 64`
- Type: script print format
- Why: reason **Aprint** (§2.1)
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**

**A-40**

```text
C >= {C*1e15:.2f} fF, E_C,F1F1 <= {Ec:.4f} GHz
```

- Source: `verify/s3/eprime_lite.py` (sha256 `37a02e0841862492d1e1c86567b171c632b8a5c92c2d92f6f65e52da148ead25`), `line 79`
- Type: script print format
- Why: reason **Aprint** (§2.1). Note: registered in the rev6 §11 table (P2, line 1116) but not named in the §11 list of contradicted interpretations (lines 1052–1057)
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**

**A-41**

```text
C_S1 >= {C*1e15:.3f} fF, E_C,F1F1 <= {ec_ghz(C):.4f} GHz ({(ec_ghz(C)/0.6-1)*100:+.1f} %)
```

- Source: `verify/s3/x1_s1.py` (sha256 `9572265cfb60f3eef3bfe391b833658e0f69e8c08467ce1f5f7ef0b8af4a50a2`), `line 24`
- Type: script print format
- Why: reason **Aprint** (§2.1)
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**

**A-42**

```text
C_lo={C:.4f} fF  E_hi=K/C={K/C:.5f} GHz
```

- Source: `e1/verify/numbers/plate3.py` (sha256 `8d99c4ddfdc34fd302c9597ef51cbb9ec983f167ea7e3743d2d836679423040c`), `line 25`
- Type: script print format
- Why: reason **Aprint** (§2.1)
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**

**A-43**

```text
The bound lapses for ε_r < 11.15.
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 57`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **A** (§2.1). Note: presents 0.60 GHz as excluded by the disk bound for ε_r ≥ 11.15
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**A-44**

```text
The analytic exclusion of 0.60 GHz lapses for eps_r below 9.77 (Pólya–Szegő) or 11.15 (disk).
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/open_questions[3]`
- Type: exploratory agent open question (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**A-45**

```text
The analytic exclusion needs eps_r >= 11.15 (disk bound) or >= 9.77 (Pólya–Szegő); on sapphire (in-plane about 9.3) it would lapse, although the model-based gap would persist.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[10]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **A** (§2.1). Note: "model-based gap" is also reason Cmodel
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**A-46**

```text
- **Numbers (CODATA):** 33.0704 fF gives 0.585727 GHz; 37.3159 fF gives 0.519087 GHz; the eps_r threshold is 11.1538.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **A** (§2.1). Note: same numbers as A-16, at a different locator
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**A-47**

```text
- **"Lapses for eps_r < 11.15"** means the bound stops excluding the 0.60 GHz target. Against the -3% window edge the threshold is 11.53. So at eps_r = 11.45 the Thomson bound alone does not decide S1, which is what the draft itself says.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **A** (§2.1). Note: also (C): "-3% window edge" and "decide S1"
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**A-48**

```text
Wording: 11.15 is where the bound stops excluding the 0.60 GHz target, not where the bound fails.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/items[11]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**A-49**

```text
(5) Numbers: 33.07 fF / 0.5857 GHz; 37.32 fF / 0.5191 GHz; eps_r threshold 11.15
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/items[11]/claim`
- Type: exploratory review claim, status CONFIRMED by that review (JSON)
- Why: reason **A** (§2.1). Note: the review confirmed it, so it is asserted there, not only quoted
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**A-50**

```text
- desk E1.2 value 57.00 fF gives E_st ≤ K/57.00 = 0.3398 GHz;
- desk E1.1 value 38.09 fF gives 0.5085 GHz.
```

- Source: `e1/verify_results.json` (sha256 `cf730feb4755cef84b0788b485835740bb2001d6c0431bd70418526e8d1c7fec`), JSON path `[1]/items[3]/evidence`
- Also verbatim in (same claim, same status): `e1/refuted.txt` (sha256 `1acfd7ea8b597a675ea4a647ac9ca5b2430e647dcadfa4c5ad859705aff42488`)
- Type: exploratory review finding (JSON)
- Why: reason **Astatic** (§2.1). Note: stated by a reviewer while objecting to the leak; listed because it states the numbers (same rule as A-33); the draft record named this locator as not listed
- Status: **WITHDRAWN as a statement about E_C,F1F1 (not asserted false as static-term arithmetic)**
- Added in this version (completeness check, §6)

**A-51**

```text
That is identical to the lower end of the Table B static-term line at C_J = 0, whose desk upper end is K/57.00 = 0.33983 GHz.
```

- Source: `e1/verify3_results.json` (sha256 `0906538735f1631d9d69bbdfcdd414eb9aa163f356f25f6b9351d560e6a58961`), JSON path `[0]/findings[1]/evidence`
- Also verbatim in (same claim, same status): `e1/rev3_findings.txt` (sha256 `0224fdc4e4a3d80c68c465c58bcf602f5eea01293c94b2a7d7f8a70d03e91fb7`)
- Type: exploratory review finding (JSON)
- Why: reason **Astatic** (§2.1). Note: stated by a reviewer while objecting; same rule as A-33
- Status: **WITHDRAWN as a statement about E_C,F1F1 (not asserted false as static-term arithmetic)**
- Added in this version (completeness check, §6)

**A-52**

```text
• A Thomson bound C_DC ≥ C_T gives only e²/(2hC_DC) ≤ e²/(2hC_T), and E_C,F1F1 ≤ e²/(2hC_T) + g²/(4f_R1).
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[0]/claims[13]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Ag** (§2.1). Note: premise of C-31 and C-63
- Status: **WITHDRAWN as stated (its condition is incomplete)**
- Added in this version (completeness check, §6)

**A-53**

```text
Under the normal-mode reading, the extra term is about g²/(4 f_R), which is 1.3 MHz at the source g.
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 56`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **Ag** (§2.1). Note: verify_results.json [0]/items[9]/evidence: "S1's g is UNAVAILABLE, so 1.3 MHz is an evaluation, not a bound"
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**A-54**

```text
print('C', C, 'fF -> e^2/2C =', round(K/C,5), 'GHz')
```

- Source: `agents/bounds.py` (sha256 `a7690a33864992bd4c9a5fcd8425aec88120c6cb86fa861361e4783e5ed94dce`), `line 15`
- Type: script print format
- Why: reason **Astatic** (§2.1). Note: printed next to the line-13 E_C,F1F1 lines, for C = 67.9755, 56.68, 53.75, 32.284, 33.07, 31.64 and 32.93 fF (line 14)
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**
- Added in this version (completeness check, §6)

**A-55**

```text
print(f"  E_C target {tgt:.4f} GHz needs C = {Cneed*1e15:.5f} fF -> Thomson eps_r threshold {2*Cneed/Cd-1:.5f}")
```

- Source: `verify/thomson/consts.py` (sha256 `74db861e81a925653a737ffdcc4a0e1074966386314962964236a3dfb79feea1`), `line 15`
- Type: script print format
- Why: reason **Aprint** (§2.1). Note: targets 0.60 and 0.582 GHz (line 14; the latter is the "-3 %" edge, also reason Ctol); file not in the rev6 §11 register
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**
- Added in this version (completeness check, §6)

### 2.3 (B) E_C lower bounds from capacitance upper bounds, stated unconditionally or with an incomplete condition — 32 items (20 in the draft, 12 added)

**B-01**

```text
From the study: C ≤ 67.98 fF rigorously, so E_C ≥ 0.285 GHz.
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 49`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **B** (§2.1)
- Status: **WITHDRAWN as unconditional**

**B-02**

```text
the study alone gives only E_C ≥ 0.285 GHz
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **B** (§2.1)
- Status: **WITHDRAWN as unconditional**

**B-03**

```text
The rigorous present knowledge (E_C,F1F1 ≥ 0.285 GHz, no upper bound) contains the whole tolerance window.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **B** (§2.1). Note: also (C): "tolerance window"
- Status: **WITHDRAWN as unconditional**

**B-04**

```text
It gives only a lower bound, E_C,F1F1 ≥ e²/2C_h ≥ 0.285 GHz (under A-R), with no upper bound, and that interval contains the whole tolerance window.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/claims[24]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Binc** (§2.1). Note: conditioned on A-R only; also (C)
- Status: **WITHDRAWN as stated (its condition is incomplete)**

**B-05**

```text
The present rigorous result (E_C,F1F1 ≥ 0.285 GHz, no upper bound) spans the whole tolerance window, so it prevents a rigorous in/out decision on the seed.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **B** (§2.1). Note: also (C)
- Status: **WITHDRAWN as unconditional**

**B-06**

```text
The upper side is unchanged: C ≤ 67.98 fF, so rigorously E_C,F1F1 is between 0.285 and 0.519 GHz (with C_J = 0).
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **B** (§2.1). Note: upper end also (A)
- Status: **WITHDRAWN as unconditional**

**B-07**

```text
With C_J = 0, E_C,F1F1 >= 0.2850 GHz (0.475 × target), from C_2.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/claims[6]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **B** (§2.1)
- Status: **WITHDRAWN as unconditional**

**B-08**

```text
The chain is e²/(2C_h) ≤ e²/(2C_FF) ≤ E_C,F1F1 = e²/(2C_FF(1 − k²)).
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[0]/claims[16]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Binc** (§2.1). Note: lumped two-node reading; the same chain is in a registered repository document, see §5
- Status: **WITHDRAWN as stated (its condition is incomplete)**

**B-09**

```text
so 1/(C^-1)_FF <= 67.98 fF and E_C >= 0.285 GHz still holds.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/items[7]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **B** (§2.1). Note: argued via floating-readout Kron reading, also (D)
- Status: **WITHDRAWN as unconditional**

**B-10**

```text
E_C,F1F1 >= that value by the Schur complement, which is fine.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/items[12]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **Binc** (§2.1). Note: conditioned on A-R and the lumped Schur step; the same finding corrects the wording to the static term e^2/(2 C_FF) >= 0.285 GHz, which is not withdrawn
- Status: **WITHDRAWN as stated (its condition is incomplete)**

**B-11**

```text
An upper bound on C_DC gives a rigorous lower bound on E_C,F1F1: at least 284.96 MHz from 67.9755 fF, under A-R and this reduction, on the meshed model.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[0]/summary`
- Type: drafting input, agent summary (JSON)
- Why: reason **Binc** (§2.1)
- Status: **WITHDRAWN as stated (its condition is incomplete)**

**B-12**

```text
An upper bound C_DC ≤ C_up rigorously gives E_C,F1F1 ≥ e²/(2hC_up).
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[0]/claims[13]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **B** (§2.1)
- Status: **WITHDRAWN as unconditional**

**B-13**

```text
C_up = 67.9755387 fF gives E_C,F1F1 ≥ 284.96 MHz (82.20 fF gives 235.64 MHz; 114.34 fF gives 169.41 MHz).
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[0]/claims[14]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **B** (§2.1)
- Status: **WITHDRAWN as unconditional**

**B-14**

```text
electrostatic upper bounds on C_DC are rigorous lower bounds on E_C,F1F1 (≥ 284.96 MHz from 67.9755 fF, the direction static-anchor §5 already records);
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[0]/verdict`
- Type: drafting input, agent verdict (JSON)
- Why: reason **B** (§2.1)
- Status: **WITHDRAWN as unconditional**

**B-15**

```text
A Dirichlet upper bound on C_static gives a lower bound on E_C (at least 0.285 GHz;
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/summary`
- Type: drafting input, agent summary (JSON)
- Why: reason **B** (§2.1)
- Status: **WITHDRAWN as unconditional**

**B-16**

```text
It gives E_C ≥ 0.2850 GHz (a deviation of at least −52.5 %) from C ≤ 67.9755 fF, which is already established.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/claims[12]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **B** (§2.1). Note: "already established" was itself refuted (e1/verify_results.json [0]/items[8])
- Status: **WITHDRAWN as unconditional**

**B-17**

```text
Under M1, in both readings, the existing Dirichlet bound gives E_C,F1F1 ≥ 0.285 GHz.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/verdict`
- Type: drafting input, agent verdict (JSON)
- Why: reason **Binc** (§2.1)
- Status: **WITHDRAWN as stated (its condition is incomplete)**

**B-18**

```text
The bound E_C,F1F1 ≥ 0.28496 GHz is new and holds only under M1 (or M2).
```

- Source: `e1/verify_results.json` (sha256 `cf730feb4755cef84b0788b485835740bb2001d6c0431bd70418526e8d1c7fec`), JSON path `[0]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **Binc** (§2.1). Note: omits the definition decision and the port-model requirement
- Status: **WITHDRAWN as stated (its condition is incomplete)**

**B-19**

```text
**Yes, under M1**, because ΔC_R1 ≥ 0 gives E_C,F1F1 ≥ K/C_hi = **0.28496 GHz**. This is already established, not new.
```

- Source: `e1/verify/auditor-rev2/E1-PREDECLARATION.DRAFT.6ec25bf9.md` (sha256 `6ec25bf97dbd2b38e5cdf93e5249a1d96300cae46788cf7a95bfe51a8692d36b`), `line 130`
- Type: superseded pre-declaration draft, revision 2 (Markdown)
- Why: reason **Binc** (§2.1). Note: "already established" refuted in e1/verify_results.json [0]/items[8]
- Status: **WITHDRAWN as stated (its condition is incomplete)**

**B-20**

```text
The lower-side fact E_C,F1F1 ≥ 0.28496 GHz is pre-existing and is restated with its source.
```

- Source: `e1/verify/auditor-rev2/E1-PREDECLARATION.DRAFT.6ec25bf9.md` (sha256 `6ec25bf97dbd2b38e5cdf93e5249a1d96300cae46788cf7a95bfe51a8692d36b`), `line 156`
- Type: superseded pre-declaration draft, revision 2 (Markdown)
- Why: reason **B** (§2.1)
- Status: **WITHDRAWN as unconditional**

**B-21**

```text
print(f"E_C from 67.98 fF = {EC(67.98e-15):.5f} GHz; from 32.28 fF = {EC(32.28e-15):.5f} GHz")
```

- Source: `verify/thomson/consts.py` (sha256 `74db861e81a925653a737ffdcc4a0e1074966386314962964236a3dfb79feea1`), `line 18`
- Type: script print format
- Why: reason **B** (§2.1). Note: labels K/C_hi as "E_C"
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**
- Added in this version (completeness check, §6)

**B-22**

```text
It shows only that E_C is at least 0.285 GHz; it does not show that S1 differs from 0.60 GHz.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/verdict`
- Type: drafting input, agent verdict (JSON)
- Why: reason **Binc** (§2.1). Note: the sentence after B-17, same condition ("Under M1")
- Status: **WITHDRAWN as stated (its condition is incomplete)**
- Added in this version (completeness check, §6)

**B-23**

```text
So the existing chain e²/(2C_h) ≤ e²/(2C_FF) ≤ E_C holds under M1, where C_FF = C_static exactly, but not automatically under M3.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/claims[11]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Binc** (§2.1). Note: the same claim calls E_C ≥ e²/(2hC_static^up) "the existing lower bound", refuted in e1/verify_results.json [0]/items[8]
- Status: **WITHDRAWN as stated (its condition is incomplete)**
- Added in this version (completeness check, §6)

**B-24**

```text
- E_C,F1F1 = K/(C_st − δC_R1), with δC_R1 = k²·C_st ≥ 0, so E_C,F1F1 ≥ E_st.
- Therefore the upper bound C_hi transfers: E_C,F1F1 ≥ K/C_hi. This holds only once the correspondence is established.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[2]/summary`
- Type: drafting input, agent summary (JSON)
- Why: reason **Binc** (§2.1). Note: the first line carries no condition; δC_R1 ≥ 0 fails under M3 (rev6 line 184); "correspondence" omits the port-model-consistent upper bound
- Status: **WITHDRAWN as stated (its condition is incomplete)**
- Added in this version (completeness check, §6)

**B-25**

```text
Hence E_C,F1F1 ≥ E_st. An upper bound on C_st transfers as a lower bound on E_C,F1F1.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[2]/claims[3]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **B** (§2.1). Note: its own support says it "relies on the correspondence C_FF ≡ C_st (assumption A-R), which is not established"
- Status: **WITHDRAWN as unconditional**
- Added in this version (completeness check, §6)

**B-26**

```text
So E_st ≥ 0.28496 GHz, and E_C,F1F1 ≥ 0.28496 GHz only once the correspondence is established.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[2]/claims[6]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Binc** (§2.1). Note: the static-term half is not withdrawn; the condition omits only the port-model-consistent upper bound
- Status: **WITHDRAWN as stated (its condition is incomplete)**
- Added in this version (completeness check, §6)

**B-27**

```text
In state R2 (correspondence established, δC_R1 uncertified) the E_C,F1F1 interval is [0.28496, +∞).
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[2]/claims[17]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Binc** (§2.1)
- Status: **WITHDRAWN as stated (its condition is incomplete)**
- Added in this version (completeness check, §6)

**B-28**

```text
Under the registered Schur relation, E_C,F1F1 ≥ e²/(2h·C_st), so a Thomson lower bound on C_st cannot put a finite upper bound on E_C,F1F1 unless δC_R1 is also certified.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[2]/verdict`
- Type: drafting input, agent verdict (JSON)
- Why: reason **Binc** (§2.1). Note: calls the lumped Schur step "registered"; the second half (no finite upper bound) stands
- Status: **WITHDRAWN as stated (its condition is incomplete)**
- Added in this version (completeness check, §6)

**B-29**

```text
§2.4 Dirichlet row (and the reviewer's question): the upper bound C_static ≤ C_hi gives E_C,F1F1 ≥ K/C_hi = 0.28496 GHz under M1, regardless of the non-R1-mode treatment.
```

- Source: `e1/verify_results.json` (sha256 `cf730feb4755cef84b0788b485835740bb2001d6c0431bd70418526e8d1c7fec`), JSON path `[0]/items[7]/claim`
- Type: exploratory review claim, status CONFIRMED by that review (JSON)
- Why: reason **Binc** (§2.1). Note: paraphrase of B-19 that the review CONFIRMED, so asserted there
- Status: **WITHDRAWN as stated (its condition is incomplete)**
- Added in this version (completeness check, §6)

**B-30**

```text
Replace with: "Under M1 (or M2), if a human adopts it, and with C_J = 0, E_C,F1F1 ≥ K/C_hi = 0.28496 GHz follows from the recorded bound C ≤ C_hi.
```

- Source: `e1/verify_results.json` (sha256 `cf730feb4755cef84b0788b485835740bb2001d6c0431bd70418526e8d1c7fec`), JSON path `[0]/items[8]/correction`
- Also verbatim in (same claim, same status): `e1/refuted.txt` (sha256 `1acfd7ea8b597a675ea4a647ac9ca5b2430e647dcadfa4c5ad859705aff42488`)
- Type: exploratory review replacement text (JSON)
- Why: reason **Binc** (§2.1). Note: includes the adoption condition; omits only the port-model-consistent upper bound (C′ under PB)
- Status: **WITHDRAWN as stated (its condition is incomplete)**
- Added in this version (completeness check, §6)

**B-31**

```text
"E_C,F1F1 ≥ K/C_hi = 0.2849588 GHz is NEW derived arithmetic (class B). It holds under A-R and the M1 reading, with C_J = 0, on the meshed model.
```

- Source: `e1/verify_results.json` (sha256 `cf730feb4755cef84b0788b485835740bb2001d6c0431bd70418526e8d1c7fec`), JSON path `[1]/items[2]/correction`
- Also verbatim in (same claim, same status): `e1/refuted.txt` (sha256 `1acfd7ea8b597a675ea4a647ac9ca5b2430e647dcadfa4c5ad859705aff42488`)
- Type: exploratory review replacement text (JSON)
- Why: reason **Binc** (§2.1). Note: no adoption decision and no port-model condition
- Status: **WITHDRAWN as stated (its condition is incomplete)**
- Added in this version (completeness check, §6)

**B-32**

```text
[0.28496, +∞), and the lower end is pre-existing
```

- Source: `e1/verify/auditor-rev2/E1-PREDECLARATION.DRAFT.6ec25bf9.md` (sha256 `6ec25bf97dbd2b38e5cdf93e5249a1d96300cae46788cf7a95bfe51a8692d36b`), `line 235`
- Type: superseded pre-declaration draft, revision 2 (Markdown)
- Why: reason **B** (§2.1). Note: the E_C,F1F1 interval in state N, "correspondence not established"; "pre-existing" refuted in e1/verify_results.json [1]/items[2]
- Status: **WITHDRAWN as unconditional**
- Added in this version (completeness check, §6)

### 2.4 (C) Suitability, tolerance and deviation conclusions — 73 items (39 in the draft, 34 added)

**C-01**

```text
**Proposed tolerance on the design-centre E_C: about −3 % / +5 %**, which is C_Σ ≈ 30.7–33.3 fF around 32.28 fF, or about ±1 fF.
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 40`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **Ctol** (§2.1). Note: refuted: verify_results.json [1]/bottom_line "The tolerance itself is a sampling artefact."
- Status: **WITHDRAWN**

**C-02**

```text
**Model-based:** 0.342–0.360 GHz, about −40 %.
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 59`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **Cmodel** (§2.1)
- Status: **WITHDRAWN**

**C-03**

```text
For the S1 disposition, the evidence plus one classical theorem already decides it: the island is far too capacitive.
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 62`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-04**

```text
Without the theorem, the rigorous upper end of −2.4 % still touches the −3 % window edge by 0.6 points.
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 62`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-05**

```text
No further refinement of S1's C can change this.
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 63`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **C** (§2.1). Note: the recommendation not to refine S1 further is a separate human decision and is not withdrawn here
- Status: **WITHDRAWN**

**C-06**

```text
That step is sizing a replacement island to about ±3 % (about ±1 fF).
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 64`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **Ctol** (§2.1)
- Status: **WITHDRAWN**

**C-07**

```text
which decides S1 without literature once C_low > 33.3 fF;
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 78`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-08**

```text
It already excludes 0.60 GHz for the declared model.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[5]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-09**

```text
The needed fact already holds rigorously (C ≥ 33.07 fF > 32.93 fF).
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **C** (§2.1). Note: 32.93 fF is the upper edge of an unregistered capacitance window [31.6, 32.9] fF, a ±2 % band on C (same verdict, "C2" paragraph)
- Status: **WITHDRAWN**

**C-10**

```text
The model-based value is about 0.34–0.37 GHz.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **Cmodel** (§2.1)
- Status: **WITHDRAWN**

**C-11**

```text
DERIVED, tightest from frozen HARD gates: E_C ≥ 0.569–0.570 GHz (−5.0 to −5.1 %).
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **Ctol** (§2.1). Note: the notch edge itself remains a valid model sensitivity (rev6 line 272)
- Status: **WITHDRAWN**

**C-12**

```text
The model-based reading, e²/2C_h = 0.342–0.360 GHz, puts the seed at −40 to −43 % if k² is small (an ASSUMPTION).
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **Cmodel** (§2.1)
- Status: **WITHDRAWN**

**C-13**

```text
To decide "out of tolerance" requires only a certified one-sided LOWER bound above 34.0 fF on the loaded capacitance 1/(C^-1)_FF.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-14**

```text
The tightest tolerance derived from the frozen HARD gates is asymmetric.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/claims[19]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Ctol** (§2.1)
- Status: **WITHDRAWN**

**C-15**

```text
A certified LOWER bound above 34.0 fF on the loaded island capacitance 1/(C^-1)_FF (other declared nodes floating) would decide 'out of tolerance'.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/claims[26]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **C** (§2.1). Note: also (D): "other declared nodes floating"
- Status: **WITHDRAWN**

**C-16**

```text
The model-based reading, about −40 %, is far outside tolerance and in a region where the repo root-finder returns spurious roots.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-17**

```text
**1. The question "is the S1 island on the E_C target?" is already answered: NO. Refining C further will not change that answer.**
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-18**

```text
The contiguous operating window around the nominal readout root runs from 0.887 to 1.114 × target, and this bound lies below it.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-19**

```text
The required change in C_Σ: rigorously a factor between 0.475 and 0.865; model-based 0.57 to 0.60.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-20**

```text
**So the architecture needs E_C to about ±3 %, certified, not sub-percent.**
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **Ctol** (§2.1)
- Status: **WITHDRAWN**

**C-21**

```text
**Is S1 on target?** No.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-22**

```text
Either way it lies below the operating window of about 0.887–1.114 × target.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-23**

```text
It must fall by a factor between 0.475 and 0.865 rigorously, and 0.57–0.60 on the model.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-24**

```text
**What accuracy does the architecture need?** About ±3 % on the design-centre E_C, not sub-percent.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **Ctol** (§2.1)
- Status: **WITHDRAWN**

**C-25**

```text
(the desk curve suggests about ±3 %)
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/open_questions[0]`
- Type: exploratory agent open question (JSON)
- Why: reason **Ctol** (§2.1)
- Status: **WITHDRAWN**

**C-26**

```text
Against the -3% window edge (0.582 GHz, C = 33.282 fF) the threshold is 11.530, so at eps_r = 11.45 the Thomson bound alone does not exclude the window.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/items[11]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-27**

```text
From a frozen hard gate, for the design-centre device only (g = 0.150 GHz, E_J and E_L nominal, per-device trim), b ≥ -5.1 % (C_Σ ≤ 34.0 fF).
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[1]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **Ctol** (§2.1). Note: offered as "the most defensible statement" of a tolerance
- Status: **WITHDRAWN**

**C-28**

```text
because E_C,F1F1 <= 0.509-0.519 GHz lies outside every candidate window.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/items[1]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **C** (§2.1). Note: rests also on (A)
- Status: **WITHDRAWN**

**C-29**

```text
Present S1 as out of tolerance for any k^2, using X1 and E'-lite, as desk results to be formally recorded only if the human wants it.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **C** (§2.1). Note: also (D); rev6 §11 misattributed this to chat only
- Status: **WITHDRAWN**

**C-30**

```text
That is 5.81 fF (k² ≥ 0.152, g ≥ 1.25 GHz) at C_static = 38.09 fF, and 24.72 fF (k² ≥ 0.434, g ≥ 2.12 GHz) at 57.00 fF.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/summary`
- Type: drafting input, agent summary (JSON)
- Why: reason **Ckthr** (§2.1)
- Status: **WITHDRAWN**

**C-31**

```text
E_C,F1F1 < 0.600 GHz then requires g²/(4f_R1) < 91.46 MHz: g < 1.164 / 1.255 / 1.353 GHz at f_R1 = 3.7 / 4.302 / 5.0 GHz, i.e. k² < 0.1524.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[0]/claims[14]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Ckthr** (§2.1)
- Status: **WITHDRAWN**

**C-32**

```text
The model-based bracket puts E_C at 0.57 to 0.60 times the target.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **Cmodel** (§2.1)
- Status: **WITHDRAWN**

**C-33**

```text
The model-based E_C is 0.57–0.60 × target.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **Cmodel** (§2.1)
- Status: **WITHDRAWN**

**C-34**

```text
It turns the "not on target" answer into an evidence record that does not depend on literature or k².
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **C** (§2.1). Note: also (D)
- Status: **WITHDRAWN**

**C-35**

```text
For S1, after E′ this is expected immediately, so E′ is the last S1 computation.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **C** (§2.1). Note: predicts the NOT ON TARGET outcome of the proposed stop rule
- Status: **WITHDRAWN**

**C-36**

```text
(a) S1 decision. X1 settles it in under 1 s (x1_s1.py, bem.py).
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/items[0]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**C-37**

```text
for tag, Cedge in (("-3% edge", 32.2837e-15/0.97), ("-5% hard gate", 34.0e-15), ("root-bracket exit -11.29%", 32.2837e-15/0.8871)):
```

- Source: `verify/s3/x1_s1.py` (sha256 `9572265cfb60f3eef3bfe391b833658e0f69e8c08467ce1f5f7ef0b8af4a50a2`), `line 27`
- Type: script code (tolerance edges)
- Why: reason **Ctol** (§2.1)
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**

**C-38**

```text
print(f"-3% edge 0.582 GHz; Thomson margin to it:
```

- Source: `verify/thomson/consts.py` (sha256 `74db861e81a925653a737ffdcc4a0e1074966386314962964236a3dfb79feea1`), `line 19`
- Type: script print format
- Why: reason **Ctol** (§2.1)
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**

**C-39**

```text
That is DIFFERS (BELOW) and FAILS every one of T1′, T2, T3 and T4 on the low side.
```

- Source: `e1/verify/auditor-rev2/E1-PREDECLARATION.DRAFT.6ec25bf9.md` (sha256 `6ec25bf97dbd2b38e5cdf93e5249a1d96300cae46788cf7a95bfe51a8692d36b`), `line 257`
- Also verbatim in (same claim, same status): `e1/refuted.txt` (sha256 `1acfd7ea8b597a675ea4a647ac9ca5b2430e647dcadfa4c5ad859705aff42488`), `e1/verify_results.json` (sha256 `cf730feb4755cef84b0788b485835740bb2001d6c0431bd70418526e8d1c7fec`)
- Type: superseded pre-declaration draft, revision 2 (Markdown)
- Why: reason **C** (§2.1). Note: the verdict words were emitted without the "CONDITIONAL ON QT" label (e1/verify_results.json [1]/items[4]/evidence)
- Status: **WITHDRAWN**

**C-40**

```text
Closing the gap to 0.60 GHz would need g = 2.03-2.11 GHz from the model-based E_S, or 2.33 GHz from the rigorous level-2 E_S: 13.5-15.5 times the source g, which would violate the architecture on its own.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[8]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Ckthr** (§2.1). Note: also a Master-g comparison (rev6 §2.5 item 3)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-41**

```text
- The A-R/Schur term is exactly g²/(4f_R): 1.3 MHz at the source g, and closing the gap would need g of 2.0-2.3 GHz.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **Ckthr** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-42**

```text
The readout cannot rescue the seed.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[7]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **C** (§2.1). Note: the rest of the claim is A-07 and D-04
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-43**

```text
Pushing E_C down, so no rescue:
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[10]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-44**

```text
None of these can close about 1.7x in C at eps_r = 11.45.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[10]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Cmodel** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-45**

```text
The keep-or-resize decision for the seed needs only a one-sided bound, which the analytic bound already provides.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[14]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-46**

```text
Sizing a replacement island to the Master device needs a systematic E_C error of roughly 1 % or less
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[14]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Ctol** (§2.1). Note: labelled heuristic by its author
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-47**

```text
The seed's own sizing rationale ('coplanar capacitance lands near 32.28 fF') is refuted for the declared model: the island alone, with no ground plane, already has C >= 33.07 fF.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[16]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **C** (§2.1). Note: C_static ≥ 33.07 fF stands as a capacitance (§3); 32.28 fF is the image of the registered 1/(C⁻¹)_F1F1, "not of C_static" (planning note rev6 line 26)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-48**

```text
2. Does the present uncertainty block the next decision? No for the seed.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-49**

```text
The yes/no decision on the S1 seed therefore needs only a one-sided bound.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-50**

```text
Sizing a replacement island needs roughly 1 % (heuristic, not a repository rule).
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **Ctol** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-51**

```text
- The tolerance is strongly ASYMMETRIC: C_Sigma too large is the dangerous side, and it is the side the refinement study points to.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **Ctol** (§2.1). Note: also (C): the direction S1 lies in
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-52**

```text
That is about 8× beyond the −5 % hard-gate limit.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **C** (§2.1). Note: the sentence after C-12
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-53**

```text
On a model basis, C_h of 53.75–56.68 fF gives E_C 0.342–0.360 GHz (−40 to −43 %) if the Schur gap k² is small. That is about 8× beyond the −5 % hard-gate limit, and in the region where the dressed model has no genuine null in the bracket.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/claims[25]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Cmodel** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-54**

```text
On the low side, E_C ≥ 0.569–0.570 GHz (b ≥ −5.0 to −5.1 %), i.e. loaded C_Sigma = 1/(C^-1)_FF ≤ 33.98–34.02 fF, including C_J.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/claims[19]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Ctol** (§2.1). Note: the sentence after C-14; the notch edge remains a valid model sensitivity (rev6 line 272)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-55**

```text
The only limit that follows from the frozen hard gates is one-sided. The nominal design first fails the 13 MHz collision gate at E_C bias −5.0 to −5.1 % (E_C ≥ 0.569 GHz, loaded C_Sigma ≤ 34.0 fF, only +1.7 fF over 32.28 fF).
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **Ctol** (§2.1). Note: withdrawn as a limit; the notch edge remains a valid model sensitivity (rev6 line 272)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-56**

```text
A certified one-sided lower bound above 34 fF on the loaded island capacitance would settle it.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **C** (§2.1). Note: same content as C-13
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-57**

```text
If it is one, the E_C tolerance tightens from about −5 % to about −0.6 to −2 %.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/open_questions[1]`
- Type: exploratory agent open question (JSON)
- Why: reason **Ctol** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-58**

```text
Only the 33.07 fF inscribed-disk bound is fully elementary, and it alone does NOT exclude the operating window.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/claims[7]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **C** (§2.1). Note: implies that the other bounds do exclude it
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-59**

```text
The architecture needs the design-centre E_C to about ±3 %, certified. In C terms that is about ±1 fF at 32 fF, not sub-percent.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/claims[15]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Ctol** (§2.1). Note: same tolerance as C-20 and C-24
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-60**

```text
The S1 island (0.0225 mm²) fails this before any ground-proximity capacitance is counted.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/claims[24]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **C** (§2.1). Note: the area criterion rests on a Pólya–Szegő capacitance lower bound set against 32.284 fF, the image of the registered 1/(C⁻¹)_F1F1 (reason A)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-61**

```text
- **H (resize the island)** is a human design decision, not a measurement. The evidence now supports opening it, but prior tasks excluded it.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **C** (§2.1). Note: rests on C-17; the resize decision itself stays a human decision and is not withdrawn
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-62**

```text
(1) Running anything more on S1 itself is only 'refining for a nicer number', given S1 is already off target.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/items[1]/claim`
- Type: exploratory review claim, status CONFIRMED by that review (JSON)
- Why: reason **C** (§2.1). Note: its evidence is C-28 and F-03
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-63**

```text
It requires g²/(4f_R1) < 260.17 MHz: g < 1.96 to 2.28 GHz, k² < 0.4336.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[0]/claims[14]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Ckthr** (§2.1). Note: the 57.00 fF counterpart of C-31
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-64**

```text
The cap needed is loose: 91.46 MHz for C_T = 38.09 fF, 260.17 MHz for C_T = 57.00 fF.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[0]/open_questions[1]`
- Type: drafting input, agent open question (JSON)
- Why: reason **Ckthr** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-65**

```text
What S1 would need for E_C,F1F1 to reach 0.60 GHz under M1 (dC_R1 ≥ C_static − 32.2837 fF; g computed with f_R* = 4.302 GHz, an ASSUMPTION):
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/claims[21]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Ckthr** (§2.1). Note: heads a table of dC_R1, k² and g thresholds at 33.07, 38.09, 57.00 and 67.9755 fF, with a "× Master g" column (rev6 §2.5 item 3)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-66**

```text
- That corresponds to k² ≈ 6e-4 to 0.033 and an E_C shift g²/(4f_R*) ≈ 0.2–17.6 MHz, which is 4.5–130× below the 5.81 fF needed at C_static = 38.09 fF.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/claims[22]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **Ckthr** (§2.1). Note: the dC_R1 model estimate itself is ASSUMPTION-level (§3)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-67**

```text
DIFFERS (BELOW), T1′ (0.509 < 0.569335) and T3a/T3b (0.509 < 0.588 and < 0.576) are CONFIRMED.
```

- Source: `e1/verify_results.json` (sha256 `cf730feb4755cef84b0788b485835740bb2001d6c0431bd70418526e8d1c7fec`), JSON path `[2]/items[23]/evidence`
- Also verbatim in (same claim, same status): `e1/refuted.txt` (sha256 `1acfd7ea8b597a675ea4a647ac9ca5b2430e647dcadfa4c5ad859705aff42488`)
- Type: exploratory review finding (JSON)
- Why: reason **C** (§2.1). Note: confirms the C-39 verdicts on the QT interval of D-19 (also reason DQT)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-68**

```text
"… that is DIFFERS (BELOW) and FAILS T1′ and T3 on the low side;
```

- Source: `e1/verify_results.json` (sha256 `cf730feb4755cef84b0788b485835740bb2001d6c0431bd70418526e8d1c7fec`), JSON path `[2]/items[23]/correction`
- Also verbatim in (same claim, same status): `e1/refuted.txt` (sha256 `1acfd7ea8b597a675ea4a647ac9ca5b2430e647dcadfa4c5ad859705aff42488`)
- Type: exploratory review replacement text (JSON)
- Why: reason **C** (§2.1). Note: also reason DQT
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-69**

```text
both edges; low for S1
```

- Source: `e1/verify/auditor-rev2/E1-PREDECLARATION.DRAFT.6ec25bf9.md` (sha256 `6ec25bf97dbd2b38e5cdf93e5249a1d96300cae46788cf7a95bfe51a8692d36b`), `line 199`
- Type: superseded pre-declaration draft, revision 2 (Markdown)
- Why: reason **C** (§2.1). Note: column "binding side for S1" of the candidate-tolerance table, lines 196–200 ("low", "low (marginally)"): states the side S1 lies on before any E1 result
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-70**

```text
print('E_S', ES, 'needs g =', round(math.sqrt(4*fR*need),3), 'GHz to reach 0.60; k^2 =', round(1-ES/0.60,3))
```

- Source: `agents/schur_identity.py` (sha256 `6c5fb033753c1c48af2f7c99be886ae91c1925f91fcf27d9ad9f54c4fa9b8d3f`), `line 31`
- Type: script print format
- Why: reason **Ckthr** (§2.1). Note: E_S = 0.28496, 0.34175, 0.36038 GHz (line 29); file not in the rev6 §11 register
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**
- Added in this version (completeness check, §6)

**C-71**

```text
The agent-derived g tolerance is about ±10–20 %.
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 42`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **Ctol** (§2.1). Note: a g tolerance; none is registered either (coupling-definition.md §6, rev6 line 271)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-72**

```text
The derived tolerance is about ±10–20 %, and upward it is set by the filter-depth/κ trade.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **Ctol** (§2.1). Note: a g tolerance, as C-71
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**C-73**

```text
The derived tolerance is about ±10–20 %, and upward it is set by the filter-depth/κ trade.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[2]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **Ctol** (§2.1). Note: a g tolerance
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

### 2.5 (D) QT-conditional and floating-R1 ("any k²") claims — 33 items (19 in the draft, 14 added)

**D-01**

```text
Under the Maxwell/Kron reading, the floating- or removed-readout configuration is covered.
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 56`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**

**D-02**

```text
makes the S1 decision literature-free for any k².
```

- Source: `DRAFT-recommendation.md` (sha256 `3ca808ae19555c7053f3ad495c8cfb1a84c33ee36b0ac68f45d09d8d0c6b2486`), `line 89`
- Type: exploratory draft recommendation (Markdown)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**

**D-03**

```text
It holds whether the readout is grounded or floating, and for any quasi-static reading of the readout mode.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**

**D-04**

```text
In the node basis (readout conductor floating, Kron-reduced), C_red >= C_absent >= C_iso
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[7]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**

**D-05**

```text
the floating/removed-conductor monotonicity bound is the one that works.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**

**D-06**

```text
1/(C^-1)_FF equals the island capacitance with the readout conductor floating (Q_R = 0), C_float.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/claims[5]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**

**D-07**

```text
(ii) readout conductor removed. This gives a lower bound on C_Σ,eff that holds for any k².
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/verdict`
- Type: exploratory agent verdict (JSON)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**

**D-08**

```text
so it is admissible and 1/(C^-1)_FF >= 33.07 fF whatever the geometric k^2.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/items[7]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**

**D-09**

```text
This is why 'any k^2' is legitimate in the electrostatic reading.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/items[8]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**

**D-10**

```text
It is right for every electrostatic (Maxwell/Kron) reading, including any way of cutting the DC-grounded readout free.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**

**D-11**

```text
gives C >= 53.6 fF (any k^2)
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/items[3]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **Dfloat** (§2.1). Note: the capacitance value itself is kept as exploratory prior knowledge (§3)
- Status: **WITHDRAWN**

**D-12**

```text
**(ii) R1 REMOVED does transfer, but only under QT.**
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/claims[14]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **DQT** (§2.1)
- Status: **WITHDRAWN**

**D-13**

```text
Hence T ≤ 1/(C⁻¹)_FF for every Thomson/Galerkin trial field admissible in the R1-removed configuration, for any k² and any mode profile.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/claims[16]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **DQT** (§2.1). Note: stated under "Rigorous consequences within QT"
- Status: **WITHDRAWN as a statement about the registered operator (the within-QT-S relation under M1, planning note rev6 §6, is not withdrawn as a surrogate statement)**

**D-14**

```text
under QT they would give E_C,F1F1 ≤ 0.586 GHz and ≤ 0.5085 GHz.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/verdict`
- Type: drafting input, agent verdict (JSON)
- Why: reason **DQT** (§2.1). Note: also (A)
- Status: **WITHDRAWN**

**D-15**

```text
So a Thomson/Galerkin trial field that is admissible with the R1 metal REMOVED is proven to bound the registered quantity from below. The disk bound (33.07 fF) and the square plate × (1+ε_r)/2 bound (38.09 fF) qualify.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/summary`
- Type: drafting input, agent summary (JSON)
- Why: reason **DQT** (§2.1)
- Status: **WITHDRAWN**

**D-16**

```text
their trial fields are admissible in the R1-removed configuration, so under QT they bound 1/(C⁻¹)_FF.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/claims[20]/claim`
- Type: drafting input, agent claim (JSON)
- Why: reason **DQT** (§2.1)
- Status: **WITHDRAWN as a statement about the registered operator (the within-QT-S relation under M1, planning note rev6 §6, is not withdrawn as a surrogate statement)**

**D-17**

```text
Under QT it is PROVEN that 1/(C⁻¹)_FF ≥ C_float(all segments) = C_inf ≥ C_removed.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/verdict`
- Type: drafting input, agent verdict (JSON)
- Why: reason **DQT** (§2.1)
- Status: **WITHDRAWN as a statement about the registered operator (the within-QT-S relation under M1, planning note rev6 §6, is not withdrawn as a surrogate statement)**

**D-18**

```text
the E_C interval would be [0.285, 0.512] GHz, CONDITIONAL ON QT.
```

- Source: `e1/verify_results.json` (sha256 `cf730feb4755cef84b0788b485835740bb2001d6c0431bd70418526e8d1c7fec`), JSON path `[2]/items[22]/correction`
- Also verbatim in (same claim, same status): `e1/refuted.txt` (sha256 `1acfd7ea8b597a675ea4a647ac9ca5b2430e647dcadfa4c5ad859705aff42488`)
- Type: exploratory review replacement text (JSON)
- Why: reason **DQT** (§2.1). Note: also (A) upper end, (B) lower end
- Status: **WITHDRAWN**

**D-19**

```text
Under Q that would give E_C,F1F1 ∈ [0.285, 0.509] GHz, CONDITIONAL ON QT.
```

- Source: `e1/verify/auditor-rev2/E1-PREDECLARATION.DRAFT.6ec25bf9.md` (sha256 `6ec25bf97dbd2b38e5cdf93e5249a1d96300cae46788cf7a95bfe51a8692d36b`), `line 257`
- Type: superseded pre-declaration draft, revision 2 (Markdown)
- Why: reason **DQT** (§2.1). Note: also (A), (B)
- Status: **WITHDRAWN**

**D-20**

```text
- A second argument gives a bound that does not depend on k² and holds for any C_J ≥ 0.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/summary`
- Type: exploratory agent report (JSON)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**D-21**

```text
The bound holds for any k².
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/claims[5]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Dfloat** (§2.1). Note: first sentence of the claim quoted in D-06
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**D-22**

```text
So C_noR <= C_float = C_Sigma,eff <= C_FF(A-R) <= C_2 = 67.98 fF. Any lower bound on the island with the readout removed is therefore a lower bound on C_Sigma,eff, whatever the unmeasured k², and C_J >= 0 only raises it.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[3]/claims[5]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Dfloat** (§2.1). Note: also (B): C_Sigma,eff ≤ 67.98 fF stated unconditionally
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**D-23**

```text
The same holds in any quasi-static LC description, including a normal-mode reading that keeps any subset of modes: 1/C_h + sum over k of A_k = 1/C_all-floating, with Foster residues A_k >= 0, and C_all-floating >= C_absent.
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[1]/claims[7]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**D-24**

```text
An upper bound on E_C,F1F1 would need a lower bound on 1/(C⁻¹)_FF = C_FF(1 − k²). That is the island capacitance with the readout floating at zero net charge
```

- Source: `workflow_results.json` (sha256 `76d7f384260f8dd4382f00a771d521b0bc26dee77c753ca8b2f72e773b33615c`), JSON path `[0]/claims[17]/claim`
- Type: exploratory agent claim (JSON)
- Why: reason **Dfloat** (§2.1). Note: the first sentence stands; the identification in the second is withdrawn
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**D-25**

```text
(3a) 'For any k^2 and any C_J >= 0' under the Maxwell/Kron reading: 1/(C^-1)_FF (readout floating, zero net charge) >= 33.07 fF
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/items[7]/claim`
- Type: exploratory review claim, status CONFIRMED by that review (JSON)
- Why: reason **Dfloat** (§2.1). Note: its evidence is A-14 and D-08
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**D-26**

```text
'Any k^2' is valid only for electrostatic (Maxwell/Kron) readings; the draft should say so, pending the definition decision it lists.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/items[9]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**D-27**

```text
The 1.3 MHz term is exact only in the two-node truncation, where the Kron bound already covers it.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[0]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**D-28**

```text
§3 alternative X1: a certified free-space Galerkin charge bound on the square plate times the exact half-space factor takes seconds, needs no mesh, and decides S1 literature-free for any k^2.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/items[2]/claim`
- Type: exploratory review claim, status CONFIRMED by that review (JSON)
- Why: reason **Dfloat** (§2.1). Note: also (C); a CONFIRMED paraphrase of DRAFT-recommendation.md line 89 (D-02), not a verbatim quotation
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**D-29**

```text
So a Thomson/Galerkin bound on the R1-REMOVED configuration bounds the registered effective capacitance from below.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/verdict`
- Type: drafting input, agent verdict (JSON)
- Why: reason **DQT** (§2.1). Note: the sentence after D-17; asserts transfer to the registered quantity
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**D-30**

```text
The modal correction is about 2× the floating-metal Kron correction (1.94–2.07 in the synthetic models), and 1/(C⁻¹)_FF is below the floating-metal value.
```

- Source: `e1/inputs.json` (sha256 `2c84b353030643d4ede75f67c700cab9a5889d45ff95cd57da447cc3c927fceb`), JSON path `[1]/summary`
- Type: drafting input, agent summary (JSON)
- Why: reason **Dreg** (§2.1)
- Status: **WITHDRAWN as a statement about the registered 1/(C⁻¹)_F1F1 (the synthetic-model ratio stands)**
- Added in this version (completeness check, §6)

**D-31**

```text
- **Under QT-M1 (if approved):** E_C,F1F1 ∈ [K/C_hi, K/C_lo^removed], labelled **"CONDITIONAL ON QT"** on every line where it appears.
```

- Source: `e1/verify/auditor-rev2/E1-PREDECLARATION.DRAFT.6ec25bf9.md` (sha256 `6ec25bf97dbd2b38e5cdf93e5249a1d96300cae46788cf7a95bfe51a8692d36b`), `line 157`
- Type: superseded pre-declaration draft, revision 2 (Markdown)
- Why: reason **DQT** (§2.1). Note: the template behind D-19
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**D-32**

```text
- Ring excludes all R1 metal: the result is also admissible with R1 removed, and may therefore feed C_lo^removed under Q.
```

- Source: `e1/verify/auditor-rev2/E1-PREDECLARATION.DRAFT.6ec25bf9.md` (sha256 `6ec25bf97dbd2b38e5cdf93e5249a1d96300cae46788cf7a95bfe51a8692d36b`), `line 288`
- Type: superseded pre-declaration draft, revision 2 (Markdown)
- Why: reason **DQT** (§2.1). Note: also found internally contradictory and inadmissible for R1 removed (e1/verify_results.json [1]/items[6]/evidence)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**D-33**

```text
tag = "A-R (R1 pad/CPW grounded, bounds C_FF only)" if cR1 else "any k^2 (no charge on R1)"
```

- Source: `verify/s3/eprime2.py` (sha256 `1ca9bd089bf0a03ec41f9e80331f54328f31a4b4678eccd5b62fc3eeffc6260c`), `line 62`
- Type: script code (print label)
- Why: reason **Dfloat** (§2.1). Note: labels the R1-uncharged runs (53.57–53.61 fF, A-20) "any k^2"
- Status: **WITHDRAWN as an E_C statement (script kept unchanged)**
- Added in this version (completeness check, §6)

### 2.6 (E) Chat-level claims (assistant text in the session transcript) — 19 items (14 in the draft, 5 added)

Each item's reason code refers to the reason list in §2.1.

**E-01**

```text
`e²/(2C_h) ≤ e²/(2C_FF) ≤ E_C,F1F1`
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 29191, timestamp 2026-09-22T18:27:54.890Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **Binc** (§2.1). Note: context: "It gives only a **lower bound** on `E_C`, never `E_C` itself"; predates the exploratory work (22 Sept); same chain as a registered repository document, see §5
- Status: **WITHDRAWN as stated (its condition is incomplete)**

**E-02**

```text
the likely decision is "the island is far too capacitive" (about 40 % low in E_C)
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 33762, timestamp 2026-09-23T08:02:35.922Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**E-03**

```text
More refinement won't change the decision, because the S1 island is far off target.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**

**E-04**

```text
**Hard limit, low side:** the 13 MHz collision gate fails for the design-centre device once E_C is more than 5.1 % low. That caps the total island capacitance at C_Σ ≤ 34.0 fF, against the 32.28 fF target.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **Ctol** (§2.1)
- Status: **WITHDRAWN**

**E-05**

```text
So the architecture needs E_C to about 1–5 %, and only on the low-E_C (high-capacitance) side, which is about 0.3–1.7 fF of C_Σ.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **Ctol** (§2.1)
- Status: **WITHDRAWN**

**E-06**

```text
| C ≤ 67.98 fF (the study, rigorous) | ≥ 0.285 GHz | rigorous for the meshed model with C_J = 0 |
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text, table row)
- Why: reason **B** (§2.1)
- Status: **WITHDRAWN as unconditional**

**E-07**

```text
| C ≥ 33.07 fF (disk inscribed in the island, Thomson principle) | ≤ 0.586 GHz | derived by me; confirmed by the check |
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text, table row)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**E-08**

```text
| C ≥ 38.09 fF (Galerkin charge bound on the square plate) | ≤ 0.509 GHz (−15 %) |
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text, table row)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**E-09**

```text
| C_FF ≥ 57.00 fF (charge bound on the island plus surrounding ground) | ≤ 0.340 GHz |
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text, table row)
- Why: reason **A** (§2.1)
- Status: **WITHDRAWN**

**E-10**

```text
**The S1 island fails the hard gate.** The 38.09 fF bound is already above the 34.0 fF limit.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **C** (§2.1). Note: nearest chat form of "S1 is out of tolerance"
- Status: **WITHDRAWN**

**E-11**

```text
That holds whatever the coupling factor k² or junction capacitance C_J, for any box size or metal thickness, and for substrate permittivity ε_r ≥ 10.9.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**

**E-12**

```text
**Scope of the bounds:** they hold for electrostatic (Maxwell/Kron) readings of E_C,F1F1.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **Dfloat** (§2.1)
- Status: **WITHDRAWN**

**E-13**

```text
**Realistic range:** S1's E_C is about 0.29–0.36 GHz, so the island needs roughly half its current capacitance.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **Cmodel** (§2.1)
- Status: **WITHDRAWN**

**E-14**

```text
A lower bound above 34.0 fF for any k² certifies S1 as not on target.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **C** (§2.1). Note: also (D)
- Status: **WITHDRAWN**

**E-15**

```text
- **Derived, lower bound only, under the stated readout assumption:** `E_C/h ≥ 235.6 MHz`.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 29778, timestamp 2026-09-22T20:06:38.680Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **Binc** (§2.1). Note: reports the class-B figure of the registered static-anchor-hypothesis.md:274-275 (see §5)
- Status: **WITHDRAWN as stated (its condition is incomplete)**
- Added in this version (completeness check, §6)

**E-16**

```text
What stops it being rigorous is a missing lower bound on C, not more refinement of the upper bound.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 33762, timestamp 2026-09-23T08:02:35.922Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **A** (§2.1). Note: the sentence after E-02
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**E-17**

```text
For the S1 island ("is it on target?"): no.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **C** (§2.1)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**E-18**

```text
The seed declaration said the island was sized "to land near 32.28 fF"; that rationale does not hold.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **C** (§2.1). Note: 32.28 fF is the image of the registered 1/(C⁻¹)_F1F1, not of C_static (planning note rev6 line 26)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

**E-19**

```text
What blocks the step after that, sizing a replacement island to about 1–2 fF, is mostly inputs rather than C precision.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **Ctol** (§2.1). Note: presupposes that S1 must be replaced (reason C)
- Status: **WITHDRAWN**
- Added in this version (completeness check, §6)

### 2.7 (F) Related: E1's Q2 outcome asserted in advance — 6 items

This group is outside groups A–E. The same search found these statements, and the rev6 review raised them (prior-knowledge MINOR, rev6_findings.txt lines 1452–1476, "the exploratory reports already asserted E1's Q2 outcome").

**F-01**

```text
This exceeds the top of the study's model-based bracket (56.68 fF), so the bracket's premise is contradicted.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **F** (§2.1)
- Status: **WITHDRAWN as a conclusion (unestablished)**

**F-02**

```text
That is X2's own "premise refuted" outcome, reached without X2.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/bottom_line`
- Type: exploratory review bottom line (JSON)
- Why: reason **F** (§2.1)
- Status: **WITHDRAWN as a conclusion (unestablished)**

**F-03**

```text
X2's predeclared 'premise refuted' outcome (C_low > 56.68 fF) is already reached by the desk A-R bound of 57.00 fF.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/items[1]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **F** (§2.1)
- Status: **WITHDRAWN as a conclusion (unestablished)**

**F-04**

```text
so the true limit of the meshed model lies above the bracket.
```

- Source: `verify_results.json` (sha256 `adc98eed35963eaa95203ce7c62d183e06bef9d4e0440247e9fce67d94994335`), JSON path `[2]/items[13]/evidence`
- Type: exploratory review finding (JSON)
- Why: reason **F** (§2.1)
- Status: **WITHDRAWN as a conclusion (unestablished)**

**F-05**

```text
That is above 56.675 fF, so the model-bracket premise would be refuted.
```

- Source: `e1/verify/auditor-rev2/E1-PREDECLARATION.DRAFT.6ec25bf9.md` (sha256 `6ec25bf97dbd2b38e5cdf93e5249a1d96300cae46788cf7a95bfe51a8692d36b`), `line 258`
- Type: superseded pre-declaration draft, revision 2 (Markdown)
- Why: reason **F** (§2.1)
- Status: **WITHDRAWN as a conclusion (unestablished)**

**F-06**

```text
**Contradiction with the study:** the 57.00 fF result sits above the study's model-based limit bracket (53.75–56.68 fF), which would mean the bracket's one-sign assumption fails.
```

- Source: session transcript `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988.jsonl` (lines 1–35004 sha256 `d656e9b2a8253b57d41ca163be0b4e12c2a7058042747686d3b60bc8840842e6`), line 34021, timestamp 2026-09-23T09:55:16.082Z, assistant text block 0
- Type: chat statement (assistant text)
- Why: reason **F** (§2.1)
- Status: **WITHDRAWN as a conclusion (unestablished)**

### 2.8 (G) Superseded pre-declaration revisions 3 and 4 — 7 items (all added)

These statements are in superseded pre-declaration texts: the revision-3 draft and the frozen revision 4 (and its working copy `e1/E1-PREDECLARATION.DRAFT.md`, byte-identical). The pre-declaration chain has already corrected them: revision 5 replaced §2.3 item 5 and added the port-model condition after the review of revision 4 (`e1/final_findings.txt`, sha256 `67ad1e8d6292623432d5469ccc05193a8070b6bd6ea25ee0ffe25fbdb7722fcb`, lines 118 and 121–122). They are listed so that this record is complete. The frozen files stay unchanged.

**G-01**

```text
(C⁻¹)_FF = 1/C_static + 1/C_R1,eff, so C_Σ,reg = C_static·C_R1,eff/(C_static + C_R1,eff) < C_static.
```

- Source: `e1/verify3/rev3-auditor/E1-PREDECLARATION.DRAFT.4e4ac852.md` (sha256 `4e4ac852a40c186644b47f4094db58db24890f042d5b4bafa57354a8ac812496`), `line 131`
- Type: superseded pre-declaration draft, revision 3 (Markdown)
- Why: reason **Breg** (§2.1)
- Status: **WITHDRAWN as stated (superseded; already corrected in a later revision)**
- Added in this version (completeness check, §6)

**G-02**

```text
The registered 1/(C⁻¹)_FF lies **below** the floating-metal value.
```

- Source: `e1/verify3/rev3-auditor/E1-PREDECLARATION.DRAFT.4e4ac852.md` (sha256 `4e4ac852a40c186644b47f4094db58db24890f042d5b4bafa57354a8ac812496`), `line 133`
- Type: superseded pre-declaration draft, revision 3 (Markdown)
- Why: reason **Dreg** (§2.1)
- Status: **WITHDRAWN as stated (superseded; already corrected in a later revision)**
- Added in this version (completeness check, §6)

**G-03**

```text
**Only under M1 (or M2), if a human adopts it, and with the given C_J:** E_C,F1F1 ≥ K/(C_hi + C_J) = 0.28495882 GHz at C_J = 0.
```

- Source: `e1/verify3/rev3-auditor/E1-PREDECLARATION.DRAFT.4e4ac852.md` (sha256 `4e4ac852a40c186644b47f4094db58db24890f042d5b4bafa57354a8ac812496`), `line 139`
- Type: superseded pre-declaration draft, revision 3 (Markdown)
- Why: reason **Binc** (§2.1). Note: omits only the port-model-consistent upper bound
- Status: **WITHDRAWN as stated (superseded; already corrected in a later revision)**
- Added in this version (completeness check, §6)

**G-04**

```text
If a human adopts M1 before execution, the lower-side line "E_C,F1F1 ≥ K/(C_hi + C_J) [NEW class-B arithmetic under M1]" may be added.
```

- Source: `e1/verify3/rev3-auditor/E1-PREDECLARATION.DRAFT.4e4ac852.md` (sha256 `4e4ac852a40c186644b47f4094db58db24890f042d5b4bafa57354a8ac812496`), `line 167`
- Type: superseded pre-declaration draft, revision 3 (Markdown)
- Why: reason **Binc** (§2.1). Note: omits the port-model-consistent upper bound
- Status: **WITHDRAWN as stated (superseded; already corrected in a later revision)**
- Added in this version (completeness check, §6)

**G-05**

```text
(C⁻¹)_FF = 1/C_static + 1/C_R1,eff, so C_Σ,reg < C_static.
```

- Source: `e1/frozen/E1-PREDECLARATION.rev4.ee69027f42dd8a8c642050216f322de58ee78f550240ecd2bbf2eaa2f552cc0a.md` (sha256 `ee69027f42dd8a8c642050216f322de58ee78f550240ecd2bbf2eaa2f552cc0a`), `line 144`
- Also verbatim in (same claim, same status): `e1/E1-PREDECLARATION.DRAFT.md` (sha256 `ee69027f42dd8a8c642050216f322de58ee78f550240ecd2bbf2eaa2f552cc0a`)
- Type: superseded frozen pre-declaration, revision 4 (Markdown)
- Why: reason **Breg** (§2.1). Note: corrected in revision 5 after e1/final_findings.txt lines 121–122
- Status: **WITHDRAWN as stated (superseded; already corrected in a later revision)**
- Added in this version (completeness check, §6)

**G-06**

```text
The registered 1/(C⁻¹)_FF lies **below** the floating-metal value.
```

- Source: `e1/frozen/E1-PREDECLARATION.rev4.ee69027f42dd8a8c642050216f322de58ee78f550240ecd2bbf2eaa2f552cc0a.md` (sha256 `ee69027f42dd8a8c642050216f322de58ee78f550240ecd2bbf2eaa2f552cc0a`), `line 146`
- Also verbatim in (same claim, same status): `e1/E1-PREDECLARATION.DRAFT.md` (sha256 `ee69027f42dd8a8c642050216f322de58ee78f550240ecd2bbf2eaa2f552cc0a`)
- Type: superseded frozen pre-declaration, revision 4 (Markdown)
- Why: reason **Dreg** (§2.1). Note: corrected in revision 5 after e1/final_findings.txt lines 121–122
- Status: **WITHDRAWN as stated (superseded; already corrected in a later revision)**
- Added in this version (completeness check, §6)

**G-07**

```text
It then uses ΔC_R1 ≥ 0, with C_hi rigorous only up to the uncertified ρ: E_C,F1F1 ≥ K/(C_hi + C_J) = 0.28495882 GHz at C_J = 0.
```

- Source: `e1/frozen/E1-PREDECLARATION.rev4.ee69027f42dd8a8c642050216f322de58ee78f550240ecd2bbf2eaa2f552cc0a.md` (sha256 `ee69027f42dd8a8c642050216f322de58ee78f550240ecd2bbf2eaa2f552cc0a`), `line 152`
- Also verbatim in (same claim, same status): `e1/E1-PREDECLARATION.DRAFT.md` (sha256 `ee69027f42dd8a8c642050216f322de58ee78f550240ecd2bbf2eaa2f552cc0a`)
- Type: superseded frozen pre-declaration, revision 4 (Markdown)
- Why: reason **Binc** (§2.1). Note: condition "Only under M1 (or M2), adopted by a separate definition decision" omits the port model; corrected in revision 5 after e1/final_findings.txt line 118
- Status: **WITHDRAWN as stated (superseded; already corrected in a later revision)**
- Added in this version (completeness check, §6)

### 2.9 Withdrawals already made in the session (recorded, not corrected again)

**W-01** (transcript line 34021, timestamp 2026-09-23T09:55:16.082Z, block 0)

```text
**Correction:** my earlier "−3 %/+5 %" tolerance came from a 400-device sample that was too small. The adversarial check refuted it, and I've withdrawn it.
```

**W-02** (transcript line 34286, timestamp 2026-09-23T12:39:17.583Z, block 0)

```text
My earlier "for any k²" claim treated R1 as a floating conductor, and it is withdrawn. So is my "S1 is out of tolerance" statement.
```

**W-03** (`e1/verify/auditor-rev2/E1-PREDECLARATION.DRAFT.6ec25bf9.md` (sha256 `6ec25bf97dbd2b38e5cdf93e5249a1d96300cae46788cf7a95bfe51a8692d36b`), `line 25`)

```text
1. **Withdrawn: "the Thomson bound gives E_C,F1F1 ≤ 0.586 GHz (or ≤ 0.509 GHz) for any k² and any C_J ≥ 0".**
```

**W-04** (`e1/verify/auditor-rev2/E1-PREDECLARATION.DRAFT.6ec25bf9.md` (sha256 `6ec25bf97dbd2b38e5cdf93e5249a1d96300cae46788cf7a95bfe51a8692d36b`), `line 30`)

```text
2. **Withdrawn: "S1 is out of tolerance / far too capacitive" as a suitability statement.**
```


## 3. What remains valid

The items below stand. Each is **exploratory prior knowledge only**: not evidence, not a record, not predeclared, not reproduced, with rounding not bounded (rev6 §3.3 item 3, lines 286–292, and §11). None may be used as, or combined into, a bound on 1/(C⁻¹)_F1F1 or E_C,F1F1 (rev6 §2.5 item 6, line 249).

- **Exploratory static-capacitance numbers as capacitances** (fF, problem-C static capacitance or its island-alone analogues):
  - island-alone and plate analogues: 37.79–38.106 fF;
  - analytic inscribed-disk value: 33.07 fF;
  - the Pólya–Szegő value: 37.32 fF (an unverified literature citation, verify_results.json [0]/bottom_line);
  - the coplanar ring with R1 uncharged: 53.57–53.61 fF;
  - the coplanar ring with the R1 pad charged: 56.33 → 56.64 → 56.88 → 57.00 fF. Whether the ±0.40 mm configuration gave 56.88 fF or 57.00 fF is UNRESOLVED; see the rev6 review MINOR finding.
  - the analytic S1 estimates in `e1/inputs.json` (C_c ≈ 6.9 fF, C_line ≈ 1141 fF), which are ASSUMPTION-level.
  As Thomson/Galerkin values they are candidate lower bounds on C_static (and so on C′) only. They are not bounds on 1/(C⁻¹)_F1F1, and not bounds on E_C in either direction.
- **Static-term arithmetic as arithmetic.** For example, K/57.00 fF = 0.3398 GHz as a value of e²/(2h·57.00 fF). It is not false as arithmetic. It is withdrawn only as an E_C statement (reason Astatic).
- **The frozen Dirichlet bound C_static ≤ C_hi = 67.9755386760 fF.** This is a registered record, outside this correction and unaffected by it. Its transfer to E_C,F1F1 is conditional: rev6 §2.4 row 1.
- **Frozen-model architecture sensitivities as model facts.** For example, the collision notch between −6.644 % and −5.111 % for the design-centre device; +22.09 MHz of root shift per 1 % of E_C; the root-bracket exits at about −11.29 % and +11.37 %; and the ensemble rejection tables in `ensemble_bias.json`, `verify/b777.json` and `verify/big4242.json`, as data. These are properties of the frozen models. They are not requirements, thresholds or tolerances (rev6 line 272).
- **Synthetic counterexamples and identities.** For example, the 2×2 circuit (0.807 GHz against 0.484 GHz); the synthetic QT-S network (M1 53.261 fF below 53.6 fF); and the Schur identity checks on synthetic circuits. These support the withdrawals above. They are not statements about S1.
- **Refutations and withdrawals** already recorded in the review files (for example, verify_results.json [1]/bottom_line on "−3 %/+5 %"), and the notices listed in §2.9.

## 4. Method

Read and grep only. No capacitance computation, no Palace or FEM solve, no read of the S1 mesh, and no change to any repository file or git state. Files written: only those listed below, all under `scratchpad/next/e1/correction/`.

**Scripts and data (sha256 measured after the final run):**

- `scan_claims.py` `cfa51eb716747883d54611c5681ae91588c06a370725ddd4b1f890a953286210`
- `sentences.py` `c6fc353b48f93c8437cbae3380ca0de6e5210ba20c53e811f528a1eb85226f5b`
- `items.py` `bf8a7775a1ae1a9c3b53298d818fca1e702f230c5c64d70010bbe1b23f09276e`
- `verify_items.py` `3c6558ee62b77df390f17a37a05a9e4d5c21d732f25d73a729d45276f4707c89`
- `build_record.py` `fb707fe7a7a5cc10a6c6aa92729e42aca6515c057f95a318ddc06feb39da98fc`
- `scan_hits.json` `d103741646f39838212294b1e82e9bb70e361e1b4d8e2684d918228f16ddaff5`
- `items_verified.json` `1a9ce9a93fac51049910da130d9a28e5afb18bd6287e65906e4872641b2eb623`

**Steps:**

1. **Claim scanner, `scan_claims.py`** (arguments: `35004`). It walks every string leaf of every JSON file, with its JSON path, and every line of every text or code file, matching the claim regex: GHz, MHz, E_C, e²/, toleran, suitab, capacitive, window, "x target", "% vs 0.6", "out of", "far outside", "outside every", premise, rigorous, "CONDITIONAL ON QT", floating, "any k²", unsuitable, "fails the", −3 %, +5 %, ±1 fF.
   Files scanned (under `scratchpad/next/`):
   - `workflow_results.json`, `verify_results.json`, `DRAFT-recommendation.md` and `ensemble_bias.{json,log,py}`;
   - `ec_sensitivity.py`, `e1/verify_results.json`, `e1/verify3_results.json`, `e1/inputs.json`, `e1/refuted.txt` and `e1/rev3_findings.txt`;
   - everything under `agents/`, including `agents/ec_tol/`, and under `verify/`, `e1/verify/` and `e1/verify3/`.

   These sets include every file in the rev6 §11 register. Result: 230 text files scanned, 14 binary files skipped by extension (.pkl, .npy, .npz), 0 unreadable.
   The same scanner walked the assistant text blocks of the session transcript (lines 1–35004) with a narrower chat regex.
2. **Reading aid, `sentences.py`.** It prints the matching sentences per JSON path or line, and was used to read the hits in the principal files. I also read these directly in full or in the relevant part: `DRAFT-recommendation.md`, the `workflow_results.json` summaries and verdicts, the revision-2 draft's matching lines, the script print lines, rev6 §2.3–§2.5, §3.2–§3.3 and §11, and the rev6 prior-knowledge findings.
3. **Chat.** Assistant text blocks only (`type == "assistant"`, content blocks of type `text`). I read the chat messages of 2026-09-23 on this topic in full (transcript lines 33762–34072 and 34286) and checked lines 34073–34947 for GHz and E_C statements. Regex hits dated 2026-09-14 to 2026-09-22, other than line 29191, were triaged by excerpt. All concern solver, numerical or evidence tolerances in unrelated tasks, so none is listed. The transcript was still being appended to during this work. Lines 1–35004 were used, and the sha256 of exactly those bytes is given in each chat item.
4. **Verification, `verify_items.py`.** It re-opens each source and asserts that the excerpt is a verbatim substring of the located JSON string, file line or transcript text block. It also measures each source's sha256. `build_record.py` refuses to render if any check fails.

**Scanned but deliberately not listed as claims:**

- **`e1/verify/numbers/snap/**`, 81 files.** Each is byte-identical to the same path at repository HEAD `3d14c095e7ac4b8971f5476bd9a9f315ba7df2e1`: checked with `git show HEAD:<path> | sha256sum`, 81 matches and 0 differences. They are registered repository material, not exploratory claims; see §5.
- **Third-party source text.** `agents/ec_tol/Full_Edition.txt`, `agents/ec_tol/Master_Final.txt` and `e1/verify/auditor-rev2/master_final.txt` are PDF text extracts of the Master documents. The two empty PDF-text files in `e1/verify/auditor-rev2/` are also in this class.
- **Data and analysis files with no S1 E_C or suitability assertion.** `ensemble_bias.*`, `ec_sensitivity.py`, `agents/ec_tol/*.py|json`, `agents/sens*.py`, `agents/lin_ensemble.py`, `agents/schur_identity.py`, `verify/*.py|json`, and the `e1/verify/numbers` scripts other than `plate3.py`. Their hits are model sensitivities, synthetic identities or code identifiers.
- **Review text that criticises a claim rather than asserts it.** For example, e1/verify3_results.json [0]/findings[0]. It is not listed separately. Where such text states a number itself, it is listed (for example, A-33, A-50 and A-51; the draft of this record named e1/verify_results.json [1]/items[3]/evidence here as not listed, although it states 0.3398 and 0.5085 GHz, and it is now A-50). A review claim whose status is CONFIRMED is asserted by that review and is listed (A-49, B-29, C-62, D-25, D-28).
- **History and review-text files.** `e1/rev3_findings.txt` (the 0.57 % margin arithmetic, disclosed in rev6 §3.3 item 3) and `e1/refuted.txt` (the revision-2 review text) were scanned. Where they repeat a listed excerpt verbatim, the item lists them under "Also verbatim in". Otherwise their matches are review criticism, not assertion.
- **Duplicates.** Where a review file quotes a draft claim verbatim, the original is listed and the quotation is not. verify_results.json [2]/items[4]/claim paraphrases `DRAFT-recommendation.md` line 78 with status REFUTED and is not listed. [2]/items[2]/claim paraphrases line 89 with status CONFIRMED; it is listed as D-28 (the draft of this record said both "quote" their source; neither is verbatim).

**Not scanned by the draft (outside the specified sources; the completeness check in §6.1 scanned all of them):** the frozen revisions 4–6 and the two planning notes (the correction basis, not exploratory claims), `e1/E1-PREDECLARATION.DRAFT.md`, `e1/final_*`, `e1/rev5_*`, `e1/rev6_results.json`, and the `e1/rev5-review/`, `e1/rev6-review/`, `e1/decision/`, `e1/own/`, `e1/regop/`, `e1/foster-shorted-r1/` and `e1/rev5/` directories. `e1/rev6_findings.txt` was read in its prior-knowledge sections only.

**Files that could not be read:** none. The 14 binary files skipped by extension are:

- `e1/verify/sec2-refute/lab.pkl` `2b3812669efbbcf30bb13417649cf13b776c3cad2b2d72b8feea61d3f1aeb17c`
- `e1/verify/sec2-refute/mesh.npy` `f6df0000bed676f0a4b777e2a1d915b6608dab452e11737f82c685cebf0e8ba7`
- `e1/verify/sec2-refute/mesh.pkl` `027daf366796c4b02ce19d7d80bcb6d63d846e99e86b22a8df52188531710d6f`
- `e1/verify/sec2-refute/r1.pkl` `7ed3148f3519752f21ad5ad31e03200d5632069999472618fa1b931315a18a48`
- `e1/verify/sec2-refute/z0.pkl` `7abe6239b5345f6a856cd6fb293cfe5fc854bebe8fb1a4f9e38e4b6932dd2021`
- `e1/verify3/method4/cells_A.pkl` `708a268f4de6a67194009a7b013f8b981079d272627384f1644ad19899a268e1`
- `e1/verify3/method4/cells_Adec.pkl` `219da5780ef7e14c01239aa54696511cf833bdff8560c3d5e355ec380ef017cd`
- `e1/verify3/method4/cells_B.pkl` `fea7724770a3243981488c660d4b069efa5e20ea7a898a7d2c903b6360eaaa13`
- `e1/verify3/method4/geo1.pkl` `0eef31ca4272f0f81dee73d12d74f67898e8d1ee14d98eee80bd23aa0bbd4ea2`
- `e1/verify3/method4/mesh.pkl` `027daf366796c4b02ce19d7d80bcb6d63d846e99e86b22a8df52188531710d6f`
- `e1/verify3/method4/r1.pkl` `b278d1b8decca076431901ef166905d1a45ff21e9264cff2277c19c4c3c6840a`
- `e1/verify3/rev3-auditor/geom.npz` `3bc6f9788cc4eb295b325c9121b01380faf393843f0c4a746380afe1e2bbb2d5`
- `verify/thomson/ground_nodes.npy` `366faee86b7133efd394a7b49aa3a4b01cf824b37b1eb45c09b75bc25887c1fe`
- `verify/thomson/island_nodes.npy` `ef12f27eecdf86cfcf0b113833d4e56b0f3f5d38d9cbd28b5e8be7dc6cbd4d73`

## 5. Out of scope, reported for human decision (not changed here)

- **A registered repository document states the same inequality chain as items B-08 and E-01.** `docs/coupled-candidate/static-anchor-hypothesis.md` (sha256 `c57f1ac4d11d372e0778c545bb851b6f7d6d158acd1648ae8f229a6cb04610ef` at HEAD `3d14c09`) contains:
  - line 126: `e²/(2 C_h)  ≤  e²/(2 C_FF)  ≤  e²(C⁻¹)_FF/2 = E_C,F1F1`;
  - line 131: "The last inequality is the Schur complement.";
  - line 274: "Under assumption A-R, `e²/(2 C_h)` gives a lower bound", continuing on line 275: "on `E_C,F1F1`: `E_C,F1F1/h ≥ 235.6 MHz` from level 1".

  Under rev6 §2.4 row 1 this direction holds only under M1 or M2, after a registered-definition decision, with the upper bound that matches the port model. For a distributed, shorted R1 the Schur step is a reading, not an identity. Correcting a registered record needs a separate correction record and human approval (CLAUDE.md §1, §3). This record changes nothing there; it only reports the contradiction (CLAUDE.md §14).
- **Scripts that print E_C arithmetic but are missing from the rev6 §11 register or from its list of contradicted interpretations.** Not in the register table: `verify/thomson/consts.py` (the rev6 review found this too; items A-36, A-37, A-55, B-21 and C-38) and `agents/schur_identity.py` (C-70). In the register table but not named in the §11 list of contradicted interpretations (lines 1052–1057): `verify/s3/eprime_lite.py` (P2, line 1116; A-40) and `agents/bounds.py` (P1, line 1103; A-34, A-35 and A-54; the rev6 review found bounds.py too). Named in that list only for its E_C print lines: `verify/s3/eprime2.py`, whose line-62 "any k^2" label is D-33. The draft of this record called eprime_lite.py "not in the rev6 §11 register"; that was wrong. Whether to extend the register or the list is for the E1 revision.

## 6. Completeness check (independent audit of the draft)

This section was added on 2026-09-23 by a separate agent. It checked the draft of this record adversarially for omissions and for errors. The draft is kept unchanged: `E1-EXPLORATORY-CLAIMS-CORRECTION.draft.md`, sha256 `dd684a00f04e57f3f4132bc1840ec4f7a1fb9d1913444d70eac2763350d6a04d`. This file is the draft with the fixes below applied and the omitted items added. Every added item carries the line "Added in this version".

### 6.1 Method

Read and grep only. There was no capacitance computation, no Palace or FEM solve, and no read of the S1 mesh. No repository file or git state was changed: HEAD is `3d14c095e7ac4b8971f5476bd9a9f315ba7df2e1` and `git status --short` prints 0 lines. Files were written only in `scratchpad/next/e1/correction/`.

**Scripts, data and reading aids** (sha256 measured when this file was built):

- `audit_verify.py` `f860c9478139b99eaa298e304f3f2fe30ff59490fd47a76c6712a3116cc88ba5`. It parses the draft's own Markdown, not `items.py`, and re-checks each excerpt as a verbatim substring at its locator, with the sha256 of the source. For transcript items it also checks the line, block, timestamp and prefix digest. Output: `audit_verify.json` `7e83bd707c28557df5f641827d59210ca4d0a53bee132da6587e232a79c39c6d`.
- `audit_scan.py` `fd2fec4b5f8cb95bb0afee04e30861a9acccfdf3c9e89af06dc78c41840ccf2e`: the omission scan. Output: `audit_scan.json` `57e1bb45a17190972cfbea97728414a3c1d2608f0a04d7999eb3de07767173ef`.
- `audit_dump.py` `5ce22decf070673b9e844f6e639eb02db525154cb605f072cf72469eab480ed9`: a reading aid that prints uncovered hit sentences. Its outputs `dump_inputs.txt`, `dump_ev.txt`, `dump_chat.txt` and `audit_triage_principal.txt` are working notes, not evidence.
- `audit_build.py` `5b7e2338c2852cb5a9160cea3c9b3e15b81a4868a4be66ca8de948778bd753c1`. It applies the fixes as exact, asserted replacements of draft text. It verifies every added excerpt at its locator and refuses to write on any mismatch; the result was 0 mismatches out of 85 added items. Output: this file, and `audit_added_items.json` `ba13a645924b2e9c10fcd6c9950343c2632e13eba5d728107bb901f4bba53677`.
- `audit_completeness.md` `4eb68073314341046459456fb2c4595d6fe714e8dbd9d5fef65d3770c1201d01`: the template of this section.

**Coverage of `audit_scan.py`.** The draft's `scan_claims.py` scanned a fixed list of 230 text files. `audit_scan.py` walks every file under `scratchpad/next/`, except the `correction/` directory (the record itself and its working files) and `__pycache__`. That is 386 text files. It detects the 29 binary files by UTF-8 decode failure rather than by file extension, and lists them in `audit_scan.json`. It newly covers 156 text files: `e1/cfg/`, `e1/decision/`, `e1/final/`, `e1/final_*`, `e1/foster-shorted-r1/`, `e1/regop/`, `e1/rev5/`, `e1/rev5-review/`, `e1/rev5_*`, `e1/rev6/`, `e1/rev6-review/`, `e1/rev6_*`, `e1/frozen/` and `e1/E1-PREDECLARATION.DRAFT.md`.

**Transcript.** It scans the assistant text blocks of all 35,069 transcript lines present at scan time. The sha256 of those bytes is `c0a4a264f563f17c59268085e6cff4db77dd46f99cee639aec4e9aa4c2cd5d41`. The draft stopped at line 35004. Lines 35005–35069 have no hit.

**Regex.** It matches at sentence level and is wider than the draft's. It adds:
- E_C relations `≤ ≥ < > ∈ =`, `E_hi` and `E_C^DC`;
- any number in GHz or MHz, `K/…`, and "of", "on" or "off target";
- `FAILS`, `DIFFERS`, `DEV_BELOW` and "hard gate";
- "whatever k", "for any C_J", "R1-removed" and "removed readout";
- `0.285`, `0.28496` and `284.96`;
- "premise contradicted" or "premise refuted".

A separate grep looked for phrasings the regex misses: "too big", "too large", "oversized", "resize" and "half its capacitance".

**Triage.** In the principal sources, every hit sentence that the draft does not already quote was read in context: `DRAFT-recommendation.md` (read in full), `workflow_results.json` (every claim), `verify_results.json` (every item's status), `e1/inputs.json`, `e1/verify_results.json`, `e1/verify3_results.json`, the revision-2 and revision-3 drafts, frozen revision 4, the two chat messages at transcript lines 33762 and 34021 (read in full), and every chat hit dated 22–23 September. Every script's print lines were grepped for E_C, GHz, `K/` and target arithmetic. The hits in the other files were triaged by excerpt.

### 6.2 Verification of the draft's items (task item 2)

- **Excerpts.** All 144 excerpts (140 items and 4 withdrawal notices) are verbatim at their stated locators. Every sha256, line number, JSON path, transcript line, block and timestamp, and the transcript prefix digest `d656e9b2…842e6` for lines 1–35004, is correct: 0 failures (`audit_verify.json`).
- **The draft's own method claims hold:**
  - `scan_hits.json` records 230 text files, 14 binary files and 0 unreadable files;
  - all 54 path rows of the rev6 §11 register were scanned;
  - the 81 `snap/` files are byte-identical to HEAD (`git show HEAD:<path> | sha256sum`: 81 matches, 0 differences);
  - no assistant chat text before line 34286 contains "out of tolerance" or "−3 %/+5 %" as an assertion.
- **This file.** Run on this file, `audit_verify.py` re-checks all 225 items and 4 withdrawal notices: 0 failures. Its output, `audit_verify_final.json`, is not digested here, because its content depends on this file.
- **rev6 and review line citations** in §2.1 were checked against the frozen files: rev6 lines 75–81, 106, 153–194, 200, 201, 235–239, 249, 271, 272 and 286–292, and `rev6_findings.txt` lines 1334, 1398, 1437, 1452 and 1488. They are correct except where listed below.

**Errors found in the draft and fixed here (14):**

1. **A-40 note and §5.** The draft said `verify/s3/eprime_lite.py` is "not in the rev6 §11 register". It is in the register table (P2, rev6 line 1116). It is only absent from the §11 list of contradicted interpretations. Both places are corrected.
2. **C-09 note.** The draft said "32.93 fF is the image of an unregistered -2 % window". 32.93 fF is the upper edge of the capacitance window [31.6, 32.9] fF, a ±2 % band on C (`workflow_results.json` [1]/verdict, "C2" paragraph). As an E_C edge it is −1.96 %.
3. **D-11 note.** A cross-reference pointed to §4. It should point to §3, "What remains valid".
4. **B-04.** It states a condition ("under A-R"), so by the draft's own reason list it is Binc, not B. Its status is now "as stated (its condition is incomplete)".
5. **B-10.** Same fix: it is conditioned on A-R and the Schur step.
6. **D-13, D-16 and D-17.** These are relations stated inside the quasi-TEM surrogate. Planning note rev6 §6 (lines 107–110) keeps such relations under M1 as surrogate facts, with an unfinished proof. They are now withdrawn only as statements about the registered operator.
7. **Reason DQT** said that the no-port-loop and no-port-to-line-mutual assumptions are "both … known to be false for the registered model". Only the first is supported (planning note rev6 lines 114–116). rev6 line 190 says the physical plausibility of the mutual inductance "for S1 [is] not assessed". The reason is rewritten.
8. **Reason Dfloat** said "Even in synthetic quasi-TEM models, the M1 value can exceed C_float,body once a port-to-line mutual inductance is present". The QT family excludes that mutual inductance by definition, and rev6 lines 188–190 say the opposite ordering held within QT. The reason also said the arguments "bound no registered quantity". The same capacitances do bound C_static and the floating-R1 capacitance (rev6 line 253). The reason is rewritten.
9. **Reason Astatic** said rev6 "uses no GHz image of a static capacitance anywhere". rev6 line 201 prints "K/C_FF = 0.484 GHz". The reason now cites what §2.5 item 1 actually forbids (lines 233–235).
10. **Reason Cmodel** attributed to rev6 "no inequality or approximate equality". rev6 line 193 says only "no inequality". The paraphrase was presented as the source's words; it is rewritten.
11. **Reason Aprint** cited rev6 §11 P2 for "most of that output was never logged". P2 covers only the P2 scripts. The reason now adds the directory evidence: no log file exists beside any listed script.
12. **§4, review-text rule.** The draft named `e1/verify_results.json` [1]/items[3]/evidence as unlisted criticism, yet by its own rule (A-33) it must be listed, because it states 0.3398 and 0.5085 GHz. It is now A-50.
13. **§4, duplicates rule.** The draft said `verify_results.json` [2]/items[2]/claim and [2]/items[4]/claim "quote" the draft recommendation. Both are paraphrases. [2]/items[2] has status CONFIRMED, so that review asserts it; it is now listed. Review claims whose status is CONFIRMED are now treated as assertions.
14. **§1 counts.** They are updated. The withdrawals section is renumbered from §2.8 to §2.9 to make room for the new group G, and every reference to it is updated.

### 6.3 Omissions found and added (task item 1)

**85 items were added.** By group: A: 13, B: 12, C: 34, D: 14, E: 5, G: 7 (A–E continue the draft's numbering; G is new). IDs: A-43, A-44, A-45, A-46, A-47, A-48, A-49, A-50, A-51, A-52, A-53, A-54, A-55, B-21, B-22, B-23, B-24, B-25, B-26, B-27, B-28, B-29, B-30, B-31, B-32, C-40, C-41, C-42, C-43, C-44, C-45, C-46, C-47, C-48, C-49, C-50, C-51, C-52, C-53, C-54, C-55, C-56, C-57, C-58, C-59, C-60, C-61, C-62, C-63, C-64, C-65, C-66, C-67, C-68, C-69, C-70, C-71, C-72, C-73, D-20, D-21, D-22, D-23, D-24, D-25, D-26, D-27, D-28, D-29, D-30, D-31, D-32, D-33, E-15, E-16, E-17, E-18, E-19, G-01, G-02, G-03, G-04, G-05, G-06, G-07.

- **A: E_C upper bounds.**
  - Statements that the Thomson bound "excludes 0.60 GHz" above an ε_r threshold (`DRAFT-recommendation.md` line 57; `workflow_results.json` [1]/open_questions[3] and [1]/claims[10]; `verify_results.json` [0]/bottom_line and [0]/items[11]).
  - The CODATA number restatement, and a review claim with status CONFIRMED.
  - Two reviewer statements of the static-term GHz image, listed under the draft's own A-33 rule.
  - Two upper bounds or "extra terms" in the form K/C_T + g²/(4f_R). They get the new reason code Ag.
  - Two script print lines: `agents/bounds.py` line 15 and `verify/thomson/consts.py` line 15.
- **B: E_C lower bounds.**
  - `consts.py` line 18, which labels K/67.98 fF as "E_C".
  - Seven `e1/inputs.json` statements, including the unconditioned "so E_C,F1F1 ≥ E_st" and "Under the registered Schur relation".
  - Three `e1/verify_results.json` statements whose condition lacks the port-model requirement.
  - The revision-2 state-N interval "[0.28496, +∞), and the lower end is pre-existing".
- **C: suitability, tolerance and deviation conclusions.**
  - "The readout cannot rescue the seed"; "No for the seed"; "keep-or-resize … the analytic bound already provides"; "fails this before any ground-proximity capacitance is counted"; "given S1 is already off target" (CONFIRMED); "The evidence now supports opening it" (resize).
  - The g-threshold statements "Closing the gap to 0.60 GHz would need g = …", `schur_identity.py` line 31, and the `e1/inputs.json` 57.00 fF threshold, "cap needed is loose", and "What S1 would need" table.
  - Tolerances presented as derived: ±3 %, about 1 %, −5 % one-sided, "tightens to −0.6 to −2 %" and "strongly ASYMMETRIC".
  - The g tolerance "±10–20 %", in three places. No g tolerance is registered either.
  - The review's CONFIRMED "DIFFERS (BELOW) … T1′ … T3 … CONFIRMED" and its replacement text.
  - The revision-2 column "binding side for S1".
- **D: floating-R1, "any k²" and QT claims.**
  - Five further `workflow_results.json` "any k²" or floating-readout sentences.
  - Four `verify_results.json` sentences: two CONFIRMED claims and two Kron-reading endorsements.
  - `e1/inputs.json`: the transfer sentence after D-17, and "1/(C⁻¹)_FF is below the floating-metal value". The second gets the new reason code Dreg.
  - The revision-2 QT template and the ring-admissibility sentence.
  - The `eprime2.py` label "any k^2 (no charge on R1)".
- **E: chat.**
  - Line 29778: "E_C/h ≥ 235.6 MHz".
  - Line 33762: "What stops it being rigorous is a missing lower bound on C".
  - Line 34021: "For the S1 island ("is it on target?"): no."; "that rationale does not hold"; "sizing a replacement island to about 1–2 fF".
- **G (new): superseded revisions 3 and 4.**
  - Unqualified registered-operator claims, "C_Σ,reg < C_static" and "lies below the floating-metal value". They get the new reason codes Breg and Dreg.
  - E_C ≥ K/(C_hi + C_J) statements that omit the port-model condition.
  - The pre-declaration chain has already corrected all of these (revision 5). They are listed for completeness.

### 6.4 Reviewed and deliberately not listed

- **Pure conversion tables or notation:**
  - `workflow_results.json` [0]/claims[15], the table from C to E_C;
  - `e1/verify/numbers/basic.py` line 7, "E_lo=K/Chi";
  - `e1/rev5-review/`, `e1/rev6-review/` and `e1/final_*`, the K/C_hi and K/C′_hi arithmetic.
- **Hypothetical thresholds that are not at an S1 value:**
  - `workflow_results.json` [0]/claims[16], "k² ≤ 1 − 32.28/C_low: 0.022 at 33 fF, …";
  - `e1/inputs.json` [1]/claims[24], the tolerance images;
  - the revision-2 "decision power" thresholds at lines 244–249 (their S1 application is C-39).
- **`workflow_results.json` [1]/claims[3], "a literal reading gives E_C >= 104.7 GHz".** The same claim calls it "a definitional artefact" and says E_C,F1F1 "cannot be compared with 0.60 GHz". It is a conditional statement under the complete-moment reading, not a bound asserted about S1. A human may still choose to list it under reason Binc.
- **"The seed's crude estimate is about 3.8× over-coupled"** (`workflow_results.json` [2]/summary). It is a g-seed statement, not a conclusion derived from a capacitance or E_C.
- **Model facts:**
  - the notch edges, the bracket exits, the sensitivities and the ensemble tables;
  - the T1–T4 derivations in `e1/decision/`, in both planning notes, and in the rev4–rev6 §3.3 texts. rev6 §3.2 keeps these candidates for later use, with none adopted.
- **Frozen revisions 5 and 6 and both planning notes.** These are consistent with rev6 §2.4. For example, planning note rev6 line 31 carries the M1-or-M2, definition-decision and port-model conditions (lines 29–33).
- **Later review files:**
  - `e1/rev5_*`, `e1/rev6_*` and `e1/final_*`;
  - `e1/rev3_findings.txt` and `e1/refuted.txt`, which are text renderings of `e1/verify3_results.json` and `e1/verify_results.json`.

  They quote claims in order to criticise them. Where a rendering repeats an added excerpt, the item lists it under "Also verbatim in".
- **Synthetic-only scripts and logs:**
  - `e1/final/`, `e1/foster-shorted-r1/`, `e1/regop/` and `e1/verify/sec2-refute/`;
  - `verify/s3/k2.py` and `marini.py`, and `verify/thomson/synth_*.py`;
  - `e1/decision/sign_check.py` and `agents/schur_identity.py` lines 23–28.

  Their E_C values belong to synthetic circuits or unit geometries.
- **Transcript hits dated 14–22 September**, other than lines 29191 and 29778. They concern solver frequencies, moments and numerical-check tolerances.
- **Transcript hits dated 23 September after line 34021.** They are:
  - withdrawals, already listed in §2.9;
  - review summaries;
  - explicitly conditional statements, for example line 34481: "Under that reading the island-only desk analogue (~37.85 fF) would imply 'E_C < 0.60 GHz'".

### 6.5 Residual uncertainty

- **Recall.** It is bounded by the regex and by human triage. A claim worded with none of the matched tokens could still be missed; the extra phrasing grep reduces this but does not remove it.
- **Borderline classifications, for human decision:**
  - the g-tolerance items;
  - review claims with status CONFIRMED, which are treated here as assertions;
  - `agents/bounds.py` line 15, a static-term print next to E_C prints;
  - the revision-2 column "binding side for S1";
  - group G, where the chain of revisions has already corrected the text.
- **Moving sources.** The transcript and `e1/cfg/`, which the configuration re-freeze task is still writing, keep changing. Coverage is fixed at 35,069 transcript lines and at the files present at scan time. `e1/cfg/` had no claim hits in its output files (`frontier*.json`, `proxy_results*.jsonl`).
- **Subagent transcripts** under `/root/.claude/projects/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988/subagents/` were not scanned. Their reports are the JSON files scanned here, and the task named the main transcript's assistant messages.
- **Rendering copies only.** "Also verbatim in" lists rendering copies only: `e1/refuted.txt`, `e1/rev3_findings.txt` and `e1/E1-PREDECLARATION.DRAFT.md`. It does not list later reviews that quote the excerpts.
- **The 56.88 fF or 57.00 fF ambiguity** of the ±0.40 mm configuration stays UNRESOLVED, as in the draft.
