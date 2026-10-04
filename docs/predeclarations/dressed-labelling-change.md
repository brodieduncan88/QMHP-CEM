# Dressed-state labelling: per-row argmax replaced by a one-to-one assignment

**Status: PREDECLARED. NOT EXECUTED.** This is a change to a scientific definition
(`CLAUDE.md` section 3), merged in PR #10 (`da1def2`) without a predeclaration.
This record declares how it is validated. It does not approve or revert it.

## The change

`models/dressed_system.py` labelled each of the six tracked bare states
`(level, photon)`, for levels 0 to 2 and photons 0 and 1, with the dressed
eigenvector of largest overlap, independently per row. The same eigenvector
could take two labels near an avoided crossing. It now uses
`scipy.optimize.linear_sum_assignment` to maximise total overlap with six
distinct eigenvectors.

## Known

At the production point (Nq = 10, Nph = 12, nominal Branch-A parameters, g =
0.150 GHz), every nominal output is bit-identical between `1ebc07a` and `79844b7`:
the root (4.301974466427182 GHz), the three pulls, the six labels with their
eigen-indices, omega24, the Purcell weight, the sink line, and the regression
pins. Nothing is known away from that point. REL-QT-QN1 records that the QuTiP
cross-check shares the labelling rule, so it is not independent evidence here.

## Question

Away from the production point, where do the two rules disagree, and where
they disagree, which rule gives the label that adiabatic continuation from
g = 0 gives?

## Method (fixed now)

1. **Algorithm identity.** An independent brute-force maximiser, searching all
   injective maps from the six bare states into the 12 largest-overlap
   eigenvectors in plain Python with no scipy, must give the same assignment as
   `_assign_bare_labels` at every grid point. Any difference is a FAIL of the
   implementation.
2. **Rule comparison.** On a fixed grid, record every point where per-row argmax
   and the assignment disagree. The grid: g from 0.025 to 0.400 GHz in 0.025
   steps; readout frequency from the nominal root −300 MHz to +300 MHz in
   10 MHz steps; EC, EJ and EL each at nominal and ±10 %. Truncation is fixed at
   Nq = 10, Nph = 12.
3. **Ground truth.** At each disagreement point, continue the labels
   adiabatically from g = 0 to the point's g in 200 equal steps, carrying each
   label by maximum overlap with the previous step's eigenvector.

## Acceptance

- **PASS:** step 1 finds no difference, and at every disagreement point the
  assignment equals the continuation label.
- **FAIL:** any step-1 difference, or a point where argmax matches continuation
  and the assignment does not.
- **INCONCLUSIVE:** any point where the continuation itself is ambiguous, meaning
  an adjacent-step overlap below 0.5. It is reported, not resolved.

## Budget and evidence

CPU-only, at most 30 minutes wall time, one attempt. The output is a new record
outside the frozen `results/` set, holding the grid, every disagreement point,
the three verdicts, and the code commit. A FAIL or INCONCLUSIVE is preserved and
stops further work on the change until the owner decides.
