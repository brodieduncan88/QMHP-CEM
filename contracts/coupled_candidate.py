"""Coupled-candidate declaration contract (checkpoint A of the v0.2 milestone).

One new schema, ``qmhp-cem.coupled-candidate/0.2.0``, validating
``config/coupled/v2a_five_node_candidate.json`` as a closed typed document
(``docs/coupled-candidate/implementation-plan.md`` §1). The declaration
*references* the Object 001 :class:`contracts.candidate.Candidate` it embeds
in through ``parent_candidate_id``; it does not subclass it, so the 0.1.0
candidate contract and the golden records are untouched.

Every quantity in the declaration carries a ``binding`` of one of three
classes:

* ``SOURCE-BOUND`` — cites a source in the source register
  (``qmhp-cem.source-register/0.2.0``) by ``source_id`` and ``locator``;
* ``ENGINEERING-SEED`` — a newly proposed, unapproved value with its
  rationale; at checkpoint A no seed may be ``approved`` (ENGINEERING-RULE of
  this checkpoint: approval is a human decision recorded after review);
* ``UNBOUND`` — no source supplies it; such a quantity may only be attached
  to an item *outside* the executable scope S1, otherwise the declaration is
  not executable and validation says so.

The cross-checks below are software validation of a declaration. They are
not coupled EM evidence, and nothing here is a QMHP requirement: the only
frozen numbers read here are the 10 % consistency rule (through
:mod:`contracts.master`) and the resolution ratio of
:data:`solvers.palace.verification.RULES`; neither is restated as a literal.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal, Union

from pydantic import Field, model_validator

from contracts.candidate import CANDIDATE_ID_PATTERN
from contracts.common import StrictModel

COUPLED_CANDIDATE_SCHEMA = "qmhp-cem.coupled-candidate/0.2.0"
SOURCE_REGISTER_SCHEMA = "qmhp-cem.source-register/0.2.0"

#: Declaration ID format, e.g. QMHP-CEM-A-CC-000001 (same shape as spec §8.2).
DECLARATION_ID_PATTERN = CANDIDATE_ID_PATTERN

#: The only port directions Palace accepts for a rectangular lumped element
#: without a 3-vector (extraction-routes.md §4).
AXIS_DIRECTIONS: frozenset[str] = frozenset({"+X", "-X", "+Y", "-Y", "+Z", "-Z"})

#: Parameter-register id prefixes that name quantities outside S1 (the
#: mediator, the second device, the second readout mode).
OUTSIDE_S1_PREFIXES: tuple[str, ...] = ("mediator_", "R2_", "F2_")

#: Geometric tolerance for containment / clearance comparisons (mm). Purely
#: a floating-point guard; 1 nm is far below any declared feature.
_GEOM_TOL_MM = 1.0e-9

_ALIASED = StrictModel.model_config | {"populate_by_name": True}


# --- bindings ------------------------------------------------------------------


class SourceBoundBinding(StrictModel):
    """A quantity bound to a cited source (``source_id`` must resolve in the register)."""

    model_config = _ALIASED

    class_: Literal["SOURCE-BOUND"] = Field(alias="class")
    source_id: str
    locator: str
    note: str | None = None


class EngineeringSeedBinding(StrictModel):
    """A newly proposed value with its rationale. Unapproved at checkpoint A."""

    model_config = _ALIASED

    class_: Literal["ENGINEERING-SEED"] = Field(alias="class")
    approved: bool
    rationale: str


class UnboundBinding(StrictModel):
    """A quantity no source supplies. Allowed only outside the executable scope."""

    model_config = _ALIASED

    class_: Literal["UNBOUND"] = Field(alias="class")
    needed_from: str


Binding = Annotated[
    Union[SourceBoundBinding, EngineeringSeedBinding, UnboundBinding],
    Field(discriminator="class_"),
]


# --- sub-models ------------------------------------------------------------------


class Frame(StrictModel):
    """Coordinate frame and units (spec §7.3)."""

    origin: str
    axes: str
    length_unit: str
    frequency_unit: str
    offset_unit: str
    energy_unit: str
    capacitance_unit: str
    inductance_unit: str
    binding: Binding


class CircuitElement(StrictModel):
    """A node-to-ground element of the proposed structure."""

    id: str
    kind: Literal["josephson_junction", "superinductor", "squid_transmon", "linear_readout_mode"]
    node: str
    to: str
    E_J_GHz: float | None = None
    E_L_GHz: float | None = None
    L_nH: float | None = None
    E_J_sum_GHz: float | None = None
    asymmetry_d: float | None = None
    E_C_GHz: float | None = None
    flux_allocation: str | None = None
    junction_phase_sign: str | int | None = None
    bare_frequency_GHz: float | None = None
    binding: Binding


class Interaction(StrictModel):
    """A pairwise coupling of the proposed structure (coupling-definition.md §5)."""

    model_config = _ALIASED

    pair: tuple[str, str]
    class_: Literal["essential", "parasitic"] = Field(alias="class")
    quantity: str
    in_S1: bool
    source_value_GHz: float | None = None
    source_binding: Binding | None = None


class ProposedStructure(StrictModel):
    name: str
    description: str
    nodes: list[str]
    ground: str
    elements: list[CircuitElement]
    interactions: list[Interaction]
    executable: bool
    why_not_executable: str | None = None


class SuitabilityQuantity(StrictModel):
    id: str
    source_value: float
    binding: Binding


class ExecutableScope(StrictModel):
    """The bounded subsystem S1 the routes actually extract."""

    name: str
    nodes: list[str]
    represents: str
    claims: str
    does_not_claim: list[str]
    required_interactions: list[tuple[str, str]]
    suitability_quantities: list[SuitabilityQuantity]


class Cell(StrictModel):
    """The bounded chip cell (spec §7.3 frame: z = 0 is the chip top)."""

    x_min_mm: float
    x_max_mm: float
    y_min_mm: float
    y_max_mm: float
    z_substrate_bottom_mm: float
    z_chip_top_mm: float
    z_lid_mm: float
    binding: dict[str, Binding]

    @model_validator(mode="after")
    def _ordered(self) -> "Cell":
        if not (self.x_min_mm < self.x_max_mm and self.y_min_mm < self.y_max_mm):
            raise ValueError("cell lateral bounds must satisfy min < max")
        if not (self.z_substrate_bottom_mm < self.z_chip_top_mm < self.z_lid_mm):
            raise ValueError("cell must satisfy z_substrate_bottom < z_chip_top < z_lid")
        return self


class GroundPlane(StrictModel):
    surface: str
    model: str
    binding: Binding


class RectangleFeature(StrictModel):
    """An etched rectangular conductor (island, pad) or a rectangular site."""

    id: str
    shape: Literal["rectangle"]
    centre_mm: tuple[float, float, float]
    size_mm: tuple[float, float]
    gap_to_ground_mm: float | None = Field(default=None, gt=0)
    gap_to_island_mm: float | None = Field(default=None, gt=0)
    node: str | None = None
    spans: str | None = None
    hosts: list[str] | None = None
    binding: Binding

    @model_validator(mode="after")
    def _positive(self) -> "RectangleFeature":
        if any(s <= 0 for s in self.size_mm):
            raise ValueError(f"feature {self.id!r}: size_mm must be positive")
        return self

    def extent_mm(self, *, with_gap: bool = False) -> tuple[float, float, float, float]:
        """``(x_min, x_max, y_min, y_max)`` of the metal, optionally plus its etch gap."""
        gap = (self.gap_to_ground_mm or 0.0) if with_gap else 0.0
        cx, cy, _ = self.centre_mm
        sx, sy = self.size_mm
        return (cx - sx / 2 - gap, cx + sx / 2 + gap, cy - sy / 2 - gap, cy + sy / 2 + gap)


class CpwMeanderFeature(StrictModel):
    """A meandered CPW line described by its cross-section, length and a path text."""

    id: str
    shape: Literal["cpw_meander"]
    centre_width_mm: float = Field(gt=0)
    gap_mm: float = Field(gt=0)
    total_length_mm: float = Field(gt=0)
    path: str
    open_end: str
    shorted_end: str
    node: str | None = None
    binding: Binding


Feature = Annotated[Union[RectangleFeature, CpwMeanderFeature], Field(discriminator="shape")]


class Clearances(StrictModel):
    island_to_cell_wall_min: float = Field(ge=0)
    meander_to_cell_wall_min: float = Field(ge=0)


class Geometry(StrictModel):
    kind: str
    rationale: str
    cell: Cell
    ground_plane: GroundPlane
    features: list[Feature]
    clearances_mm: Clearances


class Material(StrictModel):
    id: str
    region: str | None = None
    material: str | None = None
    model: str | None = None
    permittivity: float | None = Field(default=None, gt=0)
    permeability: float | None = Field(default=None, gt=0)
    loss_tangent: float | None = Field(default=None, ge=0)
    binding: Binding


class BoundaryCondition(StrictModel):
    surface: str
    condition: str
    note: str | None = None


class ElectricalNode(StrictModel):
    id: str
    conductor: str | None
    ground_connection: str | None = None
    in_S1: bool
    binding: Binding | None = None


class LumpedElementS1(StrictModel):
    """A lumped element of S1 (junction, superinductor, capacitances)."""

    id: str
    E_J_GHz: float | None = None
    L_J_linear_nH: float | None = None
    E_L_GHz: float | None = None
    L_nH: float | None = None
    C_fF: float | None = None
    used_as_linear_element: bool | str | None = None
    derived_from: str | None = None
    binding: Binding


class ReadoutStructure(StrictModel):
    id: str
    type: str
    design_bare_frequency_GHz: float = Field(gt=0)
    design_coupling_GHz: float
    feedline: str
    binding: dict[str, Binding]


class PackageStructures(StrictModel):
    included: str
    omitted: str
    binding: Binding


class RouteSpec(StrictModel):
    """What a port is in one extraction route (extraction-routes.md §2, §3)."""

    kind: str
    R_ohm: float | None = Field(default=None, ge=0)
    L_nH: float | None = Field(default=None, ge=0)
    C_fF: float | None = Field(default=None, ge=0)


class Port(StrictModel):
    """A lumped port; directions must be axis-aligned (implementation-plan.md §1)."""

    id: str
    purpose: str
    node_pair: tuple[str, str]
    surface: str
    centre_mm: tuple[float, float, float] | None
    size_mm: tuple[float, float]
    direction: str | list[str]
    direction_meaning: str | None = None
    route_A: RouteSpec
    route_B: RouteSpec
    reference_plane: str
    binding: Binding

    @property
    def directions(self) -> list[str]:
        return [self.direction] if isinstance(self.direction, str) else list(self.direction)

    @model_validator(mode="after")
    def _port_rules(self) -> "Port":
        if any(s <= 0 for s in self.size_mm):
            raise ValueError(f"port {self.id!r}: size_mm must be positive, got {list(self.size_mm)}")
        if not self.directions:
            raise ValueError(f"port {self.id!r}: at least one direction is required")
        bad = [d for d in self.directions if d not in AXIS_DIRECTIONS]
        if bad:
            raise ValueError(
                f"port {self.id!r}: direction(s) {bad} are not axis-aligned; Palace lumped "
                f"ports without a 3-vector accept only {sorted(AXIS_DIRECTIONS)}"
            )
        return self


class NominalBias(StrictModel):
    model_config = _ALIASED

    F1_phi_ext_rad: str | float = Field(alias="F1.phi_ext_rad")
    binding: Binding
    flux_line: str
    C_f_C_Phi0: float | None = Field(alias="C.f_C_Phi0")
    C_binding: Binding


class PhysicalEffects(StrictModel):
    included: list[str]
    omitted: list[str]


class ParameterEntry(StrictModel):
    id: str
    value: float | str | None
    units: str
    binding: Binding
    role: str | None = None


class ReadoutLumpedEquivalent(StrictModel):
    """Lumped LC equivalent used only to size the seed (never a solver input)."""

    C_R_fF: float
    E_C_RR_MHz: float
    E_L_R_GHz: float
    n_zpf_R: float
    note: str


class ImpliedCouplingCapacitance(StrictModel):
    """What the seed geometry would have to realise to reproduce the frozen g."""

    E_C_F1R1_MHz: float
    C_c_fF: float
    formula: str
    note: str


class SeedPlausibilityCheck(StrictModel):
    """Order-of-magnitude check of a seed against an implied requirement.

    It is an estimate about an unapproved ENGINEERING-SEED, never a gate and
    never a design change: what the geometry realises is measured by the
    extraction and reported by the suitability block.
    """

    crude_edge_estimate_fF: float
    method: str
    ratio_to_requirement: float
    statement: str
    classification: str


class AnalyticSeedValues(StrictModel):
    """Derived from source-bound energies and the seed eps_r; not evidence."""

    C_sigma_fF: float
    L_super_nH: float
    L_J_linear_nH: float
    fluxonium_harmonic_mode_GHz: float
    quarter_wave_mm_at_w_r: float
    eps_eff: float
    note: str
    readout_lumped_equivalent_at_50_ohm: ReadoutLumpedEquivalent | None = None
    coupling_capacitance_implied_by_the_source_bound_g: ImpliedCouplingCapacitance | None = None
    seed_gap_plausibility_check: SeedPlausibilityCheck | None = None


class ConsistencyRule(StrictModel):
    max_relative_disagreement: float
    classification: str
    unchanged: bool


class ExtractionRef(StrictModel):
    definition: str
    routes: str
    numerical_plan: str
    consistency_rule: ConsistencyRule
    resolution_ratio: float
    resolution_ratio_source: str


# --- root --------------------------------------------------------------------------


class CoupledCandidateDeclaration(StrictModel):
    """The typed, closed coupled-candidate declaration (schema 0.2.0)."""

    model_config = _ALIASED

    schema_: Literal[COUPLED_CANDIDATE_SCHEMA] = Field(alias="schema")
    declaration_id: str
    title: str
    status: str
    master_revision: str
    created_utc: datetime
    parent_candidate_id: str
    source_register: str
    frame: Frame
    proposed_structure: ProposedStructure
    executable_scope: ExecutableScope
    geometry: Geometry
    materials: list[Material]
    boundary_conditions: list[BoundaryCondition]
    electrical_nodes: list[ElectricalNode]
    lumped_elements_S1: list[LumpedElementS1]
    readout_structures: list[ReadoutStructure]
    package_structures: PackageStructures
    ports: list[Port]
    nominal_bias: NominalBias
    physical_effects: PhysicalEffects
    parameter_register: list[ParameterEntry]
    analytic_seed_values: AnalyticSeedValues
    extraction: ExtractionRef

    # --- helpers ---------------------------------------------------------------

    @property
    def scope_nodes(self) -> set[str]:
        return set(self.executable_scope.nodes)

    def bindings(self) -> list[tuple[str, Any]]:
        """Every binding in the declaration as ``(json_path, binding)``."""
        out: list[tuple[str, Any]] = [("frame.binding", self.frame.binding)]
        for i, e in enumerate(self.proposed_structure.elements):
            out.append((f"proposed_structure.elements[{i}]({e.id}).binding", e.binding))
        for i, it in enumerate(self.proposed_structure.interactions):
            if it.source_binding is not None:
                out.append((f"proposed_structure.interactions[{i}]({'-'.join(it.pair)}).source_binding", it.source_binding))
        for i, q in enumerate(self.executable_scope.suitability_quantities):
            out.append((f"executable_scope.suitability_quantities[{i}]({q.id}).binding", q.binding))
        for k, b in self.geometry.cell.binding.items():
            out.append((f"geometry.cell.binding[{k}]", b))
        out.append(("geometry.ground_plane.binding", self.geometry.ground_plane.binding))
        for i, f in enumerate(self.geometry.features):
            out.append((f"geometry.features[{i}]({f.id}).binding", f.binding))
        for i, m in enumerate(self.materials):
            out.append((f"materials[{i}]({m.id}).binding", m.binding))
        for i, n in enumerate(self.electrical_nodes):
            if n.binding is not None:
                out.append((f"electrical_nodes[{i}]({n.id}).binding", n.binding))
        for i, le in enumerate(self.lumped_elements_S1):
            out.append((f"lumped_elements_S1[{i}]({le.id}).binding", le.binding))
        for i, r in enumerate(self.readout_structures):
            for k, b in r.binding.items():
                out.append((f"readout_structures[{i}]({r.id}).binding[{k}]", b))
        out.append(("package_structures.binding", self.package_structures.binding))
        for i, p in enumerate(self.ports):
            out.append((f"ports[{i}]({p.id}).binding", p.binding))
        out.append(("nominal_bias.binding", self.nominal_bias.binding))
        out.append(("nominal_bias.C_binding", self.nominal_bias.C_binding))
        for i, p in enumerate(self.parameter_register):
            out.append((f"parameter_register[{i}]({p.id}).binding", p.binding))
        return out

    def source_ids(self) -> set[str]:
        return {b.source_id for _, b in self.bindings() if isinstance(b, SourceBoundBinding)}

    def to_ordered_dict(self) -> dict[str, Any]:
        """The declaration as a JSON-ready dict in declaration key order.

        Fields absent from the input are omitted (``exclude_unset``), so a
        loaded file round-trips to the same document.
        """
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)

    # --- cross-validation (implementation-plan.md §1) ------------------------------

    @model_validator(mode="after")
    def _cross_checks(self) -> "CoupledCandidateDeclaration":
        problems: list[str] = []
        if not DECLARATION_ID_PATTERN.match(self.declaration_id):
            problems.append(f"declaration_id {self.declaration_id!r} does not match {DECLARATION_ID_PATTERN.pattern}")
        if not CANDIDATE_ID_PATTERN.match(self.parent_candidate_id):
            problems.append(f"parent_candidate_id {self.parent_candidate_id!r} is not a valid candidate ID")
        problems += self._check_nodes()
        problems += self._check_scope_nodes()
        problems += self._check_required_interactions()
        problems += self._check_no_approved_seed()
        problems += self._check_unbound_outside_scope()
        problems += self._check_features_in_cell()
        problems += self._check_ports()
        problems += self._check_extraction_rules()
        problems += self._check_executable_flag()
        if problems:
            raise ValueError("coupled-candidate declaration is not valid:\n  - " + "\n  - ".join(problems))
        return self

    def _check_nodes(self) -> list[str]:
        """(a) every referenced node exists in proposed_structure.nodes."""
        nodes = self.proposed_structure.nodes
        known = set(nodes)
        problems: list[str] = []
        if len(known) != len(nodes):
            problems.append(f"proposed_structure.nodes has duplicates: {nodes}")
        refs: list[tuple[str, str]] = []
        for e in self.proposed_structure.elements:
            refs.append((f"element {e.id!r}", e.node))
        for it in self.proposed_structure.interactions:
            refs += [(f"interaction {'-'.join(it.pair)}", n) for n in it.pair]
        for n in self.electrical_nodes:
            refs.append((f"electrical_nodes {n.id!r}", n.id))
        for p in self.ports:
            refs.append((f"port {p.id!r} node_pair", p.node_pair[0]))
            if p.node_pair[1] != "ground":
                refs.append((f"port {p.id!r} node_pair", p.node_pair[1]))
        refs += [("executable_scope.nodes", n) for n in self.executable_scope.nodes]
        for pair in self.executable_scope.required_interactions:
            refs += [(f"executable_scope.required_interactions {'-'.join(pair)}", n) for n in pair]
        for f in self.geometry.features:
            if f.node is not None:
                refs.append((f"feature {f.id!r}", f.node))
        for where, node in refs:
            if node not in known:
                problems.append(f"{where} names node {node!r}, which is not in proposed_structure.nodes {nodes}")
        return problems

    def _check_scope_nodes(self) -> list[str]:
        """(b) every S1 node is an electrical node with in_S1, a conductor and a ground connection."""
        problems: list[str] = []
        by_id = {n.id: n for n in self.electrical_nodes}
        if len(by_id) != len(self.electrical_nodes):
            problems.append("electrical_nodes has duplicate ids")
        for node in self.executable_scope.nodes:
            n = by_id.get(node)
            if n is None:
                problems.append(f"executable_scope node {node!r} has no electrical_nodes entry")
                continue
            if not n.in_S1:
                problems.append(f"executable_scope node {node!r} has in_S1 false in electrical_nodes")
            if n.conductor is None or n.ground_connection is None:
                problems.append(f"executable_scope node {node!r} needs a non-null conductor and ground_connection")
        for n in self.electrical_nodes:
            if n.in_S1 and (n.conductor is None or n.ground_connection is None):
                problems.append(f"electrical node {n.id!r} is in_S1 but lacks a conductor or ground_connection")
            if n.in_S1 and n.id not in self.scope_nodes:
                problems.append(f"electrical node {n.id!r} is in_S1 but not in executable_scope.nodes")
        return problems

    def _check_required_interactions(self) -> list[str]:
        """(c) required_interactions is a subset of the proposed interactions with in_S1 true."""
        problems: list[str] = []
        proposed = {frozenset(it.pair): it for it in self.proposed_structure.interactions}
        for pair in self.executable_scope.required_interactions:
            it = proposed.get(frozenset(pair))
            if it is None:
                problems.append(f"required interaction {'-'.join(pair)} is not a proposed interaction")
            elif not it.in_S1:
                problems.append(f"required interaction {'-'.join(pair)} has in_S1 false")
            elif any(n not in self.scope_nodes for n in pair):
                problems.append(f"required interaction {'-'.join(pair)} involves a node outside executable_scope.nodes")
        for it in self.proposed_structure.interactions:
            if it.in_S1 and any(n not in self.scope_nodes for n in it.pair):
                problems.append(f"interaction {'-'.join(it.pair)} has in_S1 true but a node outside the executable scope")
        return problems

    def _check_no_approved_seed(self) -> list[str]:
        """(e) checkpoint-A rule: no ENGINEERING-SEED may be approved."""
        return [
            f"{path} is an ENGINEERING-SEED with approved true; at checkpoint A every seed is "
            f"unapproved (approval is a human review decision recorded after this checkpoint)"
            for path, b in self.bindings()
            if isinstance(b, EngineeringSeedBinding) and b.approved
        ]

    def _check_unbound_outside_scope(self) -> list[str]:
        """(f) every UNBOUND binding is attached to an item outside the executable scope."""
        problems: list[str] = []
        scope = self.scope_nodes
        by_id = {n.id: n for n in self.electrical_nodes}

        def fail(path: str, why: str) -> None:
            problems.append(f"{path} is UNBOUND but {why}; an UNBOUND quantity inside S1 makes the declaration not executable")

        if isinstance(self.frame.binding, UnboundBinding):
            fail("frame.binding", "the frame is part of every scope")
        for i, e in enumerate(self.proposed_structure.elements):
            if isinstance(e.binding, UnboundBinding) and e.node in scope:
                fail(f"proposed_structure.elements[{i}]({e.id}).binding", f"its node {e.node!r} is in the executable scope")
        for i, it in enumerate(self.proposed_structure.interactions):
            if isinstance(it.source_binding, UnboundBinding) and it.in_S1:
                fail(f"proposed_structure.interactions[{i}].source_binding", "the interaction is in S1")
        for i, q in enumerate(self.executable_scope.suitability_quantities):
            if isinstance(q.binding, UnboundBinding):
                fail(f"executable_scope.suitability_quantities[{i}]({q.id}).binding", "suitability quantities are S1 references")
        for k, b in self.geometry.cell.binding.items():
            if isinstance(b, UnboundBinding):
                fail(f"geometry.cell.binding[{k}]", "the cell is the S1 domain")
        if isinstance(self.geometry.ground_plane.binding, UnboundBinding):
            fail("geometry.ground_plane.binding", "the ground plane is the S1 domain")
        for i, f in enumerate(self.geometry.features):
            if isinstance(f.binding, UnboundBinding):
                fail(f"geometry.features[{i}]({f.id}).binding", "every declared feature is S1 geometry")
        for i, m in enumerate(self.materials):
            if isinstance(m.binding, UnboundBinding):
                fail(f"materials[{i}]({m.id}).binding", "materials are S1 inputs")
        for i, n in enumerate(self.electrical_nodes):
            if isinstance(n.binding, UnboundBinding) and (n.in_S1 or n.id in scope):
                fail(f"electrical_nodes[{i}]({n.id}).binding", "the node is in S1")
        for i, le in enumerate(self.lumped_elements_S1):
            if isinstance(le.binding, UnboundBinding):
                fail(f"lumped_elements_S1[{i}]({le.id}).binding", "lumped_elements_S1 are S1 inputs")
        for i, r in enumerate(self.readout_structures):
            for k, b in r.binding.items():
                if isinstance(b, UnboundBinding) and (r.id in scope or by_id.get(r.id, None) is not None and by_id[r.id].in_S1):
                    fail(f"readout_structures[{i}]({r.id}).binding[{k}]", "the readout structure is in S1")
        if isinstance(self.package_structures.binding, UnboundBinding):
            fail("package_structures.binding", "the package stack is S1 geometry")
        for i, p in enumerate(self.ports):
            if isinstance(p.binding, UnboundBinding):
                fail(f"ports[{i}]({p.id}).binding", "ports are S1 inputs")
        if isinstance(self.nominal_bias.binding, UnboundBinding):
            fail("nominal_bias.binding", "the S1 bias must be bound")
        # nominal_bias.C_binding belongs to the mediator flux (C.*): UNBOUND is allowed.
        for i, p in enumerate(self.parameter_register):
            if isinstance(p.binding, UnboundBinding) and not p.id.startswith(OUTSIDE_S1_PREFIXES):
                fail(
                    f"parameter_register[{i}]({p.id}).binding",
                    f"its id does not name a quantity outside S1 (allowed prefixes {list(OUTSIDE_S1_PREFIXES)})",
                )
        return problems

    def _check_features_in_cell(self) -> list[str]:
        """(g) rectangles (with their gap) lie inside the cell; the island keeps its clearance."""
        problems: list[str] = []
        cell = self.geometry.cell
        clear = self.geometry.clearances_mm.island_to_cell_wall_min
        for f in self.geometry.features:
            if not isinstance(f, RectangleFeature):
                continue  # cpw_meander: positive dimensions and length are checked on the model
            x0, x1, y0, y1 = f.extent_mm(with_gap=True)
            z = f.centre_mm[2]
            if (x0 < cell.x_min_mm - _GEOM_TOL_MM or x1 > cell.x_max_mm + _GEOM_TOL_MM
                    or y0 < cell.y_min_mm - _GEOM_TOL_MM or y1 > cell.y_max_mm + _GEOM_TOL_MM):
                problems.append(
                    f"feature {f.id!r} extends to x [{x0:.4f}, {x1:.4f}] y [{y0:.4f}, {y1:.4f}] mm (with gap), "
                    f"outside the cell x [{cell.x_min_mm}, {cell.x_max_mm}] y [{cell.y_min_mm}, {cell.y_max_mm}]"
                )
            if not (cell.z_substrate_bottom_mm - _GEOM_TOL_MM <= z <= cell.z_lid_mm + _GEOM_TOL_MM):
                problems.append(f"feature {f.id!r} has z = {z} mm outside the cell [{cell.z_substrate_bottom_mm}, {cell.z_lid_mm}]")
            if f.id.endswith(".island"):
                mx0, mx1, my0, my1 = f.extent_mm(with_gap=False)
                wall = min(mx0 - cell.x_min_mm, cell.x_max_mm - mx1, my0 - cell.y_min_mm, cell.y_max_mm - my1)
                if wall + _GEOM_TOL_MM < clear:
                    problems.append(
                        f"island {f.id!r} is {wall:.4f} mm from the nearest cell wall, below the declared "
                        f"clearances_mm.island_to_cell_wall_min = {clear} mm"
                    )
        return problems

    def _check_ports(self) -> list[str]:
        """(h) directions and sizes are checked on :class:`Port`; here: ids unique, surfaces named."""
        problems: list[str] = []
        ids = [p.id for p in self.ports]
        if len(set(ids)) != len(ids):
            problems.append(f"ports have duplicate ids: {ids}")
        for p in self.ports:
            if p.node_pair[1] != "ground" and p.node_pair[0] != "ground" and p.node_pair[0] == p.node_pair[1]:
                problems.append(f"port {p.id!r} node_pair must join two distinct nodes")
        return problems

    def _check_extraction_rules(self) -> list[str]:
        """(i) the consistency rule and resolution ratio equal their sources; never restated here."""
        from contracts import master
        from solvers.palace.verification import RULES

        problems: list[str] = []
        rule = master.get("coupling_extraction.max_relative_disagreement")
        declared = self.extraction.consistency_rule.max_relative_disagreement
        if declared != rule:
            problems.append(
                f"extraction.consistency_rule.max_relative_disagreement = {declared} differs from the master "
                f"ENGINEERING-RULE coupling_extraction.max_relative_disagreement = {rule}"
            )
        ratio = RULES["height_shift_to_uncertainty_min_ratio"]
        if self.extraction.resolution_ratio != ratio:
            problems.append(
                f"extraction.resolution_ratio = {self.extraction.resolution_ratio} differs from "
                f"solvers.palace.verification.RULES['height_shift_to_uncertainty_min_ratio'] = {ratio}"
            )
        return problems

    def _check_executable_flag(self) -> list[str]:
        """(j) the proposed structure is not executable while any element is UNBOUND."""
        unbound = [e.id for e in self.proposed_structure.elements if isinstance(e.binding, UnboundBinding)]
        if unbound and self.proposed_structure.executable:
            return [f"proposed_structure.executable is true while elements {unbound} are UNBOUND"]
        return []

    def validate_against_register(self, register: "SourceRegister") -> None:
        """(d) every SOURCE-BOUND ``source_id`` resolves to a register source.

        Raises:
            ValueError: listing every unresolved id.
        """
        known = {s.id for s in register.sources}
        unresolved = sorted(self.source_ids() - known)
        if unresolved:
            raise ValueError(
                f"SOURCE-BOUND source_id(s) {unresolved} do not resolve in the source register "
                f"(known: {sorted(known)})"
            )


# --- source register ---------------------------------------------------------------


class RegisteredSource(StrictModel):
    id: str
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision: str
    authority: str
    binds: list[str]


class PalacePinned(StrictModel):
    version: str
    commit: str
    image: str
    gslib: str
    docs_checked: str


@dataclass(frozen=True)
class Mismatch:
    """A register entry whose file digest differs (``actual`` is None when missing)."""

    path: str
    expected: str
    actual: str | None

    def __str__(self) -> str:
        if self.actual is None:
            return f"{self.path}: missing (register records {self.expected[:12]}…)"
        return f"{self.path}: register records {self.expected[:12]}… but file hashes to {self.actual[:12]}…"


class SourceRegister(StrictModel):
    """Every file a SOURCE-BOUND parameter cites, with its sha256 at declaration."""

    model_config = _ALIASED

    schema_: Literal[SOURCE_REGISTER_SCHEMA] = Field(alias="schema")
    purpose: str
    repository_commit_at_declaration: str
    sources: list[RegisteredSource]
    palace_pinned: PalacePinned
    absent_from_every_source: list[str]

    @model_validator(mode="after")
    def _unique(self) -> "SourceRegister":
        ids = [s.id for s in self.sources]
        if len(set(ids)) != len(ids):
            raise ValueError(f"source register has duplicate ids: {ids}")
        return self

    def verify(self, repo_root: Path) -> list[Mismatch]:
        """Recompute every digest. Empty means every source is exactly what was cited."""
        repo_root = Path(repo_root)
        out: list[Mismatch] = []
        for s in self.sources:
            path = repo_root / s.path
            actual = _sha256_file(path) if path.is_file() else None
            if actual != s.sha256:
                out.append(Mismatch(path=s.path, expected=s.sha256, actual=actual))
        return out

    def to_ordered_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)


# --- loading -------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_of_declaration(path: Path) -> str:
    """SHA-256 of the declaration (or register) file bytes as committed."""
    return _sha256_file(Path(path))


def load_register(path: Path) -> SourceRegister:
    with Path(path).open() as fh:
        return SourceRegister.model_validate(json.load(fh))


def load_declaration(path: Path, register: SourceRegister | None = None) -> CoupledCandidateDeclaration:
    """Load and validate a declaration; with ``register``, also resolve every source id."""
    with Path(path).open() as fh:
        decl = CoupledCandidateDeclaration.model_validate(json.load(fh))
    if register is not None:
        decl.validate_against_register(register)
    return decl


__all__ = [
    "AXIS_DIRECTIONS",
    "Binding",
    "COUPLED_CANDIDATE_SCHEMA",
    "CoupledCandidateDeclaration",
    "EngineeringSeedBinding",
    "Mismatch",
    "OUTSIDE_S1_PREFIXES",
    "SOURCE_REGISTER_SCHEMA",
    "SourceBoundBinding",
    "SourceRegister",
    "UnboundBinding",
    "load_declaration",
    "load_register",
    "sha256_of_declaration",
]
