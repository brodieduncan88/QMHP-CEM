# QMHP-CEM v0.1 Specification

**Repository:** `QMHP-CEM`  
**Specification file:** `QMHP-CEM_v0.1_Spec.md`  
**Specification version:** `0.1.0`  
**Date:** 24 August 2026  
**Status:** AUTHORITATIVE FOR QMHP-CEM v0.1 BUILD  
**Parent technical authority:** QMHP-CoPro v1.5.8f — Master Edition (Consolidated), ADOPTED MASTER — FROZEN RELEASE

---

## 1. Purpose, scope and non-goals

### 1.1 Purpose

QMHP-CEM is the Computational Engineering Model software layer for the QMHP-CoPro research programme.

The purpose of v0.1 is to establish a reproducible engineering pipeline that can:

1. load frozen QMHP technical requirements without mutating them;
2. create typed candidate definitions;
3. generate planar and 3D engineering geometry;
4. invoke solver adapters through controlled interfaces;
5. run verified quantum-device calculations required by the engineering loop;
6. evaluate only those gates that are computationally evaluable;
7. explicitly mark hardware-dependent gates as `HARDWARE-GATED`;
8. perform deterministic parameter-grid sweeps;
9. write append-only candidate and batch results;
10. hash every decision-relevant artifact with SHA-256.

The v0.1 system is an engineering and research tool. It is not evidence that QMHP hardware works.

### 1.2 Governing principle

The software shall answer:

> Given the frozen QMHP requirements and a declared engineering candidate, what can be computed now, what passes or fails those computational requirements, and what remains hardware-gated?

It shall **not** exist to force QMHP to pass.

`NO FEASIBLE DESIGN FOUND` is a valid scientific and engineering outcome.

### 1.3 Explicit non-goals for v0.1

Do not implement:

- the full 17-qubit tile;
- automated Bayesian optimisation;
- Pareto optimisation;
- genetic optimisation;
- AI-driven geometry search;
- full processor-performance claims;
- fault-tolerance claims;
- replacement of hardware measurements with simulations;
- automatic promotion of simulation outputs to measured evidence;
- full P4, P6-E or P7 closure;
- microscopic Josephson-junction geometry in PicoGK;
- a complete fabrication process flow.

---

## 2. Authority, evidence classes and provenance

### 2.1 Technical authority hierarchy

The order of authority for v0.1 is:

1. **QMHP-CoPro v1.5.8f Master Edition** — scientific/technical authority.
2. **This specification** — software implementation authority for QMHP-CEM v0.1.
3. `master/` machine-readable files generated from this specification.
4. Code.
5. Generated outputs.

Code may not alter higher-authority objects to make a test or candidate pass.

### 2.2 Evidence/value classifications

Every important numerical value or engineering assumption shall carry one of the following classifications.

#### `MASTER-FROZEN`

A value explicitly carried by the frozen QMHP-CoPro v1.5.8f research release or its frozen verification record.

Examples:

- dressed null frequency;
- F8 Purcell weight;
- 13 MHz collision gate;
- 34 dB Purcell minimum;
- P6-E6 joint acceptance limits.

These values are immutable at runtime.

#### `VERIFIED-COMPUTATIONAL`

A regression value from the verified August 2026 computational cycle used to reproduce the frozen Master.

This classification is allowed where the consolidated Master prints fewer digits than the regression artifact.

It is computational evidence, not hardware evidence.

#### `ENGINEERING-SEED`

A bootstrap engineering assumption introduced by QMHP-CEM because the frozen Master does not define the value.

Examples:

- initial package wall thickness;
- initial SMP launch bore size;
- initial cavity height;
- initial deterministic sweep ranges.

Engineering seeds must never be described as experimentally validated or frozen QMHP requirements.

#### `SOLVED`

A value produced by a numerical solver for a declared candidate.

Examples:

- simulated S21;
- simulated eigenmode frequency;
- calculated package-mode spectrum.

#### `MEASURED`

A value originating from actual hardware measurement.

QMHP-CEM v0.1 does not manufacture `MEASURED` values.

### 2.3 Hardware boundary

No simulated or model-derived result may cause a hardware-gated gate to emit `PASS`.

For hardware-dependent gates, the only permitted v0.1 statuses are:

- `HARDWARE-GATED`
- `NOT-EVALUATED`
- `FAIL` only where the governing logic explicitly permits computational rejection before hardware.

### 2.4 Provenance digests

The provenance file shall contain at minimum:

```json
{
  "schema": "qmhp-cem.provenance/0.1.0",
  "qmhp_master_revision": "v1.5.8f",
  "qmhp_master_status": "ADOPTED MASTER — FROZEN RELEASE",
  "qmhp_master_date": "2026-08-24",
  "qmhp_master_pdf_sha256": "c59c518b3956b752abe78437bfcd7d00b30c439da6fc95a7aba176156237499e",
  "operative_base_v158e_sha256": "83aeb3a2d8ebcb8f627989557350d9c172ad5bc20c3edc561b8a5e091cc4b658"
}
```

The first digest is the SHA-256 of the current frozen v1.5.8f Master PDF used to prepare this specification.

If the project later adopts a different rendered byte sequence as the canonical frozen Master, update the provenance **only after explicitly verifying and recording the replacement digest**. Do not silently substitute it.

---

## 3. Data contracts

All Python contracts shall use Pydantic v2.

All controlled top-level records must include a string `schema` field.

Unknown fields should be rejected on core scientific records unless a contract explicitly allows extensions.

Units must be explicit.

### 3.1 Candidate

Minimum structure:

```yaml
schema: qmhp-cem.candidate/0.1.0
candidate_id: QMHP-CEM-A-RF-000001
object_type: object001_single_device_package
master_revision: v1.5.8f
classification: ENGINEERING-SEED
created_utc: 2026-08-24T00:00:00Z
parent_candidate_id: null

parameters:
  chip:
    width_mm: 20.0
    height_mm: 20.0
    thickness_mm: 0.43
  package:
    outer_width_mm: 32.0
    outer_height_mm: 32.0
    body_height_mm: 5.0
    floor_thickness_mm: 1.0
  chip_recess:
    xy_clearance_mm: 0.20
    depth_mm: 0.45
  vacuum_cavity:
    width_mm: 22.0
    height_mm: 22.0
    height_above_chip_mm: 1.50
  lid:
    thickness_mm: 2.0
  launches:
    bore_diameter_mm: 2.5
    count: 2
```

Required validation:

- candidate ID format is valid;
- dimensions are finite and positive;
- recess is larger than chip in X/Y;
- recess fits inside package;
- body height exceeds floor thickness;
- cavity leaves positive package walls;
- launch count is supported by the object generator;
- no unitless geometric dimensions.

### 3.2 SolverResults

Minimum structure:

```yaml
schema: qmhp-cem.solver-results/0.1.0
candidate_id: QMHP-CEM-A-RF-000001
solver:
  name: mock
  version: "0.1.0"
  classification: TEST_FIXTURE
run_id: RUN-...
convergence:
  status: CONVERGED
  metric: relative_change
  value: 0.0001
  tolerance: 0.001
frequency_GHz: []
s_parameters: {}
z_parameters: {}
eigenmodes: []
artifacts: []
```

The `convergence` block is mandatory for every solver result.

A solver result without convergence metadata must fail validation.

### 3.3 QuantumResults

Minimum structure:

```yaml
schema: qmhp-cem.quantum-results/0.1.0
candidate_id: QMHP-CEM-A-RF-000001
master_revision: v1.5.8f
classification: SOLVED
spectrum: {}
dressed_system: {}
purcell: {}
collision: {}
tolerance: {}
regression_status: {}
```

### 3.4 GateReport

Minimum structure:

```yaml
schema: qmhp-cem.gate-report/0.1.0
candidate_id: QMHP-CEM-A-RF-000001
master_revision: v1.5.8f
overall_status: PASS
gates:
  - gate_id: COLLISION
    status: PASS
    severity: HARD
    evidence_class: SOLVED
    measured: 18.1
    threshold: 13.0
    units: MHz
    margin: 5.1
    reason: "..."
```

Allowed gate statuses:

- `PASS`
- `FAIL`
- `INCOMPLETE`
- `HARDWARE-GATED`
- `NOT-EVALUATED`
- `NOT-APPLICABLE`
- `EXTRACTION-INCONSISTENT`

### 3.5 BatchReport

The sweep/orchestrator shall also implement a typed batch-level record:

```yaml
schema: qmhp-cem.batch-report/0.1.0
batch_id: BATCH-...
solver: mock
candidate_count: 9
pass_count: 0
fail_count: 9
hardware_gated_count: 9
batch_outcome: NO_FEASIBLE_DESIGN_FOUND
manifest_sha256: "..."
```

Allowed batch outcomes:

- `FEASIBLE_CANDIDATE_FOUND`
- `NO_FEASIBLE_DESIGN_FOUND`
- `INCOMPLETE`
- `SOLVER_FAILURE`
- `BLOCKED`

---

## 4. Frozen Master requirements and regression pins

### 4.1 Branch-A nominal device parameters

Classification: `MASTER-FROZEN`

```yaml
EC_over_h_GHz: 0.60
EJ_over_h_GHz: 5.72
EL_over_h_GHz: 1.58
phi_ext: pi
logical_states: [0, 2]
sink_state: 1
```

### 4.2 Static fluxonium calculation

Classification: `MASTER-FROZEN` / `VERIFIED-COMPUTATIONAL`

Required phase-grid convention:

```yaml
grid_points: 3201
phase_min: -8*pi
phase_max: +8*pi
kinetic_operator: second_difference
```

Frozen reference values:

```yaml
f01_GHz: 0.175710013
f02_GHz: 3.581724312
n02: numerical_floor
n12: 0.659915
sin_delta_over_2_02: 0.295705232
richardson_curvature_GHz_per_Phi0_sq: 5064.55
gamma_qp_over_xqp_per_s: 4.106e10
```

### 4.3 Eq.(7) dispersive diagnostic

Classification: `MASTER-FROZEN`

At 6.5 GHz readout diagnostic and the declared convention:

```yaml
eq7_chi_MHz:
  state_0: -5.366823
  state_1: -0.305447
  state_2: +7.214942

perturbative_root_GHz: 4.314628047
```

These are diagnostic quantities. The exact dressed root is authoritative for the operating point.

### 4.4 Exact dressed-system regression pins

Production convention:

```yaml
Nq: 10
Nph: 12
root_GHz: 4.301974466
```

High-truncation spot check:

```yaml
Nq: 14
Nph: 25
root_GHz: 4.301975383
```

Production-to-high-truncation shift is approximately +0.92 kHz and is not an error condition.

Physical pull references:

```yaml
logical_pull_MHz_master_display: -9.507
sink_pull_MHz_master_display: +8.721
sink_logical_contrast_MHz: 18.228
sink_line_GHz: 4.310696
dressed_f12_GHz: 3.395056
```

For regression testing, the verified computational artifacts may carry additional pull precision:

```yaml
logical_pull_MHz_regression: -9.507089
sink_pull_MHz_regression: +8.721155
```

Classification of the extra digits: `VERIFIED-COMPUTATIONAL`.

The consolidated Master displays the pulls rounded to three decimals; do not falsely describe the extra digits as separately printed Master values.

### 4.5 F8 Purcell regression

Classification: `MASTER-FROZEN`

Executable definition:

```text
Gamma_P = kappa(omega_if) * |<f|a|i>|^2
```

Exact dressed weight:

```yaml
f8_dressed_weight: 0.01182198
```

The following is a **different quantity** and must not be substituted:

```yaml
bare_admixture_overlap_approx: 0.011815
```

Required filter constraint:

```yaml
dressed_emission_GHz: 3.395056
minimum_stopband_dB: 34.0
target_stopband_dB: 36.0
```

### 4.6 Collision/tolerance reference

Classification: `MASTER-FROZEN` for the reporting object; `QMHP-CEM-NORMATIVE` for the new RNG convention.

Collision rule:

```yaml
minimum_abs_omega24_minus_readout_MHz: 13.0
```

Frozen ensemble reporting reference:

```yaml
pooled_rejection_rate: 0.0666
wilson_95:
  low: 0.0612
  high: 0.0721
draws: 20
devices_per_draw: 400
```

Legacy exact finite-sample identities/counts are **not** reproducibility targets.

QMHP-CEM v0.1 establishes the following new normative convention for future CEM runs:

```yaml
rng: numpy.random.default_rng
sigma_fraction:
  EC: 0.02
  EJ: 0.02
  EL: 0.02
draw_order: [EC, EJ, EL]
```

This convention must never be described as exact reproduction of legacy AMD-C finite samples.

### 4.7 QEC reference values carried for provenance/golden testing

These values are not required to make Object 001 geometry, but are retained as golden research references.

Classification: `MASTER-FROZEN`.

```yaml
branch_A_Pu_per_round: 0.00850
branch_A_Pe_per_round: 0.01543
branch_A_round_time_us: 20.0
branch_C_round_time_us_prior: 13.5

matched_hazard_ratio:
  d3:
    central: 0.94
    ci95: [0.88, 1.01]
  d5:
    central: 0.92
    ci95: [0.79, 1.08]
  d7:
    central: 1.15
    ci95: [0.97, 1.36]

ideal_free_location_HR:
  d3: 0.43
  d5: 0.20
  d7: 0.15

break_even_location_efficiency:
  d3: 0.524
  d5: 0.598
```

The correct matched-screen conclusion remains:

```text
NO SEPARATION ESTABLISHED
```

without location credit.

---

## 5. Physics-model implementation requirements

### 5.1 Fluxonium static model

Implement the verified finite-difference Hamiltonian on the declared 3201-point phase grid over `[-8π, +8π]`.

Required outputs:

- first relevant eigenfrequencies;
- charge matrix elements;
- `sin(delta/2)` matrix element;
- optional convergence diagnostics.

The implementation shall be regression-tested against §4.

### 5.2 Coupled dressed-system model

Production truncation:

- `Nq = 10`
- `Nph = 12`

Required method:

- construct coupled fluxonium-resonator Hamiltonian;
- use adiabatic maximum-overlap state labelling;
- use Eq.(7) only to seed the search;
- use `scipy.optimize.brentq` or an explicitly equivalent bracketed root solver;
- solve the logical-blind condition in the dressed system.

Support the `(14,25)` high-truncation spot check.

Required regression outputs are in §4.4.

### 5.3 F8 Purcell model

Compute the actual dressed transition matrix element:

```text
|<dressed(1,0)| a |dressed(2,0)>|^2
```

Do not implement the bare-admixture overlap as a substitute.

### 5.4 Tolerance ensemble

For new QMHP-CEM runs:

- independent Gaussian fractional perturbations;
- σ = 2% for EC, EJ, EL;
- RNG = `numpy.random.default_rng`;
- draw order = `EC -> EJ -> EL`.

The RNG seed must be recorded in every batch/candidate manifest.

### 5.5 Coupling extraction

Implement:

1. eigenmode/participation-based extraction;
2. black-box-quantization cross-check from `Z(ω)`.

The interface shall return both values independently.

CEM consistency rule:

```text
relative disagreement > 10% -> EXTRACTION-INCONSISTENT
```

Classification of the 10% threshold: `ENGINEERING-RULE`, not `MASTER-FROZEN`, unless later superseded by a formally frozen QMHP requirement.

Never silently average inconsistent extraction values.

---

## 6. Validation gates

### 6.1 Gate-evidence rule

A gate may emit `PASS` only when its required evidence class is available.

A hardware-required gate shall never emit `PASS` from simulated values.

### 6.2 `COLLISION`

Classification: computational hard gate.

Pass condition:

```text
abs(omega24 - f_readout) >= 13 MHz
```

Statuses:

- `PASS`
- `FAIL`
- `INCOMPLETE`

### 6.3 `P6E2_FILTER`

Classification: computational/readout-side pre-hardware gate.

At the dressed emission frequency:

```text
frequency = 3.395056 GHz
attenuation >= 34 dB
```

Interpretation:

- `<34 dB` -> `FAIL`
- `>=34 dB and <36 dB` -> `PASS`, below design target
- `>=36 dB` -> `PASS`, target met

This does not close hardware P6-E2 measurement.

### 6.4 `P4PRE_SPECTRAL`

Only the readout-side spectral pre-check is evaluable in v0.1.

It may identify:

- package/eigenmode collision;
- readout conflict;
- candidate spectral inconsistency.

It must **not** emit a claim that full P4 has passed.

### 6.5 `TOLERANCE`

Evaluate candidate viability across the declared tolerance ensemble.

Required output:

- sample count;
- seed;
- pass count;
- fail count;
- rejection rate;
- confidence interval;
- failure reasons by category.

A single finite-sample count must not be presented as the underlying model probability.

### 6.6 P6-E6 joint acceptance object

Frozen limits carried by QMHP:

```yaml
f_star:
  d3: 0.524
  d5: 0.598

p_induced_max_per_data_qubit_round_equivalent: 0.001
Pu_total_max_per_round: 0.01
logical_advantage_confidence_min: 0.95
comparison_basis: equal_wall_clock
```

All four conditions are required.

However, v0.1 does not have the required measured hardware inputs.

Therefore the measured P6-E6 gate shall return:

```text
HARDWARE-GATED
```

until legitimate measured inputs are provided in a future release.

### 6.7 Hardware-gated objects

At minimum, the following shall be represented as hardware-gated in v0.1:

- P0d sink reset/process validation;
- P1 direct unlocated bypass acceptance;
- P3 trajectory coherence/bias;
- P5 destination-resolved erasure conversion;
- measured P6-E acceptance;
- P7 unconditional logical advantage.

Test requirement:

> No code path may cause a hardware-gated gate to emit `PASS` without an explicitly typed future `MEASURED` evidence object.

---

## 7. Geometry and solver architecture

### 7.1 Planar geometry

Use `gdsfactory`.

v0.1 planar cells:

1. readout resonator;
2. impedance-stepped filter.

Requirements:

- parameter-driven from `Candidate`;
- explicit ports;
- deterministic cell naming;
- geometry bounding-box reporting;
- project DRC test;
- export suitable for EM meshing/adapters.

All dimensions not defined by the frozen Master are `ENGINEERING-SEED`.

### 7.2 PicoGK package geometry

Use:

- .NET 9;
- PicoGK 2.3.0 pinned exactly;
- LEAP71 ShapeKernel at a recorded revision where required.

Keep the C# boundary thin and file-based.

Input:

```text
candidate.json
```

Outputs:

```text
body.stl
lid.stl
ports.json
geometry_manifest.json
```

### 7.3 Coordinate convention

Freeze:

```text
origin = centre of top surface of chip substrate
+X/+Y = chip plane
+Z = from chip toward package lid
3D geometry internal unit = mm
RF frequency unit = GHz
RF offset/separation unit = MHz
```

### 7.4 Object 001 — Single-device package

Object ID:

```text
object001_single_device_package
```

Required geometric features:

- package outer body;
- chip recess;
- package/vacuum cavity;
- removable lid;
- two opposing SMP-style launch bores/interfaces;
- mounting features;
- simple thermal-path geometry;
- filter housing allowance;
- explicit chip datum;
- solver-domain bounding definition.

Do not model:

- microscopic junctions;
- full thin-film fluxonium circuit in PicoGK;
- full 17-qubit tile.

### 7.5 Object 001 engineering seed geometry

Classification: `ENGINEERING-SEED`.

```yaml
chip:
  width_mm: 20.0
  height_mm: 20.0
  thickness_mm: 0.43

package:
  outer_width_mm: 32.0
  outer_height_mm: 32.0
  body_height_mm: 5.0
  floor_thickness_mm: 1.0

chip_recess:
  xy_clearance_mm: 0.20
  depth_mm: 0.45

vacuum_cavity:
  width_mm: 22.0
  height_mm: 22.0
  height_above_chip_mm: 1.50

lid:
  thickness_mm: 2.0

launches:
  bore_diameter_mm: 2.50
  count: 2

mounting:
  hole_count: 4
```

These are not validated QMHP hardware dimensions.

### 7.6 Geometry acceptance tests

At minimum:

- positive volume;
- recess fits inside package;
- chip fits inside recess;
- cavity leaves positive walls;
- launch bores connect exterior to intended interior region;
- mounting holes remain in valid structural material;
- exported meshes are watertight where the exporter supports a reliable check;
- ports are present;
- all geometry outputs are hashed.

---

## 8. Object 001 deterministic sweep

### 8.1 Purpose

The v0.1 integration sweep exists to prove the complete pipeline.

It is not an optimisation study.

### 8.2 Grid

The canonical v0.1 3×3 Object 001 sweep shall vary exactly two `ENGINEERING-SEED` parameters:

```yaml
vacuum_cavity.height_above_chip_mm:
  - 1.25
  - 1.50
  - 1.75

launches.bore_diameter_mm:
  - 2.25
  - 2.50
  - 2.75
```

All other Object 001 seed parameters remain at §7.5 values.

This produces exactly 9 candidates.

Candidate assignment order shall be deterministic:

1. outer loop: cavity height ascending;
2. inner loop: bore diameter ascending.

Example IDs:

```text
QMHP-CEM-A-RF-000001
...
QMHP-CEM-A-RF-000009
```

### 8.3 Sweep file

Create:

```text
sweeps/object001_grid.yaml
```

Canonical structure:

```yaml
schema: qmhp-cem.sweep/0.1.0
name: object001_grid
object_type: object001_single_device_package
solver: mock
base_candidate: config/object001_seed.yaml

grid:
  vacuum_cavity.height_above_chip_mm: [1.25, 1.50, 1.75]
  launches.bore_diameter_mm: [2.25, 2.50, 2.75]

ordering:
  - vacuum_cavity.height_above_chip_mm
  - launches.bore_diameter_mm
```

### 8.4 Deterministic mock solver

The mock solver is a `TEST_FIXTURE`.

It must produce deterministic, plausible-shaped:

- frequency grid;
- S11;
- S21;
- optional Z;
- synthetic eigenmodes;
- convergence metadata.

It must be obvious in every output that the result is synthetic.

A valid implementation may derive deterministic perturbations from the candidate ID or candidate input SHA-256, but the method must be fixed and golden-tested.

The mock must support fixtures that intentionally produce:

- a filter `PASS`;
- a filter `FAIL`;
- a collision `PASS`;
- a collision `FAIL`;
- `NO FEASIBLE DESIGN FOUND`.

### 8.5 Palace-backed sweep

The same `sweeps/object001_grid.yaml` shall be runnable through the Palace adapter.

Palace execution:

- may be slow;
- is not required by default CI;
- must never silently fall back to mock;
- must fail clearly if the requested solver/container cannot execute.

---

## 9. Repository layout

Required top-level layout:

```text
QMHP-CEM/
├── QMHP-CEM_v0.1_Spec.md
├── README.md
├── pyproject.toml
├── uv.lock
├── master/
│   ├── qmhp_v158f_requirements.yaml
│   ├── validation_gates.yaml
│   └── provenance.json
├── contracts/
├── models/
├── evaluator/
├── geometry/
│   ├── chip_planar/
│   └── package_picogk/
├── solvers/
│   ├── adapter.py
│   ├── mock/
│   ├── palace/
│   └── openems/
├── orchestrator/
│   └── cem.py
├── sweeps/
│   └── object001_grid.yaml
├── config/
│   └── object001_seed.yaml
├── docker/
│   ├── palace.Dockerfile
│   └── openems.Dockerfile
├── tests/
├── results/
├── manifests/
├── scripts/
└── docs/
```

Claude may add technically necessary files and subdirectories.

It may not remove the logical separation between:

- frozen requirements;
- contracts;
- physics models;
- geometry;
- solvers;
- evaluators;
- orchestration;
- immutable/append-only results.

---

## 10. Solver adapter requirements

### 10.1 Common interface

All solvers shall expose a common logical boundary.

Conceptual operations:

```python
prepare(candidate, geometry, run_context)
run(prepared_input)
parse(raw_output)
validate_convergence(parsed_output)
return SolverResults
```

### 10.2 Mock

Classification:

```text
TEST_FIXTURE
```

Default CI depends on mock only.

### 10.3 Palace

Invoke via subprocess/container runner.

Provide:

```text
docker/palace.Dockerfile
```

Record:

- solver version;
- image digest where available;
- command line;
- input hash;
- output hashes;
- convergence.

### 10.4 openEMS

Same rules as Palace.

Provide:

```text
docker/openems.Dockerfile
```

### 10.5 No silent substitution

If:

```text
--solver palace
```

is requested and Palace fails/unavailable:

the run shall fail clearly.

It shall not silently execute the mock solver.

---

## 11. Orchestrator, result storage and manifests

### 11.1 CLI

Provide:

```text
uv run cem generate ...
uv run cem simulate ...
uv run cem evaluate ...
uv run cem sweep ...
uv run cem report ...
```

Required acceptance command:

```text
uv run cem sweep sweeps/object001_grid.yaml --solver mock
```

### 11.2 Candidate lifecycle

Use the following state progression:

```text
DEFINED
-> VALIDATED
-> GEOMETRY_GENERATED
-> SOLVER_INPUT_PREPARED
-> SOLVED
-> QUANTUM_EVALUATED
-> GATES_EVALUATED
-> PASS | FAIL | INCOMPLETE | HARDWARE-GATED
```

Invalid transitions must be rejected.

### 11.3 Append-only results

Normal execution shall never silently overwrite a completed candidate result.

Recommended layout:

```text
results/
└── BATCH-<timestamp-or-id>/
    ├── batch_report.json
    ├── manifest.sha256
    ├── QMHP-CEM-A-RF-000001/
    │   ├── candidate.json
    │   ├── geometry/
    │   ├── solver/
    │   ├── quantum_results.json
    │   └── gate_report.json
    └── ...
```

### 11.4 SHA-256 manifest

Every decision-relevant file shall be included.

Examples:

- candidate YAML/JSON;
- GDS;
- STL;
- `ports.json`;
- geometry manifest;
- solver inputs;
- solver outputs;
- quantum results;
- gate report;
- candidate report;
- batch report.

Manifest ordering must be deterministic.

Temporary caches are excluded unless deliberately promoted to scientific artifacts.

---

## 12. Test and CI requirements

### 12.1 Master authority tests

Test:

- machine-readable Master files load;
- required values match this specification;
- provenance digests match;
- runtime code cannot mutate `master/`;
- frozen requirements cannot be changed by candidate processing.

### 12.2 Contract tests

Test:

- round trips;
- missing schema rejection;
- mandatory convergence block;
- invalid units;
- invalid candidate dimensions;
- unknown core fields where forbidden.

### 12.3 Physics regression tests

Required CI regression pins:

```yaml
dressed_root_10_12_GHz: 4.301974466
dressed_root_14_25_GHz: 4.301975383
f8_purcell_weight: 0.01182198
eq7_chi_MHz: [-5.366823, -0.305447, 7.214942]
perturbative_root_GHz: 4.314628047
sink_line_GHz: 4.310696
sink_logical_contrast_MHz: 18.228
```

Regression tolerance:

```text
<= 1e-6 relative
```

unless:

- the reference is deliberately printed at fewer digits;
- the test explicitly checks display precision;
- a stricter tolerance is justified by the verified artifact.

For extra-precision pull regression pins:

```yaml
logical_pull_MHz: -9.507089
sink_pull_MHz: 8.721155
```

classify the extra digits as `VERIFIED-COMPUTATIONAL`.

Do not weaken tolerances merely to make CI pass.

### 12.4 RNG/tolerance tests

Verify:

- `default_rng`;
- parameter draw order `EC -> EJ -> EL`;
- same declared seed and software environment reproduces the new CEM draw stream;
- the implementation does not claim legacy finite-sample identity reproduction.

### 12.5 Gate tests

At minimum:

- collision boundary at 13 MHz;
- Purcell filter boundary at 34 dB;
- target distinction at 36 dB;
- hardware-gated gate never returns PASS;
- inconsistent coupling extraction returns `EXTRACTION-INCONSISTENT`;
- P6-E6 does not pass without measured evidence.

### 12.6 Geometry tests

Planar:

- cells generate;
- ports valid;
- DRC passes project rules;
- bounding boxes plausible.

PicoGK:

- Object 001 generates;
- output non-empty;
- expected components exist;
- port definition generated;
- watertight export check where supported;
- artifacts hashed.

### 12.7 Orchestrator tests

Test:

- append-only behaviour;
- deterministic candidate ordering;
- 3×3 sweep generates exactly nine candidates;
- mock sweep completes unattended;
- batch manifest includes all required files;
- `NO FEASIBLE DESIGN FOUND` is handled as a successful scientific batch outcome rather than a software crash.

### 12.8 Default CI

Default CI shall not require:

- Palace;
- openEMS;
- HFSS;
- Sonnet;
- COMSOL;
- physical hardware.

Required commands:

```text
uv run pytest
```

and, for the .NET geometry project:

```text
dotnet restore
dotnet build
dotnet test
```

The CI must verify the pinned PicoGK/ShapeKernel environment.

---

## 13. Dependency and environment requirements

### 13.1 Python

Minimum:

- Python 3.11+
- `uv`
- Pydantic v2
- pytest
- numpy
- scipy
- scikit-rf
- gdsfactory

Pin exact resolved versions in `uv.lock`.

### 13.2 .NET

Use:

```text
.NET 9
PicoGK 2.3.0
```

Pin PicoGK exactly.

Record the exact ShapeKernel Git revision or exact compatible package version.

### 13.3 Environment record

Every batch manifest shall record:

- OS;
- architecture;
- Python version;
- uv version;
- dependency lock hash;
- .NET version;
- PicoGK version;
- ShapeKernel revision;
- git commit;
- solver version;
- solver/container identity;
- UTC start/end times.

---

## 14. Definition of done

QMHP-CEM v0.1 is complete only when all of the following are satisfied:

1. `QMHP-CEM_v0.1_Spec.md` is present.
2. Python environment is reproducibly locked.
3. .NET/PicoGK/ShapeKernel versions are pinned.
4. `master/` files are created and immutable at runtime.
5. Pydantic contracts are implemented.
6. Solver convergence metadata is mandatory.
7. Deterministic mock solver passes golden tests.
8. Static fluxonium regression tests pass.
9. Dressed-system regression tests pass.
10. F8 Purcell regression passes.
11. New CEM tolerance RNG convention is tested.
12. Coupling-extraction disagreement handling is implemented.
13. Computational gates work.
14. Hardware-gated gates cannot emit PASS.
15. gdsfactory cells generate and pass declared DRC.
16. Object 001 PicoGK geometry generates.
17. STL/ports/geometry manifest are produced.
18. Decision-relevant outputs are SHA-256 hashed.
19. Results are append-only.
20. 3×3 Object 001 mock sweep runs unattended.
21. `NO FEASIBLE DESIGN FOUND` is supported and tested.
22. Palace adapter is wired and runnable when its container is available.
23. openEMS adapter is wired and runnable when its container is available.
24. `uv run pytest` passes.
25. .NET build/tests pass.
26. README documents the evidence boundary.
27. README explicitly states that computational PASS is not hardware validation.
28. No v0.2 work has been started.

---

## 15. Deferred work

Explicitly deferred beyond v0.1:

### v0.2 candidate scope

- real Palace validation of Object 001;
- solver-convergence campaigns;
- calibrated readout/filter EM extraction;
- tighter port/de-embedding conventions.

### Later

- package-mode/thermal co-design;
- expanded planar readout/filter design;
- coupler/readout spectral co-design;
- manufacturing tolerance optimisation;
- multi-device cell;
- 17-qubit tile;
- hardware-measurement ingestion;
- measured P0d–P7 gate closure;
- optimisation only after deterministic sweep methodology is trusted.

---

## 16. Required README scientific disclaimer

README shall contain language equivalent to:

> QMHP-CEM is computational-engineering infrastructure for the QMHP-CoPro research programme. A candidate that passes computational gates has not thereby passed hardware gates and has not demonstrated processor performance or fault tolerance. Hardware-dependent gates remain HARDWARE-GATED until legitimate measured evidence is supplied.

---

## 17. Required final implementation report

At v0.1 completion, report:

1. `COMPLETE`, `INCOMPLETE`, or `BLOCKED`;
2. final repository tree;
3. Python version;
4. uv version;
5. .NET version;
6. PicoGK version;
7. ShapeKernel revision;
8. exact dependency locks;
9. solver adapter status;
10. every physics regression pin and observed value;
11. test summary;
12. 3×3 mock sweep result;
13. Object 001 artifact paths;
14. manifest paths and hashes;
15. deviations from this specification;
16. all introduced `ENGINEERING-SEED` assumptions;
17. known limitations;
18. unresolved technical issues;
19. recommended v0.2 scope.

Do not begin v0.2 automatically.

---

# Appendix A — Master verification/evidence status carried into CEM

The CEM shall preserve the following evidence distinctions:

| Layer | Status |
|---|---|
| Static Hamiltonian / spectrum / matrix elements | INDEPENDENTLY REPLICATED |
| Curvature / Richardson / QP bypass | INDEPENDENTLY REPLICATED |
| Eq.(7) diagnostic / perturbative root | INDEPENDENTLY REPLICATED |
| Exact dressed root / truncation provenance | STRONGLY VERIFIED |
| Pulls / sink line / dressed f12 | INDEPENDENTLY REPLICATED |
| Purcell weight F8 | RESOLVED — release exact |
| Ensemble rejection rate | STATISTICALLY SUPPORTED |
| Exact legacy ensemble counts | NOT ADJUDICABLE FROM SPEC |
| Ledger / row-wise mapping | INDEPENDENTLY REPLICATED |
| Statistics layer | INDEPENDENTLY REPLICATED |
| Stochastic QEC conclusions | INDEPENDENTLY SUPPORTED |
| T.12 break-even | SPOT-CHECK SUPPORTED |
| T.13 distance trend | INDEPENDENTLY SUPPORTED — EXPLORATORY |
| Hardware validity | OPEN / DECISION-BEARING |

QMHP-CEM shall not flatten these into a single generic `VERIFIED` status.

---

# Appendix B — Frozen programme position relevant to CEM

The current research position remains:

- continue as a gated research programme;
- matched Branch A versus Branch C has no established separation without location credit;
- the ideal free-location bracket is optimistic and not hardware evidence;
- the zero-location matched advantage arises from lower charged load per unit time rather than demonstrated erasure-conversion benefit;
- persistent leakage remains a major model-sensitive risk;
- full gate propagation remains required before an absolute physical logical-error claim;
- package/coupler spectral work and Purcell-filter verification are legitimate next engineering objects;
- fabrication/measurement is justified only as a gated experiment;
- no processor-performance or fault-tolerance claim is supported.

QMHP-CEM v0.1 exists to make those engineering gates executable and auditable without overstating what computation has established.
