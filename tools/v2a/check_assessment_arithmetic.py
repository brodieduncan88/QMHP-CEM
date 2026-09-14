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

# --- 3b. Consequences the assessment states only qualitatively ---------------
# (i) Matrix-element crossover at which the 150 ns rectangular cycle meets the
#     cap under convention A: u_C = 1/(T n) = cap  ->  n* = 1/(T cap).
N_C_CROSSOVER_A = 1.0 / (150e-9 * U_C_CAP_HZ)
add("Crossover n_C at which 150 ns meets the cap (convention A)", 4.0 / 3.0, N_C_CROSSOVER_A, 1e-9,
    note="exactly 4/3; assessment's 'toward 1.36' is above it, 1.300454 below it")

# (ii) Envelope-corrected peak requirement. Under the on-resonance pulse-area
#      theorem the rotation angle depends only on the integrated amplitude, so a
#      smooth envelope of the same duration needs its peak raised by 1/eta,
#      eta = (envelope area)/(peak x T). The assessment applies this only to the
#      150 ns point; applied consistently it also bites at longer durations.
ENVELOPES = {
    "rectangular": 1.0,
    "hann": hann_area_fraction(),
    "gaussian_2sigma": gaussian_area_fraction(2.0),
}
envelope_cap_table = []
for name, eta in ENVELOPES.items():
    for conv in ("A", "B"):
        for T_ns in DURATIONS_NS:
            peak = u_c_for_cycle(T_ns * 1e-9, N_C, conv) / eta
            envelope_cap_table.append({
                "envelope": name, "convention": conv, "T_ns": T_ns,
                "required_peak_u_C_MHz": peak / 1e6,
                "within_5MHz_cap": peak <= U_C_CAP_HZ,
            })
extras["envelope_cap_table"] = envelope_cap_table
breaches = {
    (name, conv): [r["T_ns"] for r in envelope_cap_table
                   if r["envelope"] == name and r["convention"] == conv and not r["within_5MHz_cap"]]
    for name in ENVELOPES for conv in ("A", "B")
}
extras["durations_breaching_cap"] = {f"{n}/{c}": v for (n, c), v in breaches.items()}
add("Cap breach, rectangular/convention A, is 150 ns only", 1.0,
    1.0 if breaches[("rectangular", "A")] == [150] else 0.0, 1e-12)
add("Cap breach, Hann/convention A, extends to 200 and 300 ns", 1.0,
    1.0 if breaches[("hann", "A")] == [150, 200, 300] else 0.0, 1e-12,
    note="the assessment applies the finite-edge argument only at 150 ns")
add("Cap breach, Hann/convention B, still includes 150 ns", 1.0,
    1.0 if 150 in breaches[("hann", "B")] else 0.0, 1e-12,
    note="2/(2 T n) = 1/(T n): the Hann penalty exactly cancels the convention factor")

# (iii) Cost of clamping at the cap instead of relaxing the duration. A
#      rectangular pulse held at the cap for T rotates by theta = 2 pi u_cap n T;
#      the mediator is left with P(1_C) = sin^2(theta/2).
def residual_after_clamped_pulse(T_s: float, n: float, convention: str, cap: float = U_C_CAP_HZ) -> float:
    f_r = cap * n if convention == "A" else 2.0 * cap * n
    theta = 2.0 * math.pi * f_r * T_s
    return math.sin(theta / 2.0) ** 2


clamp_150 = residual_after_clamped_pulse(150e-9, N_C, "A")
add("Mediator residual if 150 ns is clamped at the cap (convention A)", None, clamp_150,
    note="under-rotation left in 1_C; compare the 8e-4 screen")
extras["clamped_150ns_residual_vs_screen"] = clamp_150 / SCREEN_ERROR
extras["clamped_150ns_underrotation_percent"] = 100.0 * (1.0 - U_C_CAP_HZ / u_c_for_cycle(150e-9, N_C, "A"))

# (v) Unit and definition factors that are NOT the drive-prefactor factor of two.
extras["conversion_factors"] = {
    "MHz_to_Mrad_per_s": 2 * math.pi,
    "drive_prefactor_A_over_B": 2.0,
    "peak_coefficient_to_Rabi_frequency_convention_A": N_C,
    "peak_coefficient_to_Rabi_frequency_convention_B": 2 * N_C,
    "Rabi_defined_via_hbar_Omega_sigma_x_vs_hbar_Omega_over_2_sigma_x": 2.0,
    "5_MHz_cap_in_Mrad_per_s": 2 * math.pi * 5.0,
}
# The same factor-of-two hazard the assessment flags for u_C applies to zeta:
# H/h = zeta |22><22| gives T_pi = 1/(2 zeta); H/h = (J/2) Z Z gives T_pi = 1/(4 J).
extras["zeta_convention_T_pi_us"] = {
    "H/h = zeta |22><22|  (assessment)": t_pi_from_zeta(ZETA_DISPLAYED_HZ) * 1e6,
    "H/h = (J/2) Z Z": 1.0 / (4.0 * ZETA_DISPLAYED_HZ) * 1e6,
}
extras["M1_shortfall_factor_range"] = [
    zeta_from_t_pi(GATE_ALLOCATION_S) / zeta_from_t_pi(t * 1e-6) for t in M1_WAIT_RANGE_US
]

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

# (iv) An in-phase crosstalk term on the mediator's own drive is an amplitude
#      error: theta -> 2 pi (1 + c), leaving P(1_C) = sin^2(pi c).
def residual_from_amplitude_error(c: float) -> float:
    return math.sin(math.pi * c) ** 2


extras["residual_from_in_phase_crosstalk"] = {
    f"{db} dB": residual_from_amplitude_error(amplitude_ratio_from_db(db)) for db in CROSSTALK_DB
}
add("Residual from an uncalibrated in-phase -40 dB crosstalk term", None,
    residual_from_amplitude_error(1e-2), note="exceeds the 8e-4 screen on its own")

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

# --- 6b. What the pair-count sum does and does not establish -----------------
# The assessment writes that the counts "sum to 24, consistent with four layers
# of six interactions. That is useful: the pair graph can be edge-coloured into
# the desired four conflict-free layers." The sum is necessary, not sufficient:
# a graph with the identical data degree sequence and the identical 24 edges need
# not be 4-edge-colourable. Counterexample: move the boundary stabilisers so one
# ancilla has degree 5. Vizing/Koenig then force at least 5 colours.
COUNTEREXAMPLE_STABILISERS = [
    frozenset({0, 1, 3, 4}), frozenset({1, 2, 4, 5}),
    frozenset({3, 4, 6, 7}), frozenset({4, 5, 7, 8}),
    frozenset({0, 1, 2, 3, 6}),                      # degree-5 ancilla
    frozenset({7, 8}), frozenset({5}),
]
ce_degrees = [sum(q in st for st in COUNTEREXAMPLE_STABILISERS) for q in range(9)]
ce_edges = sum(len(st) for st in COUNTEREXAMPLE_STABILISERS)
add("Counterexample has the same data degree sequence", 1.0,
    1.0 if ce_degrees == PAIR_COUNTS else 0.0, 1e-12)
add("Counterexample has the same 24 edges", 24.0, float(ce_edges), 1e-12)
add("Counterexample is NOT 4-edge-colourable", 1.0,
    1.0 if edge_colouring(COUNTEREXAMPLE_STABILISERS, 4) is None else 0.0, 1e-12,
    note="so 'sum to 24' does not establish the four-layer schedule; the search above does")

# The 4-edge-colourability that does hold comes from the ancilla side: the Tanner
# graph is bipartite with maximum degree 4, so Koenig's line-colouring theorem
# gives exactly 4 colours, and 4 is the minimum.
ancilla_degrees = sorted((len(st) for st in SURFACE17_STABILISERS), reverse=True)
extras["ancilla_degrees"] = ancilla_degrees
add("Maximum degree of the Tanner graph is 4", 4.0, float(max(max(ancilla_degrees), max(PAIR_COUNTS))), 1e-12,
    note="Koenig: a bipartite graph needs exactly max-degree colours, so 4 is both sufficient and minimal")


def count_colourings(stabilisers, n_colours, balanced_size=None):
    """Count proper n-edge-colourings, and how many are perfectly balanced."""
    edges = [(a, q) for a, st in enumerate(stabilisers) for q in sorted(st)]
    used_a = [0] * len(stabilisers)
    used_q = [0] * 9
    size = [0] * n_colours
    total = 0
    balanced = 0

    def rec(i):
        nonlocal total, balanced
        if i == len(edges):
            total += 1
            if balanced_size is not None and all(x == balanced_size for x in size):
                balanced += 1
            return
        a, q = edges[i]
        for c in range(n_colours):
            bit = 1 << c
            if used_a[a] & bit or used_q[q] & bit:
                continue
            if balanced_size is not None and size[c] >= balanced_size:
                continue
            used_a[a] |= bit
            used_q[q] |= bit
            size[c] += 1
            rec(i + 1)
            used_a[a] &= ~bit
            used_q[q] &= ~bit
            size[c] -= 1

    rec(0)
    return total, balanced


_, N_BALANCED = count_colourings(SURFACE17_STABILISERS, 4, balanced_size=6)
extras["balanced_4x6_colouring_count"] = N_BALANCED
add("Balanced 4x6 colourings exist and are many", 1.0, 1.0 if N_BALANCED > 0 else 0.0, 1e-12,
    note="'four layers of six' is a stronger claim than 'four conflict-free layers'")

# Hook-error ordering is a separate constraint that edge colouring cannot express.
# For a weight-4 stabiliser, of the 4! = 24 orders in which its data qubits may be
# engaged, the ones that let a single mid-circuit ancilla fault propagate to a
# weight-2 data error along the logical direction are hook-fatal.
extras["weight4_orderings"] = math.factorial(4)
extras["hook_fatal_orderings_per_weight4_ancilla"] = 8
extras["hook_fatal_fraction"] = 8 / math.factorial(4)

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

# 7b. The 0.8 duty factor is a wall-clock figure. Resolved per qubit against the
# assessment's own degree list, a degree-d data qubit is inside a native-gate
# interval for only d of the 4 layers, so the outside-fraction is 1 - d/4.
# outside-fraction of a qubit engaged in d one-microsecond gate layers = 1 - d/20.
LAYER_US = 1.0
duty = {
    "wall_clock_uniform": 1.0 - (N_GATE_LAYERS_1US * LAYER_US) / SCHEDULE_US,
    "per_data_qubit_mean": sum(1.0 - d * LAYER_US / SCHEDULE_US for d in PAIR_COUNTS) / len(PAIR_COUNTS),
    "per_ancilla_mean": sum(1.0 - len(st) * LAYER_US / SCHEDULE_US for st in SURFACE17_STABILISERS)
    / len(SURFACE17_STABILISERS),
    "all_17_qubits_mean": 1.0 - (2 * 24 * LAYER_US) / (17 * SCHEDULE_US),
}
duty["per_data_qubit_mean_exact"] = str(1 - Fraction(sum(PAIR_COUNTS), len(PAIR_COUNTS)) / Fraction(int(SCHEDULE_US)))
extras["outside_fraction_by_accounting"] = duty
add("Degree-resolved outside fraction (data qubits)", 13.0 / 15.0, duty["per_data_qubit_mean"], 1e-9,
    note="0.8667, not the 0.8 the assessment uses; the assessment's own degree list implies it")
extras["background_term_by_duty_factor"] = {
    "assessment 0.8": BACKGROUND_PARENT * 0.8,
    "degree-resolved 0.8667": BACKGROUND_PARENT * duty["per_data_qubit_mean"],
}
extras["background_relative_difference_percent"] = 100.0 * (duty["per_data_qubit_mean"] / 0.8 - 1.0)

# 7c. "Linear in time" is a Markovian-white-noise assumption. Under quasi-static
# 1/f dephasing the envelope is exp[-(t/T_phi)^2], so the factor is 0.8^2.
extras["time_scaling_by_mechanism"] = {
    "markovian_linear (exponent 1)": 0.8,
    "quasi_static_1_over_f (exponent 2)": 0.8 ** 2,
}
extras["background_term_exact_exponential"] = 1.0 - (1.0 - BACKGROUND_PARENT) ** 0.8
extras["dephasing_residual_by_exponent"] = {
    "exponent 1 (as quoted)": DEPHASING_RESIDUAL,
    "exponent 2 (1/f)": (DEPHASING_RESIDUAL / 0.8) * 0.8 ** 2,
}
add("Dephasing residual under a t^2 (1/f) law instead of t", None,
    (DEPHASING_RESIDUAL / 0.8) * 0.8 ** 2,
    note="1.153e-3 vs the quoted 1.441e-3: a 25% difference the exponent alone decides")

# 7d. The diagnostic average depends entirely on the denominator, which the
# assessment states (9 data qubits) but whose consequences it does not.
extras["diagnostic_average_by_denominator"] = {
    "per data qubit (9)": 24 * SCREEN_ERROR / 9,
    "per Surface-17 qubit (17)": 24 * SCREEN_ERROR / 17,
    "half to each partner, per data qubit": 0.5 * 24 * SCREEN_ERROR / 9,
    "worst data qubit (degree 4)": max(PAIR_COUNTS) * SCREEN_ERROR,
    "best data qubit (degree 2)": min(PAIR_COUNTS) * SCREEN_ERROR,
}
add("Spread hidden by the diagnostic average (worst/best data qubit)", 2.0,
    max(PAIR_COUNTS) / min(PAIR_COUNTS), 1e-12,
    note="2.133e-3 conceals a 1.6e-3 to 3.2e-3 range")

# 7e. The two layer budgets the assessment uses are not the same.
extras["layer_budget_tension"] = {
    "once_only_section_us": N_GATE_LAYERS_1US * 1.0,
    "forbidden_surface17_insertion_us": N_LAYERS * 196.773e-3,
    "ratio": (N_GATE_LAYERS_1US * 1.0) / (N_LAYERS * 196.773e-3),
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
