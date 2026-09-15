# Palace execution path (v0.2)

Palace is the sole primary EM solver for this milestone. This document says
what the path does, what it records, how to run the proof, and what it does
**not** yet claim.

**Status first: genuine Palace runs have been executed and are committed.**
Two records so far: `results/PALACE-GOLDEN-20260915T014639Z/` (GitHub Actions
run 34918498363 on commit b79a170) and `results/PALACE-GOLDEN-20260915T015804Z/`
(run 34919265099 on 25089ae), both Palace v0.13.0 at commit a61c8cbe, image
ID `sha256:cc87ec6b…`, one MPI process, 40.4 s and 40.2 s inside Palace, and
byte-identical in every solver output. All four requested modes of the empty
Object 001 box converged (max backward error 2.0e-11 against 1e-6) and agree
with the closed form to within 4.7e-5 relative. Any later change to the
Palace path re-runs the workflow and appends another record. The last
section has the numbers; the records have everything else.

## What is solved

The **empty vacuum cavity of Object 001** as a closed perfect-electric-conductor
box, derived from the candidate's `ENGINEERING-SEED` dimensions in the spec §7.3
frame:

| Axis | Extent | Source |
|---|---|---|
| X | −11.0 … +11.0 mm | `vacuum_cavity.width_mm` = 22, centred |
| Y | −11.0 … +11.0 mm | `vacuum_cavity.height_mm` = 22, centred |
| Z | 0 … 1.5 mm | chip top surface (origin) to lid underside, `height_above_chip_mm` |

The chip dielectric, the recess step, the two launch bores and the lid body are
**not modelled**. That is deliberate. The empty box has a closed-form spectrum,
so the very first Palace calculation can be checked against numbers the
solver did not produce:

```
f_mnp = (c/2) · sqrt((m/a)² + (n/b)² + (p/d)²)      at most one zero index
f_110 = 9.6357 GHz            a = b = 22 mm
f_120 = f_210 = 15.2354 GHz   degenerate pair for the square box
f_220 = 19.2714 GHz
```

The four modes Palace is asked for are all TM_mn0: their frequencies do not
depend on the 1.5 mm cavity height at all. The check therefore verifies the
X/Y extent, the mm→m unit scaling (`L0`) and the vacuum material. It is blind
to the Z extent, and says so in the run record.

`solvers/palace/analytic.py` computes the spectrum with multiplicities;
`solvers/palace/config.py` turns it into the list of modes the solver should
report, repeats included, and the run record carries the comparison.

Two numbers govern the comparison, both `ENGINEERING-RULE`s in
`solvers/palace/config.py`:

| Rule | Value | Meaning |
|---|---|---|
| `GOLDEN_RELATIVE_TOLERANCE` | 2 % | Proof gate for the execution path. Catches a wrong box, unit or material; the harness exits 4 above it |
| `SOLVER_RULES["expected_relative_deviation"]` | 1e-4 | What order-2 elements on the mesh rule `min(a, b)/12` should achieve. Above it the harness prints a warning and records it; the exit code does not change |

Neither is a validation gate and neither says anything about the physical
package.

## The boundary (spec §10.1), preserved

| Step | `PalaceSolver` | Needs |
|---|---|---|
| `preflight()` | mesher importable → runtime on PATH → daemon reachable (and whether it is rootless) → image present → a container from the image runs and reports its own `PALACE_VERSION` / `PALACE_COMMIT` | docker |
| `prepare()` | resolve the work directory, derive the domain, mesh it with gmsh (MSH 2.2 ASCII, physical groups `vacuum`=1, `pec`=2), write `config.json`, hash both, compute the analytic reference | gmsh only |
| `run()` | the command below; capture the log; write `palace_run.json` on every outcome | docker + image |
| `parse()` | read `postpro/eig.csv`, `postpro/palace.json`, the log; hash every artifact; build `SolverResults` | nothing |
| `validate_convergence()` | inherited; rejects anything not `CONVERGED` | nothing |

The command `run()` executes, verbatim in every run record:

```
docker run --rm --network none --hostname localhost \
    --name qmhp-palace-<run_id>-<candidate_id> \
    --user <uid>:<gid> -e HOME=/tmp -v <work_dir>:/work -w /work \
    qmhp-cem/palace:0.13.0 -np <N> config.json
```

The hostname is pinned because Open MPI resolves the local hostname at
start-up, and with no network the only name guaranteed to resolve inside the
container is `localhost`.

`--user` is omitted when the daemon is rootless (the caller already owns the
mounted files) or when the adapter is constructed with `user=None`. The
container is named so that a run which exceeds the timeout can be killed by
name: `subprocess` only kills the CLI, not the container it started.

`prepare()` works on a machine without Docker, so an input can be generated
and inspected anywhere. `run()` refuses without the container and raises
`SolverUnavailable` naming the remedy. A run that starts and then fails, times
out, or cannot be started raises `PalaceRunFailed` **after** writing the log
and the run record. Nothing falls back to the mock (spec §10.5); the
orchestrator records any solver exception on the candidate as `INCOMPLETE`
with its type and message, and never retries with another solver.

## What is recorded (spec §10.3, §13.3)

| Field | Where |
|---|---|
| Palace version and git commit | image files `/opt/palace/PALACE_VERSION`, `PALACE_COMMIT` read by preflight; else image labels; else `palace.json` `GitTag`; else the log banner `Git changeset ID`. A result with none is refused |
| Container image identity | `docker image inspect` ID (content-addressed) and registry digest where one exists; the batch environment record carries `image@id` |
| Command line | verbatim, shell-quoted, in `SolverResults.solver.command_line` and `palace_run.json` |
| Input hashes | candidate canonical JSON, `mesh.msh`, `config.json` |
| Output hashes | every file under `postpro/`, the log, the run record; also as `SolverResults.artifacts` with roles, paths relative to the work directory |
| Convergence | see below |
| Mesh | node and tetrahedron counts, gmsh version, characteristic length, hash |
| Adapter rules | `SOLVER_RULES` in `solvers/palace/config.py`, copied into every `solver_input.json` and `palace_run.json` |

Convergence has two layers, and the record names both. Palace's own stopping
criterion is `Solver.Eigenmode.Tol` (1e-6): the SLEPc eigensolver iterates
until every requested mode meets it, and a mode's presence in `eig.csv` is
Palace's statement that it did. On top of that the adapter reports
`eigenmode_backward_error_max`, the maximum of the a-posteriori backward
errors Palace writes per mode, against the adapter rule
`eigenmode_backward_error_max_tolerance` (also 1e-6). That is the figure in
`SolverResults.convergence`. Palace's reference cavity example shows backward
errors well below `Tol`, so the adapter rule is not expected to bind; if it
does, the result is `NOT_CONVERGED` and `validate_convergence()` refuses it.

Both layers measure how well the eigensolver converged on the mesh it was
given. Neither measures mesh convergence; that campaign is deferred (spec §15).

## Running the proof

```bash
# 1. Build the image (once). Needs outbound HTTPS to archive.ubuntu.com,
#    snapshot.ubuntu.com, github.com and gitlab.com. Expect a long build:
#    Palace's superbuild compiles MFEM, hypre, PETSc/SLEPc and the rest.
docker build -f docker/palace.Dockerfile -t qmhp-cem/palace:0.13.0 .

# 2. Install the mesher.
uv sync --extra palace            # plus: apt-get install libglu1-mesa (Linux)

# 3. Run the golden candidate.
uv run python scripts/palace_golden_run.py
```

Exit codes: `0` converged and every requested mode within the golden
tolerance; `2` Palace cannot execute here (nothing is substituted); `3` ran
but failed, did not converge, or its output could not be parsed; `4` converged
but a mode disagrees with the closed form; `5` golden digest mismatch; `6`
Palace succeeded but the quantum/gate evaluation of its result raised.

After a successful solve the harness takes the result through the same
quantum-device layer and gate evaluation the sweep uses, and writes
`quantum_results.json` and `gate_report.json` next to the candidate. A gate
verdict on the empty box describes the empty box.

The same thing runs unattended in GitHub Actions
(`.github/workflows/palace-golden.yml`): it builds the image with a layer
cache, runs the golden candidate, prints the execution record, gate report
and Palace log into the job log, uploads everything as an artifact, and
commits `results/PALACE-GOLDEN-<UTC>/` back to the branch whatever the
outcome. It is not part of default CI (spec §12.8).

The run writes:

```
results/PALACE-GOLDEN-<UTC>/
├── QMHP-CEM-A-RF-000001/
│   ├── candidate.json
│   └── solver/
│       ├── mesh.msh  config.json  solver_input.json
│       ├── palace_log.txt  palace_run.json  solver_results.json
│       └── postpro/  (eig.csv, domain-E.csv, palace.json, …)
├── execution_record.json
└── manifest.sha256
```

The same adapter is also wired to run under `uv run cem sweep
sweeps/object001_grid.yaml --solver palace`. That is nine eigenmode solves of
nine empty boxes; this milestone does not optimise or expand it. It ran once,
as the last step of the golden-run job, and its output is a workflow artifact
rather than a committed record. In such a sweep the gates needing
S-parameters report `INCOMPLETE` honestly because an eigenmode run produces
none, and a `P4PRE_SPECTRAL` verdict computed from empty-box eigenmodes
describes the empty box, not the package: the chip, recess, launches and lid
that would move those modes are not in the model.

## Reproducibility of the image

`docker/palace.Dockerfile` pins, by default:

- the base by **content digest**, not tag;
- the Ubuntu **package snapshot** (`APT_SNAPSHOT`, via `APT::Snapshot`, on
  both `update` and `install`), with a build-time check that apt really
  resolved the snapshot; `ca-certificates` and its dependency `openssl` are
  the two packages installed from the live archive, because the snapshot
  host is HTTPS-only and the base image has no CA bundle (neither is linked
  by the Palace binary);
- the **Palace release tag**, asserted to resolve to the commit
  `a61c8cbe0cacf496cde3c62e93085fae0d6299ac`, so a moved tag fails the build;
- Palace's own dependencies at the revisions its superbuild pins for that tag.

The build inputs are therefore fixed. The resulting binaries are not
guaranteed bit-identical across builds (timestamps, build paths and compiler
nondeterminism are not controlled), which is why the adapter records the ID
and digest of the image it actually ran rather than the Dockerfile's hash.
The image records what it contains, and the build fails, rather than the
first run, if the copied binary is missing a shared library or the launcher
cannot start.

The image was first built in GitHub Actions run 34917157266 (818 s for the
superbuild on a 4-vCPU hosted runner; a cached rebuild takes under two
minutes). The first attempt failed linking libCEED: Palace hands `CC`
through to libCEED's Makefile, which detects the compiler vendor from
`$CC --version`, and Ubuntu's `cc` does not say "gcc", so `-fPIC` was
dropped. The Dockerfile now names gcc explicitly, as Palace's own CI does.

## Status of the proof in this repository

**Executed.** `results/PALACE-GOLDEN-20260915T014639Z/` is the first real
run, committed by the workflow (commit 878cd8a) from GitHub Actions run
34918498363 on b79a170. What it records:

| Item | Value |
|---|---|
| Solver | Palace 0.13.0, git changeset `v0.13.0`, commit `a61c8cbe0cacf496cde3c62e93085fae0d6299ac` |
| Image | `qmhp-cem/palace:0.13.0`, ID `sha256:cc87ec6b397ec4e55b19984b112e1638d15dd3f18bd3cf9a3b594019ec474265`, no registry digest (built on the runner) |
| Command | `docker run --rm --network none --hostname localhost --name qmhp-palace-… --user 1001:1001 -e HOME=/tmp -v …/solver:/work -w /work qmhp-cem/palace:0.13.0 -np 1 config.json` |
| Mesh | gmsh 4.15.2, 1200 tetrahedra, 443 nodes, lc 1.8333 mm, sha256 `7602c8c3…` |
| Config | sha256 `8f4675f0…`; order 2, 9848 degrees of freedom |
| Convergence | SLEPc `CONVERGED_TOL`, 4 eigenpairs; max backward error 2.02e-11 against the 1e-6 rule |
| Modes (GHz) | 9.635896, 15.235451, 15.235704, 19.272299 |
| Closed form (GHz) | 9.635695, 15.235371, 15.235371, 19.271389 |
| Relative deviation | 2.1e-5, 5.3e-6, 2.2e-5, 4.7e-5 (all within the 1e-4 expected and the 2 % gate) |
| Wall time | 40.4 s in Palace; 43 s end to end |
| Gates | overall `INCOMPLETE`: `COLLISION` PASS, `P4PRE_SPECTRAL` PASS, `P6E2_FILTER` INCOMPLETE (no S21), `COUPLING_EXTRACTION` and `TOLERANCE` NOT-EVALUATED, six hardware gates HARDWARE-GATED |

`results/PALACE-GOLDEN-20260915T015804Z/` (run 34919265099 on 25089ae,
commit c16567a) repeated the run from the cached image: the same image ID,
the same mesh and config hashes, byte-identical `eig.csv` and
`domain-E.csv`, identical gate verdicts; only the timestamps and the wall
time (40.2 s in Palace) differ.

The two PASS verdicts describe the empty box, which has no mode below 9.6 GHz
and therefore nothing near the 4.30 GHz readout root: they say the pipeline
runs, not that the package is right. The 3x3 sweep also ran in the same job
(nine Palace solves, six minutes, every candidate `INCOMPLETE` for the same
reason: no S-parameters, so `COUPLING_EXTRACTION` cannot close); it was
uploaded as a workflow artifact and not committed.

Two workflow runs failed before this one, both on the image, neither on
Palace: run 34916148077 (libCEED without `-fPIC`, above) and run 34917157266
(the image built, then `docker image inspect --format` rejected the
`join` template on an image with no registry digest; the adapter now reads
`RepoDigests` as JSON).

What is tested, in default CI, without a container:

- the analytic reference, including the square-box degeneracy;
- the domain derivation and the config document;
- the mesher, live: gmsh imports (CI asserts it), meshes the domain, and
  produces the same hash twice;
- the parsers, on hand-authored fixtures in Palace v0.13.0's output format;
- `prepare()`, and the run record it feeds;
- `preflight()` and `run()` against a scripted fake `docker` CLI: the exact
  argv, the `--user` and rootless handling, the identity probe, a non-zero
  exit, a timeout (with the container kill), a runtime that cannot start, a
  symlinked work directory, and the no-fallback guarantees;
- the orchestrator's handling of an unavailable solver (batch refused) and a
  solver that fails mid-sweep (candidate `INCOMPLETE`, cause recorded).

Palace itself is exercised only in the golden-run workflow: the
real-execution test is marked `palace`, ran there against the live container
(1 passed), and skips with the reason wherever the container is absent. The
fixtures under `tests/fixtures/palace/` are format fixtures and are not
evidence of a run; the evidence is the committed record.
