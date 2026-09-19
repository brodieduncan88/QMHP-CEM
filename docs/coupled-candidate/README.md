# First source-bound coupled EM candidate — checkpoint A

**Milestone:** v0.2 — First source-bound coupled EM candidate and independent
coupling extraction. **This checkpoint (A):** candidate definition and
extraction admission.

> **Superseded in part.** At checkpoint A no coupled EM solve had been run.
> Solves have since been executed and recorded — the pilot, the three-rung
> order-1 ladder, R1, and the nested-refinement runs N1, N2, N2R and N1R. Each
> has its own outcome record in the table below and its own committed record
> under `results/`. The candidate definition and the extraction admission are
> unchanged; **no coupling extraction has been run**, and none of the executed
> solves is coupling evidence.

| document | content |
|---|---|
| [`coupling-definition.md`](coupling-definition.md) | what the two routes estimate: the gauge-invariant triple `{E_C,F1F1, f_R1, g_F1R1}` and the per-pair coefficients `g`, `J`; units, signs, normalisation; what is *not* the target, including the non-identifiable readout-node entries; required interactions; the unchanged 10 % rule; unresolved-coupling reporting; the linear/nonlinear boundary |
| [`extraction-routes.md`](extraction-routes.md) | Route A (eigenmode + participation inversion) and Route B (driven response, S→Z, admittance fit), their shared assumptions, and the Palace v0.13.0 features each relies on, checked against the pinned tree |
| [`numerical-plan.md`](numerical-plan.md) | bands, mode identification and hidden-mode screening, refinement ladders, resolution checks, suitability checks, compute budget, order of execution |
| [`route-a-identifiability.md`](route-a-identifiability.md) | the readout-normalisation problem, the corrected invariant target, the closed-form inversion, and its demonstration on synthetic circuits |
| [`execution-proposal.md`](execution-proposal.md) | the bounded geometry, meshing and resource proposal put to the review; nothing in it is adopted |
| [`pilot-outcome.md`](pilot-outcome.md) | the approved three-solve numerical-method pilot as executed: completion, modes, the measured order and halo sensitivities, and the `NOT-A-HALO-VERDICT` under the frozen criteria. **Sections 2, 3 and 5 are superseded in part** by the corrective analysis below |
| [`corrective-analysis.md`](corrective-analysis.md) | bounded corrective analysis of the executed pilot record: mode admission, row correspondence, energy definitions against pinned Palace v0.13.0, the EPR sign convention, and what stays unproven. Keeps execution completion, algebraic convergence, mode validity, mode matching and mesh convergence apart |
| [`order1-ladder-outcome.md`](order1-ladder-outcome.md) | the three-rung order-1 mesh-refinement check: no observed order of convergence on either tracked mode, the port-stiffness mechanism reproducing at level 3, and the calibration flaw that hid it. **Superseded in part** by `s1-numerical-recovery.md` |
| [`r1-port-refinement-outcome.md`](r1-port-refinement-outcome.md) | the executed R1 run: refining only the port box moved the fluxonium-like mode by 23.9 % of what a full global refinement bought, and the readout-like mode the other way. Partial sensitivity, with the derived diagnostic holding to 1.31e-06 on a mesh it had never seen |
| [`s1-numerical-recovery.md`](s1-numerical-recovery.md) | the port-stiffness conversion derived from pinned Palace v0.13.0 rather than fitted, and reproducing the closure defect on all twelve committed rows to 2e-8; what the L1/L2/L3 meshes actually have on the port face against what the size rule asked for; one controlled local-refinement experiment, dry-run and predeclared, awaiting approval |
| [`nested-refinement-feasibility.md`](nested-refinement-feasibility.md) | whether the preserved L2 mesh can be locally refined **without** regenerating through gmsh, verified against pinned Palace/MFEM rather than assumed: `Model.Refinement.Boxes` is conforming and nested, every baseline vertex survives, and the closure refines elements outside the box. The offline marking: 221 of 64 434 tets |
| [`n1-nested-refinement-outcome.md`](n1-nested-refinement-outcome.md) | the executed N1 run: one nested level on the byte-identical L2 mesh, 84 485 DOF, both tracked modes moving the **same** way — unlike R1 — and the derived diagnostic holding on a mesh it had never seen |
| [`n2-proposal.md`](n2-proposal.md) | the N2 preparation: two total levels from the original mesh, why iteration 0 reproduces N1's stage exactly, and why no N2 DOF or runtime could be predicted offline |
| [`n2-outcome.md`](n2-outcome.md) | N2 **refused on time**: 103 411 DOF cleared the budget gate in 2.3 s, then the run hit 100 % of the 2 700 s cap with no eigenvalues. The refusal is the result; the primary comparison was unavailable |
| [`n2-runtime-diagnosis.md`](n2-runtime-diagnosis.md) | why, offline from the logs and pinned sources: refinement builds mesh levels, and `ksp.cpp:202` then demotes a sparse **direct** preconditioner to the coarse solver of a V-cycle whose levels barely coarsen. The whole regression is in the linear-solver stack. Names `MGMaxLevels: 1` as a supported configuration that leaves the discrete problem untouched |
| [`n2r-rescue-run.md`](n2r-rescue-run.md) | the N2R preparation: N2's problem plus that one key, with the config delta shown **by diff** rather than argued, and a falsifiable mesh-identity pre-declaration |
| [`n2r-outcome.md`](n2r-outcome.md) | N2R **completed in 159.0 s**, 5.9 % of the cap, against N2's timeout on the identical problem. Every pre-declaration held. Gives the N1 → N2R comparison N2 could not, and says plainly that the step crosses a preconditioner change |
| [`n1r-control.md`](n1r-control.md) | the N1R preparation: N1's problem with N2R's solver, so the sequence has one solver strategy throughout and N1 vs N1R measures the solver-path effect directly |
| [`n1r-outcome.md`](n1r-outcome.md) | N1R completed in 110.7 s. The solver-path effect on the tracked pair is **~5e-09 relative** — four orders below the frozen tolerance — so the campaign's refinement movements are refinement effects. The controlled sequence **confirms** the reported one to six significant figures |
| [`implementation-plan.md`](implementation-plan.md) | file-by-file plan; what this checkpoint implements ([A]) and what execution implements ([B]) |
| `config/coupled/v2a_five_node_candidate.json` | the machine-readable declaration (schema `qmhp-cem.coupled-candidate/0.2.0`) |
| `config/coupled/source_register.json` | every cited source with path, revision and sha256 |
| `contracts/coupled_candidate.py`, `contracts/extraction.py` | the versioned contract extension and the typed extraction record |
| `scripts/coupled_candidate_check.py` | offline validation, register verification, geometry preview, mesh dry run |
| `models/route_a_inversion.py`, `scripts/route_a_synthetic_demo.py` | the Route A inversion and its synthetic recovery demonstration |
| `docs/v2a/submission-recovery.md`, `config/coupled/v2a_submission_reconciliation.json` | recovery attempt for the 14 September V2A submission and its reconciliation against this declaration |

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
the gauge-invariant triple `{E_C,F1F1, f_R1, g_F1R1}` by two independent
routes, their agreement on the coupling to the existing 10 % rule, and a
suitability report against the source values. The individual readout-node
entries `E_C,F1R1`, `E_C,R1R1` and `E_L,R1` are **not** outputs: each depends
on an arbitrary readout-node normalisation (see the correction below). **It does not claim V2A
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

## Corrections made after checkpoint A

- **Route A's extraction target was wrong and is corrected.** The readout node
  carries no lumped element, so its matrix entries `E_C,kR`, `E_C,RR` and
  `L_R` depend on an arbitrary normalisation and are not identifiable. The
  identifiable output is the triple `{E_C,F1F1, f_R1, g_F1R1}`; the reported
  coupling and every threshold are unchanged, because `g` was invariant all
  along. Derived, witnessed and demonstrated in
  [`route-a-identifiability.md`](route-a-identifiability.md).
- **The solver size is now measured, not estimated.** The Nédélec space
  dimension follows from the mesh edges and faces, checked against Palace's
  own reported figure; the earlier per-tetrahedron estimate overstated the
  order-2 size by about 28 %.
- **The hidden-mode screen's scope is stated up front**: it can speak only
  about modes of the represented geometry inside the declared window, and is
  silent about the full package, omitted structures and anything outside the
  band.

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
  ladder needs 546 k / 1.23 M / 2.38 M degrees of freedom at order 2 against
  the 250 k budget of `numerical-plan.md` §6; at order 1 only L1 and L2 fit.
  The 20 µm coupling gap sets the cost. These are measured counts, not
  estimates: the Nédélec space dimension follows from the mesh edges and
  faces, checked against Palace's own reported figure on the golden record
  (`numerical-plan.md` §8.1, which also records that the earlier
  per-tetrahedron estimate overstated the order-2 size by about 28 %).
  Options are in [`execution-proposal.md`](execution-proposal.md); none is
  adopted here.

Execution of the coupled campaign, pulse work, decoder studies, openEMS and
any AMD-E or mediator optimisation are out of scope and not started.
