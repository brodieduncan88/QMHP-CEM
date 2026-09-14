# v1.5.8f Master (Final, build 2) — figure regeneration

Environment: pip install -r requirements.lock  (Python 3.12.3)

    python3 build_master_figures.py

regenerates figM1_truncation.png, figM2_ensemble.png,
figM3_t12_crossing.png and figM4_t13.png from the shipped numerical
artifacts only:
  M1 <- truncation-ladder values of qmhp_v158f_readout_replication.py
        (declared in-script with that provenance)
  M2 <- ensemble_20seed.json
  M3 <- t12_realistic_location_runs.json + t12_breakevens.json
        + qmhp_v158e_runs.json (matched-C hazard)
  M4 <- t13_distance_trend_release_hazard.json (release -ln hazard;
        the linear-convention JSON is sensitivity only)
Full re-computation of every underlying number: RUN.md.
