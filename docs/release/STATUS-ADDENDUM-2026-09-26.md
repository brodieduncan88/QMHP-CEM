# Status addendum, 26 September 2026

**Dated addendum. It edits nothing.** Every statement below was measured from the git objects of commit
`ba076d9d972077a7a3e256a6404ab455fd748461` (branch `qutip/branch-a-fixed-point-crosscheck-v1-prep`). That
is the commit the release claim and exception registers are frozen from. No earlier document, record,
manifest, register or hash-pinned file is changed by this addendum. The earlier text stays as it was
written. Where it disagrees with the state at ba076d9, this addendum records the measured state.

- Release scope: [`RELEASE-SCOPE.md`](RELEASE-SCOPE.md) (approved by the owner on 2026-09-26).
- Claims: [`CLAIM-REGISTER.json`](CLAIM-REGISTER.json). Exceptions: [`EXCEPTION-REGISTER.json`](EXCEPTION-REGISTER.json).
  The identifiers in the right-hand column (`REL-…`, `EXC-…`) refer to them.
- The addendum reconciles 82 locations:
  - 41 in ordinary documents, code comments and a test docstring (section 2);
  - 5 in the digest-pinned v0.1 specification (section 3b);
  - 19 in files pinned by the executed QuTiP record (section 3a);
  - 1 in the contract test that asserts that pinned text (section 3c);
  - 1 in a file this release's own test pins (section 3d);
  - 15 inside executed records or post-run provenance (section 4).

  Every quoted text was checked against the ba076d9 bytes before this file was written: where lines are
  given, each cited line or range must hold the quote on its own.
- This addendum is frozen by `tests/test_release_registers.py`. A later correction is a new, dated addendum;
  this one is never edited.

## 1. Status at ba076d9, in brief

| area | status at ba076d9 | register |
|---|---|---|
| Palace golden run (empty Object 001 PEC box) | 13 records, all CONVERGED on Palace 0.13.0 (a61c8cbe), one frequency tuple; worst closed-form deviation 4.7230588919842275e-05 against the 0.02 rule. QUALIFIED: X/Y extent and unit scaling only, blind to Z | REL-PAL-01 to REL-PAL-05 |
| Golden gate verdicts | overall INCOMPLETE in all 13. P4PRE_SPECTRAL PASS describes the empty box, not the package; COLLISION PASS is a nominal Branch-A device-model check that reads no Palace output | REL-PAL-05, REL-PAL-N1 |
| Empty-box mesh refinement | PASS in 3 records against the predeclared 1e-4 rules. QUALIFIED: non-monotone error, no order established | REL-PAL-06 |
| Auxiliary-box height sensitivity | PASS in 2 records, INCOMPLETE in 1 (the quarantined record's verdict field is not counted). QUALIFIED: auxiliary box, two levels | REL-PAL-07 |
| Object 001 height sensitivity | BLOCKED in 091242Z and 115901Z (DOF budget; 3600 s timeouts), INCOMPLETE in 065055Z (the quarantined record's verdict field is not counted). Not established | REL-PAL-08 |
| Real Palace validation of the Object 001 package | NOT-ESTABLISHED: the package has not been modelled | REL-PAL-N2 |
| `PALACE-VERIFY-20260915T063014Z` | failed execution, QUARANTINED; its verdict fields are not counted | EXC-P01 |
| QuTiP fixed-point cross-check | numerical cross-check PASS 11/11; execution integrity VERIFIED; protocol conformance QUALIFIED: RESOURCE-LIMIT DEVIATION. No overall scientific verdict was issued, and this is not an unqualified overall scientific PASS | REL-QT-01, EXC-Q01 |
| openEMS | UNSUPPORTED: preflight always refuses | REL-BD-01 |
| Planar and PicoGK geometry | UNSUPPORTED: not implemented; the code raises or exits 3 | REL-BD-02, REL-BD-03 |
| v0.1 definition of done | not met: items 3, 15-17 and 23 unmet; item 25 only partly met (one recorded successful CI build of an identical PicoGK project; no C# test project); items 9 and 10 wait on the FLAGGED pins; item 28 contradicted | EXC-B02 |
| Everything else (coupled candidate, E1, static studies, V2A, mock sweeps) | OUT-OF-SCOPE: neither endorsed nor withdrawn | REL-BD-04 |

## 2. Superseded or inaccurate statements in ordinary documents

These files are not hash-pinned and could be edited. This addendum does not edit them, because the approved
route is a dated addendum. Whether any of them later gains a pointer to this addendum is the owner's decision
(section 5). Files: `README.md`, `docs/agent-contract-implementation.md`, `docs/palace-execution.md`, `docs/palace-verification.md`, `orchestrator/pipeline.py`, `results/README.md`, `tests/test_frozen_evidence.py`.

| # | location at ba076d9 | text | status at ba076d9 | register |
|---|---|---|---|---|
| 1 | `README.md`:49 | “## Status: v0.1 scaffold” | The repository also holds executed v0.2 Palace records (13 PALACE-GOLDEN, 4 PALACE-VERIFY) and one executed QuTiP cross-check. The v0.1 definition of done is not met. | EXC-B02 |
| 2 | `README.md`:52-53 | “The physics and geometry generation are **not**.” | Physics is implemented (the same file's line 62). Geometry is not implemented and is UNSUPPORTED for the release. | REL-BD-02, REL-BD-03 |
| 3 | `README.md`:55 | “\| Layer \| Status \|” | The status table has no row for the QuTiP bridge (tools/qutip_bridge, docs/qutip, results/QUTIP-A-*). Status: executed once; numerical cross-check PASS 11/11, execution integrity VERIFIED, protocol conformance QUALIFIED: RESOURCE-LIMIT DEVIATION; no overall scientific verdict. | REL-QT-01 |
| 4 | `README.md`:65 | “across all eleven runs” | 13 golden records. The four-frequency tuple is identical in all 13; eig.csv takes two byte patterns (10 and 3 records). | REL-PAL-02, REL-PAL-04 |
| 5 | `README.md`:66 | “bounded Object 001 height attempts” | Outcomes: mesh refinement PASS in 3 records; auxiliary height PASS in 2, INCOMPLETE in 1; Object 001 height BLOCKED in 2 and INCOMPLETE in 1. Four records exist; the earliest, 063014Z, is quarantined and its verdict fields are not counted. | REL-PAL-06, REL-PAL-07, REL-PAL-08, EXC-P01 |
| 6 | `README.md`:67 | “Wired; container invocation not implemented” | Accurate as to the code. openEMS is now EXPLICITLY UNSUPPORTED for the release: preflight always raises SolverUnavailable. | REL-BD-01 |
| 7 | `README.md`:72-73 | “Three pins reproduce only to ~2e-6” | The deviations are 2.23e-6, 1.25e-6 and 9.04e-7; the last is within 1e-6 ('within, marginal'). All three remain FLAGGED-FOR-REVIEW. | EXC-R02 |
| 8 | `README.md`:79 | “Reaching `FEASIBLE_CANDIDATE_FOUND` requires Palace or openEMS.” | Neither reaches it in the release: openEMS is unsupported, and the Palace records state that coupling extraction is not available from solver 'palace'. | REL-BD-01, REL-PAL-05 |
| 9 | `README.md`:81 | “**v0.2 (in progress):**” | The release scope is frozen from ba076d9 as the Palace empty-cavity benchmark plus the QuTiP fixed-point bundle (docs/release/RELEASE-SCOPE.md). | - |
| 10 | `README.md`:152-159 | “\| `cem verify-master` \| Verify frozen provenance digests \|” | The CLI table omits `cem verify-results`, which exists. Neither it nor `cem report` can verify the launcher-registered or quarantined records; tests/test_frozen_evidence.py does. | EXC-R05 |
| 11 | `README.md`:207 | “stubs in v0.1” | The models are implemented (the same file's line 62). | - |
| 12 | `README.md`:258-260 | “and uv versions, dependency lock hash, .NET/PicoGK/ShapeKernel versions” | In all 17 Palace records uv_version is '(x86_64-unknown-linux-gnu)', a platform triple; picogk_version '2.3.0' is a constant while dotnet_version is null; shapekernel_revision is null. | EXC-P11 |
| 13 | `README.md`:272 | “\| ShapeKernel \| revision recorded in `geometry/package_picogk/driver.py` \|” | No revision is recorded: SHAPEKERNEL_REVISION is None. | EXC-B02 |
| 14 | `README.md`:278-280 | “If the .NET SDK is absent, geometry generation reports itself unavailable” | Geometry is unavailable even with .NET present: Program.cs returns 3 (NOT IMPLEMENTED). | REL-BD-03 |
| 15 | `docs/palace-execution.md`:7-8 | “Four records so far:” | 13 PALACE-GOLDEN records, all CONVERGED with the same frequencies. | REL-PAL-01 |
| 16 | `docs/palace-execution.md`:19-22 | “and so ran with more thread parallelism” | Superseded by the same document (lines 292-307): the da6f7d0d pattern recurred after the thread pin. The cause is not established. | EXC-P02 |
| 17 | `docs/palace-execution.md`:130-131 | “that campaign is deferred (spec §15).” | Executed: mesh refinement PASS in PALACE-VERIFY 065055Z, 091242Z and 115901Z. | REL-PAL-06 |
| 18 | `docs/palace-execution.md`:187-189 | “It ran once, as the last step of the golden-run job” | Not verifiable from the repository. RUN_SWEEP defaults to true on push, so the step probably ran in later golden runs too (inferred from .github/workflows/palace-golden.yml:66, 162-165). No sweep output is committed. | REL-PAL-N4, EXC-P08 |
| 19 | `docs/palace-execution.md`:218-220 | “so a run is single-threaded end to end” | By the same document (lines 12-14), the first three records (image cc87ec6b) predate the pin. No record measures the thread settings. In the records built after the pin, Palace Total spans 23.21 s to 40.95 s. | EXC-P03 |
| 20 | `docs/palace-execution.md`:273-276 | “residual digits reproducing in three of four records and the odd one out explained” | The residual digits reproduce in 10 of 13 records (19877b1e). The odd pattern is not explained. | REL-PAL-04, EXC-P02 |
| 21 | `docs/palace-execution.md`:278 | “### Reproducibility across all eleven golden records” | 13 golden records. The single frequency tuple, the identical gate verdicts and the two eig.csv patterns all still hold at 13. | REL-PAL-04 |
| 22 | `docs/palace-execution.md`:280-281 | “two images (before and after the GSLIB rebuild)” | The count of eleven was correct when written. Those eleven records carry six distinct image IDs, not two; what differs is two GSLIB label states. All 17 Palace records carry seven. | EXC-P04 |
| 23 | `docs/palace-execution.md`:284 | “result across all eleven records” | Holds for all 13 records; only the count is stale (likewise 'identical in all eleven' at line 290). | REL-PAL-04, REL-PAL-05 |
| 24 | `docs/palace-execution.md`:287 | “(eight records)” | 19877b1e is now in 10 records (adds 023201Z and 120817Z); da6f7d0d is still the same three. | REL-PAL-04 |
| 25 | `docs/palace-execution.md`:288 | “at the eleventh to twelfth significant digit” | Q and the error columns differ at about the 6th significant digit of their own values (for example Q 1.457891874e+09 against 1.457883448e+09). The real parts are identical. | EXC-P02 |
| 26 | `docs/palace-execution.md`:309 | “The two PASS verdicts describe the empty box” | Only the P4PRE_SPECTRAL PASS reads the Palace modes. The COLLISION PASS is computed from the nominal Branch-A device model (dressed_system.dressed_spectrum()) and reads no Palace output. | REL-PAL-05 |
| 27 | `docs/palace-execution.md`:300-301 | “The pin removed the large wall-clock swing” | Not supported by the records built after the pin (their thread settings are unmeasured): their Palace Total times range from 23.207766373 s to 40.952382498 s. | EXC-P03 |
| 28 | `docs/palace-verification.md`:14-15 | “the five `PALACE-GOLDEN-*` records are not touched.” | 13 golden records; none has been touched. Only the count is stale. | REL-PAL-10 |
| 29 | `docs/palace-verification.md`:85-87 | “so the benchmark is BLOCKED with those timeouts as the measurement.” | The timeouts occurred in all three complete campaigns. The recorded verdict is BLOCKED in 091242Z and 115901Z but INCOMPLETE in 065055Z. | REL-PAL-08 |
| 30 | `docs/palace-verification.md`:102-105 | “Three records exist on the milestone branch” | Four records exist. Images: 063014Z 732526ec (no GSLIB label), 065055Z and 091242Z f41ad915, 115901Z 2440f8d0. | EXC-P04 |
| 31 | `docs/palace-verification.md`:109 | “\| `PALACE-VERIFY-20260915T063014Z` \| 34937561169 (first attempt) \| none \|” | The creating commit 9cf7cb1 names workflow run 34937093910. summary.json records verdict fields (mesh INCOMPLETE, aux BLOCKED, Object 001 BLOCKED; complete false). The first run failed in Palace (GSLIB, exit 1) before report rendering failed. 'no manifest' is correct. | EXC-P01 |
| 32 | `docs/palace-verification.md`:110 | “\| `PALACE-VERIFY-20260915T065055Z` \| 34937561169 \|” | The verdicts match summary.json. The committing commit 90924c1 also reports a campaign workflow step failure, which is not mentioned. | EXC-P06 |
| 33 | `docs/palace-verification.md`:111 | “\| `PALACE-VERIFY-20260915T091242Z` \| 34951039973 \|” | The table omits the fourth record, PALACE-VERIFY-20260915T115901Z: workflow run 34964909999 (commit e736226), analysis git_commit ac8bc4a0, image 2440f8d0, mesh PASS, aux PASS, Object 001 BLOCKED, complete. | REL-PAL-06, REL-PAL-07, REL-PAL-08 |
| 34 | `docs/palace-verification.md`:113-117 | “so unlike the golden run the campaign `eig.csv` files are not byte-identical” | Three complete records exist. 091242Z and 115901Z have byte-identical eig.csv for all 7 converged runs; only 065055Z differs. The golden run also has two byte patterns. | REL-PAL-09 |
| 35 | `docs/palace-verification.md`:134-138 | “ran out their 3600 s budget in both campaigns.” | In all three complete campaigns (065055Z, 091242Z, 115901Z). | REL-PAL-08 |
| 36 | `docs/agent-contract-implementation.md`:67 | “the COMPLETE trigger surface of all five workflows” | Seven workflow files exist at ba076d9, and tests/test_launch_authority.py pins all seven. | - |
| 37 | `docs/agent-contract-implementation.md`:165 | “**One record has no manifest and is quarantined, not covered.**” | Two records are quarantined (the second is STATIC-ANCHOR-TEST-20260922T192243Z), and four QUTIP-A records are launcher-registered. | EXC-P01, EXC-R01, EXC-Q02 |
| 38 | `results/README.md`:5-7 | “results/ └── BATCH-<timestamp>/” | No BATCH-* record exists. The release-scope families (PALACE-GOLDEN, PALACE-VERIFY, QUTIP-A) are laid out differently, and `cem report` cannot verify them; tests/test_frozen_evidence.py does. | EXC-R05 |
| 39 | `tests/test_frozen_evidence.py`:19 | “the 33 historical records” | 34 manifested records (asserted at line 271), plus 2 quarantined and 4 launcher-registered. | REL-PAL-10 |
| 40 | `tests/test_frozen_evidence.py`:260 | “33 records” | As above. | REL-PAL-10 |
| 41 | `orchestrator/pipeline.py`:482-483 | “Object 001 geometry was not generated; the PicoGK project requires” | The note implies that .NET would suffice. Generation is not implemented at all (Program.cs returns 3). | REL-BD-03 |

## 3. Text in pinned files: never edited, read as follows

### 3a. Files pinned by the executed QuTiP record

The executed QuTiP record pins these files' bytes (expected-hashes record `b667aad5…`, the launcher's
`CHECKER_SHA256`/`SCHEMA_SHA256`, and the ledger and receipt). Editing any of them would break byte
equality with the executed evidence. Byte-identical copies of the checker (`9f0798c5…`) and schema
(`a65958db…`) sit inside the three QUTIP-A records that carry inputs, so these rows apply to those copies too.
Most of the status text described the state before approval and execution: it is superseded as a
description of ba076d9 and was correct when written. The exception is the linked-library sentence (the
rows citing EXC-Q03). It was never correct: the checker records the platform and the python, numpy, scipy
and qutip version strings, but no linked-library (BLAS/LAPACK/Accelerate) information.

| # | location at ba076d9 | text | status at ba076d9 | register |
|---|---|---|---|---|
| 1 | `docs/qutip/branch-a-fixed-point-crosscheck-v1.md`:3 | “**Status: PREPARED, NOT APPROVED, NOT EXECUTED. Scientific execution is BLOCKED.**” | Approved and executed once (EXECUTION-COMPLETED 2026-09-26T06:16:46Z). The attempt is spent. | REL-QT-01 |
| 2 | `docs/qutip/branch-a-fixed-point-crosscheck-v1.md`:6 | “No reference snapshot has been generated. No QuTiP calculation has been run.” | The snapshot (bb09bcbd...), the frozen rules (42e1c2a9...), the approvals and the execution record all exist. | REL-QT-07, REL-QT-02 |
| 3 | `docs/qutip/branch-a-fixed-point-crosscheck-v1.md`:97 | “**The ambiguity rule is not yet approved.**” | The frozen rules supply label_min_overlap 0.5 and label_min_margin 0.1. | REL-QT-02 |
| 4 | `docs/qutip/branch-a-fixed-point-crosscheck-v1.md`:130 | “They are **not approved**” | The thresholds were frozen by human approval as ENGINEERING-RULE. 'Not frozen master requirements' and 'not error bounds' remain true. | REL-QT-02, REL-QT-QN3 |
| 5 | `docs/qutip/branch-a-fixed-point-crosscheck-v1.md`:140 | “**Still to be frozen by a human before any evidence-bearing run.**” | Frozen and hash-bound for the run. | REL-QT-02 |
| 6 | `docs/qutip/branch-a-fixed-point-crosscheck-v1.md`:199 | “The platform and the linked numerical libraries are recorded, not qualified.” | Incorrect: the platform is recorded; linked numerical libraries are not. | EXC-Q03 |
| 7 | `docs/qutip/branch-a-fixed-point-crosscheck-v1.md`:220 | “The platform and linked libraries are recorded, not qualified.” | Incorrect for the same reason. The sentence before it on the same line (INPUTS-HASH-VERIFIED and RUNTIME-VERSIONS-MATCHED) is accurate. | EXC-Q03 |
| 8 | `docs/qutip/branch-a-fixed-point-crosscheck-v1.md`:253 | “so the QuTiP assembly path is exercised by no test.” | Still true for tests. The assembly path ran once in the Mac evidence execution, which is not a test. | REL-QT-QN6 |
| 9 | `docs/qutip/branch-a-fixed-point-crosscheck-v1.md`:257 | “None is granted by this document.” | Steps 1 to 4 were completed. Step 5 was executed once (execution approval -v2), but through a launcher that did NOT enforce the frozen memory_limit_MB = 1024: the separately approved address-space-growth control was applied instead, and it is not a memory limit. The approvals are session statements. | EXC-Q01, REL-QT-10 |
| 10 | `docs/qutip/branch-a-fixed-point-crosscheck-v1.md`:275-278 | “Open items: - the launcher mechanism for the Mac; - where the returned record is verified and stored; - ret...” | The first two are resolved (the committed launcher; results/QUTIP-A-* verified by tests/test_frozen_evidence.py). Retention is still open: the upload archives stay with the owner. | EXC-Q04, EXC-Q09 |
| 11 | `tools/qutip_bridge/check_branch_a_reference.py`:6 | “STATUS: PREPARED, NOT APPROVED, NOT EXECUTED.” | This exact checker executed once on the Mac and COMPLETED. | REL-QT-04 |
| 12 | `tools/qutip_bridge/check_branch_a_reference.py`:986-988 | “platform and linked libraries are recorded, " "not qualified)” | Overclaim, emitted verbatim into the evidence record's result.json. | EXC-Q03 |
| 13 | `scripts/export_qutip_branch_a_reference.py`:6 | “STATUS: PREPARED, NOT APPROVED, NOT EXECUTED. No snapshot has been generated.” | Exported from 110a2e0 (snapshot started 2026-09-25T23:06:52Z; source_tree_clean is the exporter's own record). One attempt was permitted and only run-attempt1 files exist; that it ran once is not re-measured. | REL-QT-07 |
| 14 | `schemas/qutip/branch-a-reference-v1.schema.json`:5 | “"$comment": "PREPARED, NOT APPROVED, NOT EXECUTED.” | The status prefix is superseded; the keyword-subset description is still accurate. | REL-QT-08 |
| 15 | `schemas/qutip/branch-a-reference-v1.schema.json`:75 | “PROPOSED ENGINEERING-RULE, not approved, not carried in this payload” | 'not approved' is superseded; 'not carried in this payload' is still true. | REL-QT-02 |
| 16 | `experiments/qutip-a-readout-crosscheck/qutip_branch_a_launcher_asgrowth.py`:6 | “STATUS: PREPARED FOR HUMAN REVIEW. NOT RUN ON THE TARGET MAC.” | It ran on the Mac for the qualification (06:06:42Z) and the execution (06:16:43Z) on 2026-09-26. | REL-QT-04, REL-QT-05 |
| 17 | `experiments/qutip-a-readout-crosscheck/qutip_branch_a_launcher_asgrowth.py`:16 | “a NEW PROPOSED rule” | The rule was approved (OWNER-APPROVAL-2026-09-26-QUTIP-A-AS-GROWTH-RULE-v1; RESOURCE-RULE-APPROVAL.json). | EXC-Q01 |
| 18 | `experiments/qutip-a-readout-crosscheck/qutip_branch_a_launcher_asgrowth.py`:102 | “(PROPOSED; requires separate human approval before” | As above (and the heading '# ... resource rule (PROPOSED)' at line 93). The rule text is emitted verbatim into the execution record (section 4). | EXC-Q01, EXC-Q07 |
| 19 | `experiments/qutip-a-readout-crosscheck/qutip_branch_a_launcher_asgrowth.py`:964 | “"rule_status": "PROPOSED; requires separate human approval before scientific execution"” | As above; emitted into the records' rule_status fields (section 4). | EXC-Q01, EXC-Q07 |

### 3b. The v0.1 specification, digest-pinned by the frozen master provenance

`master/provenance.json` records `cem_spec_sha256` (`dd1386a4…`), `contracts/master.py` compares it with
the file, and CI runs `cem verify-master` on every push. An edit to the specification, including a one-line
pointer, would fail CI unless the frozen master provenance were regenerated, which needs its own approval.

| # | location at ba076d9 | text | status at ba076d9 | register |
|---|---|---|---|---|
| 1 | `QMHP-CEM_v0.1_Spec.md`:7 | “**Status:** AUTHORITATIVE FOR QMHP-CEM v0.1 BUILD” | Still the v0.1 build specification. It cannot take a status note of its own without a change to the frozen master provenance; this addendum records the v0.2 Palace records, the QuTiP bundle and the unsupported openEMS/geometry paths. | - |
| 2 | `QMHP-CEM_v0.1_Spec.md`:1067-1069 | “### 10.4 openEMS Same rules as Palace.” | openEMS is UNSUPPORTED for the release; the adapter always refuses. | REL-BD-01 |
| 3 | `QMHP-CEM_v0.1_Spec.md`:1367 | “3. .NET/PicoGK/ShapeKernel versions are pinned.” | Not met; nor are items 15, 16, 17 (lines 1379-1381) and 23 (line 1387). Item 25 (line 1389) is only partly met: the one recorded dotnet CI outcome is a successful build on 3270469, whose PicoGK project and ci.yml are byte-identical at ba076d9, and no C# test project exists. Items 9 and 10 wait on the FLAGGED pins (EXC-R02). | EXC-B02 |
| 4 | `QMHP-CEM_v0.1_Spec.md`:1392 | “28. No v0.2 work has been started.” | Contradicted: v0.2 Palace execution and verification records exist. | EXC-B02 |
| 5 | `QMHP-CEM_v0.1_Spec.md`:1402-1403 | “- real Palace validation of Object 001; - solver-convergence campaigns;” | Empty-box mesh refinement has been executed (PASS in 3 records). Real Palace validation of Object 001 is NOT-ESTABLISHED, and its height benchmark is BLOCKED. | REL-PAL-06, REL-PAL-08, REL-PAL-N2 |

### 3c. The contract test that asserts the pinned text

| # | location at ba076d9 | text | status at ba076d9 | register |
|---|---|---|---|---|
| 1 | `tests/test_qutip_bridge_contract.py`:712 | “assert "PREPARED, NOT APPROVED, NOT EXECUTED" in text” | Not hash-pinned itself, but this assertion, with those at lines 902 ('**not approved**') and 905 ('PROPOSED ENGINEERING-RULE, not approved'), enforces the stale strings in section 3a, so the pinned files cannot be edited without breaking both the evidence pins and these tests. | EXC-Q07 |

### 3d. A file this release pins

`tests/test_release_registers.py` binds the bytes of the refusing openEMS and geometry files (REL-BD-01 to
REL-BD-03), so this comment cannot be edited, even to add a pointer, without a superseding scope.

| # | location at ba076d9 | text | status at ba076d9 | register |
|---|---|---|---|---|
| 1 | `solvers/openems/adapter.py`:59-60 | “Real openEMS validation of Object 001 is” | Spec section 15's v0.2 scope does not list openEMS. For the release, openEMS is unsupported, not deferred. | REL-BD-01 |

## 4. Text inside executed records and post-run provenance: never edited, read as follows

| # | location at ba076d9 | text | status at ba076d9 | register |
|---|---|---|---|---|
| 1 | `results/QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z/launcher-final.json`:330 | “"rule_status": "PROPOSED; requires separate human approval before scientific execution"” | Emitted verbatim from the launcher's pinned rule text, as is the '(PROPOSED; ...)' inside rule_text at lines 24 and 328. The same file records the approval file the launcher consumed (resource_rule_approval: OWNER-APPROVAL-2026-09-26-QUTIP-A-AS-GROWTH-RULE-v1, sha256 7d38e9de..., equal to RESOURCE-RULE-APPROVAL.json). The owner's approval itself is a session statement. | EXC-Q07, EXC-Q01, REL-QT-10 |
| 2 | `results/QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z/attempt-receipt.json`:95 | “"rule_status": "PROPOSED; requires separate human approval before scientific execution"” | As above (rule_text at line 93); the receipt also records resource_rule_approval. | EXC-Q07, EXC-Q01 |
| 3 | `results/QUTIP-A-LAUNCHER-CONTROL-TEST-20260926T060642Z/qualification-final.json`:328 | “"rule_status": "PROPOSED; requires separate human approval before scientific execution"” | Accurate when written (rule_text at lines 20 and 326 likewise): the approval file names this file's digest (63efd145...), so it was written afterwards. | EXC-Q07 |
| 4 | `results/QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z/launcher-final.json`:331 | “"memory_growth_limit_MiB": 1024” | The parameter of the approved address-space growth rule (RLIMIT_AS = baseline virtual size + 1073741824 bytes). It is not a memory limit of any kind. Also in attempt-receipt.json:96 and the qualification record's qualification-final.json:329. | EXC-Q13, EXC-Q01 |
| 5 | `results/QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z/launcher-final.json`:531 | “platform and linked libraries are recorded, not qualified” | The checker's overclaim, copied into the launcher's classification; linked libraries were not recorded. | EXC-Q03 |
| 6 | `results/QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z/checker-output/attempt.json`:4 | “"status": "STARTED"” | Written by the checker before it calculates; result.json records execution_status COMPLETED. | EXC-Q13 |
| 7 | `results/QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z/checker.stdout`:1 | “; no calculation performed” | The validation stage's line; the second line reports COMPLETED. | EXC-Q13 |
| 8 | `results/PALACE-GOLDEN-20260915T025408Z/execution_record.json` | “"validated": true” | In 11 of the 13 golden records (the first two predate the field). It means the result passed validate_convergence() (scripts/palace_golden_run.py:271): eigensolver-convergence acceptance of the empty box, not validation of Object 001. | EXC-P09, REL-PAL-N2 |
| 9 | `results/QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z/inputs/archive/qmhp-qutip-branch-a-export-110a2e0-attempt1/branch-a-reference-v1.json`:29 | “"comparison_thresholds": "PROPOSED ENGINEERING-RULE, not approved, not carried in this payload"” | True when exported. The frozen-rules file (FROZEN-BY-HUMAN-APPROVAL) supersedes 'not approved'. | EXC-Q07 |
| 10 | `results/QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z/inputs/archive/qmhp-qutip-branch-a-preservation-110a2e0-attempt1/README.txt`:17 | “No QuTiP calculation has been run.” | True when the export archive was made; identical copies are in the BLOCKED and CONTROL-TEST records. | EXC-Q07 |
| 11 | `results/QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z/checker-output/result.json` | “platform and linked libraries are recorded, not qualified” | Overclaim (see the checker lines above). Linked-library provenance is NOT-ESTABLISHED. | EXC-Q03 |
| 12 | `results/PALACE-GOLDEN-20260915T014639Z/execution_record.json` | “not yet a mesh-converged result (spec §15)” | In all 13 golden records. Written before the verification campaign; empty-box mesh refinement has since passed in 3 records. The Object 001 package is still not mesh-converged, because it has not been modelled. | EXC-P09, REL-PAL-06 |
| 13 | `results/PALACE-GOLDEN-20260915T014639Z/execution_record.json` | “which are not implemented in v0.1.” | In all 13 golden records (TOLERANCE gate reason). The models are implemented; the gate was not evaluated because no ensemble was requested (--tolerance-samples 0), as the same record's quantum_unavailable says. | EXC-P09 |
| 14 | `results/PALACE-GOLDEN-20260915T014639Z/execution_record.json` | “"uv_version": "(x86_64-unknown-linux-gnu)"” | In all 17 Palace records. A platform triple, not a uv version. | EXC-P11 |
| 15 | `experiments/qutip-a-readout-crosscheck/EXECUTION-LOG.json` | “two read-only reviewers” | A reviewer count is not evidence; REL-QT-03 is the recomputation this register relies on. | EXC-Q12 |

## 5. What this addendum does not do

- It edits no document, record, manifest, register, test or pinned file. The owner decides whether any
  ordinary document in section 2 should later gain a one-line pointer to this addendum; no pointer has
  been added. The files in sections 3a, 3b and 3d cannot take one without breaking their pins.
- It runs nothing. No solver, QuTiP, exporter or workflow was executed to produce it.
- It creates no release, tag, publication, merge or pull request.
- It resolves no open item. EXC-Q06 and EXC-P14 (licence status of QuTiP, and of Palace, the libraries its
  image builds and gmsh) and EXC-R02 (FLAGGED regression pins) need a human decision. EXC-P10 (out-of-scope material that reads the empty-box 9.635690 GHz mode as a package
  mode) needs an owner review of the coupled-candidate binding, outside the release.
