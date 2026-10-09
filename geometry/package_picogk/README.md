# Object 001 — PicoGK package geometry

3D package geometry for `object001_single_device_package` (spec §7.2, §7.4), built with
[PicoGK](https://github.com/leap71/PicoGK) 2.3.0.

**Status: implemented; not yet reviewed by the owner.** Every dimension is
ENGINEERING-SEED (spec §7.5). The generator adds layout assumptions A1-A9 (below) that
the seed does not fix. None of them is approved, and none is a validated QMHP hardware
dimension.

## Where it runs

PicoGK is a managed library over a native kernel. The PicoGK 2.3.0 NuGet package ships
native code for two platforms only:

| Platform | Runs? |
|---|---|
| macOS on Apple Silicon (osx-arm64) | **Yes, on macOS 26.5 or later.** The library's Mach-O `LC_BUILD_VERSION` sets minos 26.5 for `picogk.26.2.dylib` and 26.0 for its bundled dependencies, so an older macOS cannot load it. |
| Windows x64 (win-x64) | **Untested.** PicoGK ships win-x64 native code, so the generator should load there, but no Windows run is recorded: CI has no Windows job. |
| Linux, including CI's `ubuntu-latest` and the Claude Code sandbox | **No.** No native library is shipped, so the program refuses with exit code 5 and writes nothing. |

In CI, the `dotnet` job on Linux runs the managed layer. The `picogk-native` job on
`macos-26` runs the real kernel and must not skip it (`QMHP_REQUIRE_PICOGK_RUNTIME=1`).
It also uploads the seed geometry as the artifact `object001-seed-geometry-<sha>`.
Generated STLs are not committed (CLAUDE.md §11).

## Boundary

```
input:   candidate.json
outputs: body.stl, lid.stl, ports.json, geometry_manifest.json
```

```
dotnet run --project QmhpCem.Geometry.csproj --configuration Release -- \
    --candidate <candidate.json> --output <dir> [--voxel-mm <size>]
```

| Exit code | Meaning |
|---|---|
| 0 | Generated. Every acceptance check passed and the four outputs are published. |
| 2 | Usage or input error: arguments, candidate file, parameters, or an output that already exists. Geometry is never overwritten. |
| 4 | An acceptance check failed. Nothing is published. `geometry_rejected.json` says which check failed. The parts built before the failure are kept under `rejected/` as evidence, renamed so that nothing can mistake them for outputs. |
| 5 | The PicoGK native runtime cannot load on this platform. Nothing is written. |
| 6 | Unexpected internal error. Nothing is published. |

Outputs are written to a staging directory. They are moved into place only after every
check passes, with `geometry_manifest.json` last. The manifest records the sha256 of
`body.stl`, `lid.stl` and `ports.json`. The Python driver (`driver.py`) accepts geometry
only when the program exits 0 and the manifest says `PASSED` and those digests match
the files on disk.

To try it on a Mac with macOS 26.5+ and the .NET 9 SDK:

```
dotnet run --project geometry/package_picogk/QmhpCem.Geometry.csproj -c Release -- \
    --candidate geometry/package_picogk/tests/fixtures/object001_seed.candidate.json \
    --output /tmp/object001-seed
```

The STLs open in any mesh viewer, for example Preview on macOS. At the default 0.1 mm
voxel size each part is tens of MB.

## How it is built

The library is used headless: a `PicoGK.Library` instance is created directly, with no
viewer. PicoGK's getting-started pattern (`Library.Go` in
[PicoGK_Examples](https://github.com/leap71/PicoGK_Examples), CC0) opens the
interactive viewer, which a CI runner cannot show. Every solid is a box or a cylinder
rendered from an exact signed-distance function and combined with voxel booleans. The
meshes are exported as binary STL in mm.

Frame (spec §7.3, frozen): the origin is the centre of the chip's top surface, +X/+Y lie
in the chip plane, +Z points from the chip toward the lid, and the unit is mm.

| Feature (spec §7.4) | Source |
|---|---|
| Package body, chip recess, vacuum cavity | candidate parameters |
| Removable lid | A4: a plate plus a plug that fills the open pocket down to the cavity ceiling |
| Two opposing SMP-style launch bores | candidate diameter; A5 sets their position |
| Mounting features | A6: four M2-clearance corner through-holes |
| Simple thermal path | A7: a 0.5 mm contact land under the chip footprint |
| Filter housing allowance | A8: a reserved, uncut block in the +Y wall |
| Chip datum, solver-domain bounding definition | `ports.json` and `geometry_manifest.json` |

The assumptions are listed in full, with their rationale, in `Object001Layout.cs`
(`Object001Assumptions.All`) and in every manifest:

- A1: the chip rests on the recess floor.
- A2: the cavity ceiling is `height_above_chip_mm` above the chip-top datum.
- A3: `floor_thickness_mm` is the material below the recess floor.
- A4: the lid carries a line-to-line plug, so the sweep's cavity height changes the lid, not the body.
- A5: the bores run along X at y = 0, tangent to the cavity floor. They are taller than the cavity, so the plug closes their upper part. A real SMP launch would put its pin at the chip surface, which needs a pin and dielectric model that this generator does not include.
- A6: four corner holes.
- A7: the thermal land.
- A8: the filter allowance.
- A9: the voxel size is 0.1 mm, and every feature must span at least 4 voxels.

Seed layout, in mm:

- body: z = -1.43 to 3.57, plus the land down to -1.93;
- recess floor: z = -0.43;
- cavity: z = 0.02 to 1.5;
- lid: z = 1.5 (plug) to 5.57;
- bore axis: z = 1.27.

## Acceptance checks (spec §7.6)

Each check runs before anything is published, in three independent layers:

1. **Analytic** (`Object001Layout.AnalyticChecks`). Exact arithmetic on the layout, run before PicoGK is touched:
   - positive volume;
   - recess inside the package;
   - chip inside the recess;
   - positive walls;
   - bores from the outer face into the cavity, clear of everything else;
   - mounting holes surrounded by solid material;
   - thermal land present;
   - filter allowance uncut;
   - chip datum;
   - solver domain enclosed;
   - every feature at least 4 voxels thick.
2. **Probes** (`Object001Layout.Probes`). More than 100 points whose membership the layout predicts are tested against the voxel parts with `Voxels.bIsInside`:
   - the void paths run every half voxel, from outside the package through each bore to the cavity centre, and along each hole axis;
   - the solid points cover the walls around every hole and bore, the land and the allowance.
3. **Read-back** (`StlCheck`). Each published STL is read back from its bytes:
   - closed, 2-manifold and consistently outward-oriented;
   - one connected solid;
   - enclosed volume equal to the exact layout volume within area × voxel / 2 (every face within half a voxel);
   - bounds within one voxel.

Negative controls exist for each layer:

- planted layout defects, in `LayoutTests`;
- planted construction defects (a missing bore, a missing mounting hole, a missing land), in `NativeGenerationTests`;
- planted mesh defects, in `StlCheckTests`.

Each control must fail the check named for it.

## What this does not establish

- The assumptions A1-A9 are generator choices, not reviewed designs.
- The geometry is a voxel model. Faces are planar, but edges are rounded at roughly one voxel.
- It is not an electromagnetic model. The Palace meshes are built separately (`solvers/palace`), and nothing here has been solved.
- When the pipeline runs on a supported platform, `orchestrator/pipeline.py` writes the geometry straight into the candidate directory, outside the results store's write guards. That gap predates this generator and is not closed here.

## What PicoGK is and is not

PicoGK is a computational **geometry** kernel. It generates the physical geometry on
which the physics is evaluated. It is not an EM solver, a Hamiltonian solver or a QEC
simulator; those live in `solvers/` and `models/`. Thin-film mask and GDS design
belongs in `geometry/chip_planar/` (gdsfactory), not here.

## Environment

| Component | Version | Note |
|---|---|---|
| .NET | 9 | spec §13.2; `global.json` selects 9.0.x |
| PicoGK | **2.3.0, pinned exactly** | `[2.3.0]` exact-version range in the csproj. Apache-2.0 per its nuspec; built from leap71/PicoGK commit `389d4d9a`. Depends on SkiaSharp 3.119.0 (MIT per its nuspec). The package bundles native third-party libraries (on macOS: Boost, ICU, liblzma, zstd; on Windows: TBB, Blosc, LZ4, zlib, zstd). NuGet restores them at build time; this repository does not redistribute them. Licence compatibility is for human/legal review (CLAUDE.md §12). |
| LEAP71 ShapeKernel | not used | spec §7.2 asks for it only "where required" |
