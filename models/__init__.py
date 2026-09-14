"""QMHP-CEM physics models (spec §5).

v0.1 status: the physics models are NOT implemented. Each entry point raises
:class:`models._stub.PhysicsNotImplemented` carrying the frozen regression pins
it must reproduce. Conventions that are not physics — the tolerance RNG draw
stream, the collision threshold comparison, the coupling-extraction
consistency rule — ARE implemented.

Callers must treat PhysicsNotImplemented as "this quantity is unavailable" and
record it, never as a reason to substitute a plausible value.
"""

from models._stub import PhysicsNotImplemented

__all__ = ["PhysicsNotImplemented"]
