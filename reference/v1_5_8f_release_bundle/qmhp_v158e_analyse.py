"""v1.5.8e analysis: tables, hazard ratios, break-even location efficiency."""
import json, csv, hashlib, os
import numpy as np
from qmhp_v158e_core import (hazard, per_round, p_fail_time, hazard_ratio_ci,
                             T_ROUND_A, T_ROUND_C)

R = json.load(open("qmhp_v158e_runs.json"))
K = {(r["name"], r["d"], round(r.get("f_located", 0.0), 3)): r for r in R}


def g(n, d, f=None):
    if f is not None:
        return K[(n, d, round(f, 3))]
    m = [r for r in R if r["name"] == n and r["d"] == d]
    if not m:
        raise KeyError((n, d))
    return m[0]


def fmt(x, p=3):
    return f"{x:.{p}e}"


# ---------------------------------------------------------------- main table
MAIN = [
    ("A_ref_Pauli",    "A", "REFERENCE  A, Pe as uniform Pauli (v1.5.8d S.4 convention)"),
    ("A_ref_leakLRU1", "A", "REFERENCE  A, Pe as sink leakage, LRU every round"),
    ("A_ref_leakLRU2", "A", "REFERENCE  A, Pe as sink leakage, LRU every 2 rounds"),
    ("C_ref_lit",      "C", "REFERENCE  C exactly as published (6 rows, record 2Q)"),
    ("A_m_twirlAD",    "A", "MATCHED    A, Pe as twirled AD (same surrogate as C T1)"),
    ("A_m_free",       "A", "MATCHED    A, ideal free-location bracket (all Pe located)"),
    ("C_m_full_ts",    "C", "MATCHED    C contract-complete, time-dep rows rescaled to 13.5us (PRIMARY)"),
    ("C_m_full",       "C", "MATCHED    C contract-complete, added rows at Branch-A parity"),
    ("C_s_litCeil",    "C", "SENS       C published rows, 2Q anchor -> ceiling only"),
    ("C_s_fullRecord", "C", "SENS       C contract-complete, 2Q kept at record"),
    ("C_s_fullLowCorr", "C", "SENS      C contract-complete, corr reserve kept 2.0e-4"),
    ("A_s_recTwirl",   "A", "SENS       A twirled AD, 2Q -> record anchor"),
    ("A_s_leakLRU1_rec", "A", "SENS     A leakage LRU1, 2Q -> record anchor"),
]

rows_out = []
print("=" * 118)
print("TABLE 1  Row-wise QEC-MAP, matched construction (10 rounds, MWPM, "
      "failure = either CSS axis)")
print("=" * 118)
print(f"{'config':<19}{'d':>2} {'shots':>8}{'fail':>6}  {'pL/round':>10} "
      f"{'[95% Wilson]':>23}  {'t_r':>5} {'lam/ms':>8} {'P_fail(1ms)':>22}")
for name, br, note in MAIN:
    for d in (3, 5, 7):
        if not [r for r in R if r["name"] == name and r["d"] == d]:
            continue
        r = g(name, d)
        print(f"{name:<19}{d:>2} {r['shots']:>8}{r['failures']:>6}  "
              f"{fmt(r['pL_round']):>10} "
              f"[{fmt(r['pL_round_lo'],2)},{fmt(r['pL_round_hi'],2)}]  "
              f"{r['t_round_us']:>5.1f} {r['lambda_L']:>8.4f} "
              f"{r['P_fail_1ms']:.4f} [{r['P_fail_1ms_lo']:.4f},{r['P_fail_1ms_hi']:.4f}]")
        rows_out.append(dict(config=name, branch=br, d=d, **{
            k: r[k] for k in ("shots", "failures", "pL_round", "pL_round_lo",
                              "pL_round_hi", "t_round_us", "lambda_L",
                              "lambda_L_lo", "lambda_L_hi", "P_fail_1ms",
                              "P_fail_1ms_lo", "P_fail_1ms_hi", "marg_X",
                              "marg_Z", "marg_meas", "ledger_total")},
            note=note))
    print("-" * 118)

# ------------------------------------------------- delta attribution for C
print("\n" + "=" * 118)
print("TABLE 2  Branch-C delta attribution: what each construction fix costs C")
print("=" * 118)
print(f"{'step':<52}{'d=3 pL':>12}{'d=5 pL':>12}{'d=7 pL':>12}{'x vs published':>16}")
base = {d: g("C_ref_lit", d)["pL_round"] for d in (3, 5, 7)}
for tag, nm in (("C as published in v1.5.8d S.6 (6 rows, record 2Q)", "C_ref_lit"),
                ("+ 2Q anchor moved to the P4 ceiling (alone)", "C_s_litCeil"),
                ("+ 6 contract rows, corr reserve kept at 2.0e-4", "C_s_fullLowCorr"),
                ("+ contract rows, record 2Q, corr at parity 1.0e-3", "C_s_fullRecord"),
                ("+ contract rows at A parity, ceiling 2Q", "C_m_full"),
                ("= MATCHED PRIMARY: time-dep rows rescaled to 13.5 us", "C_m_full_ts")):
    v = {d: g(nm, d)["pL_round"] for d in (3, 5, 7)}
    print(f"{tag:<52}{fmt(v[3]):>12}{fmt(v[5]):>12}{fmt(v[7]):>12}"
          f"{v[3]/base[3]:>13.2f}x")

print("\n" + "=" * 118)
print("TABLE 3  Branch-A delta attribution")
print("=" * 118)
print(f"{'step':<52}{'d=3 pL':>12}{'d=5 pL':>12}{'d=7 pL':>12}")
for tag, nm in (("A, Pe as uniform Pauli (v1.5.8d convention)", "A_ref_Pauli"),
                ("A, Pe as twirled AD (matched to C decay class)", "A_m_twirlAD"),
                ("A, twirled AD + 2Q at record anchor", "A_s_recTwirl"),
                ("A, ideal free-location bracket", "A_m_free")):
    v = {d: g(nm, d)["pL_round"] for d in (3, 5, 7)}
    print(f"{tag:<52}{fmt(v[3]):>12}{fmt(v[5]):>12}{fmt(v[7]):>12}")

# ----------------------------------------------------- equal wall clock A/C
print("\n" + "=" * 118)
print("TABLE 4  Equal-wall-clock hazard ratio lambda_A / lambda_C "
      "(>1 favours C, <1 favours A); 95% parametric bootstrap")
print("=" * 118)
print(f"{'Branch-A variant':<24}{'vs Branch-C':<18}{'d':>2}"
      f"{'lam_A':>9}{'lam_C':>9}{'ratio [95% CI]':>30}   verdict")
comp = []
for an in ("A_ref_Pauli", "A_m_twirlAD", "A_m_free", "A_ref_leakLRU1"):
    for cn in ("C_ref_lit", "C_m_full_ts"):
        for d in (3, 5, 7):
            a, c = g(an, d), g(cn, d)
            m, lo, hi = hazard_ratio_ci(a["shots"], a["failures"], T_ROUND_A,
                                        c["shots"], c["failures"], T_ROUND_C)
            if lo > 1:
                v = "C better (95%)"
            elif hi < 1:
                v = "A better (95%)"
            else:
                v = "not separated"
            print(f"{an:<24}{cn:<18}{d:>2}{a['lambda_L']:>9.4f}"
                  f"{c['lambda_L']:>9.4f}{f'{m:.2f} [{lo:.2f},{hi:.2f}]':>30}   {v}")
            comp.append(dict(A=an, C=cn, d=d, lam_A=a["lambda_L"],
                             lam_C=c["lambda_L"], ratio=m, ratio_lo=lo,
                             ratio_hi=hi, verdict=v))
        print("-" * 118)

# ------------------------------------------- break-even location efficiency
print("\n" + "=" * 118)
print("TABLE 5  Erasure-location efficiency sweep and break-even against Branch C")
print("=" * 118)
sweep = {}
for d in (3, 5):
    pts = [(0.0, g("A_m_twirlAD", d)["pL_round"])]
    for f in (0.25, 0.5, 0.75, 0.9):
        pts.append((f, g("A_sweep_f", d, f)["pL_round"]))
    pts.append((1.0, g("A_m_free", d)["pL_round"]))
    sweep[d] = pts
    print(f"\n  d={d}   f (fraction of Pe located and removed) -> pL/round, "
          f"lambda_L (1/ms), P_fail(1 ms)")
    for f, p in pts:
        lam = hazard(p, T_ROUND_A)
        print(f"     f={f:<5.2f}  pL={fmt(p)}   lam={lam:7.4f}   "
              f"P1ms={p_fail_time(lam):.4f}")

    for cn in ("C_ref_lit", "C_m_full_ts"):
        lam_c = g(cn, d)["lambda_L"]
        fs = np.array([p[0] for p in pts])
        lams = np.array([hazard(p[1], T_ROUND_A) for p in pts])
        if lams.min() > lam_c:
            print(f"     break-even vs {cn}: NOT REACHED even at f=1.0")
        elif lams.max() < lam_c:
            print(f"     break-even vs {cn}: already beaten at f=0")
        else:
            o = np.argsort(lams)
            fstar = float(np.interp(lam_c, lams[o], fs[o]))
            print(f"     break-even vs {cn} (lam_C={lam_c:.4f}): "
                  f"f* = {fstar:.3f}  -> Branch A needs >= {fstar*100:.1f}% "
                  f"effective erasure location to win at equal wall clock")
            sweep[f"fstar_{d}_{cn}"] = fstar

# ------------------------------------------------- Branch-C round sensitivity
print("\n" + "=" * 118)
print("TABLE 6  Branch-C round-duration sensitivity (12 / 13.5 / 15 us) vs "
      "matched Branch A at d=3,5,7")
print("=" * 118)
for d in (3, 5, 7):
    c = g("C_m_full_ts", d)
    line = f"  d={d}  C pL={fmt(c['pL_round'])} -> "
    for t in (12.0, 13.5, 15.0):
        line += f"lam({t:.1f}us)={hazard(c['pL_round'], t):.4f}  "
    a = g("A_m_free", d)
    print(line + (f"| A_free lam={a['lambda_L']:.4f}" if a else ""))

# ------------------------------------------------------------------ outputs
with open("qmhp_v158e_decoder_summary.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
    w.writeheader(); w.writerows(rows_out)

with open("qmhp_v158e_hazard_ratios.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(comp[0].keys()))
    w.writeheader(); w.writerows(comp)

with open("qmhp_v158e_location_sweep.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["d", "f_located", "pL_round", "lambda_L", "P_fail_1ms"])
    for d in (3, 5):
        for f, p in sweep[d]:
            lam = hazard(p, T_ROUND_A)
            w.writerow([d, f, p, lam, p_fail_time(lam)])

json.dump({"sweep": {str(k): v for k, v in sweep.items()},
           "hazard_ratios": comp}, open("qmhp_v158e_summary.json", "w"), indent=1)
print("\nwrote qmhp_v158e_decoder_summary.csv, _hazard_ratios.csv, "
      "_location_sweep.csv, _summary.json")

