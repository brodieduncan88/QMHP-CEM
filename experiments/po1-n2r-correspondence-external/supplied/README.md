# QMHP PO1 ↔ N2R full-field correspondence

Classification: **external offline diagnostic**. No Palace run, no repository write, no coupling extraction.

## Source artefacts

- PO1 workflow 35536625799, artifact 10612713395
  - SHA-256 `a156768cbd0723c9988ce4617db1d1c07f29d5376d2cc5e7bf6ee25906ea8dc8`
- N2R workflow 35313973073, artifact 10533683685
  - SHA-256 `1ca851c4da54210270d6834f378bd8e5cf96e4db047beb546ac69a5079eb8b0e`

The large field ZIPs are deliberately not included in this package.

## Method

The two volume exports were checked for exact equality of:
- point coordinates,
- tetrahedral connectivity,
- material attributes.

For each saved mode, the complex electric field was compared on that identical mesh.

The inner product is the material-weighted volume integral

`<A,B> = ∫ epsilon_r A* · B dV`.

Each exported tetra contains four per-element vertex samples. Since a lowest-order Nedelec field is affine inside a tetrahedron, the script uses the exact P1 tetrahedral mass formula for the product of the exported affine fields, multiplied by the cell relative permittivity (`1.0` vacuum, `11.45` substrate).

The normalised overlap is

`|<A,B>| / sqrt(<A,A><B,B>)`.

The optimal complex scale removes the arbitrary global eigenvector phase/amplitude. The reported RMS is the residual after that optimal scale, relative to the PO1 field norm.

## Key result

PO1 mode 1 vs N2R mode 2:

- overlap: **0.999927020830**
- optimal-phase RMS difference: **0.012081101516**

PO1 m1 overlap against N2R saved modes 1–6:

`0.012036416, 0.999927021, 0.000006104, 0.000010973, 0.000059979, 0.000287128`

The exported N2R saved modes are mutually orthogonal under the same weighted inner product to approximately `3.5e-7` maximum off-diagonal overlap. The near-unit m2 overlap therefore leaves only about 1.2% norm for all components orthogonal to m2; no unseen orthogonal N2R mode can compete with m2 under the same metric.

## Frequency comparison after field correspondence

PO1 m1 = `3.885827871 GHz`.

- conditional `K-Q`: `3.885826970414 GHz`
  - PO1 minus prediction = `900.586 Hz`
  - relative = `2.318e-07`
- conditional `K-Q/N`: `3.885825996104 GHz`
  - PO1 minus prediction = `1874.896 Hz`
  - relative = `4.825e-07`

N2R m2 = `3.887370723 GHz`, so PO1 m1 is `-1.542852 MHz` below the port-loaded mode.

## Scope

This supports full-field correspondence **PO1 m1 ↔ N2R m2** and a frequency comparison at this discretisation.

It does **not** establish:
- a coupling `g`,
- a residue,
- `E_C`,
- continuum convergence,
- Route A or Route B PASS,
- hardware validity.

PO1's original pre-declared three-point classifier remains historically **INCONCLUSIVE**; this is a separate post-hoc full-field analysis.
