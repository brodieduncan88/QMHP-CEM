# Two independent extraction routes (checkpoint A)

**Status:** checkpoint-A definition, frozen for review; nothing executed.
Both routes estimate the target of `coupling-definition.md` §3: the
gauge-invariant triple `{E_C,F1F1, f_R1, g_F1R1}` for S1, and in general the
charging energies of the nodes that carry a declared lumped branch, each
readout mode's bare frequency `f_R`, and the invariant coefficient `g_kR` or
`J_kl` of every required pair. The individual readout-node entries
`E_C,kR`, `E_C,RR` and `L_R` are not identifiable and are not estimated
([`route-a-identifiability.md`](route-a-identifiability.md)).
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
- the algebra of `coupling-definition.md` §3 that turns the circuit
  quantities into the invariant coefficients `g`, `J`;
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
port `j` the **energy-participation ratio** `p_mj` as Palace v0.13.0 defines
it (`port-EPR.csv`, §5):

```
p_mj = sign(Re I_mj) · ½ L_j |I_mj|² / (E_elec,m + E_cap,m),   I_mj = V_mj / (i ω_m L_j)
```

i.e. the inductive energy in `L_j` normalised by the mode's **electric-side**
energy (field plus lumped-capacitor energy). For a lossless mode at resonance
`E_elec + E_cap = E_mag + E_ind`, so this equals the inductive participation
used in the inversion below; the record keeps `domain-E.csv` (`E_elec`,
`E_mag`, `E_cap`, `E_ind` per mode) so that the equipartition
`|E_elec + E_cap − E_mag − E_ind| / E_total` is checked per mode and reported
(a mode violating it beyond the eigen tolerance is flagged, not used). Field
probes (`probe-E.csv`) at declared points classify each mode (fluxonium-like,
readout-like, other) independently of its frequency, as in the verification
campaign.

### 2.3 Inversion of the normal-mode problem (the "participation-based" step)

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
raw unknowns, *before the gauge is fixed*, are the symmetric `C⁻¹`
(`N(N+1)/2` entries) and the readout inductances `L_R` (one per readout
node); the data are the `M` band frequencies and the `M × N_lumped`
participations, with the sum rule `Σ_j p_mj + p_m,dist = 1` per mode.

For S1 (`N = 2`, one lumped inductor, `M = 2` modes) the data are **three**
independent numbers, `f_+`, `f_−` and one participation, since
`p_−F = 1 − p_+F`; and with `L_F` declared the circuit has **three**
gauge-invariant degrees of freedom, one readout-node gauge direction having
removed the fourth. They determine the invariant triple
`{E_C,F1F1, f_R1, g_F1R1}` in closed form. A representative
`((C⁻¹)_FF, (C⁻¹)_FR, (C⁻¹)_RR, L_R)` can be written down only after a
readout-node gauge is fixed, and the implementation fixes `L_R = 1 H` purely
to have one to write:

```
ω_±² = eigenvalues of  C⁻¹ diag(1/L_F, 1/L_R)
p_±F = (u_±F² / L_F) / (u_±F²/L_F + u_±R²/L_R)
```

solved in closed form by `models/route_a_inversion.py` (`invert_two_node`),
which is implemented and demonstrated on synthetic circuits with known
parameters (`route-a-identifiability.md`). Two points that section establishes
and that this one previously got wrong:

- the two participations are **not** independent, because both sum rules hold,
  so the data are three numbers, not four, and the system is exactly
  determined rather than over-determined; the second participation is checked,
  not consumed;
- the readout node carries no lumped element, so `E_C,kR`, `E_C,RR` and `L_R`
  are **not identifiable**: the route returns the gauge-invariant triple
  `{E_C,F1F1, f_R1, g_F1R1}`, and shows any readout-node entry only in a
  stated gauge.

For the full structure the same equations are solved in least squares with the
sum rules as constraints and one gauge fixed per readout node; the residual is
part of the resolution floor (definition §9). The declared `L_j` are then
discarded. The fluxonium's linear inductance never appears in the
output; the harmonic mode near 2.75 GHz exists only inside the EM model.

### 2.4 Independent convergence evidence

Route A carries its own ladder: at least three meshes (`h0`, `h0/1.5`,
`h0/2` of the declared mesh rule) with the existing mesh-convergence rules
(finest relative change ≤ 1e-4 for the frequencies) **and** the energy
participation, whose relative change between the final two levels is reported
and is the dominant term in the resolution floor of `g`. The measured
propagation (`route-a-identifiability.md` §6) is that the relative error on
`g` tracks the relative error on the participation roughly one-for-one and is
almost insensitive to the frequency error, so the participation is what the
Route A ladder must be judged on; about 1 % relative is needed for a 1 %
Route A floor on `g`. Convergence is judged on the frequencies, the
participation and the derived invariants, never on the coupling alone.

## 3. Route B — driven-response / impedance extraction

### 3.1 EM model

Palace `Problem.Type = "Driven"` on the **same declared model** with the
nonlinear element sites as **purely resistive lumped ports** (`R > 0`,
`L = C = 0`, which is what Palace v0.13.0 requires of an excited lumped port,
§5), so that the environment is excited and observed at the exact site the
branch will occupy, and the readout tap port present as a resistive lumped
port at its declared reference plane. No lumped inductance is attached
anywhere: the driven solve sees the passive capacitive/distributed
environment, terminated by the declared port resistances, which the S→Z
conversion below removes exactly.

At v0.13.0 several excited ports superpose into one right-hand side and
suppress `port-S.csv`, so the route runs **one Palace driven solve per
excited port** (`P` solves for `P` ports), each over the decision band with
the adaptive sweep of the numerical plan. For each solve the record keeps the
generalised scattering column `S_ij(f)` for every port `i` (`|S| dB` and
`arg S` degrees, 9 significant digits each, reconstructed to a complex value
by the parser) and the complex port voltages and currents (`port-V.csv`,
`port-I.csv`). This is the "all required port excitations and complex
response data" of the milestone: with `P` ports the record holds `P`
excitations × `P` responses × the frequency grid, as complex values, plus
the incident amplitudes `V_inc`, `I_inc` of the excited port.

### 3.2 Data taken from the solve

The complex generalised scattering matrix `S(f)` assembled column by column
from the `P` solves, with the diagonal reference matrix `R = diag(R_i)` of the
declared port resistances (Palace references each port to its own `R_i`,
§5). The impedance and admittance matrices of the linear environment follow
exactly, for real references, from

```
Z(f) = R^{1/2} (I + S(f)) (I − S(f))⁻¹ R^{1/2},      Y(f) = Z(f)⁻¹ ,
```

so the port terminations are removed analytically and `Z`, `Y` describe the
open environment between the port terminals. Palace's `port-V.csv` /
`port-I.csv` are kept as evidence and used for a consistency check
(`I_i = V_i / R_i` on every port, `V_j / V_inc,j` against `1 + S_jj`), but
they are not the fitted object, because at v0.13.0 the reported current is
the current through the port's own load, not an independent measurement.
Adaptive-sweep error indicators, the number of sampled points and the
linear-solver iteration counts per frequency are recorded.

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
this route's resolution floor.

**Route B's output is the same invariant triple as Route A's**, and for the
same reason. The pole and zero of `Y_FF` fix the *product* `L_R(C_R + C_c)`
and `L_R C_R`, never `L_R` and the capacitances separately: rescaling the
readout node moves `L_R`, `C_R` and `C_c` together and leaves every fitted
pole, zero and residue unchanged. What the fit determines without a
convention is the site capacitance `E_C,F1F1`, the pole frequency `f_R1`, and
the residue at the pole, which is the invariant coupling `g_F1R1`. Any
readout-node capacitance or inductance the fit reports is stated in, and only
meaningful in, a declared gauge, and is never compared between the routes
(`route-a-identifiability.md`).

### 3.4 Independent convergence evidence

Route B has its own mesh ladder (same generator, its own levels) and a
response-fit ladder (fit order, frequency-grid density of the adaptive sweep,
band edges); the frequency of the readout pole and the extracted invariants
`{E_C,F1F1, f_R1, g_F1R1}` must change by less than the declared rule between
the final two levels of each ladder. No convergence rule is stated on a
gauge-dependent entry, because such a rule would be untestable: the entry
follows whatever normalisation the fit happens to use. Route B never reads `eig.csv`; Route A never reads
`port-*.csv`.

## 4. Why the two routes are genuinely separate

| | Route A | Route B |
|---|---|---|
| Palace problem | Eigenmode (generalised eigenproblem, shift-invert) | Driven (linear solves at many frequencies, adaptive), one solve per excited port |
| Lumped elements in the EM model | inductive ports, removed analytically | resistive ports, removed by the S→Z conversion |
| Primary data | real eigenfrequencies + energy participations | complex generalised S columns on a frequency grid |
| Extraction step | algebraic inversion of the normal-mode problem | rational fit of the admittance (poles, zeros, low-frequency slope) |
| Output | the invariant triple `{E_C,F1F1, f_R1, g_F1R1}` | the same invariant triple |
| Numerical error sources | eigen-solver tolerance, mode identification, energy postprocessing | frequency sampling, adaptive error, dB/degree quantisation, fit conditioning |
| Reads the other route's output | no | no |

They share the geometry and the conversion algebra (§1), which is why
agreement is evidence about the numerical extraction, not about the physical
model.

## 5. Palace v0.13.0 features relied on (checked against the pinned tree)

Checked in this checkpoint against tag `v0.13.0` (commit
`a61c8cbe0cacf496cde3c62e93085fae0d6299ac`, the commit the image is built
from). File paths are relative to the Palace repository at that tag; line
numbers refer to that revision. Nothing below was verified by executing
Palace; column headers are transcribed from the format strings in the
source.

| feature | status at v0.13.0 | where |
|---|---|---|
| Lumped port with circuit `R`, `L`, `C` (exactly one of the circuit or surface sets nonzero), multi-element ports, planar rectangular elements, `Direction` within 1° of a bounding-box axis | supported | `docs/src/config/boundaries.md` L248-345; `palace/models/lumpedportoperator.cpp` L19-107; `palace/fem/lumpedelement.cpp` L23-59 |
| Eigenmode solve with lumped inductive ports; `eig.csv` columns `m, Re{f} (GHz), Im{f} (GHz), Q, Error (Bkwd.), Error (Abs.)` | supported | `palace/drivers/eigensolver.cpp` L386-451 |
| `port-EPR.csv` (`m, p[j]` for every port with `|L| > 0`), `p_mj = sign(Re I)·½L|I|²/(E_elec+E_cap)` | supported; normalisation is electric-side energy | `eigensolver.cpp` L335-358, L554-592; `palace/models/postoperator.cpp` L644-660; `docs/src/reference.md` L264-299 |
| `domain-E.csv` with `E_elec, E_mag, E_cap, E_ind` per mode / frequency | supported | `palace/drivers/basesolver.cpp` L352-428 |
| Driven solve, uniform or adaptive sweep (`MinFreq`, `MaxFreq`, `FreqStep` in GHz, `AdaptiveTol > 0`, `MinFreq > 0` required by lumped-port postprocessing) | supported | `docs/src/config/solver.md` L164-210; `drivensolver.cpp` L40-105, L390-403; `postoperator.cpp` L446-448 |
| Excitation: an excited lumped port must be purely resistive; several excited ports superpose and **suppress `port-S.csv`**; a full matrix needs one run per excited port | partial (one run per excitation) | `drivensolver.cpp` L54-97, L651-680; `lumpedportoperator.cpp` L35-49; `docs/src/guide/problem.md` L58-99 |
| `port-S.csv`: `f (GHz)` then `|S[i][j]| (dB)`, `arg(S[i][j]) (deg.)` per port `i` for the single excited `j`; generalised S referenced to each port's own `R_i` (`S_ij·√(R_j/R_i)`), unit incident power | supported (magnitude/phase only) | `drivensolver.cpp` L730-757; `postoperator.cpp` L527-550; `reference.md` L192-198 |
| `port-V.csv`, `port-I.csv`: complex peak `V_i`, `I_i` for every port plus `V_inc`, `I_inc` of the excited port; `I_i` is the current through the port's own `R/L/C` branch | supported (load-terminated currents) | `drivensolver.cpp` L513-649; `postoperator.cpp` L430-471 |
| `port-Z.csv`, `port-Y.csv` | **absent** (tree grep negative); Z/Y derived from S as in §3.2 | whole `palace/` tree at v0.13.0 |
| Electrostatic `Terminal` boundaries → `terminal-C.csv` (Maxwell matrix, F), `terminal-Cinv.csv`, `terminal-Cm.csv` | supported; **not used as a route** (spec §5.5 names eigenmode and `Z(ω)`); available only as an optional informational cross-check that feeds neither route | `palace/drivers/electrostaticsolver.cpp` L124-231 |
| Field probes (`Domains.Postprocessing.Probe`, GSLIB) → `probe-E.csv` `Re{E_x[k]} (V/m)` … | supported; the image is built with GSLIB; a probe outside the mesh yields 0.0 with a log warning (checked by the parser, not silently accepted) | `palace/fem/interpolator.cpp` L14-108; `basesolver.cpp` L578-660 |
| Zero-thickness PEC sheets on internal surfaces (metal on substrate), materials with scalar or anisotropic permittivity | supported | `examples/cpw/cpw_lumped_uniform.json` L14-59; `docs/src/config/domains.md` L40-82 |
| `Active: false` ports (postprocess-only surfaces) | supported (removes L, R and C contributions) | `lumpedportoperator.cpp` L499-621; CHANGELOG 0.13.0 |
| Number format | 9 significant digits, dimensional units in headers | `basesolver.hpp` L36-44; `palace/utils/iodata.cpp` L562-618 |

## 6. Treatment of the nonlinear fluxonium

Neither route linearises the small junction. Route A's only linear inductance
at a fluxonium site is the superinductor, which is the harmonic basis in which
the Master's fluxonium is routinely diagonalised (`√(8 E_L E_C) = 2.75 GHz`
for the nominal device); that mode is a computational device of Route A and
is removed by the inversion. The extracted `E_C,F1F1` then enters the frozen
fluxonium Hamiltonian on the 3201-point grid, so the fluxonium is treated
exactly (to grid convergence) and the weakly-anharmonic approximation is used
for **no** Branch-A element. The mediator, if and when its parameters are
bound, is a transmon-regime element for which the linear-inductance
attachment in Route A is within its regime; its nonlinearity is still applied
in circuit space only.
