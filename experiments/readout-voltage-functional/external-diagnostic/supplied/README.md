# QMHP-CoPro: independent offline readout-field diagnostic

**Classification:** post-processing of existing EM results only. No Palace run,
new eigenpair, coupling extraction, production change, or acceptance decision.
No file in the user's repository was changed by this analysis.

## Scope and provenance

This evaluates the two readout surface functionals already defined at repository
commit `5bc50d01e7c4578feb7df532b3b31956f6cefac1`, rather than choosing a surface
after inspecting the voltages. The primary is the +Y rectangle; the -Y rectangle
is retained separately as the declared mirror/path diagnostic. No average is used.

- Functional: `experiments/readout-voltage-functional/functional.json` at that commit.
- +Y: x = [-0.485, -0.405], y = [0.050, 0.080], z = 0 mm; direction -Y.
- -Y: x = [-0.485, -0.405], y = [-0.080, -0.050], z = 0 mm; direction +Y.
- Readout width: 0.080 mm. F-port attribute: 10; width: 0.020 mm.
- Dimensional conversion: the pinned recipe's sqrt(Z0)/lambda = 19.409541814844687/4.
- Both ratios retain complex values and signs.

Both existing local archive copies were read and hashed:

| Dataset | Archive | Bytes | SHA-256 |
|---|---|---:|---|
| N1R | N1R_fields_35438882836.zip | 95,969,529 | 79c0401c66ec7d281c90312a01409db8a862a9e9d4ce1163b52e4b0e1c111ff0 |
| N2R | N2R_fields_35313973073.zip | 113,746,865 | 1ca851c4da54210270d6834f378bd8e5cf96e4db047beb546ac69a5079eb8b0e |

They match the registered artifact digests. Boundary collection PVD entries map
mode 1 to Cycle000000 and mode 2 to Cycle000001. Each archive contains boundary
field datasets for modes 1 through 6. The export is Float32 and is not a native
full-precision FE coefficient archive.

## Reconstruction method

VTK reads the boundary cells and the element-local complex electric-field
values. Each exported triangle has three vertices. Arithmetic uses float64,
without claiming recovery of precision absent from the Float32 source.

For the F port, integrate E_y on attribute-10 triangles using triangle area
multiplied by the mean of the three vertex values, then apply the fixed width
and unit conversion. Compare against committed port-V.csv values, without
calibrating the conversion.

For each readout rectangle, clip the z=0 boundary triangles to the exact
predeclared rectangle and interpolate E_y linearly within each triangle. This
is necessary: selecting triangle centres and summing entire triangles would
include area outside the rectangle. Preserve element-local samples; do not
average duplicate point values across elements. Integrate the clipped polygons
and apply the prescribed direction and width normalisation.

A second implementation uses Shapely/GEOS polygon intersection and barycentric
field evaluation at each clipped polygon's centroid. It reproduces the surface
integrals within 4.96e-16 relative. Analytic affine complex-field integration and
orientation-reversal tests pass. These tests check arithmetic on the same
exported interpolant, not the accuracy of the underlying EM discretisation.

The exact rectangular area, 0.0024 mm^2, is recovered for both sides on both
meshes. Very small pieces of PEC triangles are included where Float32 rounding
places an edge across the ideal rectangle; their total area is about
2.03e-10 mm^2. The materially contributing field is on interface attribute 25.

## 1. F-port reconstruction

Relative error is abs(V_reconstructed - V_CSV) / abs(V_CSV).

| Dataset | Mode | Relative complex-voltage error |
|---|---:|---:|
| N1R | 1 | 2.0044741e-6 |
| N1R | 2 | 2.0063136e-6 |
| N2R | 1 | 2.0050204e-6 |
| N2R | 2 | 2.0060361e-6 |

This reproduces the earlier approximately 2e-6 comparison. It is a limited
reconstruction cross-check, not a certified error bound for readout voltages.

## 2. Readout ratios

rho_m = V_R,m / V_F,m, using reconstructed V_F from the same mode.
r12 = rho_1 / rho_2. The real parts are shown below; complete complex values
and alternatives using the CSV F voltage are in evaluation/results.json.

| Dataset | rho_1 (+Y) | rho_2 (+Y) | r12 (+Y, primary) | r12 (-Y, mirror) |
|---|---:|---:|---:|---:|
| N1R | -0.00381269423 | 3.72887572 | -0.00102247823 | -0.00118055231 |
| N2R | -0.00384088065 | 3.69581095 | -0.00103925247 | -0.00120285662 |

The imaginary part of r12 has magnitude below 7e-12 for these calculations.
This is reported, not set to zero or discarded in the calculation.

Mirror relative difference is abs(plus-minus)/max(abs(plus),abs(minus)).
Mesh change is abs(N2R-N1R)/abs(N1R).

| Diagnostic | N1R | N2R |
|---|---:|---:|
| Mirror difference in mode-1 readout voltage | 13.2591% | 13.4678% |
| Mirror difference in mode-2 readout voltage | 0.150746% | 0.154303% |
| Mirror difference in r12 | 13.3898% | 13.6013% |

N1R -> N2R r12 changes by **1.64055% on +Y** and **1.88931% on -Y**.
These are diagnostics, not tests against a newly invented tolerance and not
Route-A/Route-B disagreements.

## 3. Geometry check

Canonicalised vertex coordinates and attributes of the exported triangles
intersecting each readout rectangle match exactly between N1R and N2R.
This is a direct comparison of the local exported surfaces, not an inference
from the refinement box not reaching them. The +Y and -Y local geometry
hashes are recorded in the JSON output.

Accordingly, this pair does not test convergence under refinement of the
readout-gap surface mesh. The changes in the fields/ratios remain differences
between two solved discretisations; no additive regional error share is claimed.

## 4. Interpretation and limits

**Established by this local calculation:** the existing archive copies are
available and hash-verified here; the declared surface integrals can be
computed; the F-port comparison reproduces the committed reference closely;
and the two readout proxies yield different ratios as quantified above.

**Not established:** which physical or numerical mechanism causes the mirror
difference; whether either functional is an adequately accurate representation
of the registered single-mode readout coordinate; a continuum value; model
completeness; an uncertainty bound on g; any coupling value or Route A PASS.

A path-specific integral can be well-defined without two different paths
being interchangeable estimates of one lumped voltage. Electromagnetic path
dependence, discretisation error, and the mapping from a distributed resonator
to a lumped coordinate must not be conflated. The present result does not
separate those causes, and the two surfaces have not been averaged or tuned.

**Next:** preserve and review these actual diagnostics before using r12 in
any synthetic-derived real-data inversion. No new solve was needed for this
calculation; no change to the coupling definition has been made.

## Reproduction

Requires Python plus numpy, vtk and shapely. Exact versions are recorded in
`evaluation/results.json`. The source archives are supplied separately and
are deliberately not copied into this small package.

```sh
python evaluate_readout_fields.py --archive-dir /path/to/the/two/archives --out /new/empty/output
```

The program verifies both archive hashes before use. It only reads the selected
archive members into a temporary directory and writes a separate JSON result.
A second local invocation produced a byte-identical results.json.

## Sources

- https://github.com/brodieduncan88/QMHP-CEM/blob/5bc50d01e7c4578feb7df532b3b31956f6cefac1/experiments/readout-voltage-functional/functional.json
- https://github.com/brodieduncan88/QMHP-CEM/blob/5bc50d01e7c4578feb7df532b3b31956f6cefac1/results/COUPLED-LADDER-O1-L2-N1R-20260919T110053Z/L2/solver/postpro/port-V.csv
- https://github.com/brodieduncan88/QMHP-CEM/blob/5bc50d01e7c4578feb7df532b3b31956f6cefac1/results/COUPLED-LADDER-O1-L2-N2R-20260918T061455Z/L2/solver/postpro/port-V.csv
- Original field artefacts: workflow 35438882836 / artifact 10583481701 and workflow 35313973073 / artifact 10533683685.
