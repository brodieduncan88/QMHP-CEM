"""
QMHP-CoPro v1.5.8e - matched-construction row-wise QEC-MAP rerun.

Purpose
-------
v1.5.8d executed the first row-wise phenomenological QEC-MAP and reported an
adverse Branch-A screen against a Branch-C literature/QEC prior. That screen
contained four one-directional construction asymmetries:

  (1) Branch A charged at its P4 acceptance CEILING (8.0e-4/gate) while Branch C
      used a published RECORD (Lin 99.94% -> 6.0e-4/incidence).
  (2) Branch A's located load Pe charged as a UNIFORM PAULI while Branch C's T1
      (physically the same class of event: a decay) charged as TWIRLED AMPLITUDE
      DAMPING. Uniform Pauli puts ~1.8x more weight on each CSS axis.
  (3) Branch C's ledger contained 7 rows and omitted ~1.95e-3/round of
      mechanism classes that Sections 2.3 / 8.3 require it to close
      (leakage, reset back-action, readout-induced, nonadiabatic, residuals),
      plus a 5x unexplained cut to the correlated-event reserve.
  (4) No free-location bracket was run, so Branch A was screened with its
      distinguishing feature switched off.

This module re-executes the map with those asymmetries removed and adds the
missing bracket plus a location-efficiency sweep.

Status: QEC-MAP-PHENO (row-wise phenomenological, MWPM). NOT a hardware
forecast and NOT full circuit-level gate propagation.
"""

from __future__ import annotations

import numpy as np
import pymatching

# ----------------------------------------------------------------------------
# 1. Rotated surface-code geometry
# ----------------------------------------------------------------------------


class RotatedCode:
    """Rotated surface code, distance d.

    Data qubits on a d x d grid at integer (row, col).
    Plaquette (r, c) has centre (r+0.5, c+0.5) and touches
    (r,c), (r,c+1), (r+1,c), (r+1,c+1) intersected with the grid.

    Type rule: X if (r+c) even else Z.
    Weight-2 plaquettes are kept only on the boundary matching their type:
      - X-type weight-2 on the LEFT/RIGHT boundaries (c == -1 or c == d-1)
      - Z-type weight-2 on the TOP/BOTTOM boundaries (r == -1 or r == d-1)
    This makes Z_L = column 0 and X_L = row 0 valid logical operators.
    """

    def __init__(self, d: int):
        assert d % 2 == 1 and d >= 3
        self.d = d
        self.n_data = d * d
        self.qidx = {(r, c): r * d + c for r in range(d) for c in range(d)}

        x_stabs, z_stabs = [], []
        for r in range(-1, d):
            for c in range(-1, d):
                sup = [
                    (r + dr, c + dc)
                    for dr in (0, 1)
                    for dc in (0, 1)
                    if 0 <= r + dr < d and 0 <= c + dc < d
                ]
                if len(sup) == 4:
                    keep = True
                elif len(sup) == 2:
                    is_x = (r + c) % 2 == 0
                    on_lr = c in (-1, d - 1)
                    on_tb = r in (-1, d - 1)
                    keep = (is_x and on_lr) or ((not is_x) and on_tb)
                else:
                    keep = False
                if not keep:
                    continue
                idxs = sorted(self.qidx[q] for q in sup)
                (x_stabs if (r + c) % 2 == 0 else z_stabs).append(idxs)

        self.x_stabs = x_stabs
        self.z_stabs = z_stabs
        self.n_x = len(x_stabs)
        self.n_z = len(z_stabs)

        # logical supports
        self.logZ = np.array([self.qidx[(r, 0)] for r in range(d)])  # column 0
        self.logX = np.array([self.qidx[(0, c)] for c in range(d)])  # row 0

        # parity-check matrices (n_stab x n_data), uint8
        self.HZ = self._to_H(z_stabs)   # detects X errors  -> memory-Z
        self.HX = self._to_H(x_stabs)   # detects Z errors  -> memory-X

        self._validate()

        # nearest-neighbour data pairs (for the correlated-event reserve)
        pairs = []
        for r in range(d):
            for c in range(d):
                if c + 1 < d:
                    pairs.append((self.qidx[(r, c)], self.qidx[(r, c + 1)]))
                if r + 1 < d:
                    pairs.append((self.qidx[(r, c)], self.qidx[(r + 1, c)]))
        self.pairs = np.array(pairs)

        # pair colour classes (no qubit repeats within a class) for fast sampling
        self.pair_classes = []
        for horiz in (True, False):
            for par in (0, 1):
                cls = []
                for r in range(d):
                    for c in range(d):
                        if horiz and c + 1 < d and c % 2 == par:
                            cls.append((self.qidx[(r, c)], self.qidx[(r, c + 1)]))
                        if (not horiz) and r + 1 < d and r % 2 == par:
                            cls.append((self.qidx[(r, c)], self.qidx[(r + 1, c)]))
                if cls:
                    a = np.array(cls)
                    assert len(set(a.ravel().tolist())) == a.size
                    self.pair_classes.append(a)
        assert sum(len(a) for a in self.pair_classes) == len(self.pairs)

        # data-check incidences = 4d(d-1) CNOT pair locations per round.
        # deg(q) = number of stabilisers touching q; sum(deg) = 4d(d-1).
        self.n_incidences = 4 * d * (d - 1)

        # per-data-qubit adjacency lists into stabiliser index space
        self.q_to_z = [np.where(self.HZ[:, q])[0] for q in range(self.n_data)]
        self.q_to_x = [np.where(self.HX[:, q])[0] for q in range(self.n_data)]
        self.deg = np.array([len(self.q_to_z[q]) + len(self.q_to_x[q])
                             for q in range(self.n_data)])
        assert self.deg.sum() == self.n_incidences, (self.deg.sum(), self.n_incidences)
        # slot k holds every qubit with deg > k -> exact per-incidence sampling
        self.inc_slots = [np.where(self.deg > k)[0] for k in range(int(self.deg.max()))]
        self.mean_deg = self.deg.mean()

    def _to_H(self, stabs):
        H = np.zeros((len(stabs), self.n_data), dtype=np.uint8)
        for i, s in enumerate(stabs):
            H[i, s] = 1
        return H

    def _validate(self):
        d = self.d
        assert self.n_x + self.n_z == d * d - 1, (self.n_x, self.n_z, d * d - 1)
        assert self.n_x == self.n_z, (self.n_x, self.n_z)
        # X and Z stabilisers must overlap in an even number of qubits
        ov = (self.HX @ self.HZ.T) % 2
        assert not ov.any(), "stabiliser commutation failure"
        # logical operators must commute with the opposite-type stabilisers
        vZ = np.zeros(self.n_data, dtype=np.uint8); vZ[self.logZ] = 1
        vX = np.zeros(self.n_data, dtype=np.uint8); vX[self.logX] = 1
        assert not ((self.HX @ vZ) % 2).any(), "Z_L does not commute with X stabs"
        assert not ((self.HZ @ vX) % 2).any(), "X_L does not commute with Z stabs"
        # each data qubit touches at most 2 stabilisers of each type
        assert self.HZ.sum(0).max() <= 2 and self.HX.sum(0).max() <= 2


# ----------------------------------------------------------------------------
# 2. Ledgers
# ----------------------------------------------------------------------------

# Opportunity classes:
#   'data'  : one opportunity per data qubit per round
#   'gate1q': N1Q opportunities per data qubit per round
#   'inc'   : 4d(d-1) data-check incidences per round (one data endpoint each)
#   'meas'  : d^2-1 syndrome measurements per round
#   'pair'  : 2d(d-1) nearest-neighbour pairs per round (two qubits per event)
#
# Channels:
#   'depol1' uniform X/Y/Z            'Z' pure Z
#   'ampXY'  X or Y, 1/2 each         'twirlAD' twirled amplitude damping
#   'depol2end' uniform non-identity Pauli on the data endpoint
#   'meas'   measurement flip         'paircorr' XX/YY/ZZ on a neighbour pair
#   'leak'   persistent sink leakage (Branch A Pe only)

N1Q = 5

BRANCH_A_PU = [
    # (name, per-qubit-per-round allocation, opportunity class, channel)
    ("two_qubit_CZ",           3.200e-3, "inc",    "depol2end"),
    ("pure_dephasing",         1.800e-3, "data",   "Z"),
    ("one_qubit_aggregate",    5.000e-4, "gate1q", "depol1"),
    ("measurement_decision",   4.000e-4, "meas",   "meas"),
    ("missed_erasures",        2.500e-4, "data",   "depol1"),
    ("QP_bypass",              1.000e-4, "data",   "ampXY"),
    ("thermal_unflagged",      1.000e-4, "data",   "ampXY"),
    ("residual_ZZ",            2.500e-4, "data",   "Z"),
    ("nonadiabatic_control",   2.000e-4, "data",   "depol1"),
    ("reset_backaction",       2.500e-4, "data",   "depol1"),
    ("readout_induced",        1.000e-4, "data",   "depol1"),
    ("coupler_higher_leakage", 1.500e-4, "data",   "depol1"),
    ("correlated_reserve",     1.000e-3, "pair",   "paircorr"),
    ("other_residual",         2.000e-4, "data",   "depol1"),
]
PE_LOAD = 1.543e-2  # located-erasure load, per data qubit per round

# Branch C as published in v1.5.8d Appendix S.6 (seven rows).
BRANCH_C_LIT = [
    ("T1_amplitude_damping",   1.11870e-2, "data",   "twirlAD"),
    ("pure_dephasing",         2.99744e-3, "data",   "Z"),
    ("one_qubit_gates",        1.80000e-4, "gate1q", "depol1"),  # 9e-5 x 2/round
    ("two_qubit_CNOT",         1.60000e-3, "inc",    "depol2end"),  # 6e-4/incidence at d=3
    ("syndrome_measurement",   8.88889e-4, "meas",   "meas"),     # 1e-3/check at d=3
    ("correlated_reserve",     2.00000e-4, "pair",   "paircorr"),
]

# Rows Sections 2.3 / 8.3 require Branch C to close but S.6 omitted.
# Charged at Branch-A parity: C has no erasure sink, so none of these are
# A-specific taxes -- they are ordinary fluxonium mechanisms.
BRANCH_C_CONTRACT_ADDITIONS = [
    ("residual_ZZ",            2.500e-4, "data", "depol1"),
    ("nonadiabatic_control",   2.000e-4, "data", "depol1"),
    ("reset_backaction",       2.500e-4, "data", "depol1"),
    ("readout_induced",        1.000e-4, "data", "depol1"),
    ("coupler_higher_leakage", 1.500e-4, "data", "depol1"),
    ("other_residual",         2.000e-4, "data", "depol1"),
]

# Wall-clock priors (microseconds per syndrome round)
T_ROUND_A = 20.0
T_ROUND_C = 13.5


def per_opportunity(rows, d):
    """Ledger-conserving map: allocation is per data qubit per round.

    tile budget = n_data * allocation, spread over n_opportunities, divided by
    the number of data qubits an event touches. Reproduces v1.5.8d Table S.2
    exactly at d=3.
    """
    n = d * d
    out = []
    for name, alloc, opp, chan in rows:
        if opp == "data":
            n_opp, per_event = n, 1
        elif opp == "gate1q":
            n_opp, per_event = N1Q * n, 1
        elif opp == "inc":
            n_opp, per_event = 4 * d * (d - 1), 1
        elif opp == "meas":
            n_opp, per_event = n - 1, 1
        elif opp == "pair":
            n_opp, per_event = 2 * d * (d - 1), 2
        else:
            raise ValueError(opp)
        p = (n * alloc) / (n_opp * per_event)
        out.append(dict(name=name, alloc=alloc, opp=opp, chan=chan,
                        n_opp=n_opp, p=p))
    return out


def set_two_qubit_anchor(rows, per_gate):
    """Rewrite the two-qubit row to a common per-gate anchor (4 gates/round)."""
    out = []
    for row in rows:
        if row[3] == "depol2end":
            out.append((row[0], 4.0 * per_gate, row[2], row[3]))
        else:
            out.append(row)
    return out


def set_correlated(rows, value):
    return [(r[0], value, r[2], r[3]) if r[0] == "correlated_reserve" else r
            for r in rows]


# ----------------------------------------------------------------------------
# 3. Channel -> per-qubit CSS marginals
# ----------------------------------------------------------------------------

def channel_marginals(chan, p):
    """Return (p_Xcomp, p_Zcomp) for one event of probability p.

    p_Xcomp = P(error has an X or Y component)  -> visible to memory-Z matching
    p_Zcomp = P(error has a Z or Y component)  -> visible to memory-X matching
    """
    if chan == "depol1":
        return 2.0 * p / 3.0, 2.0 * p / 3.0
    if chan == "Z":
        return 0.0, p
    if chan == "ampXY":
        return p, p / 2.0                      # X or Y, 1/2 each
    if chan == "twirlAD":
        return p / 2.0, p / 2.0                # X,Y,Z each p/4 (twirled AD)
    if chan == "depol2end":
        return 2.0 * p / 3.0, 2.0 * p / 3.0
    if chan == "paircorr":
        return 2.0 * p / 3.0, 2.0 * p / 3.0    # XX/YY/ZZ, per qubit
    if chan == "meas":
        return 0.0, 0.0
    raise ValueError(chan)


def combine(ps):
    """Odd-parity combination of independent small probabilities."""
    acc = 0.0
    for p in ps:
        acc = acc * (1 - p) + p * (1 - acc)
    return acc


def ledger_marginals(mapped, d):
    """Aggregate per-data-qubit-per-round X-component and Z-component
    probabilities, and the per-check measurement flip probability."""
    n = d * d
    xs, zs, ms = [], [], []
    for row in mapped:
        p, chan, opp = row["p"], row["chan"], row["opp"]
        if opp == "meas":
            ms.append(p)
            continue
        px, pz = channel_marginals(chan, p)
        # convert to per-data-qubit-per-round exposure
        if opp == "data":
            mult = 1
        elif opp == "gate1q":
            mult = N1Q
        elif opp == "inc":
            mult = row["n_opp"] / n          # mean incidences per data qubit
        elif opp == "pair":
            mult = 2 * row["n_opp"] / n      # pair events touching this qubit
        else:
            raise ValueError(opp)
        w = float(mult)
        full, frac = int(w), w - int(w)
        for _ in range(full):
            xs.append(px); zs.append(pz)
        if frac > 0:
            xs.append(px * frac); zs.append(pz * frac)
    return combine(xs), combine(zs), combine(ms)


# ----------------------------------------------------------------------------
# 4. Matching graphs
# ----------------------------------------------------------------------------

def build_matching(code, axis, p_data, p_meas, rounds):
    """Phenomenological matching graph with `rounds` noisy layers + 1 perfect
    closure layer. Node id = t * n_stab + s, boundary = (rounds+1) * n_stab."""
    H = code.HZ if axis == "Z" else code.HX
    q_to_s = code.q_to_z if axis == "Z" else code.q_to_x
    logical = set(code.logZ.tolist() if axis == "Z" else code.logX.tolist())
    n_stab = H.shape[0]
    B = (rounds + 1) * n_stab

    m = pymatching.Matching()
    w_data = np.log((1 - p_data) / max(p_data, 1e-15))
    w_meas = np.log((1 - p_meas) / max(p_meas, 1e-15))

    for t in range(rounds):
        for q in range(code.n_data):
            s = q_to_s[q]
            fid = {0} if q in logical else set()
            if len(s) == 2:
                a, b = t * n_stab + s[0], t * n_stab + s[1]
            else:
                a, b = t * n_stab + s[0], B
            m.add_edge(a, b, fault_ids=fid, weight=w_data,
                       error_probability=p_data, merge_strategy="independent")
        for s in range(n_stab):
            m.add_edge(t * n_stab + s, (t + 1) * n_stab + s, fault_ids=set(),
                       weight=w_meas, error_probability=p_meas,
                       merge_strategy="independent")
    m.set_boundary_nodes({B})
    return m, n_stab


# ----------------------------------------------------------------------------
# 5. Sampling
# ----------------------------------------------------------------------------

def sample_errors(code, mapped, rng, shots, rounds, pe=None, pe_mode="none",
                  lru_cadence=1, location_efficiency=0.0):
    """Draw error/measurement arrays.

    Returns EX, EZ  : (shots, rounds, n_data) uint8 - per-round Pauli components
            MZ, MX  : (shots, rounds, n_stab)  uint8 - measurement flips
    pe_mode: 'none' | 'pauli' | 'twirlAD' | 'leak'
    location_efficiency f: fraction of Pe events removed (ideal free location).
    """
    d, n = code.d, code.n_data
    EX = np.zeros((shots, rounds, n), np.uint8)
    EZ = np.zeros((shots, rounds, n), np.uint8)
    MZf = np.zeros((shots, rounds, code.n_z), np.uint8)
    MXf = np.zeros((shots, rounds, code.n_x), np.uint8)
    shape = (shots, rounds, n)

    def apply_pauli(mask, kind):
        """kind: 'depol1' | 'Z' | 'ampXY' | 'twirlAD' | 'depol2end'"""
        k = int(mask.sum())
        if k == 0:
            return
        if kind == "Z":
            EZ[mask] ^= 1
            return
        if kind in ("depol1", "depol2end"):
            u = rng.integers(0, 3, k)            # X, Y, Z
        elif kind == "ampXY":
            u = rng.integers(0, 2, k)            # X, Y
        elif kind == "twirlAD":
            # Pauli-twirled amplitude damping: p_X = p_Y = p_Z = gamma/4,
            # p_I = 1 - 3*gamma/4.  Marginals: X-comp = Z-comp = gamma/2.
            v = rng.integers(0, 4, k)
            EX[mask] ^= np.isin(v, (1, 2)).astype(np.uint8)
            EZ[mask] ^= np.isin(v, (2, 3)).astype(np.uint8)
            return
        else:
            raise ValueError(kind)
        ex = np.isin(u, (0, 1)).astype(np.uint8)   # X or Y -> X component
        ez = np.isin(u, (1, 2)).astype(np.uint8)   # Y or Z -> Z component
        EX[mask] ^= ex
        EZ[mask] ^= ez

    for row in mapped:
        p, chan, opp = row["p"], row["chan"], row["opp"]
        if opp == "meas":
            MZf ^= (rng.random((shots, rounds, code.n_z)) < p).astype(np.uint8)
            MXf ^= (rng.random((shots, rounds, code.n_x)) < p).astype(np.uint8)
        elif opp == "pair":
            for cls in code.pair_classes:
                k = len(cls)
                hit = rng.random((shots, rounds, k)) < p
                u = rng.integers(0, 3, (shots, rounds, k))
                ex = (hit & np.isin(u, (0, 1))).astype(np.uint8)
                ez = (hit & np.isin(u, (1, 2))).astype(np.uint8)
                for col, (q0, q1) in enumerate(cls):
                    EX[:, :, q0] ^= ex[:, :, col]; EX[:, :, q1] ^= ex[:, :, col]
                    EZ[:, :, q0] ^= ez[:, :, col]; EZ[:, :, q1] ^= ez[:, :, col]
        elif opp == "inc":
            # exact: one Bernoulli(p) trial per (data, check) incidence
            for qs in code.inc_slots:
                mask = np.zeros(shape, bool)
                mask[:, :, qs] = rng.random((shots, rounds, len(qs))) < p
                apply_pauli(mask, chan)
        else:
            reps = 1 if opp == "data" else N1Q
            for _ in range(reps):
                apply_pauli(rng.random(shape) < p, chan)

    # ---- located load Pe ----
    if pe_mode != "none" and pe:
        occur = rng.random(shape) < pe
        if location_efficiency > 0:
            keep = rng.random(shape) >= location_efficiency
            occur &= keep                      # located events removed (ideal)
        if pe_mode in ("pauli", "twirlAD"):
            apply_pauli(occur, "depol1" if pe_mode == "pauli" else "twirlAD")
        elif pe_mode == "leak":
            _apply_leakage(code, rng, occur, EX, EZ, MZf, MXf, lru_cadence)
        else:
            raise ValueError(pe_mode)

    return EX, EZ, MZf, MXf


def _apply_leakage(code, rng, occur, EX, EZ, MZf, MXf, cadence):
    """Persistent sink leakage with an unconditional LRU every `cadence` rounds.

    While leaked, every adjacent check of both axes is randomised. At the LRU
    boundary the qubit returns via a uniform depolarising event.
    """
    shots, rounds, n = occur.shape
    leaked = np.zeros_like(occur)
    for t in range(rounds):
        if t % cadence == 0:
            active = occur[:, t, :].copy()
        else:
            active = active | occur[:, t, :]
        leaked[:, t, :] = active

    # randomise adjacent checks while leaked
    for axis, H, Mf in (("Z", code.HZ, MZf), ("X", code.HX, MXf)):
        nb = (leaked.astype(np.uint8) @ H.T) > 0        # (shots, rounds, nstab)
        coin = rng.random(nb.shape) < 0.5
        Mf ^= (nb & coin).astype(np.uint8)

    # return-to-subspace depolarising event at the end of each LRU window
    ret = np.zeros_like(leaked)
    for t in range(rounds):
        if (t + 1) % cadence == 0 or t == rounds - 1:
            ret[:, t, :] = leaked[:, t, :]
    k = int(ret.sum())
    if k:
        u = rng.integers(0, 4, k)                        # I, X, Y, Z
        EX[ret.astype(bool)] ^= np.isin(u, (1, 2)).astype(np.uint8)
        EZ[ret.astype(bool)] ^= np.isin(u, (2, 3)).astype(np.uint8)


# ----------------------------------------------------------------------------
# 6. Detectors + decode
# ----------------------------------------------------------------------------

def detectors_and_obs(code, axis, E, Mf, rounds):
    """Build the detector array and the true logical flip."""
    H = code.HZ if axis == "Z" else code.HX
    log = code.logZ if axis == "Z" else code.logX
    cum = np.cumsum(E, axis=1) % 2                       # (shots, rounds, n)
    syn = (cum @ H.T) % 2                                # noiseless syndromes
    m = (syn ^ Mf).astype(np.uint8)                      # noisy measurements
    det = np.empty((E.shape[0], rounds + 1, H.shape[0]), np.uint8)
    det[:, 0, :] = m[:, 0, :]
    det[:, 1:rounds, :] = m[:, 1:, :] ^ m[:, :-1, :]
    det[:, rounds, :] = syn[:, -1, :] ^ m[:, -1, :]      # perfect closure
    obs = cum[:, -1, :][:, log].sum(1) % 2
    return det.reshape(E.shape[0], -1), obs.astype(np.uint8)


def run_config(code, mapped, rounds, shots, seed, pe=None, pe_mode="none",
               lru_cadence=1, location_efficiency=0.0, batch=20000):
    """Return (n_shots, n_failures) where failure = either CSS axis flips."""
    rng = np.random.default_rng(seed)
    px, pz, pm = ledger_marginals(mapped, code.d)
    if pe_mode in ("pauli", "twirlAD") and pe:
        # a real decoder knows the average located-event rate; fold it into the
        # data-edge weights. Leakage stays out (deliberate model mismatch).
        eff = pe * (1.0 - location_efficiency)
        ax, az = channel_marginals("depol1" if pe_mode == "pauli" else "twirlAD", eff)
        px, pz = combine([px, ax]), combine([pz, az])
    mZ, _ = build_matching(code, "Z", px, pm, rounds)
    mX, _ = build_matching(code, "X", pz, pm, rounds)

    fails = 0
    done = 0
    while done < shots:
        k = min(batch, shots - done)
        EX, EZ, MZf, MXf = sample_errors(
            code, mapped, rng, k, rounds, pe=pe, pe_mode=pe_mode,
            lru_cadence=lru_cadence, location_efficiency=location_efficiency)
        dZ, oZ = detectors_and_obs(code, "Z", EX, MZf, rounds)
        dX, oX = detectors_and_obs(code, "X", EZ, MXf, rounds)
        pZ = mZ.decode_batch(dZ)[:, 0]
        pX = mX.decode_batch(dX)[:, 0]
        fails += int((((pZ ^ oZ) | (pX ^ oX)) > 0).sum())
        done += k
    return done, fails


# ----------------------------------------------------------------------------
# 7. Statistics
# ----------------------------------------------------------------------------

def wilson(k, n, z=1.959963985):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / den
    hw = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, ctr - hw), min(1.0, ctr + hw)


def per_round(p_fail, rounds=10):
    return 1.0 - (1.0 - p_fail) ** (1.0 / rounds)


def hazard(p_round, t_us):
    """lambda_L in 1/ms."""
    return -np.log(1.0 - p_round) / (t_us * 1e-3)


def p_fail_time(lam, T_ms=1.0):
    return 1.0 - np.exp(-lam * T_ms)


def summarise(n, k, t_round, rounds=10, T_ms=1.0):
    p, lo, hi = wilson(k, n)
    out = {"shots": n, "failures": k, "P_fail_10r": p,
           "P_fail_10r_lo": lo, "P_fail_10r_hi": hi}
    for tag, v in (("", p), ("_lo", lo), ("_hi", hi)):
        pr = per_round(v, rounds)
        lam = hazard(pr, t_round)
        out[f"pL_round{tag}"] = pr
        out[f"lambda_L{tag}"] = lam
        out[f"P_fail_1ms{tag}"] = p_fail_time(lam, T_ms)
    out["t_round_us"] = t_round
    return out


def hazard_ratio_ci(nA, kA, tA, nC, kC, tC, rounds=10, reps=20000, seed=7):
    """Parametric bootstrap CI on lambda_A / lambda_C (equal wall clock)."""
    rng = np.random.default_rng(seed)
    a = rng.binomial(nA, max(kA, 1) / nA, reps) / nA
    c = rng.binomial(nC, max(kC, 1) / nC, reps) / nC
    a = np.clip(a, 1e-9, 1 - 1e-9); c = np.clip(c, 1e-9, 1 - 1e-9)
    lam_a = hazard(per_round(a, rounds), tA)
    lam_c = hazard(per_round(c, rounds), tC)
    r = lam_a / lam_c
    return float(np.median(r)), float(np.percentile(r, 2.5)), \
        float(np.percentile(r, 97.5))

