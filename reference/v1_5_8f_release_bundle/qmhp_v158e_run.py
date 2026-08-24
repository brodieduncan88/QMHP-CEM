"""v1.5.8e matched-construction grid. Writes qmhp_v158e_runs.json."""
import json, time, sys
from qmhp_v158e_core import *

ROUNDS = 10
TARGET_FAILS = 250
CAP = {3: 300_000, 5: 600_000, 7: 700_000}
BATCH = {3: 25_000, 5: 20_000, 7: 10_000}

CEIL_GATE = 8.0e-4          # P4 acceptance ceiling, per twirled 2Q gate
REC_GATE = 4.0e-4           # Lin-record-equivalent (6.0e-4/incidence at d=3)

A = BRANCH_A_PU
A_REC = set_two_qubit_anchor(A, REC_GATE)
C_LIT = BRANCH_C_LIT                                   # as published (record anchor)
C_LIT_CEIL = set_two_qubit_anchor(C_LIT, CEIL_GATE)
C_FULL = set_correlated(C_LIT + BRANCH_C_CONTRACT_ADDITIONS, 1.000e-3)
C_FULL_CEIL = set_two_qubit_anchor(C_FULL, CEIL_GATE)
C_FULL_CEIL_LOWCORR = set_correlated(C_FULL_CEIL, 2.000e-4)

# Time-scaled variant: Appendix J.1 marks residual_ZZ and the correlated reserve
# as time/burst dependent, so they are rescaled to C's 13.5 us round. The other
# added rows are marked "fixed" per reset / per gate / per measurement and are
# carried at Branch-A parity. This is the more favourable construction for C.
_TS = T_ROUND_C / T_ROUND_A
_ADD_TS = [(n, a * _TS if n in ("residual_ZZ",) else a, o, c)
           for (n, a, o, c) in BRANCH_C_CONTRACT_ADDITIONS]
C_FULL_TS = set_correlated(C_LIT + _ADD_TS, 1.000e-3 * _TS)
C_FULL_TS_CEIL = set_two_qubit_anchor(C_FULL_TS, CEIL_GATE)

# name, ledger, t_round, pe, pe_mode, cadence, f_located, group, note
CONFIGS = [
    # --- v1.5.8d-convention reference points, re-executed in this implementation
    ("A_ref_Pauli",    A, T_ROUND_A, PE_LOAD, "pauli",   1, 0.0, "reference",
     "Pe as uniform one-shot Pauli; 2Q at P4 ceiling (v1.5.8d S.4)"),
    ("A_ref_leakLRU1", A, T_ROUND_A, PE_LOAD, "leak",    1, 0.0, "reference",
     "Pe as persistent sink leakage, unconditional LRU every round"),
    ("A_ref_leakLRU2", A, T_ROUND_A, PE_LOAD, "leak",    2, 0.0, "reference",
     "Pe as persistent sink leakage, LRU every two rounds"),
    ("C_ref_lit",      C_LIT, T_ROUND_C, None, "none",   1, 0.0, "reference",
     "Branch C exactly as published in v1.5.8d S.6 (6 rows, record 2Q anchor)"),

    # --- matched construction
    ("A_m_twirlAD",    A, T_ROUND_A, PE_LOAD, "twirlAD", 1, 0.0, "matched",
     "Pe as twirled amplitude damping, matched to Branch-C T1 surrogate"),
    ("A_m_free",       A, T_ROUND_A, PE_LOAD, "twirlAD", 1, 1.0, "matched",
     "IDEAL free-location bracket: every Pe event located and removed"),
    ("C_m_full",       C_FULL_CEIL, T_ROUND_C, None, "none", 1, 0.0, "matched",
     "Branch C contract-complete (12 rows), 2Q at same P4 ceiling as A"),

    # --- sensitivity / delta attribution
    ("C_m_full_ts", C_FULL_TS_CEIL, T_ROUND_C, None, "none", 1, 0.0, "matched",
     "C contract-complete with time-dependent rows rescaled to 13.5 us (primary)"),

    ("C_s_litCeil",    C_LIT_CEIL, T_ROUND_C, None, "none", 1, 0.0, "sensitivity",
     "C published rows, 2Q anchor alone moved to ceiling"),
    ("C_s_fullRecord", C_FULL, T_ROUND_C, None, "none", 1, 0.0, "sensitivity",
     "C contract-complete but 2Q kept at record anchor"),
    ("C_s_fullLowCorr", C_FULL_CEIL_LOWCORR, T_ROUND_C, None, "none", 1, 0.0,
     "sensitivity", "C contract-complete, correlated reserve kept at 2.0e-4"),
    ("A_s_recTwirl",   A_REC, T_ROUND_A, PE_LOAD, "twirlAD", 1, 0.0, "sensitivity",
     "Branch A with 2Q moved to the record anchor"),
    ("A_s_leakLRU1_rec", A_REC, T_ROUND_A, PE_LOAD, "leak", 1, 0.0, "sensitivity",
     "Branch A leakage LRU1 with 2Q at record anchor"),
]

SWEEP_F = [0.25, 0.50, 0.75, 0.90]


def run(name, rows, t_round, pe, mode, cad, f, d, seed):
    code = RotatedCode(d)
    mapped = per_opportunity(rows, d)
    px, pz, pm = ledger_marginals(mapped, d)
    n = k = 0
    cap, batch = CAP[d], BATCH[d]
    while n < cap and k < TARGET_FAILS:
        nn, kk = run_config(code, mapped, ROUNDS, batch, seed + n,
                            pe=pe, pe_mode=mode, lru_cadence=cad,
                            location_efficiency=f, batch=batch)
        n += nn; k += kk
    s = summarise(n, k, t_round, ROUNDS)
    s.update(name=name, d=d, marg_X=px, marg_Z=pz, marg_meas=pm,
             ledger_total=sum(r[1] for r in rows), f_located=f)
    return s


if __name__ == "__main__":
    import os
    BUDGET = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
    out = json.load(open("qmhp_v158e_runs.json")) if os.path.exists(
        "qmhp_v158e_runs.json") else []
    done = {(r["name"], r["d"], round(r.get("f_located", 0.0), 3)) for r in out}
    t0 = time.time()
    for i, (name, rows, t_r, pe, mode, cad, f, grp, note) in enumerate(CONFIGS):
        for d in (3, 5, 7):
            if (name, d, round(f, 3)) in done or time.time() - t0 > BUDGET:
                continue
            s = run(name, rows, t_r, pe, mode, cad, f, d, 100000 + 977 * i + 31 * d)
            s.update(group=grp, note=note)
            out.append(s)
            print(f"[{time.time()-t0:6.1f}s] {name:<18} d={d} "
                  f"n={s['shots']:>8} k={s['failures']:>5} "
                  f"pL={s['pL_round']:.4e} lam={s['lambda_L']:.4f}/ms "
                  f"P1ms={s['P_fail_1ms']:.4f}", flush=True)
        json.dump(out, open("qmhp_v158e_runs.json", "w"), indent=1)

    for f in SWEEP_F:
        for d in (3, 5):
            if ("A_sweep_f", d, round(f, 3)) in done or time.time() - t0 > BUDGET:
                continue
            s = run("A_sweep_f", A, T_ROUND_A, PE_LOAD, "twirlAD", 1, f, d,
                    500000 + int(f * 1000) + d)
            s.update(group="sweep", note=f"location efficiency f={f}")
            out.append(s)
            print(f"[{time.time()-t0:6.1f}s] A_sweep f={f:.2f} d={d} "
                  f"pL={s['pL_round']:.4e}", flush=True)
        json.dump(out, open("qmhp_v158e_runs.json", "w"), indent=1)

    json.dump(out, open("qmhp_v158e_runs.json", "w"), indent=1)
    print(f"done in {time.time()-t0:.1f}s, {len(out)} runs")

