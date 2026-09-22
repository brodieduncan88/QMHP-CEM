# First-moment image — synthetic qualification of `sha256:5df2170a…`

**One image, two runs.** The first built it and refused it. The second changed the MPI
launch and nothing else, and qualified it. Both runs are preserved; neither record has
been edited.

| | run A | run B |
|---|---|---|
| run id | [35691886143](https://github.com/brodieduncan88/QMHP-CEM/actions/runs/35691886143) | [35699653327](https://github.com/brodieduncan88/QMHP-CEM/actions/runs/35699653327) |
| attempt | 1 | 1 |
| checked-out SHA | `1bf0fbcb1323041f75dcb744bf85df72d8e7d953` | `d40414f0d551be709d53ac34db2de5748a787158` |
| image | **built** | **restored, not rebuilt** |
| image ID | `sha256:5df2170a204ea2926f63639848751cb3ec4207520430b8ecdd529c239731dcf1` | identical, verified after load |
| archive sha256 | `7e09f5028f4bc028b9aae52cbde6bc837e97c4d11c22622b590f04e764062834` | identical, verified before load |
| MPI launch | `mpirun -n N <binary>` | `mpirun -n N --oversubscribe <binary>` |
| decision | **NOT QUALIFIED** | **QUALIFIED** |
| artefact | `first-moment-image-35691886143`, id 10679358298, 199 524 159 B, expires 2026-12-21T05:44:24Z | `first-moment-requalify-35699653327`, id 10681835623, 86 548 B, 90-day retention |

The image ID and the archive sha256 are **different identifiers**, and no registry digest
exists — the image has never been pushed anywhere (`RepoDigests` is empty).

## What run A established, and what it did not

Every fixture passed, and ranks 1 and 2 passed. Ranks 3 and 4 produced nothing:

```
>> /usr/bin/mpirun -n 3 /opt/palace/bin/palace-x86_64.bin config.json
There are not enough slots available in the system to satisfy the 3
slots that were requested by the application
```

**Palace never started.** This was a launch failure, not a numerical one, and Open MPI's
own message names the cause: with no hostfile, no `--host` and no resource manager, "Open
MPI defaults to the number of processor **cores**". The decision refused the image, which
is the correct outcome for absent measurements — a missing rank is not a passing rank.

## The one change

The preserved wrapper `/opt/palace/bin/palace` (Apache-2.0, AWS Labs; sha256
`1907df1e90f38f4ece35040c06a3abdbc7b168c5e44545f1c6b7cd763436671d`) documents

```
-launcher-args,
  --launcher-args ARGS           Any extra arguments to pass to MPI launcher
```

and builds its command as `mpirun -n $NUM_PROCS $LAUNCHER_ARGS <binary>`. The synthetic
shim now passes `--launcher-args --oversubscribe` for a **parallel** launch only; a serial
launch never reaches `mpirun` and is forwarded unchanged. The shim refuses a rank count
above four, or one that is not a number, before the container runtime is reached.

Nothing else changed: same runner class, same 120/75/30-minute caps, same one attempt,
same `OMP_NUM_THREADS=1`, same fixtures, same declared criteria, same tolerances, and
`PALACE_IMAGE_INFO_DIR` is still withheld so this remains a qualification of the **image**.

## The topology, measured rather than inferred

`nproc` is not the slot count. Run B recorded both, and measured the limit directly with
`/bin/true` — no solver, no config, no mesh:

| | value |
|---|---|
| host | AMD EPYC 7763, `nproc=4` |
| threads per core / cores per socket / sockets | 2 / 2 / 1 → **2 physical cores** |
| cgroup `cpu.max` | unavailable |
| container `nproc` | 1 |
| Open MPI | 4.1.6 |

```
mpirun -n 1 : plain=ok       with --oversubscribe=ok
mpirun -n 2 : plain=ok       with --oversubscribe=ok
mpirun -n 3 : plain=REFUSED  with --oversubscribe=ok
mpirun -n 4 : plain=REFUSED  with --oversubscribe=ok
```

Two slots, four hardware threads. That is the whole of run A's failure, and the whole of
the correction.

## Run B's numbers

All 52 checks passed; `failed` is empty.

| rank | `mpi_size` | exit | `A_nd` | relative error vs the independent assembly |
|---|---|---|---|---|
| np=1 (serial path) | 1 | 0 | 64.16250164577238 | 8.859289678982371e-16 |
| np=2 | 2 | 0 | 64.16250164577238 | 8.859289678982371e-16 |
| np=3 | 3 | 0 | 64.16250164577238 | 8.859289678982371e-16 |
| np=4 | 4 | 0 | 64.16250164577238 | 8.859289678982371e-16 |

The four ranks agree to all twelve rounded digits (`distinct_A_nd` = `[64.162501645772]`).

| fixture | result |
|---|---|
| A-nominal | converged, 32 iterations, functional check `0e+00`, `‖f_PEC‖² = 2.273e-02 > 0`, `‖x_PEC‖ = 0`, null-space gap 0.9434 (sampled, not proof) |
| B-scaled-L | converged, relative error 8.305584074045974e-16 |
| 1/L scaling | ratio 10.000000000000002 against 10.0, relative error 1.7763568394002506e-16 |
| C-maxits-1 | `Converged: false`, relative residual 0.4129210005633967, underestimates `A` by 9.953793129093022 nd, certified lower bound holds, the uncertified estimate shown **not** to be a bound |
| D-port-inactive | exit 1, **no** `first-moment.json`, structured `FAILED` record with provenance, reason "no active lumped port with nonzero inductance" |

Every record that was written carries the reviewed Palace identity and
`ImageInfoDirIsDefault: true`, so all four fixtures ran the image, not a developer build.

## What this does NOT establish

- **Fault injection did not run.** `--faulted-palace` was not supplied, so this
  qualification says nothing about whether the functional check is vacuous. The only
  evidence for that remains the native record, where it was caught at np=4 alone.
- **Two criteria have no declared threshold** and are reported, not gated: the wording of
  an intended `FAILED` record's `Reason`, and any per-fixture wall-clock or memory budget.
- **np=1 is the serial path.** The wrapper runs the binary directly at one rank, so MPI
  itself is exercised at 2, 3 and 4 ranks, not at 1.
- **This is a synthetic qualification.** No QMHP input was read, no `E_C` and no `g` were
  computed, and it grants no approval to execute the diagnostic on N2R. The independent
  image-binding requirement for that run — `load_approval()` receives no image identity,
  and `evaluate_record.py` takes the required `image_id` from the launcher's own
  provenance — is untouched and still outstanding.

## Retained evidence

Run B's artefact holds the qualification report with its decision, the harness log, the
shim as it ran, the topology measurement, the restore record, and for each of the eight
executions the config, the synthetic mesh, the raw solver log and the result or `FAILED`
record — 52 files. The image archive is **not** re-uploaded; it stays in run A's artefact
under the checksum run B verified, and `restored_image.txt` points at it.

Two honest notes on that artefact. `evidence-manifest.txt` records itself as 0 bytes
because `find` measures it while it is being written; the file itself is 1458 bytes in run
A and comparable in run B. And the manifest lists the `preserved/` copies of run A's files
that run B downloaded; those are **not** in run B's artefact, which uploads only the
thirteen paths named in the workflow.
