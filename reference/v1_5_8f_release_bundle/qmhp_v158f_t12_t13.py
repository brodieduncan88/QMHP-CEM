"""v1.5.8f AMD-C studies.

T.13': distance-trend double ratio, parametric bootstrap on the released
       S1 run record (RECOMPUTATION-FROM-RUN-RECORD, exploratory).
T.12': realistic-location study with the cost side charged
       (f, p_induced, t_check), executed in the v1.5.8e clean-room
       implementation, matched arms, Section-9 SCALING rule applied.

Seeds declared inline. Comparator: C_m_full_ts printed S1 values,
independently re-executed bit-exact in this session.
"""
import json, time
import numpy as np
from qmhp_v158e_core import (BRANCH_A_PU, PE_LOAD, T_ROUND_A, T_ROUND_C,
                             RotatedCode, per_opportunity, run_config,
                             summarise, wilson)
from qmhp_v158e_run import CONFIGS, run, TARGET_FAILS, CAP, BATCH

# ---------------------------------------------------------------- T.13'
# S1 printed record (re-executed exactly this session at declared seeds):
S1 = {  # (arm, d): (shots, fails, t_round)
    ("A", 3): (25_000, 1950, 20.0),   # A_m_twirlAD
    ("A", 5): (20_000,  364, 20.0),
    ("A", 7): (60_000,  286, 20.0),
    ("C", 3): (25_000, 1414, 13.5),   # C_m_full_ts (primary matched arm)
    ("C", 5): (20_000,  267, 13.5),
    ("C", 7): (100_000, 280, 13.5),
}
ROUNDS = 10

def lam(k, n, t, convention="release"):
    """Hazard per ms. convention='release': -ln(1-p_round)/t (the release
    definition, qmhp_v158e_core); 'linear': small-p form p_round/t
    (sensitivity only; effect on the double ratio <= 0.002)."""
    import numpy as _np
    p_shot = k / n
    p_round = 1.0 - (1.0 - p_shot) ** (1.0 / ROUNDS)
    if convention == "release":
        return -_np.log(1.0 - p_round) / t * 1000.0
    return p_round / t * 1000.0

def t13(reps=20_000, seed=13, convention="release"):
    rng = np.random.default_rng(seed)
    def draw(arm, d):
        n, k, t = S1[(arm, d)]
        kk = rng.binomial(n, k / n, reps)
        return lam(kk, n, t, convention)
    out = {}
    hr = {d: draw("A", d) / draw("C", d) for d in (3, 5, 7)}
    for a, b in ((7, 3), (5, 3), (7, 5)):
        R = hr[a] / hr[b]
        n7, k7, t7 = S1[("A", a)]
        L = lambda arm, dd: lam(S1[(arm, dd)][1], S1[(arm, dd)][0],
                                S1[(arm, dd)][2], convention)
        central = (L("A", a) / L("C", a)) / (L("A", b) / L("C", b))
        out[f"R{a}_over_R{b}"] = dict(
            central=float(central),
            lo=float(np.quantile(R, 0.025)),
            hi=float(np.quantile(R, 0.975)),
            P_gt_1=float((R > 1).mean()),
            reps=reps, seed=seed,
            method="parametric binomial bootstrap on released S1 counts",
            hazard_convention=convention,
            status="RECOMPUTATION-FROM-RUN-RECORD / EXPLORATORY",
        )
    return out

# ---------------------------------------------------------------- T.12'
# Section 9 SCALING rule (load-bearing box): rescale time-linear,
# time/burst(-flag,-control) dependent and dephasing-envelope rows by the
# round-duration ratio; carry fixed rows at parity. Pe (|2>->|1> decay
# flux) is time-linear by construction.
RESCALED = {"pure_dephasing", "missed_erasures", "QP_bypass",
            "thermal_unflagged", "residual_ZZ", "correlated_reserve"}

def a_realistic(f, p_ind, t_chk, convention="scaled"):
    r = (T_ROUND_A + t_chk) / T_ROUND_A if convention == "scaled" else 1.0
    rows = [(n, a * (r if n in RESCALED else 1.0), o, c)
            for (n, a, o, c) in BRANCH_A_PU]
    if p_ind > 0:
        rows = rows + [("check_induced", p_ind, "data", "depol1")]
    pe = PE_LOAD * r
    t_round = T_ROUND_A + t_chk
    return rows, pe, t_round

def seed_of(f, p, t, d, conv):
    return (700_000 + int(round(f * 100)) * 97 + int(round(p * 1e6)) * 3
            + int(round(t * 10)) * 11 + d * 7 + (0 if conv == "scaled" else 1))

def run_t12(grid, tag, conv="scaled"):
    out = []
    t0 = time.time()
    for (f, p, t, d) in grid:
        rows, pe, t_r = a_realistic(f, p, t, conv)
        s = run(f"A_rl_{tag}", rows, t_r, pe, "twirlAD", 1, f, d,
                seed_of(f, p, t, d, conv))
        s.update(f=f, p_induced=p, t_check=t, convention=conv)
        out.append(s)
        print(f"[{time.time()-t0:6.1f}s] f={f:.2f} p_ind={p:.1e} "
              f"t_chk={t:.1f} d={d} {conv:>6}: n={s['shots']:>7} "
              f"k={s['failures']:>4} lam={s['lambda_L']:.4f}/ms", flush=True)
    return out

if __name__ == "__main__":
    res13 = t13(convention="release")
    json.dump(res13, open("t13_distance_trend_release_hazard.json", "w"),
              indent=1)
    json.dump(t13(convention="linear"),
              open("t13_distance_trend_linear_sensitivity.json", "w"),
              indent=1)
    for k, v in res13.items():
        print(f"T.13' {k}: {v['central']:.3f} [{v['lo']:.3f},{v['hi']:.3f}] "
              f"P(>1)={v['P_gt_1']:.3f}")

    F  = [0.60, 0.90, 1.00]
    P  = [0.0, 5e-4, 1e-3, 2e-3, 4e-3, 8e-3, 1.6e-2]
    T  = [0.0, 2.0]
    grid3 = [(f, p, t, 3) for f in F for p in P for t in T]
    grid5 = [(f, p, t, 5) for f in (0.90, 1.00) for p in P for t in T]
    grid7 = [(1.00, p, 2.0, 7) for p in (0.0, 4e-3)]
    runs = run_t12(grid3 + grid5 + grid7, "scan", "scaled")
    # fixed-round bracket at the An-relevant slice
    runs += run_t12([(0.90, p, 2.0, 3) for p in P] +
                    [(0.90, p, 2.0, 5) for p in P], "scan", "fixed")
    json.dump(runs, open("t12_realistic_location_runs.json", "w"), indent=1)
    print(f"T.12' total runs: {len(runs)}")
