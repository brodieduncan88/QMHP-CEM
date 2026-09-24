# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""E1 geometry: the S1 model checks, the island, the R1 cut, the lattice candidates, the
panel merge and exact containment, exactly as the frozen contract E1-CONTRACT.rev8.5.md
specifies them in sections 3.1, 3.3, 4.1 and 4.2. GEOMETRY AND TAGS ONLY: nothing here
assembles a matrix or computes a capacitance.

The panel-merge rule (merge) and the island node formula (island_nodes) are the ones the
configuration-selection study used; the selection manifest (sha256 e1b85e0c...) records
them. The candidate and containment routines are ported from its reviewed scripts
(s1cells048.py, s1panels_sel.py) without change to their arithmetic.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from fractions import Fraction as Fr

import numpy as np
from scipy.ndimage import distance_transform_cdt
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

#: the frozen configuration (section 3.2, "Frozen configuration")
CONFIG = {"n": 32, "q": 3.5, "h_um": 1.25, "per_mm": 800, "w_mm": 0.48, "kappa": 1.25,
          "blocks": (32, 16, 8, 4, 2), "shrink_mm": 1e-9, "centre": (-0.6, 0.0),
          "island_half_mm": 0.075, "island_inset_mm": 1e-12}
#: the expected counts of section 3.3 (and the geometric facts of section 3.1)
EXPECTED = {
    "island_triangles": 283, "island_nodes": 189,
    "island_bbox": [-0.6749999999999999, -0.5249999999999999, -0.07500000000000001, 0.075],
    "island_area_mm2": 0.022500000000000003,
    "attr4_components": 2,
    "r1_cut_edges": 8, "r1_cut_nodes": 9, "r1_components": [5531, 5610], "r1_triangles": 5531,
    "cells_5um": 36864, "candidates": 33394, "cells_in_r1": 1152, "cells_island_full": 900,
    "cells_no_metal": 2570, "cells_partial": 0,
    "ground_panels": 8971,
    "ground_by_side_um": {"1.25": 5264, "2.5": 1316, "5.0": 1376, "10.0": 352, "20.0": 260, "40.0": 403},
    "ground_on_r1": 3285, "ground_straddling": 0, "ground_excl_r1": 5686,
    "N_E1_2": 9995, "N_E1_2_excl_R1": 6710, "N_E1_1": 1024, "N_E1_1_half": 256,
    "contained_island": 1024, "contained_ground": 8971, "contained_excl": 5686, "contained_half": 256,
}
BOX = (Fr(-2), Fr(2), Fr(-2), Fr(2), Fr(-0.43), Fr(1.5))
R1_SEED_POINT = (Fr(-0.455), Fr(0))


# --- island nodes and the merge rule (the selection study's, unchanged) ---------------------

def island_nodes(n: int = 32, q: float = 3.5, half: float = 0.075, inset: float = 1e-12) -> np.ndarray:
    """s_k = sign(k) (half - inset) (1 - (1 - |k|/(n/2))^q), k = -n/2..n/2, each once in float64
    in exactly this order. The power is libm pow (math.pow), not numpy's vectorised power,
    whose SIMD dispatch depends on the CPU; on the execution host the two agree for every
    node (the tests check it against the vectorised form the selection study used)."""
    m = n // 2
    return np.array([float(np.sign(k)) * (half - inset) * (1 - math.pow(1 - abs(k) / m, q))
                     for k in range(-m, m + 1)], dtype=np.float64)


def island_panels(n: int = 32, q: float = 3.5, step: int = 1) -> np.ndarray:
    """The n x n tensor cells (step 1), or the nested (n/2)^2 grid of even k (step 2), at
    x_k = -0.6 + s_k, y_k = s_k (mm), i-major."""
    s = island_nodes(n, q)[::step]
    x = -0.6 + s
    y = s
    m = len(s) - 1
    return np.array([(x[i], x[i + 1], y[j], y[j + 1]) for i in range(m) for j in range(m)], dtype=np.float64)


def upsample(M: np.ndarray, f: int) -> np.ndarray:
    return np.repeat(np.repeat(M, f, 0), f, 1)


def merge(C: np.ndarray, gi0: int, gj0: int, kappa: float, sizes) -> tuple[list, np.ndarray]:
    """Blocks of m x m base cells (largest m first), aligned to global multiples of m, all
    candidate, unused and with chessboard distance d >= kappa m to the nearest non-candidate
    cell of the window (scipy distance_transform_cdt; cells outside the window do not count).
    Every remaining candidate base cell becomes a panel. Returns (a0, a1, b0, b1) index boxes."""
    d = distance_transform_cdt(C, metric="chessboard")
    used = np.zeros_like(C)
    P = []
    nI, nJ = C.shape
    for m in sizes:
        a_start = (-gi0) % m
        b_start = (-gj0) % m
        thr = kappa * m
        for a in range(a_start, nI - m + 1, m):
            for b in range(b_start, nJ - m + 1, m):
                blk = C[a:a + m, b:b + m]
                if blk.all() and not used[a:a + m, b:b + m].any() and (d[a:a + m, b:b + m] >= thr).all():
                    used[a:a + m, b:b + m] = True
                    P.append((a, a + m, b, b + m))
    for a, b in np.argwhere(C & ~used):
        P.append((int(a), int(a) + 1, int(b), int(b) + 1))
    return P, d


# --- exact rational helpers ------------------------------------------------------------------

def _det3(a, b, c, d):
    u = [b[k] - a[k] for k in range(3)]
    v = [c[k] - a[k] for k in range(3)]
    w = [d[k] - a[k] for k in range(3)]
    return u[0] * (v[1] * w[2] - v[2] * w[1]) - u[1] * (v[0] * w[2] - v[2] * w[0]) + u[2] * (v[0] * w[1] - v[1] * w[0])


def clip(poly, x0, x1, y0, y1):
    """Sutherland-Hodgman clipping of a polygon (Fraction vertices) to a rectangle, exactly."""
    def cl(poly, inside, inter):
        out = []
        for k in range(len(poly)):
            P = poly[k]
            Q = poly[(k + 1) % len(poly)]
            ip, iq = inside(P), inside(Q)
            if ip:
                out.append(P)
                if not iq:
                    out.append(inter(P, Q))
            elif iq:
                out.append(inter(P, Q))
        return out

    def ix(xc):
        return lambda P, Q: (xc, P[1] + (Q[1] - P[1]) * (xc - P[0]) / (Q[0] - P[0]))

    def iy(yc):
        return lambda P, Q: (P[0] + (Q[0] - P[0]) * (yc - P[1]) / (Q[1] - P[1]), yc)

    for ins, inter in ((lambda P: P[0] >= x0, ix(x0)), (lambda P: P[0] <= x1, ix(x1)),
                       (lambda P: P[1] >= y0, iy(y0)), (lambda P: P[1] <= y1, iy(y1))):
        poly = cl(poly, ins, inter)
        if not poly:
            return poly
    return poly


def parea(p) -> Fr:
    s = 0
    for k in range(len(p)):
        a = p[k]
        b = p[(k + 1) % len(p)]
        s += a[0] * b[1] - a[1] * b[0]
    return abs(s) / 2


def tri_area(xyz, t) -> Fr:
    A, B, C = [(Fr(float(xyz[i][0])), Fr(float(xyz[i][1]))) for i in t]
    return abs((B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0])) / 2


# --- the model checks (section 4.1) ----------------------------------------------------------

def model_checks(mesh: dict) -> dict:
    """Every required model fact of section 4.1, checked exactly in rationals from the float64
    coordinates. Returns {"checks": {name: bool}, "details": {...}, "failures": [names]}."""
    xyz, tets, ta, tris, tra = mesh["xyz"], mesh["tets"], mesh["tet_attr"], mesh["tris"], mesh["tri_attr"]
    F = [tuple(Fr(float(v)) for v in row) for row in xyz]
    x0, x1, y0, y1, z0, z1 = BOX
    ck, det = {}, {}
    attrs = sorted({int(a) for a in ta})
    ck["tet_attribute_set_is_{1,3}"] = attrs == [1, 3]
    zt = np.array([[F[i][2] for i in t] for t in tets], dtype=object)
    zmin = [min(r) for r in zt]
    zmax = [max(r) for r in zt]
    ck["attribute_1_tets_have_z_ge_0"] = all(zmin[k] >= 0 for k in range(len(tets)) if ta[k] == 1)
    ck["attribute_3_tets_have_z_le_0"] = all(zmax[k] <= 0 for k in range(len(tets)) if ta[k] == 3)
    ck["no_tet_straddles_z_0"] = not any(zmin[k] < 0 < zmax[k] for k in range(len(tets)))
    ck["every_node_in_the_box"] = all(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and z0 <= p[2] <= z1 for p in F)
    dets = [_det3(*(F[i] for i in t)) for t in tets]
    ck["no_zero_volume_tet"] = all(d_ != 0 for d_ in dets)
    faces = defaultdict(list)
    for k, t in enumerate(tets):
        for f in ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)):
            faces[tuple(sorted(int(t[i]) for i in f))].append(k)
    mult = max(len(v) for v in faces.values())
    ck["every_face_in_at_most_two_tets"] = mult <= 2

    def side(f, k):
        o = [n for n in tets[k] if n not in f][0]
        d_ = _det3(F[f[0]], F[f[1]], F[f[2]], F[o])
        return (d_ > 0) - (d_ < 0)

    same_side = sum(1 for f, l in faces.items() if len(l) == 2 and side(f, l[0]) * side(f, l[1]) != -1)
    ck["shared_faces_on_opposite_sides"] = same_side == 0
    one = {f for f, l in faces.items() if len(l) == 1}
    a2_rows = [tuple(sorted(int(x) for x in t)) for t, a in zip(tris, tra) if a == 2]
    a2 = set(a2_rows)
    ck["attribute_2_triangles_distinct"] = len(a2) == len(a2_rows)
    ck["one_tet_faces_are_exactly_the_3040_attribute_2_faces"] = one == a2 and len(a2) == 3040

    def on_wall(f):
        P3 = [F[i] for i in f]
        for k, (lo, hi) in enumerate(((x0, x1), (y0, y1), (z0, z1))):
            if all(p[k] == lo for p in P3) or all(p[k] == hi for p in P3):
                return True
        return False

    ck["every_one_tet_face_on_a_wall_plane"] = all(on_wall(f) for f in one)
    V = {1: Fr(0), 3: Fr(0)}
    for d_, a in zip(dets, ta):
        V[int(a)] = V.get(int(a), Fr(0)) + abs(d_) / 6
    total = sum(V.values(), Fr(0))
    ck["volume_sum_is_the_box"] = total == (Fr(2) - Fr(-2)) ** 2 * (Fr(1.5) - Fr(-0.43))
    ck["attribute_3_volume"] = V.get(3) == 16 * (0 - Fr(-0.43))
    ck["attribute_1_volume"] = V.get(1) == 24
    z0f = [f for f in faces if all(F[i][2] == 0 for i in f)]

    def area2(f):
        a, b, c = (F[i] for i in f)
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    ck["z0_faces_area_is_16"] = sum((abs(area2(f)) for f in z0f), Fr(0)) / 2 == 16
    ck["every_z0_face_between_attribute_1_and_3"] = all(sorted(int(ta[k]) for k in faces[f]) == [1, 3] for f in z0f)
    edges = defaultdict(list)
    for f in z0f:
        for e in ((f[0], f[1]), (f[0], f[2]), (f[1], f[2])):
            edges[e].append([n for n in f if n not in e][0])

    def on_square(e):
        a, b = F[e[0]], F[e[1]]
        return (a[0] == b[0] and a[0] in (x0, x1)) or (a[1] == b[1] and a[1] in (y0, y1))

    bad_edges = 0
    for e, opp in edges.items():
        if on_square(e):
            continue
        if len(opp) != 2:
            bad_edges += 1
            continue
        a, b = F[e[0]], F[e[1]]
        s = [(b[0] - a[0]) * (F[o][1] - a[1]) - (b[1] - a[1]) * (F[o][0] - a[0]) for o in opp]
        if not s[0] * s[1] < 0:
            bad_edges += 1
    ck["every_z0_edge_on_the_square_or_in_two_opposite_faces"] = bad_edges == 0
    tz_rows = [tuple(sorted(int(x) for x in t)) for t in tris if all(F[int(i)][2] == 0 for i in t)]
    ck["tagged_z0_triangles_distinct_tet_faces"] = (len(set(tz_rows)) == len(tz_rows)
                                                   and all(r in faces for r in tz_rows))
    ck["every_attribute_4_triangle_at_z_0"] = all(all(F[int(i)][2] == 0 for i in t) for t, a in zip(tris, tra) if a == 4)
    det.update(tets=int(len(tets)), faces=len(faces), max_face_multiplicity=mult, same_side_faces=same_side,
               one_tet_faces=len(one), attribute_2_faces=len(a2), z0_faces=len(z0f), z0_edge_violations=bad_edges,
               tagged_z0_triangles=len(tz_rows), tet_attributes=attrs,
               volume_attr1=f"{V.get(1).numerator}/{V.get(1).denominator}",
               volume_attr3=f"{V.get(3).numerator}/{V.get(3).denominator}")
    return {"checks": ck, "details": det, "failures": [k for k, v in ck.items() if not v]}


# --- island, ground body and the R1 cut (section 3.1) ----------------------------------------

def island_and_ground(mesh: dict) -> dict:
    xyz, tris, tra = mesh["xyz"], mesh["tris"], mesh["tri_attr"]
    T4 = tris[tra == 4]
    n = len(xyz)
    r = np.concatenate([T4[:, 0], T4[:, 1], T4[:, 2]])
    c = np.concatenate([T4[:, 1], T4[:, 2], T4[:, 0]])
    _, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)), directed=False)
    tl = lab[T4[:, 0]]
    comps, cc = np.unique(tl, return_counts=True)
    isl = T4[tl == comps[np.argmin(cc)]]
    gnd = T4[tl != comps[np.argmin(cc)]]
    nodes = np.unique(isl)
    P = xyz[nodes]
    area = sum((tri_area(xyz, t) for t in isl), Fr(0))
    facts = {"attr4_components": int(len(comps)), "island_triangles": int(len(isl)), "island_nodes": int(len(nodes)),
             "island_bbox": [float(P[:, 0].min()), float(P[:, 0].max()), float(P[:, 1].min()), float(P[:, 1].max())],
             "island_area_mm2": float(area)}
    return {"island": isl, "ground": gnd, "facts": facts}


def _edges_of(t):
    return [tuple(sorted((int(a), int(b)))) for a, b in ((t[0], t[1]), (t[1], t[2]), (t[0], t[2]))]


def _contains(xyz, t, P) -> bool:
    """Whether the closed triangle t contains the point P, exactly."""
    A, B, C = [(Fr(float(xyz[i][0])), Fr(float(xyz[i][1]))) for i in t]

    def s(p, q, r_):
        return (q[0] - p[0]) * (r_[1] - p[1]) - (q[1] - p[1]) * (r_[0] - p[0])

    d = [s(A, B, P), s(B, C, P), s(C, A, P)]
    return min(d) >= 0 or max(d) <= 0


def r1_cut(mesh: dict, gnd: np.ndarray) -> dict:
    """Cut every ground-body edge whose end nodes satisfy |y + 0.433| <= 1e-9 and
    1.12 - 1e-9 <= x <= 1.17 + 1e-9 (mm); R1 is the edge-connected component containing the
    unique triangle that contains (-0.455, 0)."""
    xyz = mesh["xyz"]

    def on_cut(e):
        return all(abs(xyz[v][1] + 0.433) <= 1e-9 and 1.12 - 1e-9 <= xyz[v][0] <= 1.17 + 1e-9 for v in e)

    emap = defaultdict(list)
    for k, t in enumerate(gnd):
        for e in _edges_of(t):
            emap[e].append(k)
    rows, cols, cut = [], [], []
    for e, ks in emap.items():
        if on_cut(e):
            cut.append(e)
            continue
        for a in ks:
            for b in ks:
                if a != b:
                    rows.append(a)
                    cols.append(b)
    ncomp, lab = connected_components(coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(gnd), len(gnd))),
                                      directed=False)
    seeds = [k for k, t in enumerate(gnd) if _contains(xyz, t, R1_SEED_POINT)]
    comp_sizes = sorted(int(v) for v in np.bincount(lab))
    out = {"r1_cut_edges": len(cut), "r1_cut_nodes": len({v for e in cut for v in e}),
           "r1_components": comp_sizes, "r1_seed_triangles": len(seeds)}
    if len(seeds) != 1:
        out.update(R1=None, GP=None, r1_triangles=None, r1_area_mm2=None)
        return out
    R1 = gnd[lab == lab[seeds[0]]]
    GP = gnd[lab != lab[seeds[0]]]
    A_R1 = sum((tri_area(xyz, t) for t in R1), Fr(0))
    out.update(R1=R1, GP=GP, r1_triangles=int(len(R1)), r1_area_mm2=float(A_R1),
               r1_area_ok=abs(A_R1 - Fr("0.35915")) <= Fr("1e-12"))
    return out


# --- candidates on the 5 um lattice (section 3.1) ---------------------------------------------

def _window_cells(w: float, per_mm: int = 200):
    I0, I1 = round((-0.6 - w) * per_mm), round((-0.6 + w) * per_mm)
    J0, J1 = round(-w * per_mm), round(w * per_mm)
    return I0, I1, J0, J1


def cover(xyz, T, I0, I1, J0, J1, per_mm: int = 200, S: float = 1e-9) -> dict:
    """Exact area of each shrunk lattice cell covered by the triangles T (cells (i, j),
    rectangle [i/K + S, (i+1)/K - S] x [j/K + S, (j+1)/K - S], K = per_mm)."""
    L = lambda k: float(Fr(k, per_mm))  # noqa: E731
    cov = {}
    for t in T:
        P = xyz[t][:, :2]
        bx0, by0 = P.min(0)
        bx1, by1 = P.max(0)
        i0 = max(I0, math.floor(bx0 * per_mm) - 1)
        i1 = min(I1 - 1, math.floor(bx1 * per_mm) + 1)
        j0 = max(J0, math.floor(by0 * per_mm) - 1)
        j1 = min(J1 - 1, math.floor(by1 * per_mm) + 1)
        if i0 > i1 or j0 > j1:
            continue
        poly = None
        for i in range(i0, i1 + 1):
            cx0, cx1 = L(i) + S, L(i + 1) - S
            if cx1 < bx0 or cx0 > bx1:
                continue
            for j in range(j0, j1 + 1):
                cy0, cy1 = L(j) + S, L(j + 1) - S
                if cy1 < by0 or cy0 > by1:
                    continue
                if poly is None:
                    poly = [(Fr(float(p[0])), Fr(float(p[1]))) for p in P]
                cpol = clip(poly, Fr(cx0), Fr(cx1), Fr(cy0), Fr(cy1))
                if len(cpol) >= 3:
                    a = parea(cpol)
                    if a:
                        cov[(i, j)] = cov.get((i, j), 0) + a
    return cov


def candidates(xyz, GP, R1, isl, w: float = CONFIG["w_mm"]) -> dict:
    I0, I1, J0, J1 = _window_cells(w)
    S = CONFIG["shrink_mm"]
    L = lambda k: float(Fr(k, 200))  # noqa: E731
    cG, cR, cI = cover(xyz, GP, I0, I1, J0, J1), cover(xyz, R1, I0, I1, J0, J1), cover(xyz, isl, I0, I1, J0, J1)
    nI, nJ = I1 - I0, J1 - J0
    cand = np.zeros((nI, nJ), bool)
    inR1 = np.zeros((nI, nJ), bool)
    full = isl_full = empty = partial = 0
    for a in range(nI):
        for b in range(nJ):
            i, j = I0 + a, J0 + b
            A = (Fr(L(i + 1) - S) - Fr(L(i) + S)) * (Fr(L(j + 1) - S) - Fr(L(j) + S))
            g = cG.get((i, j), 0) + cR.get((i, j), 0)
            ii = cI.get((i, j), 0)
            cand[a, b] = g == A
            inR1[a, b] = cR.get((i, j), 0) == A
            if g == A:
                full += 1
            elif ii == A:
                isl_full += 1
            elif g == 0 and ii == 0:
                empty += 1
            else:
                partial += 1
    return {"I0": I0, "J0": J0, "cand": cand, "inR1": inR1,
            "facts": {"cells_5um": nI * nJ, "candidates": full, "cells_in_r1": int(inR1.sum()),
                      "cells_island_full": isl_full, "cells_no_metal": empty, "cells_partial": partial}}


# --- panels and exact containment (sections 3.1, 4.2) ---------------------------------------

def ground_panels(cand: dict) -> dict:
    f = 4                                       # 5 um cells -> 1.25 um base cells
    per_mm = CONFIG["per_mm"]
    C = upsample(cand["cand"], f)
    Rm = upsample(cand["inR1"], f)
    gi0, gj0 = cand["I0"] * f, cand["J0"] * f
    P, _ = merge(C, gi0, gj0, CONFIG["kappa"], CONFIG["blocks"])
    L = lambda k: float(Fr(k, per_mm))  # noqa: E731
    s = CONFIG["shrink_mm"]
    rects = [(L(gi0 + a) + s, L(gi0 + a2) - s, L(gj0 + b) + s, L(gj0 + b2) - s) for a, a2, b, b2 in P]
    inr1 = [bool(Rm[a:a2, b:b2].all()) for a, a2, b, b2 in P]
    strad = sum(1 for (a, a2, b, b2) in P if Rm[a:a2, b:b2].any() and not Rm[a:a2, b:b2].all())
    sizes = Counter(str(round((a2 - a) * CONFIG["h_um"], 4)) for a, a2, b, b2 in P)
    return {"rects": rects, "on_r1": inr1,
            "facts": {"ground_panels": len(P), "ground_by_side_um": dict(sorted(sizes.items(), key=lambda kv: float(kv[0]))),
                      "ground_on_r1": sum(inr1), "ground_straddling": strad, "ground_excl_r1": len(P) - sum(inr1)}}


def buckets(xyz, T) -> dict:
    B = defaultdict(list)
    for k, t in enumerate(T):
        Pp = xyz[t][:, :2]
        for i in range(math.floor(Pp[:, 0].min() * 200) - 1, math.floor(Pp[:, 0].max() * 200) + 2):
            for j in range(math.floor(Pp[:, 1].min() * 200) - 1, math.floor(Pp[:, 1].max() * 200) + 2):
                B[(i, j)].append(k)
    return B


def covered(xyz, T, B, r) -> bool:
    """Whether the rectangle r = (x0, x1, y0, y1) is covered by the triangles T with exactly
    its area (exact rational clipping; triangles pre-selected by bounding box, so a missed
    triangle can only cause a false refusal)."""
    x0, x1, y0, y1 = r
    idx = set()
    for i in range(math.floor(x0 * 200), math.floor(x1 * 200) + 1):
        for j in range(math.floor(y0 * 200), math.floor(y1 * 200) + 1):
            idx.update(B.get((i, j), []))
    tot = 0
    for k in idx:
        Pp = xyz[T[k]][:, :2]
        c = clip([(Fr(float(p[0])), Fr(float(p[1]))) for p in Pp], Fr(x0), Fr(x1), Fr(y0), Fr(y1))
        if len(c) >= 3:
            tot += parea(c)
    return tot == (Fr(x1) - Fr(x0)) * (Fr(y1) - Fr(y0))


def geometry_phase(mesh: dict) -> dict:
    """The whole S1 geometry phase: model checks, island, R1 cut, candidates, merge, exact
    containment, counts and the negative controls N1, N2, N3b and N3c (section 5). Returns the
    panel sets (E1.2 ordered island, then ground panels not on R1, then R1 panels, so that
    E1.1 and E1.2-excl-R1 are leading principal subsets) and the facts with the list of
    failures against EXPECTED. No matrix is assembled."""
    xyz = mesh["xyz"]
    facts, fails = {}, []
    mc = model_checks(mesh)
    fails += [f"model check: {k}" for k in mc["failures"]]
    ig = island_and_ground(mesh)
    facts.update(ig["facts"])
    cut = r1_cut(mesh, ig["ground"])
    facts.update({k: v for k, v in cut.items() if k not in ("R1", "GP")})
    if cut["R1"] is None:
        fails.append("R1: the seed point is not in exactly one triangle")
        return {"facts": facts, "model_checks": mc, "failures": fails}
    if not cut.get("r1_area_ok"):
        fails.append(f"R1 area {cut['r1_area_mm2']!r} is not 0.35915 within 1e-12")
    cand = candidates(xyz, cut["GP"], cut["R1"], ig["island"])
    facts.update(cand["facts"])
    gp = ground_panels(cand)
    facts.update(gp["facts"])
    ipan = island_panels(CONFIG["n"], CONFIG["q"])
    half = island_panels(CONFIG["n"], CONFIG["q"], step=2)
    GB = np.concatenate([cut["GP"], cut["R1"]])
    BI, BG, BGP = buckets(xyz, ig["island"]), buckets(xyz, GB), buckets(xyz, cut["GP"])
    okI = [covered(xyz, ig["island"], BI, tuple(r)) for r in ipan]
    okH = [covered(xyz, ig["island"], BI, tuple(r)) for r in half]
    okG = [covered(xyz, GB, BG, r) for r in gp["rects"]]
    okX = [covered(xyz, cut["GP"], BGP, r) for r in gp["rects"]]
    excl = [r for r, ok in zip(gp["rects"], okX) if ok]
    on_r1 = [r for r, ok in zip(gp["rects"], okX) if not ok]
    facts.update(contained_island=sum(okI), contained_half=sum(okH), contained_ground=sum(okG),
                 contained_excl=sum(okX),
                 excl_membership_equals_not_on_r1=[bool(x) for x in okX] == [not v for v in gp["on_r1"]])
    if not facts["excl_membership_equals_not_on_r1"]:
        fails.append("E1.2-excl-R1 membership by containment differs from the R1 cell map")
    # the negative controls with S1 data, each with its positive counterpart (section 5)
    edge = tuple(ipan[(CONFIG["n"] - 1) * CONFIG["n"] + CONFIG["n"] // 2])
    shifted = (edge[0] + 1e-6, edge[1] + 1e-6, edge[2], edge[3])
    n1 = {"unshifted_accepted": covered(xyz, ig["island"], BI, edge),
          "shifted_refused": not covered(xyz, ig["island"], BI, shifted)}
    r1p = on_r1[0] if on_r1 else None
    n2 = {"refused_for_excl": r1p is not None and not covered(xyz, cut["GP"], BGP, r1p),
          "accepted_for_E1_2": r1p is not None and covered(xyz, GB, BG, r1p)}
    m_b = {k: np.array(v, copy=True) for k, v in mesh.items()}
    b_idx = int(np.flatnonzero(m_b["tri_attr"] == 2)[0])
    m_b["tri_attr"][b_idx] = 0
    m_c = {k: np.array(v, copy=True) for k, v in mesh.items()}
    c_idx = int(np.flatnonzero(m_c["tet_attr"] == 3)[0])
    m_c["tet_attr"][c_idx] = 1
    n3b = {"unmodified_passes": not mc["failures"], "modified_refused": bool(model_checks(m_b)["failures"])}
    n3c = {"unmodified_passes": not mc["failures"], "modified_refused": bool(model_checks(m_c)["failures"])}
    controls = {"N1": {**n1, "pass": all(n1.values())}, "N2": {**n2, "pass": all(n2.values())},
                "N3b": {**n3b, "pass": all(n3b.values())}, "N3c": {**n3c, "pass": all(n3c.values())}}
    fails += [f"control {k} failed" for k, v in controls.items() if not v["pass"]]
    facts.update(N_E1_2=len(ipan) + len(excl) + len(on_r1), N_E1_2_excl_R1=len(ipan) + len(excl),
                 N_E1_1=len(ipan), N_E1_1_half=len(half))
    for k, want in EXPECTED.items():
        if facts.get(k) != want:
            fails.append(f"{k}: measured {facts.get(k)!r}, expected {want!r}")
    R12 = np.array(list(map(tuple, ipan)) + excl + on_r1, dtype=np.float64)
    return {"facts": facts, "model_checks": mc, "controls": controls, "failures": fails,
            "R_E1_2": R12, "n_island": len(ipan), "n_excl": len(ipan) + len(excl), "R_E1_1_half": half}
