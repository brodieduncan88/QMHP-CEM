# First source-bound coupled EM candidate — checkpoint A

**Milestone:** v0.2 — First source-bound coupled EM candidate and independent
coupling extraction. **This checkpoint (A):** candidate definition and
extraction admission. No coupled EM solve has been run; nothing here is
coupled EM evidence.

| document | content |
|---|---|
| [`coupling-definition.md`](coupling-definition.md) | what the two routes estimate: node-basis charging-energy matrix, derived `g`, `J`; units, signs, normalisation; what is *not* the target; required interactions; the unchanged 10 % rule; unresolved-coupling reporting; the linear/nonlinear boundary |
| [`extraction-routes.md`](extraction-routes.md) | Route A (eigenmode + participation inversion) and Route B (driven response, S→Z, admittance fit), their shared assumptions, and the Palace v0.13.0 features each relies on, checked against the pinned tree |
| [`numerical-plan.md`](numerical-plan.md) | bands, mode identification and hidden-mode screening, refinement ladders, resolution checks, suitability checks, compute budget, order of execution |
| [`implementation-plan.md`](implementation-plan.md) | file-by-file plan; what this checkpoint implements ([A]) and what execution implements ([B]) |
| `config/coupled/v2a_five_node_candidate.json` | the machine-readable declaration (schema `qmhp-cem.coupled-candidate/0.2.0`) |
| `config/coupled/source_register.json` | every cited source with path, revision and sha256 |
| `contracts/coupled_candidate.py`, `contracts/extraction.py` | the versioned contract extension and the typed extraction record |
| `scripts/coupled_candidate_check.py` | offline validation, register verification, geometry preview, mesh dry run |

## What the candidate is

**Proposed structure (declared, not executable):** the V2A five-node
hypothesis, two grounded Branch-A encoded fluxoniums `F1`, `F2`, one
SQUID-transmon mediator `C`, two passive readout modes `R1`, `R2`. It is
described in this repository only by the received V2A assessment
(`docs/v2a/`), whose own artefacts (the five-node capacitance matrix, the
frozen coupled Hamiltonian, the sweep outputs) are not here. The Master
PDFs, the frozen requirements and the release bundle contain no mediator,
SQUID, second device or second readout mode (0 hits, see the source
register). The mediator's `E_J`, `E_C`, asymmetry and flux bias, the second
readout frequency and every coupling geometry are therefore **UNBOUND**, and
no engineering seed is proposed for them: seeding a mediator from the
reported `f_22 ≈ 7.016 GHz` would be reconstructing a canonical parameter
from a summary.

**First executable candidate, S1 (a bounded subsystem):** one grounded
Branch-A fluxonium `F1` capacitively coupled to one passive readout mode
`R1`, in a bounded 4 × 4 mm chip cell that keeps the Object 001 vertical
stack (0.43 mm chip, 1.50 mm to the lid). Its bound inputs are exactly the
source-bound ones: `E_C = 0.60`, `E_J = 5.72`, `E_L = 1.58` GHz,
`φ_ext = π` (MASTER-FROZEN), the bare readout root 4.301974466 GHz
(MASTER-FROZEN) and `g = 0.150 GHz` (VERIFIED-COMPUTATIONAL) as suitability
references, and the Object 001 seed stack (ENGINEERING-SEED). Everything
geometric on the chip (island size and gap, coupling gap, CPW dimensions,
meander, ports, substrate permittivity, PEC metal, 50 Ω port references,
`C_J = 0`) is a **newly proposed, unapproved ENGINEERING-SEED** with its
rationale in the declaration. S1 claims a numerical extraction of
`E_C,F1F1`, `E_C,F1R1`, `(E_C,R1R1, E_L,R1)` and hence `g_F1R1` by two
independent routes, their agreement to the existing 10 % rule, and a
suitability report against the source values. **It does not claim V2A
validation, and says nothing about the mediator, `F2`, `R2` or their
couplings.**

Branch A and Branch B stay independent; nothing from Branch C (the
conventional-fluxonium control, "C-02C" appears in no source) is used.

**Seed plausibility, recorded not adopted.** The source-bound `g = 0.150 GHz`
implies a coupling capacitance of about 7.2 fF at the declared node
(`E_C,F1R1 = 5.85 MHz`). A crude edge estimate of the declared 20 µm gap over
the 100 µm facing width gives about 28 fF, roughly 4× larger, so the seed is
expected to over-couple. That is information for the review, not a design
change: what the geometry realises is what the extraction measures and the
suitability block reports. A wider gap would reduce both the coupling and the
mesh cost, and the unadopted sensitivity probe measures the second effect.

## What the routes will compare

Per required pair (S1: `F1–R1`), `|g_F1R1|` in MHz from Route A and from
Route B, with the unchanged ENGINEERING-RULE
`|a − b| / mean(|a|, |b|) ≤ 0.10`, applied only when both routes resolve the
pair at 10× their numerical floor. Details and the reporting of unresolved
or vanishing couplings: `coupling-definition.md` §6 and §9.

## Contract extension

One new schema, `qmhp-cem.coupled-candidate/0.2.0`, validating the
declaration as a closed typed document (nodes, elements, ports, materials,
boundary conditions, bias, effects, bindings). `Candidate` 0.1.0, the
Object 001 seed, the golden Palace input and the golden records are
untouched; the byte-identity test of the golden `prepare()` remains in the
suite. The per-interaction extraction record lands in
`QuantumResults.dressed_system["coupling_extraction_interactions"]` next
to, never instead of, the existing scalar block; the nominal-reference
quantum calculation stays under its own keys and is never relabelled.

## Disposition

Two dispositions are reported separately, so that a compute limit is never
read as an invalid candidate nor the reverse
(`results/COUPLED-CHECKPOINT-A-20260915T224700Z/report.md`):

- **Admission: READY-FOR-REVIEW.** The declaration validates against the new
  schema, all fifteen source digests verify, the geometry is consistent
  (empty clearance report), the preview renders and the mesh dry run runs.
- **Execution: BLOCKED on the declared compute budget.** The declared mesh
  ladder needs 699 k / 1.58 M / 3.06 M degrees of freedom at order 2 against
  the 250 k budget of `numerical-plan.md` §6; at order 1 only L1 and L2 fit.
  The 20 µm coupling gap sets the cost. `numerical-plan.md` §8 carries the
  measured table and the unadopted sensitivity probe. What to change is a
  human decision and is not made here.

Execution of the coupled campaign, pulse work, decoder studies, openEMS and
any AMD-E or mediator optimisation are out of scope and not started.
