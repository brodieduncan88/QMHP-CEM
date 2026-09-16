# Recovery and reconciliation of the 14 September 2026 V2A numerical submission

**Disposition: NOT RECOVERED.** The submission and its referenced executable
artefacts are not present in this repository, in any branch, in any commit
reachable or unreachable, or in any stashed or dangling git object. What the
repository holds is the **deep-research assessment of** that submission,
received 2026-09-14, together with the registration, verification, reference
and reported-not-reproduced documents written around it. Their
**proposed-design status is retained**: nothing recovered or reconciled here
becomes a bound parameter, an approved seed, or a QMHP requirement.

## 1. What was searched, and how

| search | command | result |
|---|---|---|
| Every V2A file ever added | `git log --all --diff-filter=A --name-only -- docs/v2a tools/v2a` | six files, all added 2026-09-14 in commits `5dec5b1`, `1ad96a3`, `b7574e3`, `126181b`, `42e3e3a`, `9f8dda1`, `b12a8d0`, merged as pull request #1 (`a7f7a77`): the assessment, the registration, the verification record, the references, the reported-not-reproduced list, and the arithmetic checker. No numerical artefact among them |
| Every filename in all history | `git log --all --name-only --pretty=format:` filtered for capacitance, Hamiltonian, five, node, sweep, matrix, audit, submission | no match outside the six documents and this milestone's own `config/coupled/` files |
| Unreachable objects | `git fsck --lost-found` | one dangling blob (an old `README.md`), three dangling commits (work-in-progress stashes of this repository), one dangling tree; none contains V2A numerics |
| Stash and reflog | `git stash list`, `git reflog --all` | nothing beyond this milestone's own commits |
| Other branches | `git branch -a`, `git diff --name-only main <branch>` | the extra content on every other branch is Palace execution and result records only |
| Data files of any kind | repository-wide search for `.npy`, `.npz`, `.h5`, `.mat`, `.csv` | only Palace solver outputs under `results/` and the Palace test fixtures |

The assessment says so itself, in its own words, at the time it was written:
"The new five-node matrix itself is not present in my accessible project
artefact set, so I cannot independently re-invert it in this review"
(`G0-followup-audit-v0.1-deep-research-assessment.md` line 25), and lists
"EM/mode extraction demonstrating the five-node reduction is adequate over the
relevant band" among the missing physical-G0 evidence (line 471). The
`reported-not-reproduced.md` register exists precisely because the underlying
artefacts were unavailable: "The audit's own artefacts (the five-node
capacitance matrix, the diagonalisation, the sweep outputs, the ledger inputs)
are **not** in this repository, so the quantities below are reproduced nowhere
here."

**Conclusion.** The artefacts were never in this repository; there is nothing
to restore. Recovery requires them to be supplied from outside it. Until then
every quantity attributed to the submission keeps the status the repository
already gives it: reported, not reproduced.

## 2. The referenced executable artefacts

Named or implied by the submission's assessment and by the M3 registration,
none supplied:

| artefact | what it would contain | referenced at | status |
|---|---|---|---|
| Five-node Maxwell capacitance matrix | the `5 × 5` capacitance matrix of the coupled circuit, generating both self-charging and coupling terms | assessment lines 25, 45, 55 | **absent** |
| Its diagonalisation | the coupled spectrum, dressed labels and conditional mediator lines | assessment lines 25, 74, 82 | **absent** |
| Sweep outputs | the `f_C` sweep (0 to 0.30 Φ₀), the M1 static-wait sweep, the duration ladder | assessment lines 79-90 | **absent** |
| Frozen coupled Hamiltonian file | the coded `H` whose hash registration item R8 must bind | registration line 222 (`BIND`, open) | **absent** |
| Ledger inputs | the parent terms behind the error ledger | `reported-not-reproduced.md` | **absent** |
| The audit document itself | QMHP-CoPro V2A G0 follow-up audit v0.1 | assessment lines 5-6 | **absent**; only the assessment of it is held |

## 3. Reconciliation against the checkpoint-A declaration

The declaration is `config/coupled/v2a_five_node_candidate.json`. Every row
below states how it treats a submission quantity, and every one keeps the
submission's proposed-design status.

### 3.1 Agreements

| item | submission, as reported | checkpoint-A declaration | reconciled |
|---|---|---|---|
| Circuit class | fluxonium–transmon–fluxonium with a state-conditioned mediator | `proposed_structure` with nodes `F1`, `F2`, `C`, `R1`, `R2` | yes: same class, same roles |
| Node count | five **nodes** of a lumped capacitance matrix | five declared electrical nodes | yes |
| Data-qubit encoding | Branch-A logical {\|0⟩, \|2⟩} with a monitored \|1⟩ sink | `logical_states [0, 2]`, `sink_state 1`, source-bound to the frozen master | yes, and bound to the master rather than to the submission |
| Readout modes | two, retained in the static calculation, effect unresolved | `R1`, `R2` declared passive; `R2` UNBOUND | yes |
| Capacitance discipline | the Maxwell matrix must generate self-charging *and* coupling, not isolated `E_C` with appended `g` | `coupling-definition.md` §2: one `C⁻¹`, used once, both roles | yes, and §8.6 states the no-double-use rule explicitly |

### 3.2 Corrections and clarifications

| finding | detail |
|---|---|
| **"five-mode" is not the submission's term** | The V2A documents say **five-node** throughout, a statement about a lumped capacitance matrix; "five-mode" appears nowhere in `docs/v2a` (zero hits). A node is not a mode: the count of electromagnetic modes in a band is exactly what the hidden-mode screen must establish, and is not fixed by the node count. The declaration and this milestone's documents use *node*, and the earlier milestone text that said "five-mode hypothesis" is superseded by that usage. |
| **The submission's matrix is a comparison target only in its invariant content** | Were it recovered, the five-node capacitance matrix would overlap the routes' target only where that target is gauge-invariant: the charging energies of nodes carrying a declared lumped branch, each readout mode's bare frequency, and the invariant couplings. Its readout-node rows and columns depend on whatever readout-node normalisation the submission chose, and are not comparable until that convention is stated (`docs/coupled-candidate/route-a-identifiability.md`). Its provenance would also have to be settled first. It is never an input to the extraction. |
| **`f_22` does not bind the mediator** | The reported conditional transition `f_22 = 7.016031785 GHz` is one number; the mediator's `E_J,Σ`, `E_C`, junction asymmetry and flux bias `f_C` are four. Infinitely many parameter sets reproduce a single conditional line, and the line is itself a property of the *coupled* spectrum rather than of the bare mediator. Deriving mediator parameters from it would be reconstructing canonical parameters from a summary, which this milestone forbids. The declaration therefore leaves them UNBOUND with **no seed proposed**. |
| **Reported values are not seeds** | `f_22`, `Δ_min ≈ 5.90 MHz`, `n_C = 1.300454`, `ζ/2π = 62.1 kHz` and the label overlaps stay in `reported-not-reproduced.md`. None appears as a value in the declaration; the declaration cites the V2A documents only as the description of the proposed structure. |
| **Registration BIND fields remain open** | R1.1–R1.7, R1b, R1c.1–R1c.3, R2.1–R2.3, R2.5, R3.1–R3.3, R7 and all R8 sign-off fields are unbound. The declaration records the irrotational 0.5/0.5 flux split as *presumptive, not bound*, and states no drive convention at all, because this milestone runs no driven propagation. |
| **Port conventions are this milestone's, not the submission's** | The registration's R2 port normalisation and phase reference concern a crosstalk transfer function for the M3 prescreen. The ports declared here are EM lumped ports for extraction. They are unrelated and must not be conflated; when a delivered-control transfer function is eventually needed, R2 governs it. |

### 3.3 What the submission would change if recovered

Nothing automatically. Recovering it would allow three things, each a separate
decision: binding the mediator parameters from a primary source instead of
leaving them UNBOUND; comparing the extraction's gauge-invariant quantities
against the submission's, with both provenances and the submission's
readout-node convention stated; and closing registration item R8 by hashing
the coupled Hamiltonian file. None of these is in scope for
checkpoint A, and none is assumed by it.

## 4. Status retained

The submission and everything attributed to it remain **proposed design**. The
assessment's own disposition is unchanged by this recovery attempt: physical
G0 remains BLOCKED, M3 keeps its conditional go for one bounded prescreen once
the registration is bound, AMD-E stays disabled, and the standing restrictions
(no 196.773 ns Surface-17 insertion, no Branch-A-versus-Branch-C claim, no
conversion of stress values into hardware measurements, no fabrication-yield
statement, no PED/AMD-E observability calculation) all stand. This document
adds no evidence and closes no gate.
