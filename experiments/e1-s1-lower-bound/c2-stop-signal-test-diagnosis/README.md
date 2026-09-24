# C-2 stop-signal test: diagnosis and deterministic replacement

Prepared 2026-09-24, on a human instruction to resolve the intermittent C-2 test before E1 approval. **Verdict: the defect was in the test's timing, not in the implementation.** The driver and every other E1 code file are unchanged. Only `tests/test_e1_s1_lower_bound.py` changes: the wall-clock test is replaced by deterministic tests with a positive and a negative control.

## 1. The symptom

- **The test.** `test_a_stop_signal_pending_when_a_C_level_exception_propagates_still_leaves_a_sealed_record[0.8]`, the 0.8 case of the old test, failed intermittently on this host.
- **What the old test did.**
  - It timed one `zlib.decompress` of a corrupt 200 MB stream.
  - It armed `ITIMER_REAL` at 0.2, 0.5 or 0.8 of that time.
  - It ran the same call again inside the attempt. The call raises `zlib.error` from C.
  - It asserted exit 3, `failure.json` with the zlib error, `signals_received == ["SIGALRM"]`, `provenance.json` and a verified manifest.
- **In failing runs.**
  - Exit 3 and the zlib error were there.
  - `signals_received` was empty, so the manifest assertion on the next line was not reached.
  - CI runs 256–260 (commits `0b48928` to `b0fec36`) passed.
- **Author's account.** The intermittent failures were first seen earlier in this session and reported to the human with the pre-approval evidence. Their raw outputs were not kept. The reproduction below is the stored one.

## 2. Pre-fix snapshot and method

- **Snapshot.** Commit `b0fec36515016946c6225e2a18d5cd6379439fa2`, in a read-only worktree. It was recorded before anything changed (CLAUDE.md §7.1).
- **Script.** [`diag_timing.py`](diag_timing.py) runs the old test's child process unchanged, with one addition. A proxy of the `signal` module, installed on the driver, records how much `ITIMER_REAL` time remains each time the driver calls `signal.alarm`. The last such call is `_disarm`'s `alarm(0)` in the failure path.
- **Classes.** Each run was classed as:
  - **A:** SIGALRM recorded; the timer had expired before the disarm.
  - **B:** nothing recorded; the timer had NOT expired at the disarm, so `alarm(0)` cancelled it.
  - **C:** nothing recorded although the timer had expired. This would be a lost signal, i.e. an implementation defect.
  - **D:** anything else.
- **Runs.** 30 runs at each of 0.8, 0.5 and 0.2, one at a time, on Python 3.11.15, Linux 6.18 with 4 CPUs. Raw rows: [`timing-rows-b0fec36.jsonl`](timing-rows-b0fec36.jsonl).

## 3. Results on the pre-fix snapshot

| fraction | A | B | C | D |
|---|---|---|---|---|
| 0.8 | 25 | 5 | 0 | 0 |
| 0.5 | 30 | 0 | 0 | 0 |
| 0.2 | 30 | 0 | 0 | 0 |

- **Every one of the 90 runs:** exit 3, the zlib error in `failure.json`, and a verified manifest.
- **The five B runs.**
  - The timer (0.197–0.875 s) was longer than the time from arming it to the driver's disarm (0.181–0.278 s).
  - At the disarm it had 0.004–0.597 s left.
  - The first, calibrating call took 0.247–1.094 s in these runs, against 0.179–0.218 s in the A runs at 0.8.
- **The A runs at 0.8.** In every one of them the timer was shorter than that elapsed time.
- **Mechanism.** When the calibrating call is a slow outlier, 0.8 of it is longer than the second call. The timer then has not expired when the second call raises. The failure path's `_disarm` cancels it (`signal.alarm(0)`), as designed. No signal arrived during the attempt, so correctly none is recorded. The old test's premise ("the signal lands inside the call on any host") did not hold.
- **Not determined.** Why the calibrating call is sometimes slow. Four of the five B runs were the first four runs of the series.
- **Implementation verdict.** No lost signal (class C) in 90 runs. The deterministic tests below also pass on this unchanged code (§5). No implementation defect was found for C-2.

## 4. The replacement test

- **The C-level chain.** The stop signal is delivered inside one C-level call: `list(map(operator.call, [arm, functools.partial(zlib.decompress, bad)]))`.
  - `map`, `operator.call`, `functools.partial` and `zlib.decompress` are all C.
  - So no bytecode runs between the signal and the C-level exception, and no Python signal handler can run before the exception reaches Python code.
  - Where the signal lands is therefore fixed by construction, not by a wall-clock race.
- **Two delivery routes** (`_C2_CASES`):
  - **`interrupt_main`, for each of the five stop signals.** `_thread.interrupt_main(sig)` trips the signal through the same `trip_signal` routine as CPython's C-level signal handler. It involves no timing at all.
  - **`itimer`, SIGALRM only.** A real SIGALRM from a 1 ms `ITIMER_REAL`, armed inside the same chain, ahead of a 200 MB inflate. The only assumption is that inflating 200 MB takes longer than 1 ms plus a scheduler tick. The positive control checks this: the timer has expired by the time the exception reaches Python.
- **Positive control** (`test_the_C2_call_chain_leaves_the_stop_signal_pending_until_the_next_call`, without the driver). When the exception reaches Python code, the handler has not run. It runs at the next call.
- **The C-2 test** (`test_a_stop_signal_pending_when_a_C_level_exception_propagates_still_leaves_a_sealed_record`, 6 cases).
  - Its assertions are the old ones, not weakened: exit 3, `failure.json` with the C-level error and the signal, `provenance.json` and a verified manifest.
  - They now apply to all five stop signals, where the old test covered SIGALRM only.
- **Negative control** (`test_the_C2_test_fails_when_the_handler_raises_in_the_failure_path`). With a handler that raises even after the failure path has begun (the defect C-2 guards against), the same chain leaves no `failure.json` and no valid manifest.
- **Routes not used.** [`delivery_probe.py`](delivery_probe.py) (run as `witness.py`) tried three routes:
  - `os.kill` to self in Python 3.11.15 runs the handler before it returns, so it cannot leave a signal pending.
  - libc `raise` through ctypes inside the chain never ran the handler in that probe, neither at the `except` nor after the next call. The reason was not investigated.
  - Neither route is used.

## 5. Evidence that the tests are deterministic and discriminating

[`determinism_and_mutations.py`](determinism_and_mutations.py) ran on the pre-fix snapshot; its output is in [`determinism-and-mutations.log`](determinism-and-mutations.log).

- **Repetitions.** [`prototype_run_against_b0fec36.py`](prototype_run_against_b0fec36.py) holds the 13 tests. The block between its markers is byte-identical to the block now in the repository test file. Results:
  - 20 plain repetitions: 13 of 13 passed each time.
  - 5 repetitions with a busy loop on each of the 4 CPUs: 13 of 13 each time.
- **Mutations.** The repository's new test file was run in git worktrees of the pre-fix snapshot:

  | driver | result |
  |---|---|
  | unmutated (M0) | 13 of 13 pass |
  | M1: the handler raises even while stopping | all 6 driver-level cases fail |
  | M2: `failure.json` drops the received signals | all 6 driver-level cases fail |
  | M3: `stopping` is set only after `_shutdown()` | all 6 driver-level cases fail |

  In M1–M3 the positive and negative controls pass, as designed.
- **Harness bug on the first execution.** The first execution of that script lacked the line `SCRATCH.mkdir(parents=True, exist_ok=False)`.
  - pytest could not create its temporary directory, so the 7 tests that need one errored in the 25 repetitions. The mutation part ran normally.
  - Its output is kept in [`determinism-and-mutations.harness-bug.log`](determinism-and-mutations.harness-bug.log).
  - The corrected script was then re-run in full.
- **After the change, in the repository.**
  - The fast E1 suite: 310 passed, 2 skipped (the opt-in Confirmation tests), 2 deselected (slow).
  - The 13 C-2 tests: 5 repetitions, 13 of 13 each time.

## 6. Files

Every file in this directory is stored byte for byte as executed, or as written by the run. The scripts carry no copyright header, so that the stored bytes equal the executed ones. They are QMHP-CEM work. [`MANIFEST.sha256`](MANIFEST.sha256) covers every file here except itself.
