# Palace execution path (v0.2)

Palace is the sole primary EM solver for this milestone. This document says
what the path does, what it records, how to run the proof, and what it does
**not** yet claim.

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
so the very first Palace calculation can be checked against a number the
solver did not produce:

```
f_mnp = (c/2) · sqrt((m/a)² + (n/b)² + (p/d)²)
f_110 = 9.6357 GHz   for a = b = 22 mm, d = 1.5 mm
```

`solvers/palace/analytic.py` computes this; the run record carries the
comparison. A first-mesh agreement within 2 % (`GOLDEN_RELATIVE_TOLERANCE` in
the harness) is the proof criterion for the execution path. It is not a
validation gate and it says nothing about the physical package.

## The boundary (spec §10.1), preserved

| Step | `PalaceSolver` | Needs |
|---|---|---|
| `preflight()` | mesher importable → runtime on PATH → daemon reachable → image present → read the image's own `PALACE_VERSION` / `PALACE_COMMIT` | docker |
| `prepare()` | derive the domain, mesh it with gmsh (MSH 2.2 ASCII, physical groups `vacuum`=1, `pec`=2), write `config.json`, hash both, compute the analytic reference | gmsh only |
| `run()` | `docker run --rm --network none --user uid:gid -v work:/work -w /work IMAGE -np N config.json`, capture the log, write `palace_run.json` | docker + image |
| `parse()` | read `postpro/eig.csv`, `postpro/palace.json`, the log; hash every artifact; build `SolverResults` | nothing |
| `validate_convergence()` | inherited; rejects anything not `CONVERGED` | nothing |

`prepare()` works on a machine without Docker, so an input can be generated
and inspected anywhere. `run()` refuses without the container and raises
`SolverUnavailable` naming the remedy. Nothing falls back to the mock (spec §10.5).

## What is recorded (spec §10.3, §13.3)

| Field | Where |
|---|---|
| Palace version and git commit | image files `/opt/palace/PALACE_VERSION`, `PALACE_COMMIT`; `palace.json` `GitTag`; log banner — the first available wins, and a result with none is refused |
| Container image identity | `docker image inspect` ID (content-addressed) and registry digest where one exists; the batch environment record carries `image@id` |
| Command line | verbatim, shell-quoted, in `SolverResults.solver.command_line` and `palace_run.json` |
| Input hashes | candidate canonical JSON, `mesh.msh`, `config.json` |
| Output hashes | every file under `postpro/`, the log, the run record; also as `SolverResults.artifacts` with roles |
| Convergence | `eigenmode_backward_error_max`: the eigensolver's own backward error, maximum over the requested modes, against `Solver.Eigenmode.Tol` |
| Mesh | node and tetrahedron counts, gmsh version, characteristic length, hash |
| Adapter rules | `SOLVER_RULES` in `solvers/palace/config.py`, copied into every `solver_input.json` |

The convergence figure is what Palace reports. It measures how well the
eigensolver converged on the mesh it was given. It does **not** measure mesh
convergence; that campaign is deferred (spec §15).

## Running the proof

```bash
# 1. Build the image (once). Pinned base digest, apt snapshot, Palace tag.
docker build -f docker/palace.Dockerfile -t qmhp-cem/palace:0.13.0 .

# 2. Install the mesher.
uv sync --extra palace            # plus: apt-get install libglu1-mesa (Linux)

# 3. Run the golden candidate.
uv run python scripts/palace_golden_run.py
```

Exit codes: `0` converged and within the analytic tolerance; `2` Palace cannot
execute here (nothing is substituted); `3` ran but failed or did not converge;
`4` converged but disagrees with the closed form; `5` golden digest mismatch.

The run writes `results/PALACE-GOLDEN-<UTC>/` with `candidate.json`,
`solver/{mesh.msh,config.json,solver_input.json,palace_log.txt,palace_run.json,solver_results.json,postpro/…}`,
`execution_record.json` and a `manifest.sha256` over all of it.

The same path also runs under `uv run cem sweep sweeps/object001_grid.yaml
--solver palace`. That is nine eigenmode solves; this milestone does not
optimise or expand it, and gates needing S-parameters report `INCOMPLETE`
honestly because an eigenmode run produces none.

## Reproducibility of the image

`docker/palace.Dockerfile` pins, by default:

- the base by **content digest**, not tag;
- the Ubuntu **package snapshot** (`APT_SNAPSHOT`), so the toolchain does not
  float with the archive;
- the **Palace release tag**, with an optional `PALACE_COMMIT` assertion that
  fails the build if the tag has moved;
- Palace's own dependencies at the revisions its superbuild pins for that tag.

The image records what it contains and the build fails, rather than the first
run, if the copied binary is missing a shared library.

## Status of the proof in this repository

**No Palace run has been executed from this checkout.** The environment that
produced this code has no reachable Docker daemon, so the image was not built
and `scripts/palace_golden_run.py` exits 2 here with that exact reason. Every
piece that does not need the container is tested: the analytic reference, the
domain derivation, the mesher (live, deterministic), the config, the parsers
on hand-authored format fixtures, `prepare()`, the run record, and the
no-fallback guarantees. The real-execution test is marked `palace` and skips
with the reason wherever the container is absent.

The first `results/PALACE-GOLDEN-*` directory committed to this repository is
the proof. Until one exists, this path is implemented and tested up to the
container boundary, and not beyond it.
