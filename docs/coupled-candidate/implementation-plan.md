# Implementation plan, file by file (checkpoint A → execution)

**Status:** checkpoint-A plan. Only the items marked **[A]** are implemented
in this checkpoint (declaration schema, offline checks, preview, mesh dry
run, tests). Everything marked **[B]** is the execution milestone and is not
started. Line numbers refer to branch `palace/physical-coupled-candidate`
at its base `e736226`.

## 1. Contracts

### `contracts/candidate.py` — unchanged
`Candidate` (schema `qmhp-cem.candidate/0.1.0`, `StrictModel`, `extra=forbid`,
`object_type` literal `object001_single_device_package`, every parameter
field `_mm`) stays byte-for-byte what it is. It cannot carry nodes, ports or
energies (tests/test_contracts.py:124-133 pin the `_mm` rule), and widening
it would change the golden candidate's validation surface. The Object 001
seed and the golden JSON remain valid and untouched.

### `contracts/coupled_candidate.py` — **[A] new**, the smallest versioned extension
One new schema, `qmhp-cem.coupled-candidate/0.2.0`, one new root model
`CoupledCandidateDeclaration`, validating exactly
`config/coupled/v2a_five_node_candidate.json`. It *references* the Object 001
`Candidate` it embeds in through `parent_candidate_id` (validated against
`CANDIDATE_ID_PATTERN`) instead of subclassing it, so the physical model is
a typed, closed document rather than an override bag. Sub-models (all
`StrictModel`):

- `Binding`: discriminated on `class` ∈ {`SOURCE-BOUND`, `ENGINEERING-SEED`,
  `UNBOUND`}; SOURCE-BOUND requires `source_id` (must exist in the register)
  and `locator`; ENGINEERING-SEED requires `rationale` and carries
  `approved: bool` (must be `false` at checkpoint A); UNBOUND requires
  `needed_from`.
- `Frame`, `Cell`, `Feature` (rectangle / cpw_meander), `Material`,
  `BoundaryCondition`, `ElectricalNode`, `LumpedElement`, `Port` (with
  `route_A` / `route_B` specs), `Bias`, `PhysicalEffects`,
  `ParameterEntry`, `Interaction`, `ProposedStructure`, `ExecutableScope`,
  `ExtractionRef`.
- Cross-validation (`model_validator`): every node named by an element,
  port, interaction or scope exists; every `in_S1` node has a conductor and
  a ground connection; the executable scope's `required_interactions` are a
  subset of the proposed interactions with `in_S1 = true`; every
  SOURCE-BOUND `source_id` resolves in the register; no ENGINEERING-SEED is
  `approved`; every UNBOUND parameter is *outside* the executable scope
  (otherwise the declaration is not executable and validation says so);
  features lie inside the cell with the declared clearances; port sizes are
  positive and directions are axis-aligned (`±X/±Y/±Z`, the only directions
  Palace accepts for rectangular lumped elements without a 3-vector);
  the consistency rule is exactly the master value 0.10 (read through
  `contracts.master`, never restated).
- `SourceRegister` (schema `qmhp-cem.source-register/0.2.0`) with
  `verify(repo_root) -> list[Mismatch]` recomputing every sha256.
- `load_declaration(path)`, `load_register(path)`.

### `contracts/results.py` — **[B]** additive, non-breaking
`SolverResults` gains nothing for Route A (eigenmodes, artifacts already
fit). For Route B the existing `frequency_GHz`, `s_parameters`,
`z_parameters` fields are used as they are (per-series length checks
already enforced at results.py:79-90): keys `S[i][j]` for the complex
generalised S (stored as two real series `re`/`im` per key, since the
contract holds `list[float]`) and `Z[i][j]` derived. No schema bump.

`QuantumResults.dressed_system` is a free dict; the per-interaction block
(§3) is added without a schema change. A future 0.2.0 bump is only needed
if the block becomes a typed field.

### `contracts/extraction.py` — **[A] new** (typed records the routes will write)
`InteractionExtraction` (pair, `route_a_MHz`, `route_a_floor_MHz`,
`route_b_MHz`, `route_b_floor_MHz`, `status` ∈ {RESOLVED, UNRESOLVED,
MISSING}, `relative_disagreement`, `consistent`), `RouteRecord`
(route id, record path, solver identity, convergence evidence, values of
the invariant triple), `CouplingExtractionRecord` (declaration id + sha256,
register sha256, both `RouteRecord`s, list of `InteractionExtraction`,
`suitability` dict, `hidden_modes`, `verdict`). Validation: `status` is
RESOLVED only if `|value| ≥ 10·floor` on both routes; `consistent` is only
set when RESOLVED; MISSING when a route value is absent. The factor 10 is
read from `solvers.palace.verification.RULES`, not restated.

## 2. Solver layer

### `solvers/palace/config.py` — **[B]**, additive
`build_config` today builds Eigenmode-only, vacuum-only, PEC attribute 2
(config.py:204-274), and the golden document is pinned byte-for-byte
(tests/test_verification.py:60-65). Extension: a new builder
`build_coupled_config(mesh, model: CoupledModel, *, problem: "Eigenmode" |
"Driven", ports: list[PortSpec], excitation: str | None, sweep: Sweep |
None, probes_mm)` in a **new module** `solvers/palace/coupled_config.py`
that assembles `Domains.Materials` (vacuum + substrate attributes),
`Boundaries.PEC` (outer + sheet attributes), `Boundaries.LumpedPort`
(Index, Attributes, Direction, R/L/C per route), `Solver.Eigenmode` or
`Solver.Driven` (`MinFreq > 0`, `MaxFreq`, `FreqStep`, `AdaptiveTol`),
`Domains.Postprocessing.Probe`. `build_config` and `SOLVER_RULES` are not
touched, so the golden path cannot change.

### `solvers/palace/mesh.py` — unchanged; `solvers/palace/coupled_mesh.py` — **[A] new**
`generate_box_mesh` (mesh.py:82-151), its single box, attributes
`VACUUM_ATTRIBUTE=1` / `PEC_ATTRIBUTE=2` and model name
`object001_empty_cavity` stay as they are (mesh determinism tests pin them).
The coupled cell needs its own generator: substrate volume, vacuum volume,
zero-thickness PEC sheets (ground plane minus etched features, island,
coupling pad, CPW centre conductor), port surfaces as separate physical
surfaces, a gap-resolving size field, deterministic gmsh options, and
distinct physical tags (`SUBSTRATE=3`, `SHEET_PEC=4`, `PORT_F1=10`,
`PORT_R1_A=11`, `PORT_R1_B=12`, outer PEC `2`, vacuum `1`). Checkpoint A
implements the generator and a **dry run** (`dry_run(declaration, level,
out_dir)` → nodes, tets, surface elements per tag, minimum gap resolution,
DOF estimate for order 2 and order 1, wall clock), no Palace call.

### `solvers/palace/outputs.py` — **[B]**, additive
Parsers for `port-EPR.csv` (`m, p[j]`), `port-S.csv` (`f (GHz)`,
`|S[i][j]| (dB)`, `arg(S[i][j]) (deg.)` → complex), `port-V.csv` /
`port-I.csv` (complex peak V, I, `V_inc`), `domain-E.csv` per mode
(`E_elec, E_mag, E_cap, E_ind`) with the equipartition check; headers as
transcribed from the v0.13.0 source (`extraction-routes.md` §5). Existing
`parse_eig_csv`, `parse_probe_csv` unchanged.

### `solvers/palace/adapter.py` — **[B]**, guarded
`prepare()` (adapter.py:377-475) keeps its whitelist of six override keys
and its empty-box default. A coupled run is **not** an override: it is
selected by `RunContext.extra["coupled_declaration"]` (path + sha256), which
routes `prepare()` to `coupled_config` / `coupled_mesh`, stamps
`payload["model"] = "coupled_chip_cell"` and the declaration sha256, and
writes the note "coupled chip cell of declaration …" instead of the
EMPTY-box statement. Without that key nothing changes (the golden
byte-identity test stays green). `parse()` gains the new artifact roles and
fills `frequency_GHz`, `s_parameters` for Driven runs; the eigenmode path is
unchanged. The adapter name and version strings stay pinned
(tests/test_solvers.py:549-550, test_palace.py:797-798); the coupled model
is recorded in the payload, not in the adapter identity.

## 3. Models and pipeline

### `models/coupling_extraction.py` — **[B]**
Keep `CouplingExtraction`, `ExtractionInconsistent`,
`max_relative_disagreement()` exactly. Replace the two stubs by real
functions that take typed inputs, never `SolverResults` of the other route:
`extract_eigenmode(eig_modes, epr, domain_E, declared_L) -> RouteResult`
(the participation inversion of `extraction-routes.md` §2.3, implemented and
demonstrated in `models/route_a_inversion.py`, returning the invariant triple
and never the readout-node entries) and
`extract_blackbox(S_complex, references_ohm, band, model_order) ->
RouteResult` (S→Z→Y, rational fit of §3.3). Plus `resolve(pair,
route_a, route_b) -> InteractionExtraction` applying the 10·floor rule
*before* any relative disagreement is computed, so the both-zero case
(`relative_disagreement` returns 0.0 today) can never reach the gate.

### `orchestrator/pipeline.py` — **[B]**, two guarded changes
`evaluate_quantum` (pipeline.py:102-202) keeps computing the frozen nominal
device and keeps `dressed_system` as the nominal block. Change 1: the
unconditional `unavailable` note at 157-161 becomes conditional on the
absence of a `CouplingExtractionRecord` for the candidate. Change 2: when a
record exists, write `dressed_system["coupling_extraction"] =
{eigenmode_MHz, blackbox_MHz}` **only for the primary required pair and only
if RESOLVED** (so the existing gate works unchanged), and
`dressed_system["coupling_extraction_interactions"] = {pair_id:
InteractionExtraction.as_dict()}` for every declared pair (the proposed
compatible per-interaction extension), together with
`dressed_system["extraction_record"] = {path, sha256, declaration_sha256}`.
The nominal `coupling_g_GHz = 0.150` stays under its own key and is never
overwritten. A geometry-derived dressed-system calculation, if made, goes
under `dressed_system["candidate_derived"]` with its own inputs listed, so
that the nominal reference is never relabelled.

### `evaluator/computational.py` — **[B]**, minimal
`CouplingExtractionGate` (computational.py:259-318) is unchanged for the
primary pair. One guard is added: if `dressed_system["extraction_record"]`
is present but the primary pair is UNRESOLVED or MISSING, return INCOMPLETE
with that reason rather than NOT-EVALUATED, and never PASS. Evidence class
stays `quantum.classification`; the record's solver identity must be
`palace` with `Classification.SOLVED`, otherwise INCOMPLETE (closes the
hazard that a TEST_FIXTURE extraction could PASS as SOLVED).

### `orchestrator/manifest.py` — **[A]** small
Add `.svg` and `.geo_unrolled` to `DECISION_RELEVANT_SUFFIXES` so the
geometry preview and the gmsh dry-run script are covered by manifests.

## 4. Scripts and workflows

- `scripts/coupled_candidate_check.py` — **[A] new**: loads and validates
  the declaration and register, recomputes every register digest, runs the
  cross-checks, writes a deterministic geometry preview (`preview.svg`,
  `preview.json` with every conductor polygon and port rectangle in the
  §7.3 frame), runs the mesh dry run at the three ladder levels, and writes
  `report.md` + `summary.json` under a results directory
  `results/COUPLED-CHECKPOINT-A-<UTC>/` with a manifest written last.
  Exit codes: 0 valid, 2 validation failure, 3 register mismatch, 4 dry-run
  failure. It never calls Palace or Docker.
- `scripts/palace_coupled_campaign.py` — **[B]**: the execution driver
  (Route A job, Route B job), mirroring `palace_verify_campaign.py`.
- `.github/workflows/palace-coupled.yml` — **[B]**: two jobs, dispatch only
  at first, `--record-pointer`, manifest gate, commit-back.

## 5. Tests

**[A] this checkpoint** (`tests/test_coupled_candidate.py`):
declaration validates; register digests verify; a tampered register entry
fails closed; an approved seed is rejected; an UNBOUND parameter inside the
executable scope is rejected; a port with a non-axis direction is rejected;
a feature outside the cell is rejected; the consistency rule must equal the
master value; the preview is deterministic (same SVG bytes twice); the dry
run produces the declared tags and a DOF estimate, and is deterministic on
one platform; `Candidate` 0.1.0 and the golden record are untouched
(reuse `test_golden_prepare_still_matches_the_committed_record`); the
extraction record marks both-zero pairs UNRESOLVED and never `consistent`.

**[B] planned for execution**: declared geometry and ports reach the input
deck (config JSON contains exactly the declared ports with the declared
R/L/C per route and the declared attributes); missing or malformed evidence
fails closed (absent `port-EPR.csv`, truncated `port-S.csv`, NaN); candidate
-derived parameters reach the downstream block under `candidate_derived`
and never overwrite the nominal block; independently known extraction
fixtures (a two-node lumped circuit with known `C`, `L` → synthetic
`(f_±, p_±)` and synthetic `S(f)`; the inversion and the fit must recover
`E_C` to 1e-6); unit/normalisation errors (a factor 2π or 2 injected in one
route → EXTRACTION-INCONSISTENT, never averaged); insufficient convergence or
mode identification → INCOMPLETE; disagreement beyond 10 % →
EXTRACTION-INCONSISTENT; partial failures (Route B run killed) still write
an inspectable record with manifest; golden defaults unchanged
(byte-identity test). Mock or analytical fixtures are software tests only,
never coupled EM evidence, and are marked `synthetic`.
