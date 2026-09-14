#!/usr/bin/env python3
"""Reproduce every numerical claim in the V2A G0 follow-up audit deep-research
assessment (docs/v2a/G0-followup-audit-v0.1-deep-research-assessment.md).

Standard library only. Run it directly to print the comparison table; it exits
non-zero if any assessment-stated value is not reproduced within tolerance.

Every quantity here is derived from numbers *reported* in the assessment
(f_22, Delta_min, n_C, zeta, the pair counts, the ledger inputs). None of those
inputs is reproduced here; only the arithmetic and physics conventions built on
them are. See docs/v2a/reported-not-reproduced.md for the input list.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field, asdict
from fractions import Fraction
from itertools import product

# --- CODATA 2018 exact constants ------------------------------------------
H_PLANCK = 6.62607015e-34  # J s
K_B = 1.380649e-23         # J / K

# --- Inputs reported by the audit / assessment (not reproduced here) -------
F22_HZ = 7.016031785e9        # 22-conditioned mediator 0_C -> 1_C transition
DELTA_MIN_HZ = 5.90e6         # nearest other logical-conditioned mediator line
N_C = 1.300454                # |<22,1_C| n_C |22,0_C>|
N_C_ALT = 1.36                # "toward 1.36" alternative quoted in the text
U_C_CAP_HZ = 5.0e6            # proposed |u_C| <= 5 MHz search cap
ZETA_DISPLAYED_HZ = 62.1e3    # displayed static ZZ point (zeta / 2 pi)
M1_WAIT_RANGE_US = (8.05, 8.37)
GATE_ALLOCATION_S = 1.0e-6    # one gate layer
DURATIONS_NS = [150, 200, 300, 400, 500, 650, 800]
TEMPERATURES_MK = [15, 20, 30]
INITIAL_POPULATIONS = [1e-3, 1e-2]
CROSSTALK_DB = [-80, -60, -50, -40]
PAIR_COUNTS = [2, 3, 2, 3, 4, 3, 2, 3, 2]
N_LAYERS = 4
SCREEN_ERROR = 8e-4
N_DATA = 9
SCHEDULE_US = 20.0
N_GATE_LAYERS_1US = 4
BACKGROUND_PARENT = 1.700e-3
DEPHASING_RESIDUAL = 1.441e-3


@dataclass
class Check:
    name: str
    stated: float | None
    computed: float
    rel_tol: float = 5e-3
    note: str = ""

    @property
    def ok(self) -> bool:
        if self.stated is None:
            return True
        if self.stated == 0:
            return abs(self.computed) < 1e-15
        return abs(self.computed - self.stated) / abs(self.stated) <= self.rel_tol


checks: list[Check] = []
extras: dict[str, object] = {}


def add(name, stated, computed, rel_tol=5e-3, note=""):
    checks.append(Check(name, stated, computed, rel_tol, note))
    return computed


# --- 1. M1 nominal static wait ---------------------------------------------
# Static ZZ: H/h = (zeta/4) Z Z (equivalently the |11>-conditioned frequency
# shift is zeta). Conditional phase phi_ZZ(t) = 2 pi zeta t reaches pi at
# T_pi = 1 / (2 zeta).
def t_pi_from_zeta(zeta_hz: float) -> float:
    return 1.0 / (2.0 * zeta_hz)


def zeta_from_t_pi(t_pi_s: float) -> float:
    return 1.0 / (2.0 * t_pi_s)


add("M1: T_pi at zeta=62.1 kHz [us]", 8.052, t_pi_from_zeta(ZETA_DISPLAYED_HZ) * 1e6, 1e-3)
add("M1: zeta needed for 1 us wait [kHz]", 500.0, zeta_from_t_pi(GATE_ALLOCATION_S) / 1e3, 1e-6)
add("M1: shortfall factor (500 kHz / 62.1 kHz)", 8.0, zeta_from_t_pi(GATE_ALLOCATION_S) / ZETA_DISPLAYED_HZ, 0.01,
    note="'about a factor of eight' (exact 8.05)")
extras["M1_zeta_range_kHz_for_8.05_8.37_us"] = [
    round(zeta_from_t_pi(t * 1e-6) / 1e3, 2) for t in M1_WAIT_RANGE_US
]

# --- 2. Rabi ladder ---------------------------------------------------------
# One full resonant 2 pi Rabi cycle at Rabi frequency f_R (cycles/s) takes
# T = 1 / f_R.
STATED_FR_MHZ = [6.67, 5.00, 3.33, 2.50, 2.00, 1.54, 1.25]
STATED_RATIO = [1.13, 0.85, 0.56, 0.42, 0.34, 0.26, 0.21]
ladder = []
for T_ns, s_fr, s_ratio in zip(DURATIONS_NS, STATED_FR_MHZ, STATED_RATIO):
    f_r = 1.0 / (T_ns * 1e-9)
    ratio = f_r / DELTA_MIN_HZ
    add(f"Rabi ladder: f_R at {T_ns} ns [MHz]", s_fr, f_r / 1e6, 2e-3)
    add(f"Rabi ladder: f_R/Delta_min at {T_ns} ns", s_ratio, ratio, 1.5e-2,
        note="table is rounded to 2 decimals")
    ladder.append({"T_ns": T_ns, "f_R_MHz": f_r / 1e6, "f_R_over_Delta_min": ratio})
extras["rabi_ladder"] = ladder

# --- 3. Drive coefficient u_C under the two candidate conventions ----------
# Two-level subspace {|0_C>, |1_C>}, real matrix element n = <1_C|n_C|0_C>, so
# n_C -> n sigma_x on that subspace.
#   Convention A ("one-factor"):  H_d/h = u_C n_C cos(2 pi f_d t)
#       RWA -> H/h = (u_C n / 2)(sigma_+ e^{-i w t} + h.c.)
#       rotating frame -> H = h (u_C n / 2) sigma_x = hbar (Omega/2) sigma_x
#       with Omega/2 = 2 pi u_C n / 2  ->  f_R = Omega/2pi = u_C n.
#   Convention B ("two-factor"):  H_d/h = 2 u_C n_C cos(2 pi f_d t)
#       f_R = 2 u_C n.
# Convention A is the one under which the assessment's "5.13 MHz at 150 ns"
# is correct.
def u_c_for_cycle(T_s: float, n: float, convention: str) -> float:
    f_r = 1.0 / T_s
    if convention == "A":
        return f_r / n
    if convention == "B":
        return f_r / (2.0 * n)
    raise ValueError(convention)


add("u_C at 150 ns, n_C=1.300454, convention A [MHz]", 5.13, u_c_for_cycle(150e-9, N_C, "A") / 1e6, 2e-3)
add("u_C at 150 ns, n_C=1.36, convention A [MHz]", None, u_c_for_cycle(150e-9, N_C_ALT, "A") / 1e6,
    note="assessment: 'may fall just inside the cap' -> 4.90 MHz")
add("u_C at 150 ns, n_C=1.300454, convention B [MHz]", None, u_c_for_cycle(150e-9, N_C, "B") / 1e6,
    note="2.56 MHz: inside the cap under the two-factor convention")
uc_table = []
for T_ns in DURATIONS_NS:
    uA = u_c_for_cycle(T_ns * 1e-9, N_C, "A")
    uB = u_c_for_cycle(T_ns * 1e-9, N_C, "B")
    uc_table.append({
        "T_ns": T_ns,
        "u_C_MHz_convention_A": uA / 1e6,
        "u_C_MHz_convention_B": uB / 1e6,
        "within_5MHz_cap_A": uA <= U_C_CAP_HZ,
        "within_5MHz_cap_B": uB <= U_C_CAP_HZ,
        "u_C_Mrad_per_s_convention_A": 2 * math.pi * uA / 1e6,
        "u_C_Mrad_per_s_convention_B": 2 * math.pi * uB / 1e6,
    })
extras["u_C_table"] = uc_table
extras["150ns_inside_cap_convention_A"] = u_c_for_cycle(150e-9, N_C, "A") <= U_C_CAP_HZ
extras["150ns_inside_cap_convention_B"] = u_c_for_cycle(150e-9, N_C, "B") <= U_C_CAP_HZ
# Minimum duration that respects the cap under each convention, at n_C=1.300454:
extras["T_min_ns_at_cap_convention_A"] = 1.0 / (U_C_CAP_HZ * N_C) * 1e9
extras["T_min_ns_at_cap_convention_B"] = 1.0 / (2.0 * U_C_CAP_HZ * N_C) * 1e9


# Envelope area: a smooth envelope bounded by its peak has less area than the
# rectangle of the same peak and duration, so it needs a larger peak for the
# same rotation angle. Peak multipliers relative to rectangular:
def hann_area_fraction() -> float:
    # cos^2(pi t / T) on [-T/2, T/2] -> area T/2
    return 0.5


def gaussian_area_fraction(n_sigma: float) -> float:
    # exp(-t^2 / (2 sigma^2)) truncated at +-n_sigma with T = 2 n_sigma sigma
    # area = sigma sqrt(2 pi) erf(n_sigma / sqrt 2); fraction = area / T
    return math.sqrt(2 * math.pi) * math.erf(n_sigma / math.sqrt(2)) / (2 * n_sigma)


extras["envelope_peak_multiplier_hann"] = 1.0 / hann_area_fraction()
extras["envelope_peak_multiplier_gaussian_2sigma"] = 1.0 / gaussian_area_fraction(2.0)
extras["envelope_peak_multiplier_gaussian_3sigma"] = 1.0 / gaussian_area_fraction(3.0)

# --- 4. Thermal occupation --------------------------------------------------
def bose_occupation(f_hz: float, T_k: float) -> float:
    x = H_PLANCK * f_hz / (K_B * T_k)
    return 1.0 / math.expm1(x)


def two_level_excited_population(f_hz: float, T_k: float) -> float:
    x = H_PLANCK * f_hz / (K_B * T_k)
    return 1.0 / (1.0 + math.exp(x))


def temperature_for_occupation(f_hz: float, n: float) -> float:
    # n = 1/(e^x - 1) -> x = ln(1 + 1/n)
    return H_PLANCK * f_hz / (K_B * math.log1p(1.0 / n))


STATED_NB = [1.8e-10, 4.9e-8, 1.3e-5]
for T_mk, s in zip(TEMPERATURES_MK, STATED_NB):
    add(f"Bose occupation at {T_mk} mK, 7.016 GHz", s, bose_occupation(F22_HZ, T_mk * 1e-3), 3e-2,
        note="assessment quotes 2 significant figures")
extras["two_level_excited_population"] = {
    f"{T_mk}_mK": two_level_excited_population(F22_HZ, T_mk * 1e-3) for T_mk in TEMPERATURES_MK
}
extras["effective_temperature_mK_for_initial_population"] = {
    f"{p:g}": temperature_for_occupation(F22_HZ, p) * 1e3 for p in INITIAL_POPULATIONS
}
extras["hf_over_kB_K"] = H_PLANCK * F22_HZ / K_B

# --- 5. Crosstalk dB ----------------------------------------------------------
def amplitude_ratio_from_db(db: float) -> float:
    return 10 ** (db / 20.0)


def power_ratio_from_db(db: float) -> float:
    return 10 ** (db / 10.0)


add("Crosstalk: amplitude ratio at -40 dB (20 log10)", 1e-2, amplitude_ratio_from_db(-40), 1e-9)
add("Crosstalk: amplitude ratio at -80 dB (20 log10)", 1e-4, amplitude_ratio_from_db(-80), 1e-9)
extras["crosstalk_table"] = [
    {
        "dB": db,
        "amplitude_ratio_20log": amplitude_ratio_from_db(db),
        "ratio_if_misread_as_10log": power_ratio_from_db(db),
        "amplitude_error_factor_if_misread": power_ratio_from_db(db) / amplitude_ratio_from_db(db),
    }
    for db in CROSSTALK_DB
]

# --- 6. Four-layer schedule: Surface-17 pair counts ------------------------
# Rotated distance-3 surface code, data qubits 0..8 row-major. Four weight-4
# plaquettes plus four weight-2 boundary stabilisers (one per edge). The
# per-data-qubit stabiliser degree sequence is the reported pair-count list.
SURFACE17_STABILISERS = [
    frozenset({0, 1, 3, 4}), frozenset({1, 2, 4, 5}),
    frozenset({3, 4, 6, 7}), frozenset({4, 5, 7, 8}),
    frozenset({0, 1}), frozenset({7, 8}),       # top / bottom weight-2
    frozenset({3, 6}), frozenset({2, 5}),       # left / right weight-2
]
degree_sequence = [sum(q in s for s in SURFACE17_STABILISERS) for q in range(9)]
extras["surface17_degree_sequence"] = degree_sequence
add("Schedule: sum of pair counts", 24, float(sum(PAIR_COUNTS)), 1e-12)
add("Schedule: 4 layers x 6 interactions", 24, float(N_LAYERS * 6), 1e-12)
add("Schedule: Surface-17 degree sequence matches reported pair counts", 1.0,
    1.0 if degree_sequence == PAIR_COUNTS else 0.0, 1e-12)
add("Schedule: 4 x weight-4 + 4 x weight-2 = 24", 24.0, float(sum(len(s) for s in SURFACE17_STABILISERS)), 1e-12)


def edge_colouring(stabilisers, n_colours, max_per_layer=None):
    """Backtracking proper edge colouring of the ancilla-data bipartite graph.
    Each colour class is one conflict-free layer (no ancilla or data qubit
    appears twice in a layer). If max_per_layer is given, no layer may hold
    more than that many pairs. Returns a list of layers or None."""
    edges = [(a, q) for a, s in enumerate(stabilisers) for q in sorted(s)]
    colour = {}
    used_a = [set() for _ in stabilisers]
    used_q = [set() for _ in range(9)]
    size = [0] * n_colours

    def rec(i):
        if i == len(edges):
            return True
        a, q = edges[i]
        for c in range(n_colours):
            if c in used_a[a] or c in used_q[q]:
                continue
            if max_per_layer is not None and size[c] >= max_per_layer:
                continue
            colour[(a, q)] = c
            used_a[a].add(c)
            used_q[q].add(c)
            size[c] += 1
            if rec(i + 1):
                return True
            used_a[a].discard(c)
            used_q[q].discard(c)
            size[c] -= 1
            del colour[(a, q)]
        return False

    if not rec(0):
        return None
    layers = [[] for _ in range(n_colours)]
    for e, c in colour.items():
        layers[c].append(e)
    return layers


layers4 = edge_colouring(SURFACE17_STABILISERS, 4, max_per_layer=6)
layers3 = edge_colouring(SURFACE17_STABILISERS, 3)
add("Schedule: a 4-layer colouring with exactly 6 pairs per layer exists", 1.0,
    1.0 if layers4 and all(len(L) == 6 for L in layers4) else 0.0, 1e-12)
add("Schedule: no 3-layer colouring exists (max degree 4)", 1.0, 1.0 if layers3 is None else 0.0, 1e-12)
extras["one_valid_4x6_layer_colouring_sizes"] = [len(L) for L in layers4] if layers4 else None
extras["one_valid_4x6_layer_colouring"] = layers4
extras["edge_colouring_caveat"] = (
    "Existence of a 4x6 conflict-free layering is a graph fact only; it says nothing about "
    "hook-error-safe ordering, ancilla basis adapters, mediator recovery or readiness."
)

# --- 7. Once-only accounting arithmetic ---------------------------------------
add("Ledger: 24 x 8e-4 / 9", 2.1333e-3, 24 * SCREEN_ERROR / N_DATA, 1e-4)
outside = SCHEDULE_US - N_GATE_LAYERS_1US * 1.0
add("Ledger: time outside native-gate intervals [us]", 16.0, outside, 1e-12)
add("Ledger: outside fraction", 0.8, outside / SCHEDULE_US, 1e-12)
add("Ledger: 1.700e-3 x 0.8", 1.360e-3, BACKGROUND_PARENT * 0.8, 1e-6)
add("Ledger: parent of 1.441e-3 dephasing residual", 1.80125e-3, DEPHASING_RESIDUAL / 0.8, 1e-6)
extras["ledger_exact_fractions"] = {
    "24*8e-4/9": str(Fraction(24, 9) * Fraction(8, 10000)),
    "16/20": str(Fraction(16, 20)),
}

# --- 8. Static SQUID sign: spectrum of A + iB equals spectrum of A - iB ------
# For Hermitian H = A + iB (A real symmetric, B real antisymmetric), the matrix
# with the imaginary hopping sign reversed is A - iB = conj(H) = K H K, the
# antiunitary (complex-conjugation) image. A Hermitian matrix has a real
# characteristic polynomial, so conj(H) has the same characteristic polynomial
# and hence the same spectrum. Demonstrated below with Faddeev-LeVerrier on a
# fixed 4x4 example (no numpy needed).
def matmul(X, Y):
    n = len(X)
    return [[sum(X[i][k] * Y[k][j] for k in range(n)) for j in range(n)] for i in range(n)]


def trace(X):
    return sum(X[i][i] for i in range(len(X)))


def char_poly_coeffs(M):
    """Faddeev-LeVerrier: returns c_0..c_n of det(lambda I - M)."""
    n = len(M)
    I = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    coeffs = [1.0]
    Mk = [row[:] for row in I]
    for k in range(1, n + 1):
        Mk = matmul(M, Mk)
        c = -trace(Mk) / k
        coeffs.append(c)
        Mk = [[Mk[i][j] + (c if i == j else 0.0) for j in range(n)] for i in range(n)]
    return coeffs


A_EX = [[1.0, 0.3, 0.0, 0.2], [0.3, -0.5, 0.7, 0.0], [0.0, 0.7, 2.0, -0.4], [0.2, 0.0, -0.4, 0.1]]
B_EX = [[0.0, 0.6, 0.0, -0.1], [-0.6, 0.0, 0.25, 0.0], [0.0, -0.25, 0.0, 0.8], [0.1, 0.0, -0.8, 0.0]]
H_plus = [[complex(A_EX[i][j], B_EX[i][j]) for j in range(4)] for i in range(4)]
H_minus = [[complex(A_EX[i][j], -B_EX[i][j]) for j in range(4)] for i in range(4)]
cp_plus = char_poly_coeffs(H_plus)
cp_minus = char_poly_coeffs(H_minus)
max_imag = max(abs(c.imag) for c in cp_plus)
max_diff = max(abs(a - b) for a, b in zip(cp_plus, cp_minus))
add("SQUID sign: char. polynomial of A+iB is real (max |Im|)", 0.0, max_imag, note="expect ~1e-16")
add("SQUID sign: char. polynomials of A+iB and A-iB agree (max diff)", 0.0, max_diff, note="expect ~1e-16")
checks[-2].stated = None  # tolerance-free informational checks; enforce below
checks[-1].stated = None
SQUID_OK = max_imag < 1e-12 and max_diff < 1e-12
extras["squid_sign_char_poly_real_and_equal"] = SQUID_OK


# --- Report -----------------------------------------------------------------
def report(stream=sys.stdout) -> bool:
    all_ok = True
    w = max(len(c.name) for c in checks)
    stream.write(f"{'check':<{w}}  {'stated':>12}  {'computed':>14}  ok\n")
    for c in checks:
        st = "-" if c.stated is None else f"{c.stated:.6g}"
        flag = "ok" if c.ok else "MISMATCH"
        all_ok &= c.ok
        stream.write(f"{c.name:<{w}}  {st:>12}  {c.computed:>14.6g}  {flag}{('  # ' + c.note) if c.note else ''}\n")
    all_ok &= SQUID_OK
    stream.write("\nSupplementary values:\n")
    stream.write(json.dumps(extras, indent=1, default=str))
    stream.write("\n")
    return all_ok


if __name__ == "__main__":
    ok = report()
    print("\nRESULT:", "ALL ASSESSMENT VALUES REPRODUCED" if ok else "MISMATCH FOUND")
    sys.exit(0 if ok else 1)
