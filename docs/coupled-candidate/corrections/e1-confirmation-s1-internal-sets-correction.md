# Correction record: what the E1 pre-approval runs computed on S1 panels

**Status: CORRECTION RECORD** (CLAUDE.md §1 and §14; human decisions D14, D15 and D16 of 2026-09-24).

**Revised in the revision-8.4 round (D15).** The first version of this record was committed at `22c9585`. The focused review of that commit found that it understated what was computed, and that it held some smaller errors. Those errors are corrected below. Each wrong sentence of the first version is kept verbatim in §8.

**Revised again in the revision-8.5 round (D16).** The second version (committed at `28f6ca3`) stated the prototype's full-size ground overlap for all its runs (review finding T1). It also said the test suite used only small synthetic sets (T2). Both are corrected below, and each wrong sentence of the second version is kept verbatim in §8.

**Corrected in the cleanup after the review of `2f752cd`.** The third version (committed at `2f752cd`) said that only the names and timestamps of the uncommitted files were read, although §2 cites `run8_small`'s rounding count (review finding REC-1). The statement of what was read is corrected below, and the wrong sentence is kept verbatim in §8.

**Corrected again in the final cleanup after the review of `e87373f`.** The fourth version (committed at `e87373f`) said that m = 532 "gives" N = 1,524. Its statement of what was read was also incomplete, and broader than the evidence. It stated session-record facts as if they were verified. Each is corrected below, and the wrong sentences are kept verbatim in §8.

**Corrected in the record-only round after the review of `da4338a`.** The fifth version (committed at `da4338a`) based its list of reads on a search that missed three reads. It covered only some of the session's directories and stopped before that round's own reads. It also worded some reads too broadly. Each is corrected below, and the wrong sentences are kept verbatim in §8.

- **What this record changes.** It rewrites no historical record. These stay as they are:
  - the commits `90bf9eb`, `22c9585`, `28f6ca3`, `2f752cd`, `e87373f` and `da4338a` and their messages;
  - their committed evidence files;
  - contract revisions 8.2, 8.3, 8.4 and 8.5;
  - the uncommitted scratch and `/tmp` files listed in §3.
- **Sources of this record.** Each statement rests on one of:
  - the repository: commits, committed files and code;
  - the attributes of the uncommitted files: names, file times, byte sizes, hashes, key names, set sizes and rounding counts;
  - geometry-only recomputation;
  - the author's account of the session record, which is not part of the repository. Statements that rest on it are marked "the author's account". They cannot be checked from the repository, and file access times do not settle them.
- **What was read (the author's account).** Based on the available session command history, the prototype and session metadata inspected included:
  - file names, timestamps and file sizes;
  - key names;
  - set-size lines and rounding-count lists;
  - `force_fail` settings, solver paths and the key names of `T`;
  - geometry-only stand-in generation.

  Other session files were read only for:
  - hashes and the file names of manifest entries;
  - key names, line counts and match counts;
  - script, source and document text;
  - log start/exit lines.

  No S1 energy, capacitance or bound value, and no `/tmp` Confirmation value, is known to have been read. That includes the energy, bound and capacitance values of the prototype's E1.1, E1.1-half and E1.2 sets. Their per-set rounding counts, solver paths and `force_fail` settings were read.

  One exception concerns synthetic proxies. The review of `28f6ca3` displayed the first 400 bytes of the prototype's `cert8_results.jsonl`. They show two non-selected configurations' proxy values: charge Q, enclosure width per unit of c, and g_E. Their islands are not S1's. The same command printed the selected configuration's g_E, the value already committed.

  This is an author/accounting statement derived from session command history and is not independently verifiable from the repository alone. The reads are listed below.
  - **How the list was made.** The session record's tool-call inputs were searched: every command, file path, search pattern, and the text of every file written. They cover the main session and every reviewer and helper agent.
    - **Period:** from the start of the revision-8.3 round (2026-09-24, 04:17 UTC) to the time this version's final search was run (11:49 UTC). That covers:
      - the revision-8.3, 8.4 and 8.5 rounds;
      - the cleanups that produced `e87373f` and `da4338a`, and this round;
      - the reviews of `22c9585`, `28f6ca3`, `2f752cd`, `e87373f` and `da4338a`.
    - **What was searched for:** any path in the session scratch area or under `/tmp/qmhp-e1-*`. Shell variables and `cd` targets were resolved within each command. Each command was resolved on its own: the tool resets the working directory to the repository after a command that leaves it.
    - **What was not consulted:** the outputs of those commands.
    - **Paths not counted as reads:** these rounds' own working files, which are review scratch, harness outputs and worktrees of committed code.
    - **What was read to make the list:** the session record itself was read only for its tool-call inputs and for the reports the rounds' reviewers returned.
    - **Limit:** a read that reaches a file without naming it or its directory would not be found.
  - **The `/tmp` Confirmation directories.** Their names, file names, file counts, byte sizes and times only.
  - **Names across the session scratch area:** directory listings and file searches.
  - **Source code.** The following source was read:
    - the revision-8 prototype's source (`next/e1/rev8/cost/*.py`, including `ldk8.py`, and the review's copy);
    - the configuration studies' scripts (`next/e1/cfg/*.py`);
    - a verification script (`next/verify/s3/x1_s1.py`).

    The prototype's stand-in generator was run for geometry only (§2).
  - **The prototype's run outputs.** These are `run8_*.json` and `run8_*.log`, the review's `rr_*`, and its copy of `run8_small.json`. The following were read:
    - their names, times (modification and access), byte sizes, key names, value types and list lengths;
    - the set sizes N, n_island and N_x, from the logs' one line `N … ni … nx …`;
    - the rounding counts m. For `run8_small`, which has no log, m = [532, 521, 512] (§2).
    - In the revision-8.3 round, also:
      - each JSON's `force_fail` setting and its `paths` (the solver path each set took);
      - the key names of its timing record `T`;
      - the number of its lines that match "K4", "E1.1" or "half".
    - In the review of `28f6ca3`, `force_fail` again.
    - In the review of `e87373f`, the logs' field names, and the K2b pair count 10,096, which the contract publishes.
    - In the cleanup that produced `da4338a` and in its review, the shapes of the log lines those greps matched. Their digits were masked, and only line shapes or counts were printed.
  - **The prototype's configuration-certification file** `cert8_results.jsonl`, in the review of `28f6ca3`:
    - the selected configuration's row: its parameters, N, solver path and proxy-A g_E. That g_E is the value committed in the contract and in `proxyA-gE.json`;
    - the file's first 400 bytes. They show the whole row of the configuration n = 32, q = 1.5, κ = 1.5, h = 1.25, w = 0.4, and most of the row of the configuration that differs from it only in q = 2.0:
      - their proxy A's N, solver path, pivot ratio and g_E;
      - the enclosure width per unit of c;
      - for the first, also the proxy's charge Q and its CPU time.

      These are values of synthetic proxies whose islands are not S1's. They were not used.
    - To establish what those bytes showed, the cleanup that produced `da4338a` and its review read only:
      - the file's line count;
      - its first line's length;
      - the key names, byte offsets and value types of its first two rows;
      - the configuration parameters (n, q, κ, h, w) of those rows.
  - **The selection study's result files** (`next/e1/cfg/*.jsonl`, `jobs_q.txt`, `selection3.json`):
    - their names, sizes, times (modification and access) and line counts;
    - in the review of `28f6ca3`, the number of lines in each that match `"n": 32, "q": 3.5`.
  - **The uncommitted pre-declaration drafts** `next/e1/frozen/E1-PREDECLARATION.rev4*` to `rev6*`: in the review of `28f6ca3`, their text around "q =" and "grading exponent".
  - **Other session files:**
    - the smoke Confirmation's `next/e1/smoke/conf-nominal.json`: its `code_sha256` hashes only;
    - `next/e1/evidence/code-at-evidence-start.json`: its key names;
    - the evidence-run script `next/e1/evidence/run.sh`;
    - the start and exit lines of `next/e1/evidence/run2.log`;
    - the manifests `REV8-MANIFEST.sha256` and the selection study's `SELECTION-MANIFEST.sha256`: their own hashes, their line counts and the file names of some of their entries;
    - cached S1 geometry: geometry only.
- **No S1 numerics (the author's account, from the same commands).** No S1 matrix was assembled or factorised for this record, and no S1 energy, bound or capacitance was formed. The rounds and reviews above ran only:
  - geometry-only comparisons: the S1 geometry phase, which assembles no matrix, and the prototype's stand-in generator;
  - tests and reviewer harnesses on small synthetic sets, including mutation tests of the separation check. Some harnesses ran the driver's attempt and Confirmation functions on such sets, redirected into scratch;
  - `--proxy-a-ge`, which refuses by design. It was run with the numerics routines replaced by stubs (review of `28f6ca3`).

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
- **S-5.** Session reports made while E1 was being implemented and reviewed. They described the Confirmation and its evidence as involving no S1 capacitance, energy or matrix. The session reports are not part of the repository; this item is the author's account of them.
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
  - **The prototype's reduced run is different (D16).** By the prototype's source, `run8_small` used a 500-panel draw of the same sheet: N = 1,524, with N_x = 1,324. How this is established is stated below. That the run used this path is the author's account.
    - Its E1.2 held S1's island plus 32 panels bit-identical to S1 E1.2 ground panels, so its matrix contained a 1,056-row block of S1's E1.2 entries (reasoning only).
    - **How N = 1,524 is established.** It is not derived from the rounding count. It is the size of the prototype's `--small` stand-in, `standin(500, 200)` in `run8.py`: S1's 1,024 island panels plus 500 ground panels drawn from the sheet, with N_x = 1,524 − 200 = 1,324. `standin.py` was last modified before the run (file times 23:28:43 and 23:32:06). The 32 comes from a geometry-only comparison of that stand-in with S1's E1.2.
    - **What the file shows.** `run8_small.json` records no N. Its rounding counts, read from the file, are m = [532, 521, 512], for its E1.2, E1.1 and E1.1-half passes. By the prototype's formula (`m_count` in `ldk8.py`), m = 532 holds for every N from 1,281 to 1,536. So m is consistent with N = 1,524 but does not determine it. The full-size stand-in (N = 9,995) gives m = 1,331.
    - **What rests on the session record.** `run8.py` was modified after `run8_small.json` was written (file time 23:38:47). Its current source therefore does not show by itself how that run was invoked. That the run used `--small`, with `standin(500, 200)`, is the author's account from the session record, which is not part of the repository.
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
| smoke nominal Confirmation | 2026-09-24 02:57–03:02 | pre-freeze implementation (not `90bf9eb`) | the same | `/tmp/qmhp-e1-confirmation-b7cbxuw0`: sigma and pass files only. Its output JSON and log are in session scratch (`next/e1/smoke/`, file time 03:02). By the author's account the JSON holds dimensionless per-set diagnostics, as the committed `confirmation-*.json` do; only its `code_sha256` hashes were read for this record. |
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

**What each `/tmp` directory holds** (as `driver.py` at `90bf9eb` writes these files; the file names are from listings):
- `sigma-E1.1*.json`: σ, Q and σᵀS₆₄σ.
- `pass-E1.1*.json`: Ê, Ŵ and Ĝ as exact fractions.
- `internal-sets.json`: C_lo, C̃ and w. It is in `akx65x9c`, `xfdweylp`, `v_3j__tc` and `59ubr8uc`. It is not in `b7cbxuw0` or `g_ee43ay`.
- They are preserved unchanged and are not committed. By the author's account they were not opened: the commands show only listings of their names, file counts, sizes and times.

**What the committed `confirmation-*.json` hold for E1.1 and E1.1-half:**
- dimensionless diagnostics only: path, m, width_rel, check_g_rel and g_E;
- the K4 statuses;
- no capacitance value.

By the author's account of the session record, session reports of that time showed the same dimensionless diagnostics. That record is not part of the repository.

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
- **The 90bf9eb evidence is superseded but kept.** The pre-approval evidence committed at `90bf9eb` stays byte-unchanged. It is regenerated only on a human instruction, after the revision-8.5 correction has passed review. Proxy A's evidence is not regenerated.
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

The third version (committed at `2f752cd`) said the following (review of `2f752cd`, finding REC-1).

| third version (verbatim) | why it is wrong | corrected in |
|---|---|---|
| "**Values not read.** The values of those uncommitted files were not read for this record. Only their names and timestamps were." | the revision-8.4 and 8.5 rounds also read the prototype files' key names, set sizes and rounding counts, and §2 cites `run8_small`'s m = 532. No energy, bound or capacitance value was read | the header ("What was read") |

The fourth version (committed at `e87373f`) said the following (review of `e87373f`; final cleanup).

| fourth version (verbatim) | why it is wrong | corrected in |
|---|---|---|
| "`run8_small` has no log. Its rounding count m = 532 was read, and gives its set size N = 1,524 (§2)." | m = 532 holds for every N from 1,281 to 1,536, so it does not give N. N = 1,524 comes from the prototype's source (`standin(500, 200)`), and that the run used it is the author's account | the header ("What was read"), §2 |
| "Its N follows from its rounding count (m = 532) and the prototype's `--small` path, `standin(500, 200)`." | the same | §2 |
| "**What was read.** No energy, bound or capacitance value of those uncommitted files was read for this record." | too broad. The review of `28f6ca3` printed the first 400 bytes of `cert8_results.jsonl`, which show bound- and capacitance-type values of two synthetic proxies (not S1's). The statement also rests on the session record, and it was not marked as such | the header ("What was read") |
| "No energy, bound or capacitance value was read" (in this section's row for the third version) | the same | the header ("What was read") |
| "Of the revision-8 prototype's session output files (`run8_*`, and the review's `rr_*`), only the following were read, in the revision-8.4 and 8.5 rounds: their names and timestamps, their key names, the set sizes N, n_island and N_x printed in their logs, and the rounding counts m in their JSON files." | incomplete. It left out the reads of the revision-8.3 round (`force_fail`, `paths`, the keys of `T`, line counts) and of the reviews. It also left out the other session files read: `cert8_results.jsonl`, the smoke Confirmation's hashes, and the evidence-run script and log | the header ("What was read") |
| "**No S1 numerics.** No S1 numerics were run for this record. The revision-8.4 and 8.5 rounds and the cleanup after the review of `2f752cd` ran only:" | it did not cover the reviews' harness runs, and it rests on the session record without saying so | the header ("No S1 numerics") |
| "The run's output JSON in session scratch holds dimensionless per-set diagnostics." (§3 table) | stated as verified; only its hashes were read for this record, and its content is the author's account | §3 |
| "These files were not read, are preserved unchanged, and are not committed." (§3) | stated as verified. That the files were not opened is the author's account, and their content is described from the code that writes them | §3 |
| "The same dimensionless diagnostics were shown in session reports." (§3) | stated as verified; it is the author's account of the session record | §3 |
| "Of the `/tmp` Confirmation files, only their names and timestamps were read." | incomplete: their file names, counts and sizes were also listed. It was replaced in the fifth version without being kept here (review of `da4338a`) | the header ("What was read") |

The fifth version (committed at `da4338a`) said the following (review of `da4338a`; record-only round).

| fifth version (verbatim) | why it is wrong | corrected in |
|---|---|---|
| "**Scope.** The reads listed below are those found by a search of the session record's commands (not their outputs) for the uncommitted files' names and directories, since the first version of this record." | the search looked only for some names and directories. It missed three reads in the review of `28f6ca3`: match counts in the selection study's result files, text of the pre-declaration drafts, and a verification script and its listing | the header ("How the list was made") |
| "both cleanups;" (the search's coverage) | the search stopped at the start of the cleanup that produced `da4338a`, so that cleanup's own reads were not listed | the header ("How the list was made") |
| "No S1 energy, bound or capacitance value was read for this record." | stated more firmly than a search of commands can support | the header ("What was read") |
| "In particular, none of the E1.1, E1.1-half or E1.2 quantities in the prototype's output files was read, and no value of a `/tmp` Confirmation file was read." | too broad: their per-set rounding counts, solver paths and `force_fail` settings were read. Only their energy, bound and capacitance values were not | the header ("What was read") |
| "the manifests `REV8-MANIFEST.sha256` and the selection study's `SELECTION-MANIFEST.sha256`: their hashes and entries (file names with hashes);" | overstated: only the manifests' own hashes, their line counts and the file names of some entries were printed | the header ("Other session files") |
| "the selection study's result files: their names and times;" | incomplete: their sizes, access times and line counts, and match counts, were also read | the header ("The selection study's result files") |
| "`run8_small` used a 500-panel draw of the same sheet: N = 1,524, with N_x = 1,324." (§2) | stated without its basis: N comes from the prototype's source, and that the run used it is the author's account | §2 |
