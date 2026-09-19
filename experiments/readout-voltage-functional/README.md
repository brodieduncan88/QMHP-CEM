# Readout-voltage functional: definition, artefact verification, mesh feasibility

An offline analysis record. It contains **no field value, no voltage, no
ratio and no coupling**: the field artefacts of N1R and N2R could not be
retrieved from the analysis environment (see `artefacts.json`), so the
functional is defined and its evaluation is specified, and the mesh-side
feasibility is measured on the committed L2 mesh. Nothing here modifies a
result record; the source artefacts stay where GitHub Actions keeps them.

The analysis is in
[`docs/coupled-candidate/readout-voltage-functional.md`](../../docs/coupled-candidate/readout-voltage-functional.md).

| file | content |
|---|---|
| `functional.json` | the readout-voltage functional, derived from the registered declaration by `solvers.palace.coupled_geometry`: location, orientation, reference conductor, integration surfaces, width normalisation, units, Palace's dimensionalisation constants, and the F-port cross-check recipe |
| `artefacts.json` | the two artefacts' identity as the GitHub API reports it (ids, names, sizes, digests, run ids, head shas), the user-supplied digests, and the blocked retrieval attempt |
| `mesh_feasibility.py` | reads the committed N1R L2 mesh (byte-identical to N2R's) and checks the port face and the readout gap rectangles; writes `mesh_feasibility.json` |
| `mesh_feasibility.json` | its output |

Re-run the mesh check (needs the `palace` extra for gmsh):

```
uv run python experiments/readout-voltage-functional/mesh_feasibility.py
```
