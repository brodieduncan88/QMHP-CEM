# PO1: the port-removed control, prepared against N2R

**Status: PREPARED, NOT APPROVED, NOT LAUNCHED.** Nothing here starts a run.
The file whose commit on a `palace/**` branch triggers the ladder workflow,
`.github/ladder-approval.json`, is untouched and carries no `port_control`
key. The driver can now *build* this configuration through one narrow,
validated option (§7); it cannot start it without that file. No extraction, no
target amendment, no merge: PO1 computes no coupling value, no residue and no
invariant triple, and authorises none. The single approval that would run it
once is §9. Record: `experiments/PO1-port-removed-control/`.

## 1. Why this control exists

[`fem-spectral-mapping.md`](fem-spectral-mapping.md) §4 records that the
difference between the rank-one removal the spectral construction performs and
the removal of the assembled port operator is **unbounded by the current
evidence**, and §10 names the evidence that would settle it: one eigenmode
solve of the same discrete problem with the F1 lumped inductive port absent,
whose spectrum *is* the F-open environment. PO1 is that solve, prepared.

It replaces an unbounded quantity with a measured one. It does not make the
spectral construction correct, and it is not a step toward a coupling value.

## 2. The exact change: `K → K − K_port`

One boolean in the existing lumped-port block:

```
Boundaries.LumpedPort[0].Active = false
```

Palace assembles the port's boundary mass term `1/L_s` into the **stiffness**
only for an active port: `AddStiffnessBdrCoefficients`
(`lumpedportoperator.cpp:571-591`) returns early at `:577` when
`!data.active`. So the assembled operator loses exactly

```
K_port(E,E) = ∫_Γ (1/L_s) |E_t|² dS ,   L_s = L · (w/l) · n_elem
```

and nothing else. `AddDampingBdrCoefficients` and `AddMassBdrCoefficients`
gate on the same flag but are already inert for this port (`R = C = 0`).
`Active` is a declared lumped-port field (`boundaries.md:259`, parsed at
`configfile.cpp:937`); its prose names only the damping condition, which is
incomplete, and the source is taken as decisive.

**Every F-site diagnostic survives**, which is why deactivation is preferred
to deleting the port block: `UpdatePorts` (`postoperator.cpp:430`),
`PostprocessEPR` and `GetInductorParticipation` (`postoperator.cpp:644`) and
`GetLumpedInductorEnergy` (`postoperator.cpp:493`) all loop over every port
with **no** active check. So `port-V.csv`, `port-I.csv`, `port-EPR.csv` and
`E_ind` are still written, now as **non-loading** functionals of a different
operator's eigenvectors — comparable with N2R's in kind, never in value. The
two interface-dielectric probes on the port face are independent of the
lumped-port block and carry over unchanged.

## 3. Comparison against N2R's solved configuration

The candidate is N2R's solved `config.json` byte-for-byte with two additions.
`prepare.py` verifies the baseline's SHA-256, asserts that it round-trips
through the driver's own serialisation, flattens both documents to leaf paths
and refuses to write unless the delta is exactly the expected set. The literal
diff is `config.delta.txt`:

```
@@ -60,7 +88,8 @@
         "Direction": "+Y",
-        "L": 1.0345665367517793e-07
+        "L": 1.0345665367517793e-07,
+        "Active": false
```

plus a `Domains.Postprocessing.Probe` block of three points (§5).

| item | N2R (solved) | PO1 (candidate) |
|---|---|---|
| mesh file / SHA-256 | `coupled_chip_cell_L2.msh`, `d8dc1a92…c14428` | identical, hash-gated before launch |
| `Model.Refinement` | `UniformLevels: 0`, one box, `Levels: 2` | identical |
| `Solver.Order` | 1 | 1 |
| `Solver.Linear` | `Default`, GMRES, `Tol 1e-08`, `MaxIts 400`, **`MGMaxLevels: 1`** | identical |
| `Solver.Eigenmode` | `N 6`, `Tol 1e-06`, `Target 0.5`, `Save 6` | identical |
| materials, PEC set | attributes 1/3, PEC {2, 4} | identical |
| port face, `Direction`, `L` | attribute 10, `+Y`, 103.457 nH | identical |
| port `Active` | absent, i.e. **true** | **`false`** — the only operator change |
| `Boundaries.Postprocessing.Dielectric` | indices 1 and 2 on attribute 10 | identical |
| `Domains.Postprocessing.Probe` | absent | three declared points — postprocessing only |
| config SHA-256 | `79304b5f…ba8c1f33f` | `2826e78c…667e0d1728` |

N2R requested six modes and Palace converged nine; `Save: 6` is why its field
archive holds six. PO1 keeps the same request.

## 4. The changed null space: the earlier count is withdrawn

**Withdrawn.** The earlier statement that removing `K_port` adds *exactly one*
direction to `ker(K)` — and with it the rule that two or more near-zero modes
would falsify the accounting — is withdrawn. It rested on the F1 island being
a galvanically **floating** conductor group in the discrete problem. It is
not: the island is a zero-thickness metal sheet carrying PEC (the PEC set
includes the sheet attribute), so its potential is pinned, not free, both in
the essential set of the ND space and in the auxiliary H1 space. No count is
put in the withdrawn one's place, and there is no predicted count left to
falsify.

**What is provable from the assembly alone.** `K = K_curl + K_port` with both
terms positive semidefinite, so `ker K = ker K_curl ∩ ker K_port` and PO1's
kernel `ker K_curl` contains it. The enlargement is
`dim ker K_curl − dim(ker K_curl ∩ ker K_port)`, bounded above by
`rank K_port` and otherwise **not determined by anything in the record** —
and [`fem-spectral-mapping.md`](fem-spectral-mapping.md) §2 already refutes
`rank K_port = 1` for the assembled operator, so even that bound is not one.
This preparation computes neither dimension and reports the enlargement as
undetermined.

**Four things that must not be conflated.**

1. **The raw gradient null space.** `ker K_curl` on the PEC-constrained ND
   space contains every discrete gradient `∇ψ` for `ψ` in the auxiliary H1
   space with its essential DOFs removed (up to any cohomology of the domain,
   which is not established here). Its dimension is of order the free H1 DOF
   count: N2R's own log prints `H1 (p = 1): 17447, ND (p = 1): 103411` for the
   space it assembles, and PO1 assembles the same one — so of order 10⁴, not
   one. It is present in N2R exactly as in PO1 and is **not** what removing the
   port changes. It is why a divergence-free projector exists at all.
2. **Conductor-charge modes.** The finite-dimensional subspace of (1) spanned
   by gradients of potentials taking different constants on galvanically
   isolated conductor groups. Here there are none of the relevant kind: every
   metal sheet carries PEC, so every conductor potential is pinned. This is
   the space the withdrawn count appealed to.
3. **The projector's removed space.** What `DivFreeSolver` actually removes:
   the ε-weighted projection onto `range(Grad)` restricted to the **free**
   auxiliary H1 space — the space left by `aux_bdr_tdof_lists`
   (`linalg/divfree.cpp:53-160`). It is a *solver* subspace defined by
   `aux_bdr_marker`, not by `ker K`, and it need not equal (1). Palace's own
   source comment records that it does not suffice: `// As tested, this does
   not eliminate all DC modes!`
4. **Returned near-zero eigenpairs.** What the run reports. Whether a
   direction lies inside the projector's range, and whether SLEPc converges an
   eigenpair near zero, are separate questions from whether it lies in a
   kernel. Only this one is observable, and it is what PO1 records.

### 4.1 The projector changes automatically, and is not configured

`GetLsAttrList()` begins `if (!data.active) { continue; }`, so an inactive
port contributes no attributes to it. `spaceoperator.cpp` builds
`lumped_port_Ls_marker` from that list, ORs it into `aux_bdr_marker` with the
`dbc`, farfield, `surf_sigma`, `surf_z` Rs/Ls, lumped-port Rs and wave-port
markers, and fills `aux_bdr_tdof_lists` by `GetEssentialTrueDofs` on every H1
level. `eigensolver.cpp:164-173` hands `space_op.GetAuxBdrTDofLists()` to the
`DivFreeSolver`, which `:191-193` applies to the starting vector.

In N2R the port face enters `aux_bdr_marker` **only** through
`lumped_port_Ls_marker`: it is not in the PEC set, `R = 0` so `GetRsAttrList`
skips it regardless, and there is no surface impedance, wave port or farfield
boundary. With `Active: false` it leaves `aux_bdr_marker` altogether, so

```
aux_bdr_marker(PO1) = aux_bdr_marker(N2R) minus the port-face attribute
```

The auxiliary essential set **shrinks**, the free auxiliary H1 space **grows**,
`range(Grad)` grows with it, and the subspace the projector removes can only
grow. That monotone statement is all that is established; *which* additional
directions it removes is not, and is not assumed.

**No setting is touched.** `DivFreeTol` and `DivFreeMaxIts` stay at Palace's
defaults, exactly as in N2R. The change above is a consequence of the `Active`
flag — recorded, not configured.

**What this costs the control.** PO1 does not isolate `K → K − K_port` in the
solver. It changes the assembled operator *and*, by the same flag, the
projector's constraint set. Any PO1-versus-N2R difference is attributable to
that **pair**, not to the operator alone. Separating them would need a further
control, which is not proposed and not approved here. This is a stated
limitation of the control, not a defect to work around.

### 4.2 Near-zero-frequency postprocessing

A near-zero mode is not merely uninformative here: in pinned Palace it can
**abort the run** during postprocessing, before any row for it is written.

1. With no damping matrix the EVP is linear in `μ = ω²` and `ω = √μ`. A
   numerically tiny **negative** `μ` gives a purely imaginary `ω` whose real
   part is exactly `0.0`.
2. `B *= -1.0 / (iω)`. At small `|ω|` this amplifies `∇×E` by `1/|ω|`; at
   `ω = 0` it is a division by zero and `B` is non-finite. `E_mag` is computed
   from `B`, so a near-zero mode's `E_mag` is not a meaningful energy and may
   be `inf` or `nan`.
3. The eigenmode fields are complex, so `HasImag()` is true and
   `UpdatePorts` reaches `MFEM_VERIFY(omega > 0.0, "Frequency domain lumped
   port postprocessing requires nonzero frequency!")`. `ω.real() ≤ 0` aborts.
4. That abort is raised **before** `Postprocess` for the mode, so no
   `eig.csv`, `domain-E.csv`, `port-EPR.csv` or `probe-E.csv` row is written
   for it. Under shift-invert at `Target 0.5 GHz` a near-zero mode would be
   ordered *first*, so the worst case is a run with **no CSV rows at all**.

**What survives, in every case.** `palace_log.txt` is the merged
stdout+stderr stream and is written by the driver whatever the exit code, so
the abort message and everything printed before it are preserved. Rows for
modes earlier in the loop are already on disk: each CSV is opened, written and
closed per mode (`basesolver.hpp:48`, append for `i > 0`). The solver
directory is bind-mounted, so files written inside the container survive its
death. A non-zero exit is recorded as `RUN_FAILED` with the log; a post-solve
analysis exception is recorded as `ERROR` and still leaves the run block, the
log and the files in the record.

**Pre-declared handling.** Whatever is returned is reported: the number of
near-zero modes, their frequencies, backward errors and energies, and every
Palace warning. Nothing is discarded, renamed or filtered. The target is
**not** moved away from 0.5 GHz, `N` is not changed, the probes are not
removed and no `DivFree` setting is touched to avoid a near-zero mode. There
is no retry. If no usable positive-frequency result comes back, that
limitation *is* the reported outcome.

**One precondition.** `Domains.Postprocessing.Probe` requires an image built
with GSLIB; without it `fem/interpolator.cpp` aborts at setup with
`InterpolationOperator class requires MFEM_USE_GSLIB!` and nothing is solved.
`docker/palace.Dockerfile`, which this workflow builds, sets
`-DPALACE_WITH_GSLIB=ON`, and committed records under
`results/PALACE-VERIFY-20260915T091242Z` carry `probe-E.csv`. If it ever
fails, the abort is the outcome; the probe block is not removed to rescue it.

### 4.3 The energy diagnostics, corrected

The quantity is `d_m = |E_mag/(E_elec + E_cap) − 1|` from `domain-E.csv`
(`E_cap ≡ 0` here, and is kept in the denominator only for form). With
`K = K_curl` alone, a converged eigenpair with `λ_m > 0` satisfies
`E_mag = E_elec + E_cap` exactly, because no port term is left in the Rayleigh
identity.

N2R's values for the same ratio — **correcting** an earlier draft of this
record, which quoted 0.9982 and 0.9991. The first of those is
`1 − E_mag/(E_elec + E_cap)` for m1, the assembled-operator participation, not
the ratio:

| mode | f (GHz) | `E_mag/(E_elec+E_cap)` | `(E_mag+E_ind)/(E_elec+E_cap) − 1` | backward error |
|---|---|---|---|---|
| m1 | 1.526014889 | **0.0017759330546** | −7.19e-6 | 2.12e-17 |
| m2 | 3.887370723 | **0.9990613568591** | −1.11e-7 | 4.19e-17 |

m2 keeps 99.906 % of its stiffness energy in the curl term; m1 keeps 0.178 %,
so 99.82 % of m1's restoring energy is the port term. That is why removing the
port is expected to move m1 a long way. **m1 is not asserted to be a curl-free
floating eigenvector**: its magnetic energy is 1.184775005e-05 J against
6.671281904e-03 J of electric energy — small, but not zero — and PO1 does not
pre-declare that its counterpart goes to exactly zero frequency.

**Acceptance threshold: `d_m ≤ 1e-3`**, for every returned mode with a
positive frequency. It is the tolerance of the frozen admission rule
`qmhp-cem.mode-admission/0.1.0` (`|R − 1| ≤ 1e-3`), reused verbatim so that no
new number is invented for this run. It is an inherited engineering tolerance,
**not** a bound derived from the solver's backward error: in N2R's own record
the backward errors are ~1e-17 while the corresponding energy discrepancies
are 7.19e-6 and 1.11e-7 — nine to eleven orders of magnitude larger. `d_m` and
the backward error are reported as two independent columns for every returned
mode, whatever the verdict, and neither is presented as bounding the other. If
no returned positive-frequency mode satisfies it, the control is **void** and
is recorded void; the threshold is not moved after seeing the values.

**Hypothetical and reference only.** `E_ind` is still written, from the same
rank-one width-averaged voltage, and corresponds to **no** term in PO1's
operator: the N2R-style ratio `(E_mag + E_ind)/(E_elec + E_cap)` is meaningless
here and is not computed as PO1's acceptance test. `|p|` from `port-EPR.csv`
is a non-loading rank-one diagnostic of a different operator's eigenvectors.
The derived `p_port = κ·(p_D − p_MA)/ω²` is an *inductive* participation
carrying `L_s` and a `1/ω²` factor; with the port inactive it backs no operator
term and at small `ω` it diverges — reference only, and **not** a
classification gate. The one field-only quantity that stays meaningful is
`p_D − p_MA`, the tangential-field energy fraction on the port face: it is
reported for every mode as a localisation observation, with **no** declared
threshold, because none has ever been declared and inventing one here would be
a post-hoc gate. A PO1 record will also carry the driver's unchanged
`admission`, `roles`, `port_field_test` and `port_diagnostic` blocks, whose
admission ratio includes `E_ind`; for a port-removed run they are reference
diagnostics, neither suppressed nor read as PO1's physical classification.

## 5. Mode identification: a new localisation diagnostic, declared in advance

`numerical-plan.md` §2 classifies a mode by (i) the inductive participation
`p_mF` of the F1 site and (ii) "the probe polarisation fractions at three
declared probe points", calling a mode readout-like if "its resonator-probe
energy dominates" and `p_mF < 0.5`.

**Clause (i) cannot be applied here.** `p_mF` is an inductive participation;
with the port inactive it backs no operator term, so gating on it would be
exactly the hypothetical-participation gate this control must not apply. It is
reported, not gated on.

**Clause (ii) names two different quantities.** A *polarisation fraction* is a
per-component share at one point; "resonator-probe energy dominates" is a
share of intensity *across* points. What PO1 defines is the second:

```
s_i = |E(P_i)|² / Σ_j |E(P_j)|²,   |E|² = Σ_c (Re E_c² + Im E_c²),  from probe-E.csv
```

a **spatial intensity-localisation share**. It implements the energy clause
and is a **new diagnostic**, declared here in advance. It does **not**
implement the polarisation clause and does not replace it: that clause remains
**unexecuted** and is reported as unexecuted. No per-component fraction is
computed, claimed or substituted.

The three points, from the registered geometry at a common 0.010 mm above the
chip surface, pinned as `PO1_PROBES_MM` in `solvers/palace/coupled_config.py`:

| probe | centre (mm) | over |
|---|---|---|
| 1 | `(−0.600, 0.000, 0.010)` | the F1 island, at its centre |
| 2 | `(−0.455, 0.000, 0.010)` | the R1 coupling pad, the resonator's open end |
| 3 | `(0.5865, 0.500, 0.010)` | the R1 CPW at half its 6.983 mm centre line |

**The rule.** `readout-like` if `s₂ + s₃ ≥ 0.9`; `island-like` if `s₁ ≥ 0.9`;
otherwise **indeterminate**, reported as hidden and assigned to neither site.
The 0.9 margin is **ad hoc and declared before any PO1 number exists** — not
derived from anything. The declared rule's own boundary is 0.5 ("dominates"),
and 0.9 lies strictly inside it, so nothing the declared reading would call
readout-like is called island-like here or the reverse; the only difference is
that the ambiguous middle is *refused* rather than forced into a class. It is
not moved after seeing the values. The classification rests on the probe
shares **alone**: `p_mF`, `|p|`, `p_port` and `p_D − p_MA` are all reported
beside it and none of them gates it.

**Selection.** If exactly one returned mode with `d_m ≤ 1e-3` is readout-like,
it is recorded as **the candidate readout-like mode**. If none is, or more
than one is, the control is **INCONCLUSIVE FOR MODE IDENTITY** and is recorded
that way. No frequency tiebreak is applied, and no threshold is adjusted after
seeing the values. "The nearest frequency is R1" is not an outcome this record
may contain.

**What the rule does not establish.** Three point samples cannot establish
that the selected mode is the quarter-wave **fundamental** rather than a
higher harmonic that happens to be large at both resonator points. The record
says *candidate readout-like mode*, never *the fundamental*. PO1 requests
`Save: 6`, so its own run would produce ParaView fields showing the node and
antinode structure along the CPW — supplementary evidence PO1 could supply
afterwards, not part of the pre-declared rule, not available before the run,
and nothing here rests on it. `s₂/s₃` is reported as a standing-wave
consistency observation; consistent with a quarter-wave profile is not proof
of one, and it never chooses a mode.

**Assumptions, stated in advance.** That `|E|` at three points at a common
height characterises where a mode lives (not proved); that 0.010 mm above
`z = 0` is inside the vacuum domain at all three points (L2 sizes: `h_gap`
0.010, `h_near` 0.0067, `h_far` 0.2222 mm) and that the value is a GSLIB point
evaluation of the FE field rather than a cell average; that `Center` is read in
mesh length units (mm) in the spec §7.3 frame, which is how Palace reads it;
and that point 3 lies inside the CPW conductor rectangle
`(0.370, 0.475)–(0.670, 0.525)`.

**Inconclusive outcomes, declared in advance.** No readout-like mode, or more
than one → inconclusive. Any probe value returning `0.0` with the Palace
warning `Probe k at (…) m could not be found! Using default value 0.0!`
(`fem/interpolator.cpp:47-58`) → the shares are void → inconclusive; a zero is
never accepted silently. `probe-E.csv` absent, or the run aborted before it was
written → inconclusive, with the log as the evidence. A mode with `d_m > 1e-3`
is not classified at all, and is reported with its numbers and no class. A
near-zero-frequency mode is reported and not classified: its `E_mag` comes
from `B = −∇×E/(iω)` and is not a meaningful energy.

**The N2R comparison at the same locations is UNAVAILABLE.** N2R's solved
config carries no `Domains.Postprocessing.Probe` block and its record carries
no `probe-E.csv`, so the quantity was never computed for N2R. The only
conceivable source is N2R's saved-field archive (GitHub Actions run
35313973073, artifact 10533683685, sha256 `1ca851c4…9eb8b0e`), which is not
reachable from this environment and is a Float32 ParaView export: resampling
it would not be the same functional as a GSLIB point evaluation of the FE
field, so even if fetched it would approximate a *different* quantity. So
`s_i` and `s₂/s₃` are reported for PO1 **alone**, with no baseline. The absence
is labelled, not approximated, and it is not replaced by a frequency argument.
Producing one would mean re-solving N2R with the probe block: a second run,
not approved and not requested here.

Probe classification is **mode-identity** evidence. It does not bear on the
operator-mapping question, which is what PO1's eigenvalues address.

## 6. Resources and the unchanged refusal conditions

| quantity | value |
|---|---|
| expected degrees of freedom | 103 411, **a prediction** |
| budget | 250 000 (41.4 % used) |
| cap | 2 700 s |

The DOF count is a prediction, not an estimate: the mesh, box and order are
N2R's and N2R's probe read 103 411, and the finite element space does not
depend on a boundary condition's `Active` flag. A different count means the
mesh is not N2R's and the comparison is void.

**No runtime is predicted.** N2R solved the same size in 159.0 s, but PO1's
operator is not N2R's: `K` is softer by a positive semidefinite term, its
kernel is larger by an amount §4 declines to count, and the projector's
constraint set changes with it (§4.1). Each of those can move GMRES and AMS
behaviour in either direction.

The existing conditions apply unchanged:

- **REFUSED-DOF-BUDGET** if the probe reads more than 250 000; Palace's solve
  does not proceed.
- **TIMEOUT** at the 2 700 s cap. The timeout is the result, recorded as such,
  with no second attempt under the approval and no change to the cap.
- **RUN_FAILED** if the container or solver dies; likewise the outcome.
- The **mesh hash gate** refuses any mesh other than `d8dc1a92…c14428`.
- No threshold, tolerance, budget or cap is changed to rescue any of these.

PO1 is at the same depth as N2R, so it is **not** a rung of the refinement
sequence and must not enter the L1/L2/L3 fit or any convergence statement.

## 7. The minimal execution path: built, tested, not armed

The driver can now produce this configuration, through one option that names
no boundary.

- **`solvers/palace/coupled_config.py`** gains one keyword, `port_active`
  (default `True`). `False` emits `Boundaries.LumpedPort[0].Active = false`
  after `L` and changes nothing else; the key is **absent** when the port is
  active, so every existing config is byte-identical. `PO1_CONTROL_ID` and
  `PO1_PROBES_MM` are pinned in the same module, and `prepare.py` imports the
  probes rather than restating them.
- **`scripts/palace_order1_ladder.py`** gains `approved_port_control()`, which
  accepts the single exact string `"PO1-port-removed"` from the approval
  record and refuses anything else. The approval carries that identifier and
  nothing else — no port index, no attribute, no configuration key, no
  coordinate — so it cannot reach any other boundary.

**Refused before any launch:** any other `port_control` value or type (an
unknown value must not degrade to "no control" — a run that silently kept the
port active would be N2R re-solved and would be recorded as the control it is
not); `port_control` without a `palace_refinement` block; a
`palace_refinement.id` other than `"PO1"` (the id is the record directory's
suffix, and the control must not be able to write into the historical record
of the baseline it is compared with); a `baseline_record` other than N2R's;
and `port_control` combined with `port_refinement`.

One guard needed a narrow, declared exception. `approved_palace_refinement`
refuses a *refined* baseline unless it is a strictly shallower point of the
same sequence — correct for a refinement step, but PO1 is not one: it wants a
baseline that is **identical**. The exception fires only when the approval
carries the pinned `port_control` identifier, and it demands exact equality in
every box (`is_identical_refinement`), which is *stricter* than the existing
"not shallower" test. Every other approval sees the unchanged rule; a
refinement step must still be strictly deeper somewhere.

**The generated config is verified against the prepared candidate.** A test
builds it through the driver's own path — `build_coupled_config` with the
pinned PO1 option, then the approval's `Model.Refinement.Boxes` and the
`MGMaxLevels` override applied exactly as `execute_level` applies them —
serialises it as the driver does, and asserts it equals
`config.candidate.json` byte for byte, SHA-256 `2826e78c…667e0d1728`.

**Nothing is armed.** `.github/ladder-approval.json` is untouched, carries no
`port_control` key, and its committed `palace_refinement` is still N1R's.
Committing that file on a `palace/**` branch is what starts a run. Every test
here runs offline: no container, no Palace invocation. A PO1 run would write
to `results/COUPLED-LADDER-O1-L2-PO1-<stamp>/`, a new directory; N2R's record
is never opened for writing.

## 8. What PO1 would and would not settle

**Would.** Whether the zeros of `G_F` computed from N2R's saved participations
are the F-open environment frequencies at this discretisation.
[`fem-spectral-mapping.md`](fem-spectral-mapping.md) §5 gives those zeros for
N2R as 15.099644 GHz² (normalised removal, `K − Q/N`) and 15.099651 GHz²
(declared removal, `K − Q`), i.e. 3.885826 and 3.885827 GHz. If the declared
rule of §5 selects a candidate readout-like mode, its eigenfrequency is the
measured value to compare them against. If they agree, the rank-one removal is
an adequate stand-in **at this discretisation, for this mode**. If they
disagree, the disagreement is a measured difference that replaces the
unbounded status — measured, but **for the pair** of §4.1: the operator change
and the projector-constraint change that the same flag forces. It is not the
operator-mapping error alone, and this control cannot separate the two.

**Would not.** It is a frequency comparison, not an extraction: no residue, no
coupling, no `E_C`, no triple. It is one mesh, so it is neither a continuum
result nor a bound. It does not measure the normalisation `N = fᵀK⁺f/L` of
§3 of that note, so `E_C,F1F1` stays unavailable. It does not licence any
amendment to the registered target, and it is not an approval to extract. And
it settles nothing at all if §4.2's near-zero case aborts the run, or if §5's
rule returns no unique candidate: both are pre-declared outcomes, recorded as
they fall.

## 9. The single approval needed

One execution of PO1, once. To give it: add `"port_control":
"PO1-port-removed"` to `.github/ladder-approval.json`, set
`palace_refinement.id` to `"PO1"` with N2R's boxes
(`[{Levels: 2, BoundingBoxMin: [-0.62, -0.125, -0.01], BoundingBoxMax:
[-0.58, -0.065, 0.01]}]`) and `solver_linear_overrides {MGMaxLevels: 1}`, set
`baseline_record` to `COUPLED-LADDER-O1-L2-N2R-20260918T061455Z`, keep
`baseline_mesh_sha256` `d8dc1a92…c14428`, and commit it on the `palace/**`
branch. Nothing else changes.

That authorises **one solve**, at the unchanged 250 000-DOF rule and 2 700 s
cap, with no retry. It authorises no second attempt, no other level, no
extraction, no Route A or Route B result, no coupling value, no
registered-definition amendment, no budget or cap change, and no merge of
PR #7.
