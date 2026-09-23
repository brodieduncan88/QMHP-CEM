# QMHP-CEM — Claude Code Operating Rules

These rules govern Claude Code work in this repository.
Scientific evidence integrity takes priority over producing a successful-looking result.

`AGENTS.md`, the Shared AI Agent Operating Contract, was adopted as repository policy on
21 September 2026 and applies IN ADDITION to these rules. It is additive: nothing below
is replaced, relaxed or superseded by it, and where both speak to the same subject the
stricter reading governs. The clause-by-clause mapping, and an honest record of which
contract clauses are enforced by a mechanism and which are behavioural only, is in
`docs/agent-contract-implementation.md`. Adopting a policy file installs no control.

## 1. Scientific Evidence Is Append-Only

Historical evidence is immutable.

NEVER:
- modify an executed record to improve its result;
- alter a historical manifest;
- replace solver output after execution;
- change a pre-declared acceptance criterion after seeing the result;
- loosen a tolerance, threshold, budget or admission rule to turn a failure into a pass;
- silently discard an inconvenient result.

Treat committed historical `results/` records and their manifests as read-only.

Corrections must be made through a NEW correction/superseding record that:
- identifies the original claim;
- preserves the original evidence;
- states exactly what was wrong;
- supplies the corrected analysis and provenance.

Permitted scientific outcomes include:

PASS
FAIL
INCONCLUSIVE
UNAVAILABLE
BLOCKED

Never force a definitive conclusion when the evidence does not support one.

## 2. Predeclare Experiments

Before any consequential FEM/solver execution, record:

- question being tested;
- baseline record;
- exact configuration;
- mesh/source/config hashes;
- independent variable;
- controlled variables;
- acceptance/refusal criteria;
- compute budget;
- wall-clock cap;
- permitted number of attempts;
- expected evidence;
- stop conditions.

Do not redesign an experiment after seeing its result unless the first experiment
is preserved and the redesign is separately declared and approved.

## 3. Human Approval Gates

Do not launch a consequential Palace solve, change an approval file, increase a
compute budget, change a registered scientific definition, merge a research
checkpoint, or perform a real-data extraction without explicit human approval.

Approval for one experiment does not imply approval for:
- a retry;
- another refinement;
- another solver configuration;
- another extraction route;
- relaxed criteria;
- a larger compute budget.

If an approved experiment fails or times out, preserve that result and STOP.

## 4. Evidence Before Presentation

Raw evidence must survive even if analysis, rendering or reporting fails.

Where applicable, write and verify:
1. raw solver output;
2. hashes;
3. manifest;
4. record pointer/index;
5. machine-readable summary;
6. human-readable report.

Presentation failure must never destroy completed scientific evidence.

## 5. Provenance Must Fail Closed

Never report an expected hash as though it were a measured hash.

For evidence-bearing executions, verify actual inputs where applicable:
- source commit;
- source-register digest;
- configuration;
- mesh;
- patch;
- container/image;
- scripts;
- solver version;
- dependencies.

Missing or mismatched required provenance makes the result UNQUALIFIED until resolved.

Do not silently substitute a similar file, branch, artefact or solver version.

## 6. Source-Bound Claims

When a conclusion depends on Palace, MFEM, Gmsh or another dependency:

- pin the exact version/commit;
- cite the exact implementation used;
- distinguish source-derived facts from assumptions;
- distinguish upstream behaviour from QMHP modifications.

If a registered source digest changes, fail closed until the change is explicitly reviewed.

## 7. Adversarial Verification

For consequential new mathematics or numerical methods:

- independently derive the result where practical;
- create synthetic known-answer tests;
- construct negative controls/counterexamples;
- test refusal paths;
- distinguish identities from numerical approximations;
- distinguish measured quantities from derived quantities;
- distinguish correlation from causal attribution.

Do not treat agreement between two calculations sharing the same assumptions or
inputs as fully independent confirmation.

### 7.1 Verification targets an immutable SHA

**Adversarial verification must target an immutable pre-fix SHA. Verification against a
mutable or already-fixed working tree is invalid evidence.**

Consequences of that rule:

- Record the pre-fix commit SHA BEFORE changing anything, and verify against a frozen
  snapshot or worktree at that SHA.
- A finding is REFUTED only by demonstrating that the claimed defect does not exist on
  that snapshot. "Already fixed in current code", "handled elsewhere", inability to
  reproduce, and uncertainty are NOT refutations. Record such findings UNRESOLVED.
- Keep pre-fix defect reproduction and post-fix regression proof separate. They are
  different claims and neither substitutes for the other.
- Report the snapshot SHA, the reproduced mechanism and the exact positive and negative
  controls. Reviewer counts are not evidence.

## 8. Numerical Integrity

Never:
- hide solver warnings;
- discard inconvenient eigenmodes without a predeclared rule;
- choose modes solely because their frequencies match expectations unless that
  criterion was predeclared;
- call a residual an error bound without deriving the bound;
- claim convergence from insufficient refinement evidence;
- convert a sensitivity study into an uncertainty bound without justification.

Report numerical precision separately from physical/model uncertainty.

## 9. Git Safety

NEVER:
- force-push;
- rewrite evidence-bearing history;
- delete evidence tags/records to clean up history;
- squash away executed scientific provenance unless explicitly authorised and
  the evidence remains independently immutable.

Before committing:
- inspect the diff;
- run relevant guards/tests;
- run secret scanning;
- verify no unexpected generated files are staged.

Before pushing:
- identify workflows the changed paths will trigger.

Do not trigger an expensive solver workflow accidentally.

## 10. Secrets and Sensitive Information

Never commit:
- API keys;
- access tokens;
- passwords;
- private credentials;
- `.env` secrets;
- private customer information;
- private endpoints containing credentials.

Run the repository's approved secret scanner before evidence-bearing pushes.

Never print secrets into logs or evidence records.

## 11. Generated and Binary Artefacts

Generated/binary artefacts are denied by default.

They may be committed only when:
- the evidence policy explicitly permits that file class;
- the file is necessary for reproducibility/auditability;
- its size is acceptable;
- it is hash-bound and manifested.

Otherwise store large solver fields/meshes as immutable workflow/release evidence
and keep their hashes and provenance in Git.

Do not assume every `.msh`, `.vtu`, field archive or solver output belongs in Git.

## 12. Licensing and Intellectual Property

Do not automatically claim ownership of third-party-derived files.

Before creating/modifying a file, classify it as:
- proprietary QMHP-CEM work;
- third-party code;
- modification/patch of third-party code;
- generated evidence;
- documentation/data with separate provenance.

Preserve all required upstream copyright and licence notices.

For genuinely new proprietary QMHP-CEM source files, use the project's approved
copyright header.

Never add or redistribute a new third-party dependency without:
- identifying the exact package/version;
- identifying its licence;
- recording how it is used/distributed;
- obtaining explicit approval when licensing implications are unclear or material.

Do not make legal conclusions about licence compatibility. Flag them for human/legal review.

## 13. Diagnostic Isolation

Experimental diagnostics must be default-off and isolated from the validated
production solver path wherever practical.

Adding a diagnostic must not silently change ordinary Palace/QMHP execution.

Regression testing must determine what is expected to be:
- byte-identical;
- structurally identical;
- numerically equivalent within a justified tolerance.

Do not demand byte identity for floating-point results when platform/library
round-off legitimately prevents it.

## 14. Model Behaviour

Do not optimise for agreement with the user's expected result.

If evidence contradicts a prior Claude, ChatGPT or human interpretation:
report the contradiction.

Never describe:
- a proposed calculation as executed;
- an externally supplied result as independently reproduced;
- an inaccessible artefact as inspected;
- a test as passed before it finishes;
- elapsed time based on guessed or stale monitoring data.

When uncertain, say exactly what is known, unknown and required to resolve it.

## 15. Scope Control

Perform only the approved task.

Do not broaden a bounded task into:
- unrelated refactoring;
- additional FEM solves;
- additional research campaigns;
- parameter sweeps;
- speculative physics work;
- PR merges.

If an unexpected issue materially affects the requested task, report it before
expanding scope.

## 16. End-of-Task Report

For consequential work, report:

- commit SHA;
- files changed;
- tests executed and results;
- workflows triggered;
- experiments executed;
- evidence records created;
- corrections/retractions;
- unresolved blockers;
- what is explicitly NOT established;
- whether further action requires human approval.
