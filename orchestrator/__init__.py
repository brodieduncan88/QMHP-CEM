"""QMHP-CEM orchestration (spec §11).

Python orchestrates; PicoGK geometry stays in C# behind a thin file-based
boundary. Results are append-only and every decision-relevant artifact is
SHA-256 hashed.
"""

from orchestrator import environment, lifecycle, manifest, pipeline, results_store

__all__ = ["environment", "lifecycle", "manifest", "pipeline", "results_store"]
