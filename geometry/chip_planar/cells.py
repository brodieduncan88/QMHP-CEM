"""Planar chip geometry via gdsfactory (spec §7.1). NOT IMPLEMENTED in v0.1.

v0.1 planar cells required by the spec:

1. readout resonator;
2. impedance-stepped filter.

Each must be parameter-driven from a :class:`contracts.Candidate`, expose
explicit ports, use deterministic cell naming, report a bounding box, pass the
project DRC test, and export in a form the EM adapters can mesh.

All planar dimensions not defined by the frozen Master are ENGINEERING-SEED.

gdsfactory is an optional dependency (``pip install -e '.[planar]'``) so that
default CI stays light per spec §12.8.
"""

from __future__ import annotations

from typing import Any


class PlanarGeometryNotImplemented(NotImplementedError):
    """A spec §7.1 planar cell has not been implemented in this release."""


def gdsfactory_available() -> bool:
    """Whether the optional planar stack is importable.

    A broken or version-skewed install raises something other than ImportError
    on import (gdsfactory pulls in kfactory, which raises PydanticUserError
    when its pydantic is incompatible). Such a stack is just as unusable as an
    absent one, so treat any import failure as unavailable rather than letting
    it escape this probe and break collection of every test in the module.
    """
    try:
        import gdsfactory  # noqa: F401
    except Exception:
        return False
    return True


def require_gdsfactory() -> Any:
    """Import gdsfactory or explain how to install it."""
    try:
        import gdsfactory
    except Exception as exc:
        raise PlanarGeometryNotImplemented(
            "gdsfactory is not importable. Planar geometry (spec §7.1) needs the "
            "optional planar extra: pip install -e '.[planar]'. An installed but "
            "version-skewed stack fails here too. Default CI does not require it "
            "(spec §12.8)."
        ) from exc
    return gdsfactory


def readout_resonator(candidate) -> Any:  # noqa: ANN001
    """Readout resonator cell. NOT IMPLEMENTED."""
    raise PlanarGeometryNotImplemented(
        "the readout resonator cell (spec §7.1) is not implemented in v0.1. "
        "It must be parameter-driven from the candidate, expose explicit ports "
        "and use deterministic cell naming."
    )


def stepped_filter(candidate) -> Any:  # noqa: ANN001
    """Impedance-stepped Purcell filter cell. NOT IMPLEMENTED."""
    raise PlanarGeometryNotImplemented(
        "the impedance-stepped filter cell (spec §7.1) is not implemented in "
        "v0.1. Its stopband must be evaluated at the frozen dressed emission "
        "frequency 3.395056 GHz against the 34/36 dB requirement."
    )


def run_drc(cell) -> list[str]:  # noqa: ANN001
    """Project DRC. NOT IMPLEMENTED. Returns violations when implemented."""
    raise PlanarGeometryNotImplemented(
        "project DRC rules (spec §7.1, §12.6) are not implemented in v0.1."
    )
