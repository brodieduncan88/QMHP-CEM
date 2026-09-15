# Palace mesh-refinement and height-sensitive verification

Campaign `mesh-height-verification-v1`, definition sha256 `249e1a12a4853850a3feb47d0caa619173d6fecb53a4b838dc3431afca66ba2d`; execution `palace`.

Numerical verification of the empty PEC box only. Mesh convergence of the 22 x 22 x 1.5 mm box on three meshes, and height sensitivity through p >= 1 modes: the Object 001 box itself where the runner budget allows, and an auxiliary 22 x 22 x 7.0/7.7 mm box that verifies the Z pipeline and is not a verification of Object 001. All rules are ENGINEERING-RULEs of numerical verification, not frozen QMHP physical requirements. No mode splitting here is physical QMHP coupling.

## Verdicts

- Mesh convergence (22 x 22 x 1.5 mm box): **PASS**
- Height sensitivity, auxiliary 22 x 22 x 7.0/7.7 mm box (Z pipeline, not Object 001): **PASS**
- Height sensitivity, Object 001 box (1.5 mm against 1.65 mm): **BLOCKED**

## Objective 1: mesh convergence

Analytic (GHz): 9.635695, 15.235371, 15.235371, 19.271389

| run | status | lc (mm) | nodes | tets | DOF | f1..f4 (GHz) | max |rel analytic err| | max |rel change vs prev| | max bkwd err | Palace s |
|---|---|---|---|---|---|---|---|---|---|---|
| ladder-L1 | CONVERGED | 1.8333 | 443 | 1200 | 9848 | 9.635896, 15.235451, 15.235704, 19.272299 | 4.72e-05 | - | 2.02e-11 | 28.7 |
| ladder-L2 | CONVERGED | 1.2222 | 925 | 2566 | 20936 | 9.635693, 15.235332, 15.235389, 19.271519 | 6.75e-06 | 4.05e-05 | 2.10e-11 | 69.7 |
| ladder-L3 | CONVERGED | 0.9167 | 1560 | 4561 | 36708 | 9.635690, 15.235327, 15.235328, 19.271249 | 7.27e-06 | 1.40e-05 | 3.48e-11 | 64.4 |

Degenerate (1,2,0)/(2,1,0) pair (numerical splitting of an exact degeneracy, not physical coupling):

| run | mode a (GHz) | mode b (GHz) | centre (GHz) | splitting (MHz) | relative |
|---|---|---|---|---|---|
| ladder-L1 | 15.235451 | 15.235704 | 15.235578 | 0.253 | 1.66e-05 |
| ladder-L2 | 15.235332 | 15.235389 | 15.235361 | 0.057 | 3.75e-06 |
| ladder-L3 | 15.235327 | 15.235328 | 15.235327 | 0.001 | 9.32e-08 |

finest error 7.275e-06, final-two-level change 1.403e-05, all levels CONVERGED

## Objective 2: height sensitivity (p >= 1 modes)

### object001_height: Object 001 box (22 x 22 x 1.5 mm against 1.65 mm)

Verdict **BLOCKED**. no attempted run converged within its budget; 1.5 L1: RUN_FAILED (PalaceRunFailed: Palace exceeded the 3600s timeout; the container qmhp-palace-RUN-PALACE-V); 1.65 L1: RUN_FAILED (PalaceRunFailed: Palace exceeded the 3600s timeout; the container qmhp-palace-RUN-PALACE-V)

- mode (0, 1, 1), heights [1.5, 1.65] mm, exact f {'1.5': 100.16282722306777, '1.65': 91.10134603292212}, Δf_exact -9.06148 GHz (-9.047%)

### aux_height: AUXILIARY taller box (22 x 22 x 7.0 mm against 7.7 mm); not a verification of Object 001

Verdict **PASS**. Δf_Palace -1.84673 GHz vs Δf_exact -1.84662 GHz (disagreement 6.20e-05); |Δf_exact| is 793x the numerical uncertainty

- mode (0, 1, 1), heights [7.0, 7.7] mm, exact f {'7': 22.47157905592814, '7.7': 20.624961993474823}, Δf_exact -1.84662 GHz (-8.218%)
- L1 (lc [1.75, 1.8333333333333333] mm): f_Palace [22.47459, 20.627728] GHz, Δf_Palace -1.84686 GHz
- L2 (lc [1.1666666666666667, 1.222222222222222] mm): f_Palace [22.472261, 20.62553] GHz, Δf_Palace -1.84673 GHz
- finest level L2: Δf_Palace -1.84673 vs Δf_exact -1.84662 GHz, relative disagreement 6.198e-05; numerical uncertainty 2.329e-03 GHz (max change of the identified mode between the final two mesh levels, over both heights); |Δf_exact|/uncertainty = 792.9

## Runs

| run | role | status | lc (mm) | tets | DOF (est.) | DOF | Palace s | failure |
|---|---|---|---|---|---|---|---|---|
| ladder-L1 | mesh_ladder | CONVERGED | 1.8333 | 1200 | 9840 | 9848 | 28.7 |  |
| ladder-L2 | mesh_ladder | CONVERGED | 1.2222 | 2566 | 21041 | 20936 | 69.7 |  |
| ladder-L3 | mesh_ladder | CONVERGED | 0.9167 | 4561 | 37400 | 36708 | 64.4 |  |
| aux_height-d7-L1 | height | CONVERGED | 1.7500 | 3479 | 28528 | 25478 | 73.9 |  |
| aux_height-d7.7-L1 | height | CONVERGED | 1.8333 | 3206 | 26289 | 23468 | 54.4 |  |
| aux_height-d7-L2 | height | CONVERGED | 1.1667 | 10692 | 87674 | 74714 | 216.4 |  |
| aux_height-d7.7-L2 | height | CONVERGED | 1.2222 | 10093 | 82763 | 70712 | 162.9 |  |
| object001_height-d1.5-L1 | height_exploratory | RUN_FAILED | 0.5000 | 31831 | 261014 | None | - | PalaceRunFailed: Palace exceeded the 3600s timeout; the container qmhp-palace-RUN-PALACE-VERIFY-20260915T115901Z-object0 |
| object001_height-d1.65-L1 | height_exploratory | RUN_FAILED | 0.5500 | 26188 | 214742 | None | - | PalaceRunFailed: Palace exceeded the 3600s timeout; the container qmhp-palace-RUN-PALACE-VERIFY-20260915T115901Z-object0 |
| object001_height-d1.5-L2 | height_rule | BLOCKED | 0.3750 | 66503 | 545325 | None | - | estimated 545325 DOF exceeds the declared runner budget of 400000; mesh kept, Palace not launched |
| object001_height-d1.65-L2 | height_rule | BLOCKED | 0.4125 | 56055 | 459651 | None | - | estimated 459651 DOF exceeds the declared runner budget of 400000; mesh kept, Palace not launched |

Every number above is a numerical-verification result for the empty PEC box. It says nothing about the physical package.
