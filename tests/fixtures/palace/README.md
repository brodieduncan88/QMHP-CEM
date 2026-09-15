# Palace output FORMAT fixtures

**These files were written by hand to Palace v0.13.0's output layout. They are
not solver output.** They exist so that `solvers/palace/outputs.py` can be
tested without a container, and they prove nothing about execution.

| File | Exercises |
|---|---|
| `eig.csv` | header-driven column matching, `inf` Q, backward and absolute error columns |
| `eig_not_converged.csv` | a mode above the backward-error ceiling; its five-column header is hypothetical (every 0.11–0.13 release writes six columns) and only tests that the absolute-error column is optional |
| `palace.json` | the `GitTag` metadata path; keys follow the real file (`Problem.MPISize`, `MeshElements`, `DegreesOfFreedom`, `ElapsedTime.Durations`) |
| `palace_log.txt` | banner extraction: `Git changeset ID` carries `git describe` output (`v0.13.0` for a tag build, no separate version line), the MPI count, and the stdout eigenvalue table whose "Bkwd. Error" heading must not be mistaken for a diagnostic |

The mode frequencies follow the golden cavity's closed-form spectrum **with
multiplicity**, as an eigensolver counts: `f_110, f_120, f_120, f_220` for a
square box. The digits after the leading ones are invented.
