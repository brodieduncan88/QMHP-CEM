# Two independent extraction routes (checkpoint A)

**Status:** checkpoint-A definition, frozen for review; nothing executed.
Both routes estimate the target of `coupling-definition.md` §3: the
charging-energy matrix `E_C` of the declared nodes and the bare readout-mode
parameters, from which the per-pair coefficients `g_kR`, `J_kl` follow.
Neither route may read the other's coupling, intermediate or final. The
Palace facts cited below are checked against the pinned v0.13.0 documentation
and source (commit a61c8cbe, image `qmhp-cem/palace:0.13.0`); see §5 for the
exact features and output files relied on.

## 1. What is common to both routes (and therefore not tested by agreement)

Shared inputs (identical files, hashed into both records):

- the declared geometry, materials and boundary conditions, and the mesh
  family generated from them (the two routes may run at different refinement
  levels, but from the same mesh generator and the same CAD);
- the declared node set, port locations, port orientations, reference planes
  and the lumped-element site geometry;
- the declared lumped values `E_J`, `E_L`, `f_C`, non-geometric capacitances;
- the algebra of `coupling-definition.md` §3 that turns `(E_C, E_L,R)` into
  `g`, `J`;
- the single-mode representation of each readout resonator;
- Palace itself (one binary, one image) and MFEM's Nédélec discretisation.

Common-mode errors that agreement between the routes will **not** detect:

1. geometry that is not the intended device (wrong electrode dimension,
   substrate thickness, box size, missing conductor);
2. a port placed or oriented so that it does not represent the junction
   branch (wrong reference plane, wrong node pairing);
3. a missing or mis-declared non-geometric capacitance (`C_J`);
4. physics absent from the EM model by declaration: kinetic inductance,
   superinductor array modes, package coupling outside the bounded box,
   dielectric loss, TLS, flux-line/feedline structures not modelled;
5. the single-mode approximation of a resonator whose second mode is close;
6. the conversion algebra and its unit conventions (a shared factor of two
   or of 2π is invisible to the comparison);
7. any discretisation error that is the same on both routes' meshes;
8. Palace-level errors common to both solvers (material assignment, PEC
   assignment).

Items 1–3 and 6 are covered by the offline declaration checks and by the
planned deck-reaching tests; 4 and 5 by the hidden-mode screening of the
numerical plan; 7 by using independent convergence evidence per route.

## 2. Route A — eigenmode / participation extraction

### 2.1 EM model

Palace `Problem.Type = "Eigenmode"` on the declared model, with each
nonlinear element site carrying a **lumped inductive port** whose inductance
is the declared *linear* inductance of that branch:

- fluxonium site `F_k`: `L = L_super = 103.46 nH` (superinductor only; the
  small junction is open, section 8 of the definition);
- mediator site `C` (full structure only): `L = L_C(f_C)`;
- readout modes: no lumped element, they are distributed conductors of the
  model;
- optional readout feedline port: **absent** in Route A (a resistive port
  would make the eigenproblem lossy; Q is not a target here).

Requested: all eigenmodes in the decision band `[f_lo, f_hi]` of the
numerical plan (for S1: every mode below the first Object 001 package mode,
i.e. the fluxonium harmonic mode near 2.75 GHz, the readout mode near
4.30 GHz, and anything else the environment produces below the screen
ceiling), with the mode count and target chosen from the analytic estimate
of the numerical plan, not from the solver's answer.

### 2.2 Data taken from the solve

For each mode `m` in the band: the eigenfrequency `f_m` (from `eig.csv`),
its backward error (existing rule: ≤ 1e-6), and for each lumped inductive
port `j` the **energy-participation ratio** `p_mj` = inductive energy stored
in `L_j` divided by the total inductive energy of the mode (Palace's
`port-EPR.csv`, see §5). Field probes (`probe-E.csv`) at declared points
classify each mode (fluxonium-like, readout-like, other) independently of its
frequency, as in the verification campaign.

### 2.3 Inversion to the node basis (the "participation-based" step)

The linear circuit of `coupling-definition.md` §2 with the lumped inductances
attached is `H_lin = ½ Qᵀ C⁻¹ Q + ½ Φᵀ L⁻¹ Φ` on the node set `𝒩`, with
`L⁻¹ = diag(1/L_j)` for the lumped sites and `(E_L,R)` for the readout
single-mode nodes. Its normal modes satisfy

```
C⁻¹ L⁻¹ u_m = ω_m² u_m            (u_m: node-flux pattern of mode m)
```

and the participation of lumped inductor `j` in mode `m` is

```
p_mj = (u_mj² / L_j) / (u_mᵀ L⁻¹ u_m)
```

which is exactly what the EM solver reports as the EPR of that element. The
unknowns are the symmetric `C⁻¹` (`N(N+1)/2` entries) and the readout
inductances `L_R` (one per readout node); the data are the `M` band
frequencies and the `M × N_lumped` participations, with the sum rule
`Σ_j p_mj + p_m,dist = 1` per mode. For S1 (`N = 2`, one lumped inductor,
`M = 2` modes) the four data `(f_+, f_−, p_+F, p_−F)` determine the four
unknowns `((C⁻¹)_FF, (C⁻¹)_FR, (C⁻¹)_RR, L_R)` in closed form:

```
ω_±² = eigenvalues of  C⁻¹ diag(1/L_F, 1/L_R)
p_±F = (u_±F² / L_F) / (u_±F²/L_F + u_±R²/L_R)
```

solved by the deterministic procedure in `models/coupling_extraction.py`
(planned: `invert_participations`). For the full structure the same
equations are solved in least squares with the sum rules as constraints; the
residual is part of the resolution floor (definition §9). The declared
`L_j` are then discarded: `E_C = (e²/2) C⁻¹` and `(E_C,RR, E_L,R)` are the
route's output. The fluxonium's linear inductance never appears in the
output; the harmonic mode near 2.75 GHz exists only inside the EM model.

### 2.4 Independent convergence evidence

Route A carries its own ladder: at least three meshes (`h0`, `h0/1.5`,
`h0/2` of the declared mesh rule) with the existing mesh-convergence rules
(finest relative change ≤ 1e-4 for the frequencies) **and** a declared rule
for the participations (relative change between the final two levels
reported; the resolution floor of each derived `E_C,kl` is the change of that
entry between the final two levels). Convergence is judged on the frequencies
and on the derived `E_C`, not on the coupling coefficient alone.

## 3. Route B — driven-response / impedance extraction

### 3.1 EM model

Palace `Problem.Type = "Driven"` on the **same declared model** with the
nonlinear element sites as **lumped ports without any inductance**
(`R` reference only, so that the environment is excited and observed at the
exact site the branch will occupy), and the readout feedline port present as a
resistive 50 Ω lumped port at its declared reference plane. No lumped
inductance is attached anywhere: the driven solve sees the passive
capacitive/distributed environment only.

Every declared port is excited in turn (one excitation per driven solve, or
Palace's multi-excitation form if the pinned version supports it, §5), over
the decision band with the adaptive sweep of the numerical plan, and the
complex port voltages and currents of **all** ports are recorded for each
excitation. This is the "all required port excitations and complex response
data" of the milestone: with `P` ports the record holds `P` excitations ×
`P` responses × the frequency grid, as complex values.

### 3.2 Data taken from the solve

The complex impedance matrix on the frequency grid,

```
Z_ij(f) = V_i(f) / I_j(f)   with excitation on port j only,
```

or equivalently the admittance `Y(f) = Z(f)⁻¹`, and the scattering matrix
`S(f)` on the ports' reference impedances (Palace's `port-S.csv`), which is
kept as evidence but is not the fitted object. Adaptive-sweep error
indicators and the linear-solver residual per frequency are recorded.

### 3.3 Fit to the lumped model (the "black-box" step)

The environment admittance at the element sites is fitted, in the band, to
the rational form of the declared lumped circuit with all inductive branches
removed:

```
Y(f) = j ω C_∞ + Σ_R  j ω C_R,c(f)  /  (1 − (ω/ω_R)²)  + (feedline term)
```

i.e. a Foster-type expansion whose poles are the readout modes and whose
low-frequency limit `Y → jω C_∞` is the site-to-site capacitance matrix with
the resonators' inductive branches open. Concretely for S1 with the fluxonium
site port `F` and the resonator represented by its coupling to `F`:

- the low-frequency slope of `Im Y_FF` and of the off-diagonal block gives
  the Maxwell entries `C_FF + C_c`, `C_c`, and, with the feedline port, the
  resonator's static capacitance to ground;
- the pole of `Y_FF(f)` at `ω_p² = 1/(L_R (C_R + C_c))` and the zero at
  `ω_z² = 1/(L_R C_R)` fix `L_R` and the split of `C_R` versus `C_c`; the
  residue at the pole is the black-box-quantization participation of the site
  in the readout mode (Nigg et al. form: `Z_FF(ω)` poles and residues give
  `ω_R` and the site's effective impedance in that mode).

The fit is a deterministic vector-fitting / rational least squares over the
recorded complex `Y(f)` with the model order fixed by the declared mode
count (one readout pole for S1), never chosen from the data. Its residual, the
change between two consecutive fit orders and between two mesh levels give
this route's resolution floor. The output is again `C⁻¹`, `E_C` and
`(E_C,RR, E_L,R)` in the node basis.

### 3.4 Independent convergence evidence

Route B has its own mesh ladder (same generator, its own levels) and a
response-fit ladder (fit order, frequency-grid density of the adaptive sweep,
band edges); the frequency of the readout pole and the extracted `E_C`
entries must change by less than the declared rule between the final two
levels of each ladder. Route B never reads `eig.csv`; Route A never reads
`port-*.csv`.

## 4. Why the two routes are genuinely separate

| | Route A | Route B |
|---|---|---|
| Palace problem | Eigenmode (generalised eigenproblem, shift-invert) | Driven (linear solves at many frequencies, adaptive) |
| Lumped inductances in the EM model | attached, then removed analytically | never attached |
| Primary data | real eigenfrequencies + inductive energy participations | complex port voltages/currents on a frequency grid |
| Extraction step | algebraic inversion of the normal-mode problem | rational fit of the admittance (poles, zeros, low-frequency slope) |
| Numerical error sources | eigen-solver tolerance, mode identification, energy postprocessing | frequency sampling, adaptive error, fit conditioning |
| Reads the other route's output | no | no |

They share the geometry and the conversion algebra (§1), which is why
agreement is evidence about the numerical extraction, not about the physical
model.

## 5. Palace v0.13.0 features relied on

[This section is completed from the pinned documentation read in this
checkpoint; every entry cites the file at tag v0.13.0. See the table in
`README.md` §"Palace feature check" once filled.]

## 6. Treatment of the nonlinear fluxonium

Neither route linearises the small junction. Route A's only linear inductance
at a fluxonium site is the superinductor, which is the harmonic basis in which
the Master's fluxonium is routinely diagonalised (`√(8 E_L E_C) = 2.75 GHz`
for the nominal device); that mode is a computational device of Route A and
is removed by the inversion. The extracted `E_C` then enters the frozen
fluxonium Hamiltonian on the 3201-point grid, so the fluxonium is treated
exactly (to grid convergence) and the weakly-anharmonic approximation is used
for **no** Branch-A element. The mediator, if and when its parameters are
bound, is a transmon-regime element for which the linear-inductance
attachment in Route A is within its regime; its nonlinearity is still applied
in circuit space only.
