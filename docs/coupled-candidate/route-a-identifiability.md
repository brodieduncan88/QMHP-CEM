# Route A: the readout-normalisation problem and its resolution

**Status:** correction to the checkpoint-A extraction definition, demonstrated
on synthetic circuits. No coupled EM solve has been run. The 10 % agreement
ENGINEERING-RULE is unchanged and nothing here is compared against it.

## 1. The defect in the checkpoint-A definition

`coupling-definition.md` §3 as first written declared the extraction target to
be

> the off-diagonal charging-energy matrix `E_C,kl` … together with the
> diagonal `E_C,kk` and the bare linear-mode parameters `(E_C,RR, E_L,R)` of
> each readout node … **These are circuit-level, convention-free quantities:
> the geometry alone decides them.**

For the fluxonium node that is true. **For a readout node it is false**, and
the error is load-bearing, because it would have had Route A report a
convention as a measurement.

A node variable is only defined once something fixes its scale. The fluxonium
node has a declared lumped branch across a declared port surface, so its flux
is the flux across that branch and its scale is fixed. The readout node has no
lumped element: it is a distributed mode, and the EM model contains nothing
that says whether "the readout node flux" means the voltage at the open end,
at the tap, or anywhere else. The rescaling

```
Φ_R → s Φ_R ,   Q_R → Q_R / s        (s > 0)
```

leaves the Hamiltonian identically unchanged while moving

```
(C⁻¹)_FR → (C⁻¹)_FR / s ,   (C⁻¹)_RR → (C⁻¹)_RR / s² ,   L_R → L_R / s²
```

by an arbitrary factor. Every observable of the linear model, the two normal
frequencies and every energy participation, is invariant. So `E_C,FR`,
`E_C,RR` and `L_R` are **not identifiable from Route A data**. Two circuits
whose `L_R` differ by 10¹⁶ produce identical observables; that witness is
computed and recorded in
`results/ROUTE-A-SYNTHETIC-*/report.md` §1.

## 2. What is identifiable

The gauge factors cancel in exactly the quantities that matter:

| quantity | invariant? | why |
|---|---|---|
| `E_C,F1F1` | yes | the fluxonium node is fixed by its declared branch; the gauge acts only on the readout node |
| `f_F = √(8 E_C,FF E_L,F)` | yes | fixed by `E_C,FF` and the declared `L_F`, so not independent of the first row |
| `f_R = √(8 E_C,RR E_L,R)` | yes | `E_C,RR ∝ 1/s²` and `E_L,R ∝ s²` |
| `g = 8 E_C,F1R1 n_zpf,R` | yes | `E_C,FR ∝ 1/s` and `n_zpf,R ∝ s` |
| `E_C,F1R1`, `E_C,R1R1`, `L_R` individually | **no** | each scales with a power of the arbitrary `s` |

The corrected Route A target is therefore the triple

```
{ E_C,F1F1 ,  f_R1 ,  g_F1R1 }
```

with the fluxonium's linear inductance `L_F = 103.457 nH` known by
declaration. The coupling that the COUPLING_EXTRACTION gate consumes, `g`, was
always invariant, so **no threshold, rule or reported coupling changes**; what
changes is that the individual matrix entries are no longer claimed as
outputs, and where they are shown at all they are shown in a stated gauge and
labelled as such.

`g`'s invariance is not asserted, it is derived: substituting
`E_C,FR = e²c_FR/2h`, `E_C,RR = e²c_RR/2h`, `E_L,R = φ_r²/(L_R h)`,
`c_FR = k√(L_F L_R)` and `c_RR = b L_R` into `g = 8 E_C,FR n_zpf,R` gives

```
g = 2 e^{3/2} √(L_F) √(φ_r) · k / (h b^{1/4}) ,     b = ω_R² ,  k = |c_FR|/√(L_F L_R)
```

in which `L_R` has cancelled (`models/route_a_inversion.py`,
`coupling_GHz`). A test checks this closed form against the direct definition.

## 3. Counting, and why the inversion is exactly determined

With `L_F` known the circuit has four parameters and one gauge direction, so
**three** physical degrees of freedom. Route A supplies two frequencies and
two participations, but the two participations are not independent: both sum
rules hold,

```
Σ_j p_mj = 1   (per mode, over the lumped inductors)
Σ_m p_mj = 1   (per inductor, over the modes)
```

so `p₋F = 1 − p₊F`. That leaves **three** independent data. The system is
exactly determined, not over-determined: the second participation is a
*check* on the solve, not a datum, and the code checks it rather than assuming
it (`NormalModeData.check_sum_rule`). A violation means the mode pair is
incomplete or a mode outside the pair carries site participation, which is
reported, never absorbed.

## 4. The inversion

With `a = ω_F²`, `b = ω_R²`, `k² = c_FR²/(L_F L_R)` and the exact eigenproblem
of `C⁻¹L⁻¹`:

```
a + b             = ω₊² + ω₋²
(a − b)² + 4k²    = (ω₊² − ω₋²)²
p₊F               = k² / (k² + (ω₊² − a)²)
```

The third line is exact, not a perturbative form: it follows from the
eigenvector ratio `u_R/u_F = (ω² − a)L_R/c_FR`, and it shows again that the
participation depends on the gauge-dependent quantities only through `k`.

Eliminating `b` and `k²` gives a quadratic in `a`. Both roots satisfy the
squared second line, so the algebra alone does not choose between them: the
implementation runs the forward map on each candidate and keeps the one that
reproduces the observed data, raising if none or both do. A silently chosen
root would be a fabricated coupling.

## 5. Demonstration on known synthetic circuits

`scripts/route_a_synthetic_demo.py` writes
`results/ROUTE-A-SYNTHETIC-20260915T231055Z/`. Six circuits with prescribed
invariants (the S1 design point, strong coupling, 5 MHz weak coupling, a
52 MHz near-degenerate pair, a factor-eight detuning, and a case with the
readout below the fluxonium so the inversion cannot assume the mode order),
each observed through five readout gauges spanning eight decades.

- **Gauge invariance:** the observables do not move across the gauges, and the
  recovered triple does not move.
- **Exact recovery:** worst relative error over the whole suite
  **2.3 × 10⁻¹⁰** from noiseless data.
- **Root discrimination:** both roots are recorded in every case; exactly one
  survives the forward-map check.
- **Sum rules:** residual below 10⁻¹² in every case.

**The demonstration reads no Route B quantity.** The inversion module imports
only `math`, `dataclasses` and `typing`; a test asserts that import list and
that no Route B name appears in the module.

## 6. What the solve must deliver, measured

The propagation study perturbs the frequencies and the participation with
Gaussian relative errors and reports the 95th-percentile error on the
recovered invariants. A participation is bounded in [0, 1] and the solver
resolves the smaller of `p` and `1 − p`, so the noise is applied to that
smaller quantity; perturbing `p` multiplicatively when it is near one measures
the noise model rather than the inversion.

At the S1 design point (`p₊F = 2.5 × 10⁻³`):

| σ on each frequency | σ on the participation | 95th pct error on `g` | on `f_R` | on `E_C,FF` |
|---|---|---|---|---|
| 1e-6 | 1e-3 | 9.7e-4 | 2.5e-6 | 7.6e-6 |
| 1e-5 | 1e-2 | 9.7e-3 | 2.5e-5 | 7.6e-5 |
| 1e-4 | 1e-2 | 9.8e-3 | 1.9e-4 | 3.9e-4 |
| 1e-4 | 1e-1 | 9.5e-2 | 2.5e-4 | 7.6e-4 |
| 1e-3 | 1e-2 | 1.3e-2 | 1.9e-3 | 4.1e-3 |

**The error on `g` is set by the participation, essentially one-for-one, and
is almost insensitive to the frequency error.** Loosening the frequency by a
factor of a hundred, from 1e-6 to 1e-4, changes the error on `g` from
9.7 × 10⁻⁴ to 9.8 × 10⁻³ only because the participation was loosened tenfold
in the same rows; at fixed participation the frequency hardly matters. The
same behaviour holds in every other case in the suite.

Two consequences for the execution plan, both about **Route A's own numerical
floor** and neither a change to the agreement rule:

1. Route A must obtain the energy participation to about **1 %** relative for
   its own uncertainty on `g` to be about 1 %. That is a requirement on the
   eigenmode solve and its energy postprocessing, and it is now the quantity
   the Route A mesh ladder must be judged on, alongside the existing 1e-4
   frequency rule.
2. The existing frequency convergence rule is comfortably sufficient for `g`.
   It still matters for `f_R` and `E_C,FF`, where the error tracks it directly.

## 7. Changes this forces elsewhere

- `coupling-definition.md` §3 and §10 now state the invariant target and the
  gauge, and no longer claim the readout-node entries are convention-free.
- `extraction-routes.md` §2.3 states what Route A returns and in which gauge
  any matrix entry is shown.
- `numerical-plan.md` §3 adds the participation accuracy to the Route A
  ladder's convergence evidence.
- Route B is unaffected in its target: it estimates the same invariants. Its
  own identifiability is a separate question about the rational fit, and is
  not addressed here.
- The general `N`-node case has one gauge direction per readout node; the same
  correction applies, and only the invariants are reportable. The closed-form
  inversion implemented here covers the two-node S1 scope, which is the only
  executable scope.
