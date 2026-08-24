"""PicoGK package geometry (spec §7.2, §7.4).

Object 001 — ``object001_single_device_package``.
"""

from geometry.package_picogk.driver import (
    PICOGK_VERSION,
    SHAPEKERNEL_REVISION,
    GeometryResult,
    dotnet_available,
    environment_record,
    generate,
)

__all__ = [
    "PICOGK_VERSION",
    "SHAPEKERNEL_REVISION",
    "GeometryResult",
    "dotnet_available",
    "environment_record",
    "generate",
]
