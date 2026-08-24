"""Sweep definition contract (spec §8.3)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from contracts.candidate import OBJECT001
from contracts.common import StrictModel

SWEEP_SCHEMA = "qmhp-cem.sweep/0.1.0"


class SweepDefinition(StrictModel):
    """A deterministic parameter-grid sweep.

    v0.1 sweeps are deterministic grids only. They exist to prove the
    pipeline, not to optimise (spec §8.1). Bayesian, Pareto, genetic and
    AI-driven search are explicit non-goals (spec §1.3).
    """

    schema_: Literal[SWEEP_SCHEMA] = Field(alias="schema")
    name: str
    object_type: Literal[OBJECT001]
    solver: str
    base_candidate: str
    grid: dict[str, list[float]]
    ordering: list[str]
    rng_seed: int = 20260824

    model_config = StrictModel.model_config | {"populate_by_name": True}

    @model_validator(mode="after")
    def _validate(self) -> "SweepDefinition":
        if not self.grid:
            raise ValueError("sweep grid is empty")
        if sorted(self.ordering) != sorted(self.grid):
            raise ValueError(
                f"ordering {self.ordering} does not cover exactly the grid axes "
                f"{sorted(self.grid)}; candidate ordering must be deterministic "
                f"(spec §8.2)"
            )
        for axis, values in self.grid.items():
            if not values:
                raise ValueError(f"grid axis {axis!r} has no values")
            if len(set(values)) != len(values):
                raise ValueError(f"grid axis {axis!r} has duplicate values")
        return self

    @property
    def candidate_count(self) -> int:
        total = 1
        for values in self.grid.values():
            total *= len(values)
        return total

    def points(self) -> list[dict[str, Any]]:
        """Grid points in deterministic order.

        Ordering follows ``self.ordering``: the first axis is the outer loop,
        the last is the inner loop (spec §8.2).
        """
        points: list[dict[str, Any]] = [{}]
        for axis in self.ordering:
            expanded: list[dict[str, Any]] = []
            for point in points:
                for value in self.grid[axis]:
                    expanded.append({**point, axis: value})
            points = expanded
        return points
