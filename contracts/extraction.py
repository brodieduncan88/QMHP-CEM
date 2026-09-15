"""Typed records of the two-route coupling extraction (implementation-plan.md §1).

These are the records the execution milestone ([B]) will write. At checkpoint
A they define the admission rules only:

* a pair is ``RESOLVED`` only when *both* routes resolve it at
  ``ratio × floor`` — the ratio is
  ``solvers.palace.verification.RULES["height_shift_to_uncertainty_min_ratio"]``
  and is never restated here (coupling-definition.md §6, §9);
* ``relative_disagreement`` and ``consistent`` exist only for RESOLVED pairs
  and are computed by :class:`models.coupling_extraction.CouplingExtraction`
  (the unchanged 10 % ENGINEERING-RULE read from the master); an UNRESOLVED
  pair reports an upper bound instead, so the both-zero case can never reach
  the gate as "consistent";
* ``MISSING`` when either route has no value;
* the record verdict is ``PASS`` only when every required pair is RESOLVED and
  consistent, ``EXTRACTION-INCONSISTENT`` when a required pair is RESOLVED
  and inconsistent (never averaged), ``INCOMPLETE`` otherwise.

Nothing here is coupled EM evidence; a record is evidence only through the
solver identity and classification it carries, which the evaluator checks.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from contracts.common import Classification, GateStatus, StrictModel

EXTRACTION_RECORD_SCHEMA = "qmhp-cem.coupling-extraction-record/0.2.0"

RESOLVED, UNRESOLVED, MISSING = "RESOLVED", "UNRESOLVED", "MISSING"
Status = Literal["RESOLVED", "UNRESOLVED", "MISSING"]
Verdict = Literal["PASS", "EXTRACTION-INCONSISTENT", "INCOMPLETE"]

_DERIVED = ("status", "relative_disagreement", "consistent", "upper_bound_MHz")


def resolution_ratio() -> float:
    """The ``ratio × floor`` resolution rule, read from the verification RULES."""
    from solvers.palace.verification import RULES

    return float(RULES["height_shift_to_uncertainty_min_ratio"])


def pair_id(pair: tuple[str, str]) -> str:
    return f"{pair[0]}-{pair[1]}"


def _derive(
    route_a_MHz: float | None,
    route_a_floor_MHz: float,
    route_b_MHz: float | None,
    route_b_floor_MHz: float,
) -> dict[str, Any]:
    """Status, disagreement, consistency and upper bound from the raw route values."""
    from models.coupling_extraction import CouplingExtraction

    ratio = resolution_ratio()
    if route_a_MHz is None or route_b_MHz is None:
        return {"status": MISSING, "relative_disagreement": None, "consistent": None, "upper_bound_MHz": None}
    resolved = abs(route_a_MHz) >= ratio * route_a_floor_MHz and abs(route_b_MHz) >= ratio * route_b_floor_MHz
    if not resolved:
        return {
            "status": UNRESOLVED,
            "relative_disagreement": None,
            "consistent": None,
            "upper_bound_MHz": ratio * max(route_a_floor_MHz, route_b_floor_MHz),
        }
    ext = CouplingExtraction(eigenmode_MHz=route_a_MHz, blackbox_MHz=route_b_MHz)
    return {
        "status": RESOLVED,
        "relative_disagreement": ext.relative_disagreement,
        "consistent": ext.consistent,
        "upper_bound_MHz": None,
    }


class InteractionExtraction(StrictModel):
    """One pair, both routes, and the derived admission fields.

    Route A is the eigenmode / participation route, Route B the driven
    black-box route (extraction-routes.md §2, §3). The derived fields are
    computed from the route values; supplying them explicitly is allowed
    only when they agree with the computation, so a record cannot claim a
    resolution or a consistency it does not have.
    """

    pair: tuple[str, str]
    route_a_MHz: float | None
    route_a_floor_MHz: float = Field(gt=0)
    route_b_MHz: float | None
    route_b_floor_MHz: float = Field(gt=0)
    status: Status
    relative_disagreement: float | None = None
    consistent: bool | None = None
    upper_bound_MHz: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _fill_derived(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        floors = (data.get("route_a_floor_MHz"), data.get("route_b_floor_MHz"))
        if any(not isinstance(f, (int, float)) or isinstance(f, bool) or f <= 0 for f in floors):
            return data  # let the field validators report the floor
        derived = _derive(data.get("route_a_MHz"), float(floors[0]), data.get("route_b_MHz"), float(floors[1]))
        for key, value in derived.items():
            if key in data and data[key] != value:
                raise ValueError(
                    f"{key} = {data[key]!r} contradicts the value {value!r} derived from the route values and "
                    f"floors (pair {data.get('pair')}); derived fields may not be asserted"
                )
        return {**data, **derived}

    @property
    def resolved(self) -> bool:
        return self.status == RESOLVED

    def as_dict(self) -> dict[str, Any]:
        d = self.model_dump(mode="json")
        d["pair"] = list(self.pair)
        return d

    @classmethod
    def resolve(
        cls,
        pair: tuple[str, str],
        route_a_MHz: float | None,
        route_a_floor_MHz: float,
        route_b_MHz: float | None,
        route_b_floor_MHz: float,
    ) -> "InteractionExtraction":
        """Build a record from the raw route values (the derived fields follow)."""
        return cls.model_validate(
            {
                "pair": tuple(pair),
                "route_a_MHz": route_a_MHz,
                "route_a_floor_MHz": route_a_floor_MHz,
                "route_b_MHz": route_b_MHz,
                "route_b_floor_MHz": route_b_floor_MHz,
            }
        )


class RouteRecord(StrictModel):
    """Where one route's result came from: record path, solver identity, evidence."""

    route: Literal["A", "B"]
    method: str
    record_path: str
    record_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    solver_name: str
    solver_version: str
    classification: Classification
    convergence: dict[str, Any] = Field(default_factory=dict)
    E_C_GHz: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class CouplingExtractionRecord(StrictModel):
    """Both routes, every declared pair, and the admission verdict."""

    schema_: Literal[EXTRACTION_RECORD_SCHEMA] = Field(alias="schema", default=EXTRACTION_RECORD_SCHEMA)
    declaration_id: str
    declaration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    register_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    route_a: RouteRecord
    route_b: RouteRecord
    required_pairs: list[tuple[str, str]]
    primary_pair: tuple[str, str]
    interactions: list[InteractionExtraction]
    suitability: dict[str, Any] = Field(default_factory=dict)
    hidden_modes: list[dict[str, Any]] = Field(default_factory=list)
    verdict: Verdict

    model_config = StrictModel.model_config | {"populate_by_name": True}

    @staticmethod
    def _verdict_for(required: list[tuple[str, str]], interactions: list[InteractionExtraction]) -> str:
        by_pair = {frozenset(ie.pair): ie for ie in interactions}
        found = [by_pair.get(frozenset(p)) for p in required]
        if any(ie is not None and ie.resolved and ie.consistent is False for ie in found):
            return GateStatus.EXTRACTION_INCONSISTENT.value
        if found and all(ie is not None and ie.resolved and ie.consistent is True for ie in found):
            return GateStatus.PASS.value
        return GateStatus.INCOMPLETE.value

    @model_validator(mode="before")
    @classmethod
    def _fill_verdict(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "required_pairs" not in data or "interactions" not in data:
            return data
        try:
            interactions = [
                ie if isinstance(ie, InteractionExtraction) else InteractionExtraction.model_validate(ie)
                for ie in data["interactions"]
            ]
            required = [tuple(p) for p in data["required_pairs"]]
        except (ValueError, TypeError):
            return data  # the field validators will report the defect
        verdict = cls._verdict_for(required, interactions)
        if "verdict" in data and data["verdict"] != verdict:
            raise ValueError(f"verdict {data['verdict']!r} contradicts the derived verdict {verdict!r}; it may not be asserted")
        return {**data, "verdict": verdict}

    @model_validator(mode="after")
    def _consistent_record(self) -> "CouplingExtractionRecord":
        if self.route_a.route != "A" or self.route_b.route != "B":
            raise ValueError("route_a must carry route 'A' and route_b route 'B'")
        if frozenset(self.primary_pair) not in {frozenset(p) for p in self.required_pairs}:
            raise ValueError(f"primary_pair {list(self.primary_pair)} is not one of required_pairs")
        pairs = [frozenset(ie.pair) for ie in self.interactions]
        if len(set(pairs)) != len(pairs):
            raise ValueError("interactions list the same pair more than once")
        return self

    def interaction(self, pair: tuple[str, str]) -> InteractionExtraction | None:
        for ie in self.interactions:
            if frozenset(ie.pair) == frozenset(pair):
                return ie
        return None

    def gate_block(self) -> dict[str, float] | None:
        """``{eigenmode_MHz, blackbox_MHz}`` of the primary pair, only when RESOLVED.

        This is the scalar block the existing ``CouplingExtractionGate`` reads;
        an unresolved or missing primary pair yields ``None`` so the gate can
        never see a vanishing pair as two agreeing zeros.
        """
        ie = self.interaction(self.primary_pair)
        if ie is None or not ie.resolved:
            return None
        assert ie.route_a_MHz is not None and ie.route_b_MHz is not None
        return {"eigenmode_MHz": ie.route_a_MHz, "blackbox_MHz": ie.route_b_MHz}

    def interactions_block(self) -> dict[str, dict[str, Any]]:
        """Per-pair dict for ``dressed_system["coupling_extraction_interactions"]``."""
        return {pair_id(ie.pair): ie.as_dict() for ie in self.interactions}


__all__ = [
    "EXTRACTION_RECORD_SCHEMA",
    "CouplingExtractionRecord",
    "InteractionExtraction",
    "MISSING",
    "RESOLVED",
    "RouteRecord",
    "UNRESOLVED",
    "pair_id",
    "resolution_ratio",
]
