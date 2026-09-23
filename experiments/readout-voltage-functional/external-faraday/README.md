# External Faraday consistency diagnostic: preserved package and review

**Provenance.** `supplied/` is the byte-for-byte content of
`QMHP_Faraday_Consistency_Diagnostic.zip`, received through the session upload
mechanism on 2026-09-20 (SHA-256 in `supplied-archive.sha256`; its own
`manifest.sha256` verifies). It was produced **outside** this repository's
analysis environment from the two hash-verified N1R/N2R field archives, which
this environment cannot read. Its results are therefore **EXTERNALLY PRODUCED** and
are not reproduced here.

**What it reports.** With two corrections to the pre-declared test
(`../faraday_test_predeclaration.md`), the Faraday prediction reproduces the
measured `V₊ − V₋` of the two readout surfaces with relative complex
disagreement 9.53e-7 (N1R m1), 8.57e-6 (N1R m2), 8.23e-7 (N2R m1) and
1.14e-5 (N2R m2).

**The two corrections, verified locally without the archives (`review.json`):**

1. *Orientation.* The pre-declared loop, traversed as declared, has signed
   area −0.0585 mm² at `x = −0.45`: it is clockwise viewed from +z, so its
   Stokes normal is −z and, with Palace's `∇ × E = −iωB` and the exported +z
   `B_z`, `V₊ − V₋ = +iω Φ_z`. The pre-declaration wrote `−iω` with an
   implicit +z normal; that sign was wrong.
2. *Spanning surface.* `A_west` (area 0.0284 mm² from the registered geometry,
   equal to the package's value) geometrically contains the `P_F1` port face
   (attribute 10, 2.8 % of the area), which is a boundary element of the input
   mesh and therefore not an interface element. Restricting the flux to
   attribute 25, as the review note of 476ee33 proposed, omits it; the
   package reports that piece as 4.0–5.5 % of the weighted flux.

Also verified: the package's measured `V₊ − V₋` equal, to the last digit, the
differences of the earlier readout diagnostic's voltages; its relative
disagreements recompute from its listed complex values; its mode frequencies
equal the committed `eig.csv` of both records.

**What it establishes and what it does not.** The 5–7 mV surface difference
is the magnetic-flux/path term of the stored discrete solution to the
precision of the Float32 export. It does not say either path is wrong, does
not make the 13–14 % `r₁₂` difference a coupling error, does not establish
continuum convergence, and does not assign the term to any lumped inductive
element. The decision it forces is in
[`docs/coupled-candidate/r1-definition-decision.md`](../../../docs/coupled-candidate/r1-definition-decision.md).
