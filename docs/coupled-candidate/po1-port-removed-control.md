# PO1: the port-removed control, prepared against N2R

**Status: PREPARED, NOT APPROVED, NOT LAUNCHED.** Nothing here starts a run.
The file whose commit on a `palace/**` branch triggers the ladder workflow,
`.github/ladder-approval.json`, is untouched, and the driver cannot yet
produce this configuration (§7). No extraction, no target amendment, no merge:
PO1 computes no coupling value, no residue and no invariant triple, and
authorises none. Record: `experiments/PO1-port-removed-control/`.

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

## 4. The changed null space, accounted for

Removing `K_port` adds **exactly one** direction to the null space of `K`: the
floating-potential gradient of the F1 island, the field `∇ψ` with `ψ` constant
on the island, constant on the grounded group and varying between. It is
curl-free and has zero tangential trace on every PEC sheet, so it always lies
in `ker(K_curl)`; with the port active it is *not* in `ker(K)`, because its
tangential trace on the port face is non-zero and `K_port` gives it energy.
That is precisely what makes it N2R's mode 1 at 1.526 GHz, whose magnetic
energy is 0.18 % of its electric energy. Removing the port removes its only
restoring force.

**Exactly one**, because there is one direction per conductor group
galvanically isolated from ground once the lumped inductances are gone, and
the island is the only such group: the coupling pad, the CPW and the ground
plane are a single group through the CPW short bar.

**The solver's handling is not assumed.** `eigensolver.cpp:164-173` builds a
`DivFreeSolver` and installs it as the eigensolver's projector, applying it to
the starting vector at `:191-193`. Whether the island's floating mode lies in
that projector's range depends on whether the auxiliary H1 space leaves the
island's potential free or constrains it with the other PEC boundaries, which
this preparation did **not** settle from the pinned source. Both outcomes are
pre-declared:

- **Case A, projected out.** No near-zero mode is returned; the lowest
  returned mode is a field resonance. No slot cost.
- **Case B, returned.** One mode at `f ≈ 0` is returned and, under
  shift-invert at `Target 0.5 GHz`, is found first. One slot of six.

Whichever occurs is the observation. A near-zero mode is never discarded,
renamed or filtered out, and the target is not retuned mid-run to avoid it.
**Two or more near-zero modes would falsify this accounting**, and the control
would be reported as falsified rather than reinterpreted.

**The check that the operator really changed.** With `K = K_curl` alone, the
Rayleigh identity is complete without a port term, so every converged
eigenpair with `λ > 0` satisfies `E_mag = E_elec + E_cap` exactly. The
pre-declaration is therefore

```
E_mag / (E_elec + E_cap) = 1   to solver tolerance, for every field-resonant mode
```

against N2R's 0.9982 and 0.9991 for its two field-resonant modes, the deficit
being the port energy. A failure voids the control and is reported as void;
the check is not relaxed. `E_ind` is still written but now corresponds to no
term in the operator, so the N2R-style ratio `(E_mag + E_ind)/(E_elec + E_cap)`
is meaningless for PO1 and must not be computed as its equipartition test.

## 5. Mode matching: field evidence, never frequency proximity

`numerical-plan.md` §2 classifies a mode from probe polarisation fractions at
three declared points together with the F-site participation. The solved N1R
and N2R configs carry no probe block and their records carry no `probe-E.csv`,
so that declared classification has never been executable. PO1 adds the three
points, from the registered geometry, at a common 0.010 mm above the chip
surface:

| probe | centre (mm) | over |
|---|---|---|
| 1 | `(−0.600, 0.000, 0.010)` | the F1 island, at its centre |
| 2 | `(−0.455, 0.000, 0.010)` | the R1 coupling pad, the resonator's open end |
| 3 | `(0.5865, 0.500, 0.010)` | the R1 CPW at half its 6.983 mm centre line |

Point 3 is computed from `solvers.palace.coupled_geometry` and lies inside the
CPW conductor rectangle `(0.370, 0.475)–(0.670, 0.525)`. The common height
makes the three comparable; all three are inside the vacuum domain (L2 sizes:
`h_gap` 0.010, `h_near` 0.0067, `h_far` 0.2222 mm). A probe outside the mesh
yields 0.0 with a Palace warning, which the record's parser checks rather than
accepting silently. Probes add no bilinear form, so they cannot move an
eigenvalue.

**Declared before the run.** With `s_i = |E(P_i)|² / Σ_j |E(P_j)|²` from
`probe-E.csv` (the complex magnitude, summed over components), `p_port` the
exact port-face tangential fraction from `surface-Q.csv` through
`solvers/palace/port_diagnostic.py`, and `|p|` the non-loading rank-one weight
from `port-EPR.csv`:

- **readout-like**: `s₂ + s₃ > 0.5` **and** `s₁ < 0.5` **and** `p_port < 0.5`;
- **island-like**: `s₁ > 0.5` **or** `p_port ≥ 0.5`;
- otherwise **hidden**, and reported.

The readout-like mode is the **unique** mode satisfying the first rule. If
there is none, or more than one, the control is **INCONCLUSIVE for mode
identity** and is recorded that way: no frequency tiebreak, and no threshold
adjusted after seeing the values. The reading of "probe polarisation
fractions" above is explicit and stated in advance; it is a reading of the
declared rule, not a replacement for it.

`s₂/s₃` characterises the quarter-wave standing-wave profile and is reported
beside N2R's at the same points as a consistency observation. It is never used
to choose a mode.

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
operator is not N2R's: `K` is softer by a positive semidefinite term and the
null space is one direction larger, either of which can move GMRES and AMS
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

## 7. What execution would still need, deliberately not done

The ladder driver cannot produce this configuration.
`solvers/palace/coupled_config.build_coupled_config` has no port-deactivation
parameter, and the approval allow-list `_SOLVER_LINEAR_OVERRIDE_KEYS` admits
only `MGMaxLevels` and `MGUseMesh`, both under `Solver.Linear`; a
boundary-level override lies outside it and is refused before launch, by
design. Executing PO1 needs one new declared, validated driver option setting
`Boundaries.LumpedPort[<index>].Active`, with the treatment the solver
overrides already get: an explicit allow-list entry, a recorded
applied/replaced/unchanged block, and refusal of any key outside it.

That is left undone on purpose. Implementing it creates the execution path,
and this is approval material, not an execution trigger.

## 8. What PO1 would and would not settle

**Would.** Whether the zeros of `G_F` computed from N2R's saved participations
are the F-open environment frequencies at this discretisation.
[`fem-spectral-mapping.md`](fem-spectral-mapping.md) §5 gives those zeros for
N2R as 15.099644 GHz² (normalised removal, `K − Q/N`) and 15.099651 GHz²
(declared removal, `K − Q`), i.e. 3.885826 and 3.885827 GHz. PO1's
readout-like eigenfrequency is the measured value to compare them against. If
they agree, the rank-one removal is an adequate stand-in **at this
discretisation, for this mode**. If they disagree, the disagreement is the
measured operator-mapping error, replacing the unbounded status.

**Would not.** It is a frequency comparison, not an extraction: no residue, no
coupling, no `E_C`, no triple. It is one mesh, so it is neither a continuum
result nor a bound. It does not measure the normalisation `N = fᵀK⁺f/L` of
§3 of that note, so `E_C,F1F1` stays unavailable. It does not licence any
amendment to the registered target, and it is not an approval to extract.
