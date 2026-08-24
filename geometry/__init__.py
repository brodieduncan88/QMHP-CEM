"""QMHP-CEM geometry generation (spec §7).

Two layers, deliberately separate:

* ``chip_planar`` — planar superconducting geometry via gdsfactory (§7.1);
* ``package_picogk`` — 3D package geometry via PicoGK/ShapeKernel (§7.2).

PicoGK owns physical geometry. It is a computational-geometry engine, not an
EM or quantum solver: it generates the geometry on which the physics is
evaluated, and never the physics itself. Thin-film mask/GDS work belongs in
``chip_planar``; Hamiltonians and QEC belong in ``models``.
"""

from geometry import coordinates

__all__ = ["coordinates"]
