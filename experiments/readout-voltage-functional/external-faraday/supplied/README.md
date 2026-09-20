# QMHP-CoPro — offline Faraday consistency diagnostic

**Classification:** offline post-processing of the already-solved N1R/N2R field
archives. No Palace run, no new eigenpair, no coupling extraction, no change to
the repository, and no acceptance decision.

## Result

The measured difference between the two predeclared readout surfaces is
reproduced by Faraday's law on the same exported fields.

| Record | Mode | relative complex disagreement |
|---|---:|---:|
| N1R | 1 | 9.53e-7 |
| N1R | 2 | 8.57e-6 |
| N2R | 1 | 8.23e-7 |
| N2R | 2 | 1.14e-5 |

This establishes that the 5–7 mV `V+ - V-` difference is the enclosed
magnetic-flux/path term of the **stored discrete solution**, within the
precision of the Float32 export and the offline integration.

It does **not** establish which path is the registered circuit coordinate,
mesh convergence of either voltage, model completeness, or any value of `g`.

## Two corrections to the predeclared test

1. **Orientation sign.** The declared loop is clockwise when viewed from +z,
   hence its Stokes normal is -z. With Palace's `curl E = -i omega B`,
   comparison to the exported +z `B_z` is

   `V+ - V- = + i omega Phi_z`.

   Equivalently, the original `-i omega` form is retained only if the flux is
   defined with the loop's -z normal.

2. **The spanning surface includes P_F1.** `A_west` contains the existing
   F1 lumped-port face, attribute 10, area about 0.00080000156 mm^2. Restricting
   the flux integral to attribute 25 misses this piece. Attribute 10 contributes
   about 4.0–5.5% of the weighted flux in the four checked cases. Including it
   restores the Faraday identity.

The tiny attribute-4 slivers caused by Float32 geometry rounding carry zero
material contribution at the reported precision.

## Interpretation

Faraday closure shows that the mirror difference is not an unexplained
numerical mismatch between the two E integrations. It is the non-conservative
electric-field loop term associated with time-varying magnetic flux in this
solution.

That does **not** by itself mean the term must be assigned to a particular
lumped inductive branch, nor does it select +Y or -Y as the canonical readout
coordinate. Circuit reduction still needs an explicit coordinate/path (or
gauge/tree) convention consistent with the registered Hamiltonian.

See `evaluation/results.json` for the complete complex comparisons.
