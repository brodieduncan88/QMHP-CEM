"""Coupling extraction and its consistency rule (spec §5.5).

Two independent extractions are required:

1. eigenmode / participation-based;
2. black-box quantization cross-check from Z(omega).

The interface returns both values independently. Inconsistent values are NEVER
silently averaged.
"""

from __future__ import annotations

from dataclasses import dataclass

from contracts import master
from models._stub import PhysicsNotImplemented


@dataclass(frozen=True)
class CouplingExtraction:
    """Two independent coupling extractions and their agreement."""

    eigenmode_MHz: float
    blackbox_MHz: float

    @property
    def relative_disagreement(self) -> float:
        """|a - b| / mean(|a|, |b|). Returns 0.0 when both are zero."""
        scale = (abs(self.eigenmode_MHz) + abs(self.blackbox_MHz)) / 2.0
        if scale == 0.0:
            return 0.0
        return abs(self.eigenmode_MHz - self.blackbox_MHz) / scale

    @property
    def consistent(self) -> bool:
        return self.relative_disagreement <= max_relative_disagreement()

    def value_MHz(self) -> float:
        """The agreed coupling.

        Raises:
            ExtractionInconsistent: if the two extractions disagree by more
                than the threshold. Never averages inconsistent values.
        """
        if not self.consistent:
            raise ExtractionInconsistent(self)
        return (self.eigenmode_MHz + self.blackbox_MHz) / 2.0


class ExtractionInconsistent(RuntimeError):
    """The two coupling extractions disagree beyond the engineering rule."""

    def __init__(self, extraction: CouplingExtraction) -> None:
        self.extraction = extraction
        super().__init__(
            f"coupling extractions disagree by "
            f"{extraction.relative_disagreement:.1%} "
            f"(eigenmode {extraction.eigenmode_MHz} MHz vs black-box "
            f"{extraction.blackbox_MHz} MHz), exceeding the "
            f"{max_relative_disagreement():.0%} ENGINEERING-RULE threshold. "
            f"Inconsistent extractions must not be averaged (spec §5.5)."
        )


def max_relative_disagreement() -> float:
    """The 10% threshold. Classification: ENGINEERING-RULE, not MASTER-FROZEN."""
    return master.get("coupling_extraction.max_relative_disagreement")


def extract_eigenmode(solver_results) -> float:  # noqa: ANN001 - stub
    """Eigenmode/participation-based coupling extraction. NOT IMPLEMENTED."""
    raise PhysicsNotImplemented(
        model="coupling_extraction_eigenmode",
        spec_section="5.5",
        detail="Requires participation ratios from an eigenmode solve.",
    )


def extract_blackbox(solver_results) -> float:  # noqa: ANN001 - stub
    """Black-box-quantization cross-check from Z(omega). NOT IMPLEMENTED."""
    raise PhysicsNotImplemented(
        model="coupling_extraction_blackbox",
        spec_section="5.5",
        detail="Requires Z(omega) from the solver result.",
    )
