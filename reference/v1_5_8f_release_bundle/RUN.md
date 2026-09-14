# QMHP-CoPro v1.5.8f AMD-C — reproduction instructions

Environment: Python 3.12, `pip install -r requirements.lock`
(numpy 2.4.4, PyMatching 2.4.0, stim 1.16.0 — must match exactly for
bit-exact reproduction; other versions give statistically equivalent
results only).

1. Released grid (verification register, AMD-C §2):
       python3 qmhp_v158e_run.py 900
   Writes qmhp_v158e_runs.json. Compare against expected_outputs.json
   → bit_exact_reproduction and headline_ratios. Seeds are declared in
   qmhp_v158e_run.py (100000 + 977*i + 31*d). ~4 min single core.

2. T.12' realistic-location study and T.13' distance trend (AMD-C §3–4):
       python3 qmhp_v158f_t12_t13.py
   Writes t12_realistic_location_runs.json and t13_distance_trend.json.
   Seeds declared inline (T.12': 700000-family; T.13': seed 13).
   ~6 min single core.

3. Break-evens and figures: values in t12_breakevens.json and the three
   figF*.png files; regeneration scripts embedded in AMD-C provenance
   (build_amd.py in the working session). Compare against
   expected_outputs.json → t12_breakevens_scaled_tchk2us and t13.

Every artifact digest is listed in qmhp_v158f_amdc_manifest.json.
The reconstructed qmhp_v158e_*.py sources are functionally validated by
the bit-exact reproduction but are not byte-identical to the originals
(whitespace under-determined by the printed listing), so their digests
differ from the release's T.11 values by construction.

Base artifacts (E17 designation):
OPERATIVE: QMHP-CoPro v1.5.8e, 117 pages,
SHA-256 d334cda822c07c212be1fac850a34debef5ea66ee45899e56b44e19154f86c6c
PROVENANCE ONLY: 109-page render,
SHA-256 83aeb3a2d8ebcb8f627989557350d9c172ad5bc20c3edc561b8a5e091cc4b658

T.13' ships as two convention-named artifacts (primary first):
t13_distance_trend_release_hazard.json  (-ln(1-p_round)/t, the release
definition; source of Figure 4) and
t13_distance_trend_linear_sensitivity.json (small-p form; sensitivity,
double-ratio effect <= 0.002). Master figures regenerate via
RUN_MASTER.md / build_master_figures.py.
