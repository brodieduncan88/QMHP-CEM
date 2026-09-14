"""Shared machinery for v0.1 physics stubs.

The physics models required by spec §5 are NOT implemented in this scaffold.
Every stub below raises :class:`PhysicsNotImplemented` rather than returning a
plausible number.

This is deliberate and load-bearing. Spec §1.2 requires the software to answer
"what can be computed now" honestly. A stub that returned an invented value
would let a gate emit PASS on evidence that does not exist, which is the exact
failure mode the evidence model exists to prevent. Callers must handle the
exception by recording the quantity as unavailable, which drives the dependent
gate to INCOMPLETE / NOT-EVALUATED.

Each stub carries the frozen regression pins it will be tested against once
implemented, so the acceptance target is stated at the point of work.
"""

from __future__ import annotations

from typing import Any


class PhysicsNotImplemented(NotImplementedError):
    """A spec §5 physics model has not been implemented in this release.

    Attributes:
        model: Short model identifier, e.g. ``"dressed_system"``.
        spec_section: The governing specification section.
        regression_pins: Frozen values the implementation must reproduce.
    """

    def __init__(
        self,
        model: str,
        spec_section: str,
        regression_pins: dict[str, Any] | None = None,
        detail: str = "",
    ) -> None:
        self.model = model
        self.spec_section = spec_section
        self.regression_pins = regression_pins or {}
        message = (
            f"physics model {model!r} is not implemented in QMHP-CEM v0.1 "
            f"(spec §{spec_section})."
        )
        if detail:
            message += f" {detail}"
        if self.regression_pins:
            pins = ", ".join(f"{k}={v}" for k, v in self.regression_pins.items())
            message += f" Implementation must reproduce: {pins}."
        super().__init__(message)
