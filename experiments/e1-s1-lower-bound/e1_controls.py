# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""E1 synthetic known-answer and negative controls K1, K2, K2b, K3, N3 and N4, exactly as the
frozen contract E1-CONTRACT.rev8.5.md specifies them in section 5. SYNTHETIC GEOMETRY ONLY:
nothing here reads the S1 mesh. (N1, N2, N3b and N3c need S1 geometry and live in
e1_geometry.geometry_phase; K4 needs the S1 enclosures and lives in the driver.)

Every control is evaluated as isfinite(value) and <inequality>; a non-finite quantity fails the
control (UNQUALIFIED) and never raises: finiteness is checked before any exact conversion, a
recorded value outside the float64 range becomes +-inf (and fails), and a last-resort sigma that
is not finite or has Q <= 0 inside K3 or N3 fails that control.
"""
from __future__ import annotations

import hashlib
import json
import math
import warnings
from decimal import Decimal, localcontext
from fractions import Fraction

import numpy as np
from scipy import integrate

import e1_numerics as nm
from e1_geometry import island_nodes

LD = nm.LD
UM = 1e-3                                     # one micrometre in mm
#: the 47-significant-digit K1 reference, as an exact rational
K1_REFERENCE = Fraction(Decimal("2.9732095982473787025281856676395717980197454792"))
#: K3's frozen D (fF): the correctly rounded exact product 8 x Fraction(8.854187817620389e-12) x 1e-4 x 1e15
K3_D_FF = 7.083350254096311
K2B_SEED = 20260923
#: t with F(1, t) = 0 (the F-zero lines of K2b)
F_ZERO_T = 0.3975553878545899
#: the sha256 of the K2b pair list (canonical JSON of float64 corners), frozen with the code
K2B_PAIRS_SHA256 = "9f47657181725147b14f3c2d05034d9bbde2d9f5e2f7419fcf9704cf38a6cb9e"


def _fin(v) -> bool:
    return v is not None and math.isfinite(nm.to_float(v))


def smin() -> float:
    """The selected configuration's smallest island panel side (mm)."""
    return float(np.diff(island_nodes(32, 3.5)).min())


H_MIN = float(Fraction(1, 800))               # the base lattice step, 1.25 um in mm


# --- references --------------------------------------------------------------------------------

def _F_dec(X: Decimal, Y: Decimal):
    X, Y = abs(X), abs(Y)
    r = (X * X + Y * Y).sqrt()
    t1 = Decimal(0) if X == 0 or Y == 0 else X * X * Y * ((Y + r) / X).ln() / 2
    t2 = Decimal(0) if X == 0 or Y == 0 else X * Y * Y * ((X + r) / Y).ln() / 2
    return t1 + t2 - r * r * r / 6, r * r * r


def reference_dec(a, b, prec: int = 60):
    """S(a, b) and sum_k r_k^3/(A_a A_b) in ``prec``-digit decimal from the float64 corners."""
    with localcontext() as ctx:
        ctx.prec = prec
        s = Decimal(0)
        r3 = Decimal(0)
        for p, xa in ((1, a[0]), (2, a[1])):
            for q, xb in ((1, b[0]), (2, b[1])):
                for u_, ya in ((1, a[2]), (2, a[3])):
                    for v, yb in ((1, b[2]), (2, b[3])):
                        f, rr = _F_dec(Decimal(xa) - Decimal(xb), Decimal(ya) - Decimal(yb))
                        s += (-1) ** (p + q + u_ + v) * f
                        r3 += rr
        AA = ((Decimal(a[1]) - Decimal(a[0])) * (Decimal(a[3]) - Decimal(a[2]))
              * (Decimal(b[1]) - Decimal(b[0])) * (Decimal(b[3]) - Decimal(b[2])))
        return s / AA, r3 / AA


def _phi(a, x, y) -> float:
    """The cancellation-free potential of a uniformly charged rectangle a at (x, y)."""
    s = 0.0
    for sx, xa in ((-1, a[0]), (1, a[1])):
        for sy, ya in ((-1, a[2]), (1, a[3])):
            X = x - xa
            Y = y - ya
            t = 0.0
            if X != 0:
                t += X * math.asinh(Y / abs(X))
            if Y != 0:
                t += Y * math.asinh(X / abs(Y))
            s += sx * sy * t
    return s


def quadrature(a, b) -> dict:
    """scipy dblquad (epsabs = 0, epsrel = 1e-12) over b of the potential of a, per unit areas.
    IntegrationWarnings are counted and recorded, never raised or hidden."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        v, err = integrate.dblquad(lambda y, x: _phi(a, x, y), b[0], b[1], b[2], b[3], epsabs=0, epsrel=1e-12)
    A = (a[1] - a[0]) * (a[3] - a[2])
    B = (b[1] - b[0]) * (b[3] - b[2])
    return {"value": v / (A * B), "error_estimate": err / (A * B), "warnings": len(w)}


# --- K1 ---------------------------------------------------------------------------------------

def _rel_to_reference(v, ref: Fraction):
    """|v - ref|/ref exactly for a finite v; None (a failure) for a non-finite one."""
    return nm.to_float(abs(nm.to_fr(v) - ref) / ref) if nm.finite(v) else None


def k1() -> dict:
    sq = (0.0, 1.0, 0.0, 1.0)
    rel_ld = _rel_to_reference(nm.entry(sq, sq, LD), K1_REFERENCE)
    rel_64 = _rel_to_reference(nm.entry(sq, sq, np.float64), K1_REFERENCE)
    ok = _fin(rel_ld) and rel_ld <= 1e-17 and _fin(rel_64) and rel_64 <= 1e-13
    return {"rel_long_double": rel_ld, "rel_float64": rel_64, "pass": bool(ok)}


# --- K2 and N4 --------------------------------------------------------------------------------

def k2_pairs() -> list:
    """The 24 fixed pairs (mm): four contact cases, then twenty separated pairs."""
    pairs = [("contained", (3 * UM, 4 * UM, 2 * UM, 3 * UM), (0.0, 20 * UM, 0.0, 20 * UM)),
             ("partial overlap", (0.0, 5 * UM, 0.0, 5 * UM), (4 * UM, 14 * UM, 2 * UM, 12 * UM)),
             ("edge-sharing", (20 * UM, 21 * UM, 0.0, 1 * UM), (0.0, 20 * UM, 0.0, 20 * UM)),
             ("corner-sharing", (0.0, 5 * UM, 0.0, 5 * UM), (5 * UM, 10 * UM, 5 * UM, 10 * UM))]
    s = smin()
    for name, s1, s2 in (("s_min/s_min", s, s), ("40/40", 40 * UM, 40 * UM),
                         ("h_min/40", H_MIN, 40 * UM), ("s_min/h_min", s, H_MIN)):
        h = min(s1, s2)
        for g in (0.5, 1, 2, 10, 100):
            pairs.append((f"{name} gap {g}h", (0.0, s1, -s1 / 2, s1 / 2),
                          (s1 + g * h, s1 + g * h + s2, -s2 / 2, s2 / 2)))
    return pairs


def k2(routine=None, quad_refs: list | None = None) -> dict:
    """K2: long double against quadrature <= 1e-9 relative and float64 against long double
    <= 1e-6 relative on every pair. ``routine`` replaces the long-double entry routine (N4)."""
    rows = []
    ok = True
    refs = []
    for k, (name, a, b) in enumerate(k2_pairs()):
        q = quad_refs[k] if quad_refs is not None else quadrature(a, b)
        refs.append(q)
        vld = float(routine(a, b)) if routine is not None else float(nm.entry(a, b, LD))
        v64 = float(nm.entry(a, b, np.float64))
        with np.errstate(all="ignore"):
            rel_q = float(np.float64(abs(vld - q["value"])) / np.float64(abs(vld))) if vld != 0 else math.inf
            rel_64 = float(np.float64(abs(v64 - vld)) / np.float64(abs(vld))) if vld != 0 else math.inf
            est = float(np.float64(abs(q["error_estimate"])) / np.float64(abs(q["value"])))
        good = _fin(rel_q) and rel_q <= 1e-9 and _fin(rel_64) and rel_64 <= 1e-6
        ok &= good
        rows.append({"pair": name, "a": list(a), "b": list(b), "rel_ld_vs_quad": rel_q, "rel_f64_vs_ld": rel_64,
                     "quad_warnings": q["warnings"], "quad_error_estimate_rel": est, "pass": bool(good)})
    return {"pairs": rows, "max_rel_ld_vs_quad": max(r["rel_ld_vs_quad"] for r in rows),
            "max_rel_f64_vs_ld": max(r["rel_f64_vs_ld"] for r in rows),
            "quad_warnings_total": sum(r["quad_warnings"] for r in rows), "pass": bool(ok), "_refs": refs}


def n4_routine(a, b):
    """The broken entry routine of N4: centroid distance 0 < d <= max(h_i, h_j) -> A_i A_j/d,
    and d = 0 -> A_i A_j/max(h_i, h_j) (per unit areas, i.e. 1/d and 1/max h); else unchanged."""
    ca = ((a[0] + a[1]) / 2, (a[2] + a[3]) / 2)
    cb = ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2)
    d = math.hypot(ca[0] - cb[0], ca[1] - cb[1])
    h = max(a[1] - a[0], a[3] - a[2], b[1] - b[0], b[3] - b[2])
    if d == 0:
        return 1.0 / h
    if d <= h:
        return 1.0 / d
    return nm.entry(a, b, LD)


def n4(k2_result: dict) -> dict:
    broken = k2(routine=n4_routine, quad_refs=k2_result["_refs"])
    return {"broken_routine_fails_K2": not broken["pass"],
            "pairs_failing": sum(1 for r in broken["pairs"] if not r["pass"]),
            "pass": bool(not broken["pass"] and k2_result["pass"])}


# --- K2b ----------------------------------------------------------------------------------------

def k2b_side_classes() -> list:
    s = island_nodes(32, 3.5)
    island = [float(s[k + 1 + 16] - s[k + 16]) for k in range(16)]
    ground = [float(Fraction(k, 800)) for k in (1, 2, 4, 8, 16, 32)]
    cls = sorted(set(island + ground))
    if len(cls) != 22:
        raise RuntimeError(f"K2b: expected 22 side classes, found {len(cls)}")
    return cls


def k2b_pairs() -> list:
    """Exactly 10,000 seeded pairs and 96 F-zero pairs (section 5, K2b)."""
    cls = k2b_side_classes()
    D = 0.96 * math.sqrt(2)
    rng = np.random.default_rng(K2B_SEED)
    ix = rng.integers(0, len(cls), size=(10000, 4))
    dd = rng.uniform(0, D, 10000)
    th = rng.uniform(0, 2 * math.pi, 10000)
    cx, cy = -0.6, 0.0
    pairs = []
    for k in range(10000):
        wi, hi, wj, hj = (cls[i] for i in ix[k])
        bx = cx + dd[k] * math.cos(th[k])
        by = cy + dd[k] * math.sin(th[k])
        pairs.append(((cx - wi / 2, cx + wi / 2, cy - hi / 2, cy + hi / 2),
                      (bx - wj / 2, bx + wj / 2, by - hj / 2, by + hj / 2)))
    s = smin()
    # log-spaced with libm pow, not np.geomspace (numpy's float64 power and log10 dispatch to
    # CPU-dependent SIMD code, which would make the frozen pair-list sha256 host-dependent)
    for d in [0.05 * math.pow(D / 0.05, k / 23) for k in range(23)] + [D]:
        X = float(d) / math.sqrt(1 + F_ZERO_T * F_ZERO_T)
        Y = F_ZERO_T * X
        for side in (s, float(Fraction(32, 800))):
            for px, py in ((X, Y), (Y, X)):
                pairs.append(((cx - side / 2, cx + side / 2, cy - side / 2, cy + side / 2),
                              (cx + px - side / 2, cx + px + side / 2, cy + py - side / 2, cy + py + side / 2)))
    return pairs


def k2b_pairs_sha256(pairs: list) -> str:
    return hashlib.sha256(json.dumps([[list(a), list(b)] for a, b in pairs]).encode()).hexdigest()


def k2b(c0: Fraction) -> dict:
    pairs = k2b_pairs()
    sha = k2b_pairs_sha256(pairs)
    u = Decimal(1) / Decimal(2 ** 64)
    c0_dec = Decimal(c0.numerator) / Decimal(c0.denominator)
    viol_b = viol_c0 = overlapping = nonfinite = 0
    implied_max = 0.0
    for a, b in pairs:
        if max(a[0], b[0]) < min(a[1], b[1]) and max(a[2], b[2]) < min(a[3], b[3]):
            overlapping += 1
        S, B = nm.entry(a, b, LD, want_b=True)
        if not (nm.finite(S) and nm.finite(B)):
            nonfinite += 1                           # a non-finite entry or bound fails both criteria
            viol_b += 1
            viol_c0 += 1
            continue
        with localcontext() as ctx:
            ctx.prec = 60
            ref, r3AA = reference_dec(a, b, 60)
            fs = nm.to_fr(S)
            fb = nm.to_fr(B)
            err = abs(Decimal(fs.numerator) / Decimal(fs.denominator) - ref)
            bnd = Decimal(fb.numerator) / Decimal(fb.denominator)
            if not err <= bnd:
                viol_b += 1
            if not err <= c0_dec * u * r3AA:
                viol_c0 += 1
            implied_max = max(implied_max, float(err / (u * r3AA)))
    ok = viol_b == 0 and viol_c0 == 0 and len(pairs) == 10096 and _fin(implied_max)
    frozen = sha == K2B_PAIRS_SHA256
    return {"pairs": len(pairs), "overlapping_pairs": overlapping, "pair_list_sha256": sha,
            "pair_list_matches_frozen": frozen, "violations_of_B": viol_b, "violations_of_c0_bound": viol_c0,
            "non_finite_pairs": nonfinite,
            "largest_implied_constant": implied_max, "c0": float(c0), "pass": bool(ok and frozen)}


# --- K3 and N3 -----------------------------------------------------------------------------------

def disk(n: int, a: float = 0.1) -> np.ndarray:
    """The staircase disk: lattice lines x = i a/n, y = j a/n through the centre; a square is a
    panel iff all four corners satisfy x^2 + y^2 <= a^2."""
    P = []
    for i in range(-n, n):
        for j in range(-n, n):
            xs = (i * a / n, (i + 1) * a / n)
            ys = (j * a / n, (j + 1) * a / n)
            if all(x * x + y * y <= a * a for x in xs for y in ys):
                P.append((xs[0], xs[1], ys[0], ys[1]))
    return np.array(P, dtype=np.float64)


def certify_single(R: np.ndarray, kappa_: Fraction) -> dict:
    """The E1 certificate for one synthetic set whose panels are all charged (island = all),
    through the same routines as the attempt: S64, sigma with fallbacks, the long-double pass,
    E_up and C_lo, with the section 4.3 requirements (B~ finite and non-negative, the
    no-underflow requirement). An invalid last-resort sigma or a failed requirement gives
    ok = False and no C_lo, never an exception."""
    S = nm.assemble64(R)
    try:
        sol = nm.solve_sigma(S, len(R))
    except nm.LastResortInvalid as exc:
        return {"N": len(R), "path": "last_resort_invalid", "m": nm.m_count(len(R)), "ok": False, "reason": str(exc)}
    del S
    p = nm.ld_pass(R, [sol["sigma"]])
    uf = nm.underflow_check([sol["sigma"]], p["min_abs_S"], p["min_B"])
    enc = nm.enclosure(sol["Q"], p["E"][0], p["W"][0], p["G"][0], p["m"], kappa_)
    reqs = {"B_finite_nonnegative": p["B_finite_nonneg"], "no_underflow": uf["ok"], "enclosure_ok": enc["ok"]}
    out = {"N": len(R), "path": sol["path"], "m": p["m"], **enc, "requirements": reqs}
    if not all(reqs.values()):
        out["ok"] = False
        out.pop("C_lo_fF", None)
    return out


def k3(kappa_free: Fraction) -> dict:
    d32, d16 = disk(32), disk(16)
    r32, r16 = certify_single(d32, kappa_free), certify_single(d16, kappa_free)
    c32 = r32.get("C_lo_fF") if r32.get("ok") else None
    c16 = r16.get("C_lo_fF") if r16.get("ok") else None
    ratio = c32 / K3_D_FF if _fin(c32) else None
    ok = (len(d32) == 3080 and len(d16) == 732 and _fin(ratio) and 0.97 <= ratio <= 1
          and _fin(c16) and c16 <= c32)
    return {"panels_a_over_32": len(d32), "panels_a_over_16": len(d16), "C_lo_a_over_32_fF": c32,
            "C_lo_a_over_16_fF": c16, "ratio_to_D": ratio, "D_fF": K3_D_FF, "m": [r32["m"], r16["m"]],
            "paths": [r32["path"], r16["path"]], "pass": bool(ok)}


def n3(kappa_free: Fraction, epsilon0: float, a: float = 0.1, n: int = 16) -> dict:
    """A plate filling the cross-section of an a x a box (Neumann side walls and lid, grounded
    floor at d = 10a) has exact capacitance eps0 a/10. The free-space Galerkin value must
    exceed it by more than 10x (the bound needs grounded walls)."""
    R = np.array([(a * i / n, a * (i + 1) / n, a * j / n, a * (j + 1) / n) for i in range(n) for j in range(n)])
    c_exact = float(Fraction(epsilon0) * Fraction(a) / 1000 / 10 * 10 ** 15)
    S = nm.assemble64(R)
    try:
        sol = nm.solve_sigma(S, len(R))
    except nm.LastResortInvalid as exc:
        return {"C_galerkin_free_space_fF": None, "C_exact_fF": c_exact, "ratio": None, "reason": str(exc),
                "pass": False}
    S = nm.assemble64(R)
    with np.errstate(all="ignore"):
        E64 = float(sol["sigma"] @ S @ sol["sigma"])
    if not (nm.finite(E64) and E64 > 0):
        return {"C_galerkin_free_space_fF": None, "C_exact_fF": c_exact, "ratio": None,
                "reason": "sigma^T S sigma is not finite and positive", "pass": False}
    c_gal = nm.to_float(sol["Q"] * sol["Q"] * kappa_free / Fraction(E64))
    ratio = c_gal / c_exact
    return {"C_galerkin_free_space_fF": c_gal, "C_exact_fF": c_exact, "ratio": ratio,
            "pass": bool(_fin(ratio) and ratio > 10)}


def control_numeric_sets() -> dict:
    """Every panel set on which a synthetic control forms an entry, a matrix or an energy: K1's
    unit square (its self entry), the K2/N4 pairs, the K2b pairs, K3's two disks and N3's plate.
    The rehearsal and the Confirmation check them against the S1 attempt sets before any
    control numerics (section 3.2 item 2 separation)."""
    out = {"K1 unit square": np.array([(0.0, 1.0, 0.0, 1.0)])}
    for k, (name, a, b) in enumerate(k2_pairs()):
        out[f"K2/N4 pair {k} ({name})"] = np.array([a, b], dtype=np.float64)
    for k, (a, b) in enumerate(k2b_pairs()):
        out[f"K2b pair {k}"] = np.array([a, b], dtype=np.float64)
    out["K3 disk a/32"] = disk(32)
    out["K3 disk a/16"] = disk(16)
    a, n = 0.1, 16
    out["N3 plate"] = np.array([(a * i / n, a * (i + 1) / n, a * j / n, a * (j + 1) / n)
                                for i in range(n) for j in range(n)], dtype=np.float64)
    return out


def synthetic_controls(c0: Fraction, epsilon0: float, stop=None) -> dict:
    """K1, K2, K2b, K3, N3 and N4, in that order."""
    kf = Fraction(nm.KAPPA_FREE_PQ)
    out = {"K1": k1()}
    if stop:
        stop()
    kk2 = k2()
    out["K2"] = {k: v for k, v in kk2.items() if k != "_refs"}
    out["N4"] = n4(kk2)
    if stop:
        stop()
    out["K2b"] = k2b(c0)
    if stop:
        stop()
    out["K3"] = k3(kf)
    out["N3"] = n3(kf, epsilon0)
    out["failures"] = [k for k, v in out.items() if isinstance(v, dict) and not v.get("pass")]
    return out
