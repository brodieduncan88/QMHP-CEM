# Palace mesh-refinement and height-sensitive verification (v0.2)

The second bounded v0.2 milestone: numerical verification of the empty-cavity
benchmark that the golden run established. It answers two questions the golden
records cannot: does the answer converge under mesh refinement, and does the
cavity height actually enter the calculation. Everything here is an
ENGINEERING-RULE of numerical verification. Nothing is a frozen QMHP
physical requirement, and nothing is evidence about the physical package.

The campaign is defined in `solvers/palace/verification.py` (frozen into
`campaign.json` with its sha256 in every record), executed by
`scripts/palace_verify_campaign.py`, and run unattended by
`.github/workflows/palace-verify.yml`. Records go to
`results/PALACE-VERIFY-<UTC>/`, append-only; the five `PALACE-GOLDEN-*`
records are not touched.

## What is executed

Each run goes through the unchanged adapter boundary
`prepare → run → parse → validate_convergence`, with its mesh length, mode
count, target and field probes set explicitly through `RunContext.extra`.
Without those overrides the adapter is byte-for-byte the golden path (a test
compares a fresh `prepare()` with the committed golden record).

**Objective 1, mesh convergence.** The 22 × 22 × 1.5 mm box at
h0 = 22/12 mm, h0/1.5 and h0/2, with the golden physics, order 2, tolerances
and target. Four modes each: (1,1,0), the degenerate (1,2,0)/(2,1,0) pair,
(2,2,0). Rules: finest-level relative analytic error ≤ 1e-4 for every mode,
relative change between the final two levels ≤ 1e-4, and the unchanged
backward-error rule. The pair is reported as both modes, their centre and
their splitting per level; that splitting is the mesh breaking an exact
degeneracy and is not physical coupling.

**Objective 2, height sensitivity.** The four golden modes are TM_mn0 and
do not depend on the height at all, so they verify nothing about Z. A
height-sensitive verification needs p ≥ 1 modes, which for a box of height d
start at f ≈ c/(2d):

| Benchmark | Box | Heights | (0,1,1) mode | modes below it | Δf_exact |
|---|---|---|---|---|---|
| `object001_height` (Object 001) | 22 × 22 mm | 1.5 / 1.65 mm | 100.163 / 91.101 GHz | 154 / 127 | −9.061 GHz (−9.05 %) |
| `aux_height` (auxiliary, not Object 001) | 22 × 22 mm | 7.0 / 7.7 mm | 22.472 / 20.625 GHz | 6 / 4 | −1.847 GHz (−8.22 %) |

The analytic enumeration is range-aware (index bounds derived from the
frequency ceiling), so the 154 modes below Object 001's first
height-dependent mode are all accounted for; a fixed index cap would not do.

The mesh rule for height runs is `min(min(a,b)/12, d/4, λ(f_target)/6)`: the
shortest structure decides, which for these boxes is four elements across the
height. Palace returns eigenvalues close to but not below its target, so the
target is placed midway between the wanted mode and the highest analytic
mode below it, and enough modes are requested to cover a 1 % window above
the mode plus a margin. Three field probes are added per run; the fraction
`Σ|E_z|²/Σ|E|²` over the probes classifies each computed mode as z-polarised
(TM_mn0, height-independent) or transverse/mixed (p ≥ 1), independently of
its frequency. Mode matching assigns computed modes to analytic ones by
frequency within 2e-3 relative, honouring multiplicity, and records the probe
family and whether it agrees; every decision is written to
`mode_matching.json`.

For the wanted mode, Δf_Palace = f(height 2) − f(height 1) is compared with
Δf_exact. Rules: relative disagreement ≤ 1e-2, and |Δf_exact| at least 10×
the numerical uncertainty, which is the change of the identified mode
between the final two mesh levels; PASS needs two mesh levels at both
heights. A single level is INCOMPLETE; a benchmark none of whose runs could
execute within the budget is BLOCKED.

**The Object 001 box.** Resolving a 100 GHz mode in a 22 mm box to the
declared rule (0.375 mm) meshes to about 545k degrees of freedom, above the
declared runner budget of 400k, so that level is BLOCKED before Palace is
launched and its mesh is kept as evidence. The campaign then makes one
bounded exploratory attempt per height at d/3 (about 260k and 215k DOF, one
hour each). Without refinement that benchmark can be at most INCOMPLETE. The
auxiliary box is what verifies the Z pipeline; it is labelled auxiliary
everywhere and is not represented as verification of Object 001.

## Execution configuration

One MPI process, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1` (the image
pins both), GitHub-hosted `ubuntu-latest`. The workflow shares the golden
workflow's layer cache, runs the campaign with `--record-pointer`, re-hashes
the record (`cem verify-results`, a mismatch fails the job), uploads it,
commits it to the branch, and fails the job if the campaign or the manifest
check did not succeed.

## Status

See `results/PALACE-VERIFY-*/report.md` for the executed campaign and its
verdicts, and the pull request that introduced this milestone for the
summary. Until a record exists on a branch, no verification claim is made.
