"""QEC golden reference values (spec §4.7).

These are NOT required to make Object 001 geometry. They are retained as
golden research references and for provenance.

The correct matched-screen conclusion remains ``NO SEPARATION ESTABLISHED``
without location credit (spec §4.7, Appendix B). This module deliberately
provides no function that computes a separation claim.
"""

from __future__ import annotations

from typing import Any

from contracts import master

MATCHED_SCREEN_CONCLUSION = "NO SEPARATION ESTABLISHED"


def references() -> dict[str, Any]:
    """Frozen QEC reference values."""

    def unfreeze(node: Any) -> Any:
        if hasattr(node, "items"):
            return {k: unfreeze(v) for k, v in node.items()}
        if isinstance(node, tuple):
            return [unfreeze(v) for v in node]
        return node

    return unfreeze(master.get("qec_references"))


def p6e6_limits() -> dict[str, Any]:
    """Frozen P6-E6 joint acceptance limits (spec §6.6).

    All four conditions are required. v0.1 has no measured inputs, so the
    measured gate returns HARDWARE-GATED.
    """

    def unfreeze(node: Any) -> Any:
        if hasattr(node, "items"):
            return {k: unfreeze(v) for k, v in node.items()}
        if isinstance(node, tuple):
            return [unfreeze(v) for v in node]
        return node

    return unfreeze(master.get("p6e6_joint_acceptance"))
