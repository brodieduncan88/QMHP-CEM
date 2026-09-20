# FEM-to-spectral compatibility: arithmetic on the committed scalar records

Offline. Reads only the committed `eig.csv`, `port-EPR.csv` and `domain-E.csv`
of the N1R (six eigenpairs) and N2R (nine eigenpairs) records. No Palace run,
no field archive, no Route A result, no coupling evidence, no gate input.
N2R is **not** truncated to six modes. Participation weights are never
renormalised.

| file | content |
|---|---|
| `spectral_compatibility.py` | the calculation; writes the JSON beside itself |
| `spectral_compatibility.json` | per-mode equipartition, the assembled-operator participation against the reported rank-one EPR, the decomposition of the saved sum, every inclusion and exclusion with its reason, and the conditional spectral variants |

Two distinct things are computed:

1. **Compatibility evidence.** For each mode, the equipartition ratio
   `R = (E_mag + E_ind)/(E_elec + E_cap)` and, with it, the participation of
   the *assembled* port operator `p_assembled = 1 − E_mag/(E_elec + E_cap)`,
   against Palace's *reported* rank-one EPR `|p|`. If the assembled port term
   were the rank-one circuit term `f fᵀ/L`, these would be equal mode by mode.
   They differ by up to 0.99999.

2. **A conditional diagnostic**, labelled throughout
   `CONDITIONAL SPECTRAL CALCULATION — EM MAPPING UNVERIFIED`: the zeros and
   residues of `G_F(z) = Σ_m |p_m|/(z − f_m²)` in explicit variants (all saved
   modes / field-resonant modes only, and `N = Σ|p|` / `N = 1`), with the units
   conversion `GHz² → (rad/s)²` stated in the script and the note.

The analysis is in
[`docs/coupled-candidate/fem-spectral-mapping.md`](../../docs/coupled-candidate/fem-spectral-mapping.md).

```
uv run python experiments/fem-spectral-mapping/spectral_compatibility.py
```
