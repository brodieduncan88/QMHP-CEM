# Correction record: the E1 Confirmation formed S1's internal sets E1.1 and E1.1-half

**Status: CORRECTION RECORD** (CLAUDE.md §1 and §14; human decision D14 of 2026-09-24).

- **What this record changes.** It rewrites no historical record. The commit `90bf9eb355928b6d2e1df16bd133fa70ba9c4f23` and its message stay as they are. So do its committed evidence files and the uncommitted scratch and `/tmp` files listed in §3.
- **Values not read.** The values of those uncommitted files were not read for this record. Only their names and timestamps were.
- **No new computation.** No computation was run for this record.
- **Status of the computation (D14).** The computation described below is acknowledged as an **unintended pre-execution computation, not approved behaviour**.

## 1. The statements corrected (verbatim, preserved)

- **S-1.** The message of commit `90bf9eb` says:
  - "No S1 matrix was assembled or factorised and no S1 energy or capacitance was computed; the one attempt is unspent; no approval exists."
  - "Evidence from this code (S1 geometry and synthetic sets only)".
- **S-2.** `docs/coupled-candidate/e1-s1-lower-bound.md` at `90bf9eb`, status paragraph: "No S1 capacitance has been computed by E1: no S1 Galerkin matrix has been assembled or factorised, and no S1 energy has been formed."
- **S-3.** The same file, evidence section:
  - the heading "Pre-approval evidence (S1 geometry and synthetic sets only)";
  - "No approval, no ledger entry and no S1 capacitance were involved."
- **S-4.** `docs/coupled-candidate/README.md` at `90bf9eb`, the E1 row: "No S1 capacitance has been computed."
- **S-5.** Session reports made while E1 was being implemented and reviewed. They described the Confirmation and its evidence as involving no S1 capacitance, energy or matrix.
- **S-6.** Contract revision 8.2, §6 (sha256 `24ffff7d…504c`). It describes the prototype's stand-in as "the selected island (n = 32, q = 3.5) at (−0.6, 0) mm", but does not state the consequence given in §2.

## 2. What is wrong

- **The stand-in's island was S1's island.** The Confirmation stand-in placed "the selected island (n = 32, q = 3.5) at (−0.6, 0) mm", built from the contract's §3.1 node formula. The same is true of the revision-8 prototype's `standin.py` and of `e1_standin.py` at `90bf9eb`.
- **So two stand-in sets were S1 attempt sets.** The stand-in's first 1,024 panels and its 16 × 16 nested grid were bit-identical to two S1 attempt sets: the internal set E1.1 (island panels only) and the internal set E1.1-half.
  - This was verified on the frozen snapshot of `90bf9eb`: `R[:1024] == island_panels()`, and the nested grid equals `island_panels(step=2)`.
- **What the capacitance phase computed for E1.1 and E1.1-half:**
  - it assembled their float64 matrices;
  - it factorised them in place (Cholesky);
  - it formed σᵀS₆₄σ and the long-double sums Ê, Ŵ and Ĝ;
  - it formed E_up and the enclosures C_lo and C̃;
  - it evaluated check (g) on them, and K4 inequality 1 between them.

  These are S1's internal E1.1 and E1.1-half quantities. They are island-only, internal-only (D2, D10), and not results.
- **What was not computed.** E1.2 and E1.2-excl-R1 on S1 geometry were never assembled, factorised or used in any energy. No S1 ground panel, and no panel derived from the S1 mesh, entered any numerics.
- **So statements S-1 to S-5 are wrong** as far as they concern S1 matrices and energies.

## 3. The runs that formed them

| run | time (UTC) | code | where the E1.1 / E1.1-half quantities are |
|---|---|---|---|
| revision-8 prototype `run8.py`: runs `run8_small`, `run8_full`, `run8_force5`, `run8_release` | 2026-09-23, 23:32–23:47 (file times) | session prototype (not the E1 implementation) | session scratch `next/e1/rev8/cost/run8_*.json`, covered by the manifest `c781b6ef…` pinned in contract §9. The revision-8 configuration review also re-measured this prototype; the number of those runs is not recorded here. |
| smoke nominal Confirmation | 2026-09-24 02:57–03:02 | pre-freeze implementation | `/tmp/qmhp-e1-confirmation-b7cbxuw0`: sigma and pass files only. The run's output JSON in session scratch holds dimensionless per-set diagnostics. |
| committed nominal Confirmation | 03:22–03:27 | `90bf9eb` | `/tmp/qmhp-e1-confirmation-akx65x9c`; `experiments/e1-s1-lower-bound/confirmation-nominal.json` |
| committed forced-fallback Confirmation | 03:27–03:32 | `90bf9eb` | `/tmp/qmhp-e1-confirmation-xfdweylp`; `experiments/e1-s1-lower-bound/confirmation-forced.json` |
| in-suite re-run, nominal (opt-in test) | 03:44–03:49 | `90bf9eb` worktree | `/tmp/qmhp-e1-confirmation-v_3j__tc` |
| in-suite re-run, forced (opt-in test) | 03:49–03:55 | `90bf9eb` worktree | `/tmp/qmhp-e1-confirmation-59ubr8uc` |

**Not affected:**
- **The run stopped at 03:16.** It wrote only `controls.json`, in `/tmp/qmhp-e1-confirmation-g_ee43ay`.
- **The rehearsal.** It runs the synthetic controls and the S1 geometry phase, which assembles no matrix.
- **The proxy-A g_E run.** It solves only its full 4,080-panel synthetic set. That set contains a translated copy of the selected island, as the frozen selection rule defines proxy A, but no island-only solve is made.
- **The test suite and CI.** They use only synthetic sets.

**What each `/tmp` directory holds:**
- `sigma-E1.1*.json`: σ, Q and σᵀS₆₄σ.
- `pass-E1.1*.json`: Ê, Ŵ and Ĝ as exact fractions.
- `internal-sets.json`: C_lo, C̃ and w. Every directory except `b7cbxuw0` has it.
- These files were not read, are preserved unchanged, and are not committed.

**What the committed `confirmation-*.json` hold for E1.1 and E1.1-half:**
- dimensionless diagnostics only: path, m, width_rel, check_g_rel and g_E;
- the K4 statuses;
- no capacitance value.

The same dimensionless diagnostics were shown in session reports.

## 4. Status of the computed quantities

**Unintended pre-execution computation, not approved behaviour (D14).** The quantities are not an E1 result. No value may be used as, or combined into, any result, bound or decision. Under D2 and D10 they would be internal in any case.

## 5. Corrected statements

- **For S-1, S-2, S-4 and S-5:** E1 has not been executed. No matrix of E1.2 or E1.2-excl-R1 has been assembled on S1 geometry, and no S1 ground panel has entered any numerics. However, the Confirmation runs in §3, and the revision-8 prototype, assembled, factorised and formed energies and internal lower bounds for S1's island-only internal sets E1.1 and E1.1-half, because the stand-in's island was S1's island.
- **For S-3:** the evidence covers the S1 geometry phase and synthetic sets, and also S1's island-only internal sets reached through the stand-in (§3).
- **For S-6:** contract revision 8.3 states the consequence (§6) and forbids it (§3.2 item 2).

## 6. Corrective action

- **Contract revision 8.3** (`experiments/e1-s1-lower-bound/E1-CONTRACT.rev8.3.md`) changes only the stand-in wording and records D14:
  - **§3.2 item 2, the separation rule.** No numeric set of a pre-approval run may coincide with an S1 attempt set (E1.2, E1.2-excl-R1, E1.1 or E1.1-half), byte for byte or up to translation, axis reflection, exchange of x and y, and uniform scaling.
  - **§6, the frozen stand-in's island.** Half-width 0.075 mm in x and 0.0625 mm in y, so it is not similar to the S1 island.
- **The frozen code enforces the rule.** It checks the stand-in's four numeric sets against the S1 geometry phase's sets before any stand-in matrix is assembled, and computes nothing if they coincide. The rehearsal checks every control set in the same way.
- **The tests prove it.** They cover byte identity and similarity against all four S1 sets, and include the revision-8.2 stand-in as the positive control.
- **The 90bf9eb evidence is superseded but kept.** The pre-approval evidence committed at `90bf9eb` stays byte-unchanged. It is regenerated only after the corrected separation has passed review.
- **History is kept.** The commit message of `90bf9eb` is not rewritten; this record supersedes its statements.
