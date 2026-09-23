#!/usr/bin/env python3
"""SYNTHETIC ONLY. How a participation weight carried by modes far above the band
moves the environment normal-mode quantities identified from in-band F-site data.

Uses the SYNTHETIC reference circuit B of ../three_mode_identifiability.py (same
regime as the real records: p_1F ~ 0.9985, p_2F ~ 7e-4, f ~ 1.5 / 3.9 / 8 GHz).
A weight delta is removed from the in-band participations proportionally and
placed at a single far frequency f_far; the in-band data are then handed to the
F-site identification as if complete (no renormalisation), and the relative
shifts of a = sum p f^2, of the readout normal-mode frequency beta_R and of its
residue ctil_R^2 are recorded. No real record is read.
"""
from __future__ import annotations
import importlib.util, json, math, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("synth", HERE.parent / "three_mode_identifiability.py")
synth = importlib.util.module_from_spec(spec); spec.loader.exec_module(synth)
import numpy as np
from scipy.optimize import brentq

A0, B0, D0, KFR0, KRX = 1.50**2, 3.90**2, 8.0**2, 0.41, 2.0
kfx = brentq(lambda k: synth.modes3(synth.S3(A0, B0, D0, KFR0, k, KRX))[1][2] - 8e-4, 0.0, 6.0)
S = synth.S3(A0, B0, D0, KFR0, kfx, KRX)
f, p, _ = synth.modes3(S)
beta_true, ctil_true, _ = synth.env_normal_modes(S)
ref = synth.f_site_identify(f, p)
out = {"label": "SYNTHETIC", "reference_circuit_B": S.tolist(), "modes_GHz": f.tolist(), "p_F": p.tolist(),
       "exact_identification": {"a": ref["a"], "beta": ref["beta"].tolist(), "ctil2": ref["ctil2"].tolist()}, "rows": []}
for delta in (7.8e-4, 1e-4):
    for f_far in (9.5, 12.9, 20.0, 50.0):
        # remove weight delta from the in-band participations proportionally (they now sum to 1 - delta);
        # the far mode at f_far carries it. Only the in-band data are identified, uncorrected.
        p_in = p * (1 - delta)
        idn = synth.f_site_identify(f, p_in)                      # in-band data only, sum p = 1 - delta
        f_all = np.append(f, f_far); p_all = np.append(p_in, delta)
        full = synth.f_site_identify(f_all, p_all)                # if the far mode were included: exact completeness
        row = {"delta": delta, "f_far_GHz": f_far, "sum_p_in_band": float(p_in.sum()),
               "in_band_only": {"rel_shift_a": (idn["a"] - full["a"]) / full["a"],
                                "rel_shift_beta_R": (idn["beta"][0] - full["beta"][0]) / full["beta"][0],
                                "rel_shift_ctil2_R": (idn["ctil2"][0] - full["ctil2"][0]) / full["ctil2"][0],
                                "rel_shift_f_R": math.sqrt(idn["beta"][0] / full["beta"][0]) - 1.0,
                                "rel_shift_g": math.sqrt(idn["ctil2"][0] / full["ctil2"][0]) * (full["beta"][0] / idn["beta"][0]) ** 0.25 - 1.0},
               "a_with_far_mode_rel_to_reference": (full["a"] - ref["a"]) / ref["a"]}
        out["rows"].append(row)
        print(f"delta={delta:.1e} f_far={f_far:5.1f} GHz | in-band-only vs complete: a {row['in_band_only']['rel_shift_a']:+.2e}  "
              f"beta_R {row['in_band_only']['rel_shift_beta_R']:+.2e}  ctil2_R {row['in_band_only']['rel_shift_ctil2_R']:+.2e}  "
              f"f_R {row['in_band_only']['rel_shift_f_R']:+.2e}  g {row['in_band_only']['rel_shift_g']:+.2e}")
for r in out["rows"]:
    for v in r["in_band_only"].values():
        if not math.isfinite(v): raise RuntimeError("non-finite")
(HERE / "far_mode_background_sensitivity.json").write_text(json.dumps(out, indent=1) + "\n")
