# FEM-to-spectral compatibility: arithmetic on the committed scalar records

Offline. Reads only the committed `eig.csv`, `port-EPR.csv` and `domain-E.csv`
of the N1R (six eigenpairs) and N2R (nine eigenpairs) records. No Palace run,
no field archive, no Route A result, no coupling evidence, no gate input.
N2R is **not** truncated to six modes. Participation weights are never
renormalised.

| file | content |
|---|---|
| `spectral_compatibility.py` | the calculation; writes the JSON beside itself |
| `spectral_compatibility.json` | per-mode equipartition, the assembled-operator participation against the reported rank-one EPR, the decomposition of the saved sum, every inclusion and exclusion with its reason, the declared-versus-normalised rank-one removal, the conditional spectral variants, and the two withdrawn claims |
| `review_checks_reconstructed.py` | independent reconstruction of the three review checks against 46bf8b5 (the supplied `QMHP_46bf8b5_review_checks.py` did not reach this environment): a rank-2 and a rank-3 port term with `N = 1`, the exact identity `N − N² = uᵀK_curl u + uᵀ(K_port − Q)u`, a counterexample to the diagonal-participation shift bound, and the determinant identity |
| `review_checks_reconstructed.json` | its output. SYNTHETIC small matrices only; no QMHP record is read |

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
