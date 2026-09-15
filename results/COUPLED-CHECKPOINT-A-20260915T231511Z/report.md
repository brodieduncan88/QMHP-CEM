# Coupled candidate checkpoint A: offline check

Record `COUPLED-CHECKPOINT-A-20260915T231511Z`. Nothing in this record is coupled EM evidence: it validates a declaration, recomputes source digests, draws the declared seed geometry and estimates a mesh. No Palace solve was run. Every ENGINEERING-SEED remains unapproved.

| item | value |
|---|---|
| declaration | `/home/user/QMHP-CEM/config/coupled/v2a_five_node_candidate.json` sha256 `c0f68ca183a9034e1095d796f5f5d138a500852202559a1f91803a6f73e46472` |
| declaration id | QMHP-CEM-A-CC-000001 |
| register | `/home/user/QMHP-CEM/config/coupled/source_register.json` sha256 `d1e45b5da7d736d848d8d1fe60dbe8c2d52e0e78b9274d66781a81714706fcd6` |
| declaration valid | True |
| register verified | True (0 mismatches) |
| preview | preview.svg |
| mesh dry run | gmsh |
| admission disposition | READY-FOR-REVIEW: declaration valid, sources verified, geometry consistent |
| execution disposition | BLOCKED: ladder exceeds the DOF budget |

## Mesh dry run against the DOF budget

DOF budget 250000 (numerical-plan.md §6). Mesh counts and the solver-space dimensions below are MEASURED: the dimension of MFEM's Nedelec space on tetrahedra is fixed by the mesh topology (edges for order 1, 2*edges + 2*faces for order 2), checked against Palace's own reported DegreesOfFreedom on the committed golden record. No solver size here is extrapolated from a per-tetrahedron ratio.

| level | status | DOF order 2 | within budget | DOF order 1 | within budget |
|---|---|---|---|---|---|
| L1 | OK | 545734 | False | 101668 | True |
| L2 | OK | 1230572 | False | 228572 | True |
| L3 | OK | 2378980 | False | 440642 | False |


## Sensitivity probe (UNADOPTED)

Unadopted measurements. Each row is the declared candidate with one seed changed, meshed at level 1 only, to show what drives the mesh cost. No variant is part of the declaration; adopting one is a human decision that would change config/coupled/v2a_five_node_candidate.json and its record.

| variant | changes | tets | DOF order 2 | DOF order 1 |
|---|---|---|---|---|
| cell_2mm | cell 2 x 2 mm instead of 4 x 4 mm; everything else as declared | 123007 | 798172 | 149470 |
| coupling_gap_40um | coupling gap 40 um instead of 20 um (the narrowest gap sets the mesh) | 51328 | 330024 | 61624 |
| coupling_gap_40um_cell_2mm | both of the above together | 73837 | 480286 | 90048 |

## Statement

Nothing in this record is coupled EM evidence: it validates a declaration, recomputes source digests, draws the declared seed geometry and estimates a mesh. No Palace solve was run. Every ENGINEERING-SEED remains unapproved.
