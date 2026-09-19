"""Gmsh mesh and dry run for the S1 coupled chip cell (checkpoint A).

Companion of :mod:`solvers.palace.mesh`, which stays untouched: the golden
empty-cavity generator, its attributes 1 / 2 and its model name are pinned
by the golden records. The coupled cell needs its own generator
(``implementation-plan.md`` §2): a substrate volume, a vacuum volume,
zero-thickness PEC sheets in the z = 0 plane (ground plane minus the etched
features, island, coupling pad, CPW centre conductor), the lumped-port
rectangles as separate physical surfaces, and a gap-resolving size field.

Physical tags (Palace addresses them by attribute number)::

    vacuum     1   substrate  3
    outer_pec  2   sheet_pec  4
    port_F1   10   port_R1_a 11   port_R1_b 12

The etched dielectric surfaces (etch regions minus ports and conductors)
carry no physical group: they are ordinary interior faces of the mesh.

Mesh rule (``numerical-plan.md`` §3, ENGINEERING-RULE): at ``h0`` the size
near conductor and etch edges is ``h_gap = min_gap / 2`` (two elements across
the narrowest declared gap) and far from them ``h_far = min(a, b) / 12``
(the box rule), blended by a Distance/Threshold field over ``DIST_MAX_MM``.
The ladder levels scale both sizes by ``LEVELS[level]``.

Only :func:`dry_run` is provided at this checkpoint: it meshes, counts,
estimates the degrees of freedom against the budget of
``numerical-plan.md`` §6 and writes the mesh. It never calls Palace. The
gmsh options are the deterministic ones of :mod:`solvers.palace.mesh`
(single thread, fixed algorithms, pinned random seed, MSH 2.2 ASCII), so the
same inputs give the same mesh with the same gmsh wheel on the same platform.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from solvers.palace.coupled_geometry import ChipCell, Rect
from solvers.palace.mesh import MSH_FORMAT_VERSION, _require_gmsh, gmsh_available  # noqa: F401
from solvers.palace.verification import RULES

MODEL_NAME = "coupled_chip_cell"

#: Physical attribute numbers of the coupled cell mesh.
TAGS: dict[str, int] = {
    "vacuum": 1,
    "outer_pec": 2,
    "substrate": 3,
    "sheet_pec": 4,
    "port_F1": 10,
    "port_R1_a": 11,
    "port_R1_b": 12,
}
VOLUME_TAGS = ("vacuum", "substrate")
SURFACE_TAGS = ("outer_pec", "sheet_pec", "port_F1", "port_R1_a", "port_R1_b")

#: Mesh ladder of numerical-plan.md §3: h0, h0/1.5, h0/2 as scale factors.
LEVELS: dict[int, float] = {1: 1.0, 2: 1.0 / 1.5, 3: 0.5}

#: Elements across the narrowest declared gap at h0 (numerical-plan.md §3).
GAP_ELEMENTS_AT_H0 = 2.0
#: Box rule divisor far from the conductors (numerical-plan.md §3).
BOX_RULE_DIVISOR = 12.0
#: Reach of the size-field blend from the conductor / etch edges (mm).
DIST_MAX_MM = 0.3
#: Sample points per curve of the Distance field: the field must see every
#: straight edge densely enough that the size at the edge is h_gap, so the
#: spacing is bounded by h_gap / 2 at the finest level (set per run).
DISTANCE_SAMPLING_MIN = 20

#: Order-2 DOF per tetrahedron, measured in the verification campaign on the
#: EMPTY BOX (solvers.palace.verification.RULES). Kept only as a cross-check of
#: the exact count below: extrapolating a per-tetrahedron ratio from one mesh
#: family to another is an estimate, and this dry run does not rely on it.
DOF_PER_TET_ORDER2 = float(RULES["dof_per_tetrahedron_estimate"])

#: The solver-space dimension is not estimated: for MFEM's Nedelec space on
#: tetrahedra, which is what Palace assembles for both the eigenmode and the
#: driven problem, the dimension is fixed by the mesh topology,
#:
#:     order 1 : DOF = edges
#:     order 2 : DOF = 2 * edges + 2 * faces
#:
#: and both counts are measured from the mesh. Checked against a committed
#: Palace run: the golden 22 x 22 x 1.5 mm mesh has 2083 edges and 2841 faces,
#: giving 2(2083 + 2841) = 9848, which is exactly the DegreesOfFreedom Palace
#: reports in its own palace.json for that solve
#: (results/PALACE-GOLDEN-*/QMHP-CEM-A-RF-000001/solver/postpro/palace.json).
#: tests/test_coupled_mesh.py re-verifies this against the committed record.
DOF_FORMULA_NOTE = (
    "DOF = edges (order 1) and 2*edges + 2*faces (order 2) for MFEM Nedelec "
    "spaces on tetrahedra; both are measured from the mesh topology, not "
    "estimated. The count is the assembled space dimension before any "
    "essential-boundary elimination, so it is an upper bound on the size "
    "Palace factorises, and it is exactly what Palace reports as "
    "Problem.DegreesOfFreedom."
)

#: Bounding-box tolerance used to classify fragmented faces (mm). OCC
#: bounding boxes are enlarged by its own tolerance (~1e-7).
_BBOX_TOL = 1.0e-6


def _count_edges_and_faces() -> tuple[int, int]:
    """Unique mesh edges and faces of the volume mesh, from gmsh.

    These are mesh facts, and with them the Nedelec space dimension is a
    measurement rather than an extrapolated ratio (see DOF_FORMULA_NOTE).
    Falls back to counting from the tetrahedron connectivity if gmsh's edge
    and face helpers are unavailable, so the count is never silently skipped.
    """
    import gmsh

    try:
        gmsh.model.mesh.createEdges()
        gmsh.model.mesh.createFaces()
        edge_tags, _ = gmsh.model.mesh.getAllEdges()
        face_tags, _ = gmsh.model.mesh.getAllFaces(3)
        if len(edge_tags) and len(face_tags):
            return len(set(edge_tags)), len(set(face_tags))
    except Exception:  # noqa: BLE001 - fall through to the explicit count
        pass
    edges: set[tuple[int, int]] = set()
    faces: set[tuple[int, int, int]] = set()
    _, tags, node_tags = gmsh.model.mesh.getElements(3)
    for element_nodes in node_tags:
        for i in range(0, len(element_nodes), 4):
            tet = sorted(int(x) for x in element_nodes[i : i + 4])
            for a in range(4):
                for b in range(a + 1, 4):
                    edges.add((tet[a], tet[b]))
                faces.add(tuple(x for j, x in enumerate(tet) if j != a))  # type: ignore[arg-type]
    return len(edges), len(faces)


@dataclass(frozen=True)
class DryRunReport:
    """What the dry run measured; ``as_dict()`` is JSON-serialisable."""

    level: int
    h0_gap_mm: float
    h_gap_mm: float
    h_far_mm: float
    halo_mm: float
    port_refinement: "PortRefinement | None"
    nodes: int
    tetrahedra: int
    edges: int
    faces: int
    triangles_by_tag: dict[str, int]
    tetrahedra_by_tag: dict[str, int]
    min_gap_elements: float
    dof_order2: int
    dof_order1: int
    dof_order2_cross_check_estimate: int
    within_budget_order2: bool
    within_budget_order1: bool
    dof_budget: int
    mesh_path: Path
    sha256: str
    gmsh_version: str
    wall_clock_s: float
    aborted_reason: str | None
    surface_elements_total: int
    max_surface_elements: int
    format: str = f"msh{MSH_FORMAT_VERSION}-ascii"

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": MODEL_NAME,
            "level": self.level,
            "scale": LEVELS[self.level],
            "h0_gap_mm": self.h0_gap_mm,
            "h_gap_mm": self.h_gap_mm,
            "h_far_mm": self.h_far_mm,
            "halo_mm": self.halo_mm,
            "port_refinement": (
                None if self.port_refinement is None else self.port_refinement.as_dict()
            ),
            "measured": {
                "nodes": self.nodes,
                "tetrahedra": self.tetrahedra,
                "edges": self.edges,
                "faces": self.faces,
                "triangles_by_tag": dict(self.triangles_by_tag),
                "tetrahedra_by_tag": dict(self.tetrahedra_by_tag),
                "surface_elements_total": self.surface_elements_total,
                "min_gap_elements": self.min_gap_elements,
                "dof_order1": self.dof_order1,
                "dof_order2": self.dof_order2,
                "note": DOF_FORMULA_NOTE,
            },
            "estimated": {
                "dof_order2_from_per_tetrahedron_ratio": self.dof_order2_cross_check_estimate,
                "dof_per_tetrahedron_order2": DOF_PER_TET_ORDER2,
                "ratio_to_measured": (
                    self.dof_order2_cross_check_estimate / self.dof_order2
                    if self.dof_order2 else None
                ),
                "note": (
                    "cross-check only, and the only estimated quantity in this report: the "
                    f"{DOF_PER_TET_ORDER2} DOF per tetrahedron was measured on the empty-box "
                    "mesh family of the verification campaign and is extrapolated here to a "
                    "different mesh family. Nothing in the disposition uses it."
                ),
            },
            "max_surface_elements": self.max_surface_elements,
            "dof_budget": self.dof_budget,
            "within_budget_order2": self.within_budget_order2,
            "within_budget_order1": self.within_budget_order1,
            "mesh_path": str(self.mesh_path),
            "mesh_file": self.mesh_path.name,
            "sha256": self.sha256,
            "gmsh_version": self.gmsh_version,
            "format": self.format,
            "wall_clock_s": self.wall_clock_s,
            "aborted_reason": self.aborted_reason,
            "physical_groups": dict(TAGS),
        }


def mesh_sizes_mm(cell: ChipCell, level: int) -> tuple[float, float, float]:
    """``(h0_gap, h_gap, h_far)`` of numerical-plan.md §3 for ``level``."""
    if level not in LEVELS:
        raise ValueError(f"level must be one of {sorted(LEVELS)}, got {level!r}")
    scale = LEVELS[level]
    h0_gap = cell.min_gap_mm / GAP_ELEMENTS_AT_H0
    h_far0 = min(cell.x_size_mm, cell.y_size_mm) / BOX_RULE_DIVISOR
    return h0_gap, h0_gap * scale, h_far0 * scale


def _bbox_inside(bb: tuple[float, ...], rect: Rect) -> bool:
    return (
        bb[0] >= rect.x_min - _BBOX_TOL
        and bb[3] <= rect.x_max + _BBOX_TOL
        and bb[1] >= rect.y_min - _BBOX_TOL
        and bb[4] <= rect.y_max + _BBOX_TOL
    )


def _is_plane_face(bb: tuple[float, ...], z: float) -> bool:
    return abs(bb[2] - z) <= _BBOX_TOL and abs(bb[5] - z) <= _BBOX_TOL


@dataclass(frozen=True)
class PortRefinement:
    """A local size constraint over a declared box around the lumped-port face.

    The existing Distance/Threshold field is anchored to the *conductor and
    etch curves*: it prescribes ``h_gap`` on those curves and blends linearly
    to ``h_far`` over the halo. The port face's interior is up to half its
    width from the nearest such curve, and because ``h_gap`` and ``h_far`` both
    carry the ladder's level factor while the halo does not, the size the field
    asks for at the port centre is a fixed multiple of ``h_gap`` at *every*
    level (5.04x for the S1 cell, which is 2.5x the whole port width at level 1
    and still 1.26x at level 3). Refining the ladder therefore never resolves
    the port face; only a constraint anchored to the face itself does.

    This is that constraint: a gmsh ``Box`` field holding ``h_port_mm`` over the
    port rectangle padded by ``pad_mm`` in every direction, blending back to
    ``h_far`` over ``transition_mm``, combined with the existing field by
    ``Min``.

    **It is a volume, not a face.** ``pad_mm`` applies in ``z`` as well as in
    ``x`` and ``y``, so a 0.010 mm pad around the 0.020 x 0.040 mm S1 port makes
    a 0.040 x 0.060 x 0.020 mm box reaching into vacuum AND substrate, and the
    transition carries it 0.020 mm further. Do not describe a run using it as a
    "port-face refinement": one prescribed number changes, but the perturbed
    region is a neighbourhood, and gmsh re-meshes globally in response - on the
    S1 cell 18.4 % of the baseline's nodes do not survive, out to 3.32 mm.
    Whether a mode's shift is port-mediated is settled by checking that it
    scales with that mode's port participation, not by the prescription.

    Because the box field returns ``h_far`` outside the padded box and
    the combination is a minimum, this can only refine: the distant size
    prescription is exactly the ladder's, and the geometry, materials, port
    dimensions, inductance, boundary conditions and physical groups are
    untouched. It changes the mesh and nothing else.
    """

    h_port_mm: float
    """Size held over the padded port box."""
    pad_mm: float
    """How far the box extends beyond the port rectangle, in every direction."""
    transition_mm: float
    """Distance over which the box field blends back to ``h_far``."""
    ports: tuple[str, ...] = ("port_F1",)
    """Which declared ports the boxes are built around."""
    label: str = ""
    """The approval's identifier for this refinement, e.g. "R1".

    Carried so the record and the commit headline can tell a refined run from a
    plain rerun of the same level; without it both read "L2 COMPLETED".
    """

    def __post_init__(self) -> None:
        if self.h_port_mm <= 0.0:
            raise ValueError("h_port_mm must be positive")
        if self.pad_mm < 0.0:
            raise ValueError("pad_mm must not be negative")
        if self.transition_mm <= 0.0:
            raise ValueError("transition_mm must be positive")
        if not self.ports:
            raise ValueError("a port refinement must name at least one port")
        unknown = [p for p in self.ports if p not in TAGS]
        if unknown:
            raise ValueError(f"unknown port name(s) {unknown}; known: {sorted(TAGS)}")

    def box_mm(self, rect: Rect, z0: float) -> tuple[float, float, float, float, float, float]:
        """``(x_min, x_max, y_min, y_max, z_min, z_max)`` of the padded box."""
        return (
            rect.x_min - self.pad_mm, rect.x_max + self.pad_mm,
            rect.y_min - self.pad_mm, rect.y_max + self.pad_mm,
            z0 - self.pad_mm, z0 + self.pad_mm,
        )

    def refined_volume_mm3(self, rect: Rect) -> float:
        """Volume held at ``h_port_mm``; the first-order cost of the constraint."""
        return (
            (rect.w_mm + 2.0 * self.pad_mm)
            * (rect.h_mm + 2.0 * self.pad_mm)
            * (2.0 * self.pad_mm)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.label or None,
            "h_port_mm": self.h_port_mm,
            "pad_mm": self.pad_mm,
            "transition_mm": self.transition_mm,
            "ports": list(self.ports),
            "field": "gmsh Box (VIn = h_port, VOut = h_far, Thickness = transition)",
            "combination": "Min with the existing conductor/etch Threshold",
            "can_only_refine": True,
            "holds_fixed": (
                "h_far, the conductor/etch Distance field, the halo, the geometry, the "
                "materials, the port dimensions and inductance, the boundary conditions "
                "and the physical groups"
            ),
        }


def dry_run(
    cell: ChipCell,
    level: int,
    out_dir: Path,
    dof_budget: int = 250_000,
    max_surface_elements: int = 400_000,
    halo_mm: float | None = None,
    port_refinement: PortRefinement | None = None,
    mesh_filename: str | None = None,
) -> DryRunReport:
    """Mesh the coupled cell at ladder ``level`` and report counts and DOF estimates.

    Writes ``coupled_chip_cell_L<level>.msh`` (MSH 2.2 ASCII) into ``out_dir``.
    After the surface mesh, if the number of surface elements exceeds
    ``max_surface_elements`` the volume mesh is not attempted: the surface
    mesh is written as it stands, ``tetrahedra`` is 0 and ``aborted_reason``
    says why. gmsh is always finalised.
    """
    gmsh = _require_gmsh()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    halo = DIST_MAX_MM if halo_mm is None else float(halo_mm)
    if halo <= 0.0:
        raise ValueError("halo_mm must be positive")
    mesh_path = out_dir / (mesh_filename or f"{MODEL_NAME}_L{level}.msh")
    h0_gap, h_gap, h_far = mesh_sizes_mm(cell, level)
    if not (0.0 < h_gap <= h_far):
        raise ValueError(f"mesh sizes must satisfy 0 < h_gap <= h_far, got {h_gap} and {h_far}")
    z0 = cell.z_chip_top_mm
    ports_in_order = [
        ("port_F1", cell.ports["P_F1"][0]),
        ("port_R1_a", cell.ports["P_R1"][0]),
        ("port_R1_b", cell.ports["P_R1"][1]),
    ]
    conductor_rects = cell.all_conductor_rects()
    etch_rects = list(cell.etch)

    t0 = time.perf_counter()
    aborted: str | None = None
    tets_by_tag: dict[str, int] = {k: 0 for k in VOLUME_TAGS}
    tris_by_tag: dict[str, int] = {k: 0 for k in SURFACE_TAGS}
    n_nodes = 0
    n_tets = 0
    n_surface = 0
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.NumThreads", 1)
        gmsh.option.setNumber("Mesh.MaxNumThreads1D", 1)
        gmsh.option.setNumber("Mesh.MaxNumThreads2D", 1)
        gmsh.option.setNumber("Mesh.MaxNumThreads3D", 1)
        gmsh.option.setNumber("Mesh.Algorithm", 6)      # Frontal-Delaunay (2D), as mesh.py
        gmsh.option.setNumber("Mesh.Algorithm3D", 1)    # Delaunay (3D), as mesh.py
        gmsh.option.setNumber("Mesh.RandomSeed", 1)     # pinned, as mesh.py
        gmsh.option.setNumber("Mesh.Optimize", 1)
        gmsh.option.setNumber("Mesh.OptimizeNetgen", 0)
        gmsh.option.setNumber(
            "Mesh.CharacteristicLengthMin",
            h_gap if port_refinement is None else min(h_gap, port_refinement.h_port_mm),
        )
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", h_far)
        # The background field alone sets the size: no size from points,
        # curvature or boundary extension, so the rule is exactly §3.
        gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.MshFileVersion", MSH_FORMAT_VERSION)
        gmsh.option.setNumber("Mesh.Binary", 0)
        gmsh.option.setNumber("Mesh.SaveAll", 0)

        gmsh.model.add(MODEL_NAME)
        occ = gmsh.model.occ
        dx, dy = cell.x_size_mm, cell.y_size_mm
        substrate = occ.addBox(
            cell.x_min_mm, cell.y_min_mm, cell.z_substrate_bottom_mm, dx, dy, z0 - cell.z_substrate_bottom_mm
        )
        vacuum = occ.addBox(cell.x_min_mm, cell.y_min_mm, z0, dx, dy, cell.z_lid_mm - z0)
        plane_tools = []
        for r in [*etch_rects, *conductor_rects, *(p for _, p in ports_in_order)]:
            plane_tools.append((2, occ.addRectangle(r.x_min, r.y_min, z0, r.w_mm, r.h_mm)))
        # One fragment: the two volumes share the z = 0 interface, and every
        # rectangle is imprinted into it, so all sheets are conformal.
        occ.fragment([(3, substrate), (3, vacuum)], plane_tools)
        occ.synchronize()

        volumes = gmsh.model.getEntities(3)
        vac_tags, sub_tags = [], []
        for dim, tag in volumes:
            bb = gmsh.model.getBoundingBox(dim, tag)
            (vac_tags if bb[2] >= z0 - _BBOX_TOL else sub_tags).append(tag)
        if len(vac_tags) != 1 or len(sub_tags) != 1:
            raise RuntimeError(f"expected one vacuum and one substrate volume, got {volumes}")

        outer = [tag for (_, tag) in gmsh.model.getBoundary(volumes, combined=True, oriented=False)]
        sheet: list[int] = []
        port_faces: dict[str, list[int]] = {name: [] for name, _ in ports_in_order}
        field_curves: set[int] = set()
        for dim, tag in gmsh.model.getEntities(2):
            bb = gmsh.model.getBoundingBox(dim, tag)
            if not _is_plane_face(bb, z0):
                continue
            port_name = next((name for name, r in ports_in_order if _bbox_inside(bb, r)), None)
            if port_name is not None:
                port_faces[port_name].append(tag)
                # A port face is not a conductor or etch face, so its curves are
                # not collected here. Measured on this model
                # (solvers.palace.mesh_inspection.classify_size_field_curves):
                # three of each port's four curves ARE in the field anyway,
                # contributed by the neighbouring conductor and etch faces; the
                # fourth, shared only with the untagged ground plane, is not.
                # Collecting them here would not resolve the face either - the
                # blend is what coarsens its interior - so the fix is the Box
                # field of PortRefinement, not a change to this classification.
                continue
            in_conductor = any(_bbox_inside(bb, r) for r in conductor_rects)
            in_etch = any(_bbox_inside(bb, r) for r in etch_rects)
            if in_conductor or not in_etch:
                sheet.append(tag)          # metal or ground plane
            else:
                # Etched dielectric: no physical group; its edges bound the
                # gap and drive the size field like the conductor edges.
                pass
            if in_conductor or in_etch:
                for (_, c) in gmsh.model.getBoundary([(2, tag)], oriented=False):
                    field_curves.add(c)
        missing = [name for name, faces in port_faces.items() if not faces]
        if missing:
            raise RuntimeError(f"port surfaces not found in the fragmented plane: {missing}")

        gmsh.model.addPhysicalGroup(3, vac_tags, TAGS["vacuum"])
        gmsh.model.setPhysicalName(3, TAGS["vacuum"], "vacuum")
        gmsh.model.addPhysicalGroup(3, sub_tags, TAGS["substrate"])
        gmsh.model.setPhysicalName(3, TAGS["substrate"], "substrate")
        gmsh.model.addPhysicalGroup(2, outer, TAGS["outer_pec"])
        gmsh.model.setPhysicalName(2, TAGS["outer_pec"], "outer_pec")
        gmsh.model.addPhysicalGroup(2, sheet, TAGS["sheet_pec"])
        gmsh.model.setPhysicalName(2, TAGS["sheet_pec"], "sheet_pec")
        for name, faces in port_faces.items():
            gmsh.model.addPhysicalGroup(2, faces, TAGS[name])
            gmsh.model.setPhysicalName(2, TAGS[name], name)

        # Size field: h_gap at the conductor / etch edges, h_far beyond DIST_MAX_MM.
        longest = max(max(r.w_mm, r.h_mm) for r in [*etch_rects, *conductor_rects])
        sampling = max(DISTANCE_SAMPLING_MIN, int(2.0 * longest / h_gap) + 1)
        dist = gmsh.model.mesh.field.add("Distance")
        gmsh.model.mesh.field.setNumbers(dist, "CurvesList", sorted(field_curves))
        gmsh.model.mesh.field.setNumber(dist, "Sampling", sampling)
        thr = gmsh.model.mesh.field.add("Threshold")
        gmsh.model.mesh.field.setNumber(thr, "InField", dist)
        gmsh.model.mesh.field.setNumber(thr, "SizeMin", h_gap)
        gmsh.model.mesh.field.setNumber(thr, "SizeMax", h_far)
        gmsh.model.mesh.field.setNumber(thr, "DistMin", 0.0)
        gmsh.model.mesh.field.setNumber(thr, "DistMax", halo)
        background = thr
        if port_refinement is not None:
            boxes = [thr]
            for name in port_refinement.ports:
                rect = next(r for n, r in ports_in_order if n == name)
                x0, x1, y0, y1, z_lo, z_hi = port_refinement.box_mm(rect, z0)
                box = gmsh.model.mesh.field.add("Box")
                gmsh.model.mesh.field.setNumber(box, "XMin", x0)
                gmsh.model.mesh.field.setNumber(box, "XMax", x1)
                gmsh.model.mesh.field.setNumber(box, "YMin", y0)
                gmsh.model.mesh.field.setNumber(box, "YMax", y1)
                gmsh.model.mesh.field.setNumber(box, "ZMin", z_lo)
                gmsh.model.mesh.field.setNumber(box, "ZMax", z_hi)
                gmsh.model.mesh.field.setNumber(box, "VIn", port_refinement.h_port_mm)
                # VOut is h_far, so outside the box this field is never the Min
                # and the distant prescription is exactly the ladder's.
                gmsh.model.mesh.field.setNumber(box, "VOut", h_far)
                gmsh.model.mesh.field.setNumber(box, "Thickness", port_refinement.transition_mm)
                boxes.append(box)
            background = gmsh.model.mesh.field.add("Min")
            gmsh.model.mesh.field.setNumbers(background, "FieldsList", boxes)
        gmsh.model.mesh.field.setAsBackgroundMesh(background)

        gmsh.model.mesh.generate(2)
        _, tri_tags, _ = gmsh.model.mesh.getElements(2)
        n_surface = sum(len(t) for t in tri_tags)
        if n_surface > max_surface_elements:
            aborted = (
                f"surface mesh has {n_surface} elements, above the guard of "
                f"{max_surface_elements}; the volume mesh was not attempted"
            )
        else:
            gmsh.model.mesh.generate(3)
            _, tet_tags, _ = gmsh.model.mesh.getElements(3)
            n_tets = sum(len(t) for t in tet_tags)
            if n_tets == 0:
                raise RuntimeError("gmsh produced no tetrahedra for the coupled cell")

        node_tags, _, _ = gmsh.model.mesh.getNodes()
        n_nodes = len(node_tags)
        n_edges, n_faces = _count_edges_and_faces()
        for dim, group in gmsh.model.getPhysicalGroups():
            name = gmsh.model.getPhysicalName(dim, group)
            count = 0
            for ent in gmsh.model.getEntitiesForPhysicalGroup(dim, group):
                _, elem_tags, _ = gmsh.model.mesh.getElements(dim, ent)
                count += sum(len(t) for t in elem_tags)
            (tets_by_tag if dim == 3 else tris_by_tag)[name] = count

        gmsh.write(str(mesh_path))
        version = gmsh.option.getString("General.Version")
    finally:
        gmsh.finalize()
    wall = time.perf_counter() - t0

    # Measured solver-space dimensions (see DOF_FORMULA_NOTE), not estimates.
    dof2 = 2 * n_edges + 2 * n_faces
    dof1 = n_edges
    dof2_estimate = round(DOF_PER_TET_ORDER2 * n_tets)
    return DryRunReport(
        level=level,
        h0_gap_mm=h0_gap,
        h_gap_mm=h_gap,
        h_far_mm=h_far,
        halo_mm=halo,
        port_refinement=port_refinement,
        nodes=n_nodes,
        tetrahedra=n_tets,
        edges=n_edges,
        faces=n_faces,
        triangles_by_tag=tris_by_tag,
        tetrahedra_by_tag=tets_by_tag,
        min_gap_elements=cell.min_gap_mm / h_gap,
        dof_order2=dof2,
        dof_order1=dof1,
        dof_order2_cross_check_estimate=dof2_estimate,
        within_budget_order2=(aborted is None and dof2 <= dof_budget),
        within_budget_order1=(aborted is None and dof1 <= dof_budget),
        dof_budget=dof_budget,
        mesh_path=mesh_path,
        sha256=hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
        gmsh_version=version,
        wall_clock_s=wall,
        aborted_reason=aborted,
        surface_elements_total=n_surface,
        max_surface_elements=max_surface_elements,
    )


__all__ = [
    "DIST_MAX_MM",
    "DOF_FORMULA_NOTE",
    "DOF_PER_TET_ORDER2",
    "LEVELS",
    "MODEL_NAME",
    "TAGS",
    "DryRunReport",
    "PortRefinement",
    "dry_run",
    "gmsh_available",
    "mesh_sizes_mm",
]
