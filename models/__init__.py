"""QMHP-CEM physics models (spec §5).

The static spectrum, dressed-system root, Purcell estimates, collision screen,
and tolerance ensemble are implemented and regression-tested against the
frozen conventions.  Some deliberately incomplete paths — notably the two
independent coupling extractions — still raise
:class:`models._stub.PhysicsNotImplemented` rather than fabricate evidence.

Callers must treat ``PhysicsNotImplemented`` as "this quantity is unavailable"
and record it, never as a reason to substitute a plausible value.
"""

from models._stub import PhysicsNotImplemented

__all__ = ["PhysicsNotImplemented"]
