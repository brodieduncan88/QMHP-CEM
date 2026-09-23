# Route A recovery on synthetic circuits

Synthetic software demonstration of the Route A inversion. Every circuit here is written down with known parameters; no Palace solve, no EM model and no Route B quantity is involved. It demonstrates that the inversion recovers the gauge-invariant triple it claims to recover, and measures how solver error propagates into the coupling. It is not evidence about any candidate.

## 1. Identifiability witness

Every row has the same observables and the same invariant triple; c_FR, c_RR and L_R differ by a factor of 1e+16. The raw readout-node entries are conventions, not measurements.

| gauge s | c_FR (1/F) | c_RR (1/F) | L_R (nH) | f+ (GHz) | f- (GHz) | p+F | g (GHz) |
|---|---|---|---|---|---|---|---|
| 1 | 2.220791e+11 | 7.306265e+11 | 1.000000e+00 | 4.305219536 | 2.748824160 | 0.002544061 | 0.150000000 |
| 0.0001 | 2.220791e+15 | 7.306265e+19 | 1.000000e+08 | 4.305219536 | 2.748824160 | 0.002544061 | 0.150000000 |
| 0.017 | 1.306348e+13 | 2.528119e+15 | 3.460208e+03 | 4.305219536 | 2.748824160 | 0.002544061 | 0.150000000 |
| 53 | 4.190171e+09 | 2.601020e+08 | 3.559986e-04 | 4.305219536 | 2.748824160 | 0.002544061 | 0.150000000 |
| 10000 | 2.220791e+07 | 7.306265e+03 | 1.000000e-08 | 4.305219536 | 2.748824160 | 0.002544061 | 0.150000000 |

## 2. Exact recovery and gauge invariance

| case | f+ (GHz) | f- (GHz) | p+F | worst relative error over 5 gauges |
|---|---|---|---|---|
| s1_design_point | 4.305220 | 2.748824 | 2.544061e-03 | 3.79e-16 |
| strong_coupling | 4.351783 | 2.674497 | 3.657415e-02 | 3.79e-16 |
| weak_coupling | 4.301978 | 2.753894 | 2.848432e-06 | 2.06e-16 |
| near_degenerate | 4.345202 | 4.205794 | 3.135673e-01 | 1.01e-13 |
| far_detuned | 8.000564 | 0.995476 | 1.432491e-04 | 1.58e-15 |
| readout_below_fluxonium | 4.304079 | 2.750649 | 9.983670e-01 | 2.34e-10 |

Every case recovers the known invariants to machine precision, and the observables do not move across eight decades of readout-node normalisation.

## 3. Error propagation into the coupling

Relative error on `g` at the 95th percentile of 400 draws, by the relative error supplied on the frequencies and on the participation.

| case | sigma_f | sigma_p | p+F | g 95th pct | f_R 95th pct | E_C,FF 95th pct | failures |
|---|---|---|---|---|---|---|---|
| s1_design_point | 1e-06 | 1e-03 | 2.54e-03 | 9.68e-04 | 2.46e-06 | 7.58e-06 | 0 |
| s1_design_point | 1e-05 | 1e-02 | 2.54e-03 | 9.72e-03 | 2.46e-05 | 7.58e-05 | 0 |
| s1_design_point | 1e-04 | 1e-02 | 2.54e-03 | 9.83e-03 | 1.87e-04 | 3.90e-04 | 0 |
| s1_design_point | 1e-04 | 1e-01 | 2.54e-03 | 9.45e-02 | 2.46e-04 | 7.58e-04 | 0 |
| s1_design_point | 1e-03 | 1e-02 | 2.54e-03 | 1.27e-02 | 1.87e-03 | 4.09e-03 | 0 |
| strong_coupling | 1e-06 | 1e-03 | 3.66e-02 | 9.44e-04 | 2.17e-05 | 1.09e-04 | 0 |
| strong_coupling | 1e-05 | 1e-02 | 3.66e-02 | 9.49e-03 | 2.17e-04 | 1.09e-03 | 0 |
| strong_coupling | 1e-04 | 1e-02 | 3.66e-02 | 9.59e-03 | 2.93e-04 | 1.11e-03 | 0 |
| strong_coupling | 1e-04 | 1e-01 | 3.66e-02 | 9.24e-02 | 2.17e-03 | 1.08e-02 | 0 |
| strong_coupling | 1e-03 | 1e-02 | 3.66e-02 | 1.23e-02 | 1.85e-03 | 3.73e-03 | 0 |
| weak_coupling | 1e-06 | 1e-03 | 2.85e-06 | 9.69e-04 | 1.88e-06 | 4.12e-06 | 0 |
| weak_coupling | 1e-05 | 1e-02 | 2.85e-06 | 9.74e-03 | 1.88e-05 | 4.12e-05 | 0 |
| weak_coupling | 1e-04 | 1e-02 | 2.85e-06 | 9.85e-03 | 1.89e-04 | 4.12e-04 | 0 |
| weak_coupling | 1e-04 | 1e-01 | 2.85e-06 | 9.47e-02 | 1.88e-04 | 4.12e-04 | 0 |
| weak_coupling | 1e-03 | 1e-02 | 2.85e-06 | 1.27e-02 | 1.88e-03 | 4.11e-03 | 0 |
| near_degenerate | 1e-06 | 1e-03 | 3.14e-01 | 5.74e-04 | 1.89e-05 | 3.91e-05 | 0 |
| near_degenerate | 1e-05 | 1e-02 | 3.14e-01 | 5.74e-03 | 1.90e-04 | 3.91e-04 | 0 |
| near_degenerate | 1e-04 | 1e-02 | 3.14e-01 | 1.04e-02 | 2.44e-04 | 4.69e-04 | 0 |
| near_degenerate | 1e-04 | 1e-01 | 3.14e-01 | 5.62e-02 | 1.90e-03 | 3.89e-03 | 0 |
| near_degenerate | 1e-03 | 1e-02 | 3.14e-01 | 8.55e-02 | 1.49e-03 | 2.97e-03 | 0 |
| far_detuned | 1e-06 | 1e-03 | 1.43e-04 | 9.73e-04 | 1.86e-06 | 1.71e-05 | 0 |
| far_detuned | 1e-05 | 1e-02 | 1.43e-04 | 9.76e-03 | 1.86e-05 | 1.71e-04 | 0 |
| far_detuned | 1e-04 | 1e-02 | 1.43e-04 | 9.75e-03 | 1.87e-04 | 4.05e-04 | 0 |
| far_detuned | 1e-04 | 1e-01 | 1.43e-04 | 9.46e-02 | 1.86e-04 | 1.71e-03 | 0 |
| far_detuned | 1e-03 | 1e-02 | 1.43e-04 | 1.06e-02 | 1.88e-03 | 4.07e-03 | 0 |
| readout_below_fluxonium | 1e-06 | 1e-03 | 9.98e-01 | 9.65e-04 | 2.79e-06 | 4.12e-06 | 0 |
| readout_below_fluxonium | 1e-05 | 1e-02 | 9.98e-01 | 9.70e-03 | 2.79e-05 | 4.12e-05 | 0 |
| readout_below_fluxonium | 1e-04 | 1e-02 | 9.98e-01 | 9.80e-03 | 1.98e-04 | 3.67e-04 | 0 |
| readout_below_fluxonium | 1e-04 | 1e-01 | 9.98e-01 | 9.45e-02 | 2.79e-04 | 4.11e-04 | 0 |
| readout_below_fluxonium | 1e-03 | 1e-02 | 9.98e-01 | 1.31e-02 | 2.05e-03 | 3.74e-03 | 0 |

Noise model: Gaussian relative error on each frequency, and on the smaller of the site participation and its complement, because a participation is bounded in [0, 1] and the solver resolves the smaller energy ratio. Perturbing p multiplicatively when it is near one measures the noise model, not the inversion.

Across the suite the recovered invariants track the known values to 2.3e-10 relative with noiseless data. Under noise the coupling error is set by the participation, not by the frequencies: at the S1 design point the 95th-percentile relative error on g is 0.95 to 1.27 times the relative error supplied on the participation, while a hundredfold loosening of the frequency error changes it little. Route A therefore needs the energy participation to about 1 % to keep its own uncertainty on g near 1 %. This is a statement about Route A's numerical floor. It is not a comparison against the 10 % agreement rule, which is unchanged and applies between the two routes.

## 4. Sum rules

| case | sum over modes of p_F | residual |
|---|---|---|
| s1_design_point | 1.000000000000000 | 2.22e-16 |
| strong_coupling | 1.000000000000000 | 2.22e-16 |
| weak_coupling | 1.000000000000000 | 2.22e-16 |
| near_degenerate | 1.000000000000000 | 1.11e-16 |
| far_detuned | 1.000000000000000 | 0.00e+00 |
| readout_below_fluxonium | 1.000000000000000 | 2.22e-16 |

## Statement

Synthetic software demonstration of the Route A inversion. Every circuit here is written down with known parameters; no Palace solve, no EM model and no Route B quantity is involved. It demonstrates that the inversion recovers the gauge-invariant triple it claims to recover, and measures how solver error propagates into the coupling. It is not evidence about any candidate.
