# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""SYNTHETIC panel sets for the resource Confirmation and the proxy-A g_E check of the frozen
contract E1-CONTRACT.rev8.2.md (section 3.2 item 2 and item 4, section 6). NOT S1: nothing
here reads the S1 mesh, and nothing here is ever used by the attempt.

The stand-in is the one the revision-8 prototype measured (section 6): the selected island
(n = 32, q = 3.5) at (-0.6, 0) mm, plus 8,971 ground panels drawn at random (default_rng(5))
from a synthetic slotted ground sheet in W panelled with the selected rules; the 3,285 of
those that come last when sorted by ascending centroid x, then ascending centroid y, form
its R1 set. The contract freezes this generator with the implementation.

Proxy A is the selection rule's synthetic proxy (section 3.2 item 5): the island
[-0.075, 0.075]^2 mm at the origin, in a square ground hole of half-width 0.115 mm, in a
ground sheet filling [-w, w]^2, with the same panelling rules.
"""
from __future__ import annotations

from fractions import Fraction as Fr

import numpy as np

from e1_geometry import CONFIG, island_nodes, island_panels, merge

N_GROUND, N_R1, SEED = 8971, 3285, 5
NSLOT, COMB_UM = 12, 40.0


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
    isl = island_panels(CONFIG["n"], CONFIG["q"])
    R = np.array(list(map(tuple, isl)) + excl + r1l, dtype=np.float64)
    return {"R_E1_2": R, "n_island": len(isl), "n_excl": len(isl) + len(excl),
            "R_E1_1_half": island_panels(CONFIG["n"], CONFIG["q"], step=2), "sheet_panels": len(P)}


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
