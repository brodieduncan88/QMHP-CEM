# Numerical plan for the coupled-candidate extraction campaign (predeclared)

**Status:** checkpoint-A predeclaration. Nothing below has been executed.
Every limit is an ENGINEERING-RULE of numerical verification and is written
down before any coupled solve so that it cannot be tuned to a result. The
plan is for the first executable candidate S1 (`{F1, R1}` in the bounded chip
cell, see `README.md`); the full five-mode structure inherits the same rules
with the larger node set and is not executable until its parameters are
bound.

## 1. Decision-relevant frequency bands

| band | range | why it is sufficient |
|---|---|---|
| Route A eigenmode band | 0.5 GHz – 9.0 GHz | contains the fluxonium harmonic mode (2.75 GHz for the nominal `E_C`, `E_L`; ±30 % for the seed geometry gives 1.9–3.6 GHz), the readout mode (4.30 GHz nominal, ±15 % for the seed: 3.7–5.0 GHz), the readout's second harmonic region (λ/4 line: 3 × f₀ ≈ 12.9 GHz lies **above** the band and is the first hidden resonator mode, screened by 2×f₀ margin), and stays below the first measured Object 001 package mode (9.636 GHz, `results/PALACE-GOLDEN-*`). The ceiling 9.0 GHz is chosen so that the band ends below the first package mode; a chip-cell mode found between 5.0 and 9.0 GHz is a reportable hidden mode |
| Route B driven band | 0.1 GHz – 9.0 GHz, adaptive sweep | the low edge gives the static (`jωC`) limit of the admittance with `ωL_R`-independent slope; the same ceiling as Route A so both routes screen the same window; at least 12 points per readout linewidth-equivalent (the pole is lossless, so the fit uses the analytic pole/zero structure, not a linewidth) and a dense grid (≤ 10 MHz spacing) within ±200 MHz of every pole identified by the fit's first pass, the pass being the adaptive sweep's own error indicator, never Route A's frequencies |
| Full five-mode band (not executable now) | 0.1 – 9.0 GHz plus the mediator region 6–8 GHz | the reported `f_22 ≈ 7.016 GHz` (reported, not reproduced) lies inside; still below the package mode |

## 2. Mode identification and hidden-mode screening

- Route A classifies every eigenmode in the band by (i) the inductive
  participation of the F1 site (`p_mF`), (ii) the probe polarisation
  fractions at three declared probe points (over the pad, over the resonator
  open end, over the resonator mid-length), (iii) its frequency against the
  analytic estimates. A mode is "readout-like" if its resonator-probe energy
  dominates and `p_mF < 0.5`, "fluxonium-like" if `p_mF ≥ 0.5`, otherwise
  **hidden** and reported. Any hidden mode below 9.0 GHz is listed with its
  frequency and participation; the S1 single-mode representation is declared
  invalid (extraction INCOMPLETE) if a hidden mode lies within 1.0 GHz of the
  readout mode **or** carries `p_mF ≥ 0.05`.
- Route B screens by the number of poles the rational fit needs: the fit is
  run at the declared order (one pole in band for S1) and at order + 1; if
  the higher order reduces the residual by more than a factor 10, an
  unmodelled pole exists in band and is reported as a hidden mode; the
  extraction is INCOMPLETE unless the extra pole is above 9.0 GHz or is
  identified with a declared structure.
- The two screens are independent; a hidden mode found by one and not the
  other is itself a reportable disagreement.

## 3. Refinement ladders

| ladder | levels | what converges | rule |
|---|---|---|---|
| Route A mesh | `h0`, `h0/1.5`, `h0/2` of the declared rule (gap-resolving size field: 2 elements across the narrowest declared gap at `h0`, box rule `min(a,b)/12` far from conductors) | eigenfrequencies, `p_mF`, derived `E_C` entries | frequencies: final-two-level relative change ≤ 1e-4 (existing rule); `E_C,FR`, `E_C,FF`: final-two-level relative change reported and used as the resolution floor `δ_A`; no threshold on `E_C` is invented |
| Route B mesh | its own `h0`, `h0/1.5` (minimum two levels; `h0/2` if the budget allows) | pole frequency, low-frequency capacitance slope, derived `E_C` | pole: ≤ 1e-4 relative change; `E_C`: change reported, floor `δ_B,mesh` |
| Route B response fit | fit order `n`, `n+1`; adaptive sweep tolerance `1e-2`, `1e-3` | fitted `E_C`, `L_R` | change between the two tolerances and the two orders reported; floor `δ_B,fit`; `δ_B = max(δ_B,mesh, δ_B,fit)` |
| Chip-cell size (suitability, not extraction) | box 4 × 4 mm and 6 × 6 mm at `h0` | `E_C,FF`, `E_C,FR`, readout frequency | change reported as the wall-proximity uncertainty of the bounded model; it is **not** part of the route disagreement and is listed under omitted effects |
| Element order | 2 preferred; 1 only if the dry-run DOF estimate at `h0/2` exceeds the budget with order 2 | | the order is fixed by the mesh dry run **before** any solve and is the same for both routes |

## 4. Uncertainty and resolution checks

For each required pair (S1: F1–R1) and each route: value, `δ` as defined in
`coupling-definition.md` §9, status RESOLVED / UNRESOLVED / MISSING. The 10 %
comparison is made only between two RESOLVED values. The record also carries
the backward errors (Route A, existing ≤ 1e-6 rule), the adaptive-sweep error
indicator and per-frequency residuals (Route B), and the fit residual.

## 5. Candidate suitability checks (separate from agreement)

Reported as information after both routes exist: `E_C,F1F1` against 0.60 GHz,
bare readout root against 4.301974466 GHz, `|g|` against 0.150 GHz, the
chip-cell wall sensitivity from the box-size ladder, the list of omitted
effects, and whether the seed geometry's `C_Σ` includes a declared `C_J`.
No suitability threshold is attached at this checkpoint; the frozen σ = 2 %
tolerance scale is printed next to the `E_C` deviation as context only.

## 6. Compute budget (GitHub-hosted runner, no purchased compute)

Measured references from the executed campaigns: order-2 DOF ≈ 8.2 per
tetrahedron; 36.7 k DOF eigenmode solve ≈ 60 s; 74.7 k DOF ≈ 190 s; the two
≈ 260 k / 215 k DOF attempts did **not** finish in 3600 s. The runner has one
MPI process, one thread, and a 6 h job ceiling.

| limit | value |
|---|---|
| DOF per solve | ≤ 250 000 (below the level that timed out; the 400 k declared budget of the verification campaign is retained as the hard ceiling for the mesh dry run only) |
| Route A per solve | ≤ 45 min wall clock, killed at the limit, recorded as RUN_FAILED |
| Route B per excitation | ≤ 60 min wall clock (adaptive sweep), killed at the limit |
| Route A total | 3 levels × 1 solve ≤ 2.0 h |
| Route B total | 2 levels × 2 excitations (F1 site, readout tap) + fit tolerances ≤ 3.0 h; the fit tolerance ladder reuses the same solves where Palace allows, otherwise the second tolerance runs only at the finest level |
| Box-size ladder | 1 extra Route A solve at `h0` ≤ 30 min |
| Total solver time | ≤ 5.5 h across two workflow jobs (Route A job, Route B job), each ≤ 3.5 h so that it fits the 6 h ceiling with the image build and evidence steps |
| Memory | the runner's 16 GB; a solve is declared over budget if the dry-run estimate exceeds 250 k DOF, and is not launched |
| Evidence finalisation | 30 min per job reserved outside the solver budget: parsing, fitting, manifests, `cem verify-results`, commit; the solver timeouts are set so that this reserve is never consumed by a solve |

Exceeding a per-case limit yields RUN_FAILED with the mesh, deck and log
kept; exceeding the DOF limit at dry run yields BLOCKED before launch, with
the mesh kept, as in the verification campaign. Neither is silently retried
with a coarser mesh: a coarser ladder is a new declared plan.

## 7. Order of execution and what is decided when

1. Mesh dry run of the declared S1 geometry at `h0`, `h0/1.5`, `h0/2`
   (this checkpoint, offline): tets, DOF estimate for order 2 and 1, gap
   resolution report. Decides the element order and whether the ladder fits
   the budget. If not, the disposition is BLOCKED with the numbers.
2. Route A ladder, then Route A inversion; Route B ladder, then Route B fit;
   the two run in separate workflow jobs writing separate records.
3. Comparison, suitability report, per-interaction record, gate evaluation.
   Only then is any coupled value written into `QuantumResults`.
