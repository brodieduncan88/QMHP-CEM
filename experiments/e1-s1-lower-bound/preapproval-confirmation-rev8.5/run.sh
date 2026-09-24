#!/bin/bash
# The two pre-approval Confirmation runs, exactly as predeclared at ca19ece (one per mode, no retry, stop at the first failure).
set -u
cd /home/user/QMHP-CEM
S=/tmp/claude-0/-home-user-QMHP-CEM/7e301b81-9cc3-5878-8c8a-f1390dcdb988/scratchpad/next/e1/r86
for mode in nominal forced; do
  rec=$S/run-$mode.record
  {
    echo "mode=$mode"
    echo "start_utc=$(date -u +%FT%TZ)"
    echo "head=$(git rev-parse HEAD)"
    echo "git_status_porcelain_lines=$(git status --porcelain | wc -l)"
    echo "loadavg_before=$(cat /proc/loadavg)"
    echo "invocation=env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 1260 .venv/bin/python experiments/e1-s1-lower-bound/driver.py --confirmation $mode --out $S/confirmation-$mode.json"
  } > $rec
  env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout --signal=KILL 1260 .venv/bin/python experiments/e1-s1-lower-bound/driver.py --confirmation $mode --out $S/confirmation-$mode.json > $S/stdout-$mode.log 2> $S/stderr-$mode.log
  rc=$?
  {
    echo "exit_code=$rc"
    echo "end_utc=$(date -u +%FT%TZ)"
    echo "loadavg_after=$(cat /proc/loadavg)"
    echo "git_status_porcelain_lines_after=$(git status --porcelain | wc -l)"
  } >> $rec
  if [ $rc -ne 0 ]; then echo "STOP: $mode exited $rc (predeclared: no retry)" >> $rec; break; fi
done
echo "all_done_utc=$(date -u +%FT%TZ)" > $S/DONE
