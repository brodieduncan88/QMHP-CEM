# Correction record: what the E1 pre-approval runs computed on S1 panels

**Status: CORRECTION RECORD** (CLAUDE.md §1 and §14; human decisions D14, D15 and D16 of 2026-09-24).

**Revised in the revision-8.4 round (D15).** The first version of this record was committed at `22c9585`. The focused review of that commit found that it understated what was computed, and that it held some smaller errors. Those errors are corrected below. Each wrong sentence of the first version is kept verbatim in §8.

**Revised again in the revision-8.5 round (D16).** The second version (committed at `28f6ca3`) stated the prototype's full-size ground overlap for all its runs (review finding T1). It also said the test suite used only small synthetic sets (T2). Both are corrected below, and each wrong sentence of the second version is kept verbatim in §8.

- **What this record changes.** It rewrites no historical record. These stay as they are:
  - the commits `90bf9eb`, `22c9585` and `28f6ca3` and their messages;
  - their committed evidence files;
  - contract revisions 8.2, 8.3 and 8.4;
  - the uncommitted scratch and `/tmp` files listed in §3.
- **Values not read.** The values of those uncommitted files were not read for this record. Only their names and timestamps were.
- **No S1 numerics.** No S1 numerics were run for this record. The revision-8.4 round ran only:
  - geometry-only comparisons: the S1 geometry phase, which assembles no matrix;
  - synthetic tests.

  The panel counts in §2 come from those comparisons.
- **Status of the computation (D14).** The computation described below is acknowledged as an **unintended pre-execution computation, not approved behaviour**.

## 1. The statements corrected (verbatim, preserved)

- **S-1.** The message of commit `90bf9eb` says:
  - "No S1 matrix was assembled or factorised and no S1 energy or capacitance was computed; the one attempt is unspent; no approval exists."
  - "Evidence from this code (S1 geometry and synthetic sets only)".
- **S-2.** `docs/coupled-candidate/e1-s1-lower-bound.md` at `90bf9eb`, status paragraph: "No S1 capacitance has been computed by E1: no S1 Galerkin matrix has been assembled or factorised, and no S1 energy has been formed."
- **S-3.** The same file, evidence section:
  - the heading "Pre-approval evidence (S1 geometry and synthetic sets only)";
  - "No approval, no ledger entry and no S1 capacitance were involved.";
  - "The Confirmations ran on the SYNTHETIC stand-in of contract §6".
- **S-4.** `docs/coupled-candidate/README.md` at `90bf9eb`, the E1 row: "No S1 capacitance has been computed."
- **S-5.** Session reports made while E1 was being implemented and reviewed. They described the Confirmation and its evidence as involving no S1 capacitance, energy or matrix.
- **S-6.** Contract revision 8.2, §6 (sha256 `24ffff7d…504c`). It describes the prototype's stand-in as "the selected island (n = 32, q = 3.5) at (−0.6, 0) mm", but does not state the consequence given in §2.
- **S-7.** The committed evidence of `90bf9eb`:
  - `confirmation-nominal.json` and `confirmation-forced.json` each record `"s1_capacitance_computed": false`;
  - the docstring of `e1_standin.py` says "NOT S1: nothing here reads the S1 mesh".
- **S-8.** The message of commit `22c9585` says:
  - "No E1.2 or E1.2-excl-R1 matrix was ever assembled on S1 geometry and no S1 ground panel entered any numerics.";
  - "the rehearsal and proxy A check their sets likewise";
  - "C-3: the failure path writes missing provenance (or keeps it in the ledger note)."
- **S-9.** `docs/coupled-candidate/e1-s1-lower-bound.md` at `22c9585`:
  - "No matrix of E1.2 or E1.2-excl-R1 has been assembled on S1 geometry, and no S1 ground panel has entered any numerics.";
  - "However, the Confirmation runs of the implementation reviewed at `90bf9eb`, and the revision-8 prototype, did assemble, factorise and form energies";
  - "An accepted approval therefore cannot spend the attempt and then lose its provenance.";
  - "If `provenance.json` is still missing after spending, the failure path writes it from memory, or keeps it in the ledger note.";
  - "They include a non-finite, zero or negative Ê, Ŵ, Ĝ or σᵀS₆₄σ";
  - "compares every numeric set of the Confirmation, the rehearsal and proxy A with the four S1 attempt sets";
  - "Only the full set is solved."
- **S-10.** `docs/coupled-candidate/README.md` at `22c9585`, the E1 row: "no E1.2 or E1.2-excl-R1 matrix has been assembled on S1 and no S1 ground panel has entered any numerics".
- **S-11.** Contract revision 8.3 (sha256 `2b9b9357…6b296`):
  - §3.2 lead: "No exploratory S1 capacitance value, and no capacitance computed on S1 geometry, enters it.";
  - §3.2 item 5: "Tightness order on generic synthetic proxies (not S1).";
  - §3.2 item 7: "(synthetic data only, and exact S1 geometry counts; no S1 capacitance value at any step)";
  - §4.3: "COMPUTED-DESK (prototype, synthetic stand-in): the product bound is 2.1e-49.";
  - §5 K4: "COMPUTED-DESK (prototype, forced fallbacks, synthetic)";
  - §6: "`**Measured with the corrected prototype** (COMPUTED-DESK, synthetic).`" and "It ran on a synthetic stand-in of N = 9,995";
  - §9: "(revision 7; 40 files; S1 geometry counts and synthetic proxies only)" and "(prototype, stand-ins, proxy-A g_E, K2 check, c₀ derivation; synthetic, and S1 geometry only)".
- **S-12.** The first and second versions of this record: the sentences listed in §8.
- **S-13.** At `28f6ca3`:
  - `docs/coupled-candidate/e1-s1-lower-bound.md`: "Their stand-in's E1.2 also held 534 ground panels bit-identical to S1 E1.2 ground panels (476 of them in S1's E1.2-excl-R1).";
  - the E1 row of `docs/coupled-candidate/README.md`: "their stand-in's E1.2 also held 534 panels bit-identical to S1 ground panels";
  - contract revision 8.4, §6: "So the E1.2 of the prototype and of the `90bf9eb` Confirmations contained S1's island and these 534 panels."

  Each also covered the prototype's reduced run, which is wrong (§2).

## 2. What is wrong

- **The stand-in's island was S1's island.** The Confirmation stand-in placed "the selected island (n = 32, q = 3.5) at (−0.6, 0) mm", built from the contract's §3.1 node formula. The same is true of the revision-8 prototype's `standin.py` and of `e1_standin.py` at `90bf9eb`.
- **So two stand-in sets were S1 attempt sets.** The stand-in's first 1,024 panels and its 16 × 16 nested grid were bit-identical to two S1 attempt sets: the internal set E1.1 (island panels only) and the internal set E1.1-half.
  - This was verified on the frozen snapshot of `90bf9eb`: `R[:1024] == island_panels()`, and the nested grid equals `island_panels(step=2)`.
- **What the capacitance phase computed for E1.1 and E1.1-half:**
  - it assembled their float64 matrices;
  - it factorised them in place (Cholesky);
  - it formed σᵀS₆₄σ and the long-double sums Ê, Ŵ and Ĝ;
  - it formed E_up and the enclosures C_lo and C̃;
  - it evaluated check (g) on them, and K4 inequality 1 between them;
  - the nominal runs also evaluated K4 inequality 2, which compares C_lo(E1.1) (here S1's E1.1) with the stand-in's E1.2-excl-R1, and recorded PASS. The forced runs recorded it `NOT_EVALUATED_LAST_RESORT`.

  These are S1's internal E1.1 and E1.1-half quantities. They are island-only, internal-only (D2, D10), and not results.
- **The stand-in's ground shares panels with S1's E1.2.** The ground was drawn from a synthetic slotted sheet, not from the S1 mesh. But the sheet used S1's lattice, window and merge rules. As a result, 534 of the stand-in's 8,971 ground panels are bit-identical to S1 E1.2 ground panels, 476 of them in S1's E1.2-excl-R1 (geometry-only comparison).
  - The ground of the prototype's full-size stand-in is byte-identical to the implementation's, so the same holds for the prototype's full-size runs.
  - So the E1.2 of every Confirmation in §3, and of the prototype's full-size runs (N = 9,995), held S1's island plus these 534 panels. Its matrix therefore contained a 1,558-row principal block whose entries are S1's E1.2 entries for the same panels, up to the argument order of the entry routine. This is reasoning only; no entry was computed for this record.
  - **The prototype's reduced run is different (D16).** `run8_small` used a 500-panel draw of the same sheet: N = 1,524, with N_x = 1,324.
    - Its E1.2 held S1's island plus 32 panels bit-identical to S1 E1.2 ground panels, so its matrix contained a 1,056-row block of S1's E1.2 entries (reasoning only).
    - Its N follows from its rounding count (m = 532) and the prototype's `--small` path, `standin(500, 200)`. The 32 comes from a geometry-only comparison.
- **What was not computed.** No set equal to S1's E1.2 or E1.2-excl-R1, and no set containing an image of either, was assembled, factorised or used in any energy.
- **Proxy A contains S1's E1.1, translated.** Proxy A's first 1,024 panels are S1's E1.1 translated by +0.6 mm in x, up to the rounding of the translation. A further 162 of its panels are bit-identical to S1 E1.2 panels. The same island is in proxies B and C of every configuration with n = 32 and q = 3.5.
  - Every Cholesky factorisation of such a proxy computes the factor of that translated E1.1's matrix as its leading block. No σ, energy or bound was formed on that block alone.
  - This holds for:
    - the proxy-A g_E run of `90bf9eb`, which wrote `proxyA-gE.json`;
    - the proxy-A g_E re-evaluation of the revision-8 review (manifest `c781b6ef…`);
    - the selection study's proxy runs for those configurations (manifest `e1b85e0c…`).
- **So statements S-1 to S-13 are wrong** as far as they concern S1 matrices, energies and panels. The provenance statements among them ("nothing here reads the S1 mesh") are true, but the value statements are not.

## 3. The runs that formed them

| run | time (UTC) | code | what it formed from S1 panels | where the quantities are |
|---|---|---|---|---|
| revision-8 prototype `run8.py`, full-size runs `run8_full`, `run8_force5`, `run8_release` (N = 9,995) | 2026-09-23, 23:37–23:47 (file times) | session prototype (not the E1 implementation) | E1.1 and E1.1-half quantities; an E1.2 with S1's island and 534 S1 ground panels | session scratch `next/e1/rev8/cost/run8_{full,force5,release}.json`, covered by the manifest `c781b6ef…` pinned in contract §9 |
| revision-8 prototype `run8.py`, reduced run `run8_small` (N = 1,524) | 2026-09-23, 23:32 (file time) | session prototype | E1.1 and E1.1-half quantities; an E1.2 with S1's island and 32 S1 ground panels | session scratch `next/e1/rev8/cost/run8_small.json`, covered by the manifest `c781b6ef…` |
| the revision-8 configuration review's re-measurements of the prototype: `rr_release`, `rr_full`, `rr_force5` (N = 9,995) | 2026-09-24, 00:49–01:12 (file times) | session prototype (review copy) | the same as the full-size runs | session scratch `next/e1/rev8-review/configuration/cost_copy/rr_*.json` |
| smoke nominal Confirmation | 2026-09-24 02:57–03:02 | pre-freeze implementation (not `90bf9eb`) | the same | `/tmp/qmhp-e1-confirmation-b7cbxuw0`: sigma and pass files only. The run's output JSON in session scratch holds dimensionless per-set diagnostics. |
| committed nominal Confirmation | 03:22–03:27 | `90bf9eb` | the same | `/tmp/qmhp-e1-confirmation-akx65x9c`; `experiments/e1-s1-lower-bound/confirmation-nominal.json` |
| committed forced-fallback Confirmation | 03:27–03:32 | `90bf9eb` | the same | `/tmp/qmhp-e1-confirmation-xfdweylp`; `experiments/e1-s1-lower-bound/confirmation-forced.json` |
| in-suite re-run, nominal (opt-in test) | 03:44–03:49 | `90bf9eb` worktree | the same | `/tmp/qmhp-e1-confirmation-v_3j__tc` |
| in-suite re-run, forced (opt-in test) | 03:49–03:55 | `90bf9eb` worktree | the same | `/tmp/qmhp-e1-confirmation-59ubr8uc` |
| proxy-A g_E | 03:22 | `90bf9eb` | the Cholesky factor of E1.1 translated, as the leading block of proxy A's | `experiments/e1-s1-lower-bound/proxyA-gE.json`: g_E, the path and the pivot ratio of the full proxy set |
| selection-study proxy runs, and the revision-8 g_E re-evaluation | before revision 8 (session file times, not restated here) | session scripts | the same, for every n = 32, q = 3.5 configuration on proxies A, B and C | session scratch, covered by the manifests `e1b85e0c…` and `c781b6ef…` (contract §9) |

**Not affected:**
- **The run stopped at 03:17 (file time 03:17:07).** It wrote only `controls.json`, in `/tmp/qmhp-e1-confirmation-g_ee43ay`.
- **The rehearsal.** It runs the synthetic controls and the S1 geometry phase, which assembles no matrix.
- **The default test selection and CI.** They use only small synthetic sets, apart from the S1 geometry phase, which assembles no matrix.
  - The two opt-in Confirmation tests (`test_the_confirmation_re_runs_within_the_limits`, nominal and forced, run only with `E1_RUN_CONFIRMATION=1`) are part of the test suite, but are skipped by default and in CI.
  - When they were run, at `90bf9eb`, they did form S1's E1.1 and E1.1-half quantities: they are the two in-suite rows of the table above (D16).

**What each `/tmp` directory holds:**
- `sigma-E1.1*.json`: σ, Q and σᵀS₆₄σ.
- `pass-E1.1*.json`: Ê, Ŵ and Ĝ as exact fractions.
- `internal-sets.json`: C_lo, C̃ and w. It is in `akx65x9c`, `xfdweylp`, `v_3j__tc` and `59ubr8uc`. It is not in `b7cbxuw0` or `g_ee43ay`.
- These files were not read, are preserved unchanged, and are not committed.

**What the committed `confirmation-*.json` hold for E1.1 and E1.1-half:**
- dimensionless diagnostics only: path, m, width_rel, check_g_rel and g_E;
- the K4 statuses;
- no capacitance value.

The same dimensionless diagnostics were shown in session reports.

## 4. Status of the computed quantities

**Unintended pre-execution computation, not approved behaviour (D14).** The quantities are not an E1 result. No value may be used as, or combined into, any result, bound or decision. Under D2 and D10 they would be internal in any case.

**Proxy A (D15).** Proxy A is historical configuration-selection evidence only. It is not execution evidence and not an S1 capacitance result, and it is not re-run.

## 5. Corrected statements

- **For S-1, S-2, S-4, S-5 and S-8 to S-10:**
  - E1 has not been executed.
  - No set equal to S1's E1.2 or E1.2-excl-R1, and no set containing an image of either, has been assembled, factorised or used in any energy.
  - However:
    - the Confirmation runs in §3 and the revision-8 prototype assembled, factorised and formed energies and internal lower bounds for S1's island-only internal sets E1.1 and E1.1-half, because the stand-in's island was S1's island;
    - the E1.2 of the Confirmations and of the prototype's full-size runs also contained 534 panels bit-identical to S1 E1.2 ground panels, and that of its reduced run `run8_small` 32;
    - proxy A (and, in the selection study, proxies B and C) of the selected configuration contain S1's E1.1 translated, and their Cholesky factors contain its factor.
- **For S-3 and S-7:** the evidence covers:
  - the S1 geometry phase;
  - synthetic sets, as contract revisions 8.4 and 8.5 define "synthetic" (generated without reading the S1 mesh, not disjoint from S1);
  - S1's island-only internal sets, reached through the stand-in (§2).

  The committed evidence stays byte-unchanged. Its `"s1_capacitance_computed": false` is wrong for E1.1 and E1.1-half, and the corrected code no longer writes that field.
- **For S-6:** contract revision 8.3 states the consequence (§6), and revision 8.4 states it for the ground and proxy A as well.
- **For S-8 and S-9, the provenance and separation statements:**
  - At `22c9585`, if `provenance.json` could not be written after spending, the provenance was kept nowhere (review finding L1-1).
  - At `22c9585`, the rehearsal checked the control sets only after running the controls, and the Confirmation did not check them (L5-3).
  - At `22c9585`, proxy A's check could never fire (L4-F1).
  - At `22c9585`, a zero Ŵ or Ĝ is accepted, as the contract allows. It is not an abnormality.

  Each is corrected in the revision-8.4 code and documentation (§6).
- **For S-13:** the statements are corrected on the E1 page, in the README row and in contract revision 8.5, §6. The prototype's full-size runs held the 534 panels; its reduced run `run8_small` held 32 (§2).
- **For S-11:** contract revision 8.4 corrects each of these statements: the §3.2 lead (the meaning of "synthetic"), items 5 and 7, §4.3, §5 K4, §6 and §9.

## 6. Corrective action

- **Contract revision 8.3** (`experiments/e1-s1-lower-bound/E1-CONTRACT.rev8.3.md`, kept byte-unchanged) introduced the first separation rule and the new stand-in island. It recorded D14.
- **Contract revision 8.4** (`experiments/e1-s1-lower-bound/E1-CONTRACT.rev8.4.md`) records D15.
  - **The separation rule (§3.2 item 2).** No pre-approval numeric set may contain an image of an S1 attempt set, as the whole set or as an embedded subset. An image is taken under the symmetries of the square, uniform scaling and translation, with the panels in any order and their bounds in either order.
    - Individual coincident panels, and a coincident proper subset, are permitted.
    - The tolerance is stated (2⁻²²·M). A near-copy beyond it is outside the rule, and no claim is made about it.
  - **The check runs before any numerics on the set concerned.** It applies both to the control sets and to the stand-in.
  - **Proxy A is kept as historical selection evidence** and is not re-run.
  - **The statements in S-11 are corrected.**
- **The frozen code enforces the rule.**
  - The Confirmation and the rehearsal check every control set against S1's E1.1 and E1.1-half before any control runs.
  - The Confirmation checks the stand-in's four sets against the S1 geometry phase's four sets before any stand-in matrix.
  - A coincidence, or a missing check, computes nothing further.
  - The proxy-A mode refuses, computing nothing.
- **The tests prove it.** They cover:
  - whole-set and embedded images under every symmetry, scaling, translation, permutation and reversed bounds;
  - negative controls: individual panels, proper subsets, non-symmetry maps and near-copies beyond the tolerance;
  - the ordering of the checks;
  - proxy A, and the revision-8.2 stand-in, as positive controls on the real S1 sets (geometry only).
- **The 90bf9eb evidence is superseded but kept.** The pre-approval evidence committed at `90bf9eb` stays byte-unchanged. It is regenerated only on a human instruction, after the revision-8.4 separation has passed review. Proxy A's evidence is not regenerated.
- **History is kept.** The commit messages of `90bf9eb` and `22c9585` are not rewritten; this record supersedes their statements.

## 7. What is not established

- Any S1 E1.2 or E1.2-excl-R1 quantity: E1 has not been executed.
- Any use of the E1.1 and E1.1-half quantities of §3. They are not results (D14).
- That the separation rule excludes approximate reproductions. It prohibits images within its stated tolerance, and D15 makes no claim about near-copies beyond it.

## 8. Revision history: the earlier versions' errors (verbatim, preserved)

The first version of this record (committed at `22c9585`) said the following. Each sentence is corrected in the sections given.

| first version (verbatim) | why it is wrong | corrected in |
|---|---|---|
| "No S1 ground panel, and no panel derived from the S1 mesh, entered any numerics." | 534 stand-in ground panels are bit-identical to S1 E1.2 ground panels. The second clause (provenance) is true; the first (value) is not | §2 |
| "it evaluated check (g) on them, and K4 inequality 1 between them." | the nominal runs also evaluated K4 inequality 2 on S1's E1.1 | §2 |
| "**For S-1, S-2, S-4 and S-5:** E1 has not been executed. No matrix of E1.2 or E1.2-excl-R1 has been assembled on S1 geometry, and no S1 ground panel has entered any numerics." | the same as the first row | §5 |
| "The run stopped at 03:16." | its only file was written at 03:17:07 | §3 |
| "`internal-sets.json`: C_lo, C̃ and w. Every directory except `b7cbxuw0` has it." | `g_ee43ay` does not have it either | §3 |
| "**The proxy-A g_E run.** It solves only its full 4,080-panel synthetic set. That set contains a translated copy of the selected island, as the frozen selection rule defines proxy A, but no island-only solve is made." (listed under "Not affected") | its Cholesky factor contains the factor of the translated E1.1 as its leading block | §2, §3 |
| "The rehearsal checks every control set in the same way." | at `22c9585` the rehearsal checked the control sets after running the controls | §5, §6 |
| "The tests prove it. They cover byte identity and similarity against all four S1 sets, and include the revision-8.2 stand-in as the positive control." | at `22c9585` they did not cover embedded images, reversed bounds or the point reflection | §6 |

The second version (committed at `28f6ca3`) said the following (review of `28f6ca3`, findings T1 and T2; D16).

| second version (verbatim) | why it is wrong | corrected in |
|---|---|---|
| "revision-8 prototype `run8.py`: runs `run8_small`, `run8_full`, `run8_force5`, `run8_release`", with "an E1.2 with S1's island and 534 S1 ground panels" (§3 table) | `run8_small`'s E1.2 had N = 1,524 and 32 coinciding ground panels, not 534 | §2, §3 |
| "The prototype's ground is byte-identical to the implementation's, so the same holds for the prototype." | true only of the prototype's full-size runs | §2 |
| "So the E1.2 of every Confirmation in §3 and of the prototype held S1's island plus these 534 panels." | the same as the first row | §2 |
| "their E1.2 also contained 534 panels bit-identical to S1 E1.2 ground panels;" | the same as the first row | §5 |
| "**The test suite and CI.** They use only small synthetic sets, apart from the S1 geometry phase, which assembles no matrix." (listed under "Not affected") | the two opt-in Confirmation tests are part of the suite, and when run they formed S1's E1.1 and E1.1-half quantities | §3 |
