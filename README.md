# QMHP-CEM

Computational Engineering Model software layer for the QMHP-CoPro research
programme.

**Specification:** [`QMHP-CEM_v0.1_Spec.md`](QMHP-CEM_v0.1_Spec.md)
**Parent technical authority:** QMHP-CoPro v1.5.8f — Master Edition
(Consolidated), ADOPTED MASTER — FROZEN RELEASE

---

## Scientific disclaimer

> QMHP-CEM is computational-engineering infrastructure for the QMHP-CoPro
> research programme. A candidate that passes computational gates has not
> thereby passed hardware gates and has not demonstrated processor performance
> or fault tolerance. Hardware-dependent gates remain HARDWARE-GATED until
> legitimate measured evidence is supplied.

**A computational PASS is not hardware validation.**

QMHP-CEM does not exist to find a way to make QMHP work. It exists to answer:

> Given the frozen QMHP requirements and a declared engineering candidate, what
> can be computed now, what passes or fails those computational requirements,
> and what remains hardware-gated?

`NO FEASIBLE DESIGN FOUND` is a valid scientific and engineering outcome, and
is reported as a successful batch rather than a software failure.

---

## Status: v0.1 scaffold

The repository structure, frozen requirements layer, data contracts, gate
evaluator, solver boundary and orchestrator are **implemented and tested**. The
physics and geometry generation are **not**.

| Layer | Status |
|---|---|
| `master/` frozen requirements + provenance | Implemented |
| `contracts/` Pydantic v2 records | Implemented |
| `evaluator/` gate logic and evidence boundary | Implemented |
| `solvers/` adapter boundary + deterministic mock | Implemented |
| `orchestrator/` lifecycle, append-only store, manifests, CLI | Implemented |
| `models/` physics (§5) | **Implemented** and regression-tested against the frozen pins |
| `geometry/chip_planar/` gdsfactory cells (§7.1) | **Not implemented** |
| `geometry/package_picogk/` Object 001 (§7.2) | **Not implemented** — C# project skeleton only |
| `solvers/palace` | **v0.2 execution path implemented and executed**: mesh, config, container run, parse, provenance. Genuine Palace v0.13.0 runs recorded under `results/PALACE-GOLDEN-*/` (empty Object 001 box, four modes within 5e-5 of closed form, frequencies identical to every printed digit across four runs). See [`docs/palace-execution.md`](docs/palace-execution.md) |
| `solvers/palace` verification | **v0.2 mesh-refinement and height-sensitive campaign**: three meshes of the golden box, an auxiliary 22 × 22 × 7.0/7.7 mm Z benchmark, bounded Object 001 height attempts; records under `results/PALACE-VERIFY-*/`. See [`docs/palace-verification.md`](docs/palace-verification.md) |
| `solvers/openems` | Wired; container invocation not implemented |
| `reference/` vendored v1.5.8f release bundle | Vendored, 27/29 hash-verified |

The physics reproduces the frozen dressed root **exactly** (4.301974466 GHz at
1e-10), along with the static spectrum, the sink line and the dressed emission
frequency. Three pins reproduce only to ~2e-6 and are **flagged, not absorbed**
— see [`docs/regression-pins.md`](docs/regression-pins.md).

A mock sweep still tops out at `INCOMPLETE`, but now for a precise reason:
`COUPLING_EXTRACTION` is a HARD gate requiring *both* an eigenmode and a
black-box extraction from a real EM solver, which the mock `TEST_FIXTURE`
cannot supply. Every other computationally evaluable gate adjudicates.
Reaching `FEASIBLE_CANDIDATE_FOUND` requires Palace or openEMS.

**v0.2 (in progress):** the Palace execution path is implemented and has
been executed, for real. `PalaceSolver` meshes the empty Object 001
vacuum cavity, runs the pinned container, parses the eigenmode output and
records solver version, image identity, command line, input/output hashes
and the solver's own convergence figure. The first run is the golden
candidate in `solvers/palace/golden/`, executed by
`scripts/palace_golden_run.py` inside GitHub Actions
(`.github/workflows/palace-golden.yml`) and committed as
`results/PALACE-GOLDEN-20260915T014639Z/`, then repeated as further
`results/PALACE-GOLDEN-*/` records with the same frequencies to every
printed digit: Palace 0.13.0, four converged modes, fundamental
9.635896 GHz against the closed-form 9.635695 GHz. The
gates on that result are `INCOMPLETE`, as they must be for an eigenmode-only
solve of an empty box. See
[`docs/palace-execution.md`](docs/palace-execution.md).

---

## Audit record: V2A G0

Separate from the CEM software layer, the repository carries the deep-research
assessment of the QMHP-CoPro V2A G0 follow-up audit v0.1, with its arithmetic
reproduced and its citations resolved.

| Path | What it is |
|---|---|
| [`docs/v2a/`](docs/v2a/README.md) | The assessment as received, the M3 prescreen registration template, the verification record, the reference list and the inputs taken on report |
| [`tools/v2a/check_assessment_arithmetic.py`](tools/v2a/check_assessment_arithmetic.py) | Reproduces every number stated in the assessment; exits non-zero on any mismatch |

Its disposition: **physical G0 remains BLOCKED**; the M3 mechanism has a
conditional go for one bounded, non-optimising coherent prescreen once the
registration items are frozen. That assessment is about the V2A gate programme
and does not alter the CEM gate definitions in `master/validation_gates.yaml`.

Both checks run on the standard library alone, with no solver and no `uv`:

```bash
python3 tools/v2a/check_assessment_arithmetic.py
python3 -m unittest discover -s tests -p 'test_assessment_arithmetic.py' -v
```

The pattern is needed because `tests/` also holds the CEM suite, which does
need the locked environment. `uv run pytest` runs everything together.

---

## Quick start

```bash
uv sync --dev

# Verify the frozen master layer and its provenance digests
uv run cem verify-master

# Expand the canonical sweep without solving
uv run cem generate sweeps/object001_grid.yaml

# Acceptance command — the 3x3 Object 001 sweep, unattended
uv run cem sweep sweeps/object001_grid.yaml --solver mock

# Summarise a batch and re-verify its SHA-256 manifest
uv run cem report results/BATCH-<id>

uv run pytest

# Re-verify the vendored release bundle against its AMD-C manifest
uv run python scripts/verify_reference_bundle.py
```

### CLI

| Command | Purpose |
|---|---|
| `cem generate <sweep>` | Expand a sweep into candidates |
| `cem simulate <sweep>` | Run candidates through a solver |
| `cem sweep <sweep>` | Full deterministic sweep, end to end |
| `cem evaluate <batch>` | Print gate outcomes for a batch |
| `cem report <batch>` | Batch summary + manifest verification |
| `cem verify-master` | Verify frozen provenance digests |

Add `--tolerance-samples N` to run the TOLERANCE ensemble (0 = skip, the
default; each device costs ~50 ms).

Mock fixtures (`--fixture`) force specific downstream outcomes for testing:
`default`, `filter_pass`, `filter_fail`, `collision_pass`, `collision_fail`,
`no_feasible_design`.

---

## The evidence model

Every decision-relevant value carries a classification (spec §2.2):

| Class | Meaning |
|---|---|
| `MASTER-FROZEN` | Carried by the frozen v1.5.8f Master. Immutable at runtime. |
| `VERIFIED-COMPUTATIONAL` | From the verified August 2026 computational cycle. Computational evidence, not hardware evidence. |
| `ENGINEERING-SEED` | A CEM bootstrap assumption. **Never** experimentally validated, never a QMHP requirement. |
| `SOLVED` | Produced by a numerical solver for a declared candidate. |
| `MEASURED` | From actual hardware. **QMHP-CEM v0.1 does not manufacture these.** |

### The hardware boundary

No simulated or model-derived result may cause a hardware-gated gate to emit
`PASS`. This is enforced in three independent places:

1. `master/validation_gates.yaml` omits `PASS` from those gates' allowed statuses;
2. `Gate.evaluate()` rejects any status outside the frozen allowed list;
3. `GateResult` refuses to *construct* a `PASS` for a hardware-required gate
   without `MEASURED` evidence.

Defeating the boundary would require breaking all three. `P0d`, `P1`, `P3`,
`P5`, `P6-E6` and `P7` all return `HARDWARE-GATED`.

All Object 001 dimensions are `ENGINEERING-SEED` (spec §7.5). They are not
validated QMHP hardware dimensions.

---

## Layout

```
QMHP-CEM/
├── QMHP-CEM_v0.1_Spec.md   # the specification (authority level 2)
├── master/                 # frozen machine-readable requirements (level 3)
├── contracts/              # Pydantic v2 records + frozen-master loader
├── models/                 # physics (spec §5) — stubs in v0.1
├── evaluator/              # validation gates (spec §6)
├── geometry/
│   ├── chip_planar/        # gdsfactory planar cells (spec §7.1)
│   └── package_picogk/     # PicoGK Object 001, C# (spec §7.2)
├── solvers/                # adapter boundary + mock / palace / openems
├── orchestrator/           # lifecycle, append-only store, manifests, CLI
├── sweeps/                 # deterministic sweep definitions
├── config/                 # seed candidates
├── docker/                 # solver container definitions
├── reference/              # vendored upstream release bundle (read-only)
├── tests/
├── results/                # append-only batch outputs
└── manifests/
```

The logical separation between frozen requirements, contracts, physics models,
geometry, solvers, evaluators, orchestration and immutable results is
structural and must not be collapsed (spec §9).

### Authority order

1. QMHP-CoPro v1.5.8f Master Edition — scientific/technical authority
2. `QMHP-CEM_v0.1_Spec.md` — software implementation authority
3. `master/` machine-readable files
4. Code
5. Generated outputs

Code may not alter a higher-authority object to make a test or candidate pass.

---

## What PicoGK is for

PicoGK owns **physical geometry** — package bodies, enclosures, launches,
cavities, thermal and shielding structures. It generates the geometry on which
the physics is evaluated.

It is not an EM solver, not a Hamiltonian solver, and not a QEC simulator.
Thin-film mask/GDS work belongs in `geometry/chip_planar/` (gdsfactory);
Hamiltonians and QEC belong in `models/`.

---

## Results and provenance

Results are **append-only** (spec §11.3). A completed candidate result is never
silently overwritten; a completed batch cannot be reopened.

Every decision-relevant artifact is SHA-256 hashed into a per-batch
`manifest.sha256` with deterministic ordering, and `cem report` re-verifies the
tree against it. Each batch records its environment: OS, architecture, Python
and uv versions, dependency lock hash, .NET/PicoGK/ShapeKernel versions, git
commit, solver identity, RNG seed and UTC times.

---

## Environment

| Component | Requirement |
|---|---|
| Python | 3.11+ with `uv` |
| Pydantic | v2 |
| .NET | 9 |
| PicoGK | **2.3.0, pinned exactly** |
| ShapeKernel | revision recorded in `geometry/package_picogk/driver.py` |

`gdsfactory` is an optional extra (`uv sync --extra planar`) so that default CI
stays light. Default CI requires **no** Palace, openEMS, HFSS, Sonnet, COMSOL
or physical hardware (spec §12.8).

If the .NET SDK is absent, geometry generation reports itself unavailable and
the pipeline continues, recording plainly that no geometry was produced. It
never fabricates an STL.

---

## Explicit non-goals for v0.1

The 17-qubit tile; Bayesian, Pareto, genetic or AI-driven optimisation; full
processor-performance or fault-tolerance claims; replacing hardware
measurements with simulations; promoting simulation output to measured
evidence; full P4, P6-E or P7 closure; microscopic Josephson-junction geometry
in PicoGK; a complete fabrication process flow.

Deterministic sweeps come first. Optimisation is deferred until the sweep
methodology is trusted (spec §9 of the parent plan, spec §15 here).
