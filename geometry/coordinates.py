"""Frozen coordinate and unit convention (spec §7.3).

::

    origin  = centre of top surface of chip substrate
    +X/+Y   = chip plane
    +Z      = from chip toward package lid
    3D geometry internal unit = mm
    RF frequency unit         = GHz
    RF offset/separation unit = MHz

Every geometry generator and solver adapter works in this frame. It is frozen:
changing it would silently invalidate every stored result.
"""

from __future__ import annotations

from typing import Any

from contracts import master

GEOMETRY_UNIT = "mm"
FREQUENCY_UNIT = "GHz"
OFFSET_UNIT = "MHz"


def convention() -> dict[str, Any]:
    """The frozen convention as recorded in master/."""
    return dict(master.get("conventions"))


def GHz_to_MHz(value_GHz: float) -> float:
    return value_GHz * 1000.0


def MHz_to_GHz(value_MHz: float) -> float:
    return value_MHz / 1000.0
