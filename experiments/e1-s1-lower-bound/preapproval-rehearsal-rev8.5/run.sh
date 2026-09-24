#!/bin/bash
# The pre-approval rehearsal, revision 8.5, exactly as predeclared in PREDECLARATION.md next to this
# file: part 1, one run of the driver's rehearsal mode; part 2, one run of the contract section 5
# rehearsal test (the same rehearsal with a spy on matrix assembly). No retry; stop at the first failure.
set -u
cd /home/user/QMHP-CEM
S=/tmp/claude-0/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988/scratchpad/next/e1/r87/rehearsal
mkdir -p $S
TIMEFORMAT='real_s=%R user_s=%U sys_s=%S'
TEST="tests/test_e1_s1_lower_bound.py::test_the_rehearsal_runs_the_real_controls_and_the_S1_geometry_phase_and_assembles_nothing_on_S1"
rec=$S/run-driver.record
{
  echo "part=1 driver --rehearsal"
  echo "start_utc=$(date -u +%FT%TZ)"
  echo "head=$(git rev-parse HEAD)"
  echo "git_status_porcelain_lines=$(git status --porcelain | wc -l)"
  echo "loadavg_before=$(cat /proc/loadavg)"
  echo "invocation=env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 1260 .venv/bin/python experiments/e1-s1-lower-bound/driver.py --rehearsal --out $S/rehearsal.json"
} > $rec
{ time env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 1260 .venv/bin/python experiments/e1-s1-lower-bound/driver.py --rehearsal --out $S/rehearsal.json > $S/stdout-driver.log 2> $S/stderr-driver.log ; } 2> $S/time-driver.txt
rc=$?
{
  echo "exit_code=$rc"
  echo "end_utc=$(date -u +%FT%TZ)"
  echo "loadavg_after=$(cat /proc/loadavg)"
  echo "git_status_porcelain_lines_after=$(git status --porcelain | wc -l)"
} >> $rec
if [ $rc -ne 0 ]; then echo "STOP: part 1 exited $rc (predeclared: no retry; part 2 not run)" >> $rec; echo "all_done_utc=$(date -u +%FT%TZ)" > $S/DONE; exit 0; fi
rec=$S/run-test.record
{
  echo "part=2 contract section 5 rehearsal test"
  echo "start_utc=$(date -u +%FT%TZ)"
  echo "head=$(git rev-parse HEAD)"
  echo "git_status_porcelain_lines=$(git status --porcelain | wc -l)"
  echo "loadavg_before=$(cat /proc/loadavg)"
  echo "invocation=env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 timeout --signal=KILL 1260 .venv/bin/python -m pytest -p no:cacheprovider -rA -v --basetemp $S/pytest-tmp $TEST"
} > $rec
{ time env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 timeout --signal=KILL 1260 .venv/bin/python -m pytest -p no:cacheprovider -rA -v --basetemp $S/pytest-tmp $TEST > $S/stdout-test.log 2> $S/stderr-test.log ; } 2> $S/time-test.txt
rc=$?
{
  echo "exit_code=$rc"
  echo "end_utc=$(date -u +%FT%TZ)"
  echo "loadavg_after=$(cat /proc/loadavg)"
  echo "git_status_porcelain_lines_after=$(git status --porcelain | wc -l)"
} >> $rec
if [ $rc -ne 0 ]; then echo "STOP: part 2 exited $rc (predeclared: no retry)" >> $rec; fi
echo "all_done_utc=$(date -u +%FT%TZ)" > $S/DONE
