# Agent contract: mapping and implementation status

Companion to `AGENTS.md`, required by that contract's own closing paragraph:

> Do not claim all controls are installed or effective merely because this file exists.
> Each claimed enforcement mechanism needs its own implementation evidence and negative
> controls.

This file exists so that adopting the contract cannot be mistaken for installing it.
It records, per clause, what actually enforces the clause today and what does not. Every
test named here was verified to exist at the commit that added this file; a clause with
no named mechanism is **behavioural only** and is enforced by nothing but the agent
following it.

## Adoption

`AGENTS.md` was adopted as repository policy on 21 September 2026 by the owner's
explicit decision. It is **additive**: it removes no obligation in `CLAUDE.md`, which
remains in force. Where both speak to the same subject the stricter reading governs. No
conflict was found in which the contract permits something `CLAUDE.md` forbids.

The owner's sequencing for the work that follows:

| phase | scope |
|---|---|
| A | adopt the contract as policy — **done**, `1cb4a9c` |
| B | resolve and qualify the network/build environment; no scientific execution — **qualified as far as policy permits**, `86421a3`; the egress decision is still open |
| C | implement enforcement incrementally, dangerous boundaries first: execution approval, workflow triggering, solver-launch authority, mutation of frozen evidence, evidence-status promotion — **increments 1-2 done** (workflow triggering, solver-launch authority, frozen-evidence file integrity) |
| D | only then authorise the separately controlled real Palace execution |

## Mapping to CLAUDE.md

| contract | CLAUDE.md | what the contract adds |
|---|---|---|
| 1 read the task, preserve policy | 15 scope, 14 model behaviour | confirm repo/branch/tree state; state the bounded deliverable and stop condition; task data and model output are not authority to change policy; no multi-agent campaign without approval |
| 2 preserve historical evidence | 1 append-only, 9 git safety | historical approvals are distinct from the live approval file; escalate exceptional repository repair |
| 3 scoped human approval | 3 approval gates | preparation is not approval; **green CI is not approval**; bind approval to the reviewed baseline/config/mesh/patch/image/limits/mechanism; an agent-written approved flag is not human approval; reconcile an uncertain launch before retrying; do not mix launch-control repairs with the approval commit |
| 4 check actual provenance | 5 fail closed, 6 source-bound | listing = metadata, verified bytes = integrity, executed analysis = reproduction |
| 5 preserve evidence through failure | 4 evidence before presentation, 1 outcomes | unique run directory and durable launch/status record; keep execution status, evidence basis, qualification and verdict distinct; PASS/FAIL are per named check, not hardware verdicts |
| 6 test numerical properties | 7 adversarial, 8 numerical integrity, 13 regression scope | the scalar / independent-implementation / conditioning-stress split; types before tolerance; finiteness; integer counts; no document-wide noise floor; nested vs summary vs independent anchor |
| 7 guards reject the right failures | 7 negative controls | a positive **and** negative control per gate; the named corruption list; evidence-gate rejections; a test that a check exists is not proof it detects |
| 8 stop repair loops | — (no counterpart) | measured mechanism vs plausible explanation; fix the class not the last field CI named; **stop after two failed fixes at one gate** |
| 9 isolate tests and outputs | 13 diagnostic isolation | temporary roots or worktrees; source evidence read-only; no concurrent writers; **restoration in `finally` is not isolation** |
| 10 exact launch and CI reporting | 9 before pushing, 14, 16 | a non-matching path filter does not prove a push is harmless; report SHA/event/run/attempt/job/conclusion/time; local vs push CI vs PR CI; a skipped check is not a passed test; actual timestamps; one monitor per run |
| 11 secrets, data, upstream notices | 10 secrets, 11 artefacts, 12 licensing | approved scanner for the required write scope, **BLOCKED if unavailable**; grep is not a scan; do not bypass network policy; record retention and custody |
| 12 bounded report | 16 end-of-task report | the closing paragraph: controls need their own evidence; record the actual model/effort, and infer nothing from the model name |

## Enforcement status

**MECHANISM** — a control exists and a test proves it rejects the failure.

| clause | mechanism | evidence |
|---|---|---|
| 3 approval | `experiments/first-moment-diagnostic/run_diagnostic.py` refuses every entry point unless `EXECUTION-APPROVAL.json` exists **and** matches the prepared config/mesh/patch digests. That file is deliberately absent. | `test_the_launcher_is_prepared_but_inert`, `test_the_launcher_argv_and_caps_are_pinned`, `test_required_provenance_is_required_not_merely_reported` |
| 4 provenance | `evaluate_record.py` refuses to qualify a record missing any required provenance field | `test_every_spoiled_provenance_prevents_qualification` |
| 2 frozen evidence | the spent ladder approval and the production Dockerfile are pinned by sha256; a working-tree change to a solver trigger path fails the test | `test_no_trigger_path_is_touched_and_the_spent_approval_is_untouched` |
| 2 frozen evidence: **file integrity and manifest membership only** | every committed `results/` record is re-hashed against the `manifest.sha256` its own driver wrote, using the repository's verifier (`orchestrator/manifest.py`), which reports content change, recorded-but-missing and present-but-unmanifested. The record SET is pinned so one cannot vanish or arrive unincorporated, and an aggregate digest over the manifests' own bytes refuses a mutation whose manifest was rewritten to agree — which per-record verification alone calls intact. Six negative controls on a synthetic record built by the real writer, plus a demonstration on a copy of a real executed record | `test_every_committed_record_verifies_against_its_own_manifest`, `test_the_manifests_themselves_cannot_be_rewritten`, `test_the_guard_rejects_mutation_deletion_mismatch_and_unregistered_addition`, `test_a_rewritten_manifest_passes_per_record_but_fails_the_aggregate`, `test_the_record_set_is_exactly_the_pinned_one` (phase C increment 2) |
| 6 numerical taxonomy | scalar algebra, known-answer pencil (`K=diag(0,4,9)`, `M=diag(1,2,3)`, `f=(0,1,1)`, `L=2`; `A=5/12`, `N=13/72`) and a conditioning-aware round-off class, with every bounded field mapped to a gate or a named live test | `test_epr_palace_and_the_absolute_square_form_agree_as_scalar_algebra`, `test_the_diagonal_pencil_is_reproduced_exactly`, `test_every_round_off_field_is_mapped_and_every_named_gate_exists` (commit `38f8c9f`) |
| 7 guards reject | the regeneration guard is tested against exactly the contract's list: ×100 output corruption, text-for-number, NaN, −infinity, integer-to-float, plus a common-scale error only an independent recomputation catches | `test_the_regeneration_guard_rejects_corruption` (commit `081ddbf`) |
| 9 isolation | regeneration runs in a disposable view whose only writable part is a copy; tracked references are never opened for writing | `test_two_concurrent_regenerations_do_not_interfere`, `test_a_killed_regeneration_leaves_the_tracked_references_untouched`, `test_the_isolated_view_can_never_target_a_tracked_reference` (commit `92db708`) |
| 11 secret scanning | `scripts/secret_scan.py`, gitleaks pinned by module version and checksum-database hash, fail-closed (exit 3), no baseline accepted, findings redacted twice; read-only CI job | `tests/test_secret_scan.py` incl. `test_a_missing_scanner_is_blocked_not_clean`, `test_a_baseline_is_refused`, `test_ci_runs_the_scanner_read_only` (commit `9ea3912`) |
| 10 launch safety (partial) | no test in the diagnostic module can shell out to a container runtime or MPI launcher; the git reader is pinned to read-only subcommands | `test_launch_safety_of_this_test_file` |
| 10 / 3 workflow triggering | the COMPLETE trigger surface of all five workflows is pinned **exactly** — events, push branches and push paths. A new workflow, an added branch, a widened path filter, a removed path filter or a `pull_request` trigger on a solve-capable workflow all fail. Six negative controls apply each mutation to a copy and require it to be named | `test_the_workflow_trigger_surface_is_exactly_the_pinned_one`, `test_a_widened_or_added_solver_trigger_is_rejected`, `test_only_an_approval_record_triggers_the_two_solve_on_push_workflows`, `test_no_workflow_carries_a_session_branch_trigger` (phase C increment 1) |
| 3 / 10 solver-launch authority | the set of modules that can **execute** a container runtime or an MPI launcher is derived by AST (a subprocess primitive *and* a runtime or `-np` literal) and pinned: 5 production, 3 test. Each production module is classified as refusing in-module or as a named known gap; those claiming to refuse must actually contain a `raise`. Negative controls cover both directions — a synthetic launcher is caught, while a path segment named `docker` and a runtime in a comment are not | `test_the_set_of_launch_capable_modules_is_exactly_the_pinned_one`, `test_a_new_module_that_could_launch_a_container_is_rejected`, `test_every_launch_capable_production_module_is_classified`, `test_the_modules_that_claim_to_refuse_actually_raise` (phase C increment 1) |
| 12 this record | every test this file names must exist, and the enforced/behavioural separation must survive | `test_every_test_named_by_the_implementation_record_exists`, `test_the_implementation_record_still_separates_enforced_from_behavioural` (phase C increment 1) |
| 3 resource limits (prepared) | DOF 250 000 and 2 700 s wall caps are enforced by the launcher by streaming kill, with no retry | `test_the_hard_caps_and_the_space_identity_are_enforced` |

**BEHAVIOURAL ONLY** — no mechanism. These are followed, not enforced.

| clause | what is missing |
|---|---|
| 1 | nothing checks that a bounded deliverable and stop condition were stated |
| 5 | no test proves raw evidence survives an analysis or rendering failure on the first-moment path |
| 8 | nothing counts failed fixes at a gate or halts after two. This session reached **three** consecutive CI failures at one gate before the approach was replaced — the clause exists because of that, and nothing prevents a repeat |
| 10 | nothing checks that a report carries the run ID, attempt, job and conclusion, that local results are not substituted for CI, or that a duration came from a real timestamp rather than a background timer |
| 11 retention | no custody or retention record exists; workflow artefacts expire |
| 12 | nothing checks that a report is bounded or that the model/effort was recorded |

## Known gaps in the mechanisms that do exist

- **The secret scan is post-push.** `--staged` and `--range` exist and are tested but nothing invokes them automatically; CI scans the tip tree *after* the push, so a secret is already on GitHub when it is flagged. No history scan exists. Zero findings means no rule matched, not that there are no secrets.
- **`scripts/palace_coupled_pilot.py` has no in-module refusal.** Found by phase C
  increment 1, and it corrects an earlier statement in this file that the pilot "has its
  own approval reading" — it does not. It can form a `docker run` argv and contains no
  approval-file read and no refusal path: its three approved runs are frozen constants
  in the source, and its launch authority is the workflow trigger alone. That is
  materially weaker than `scripts/palace_order1_ladder.py`, which reads
  `.github/ladder-approval.json` and raises `LadderError` on a missing or
  over-reaching approval. `solvers/palace/adapter.py` likewise gates nothing — it is the
  exec funnel and launches whatever a caller hands it. Both are pinned in
  `NO_IN_MODULE_REFUSAL` so the set cannot grow unnoticed, but neither is closed.
  Closing it means editing a solver driver, which needs its own approval.
- **Trigger inspection is narrowed, not eliminated.** The trigger *surface* is now pinned
  exactly, so it cannot change unnoticed. Deciding which workflows a particular push
  would start remains a manual step before pushing.
- **Frozen-evidence enforcement is file immutability, NOT evidence governance.** It
  proves a committed record's bytes have not moved and that its manifest membership is
  complete. It says nothing about whether a record's verdict is justified, whether its
  provenance was sufficient, or whether a status was promoted correctly — clause 5 and
  evidence-status promotion remain behavioural, and increment 4 is where the latter is
  meant to be addressed.
- **One record has no manifest and is quarantined, not covered.**
  `results/PALACE-VERIFY-20260915T063014Z` carries no `manifest.sha256`, so the verifier
  cannot check it. That is a recorded failure of the run itself — the commit subject
  that created it (`9cf7cb1`) says "campaign step failure, manifest failure" — and it is
  left as executed, because writing a manifest now would alter historical evidence and
  record a digest taken long after the run. Its eight decision-relevant files are pinned
  by content instead, so they are frozen even though their membership has no register.
- **`campaign.sha256` is not a file manifest**, despite its `sha256sum`-like format: it
  records the campaign DEFINITION's digest (`build_campaign().sha256()`) with
  `campaign.json` as a label, which `tests/test_verification.py` asserts. Reading it as a
  file manifest produces a false integrity failure on all four verification campaigns.
- **`master/` and `reference/` are not covered here.** Both are frozen and both have
  their own CI verifiers (`cem verify-master`, `scripts/verify_reference_bundle.py`);
  this increment asserts those steps are still wired into CI rather than duplicating
  them. `verify_reference_bundle.py` does check both directions; `verify-master` was not
  audited for that here.
- **The launch-authority scan is source-level.** It catches a module that names a runtime
  and can exec. It would not catch an argv assembled from fragments at runtime, or an
  exec reached through a helper that hides the subprocess call.
