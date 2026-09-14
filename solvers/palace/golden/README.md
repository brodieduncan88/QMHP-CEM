# Palace golden candidate

`QMHP-CEM-A-RF-000001.json` is the Object 001 seed candidate (spec §7.5,
`config/object001_seed.yaml`) frozen in canonical JSON. `GOLDEN.sha256` is its
digest, and `tests/test_palace.py` asserts the two agree, so the golden input
cannot drift without a deliberate, reviewed change to both files.

It is the single input for the first real Palace execution
(`scripts/palace_golden_run.py`). Every dimension in it is `ENGINEERING-SEED`.

The solver domain derived from it is the empty vacuum cavity, a closed PEC
box of 22 × 22 × 1.5 mm in the spec §7.3 frame, whose closed-form fundamental
is 9.6357 GHz (`solvers/palace/analytic.py`). That number is the check on the
run, and it is not a QMHP requirement.
