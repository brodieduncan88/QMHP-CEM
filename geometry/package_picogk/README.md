# Object 001 — PicoGK package geometry

3D package geometry for `object001_single_device_package` (spec §7.2, §7.4).

**Status: not implemented.** This project defines the file-based boundary, the
CLI contract, candidate parsing and the acceptance-test checklist. The PicoGK
voxel construction in `Object001Package.Generate()` is the first
implementation task.

## Environment

| Component | Version | Note |
|---|---|---|
| .NET | 9 | spec §13.2 |
| PicoGK | **2.3.0, pinned exactly** | `[2.3.0]` exact-version range in the csproj |
| LEAP71 ShapeKernel | revision recorded in `driver.py` | vendor as a submodule before use |

`dotnet` is **not installed in every QMHP-CEM development container.** When it
is absent, `driver.generate()` reports geometry as unavailable and the pipeline
continues, recording plainly that no geometry was produced. It never fabricates
an STL.

## Boundary

```
input:   candidate.json
outputs: body.stl, lid.stl, ports.json, geometry_manifest.json
```

Invoked as:

```
dotnet run --project QmhpCem.Geometry.csproj --configuration Release -- \
    --candidate <candidate.json> --output <dir>
```

Exit codes: `0` success, `2` usage/input error, `3` not implemented.

## What PicoGK is and is not

PicoGK is a computational **geometry** kernel. It generates the physical
geometry on which the physics is evaluated. It is not an EM solver, not a
Hamiltonian solver and not a QEC simulator — those live in `solvers/` and
`models/`. Thin-film mask/GDS design belongs in `geometry/chip_planar/`
(gdsfactory), not here.

## Acceptance tests (spec §7.6)

- [ ] positive volume
- [ ] recess fits inside the package
- [ ] chip fits inside the recess
- [ ] cavity leaves positive walls
- [ ] launch bores connect exterior to the intended interior region
- [ ] mounting holes remain in valid structural material
- [ ] exported meshes watertight where the exporter supports a reliable check
- [ ] ports present
- [ ] all geometry outputs hashed

## Seed dimensions

All Object 001 dimensions are **ENGINEERING-SEED** (spec §7.5) — bootstrap
assumptions introduced by QMHP-CEM because the frozen Master does not define
them. They are not validated QMHP hardware dimensions.
