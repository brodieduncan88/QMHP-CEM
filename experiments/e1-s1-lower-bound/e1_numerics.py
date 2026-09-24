# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""E1 numerics: the Galerkin entries, the rigorous energy enclosure, the trial vector and
the float64 consistency check, exactly as the frozen contract E1-CONTRACT.rev8.5.md (its
sha256 is pinned in driver.py) specifies them in sections 4.3-4.5. Section numbers below refer
to that contract. A non-finite or non-positive quantity never raises here: it makes the
requirement it belongs to fail, so the attempt is UNQUALIFIED, never FAILED (section 8). The
same holds for a finite value outside the float64 range: every decision is exact, and a
recorded float64 copy of such a value is +-inf (null in JSON), never an OverflowError.

Nothing here reads the S1 mesh or any result. The functions work on any list of
axis-aligned rectangles on z = 0 (R, an (N, 4) float64 array of x0, x1, y0, y1 in mm).

Units: S in mm^-1, sigma in arbitrary charge units, Q^2/(sigma^T S sigma) in mm, and
kappa in fF/mm, so C_lo = RD(Q^2 kappa_lo / E_up) is in fF.
"""
from __future__ import annotations

import ctypes
import math
import platform
import sys
from decimal import Decimal
from fractions import Fraction

import numpy as np
import scipy.linalg as sla

LD = np.longdouble
#: unit roundoff of the x87 64-bit significand (section 4.3)
U_LD = Fraction(1, 2 ** 64)
#: the frozen enclosure constant c (section 4.3)
C_ENC = 64
#: the block size of the block-pair structure (section 4.3)
BLOCK = 256
#: the smallest normal x87 long double
LD_MIN_NORMAL = Fraction(1, 2 ** 16382)
#: the no-underflow requirement's floor (section 4.3)
UNDERFLOW_FLOOR = Fraction(1, 2 ** 16300)
#: the largest finite float64, exactly
DBL_MAX = Fraction(sys.float_info.max)

#: pi_lo, the 35-digit truncation of pi (section 4.3)
PI_LO = Fraction(Decimal("3.1415926535897932384626433832795028"))
#: the speed of light c_light, m/s, exactly (section 4.3)
C_LIGHT = Fraction(299792458)
#: eps_avg,lo = (1 + Fraction(11.45))/2, frozen as p/q (section 4.1, 4.3)
EPS_AVG_LO_PQ = "3504363460047667/562949953421312"
#: kappa_lo in fF/mm, frozen as p/q (section 4.3)
KAPPA_LO_PQ = ("1885503669250627622861089360932191552655172901344957236353565033/"
               "2722258935367507707706996859454145691648000000000000000000000")
#: the same function with eps_avg = 1 (K3, section 5)
KAPPA_FREE_PQ = ("538044552383553460856660832239569436888492538099/"
                 "4835703278458516698824704000000000000000000000")


class NumericsError(RuntimeError):
    """A numerical requirement of sections 4.3-4.5 failed (UNQUALIFIED in the attempt)."""


# --- exact helpers ----------------------------------------------------------------------------

def to_fr(x) -> Fraction:
    """The exact rational value of a float64 or long-double number."""
    return Fraction(*LD(x).as_integer_ratio())


def rd(x: Fraction) -> float:
    """RD: the largest float64 not above x (round toward -infinity), exactly once. Above the
    float64 range that is the largest finite float64; below -DBL_MAX it is -inf."""
    if x >= DBL_MAX:
        return sys.float_info.max
    if x < -DBL_MAX:
        return -math.inf
    f = float(x)                        # int/int true division is correctly rounded; |x| <= DBL_MAX
    if Fraction(f) > x:
        f = float(np.nextafter(f, -np.inf))
    return f


def ru(x: Fraction) -> float:
    """Round toward +infinity (displays of C_hi only): +inf above the float64 range."""
    if x > DBL_MAX:
        return math.inf
    if x <= -DBL_MAX:
        return -sys.float_info.max
    f = float(x)
    if Fraction(f) < x:
        f = float(np.nextafter(f, np.inf))
    return f


def to_float(x) -> float:
    """A recorded float64 copy of an exact rational, a float64 or a long double: +-inf beyond
    the float64 range instead of an OverflowError (no decision is taken on it)."""
    try:
        with np.errstate(over="ignore", under="ignore"):
            return float(x)
    except OverflowError:
        return math.inf if x > 0 else -math.inf


def gamma(m: int) -> Fraction:
    """gamma_m = m u / (1 - m u), exactly (section 4.3)."""
    return m * U_LD / (1 - m * U_LD)


def _digits(n: int) -> str:
    """The decimal digits of an int of any size (str() refuses more than 4,300 digits, and an
    exact long double below about 1e-4300 has a longer denominator)."""
    if n < 0:
        return "-" + _digits(-n)
    if n < 10 ** 4000:
        return str(n)
    chunks, base = [], 10 ** 1000
    while n:
        n, r = divmod(n, base)
        chunks.append(r)
    return str(chunks[-1]) + "".join(f"{c:01000d}" for c in reversed(chunks[:-1]))


def pq(x: Fraction) -> str:
    return f"{_digits(x.numerator)}/{_digits(x.denominator)}"


def finite(x) -> bool:
    """True for a finite float64 or long-double number (no exception for any input value)."""
    try:
        return bool(np.isfinite(LD(x)))
    except (TypeError, ValueError, OverflowError):
        return False


def pq_or_label(x) -> str:
    """The exact p/q string of a finite value; 'non-finite: <repr>' otherwise (raw files)."""
    return pq(to_fr(x)) if finite(x) else f"non-finite: {to_float(x)!r}"


def eps_avg_lo() -> Fraction:
    return (1 + Fraction(11.45)) / 2


def kappa(eps_avg: Fraction, epsilon0: float) -> Fraction:
    """min(4 pi_lo Fraction(EPSILON0), 10^7/c_light^2) * eps_avg * 10^12, in fF/mm."""
    return min(4 * PI_LO * Fraction(epsilon0), Fraction(10 ** 7) / (C_LIGHT * C_LIGHT)) * eps_avg * 10 ** 12


def frozen_constants_problems(epsilon0: float) -> list[str]:
    """The frozen p/q strings, recomputed (section 4.3 and the section 8 refusal list)."""
    bad = []
    if pq(eps_avg_lo()) != EPS_AVG_LO_PQ:
        bad.append("eps_avg,lo does not match its frozen p/q string")
    if pq(kappa(eps_avg_lo(), epsilon0)) != KAPPA_LO_PQ:
        bad.append("kappa_lo does not match its frozen p/q string")
    if pq(kappa(Fraction(1), epsilon0)) != KAPPA_FREE_PQ:
        bad.append("kappa (eps_avg = 1) does not match its frozen p/q string")
    return bad


# --- the entry routine (section 4.3) --------------------------------------------------------

def _F(X, Y, dt):
    """F(X, Y) and r^3 for arrays of coordinate differences, evaluated in dtype ``dt``.

    The operation sequence is the one the c0 derivation below counts:
      a2 = |X|*|X|; b2 = |Y|*|Y|; r2 = a2 + b2; r = sqrt(r2); r3 = r2*r;
      t1 = (((0.5*|X|)*|X|)*|Y|)*log((|Y| + r)/|X|)   (0 where X = 0 or Y = 0);
      t2 = (((0.5*|X|)*|Y|)*|Y|)*log((|X| + r)/|Y|)   (0 where X = 0 or Y = 0);
      F  = (t1 + t2) - r3/6.
    """
    ax = np.abs(X)
    ay = np.abs(Y)
    r2 = ax * ax + ay * ay
    r = np.sqrt(r2)
    r3 = r2 * r
    pos = (ax > 0) & (ay > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        t1 = np.where(pos, dt(0.5) * ax * ax * ay * np.log((ay + r) / ax), dt(0))
        t2 = np.where(pos, dt(0.5) * ax * ay * ay * np.log((ax + r) / ay), dt(0))
    return (t1 + t2) - r3 / dt(6), r3


_CORNERS = [(p, sp, q, sq, s, ss, t, st)
            for p, sp in ((0, -1), (1, 1)) for q, sq in ((0, -1), (1, 1))
            for s, ss in ((2, -1), (3, 1)) for t, st in ((2, -1), (3, 1))]


def entry_block(R: np.ndarray, i0: int, i1: int, j0: int, j1: int, dt, want_b: bool = False):
    """S entries for rows i0:i1 and columns j0:j1, wholly in dtype ``dt`` from the float64
    coordinates (coordinate differences, the log argument, every product, A_i, A_j, their
    product and the final division). With ``want_b`` (long double only) also
    B~ = c u_ld sum_k r~_k^3 / (A~_i A~_j) from the same intermediates.

    The 16-term corner sum is accumulated in a fixed order from 0. In a diagonal block the
    value computed for i <= j is used for both (i, j) and (j, i) (section 4.3)."""
    Ri = R[i0:i1].astype(dt)
    Rj = R[j0:j1].astype(dt)
    acc = np.zeros((i1 - i0, j1 - j0), dt)
    r3s = np.zeros_like(acc) if want_b else None
    for p, sp, q, sq, s, ss, t, st in _CORNERS:
        X = Ri[:, p][:, None] - Rj[:, q][None, :]
        Y = Ri[:, s][:, None] - Rj[:, t][None, :]
        f, r3 = _F(X, Y, dt)
        acc += (sp * sq * ss * st) * f
        if want_b:
            r3s += r3
    Ai = (Ri[:, 1] - Ri[:, 0]) * (Ri[:, 3] - Ri[:, 2])
    Aj = (Rj[:, 1] - Rj[:, 0]) * (Rj[:, 3] - Rj[:, 2])
    AA = Ai[:, None] * Aj[None, :]
    S = acc / AA
    B = (dt(C_ENC) * dt(2) ** -64) * r3s / AA if want_b else None
    if i0 == j0:
        iu = np.triu_indices(i1 - i0, 1)
        S[(iu[1], iu[0])] = S[iu]
        if want_b:
            B[(iu[1], iu[0])] = B[iu]
    return S, B


def entry(a, b, dt=LD, want_b: bool = False):
    """One entry S(a, b) (and B~) for two rectangles a, b = (x0, x1, y0, y1) in mm."""
    R = np.array([a, b], dtype=np.float64)
    S, B = entry_block(R, 0, 1, 1, 2, dt, want_b)
    return (S[0, 0], B[0, 0]) if want_b else S[0, 0]


# --- the c0 derivation (section 4.3) -------------------------------------------------------------

#: Rational upper bounds on the angular maxima used by the derivation. With a = |X|/r,
#: b = |Y|/r (a^2 + b^2 = 1) and asinh(t) <= t:
#:   K_T  >= max 1/2 a^2 b = 1/(3 sqrt 3) = 0.19245..   bounds |t1|/r^3, |t2|/r^3 and 1/2 X^2 Y / r^3
#:   K_12 >= max 1/2 a b (a + b) = 1/(2 sqrt 2) = 0.35355..  bounds (t1 + t2)/r^3
#:   K_F  >= max(1/6, K_12 - 1/6)                     bounds |F|/r^3 (t1, t2 >= 0, so -1/6 <= F/r^3 <= K_12 - 1/6)
#:   K_S  >= 2 max(a b^2 + 1/2 a^2 b, 1/2 a^2) = 2 (0.3849.. + 0.19245..) bounds (|X F_X| + |Y F_Y|)/r^3,
#:          since X F_X = X^2 Y asinh(Y/X) + 1/2 X Y^2 asinh(X/Y) - 1/2 r X^2 and |p - n| <= max(p, n).
#: The tests verify each against dense sampling of the angle.
K_T = Fraction(77, 400)
K_12 = Fraction(221, 625)
K_F = Fraction(187, 1000)
K_S = Fraction(231, 200)


def derive_c0() -> dict:
    """c0 with |S~_ij - S_ij| <= c0 u sum_k r_k^3/(A_i A_j) for every pair, and q_B, from the
    operation sequence of _F and entry_block (section 4.3). Rigorous (not first order): every
    rounding is a factor (1 + theta_k) with |theta_k| <= gamma_k; logl <= 2 ulp, i.e.
    |logl(x) - ln x| <= 4 u ln x for x >= 1; sqrtl correctly rounded.

    1. Inputs. X~ = X(1 + d), |d| <= u (a long-double difference of two float64 values), so
       by the mean-value theorem |F(X~, Y~) - F(X, Y)| <= K_S u r^3 (1 + u)^3 / (1 - u).
    2. Evaluation at the rounded inputs (r below is r(X~, Y~) <= r (1 + u)):
       r~ = r(1 + theta_2) [r2 = r^2(1 + theta_2), sqrt correctly rounded];
       log argument (|Y| + r~)/|X| (1 + theta_4), so ln(arg~) = L + l4 with |l4| <= gamma_4/(1 - gamma_4);
       |logl(arg~) - L| <= 4u L + (1 + 4u) l4;
       t1~ = 1/2 X^2 Y (L + eta)(1 + theta_3), so |t1~ - t1| <= K_T r^3 [gamma_3 + 4u(1 + gamma_3) + (1 + gamma_3)(1 + 4u) l4]; t2 alike;
       r3~/6 = r^3/6 (1 + theta_6);
       F~ = ((t1~ + t2~)(1 + d1) - r3~/6)(1 + d2), so
       |F~ - F(X~,Y~)| <= (e1 + e2)(1 + gamma_2) + gamma_2 K_12 r^3 + gamma_7 r^3/6.
    3. Corner sum from 0 (15 additions): |I~ - sum F~_k| <= gamma_15 sum |F~_k|,
       |F~_k| <= (K_F + c_F u) r_k^3.
    4. Areas A~ = A(1 + theta_3), A~_i A~_j = A_i A_j (1 + theta_7), division (1 + d):
       |S~ - I~/(A_i A_j)| <= |I~|/(A_i A_j) (u + gamma_7)/(1 - gamma_7).
    q_B: r~^3 = r^3 (1 + theta_8) [inputs 2 x 1, squares 1, sum 1, sqrt 1, product 1];
    15 additions of positive terms; the factor c u = 2^-58 is exact; A~_i A~_j (1 + theta_7);
    division (1 + d): B~ >= c u sum r^3/(A_i A_j) (1 - gamma_24)/(1 + gamma_7) >= (1 - gamma_31)(...).
    """
    u = U_LD
    g2, g3, g4, g6, g7, g15 = (gamma(k) for k in (2, 3, 4, 6, 7, 15))
    grow = (1 + u) ** 3                               # r(X~, Y~)^3 <= r^3 (1 + u)^3
    l4 = g4 / (1 - g4)
    e_t = K_T * (g3 + 4 * u * (1 + g3) + (1 + g3) * (1 + 4 * u) * l4)
    e_eval = (2 * e_t * (1 + g2) + g2 * K_12 + g7 / 6) * grow
    e_input = K_S * u * grow / (1 - u)
    c_F = (e_eval + e_input) / u
    per_term = K_F * grow + c_F * u                   # |F~_k| / r_k^3
    e_sum = g15 * per_term
    e_div = per_term * (1 + g15) * (u + g7) / (1 - g7)
    c0 = c_F + (e_sum + e_div) / u
    q_B = 31
    lower = (1 - gamma(24)) / (1 + g7)
    assert lower >= 1 - gamma(q_B)
    return {"c0": c0, "c0_float": float(c0), "q_B": q_B, "c_F": float(c_F),
            "corner_sum_term": float(e_sum / u), "division_term": float(e_div / u),
            "limit": C_ENC * (1 - gamma(q_B)),
            "within_limit": c0 <= C_ENC * (1 - gamma(q_B)),
            "constants": {"K_T": pq(K_T), "K_12": pq(K_12), "K_F": pq(K_F), "K_S": pq(K_S)}}


# --- rounding counts and the enclosure (section 4.3) -----------------------------------------

def m_count(N: int) -> int:
    """m(N) = 2 min(N, 256) + P(N) - 1, P(N) = n_b (n_b + 1)/2, n_b = ceil(N/256)."""
    nb = -(-N // BLOCK)
    return 2 * min(N, BLOCK) + nb * (nb + 1) // 2 - 1


def ld_pass(R: np.ndarray, sigmas: list, *, stop=None) -> dict:
    """The symmetric block-pair long-double pass (section 4.3). For each sigma (float64,
    zero-extended to len(R)) it returns E^ = fl(sigma^T S~ sigma), W^ = fl(sum |s_i| B~_ij |s_j|)
    and G^ = fl(sum |s_i| |S~_ij| |s_j|), each as a long double, formed by: for each block
    pair (I, J), J >= I in a fixed order, t_IJ = s_I^T (M s_J), doubled when J > I, added to an
    accumulator that starts at 0. It also records the smallest nonzero |S~| and B~ and
    whether every B~ is finite and non-negative. ``stop`` (optional) is called between
    block pairs."""
    N = len(R)
    s_ld = [np.asarray(s, dtype=np.float64).astype(LD) for s in sigmas]
    a_ld = [np.abs(s) for s in s_ld]
    E = [LD(0)] * len(s_ld)
    W = [LD(0)] * len(s_ld)
    G = [LD(0)] * len(s_ld)
    min_s = LD(np.inf)
    min_b = LD(np.inf)
    b_ok = True
    s_ok = True
    for i0 in range(0, N, BLOCK):
        i1 = min(N, i0 + BLOCK)
        for j0 in range(i0, N, BLOCK):
            j1 = min(N, j0 + BLOCK)
            if stop is not None:
                stop()
            M, B = entry_block(R, i0, i1, j0, j1, LD, True)
            b_ok &= bool(np.isfinite(B).all() and (B >= 0).all())
            s_ok &= bool(np.isfinite(M).all())
            aM = np.abs(M)
            nz = aM[aM != 0]
            if nz.size:
                min_s = min(min_s, nz.min())
            nzb = B[B != 0]
            if nzb.size:
                min_b = min(min_b, nzb.min())
            f = LD(1) if j0 == i0 else LD(2)
            for k in range(len(s_ld)):
                s, a = s_ld[k], a_ld[k]
                E[k] += f * (s[i0:i1] @ (M @ s[j0:j1]))
                W[k] += f * (a[i0:i1] @ (B @ a[j0:j1]))
                G[k] += f * (a[i0:i1] @ (aM @ a[j0:j1]))
    return {"E": E, "W": W, "G": G, "min_abs_S": min_s, "min_B": min_b, "B_finite_nonneg": b_ok,
            "S_finite": s_ok, "m": m_count(N), "N": N}


def e_up(E, W, G, m: int) -> Fraction:
    """E_up = E^ + (W^ + gamma_m G^)/(1 - gamma_m), exactly (section 4.3)."""
    g = gamma(m)
    return to_fr(E) + (to_fr(W) + g * to_fr(G)) / (1 - g)


def underflow_check(sigmas: list, min_abs_S, min_B) -> dict:
    """The no-underflow requirement of section 4.3, per pass: with s = min nonzero |sigma_i|
    over the pass's sigmas and e = min(|S~|, B~) over nonzero values, s e >= 2^-16300 and
    s^2 e 2^-64 >= 2^-16300."""
    nz = [np.abs(v[v != 0]) for v in sigmas if np.any(v != 0)]
    vals = (min_abs_S, min_B)
    if not nz or not all(np.isfinite(a).all() for a in nz) or not all(finite(v) for v in vals):
        return {"min_abs_sigma": None, "min_abs_S": to_float(min_abs_S), "min_B": to_float(min_B),
                "first_product_bound": None, "second_product_bound_log2": None, "ok": False,
                "reason": "no nonzero sigma, or a non-finite smallest |sigma|, |S~| or B~"}
    s = min(float(a.min()) for a in nz)
    e = min(to_fr(min_abs_S), to_fr(min_B))
    s_f = Fraction(s)
    first = s_f * e
    second = s_f * s_f * e * Fraction(1, 2 ** 64)
    return {"min_abs_sigma": s, "min_abs_S": to_float(min_abs_S), "min_B": to_float(min_B),
            "first_product_bound": to_float(first) if first > 0 else 0.0,
            "second_product_bound_log2": (math.log2(second.numerator) - math.log2(second.denominator)) if second > 0 else None,
            "ok": bool(first >= UNDERFLOW_FLOOR and second >= UNDERFLOW_FLOOR)}


def island_charge(sigma: np.ndarray, n_island: int) -> Fraction:
    """Q = sum over the island panels of sigma_i, exactly (section 4.3)."""
    return sum((Fraction(float(v)) for v in sigma[:n_island]), Fraction(0))


def enclosure(Q: Fraction, E, W, G, m: int, kappa_: Fraction) -> dict:
    """E_up, C_lo = RD(Q^2 kappa/E_up), C~ = Q^2 kappa/E^ and w = C~ - C_lo (section 4.3, K4).
    Not ok, without raising, when E^, W^ or G^ is not finite, W^ or G^ is negative, E^ or E_up
    is not positive (a non-positive energy, section 8), or Q <= 0."""
    fin = all(finite(v) for v in (E, W, G))
    Eup = e_up(E, W, G, m) if fin else None             # exact arithmetic only on finite values
    ok = bool(fin and to_fr(E) > 0 and to_fr(W) >= 0 and to_fr(G) >= 0 and Eup > 0 and Q > 0)
    if not ok:
        return {"ok": False, "E_hat": to_float(E), "W_hat": to_float(W), "G_hat": to_float(G), "m": m,
                "Q": to_float(Q), "E_up_positive": bool(fin and Eup > 0), "E_hat_positive": bool(fin and to_fr(E) > 0)}
    C_lo = rd(Q * Q * kappa_ / Eup)
    C_t = Q * Q * kappa_ / to_fr(E)
    return {"ok": True, "m": m, "gamma_m": pq(gamma(m)), "E_hat_pq": pq(to_fr(E)), "W_hat_pq": pq(to_fr(W)),
            "G_hat_pq": pq(to_fr(G)), "E_up_pq": pq(Eup), "Q_pq": pq(Q), "E_hat": to_float(E), "W_hat": to_float(W),
            "G_hat": to_float(G), "E_up": to_float(Eup), "Q": to_float(Q), "C_lo_fF": C_lo, "C_tilde_fF": to_float(C_t),
            "w_fF": to_float(C_t - Fraction(C_lo)),
            "width_rel": to_float((C_t - Fraction(C_lo)) / Fraction(C_lo)) if C_lo > 0 else None}


# --- float64 assembly, the trial vector and its fallbacks (section 4.5) ------------------------

def assemble64(R: np.ndarray, bs: int = 512) -> np.ndarray:
    """S64: the full symmetric float64 matrix, F-ordered, from the float64 routine; each value
    for i <= j is computed once and mirrored, so the two triangles are identical."""
    N = len(R)
    S = np.empty((N, N), order="F")
    for i0 in range(0, N, bs):
        i1 = min(N, i0 + bs)
        for j0 in range(i0, N, bs):
            j1 = min(N, j0 + bs)
            b, _ = entry_block(R, i0, i1, j0, j1, np.float64)
            S[i0:i1, j0:j1] = b
            if j0 != i0:
                S[j0:j1, i0:i1] = b.T
    return S


def restore_upper(S: np.ndarray, d: np.ndarray, scale=None, shift: float = 0.0, bs: int = 512) -> None:
    """Rebuild the upper triangle and diagonal of S from its untouched strict lower triangle
    and the saved diagonal d, optionally Jacobi-scaled (scale = D^-1/2) and shifted. The
    strict lower triangle is never written (LAPACK potrf with uplo='U' does not reference it)."""
    N = S.shape[0]
    for j0 in range(0, N, bs):
        j1 = min(N, j0 + bs)
        if j0:
            U = S[j0:j1, :j0].T
            if scale is not None:
                U = U * scale[:j0, None] * scale[None, j0:j1]
            S[:j0, j0:j1] = U
        Dblk = S[j0:j1, j0:j1]
        Lb = np.tril(Dblk, -1)
        full = Lb + Lb.T
        full[np.diag_indices(j1 - j0)] = d[j0:j1]
        if scale is not None:
            full = full * scale[j0:j1, None] * scale[None, j0:j1]
        full[np.diag_indices(j1 - j0)] += shift
        iu = np.triu_indices(j1 - j0)
        Dblk[iu] = full[iu]


def energy64(S: np.ndarray, d: np.ndarray, sigma: np.ndarray, bs: int = 512) -> float:
    """sigma^T S64 sigma in float64, from the untouched strict lower triangle and the saved
    diagonal (check (g), section 4.5)."""
    N = S.shape[0]
    y = np.zeros(N)
    for i0 in range(0, N, bs):
        i1 = min(N, i0 + bs)
        if i0:
            y[i0:i1] += S[i0:i1, :i0] @ sigma[:i0]
        y[i0:i1] += np.tril(S[i0:i1, i0:i1], -1) @ sigma[i0:i1]
    return float(d @ (sigma * sigma) + 2.0 * (sigma @ y))


def principal_from_lower(S: np.ndarray, n: int, d: np.ndarray, bs: int = 512) -> np.ndarray:
    """A new F-ordered full symmetric n x n matrix: the leading principal submatrix of S64,
    read from S's strict lower triangle and d (valid after S has been factorised in place)."""
    X = np.empty((n, n), order="F")
    for j0 in range(0, n, bs):
        j1 = min(n, j0 + bs)
        X[j0:n, j0:j1] = S[j0:n, j0:j1]
        if j0:
            X[:j0, j0:j1] = S[j0:j1, :j0].T
        Dblk = X[j0:j1, j0:j1]
        Lb = np.tril(Dblk, -1)
        full = Lb + Lb.T
        full[np.diag_indices(j1 - j0)] = d[j0:j1]
        Dblk[...] = full
    return X


#: the fallback steps of section 4.5, in order; forced failures exist only for the
#: Confirmation's forced-fallback run (never in the attempt)
FALLBACK_STEPS = ("cholesky", "jacobi_scaled", "shift_2^-40", "shift_2^-30", "shift_2^-20")
_SHIFTS = {"shift_2^-40": 2.0 ** -40, "shift_2^-30": 2.0 ** -30, "shift_2^-20": 2.0 ** -20}


class LastResortInvalid(NumericsError):
    """The last-resort sigma = D^-1 1_island is not finite or has Q <= 0 (UNQUALIFIED)."""


def solve_sigma(S: np.ndarray, n_island: int, *, force_fail: int = 0) -> dict:
    """The trial vector of section 4.5, from S64 (F-ordered, full symmetric; its upper
    triangle is overwritten, its strict lower triangle kept). A step fails if its
    factorisation fails, if sigma is not finite, or if Q <= 0. ``force_fail`` makes the first
    ``force_fail`` factorisations count as failed (Confirmation only)."""
    if not (S.flags.f_contiguous and S.dtype == np.float64 and S.shape[0] == S.shape[1]):
        raise NumericsError("S64 must be a square F-ordered float64 array")
    N = S.shape[0]
    d = np.diag(S).copy()
    rhs = np.zeros(N)
    rhs[:n_island] = 1.0
    attempts = []
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = 1.0 / np.sqrt(d)
    for idx, step in enumerate(FALLBACK_STEPS):
        scaled = step != "cholesky"
        if idx > 0:
            if not np.isfinite(scale).all():
                attempts.append({"step": step, "failed": "the diagonal is not positive and finite"})
                continue
            tau = 0.0
            if step in _SHIFTS:
                tau = _SHIFTS[step] * float(np.max(d * scale * scale))
            restore_upper(S, d, scale, tau)
        try:
            c, low = sla.cho_factor(S, lower=False, overwrite_a=True, check_finite=False)
            in_place = bool(np.shares_memory(c, S))
            if idx < force_fail:
                raise np.linalg.LinAlgError("forced failure (Confirmation only)")
            y = sla.cho_solve((c, low), rhs * scale if scaled else rhs, check_finite=False)
            sigma = y * scale if scaled else y
            if not np.isfinite(sigma).all():
                attempts.append({"step": step, "failed": "sigma is not finite"})
                continue
            Q = island_charge(sigma, n_island)
            if Q <= 0:
                attempts.append({"step": step, "failed": "Q <= 0"})
                continue
            dg = np.abs(np.diag(c))
            attempts.append({"step": step, "failed": None})
            return {"sigma": sigma, "path": step, "d": d, "Q": Q, "in_place": in_place,
                    "pivot_ratio_squared": float((dg.min() / dg.max()) ** 2), "attempts": attempts}
        except np.linalg.LinAlgError as exc:
            attempts.append({"step": step, "failed": f"factorisation: {exc}"})
    with np.errstate(divide="ignore", invalid="ignore"):
        sigma = np.where(rhs > 0, rhs / d, 0.0)
    if not np.isfinite(sigma).all():
        raise LastResortInvalid("the last-resort sigma is not finite")
    Q = island_charge(sigma, n_island)
    if Q <= 0:
        raise LastResortInvalid("the last-resort sigma has Q <= 0")
    attempts.append({"step": "last_resort", "failed": None})
    return {"sigma": sigma, "path": "last_resort", "d": d, "Q": Q, "in_place": None,
            "pivot_ratio_squared": None, "attempts": attempts}


def check_g(Q: Fraction, E64: float, E_hat, C_lo: float, kappa_: Fraction) -> dict:
    """Check (g) of section 4.5: |C64 - C~| <= 1e-7 C_lo, with C64 = Q^2 kappa/(sigma^T S64 sigma)
    and C~ = Q^2 kappa/E^. The enclosure width is not part of it."""
    if not (finite(E64) and E64 > 0):
        return {"ok": False, "E64": E64, "reason": "sigma^T S64 sigma is not finite and positive"}
    if not (finite(E_hat) and to_fr(E_hat) > 0 and finite(C_lo) and C_lo >= 0):
        return {"ok": False, "E64": E64, "reason": "E^ is not finite and positive, or C_lo is not finite"}
    C64 = Q * Q * kappa_ / Fraction(E64)
    Ct = Q * Q * kappa_ / to_fr(E_hat)
    lhs = abs(C64 - Ct)
    return {"ok": bool(lhs <= Fraction(1, 10 ** 7) * Fraction(C_lo)), "E64": E64, "C64_fF": to_float(C64),
            "C_tilde_fF": to_float(Ct), "rel": to_float(lhs / Fraction(C_lo)) if C_lo > 0 else None,
            "g_E": to_float(abs(Fraction(E64) - to_fr(E_hat)) / to_fr(E_hat))}


# --- probes (section 4.4) -------------------------------------------------------------------

def _rn64(x: Fraction) -> Fraction:
    """x rounded to nearest (ties to even) with a 64-bit significand."""
    if x == 0:
        return x
    s = -1 if x < 0 else 1
    a = abs(x)
    e = a.numerator.bit_length() - a.denominator.bit_length()
    while Fraction(2) ** e > a:
        e -= 1
    while Fraction(2) ** (e + 1) <= a:
        e += 1
    q = a / Fraction(2) ** (e - 63)                   # in [2^63, 2^64)
    n, rem = divmod(q.numerator, q.denominator)
    frac = Fraction(rem, q.denominator)
    if frac > Fraction(1, 2) or (frac == Fraction(1, 2) and n % 2 == 1):
        n += 1
    return s * Fraction(n) * Fraction(2) ** (e - 63)


def arithmetic_probe() -> dict:
    """+, -, x and / on np.longdouble arrays must reproduce the round-to-nearest 64-bit
    significand result, computed exactly (section 4.4). s = 1 + 2^-63 is formed by a
    long-double addition at run time; s - 1 = 2^-63 and s*s = 1 + 2^-62 detect a 53-bit
    precision-control word."""
    one = np.array([1.0], dtype=LD)
    tiny = np.array([2.0], dtype=LD) ** -63
    s = one + tiny
    cases = {"s - 1 == 2^-63": to_fr((s - one)[0]) == Fraction(1, 2 ** 63),
             "s * s == 1 + 2^-62": to_fr((s * s)[0]) == 1 + Fraction(1, 2 ** 62)}
    a = np.array([1, 3, 7, 1e-300, 1e300, 2.0 ** -40, 12345.678, -2.5], dtype=LD) / np.array([3], dtype=LD)
    b = np.array([7, 11, 2.0 ** -63, 5e-301, 3e299, 1 + 2.0 ** -52, 0.1, 9], dtype=LD) * np.array([1.0000001], dtype=LD)
    fa = [to_fr(v) for v in a]
    fb = [to_fr(v) for v in b]
    ops = {"add": (a + b, [x + y for x, y in zip(fa, fb)]), "sub": (a - b, [x - y for x, y in zip(fa, fb)]),
           "mul": (a * b, [x * y for x, y in zip(fa, fb)]), "div": (a / b, [x / y for x, y in zip(fa, fb)])}
    for name, (got, exact) in ops.items():
        cases[name] = all(to_fr(g) == _rn64(e) for g, e in zip(got, exact))
    return {"cases": cases, "ok": all(cases.values())}


def dispatch_probe(n: int = 3000) -> dict:
    """np.log and np.sqrt on long-double arrays against libm logl and sqrtl through ctypes,
    with arguments built from the 80-bit bytes, compared on the first 10 bytes (section 4.4)."""
    libm = ctypes.CDLL("libm.so.6")

    class LDc(ctypes.c_longdouble):
        pass

    libm.logl.restype = LDc
    libm.logl.argtypes = [LDc]
    libm.sqrtl.restype = LDc
    libm.sqrtl.argtypes = [LDc]
    xs = (np.geomspace(LD("1e-300"), LD("1e300"), n, dtype=LD)
          * (LD(1) + np.arange(n, dtype=LD) * LD(2) ** -62))
    # as the entry routine calls them: on 2-D long-double arrays (and on 1-D arrays)
    shape2 = (n // 3, 3)
    nl = [np.log(xs), np.log(xs[: shape2[0] * 3].reshape(shape2)).ravel()]
    ns_ = [np.sqrt(xs), np.sqrt(xs[: shape2[0] * 3].reshape(shape2)).ravel()]
    mismatches = 0
    for i in range(n):
        arg = LDc.from_buffer_copy(np.array([xs[i]], dtype=LD).tobytes())
        lg = bytes(libm.logl(arg))[:10]
        sq = bytes(libm.sqrtl(arg))[:10]
        for got_l, got_s in zip(nl, ns_):
            if i < len(got_l):
                mismatches += (np.array([got_l[i]], dtype=LD).tobytes()[:10] != lg)
                mismatches += (np.array([got_s[i]], dtype=LD).tobytes()[:10] != sq)
    not_float64 = int(sum(LD(float(x)) != x for x in xs))
    return {"inputs": n, "inputs_not_representable_in_float64": not_float64,
            "mismatches": int(mismatches), "ok": bool(mismatches == 0 and not_float64 > 0)}


def longdouble_facts() -> dict:
    fi = np.finfo(LD)
    return {"nmant": int(fi.nmant), "itemsize": int(np.dtype(LD).itemsize),
            "libc": platform.libc_ver()}
