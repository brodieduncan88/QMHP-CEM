# Palace dispatch predeclarations

`palace-golden.yml` and `palace-verify.yml` run only on manual dispatch, and
only after `scripts/palace_dispatch_gate.py` accepts the dispatch against a
JSON predeclaration committed in this directory (`CLAUDE.md` sections 2 and 3).

## How a run is authorised

1. Commit the declaration as the **only** change on top of the code you want
   run (`code_commit`). The gate refuses a commit that differs from
   `code_commit` anywhere outside this directory.
2. The owner approves it, and the place of that approval is recorded as
   `approval_ref` (for example a PR review URL or a dated decision record).
3. Dispatch the workflow on that commit with `expected_sha` set to the full
   hash of the commit containing the declaration, `declaration_ref` set to
   its path, `approval_ref` exactly as declared, and every other input exactly
   as declared.
4. The solving job then waits on the protected `palace-solver` environment.
   Its required reviewer is the human approval of this specific run.

The gate checks consistency only. It does not judge the declaration, does not
record the approval, and does not count attempts: a second dispatch of the same
declaration is not refused mechanically, so `budget.attempts` is a declared
limit, not an enforced one.

## Schema `qmhp-cem.palace-dispatch-declaration/1`

Exactly these keys:

| key | type | meaning |
|---|---|---|
| `schema` | string | `qmhp-cem.palace-dispatch-declaration/1` |
| `workflow` | string | `palace-golden` or `palace-verify` |
| `code_commit` | string | full hash of the code being run |
| `question` | string | the question being tested |
| `baseline_record` | string | the record it is compared with, or `none` with a reason |
| `independent_variable` | string | what is varied |
| `controlled_variables` | list of strings | what is held fixed |
| `inputs` | object | every dispatch input other than `expected_sha`, `declaration_ref` and `approval_ref`, with the same JSON types (booleans stay booleans) |
| `approval_ref` | string | where the owner approved it |
| `budget` | object | `{"timeout_minutes": <1..job cap>, "attempts": 1}`; the caps are 360 (golden) and 350 (verify) |
| `acceptance_criteria` | list of strings | fixed before the run |
| `stop_conditions` | list of strings | fixed before the run |
| `expected_evidence` | list of strings | what the run must leave behind |

A failed or timed-out approved run is preserved and stops there. A retry, a
refinement or another configuration needs its own declaration and approval.
