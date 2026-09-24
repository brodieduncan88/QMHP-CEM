# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""SYNTHETIC panel sets for the resource Confirmation of the frozen contract
E1-CONTRACT.rev8.5.md (section 3.2 item 2, section 6), the section 3.2 item 2 separation rule,
and proxy A of section 3.2 item 5. "Synthetic" means generated here without reading the S1
mesh; it does not mean that no panel coincides with an S1 panel (D15). Nothing here is ever
used by the attempt.

The stand-in (section 6, revisions 8.3 to 8.5) is the revision-8 prototype's full-size one, except its
island: 32 x 32 panels at (-0.6, 0) mm with x_k = -0.6 + s_k(0.075) and y_k = s_k(0.0625),
s_k(a) the section 3.1 node formula with n = 32 and q = 3.5 at half-width a. The prototype's
island was the selected island itself, so its E1.1 and E1.1-half were S1's internal sets (D14).
The 8,971 ground panels are drawn at random (default_rng(5)) from a synthetic slotted ground
sheet in W panelled with the selected rules; the 3,285 of them that come last when sorted by
ascending centroid x, then ascending centroid y, form its R1 set. Because the sheet uses S1's
lattice, window and merge rules, 534 of these ground panels are bit-identical to S1 E1.2
ground panels; individual coincidences are permitted (D15).

separation_problems() is the section 3.2 item 2 rule (revisions 8.4 and 8.5, D15, D16): no numeric set of a
pre-approval run may contain an image of an S1 attempt set (E1.2, E1.2-excl-R1, E1.1 or
E1.1-half), as the whole set or as an embedded subset, under the symmetries of the square,
uniform scaling and translation, with the panels in any order and their bounds in either
order. The pre-approval runs check it before any numerics on the set concerned.

Proxy A is the selection rule's synthetic proxy (section 3.2 item 5): the island
[-0.075, 0.075]^2 mm at the origin, in a square ground hole of half-width 0.115 mm, in a
ground sheet filling [-w, w]^2, with the same panelling rules. For the selected configuration
its island is S1's E1.1 translated by +0.6 mm in x, so it embeds an image of E1.1: it is kept
as historical configuration-selection evidence and is not run again (D15).
"""
from __future__ import annotations

import math
from fractions import Fraction as Fr

import numpy as np

from e1_geometry import CONFIG, island_nodes, island_panels, merge

N_GROUND, N_R1, SEED = 8971, 3285, 5
NSLOT, COMB_UM = 12, 40.0
#: the stand-in island's half-widths in x and y (mm), section 6 (revisions 8.3 and 8.4)
ISLAND_HALF_X, ISLAND_HALF_Y = 0.075, 0.0625


def _slotted_mask():
    I0, I1, J0, J1 = -864, -96, -384, 384            # W = [-1.08, -0.12] x [-0.48, 0.48] at 1.25 um
    per = CONFIG["per_mm"]
    xi = np.arange(I0, I1)
    yj = np.arange(J0, J1)
    xc = (xi + 0.5) / per
    yc = (yj + 0.5) / per
    C = ~((np.abs(xc + 0.6)[:, None] < 0.115) & (np.abs(yc)[None, :] < 0.115))
    for k in range(NSLOT):
        y0 = -0.44 + k * 0.88 / max(NSLOT - 1, 1)
        jj = (yj >= round(y0 * per)) & (yj < round(y0 * per) + 4)
        C[np.ix_(xc < -0.75, jj)] = False
    for x0 in np.arange(-0.44, -0.14, COMB_UM / 1000.0):
        ii = (xi >= round(x0 * per)) & (xi < round(x0 * per) + 4)
        C[np.ix_(ii, (yc > -0.40) & (yc < 0.40))] = False
    return C, I0, J0


def _rects(P, I0, J0, per):
    L = lambda k: float(Fr(k, per))  # noqa: E731
    s = CONFIG["shrink_mm"]
    return [(L(I0 + a) + s, L(I0 + a2) - s, L(J0 + b) + s, L(J0 + b2) - s) for a, a2, b, b2 in P]


def standin_island(step: int = 1) -> np.ndarray:
    """The stand-in's 32 x 32 island (step 1) or its nested 16 x 16 grid of even k (step 2):
    x_k = -0.6 + s_k(0.075), y_k = s_k(0.0625), i-major (section 6, revisions 8.3 and 8.4)."""
    sx = island_nodes(CONFIG["n"], CONFIG["q"], half=ISLAND_HALF_X)[::step]
    sy = island_nodes(CONFIG["n"], CONFIG["q"], half=ISLAND_HALF_Y)[::step]
    x = -0.6 + sx
    m = len(sx) - 1
    return np.array([(x[i], x[i + 1], sy[j], sy[j + 1]) for i in range(m) for j in range(m)], dtype=np.float64)


def standin() -> dict:
    """The stand-in of the selected sizes: R (E1.2 order: island, the 5,686 non-R1 ground
    panels, the 3,285 stand-in R1 panels), n_island = 1,024, n_excl = 6,710, and E1.1-half."""
    C, I0, J0 = _slotted_mask()
    P, _ = merge(C, I0, J0, CONFIG["kappa"], CONFIG["blocks"])
    g = _rects(P, I0, J0, CONFIG["per_mm"])
    rng = np.random.default_rng(SEED)
    keep = np.sort(rng.choice(len(g), N_GROUND, replace=False))
    g = [g[k] for k in keep]
    cx = np.array([(p[0] + p[1]) / 2 for p in g])
    cy = np.array([(p[2] + p[3]) / 2 for p in g])
    order = np.lexsort((cy, cx))                      # ascending x, then ascending y
    r1 = set(order[-N_R1:].tolist())
    excl = [g[k] for k in range(N_GROUND) if k not in r1]
    r1l = [g[k] for k in range(N_GROUND) if k in r1]
    isl = standin_island()
    R = np.array(list(map(tuple, isl)) + excl + r1l, dtype=np.float64)
    return {"R_E1_2": R, "n_island": len(isl), "n_excl": len(isl) + len(excl),
            "R_E1_1_half": standin_island(step=2), "sheet_panels": len(P)}


def numeric_sets(sets: dict) -> dict:
    """The four panel sets on which the capacitance phase assembles, factorises and forms an
    energy, from a stand-in or attempt family: E1.2, E1.2-excl-R1, E1.1 and E1.1-half."""
    R, ni, nx = sets["R_E1_2"], sets["n_island"], sets["n_excl"]
    return {"E1.2": R, "E1.2-excl-R1": R[:nx], "E1.1": R[:ni], "E1.1-half": sets["R_E1_1_half"]}


# --- the separation rule (section 3.2 item 2, revision 8.4, D15) --------------------------------

#: the eight symmetries of the square, as (exchange x and y, sign of x, sign of y) applied in that
#: order: the identity, the two axis reflections, the point reflection (uniform scaling by -1),
#: the exchange of x and y, and the rotations by +-90 degrees and the diagonal reflections
_SYMMETRIES = [(swap, fx, fy) for swap in (False, True) for fx in (1, -1) for fy in (1, -1)]
#: two bounds agree when they differ by at most SEPARATION_RHO * M, M the largest coordinate
#: magnitude of the synthetic set (section 3.2 item 2)
SEPARATION_RHO = 2.0 ** -22
#: the rows of the image checked first, before all of it
_SAMPLE_ROWS = 32


def normalised(R) -> np.ndarray:
    """Each panel with its bounds in increasing order (x0 <= x1, y0 <= y1). Reversing a panel's
    x (or y) bounds changes the sign of its corner sum and of its area together, so its Galerkin
    entries are unchanged; the rule therefore compares normalised panels."""
    R = np.asarray(R, dtype=np.float64).reshape(-1, 4)
    return np.stack([np.minimum(R[:, 0], R[:, 1]), np.maximum(R[:, 0], R[:, 1]),
                     np.minimum(R[:, 2], R[:, 3]), np.maximum(R[:, 2], R[:, 3])], axis=1)


def _apply(R: np.ndarray, swap: bool, fx: int, fy: int) -> np.ndarray:
    """A normalised set under one of the eight symmetries (exact: exchanges and negations)."""
    x0, x1, y0, y1 = R[:, 0], R[:, 1], R[:, 2], R[:, 3]
    if swap:
        x0, x1, y0, y1 = y0, y1, x0, x1
    if fx < 0:
        x0, x1 = -x1, -x0
    if fy < 0:
        y0, y1 = -y1, -y0
    return np.stack([x0, x1, y0, y1], axis=1)


def _first(idx: np.ndarray, R: np.ndarray) -> int:
    """Of the rows idx of R, the lexicographically smallest (a deterministic tie-break)."""
    sub = R[idx]
    return int(idx[np.lexsort(sub.T[::-1])[0]])


class _Corners:
    """The panels of a normalised set X by lower-left corner, on a grid of cell size ``cell``:
    near(x0, y0, e) with e <= cell returns every panel whose corner is within e in x and y."""

    def __init__(self, X: np.ndarray, cell: float):
        self.X, self.cell = X, cell
        self.grid: dict = {}
        kx = np.floor(X[:, 0] / cell).astype(np.int64).tolist()
        ky = np.floor(X[:, 2] / cell).astype(np.int64).tolist()
        for i, key in enumerate(zip(kx, ky)):
            self.grid.setdefault(key, []).append(i)

    def near(self, x0: float, y0: float, e: float) -> list[int]:
        kx, ky = math.floor(x0 / self.cell), math.floor(y0 / self.cell)
        X, out = self.X, []
        for a in (kx - 1, kx, kx + 1):
            for b in (ky - 1, ky, ky + 1):
                for i in self.grid.get((a, b), ()):
                    if abs(X[i, 0] - x0) <= e and abs(X[i, 2] - y0) <= e:
                        out.append(i)
        return out


def _candidates(X: np.ndarray, index: _Corners, P: np.ndarray, rows, V: float) -> list | None:
    """For each row k of P in ``rows``, the panels of X whose four bounds all lie within V of
    P[k]; None as soon as a row has none."""
    out = []
    for k in rows:
        x0, x1, y0, y1 = P[k].tolist()
        c = [i for i in index.near(x0, y0, V) if abs(X[i, 1] - x1) <= V and abs(X[i, 3] - y1) <= V]
        if not c:
            return None
        out.append(c)
    return out


def _one_to_one(cands: list) -> bool:
    """Whether every row can have its own panel: a perfect matching of the rows to their
    candidate panels (breadth-first augmenting paths). Exact, whatever the candidate lists."""
    if all(len(c) == 1 for c in cands) and len({c[0] for c in cands}) == len(cands):
        return True
    row_of, panel_of = {}, {}
    for root in range(len(cands)):
        parent, seen, frontier, end = {}, {root}, [root], None
        while frontier and end is None:
            nxt = []
            for r in frontier:
                for p in cands[r]:
                    if p in parent:
                        continue
                    parent[p] = r
                    if p not in row_of:
                        end = p
                        break
                    if row_of[p] not in seen:
                        seen.add(row_of[p])
                        nxt.append(row_of[p])
                if end is not None:
                    break
            frontier = nxt
        if end is None:
            return False
        p = end
        while True:
            r = parent[p]
            old = panel_of.get(r)
            panel_of[r], row_of[p] = p, r
            if r == root:
                break
            p = old
    return True


def _embed_under(X, wX, hX, Ah, tol, M):
    """An image s Ah + t (s > 0, t a translation) of the normalised set Ah whose panels are
    distinct panels of X, or None. With the anchor a (Ah's panel of largest smallest side) and
    a second anchor a' (the panel, of smallest side >= that of a / 8, farthest from a):
      - every panel b of X whose shape can be a's image is a candidate; s0 from its size;
      - a' must then have an image b' near s0 (a' - a) + b; s is fitted on the long baseline
        a -> a' (length delta) and t from b;
      - every panel of s Ah + t must have its own panel of X within V (a perfect matching).
    What is proven (section 3.2 item 2, revision 8.5): if X contains an image of Ah with scale s
    whose bounds agree to within tol, AND s delta > 2 eps (eps = tol + 2^-44 M), this finds it:
    the anchor windows contain the true images of a and a'; the fitted scale then lies within
    2 eps/delta of s, so it is positive; and the fitted image lies within
    V = eps (2 + 2 L/delta) of that image's panels (L the extent of Ah). For a smaller image
    (s delta <= 2 eps) the fitted scale can be <= 0 for every anchor pair, and the image can be
    missed: no claim is made for it."""
    w, h = Ah[:, 1] - Ah[:, 0], Ah[:, 3] - Ah[:, 2]
    m = np.minimum(w, h)
    ia = _first(np.flatnonzero(m == m.max()), Ah)
    a, wa, ha = Ah[ia], float(w[ia]), float(h[ia])
    L = float(max(Ah[:, 1].max() - Ah[:, 0].min(), Ah[:, 3].max() - Ah[:, 2].min()))
    d = np.maximum(np.abs(Ah[:, 0] - a[0]), np.abs(Ah[:, 2] - a[2]))
    d = np.where(m >= m[ia] / 8, d, -1.0)
    ib = _first(np.flatnonzero(d == d.max()), Ah)
    delta = float(d[ib])
    axis = 0 if abs(Ah[ib, 0] - a[0]) >= abs(Ah[ib, 2] - a[2]) else 2
    eps = tol + 2.0 ** -44 * M
    e0 = eps * (2 + 4 * delta / (wa + ha))
    V = eps * (2 + 2 * L / delta) if delta > 0 else eps * (2 + 4 * L / (wa + ha))
    index = _Corners(X, max(e0, V))
    cand = np.flatnonzero(np.abs(wX * ha - hX * wa) <= 2 * eps * (wa + ha))
    n = len(Ah)
    sample = sorted({ia, ib, *np.linspace(0, n - 1, min(n, _SAMPLE_ROWS)).astype(int).tolist()})
    for b in cand.tolist():
        s0 = (wX[b] + hX[b]) / (wa + ha)
        if delta > 0:
            second = index.near(X[b, 0] + s0 * (Ah[ib, 0] - a[0]), X[b, 2] + s0 * (Ah[ib, 2] - a[2]), e0)
        else:
            second = [b]
        for bp in second:
            s = (X[bp, axis] - X[b, axis]) / (Ah[ib, axis] - a[axis]) if delta > 0 else s0
            if not (math.isfinite(s) and s > 0):
                continue
            tx, ty = X[b, 0] - s * a[0], X[b, 2] - s * a[2]
            P = Ah * s + np.array([tx, tx, ty, ty])
            if _candidates(X, index, P, sample, V) is None:
                continue
            c = _candidates(X, index, P, range(n), V)
            if c is not None and _one_to_one(c):
                return {"scale": float(s), "translation": [float(tx), float(ty)], "tolerance": V}
    return None


def find_embedding(X, A) -> dict | None:
    """Whether the synthetic set X contains an image of the set A under the section 3.2 item 2
    maps (the eight symmetries of the square, uniform scaling s > 0, translation; panels in any
    order and with their bounds in either order), as the whole set or as an embedded subset.
    Returns the map found, or None. With tol = SEPARATION_RHO * M, M the largest coordinate
    magnitude of X: an image whose bounds agree to within tol is found whenever its scaled
    fitting baseline s delta exceeds 2 (tol + 2^-44 M) (see _embed_under; a smaller image is
    not guaranteed to be found), and a map is returned only if every panel of its image has its
    own panel of X within the returned tolerance (at most (tol + 2^-44 M)(2 + 2 L/delta))."""
    X, A = normalised(X), normalised(A)
    if len(A) == 0 or len(X) < len(A):
        return None
    M = float(np.abs(X).max())
    tol = SEPARATION_RHO * M
    wX, hX = X[:, 1] - X[:, 0], X[:, 3] - X[:, 2]
    for sym in _SYMMETRIES:
        hit = _embed_under(X, wX, hX, _apply(A, *sym), tol, M)
        if hit is not None:
            return {**hit, "symmetry": {"exchange_x_y": sym[0], "x_sign": sym[1], "y_sign": sym[2]}}
    return None


def _comparable(R) -> str | None:
    R = np.asarray(R, dtype=np.float64)
    if R.ndim != 2 or R.shape[1] != 4 or len(R) == 0:
        return "is not a non-empty list of panels (x0, x1, y0, y1)"
    if not np.isfinite(R).all():
        return "has a non-finite coordinate"
    if not ((R[:, 0] != R[:, 1]) & (R[:, 2] != R[:, 3])).all():
        return "has a panel of zero width or height"
    return None


def separation_problems(synthetic: dict, s1: dict) -> list[str]:
    """Section 3.2 item 2 (revision 8.4, D15): every synthetic numeric set that contains an image
    of an S1 attempt set, as the whole set or as an embedded subset, under the maps of
    find_embedding, and every set that cannot be compared (a non-finite coordinate or a panel of
    zero width or height: fail closed). Empty means separated. Individual panels, and proper
    subsets of an S1 set, may coincide."""
    bad = []
    for an, A in s1.items():
        why = _comparable(A)
        if why:
            bad.append(f"the S1 set {an} {why}: the separation cannot be checked")
    if bad:
        return bad
    for sn, T in synthetic.items():
        why = _comparable(T)
        if why:
            bad.append(f"{sn} {why}: the separation cannot be checked")
            continue
        T = np.asarray(T, dtype=np.float64)
        for an, A in s1.items():
            A = np.asarray(A, dtype=np.float64)
            if T.shape == A.shape and T.tobytes() == A.tobytes():
                bad.append(f"{sn} is byte-identical to the S1 set {an}")
                continue
            hit = find_embedding(T, A)
            if hit is None:
                continue
            kind = "is equivalent to" if len(T) == len(A) else "contains, as an embedded subset, an image of"
            bad.append(f"{sn} {kind} the S1 set {an} (scale {hit['scale']!r}, symmetry {hit['symmetry']})")
    return bad


def s1_island_sets() -> dict:
    """S1's E1.1 and E1.1-half from the section 3.1 node formula, before any mesh is read (the
    geometry phase builds them with the same function). A set containing no image of either
    contains no image of E1.2 or E1.2-excl-R1 either, since E1.1 is a leading subset of both:
    this is what the pre-approval runs check before any control numerics."""
    return {"E1.1": island_panels(CONFIG["n"], CONFIG["q"]), "E1.1-half": island_panels(CONFIG["n"], CONFIG["q"], step=2)}


def proxy_a(h_um: float = 1.25, w: float = 0.48, n: int = 32, q: float = 3.5, kappa: float = 1.25,
            hole: float = 0.115) -> dict:
    """Proxy A (section 3.2 item 5) for one configuration."""
    per = {5.0: 200, 2.5: 400, 1.25: 800}[h_um]
    I0, I1 = round(-w * per), round(w * per)
    xc = (np.arange(I0, I1) + 0.5) / per
    C = ~((np.abs(xc)[:, None] < hole) & (np.abs(xc)[None, :] < hole))
    sizes = {5.0: [8, 4, 2], 2.5: [16, 8, 4, 2], 1.25: [32, 16, 8, 4, 2]}[h_um]
    P, _ = merge(C, I0, I0, kappa, sizes)
    ground = _rects(P, I0, I0, per)
    nd = island_nodes(n, q)
    isl = [(nd[i], nd[i + 1], nd[j], nd[j + 1]) for i in range(n) for j in range(n)]
    return {"R": np.array(isl + ground, dtype=np.float64), "n_island": len(isl)}
