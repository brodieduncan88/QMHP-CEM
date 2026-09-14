# Palace output FORMAT fixtures

**These files were written by hand to Palace's output layout. They are not
solver output.** They exist so that `solvers/palace/outputs.py` can be tested
without a container, and they prove nothing about execution.

| File | Exercises |
|---|---|
| `eig.csv` | header-driven column matching, `inf` Q, backward and absolute error columns |
| `eig_not_converged.csv` | a release without the absolute-error column, and a mode above tolerance |
| `palace.json` | the `GitTag` metadata path |
| `palace_log.txt` | banner extraction: version, git changeset, MPI count |

The mode frequencies were placed near the golden cavity's closed-form values
so the analytic-comparison note is exercised. The digits are invented.
