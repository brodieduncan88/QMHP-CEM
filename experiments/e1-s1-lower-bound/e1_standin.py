# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""SYNTHETIC panel sets for the resource Confirmation and the proxy-A g_E check of the frozen
contract E1-CONTRACT.rev8.3.md (section 3.2 item 2 and item 4, section 6). NOT S1: nothing
here reads the S1 mesh, and nothing here is ever used by the attempt.

The stand-in (section 6, revision 8.3, D14) is the revision-8 prototype's, except its island:
32 x 32 panels at (-0.6, 0) mm with x_k = -0.6 + s_k(0.075) and y_k = s_k(0.0625), s_k(a) the
section 3.1 node formula with n = 32 and q = 3.5 at half-width a. The prototype's island was the
selected island itself, so its E1.1 and E1.1-half were S1's internal sets; this island is not
similar to any S1 attempt set. The 8,971 ground panels are drawn at random (default_rng(5)) from
a synthetic slotted ground sheet in W panelled with the selected rules; the 3,285 of them that
come last when sorted by ascending centroid x, then ascending centroid y, form its R1 set.

separation_problems() is the section 3.2 item 2 separation rule: no numeric set of a
pre-approval run may coincide with an S1 attempt set, byte for byte or up to translation, axis
reflection, exchange of x and y, and uniform scaling. The Confirmation checks it against the S1
geometry phase's sets before any stand-in matrix is assembled.

Proxy A is the selection rule's synthetic proxy (section 3.2 item 5): the island
[-0.075, 0.075]^2 mm at the origin, in a square ground hole of half-width 0.115 mm, in a
ground sheet filling [-w, w]^2, with the same panelling rules.
"""
from __future__ import annotations

from fractions import Fraction as Fr

import numpy as np

from e1_geometry import CONFIG, island_nodes, merge

N_GROUND, N_R1, SEED = 8971, 3285, 5
NSLOT, COMB_UM = 12, 40.0
#: the stand-in island's half-widths in x and y (mm), section 6 (revision 8.3)
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
    x_k = -0.6 + s_k(0.075), y_k = s_k(0.0625), i-major (section 6, revision 8.3)."""
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


# --- the separation rule (section 3.2 item 2, revision 8.3) --------------------------------------

_SYMMETRIES = [(swap, fx, fy) for swap in (False, True) for fx in (1, -1) for fy in (1, -1)]
SIMILARITY_RTOL = 1e-9


def _canonical(R: np.ndarray, swap: bool, fx: int, fy: int) -> np.ndarray:
    """R under one of the eight axis symmetries, translated to its lower-left corner, scaled to
    unit largest extent, rounded to SIMILARITY_RTOL and sorted: equal for similar sets."""
    x0, x1, y0, y1 = (R[:, k].astype(np.float64) for k in range(4))
    if swap:
        x0, x1, y0, y1 = y0, y1, x0, x1
    if fx < 0:
        x0, x1 = -x1, -x0
    if fy < 0:
        y0, y1 = -y1, -y0
    ox, oy = x0.min(), y0.min()
    L = max(x1.max() - ox, y1.max() - oy)
    if not (np.isfinite(L) and L > 0):
        return np.full((len(R), 4), np.nan)
    C = np.stack([(x0 - ox) / L, (x1 - ox) / L, (y0 - oy) / L, (y1 - oy) / L], axis=1)
    C = np.round(C / SIMILARITY_RTOL).astype(np.int64)
    return C[np.lexsort(C.T[::-1])]


def _aspects(R: np.ndarray) -> np.ndarray:
    w = R[:, 1] - R[:, 0]
    h = R[:, 3] - R[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.sort(np.maximum(w, h) / np.minimum(w, h))


def similar(A: np.ndarray, B: np.ndarray) -> bool:
    """Whether two axis-aligned rectangle sets coincide up to translation, axis reflection,
    exchange of x and y and uniform scaling (to SIMILARITY_RTOL). The sorted aspect ratios
    max(w, h)/min(w, h) are invariant under all of these, so a difference there proves the sets
    are not similar; otherwise the eight canonical forms are compared."""
    A = np.asarray(A, dtype=np.float64)
    B = np.asarray(B, dtype=np.float64)
    if A.shape != B.shape:
        return False
    if not np.allclose(_aspects(A), _aspects(B), rtol=SIMILARITY_RTOL, atol=0, equal_nan=True):
        return False
    ca = _canonical(A, False, 1, 1)
    return any(np.array_equal(ca, _canonical(B, *sym)) for sym in _SYMMETRIES)


def separation_problems(synthetic: dict, s1: dict) -> list[str]:
    """Every coincidence between a synthetic numeric set and an S1 attempt set: byte-identical,
    or similar (section 3.2 item 2). Empty means separated."""
    bad = []
    for sn, T in synthetic.items():
        T = np.asarray(T, dtype=np.float64)
        for an, A in s1.items():
            A = np.asarray(A, dtype=np.float64)
            if T.shape == A.shape and T.tobytes() == A.tobytes():
                bad.append(f"{sn} is byte-identical to the S1 set {an}")
            elif similar(T, A):
                bad.append(f"{sn} is similar to the S1 set {an}")
    return bad


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
