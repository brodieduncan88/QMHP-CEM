"""AMD-C readout/collision-screen replication (third independent implementation).

Nominal Eq(7) pulls, perturbative and exact dressed logical-blind roots with
truncation ladder, physical pulls/sink line/Purcell weight, and the 400-device
sigma=2% (EJ,EC,EL) ensemble at the release seed 20260725 plus an independent
seed. Static: [-8pi,8pi], 3201-point second-difference grid. Dressed:
H = diag(w_i) + wr a^dag a + g n (a+a^dag), complex-Hermitian, adiabatic
labels by max bare overlap. g = 150 MHz.
Run: python3 qmhp_v158f_readout_replication.py   (~40 s)
"""
import numpy as np, numpy.linalg as la, json
from scipy.linalg import eigh_tridiagonal
from scipy.optimize import brentq

EC0, EJ0, EL0, g = 0.60, 5.72, 1.58, 0.150

def static(EC, EJ, EL, nlev=10, N=3201):
    x = np.linspace(-8*np.pi, 8*np.pi, N); h = x[1]-x[0]
    w, v = eigh_tridiagonal(4*EC*2/h**2 + 0.5*EL*x**2 - EJ*np.cos(x-np.pi),
                            np.full(N-1, -4*EC/h**2),
                            select='i', select_range=(0, nlev-1))
    dv = np.gradient(v, h, axis=0)
    c = np.array([[np.sum(v[:,i]*dv[:,j]) for j in range(nlev)]
                  for i in range(nlev)])
    return w - w[0], -1j*c

def pulls(wr, w, nm, NQ=10, NPH=12):
    a_ph = np.diag(np.sqrt(np.arange(1, NPH)), 1); x_ph = a_ph + a_ph.T
    dim = NQ*NPH; H = np.zeros((dim, dim), complex)
    for i in range(NQ):
        for ph in range(NPH): H[i*NPH+ph, i*NPH+ph] = w[i] + wr*ph
    for i in range(NQ):
        for j in range(NQ):
            if abs(nm[i, j]) < 1e-14: continue
            H[i*NPH:(i+1)*NPH, j*NPH:(j+1)*NPH] += g*nm[i, j]*x_ph
    ev, vec = la.eigh(H); ov = np.abs(vec)**2
    E = {(i, ph): (ev[np.argmax(ov[i*NPH+ph, :])], np.argmax(ov[i*NPH+ph, :]))
         for i in (0, 1, 2) for ph in (0, 1)}
    return np.array([E[(i,1)][0]-E[(i,0)][0]-wr for i in range(3)])*1e3, E, ev, vec

def null_root(w, nm, NQ=10, NPH=12, lo=4.05, hi=4.55):
    return brentq(lambda wr: (lambda p: p[0]-p[2])(pulls(wr, w, nm, NQ, NPH)[0]),
                  lo, hi, xtol=1e-10)

if __name__ == "__main__":
    out = {}
    for (nq, nph) in [(10, 12), (12, 18), (14, 25)]:
        w, nm = static(EC0, EJ0, EL0, nlev=nq)
        r = null_root(w, nm, nq, nph, 4.20, 4.40)
        out[f"root_Nq{nq}_Nph{nph}"] = r
        print(f"Nq={nq} Nph={nph}: dressed null {r:.9f} GHz")
    w, nm = static(EC0, EJ0, EL0)
    r = out["root_Nq10_Nph12"]
    p, E, ev, vec = pulls(r, w, nm)
    NPH = 12
    a_full = np.kron(np.eye(10), np.diag(np.sqrt(np.arange(1, NPH)), 1))
    M = abs(vec[:, E[(1,0)][1]].conj() @ a_full @ vec[:, E[(2,0)][1]])
    out.update(pull_logical_MHz=p[0], pull_sink_MHz=p[1],
               sink_line_GHz=r+p[1]/1e3, purcell_weight=M*M,
               dressed_f12_GHz=ev[E[(2,0)][1]]-ev[E[(1,0)][1]])
    print(f"pulls {p[0]:+.6f}/{p[1]:+.6f} MHz | sink line {r+p[1]/1e3:.6f} "
          f"| Purcell {M*M:.8f} | f12 {out['dressed_f12_GHz']:.4f}")
    for seed, tag in [(20260725, "release_seed"), (77, "independent_seed")]:
        rng = np.random.default_rng(seed)
        draws = rng.normal(1.0, 0.02, (400, 3))          # (EJ, EC, EL)
        roots, w24 = [], []
        for f in draws:
            wk, nk = static(EC0*f[1], EJ0*f[0], EL0*f[2])
            roots.append(null_root(wk, nk)); w24.append(wk[4]-wk[2])
        roots, w24 = np.array(roots), np.array(w24)
        rej = int(np.sum(np.abs(w24-roots)*1e3 < 13.0))
        out[tag] = dict(reject=rej, p5=float(np.percentile(roots, 5)),
                        median=float(np.percentile(roots, 50)),
                        p95=float(np.percentile(roots, 95)))
        print(f"[{tag} {seed}] sub-13MHz {rej}/400 | p5/med/p95 "
              f"{out[tag]['p5']:.6f}/{out[tag]['median']:.5f}/{out[tag]['p95']:.6f}")
    json.dump(out, open("readout_replication.json", "w"), indent=1)
